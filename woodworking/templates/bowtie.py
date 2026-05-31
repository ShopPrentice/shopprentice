"""Bowtie (butterfly key) inlay template.

Creates decorative bowtie/butterfly key inlays that span cracks or
edge-glue joints. The bowtie is an hourglass-shaped body that CUTs
into the target surface, creating a pocket for a contrasting wood
inlay.

Orientation rule: bowties are always perpendicular to the crack /
joint direction. The long axis crosses the crack, the waist sits on
the crack line. The bowtie lies FLAT on the visible surface and
extrudes (as a CUT) into the wood.

The template is orientation-agnostic — specify both in-plane axes
via ``long_axis`` (the hourglass's long dimension) and ``short_axis``
(the waist direction). The sketch plane must contain both axes; the
extrude is in the plane's normal direction.

Usage:
    from woodworking.templates import bowtie

    # Nakashima-style headboard — vertical slab, crack running in X,
    # bowtie long axis in Z (vertical), extruding in -Y into the slab
    bowtie.single(comp, slab.xZConstructionPlane,
                  center=("mid_x", "0 in", "mid_z"),
                  long_axis="z", short_axis="x",
                  length="bt_len", end_w="bt_end_w",
                  waist_w="bt_waist_w", depth="bt_depth",
                  slab_body=slab, name="BT_1", ev=ev)

    # Horizontal tabletop, crack along X, bowtie long axis in Y
    bowtie.single(comp, top_pl,
                  center=("mid_x", "mid_y", "top_z"),
                  long_axis="y", short_axis="x",
                  length=..., end_w=..., waist_w=..., depth=...,
                  slab_body=top, name="BT_Top", ev=ev)

    # Two boards edge-joined along X — bowtie bridges the joint,
    # long axis Y (crosses the X joint line)
    bowtie.single(comp, top_pl, center=("mid_x", "joint_y", "top_z"),
                  long_axis="y", short_axis="x", ...)
"""

import adsk.core
import adsk.fusion
import math

from helpers import sp

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation

METADATA = {
    "name": "bowtie",
    "category": "decorative_joinery",
    "description": "Butterfly key / bowtie inlay for stabilizing cracks in live edge slabs",
    "best_for": ["live edge slab cracks", "decorative inlays", "tabletop crack repair"],
    "not_for": ["structural joints", "hidden joinery"],
    "sizing_guide": {
        "small":  {"length": "2 in",   "end_w": "1 in",   "waist_w": "0.375 in", "depth": "0.5 in"},
        "medium": {"length": "3 in",   "end_w": "1.5 in", "waist_w": "0.5 in",   "depth": "0.67 in"},
        "large":  {"length": "4 in",   "end_w": "2 in",   "waist_w": "0.75 in",  "depth": "0.75 in"},
    },
    "rules": {
        "depth": "1/3 to 1/2 of slab thickness",
        "spacing": "one near each end of crack, others every 5-8 inches",
        "orientation": "perpendicular to crack (= perpendicular to grain)",
    },
}


_UNIT = {
    "x": (1.0, 0.0, 0.0),
    "y": (0.0, 1.0, 0.0),
    "z": (0.0, 0.0, 1.0),
}


def _bowtie_points_3d(center, long_axis, short_axis,
                       half_l, half_ew, half_ww):
    """Return 6 model-space Point3Ds for an hourglass bowtie.

    Args:
        center: (cx, cy, cz) model-space center, cm floats.
        long_axis: "x", "y", or "z" — model axis aligned with the
            bowtie's long dimension.
        short_axis: "x", "y", or "z" — model axis aligned with the
            bowtie's short (waist) dimension. Must differ from
            long_axis; together they define the 2D bowtie plane.
        half_l: half the long length.
        half_ew: half-width at the wide ends (spread).
        half_ww: half-width at the waist (narrow middle).

    The 6 corners traverse the hourglass in order:
        (+L, -S)  wide end A, short-negative side
        (+L, +S)  wide end A, short-positive side
        ( 0, +S)  waist on the short-positive side
        (-L, +S)  wide end B, short-positive side
        (-L, -S)  wide end B, short-negative side
        ( 0, -S)  waist on the short-negative side
    so two lines go straight across each wide end and the waist
    corners define the hourglass pinch.
    """
    if long_axis == short_axis:
        raise ValueError(
            f"long_axis and short_axis must differ, got {long_axis!r}")

    P3 = adsk.core.Point3D
    cx, cy, cz = center
    la = _UNIT[long_axis]
    sa = _UNIT[short_axis]

    def pt(l, s):
        return P3.create(cx + la[0] * l + sa[0] * s,
                         cy + la[1] * l + sa[1] * s,
                         cz + la[2] * l + sa[2] * s)

    return [
        pt( half_l, -half_ew),
        pt( half_l,  half_ew),
        pt(      0,  half_ww),
        pt(-half_l,  half_ew),
        pt(-half_l, -half_ew),
        pt(      0, -half_ww),
    ]


def single(comp, plane, center, long_axis, short_axis,
           length, end_w, waist_w, depth, slab_body,
           name="BT", ev=None, cut=True, anchor=None):
    """Create a single bowtie inlay on a slab.

    Args:
        comp: Component to create features in.
        plane: Construction plane or BRepFace for the sketch. The
            bowtie sketch lies in this plane and extrudes in its
            normal direction.
        center: (x_expr, y_expr, z_expr) — model-space center of the
            bowtie (on the sketch plane).
        long_axis: "x", "y", or "z" — model axis aligned with the
            bowtie's long dimension. Crosses the crack / joint.
        short_axis: "x", "y", or "z" — model axis aligned with the
            bowtie's waist dimension. Along the crack / joint. Must
            differ from long_axis and must lie in ``plane``.
        length: Expression for bowtie length (long dimension).
        end_w: Expression for width at the wide ends (short direction).
        waist_w: Expression for width at the narrow waist.
        depth: Expression for inlay depth (into slab, plane's normal).
        slab_body: The slab body to CUT into (or assembly proxy).
        name: Feature name prefix.
        ev: Parameter evaluator function.
        cut: If True, CUT the bowtie into the slab. If False, just
            create the body.
        anchor: Optional dict for NON-root slab components — retargets the
            two origin position dims (which locate the +long/-short wide-end
            corner) to a projected parent-face corner via ``sp.reanchor``.
            Keys: parent_body, parent_occ, face_axis, face_dir, anchor_xyz.
            Default None keeps origin mode (backward compatible). The hourglass
            is ALWAYS fully constrained (H/V on the wide-end lines + 10 dims).

    Returns:
        The bowtie body.
    """
    if ev is None:
        design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
        ev = lambda e: (design.userParameters.itemByName(e).value
                        if design.userParameters.itemByName(e)
                        else design.unitsManager.evaluateExpression(e, "cm"))

    # Evaluate center and dimensions
    cx = ev(center[0]) if isinstance(center[0], str) else center[0]
    cy = ev(center[1]) if isinstance(center[1], str) else center[1]
    cz = ev(center[2]) if isinstance(center[2], str) else center[2]
    half_l = ev(length) / 2
    half_ew = ev(end_w) / 2
    half_ww = ev(waist_w) / 2

    Point3D = adsk.core.Point3D

    def _s(v):
        return v if isinstance(v, str) else f"{v} cm"
    len_e, ew_e, ww_e = _s(length), _s(end_w), _s(waist_w)
    idx = {"x": 0, "y": 1, "z": 2}
    c_long, c_short = _s(center[idx[long_axis]]), _s(center[idx[short_axis]])

    # 6 corners in model space, oriented by long_axis + short_axis
    model_pts = _bowtie_points_3d((cx, cy, cz), long_axis, short_axis,
                                   half_l, half_ew, half_ww)

    sk = comp.sketches.add(plane)
    sk.name = f"{name}_Sk"
    m2s = sk.modelToSketchSpace
    pts = [m2s(p) for p in model_pts]

    lines = sk.sketchCurves.sketchLines
    # Explicit handles: l0 p0->p1 (wide end A), l1 p1->p2, l2 p2->p3,
    # l3 p3->p4 (wide end B), l4 p4->p5, l5 p5->p0.
    l0 = lines.addByTwoPoints(pts[0], pts[1])
    l1 = lines.addByTwoPoints(l0.endSketchPoint, pts[2])
    l2 = lines.addByTwoPoints(l1.endSketchPoint, pts[3])
    l3 = lines.addByTwoPoints(l2.endSketchPoint, pts[4])
    l4 = lines.addByTwoPoints(l3.endSketchPoint, pts[5])
    lines.addByTwoPoints(l4.endSketchPoint, l0.startSketchPoint)

    # --- Fully constrain the hourglass (12 DOF) ---
    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
    h_axis, v_axis = sp.probe_sketch_axes(sk)
    LONG_DIM = H if long_axis == h_axis else V
    SHORT_DIM = H if short_axis == h_axis else V
    gc = sk.geometricConstraints
    # Wide-end lines (l0, l3) are perpendicular to the long axis.
    if long_axis == h_axis:
        gc.addVertical(l0); gc.addVertical(l3)
    else:
        gc.addHorizontal(l0); gc.addHorizontal(l3)
    d = sk.sketchDimensions
    p0, p1 = l0.startSketchPoint, l0.endSketchPoint
    p3, p4 = l3.startSketchPoint, l3.endSketchPoint
    p2, p5 = l1.endSketchPoint, l4.endSketchPoint
    tp = lambda a, b: Point3D.create((a.geometry.x + b.geometry.x) / 2 + 0.3,
                                     (a.geometry.y + b.geometry.y) / 2 + 0.3, 0)
    # End widths (both wide faces) + length + symmetry of far end via p1->p4.
    d.addDistanceDimension(p0, p1, SHORT_DIM, tp(p0, p1)).parameter.expression = ew_e
    d.addDistanceDimension(p3, p4, SHORT_DIM, tp(p3, p4)).parameter.expression = ew_e
    d.addDistanceDimension(p1, p4, LONG_DIM, tp(p1, p4)).parameter.expression = len_e
    d.addDistanceDimension(p1, p4, SHORT_DIM, tp(p1, p4)).parameter.expression = ew_e
    # Waist points p2 (+short) and p5 (-short), located from p0.
    d.addDistanceDimension(p0, p2, LONG_DIM, tp(p0, p2)
        ).parameter.expression = f"({len_e}) / 2"
    d.addDistanceDimension(p0, p2, SHORT_DIM, tp(p0, p2)
        ).parameter.expression = f"(({ew_e}) + ({ww_e})) / 2"
    d.addDistanceDimension(p0, p5, LONG_DIM, tp(p0, p5)
        ).parameter.expression = f"({len_e}) / 2"
    d.addDistanceDimension(p0, p5, SHORT_DIM, tp(p0, p5)
        ).parameter.expression = f"(({ew_e}) - ({ww_e})) / 2"
    # p0 position: 2 origin dims (retargeted to a parent corner when anchored).
    d.addDistanceDimension(sk.originPoint, p0, LONG_DIM,
        Point3D.create(p0.geometry.x / 2, p0.geometry.y - 1, 0)
        ).parameter.expression = f"abs(({c_long}) + ({len_e}) / 2)"
    d.addDistanceDimension(sk.originPoint, p0, SHORT_DIM,
        Point3D.create(p0.geometry.x - 1, p0.geometry.y / 2, 0)
        ).parameter.expression = f"abs(({c_short}) - ({ew_e}) / 2)"
    if anchor is not None:
        sp.reanchor(sk, anchor["parent_body"], anchor.get("parent_occ"),
                    anchor["face_axis"], anchor["face_dir"],
                    anchor["anchor_xyz"])

    prof = sk.profiles.item(0)
    VI = adsk.core.ValueInput.createByString

    ext_inp = comp.features.extrudeFeatures.createInput(
        prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ext_inp.setDistanceExtent(False, VI(depth))
    ext = comp.features.extrudeFeatures.add(ext_inp)
    ext.name = name
    bt_body = ext.bodies.item(0)
    bt_body.name = name

    if cut and slab_body:
        # combine routes intra- or cross-component automatically.
        sp.combine(slab_body, [bt_body], CUT, True, f"{name}_Cut")

    sk.isVisible = False
    return bt_body


def row(comp, plane, crack_axis, crack_center, count, spacing,
        long_axis, short_axis, length, end_w, waist_w, depth,
        slab_body, name="BT", ev=None, anchor=None):
    """Create a row of bowties along a crack / joint line.

    Args:
        comp: Component.
        plane: Construction plane for sketches.
        crack_axis: "x", "y", or "z" — direction the crack/joint runs.
            Bowties step along this axis. Typically == short_axis
            (the waist direction runs along the crack).
        crack_center: (x_expr, y_expr, z_expr) — center of the row on
            the crack line.
        count: Number of bowties (int or expression string).
        spacing: Expression for center-to-center spacing along
            crack_axis.
        long_axis: "x", "y", or "z" — bowtie's long dimension (crosses
            the crack).
        short_axis: "x", "y", or "z" — bowtie's waist dimension
            (should be == crack_axis).
        length, end_w, waist_w, depth: Dimension expressions.
        slab_body: Slab body to CUT into.
        name: Name prefix.
        ev: Parameter evaluator.
        anchor: Optional dict forwarded to every ``single()`` — anchors each
            bowtie's origin position dims to a projected parent-face corner
            (for non-root slab components). Default None keeps origin mode.

    Returns:
        List of bowtie bodies.
    """
    if ev is None:
        design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
        ev = lambda e: (design.userParameters.itemByName(e).value
                        if design.userParameters.itemByName(e)
                        else design.unitsManager.evaluateExpression(e, "cm"))

    n = int(ev(count)) if isinstance(count, str) else int(count)
    sp_cm = ev(spacing) if isinstance(spacing, str) else spacing

    # Crack center
    cc = [ev(c) if isinstance(c, str) else c for c in crack_center]
    axis_idx = {"x": 0, "y": 1, "z": 2}
    ax = axis_idx[crack_axis]

    bodies = []
    for i in range(n):
        offset = (i - (n - 1) / 2) * sp_cm
        center = list(cc)
        center[ax] += offset

        bt = single(comp, plane, tuple(center),
                     long_axis, short_axis,
                     length, end_w, waist_w, depth,
                     slab_body, f"{name}_{i+1}", ev, anchor=anchor)
        bodies.append(bt)

    return bodies
