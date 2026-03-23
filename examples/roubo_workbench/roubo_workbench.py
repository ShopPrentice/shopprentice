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
        ("ls_t",         "2 in",     "in", "Long stretcher thickness"),
        ("ls_z",         "3 in",     "in", "Long stretcher bottom Z (near floor)"),
        ("ls_proud",     "0.5 in",   "in", "Long stretcher proud past leg"),
        # Short stretchers (left/right, grain in Y, blind into LS)
        ("ss_w",         "4 in",     "in", "Short stretcher width (height)"),
        ("ss_t",         "2 in",     "in", "Short stretcher thickness"),
        # Roubo paired joint: legs into top (flush)
        # Front half = sliding dovetail, back half = straight tenon
        ("lt_tw",        "3.5 in",   "in", "Leg joint width (X)"),
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
        ("dm_gap",       "1 in",     "in", "Gap between deadman top and top underside"),
        # Dog holes
        ("dog_dia",      "0.75 in",  "in", "Dog hole diameter"),
        ("dog_sp",       "4 in",     "in", "Dog hole spacing"),
        ("dog_inset",    "1.75 in",  "in", "Dog hole center from front edge"),
        # Leg vise
        ("vise_chop_t",  "2.5 in",  "in", "Vise chop thickness"),
        ("vise_screw_dia","1.25 in", "in", "Vise screw diameter"),
        ("vise_handle_l","14 in",    "in", "Vise handle length"),
        ("vise_handle_dia","1 in",   "in", "Vise handle diameter"),
        ("vise_guide_w", "1 in",     "in", "Parallel guide width (Y)"),
        ("vise_guide_h", "3 in",     "in", "Parallel guide height (Z)"),
        # Chamfers
        ("ch_top",       "0.125 in", "in", "Top edge chamfer"),
        ("ch_leg",       "0.0625 in","in", "Leg bottom chamfer"),
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
        ("dm_h",         "leg_h - ls_z - ls_w - dm_gap", "in",
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
        ("vise_screw_z", "leg_h - 9 in", "in", "Vise screw center Z"),
        ("vise_guide_z", "ls_z + ls_w + ss_w + 1 in", "in",
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
    leg_top_face = af.find_face(leg_fl, "z", +1)

    # 1. Dovetail tenon (front half) — trapezoidal plan-view cross-section
    #    Front edge (Y=0, outer): lt_tw wide
    #    Back edge (Y=dt_thick, inner): lt_tw + 2*dt_expand wide (wider inside)
    #    Straight extrude up into top slab.
    P = adsk.core.Point3D
    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation

    sk_dt = leg_c.sketches.add(leg_top_face)
    sk_dt.name = "DT_FL_Sk"
    m2s = sk_dt.modelToSketchSpace

    cx = ev("leg_setback + leg_w / 2")
    hw_f = ev("lt_tw") / 2
    hw_b = ev("lt_tw + 2 * dt_expand") / 2
    dy = ev("dt_thick")
    z = ev("leg_h")

    p_fl = m2s(P.create(cx - hw_f, 0, z))
    p_fr = m2s(P.create(cx + hw_f, 0, z))
    p_br = m2s(P.create(cx + hw_b, dy, z))
    p_bl = m2s(P.create(cx - hw_b, dy, z))

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
    mid_b = (p_bl.x + p_br.x) / 2

    # Front edge width
    d.addDistanceDimension(
        l_front.startSketchPoint, l_front.endSketchPoint,
        H, P.create(mid_f, p_fl.y - 1, 0)
    ).parameter.expression = "lt_tw"
    # Back edge width
    d.addDistanceDimension(
        l_back.endSketchPoint, l_back.startSketchPoint,
        H, P.create(mid_b, p_bl.y + 1, 0)
    ).parameter.expression = "lt_tw + 2 * dt_expand"
    # Depth (front to back)
    d.addDistanceDimension(
        l_front.startSketchPoint, l_back.endSketchPoint,
        V, P.create(p_fl.x - 1, (p_fl.y + p_bl.y) / 2, 0)
    ).parameter.expression = "dt_thick"
    # X position of front-left from sketch origin
    d.addDistanceDimension(
        sk_dt.originPoint, l_front.startSketchPoint,
        H, P.create(p_fl.x / 2, p_fl.y - 2, 0)
    ).parameter.expression = "leg_setback + (leg_w - lt_tw) / 2"
    # Y position of front edge from sketch origin
    d.addDistanceDimension(
        sk_dt.originPoint, l_front.startSketchPoint,
        V, P.create(p_fl.x - 2, p_fl.y / 2, 0)
    ).parameter.expression = "0 in"
    # Symmetry: back edge centered on same X as front edge
    d.addDistanceDimension(
        sk_dt.originPoint, l_back.endSketchPoint,
        H, P.create(p_bl.x / 2, p_bl.y + 2, 0)
    ).parameter.expression = "leg_setback + (leg_w - lt_tw) / 2 - dt_expand"

    dt_pr = af.smallest_profile(sk_dt)
    dt_ext = af.ext_new(leg_c, dt_pr, "top_thick", "DT_FL")
    dt_body = dt_ext.bodies.item(0)
    dt_body.name = "DT_FL"

    # 2. Straight tenon (back half) — no taper
    _, pr = af.sketch_rect_model(leg_c, leg_top_face,
        ("leg_setback + (leg_w - lt_tw) / 2",
         "dt_thick + jt_gap",
         "leg_h"),
        {"x": "lt_tw", "y": "mt_thick"},
        "MT_FL_Sk", ev=ev)
    pr = af.smallest_profile(leg_c.sketches.itemByName("MT_FL_Sk"))
    mt_ext = af.ext_new(leg_c, pr, "top_thick", "MT_FL")
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
    #  LONG STRETCHERS (front flush with front legs, through legs)
    # ==============================================================
    ls_occ = af.make_comp(root, "LongStretchers")
    ls_c = ls_occ.component

    # Front LS: centered in leg depth, runs through legs with proud
    # Y position: centered in front leg → (leg_d - ls_t) / 2
    ls_front_pl = af.off_plane(ls_c, root.xZConstructionPlane,
        "(leg_d - ls_t) / 2", "LSFront_Pl")
    _, pr = af.sketch_rect_model(ls_c, ls_front_pl,
        ("leg_setback - ls_proud", "(leg_d - ls_t) / 2", "ls_z"),
        {"x": "ls_len", "z": "ls_w"},
        "LSFront_Sk", ev=ev)
    ls_front_ext = af.ext_new(ls_c, pr, "ls_t", "LSFront")
    ls_front = ls_front_ext.bodies.item(0)
    ls_front.name = "LS_Front"

    # Mirror across YMid → LS_Back
    mir_ls = af.mirror_body(ls_c, ls_front, YMid, "LSMirY")
    ls_back = mir_ls.bodies.item(0)
    ls_back.name = "LS_Back"

    # ==============================================================
    #  SHORT STRETCHERS (through legs, raised above LS)
    # ==============================================================
    ss_occ = af.make_comp(root, "ShortStretchers")
    ss_c = ss_occ.component

    # Left SS: centered on left leg (X), spans full bench width through legs
    # Raised above LS so through-mortises don't overlap in legs
    ss_pl_l = af.off_plane(ss_c, root.yZConstructionPlane,
        "leg_setback + leg_w / 2", "SSLeft_Pl")
    _, pr = af.sketch_rect_model(ss_c, ss_pl_l,
        ("0 in",
         "0 in",
         "ls_z + ls_w"),
        {"y": "bench_w", "z": "ss_w"},
        "SSLeft_Sk", ev=ev)
    ss_left_ext = af.ext_new_sym(ss_c, pr, "ss_t / 2", "SSLeft")
    ss_left = ss_left_ext.bodies.item(0)
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
    # Z: from top of front LS to underside of top minus gap
    dm_pl = af.off_plane(dm_c, root.yZConstructionPlane,
        "mid_x", "DM_Pl")
    _, pr = af.sketch_rect_model(dm_c, dm_pl,
        ("0 in", "(leg_d - ls_t) / 2", "ls_z + ls_w"),
        {"y": "dm_thick", "z": "dm_h"},
        "DM_Sk", ev=ev)
    dm_ext = af.ext_new_sym(dm_c, pr, "dm_w / 2", "DMPanel")
    dm_body = dm_ext.bodies.item(0)
    dm_body.name = "Deadman"

    # Deadman dog holes — vertical column on front face
    dm_front_face = af.find_face(dm_body, "y", -1)
    dm_sk = dm_c.sketches.add(dm_front_face)
    dm_sk.name = "DMDog_Sk"
    dm_m2s = dm_sk.modelToSketchSpace
    P = adsk.core.Point3D
    dm_cx = ev("mid_x")
    dm_y = ev("(leg_d - ls_t) / 2")
    dm_z0 = ev("ls_z + ls_w + dog_sp")
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

    # Chop — full-height slab in front of FL leg (Y < 0)
    vise_chop_pl = af.off_plane(vise_c, root.xZConstructionPlane,
        "0 in - vise_chop_t", "ViseChop_Pl")
    _, pr = af.sketch_rect_model(vise_c, vise_chop_pl,
        ("leg_setback", "0 in - vise_chop_t", "0 in"),
        {"x": "leg_w", "z": "bench_h"},
        "ViseChop_Sk", ev=ev)
    chop_ext = af.ext_new(vise_c, pr, "vise_chop_t", "ViseChop")
    chop_body = chop_ext.bodies.item(0)
    chop_body.name = "Vise_Chop"

    # Screw — cylinder along Y through chop and leg
    vise_screw_pl = af.off_plane(vise_c, root.xZConstructionPlane,
        "0 in - vise_chop_t", "ViseScrew_Pl")
    screw_sk = vise_c.sketches.add(vise_screw_pl)
    screw_sk.name = "ViseScrew_Sk"
    screw_m2s = screw_sk.modelToSketchSpace
    P = adsk.core.Point3D
    screw_ctr = screw_m2s(P.create(
        ev("leg_setback + leg_w / 2"),
        ev("0 in - vise_chop_t"),
        ev("vise_screw_z")))
    screw_r = ev("vise_screw_dia") / 2
    screw_sk.sketchCurves.sketchCircles.addByCenterRadius(
        P.create(screw_ctr.x, screw_ctr.y, 0), screw_r)
    screw_circle = screw_sk.sketchCurves.sketchCircles.item(0)
    screw_sk.sketchDimensions.addRadialDimension(
        screw_circle, P.create(screw_ctr.x + screw_r + 1, screw_ctr.y, 0)
    ).parameter.expression = "vise_screw_dia / 2"
    screw_prof = af.smallest_profile(screw_sk)
    screw_ext = af.ext_new(vise_c, screw_prof, "vise_chop_t + leg_d", "ViseScrew")
    screw_body = screw_ext.bodies.item(0)
    screw_body.name = "Vise_Screw"

    # Handle — cylinder along X on front face of chop
    vise_handle_pl = af.off_plane(vise_c, root.yZConstructionPlane,
        "leg_setback + leg_w / 2", "ViseHandle_Pl")
    handle_sk = vise_c.sketches.add(vise_handle_pl)
    handle_sk.name = "ViseHandle_Sk"
    handle_m2s = handle_sk.modelToSketchSpace
    handle_ctr = handle_m2s(P.create(
        ev("leg_setback + leg_w / 2"),
        ev("0 in - vise_chop_t"),
        ev("vise_screw_z")))
    handle_r = ev("vise_handle_dia") / 2
    handle_sk.sketchCurves.sketchCircles.addByCenterRadius(
        P.create(handle_ctr.x, handle_ctr.y, 0), handle_r)
    handle_circle = handle_sk.sketchCurves.sketchCircles.item(0)
    handle_sk.sketchDimensions.addRadialDimension(
        handle_circle, P.create(handle_ctr.x + handle_r + 1, handle_ctr.y, 0)
    ).parameter.expression = "vise_handle_dia / 2"
    handle_prof = af.smallest_profile(handle_sk)
    handle_ext = af.ext_new_sym(vise_c, handle_prof, "vise_handle_l / 2", "ViseHandle")
    handle_body = handle_ext.bodies.item(0)
    handle_body.name = "Vise_Handle"

    # Parallel guide — rectangular board along Y through leg
    vise_guide_pl = af.off_plane(vise_c, root.xZConstructionPlane,
        "0 in - vise_chop_t", "ViseGuide_Pl")
    _, pr = af.sketch_rect_model(vise_c, vise_guide_pl,
        ("leg_setback + (leg_w - vise_guide_w) / 2",
         "0 in - vise_chop_t",
         "vise_guide_z - vise_guide_h / 2"),
        {"x": "vise_guide_w", "z": "vise_guide_h"},
        "ViseGuide_Sk", ev=ev)
    guide_ext = af.ext_new(vise_c, pr, "vise_chop_t + leg_d", "ViseGuide")
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
