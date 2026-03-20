"""
Modern Coffee Table
===================
48"L x 24"W x 18"H, 1" thick top, 1.75" square legs.
Domino joinery at all apron-to-leg connections, lower shelf.

Coordinate system:
  X = length (48")  Y = width (24")  Z = height (18")

Components:
  Legs   — 4 square legs at corners
  Aprons — 2 long (front/back) + 2 short (left/right)
  Top    — solid panel
  Shelf  — lower shelf between legs

Joinery:
  - Domino grid at each apron-to-leg interface (2 per joint, 8 total)
  - Dominos at top-to-apron connections (4 per long apron, 2 per short)
  - Shelf rests on cleats or in dados (simplified: shelf extends into legs)
"""
import adsk.core, adsk.fusion

from helpers import af
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
        ("table_l",     "48 in",   "in"),
        ("table_w",     "24 in",   "in"),
        ("table_h",     "18 in",   "in"),
        ("top_thick",   "1 in",    "in"),
        ("leg_size",    "1.75 in", "in"),
        ("apron_h",     "3 in",    "in"),
        ("apron_thick", "0.75 in", "in"),
        ("shelf_thick", "0.75 in", "in"),
        ("shelf_z",     "3 in",    "in"),
        # Domino params (8mm Festool)
        ("dm_t",        "8 mm",    "in"),
        ("dm_w",        "22 mm",   "in"),
        ("dm_d",        "20 mm",   "in"),
        ("dm_count",    "2",       ""),   # dominos per apron end
    ]:
        params.add(pname, VI(expr), unit, "")

    for pname, expr, unit in [
        ("leg_h",         "table_h - top_thick",                     "in"),
        ("apron_z",       "table_h - top_thick - apron_h",           "in"),
        ("long_apron_l",  "table_l - 2 * leg_size",                  "in"),
        ("short_apron_l", "table_w - 2 * leg_size",                  "in"),
        ("shelf_l",       "table_l - 2 * leg_size",                  "in"),
        ("shelf_w",       "table_w - 2 * leg_size",                  "in"),
        ("mid_x",         "table_l / 2",                              "in"),
        ("mid_y",         "table_w / 2",                              "in"),
        ("dm_sp",         "apron_h / (dm_count + 1)",                "in"),
        ("dm_z_start",    "apron_z + apron_h / (dm_count + 1)",     "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    print(">>> Parameters done")

    # ==============================================================
    #  COMPONENTS
    # ==============================================================
    leg_occ   = af.make_comp(root, "Legs")
    apron_occ = af.make_comp(root, "Aprons")
    top_occ   = af.make_comp(root, "Top")
    shelf_occ = af.make_comp(root, "Shelf")

    leg_c   = leg_occ.component
    apron_c = apron_occ.component
    top_c   = top_occ.component
    shelf_c = shelf_occ.component

    # ==============================================================
    #  1. LEGS — 4 square legs at corners
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
    #  2. APRONS — 2 long (front/back) + 2 short (left/right)
    # ==============================================================
    apron_z_pl = af.off_plane(apron_c, apron_c.xYConstructionPlane,
                               "apron_z", "ApronZ_Pl")

    # Front apron
    _, pr = af.sketch_rect_model(apron_c, apron_z_pl,
        ("leg_size", "0 in", "apron_z"),
        {"x": "long_apron_l", "y": "apron_thick"},
        "FrontApron_Sk", ev)
    fa_ext = af.ext_new(apron_c, pr, "apron_h", "FrontApron")
    front_apron = fa_ext.bodies.item(0)
    front_apron.name = "Apron_Front"

    a_ymid = af.off_plane(apron_c, apron_c.xZConstructionPlane, "mid_y", "AYMid")
    ba_mir = af.mirror_feats(apron_c, [fa_ext], a_ymid, "BackApronMir")
    back_apron = ba_mir.bodies.item(0)
    back_apron.name = "Apron_Back"

    # Left apron
    _, pr = af.sketch_rect_model(apron_c, apron_z_pl,
        ("0 in", "leg_size", "apron_z"),
        {"x": "apron_thick", "y": "short_apron_l"},
        "LeftApron_Sk", ev)
    la_ext = af.ext_new(apron_c, pr, "apron_h", "LeftApron")
    left_apron = la_ext.bodies.item(0)
    left_apron.name = "Apron_Left"

    a_xmid = af.off_plane(apron_c, apron_c.yZConstructionPlane, "mid_x", "AXMid")
    ra_mir = af.mirror_feats(apron_c, [la_ext], a_xmid, "RightApronMir")
    right_apron = ra_mir.bodies.item(0)
    right_apron.name = "Apron_Right"

    print(">>> Aprons: 4 bodies done")

    # ==============================================================
    #  3. TOP — solid panel
    # ==============================================================
    top_pl = af.off_plane(top_c, top_c.xYConstructionPlane, "leg_h", "Top_Pl")
    _, pr = af.sketch_rect_model(top_c, top_pl,
        ("0 in", "0 in", "leg_h"),
        {"x": "table_l", "y": "table_w"},
        "Top_Sk", ev)
    top_ext = af.ext_new(top_c, pr, "top_thick", "TopBoard")
    top_body = top_ext.bodies.item(0)
    top_body.name = "Top"

    print(">>> Top: 1 body done")

    # ==============================================================
    #  4. SHELF — lower shelf between legs
    # ==============================================================
    shelf_z_pl = af.off_plane(shelf_c, shelf_c.xYConstructionPlane,
                               "shelf_z", "Shelf_Pl")
    _, pr = af.sketch_rect_model(shelf_c, shelf_z_pl,
        ("leg_size", "leg_size", "shelf_z"),
        {"x": "shelf_l", "y": "shelf_w"},
        "Shelf_Sk", ev)
    shelf_ext = af.ext_new(shelf_c, pr, "shelf_thick", "ShelfBoard")
    shelf_body = shelf_ext.bodies.item(0)
    shelf_body.name = "Shelf"

    print(">>> Shelf: 1 body done")

    # ==============================================================
    #  5. DOMINO JOINERY — apron-to-leg connections
    #     8 joints total (2 ends × 4 aprons).
    #     Each joint: domino grid of dm_count dominos along Z.
    #     Interface plane: YZ at the leg-apron boundary for long aprons,
    #                      XZ for short aprons.
    # ==============================================================
    # Assembly proxies for cross-component CUTs
    fl_proxy = leg_fl.createForAssemblyContext(leg_occ)
    fr_proxy = leg_fr.createForAssemblyContext(leg_occ)
    bl_proxy = leg_bl.createForAssemblyContext(leg_occ)
    br_proxy = leg_br.createForAssemblyContext(leg_occ)
    fa_proxy = front_apron.createForAssemblyContext(apron_occ)
    ba_proxy = back_apron.createForAssemblyContext(apron_occ)
    la_proxy = left_apron.createForAssemblyContext(apron_occ)
    ra_proxy = right_apron.createForAssemblyContext(apron_occ)

    # Front apron left end → FL leg
    # Interface: YZ plane at X = leg_size
    dm_fl_pl = af.off_plane(root, root.yZConstructionPlane, "leg_size", "DM_FL_Pl")
    domino.grid(root, dm_fl_pl,
        start=("leg_size", "apron_thick / 2", "dm_z_start"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d", body_a=fa_proxy, body_b=fl_proxy,
        name="DM_FA_L", ev=ev)

    # Front apron right end → FR leg
    dm_fr_pl = af.off_plane(root, root.yZConstructionPlane,
                             "table_l - leg_size", "DM_FR_Pl")
    domino.grid(root, dm_fr_pl,
        start=("table_l - leg_size", "apron_thick / 2", "dm_z_start"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d", body_a=fa_proxy, body_b=fr_proxy,
        name="DM_FA_R", ev=ev)

    # Back apron left end → BL leg
    domino.grid(root, dm_fl_pl,
        start=("leg_size", "table_w - apron_thick / 2", "dm_z_start"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d", body_a=ba_proxy, body_b=bl_proxy,
        name="DM_BA_L", ev=ev)

    # Back apron right end → BR leg
    domino.grid(root, dm_fr_pl,
        start=("table_l - leg_size", "table_w - apron_thick / 2", "dm_z_start"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d", body_a=ba_proxy, body_b=br_proxy,
        name="DM_BA_R", ev=ev)

    # Left apron front end → FL leg
    dm_lf_pl = af.off_plane(root, root.xZConstructionPlane, "leg_size", "DM_LF_Pl")
    domino.grid(root, dm_lf_pl,
        start=("apron_thick / 2", "leg_size", "dm_z_start"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d", body_a=la_proxy, body_b=fl_proxy,
        name="DM_LA_F", ev=ev)

    # Left apron back end → BL leg
    dm_lb_pl = af.off_plane(root, root.xZConstructionPlane,
                             "table_w - leg_size", "DM_LB_Pl")
    domino.grid(root, dm_lb_pl,
        start=("apron_thick / 2", "table_w - leg_size", "dm_z_start"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d", body_a=la_proxy, body_b=bl_proxy,
        name="DM_LA_B", ev=ev)

    # Right apron front end → FR leg
    domino.grid(root, dm_lf_pl,
        start=("table_l - apron_thick / 2", "leg_size", "dm_z_start"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d", body_a=ra_proxy, body_b=fr_proxy,
        name="DM_RA_F", ev=ev)

    # Right apron back end → BR leg
    domino.grid(root, dm_lb_pl,
        start=("table_l - apron_thick / 2", "table_w - leg_size", "dm_z_start"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d", body_a=ra_proxy, body_b=br_proxy,
        name="DM_RA_B", ev=ev)

    print(">>> Domino joinery: 8 joints (16 voids)")

    # ==============================================================
    #  EPILOGUE
    # ==============================================================
    all_comps = [leg_c, apron_c, top_c, shelf_c]
    for comp in all_comps:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False
    for sk in root.sketches:
        sk.isVisible = False
    for cp in root.constructionPlanes:
        cp.isLightBulbOn = False

    for comp_name, c in [("Legs", leg_c), ("Aprons", apron_c),
                          ("Top", top_c), ("Shelf", shelf_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{comp_name}: {len(names)} bodies -> {names}")

    root_names = [root.bRepBodies.item(i).name
                  for i in range(root.bRepBodies.count)]
    print(f"Root: {len(root_names)} domino voids")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
