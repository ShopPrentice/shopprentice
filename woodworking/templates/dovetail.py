"""Dovetail joint template.

Creates dovetail joints between two boards at a corner. Supports through
dovetails with automatic tail count, pin width derivation, and parametric
half-pin layout.

Usage:
    from woodworking.templates import dovetail

    # Through dovetail at a box corner — works whether front_body and
    # side_body live in the same component or in different components.
    # The function derives the owning component from tail_body and places
    # the final CUT combine intra-component (direct bodies) or at root
    # (assembly proxies) automatically.
    dovetail.corner(
        pin_body=front_body, tail_body=side_body,
        plane=side_body.parentComponent.yZConstructionPlane,
        x_model=0, y_wide=0, y_narrow=bt,
        y_wide_expr="0 in", thick_expr="board_thick", dist_expr="board_thick",
        name="DT_FL", ev=ctx.ev,
    )

    # Select the right variant for a purpose
    variant = dovetail.select_variant("drawer_front")  # → "half_blind"
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
    "name": "dovetail",
    "category": "joinery",
    "variants": {
        "through": {
            "description": "Tails visible on both faces — classic hand-cut joint",
            "best_for": ["boxes", "case sides", "premium visible joints", "drawers (back)"],
            "not_for": ["drawer fronts (shows end grain)"],
        },
        "half_blind": {
            "description": "Tails hidden on one face — front board conceals joint",
            "best_for": ["drawer fronts", "case tops where one face must be clean"],
            "not_for": [],
            "template": "half_blind_dovetail",
        },
        "houndstooth": {
            "description": "Mitered face with hidden dovetail for strength",
            "best_for": ["premium case corners", "jewelry boxes"],
            "not_for": ["structural joints", "thick stock"],
            "status": "planned",
        },
        "full_blind": {
            "description": "Completely hidden dovetail — no visible joint",
            "best_for": ["fine furniture", "hidden structural corners"],
            "not_for": ["high-volume production"],
            "status": "planned",
        },
    },
    "params": {
        "dt_angle": "Dovetail angle (typically 7-14 deg, 8 deg default)",
        "dt_tail_w": "Tail width at wide face",
        "dt_tail_count": "Number of tails",
        "dt_pin_w": "Derived: joint_h / count - tail_w",
        "dt_pitch": "Derived: joint_h / count",
        "dt_narrow_w": "Derived: tail_w - 2 * thick * tan(angle)",
        "dt_half_pin": "Derived: pin_w / 2 (half-pin at edges)",
    },
}


# ── Private helpers ──────────────────────────────────────────────────


def _trapezoid_sketch(comp, plane, m1_pt, m2_pt, m3_pt, m4_pt,
                      thick_expr, z_dim_expr, thick_base_expr,
                      prefix, name):
    """Build the shared through-dovetail trapezoid sketch with 6 parametric dims.

    The four model-space corner points define the trapezoid geometry:
      m1 = wide-side joint-base corner          (outer face, low end)
      m2 = wide-side joint-top corner           (outer face, high end)
      m3 = narrow-side joint-top corner         (inner face, high end - δ)
      m4 = narrow-side joint-base corner        (inner face, low end + δ)
    where δ = ``thick_expr * tan({prefix}_angle)``.

    Args:
        comp: Component that owns the sketch.
        plane: Construction plane / face to sketch on.
        m1_pt, m2_pt, m3_pt, m4_pt: Point3D in model space.
        thick_expr: Parametric expression for board thickness
            (dim across thickness axis between wide and narrow faces).
        z_dim_expr: Parametric expression for origin → l1.start along
            the joint axis (half-pin offset).
        thick_base_expr: Parametric expression for origin → l1.start
            along the thickness axis (wide-face position).
        prefix: Parameter-name prefix (e.g. ``"dt"``). Used to compose
            ``{prefix}_tail_w``, ``{prefix}_narrow_w``, and
            ``{prefix}_angle`` references inside the sketch dims.
        name: Sketch name prefix (sketch will be named ``{name}_Sk``).

    Returns:
        The selected profile (smallest_profile).
    """
    p = prefix
    sk = comp.sketches.add(plane)
    sk.name = f"{name}_Sk"
    m = sk.modelToSketchSpace

    m1 = m(m1_pt)
    m2 = m(m2_pt)
    m3 = m(m3_pt)
    m4 = m(m4_pt)

    lines = sk.sketchCurves.sketchLines
    l1 = lines.addByTwoPoints(
        Point3D.create(m1.x, m1.y, 0), Point3D.create(m2.x, m2.y, 0))
    l2 = lines.addByTwoPoints(
        l1.endSketchPoint, Point3D.create(m3.x, m3.y, 0))
    l3 = lines.addByTwoPoints(
        l2.endSketchPoint, Point3D.create(m4.x, m4.y, 0))
    l4 = lines.addByTwoPoints(
        l3.endSketchPoint, l1.startSketchPoint)

    # Detect whether the joint axis maps to sketch-H or sketch-V
    joint_is_sketch_h = abs(m2.x - m1.x) > abs(m2.y - m1.y)

    gc = sk.geometricConstraints
    if joint_is_sketch_h:
        gc.addHorizontal(l1)
        gc.addHorizontal(l3)
    else:
        gc.addVertical(l1)
        gc.addVertical(l3)

    JOINT_DIM = H if joint_is_sketch_h else V
    THICK_DIM = V if joint_is_sketch_h else H

    d = sk.sketchDimensions
    # Dim 1: l1 length = tail_w  (along joint axis)
    d.addDistanceDimension(
        l1.startSketchPoint, l1.endSketchPoint,
        JOINT_DIM, Point3D.create(m1.x - 0.5, (m1.y + m2.y) / 2, 0)
    ).parameter.expression = f"{p}_tail_w"
    # Dim 2: l3 length = narrow_w  (along joint axis)
    d.addDistanceDimension(
        l3.startSketchPoint, l3.endSketchPoint,
        JOINT_DIM, Point3D.create(m3.x + 0.5, (m3.y + m4.y) / 2, 0)
    ).parameter.expression = f"{p}_narrow_w"
    # Dim 3: l1→l4 distance = board_thick  (across thickness axis)
    d.addDistanceDimension(
        l1.startSketchPoint, l4.startSketchPoint,
        THICK_DIM, Point3D.create((m1.x + m4.x) / 2, m1.y - 0.5, 0)
    ).parameter.expression = thick_expr
    # Dim 4: origin → l1.start along joint axis = half_pin offset
    d.addDistanceDimension(
        sk.originPoint, l1.startSketchPoint,
        JOINT_DIM, Point3D.create(m1.x - 1, m1.y / 2, 0)
    ).parameter.expression = z_dim_expr
    # Dim 5: origin → l1.start along thickness axis = wide-face position
    d.addDistanceDimension(
        sk.originPoint, l1.startSketchPoint,
        THICK_DIM, Point3D.create(m1.x / 2, m1.y - 1, 0)
    ).parameter.expression = thick_base_expr
    # Dim 6: origin → l4.start along joint axis = half_pin + taper offset
    d.addDistanceDimension(
        sk.originPoint, l4.startSketchPoint,
        JOINT_DIM, Point3D.create(m4.x + 1, m4.y / 2, 0)
    ).parameter.expression = z_dim_expr + f" + {thick_expr} * tan({p}_angle)"

    return sp.smallest_profile(sk)


# ── Public API ───────────────────────────────────────────────────────

def select_variant(purpose):
    """Select the best dovetail variant for a given purpose.

    Args:
        purpose: One of "drawer_front", "drawer_back", "box", "case",
                 "premium", "hidden".

    Returns:
        Variant name string.
    """
    mapping = {
        "drawer_front": "half_blind",
        "drawer_back": "through",
        "box": "through",
        "case": "through",
        "premium": "houndstooth",
        "hidden": "full_blind",
    }
    return mapping.get(purpose, "through")


def define_params(params, prefix="dt", angle="8 deg", tail_w="0.5 in",
                  tail_count="3", joint_h_expr="open_height",
                  thick_expr="board_thick"):
    """Define all dovetail parameters with proper derivations.

    Creates user parameters for the independent values and derived
    parameters for everything else. All parametric — changing tail_count
    or tail_w automatically adjusts pin_w, pitch, narrow_w, etc.

    Args:
        params: design.userParameters
        prefix: Parameter name prefix (e.g. "dt", "dd" for drawer dovetails).
        angle: Angle expression.
        tail_w: Tail width expression.
        tail_count: Number of tails expression.
        joint_h_expr: Expression for the joint height (board dimension along
            which tails are distributed).
        thick_expr: Board thickness expression (for narrow width calc).

    Returns:
        Dict of parameter names for use in corner().
    """
    VI = adsk.core.ValueInput.createByString
    p = prefix

    # Independent params
    params.add(f"{p}_angle", VI(angle), "deg", "Dovetail angle")
    params.add(f"{p}_tail_w", VI(tail_w), "in", "Tail width at wide face")
    params.add(f"{p}_tail_count", VI(tail_count), "", "Number of tails")

    # Derived params
    params.add(f"{p}_pin_w",
               VI(f"{joint_h_expr} / {p}_tail_count - {p}_tail_w"),
               "in", "Pin width (derived)")
    params.add(f"{p}_pitch",
               VI(f"{joint_h_expr} / {p}_tail_count"),
               "in", "Tail pitch (derived)")
    params.add(f"{p}_narrow_w",
               VI(f"{p}_tail_w - 2 * {thick_expr} * tan({p}_angle)"),
               "in", "Narrow face width (derived)")
    params.add(f"{p}_half_pin",
               VI(f"{p}_pin_w / 2"),
               "in", "Half-pin at edges (derived)")

    return {
        "angle": f"{p}_angle",
        "tail_w": f"{p}_tail_w",
        "tail_count": f"{p}_tail_count",
        "pin_w": f"{p}_pin_w",
        "pitch": f"{p}_pitch",
        "narrow_w": f"{p}_narrow_w",
        "half_pin": f"{p}_half_pin",
    }


def corner(pin_body, tail_body, plane,
           x_model, y_wide, y_narrow,
           y_wide_expr, thick_expr, dist_expr,
           name="DT", prefix="dt", variant="through", ev=None,
           pattern_axis=None, z_base_expr=None):
    """Create a through dovetail joint at one corner.

    Topology (matches ``box(..., corners=1)``):
      1. ONE sketch on ``plane`` in ``tail_body``'s component.
      2. ``ext_op`` JOIN into ``tail_body`` + feature-pattern along the
         joint axis — the tail board grows by N tails as a single body.
      3. ONE ``combine`` CUT: ``pin_body`` is cut by ``tail_body``
         (keepTool=True). The combine holds a live reference to the tail
         body, so ``{prefix}_tail_count`` changes propagate through the
         feature pattern → enriched tail board → Front's sockets.

    Works for both same-component and cross-component cases without
    separate entry points. The sketch, extrude, and pattern always live
    in ``tail_body``'s component (intra-component, required for Fusion's
    feature-pattern to accept the participant path). The final combine
    is placed intra-component when ``pin_body`` and ``tail_body`` share
    a component, or at root with assembly-context proxies otherwise.

    Args:
        pin_body: Pin board body — receives tail sockets via the final
            combine. Can live in any component.
        tail_body: Tail board body — receives the JOIN extrude. The
            sketch, extrude, and pattern are all created in
            ``tail_body.parentComponent``.
        plane: Construction plane for the sketch. Must live in
            ``tail_body``'s component (typically
            ``tail_body.parentComponent.yZConstructionPlane``).
        x_model: Model X coordinate of the sketch plane position.
        y_wide: Model coordinate of the wide (outer) face.
        y_narrow: Model coordinate of the narrow (inner) face.
        y_wide_expr: Parametric expression for origin → wide-face
            distance along the thickness axis.
        thick_expr: Board thickness expression.
        dist_expr: Extrude distance expression (typically
            ``thick_expr``).
        name: Feature name prefix (e.g. ``"DT_FL"``).
        prefix: Parameter prefix (e.g. ``"dt"``, ``"dd"``).
        variant: Joint variant — currently only ``"through"``.
        ev: Evaluator function.
        pattern_axis: Construction axis for the pattern direction.
            Default: ``tail_body.parentComponent.zConstructionAxis``.
        z_base_expr: Expression for joint-axis offset of the first
            half-pin. Default: ``f"{prefix}_half_pin"``.

    Returns:
        Dict with keys: ``join_feat``, ``pattern``, ``cut_combine``.
    """
    if variant != "through":
        raise NotImplementedError(
            f"Dovetail variant '{variant}' not yet implemented. "
            f"Currently supported: 'through'")

    if ev is None:
        ev = sp._make_ev()

    p = prefix
    bt = ev(thick_expr)
    hp = ev(f"{p}_half_pin")
    tw = ev(f"{p}_tail_w")
    delta = bt * math.tan(ev(f"{p}_angle"))

    # Sketch, extrude, and pattern live in the tail board's component
    comp_tail = tail_body.parentComponent

    # Joint-axis offset and expression for the first half-pin
    if z_base_expr is None:
        z_base = hp
        z_dim_expr = f"{p}_pin_w / 2"
    else:
        z_base = ev(z_base_expr)
        z_dim_expr = z_base_expr

    # 4 trapezoid corners in model space — always (x, y, z)
    m1_pt = Point3D.create(x_model, y_wide,   z_base)
    m2_pt = Point3D.create(x_model, y_wide,   z_base + tw)
    m3_pt = Point3D.create(x_model, y_narrow, z_base + tw - delta)
    m4_pt = Point3D.create(x_model, y_narrow, z_base + delta)

    prof = _trapezoid_sketch(
        comp_tail, plane,
        m1_pt, m2_pt, m3_pt, m4_pt,
        thick_expr=thick_expr,
        z_dim_expr=z_dim_expr,
        thick_base_expr=y_wide_expr,
        prefix=prefix, name=name)

    # JOIN into tail_body (intra-component)
    join_feat = sp.ext_op(comp_tail, prof, dist_expr, JOIN, tail_body,
                          f"{name}_Join")

    # Feature-pattern the JOIN along the joint axis
    if pattern_axis is None:
        pattern_axis = comp_tail.zConstructionAxis

    pattern = sp.feat_pattern(comp_tail, join_feat, pattern_axis,
                              f"{p}_tail_count", f"{p}_pitch",
                              f"{name}_Pat")

    # Final CUT combine — sp.combine_auto routes intra-component when
    # pin_body and tail_body share a component, or to root with
    # assembly proxies when they live in different components.
    cut_combine = sp.combine_auto(pin_body, tail_body, CUT, True,
                                   f"{name}_Cut")

    return {
        "join_feat": join_feat,
        "pattern": pattern,
        "cut_combine": cut_combine,
    }


def box(comp, front, left,
        x_mid, y_mid, thick_expr,
        right=None, back=None,
        prefix="dt", name="DT", ev=None,
        fl_plane=None,
        front_expr="0 in",
        joint_axis="z", thick_axis="y",
        joint_base_expr=None,
        thick_dir=1):
    """Create through dovetails at box corners.

    Supports 1-corner, 2-corner, or 4-corner dovetails on any axis
    orientation:
      1-corner (right=None, back=None): 1 sk + 1 JOIN + 1 pat + 1 CUT = 4 features
      2-corner (back=None): 1 sk + 1 JOIN + 1 mir + 1 pat + 1 CUT = 5 features
      4-corner: 1 sk + 1 JOIN + 3 mir + 1 pat + 2 CUT = 8 features

    Uses participantBodies=[left, right] on the ext_op JOIN so that
    mirrors across x_mid auto-target the correct board (whichever the
    mirrored extrude touches).

    IMPORTANT: Tail boards (left, right) must be built narrower along
    thick_axis — inset by board thickness on each side — so there is no
    initial overlap with pin boards at corners.

    Args:
        comp: Component containing all boards.
        front: Front pin board body.
        left: Left tail board body (narrower, no corner overlap).
        x_mid: Construction plane at tail board midpoint (for left→right mirror).
        y_mid: Construction plane at pin board midpoint (for front→back mirror).
        thick_expr: Board thickness expression (= extrude distance).
        right: Right tail board body. If None, 1-corner dovetails (FL only).
        back: Back pin board body. If None, no back dovetails.
        prefix: Dovetail parameter prefix (from define_params).
        name: Feature name prefix.
        ev: Evaluator function.
        fl_plane: Sketch plane at left board, perpendicular to ext_axis.
            Default: comp.yZConstructionPlane.
        front_expr: Expression for front board outer face on thick_axis.
        joint_axis: Model axis along which tails repeat ("x", "y", or "z").
        thick_axis: Model axis along which pin board thickness runs.
        joint_base_expr: Expression for joint-axis offset of first board edge.
            Use when boards are offset along the joint axis (e.g. Y-axis
            dovetails on boards starting at y=offset instead of y=0).
        thick_dir: Direction of taper along thick_axis. 1 (default) = narrow
            face at front_expr + thick (standard front dovetails). -1 = narrow
            face at front_expr - thick (back dovetails where front_expr is
            the outer face of the back board).

    Returns:
        Dict with feature references.
    """
    if ev is None:
        ev = sp._make_ev()

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

    # ── Validate dovetail parameters ──
    pin_w = ev(f"{p}_pin_w")
    if pin_w <= 0:
        n = int(ev(f"{p}_tail_count"))
        tw_in = ev(f"{p}_tail_w") / 2.54
        raise ValueError(
            f"Dovetails don't fit: {n} tails × {tw_in:.3f}in exceeds "
            f"joint height. Reduce {p}_tail_count or {p}_tail_w.")

    bt = ev(thick_expr)
    hp = ev(f"{p}_half_pin")
    tw = ev(f"{p}_tail_w")
    delta = bt * math.tan(ev(f"{p}_angle"))

    # Joint-axis base offset (for boards offset along joint axis)
    if joint_base_expr is not None:
        j_base_val = ev(joint_base_expr)
        j_base = j_base_val + hp
        j_expr = f"{joint_base_expr} + {p}_pin_w / 2"
    else:
        j_base = hp
        j_expr = f"{p}_pin_w / 2"

    # Front face values along thick_axis (wide = outer, narrow = inner)
    # thick_dir=1: narrow at front_expr + thick (standard front dovetails)
    # thick_dir=-1: narrow at front_expr - thick (back dovetails)
    f_wide = ev(front_expr) if front_expr != "0 in" else 0.0
    f_narrow = f_wide + thick_dir * bt

    # ext_axis coordinate of sketch plane
    if hasattr(fl_plane, 'geometry'):
        px = getattr(fl_plane.geometry.origin, ext_axis)
    else:
        px = 0.0

    # ── Single trapezoid sketch (axis-mapped corners → shared helper) ──
    m1_pt = _pt3(px, f_wide,   j_base)
    m2_pt = _pt3(px, f_wide,   j_base + tw)
    m3_pt = _pt3(px, f_narrow, j_base + tw - delta)
    m4_pt = _pt3(px, f_narrow, j_base + delta)

    prof = _trapezoid_sketch(
        comp, fl_plane,
        m1_pt, m2_pt, m3_pt, m4_pt,
        thick_expr=thick_expr,
        z_dim_expr=j_expr,
        thick_base_expr=front_expr,
        prefix=prefix, name=name)

    # ── ext_op JOIN with participantBodies ──
    # At FL position the extrude touches left → merges into left.
    # When right is provided, mirrors across x_mid auto-target the right board.
    tail_boards = [left, right] if right is not None else [left]
    join_fl = sp.ext_op(comp, prof, thick_expr, JOIN, tail_boards,
                        f"{name}_JoinFL")

    # ── Mirrors ──
    feats = [join_fl]
    if right is not None and back is not None:
        # 4-corner: 3 mirrors (FL→BL, FL→FR, FR→BR)
        mir_bl = sp.mirror_feats(comp, [join_fl], y_mid, f"{name}_MirBL")
        mir_fr = sp.mirror_feats(comp, [join_fl], x_mid, f"{name}_MirFR")
        mir_br = sp.mirror_feats(comp, [mir_fr], y_mid, f"{name}_MirBR")
        feats = [join_fl, mir_bl, mir_fr, mir_br]
    elif right is not None:
        # 2-corner: 1 mirror (FL→FR)
        mir_fr = sp.mirror_feats(comp, [join_fl], x_mid, f"{name}_MirFR")
        feats = [join_fl, mir_fr]
    elif back is not None:
        # 2-corner: 1 mirror (FL→BL)
        mir_bl = sp.mirror_feats(comp, [join_fl], y_mid, f"{name}_MirBL")
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
        VI(f"{p}_tail_count"), VI(f"{p}_pitch"),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    inp.quantityTwo = VI("1")
    pat = comp.features.rectangularPatternFeatures.add(inp)
    pat.name = f"{name}_Pat"

    # ── CUT pin boards using tail boards as tools ──
    cut_front = sp.combine(comp, front, tail_boards, CUT, True,
                           f"{name}_CutFront")
    cut_back = None
    if back is not None:
        cut_back = sp.combine(comp, back, tail_boards, CUT, True,
                              f"{name}_CutBack")

    return {
        "join_fl": join_fl, "pattern": pat,
        "cut_front": cut_front, "cut_back": cut_back,
    }

