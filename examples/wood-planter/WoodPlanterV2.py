"""
Wood Planter V2 — Parametric with Combine-Based M&T Joinery
=============================================================
60"L x 20"W body, 30" tall, on 10" legs (40" total).
Frame construction with vertical tongue-and-groove slat infill.

Build approach:
  - Features live inside their respective components (Legs, LongRails, ShortRails, Slats, BottomSlats)
  - Rail tenons built as NewBody, JOINed into rail, then CUT into legs via assembly proxies
  - Mirrors replicate legs, rails, and slat templates
  - Independent body patterns replicate slats per side

Coordinate system:
  X = length (60")   Y = width (20")   Z = height (40")
"""
import adsk.core, adsk.fusion, adsk.cam, math
from helpers import sp


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters

    # ==============================================================
    #  PARAMETERS
    # ==============================================================
    for pname, expr, unit, desc in [
        ("planter_length",    "50 in",    "in", "Overall length (X direction)"),
        ("planter_width",     "20 in",    "in", "Overall width (Y direction)"),
        ("total_height",      "35 in",    "in", "Top of leg posts to ground"),
        ("leg_below_body",    "10 in",    "in", "Leg height below the planter body"),
        ("leg_size",          "3.5 in",   "in", "Leg post cross-section (square)"),
        ("post_reveal",       "0.5 in",   "in", "How far posts stick above the upper rail"),
        ("post_chamfer",      "0.25 in",  "in", "Chamfer on top of each leg post"),
        ("rail_thickness",    "1.8 in",   "in", "Rail depth front-to-back"),
        ("rail_recess",       "0.125 in", "in", "How far rails/slats are recessed from leg face"),
        ("rail_height_lo",    "3.5 in",   "in", "Lower rail height"),
        ("rail_height_hi",    "2.5 in",   "in", "Upper rail height"),
        ("tenon_clearance",   "0.3 in",   "in", "Wood left at far side of tenon in leg"),
        ("tenon_width_lr",    "1.4 in",   "in", "Long rail tenon width (wider for interlock prongs)"),
        ("tenon_width_sr",    "0.6 in",   "in", "Short rail tenon width (passes through long rail)"),
        ("tenon_shoulder",    "0.25 in",  "in", "Vertical shoulder above/below tenon"),
        ("groove_width",      "0.375 in", "in", "Groove width for slat frame tongues"),
        ("groove_depth",      "0.375 in", "in", "Groove depth into rail/leg face"),
        ("frame_tongue_thick","0.34 in",  "in", "Slat frame tongue thickness (fits in groove)"),
        ("floor_board_w",  "4 in",     "in", "Floor board width"),
        ("floor_thickness",   "1 in",     "in", "Floor board thickness"),
        ("slat_width",        "4 in",     "in", "Side slat width"),
        ("slat_thickness",    "0.5 in",   "in", "Side slat panel thickness"),
        ("slat_tg_width",     "0.25 in",  "in", "Tongue-and-groove width between slats"),
        ("slat_tg_depth",     "0.25 in",  "in", "Tongue-and-groove depth between slats"),
        ("drainage_gap",      "0.25 in",  "in", "Gap between floor boards for drainage"),
        ("dm_bt_w",           "0.25 in",  "in", "Bottom domino width"),
        ("dm_bt_h",           "0.5 in",   "in", "Bottom domino height"),
        ("dm_bt_d",           "0.75 in",  "in", "Bottom domino depth"),
    ]:
        params.add(pname, adsk.core.ValueInput.createByString(expr), unit, desc)

    for pname, expr, unit, desc in [
        ("long_shoulder",  "planter_length - 2 * leg_size",                            "in", "Rail span between legs (length direction)"),
        ("short_shoulder", "planter_width - 2 * leg_size",                             "in", "Rail span between legs (width direction)"),
        ("lo_z",           "leg_below_body",                                           "in", "Z of lower rail bottom"),
        ("hi_z",           "total_height - post_reveal - rail_height_hi",               "in", "Z of upper rail bottom"),
        ("groove_offset",  "rail_recess + (rail_thickness - groove_width) / 2",         "in", "Groove center offset from outer face"),
        ("tenon_depth",    "leg_size - tenon_clearance",                              "in", "How deep tenon penetrates into leg"),
        ("tenon_height_lo","rail_height_lo - 2 * tenon_shoulder",                    "in", "Lower rail tenon height"),
        ("tenon_height_hi","rail_height_hi - 2 * tenon_shoulder",                    "in", "Upper rail tenon height"),
        ("body_z",         "leg_below_body + rail_height_lo",                          "in", "Z of slat body bottom"),
        ("body_h",         "total_height - post_reveal - rail_height_lo - rail_height_hi - leg_below_body", "in", "Slat body height"),
        ("full_slat_h",    "total_height - post_reveal - rail_height_lo - rail_height_hi + 2 * groove_depth - leg_below_body", "in", "Full slat height including tongues"),
        ("groove_span",    "total_height - post_reveal - rail_height_hi + groove_depth - leg_below_body", "in", "Leg groove height for slat edge tongues"),
        ("mid_x",          "planter_length / 2",                                       "in", "X midplane for mirrors"),
        ("mid_y",          "planter_width / 2",                                        "in", "Y midplane for mirrors"),
        ("bottom_slat_spacing", "floor_board_w + drainage_gap",                     "in", "Floor board pattern spacing"),
        ("floor_inset",     "groove_offset + (groove_width + slat_thickness) / 2",      "in", "Floor board edge offset (contacts slat inner face)"),
        ("floor_span_x",    "planter_length - 2 * floor_inset",                        "in", "Floor board span in X (left slat to right slat)"),
        ("floor_span_y",    "planter_width - 2 * floor_inset",                         "in", "Floor board span in Y (front slat to back slat)"),
    ]:
        params.add(pname, adsk.core.ValueInput.createByString(expr), unit, desc)

    for pname, expr, desc in [
        ("n_long_slats",    "floor(long_shoulder / slat_width)",                        "Number of full-width slats per long side"),
        ("n_short_slats",   "floor(short_shoulder / slat_width)",                       "Number of full-width slats per short side"),
        ("n_floor_slats",   "floor(floor_span_x / (floor_board_w + drainage_gap)) + 1", "Number of floor boards (fills span exactly)"),
    ]:
        params.add(pname, adsk.core.ValueInput.createByString(expr), "", desc)

    for pname, expr, unit, desc in [
        ("floor_board_w_fit", "(floor_span_x - (n_floor_slats - 1) * drainage_gap) / n_floor_slats", "in",
         "Actual floor board width (adjusted to fill span exactly)"),
    ]:
        params.add(pname, adsk.core.ValueInput.createByString(expr), unit, desc)

    # ==============================================================
    #  HELPERS
    # ==============================================================
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

    def ev(e):
        p = params.itemByName(e)
        return p.value if p else design.unitsManager.evaluateExpression(e, "cm")

    def sketch_rect(comp, plane, x0e, y0e, we, he, name="Sk"):
        sk = comp.sketches.add(plane)
        sk.name = name
        x0, y0, w, h = ev(x0e), ev(y0e), ev(we), ev(he)
        P = adsk.core.Point3D.create
        lines = sk.sketchCurves.sketchLines
        gc = sk.geometricConstraints
        H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
        V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
        l_bot = lines.addByTwoPoints(P(x0, y0, 0), P(x0 + w, y0, 0))
        l_right = lines.addByTwoPoints(l_bot.endSketchPoint, P(x0 + w, y0 + h, 0))
        l_top = lines.addByTwoPoints(l_right.endSketchPoint, P(x0, y0 + h, 0))
        l_left = lines.addByTwoPoints(l_top.endSketchPoint, l_bot.startSketchPoint)
        gc.addHorizontal(l_bot)
        gc.addHorizontal(l_top)
        gc.addVertical(l_right)
        gc.addVertical(l_left)
        d = sk.sketchDimensions
        d.addDistanceDimension(l_bot.startSketchPoint, l_bot.endSketchPoint,
            H, P(x0 + w/2, y0 - 1, 0)).parameter.expression = we
        d.addDistanceDimension(l_right.startSketchPoint, l_right.endSketchPoint,
            V, P(x0 + w + 1, y0 + h/2, 0)).parameter.expression = he
        d.addDistanceDimension(sk.originPoint, l_bot.startSketchPoint,
            H, P(x0/2, y0 - 2, 0)).parameter.expression = x0e
        d.addDistanceDimension(sk.originPoint, l_bot.startSketchPoint,
            V, P(x0 - 1, y0/2, 0)).parameter.expression = y0e
        return sk, sk.profiles.item(0)

    def sketch_slot(comp, plane, cxe, cye, long_e, short_e, vertical=True, name="Sk"):
        """Stadium profile: 2 semicircles + 2 lines, fully constrained.
        Center at (cxe, cye), overall long_e × short_e.
        vertical=True → long axis along sketch Y.
        Returns (sketch, inner_profile)."""
        sk = comp.sketches.add(plane)
        sk.name = name
        cx, cy = ev(cxe), ev(cye)
        lv, sv = ev(long_e), ev(short_e)
        r, s = sv / 2, (lv - sv) / 2
        P = adsk.core.Point3D.create
        arcs = sk.sketchCurves.sketchArcs
        lns = sk.sketchCurves.sketchLines
        if vertical:
            a1 = arcs.addByCenterStartSweep(P(cx, cy+s, 0), P(cx+r, cy+s, 0), math.pi)
            a2 = arcs.addByCenterStartSweep(P(cx, cy-s, 0), P(cx-r, cy-s, 0), math.pi)
            lns.addByTwoPoints(P(cx-r, cy+s, 0), P(cx-r, cy-s, 0))
            lns.addByTwoPoints(P(cx+r, cy-s, 0), P(cx+r, cy+s, 0))
        else:
            a1 = arcs.addByCenterStartSweep(P(cx+s, cy, 0), P(cx+s, cy+r, 0), math.pi)
            a2 = arcs.addByCenterStartSweep(P(cx-s, cy, 0), P(cx-s, cy-r, 0), math.pi)
            lns.addByTwoPoints(P(cx-s, cy+r, 0), P(cx+s, cy+r, 0))
            lns.addByTwoPoints(P(cx+s, cy-r, 0), P(cx-s, cy-r, 0))
        sk.geometricConstraints.addEqual(a1, a2)
        d = sk.sketchDimensions
        H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
        V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
        d.addRadialDimension(a1,
            P(cx + r*0.7, cy + s + r*0.3, 0) if vertical
            else P(cx + s + r*0.3, cy + r*0.7, 0)
        ).parameter.expression = f"{short_e} / 2"
        d.addDistanceDimension(a1.centerSketchPoint, a2.centerSketchPoint,
            V if vertical else H, P(cx + r + 1, cy, 0)
        ).parameter.expression = f"{long_e} - {short_e}"
        d.addDistanceDimension(sk.originPoint, a1.centerSketchPoint,
            H, P(cx/2, cy + s - 1, 0)).parameter.expression = cxe
        d.addDistanceDimension(sk.originPoint, a1.centerSketchPoint,
            V, P(cx - 1, (cy + s)/2, 0)
        ).parameter.expression = (f"{cye} + ({long_e} - {short_e}) / 2"
                                  if vertical else cye)
        # Select inner profile (the slot, not the surrounding face region)
        prof = sk.profiles.item(0)
        if sk.profiles.count > 1:
            for i in range(sk.profiles.count):
                p = sk.profiles.item(i)
                if p.profileLoops.count == 1:
                    prof = p
                    break
        return sk, prof

    def ext_new(comp, prof, dist, name="Ext"):
        inp = comp.features.extrudeFeatures.createInput(
            prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        inp.setDistanceExtent(False, adsk.core.ValueInput.createByString(dist))
        f = comp.features.extrudeFeatures.add(inp)
        f.name = name
        return f

    def ext_cut(comp, prof, dist, body, name="Cut"):
        inp = comp.features.extrudeFeatures.createInput(
            prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
        inp.setDistanceExtent(False, adsk.core.ValueInput.createByString(dist))
        inp.participantBodies = [body]
        f = comp.features.extrudeFeatures.add(inp)
        f.name = name
        return f

    def ext_join(comp, prof, dist, body, name="Join"):
        inp = comp.features.extrudeFeatures.createInput(
            prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
        inp.setDistanceExtent(False, adsk.core.ValueInput.createByString(dist))
        inp.participantBodies = [body]
        f = comp.features.extrudeFeatures.add(inp)
        f.name = name
        return f

    def ext_new_sym(comp, prof, dist, name="Ext"):
        inp = comp.features.extrudeFeatures.createInput(
            prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        inp.setSymmetricExtent(adsk.core.ValueInput.createByString(dist), True)
        f = comp.features.extrudeFeatures.add(inp)
        f.name = name
        return f

    def off_plane(comp, base, expr, name="Pl"):
        inp = comp.constructionPlanes.createInput()
        inp.setByOffset(base, adsk.core.ValueInput.createByString(expr))
        p = comp.constructionPlanes.add(inp)
        p.name = name
        return p

    def combine(comp, target, tool_bodies, op, keep_tool, name="Comb"):
        coll = adsk.core.ObjectCollection.create()
        if isinstance(tool_bodies, list):
            for b in tool_bodies:
                coll.add(b)
        else:
            coll.add(tool_bodies)
        inp = comp.features.combineFeatures.createInput(target, coll)
        inp.operation = op
        inp.isKeepToolBodies = keep_tool
        f = comp.features.combineFeatures.add(inp)
        f.name = name
        return f

    def mirror_feat(comp, features, plane, name="Mir"):
        coll = adsk.core.ObjectCollection.create()
        for f in features:
            coll.add(f)
        inp = comp.features.mirrorFeatures.createInput(coll, plane)
        m = comp.features.mirrorFeatures.add(inp)
        m.name = name
        return m

    def mirror_bodies(comp, bodies, plane, name="Mir"):
        coll = adsk.core.ObjectCollection.create()
        for b in bodies:
            coll.add(b)
        inp = comp.features.mirrorFeatures.createInput(coll, plane)
        m = comp.features.mirrorFeatures.add(inp)
        m.name = name
        return m

    def body_pattern(comp, body, axis, count_expr, spacing_expr, name="Pat"):
        coll = adsk.core.ObjectCollection.create()
        coll.add(body)
        inp = comp.features.rectangularPatternFeatures.createInput(
            coll, axis,
            adsk.core.ValueInput.createByString(count_expr),
            adsk.core.ValueInput.createByString(spacing_expr),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        inp.quantityTwo = adsk.core.ValueInput.createByString("1")
        pat = comp.features.rectangularPatternFeatures.add(inp)
        pat.name = name
        return pat

    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
    CUT  = adsk.fusion.FeatureOperations.CutFeatureOperation

    # ==============================================================
    #  COMPONENTS
    # ==============================================================
    def make_comp(name):
        occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        occ.component.name = name
        return occ

    leg_occ = make_comp("Legs")
    lr_occ  = make_comp("LongRails")
    sr_occ  = make_comp("ShortRails")
    sl_occ  = make_comp("Slats")
    bt_occ  = make_comp("Bottom")

    leg_c = leg_occ.component
    lr_c  = lr_occ.component
    sr_c  = sr_occ.component
    sl_c  = sl_occ.component
    bt_c  = bt_occ.component

    # ==============================================================
    #  1. LEGS  (Legs component)
    #
    #  Plain posts with grooves for slat edge tongues.
    #  Mortises are created later via assembly proxy CUT.
    # ==============================================================
    _, pr = sketch_rect(leg_c, leg_c.xYConstructionPlane,
        "0 in", "0 in", "leg_size", "leg_size", "FL_Leg_Sk")
    ext_fl = ext_new(leg_c, pr, "total_height", "FL_Leg")
    fl_leg = ext_fl.bodies.item(0)
    fl_leg.name = "Leg_FL"

    # X-face groove (for front slat edge tongues)
    grv_pl = off_plane(leg_c, leg_c.xYConstructionPlane, "lo_z", "Groove_Pl")
    _, pr = sketch_rect(leg_c, grv_pl,
        "leg_size - groove_depth", "groove_offset",
        "groove_depth", "groove_width", "FL_Groove_X_Sk")
    ext_cut(leg_c, pr, "groove_span", fl_leg, "Cut_Groove_X")

    # Y-face groove (for left slat edge tongues)
    _, pr = sketch_rect(leg_c, grv_pl,
        "groove_offset", "leg_size - groove_depth",
        "groove_width", "groove_depth", "FL_Groove_Y_Sk")
    ext_cut(leg_c, pr, "groove_span", fl_leg, "Cut_Groove_Y")

    # Chamfer top edges of FL leg (find highest +Z face)
    top_face = None
    max_z = -float('inf')
    for i in range(fl_leg.faces.count):
        f = fl_leg.faces.item(i)
        if hasattr(f.geometry, 'normal') and abs(f.geometry.normal.z - 1.0) < 0.01:
            if f.centroid.z > max_z:
                max_z = f.centroid.z
                top_face = f
    if top_face:
        ch_edges = adsk.core.ObjectCollection.create()
        for i in range(top_face.edges.count):
            ch_edges.add(top_face.edges.item(i))
        ch_inp = leg_c.features.chamferFeatures.createInput(ch_edges, False)
        ch_inp.setToEqualDistance(adsk.core.ValueInput.createByString("post_chamfer"))
        leg_c.features.chamferFeatures.add(ch_inp).name = "FL_TopChamfer"

    # Midplanes + mirror: FL→FR, [FL,FR]→BL,BR
    mid_yz = off_plane(leg_c, leg_c.yZConstructionPlane, "mid_x", "MidYZ")
    mid_xz = off_plane(leg_c, leg_c.xZConstructionPlane, "mid_y", "MidXZ")

    mir_x = mirror_bodies(leg_c, [fl_leg], mid_yz, "Mir_FL_FR")
    fr_leg = mir_x.bodies.item(0)
    fr_leg.name = "Leg_FR"

    mir_y = mirror_bodies(leg_c, [fl_leg, fr_leg], mid_xz, "Mir_Front_Back")
    bl_leg = mir_y.bodies.item(0)
    bl_leg.name = "Leg_BL"
    br_leg = mir_y.bodies.item(1)
    br_leg.name = "Leg_BR"

    # ==============================================================
    #  2. LONG RAILS  (LongRails component)
    #
    #  Front lower + upper rails with tenons and grooves.
    #  Tenons built as NewBody, mirrored, JOINed into rail.
    # ==============================================================

    # Body-relative references for rail positioning
    ref_leg_fl = find_body("Leg_FL")
    ref_leg_fl_bb = ref_leg_fl.boundingBox

    # --- Front lower rail ---
    flo_pl = off_plane(lr_c, lr_c.xYConstructionPlane, "lo_z", "FLo_Pl")
    _, pr = sketch_rect(lr_c, flo_pl,
        "leg_size", "rail_recess", "long_shoulder", "rail_thickness", "FLo_Rail_Sk")
    ext_flo = ext_new(lr_c, pr, "rail_height_lo", "FLo_Rail")
    flo_body = ext_flo.bodies.item(0)
    flo_body.name = "LR_Front_Lower"

    # Left tenon (NewBody) — tall, with half-lap interlock
    flo_t_pl = off_plane(lr_c, lr_c.xYConstructionPlane,
        "lo_z + tenon_shoulder", "FLo_Tenon_Pl")
    _, pr = sketch_rect(lr_c, flo_t_pl,
        "leg_size - tenon_depth", "rail_recess + (rail_thickness - tenon_width_lr) / 2",
        "tenon_depth", "tenon_width_lr", "FLo_Tenon_L_Sk")
    ext_flo_t = ext_new(lr_c, pr, "tenon_height_lo", "FLo_Tenon_L")
    flo_tenon_l = ext_flo_t.bodies.item(0)
    flo_tenon_l.name = "FLo_Tenon_L"

    # Mirror left tenon → right tenon
    flo_xmid = off_plane(lr_c, lr_c.yZConstructionPlane,
        "leg_size + long_shoulder / 2", "FLo_XMid")
    mir_flo_t = mirror_feat(lr_c, [ext_flo_t], flo_xmid, "FLo_MirTenon")
    flo_tenon_r = mir_flo_t.bodies.item(0)
    flo_tenon_r.name = "FLo_Tenon_R"

    # JOIN both tenons into rail
    combine(lr_c, flo_body, [flo_tenon_l, flo_tenon_r], JOIN, False, "FLo_JoinTenons")

    # Groove on top of front lower rail (for slat frame tongues)
    flo_grv_pl = off_plane(lr_c, lr_c.xYConstructionPlane,
        "lo_z + rail_height_lo - groove_depth", "FLo_Groove_Pl")
    _, pr = sketch_rect(lr_c, flo_grv_pl,
        "leg_size", "groove_offset",
        "long_shoulder", "groove_width", "FLo_Groove_Sk")
    ext_cut(lr_c, pr, "groove_depth", flo_body, "FLo_Groove")

    # Body-relative reference for upper rail positioning
    ref_flo = find_body("LR_Front_Lower")
    ref_flo_bb = ref_flo.boundingBox

    # --- Front upper rail ---
    fhi_pl = off_plane(lr_c, lr_c.xYConstructionPlane, "hi_z", "FHi_Pl")
    _, pr = sketch_rect(lr_c, fhi_pl,
        "leg_size", "rail_recess", "long_shoulder", "rail_thickness", "FHi_Rail_Sk")
    ext_fhi = ext_new(lr_c, pr, "rail_height_hi", "FHi_Rail")
    fhi_body = ext_fhi.bodies.item(0)
    fhi_body.name = "LR_Front_Upper"

    # Left tenon — tall, with half-lap interlock
    fhi_t_pl = off_plane(lr_c, lr_c.xYConstructionPlane,
        "hi_z + tenon_shoulder", "FHi_Tenon_Pl")
    _, pr = sketch_rect(lr_c, fhi_t_pl,
        "leg_size - tenon_depth", "rail_recess + (rail_thickness - tenon_width_lr) / 2",
        "tenon_depth", "tenon_width_lr", "FHi_Tenon_L_Sk")
    ext_fhi_t = ext_new(lr_c, pr, "tenon_height_hi", "FHi_Tenon_L")
    fhi_tenon_l = ext_fhi_t.bodies.item(0)
    fhi_tenon_l.name = "FHi_Tenon_L"

    # Mirror left tenon → right tenon
    mir_fhi_t = mirror_feat(lr_c, [ext_fhi_t], flo_xmid, "FHi_MirTenon")
    fhi_tenon_r = mir_fhi_t.bodies.item(0)
    fhi_tenon_r.name = "FHi_Tenon_R"

    # JOIN both tenons into rail
    combine(lr_c, fhi_body, [fhi_tenon_l, fhi_tenon_r], JOIN, False, "FHi_JoinTenons")

    # Groove on bottom of front upper rail
    _, pr = sketch_rect(lr_c, fhi_pl,
        "leg_size", "groove_offset",
        "long_shoulder", "groove_width", "FHi_Groove_Sk")
    ext_cut(lr_c, pr, "groove_depth", fhi_body, "FHi_Groove")

    # Body-relative reference for back rails
    ref_leg_bl = find_body("Leg_BL")
    ref_leg_bl_bb = ref_leg_bl.boundingBox

    # Mirror front pair → back pair
    lr_mid_xz = off_plane(lr_c, lr_c.xZConstructionPlane, "mid_y", "LR_MidXZ")
    mir_lr = mirror_bodies(lr_c, [flo_body, fhi_body], lr_mid_xz, "Mir_LR_Back")
    blo_body = mir_lr.bodies.item(0)
    blo_body.name = "LR_Back_Lower"
    bhi_body = mir_lr.bodies.item(1)
    bhi_body.name = "LR_Back_Upper"

    # Body-relative reference for back upper rail
    ref_blo = find_body("LR_Back_Lower")
    ref_blo_bb = ref_blo.boundingBox

    # ==============================================================
    #  3. SHORT RAILS  (ShortRails component)
    #
    #  Same pattern as long rails but rotated, staggered tenon Z.
    # ==============================================================

    # --- Left lower rail (projected leg face reference) ---
    llo_pl = off_plane(sr_c, sr_c.xYConstructionPlane, "lo_z", "LLo_Pl")

    def sr_sketch_from_leg(comp, plane, leg_body, leg_occ_ref, we, he, name):
        """Short rail sketch anchored to projected leg inner face, offset by rail_recess."""
        sk = comp.sketches.add(plane)
        sk.name = name
        P = adsk.core.Point3D.create
        H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
        V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation

        leg_proxy = leg_body.createForAssemblyContext(leg_occ_ref)
        proj = sk.project(leg_proxy)
        for i in range(proj.count):
            e = proj.item(i)
            if hasattr(e, 'isConstruction'):
                e.isConstruction = True

        leg_y = ev("leg_size")
        recess = ev("rail_recess")
        ref_pt = None
        for i in range(sk.sketchPoints.count):
            pt = sk.sketchPoints.item(i)
            if pt == sk.originPoint:
                continue
            if abs(pt.geometry.x) < 0.01 and abs(pt.geometry.y - leg_y) < 0.01:
                ref_pt = pt
                break

        w, h = ev(we), ev(he)
        lines = sk.sketchCurves.sketchLines
        gc = sk.geometricConstraints
        y0 = leg_y
        x0 = recess
        l_bot = lines.addByTwoPoints(P(x0, y0, 0), P(x0 + w, y0, 0))
        l_right = lines.addByTwoPoints(l_bot.endSketchPoint, P(x0 + w, y0 + h, 0))
        l_top = lines.addByTwoPoints(l_right.endSketchPoint, P(x0, y0 + h, 0))
        l_left = lines.addByTwoPoints(l_top.endSketchPoint, l_bot.startSketchPoint)
        gc.addHorizontal(l_bot)
        gc.addHorizontal(l_top)
        gc.addVertical(l_right)
        gc.addVertical(l_left)

        d = sk.sketchDimensions
        if ref_pt:
            d.addDistanceDimension(ref_pt, l_bot.startSketchPoint,
                V, P(x0 - 1, y0 / 2, 0)).parameter.expression = "0 in"
            d.addDistanceDimension(ref_pt, l_bot.startSketchPoint,
                H, P(x0 / 2, y0 - 2, 0)).parameter.expression = "rail_recess"

        d.addDistanceDimension(l_bot.startSketchPoint, l_bot.endSketchPoint,
            H, P(x0 + w / 2, y0 - 1, 0)).parameter.expression = we
        d.addDistanceDimension(l_right.startSketchPoint, l_right.endSketchPoint,
            V, P(x0 + w + 1, y0 + h / 2, 0)).parameter.expression = he
        return sk, sk.profiles.item(0)

    _, pr = sr_sketch_from_leg(sr_c, llo_pl, fl_leg, leg_occ,
        "rail_thickness", "short_shoulder", "LLo_Rail_Sk")
    ext_llo = ext_new(sr_c, pr, "rail_height_lo", "LLo_Rail")
    llo_body = ext_llo.bodies.item(0)
    llo_body.name = "SR_Left_Lower"

    # Front tenon (NewBody) — tall, with half-lap interlock
    llo_t_pl = off_plane(sr_c, sr_c.xYConstructionPlane,
        "lo_z + tenon_shoulder", "LLo_Tenon_Pl")
    _, pr = sketch_rect(sr_c, llo_t_pl,
        "rail_recess + (rail_thickness - tenon_width_sr) / 2", "leg_size - tenon_depth",
        "tenon_width_sr", "tenon_depth", "LLo_Tenon_F_Sk")
    ext_llo_t = ext_new(sr_c, pr, "tenon_height_lo", "LLo_Tenon_F")
    llo_tenon_f = ext_llo_t.bodies.item(0)
    llo_tenon_f.name = "LLo_Tenon_F"

    # Mirror front tenon → back tenon
    llo_ymid = off_plane(sr_c, sr_c.xZConstructionPlane,
        "leg_size + short_shoulder / 2", "LLo_YMid")
    mir_llo_t = mirror_feat(sr_c, [ext_llo_t], llo_ymid, "LLo_MirTenon")
    llo_tenon_b = mir_llo_t.bodies.item(0)
    llo_tenon_b.name = "LLo_Tenon_B"

    # JOIN both tenons into rail
    combine(sr_c, llo_body, [llo_tenon_f, llo_tenon_b], JOIN, False, "LLo_JoinTenons")

    # Groove on top of left lower rail
    llo_grv_pl = off_plane(sr_c, sr_c.xYConstructionPlane,
        "lo_z + rail_height_lo - groove_depth", "LLo_Groove_Pl")
    _, pr = sketch_rect(sr_c, llo_grv_pl,
        "groove_offset", "leg_size",
        "groove_width", "short_shoulder", "LLo_Groove_Sk")
    ext_cut(sr_c, pr, "groove_depth", llo_body, "LLo_Groove")

    # Body-relative reference for left upper short rail
    ref_sllo = find_body("SR_Left_Lower")
    ref_sllo_bb = ref_sllo.boundingBox

    # --- Left upper rail (projected leg face reference) ---
    lhi_pl = off_plane(sr_c, sr_c.xYConstructionPlane, "hi_z", "LHi_Pl")
    _, pr = sr_sketch_from_leg(sr_c, lhi_pl, fl_leg, leg_occ,
        "rail_thickness", "short_shoulder", "LHi_Rail_Sk")
    ext_lhi = ext_new(sr_c, pr, "rail_height_hi", "LHi_Rail")
    lhi_body = ext_lhi.bodies.item(0)
    lhi_body.name = "SR_Left_Upper"

    # Front tenon — tall, with half-lap interlock
    lhi_t_pl = off_plane(sr_c, sr_c.xYConstructionPlane,
        "hi_z + tenon_shoulder", "LHi_Tenon_Pl")
    _, pr = sketch_rect(sr_c, lhi_t_pl,
        "rail_recess + (rail_thickness - tenon_width_sr) / 2", "leg_size - tenon_depth",
        "tenon_width_sr", "tenon_depth", "LHi_Tenon_F_Sk")
    ext_lhi_t = ext_new(sr_c, pr, "tenon_height_hi", "LHi_Tenon_F")
    lhi_tenon_f = ext_lhi_t.bodies.item(0)
    lhi_tenon_f.name = "LHi_Tenon_F"

    # Mirror front tenon → back tenon
    mir_lhi_t = mirror_feat(sr_c, [ext_lhi_t], llo_ymid, "LHi_MirTenon")
    lhi_tenon_b = mir_lhi_t.bodies.item(0)
    lhi_tenon_b.name = "LHi_Tenon_B"

    # JOIN both tenons into rail
    combine(sr_c, lhi_body, [lhi_tenon_f, lhi_tenon_b], JOIN, False, "LHi_JoinTenons")

    # Groove on bottom of left upper rail
    _, pr = sketch_rect(sr_c, lhi_pl,
        "groove_offset", "leg_size",
        "groove_width", "short_shoulder", "LHi_Groove_Sk")
    ext_cut(sr_c, pr, "groove_depth", lhi_body, "LHi_Groove")

    # Body-relative reference for right short rails
    ref_leg_fr = find_body("Leg_FR")
    ref_leg_fr_bb = ref_leg_fr.boundingBox

    # Mirror left pair → right pair
    sr_mid_yz = off_plane(sr_c, sr_c.yZConstructionPlane, "mid_x", "SR_MidYZ")
    mir_sr = mirror_bodies(sr_c, [llo_body, lhi_body], sr_mid_yz, "Mir_SR_Right")
    rlo_body = mir_sr.bodies.item(0)
    rlo_body.name = "SR_Right_Lower"
    rhi_body = mir_sr.bodies.item(1)
    rhi_body.name = "SR_Right_Upper"

    # Body-relative reference for right upper short rail
    ref_srlo = find_body("SR_Right_Lower")
    ref_srlo_bb = ref_srlo.boundingBox

    # ==============================================================
    #  4. LEG MORTISES — bulk CUT  (root, assembly proxies)
    #
    #  Each rail (with tenons JOINed) is used as CUT tool against
    #  the leg. Only the tenon overlap creates mortise pockets.
    # ==============================================================
    # Create assembly proxies for all legs and rails
    fl_proxy = fl_leg.createForAssemblyContext(leg_occ)
    fr_proxy = fr_leg.createForAssemblyContext(leg_occ)
    bl_proxy = bl_leg.createForAssemblyContext(leg_occ)
    br_proxy = br_leg.createForAssemblyContext(leg_occ)

    flo_proxy = flo_body.createForAssemblyContext(lr_occ)
    fhi_proxy = fhi_body.createForAssemblyContext(lr_occ)
    blo_proxy = blo_body.createForAssemblyContext(lr_occ)
    bhi_proxy = bhi_body.createForAssemblyContext(lr_occ)

    llo_proxy = llo_body.createForAssemblyContext(sr_occ)
    lhi_proxy = lhi_body.createForAssemblyContext(sr_occ)
    rlo_proxy = rlo_body.createForAssemblyContext(sr_occ)
    rhi_proxy = rhi_body.createForAssemblyContext(sr_occ)

    # Tenon interlock: CUT long rail tenons with short rail bodies
    all_sr_proxies = [llo_proxy, lhi_proxy, rlo_proxy, rhi_proxy]
    combine(root, flo_proxy, all_sr_proxies, CUT, True, "Interlock_FLo")
    combine(root, fhi_proxy, all_sr_proxies, CUT, True, "Interlock_FHi")
    combine(root, blo_proxy, all_sr_proxies, CUT, True, "Interlock_BLo")
    combine(root, bhi_proxy, all_sr_proxies, CUT, True, "Interlock_BHi")

    # Re-collect ALL rail bodies (including interlock fragments) for mortise CUTs
    all_lr_proxies = [lr_c.bRepBodies.item(i).createForAssemblyContext(lr_occ)
                      for i in range(lr_c.bRepBodies.count)]
    all_sr_proxies_m = [sr_c.bRepBodies.item(i).createForAssemblyContext(sr_occ)
                        for i in range(sr_c.bRepBodies.count)]
    all_rail_proxies = all_lr_proxies + all_sr_proxies_m

    # CUT each leg with ALL rail bodies
    combine(root, fl_proxy, all_rail_proxies, CUT, True, "Mort_FL")
    combine(root, fr_proxy, all_rail_proxies, CUT, True, "Mort_FR")
    combine(root, bl_proxy, all_rail_proxies, CUT, True, "Mort_BL")
    combine(root, br_proxy, all_rail_proxies, CUT, True, "Mort_BR")

    # ==============================================================
    #  5. SLATS  (Slats component)
    #
    #  Mirror template + independent pattern approach.
    # ==============================================================
    sl_body_pl = off_plane(sl_c, sl_c.xYConstructionPlane, "body_z", "Slat_BodyZ")
    sl_top_pl  = off_plane(sl_c, sl_c.xYConstructionPlane, "hi_z", "Slat_TopZ")
    sl_bot_pl  = off_plane(sl_c, sl_c.xYConstructionPlane,
        "lo_z + rail_height_lo - groove_depth", "Slat_BotZ")
    sl_mid_xz = off_plane(sl_c, sl_c.xZConstructionPlane, "mid_y", "Slat_MidXZ")
    sl_mid_yz = off_plane(sl_c, sl_c.yZConstructionPlane, "mid_x", "Slat_MidYZ")

    # Y expressions for front slats (centered on front rail groove)
    fy_body = "groove_offset + groove_width / 2 - slat_thickness / 2"
    fy_tng  = "groove_offset + groove_width / 2 - frame_tongue_thick / 2"
    fy_tg   = "groove_offset + groove_width / 2 - slat_tg_width / 2"

    # ---- FRONT SLAT TEMPLATE ----
    front_feats = []

    _, pr = sketch_rect(sl_c, sl_body_pl,
        "leg_size", fy_body, "slat_width", "slat_thickness", "FSlat_Body_Sk")
    ext_fs = ext_new(sl_c, pr, "body_h", "FSlat_Body")
    front_feats.append(ext_fs)
    front_tmpl = ext_fs.bodies.item(0)
    front_tmpl.name = "Slat_Front_1"

    # Left-face T&G groove
    _, pr = sketch_rect(sl_c, sl_body_pl,
        "leg_size", fy_tg, "slat_tg_depth", "slat_tg_width", "FSlat_LGroove_Sk")
    front_feats.append(ext_cut(sl_c, pr, "body_h", front_tmpl, "FSlat_LGroove"))

    # Right-edge T&G tongue
    _, pr = sketch_rect(sl_c, sl_body_pl,
        "leg_size + slat_width", fy_tg, "slat_tg_depth", "slat_tg_width", "FSlat_RTongue_Sk")
    front_feats.append(ext_join(sl_c, pr, "body_h", front_tmpl, "FSlat_RTongue"))

    # Top frame tongue
    _, pr = sketch_rect(sl_c, sl_top_pl,
        "leg_size", fy_tng, "slat_width", "frame_tongue_thick", "FSlat_TopTng_Sk")
    front_feats.append(ext_join(sl_c, pr, "groove_depth", front_tmpl, "FSlat_TopTng"))

    # Bottom frame tongue
    _, pr = sketch_rect(sl_c, sl_bot_pl,
        "leg_size", fy_tng, "slat_width", "frame_tongue_thick", "FSlat_BotTng_Sk")
    front_feats.append(ext_join(sl_c, pr, "groove_depth", front_tmpl, "FSlat_BotTng"))

    # ---- MIRROR FRONT → BACK ----
    mir_back = mirror_feat(sl_c, front_feats, sl_mid_xz, "Mir_FSlat_Back")
    back_tmpl = mir_back.bodies.item(0)
    back_tmpl.name = "Slat_Back_1"

    # ---- PATTERN FRONT along X ----
    pat_front = body_pattern(sl_c, front_tmpl, sl_c.xConstructionAxis,
        "n_long_slats", "slat_width", "Pat_FrontSlats")
    for i in range(pat_front.bodies.count):
        pat_front.bodies.item(i).name = f"Slat_Front_{i + 2}"

    # ---- PATTERN BACK along X (independent) ----
    pat_back = body_pattern(sl_c, back_tmpl, sl_c.xConstructionAxis,
        "n_long_slats", "slat_width", "Pat_BackSlats")
    for i in range(pat_back.bodies.count):
        pat_back.bodies.item(i).name = f"Slat_Back_{i + 2}"

    # ---- FRONT LEFT-EDGE TONGUE ----
    _, pr = sketch_rect(sl_c, sl_bot_pl,
        "leg_size - groove_depth", fy_tng,
        "groove_depth", "frame_tongue_thick", "FSlat_LEdge_Sk")
    f_edge = ext_join(sl_c, pr, "full_slat_h", front_tmpl, "FSlat_LEdge")
    mirror_feat(sl_c, [f_edge], sl_mid_xz, "Mir_FEdge_Back")

    # ---- FRONT GAP SLAT (conditional) ----
    gap_long_cm = ev("long_shoulder") - ev("slat_width") * int(ev("n_long_slats"))
    if gap_long_cm > 0.01:
        n_lp = int(ev("n_long_slats"))
        fg_x = "leg_size + slat_width * n_long_slats"
        fg_w = "long_shoulder - slat_width * n_long_slats"
        fgap_feats = []

        _, pr = sketch_rect(sl_c, sl_body_pl,
            fg_x, fy_body, fg_w, "slat_thickness", "FGap_Body_Sk")
        ext_fg = ext_new(sl_c, pr, "body_h", "FGap_Body")
        fgap_feats.append(ext_fg)
        fg_body = ext_fg.bodies.item(0)
        fg_body.name = f"Slat_Front_{n_lp + 1}"

        _, pr = sketch_rect(sl_c, sl_body_pl,
            fg_x, fy_tg, "slat_tg_depth", "slat_tg_width", "FGap_LGroove_Sk")
        fgap_feats.append(ext_cut(sl_c, pr, "body_h", fg_body, "FGap_LGroove"))

        _, pr = sketch_rect(sl_c, sl_body_pl,
            "leg_size + long_shoulder", fy_tng,
            "groove_depth", "frame_tongue_thick", "FGap_REdge_Sk")
        fgap_feats.append(ext_join(sl_c, pr, "body_h", fg_body, "FGap_REdge"))

        _, pr = sketch_rect(sl_c, sl_top_pl,
            fg_x, fy_tng, fg_w, "frame_tongue_thick", "FGap_TopTng_Sk")
        fgap_feats.append(ext_join(sl_c, pr, "groove_depth", fg_body, "FGap_TopTng"))

        _, pr = sketch_rect(sl_c, sl_bot_pl,
            fg_x, fy_tng, fg_w, "frame_tongue_thick", "FGap_BotTng_Sk")
        fgap_feats.append(ext_join(sl_c, pr, "groove_depth", fg_body, "FGap_BotTng"))

        mir_bgap = mirror_feat(sl_c, fgap_feats, sl_mid_xz, "Mir_FGap_Back")
        for i in range(mir_bgap.bodies.count):
            mir_bgap.bodies.item(i).name = f"Slat_Back_{n_lp + 1}"

    # ---- LEFT SLAT TEMPLATE ----
    left_feats = []

    lx_body = "groove_offset + groove_width / 2 - slat_thickness / 2"
    lx_tng  = "groove_offset + groove_width / 2 - frame_tongue_thick / 2"
    lx_tg   = "groove_offset + groove_width / 2 - slat_tg_width / 2"

    _, pr = sketch_rect(sl_c, sl_body_pl,
        lx_body, "leg_size", "slat_thickness", "slat_width", "LSlat_Body_Sk")
    ext_ls = ext_new(sl_c, pr, "body_h", "LSlat_Body")
    left_feats.append(ext_ls)
    left_tmpl = ext_ls.bodies.item(0)
    left_tmpl.name = "Slat_Left_1"

    # Front-face T&G groove
    _, pr = sketch_rect(sl_c, sl_body_pl,
        lx_tg, "leg_size", "slat_tg_width", "slat_tg_depth", "LSlat_FGroove_Sk")
    left_feats.append(ext_cut(sl_c, pr, "body_h", left_tmpl, "LSlat_FGroove"))

    # Back-edge T&G tongue
    _, pr = sketch_rect(sl_c, sl_body_pl,
        lx_tg, "leg_size + slat_width", "slat_tg_width", "slat_tg_depth", "LSlat_BTongue_Sk")
    left_feats.append(ext_join(sl_c, pr, "body_h", left_tmpl, "LSlat_BTongue"))

    # Top frame tongue
    _, pr = sketch_rect(sl_c, sl_top_pl,
        lx_tng, "leg_size", "frame_tongue_thick", "slat_width", "LSlat_TopTng_Sk")
    left_feats.append(ext_join(sl_c, pr, "groove_depth", left_tmpl, "LSlat_TopTng"))

    # Bottom frame tongue
    _, pr = sketch_rect(sl_c, sl_bot_pl,
        lx_tng, "leg_size", "frame_tongue_thick", "slat_width", "LSlat_BotTng_Sk")
    left_feats.append(ext_join(sl_c, pr, "groove_depth", left_tmpl, "LSlat_BotTng"))

    # ---- MIRROR LEFT → RIGHT ----
    mir_right = mirror_feat(sl_c, left_feats, sl_mid_yz, "Mir_LSlat_Right")
    right_tmpl = mir_right.bodies.item(0)
    right_tmpl.name = "Slat_Right_1"

    # ---- PATTERN LEFT along Y ----
    pat_left = body_pattern(sl_c, left_tmpl, sl_c.yConstructionAxis,
        "n_short_slats", "slat_width", "Pat_LeftSlats")
    for i in range(pat_left.bodies.count):
        pat_left.bodies.item(i).name = f"Slat_Left_{i + 2}"

    # ---- PATTERN RIGHT along Y (independent) ----
    pat_right = body_pattern(sl_c, right_tmpl, sl_c.yConstructionAxis,
        "n_short_slats", "slat_width", "Pat_RightSlats")
    for i in range(pat_right.bodies.count):
        pat_right.bodies.item(i).name = f"Slat_Right_{i + 2}"

    # ---- LEFT FRONT-EDGE TONGUE ----
    _, pr = sketch_rect(sl_c, sl_bot_pl,
        lx_tng, "leg_size - groove_depth",
        "frame_tongue_thick", "groove_depth", "LSlat_FEdge_Sk")
    l_edge = ext_join(sl_c, pr, "full_slat_h", left_tmpl, "LSlat_FEdge")
    mirror_feat(sl_c, [l_edge], sl_mid_yz, "Mir_LEdge_Right")

    # ---- LEFT GAP SLAT (conditional) ----
    gap_short_cm = ev("short_shoulder") - ev("slat_width") * int(ev("n_short_slats"))
    if gap_short_cm > 0.01:
        n_sp = int(ev("n_short_slats"))
        lg_y = "leg_size + slat_width * n_short_slats"
        lg_h = "short_shoulder - slat_width * n_short_slats"
        lgap_feats = []

        _, pr = sketch_rect(sl_c, sl_body_pl,
            lx_body, lg_y, "slat_thickness", lg_h, "LGap_Body_Sk")
        ext_lg = ext_new(sl_c, pr, "body_h", "LGap_Body")
        lgap_feats.append(ext_lg)
        lg_body = ext_lg.bodies.item(0)
        lg_body.name = f"Slat_Left_{n_sp + 1}"

        _, pr = sketch_rect(sl_c, sl_body_pl,
            lx_tg, lg_y, "slat_tg_width", "slat_tg_depth", "LGap_FGroove_Sk")
        lgap_feats.append(ext_cut(sl_c, pr, "body_h", lg_body, "LGap_FGroove"))

        _, pr = sketch_rect(sl_c, sl_body_pl,
            lx_tng, "leg_size + short_shoulder",
            "frame_tongue_thick", "groove_depth", "LGap_BEdge_Sk")
        lgap_feats.append(ext_join(sl_c, pr, "body_h", lg_body, "LGap_BEdge"))

        _, pr = sketch_rect(sl_c, sl_top_pl,
            lx_tng, lg_y, "frame_tongue_thick", lg_h, "LGap_TopTng_Sk")
        lgap_feats.append(ext_join(sl_c, pr, "groove_depth", lg_body, "LGap_TopTng"))

        _, pr = sketch_rect(sl_c, sl_bot_pl,
            lx_tng, lg_y, "frame_tongue_thick", lg_h, "LGap_BotTng_Sk")
        lgap_feats.append(ext_join(sl_c, pr, "groove_depth", lg_body, "LGap_BotTng"))

        mir_rgap = mirror_feat(sl_c, lgap_feats, sl_mid_yz, "Mir_LGap_Right")
        for i in range(mir_rgap.bodies.count):
            mir_rgap.bodies.item(i).name = f"Slat_Right_{n_sp + 1}"

    # ==============================================================
    #  6. FLOOR BOARDS  (Bottom component)
    #
    #  1" thick boards on top of lower rails, spanning full interior.
    #  Patterned across X. Corner boards CUT by leg posts via proxies.
    # ==============================================================
    bt_pl = off_plane(bt_c, bt_c.xYConstructionPlane,
        "lo_z + rail_height_lo", "Floor_Pl")

    # Template board — width auto-adjusted to fill span exactly (no gap board needed)
    _, pr = sketch_rect(bt_c, bt_pl,
        "floor_inset", "floor_inset",
        "floor_board_w_fit", "floor_span_y", "FloorSlat_Sk")
    ext_bt = ext_new(bt_c, pr, "floor_thickness", "FloorSlat_Ext")
    bt_tmpl = ext_bt.bodies.item(0)
    bt_tmpl.name = "FloorSlat_1"

    # Pattern across full X span — spacing = board width + drainage gap
    n_floor = int(ev("n_floor_slats"))
    print(f"Floor: n={n_floor}, board_w_fit={ev('floor_board_w_fit')/2.54:.3f}in")
    pat_bt = body_pattern(bt_c, bt_tmpl, bt_c.xConstructionAxis,
        str(n_floor), "floor_board_w_fit + drainage_gap", "Pat_FloorSlats")
    for i in range(pat_bt.bodies.count):
        pat_bt.bodies.item(i).name = f"FloorSlat_{i + 2}"

    # CUT leg posts from ALL floor boards that overlap with legs
    leg_pairs = [(fl_leg, fl_proxy), (fr_leg, fr_proxy),
                 (bl_leg, bl_proxy), (br_leg, br_proxy)]
    for bi in range(bt_c.bRepBodies.count):
        board = bt_c.bRepBodies.item(bi)
        bb = board.boundingBox
        legs_to_cut = []
        for leg_body, lp in leg_pairs:
            lbb = leg_body.boundingBox
            if (bb.maxPoint.x > lbb.minPoint.x and bb.minPoint.x < lbb.maxPoint.x and
                bb.maxPoint.y > lbb.minPoint.y and bb.minPoint.y < lbb.maxPoint.y):
                legs_to_cut.append(lp)
        if legs_to_cut:
            bp = board.createForAssemblyContext(bt_occ)
            combine(root, bp, legs_to_cut, CUT, True, f"FloorNotch_{board.name}")

    # ==============================================================
    #  7. EPILOGUE
    # ==============================================================
    all_comps = [leg_c, lr_c, sr_c, sl_c, bt_c]
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

    for comp_name, c in [("Root", root), ("Legs", leg_c), ("LongRails", lr_c),
                          ("ShortRails", sr_c), ("Slats", sl_c), ("Bottom", bt_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{comp_name}: {len(names)} bodies -> {names}")

    sp.apply_appearance("teak a", bodies=[leg_c.bRepBodies.item(i).name for i in range(leg_c.bRepBodies.count)])
    sp.apply_appearance("teak b", bodies=[lr_c.bRepBodies.item(i).name for i in range(lr_c.bRepBodies.count)])
    sp.apply_appearance("teak c", bodies=[sr_c.bRepBodies.item(i).name for i in range(sr_c.bRepBodies.count)])
    sp.apply_appearance("teak d", bodies=[sl_c.bRepBodies.item(i).name for i in range(sl_c.bRepBodies.count)])
    sp.apply_appearance("teak",   bodies=[bt_c.bRepBodies.item(i).name for i in range(bt_c.bRepBodies.count)])

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
