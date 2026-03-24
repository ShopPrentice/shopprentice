"""Test fixture for dovetail joint template.

Tests define_params and box() with 9 configurations:
  B1-B2: 1-corner dovetails (2 boards: front + left)
  B3-B4: 2-corner dovetails (3 boards: front + left + right)
  B5-B6: 4-corner dovetails, joint along Z (default)
  B7: 4-corner, joint along X
  B8: 4-corner, joint along Y
  B9: 4-corner, rotated to (1,1,1) via occurrence transform

Each box is in its own component, positioned with X/Y offsets.
For 2+ corners, right tail board is created by mirroring left across x_mid.
"""
import adsk.core
import adsk.fusion
import math


def build_box(root, prefix, l_expr, w_expr, h_expr, t_expr,
              x_off_expr, dt_prefix, ev, y_off_expr="0 in",
              corners=4):
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

    Returns:
        Dict with component, bodies, and body count.
    """
    from helpers import sp
    from woodworking.templates import dovetail

    occ = sp.make_comp(root, prefix)
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
    app = adsk.core.Application.get()

    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString

    from helpers import sp
    from woodworking.templates import dovetail

    ctx = sp.DesignContext(design)

    # ================================================================
    # FIXTURE 1: 1-corner — 8x6x4, 0.5" thick, 3 tails, 8 deg
    # ================================================================
    print("=" * 50)
    print("FIXTURE 1: 1-corner box 8x6x4, 3 tails")
    print("=" * 50)

    params.add("b1_l", VI("8 in"), "in", "Box 1 length")
    params.add("b1_w", VI("6 in"), "in", "Box 1 width")
    params.add("b1_h", VI("4 in"), "in", "Box 1 height")
    params.add("b1_t", VI("0.5 in"), "in", "Box 1 thickness")

    dovetail.define_params(params, prefix="dt1",
        angle="8 deg", tail_w="0.75 in", tail_count="3",
        joint_h_expr="b1_h", thick_expr="b1_t")

    r1 = build_box(root, "B1", "b1_l", "b1_w", "b1_h", "b1_t",
                   "0 in", "dt1", ctx.ev, corners=1)
    assert r1["count"] == 2, f"Box 1: expected 2, got {r1['count']}"
    print("Box 1: PASS\n")

    # ================================================================
    # FIXTURE 2: 1-corner — 5x3x2, 0.375" thick, 1 tail, 8 deg
    # ================================================================
    print("=" * 50)
    print("FIXTURE 2: 1-corner jewelry box 5x3x2, single tail")
    print("=" * 50)

    params.add("b2_l", VI("5 in"), "in", "Box 2 length")
    params.add("b2_w", VI("3 in"), "in", "Box 2 width")
    params.add("b2_h", VI("2 in"), "in", "Box 2 height")
    params.add("b2_t", VI("0.375 in"), "in", "Box 2 thickness")
    params.add("b2_x", VI("b1_l + 2 in"), "in", "Box 2 X offset")

    dovetail.define_params(params, prefix="dt2",
        angle="8 deg", tail_w="0.25 in", tail_count="1",
        joint_h_expr="b2_h", thick_expr="b2_t")

    r2 = build_box(root, "B2", "b2_l", "b2_w", "b2_h", "b2_t",
                   "b2_x", "dt2", ctx.ev, corners=1)
    assert r2["count"] == 2, f"Box 2: expected 2, got {r2['count']}"
    print("Box 2: PASS\n")

    # ================================================================
    # FIXTURE 3: 2-corner — 8x5x4, 0.5" thick, 3 tails, 8 deg
    # ================================================================
    print("=" * 50)
    print("FIXTURE 3: 2-corner box 8x5x4, front only")
    print("=" * 50)

    params.add("b3_l", VI("8 in"), "in", "Box 3 length")
    params.add("b3_w", VI("5 in"), "in", "Box 3 width")
    params.add("b3_h", VI("4 in"), "in", "Box 3 height")
    params.add("b3_t", VI("0.5 in"), "in", "Box 3 thickness")
    params.add("b3_y", VI("b1_w + 2 in"), "in", "Box 3 Y offset")

    dovetail.define_params(params, prefix="dt3",
        angle="8 deg", tail_w="0.5 in", tail_count="3",
        joint_h_expr="b3_h", thick_expr="b3_t")

    r3 = build_box(root, "B3", "b3_l", "b3_w", "b3_h", "b3_t",
                   "0 in", "dt3", ctx.ev, y_off_expr="b3_y",
                   corners=2)
    assert r3["count"] == 3, f"Box 3: expected 3, got {r3['count']}"
    print("Box 3: PASS\n")

    # ================================================================
    # FIXTURE 4: 2-corner — 6x4x6, 0.5" thick, 4 tails, 8 deg
    # ================================================================
    print("=" * 50)
    print("FIXTURE 4: 2-corner box 6x4x6, front only, 4 tails")
    print("=" * 50)

    params.add("b4_l", VI("6 in"), "in", "Box 4 length")
    params.add("b4_w", VI("4 in"), "in", "Box 4 width")
    params.add("b4_h", VI("6 in"), "in", "Box 4 height")
    params.add("b4_t", VI("0.5 in"), "in", "Box 4 thickness")
    params.add("b4_x", VI("b3_l + 2 in"), "in", "Box 4 X offset")

    dovetail.define_params(params, prefix="dt4",
        angle="8 deg", tail_w="0.5 in", tail_count="4",
        joint_h_expr="b4_h", thick_expr="b4_t")

    r4 = build_box(root, "B4", "b4_l", "b4_w", "b4_h", "b4_t",
                   "b4_x", "dt4", ctx.ev, y_off_expr="b3_y",
                   corners=2)
    assert r4["count"] == 3, f"Box 4: expected 3, got {r4['count']}"
    print("Box 4: PASS\n")

    # ================================================================
    # FIXTURE 5: 4-corner — 8x6x4, 0.5" thick, 3 tails, 8 deg
    # ================================================================
    print("=" * 50)
    print("FIXTURE 5: 4-corner standard box 8x6x4")
    print("=" * 50)

    params.add("b5_l", VI("8 in"), "in", "Box 5 length")
    params.add("b5_w", VI("6 in"), "in", "Box 5 width")
    params.add("b5_h", VI("4 in"), "in", "Box 5 height")
    params.add("b5_t", VI("0.5 in"), "in", "Box 5 thickness")
    params.add("b5_y", VI("b3_y + b3_w + 2 in"), "in", "Box 5 Y offset")

    dovetail.define_params(params, prefix="dt5",
        angle="8 deg", tail_w="0.75 in", tail_count="3",
        joint_h_expr="b5_h", thick_expr="b5_t")

    r5 = build_box(root, "B5", "b5_l", "b5_w", "b5_h", "b5_t",
                   "0 in", "dt5", ctx.ev, y_off_expr="b5_y")
    assert r5["count"] == 4, f"Box 5: expected 4, got {r5['count']}"
    print("Box 5: PASS\n")

    # ================================================================
    # FIXTURE 6: 4-corner — 4x4x12, 0.5" thick, 6 tails, 8 deg
    # ================================================================
    print("=" * 50)
    print("FIXTURE 6: 4-corner tall narrow box 4x4x12, 6 tails")
    print("=" * 50)

    params.add("b6_l", VI("4 in"), "in", "Box 6 length")
    params.add("b6_w", VI("4 in"), "in", "Box 6 width")
    params.add("b6_h", VI("12 in"), "in", "Box 6 height")
    params.add("b6_t", VI("0.5 in"), "in", "Box 6 thickness")
    params.add("b6_x", VI("b5_l + 2 in"), "in", "Box 6 X offset")

    dovetail.define_params(params, prefix="dt6",
        angle="8 deg", tail_w="0.625 in", tail_count="6",
        joint_h_expr="b6_h", thick_expr="b6_t")

    r6 = build_box(root, "B6", "b6_l", "b6_w", "b6_h", "b6_t",
                   "b6_x", "dt6", ctx.ev, y_off_expr="b5_y")
    assert r6["count"] == 4, f"Box 6: expected 4, got {r6['count']}"
    print("Box 6: PASS\n")

    # ================================================================
    # FIXTURE 7: 4-corner — joint along X, thick along Z
    # Box "lying flat": pin boards thin in Z, tail boards thin in Y
    # ================================================================
    print("=" * 50)
    print("FIXTURE 7: 4-corner, joint along X, 7x5x3")
    print("=" * 50)

    params.add("b9_l", VI("7 in"), "in", "Box 7 length (X)")
    params.add("b9_w", VI("5 in"), "in", "Box 7 width (Y)")
    params.add("b9_h", VI("3 in"), "in", "Box 7 height (Z)")
    params.add("b9_t", VI("0.5 in"), "in", "Box 7 thickness")
    params.add("b9_y", VI("b5_y + b5_w + 2 in"), "in", "Box 7 Y offset")

    dovetail.define_params(params, prefix="dt9",
        angle="8 deg", tail_w="0.75 in", tail_count="3",
        joint_h_expr="b9_l", thick_expr="b9_t")

    b9_occ = sp.make_comp(root, "B9")
    b9_c = b9_occ.component

    # Front (pin board): spans X×Y at z=0, thin in Z
    sk, pr = sp.sketch_rect_model(b9_c, b9_c.xYConstructionPlane,
        ("0 in", "b9_y", "0 in"),
        {"x": "b9_l", "y": "b9_w"}, "B9_Front_Sk", ctx.ev)
    b9_front = sp.ext_new(b9_c, pr, "b9_t", "B9_Front").bodies.item(0)
    b9_front.name = "B9_Front"

    # Back (pin board): spans X×Y at z=b9_h-b9_t, thin in Z
    b9_back_pl = sp.off_plane(b9_c, b9_c.xYConstructionPlane,
                               "b9_h - b9_t", "B9_Back_Pl")
    sk, pr = sp.sketch_rect_model(b9_c, b9_back_pl,
        ("0 in", "b9_y", "b9_h - b9_t"),
        {"x": "b9_l", "y": "b9_w"}, "B9_Back_Sk", ctx.ev)
    b9_back = sp.ext_new(b9_c, pr, "b9_t", "B9_Back").bodies.item(0)
    b9_back.name = "B9_Back"

    # Midplanes for dovetail mirrors:
    #   x_mid: left→right mirror across ext_axis=Y midplane
    b9_ext_mid = sp.off_plane(b9_c, b9_c.xZConstructionPlane,
                               "b9_y + b9_w / 2", "B9_ExtMid")
    #   y_mid: front→back mirror across thick_axis=Z midplane
    b9_thick_mid = sp.off_plane(b9_c, b9_c.xYConstructionPlane,
                                 "b9_h / 2", "B9_ThickMid")

    # Left (tail board): spans X×Z at y=b9_y, thin in Y, narrower in Z
    b9_left_pl = sp.off_plane(b9_c, b9_c.xZConstructionPlane,
                               "b9_y", "B9_Left_Pl")
    sk, pr = sp.sketch_rect_model(b9_c, b9_left_pl,
        ("0 in", "b9_y", "b9_t"),
        {"x": "b9_l", "z": "b9_h - 2 * b9_t"}, "B9_Left_Sk", ctx.ev)
    b9_left = sp.ext_new(b9_c, pr, "b9_t", "B9_Left").bodies.item(0)
    b9_left.name = "B9_Left"

    # Right (tail board): mirror of left across ext_mid
    b9_right_mir = sp.mirror_body(b9_c, b9_left, b9_ext_mid, "B9_RightMir")
    b9_right = b9_right_mir.bodies.item(0)
    b9_right.name = "B9_Right"

    print(f"  B9 boards built: 4 boards (left mirrored → right)")

    # Dovetails: joint along X, thick along Z
    dt9_result = dovetail.box(b9_c, b9_front, b9_left,
                              b9_ext_mid, b9_thick_mid, thick_expr="b9_t",
                              right=b9_right, back=b9_back,
                              prefix="dt9", name="B9", ev=ctx.ev,
                              fl_plane=b9_left_pl,
                              front_expr="0 in",
                              joint_axis="x", thick_axis="z")

    b9_n = b9_c.bRepBodies.count
    b9_names = [b9_c.bRepBodies.item(i).name for i in range(b9_n)]
    print(f"  B7 dovetails done (4-corner, X-axis): {b9_n} bodies -> {b9_names}")
    assert b9_n == 4, f"Box 7: expected 4, got {b9_n}"
    print("Box 7: PASS\n")

    # ================================================================
    # FIXTURE 8: 4-corner — joint along Y, thick along X
    # Box "on its side": front thin in X, left thin in Z
    # ================================================================
    print("=" * 50)
    print("FIXTURE 8: 4-corner, joint along Y, 6x8x5")
    print("=" * 50)

    params.add("b10_l", VI("6 in"), "in", "Box 8 length (X)")
    params.add("b10_w", VI("8 in"), "in", "Box 8 width (Y)")
    params.add("b10_h", VI("5 in"), "in", "Box 8 height (Z)")
    params.add("b10_t", VI("0.5 in"), "in", "Box 8 thickness")
    params.add("b10_x", VI("b9_l + 2 in"), "in", "Box 8 X offset")
    params.add("b10_y", VI("b9_y"), "in", "Box 8 Y offset")

    dovetail.define_params(params, prefix="dt10",
        angle="8 deg", tail_w="0.625 in", tail_count="4",
        joint_h_expr="b10_w", thick_expr="b10_t")

    b10_occ = sp.make_comp(root, "B10")
    b10_c = b10_occ.component

    b10_ox = ctx.ev("b10_x")

    # Front (pin board): spans Y×Z at x=b10_x, thin in X
    b10_front_pl = sp.off_plane(b10_c, b10_c.yZConstructionPlane,
                                 "b10_x", "B10_Front_Pl")
    sk, pr = sp.sketch_rect_model(b10_c, b10_front_pl,
        ("b10_x", "b10_y", "0 in"),
        {"y": "b10_w", "z": "b10_h"}, "B10_Front_Sk", ctx.ev)
    b10_front = sp.ext_new(b10_c, pr, "b10_t", "B10_Front").bodies.item(0)
    b10_front.name = "B10_Front"

    # Back (pin board): at x=b10_x+b10_l-b10_t
    b10_back_pl = sp.off_plane(b10_c, b10_c.yZConstructionPlane,
                                "b10_x + b10_l - b10_t", "B10_Back_Pl")
    sk, pr = sp.sketch_rect_model(b10_c, b10_back_pl,
        ("b10_x + b10_l - b10_t", "b10_y", "0 in"),
        {"y": "b10_w", "z": "b10_h"}, "B10_Back_Sk", ctx.ev)
    b10_back = sp.ext_new(b10_c, pr, "b10_t", "B10_Back").bodies.item(0)
    b10_back.name = "B10_Back"

    # Left (tail board): spans Y×X at z=0, thin in Z, narrower in X
    sk, pr = sp.sketch_rect_model(b10_c, b10_c.xYConstructionPlane,
        ("b10_x + b10_t", "b10_y", "0 in"),
        {"x": "b10_l - 2 * b10_t", "y": "b10_w"}, "B10_Left_Sk", ctx.ev)
    b10_left = sp.ext_new(b10_c, pr, "b10_t", "B10_Left").bodies.item(0)
    b10_left.name = "B10_Left"

    # Right (tail board): mirror of left across z_mid
    b10_z_mid = sp.off_plane(b10_c, b10_c.xYConstructionPlane,
                              "b10_h / 2", "B10_ZMid")
    b10_right_mir = sp.mirror_body(b10_c, b10_left, b10_z_mid,
                                    "B10_RightMir")
    b10_right = b10_right_mir.bodies.item(0)
    b10_right.name = "B10_Right"

    # Midplanes for dovetail mirrors
    b10_x_mid = sp.off_plane(b10_c, b10_c.yZConstructionPlane,
                              "b10_x + b10_l / 2", "B10_XMid")
    b10_y_mid = sp.off_plane(b10_c, b10_c.xYConstructionPlane,
                              "b10_h / 2", "B10_YMid")

    # Dovetails: joint along Y, thick along X
    # fl_plane = XY plane at left board (z=0)
    dt10_result = dovetail.box(b10_c, b10_front, b10_left,
                               b10_z_mid, b10_x_mid, thick_expr="b10_t",
                               right=b10_right, back=b10_back,
                               prefix="dt10", name="B10", ev=ctx.ev,
                               fl_plane=b10_c.xYConstructionPlane,
                               front_expr="b10_x",
                               joint_axis="y", thick_axis="x",
                               joint_base_expr="b10_y")

    b10_n = b10_c.bRepBodies.count
    b10_names = [b10_c.bRepBodies.item(i).name for i in range(b10_n)]
    print(f"  B8 dovetails done (4-corner, Y-axis): {b10_n} bodies -> {b10_names}")
    assert b10_n == 4, f"Box 8: expected 4, got {b10_n}"
    print("Box 8: PASS\n")

    # ================================================================
    # FIXTURE 9: 4-corner — standard box rotated to (1,1,1) direction
    # Demonstrates dovetails at arbitrary angle via occurrence transform.
    # Boards are axis-aligned in component space; the occurrence is
    # rotated so the joint edge (Z in comp) maps to (1,1,1) in root.
    # ================================================================
    print("=" * 50)
    print("FIXTURE 9: 4-corner, rotated to (1,1,1), 6x4x5")
    print("=" * 50)

    params.add("b11_l", VI("6 in"), "in", "Box 9 length")
    params.add("b11_w", VI("4 in"), "in", "Box 9 width")
    params.add("b11_h", VI("5 in"), "in", "Box 9 height")
    params.add("b11_t", VI("0.5 in"), "in", "Box 9 thickness")

    dovetail.define_params(params, prefix="dt11",
        angle="8 deg", tail_w="0.5 in", tail_count="3",
        joint_h_expr="b11_h", thick_expr="b11_t")

    r11 = build_box(root, "B11", "b11_l", "b11_w", "b11_h", "b11_t",
                    "0 in", "dt11", ctx.ev)
    assert r11["count"] == 4, f"Box 9: expected 4, got {r11['count']}"

    # Rotate occurrence so comp-Z → (1,1,1)/√3 in root space
    # Orthonormal basis: X→(-1,1,0)/√2, Y→(-1,-1,2)/√6, Z→(1,1,1)/√3
    s3 = 1 / math.sqrt(3)
    s2 = 1 / math.sqrt(2)
    s6 = 1 / math.sqrt(6)
    xf = adsk.core.Matrix3D.create()
    # Column 0: comp-X maps to (-1/√2, 1/√2, 0)
    xf.setCell(0, 0, -s2); xf.setCell(1, 0, s2); xf.setCell(2, 0, 0)
    # Column 1: comp-Y maps to (-1/√6, -1/√6, 2/√6)
    xf.setCell(0, 1, -s6); xf.setCell(1, 1, -s6); xf.setCell(2, 1, 2*s6)
    # Column 2: comp-Z maps to (1/√3, 1/√3, 1/√3)
    xf.setCell(0, 2, s3); xf.setCell(1, 2, s3); xf.setCell(2, 2, s3)
    # Translation: position clear of other fixtures (~15in X, 43in Y, 5in Z)
    xf.setCell(0, 3, 15 * 2.54)
    xf.setCell(1, 3, 43 * 2.54)
    xf.setCell(2, 3, 5 * 2.54)
    r11["occ"].transform = xf

    print(f"  B9 rotated to (1,1,1) via occurrence transform")
    print("Box 9: PASS\n")

    # ================================================================
    # Summary
    # ================================================================
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)

    total = 0
    for occ in root.occurrences:
        c = occ.component
        n = c.bRepBodies.count
        names = [c.bRepBodies.item(i).name for i in range(n)]
        print(f"  {c.name}: {n} bodies -> {names}")
        total += n

    # B1,B2: 2 bodies each = 4
    # B3,B4: 3 bodies each = 6
    # B5-B9: 4 bodies each = 20
    expected = 4 + 6 + 20  # 30
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
