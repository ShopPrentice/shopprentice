"""
Modern Sideboard / Buffet
=========================
60"W x 20"D x 34"H, 3 sections: 2 door compartments + center drawer.
Recessed kick base, plywood back.

Coordinate system:
  X = width (60")  Y = depth (20")  Z = height (34")
"""
import adsk.core, adsk.fusion

from helpers import sp
from woodworking.templates import dovetailed_drawer

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
        ("case_w",      "60 in",    "in"),
        ("case_d",      "20 in",    "in"),
        ("case_h",      "34 in",    "in"),
        ("board_thick", "0.75 in",  "in"),
        ("back_thick",  "0.25 in",  "in"),
        ("kick_h",      "4 in",     "in"),
        ("kick_inset",  "1 in",     "in"),
        ("top_thick",   "0.75 in",  "in"),
        ("top_overhang","1 in",     "in"),
        ("divider_thick","0.75 in", "in"),
        ("door_thick",  "0.75 in",  "in"),
        ("door_gap",    "0.0625 in","in"),
        ("drawer_gap",  "0.0625 in","in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    for pname, expr, unit in [
        ("inner_w",    "case_w - 2 * board_thick",                   "in"),
        ("inner_h",    "case_h - kick_h - board_thick - top_thick",  "in"),
        ("section_w",  "(inner_w - 2 * divider_thick) / 3",         "in"),
        ("door_w",     "section_w - 2 * door_gap",                  "in"),
        ("door_h",     "inner_h - 2 * door_gap",                    "in"),
        ("mid_x",      "case_w / 2",                                 "in"),
        ("bottom_z",   "kick_h",                                     "in"),
        ("top_z",      "case_h - top_thick",                         "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    # Drawer params
    dovetailed_drawer.define_params(params, prefix="dd",
        drawer_w="section_w - 2 * drawer_gap",
        drawer_d="case_d - back_thick - 2 * drawer_gap",
        drawer_h="inner_h - 2 * drawer_gap",
        front_thick="0.75 in", side_thick="0.5 in",
        bottom_thick="0.25 in",
        bg_depth="0.25 in", bg_up="0.25 in",
        dt_angle="8 deg", dt_tail_w="0.75 in",
        front_tail_count="4", back_tail_count="4",
        x_offset="board_thick + section_w + divider_thick + drawer_gap",
        z_offset="kick_h + board_thick + drawer_gap")

    # ==============================================================
    #  BODY LOOKUP (for body-relative references / validate_deps)
    # ==============================================================
    def find_body(name, comp=None):
        c = comp or root
        for i in range(c.bRepBodies.count):
            if c.bRepBodies.item(i).name == name:
                return c.bRepBodies.item(i)
        for j in range(c.occurrences.count):
            r = find_body(name, c.occurrences.item(j).component)
            if r:
                return r
        return None

    print(">>> Parameters done")

    case_occ   = sp.make_comp(root, "Case")
    top_occ    = sp.make_comp(root, "Top")
    kick_occ   = sp.make_comp(root, "Kick")
    door_occ   = sp.make_comp(root, "Doors")
    drawer_occ = sp.make_comp(root, "Drawer")
    back_occ   = sp.make_comp(root, "Back")

    case_c   = case_occ.component
    top_c    = top_occ.component
    kick_c   = kick_occ.component
    door_c   = door_occ.component
    drawer_c = drawer_occ.component
    back_c   = back_occ.component

    # ==== CASE: sides + bottom + 2 dividers ====
    # Left side
    _, pr = sp.sketch_rect_model(case_c, case_c.yZConstructionPlane,
        ("0 in", "0 in", "kick_h"),
        {"y": "case_d", "z": "case_h - kick_h - top_thick"}, "LeftSide_Sk", ev)
    ls_ext = sp.ext_new(case_c, pr, "board_thick", "LeftSide")
    ls_ext.bodies.item(0).name = "Side_Left"

    # Body-relative ref: Side_Right mirrors Side_Left
    ref_side_left = find_body("Side_Left")
    ref_side_left_bb = ref_side_left.boundingBox

    x_mid = sp.off_plane(case_c, case_c.yZConstructionPlane, "mid_x", "XMid")
    sp.mirror_feats(case_c, [ls_ext], x_mid, "RightMir").bodies.item(0).name = "Side_Right"

    # Bottom board
    bot_pl = sp.off_plane(case_c, case_c.xYConstructionPlane, "kick_h", "Bot_Pl")
    _, pr = sp.sketch_rect_model(case_c, bot_pl,
        ("board_thick", "0 in", "kick_h"),
        {"x": "inner_w", "y": "case_d"}, "Bottom_Sk", ev)
    sp.ext_new(case_c, pr, "board_thick", "BottomBoard").bodies.item(0).name = "Bottom"

    # Body-relative ref: Div_Left sits above Bottom
    ref_bottom = find_body("Bottom")
    ref_bottom_bb = ref_bottom.boundingBox

    # Left divider
    div_l_pl = sp.off_plane(case_c, case_c.yZConstructionPlane,
        "board_thick + section_w", "DivL_Pl")
    _, pr = sp.sketch_rect_model(case_c, div_l_pl,
        ("board_thick + section_w", "0 in", "kick_h + board_thick"),
        {"y": "case_d - back_thick", "z": "inner_h"}, "DivL_Sk", ev)
    sp.ext_new(case_c, pr, "divider_thick", "DivLeft").bodies.item(0).name = "Div_Left"

    # Body-relative ref: Div_Right mirrors Div_Left
    ref_div_left = find_body("Div_Left")
    ref_div_left_bb = ref_div_left.boundingBox

    # Right divider: mirror
    sp.mirror_feats(case_c, [case_c.features.extrudeFeatures.itemByName("DivLeft")],
                     x_mid, "DivRightMir").bodies.item(0).name = "Div_Right"

    print(">>> Case: 5 bodies (2 sides, bottom, 2 dividers)")

    # ==== TOP ====
    # Body-relative ref: Top sits on Side_Right (and Side_Left)
    ref_side_right = find_body("Side_Right")
    ref_side_right_bb = ref_side_right.boundingBox

    _, pr = sp.sketch_rect_model(top_c, top_c.xYConstructionPlane,
        ("-top_overhang", "-top_overhang", "top_z"),
        {"x": "case_w + 2 * top_overhang", "y": "case_d + top_overhang"},
        "Top_Sk", ev)
    top_pl = sp.off_plane(top_c, top_c.xYConstructionPlane, "top_z", "TopPl")
    _, pr = sp.sketch_rect_model(top_c, top_pl,
        ("-top_overhang", "-top_overhang", "top_z"),
        {"x": "case_w + 2 * top_overhang", "y": "case_d + top_overhang"},
        "Top_Sk2", ev)
    sp.ext_new(top_c, pr, "top_thick", "TopBoard").bodies.item(0).name = "Top"
    print(">>> Top: 1")

    # ==== KICK ====
    _, pr = sp.sketch_rect_model(kick_c, kick_c.xZConstructionPlane,
        ("kick_inset", "kick_inset", "0 in"),
        {"x": "case_w - 2 * kick_inset", "z": "kick_h"}, "KickFront_Sk", ev)
    kf_ext = sp.ext_new(kick_c, pr, "board_thick", "KickFront")
    kf_ext.bodies.item(0).name = "Kick_Front"

    # Body-relative ref: Kick_Back mirrors Kick_Front
    ref_kick_front = find_body("Kick_Front")
    ref_kick_front_bb = ref_kick_front.boundingBox

    k_ymid = sp.off_plane(kick_c, kick_c.xZConstructionPlane, "case_d / 2", "KYMid")
    sp.mirror_feats(kick_c, [kf_ext], k_ymid, "KickBackMir").bodies.item(0).name = "Kick_Back"

    _, pr = sp.sketch_rect_model(kick_c, kick_c.yZConstructionPlane,
        ("kick_inset", "kick_inset + board_thick", "0 in"),
        {"y": "case_d - 2 * kick_inset - 2 * board_thick", "z": "kick_h"},
        "KickLeft_Sk", ev)
    kl_ext = sp.ext_new(kick_c, pr, "board_thick", "KickLeft")
    kl_ext.bodies.item(0).name = "Kick_Left"

    # Body-relative ref: Kick_Right mirrors Kick_Left
    ref_kick_left = find_body("Kick_Left")
    ref_kick_left_bb = ref_kick_left.boundingBox

    k_xmid = sp.off_plane(kick_c, kick_c.yZConstructionPlane, "mid_x", "KXMid")
    sp.mirror_feats(kick_c, [kl_ext], k_xmid, "KickRightMir").bodies.item(0).name = "Kick_Right"
    print(">>> Kick: 4")

    # ==== DOORS (2 — left and right sections) ====
    _, pr = sp.sketch_rect_model(door_c, door_c.xZConstructionPlane,
        ("board_thick + door_gap", "0 in", "kick_h + board_thick + door_gap"),
        {"x": "door_w", "z": "door_h"}, "DoorL_Sk", ev)
    dl_ext = sp.ext_new(door_c, pr, "door_thick", "DoorLeft")
    dl_ext.bodies.item(0).name = "Door_Left"

    # Body-relative ref: Door_Right positioned relative to Div_Right
    ref_div_right = find_body("Div_Right")
    ref_div_right_bb = ref_div_right.boundingBox

    d_xmid = sp.off_plane(door_c, door_c.yZConstructionPlane, "mid_x", "DXMid")
    sp.mirror_feats(door_c, [dl_ext], d_xmid, "DoorRightMir").bodies.item(0).name = "Door_Right"
    print(">>> Doors: 2")

    # ==== DRAWER (center section) ====
    dd_result = dovetailed_drawer.build(drawer_c, prefix="dd", ev=ev)

    # Body-relative ref: dd_Back/dd_Left/dd_Right/dd_Bottom relative to dd_Front
    ref_dd_front = find_body("dd_Front")
    ref_dd_front_bb = ref_dd_front.boundingBox

    # Body-relative ref: dd_Right positioned relative to dd_Left
    ref_dd_left = find_body("dd_Left")
    ref_dd_left_bb = ref_dd_left.boundingBox

    print(">>> Drawer: %d" % len(dd_result["all_bodies"]))

    # ==== BACK PANEL ====
    _, pr = sp.sketch_rect_model(back_c, back_c.xZConstructionPlane,
        ("board_thick", "case_d - back_thick", "kick_h + board_thick"),
        {"x": "inner_w", "z": "inner_h"}, "Back_Sk", ev)
    sp.ext_new(back_c, pr, "back_thick", "BackPanel").bodies.item(0).name = "BackPanel"
    print(">>> Back: 1")

    # ==== EPILOGUE ====
    for comp in [case_c, top_c, kick_c, door_c, drawer_c, back_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False

    for cn, c in [("Case", case_c), ("Top", top_c), ("Kick", kick_c),
                   ("Doors", door_c), ("Drawer", drawer_c), ("Back", back_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{cn}: {len(names)} bodies -> {names}")

    sp.apply_appearance("white oak")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
