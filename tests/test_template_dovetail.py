"""Test fixture for dovetail joint template.

Grid-based layout — each box lives in its own (col, row) slot on a
uniform ``grid_x`` × ``grid_y`` grid, so variants spread out predictably
regardless of how their individual dimensions change.

  Row 0 (y=0):           B1  1-corner 8x6x4     B2  1-corner 5x3x2
                         B3  2-corner 8x5x4     B4  2-corner 6x4x6 (4 tails)
  Row 1 (y=grid_y):      B5  4-corner 8x6x4     B6  4-corner 4x4x12 (6 tails)
                         B9  4-corner 7x5x3 (joint along X)
                         B10 4-corner 6x8x5 (joint along Y)
  Row 2 (y=2*grid_y):    B11 4-corner 6x4x5, rotated to (1,1,1)
                         B12 1-corner 8x6x4 — wide tails, ultra-thin pins
                         B13 4-corner 6x4x5, rotated 42° about (1,2,1)/√6
                         C1  corner() intra-component (direct API call)
                         C2  corner() cross-component (two components)

B1–B13 exercise ``dovetail.box()``. C1 and C2 exercise ``dovetail.corner()``
directly, covering the same-component and cross-component code paths of the
unified API.

For 2+ corners, the right tail board is created by mirroring the left
across x_mid. B11 and B13 are rotated via their occurrence transform.
"""
import adsk.core
import adsk.fusion
import math
import sys


def build_box(root, prefix, l_expr, w_expr, h_expr, t_expr,
              x_off_expr, dt_prefix, ev, y_off_expr="0 in",
              corners=4, occ_transform=None):
    """Build a box with through dovetails.

    Args:
        root: Root component.
        prefix: Name prefix.
        l_expr, w_expr, h_expr, t_expr: Dimension parameter expressions.
        x_off_expr: X offset expression.
        dt_prefix: Dovetail parameter prefix.
        ev: Evaluator function.
        y_off_expr: Y offset expression.
        corners: 4 = all corners, 2 = front corners only, 1 = FL corner only.
        occ_transform: Optional ``Matrix3D`` — placed on the new
            occurrence at creation time. Use this for rotated fixtures
            where sketch-level offsets can't express the placement.

    Returns:
        Dict with component, bodies, and body count.
    """
    from helpers import sp
    from woodworking.templates import dovetail

    occ = sp.make_comp(root, prefix, transform=occ_transform)
    comp = occ.component

    ox = ev(x_off_expr) if x_off_expr != "0 in" else 0.0
    oy = ev(y_off_expr) if y_off_expr != "0 in" else 0.0

    # Y expressions for board positions
    front_y_expr = y_off_expr
    back_y_expr = f"{y_off_expr} + {w_expr} - {t_expr}" if oy != 0.0 else f"{w_expr} - {t_expr}"
    tail_y_expr = f"{y_off_expr} + {t_expr}" if oy != 0.0 else t_expr
    tail_w_expr = f"{w_expr} - 2 * {t_expr}"

    # ── Front (pin board) ──
    if oy == 0.0:
        front_sk_pl = comp.xZConstructionPlane
    else:
        front_sk_pl = sp.off_plane(comp, comp.xZConstructionPlane,
                                    y_off_expr, f"{prefix}_FrontYPl")

    sk, pr = sp.sketch_rect_model(comp, front_sk_pl,
        (x_off_expr, front_y_expr, "0 in"),
        {"x": l_expr, "z": h_expr}, f"{prefix}_Front_Sk", ev)
    front = sp.ext_new(comp, pr, t_expr, f"{prefix}_Front").bodies.item(0)
    front.name = f"{prefix}_Front"

    # ── Back (pin board, only for 4-corner) ──
    back = None
    if corners == 4:
        back_pl = sp.off_plane(comp, comp.xZConstructionPlane,
                               back_y_expr, f"{prefix}_Back_Pl")
        sk, pr = sp.sketch_rect_model(comp, back_pl,
            (x_off_expr, back_y_expr, "0 in"),
            {"x": l_expr, "z": h_expr}, f"{prefix}_Back_Sk", ev)
        back = sp.ext_new(comp, pr, t_expr, f"{prefix}_Back").bodies.item(0)
        back.name = f"{prefix}_Back"

    # ── Midplanes ──
    x_mid_expr = f"{x_off_expr} + {l_expr} / 2" if ox != 0.0 else f"{l_expr} / 2"
    y_mid_expr = f"{y_off_expr} + {w_expr} / 2" if oy != 0.0 else f"{w_expr} / 2"

    x_mid = sp.off_plane(comp, comp.yZConstructionPlane,
                          x_mid_expr, f"{prefix}_XMid")
    y_mid = sp.off_plane(comp, comp.xZConstructionPlane,
                          y_mid_expr, f"{prefix}_YMid")

    # ── Left (tail board, narrower) ──
    if ox == 0.0:
        left_pl = comp.yZConstructionPlane
    else:
        left_pl = sp.off_plane(comp, comp.yZConstructionPlane,
                               x_off_expr, f"{prefix}_Left_Pl")

    sk, pr = sp.sketch_rect_model(comp, left_pl,
        (x_off_expr, tail_y_expr, "0 in"),
        {"y": tail_w_expr, "z": h_expr}, f"{prefix}_Left_Sk", ev)
    left = sp.ext_new(comp, pr, t_expr, f"{prefix}_Left").bodies.item(0)
    left.name = f"{prefix}_Left"

    # ── Right (tail board via mirror of left, only for 2+ corners) ──
    right = None
    if corners >= 2:
        right_mir = sp.mirror_body(comp, left, x_mid, f"{prefix}_RightMir")
        right = right_mir.bodies.item(0)
        right.name = f"{prefix}_Right"

    board_count = 1 + (1 if back else 0) + 1 + (1 if right else 0)
    print(f"  {prefix} boards built: {board_count} boards"
          f"{' (left mirrored → right)' if right else ''}")

    # ── Dovetails: 1 sketch, mirrors to corners, CUT pin boards ──
    result = dovetail.box(comp, front, left,
                          x_mid, y_mid, thick_expr=t_expr,
                          right=right,
                          back=back,
                          prefix=dt_prefix, name=prefix, ev=ev,
                          fl_plane=left_pl,
                          front_expr=front_y_expr)

    # Restore body names by position
    x_mid_val = ev(x_mid_expr)
    y_mid_val = ev(y_mid_expr)
    for i in range(comp.bRepBodies.count):
        b = comp.bRepBodies.item(i)
        bb = b.boundingBox
        cx = (bb.minPoint.x + bb.maxPoint.x) / 2
        cy = (bb.minPoint.y + bb.maxPoint.y) / 2
        dx = bb.maxPoint.x - bb.minPoint.x
        dy = bb.maxPoint.y - bb.minPoint.y
        if dx > dy:  # pin board (wider in X)
            if cy < y_mid_val:
                b.name = f"{prefix}_Front"
            else:
                b.name = f"{prefix}_Back"
        else:  # tail board (wider in Y)
            if cx < x_mid_val:
                b.name = f"{prefix}_Left"
            else:
                b.name = f"{prefix}_Right"

    n = comp.bRepBodies.count
    names = [comp.bRepBodies.item(i).name for i in range(n)]
    print(f"  {prefix} dovetails done ({corners}-corner): {n} bodies -> {names}")
    return {"comp": comp, "occ": occ, "count": n, "names": names,
            "front": front, "back": back, "left": left, "right": right}


def run(context):
    # Evict any cached ``woodworking``/``helpers`` modules from earlier
    # sessions — Fusion keeps Python modules hot across script runs, so
    # a recent edit to dovetail.py (new signatures, etc.) wouldn't be
    # picked up without this.
    for _mod in list(sys.modules):
        if _mod.startswith("woodworking") or _mod.startswith("helpers"):
            del sys.modules[_mod]

    app = adsk.core.Application.get()

    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString

    from helpers import sp
    from woodworking.templates import dovetail

    ctx = sp.DesignContext(design)

    # clean=true wipes features but keeps user parameters; drop any
    # lingering params from earlier runs so dovetail.define_params()
    # and our own _add_param helper are free to re-define cleanly.
    for i in range(params.count - 1, -1, -1):
        try:
            params.item(i).deleteMe()
        except Exception:
            pass

    def _add_param(name, expr, unit, comment):
        p = params.itemByName(name)
        if p is not None:
            try:
                p.expression = expr
            except Exception:
                pass
        else:
            params.add(name, VI(expr), unit, comment)

    # ── Grid: each fixture lives in its own (col, row) slot ──
    # Spacing is large enough for the biggest box (8 in) plus rotation
    # margins. Change grid_x/grid_y to re-space the whole gallery uniformly.
    _add_param("grid_x", "14 in", "in", "Grid X spacing between boxes")
    _add_param("grid_y", "12 in", "in", "Grid Y spacing between boxes")

    def slot(col, row):
        x_expr = "0 in" if col == 0 else f"{col} * grid_x"
        y_expr = "0 in" if row == 0 else f"{row} * grid_y"
        return x_expr, y_expr

    # ================================================================
    # B1 @ (0,0): 1-corner 8x6x4, 3 tails, 8 deg
    # ================================================================
    print("=" * 50 + "\nB1 @ (0,0): 1-corner 8x6x4, 3 tails\n" + "=" * 50)
    b1_x, b1_y = slot(0, 0)
    _add_param("b1_l", "8 in", "in", "B1 length")
    _add_param("b1_w", "6 in", "in", "B1 width")
    _add_param("b1_h", "4 in", "in", "B1 height")
    _add_param("b1_t", "0.5 in", "in", "B1 thickness")
    dovetail.define_params(params, prefix="dt1",
        angle="8 deg", tail_w="0.75 in", tail_count="3",
        joint_h_expr="b1_h", thick_expr="b1_t")
    r1 = build_box(root, "B1", "b1_l", "b1_w", "b1_h", "b1_t",
                   b1_x, "dt1", ctx.ev, y_off_expr=b1_y, corners=1)
    assert r1["count"] == 2, f"B1: expected 2, got {r1['count']}"
    print("B1: PASS\n")

    # ================================================================
    # B2 @ (1,0): 1-corner jewelry box 5x3x2, single tail
    # ================================================================
    print("=" * 50 + "\nB2 @ (1,0): 1-corner jewelry box 5x3x2\n" + "=" * 50)
    b2_x, b2_y = slot(1, 0)
    _add_param("b2_l", "5 in", "in", "B2 length")
    _add_param("b2_w", "3 in", "in", "B2 width")
    _add_param("b2_h", "2 in", "in", "B2 height")
    _add_param("b2_t", "0.375 in", "in", "B2 thickness")
    dovetail.define_params(params, prefix="dt2",
        angle="8 deg", tail_w="0.25 in", tail_count="1",
        joint_h_expr="b2_h", thick_expr="b2_t")
    r2 = build_box(root, "B2", "b2_l", "b2_w", "b2_h", "b2_t",
                   b2_x, "dt2", ctx.ev, y_off_expr=b2_y, corners=1)
    assert r2["count"] == 2, f"B2: expected 2, got {r2['count']}"
    print("B2: PASS\n")

    # ================================================================
    # B3 @ (2,0): 2-corner 8x5x4, front only, 3 tails
    # ================================================================
    print("=" * 50 + "\nB3 @ (2,0): 2-corner 8x5x4, front only\n" + "=" * 50)
    b3_x, b3_y = slot(2, 0)
    _add_param("b3_l", "8 in", "in", "B3 length")
    _add_param("b3_w", "5 in", "in", "B3 width")
    _add_param("b3_h", "4 in", "in", "B3 height")
    _add_param("b3_t", "0.5 in", "in", "B3 thickness")
    dovetail.define_params(params, prefix="dt3",
        angle="8 deg", tail_w="0.5 in", tail_count="3",
        joint_h_expr="b3_h", thick_expr="b3_t")
    r3 = build_box(root, "B3", "b3_l", "b3_w", "b3_h", "b3_t",
                   b3_x, "dt3", ctx.ev, y_off_expr=b3_y, corners=2)
    assert r3["count"] == 3, f"B3: expected 3, got {r3['count']}"
    print("B3: PASS\n")

    # ================================================================
    # B4 @ (3,0): 2-corner 6x4x6, 4 tails
    # ================================================================
    print("=" * 50 + "\nB4 @ (3,0): 2-corner 6x4x6, 4 tails\n" + "=" * 50)
    b4_x, b4_y = slot(3, 0)
    _add_param("b4_l", "6 in", "in", "B4 length")
    _add_param("b4_w", "4 in", "in", "B4 width")
    _add_param("b4_h", "6 in", "in", "B4 height")
    _add_param("b4_t", "0.5 in", "in", "B4 thickness")
    dovetail.define_params(params, prefix="dt4",
        angle="8 deg", tail_w="0.5 in", tail_count="4",
        joint_h_expr="b4_h", thick_expr="b4_t")
    r4 = build_box(root, "B4", "b4_l", "b4_w", "b4_h", "b4_t",
                   b4_x, "dt4", ctx.ev, y_off_expr=b4_y, corners=2)
    assert r4["count"] == 3, f"B4: expected 3, got {r4['count']}"
    print("B4: PASS\n")

    # ================================================================
    # B5 @ (0,1): 4-corner standard 8x6x4, 3 tails
    # ================================================================
    print("=" * 50 + "\nB5 @ (0,1): 4-corner standard 8x6x4\n" + "=" * 50)
    b5_x, b5_y = slot(0, 1)
    _add_param("b5_l", "8 in", "in", "B5 length")
    _add_param("b5_w", "6 in", "in", "B5 width")
    _add_param("b5_h", "4 in", "in", "B5 height")
    _add_param("b5_t", "0.5 in", "in", "B5 thickness")
    dovetail.define_params(params, prefix="dt5",
        angle="8 deg", tail_w="0.75 in", tail_count="3",
        joint_h_expr="b5_h", thick_expr="b5_t")
    r5 = build_box(root, "B5", "b5_l", "b5_w", "b5_h", "b5_t",
                   b5_x, "dt5", ctx.ev, y_off_expr=b5_y)
    assert r5["count"] == 4, f"B5: expected 4, got {r5['count']}"
    print("B5: PASS\n")

    # ================================================================
    # B6 @ (1,1): 4-corner tall narrow 4x4x12, 6 tails
    # ================================================================
    print("=" * 50 + "\nB6 @ (1,1): 4-corner tall narrow 4x4x12, 6 tails\n" + "=" * 50)
    b6_x, b6_y = slot(1, 1)
    _add_param("b6_l", "4 in", "in", "B6 length")
    _add_param("b6_w", "4 in", "in", "B6 width")
    _add_param("b6_h", "12 in", "in", "B6 height")
    _add_param("b6_t", "0.5 in", "in", "B6 thickness")
    dovetail.define_params(params, prefix="dt6",
        angle="8 deg", tail_w="0.625 in", tail_count="6",
        joint_h_expr="b6_h", thick_expr="b6_t")
    r6 = build_box(root, "B6", "b6_l", "b6_w", "b6_h", "b6_t",
                   b6_x, "dt6", ctx.ev, y_off_expr=b6_y)
    assert r6["count"] == 4, f"B6: expected 4, got {r6['count']}"
    print("B6: PASS\n")

    # ================================================================
    # B9 @ (2,1): 4-corner, joint along X, 7x5x3 — built in place
    # Box "lying flat": pin boards thin in Z, tail boards thin in Y.
    # Sketch origins and construction planes carry the grid-slot offset
    # so the component's bodies land directly at their final world
    # coordinates — no moveFeature, no occurrence transform.
    # ================================================================
    print("=" * 50 + "\nB9 @ (2,1): 4-corner, joint along X, 7x5x3\n" + "=" * 50)
    b9_x, b9_y = slot(2, 1)
    _add_param("b9_l", "7 in", "in", "B9 length (X)")
    _add_param("b9_w", "5 in", "in", "B9 width (Y)")
    _add_param("b9_h", "3 in", "in", "B9 height (Z)")
    _add_param("b9_t", "0.5 in", "in", "B9 thickness")

    dovetail.define_params(params, prefix="dt9",
        angle="8 deg", tail_w="0.75 in", tail_count="3",
        joint_h_expr="b9_l", thick_expr="b9_t")

    b9_occ = sp.make_comp(root, "B9")
    b9_c = b9_occ.component

    # Front: xY plane (Z=0), at grid slot
    sk, pr = sp.sketch_rect_model(b9_c, b9_c.xYConstructionPlane,
        (b9_x, b9_y, "0 in"),
        {"x": "b9_l", "y": "b9_w"}, "B9_Front_Sk", ctx.ev)
    b9_front = sp.ext_new(b9_c, pr, "b9_t", "B9_Front").bodies.item(0)
    b9_front.name = "B9_Front"

    # Back: offset xY plane at Z=b9_h-b9_t
    b9_back_pl = sp.off_plane(b9_c, b9_c.xYConstructionPlane,
                               "b9_h - b9_t", "B9_Back_Pl")
    sk, pr = sp.sketch_rect_model(b9_c, b9_back_pl,
        (b9_x, b9_y, "b9_h - b9_t"),
        {"x": "b9_l", "y": "b9_w"}, "B9_Back_Sk", ctx.ev)
    b9_back = sp.ext_new(b9_c, pr, "b9_t", "B9_Back").bodies.item(0)
    b9_back.name = "B9_Back"

    # Mid planes shifted by Y offset
    b9_ext_mid = sp.off_plane(b9_c, b9_c.xZConstructionPlane,
                               f"{b9_y} + b9_w / 2", "B9_ExtMid")
    b9_thick_mid = sp.off_plane(b9_c, b9_c.xYConstructionPlane,
                                 "b9_h / 2", "B9_ThickMid")

    # Left plane: xZ offset by b9_y (Y of grid slot)
    b9_left_pl = sp.off_plane(b9_c, b9_c.xZConstructionPlane,
                               b9_y, "B9_LeftPl")
    sk, pr = sp.sketch_rect_model(b9_c, b9_left_pl,
        (b9_x, b9_y, "b9_t"),
        {"x": "b9_l", "z": "b9_h - 2 * b9_t"}, "B9_Left_Sk", ctx.ev)
    b9_left = sp.ext_new(b9_c, pr, "b9_t", "B9_Left").bodies.item(0)
    b9_left.name = "B9_Left"

    b9_right_mir = sp.mirror_body(b9_c, b9_left, b9_ext_mid, "B9_RightMir")
    b9_right = b9_right_mir.bodies.item(0)
    b9_right.name = "B9_Right"

    dovetail.box(b9_c, b9_front, b9_left,
                 b9_ext_mid, b9_thick_mid, thick_expr="b9_t",
                 right=b9_right, back=b9_back,
                 prefix="dt9", name="B9", ev=ctx.ev,
                 fl_plane=b9_left_pl,
                 front_expr="0 in",
                 joint_axis="x", thick_axis="z",
                 joint_base_expr=b9_x)

    b9_n = b9_c.bRepBodies.count
    assert b9_n == 4, f"B9: expected 4, got {b9_n}"
    print("B9: PASS\n")

    # ================================================================
    # B10 @ (3,1): 4-corner, joint along Y, 6x8x5 — built in place
    # ================================================================
    print("=" * 50 + "\nB10 @ (3,1): 4-corner, joint along Y, 6x8x5\n" + "=" * 50)
    b10_x, b10_y = slot(3, 1)
    _add_param("b10_l", "6 in", "in", "B10 length (X)")
    _add_param("b10_w", "8 in", "in", "B10 width (Y)")
    _add_param("b10_h", "5 in", "in", "B10 height (Z)")
    _add_param("b10_t", "0.5 in", "in", "B10 thickness")

    dovetail.define_params(params, prefix="dt10",
        angle="8 deg", tail_w="0.625 in", tail_count="4",
        joint_h_expr="b10_w", thick_expr="b10_t")

    b10_occ = sp.make_comp(root, "B10")
    b10_c = b10_occ.component

    # Front: yZ plane offset to X=b10_x
    b10_front_pl = sp.off_plane(b10_c, b10_c.yZConstructionPlane,
                                 b10_x, "B10_FrontPl")
    sk, pr = sp.sketch_rect_model(b10_c, b10_front_pl,
        (b10_x, b10_y, "0 in"),
        {"y": "b10_w", "z": "b10_h"}, "B10_Front_Sk", ctx.ev)
    b10_front = sp.ext_new(b10_c, pr, "b10_t", "B10_Front").bodies.item(0)
    b10_front.name = "B10_Front"

    # Back: yZ plane offset to X=b10_x + b10_l - b10_t
    b10_back_pl = sp.off_plane(b10_c, b10_c.yZConstructionPlane,
                                f"{b10_x} + b10_l - b10_t", "B10_Back_Pl")
    sk, pr = sp.sketch_rect_model(b10_c, b10_back_pl,
        (f"{b10_x} + b10_l - b10_t", b10_y, "0 in"),
        {"y": "b10_w", "z": "b10_h"}, "B10_Back_Sk", ctx.ev)
    b10_back = sp.ext_new(b10_c, pr, "b10_t", "B10_Back").bodies.item(0)
    b10_back.name = "B10_Back"

    # Left: xY plane (Z=0), inset by b10_t in X and at grid slot in Y
    sk, pr = sp.sketch_rect_model(b10_c, b10_c.xYConstructionPlane,
        (f"{b10_x} + b10_t", b10_y, "0 in"),
        {"x": "b10_l - 2 * b10_t", "y": "b10_w"}, "B10_Left_Sk", ctx.ev)
    b10_left = sp.ext_new(b10_c, pr, "b10_t", "B10_Left").bodies.item(0)
    b10_left.name = "B10_Left"

    b10_z_mid = sp.off_plane(b10_c, b10_c.xYConstructionPlane,
                              "b10_h / 2", "B10_ZMid")
    b10_right_mir = sp.mirror_body(b10_c, b10_left, b10_z_mid,
                                    "B10_RightMir")
    b10_right = b10_right_mir.bodies.item(0)
    b10_right.name = "B10_Right"

    b10_x_mid = sp.off_plane(b10_c, b10_c.yZConstructionPlane,
                              f"{b10_x} + b10_l / 2", "B10_XMid")

    dovetail.box(b10_c, b10_front, b10_left,
                 b10_z_mid, b10_x_mid, thick_expr="b10_t",
                 right=b10_right, back=b10_back,
                 prefix="dt10", name="B10", ev=ctx.ev,
                 fl_plane=b10_c.xYConstructionPlane,
                 front_expr=b10_x,
                 joint_axis="y", thick_axis="x",
                 joint_base_expr=b10_y)

    b10_n = b10_c.bRepBodies.count
    assert b10_n == 4, f"B10: expected 4, got {b10_n}"
    print("B10: PASS\n")

    # ================================================================
    # B11 @ (0,2): 4-corner rotated to (1,1,1)/√3
    # Rotation can't be baked into sketches, so we compute the
    # occurrence transform FIRST and pass it to build_box so the
    # component is placed at creation time. Bodies are built at
    # component-local coords; the occurrence carries rotation +
    # translation into world space.
    # ================================================================
    print("=" * 50 + "\nB11 @ (0,2): 4-corner rotated to (1,1,1)\n" + "=" * 50)
    _add_param("b11_l", "6 in", "in", "B11 length")
    _add_param("b11_w", "4 in", "in", "B11 width")
    _add_param("b11_h", "5 in", "in", "B11 height")
    _add_param("b11_t", "0.5 in", "in", "B11 thickness")
    dovetail.define_params(params, prefix="dt11",
        angle="8 deg", tail_w="0.5 in", tail_count="3",
        joint_h_expr="b11_h", thick_expr="b11_t")

    # Orthonormal basis: X→(-1,1,0)/√2, Y→(-1,-1,2)/√6, Z→(1,1,1)/√3.
    gx_cm = ctx.ev("grid_x"); gy_cm = ctx.ev("grid_y")
    s3, s2, s6 = 1/math.sqrt(3), 1/math.sqrt(2), 1/math.sqrt(6)
    xf11 = adsk.core.Matrix3D.create()
    xf11.setCell(0, 0, -s2); xf11.setCell(1, 0, s2); xf11.setCell(2, 0, 0)
    xf11.setCell(0, 1, -s6); xf11.setCell(1, 1, -s6); xf11.setCell(2, 1, 2*s6)
    xf11.setCell(0, 2, s3);  xf11.setCell(1, 2, s3);  xf11.setCell(2, 2, s3)
    xf11.setCell(0, 3, 0 * gx_cm + 6 * 2.54)   # col 0 + small x-nudge
    xf11.setCell(1, 3, 2 * gy_cm)              # row 2
    xf11.setCell(2, 3, 5 * 2.54)

    r11 = build_box(root, "B11", "b11_l", "b11_w", "b11_h", "b11_t",
                    "0 in", "dt11", ctx.ev,
                    occ_transform=xf11)
    assert r11["count"] == 4
    print("B11: PASS (placed at creation)\n")

    # ================================================================
    # B12 @ (1,2): 1-corner 8x6x4 — WIDE TAILS / ULTRA-THIN PINS
    # Same geometry as B1. Only dovetail params change: 3 tails at
    # 1.2 in each along the 4 in joint height → 3.6 in of tails, and
    # the 4 pin segments share the remaining 0.4 in → 0.1 in per pin.
    # Demonstrates the dovetail template's tolerance for lopsided
    # tail:pin ratios without driving pin width negative.
    # ================================================================
    print("=" * 50 + "\nB12 @ (1,2): wide tails / ultra-thin pins\n" + "=" * 50)
    b12_x, b12_y = slot(1, 2)
    _add_param("b12_l", "8 in", "in", "B12 length")
    _add_param("b12_w", "6 in", "in", "B12 width")
    _add_param("b12_h", "4 in", "in", "B12 height")
    _add_param("b12_t", "0.5 in", "in", "B12 thickness")
    dovetail.define_params(params, prefix="dt12",
        angle="8 deg", tail_w="1.2 in", tail_count="3",
        joint_h_expr="b12_h", thick_expr="b12_t")
    r12 = build_box(root, "B12", "b12_l", "b12_w", "b12_h", "b12_t",
                    b12_x, "dt12", ctx.ev, y_off_expr=b12_y, corners=1)
    assert r12["count"] == 2, f"B12: expected 2, got {r12['count']}"
    print("B12: PASS (wide tails, pins ~0.10 in)\n")

    # ================================================================
    # B13 @ (2,2): 4-corner 6x4x5, rotated 42° about (1,2,1)/√6
    # A more extreme tilt than B11 — axis is not a coordinate axis or
    # the body diagonal, angle is non-special, so the box ends up at
    # a visibly awkward orientation. Exercises the same build_box
    # pipeline — all dovetail geometry is computed in component space
    # and the rotation is applied via the occurrence transform.
    # ================================================================
    print("=" * 50 + "\nB13 @ (2,2): rotated 42° about (1,2,1)/√6\n" + "=" * 50)
    _add_param("b13_l", "6 in", "in", "B13 length")
    _add_param("b13_w", "4 in", "in", "B13 width")
    _add_param("b13_h", "5 in", "in", "B13 height")
    _add_param("b13_t", "0.5 in", "in", "B13 thickness")
    dovetail.define_params(params, prefix="dt13",
        angle="8 deg", tail_w="0.5 in", tail_count="3",
        joint_h_expr="b13_h", thick_expr="b13_t")
    # 42° axis-angle rotation about (1,2,1)/√6, placed at creation time
    # (same reason as B11).
    ax_raw = (1.0, 2.0, 1.0)
    ax_m = math.sqrt(sum(c*c for c in ax_raw))
    ax = tuple(c / ax_m for c in ax_raw)
    theta = math.radians(42.0)
    c_t = math.cos(theta); s_t = math.sin(theta); one_c = 1 - c_t
    ux, uy, uz = ax
    rot = [
        [c_t + ux*ux*one_c,    ux*uy*one_c - uz*s_t, ux*uz*one_c + uy*s_t],
        [uy*ux*one_c + uz*s_t, c_t + uy*uy*one_c,    uy*uz*one_c - ux*s_t],
        [uz*ux*one_c - uy*s_t, uz*uy*one_c + ux*s_t, c_t + uz*uz*one_c],
    ]
    xf13 = adsk.core.Matrix3D.create()
    for r_ in range(3):
        for c_ in range(3):
            xf13.setCell(r_, c_, rot[r_][c_])
    xf13.setCell(0, 3, 2 * gx_cm + 3 * 2.54)  # col 2 + nudge toward slot centre
    xf13.setCell(1, 3, 2 * gy_cm + 3 * 2.54)  # row 2
    xf13.setCell(2, 3, 4 * 2.54)

    r13 = build_box(root, "B13", "b13_l", "b13_w", "b13_h", "b13_t",
                    "0 in", "dt13", ctx.ev,
                    occ_transform=xf13)
    assert r13["count"] == 4
    print("B13: PASS (placed at creation)\n")

    # ================================================================
    # B14 @ (0,3): 1-corner 8x6x4 with pad=1/8" — edge padding demo
    # Same thin-pin geometry as B12 (3 tails × 1.2" on a 4" board,
    # inner pin ~0.1"), but with dt_pad=0.125" so the end pins grow
    # to pad + pin_w/2 ≈ 0.175" — robust enough not to break.
    # Verifies:
    #   - pin_w shrinks because effective board = h - 2*pad
    #   - first tail z-base shifts by pad (corner() codepath)
    #   - body count matches expected
    # ================================================================
    print("=" * 50 + "\nB14 @ (0,3): 1-corner with pad=1/8\" — edge padding\n" + "=" * 50)
    b14_x, b14_y = slot(0, 3)
    _add_param("b14_l", "8 in", "in", "B14 length")
    _add_param("b14_w", "6 in", "in", "B14 width")
    _add_param("b14_h", "4 in", "in", "B14 height")
    _add_param("b14_t", "0.5 in", "in", "B14 thickness")
    dovetail.define_params(params, prefix="dt14",
        angle="8 deg", tail_w="1.2 in", tail_count="3",
        joint_h_expr="b14_h", thick_expr="b14_t",
        pad="0.125 in")
    # With pad: pin_w = (4 - 0.25) / 3 - 1.2 = 0.05", edge = pad + pin_w/2 = 0.15"
    # Without pad would be: pin_w = 4/3 - 1.2 = 0.133", edge half-pin = 0.066"
    pin_w_v = ctx.ev("dt14_pin_w") / 2.54
    edge_pin_v = (ctx.ev("dt14_pad") + ctx.ev("dt14_half_pin")) / 2.54
    assert edge_pin_v > 2 * pin_w_v, (
        f"B14: edge pin ({edge_pin_v:.3f}) should be > 2× inner ({pin_w_v:.3f})")
    r14 = build_box(root, "B14", "b14_l", "b14_w", "b14_h", "b14_t",
                    b14_x, "dt14", ctx.ev, y_off_expr=b14_y, corners=1)
    assert r14["count"] == 2, f"B14: expected 2, got {r14['count']}"
    print(f"B14: PASS (inner pin {pin_w_v:.3f}\", edge pin {edge_pin_v:.3f}\")\n")

    # ================================================================
    # B15 @ (1,3): 4-corner with pad=1/16" — exercises box() j_base
    # Standard 4-corner box but with pad=0.0625". Verifies that
    # box()'s j_base = pad + half_pin path produces a valid mirror +
    # pattern layout on all four corners.
    # ================================================================
    print("=" * 50 + "\nB15 @ (1,3): 4-corner 8x5x5 with pad=1/16\"\n" + "=" * 50)
    b15_x, b15_y = slot(1, 3)
    _add_param("b15_l", "8 in", "in", "B15 length")
    _add_param("b15_w", "5 in", "in", "B15 width")
    _add_param("b15_h", "5 in", "in", "B15 height")
    _add_param("b15_t", "0.5 in", "in", "B15 thickness")
    dovetail.define_params(params, prefix="dt15",
        angle="8 deg", tail_w="0.5 in", tail_count="4",
        joint_h_expr="b15_h", thick_expr="b15_t",
        pad="0.0625 in")
    r15 = build_box(root, "B15", "b15_l", "b15_w", "b15_h", "b15_t",
                    b15_x, "dt15", ctx.ev, y_off_expr=b15_y, corners=4)
    assert r15["count"] == 4, f"B15: expected 4, got {r15['count']}"
    print("B15: PASS (pad propagates through box() + 4 mirrors)\n")

    # ================================================================
    # C1 @ (3,2): dovetail.corner() — intra-component
    # Exercises the unified corner() API with pin + tail bodies in the
    # same component (simplest case).
    # ================================================================
    print("=" * 50 + "\nC1 @ (3,2): corner() intra-component\n" + "=" * 50)
    c1_x, c1_y = slot(3, 2)
    _add_param("c1_l", "8 in", "in", "C1 length")
    _add_param("c1_w", "6 in", "in", "C1 width")
    _add_param("c1_h", "4 in", "in", "C1 height")
    _add_param("c1_t", "0.5 in", "in", "C1 thickness")
    dovetail.define_params(params, prefix="dtc1",
        angle="8 deg", tail_w="0.5 in", tail_count="3",
        joint_h_expr="c1_h", thick_expr="c1_t")

    c1_occ = sp.make_comp(root, "C1")
    c1_comp = c1_occ.component
    # Pin board (Front) on xZ plane
    c1_front_pl = sp.off_plane(c1_comp, c1_comp.xZConstructionPlane,
                                c1_y, "C1_FrontYPl")
    sk, pr = sp.sketch_rect_model(c1_comp, c1_front_pl,
        (c1_x, c1_y, "0 in"),
        {"x": "c1_l", "z": "c1_h"}, "C1_Front_Sk", ctx.ev)
    c1_front = sp.ext_new(c1_comp, pr, "c1_t", "C1_Front").bodies.item(0)
    c1_front.name = "C1_Front"
    # Tail board (Left) on yZ plane, inset by t on the front side
    c1_left_pl = sp.off_plane(c1_comp, c1_comp.yZConstructionPlane,
                               c1_x, "C1_LeftXPl")
    sk, pr = sp.sketch_rect_model(c1_comp, c1_left_pl,
        (c1_x, f"{c1_y} + c1_t", "0 in"),
        {"y": "c1_w - 2 * c1_t", "z": "c1_h"}, "C1_Left_Sk", ctx.ev)
    c1_left = sp.ext_new(c1_comp, pr, "c1_t", "C1_Left").bodies.item(0)
    c1_left.name = "C1_Left"
    # Direct corner() — pin+tail in same comp, combine lives in c1_comp
    dovetail.corner(
        pin_body=c1_front, tail_body=c1_left, plane=c1_left_pl,
        x_model=ctx.ev(c1_x), y_wide=ctx.ev(c1_y),
        y_narrow=ctx.ev(c1_y) + ctx.ev("c1_t"),
        y_wide_expr=c1_y, thick_expr="c1_t", dist_expr="c1_t",
        name="C1_DT", prefix="dtc1", ev=ctx.ev)
    assert c1_comp.bRepBodies.count == 2, \
        f"C1: expected 2 bodies, got {c1_comp.bRepBodies.count}"
    print("C1: PASS (intra-component corner)\n")

    # ================================================================
    # C2 @ (4,2): dovetail.corner() — cross-component
    # Exercises the unified corner() API with pin + tail bodies in
    # SEPARATE components under root. The final combine lives at root
    # and uses assembly-context proxies on both bodies.
    # ================================================================
    print("=" * 50 + "\nC2 @ (4,2): corner() cross-component\n" + "=" * 50)
    c2_x, c2_y = slot(4, 2)
    _add_param("c2_l", "8 in", "in", "C2 length")
    _add_param("c2_w", "6 in", "in", "C2 width")
    _add_param("c2_h", "4 in", "in", "C2 height")
    _add_param("c2_t", "0.5 in", "in", "C2 thickness")
    dovetail.define_params(params, prefix="dtc2",
        angle="8 deg", tail_w="0.5 in", tail_count="3",
        joint_h_expr="c2_h", thick_expr="c2_t")

    # Front in its own component
    c2_fo = sp.make_comp(root, "C2_Front")
    c2_fc = c2_fo.component
    c2_fp = sp.off_plane(c2_fc, c2_fc.xZConstructionPlane,
                         c2_y, "C2_Front_YPl")
    sk, pr = sp.sketch_rect_model(c2_fc, c2_fp,
        (c2_x, c2_y, "0 in"),
        {"x": "c2_l", "z": "c2_h"}, "C2_Front_Sk", ctx.ev)
    c2_front = sp.ext_new(c2_fc, pr, "c2_t", "C2_Front").bodies.item(0)
    c2_front.name = "C2_Front"

    # Left in its own component
    c2_lo = sp.make_comp(root, "C2_Left")
    c2_lc = c2_lo.component
    c2_lp = sp.off_plane(c2_lc, c2_lc.yZConstructionPlane,
                         c2_x, "C2_Left_XPl")
    sk, pr = sp.sketch_rect_model(c2_lc, c2_lp,
        (c2_x, f"{c2_y} + c2_t", "0 in"),
        {"y": "c2_w - 2 * c2_t", "z": "c2_h"}, "C2_Left_Sk", ctx.ev)
    c2_left = sp.ext_new(c2_lc, pr, "c2_t", "C2_Left").bodies.item(0)
    c2_left.name = "C2_Left"

    # Direct corner() — pin+tail in DIFFERENT comps; corner() detects
    # this via body.parentComponent and routes the final combine to root
    # with createForAssemblyContext proxies.
    dovetail.corner(
        pin_body=c2_front, tail_body=c2_left, plane=c2_lp,
        x_model=ctx.ev(c2_x), y_wide=ctx.ev(c2_y),
        y_narrow=ctx.ev(c2_y) + ctx.ev("c2_t"),
        y_wide_expr=c2_y, thick_expr="c2_t", dist_expr="c2_t",
        name="C2_DT", prefix="dtc2", ev=ctx.ev)
    c2_total = c2_fc.bRepBodies.count + c2_lc.bRepBodies.count
    assert c2_total == 2, \
        f"C2: expected 2 bodies across 2 comps, got {c2_total}"
    print("C2: PASS (cross-component corner)\n")

    # ================================================================
    # Summary
    # ================================================================
    print("=" * 50 + "\nSUMMARY\n" + "=" * 50)
    total = 0
    for occ in root.occurrences:
        c = occ.component
        n = c.bRepBodies.count
        names = [c.bRepBodies.item(i).name for i in range(n)]
        print(f"  {c.name}: {n} bodies -> {names}")
        total += n

    # B1, B2, B12, B14: 2 bodies each (1-corner)     = 8
    # B3, B4          : 3 bodies each (2-corner)     = 6
    # B5, B6, B9, B10, B11, B13, B15: 4 bodies each  = 28
    # C1              : 2 bodies (corner intra)      = 2
    # C2_Front, C2_Left: 1 body each (corner cross)  = 2
    expected = 2 * 4 + 3 * 2 + 4 * 7 + 2 + 2  # = 46
    status = "PASS" if total == expected else "FAIL"
    print(f"\n{status}: expected {expected} bodies, got {total}")

    for occ in root.occurrences:
        c = occ.component
        for sk in c.sketches:
            sk.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
