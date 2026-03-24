"""TV Console — dovetailed case, M&T frame, dovetailed drawers."""
import adsk.core, adsk.fusion, math
from helpers import sp
from woodworking.templates import domino
from woodworking.templates import dovetail
from woodworking.templates import dovetailed_drawer

CUT  = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
NEW  = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    Point3D = adsk.core.Point3D

    ctx = sp.DesignContext()

    # ── Shared Parameters ──────────────────────────────────────────
    shared = [
        # Envelope
        ("console_w",  "60 in",   "in", "Overall width"),
        ("console_d",  "18 in",   "in", "Overall depth"),
        ("case_h",     "12 in",   "in", "Case interior height"),
        ("leg_h",      "6 in",    "in", "Leg height below case"),
        ("frame_gap",  "0.25 in", "in", "Gap between frame top and case bottom"),
        # Case boards
        ("board_thick", "0.75 in", "in", "Case board thickness"),
        ("back_thick",  "0.375 in","in", "Back panel thickness"),
        # Frame
        ("leg_size",   "1.5 in",  "in", "Leg cross-section"),
        ("rail_w",     "2.5 in",  "in", "Rail width (height)"),
        ("rail_thick",  "0.75 in", "in", "Rail thickness"),
        # Cleats
        ("cleat_w",    "1.25 in", "in", "Cleat width"),
        ("cleat_thick", "2.5 in", "in", "Cleat thickness (height)"),
        ("tt_shoulder", "0.25 in","in", "Cleat tenon shoulder"),
        # Dividers
        ("n_sections",  "3",      "",   "Number of sections"),
        ("divider_thick","0.75 in","in", "Divider thickness"),
        # Drawers
        ("n_drawers",   "3",      "",   "Number of drawers"),
        ("drawer_gap",  "0.0625 in","in","Drawer clearance gap"),
        ("drawer_front_thick", "0.75 in","in","Drawer front thickness"),
        ("drawer_side_thick",  "0.5 in", "in","Drawer side thickness"),
        ("drawer_bottom_thick","0.25 in","in","Drawer bottom thickness"),
        ("bg_depth",    "0.25 in","in", "Bottom groove depth"),
        ("bg_up",       "0.25 in","in", "Bottom groove offset from floor"),
        # Doors
        ("door_thick",  "0.75 in","in", "Door panel thickness"),
        ("door_gap",    "0.0625 in","in","Door inset gap"),
        # Rabbet
        ("rabbet_d",    "0.375 in","in", "Back rabbet depth"),
        # M&T
        ("mt_tw",       "2 in",   "in", "Tenon width"),
        ("mt_tt",       "0.375 in","in","Tenon thickness"),
        ("mt_td",       "1 in",   "in", "Tenon depth"),
        # Dominos (cleat-to-case)
        ("dm_cl_short", "8 mm",   "in", "Domino short (cutter dia)"),
        ("dm_cl_long",  "40 mm",  "in", "Domino long dimension"),
        ("dm_cl_depth", "20 mm",  "in", "Domino depth per side"),
        ("dm_cl_count", "3",      "",   "Dominos per cleat"),
        # Dominos (divider-to-case)
        ("dm_dv_short", "6 mm",   "in", "Divider domino short"),
        ("dm_dv_long",  "30 mm",  "in", "Divider domino long"),
        ("dm_dv_depth", "12 mm",  "in", "Divider domino depth per side"),
        ("dm_dv_count", "3",      "",   "Dominos per divider edge"),
    ]
    for name, expr, unit, desc in shared:
        params.add(name, VI(expr), unit, desc)

    # ── Derived Parameters ─────────────────────────────────────────
    derived = [
        # Case Z base (above frame + gap)
        ("case_z",     "leg_h + frame_gap",            "in", "Case bottom Z"),
        # Case interior
        ("inner_w",    "console_w - 2 * board_thick",  "in", "Case interior width"),
        ("inner_d",    "console_d - back_thick",       "in", "Case interior depth"),
        # Section widths
        ("section_w",  "inner_w / n_sections",         "in", "Section width"),
        # Divider positions (from left inner face)
        ("div1_x",     "board_thick + section_w - divider_thick / 2", "in", "Divider 1 X"),
        ("div2_x",     "board_thick + 2 * section_w - divider_thick / 2","in","Divider 2 X"),
        # Drawer dims (center section between dividers)
        ("drawer_w",   "section_w - divider_thick - 2 * drawer_gap","in","Drawer width"),
        ("drawer_d",   "console_d - back_thick - 2 * drawer_gap", "in", "Drawer depth"),
        ("drawer_h",   "(case_h - (n_drawers + 1) * drawer_gap) / n_drawers","in","Drawer height"),
        ("drawer_pitch","drawer_h + drawer_gap", "in", "Drawer vertical pitch"),
        # Door dims
        ("door_w",     "section_w - divider_thick / 2 - 2 * door_gap","in","Door width"),
        ("door_h",     "case_h - 2 * door_gap",       "in", "Door height"),
        # Interlocking tenon notch
        ("notch_d",    "mt_td - leg_size / 2 + mt_tt / 2", "in", "Notch depth into tenon"),
        # Domino spacing (cleat-to-case)
        ("dm_cl_sp",   "(console_d - leg_size - rail_thick) / (dm_cl_count + 1)",
                                                       "in", "Domino spacing along cleat"),
        # Domino spacing (divider-to-case)
        ("dm_dv_sp",   "(console_d - back_thick) / (dm_dv_count + 1)",
                                                       "in", "Domino spacing along divider"),
        # Midplanes
        ("mid_x",      "console_w / 2",               "in", "X midplane"),
        ("mid_y",      "console_d / 2",                "in", "Y midplane"),
    ]
    for name, expr, unit, desc in derived:
        params.add(name, VI(expr), unit, desc)

    ev = ctx.ev

    # ── Dovetail parameters (via template) ─────────────────────────
    # Tails run along Y (depth), pin boards = Top/Bottom (thick in Z)
    dt_params = dovetail.define_params(params,
        prefix="dt",
        angle="8 deg",
        tail_w="1.5 in",
        tail_count="4",
        joint_h_expr="console_d",
        thick_expr="board_thick")

    # ── Midplanes ──────────────────────────────────────────────────
    xmid = sp.off_plane(root, root.yZConstructionPlane, "mid_x", "XMid")
    ymid = sp.off_plane(root, root.xZConstructionPlane, "mid_y", "YMid")

    # ── Case Component ─────────────────────────────────────────────
    case_occ = sp.make_comp(root, "Case")
    case_c = case_occ.component

    # Case midplanes (inside component)
    xmid_case = sp.off_plane(case_c, case_c.yZConstructionPlane,
        "mid_x", "XMid_Case")
    # Z midplane for Bottom↔Top dovetail mirror (XY plane at mid height)
    zmid_case = sp.off_plane(case_c, case_c.xYConstructionPlane,
        "case_z + board_thick + case_h / 2", "ZMid_Case")

    # ── Bottom board (pin board) — full width ──
    bot_pl = sp.off_plane(case_c, case_c.xYConstructionPlane,
        "case_z", "Bot_Pl")
    _, bot_pr = sp.sketch_rect_model(case_c, bot_pl,
        ("0 in", "0 in", "case_z"),
        {"x": "console_w", "y": "console_d"},
        "Bot_Sk", ev=ev)
    bot_ext = sp.ext_new(case_c, bot_pr, "board_thick", "BotBoard")
    bot_body = bot_ext.bodies.item(0)
    bot_body.name = "Bottom"

    # ── Top board (pin board) — full width ──
    top_pl = sp.off_plane(case_c, case_c.xYConstructionPlane,
        "case_z + board_thick + case_h", "Top_Pl")
    _, top_pr = sp.sketch_rect_model(case_c, top_pl,
        ("0 in", "0 in", "case_z + board_thick + case_h"),
        {"x": "console_w", "y": "console_d"},
        "Top_Sk", ev=ev)
    top_ext = sp.ext_new(case_c, top_pr, "board_thick", "TopBoard")
    top_body = top_ext.bodies.item(0)
    top_body.name = "Top"

    # ── Left end board (tail board) — interior height only ──
    # Inset along Z: starts at leg_h + board_thick, spans case_h
    # Tails will JOIN into this board, extending it into Top/Bottom zones
    left_pl = sp.off_plane(case_c, case_c.yZConstructionPlane, "0 in", "Left_Pl")
    _, left_pr = sp.sketch_rect_model(case_c, left_pl,
        ("0 in", "0 in", "case_z + board_thick"),
        {"y": "console_d", "z": "case_h"},
        "Left_Sk", ev=ev)
    left_ext = sp.ext_new(case_c, left_pr, "board_thick", "LeftBoard")
    left_body = left_ext.bodies.item(0)
    left_body.name = "Left"

    # Mirror Left → Right
    right_mir = sp.mirror_body(case_c, left_body, xmid_case, "RightMirror")
    right_body = right_mir.bodies.item(0)
    right_body.name = "Right"

    # ── Case Dovetails (4 corners) ─────────────────────────────────
    # joint_axis="y" (tails along depth Y)
    # thick_axis="z" (pin board Top/Bottom thickness in Z)
    # ext_axis="x"   (tail board Left/Right thickness in X)
    # fl_plane = YZ plane at X=0 (left end)
    # front = Bottom (pin board, outer face at Z=leg_h)
    # back = Top (pin board, outer face at Z=leg_h+board_thick+case_h)
    # x_mid = xmid_case (YZ plane at console_w/2, for Left→Right mirror)
    # y_mid = zmid_case (XY plane at mid-height, for Bottom→Top mirror)
    dt_result = dovetail.box(case_c,
        front=bot_body,
        left=left_body,
        x_mid=xmid_case,
        y_mid=zmid_case,
        thick_expr="board_thick",
        right=right_body,
        back=top_body,
        prefix="dt",
        name="DT",
        ev=ev,
        fl_plane=left_pl,
        front_expr="case_z",
        joint_axis="y",
        thick_axis="z",
    )

    # ── Back Panel ─────────────────────────────────────────────────
    # Thin panel sits in rabbet at back of case
    back_pl = sp.off_plane(case_c, case_c.xZConstructionPlane,
        "console_d - back_thick", "Back_Pl")
    _, back_pr = sp.sketch_rect_model(case_c, back_pl,
        ("board_thick", "console_d - back_thick", "case_z + board_thick"),
        {"x": "console_w - 2 * board_thick", "z": "case_h"},
        "Back_Sk", ev=ev)
    back_ext = sp.ext_new(case_c, back_pr, "back_thick", "BackPanel")
    back_body = back_ext.bodies.item(0)
    back_body.name = "Back"

    # Rabbet CUTs — back panel body CUTs into each case board
    # Use the back panel as tool body to cut matching grooves
    for bname, bbody in [("Bot", bot_body), ("Top", top_body),
                          ("Left", left_body), ("Right", right_body)]:
        sp.combine(case_c, bbody, back_body, CUT, True,
                   f"Rab_{bname}")

    # ── Dividers (2 vertical partitions) ───────────────────────────
    # Divider 1 at section boundary
    div1_pl = sp.off_plane(case_c, case_c.yZConstructionPlane,
        "div1_x", "Div1_Pl")
    _, div1_pr = sp.sketch_rect_model(case_c, div1_pl,
        ("div1_x", "0 in", "case_z + board_thick"),
        {"y": "console_d - back_thick", "z": "case_h"},
        "Div1_Sk", ev=ev)
    div1_ext = sp.ext_new(case_c, div1_pr, "divider_thick", "Div1Board")
    div1_body = div1_ext.bodies.item(0)
    div1_body.name = "Divider1"

    # Divider 2 at second section boundary
    div2_pl = sp.off_plane(case_c, case_c.yZConstructionPlane,
        "div2_x", "Div2_Pl")
    _, div2_pr = sp.sketch_rect_model(case_c, div2_pl,
        ("div2_x", "0 in", "case_z + board_thick"),
        {"y": "console_d - back_thick", "z": "case_h"},
        "Div2_Sk", ev=ev)
    div2_ext = sp.ext_new(case_c, div2_pr, "divider_thick", "Div2Board")
    div2_body = div2_ext.bodies.item(0)
    div2_body.name = "Divider2"

    # Dado CUTs — dividers CUT into Top and Bottom boards
    sp.combine(case_c, bot_body, [div1_body, div2_body], CUT, True,
               "Dado_Bot")
    sp.combine(case_c, top_body, [div1_body, div2_body], CUT, True,
               "Dado_Top")

    # ── Dominos: Divider-to-Case Top & Bottom ─────────────────────
    # Dominos at the divider edge / case board interface.
    # long_axis = "y" (parallel to divider grain/depth).
    # Build inside case_c (same component, no proxies needed).
    first_dv_dm_y = "dm_dv_sp"

    for div_body, div_cx, div_name in [
        (div1_body, "div1_x + divider_thick / 2", "DmDv1"),
        (div2_body, "div2_x + divider_thick / 2", "DmDv2"),
    ]:
        # Bottom interface (Z = case_z + board_thick)
        dm_bot_pl = sp.off_plane(case_c, case_c.xYConstructionPlane,
            "case_z + board_thick", f"{div_name}_BotPl")
        dm_bot_pl.isLightBulbOn = False
        domino.grid(case_c, dm_bot_pl,
            start=(div_cx, first_dv_dm_y, "case_z + board_thick"),
            step_axis="y", step_expr="dm_dv_sp", count_expr="dm_dv_count",
            long_axis="y",
            long_expr="dm_dv_long", short_expr="dm_dv_short",
            depth_expr="dm_dv_depth",
            body_a=div_body, body_b=bot_body,
            name=f"{div_name}_Bot", ev=ev)

        # Top interface (Z = case_z + board_thick + case_h)
        dm_top_pl = sp.off_plane(case_c, case_c.xYConstructionPlane,
            "case_z + board_thick + case_h", f"{div_name}_TopPl")
        dm_top_pl.isLightBulbOn = False
        domino.grid(case_c, dm_top_pl,
            start=(div_cx, first_dv_dm_y, "case_z + board_thick + case_h"),
            step_axis="y", step_expr="dm_dv_sp", count_expr="dm_dv_count",
            long_axis="y",
            long_expr="dm_dv_long", short_expr="dm_dv_short",
            depth_expr="dm_dv_depth",
            body_a=div_body, body_b=top_body,
            name=f"{div_name}_Top", ev=ev)

    # ── Frame Component ────────────────────────────────────────────
    frame_occ = sp.make_comp(root, "Frame")
    frame_c = frame_occ.component

    xmid_frame = sp.off_plane(frame_c, frame_c.yZConstructionPlane,
        "mid_x", "XMid_Frame")
    ymid_frame = sp.off_plane(frame_c, frame_c.xZConstructionPlane,
        "mid_y", "YMid_Frame")

    # ── Legs ───────────────────────────────────────────────────────
    # Front-left leg at origin corner
    _, leg_pr = sp.sketch_rect_model(frame_c, frame_c.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_size", "y": "leg_size"},
        "LegFL_Sk", ev=ev)
    leg_fl_ext = sp.ext_new(frame_c, leg_pr, "leg_h", "LegFL")
    leg_fl = leg_fl_ext.bodies.item(0)
    leg_fl.name = "Leg_FL"

    # Mirror FL → FR (across X mid)
    leg_fr_mir = sp.mirror_body(frame_c, leg_fl, xmid_frame, "LegFR_Mir")
    leg_fr = leg_fr_mir.bodies.item(0)
    leg_fr.name = "Leg_FR"

    # Mirror FL → BL (across Y mid)
    leg_bl_mir = sp.mirror_body(frame_c, leg_fl, ymid_frame, "LegBL_Mir")
    leg_bl = leg_bl_mir.bodies.item(0)
    leg_bl.name = "Leg_BL"

    # Mirror FR → BR (across Y mid)
    leg_br_mir = sp.mirror_body(frame_c, leg_fr, ymid_frame, "LegBR_Mir")
    leg_br = leg_br_mir.bodies.item(0)
    leg_br.name = "Leg_BR"

    # ── Front Rail (M&T into front legs) ───────────────────────────
    # Rail spans between front legs, with tenons extending into each leg
    # Position: X = leg_size (after left leg), Y centered on leg front face
    # Z = leg_h - rail_w (rail at top of legs)
    front_rail_pl = sp.off_plane(frame_c, frame_c.xZConstructionPlane,
        "leg_size / 2 - rail_thick / 2", "FRail_Pl")
    _, frail_pr = sp.sketch_rect_model(frame_c, front_rail_pl,
        ("leg_size - mt_td", "leg_size / 2 - rail_thick / 2",
         "leg_h - rail_w"),
        {"x": "console_w - 2 * leg_size + 2 * mt_td", "z": "rail_w"},
        "FRail_Sk", ev=ev)
    frail_ext = sp.ext_new(frame_c, frail_pr, "rail_thick", "FrontRail")
    frail_body = frail_ext.bodies.item(0)
    frail_body.name = "FrontRail"

    # Shoulder CUTs on front rail (create tenons at each end)
    # Draw tenon rectangle (mt_tw × mt_tt) centered on end face.
    # Face boundary + tenon rect = 2 profiles. CUT the larger (shoulder ring).
    HO = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    VO = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation

    _rx = ev("leg_size - mt_td")
    _ry = ev("leg_size / 2 - rail_thick / 2")
    _rz = ev("leg_h - rail_w")
    _rw = ev("rail_w")
    _rt = ev("rail_thick")
    _tw = ev("mt_tw")
    _tt = ev("mt_tt")
    _cy = _ry + _rt / 2   # face center Y
    _cz = _rz + _rw / 2   # face center Z

    # Left shoulder
    fr_lshoulder_face = sp.find_face(frail_body, "x", -1)
    sk_fls = frame_c.sketches.add(fr_lshoulder_face)
    sk_fls.name = "FRail_LSh_Sk"
    m = sk_fls.modelToSketchSpace
    p1 = m(Point3D.create(_rx, _cy - _tt/2, _cz - _tw/2))
    p2 = m(Point3D.create(_rx, _cy + _tt/2, _cz + _tw/2))
    rect_sh = sk_fls.sketchCurves.sketchLines.addTwoPointRectangle(
        Point3D.create(p1.x, p1.y, 0), Point3D.create(p2.x, p2.y, 0))
    sk_fls.geometricConstraints.addHorizontal(rect_sh[0])
    sk_fls.geometricConstraints.addHorizontal(rect_sh[2])
    sk_fls.geometricConstraints.addVertical(rect_sh[1])
    sk_fls.geometricConstraints.addVertical(rect_sh[3])
    ha, va = sp.probe_sketch_axes(sk_fls)
    dim = sk_fls.sketchDimensions
    dim.addDistanceDimension(
        rect_sh[0].startSketchPoint, rect_sh[0].endSketchPoint,
        HO, Point3D.create((p1.x+p2.x)/2, p1.y-0.5, 0)
    ).parameter.expression = "mt_tw" if ha == "z" else "mt_tt"
    dim.addDistanceDimension(
        rect_sh[1].startSketchPoint, rect_sh[1].endSketchPoint,
        VO, Point3D.create(p2.x+0.5, (p1.y+p2.y)/2, 0)
    ).parameter.expression = "mt_tt" if va == "y" else "mt_tw"
    # Largest profile = shoulder ring (face minus tenon)
    best_prof = None
    best_area = 0
    for pi in range(sk_fls.profiles.count):
        p = sk_fls.profiles.item(pi)
        a = p.areaProperties().area
        if a > best_area:
            best_area = a
            best_prof = p
    sp.ext_op(frame_c, best_prof, "mt_td", CUT, frail_body,
              "FRail_LSh", flip=True)

    # Right shoulder
    fr_rshoulder_face = sp.find_face(frail_body, "x", +1)
    sk_frs = frame_c.sketches.add(fr_rshoulder_face)
    sk_frs.name = "FRail_RSh_Sk"
    m2 = sk_frs.modelToSketchSpace
    _rx2 = ev("console_w - leg_size + mt_td")
    p3 = m2(Point3D.create(_rx2, _cy - _tt/2, _cz - _tw/2))
    p4 = m2(Point3D.create(_rx2, _cy + _tt/2, _cz + _tw/2))
    rect_sh2 = sk_frs.sketchCurves.sketchLines.addTwoPointRectangle(
        Point3D.create(p3.x, p3.y, 0), Point3D.create(p4.x, p4.y, 0))
    sk_frs.geometricConstraints.addHorizontal(rect_sh2[0])
    sk_frs.geometricConstraints.addHorizontal(rect_sh2[2])
    sk_frs.geometricConstraints.addVertical(rect_sh2[1])
    sk_frs.geometricConstraints.addVertical(rect_sh2[3])
    dim2 = sk_frs.sketchDimensions
    dim2.addDistanceDimension(
        rect_sh2[0].startSketchPoint, rect_sh2[0].endSketchPoint,
        HO, Point3D.create((p3.x+p4.x)/2, p3.y-0.5, 0)
    ).parameter.expression = "mt_tw" if ha == "z" else "mt_tt"
    dim2.addDistanceDimension(
        rect_sh2[1].startSketchPoint, rect_sh2[1].endSketchPoint,
        VO, Point3D.create(p4.x+0.5, (p3.y+p4.y)/2, 0)
    ).parameter.expression = "mt_tt" if va == "y" else "mt_tw"
    best_prof2 = None
    best_area2 = 0
    for pi in range(sk_frs.profiles.count):
        p = sk_frs.profiles.item(pi)
        a = p.areaProperties().area
        if a > best_area2:
            best_area2 = a
            best_prof2 = p
    sp.ext_op(frame_c, best_prof2, "mt_td", CUT, frail_body,
              "FRail_RSh", flip=True)

    # ── Front rail interlocking notches (middle half of each tenon) ──
    # Remove center mt_tw/2, keeping top + bottom mt_tw/4 each
    frnotch_pl = sp.off_plane(frame_c, frame_c.xZConstructionPlane,
        "leg_size / 2 - mt_tt / 2", "FRNotch_Pl")
    # Left tenon — center notch
    _, frn_lpr = sp.sketch_rect_model(frame_c, frnotch_pl,
        ("leg_size - mt_td",
         "leg_size / 2 - mt_tt / 2",
         "leg_h - rail_w / 2 - mt_tw / 4"),
        {"x": "notch_d", "z": "mt_tw / 2"},
        "FRail_LNotch_Sk", ev=ev)
    sp.ext_op(frame_c, frn_lpr, "mt_tt", CUT, frail_body, "FRail_LNotch")
    # Right tenon — center notch
    _, frn_rpr = sp.sketch_rect_model(frame_c, frnotch_pl,
        ("console_w - leg_size + mt_td - notch_d",
         "leg_size / 2 - mt_tt / 2",
         "leg_h - rail_w / 2 - mt_tw / 4"),
        {"x": "notch_d", "z": "mt_tw / 2"},
        "FRail_RNotch_Sk", ev=ev)
    sp.ext_op(frame_c, frn_rpr, "mt_tt", CUT, frail_body, "FRail_RNotch")

    # Mirror front rail → back rail (notches included)
    brail_mir = sp.mirror_body(frame_c, frail_body, ymid_frame, "BackRail_Mir")
    brail_body = brail_mir.bodies.item(0)
    brail_body.name = "BackRail"

    # ── Side Rails (M&T into side legs) ────────────────────────────
    # Left side rail: X centered on left leg, Y spans between legs
    side_rail_pl = sp.off_plane(frame_c, frame_c.yZConstructionPlane,
        "leg_size / 2 - rail_thick / 2", "SRail_Pl")
    _, srail_pr = sp.sketch_rect_model(frame_c, side_rail_pl,
        ("leg_size / 2 - rail_thick / 2", "leg_size - mt_td",
         "leg_h - rail_w"),
        {"y": "console_d - 2 * leg_size + 2 * mt_td", "z": "rail_w"},
        "SRailL_Sk", ev=ev)
    srail_ext = sp.ext_new(frame_c, srail_pr, "rail_thick", "SideRailL")
    srail_body = srail_ext.bodies.item(0)
    srail_body.name = "SideRailL"

    # Shoulder CUTs on side rail — tenon rect centered on face
    _sx = ev("leg_size / 2 - rail_thick / 2")
    _sy = ev("leg_size - mt_td")
    _sz = ev("leg_h - rail_w")
    _scx = _sx + _rt / 2   # face center X
    _scz = _sz + _rw / 2   # face center Z

    sr_front_face = sp.find_face(srail_body, "y", -1)
    sk_srf = frame_c.sketches.add(sr_front_face)
    sk_srf.name = "SRailL_FSh_Sk"
    ms = sk_srf.modelToSketchSpace
    ps1 = ms(Point3D.create(_scx - _tt/2, _sy, _scz - _tw/2))
    ps2 = ms(Point3D.create(_scx + _tt/2, _sy, _scz + _tw/2))
    rect_sr = sk_srf.sketchCurves.sketchLines.addTwoPointRectangle(
        Point3D.create(ps1.x, ps1.y, 0), Point3D.create(ps2.x, ps2.y, 0))
    sk_srf.geometricConstraints.addHorizontal(rect_sr[0])
    sk_srf.geometricConstraints.addHorizontal(rect_sr[2])
    sk_srf.geometricConstraints.addVertical(rect_sr[1])
    sk_srf.geometricConstraints.addVertical(rect_sr[3])
    has, vas = sp.probe_sketch_axes(sk_srf)
    dims = sk_srf.sketchDimensions
    dims.addDistanceDimension(
        rect_sr[0].startSketchPoint, rect_sr[0].endSketchPoint,
        HO, Point3D.create((ps1.x+ps2.x)/2, ps1.y-0.5, 0)
    ).parameter.expression = "mt_tt" if has == "x" else "mt_tw"
    dims.addDistanceDimension(
        rect_sr[1].startSketchPoint, rect_sr[1].endSketchPoint,
        VO, Point3D.create(ps2.x+0.5, (ps1.y+ps2.y)/2, 0)
    ).parameter.expression = "mt_tw" if vas == "z" else "mt_tt"
    best_sr = None
    best_sra = 0
    for pi in range(sk_srf.profiles.count):
        p = sk_srf.profiles.item(pi)
        a = p.areaProperties().area
        if a > best_sra:
            best_sra = a
            best_sr = p
    sp.ext_op(frame_c, best_sr, "mt_td", CUT, srail_body,
              "SRailL_FSh", flip=True)

    # Back shoulder
    sr_back_face = sp.find_face(srail_body, "y", +1)
    sk_srb = frame_c.sketches.add(sr_back_face)
    sk_srb.name = "SRailL_BSh_Sk"
    ms2 = sk_srb.modelToSketchSpace
    _sy2 = ev("console_d - leg_size + mt_td")
    ps3 = ms2(Point3D.create(_scx - _tt/2, _sy2, _scz - _tw/2))
    ps4 = ms2(Point3D.create(_scx + _tt/2, _sy2, _scz + _tw/2))
    rect_sr2 = sk_srb.sketchCurves.sketchLines.addTwoPointRectangle(
        Point3D.create(ps3.x, ps3.y, 0), Point3D.create(ps4.x, ps4.y, 0))
    sk_srb.geometricConstraints.addHorizontal(rect_sr2[0])
    sk_srb.geometricConstraints.addHorizontal(rect_sr2[2])
    sk_srb.geometricConstraints.addVertical(rect_sr2[1])
    sk_srb.geometricConstraints.addVertical(rect_sr2[3])
    dims2 = sk_srb.sketchDimensions
    dims2.addDistanceDimension(
        rect_sr2[0].startSketchPoint, rect_sr2[0].endSketchPoint,
        HO, Point3D.create((ps3.x+ps4.x)/2, ps3.y-0.5, 0)
    ).parameter.expression = "mt_tt" if has == "x" else "mt_tw"
    dims2.addDistanceDimension(
        rect_sr2[1].startSketchPoint, rect_sr2[1].endSketchPoint,
        VO, Point3D.create(ps4.x+0.5, (ps3.y+ps4.y)/2, 0)
    ).parameter.expression = "mt_tw" if vas == "z" else "mt_tt"
    best_sr2 = None
    best_sra2 = 0
    for pi in range(sk_srb.profiles.count):
        p = sk_srb.profiles.item(pi)
        a = p.areaProperties().area
        if a > best_sra2:
            best_sra2 = a
            best_sr2 = p
    sp.ext_op(frame_c, best_sr2, "mt_td", CUT, srail_body,
              "SRailL_BSh", flip=True)

    # ── Side rail interlocking notches (top + bottom of each tenon) ──
    srnotch_pl = sp.off_plane(frame_c, frame_c.yZConstructionPlane,
        "leg_size / 2 - mt_tt / 2", "SRNotch_Pl")
    # Front tenon — top notch
    _, srn_ft_pr = sp.sketch_rect_model(frame_c, srnotch_pl,
        ("leg_size / 2 - mt_tt / 2",
         "leg_size - mt_td",
         "leg_h - rail_w / 2 + mt_tw / 4"),
        {"y": "notch_d", "z": "mt_tw / 4"},
        "SRailL_FNotchT_Sk", ev=ev)
    sp.ext_op(frame_c, srn_ft_pr, "mt_tt", CUT, srail_body, "SRailL_FNotchT")
    # Front tenon — bottom notch
    _, srn_fb_pr = sp.sketch_rect_model(frame_c, srnotch_pl,
        ("leg_size / 2 - mt_tt / 2",
         "leg_size - mt_td",
         "leg_h - rail_w / 2 - mt_tw / 2"),
        {"y": "notch_d", "z": "mt_tw / 4"},
        "SRailL_FNotchB_Sk", ev=ev)
    sp.ext_op(frame_c, srn_fb_pr, "mt_tt", CUT, srail_body, "SRailL_FNotchB")
    # Back tenon — top notch
    _, srn_bt_pr = sp.sketch_rect_model(frame_c, srnotch_pl,
        ("leg_size / 2 - mt_tt / 2",
         "console_d - leg_size + mt_td - notch_d",
         "leg_h - rail_w / 2 + mt_tw / 4"),
        {"y": "notch_d", "z": "mt_tw / 4"},
        "SRailL_BNotchT_Sk", ev=ev)
    sp.ext_op(frame_c, srn_bt_pr, "mt_tt", CUT, srail_body, "SRailL_BNotchT")
    # Back tenon — bottom notch
    _, srn_bb_pr = sp.sketch_rect_model(frame_c, srnotch_pl,
        ("leg_size / 2 - mt_tt / 2",
         "console_d - leg_size + mt_td - notch_d",
         "leg_h - rail_w / 2 - mt_tw / 2"),
        {"y": "notch_d", "z": "mt_tw / 4"},
        "SRailL_BNotchB_Sk", ev=ev)
    sp.ext_op(frame_c, srn_bb_pr, "mt_tt", CUT, srail_body, "SRailL_BNotchB")

    # Mirror left side rail → right (notches included)
    srail_r_mir = sp.mirror_body(frame_c, srail_body, xmid_frame, "SideRailR_Mir")
    srail_r_body = srail_r_mir.bodies.item(0)
    srail_r_body.name = "SideRailR"

    # ── Cross-Component: Rails CUT legs (mortises) ─────────────────
    frail_proxy = frail_body.createForAssemblyContext(frame_occ)
    brail_proxy = brail_body.createForAssemblyContext(frame_occ)
    srail_l_proxy = srail_body.createForAssemblyContext(frame_occ)
    srail_r_proxy = srail_r_body.createForAssemblyContext(frame_occ)

    leg_fl_proxy = leg_fl.createForAssemblyContext(frame_occ)
    leg_fr_proxy = leg_fr.createForAssemblyContext(frame_occ)
    leg_bl_proxy = leg_bl.createForAssemblyContext(frame_occ)
    leg_br_proxy = leg_br.createForAssemblyContext(frame_occ)

    sp.combine(root, leg_fl_proxy,
               [frail_proxy, srail_l_proxy],
               CUT, True, "Mortise_FL")
    sp.combine(root, leg_fr_proxy,
               [frail_proxy, srail_r_proxy],
               CUT, True, "Mortise_FR")
    sp.combine(root, leg_bl_proxy,
               [brail_proxy, srail_l_proxy],
               CUT, True, "Mortise_BL")
    sp.combine(root, leg_br_proxy,
               [brail_proxy, srail_r_proxy],
               CUT, True, "Mortise_BR")

    # ── Drawers Component ──────────────────────────────────────────
    drawers_occ = sp.make_comp(root, "Drawers")
    drawers_c = drawers_occ.component

    # Define drawer params via template
    # x_offset: center section starts after Divider1 + gap
    # z_offset: above bottom board + gap
    dd_params = dovetailed_drawer.define_params(params, prefix="dd",
        drawer_w="drawer_w",
        drawer_d="drawer_d",
        drawer_h="drawer_h",
        front_thick="drawer_front_thick",
        side_thick="drawer_side_thick",
        bottom_thick="drawer_bottom_thick",
        bg_depth="bg_depth",
        bg_up="bg_up",
        dt_angle="8 deg",
        dt_tail_w="0.75 in",
        front_tail_count="2",
        back_tail_count="2",
        hbd_lap="0.25 in",
        x_offset="div1_x + divider_thick + drawer_gap",
        z_offset="case_z + board_thick + drawer_gap")

    # Build one drawer
    dd_result = dovetailed_drawer.build(drawers_c, prefix="dd", ev=ev)

    # Pattern for multiple drawers
    dd_pat = dovetailed_drawer.pattern(drawers_c,
        dd_result["all_bodies"],
        "n_drawers", "drawer_pitch", ev=ev)

    # ── Doors Component ────────────────────────────────────────────
    doors_occ = sp.make_comp(root, "Doors")
    doors_c = doors_occ.component

    # Left door — inset in left section opening
    # Left section: X from board_thick to div1_x
    _, ldoor_pr = sp.sketch_rect_model(doors_c, doors_c.xZConstructionPlane,
        ("board_thick + door_gap", "0 in",
         "case_z + board_thick + door_gap"),
        {"x": "door_w", "z": "door_h"},
        "LDoor_Sk", ev=ev)
    ldoor_ext = sp.ext_new(doors_c, ldoor_pr, "door_thick", "LeftDoor")
    ldoor_body = ldoor_ext.bodies.item(0)
    ldoor_body.name = "LeftDoor"

    # Right door — mirror of left across X midplane
    xmid_doors = sp.off_plane(doors_c, doors_c.yZConstructionPlane,
        "mid_x", "XMid_Doors")
    rdoor_mir = sp.mirror_body(doors_c, ldoor_body, xmid_doors, "RightDoor_Mir")
    rdoor_body = rdoor_mir.bodies.item(0)
    rdoor_body.name = "RightDoor"

    # ── Cleats Component (Rachel's desk connection) ─────────────
    # 4 cleats under the case bottom, bridging the gap to the frame
    # Each cleat has through-tenons through front/back rails
    # Cleat top face = case bottom; cleat extends down into rail zone
    cleats_occ = sp.make_comp(root, "Cleats")
    cleats_c = cleats_occ.component

    xmid_cleats = sp.off_plane(cleats_c, cleats_c.yZConstructionPlane,
        "mid_x", "XMid_Cleats")

    # Cleat Z: top at case_z (touching case bottom), extends down
    # cleat_thick must be > frame_gap for tenon overlap with rails
    cleat_z_expr = "case_z - cleat_thick"

    # Build 2 cleats (inner pair), mirror each across XMid for 4 total
    # Positions: 1/5 and 2/5 of console width
    cleat_bodies = []
    cleat_x_exprs = [
        ("console_w / 5 - cleat_w / 2", "Cleat1"),
        ("2 * console_w / 5 - cleat_w / 2", "Cleat2"),
    ]

    for cx_expr, cname in cleat_x_exprs:
        # Cleat body
        cpl = sp.off_plane(cleats_c, cleats_c.xYConstructionPlane,
            cleat_z_expr, f"{cname}_Pl")
        _, cpr = sp.sketch_rect_model(cleats_c, cpl,
            (cx_expr,
             "(leg_size + rail_thick) / 2",
             cleat_z_expr),
            {"x": "cleat_w",
             "y": "console_d - leg_size - rail_thick"},
            f"{cname}_Sk", ev=ev)
        c_ext = sp.ext_new(cleats_c, cpr, "cleat_thick", cname)
        c_body = c_ext.bodies.item(0)
        c_body.name = cname

        # Front tenon — blind into front rail, overlaps cleat for JOIN
        # Plane at rail center (leg_size/2), extrude +Y through inner half
        # of rail + tt_shoulder into cleat body
        tn_f_pl = sp.off_plane(cleats_c, cleats_c.xZConstructionPlane,
            "leg_size / 2", f"{cname}_TnF_Pl")
        _, tn_f_pr = sp.sketch_rect_model(cleats_c, tn_f_pl,
            (f"{cx_expr} + tt_shoulder",
             "leg_size / 2",
             "leg_h - rail_w + tt_shoulder"),
            {"x": "cleat_w - 2 * tt_shoulder",
             "z": "rail_w - 2 * tt_shoulder"},
            f"{cname}_TnF_Sk", ev=ev)
        tn_f_ext = sp.ext_new(cleats_c, tn_f_pr,
            "rail_thick / 2 + tt_shoulder", f"{cname}_TnF")
        tn_f_body = tn_f_ext.bodies.item(0)

        # Back tenon — blind into back rail, overlaps cleat for JOIN
        # Plane inside cleat near back rail inner face, extrude +Y into rail
        tn_b_pl = sp.off_plane(cleats_c, cleats_c.xZConstructionPlane,
            "console_d - (leg_size + rail_thick) / 2 - tt_shoulder",
            f"{cname}_TnB_Pl")
        _, tn_b_pr = sp.sketch_rect_model(cleats_c, tn_b_pl,
            (f"{cx_expr} + tt_shoulder",
             "console_d - (leg_size + rail_thick) / 2 - tt_shoulder",
             "leg_h - rail_w + tt_shoulder"),
            {"x": "cleat_w - 2 * tt_shoulder",
             "z": "rail_w - 2 * tt_shoulder"},
            f"{cname}_TnB_Sk", ev=ev)
        tn_b_ext = sp.ext_new(cleats_c, tn_b_pr,
            "rail_thick / 2 + tt_shoulder", f"{cname}_TnB")
        tn_b_body = tn_b_ext.bodies.item(0)

        # JOIN both tenons into cleat
        sp.combine(cleats_c, c_body, [tn_f_body, tn_b_body],
                   JOIN, False, f"{cname}_TnJoin")

        # Mirror across XMid
        c_mir = sp.mirror_body(cleats_c, c_body, xmid_cleats,
                               f"{cname}_Mir")
        c_mir_body = c_mir.bodies.item(0)
        c_mir_body.name = f"{cname}_R"

        cleat_bodies.append(c_body)
        cleat_bodies.append(c_mir_body)

    # ── Cross-Component: Cleats CUT rails + case bottom ──────────
    # Re-lookup rail bodies in frame component
    frail_ref = brail_ref = None
    for i in range(frame_c.bRepBodies.count):
        b = frame_c.bRepBodies.item(i)
        if b.name == "FrontRail":
            frail_ref = b
        elif b.name == "BackRail":
            brail_ref = b

    frail_px = frail_ref.createForAssemblyContext(frame_occ)
    brail_px = brail_ref.createForAssemblyContext(frame_occ)

    cleat_proxies = [b.createForAssemblyContext(cleats_occ)
                     for b in cleat_bodies]

    # Cleats CUT mortises in front/back rails
    sp.combine(root, frail_px, cleat_proxies,
               CUT, True, "CleatMort_Front")
    sp.combine(root, brail_px, cleat_proxies,
               CUT, True, "CleatMort_Back")

    # Cleats CUT into case bottom (attachment dados)
    bot_ref = None
    for i in range(case_c.bRepBodies.count):
        b = case_c.bRepBodies.item(i)
        if b.name == "Bottom":
            bot_ref = b
            break
    bot_px = bot_ref.createForAssemblyContext(case_occ)
    sp.combine(root, bot_px, cleat_proxies,
               CUT, True, "CleatDado_Bot")

    # ── Dominos: Cleat-to-Case Bottom ───────────────────────────────
    # Dominos at the cleat top / case bottom interface (Z = case_z).
    # long_axis = "y" (parallel to cleat grain/length).
    # Build in root with assembly proxies for cross-component CUT.
    dm_plane = sp.off_plane(root, root.xYConstructionPlane,
        "case_z", "DM_CL_Pl")

    # Cleat center X expressions (left-side then mirrored right-side)
    cleat_cx_exprs = [
        ("console_w / 5",         "DmCl1"),     # Cleat1
        ("4 * console_w / 5",     "DmCl1R"),    # Cleat1_R (mirror of Cleat1)
        ("2 * console_w / 5",     "DmCl2"),     # Cleat2
        ("3 * console_w / 5",     "DmCl2R"),    # Cleat2_R (mirror of Cleat2)
    ]

    # cleat_bodies list order: [Cleat1, Cleat1_R, Cleat2, Cleat2_R]
    first_dm_y = "(leg_size + rail_thick) / 2 + dm_cl_sp"

    for i, (cx_expr, dm_name) in enumerate(cleat_cx_exprs):
        cleat_proxy = cleat_bodies[i].createForAssemblyContext(cleats_occ)
        dm_voids = domino.grid(root, dm_plane,
            start=(cx_expr, first_dm_y, "case_z"),
            step_axis="y", step_expr="dm_cl_sp", count_expr="dm_cl_count",
            long_axis="y",
            long_expr="dm_cl_long", short_expr="dm_cl_short",
            depth_expr="dm_cl_depth",
            body_a=cleat_proxy, body_b=bot_px,
            name=dm_name, ev=ev)

    # ── Details: Leg Bottom Chamfers ───────────────────────────────
    # Small chamfer on bottom edges of each leg
    params.add("leg_ch", VI("0.125 in"), "in", "Leg bottom chamfer")

    for leg_name in ["Leg_FL", "Leg_FR", "Leg_BL", "Leg_BR"]:
        leg_ref = None
        for i in range(frame_c.bRepBodies.count):
            b = frame_c.bRepBodies.item(i)
            if b.name == leg_name:
                leg_ref = b
                break
        if leg_ref is None:
            continue
        # Find bottom face (min Z)
        bot_face = sp.find_face(leg_ref, "z", -1)
        if bot_face is None:
            continue
        # Collect bottom face edges
        edge_coll = adsk.core.ObjectCollection.create()
        seen = set()
        for ei in range(bot_face.edges.count):
            e = bot_face.edges.item(ei)
            if e.tempId not in seen:
                seen.add(e.tempId)
                edge_coll.add(e)
        if edge_coll.count == 0:
            continue
        ch_inp = frame_c.features.chamferFeatures.createInput2()
        ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
            edge_coll, VI("leg_ch"), True)
        ch_feat = frame_c.features.chamferFeatures.add(ch_inp)
        ch_feat.name = f"{leg_name}_Ch"

    # ── Door Hinges (door_flush, inset) ─────────────────────────────
    from helpers import hardware
    hardware.clear_step_cache()

    # Proxied bodies for cross-component hinge install
    ldoor_px = ldoor_body.createForAssemblyContext(doors_occ)
    rdoor_px = rdoor_body.createForAssemblyContext(doors_occ)

    left_ref = right_ref = None
    for i in range(case_c.bRepBodies.count):
        b = case_c.bRepBodies.item(i)
        if b.name == "Left":
            left_ref = b
        elif b.name == "Right":
            right_ref = b
    left_px = left_ref.createForAssemblyContext(case_occ)
    right_px = right_ref.createForAssemblyContext(case_occ)

    rec = hardware.recommend_hinge(lid_length_cm=ev("door_h"))
    hinge_id = rec["part_id"]
    print(f"Door hinges: {hinge_id} (door_h={ev('door_h'):.1f}cm)")

    # Left door — hinges at 1/4 and 3/4 of case height
    for z_expr, sfx in [("case_z + board_thick + case_h / 4", "Lo"),
                         ("case_z + board_thick + 3 * case_h / 4", "Hi")]:
        hardware.install_butt_hinge(
            part_id=hinge_id, comp=root,
            door_body=ldoor_px, case_body=left_px,
            pin_position=("board_thick", "0 in", z_expr),
            style="door_flush", gap=ev("door_gap"),
            ev=ev, name=f"LDoor_H_{sfx}")

    # Right door — hinges at same heights, X at right case side
    for z_expr, sfx in [("case_z + board_thick + case_h / 4", "Lo"),
                         ("case_z + board_thick + 3 * case_h / 4", "Hi")]:
        hardware.install_butt_hinge(
            part_id=hinge_id, comp=root,
            door_body=rdoor_px, case_body=right_px,
            pin_position=("console_w - board_thick", "0 in", z_expr),
            style="door_flush", gap=ev("door_gap"),
            ev=ev, name=f"RDoor_H_{sfx}")

    hardware.cleanup_step_templates()

    # ── Epilogue ───────────────────────────────────────────────────
    all_comps = [case_c, frame_c, drawers_c, doors_c, cleats_c]
    for comp in all_comps:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False
    for sk in root.sketches:
        sk.isVisible = False
    for cp in root.constructionPlanes:
        cp.isLightBulbOn = False

    # Print body counts per component
    for comp_name, c in [("Root", root), ("Case", case_c), ("Frame", frame_c),
                          ("Drawers", drawers_c), ("Doors", doors_c),
                          ("Cleats", cleats_c)]:
        names = [c.bRepBodies.item(i).name
                 for i in range(c.bRepBodies.count)]
        print(f"{comp_name}: {len(names)} bodies -> {names}")

    sp.apply_appearance("walnut")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
