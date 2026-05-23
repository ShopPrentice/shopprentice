import adsk.core, adsk.fusion, math
from helpers import sp

def run(context):
    ctx = sp.DesignContext()
    design = ctx.design
    root = ctx.root
    params = ctx.params
    ev = ctx.ev
    P = adsk.core.Point3D.create

    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    # ── Shared Parameters ──────────────────────────────────────────
    pa = params.add
    pa("bed_l",           adsk.core.ValueInput.createByString("75 in"),  "in", "Mattress length")
    pa("bed_w",           adsk.core.ValueInput.createByString("40 in"),  "in", "Mattress width")
    pa("post_size",       adsk.core.ValueInput.createByString("3 in"),   "in", "Post cross-section")
    pa("post_h",          adsk.core.ValueInput.createByString("78 in"),  "in", "Total post height")
    pa("rail_h",          adsk.core.ValueInput.createByString("8 in"),   "in", "Bed rail height")
    pa("rail_thick",      adsk.core.ValueInput.createByString("1.5 in"), "in", "Bed rail thickness")
    pa("loft_h",          adsk.core.ValueInput.createByString("58 in"),  "in", "Bottom of bed rails from floor")
    pa("guard_thick",     adsk.core.ValueInput.createByString("1 in"),   "in", "Guard rail board thickness")
    pa("guard_w",         adsk.core.ValueInput.createByString("4 in"),   "in", "Guard rail board width")
    pa("mattress_recess", adsk.core.ValueInput.createByString("1.5 in"), "in", "Slat top below rail top")
    pa("desk_h",          adsk.core.ValueInput.createByString("30 in"),  "in", "Desk surface top from floor")
    pa("desk_thick",      adsk.core.ValueInput.createByString("1 in"),   "in", "Desk top thickness")
    pa("desk_rail_h",     adsk.core.ValueInput.createByString("3 in"),   "in", "Desk support rail height")
    pa("desk_rail_thick", adsk.core.ValueInput.createByString("1 in"),   "in", "Desk rail thickness")
    pa("desk_depth",      adsk.core.ValueInput.createByString("25 in"),  "in", "Desk depth front to back")
    pa("desk_leg_size",   adsk.core.ValueInput.createByString("2 in"),   "in", "Desk front leg cross-section")
    pa("n_slats",         adsk.core.ValueInput.createByString("13"),     "",   "Number of mattress slats")
    pa("slat_w",          adsk.core.ValueInput.createByString("3 in"),   "in", "Slat width")
    pa("slat_thick",      adsk.core.ValueInput.createByString("0.75 in"),"in", "Slat thickness")
    pa("ledger_h",        adsk.core.ValueInput.createByString("1.5 in"), "in", "Ledger strip height")
    pa("ledger_thick",    adsk.core.ValueInput.createByString("0.75 in"),"in", "Ledger strip thickness")
    pa("ladder_w",        adsk.core.ValueInput.createByString("16 in"),  "in", "Ladder opening width")
    pa("ladder_side_w",   adsk.core.ValueInput.createByString("3 in"),   "in", "Ladder side board width")
    pa("ladder_side_thick",adsk.core.ValueInput.createByString("1.5 in"),"in", "Ladder side thickness")
    pa("rung_face",       adsk.core.ValueInput.createByString("1.5 in"), "in", "Rung face height")
    pa("rung_depth",      adsk.core.ValueInput.createByString("4 in"),   "in", "Rung stepping depth")
    pa("n_rungs",         adsk.core.ValueInput.createByString("4"),      "",   "Number of ladder rungs")
    pa("post_chamfer",    adsk.core.ValueInput.createByString("0.25 in"),"in", "Post top chamfer")

    # Derived parameters
    pa("outer_l",    adsk.core.ValueInput.createByString("bed_l + 2 * post_size"),   "in", "Overall length")
    pa("outer_w",    adsk.core.ValueInput.createByString("bed_w + 2 * post_size"),   "in", "Overall width")
    pa("slat_z",     adsk.core.ValueInput.createByString("loft_h + rail_h - mattress_recess - slat_thick"), "in", "Slat bottom Z")
    pa("slat_pitch", adsk.core.ValueInput.createByString("bed_l / (n_slats + 1)"),   "in", "Slat spacing")
    pa("guard_z",    adsk.core.ValueInput.createByString("post_h - guard_w - post_chamfer"), "in", "Guard rail bottom Z")
    pa("ledger_z",   adsk.core.ValueInput.createByString("slat_z - ledger_h"),      "in", "Ledger bottom Z")
    pa("ladder_top_z", adsk.core.ValueInput.createByString("loft_h + rail_h"),      "in", "Ladder top Z")
    pa("desk_rail_z",  adsk.core.ValueInput.createByString("desk_h - desk_thick - desk_rail_h"), "in", "Desk rail bottom Z")

    # Compute ladder lean from angle (trig not supported in Fusion params)
    LADDER_ANGLE_DEG = 12
    LADDER_CLOSER_IN = 2.0  # bring bottom 2" closer to bed
    angle_rad = math.radians(LADDER_ANGLE_DEG)
    top_z_cm = ev("ladder_top_z")
    lean_cm = top_z_cm * math.tan(angle_rad)
    lean_in = lean_cm / 2.54 - LADDER_CLOSER_IN
    pa("ladder_lean", adsk.core.ValueInput.createByString(f"{lean_in:.4f} in"), "in", "Ladder bottom offset")
    pa("rung_pitch",  adsk.core.ValueInput.createByString("ladder_top_z / (n_rungs + 1)"), "in", "Rung Z spacing")
    pa("rung_lean_pitch", adsk.core.ValueInput.createByString(
        "sqrt(ladder_lean * ladder_lean + ladder_top_z * ladder_top_z) / (n_rungs + 1)"), "in", "Rung pitch along ladder")

    # ── Midplanes ──────────────────────────────────────────────────
    xmid = sp.off_plane(root, root.yZConstructionPlane, "outer_l / 2", "XMid")
    ymid = sp.off_plane(root, root.xZConstructionPlane, "outer_w / 2", "YMid")

    # ── Posts Component ────────────────────────────────────────────
    post_occ = sp.make_comp(root, "Posts")
    post_c = post_occ.component

    sk_post, prof_post = sp.sketch_rect_model(
        post_c, post_c.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "post_size", "y": "post_size"},
        "Post_FL_Sk", ev=ev)
    ext_post = sp.ext_new(post_c, prof_post, "post_h", "Post_FL")
    post_fl = ext_post.bodies.item(0)
    post_fl.name = "Post_FL"

    m1 = sp.mirror_body(post_c, post_fl, ymid, "Post_FR_Mirror")
    post_fr = m1.bodies.item(0)
    post_fr.name = "Post_FR"

    m2 = sp.mirror_bodies(post_c, [post_fl, post_fr], xmid, "Posts_Back_Mirror")
    post_bl = m2.bodies.item(0)
    post_bl.name = "Post_BL"
    post_br = m2.bodies.item(1)
    post_br.name = "Post_BR"

    print(f"Posts: {post_c.bRepBodies.count} bodies")

    # ── Body-relative lookups: posts ───────────────────────────────
    _pfl = ctx.find_body("Post_FL")
    _pfl_bb = _pfl.boundingBox
    _pfr = ctx.find_body("Post_FR")
    _pfr_bb = _pfr.boundingBox
    _pbl = ctx.find_body("Post_BL")
    _pbl_bb = _pbl.boundingBox

    # ── BedRails Component ─────────────────────────────────────────
    rail_occ = sp.make_comp(root, "BedRails")
    rail_c = rail_occ.component

    rail_pl = sp.off_plane(rail_c, rail_c.xYConstructionPlane, "loft_h", "Rail_Pl")

    # Left side rail (Y=0 side) — centered on post in Y
    sk_sr, prof_sr = sp.sketch_rect_model(
        rail_c, rail_pl,
        ("post_size", "post_size / 2 - rail_thick / 2", "loft_h"),
        {"x": "bed_l", "y": "rail_thick"},
        "SideRail_L_Sk", ev=ev)
    ext_sr = sp.ext_new(rail_c, prof_sr, "rail_h", "SideRail_L")
    sr_l = ext_sr.bodies.item(0)
    sr_l.name = "SideRail_L"

    # Mirror across YMid → right side rail (Y=outer_w side)
    m_sr = sp.mirror_body(rail_c, sr_l, ymid, "SideRail_R_Mirror")
    sr_r = m_sr.bodies.item(0)
    sr_r.name = "SideRail_R"

    # Head end rail — centered on head post in X, spans between posts in Y
    sk_er, prof_er = sp.sketch_rect_model(
        rail_c, rail_pl,
        ("outer_l - post_size / 2 - rail_thick / 2", "post_size", "loft_h"),
        {"x": "rail_thick", "y": "outer_w - 2 * post_size"},
        "EndRail_Head_Sk", ev=ev)
    ext_er = sp.ext_new(rail_c, prof_er, "rail_h", "EndRail_Head")
    er_head = ext_er.bodies.item(0)
    er_head.name = "EndRail_Head"

    # Mirror across XMid → foot end rail
    m_er = sp.mirror_body(rail_c, er_head, xmid, "EndRail_Foot_Mirror")
    er_foot = m_er.bodies.item(0)
    er_foot.name = "EndRail_Foot"

    print(f"BedRails: {rail_c.bRepBodies.count} bodies")

    # ── Body-relative lookups: rails ───────────────────────────────
    _srl = ctx.find_body("SideRail_L")
    _srl_bb = _srl.boundingBox
    _srr = ctx.find_body("SideRail_R")
    _srr_bb = _srr.boundingBox

    # ── GuardRails Component ───────────────────────────────────────
    # Layout: Right side (full), Head (full), Foot (full), Front/Left (partial — opening for ladder)
    guard_occ = sp.make_comp(root, "GuardRails")
    guard_c = guard_occ.component

    guard_pl = sp.off_plane(guard_c, guard_c.xYConstructionPlane, "guard_z", "Guard_Pl")

    # Right guard rail (Y=outer_w side) — full length, centered on post in Y
    sk_gr, prof_gr = sp.sketch_rect_model(
        guard_c, guard_pl,
        ("post_size", "outer_w - post_size / 2 - guard_thick / 2", "guard_z"),
        {"x": "bed_l", "y": "guard_thick"},
        "GuardRail_R_Sk", ev=ev)
    ext_gr = sp.ext_new(guard_c, prof_gr, "guard_w", "GuardRail_R")
    gr_r = ext_gr.bodies.item(0)
    gr_r.name = "GuardRail_R"

    # Head guard rail — centered on head posts in X, spans between posts in Y
    sk_gh, prof_gh = sp.sketch_rect_model(
        guard_c, guard_pl,
        ("outer_l - post_size / 2 - guard_thick / 2", "post_size", "guard_z"),
        {"x": "guard_thick", "y": "outer_w - 2 * post_size"},
        "GuardRail_Head_Sk", ev=ev)
    ext_gh = sp.ext_new(guard_c, prof_gh, "guard_w", "GuardRail_Head")
    gr_head = ext_gh.bodies.item(0)
    gr_head.name = "GuardRail_Head"

    # Foot guard rail — centered on foot posts in X, spans between posts in Y
    sk_gf, prof_gf = sp.sketch_rect_model(
        guard_c, guard_pl,
        ("post_size / 2 - guard_thick / 2", "post_size", "guard_z"),
        {"x": "guard_thick", "y": "outer_w - 2 * post_size"},
        "GuardRail_Foot_Sk", ev=ev)
    ext_gf = sp.ext_new(guard_c, prof_gf, "guard_w", "GuardRail_Foot")
    gr_foot = ext_gf.bodies.item(0)
    gr_foot.name = "GuardRail_Foot"

    # Front guard rail (partial, Y=0 side) — from ladder right side to head post
    # FIX 5: Ladder is at foot end: left side X = post_size
    # Right side outer edge = post_size + 2 * ladder_side_thick + ladder_w
    # Guard starts at right edge of ladder and goes to head post
    pa("fence_front_x", adsk.core.ValueInput.createByString(
        "post_size + 2 * ladder_side_thick + ladder_w"), "in", "Front fence start X")
    pa("fence_front_len", adsk.core.ValueInput.createByString(
        "outer_l - post_size - fence_front_x"), "in", "Front fence length")

    sk_gfr, prof_gfr = sp.sketch_rect_model(
        guard_c, guard_pl,
        ("fence_front_x", "post_size / 2 - guard_thick / 2", "guard_z"),
        {"x": "fence_front_len", "y": "guard_thick"},
        "GuardRail_Front_Sk", ev=ev)
    ext_gfr = sp.ext_new(guard_c, prof_gfr, "guard_w", "GuardRail_Front")
    gr_front = ext_gfr.bodies.item(0)
    gr_front.name = "GuardRail_Front"

    # Body-relative lookup: guard rail front
    _grf = ctx.find_body("GuardRail_Front")
    _grf_bb = _grf.boundingBox

    # Fence support post — vertical piece connecting front fence end to bed rail below
    pa("fence_support_z", adsk.core.ValueInput.createByString("loft_h + rail_h"), "in", "Support post bottom Z")
    pa("fence_support_h", adsk.core.ValueInput.createByString("guard_z - loft_h - rail_h"), "in", "Support post height")

    fsp_pl = sp.off_plane(guard_c, guard_c.xYConstructionPlane, "fence_support_z", "FenceSupport_Pl")
    sk_fsp2, prof_fsp2 = sp.sketch_rect_model(
        guard_c, fsp_pl,
        ("fence_front_x", "post_size / 2 - guard_thick / 2", "fence_support_z"),
        {"x": "post_size", "y": "guard_thick"},
        "FenceSupport_Sk", ev=ev)
    ext_fsp = sp.ext_new(guard_c, prof_fsp2, "fence_support_h", "FenceSupport")
    fsp_body = ext_fsp.bodies.item(0)
    fsp_body.name = "FenceSupport"

    print(f"GuardRails: {guard_c.bRepBodies.count} bodies")

    # ── Ledgers Component ──────────────────────────────────────────
    ledger_occ = sp.make_comp(root, "Ledgers")
    ledger_c = ledger_occ.component

    ledger_pl = sp.off_plane(ledger_c, ledger_c.xYConstructionPlane, "ledger_z", "Ledger_Pl")

    # Left ledger — on inside face of left side rail
    sk_ll, prof_ll = sp.sketch_rect_model(
        ledger_c, ledger_pl,
        ("post_size + rail_thick", "post_size / 2 + rail_thick / 2", "ledger_z"),
        {"x": "bed_l - 2 * rail_thick", "y": "ledger_thick"},
        "Ledger_L_Sk", ev=ev)
    ext_ll = sp.ext_new(ledger_c, prof_ll, "ledger_h", "Ledger_L")
    led_l = ext_ll.bodies.item(0)
    led_l.name = "Ledger_L"

    m_ll = sp.mirror_body(ledger_c, led_l, ymid, "Ledger_R_Mirror")
    led_r = m_ll.bodies.item(0)
    led_r.name = "Ledger_R"

    print(f"Ledgers: {ledger_c.bRepBodies.count} bodies")

    # ── Body-relative lookup: ledger ───────────────────────────────
    _ll = ctx.find_body("Ledger_L")
    _ll_bb = _ll.boundingBox

    # ── Slats Component ────────────────────────────────────────────
    slat_occ = sp.make_comp(root, "Slats")
    slat_c = slat_occ.component

    slat_pl = sp.off_plane(slat_c, slat_c.xYConstructionPlane, "slat_z", "Slat_Pl")

    sk_sl, prof_sl = sp.sketch_rect_model(
        slat_c, slat_pl,
        ("post_size + slat_pitch - slat_w / 2", "post_size / 2 + rail_thick / 2", "slat_z"),
        {"x": "slat_w", "y": "outer_w - post_size - rail_thick"},
        "Slat_Sk", ev=ev)
    ext_sl = sp.ext_new(slat_c, prof_sl, "slat_thick", "Slat")
    slat_body = ext_sl.bodies.item(0)
    slat_body.name = "Slat"

    sp.body_pattern(slat_c, slat_body, root.xConstructionAxis,
                    "n_slats", "slat_pitch", "Slat_Pat")

    print(f"Slats: {slat_c.bRepBodies.count} bodies")

    # ── Desk Component ─────────────────────────────────────────────
    # Desk is 25" deep, back against back (Y=outer_w) posts, front has legs.
    # Aprons connect to legs from the side. Desk top sits over back apron.
    desk_occ = sp.make_comp(root, "Desk")
    desk_c = desk_occ.component

    pa("desk_front_y", adsk.core.ValueInput.createByString(
        "outer_w - post_size - desk_depth"), "in", "Desk front rail Y")

    # Front desk legs (two) — full height to desk top underside
    desk_leg_pl = desk_c.xYConstructionPlane  # at Z=0
    sk_dll, prof_dll = sp.sketch_rect_model(
        desk_c, desk_leg_pl,
        ("post_size", "desk_front_y", "0 in"),
        {"x": "desk_leg_size", "y": "desk_leg_size"},
        "DeskLeg_L_Sk", ev=ev)
    dl_l = sp.ext_new(desk_c, prof_dll, "desk_h - desk_thick", "DeskLeg_L").bodies.item(0)
    dl_l.name = "DeskLeg_L"

    sk_dlr, prof_dlr = sp.sketch_rect_model(
        desk_c, desk_leg_pl,
        ("outer_l - post_size - desk_leg_size", "desk_front_y", "0 in"),
        {"x": "desk_leg_size", "y": "desk_leg_size"},
        "DeskLeg_R_Sk", ev=ev)
    dl_r = sp.ext_new(desk_c, prof_dlr, "desk_h - desk_thick", "DeskLeg_R").bodies.item(0)
    dl_r.name = "DeskLeg_R"

    # Body-relative lookup: desk legs
    _dll = ctx.find_body("DeskLeg_L")
    _dll_bb = _dll.boundingBox

    # Front desk apron — between legs, centered on leg in Y
    desk_rail_pl = sp.off_plane(desk_c, desk_c.xYConstructionPlane, "desk_rail_z", "DeskRail_Pl")
    sk_drf, prof_drf = sp.sketch_rect_model(
        desk_c, desk_rail_pl,
        ("post_size + desk_leg_size", "desk_front_y + desk_leg_size / 2 - desk_rail_thick / 2", "desk_rail_z"),
        {"x": "bed_l - 2 * desk_leg_size", "y": "desk_rail_thick"},
        "DeskRail_Front_Sk", ev=ev)
    dr_front = sp.ext_new(desk_c, prof_drf, "desk_rail_h", "DeskRail_Front").bodies.item(0)
    dr_front.name = "DeskRail_Front"

    # Back desk apron — between back posts, centered on post in Y
    sk_drb, prof_drb = sp.sketch_rect_model(
        desk_c, desk_rail_pl,
        ("post_size", "outer_w - post_size / 2 - desk_rail_thick / 2", "desk_rail_z"),
        {"x": "bed_l", "y": "desk_rail_thick"},
        "DeskRail_Back_Sk", ev=ev)
    dr_back = sp.ext_new(desk_c, prof_drb, "desk_rail_h", "DeskRail_Back").bodies.item(0)
    dr_back.name = "DeskRail_Back"

    # Body-relative lookup: desk rail
    _drf = ctx.find_body("DeskRail_Front")
    _drf_bb = _drf.boundingBox

    # Desk top — spans from front rail to over back apron (supported on back)
    desk_top_pl = sp.off_plane(desk_c, desk_c.xYConstructionPlane, "desk_h - desk_thick", "DeskTop_Pl")
    sk_dt, prof_dt = sp.sketch_rect_model(
        desk_c, desk_top_pl,
        ("post_size", "desk_front_y", "desk_h - desk_thick"),
        {"x": "bed_l", "y": "desk_depth + desk_rail_thick"},
        "DeskTop_Sk", ev=ev)
    sp.ext_new(desk_c, prof_dt, "desk_thick", "DeskTop").bodies.item(0).name = "DeskTop"

    print(f"Desk: {desk_c.bRepBodies.count} bodies")

    # ── Ladder Component ───────────────────────────────────────────
    # Angled ladder on front side (Y=0), at FOOT END (X near post_size)
    # Ladder leans: top touches front rail at Y=0, bottom at Y=-ladder_lean
    ladder_occ = sp.make_comp(root, "Ladder")
    ladder_c = ladder_occ.component

    # Compute geometry for angled ladder sides (parallelogram + hook tab)
    top_z_val = ev("ladder_top_z")    # cm
    lean_val = ev("ladder_lean")      # cm
    side_w_val = ev("ladder_side_w")  # cm
    side_thick_val = ev("ladder_side_thick")  # cm
    ladder_w_val = ev("ladder_w")     # cm
    post_size_val = ev("post_size")   # cm
    rung_depth_val = ev("rung_depth") # cm
    rung_face_val = ev("rung_face")   # cm
    n_rungs_val = int(ev("n_rungs"))
    rung_pitch_val = ev("rung_pitch") # cm
    # FIX 4: Ladder at foot end, not centered
    left_side_x = post_size_val
    right_side_x = post_size_val + side_thick_val + ladder_w_val

    # Hook tab: ladder side extends back at top to wrap around side rail.
    # Derive hook geometry from the side rail body's cross-section —
    # the ladder connects to the frame, so reference its actual geometry.
    sr_l_bb = sr_l.boundingBox
    rail_inner_y = sr_l_bb.maxPoint.y    # side rail inner face Y
    rail_bot_z   = sr_l_bb.minPoint.z    # side rail bottom Z
    rail_top_z   = sr_l_bb.maxPoint.z    # side rail top Z
    print(f"Rail cross-section: Y=[{sr_l_bb.minPoint.y:.2f}, {rail_inner_y:.2f}], "
          f"Z=[{rail_bot_z:.2f}, {rail_top_z:.2f}]")

    # Back edge of parallelogram at rail bottom Z (from lean geometry)
    back_y_at_rail_bot = -lean_val * (1.0 - rail_bot_z / rail_top_z)

    # 6-vertex polygon: parallelogram below rail + tab wrapping the rail
    corners_hook = [
        (0.0, -lean_val - side_w_val, 0.0),            # 0: front-bottom
        (0.0, -lean_val, 0.0),                           # 1: back-bottom
        (0.0, back_y_at_rail_bot, rail_bot_z),            # 2: back edge at rail bottom
        (0.0, rail_inner_y, rail_bot_z),                  # 3: step out to rail inner face
        (0.0, rail_inner_y, rail_top_z),                  # 4: tab top at rail top
        (0.0, -side_w_val, rail_top_z),                   # 5: front-top
    ]

    # Left ladder side — YZ plane sketch with hook tab
    left_plane = sp.off_plane(ladder_c, root.yZConstructionPlane,
                              f"{left_side_x / 2.54:.6f} in", "Ladder_L_Pl")
    sk_lad_l = ladder_c.sketches.add(left_plane)
    sk_lad_l.name = "LadderSide_L_Sk"
    m2s_l = sk_lad_l.modelToSketchSpace
    lines = sk_lad_l.sketchCurves.sketchLines
    pts_l = []
    for (_, y, z) in corners_hook:
        p_model = P(left_side_x, y, z)
        p_sk = m2s_l(p_model)
        pts_l.append(P(p_sk.x, p_sk.y, 0))
    for i in range(6):
        lines.addByTwoPoints(pts_l[i], pts_l[(i+1) % 6])
    prof_lad_l = sk_lad_l.profiles.item(0)

    # Extrude in +X for ladder_side_thick
    ext_lad_l = sp.ext_new(ladder_c, prof_lad_l, "ladder_side_thick", "LadderSide_L")
    ls_l = ext_lad_l.bodies.item(0)
    ls_l.name = "LadderSide_L"

    # Right ladder side — same polygon, at right X position
    right_plane = sp.off_plane(ladder_c, root.yZConstructionPlane,
                               f"{right_side_x / 2.54:.6f} in", "Ladder_R_Pl")
    sk_lad_r = ladder_c.sketches.add(right_plane)
    sk_lad_r.name = "LadderSide_R_Sk"
    m2s_r = sk_lad_r.modelToSketchSpace
    lines_r = sk_lad_r.sketchCurves.sketchLines
    pts_r = []
    for (_, y, z) in corners_hook:
        p_model = P(right_side_x, y, z)
        p_sk = m2s_r(p_model)
        pts_r.append(P(p_sk.x, p_sk.y, 0))
    for i in range(6):
        lines_r.addByTwoPoints(pts_r[i], pts_r[(i+1) % 6])
    prof_lad_r = sk_lad_r.profiles.item(0)

    ext_lad_r = sp.ext_new(ladder_c, prof_lad_r, "ladder_side_thick", "LadderSide_R")
    ls_r = ext_lad_r.bodies.item(0)
    ls_r.name = "LadderSide_R"

    # Body-relative lookup: ladder sides
    _lsl = ctx.find_body("LadderSide_L")
    _lsl_bb = _lsl.boundingBox

    # Rungs: build first rung on ladder side inner face (YZ plane),
    # then pattern along the ladder lean axis for the rest.
    rung_plane = sp.off_plane(ladder_c, root.yZConstructionPlane,
                              "post_size + ladder_side_thick", "Rung_Pl")

    inner_x_val = post_size_val + side_thick_val  # cm — inner face X

    # --- First rung (i=1) ---
    frac_total = n_rungs_val + 1
    rung1_z_val = top_z_val * 1 / frac_total
    rung1_y_val = -lean_val * (frac_total - 1) / frac_total - rung_depth_val

    sk = ladder_c.sketches.add(rung_plane)
    sk.name = "Rung1_Sk"
    m2s = sk.modelToSketchSpace

    p0_model = P(inner_x_val, rung1_y_val, rung1_z_val)
    p1_model = P(inner_x_val, rung1_y_val + rung_depth_val, rung1_z_val + rung_face_val)
    p0_sk = m2s(p0_model)
    p1_sk = m2s(p1_model)

    rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(
        P(p0_sk.x, p0_sk.y, 0), P(p1_sk.x, p1_sk.y, 0))

    geo = sk.geometricConstraints
    geo.addHorizontal(rect.item(0))
    geo.addHorizontal(rect.item(2))
    geo.addVertical(rect.item(1))
    geo.addVertical(rect.item(3))

    dims = sk.sketchDimensions
    # On a YZ plane: sketch horizontal = model Z, sketch vertical = model Y
    d_w = dims.addDistanceDimension(
        rect.item(0).startSketchPoint, rect.item(0).endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P((p0_sk.x + p1_sk.x) / 2, p0_sk.y - 1, 0))
    d_w.parameter.expression = "rung_face"
    d_h = dims.addDistanceDimension(
        rect.item(1).startSketchPoint, rect.item(1).endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(p1_sk.x + 1, (p0_sk.y + p1_sk.y) / 2, 0))
    d_h.parameter.expression = "rung_depth"

    prof = sk.profiles.item(0)
    rung1_ext = sp.ext_new(ladder_c, prof, "ladder_w", "Rung1")
    rung1_body = rung1_ext.bodies.item(0)
    rung1_body.name = "Rung_1"

    # --- Construction axis along ladder lean direction ---
    # Use front-inner edge of left ladder side (full height, same lean angle)
    lean_edge = None
    for ei in range(ls_l.edges.count):
        e = ls_l.edges.item(ei)
        if not e.geometry.curveType == adsk.core.Curve3DTypes.Line3DCurveType:
            continue
        sv = e.startVertex.geometry
        ev3 = e.endVertex.geometry
        # Both endpoints should have X ≈ inner_x_val (inner face)
        if abs(sv.x - inner_x_val) > 0.01 or abs(ev3.x - inner_x_val) > 0.01:
            continue
        # One endpoint at Z≈0, other at Z≈top_z
        z_lo = min(sv.z, ev3.z)
        z_hi = max(sv.z, ev3.z)
        if abs(z_lo) < 0.1 and abs(z_hi - top_z_val) < 0.1:
            lean_edge = e
            break
    axes_coll = ladder_c.constructionAxes
    axis_input = axes_coll.createInput()
    axis_input.setByEdge(lean_edge)
    ladder_axis = axes_coll.add(axis_input)
    ladder_axis.name = "LadderLean_Axis"

    # --- Pattern rungs along the lean axis ---
    # Validate axis direction: BRep edge direction is arbitrary, so check
    # mathematically. Pattern must go from rung 1 (lowest) toward higher
    # rungs — i.e., the axis Z component must be positive (upward).
    axis_dir = ladder_axis.geometry.direction
    rung_spacing_expr = "rung_lean_pitch" if axis_dir.z > 0 else "-rung_lean_pitch"
    print(f"Ladder axis direction: Z={axis_dir.z:.4f} → spacing={rung_spacing_expr}")

    rung_pat = sp.feat_pattern(ladder_c, rung1_ext, ladder_axis,
                               "n_rungs", rung_spacing_expr, "RungPat")

    rung_bodies = [rung1_body]
    for j in range(rung_pat.bodies.count):
        b = rung_pat.bodies.item(j)
        b.name = f"Rung_{j + 2}"
        rung_bodies.append(b)

    print(f"Ladder: {ladder_c.bRepBodies.count} bodies")

    # ── Cross-Component Joinery ────────────────────────────────────
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    VI = adsk.core.ValueInput.createByString

    # Domino parameters — per-joint sizing
    pa("dm_rail_t", VI("8 mm"), "in", "Bed rail domino thickness")
    pa("dm_rail_h", VI("40 mm"), "in", "Bed rail domino height")
    pa("dm_rail_d", VI("20 mm"), "in", "Bed rail domino depth per side")
    pa("dm_guard_t", VI("6 mm"), "in", "Guard rail domino thickness")
    pa("dm_guard_h", VI("30 mm"), "in", "Guard rail domino height")
    pa("dm_guard_d", VI("12 mm"), "in", "Guard rail domino depth per side")
    pa("dm_desk_t", VI("6 mm"), "in", "Desk rail domino thickness")
    pa("dm_desk_h", VI("30 mm"), "in", "Desk rail domino height")
    pa("dm_desk_d", VI("12 mm"), "in", "Desk rail domino depth per side")
    pa("dm_led_t", VI("5 mm"), "in", "Ledger domino thickness")
    pa("dm_led_h", VI("30 mm"), "in", "Ledger domino height")
    pa("dm_led_d", VI("10 mm"), "in", "Ledger domino depth per side")
    pa("n_led_dm", VI("4"), "", "Dominos per ledger")
    pa("dm_led_sp", VI("(bed_l - 2 * rail_thick) / (n_led_dm + 1)"), "in", "Ledger domino spacing")
    pa("dm_rung_t", VI("6 mm"), "in", "Rung domino thickness")
    pa("dm_rung_h", VI("20 mm"), "in", "Rung domino height")
    pa("dm_rung_d", VI("12 mm"), "in", "Rung domino depth per side")

    # Interface planes (where rails meet posts)
    iface_foot = sp.off_plane(root, root.yZConstructionPlane, "post_size", "Iface_Foot")
    iface_head = sp.off_plane(root, root.yZConstructionPlane, "outer_l - post_size", "Iface_Head")
    # XZ interface planes (Y-direction: guard ends → posts, desk back → posts)
    iface_post_yl = sp.off_plane(root, root.xZConstructionPlane, "post_size", "Iface_PostY_L")
    iface_post_yr = sp.off_plane(root, root.xZConstructionPlane, "outer_w - post_size", "Iface_PostY_R")
    # XZ interface plane for ladder hook → side rail front face
    iface_rail_front = sp.off_plane(root, root.xZConstructionPlane,
                                    "post_size / 2 - rail_thick / 2", "Iface_RailFront")

    # ── Ladder Hook CUTs ──────────────────────────────────────────────
    # CUT side rail shape from each ladder side to create hook notch
    ls_l_hk = ls_l.createForAssemblyContext(ladder_occ)
    sr_l_hk = sr_l.createForAssemblyContext(rail_occ)
    sp.combine(ls_l_hk, [sr_l_hk], CUT, True, "LadHook_CutL")
    ls_r_hk = ls_r.createForAssemblyContext(ladder_occ)
    sr_l_hk2 = sr_l.createForAssemblyContext(rail_occ)
    sp.combine(ls_r_hk, [sr_l_hk2], CUT, True, "LadHook_CutR")
    print("Ladder: hook CUTs applied to both sides")

    # Helper: create domino void INSIDE body_a's component, CUT both pieces
    def domino_joint(plane, center, long_axis, h_e, t_e, d_e, name, body_a, occ_a, body_b, occ_b):
        comp_a = occ_a.component
        sk, prof = sp.sketch_slot_model(comp_a, plane, center, long_axis, h_e, t_e, name=name+"_Sk", ev=ev)
        ext = sp.ext_new_sym(comp_a, prof, d_e, name)
        void = ext.bodies.item(0)
        void.name = name
        # Detect interface normal from plane geometry
        pn = plane.geometry.normal
        normal_axis = 'x' if abs(pn.x) > 0.9 else ('y' if abs(pn.y) > 0.9 else 'z')
        sp.check_domino_exposure(void, body_a, body_b, normal_axis)
        # CUT primary piece (same component — no proxy needed)
        sp.combine(body_a, [void], CUT, True, name+"_CutA")
        # CUT secondary piece (cross-component via assembly proxies)
        void_proxy = void.createForAssemblyContext(occ_a)
        proxy_b = body_b.createForAssemblyContext(occ_b)
        sp.combine(proxy_b, [void_proxy], CUT, True, name+"_CutB")
        return void

    # ── Bed Rail → Post Dominos (2 per end, 8 joints) ─────────────
    rail_z1 = "loft_h + rail_h / 3"
    rail_z2 = "loft_h + 2 * rail_h / 3"
    rail_y_l = "post_size / 2"
    rail_y_r = "outer_w - post_size / 2"

    # SideRail_L → Posts
    domino_joint(iface_foot, ("post_size", rail_y_l, rail_z1), "z",
                 "dm_rail_h", "dm_rail_t", "dm_rail_d",
                 "DM_SR_L_F1", sr_l, rail_occ, post_fl, post_occ)
    domino_joint(iface_foot, ("post_size", rail_y_l, rail_z2), "z",
                 "dm_rail_h", "dm_rail_t", "dm_rail_d",
                 "DM_SR_L_F2", sr_l, rail_occ, post_fl, post_occ)
    domino_joint(iface_head, ("outer_l - post_size", rail_y_l, rail_z1), "z",
                 "dm_rail_h", "dm_rail_t", "dm_rail_d",
                 "DM_SR_L_H1", sr_l, rail_occ, post_bl, post_occ)
    domino_joint(iface_head, ("outer_l - post_size", rail_y_l, rail_z2), "z",
                 "dm_rail_h", "dm_rail_t", "dm_rail_d",
                 "DM_SR_L_H2", sr_l, rail_occ, post_bl, post_occ)

    # SideRail_R → Posts
    domino_joint(iface_foot, ("post_size", rail_y_r, rail_z1), "z",
                 "dm_rail_h", "dm_rail_t", "dm_rail_d",
                 "DM_SR_R_F1", sr_r, rail_occ, post_fr, post_occ)
    domino_joint(iface_foot, ("post_size", rail_y_r, rail_z2), "z",
                 "dm_rail_h", "dm_rail_t", "dm_rail_d",
                 "DM_SR_R_F2", sr_r, rail_occ, post_fr, post_occ)
    domino_joint(iface_head, ("outer_l - post_size", rail_y_r, rail_z1), "z",
                 "dm_rail_h", "dm_rail_t", "dm_rail_d",
                 "DM_SR_R_H1", sr_r, rail_occ, post_br, post_occ)
    domino_joint(iface_head, ("outer_l - post_size", rail_y_r, rail_z2), "z",
                 "dm_rail_h", "dm_rail_t", "dm_rail_d",
                 "DM_SR_R_H2", sr_r, rail_occ, post_br, post_occ)

    print("Joinery: 8 side rail domino joints")

    # ── End Rail → Post Dominos (2 per end, 8 joints) ─────────────
    end_x_head = "outer_l - post_size / 2"
    end_x_foot = "post_size / 2"

    # Head end rail → posts (XZ interface planes)
    domino_joint(iface_post_yl, (end_x_head, "post_size", rail_z1), "z",
                 "dm_rail_h", "dm_rail_t", "dm_rail_d",
                 "DM_ER_H_L1", er_head, rail_occ, post_bl, post_occ)
    domino_joint(iface_post_yl, (end_x_head, "post_size", rail_z2), "z",
                 "dm_rail_h", "dm_rail_t", "dm_rail_d",
                 "DM_ER_H_L2", er_head, rail_occ, post_bl, post_occ)
    domino_joint(iface_post_yr, (end_x_head, "outer_w - post_size", rail_z1), "z",
                 "dm_rail_h", "dm_rail_t", "dm_rail_d",
                 "DM_ER_H_R1", er_head, rail_occ, post_br, post_occ)
    domino_joint(iface_post_yr, (end_x_head, "outer_w - post_size", rail_z2), "z",
                 "dm_rail_h", "dm_rail_t", "dm_rail_d",
                 "DM_ER_H_R2", er_head, rail_occ, post_br, post_occ)

    # Foot end rail → posts
    domino_joint(iface_post_yl, (end_x_foot, "post_size", rail_z1), "z",
                 "dm_rail_h", "dm_rail_t", "dm_rail_d",
                 "DM_ER_F_L1", er_foot, rail_occ, post_fl, post_occ)
    domino_joint(iface_post_yl, (end_x_foot, "post_size", rail_z2), "z",
                 "dm_rail_h", "dm_rail_t", "dm_rail_d",
                 "DM_ER_F_L2", er_foot, rail_occ, post_fl, post_occ)
    domino_joint(iface_post_yr, (end_x_foot, "outer_w - post_size", rail_z1), "z",
                 "dm_rail_h", "dm_rail_t", "dm_rail_d",
                 "DM_ER_F_R1", er_foot, rail_occ, post_fr, post_occ)
    domino_joint(iface_post_yr, (end_x_foot, "outer_w - post_size", rail_z2), "z",
                 "dm_rail_h", "dm_rail_t", "dm_rail_d",
                 "DM_ER_F_R2", er_foot, rail_occ, post_fr, post_occ)

    print("Joinery: 8 end rail → post domino joints")

    # ── Guard Rail → Post Dominos ─────────────────────────────────
    guard_z_ctr = "guard_z + guard_w / 2"

    # Right guard → Posts (foot + head)
    domino_joint(iface_foot, ("post_size", rail_y_r, guard_z_ctr), "z",
                 "dm_guard_h", "dm_guard_t", "dm_guard_d",
                 "DM_GR_R_F", gr_r, guard_occ, post_fr, post_occ)
    domino_joint(iface_head, ("outer_l - post_size", rail_y_r, guard_z_ctr), "z",
                 "dm_guard_h", "dm_guard_t", "dm_guard_d",
                 "DM_GR_R_H", gr_r, guard_occ, post_br, post_occ)

    # Head guard → Posts directly (end faces at Y=post_size and Y=outer_w-post_size)
    # Interface is XZ plane at post inner Y faces; guard centered on post in X
    guard_x_head = "outer_l - post_size / 2"  # X center of head guard (inside both guard & post)
    guard_x_foot = "post_size / 2"            # X center of foot guard

    domino_joint(iface_post_yl, (guard_x_head, "post_size", guard_z_ctr), "z",
                 "dm_guard_h", "dm_guard_t", "dm_guard_d",
                 "DM_GR_Head_L", gr_head, guard_occ, post_bl, post_occ)
    domino_joint(iface_post_yr, (guard_x_head, "outer_w - post_size", guard_z_ctr), "z",
                 "dm_guard_h", "dm_guard_t", "dm_guard_d",
                 "DM_GR_Head_R", gr_head, guard_occ, post_br, post_occ)

    # Foot guard → Posts directly
    domino_joint(iface_post_yl, (guard_x_foot, "post_size", guard_z_ctr), "z",
                 "dm_guard_h", "dm_guard_t", "dm_guard_d",
                 "DM_GR_Foot_L", gr_foot, guard_occ, post_fl, post_occ)
    domino_joint(iface_post_yr, (guard_x_foot, "outer_w - post_size", guard_z_ctr), "z",
                 "dm_guard_h", "dm_guard_t", "dm_guard_d",
                 "DM_GR_Foot_R", gr_foot, guard_occ, post_fr, post_occ)

    # Front guard → BL post (head end only, other end has support post)
    domino_joint(iface_head, ("outer_l - post_size", rail_y_l, guard_z_ctr), "z",
                 "dm_guard_h", "dm_guard_t", "dm_guard_d",
                 "DM_GR_Front_H", gr_front, guard_occ, post_bl, post_occ)

    # Fence support → front guard rail (XY interface at Z=guard_z)
    domino_joint(guard_pl, ("fence_front_x + post_size / 2", "post_size / 2", "guard_z"), "x",
                 "dm_guard_h", "dm_guard_t", "dm_guard_d",
                 "DM_FS_GR", fsp_body, guard_occ, gr_front, guard_occ)

    print("Joinery: guard rail domino joints")

    # ── Desk Rail → Post Dominos ──────────────────────────────────
    desk_z_ctr = "desk_rail_z + desk_rail_h / 2"

    # Back desk apron → back posts (rail centered on post in Y, domino at post center)
    # Interface at YZ planes X=post_size and X=outer_l-post_size
    domino_joint(iface_foot, ("post_size", "outer_w - post_size / 2", desk_z_ctr), "z",
                 "dm_desk_h", "dm_desk_t", "dm_desk_d",
                 "DM_DR_B_F", dr_back, desk_occ, post_fr, post_occ)
    domino_joint(iface_head, ("outer_l - post_size", "outer_w - post_size / 2", desk_z_ctr), "z",
                 "dm_desk_h", "dm_desk_t", "dm_desk_d",
                 "DM_DR_B_H", dr_back, desk_occ, post_br, post_occ)

    # Front desk apron → desk legs (interface at side of leg — YZ plane)
    iface_dl_l = sp.off_plane(root, root.yZConstructionPlane,
                              "post_size + desk_leg_size", "Iface_DL_L")
    iface_dl_r = sp.off_plane(root, root.yZConstructionPlane,
                              "outer_l - post_size - desk_leg_size", "Iface_DL_R")

    domino_joint(iface_dl_l,
                 ("post_size + desk_leg_size", "desk_front_y + desk_leg_size / 2", desk_z_ctr), "z",
                 "dm_desk_h", "dm_desk_t", "dm_desk_d",
                 "DM_DL_L", dr_front, desk_occ, dl_l, desk_occ)
    domino_joint(iface_dl_r,
                 ("outer_l - post_size - desk_leg_size", "desk_front_y + desk_leg_size / 2", desk_z_ctr), "z",
                 "dm_desk_h", "dm_desk_t", "dm_desk_d",
                 "DM_DL_R", dr_front, desk_occ, dl_r, desk_occ)

    print("Joinery: desk rail domino joints")

    # ── Ledger → Side Rail Dominos ────────────────────────────────
    iface_led_l = sp.off_plane(root, root.xZConstructionPlane, "post_size / 2 + rail_thick / 2", "Iface_Led_L")
    iface_led_r = sp.off_plane(root, root.xZConstructionPlane, "outer_w - post_size / 2 - rail_thick / 2", "Iface_Led_R")

    led_z_ctr = "ledger_z + ledger_h / 2"
    led_x_first = "post_size + rail_thick + dm_led_sp"

    # Left ledger voids — inside Ledgers component
    sk_ldm, prof_ldm = sp.sketch_slot_model(ledger_c, iface_led_l,
        (led_x_first, "post_size / 2 + rail_thick / 2", led_z_ctr), "x",
        "dm_led_h", "dm_led_t", name="DM_Led_L_Sk", ev=ev)
    ext_ldm = sp.ext_new_sym(ledger_c, prof_ldm, "dm_led_d", "DM_Led_L")
    ldm_body = ext_ldm.bodies.item(0)
    ldm_body.name = "DM_Led_L"

    ldm_pat = sp.body_pattern(ledger_c, ldm_body, root.xConstructionAxis,
                              "n_led_dm", "dm_led_sp", "DM_Led_L_Pat")

    ldm_l_voids = [ldm_body]
    for i in range(ldm_pat.bodies.count):
        ldm_l_voids.append(ldm_pat.bodies.item(i))

    # CUT ledger (same component — no proxy)
    sp.combine(led_l, ldm_l_voids, CUT, True, "DM_Led_L_CutLed")
    # CUT side rail (cross-component via proxies)
    ldm_l_proxies = [v.createForAssemblyContext(ledger_occ) for v in ldm_l_voids]
    sr_l_proxy = sr_l.createForAssemblyContext(rail_occ)
    sp.combine(sr_l_proxy, ldm_l_proxies, CUT, True, "DM_Led_L_CutRail")

    # Right ledger voids — inside Ledgers component
    sk_ldmr, prof_ldmr = sp.sketch_slot_model(ledger_c, iface_led_r,
        (led_x_first, "outer_w - post_size / 2 - rail_thick / 2", led_z_ctr), "x",
        "dm_led_h", "dm_led_t", name="DM_Led_R_Sk", ev=ev)
    ext_ldmr = sp.ext_new_sym(ledger_c, prof_ldmr, "dm_led_d", "DM_Led_R")
    ldmr_body = ext_ldmr.bodies.item(0)
    ldmr_body.name = "DM_Led_R"

    ldmr_pat = sp.body_pattern(ledger_c, ldmr_body, root.xConstructionAxis,
                               "n_led_dm", "dm_led_sp", "DM_Led_R_Pat")

    ldm_r_voids = [ldmr_body]
    for i in range(ldmr_pat.bodies.count):
        ldm_r_voids.append(ldmr_pat.bodies.item(i))

    # CUT ledger (same component — no proxy)
    sp.combine(led_r, ldm_r_voids, CUT, True, "DM_Led_R_CutLed")
    # CUT side rail (cross-component via proxies)
    ldm_r_proxies = [v.createForAssemblyContext(ledger_occ) for v in ldm_r_voids]
    sr_r_proxy = sr_r.createForAssemblyContext(rail_occ)
    sp.combine(sr_r_proxy, ldm_r_proxies, CUT, True, "DM_Led_R_CutRail")

    print("Joinery: 8 ledger domino joints (patterned)")

    # ── Rung → Ladder Side Dominos ────────────────────────────────
    # 2 dominos per joining surface (left end + right end of each rung).
    # sketch_slot_model can't handle negative Y (distance dims always positive).
    # Custom slot_at draws stadium at correct position via modelToSketchSpace,
    # adding only parametric SIZE dimensions (no position dims).
    iface_lad_l = sp.off_plane(root, root.yZConstructionPlane,
                               "post_size + ladder_side_thick", "Iface_Lad_L")
    iface_lad_r = sp.off_plane(root, root.yZConstructionPlane,
                               "post_size + ladder_side_thick + ladder_w", "Iface_Lad_R")

    H_DIM = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V_DIM = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation

    def slot_at(plane, center_cm, vertical, h_expr, t_expr, name):
        """Stadium sketch at model-space center. Only size dims (no position dims)."""
        sk_s = ladder_c.sketches.add(plane)
        sk_s.name = name + "_Sk"
        m2s_s = sk_s.modelToSketchSpace
        cx_m, cy_m, cz_m = center_cm
        csk = m2s_s(P(cx_m, cy_m, cz_m))
        cx, cy = csk.x, csk.y
        h_v, t_v = ev(h_expr), ev(t_expr)
        r = t_v / 2
        hl = (h_v - t_v) / 2
        slines = sk_s.sketchCurves.sketchLines
        sarcs = sk_s.sketchCurves.sketchArcs
        if vertical:
            br = P(cx + r, cy - hl, 0)
            tr = P(cx + r, cy + hl, 0)
            tc = P(cx, cy + hl, 0)
            tl = P(cx - r, cy + hl, 0)
            bl = P(cx - r, cy - hl, 0)
            bc = P(cx, cy - hl, 0)
            l_r = slines.addByTwoPoints(br, tr)
            a_t = sarcs.addByCenterStartSweep(tc, tr, math.pi)
            l_l = slines.addByTwoPoints(tl, bl)
            a_b = sarcs.addByCenterStartSweep(bc, bl, math.pi)
            sk_s.geometricConstraints.addVertical(l_r)
            sk_s.geometricConstraints.addVertical(l_l)
            sk_s.geometricConstraints.addTangent(l_r, a_t)
            sk_s.geometricConstraints.addTangent(a_t, l_l)
            sk_s.geometricConstraints.addTangent(l_l, a_b)
            sk_s.geometricConstraints.addTangent(a_b, l_r)
            d = sk_s.sketchDimensions
            d.addRadialDimension(a_b,
                P(cx + r + 1, cy - hl, 0)).parameter.expression = t_expr + " / 2"
            d.addDistanceDimension(
                a_b.centerSketchPoint, a_t.centerSketchPoint,
                V_DIM, P(cx + r + 2, cy, 0)
            ).parameter.expression = h_expr + " - " + t_expr
        else:
            bsl = P(cx - hl, cy - r, 0)
            bsr = P(cx + hl, cy - r, 0)
            rc = P(cx + hl, cy, 0)
            tsr = P(cx + hl, cy + r, 0)
            tsl = P(cx - hl, cy + r, 0)
            lc = P(cx - hl, cy, 0)
            l_b = slines.addByTwoPoints(bsl, bsr)
            a_r = sarcs.addByCenterStartSweep(rc, bsr, math.pi)
            l_t = slines.addByTwoPoints(tsr, tsl)
            a_l = sarcs.addByCenterStartSweep(lc, tsl, math.pi)
            sk_s.geometricConstraints.addHorizontal(l_b)
            sk_s.geometricConstraints.addHorizontal(l_t)
            sk_s.geometricConstraints.addTangent(l_b, a_r)
            sk_s.geometricConstraints.addTangent(a_r, l_t)
            sk_s.geometricConstraints.addTangent(l_t, a_l)
            sk_s.geometricConstraints.addTangent(a_l, l_b)
            d = sk_s.sketchDimensions
            d.addRadialDimension(a_l,
                P(cx - hl - 1, cy + r + 1, 0)).parameter.expression = t_expr + " / 2"
            d.addDistanceDimension(
                a_l.centerSketchPoint, a_r.centerSketchPoint,
                H_DIM, P(cx, cy - r - 2, 0)
            ).parameter.expression = h_expr + " - " + t_expr
        return sk_s, sk_s.profiles.item(0)

    inner_x_dm = post_size_val + side_thick_val
    right_x_dm = inner_x_dm + ladder_w_val

    all_left_voids = []
    all_right_voids = []
    rung_void_map = {}  # rung index → list of void bodies for CUT

    for idx in range(n_rungs_val):
        i = idx + 1
        frac = i / (n_rungs_val + 1)
        frac_remain_r = (n_rungs_val + 1 - i) / (n_rungs_val + 1)
        rung_z_ctr = top_z_val * frac + rung_face_val / 2
        rung_y_back = -lean_val * frac_remain_r  # back edge Y of rung
        # 2 dominos spaced at 1/3 and 2/3 of ladder_side_w (joining area)
        dm_y1 = rung_y_back - side_w_val / 3
        dm_y2 = rung_y_back - 2 * side_w_val / 3

        rung_voids = []
        for j, dm_y in enumerate([dm_y1, dm_y2], 1):
            # Left side (on iface_lad_l — vertical stadium, long axis = model Y)
            _, prf_l = slot_at(iface_lad_l, (inner_x_dm, dm_y, rung_z_ctr),
                               True, "dm_rung_h", "dm_rung_t", f"DM_R{i}L{j}")
            ext_l = sp.ext_new_sym(ladder_c, prf_l, "dm_rung_d", f"DM_R{i}L{j}")
            v_l = ext_l.bodies.item(0)
            v_l.name = f"DM_R{i}L{j}"
            all_left_voids.append(v_l)
            rung_voids.append(v_l)

            # Right side (on iface_lad_r — same orientation)
            _, prf_r = slot_at(iface_lad_r, (right_x_dm, dm_y, rung_z_ctr),
                               True, "dm_rung_h", "dm_rung_t", f"DM_R{i}R{j}")
            ext_r = sp.ext_new_sym(ladder_c, prf_r, "dm_rung_d", f"DM_R{i}R{j}")
            v_r = ext_r.bodies.item(0)
            v_r.name = f"DM_R{i}R{j}"
            all_right_voids.append(v_r)
            rung_voids.append(v_r)

        rung_void_map[idx] = rung_voids

    # CUT all left voids from left ladder side (same component — no proxy)
    sp.combine(ls_l, all_left_voids, CUT, True, "DM_Rung_CutSideL")

    # CUT all right voids from right ladder side (same component — no proxy)
    sp.combine(ls_r, all_right_voids, CUT, True, "DM_Rung_CutSideR")

    # CUT each rung's 4 voids from that rung body (same component — no proxy)
    for idx in range(n_rungs_val):
        sp.combine(rung_bodies[idx], rung_void_map[idx], CUT, True, f"DM_Rung{idx+1}_Cut")

    print(f"Joinery: {n_rungs_val * 4} rung domino joints (2 per end)")

    # ── Ladder Side → Side Rail Dominos (hook joint) ────────────────
    # 2 dominos per side connecting ladder hook vertical face to side rail
    lad_x_l = "post_size + ladder_side_thick / 2"
    lad_x_r = "post_size + ladder_side_thick + ladder_w + ladder_side_thick / 2"
    lad_rail_y = "post_size / 2 - rail_thick / 2"

    domino_joint(iface_rail_front,
                 (lad_x_l, lad_rail_y, rail_z1), "z",
                 "dm_rail_h", "dm_rail_t", "dm_rail_d",
                 "DM_LH_L1", ls_l, ladder_occ, sr_l, rail_occ)
    domino_joint(iface_rail_front,
                 (lad_x_l, lad_rail_y, rail_z2), "z",
                 "dm_rail_h", "dm_rail_t", "dm_rail_d",
                 "DM_LH_L2", ls_l, ladder_occ, sr_l, rail_occ)
    domino_joint(iface_rail_front,
                 (lad_x_r, lad_rail_y, rail_z1), "z",
                 "dm_rail_h", "dm_rail_t", "dm_rail_d",
                 "DM_LH_R1", ls_r, ladder_occ, sr_l, rail_occ)
    domino_joint(iface_rail_front,
                 (lad_x_r, lad_rail_y, rail_z2), "z",
                 "dm_rail_h", "dm_rail_t", "dm_rail_d",
                 "DM_LH_R2", ls_r, ladder_occ, sr_l, rail_occ)

    print("Joinery: 4 ladder hook → side rail dominos")

    # Count joinery voids in root
    root_bodies = [root.bRepBodies.item(i).name for i in range(root.bRepBodies.count)]
    print(f"Root: {len(root_bodies)} joinery voids")

    # ── Details ────────────────────────────────────────────────────
    # Post top chamfers
    target_z = ev("post_h")
    for i in range(post_c.bRepBodies.count):
        body = post_c.bRepBodies.item(i)
        edges = adsk.core.ObjectCollection.create()
        for j in range(body.edges.count):
            e = body.edges.item(j)
            sv = e.startVertex.geometry
            ev2 = e.endVertex.geometry
            if abs(sv.z - target_z) < 0.01 and abs(ev2.z - target_z) < 0.01:
                edges.add(e)
        if edges.count > 0:
            ch_inp = post_c.features.chamferFeatures.createInput2()
            ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                edges, adsk.core.ValueInput.createByString("post_chamfer"), False)
            ch = post_c.features.chamferFeatures.add(ch_inp)
            ch.name = f"PostTop_Ch_{body.name}"

    print("Details: post top chamfers applied")

    # ── Epilogue: hide construction ────────────────────────────────
    for sk in root.sketches:
        sk.isVisible = False
    for cp in root.constructionPlanes:
        cp.isLightBulbOn = False
    for ca in root.constructionAxes:
        ca.isLightBulbOn = False
    for comp in [post_c, rail_c, guard_c, ledger_c, slat_c, desk_c, ladder_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False
        for ca in comp.constructionAxes:
            ca.isLightBulbOn = False

    sp.apply_appearance("white oak")

    # ── Dependency tree validation ────────────────────────────────
    sp.validate_deps(ctx)
