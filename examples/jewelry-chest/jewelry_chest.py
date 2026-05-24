import adsk.core, adsk.fusion, math
from helpers import sp
from woodworking.templates import dovetail

def run(context):
    ctx = sp.DesignContext(); design = ctx.design; root = ctx.root; params = ctx.params; ev = ctx.ev
    P = adsk.core.Point3D.create
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation

    # ── Parameters ──
    params.add("box_length", adsk.core.ValueInput.createByString("14 in"), "in", "Overall length (X)")
    params.add("box_width", adsk.core.ValueInput.createByString("9 in"), "in", "Overall depth (Y)")
    params.add("case_height", adsk.core.ValueInput.createByString("5.25 in"), "in", "Total box height (end board top = lid top)")
    params.add("board_thick", adsk.core.ValueInput.createByString("0.625 in"), "in", "Case board thickness (5/8)")
    params.add("bottom_thick", adsk.core.ValueInput.createByString("0.25 in"), "in", "Bottom tongue thickness (fits in groove)")
    params.add("bottom_full_thick", adsk.core.ValueInput.createByString("0.5 in"), "in", "Bottom panel full thickness")
    params.add("groove_depth", adsk.core.ValueInput.createByString("0.25 in"), "in", "Groove depth")
    params.add("groove_up", adsk.core.ValueInput.createByString("0.375 in"), "in", "Bottom groove offset")
    params.add("support_thick", adsk.core.ValueInput.createByString("0.125 in"), "in", "Support panel thickness (1/8)")
    params.add("lid_frame_w", adsk.core.ValueInput.createByString("1.25 in"), "in", "Lid frame piece width (1-1/4)")
    params.add("lid_frame_h", adsk.core.ValueInput.createByString("0.5625 in"), "in", "Lid frame height (9/16)")
    params.add("lid_panel_t", adsk.core.ValueInput.createByString("0.4375 in"), "in", "Lid panel face thickness (7/16)")
    params.add("lid_groove_t", adsk.core.ValueInput.createByString("0.3125 in"), "in", "Groove/tongue/tenon thickness (5/16)")
    params.add("lid_tenon_l", adsk.core.ValueInput.createByString("0.5 in"), "in", "Tenon length into rail groove")
    params.add("lid_tongue_l", adsk.core.ValueInput.createByString("0.25 in"), "in", "Panel tongue protrusion")
    params.add("lid_rab", adsk.core.ValueInput.createByString("lid_frame_h * 0.6"), "in", "Front lip height (60% of lid)")
    params.add("pull_w", adsk.core.ValueInput.createByString("1.125 in"), "in", "Pull width (1-1/8)")
    params.add("pull_h", adsk.core.ValueInput.createByString("0.375 in"), "in", "Pull height (3/8)")
    params.add("pull_d", adsk.core.ValueInput.createByString("0.4375 in"), "in", "Pull depth (7/16)")
    params.add("tray_height", adsk.core.ValueInput.createByString("1.625 in"), "in", "Tray side height")
    params.add("tray_thick", adsk.core.ValueInput.createByString("0.25 in"), "in", "Tray side thickness")
    params.add("tray_bottom_thick", adsk.core.ValueInput.createByString("0.25 in"), "in", "Tray bottom thickness")
    params.add("tray_cl", adsk.core.ValueInput.createByString("0.0625 in"), "in", "Tray clearance")
    params.add("div_thick", adsk.core.ValueInput.createByString("0.25 in"), "in", "Tray divider thickness")
    params.add("tray_groove_depth", adsk.core.ValueInput.createByString("0.0625 in"), "in", "Tray groove depth for bottom panel")
    params.add("tray_groove_up", adsk.core.ValueInput.createByString("0.125 in"), "in", "Tray groove offset from bottom edge")
    params.add("divider_handle_ext", adsk.core.ValueInput.createByString("0.1875 in"), "in", "Upper tray divider handle extension")
    params.add("notch_h", adsk.core.ValueInput.createByString("0.375 in"), "in", "Handle notch height")
    params.add("notch_margin", adsk.core.ValueInput.createByString("2.6 in"), "in", "Handle notch Y-side margin")
    params.add("lower_handle_ext", adsk.core.ValueInput.createByString("0.25 in"), "in", "Lower tray divider handle extension")
    params.add("lower_tray_height", adsk.core.ValueInput.createByString("1.875 in"), "in", "Lower tray side height")
    params.add("tray_dado_depth", adsk.core.ValueInput.createByString("0.0625 in"), "in", "Dado depth for tray divider")
    params.add("proud_offset", adsk.core.ValueInput.createByString("0.05 in"), "in", "Proud dovetail offset (Krenov-style)")

    # Full board height (end boards = lid top). Dovetails run this full height for equal end pins.
    params.add("end_height", adsk.core.ValueInput.createByString("case_height"), "in", "End board height = total height")
    params.add("open_height", adsk.core.ValueInput.createByString("case_height - lid_frame_h"), "in", "Back board height (below lid)")

    dovetail.define_params(params, prefix="dt", angle="8 deg", tail_w="0.875 in",
        tail_count="4", joint_h_expr="end_height", thick_expr="board_thick", pad="0.75 in",
        proud_offset="proud_offset")

    params.add("interior_l", adsk.core.ValueInput.createByString("box_length - 2 * board_thick"), "in", "")
    params.add("interior_w", adsk.core.ValueInput.createByString("box_width - 2 * board_thick"), "in", "")
    params.add("lid_panel_z", adsk.core.ValueInput.createByString("open_height + lid_frame_h - lid_panel_t"), "in", "")
    params.add("lid_groove_z", adsk.core.ValueInput.createByString("lid_panel_z"), "in", "")
    params.add("tray_z", adsk.core.ValueInput.createByString("groove_up + bottom_thick + lower_tray_height + lower_handle_ext"), "in", "")
    params.add("tray_l_out", adsk.core.ValueInput.createByString("interior_l - 2 * tray_cl"), "in", "")
    params.add("tray_w_out", adsk.core.ValueInput.createByString("interior_w - 2 * tray_cl"), "in", "")
    params.add("lower_tray_l", adsk.core.ValueInput.createByString("(interior_l - 3 * tray_cl) / 2"), "in", "")
    params.add("lower_tray_z", adsk.core.ValueInput.createByString("groove_up + bottom_thick"), "in", "")
    params.add("lower_tray_w_out", adsk.core.ValueInput.createByString("interior_w - 2 * support_thick - 2 * tray_cl"), "in", "")

    xmid_pl = sp.off_plane(root, root.yZConstructionPlane, "box_length / 2", "XMid")
    ymid_pl = sp.off_plane(root, root.xZConstructionPlane, "box_width / 2", "YMid")

    # ── Body-relative reference helper (via DesignContext) ──
    # All non-origin refs need ctx.find_body + .boundingBox to pass validate_deps

    # ── Case: ALL boards at end_height (dovetails need equal height) ──
    case_occ = sp.make_comp(root, "Case"); case_c = case_occ.component
    sk, prof = sp.sketch_rect_model(case_c, root.yZConstructionPlane,
        ("0 in","0 in","0 in"), {"y":"box_width","z":"end_height"}, "EndL_Sk", ev=ev)
    end_l = sp.ext_new(case_c, prof, "board_thick", "EndLBoard").bodies.item(0); end_l.name = "End_L"
    end_r = sp.mirror_body(case_c, end_l, xmid_pl, "EndR_M").bodies.item(0); end_r.name = "End_R"
    # Body-relative reference: Front depends on End_L
    ref_end_l = ctx.find_body("End_L")
    ref_end_l_bb = ref_end_l.boundingBox

    sk, prof = sp.sketch_rect_model(case_c, root.xZConstructionPlane,
        ("board_thick","0 in","0 in"), {"x":"interior_l","z":"end_height"}, "Front_Sk", ev=ev)
    front = sp.ext_new(case_c, prof, "board_thick", "FrontBoard").bodies.item(0); front.name = "Front"
    back = sp.mirror_body(case_c, front, ymid_pl, "Back_M").bodies.item(0); back.name = "Back"
    # Body-relative reference: Support_F depends on Front, Support_B depends on Back
    ref_front = ctx.find_body("Front")
    ref_front_bb = ref_front.boundingBox
    ref_back = ctx.find_body("Back")
    ref_back_bb = ref_back.boundingBox

    sup_pl = sp.off_plane(case_c, root.xYConstructionPlane, "groove_up + bottom_thick", "Sup_Pl")
    sk, prof = sp.sketch_rect_model(case_c, sup_pl,
        ("board_thick", "board_thick", "groove_up + bottom_thick"),
        {"x": "interior_l", "y": "support_thick"}, "SupF_Sk", ev=ev)
    sup_f = sp.ext_new(case_c, prof, "lower_tray_height + lower_handle_ext", "SupF").bodies.item(0); sup_f.name = "Support_F"
    sup_b = sp.mirror_body(case_c, sup_f, ymid_pl, "SupB_M").bodies.item(0); sup_b.name = "Support_B"

    # ── Proud extensions: widen pin boards (End) + thicken tail boards (Front/Back) in Y ──
    if ev("proud_offset") > 0:
        for pb in [end_l, end_r]:
            for direction in [-1, +1]:
                face = sp.find_face(pb, "y", direction)
                inp = case_c.features.extrudeFeatures.createInput(face, JOIN)
                inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("proud_offset"))
                inp.participantBodies = [pb]
                ext = case_c.features.extrudeFeatures.add(inp)
                ext.name = f"{pb.name}_ProudExt{'F' if direction < 0 else 'B'}"
        # Front extends in -Y, Back extends in +Y
        face_f = sp.find_face(front, "y", -1)
        inp = case_c.features.extrudeFeatures.createInput(face_f, JOIN)
        inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("proud_offset"))
        inp.participantBodies = [front]
        case_c.features.extrudeFeatures.add(inp).name = "Front_ProudExt"
        face_b = sp.find_face(back, "y", +1)
        inp = case_c.features.extrudeFeatures.createInput(face_b, JOIN)
        inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("proud_offset"))
        inp.participantBodies = [back]
        case_c.features.extrudeFeatures.add(inp).name = "Back_ProudExt"

    # ── Bottom ──
    # Body-relative reference: Bottom depends on Front
    ref_front2 = ctx.find_body("Front")
    ref_front2_bb = ref_front2.boundingBox

    bot_occ = sp.make_comp(root, "Bottom"); bot_c = bot_occ.component
    bpp = sp.off_plane(bot_c, root.xYConstructionPlane, "groove_up", "BP_Pl")
    sk, prof = sp.sketch_rect_model(bot_c, bpp,
        ("board_thick - groove_depth","board_thick - groove_depth","groove_up"),
        {"x":"interior_l + 2 * groove_depth","y":"interior_w + 2 * groove_depth"}, "BP_Sk", ev=ev)
    bp = sp.ext_new(bot_c, prof, "bottom_thick", "BP").bodies.item(0); bp.name = "Bottom"
    # Raised center: thicker block below the tongue, inside the case interior
    rpl = sp.off_plane(bot_c, root.xYConstructionPlane,
        "groove_up - bottom_full_thick + bottom_thick", "BP_R_Pl")
    sk, prof = sp.sketch_rect_model(bot_c, rpl,
        ("board_thick", "board_thick", "groove_up - bottom_full_thick + bottom_thick"),
        {"x": "interior_l", "y": "interior_w"}, "BP_R_Sk", ev=ev)
    bp_r = sp.ext_new(bot_c, prof, "bottom_full_thick - bottom_thick", "BP_R").bodies.item(0)
    sp.combine(bp, bp_r, JOIN, False, "BP_RJ")
    sp.combine(end_l, bp, CUT, True, "BG_EL"); sp.combine(end_r, bp, CUT, True, "BG_ER")
    sp.combine(front, bp, CUT, True, "BG_F"); sp.combine(back, bp, CUT, True, "BG_B")

    # ── Dovetails at full end_height (equal top/bottom end pins) ──
    # Proud dovetails: sketch plane at extended tail board position (-proud_offset in Y)
    dt_plane = case_c.xZConstructionPlane
    proud_expr = None
    if ev("proud_offset") > 0:
        dt_plane = sp.off_plane(case_c, root.xZConstructionPlane,
                                "0 in - proud_offset", "DT_Proud_Pl")
        proud_expr = "proud_offset"
    dovetail.box(comp=case_c, front=end_l, left=front, x_mid=ymid_pl, y_mid=xmid_pl,
        thick_expr="board_thick", right=back, back=end_r, prefix="dt", name="DT", ev=ev,
        fl_plane=dt_plane, front_expr="0 in",
        joint_axis="z", thick_axis="x", thick_dir=1,
        proud_offset_expr=proud_expr)
    sp.combine(front, bp, CUT, True, "BG_F2"); sp.combine(back, bp, CUT, True, "BG_B2")

    # ── Trim back board: remove above open_height ──
    trim_pl = sp.off_plane(case_c, root.xYConstructionPlane, "open_height", "Trim_Pl")
    sk, prof = sp.sketch_rect_model(case_c, trim_pl,
        ("0 in","box_width - board_thick","open_height"),
        {"x":"box_length","y":"board_thick"}, "TrimB_Sk", ev=ev)
    sp.ext_op(case_c, prof, "lid_frame_h", CUT, back, "TrimBack")

    # ── Front board: remove ALL above open_height, then add outer-half lip ──
    sk, prof = sp.sketch_rect_model(case_c, trim_pl,
        ("0 in","0 in","open_height"),
        {"x":"box_length","y":"board_thick"}, "TrimF_Sk", ev=ev)
    sp.ext_op(case_c, prof, "lid_frame_h", CUT, front, "TrimFrontAll")
    # Add back outer-half lip between end boards (lid_rab tall)
    sk, prof = sp.sketch_rect_model(case_c, trim_pl,
        ("board_thick","0 in","open_height"),
        {"x":"interior_l","y":"board_thick / 2"}, "FLip_Sk", ev=ev)
    flip_body = sp.ext_new(case_c, prof, "lid_rab", "FLip").bodies.item(0)
    sp.combine(front, flip_body, JOIN, False, "FLip_J")

    # ── Upper Tray (mitered corners, grooved bottom, dado divider with handle) ──
    # Body-relative reference: UT_Front depends on Front
    ref_front3 = ctx.find_body("Front")
    ref_front3_bb = ref_front3.boundingBox
    def find_shared_edge(face_a, face_b):
        ids_b = {face_b.edges.item(j).tempId for j in range(face_b.edges.count)}
        for i in range(face_a.edges.count):
            if face_a.edges.item(i).tempId in ids_b:
                return face_a.edges.item(i)

    ut_occ = sp.make_comp(root, "UpperTray"); ut_c = ut_occ.component
    tp = sp.off_plane(ut_c, root.xYConstructionPlane, "tray_z", "UT_Pl")
    sk, prof = sp.sketch_rect_model(ut_c, tp,
        ("board_thick + tray_cl", "board_thick + tray_cl", "tray_z"),
        {"x": "tray_l_out", "y": "tray_thick"}, "UTF_Sk", ev=ev)
    ut_f = sp.ext_new(ut_c, prof, "tray_height", "UTF").bodies.item(0); ut_f.name = "UT_Front"
    left_end = sp.find_face(ut_f, "x", -1); right_end = sp.find_face(ut_f, "x", +1)
    inner_y = sp.find_face(ut_f, "y", +1)
    me = adsk.core.ObjectCollection.create()
    me.add(find_shared_edge(left_end, inner_y)); me.add(find_shared_edge(right_end, inner_y))
    ci = ut_c.features.chamferFeatures.createInput2()
    ci.chamferEdgeSets.addEqualDistanceChamferEdgeSet(me,
        adsk.core.ValueInput.createByString("tray_thick"), False)
    ut_c.features.chamferFeatures.add(ci).name = "UTF_Miter"
    # Body-relative reference: UT_Back, UT_End_L, UT_End_R depend on UT_Front
    ref_ut_front = ctx.find_body("UT_Front")
    ref_ut_front_bb = ref_ut_front.boundingBox

    ut_b = sp.mirror_body(ut_c, ut_f, ymid_pl, "UTB_M").bodies.item(0); ut_b.name = "UT_Back"

    sk, prof = sp.sketch_rect_model(ut_c, tp,
        ("board_thick + tray_cl", "board_thick + tray_cl", "tray_z"),
        {"x": "tray_thick", "y": "tray_w_out"}, "UTEL_Sk", ev=ev)
    ut_el = sp.ext_new(ut_c, prof, "tray_height", "UTEL").bodies.item(0); ut_el.name = "UT_End_L"
    fend = sp.find_face(ut_el, "y", -1); bend = sp.find_face(ut_el, "y", +1)
    inner_x = sp.find_face(ut_el, "x", +1)
    me = adsk.core.ObjectCollection.create()
    me.add(find_shared_edge(fend, inner_x)); me.add(find_shared_edge(bend, inner_x))
    ci = ut_c.features.chamferFeatures.createInput2()
    ci.chamferEdgeSets.addEqualDistanceChamferEdgeSet(me,
        adsk.core.ValueInput.createByString("tray_thick"), False)
    ut_c.features.chamferFeatures.add(ci).name = "UTEL_Miter"
    ut_er = sp.mirror_body(ut_c, ut_el, xmid_pl, "UTER_M").bodies.item(0); ut_er.name = "UT_End_R"

    utbp = sp.off_plane(ut_c, root.xYConstructionPlane, "tray_z + tray_groove_up", "UTBot_Pl")
    sk, prof = sp.sketch_rect_model(ut_c, utbp,
        ("board_thick + tray_cl + tray_thick - tray_groove_depth",
         "board_thick + tray_cl + tray_thick - tray_groove_depth",
         "tray_z + tray_groove_up"),
        {"x": "tray_l_out - 2 * tray_thick + 2 * tray_groove_depth",
         "y": "tray_w_out - 2 * tray_thick + 2 * tray_groove_depth"},
        "UTBot_Sk", ev=ev)
    ut_bot = sp.ext_new(ut_c, prof, "tray_bottom_thick", "UTBot").bodies.item(0)
    ut_bot.name = "UT_Bottom"

    # Body-relative reference: UT_Div depends on UT_Bottom
    ref_ut_bottom = ctx.find_body("UT_Bottom")
    ref_ut_bottom_bb = ref_ut_bottom.boundingBox
    sp.combine(ut_f, ut_bot, CUT, True, "UTG_F"); sp.combine(ut_b, ut_bot, CUT, True, "UTG_B")
    sp.combine(ut_el, ut_bot, CUT, True, "UTG_EL"); sp.combine(ut_er, ut_bot, CUT, True, "UTG_ER")

    utdz = "tray_z + tray_groove_up + tray_bottom_thick"
    utdh = "tray_height - tray_groove_up - tray_bottom_thick + divider_handle_ext"
    utdp = sp.off_plane(ut_c, root.xYConstructionPlane, utdz, "UTDiv_Pl")
    sk, prof = sp.sketch_rect_model(ut_c, utdp,
        ("box_length / 2 - div_thick / 2",
         "board_thick + tray_cl + tray_thick - tray_dado_depth", utdz),
        {"x": "div_thick",
         "y": "tray_w_out - 2 * tray_thick + 2 * tray_dado_depth"},
        "UTDiv_Sk", ev=ev)
    ut_div = sp.ext_new(ut_c, prof, utdh, "UTDiv").bodies.item(0); ut_div.name = "UT_Div"
    sp.combine(ut_f, ut_div, CUT, True, "UTD_F"); sp.combine(ut_b, ut_div, CUT, True, "UTD_B")

    # Arch notch in upper tray divider (finger grip below handle)
    notch_pl = sp.off_plane(ut_c, root.yZConstructionPlane,
        "box_length / 2 - div_thick / 2", "UTNotch_Pl")
    sk = ut_c.sketches.add(notch_pl); sk.name = "UTNotch_Sk"
    m2s = sk.modelToSketchSpace
    z_top = ev("tray_z + tray_height")
    y_s = ev("board_thick + tray_cl + tray_thick + notch_margin")
    y_e = ev("board_thick + tray_cl + tray_w_out - tray_thick - notch_margin")
    x_n = ev("box_length / 2 - div_thick / 2")
    pl = m2s(P(x_n, y_s, z_top)); pr = m2s(P(x_n, y_e, z_top))
    pm = m2s(P(x_n, (y_s + y_e) / 2, z_top - ev("notch_h")))
    top_ln = sk.sketchCurves.sketchLines.addByTwoPoints(
        P(pl.x, pl.y, 0), P(pr.x, pr.y, 0))
    sk.sketchCurves.sketchArcs.addByThreePoints(
        top_ln.endSketchPoint, P(pm.x, pm.y, 0), top_ln.startSketchPoint)
    sp.refs_to_construction(sk)
    prof = sp.smallest_profile(sk)
    sp.ext_op(ut_c, prof, "div_thick", CUT, ut_div, "UTNotch")

    # ── Lower Trays (pair, side by side on bottom panel) ──
    # Body-relative reference: LTL_Front and LTR_Front depend on Bottom
    ref_bottom = ctx.find_body("Bottom")
    ref_bottom_bb = ref_bottom.boundingBox

    lt_occ = sp.make_comp(root, "LowerTrays"); lt_c = lt_occ.component
    ltp = sp.off_plane(lt_c, root.xYConstructionPlane, "lower_tray_z", "LT_Pl")
    lt1_xmid = sp.off_plane(lt_c, root.yZConstructionPlane,
        "board_thick + tray_cl + lower_tray_l / 2", "LT1_XMid")

    sk, prof = sp.sketch_rect_model(lt_c, ltp,
        ("board_thick + tray_cl", "board_thick + support_thick + tray_cl", "lower_tray_z"),
        {"x": "lower_tray_l", "y": "tray_thick"}, "LTL_F_Sk", ev=ev)
    lt1_f = sp.ext_new(lt_c, prof, "lower_tray_height", "LTL_F").bodies.item(0)
    lt1_f.name = "LTL_Front"
    left_end = sp.find_face(lt1_f, "x", -1); right_end = sp.find_face(lt1_f, "x", +1)
    inner_y = sp.find_face(lt1_f, "y", +1)
    me = adsk.core.ObjectCollection.create()
    me.add(find_shared_edge(left_end, inner_y)); me.add(find_shared_edge(right_end, inner_y))
    ci = lt_c.features.chamferFeatures.createInput2()
    ci.chamferEdgeSets.addEqualDistanceChamferEdgeSet(me,
        adsk.core.ValueInput.createByString("tray_thick"), False)
    lt_c.features.chamferFeatures.add(ci).name = "LTL_F_Miter"
    # Body-relative reference: LTL_Back, LTL_End_L, LTL_End_R, LTL_Bottom depend on LTL_Front
    ref_ltl_front = ctx.find_body("LTL_Front")
    ref_ltl_front_bb = ref_ltl_front.boundingBox

    lt1_b = sp.mirror_body(lt_c, lt1_f, ymid_pl, "LTL_B_M").bodies.item(0)
    lt1_b.name = "LTL_Back"

    sk, prof = sp.sketch_rect_model(lt_c, ltp,
        ("board_thick + tray_cl", "board_thick + support_thick + tray_cl", "lower_tray_z"),
        {"x": "tray_thick", "y": "lower_tray_w_out"}, "LTL_EL_Sk", ev=ev)
    lt1_el = sp.ext_new(lt_c, prof, "lower_tray_height", "LTL_EL").bodies.item(0)
    lt1_el.name = "LTL_End_L"
    fend = sp.find_face(lt1_el, "y", -1); bend = sp.find_face(lt1_el, "y", +1)
    inner_x = sp.find_face(lt1_el, "x", +1)
    me = adsk.core.ObjectCollection.create()
    me.add(find_shared_edge(fend, inner_x)); me.add(find_shared_edge(bend, inner_x))
    ci = lt_c.features.chamferFeatures.createInput2()
    ci.chamferEdgeSets.addEqualDistanceChamferEdgeSet(me,
        adsk.core.ValueInput.createByString("tray_thick"), False)
    lt_c.features.chamferFeatures.add(ci).name = "LTL_EL_Miter"
    lt1_er = sp.mirror_body(lt_c, lt1_el, lt1_xmid, "LTL_ER_M").bodies.item(0)
    lt1_er.name = "LTL_End_R"

    ltbp = sp.off_plane(lt_c, root.xYConstructionPlane,
        "lower_tray_z + tray_groove_up", "LTBot_Pl")
    sk, prof = sp.sketch_rect_model(lt_c, ltbp,
        ("board_thick + tray_cl + tray_thick - tray_groove_depth",
         "board_thick + support_thick + tray_cl + tray_thick - tray_groove_depth",
         "lower_tray_z + tray_groove_up"),
        {"x": "lower_tray_l - 2 * tray_thick + 2 * tray_groove_depth",
         "y": "lower_tray_w_out - 2 * tray_thick + 2 * tray_groove_depth"},
        "LTL_Bot_Sk", ev=ev)
    lt1_bot = sp.ext_new(lt_c, prof, "tray_bottom_thick", "LTL_Bot").bodies.item(0)
    lt1_bot.name = "LTL_Bottom"

    # Body-relative reference: LTL_Div depends on LTL_Bottom
    ref_ltl_bottom = ctx.find_body("LTL_Bottom")
    ref_ltl_bottom_bb = ref_ltl_bottom.boundingBox
    sp.combine(lt1_f, lt1_bot, CUT, True, "LTG_F"); sp.combine(lt1_b, lt1_bot, CUT, True, "LTG_B")
    sp.combine(lt1_el, lt1_bot, CUT, True, "LTG_EL"); sp.combine(lt1_er, lt1_bot, CUT, True, "LTG_ER")

    ltdz = "lower_tray_z + tray_groove_up + tray_bottom_thick"
    ltdh = "lower_tray_height - tray_groove_up - tray_bottom_thick + lower_handle_ext"
    ltdp = sp.off_plane(lt_c, root.xYConstructionPlane, ltdz, "LTDiv_Pl")
    sk, prof = sp.sketch_rect_model(lt_c, ltdp,
        ("board_thick + tray_cl + lower_tray_l / 2 - div_thick / 2",
         "board_thick + support_thick + tray_cl + tray_thick - tray_dado_depth", ltdz),
        {"x": "div_thick",
         "y": "lower_tray_w_out - 2 * tray_thick + 2 * tray_dado_depth"},
        "LTL_Div_Sk", ev=ev)
    lt1_div = sp.ext_new(lt_c, prof, ltdh, "LTL_Div").bodies.item(0); lt1_div.name = "LTL_Div"
    sp.combine(lt1_f, lt1_div, CUT, True, "LTD_F"); sp.combine(lt1_b, lt1_div, CUT, True, "LTD_B")

    # Arch notch in lower tray divider
    lt_notch_pl = sp.off_plane(lt_c, root.yZConstructionPlane,
        "board_thick + tray_cl + lower_tray_l / 2 - div_thick / 2", "LTNotch_Pl")
    sk = lt_c.sketches.add(lt_notch_pl); sk.name = "LTNotch_Sk"
    m2s = sk.modelToSketchSpace
    lz_top = ev("lower_tray_z + lower_tray_height")
    ly_s = ev("board_thick + support_thick + tray_cl + tray_thick + notch_margin")
    ly_e = ev("board_thick + support_thick + tray_cl + lower_tray_w_out - tray_thick - notch_margin")
    lx_n = ev("board_thick + tray_cl + lower_tray_l / 2 - div_thick / 2")
    lpl = m2s(P(lx_n, ly_s, lz_top)); lpr = m2s(P(lx_n, ly_e, lz_top))
    lpm = m2s(P(lx_n, (ly_s + ly_e) / 2, lz_top - ev("notch_h")))
    lt_ln = sk.sketchCurves.sketchLines.addByTwoPoints(P(lpl.x, lpl.y, 0), P(lpr.x, lpr.y, 0))
    sk.sketchCurves.sketchArcs.addByThreePoints(lt_ln.endSketchPoint, P(lpm.x, lpm.y, 0), lt_ln.startSketchPoint)
    sp.refs_to_construction(sk)
    prof = sp.smallest_profile(sk)
    sp.ext_op(lt_c, prof, "div_thick", CUT, lt1_div, "LTNotch")

    # Body-relative references: LTR sub-bodies depend on LTR_Front, LTR_Bottom
    # (LTR_Front itself depends on Bottom, already looked up above)

    lt2_f = sp.mirror_body(lt_c, lt1_f, xmid_pl, "LTR_F_M").bodies.item(0); lt2_f.name = "LTR_Front"
    lt2_b = sp.mirror_body(lt_c, lt1_b, xmid_pl, "LTR_B_M").bodies.item(0); lt2_b.name = "LTR_Back"
    lt2_el = sp.mirror_body(lt_c, lt1_el, xmid_pl, "LTR_EL_M").bodies.item(0); lt2_el.name = "LTR_End_L"
    lt2_er = sp.mirror_body(lt_c, lt1_er, xmid_pl, "LTR_ER_M").bodies.item(0); lt2_er.name = "LTR_End_R"
    lt2_bot = sp.mirror_body(lt_c, lt1_bot, xmid_pl, "LTR_Bot_M").bodies.item(0); lt2_bot.name = "LTR_Bottom"
    lt2_div = sp.mirror_body(lt_c, lt1_div, xmid_pl, "LTR_Div_M").bodies.item(0); lt2_div.name = "LTR_Div"

    # Body-relative references for mirrored LTR tray
    ref_ltr_front = ctx.find_body("LTR_Front")
    ref_ltr_front_bb = ref_ltr_front.boundingBox
    ref_ltr_bottom = ctx.find_body("LTR_Bottom")
    ref_ltr_bottom_bb = ref_ltr_bottom.boundingBox

    # ── Lid (frame-and-panel between end boards, divider runs Y) ──
    # Body-relative references: Lid_Rail_F depends on Front, Lid_Rail_B depends on Back
    ref_front4 = ctx.find_body("Front")
    ref_front4_bb = ref_front4.boundingBox
    ref_back2 = ctx.find_body("Back")
    ref_back2_bb = ref_back2.boundingBox

    lid_occ = sp.make_comp(root, "Lid"); lid_c = lid_occ.component
    lbp = sp.off_plane(lid_c, root.xYConstructionPlane, "open_height", "LB_Pl")
    lgp = sp.off_plane(lid_c, root.xYConstructionPlane, "lid_groove_z", "LG_Pl")

    # Rail_F (recessed lid_rab from front face — flat bottom, no rabbet)
    sk, prof = sp.sketch_rect_model(lid_c, lbp,
        ("board_thick","lid_rab","open_height"), {"x":"interior_l","y":"lid_frame_w"}, "LRF_Sk", ev=ev)
    lrf = sp.ext_new(lid_c, prof, "lid_frame_h", "LRF").bodies.item(0); lrf.name = "Lid_Rail_F"
    sk, prof = sp.sketch_rect_model(lid_c, lgp,
        ("board_thick","lid_rab + lid_frame_w - lid_tenon_l","lid_groove_z"),
        {"x":"interior_l","y":"lid_tenon_l"}, "LRF_G_Sk", ev=ev)
    gf = sp.ext_new(lid_c, prof, "lid_groove_t", "LRF_GT").bodies.item(0)
    sp.combine(lrf, gf, CUT, False, "LRF_G")

    # Rail_B (at back edge, flat bottom)
    sk, prof = sp.sketch_rect_model(lid_c, lbp,
        ("board_thick","box_width - lid_frame_w","open_height"), {"x":"interior_l","y":"lid_frame_w"}, "LRB_Sk", ev=ev)
    lrb = sp.ext_new(lid_c, prof, "lid_frame_h", "LRB").bodies.item(0); lrb.name = "Lid_Rail_B"
    sk, prof = sp.sketch_rect_model(lid_c, lgp,
        ("board_thick","box_width - lid_frame_w","lid_groove_z"),
        {"x":"interior_l","y":"lid_tenon_l"}, "LRB_G_Sk", ev=ev)
    gb = sp.ext_new(lid_c, prof, "lid_groove_t", "LRB_GT").bodies.item(0)
    sp.combine(lrb, gb, CUT, False, "LRB_G")

    # Body-relative reference: Lid_Stile_L depends on Lid_Rail_F
    ref_lid_rail_f = ctx.find_body("Lid_Rail_F")
    ref_lid_rail_f_bb = ref_lid_rail_f.boundingBox

    # Stile_L (between rails, inside end board extension)
    sk, prof = sp.sketch_rect_model(lid_c, lbp,
        ("board_thick","lid_rab + lid_frame_w","open_height"),
        {"x":"lid_frame_w","y":"box_width - 2 * lid_frame_w - lid_rab"}, "LSL_Sk", ev=ev)
    lsl = sp.ext_new(lid_c, prof, "lid_frame_h", "LSL").bodies.item(0); lsl.name = "Lid_Stile_L"
    sk, prof = sp.sketch_rect_model(lid_c, lgp,
        ("board_thick + lid_frame_w - lid_tongue_l","lid_rab + lid_frame_w","lid_groove_z"),
        {"x":"lid_tongue_l","y":"box_width - 2 * lid_frame_w - lid_rab"}, "LSL_G_Sk", ev=ev)
    gs = sp.ext_new(lid_c, prof, "lid_groove_t", "LSL_GT").bodies.item(0)
    sp.combine(lsl, gs, CUT, False, "LSL_G")
    # Stile tenons into rails (recessed from inner edge)
    sk, prof = sp.sketch_rect_model(lid_c, lgp,
        ("board_thick","lid_rab + lid_frame_w - lid_tenon_l","lid_groove_z"),
        {"x":"lid_frame_w - lid_tongue_l","y":"lid_tenon_l"}, "LSL_TF_Sk", ev=ev)
    t = sp.ext_new(lid_c, prof, "lid_groove_t", "LSL_TF").bodies.item(0)
    sp.combine(lsl, t, JOIN, False, "LSL_TFJ")
    sk, prof = sp.sketch_rect_model(lid_c, lgp,
        ("board_thick","box_width - lid_frame_w","lid_groove_z"),
        {"x":"lid_frame_w - lid_tongue_l","y":"lid_tenon_l"}, "LSL_TB_Sk", ev=ev)
    t = sp.ext_new(lid_c, prof, "lid_groove_t", "LSL_TB").bodies.item(0)
    sp.combine(lsl, t, JOIN, False, "LSL_TBJ")
    lsr = sp.mirror_body(lid_c, lsl, xmid_pl, "LSR_M").bodies.item(0); lsr.name = "Lid_Stile_R"

    # Div (runs in Y between rails, centered in X — parallel to sides)
    sk, prof = sp.sketch_rect_model(lid_c, lbp,
        ("box_length / 2 - lid_frame_w / 2","lid_rab + lid_frame_w","open_height"),
        {"x":"lid_frame_w","y":"box_width - 2 * lid_frame_w - lid_rab"}, "LDV_Sk", ev=ev)
    ldv = sp.ext_new(lid_c, prof, "lid_frame_h", "LDV").bodies.item(0); ldv.name = "Lid_Div"
    sk, prof = sp.sketch_rect_model(lid_c, lgp,
        ("box_length / 2 - lid_frame_w / 2","lid_rab + lid_frame_w","lid_groove_z"),
        {"x":"lid_tongue_l","y":"box_width - 2 * lid_frame_w - lid_rab"}, "LDV_GL_Sk", ev=ev)
    gl = sp.ext_new(lid_c, prof, "lid_groove_t", "LDV_GLT").bodies.item(0); sp.combine(ldv, gl, CUT, False, "LDV_GL")
    sk, prof = sp.sketch_rect_model(lid_c, lgp,
        ("box_length / 2 + lid_frame_w / 2 - lid_tongue_l","lid_rab + lid_frame_w","lid_groove_z"),
        {"x":"lid_tongue_l","y":"box_width - 2 * lid_frame_w - lid_rab"}, "LDV_GR_Sk", ev=ev)
    gr = sp.ext_new(lid_c, prof, "lid_groove_t", "LDV_GRT").bodies.item(0); sp.combine(ldv, gr, CUT, False, "LDV_GR")
    sk, prof = sp.sketch_rect_model(lid_c, lgp,
        ("box_length / 2 - lid_frame_w / 2","lid_rab + lid_frame_w - lid_tenon_l","lid_groove_z"),
        {"x":"lid_frame_w","y":"lid_tenon_l"}, "LDV_TF_Sk", ev=ev)
    t = sp.ext_new(lid_c, prof, "lid_groove_t", "LDV_TF").bodies.item(0); sp.combine(ldv, t, JOIN, False, "LDV_TFJ")
    sk, prof = sp.sketch_rect_model(lid_c, lgp,
        ("box_length / 2 - lid_frame_w / 2","box_width - lid_frame_w","lid_groove_z"),
        {"x":"lid_frame_w","y":"lid_tenon_l"}, "LDV_TB_Sk", ev=ev)
    t = sp.ext_new(lid_c, prof, "lid_groove_t", "LDV_TB").bodies.item(0); sp.combine(ldv, t, JOIN, False, "LDV_TBJ")

    # Body-relative reference: Lid_Panel_L depends on Lid_Stile_L, Lid_Panel_R depends on Lid_Stile_R
    ref_lid_stile_l = ctx.find_body("Lid_Stile_L")
    ref_lid_stile_l_bb = ref_lid_stile_l.boundingBox
    ref_lid_stile_r = ctx.find_body("Lid_Stile_R")
    ref_lid_stile_r_bb = ref_lid_stile_r.boundingBox

    # ── 2 Panels (LEFT and RIGHT of center divider) ──
    lpp = sp.off_plane(lid_c, root.xYConstructionPlane, "lid_panel_z", "LP_Pl")
    sk, prof = sp.sketch_rect_model(lid_c, lpp,
        ("board_thick + lid_frame_w - lid_tongue_l","lid_rab + lid_frame_w - lid_tongue_l","lid_panel_z"),
        {"x":"box_length / 2 - board_thick - 3 * lid_frame_w / 2 + 2 * lid_tongue_l",
         "y":"box_width - 2 * lid_frame_w - lid_rab + 2 * lid_tongue_l"}, "LPL_Sk", ev=ev)
    lpl = sp.ext_new(lid_c, prof, "lid_panel_t", "LPL").bodies.item(0); lpl.name = "Lid_Panel_L"
    lrp = sp.off_plane(lid_c, root.xYConstructionPlane, "lid_panel_z + lid_groove_t", "LRab_Pl")
    px = "board_thick + lid_frame_w - lid_tongue_l"; py = "lid_rab + lid_frame_w - lid_tongue_l"
    rz = "lid_panel_z + lid_groove_t"
    pwx = "box_length / 2 - board_thick - 3 * lid_frame_w / 2 + 2 * lid_tongue_l"
    pwy = "box_width - 2 * lid_frame_w - lid_rab + 2 * lid_tongue_l"; rd = "lid_panel_t - lid_groove_t"
    sk, prof = sp.sketch_rect_model(lid_c, lrp, (px,py,rz), {"x":pwx,"y":"lid_tongue_l"}, "LPL_RbF_Sk", ev=ev); sp.ext_op(lid_c, prof, rd, CUT, lpl, "LPL_RbF")
    sk, prof = sp.sketch_rect_model(lid_c, lrp, (px,"box_width - lid_frame_w",rz), {"x":pwx,"y":"lid_tongue_l"}, "LPL_RbB_Sk", ev=ev); sp.ext_op(lid_c, prof, rd, CUT, lpl, "LPL_RbB")
    sk, prof = sp.sketch_rect_model(lid_c, lrp, (px,py,rz), {"x":"lid_tongue_l","y":pwy}, "LPL_RbL_Sk", ev=ev); sp.ext_op(lid_c, prof, rd, CUT, lpl, "LPL_RbL")
    sk, prof = sp.sketch_rect_model(lid_c, lrp, ("box_length / 2 - lid_frame_w / 2",py,rz), {"x":"lid_tongue_l","y":pwy}, "LPL_RbR_Sk", ev=ev); sp.ext_op(lid_c, prof, rd, CUT, lpl, "LPL_RbR")
    lpr = sp.mirror_body(lid_c, lpl, xmid_pl, "LPR_M").bodies.item(0); lpr.name = "Lid_Panel_R"

    sp.combine(lsl, [lpl, lpr], CUT, True, "LPG_SL"); sp.combine(lsr, [lpl, lpr], CUT, True, "LPG_SR")
    sp.combine(ldv, [lpl, lpr], CUT, True, "LPG_DV")
    sp.combine(lrf, [lpl, lpr], CUT, True, "LPG_RF"); sp.combine(lrb, [lpl, lpr], CUT, True, "LPG_RB")

    # Body-relative reference: Pull depends on Lid_Rail_F
    ref_lid_rail_f2 = ctx.find_body("Lid_Rail_F")
    ref_lid_rail_f2_bb = ref_lid_rail_f2.boundingBox

    # ── Pull (3/4 thick block, protrudes past case front, tenon into rail) ──
    pull_z_expr = "open_height + lid_frame_h / 2 - pull_h / 2"
    pull_y_pl = sp.off_plane(lid_c, root.xZConstructionPlane, "lid_rab - pull_d", "Pull_YPl")
    sk, prof = sp.sketch_rect_model(lid_c, pull_y_pl,
        ("box_length / 2 - pull_w / 2", "lid_rab - pull_d", pull_z_expr),
        {"x":"pull_w","z":"pull_h"}, "Pull_Sk", ev=ev)
    pull = sp.ext_new(lid_c, prof, "pull_d", "Pull").bodies.item(0); pull.name = "Pull"
    # Tenon from pull into front rail (0.5" wide)
    pt_pl = sp.off_plane(lid_c, root.xYConstructionPlane,
        "open_height + lid_frame_h / 2 - pull_h / 2", "PT_Pl")
    sk, prof = sp.sketch_rect_model(lid_c, pt_pl,
        ("box_length / 2 - 0.1875 in","lid_rab",
         "open_height + lid_frame_h / 2 - pull_h / 2"),
        {"x":"0.375 in","y":"lid_tongue_l"}, "PT_Sk", ev=ev)
    pt = sp.ext_new(lid_c, prof, "pull_h", "PT").bodies.item(0)
    sp.combine(lrf, pt, CUT, True, "PullMortise")
    sp.combine(pull, pt, JOIN, False, "PullTenonJ")

    # CUT front board: lid rail creates its recess, pull creates tight-fit notch
    sp.combine(front, lrf, CUT, True, "FrontRailCut")
    sp.combine(front, pull, CUT, True, "FrontPullCut")

    # ── Cleanup + Appearance ──
    for comp in [root, case_c, bot_c, ut_c, lt_c, lid_c]:
        for i in range(comp.sketches.count): comp.sketches.item(i).isVisible = False
        for i in range(comp.constructionPlanes.count): comp.constructionPlanes.item(i).isLightBulbOn = False
        for i in range(comp.constructionAxes.count): comp.constructionAxes.item(i).isLightBulbOn = False
    for label, c in [("Case", case_c), ("Bottom", bot_c), ("UpperTray", ut_c), ("LowerTrays", lt_c), ("Lid", lid_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{label}: {len(names)} -- {names}")
    sp.apply_appearance("white oak")
    sp.apply_appearance("ziricote", bodies=["Pull"])
    # Spalted maple panels applied via MCP post-build (avoids endgrain face overrides)
    print("Done")
