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

from helpers import sp

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation


def _refs_to_construction(sk):
    """Convert projected/reference lines to construction (no profile splits).

    Inline fallback — use sp.refs_to_construction() once addin is restarted.
    """
    for i in range(sk.sketchCurves.sketchLines.count):
        ln = sk.sketchCurves.sketchLines.item(i)
        if ln.isReference:
            ln.isConstruction = True


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
        ("st_blind",     "1 in",     "in", "Blind tenon stop depth inside leg"),
        # Drawbore pins
        ("pin_dia",      "0.375 in", "in", "Drawbore pin diameter"),
        ("pin_sp",       "2 in",     "in", "Vertical spacing between 2 pins"),
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

    # ==============================================================
    #  MIDPLANES
    # ==============================================================
    XMid = sp.off_plane(root, root.yZConstructionPlane, "mid_x", "XMid")
    YMid = sp.off_plane(root, root.xZConstructionPlane, "mid_y", "YMid")

    # ==============================================================
    #  TOP
    # ==============================================================
    top_occ = sp.make_comp(root, "Top")
    top_c = top_occ.component

    _, pr = sp.sketch_rect_model(top_c, root.xZConstructionPlane,
        ("0 in", "0 in", "leg_h"),
        {"x": "bench_l", "z": "top_thick"},
        "Top_Sk", ev=ev)
    top_ext = sp.ext_new(top_c, pr, "bench_w", "TopSlab")
    top_body = top_ext.bodies.item(0)
    top_body.name = "Top"

    # ==============================================================
    #  LEGS (front flush Y=0, back flush Y=bench_w-leg_d)
    # ==============================================================
    leg_occ = sp.make_comp(root, "Legs")
    leg_c = leg_occ.component

    # FL leg: front-left corner
    _, pr = sp.sketch_rect_model(leg_c, root.xYConstructionPlane,
        ("leg_setback", "0 in", "0 in"),
        {"x": "leg_w", "y": "leg_d"},
        "LegFL_Sk", ev=ev)
    leg_fl_ext = sp.ext_new(leg_c, pr, "leg_h", "LegFL")
    leg_fl = leg_fl_ext.bodies.item(0)
    leg_fl.name = "Leg_FL"

    # Roubo paired joint on FL leg top: dovetail (front) + tenon (back), flush
    # Layout from front (Y=0): dovetail | gap | tenon | shoulder
    # Sketch on the mating surface (leg top face) so all dimensions are
    # relative to the leg, not to the table origin.  Full-width tenons
    # cause sketch edges to coincide with auto-projected face edges,
    # creating fragment profiles — refs_to_construction clears them.
    leg_top_face = sp.find_face(leg_fl, "z", +1)

    def _face_fl_pt(sketch):
        """Front-left corner sketch point of the projected face boundary."""
        best = None
        seen = set()
        for i in range(sketch.sketchCurves.sketchLines.count):
            ln = sketch.sketchCurves.sketchLines.item(i)
            if not ln.isReference:
                continue
            for skpt in [ln.startSketchPoint, ln.endSketchPoint]:
                if id(skpt) not in seen:
                    seen.add(id(skpt))
                    g = skpt.geometry
                    if best is None or (g.x + g.y) < (best.geometry.x + best.geometry.y):
                        best = skpt
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

    _refs_to_construction(sk_dt)
    dt_pr = sp.smallest_profile(sk_dt)
    dt_ext = sp.ext_new(leg_c, dt_pr, "top_thick", "DT_FL")
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

    _refs_to_construction(sk_mt)
    mt_pr = sp.smallest_profile(sk_mt)
    mt_ext = sp.ext_new(leg_c, mt_pr, "top_thick", "MT_FL")
    mt_body = mt_ext.bodies.item(0)
    mt_body.name = "MT_FL"

    # JOIN both tenons to FL leg
    sp.combine(leg_fl, [dt_body, mt_body], JOIN, False, "LegJt_FL_Join")

    # Mirror across XMid → FR, then across YMid → BL, BR
    mir_x = sp.mirror_body(leg_c, leg_fl, XMid, "LegMirX")
    leg_fr = mir_x.bodies.item(0)
    leg_fr.name = "Leg_FR"

    mir_y = sp.mirror_bodies(leg_c, [leg_fl, leg_fr], YMid, "LegMirY")
    mir_y.bodies.item(0).name = "Leg_BL"
    mir_y.bodies.item(1).name = "Leg_BR"

    # -- Body-relative references: stretchers + top relative to legs --
    ref_leg_fl = find_body("Leg_FL")
    ref_leg_fl_bb = ref_leg_fl.boundingBox
    ref_leg_fr = find_body("Leg_FR")
    ref_leg_fr_bb = ref_leg_fr.boundingBox
    ref_leg_bl = find_body("Leg_BL")
    ref_leg_bl_bb = ref_leg_bl.boundingBox

    # ==============================================================
    #  LONG STRETCHERS — proper combine-based joinery workflow:
    #  1. Stretcher body (full cross-section, spans between legs)
    #  2. Sketch tenon on end face → extrude through leg + proud
    #  3. Sketch drawbore pins → extrude through leg
    #  4. Mirror tenon + pins to other end
    #  5. JOIN tenons to stretcher, CUT tenon with pins
    #  6. Mirror everything across YMid for back stretcher
    # ==============================================================
    ls_occ = sp.make_comp(root, "LongStretchers")
    ls_c = ls_occ.component
    P = adsk.core.Point3D

    # 1. Stretcher body — full cross-section, FLUSH with front face of leg (Y=0)
    ls_body_pl = sp.off_plane(ls_c, root.xZConstructionPlane,
        "0 in", "LSBody_Pl")
    _, pr = sp.sketch_rect_model(ls_c, ls_body_pl,
        ("leg_setback + leg_w",
         "0 in",
         "ls_z"),
        {"x": "bench_l - 2 * leg_setback - 2 * leg_w", "z": "ls_w"},
        "LSBody_Sk", ev=ev)
    ls_body_ext = sp.ext_new(ls_c, pr, "ls_t", "LSBody")
    ls_front = ls_body_ext.bodies.item(0)
    ls_front.name = "LS_Front"

    # 2. Left tenon — plane at outer end (proud face), extrude inward
    #    Tenon Y centered on STRETCHER (which is now flush-front at Y=[0, ls_t])
    ls_tenon_pl = sp.off_plane(ls_c, root.yZConstructionPlane,
        "leg_setback - ls_proud", "LSTenon_Pl")
    _, pr = sp.sketch_rect_model(ls_c, ls_tenon_pl,
        ("leg_setback - ls_proud",
         "(ls_t - st_tt) / 2",
         "ls_z"),
        {"y": "st_tt", "z": "ls_w"},
        "LSTenon_L_Sk", ev=ev)
    ls_tenon_l = sp.ext_new(ls_c, pr, "leg_w + ls_proud", "LSTenon_L")
    ls_tenon_l_body = ls_tenon_l.bodies.item(0)
    ls_tenon_l_body.name = "LS_Tenon_L"

    # 3. Drawbore pins — sketch on XZ plane, 2 circles at 1/3 into leg from shoulder
    #    Pins go in Y direction (through leg cheek, perpendicular to tenon)
    ls_pin_sk = ls_c.sketches.add(root.xZConstructionPlane)
    ls_pin_sk.name = "LSPinL_Sk"
    m = ls_pin_sk.modelToSketchSpace
    for z_expr in ["ls_z + ls_w / 2 - pin_sp / 2",
                    "ls_z + ls_w / 2 + pin_sp / 2"]:
        ctr = m(P.create(ev("leg_setback + 2 * leg_w / 3"), 0, ev(z_expr)))
        ls_pin_sk.sketchCurves.sketchCircles.addByCenterRadius(
            P.create(ctr.x, ctr.y, 0), ev("pin_dia") / 2)
    d = ls_pin_sk.sketchDimensions
    c0 = ls_pin_sk.sketchCurves.sketchCircles.item(0)
    c1 = ls_pin_sk.sketchCurves.sketchCircles.item(1)
    g0 = c0.centerSketchPoint.geometry
    g1 = c1.centerSketchPoint.geometry
    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
    d.addRadialDimension(c0, P.create(g0.x + 0.5, g0.y, 0)
    ).parameter.expression = "pin_dia / 2"
    d.addRadialDimension(c1, P.create(g1.x + 0.5, g1.y, 0)
    ).parameter.expression = "pin_dia / 2"
    d.addDistanceDimension(ls_pin_sk.originPoint, c0.centerSketchPoint,
        H, P.create(g0.x / 2, g0.y - 1, 0)
    ).parameter.expression = "leg_setback + 2 * leg_w / 3"
    d.addDistanceDimension(ls_pin_sk.originPoint, c0.centerSketchPoint,
        V, P.create(g0.x - 1, g0.y / 2, 0)
    ).parameter.expression = "ls_z + ls_w / 2 - pin_sp / 2"
    d.addDistanceDimension(c0.centerSketchPoint, c1.centerSketchPoint,
        V, P.create(g0.x - 1, (g0.y + g1.y) / 2, 0)
    ).parameter.expression = "pin_sp"
    _refs_to_construction(ls_pin_sk)
    ls_pin_bodies = []
    for j in range(ls_pin_sk.profiles.count):
        p = ls_pin_sk.profiles.item(j)
        if p.areaProperties().area < 1.0:
            ext = sp.ext_new(ls_c, p, "leg_d", f"LSPinL_{j}")
            ext.bodies.item(0).name = f"LSPinL_{j}"
            ls_pin_bodies.append(ext.bodies.item(0))

    # 4. Mirror tenon + pins to right end across XMid
    mir_tenon = sp.mirror_bodies(ls_c,
        [ls_tenon_l_body] + ls_pin_bodies, XMid, "LSMirTenon")

    # 5. JOIN all tenons to stretcher, CUT tenons with pins
    all_tenons = []
    all_pins = []
    for i in range(ls_c.bRepBodies.count):
        b = ls_c.bRepBodies.item(i)
        if "Tenon" in b.name:
            all_tenons.append(b)
        elif "Pin" in b.name:
            all_pins.append(b)
    if all_tenons:
        sp.combine(ls_front, all_tenons, JOIN, False, "LSTenonJoin")
    if all_pins:
        sp.combine(ls_front, all_pins, CUT, True, "LSPinCut")

    # 6. Mirror everything across YMid → LS_Back
    _ls_bodies = [ls_c.bRepBodies.item(i) for i in range(ls_c.bRepBodies.count)]
    mir_ls = sp.mirror_bodies(ls_c, _ls_bodies, YMid, "LSMirY")
    for i in range(mir_ls.bodies.count):
        b = mir_ls.bodies.item(i)
        if b.volume > 100:  # stretcher, not pin
            b.name = "LS_Back"
            break

    # ==============================================================
    #  SHORT STRETCHERS — same workflow, blind tenon variant:
    #  Tenon extrudes into leg (not through), pin extrudes through leg
    # ==============================================================
    ss_occ = sp.make_comp(root, "ShortStretchers")
    ss_c = ss_occ.component

    # 1. Stretcher body — flush with OUTER face of left leg (X = leg_setback)
    ss_body_pl = sp.off_plane(ss_c, root.yZConstructionPlane,
        "leg_setback + ss_t / 2", "SSBody_Pl")
    _, pr = sp.sketch_rect_model(ss_c, ss_body_pl,
        ("leg_setback + ss_t / 2",
         "leg_d",
         "ls_z"),
        {"y": "bench_w - 2 * leg_d", "z": "ss_w"},
        "SSBody_Sk", ev=ev)
    ss_body_ext = sp.ext_new_sym(ss_c, pr, "ss_t / 2", "SSBody")
    ss_left = ss_body_ext.bodies.item(0)
    ss_left.name = "SS_Left"

    # 2. Front tenon — plane at blind stop point (Y = st_blind),
    #    extrude in +Y to stretcher front end (Y = leg_d). ✓
    ss_tenon_pl = sp.off_plane(ss_c, root.xZConstructionPlane,
        "st_blind", "SSTenon_Pl")
    _, pr = sp.sketch_rect_model(ss_c, ss_tenon_pl,
        ("leg_setback + (ss_t - st_tt) / 2",
         "st_blind",
         "ls_z"),
        {"x": "st_tt", "z": "ss_w"},
        "SSTenon_F_Sk", ev=ev)
    ss_tenon_f = sp.ext_new(ss_c, pr, "leg_d - st_blind", "SSTenon_F")
    ss_tenon_f_body = ss_tenon_f.bodies.item(0)
    ss_tenon_f_body.name = "SS_Tenon_F"

    # 3. Drawbore pins — sketch on YZ plane (normal=X) so pin goes through
    #    leg side, perpendicular to tenon which goes in Y
    ss_pin_pl = sp.off_plane(ss_c, root.yZConstructionPlane,
        "leg_setback", "SSPinF_Pl")
    ss_pin_sk = ss_c.sketches.add(ss_pin_pl)
    ss_pin_sk.name = "SSPinF_Sk"
    m = ss_pin_sk.modelToSketchSpace
    # Detect axis mapping on YZ plane
    _ss_o = m(P.create(ev("leg_setback"), 0, 0))
    _ss_ty = m(P.create(ev("leg_setback"), 1, 0))
    _ss_tz = m(P.create(ev("leg_setback"), 0, 1))
    y_is_H = abs(_ss_ty.x - _ss_o.x) > abs(_ss_ty.y - _ss_o.y)
    y_orient = H if y_is_H else V
    z_orient = V if y_is_H else H

    _pin_y = ev("leg_d - (leg_d - st_blind) / 3")
    for z_expr in ["ls_z + ss_w / 2 - pin_sp / 2",
                    "ls_z + ss_w / 2 + pin_sp / 2"]:
        ctr = m(P.create(ev("leg_setback"), _pin_y, ev(z_expr)))
        ss_pin_sk.sketchCurves.sketchCircles.addByCenterRadius(
            P.create(ctr.x, ctr.y, 0), ev("pin_dia") / 2)
    d = ss_pin_sk.sketchDimensions
    c0 = ss_pin_sk.sketchCurves.sketchCircles.item(0)
    c1 = ss_pin_sk.sketchCurves.sketchCircles.item(1)
    g0 = c0.centerSketchPoint.geometry
    g1 = c1.centerSketchPoint.geometry
    d.addRadialDimension(c0, P.create(g0.x + 0.5, g0.y, 0)
    ).parameter.expression = "pin_dia / 2"
    d.addRadialDimension(c1, P.create(g1.x + 0.5, g1.y, 0)
    ).parameter.expression = "pin_dia / 2"
    d.addDistanceDimension(ss_pin_sk.originPoint, c0.centerSketchPoint,
        y_orient, P.create(g0.x / 2, g0.y - 1, 0)
    ).parameter.expression = "leg_d - (leg_d - st_blind) / 3"
    d.addDistanceDimension(ss_pin_sk.originPoint, c0.centerSketchPoint,
        z_orient, P.create(g0.x - 1, g0.y / 2, 0)
    ).parameter.expression = "ls_z + ss_w / 2 - pin_sp / 2"
    d.addDistanceDimension(c0.centerSketchPoint, c1.centerSketchPoint,
        z_orient, P.create(g0.x - 1, (g0.y + g1.y) / 2, 0)
    ).parameter.expression = "pin_sp"
    _refs_to_construction(ss_pin_sk)
    ss_pin_bodies = []
    for j in range(ss_pin_sk.profiles.count):
        p = ss_pin_sk.profiles.item(j)
        if p.areaProperties().area < 1.0:
            ext = sp.ext_new(ss_c, p, "leg_w", f"SSPinF_{j}")
            ext.bodies.item(0).name = f"SSPinF_{j}"
            ss_pin_bodies.append(ext.bodies.item(0))

    # 4. Mirror tenon + pins to back end across YMid
    mir_ss_tenon = sp.mirror_bodies(ss_c,
        [ss_tenon_f_body] + ss_pin_bodies, YMid, "SSMirTenon")

    # 5. JOIN all tenons to stretcher, CUT tenons with pins
    all_tenons = []
    all_pins = []
    for i in range(ss_c.bRepBodies.count):
        b = ss_c.bRepBodies.item(i)
        if "Tenon" in b.name:
            all_tenons.append(b)
        elif "Pin" in b.name:
            all_pins.append(b)
    if all_tenons:
        sp.combine(ss_left, all_tenons, JOIN, False, "SSTenonJoin")
    if all_pins:
        sp.combine(ss_left, all_pins, CUT, True, "SSPinCut")

    # 6. Mirror everything across XMid → SS_Right
    _ss_bodies = [ss_c.bRepBodies.item(i) for i in range(ss_c.bRepBodies.count)]
    mir_ss = sp.mirror_bodies(ss_c, _ss_bodies, XMid, "SSMirX")
    for i in range(mir_ss.bodies.count):
        b = mir_ss.bodies.item(i)
        if b.volume > 100:
            b.name = "SS_Right"
            break

    # -- Body-relative references: deadman relative to front long stretcher --
    ref_ls_front = find_body("LS_Front")
    ref_ls_front_bb = ref_ls_front.boundingBox
    # SS_Left used by SSPinF_0
    ref_ss_left = find_body("SS_Left")
    ref_ss_left_bb = ref_ss_left.boundingBox

    # ==============================================================
    #  DEADMAN (panel on front stretcher, between front legs)
    # ==============================================================
    dm_occ = sp.make_comp(root, "Deadman")
    dm_c = dm_occ.component

    # Deadman: centered at bench midpoint (X), flush with front LS front face
    # Y: front LS front face = 0 in
    # Z: raised by dm_gap above LS top, with gap at top too
    dm_pl = sp.off_plane(dm_c, root.yZConstructionPlane,
        "mid_x", "DM_Pl")
    _, pr = sp.sketch_rect_model(dm_c, dm_pl,
        ("0 in", "0 in", "ls_z + ls_w + dm_gap"),
        {"y": "dm_thick", "z": "dm_h"},
        "DM_Sk", ev=ev)
    dm_ext = sp.ext_new_sym(dm_c, pr, "dm_w / 2", "DMPanel")
    dm_body = dm_ext.bodies.item(0)
    dm_body.name = "Deadman"

    # Bottom tongue — extends down from panel into LS groove
    _, pr = sp.sketch_rect_model(dm_c, dm_pl,
        ("0 in",
         "(dm_thick - dm_tongue_t) / 2",
         "ls_z + ls_w + dm_gap - dm_tongue_h"),
        {"y": "dm_tongue_t", "z": "dm_tongue_h"},
        "DMTongueBot_Sk", ev=ev)
    dm_tbot_ext = sp.ext_new_sym(dm_c, pr, "dm_w / 2", "DMTongueBot")
    dm_tbot = dm_tbot_ext.bodies.item(0)
    dm_tbot.name = "DM_Tongue_Bot"
    sp.combine(dm_body, [dm_tbot], JOIN, False, "DMTongueBot_Join")

    # Top tongue — extends up from panel into top groove
    _, pr = sp.sketch_rect_model(dm_c, dm_pl,
        ("0 in",
         "(dm_thick - dm_tongue_t) / 2",
         "leg_h - dm_gap"),
        {"y": "dm_tongue_t", "z": "dm_tongue_h"},
        "DMTongueTop_Sk", ev=ev)
    dm_ttop_ext = sp.ext_new_sym(dm_c, pr, "dm_w / 2", "DMTongueTop")
    dm_ttop = dm_ttop_ext.bodies.item(0)
    dm_ttop.name = "DM_Tongue_Top"
    sp.combine(dm_body, [dm_ttop], JOIN, False, "DMTongueTop_Join")

    # Deadman dog holes — vertical column on front face, face-relative.
    # Sketch on the deadman front face. Use m2s to detect axis mapping,
    # then dimension the circle center with parametric expressions.
    dm_front_face = sp.find_face(dm_body, "y", -1)
    dm_sk = dm_c.sketches.add(dm_front_face)
    dm_sk.name = "DMDog_Sk"
    dm_m2s = dm_sk.modelToSketchSpace
    P = adsk.core.Point3D
    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation

    # Detect axis mapping: which sketch direction is model Z?
    _dm_origin = dm_m2s(P.create(ev("mid_x"), ev("0 in"),
                                  ev("ls_z + ls_w + dm_gap")))
    _dm_z_test = dm_m2s(P.create(ev("mid_x"), ev("0 in"),
                                  ev("ls_z + ls_w + dm_gap") + 1))
    _dm_z_is_H = abs(_dm_z_test.x - _dm_origin.x) > abs(_dm_z_test.y - _dm_origin.y)
    _dm_z_orient = H if _dm_z_is_H else V
    _dm_x_orient = V if _dm_z_is_H else H

    # First dog hole — placed near bottom of deadman, offset 2 in from bottom
    dm_z0 = ev("ls_z + ls_w + dm_gap + 2 in")
    dm_r = ev("dog_dia") / 2
    dm_ctr = dm_m2s(P.create(ev("mid_x"), ev("0 in"), dm_z0))
    dm_sk.sketchCurves.sketchCircles.addByCenterRadius(
        P.create(dm_ctr.x, dm_ctr.y, 0), dm_r)
    dm_circle = dm_sk.sketchCurves.sketchCircles.item(0)

    dm_d = dm_sk.sketchDimensions
    dm_d.addRadialDimension(
        dm_circle, P.create(dm_ctr.x + dm_r + 1, dm_ctr.y, 0)
    ).parameter.expression = "dog_dia / 2"
    # X center from sketch origin (centered on deadman = mid_x)
    dm_d.addDistanceDimension(
        dm_sk.originPoint, dm_circle.centerSketchPoint,
        _dm_x_orient, P.create(dm_ctr.x + 1, dm_ctr.y + 1, 0)
    ).parameter.expression = "mid_x"
    # Z offset from origin: bottom of deadman + 2 in
    dm_d.addDistanceDimension(
        dm_sk.originPoint, dm_circle.centerSketchPoint,
        _dm_z_orient, P.create(dm_ctr.x - 1, dm_ctr.y - 1, 0)
    ).parameter.expression = "ls_z + ls_w + dm_gap + 2 in"

    _refs_to_construction(dm_sk)
    dm_dog_prof = sp.smallest_profile(dm_sk)
    dm_dog_ext = sp.ext_op(dm_c, dm_dog_prof, "dm_thick", CUT,
                           dm_body, "DMDogHole", flip=True)

    # Pattern vertically
    dm_dc = int(ev("dm_dog_count"))
    if dm_dc > 1:
        sp.feat_pattern(dm_c, dm_dog_ext, dm_c.zConstructionAxis,
                        "dm_dog_count", "dog_sp", "DMDog_Pat")

    # ==============================================================
    #  LEG VISE (on front-left leg)
    # ==============================================================
    vise_occ = sp.make_comp(root, "LegVise")
    vise_c = vise_occ.component

    # Reference FL leg's left face — vise X positioning follows the leg
    leg_fl_left = sp.find_face(leg_fl, "x", -1).createForAssemblyContext(leg_occ)
    LegFL_Left = sp.off_plane(vise_c, leg_fl_left, "0 in", "LegFL_Left")

    P = adsk.core.Point3D
    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation

    # Runtime X values for initial geometry placement (not in parametric expressions)
    _vise_lx = ev("leg_setback")
    _vise_cx = ev("leg_setback + leg_w / 2")

    # Chop — full-height slab in front of FL leg (Y < 0)
    vise_chop_pl = sp.off_plane(vise_c, root.xZConstructionPlane,
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

    _refs_to_construction(chop_sk)
    chop_ext = sp.ext_new(vise_c, sp.smallest_profile(chop_sk),
        "vise_chop_t", "ViseChop")
    chop_body = chop_ext.bodies.item(0)
    chop_body.name = "Vise_Chop"

    # Chamfer on chop outer front edges: top edge + two vertical side edges
    _chop_max_z = ev("bench_h")
    _chop_min_y = ev("-vise_distance - vise_chop_t")
    _chop_lx = ev("leg_setback") - (ev("vise_chop_w") - ev("leg_w")) / 2
    _chop_rx = _chop_lx + ev("vise_chop_w")
    chop_edges = adsk.core.ObjectCollection.create()
    for j in range(chop_body.edges.count):
        e = chop_body.edges.item(j)
        sv, ev2 = e.startVertex.geometry, e.endVertex.geometry
        on_front = (abs(sv.y - _chop_min_y) < 0.01
                    and abs(ev2.y - _chop_min_y) < 0.01)
        if not on_front:
            continue
        # Top front edge (horizontal, Z=max)
        is_top = (abs(sv.z - _chop_max_z) < 0.01
                  and abs(ev2.z - _chop_max_z) < 0.01)
        # Left front edge (vertical, X=min)
        is_left = (abs(sv.x - _chop_lx) < 0.01
                   and abs(ev2.x - _chop_lx) < 0.01)
        # Right front edge (vertical, X=max)
        is_right = (abs(sv.x - _chop_rx) < 0.01
                    and abs(ev2.x - _chop_rx) < 0.01)
        if is_top or is_left or is_right:
            chop_edges.add(e)
    if chop_edges.count > 0:
        ch_inp = vise_c.features.chamferFeatures.createInput2()
        ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
            chop_edges, VI("ch_vise_chop"), True)
        ch = vise_c.features.chamferFeatures.add(ch_inp)
        ch.name = "ViseChop_Ch"

    # Screw — cylinder along Y through chop and leg
    vise_screw_pl = sp.off_plane(vise_c, root.xZConstructionPlane,
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

    screw_prof = sp.smallest_profile(screw_sk)
    screw_ext = sp.ext_new(vise_c, screw_prof,
        "vise_chop_t + leg_d + vise_handle_gap + vise_distance", "ViseScrew")
    screw_body = screw_ext.bodies.item(0)
    screw_body.name = "Vise_Screw"

    # Handle — cylinder along X, centered on leg
    vise_handle_pl = sp.off_plane(vise_c, LegFL_Left,
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

    handle_prof = sp.smallest_profile(handle_sk)
    handle_ext = sp.ext_new_sym(vise_c, handle_prof,
        "vise_handle_l / 2", "ViseHandle")
    handle_body = handle_ext.bodies.item(0)
    handle_body.name = "Vise_Handle"

    # -- Body-relative references: vise guide + handle relative to chop + screw --
    ref_vise_chop = find_body("Vise_Chop")
    ref_vise_chop_bb = ref_vise_chop.boundingBox
    ref_vise_screw = find_body("Vise_Screw")
    ref_vise_screw_bb = ref_vise_screw.boundingBox

    # Parallel guide — rectangular board along Y through leg
    vise_guide_pl = sp.off_plane(vise_c, root.xZConstructionPlane,
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

    _refs_to_construction(guide_sk)
    guide_ext = sp.ext_new(vise_c, sp.smallest_profile(guide_sk),
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

    top_top_face = sp.find_face(top_c.bRepBodies.item(0), "z", +1)
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

    dog_prof = sp.smallest_profile(sk)
    dog_ext = sp.ext_op(top_c, dog_prof, "top_thick", CUT,
                        top_c.bRepBodies.item(0), "DogHole", flip=True)

    dog_count = int(ev("dog_count"))
    if dog_count > 1:
        sp.feat_pattern(top_c, dog_ext, top_c.xConstructionAxis,
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
    sp.combine(top_proxy, leg_proxies, CUT, True, "LegMortise_Cut")

    # CUT legs with long stretcher proxies (through-mortises)
    ls_proxies = get_proxies(ls_occ)
    for i in range(leg_c.bRepBodies.count):
        lp = leg_c.bRepBodies.item(i).createForAssemblyContext(leg_occ)
        sp.combine(lp, ls_proxies, CUT, True, f"LSMort_Leg{i}")

    # Pin holes in legs — pins are in stretcher components, CUT via proxies
    for prefix, s_c, s_occ in [("LS", ls_c, ls_occ), ("SS", ss_c, ss_occ)]:
        pin_proxies = [s_c.bRepBodies.item(i).createForAssemblyContext(s_occ)
                       for i in range(s_c.bRepBodies.count)
                       if "Pin" in s_c.bRepBodies.item(i).name]
        if pin_proxies:
            for i in range(leg_c.bRepBodies.count):
                lp = leg_c.bRepBodies.item(i).createForAssemblyContext(leg_occ)
                sp.combine(lp, pin_proxies, CUT, True,
                           f"{prefix}PinHole_Leg{i}")

    # CUT FL leg with vise screw bore and guide slot (not chop/handle)
    vise_screw_p = vise_c.bRepBodies.itemByName("Vise_Screw").createForAssemblyContext(vise_occ)
    vise_guide_p = vise_c.bRepBodies.itemByName("Vise_Guide").createForAssemblyContext(vise_occ)
    fl_proxy = leg_c.bRepBodies.item(0).createForAssemblyContext(leg_occ)
    sp.combine(fl_proxy, [vise_screw_p, vise_guide_p], CUT, True, "ViseMort_FL")

    # CUT chop with screw bore
    chop_proxy = vise_c.bRepBodies.itemByName("Vise_Chop").createForAssemblyContext(vise_occ)
    screw_proxy = vise_c.bRepBodies.itemByName("Vise_Screw").createForAssemblyContext(vise_occ)
    sp.combine(chop_proxy, [screw_proxy], CUT, True, "ViseScrew_ChopCut")

    # CUT legs with short stretcher proxies (SS passes through legs)
    ss_proxies = get_proxies(ss_occ)
    for i in range(leg_c.bRepBodies.count):
        lp = leg_c.bRepBodies.item(i).createForAssemblyContext(leg_occ)
        sp.combine(lp, ss_proxies, CUT, True, f"SSMort_Leg{i}")

    # Deadman tongue grooves — built in target components (local combine).
    # Groove depth into material = dm_tongue_h - dm_gap.

    # Bottom groove in front LS (top face, runs between inner leg faces)
    groove_ls_pl = sp.off_plane(ls_c, root.xZConstructionPlane,
        "(dm_thick - dm_tongue_t) / 2", "GrooveBot_Pl")
    _, pr = sp.sketch_rect_model(ls_c, groove_ls_pl,
        ("leg_setback + leg_w",
         "(dm_thick - dm_tongue_t) / 2",
         "ls_z + ls_w - (dm_tongue_h - dm_gap)"),
        {"x": "bench_l - 2 * leg_setback - 2 * leg_w",
         "z": "dm_tongue_h - dm_gap"},
        "GrooveBot_Sk", ev=ev)
    groove_bot_ext = sp.ext_op(ls_c, pr, "dm_tongue_t", CUT,
        ls_c.bRepBodies.itemByName("LS_Front"), "DMGroove_LS")

    # Top groove in bench top underside (runs between inner leg faces)
    groove_top_pl = sp.off_plane(top_c, root.xZConstructionPlane,
        "(dm_thick - dm_tongue_t) / 2", "GrooveTop_Pl")
    _, pr = sp.sketch_rect_model(top_c, groove_top_pl,
        ("leg_setback + leg_w",
         "(dm_thick - dm_tongue_t) / 2",
         "leg_h"),
        {"x": "bench_l - 2 * leg_setback - 2 * leg_w",
         "z": "dm_tongue_h - dm_gap"},
        "GrooveTop_Sk", ev=ev)
    groove_top_ext = sp.ext_op(top_c, pr, "dm_tongue_t", CUT,
        top_c.bRepBodies.item(0), "DMGroove_Top")

    # ==============================================================
    #  DETAILS — chamfers on exposed edges (not on joint mating lines)
    # ==============================================================

    def _chamfer_boundary_edges(comp, body, size_expr, name, z_filter=None):
        """Chamfer edges on the outer bounding box boundary of a body.

        Only selects edges where BOTH vertices sit on the body's bounding
        box faces.  Joint/mortise edges are interior — they don't touch
        the bounding box — so they're automatically excluded.
        Optional z_filter: 'top', 'bottom', or None (all boundary edges).
        """
        bb = body.boundingBox
        mn, mx = bb.minPoint, bb.maxPoint
        tol = 0.05  # cm

        def on_bb(pt):
            return (abs(pt.x - mn.x) < tol or abs(pt.x - mx.x) < tol
                    or abs(pt.y - mn.y) < tol or abs(pt.y - mx.y) < tol
                    or abs(pt.z - mn.z) < tol or abs(pt.z - mx.z) < tol)

        edges = adsk.core.ObjectCollection.create()
        for j in range(body.edges.count):
            e = body.edges.item(j)
            sv, ev2 = e.startVertex.geometry, e.endVertex.geometry
            if not (on_bb(sv) and on_bb(ev2)):
                continue
            if z_filter == 'bottom' and not (abs(sv.z - mn.z) < tol
                                              and abs(ev2.z - mn.z) < tol):
                continue
            if z_filter == 'top' and not (abs(sv.z - mx.z) < tol
                                           and abs(ev2.z - mx.z) < tol):
                continue
            edges.add(e)
        if edges.count > 0:
            ch_inp = comp.features.chamferFeatures.createInput2()
            ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                edges, VI(size_expr), True)
            ch = comp.features.chamferFeatures.add(ch_inp)
            ch.name = name

    # Top slab — chamfer outer perimeter (skipping tenon mortise slot edges),
    # dog hole circles, and end edges.  Tenon slot edges are joint mating
    # lines and must not be chamfered.
    _top_body = top_c.bRepBodies.item(0)
    _top_bb = _top_body.boundingBox
    _top_edges = adsk.core.ObjectCollection.create()
    tol = 0.05
    for j in range(_top_body.edges.count):
        e = _top_body.edges.item(j)
        sv, ev2 = e.startVertex.geometry, e.endVertex.geometry

        # End edges: both vertices at X=min or X=max (always safe)
        at_left_end = (abs(sv.x - _top_bb.minPoint.x) < tol
                       and abs(ev2.x - _top_bb.minPoint.x) < tol)
        at_right_end = (abs(sv.x - _top_bb.maxPoint.x) < tol
                        and abs(ev2.x - _top_bb.maxPoint.x) < tol)
        if at_left_end or at_right_end:
            _top_edges.add(e)
            continue

        # Top face (Z=max): perimeter segments + dog hole circles
        at_top = (abs(sv.z - _top_bb.maxPoint.z) < tol
                  and abs(ev2.z - _top_bb.maxPoint.z) < tol)
        if not at_top:
            continue

        # Dog holes: circular edges (start == end position)
        is_circle = (abs(sv.x - ev2.x) < tol and abs(sv.y - ev2.y) < tol)
        if is_circle:
            _top_edges.add(e)
            continue

        # Perimeter segments: both vertices on outer Y boundary (front/back)
        on_front = (abs(sv.y - _top_bb.minPoint.y) < tol
                    and abs(ev2.y - _top_bb.minPoint.y) < tol)
        on_back = (abs(sv.y - _top_bb.maxPoint.y) < tol
                   and abs(ev2.y - _top_bb.maxPoint.y) < tol)
        if on_front or on_back:
            _top_edges.add(e)
            continue

        # Left/right end edges on top face
        on_left = (abs(sv.x - _top_bb.minPoint.x) < tol
                   and abs(ev2.x - _top_bb.minPoint.x) < tol)
        on_right = (abs(sv.x - _top_bb.maxPoint.x) < tol
                    and abs(ev2.x - _top_bb.maxPoint.x) < tol)
        if on_left or on_right:
            _top_edges.add(e)

    if _top_edges.count > 0:
        ch_inp = top_c.features.chamferFeatures.createInput2()
        ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
            _top_edges, VI("ch_top"), True)
        ch = top_c.features.chamferFeatures.add(ch_inp)
        ch.name = "TopFace_Ch"

    # Legs — chamfer bottom edges only (top meets the slab joint)
    for i in range(leg_c.bRepBodies.count):
        _chamfer_boundary_edges(leg_c, leg_c.bRepBodies.item(i),
                                "ch_leg", f"LegBot_Ch{i}", z_filter='bottom')

    # LS through-tenon proud faces — chamfer exposed end grain
    for body_name in ["LS_Front", "LS_Back"]:
        ls_body = ls_c.bRepBodies.itemByName(body_name)
        if not ls_body:
            continue
        proud_edges = adsk.core.ObjectCollection.create()
        bb = ls_body.boundingBox
        for j in range(ls_body.faces.count):
            f = ls_body.faces.item(j)
            # Proud faces are at X extremes (outside the legs)
            pt = f.pointOnFace
            at_left = abs(pt.x - bb.minPoint.x) < 0.5
            at_right = abs(pt.x - bb.maxPoint.x) < 0.5
            if (at_left or at_right) and f.area < 50:  # small face = tenon end
                for k in range(f.edges.count):
                    proud_edges.add(f.edges.item(k))
        if proud_edges.count > 0:
            ch_inp = ls_c.features.chamferFeatures.createInput2()
            ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                proud_edges, VI("ch_top"), True)
            ch = ls_c.features.chamferFeatures.add(ch_inp)
            ch.name = f"{body_name}_ProudCh"

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

    # Apply white oak appearance
    sp.apply_appearance("white oak")

    # Show edge lines
    app.activeViewport.visualStyle = \
        adsk.core.VisualStyles.ShadedWithVisibleEdgesOnlyVisualStyle

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
