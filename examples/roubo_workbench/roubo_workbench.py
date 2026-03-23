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
        # Through-tenon: legs through top
        ("lt_tw",        "3.5 in",   "in", "Leg tenon width (X)"),
        ("lt_tt",        "3.5 in",   "in", "Leg tenon thickness (Y)"),
        ("lt_proud",     "0.25 in",  "in", "Leg tenon proud above top"),
        # Through-tenon: long stretchers through legs
        ("st_tw",        "3 in",     "in", "Stretcher tenon width (Z)"),
        ("st_tt",        "1.5 in",   "in", "Stretcher tenon thickness (Y)"),
        # Blind M&T: short stretchers into long stretchers
        ("sst_tw",       "2.5 in",   "in", "Short stretcher tenon width (Z)"),
        ("sst_tt",       "1.5 in",   "in", "Short stretcher tenon thickness (X)"),
        ("sst_td",       "1.5 in",   "in", "Short stretcher tenon depth (Y)"),
        # Deadman
        ("dm_thick",     "1.5 in",   "in", "Deadman panel thickness"),
        ("dm_w",         "4 in",     "in", "Deadman width (X)"),
        ("dm_gap",       "1 in",     "in", "Gap between deadman top and top underside"),
        # Dog holes
        ("dog_dia",      "0.75 in",  "in", "Dog hole diameter"),
        ("dog_sp",       "4 in",     "in", "Dog hole spacing"),
        ("dog_inset",    "1.75 in",  "in", "Dog hole center from front edge"),
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
        # Short stretcher spans between long stretcher inner faces
        ("ss_len",       "bench_w - 2 * ls_t", "in",
         "Short stretcher length"),
        # Deadman height: from top of front LS to underside of top, minus gap
        ("dm_h",         "leg_h - ls_z - ls_w - dm_gap", "in",
         "Deadman panel height"),
        # Dog hole count
        ("dog_count",    "floor((ls_span - leg_w) / dog_sp)", "",
         "Number of dog holes"),
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

    # Through-tenon on top of FL leg (reduced section, centered)
    leg_top_face = af.find_face(leg_fl, "z", +1)
    _, pr = af.sketch_rect_model(leg_c, leg_top_face,
        ("leg_setback + (leg_w - lt_tw) / 2",
         "(leg_d - lt_tt) / 2",
         "leg_h"),
        {"x": "lt_tw", "y": "lt_tt"},
        "LegTenFL_Sk", ev=ev)
    pr = af.smallest_profile(leg_c.sketches.itemByName("LegTenFL_Sk"))
    lt_ext = af.ext_new(leg_c, pr, "top_thick + lt_proud", "LegTenFL")
    lt_body = lt_ext.bodies.item(0)
    lt_body.name = "LegTen_FL"
    af.combine(leg_c, leg_fl, lt_body, JOIN, False, "LegTenFL_Join")

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
    #  SHORT STRETCHERS (blind tenon into LS, same Z as LS)
    # ==============================================================
    ss_occ = af.make_comp(root, "ShortStretchers")
    ss_c = ss_occ.component

    # Left SS: centered on left leg (X), between LS inner faces (Y)
    # X center: leg_setback + leg_w / 2
    # Y range: (leg_d - ls_t)/2 + ls_t  to  bench_w - (leg_d - ls_t)/2 - ls_t
    #         = (leg_d + ls_t)/2         to  bench_w - (leg_d + ls_t)/2
    ss_pl_l = af.off_plane(ss_c, root.yZConstructionPlane,
        "leg_setback + leg_w / 2", "SSLeft_Pl")
    _, pr = af.sketch_rect_model(ss_c, ss_pl_l,
        ("0 in",
         "(leg_d + ls_t) / 2",
         "ls_z + ls_w / 2 - ss_w / 2"),
        {"y": "bench_w - leg_d - ls_t", "z": "ss_w"},
        "SSLeft_Sk", ev=ev)
    ss_left_ext = af.ext_new_sym(ss_c, pr, "ss_t / 2", "SSLeft")
    ss_left = ss_left_ext.bodies.item(0)
    ss_left.name = "SS_Left"

    # Front tenon (into front LS)
    ss_front_face = af.find_face(ss_left, "y", -1)
    _, pr = af.sketch_rect_model(ss_c, ss_front_face,
        ("leg_setback + leg_w / 2 - sst_tt / 2",
         "(leg_d + ls_t) / 2",
         "ls_z + ls_w / 2 - sst_tw / 2"),
        {"x": "sst_tt", "z": "sst_tw"},
        "SSTenLF_Sk", ev=ev)
    pr = af.smallest_profile(ss_c.sketches.itemByName("SSTenLF_Sk"))
    sst_f_ext = af.ext_new(ss_c, pr, "sst_td", "SSTenLF")
    sst_f = sst_f_ext.bodies.item(0)
    sst_f.name = "SSTen_LF"

    # Back tenon (into back LS)
    ss_back_face = af.find_face(ss_left, "y", +1)
    _, pr = af.sketch_rect_model(ss_c, ss_back_face,
        ("leg_setback + leg_w / 2 - sst_tt / 2",
         "bench_w - (leg_d + ls_t) / 2",
         "ls_z + ls_w / 2 - sst_tw / 2"),
        {"x": "sst_tt", "z": "sst_tw"},
        "SSTenLB_Sk", ev=ev)
    pr = af.smallest_profile(ss_c.sketches.itemByName("SSTenLB_Sk"))
    sst_b_ext = af.ext_new(ss_c, pr, "sst_td", "SSTenLB")
    sst_b = sst_b_ext.bodies.item(0)
    sst_b.name = "SSTen_LB"

    # JOIN both tenons to SS_Left
    af.combine(ss_c, ss_left, [sst_f, sst_b], JOIN, False, "SSTenL_Join")

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

    # CUT legs with short stretcher proxies (SS passes through legs)
    ss_proxies = get_proxies(ss_occ)
    for i in range(leg_c.bRepBodies.count):
        lp = leg_c.bRepBodies.item(i).createForAssemblyContext(leg_occ)
        af.combine(root, lp, ss_proxies, CUT, True, f"SSMort_Leg{i}")

    # CUT long stretchers with short stretcher proxies (blind mortises)
    ss_proxies = get_proxies(ss_occ)
    for i in range(ls_c.bRepBodies.count):
        ls_proxy = ls_c.bRepBodies.item(i).createForAssemblyContext(ls_occ)
        af.combine(root, ls_proxy, ss_proxies, CUT, True, f"SSMort_LS{i}")

    # ==============================================================
    #  DOG HOLES (row along front edge of top)
    # ==============================================================
    # Dog holes: cylindrical CUTs through the top
    # First hole at X = leg_setback + leg_w + dog_sp
    # Pattern along X with dog_sp spacing
    dog_x0 = ev("leg_setback + leg_w + dog_sp")
    dog_y = ev("dog_inset")
    dog_z = ev("leg_h")
    dog_r = ev("dog_dia") / 2

    top_top_face = af.find_face(top_c.bRepBodies.item(0), "z", +1)
    sk = top_c.sketches.add(top_top_face)
    sk.name = "DogHole_Sk"
    # Sketch circle on top face — need to convert model coords to sketch space
    m2s = sk.modelToSketchSpace
    P = adsk.core.Point3D
    center_sk = m2s(P.create(dog_x0, dog_y, ev("bench_h")))
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        P.create(center_sk.x, center_sk.y, 0), dog_r)
    # Dimension the radius
    circle = sk.sketchCurves.sketchCircles.item(0)
    sk.sketchDimensions.addRadialDimension(
        circle, P.create(center_sk.x + dog_r + 1, center_sk.y, 0)
    ).parameter.expression = "dog_dia / 2"

    dog_prof = sk.profiles.item(0)
    dog_ext = af.ext_op(top_c, dog_prof, "top_thick", CUT,
                        top_c.bRepBodies.item(0), "DogHole", flip=True)

    # Pattern dog holes along X
    dog_count = int(ev("dog_count"))
    if dog_count > 1:
        af.feat_pattern(top_c, dog_ext, top_c.xConstructionAxis,
                        "dog_count", "dog_sp", "DogHole_Pat")

    # ==============================================================
    #  DETAILS — chamfers
    # ==============================================================
    # Top slab — chamfer top edges (Z = bench_h)
    top_b = top_c.bRepBodies.item(0)
    top_top_z = ev("bench_h")
    edges = adsk.core.ObjectCollection.create()
    for i in range(top_b.edges.count):
        e = top_b.edges.item(i)
        sv = e.startVertex.geometry
        ev2 = e.endVertex.geometry
        if abs(sv.z - top_top_z) < 0.01 and abs(ev2.z - top_top_z) < 0.01:
            # Skip edges around dog holes (circular)
            if e.geometry.curveType == adsk.core.Curve3DTypes.Line3DCurveType:
                edges.add(e)
    if edges.count > 0:
        ch_inp = top_c.features.chamferFeatures.createInput2()
        ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
            edges, VI("ch_top"), True)
        ch = top_c.features.chamferFeatures.add(ch_inp)
        ch.name = "TopEdge_Ch"

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
