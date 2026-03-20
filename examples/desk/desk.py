"""
Modern Writing Desk
===================
48"L x 28"W x 30"H, 1" thick top, 2" square legs.
Single dovetailed drawer, back apron, side aprons, no front apron
(drawer front fills the front face).

Coordinate system:
  X = length (48")  Y = width (28")  Z = height (30")
"""
import adsk.core, adsk.fusion

from helpers import af
from helpers.templates import dovetailed_drawer
from helpers.templates import domino

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
        ("desk_l",      "48 in",    "in"),
        ("desk_w",      "28 in",    "in"),
        ("desk_h",      "30 in",    "in"),
        ("top_thick",   "1 in",     "in"),
        ("leg_size",    "2 in",     "in"),
        ("apron_h",     "5 in",     "in"),
        ("apron_thick", "0.75 in",  "in"),
        ("drawer_gap",  "0.0625 in","in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    for pname, expr, unit in [
        ("leg_h",         "desk_h - top_thick",                      "in"),
        ("apron_z",       "desk_h - top_thick - apron_h",            "in"),
        ("long_apron_l",  "desk_l - 2 * leg_size",                   "in"),
        ("short_apron_l", "desk_w - 2 * leg_size",                   "in"),
        ("mid_x",         "desk_l / 2",                               "in"),
        ("mid_y",         "desk_w / 2",                               "in"),
        ("drawer_w",      "long_apron_l - 2 * drawer_gap",           "in"),
        ("drawer_d",      "desk_w - apron_thick - drawer_gap",       "in"),
        ("drawer_h_inner","apron_h - 2 * drawer_gap",                "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    dovetailed_drawer.define_params(params, prefix="dd",
        drawer_w="drawer_w", drawer_d="drawer_d",
        drawer_h="drawer_h_inner",
        front_thick="0.75 in", side_thick="0.5 in",
        bottom_thick="0.25 in",
        bg_depth="0.25 in", bg_up="0.25 in",
        dt_angle="8 deg", dt_tail_w="0.625 in",
        front_tail_count="3", back_tail_count="3",
        x_offset="leg_size + drawer_gap",
        z_offset="apron_z + drawer_gap")

    print(">>> Parameters done")

    # ==============================================================
    #  COMPONENTS
    # ==============================================================
    leg_occ    = af.make_comp(root, "Legs")
    apron_occ  = af.make_comp(root, "Aprons")
    top_occ    = af.make_comp(root, "Top")
    drawer_occ = af.make_comp(root, "Drawer")

    leg_c    = leg_occ.component
    apron_c  = apron_occ.component
    top_c    = top_occ.component
    drawer_c = drawer_occ.component

    # ==============================================================
    #  1. LEGS
    # ==============================================================
    _, pr = af.sketch_rect_model(leg_c, leg_c.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_size", "y": "leg_size"}, "LegFL_Sk", ev)
    fl_ext = af.ext_new(leg_c, pr, "leg_h", "LegFL")
    leg_fl = fl_ext.bodies.item(0); leg_fl.name = "Leg_FL"

    l_xmid = af.off_plane(leg_c, leg_c.yZConstructionPlane, "mid_x", "LXMid")
    l_ymid = af.off_plane(leg_c, leg_c.xZConstructionPlane, "mid_y", "LYMid")
    af.mirror_body(leg_c, leg_fl, l_xmid, "LegFR").bodies.item(0).name = "Leg_FR"
    leg_bl = af.mirror_body(leg_c, leg_fl, l_ymid, "LegBL").bodies.item(0)
    leg_bl.name = "Leg_BL"
    af.mirror_body(leg_c, leg_bl, l_xmid, "LegBR").bodies.item(0).name = "Leg_BR"
    print(">>> Legs: 4")

    # ==============================================================
    #  2. APRONS (back + 2 sides, no front — drawer front fills it)
    # ==============================================================
    az_pl = af.off_plane(apron_c, apron_c.xYConstructionPlane, "apron_z", "AZ_Pl")

    _, pr = af.sketch_rect_model(apron_c, az_pl,
        ("leg_size", "desk_w - leg_size - apron_thick", "apron_z"),
        {"x": "long_apron_l", "y": "apron_thick"}, "BackApron_Sk", ev)
    af.ext_new(apron_c, pr, "apron_h", "BackApron").bodies.item(0).name = "Apron_Back"

    _, pr = af.sketch_rect_model(apron_c, az_pl,
        ("0 in", "leg_size", "apron_z"),
        {"x": "apron_thick", "y": "short_apron_l"}, "LeftApron_Sk", ev)
    la_ext = af.ext_new(apron_c, pr, "apron_h", "LeftApron")
    la_ext.bodies.item(0).name = "Apron_Left"

    a_xmid = af.off_plane(apron_c, apron_c.yZConstructionPlane, "mid_x", "AXMid")
    af.mirror_feats(apron_c, [la_ext], a_xmid, "RightApronMir").bodies.item(0).name = "Apron_Right"
    print(">>> Aprons: 3")

    # ==============================================================
    #  3. TOP
    # ==============================================================
    top_pl = af.off_plane(top_c, top_c.xYConstructionPlane, "leg_h", "Top_Pl")
    _, pr = af.sketch_rect_model(top_c, top_pl,
        ("0 in", "0 in", "leg_h"),
        {"x": "desk_l", "y": "desk_w"}, "Top_Sk", ev)
    af.ext_new(top_c, pr, "top_thick", "TopBoard").bodies.item(0).name = "Top"
    print(">>> Top: 1")

    # ==============================================================
    #  4. DRAWER
    # ==============================================================
    dd_result = dovetailed_drawer.build(drawer_c, prefix="dd", ev=ev)
    print(">>> Drawer: %d bodies" % len(dd_result["all_bodies"]))

    # ==============================================================
    #  5. DOMINO JOINERY — apron-to-leg connections (6 joints)
    # ==============================================================
    params.add("dm_t", VI("8 mm"), "in", "")
    params.add("dm_w", VI("22 mm"), "in", "")
    params.add("dm_d", VI("20 mm"), "in", "")
    params.add("dm_count", VI("2"), "", "")
    params.add("dm_sp", VI("apron_h / (dm_count + 1)"), "in", "")
    params.add("dm_z_start", VI("apron_z + apron_h / (dm_count + 1)"), "in", "")

    # Get leg bodies for proxies
    leg_fr = leg_bl = leg_br = None
    for i in range(leg_c.bRepBodies.count):
        b = leg_c.bRepBodies.item(i)
        if b.name == "Leg_FR": leg_fr = b
        elif b.name == "Leg_BL": leg_bl = b
        elif b.name == "Leg_BR": leg_br = b

    fl_p = leg_fl.createForAssemblyContext(leg_occ)
    fr_p = leg_fr.createForAssemblyContext(leg_occ)
    bl_p = leg_bl.createForAssemblyContext(leg_occ)
    br_p = leg_br.createForAssemblyContext(leg_occ)

    ba_body = la_body = ra_body = None
    for i in range(apron_c.bRepBodies.count):
        b = apron_c.bRepBodies.item(i)
        if b.name == "Apron_Back": ba_body = b
        elif b.name == "Apron_Left": la_body = b
        elif b.name == "Apron_Right": ra_body = b
    ba_p = ba_body.createForAssemblyContext(apron_occ)
    la_p = la_body.createForAssemblyContext(apron_occ)
    ra_p = ra_body.createForAssemblyContext(apron_occ)

    dm_fl = af.off_plane(root, root.yZConstructionPlane, "leg_size", "DM_FL")
    dm_fr = af.off_plane(root, root.yZConstructionPlane, "desk_l - leg_size", "DM_FR")
    dm_lf = af.off_plane(root, root.xZConstructionPlane, "leg_size", "DM_LF")
    dm_lb = af.off_plane(root, root.xZConstructionPlane, "desk_w - leg_size", "DM_LB")

    # Back apron → BL, BR legs
    domino.grid(root, dm_fl, ("leg_size", "desk_w - leg_size - apron_thick/2", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d", ba_p, bl_p, "DM_BA_L", ev)
    domino.grid(root, dm_fr, ("desk_l - leg_size", "desk_w - leg_size - apron_thick/2", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d", ba_p, br_p, "DM_BA_R", ev)

    # Left apron → FL, BL
    domino.grid(root, dm_lf, ("apron_thick/2", "leg_size", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d", la_p, fl_p, "DM_LA_F", ev)
    domino.grid(root, dm_lb, ("apron_thick/2", "desk_w - leg_size", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d", la_p, bl_p, "DM_LA_B", ev)

    # Right apron → FR, BR
    domino.grid(root, dm_lf, ("desk_l - apron_thick/2", "leg_size", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d", ra_p, fr_p, "DM_RA_F", ev)
    domino.grid(root, dm_lb, ("desk_l - apron_thick/2", "desk_w - leg_size", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d", ra_p, br_p, "DM_RA_B", ev)

    print(">>> Dominos: 6 joints (12 voids)")

    # ==============================================================
    #  EPILOGUE
    # ==============================================================
    for comp in [leg_c, apron_c, top_c, drawer_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False
    for sk in root.sketches:
        sk.isVisible = False
    for cp in root.constructionPlanes:
        cp.isLightBulbOn = False

    for cn, c in [("Legs", leg_c), ("Aprons", apron_c),
                   ("Top", top_c), ("Drawer", drawer_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{cn}: {len(names)} bodies -> {names}")
    print(f"Root: {root.bRepBodies.count} domino voids")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
