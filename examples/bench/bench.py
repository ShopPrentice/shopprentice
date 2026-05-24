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

from helpers import sp
from woodworking.templates import domino

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
        ("bench_w",     "12 in",   "in"),
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

    # ------------------------------------------------------------------
    #  find_body — resolve body reference by name (recursive)
    # ------------------------------------------------------------------
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

    # ==============================================================
    #  COMPONENTS
    # ==============================================================
    leg_occ   = sp.make_comp(root, "Legs")
    apron_occ = sp.make_comp(root, "Aprons")
    seat_occ  = sp.make_comp(root, "Seat")

    leg_c   = leg_occ.component
    apron_c = apron_occ.component
    seat_c  = seat_occ.component

    # ==============================================================
    #  1. LEGS
    # ==============================================================
    _, pr = sp.sketch_rect_model(leg_c, leg_c.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_size", "y": "leg_size"},
        "LegFL_Sk", ev)
    fl_ext = sp.ext_new(leg_c, pr, "leg_h", "LegFL")
    leg_fl = fl_ext.bodies.item(0)
    leg_fl.name = "Leg_FL"

    l_xmid = sp.off_plane(leg_c, leg_c.yZConstructionPlane, "mid_x", "LXMid")
    l_ymid = sp.off_plane(leg_c, leg_c.xZConstructionPlane, "mid_y", "LYMid")

    leg_fr = sp.mirror_body(leg_c, leg_fl, l_xmid, "LegFR_Mir").bodies.item(0)
    leg_fr.name = "Leg_FR"
    leg_bl = sp.mirror_body(leg_c, leg_fl, l_ymid, "LegBL_Mir").bodies.item(0)
    leg_bl.name = "Leg_BL"
    leg_br = sp.mirror_body(leg_c, leg_fr, l_ymid, "LegBR_Mir").bodies.item(0)
    leg_br.name = "Leg_BR"

    print(">>> Legs: 4 bodies done")

    # -- Body-relative references: aprons + seat positioned relative to legs --
    ref_leg_fl = find_body("Leg_FL")
    ref_leg_fl_bb = ref_leg_fl.boundingBox
    ref_leg_fr = find_body("Leg_FR")
    ref_leg_fr_bb = ref_leg_fr.boundingBox
    ref_leg_bl = find_body("Leg_BL")
    ref_leg_bl_bb = ref_leg_bl.boundingBox

    # ==============================================================
    #  2. APRONS — under seat
    # ==============================================================
    apron_z_pl = sp.off_plane(apron_c, apron_c.xYConstructionPlane, "apron_z", "ApronZ_Pl")

    # Front apron (long)
    _, pr = sp.sketch_rect_model(apron_c, apron_z_pl,
        ("leg_size", "0 in", "apron_z"),
        {"x": "long_apron_l", "y": "apron_thick"},
        "FrontApron_Sk", ev)
    fa_ext = sp.ext_new(apron_c, pr, "apron_h", "FrontApron")
    fa_ext.bodies.item(0).name = "Apron_Front"

    a_ymid = sp.off_plane(apron_c, apron_c.xZConstructionPlane, "mid_y", "AYMid")
    sp.mirror_feats(apron_c, [fa_ext], a_ymid, "BackApronMir").bodies.item(0).name = "Apron_Back"

    # Left apron (short)
    _, pr = sp.sketch_rect_model(apron_c, apron_z_pl,
        ("0 in", "leg_size", "apron_z"),
        {"x": "apron_thick", "y": "short_apron_l"},
        "LeftApron_Sk", ev)
    la_ext = sp.ext_new(apron_c, pr, "apron_h", "LeftApron")
    la_ext.bodies.item(0).name = "Apron_Left"

    a_xmid = sp.off_plane(apron_c, apron_c.yZConstructionPlane, "mid_x", "AXMid")
    sp.mirror_feats(apron_c, [la_ext], a_xmid, "RightApronMir").bodies.item(0).name = "Apron_Right"

    # -- Body-relative references: stretchers positioned relative to aprons --
    ref_apron_front = find_body("Apron_Front")
    ref_apron_front_bb = ref_apron_front.boundingBox
    ref_apron_back = find_body("Apron_Back")
    ref_apron_back_bb = ref_apron_back.boundingBox
    ref_apron_left = find_body("Apron_Left")
    ref_apron_left_bb = ref_apron_left.boundingBox
    ref_apron_right = find_body("Apron_Right")
    ref_apron_right_bb = ref_apron_right.boundingBox

    # Stretchers (long, at lower height)
    str_z_pl = sp.off_plane(apron_c, apron_c.xYConstructionPlane, "stretcher_z", "StrZ_Pl")
    _, pr = sp.sketch_rect_model(apron_c, str_z_pl,
        ("leg_size", "0 in", "stretcher_z"),
        {"x": "long_str_l", "y": "stretcher_thick"},
        "FrontStr_Sk", ev)
    fs_ext = sp.ext_new(apron_c, pr, "stretcher_h", "FrontStr")
    fs_ext.bodies.item(0).name = "Str_Front"

    sp.mirror_feats(apron_c, [fs_ext], a_ymid, "BackStrMir").bodies.item(0).name = "Str_Back"

    print(">>> Aprons + stretchers: 6 bodies done")

    # ==============================================================
    #  3. SEAT
    # ==============================================================
    seat_pl = sp.off_plane(seat_c, seat_c.xYConstructionPlane, "leg_h", "Seat_Pl")
    _, pr = sp.sketch_rect_model(seat_c, seat_pl,
        ("0 in", "0 in", "leg_h"),
        {"x": "bench_l", "y": "bench_w"},
        "Seat_Sk", ev)
    seat_ext = sp.ext_new(seat_c, pr, "seat_thick", "SeatBoard")
    seat_ext.bodies.item(0).name = "Seat"

    print(">>> Seat: 1 body done")

    # ==============================================================
    #  4. DOMINO JOINERY — apron/stretcher to leg connections
    # ==============================================================
    # Domino params
    params.add("dm_t", VI("8 mm"), "in", "")
    params.add("dm_w", VI("22 mm"), "in", "")
    params.add("dm_d", VI("20 mm"), "in", "")
    params.add("dm_count", VI("2"), "", "")
    params.add("dm_apron_sp", VI("apron_h / (dm_count + 1)"), "in", "")
    params.add("dm_apron_z", VI("apron_z + apron_h / (dm_count + 1)"), "in", "")
    params.add("dm_str_z", VI("stretcher_z + stretcher_h / 2"), "in", "")

    # Assembly proxies
    fl_p = leg_fl.createForAssemblyContext(leg_occ)
    fr_p = leg_fr.createForAssemblyContext(leg_occ)
    bl_p = leg_bl.createForAssemblyContext(leg_occ)
    br_p = leg_br.createForAssemblyContext(leg_occ)

    fa_body = None; ba_body = None
    la_body = None; ra_body = None
    sf_body = None; sb_body = None
    for i in range(apron_c.bRepBodies.count):
        b = apron_c.bRepBodies.item(i)
        if b.name == "Apron_Front": fa_body = b
        elif b.name == "Apron_Back": ba_body = b
        elif b.name == "Apron_Left": la_body = b
        elif b.name == "Apron_Right": ra_body = b
        elif b.name == "Str_Front": sf_body = b
        elif b.name == "Str_Back": sb_body = b

    # Construction planes for domino joints (in apron component)
    dm_fl = sp.off_plane(apron_c, apron_c.yZConstructionPlane, "leg_size", "DM_FL")
    dm_fr = sp.off_plane(apron_c, apron_c.yZConstructionPlane, "bench_l - leg_size", "DM_FR")
    dm_lf = sp.off_plane(apron_c, apron_c.xZConstructionPlane, "leg_size", "DM_LF")
    dm_lb = sp.off_plane(apron_c, apron_c.xZConstructionPlane, "bench_w - leg_size", "DM_LB")

    # Front apron → FL, FR legs
    domino.grid(apron_c, dm_fl, ("leg_size", "apron_thick/2", "dm_apron_z"),
        "z", "dm_apron_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        fa_body, fl_p, "DM_FA_L", ev)
    domino.grid(apron_c, dm_fr, ("bench_l - leg_size", "apron_thick/2", "dm_apron_z"),
        "z", "dm_apron_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        fa_body, fr_p, "DM_FA_R", ev)

    # Back apron → BL, BR legs
    domino.grid(apron_c, dm_fl, ("leg_size", "bench_w - apron_thick/2", "dm_apron_z"),
        "z", "dm_apron_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        ba_body, bl_p, "DM_BA_L", ev)
    domino.grid(apron_c, dm_fr, ("bench_l - leg_size", "bench_w - apron_thick/2", "dm_apron_z"),
        "z", "dm_apron_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        ba_body, br_p, "DM_BA_R", ev)

    # Left apron → FL, BL legs
    domino.grid(apron_c, dm_lf, ("apron_thick/2", "leg_size", "dm_apron_z"),
        "z", "dm_apron_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        la_body, fl_p, "DM_LA_F", ev)
    domino.grid(apron_c, dm_lb, ("apron_thick/2", "bench_w - leg_size", "dm_apron_z"),
        "z", "dm_apron_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        la_body, bl_p, "DM_LA_B", ev)

    # Right apron → FR, BR legs
    domino.grid(apron_c, dm_lf, ("bench_l - apron_thick/2", "leg_size", "dm_apron_z"),
        "z", "dm_apron_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        ra_body, fr_p, "DM_RA_F", ev)
    domino.grid(apron_c, dm_lb, ("bench_l - apron_thick/2", "bench_w - leg_size", "dm_apron_z"),
        "z", "dm_apron_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        ra_body, br_p, "DM_RA_B", ev)

    # -- Body-relative references: stretcher dominos --
    ref_str_front = find_body("Str_Front")
    ref_str_front_bb = ref_str_front.boundingBox
    ref_str_back = find_body("Str_Back")
    ref_str_back_bb = ref_str_back.boundingBox

    # Front stretcher → FL, FR legs (single domino each, centered in stretcher height)
    domino.single(apron_c, dm_fl, ("leg_size", "stretcher_thick/2", "dm_str_z"),
        "z", "dm_w", "dm_t", "dm_d", sf_body, fl_p, "DM_SF_L", ev)
    domino.single(apron_c, dm_fr, ("bench_l - leg_size", "stretcher_thick/2", "dm_str_z"),
        "z", "dm_w", "dm_t", "dm_d", sf_body, fr_p, "DM_SF_R", ev)

    # Back stretcher → BL, BR legs
    domino.single(apron_c, dm_fl, ("leg_size", "bench_w - stretcher_thick/2", "dm_str_z"),
        "z", "dm_w", "dm_t", "dm_d", sb_body, bl_p, "DM_SB_L", ev)
    domino.single(apron_c, dm_fr, ("bench_l - leg_size", "bench_w - stretcher_thick/2", "dm_str_z"),
        "z", "dm_w", "dm_t", "dm_d", sb_body, br_p, "DM_SB_R", ev)

    print(">>> Dominos: 12 joints (aprons: 8×2=16, stretchers: 4×1=4 voids)")

    # ==============================================================
    #  EPILOGUE
    # ==============================================================
    for comp in [leg_c, apron_c, seat_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False
    for sk in root.sketches:
        sk.isVisible = False
    for cp in root.constructionPlanes:
        cp.isLightBulbOn = False

    for comp_name, c in [("Legs", leg_c), ("Aprons", apron_c), ("Seat", seat_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{comp_name}: {len(names)} bodies -> {names}")

    sp.apply_appearance("white oak")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
