"""
Modern Wardrobe / Armoire
=========================
42"W x 24"D x 78"H, 2 full-height doors, hanging rod, shelf.

Coordinate system:
  X = width (42")  Y = depth (24")  Z = height (78")
"""
import adsk.core, adsk.fusion

from helpers import af

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    for pname, expr, unit in [
        ("case_w",      "42 in",    "in"),
        ("case_d",      "24 in",    "in"),
        ("case_h",      "78 in",    "in"),
        ("board_thick", "0.75 in",  "in"),
        ("back_thick",  "0.25 in",  "in"),
        ("kick_h",      "4 in",     "in"),
        ("kick_inset",  "1 in",     "in"),
        ("door_thick",  "0.75 in",  "in"),
        ("door_gap",    "0.0625 in","in"),
        ("shelf_thick", "0.75 in",  "in"),
        ("rod_dia",     "1.25 in",  "in"),
        ("rod_z",       "63 in",    "in"),  # rod height from floor
    ]:
        params.add(pname, VI(expr), unit, "")

    for pname, expr, unit in [
        ("inner_w",    "case_w - 2 * board_thick",                   "in"),
        ("inner_h",    "case_h - kick_h - 2 * board_thick",         "in"),
        ("door_w",     "(inner_w - 3 * door_gap) / 2",              "in"),
        ("door_h",     "inner_h - 2 * door_gap",                    "in"),
        ("mid_x",      "case_w / 2",                                 "in"),
        ("shelf_z",    "case_h - board_thick - shelf_thick - 6 in", "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    print(">>> Parameters done")

    case_occ = af.make_comp(root, "Case")
    door_occ = af.make_comp(root, "Doors")
    kick_occ = af.make_comp(root, "Kick")
    int_occ  = af.make_comp(root, "Interior")
    back_occ = af.make_comp(root, "Back")

    case_c = case_occ.component
    door_c = door_occ.component
    kick_c = kick_occ.component
    int_c  = int_occ.component
    back_c = back_occ.component

    # ==== CASE ====
    _, pr = af.sketch_rect_model(case_c, case_c.yZConstructionPlane,
        ("0 in", "0 in", "kick_h"),
        {"y": "case_d", "z": "case_h - kick_h"}, "LeftSide_Sk", ev)
    ls_ext = af.ext_new(case_c, pr, "board_thick", "LeftSide")
    ls_ext.bodies.item(0).name = "Side_Left"

    x_mid = af.off_plane(case_c, case_c.yZConstructionPlane, "mid_x", "XMid")
    af.mirror_feats(case_c, [ls_ext], x_mid, "RightMir").bodies.item(0).name = "Side_Right"

    # Top
    top_pl = af.off_plane(case_c, case_c.xYConstructionPlane, "case_h - board_thick", "TopPl")
    _, pr = af.sketch_rect_model(case_c, top_pl,
        ("board_thick", "0 in", "case_h - board_thick"),
        {"x": "inner_w", "y": "case_d"}, "Top_Sk", ev)
    af.ext_new(case_c, pr, "board_thick", "TopBoard").bodies.item(0).name = "Top"

    # Bottom
    bot_pl = af.off_plane(case_c, case_c.xYConstructionPlane, "kick_h", "BotPl")
    _, pr = af.sketch_rect_model(case_c, bot_pl,
        ("board_thick", "0 in", "kick_h"),
        {"x": "inner_w", "y": "case_d"}, "Bot_Sk", ev)
    af.ext_new(case_c, pr, "board_thick", "BotBoard").bodies.item(0).name = "Bottom"
    print(">>> Case: 4")

    # ==== KICK ====
    _, pr = af.sketch_rect_model(kick_c, kick_c.xZConstructionPlane,
        ("kick_inset", "kick_inset", "0 in"),
        {"x": "case_w - 2 * kick_inset", "z": "kick_h"}, "KickF_Sk", ev)
    kf_ext = af.ext_new(kick_c, pr, "board_thick", "KickFront")
    kf_ext.bodies.item(0).name = "Kick_Front"

    k_ymid = af.off_plane(kick_c, kick_c.xZConstructionPlane, "case_d / 2", "KYMid")
    af.mirror_feats(kick_c, [kf_ext], k_ymid, "KickBackMir").bodies.item(0).name = "Kick_Back"

    _, pr = af.sketch_rect_model(kick_c, kick_c.yZConstructionPlane,
        ("kick_inset", "kick_inset + board_thick", "0 in"),
        {"y": "case_d - 2 * kick_inset - 2 * board_thick", "z": "kick_h"}, "KickL_Sk", ev)
    kl_ext = af.ext_new(kick_c, pr, "board_thick", "KickLeft")
    kl_ext.bodies.item(0).name = "Kick_Left"

    k_xmid = af.off_plane(kick_c, kick_c.yZConstructionPlane, "mid_x", "KXMid")
    af.mirror_feats(kick_c, [kl_ext], k_xmid, "KickRightMir").bodies.item(0).name = "Kick_Right"
    print(">>> Kick: 4")

    # ==== DOORS ====
    _, pr = af.sketch_rect_model(door_c, door_c.xZConstructionPlane,
        ("board_thick + door_gap", "0 in", "kick_h + board_thick + door_gap"),
        {"x": "door_w", "z": "door_h"}, "DoorL_Sk", ev)
    dl_ext = af.ext_new(door_c, pr, "door_thick", "DoorLeft")
    dl_ext.bodies.item(0).name = "Door_Left"

    d_xmid = af.off_plane(door_c, door_c.yZConstructionPlane, "mid_x", "DXMid")
    af.mirror_feats(door_c, [dl_ext], d_xmid, "DoorRightMir").bodies.item(0).name = "Door_Right"
    print(">>> Doors: 2")

    # ==== INTERIOR: shelf + hanging rod (rod as rectangular bar placeholder) ====
    shelf_pl = af.off_plane(int_c, int_c.xYConstructionPlane, "shelf_z", "ShelfPl")
    _, pr = af.sketch_rect_model(int_c, shelf_pl,
        ("board_thick", "0 in", "shelf_z"),
        {"x": "inner_w", "y": "case_d - back_thick - board_thick"}, "Shelf_Sk", ev)
    af.ext_new(int_c, pr, "shelf_thick", "ShelfBoard").bodies.item(0).name = "Shelf"

    # Hanging rod (simplified as rectangular bar)
    rod_pl = af.off_plane(int_c, int_c.xYConstructionPlane, "rod_z", "RodPl")
    _, pr = af.sketch_rect_model(int_c, rod_pl,
        ("board_thick", "case_d / 2 - rod_dia / 2", "rod_z"),
        {"x": "inner_w", "y": "rod_dia"}, "Rod_Sk", ev)
    af.ext_new(int_c, pr, "rod_dia", "HangingRod").bodies.item(0).name = "Rod"
    print(">>> Interior: shelf + rod")

    # ==== BACK ====
    _, pr = af.sketch_rect_model(back_c, back_c.xZConstructionPlane,
        ("board_thick", "case_d - back_thick", "kick_h + board_thick"),
        {"x": "inner_w", "z": "inner_h"}, "Back_Sk", ev)
    af.ext_new(back_c, pr, "back_thick", "BackPanel").bodies.item(0).name = "BackPanel"
    print(">>> Back: 1")

    # ==== EPILOGUE ====
    for comp in [case_c, door_c, kick_c, int_c, back_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False

    for cn, c in [("Case", case_c), ("Kick", kick_c), ("Doors", door_c),
                   ("Interior", int_c), ("Back", back_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{cn}: {len(names)} bodies -> {names}")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
