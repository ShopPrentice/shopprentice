"""Finger joint (box joint) template.

Creates interlocking rectangular fingers at box corners. Both boards have
the same finger width — the joint distributes fingers evenly along the
joint edge, starting with a full finger at the bottom.

Simpler than dovetails: rectangular profile, no angle, same width on
both boards. Fingers are typically narrow (width < board thickness).

Three entry points:
  - define_params(): create parametric finger joint dimensions
  - box(): create finger joints at 1, 2, or 4 corners of a box
  - corner(): create a single finger joint at one corner (lower-level)

Usage:
    from helpers.templates import finger_joint

    # Define parameters
    fp = finger_joint.define_params(params, prefix="fj",
        finger_w="0.375 in", finger_count="8",
        joint_h_expr="box_height", thick_expr="board_thick")

    # 4-corner box
    finger_joint.box(comp, front, left,
                     x_mid, y_mid, thick_expr="board_thick",
                     right=right, back=back,
                     prefix="fj", name="FJ", ev=ctx.ev)
"""

import adsk.core
import adsk.fusion

from helpers import af

Point3D = adsk.core.Point3D
H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation

METADATA = {
    "name": "finger_joint",
    "category": "joinery",
    "description": "Interlocking rectangular fingers for strong right-angle joints",
    "best_for": ["boxes", "drawers", "decorative corners",
                 "any right-angle joint where visible end grain is acceptable"],
    "not_for": ["drawer fronts (shows end grain on both boards)"],
    "params": {
        "fj_finger_w": "Width of each finger (same on both boards)",
        "fj_count": "Number of fingers on the finger board",
        "fj_pitch": "Derived: 2 * finger_w (spacing between same-board fingers)",
    },
}


def define_params(params, prefix="fj", finger_w="0.375 in",
                  finger_count="8", joint_h_expr="open_height",
                  thick_expr="board_thick"):
    """Define finger joint parameters.

    No angle — fingers are rectangular. The count represents how many
    fingers the "finger board" (left/right) gets. The slot board
    (front/back) gets interlocking fingers automatically via CUT.

    Typical sizing: finger_w < board_thick (narrow fingers).

    Args:
        params: design.userParameters
        prefix: Parameter name prefix (e.g. "fj").
        finger_w: Finger width expression.
        finger_count: Number of fingers on finger board.
        joint_h_expr: Joint height expression (board dimension along joint).
        thick_expr: Board thickness expression.

    Returns:
        Dict of parameter names.
    """
    VI = adsk.core.ValueInput.createByString
    p = prefix

    # Independent params
    params.add(f"{p}_finger_w", VI(finger_w), "in", "Finger width")
    params.add(f"{p}_count", VI(finger_count), "", "Number of fingers")

    # Derived
    params.add(f"{p}_pitch",
               VI(f"2 * {p}_finger_w"),
               "in", "Finger pitch (derived)")

    return {
        "finger_w": f"{p}_finger_w",
        "count": f"{p}_count",
        "pitch": f"{p}_pitch",
    }


def corner(comp, plane, thick_expr, dist_expr,
           pin_body, finger_body, name="FJ",
           prefix="fj", ev=None,
           pattern_axis=None, joint_base_expr=None,
           x_model=0.0, y_wide=0.0, y_wide_expr="0 in"):
    """Create a finger joint at one corner.

    Sketches a single rectangular finger, extrudes CUT into the pin board
    and JOIN into the finger board, then feature-patterns both along
    the joint axis.

    Args:
        comp: Component to create features in.
        plane: Construction plane at the corner.
        thick_expr: Board thickness expression (= extrude distance).
        dist_expr: Extrude distance expression (typically = thick_expr).
        pin_body: Pin/slot board body (receives CUT sockets).
        finger_body: Finger board body (fingers JOIN into this).
        name: Feature name prefix (e.g. "FJ_FL").
        prefix: Parameter prefix (e.g. "fj").
        ev: Evaluator function.
        pattern_axis: Construction axis for pattern direction.
            If None, uses comp.zConstructionAxis.
        joint_base_expr: Expression for joint-axis offset of first finger.
            If None, starts at 0.
        x_model: Model coordinate of the sketch plane position on ext_axis.
        y_wide: Model coordinate of the outer face on thick_axis.
        y_wide_expr: Parametric expression for outer face position.

    Returns:
        Dict with keys: 'cut_feat', 'join_feat', 'cut_pattern',
        'join_pattern', 'pin_cut'.
    """
    if ev is None:
        ev = af._make_ev()

    p = prefix
    bt = ev(thick_expr)
    fw = ev(f"{p}_finger_w")

    sk = comp.sketches.add(plane)
    sk.name = f"{name}_Sk"
    m = sk.modelToSketchSpace

    # Joint-axis base offset
    if joint_base_expr is not None:
        j_base = ev(joint_base_expr)
        j_expr = joint_base_expr
    else:
        j_base = 0.0
        j_expr = "0 in"

    # 4 corners of the rectangle in model space
    m1 = m(Point3D.create(x_model, y_wide, j_base))
    m2 = m(Point3D.create(x_model, y_wide, j_base + fw))
    m3 = m(Point3D.create(x_model, y_wide + bt, j_base + fw))
    m4 = m(Point3D.create(x_model, y_wide + bt, j_base))

    lines = sk.sketchCurves.sketchLines
    l1 = lines.addByTwoPoints(
        Point3D.create(m1.x, m1.y, 0), Point3D.create(m2.x, m2.y, 0))
    l2 = lines.addByTwoPoints(
        l1.endSketchPoint, Point3D.create(m3.x, m3.y, 0))
    l3 = lines.addByTwoPoints(
        l2.endSketchPoint, Point3D.create(m4.x, m4.y, 0))
    l4 = lines.addByTwoPoints(
        l3.endSketchPoint, l1.startSketchPoint)

    # Detect joint axis orientation in sketch space
    joint_is_sketch_h = abs(m2.x - m1.x) > abs(m2.y - m1.y)
    gc = sk.geometricConstraints
    if joint_is_sketch_h:
        gc.addHorizontal(l1); gc.addHorizontal(l3)
        gc.addVertical(l2); gc.addVertical(l4)
    else:
        gc.addVertical(l1); gc.addVertical(l3)
        gc.addHorizontal(l2); gc.addHorizontal(l4)

    JD = H if joint_is_sketch_h else V
    TD = V if joint_is_sketch_h else H
    d = sk.sketchDimensions

    # Dim 1: finger width (along joint axis)
    d.addDistanceDimension(
        l1.startSketchPoint, l1.endSketchPoint,
        JD, Point3D.create(m1.x - 0.5, (m1.y + m2.y) / 2, 0)
    ).parameter.expression = f"{p}_finger_w"

    # Dim 2: board thickness (across thickness axis)
    d.addDistanceDimension(
        l1.startSketchPoint, l4.startSketchPoint,
        TD, Point3D.create((m1.x + m4.x) / 2, m1.y - 0.5, 0)
    ).parameter.expression = thick_expr

    # Dim 3: origin → first finger along joint axis
    d.addDistanceDimension(
        sk.originPoint, l1.startSketchPoint,
        JD, Point3D.create(m1.x - 1, m1.y / 2, 0)
    ).parameter.expression = j_expr

    # Dim 4: origin → first finger along thickness axis
    d.addDistanceDimension(
        sk.originPoint, l1.startSketchPoint,
        TD, Point3D.create(m1.x / 2, m1.y - 1, 0)
    ).parameter.expression = y_wide_expr

    prof = af.smallest_profile(sk)

    # Extrude CUT into pin board
    cut_feat = af.ext_op(comp, prof, dist_expr, CUT, pin_body,
                         f"{name}_Cut")

    # Extrude JOIN into finger board
    join_feat = af.ext_op(comp, prof, dist_expr, JOIN, finger_body,
                          f"{name}_Join")

    # Pattern both along joint axis
    if pattern_axis is None:
        pattern_axis = comp.zConstructionAxis

    cut_pat = af.feat_pattern(comp, cut_feat, pattern_axis,
                              f"{p}_count", f"{p}_pitch",
                              f"{name}_PatCut")
    join_pat = af.feat_pattern(comp, join_feat, pattern_axis,
                               f"{p}_count", f"{p}_pitch",
                               f"{name}_PatJoin")

    # CUT pin board into finger board to create interlocking sockets.
    # The pin board's remaining material IS its fingers — cutting it
    # into the finger board carves matching slots.
    pin_cut = af.combine(comp, finger_body, pin_body, CUT, True,
                         f"{name}_PinCut")

    return {
        "cut_feat": cut_feat,
        "join_feat": join_feat,
        "cut_pattern": cut_pat,
        "join_pattern": join_pat,
        "pin_cut": pin_cut,
    }


def box(comp, front, left,
        x_mid, y_mid, thick_expr,
        right=None, back=None,
        prefix="fj", name="FJ", ev=None,
        fl_plane=None,
        front_expr="0 in",
        joint_axis="z", thick_axis="y",
        joint_base_expr=None):
    """Create finger joints at box corners.

    Same structure as dovetail.box() but with rectangular fingers:
      1-corner (right=None, back=None): 1 sk + 1 JOIN + 1 pat + 1 CUT = 4 features
      2-corner (back=None): 1 sk + 1 JOIN + 1 mir + 1 pat + 1 CUT = 5 features
      4-corner: 1 sk + 1 JOIN + 3 mir + 1 pat + 2 CUT = 8 features

    Board layout is identical to dovetails:
    - front/back = "slot boards" (get CUT by finger boards)
    - left/right = "finger boards" (narrower, get fingers JOINed)

    IMPORTANT: Finger boards (left, right) must be built narrower along
    thick_axis — inset by board thickness on each side — so there is no
    initial overlap with slot boards at corners.

    Args:
        comp: Component containing all boards.
        front: Front slot board body.
        left: Left finger board body (narrower, no corner overlap).
        x_mid: Construction plane at finger board midpoint (for left→right mirror).
        y_mid: Construction plane at slot board midpoint (for front→back mirror).
        thick_expr: Board thickness expression (= extrude distance).
        right: Right finger board body. If None, 1-corner (FL only).
        back: Back slot board body. If None, no back finger joints.
        prefix: Finger joint parameter prefix (from define_params).
        name: Feature name prefix.
        ev: Evaluator function.
        fl_plane: Sketch plane at left board, perpendicular to ext_axis.
            Default: comp.yZConstructionPlane.
        front_expr: Expression for front board outer face on thick_axis.
        joint_axis: Model axis along which fingers repeat ("x", "y", or "z").
        thick_axis: Model axis along which slot board thickness runs.
        joint_base_expr: Expression for joint-axis offset of first board edge.

    Returns:
        Dict with feature references.
    """
    if ev is None:
        ev = af._make_ev()

    if fl_plane is None:
        fl_plane = comp.yZConstructionPlane

    p = prefix

    # ── Derive ext_axis (the remaining axis) ──
    ext_axis = ({"x", "y", "z"} - {joint_axis, thick_axis}).pop()
    _idx = {"x": 0, "y": 1, "z": 2}

    def _pt3(ext_v, thick_v, joint_v):
        """Create Point3D from axis-mapped values."""
        c = [0.0, 0.0, 0.0]
        c[_idx[ext_axis]] = ext_v
        c[_idx[thick_axis]] = thick_v
        c[_idx[joint_axis]] = joint_v
        return Point3D.create(c[0], c[1], c[2])

    # ── Evaluate parameters ──
    fw = ev(f"{p}_finger_w")
    count = int(ev(f"{p}_count"))
    bt = ev(thick_expr)

    # Joint-axis base offset
    if joint_base_expr is not None:
        j_base = ev(joint_base_expr)
        j_expr = joint_base_expr
    else:
        j_base = 0.0
        j_expr = "0 in"

    # Front face along thick_axis
    f_wide = ev(front_expr) if front_expr != "0 in" else 0.0
    f_inner = f_wide + bt

    # ext_axis coordinate of sketch plane
    if hasattr(fl_plane, 'geometry'):
        px = getattr(fl_plane.geometry.origin, ext_axis)
    else:
        px = 0.0

    # ── Rectangle sketch on fl_plane ──
    sk = comp.sketches.add(fl_plane)
    sk.name = f"{name}_Sk"
    m = sk.modelToSketchSpace

    m1 = m(_pt3(px, f_wide, j_base))
    m2 = m(_pt3(px, f_wide, j_base + fw))
    m3 = m(_pt3(px, f_inner, j_base + fw))
    m4 = m(_pt3(px, f_inner, j_base))

    lines = sk.sketchCurves.sketchLines
    l1 = lines.addByTwoPoints(
        Point3D.create(m1.x, m1.y, 0), Point3D.create(m2.x, m2.y, 0))
    l2 = lines.addByTwoPoints(
        l1.endSketchPoint, Point3D.create(m3.x, m3.y, 0))
    l3 = lines.addByTwoPoints(
        l2.endSketchPoint, Point3D.create(m4.x, m4.y, 0))
    l4 = lines.addByTwoPoints(
        l3.endSketchPoint, l1.startSketchPoint)

    # Detect joint axis orientation in sketch space
    joint_h = abs(m2.x - m1.x) > abs(m2.y - m1.y)
    gc = sk.geometricConstraints
    if joint_h:
        gc.addHorizontal(l1); gc.addHorizontal(l3)
        gc.addVertical(l2); gc.addVertical(l4)
    else:
        gc.addVertical(l1); gc.addVertical(l3)
        gc.addHorizontal(l2); gc.addHorizontal(l4)

    JD = H if joint_h else V
    TD = V if joint_h else H
    d = sk.sketchDimensions

    # Dim 1: finger width (along joint axis)
    d.addDistanceDimension(
        l1.startSketchPoint, l1.endSketchPoint,
        JD, Point3D.create(m1.x - 0.5, (m1.y + m2.y) / 2, 0)
    ).parameter.expression = f"{p}_finger_w"

    # Dim 2: board thickness (across thickness axis)
    d.addDistanceDimension(
        l1.startSketchPoint, l4.startSketchPoint,
        TD, Point3D.create((m1.x + m4.x) / 2, m1.y - 0.5, 0)
    ).parameter.expression = thick_expr

    # Dim 3: origin → first finger along joint axis
    d.addDistanceDimension(
        sk.originPoint, l1.startSketchPoint,
        JD, Point3D.create(m1.x - 1, m1.y / 2, 0)
    ).parameter.expression = j_expr

    # Dim 4: origin → first finger along thickness axis
    d.addDistanceDimension(
        sk.originPoint, l1.startSketchPoint,
        TD, Point3D.create(m1.x / 2, m1.y - 1, 0)
    ).parameter.expression = front_expr

    prof = af.smallest_profile(sk)

    # ── JOIN into finger boards (left, right) ──
    finger_boards = [left, right] if right is not None else [left]
    join_fl = af.ext_op(comp, prof, thick_expr, JOIN, finger_boards,
                        f"{name}_JoinFL")

    # ── Mirrors ──
    feats = [join_fl]
    if right is not None and back is not None:
        # 4-corner: 3 mirrors (FL→BL, FL→FR, FR→BR)
        mir_bl = af.mirror_feats(comp, [join_fl], y_mid, f"{name}_MirBL")
        mir_fr = af.mirror_feats(comp, [join_fl], x_mid, f"{name}_MirFR")
        mir_br = af.mirror_feats(comp, [mir_fr], y_mid, f"{name}_MirBR")
        feats = [join_fl, mir_bl, mir_fr, mir_br]
    elif right is not None:
        # 2-corner: 1 mirror (FL→FR)
        mir_fr = af.mirror_feats(comp, [join_fl], x_mid, f"{name}_MirFR")
        feats = [join_fl, mir_fr]
    elif back is not None:
        # 2-corner: 1 mirror (FL→BL)
        mir_bl = af.mirror_feats(comp, [join_fl], y_mid, f"{name}_MirBL")
        feats = [join_fl, mir_bl]
    # else: 1-corner, no mirrors needed

    # ── Pattern along joint_axis ──
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
        VI(f"{p}_count"), VI(f"{p}_pitch"),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    inp.quantityTwo = VI("1")
    pat = comp.features.rectangularPatternFeatures.add(inp)
    pat.name = f"{name}_Pat"

    # ── CUT slot boards using finger boards as tools ──
    cut_front = af.combine(comp, front, finger_boards, CUT, True,
                           f"{name}_CutFront")
    cut_back = None
    if back is not None:
        cut_back = af.combine(comp, back, finger_boards, CUT, True,
                              f"{name}_CutBack")

    return {
        "join_fl": join_fl, "pattern": pat,
        "cut_front": cut_front, "cut_back": cut_back,
    }
