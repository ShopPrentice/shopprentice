import adsk.core
import adsk.fusion


def mating_bounds(body_a, body_b, normal_axis, tol=0.1):
    """Compute the contact area between two bodies at their shared interface.

    Raises ValueError if bodies are gapped, overlapping, or have no shared
    area — this is a computation, not a validation. The caller needs the
    result to position geometry, so failing early is correct.

    Args:
        body_a, body_b: The two mating bodies.
        normal_axis: 'x', 'y', or 'z' — axis perpendicular to the interface.
        tol: Contact tolerance in cm (default 0.1 = 1mm).

    Returns:
        dict with overlap bounds in model coordinates (cm).
    """
    bb_a = body_a.boundingBox
    bb_b = body_b.boundingBox

    n_a_lo = getattr(bb_a.minPoint, normal_axis)
    n_a_hi = getattr(bb_a.maxPoint, normal_axis)
    n_b_lo = getattr(bb_b.minPoint, normal_axis)
    n_b_hi = getattr(bb_b.maxPoint, normal_axis)

    normal_overlap = min(n_a_hi, n_b_hi) - max(n_a_lo, n_b_lo)

    if normal_overlap < -tol:
        gap = -normal_overlap
        raise ValueError(
            f"mating_bounds: {body_a.name} and {body_b.name} have a "
            f"{gap:.2f} cm gap along {normal_axis} axis — not in contact. "
            f"{body_a.name} {normal_axis}=[{n_a_lo:.2f}, {n_a_hi:.2f}], "
            f"{body_b.name} {normal_axis}=[{n_b_lo:.2f}, {n_b_hi:.2f}].")

    if normal_overlap > tol:
        raise ValueError(
            f"mating_bounds: {body_a.name} and {body_b.name} overlap "
            f"by {normal_overlap:.2f} cm along {normal_axis} axis — "
            f"penetrating. "
            f"{body_a.name} {normal_axis}=[{n_a_lo:.2f}, {n_a_hi:.2f}], "
            f"{body_b.name} {normal_axis}=[{n_b_lo:.2f}, {n_b_hi:.2f}].")

    para_axes = [ax for ax in ('x', 'y', 'z') if ax != normal_axis]

    result = {}
    for ax in para_axes:
        a_lo = getattr(bb_a.minPoint, ax)
        a_hi = getattr(bb_a.maxPoint, ax)
        b_lo = getattr(bb_b.minPoint, ax)
        b_hi = getattr(bb_b.maxPoint, ax)

        lo = max(a_lo, b_lo)
        hi = min(a_hi, b_hi)

        if lo >= hi:
            raise ValueError(
                f"mating_bounds: {body_a.name} and {body_b.name} have no "
                f"overlap in {ax} axis — no shared mating surface. "
                f"{body_a.name} {ax}=[{a_lo:.2f}, {a_hi:.2f}], "
                f"{body_b.name} {ax}=[{b_lo:.2f}, {b_hi:.2f}].")

        result[f'{ax}_min'] = lo
        result[f'{ax}_max'] = hi
        result[f'{ax}_center'] = (lo + hi) / 2
        result[f'{ax}_size'] = hi - lo

    return result


def check_domino_exposure(void, body_a, body_b, normal_axis, tol=0.05):
    """Check that a domino void creates blind pockets in both mating pieces.

    Prints warnings if the void extends beyond a body's boundary (exposed
    mortise). Returns a dict with 'ok' bool and any 'warnings' list.
    """
    perp_axes = [ax for ax in ('x', 'y', 'z') if ax != normal_axis]
    vbb = void.boundingBox
    warnings = []

    for body, label in [(body_a, body_a.name), (body_b, body_b.name)]:
        bbb = body.boundingBox
        for ax in perp_axes:
            v_lo = getattr(vbb.minPoint, ax)
            v_hi = getattr(vbb.maxPoint, ax)
            b_lo = getattr(bbb.minPoint, ax)
            b_hi = getattr(bbb.maxPoint, ax)

            if v_lo < b_lo - tol:
                overshoot = b_lo - v_lo
                warnings.append(
                    f"{void.name} exposed in {label} on -{ax.upper()} side: "
                    f"void {ax}={v_lo:.2f} extends {overshoot:.2f} cm "
                    f"beyond {label} {ax}_min={b_lo:.2f}")
            if v_hi > b_hi + tol:
                overshoot = v_hi - b_hi
                warnings.append(
                    f"{void.name} exposed in {label} on +{ax.upper()} side: "
                    f"void {ax}={v_hi:.2f} extends {overshoot:.2f} cm "
                    f"beyond {label} {ax}_max={b_hi:.2f}")

    if warnings:
        for w in warnings:
            print(f"WARNING check_domino_exposure: {w}")

    return {"ok": len(warnings) == 0, "warnings": warnings}


def validate_joint_contact(body_a, body_b, joint_axis=None, tol_cm=0.1):
    """Validate that two bodies have touching/overlapping faces.

    Prints warnings if bodies don't contact. Never raises — the script
    continues and issues are caught by post-phase validate_design.

    Returns:
        Dict with 'ok', 'axis', 'gap_cm', 'perp_overlaps'.
    """
    bb_a = body_a.boundingBox
    bb_b = body_b.boundingBox
    all_axes = ['x', 'y', 'z']

    def _bb_range(bb, ax):
        return (getattr(bb.minPoint, ax), getattr(bb.maxPoint, ax))

    if joint_axis is None:
        best_axis = None
        best_gap = 1e10
        for ax in all_axes:
            a_min, a_max = _bb_range(bb_a, ax)
            b_min, b_max = _bb_range(bb_b, ax)
            overlap = min(a_max, b_max) - max(a_min, b_min)
            if overlap >= -tol_cm:
                continue
            gap = -overlap
            if gap < best_gap:
                best_gap = gap
                best_axis = ax
        if best_axis is None:
            return {"ok": True, "axis": None, "gap_cm": 0.0, "perp_overlaps": {}}
        joint_axis = best_axis

    ok = True
    a_min, a_max = _bb_range(bb_a, joint_axis)
    b_min, b_max = _bb_range(bb_b, joint_axis)

    overlap_along = min(a_max, b_max) - max(a_min, b_min)
    if overlap_along < -tol_cm:
        gap = -overlap_along
        print(
            f"WARNING validate_joint_contact: {body_a.name} and "
            f"{body_b.name} have a {gap:.2f} cm gap along {joint_axis}. "
            f"{body_a.name} {joint_axis}=[{a_min:.2f}, {a_max:.2f}], "
            f"{body_b.name} {joint_axis}=[{b_min:.2f}, {b_max:.2f}].")
        ok = False

    perp_axes = [ax for ax in all_axes if ax != joint_axis]
    perp_overlaps = {}
    for pax in perp_axes:
        pa_min, pa_max = _bb_range(bb_a, pax)
        pb_min, pb_max = _bb_range(bb_b, pax)
        p_overlap = min(pa_max, pb_max) - max(pa_min, pb_min)
        perp_overlaps[pax] = p_overlap
        if p_overlap < -tol_cm:
            print(
                f"WARNING validate_joint_contact: {body_a.name} and "
                f"{body_b.name} don't overlap in {pax} — no shared "
                f"mating area. "
                f"{body_a.name} {pax}=[{pa_min:.2f}, {pa_max:.2f}], "
                f"{body_b.name} {pax}=[{pb_min:.2f}, {pb_max:.2f}].")
            ok = False

    return {
        "ok": ok,
        "axis": joint_axis,
        "gap_cm": max(0, -overlap_along),
        "perp_overlaps": perp_overlaps,
    }


# ---------------------------------------------------------------------------
# Grain-aware tenon orientation (see docs/joinery/grain-and-strength.md)
#
# Wood is strong along its fibers and splits easily across them. Cutting a
# mortise removes material from the mortise piece; to preserve its integrity the
# mortise must run WITH the grain, severing the fewest long fibers and leaving
# long-grain cheeks. Equivalently: a rectangular tenon's WIDER cross-section
# dimension must lie ALONG the mortise piece's fiber direction (a square section
# must keep one edge parallel to it). This matters most for slender mortise
# pieces (legs, rails, stretchers) where a mortise cut the wrong way leaves weak
# short-grain cheeks. The wider dimension is derived, not assumed, from the
# mortise piece's fiber direction.
# ---------------------------------------------------------------------------

def _axis_to_vec(a):
    """'x'/'y'/'z' or Vector3D -> unit Vector3D."""
    if isinstance(a, str):
        m = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}
        return adsk.core.Vector3D.create(*m[a])
    v = a.copy()
    v.normalize()
    return v


def _dominant_axis(vec):
    """Model axis name ('x'/'y'/'z') most aligned with a Vector3D."""
    return max(("x", "y", "z"), key=lambda ax: abs(getattr(vec, ax)))


def grain_axis(body):
    """Grain/fiber direction of a body as an axis name ('x'/'y'/'z').

    The body's longest bounding-box axis = its elongation = the fiber direction.
    Public wrapper over the appearance module's detector."""
    from helpers.sp.appearance import _grain_axis
    return _grain_axis(body)


def grain_vector(body):
    """Grain/fiber direction of a body as a unit Vector3D.

    Uses the principal axes of inertia (the axis with the smallest moment is the
    elongation = fiber direction); falls back to the longest bounding-box axis.
    Works for axis-aligned, slender, AND angled members. Public wrapper over the
    appearance module's detector."""
    from helpers.sp.appearance import _grain_vector
    return _grain_vector(body)


def tenon_wide_direction(mortise_body, tenon_axis):
    """Direction the tenon's WIDER cross-section dimension should run.

    = the mortise piece's fiber direction projected into the plane perpendicular
    to the tenon insertion axis, returned as a unit Vector3D. Orienting the wide
    dimension along this vector makes the mortise run WITH the grain.

    Returns None when the fiber is (nearly) parallel to the insertion axis (an
    end-grain mortise -- rare; the cross-section orientation is then unconstrained).

    Args:
        mortise_body: the piece the mortise is cut into (the tenon inserts into it).
        tenon_axis:   the insertion direction, 'x'/'y'/'z' or a Vector3D.
    """
    f = grain_vector(mortise_body)
    a = _axis_to_vec(tenon_axis)
    dot = f.dotProduct(a)
    fp = adsk.core.Vector3D.create(f.x - dot * a.x, f.y - dot * a.y, f.z - dot * a.z)
    if fp.length < 1e-6:
        return None
    fp.normalize()
    return fp


def tenon_wide_axis(mortise_body, tenon_axis):
    """Axis-aligned convenience for `tenon_wide_direction`.

    Of the two model axes perpendicular to the insertion axis, returns the one
    ('x'/'y'/'z') most aligned with the mortise piece's fiber. Build the tenon's
    WIDE cross-section dimension along it and the NARROW dimension along the other
    (a square cross-section should still keep an edge along it)."""
    d = tenon_wide_direction(mortise_body, tenon_axis)
    ta = tenon_axis if isinstance(tenon_axis, str) else _dominant_axis(tenon_axis)
    perp = [ax for ax in ("x", "y", "z") if ax != ta]
    if d is None:
        return perp[0]
    return max(perp, key=lambda ax: abs(getattr(d, ax)))


def _extent_along(body, vec):
    """Span (cm) of a body's vertices projected onto a unit direction."""
    v = _axis_to_vec(vec)
    lo, hi = 1e18, -1e18
    verts = body.vertices
    for i in range(verts.count):
        p = verts.item(i).geometry
        d = p.x * v.x + p.y * v.y + p.z * v.z
        if d < lo:
            lo = d
        if d > hi:
            hi = d
    return hi - lo


def validate_tenon_grain(tenon_body, mortise_body, tenon_axis, tol=0.12):
    """Check a tenon's WIDER cross-section dimension runs ALONG the mortise grain.

    The grain-strength rule (docs/joinery/grain-and-strength.md): a mortise must
    be cut WITH the mortise piece's grain, so the tenon's wider cross-section
    dimension lies along the fiber. This measures the tenon's extent along the
    in-section fiber direction vs across it; if the tenon is wider ACROSS the
    grain (the 90-degrees-wrong orientation) it prints a WARNING and returns
    ok=False. A square cross-section passes (one edge is parallel to the fiber by
    definition). Never raises -- mirrors validate_joint_contact; call it on the
    tenon body before JOINing it to its owner.

    This is the AXIS-ALIGNED heuristic for the real rule -- both pieces' fibers
    parallel to the glue (mating) face (see grain-and-strength.md). For ANGLED
    joints it is ADVISORY: the joint angle alone does NOT create end grain, so an
    angled tenon with long-grain cheeks is fine even if this flags it.

    Args:
        tenon_body:   the tenon (a separate body at build time, before JOIN).
        mortise_body: the piece the tenon inserts into.
        tenon_axis:   insertion direction, 'x'/'y'/'z' or Vector3D.
        tol:          square tolerance as a fraction of the wider dimension.

    Returns {ok, fiber_extent, cross_extent, square}.
    """
    u = tenon_wide_direction(mortise_body, tenon_axis)
    if u is None:
        return {"ok": True, "fiber_extent": None, "cross_extent": None,
                "square": False, "reason": "fiber parallel to insertion axis"}
    a = _axis_to_vec(tenon_axis)
    w = a.crossProduct(u)          # cross-fiber direction within the section
    w.normalize()
    ext_u = _extent_along(tenon_body, u)   # along the grain
    ext_w = _extent_along(tenon_body, w)   # across the grain
    wide = max(ext_u, ext_w)
    square = wide <= 1e-9 or (wide - min(ext_u, ext_w)) <= tol * wide
    along_ok = bool(square or ext_u >= ext_w)
    # The wider-along-grain test is the AXIS-ALIGNED heuristic. When the joint is
    # angled (the insertion axis or the in-section fibre direction isn't ~axis-
    # aligned), the real rule -- both fibres parallel to the glue face -- can hold
    # even when this heuristic doesn't, so it is ADVISORY there: never fail it.
    def _axis_aligned(v):
        return max(abs(v.x), abs(v.y), abs(v.z)) >= 0.95
    angled = not (_axis_aligned(a) and _axis_aligned(u))
    ok = bool(along_ok or angled)
    if not along_ok:
        kind = ("ADVISORY (angled joint -- the angle alone makes no end grain; "
                "verify the cheeks: are both fibres parallel to the glue face?)"
                if angled else
                "AXIS-ALIGNED joint -- rotate the tenon 90 deg (more long-long cheek, "
                "fewer fibres severed)")
        print("WARNING validate_tenon_grain: %s's wider section (%.2f cm) runs ACROSS "
              "%s's grain rather than along it (%.2f cm). %s See "
              "docs/joinery/grain-and-strength.md." % (
                  tenon_body.name, ext_w, mortise_body.name, ext_u, kind))
    return {"ok": ok, "fiber_extent": ext_u, "cross_extent": ext_w,
            "square": square, "angled": angled, "along_grain_ok": along_ok}


def validate_joint_strength(tenon_body, mortise_body, tenon_axis, species="hardwood",
                            through=False, proud=0.0, pins=0, pin_dia=0.0,
                            pin_end_distance=None, sized=False, expected=None,
                            thin_ratio=0.25, wedged=False, tusked=False,
                            max_host_severed=0.5):
    """Build-time GATE for a mortise-and-tenon, enforcing the PRINCIPLE PRIORITY.

    A correct joint must satisfy the two SHAPE principles FIRST, and the shape must
    pass ON ITS OWN, independent of any lock:
      #1  maximize long-grain-to-long-grain glue cheeks (wide dim ALONG the host grain),
      #2  sever the fewest host fibers (don't gut the host's section).
    Locks (drawbore pins, wedges, tusk, through-tenons) are OPTIONAL add-ons, checked
    SECOND. A lock can ADD capacity but NEVER substitutes for a compliant shape -- every
    lock actually severs MORE fiber -- so a lock can never flip a failing shape to ok.
    ``shape_ok`` reports the shape verdict alone; if a lock is present while the shape
    fails, a loud 'LOCK MASKS A NON-COMPLIANT SHAPE' flag fires.

    SHAPE flags (must be empty for shape_ok):
      * grain orientation wrong -- wider ACROSS the grain (via validate_tenon_grain),
      * thin slice -- thickness < ``thin_ratio`` x width (tenon's own shear/bending governs),
      * guts the host -- the mortise removes > ``max_host_severed`` of the host's section
        across its grain (the "too many fibers severed / left no walls" trap).
    LOCK flags: brittle peg relish (end distance < 4 x dia); lock-masks-shape.
    Plus an optional load-adequacy check via ``expected={mode: load_lbf}``.

    Never raises (call it on the tenon before JOIN). Args as before, plus
    ``wedged``/``tusked`` (declare locks so the gate knows one is present) and
    ``max_host_severed`` (host-gutting threshold).

    Returns {ok, shape_ok, flags, shape_flags, lock_flags, weakest, dims_in,
             capacities, utilization, estimate}.
    """
    from helpers.sp.joint_strength import estimate_mortise_tenon
    IN = 2.54
    a = _axis_to_vec(tenon_axis)
    u = tenon_wide_direction(mortise_body, tenon_axis)   # along-grain, in-section
    wv = None
    if u is None:                                        # end-grain mortise (rare)
        ta = tenon_axis if isinstance(tenon_axis, str) else _dominant_axis(a)
        perp = [ax for ax in ("x", "y", "z") if ax != ta]
        e0, e1 = _extent_along(tenon_body, perp[0]), _extent_along(tenon_body, perp[1])
        w_cm, t_cm = max(e0, e1), min(e0, e1)
    else:
        wv = a.crossProduct(u); wv.normalize()
        w_cm = _extent_along(tenon_body, u)              # along grain (the cheeks)
        t_cm = _extent_along(tenon_body, wv)             # across grain (severs fibers)
    depth_cm = _extent_along(tenon_body, a) - proud * IN
    w, t, depth = w_cm / IN, t_cm / IN, max(depth_cm, 1e-6) / IN

    est = estimate_mortise_tenon(w, t, depth, species=species, through=through,
                                 proud=proud, pins=pins, pin_dia=pin_dia,
                                 pin_end_distance=pin_end_distance, sized=sized,
                                 wedged=wedged, tusked=tusked)
    caps = est["capacities"]

    # ---- SHAPE merit (principles #1 + #2) -- must pass independent of any lock ----
    shape_flags = []
    g = validate_tenon_grain(tenon_body, mortise_body, tenon_axis)
    if not g["ok"]:
        shape_flags.append("grain: wider ACROSS host grain -> rotate so the WIDE dim runs "
                           "ALONG the grain (more glue cheek, fewer fibers cut)")
    if t < thin_ratio * w:
        shape_flags.append("thin slice: t=%.2f in < %.2f x w=%.2f in -> the tenon's own "
                           "shear/bending governs even at full glue" % (t, thin_ratio, w))
    if t < 0.1875:
        shape_flags.append("very thin tenon (t=%.2f in): fragile + shear-weak" % t)
    host_across = (_extent_along(mortise_body, wv) / IN) if wv is not None else None
    if host_across and host_across > 1e-6:
        sev = t / host_across
        if sev > max_host_severed:
            shape_flags.append("guts the host: mortise takes %.0f%% of the host section "
                               "across its grain (only %.2f in walls left) -> reshape "
                               "WIDER+SHORTER (grow width ALONG the grain, drop height)" % (
                                   100.0 * sev, max(host_across - t, 0.0)))

    # ---- LOCK merit (optional add-ons) -- a lock NEVER excuses a bad shape ----
    lock_flags = []
    has_lock = bool(pins) or wedged or tusked
    if pins and pin_dia and pin_end_distance is not None and pin_end_distance < 4.0 * pin_dia:
        lock_flags.append("brittle peg: end distance %.2f in < 4xD (%.2f in) -> relish "
                          "tear-out" % (pin_end_distance, 4.0 * pin_dia))
    if has_lock and shape_flags:
        lock_flags.append("LOCK MASKS A NON-COMPLIANT SHAPE -- fix the tenon proportions "
                          "FIRST (shape principles come before locks); a peg/wedge/tusk "
                          "adds capacity but severs MORE fiber and cannot make a bad shape ok")

    # ---- load adequacy (optional) ----
    forces = {k: v["value"] for k, v in caps.items() if v["unit"] == "lbf"}
    weakest = min(forces, key=forces.get) if forces else None
    util = {}
    overload_flags = []
    if expected:
        for k, load in expected.items():
            c = caps.get(k)
            if c and load > 0:
                util[k] = load / c["value"]
                if util[k] > 1.0:
                    overload_flags.append("OVERLOADED %s: %.0f lbf > capacity %.0f (util %.2f)"
                                          % (k, load, c["value"], util[k]))

    shape_ok = not shape_flags
    brittle = any(f.startswith("brittle") for f in lock_flags)
    flags = shape_flags + lock_flags + overload_flags
    # ok requires the SHAPE to pass on its own (principle priority) + no brittle lock +
    # no overload. Locks add capacity but can never flip a failing shape to ok.
    ok = shape_ok and not brittle and not overload_flags
    if flags:
        print("WARNING validate_joint_strength: %s (%.2f w x %.2f t x %.2f deep, %s) "
              "shape_ok=%s -> %s | weakest: %s %.0f lbf" % (
                  tenon_body.name, w, t, depth, species, shape_ok, "; ".join(flags),
                  weakest, forces.get(weakest, 0.0)))
    return {"ok": ok, "shape_ok": shape_ok, "flags": flags,
            "shape_flags": shape_flags, "lock_flags": lock_flags, "weakest": weakest,
            "dims_in": {"width": w, "thickness": t, "depth": depth},
            "capacities": caps, "utilization": util, "estimate": est}


def validate_wedged_tenon(tenon_body, mortise_body, tenon_axis, species="hardwood",
                          flare_delta=0.0625, undercut_deg=8.0, mu=0.4,
                          engaged_ratio=2.0 / 3.0, fox=False, through=True, glue=True,
                          sized=False, expected=None, thin_ratio=0.25):
    """Build-time GATE for a WEDGED tenon — the interlock counterpart of
    ``validate_joint_strength`` (a DEDICATED per-joint-type check, not an overload of the
    M&T gate). Measures the tenon off the body, runs ``joint_strength.estimate_wedged_tenon``,
    and surfaces the mechanical-interlock result + the red flags a designer should never ship:

      * grain orientation wrong (via ``validate_tenon_grain``),
      * thin slice (thickness < ``thin_ratio`` x width — the tenon's own shear/bending governs),
      * undercut angle outside the buildable band (~3-15 deg — beyond it the flat-bearing model
        and the formability of the bent half both degrade),
      * BRITTLE interlock when the joint RELIES on it (``glue=False``): the sole withdrawal
        path is mortise-cheek split (tension perp to grain) — sudden cleavage,
      * optional overload (``expected={mode: lbf}``).

    The interlock is **always** reported (its governing mode + the brittle characteristic),
    since a wedged through-tenon is essentially always split-governed in clear wood — that is
    the joint's defining behavior, not a fixable error, so it is surfaced as a NOTE and does
    not by itself fail the gate (unlike the dry-reliance case above). Never raises (mirrors
    ``validate_joint_strength``); the joinery template calls it automatically before the JOIN.

    Returns {ok, flags, notes, interlock_withdrawal, governing, brittle, withdrawal,
    dims_in, utilization, estimate}.
    """
    from helpers.sp.joint_strength import estimate_wedged_tenon
    IN = 2.54
    a = _axis_to_vec(tenon_axis)
    u = tenon_wide_direction(mortise_body, tenon_axis)
    if u is None:                                       # end-grain mortise (rare)
        ta = tenon_axis if isinstance(tenon_axis, str) else _dominant_axis(a)
        perp = [ax for ax in ("x", "y", "z") if ax != ta]
        e0, e1 = _extent_along(tenon_body, perp[0]), _extent_along(tenon_body, perp[1])
        w_cm, t_cm = max(e0, e1), min(e0, e1)
    else:
        wv = a.crossProduct(u); wv.normalize()
        w_cm = _extent_along(tenon_body, u)            # along grain (the cheeks/contact)
        t_cm = _extent_along(tenon_body, wv)           # across grain (split by the kerf)
    # Full along-axis extent (proud NOT subtracted): the interlock engages over the
    # through depth, and the gate's headline output is the interlock, not glue depth.
    depth_cm = _extent_along(tenon_body, a)
    w, t, depth = w_cm / IN, t_cm / IN, max(depth_cm, 1e-6) / IN

    est = estimate_wedged_tenon(w, t, depth, species=species, flare_delta=flare_delta,
                                undercut_deg=undercut_deg, mu=mu, engaged_ratio=engaged_ratio,
                                fox=fox, through=through, glue=glue, sized=sized)
    caps = est["capacities"]
    interlock = est["interlock_withdrawal"]
    im = est["interlock_modes"]
    gov, brittle = im["governing"], im["brittle"]

    flags, notes = [], []
    g = validate_tenon_grain(tenon_body, mortise_body, tenon_axis)
    if not g["ok"]:
        flags.append("grain orientation: wider ACROSS the grain (rotate 90 deg)")
    if t < thin_ratio * w:
        flags.append("thin slice: thickness %.2f in < %.2f x width (%.2f in)" % (t, thin_ratio, w))
    if not (3.0 <= undercut_deg <= 15.0):
        flags.append("undercut angle %.1f deg outside buildable band 3-15 deg" % undercut_deg)
    if brittle and not glue:
        flags.append("BRITTLE sole load path: dry/unglued joint relies on the interlock, which "
                     "is governed by mortise-cheek SPLIT (tension perp to grain) — sudden "
                     "cleavage; glue it, reduce flare/undercut, or hoop the mortise")
    elif brittle:
        notes.append("interlock is brittle (mortise-cheek split governs) — a backstop behind "
                     "the glue line; size with margin")
    if fox:
        notes.append("fox-wedged: spread is set by assembly (cannot be re-tightened); "
                     "leave a mortise-bottom wall")

    util = {}
    if expected:
        for k, load in expected.items():
            c = caps.get(k)
            if c and load > 0:
                util[k] = load / c["value"]
                if util[k] > 1.0:
                    flags.append("OVERLOADED %s: %.0f lbf > capacity %.0f (util %.2f)"
                                 % (k, load, c["value"], util[k]))

    ok = not flags
    head = ("%s (%.2f w x %.2f t x %.2f deep, %s): interlock %.0f lbf (%s%s), withdrawal %.0f"
            % (tenon_body.name, w, t, depth, species, interlock, gov,
               ", BRITTLE" if brittle else "", caps["withdrawal_tension"]["value"]))
    if flags:
        print("WARNING validate_wedged_tenon: %s -> %s" % (head, "; ".join(flags + notes)))
    elif notes:
        print("NOTE validate_wedged_tenon: %s -> %s" % (head, "; ".join(notes)))

    return {"ok": ok, "flags": flags, "notes": notes,
            "interlock_withdrawal": interlock, "governing": gov, "brittle": brittle,
            "withdrawal": caps["withdrawal_tension"]["value"],
            "dims_in": {"width": w, "thickness": t, "depth": depth},
            "utilization": util, "estimate": est}
