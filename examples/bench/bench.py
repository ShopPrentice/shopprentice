"""
Modern Entryway Bench
=====================
48"L x 14"W x 18"H, 1.5" thick seat, 2" square legs.
Short aprons under seat, stretchers at lower height.

Coordinate system:
  X = length (48")  Y = width (14")  Z = height (18")

Components:
  Legs    — 4 square legs at corners
  Aprons  — 2 short (left/right) + 2 long (front/back)
  Seat    — solid thick board
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

    # ==============================================================
    #  PARAMETERS
    # ==============================================================
    for pname, expr, unit in [
        ("bench_l",     "48 in",   "in"),
        ("bench_w",     "14 in",   "in"),
        ("seat_h",      "18 in",   "in"),
        ("seat_thick",  "1.5 in",  "in"),
        ("leg_size",    "2 in",    "in"),
        ("apron_h",     "3 in",    "in"),
        ("apron_thick", "0.75 in", "in"),
        ("stretcher_h", "1.5 in",  "in"),
        ("stretcher_thick", "0.75 in", "in"),
        ("stretcher_z", "4 in",    "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    for pname, expr, unit in [
        ("leg_h",         "seat_h - seat_thick",                    "in"),
        ("apron_z",       "seat_h - seat_thick - apron_h",          "in"),
        ("long_apron_l",  "bench_l - 2 * leg_size",                 "in"),
        ("short_apron_l", "bench_w - 2 * leg_size",                 "in"),
        ("long_str_l",    "bench_l - 2 * leg_size",                 "in"),
        ("short_str_l",   "bench_w - 2 * leg_size",                 "in"),
        ("mid_x",         "bench_l / 2",                             "in"),
        ("mid_y",         "bench_w / 2",                             "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    print(">>> Parameters done")

    # ==============================================================
    #  COMPONENTS
    # ==============================================================
    leg_occ   = af.make_comp(root, "Legs")
    apron_occ = af.make_comp(root, "Aprons")
    seat_occ  = af.make_comp(root, "Seat")

    leg_c   = leg_occ.component
    apron_c = apron_occ.component
    seat_c  = seat_occ.component

    # ==============================================================
    #  1. LEGS
    # ==============================================================
    _, pr = af.sketch_rect_model(leg_c, leg_c.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_size", "y": "leg_size"},
        "LegFL_Sk", ev)
    fl_ext = af.ext_new(leg_c, pr, "leg_h", "LegFL")
    leg_fl = fl_ext.bodies.item(0)
    leg_fl.name = "Leg_FL"

    l_xmid = af.off_plane(leg_c, leg_c.yZConstructionPlane, "mid_x", "LXMid")
    l_ymid = af.off_plane(leg_c, leg_c.xZConstructionPlane, "mid_y", "LYMid")

    leg_fr = af.mirror_body(leg_c, leg_fl, l_xmid, "LegFR_Mir").bodies.item(0)
    leg_fr.name = "Leg_FR"
    leg_bl = af.mirror_body(leg_c, leg_fl, l_ymid, "LegBL_Mir").bodies.item(0)
    leg_bl.name = "Leg_BL"
    leg_br = af.mirror_body(leg_c, leg_fr, l_ymid, "LegBR_Mir").bodies.item(0)
    leg_br.name = "Leg_BR"

    print(">>> Legs: 4 bodies done")

    # ==============================================================
    #  2. APRONS — under seat
    # ==============================================================
    apron_z_pl = af.off_plane(apron_c, apron_c.xYConstructionPlane, "apron_z", "ApronZ_Pl")

    # Front apron (long)
    _, pr = af.sketch_rect_model(apron_c, apron_z_pl,
        ("leg_size", "0 in", "apron_z"),
        {"x": "long_apron_l", "y": "apron_thick"},
        "FrontApron_Sk", ev)
    fa_ext = af.ext_new(apron_c, pr, "apron_h", "FrontApron")
    fa_ext.bodies.item(0).name = "Apron_Front"

    a_ymid = af.off_plane(apron_c, apron_c.xZConstructionPlane, "mid_y", "AYMid")
    af.mirror_feats(apron_c, [fa_ext], a_ymid, "BackApronMir").bodies.item(0).name = "Apron_Back"

    # Left apron (short)
    _, pr = af.sketch_rect_model(apron_c, apron_z_pl,
        ("0 in", "leg_size", "apron_z"),
        {"x": "apron_thick", "y": "short_apron_l"},
        "LeftApron_Sk", ev)
    la_ext = af.ext_new(apron_c, pr, "apron_h", "LeftApron")
    la_ext.bodies.item(0).name = "Apron_Left"

    a_xmid = af.off_plane(apron_c, apron_c.yZConstructionPlane, "mid_x", "AXMid")
    af.mirror_feats(apron_c, [la_ext], a_xmid, "RightApronMir").bodies.item(0).name = "Apron_Right"

    # Stretchers (long, at lower height)
    str_z_pl = af.off_plane(apron_c, apron_c.xYConstructionPlane, "stretcher_z", "StrZ_Pl")
    _, pr = af.sketch_rect_model(apron_c, str_z_pl,
        ("leg_size", "0 in", "stretcher_z"),
        {"x": "long_str_l", "y": "stretcher_thick"},
        "FrontStr_Sk", ev)
    fs_ext = af.ext_new(apron_c, pr, "stretcher_h", "FrontStr")
    fs_ext.bodies.item(0).name = "Str_Front"

    af.mirror_feats(apron_c, [fs_ext], a_ymid, "BackStrMir").bodies.item(0).name = "Str_Back"

    print(">>> Aprons + stretchers: 6 bodies done")

    # ==============================================================
    #  3. SEAT
    # ==============================================================
    seat_pl = af.off_plane(seat_c, seat_c.xYConstructionPlane, "leg_h", "Seat_Pl")
    _, pr = af.sketch_rect_model(seat_c, seat_pl,
        ("0 in", "0 in", "leg_h"),
        {"x": "bench_l", "y": "bench_w"},
        "Seat_Sk", ev)
    seat_ext = af.ext_new(seat_c, pr, "seat_thick", "SeatBoard")
    seat_ext.bodies.item(0).name = "Seat"

    print(">>> Seat: 1 body done")

    # ==============================================================
    #  EPILOGUE
    # ==============================================================
    for comp in [leg_c, apron_c, seat_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False

    for comp_name, c in [("Legs", leg_c), ("Aprons", apron_c), ("Seat", seat_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{comp_name}: {len(names)} bodies -> {names}")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
