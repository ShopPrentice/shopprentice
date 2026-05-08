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
    params.add("bottom_thick", adsk.core.ValueInput.createByString("0.25 in"), "in", "Bottom plywood thickness")
    params.add("groove_depth", adsk.core.ValueInput.createByString("0.25 in"), "in", "Groove depth")
    params.add("groove_up", adsk.core.ValueInput.createByString("0.5 in"), "in", "Bottom groove offset")
    params.add("runner_w", adsk.core.ValueInput.createByString("0.375 in"), "in", "Runner width (Z)")
    params.add("runner_thick", adsk.core.ValueInput.createByString("0.25 in"), "in", "Runner thickness (X)")
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
    params.add("tray_height", adsk.core.ValueInput.createByString("1.5 in"), "in", "Tray side height")
    params.add("tray_thick", adsk.core.ValueInput.createByString("0.375 in"), "in", "Tray side thickness")
    params.add("tray_bottom_thick", adsk.core.ValueInput.createByString("0.25 in"), "in", "Tray bottom thickness")
    params.add("tray_cl", adsk.core.ValueInput.createByString("0.0625 in"), "in", "Tray clearance")
    params.add("div_thick", adsk.core.ValueInput.createByString("0.375 in"), "in", "Tray divider thickness")

    # Full board height (end boards = lid top). Dovetails run this full height for equal end pins.
    params.add("end_height", adsk.core.ValueInput.createByString("case_height"), "in", "End board height = total height")
    params.add("open_height", adsk.core.ValueInput.createByString("case_height - lid_frame_h"), "in", "Back board height (below lid)")

    dovetail.define_params(params, prefix="dt", angle="8 deg", tail_w="0.875 in",
        tail_count="4", joint_h_expr="end_height", thick_expr="board_thick", pad="0.75 in")

    params.add("interior_l", adsk.core.ValueInput.createByString("box_length - 2 * board_thick"), "in", "")
    params.add("interior_w", adsk.core.ValueInput.createByString("box_width - 2 * board_thick"), "in", "")
    params.add("runner_z", adsk.core.ValueInput.createByString("open_height - tray_height - lid_rab - runner_w - 0.0625 in"), "in", "")
    params.add("lid_panel_z", adsk.core.ValueInput.createByString("open_height + lid_frame_h - lid_panel_t"), "in", "")
    params.add("lid_groove_z", adsk.core.ValueInput.createByString("lid_panel_z"), "in", "")
    params.add("tray_z", adsk.core.ValueInput.createByString("runner_z + runner_w"), "in", "")

    xmid_pl = sp.off_plane(root, root.yZConstructionPlane, "box_length / 2", "XMid")
    ymid_pl = sp.off_plane(root, root.xZConstructionPlane, "box_width / 2", "YMid")

    # ── Case: ALL boards at end_height (dovetails need equal height) ──
    case_occ = sp.make_comp(root, "Case"); case_c = case_occ.component
    sk, prof = sp.sketch_rect_model(case_c, root.yZConstructionPlane,
        ("0 in","0 in","0 in"), {"y":"box_width","z":"end_height"}, "EndL_Sk", ev=ev)
    end_l = sp.ext_new(case_c, prof, "board_thick", "EndLBoard").bodies.item(0); end_l.name = "End_L"
    end_r = sp.mirror_body(case_c, end_l, xmid_pl, "EndR_M").bodies.item(0); end_r.name = "End_R"
    sk, prof = sp.sketch_rect_model(case_c, root.xZConstructionPlane,
        ("board_thick","0 in","0 in"), {"x":"interior_l","z":"end_height"}, "Front_Sk", ev=ev)
    front = sp.ext_new(case_c, prof, "board_thick", "FrontBoard").bodies.item(0); front.name = "Front"
    back = sp.mirror_body(case_c, front, ymid_pl, "Back_M").bodies.item(0); back.name = "Back"
    rl_pl = sp.off_plane(case_c, root.yZConstructionPlane, "board_thick", "RL_Pl")
    sk, prof = sp.sketch_rect_model(case_c, rl_pl,
        ("board_thick","board_thick","runner_z"), {"y":"interior_w","z":"runner_w"}, "RunL_Sk", ev=ev)
    runner_l = sp.ext_new(case_c, prof, "runner_thick", "RunL").bodies.item(0); runner_l.name = "Runner_L"
    runner_r = sp.mirror_body(case_c, runner_l, xmid_pl, "RunR_M").bodies.item(0); runner_r.name = "Runner_R"

    # ── Bottom ──
    bot_occ = sp.make_comp(root, "Bottom"); bot_c = bot_occ.component
    bpp = sp.off_plane(bot_c, root.xYConstructionPlane, "groove_up", "BP_Pl")
    sk, prof = sp.sketch_rect_model(bot_c, bpp,
        ("board_thick - groove_depth","board_thick - groove_depth","groove_up"),
        {"x":"interior_l + 2 * groove_depth","y":"interior_w + 2 * groove_depth"}, "BP_Sk", ev=ev)
    bp = sp.ext_new(bot_c, prof, "bottom_thick", "BP").bodies.item(0); bp.name = "Bottom"
    sp.combine(end_l, bp, CUT, True, "BG_EL"); sp.combine(end_r, bp, CUT, True, "BG_ER")
    sp.combine(front, bp, CUT, True, "BG_F"); sp.combine(back, bp, CUT, True, "BG_B")

    # ── Dovetails at full end_height (equal top/bottom end pins) ──
    dovetail.box(comp=case_c, front=end_l, left=front, x_mid=ymid_pl, y_mid=xmid_pl,
        thick_expr="board_thick", right=back, back=end_r, prefix="dt", name="DT", ev=ev,
        fl_plane=case_c.xZConstructionPlane, front_expr="0 in",
        joint_axis="z", thick_axis="x", thick_dir=1)
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

    # ── Tray ──
    tray_occ = sp.make_comp(root, "Tray"); tray_c = tray_occ.component
    tp = sp.off_plane(tray_c, root.xYConstructionPlane, "tray_z", "Tray_Pl")
    sk, prof = sp.sketch_rect_model(tray_c, tp,
        ("board_thick + tray_cl","board_thick + tray_cl","tray_z"),
        {"x":"interior_l - 2 * tray_cl","y":"tray_thick"}, "TF_Sk", ev=ev)
    tf = sp.ext_new(tray_c, prof, "tray_height", "TF").bodies.item(0); tf.name = "Tray_Front"
    tb = sp.mirror_body(tray_c, tf, ymid_pl, "TB_M").bodies.item(0); tb.name = "Tray_Back"
    sk, prof = sp.sketch_rect_model(tray_c, tp,
        ("board_thick + tray_cl","board_thick + tray_cl + tray_thick","tray_z"),
        {"x":"tray_thick","y":"interior_w - 2 * tray_cl - 2 * tray_thick"}, "TEL_Sk", ev=ev)
    tel = sp.ext_new(tray_c, prof, "tray_height", "TEL").bodies.item(0); tel.name = "Tray_End_L"
    ter = sp.mirror_body(tray_c, tel, xmid_pl, "TER_M").bodies.item(0); ter.name = "Tray_End_R"
    sk, prof = sp.sketch_rect_model(tray_c, tp,
        ("board_thick + tray_cl","board_thick + tray_cl","tray_z"),
        {"x":"interior_l - 2 * tray_cl","y":"interior_w - 2 * tray_cl"}, "TBot_Sk", ev=ev)
    tbot = sp.ext_new(tray_c, prof, "tray_bottom_thick", "TBot").bodies.item(0); tbot.name = "Tray_Bottom"
    sp.combine(tf, tbot, CUT, True, "TBG_F"); sp.combine(tb, tbot, CUT, True, "TBG_B")
    sp.combine(tel, tbot, CUT, True, "TBG_EL"); sp.combine(ter, tbot, CUT, True, "TBG_ER")
    tdze = "tray_z + tray_bottom_thick"; tdhe = "tray_height - tray_bottom_thick"
    tdp = sp.off_plane(tray_c, root.xYConstructionPlane, tdze, "TD_Pl")
    sk, prof = sp.sketch_rect_model(tray_c, tdp,
        ("board_thick + tray_cl + tray_thick","box_width / 2 - div_thick / 2",tdze),
        {"x":"interior_l - 2 * tray_cl - 2 * tray_thick","y":"div_thick"}, "TD_Sk", ev=ev)
    td = sp.ext_new(tray_c, prof, tdhe, "TD").bodies.item(0); td.name = "Tray_Div"
    slot_pl = sp.off_plane(tray_c, root.xYConstructionPlane, "tray_z + tray_height - 0.625 in", "TDSlot_Pl")
    sk, prof = sp.sketch_rect_model(tray_c, slot_pl,
        ("box_length / 2 - 1.5 in","box_width / 2 - div_thick / 2","tray_z + tray_height - 0.625 in"),
        {"x":"3 in","y":"div_thick"}, "TDSlot_Sk", ev=ev)
    sp.ext_op(tray_c, prof, "0.375 in", CUT, td, "TDSlot")

    # ── Lid (frame-and-panel between end boards, divider runs Y) ──
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
    for comp in [root, case_c, bot_c, tray_c, lid_c]:
        for i in range(comp.sketches.count): comp.sketches.item(i).isVisible = False
        for i in range(comp.constructionPlanes.count): comp.constructionPlanes.item(i).isLightBulbOn = False
        for i in range(comp.constructionAxes.count): comp.constructionAxes.item(i).isLightBulbOn = False
    for label, c in [("Case", case_c), ("Bottom", bot_c), ("Tray", tray_c), ("Lid", lid_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{label}: {len(names)} -- {names}")
    sp.apply_appearance("white oak")
    sp.apply_appearance("ziricote", bodies=["Pull"])
    # Spalted maple panels applied via MCP post-build (avoids endgrain face overrides)
    print("Done")
