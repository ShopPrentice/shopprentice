"""
Shaker Blanket Chest / Toy Box
==============================
36"W x 20"D x 24"H, 3/4" board stock.
Through dovetail case corners, dovetailed drawer at bottom,
bracket feet with arched cutouts, hinged lid with breadboard battens,
plywood back panel.

Coordinate system:
  X = width (36")   Y = depth (20")   Z = height (24")

Components:
  Case   — Front, Back, Side_Left, Side_Right (through dovetails)
  Bottom — Divider board between chest and drawer
  Feet   — Front, Back, Left, Right bracket boards with arch cutouts
  Drawer — Dovetailed drawer box (via template)
  Lid    — Solid panel + 2 breadboard battens
  BackPn — Plywood back panel (rabbeted in)
"""
import adsk.core, adsk.fusion, math

from helpers import sp
from woodworking.templates import dovetailed_drawer


CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation


def find_body(name, comp=None):
    c = comp or _root_comp
    for i in range(c.bRepBodies.count):
        if c.bRepBodies.item(i).name == name:
            return c.bRepBodies.item(i)
    for j in range(c.occurrences.count):
        r = find_body(name, c.occurrences.item(j).component)
        if r:
            return r
    return None


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    global _root_comp
    _root_comp = root
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    # ==============================================================
    #  PARAMETERS
    # ==============================================================
    for pname, expr, unit in [
        # Case envelope
        ("case_w",        "36 in",    "in"),
        ("case_d",        "20 in",    "in"),
        ("case_h",        "24 in",    "in"),
        ("board_thick",   "0.75 in",  "in"),
        ("back_thick",    "0.25 in",  "in"),
        # Bottom divider
        ("bottom_thick",  "0.5 in",   "in"),
        ("bottom_dado_d", "0.25 in",  "in"),
        # Feet
        ("foot_h",        "4 in",     "in"),
        ("foot_thick",    "0.75 in",  "in"),
        ("arch_h",        "2.5 in",   "in"),
        ("arch_inset",    "1.5 in",   "in"),
        # Lid
        ("lid_thick",     "0.75 in",  "in"),
        ("lid_overhang",  "0.25 in",  "in"),
        ("batten_w",      "2 in",     "in"),
        ("batten_thick",  "0.75 in",  "in"),
        ("batten_inset",  "3 in",     "in"),
        # Drawer
        ("drawer_h",      "4 in",     "in"),
        ("drawer_gap",    "0.0625 in","in"),
        # Case dovetails
        ("dt_angle",      "8 deg",    "deg"),
        ("dt_tail_w",     "1.25 in",  "in"),
        ("dt_tail_count", "4",        ""),
    ]:
        params.add(pname, VI(expr), unit, "")

    for pname, expr, unit in [
        # Derived
        ("inner_w",       "case_w - 2 * board_thick",                        "in"),
        ("inner_d",       "case_d - 2 * board_thick",                        "in"),
        ("drawer_z",      "foot_h",                                          "in"),
        ("bottom_z",      "foot_h + drawer_h",                               "in"),
        ("chest_h",       "case_h - foot_h - drawer_h - bottom_thick - lid_thick", "in"),
        ("mid_x",         "case_w / 2",                                      "in"),
        ("mid_y",         "case_d / 2",                                      "in"),
        # Case dovetail derived
        ("dt_pin_w",      "case_d / dt_tail_count - dt_tail_w",              "in"),
        ("dt_pitch",      "case_d / dt_tail_count",                          "in"),
        ("dt_narrow_w",   "dt_tail_w - 2 * board_thick * tan(dt_angle)",     "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    # Drawer template params
    dovetailed_drawer.define_params(params, prefix="dd",
        drawer_w="inner_w - 2 * drawer_gap",
        drawer_d="case_d - back_thick - 2 * drawer_gap",
        drawer_h="drawer_h - 2 * drawer_gap",
        front_thick="0.75 in", side_thick="0.5 in",
        bottom_thick="0.25 in",
        bg_depth="0.25 in", bg_up="0.25 in",
        dt_angle="8 deg", dt_tail_w="0.625 in",
        front_tail_count="3", back_tail_count="3",
        x_offset="board_thick + drawer_gap",
        z_offset="foot_h + drawer_gap")

    print(">>> Parameters done")

    # ==============================================================
    #  COMPONENTS
    # ==============================================================
    case_occ   = sp.make_comp(root, "Case")
    bottom_occ = sp.make_comp(root, "Bottom")
    feet_occ   = sp.make_comp(root, "Feet")
    drawer_occ = sp.make_comp(root, "Drawer")
    lid_occ    = sp.make_comp(root, "Lid")
    back_occ   = sp.make_comp(root, "BackPanel")

    case_c   = case_occ.component
    bottom_c = bottom_occ.component
    feet_c   = feet_occ.component
    drawer_c = drawer_occ.component
    lid_c    = lid_occ.component
    back_c   = back_occ.component

    # ==============================================================
    #  1. CASE — Front, Back, Side_Left, Side_Right
    # ==============================================================
    # Front board: X=0..case_w, Z=foot_h..case_h-lid_thick
    case_z_pl = sp.off_plane(case_c, case_c.xYConstructionPlane,
                              "foot_h", "Case_Z_Pl")
    _, pr = sp.sketch_rect_model(case_c, case_c.xZConstructionPlane,
        ("0 in", "0 in", "foot_h"),
        {"x": "case_w", "z": "case_h - foot_h - lid_thick"},
        "Front_Sk", ev)
    front_ext = sp.ext_new(case_c, pr, "board_thick", "FrontBoard")
    front = front_ext.bodies.item(0)
    front.name = "Front"

    # Body-relative reference: Back depends on Front
    ref_front = find_body("Front")
    ref_front_bb = ref_front.boundingBox

    # Back board
    back_pl = sp.off_plane(case_c, case_c.xZConstructionPlane,
                            "case_d - board_thick", "Back_Pl")
    _, pr = sp.sketch_rect_model(case_c, back_pl,
        ("0 in", "case_d - board_thick", "foot_h"),
        {"x": "case_w", "z": "case_h - foot_h - lid_thick"},
        "Back_Sk", ev)
    back_ext = sp.ext_new(case_c, pr, "board_thick", "BackBoard")
    back = back_ext.bodies.item(0)
    back.name = "Back"

    # Midplanes for mirror
    x_mid = sp.off_plane(case_c, case_c.yZConstructionPlane, "mid_x", "XMid")
    y_mid = sp.off_plane(case_c, case_c.xZConstructionPlane, "mid_y", "YMid")

    # Body-relative reference: Side_Left depends on Front
    ref_front2 = find_body("Front")
    ref_front2_bb = ref_front2.boundingBox

    # Left side: Y=board_thick..case_d-board_thick, Z=foot_h..case_h-lid_thick
    left_yz = sp.off_plane(case_c, case_c.yZConstructionPlane,
                            "0 in", "Left_Pl")
    _, pr = sp.sketch_rect_model(case_c, case_c.yZConstructionPlane,
        ("0 in", "board_thick", "foot_h"),
        {"y": "inner_d", "z": "case_h - foot_h - lid_thick"},
        "LeftSide_Sk", ev)
    left_ext = sp.ext_new(case_c, pr, "board_thick", "LeftSide")
    left = left_ext.bodies.item(0)
    left.name = "Side_Left"

    # Body-relative reference: Side_Right depends on Side_Left
    ref_side_left = find_body("Side_Left")
    ref_side_left_bb = ref_side_left.boundingBox

    # Right side: mirror left across XMid
    right_mir = sp.mirror_feats(case_c, [left_ext], x_mid, "RightMir")
    right = right_mir.bodies.item(0)
    right.name = "Side_Right"

    print(">>> Case: 4 boards done")

    # ==============================================================
    #  2. BOTTOM — divider board between chest and drawer
    # ==============================================================
    # Body-relative reference: Bottom depends on Front
    ref_front3 = find_body("Front")
    ref_front3_bb = ref_front3.boundingBox

    bot_pl = sp.off_plane(bottom_c, bottom_c.xYConstructionPlane,
                           "bottom_z", "Bot_Pl")
    _, pr = sp.sketch_rect_model(bottom_c, bot_pl,
        ("board_thick - bottom_dado_d", "board_thick - bottom_dado_d", "bottom_z"),
        {"x": "inner_w + 2 * bottom_dado_d",
         "y": "inner_d + 2 * bottom_dado_d"},
        "Bottom_Sk", ev)
    bot_ext = sp.ext_new(bottom_c, pr, "bottom_thick", "BottomBoard")
    bot_body = bot_ext.bodies.item(0)
    bot_body.name = "Bottom"

    # Bottom dado CUTs into case boards (cross-component, in root)
    front_proxy = front.createForAssemblyContext(case_occ)
    back_proxy = back.createForAssemblyContext(case_occ)
    left_proxy = left.createForAssemblyContext(case_occ)
    right_proxy = right.createForAssemblyContext(case_occ)
    bot_proxy = bot_body.createForAssemblyContext(bottom_occ)

    sp.combine(front_proxy, [bot_proxy], CUT, True, "BotDado_F")
    sp.combine(back_proxy, [bot_proxy], CUT, True, "BotDado_B")
    sp.combine(left_proxy, [bot_proxy], CUT, True, "BotDado_L")
    sp.combine(right_proxy, [bot_proxy], CUT, True, "BotDado_R")

    print(">>> Bottom + dados done")

    # ==============================================================
    #  3. FEET — bracket feet with arch cutouts
    #     Front + back: full width, foot_thick deep
    #     Left + right: inner_d long, foot_thick deep
    #     All foot_h tall with arch CUT
    # ==============================================================
    # Body-relative reference: Foot_Front depends on Front
    ref_front4 = find_body("Front")
    ref_front4_bb = ref_front4.boundingBox

    # Front foot board
    _, pr = sp.sketch_rect_model(feet_c, feet_c.xZConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "case_w", "z": "foot_h"},
        "FootFront_Sk", ev)
    ff_ext = sp.ext_new(feet_c, pr, "foot_thick", "FootFront")
    foot_front = ff_ext.bodies.item(0)
    foot_front.name = "Foot_Front"

    # Body-relative reference: Foot_Back depends on Foot_Front
    ref_foot_front = find_body("Foot_Front")
    ref_foot_front_bb = ref_foot_front.boundingBox

    # Back foot board
    ff_back_pl = sp.off_plane(feet_c, feet_c.xZConstructionPlane,
                               "case_d - foot_thick", "FootBack_Pl")
    _, pr = sp.sketch_rect_model(feet_c, ff_back_pl,
        ("0 in", "case_d - foot_thick", "0 in"),
        {"x": "case_w", "z": "foot_h"},
        "FootBack_Sk", ev)
    fb_ext = sp.ext_new(feet_c, pr, "foot_thick", "FootBack")
    foot_back = fb_ext.bodies.item(0)
    foot_back.name = "Foot_Back"

    # Body-relative reference: Foot_Left depends on Foot_Front
    ref_foot_front2 = find_body("Foot_Front")
    ref_foot_front2_bb = ref_foot_front2.boundingBox

    # Left foot board (between front and back foot boards)
    _, pr = sp.sketch_rect_model(feet_c, feet_c.yZConstructionPlane,
        ("0 in", "foot_thick", "0 in"),
        {"y": "case_d - 2 * foot_thick", "z": "foot_h"},
        "FootLeft_Sk", ev)
    fl_ext = sp.ext_new(feet_c, pr, "foot_thick", "FootLeft")
    foot_left = fl_ext.bodies.item(0)
    foot_left.name = "Foot_Left"

    # Body-relative reference: Foot_Right depends on Foot_Left
    ref_foot_left = find_body("Foot_Left")
    ref_foot_left_bb = ref_foot_left.boundingBox

    # Right foot: mirror across XMid
    f_xmid = sp.off_plane(feet_c, feet_c.yZConstructionPlane, "mid_x", "FXMid")
    fr_mir = sp.mirror_feats(feet_c, [fl_ext], f_xmid, "FootRightMir")
    foot_right = fr_mir.bodies.item(0)
    foot_right.name = "Foot_Right"

    # Arch cutouts — use construction planes (not body faces) so each
    # arch can target its own body without mirror issues
    Point3D = adsk.core.Point3D
    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
    ai = ev("arch_inset")
    cw = ev("case_w")
    ah = ev("arch_h")
    ft = ev("foot_thick")
    cd = ev("case_d")

    def make_arch(plane, body, left_expr, width_expr, height_expr,
                  left_val, width_val, height_val, name):
        """Create an arch cutout on an XZ or YZ construction plane."""
        sk = feet_c.sketches.add(plane)
        sk.name = f"{name}_Sk"
        ha, va = sp.probe_sketch_axes(sk)
        # The arch baseline is along the H axis, arch rises along V
        # Convert model points to sketch space
        m = sk.modelToSketchSpace
        # We need the plane's normal axis to figure out model coords
        # For XZ planes: H=X, V=Z. For YZ planes: H varies.
        # Use approximate positions and let dimensions correct
        p1 = Point3D.create(left_val, 0, 0)
        p2 = Point3D.create(left_val + width_val, 0, 0)
        p3 = Point3D.create(left_val + width_val / 2, height_val, 0)

        baseline = sk.sketchCurves.sketchLines.addByTwoPoints(p1, p2)
        arc = sk.sketchCurves.sketchArcs.addByThreePoints(
            baseline.startSketchPoint, p3, baseline.endSketchPoint)

        d = sk.sketchDimensions
        d.addDistanceDimension(baseline.startSketchPoint, baseline.endSketchPoint,
            H, Point3D.create(left_val + width_val / 2, -1, 0)
        ).parameter.expression = width_expr
        d.addDistanceDimension(baseline.startSketchPoint, arc.centerSketchPoint,
            V, Point3D.create(left_val - 1, height_val / 2, 0)
        ).parameter.expression = height_expr
        d.addDistanceDimension(sk.originPoint, baseline.startSketchPoint,
            H, Point3D.create(left_val / 2, -1, 0)
        ).parameter.expression = left_expr

        prof = sp.smallest_profile(sk)
        return sp.ext_op(feet_c, prof, "foot_thick", CUT, body, name, flip=True)

    # Front arch — on XZ plane at Y=0
    make_arch(feet_c.xZConstructionPlane, foot_front,
              "arch_inset", "case_w - 2 * arch_inset", "arch_h",
              ai, cw - 2 * ai, ah, "FrontArch")

    # Back arch — on XZ plane offset to Y=case_d-foot_thick
    back_arch_pl = sp.off_plane(feet_c, feet_c.xZConstructionPlane,
                                 "case_d - foot_thick", "BackArch_Pl")
    make_arch(back_arch_pl, foot_back,
              "arch_inset", "case_w - 2 * arch_inset", "arch_h",
              ai, cw - 2 * ai, ah, "BackArch")

    # Left arch — on YZ plane at X=0
    make_arch(feet_c.yZConstructionPlane, foot_left,
              "foot_thick + arch_inset",
              "case_d - 2 * foot_thick - 2 * arch_inset", "arch_h",
              ft + ai, cd - 2 * ft - 2 * ai, ah, "LeftArch")

    # Right arch — on YZ plane offset to X=case_w-foot_thick
    right_arch_pl = sp.off_plane(feet_c, feet_c.yZConstructionPlane,
                                  "case_w - foot_thick", "RightArch_Pl")
    make_arch(right_arch_pl, foot_right,
              "foot_thick + arch_inset",
              "case_d - 2 * foot_thick - 2 * arch_inset", "arch_h",
              ft + ai, cd - 2 * ft - 2 * ai, ah, "RightArch")

    print(">>> Feet: 4 bracket feet with arches done")

    # ==============================================================
    #  4. DRAWER — dovetailed drawer box (via template)
    # ==============================================================
    # Body-relative reference: dd_Front depends on Bottom
    ref_bottom = find_body("Bottom")
    ref_bottom_bb = ref_bottom.boundingBox

    dd_result = dovetailed_drawer.build(drawer_c, prefix="dd", ev=ev)
    print(">>> Drawer: dovetailed drawer done (%d bodies)" % len(dd_result["all_bodies"]))

    # Body-relative references for drawer sub-bodies
    ref_dd_front = find_body("dd_Front")
    ref_dd_front_bb = ref_dd_front.boundingBox
    ref_dd_left = find_body("dd_Left")
    ref_dd_left_bb = ref_dd_left.boundingBox

    # ==============================================================
    #  5. LID — solid panel + 2 breadboard battens
    # ==============================================================
    # Body-relative reference: Lid depends on Front
    ref_front5 = find_body("Front")
    ref_front5_bb = ref_front5.boundingBox

    lid_z_pl = sp.off_plane(lid_c, lid_c.xYConstructionPlane,
                             "case_h - lid_thick", "Lid_Pl")
    _, pr = sp.sketch_rect_model(lid_c, lid_z_pl,
        ("-lid_overhang", "-lid_overhang", "case_h - lid_thick"),
        {"x": "case_w + 2 * lid_overhang",
         "y": "case_d + lid_overhang"},
        "Lid_Sk", ev)
    lid_ext = sp.ext_new(lid_c, pr, "lid_thick", "LidPanel")
    lid_body = lid_ext.bodies.item(0)
    lid_body.name = "Lid"

    # Body-relative reference: Batten_Left depends on Lid
    ref_lid = find_body("Lid")
    ref_lid_bb = ref_lid.boundingBox

    # Breadboard battens on underside — 2 battens running across Y (depth)
    # positioned at batten_inset from each end
    bat_z_pl = sp.off_plane(lid_c, lid_c.xYConstructionPlane,
                             "case_h - lid_thick - batten_thick", "Batten_Pl")
    _, pr = sp.sketch_rect_model(lid_c, bat_z_pl,
        ("batten_inset", "0 in", "case_h - lid_thick - batten_thick"),
        {"x": "batten_w", "y": "case_d - board_thick"},
        "BattenL_Sk", ev)
    bat_l_ext = sp.ext_new(lid_c, pr, "batten_thick", "BattenL")
    batten_l = bat_l_ext.bodies.item(0)
    batten_l.name = "Batten_Left"

    # Body-relative reference: Batten_Right depends on Batten_Left
    ref_batten_left = find_body("Batten_Left")
    ref_batten_left_bb = ref_batten_left.boundingBox

    # Mirror left batten to right
    lid_xmid = sp.off_plane(lid_c, lid_c.yZConstructionPlane, "mid_x", "LidXMid")
    bat_mir = sp.mirror_feats(lid_c, [bat_l_ext], lid_xmid, "BattenRightMir")
    batten_r = bat_mir.bodies.item(0)
    batten_r.name = "Batten_Right"

    print(">>> Lid: panel + 2 battens done")

    # ==============================================================
    #  6. BACK PANEL — plywood, rabbeted into sides
    # ==============================================================
    # Body-relative references: BackPanel depends on Back and Side_Left
    ref_back = find_body("Back")
    ref_back_bb = ref_back.boundingBox
    ref_side_left2 = find_body("Side_Left")
    ref_side_left2_bb = ref_side_left2.boundingBox

    _, pr = sp.sketch_rect_model(back_c, back_c.xZConstructionPlane,
        ("board_thick", "case_d - back_thick", "foot_h"),
        {"x": "inner_w", "z": "case_h - foot_h - lid_thick"},
        "BackPanel_Sk", ev)
    bp_ext = sp.ext_new(back_c, pr, "back_thick", "BackPanelBoard")
    back_panel = bp_ext.bodies.item(0)
    back_panel.name = "BackPanel"

    # Rabbet CUTs in sides for back panel (cross-component)
    bp_proxy = back_panel.createForAssemblyContext(back_occ)

    # Left side rabbet
    rab_l_pl = sp.off_plane(root, root.yZConstructionPlane, "0 in", "RabL_Pl")
    _, pr = sp.sketch_rect_model(root, rab_l_pl,
        ("0 in", "case_d - back_thick", "foot_h"),
        {"y": "back_thick", "z": "case_h - foot_h - lid_thick"},
        "RabL_Sk", ev)
    rab_l_tool = sp.ext_new(root, pr, "board_thick", "RabL_Tool")
    sp.combine(left_proxy, [rab_l_tool.bodies.item(0)], CUT, False, "RabL_Cut")

    # Right side rabbet
    rab_r_pl = sp.off_plane(root, root.yZConstructionPlane,
                             "case_w - board_thick", "RabR_Pl")
    _, pr = sp.sketch_rect_model(root, rab_r_pl,
        ("case_w - board_thick", "case_d - back_thick", "foot_h"),
        {"y": "back_thick", "z": "case_h - foot_h - lid_thick"},
        "RabR_Sk", ev)
    rab_r_tool = sp.ext_new(root, pr, "board_thick", "RabR_Tool")
    sp.combine(right_proxy, [rab_r_tool.bodies.item(0)], CUT, False, "RabR_Cut")

    print(">>> Back panel + rabbets done")

    # ==============================================================
    #  7. CASE DOVETAILS — through dovetails at 4 corners
    #     Sides = tail boards, Front/Back = pin boards
    #     Tails run along Z (height), sketched on YZ planes.
    #     Pattern along Z by dt_pitch.
    # ==============================================================
    # Recompute derived params for case height range
    # Case boards span Z = foot_h .. case_h - lid_thick
    # Dovetails: dt_tail_count tails evenly spaced along this height
    # Need to update derived params to use case board height, not case_d
    # Actually dt_pin_w etc already reference case_d — need to fix for Z.
    # Let's add case-specific dovetail derived params:
    params.add("case_board_h",
               VI("case_h - foot_h - lid_thick"), "in", "")
    params.add("dt_pin_w_z",
               VI("case_board_h / dt_tail_count - dt_tail_w"), "in", "")
    params.add("dt_pitch_z",
               VI("case_board_h / dt_tail_count"), "in", "")
    params.add("dt_narrow_w_z",
               VI("dt_tail_w - 2 * board_thick * tan(dt_angle)"), "in", "")

    bt = ev("board_thick")
    bw = ev("case_d")
    hp = ev("dt_pin_w_z") / 2
    tw = ev("dt_tail_w")
    delta = bt * math.tan(ev("dt_angle"))
    fz = ev("foot_h")
    cw = ev("case_w")

    # YZ planes for left and right corners
    dt_left_pl = root.yZConstructionPlane  # X=0
    dt_right_pl = sp.off_plane(root, root.yZConstructionPlane,
                                "case_w - board_thick", "DT_Right_Pl")

    def dt_corner(plane, mx, yw, yn, y_wide_expr, cut_body, join_body, name):
        """One dovetail corner on a YZ plane. Tails along Z."""
        sk = root.sketches.add(plane)
        sk.name = f"{name}_Sk"
        ha, va = sp.probe_sketch_axes(sk)
        of = lambda a: H if a == ha else V
        m = sk.modelToSketchSpace

        # Trapezoid: wide face at yw, narrow at yn, starting at fz + hp
        s1 = m(Point3D.create(mx, yw, fz + hp))
        s2 = m(Point3D.create(mx, yw, fz + hp + tw))
        s3 = m(Point3D.create(mx, yn, fz + hp + tw - delta))
        s4 = m(Point3D.create(mx, yn, fz + hp + delta))

        ln = sk.sketchCurves.sketchLines
        l_short = ln.addByTwoPoints(Point3D.create(s4.x, s4.y, 0),
                                    Point3D.create(s3.x, s3.y, 0))
        l_back = ln.addByTwoPoints(l_short.endSketchPoint,
                                   Point3D.create(s2.x, s2.y, 0))
        l_wide = ln.addByTwoPoints(l_back.endSketchPoint,
                                   Point3D.create(s1.x, s1.y, 0))
        l_front = ln.addByTwoPoints(l_wide.endSketchPoint,
                                    l_short.startSketchPoint)

        if va == "z":
            sk.geometricConstraints.addVertical(l_short)
            sk.geometricConstraints.addVertical(l_wide)
        else:
            sk.geometricConstraints.addHorizontal(l_short)
            sk.geometricConstraints.addHorizontal(l_wide)

        dd = sk.sketchDimensions

        dd.addDistanceDimension(l_short.startSketchPoint, l_short.endSketchPoint,
            of("z"), Point3D.create(s3.x + (1 if of("z") == V else 0),
                                     s3.y + (0 if of("z") == V else 1), 0)
        ).parameter.expression = "dt_narrow_w_z"
        dd.addDistanceDimension(l_short.startSketchPoint, l_wide.endSketchPoint,
            of("y"), Point3D.create((s1.x + s4.x) / 2,
                                     (s1.y + s4.y) / 2 + (-1 if of("y") == V else 0), 0)
        ).parameter.expression = "board_thick"
        dd.addDistanceDimension(sk.originPoint, l_short.startSketchPoint,
            of("z"), Point3D.create(s4.x + (2 if of("z") == V else 0),
                                     s4.y / 2, 0)
        ).parameter.expression = "foot_h + dt_pin_w_z / 2 + board_thick * tan(dt_angle)"
        short_y_expr = (f"{y_wide_expr} + board_thick"
                        if yn >= yw else f"{y_wide_expr} - board_thick")
        dd.addDistanceDimension(sk.originPoint, l_short.startSketchPoint,
            of("y"), Point3D.create(s1.x / 2,
                                     s1.y + (-2 if of("y") == V else 0), 0)
        ).parameter.expression = short_y_expr
        dd.addAngularDimension(
            l_front, l_short,
            Point3D.create((s1.x + s4.x) / 2, (s1.y + s4.y) / 2, 0)
        ).parameter.expression = "90 deg - dt_angle"

        prof = sk.profiles.item(0)

        # Tail as NewBody, pattern along Z, then bulk CUT + JOIN
        tail_ext = sp.ext_new(root, prof, "board_thick", f"{name}_Tail")
        tail_body = tail_ext.bodies.item(0)
        tail_body.name = name

        coll = adsk.core.ObjectCollection.create()
        coll.add(tail_ext)
        pat = root.features.rectangularPatternFeatures.createInput(
            coll, root.zConstructionAxis,
            VI("dt_tail_count"), VI("dt_pitch_z"),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        pat_feat = root.features.rectangularPatternFeatures.add(pat)
        pat_feat.name = f"{name}_Pat"

        all_tails = [tail_body] + [pat_feat.bodies.item(i)
                                    for i in range(pat_feat.bodies.count)]
        sp.combine(cut_body, all_tails, CUT, True, f"{name}_CutPin")
        sp.combine(join_body, all_tails, JOIN, False, f"{name}_JoinSide")

    # 4 corners: FL (front-left), BL (back-left), FR (front-right), BR (back-right)
    dt_corner(dt_left_pl, 0, 0, bt, "0 in",
              front_proxy, left_proxy, "DT_FL")
    dt_corner(dt_left_pl, 0, bw, bw - bt, "case_d",
              back_proxy, left_proxy, "DT_BL")
    dt_corner(dt_right_pl, ev("case_w - board_thick"), 0, bt, "0 in",
              front_proxy, right_proxy, "DT_FR")
    dt_corner(dt_right_pl, ev("case_w - board_thick"), bw, bw - bt, "case_d",
              back_proxy, right_proxy, "DT_BR")

    print(">>> Case dovetails done")

    # ==============================================================
    #  EPILOGUE
    # ==============================================================
    all_comps = [case_c, bottom_c, feet_c, drawer_c, lid_c, back_c]
    for comp in all_comps:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False
        for ca in comp.constructionAxes:
            ca.isLightBulbOn = False
    for sk in root.sketches:
        sk.isVisible = False
    for cp in root.constructionPlanes:
        cp.isLightBulbOn = False

    for comp_name, c in [("Case", case_c), ("Bottom", bottom_c),
                          ("Feet", feet_c), ("Drawer", drawer_c),
                          ("Lid", lid_c), ("BackPanel", back_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{comp_name}: {len(names)} bodies -> {names}")

    root_names = [root.bRepBodies.item(i).name
                  for i in range(root.bRepBodies.count)]
    print(f"Root: {len(root_names)} bodies -> {root_names}")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
