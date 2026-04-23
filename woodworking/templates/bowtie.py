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
           name="BT", ev=None, cut=True):
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

    # 6 corners in model space, oriented by long_axis + short_axis
    model_pts = _bowtie_points_3d((cx, cy, cz), long_axis, short_axis,
                                   half_l, half_ew, half_ww)

    sk = comp.sketches.add(plane)
    sk.name = f"{name}_Sk"
    m2s = sk.modelToSketchSpace
    pts = [m2s(p) for p in model_pts]

    lines = sk.sketchCurves.sketchLines
    prev = lines.addByTwoPoints(pts[0], pts[1])
    for j in range(2, len(pts)):
        prev = lines.addByTwoPoints(prev.endSketchPoint, pts[j])
    lines.addByTwoPoints(prev.endSketchPoint,
                          sk.sketchCurves.sketchLines.item(0).startSketchPoint)

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
        slab_body, name="BT", ev=None):
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
                     slab_body, f"{name}_{i+1}", ev)
        bodies.append(bt)

    return bodies
