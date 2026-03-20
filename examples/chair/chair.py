"""
Modern Dining Chair
===================
18"W x 16"D seat, 18"H seat height, 34"H total (back).
4 legs (back legs are taller, straight — not angled for simplicity),
4 aprons, seat board, back rest rail.

Coordinate system:
  X = width (18")  Y = depth (16")  Z = height (34")
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
        ("seat_w",      "18 in",    "in"),
        ("seat_d",      "16 in",    "in"),
        ("seat_h",      "18 in",    "in"),
        ("back_h",      "34 in",    "in"),
        ("seat_thick",  "0.75 in",  "in"),
        ("leg_size",    "1.5 in",   "in"),
        ("apron_h",     "3 in",     "in"),
        ("apron_thick", "0.75 in",  "in"),
        ("backrest_h",  "4 in",     "in"),
        ("backrest_thick","0.75 in","in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    for pname, expr, unit in [
        ("front_leg_h",  "seat_h - seat_thick",                       "in"),
        ("back_leg_h",   "back_h",                                     "in"),
        ("apron_z",      "seat_h - seat_thick - apron_h",              "in"),
        ("long_apron_l", "seat_d - 2 * leg_size",                     "in"),
        ("short_apron_l","seat_w - 2 * leg_size",                     "in"),
        ("backrest_z",   "seat_h + 4 in",                             "in"),  # back rest above seat
        ("mid_x",        "seat_w / 2",                                 "in"),
        ("mid_y",        "seat_d / 2",                                 "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    print(">>> Parameters done")

    leg_occ   = af.make_comp(root, "Legs")
    apron_occ = af.make_comp(root, "Aprons")
    seat_occ  = af.make_comp(root, "Seat")
    back_occ  = af.make_comp(root, "Back")

    leg_c   = leg_occ.component
    apron_c = apron_occ.component
    seat_c  = seat_occ.component
    back_c  = back_occ.component

    # ==== LEGS ====
    # Front-left (short)
    _, pr = af.sketch_rect_model(leg_c, leg_c.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_size", "y": "leg_size"}, "LegFL_Sk", ev)
    fl_ext = af.ext_new(leg_c, pr, "front_leg_h", "LegFL")
    fl_ext.bodies.item(0).name = "Leg_FL"

    l_xmid = af.off_plane(leg_c, leg_c.yZConstructionPlane, "mid_x", "LXMid")
    af.mirror_body(leg_c, fl_ext.bodies.item(0), l_xmid, "LegFR").bodies.item(0).name = "Leg_FR"

    # Back-left (tall — extends above seat for back)
    _, pr = af.sketch_rect_model(leg_c, leg_c.xYConstructionPlane,
        ("0 in", "seat_d - leg_size", "0 in"),
        {"x": "leg_size", "y": "leg_size"}, "LegBL_Sk", ev)
    bl_ext = af.ext_new(leg_c, pr, "back_leg_h", "LegBL")
    bl_ext.bodies.item(0).name = "Leg_BL"

    af.mirror_body(leg_c, bl_ext.bodies.item(0), l_xmid, "LegBR").bodies.item(0).name = "Leg_BR"
    print(">>> Legs: 4 (front short, back tall)")

    # ==== APRONS ====
    az_pl = af.off_plane(apron_c, apron_c.xYConstructionPlane, "apron_z", "AZ_Pl")

    # Front apron
    _, pr = af.sketch_rect_model(apron_c, az_pl,
        ("leg_size", "0 in", "apron_z"),
        {"x": "short_apron_l", "y": "apron_thick"}, "FrontApron_Sk", ev)
    af.ext_new(apron_c, pr, "apron_h", "FrontApron").bodies.item(0).name = "Apron_Front"

    # Back apron
    _, pr = af.sketch_rect_model(apron_c, az_pl,
        ("leg_size", "seat_d - leg_size - apron_thick", "apron_z"),
        {"x": "short_apron_l", "y": "apron_thick"}, "BackApron_Sk", ev)
    af.ext_new(apron_c, pr, "apron_h", "BackApron").bodies.item(0).name = "Apron_Back"

    # Left side apron
    _, pr = af.sketch_rect_model(apron_c, az_pl,
        ("0 in", "leg_size", "apron_z"),
        {"x": "apron_thick", "y": "long_apron_l"}, "LeftApron_Sk", ev)
    la_ext = af.ext_new(apron_c, pr, "apron_h", "LeftApron")
    la_ext.bodies.item(0).name = "Apron_Left"

    a_xmid = af.off_plane(apron_c, apron_c.yZConstructionPlane, "mid_x", "AXMid")
    af.mirror_feats(apron_c, [la_ext], a_xmid, "RightApronMir").bodies.item(0).name = "Apron_Right"
    print(">>> Aprons: 4")

    # ==== SEAT ====
    seat_pl = af.off_plane(seat_c, seat_c.xYConstructionPlane, "front_leg_h", "SeatPl")
    _, pr = af.sketch_rect_model(seat_c, seat_pl,
        ("0 in", "0 in", "front_leg_h"),
        {"x": "seat_w", "y": "seat_d"}, "Seat_Sk", ev)
    af.ext_new(seat_c, pr, "seat_thick", "SeatBoard").bodies.item(0).name = "Seat"
    print(">>> Seat: 1")

    # ==== BACK REST ====
    # Horizontal rail between back legs above the seat
    _, pr = af.sketch_rect_model(back_c, back_c.xZConstructionPlane,
        ("leg_size", "seat_d - leg_size", "backrest_z"),
        {"x": "short_apron_l", "z": "backrest_h"}, "BackRest_Sk", ev)
    af.ext_new(back_c, pr, "backrest_thick", "BackRest").bodies.item(0).name = "BackRest"

    # Upper back rail (near top of back legs)
    _, pr = af.sketch_rect_model(back_c, back_c.xZConstructionPlane,
        ("leg_size", "seat_d - leg_size", "back_h - leg_size - backrest_h"),
        {"x": "short_apron_l", "z": "backrest_h"}, "TopRail_Sk", ev)
    af.ext_new(back_c, pr, "backrest_thick", "TopRail").bodies.item(0).name = "TopRail"
    print(">>> Back: 2 rails")

    # ==== EPILOGUE ====
    for comp in [leg_c, apron_c, seat_c, back_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False

    for cn, c in [("Legs", leg_c), ("Aprons", apron_c),
                   ("Seat", seat_c), ("Back", back_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{cn}: {len(names)} bodies -> {names}")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
