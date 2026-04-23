"""Half-blind dovetail joint template.

Creates half-blind dovetails where tails don't show on the pin board's
outer face. Used primarily for drawer fronts — the front board conceals
the joint from the outside.

Geometry:
    Pin board (front) is thicker. Tails enter from the inner face and
    extend inward by socket_depth = pin_thick - lap. The remaining
    material (lap) on the outer face stays clean.

    Wide face of tail: at socket bottom (toward outer face) — mechanical lock
    Narrow face of tail: at inner face of pin board (entry/opening)

Usage:
    from woodworking.templates import half_blind_dovetail

    half_blind_dovetail.define_params(params, prefix="hbd",
        angle="8 deg", tail_w="0.5 in", tail_count="3",
        joint_h_expr="box_h", pin_thick_expr="front_thick",
        lap="0.25 in")

    result = half_blind_dovetail.box(comp, front, left,
        x_mid, y_mid,
        pin_thick_expr="front_thick", tail_thick_expr="side_thick",
        right=right, back=back,
        prefix="hbd", name="HBD", ev=ctx.ev,
        fl_plane=left_pl, front_expr="0 in")
"""

import adsk.core
import adsk.fusion
import math

from helpers import sp

Point3D = adsk.core.Point3D
H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation

METADATA = {
    "name": "half_blind_dovetail",
    "category": "joinery",
    "description": "Tails hidden on one face — front board conceals joint",
    "best_for": ["drawer fronts", "case tops where one face must be clean"],
    "params": {
        "hbd_angle": "Dovetail angle (typically 7-14 deg)",
        "hbd_tail_w": "Tail width at wide face (inner face of pin board)",
        "hbd_tail_count": "Number of tails",
        "hbd_lap": "Material remaining on pin board outer face",
        "hbd_socket_depth": "Derived: pin_thick - lap",
        "hbd_pin_w": "Derived: joint_h / count - tail_w",
        "hbd_pitch": "Derived: joint_h / count",
        "hbd_narrow_w": "Derived: tail_w - 2 * socket_depth * tan(angle)",
        "hbd_half_pin": "Derived: pin_w / 2",
    },
}


def define_params(params, prefix="hbd", angle="8 deg", tail_w="0.5 in",
                  tail_count="3", joint_h_expr="open_height",
                  pin_thick_expr="front_thick", lap="0.25 in"):
    """Define all half-blind dovetail parameters.

    Args:
        params: design.userParameters
        prefix: Parameter name prefix.
        angle: Angle expression.
        tail_w: Tail width expression.
        tail_count: Number of tails expression.
        joint_h_expr: Expression for the joint height (board dimension
            along which tails are distributed).
        pin_thick_expr: Pin board thickness expression (thicker board).
        lap: Lap expression (material remaining on outer face).

    Returns:
        Dict of parameter names.
    """
    VI = adsk.core.ValueInput.createByString
    p = prefix

    # Independent
    params.add(f"{p}_angle", VI(angle), "deg", "Dovetail angle")
    params.add(f"{p}_tail_w", VI(tail_w), "in", "Tail width at wide face")
    params.add(f"{p}_tail_count", VI(tail_count), "", "Number of tails")
    params.add(f"{p}_lap", VI(lap), "in", "Lap (outer face material)")

    # Derived
    params.add(f"{p}_socket_depth",
               VI(f"{pin_thick_expr} - {p}_lap"),
               "in", "Socket depth (derived)")
    params.add(f"{p}_pin_w",
               VI(f"{joint_h_expr} / {p}_tail_count - {p}_tail_w"),
               "in", "Pin width (derived)")
    params.add(f"{p}_pitch",
               VI(f"{joint_h_expr} / {p}_tail_count"),
               "in", "Tail pitch (derived)")
    params.add(f"{p}_narrow_w",
               VI(f"{p}_tail_w - 2 * {p}_socket_depth * tan({p}_angle)"),
               "in", "Narrow face width (derived)")
    params.add(f"{p}_half_pin",
               VI(f"{p}_pin_w / 2"),
               "in", "Half-pin at edges (derived)")

    return {
        "angle": f"{p}_angle",
        "tail_w": f"{p}_tail_w",
        "tail_count": f"{p}_tail_count",
        "lap": f"{p}_lap",
        "socket_depth": f"{p}_socket_depth",
        "pin_w": f"{p}_pin_w",
        "pitch": f"{p}_pitch",
        "narrow_w": f"{p}_narrow_w",
        "half_pin": f"{p}_half_pin",
    }


def box(comp, front, left,
        x_mid, y_mid,
        pin_thick_expr, tail_thick_expr,
        right=None, back=None,
        prefix="hbd", name="HBD", ev=None,
        fl_plane=None,
        front_expr="0 in",
        joint_axis="z", thick_axis="y",
        joint_base_expr=None):
    """Create half-blind dovetails at box corners.

    Same mirror/pattern strategy as through dovetails, but the tail
    trapezoid is shallower (socket_depth instead of full pin thickness)
    and positioned at the inner face of the pin board.

    Args:
        comp: Component containing all boards.
        front: Front pin board body (thicker).
        left: Left tail board body (thinner, narrower).
        x_mid: Construction plane at tail board midpoint.
        y_mid: Construction plane at pin board midpoint.
        pin_thick_expr: Pin board thickness expression.
        tail_thick_expr: Tail board thickness expression (= extrude dist).
        right: Right tail board body. None for 1-corner.
        back: Back pin board body. None for no back dovetails.
        prefix: Parameter prefix (from define_params).
        name: Feature name prefix.
        ev: Evaluator function.
        fl_plane: Sketch plane at left board, perpendicular to ext_axis.
        front_expr: Expression for front board outer face on thick_axis.
        joint_axis: Model axis along which tails repeat.
        thick_axis: Model axis along which pin board thickness runs.
        joint_base_expr: Expression for joint-axis offset of first board edge.

    Returns:
        Dict with feature references.
    """
    if ev is None:
        ev = sp._make_ev()

    if fl_plane is None:
        fl_plane = comp.yZConstructionPlane

    p = prefix

    # Derive ext_axis
    ext_axis = ({"x", "y", "z"} - {joint_axis, thick_axis}).pop()
    _idx = {"x": 0, "y": 1, "z": 2}

    def _pt3(ext_v, thick_v, joint_v):
        c = [0.0, 0.0, 0.0]
        c[_idx[ext_axis]] = ext_v
        c[_idx[thick_axis]] = thick_v
        c[_idx[joint_axis]] = joint_v
        return Point3D.create(c[0], c[1], c[2])

    # Validate
    pin_w = ev(f"{p}_pin_w")
    if pin_w <= 0:
        n = int(ev(f"{p}_tail_count"))
        tw_in = ev(f"{p}_tail_w") / 2.54
        raise ValueError(
            f"Dovetails don't fit: {n} tails x {tw_in:.3f}in exceeds "
            f"joint height. Reduce {p}_tail_count or {p}_tail_w.")

    socket_depth = ev(f"{p}_socket_depth")
    hp = ev(f"{p}_half_pin")
    tw = ev(f"{p}_tail_w")
    delta = socket_depth * math.tan(ev(f"{p}_angle"))

    # Joint-axis base offset
    if joint_base_expr is not None:
        j_base_val = ev(joint_base_expr)
        j_base = j_base_val + hp
        j_expr = f"{joint_base_expr} + {p}_pin_w / 2"
    else:
        j_base = hp
        j_expr = f"{p}_pin_w / 2"

    # Wide face at SOCKET BOTTOM (toward outer face) — mechanical lock
    f_front = ev(front_expr) if front_expr != "0 in" else 0.0
    f_wide = f_front + ev(f"{p}_lap")
    # Narrow face at INNER face (entry/opening of socket)
    f_narrow = f_front + ev(pin_thick_expr)

    # ext_axis coordinate of sketch plane
    if hasattr(fl_plane, 'geometry'):
        px = getattr(fl_plane.geometry.origin, ext_axis)
    else:
        px = 0.0

    # Single trapezoid sketch
    sk = comp.sketches.add(fl_plane)
    sk.name = f"{name}_Sk"
    m = sk.modelToSketchSpace

    m1 = m(_pt3(px, f_wide, j_base))
    m2 = m(_pt3(px, f_wide, j_base + tw))
    m3 = m(_pt3(px, f_narrow, j_base + tw - delta))
    m4 = m(_pt3(px, f_narrow, j_base + delta))

    lines = sk.sketchCurves.sketchLines
    l1 = lines.addByTwoPoints(
        Point3D.create(m1.x, m1.y, 0), Point3D.create(m2.x, m2.y, 0))
    l2 = lines.addByTwoPoints(
        l1.endSketchPoint, Point3D.create(m3.x, m3.y, 0))
    l3 = lines.addByTwoPoints(
        l2.endSketchPoint, Point3D.create(m4.x, m4.y, 0))
    l4 = lines.addByTwoPoints(
        l3.endSketchPoint, l1.startSketchPoint)

    joint_h = abs(m2.x - m1.x) > abs(m2.y - m1.y)
    gc = sk.geometricConstraints
    if joint_h:
        gc.addHorizontal(l1); gc.addHorizontal(l3)
    else:
        gc.addVertical(l1); gc.addVertical(l3)

    JD = H if joint_h else V
    TD = V if joint_h else H
    d = sk.sketchDimensions

    # Dim 1: tail_w (wide side length along joint axis)
    d.addDistanceDimension(
        l1.startSketchPoint, l1.endSketchPoint,
        JD, Point3D.create(m1.x - 0.5, (m1.y + m2.y) / 2, 0)
    ).parameter.expression = f"{p}_tail_w"

    # Dim 2: narrow_w (narrow side length along joint axis)
    d.addDistanceDimension(
        l3.startSketchPoint, l3.endSketchPoint,
        JD, Point3D.create(m3.x + 0.5, (m3.y + m4.y) / 2, 0)
    ).parameter.expression = f"{p}_narrow_w"

    # Dim 3: socket_depth (trapezoid thickness across thick_axis)
    d.addDistanceDimension(
        l1.startSketchPoint, l4.startSketchPoint,
        TD, Point3D.create((m1.x + m4.x) / 2, m1.y - 0.5, 0)
    ).parameter.expression = f"{p}_socket_depth"

    # Dim 4: origin -> wide face start along joint axis
    d.addDistanceDimension(
        sk.originPoint, l1.startSketchPoint,
        JD, Point3D.create(m1.x - 1, m1.y / 2, 0)
    ).parameter.expression = j_expr

    # Dim 5: origin -> wide face along thick_axis = front + lap
    if front_expr == "0 in":
        wide_face_expr = f"{p}_lap"
    else:
        wide_face_expr = f"{front_expr} + {p}_lap"
    d.addDistanceDimension(
        sk.originPoint, l1.startSketchPoint,
        TD, Point3D.create(m1.x / 2, m1.y - 1, 0)
    ).parameter.expression = wide_face_expr

    # Dim 6: origin -> narrow face start along joint axis (angle offset)
    d.addDistanceDimension(
        sk.originPoint, l4.startSketchPoint,
        JD, Point3D.create(m4.x + 1, m4.y / 2, 0)
    ).parameter.expression = j_expr + f" + {p}_socket_depth * tan({p}_angle)"

    prof = sp.smallest_profile(sk)

    # ext_op JOIN into tail boards
    tail_boards = [left, right] if right is not None else [left]
    join_fl = sp.ext_op(comp, prof, tail_thick_expr, JOIN, tail_boards,
                        f"{name}_JoinFL")

    # Mirrors (same strategy as through dovetails)
    feats = [join_fl]
    if right is not None and back is not None:
        mir_bl = sp.mirror_feats(comp, [join_fl], y_mid, f"{name}_MirBL")
        mir_fr = sp.mirror_feats(comp, [join_fl], x_mid, f"{name}_MirFR")
        mir_br = sp.mirror_feats(comp, [mir_fr], y_mid, f"{name}_MirBR")
        feats = [join_fl, mir_bl, mir_fr, mir_br]
    elif right is not None:
        mir_fr = sp.mirror_feats(comp, [join_fl], x_mid, f"{name}_MirFR")
        feats = [join_fl, mir_fr]
    elif back is not None:
        mir_bl = sp.mirror_feats(comp, [join_fl], y_mid, f"{name}_MirBL")
        feats = [join_fl, mir_bl]

    # Pattern along joint_axis
    _axis_map = {
        "x": comp.xConstructionAxis,
        "y": comp.yConstructionAxis,
        "z": comp.zConstructionAxis,
    }
    VI = adsk.core.ValueInput.createByString
    coll = adsk.core.ObjectCollection.create()
    for f in feats:
        coll.add(f)
    inp = comp.features.rectangularPatternFeatures.createInput(
        coll, _axis_map[joint_axis],
        VI(f"{p}_tail_count"), VI(f"{p}_pitch"),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    inp.quantityTwo = VI("1")
    pat = comp.features.rectangularPatternFeatures.add(inp)
    pat.name = f"{name}_Pat"

    # CUT pin boards using tail boards as tools
    cut_front = sp.combine(front, tail_boards, CUT, True,
                           f"{name}_CutFront")
    cut_back = None
    if back is not None:
        cut_back = sp.combine(back, tail_boards, CUT, True,
                              f"{name}_CutBack")

    return {
        "join_fl": join_fl, "pattern": pat,
        "cut_front": cut_front, "cut_back": cut_back,
    }
