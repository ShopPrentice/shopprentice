"""Test fixture for half-blind dovetail joint template.

Tests define_params and box() with 4 configurations:
  B1: 1-corner half-blind (2 boards: front + left)
  B2: 2-corner half-blind (3 boards: front + left + right)
  B3: 4-corner half-blind (4 boards)
  B4: 4-corner half-blind, different dimensions

Layout: 2x2 grid
  Row 0 (y=0):      B1 (8x6),   B2 (10x5)
  Row 1 (y=offset):  B3 (8x6),   B4 (6x4)
"""
import adsk.core
import adsk.fusion


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
    from helpers import af
    from helpers.templates import half_blind_dovetail

    if lap_expr is None:
        lap_expr = f"{hbd_prefix}_lap"

    occ = af.make_comp(root, prefix)
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
        front_sk_pl = af.off_plane(comp, comp.xZConstructionPlane,
                                    y_off_expr, f"{prefix}_FrontYPl")

    sk, pr = af.sketch_rect_model(comp, front_sk_pl,
        (x_off_expr, front_y_expr, "0 in"),
        {"x": l_expr, "z": h_expr}, f"{prefix}_Front_Sk", ev)
    front = af.ext_new(comp, pr, pin_t_expr,
                       f"{prefix}_Front").bodies.item(0)
    front.name = f"{prefix}_Front"

    # Back (pin board, only for 4-corner)
    back = None
    if corners == 4:
        back_pl = af.off_plane(comp, comp.xZConstructionPlane,
                               back_y_expr, f"{prefix}_Back_Pl")
        sk, pr = af.sketch_rect_model(comp, back_pl,
            (x_off_expr, back_y_expr, "0 in"),
            {"x": l_expr, "z": h_expr}, f"{prefix}_Back_Sk", ev)
        back = af.ext_new(comp, pr, pin_t_expr,
                          f"{prefix}_Back").bodies.item(0)
        back.name = f"{prefix}_Back"

    # Midplanes
    x_mid_expr = (f"{x_off_expr} + {l_expr} / 2"
                  if ox != 0.0 else f"{l_expr} / 2")
    y_mid_expr = (f"{y_off_expr} + {w_expr} / 2"
                  if oy != 0.0 else f"{w_expr} / 2")

    x_mid = af.off_plane(comp, comp.yZConstructionPlane,
                          x_mid_expr, f"{prefix}_XMid")
    y_mid = af.off_plane(comp, comp.xZConstructionPlane,
                          y_mid_expr, f"{prefix}_YMid")

    # Left (tail board, thinner, narrower by pin_thick on each end)
    if ox == 0.0:
        left_pl = comp.yZConstructionPlane
    else:
        left_pl = af.off_plane(comp, comp.yZConstructionPlane,
                               x_off_expr, f"{prefix}_Left_Pl")

    sk, pr = af.sketch_rect_model(comp, left_pl,
        (x_off_expr, tail_y_expr, "0 in"),
        {"y": tail_w_expr, "z": h_expr}, f"{prefix}_Left_Sk", ev)
    left = af.ext_new(comp, pr, side_t_expr,
                      f"{prefix}_Left").bodies.item(0)
    left.name = f"{prefix}_Left"

    # Right (tail board via mirror, only for 2+ corners)
    right = None
    if corners >= 2:
        right_mir = af.mirror_body(comp, left, x_mid,
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

    while True:
        doc = app.activeDocument
        if doc and not doc.isSaved:
            doc.close(False)
        else:
            break
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString

    from helpers import af
    from helpers.templates import half_blind_dovetail

    ctx = af.DesignContext(design)

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

    # B1: 2, B2: 3, B3: 4, B4: 4 = 13
    expected = 2 + 3 + 4 + 4
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
