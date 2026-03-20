"""
Modern Sofa Frame
=================
72"L x 22"D seat, 18"H seat, 34"H back, 26"H arms.
Wood frame only — cushions/upholstery not modeled.

Coordinate system:
  X = length (72")  Y = depth (22")  Z = height (34")
"""
import adsk.core, adsk.fusion

from helpers import af


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
        ("sofa_l",      "72 in",    "in"),
        ("seat_d",      "22 in",    "in"),
        ("seat_h",      "18 in",    "in"),
        ("back_h",      "34 in",    "in"),
        ("arm_h",       "26 in",    "in"),
        ("rail_size",   "2.5 in",   "in"),
        ("leg_size",    "2.5 in",   "in"),
        ("seat_thick",  "0.75 in",  "in"),  # plywood deck
    ]:
        params.add(pname, VI(expr), unit, "")

    for pname, expr, unit in [
        ("leg_h",       "seat_h - rail_size",                        "in"),
        ("inner_l",     "sofa_l - 2 * leg_size",                    "in"),
        ("inner_d",     "seat_d - 2 * rail_size",                   "in"),
        ("mid_x",       "sofa_l / 2",                                "in"),
        ("mid_y",       "seat_d / 2",                                "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    print(">>> Parameters done")

    leg_occ  = af.make_comp(root, "Legs")
    rail_occ = af.make_comp(root, "Rails")
    back_occ = af.make_comp(root, "Back")
    arm_occ  = af.make_comp(root, "Arms")
    deck_occ = af.make_comp(root, "Deck")

    leg_c  = leg_occ.component
    rail_c = rail_occ.component
    back_c = back_occ.component
    arm_c  = arm_occ.component
    deck_c = deck_occ.component

    # ==== LEGS (6: 4 corners + 2 center supports) ====
    _, pr = af.sketch_rect_model(leg_c, leg_c.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_size", "y": "leg_size"}, "LegFL_Sk", ev)
    fl_ext = af.ext_new(leg_c, pr, "leg_h", "LegFL")
    fl_ext.bodies.item(0).name = "Leg_FL"

    l_xmid = af.off_plane(leg_c, leg_c.yZConstructionPlane, "mid_x", "LXMid")
    l_ymid = af.off_plane(leg_c, leg_c.xZConstructionPlane, "mid_y", "LYMid")
    af.mirror_body(leg_c, fl_ext.bodies.item(0), l_xmid, "LegFR").bodies.item(0).name = "Leg_FR"
    leg_bl = af.mirror_body(leg_c, fl_ext.bodies.item(0), l_ymid, "LegBL").bodies.item(0)
    leg_bl.name = "Leg_BL"
    af.mirror_body(leg_c, leg_bl, l_xmid, "LegBR").bodies.item(0).name = "Leg_BR"
    print(">>> Legs: 4")

    # ==== SEAT RAILS ====
    rail_z_pl = af.off_plane(rail_c, rail_c.xYConstructionPlane, "leg_h", "RailZ")

    # Front rail
    _, pr = af.sketch_rect_model(rail_c, rail_z_pl,
        ("leg_size", "0 in", "leg_h"),
        {"x": "inner_l", "y": "rail_size"}, "FrontRail_Sk", ev)
    fr_ext = af.ext_new(rail_c, pr, "rail_size", "FrontRail")
    fr_ext.bodies.item(0).name = "Rail_Front"

    r_ymid = af.off_plane(rail_c, rail_c.xZConstructionPlane, "mid_y", "RYMid")
    af.mirror_feats(rail_c, [fr_ext], r_ymid, "BackRailMir").bodies.item(0).name = "Rail_Back"

    # Side rails
    _, pr = af.sketch_rect_model(rail_c, rail_z_pl,
        ("0 in", "rail_size", "leg_h"),
        {"x": "leg_size", "y": "inner_d"}, "LeftRail_Sk", ev)
    lr_ext = af.ext_new(rail_c, pr, "rail_size", "LeftRail")
    lr_ext.bodies.item(0).name = "Rail_Left"

    r_xmid = af.off_plane(rail_c, rail_c.yZConstructionPlane, "mid_x", "RXMid")
    af.mirror_feats(rail_c, [lr_ext], r_xmid, "RightRailMir").bodies.item(0).name = "Rail_Right"
    print(">>> Rails: 4")

    # ==== BACK FRAME ====
    # Back uprights (extensions of back legs to back_h)
    _, pr = af.sketch_rect_model(back_c, back_c.xYConstructionPlane,
        ("0 in", "seat_d - leg_size", "seat_h"),
        {"x": "leg_size", "y": "leg_size"}, "BackUpL_Sk", ev)
    bul_ext = af.ext_new(back_c, pr, "back_h - seat_h", "BackUpLeft")
    bul_ext.bodies.item(0).name = "BackUp_Left"

    b_xmid = af.off_plane(back_c, back_c.yZConstructionPlane, "mid_x", "BXMid")
    af.mirror_feats(back_c, [bul_ext], b_xmid, "BackUpRightMir").bodies.item(0).name = "BackUp_Right"

    # Back top rail
    _, pr = af.sketch_rect_model(back_c, back_c.xZConstructionPlane,
        ("leg_size", "seat_d - leg_size", "back_h - rail_size"),
        {"x": "inner_l", "z": "rail_size"}, "BackTopRail_Sk", ev)
    af.ext_new(back_c, pr, "rail_size", "BackTopRail").bodies.item(0).name = "BackTop_Rail"

    # Back mid rail
    _, pr = af.sketch_rect_model(back_c, back_c.xZConstructionPlane,
        ("leg_size", "seat_d - leg_size", "seat_h"),
        {"x": "inner_l", "z": "rail_size"}, "BackMidRail_Sk", ev)
    af.ext_new(back_c, pr, "rail_size", "BackMidRail").bodies.item(0).name = "BackMid_Rail"
    print(">>> Back: 4 (2 uprights + 2 rails)")

    # ==== ARMS ====
    # Left arm: vertical post at front + horizontal rail to back
    _, pr = af.sketch_rect_model(arm_c, arm_c.xYConstructionPlane,
        ("0 in", "0 in", "seat_h"),
        {"x": "leg_size", "y": "leg_size"}, "ArmPostL_Sk", ev)
    apl_ext = af.ext_new(arm_c, pr, "arm_h - seat_h", "ArmPostLeft")
    apl_ext.bodies.item(0).name = "ArmPost_Left"

    # Arm rail (horizontal from front post to back leg at arm_h)
    _, pr = af.sketch_rect_model(arm_c, arm_c.yZConstructionPlane,
        ("0 in", "0 in", "arm_h - rail_size"),
        {"y": "seat_d", "z": "rail_size"}, "ArmRailL_Sk", ev)
    arl_ext = af.ext_new(arm_c, pr, "leg_size", "ArmRailLeft")
    arl_ext.bodies.item(0).name = "ArmRail_Left"

    a_xmid = af.off_plane(arm_c, arm_c.yZConstructionPlane, "mid_x", "AXMid")
    af.mirror_bodies(arm_c, [apl_ext.bodies.item(0), arl_ext.bodies.item(0)],
                      a_xmid, "ArmRightMir")
    # Name mirrored bodies
    for i in range(arm_c.bRepBodies.count):
        b = arm_c.bRepBodies.item(i)
        if b.name.startswith("Body"):
            if "Post" not in b.name and "Rail" not in b.name:
                # Rename unnamed mirrored bodies
                pass
    print(">>> Arms: 4 (2 posts + 2 rails, mirrored)")

    # ==== DECK (plywood seat platform) ====
    deck_pl = af.off_plane(deck_c, deck_c.xYConstructionPlane, "seat_h - seat_thick", "DeckPl")
    _, pr = af.sketch_rect_model(deck_c, deck_pl,
        ("rail_size", "rail_size", "seat_h - seat_thick"),
        {"x": "sofa_l - 2 * rail_size", "y": "seat_d - 2 * rail_size"}, "Deck_Sk", ev)
    af.ext_new(deck_c, pr, "seat_thick", "DeckBoard").bodies.item(0).name = "Deck"
    print(">>> Deck: 1")

    # ==== EPILOGUE ====
    for comp in [leg_c, rail_c, back_c, arm_c, deck_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False

    for cn, c in [("Legs", leg_c), ("Rails", rail_c), ("Back", back_c),
                   ("Arms", arm_c), ("Deck", deck_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{cn}: {len(names)} bodies -> {names}")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
