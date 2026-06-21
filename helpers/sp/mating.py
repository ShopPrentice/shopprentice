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
    ok = bool(square or ext_u >= ext_w)
    if not ok:
        print("WARNING validate_tenon_grain: %s is wider ACROSS %s's grain "
              "(%.2f cm) than along it (%.2f cm). Rotate the tenon 90 deg so its "
              "wider cross-section dimension runs ALONG the grain -- otherwise the "
              "mortise severs extra long fibers and leaves weak short-grain "
              "cheeks in %s." % (tenon_body.name, mortise_body.name, ext_w,
                                 ext_u, mortise_body.name))
    return {"ok": ok, "fiber_extent": ext_u, "cross_extent": ext_w,
            "square": square}


def _measure_tenon(tenon_body, mortise_body, tenon_axis, proud=0.0):
    """Measure a tenon body's (width ALONG grain, thickness ACROSS grain, glue depth)
    in INCHES, off the live body before JOIN. Shared by the per-type body checks.

    width  = the cross-section dim along the mortise piece's fiber (the glue cheeks),
    thick. = the cross-section dim across it,
    depth  = embedded length along the insertion axis, minus any through-proud (which
             carries no glue).
    """
    IN = 2.54
    a = _axis_to_vec(tenon_axis)
    u = tenon_wide_direction(mortise_body, tenon_axis)   # along-grain, in-section
    if u is None:                                        # end-grain mortise (rare)
        ta = tenon_axis if isinstance(tenon_axis, str) else _dominant_axis(a)
        perp = [ax for ax in ("x", "y", "z") if ax != ta]
        e0, e1 = _extent_along(tenon_body, perp[0]), _extent_along(tenon_body, perp[1])
        w_cm, t_cm = max(e0, e1), min(e0, e1)
    else:
        wv = a.crossProduct(u); wv.normalize()
        w_cm = _extent_along(tenon_body, u)              # along grain (the cheeks)
        t_cm = _extent_along(tenon_body, wv)             # across grain
    depth_cm = _extent_along(tenon_body, a) - proud * IN
    return w_cm / IN, t_cm / IN, max(depth_cm, 1e-6) / IN


def validate_mortise_tenon(tenon_body, mortise_body, tenon_axis, species="hardwood",
                           through=False, proud=0.0, sized=False, expected=None,
                           thin_ratio=0.25):
    """Build-time strength check for a (plain) mortise-and-tenon — the per-type check
    split out of the old monolith (issue 106; drawbore PEGS are now a SEPARATE concern,
    see ``validate_pegged_joint``). Measures the tenon off the body, runs the grain-
    orientation check + the pure ``joint_strength.mortise_tenon_flags`` core, and prints
    a WARNING for the LOAD-INDEPENDENT red flags a designer should never ship:

      * grain orientation wrong (wider across the grain -- via validate_tenon_grain),
      * thin slice (thickness < ``thin_ratio`` x width -> shear/bending collapse even
        with maximal glue area -- the "don't optimize glue to a sliver" trap),
      * very thin tenon (< 3/16 in).

    Optionally checks adequacy: pass ``expected={mode: load}`` (lbf, keys matching the
    estimator's capacity names) and it WARNs on any direction loaded past capacity.
    Never raises -- call it on the tenon body before JOINing it (design-time sizing
    should use ``estimate_mortise_tenon`` directly; this is the after-build safety net
    the joinery templates call).

    Args:
        tenon_body, mortise_body: the tenon (pre-JOIN) and the piece it enters.
        tenon_axis: insertion direction, 'x'/'y'/'z' or Vector3D.
        species: wood key into ``joint_strength.SPECIES``.
        through/proud: through tenon? proud length (in) -- excluded from glue depth.
        sized: end-grain glue surfaces primed/sized.
        expected: optional {capacity_name: applied_load_lbf} for an adequacy check.
        thin_ratio: thickness/width below which the tenon is flagged a thin slice.

    Returns {ok, flags, weakest, dims_in, capacities, utilization, estimate}.
    """
    from helpers.sp.joint_strength import mortise_tenon_flags
    w, t, depth = _measure_tenon(tenon_body, mortise_body, tenon_axis, proud)
    res = mortise_tenon_flags(w, t, depth, species=species, through=through,
                              proud=proud, sized=sized, expected=expected,
                              thin_ratio=thin_ratio)
    flags = list(res["flags"])
    g = validate_tenon_grain(tenon_body, mortise_body, tenon_axis)
    if not g["ok"]:
        flags.insert(0, "grain orientation: wider ACROSS the grain (rotate 90 deg)")

    est = res["est"]
    caps = est["capacities"]
    weakest = res["weakest"]
    forces = {k: v["value"] for k, v in caps.items() if v["unit"] == "lbf"}
    ok = not flags
    if flags:
        print("WARNING validate_mortise_tenon: %s (%.2f w x %.2f t x %.2f deep, %s) "
              "-> %s | weakest force dir: %s %.0f lbf" % (
                  tenon_body.name, w, t, depth, species, "; ".join(flags),
                  weakest, forces.get(weakest, 0.0)))
    return {"ok": ok, "flags": flags, "weakest": weakest,
            "dims_in": {"width": w, "thickness": t, "depth": depth},
            "capacities": caps, "utilization": res["utilization"], "estimate": est}


def validate_pegged_joint(tenon_body, mortise_body, tenon_axis, pins, pin_dia,
                          pin_end_distance, species="hardwood", peg_species=None):
    """Dedicated build-time check for a PEGGED / drawbore tenon (issue 106): the peg
    mechanism split out of the M&T sizing check. Measures the tenon (for the EYM
    bearing term), runs the pure ``joint_strength.pegged_flags`` core -- the relish
    tear-out flag (peg end distance >= 4xD) + the European-Yield-Model peg capacity
    breakdown. Never raises.

    Args:
        tenon_body, mortise_body: the tenon (pre-JOIN) and the piece it enters.
        tenon_axis: insertion direction, 'x'/'y'/'z' or Vector3D.
        pins/pin_dia/pin_end_distance: drawbore peg count/dia/end-distance (in).
        species: mortise wood key; peg_species: peg wood (else = species).

    Returns {ok, flags, pin_modes, pin_withdrawal, dims_in}.
    """
    from helpers.sp.joint_strength import pegged_flags
    w, t, depth = _measure_tenon(tenon_body, mortise_body, tenon_axis)
    res = pegged_flags(pins, pin_dia, pin_end_distance, species=species,
                       peg_species=peg_species, tenon_width=w, tenon_thickness=t,
                       tenon_depth=depth)
    flags = res["flags"]
    ok = not flags
    if flags:
        print("WARNING validate_pegged_joint: %s (%d peg(s), D=%.3f in, end dist %s) "
              "-> %s" % (tenon_body.name, pins, pin_dia,
                         ("%.2f in" % pin_end_distance) if pin_end_distance is not None
                         else "?", "; ".join(flags)))
    return {"ok": ok, "flags": flags, "pin_modes": res["pin_modes"],
            "pin_withdrawal": res["pin_withdrawal"],
            "dims_in": {"width": w, "thickness": t, "depth": depth}}


def validate_joint_strength(tenon_body, mortise_body, tenon_axis, species="hardwood",
                            through=False, proud=0.0, pins=0, pin_dia=0.0,
                            pin_end_distance=None, sized=False, expected=None,
                            thin_ratio=0.25):
    """DEPRECATED back-compat wrapper. Issue 106 split this monolith into dedicated
    per-type checks: use ``validate_mortise_tenon`` (and ``validate_pegged_joint`` for
    drawbore pegs). This keeps the old call signature working -- it runs the M&T check
    and, when pins are given, the dedicated pegged check, merging their flags. Returns
    the M&T result dict, augmented with ``pin_modes`` / ``pin_withdrawal`` when pegged.
    """
    res = validate_mortise_tenon(tenon_body, mortise_body, tenon_axis, species=species,
                                 through=through, proud=proud, sized=sized,
                                 expected=expected, thin_ratio=thin_ratio)
    if pins and pin_dia:
        peg = validate_pegged_joint(tenon_body, mortise_body, tenon_axis, pins, pin_dia,
                                    pin_end_distance, species=species)
        res["flags"] = list(res["flags"]) + list(peg["flags"])
        res["ok"] = not res["flags"]
        res["pin_modes"] = peg["pin_modes"]
        res["pin_withdrawal"] = peg["pin_withdrawal"]
    return res


def contacting_pairs(ctx, min_area_cm2=1.0):
    """Body-name pairs whose planar faces are in face-to-face contact, design-wide.

    Mirrors validate_design's planar-face overlap test (opposed coplanar faces, in-plane
    bbox overlap). Used by the deps completeness check to surface contacting bodies with
    no declared joint. Best-effort and fail-soft: any body whose faces can't be read is
    skipped, and an empty list is returned if the context has no real geometry (offline
    stubs) -- so callers can run it unconditionally inside a try/except.

    Returns a list of ``(name_a, name_b)`` tuples (names sorted within each pair) whose
    contact area is at least ``min_area_cm2``.
    """
    TOL_CM = 0.05

    def planar_faces(body):
        out = []
        try:
            faces = body.faces
            for i in range(faces.count):
                face = faces.item(i)
                if face.geometry.surfaceType != adsk.core.SurfaceTypes.PlaneSurfaceType:
                    continue
                ok, normal = face.evaluator.getNormalAtPoint(face.pointOnFace)
                if not ok:
                    continue
                bb = face.boundingBox
                if not bb:
                    continue
                out.append({"normal": normal, "point": face.pointOnFace,
                            "bb_min": [bb.minPoint.x, bb.minPoint.y, bb.minPoint.z],
                            "bb_max": [bb.maxPoint.x, bb.maxPoint.y, bb.maxPoint.z],
                            "area": face.area})
        except Exception:
            return []
        return out

    def contact_area(fa_list, fb_list):
        total = 0.0
        for fa in fa_list:
            na, pa = fa["normal"], fa["point"]
            a_min, a_max = fa["bb_min"], fa["bb_max"]
            for fb in fb_list:
                nb = fb["normal"]
                if na.x * nb.x + na.y * nb.y + na.z * nb.z > -0.95:
                    continue
                d = ((fb["point"].x - pa.x) * na.x + (fb["point"].y - pa.y) * na.y +
                     (fb["point"].z - pa.z) * na.z)
                if abs(d) > TOL_CM:
                    continue
                b_min, b_max = fb["bb_min"], fb["bb_max"]
                ax, ay, az = abs(na.x), abs(na.y), abs(na.z)
                if ax >= ay and ax >= az:
                    i1, i2 = 1, 2
                elif ay >= ax and ay >= az:
                    i1, i2 = 0, 2
                else:
                    i1, i2 = 0, 1
                o1 = min(a_max[i1], b_max[i1]) - max(a_min[i1], b_min[i1])
                o2 = min(a_max[i2], b_max[i2]) - max(a_min[i2], b_min[i2])
                if o1 <= 0 or o2 <= 0:
                    continue
                total += min(o1 * o2, fa["area"], fb["area"])
        return total

    bodies = []
    try:
        root = ctx.root
        for j in range(root.occurrences.count):
            comp = root.occurrences.item(j).component
            for i in range(comp.bRepBodies.count):
                bodies.append(comp.bRepBodies.item(i))
        for i in range(root.bRepBodies.count):
            bodies.append(root.bRepBodies.item(i))
    except Exception:
        return []

    faces = [planar_faces(b) for b in bodies]
    pairs = []
    for i in range(len(bodies)):
        if not faces[i]:
            continue
        for k in range(i + 1, len(bodies)):
            if not faces[k]:
                continue
            if contact_area(faces[i], faces[k]) >= min_area_cm2:
                na, nb = bodies[i].name, bodies[k].name
                pairs.append((na, nb) if na <= nb else (nb, na))
    return pairs
