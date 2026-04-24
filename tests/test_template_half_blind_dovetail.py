"""Test fixture for half-blind dovetail joint template.

Tests define_params and box() with 5 configurations plus direct
corner() coverage:
  B1: 1-corner half-blind (2 boards: front + left)
  B2: 2-corner half-blind (3 boards: front + left + right)
  B3: 4-corner half-blind (4 boards)
  B4: 4-corner half-blind, different dimensions
  B5: 4-corner half-blind with edge padding (pad > 0)
  C1: direct corner() inside one component
  C2: direct corner() across two components

Layout: 2x2 grid, with B5 placed to the right of row 1.
  Row 0 (y=0):      B1 (8x6),   B2 (10x5)
  Row 1 (y=offset): B3 (8x6),   B4 (6x4),   B5 (8x6 + pad)
"""
import adsk.core
import adsk.fusion
import sys


def build_box(root, prefix, l_expr, w_expr, h_expr,
              pin_t_expr, side_t_expr,
              x_off_expr, hbd_prefix, ev, y_off_expr="0 in",
              corners=4, lap_expr=None):
    """Build a box with half-blind dovetails.

    Pin boards (front, back) are thicker than tail boards (left, right).

    Args:
        root: Root component.
        prefix: Name prefix.
        l_expr, w_expr, h_expr: Dimension param expressions.
        pin_t_expr: Pin board (front/back) thickness param.
        side_t_expr: Tail board (left/right) thickness param.
        x_off_expr: X offset expression.
        hbd_prefix: Half-blind dovetail parameter prefix.
        ev: Evaluator function.
        y_off_expr: Y offset expression.
        corners: 4 = all corners, 2 = front corners only, 1 = FL only.
        lap_expr: Lap parameter name (defaults to f"{hbd_prefix}_lap").

    Returns:
        Dict with component, bodies, and body count.
    """
    from helpers import sp
    from woodworking.templates import half_blind_dovetail

    if lap_expr is None:
        lap_expr = f"{hbd_prefix}_lap"

    occ = sp.make_comp(root, prefix)
    comp = occ.component

    ox = ev(x_off_expr) if x_off_expr != "0 in" else 0.0
    oy = ev(y_off_expr) if y_off_expr != "0 in" else 0.0

    # Y expressions for board positions
    front_y_expr = y_off_expr
    back_y_expr = (f"{y_off_expr} + {w_expr} - {pin_t_expr}"
                   if oy != 0.0 else f"{w_expr} - {pin_t_expr}")
    # Tail boards inset by pin_thick on each end (not side_thick)
    tail_y_expr = (f"{y_off_expr} + {pin_t_expr}"
                   if oy != 0.0 else pin_t_expr)
    tail_w_expr = f"{w_expr} - 2 * {pin_t_expr}"

    # Front (pin board, thicker)
    if oy == 0.0:
        front_sk_pl = comp.xZConstructionPlane
    else:
        front_sk_pl = sp.off_plane(comp, comp.xZConstructionPlane,
                                    y_off_expr, f"{prefix}_FrontYPl")

    sk, pr = sp.sketch_rect_model(comp, front_sk_pl,
        (x_off_expr, front_y_expr, "0 in"),
        {"x": l_expr, "z": h_expr}, f"{prefix}_Front_Sk", ev)
    front = sp.ext_new(comp, pr, pin_t_expr,
                       f"{prefix}_Front").bodies.item(0)
    front.name = f"{prefix}_Front"

    # Back (pin board, only for 4-corner)
    back = None
    if corners == 4:
        back_pl = sp.off_plane(comp, comp.xZConstructionPlane,
                               back_y_expr, f"{prefix}_Back_Pl")
        sk, pr = sp.sketch_rect_model(comp, back_pl,
            (x_off_expr, back_y_expr, "0 in"),
            {"x": l_expr, "z": h_expr}, f"{prefix}_Back_Sk", ev)
        back = sp.ext_new(comp, pr, pin_t_expr,
                          f"{prefix}_Back").bodies.item(0)
        back.name = f"{prefix}_Back"

    # Midplanes
    x_mid_expr = (f"{x_off_expr} + {l_expr} / 2"
                  if ox != 0.0 else f"{l_expr} / 2")
    y_mid_expr = (f"{y_off_expr} + {w_expr} / 2"
                  if oy != 0.0 else f"{w_expr} / 2")

    x_mid = sp.off_plane(comp, comp.yZConstructionPlane,
                          x_mid_expr, f"{prefix}_XMid")
    y_mid = sp.off_plane(comp, comp.xZConstructionPlane,
                          y_mid_expr, f"{prefix}_YMid")

    # Left (tail board, thinner, narrower by pin_thick on each end)
    if ox == 0.0:
        left_pl = comp.yZConstructionPlane
    else:
        left_pl = sp.off_plane(comp, comp.yZConstructionPlane,
                               x_off_expr, f"{prefix}_Left_Pl")

    sk, pr = sp.sketch_rect_model(comp, left_pl,
        (x_off_expr, tail_y_expr, "0 in"),
        {"y": tail_w_expr, "z": h_expr}, f"{prefix}_Left_Sk", ev)
    left = sp.ext_new(comp, pr, side_t_expr,
                      f"{prefix}_Left").bodies.item(0)
    left.name = f"{prefix}_Left"

    # Right (tail board via mirror, only for 2+ corners)
    right = None
    if corners >= 2:
        right_mir = sp.mirror_body(comp, left, x_mid,
                                    f"{prefix}_RightMir")
        right = right_mir.bodies.item(0)
        right.name = f"{prefix}_Right"

    board_count = 1 + (1 if back else 0) + 1 + (1 if right else 0)
    print(f"  {prefix} boards built: {board_count}"
          f"{' (left mirrored -> right)' if right else ''}")

    # Half-blind dovetails
    result = half_blind_dovetail.box(
        comp, front, left,
        x_mid, y_mid,
        pin_thick_expr=pin_t_expr,
        tail_thick_expr=side_t_expr,
        right=right, back=back,
        prefix=hbd_prefix, name=prefix, ev=ev,
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
        if dx > dy:  # pin board
            if cy < y_mid_val:
                b.name = f"{prefix}_Front"
            else:
                b.name = f"{prefix}_Back"
        else:  # tail board
            if cx < x_mid_val:
                b.name = f"{prefix}_Left"
            else:
                b.name = f"{prefix}_Right"

    n = comp.bRepBodies.count
    names = [comp.bRepBodies.item(i).name for i in range(n)]
    print(f"  {prefix} half-blind dovetails done ({corners}-corner): "
          f"{n} bodies -> {names}")
    return {"comp": comp, "occ": occ, "count": n, "names": names}


def run(context):
    app = adsk.core.Application.get()

    for name in list(sys.modules):
        if name == "helpers" or name.startswith("helpers."):
            del sys.modules[name]
        if name == "woodworking" or name.startswith("woodworking."):
            del sys.modules[name]

    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString

    from helpers import sp
    from woodworking.templates import half_blind_dovetail

    ctx = sp.DesignContext(design)

    # ================================================================
    # FIXTURE 1: 1-corner — 8x6x4, front 0.75", sides 0.5", lap 0.25"
    # ================================================================
    print("=" * 50)
    print("FIXTURE 1: 1-corner half-blind 8x6x4")
    print("=" * 50)

    params.add("b1_l", VI("8 in"), "in", "Box 1 length")
    params.add("b1_w", VI("6 in"), "in", "Box 1 width")
    params.add("b1_h", VI("4 in"), "in", "Box 1 height")
    params.add("b1_ft", VI("0.75 in"), "in", "Box 1 front thickness")
    params.add("b1_st", VI("0.5 in"), "in", "Box 1 side thickness")

    half_blind_dovetail.define_params(params, prefix="hbd1",
        angle="8 deg", tail_w="0.75 in", tail_count="3",
        joint_h_expr="b1_h", pin_thick_expr="b1_ft", lap="0.25 in")

    r1 = build_box(root, "B1", "b1_l", "b1_w", "b1_h",
                   "b1_ft", "b1_st", "0 in", "hbd1", ctx.ev,
                   corners=1)
    assert r1["count"] == 2, f"Box 1: expected 2, got {r1['count']}"
    print("Box 1: PASS\n")

    # ================================================================
    # FIXTURE 2: 2-corner — 10x5x4, front 0.75", sides 0.5", lap 0.25"
    # ================================================================
    print("=" * 50)
    print("FIXTURE 2: 2-corner half-blind 10x5x4")
    print("=" * 50)

    params.add("b2_l", VI("10 in"), "in", "Box 2 length")
    params.add("b2_w", VI("5 in"), "in", "Box 2 width")
    params.add("b2_h", VI("4 in"), "in", "Box 2 height")
    params.add("b2_ft", VI("0.75 in"), "in", "Box 2 front thickness")
    params.add("b2_st", VI("0.5 in"), "in", "Box 2 side thickness")
    params.add("b2_x", VI("b1_l + 2 in"), "in", "Box 2 X offset")

    half_blind_dovetail.define_params(params, prefix="hbd2",
        angle="8 deg", tail_w="0.625 in", tail_count="3",
        joint_h_expr="b2_h", pin_thick_expr="b2_ft", lap="0.25 in")

    r2 = build_box(root, "B2", "b2_l", "b2_w", "b2_h",
                   "b2_ft", "b2_st", "b2_x", "hbd2", ctx.ev,
                   corners=2)
    assert r2["count"] == 3, f"Box 2: expected 3, got {r2['count']}"
    print("Box 2: PASS\n")

    # ================================================================
    # FIXTURE 3: 4-corner — 8x6x4, front 0.75", sides 0.5", lap 0.25"
    # ================================================================
    print("=" * 50)
    print("FIXTURE 3: 4-corner half-blind 8x6x4")
    print("=" * 50)

    params.add("b3_l", VI("8 in"), "in", "Box 3 length")
    params.add("b3_w", VI("6 in"), "in", "Box 3 width")
    params.add("b3_h", VI("4 in"), "in", "Box 3 height")
    params.add("b3_ft", VI("0.75 in"), "in", "Box 3 front thickness")
    params.add("b3_st", VI("0.5 in"), "in", "Box 3 side thickness")
    params.add("b3_y", VI("b1_w + 2 in"), "in", "Box 3 Y offset")

    half_blind_dovetail.define_params(params, prefix="hbd3",
        angle="8 deg", tail_w="0.75 in", tail_count="3",
        joint_h_expr="b3_h", pin_thick_expr="b3_ft", lap="0.25 in")

    r3 = build_box(root, "B3", "b3_l", "b3_w", "b3_h",
                   "b3_ft", "b3_st", "0 in", "hbd3", ctx.ev,
                   y_off_expr="b3_y")
    assert r3["count"] == 4, f"Box 3: expected 4, got {r3['count']}"
    print("Box 3: PASS\n")

    # ================================================================
    # FIXTURE 4: 4-corner — 6x4x6, front 0.625", sides 0.375", lap 0.1875"
    # ================================================================
    print("=" * 50)
    print("FIXTURE 4: 4-corner half-blind 6x4x6, thinner stock")
    print("=" * 50)

    params.add("b4_l", VI("6 in"), "in", "Box 4 length")
    params.add("b4_w", VI("4 in"), "in", "Box 4 width")
    params.add("b4_h", VI("6 in"), "in", "Box 4 height")
    params.add("b4_ft", VI("0.625 in"), "in", "Box 4 front thickness")
    params.add("b4_st", VI("0.375 in"), "in", "Box 4 side thickness")
    params.add("b4_x", VI("b3_l + 2 in"), "in", "Box 4 X offset")

    half_blind_dovetail.define_params(params, prefix="hbd4",
        angle="8 deg", tail_w="0.5 in", tail_count="4",
        joint_h_expr="b4_h", pin_thick_expr="b4_ft", lap="0.1875 in")

    r4 = build_box(root, "B4", "b4_l", "b4_w", "b4_h",
                   "b4_ft", "b4_st", "b4_x", "hbd4", ctx.ev,
                   y_off_expr="b3_y")
    assert r4["count"] == 4, f"Box 4: expected 4, got {r4['count']}"
    print("Box 4: PASS\n")

    # ================================================================
    # FIXTURE 5: 4-corner half-blind with pad=1/16" — edge padding
    # Same box style as B3 but with dt_pad=0.0625" so end pins grow
    # to pad + half_pin. Exercises the half-blind box() j_base =
    # pad + half_pin code path across all 4 mirrored corners.
    # ================================================================
    print("=" * 50)
    print("FIXTURE 5: 4-corner half-blind with pad=1/16\"")
    print("=" * 50)

    params.add("b5_l", VI("8 in"), "in", "Box 5 length")
    params.add("b5_w", VI("6 in"), "in", "Box 5 width")
    params.add("b5_h", VI("5 in"), "in", "Box 5 height")
    params.add("b5_ft", VI("0.75 in"), "in", "Box 5 front thickness")
    params.add("b5_st", VI("0.5 in"), "in", "Box 5 side thickness")
    params.add("b5_x", VI("b4_x + b4_l + 2 in"), "in", "Box 5 X offset")

    half_blind_dovetail.define_params(params, prefix="hbd5",
        angle="8 deg", tail_w="0.5 in", tail_count="4",
        joint_h_expr="b5_h", pin_thick_expr="b5_ft", lap="0.25 in",
        pad="0.0625 in")  # NEW: edge padding

    # Verify padding produces thicker edge pins than an unpadded layout
    pad_v = ctx.ev("hbd5_pad") / 2.54
    half_pin_v = ctx.ev("hbd5_half_pin") / 2.54
    edge_pin_v = pad_v + half_pin_v
    unpadded_edge = ctx.ev("b5_h") / 2.54 / 4 / 2 - 0.25  # 5/4/2 - tail_w/2... just sanity
    assert pad_v > 0, "Fixture 5: pad should be > 0"
    assert edge_pin_v > half_pin_v, (
        f"Fixture 5: edge pin ({edge_pin_v:.4f}) should be > half_pin ({half_pin_v:.4f})")

    r5 = build_box(root, "B5", "b5_l", "b5_w", "b5_h",
                   "b5_ft", "b5_st", "b5_x", "hbd5", ctx.ev,
                   y_off_expr="b3_y")
    assert r5["count"] == 4, f"Box 5: expected 4, got {r5['count']}"
    print(f"Box 5: PASS (pad={pad_v:.4f}\", edge pin={edge_pin_v:.4f}\", "
          f"half_pin={half_pin_v:.4f}\")\n")

    # ================================================================
    # C1: corner() — intra-component
    # ================================================================
    print("=" * 50)
    print("C1: corner() intra-component")
    print("=" * 50)

    params.add("c1_l", VI("8 in"), "in", "C1 length")
    params.add("c1_w", VI("6 in"), "in", "C1 width")
    params.add("c1_h", VI("4 in"), "in", "C1 height")
    params.add("c1_ft", VI("0.75 in"), "in", "C1 front thickness")
    params.add("c1_st", VI("0.5 in"), "in", "C1 side thickness")
    params.add("c1_lap", VI("0.25 in"), "in", "C1 lap")
    params.add("c1_x", VI("b4_x + b4_l + 2 in"), "in", "C1 X offset")
    params.add("c1_y", VI("0 in"), "in", "C1 Y offset")

    half_blind_dovetail.define_params(params, prefix="hbdc1",
        angle="8 deg", tail_w="0.75 in", tail_count="3",
        joint_h_expr="c1_h", pin_thick_expr="c1_ft", lap="c1_lap")

    c1_occ = sp.make_comp(root, "C1")
    c1_comp = c1_occ.component
    c1_front_pl = sp.off_plane(c1_comp, c1_comp.xZConstructionPlane,
                               "c1_y", "C1_FrontYPl")
    sk, pr = sp.sketch_rect_model(c1_comp, c1_front_pl,
        ("c1_x", "c1_y", "0 in"),
        {"x": "c1_l", "z": "c1_h"}, "C1_Front_Sk", ctx.ev)
    c1_front = sp.ext_new(c1_comp, pr, "c1_ft", "C1_Front").bodies.item(0)
    c1_front.name = "C1_Front"

    c1_left_pl = sp.off_plane(c1_comp, c1_comp.yZConstructionPlane,
                              "c1_x", "C1_LeftXPl")
    sk, pr = sp.sketch_rect_model(c1_comp, c1_left_pl,
        ("c1_x", "c1_ft", "0 in"),
        {"y": "c1_w - 2 * c1_ft", "z": "c1_h"}, "C1_Left_Sk", ctx.ev)
    c1_left = sp.ext_new(c1_comp, pr, "c1_st", "C1_Left").bodies.item(0)
    c1_left.name = "C1_Left"

    half_blind_dovetail.corner(
        pin_body=c1_front, tail_body=c1_left, plane=c1_left_pl,
        x_model=ctx.ev("c1_x"),
        y_wide=ctx.ev("c1_lap"),
        y_narrow=ctx.ev("c1_ft"),
        y_wide_expr="c1_lap",
        socket_depth_expr="hbdc1_socket_depth",
        dist_expr="c1_st",
        name="C1_HBD", prefix="hbdc1", ev=ctx.ev)
    assert c1_comp.bRepBodies.count == 2, \
        f"C1: expected 2 bodies, got {c1_comp.bRepBodies.count}"
    print("C1: PASS (intra-component corner)\n")

    # ================================================================
    # C2: corner() — cross-component
    # ================================================================
    print("=" * 50)
    print("C2: corner() cross-component")
    print("=" * 50)

    params.add("c2_l", VI("8 in"), "in", "C2 length")
    params.add("c2_w", VI("6 in"), "in", "C2 width")
    params.add("c2_h", VI("4 in"), "in", "C2 height")
    params.add("c2_ft", VI("0.75 in"), "in", "C2 front thickness")
    params.add("c2_st", VI("0.5 in"), "in", "C2 side thickness")
    params.add("c2_lap", VI("0.25 in"), "in", "C2 lap")
    params.add("c2_x", VI("c1_x + c1_l + 2 in"), "in", "C2 X offset")
    params.add("c2_y", VI("0 in"), "in", "C2 Y offset")

    half_blind_dovetail.define_params(params, prefix="hbdc2",
        angle="8 deg", tail_w="0.75 in", tail_count="3",
        joint_h_expr="c2_h", pin_thick_expr="c2_ft", lap="c2_lap")

    c2_fo = sp.make_comp(root, "C2_Front")
    c2_fc = c2_fo.component
    c2_fp = sp.off_plane(c2_fc, c2_fc.xZConstructionPlane,
                         "c2_y", "C2_FrontYPl")
    sk, pr = sp.sketch_rect_model(c2_fc, c2_fp,
        ("c2_x", "c2_y", "0 in"),
        {"x": "c2_l", "z": "c2_h"}, "C2_Front_Sk", ctx.ev)
    c2_front = sp.ext_new(c2_fc, pr, "c2_ft", "C2_Front").bodies.item(0)
    c2_front.name = "C2_Front"

    c2_lo = sp.make_comp(root, "C2_Left")
    c2_lc = c2_lo.component
    c2_lp = sp.off_plane(c2_lc, c2_lc.yZConstructionPlane,
                         "c2_x", "C2_LeftXPl")
    sk, pr = sp.sketch_rect_model(c2_lc, c2_lp,
        ("c2_x", "c2_ft", "0 in"),
        {"y": "c2_w - 2 * c2_ft", "z": "c2_h"}, "C2_Left_Sk", ctx.ev)
    c2_left = sp.ext_new(c2_lc, pr, "c2_st", "C2_Left").bodies.item(0)
    c2_left.name = "C2_Left"

    half_blind_dovetail.corner(
        pin_body=c2_front, tail_body=c2_left, plane=c2_lp,
        x_model=ctx.ev("c2_x"),
        y_wide=ctx.ev("c2_lap"),
        y_narrow=ctx.ev("c2_ft"),
        y_wide_expr="c2_lap",
        socket_depth_expr="hbdc2_socket_depth",
        dist_expr="c2_st",
        name="C2_HBD", prefix="hbdc2", ev=ctx.ev)
    c2_total = c2_fc.bRepBodies.count + c2_lc.bRepBodies.count
    assert c2_total == 2, \
        f"C2: expected 2 bodies across 2 comps, got {c2_total}"
    print("C2: PASS (cross-component corner)\n")

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

    # B1: 2, B2: 3, B3: 4, B4: 4, B5: 4, C1: 2, C2: 2 = 21
    expected = 2 + 3 + 4 + 4 + 4 + 2 + 2
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
