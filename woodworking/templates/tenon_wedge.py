"""Tenon wedge template — tapered inserts that spread and lock tenons.

A tenon wedge is a small tapered piece of wood driven into a slot cut
in the tenon end.  When inserted it spreads the tenon to create a
tighter fit in the mortise.  The wedge grain runs along the taper
direction; the slot is oriented perpendicular to the mortise piece's
grain to prevent splitting.

Supports arbitrary tenon orientations (axis-aligned AND compound-angle)
by deriving all geometry from the tenon's **end face**.

Variants:
  - **Rectangular tenons** (``rect``): 2 wedges at ``offset_ratio``
    from each end of the tenon cross-section.
  - **Round tenons** (``round_tenon``): 1 centred wedge, trimmed flush
    to the cylindrical surface via intersect.

Usage::

    from woodworking.templates import tenon_wedge as tw

    tw.define_params(params)

    # Axis-aligned rectangular tenon
    tw.rect(comp, tenon_body=tenon, mortise_body=leg,
            tenon_axis="x", tenon_depth_expr="mt_td",
            slot_span_expr="mt_tt", offset_dim_expr="mt_tw",
            name="TW", ev=ev)

    # Compound-angle round tenon (e.g. Windsor splayed leg)
    end = sp.find_face(leg_body, "z", +1)
    tw.round_tenon(comp, tenon_body=leg_body, mortise_body=seat,
                   end_face=end, tenon_depth_expr="seat_t",
                   tenon_diam_expr="leg_tenon_dia",
                   name="TW_FL", ev=ev)
"""

import adsk.core
import adsk.fusion
import math
from helpers import sp

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
AL = adsk.fusion.DimensionOrientations.AlignedDimensionOrientation
VI = adsk.core.ValueInput.createByString
P3 = adsk.core.Point3D.create
V3 = adsk.core.Vector3D.create


# ── Public API ──────────────────────────────────────────────────────

def define_params(params, prefix="tw", slot_w="0.1 in",
                  depth_ratio="2 / 3", offset_ratio="1 / 4",
                  undercut="6"):
    """Add wedge parameters to the design.

    ``undercut`` drives the optional MECHANICAL LOCK (``rect(flare=True)``): the wedge
    spreads the tenon into a TRAPEZOID — narrow at the mouth, wide at the end — that
    locks behind a matching undercut mortise. The trapezoid tapers over the wedge depth
    (``tenon_depth * tw_dr``) at ``tw_theta`` degrees, so the spread per half at the end
    is ``depth * tw_dr * tan(tw_theta)``. ``tw_theta`` is the undercut angle the strength
    model uses (``joint_strength.estimate_wedged_tenon``'s ``undercut_deg``).

    Returns dict ``{sw, dr, or, theta}`` → full parameter names.
    """
    p = prefix
    for pname, expr, unit, desc in [
        (f"{p}_sw",    slot_w,       "in", "Wedge slot width"),
        (f"{p}_dr",    depth_ratio,  "",   "Wedge depth ratio"),
        (f"{p}_or",    offset_ratio, "",   "Wedge offset ratio"),
        (f"{p}_theta", undercut,     "",   "Undercut / flare angle (deg)"),
    ]:
        if not params.itemByName(pname):
            params.add(pname, VI(expr), unit, desc)
    return {"sw": f"{p}_sw", "dr": f"{p}_dr", "or": f"{p}_or", "theta": f"{p}_theta"}


def rect(comp, tenon_body, mortise_body,
         tenon_depth_expr, slot_span_expr, offset_dim_expr,
         tenon_axis=None, tenon_dir=None, end_face=None,
         grain_dir=None, prefix="tw", name="TW", ev=None,
         flare=False, fox=False, species="hardwood", validate_strength=True):
    """Two wedges on a rectangular tenon, symmetric about the tenon axis.

    Provide *end_face* for arbitrary orientations (compound-angle),
    or *tenon_axis* + optional *tenon_dir* for axis-aligned tenons.

    *grain_dir* overrides auto-detected mortise grain.  Pass a tuple
    ``(x, y, z)`` when the mortise piece has ambiguous proportions
    (e.g. a nearly-square seat plank).

    *flare* models the MECHANICAL LOCK (off by default). When True, each outer
    tenon half is spread by ``{prefix}_delta`` toward the exit at ``{prefix}_theta``
    degrees of undercut, so the assembled tenon is **wider at the end than at the
    shoulder**. Build the tenon proud (through-wedged) or blind (*fox*=True), call
    this, JOIN the tenon, then CUT the mortise piece with it — the flared tenon
    carves its own matching undercut mortise, so there is no interference and the
    lock is real and visible. The flare spread is in ``off_dir`` (the wide,
    along-grain dimension), into the mortise's end-grain flares; the kerf stays
    perpendicular to the mortise grain so the spread never cleaves the long-grain
    cheeks. *flare*=False keeps the original straight-tenon behavior.

    *species* / *validate_strength*: when flaring, the wedged-tenon strength GATE
    (``sp.validate_wedged_tenon``) runs on the tenon before it is consumed — the
    forcing function lives here, not in the agent. Wrapped so it never breaks a build.
    """
    ev = ev or _default_ev()
    end_face = _resolve_end_face(
        tenon_body, mortise_body, tenon_axis, tenon_dir, end_face)

    face_n, slot_dir, off_dir = _face_directions(
        end_face, mortise_body, grain_dir=grain_dir)

    # Cache the original face centroid. After the first wedge's CUT,
    # the end face is split into fragments and re-finding it picks
    # one piece whose centroid is offset from the tenon's true centre
    # — which would make the two wedges land on the same side of the
    # tenon rather than symmetric about its axis.
    _c = end_face.centroid
    face_centroid = (_c.x, _c.y, _c.z)

    w1 = _make_wedge(comp, tenon_body, end_face, face_n, slot_dir, off_dir,
                     f"{prefix}_or", tenon_depth_expr, slot_span_expr,
                     prefix, f"{name}_1", ev,
                     offset_dim_expr=offset_dim_expr,
                     face_centroid=face_centroid)

    # Re-find end face for sketch/plane anchoring only (the cached
    # face_centroid above keeps the wedge position correct regardless
    # of which fragment this picks).
    if tenon_axis:
        end_face = _resolve_end_face(
            tenon_body, mortise_body, tenon_axis, tenon_dir, None)
    else:
        end_face = _find_face_by_normal(tenon_body, face_n)

    w2 = _make_wedge(comp, tenon_body, end_face, face_n, slot_dir, off_dir,
                     f"1 - {prefix}_or", tenon_depth_expr, slot_span_expr,
                     prefix, f"{name}_2", ev,
                     offset_dim_expr=offset_dim_expr,
                     face_centroid=face_centroid)

    if not flare:
        return [w1, w2]

    # ── Mechanical lock: spread the two outer halves into a TRAPEZOID ──
    # The flare tapers over the wedge depth (tenon_depth * tw_dr) at the tw_theta
    # undercut angle, so the tenon's outer profile becomes a trapezoid (narrow at the
    # mouth, wide at the end) and the later mortise CUT carves the matching trapezoidal
    # void — the lock. run_expr = the taper length; the spread per half = run * tan(theta).
    run_expr = f"({tenon_depth_expr}) * {prefix}_dr"

    # Gate the tenon BEFORE the flare ears (so w/t/depth are the nominal tenon).
    # Advisory — never break. flare_delta (in) = run * tan(theta).
    if validate_strength:
        try:
            axis = tenon_axis if tenon_axis else V3(face_n[0], face_n[1], face_n[2])
            theta = ev(f"{prefix}_theta")
            delta_cm = math.tan(math.radians(theta)) * ev(run_expr)
            sp.validate_wedged_tenon(
                tenon_body, mortise_body, axis, species=species,
                flare_delta=delta_cm / 2.54,
                undercut_deg=theta, fox=fox, through=not fox)
        except Exception:
            pass

    ears = []
    for sign, suff in ((+1, "FT"), (-1, "FB")):
        # Re-find the end face each pass — the prior JOIN re-splits it.
        if tenon_axis:
            ef = _resolve_end_face(tenon_body, mortise_body, tenon_axis,
                                   tenon_dir, None)
        else:
            ef = _find_face_by_normal(tenon_body, face_n)
        ears.append(_make_flare_ear(
            comp, tenon_body, ef, face_n, slot_dir, off_dir, sign,
            face_centroid, offset_dim_expr, slot_span_expr,
            f"{prefix}_theta", run_expr, prefix, f"{name}_{suff}", ev))

    return [w1, w2] + ears


def round_tenon(comp, tenon_body, mortise_body,
                tenon_depth_expr, tenon_diam_expr,
                tenon_axis=None, tenon_dir=None, end_face=None,
                grain_dir=None, prefix="tw", name="TW", ev=None,
                defer_cut=False):
    """One centred wedge on a round tenon, trimmed to the cylinder.

    *grain_dir* overrides auto-detected mortise grain.  Pass a tuple
    ``(x, y, z)`` when the mortise piece has ambiguous proportions.

    *defer_cut*: when True, build and trim the wedge but DO NOT cut its slot
    into the tenon — the caller is responsible for cutting the slot LATER
    (``sp.combine(tenon, wedge, CUT, True)``). Use this when the tenon will be
    SplitBody/rejoined downstream (e.g. a through-tenon trimmed flush): a slot
    cut made before that split has its faces orphaned when the body is
    regenerated, so ``validate_design`` reports it as zero-impact even though
    the slot is physically there. Deferring the cut until after the split keeps
    it the tenon's last feature, so its faces stay associated. The returned
    wedge still overlaps the tenon until the caller performs the cut.
    """
    ev = ev or _default_ev()
    end_face = _resolve_end_face(
        tenon_body, mortise_body, tenon_axis, tenon_dir, end_face)

    face_n, slot_dir, off_dir = _face_directions(
        end_face, mortise_body, grain_dir=grain_dir)

    wedge = _make_wedge(comp, tenon_body, end_face, face_n, slot_dir, off_dir,
                        "0.5", tenon_depth_expr, tenon_diam_expr,
                        prefix, name, ev, skip_cut=True)

    # Trim wedge to tenon cylinder + cut wedge slot in tenon. Both
    # operations route via combine so they work whether
    # tenon_body shares ``comp`` or lives in another component.
    _intersect_trim(wedge, tenon_body, f"{name}_Trim")
    if not defer_cut:
        sp.combine(tenon_body, wedge, CUT, True, f"{name}_Cut")

    return wedge


# ── Private helpers ─────────────────────────────────────────────────

def _default_ev():
    design = adsk.fusion.Design.cast(
        adsk.core.Application.get().activeProduct)
    def _ev(e):
        if isinstance(e, (int, float)):
            return float(e)
        p = design.userParameters.itemByName(e)
        if p:
            return p.value
        return design.unitsManager.evaluateExpression(e, "cm")
    return _ev


def _resolve_end_face(tenon_body, mortise_body, tenon_axis, tenon_dir, end_face):
    """Return the tenon end face (BRepFace).

    If *end_face* is provided, return it directly.
    Otherwise derive from *tenon_axis* and *tenon_dir*.
    """
    if end_face is not None:
        return end_face

    if tenon_axis is None:
        raise ValueError("Provide either end_face or tenon_axis")

    if tenon_dir is None:
        tenon_dir = _detect_tenon_dir(tenon_body, mortise_body, tenon_axis)

    return sp.find_face(tenon_body, tenon_axis, tenon_dir)


def _detect_tenon_dir(tenon_body, mortise_body, tenon_axis):
    """Return +1 if the wedge end face is at max-axis, -1 if at min-axis."""
    tbb = tenon_body.boundingBox
    mbb = mortise_body.boundingBox
    t_min = getattr(tbb.minPoint, tenon_axis)
    t_max = getattr(tbb.maxPoint, tenon_axis)
    m_min = getattr(mbb.minPoint, tenon_axis)
    m_max = getattr(mbb.maxPoint, tenon_axis)
    TOL = 0.01

    if t_max > m_max + TOL and not (t_min < m_min - TOL):
        return +1
    if t_min < m_min - TOL and not (t_max > m_max + TOL):
        return -1
    mc = (m_min + m_max) / 2
    return -1 if abs(t_min - mc) < abs(t_max - mc) else +1


def _find_face_by_normal(body, target_normal, tol=0.1):
    """Find a planar face whose normal is closest to target_normal."""
    best = None
    best_dot = -2
    for i in range(body.faces.count):
        f = body.faces.item(i)
        if not isinstance(f.geometry, adsk.core.Plane):
            continue
        ok, n = f.evaluator.getNormalAtPoint(f.pointOnFace)
        if not ok:
            continue
        dot = n.x * target_normal[0] + n.y * target_normal[1] + n.z * target_normal[2]
        if dot > best_dot:
            best_dot = dot
            best = f
    return best


def _mortise_grain(mortise_body):
    """Compute mortise grain direction as a unit-length tuple.

    Uses principal axes of inertia: the axis with the smallest moment
    is the elongation axis (grain direction).  Works for any orientation
    including compound-angle splayed legs and angled stretchers.

    Falls back to bounding-box longest axis if the API call fails.
    """
    try:
        pp = mortise_body.physicalProperties
        ok_ax, ax_x, ax_y, ax_z = pp.getPrincipalAxes()
        ok_mo, mx, my, mz = pp.getPrincipalMomentsOfInertia()
        if ok_ax and ok_mo:
            axes = [(mx, ax_x), (my, ax_y), (mz, ax_z)]
            axes.sort(key=lambda a: a[0])
            g = axes[0][1]          # smallest moment = elongation axis
            return (g.x, g.y, g.z)
    except Exception:
        pass

    # Fallback: bounding-box longest axis
    bb = mortise_body.boundingBox
    dims = {a: getattr(bb.maxPoint, a) - getattr(bb.minPoint, a)
            for a in ('x', 'y', 'z')}
    grain_axis = max(dims, key=dims.get)
    return {'x': (1, 0, 0), 'y': (0, 1, 0), 'z': (0, 0, 1)}[grain_axis]


def _face_directions(end_face, mortise_body, grain_dir=None):
    """Compute (face_normal, slot_dir, offset_dir) for the end face.

    face_normal : points outward from the tenon (away from body)
    slot_dir    : on the end face plane, ⊥ to mortise grain
    offset_dir  : on the end face plane, ⊥ to slot_dir

    *grain_dir*: optional ``(x, y, z)`` tuple overriding auto-detection.
    """
    # Face outward normal
    ok, normal = end_face.evaluator.getNormalAtPoint(end_face.pointOnFace)
    if not ok:
        normal = V3(0, 0, 1)
    fn = (normal.x, normal.y, normal.z)

    # Mortise grain direction — explicit override or auto-detect
    if grain_dir is not None:
        gv = grain_dir
    else:
        gv = _mortise_grain(mortise_body)

    # slot_dir = face_normal × grain (lies on face, ⊥ to grain)
    sx = fn[1] * gv[2] - fn[2] * gv[1]
    sy = fn[2] * gv[0] - fn[0] * gv[2]
    sz = fn[0] * gv[1] - fn[1] * gv[0]
    mag = math.sqrt(sx * sx + sy * sy + sz * sz)

    if mag < 1e-6:
        # Grain parallel to face normal — pick from a face edge
        e = end_face.edges.item(0)
        sp_g = e.startVertex.geometry
        ep_g = e.endVertex.geometry
        sx = ep_g.x - sp_g.x
        sy = ep_g.y - sp_g.y
        sz = ep_g.z - sp_g.z
        mag = math.sqrt(sx * sx + sy * sy + sz * sz)

    slot_dir = (sx / mag, sy / mag, sz / mag)

    # offset_dir = face_normal × slot_dir
    ox = fn[1] * slot_dir[2] - fn[2] * slot_dir[1]
    oy = fn[2] * slot_dir[0] - fn[0] * slot_dir[2]
    oz = fn[0] * slot_dir[1] - fn[1] * slot_dir[0]
    omag = math.sqrt(ox * ox + oy * oy + oz * oz)
    if omag < 1e-6:
        offset_dir = (0, 0, 1)
    else:
        offset_dir = (ox / omag, oy / omag, oz / omag)

    return fn, slot_dir, offset_dir


def _make_wedge(comp, tenon_body, end_face, face_n, slot_dir, off_dir,
                offset_frac_expr, tenon_depth_expr, slot_span_expr,
                prefix, name, ev, skip_cut=False,
                offset_dim_expr=None, face_centroid=None):
    """Build one wedge body on an arbitrarily oriented tenon.

    1. Draw a construction line on the end face along the slot direction.
    2. Create a plane at 90° from the end face around that line — this
       plane contains the tenon axis (face normal) and offset direction.
    3. Sketch the triangle profile on that plane.
    4. Symmetric-extrude along the slot direction for the full span.

    ``face_centroid``: optional pre-computed model-space (x, y, z) of
    the tenon end face centroid. Use this when the caller wants the
    wedge centred relative to the ORIGINAL face centre — otherwise
    the face's current ``.centroid`` is used, which may be off-centre
    if the face was split by a previous CUT (e.g., for wedge 2 of
    the 2-wedge ``rect`` variant).
    """
    sw = ev(f"{prefix}_sw")
    depth = ev(tenon_depth_expr) * ev(f"{prefix}_dr")
    span = ev(slot_span_expr)
    frac = ev(offset_frac_expr)
    if offset_dim_expr:
        off_dim = ev(offset_dim_expr)
    else:
        off_dim = span

    # ── wedge centre in model space ─────────────────────────────
    if face_centroid is not None:
        fc_x, fc_y, fc_z = face_centroid
    else:
        _c = end_face.centroid
        fc_x, fc_y, fc_z = _c.x, _c.y, _c.z
    shift = off_dim * (frac - 0.5)
    wcx = fc_x + shift * off_dir[0]
    wcy = fc_y + shift * off_dir[1]
    wcz = fc_z + shift * off_dir[2]

    # ── construction line on end face along OFFSET direction ────
    # Rotating the end face 90° around this line gives a plane
    # containing face_normal + offset_dir, ⊥ to slot_dir.
    aux_sk = comp.sketches.add(end_face)
    m2s_a = aux_sk.modelToSketchSpace
    p_ctr = m2s_a(P3(wcx, wcy, wcz))
    p_far = m2s_a(P3(wcx + off_dir[0] * 5,
                      wcy + off_dir[1] * 5,
                      wcz + off_dir[2] * 5))
    off_line = aux_sk.sketchCurves.sketchLines.addByTwoPoints(
        P3(p_ctr.x, p_ctr.y, 0), P3(p_far.x, p_far.y, 0))
    off_line.isConstruction = True
    sp.refs_to_construction(aux_sk)
    aux_sk.name = f"{name}_Aux"

    # ── plane at 90° from end face around offset line ───────────
    # Contains face_normal (tenon axis) + offset_dir; ⊥ to slot_dir
    pl_inp = comp.constructionPlanes.createInput()
    pl_inp.setByAngle(off_line, VI("90 deg"), end_face)
    perp_plane = comp.constructionPlanes.add(pl_inp)
    perp_plane.name = f"{name}_Pl"

    # ── triangle profile on the perpendicular plane ─────────────
    sk = comp.sketches.add(perp_plane)
    m2s = sk.modelToSketchSpace

    # Triangle vertices in model space:
    # A — end face, offset + sw/2   (top of slot)
    # B — end face, offset - sw/2   (bottom of slot)
    # C — depth inside tenon, offset centre  (apex)
    a_m = P3(wcx + (sw / 2) * off_dir[0],
             wcy + (sw / 2) * off_dir[1],
             wcz + (sw / 2) * off_dir[2])
    b_m = P3(wcx - (sw / 2) * off_dir[0],
             wcy - (sw / 2) * off_dir[1],
             wcz - (sw / 2) * off_dir[2])
    # C is at depth INTO the tenon (opposite to face normal)
    c_m = P3(wcx - depth * face_n[0],
             wcy - depth * face_n[1],
             wcz - depth * face_n[2])

    a = m2s(a_m); b = m2s(b_m); c = m2s(c_m)

    lines = sk.sketchCurves.sketchLines
    la = lines.addByTwoPoints(P3(a.x, a.y, 0), P3(b.x, b.y, 0))
    lb = lines.addByTwoPoints(la.endSketchPoint, P3(c.x, c.y, 0))
    lines.addByTwoPoints(lb.endSketchPoint, la.startSketchPoint)

    # Dimensions (Aligned — works at any angle)
    d = sk.sketchDimensions
    d.addDistanceDimension(
        la.startSketchPoint, la.endSketchPoint, AL,
        P3((a.x + b.x) / 2 + 0.3, (a.y + b.y) / 2, 0)
    ).parameter.expression = f"{prefix}_sw"
    d.addDistanceDimension(
        la.startSketchPoint, lb.endSketchPoint, AL,
        P3((a.x + c.x) / 2 - 0.3, (a.y + c.y) / 2, 0)
    ).parameter.expression = f"{tenon_depth_expr} * {prefix}_dr"

    sk.name = f"{name}_Sk"
    prof = sp.smallest_profile(sk)

    # ── symmetric extrude along slot direction ──────────────────
    ext = sp.ext_new_sym(comp, prof, f"{slot_span_expr} / 2", name)
    wedge = ext.bodies.item(0)
    wedge.name = name

    if not skip_cut:
        # CUT wedge slot into tenon — combine routes intra- or
        # cross-component depending on tenon_body's owning component.
        sp.combine(tenon_body, wedge, CUT, True, f"{name}_Cut")

    return wedge


def _make_flare_ear(comp, tenon_body, end_face, face_n, slot_dir, off_dir, sign,
                    face_centroid, offset_dim_expr, slot_span_expr,
                    undercut_expr, run_expr, prefix, name, ev):
    """Add one tapered FLARE EAR to a tenon's outer offset-dir edge, then JOIN it.

    The ear is a long tapered wedge of wood on the +/-off_dir extreme face of the
    tenon (``sign`` = +1 top, -1 bottom): it grows from ZERO at ``run_expr`` inside the
    end face (the kerf root) to its full spread at the end (exit) face, tapering at the
    undercut angle. Two ears (top + bottom) turn the tenon's outer profile into a
    TRAPEZOID — narrow at the shoulder/mouth, wide at the end — so a later CUT of the
    mortise piece with this tenon (plus the wedges that fill the kerfs) carves a matching
    trapezoidal/undercut mortise: the wide end can't pull back through the narrow mouth,
    so the wedged tenon is mechanically locked. No interference (the tenon IS the cut tool).

    The taper spans ``run_expr`` (= the wedge depth, ``tenon_depth * tw_dr``) so the
    trapezoid runs the full wedged region, and its side angle is ``undercut_expr`` deg;
    the spread per half is therefore ``run * tan(undercut)`` (derived, fully parametric).
    Built on the SAME perpendicular-plane machinery as ``_make_wedge`` so it works at any
    orientation.
    """
    theta = ev(undercut_expr)                     # degrees — trapezoid side angle
    flare_run = ev(run_expr)                       # taper length = wedge depth (depth*dr)
    flare = math.tan(math.radians(theta)) * flare_run   # spread per half at the end
    off_dim = ev(offset_dim_expr)

    fc_x, fc_y, fc_z = face_centroid
    # Ear base centre: the tenon's outer edge in off_dir, at the end face.
    ecx = fc_x + sign * (off_dim / 2) * off_dir[0]
    ecy = fc_y + sign * (off_dim / 2) * off_dir[1]
    ecz = fc_z + sign * (off_dim / 2) * off_dir[2]

    # ── construction line on end face along off_dir → 90° plane ──
    aux = comp.sketches.add(end_face)
    m2s_a = aux.modelToSketchSpace
    p0 = m2s_a(P3(ecx, ecy, ecz))
    p1 = m2s_a(P3(ecx + off_dir[0] * 5, ecy + off_dir[1] * 5, ecz + off_dir[2] * 5))
    off_line = aux.sketchCurves.sketchLines.addByTwoPoints(
        P3(p0.x, p0.y, 0), P3(p1.x, p1.y, 0))
    off_line.isConstruction = True
    sp.refs_to_construction(aux)
    aux.name = f"{name}_Aux"

    pl_inp = comp.constructionPlanes.createInput()
    pl_inp.setByAngle(off_line, VI("90 deg"), end_face)
    perp_plane = comp.constructionPlanes.add(pl_inp)
    perp_plane.name = f"{name}_Pl"

    # ── right-triangle ear profile on the perpendicular plane ──
    # A — outer edge at the end (exit) face            (right-angle vertex)
    # B — A + sign*flare along off_dir, at the exit     (the wide trapezoid corner)
    # C — A - flare_run along face_n (the kerf root)     (where the taper starts, width 0)
    sk = comp.sketches.add(perp_plane)
    m2s = sk.modelToSketchSpace
    a = m2s(P3(ecx, ecy, ecz))
    b = m2s(P3(ecx + sign * flare * off_dir[0],
               ecy + sign * flare * off_dir[1],
               ecz + sign * flare * off_dir[2]))
    c = m2s(P3(ecx - flare_run * face_n[0],
               ecy - flare_run * face_n[1],
               ecz - flare_run * face_n[2]))

    lines = sk.sketchCurves.sketchLines
    lab = lines.addByTwoPoints(P3(a.x, a.y, 0), P3(b.x, b.y, 0))
    lbc = lines.addByTwoPoints(lab.endSketchPoint, P3(c.x, c.y, 0))
    lines.addByTwoPoints(lbc.endSketchPoint, lab.startSketchPoint)

    d = sk.sketchDimensions
    d.addDistanceDimension(
        lab.startSketchPoint, lab.endSketchPoint, AL,
        P3((a.x + b.x) / 2, (a.y + b.y) / 2 - 0.3, 0)
    ).parameter.expression = f"({run_expr}) * tan({undercut_expr} * 1 deg)"
    d.addDistanceDimension(
        lab.startSketchPoint, lbc.endSketchPoint, AL,
        P3((a.x + c.x) / 2 - 0.3, (a.y + c.y) / 2, 0)
    ).parameter.expression = run_expr

    sk.name = f"{name}_Sk"
    prof = sp.smallest_profile(sk)

    ext = sp.ext_new_sym(comp, prof, f"{slot_span_expr} / 2", name)
    ear = ext.bodies.item(0)
    ear.name = name

    # JOIN the ear onto the tenon (combine routes intra- or cross-component).
    sp.combine(tenon_body, ear, JOIN, False, f"{name}_Join")
    return ear


def _intersect_trim(wedge, tenon_body, name):
    """Trim a wedge to the tenon body via intersect.

    Keeps only the volume of *wedge* that overlaps *tenon_body*.
    The tenon body is unchanged (``isKeepToolBodies=True``).

    Uses ``sp.combine`` so the intersect feature lives in the
    wedge's component when tenon_body shares it, or at root with
    assembly proxies when they're in different components.
    """
    INTERSECT = adsk.fusion.FeatureOperations.IntersectFeatureOperation
    sp.combine(wedge, tenon_body, INTERSECT, True, name)
