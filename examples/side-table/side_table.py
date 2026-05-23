"""
Modern Side Table / Nightstand
==============================
22"L x 16"W x 24"H, 0.75" top, 1.5" square legs.
Single dovetailed drawer below top, three aprons (back + two sides) with
domino joinery, two front stretchers (upper + lower) framing the drawer
opening, 3" bar pull, leg chamfers, top fillet. Walnut body with spalted
maple drawer front.

Coordinate system:
  X = length (22")  Y = width (16")  Z = height (24")

Components:
  Legs    — 4 square legs (with mortise pockets)
  Aprons  — 3 apron rails + 2 front stretchers with domino joinery
  Top     — solid panel with edge fillet
  Drawer  — dovetailed drawer box with 3" bar pull

Bodies: 16
  Legs(4) + Aprons(3) + Stretchers(2) + Top(1) + Drawer(5) + Pull(1) = 16
"""
import adsk.core, adsk.fusion

from helpers import sp
from woodworking.templates import dovetailed_drawer
from woodworking.templates import domino
from woodworking.templates import pull
from woodworking.templates import tabletop_bracket

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation


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
        ("table_l",     "22 in",     "in"),
        ("table_w",     "16 in",     "in"),
        ("table_h",     "24 in",     "in"),
        ("top_thick",   "0.75 in",   "in"),
        ("leg_size",    "1.5 in",    "in"),
        ("apron_h",     "6 in",      "in"),
        ("apron_thick", "0.75 in",   "in"),
        ("drawer_gap",  "0.0625 in", "in"),
        ("leg_ch",      "0.125 in",  "in"),
        ("top_fil",     "0.0625 in", "in"),
        ("str_h",       "1 in",      "in"),
        ("str_thick",   "0.75 in",   "in"),
        ("top_oh",      "0.25 in",   "in"),
        ("leg_taper",   "0.375 in",  "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    # Domino parameters — apron joints (6mm cutter for 0.75" stock)
    for pname, expr, unit in [
        ("dm_ap_t", "6 mm",  "in"),   # short (cutter dia)
        ("dm_ap_w", "30 mm", "in"),   # long
        ("dm_ap_d", "15 mm", "in"),   # depth per side
    ]:
        params.add(pname, VI(expr), unit, "")

    # Domino parameters — stretcher joints (5mm cutter, 1" tall rail)
    for pname, expr, unit in [
        ("dm_st_t", "5 mm",  "in"),
        ("dm_st_w", "20 mm", "in"),
        ("dm_st_d", "12 mm", "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    # Pull parameters
    pull.define_params(params, prefix="pl", style="bar_3in")

    # Derived parameters
    for pname, expr, unit in [
        ("leg_h",         "table_h - top_thick",                    "in"),
        ("apron_z",       "table_h - top_thick - apron_h",          "in"),
        ("long_apron_l",  "table_l - 2 * leg_size",                 "in"),
        ("short_apron_l", "table_w - 2 * leg_size",                 "in"),
        ("mid_x",         "table_l / 2",                            "in"),
        ("mid_y",         "table_w / 2",                            "in"),
        ("dm_ap_sp",      "apron_h / 3",                            "in"),
        ("drawer_w",      "long_apron_l - 2 * drawer_gap",          "in"),
        ("drawer_d",      "table_w - apron_thick - drawer_gap",     "in"),
        ("drawer_h",      "apron_h - 2 * str_h - 2 * drawer_gap",   "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    # Drawer template params
    dovetailed_drawer.define_params(params, prefix="dd",
        drawer_w="drawer_w", drawer_d="drawer_d", drawer_h="drawer_h",
        front_thick="0.625 in", side_thick="0.5 in",
        bottom_thick="0.25 in",
        bg_depth="0.1875 in", bg_up="0.1875 in",
        dt_angle="8 deg", dt_tail_w="0.5 in",
        front_tail_count="3", back_tail_count="3",
        x_offset="leg_size + drawer_gap",
        z_offset="apron_z + str_h + drawer_gap")

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
    leg_occ    = sp.make_comp(root, "Legs")
    apron_occ  = sp.make_comp(root, "Aprons")
    top_occ    = sp.make_comp(root, "Top")
    drawer_occ = sp.make_comp(root, "Drawer")

    leg_c    = leg_occ.component
    apron_c  = apron_occ.component
    top_c    = top_occ.component
    drawer_c = drawer_occ.component

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

    # Taper inner faces of FL leg (below apron line → foot)
    P3 = adsk.core.Point3D.create
    ls_v = ev("leg_size"); az_v = ev("apron_z"); lt_v = ev("leg_taper")
    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation

    # X-taper on XZ plane (inner X face tapers inward at foot)
    sk_tx = leg_c.sketches.add(leg_c.xZConstructionPlane)
    l_tx = sk_tx.sketchCurves.sketchLines
    la = l_tx.addByTwoPoints(P3(ls_v, az_v, 0), P3(ls_v, 0, 0))
    lb = l_tx.addByTwoPoints(la.endSketchPoint, P3(ls_v - lt_v, 0, 0))
    l_tx.addByTwoPoints(lb.endSketchPoint, la.startSketchPoint)
    sk_tx.geometricConstraints.addVertical(la)
    sk_tx.geometricConstraints.addHorizontal(lb)
    d_tx = sk_tx.sketchDimensions
    d_tx.addDistanceDimension(sk_tx.originPoint, la.startSketchPoint, H,
        P3(ls_v / 2, az_v + 1, 0)).parameter.expression = "leg_size"
    d_tx.addDistanceDimension(sk_tx.originPoint, la.startSketchPoint, V,
        P3(ls_v + 1, az_v / 2, 0)).parameter.expression = "apron_z"
    d_tx.addDistanceDimension(lb.startSketchPoint, lb.endSketchPoint, H,
        P3(ls_v - lt_v / 2, -1, 0)).parameter.expression = "leg_taper"
    sk_tx.name = "TaperX_Sk"
    sp.ext_op(leg_c, sp.smallest_profile(sk_tx), "leg_size",
              CUT, leg_fl, "TaperX_Cut")

    # Y-taper on YZ plane (inner Y face tapers inward at foot)
    sk_ty = leg_c.sketches.add(leg_c.yZConstructionPlane)
    m2s = sk_ty.modelToSketchSpace
    a2 = m2s(P3(0, ls_v, az_v))
    b2 = m2s(P3(0, ls_v, 0))
    c2 = m2s(P3(0, ls_v - lt_v, 0))
    l_ty = sk_ty.sketchCurves.sketchLines
    la2 = l_ty.addByTwoPoints(P3(a2.x, a2.y, 0), P3(b2.x, b2.y, 0))
    lb2 = l_ty.addByTwoPoints(la2.endSketchPoint, P3(c2.x, c2.y, 0))
    l_ty.addByTwoPoints(lb2.endSketchPoint, la2.startSketchPoint)
    orient = sp.probe_orientations(sk_ty, 0, ls_v, az_v)
    V_enum = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
    if orient['z'] == V_enum:
        sk_ty.geometricConstraints.addVertical(la2)
    else:
        sk_ty.geometricConstraints.addHorizontal(la2)
    if orient['y'] == V_enum:
        sk_ty.geometricConstraints.addVertical(lb2)
    else:
        sk_ty.geometricConstraints.addHorizontal(lb2)
    d_ty = sk_ty.sketchDimensions
    d_ty.addDistanceDimension(sk_ty.originPoint, la2.startSketchPoint,
        orient['y'], P3(a2.x - 1, a2.y + 1, 0)
        ).parameter.expression = "leg_size"
    d_ty.addDistanceDimension(sk_ty.originPoint, la2.startSketchPoint,
        orient['z'], P3(a2.x + 1, (a2.y + b2.y) / 2, 0)
        ).parameter.expression = "apron_z"
    d_ty.addDistanceDimension(lb2.startSketchPoint, lb2.endSketchPoint,
        orient['y'], P3((b2.x + c2.x) / 2, b2.y - 1, 0)
        ).parameter.expression = "leg_taper"
    sk_ty.name = "TaperY_Sk"
    sp.ext_op(leg_c, sp.smallest_profile(sk_ty), "leg_size",
              CUT, leg_fl, "TaperY_Cut")

    print(">>> Leg taper: 2 CUTs on FL (mirrors handle rest)")

    l_xmid = sp.off_plane(leg_c, leg_c.yZConstructionPlane, "mid_x", "LXMid")
    l_ymid = sp.off_plane(leg_c, leg_c.xZConstructionPlane, "mid_y", "LYMid")

    leg_fr = sp.mirror_body(leg_c, leg_fl, l_xmid, "LegFR_Mir").bodies.item(0)
    leg_fr.name = "Leg_FR"
    leg_bl = sp.mirror_body(leg_c, leg_fl, l_ymid, "LegBL_Mir").bodies.item(0)
    leg_bl.name = "Leg_BL"
    leg_br = sp.mirror_body(leg_c, leg_bl, l_xmid, "LegBR_Mir").bodies.item(0)
    leg_br.name = "Leg_BR"

    print(">>> Legs: 4 bodies")

    # -- Body-relative references: aprons + stretchers relative to legs --
    ref_leg_fl = find_body("Leg_FL")
    ref_leg_fl_bb = ref_leg_fl.boundingBox
    ref_leg_fr = find_body("Leg_FR")
    ref_leg_fr_bb = ref_leg_fr.boundingBox
    ref_leg_bl = find_body("Leg_BL")
    ref_leg_bl_bb = ref_leg_bl.boundingBox

    # ==============================================================
    #  2. APRONS + FRONT STRETCHERS
    # ==============================================================
    apron_z_pl = sp.off_plane(apron_c, apron_c.xYConstructionPlane,
        "apron_z", "ApronZ_Pl")

    # Back apron — flush with back of legs
    _, pr = sp.sketch_rect_model(apron_c, apron_z_pl,
        ("leg_size", "table_w - apron_thick", "apron_z"),
        {"x": "long_apron_l", "y": "apron_thick"},
        "BackApron_Sk", ev)
    apron_back = sp.ext_new(apron_c, pr, "apron_h", "BackApron").bodies.item(0)
    apron_back.name = "Apron_Back"

    # Left side apron — between front and back legs on left side
    _, pr = sp.sketch_rect_model(apron_c, apron_z_pl,
        ("0 in", "leg_size", "apron_z"),
        {"x": "apron_thick", "y": "short_apron_l"},
        "LeftApron_Sk", ev)
    apron_left = sp.ext_new(apron_c, pr, "apron_h", "LeftApron").bodies.item(0)
    apron_left.name = "Apron_Left"

    # (Right side apron mirrored after joinery)

    # Upper front stretcher — top rail framing drawer opening
    str_upper_pl = sp.off_plane(apron_c, apron_c.xYConstructionPlane,
        "apron_z + apron_h - str_h", "StrUpperZ_Pl")
    _, pr = sp.sketch_rect_model(apron_c, str_upper_pl,
        ("leg_size", "0 in", "apron_z + apron_h - str_h"),
        {"x": "long_apron_l", "y": "str_thick"},
        "UpperStr_Sk", ev)
    str_upper = sp.ext_new(apron_c, pr, "str_h", "UpperStr").bodies.item(0)
    str_upper.name = "Str_Upper"

    # Lower front stretcher — bottom rail framing drawer opening
    _, pr = sp.sketch_rect_model(apron_c, apron_z_pl,
        ("leg_size", "0 in", "apron_z"),
        {"x": "long_apron_l", "y": "str_thick"},
        "LowerStr_Sk", ev)
    str_lower = sp.ext_new(apron_c, pr, "str_h", "LowerStr").bodies.item(0)
    str_lower.name = "Str_Lower"

    # Mirror left apron → right
    a_xmid = sp.off_plane(apron_c, apron_c.yZConstructionPlane,
        "mid_x", "AXMid")
    apron_right = sp.mirror_body(apron_c, apron_left, a_xmid,
        "RightApronMir").bodies.item(0)
    apron_right.name = "Apron_Right"

    print(">>> Aprons: 5 bodies complete (3 aprons + 2 stretchers)")

    # -- Body-relative references: dominos relative to aprons + stretchers --
    ref_apron_back = find_body("Apron_Back")
    ref_apron_back_bb = ref_apron_back.boundingBox
    ref_apron_left = find_body("Apron_Left")
    ref_apron_left_bb = ref_apron_left.boundingBox
    ref_apron_right = find_body("Apron_Right")
    ref_apron_right_bb = ref_apron_right.boundingBox
    ref_str_upper = find_body("Str_Upper")
    ref_str_upper_bb = ref_str_upper.boundingBox
    ref_str_lower = find_body("Str_Lower")
    ref_str_lower_bb = ref_str_lower.boundingBox

    # ==============================================================
    #  3. DOMINO JOINERY — loose tenons at all rail-to-leg interfaces
    # ==============================================================
    # Leg proxies for cross-component CUTs
    fl_proxy = leg_fl.createForAssemblyContext(leg_occ)
    fr_proxy = leg_fr.createForAssemblyContext(leg_occ)
    bl_proxy = leg_bl.createForAssemblyContext(leg_occ)
    br_proxy = leg_br.createForAssemblyContext(leg_occ)

    # Construction planes inside apron_c (voids live in owning component)
    dm_xl = sp.off_plane(apron_c, apron_c.yZConstructionPlane,
        "leg_size", "DM_XL_Pl")
    dm_xr = sp.off_plane(apron_c, apron_c.yZConstructionPlane,
        "table_l - leg_size", "DM_XR_Pl")
    dm_yf = sp.off_plane(apron_c, apron_c.xZConstructionPlane,
        "leg_size", "DM_YF_Pl")
    dm_yb = sp.off_plane(apron_c, apron_c.xZConstructionPlane,
        "table_w - leg_size", "DM_YB_Pl")

    # -- Back apron: 2 dominos per end, along Z --
    domino.grid(apron_c, dm_xl,
        start=("leg_size", "table_w - apron_thick / 2", "apron_z + dm_ap_sp"),
        step_axis="z", step_expr="dm_ap_sp", count_expr="2",
        long_axis="z", long_expr="dm_ap_w", short_expr="dm_ap_t",
        depth_expr="dm_ap_d", body_a=apron_back, body_b=bl_proxy,
        name="DM_BA_L", ev=ev)

    domino.grid(apron_c, dm_xr,
        start=("table_l - leg_size", "table_w - apron_thick / 2",
               "apron_z + dm_ap_sp"),
        step_axis="z", step_expr="dm_ap_sp", count_expr="2",
        long_axis="z", long_expr="dm_ap_w", short_expr="dm_ap_t",
        depth_expr="dm_ap_d", body_a=apron_back, body_b=br_proxy,
        name="DM_BA_R", ev=ev)

    # -- Left side apron: 2 dominos per end, along Z --
    domino.grid(apron_c, dm_yf,
        start=("apron_thick / 2", "leg_size", "apron_z + dm_ap_sp"),
        step_axis="z", step_expr="dm_ap_sp", count_expr="2",
        long_axis="z", long_expr="dm_ap_w", short_expr="dm_ap_t",
        depth_expr="dm_ap_d", body_a=apron_left, body_b=fl_proxy,
        name="DM_LA_F", ev=ev)

    domino.grid(apron_c, dm_yb,
        start=("apron_thick / 2", "table_w - leg_size",
               "apron_z + dm_ap_sp"),
        step_axis="z", step_expr="dm_ap_sp", count_expr="2",
        long_axis="z", long_expr="dm_ap_w", short_expr="dm_ap_t",
        depth_expr="dm_ap_d", body_a=apron_left, body_b=bl_proxy,
        name="DM_LA_B", ev=ev)

    # -- Right side apron: 2 dominos per end, along Z --
    domino.grid(apron_c, dm_yf,
        start=("table_l - apron_thick / 2", "leg_size",
               "apron_z + dm_ap_sp"),
        step_axis="z", step_expr="dm_ap_sp", count_expr="2",
        long_axis="z", long_expr="dm_ap_w", short_expr="dm_ap_t",
        depth_expr="dm_ap_d", body_a=apron_right, body_b=fr_proxy,
        name="DM_RA_F", ev=ev)

    domino.grid(apron_c, dm_yb,
        start=("table_l - apron_thick / 2", "table_w - leg_size",
               "apron_z + dm_ap_sp"),
        step_axis="z", step_expr="dm_ap_sp", count_expr="2",
        long_axis="z", long_expr="dm_ap_w", short_expr="dm_ap_t",
        depth_expr="dm_ap_d", body_a=apron_right, body_b=br_proxy,
        name="DM_RA_B", ev=ev)

    # -- Upper stretcher: 1 domino per end --
    domino.single(apron_c, dm_xl,
        center=("leg_size", "str_thick / 2",
                "apron_z + apron_h - str_h / 2"),
        long_axis="z", long_expr="dm_st_w", short_expr="dm_st_t",
        depth_expr="dm_st_d", body_a=str_upper, body_b=fl_proxy,
        name="DM_SU_L", ev=ev)

    domino.single(apron_c, dm_xr,
        center=("table_l - leg_size", "str_thick / 2",
                "apron_z + apron_h - str_h / 2"),
        long_axis="z", long_expr="dm_st_w", short_expr="dm_st_t",
        depth_expr="dm_st_d", body_a=str_upper, body_b=fr_proxy,
        name="DM_SU_R", ev=ev)

    # -- Lower stretcher: 1 domino per end --
    domino.single(apron_c, dm_xl,
        center=("leg_size", "str_thick / 2", "apron_z + str_h / 2"),
        long_axis="z", long_expr="dm_st_w", short_expr="dm_st_t",
        depth_expr="dm_st_d", body_a=str_lower, body_b=fl_proxy,
        name="DM_SL_L", ev=ev)

    domino.single(apron_c, dm_xr,
        center=("table_l - leg_size", "str_thick / 2",
                "apron_z + str_h / 2"),
        long_axis="z", long_expr="dm_st_w", short_expr="dm_st_t",
        depth_expr="dm_st_d", body_a=str_lower, body_b=fr_proxy,
        name="DM_SL_R", ev=ev)

    print(">>> Dominos: 16 loose tenons (12 apron + 4 stretcher)")

    # ==============================================================
    #  4. TOP (with overhang)
    # ==============================================================
    top_pl = sp.off_plane(top_c, top_c.xYConstructionPlane, "leg_h", "Top_Pl")
    sk_top = top_c.sketches.add(top_pl)
    m2s_top = sk_top.modelToSketchSpace
    oh = ev("top_oh"); tl = ev("table_l"); tw = ev("table_w"); lh = ev("leg_h")
    c0 = m2s_top(P3(-oh, -oh, lh))
    c1 = m2s_top(P3(tl + oh, tw + oh, lh))
    rect_top = sk_top.sketchCurves.sketchLines.addTwoPointRectangle(
        P3(c0.x, c0.y, 0), P3(c1.x, c1.y, 0))
    sk_top.geometricConstraints.addHorizontal(rect_top[0])
    sk_top.geometricConstraints.addHorizontal(rect_top[2])
    sk_top.geometricConstraints.addVertical(rect_top[1])
    sk_top.geometricConstraints.addVertical(rect_top[3])
    d_top = sk_top.sketchDimensions
    d_top.addDistanceDimension(
        rect_top[0].startSketchPoint, rect_top[0].endSketchPoint,
        H, P3((c0.x + c1.x) / 2, c0.y - 1, 0)
    ).parameter.expression = "table_l + 2 * top_oh"
    d_top.addDistanceDimension(
        rect_top[1].startSketchPoint, rect_top[1].endSketchPoint,
        V, P3(c1.x + 1, (c0.y + c1.y) / 2, 0)
    ).parameter.expression = "table_w + 2 * top_oh"
    sk_top.name = "Top_Sk"
    top_body = sp.ext_new(top_c, sp.smallest_profile(sk_top),
        "top_thick", "TopBoard").bodies.item(0)
    top_body.name = "Top"

    print(">>> Top: 1 body (0.25\" overhang)")

    # ==============================================================
    #  5. TABLETOP BRACKETS — side aprons to top
    # ==============================================================
    bracket_occ = sp.make_comp(root, "Brackets")
    bracket_c = bracket_occ.component
    tb_sp = ev("short_apron_l") / 3  # spacing between brackets

    # Left side apron: 2 brackets (face_axis="x", face_dir=+1)
    tabletop_bracket.row(bracket_c, face_axis="x", face_dir=+1,
        start=(ev("apron_thick"),
               ev("leg_size") + tb_sp,
               ev("leg_h")),
        step_axis="y", step_expr=tb_sp, count=2,
        name="TB_L", ev=ev)

    # Right side apron: 2 brackets (face_axis="x", face_dir=-1)
    tabletop_bracket.row(bracket_c, face_axis="x", face_dir=-1,
        start=(ev("table_l") - ev("apron_thick"),
               ev("leg_size") + tb_sp,
               ev("leg_h")),
        step_axis="y", step_expr=tb_sp, count=2,
        name="TB_R", ev=ev)

    print(">>> Brackets: 4 tabletop brackets (2 per side apron)")

    # -- Body-relative references: drawer positioned relative to lower stretcher --
    ref_dd_str = find_body("Str_Lower")
    ref_dd_str_bb = ref_dd_str.boundingBox

    # ==============================================================
    #  7. DRAWER — dovetailed box + bar pull
    # ==============================================================
    dd_result = dovetailed_drawer.build(drawer_c, prefix="dd", ev=ev)
    dd_front = dd_result["front"]

    # -- Body-relative references: drawer parts + pull relative to dd_Front --
    ref_dd_front = find_body("dd_Front")
    ref_dd_front_bb = ref_dd_front.boundingBox

    # Install 3" bar pull on drawer front face
    pull.install(drawer_c, dd_front, drawer_c.xZConstructionPlane,
        center=("leg_size + drawer_gap + drawer_w / 2", "0 in",
                "apron_z + str_h + drawer_gap + drawer_h / 2"),
        pull_axis="x", depth_axis="y",
        prefix="pl", name="Pull", ev=ev, flip=False,
        board_thick_expr="dd_ft")

    # -- Body-relative reference: pull posts relative to pull bar --
    ref_pull_bar = find_body("Pull_Bar")
    if ref_pull_bar:
        ref_pull_bar_bb = ref_pull_bar.boundingBox

    print(">>> Drawer: %d bodies + pull" % len(dd_result["all_bodies"]))

    # ==============================================================
    #  8. DETAILS — leg chamfers + top fillet
    # ==============================================================
    # Leg bottom chamfers
    for leg_body in [leg_fl, leg_fr, leg_bl, leg_br]:
        bot_face = sp.find_face(leg_body, "z", -1)
        if bot_face is None:
            continue
        edge_coll = adsk.core.ObjectCollection.create()
        seen = set()
        for ei in range(bot_face.edges.count):
            e = bot_face.edges.item(ei)
            if e.tempId not in seen:
                seen.add(e.tempId)
                edge_coll.add(e)
        if edge_coll.count == 0:
            continue
        ch_inp = leg_c.features.chamferFeatures.createInput2()
        ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
            edge_coll, VI("leg_ch"), True)
        ch = leg_c.features.chamferFeatures.add(ch_inp)
        ch.name = f"{leg_body.name}_Ch"

    # Top edge fillet (perimeter edges of top face)
    top_face = sp.find_face(top_body, "z", +1)
    if top_face:
        edge_coll = adsk.core.ObjectCollection.create()
        seen = set()
        for ei in range(top_face.edges.count):
            e = top_face.edges.item(ei)
            if e.tempId not in seen:
                seen.add(e.tempId)
                edge_coll.add(e)
        if edge_coll.count > 0:
            fil_inp = top_c.features.filletFeatures.createInput()
            fil_inp.addConstantRadiusEdgeSet(edge_coll,
                VI("top_fil"), True)
            fil = top_c.features.filletFeatures.add(fil_inp)
            fil.name = "Top_Fillet"

    print(">>> Details: leg chamfers + top fillet")

    # ==============================================================
    #  EPILOGUE
    # ==============================================================
    # Hide construction geometry
    for comp in [leg_c, apron_c, top_c, drawer_c, bracket_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False
    for sk in root.sketches:
        sk.isVisible = False
    for cp in root.constructionPlanes:
        cp.isLightBulbOn = False

    # Print body inventory
    for comp_name, c in [("Legs", leg_c), ("Aprons", apron_c),
                          ("Top", top_c), ("Drawer", drawer_c),
                          ("Brackets", bracket_c)]:
        names = [c.bRepBodies.item(i).name
                 for i in range(c.bRepBodies.count)]
        print(f"{comp_name}: {len(names)} bodies -> {names}")

    # Appearances
    sp.apply_appearance("walnut")
    sp.apply_appearance("spalted maple", bodies=["dd_Front"])
    sp.apply_appearance("ash", bodies=["dd_Back", "dd_Left",
                                        "dd_Right", "dd_Bottom"])
    # Beech for all domino void bodies (in apron component)
    dm_names = [apron_c.bRepBodies.item(i).name
                for i in range(apron_c.bRepBodies.count)
                if apron_c.bRepBodies.item(i).name.startswith("DM_")]
    if dm_names:
        sp.apply_appearance("beech", bodies=dm_names)

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
