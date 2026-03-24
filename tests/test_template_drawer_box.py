"""Test fixture for drawer box template.

Tests define_params, build (4 boards + bottom + grooves), and pattern.
Creates a simple case with 3 drawers.
"""
import adsk.core
import adsk.fusion
import math

def run(context):
    app = adsk.core.Application.get()

    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    Point3D = adsk.core.Point3D

    from helpers import sp
    from woodworking.templates import drawer_box

    ctx = sp.DesignContext(design)

    # ── Case parameters ──
    params.add("case_w", VI("24 in"), "in", "Case width")
    params.add("case_d", VI("16 in"), "in", "Case depth")
    params.add("case_h", VI("30 in"), "in", "Case height")
    params.add("board_thick", VI("0.75 in"), "in", "Case side thickness")
    params.add("back_thick", VI("0.5 in"), "in", "Case back thickness")
    params.add("top_thick", VI("0.75 in"), "in", "Case top thickness")
    params.add("bot_thick", VI("0.75 in"), "in", "Case bottom thickness")
    params.add("kick_h", VI("3 in"), "in", "Kick height")

    # ── Drawer params via template ──
    drawer_box.define_params(params, n_drawers="3",
        front_thick="0.75 in", side_thick="0.5 in",
        bottom_thick="0.25 in", gap="0.125 in",
        case_w_expr="case_w", case_d_expr="case_d")

    print(f"Drawer dims: w={ctx.ev('drawer_w')/2.54:.2f}in, "
          f"h={ctx.ev('drawer_h')/2.54:.2f}in, "
          f"d={ctx.ev('drawer_d')/2.54:.2f}in")

    # ── Build simple case (4 boards — no joinery, just context) ──
    case_occ = sp.make_comp(root, "Case")
    case_c = case_occ.component

    # Left side — spans Y×Z, sketch on YZ plane
    sk, pr = sp.sketch_rect_model(case_c, case_c.yZConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"y": "case_d", "z": "case_h"}, "CaseLeft_Sk", ctx.ev)
    cl = sp.ext_new(case_c, pr, "board_thick", "CaseLeft").bodies.item(0)
    cl.name = "Case_Left"

    # Right side
    right_pl = sp.off_plane(case_c, case_c.yZConstructionPlane,
                            "case_w - board_thick", "CaseRight_Pl")
    sk, pr = sp.sketch_rect_model(case_c, right_pl,
        ("case_w - board_thick", "0 in", "0 in"),
        {"y": "case_d", "z": "case_h"}, "CaseRight_Sk", ctx.ev)
    cr = sp.ext_new(case_c, pr, "board_thick", "CaseRight").bodies.item(0)
    cr.name = "Case_Right"

    # Bottom
    bot_pl = sp.off_plane(case_c, case_c.xYConstructionPlane,
                          "kick_h", "CaseBot_Pl")
    sk, pr = sp.sketch_rect_model(case_c, bot_pl,
        ("board_thick", "0 in", "kick_h"),
        {"x": "case_w - 2 * board_thick", "y": "case_d"}, "CaseBot_Sk", ctx.ev)
    cb = sp.ext_new(case_c, pr, "bot_thick", "CaseBot").bodies.item(0)
    cb.name = "Case_Bot"

    # Top
    top_pl = sp.off_plane(case_c, case_c.xYConstructionPlane,
                          "case_h - top_thick", "CaseTop_Pl")
    sk, pr = sp.sketch_rect_model(case_c, top_pl,
        ("board_thick", "0 in", "case_h - top_thick"),
        {"x": "case_w - 2 * board_thick", "y": "case_d"}, "CaseTop_Sk", ctx.ev)
    ct = sp.ext_new(case_c, pr, "top_thick", "CaseTop").bodies.item(0)
    ct.name = "Case_Top"

    print("Case built: 4 boards")

    # ── Build drawer template ──
    drawers_occ = sp.make_comp(root, "Drawers")
    drawers_c = drawers_occ.component

    result = drawer_box.build(drawers_c, ev=ctx.ev)
    print(f"Drawer template built: {[b.name for b in result['all_bodies']]}")

    # Verify 5 bodies in drawer component
    dr_count = drawers_c.bRepBodies.count
    print(f"Drawer component bodies: {dr_count}")
    assert dr_count == 5, f"Expected 5 drawer bodies, got {dr_count}"

    # ── Pattern for 3 drawers ──
    pat = drawer_box.pattern(drawers_c, result["all_bodies"], ev=ctx.ev)
    if pat:
        print(f"Pattern created: {pat.name}, count={int(ctx.ev('n_drawers'))}")

    # Verify body count after pattern
    dr_count_after = drawers_c.bRepBodies.count
    expected_drawer_bodies = 5 * int(ctx.ev("n_drawers"))
    print(f"Drawer bodies after pattern: {dr_count_after} (expected {expected_drawer_bodies})")

    # ── Summary ──
    total = 0
    for occ in root.occurrences:
        c = occ.component
        n = c.bRepBodies.count
        names = [c.bRepBodies.item(i).name for i in range(n)]
        print(f"  {c.name}: {n} bodies -> {names[:8]}{'...' if n > 8 else ''}")
        total += n

    expected_total = 4 + expected_drawer_bodies  # 4 case + 15 drawer
    status = "PASS" if total == expected_total else "FAIL"
    print(f"\n{status}: expected {expected_total} bodies, got {total}")

    for occ in root.occurrences:
        c = occ.component
        for sk in c.sketches:
            sk.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
