"""Test fixture for dado & rabbet patterns.

Shows how to create dados, rabbets, and panel grooves using af helpers
directly — no template needed, each is just 2 features (sketch + CUT).

  Through_Dado: 2 sides (mirror) + 2 shelves in through dados. 4 bodies.
  Rabbet: 2 sides (mirror) + 1 back panel in rabbets. 3 bodies.
  Stopped_Dado: 2 sides (mirror) + 1 shelf in stopped dado. 3 bodies.
  Panel_Groove: front + back + 2 sides (mirror) + bottom panel. 5 bodies.

Total: 4 + 3 + 3 + 5 = 15 bodies.
"""
import adsk.core
import adsk.fusion


def make_comp_at(root, name, x_cm=0.0):
    """Create a component at the given X world position."""
    xf = adsk.core.Matrix3D.create()
    if x_cm != 0.0:
        xf.setCell(0, 3, x_cm)
    occ = root.occurrences.addNewComponent(xf)
    occ.component.name = name
    return occ


def dado(comp, face, origin, size, depth_expr, body, name, ev):
    """Dado/groove/rabbet — sketch rect on face, CUT inward. 2 features."""
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    sk, _prof = sp.sketch_rect_model(comp, face, origin, size,
                                      name=f"{name}_Sk", ev=ev)
    prof = sp.smallest_profile(sk)
    return sp.ext_op(comp, prof, depth_expr, CUT, body, name, flip=True)


def run(context):
    app = adsk.core.Application.get()

    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation

    global af
    from helpers import sp

    ctx = sp.DesignContext(design)

    # ── Shared parameters ──
    params.add("side_h", VI("12 in"), "in", "Side board height")
    params.add("side_d", VI("8 in"), "in", "Side board depth")
    params.add("side_t", VI("0.75 in"), "in", "Side board thickness")
    params.add("shelf_t", VI("0.75 in"), "in", "Shelf thickness")
    params.add("back_t", VI("0.25 in"), "in", "Back panel thickness")
    params.add("inner_w", VI("10 in"), "in", "Inner width between sides")
    params.add("dado_d", VI("side_t / 3"), "in", "Dado depth")
    params.add("rab_w", VI("back_t"), "in", "Rabbet width")
    params.add("rab_d", VI("side_t / 2"), "in", "Rabbet depth")

    # ═══════════════════════════════════════════════════════════════════
    # F1: Through Dado — 2 shelves in through dados
    # ═══════════════════════════════════════════════════════════════════
    params.add("f1_shelf_z1", VI("3 in"), "in", "F1 shelf 1 Z")
    params.add("f1_shelf_z2", VI("7 in"), "in", "F1 shelf 2 Z")

    f1 = make_comp_at(root, "Through_Dado").component

    f1_mid = sp.off_plane(f1, f1.yZConstructionPlane,
                           "inner_w / 2 + side_t", "f1_XMid")

    # Left side
    _, pr = sp.sketch_rect_model(f1, f1.xZConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "side_t", "z": "side_h"}, "f1_SideL_Sk", ctx.ev)
    side_l = sp.ext_new(f1, pr, "side_d", "f1_SideL").bodies.item(0)
    side_l.name = "f1_Side_L"
    side_r = sp.mirror_body(f1, side_l, f1_mid, "f1_SideR_Mir").bodies.item(0)
    side_r.name = "f1_Side_R"

    # Shelves
    _, pr = sp.sketch_rect_model(f1, f1.xYConstructionPlane,
        ("side_t", "0 in", "f1_shelf_z1"),
        {"x": "inner_w", "y": "side_d"}, "f1_Shelf1_Sk", ctx.ev)
    shelf1 = sp.ext_new(f1, pr, "shelf_t", "f1_Shelf1").bodies.item(0)
    shelf1.name = "f1_Shelf_1"

    _, pr = sp.sketch_rect_model(f1, f1.xYConstructionPlane,
        ("side_t", "0 in", "f1_shelf_z2"),
        {"x": "inner_w", "y": "side_d"}, "f1_Shelf2_Sk", ctx.ev)
    shelf2 = sp.ext_new(f1, pr, "shelf_t", "f1_Shelf2").bodies.item(0)
    shelf2.name = "f1_Shelf_2"

    # Through dados — sketch on inner face, CUT inward.
    # Re-find face after each CUT (topology invalidates references).
    dado(f1, sp.find_face(side_l, "x", +1),
        origin=("side_t", "0 in", "f1_shelf_z1"),
        size={"y": "side_d", "z": "shelf_t"},
        depth_expr="dado_d", body=side_l,
        name="f1_Dado_L1", ev=ctx.ev)
    dado(f1, sp.find_face(side_l, "x", +1),
        origin=("side_t", "0 in", "f1_shelf_z2"),
        size={"y": "side_d", "z": "shelf_t"},
        depth_expr="dado_d", body=side_l,
        name="f1_Dado_L2", ev=ctx.ev)

    dado(f1, sp.find_face(side_r, "x", -1),
        origin=("side_t + inner_w", "0 in", "f1_shelf_z1"),
        size={"y": "side_d", "z": "shelf_t"},
        depth_expr="dado_d", body=side_r,
        name="f1_Dado_R1", ev=ctx.ev)
    dado(f1, sp.find_face(side_r, "x", -1),
        origin=("side_t + inner_w", "0 in", "f1_shelf_z2"),
        size={"y": "side_d", "z": "shelf_t"},
        depth_expr="dado_d", body=side_r,
        name="f1_Dado_R2", ev=ctx.ev)

    assert f1.bRepBodies.count == 4
    print("Through_Dado: 4 bodies — PASS")

    # ═══════════════════════════════════════════════════════════════════
    # F2: Rabbet — back panel in rabbets along back edge of sides
    # ═══════════════════════════════════════════════════════════════════
    params.add("f2_x", VI("inner_w + 2 * side_t + 3 in"), "in", "F2 X offset")

    f2 = make_comp_at(root, "Rabbet", ctx.ev("f2_x")).component

    f2_mid = sp.off_plane(f2, f2.yZConstructionPlane,
                           "inner_w / 2 + side_t", "f2_XMid")

    _, pr = sp.sketch_rect_model(f2, f2.xZConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "side_t", "z": "side_h"}, "f2_SideL_Sk", ctx.ev)
    side_l = sp.ext_new(f2, pr, "side_d", "f2_SideL").bodies.item(0)
    side_l.name = "f2_Side_L"
    side_r = sp.mirror_body(f2, side_l, f2_mid, "f2_SideR_Mir").bodies.item(0)
    side_r.name = "f2_Side_R"

    _, pr = sp.sketch_rect_model(f2, f2.xZConstructionPlane,
        ("side_t", "side_d - back_t", "0 in"),
        {"x": "inner_w", "z": "side_h"}, "f2_Back_Sk", ctx.ev)
    back = sp.ext_new(f2, pr, "back_t", "f2_Back").bodies.item(0)
    back.name = "f2_Back"

    # Rabbet — sketch on inner face, strip along back edge.
    # Creates L-shaped step: rab_w wide × rab_d deep.
    dado(f2, sp.find_face(side_l, "x", +1),
        origin=("side_t", "side_d - rab_w", "0 in"),
        size={"y": "rab_w", "z": "side_h"},
        depth_expr="rab_d", body=side_l,
        name="f2_Rab_L", ev=ctx.ev)

    dado(f2, sp.find_face(side_r, "x", -1),
        origin=("side_t + inner_w", "side_d - rab_w", "0 in"),
        size={"y": "rab_w", "z": "side_h"},
        depth_expr="rab_d", body=side_r,
        name="f2_Rab_R", ev=ctx.ev)

    assert f2.bRepBodies.count == 3
    print("Rabbet: 3 bodies — PASS")

    # ═══════════════════════════════════════════════════════════════════
    # F3: Stopped Dado — shelf dado stops 1in from front edge
    # ═══════════════════════════════════════════════════════════════════
    params.add("f3_stop", VI("1 in"), "in", "F3 stop inset from front")
    params.add("f3_shelf_z", VI("5 in"), "in", "F3 shelf Z")
    params.add("f3_x", VI("f2_x + inner_w + 2 * side_t + 3 in"), "in",
               "F3 X offset")

    f3 = make_comp_at(root, "Stopped_Dado", ctx.ev("f3_x")).component

    f3_mid = sp.off_plane(f3, f3.yZConstructionPlane,
                           "inner_w / 2 + side_t", "f3_XMid")

    _, pr = sp.sketch_rect_model(f3, f3.xZConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "side_t", "z": "side_h"}, "f3_SideL_Sk", ctx.ev)
    side_l = sp.ext_new(f3, pr, "side_d", "f3_SideL").bodies.item(0)
    side_l.name = "f3_Side_L"
    side_r = sp.mirror_body(f3, side_l, f3_mid, "f3_SideR_Mir").bodies.item(0)
    side_r.name = "f3_Side_R"

    _, pr = sp.sketch_rect_model(f3, f3.xYConstructionPlane,
        ("side_t", "f3_stop", "f3_shelf_z"),
        {"x": "inner_w", "y": "side_d - f3_stop"}, "f3_Shelf_Sk", ctx.ev)
    shelf = sp.ext_new(f3, pr, "shelf_t", "f3_Shelf").bodies.item(0)
    shelf.name = "f3_Shelf"

    # Stopped dado — same as through but rect starts at f3_stop
    dado(f3, sp.find_face(side_l, "x", +1),
        origin=("side_t", "f3_stop", "f3_shelf_z"),
        size={"y": "side_d - f3_stop", "z": "shelf_t"},
        depth_expr="dado_d", body=side_l,
        name="f3_SDado_L", ev=ctx.ev)

    dado(f3, sp.find_face(side_r, "x", -1),
        origin=("side_t + inner_w", "f3_stop", "f3_shelf_z"),
        size={"y": "side_d - f3_stop", "z": "shelf_t"},
        depth_expr="dado_d", body=side_r,
        name="f3_SDado_R", ev=ctx.ev)

    assert f3.bRepBodies.count == 3
    print("Stopped_Dado: 3 bodies — PASS")

    # ═══════════════════════════════════════════════════════════════════
    # F4: Panel Groove — bottom panel CUTs groove in 4 boards
    # ═══════════════════════════════════════════════════════════════════
    # "If it fits, it cuts" — panel overlaps boards, CUT creates groove.
    params.add("f4_box_w", VI("8 in"), "in", "F4 box width")
    params.add("f4_box_d", VI("6 in"), "in", "F4 box depth")
    params.add("f4_box_h", VI("4 in"), "in", "F4 box height")
    params.add("f4_bt", VI("0.75 in"), "in", "F4 board thickness")
    params.add("f4_pt", VI("0.25 in"), "in", "F4 panel thickness")
    params.add("f4_gd", VI("0.25 in"), "in", "F4 groove depth into boards")
    params.add("f4_gu", VI("0.25 in"), "in", "F4 groove offset from bottom")
    params.add("f4_x", VI("f3_x + inner_w + 2 * side_t + 3 in"), "in",
               "F4 X offset")

    f4 = make_comp_at(root, "Panel_Groove", ctx.ev("f4_x")).component

    f4_xmid = sp.off_plane(f4, f4.yZConstructionPlane,
                             "f4_box_w / 2", "f4_XMid")
    f4_ymid = sp.off_plane(f4, f4.xZConstructionPlane,
                             "f4_box_d / 2", "f4_YMid")

    _, pr = sp.sketch_rect_model(f4, f4.xZConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "f4_box_w", "z": "f4_box_h"}, "f4_Front_Sk", ctx.ev)
    front = sp.ext_new(f4, pr, "f4_bt", "f4_Front").bodies.item(0)
    front.name = "f4_Front"
    back = sp.mirror_body(f4, front, f4_ymid, "f4_Back_Mir").bodies.item(0)
    back.name = "f4_Back"

    left_pl = sp.off_plane(f4, f4.yZConstructionPlane, "0 in", "f4_LeftPl")
    _, pr = sp.sketch_rect_model(f4, left_pl,
        ("0 in", "f4_bt", "0 in"),
        {"y": "f4_box_d - 2 * f4_bt", "z": "f4_box_h"}, "f4_Left_Sk", ctx.ev)
    left = sp.ext_new(f4, pr, "f4_bt", "f4_Left").bodies.item(0)
    left.name = "f4_Left"
    right = sp.mirror_body(f4, left, f4_xmid, "f4_Right_Mir").bodies.item(0)
    right.name = "f4_Right"

    # Bottom panel — extends gd into all 4 boards
    bg_pl = sp.off_plane(f4, f4.xYConstructionPlane, "f4_gu", "f4_BG_Pl")
    _, pr = sp.sketch_rect_model(f4, bg_pl,
        ("f4_bt - f4_gd", "f4_bt - f4_gd", "f4_gu"),
        {"x": "f4_box_w - 2 * f4_bt + 2 * f4_gd",
         "y": "f4_box_d - 2 * f4_bt + 2 * f4_gd"},
        "f4_Bottom_Sk", ctx.ev)
    bottom = sp.ext_new(f4, pr, "f4_pt", "f4_Bottom").bodies.item(0)
    bottom.name = "f4_Bottom"

    # CUT all 4 boards with bottom panel
    for i, board in enumerate([front, back, left, right]):
        sp.combine(board, [bottom], CUT, True, f"f4_BG_{i}")

    assert f4.bRepBodies.count == 5
    print("Panel_Groove: 5 bodies — PASS")

    # ── Summary ──
    total = 0
    for occ in root.occurrences:
        c = occ.component
        n = c.bRepBodies.count
        names = [c.bRepBodies.item(i).name for i in range(n)]
        print(f"  {c.name}: {n} bodies -> {names}")
        total += n
    print(f"\n{'PASS' if total == 15 else 'FAIL'}: {total}/15 bodies")

    for occ in root.occurrences:
        c = occ.component
        for sk in c.sketches:
            sk.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
