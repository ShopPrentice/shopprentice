"""
Roubo Workbench
===============
72"L x 24"W x 34"H. Classic Andre Roubo French workbench.
Massive slab top, heavy legs with through-tenons, stretchers
with through-tenons through legs.

Coordinate system:
  X = length (72")  Y = width/depth (24")  Z = height (34")
"""
import adsk.core, adsk.fusion

from helpers import af
from helpers.templates import mortise_tenon as mt

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
        ("bench_l",      "72 in",    "in", "Overall length"),
        ("bench_w",      "24 in",    "in", "Overall width/depth"),
        ("bench_h",      "34 in",    "in", "Overall height"),
        # Top
        ("top_thick",    "4 in",     "in", "Slab top thickness"),
        # Legs
        ("leg_size",     "5 in",     "in", "Leg cross-section (square)"),
        ("leg_inset",    "3 in",     "in", "Leg inset from top edge"),
        # Long stretchers (front/back, grain in X, full section through legs)
        ("ls_w",         "4 in",     "in", "Long stretcher width (height)"),
        ("ls_t",         "3 in",     "in", "Long stretcher thickness"),
        ("ls_z",         "8 in",     "in", "Long stretcher bottom Z"),
        ("ls_proud",     "0.25 in",  "in", "Long stretcher proud past leg"),
        # Short stretchers (left/right, grain in Y)
        ("ss_w",         "3.5 in",   "in", "Short stretcher width (height)"),
        ("ss_t",         "2.5 in",   "in", "Short stretcher thickness"),
    ]:
        params.add(pname, VI(expr), unit, desc)

    # Through-tenon: legs through top (reduced section)
    for pname, expr, unit, desc in [
        ("lt_tw",        "3.5 in",   "in", "Leg tenon width (X)"),
        ("lt_tt",        "3.5 in",   "in", "Leg tenon thickness (Y)"),
        ("lt_proud",     "0.25 in",  "in", "Leg tenon proud above top"),
    ]:
        params.add(pname, VI(expr), unit, desc)

    # Blind M&T: short stretchers into long stretchers
    for pname, expr, unit, desc in [
        ("sst_tw",       "2 in",     "in", "Short stretcher tenon width"),
        ("sst_tt",       "1.5 in",   "in", "Short stretcher tenon thickness"),
        ("sst_td",       "1.5 in",   "in", "Short stretcher tenon depth"),
    ]:
        params.add(pname, VI(expr), unit, desc)

    # Derived
    for pname, expr, unit, desc in [
        ("leg_h",        "bench_h - top_thick",  "in", "Leg height"),
        ("inner_l",      "bench_l - 2 * leg_inset - leg_size", "in",
         "Length between leg inner faces"),
        ("inner_w",      "bench_w - 2 * leg_inset - leg_size", "in",
         "Width between leg inner faces"),
        ("mid_x",        "bench_l / 2", "in", "X midplane"),
        ("mid_y",        "bench_w / 2", "in", "Y midplane"),
        # Long stretcher: full section passes through legs + proud on each end
        ("ls_len",       "inner_l + leg_size + 2 * ls_proud", "in",
         "Long stretcher total length (through legs + proud)"),
        # Short stretcher length between long stretcher inner faces
        ("ss_len",       "inner_w - 2 * ls_t", "in",
         "Short stretcher length between LS inner faces"),
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
    #  LEGS (with through-tenon on top, before mirroring)
    # ==============================================================
    leg_occ = af.make_comp(root, "Legs")
    leg_c = leg_occ.component

    # FL leg body
    _, pr = af.sketch_rect_model(leg_c, root.xYConstructionPlane,
        ("leg_inset", "leg_inset", "0 in"),
        {"x": "leg_size", "y": "leg_size"},
        "LegFL_Sk", ev=ev)
    leg_fl_ext = af.ext_new(leg_c, pr, "leg_h", "LegFL")
    leg_fl = leg_fl_ext.bodies.item(0)
    leg_fl.name = "Leg_FL"

    # Through-tenon on top of FL leg (reduced section, centered)
    leg_top_face = af.find_face(leg_fl, "z", +1)
    _, pr = af.sketch_rect_model(leg_c, leg_top_face,
        ("leg_inset + (leg_size - lt_tw) / 2",
         "leg_inset + (leg_size - lt_tt) / 2",
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
    #  LONG STRETCHERS (full section through legs, no shoulders)
    # ==============================================================
    ls_occ = af.make_comp(root, "LongStretchers")
    ls_c = ls_occ.component

    # Front long stretcher: starts at leg_inset - ls_proud
    ls_front_pl = af.off_plane(ls_c, root.xZConstructionPlane,
        "leg_inset", "LSFront_Pl")
    _, pr = af.sketch_rect_model(ls_c, ls_front_pl,
        ("leg_inset - ls_proud", "leg_inset", "ls_z"),
        {"x": "ls_len", "z": "ls_w"},
        "LSFront_Sk", ev=ev)
    ls_front_ext = af.ext_new(ls_c, pr, "ls_t", "LSFront")
    ls_front = ls_front_ext.bodies.item(0)
    ls_front.name = "LS_Front"

    mir_ls = af.mirror_body(ls_c, ls_front, YMid, "LSMirY")
    ls_back = mir_ls.bodies.item(0)
    ls_back.name = "LS_Back"

    # ==============================================================
    #  SHORT STRETCHERS (with blind tenons, before mirroring)
    # ==============================================================
    ss_occ = af.make_comp(root, "ShortStretchers")
    ss_c = ss_occ.component

    # Left short stretcher body: centered on left leg X, between LS inner faces
    ss_pl_l = af.off_plane(ss_c, root.yZConstructionPlane,
        "leg_inset + leg_size / 2", "SSLeft_Pl")
    _, pr = af.sketch_rect_model(ss_c, ss_pl_l,
        ("0 in", "leg_inset + ls_t", "ls_z + ls_w / 2 - ss_w / 2"),
        {"y": "ss_len", "z": "ss_w"},
        "SSLeft_Sk", ev=ev)
    ss_left_ext = af.ext_new_sym(ss_c, pr, "ss_t / 2", "SSLeft")
    ss_left = ss_left_ext.bodies.item(0)
    ss_left.name = "SS_Left"

    # Blind tenon on front end of SS_Left (into LS_Front)
    ss_front_face = af.find_face(ss_left, "y", -1)
    _, pr = af.sketch_rect_model(ss_c, ss_front_face,
        ("leg_inset + leg_size / 2 - sst_tt / 2",
         "leg_inset + ls_t",
         "ls_z + ls_w / 2 - sst_tw / 2"),
        {"x": "sst_tt", "z": "sst_tw"},
        "SSTenLF_Sk", ev=ev)
    pr = af.smallest_profile(ss_c.sketches.itemByName("SSTenLF_Sk"))
    sst_f_ext = af.ext_new(ss_c, pr, "sst_td", "SSTenLF")
    sst_f = sst_f_ext.bodies.item(0)
    sst_f.name = "SSTen_LF"

    # Blind tenon on back end of SS_Left (into LS_Back)
    ss_back_face = af.find_face(ss_left, "y", +1)
    _, pr = af.sketch_rect_model(ss_c, ss_back_face,
        ("leg_inset + leg_size / 2 - sst_tt / 2",
         "leg_inset + ls_t + ss_len",
         "ls_z + ls_w / 2 - sst_tw / 2"),
        {"x": "sst_tt", "z": "sst_tw"},
        "SSTenLB_Sk", ev=ev)
    pr = af.smallest_profile(ss_c.sketches.itemByName("SSTenLB_Sk"))
    sst_b_ext = af.ext_new(ss_c, pr, "sst_td", "SSTenLB")
    sst_b = sst_b_ext.bodies.item(0)
    sst_b.name = "SSTen_LB"

    # JOIN both tenons to SS_Left
    af.combine(ss_c, ss_left, [sst_f, sst_b], JOIN, False, "SSTenL_Join")

    # Mirror SS_Left (with tenons) across XMid → SS_Right
    mir_ss = af.mirror_body(ss_c, ss_left, XMid, "SSMirX")
    ss_right = mir_ss.bodies.item(0)
    ss_right.name = "SS_Right"

    # ==============================================================
    #  CROSS-COMPONENT CUTS (root level, via assembly proxies)
    # ==============================================================

    # Helper to get all bodies from a component as assembly proxies
    def get_proxies(occ):
        c = occ.component
        return [c.bRepBodies.item(i).createForAssemblyContext(occ)
                for i in range(c.bRepBodies.count)]

    # CUT top with all 4 leg proxies (through-tenon mortises)
    top_proxy = top_c.bRepBodies.item(0).createForAssemblyContext(top_occ)
    leg_proxies = get_proxies(leg_occ)
    af.combine(root, top_proxy, leg_proxies, CUT, True, "LegMortise_Cut")

    # CUT legs with long stretcher proxies (through-mortises)
    # Each LS passes through 2 legs. CUT all 4 legs with both stretchers.
    ls_proxies = get_proxies(ls_occ)
    for i, lp in enumerate(leg_proxies):
        # Re-find leg proxy after previous CUT may have invalidated it
        lp = leg_c.bRepBodies.item(i).createForAssemblyContext(leg_occ)
        af.combine(root, lp, ls_proxies, CUT, True, f"LSMort_Leg{i}")

    # CUT legs with short stretcher proxies (SS passes through legs too)
    ss_proxies = get_proxies(ss_occ)
    for i in range(leg_c.bRepBodies.count):
        lp = leg_c.bRepBodies.item(i).createForAssemblyContext(leg_occ)
        af.combine(root, lp, ss_proxies, CUT, True, f"SSMort_Leg{i}")

    # CUT long stretchers with short stretcher proxies (blind mortises)
    ss_proxies = get_proxies(ss_occ)
    for i in range(ls_c.bRepBodies.count):
        ls_proxy = ls_c.bRepBodies.item(i).createForAssemblyContext(ls_occ)
        af.combine(root, ls_proxy, ss_proxies, CUT, True,
                   f"SSMort_LS{i}")

    # ==============================================================
    #  DETAILS — chamfers
    # ==============================================================
    params.add("ch_top", VI("0.125 in"), "in", "Top edge chamfer")
    params.add("ch_leg", VI("0.0625 in"), "in", "Leg bottom chamfer")

    # Top slab — chamfer all top edges (Z = bench_h)
    top_p = top_c.bRepBodies.item(0)
    top_top_z = ev("bench_h")
    edges = adsk.core.ObjectCollection.create()
    for i in range(top_p.edges.count):
        e = top_p.edges.item(i)
        sv = e.startVertex.geometry
        ev2 = e.endVertex.geometry
        if abs(sv.z - top_top_z) < 0.01 and abs(ev2.z - top_top_z) < 0.01:
            edges.add(e)
    if edges.count > 0:
        ch_inp = top_c.features.chamferFeatures.createInput2()
        ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
            edges, VI("ch_top"), True)
        ch = top_c.features.chamferFeatures.add(ch_inp)
        ch.name = "TopEdge_Ch"

    # Leg bottoms — chamfer all Z=0 edges on each leg
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
