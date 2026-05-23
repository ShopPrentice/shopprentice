"""
Hall Bench with Raked Back
==========================
60"L x 18"D x ~32"H total, 18"H seat height.
Modern style, white oak. Back posts have a smooth curved transition
from vertical to 8° angled backrest (like a chair). Post tops are
cut square to the rake angle.

Coordinate system:
  X = length (60")  Y = depth (18")  Z = height
"""
import adsk.core, adsk.fusion, math

from helpers import sp
from woodworking.templates import domino

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
    for pname, expr, unit, desc in [
        ("bench_l",       "60 in",   "in", "Overall length"),
        ("bench_d",       "18 in",   "in", "Overall depth"),
        ("seat_h",        "18 in",   "in", "Seat height"),
        ("seat_thick",    "1.5 in",  "in", "Seat slab thickness"),
        ("leg_size",      "2 in",    "in", "Leg cross-section (square)"),
        ("apron_h",       "3 in",    "in", "Apron height"),
        ("apron_thick",   "0.75 in", "in", "Apron thickness"),
        ("front_inset",   "20 mm",   "in", "Front leg inset from seat edge"),
        ("back_board_w",  "20 cm",   "in", "Back board width"),
        ("back_board_t",  "0.75 in", "in", "Back board thickness"),
        ("back_rake",     "8",       "",   "Back rake angle (degrees)"),
        ("bend_above",    "2 in",    "in", "Height above seat where bend starts"),
        ("bend_r",        "6 in",    "in", "Bend fillet radius"),
        ("back_board_offset","7 in", "in", "Distance along post from bend to board center"),
        ("upper_post_margin","1.5 in","in","Post length above back board"),
        ("dm_t",          "8 mm",    "in", "Domino cutter diameter"),
        ("dm_w",          "40 mm",   "in", "Domino width"),
        ("dm_d",          "20 mm",   "in", "Domino depth per side"),
        ("dm_count",      "2",       "",   "Dominos per apron-to-leg joint"),
        ("fl_r",          "0.125 in","in", "Seat top edge fillet"),
        ("seat_front_r",  "0.5 in",  "in", "Seat front edge fillet"),
        ("bb_r",          "0.125 in","in", "Back board edge fillet"),
        ("ch_d",          "0.0625 in","in","Chamfer distance"),
    ]:
        params.add(pname, VI(expr), unit, desc)

    for pname, expr, unit, desc in [
        ("leg_h",            "seat_h - seat_thick",                                    "in", "Front leg height"),
        ("inner_l",          "bench_l - 2 * leg_size",                                "in", "Length between legs"),
        ("inner_d",          "bench_d - 2 * leg_size - front_inset",                   "in", "Depth between legs"),
        ("apron_z",          "seat_h - seat_thick - apron_h",                         "in", "Apron bottom Z"),
        ("bend_z",           "seat_h + bend_above",                                   "in", "Z where bend starts"),
        ("upper_post_len",   "back_board_offset + back_board_w / 2 + upper_post_margin","in","Angled post length above bend"),
        ("back_board_z",     "bend_z + back_board_offset - back_board_w / 2",         "in", "Back board bottom Z (pre-rotation)"),
        ("dm_sp",            "apron_h / (dm_count + 1)",                              "in", "Domino spacing"),
    ]:
        params.add(pname, VI(expr), unit, desc)

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

    # Rake geometry (used for post profile + domino positions)
    rake_rad = math.radians(ev("back_rake"))
    cos_r, sin_r = math.cos(rake_rad), math.sin(rake_rad)

    XMid = sp.off_plane(root, root.yZConstructionPlane, "bench_l / 2", "XMid")

    # ==============================================================
    #  1. LEGS — front legs + profiled back posts with smooth bend
    # ==============================================================
    leg_occ = sp.make_comp(root, "Legs")
    leg_c = leg_occ.component

    _, pr = sp.sketch_rect_model(leg_c, root.xYConstructionPlane,
        ("0 in", "front_inset", "0 in"),
        {"x": "leg_size", "y": "leg_size"},
        "LegFL_Sk", ev=ev)
    leg_fl = sp.ext_new(leg_c, pr, "leg_h", "LegFL").bodies.item(0)
    leg_fl.name = "Leg_FL"

    # Back-left post — profiled extrusion with square top
    yi = ev("bench_d - leg_size")
    yo = ev("bench_d")
    bz = ev("bend_z")
    ls = ev("leg_size")
    h_back = ev("upper_post_len")
    dy, dz = h_back * sin_r, h_back * cos_r

    sk = leg_c.sketches.add(leg_c.yZConstructionPlane)
    sk.name = "PostBL_Profile_Sk"
    lines = sk.sketchCurves.sketchLines
    P3 = adsk.core.Point3D
    m2s = sk.modelToSketchSpace

    # 6-point profile: vertical bottom → bend → angled top (square cap)
    mp = [
        P3.create(0, yi, 0),                                              # 0: inner bottom
        P3.create(0, yi, bz),                                             # 1: inner bend
        P3.create(0, yi + dy, bz + dz),                                   # 2: inner top
        P3.create(0, yi + dy + ls * cos_r, bz + dz - ls * sin_r),         # 3: outer top (square cap)
        P3.create(0, yo, bz),                                             # 4: outer bend
        P3.create(0, yo, 0),                                              # 5: outer bottom
    ]
    spts = [m2s(p) for p in mp]

    l0 = lines.addByTwoPoints(spts[0], spts[1])
    l1 = lines.addByTwoPoints(l0.endSketchPoint, spts[2])
    l2 = lines.addByTwoPoints(l1.endSketchPoint, spts[3])
    l3 = lines.addByTwoPoints(l2.endSketchPoint, spts[4])
    l4 = lines.addByTwoPoints(l3.endSketchPoint, spts[5])
    l5 = lines.addByTwoPoints(l4.endSketchPoint, l0.startSketchPoint)

    h_ax, v_ax = sp.probe_sketch_axes(sk)
    gc = sk.geometricConstraints
    if v_ax == "z":
        gc.addVertical(l0);  gc.addVertical(l4)
        gc.addHorizontal(l5)
    else:
        gc.addHorizontal(l0); gc.addHorizontal(l4)
        gc.addVertical(l5)
    # l2 (top cap) is NOT horizontal — it's perpendicular to the rake

    prof = sk.profiles.item(0)
    ext_inp = leg_c.features.extrudeFeatures.createInput(
        prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ext_inp.setDistanceExtent(False, VI("leg_size"))
    bl_ext = leg_c.features.extrudeFeatures.add(ext_inp)
    bl_ext.name = "PostBL"
    post_bl = bl_ext.bodies.item(0)
    post_bl.name = "Post_BL"

    # Fillet bend edges (inner + outer)
    bend_edges = adsk.core.ObjectCollection.create()
    for i in range(post_bl.edges.count):
        edge = post_bl.edges.item(i)
        if edge.faces.count != 2:
            continue
        g1 = edge.faces.item(0).geometry
        g2 = edge.faces.item(1).geometry
        if not (isinstance(g1, adsk.core.Plane) and isinstance(g2, adsk.core.Plane)):
            continue
        n1, n2 = g1.normal, g2.normal
        dot = max(-1.0, min(1.0, n1.x*n2.x + n1.y*n2.y + n1.z*n2.z))
        angle = math.degrees(math.acos(dot))
        if angle < 20:
            bend_edges.add(edge)

    if bend_edges.count > 0:
        fil_inp = leg_c.features.filletFeatures.createInput()
        fil_inp.addConstantRadiusEdgeSet(bend_edges, VI("bend_r"), True)
        leg_c.features.filletFeatures.add(fil_inp).name = "PostBL_Bend_Fil"
        print(f">>> Bend fillet: {bend_edges.count} edges")

    mir = sp.mirror_bodies(leg_c, [leg_fl, post_bl], XMid, "LegR_Mir")
    leg_fr = mir.bodies.item(0); leg_fr.name = "Leg_FR"
    post_br = mir.bodies.item(1); post_br.name = "Post_BR"

    print(f">>> Legs: {leg_c.bRepBodies.count} bodies")

    # -- Body-relative references: aprons positioned relative to legs/posts --
    ref_leg_fl = find_body("Leg_FL")
    ref_leg_fl_bb = ref_leg_fl.boundingBox
    ref_leg_fr = find_body("Leg_FR")
    ref_leg_fr_bb = ref_leg_fr.boundingBox
    ref_post_bl = find_body("Post_BL")
    ref_post_bl_bb = ref_post_bl.boundingBox

    # ==============================================================
    #  2. APRONS
    # ==============================================================
    apr_occ = sp.make_comp(root, "Aprons")
    apr_c = apr_occ.component

    front_apr_pl = sp.off_plane(apr_c, root.xZConstructionPlane,
        "front_inset", "FrontAprY_Pl")
    _, pr = sp.sketch_rect_model(apr_c, front_apr_pl,
        ("leg_size", "front_inset", "apron_z"),
        {"x": "inner_l", "z": "apron_h"},
        "AprFront_Sk", ev=ev)
    apr_front = sp.ext_new(apr_c, pr, "apron_thick", "AprFront").bodies.item(0)
    apr_front.name = "Apron_Front"

    back_apr_pl = sp.off_plane(apr_c, root.xZConstructionPlane,
        "bench_d - leg_size + (leg_size - apron_thick) / 2", "BackAprY_Pl")
    _, pr = sp.sketch_rect_model(apr_c, back_apr_pl,
        ("leg_size", "0 in", "apron_z"),
        {"x": "inner_l", "z": "apron_h"},
        "AprBack_Sk", ev=ev)
    apr_back = sp.ext_new(apr_c, pr, "apron_thick", "AprBack").bodies.item(0)
    apr_back.name = "Apron_Back"

    _, pr = sp.sketch_rect_model(apr_c, root.yZConstructionPlane,
        ("0 in", "front_inset + leg_size", "apron_z"),
        {"y": "inner_d", "z": "apron_h"},
        "AprLeft_Sk", ev=ev)
    apr_left = sp.ext_new(apr_c, pr, "apron_thick", "AprLeft").bodies.item(0)
    apr_left.name = "Apron_Left"

    apr_right = sp.mirror_body(apr_c, apr_left, XMid, "AprRight_Mir").bodies.item(0)
    apr_right.name = "Apron_Right"

    print(f">>> Aprons: {apr_c.bRepBodies.count} bodies")

    # -- Body-relative reference: back board positioned relative to posts --
    # (Post_BL ref already resolved above — re-read for back board positioning)
    ref_post_bl_back_bb = ref_post_bl.boundingBox

    # ==============================================================
    #  3. BACK — back board (raked to match post angle)
    # ==============================================================
    back_occ = sp.make_comp(root, "Back")
    back_c = back_occ.component

    bb_y_pl = sp.off_plane(back_c, root.xZConstructionPlane,
        "bench_d - leg_size + (leg_size - back_board_t) / 2", "BackBoardY_Pl")
    _, pr = sp.sketch_rect_model(back_c, bb_y_pl,
        ("leg_size", "0 in", "back_board_z"),
        {"x": "inner_l", "z": "back_board_w"},
        "BackBoard_Sk", ev=ev)
    back_board = sp.ext_new(back_c, pr, "back_board_t", "BackBoard").bodies.item(0)
    back_board.name = "Back_Board"

    # Rotate board to match post rake — pivot at bend point
    bodies_to_rotate = adsk.core.ObjectCollection.create()
    bodies_to_rotate.add(back_board)
    transform = adsk.core.Matrix3D.create()
    pivot = adsk.core.Point3D.create(0, ev("bench_d"), ev("bend_z"))
    transform.setToRotation(-rake_rad, adsk.core.Vector3D.create(1, 0, 0), pivot)
    move_input = back_c.features.moveFeatures.createInput(bodies_to_rotate, transform)
    back_c.features.moveFeatures.add(move_input).name = "BackRake"

    print(f">>> Back: {back_c.bRepBodies.count} body (raked)")

    # ==============================================================
    #  4. SEAT
    # ==============================================================
    seat_occ = sp.make_comp(root, "Seat")
    seat_c = seat_occ.component

    seat_z_pl = sp.off_plane(seat_c, root.xYConstructionPlane,
        "seat_h - seat_thick", "SeatZ_Pl")
    _, pr = sp.sketch_rect_model(seat_c, seat_z_pl,
        ("0 in", "0 in", "seat_h - seat_thick"),
        {"x": "bench_l", "y": "bench_d"},
        "Seat_Sk", ev=ev)
    seat_body = sp.ext_new(seat_c, pr, "seat_thick", "SeatBoard").bodies.item(0)
    seat_body.name = "Seat"

    print(f">>> Seat: {seat_c.bRepBodies.count} body")

    # -- Body-relative references: dominos positioned relative to aprons + back board --
    ref_apron_front = find_body("Apron_Front")
    ref_apron_front_bb = ref_apron_front.boundingBox
    ref_apron_back = find_body("Apron_Back")
    ref_apron_back_bb = ref_apron_back.boundingBox
    ref_apron_left = find_body("Apron_Left")
    ref_apron_left_bb = ref_apron_left.boundingBox
    ref_apron_right = find_body("Apron_Right")
    ref_apron_right_bb = ref_apron_right.boundingBox
    ref_back_board = find_body("Back_Board")
    ref_back_board_bb = ref_back_board.boundingBox

    # ==============================================================
    #  5. JOINERY
    # ==============================================================
    # Leg/post proxies (cross-component targets for apron + back board dominos)
    fl_p = leg_fl.createForAssemblyContext(leg_occ)
    fr_p = leg_fr.createForAssemblyContext(leg_occ)
    bl_p = post_bl.createForAssemblyContext(leg_occ)
    br_p = post_br.createForAssemblyContext(leg_occ)
    seat_p = seat_body.createForAssemblyContext(seat_occ)

    # -- Apron dominos (voids live in apron component) --
    dm_yz_l = sp.off_plane(apr_c, apr_c.yZConstructionPlane, "leg_size", "DM_YZ_L")
    dm_yz_r = sp.off_plane(apr_c, apr_c.yZConstructionPlane, "bench_l - leg_size", "DM_YZ_R")
    dm_xz_f = sp.off_plane(apr_c, apr_c.xZConstructionPlane, "front_inset + leg_size", "DM_XZ_F")
    dm_xz_b = sp.off_plane(apr_c, apr_c.xZConstructionPlane, "bench_d - leg_size", "DM_XZ_B")

    domino.grid(apr_c, dm_yz_l,
        start=("leg_size", "front_inset + apron_thick / 2", "apron_z + dm_sp"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d", body_a=apr_front, body_b=fl_p, name="DM_FA_L", ev=ev)
    domino.grid(apr_c, dm_yz_r,
        start=("bench_l - leg_size", "front_inset + apron_thick / 2", "apron_z + dm_sp"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d", body_a=apr_front, body_b=fr_p, name="DM_FA_R", ev=ev)
    domino.grid(apr_c, dm_yz_l,
        start=("leg_size", "bench_d - leg_size / 2", "apron_z + dm_sp"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d", body_a=apr_back, body_b=bl_p, name="DM_BA_L", ev=ev)
    domino.grid(apr_c, dm_yz_r,
        start=("bench_l - leg_size", "bench_d - leg_size / 2", "apron_z + dm_sp"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d", body_a=apr_back, body_b=br_p, name="DM_BA_R", ev=ev)
    domino.grid(apr_c, dm_xz_f,
        start=("apron_thick / 2", "front_inset + leg_size", "apron_z + dm_sp"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d", body_a=apr_left, body_b=fl_p, name="DM_LA_F", ev=ev)
    domino.grid(apr_c, dm_xz_b,
        start=("apron_thick / 2", "bench_d - leg_size", "apron_z + dm_sp"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d", body_a=apr_left, body_b=bl_p, name="DM_LA_B", ev=ev)
    domino.grid(apr_c, dm_xz_f,
        start=("bench_l - apron_thick / 2", "front_inset + leg_size", "apron_z + dm_sp"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d", body_a=apr_right, body_b=fr_p, name="DM_RA_F", ev=ev)
    domino.grid(apr_c, dm_xz_b,
        start=("bench_l - apron_thick / 2", "bench_d - leg_size", "apron_z + dm_sp"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d", body_a=apr_right, body_b=br_p, name="DM_RA_B", ev=ev)

    # -- Back board dominos (voids live in back component) --
    bb_off = ev("back_board_offset")
    bench_d_cm = ev("bench_d")
    bend_z_cm = ev("bend_z")
    ls_cm = ev("leg_size")
    # Board center after rotation (relative to bend pivot)
    bb_y = bench_d_cm + (-ls_cm / 2 * cos_r + bb_off * sin_r)
    bb_z = bend_z_cm + (ls_cm / 2 * sin_r + bb_off * cos_r)

    dm_bb_yz_l = sp.off_plane(back_c, back_c.yZConstructionPlane, "leg_size", "DM_YZ_L")
    dm_bb_yz_r = sp.off_plane(back_c, back_c.yZConstructionPlane, "bench_l - leg_size", "DM_YZ_R")

    domino.single(back_c, dm_bb_yz_l,
        center=(f"{ls_cm} cm", f"{bb_y} cm", f"{bb_z} cm"),
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d", body_a=back_board, body_b=bl_p,
        name="DM_BB_L", ev=ev)
    domino.single(back_c, dm_bb_yz_r,
        center=(f"{ev('bench_l') - ls_cm} cm", f"{bb_y} cm", f"{bb_z} cm"),
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d", body_a=back_board, body_b=br_p,
        name="DM_BB_R", ev=ev)

    print(f">>> Dominos done")

    # Seat notches
    sp.combine(seat_p, [bl_p, br_p], CUT, True, "SeatNotch")

    print(">>> Joinery done")

    # ==============================================================
    #  6. DETAILS — fillets and chamfers
    # ==============================================================
    # --- Seat front fillet (generous rounding on front edge) ---
    seat_p = seat_body.createForAssemblyContext(seat_occ)
    seat_front = sp.find_face(seat_p, "y", -1)
    front_edges = adsk.core.ObjectCollection.create()
    fe_added = set()
    for i in range(seat_front.edges.count):
        e = seat_front.edges.item(i)
        if e.tempId not in fe_added:
            front_edges.add(e)
            fe_added.add(e.tempId)
    fil_inp = root.features.filletFeatures.createInput()
    fil_inp.addConstantRadiusEdgeSet(front_edges, VI("seat_front_r"), True)
    root.features.filletFeatures.add(fil_inp).name = "Seat_Front_Fil"

    # --- Seat top edge fillet (remaining edges) ---
    seat_p = seat_body.createForAssemblyContext(seat_occ)
    seat_top = sp.find_face(seat_p, "z", +1)
    top_edges = adsk.core.ObjectCollection.create()
    te_added = set()
    for i in range(seat_top.edges.count):
        e = seat_top.edges.item(i)
        if e.tempId not in te_added:
            top_edges.add(e)
            te_added.add(e.tempId)
    fil_inp = root.features.filletFeatures.createInput()
    fil_inp.addConstantRadiusEdgeSet(top_edges, VI("fl_r"), True)
    root.features.filletFeatures.add(fil_inp).name = "Seat_Top_Fil"

    # --- Back board fillet (long edges along X) ---
    bb_p = back_board.createForAssemblyContext(back_occ)
    bb_edges = adsk.core.ObjectCollection.create()
    for i in range(bb_p.edges.count):
        e = bb_p.edges.item(i)
        sp_pt, ep_pt = e.startVertex.geometry, e.endVertex.geometry
        if abs(sp_pt.y - ep_pt.y) < 0.1 and abs(sp_pt.z - ep_pt.z) < 0.1:
            bb_edges.add(e)
    if bb_edges.count > 0:
        fil_inp = root.features.filletFeatures.createInput()
        fil_inp.addConstantRadiusEdgeSet(bb_edges, VI("bb_r"), True)
        root.features.filletFeatures.add(fil_inp).name = "BackBoard_Fil"

    # --- Leg/post bottom chamfers ---
    for body, name in [(leg_fl, "LegFL"), (leg_fr, "LegFR"),
                       (post_bl, "PostBL"), (post_br, "PostBR")]:
        proxy = body.createForAssemblyContext(leg_occ)
        bot = sp.find_face(proxy, "z", -1)
        ch_edges = adsk.core.ObjectCollection.create()
        ch_added = set()
        for i in range(bot.edges.count):
            e = bot.edges.item(i)
            if e.tempId not in ch_added:
                ch_edges.add(e)
                ch_added.add(e.tempId)
        ch_inp = root.features.chamferFeatures.createInput2()
        ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
            ch_edges, VI("ch_d"), True)
        root.features.chamferFeatures.add(ch_inp).name = f"{name}_Bot_Ch"

    # --- Front leg vertical edge chamfers ---
    for body, name in [(leg_fl, "LegFL"), (leg_fr, "LegFR")]:
        proxy = body.createForAssemblyContext(leg_occ)
        vert_edges = adsk.core.ObjectCollection.create()
        for i in range(proxy.edges.count):
            e = proxy.edges.item(i)
            sp_pt, ep_pt = e.startVertex.geometry, e.endVertex.geometry
            dz_e = abs(sp_pt.z - ep_pt.z)
            dx_e = abs(sp_pt.x - ep_pt.x)
            dy_e = abs(sp_pt.y - ep_pt.y)
            if dz_e > 10 and dx_e < 0.1 and dy_e < 0.1:
                vert_edges.add(e)
        if vert_edges.count > 0:
            ch_inp = root.features.chamferFeatures.createInput2()
            ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                vert_edges, VI("ch_d"), True)
            root.features.chamferFeatures.add(ch_inp).name = f"{name}_Vert_Ch"

    # --- Post edge chamfers (edges along X, away from fillet zone) ---
    for body, name in [(post_bl, "PostBL"), (post_br, "PostBR")]:
        proxy = body.createForAssemblyContext(leg_occ)
        x_edges = adsk.core.ObjectCollection.create()
        for i in range(proxy.edges.count):
            e = proxy.edges.item(i)
            if not e.isValid or e.faces.count < 2:
                continue
            sp_pt, ep_pt = e.startVertex.geometry, e.endVertex.geometry
            dx_e = abs(sp_pt.x - ep_pt.x)
            dy_e = abs(sp_pt.y - ep_pt.y)
            dz_e = abs(sp_pt.z - ep_pt.z)
            if dx_e < ls * 0.9 or dy_e > 0.1 or dz_e > 0.1:
                continue
            # Both faces must be planar (skip edges touching fillet)
            g1 = e.faces.item(0).geometry
            g2 = e.faces.item(1).geometry
            if not (isinstance(g1, adsk.core.Plane) and isinstance(g2, adsk.core.Plane)):
                continue
            # Only ~90° edges (skip near-parallel bend zone edges)
            n1, n2 = g1.normal, g2.normal
            dot = abs(n1.x*n2.x + n1.y*n2.y + n1.z*n2.z)
            if dot < 0.35:  # angle between 70-110°
                x_edges.add(e)
        if x_edges.count > 0:
            ch_inp = root.features.chamferFeatures.createInput2()
            ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                x_edges, VI("ch_d"), True)
            root.features.chamferFeatures.add(ch_inp).name = f"{name}_Edge_Ch"

    print(">>> Details done")

    # ==============================================================
    #  EPILOGUE
    # ==============================================================
    comps = [root] + [root.allOccurrences.item(i).component
                      for i in range(root.allOccurrences.count)]
    for c in comps:
        for sk in c.sketches:
            sk.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False
        for ca in c.constructionAxes:
            ca.isLightBulbOn = False

    for i in range(root.occurrences.count):
        occ = root.occurrences.item(i)
        cn = occ.component.name
        names = [occ.component.bRepBodies.item(j).name
                 for j in range(occ.component.bRepBodies.count)]
        print(f"{cn}: {len(names)} -> {names}")
    print(f"Root: {root.bRepBodies.count} bodies")

    sp.apply_appearance("white oak")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
