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

Proportions & defaults
----------------------
These rules of thumb produce joints that look right and work mechanically.
Start with the defaults; override when the piece demands it.

**dt_angle** — dovetail angle, measured off the perpendicular to the face:
  - Hardwood (oak, walnut, cherry, maple): 7-9°. Default 8° (≈ 1:7).
  - Softwood (pine, cedar): 10-14°. Softer fibers need more mechanical
    engagement since glue grabs less reliably.
  - Never < 7°: the joint can pull apart — insufficient lock.
  - Never > 14°: the tail tips become short-grain and break off easily.

**dt_tail_count** — choose from board_h, not stock thickness:
  - Fine work / small boxes: ~1 tail per 1" of board height.
  - Casework / drawers: ~1 tail per 1.5-2".
  - Minimum 3 tails for visual balance, unless the piece is < 3" tall.
  - Validate: the derived `{prefix}_pin_w` must stay > 0. If not,
    reduce tail_count or tail_w.

**tail : pin width ratio** (visual, derived from count + tail_w):
  - Classic fine work: 3:1 to 4:1 (tails dominant, pins look like thin
    vertical lines). This is the "handcut dovetail" aesthetic.
  - Modern / utilitarian: 2:1 (machine-cut look, pins more prominent).
  - Machine-cut router jig: often 1:1 (box-joint-like).
  - The ratio is implicit: given count and tail_w, pin_w is whatever
    fills the remaining board height.

**Pin width is derived, not a parameter.**
`pin_w = (board_h - 2 * pad) / count - tail_w`. Always pick `tail_w`
and `tail_count`; the pin width follows from the geometry so tails +
inner pins + edge pins always fill the board exactly.

**dt_pad** — edge padding. Extra material added to the end pins
beyond half a normal pin, on both board edges.
  - Default 0 (classic symmetric-half-pin layout).
  - Use when `pin_w` is very thin (< ~1/8" / 3mm) and the unpadded
    half-pins at the board edges would be fragile — e.g. 7+ tails
    on a 6" board with 3/4" tail_w (pin_w ≈ 0.1").
  - Typical values: 1/16" (1.5mm) to 3/16" (5mm). Keep below tail_w/2
    so edge pins don't visually dominate.
  - With pad > 0 the tail pattern still spaces evenly — only the end
    pins grow. Inner layout (count, tail_w, inner pin_w) is unaffected.
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

# The trapezoid sketch is shared with the half-blind template — through
# dovetails are the special case where the tail penetrates the full pin
# thickness (equivalent to half-blind with lap = 0). Keeping the sketch
# in one place means fixes propagate to both joint types.
from woodworking.templates._dovetail_common import (
    trapezoid_sketch as _trapezoid_sketch,
)


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
                  thick_expr="board_thick", pad="0 in",
                  proud_offset="0 in"):
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
        pad: Edge padding — extra material added to the board's end
            half-pins (on both edges) beyond half a normal pin. Default
            "0 in" reproduces the classic symmetric-half-pin layout.
            With pad > 0, the joint-axis space used for the tail pattern
            shrinks by ``2 * pad`` and the end pins grow to
            ``pad + pin_w / 2``. Useful when ``pin_w`` is very thin
            (sub-3mm) and the unpadded half-pins would be fragile.

    Returns:
        Dict of parameter names for use in corner().
    """
    VI = adsk.core.ValueInput.createByString
    p = prefix
    has_proud = proud_offset != "0 in"

    # Independent params
    params.add(f"{p}_angle", VI(angle), "deg", "Dovetail angle")
    params.add(f"{p}_tail_w", VI(tail_w), "in", "Tail width at wide face")
    params.add(f"{p}_tail_count", VI(tail_count), "", "Number of tails")
    params.add(f"{p}_pad", VI(pad), "in",
               "Edge padding — extra end-pin material beyond half a normal pin")
    if has_proud:
        params.add(f"{p}_proud", VI(proud_offset), "in",
                   "Proud offset (Krenov-style proud dovetails)")

    # Effective thickness for narrow_w: includes proud_offset because
    # the tail taper spans the full penetration depth.
    eff_thick = f"({thick_expr} + {p}_proud)" if has_proud else thick_expr

    # Derived params — tail pattern fits in (joint_h - 2*pad)
    params.add(f"{p}_pin_w",
               VI(f"({joint_h_expr} - 2 * {p}_pad) / {p}_tail_count"
                  f" - {p}_tail_w"),
               "in", "Inner pin width (derived)")
    params.add(f"{p}_pitch",
               VI(f"({joint_h_expr} - 2 * {p}_pad) / {p}_tail_count"),
               "in", "Tail pitch (derived)")
    params.add(f"{p}_narrow_w",
               VI(f"{p}_tail_w - 2 * {eff_thick} * tan({p}_angle)"),
               "in", "Narrow face width (derived)")
    params.add(f"{p}_half_pin",
               VI(f"{p}_pin_w / 2"),
               "in", "Inner half-pin — edge pins are pad + half_pin (derived)")

    return {
        "angle": f"{p}_angle",
        "tail_w": f"{p}_tail_w",
        "tail_count": f"{p}_tail_count",
        "pad": f"{p}_pad",
        "pin_w": f"{p}_pin_w",
        "pitch": f"{p}_pitch",
        "narrow_w": f"{p}_narrow_w",
        "half_pin": f"{p}_half_pin",
        "proud_offset": f"{p}_proud" if has_proud else None,
    }


def corner(pin_body, tail_body, plane,
           x_model, y_wide, y_narrow,
           y_wide_expr, thick_expr, dist_expr,
           name="DT", prefix="dt", variant="through", ev=None,
           pattern_axis=None, z_base_expr=None, anchor=None):
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
        anchor: Optional ``trapezoid_sketch`` anchor dict. When provided the
            trapezoid is anchored to a PROJECTED parent face (deps rules 1-3)
            instead of the sketch origin; default None keeps origin mode
            (backward compatible). See ``_dovetail_common.trapezoid_sketch``.

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

    # Joint-axis offset of the first tail. Edge pin = pad + half_pin.
    if z_base_expr is None:
        z_base = ev(f"{p}_pad") + hp
        z_dim_expr = f"{p}_pad + {p}_pin_w / 2"
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
        short_joint_expr=f"{z_dim_expr} + {thick_expr} * tan({p}_angle)",
        short_base_expr=f"{y_wide_expr} + {thick_expr}",
        prefix=prefix, name=name, anchor=anchor)

    # JOIN into tail_body (intra-component)
    join_feat = sp.ext_op(comp_tail, prof, dist_expr, JOIN, tail_body,
                          f"{name}_Join")

    # Feature-pattern the JOIN along the joint axis
    if pattern_axis is None:
        pattern_axis = comp_tail.zConstructionAxis

    pattern = sp.feat_pattern(comp_tail, join_feat, pattern_axis,
                              f"{p}_tail_count", f"{p}_pitch",
                              f"{name}_Pat")

    # Final CUT combine — sp.combine routes intra-component when
    # pin_body and tail_body share a component, or to root with
    # assembly proxies when they live in different components.
    cut_combine = sp.combine(pin_body, tail_body, CUT, True,
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
        thick_dir=1,
        proud_offset_expr=None,
        anchor=None):
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

    has_proud = proud_offset_expr is not None
    bt = ev(thick_expr)
    proud_val = ev(proud_offset_expr) if has_proud else 0.0
    dt_bt = bt + proud_val
    hp = ev(f"{p}_half_pin")
    tw = ev(f"{p}_tail_w")
    delta = dt_bt * math.tan(ev(f"{p}_angle"))

    # Effective thickness expressions for proud-aware dovetails.
    # dt_thick covers board_thick + proud_offset (full tail penetration).
    dt_thick_expr = (f"({thick_expr} + {proud_offset_expr})"
                     if has_proud else thick_expr)

    # Joint-axis base offset (for boards offset along joint axis).
    # Edge pin = pad + half_pin; first tail lands at this offset past the
    # board edge.
    pad_val = ev(f"{p}_pad")
    if joint_base_expr is not None:
        j_base_val = ev(joint_base_expr)
        j_base = j_base_val + pad_val + hp
        j_expr = f"{joint_base_expr} + {p}_pad + {p}_pin_w / 2"
    else:
        j_base = pad_val + hp
        j_expr = f"{p}_pad + {p}_pin_w / 2"

    # Front face values along thick_axis (wide = outer, narrow = inner).
    # For proud dovetails, the wide face extends past the pin board outer
    # face by proud_offset so the tails protrude.
    f_wide = ev(front_expr) if front_expr != "0 in" else 0.0
    f_wide_actual = f_wide - thick_dir * proud_val
    f_narrow = f_wide + thick_dir * bt

    # ext_axis coordinate of sketch plane
    if hasattr(fl_plane, 'geometry'):
        px = getattr(fl_plane.geometry.origin, ext_axis)
    else:
        px = 0.0

    # ── Single trapezoid sketch (axis-mapped corners → shared helper) ──
    # Wide face at f_wide_actual (past pin board outer face by proud_offset).
    m1_pt = _pt3(px, f_wide_actual, j_base)
    m2_pt = _pt3(px, f_wide_actual, j_base + tw)
    m3_pt = _pt3(px, f_narrow,      j_base + tw - delta)
    m4_pt = _pt3(px, f_narrow,      j_base + delta)

    prof = _trapezoid_sketch(
        comp, fl_plane,
        m1_pt, m2_pt, m3_pt, m4_pt,
        thick_expr=dt_thick_expr,
        short_joint_expr=f"{j_expr} + {dt_thick_expr} * tan({p}_angle)",
        short_base_expr=(
            f"({front_expr}) + {thick_expr}" if thick_dir >= 0
            else f"({front_expr}) - {thick_expr}"
        ),
        prefix=prefix, name=name, anchor=anchor)

    # ── ext_op JOIN with participantBodies ──
    # At FL position the extrude touches left → merges into left.
    # When right is provided, mirrors across x_mid auto-target the right board.
    # Extrude distance includes proud_offset (tail board is wider in ext_axis).
    tail_boards = [left, right] if right is not None else [left]
    join_fl = sp.ext_op(comp, prof, dt_thick_expr, JOIN, tail_boards,
                        f"{name}_JoinFL")

    # ── Mirrors ──
    src_feats = [join_fl]
    feats = list(src_feats)
    if right is not None and back is not None:
        # 4-corner: 3 mirrors (FL→BL, FL→FR, FR→BR)
        mir_bl = sp.mirror_feats(comp, src_feats, y_mid, f"{name}_MirBL")
        mir_fr = sp.mirror_feats(comp, src_feats, x_mid, f"{name}_MirFR")
        mir_br = sp.mirror_feats(comp, [mir_fr], y_mid, f"{name}_MirBR")
        feats = src_feats + [mir_bl, mir_fr, mir_br]
    elif right is not None:
        # 2-corner: 1 mirror (FL→FR)
        mir_fr = sp.mirror_feats(comp, src_feats, x_mid, f"{name}_MirFR")
        feats = src_feats + [mir_fr]
    elif back is not None:
        # 2-corner: 1 mirror (FL→BL)
        mir_bl = sp.mirror_feats(comp, src_feats, y_mid, f"{name}_MirBL")
        feats = src_feats + [mir_bl]
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
    cut_front = sp.combine(front, tail_boards, CUT, True,
                           f"{name}_CutFront")
    cut_back = None
    if back is not None:
        cut_back = sp.combine(back, tail_boards, CUT, True,
                              f"{name}_CutBack")

    # ── Proud trim: cut tail boards back to original thickness ──
    # The tail boards were extended by proud_offset in ext_axis direction
    # (toward the pin board ends). After the dovetail CUT carved the
    # sockets, trim the extension so only the proud pins remain.
    # Select the outer face directly and extrude CUT inward (NegativeExtent).
    trim_feats = []
    if has_proud:
        VI_trim = adsk.core.ValueInput.createByString
        NEG = adsk.fusion.ExtentDirections.NegativeExtentDirection
        # Left board's outer face is at min ext_axis (-1),
        # right board's outer face is at max ext_axis (+1).
        trim_dirs = [-1, +1] if len(tail_boards) == 2 else [-1]
        for tb, trim_dir in zip(tail_boards, trim_dirs):
            trim_face = sp.find_face(tb, ext_axis, trim_dir)
            ext_input = comp.features.extrudeFeatures.createInput(
                trim_face, CUT)
            ext_input.setOneSideExtent(
                adsk.fusion.DistanceExtentDefinition.create(
                    VI_trim(proud_offset_expr)),
                NEG)
            ext_input.participantBodies = [tb]
            trim_ext = comp.features.extrudeFeatures.add(ext_input)
            trim_ext.name = f"{name}_Trim_{tb.name}"
            trim_feats.append(trim_ext)

    # ── Proud tail chamfer: after trim, chamfer all proud tail tip edges ──
    # Each tail board has proud tails on BOTH sides (toward Front and Back
    # pin boards). Check both thick_axis extremes.
    #
    # NOTE: The tail chamfer uses coordinate-based edge selection on the
    # final geometry. It is NOT fully parametric with tail_count changes —
    # increasing tail_count via Change Parameters adds new tails from the
    # pattern, but the chamfer does not auto-apply to new tail edges.
    # Re-run the script to re-apply chamfers after count changes. This is
    # a Fusion limitation: chamfer features reference specific edge entities
    # and don't re-select by coordinate on recompute. The pin chamfer
    # adapts because the CUT recomputes the pin board's topology.
    tail_chamfer_feats = []
    if has_proud:
        # Find proud tail tip faces: parallel to each pin board's outer
        # face, offset by proud_offset, extent = board_thick along ext_axis.
        bt_cm = ev(thick_expr)
        proud_cm = proud_val
        ch_val = adsk.core.ValueInput.createByString(
            f"{proud_offset_expr} * 0.4")

        # Front pin board outer face as reference
        front_ref = sp.find_face(front, thick_axis, -thick_dir)
        # Back pin board outer face (if 4-corner)
        back_ref = sp.find_face(back, thick_axis, thick_dir) if back else None

        for tb in tail_boards:
            all_tip_faces = []
            # Front-side proud tails: offset in the outward normal direction
            # (ref face normal points away from pin board → toward the proud tip)
            ff = sp.find_faces_at_offset(
                tb, front_ref, proud_cm,
                extent_axis=ext_axis, extent_val=bt_cm, extent_tol=0.05)
            all_tip_faces.extend(ff)
            # Back-side proud tails
            if back_ref:
                bf = sp.find_faces_at_offset(
                    tb, back_ref, proud_cm,
                    extent_axis=ext_axis, extent_val=bt_cm, extent_tol=0.05)
                all_tip_faces.extend(bf)

            if all_tip_faces:
                edges = sp.edges_from_faces(all_tip_faces)
                if edges.count > 0:
                    ch_inp = comp.features.chamferFeatures.createInput2()
                    ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                        edges, ch_val, False)
                    ch = comp.features.chamferFeatures.add(ch_inp)
                    ch.name = f"{name}_TailCh_{tb.name}"
                    tail_chamfer_feats.append(ch)

    # ── Proud pin chamfer: find proud pin tip faces on each pin board ──
    # Parallel to tail board outer faces, offset by proud_offset, extent
    # = board_thick along thick_axis.
    pin_chamfer_feats = []
    if has_proud:
        ch_val = adsk.core.ValueInput.createByString(
            f"{proud_offset_expr} * 0.4")

        # Tail board outer faces as references (after trim = original faces)
        left_ref = sp.find_face(left, ext_axis, -1)
        right_ref = sp.find_face(right, ext_axis, +1) if right else None

        pin_boards = [front] + ([back] if back is not None else [])
        for pb in pin_boards:
            all_pin_faces = []
            # Left-end proud pins: ref face normal points away from tail
            # board → toward the proud pin tip, so offset is positive
            lf = sp.find_faces_at_offset(
                pb, left_ref, proud_cm,
                extent_axis=thick_axis, extent_val=bt_cm, extent_tol=0.05)
            all_pin_faces.extend(lf)
            # Right-end proud pins
            if right_ref:
                rf = sp.find_faces_at_offset(
                    pb, right_ref, proud_cm,
                    extent_axis=thick_axis, extent_val=bt_cm, extent_tol=0.05)
                all_pin_faces.extend(rf)

            if all_pin_faces:
                edges = sp.edges_from_faces(all_pin_faces)
                if edges.count > 0:
                    ch_inp = comp.features.chamferFeatures.createInput2()
                    ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                        edges, ch_val, False)
                    ch = comp.features.chamferFeatures.add(ch_inp)
                    ch.name = f"{name}_PinCh_{pb.name}"
                    pin_chamfer_feats.append(ch)

    return {
        "join_fl": join_fl, "pattern": pat,
        "cut_front": cut_front, "cut_back": cut_back,
        "trim_feats": trim_feats,
        "pin_chamfer_feats": pin_chamfer_feats,
        "tail_chamfer_feats": tail_chamfer_feats,
    }
