import adsk.core
import adsk.fusion
import math

from ._util import _make_ev
from .sketch import probe_sketch_axes

Point3D = adsk.core.Point3D
H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation


def sketch_slot(comp, plane, cx_expr, cy_expr, long_expr, short_expr,
                vertical, name="Sk", ev=None):
    """Stadium-shaped sketch on a construction plane (2 arcs + 2 lines).

    All dimensions are parametric. The long axis runs along sketch V when
    vertical=True, sketch H when False.

    Args:
        comp: Component to create sketch in.
        plane: Construction plane or BRepFace.
        cx_expr, cy_expr: Center position in sketch-space (parameter expressions).
        long_expr: Long dimension expression (e.g. "dm_l").
        short_expr: Short dimension expression (e.g. "dm_w").
        vertical: True → long axis along sketch Y; False → along sketch X.
        name: Sketch name.
        ev: Evaluator function. If None, creates one from active design.

    Returns:
        (sketch, profile)
    """
    if ev is None:
        ev = _make_ev()

    sk = comp.sketches.add(plane)
    sk.name = name
    slines = sk.sketchCurves.sketchLines
    sarcs = sk.sketchCurves.sketchArcs
    cx, cy = ev(cx_expr), ev(cy_expr)
    lg, sh = ev(long_expr), ev(short_expr)
    r = sh / 2
    hl = (lg - sh) / 2

    if vertical:
        br = Point3D.create(cx + r, cy - hl, 0)
        tr = Point3D.create(cx + r, cy + hl, 0)
        tc = Point3D.create(cx, cy + hl, 0)
        tl = Point3D.create(cx - r, cy + hl, 0)
        bl = Point3D.create(cx - r, cy - hl, 0)
        bc = Point3D.create(cx, cy - hl, 0)
        l_r = slines.addByTwoPoints(br, tr)
        a_t = sarcs.addByCenterStartSweep(tc, tr, math.pi)
        l_l = slines.addByTwoPoints(tl, bl)
        a_b = sarcs.addByCenterStartSweep(bc, bl, math.pi)
        sk.geometricConstraints.addVertical(l_r)
        sk.geometricConstraints.addVertical(l_l)
        sk.geometricConstraints.addTangent(l_r, a_t)
        sk.geometricConstraints.addTangent(a_t, l_l)
        sk.geometricConstraints.addTangent(l_l, a_b)
        sk.geometricConstraints.addTangent(a_b, l_r)
        d = sk.sketchDimensions
        d.addRadialDimension(a_b,
            Point3D.create(cx + r + 1, cy - hl, 0)
        ).parameter.expression = short_expr + " / 2"
        d.addDistanceDimension(
            a_b.centerSketchPoint, a_t.centerSketchPoint,
            V, Point3D.create(cx + r + 2, cy, 0)
        ).parameter.expression = long_expr + " - " + short_expr
        d.addDistanceDimension(
            sk.originPoint, a_b.centerSketchPoint,
            H, Point3D.create(cx / 2, cy - hl - 1, 0)
        ).parameter.expression = cx_expr
        d.addDistanceDimension(
            sk.originPoint, a_b.centerSketchPoint,
            V, Point3D.create(cx - r - 1, (cy - hl) / 2, 0)
        ).parameter.expression = cy_expr + " - (" + long_expr + " - " + short_expr + ") / 2"
    else:
        bsl = Point3D.create(cx - hl, cy - r, 0)
        bsr = Point3D.create(cx + hl, cy - r, 0)
        rc = Point3D.create(cx + hl, cy, 0)
        tsr = Point3D.create(cx + hl, cy + r, 0)
        tsl = Point3D.create(cx - hl, cy + r, 0)
        lc = Point3D.create(cx - hl, cy, 0)
        l_b = slines.addByTwoPoints(bsl, bsr)
        a_r = sarcs.addByCenterStartSweep(rc, bsr, math.pi)
        l_t = slines.addByTwoPoints(tsr, tsl)
        a_l = sarcs.addByCenterStartSweep(lc, tsl, math.pi)
        sk.geometricConstraints.addHorizontal(l_b)
        sk.geometricConstraints.addHorizontal(l_t)
        sk.geometricConstraints.addTangent(l_b, a_r)
        sk.geometricConstraints.addTangent(a_r, l_t)
        sk.geometricConstraints.addTangent(l_t, a_l)
        sk.geometricConstraints.addTangent(a_l, l_b)
        d = sk.sketchDimensions
        d.addRadialDimension(a_l,
            Point3D.create(cx - hl - 1, cy + r + 1, 0)
        ).parameter.expression = short_expr + " / 2"
        d.addDistanceDimension(
            a_l.centerSketchPoint, a_r.centerSketchPoint,
            H, Point3D.create(cx, cy - r - 2, 0)
        ).parameter.expression = long_expr + " - " + short_expr
        d.addDistanceDimension(
            sk.originPoint, a_l.centerSketchPoint,
            H, Point3D.create((cx - hl) / 2, cy - r - 1, 0)
        ).parameter.expression = cx_expr + " - (" + long_expr + " - " + short_expr + ") / 2"
        d.addDistanceDimension(
            sk.originPoint, a_l.centerSketchPoint,
            V, Point3D.create(cx - hl - 2, cy / 2, 0)
        ).parameter.expression = cy_expr
    return sk, sk.profiles.item(0)


def probe_sketch_signs(sk):
    """Return (h_axis, v_axis, h_sign, v_sign) for a sketch.

    Extends probe_sketch_axes with sign detection: h/v_sign is +1 if
    increasing model coordinate → increasing sketch coordinate, else -1.
    Use the sign when building offset expressions on non-XY planes.
    """
    h_axis, v_axis = probe_sketch_axes(sk)
    sc = sk.modelToSketchSpace(Point3D.create(0, 0, 0))
    delta = {
        "x": Point3D.create(1, 0, 0),
        "y": Point3D.create(0, 1, 0),
        "z": Point3D.create(0, 0, 1),
    }
    sd_h = sk.modelToSketchSpace(delta[h_axis])
    sd_v = sk.modelToSketchSpace(delta[v_axis])
    h_sign = 1 if (sd_h.x - sc.x) > 0 else -1
    v_sign = 1 if (sd_v.y - sc.y) > 0 else -1
    return h_axis, v_axis, h_sign, v_sign


def sketch_slot_model(comp, plane, model_center, long_model_axis,
                      long_expr, short_expr, name="Sk", ev=None):
    """Stadium-shaped sketch positioned in model coordinates.

    Handles axis flips on non-XY planes automatically via sign detection.
    Use this instead of sketch_slot when working in model-space coordinates.

    Args:
        comp: Component to create sketch in.
        plane: Construction plane or BRepFace (can be non-XY).
        model_center: (x_expr, y_expr, z_expr) — center in model-space expressions.
        long_model_axis: 'x', 'y', or 'z' — which model axis the long dim runs along.
        long_expr: Long dimension expression.
        short_expr: Short dimension expression.
        name: Sketch name.
        ev: Evaluator function. If None, creates one from active design.

    Returns:
        (sketch, profile)
    """
    if ev is None:
        ev = _make_ev()

    sk = comp.sketches.add(plane)
    sk.name = name
    h_axis, v_axis = probe_sketch_axes(sk)

    mcx = ev(model_center[0])
    mcy = ev(model_center[1])
    mcz = ev(model_center[2])
    sc = sk.modelToSketchSpace(Point3D.create(mcx, mcy, mcz))
    cx, cy = sc.x, sc.y

    vertical = (long_model_axis == v_axis)

    axis_expr = {
        "x": model_center[0], "y": model_center[1], "z": model_center[2]
    }
    h_expr = axis_expr[h_axis]
    v_expr = axis_expr[v_axis]

    lg, sh = ev(long_expr), ev(short_expr)
    r = sh / 2
    hl = (lg - sh) / 2
    slines = sk.sketchCurves.sketchLines
    sarcs = sk.sketchCurves.sketchArcs

    delta_pt = {
        "x": Point3D.create(mcx + 1, mcy, mcz),
        "y": Point3D.create(mcx, mcy + 1, mcz),
        "z": Point3D.create(mcx, mcy, mcz + 1),
    }
    sd_h = sk.modelToSketchSpace(delta_pt[h_axis])
    sd_v = sk.modelToSketchSpace(delta_pt[v_axis])
    h_sign = 1 if (sd_h.x - sc.x) > 0 else -1
    v_sign = 1 if (sd_v.y - sc.y) > 0 else -1

    half_str = "(" + long_expr + " - " + short_expr + ") / 2"
    v_bot_op = " - " if v_sign > 0 else " + "
    h_left_op = " - " if h_sign > 0 else " + "

    if vertical:
        br = Point3D.create(cx + r, cy - hl, 0)
        tr = Point3D.create(cx + r, cy + hl, 0)
        tc = Point3D.create(cx, cy + hl, 0)
        tl = Point3D.create(cx - r, cy + hl, 0)
        bl = Point3D.create(cx - r, cy - hl, 0)
        bc = Point3D.create(cx, cy - hl, 0)
        l_r = slines.addByTwoPoints(br, tr)
        a_t = sarcs.addByCenterStartSweep(tc, tr, math.pi)
        l_l = slines.addByTwoPoints(tl, bl)
        a_b = sarcs.addByCenterStartSweep(bc, bl, math.pi)
        sk.geometricConstraints.addVertical(l_r)
        sk.geometricConstraints.addVertical(l_l)
        sk.geometricConstraints.addTangent(l_r, a_t)
        sk.geometricConstraints.addTangent(a_t, l_l)
        sk.geometricConstraints.addTangent(l_l, a_b)
        sk.geometricConstraints.addTangent(a_b, l_r)
        d = sk.sketchDimensions
        d.addRadialDimension(a_b,
            Point3D.create(cx + r + 1, cy - hl, 0)
        ).parameter.expression = short_expr + " / 2"
        d.addDistanceDimension(
            a_b.centerSketchPoint, a_t.centerSketchPoint,
            V, Point3D.create(cx + r + 2, cy, 0)
        ).parameter.expression = long_expr + " - " + short_expr
        d.addDistanceDimension(
            sk.originPoint, a_b.centerSketchPoint,
            H, Point3D.create(cx / 2, cy - hl - 1, 0)
        ).parameter.expression = h_expr
        d.addDistanceDimension(
            sk.originPoint, a_b.centerSketchPoint,
            V, Point3D.create(cx - r - 1, (cy - hl) / 2, 0)
        ).parameter.expression = v_expr + v_bot_op + half_str
    else:
        bsl = Point3D.create(cx - hl, cy - r, 0)
        bsr = Point3D.create(cx + hl, cy - r, 0)
        rc = Point3D.create(cx + hl, cy, 0)
        tsr = Point3D.create(cx + hl, cy + r, 0)
        tsl = Point3D.create(cx - hl, cy + r, 0)
        lc = Point3D.create(cx - hl, cy, 0)
        l_b = slines.addByTwoPoints(bsl, bsr)
        a_r = sarcs.addByCenterStartSweep(rc, bsr, math.pi)
        l_t = slines.addByTwoPoints(tsr, tsl)
        a_l = sarcs.addByCenterStartSweep(lc, tsl, math.pi)
        sk.geometricConstraints.addHorizontal(l_b)
        sk.geometricConstraints.addHorizontal(l_t)
        sk.geometricConstraints.addTangent(l_b, a_r)
        sk.geometricConstraints.addTangent(a_r, l_t)
        sk.geometricConstraints.addTangent(l_t, a_l)
        sk.geometricConstraints.addTangent(a_l, l_b)
        d = sk.sketchDimensions
        d.addRadialDimension(a_l,
            Point3D.create(cx - hl - 1, cy + r + 1, 0)
        ).parameter.expression = short_expr + " / 2"
        d.addDistanceDimension(
            a_l.centerSketchPoint, a_r.centerSketchPoint,
            H, Point3D.create(cx, cy - r - 2, 0)
        ).parameter.expression = long_expr + " - " + short_expr
        d.addDistanceDimension(
            sk.originPoint, a_l.centerSketchPoint,
            H, Point3D.create((cx - hl) / 2, cy - r - 1, 0)
        ).parameter.expression = h_expr + h_left_op + half_str
        d.addDistanceDimension(
            sk.originPoint, a_l.centerSketchPoint,
            V, Point3D.create(cx - hl - 2, cy / 2, 0)
        ).parameter.expression = v_expr
    return sk, sk.profiles.item(0)
