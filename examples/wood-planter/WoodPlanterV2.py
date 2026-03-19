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


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters

    # ==============================================================
    #  PARAMETERS
    # ==============================================================
    for pname, expr, unit in [
        ("planter_length",    "60 in",    "in"),
        ("planter_width",     "20 in",    "in"),
        ("total_height",      "40 in",    "in"),
        ("leg_below_body",    "10 in",    "in"),
        ("leg_size",          "3 in",     "in"),
        ("rail_thickness",    "2 in",     "in"),
        ("rail_height",       "3 in",     "in"),
        ("tenon_depth",       "2 in",     "in"),
        ("tenon_width",       "1.25 in",  "in"),
        ("tenon_height",      "1.25 in",  "in"),
        ("groove_width",      "0.375 in", "in"),
        ("groove_depth",      "0.375 in", "in"),
        ("frame_tongue_thick","0.34 in",  "in"),
        ("bottom_thickness",  "0.75 in",  "in"),
        ("slat_width",        "4 in",     "in"),
        ("slat_thickness",    "0.5 in",   "in"),
        ("slat_tg_width",     "0.25 in",  "in"),
        ("slat_tg_depth",     "0.25 in",  "in"),
        ("drainage_gap",      "0.25 in",  "in"),
        ("dm_bt_w",           "0.25 in",  "in"),
        ("dm_bt_h",           "0.5 in",   "in"),
        ("dm_bt_d",           "0.75 in",  "in"),
    ]:
        params.add(pname, adsk.core.ValueInput.createByString(expr), unit, "")

    for pname, expr, unit in [
        ("long_shoulder",  "planter_length - 2 * leg_size",                            "in"),
        ("short_shoulder", "planter_width - 2 * leg_size",                             "in"),
        ("lo_z",           "leg_below_body",                                           "in"),
        ("hi_z",           "total_height - rail_height",                               "in"),
        ("groove_offset",  "(rail_thickness - groove_width) / 2",                      "in"),
        ("long_t_zoff",    "(rail_height - 2 * tenon_height) / 3",                    "in"),
        ("short_t_zoff",   "2 * (rail_height - 2 * tenon_height) / 3 + tenon_height", "in"),
        ("body_z",         "leg_below_body + rail_height",                             "in"),
        ("body_h",         "total_height - 2 * rail_height - leg_below_body",          "in"),
        ("full_slat_h",    "total_height - 2 * rail_height + 2 * groove_depth - leg_below_body", "in"),
        ("groove_span",    "total_height - leg_below_body",                            "in"),
        ("mid_x",          "planter_length / 2",                                       "in"),
        ("mid_y",          "planter_width / 2",                                        "in"),
        ("bottom_slat_spacing", "bottom_thickness + drainage_gap",                     "in"),
        ("bottom_slat_length", "planter_width - 2 * rail_thickness",                  "in"),
    ]:
        params.add(pname, adsk.core.ValueInput.createByString(expr), unit, "")

    for pname, expr in [
        ("n_long_slats",    "floor(long_shoulder / slat_width)"),
        ("n_short_slats",   "floor(short_shoulder / slat_width)"),
        ("n_bottom_slats",  "floor((long_shoulder + drainage_gap) / (bottom_thickness + drainage_gap))"),
    ]:
        params.add(pname, adsk.core.ValueInput.createByString(expr), "", "")

    # ==============================================================
    #  HELPERS
    # ==============================================================
    def ev(e):
        p = params.itemByName(e)
        return p.value if p else design.unitsManager.evaluateExpression(e, "cm")

    def sketch_rect(comp, plane, x0e, y0e, we, he, name="Sk"):
        sk = comp.sketches.add(plane)
        sk.name = name
        x0, y0, w, h = ev(x0e), ev(y0e), ev(we), ev(he)
        rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(
            adsk.core.Point3D.create(x0, y0, 0),
            adsk.core.Point3D.create(x0 + w, y0 + h, 0))
        d = sk.sketchDimensions
        d.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
            adsk.core.Point3D.create(x0+w/2, y0-1, 0)).parameter.expression = we
        d.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
            adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
            adsk.core.Point3D.create(x0+w+1, y0+h/2, 0)).parameter.expression = he
        d.addDistanceDimension(sk.originPoint, rect[0].startSketchPoint,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
            adsk.core.Point3D.create(x0/2, y0-2, 0)).parameter.expression = x0e
        d.addDistanceDimension(sk.originPoint, rect[0].startSketchPoint,
            adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
            adsk.core.Point3D.create(x0-1, y0/2, 0)).parameter.expression = y0e
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

    # --- Front lower rail ---
    flo_pl = off_plane(lr_c, lr_c.xYConstructionPlane, "lo_z", "FLo_Pl")
    _, pr = sketch_rect(lr_c, flo_pl,
        "leg_size", "0 in", "long_shoulder", "rail_thickness", "FLo_Rail_Sk")
    ext_flo = ext_new(lr_c, pr, "rail_height", "FLo_Rail")
    flo_body = ext_flo.bodies.item(0)
    flo_body.name = "LR_Front_Lower"

    # Left tenon (NewBody)
    flo_t_pl = off_plane(lr_c, lr_c.xYConstructionPlane,
        "lo_z + long_t_zoff", "FLo_Tenon_Pl")
    _, pr = sketch_rect(lr_c, flo_t_pl,
        "leg_size - tenon_depth", "(rail_thickness - tenon_width) / 2",
        "tenon_depth", "tenon_width", "FLo_Tenon_L_Sk")
    ext_flo_t = ext_new(lr_c, pr, "tenon_height", "FLo_Tenon_L")
    flo_tenon_l = ext_flo_t.bodies.item(0)
    flo_tenon_l.name = "FLo_Tenon_L"

    # Mirror left tenon across rail X-midpoint → right tenon
    flo_xmid = off_plane(lr_c, lr_c.yZConstructionPlane,
        "leg_size + long_shoulder / 2", "FLo_XMid")
    mir_flo_t = mirror_feat(lr_c, [ext_flo_t], flo_xmid, "FLo_MirTenon")
    flo_tenon_r = mir_flo_t.bodies.item(0)
    flo_tenon_r.name = "FLo_Tenon_R"

    # JOIN both tenons into rail
    combine(lr_c, flo_body, [flo_tenon_l, flo_tenon_r], JOIN, False, "FLo_JoinTenons")

    # Groove on top of front lower rail (for slat frame tongues)
    flo_grv_pl = off_plane(lr_c, lr_c.xYConstructionPlane,
        "lo_z + rail_height - groove_depth", "FLo_Groove_Pl")
    _, pr = sketch_rect(lr_c, flo_grv_pl,
        "leg_size", "groove_offset",
        "long_shoulder", "groove_width", "FLo_Groove_Sk")
    ext_cut(lr_c, pr, "groove_depth", flo_body, "FLo_Groove")

    # --- Front upper rail ---
    fhi_pl = off_plane(lr_c, lr_c.xYConstructionPlane, "hi_z", "FHi_Pl")
    _, pr = sketch_rect(lr_c, fhi_pl,
        "leg_size", "0 in", "long_shoulder", "rail_thickness", "FHi_Rail_Sk")
    ext_fhi = ext_new(lr_c, pr, "rail_height", "FHi_Rail")
    fhi_body = ext_fhi.bodies.item(0)
    fhi_body.name = "LR_Front_Upper"

    # Left tenon
    fhi_t_pl = off_plane(lr_c, lr_c.xYConstructionPlane,
        "hi_z + long_t_zoff", "FHi_Tenon_Pl")
    _, pr = sketch_rect(lr_c, fhi_t_pl,
        "leg_size - tenon_depth", "(rail_thickness - tenon_width) / 2",
        "tenon_depth", "tenon_width", "FHi_Tenon_L_Sk")
    ext_fhi_t = ext_new(lr_c, pr, "tenon_height", "FHi_Tenon_L")
    fhi_tenon_l = ext_fhi_t.bodies.item(0)
    fhi_tenon_l.name = "FHi_Tenon_L"

    # Mirror left tenon → right tenon (reuse same midplane)
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

    # Mirror front pair → back pair
    lr_mid_xz = off_plane(lr_c, lr_c.xZConstructionPlane, "mid_y", "LR_MidXZ")
    mir_lr = mirror_bodies(lr_c, [flo_body, fhi_body], lr_mid_xz, "Mir_LR_Back")
    blo_body = mir_lr.bodies.item(0)
    blo_body.name = "LR_Back_Lower"
    bhi_body = mir_lr.bodies.item(1)
    bhi_body.name = "LR_Back_Upper"

    # ==============================================================
    #  3. SHORT RAILS  (ShortRails component)
    #
    #  Same pattern as long rails but rotated, staggered tenon Z.
    # ==============================================================

    # --- Left lower rail ---
    llo_pl = off_plane(sr_c, sr_c.xYConstructionPlane, "lo_z", "LLo_Pl")
    _, pr = sketch_rect(sr_c, llo_pl,
        "0 in", "leg_size", "rail_thickness", "short_shoulder", "LLo_Rail_Sk")
    ext_llo = ext_new(sr_c, pr, "rail_height", "LLo_Rail")
    llo_body = ext_llo.bodies.item(0)
    llo_body.name = "SR_Left_Lower"

    # Front tenon (NewBody)
    llo_t_pl = off_plane(sr_c, sr_c.xYConstructionPlane,
        "lo_z + short_t_zoff", "LLo_Tenon_Pl")
    _, pr = sketch_rect(sr_c, llo_t_pl,
        "(rail_thickness - tenon_width) / 2", "leg_size - tenon_depth",
        "tenon_width", "tenon_depth", "LLo_Tenon_F_Sk")
    ext_llo_t = ext_new(sr_c, pr, "tenon_height", "LLo_Tenon_F")
    llo_tenon_f = ext_llo_t.bodies.item(0)
    llo_tenon_f.name = "LLo_Tenon_F"

    # Mirror front tenon across rail Y-midpoint → back tenon
    llo_ymid = off_plane(sr_c, sr_c.xZConstructionPlane,
        "leg_size + short_shoulder / 2", "LLo_YMid")
    mir_llo_t = mirror_feat(sr_c, [ext_llo_t], llo_ymid, "LLo_MirTenon")
    llo_tenon_b = mir_llo_t.bodies.item(0)
    llo_tenon_b.name = "LLo_Tenon_B"

    # JOIN both tenons into rail
    combine(sr_c, llo_body, [llo_tenon_f, llo_tenon_b], JOIN, False, "LLo_JoinTenons")

    # Groove on top of left lower rail
    llo_grv_pl = off_plane(sr_c, sr_c.xYConstructionPlane,
        "lo_z + rail_height - groove_depth", "LLo_Groove_Pl")
    _, pr = sketch_rect(sr_c, llo_grv_pl,
        "groove_offset", "leg_size",
        "groove_width", "short_shoulder", "LLo_Groove_Sk")
    ext_cut(sr_c, pr, "groove_depth", llo_body, "LLo_Groove")

    # --- Left upper rail ---
    lhi_pl = off_plane(sr_c, sr_c.xYConstructionPlane, "hi_z", "LHi_Pl")
    _, pr = sketch_rect(sr_c, lhi_pl,
        "0 in", "leg_size", "rail_thickness", "short_shoulder", "LHi_Rail_Sk")
    ext_lhi = ext_new(sr_c, pr, "rail_height", "LHi_Rail")
    lhi_body = ext_lhi.bodies.item(0)
    lhi_body.name = "SR_Left_Upper"

    # Front tenon
    lhi_t_pl = off_plane(sr_c, sr_c.xYConstructionPlane,
        "hi_z + short_t_zoff", "LHi_Tenon_Pl")
    _, pr = sketch_rect(sr_c, lhi_t_pl,
        "(rail_thickness - tenon_width) / 2", "leg_size - tenon_depth",
        "tenon_width", "tenon_depth", "LHi_Tenon_F_Sk")
    ext_lhi_t = ext_new(sr_c, pr, "tenon_height", "LHi_Tenon_F")
    lhi_tenon_f = ext_lhi_t.bodies.item(0)
    lhi_tenon_f.name = "LHi_Tenon_F"

    # Mirror front tenon → back tenon (reuse same midplane)
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

    # Mirror left pair → right pair
    sr_mid_yz = off_plane(sr_c, sr_c.yZConstructionPlane, "mid_x", "SR_MidYZ")
    mir_sr = mirror_bodies(sr_c, [llo_body, lhi_body], sr_mid_yz, "Mir_SR_Right")
    rlo_body = mir_sr.bodies.item(0)
    rlo_body.name = "SR_Right_Lower"
    rhi_body = mir_sr.bodies.item(1)
    rhi_body.name = "SR_Right_Upper"

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

    # CUT each leg with its 4 adjacent rails
    combine(root, fl_proxy, [flo_proxy, fhi_proxy, llo_proxy, lhi_proxy],
            CUT, True, "Mort_FL")
    combine(root, fr_proxy, [flo_proxy, fhi_proxy, rlo_proxy, rhi_proxy],
            CUT, True, "Mort_FR")
    combine(root, bl_proxy, [blo_proxy, bhi_proxy, llo_proxy, lhi_proxy],
            CUT, True, "Mort_BL")
    combine(root, br_proxy, [blo_proxy, bhi_proxy, rlo_proxy, rhi_proxy],
            CUT, True, "Mort_BR")

    # ==============================================================
    #  5. SLATS  (Slats component)
    #
    #  Mirror template + independent pattern approach.
    # ==============================================================
    sl_body_pl = off_plane(sl_c, sl_c.xYConstructionPlane, "body_z", "Slat_BodyZ")
    sl_top_pl  = off_plane(sl_c, sl_c.xYConstructionPlane, "hi_z", "Slat_TopZ")
    sl_bot_pl  = off_plane(sl_c, sl_c.xYConstructionPlane,
        "lo_z + rail_height - groove_depth", "Slat_BotZ")
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

        _, pr = sketch_rect(sl_c, sl_bot_pl,
            "leg_size + long_shoulder", fy_tng,
            "groove_depth", "frame_tongue_thick", "FGap_REdge_Sk")
        fgap_feats.append(ext_join(sl_c, pr, "full_slat_h", fg_body, "FGap_REdge"))

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

        _, pr = sketch_rect(sl_c, sl_bot_pl,
            lx_tng, "leg_size + short_shoulder",
            "frame_tongue_thick", "groove_depth", "LGap_BEdge_Sk")
        lgap_feats.append(ext_join(sl_c, pr, "full_slat_h", lg_body, "LGap_BEdge"))

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
    #  6. BOTTOM SLATS + DOMINO JOINERY  (Bottom component)
    #
    #  Slats run along Y (width), patterned along X (length).
    #  Each slat butts against front/back lower rail inner face.
    #  Domino voids at each mating face CUT both slat and rail.
    # ==============================================================
    bt_pl = off_plane(bt_c, bt_c.xYConstructionPlane,
        "lo_z", "Bottom_Pl")
    _, pr = sketch_rect(bt_c, bt_pl,
        "leg_size", "rail_thickness",
        "bottom_thickness", "bottom_slat_length", "BottomSlat_Sk")
    ext_bt = ext_new(bt_c, pr, "bottom_thickness", "BottomSlat_1")
    bt_tmpl = ext_bt.bodies.item(0)
    bt_tmpl.name = "BottomSlat_1"

    # --- Domino voids (sketched on slat mating face, not origin) ---
    # Find the front mating face of the template slat (min Y face)
    bt_front_face = None
    min_y = float('inf')
    for i in range(bt_tmpl.faces.count):
        f = bt_tmpl.faces.item(i)
        if f.pointOnFace.y < min_y:
            min_y = f.pointOnFace.y
            bt_front_face = f

    # Stadium slot on the slat's front face, centered on the face
    _, pr = sketch_slot(bt_c, bt_front_face,
        "leg_size + bottom_thickness / 2",
        "lo_z + bottom_thickness / 2",
        "dm_bt_h", "dm_bt_w", vertical=True, name="BtDm_Front_Sk")
    ext_dm_f = ext_new_sym(bt_c, pr, "dm_bt_d", "BtDm_Front_Void")
    dm_f_body = ext_dm_f.bodies.item(0)
    dm_f_body.name = "BtDm_Front"

    # Mirror front void → back void
    bt_mid_xz = off_plane(bt_c, bt_c.xZConstructionPlane, "mid_y", "Bt_MidXZ")
    mir_dm = mirror_feat(bt_c, [ext_dm_f], bt_mid_xz, "BtDm_MirBack")
    dm_b_body = mir_dm.bodies.item(0)
    dm_b_body.name = "BtDm_Back"

    # CUT domino pockets from template slat (voids survive for rail CUT)
    combine(bt_c, bt_tmpl, [dm_f_body, dm_b_body], CUT, True, "BtDm_CutSlat")

    # Pattern slat + void bodies along X
    pat_bt = body_pattern(bt_c, bt_tmpl, bt_c.xConstructionAxis,
        "n_bottom_slats", "bottom_slat_spacing", "Pat_BottomSlats")
    for i in range(pat_bt.bodies.count):
        pat_bt.bodies.item(i).name = f"BottomSlat_{i + 2}"

    pat_dm_f = body_pattern(bt_c, dm_f_body, bt_c.xConstructionAxis,
        "n_bottom_slats", "bottom_slat_spacing", "Pat_BtDm_Front")
    pat_dm_b = body_pattern(bt_c, dm_b_body, bt_c.xConstructionAxis,
        "n_bottom_slats", "bottom_slat_spacing", "Pat_BtDm_Back")

    # Collect all void bodies
    dm_f_all = [dm_f_body] + [pat_dm_f.bodies.item(i) for i in range(pat_dm_f.bodies.count)]
    dm_b_all = [dm_b_body] + [pat_dm_b.bodies.item(i) for i in range(pat_dm_b.bodies.count)]

    # CUT front/back lower rails via assembly proxies
    dm_f_proxies = [b.createForAssemblyContext(bt_occ) for b in dm_f_all]
    dm_b_proxies = [b.createForAssemblyContext(bt_occ) for b in dm_b_all]
    combine(root, flo_proxy, dm_f_proxies, CUT, True, "BtDm_CutFrontRail")
    combine(root, blo_proxy, dm_b_proxies, CUT, True, "BtDm_CutBackRail")

    # ==============================================================
    #  7. FIT VIEW
    # ==============================================================
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
