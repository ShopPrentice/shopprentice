import adsk.core, adsk.fusion, math
from helpers import af
from woodworking.templates import dovetail

def run(context):
    ctx = af.DesignContext()
    app, design, root = ctx.app, ctx.design, ctx.root
    params = design.userParameters
    P = adsk.core.Point3D.create
    VI = adsk.core.ValueInput.createByString
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation

    # ======================================================================
    # PARAMETERS
    # ======================================================================

    # Case envelope
    params.add("case_l",   VI("41 in"),   "in", "Case length (X)")
    params.add("case_w",   VI("20 in"),   "in", "Case width/depth (Y)")
    params.add("case_h",   VI("25 in"),   "in", "Case height (Z)")
    params.add("board_t",  VI("0.75 in"), "in", "Case board thickness")

    # Lid
    params.add("lid_t",    VI("0.75 in"), "in", "Lid thickness")
    params.add("lid_overhang", VI("0.25 in"), "in", "Lid overhang per side")

    # Bottom panel
    params.add("bottom_t", VI("0.75 in"), "in", "Bottom panel thickness")

    # Base
    params.add("leg_h",      VI("4.5 in"),  "in", "Leg height below case")
    params.add("leg_size",   VI("1.5 in"),  "in", "Leg cross-section")
    params.add("base_rail_h", VI("3.5 in"), "in", "Base rail height")
    params.add("base_rail_t", VI("0.75 in"), "in", "Base rail thickness")

    # Drawer
    params.add("drawer_h",       VI("3.5 in"),  "in", "Drawer opening height")
    params.add("drawer_front_t", VI("0.75 in"), "in", "Drawer front thickness")
    params.add("drawer_side_t",  VI("0.5 in"),  "in", "Drawer side thickness")
    params.add("drawer_bottom_t", VI("0.25 in"), "in", "Drawer bottom thickness")
    params.add("drawer_gap",     VI("0.0625 in"), "in", "Drawer clearance gap")

    # M&T for base
    params.add("mt_tw", VI("2.5 in"), "in", "Base M&T tenon width")
    params.add("mt_th", VI("0.375 in"), "in", "Base M&T tenon thickness")
    params.add("mt_td", VI("1 in"), "in", "Base M&T tenon depth")

    # Bottom dado
    params.add("dado_depth", VI("0.375 in"), "in", "Bottom dado depth")

    # Arch detail
    params.add("arch_h", VI("2 in"), "in", "Arch height on base rails")

    # Lid chamfer
    params.add("lid_chamfer", VI("0.125 in"), "in", "Lid edge chamfer")

    # ======================================================================
    # DERIVED PARAMETERS
    # ======================================================================

    params.add("case_int_l", VI("case_l - 2 * board_t"), "in", "Interior length")
    params.add("case_int_w", VI("case_w - 2 * board_t"), "in", "Interior width")
    params.add("bottom_z", VI("drawer_h"), "in", "Bottom panel top Z")
    params.add("drw_box_h", VI("drawer_h - bottom_t - 2 * drawer_gap"), "in", "Drawer box height")
    params.add("rail_int_l", VI("case_l - 2 * board_t - 2 * leg_size"), "in", "Long rail length")
    params.add("rail_int_w", VI("case_w - 2 * board_t - 2 * leg_size"), "in", "Short rail length")

    # Dovetail parameters via template
    dt_params = dovetail.define_params(params, prefix="dt",
        angle="8 deg", tail_w="0.75 in", tail_count="5",
        joint_h_expr="case_h", thick_expr="board_t")

    # ======================================================================
    # MIDPLANES
    # ======================================================================

    xmid = af.off_plane(root, root.yZConstructionPlane, "case_l / 2", "XMid")
    ymid = af.off_plane(root, root.xZConstructionPlane, "case_w / 2", "YMid")

    # ======================================================================
    # CASE COMPONENT
    # ======================================================================

    case_occ = af.make_comp(root, "Case")
    case_comp = case_occ.component

    # Front board (pin board): full case_l x case_h at Y=0
    sk_f, prof_f = af.sketch_rect_model(case_comp, case_comp.xZConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "case_l", "z": "case_h"},
        "Front_Sk", ev=ctx.ev)
    f_front = af.ext_new(case_comp, prof_f, "board_t", "FrontBoard")
    front = f_front.bodies.item(0)
    front.name = "Front"

    # Back board (pin board): at Y = case_w - board_t
    back_pl = af.off_plane(case_comp, case_comp.xZConstructionPlane,
                           "case_w - board_t", "Back_Pl")
    sk_b, prof_b = af.sketch_rect_model(case_comp, back_pl,
        ("0 in", "case_w - board_t", "0 in"),
        {"x": "case_l", "z": "case_h"},
        "Back_Sk", ev=ctx.ev)
    f_back = af.ext_new(case_comp, prof_b, "board_t", "BackBoard")
    back = f_back.bodies.item(0)
    back.name = "Back"

    # Left end board (tail board): INTERIOR width only (board_t to case_w-board_t)
    # Tails will protrude into pin boards when joined by dovetail template
    sk_l, prof_l = af.sketch_rect_model(case_comp, case_comp.yZConstructionPlane,
        ("0 in", "board_t", "0 in"),
        {"y": "case_w - 2 * board_t", "z": "case_h"},
        "Left_Sk", ev=ctx.ev)
    f_left = af.ext_new(case_comp, prof_l, "board_t", "LeftBoard")
    left = f_left.bodies.item(0)
    left.name = "Left"

    # Right end board (tail board): interior width, at X = case_l - board_t
    right_pl = af.off_plane(case_comp, case_comp.yZConstructionPlane,
                            "case_l - board_t", "Right_Pl")
    sk_r, prof_r = af.sketch_rect_model(case_comp, right_pl,
        ("case_l - board_t", "board_t", "0 in"),
        {"y": "case_w - 2 * board_t", "z": "case_h"},
        "Right_Sk", ev=ctx.ev)
    f_right = af.ext_new(case_comp, prof_r, "board_t", "RightBoard")
    right = f_right.bodies.item(0)
    right.name = "Right"

    # ======================================================================
    # BOTTOM COMPONENT
    # ======================================================================

    bot_occ = af.make_comp(root, "Bottom")
    bot_comp = bot_occ.component

    # Bottom panel: edges protrude dado_depth into case boards
    bot_pl = af.off_plane(bot_comp, bot_comp.xYConstructionPlane,
                          "drawer_h - bottom_t", "Bottom_Pl")
    sk_bot, prof_bot = af.sketch_rect_model(bot_comp, bot_pl,
        ("board_t - dado_depth", "board_t - dado_depth", "drawer_h - bottom_t"),
        {"x": "case_l - 2 * board_t + 2 * dado_depth",
         "y": "case_w - 2 * board_t + 2 * dado_depth"},
        "Bottom_Sk", ev=ctx.ev)
    f_bottom = af.ext_new(bot_comp, prof_bot, "bottom_t", "BottomBoard")
    bottom = f_bottom.bodies.item(0)
    bottom.name = "Bottom"

    # ======================================================================
    # LID COMPONENT
    # ======================================================================

    lid_occ = af.make_comp(root, "Lid")
    lid_comp = lid_occ.component

    # Lid sits ON TOP of case: Z = case_h to case_h + lid_t
    lid_pl = af.off_plane(lid_comp, lid_comp.xYConstructionPlane,
                          "case_h", "Lid_Pl")
    sk_lid, prof_lid = af.sketch_rect_model(lid_comp, lid_pl,
        ("-lid_overhang", "-lid_overhang", "case_h"),
        {"x": "case_l + 2 * lid_overhang", "y": "case_w + 2 * lid_overhang"},
        "Lid_Sk", ev=ctx.ev)
    f_lid = af.ext_new(lid_comp, prof_lid, "lid_t", "LidBoard")
    lid = f_lid.bodies.item(0)
    lid.name = "Lid"

    # ======================================================================
    # BASE COMPONENT (Legs + Rails)
    # ======================================================================

    base_occ = af.make_comp(root, "Base")
    base_comp = base_occ.component

    # Front-left leg: sketch at Z=-leg_h, extrude UP
    leg_pl = af.off_plane(base_comp, base_comp.xYConstructionPlane,
                          "-leg_h", "Leg_Pl")
    sk_leg, prof_leg = af.sketch_rect_model(base_comp, leg_pl,
        ("board_t", "board_t", "-leg_h"),
        {"x": "leg_size", "y": "leg_size"},
        "Leg_Sk", ev=ctx.ev)
    f_leg = af.ext_new(base_comp, prof_leg, "leg_h", "LegFL")
    leg_fl = f_leg.bodies.item(0)
    leg_fl.name = "Leg_FL"

    # Mirror legs to all 4 corners
    base_xmid = af.off_plane(base_comp, base_comp.yZConstructionPlane,
                             "case_l / 2", "Base_XMid")
    base_ymid = af.off_plane(base_comp, base_comp.xZConstructionPlane,
                             "case_w / 2", "Base_YMid")

    m_lr = af.mirror_body(base_comp, leg_fl, base_xmid, "LegFR_Mirror")
    leg_fr = m_lr.bodies.item(0)
    leg_fr.name = "Leg_FR"

    m_fb = af.mirror_bodies(base_comp, [leg_fl, leg_fr], base_ymid, "LegsBack_Mirror")
    leg_bl = m_fb.bodies.item(0)
    leg_bl.name = "Leg_BL"
    leg_br = m_fb.bodies.item(1)
    leg_br.name = "Leg_BR"

    # Front rail: sketch on leg_pl (Z=-leg_h), extrude UP by base_rail_h
    sk_rf, prof_rf = af.sketch_rect_model(base_comp, leg_pl,
        ("board_t + leg_size", "board_t", "-leg_h"),
        {"x": "rail_int_l", "y": "base_rail_t"},
        "RailFront_Sk", ev=ctx.ev)
    f_rf = af.ext_new(base_comp, prof_rf, "base_rail_h", "RailFrontBoard")
    rail_front = f_rf.bodies.item(0)
    rail_front.name = "Rail_Front"

    m_rail_fb = af.mirror_body(base_comp, rail_front, base_ymid, "RailBack_Mirror")
    rail_back = m_rail_fb.bodies.item(0)
    rail_back.name = "Rail_Back"

    # Left side rail
    sk_rl, prof_rl = af.sketch_rect_model(base_comp, leg_pl,
        ("board_t", "board_t + leg_size", "-leg_h"),
        {"x": "base_rail_t", "y": "rail_int_w"},
        "RailLeft_Sk", ev=ctx.ev)
    f_rl = af.ext_new(base_comp, prof_rl, "base_rail_h", "RailLeftBoard")
    rail_left = f_rl.bodies.item(0)
    rail_left.name = "Rail_Left"

    m_rail_lr = af.mirror_body(base_comp, rail_left, base_xmid, "RailRight_Mirror")
    rail_right = m_rail_lr.bodies.item(0)
    rail_right.name = "Rail_Right"

    # ======================================================================
    # DRAWER COMPONENT
    # ======================================================================

    drw_occ = af.make_comp(root, "Drawer")
    drw_comp = drw_occ.component

    # Drawer front: fills opening, flush with case front
    sk_df, prof_df = af.sketch_rect_model(drw_comp, drw_comp.xZConstructionPlane,
        ("board_t + drawer_gap", "0 in", "drawer_gap"),
        {"x": "case_l - 2 * board_t - 2 * drawer_gap", "z": "drw_box_h"},
        "DrwFront_Sk", ev=ctx.ev)
    f_df = af.ext_new(drw_comp, prof_df, "drawer_front_t", "DrwFrontBoard")
    drw_front = f_df.bodies.item(0)
    drw_front.name = "Drw_Front"

    # Drawer back
    drw_back_pl = af.off_plane(drw_comp, drw_comp.xZConstructionPlane,
        "case_w - board_t - drawer_side_t", "DrwBack_Pl")
    sk_db, prof_db = af.sketch_rect_model(drw_comp, drw_back_pl,
        ("board_t + drawer_gap + drawer_side_t",
         "case_w - board_t - drawer_side_t",
         "drawer_gap + drawer_bottom_t"),
        {"x": "case_l - 2 * board_t - 2 * drawer_gap - 2 * drawer_side_t",
         "z": "drw_box_h - drawer_bottom_t"},
        "DrwBack_Sk", ev=ctx.ev)
    f_db = af.ext_new(drw_comp, prof_db, "drawer_side_t", "DrwBackBoard")
    drw_back = f_db.bodies.item(0)
    drw_back.name = "Drw_Back"

    # Drawer left side
    drw_left_pl = af.off_plane(drw_comp, drw_comp.yZConstructionPlane,
        "board_t + drawer_gap", "DrwLeft_Pl")
    sk_dls, prof_dls = af.sketch_rect_model(drw_comp, drw_left_pl,
        ("board_t + drawer_gap", "drawer_front_t", "drawer_gap + drawer_bottom_t"),
        {"y": "case_w - 2 * board_t - drawer_front_t - drawer_side_t",
         "z": "drw_box_h - drawer_bottom_t"},
        "DrwLeft_Sk", ev=ctx.ev)
    f_dls = af.ext_new(drw_comp, prof_dls, "drawer_side_t", "DrwLeftBoard")
    drw_left = f_dls.bodies.item(0)
    drw_left.name = "Drw_Left"

    # Drawer right side — mirror
    drw_xmid = af.off_plane(drw_comp, drw_comp.yZConstructionPlane,
        "case_l / 2", "Drw_XMid")
    m_drw_r = af.mirror_body(drw_comp, drw_left, drw_xmid, "DrwRight_Mirror")
    drw_right = m_drw_r.bodies.item(0)
    drw_right.name = "Drw_Right"

    # Drawer bottom
    drw_bot_pl = af.off_plane(drw_comp, drw_comp.xYConstructionPlane,
        "drawer_gap", "DrwBot_Pl")
    sk_dbot, prof_dbot = af.sketch_rect_model(drw_comp, drw_bot_pl,
        ("board_t + drawer_gap + drawer_side_t", "drawer_front_t", "drawer_gap"),
        {"x": "case_l - 2 * board_t - 2 * drawer_gap - 2 * drawer_side_t",
         "y": "case_w - 2 * board_t - drawer_front_t - drawer_side_t"},
        "DrwBot_Sk", ev=ctx.ev)
    f_dbot = af.ext_new(drw_comp, prof_dbot, "drawer_bottom_t", "DrwBotBoard")
    drw_bottom = f_dbot.bodies.item(0)
    drw_bottom.name = "Drw_Bottom"

    # ======================================================================
    # CROSS-COMPONENT: DRAWER OPENING
    # ======================================================================
    # CUT front case board with drawer front body (rule 6)
    drw_front_proxy = drw_front.createForAssemblyContext(drw_occ)
    af.combine(case_comp, front, [drw_front_proxy], CUT, True, "DrawerOpen_Cut")

    # ======================================================================
    # CROSS-COMPONENT: DOVETAILS (via template)
    # ======================================================================
    # dovetail.box() handles all 4 corners:
    #   - Sketches one trapezoid tail at front-left
    #   - JOIN extrudes into left board (participantBodies=[left,right])
    #   - Mirrors to FR, BL, BR corners
    #   - Patterns all along Z
    #   - CUTs front/back pin boards using tail boards as tools

    # Component-local midplanes for dovetail mirrors
    case_xmid = af.off_plane(case_comp, case_comp.yZConstructionPlane,
                             "case_l / 2", "Case_XMid")
    case_ymid = af.off_plane(case_comp, case_comp.xZConstructionPlane,
                             "case_w / 2", "Case_YMid")

    dt_result = dovetail.box(
        comp=case_comp,
        front=front, left=left,
        x_mid=case_xmid, y_mid=case_ymid,
        thick_expr="board_t",
        right=right, back=back,
        prefix="dt", name="DT", ev=ctx.ev,
        fl_plane=case_comp.yZConstructionPlane,
        front_expr="0 in",
        joint_axis="z", thick_axis="y",
        thick_dir=1)

    # ======================================================================
    # CROSS-COMPONENT: BOTTOM DADOS
    # ======================================================================
    bot_proxy = bottom.createForAssemblyContext(bot_occ)
    af.combine(case_comp, front, [bot_proxy], CUT, True, "BottomDado_Front")
    af.combine(case_comp, back, [bot_proxy], CUT, True, "BottomDado_Back")
    af.combine(case_comp, left, [bot_proxy], CUT, True, "BottomDado_Left")
    af.combine(case_comp, right, [bot_proxy], CUT, True, "BottomDado_Right")

    # ======================================================================
    # DETAILS: ARCH CUTOUTS ON BASE RAILS
    # ======================================================================

    # Front rail arch
    arch_face = af.find_face(rail_front, "y", -1)
    sk_arch = base_comp.sketches.add(arch_face)
    sk_arch.name = "Arch_Front_Sk"
    m2s = sk_arch.modelToSketchSpace

    rl_x0 = ctx.ev("board_t") + ctx.ev("leg_size")
    rl_x1 = ctx.ev("case_l") - ctx.ev("board_t") - ctx.ev("leg_size")
    rl_z_bot = -ctx.ev("leg_h")
    rl_y = ctx.ev("board_t")
    mid_x = (rl_x0 + rl_x1) / 2
    arch_peak_z = rl_z_bot + ctx.ev("arch_h")

    sa = m2s(P(rl_x0, rl_y, rl_z_bot))
    sb = m2s(P(rl_x1, rl_y, rl_z_bot))
    sm = m2s(P(mid_x, rl_y, arch_peak_z))

    arch_line = sk_arch.sketchCurves.sketchLines.addByTwoPoints(
        P(sa.x, sa.y, 0), P(sb.x, sb.y, 0))
    sk_arch.sketchCurves.sketchArcs.addByThreePoints(
        arch_line.startSketchPoint, P(sm.x, sm.y, 0), arch_line.endSketchPoint)

    arch_prof = af.smallest_profile(sk_arch)
    af.ext_op(base_comp, arch_prof, "base_rail_t", CUT, rail_front,
              "Arch_Front_Cut", flip=True)

    # Back rail arch
    arch_face_b = af.find_face(rail_back, "y", +1)
    sk_arch_b = base_comp.sketches.add(arch_face_b)
    sk_arch_b.name = "Arch_Back_Sk"
    m2s_b = sk_arch_b.modelToSketchSpace

    rl_y_b = ctx.ev("case_w") - ctx.ev("board_t")
    sa_b = m2s_b(P(rl_x0, rl_y_b, rl_z_bot))
    sb_b = m2s_b(P(rl_x1, rl_y_b, rl_z_bot))
    sm_b = m2s_b(P(mid_x, rl_y_b, arch_peak_z))

    arch_line_b = sk_arch_b.sketchCurves.sketchLines.addByTwoPoints(
        P(sa_b.x, sa_b.y, 0), P(sb_b.x, sb_b.y, 0))
    sk_arch_b.sketchCurves.sketchArcs.addByThreePoints(
        arch_line_b.startSketchPoint, P(sm_b.x, sm_b.y, 0), arch_line_b.endSketchPoint)

    arch_prof_b = af.smallest_profile(sk_arch_b)
    af.ext_op(base_comp, arch_prof_b, "base_rail_t", CUT, rail_back,
              "Arch_Back_Cut", flip=True)

    # Left side rail arch
    arch_face_l = af.find_face(rail_left, "x", -1)
    sk_arch_l = base_comp.sketches.add(arch_face_l)
    sk_arch_l.name = "Arch_Left_Sk"
    m2s_l = sk_arch_l.modelToSketchSpace

    rl_y0 = ctx.ev("board_t") + ctx.ev("leg_size")
    rl_y1 = ctx.ev("case_w") - ctx.ev("board_t") - ctx.ev("leg_size")
    rl_x_l = ctx.ev("board_t")
    mid_y = (rl_y0 + rl_y1) / 2

    sa_l = m2s_l(P(rl_x_l, rl_y0, rl_z_bot))
    sb_l = m2s_l(P(rl_x_l, rl_y1, rl_z_bot))
    sm_l = m2s_l(P(rl_x_l, mid_y, arch_peak_z))

    arch_line_l = sk_arch_l.sketchCurves.sketchLines.addByTwoPoints(
        P(sa_l.x, sa_l.y, 0), P(sb_l.x, sb_l.y, 0))
    sk_arch_l.sketchCurves.sketchArcs.addByThreePoints(
        arch_line_l.startSketchPoint, P(sm_l.x, sm_l.y, 0), arch_line_l.endSketchPoint)

    arch_prof_l = af.smallest_profile(sk_arch_l)
    af.ext_op(base_comp, arch_prof_l, "base_rail_t", CUT, rail_left,
              "Arch_Left_Cut", flip=True)

    # Right side rail arch
    arch_face_r = af.find_face(rail_right, "x", +1)
    sk_arch_r = base_comp.sketches.add(arch_face_r)
    sk_arch_r.name = "Arch_Right_Sk"
    m2s_r = sk_arch_r.modelToSketchSpace

    rl_x_r = ctx.ev("case_l") - ctx.ev("board_t")
    sa_r = m2s_r(P(rl_x_r, rl_y0, rl_z_bot))
    sb_r = m2s_r(P(rl_x_r, rl_y1, rl_z_bot))
    sm_r = m2s_r(P(rl_x_r, mid_y, arch_peak_z))

    arch_line_r = sk_arch_r.sketchCurves.sketchLines.addByTwoPoints(
        P(sa_r.x, sa_r.y, 0), P(sb_r.x, sb_r.y, 0))
    sk_arch_r.sketchCurves.sketchArcs.addByThreePoints(
        arch_line_r.startSketchPoint, P(sm_r.x, sm_r.y, 0), arch_line_r.endSketchPoint)

    arch_prof_r = af.smallest_profile(sk_arch_r)
    af.ext_op(base_comp, arch_prof_r, "base_rail_t", CUT, rail_right,
              "Arch_Right_Cut", flip=True)

    # ======================================================================
    # DETAILS: LID CHAMFER
    # ======================================================================

    lid_bottom_face = af.find_face(lid, "z", -1)
    lid_edges = []
    seen = set()
    for i in range(lid_bottom_face.edges.count):
        e = lid_bottom_face.edges.item(i)
        if e.tempId not in seen:
            seen.add(e.tempId)
            lid_edges.append(e)

    edge_coll = adsk.core.ObjectCollection.create()
    for e in lid_edges:
        edge_coll.add(e)

    ch_input = lid_comp.features.chamferFeatures.createInput2()
    ch_input.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
        edge_coll, VI("lid_chamfer"), True)
    ch_feat = lid_comp.features.chamferFeatures.add(ch_input)
    ch_feat.name = "Lid_Ch"

    # ======================================================================
    # EPILOGUE
    # ======================================================================

    for comp_iter in [root, case_comp, bot_comp, lid_comp, base_comp, drw_comp]:
        for i in range(comp_iter.sketches.count):
            comp_iter.sketches.item(i).isVisible = False
        for i in range(comp_iter.constructionPlanes.count):
            comp_iter.constructionPlanes.item(i).isLightBulbOn = False
        for i in range(comp_iter.constructionAxes.count):
            comp_iter.constructionAxes.item(i).isLightBulbOn = False

    all_bodies = []
    def collect_bodies(comp_node):
        for i in range(comp_node.bRepBodies.count):
            all_bodies.append(comp_node.bRepBodies.item(i).name)
        for i in range(comp_node.occurrences.count):
            collect_bodies(comp_node.occurrences.item(i).component)
    collect_bodies(root)
    print(f"Total: {len(all_bodies)} bodies -> {all_bodies}")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
