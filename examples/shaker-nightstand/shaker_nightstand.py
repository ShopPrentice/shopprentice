"""Shaker Nightstand — parametric case-construction nightstand.

Full side panels with tapered feet, half-blind dovetailed sub-top,
two-part shelves (stretcher with sliding dovetail + rear board in dado),
divider frame, rabbeted back panel with feet, overhanging top. White oak.
"""

import math
import adsk.core
import adsk.fusion

from helpers import sp
from woodworking.templates import half_blind_dovetail
from woodworking.templates import dovetailed_drawer

P = adsk.core.Point3D.create
VI = adsk.core.ValueInput.createByString
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation


def run(context):
    ctx = sp.DesignContext()
    design = ctx.design
    root = ctx.root
    params = ctx.params
    ev = ctx.ev

    # ════════════════════════════════════════════════════════════
    #  PARAMETERS
    # ════════════════════════════════════════════════════════════

    # -- Envelope --
    params.add("case_w", VI("24 in"), "in", "Overall case width (X)")
    params.add("case_d", VI("16 in"), "in", "Overall case depth (Y)")
    params.add("side_h", VI("28 in"), "in", "Side panel height (Z)")
    params.add("top_thick", VI("0.75 in"), "in", "Top board thickness")
    params.add("top_overhang", VI("0.5 in"), "in", "Top overhang beyond case")

    # -- Parts --
    params.add("board_thick", VI("0.75 in"), "in", "Side/shelf board thickness")
    params.add("back_thick", VI("0.25 in"), "in", "Back panel thickness")

    # -- Layout --
    params.add("drawer_h", VI("5 in"), "in", "Drawer opening height")
    params.add("leg_h", VI("3 in"), "in", "Leg cutout height from floor")
    params.add("leg_w", VI("1.5 in"), "in", "Leg width at floor")
    params.add("taper_offset", VI("0.375 in"), "in", "Foot taper inset at floor")
    params.add("frame_w", VI("2.5 in"), "in", "Divider frame member width")
    params.add("drawer_gap", VI("0.125 in"), "in", "Gap around drawers")
    params.add("stretcher_d", VI("1.5 in"), "in", "Stretcher depth (front-to-back)")
    params.add("bot_shelf_lift", VI("1.5 in"), "in", "Bottom shelf lift above legs")

    # -- Derived --
    params.add("inner_w", VI("case_w - 2 * board_thick"), "in", "Inner width")
    params.add("inner_d", VI("case_d - back_thick"), "in",
               "Inner depth (front to back rabbet)")
    params.add("bot_shelf_z", VI("leg_h + bot_shelf_lift"), "in",
               "Bottom shelf Z position")

    # Vertical layout — positions of horizontal boards (bottom face Z)
    params.add("sub_top_z", VI("side_h - board_thick"), "in",
               "Sub-top bottom face Z")
    params.add("div_z", VI("sub_top_z - drawer_h - board_thick"), "in",
               "Divider bottom face Z")
    params.add("shelf_z", VI("div_z - drawer_h - board_thick"), "in",
               "Shelf (drawer bottom) bottom face Z")
    params.add("open_shelf_h",
               VI("shelf_z - bot_shelf_z - board_thick"), "in",
               "Open shelf height (derived)")

    # Midplanes
    params.add("mid_x", VI("case_w / 2"), "in", "X midplane offset")
    params.add("mid_y", VI("case_d / 2"), "in", "Y midplane offset")

    # -- Joinery --
    params.add("dado_depth", VI("0.25 in"), "in", "Dado depth into side panels")
    params.add("dt_slide_depth", VI("2 / 3 * board_thick"), "in",
               "Sliding dovetail depth into side")
    params.add("dt_slide_shoulder", VI("dt_slide_depth * tan(8 deg)"), "in",
               "Sliding DT shoulder offset per side")

    # Half-blind dovetails for sub-top to sides
    half_blind_dovetail.define_params(params, prefix="hbd_case",
        angle="8 deg", tail_w="1.5 in",
        tail_count="7",
        joint_h_expr="case_d",
        pin_thick_expr="board_thick",
        lap="0.25 in")

    # -- Knobs --
    params.add("knob_dia", VI("1.25 in"), "in", "Drawer knob diameter")
    params.add("knob_proj", VI("0.75 in"), "in", "Knob projection from front")

    # ════════════════════════════════════════════════════════════
    #  MIDPLANES
    # ════════════════════════════════════════════════════════════
    x_mid = sp.off_plane(root, root.yZConstructionPlane, "mid_x", "XMid")
    y_mid = sp.off_plane(root, root.xZConstructionPlane, "mid_y", "YMid")

    # ════════════════════════════════════════════════════════════
    #  SIDES COMPONENT
    # ════════════════════════════════════════════════════════════
    sides_occ = sp.make_comp(root, "Sides")
    sides_c = sides_occ.component

    # -- Left side panel (sketch on XZ, extrude +Y) --
    sk, prof = sp.sketch_rect_model(sides_c, root.xZConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "board_thick", "z": "side_h"},
        "SideL_Sk", ev=ev)
    side_l_ext = sp.ext_new(sides_c, prof, "case_d", "SideL")
    side_l = side_l_ext.bodies.item(0)
    side_l.name = "Side_Left"

    # -- Leg cutout on left side (flat rectangle — two tapered feet) --
    sk_leg, _ = sp.sketch_rect_model(sides_c,
        sp.find_face(side_l, "x", +1),
        ("board_thick", "leg_w", "0 in"),
        {"y": "case_d - 2 * leg_w", "z": "leg_h"},
        "LegCut_Sk", ev=ev)
    prof_leg = sp.smallest_profile(sk_leg)
    leg_cut = sp.ext_op(sides_c, prof_leg, "board_thick", CUT,
                        side_l, "LegCutL", flip=True)

    # -- Foot tapers on left side (triangle CUTs on inner sides) --
    bt_val = ev("board_thick")
    lw_val = ev("leg_w")
    lh_val = ev("leg_h")
    to_val = ev("taper_offset")
    cd_val = ev("case_d")

    # Front foot taper: triangle on YZ plane (X=0), extrude +X
    sk_tf = sides_c.sketches.add(root.yZConstructionPlane)
    sk_tf.name = "TaperFrontL_Sk"
    m2s_tf = sk_tf.modelToSketchSpace
    tf_p1 = m2s_tf(P(0, lw_val, lh_val))
    tf_p2 = m2s_tf(P(0, lw_val, 0))
    tf_p3 = m2s_tf(P(0, lw_val - to_val, 0))
    lines_tf = sk_tf.sketchCurves.sketchLines
    tf_l1 = lines_tf.addByTwoPoints(P(tf_p1.x, tf_p1.y, 0),
                                     P(tf_p2.x, tf_p2.y, 0))
    tf_l2 = lines_tf.addByTwoPoints(P(tf_p2.x, tf_p2.y, 0),
                                     P(tf_p3.x, tf_p3.y, 0))
    tf_l3 = lines_tf.addByTwoPoints(P(tf_p3.x, tf_p3.y, 0),
                                     P(tf_p1.x, tf_p1.y, 0))
    orient_tf = sp.probe_orientations(sk_tf, 0, lw_val, lh_val / 2)
    dims_tf = sk_tf.sketchDimensions
    dims_tf.addDistanceDimension(
        tf_l1.startSketchPoint, tf_l1.endSketchPoint,
        orient_tf['z'], m2s_tf(P(0, lw_val + 1, lh_val / 2))
    ).parameter.expression = "leg_h"
    dims_tf.addDistanceDimension(
        tf_l2.startSketchPoint, tf_l2.endSketchPoint,
        orient_tf['y'], m2s_tf(P(0, lw_val - to_val / 2, -1))
    ).parameter.expression = "taper_offset"
    prof_tf = sp.smallest_profile(sk_tf)
    sp.ext_op(sides_c, prof_tf, "board_thick", CUT, side_l, "TaperFrontL")

    # Back foot taper: similar triangle at back foot inner edge
    sk_tb = sides_c.sketches.add(root.yZConstructionPlane)
    sk_tb.name = "TaperBackL_Sk"
    m2s_tb = sk_tb.modelToSketchSpace
    tb_p1 = m2s_tb(P(0, cd_val - lw_val, lh_val))
    tb_p2 = m2s_tb(P(0, cd_val - lw_val, 0))
    tb_p3 = m2s_tb(P(0, cd_val - lw_val + to_val, 0))
    lines_tb = sk_tb.sketchCurves.sketchLines
    tb_l1 = lines_tb.addByTwoPoints(P(tb_p1.x, tb_p1.y, 0),
                                     P(tb_p2.x, tb_p2.y, 0))
    tb_l2 = lines_tb.addByTwoPoints(P(tb_p2.x, tb_p2.y, 0),
                                     P(tb_p3.x, tb_p3.y, 0))
    tb_l3 = lines_tb.addByTwoPoints(P(tb_p3.x, tb_p3.y, 0),
                                     P(tb_p1.x, tb_p1.y, 0))
    orient_tb = sp.probe_orientations(sk_tb, 0, cd_val - lw_val, lh_val / 2)
    dims_tb = sk_tb.sketchDimensions
    dims_tb.addDistanceDimension(
        tb_l1.startSketchPoint, tb_l1.endSketchPoint,
        orient_tb['z'], m2s_tb(P(0, cd_val - lw_val - 1, lh_val / 2))
    ).parameter.expression = "leg_h"
    dims_tb.addDistanceDimension(
        tb_l2.startSketchPoint, tb_l2.endSketchPoint,
        orient_tb['y'], m2s_tb(P(0, cd_val - lw_val + to_val / 2, -1))
    ).parameter.expression = "taper_offset"
    prof_tb = sp.smallest_profile(sk_tb)
    sp.ext_op(sides_c, prof_tb, "board_thick", CUT, side_l, "TaperBackL")

    # -- Mirror left side to right (includes leg cutout + tapers) --
    side_r_mir = sp.mirror_body(sides_c, side_l, x_mid, "SideR_Mirror")
    side_r = side_r_mir.bodies.item(0)
    side_r.name = "Side_Right"

    # ════════════════════════════════════════════════════════════
    #  CASE COMPONENT (horizontal boards + divider frame)
    # ════════════════════════════════════════════════════════════
    case_occ = sp.make_comp(root, "Case")
    case_c = case_occ.component

    case_x_mid = sp.off_plane(case_c, case_c.yZConstructionPlane,
                               "mid_x", "CaseXMid")

    # -- Sub-top board (half-blind dovetailed to sides at top) --
    sk_st, prof_st = sp.sketch_rect_model(case_c, root.xZConstructionPlane,
        ("board_thick", "0 in", "sub_top_z"),
        {"x": "inner_w", "z": "board_thick"},
        "SubTop_Sk", ev=ev)
    sub_top_ext = sp.ext_new(case_c, prof_st, "case_d", "SubTop")
    sub_top = sub_top_ext.bodies.item(0)
    sub_top.name = "SubTop"

    # -- Evaluated values for sliding dovetail tenon geometry --
    dtd_val = ev("dt_slide_depth")
    dts_val = ev("dt_slide_shoulder")
    cw_val = ev("case_w")

    # ────────────────────────────────────────────────────────────
    #  Helper: build a sliding-dovetail stretcher + rear board
    # ────────────────────────────────────────────────────────────
    def build_shelf(z_expr, z_val, tag):
        """Build a two-part shelf: stretcher (front) + board (rear).

        Returns (stretcher_body, board_body).
        """
        # --- Stretcher rectangle (inner width, at front face) ---
        sk_s, prof_s = sp.sketch_rect_model(case_c, root.xZConstructionPlane,
            ("board_thick", "0 in", z_expr),
            {"x": "inner_w", "z": "board_thick"},
            f"{tag}Str_Sk", ev=ev)
        s_ext = sp.ext_new(case_c, prof_s, "stretcher_d", f"{tag}Str")
        stretcher = s_ext.bodies.item(0)
        stretcher.name = f"{tag}_Stretcher"

        # --- Left dovetail tenon (trapezoid on xZConstructionPlane) ---
        sk_dtl = case_c.sketches.add(root.xZConstructionPlane)
        sk_dtl.name = f"{tag}DTL_Sk"
        m = sk_dtl.modelToSketchSpace
        # Trapezoid: wider at deep end, narrower at shoulder
        dp1 = m(P(bt_val - dtd_val, 0, z_val))
        dp2 = m(P(bt_val, 0, z_val + dts_val))
        dp3 = m(P(bt_val, 0, z_val + bt_val - dts_val))
        dp4 = m(P(bt_val - dtd_val, 0, z_val + bt_val))
        sl = sk_dtl.sketchCurves.sketchLines
        dl1 = sl.addByTwoPoints(P(dp1.x, dp1.y, 0), P(dp2.x, dp2.y, 0))
        dl2 = sl.addByTwoPoints(P(dp2.x, dp2.y, 0), P(dp3.x, dp3.y, 0))
        dl3 = sl.addByTwoPoints(P(dp3.x, dp3.y, 0), P(dp4.x, dp4.y, 0))
        dl4 = sl.addByTwoPoints(P(dp4.x, dp4.y, 0), P(dp1.x, dp1.y, 0))

        ori = sp.probe_orientations(sk_dtl, bt_val - dtd_val / 2, 0,
                                     z_val + bt_val / 2)
        dd = sk_dtl.sketchDimensions
        # Deep face height = board_thick
        dd.addDistanceDimension(
            dl4.startSketchPoint, dl4.endSketchPoint,
            ori['z'], m(P(bt_val - dtd_val - 1, 0, z_val + bt_val / 2))
        ).parameter.expression = "board_thick"
        # Tenon depth = dt_slide_depth
        dd.addDistanceDimension(
            dl4.startSketchPoint, dl2.startSketchPoint,
            ori['x'], m(P(bt_val - dtd_val / 2, 0, z_val - 1))
        ).parameter.expression = "dt_slide_depth"
        # Shoulder face height = board_thick - 2 * shoulder offset
        dd.addDistanceDimension(
            dl2.startSketchPoint, dl2.endSketchPoint,
            ori['z'], m(P(bt_val + 1, 0, z_val + bt_val / 2))
        ).parameter.expression = "board_thick - 2 * dt_slide_shoulder"

        pf_dtl = sp.smallest_profile(sk_dtl)
        dtl_ext = sp.ext_new(case_c, pf_dtl, "stretcher_d", f"{tag}DTL")
        dtl_body = dtl_ext.bodies.item(0)

        # Mirror left tenon extrude → right tenon
        dtr_mir = sp.mirror_feats(case_c, [dtl_ext], case_x_mid,
                                   f"{tag}DTR_Mir")
        dtr_body = dtr_mir.bodies.item(0)

        # JOIN both tenons to stretcher
        sp.combine(stretcher, [dtl_body], JOIN, False, f"{tag}DTL_Join")
        sp.combine(stretcher, [dtr_body], JOIN, False, f"{tag}DTR_Join")

        # --- Rear board (behind stretcher, with dado extensions) ---
        brd_pl = sp.off_plane(case_c, root.xZConstructionPlane,
                               "stretcher_d", f"{tag}Brd_Pl")
        sk_b, prof_b = sp.sketch_rect_model(case_c, brd_pl,
            ("board_thick - dado_depth", "stretcher_d", z_expr),
            {"x": "inner_w + 2 * dado_depth", "z": "board_thick"},
            f"{tag}Brd_Sk", ev=ev)
        b_ext = sp.ext_new(case_c, prof_b, "inner_d - stretcher_d",
                            f"{tag}Brd")
        board = b_ext.bodies.item(0)
        board.name = f"{tag}_Board"

        return stretcher, board

    # -- Bottom shelf (stretcher + board, raised above legs) --
    bsz_val = ev("bot_shelf_z")
    bot_stretcher, bot_board = build_shelf("bot_shelf_z", bsz_val, "BotSh")

    # -- Divider frame (4 pieces between upper and lower drawers) --
    # Front rail (full width with dado extensions)
    sk_dfr, prof_dfr = sp.sketch_rect_model(case_c, root.xZConstructionPlane,
        ("board_thick", "0 in", "div_z"),
        {"x": "inner_w", "z": "board_thick"},
        "DivFR_Sk", ev=ev)
    dfr_ext = sp.ext_new(case_c, prof_dfr, "frame_w", "DivFR")
    div_front_rail = dfr_ext.bodies.item(0)
    div_front_rail.name = "Div_FrontRail"

    # Sliding dovetail tenons on divider front rail
    dz_val = ev("div_z")
    sk_dfl = case_c.sketches.add(root.xZConstructionPlane)
    sk_dfl.name = "DivFR_DTL_Sk"
    m_df = sk_dfl.modelToSketchSpace
    dfp1 = m_df(P(bt_val - dtd_val, 0, dz_val))
    dfp2 = m_df(P(bt_val, 0, dz_val + dts_val))
    dfp3 = m_df(P(bt_val, 0, dz_val + bt_val - dts_val))
    dfp4 = m_df(P(bt_val - dtd_val, 0, dz_val + bt_val))
    sl_df = sk_dfl.sketchCurves.sketchLines
    dfl1 = sl_df.addByTwoPoints(P(dfp1.x, dfp1.y, 0), P(dfp2.x, dfp2.y, 0))
    dfl2 = sl_df.addByTwoPoints(P(dfp2.x, dfp2.y, 0), P(dfp3.x, dfp3.y, 0))
    dfl3 = sl_df.addByTwoPoints(P(dfp3.x, dfp3.y, 0), P(dfp4.x, dfp4.y, 0))
    dfl4 = sl_df.addByTwoPoints(P(dfp4.x, dfp4.y, 0), P(dfp1.x, dfp1.y, 0))

    ori_df = sp.probe_orientations(sk_dfl, bt_val - dtd_val / 2, 0,
                                    dz_val + bt_val / 2)
    dd_df = sk_dfl.sketchDimensions
    dd_df.addDistanceDimension(
        dfl4.startSketchPoint, dfl4.endSketchPoint,
        ori_df['z'], m_df(P(bt_val - dtd_val - 1, 0, dz_val + bt_val / 2))
    ).parameter.expression = "board_thick"
    dd_df.addDistanceDimension(
        dfl4.startSketchPoint, dfl2.startSketchPoint,
        ori_df['x'], m_df(P(bt_val - dtd_val / 2, 0, dz_val - 1))
    ).parameter.expression = "dt_slide_depth"
    dd_df.addDistanceDimension(
        dfl2.startSketchPoint, dfl2.endSketchPoint,
        ori_df['z'], m_df(P(bt_val + 1, 0, dz_val + bt_val / 2))
    ).parameter.expression = "board_thick - 2 * dt_slide_shoulder"

    pf_dfl = sp.smallest_profile(sk_dfl)
    dfl_ext = sp.ext_new(case_c, pf_dfl, "frame_w", "DivFR_DTL")
    dfl_body = dfl_ext.bodies.item(0)

    dfr_dt_mir = sp.mirror_feats(case_c, [dfl_ext], case_x_mid,
                                  "DivFR_DTR_Mir")
    dfr_body_r = dfr_dt_mir.bodies.item(0)

    sp.combine(div_front_rail, [dfl_body], JOIN, False, "DivFR_DTL_Join")
    sp.combine(div_front_rail, [dfr_body_r], JOIN, False, "DivFR_DTR_Join")

    # Back rail (full width with dado extensions, at rear)
    div_br_pl = sp.off_plane(case_c, root.xZConstructionPlane,
                              "inner_d - frame_w", "DivBR_Pl")
    sk_dbr, prof_dbr = sp.sketch_rect_model(case_c, div_br_pl,
        ("board_thick - dado_depth", "inner_d - frame_w", "div_z"),
        {"x": "inner_w + 2 * dado_depth", "z": "board_thick"},
        "DivBR_Sk", ev=ev)
    dbr_ext = sp.ext_new(case_c, prof_dbr, "frame_w", "DivBR")
    div_back_rail = dbr_ext.bodies.item(0)
    div_back_rail.name = "Div_BackRail"

    # Left stile (between rails, flush with side inner face)
    div_stile_pl = sp.off_plane(case_c, root.xZConstructionPlane,
                                 "frame_w", "DivStile_Pl")
    sk_dls, prof_dls = sp.sketch_rect_model(case_c, div_stile_pl,
        ("board_thick - dado_depth", "frame_w", "div_z"),
        {"x": "frame_w + dado_depth", "z": "board_thick"},
        "DivLS_Sk", ev=ev)
    dls_ext = sp.ext_new(case_c, prof_dls, "inner_d - 2 * frame_w", "DivLS")
    div_left_stile = dls_ext.bodies.item(0)
    div_left_stile.name = "Div_LeftStile"

    # Right stile (mirror of left)
    drs_mir = sp.mirror_body(case_c, div_left_stile, case_x_mid, "DivRS_Mir")
    div_right_stile = drs_mir.bodies.item(0)
    div_right_stile.name = "Div_RightStile"

    # -- Shelf (stretcher + board, bottom of lower drawer section) --
    sz_val = ev("shelf_z")
    shelf_stretcher, shelf_board = build_shelf("shelf_z", sz_val, "Sh")

    # ════════════════════════════════════════════════════════════
    #  TOP COMPONENT
    # ════════════════════════════════════════════════════════════
    top_occ = sp.make_comp(root, "Top")
    top_c = top_occ.component

    top_pl = sp.off_plane(top_c, root.xYConstructionPlane, "side_h", "Top_Pl")
    sk_top = top_c.sketches.add(top_pl)
    sk_top.name = "Top_Sk"
    m2s_t = sk_top.modelToSketchSpace
    sh = ev("side_h")
    ovh = ev("top_overhang")
    cw = ev("case_w")

    s0 = m2s_t(P(-ovh, -ovh, sh))
    s1 = m2s_t(P(cw + ovh, cd_val + ovh, sh))
    rect_t = sk_top.sketchCurves.sketchLines.addTwoPointRectangle(
        P(s0.x, s0.y, 0), P(s1.x, s1.y, 0))
    gc = sk_top.geometricConstraints
    gc.addHorizontal(rect_t.item(0))
    gc.addHorizontal(rect_t.item(2))
    gc.addVertical(rect_t.item(1))
    gc.addVertical(rect_t.item(3))

    orient_t = sp.probe_orientations(sk_top, cw / 2, cd_val / 2, sh)
    dt_top = sk_top.sketchDimensions
    dt_top.addDistanceDimension(
        rect_t.item(0).startSketchPoint, rect_t.item(0).endSketchPoint,
        orient_t['x'], m2s_t(P(cw / 2, -ovh - 3, sh))
    ).parameter.expression = "case_w + 2 * top_overhang"
    dt_top.addDistanceDimension(
        rect_t.item(1).startSketchPoint, rect_t.item(1).endSketchPoint,
        orient_t['y'], m2s_t(P(cw + ovh + 3, cd_val / 2, sh))
    ).parameter.expression = "case_d + 2 * top_overhang"

    sp.refs_to_construction(sk_top)
    prof_top = sp.smallest_profile(sk_top)
    top_ext = sp.ext_new(top_c, prof_top, "top_thick", "TopBoard")
    top_body = top_ext.bodies.item(0)
    top_body.name = "Top"

    # ════════════════════════════════════════════════════════════
    #  BACK COMPONENT — extends to floor with feet and tapers
    # ════════════════════════════════════════════════════════════
    back_occ = sp.make_comp(root, "Back")
    back_c = back_occ.component

    back_pl = sp.off_plane(back_c, root.xZConstructionPlane,
                           "case_d - back_thick", "Back_Pl")

    # Full height from floor to sub_top_z
    sk_bk, prof_bk = sp.sketch_rect_model(back_c, back_pl,
        ("board_thick - back_thick", "case_d - back_thick", "0 in"),
        {"x": "inner_w + 2 * back_thick", "z": "sub_top_z"},
        "Back_Sk", ev=ev)
    back_ext = sp.ext_new(back_c, prof_bk, "back_thick", "BackPanel")
    back_body = back_ext.bodies.item(0)
    back_body.name = "Back"

    # Leg cutout on back panel (center rectangle at bottom)
    sk_bkl, prof_bkl = sp.sketch_rect_model(back_c, back_pl,
        ("board_thick - back_thick + leg_w", "case_d - back_thick", "0 in"),
        {"x": "inner_w + 2 * back_thick - 2 * leg_w", "z": "leg_h"},
        "BackLegCut_Sk", ev=ev)
    sp.ext_op(back_c, prof_bkl, "back_thick", CUT, back_body, "BackLegCut")

    # Foot tapers on back panel — left foot inner edge
    bk_thick_val = ev("back_thick")
    bk_y = cd_val - bk_thick_val
    bk_lf_inner = bt_val - bk_thick_val + lw_val

    sk_btl = back_c.sketches.add(back_pl)
    sk_btl.name = "BackTaperL_Sk"
    m2s_btl = sk_btl.modelToSketchSpace
    btl_p1 = m2s_btl(P(bk_lf_inner, bk_y, lh_val))
    btl_p2 = m2s_btl(P(bk_lf_inner, bk_y, 0))
    btl_p3 = m2s_btl(P(bk_lf_inner - to_val, bk_y, 0))
    lines_btl = sk_btl.sketchCurves.sketchLines
    btl_l1 = lines_btl.addByTwoPoints(P(btl_p1.x, btl_p1.y, 0),
                                       P(btl_p2.x, btl_p2.y, 0))
    btl_l2 = lines_btl.addByTwoPoints(P(btl_p2.x, btl_p2.y, 0),
                                       P(btl_p3.x, btl_p3.y, 0))
    btl_l3 = lines_btl.addByTwoPoints(P(btl_p3.x, btl_p3.y, 0),
                                       P(btl_p1.x, btl_p1.y, 0))
    orient_btl = sp.probe_orientations(sk_btl, bk_lf_inner, bk_y, lh_val / 2)
    dims_btl = sk_btl.sketchDimensions
    dims_btl.addDistanceDimension(
        btl_l1.startSketchPoint, btl_l1.endSketchPoint,
        orient_btl['z'], m2s_btl(P(bk_lf_inner + 1, bk_y, lh_val / 2))
    ).parameter.expression = "leg_h"
    dims_btl.addDistanceDimension(
        btl_l2.startSketchPoint, btl_l2.endSketchPoint,
        orient_btl['x'], m2s_btl(P(bk_lf_inner - to_val / 2, bk_y, -1))
    ).parameter.expression = "taper_offset"
    prof_btl = sp.smallest_profile(sk_btl)
    bk_taper_l = sp.ext_op(back_c, prof_btl, "back_thick", CUT,
                            back_body, "BackTaperL")

    # Mirror left foot taper to right foot
    back_x_mid = sp.off_plane(back_c, back_c.yZConstructionPlane,
                               "mid_x", "BackXMid")
    sp.mirror_feats(back_c, [bk_taper_l], back_x_mid, "BackTaperR_Mir")

    # ════════════════════════════════════════════════════════════
    #  DRAWERS COMPONENT (no runners — drawers sit directly)
    # ════════════════════════════════════════════════════════════
    drawer_occ = sp.make_comp(root, "Drawers")
    drawer_c = drawer_occ.component

    dovetailed_drawer.define_params(params, prefix="dd",
        drawer_w="inner_w - 2 * drawer_gap",
        drawer_d="inner_d - 2 * drawer_gap",
        drawer_h="drawer_h - 2 * drawer_gap",
        front_thick="0.75 in",
        side_thick="0.5 in",
        bottom_thick="0.25 in",
        front_tail_count="3",
        back_tail_count="3",
        x_offset="board_thick + drawer_gap",
        z_offset="shelf_z + board_thick + drawer_gap")

    dd_result = dovetailed_drawer.build(drawer_c, prefix="dd", ev=ev)

    # -- Drawer knob (revolved spline — drag fit points to reshape) --
    knob_sk_pl = sp.off_plane(drawer_c, root.yZConstructionPlane,
                               "mid_x", "KnobSk_Pl")
    sk_kn = drawer_c.sketches.add(knob_sk_pl)
    sk_kn.name = "Knob_Sk"
    m_kn = sk_kn.modelToSketchSpace

    kn_cx = ev("mid_x")
    kn_cz = ev("dd_zo") + ev("dd_fh") / 2
    kn_r = ev("knob_dia") / 2
    kn_p = ev("knob_proj")
    stem_r = kn_r * 0.32

    # Spline profile — 5 adjustable fit points (drag in Fusion to reshape)
    profile_pts = [
        P(kn_cx, 0, kn_cz + stem_r),                    # 1 stem at face
        P(kn_cx, -kn_p * 0.35, kn_cz + kn_r * 0.35),   # 2 stem body
        P(kn_cx, -kn_p * 0.533, kn_cz + kn_r * 0.72),  # 3 cap flare
        P(kn_cx, -kn_p * 0.833, kn_cz + kn_r * 0.954), # 4 cap dome
        P(kn_cx, -kn_p, kn_cz),                         # 5 tip on axis
    ]
    pts_coll = adsk.core.ObjectCollection.create()
    for mp in profile_pts:
        sk_pt = m_kn(mp)
        pts_coll.add(P(sk_pt.x, sk_pt.y, 0))
    spline = sk_kn.sketchCurves.sketchFittedSplines.add(pts_coll)

    # Flat base: perpendicular line from axis to spline start
    axis_base = m_kn(P(kn_cx, 0, kn_cz))
    sp_start = spline.startSketchPoint.geometry
    base_line = sk_kn.sketchCurves.sketchLines.addByTwoPoints(
        P(axis_base.x, axis_base.y, 0), P(sp_start.x, sp_start.y, 0))

    # Close profile along axis (tip → axis base)
    sp_end = spline.endSketchPoint.geometry
    bl_start = base_line.startSketchPoint.geometry
    closing_line = sk_kn.sketchCurves.sketchLines.addByTwoPoints(
        P(sp_end.x, sp_end.y, 0), P(bl_start.x, bl_start.y, 0))

    prof_kn = sp.smallest_profile(sk_kn)

    # Revolve 360° around closing line (axis of symmetry)
    rev_inp = drawer_c.features.revolveFeatures.createInput(
        prof_kn, closing_line, NEW)
    rev_inp.setAngleExtent(False, VI("360 deg"))
    kn_feat = drawer_c.features.revolveFeatures.add(rev_inp)
    kn_feat.name = "KnobRevolve"
    knob = kn_feat.bodies.item(0)
    knob.name = "Knob"

    dd_result["all_bodies"].append(knob)

    dovetailed_drawer.pattern(drawer_c, dd_result["all_bodies"],
        "2", "drawer_h + board_thick", ev=ev)

    # ════════════════════════════════════════════════════════════
    #  JOINERY — dados, rabbet, sliding dovetails, half-blind DTs
    # ════════════════════════════════════════════════════════════

    # -- Sliding dovetails: stretchers + divider front rail into Sides --
    sp.combine(side_l, [bot_stretcher], CUT, True, "SlideDT_BotStr_L")
    sp.combine(side_r, [bot_stretcher], CUT, True, "SlideDT_BotStr_R")
    sp.combine(side_l, [shelf_stretcher], CUT, True, "SlideDT_ShStr_L")
    sp.combine(side_r, [shelf_stretcher], CUT, True, "SlideDT_ShStr_R")
    sp.combine(side_l, [div_front_rail], CUT, True, "SlideDT_DivFR_L")
    sp.combine(side_r, [div_front_rail], CUT, True, "SlideDT_DivFR_R")

    # -- Dados: rear boards into Sides --
    sp.combine(side_l, [bot_board], CUT, True, "DadoBotBrd_L")
    sp.combine(side_r, [bot_board], CUT, True, "DadoBotBrd_R")
    sp.combine(side_l, [shelf_board], CUT, True, "DadoShBrd_L")
    sp.combine(side_r, [shelf_board], CUT, True, "DadoShBrd_R")

    # -- Dados: Divider rails + stiles into Sides --
    sp.combine(side_l, [div_back_rail], CUT, True, "DadoDivBR_L")
    sp.combine(side_r, [div_back_rail], CUT, True, "DadoDivBR_R")
    sp.combine(side_l, [div_left_stile], CUT, True, "DadoDivLS_L")
    sp.combine(side_r, [div_right_stile], CUT, True, "DadoDivRS_R")

    # -- Back panel rabbet into Sides --
    sp.combine(side_l, [back_body], CUT, True, "RabbetL")
    sp.combine(side_r, [back_body], CUT, True, "RabbetR")

    # -- Half-blind dovetails: SubTop to Sides --
    st_hbd_pl = sp.off_plane(case_c, case_c.xYConstructionPlane,
                              "sub_top_z", "ST_HBD_Pl")
    half_blind_dovetail.box(
        case_c, side_l, sub_top,
        None, case_x_mid,
        pin_thick_expr="board_thick",
        tail_thick_expr="board_thick",
        right=None, back=side_r,
        prefix="hbd_case", name="ST_HBD", ev=ev,
        fl_plane=st_hbd_pl,
        front_expr="0 in",
        joint_axis="y", thick_axis="x")


    # ════════════════════════════════════════════════════════════
    #  DETAILS — edge treatments
    # ════════════════════════════════════════════════════════════

    # -- Top board: gentle roundover on top edges --
    top_top = sp.find_face(top_body, "z", +1)
    edges_coll = adsk.core.ObjectCollection.create()
    for i in range(top_top.edges.count):
        edges_coll.add(top_top.edges.item(i))
    fil_inp = top_c.features.filletFeatures.createInput()
    fil_inp.addConstantRadiusEdgeSet(edges_coll, VI("0.125 in"), False)
    top_fillet = top_c.features.filletFeatures.add(fil_inp)
    top_fillet.name = "TopFillet"

    # ════════════════════════════════════════════════════════════
    #  EPILOGUE
    # ════════════════════════════════════════════════════════════
    for comp in [root, sides_c, case_c, top_c, back_c, drawer_c]:
        for i in range(comp.sketches.count):
            comp.sketches.item(i).isVisible = False
        for i in range(comp.constructionPlanes.count):
            comp.constructionPlanes.item(i).isLightBulbOn = False
        for i in range(comp.constructionAxes.count):
            comp.constructionAxes.item(i).isLightBulbOn = False

    for comp_name, comp in [("Sides", sides_c), ("Case", case_c),
                            ("Top", top_c), ("Back", back_c),
                            ("Drawers", drawer_c)]:
        names = [comp.bRepBodies.item(i).name
                 for i in range(comp.bRepBodies.count)]
        print(f"{comp_name}: {len(names)} bodies — {names}")

    # APPEARANCE SPEC
    # species: white_oak  |  knobs: mahogany
    sp.apply_appearance("white oak")
    sp.apply_appearance("mahogany", bodies=["Knob", "Knob (1)"])
