"""
Modern Dining Chair (NORDVIKEN-inspired)
========================================
18"W x 17"D seat, 18"H seat height, 34"H total.
Vertical back slats with top/bottom rails, back legs vertical to 2" above
seat then smoothly curved into 8° angled backrest. Box stretchers, domino
joinery at all connections, through-mortise rails and slats.

Coordinate system:
  X = width (18")  Y = depth (17")  Z = height (34")
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

    # === USER PARAMETERS ===
    for pname, expr, unit in [
        ("seat_w",       "18 in",    "in"),
        ("seat_d",       "17 in",    "in"),
        ("seat_h",       "18 in",    "in"),
        ("back_h",       "34 in",    "in"),
        ("seat_thick",   "0.75 in",  "in"),
        ("leg_size",     "1.5 in",   "in"),
        ("apron_h",      "3 in",     "in"),
        ("apron_thick",  "0.75 in",  "in"),
        ("back_rake",    "8 deg",    "deg"),
        ("bend_above",   "2 in",     "in"),
        ("bend_r",       "6 in",     "in"),
        # Back slats (vertical) and rails
        ("n_slats",      "3",        ""),
        ("slat_w",       "2 in",     "in"),   # vertical slat width (in X)
        ("slat_thick",   "0.75 in",  "in"),   # slat depth (in Y)
        ("top_rail_h",   "2.5 in",   "in"),   # top rail height
        ("bot_rail_h",   "2 in",     "in"),   # bottom rail height
        ("rail_thick",   "1 in",     "in"),   # rail depth (thicker for strength)
        ("top_rail_off", "0.5 in",   "in"),   # top rail offset below back_h
        # Stretchers
        ("str_h",        "1.5 in",   "in"),
        ("str_thick",    "1 in",     "in"),    # thicker for strength
        ("str_z",        "4 in",     "in"),
        # Dominos (6mm)
        ("dm_t",         "6 mm",     "in"),
        ("dm_w",         "20 mm",    "in"),
        ("dm_d",         "15 mm",    "in"),
        # Details
        ("leg_chamfer",  "0.125 in", "in"),
        ("seat_fillet",  "0.125 in", "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    # === DERIVED PARAMETERS ===
    for pname, expr, unit in [
        ("front_leg_h",   "seat_h - seat_thick",             "in"),
        ("apron_z",       "seat_h - seat_thick - apron_h",   "in"),
        ("short_apron_l", "seat_w - 2 * leg_size",           "in"),
        ("long_apron_l",  "seat_d - 2 * leg_size",           "in"),
        ("mid_x",         "seat_w / 2",                       "in"),
        ("mid_y",         "seat_d / 2",                       "in"),
        # Bend and backrest
        ("bend_z",        "seat_h + bend_above",              "in"),
        ("back_post_h",   "back_h - bend_z + seat_thick",    "in"),
        # Vertical slat spacing (equal gaps between slats and to posts)
        ("slat_gap",      "(short_apron_l - n_slats * slat_w) / (n_slats + 1)", "in"),
        ("slat_pitch_x",  "slat_w + slat_gap",               "in"),
        ("slat_start_x",  "leg_size + slat_gap + slat_w / 2", "in"),
        ("slat_zone_h",   "back_h - top_rail_off - top_rail_h - bend_z - bot_rail_h", "in"),
        # Center rails/slats on back leg cross-section
        ("back_face_y",   "seat_d - leg_size / 2 - rail_thick / 2", "in"),
        # Slat stub tenon into rails
        ("slat_tenon",    "dm_d",                                  "in"),
        # Stretcher
        ("front_str_l",   "seat_w - 2 * leg_size",           "in"),
        ("str_dm_z",      "str_z + str_h / 2",               "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    print(">>> Parameters done")

    # === COMPONENTS ===
    leg_occ   = sp.make_comp(root, "Legs")
    apron_occ = sp.make_comp(root, "Aprons")
    str_occ   = sp.make_comp(root, "Stretchers")
    seat_occ  = sp.make_comp(root, "Seat")
    back_occ  = sp.make_comp(root, "Back")

    leg_c   = leg_occ.component
    apron_c = apron_occ.component
    str_c   = str_occ.component
    seat_c  = seat_occ.component
    back_c  = back_occ.component

    # ==== FRONT LEGS ====
    _, pr = sp.sketch_rect_model(leg_c, leg_c.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_size", "y": "leg_size"}, "LegFL_Sk", ev)
    fl_ext = sp.ext_new(leg_c, pr, "front_leg_h", "LegFL")
    leg_fl = fl_ext.bodies.item(0); leg_fl.name = "Leg_FL"

    l_xmid = sp.off_plane(leg_c, leg_c.yZConstructionPlane, "mid_x", "LXMid")
    leg_fr = sp.mirror_body(leg_c, leg_fl, l_xmid, "LegFR").bodies.item(0)
    leg_fr.name = "Leg_FR"

    # ==== BACK LEGS (single profiled extrude — clean bend on ALL faces) ====
    # Sketch the side profile on the YZ plane, extrude by leg_size in X.
    # Profile: vertical bottom → bend → angled top → horizontal cap → return.
    bl_cy = ev("seat_d") - ev("leg_size") / 2
    bend_z_cm = ev("bend_z")
    rake_rad = ev("back_rake")
    cos_r = math.cos(rake_rad)
    sin_r = math.sin(rake_rad)

    yi = ev("seat_d - leg_size")  # inner face Y
    yo = ev("seat_d")              # outer face Y
    bz = bend_z_cm                 # bend Z (cm)
    h_back = ev("back_h") - bz     # backrest height above bend
    dy = h_back * sin_r            # Y shift at top due to rake
    dz = h_back * cos_r            # Z shift at top due to rake

    sk = leg_c.sketches.add(leg_c.yZConstructionPlane)
    sk.name = "LegBL_Profile_Sk"
    lines = sk.sketchCurves.sketchLines
    P3 = adsk.core.Point3D
    m2s = sk.modelToSketchSpace

    # 6-point closed profile in model space (all at X=0)
    mp = [
        P3.create(0, yi, 0),               # 0: inner bottom
        P3.create(0, yi, bz),              # 1: inner bend
        P3.create(0, yi + dy, bz + dz),   # 2: inner top
        P3.create(0, yo + dy, bz + dz),   # 3: outer top
        P3.create(0, yo, bz),              # 4: outer bend
        P3.create(0, yo, 0),               # 5: outer bottom
    ]
    sp = [m2s(p) for p in mp]

    # Draw closed profile with shared sketch points
    l0 = lines.addByTwoPoints(sp[0], sp[1])          # inner vertical
    l1 = lines.addByTwoPoints(l0.endSketchPoint, sp[2])   # inner angled
    l2 = lines.addByTwoPoints(l1.endSketchPoint, sp[3])   # top cap
    l3 = lines.addByTwoPoints(l2.endSketchPoint, sp[4])   # outer angled
    l4 = lines.addByTwoPoints(l3.endSketchPoint, sp[5])   # outer vertical
    l5 = lines.addByTwoPoints(l4.endSketchPoint, l0.startSketchPoint)  # bottom cap

    # H/V constraints (YZ plane: model Y → sketch H, model Z → sketch V)
    h_ax, v_ax = sp.probe_sketch_axes(sk)
    gc = sk.geometricConstraints
    if v_ax == "z":
        gc.addVertical(l0);  gc.addVertical(l4)   # vertical lines
        gc.addHorizontal(l2); gc.addHorizontal(l5) # horizontal caps
    else:
        gc.addHorizontal(l0); gc.addHorizontal(l4)
        gc.addVertical(l2);   gc.addVertical(l5)

    # Extrude profile by leg_size in +X
    prof = sk.profiles.item(0)
    ext_inp = leg_c.features.extrudeFeatures.createInput(
        prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ext_inp.setDistanceExtent(False, VI("leg_size"))
    bl_ext = leg_c.features.extrudeFeatures.add(ext_inp)
    bl_ext.name = "LegBL"
    leg_bl = bl_ext.bodies.item(0); leg_bl.name = "Leg_BL"

    # Fillet the 2 bend edges (inner + outer, both at Z≈bend_z running along X)
    bend_edges = adsk.core.ObjectCollection.create()
    for i in range(leg_bl.edges.count):
        edge = leg_bl.edges.item(i)
        if edge.faces.count != 2:
            continue
        g1 = edge.faces.item(0).geometry
        g2 = edge.faces.item(1).geometry
        if not (isinstance(g1, adsk.core.Plane) and isinstance(g2, adsk.core.Plane)):
            continue
        n1, n2 = g1.normal, g2.normal
        dot = max(-1.0, min(1.0, n1.x*n2.x + n1.y*n2.y + n1.z*n2.z))
        angle = math.degrees(math.acos(dot))
        if angle < 20:  # bend edges: nearly parallel normals
            bend_edges.add(edge)

    if bend_edges.count > 0:
        fil_inp = leg_c.features.filletFeatures.createInput()
        fil_inp.addConstantRadiusEdgeSet(bend_edges,
            adsk.core.ValueInput.createByString("bend_r"), True)
        leg_c.features.filletFeatures.add(fil_inp).name = "LegBL_Bend_Fil"
        print(f">>> Bend fillet: {bend_edges.count} edges")

    leg_br = sp.mirror_body(leg_c, leg_bl, l_xmid, "LegBR").bodies.item(0)
    leg_br.name = "Leg_BR"
    print(">>> Legs: 4")

    # ==== APRONS ====
    az_pl = sp.off_plane(apron_c, apron_c.xYConstructionPlane, "apron_z", "AZ_Pl")

    _, pr = sp.sketch_rect_model(apron_c, az_pl,
        ("leg_size", "0 in", "apron_z"),
        {"x": "short_apron_l", "y": "apron_thick"}, "FrontApron_Sk", ev)
    fa_ext = sp.ext_new(apron_c, pr, "apron_h", "FrontApron")
    front_apron = fa_ext.bodies.item(0); front_apron.name = "Apron_Front"

    _, pr = sp.sketch_rect_model(apron_c, az_pl,
        ("leg_size", "seat_d - apron_thick", "apron_z"),
        {"x": "short_apron_l", "y": "apron_thick"}, "BackApron_Sk", ev)
    ba_ext = sp.ext_new(apron_c, pr, "apron_h", "BackApron")
    back_apron = ba_ext.bodies.item(0); back_apron.name = "Apron_Back"

    _, pr = sp.sketch_rect_model(apron_c, az_pl,
        ("0 in", "leg_size", "apron_z"),
        {"x": "apron_thick", "y": "long_apron_l"}, "LeftApron_Sk", ev)
    la_ext = sp.ext_new(apron_c, pr, "apron_h", "LeftApron")
    left_apron = la_ext.bodies.item(0); left_apron.name = "Apron_Left"

    a_xmid = sp.off_plane(apron_c, apron_c.yZConstructionPlane, "mid_x", "AXMid")
    ra_mir = sp.mirror_feats(apron_c, [la_ext], a_xmid, "RightApronMir")
    right_apron = ra_mir.bodies.item(0); right_apron.name = "Apron_Right"
    print(">>> Aprons: 4")

    # ==== STRETCHERS (centered on legs, thicker) ====
    str_z_pl = sp.off_plane(str_c, str_c.xYConstructionPlane, "str_z", "StrZ_Pl")

    _, pr = sp.sketch_rect_model(str_c, str_z_pl,
        ("leg_size", "leg_size / 2 - str_thick / 2", "str_z"),
        {"x": "front_str_l", "y": "str_thick"}, "FrontStr_Sk", ev)
    fs_ext = sp.ext_new(str_c, pr, "str_h", "FrontStr")
    str_front = fs_ext.bodies.item(0); str_front.name = "Str_Front"

    _, pr = sp.sketch_rect_model(str_c, str_z_pl,
        ("leg_size", "seat_d - leg_size / 2 - str_thick / 2", "str_z"),
        {"x": "front_str_l", "y": "str_thick"}, "BackStr_Sk", ev)
    bs_ext = sp.ext_new(str_c, pr, "str_h", "BackStr")
    str_back = bs_ext.bodies.item(0); str_back.name = "Str_Back"

    _, pr = sp.sketch_rect_model(str_c, str_z_pl,
        ("leg_size / 2 - str_thick / 2", "leg_size", "str_z"),
        {"x": "str_thick", "y": "long_apron_l"}, "LeftStr_Sk", ev)
    ls_ext = sp.ext_new(str_c, pr, "str_h", "LeftStr")
    str_left = ls_ext.bodies.item(0); str_left.name = "Str_Left"

    s_xmid = sp.off_plane(str_c, str_c.yZConstructionPlane, "mid_x", "SXMid")
    rs_mir = sp.mirror_feats(str_c, [ls_ext], s_xmid, "RightStrMir")
    str_right = rs_mir.bodies.item(0); str_right.name = "Str_Right"
    print(">>> Stretchers: 4 (centered on legs)")

    # ==== SEAT ====
    seat_pl = sp.off_plane(seat_c, seat_c.xYConstructionPlane, "front_leg_h", "SeatPl")
    _, pr = sp.sketch_rect_model(seat_c, seat_pl,
        ("0 in", "0 in", "front_leg_h"),
        {"x": "seat_w", "y": "seat_d"}, "Seat_Sk", ev)
    seat_ext = sp.ext_new(seat_c, pr, "seat_thick", "SeatBoard")
    seat_body = seat_ext.bodies.item(0); seat_body.name = "Seat"
    print(">>> Seat: 1")

    # ==== BACK: Top rail + Bottom rail + 3 vertical slats ====
    # All built at non-raked positions, then rotated together.
    # Rails sit between posts (dominos connect them to posts).
    # Slats have stub tenons into both rails.
    back_y_pl = sp.off_plane(back_c, back_c.xZConstructionPlane,
                              "back_face_y", "BackY_Pl")

    # Top rail (between posts, offset down from top by top_rail_off)
    _, pr = sp.sketch_rect_model(back_c, back_y_pl,
        ("leg_size", "back_face_y", "back_h - top_rail_off - top_rail_h"),
        {"x": "short_apron_l", "z": "top_rail_h"}, "TopRail_Sk", ev)
    tr_ext = sp.ext_new(back_c, pr, "rail_thick", "TopRail")
    top_rail = tr_ext.bodies.item(0); top_rail.name = "TopRail"

    # Bottom rail (between posts, at bend_z)
    _, pr = sp.sketch_rect_model(back_c, back_y_pl,
        ("leg_size", "back_face_y", "bend_z"),
        {"x": "short_apron_l", "z": "bot_rail_h"}, "BotRail_Sk", ev)
    br_ext = sp.ext_new(back_c, pr, "rail_thick", "BotRail")
    bot_rail = br_ext.bodies.item(0); bot_rail.name = "BotRail"

    # Vertical slats — extend slat_tenon into each rail for stub tenon
    slat_z_expr = "bend_z + bot_rail_h - slat_tenon"
    _, pr = sp.sketch_rect_model(back_c, back_y_pl,
        ("slat_start_x - slat_w / 2", "back_face_y", slat_z_expr),
        {"x": "slat_w", "z": "slat_zone_h + 2 * slat_tenon"}, "VSlat_Sk", ev)
    vs_ext = sp.ext_new(back_c, pr, "slat_thick", "VSlat_1")
    vslat_body = vs_ext.bodies.item(0); vslat_body.name = "VSlat_1"

    n_s = int(ev("n_slats"))
    vs_pat = None
    if n_s > 1:
        vs_pat = sp.body_pattern(back_c, vslat_body, back_c.xConstructionAxis,
                                  "n_slats", "slat_pitch_x", "VSlatPat")
        for i in range(vs_pat.bodies.count):
            vs_pat.bodies.item(i).name = f"VSlat_{i+2}"

    # Rotate ALL back pieces by back_rake (same pivot as backrest posts)
    back_coll = adsk.core.ObjectCollection.create()
    back_coll.add(top_rail)
    back_coll.add(bot_rail)
    back_coll.add(vslat_body)
    if vs_pat:
        for i in range(vs_pat.bodies.count):
            back_coll.add(vs_pat.bodies.item(i))

    back_move = back_c.features.moveFeatures
    back_move_inp = back_move.createInput2(back_coll)
    back_xf = adsk.core.Matrix3D.create()
    back_xf.setCell(0, 0, 1); back_xf.setCell(0, 1, 0);      back_xf.setCell(0, 2, 0)
    back_xf.setCell(1, 0, 0); back_xf.setCell(1, 1, cos_r);   back_xf.setCell(1, 2, sin_r)
    back_xf.setCell(2, 0, 0); back_xf.setCell(2, 1, -sin_r);  back_xf.setCell(2, 2, cos_r)
    back_xf.setCell(0, 3, 0)
    back_xf.setCell(1, 3, bl_cy * (1 - cos_r) - bend_z_cm * sin_r)
    back_xf.setCell(2, 3, bl_cy * sin_r + bend_z_cm * (1 - cos_r))
    back_move_inp.defineAsFreeMove(back_xf)
    back_move.add(back_move_inp).name = "Back_Rake"

    print(f">>> Back: top rail + bottom rail + {n_s} vertical slats")

    # ==== DOMINO PLANES (shared by cross-component and domino sections) ====
    dm_fl = sp.off_plane(root, root.yZConstructionPlane, "leg_size", "DM_FL")
    dm_fr = sp.off_plane(root, root.yZConstructionPlane, "seat_w - leg_size", "DM_FR")
    dm_lf = sp.off_plane(root, root.xZConstructionPlane, "leg_size", "DM_LF")
    dm_lb = sp.off_plane(root, root.xZConstructionPlane, "seat_d - leg_size", "DM_LB")

    # ==== CROSS-COMPONENT: Seat notch, slat mortises into rails, rail dominos ====
    seat_p = seat_body.createForAssemblyContext(seat_occ)
    bl_p = leg_bl.createForAssemblyContext(leg_occ)
    br_p = leg_br.createForAssemblyContext(leg_occ)
    tr_p = top_rail.createForAssemblyContext(back_occ)
    br_rail_p = bot_rail.createForAssemblyContext(back_occ)

    # Seat notch
    sp.combine(root, seat_p, [bl_p, br_p], CUT, True, "SeatNotch")

    # Slat stub-mortises into rails
    all_slat_bodies = [vslat_body]
    if vs_pat:
        for i in range(vs_pat.bodies.count):
            all_slat_bodies.append(vs_pat.bodies.item(i))

    slat_proxies = [b.createForAssemblyContext(back_occ) for b in all_slat_bodies]
    for i, sp in enumerate(slat_proxies):
        sp.combine(root, tr_p, [sp], CUT, True, f"SlatMort_TR_{i}")
        sp.combine(root, br_rail_p, [sp], CUT, True, f"SlatMort_BR_{i}")

    # Rail-to-post TILTED dominos (aligned with backrest cross-section)
    # Build manually: sketch tilted rectangle on dm_fl/dm_fr, extrude in X
    def rotated_yz(z_pre):
        dz = z_pre - bend_z_cm
        return (bl_cy + sin_r * dz, bend_z_cm + cos_r * dz)

    def tilted_rail_domino(plane, center_x, rail_z_center, rail_body, leg_body, name):
        """Create a domino tilted by back_rake at the rail-to-post interface."""
        y_rot, z_rot = rotated_yz(rail_z_center)
        dm_w_cm = ev("dm_w")
        dm_t_cm = ev("dm_t")
        half_l = dm_w_cm / 2
        half_s = dm_t_cm / 2
        # Long direction: tilted by back_rake in YZ plane
        dy_l = half_l * sin_r;  dz_l = half_l * cos_r
        # Short direction: perpendicular to long in YZ plane
        dy_s = half_s * cos_r;  dz_s = -half_s * sin_r
        # 4 corners in model space
        P3 = adsk.core.Point3D
        corners = [
            P3.create(center_x, y_rot + dy_l + dy_s, z_rot + dz_l + dz_s),
            P3.create(center_x, y_rot + dy_l - dy_s, z_rot + dz_l - dz_s),
            P3.create(center_x, y_rot - dy_l - dy_s, z_rot - dz_l - dz_s),
            P3.create(center_x, y_rot - dy_l + dy_s, z_rot - dz_l + dz_s),
        ]
        sk = root.sketches.add(plane)
        sk.name = f"{name}_Sk"
        m2s = sk.modelToSketchSpace
        sp = [m2s(p) for p in corners]
        lines = sk.sketchCurves.sketchLines
        l0 = lines.addByTwoPoints(sp[0], sp[1])
        l1 = lines.addByTwoPoints(l0.endSketchPoint, sp[2])
        l2 = lines.addByTwoPoints(l1.endSketchPoint, sp[3])
        l3 = lines.addByTwoPoints(l2.endSketchPoint, l0.startSketchPoint)
        prof = sk.profiles.item(0)
        ext_inp = root.features.extrudeFeatures.createInput(
            prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        ext_inp.setSymmetricExtent(VI("dm_d"), False)
        ext = root.features.extrudeFeatures.add(ext_inp)
        ext.name = name
        dm_body = ext.bodies.item(0); dm_body.name = name
        sp.combine(root, rail_body, [dm_body], CUT, True, f"{name}_CutRail")
        sp.combine(root, leg_body, [dm_body], CUT, True, f"{name}_CutLeg")
        sk.isVisible = False
        return dm_body

    z_tr = ev("back_h") - ev("top_rail_off") - ev("top_rail_h") / 2
    z_br = ev("bend_z") + ev("bot_rail_h") / 2
    lx = ev("leg_size")
    rx = ev("seat_w - leg_size")

    tilted_rail_domino(dm_fl, lx, z_tr, tr_p, bl_p, "DM_TR_L")
    tilted_rail_domino(dm_fr, rx, z_tr, tr_p, br_p, "DM_TR_R")
    tilted_rail_domino(dm_fl, lx, z_br, br_rail_p, bl_p, "DM_BR_L")
    tilted_rail_domino(dm_fr, rx, z_br, br_rail_p, br_p, "DM_BR_R")

    print(">>> Cross-component: seat notch, slat mortises, 4 tilted rail dominos")

    # ==== DOMINO JOINERY ====
    params.add("dm_count", VI("2"), "", "")
    params.add("dm_sp", VI("apron_h / (dm_count + 1)"), "in", "")
    params.add("dm_z_start", VI("apron_z + apron_h / (dm_count + 1)"), "in", "")

    fl_p = leg_fl.createForAssemblyContext(leg_occ)
    fr_p = leg_fr.createForAssemblyContext(leg_occ)
    fa_p = front_apron.createForAssemblyContext(apron_occ)
    ba_p = back_apron.createForAssemblyContext(apron_occ)
    la_p = left_apron.createForAssemblyContext(apron_occ)
    ra_p = right_apron.createForAssemblyContext(apron_occ)
    fs_p = str_front.createForAssemblyContext(str_occ)
    bs_p = str_back.createForAssemblyContext(str_occ)
    ls_p = str_left.createForAssemblyContext(str_occ)
    rs_p = str_right.createForAssemblyContext(str_occ)

    # Apron dominos (8 joints)
    domino.grid(root, dm_fl, ("leg_size", "apron_thick/2", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        fa_p, fl_p, "DM_FA_L", ev)
    domino.grid(root, dm_fr, ("seat_w - leg_size", "apron_thick/2", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        fa_p, fr_p, "DM_FA_R", ev)
    domino.grid(root, dm_fl, ("leg_size", "seat_d - apron_thick/2", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        ba_p, bl_p, "DM_BA_L", ev)
    domino.grid(root, dm_fr, ("seat_w - leg_size", "seat_d - apron_thick/2", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        ba_p, br_p, "DM_BA_R", ev)
    domino.grid(root, dm_lf, ("apron_thick/2", "leg_size", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        la_p, fl_p, "DM_LA_F", ev)
    domino.grid(root, dm_lb, ("apron_thick/2", "seat_d - leg_size", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        la_p, bl_p, "DM_LA_B", ev)
    domino.grid(root, dm_lf, ("seat_w - apron_thick/2", "leg_size", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        ra_p, fr_p, "DM_RA_F", ev)
    domino.grid(root, dm_lb, ("seat_w - apron_thick/2", "seat_d - leg_size", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        ra_p, br_p, "DM_RA_B", ev)

    # Stretcher dominos (8 joints, 1 each — centered Y/X positions)
    domino.grid(root, dm_fl, ("leg_size", "leg_size / 2", "str_dm_z"),
        "z", "0 in", "1", "z", "dm_w", "dm_t", "dm_d",
        fs_p, fl_p, "DM_FS_L", ev)
    domino.grid(root, dm_fr, ("seat_w - leg_size", "leg_size / 2", "str_dm_z"),
        "z", "0 in", "1", "z", "dm_w", "dm_t", "dm_d",
        fs_p, fr_p, "DM_FS_R", ev)
    domino.grid(root, dm_fl, ("leg_size", "seat_d - leg_size / 2", "str_dm_z"),
        "z", "0 in", "1", "z", "dm_w", "dm_t", "dm_d",
        bs_p, bl_p, "DM_BS_L", ev)
    domino.grid(root, dm_fr, ("seat_w - leg_size", "seat_d - leg_size / 2", "str_dm_z"),
        "z", "0 in", "1", "z", "dm_w", "dm_t", "dm_d",
        bs_p, br_p, "DM_BS_R", ev)
    domino.grid(root, dm_lf, ("leg_size / 2", "leg_size", "str_dm_z"),
        "z", "0 in", "1", "z", "dm_w", "dm_t", "dm_d",
        ls_p, fl_p, "DM_LS_F", ev)
    domino.grid(root, dm_lb, ("leg_size / 2", "seat_d - leg_size", "str_dm_z"),
        "z", "0 in", "1", "z", "dm_w", "dm_t", "dm_d",
        ls_p, bl_p, "DM_LS_B", ev)
    domino.grid(root, dm_lf, ("seat_w - leg_size / 2", "leg_size", "str_dm_z"),
        "z", "0 in", "1", "z", "dm_w", "dm_t", "dm_d",
        rs_p, fr_p, "DM_RS_F", ev)
    domino.grid(root, dm_lb, ("seat_w - leg_size / 2", "seat_d - leg_size", "str_dm_z"),
        "z", "0 in", "1", "z", "dm_w", "dm_t", "dm_d",
        rs_p, br_p, "DM_RS_B", ev)

    print(">>> Dominos: 16 joints (aprons + stretchers)")

    # ==== DETAILS: Leg chamfers + Seat fillet ====
    chamfer_size = ev("leg_chamfer")
    if chamfer_size > 0:
        # Chamfer bottom edges of all legs
        for body_name, comp in [("Leg_FL", leg_c), ("Leg_FR", leg_c),
                                 ("Leg_BL", leg_c), ("Leg_BR", leg_c)]:
            body = None
            for bi in range(comp.bRepBodies.count):
                if comp.bRepBodies.item(bi).name == body_name:
                    body = comp.bRepBodies.item(bi)
                    break
            if not body:
                continue
            bot_edges = adsk.core.ObjectCollection.create()
            for ei in range(body.edges.count):
                edge = body.edges.item(ei)
                sv = edge.startVertex.geometry
                ev_p = edge.endVertex.geometry
                if sv.z < 0.1 and ev_p.z < 0.1:
                    bot_edges.add(edge)
            if bot_edges.count > 0:
                ch_inp = comp.features.chamferFeatures.createInput2()
                ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                    bot_edges, adsk.core.ValueInput.createByString("leg_chamfer"), True)
                comp.features.chamferFeatures.add(ch_inp).name = f"{body_name}_BotCh"

        print(">>> Leg bottom chamfers applied")

    # Seat top edge fillet
    seat_fil_r = ev("seat_fillet")
    if seat_fil_r > 0:
        seat_z_top = ev("seat_h")
        top_edges = adsk.core.ObjectCollection.create()
        for ei in range(seat_body.edges.count):
            edge = seat_body.edges.item(ei)
            sv = edge.startVertex.geometry
            ev_p = edge.endVertex.geometry
            if sv.z > seat_z_top - 0.1 and ev_p.z > seat_z_top - 0.1:
                top_edges.add(edge)
        if top_edges.count > 0:
            fil_inp = seat_c.features.filletFeatures.createInput()
            fil_inp.addConstantRadiusEdgeSet(top_edges,
                adsk.core.ValueInput.createByString("seat_fillet"), True)
            seat_c.features.filletFeatures.add(fil_inp).name = "Seat_TopFil"
            print(">>> Seat top edge fillet applied")

    # ==== EPILOGUE ====
    for comp in [leg_c, apron_c, str_c, seat_c, back_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False
    for sk in root.sketches:
        sk.isVisible = False
    for cp in root.constructionPlanes:
        cp.isLightBulbOn = False

    for cn, c in [("Legs", leg_c), ("Aprons", apron_c), ("Stretchers", str_c),
                   ("Seat", seat_c), ("Back", back_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{cn}: {len(names)} -> {names}")
    print(f"Root: {root.bRepBodies.count} voids")

    sp.apply_appearance("white oak")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
