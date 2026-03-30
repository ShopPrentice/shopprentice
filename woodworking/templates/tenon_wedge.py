"""Tenon wedge template — tapered inserts that spread and lock tenons.

A tenon wedge is a small tapered piece of wood driven into a slot cut
in the tenon end.  When inserted it spreads the tenon to create a
tighter fit in the mortise.  The wedge grain runs along the taper
direction; the slot is oriented perpendicular to the mortise piece's
grain to prevent splitting.

Supports:
  - **Rectangular tenons** (``rect``): 2 wedges at ``offset_ratio``
    from each end of the tenon cross-section.
  - **Round tenons** (``round_tenon``): 1 centred wedge, trimmed flush
    to the cylindrical surface via intersect.

Call **before** JOIN-ing the tenon into the rail body so the template
can read the standalone tenon's bounding box.  The wedge CUTs the
tenon to create its slot, then stays as a separate visible body in
the same component.

Usage::

    from helpers.templates import tenon_wedge as tw

    tw.define_params(params)

    # Rectangular tenon — 2 wedges
    tw.rect(comp, tenon_body=tenon, mortise_body=leg,
            tenon_axis="x", tenon_depth_expr="mt_td",
            slot_span_expr="mt_tw", offset_dim_expr="mt_tt",
            name="TW_FL", ev=ev)

    # Round tenon — 1 centred wedge trimmed to cylinder
    tw.round_tenon(comp, tenon_body=spindle_tenon, mortise_body=seat,
                   tenon_axis="z", tenon_depth_expr="sp_td",
                   tenon_diam_expr="sp_dia",
                   name="TW_S1", ev=ev)
"""

import adsk.core
import adsk.fusion
from helpers import sp

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
VI = adsk.core.ValueInput.createByString
P3 = adsk.core.Point3D.create


# ── Public API ──────────────────────────────────────────────────────

def define_params(params, prefix="tw", slot_w="0.1 in",
                  depth_ratio="2 / 3", offset_ratio="1 / 4"):
    """Add wedge parameters to the design.

    Parameters
    ----------
    params : UserParameters
    prefix : str
    slot_w : str   – slot width at the tenon surface
    depth_ratio : str – slot depth as a fraction of tenon depth
    offset_ratio : str – wedge centre position as a fraction from
                         each end of the offset dimension (rect only)

    Returns
    -------
    dict  ``{sw, dr, or}`` → full parameter names
    """
    p = prefix
    for pname, expr, unit, desc in [
        (f"{p}_sw", slot_w,       "in", "Wedge slot width"),
        (f"{p}_dr", depth_ratio,  "",   "Wedge depth ratio"),
        (f"{p}_or", offset_ratio, "",   "Wedge offset ratio"),
    ]:
        params.add(pname, VI(expr), unit, desc)
    return {"sw": f"{p}_sw", "dr": f"{p}_dr", "or": f"{p}_or"}


def rect(comp, tenon_body, mortise_body, tenon_axis,
         tenon_depth_expr, slot_span_expr, offset_dim_expr,
         tenon_dir=None, prefix="tw", name="TW", ev=None):
    """Two wedges on a rectangular tenon.

    The slot runs perpendicular to the mortise grain.  Wedges sit at
    ``offset_ratio`` from each end of the offset dimension.

    Parameters
    ----------
    comp : Component – component containing *tenon_body*
    tenon_body : BRepBody – the **standalone tenon** (before JOIN)
    mortise_body : BRepBody – the mortise piece (for grain detection)
    tenon_axis : str – ``'x'|'y'|'z'``, protrusion axis
    tenon_depth_expr : str – parametric depth (e.g. ``"mt_td"``)
    slot_span_expr : str – tenon extent in slot direction (e.g. ``"mt_tw"``)
    offset_dim_expr : str – tenon extent in offset direction (e.g. ``"mt_tt"``)
    tenon_dir : int|None – +1/-1, auto-detected from *mortise_body*
    prefix, name : str
    ev : callable

    Returns
    -------
    list[BRepBody]  ``[wedge_near, wedge_far]``
    """
    ev = ev or _default_ev()
    if tenon_dir is None:
        tenon_dir = _detect_tenon_dir(tenon_body, mortise_body, tenon_axis)

    mortise_grain = _detect_grain(mortise_body)
    slot_axis, offset_axis = _slot_axes(tenon_axis, mortise_grain)

    w1 = _make_wedge(comp, tenon_body, tenon_axis, slot_axis, offset_axis,
                     tenon_dir, f"{prefix}_or",
                     tenon_depth_expr, slot_span_expr,
                     prefix, f"{name}_1", ev,
                     offset_dim_expr=offset_dim_expr)

    w2 = _make_wedge(comp, tenon_body, tenon_axis, slot_axis, offset_axis,
                     tenon_dir, f"1 - {prefix}_or",
                     tenon_depth_expr, slot_span_expr,
                     prefix, f"{name}_2", ev,
                     offset_dim_expr=offset_dim_expr)

    return [w1, w2]


def round_tenon(comp, tenon_body, mortise_body, tenon_axis,
                tenon_depth_expr, tenon_diam_expr,
                tenon_dir=None, prefix="tw", name="TW", ev=None):
    """One centred wedge on a round tenon, trimmed to the cylinder.

    Parameters
    ----------
    comp : Component
    tenon_body : BRepBody – cylindrical tenon (before JOIN)
    mortise_body : BRepBody
    tenon_axis : str
    tenon_depth_expr : str
    tenon_diam_expr : str – diameter expression
    tenon_dir : int|None
    prefix, name : str
    ev : callable

    Returns
    -------
    BRepBody – the trimmed wedge
    """
    ev = ev or _default_ev()
    if tenon_dir is None:
        tenon_dir = _detect_tenon_dir(tenon_body, mortise_body, tenon_axis)

    mortise_grain = _detect_grain(mortise_body)
    slot_axis, offset_axis = _slot_axes(tenon_axis, mortise_grain)

    wedge = _make_wedge(comp, tenon_body, tenon_axis, slot_axis, offset_axis,
                        tenon_dir, "0.5",
                        tenon_depth_expr, tenon_diam_expr,
                        prefix, name, ev, skip_cut=True)

    # Trim wedge to tenon cylinder via intersect, then CUT the slot
    _intersect_trim(comp, wedge, tenon_body, f"{name}_Trim")
    sp.combine(comp, tenon_body, wedge, CUT, True, f"{name}_Cut")

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


def _detect_grain(body):
    """Longest bounding-box axis → assumed grain direction."""
    bb = body.boundingBox
    dims = {a: getattr(bb.maxPoint, a) - getattr(bb.minPoint, a)
            for a in ('x', 'y', 'z')}
    return max(dims, key=dims.get)


def _slot_axes(tenon_axis, mortise_grain):
    """Return (slot_axis, offset_axis).

    slot_axis  – perpendicular to mortise grain in the tenon cross-section;
                 the slot spans the full tenon width in this direction.
    offset_axis – the other cross-section axis (parallel to mortise grain);
                  wedges are spaced along this direction.
    """
    cross = [a for a in ('x', 'y', 'z') if a != tenon_axis]
    if mortise_grain in cross:
        slot_axis = [a for a in cross if a != mortise_grain][0]
        offset_axis = mortise_grain
    else:
        # mortise grain along tenon axis (unusual) — pick arbitrary cross axes
        slot_axis, offset_axis = cross
    return slot_axis, offset_axis


def _detect_tenon_dir(tenon_body, mortise_body, tenon_axis):
    """Return +1 if the wedge end face is at max-axis, -1 if at min-axis.

    For through tenons the end face protrudes beyond the mortise body.
    For blind tenons the end face is the deeper face (closer to the
    mortise centre).
    """
    tbb = tenon_body.boundingBox
    mbb = mortise_body.boundingBox
    t_min = getattr(tbb.minPoint, tenon_axis)
    t_max = getattr(tbb.maxPoint, tenon_axis)
    m_min = getattr(mbb.minPoint, tenon_axis)
    m_max = getattr(mbb.maxPoint, tenon_axis)
    TOL = 0.01  # cm

    protrudes_pos = t_max > m_max + TOL
    protrudes_neg = t_min < m_min - TOL

    if protrudes_pos and not protrudes_neg:
        return +1
    if protrudes_neg and not protrudes_pos:
        return -1
    # Blind — end face is the one closer to the mortise centre
    mc = (m_min + m_max) / 2
    return -1 if abs(t_min - mc) < abs(t_max - mc) else +1


def _bbox_center(body, axis):
    bb = body.boundingBox
    return (getattr(bb.minPoint, axis) + getattr(bb.maxPoint, axis)) / 2


def _plane_base_attr(axis):
    """Construction-plane attribute name perpendicular to *axis*."""
    return {'x': 'yZConstructionPlane',
            'y': 'xZConstructionPlane',
            'z': 'xYConstructionPlane'}[axis]


def _make_wedge(comp, tenon_body, tenon_axis, slot_axis, offset_axis,
                tenon_dir, offset_frac_expr,
                tenon_depth_expr, slot_span_expr,
                prefix, name, ev, skip_cut=False,
                offset_dim_expr=None):
    """Build one wedge body (triangle profile, symmetric extrude).

    Uses face-based references so it works on both standalone tenon
    bodies and tenons already JOINed into a rail.  The end face is
    found via ``find_face`` (tenon tip always protrudes furthest).
    The slot-axis and offset-axis centres are derived from the end
    face coordinate + parametric expressions.
    """
    sw = ev(f"{prefix}_sw")
    depth = ev(tenon_depth_expr) * ev(f"{prefix}_dr")
    frac = ev(offset_frac_expr)

    # End face — the tenon tip is the outermost face on the body
    end_face = sp.find_face(tenon_body, tenon_axis, tenon_dir)
    end = end_face.pointOnFace
    end_val = getattr(end, tenon_axis)

    # Slot centre — offset from end face by half the slot span
    # On the end face, the slot_axis extent = slot_span_expr.
    # Centre = end face coordinate in slot_axis (read from face point)
    slot_ctr = getattr(end, slot_axis)

    # Offset centre — from end face point + fraction of offset_dim
    off_face_val = getattr(end, offset_axis)
    if offset_dim_expr is not None:
        off_dim = ev(offset_dim_expr)
    else:
        off_dim = ev(slot_span_expr)  # fallback for round tenons
    # Shift from face centre to wedge position
    # face point is near the centre; offset from centre by (frac - 0.5)
    w_ctr = off_face_val + off_dim * (frac - 0.5)

    # Construction plane ⊥ slot_axis at tenon centre.
    # For rect tenons: offset from the planar slot-axis face (parametric).
    # For round tenons: the face is cylindrical, so fall back to a
    # component construction plane with a computed offset.
    slot_face = sp.find_face(tenon_body, slot_axis, -1)
    if slot_face and isinstance(slot_face.geometry, adsk.core.Plane):
        c_plane = sp.off_plane(
            comp, slot_face, f"{slot_span_expr} / 2", f"{name}_Pl")
    else:
        c_plane = sp.off_plane(
            comp, getattr(comp, _plane_base_attr(slot_axis)),
            f"{slot_ctr} cm", f"{name}_Pl")

    # ── triangle sketch ─────────────────────────────────────────
    sk = comp.sketches.add(c_plane)
    m2s = sk.modelToSketchSpace

    def mpt(ta, sa, oa):
        c = {tenon_axis: ta, slot_axis: sa, offset_axis: oa}
        return P3(c['x'], c['y'], c['z'])

    a_m = mpt(end_val, slot_ctr, w_ctr + sw / 2)
    b_m = mpt(end_val, slot_ctr, w_ctr - sw / 2)
    c_m = mpt(end_val - tenon_dir * depth, slot_ctr, w_ctr)

    a = m2s(a_m); b = m2s(b_m); c = m2s(c_m)

    lines = sk.sketchCurves.sketchLines
    la = lines.addByTwoPoints(P3(a.x, a.y, 0), P3(b.x, b.y, 0))
    lb = lines.addByTwoPoints(la.endSketchPoint, P3(c.x, c.y, 0))
    lines.addByTwoPoints(lb.endSketchPoint, la.startSketchPoint)

    # AB runs along offset_axis — constrain H or V
    orient = sp.probe_orientations(sk, a_m.x, a_m.y, a_m.z)
    V_e = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
    if orient[offset_axis] == V_e:
        sk.geometricConstraints.addVertical(la)
    else:
        sk.geometricConstraints.addHorizontal(la)

    # parametric dimensions
    d = sk.sketchDimensions
    # base width = tw_sw
    d.addDistanceDimension(
        la.startSketchPoint, la.endSketchPoint, orient[offset_axis],
        P3((a.x + b.x) / 2 + 0.3, (a.y + b.y) / 2, 0)
    ).parameter.expression = f"{prefix}_sw"
    # depth = tenon_depth * tw_dr
    d.addDistanceDimension(
        la.startSketchPoint, lb.endSketchPoint, orient[tenon_axis],
        P3((a.x + c.x) / 2, (a.y + c.y) / 2 - 0.3, 0)
    ).parameter.expression = f"{tenon_depth_expr} * {prefix}_dr"

    sk.name = f"{name}_Sk"
    prof = sp.smallest_profile(sk)

    # symmetric extrude along slot_axis for full span
    ext = sp.ext_new_sym(comp, prof, f"{slot_span_expr} / 2", name)
    wedge = ext.bodies.item(0)
    wedge.name = name

    if not skip_cut:
        sp.combine(comp, tenon_body, wedge, CUT, True, f"{name}_Cut")

    return wedge


def _intersect_trim(comp, wedge, tenon_body, name):
    """Trim a wedge to the tenon body via intersect.

    Keeps only the volume of *wedge* that overlaps *tenon_body*.
    The tenon body is unchanged (``isKeepToolBodies=True``).
    """
    comb_feats = comp.features.combineFeatures
    tool_coll = adsk.core.ObjectCollection.create()
    tool_coll.add(tenon_body)
    comb_input = comb_feats.createInput(wedge, tool_coll)
    comb_input.operation = \
        adsk.fusion.FeatureOperations.IntersectFeatureOperation
    comb_input.isKeepToolBodies = True
    feat = comb_feats.add(comb_input)
    feat.name = name
