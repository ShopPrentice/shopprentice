"""
Roubo Workbench
===============
84"L x 22"W x 34"H. Classic Andre Roubo French workbench.
Massive 5" slab top, heavy legs flush with front/back edges,
through-tenon joinery, low stretchers, sliding deadman, dog holes.

Front legs and stretcher flush with front edge — critical for
clamping and supporting long boards.

Coordinate system:
  X = length (84")  Y = width/depth (22")  Z = height (34")
"""
import adsk.core, adsk.fusion, math

from helpers import af

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
        # Envelope
        ("bench_l",      "84 in",    "in", "Overall length"),
        ("bench_w",      "22 in",    "in", "Overall width/depth"),
        ("bench_h",      "34 in",    "in", "Overall height"),
        # Top
        ("top_thick",    "5 in",     "in", "Slab top thickness"),
        # Legs — flush with front/back edges
        ("leg_w",        "5 in",     "in", "Leg width (X direction)"),
        ("leg_d",        "5 in",     "in", "Leg depth (Y direction)"),
        ("leg_setback",  "14 in",    "in", "Leg setback from each end (X)"),
        # Long stretchers (front/back, grain in X)
        ("ls_w",         "5 in",     "in", "Long stretcher width (height)"),
        ("ls_t",         "3 in",     "in", "Long stretcher thickness"),
        ("ls_z",         "3 in",     "in", "Long stretcher bottom Z (near floor)"),
        ("ls_proud",     "0.5 in",   "in", "Long stretcher proud past leg"),
        # Short stretchers (left/right, grain in Y, blind into LS)
        ("ss_w",         "4 in",     "in", "Short stretcher width (height)"),
        ("ss_t",         "3 in",     "in", "Short stretcher thickness"),
        # Roubo paired joint: legs into top (flush)
        # Front half = sliding dovetail, back half = straight tenon
        ("lt_tw",        "4 in",     "in", "Leg joint width (X)"),
        ("dt_thick",     "1.5 in",   "in", "Dovetail thickness (Y, front)"),
        ("dt_angle",     "7",        "",   "Dovetail taper angle (degrees)"),
        ("jt_gap",       "1.5 in",   "in", "Gap between DT and tenon"),
        ("mt_thick",     "1.5 in",   "in", "Straight tenon thickness (Y, back)"),
        # Through-tenon: long stretchers through legs
        ("st_tw",        "3 in",     "in", "Stretcher tenon width (Z)"),
        ("st_tt",        "1.5 in",   "in", "Stretcher tenon thickness (Y)"),
        # Deadman
        ("dm_thick",     "1.5 in",   "in", "Deadman panel thickness"),
        ("dm_w",         "4 in",     "in", "Deadman width (X)"),
        ("dm_gap",       "0.5 in",   "in", "Gap between deadman edge and stretcher/top"),
        ("dm_tongue_h",  "1 in",     "in", "Deadman tongue total projection"),
        ("dm_tongue_t",  "0.5 in",   "in", "Deadman tongue thickness (Y)"),
        # Dog holes
        ("dog_dia",      "0.75 in",  "in", "Dog hole diameter"),
        ("dog_sp",       "4 in",     "in", "Dog hole spacing"),
        ("dog_inset",    "1.75 in",  "in", "Dog hole center from front edge"),
        # Leg vise
        ("vise_chop_t",  "2.5 in",  "in", "Vise chop thickness"),
        ("vise_chop_w",  "7 in",    "in", "Vise chop width (wider than leg)"),
        ("vise_bottom_gap","2 in",  "in", "Vise chop clearance from floor"),
        ("vise_screw_dia","1.25 in", "in", "Vise screw diameter"),
        ("vise_handle_l","14 in",    "in", "Vise handle length"),
        ("vise_handle_dia","1 in",   "in", "Vise handle diameter"),
        ("vise_guide_w", "1 in",     "in", "Parallel guide width (Y)"),
        ("vise_guide_h", "3 in",     "in", "Parallel guide height (Z)"),
        # Chamfers
        ("ch_top",       "0.125 in", "in", "Top edge chamfer"),
        ("ch_vise_chop", "1 in",    "in", "Vise chop outer top chamfer"),
        ("ch_leg",       "0.0625 in","in", "Leg bottom chamfer"),
        # Vise positioning
        ("vise_distance","3 in",    "in", "Default distance between vise and leg"),
        ("vise_handle_gap","1 in",  "in", "Vise handle clearance gap"),
    ]:
        params.add(pname, VI(expr), unit, desc)

    # Derived
    for pname, expr, unit, desc in [
        ("leg_h",        "bench_h - top_thick", "in", "Leg height"),
        ("mid_x",        "bench_l / 2",         "in", "X midplane"),
        ("mid_y",        "bench_w / 2",         "in", "Y midplane"),
        # Long stretcher spans from left leg outer face to right leg outer face + proud
        ("ls_span",      "bench_l - 2 * leg_setback", "in",
         "Span between leg outer faces"),
        ("ls_len",       "ls_span + 2 * ls_proud", "in",
         "Long stretcher total length"),
        # Deadman height: from top of front LS to underside of top, minus gap
        ("dm_h",         "leg_h - ls_z - ls_w - 2 * dm_gap", "in",
         "Deadman panel height"),
        # Dovetail X expansion across Y depth (per side)
        ("dt_expand",    "dt_thick * tan(dt_angle * 1 deg)", "in",
         "Dovetail taper expansion per side"),
        # Dog hole count
        ("dog_count",    "floor((bench_l - 2 * leg_setback - 2 * leg_w) / dog_sp)", "",
         "Number of dog holes"),
        ("dm_dog_count", "floor((dm_h - dog_sp) / dog_sp) + 1", "",
         "Number of deadman dog holes"),
        # Vise derived
        ("vise_screw_z", "leg_h - 5 in", "in", "Vise screw center Z"),
        ("vise_guide_z", "ls_z + ls_w + 1 in", "in",
         "Parallel guide center Z"),
    ]:
        params.add(pname, VI(expr), unit, desc)

    # ==============================================================
    #  MIDPLANES
    # ==============================================================
    XMid = af.off_plane(root, root.yZConstructionPlane, "mid_x", "XMid")
    YMid = af.off_plane(root, root.xZConstructionPlane, "mid_y", "YMid")

    # ==============================================================
    #  TOP
    # ==============================================================
    top_occ = af.make_comp(root, "Top")
    top_c = top_occ.component

    _, pr = af.sketch_rect_model(top_c, root.xZConstructionPlane,
        ("0 in", "0 in", "leg_h"),
        {"x": "bench_l", "z": "top_thick"},
        "Top_Sk", ev=ev)
    top_ext = af.ext_new(top_c, pr, "bench_w", "TopSlab")
    top_body = top_ext.bodies.item(0)
    top_body.name = "Top"

    # ==============================================================
    #  LEGS (front flush Y=0, back flush Y=bench_w-leg_d)
    # ==============================================================
    leg_occ = af.make_comp(root, "Legs")
    leg_c = leg_occ.component

    # FL leg: front-left corner
    _, pr = af.sketch_rect_model(leg_c, root.xYConstructionPlane,
        ("leg_setback", "0 in", "0 in"),
        {"x": "leg_w", "y": "leg_d"},
        "LegFL_Sk", ev=ev)
    leg_fl_ext = af.ext_new(leg_c, pr, "leg_h", "LegFL")
    leg_fl = leg_fl_ext.bodies.item(0)
    leg_fl.name = "Leg_FL"

    # Roubo paired joint on FL leg top: dovetail (front) + tenon (back), flush
    # Layout from front (Y=0): dovetail | gap | tenon | shoulder
    # Sketch on the mating surface (leg top face) so all dimensions are
    # relative to the leg, not to the table origin.  Full-width tenons
    # cause sketch edges to coincide with auto-projected face edges,
    # creating fragment profiles — _pick_profile selects by centroid.
    leg_top_face = af.find_face(leg_fl, "z", +1)

    def _face_fl_pt(sketch):
        """Front-left corner sketch point of the projected face boundary."""
        best = None
        seen = set()
        for i in range(sketch.sketchCurves.sketchLines.count):
            ln = sketch.sketchCurves.sketchLines.item(i)
            if not ln.isReference:
                continue
            for sp in [ln.startSketchPoint, ln.endSketchPoint]:
                if id(sp) not in seen:
                    seen.add(id(sp))
                    g = sp.geometry
                    if best is None or (g.x + g.y) < (best.geometry.x + best.geometry.y):
                        best = sp
        return best

    def _pick_profile(sketch, target_x, target_y):
        """Select profile whose bounding box center is nearest target."""
        best, best_d = None, float('inf')
        for i in range(sketch.profiles.count):
            p = sketch.profiles.item(i)
            bb = p.boundingBox
            mx = (bb.minPoint.x + bb.maxPoint.x) / 2
            my = (bb.minPoint.y + bb.maxPoint.y) / 2
            d2 = (mx - target_x)**2 + (my - target_y)**2
            if d2 < best_d:
                best, best_d = p, d2
        return best

    # 1. Dovetail tenon (front half) — trapezoidal plan-view cross-section
    #    Front edge (Y=0, outer): lt_tw wide, centered on face
    #    Back edge (Y=dt_thick, inner): full leg_w
    P = adsk.core.Point3D
    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation

    sk_dt = leg_c.sketches.add(leg_top_face)
    sk_dt.name = "DT_FL_Sk"
    m2s = sk_dt.modelToSketchSpace
    face_fl = _face_fl_pt(sk_dt)

    cx = ev("leg_setback + leg_w / 2")
    hw_f = ev("lt_tw") / 2
    dy = ev("dt_thick")
    z = ev("leg_h")
    lx = ev("leg_setback")
    rx = ev("leg_setback + leg_w")

    p_fl = m2s(P.create(cx - hw_f, 0, z))
    p_fr = m2s(P.create(cx + hw_f, 0, z))
    p_br = m2s(P.create(rx, dy, z))
    p_bl = m2s(P.create(lx, dy, z))

    sl = sk_dt.sketchCurves.sketchLines
    l_front = sl.addByTwoPoints(
        P.create(p_fl.x, p_fl.y, 0), P.create(p_fr.x, p_fr.y, 0))
    l_right = sl.addByTwoPoints(
        l_front.endSketchPoint, P.create(p_br.x, p_br.y, 0))
    l_back = sl.addByTwoPoints(
        l_right.endSketchPoint, P.create(p_bl.x, p_bl.y, 0))
    l_left = sl.addByTwoPoints(
        l_back.endSketchPoint, l_front.startSketchPoint)

    sk_dt.geometricConstraints.addHorizontal(l_front)
    sk_dt.geometricConstraints.addHorizontal(l_back)

    d = sk_dt.sketchDimensions
    mid_f = (p_fl.x + p_fr.x) / 2
    fl_g = face_fl.geometry

    # Front edge width
    d.addDistanceDimension(
        l_front.startSketchPoint, l_front.endSketchPoint,
        H, P.create(mid_f, p_fl.y - 1, 0)
    ).parameter.expression = "lt_tw"
    # Back edge width
    d.addDistanceDimension(
        l_back.endSketchPoint, l_back.startSketchPoint,
        H, P.create((p_bl.x + p_br.x) / 2, p_bl.y + 1, 0)
    ).parameter.expression = "leg_w"
    # Depth (front to back)
    d.addDistanceDimension(
        l_front.startSketchPoint, l_back.endSketchPoint,
        V, P.create(p_fl.x - 1, dy / 2, 0)
    ).parameter.expression = "dt_thick"
    # Front-left offset from face left edge (face-relative, no leg_setback)
    d.addDistanceDimension(
        face_fl, l_front.startSketchPoint,
        H, P.create((fl_g.x + p_fl.x) / 2, p_fl.y - 2, 0)
    ).parameter.expression = "(leg_w - lt_tw) / 2"
    # Front edge Y = face front edge (0 offset)
    d.addDistanceDimension(
        face_fl, l_front.startSketchPoint,
        V, P.create(p_fl.x - 2, fl_g.y - 0.5, 0)
    ).parameter.expression = "0 in"
    # Back-left X = face left edge (0 offset)
    d.addDistanceDimension(
        face_fl, l_back.endSketchPoint,
        H, P.create(fl_g.x - 0.5, p_bl.y + 1, 0)
    ).parameter.expression = "0 in"

    dt_pr = _pick_profile(sk_dt, cx, dy / 2)
    dt_ext = af.ext_new(leg_c, dt_pr, "top_thick", "DT_FL")
    dt_body = dt_ext.bodies.item(0)
    dt_body.name = "DT_FL"

    # 2. Straight tenon (back half) — full leg width, no taper
    sk_mt = leg_c.sketches.add(leg_top_face)
    sk_mt.name = "MT_FL_Sk"
    m2s_mt = sk_mt.modelToSketchSpace
    face_fl_mt = _face_fl_pt(sk_mt)

    mt_y0 = ev("dt_thick + jt_gap")
    mt_dy = ev("mt_thick")
    p_mt_fl = m2s_mt(P.create(lx, mt_y0, z))
    p_mt_fr = m2s_mt(P.create(rx, mt_y0, z))
    p_mt_br = m2s_mt(P.create(rx, mt_y0 + mt_dy, z))
    p_mt_bl = m2s_mt(P.create(lx, mt_y0 + mt_dy, z))

    sl_mt = sk_mt.sketchCurves.sketchLines
    mt_bot = sl_mt.addByTwoPoints(
        P.create(p_mt_fl.x, p_mt_fl.y, 0), P.create(p_mt_fr.x, p_mt_fr.y, 0))
    mt_right = sl_mt.addByTwoPoints(
        mt_bot.endSketchPoint, P.create(p_mt_br.x, p_mt_br.y, 0))
    mt_top = sl_mt.addByTwoPoints(
        mt_right.endSketchPoint, P.create(p_mt_bl.x, p_mt_bl.y, 0))
    mt_left = sl_mt.addByTwoPoints(
        mt_top.endSketchPoint, mt_bot.startSketchPoint)

    sk_mt.geometricConstraints.addHorizontal(mt_bot)
    sk_mt.geometricConstraints.addHorizontal(mt_top)
    sk_mt.geometricConstraints.addVertical(mt_left)
    sk_mt.geometricConstraints.addVertical(mt_right)

    fl_mt_g = face_fl_mt.geometry
    d_mt = sk_mt.sketchDimensions
    # Tenon width (full leg width)
    d_mt.addDistanceDimension(
        mt_bot.startSketchPoint, mt_bot.endSketchPoint,
        H, P.create((p_mt_fl.x + p_mt_fr.x) / 2, p_mt_fl.y - 1, 0)
    ).parameter.expression = "leg_w"
    # Tenon thickness
    d_mt.addDistanceDimension(
        mt_bot.startSketchPoint, mt_top.endSketchPoint,
        V, P.create(p_mt_fl.x - 1, mt_y0 + mt_dy / 2, 0)
    ).parameter.expression = "mt_thick"
    # Bottom-left X = face left edge (0 offset)
    d_mt.addDistanceDimension(
        face_fl_mt, mt_bot.startSketchPoint,
        H, P.create(fl_mt_g.x - 0.5, p_mt_fl.y, 0)
    ).parameter.expression = "0 in"
    # Offset from face front edge
    d_mt.addDistanceDimension(
        face_fl_mt, mt_bot.startSketchPoint,
        V, P.create(p_mt_fl.x - 2, mt_y0 / 2, 0)
    ).parameter.expression = "dt_thick + jt_gap"

    mt_pr = _pick_profile(sk_mt, (lx + rx) / 2, mt_y0 + mt_dy / 2)
    mt_ext = af.ext_new(leg_c, mt_pr, "top_thick", "MT_FL")
    mt_body = mt_ext.bodies.item(0)
    mt_body.name = "MT_FL"

    # JOIN both tenons to FL leg
    af.combine(leg_c, leg_fl, [dt_body, mt_body], JOIN, False, "LegJt_FL_Join")

    # Mirror across XMid → FR, then across YMid → BL, BR
    mir_x = af.mirror_body(leg_c, leg_fl, XMid, "LegMirX")
    leg_fr = mir_x.bodies.item(0)
    leg_fr.name = "Leg_FR"

    mir_y = af.mirror_bodies(leg_c, [leg_fl, leg_fr], YMid, "LegMirY")
    mir_y.bodies.item(0).name = "Leg_BL"
    mir_y.bodies.item(1).name = "Leg_BR"

    # ==============================================================
    #  LONG STRETCHERS (front flush with front legs, through-tenon)
    # ==============================================================
    ls_occ = af.make_comp(root, "LongStretchers")
    ls_c = ls_occ.component

    # Through-tenon: full-length tenon body (st_tw × st_tt) + main body
    # between inner leg faces (ls_w × ls_t).  CUT against legs uses the
    # combined body — only the tenon cross-section intersects the leg,
    # so mortises are automatically tenon-sized.

    # Tenon body (full length, tenon cross-section, centered on stretcher)
    ls_tenon_pl = af.off_plane(ls_c, root.xZConstructionPlane,
        "(leg_d - st_tt) / 2", "LSTenon_Pl")
    _, pr = af.sketch_rect_model(ls_c, ls_tenon_pl,
        ("leg_setback - ls_proud",
         "(leg_d - st_tt) / 2",
         "ls_z + (ls_w - st_tw) / 2"),
        {"x": "ls_len", "z": "st_tw"},
        "LSTenon_Sk", ev=ev)
    ls_tenon_ext = af.ext_new(ls_c, pr, "st_tt", "LSTenon")
    ls_tenon = ls_tenon_ext.bodies.item(0)
    ls_tenon.name = "LS_Front_Tenon"

    # Main body (between inner leg faces, full stretcher cross-section)
    ls_main_pl = af.off_plane(ls_c, root.xZConstructionPlane,
        "(leg_d - ls_t) / 2", "LSMain_Pl")
    _, pr = af.sketch_rect_model(ls_c, ls_main_pl,
        ("leg_setback + leg_w",
         "(leg_d - ls_t) / 2",
         "ls_z"),
        {"x": "bench_l - 2 * leg_setback - 2 * leg_w", "z": "ls_w"},
        "LSMain_Sk", ev=ev)
    ls_main_ext = af.ext_new(ls_c, pr, "ls_t", "LSMain")
    ls_main = ls_main_ext.bodies.item(0)
    ls_main.name = "LS_Front_Main"

    # JOIN main to tenon → combined stretcher with shoulders
    af.combine(ls_c, ls_tenon, [ls_main], JOIN, False, "LSFront_Join")
    ls_front = ls_tenon
    ls_front.name = "LS_Front"

    # Mirror across YMid → LS_Back
    mir_ls = af.mirror_body(ls_c, ls_front, YMid, "LSMirY")
    ls_back = mir_ls.bodies.item(0)
    ls_back.name = "LS_Back"

    # ==============================================================
    #  SHORT STRETCHERS (through legs, raised above LS, through-tenon)
    # ==============================================================
    ss_occ = af.make_comp(root, "ShortStretchers")
    ss_c = ss_occ.component

    # Tenon body (full bench width, tenon cross-section)
    ss_tenon_pl = af.off_plane(ss_c, root.yZConstructionPlane,
        "leg_setback + leg_w / 2", "SSTenon_Pl")
    _, pr = af.sketch_rect_model(ss_c, ss_tenon_pl,
        ("0 in",
         "0 in",
         "ls_z + ls_w + (ss_w - st_tw) / 2"),
        {"y": "bench_w", "z": "st_tw"},
        "SSTenon_Sk", ev=ev)
    ss_tenon_ext = af.ext_new_sym(ss_c, pr, "st_tt / 2", "SSTenon")
    ss_tenon = ss_tenon_ext.bodies.item(0)
    ss_tenon.name = "SS_Left_Tenon"

    # Main body (between front/back inner leg faces, full cross-section)
    ss_main_pl = af.off_plane(ss_c, root.yZConstructionPlane,
        "leg_setback + leg_w / 2", "SSMain_Pl")
    _, pr = af.sketch_rect_model(ss_c, ss_main_pl,
        ("0 in",
         "leg_d",
         "ls_z + ls_w"),
        {"y": "bench_w - 2 * leg_d", "z": "ss_w"},
        "SSMain_Sk", ev=ev)
    ss_main_ext = af.ext_new_sym(ss_c, pr, "ss_t / 2", "SSMain")
    ss_main = ss_main_ext.bodies.item(0)
    ss_main.name = "SS_Left_Main"

    # JOIN main to tenon
    af.combine(ss_c, ss_tenon, [ss_main], JOIN, False, "SSLeft_Join")
    ss_left = ss_tenon
    ss_left.name = "SS_Left"

    # Mirror across XMid → SS_Right
    mir_ss = af.mirror_body(ss_c, ss_left, XMid, "SSMirX")
    ss_right = mir_ss.bodies.item(0)
    ss_right.name = "SS_Right"

    # ==============================================================
    #  DEADMAN (panel on front stretcher, between front legs)
    # ==============================================================
    dm_occ = af.make_comp(root, "Deadman")
    dm_c = dm_occ.component

    # Deadman: centered at bench midpoint (X), flush with front LS front face
    # Y: front LS front face = (leg_d - ls_t) / 2
    # Z: raised by dm_gap above LS top, with gap at top too
    dm_pl = af.off_plane(dm_c, root.yZConstructionPlane,
        "mid_x", "DM_Pl")
    _, pr = af.sketch_rect_model(dm_c, dm_pl,
        ("0 in", "(leg_d - ls_t) / 2", "ls_z + ls_w + dm_gap"),
        {"y": "dm_thick", "z": "dm_h"},
        "DM_Sk", ev=ev)
    dm_ext = af.ext_new_sym(dm_c, pr, "dm_w / 2", "DMPanel")
    dm_body = dm_ext.bodies.item(0)
    dm_body.name = "Deadman"

    # Bottom tongue — extends down from panel into LS groove
    _, pr = af.sketch_rect_model(dm_c, dm_pl,
        ("0 in",
         "(leg_d - ls_t) / 2 + (dm_thick - dm_tongue_t) / 2",
         "ls_z + ls_w + dm_gap - dm_tongue_h"),
        {"y": "dm_tongue_t", "z": "dm_tongue_h"},
        "DMTongueBot_Sk", ev=ev)
    dm_tbot_ext = af.ext_new_sym(dm_c, pr, "dm_w / 2", "DMTongueBot")
    dm_tbot = dm_tbot_ext.bodies.item(0)
    dm_tbot.name = "DM_Tongue_Bot"
    af.combine(dm_c, dm_body, [dm_tbot], JOIN, False, "DMTongueBot_Join")

    # Top tongue — extends up from panel into top groove
    _, pr = af.sketch_rect_model(dm_c, dm_pl,
        ("0 in",
         "(leg_d - ls_t) / 2 + (dm_thick - dm_tongue_t) / 2",
         "leg_h - dm_gap"),
        {"y": "dm_tongue_t", "z": "dm_tongue_h"},
        "DMTongueTop_Sk", ev=ev)
    dm_ttop_ext = af.ext_new_sym(dm_c, pr, "dm_w / 2", "DMTongueTop")
    dm_ttop = dm_ttop_ext.bodies.item(0)
    dm_ttop.name = "DM_Tongue_Top"
    af.combine(dm_c, dm_body, [dm_ttop], JOIN, False, "DMTongueTop_Join")

    # Deadman dog holes — vertical column on front face
    dm_front_face = af.find_face(dm_body, "y", -1)
    dm_sk = dm_c.sketches.add(dm_front_face)
    dm_sk.name = "DMDog_Sk"
    dm_m2s = dm_sk.modelToSketchSpace
    P = adsk.core.Point3D
    dm_cx = ev("mid_x")
    dm_y = ev("(leg_d - ls_t) / 2")
    dm_z0 = ev("ls_z + ls_w + dm_gap + dog_sp - 2 in")
    dm_r = ev("dog_dia") / 2
    dm_ctr = dm_m2s(P.create(dm_cx, dm_y, dm_z0))
    dm_sk.sketchCurves.sketchCircles.addByCenterRadius(
        P.create(dm_ctr.x, dm_ctr.y, 0), dm_r)
    dm_circle = dm_sk.sketchCurves.sketchCircles.item(0)
    dm_sk.sketchDimensions.addRadialDimension(
        dm_circle, P.create(dm_ctr.x + dm_r + 1, dm_ctr.y, 0)
    ).parameter.expression = "dog_dia / 2"

    dm_dog_prof = af.smallest_profile(dm_sk)
    dm_dog_ext = af.ext_op(dm_c, dm_dog_prof, "dm_thick", CUT,
                           dm_body, "DMDogHole", flip=True)

    # Pattern vertically
    dm_dc = int(ev("dm_dog_count"))
    if dm_dc > 1:
        af.feat_pattern(dm_c, dm_dog_ext, dm_c.zConstructionAxis,
                        "dm_dog_count", "dog_sp", "DMDog_Pat")

    # ==============================================================
    #  LEG VISE (on front-left leg)
    # ==============================================================
    vise_occ = af.make_comp(root, "LegVise")
    vise_c = vise_occ.component

    # Reference FL leg's left face — vise X positioning follows the leg
    leg_fl_left = af.find_face(leg_fl, "x", -1).createForAssemblyContext(leg_occ)
    LegFL_Left = af.off_plane(vise_c, leg_fl_left, "0 in", "LegFL_Left")

    P = adsk.core.Point3D
    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation

    # Runtime X values for initial geometry placement (not in parametric expressions)
    _vise_lx = ev("leg_setback")
    _vise_cx = ev("leg_setback + leg_w / 2")

    # Chop — full-height slab in front of FL leg (Y < 0)
    vise_chop_pl = af.off_plane(vise_c, root.xZConstructionPlane,
        "-vise_distance - vise_chop_t", "ViseChop_Pl")
    chop_sk = vise_c.sketches.add(vise_chop_pl)
    chop_sk.name = "ViseChop_Sk"
    chop_ref = chop_sk.project(LegFL_Left).item(0).startSketchPoint
    chop_m2s = chop_sk.modelToSketchSpace

    _chop_y = ev("-vise_distance - vise_chop_t")
    _chop_offset = (ev("vise_chop_w") - ev("leg_w")) / 2
    _chop_lx = _vise_lx - _chop_offset
    _chop_rx = _chop_lx + ev("vise_chop_w")
    _chop_z0 = ev("vise_bottom_gap")
    _chop_z1 = ev("bench_h")
    chop_bl = chop_m2s(P.create(_chop_lx, _chop_y, _chop_z0))
    chop_br = chop_m2s(P.create(_chop_rx, _chop_y, _chop_z0))
    chop_tr = chop_m2s(P.create(_chop_rx, _chop_y, _chop_z1))
    chop_tl = chop_m2s(P.create(_chop_lx, _chop_y, _chop_z1))
    sl_c = chop_sk.sketchCurves.sketchLines
    c_bot = sl_c.addByTwoPoints(
        P.create(chop_bl.x, chop_bl.y, 0),
        P.create(chop_br.x, chop_br.y, 0))
    c_right = sl_c.addByTwoPoints(
        c_bot.endSketchPoint,
        P.create(chop_tr.x, chop_tr.y, 0))
    c_top = sl_c.addByTwoPoints(
        c_right.endSketchPoint,
        P.create(chop_tl.x, chop_tl.y, 0))
    c_left = sl_c.addByTwoPoints(
        c_top.endSketchPoint, c_bot.startSketchPoint)

    chop_sk.geometricConstraints.addHorizontal(c_bot)
    chop_sk.geometricConstraints.addHorizontal(c_top)
    chop_sk.geometricConstraints.addVertical(c_left)
    chop_sk.geometricConstraints.addVertical(c_right)

    dc = chop_sk.sketchDimensions
    dc.addDistanceDimension(
        c_bot.startSketchPoint, c_bot.endSketchPoint,
        H, P.create((chop_bl.x + chop_br.x) / 2, chop_bl.y - 1, 0)
    ).parameter.expression = "vise_chop_w"
    dc.addDistanceDimension(
        c_bot.startSketchPoint, c_top.endSketchPoint,
        V, P.create(chop_bl.x - 1, (chop_bl.y + chop_tl.y) / 2, 0)
    ).parameter.expression = "bench_h - vise_bottom_gap"
    # X from leg left face (centered, so offset by half the width difference)
    dc.addDistanceDimension(
        chop_ref, c_bot.startSketchPoint,
        H, P.create(chop_bl.x - 0.5, chop_bl.y - 2, 0)
    ).parameter.expression = "(vise_chop_w - leg_w) / 2"
    # Z from floor
    dc.addDistanceDimension(
        chop_sk.originPoint, c_bot.startSketchPoint,
        V, P.create(chop_bl.x - 2, chop_bl.y / 2, 0)
    ).parameter.expression = "vise_bottom_gap"

    chop_ext = af.ext_new(vise_c,
        _pick_profile(chop_sk,
                      (chop_bl.x + chop_br.x) / 2,
                      (chop_bl.y + chop_tl.y) / 2),
        "vise_chop_t", "ViseChop")
    chop_body = chop_ext.bodies.item(0)
    chop_body.name = "Vise_Chop"

    # Chamfer on outer top edge of chop (front face, Z=max)
    _chop_max_z = ev("bench_h")
    _chop_min_y = ev("-vise_distance - vise_chop_t")
    chop_edges = adsk.core.ObjectCollection.create()
    for j in range(chop_body.edges.count):
        e = chop_body.edges.item(j)
        sv, ev2 = e.startVertex.geometry, e.endVertex.geometry
        if (abs(sv.z - _chop_max_z) < 0.01 and abs(ev2.z - _chop_max_z) < 0.01
                and abs(sv.y - _chop_min_y) < 0.01 and abs(ev2.y - _chop_min_y) < 0.01):
            chop_edges.add(e)
    if chop_edges.count > 0:
        ch_inp = vise_c.features.chamferFeatures.createInput2()
        ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
            chop_edges, VI("ch_vise_chop"), True)
        ch = vise_c.features.chamferFeatures.add(ch_inp)
        ch.name = "ViseChop_Ch"

    # Screw — cylinder along Y through chop and leg
    vise_screw_pl = af.off_plane(vise_c, root.xZConstructionPlane,
        "-vise_distance - vise_chop_t - vise_handle_gap", "ViseScrew_Pl")
    screw_sk = vise_c.sketches.add(vise_screw_pl)
    screw_sk.name = "ViseScrew_Sk"
    screw_ref = screw_sk.project(LegFL_Left).item(0).startSketchPoint
    screw_m2s = screw_sk.modelToSketchSpace

    screw_ctr = screw_m2s(P.create(
        _vise_cx,
        ev("-vise_distance - vise_chop_t - vise_handle_gap"),
        ev("vise_screw_z")))
    screw_r = ev("vise_screw_dia") / 2
    screw_sk.sketchCurves.sketchCircles.addByCenterRadius(
        P.create(screw_ctr.x, screw_ctr.y, 0), screw_r)
    screw_circle = screw_sk.sketchCurves.sketchCircles.item(0)

    ds = screw_sk.sketchDimensions
    ds.addRadialDimension(
        screw_circle, P.create(screw_ctr.x + screw_r + 1, screw_ctr.y, 0)
    ).parameter.expression = "vise_screw_dia / 2"
    # X center from leg left face
    ds.addDistanceDimension(
        screw_circle.centerSketchPoint, screw_ref,
        H, P.create(screw_ctr.x - 1, screw_ctr.y - 2, 0)
    ).parameter.expression = "leg_w / 2"
    # Z position
    ds.addDistanceDimension(
        screw_sk.originPoint, screw_circle.centerSketchPoint,
        V, P.create(screw_ctr.x - 2, screw_ctr.y / 2, 0)
    ).parameter.expression = "vise_screw_z"

    screw_prof = af.smallest_profile(screw_sk)
    screw_ext = af.ext_new(vise_c, screw_prof,
        "vise_chop_t + leg_d + vise_handle_gap + vise_distance", "ViseScrew")
    screw_body = screw_ext.bodies.item(0)
    screw_body.name = "Vise_Screw"

    # Handle — cylinder along X, centered on leg
    vise_handle_pl = af.off_plane(vise_c, LegFL_Left,
        "-leg_w / 2", "ViseHandle_Pl")
    handle_sk = vise_c.sketches.add(vise_handle_pl)
    handle_sk.name = "ViseHandle_Sk"
    handle_m2s = handle_sk.modelToSketchSpace

    handle_ctr = handle_m2s(P.create(
        _vise_cx,
        ev("-vise_distance - vise_chop_t - vise_handle_gap"),
        ev("vise_screw_z")))
    handle_r = ev("vise_handle_dia") / 2
    handle_sk.sketchCurves.sketchCircles.addByCenterRadius(
        P.create(handle_ctr.x, handle_ctr.y, 0), handle_r)
    handle_circle = handle_sk.sketchCurves.sketchCircles.item(0)

    # Detect sketch axis mapping: which sketch direction corresponds to model Y vs Z
    _h_origin = handle_m2s(P.create(_vise_cx, 0, 0))
    _h_test_y = handle_m2s(P.create(_vise_cx, 1, 0))
    _h_y_is_H = abs(_h_test_y.x - _h_origin.x) > abs(_h_test_y.y - _h_origin.y)
    _h_y_orient = H if _h_y_is_H else V
    _h_z_orient = V if _h_y_is_H else H

    dh = handle_sk.sketchDimensions
    dh.addRadialDimension(
        handle_circle, P.create(handle_ctr.x + handle_r + 1, handle_ctr.y, 0)
    ).parameter.expression = "vise_handle_dia / 2"
    # Y position (vise offset from leg front face)
    dh.addDistanceDimension(
        handle_sk.originPoint, handle_circle.centerSketchPoint,
        _h_y_orient, P.create(handle_ctr.x / 2, handle_ctr.y - 2, 0)
    ).parameter.expression = "vise_distance + vise_chop_t + vise_handle_gap"
    # Z position
    dh.addDistanceDimension(
        handle_sk.originPoint, handle_circle.centerSketchPoint,
        _h_z_orient, P.create(handle_ctr.x - 2, handle_ctr.y / 2, 0)
    ).parameter.expression = "vise_screw_z"

    handle_prof = af.smallest_profile(handle_sk)
    handle_ext = af.ext_new_sym(vise_c, handle_prof,
        "vise_handle_l / 2", "ViseHandle")
    handle_body = handle_ext.bodies.item(0)
    handle_body.name = "Vise_Handle"

    # Parallel guide — rectangular board along Y through leg
    vise_guide_pl = af.off_plane(vise_c, root.xZConstructionPlane,
        "-vise_distance - vise_chop_t", "ViseGuide_Pl")
    guide_sk = vise_c.sketches.add(vise_guide_pl)
    guide_sk.name = "ViseGuide_Sk"
    guide_ref = guide_sk.project(LegFL_Left).item(0).startSketchPoint
    guide_m2s = guide_sk.modelToSketchSpace

    _guide_lx = ev("leg_setback + (leg_w - vise_guide_w) / 2")
    _guide_rx = _guide_lx + ev("vise_guide_w")
    _guide_y = ev("-vise_distance - vise_chop_t")
    _guide_z0 = ev("vise_guide_z - vise_guide_h / 2")
    _guide_z1 = _guide_z0 + ev("vise_guide_h")
    guide_bl = guide_m2s(P.create(_guide_lx, _guide_y, _guide_z0))
    guide_br = guide_m2s(P.create(_guide_rx, _guide_y, _guide_z0))
    guide_tr = guide_m2s(P.create(_guide_rx, _guide_y, _guide_z1))
    guide_tl = guide_m2s(P.create(_guide_lx, _guide_y, _guide_z1))

    sl_g = guide_sk.sketchCurves.sketchLines
    g_bot = sl_g.addByTwoPoints(
        P.create(guide_bl.x, guide_bl.y, 0),
        P.create(guide_br.x, guide_br.y, 0))
    g_right = sl_g.addByTwoPoints(
        g_bot.endSketchPoint,
        P.create(guide_tr.x, guide_tr.y, 0))
    g_top = sl_g.addByTwoPoints(
        g_right.endSketchPoint,
        P.create(guide_tl.x, guide_tl.y, 0))
    g_left = sl_g.addByTwoPoints(
        g_top.endSketchPoint, g_bot.startSketchPoint)

    guide_sk.geometricConstraints.addHorizontal(g_bot)
    guide_sk.geometricConstraints.addHorizontal(g_top)
    guide_sk.geometricConstraints.addVertical(g_left)
    guide_sk.geometricConstraints.addVertical(g_right)

    dg = guide_sk.sketchDimensions
    dg.addDistanceDimension(
        g_bot.startSketchPoint, g_bot.endSketchPoint,
        H, P.create((guide_bl.x + guide_br.x) / 2, guide_bl.y - 1, 0)
    ).parameter.expression = "vise_guide_w"
    dg.addDistanceDimension(
        g_bot.startSketchPoint, g_top.endSketchPoint,
        V, P.create(guide_bl.x - 1, (guide_bl.y + guide_tl.y) / 2, 0)
    ).parameter.expression = "vise_guide_h"
    # X from leg left face
    dg.addDistanceDimension(
        g_bot.startSketchPoint, guide_ref,
        H, P.create(guide_bl.x - 0.5, guide_bl.y - 2, 0)
    ).parameter.expression = "(leg_w - vise_guide_w) / 2"
    # Z position
    dg.addDistanceDimension(
        guide_sk.originPoint, g_bot.startSketchPoint,
        V, P.create(guide_bl.x - 2, guide_bl.y / 2, 0)
    ).parameter.expression = "vise_guide_z - vise_guide_h / 2"

    guide_ext = af.ext_new(vise_c,
        _pick_profile(guide_sk,
                      (guide_bl.x + guide_br.x) / 2,
                      (guide_bl.y + guide_tl.y) / 2),
        "vise_chop_t + vise_distance + leg_d", "ViseGuide")
    guide_body = guide_ext.bodies.item(0)
    guide_body.name = "Vise_Guide"

    # ==============================================================
    #  DOG HOLES (row along front edge of top — before mortise cuts)
    # ==============================================================
    dog_x0 = ev("leg_setback + leg_w + dog_sp")
    dog_y = ev("dog_inset")
    dog_z = ev("leg_h")
    dog_r = ev("dog_dia") / 2

    top_top_face = af.find_face(top_c.bRepBodies.item(0), "z", +1)
    sk = top_c.sketches.add(top_top_face)
    sk.name = "DogHole_Sk"
    m2s = sk.modelToSketchSpace
    P = adsk.core.Point3D
    center_sk = m2s(P.create(dog_x0, dog_y, ev("bench_h")))
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        P.create(center_sk.x, center_sk.y, 0), dog_r)
    circle = sk.sketchCurves.sketchCircles.item(0)
    sk.sketchDimensions.addRadialDimension(
        circle, P.create(center_sk.x + dog_r + 1, center_sk.y, 0)
    ).parameter.expression = "dog_dia / 2"

    dog_prof = af.smallest_profile(sk)
    dog_ext = af.ext_op(top_c, dog_prof, "top_thick", CUT,
                        top_c.bRepBodies.item(0), "DogHole", flip=True)

    dog_count = int(ev("dog_count"))
    if dog_count > 1:
        af.feat_pattern(top_c, dog_ext, top_c.xConstructionAxis,
                        "dog_count", "dog_sp", "DogHole_Pat")

    # ==============================================================
    #  CROSS-COMPONENT CUTS
    # ==============================================================
    def get_proxies(occ):
        c = occ.component
        return [c.bRepBodies.item(i).createForAssemblyContext(occ)
                for i in range(c.bRepBodies.count)]

    # CUT top with all 4 leg proxies (through-tenon mortises)
    top_proxy = top_c.bRepBodies.item(0).createForAssemblyContext(top_occ)
    leg_proxies = get_proxies(leg_occ)
    af.combine(root, top_proxy, leg_proxies, CUT, True, "LegMortise_Cut")

    # CUT legs with long stretcher proxies (through-mortises)
    ls_proxies = get_proxies(ls_occ)
    for i in range(leg_c.bRepBodies.count):
        lp = leg_c.bRepBodies.item(i).createForAssemblyContext(leg_occ)
        af.combine(root, lp, ls_proxies, CUT, True, f"LSMort_Leg{i}")

    # CUT FL leg with vise screw bore and guide slot (not chop/handle)
    vise_screw_p = vise_c.bRepBodies.itemByName("Vise_Screw").createForAssemblyContext(vise_occ)
    vise_guide_p = vise_c.bRepBodies.itemByName("Vise_Guide").createForAssemblyContext(vise_occ)
    fl_proxy = leg_c.bRepBodies.item(0).createForAssemblyContext(leg_occ)
    af.combine(root, fl_proxy, [vise_screw_p, vise_guide_p], CUT, True, "ViseMort_FL")

    # CUT chop with screw bore
    chop_proxy = vise_c.bRepBodies.itemByName("Vise_Chop").createForAssemblyContext(vise_occ)
    screw_proxy = vise_c.bRepBodies.itemByName("Vise_Screw").createForAssemblyContext(vise_occ)
    af.combine(root, chop_proxy, [screw_proxy], CUT, True, "ViseScrew_ChopCut")

    # CUT legs with short stretcher proxies (SS passes through legs)
    ss_proxies = get_proxies(ss_occ)
    for i in range(leg_c.bRepBodies.count):
        lp = leg_c.bRepBodies.item(i).createForAssemblyContext(leg_occ)
        af.combine(root, lp, ss_proxies, CUT, True, f"SSMort_Leg{i}")

    # Deadman tongue grooves — built in target components (local combine).
    # Groove depth into material = dm_tongue_h - dm_gap.

    # Bottom groove in front LS (top face, runs between inner leg faces)
    groove_ls_pl = af.off_plane(ls_c, root.xZConstructionPlane,
        "(leg_d - ls_t) / 2 + (dm_thick - dm_tongue_t) / 2", "GrooveBot_Pl")
    _, pr = af.sketch_rect_model(ls_c, groove_ls_pl,
        ("leg_setback + leg_w",
         "(leg_d - ls_t) / 2 + (dm_thick - dm_tongue_t) / 2",
         "ls_z + ls_w - (dm_tongue_h - dm_gap)"),
        {"x": "bench_l - 2 * leg_setback - 2 * leg_w",
         "z": "dm_tongue_h - dm_gap"},
        "GrooveBot_Sk", ev=ev)
    groove_bot_ext = af.ext_op(ls_c, pr, "dm_tongue_t", CUT,
        ls_c.bRepBodies.itemByName("LS_Front"), "DMGroove_LS")

    # Top groove in bench top underside (runs between inner leg faces)
    groove_top_pl = af.off_plane(top_c, root.xZConstructionPlane,
        "(leg_d - ls_t) / 2 + (dm_thick - dm_tongue_t) / 2", "GrooveTop_Pl")
    _, pr = af.sketch_rect_model(top_c, groove_top_pl,
        ("leg_setback + leg_w",
         "(leg_d - ls_t) / 2 + (dm_thick - dm_tongue_t) / 2",
         "leg_h"),
        {"x": "bench_l - 2 * leg_setback - 2 * leg_w",
         "z": "dm_tongue_h - dm_gap"},
        "GrooveTop_Sk", ev=ev)
    groove_top_ext = af.ext_op(top_c, pr, "dm_tongue_t", CUT,
        top_c.bRepBodies.item(0), "DMGroove_Top")

    # ==============================================================
    #  DETAILS — chamfers
    # ==============================================================
    # Leg bottoms — chamfer Z=0 edges
    for i in range(leg_c.bRepBodies.count):
        body = leg_c.bRepBodies.item(i)
        edges = adsk.core.ObjectCollection.create()
        for j in range(body.edges.count):
            e = body.edges.item(j)
            sv = e.startVertex.geometry
            ev2 = e.endVertex.geometry
            if abs(sv.z) < 0.01 and abs(ev2.z) < 0.01:
                edges.add(e)
        if edges.count > 0:
            ch_inp = leg_c.features.chamferFeatures.createInput2()
            ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                edges, VI("ch_leg"), True)
            ch = leg_c.features.chamferFeatures.add(ch_inp)
            ch.name = f"LegBot_Ch{i}"

    # ==============================================================
    #  EPILOGUE
    # ==============================================================
    for occ in root.occurrences:
        c = occ.component
        for i in range(c.sketches.count):
            c.sketches.item(i).isVisible = False
        for i in range(c.constructionPlanes.count):
            c.constructionPlanes.item(i).isLightBulbOn = False
    for sk in root.sketches:
        sk.isVisible = False
    for cp in root.constructionPlanes:
        cp.isLightBulbOn = False

    names = []
    for occ in root.occurrences:
        c = occ.component
        for i in range(c.bRepBodies.count):
            names.append(f"{occ.name}/{c.bRepBodies.item(i).name}")
    print(f"Bodies: {len(names)} -> {names}")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
