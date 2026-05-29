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

    result = half_blind_dovetail.corner(
        pin_body=front_body, tail_body=side_body,
        plane=side_body.parentComponent.yZConstructionPlane,
        x_model=0, y_wide=0.25, y_narrow=0.75,
        y_wide_expr="0.25 in", socket_depth_expr="front_thick - 0.25 in",
        dist_expr="side_thick", name="HBD_FL", ev=ctx.ev,
    )

    result = half_blind_dovetail.box(comp, front, left,
        x_mid, y_mid,
        pin_thick_expr="front_thick", tail_thick_expr="side_thick",
        right=right, back=back,
        prefix="hbd", name="HBD", ev=ctx.ev,
        fl_plane=left_pl, front_expr="0 in")

Proportions & defaults
----------------------
Inherits all proportion rules from the through-dovetail template for
``{prefix}_angle``, ``{prefix}_tail_count``, and ``{prefix}_tail_w``.
Half-blind adds one more parameter:

**{prefix}_lap** — material remaining on the pin board's outer face:
  - Typical: 1/3 of pin board thickness. For 3/4" stock, 1/4" lap
    leaves 1/2" socket depth — a good default.
  - Minimum: 1/4" (0.25"). Thinner laps tend to blow out when glue
    swells the wood or when the joint is tapped home.
  - Maximum: 1/2 of pin thickness. More than half leaves insufficient
    socket depth for the tail to grip.
  - Design intent: the lap exists to HIDE the joint from the outer
    face. Keep it as thin as practical while staying above the
    blowout minimum.

Socket depth (derived): `socket_depth = pin_thick - lap`. The tail
penetrates this far into the pin board. Verify `socket_depth >
tail_w / 2` (roughly) so the tail has enough material around it for
mechanical grip.

Best for: drawer fronts, case tops — anywhere one face must look
clean. Not worth the effort for utility boxes; use through instead.
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


# Half-blind is the same trapezoid sketch as through, only with tail
# penetration set to ``socket_depth`` instead of full board thickness.
# Share the sketch so fixes propagate to both joint types.
from woodworking.templates._dovetail_common import (
    trapezoid_sketch as _trapezoid_sketch,
)


def define_params(params, prefix="hbd", angle="8 deg", tail_w="0.5 in",
                  tail_count="3", joint_h_expr="open_height",
                  pin_thick_expr="front_thick", lap="0.25 in",
                  pad="0 in"):
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
        pad: Edge padding — extra end-pin material beyond half a normal
            pin. Default "0 in" keeps the classic symmetric-half-pin
            layout. With pad > 0 the tail pattern packs into
            ``joint_h - 2*pad`` and edge pins grow to ``pad + pin_w/2``.

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
    params.add(f"{p}_pad", VI(pad), "in",
               "Edge padding — extra end-pin material beyond half a normal pin")

    # Derived — tail pattern fits in (joint_h - 2*pad)
    params.add(f"{p}_socket_depth",
               VI(f"{pin_thick_expr} - {p}_lap"),
               "in", "Socket depth (derived)")
    params.add(f"{p}_pin_w",
               VI(f"({joint_h_expr} - 2 * {p}_pad) / {p}_tail_count"
                  f" - {p}_tail_w"),
               "in", "Inner pin width (derived)")
    params.add(f"{p}_pitch",
               VI(f"({joint_h_expr} - 2 * {p}_pad) / {p}_tail_count"),
               "in", "Tail pitch (derived)")
    params.add(f"{p}_narrow_w",
               VI(f"{p}_tail_w - 2 * {p}_socket_depth * tan({p}_angle)"),
               "in", "Narrow face width (derived)")
    params.add(f"{p}_half_pin",
               VI(f"{p}_pin_w / 2"),
               "in", "Inner half-pin — edge pins are pad + half_pin (derived)")

    return {
        "angle": f"{p}_angle",
        "tail_w": f"{p}_tail_w",
        "tail_count": f"{p}_tail_count",
        "lap": f"{p}_lap",
        "pad": f"{p}_pad",
        "socket_depth": f"{p}_socket_depth",
        "pin_w": f"{p}_pin_w",
        "pitch": f"{p}_pitch",
        "narrow_w": f"{p}_narrow_w",
        "half_pin": f"{p}_half_pin",
    }


def corner(pin_body, tail_body, plane,
           x_model, y_wide, y_narrow,
           y_wide_expr, socket_depth_expr, dist_expr,
           name="HBD", prefix="hbd", ev=None,
           pattern_axis=None, z_base_expr=None, anchor=None):
    """Create a half-blind dovetail joint at one corner.

    Works for both same-component and cross-component cases. The sketch,
    JOIN extrude, and pattern always live in ``tail_body``'s component;
    the final CUT combine is routed intra-component or at root
    automatically by ``sp.combine``.

    Args:
        pin_body: Pin board body that receives the sockets.
        tail_body: Tail board body that receives the JOIN extrude.
        plane: Sketch plane in ``tail_body``'s component.
        x_model: Model X coordinate of the sketch plane position.
        y_wide: Model coordinate of the wide face at socket bottom.
        y_narrow: Model coordinate of the narrow face at socket opening.
        y_wide_expr: Parametric expression for the wide-face position.
        socket_depth_expr: Parametric expression for socket depth.
        dist_expr: Extrude distance expression.
        name: Feature name prefix.
        prefix: Parameter prefix (e.g. ``"hbd"``).
        ev: Evaluator function.
        pattern_axis: Construction axis for the tail pattern.
        z_base_expr: Expression for joint-axis offset of the first
            half-pin. Default: ``f"{prefix}_pin_w / 2"``.
        anchor: Optional ``trapezoid_sketch`` anchor dict — when provided the
            socket trapezoid is anchored to a PROJECTED parent face (deps
            rules 1-3) instead of the origin. Default None = origin mode
            (backward compatible). See ``_dovetail_common.trapezoid_sketch``.

    Returns:
        Dict with keys: ``join_feat``, ``pattern``, ``cut_combine``.
    """
    if ev is None:
        ev = sp._make_ev()

    p = prefix
    socket_depth = ev(socket_depth_expr)
    tw = ev(f"{p}_tail_w")
    delta = socket_depth * math.tan(ev(f"{p}_angle"))

    comp_tail = tail_body.parentComponent

    if z_base_expr is None:
        # Edge pin = pad + half_pin; first tail's joint-axis base = pad + half_pin
        z_base = ev(f"{p}_pad") + ev(f"{p}_half_pin")
        z_dim_expr = f"{p}_pad + {p}_pin_w / 2"
    else:
        z_base = ev(z_base_expr)
        z_dim_expr = z_base_expr

    m1_pt = Point3D.create(x_model, y_wide, z_base)
    m2_pt = Point3D.create(x_model, y_wide, z_base + tw)
    m3_pt = Point3D.create(x_model, y_narrow, z_base + tw - delta)
    m4_pt = Point3D.create(x_model, y_narrow, z_base + delta)

    prof = _trapezoid_sketch(
        comp_tail, plane,
        m1_pt, m2_pt, m3_pt, m4_pt,
        thick_expr=socket_depth_expr,
        short_joint_expr=(
            f"{z_dim_expr} + {socket_depth_expr} * tan({p}_angle)"),
        short_base_expr=f"({y_wide_expr}) + ({socket_depth_expr})",
        prefix=prefix, name=name, anchor=anchor)

    join_feat = sp.ext_op(comp_tail, prof, dist_expr, JOIN, tail_body,
                          f"{name}_Join")

    if pattern_axis is None:
        pattern_axis = comp_tail.zConstructionAxis

    pattern = sp.feat_pattern(comp_tail, join_feat, pattern_axis,
                              f"{p}_tail_count", f"{p}_pitch",
                              f"{name}_Pat")

    cut_combine = sp.combine(pin_body, tail_body, CUT, True,
                             f"{name}_Cut")

    return {
        "join_feat": join_feat,
        "pattern": pattern,
        "cut_combine": cut_combine,
    }


def box(comp, front, left,
        x_mid, y_mid,
        pin_thick_expr, tail_thick_expr,
        right=None, back=None,
        prefix="hbd", name="HBD", ev=None,
        fl_plane=None,
        front_expr="0 in",
        joint_axis="z", thick_axis="y",
        joint_base_expr=None, anchor=None):
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
        anchor: Optional ``trapezoid_sketch`` anchor dict — when provided the
            socket trapezoid is anchored to a PROJECTED parent face (deps
            rules 1-3) instead of the origin. Default None = origin mode
            (backward compatible). See ``_dovetail_common.trapezoid_sketch``.

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
    pad_val = ev(f"{p}_pad")
    if joint_base_expr is not None:
        j_base_val = ev(joint_base_expr)
        j_base = j_base_val + pad_val + hp
        j_expr = f"{joint_base_expr} + {p}_pad + {p}_pin_w / 2"
    else:
        j_base = pad_val + hp
        j_expr = f"{p}_pad + {p}_pin_w / 2"

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

    if front_expr == "0 in":
        wide_face_expr = f"{p}_lap"
    else:
        wide_face_expr = f"{front_expr} + {p}_lap"

    prof = _trapezoid_sketch(
        comp, fl_plane,
        _pt3(px, f_wide, j_base),
        _pt3(px, f_wide, j_base + tw),
        _pt3(px, f_narrow, j_base + tw - delta),
        _pt3(px, f_narrow, j_base + delta),
        thick_expr=f"{p}_socket_depth",
        short_joint_expr=f"{j_expr} + {p}_socket_depth * tan({p}_angle)",
        short_base_expr=f"({wide_face_expr}) + ({p}_socket_depth)",
        prefix=prefix, name=name, anchor=anchor)

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
