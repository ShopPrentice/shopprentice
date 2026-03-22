"""
Modern Writing Desk
===================
48"L x 28"W x 30"H, 1" thick top, tapered legs.
Single dovetailed drawer with runners and stops.
Front rail above drawer opening.
Top attached to aprons via dominos.
Cable grommet in top.

Coordinate system:
  X = length (48")  Y = width (28")  Z = height (30")
"""
import adsk.core, adsk.fusion

from helpers import af
from woodworking.templates import dovetailed_drawer
from woodworking.templates import domino
from woodworking.templates import tabletop_bracket

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    P3 = adsk.core.Point3D
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
        ("leg_taper",   "0.75 in",  "in"),   # how much each inner face tapers
        ("apron_h",     "5 in",     "in"),
        ("apron_thick", "0.75 in",  "in"),
        ("front_rail_h","1.5 in",   "in"),   # rail above drawer opening
        ("drawer_gap",  "0.0625 in","in"),
        ("runner_w",    "0.75 in",  "in"),   # drawer runner width
        ("runner_h",    "0.375 in", "in"),   # drawer runner height
        ("stop_l",      "1 in",     "in"),   # drawer stop length
        ("grommet_dia",  "2 in",    "in"),   # cable grommet diameter
        ("grommet_inset","3 in",    "in"),   # from back-right corner
        ("edge_chamfer","0.03125 in","in"),  # 1/32" edge break
    ]:
        params.add(pname, VI(expr), unit, "")

    for pname, expr, unit in [
        ("leg_h",         "desk_h - top_thick",                         "in"),
        ("leg_foot",      "leg_size - leg_taper",                       "in"),
        ("apron_z",       "desk_h - top_thick - apron_h",               "in"),
        ("long_apron_l",  "desk_l - 2 * leg_size",                      "in"),
        ("short_apron_l", "desk_w - 2 * leg_size",                      "in"),
        ("mid_x",         "desk_l / 2",                                  "in"),
        ("mid_y",         "desk_w / 2",                                  "in"),
        # Drawer opening = apron_h minus front_rail_h
        ("drawer_opening","apron_h - front_rail_h",                     "in"),
        ("drawer_w",      "long_apron_l - 2 * drawer_gap",             "in"),
        ("drawer_d",      "short_apron_l",                              "in"),
        ("drawer_h_inner","drawer_opening - 2 * drawer_gap",           "in"),
        # Taper starts below the apron
        ("taper_h",       "apron_z",                                    "in"),
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
    #  1. LEGS — tapered on inner faces below the apron
    # ==============================================================
    _, pr = af.sketch_rect_model(leg_c, leg_c.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_size", "y": "leg_size"}, "LegFL_Sk", ev)
    fl_ext = af.ext_new(leg_c, pr, "leg_h", "LegFL")
    leg_fl = fl_ext.bodies.item(0); leg_fl.name = "Leg_FL"

    # Taper — CUT triangular wedges from inner faces below the apron
    # X-direction taper: sketch on XZ plane, extrude through leg in Y
    sk_tx = leg_c.sketches.add(leg_c.xZConstructionPlane)
    sk_tx.name = "TaperX_Sk"
    m2s = sk_tx.modelToSketchSpace
    pt1 = m2s(P3.create(ev("leg_size"), 0, ev("apron_z")))
    pt2 = m2s(P3.create(ev("leg_size"), 0, 0))
    pt3 = m2s(P3.create(ev("leg_size") - ev("leg_taper"), 0, 0))
    lines = sk_tx.sketchCurves.sketchLines
    l1 = lines.addByTwoPoints(P3.create(pt1.x, pt1.y, 0), P3.create(pt2.x, pt2.y, 0))
    l2 = lines.addByTwoPoints(l1.endSketchPoint, P3.create(pt3.x, pt3.y, 0))
    lines.addByTwoPoints(l2.endSketchPoint, l1.startSketchPoint)
    taper_prof = sk_tx.profiles.item(0)
    af.ext_op(leg_c, taper_prof, "leg_size", CUT, leg_fl, "TaperX_Cut")

    # Y-direction taper: sketch on YZ plane, extrude through leg in X
    sk_ty = leg_c.sketches.add(leg_c.yZConstructionPlane)
    sk_ty.name = "TaperY_Sk"
    m2s = sk_ty.modelToSketchSpace
    pt1 = m2s(P3.create(0, ev("leg_size"), ev("apron_z")))
    pt2 = m2s(P3.create(0, ev("leg_size"), 0))
    pt3 = m2s(P3.create(0, ev("leg_size") - ev("leg_taper"), 0))
    lines = sk_ty.sketchCurves.sketchLines
    l1 = lines.addByTwoPoints(P3.create(pt1.x, pt1.y, 0), P3.create(pt2.x, pt2.y, 0))
    l2 = lines.addByTwoPoints(l1.endSketchPoint, P3.create(pt3.x, pt3.y, 0))
    lines.addByTwoPoints(l2.endSketchPoint, l1.startSketchPoint)
    taper_prof = sk_ty.profiles.item(0)
    af.ext_op(leg_c, taper_prof, "leg_size", CUT, leg_fl, "TaperY_Cut")

    # Mirror to all 4 corners
    l_xmid = af.off_plane(leg_c, leg_c.yZConstructionPlane, "mid_x", "LXMid")
    l_ymid = af.off_plane(leg_c, leg_c.xZConstructionPlane, "mid_y", "LYMid")
    af.mirror_body(leg_c, leg_fl, l_xmid, "LegFR").bodies.item(0).name = "Leg_FR"
    leg_bl = af.mirror_body(leg_c, leg_fl, l_ymid, "LegBL").bodies.item(0)
    leg_bl.name = "Leg_BL"
    af.mirror_body(leg_c, leg_bl, l_xmid, "LegBR").bodies.item(0).name = "Leg_BR"
    print(">>> Legs: 4 (tapered)")

    # ==============================================================
    #  2. APRONS — back + 2 sides + front rail above drawer
    # ==============================================================
    az_pl = af.off_plane(apron_c, apron_c.xYConstructionPlane, "apron_z", "AZ_Pl")

    # Back apron (full height)
    _, pr = af.sketch_rect_model(apron_c, az_pl,
        ("leg_size", "desk_w - leg_size - apron_thick", "apron_z"),
        {"x": "long_apron_l", "y": "apron_thick"}, "BackApron_Sk", ev)
    af.ext_new(apron_c, pr, "apron_h", "BackApron").bodies.item(0).name = "Apron_Back"

    # Left side apron (full height)
    _, pr = af.sketch_rect_model(apron_c, az_pl,
        ("0 in", "leg_size", "apron_z"),
        {"x": "apron_thick", "y": "short_apron_l"}, "LeftApron_Sk", ev)
    la_ext = af.ext_new(apron_c, pr, "apron_h", "LeftApron")
    la_ext.bodies.item(0).name = "Apron_Left"

    a_xmid = af.off_plane(apron_c, apron_c.yZConstructionPlane, "mid_x", "AXMid")
    af.mirror_feats(apron_c, [la_ext], a_xmid, "RightApronMir").bodies.item(0).name = "Apron_Right"

    # Front rail (thin strip above drawer opening)
    fr_z_pl = af.off_plane(apron_c, apron_c.xYConstructionPlane,
                            "desk_h - top_thick - front_rail_h", "FrontRail_Pl")
    _, pr = af.sketch_rect_model(apron_c, fr_z_pl,
        ("leg_size", "0 in", "desk_h - top_thick - front_rail_h"),
        {"x": "long_apron_l", "y": "apron_thick"}, "FrontRail_Sk", ev)
    af.ext_new(apron_c, pr, "front_rail_h", "FrontRail").bodies.item(0).name = "Apron_FrontRail"

    # Drawer runners — strips on inner face of side aprons, running front-to-back (Y)
    runner_z = "apron_z + drawer_gap"
    runner_z_pl = af.off_plane(apron_c, apron_c.xYConstructionPlane, runner_z, "RunnerZ_Pl")
    _, pr = af.sketch_rect_model(apron_c, runner_z_pl,
        ("apron_thick", "leg_size", runner_z),
        {"x": "runner_w", "y": "short_apron_l"}, "LeftRunner_Sk", ev)
    lr_ext = af.ext_new(apron_c, pr, "runner_h", "LeftRunner")
    lr_ext.bodies.item(0).name = "Runner_Left"
    af.mirror_feats(apron_c, [lr_ext], a_xmid, "RightRunnerMir").bodies.item(0).name = "Runner_Right"

    # Drawer stops — blocks at back of each runner, on top of runner
    stop_z = "apron_z + drawer_gap + runner_h"
    stop_z_pl = af.off_plane(apron_c, apron_c.xYConstructionPlane, stop_z, "StopZ_Pl")
    _, pr = af.sketch_rect_model(apron_c, stop_z_pl,
        ("apron_thick", "desk_w - leg_size - apron_thick - stop_l", stop_z),
        {"x": "runner_w", "y": "stop_l"}, "LeftStop_Sk", ev)
    ls_ext = af.ext_new(apron_c, pr, "drawer_h_inner", "LeftStop")
    ls_ext.bodies.item(0).name = "Stop_Left"
    af.mirror_feats(apron_c, [ls_ext], a_xmid, "RightStopMir").bodies.item(0).name = "Stop_Right"

    print(">>> Aprons: 4 + 2 runners + 2 stops")

    # ==============================================================
    #  3. TOP — with cable grommet
    # ==============================================================
    top_pl = af.off_plane(top_c, top_c.xYConstructionPlane, "leg_h", "Top_Pl")
    _, pr = af.sketch_rect_model(top_c, top_pl,
        ("0 in", "0 in", "leg_h"),
        {"x": "desk_l", "y": "desk_w"}, "Top_Sk", ev)
    top_ext = af.ext_new(top_c, pr, "top_thick", "TopBoard")
    top_body = top_ext.bodies.item(0); top_body.name = "Top"

    # Cable grommet — circular CUT at back-right corner
    grommet_pl = af.off_plane(top_c, top_c.xYConstructionPlane,
                               "leg_h", "Grommet_Pl")
    sk_g = top_c.sketches.add(grommet_pl)
    sk_g.name = "Grommet_Sk"
    gx = ev("desk_l") - ev("grommet_inset")
    gy = ev("desk_w") - ev("grommet_inset")
    sk_g.sketchCurves.sketchCircles.addByCenterRadius(
        P3.create(gx, gy, 0), ev("grommet_dia") / 2)
    grommet_prof = sk_g.profiles.item(0)
    af.ext_op(top_c, grommet_prof, "top_thick", CUT, top_body, "GrommetCut")

    print(">>> Top: 1 (with grommet)")

    # ==============================================================
    #  4. DRAWER
    # ==============================================================
    dd_result = dovetailed_drawer.build(drawer_c, prefix="dd", ev=ev)
    print(">>> Drawer: %d bodies" % len(dd_result["all_bodies"]))

    # ==============================================================
    #  5. JOINERY — dominos for all connections
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

    ba_body = la_body = ra_body = fr_body = None
    for i in range(apron_c.bRepBodies.count):
        b = apron_c.bRepBodies.item(i)
        if b.name == "Apron_Back": ba_body = b
        elif b.name == "Apron_Left": la_body = b
        elif b.name == "Apron_Right": ra_body = b
        elif b.name == "Apron_FrontRail": fr_body = b
    ba_p = ba_body.createForAssemblyContext(apron_occ)
    la_p = la_body.createForAssemblyContext(apron_occ)
    ra_p = ra_body.createForAssemblyContext(apron_occ)
    fr_p_body = fr_body.createForAssemblyContext(apron_occ)

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

    # Front rail → FL, FR legs (1 domino each)
    params.add("fr_dm_z", VI("desk_h - top_thick - front_rail_h / 2"), "in", "")
    domino.grid(root, dm_fl, ("leg_size", "apron_thick / 2", "fr_dm_z"),
        "z", "0 in", "1", "z", "dm_w", "dm_t", "dm_d", fr_p_body, fl_p, "DM_FR_L", ev)
    domino.grid(root, dm_fr, ("desk_l - leg_size", "apron_thick / 2", "fr_dm_z"),
        "z", "0 in", "1", "z", "dm_w", "dm_t", "dm_d", fr_p_body, fr_p, "DM_FR_R", ev)

    # Top → aprons via L-brackets (slotted holes allow cross-grain movement)
    # Vertical leg against apron inner face, horizontal leg under top
    bracket_occ = af.make_comp(root, "Brackets")
    bracket_c = bracket_occ.component
    tabletop_bracket._define_params(params)
    top_z = ev("leg_h")  # top underside Z

    # Back apron: inner face at Y = desk_w - leg_size - apron_thick
    # face_dir=-1: horizontal leg extends toward -Y (into the desk)
    back_y = ev("desk_w") - ev("leg_size") - ev("apron_thick")
    tabletop_bracket.row(bracket_c, face_axis="y", face_dir=-1,
        start=(ev("leg_size") + ev("long_apron_l") / 4, back_y, top_z),
        step_axis="x", step_expr=str(ev("long_apron_l") / 4),
        count=3, name="TB_B", ev=ev)

    # Left apron: inner face at X = apron_thick
    # face_dir=+1: horizontal leg extends toward +X (into the desk)
    tabletop_bracket.row(bracket_c, face_axis="x", face_dir=1,
        start=(ev("apron_thick"), ev("leg_size") + ev("short_apron_l") / 3, top_z),
        step_axis="y", step_expr=str(ev("short_apron_l") / 3),
        count=2, name="TB_L", ev=ev)

    # Right apron: inner face at X = desk_l - apron_thick
    # face_dir=-1: horizontal leg extends toward -X (into the desk)
    tabletop_bracket.row(bracket_c, face_axis="x", face_dir=-1,
        start=(ev("desk_l") - ev("apron_thick"), ev("leg_size") + ev("short_apron_l") / 3, top_z),
        step_axis="y", step_expr=str(ev("short_apron_l") / 3),
        count=2, name="TB_R", ev=ev)

    # Front rail: inner face at Y = apron_thick
    # face_dir=+1: horizontal leg extends toward +Y (into the desk)
    front_y = ev("apron_thick")
    tabletop_bracket.row(bracket_c, face_axis="y", face_dir=1,
        start=(ev("leg_size") + ev("long_apron_l") / 4, front_y, top_z),
        step_axis="x", step_expr=str(ev("long_apron_l") / 4),
        count=3, name="TB_F", ev=ev)

    print(">>> Brackets: 10 tabletop L-brackets (3 front + 3 back + 2 left + 2 right)")
    print(">>> Dominos: 8 apron-leg + 2 front-rail = 10 joints")

    # ==============================================================
    #  6. DETAILS — edge chamfers
    # ==============================================================
    for comp_name, comp in [("Legs", leg_c), ("Aprons", apron_c), ("Top", top_c)]:
        edges = adsk.core.ObjectCollection.create()
        for bi in range(comp.bRepBodies.count):
            body = comp.bRepBodies.item(bi)
            if body.name.startswith("DM_"):
                continue
            for ei in range(body.edges.count):
                edges.add(body.edges.item(ei))
        if edges.count > 0:
            ch_inp = comp.features.chamferFeatures.createInput2()
            ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                edges, VI("edge_chamfer"), True)
            comp.features.chamferFeatures.add(ch_inp).name = f"{comp_name}_Ch"

    print(">>> Chamfers: 3 component edge breaks")

    # ==============================================================
    #  EPILOGUE
    # ==============================================================
    for comp in [leg_c, apron_c, top_c, drawer_c, bracket_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False
    for sk in root.sketches:
        sk.isVisible = False
    for cp in root.constructionPlanes:
        cp.isLightBulbOn = False

    for cn, c in [("Legs", leg_c), ("Aprons", apron_c),
                   ("Top", top_c), ("Drawer", drawer_c),
                   ("Brackets", bracket_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{cn}: {len(names)} bodies -> {names}")
    print(f"Root: {root.bRepBodies.count} domino voids")

    af.apply_appearance("walnut")

    # Re-apply steel to brackets (walnut overwrites them)
    tabletop_bracket._apply_steel(bracket_c,
        [bracket_c.bRepBodies.item(i) for i in range(bracket_c.bRepBodies.count)])

    vp = app.activeViewport
    vp.visualStyle = adsk.core.VisualStyles.ShadedWithVisibleEdgesOnlyVisualStyle
    cam = vp.camera
    cam.isFitView = True
    vp.camera = cam
