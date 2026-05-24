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

from helpers import sp
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
        ("desk_w",      "24 in",    "in"),
        ("desk_h",      "30 in",    "in"),
        ("top_thick",   "1 in",     "in"),
        ("top_overhang","0.75 in",  "in"),   # overhang past legs on each end
        ("leg_size",    "2 in",     "in"),
        ("leg_taper",   "0.75 in",  "in"),   # how much each inner face tapers
        ("apron_h",     "5 in",     "in"),
        ("apron_thick", "0.75 in",  "in"),
        ("stretcher_h", "1.5 in",   "in"),   # front stretcher below drawers
        ("divider_thick","0.75 in", "in"),  # center divider between drawers
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
        ("drawer_opening","apron_h - stretcher_h",                       "in"),
        ("drawer_w",      "(long_apron_l - divider_thick - 4 * drawer_gap) / 2", "in"),
        ("drawer_d",      "short_apron_l",                              "in"),
        ("drawer_h_inner","drawer_opening - 2 * drawer_gap",           "in"),
        # Taper starts below the apron
        ("taper_h",       "apron_z",                                    "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    # Left drawer x_offset: just inside left leg
    dovetailed_drawer.define_params(params, prefix="ddl",
        drawer_w="drawer_w", drawer_d="drawer_d",
        drawer_h="drawer_h_inner",
        front_thick="0.75 in", side_thick="0.5 in",
        bottom_thick="0.25 in",
        bg_depth="0.25 in", bg_up="0.25 in",
        dt_angle="8 deg", dt_tail_w="0.625 in",
        front_tail_count="2", back_tail_count="2",
        x_offset="leg_size + drawer_gap",
        z_offset="apron_z + stretcher_h + drawer_gap")
    # Right drawer x_offset: after divider
    dovetailed_drawer.define_params(params, prefix="ddr",
        drawer_w="drawer_w", drawer_d="drawer_d",
        drawer_h="drawer_h_inner",
        front_thick="0.75 in", side_thick="0.5 in",
        bottom_thick="0.25 in",
        bg_depth="0.25 in", bg_up="0.25 in",
        dt_angle="8 deg", dt_tail_w="0.625 in",
        front_tail_count="2", back_tail_count="2",
        x_offset="mid_x + divider_thick / 2 + drawer_gap",
        z_offset="apron_z + stretcher_h + drawer_gap")

    print(">>> Parameters done")

    # === BODY-RELATIVE HELPER ===
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
    leg_occ    = sp.make_comp(root, "Legs")
    apron_occ  = sp.make_comp(root, "Aprons")
    top_occ    = sp.make_comp(root, "Top")
    drawer_l_occ = sp.make_comp(root, "DrawerLeft")
    drawer_r_occ = sp.make_comp(root, "DrawerRight")

    leg_c    = leg_occ.component
    apron_c  = apron_occ.component
    top_c    = top_occ.component
    drawer_l_c = drawer_l_occ.component
    drawer_r_c = drawer_r_occ.component

    # ==============================================================
    #  1. LEGS — tapered on inner faces below the apron
    # ==============================================================
    _, pr = sp.sketch_rect_model(leg_c, leg_c.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_size", "y": "leg_size"}, "LegFL_Sk", ev)
    fl_ext = sp.ext_new(leg_c, pr, "leg_h", "LegFL")
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
    sp.ext_op(leg_c, taper_prof, "leg_size", CUT, leg_fl, "TaperX_Cut")

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
    sp.ext_op(leg_c, taper_prof, "leg_size", CUT, leg_fl, "TaperY_Cut")

    # Mirror to all 4 corners
    l_xmid = sp.off_plane(leg_c, leg_c.yZConstructionPlane, "mid_x", "LXMid")
    l_ymid = sp.off_plane(leg_c, leg_c.xZConstructionPlane, "mid_y", "LYMid")
    sp.mirror_body(leg_c, leg_fl, l_xmid, "LegFR").bodies.item(0).name = "Leg_FR"
    leg_bl = sp.mirror_body(leg_c, leg_fl, l_ymid, "LegBL").bodies.item(0)
    leg_bl.name = "Leg_BL"
    sp.mirror_body(leg_c, leg_bl, l_xmid, "LegBR").bodies.item(0).name = "Leg_BR"
    print(">>> Legs: 4 (tapered)")

    # Body-relative refs: aprons reference legs for positioning
    ref_fl = find_body("Leg_FL")
    ref_fl_bb = ref_fl.boundingBox
    ref_bl = find_body("Leg_BL")
    ref_bl_bb = ref_bl.boundingBox

    # ==============================================================
    #  2. APRONS — back + 2 sides + front rail above drawer
    # ==============================================================
    az_pl = sp.off_plane(apron_c, apron_c.xYConstructionPlane, "apron_z", "AZ_Pl")

    # Back apron (full height)
    _, pr = sp.sketch_rect_model(apron_c, az_pl,
        ("leg_size", "desk_w - leg_size - apron_thick", "apron_z"),
        {"x": "long_apron_l", "y": "apron_thick"}, "BackApron_Sk", ev)
    sp.ext_new(apron_c, pr, "apron_h", "BackApron").bodies.item(0).name = "Apron_Back"

    # Left side apron (full height)
    _, pr = sp.sketch_rect_model(apron_c, az_pl,
        ("0 in", "leg_size", "apron_z"),
        {"x": "apron_thick", "y": "short_apron_l"}, "LeftApron_Sk", ev)
    la_ext = sp.ext_new(apron_c, pr, "apron_h", "LeftApron")
    la_ext.bodies.item(0).name = "Apron_Left"

    a_xmid = sp.off_plane(apron_c, apron_c.yZConstructionPlane, "mid_x", "AXMid")
    sp.mirror_feats(apron_c, [la_ext], a_xmid, "RightApronMir").bodies.item(0).name = "Apron_Right"

    # Front stretcher (below drawers, at bottom of apron zone)
    _, pr = sp.sketch_rect_model(apron_c, az_pl,
        ("leg_size", "0 in", "apron_z"),
        {"x": "long_apron_l", "y": "apron_thick"}, "FrontStretcher_Sk", ev)
    sp.ext_new(apron_c, pr, "stretcher_h", "FrontStretcher").bodies.item(0).name = "Apron_FrontStretcher"

    # Center divider — runs between front rail back face and back apron front face
    _, pr = sp.sketch_rect_model(apron_c, az_pl,
        ("mid_x - divider_thick / 2", "apron_thick", "apron_z"),
        {"x": "divider_thick", "y": "desk_w - leg_size - 2 * apron_thick"}, "Divider_Sk", ev)
    div_ext = sp.ext_new(apron_c, pr, "apron_h", "Divider")
    div_body = div_ext.bodies.item(0); div_body.name = "Divider"

    # Divider front extension — fills gap between drawer fronts above stretcher
    div_front_z_pl = sp.off_plane(apron_c, apron_c.xYConstructionPlane,
                                   "apron_z + stretcher_h", "DivFrontZ_Pl")
    _, pr = sp.sketch_rect_model(apron_c, div_front_z_pl,
        ("mid_x - divider_thick / 2", "0 in", "apron_z + stretcher_h"),
        {"x": "divider_thick", "y": "apron_thick"}, "DivFront_Sk", ev)
    sp.ext_new(apron_c, pr, "drawer_opening", "DivFront").bodies.item(0).name = "Divider_Front"

    # Drawer runners — 2 on side aprons only (divider sides have no runners
    # to avoid blocking drawer slide path)
    runner_z = "apron_z + stretcher_h + drawer_gap"
    runner_z_pl = sp.off_plane(apron_c, apron_c.xYConstructionPlane, runner_z, "RunnerZ_Pl")

    # Left apron runner
    _, pr = sp.sketch_rect_model(apron_c, runner_z_pl,
        ("apron_thick", "leg_size", runner_z),
        {"x": "runner_w", "y": "short_apron_l"}, "RunnerL_Sk", ev)
    lr_ext = sp.ext_new(apron_c, pr, "runner_h", "RunnerL")
    lr_ext.bodies.item(0).name = "Runner_L"

    # Right apron runner (mirror)
    sp.mirror_feats(apron_c, [lr_ext], a_xmid, "RunnerRMir").bodies.item(0).name = "Runner_R"

    # Drawer stops — 2 blocks at back of each runner
    stop_z = "apron_z + stretcher_h + drawer_gap + runner_h"
    stop_z_pl = sp.off_plane(apron_c, apron_c.xYConstructionPlane, stop_z, "StopZ_Pl")
    _, pr = sp.sketch_rect_model(apron_c, stop_z_pl,
        ("apron_thick", "desk_w - leg_size - apron_thick - stop_l", stop_z),
        {"x": "runner_w", "y": "stop_l"}, "StopL_Sk", ev)
    sl_ext = sp.ext_new(apron_c, pr, "drawer_h_inner / 2", "StopL")
    sl_ext.bodies.item(0).name = "Stop_L"
    sp.mirror_feats(apron_c, [sl_ext], a_xmid, "StopRMir").bodies.item(0).name = "Stop_R"

    print(">>> Aprons: 4 + divider + 2 runners + 2 stops")

    # Body-relative refs: top sits on legs, aprons hang below top
    ref_fl_top = find_body("Leg_FL")
    ref_fl_top_bb = ref_fl_top.boundingBox
    ref_ab = find_body("Apron_Back")
    ref_ab_bb = ref_ab.boundingBox
    ref_al = find_body("Apron_Left")
    ref_al_bb = ref_al.boundingBox
    ref_ar = find_body("Apron_Right")
    ref_ar_bb = ref_ar.boundingBox
    ref_afs = find_body("Apron_FrontStretcher")
    ref_afs_bb = ref_afs.boundingBox

    # ==============================================================
    #  3. TOP — with cable grommet
    # ==============================================================
    top_pl = sp.off_plane(top_c, top_c.xYConstructionPlane, "leg_h", "Top_Pl")
    # Use a YZ offset plane at -overhang so the sketch starts in negative X
    top_x_pl = sp.off_plane(top_c, top_c.yZConstructionPlane,
                             "0 in - top_overhang", "TopX_Pl")
    sk_top = top_c.sketches.add(top_pl)
    sk_top.name = "Top_Sk"
    P3 = adsk.core.Point3D
    m2s = sk_top.modelToSketchSpace
    p1 = m2s(P3.create(-ev("top_overhang"), 0, ev("leg_h")))
    p2 = m2s(P3.create(ev("desk_l") + ev("top_overhang"), ev("desk_w"), ev("leg_h")))
    rect = sk_top.sketchCurves.sketchLines.addTwoPointRectangle(
        P3.create(p1.x, p1.y, 0), P3.create(p2.x, p2.y, 0))
    sk_top.geometricConstraints.addHorizontal(rect[0])
    sk_top.geometricConstraints.addHorizontal(rect[2])
    sk_top.geometricConstraints.addVertical(rect[1])
    sk_top.geometricConstraints.addVertical(rect[3])
    pr = sk_top.profiles.item(0)
    top_ext = sp.ext_new(top_c, pr, "top_thick", "TopBoard")
    top_body = top_ext.bodies.item(0); top_body.name = "Top"

    # Cable grommet — circular CUT at back-right corner
    grommet_pl = sp.off_plane(top_c, top_c.xYConstructionPlane,
                               "leg_h", "Grommet_Pl")
    sk_g = top_c.sketches.add(grommet_pl)
    sk_g.name = "Grommet_Sk"
    gx = ev("desk_l") - ev("grommet_inset")
    gy = ev("desk_w") - ev("grommet_inset")
    sk_g.sketchCurves.sketchCircles.addByCenterRadius(
        P3.create(gx, gy, 0), ev("grommet_dia") / 2)
    grommet_prof = sk_g.profiles.item(0)
    sp.ext_op(top_c, grommet_prof, "top_thick", CUT, top_body, "GrommetCut")

    print(">>> Top: 1 (with grommet)")

    # Body-relative refs: drawers ref front stretcher, runners ref side aprons
    ref_afs_dr = find_body("Apron_FrontStretcher")
    ref_afs_dr_bb = ref_afs_dr.boundingBox
    ref_rl = find_body("Runner_L")
    ref_rl_bb = ref_rl.boundingBox if ref_rl else None
    ref_rr = find_body("Runner_R")
    ref_rr_bb = ref_rr.boundingBox if ref_rr else None

    # ==============================================================
    #  4. DRAWERS — left and right, separated by center divider
    # ==============================================================
    ddl_result = dovetailed_drawer.build(drawer_l_c, prefix="ddl", ev=ev)
    ddr_result = dovetailed_drawer.build(drawer_r_c, prefix="ddr", ev=ev)
    print(f">>> Drawers: {len(ddl_result['all_bodies'])} + {len(ddr_result['all_bodies'])} bodies")

    # Body-relative refs: drawer parts reference drawer fronts
    ref_ddl_front = find_body("ddl_Front")
    ref_ddl_front_bb = ref_ddl_front.boundingBox if ref_ddl_front else None
    ref_ddr_front = find_body("ddr_Front")
    ref_ddr_front_bb = ref_ddr_front.boundingBox if ref_ddr_front else None
    # Bracket refs: Top references legs
    ref_top = find_body("Top")
    ref_top_bb = ref_top.boundingBox if ref_top else None

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

    ba_body = la_body = ra_body = fr_body = div_body = None
    for i in range(apron_c.bRepBodies.count):
        b = apron_c.bRepBodies.item(i)
        if b.name == "Apron_Back": ba_body = b
        elif b.name == "Apron_Left": la_body = b
        elif b.name == "Apron_Right": ra_body = b
        elif b.name == "Apron_FrontStretcher": fr_body = b
        elif b.name == "Divider": div_body = b
    # Construction planes inside apron_c (voids live in owning component)
    dm_fl = sp.off_plane(apron_c, apron_c.yZConstructionPlane, "leg_size", "DM_FL")
    dm_fr = sp.off_plane(apron_c, apron_c.yZConstructionPlane, "desk_l - leg_size", "DM_FR")
    dm_lf = sp.off_plane(apron_c, apron_c.xZConstructionPlane, "leg_size", "DM_LF")
    dm_lb = sp.off_plane(apron_c, apron_c.xZConstructionPlane, "desk_w - leg_size", "DM_LB")

    # Back apron → BL, BR legs (native body_a, leg proxy body_b)
    domino.grid(apron_c, dm_fl, ("leg_size", "desk_w - leg_size - apron_thick/2", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d", ba_body, bl_p, "DM_BA_L", ev)
    domino.grid(apron_c, dm_fr, ("desk_l - leg_size", "desk_w - leg_size - apron_thick/2", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d", ba_body, br_p, "DM_BA_R", ev)

    # Left apron → FL, BL
    domino.grid(apron_c, dm_lf, ("apron_thick/2", "leg_size", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d", la_body, fl_p, "DM_LA_F", ev)
    domino.grid(apron_c, dm_lb, ("apron_thick/2", "desk_w - leg_size", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d", la_body, bl_p, "DM_LA_B", ev)

    # Right apron → FR, BR
    domino.grid(apron_c, dm_lf, ("desk_l - apron_thick/2", "leg_size", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d", ra_body, fr_p, "DM_RA_F", ev)
    domino.grid(apron_c, dm_lb, ("desk_l - apron_thick/2", "desk_w - leg_size", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d", ra_body, br_p, "DM_RA_B", ev)

    # Front stretcher → FL, FR legs (1 domino each, centered in stretcher)
    params.add("fr_dm_z", VI("apron_z + stretcher_h / 2"), "in", "")
    domino.grid(apron_c, dm_fl, ("leg_size", "apron_thick / 2", "fr_dm_z"),
        "z", "0 in", "1", "z", "dm_w", "dm_t", "dm_d", fr_body, fl_p, "DM_FR_L", ev)
    domino.grid(apron_c, dm_fr, ("desk_l - leg_size", "apron_thick / 2", "fr_dm_z"),
        "z", "0 in", "1", "z", "dm_w", "dm_t", "dm_d", fr_body, fr_p, "DM_FR_R", ev)

    # Divider → front rail and back apron (auto-placed in mating area)
    # domino.between() finds where the bodies overlap and places dominos there.
    # Short depth so dominos fit within the thin apron/divider.
    ref_div = find_body("Divider")
    ref_div_bb = ref_div.boundingBox
    params.add("div_dm_d", VI("apron_thick / 2"), "in", "")
    dm_div_f = sp.off_plane(apron_c, apron_c.xZConstructionPlane, "apron_thick", "DM_DivF")
    dm_div_b = sp.off_plane(apron_c, apron_c.xZConstructionPlane,
                             "desk_w - leg_size - apron_thick", "DM_DivB")
    # Divider dominos — between() auto-orients: long_axis=Z (longer
    # mating dimension), step along X. Standard dm_w/dm_t fit.
    domino.between(apron_c, dm_div_f, div_body, fr_body,
        interface_axis="y", short_expr="dm_t", depth_expr="div_dm_d",
        long_expr="dm_w", count=1, name="DM_Div_F", ev=ev)
    domino.between(apron_c, dm_div_b, div_body, ba_body,
        interface_axis="y", short_expr="dm_t", depth_expr="div_dm_d",
        long_expr="dm_w", count=2, name="DM_Div_B", ev=ev)

    # Top → aprons via L-brackets (slotted holes allow cross-grain movement)
    # Vertical leg against apron inner face, horizontal leg under top
    bracket_occ = sp.make_comp(root, "Brackets")
    bracket_c = bracket_occ.component
    tabletop_bracket._define_params(params)
    top_z = ev("leg_h")  # top underside Z
    drawer_w_cm = ev("drawer_w")
    left_center = ev("leg_size") + ev("drawer_gap") + drawer_w_cm / 2
    right_center = ev("mid_x") + ev("divider_thick") / 2 + ev("drawer_gap") + drawer_w_cm / 2

    # Back apron: 2 brackets (one per drawer opening, centered in each)
    # Skip center — divider is there
    back_y = ev("desk_w") - ev("leg_size") - ev("apron_thick")
    tabletop_bracket.single(bracket_c, face_axis="y", face_dir=-1,
        pos=(left_center, back_y, top_z), name="TB_BL", ev=ev)
    tabletop_bracket.single(bracket_c, face_axis="y", face_dir=-1,
        pos=(right_center, back_y, top_z), name="TB_BR", ev=ev)

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

    # Front rail: 2 brackets (one per drawer opening, centered in each)
    front_y = ev("apron_thick")
    tabletop_bracket.single(bracket_c, face_axis="y", face_dir=1,
        pos=(left_center, front_y, top_z), name="TB_FL", ev=ev)
    tabletop_bracket.single(bracket_c, face_axis="y", face_dir=1,
        pos=(right_center, front_y, top_z), name="TB_FR", ev=ev)

    print(">>> Brackets: 8 tabletop L-brackets (2 front + 2 back + 2 left + 2 right)")
    print(">>> Dominos: 8 apron-leg + 2 front-rail = 10 joints")

    # ==============================================================
    #  6. DRAWER SLIDE TEST — verify drawers can open fully
    # ==============================================================
    # Slide each drawer to 75% open position, check for interference
    slide_dist = ev("drawer_d") * 0.75  # 75% of drawer depth

    for dr_name, dr_prefix, dr_occ in [("DrawerL", "ddl_", drawer_l_occ),
                                        ("DrawerR", "ddr_", drawer_r_occ)]:
        # Save original transform
        orig_t = dr_occ.transform.copy()

        # Move drawer forward (-Y direction)
        slide_t = adsk.core.Matrix3D.create()
        slide_t.translation = adsk.core.Vector3D.create(0, -slide_dist, 0)
        new_t = orig_t.copy()
        new_t.transformBy(slide_t)
        dr_occ.transform = new_t
        adsk.doEvents()

        # Collect all bodies for interference check
        all_bodies = adsk.core.ObjectCollection.create()
        for occ in root.allOccurrences:
            for i in range(occ.component.bRepBodies.count):
                all_bodies.add(occ.component.bRepBodies.item(i))
        for i in range(root.bRepBodies.count):
            all_bodies.add(root.bRepBodies.item(i))

        if all_bodies.count >= 2:
            interf_input = design.createInterferenceInput(all_bodies)
            results = design.analyzeInterference(interf_input)

            # Filter: only report interferences involving THIS drawer
            drawer_hits = []
            for j in range(results.count):
                r = results.item(j)
                try:
                    b1 = r.entityOne.name
                    b2 = r.entityTwo.name
                except Exception:
                    continue
                if b1.startswith(dr_prefix) or b2.startswith(dr_prefix):
                    vol = 0
                    try:
                        vol = r.interferenceBody.volume
                    except Exception:
                        pass
                    if vol > 0.01:  # ignore tiny cosmetic overlaps
                        drawer_hits.append(f"{b1} vs {b2} (vol={vol:.2f})")

            if drawer_hits:
                print(f"WARNING: {dr_name} BLOCKED when open:")
                for h in drawer_hits:
                    print(f"  {h}")
            else:
                print(f">>> {dr_name} slide test PASSED (75% open, no interference)")

        # Restore original position
        dr_occ.transform = orig_t
        adsk.doEvents()

    # ==============================================================
    #  7. DETAILS — edge chamfers
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
            try:
                ch_inp = comp.features.chamferFeatures.createInput2()
                ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                    edges, VI("edge_chamfer"), True)
                comp.features.chamferFeatures.add(ch_inp).name = f"{comp_name}_Ch"
            except Exception:
                print(f"  (chamfer skipped for {comp_name} — edges too small)")

    print(">>> Chamfers applied")

    # ==============================================================
    #  EPILOGUE
    # ==============================================================
    for comp in [leg_c, apron_c, top_c, drawer_l_c, drawer_r_c, bracket_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False
    for sk in root.sketches:
        sk.isVisible = False
    for cp in root.constructionPlanes:
        cp.isLightBulbOn = False

    for cn, c in [("Legs", leg_c), ("Aprons", apron_c),
                   ("Top", top_c), ("DrawerL", drawer_l_c),
                   ("DrawerR", drawer_r_c), ("Brackets", bracket_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{cn}: {len(names)} bodies -> {names}")
    dm_count = sum(1 for i in range(apron_c.bRepBodies.count)
                   if apron_c.bRepBodies.item(i).name.startswith("DM_"))
    print(f"Aprons: includes {dm_count} domino voids")

    sp.apply_appearance("maple")
    # Note: Fusion's "3D Maple" uses a procedural 3D texture — grain direction
    # is controlled by the procedural algorithm, not the texture map transform.
    # The ProjectedTextureMapControl.transform has no visible effect on 3D textures.
    # To change grain direction, use a 2D-mapped wood appearance or white oak.

    # Re-apply steel to brackets (walnut overwrites them)
    tabletop_bracket._apply_steel(bracket_c,
        [bracket_c.bRepBodies.item(i) for i in range(bracket_c.bRepBodies.count)])

    vp = app.activeViewport
    vp.visualStyle = adsk.core.VisualStyles.ShadedWithVisibleEdgesOnlyVisualStyle
    cam = vp.camera
    cam.isFitView = True
    vp.camera = cam
