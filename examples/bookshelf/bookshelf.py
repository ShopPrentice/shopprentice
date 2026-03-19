"""
Parametric Solid Wood Bookshelf
===============================
70"H x 30"W x 20"D, 3/4" board stock.
Through M&T shelves + domino kick + 1/2" plywood backboard + through dovetail top.

Build approach:
  - Features live inside their respective components (Sides, Shelves, Top, Kick, Back)
  - Mirrors replicate tenons/tails (1 extrude → 4 via 2 mirrors)
  - Body patterns replicate shelves, domino voids, and dovetail tails
  - Cross-component CUT in root via assembly proxies (bulk, keepTool=True)

Coordinate system:
  X = width (30")   Y = depth (20")   Z = height (70")
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
        ("total_height",  "70 in",    "in"),
        ("total_width",   "30 in",    "in"),
        ("total_depth",   "20 in",    "in"),
        ("board_thick",   "0.75 in",  "in"),
        ("kick_height",   "4 in",     "in"),
        ("back_thick",    "0.5 in",   "in"),
        ("n_shelves",     "5",        ""),
        ("mt_tenon_w",    "2 in",     "in"),
        ("dm_kick_w",     "5 mm",     "in"),
        ("dm_kick_h",     "30 mm",    "in"),
        ("dm_kick_d",     "15 mm",    "in"),
        ("dm_back_w",     "6 mm",     "in"),
        ("dm_back_h",     "40 mm",    "in"),
        ("dm_back_d",     "10 mm",    "in"),
        ("dm_kick_count", "2",        ""),
        ("dm_back_count", "3",        ""),
        ("dt_angle",      "8 deg",    "deg"),
        ("dt_tail_w",     "2 in",     "in"),
        ("dt_tail_count", "8",        ""),
    ]:
        params.add(pname, adsk.core.ValueInput.createByString(expr), unit, "")

    for pname, expr, unit in [
        ("inner_width",    "total_width - 2 * board_thick",                              "in"),
        ("shelf_depth",    "total_depth - back_thick",                                   "in"),
        ("back_height",    "total_height - board_thick - kick_height",                   "in"),
        ("shelf_spacing",  "(total_height - 2 * board_thick - kick_height) / n_shelves", "in"),
        ("mt_tenon_y1",    "(total_depth - back_thick) / 4 - mt_tenon_w / 2",            "in"),
        ("dm_kick_zsp",    "kick_height / (dm_kick_count + 1)",                          "in"),
        ("dm_back_xsp",    "inner_width / (dm_back_count + 1)",                          "in"),
        ("dt_pin_w",       "total_depth / dt_tail_count - dt_tail_w",                    "in"),
        ("dt_pitch",       "total_depth / dt_tail_count",                                "in"),
        ("dt_narrow_w",    "dt_tail_w - 2 * board_thick * tan(dt_angle)",                "in"),
        ("dt_start_y",     "dt_pin_w / 2 + dt_tail_w / 2",                              "in"),
    ]:
        params.add(pname, adsk.core.ValueInput.createByString(expr), unit, "")

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

    def ext_new(comp, prof, dist, name="Ext"):
        inp = comp.features.extrudeFeatures.createInput(
            prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        inp.setDistanceExtent(False, adsk.core.ValueInput.createByString(dist))
        f = comp.features.extrudeFeatures.add(inp)
        f.name = name
        return f

    def ext_new_sym(comp, prof, dist, name="Ext"):
        inp = comp.features.extrudeFeatures.createInput(
            prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        inp.setSymmetricExtent(
            adsk.core.ValueInput.createByString(dist), False,
            adsk.core.ValueInput.createByString("0 deg"))
        f = comp.features.extrudeFeatures.add(inp)
        f.name = name
        return f

    def sketch_slot(comp, plane, cxe, cye, long_e, short_e, vertical, name="Sk"):
        sk = comp.sketches.add(plane)
        sk.name = name
        slines = sk.sketchCurves.sketchLines
        sarcs = sk.sketchCurves.sketchArcs
        cx, cy = ev(cxe), ev(cye)
        lg, sh = ev(long_e), ev(short_e)
        r = sh / 2
        hl = (lg - sh) / 2
        if vertical:
            br = adsk.core.Point3D.create(cx + r, cy - hl, 0)
            tr = adsk.core.Point3D.create(cx + r, cy + hl, 0)
            tc = adsk.core.Point3D.create(cx, cy + hl, 0)
            tl = adsk.core.Point3D.create(cx - r, cy + hl, 0)
            bl = adsk.core.Point3D.create(cx - r, cy - hl, 0)
            bc = adsk.core.Point3D.create(cx, cy - hl, 0)
            l_right = slines.addByTwoPoints(br, tr)
            arc_top = sarcs.addByCenterStartSweep(tc, tr, math.pi)
            l_left = slines.addByTwoPoints(tl, bl)
            arc_bot = sarcs.addByCenterStartSweep(bc, bl, math.pi)
            sk.geometricConstraints.addVertical(l_right)
            sk.geometricConstraints.addVertical(l_left)
            sk.geometricConstraints.addTangent(l_right, arc_top)
            sk.geometricConstraints.addTangent(arc_top, l_left)
            sk.geometricConstraints.addTangent(l_left, arc_bot)
            sk.geometricConstraints.addTangent(arc_bot, l_right)
            d = sk.sketchDimensions
            d.addRadialDimension(arc_bot,
                adsk.core.Point3D.create(cx + r + 1, cy - hl, 0)
            ).parameter.expression = short_e + " / 2"
            d.addDistanceDimension(
                arc_bot.centerSketchPoint, arc_top.centerSketchPoint,
                adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
                adsk.core.Point3D.create(cx + r + 2, cy, 0)
            ).parameter.expression = long_e + " - " + short_e
            d.addDistanceDimension(
                sk.originPoint, arc_bot.centerSketchPoint,
                adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
                adsk.core.Point3D.create(cx / 2, cy - hl - 1, 0)
            ).parameter.expression = cxe
            d.addDistanceDimension(
                sk.originPoint, arc_bot.centerSketchPoint,
                adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
                adsk.core.Point3D.create(cx - r - 1, (cy - hl) / 2, 0)
            ).parameter.expression = cye + " - (" + long_e + " - " + short_e + ") / 2"
        else:
            bsl = adsk.core.Point3D.create(cx - hl, cy - r, 0)
            bsr = adsk.core.Point3D.create(cx + hl, cy - r, 0)
            rc = adsk.core.Point3D.create(cx + hl, cy, 0)
            tsr = adsk.core.Point3D.create(cx + hl, cy + r, 0)
            tsl = adsk.core.Point3D.create(cx - hl, cy + r, 0)
            lc = adsk.core.Point3D.create(cx - hl, cy, 0)
            l_bot = slines.addByTwoPoints(bsl, bsr)
            arc_right = sarcs.addByCenterStartSweep(rc, bsr, math.pi)
            l_top = slines.addByTwoPoints(tsr, tsl)
            arc_left = sarcs.addByCenterStartSweep(lc, tsl, math.pi)
            sk.geometricConstraints.addHorizontal(l_bot)
            sk.geometricConstraints.addHorizontal(l_top)
            sk.geometricConstraints.addTangent(l_bot, arc_right)
            sk.geometricConstraints.addTangent(arc_right, l_top)
            sk.geometricConstraints.addTangent(l_top, arc_left)
            sk.geometricConstraints.addTangent(arc_left, l_bot)
            d = sk.sketchDimensions
            d.addRadialDimension(arc_left,
                adsk.core.Point3D.create(cx - hl - 1, cy + r + 1, 0)
            ).parameter.expression = short_e + " / 2"
            d.addDistanceDimension(
                arc_left.centerSketchPoint, arc_right.centerSketchPoint,
                adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
                adsk.core.Point3D.create(cx, cy - r - 2, 0)
            ).parameter.expression = long_e + " - " + short_e
            d.addDistanceDimension(
                sk.originPoint, arc_left.centerSketchPoint,
                adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
                adsk.core.Point3D.create((cx - hl) / 2, cy - r - 1, 0)
            ).parameter.expression = cxe + " - (" + long_e + " - " + short_e + ") / 2"
            d.addDistanceDimension(
                sk.originPoint, arc_left.centerSketchPoint,
                adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
                adsk.core.Point3D.create(cx - hl - 2, cy / 2, 0)
            ).parameter.expression = cye
        return sk, sk.profiles.item(0)

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
    def make_comp(root_comp, name):
        occ = root_comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        occ.component.name = name
        return occ

    sides_occ = make_comp(root, "Sides")
    shelves_occ = make_comp(root, "Shelves")
    top_occ = make_comp(root, "Top")
    kick_occ = make_comp(root, "Kick")
    back_occ = make_comp(root, "Back")

    sides = sides_occ.component
    shelves_c = shelves_occ.component
    top_c = top_occ.component
    kick_c = kick_occ.component
    back_c = back_occ.component

    # ==============================================================
    #  1. SIDE BOARDS  (Sides component)
    # ==============================================================
    _, pr = sketch_rect(sides, sides.xYConstructionPlane,
        "0 in", "0 in", "board_thick", "total_depth", "LeftSide_Sk")
    left_side = ext_new(sides, pr, "total_height", "LeftSide").bodies.item(0)
    left_side.name = "Side_Left"

    _, pr = sketch_rect(sides, sides.xYConstructionPlane,
        "total_width - board_thick", "0 in", "board_thick", "total_depth",
        "RightSide_Sk")
    right_side = ext_new(sides, pr, "total_height", "RightSide").bodies.item(0)
    right_side.name = "Side_Right"

    # ==============================================================
    #  2. SHELF TEMPLATE + BODY PATTERN  (Shelves component)
    #
    #  One shelf + 4 tenons (mirrors) + JOIN + domino voids →
    #  CUT voids from shelf → body pattern shelf + body pattern voids
    # ==============================================================
    sh_YMid = off_plane(shelves_c, shelves_c.xZConstructionPlane,
                        "shelf_depth / 2", "YMid_Pl")
    sh_XMid = off_plane(shelves_c, shelves_c.yZConstructionPlane,
                        "total_width / 2", "XMid_Pl")
    sh_pl = off_plane(shelves_c, shelves_c.xYConstructionPlane,
                      "kick_height", "Shelf_Pl")

    # Shelf body (depth = shelf_depth, recessed for backboard)
    _, pr = sketch_rect(shelves_c, sh_pl, "board_thick", "0 in",
                        "inner_width", "shelf_depth", "Shelf_Sk")
    ext_sh = ext_new(shelves_c, pr, "board_thick", "ShelfBody")
    sh_body = ext_sh.bodies.item(0)
    sh_body.name = "Shelf"

    # One tenon (left-front)
    _, pr = sketch_rect(shelves_c, sh_pl, "0 in", "mt_tenon_y1",
                        "board_thick", "mt_tenon_w", "Sh_Tenon_Sk")
    ext_t = ext_new(shelves_c, pr, "board_thick", "Sh_Tenon")

    # Mirror tenon across YMid → left-back tenon
    mir_y = mirror_feat(shelves_c, [ext_t], sh_YMid, "Sh_MirY")
    # Mirror [tenon + mir_y] across XMid → right-front + right-back tenons
    mir_x = mirror_feat(shelves_c, [ext_t, mir_y], sh_XMid, "Sh_MirX")

    # JOIN all 4 tenon bodies into shelf body
    t_bodies = [ext_t.bodies.item(0)]
    for j in range(mir_y.bodies.count):
        t_bodies.append(mir_y.bodies.item(j))
    for j in range(mir_x.bodies.count):
        t_bodies.append(mir_x.bodies.item(j))
    combine(shelves_c, sh_body, t_bodies, JOIN, False, "Sh_JoinTenons")

    # -- Shelf-to-backboard domino voids (stadium, symmetric extrude) --
    # Sketch on the actual back face of the shelf body (mating surface)
    shelf_depth_val = ev("shelf_depth")
    back_face = None
    for face in sh_body.faces:
        geom = face.geometry
        if isinstance(geom, adsk.core.Plane):
            if geom.normal.y > 0.99:
                if abs(face.pointOnFace.y - shelf_depth_val) < 0.01:
                    back_face = face
                    break

    # Find bottom-left corner of back face (min X + min Z in model space)
    corner_v = None
    min_val = float('inf')
    for vi in range(back_face.vertices.count):
        v = back_face.vertices.item(vi)
        val = v.geometry.x + v.geometry.z
        if val < min_val:
            min_val = val
            corner_v = v

    # Create sketch on back face, project corner as dimension reference
    sk_dm = shelves_c.sketches.add(back_face)
    sk_dm.name = "ShDm_Sk"
    ref = sk_dm.project(corner_v).item(0)
    ref_sx, ref_sy = ref.geometry.x, ref.geometry.y

    # Compute domino center in sketch space via modelToSketchSpace
    bt_val = ev("board_thick")
    kh_val = ev("kick_height")
    dm_xsp_val = ev("dm_back_xsp")
    dm_h_val = ev("dm_back_h")
    dm_w_val = ev("dm_back_w")

    dm_model = adsk.core.Point3D.create(
        bt_val + dm_xsp_val, shelf_depth_val, kh_val + bt_val / 2)
    dm_ss = sk_dm.modelToSketchSpace(dm_model)
    cx, cy = dm_ss.x, dm_ss.y

    # Stadium geometry — horizontal (long axis along sketch X)
    r = dm_w_val / 2
    hl = (dm_h_val - dm_w_val) / 2
    slines = sk_dm.sketchCurves.sketchLines
    sarcs = sk_dm.sketchCurves.sketchArcs

    bsl = adsk.core.Point3D.create(cx - hl, cy - r, 0)
    bsr = adsk.core.Point3D.create(cx + hl, cy - r, 0)
    rc_pt = adsk.core.Point3D.create(cx + hl, cy, 0)
    tsr = adsk.core.Point3D.create(cx + hl, cy + r, 0)
    tsl = adsk.core.Point3D.create(cx - hl, cy + r, 0)
    lc_pt = adsk.core.Point3D.create(cx - hl, cy, 0)

    l_bot = slines.addByTwoPoints(bsl, bsr)
    arc_right = sarcs.addByCenterStartSweep(rc_pt, bsr, math.pi)
    l_top = slines.addByTwoPoints(tsr, tsl)
    arc_left = sarcs.addByCenterStartSweep(lc_pt, tsl, math.pi)

    sk_dm.geometricConstraints.addHorizontal(l_bot)
    sk_dm.geometricConstraints.addHorizontal(l_top)
    sk_dm.geometricConstraints.addTangent(l_bot, arc_right)
    sk_dm.geometricConstraints.addTangent(arc_right, l_top)
    sk_dm.geometricConstraints.addTangent(l_top, arc_left)
    sk_dm.geometricConstraints.addTangent(arc_left, l_bot)

    dims = sk_dm.sketchDimensions
    dims.addRadialDimension(arc_left,
        adsk.core.Point3D.create(cx - hl - 1, cy + r + 1, 0)
    ).parameter.expression = "dm_back_w / 2"
    dims.addDistanceDimension(
        arc_left.centerSketchPoint, arc_right.centerSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        adsk.core.Point3D.create(cx, cy - r - 2, 0)
    ).parameter.expression = "dm_back_h - dm_back_w"

    # Position from corner reference (positive offsets into the face)
    lc_sx, lc_sy = cx - hl, cy
    if lc_sx >= ref_sx:
        h1, h2 = ref, arc_left.centerSketchPoint
    else:
        h1, h2 = arc_left.centerSketchPoint, ref
    dims.addDistanceDimension(h1, h2,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        adsk.core.Point3D.create((ref_sx + lc_sx) / 2, cy - r - 1, 0)
    ).parameter.expression = "dm_back_xsp - (dm_back_h - dm_back_w) / 2"

    if lc_sy >= ref_sy:
        v1, v2 = ref, arc_left.centerSketchPoint
    else:
        v1, v2 = arc_left.centerSketchPoint, ref
    dims.addDistanceDimension(v1, v2,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        adsk.core.Point3D.create(cx - hl - 2, (ref_sy + lc_sy) / 2, 0)
    ).parameter.expression = "board_thick / 2"

    # Select the stadium profile (smallest area, not the surrounding face)
    min_area = float('inf')
    pr = None
    for pi in range(sk_dm.profiles.count):
        p = sk_dm.profiles.item(pi)
        a = p.areaProperties().area
        if a < min_area:
            min_area = a
            pr = p
    ext_sh_dm = ext_new_sym(shelves_c, pr, "dm_back_d", "ShDm_Void")
    sh_dm_body = ext_sh_dm.bodies.item(0)
    sh_dm_body.name = "ShDm_Void"

    # X-pattern: dm_back_count voids at first shelf level
    sh_dm_pat_x = body_pattern(shelves_c, sh_dm_body, shelves_c.xConstructionAxis,
                                "dm_back_count", "dm_back_xsp", "ShDm_PatX")

    # Collect first-level void bodies
    first_level_voids = [sh_dm_body]
    for j in range(sh_dm_pat_x.bodies.count):
        first_level_voids.append(sh_dm_pat_x.bodies.item(j))

    # CUT all first-level voids from shelf template (keepTool=True)
    combine(shelves_c, sh_body, first_level_voids, CUT, True, "ShDm_CutShelf")

    # Body pattern shelf along Z → n_shelves identical shelf bodies (pockets replicate)
    shelf_pat = body_pattern(shelves_c, sh_body, shelves_c.zConstructionAxis,
                             "n_shelves", "shelf_spacing", "ShelfPattern")

    # Z-pattern all first-level voids together for backboard CUT at all levels
    void_coll = adsk.core.ObjectCollection.create()
    for v in first_level_voids:
        void_coll.add(v)
    sh_dm_z_inp = shelves_c.features.rectangularPatternFeatures.createInput(
        void_coll, shelves_c.zConstructionAxis,
        adsk.core.ValueInput.createByString("n_shelves"),
        adsk.core.ValueInput.createByString("shelf_spacing"),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    sh_dm_z_pat = shelves_c.features.rectangularPatternFeatures.add(sh_dm_z_inp)
    sh_dm_z_pat.name = "ShDm_PatZ"

    # Collect ALL void bodies (first-level + Z-pattern copies)
    all_sh_dm_voids = list(first_level_voids)
    for j in range(sh_dm_z_pat.bodies.count):
        all_sh_dm_voids.append(sh_dm_z_pat.bodies.item(j))

    # Collect all shelf bodies (template + pattern copies)
    all_shelf_bodies = [sh_body]
    for i in range(shelf_pat.bodies.count):
        all_shelf_bodies.append(shelf_pat.bodies.item(i))

    # ==============================================================
    #  3. SHELF MORTISES — bulk CUT  (root, assembly proxies)
    #
    #  2 CUT features create ALL shelf mortises on both sides.
    # ==============================================================
    all_shelf_proxies = [b.createForAssemblyContext(shelves_occ)
                         for b in all_shelf_bodies]
    left_side_proxy  = left_side.createForAssemblyContext(sides_occ)
    right_side_proxy = right_side.createForAssemblyContext(sides_occ)

    combine(root, left_side_proxy,  all_shelf_proxies, CUT, True, "ShelfMortL")
    combine(root, right_side_proxy, all_shelf_proxies, CUT, True, "ShelfMortR")

    # ==============================================================
    #  4. KICK BOARD + DOMINO VOIDS  (Kick component)
    #
    #  Kick flush with front (Y=0), domino voids for hidden joints.
    #  Mirror only the extrude (not the pattern) — Fusion limitation.
    #  Independent Z-pattern per side.
    # ==============================================================
    k_XMid = off_plane(kick_c, kick_c.yZConstructionPlane,
                       "total_width / 2", "XMid_Pl")

    _, pr = sketch_rect(kick_c, kick_c.xYConstructionPlane,
        "board_thick", "0 in", "inner_width", "board_thick", "Kick_Sk")
    kick_body = ext_new(kick_c, pr, "kick_height", "KickBoard").bodies.item(0)
    kick_body.name = "KickBoard"

    # -- Left-side domino voids (stadium, symmetric extrude) --
    # Sketch on the left end face of the kick board (mating surface)
    bt_val = ev("board_thick")
    left_face = None
    for face in kick_body.faces:
        geom = face.geometry
        if isinstance(geom, adsk.core.Plane):
            if geom.normal.x < -0.99:
                if abs(face.pointOnFace.x - bt_val) < 0.01:
                    left_face = face
                    break

    # Find bottom-front corner (min Y + min Z in model space)
    k_corner_v = None
    k_min_val = float('inf')
    for vi in range(left_face.vertices.count):
        v = left_face.vertices.item(vi)
        val = v.geometry.y + v.geometry.z
        if val < k_min_val:
            k_min_val = val
            k_corner_v = v

    # Create sketch on left face, project corner as dimension reference
    sk_kdm = kick_c.sketches.add(left_face)
    sk_kdm.name = "KDm_Sk"
    k_ref = sk_kdm.project(k_corner_v).item(0)
    k_ref_sx, k_ref_sy = k_ref.geometry.x, k_ref.geometry.y

    # Compute domino center in sketch space via modelToSketchSpace
    dm_kzsp_val = ev("dm_kick_zsp")
    dm_kh_val = ev("dm_kick_h")
    dm_kw_val = ev("dm_kick_w")

    kdm_model = adsk.core.Point3D.create(bt_val, bt_val / 2, dm_kzsp_val)
    kdm_ss = sk_kdm.modelToSketchSpace(kdm_model)
    kcx, kcy = kdm_ss.x, kdm_ss.y

    # Stadium geometry — vertical (long axis along sketch Y)
    kr = dm_kw_val / 2
    khl = (dm_kh_val - dm_kw_val) / 2
    kslines = sk_kdm.sketchCurves.sketchLines
    ksarcs = sk_kdm.sketchCurves.sketchArcs

    kbr = adsk.core.Point3D.create(kcx + kr, kcy - khl, 0)
    ktr = adsk.core.Point3D.create(kcx + kr, kcy + khl, 0)
    ktc = adsk.core.Point3D.create(kcx, kcy + khl, 0)
    ktl = adsk.core.Point3D.create(kcx - kr, kcy + khl, 0)
    kbl = adsk.core.Point3D.create(kcx - kr, kcy - khl, 0)
    kbc = adsk.core.Point3D.create(kcx, kcy - khl, 0)

    kl_right = kslines.addByTwoPoints(kbr, ktr)
    karc_top = ksarcs.addByCenterStartSweep(ktc, ktr, math.pi)
    kl_left = kslines.addByTwoPoints(ktl, kbl)
    karc_bot = ksarcs.addByCenterStartSweep(kbc, kbl, math.pi)

    sk_kdm.geometricConstraints.addVertical(kl_right)
    sk_kdm.geometricConstraints.addVertical(kl_left)
    sk_kdm.geometricConstraints.addTangent(kl_right, karc_top)
    sk_kdm.geometricConstraints.addTangent(karc_top, kl_left)
    sk_kdm.geometricConstraints.addTangent(kl_left, karc_bot)
    sk_kdm.geometricConstraints.addTangent(karc_bot, kl_right)

    kdims = sk_kdm.sketchDimensions
    kdims.addRadialDimension(karc_bot,
        adsk.core.Point3D.create(kcx + kr + 1, kcy - khl, 0)
    ).parameter.expression = "dm_kick_w / 2"
    kdims.addDistanceDimension(
        karc_bot.centerSketchPoint, karc_top.centerSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        adsk.core.Point3D.create(kcx + kr + 2, kcy, 0)
    ).parameter.expression = "dm_kick_h - dm_kick_w"

    # Position from corner reference (positive offsets into the face)
    kbc_sx, kbc_sy = kcx, kcy - khl
    if kbc_sx >= k_ref_sx:
        kh1, kh2 = k_ref, karc_bot.centerSketchPoint
    else:
        kh1, kh2 = karc_bot.centerSketchPoint, k_ref
    kdims.addDistanceDimension(kh1, kh2,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        adsk.core.Point3D.create((k_ref_sx + kbc_sx) / 2, kcy - khl - 1, 0)
    ).parameter.expression = "board_thick / 2"

    if kbc_sy >= k_ref_sy:
        kv1, kv2 = k_ref, karc_bot.centerSketchPoint
    else:
        kv1, kv2 = karc_bot.centerSketchPoint, k_ref
    kdims.addDistanceDimension(kv1, kv2,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        adsk.core.Point3D.create(kcx - kr - 1, (k_ref_sy + kbc_sy) / 2, 0)
    ).parameter.expression = "dm_kick_zsp - (dm_kick_h - dm_kick_w) / 2"

    # Select the stadium profile (smallest area)
    min_area = float('inf')
    kpr = None
    for pi in range(sk_kdm.profiles.count):
        p = sk_kdm.profiles.item(pi)
        a = p.areaProperties().area
        if a < min_area:
            min_area = a
            kpr = p
    ext_k_dm = ext_new_sym(kick_c, kpr, "dm_kick_d", "KDm_Void")
    k_dm_body_l = ext_k_dm.bodies.item(0)
    k_dm_body_l.name = "KDm_Left"

    k_dm_pat_l = body_pattern(kick_c, k_dm_body_l, kick_c.zConstructionAxis,
                               "dm_kick_count", "dm_kick_zsp", "KDm_PatZL")
    dm_kick_left = [k_dm_body_l]
    for i in range(k_dm_pat_l.bodies.count):
        dm_kick_left.append(k_dm_pat_l.bodies.item(i))

    # CUT left voids from kick (keepTool=True)
    combine(kick_c, kick_body, dm_kick_left, CUT, True, "KDm_CutKickL")

    # -- Right-side domino voids (mirror extrude only, then independent pattern) --
    mir_k_dm = mirror_feat(kick_c, [ext_k_dm], k_XMid, "KDm_MirX")
    k_dm_body_r = mir_k_dm.bodies.item(0)
    k_dm_body_r.name = "KDm_Right"

    k_dm_pat_r = body_pattern(kick_c, k_dm_body_r, kick_c.zConstructionAxis,
                               "dm_kick_count", "dm_kick_zsp", "KDm_PatZR")
    dm_kick_right = [k_dm_body_r]
    for i in range(k_dm_pat_r.bodies.count):
        dm_kick_right.append(k_dm_pat_r.bodies.item(i))

    # CUT right voids from kick (keepTool=True)
    combine(kick_c, kick_body, dm_kick_right, CUT, True, "KDm_CutKickR")

    # ==============================================================
    #  5. KICK DOMINO MORTISES — CUT sides  (root, assembly proxies)
    # ==============================================================
    dm_kick_left_proxies = [b.createForAssemblyContext(kick_occ)
                             for b in dm_kick_left]
    dm_kick_right_proxies = [b.createForAssemblyContext(kick_occ)
                              for b in dm_kick_right]
    combine(root, left_side_proxy,  dm_kick_left_proxies,  CUT, True, "KickDomL")
    combine(root, right_side_proxy, dm_kick_right_proxies, CUT, True, "KickDomR")

    # ==============================================================
    #  6. BACKBOARD  (Back component)
    #
    #  1/2" plywood panel flush with back surface
    # ==============================================================
    bk_pl = off_plane(back_c, back_c.xYConstructionPlane,
                      "kick_height", "Back_Pl")
    _, pr = sketch_rect(back_c, bk_pl, "board_thick",
                        "total_depth - back_thick",
                        "inner_width", "back_thick", "Back_Sk")
    back_body = ext_new(back_c, pr, "back_height", "BackPanel").bodies.item(0)
    back_body.name = "BackPanel"

    # ==============================================================
    #  7. BACKBOARD DOMINO CUTS  (root, assembly proxies)
    #
    #  CUT shelf domino void proxies from backboard
    # ==============================================================
    all_sh_dm_proxies = [b.createForAssemblyContext(shelves_occ)
                          for b in all_sh_dm_voids]
    back_proxy = back_body.createForAssemblyContext(back_occ)
    combine(root, back_proxy, all_sh_dm_proxies, CUT, True, "BackDomCut")

    # ==============================================================
    #  8. TOP BOARD + DOVETAIL TAILS + PATTERNS  (Top component)  — UNCHANGED
    #
    #  1 top board (full total_depth) + 1 left tail + mirror X → right tail
    #  Body pattern left tails along Y, body pattern right tails along Y
    # ==============================================================
    t_XMid = off_plane(top_c, top_c.yZConstructionPlane,
                       "total_width / 2", "XMid_Pl")

    tp = off_plane(top_c, top_c.xYConstructionPlane,
                   "total_height - board_thick", "Top_Pl")
    _, pr = sketch_rect(top_c, tp, "board_thick", "0 in",
                        "inner_width", "total_depth", "Top_Sk")
    top_body = ext_new(top_c, pr, "board_thick", "TopBoard").bodies.item(0)
    top_body.name = "TopBoard"

    dt_pl = off_plane(top_c, top_c.xYConstructionPlane,
                      "total_height - board_thick", "DT_Plane")

    # ONE left tail — parametric trapezoid sketch
    # Wide end at X=0 (outside face), narrow at X=board_thick (inside)
    bt = ev("board_thick")
    hp = ev("dt_pin_w") / 2
    delta = bt * math.tan(ev("dt_angle"))
    tw = ev("dt_tail_w")

    sk_dt = top_c.sketches.add(dt_pl)
    sk_dt.name = "DT_Left_Sk"
    dtl = sk_dt.sketchCurves.sketchLines

    p1 = adsk.core.Point3D.create(0, hp, 0)
    p2 = adsk.core.Point3D.create(0, hp + tw, 0)
    p3 = adsk.core.Point3D.create(bt, hp + tw - delta, 0)
    p4 = adsk.core.Point3D.create(bt, hp + delta, 0)

    l1 = dtl.addByTwoPoints(p1, p2)                                   # wide side (X=0)
    l2 = dtl.addByTwoPoints(l1.endSketchPoint, p3)                    # angled back
    l3 = dtl.addByTwoPoints(l2.endSketchPoint, p4)                    # narrow side (X=bt)
    l4 = dtl.addByTwoPoints(l3.endSketchPoint, l1.startSketchPoint)   # angled front

    # 8 constraints for 8 DOF
    sk_dt.geometricConstraints.addVertical(l1)
    sk_dt.geometricConstraints.addVertical(l3)
    d = sk_dt.sketchDimensions
    d.addDistanceDimension(l1.startSketchPoint, l1.endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        adsk.core.Point3D.create(-1, hp + tw / 2, 0)
    ).parameter.expression = "dt_tail_w"
    d.addDistanceDimension(l3.startSketchPoint, l3.endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        adsk.core.Point3D.create(bt + 1, hp + tw / 2, 0)
    ).parameter.expression = "dt_narrow_w"
    d.addDistanceDimension(l1.startSketchPoint, l3.endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        adsk.core.Point3D.create(bt / 2, hp - 1, 0)
    ).parameter.expression = "board_thick"
    d.addDistanceDimension(sk_dt.originPoint, l1.startSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        adsk.core.Point3D.create(-1, hp / 2, 0)
    ).parameter.expression = "dt_pin_w / 2"
    d.addDistanceDimension(sk_dt.originPoint, l1.startSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        adsk.core.Point3D.create(0, hp - 2, 0)
    ).parameter.expression = "0 in"
    d.addDistanceDimension(sk_dt.originPoint, l3.endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        adsk.core.Point3D.create(bt + 2, (hp + delta) / 2, 0)
    ).parameter.expression = "dt_pin_w / 2 + board_thick * tan(dt_angle)"

    ext_dt_l = ext_new(top_c, sk_dt.profiles.item(0), "board_thick", "DT_Left")
    left_tail = ext_dt_l.bodies.item(0)
    left_tail.name = "DT_Left"

    # Mirror single extrude across XMid → right tail
    mir_dt = mirror_feat(top_c, [ext_dt_l], t_XMid, "DT_MirX")
    right_tail = mir_dt.bodies.item(0)
    right_tail.name = "DT_Right"

    # Body pattern left tails along Y
    left_pat = body_pattern(top_c, left_tail, top_c.yConstructionAxis,
                            "dt_tail_count", "dt_pitch", "DT_PatL")

    # Body pattern right tails along Y
    right_pat = body_pattern(top_c, right_tail, top_c.yConstructionAxis,
                             "dt_tail_count", "dt_pitch", "DT_PatR")

    # Collect all tail bodies
    all_left_tails = [left_tail]
    for i in range(left_pat.bodies.count):
        all_left_tails.append(left_pat.bodies.item(i))

    all_right_tails = [right_tail]
    for i in range(right_pat.bodies.count):
        all_right_tails.append(right_pat.bodies.item(i))

    # ==============================================================
    #  9. DOVETAIL SOCKETS — bulk CUT  (root, assembly proxies)
    # ==============================================================
    left_tail_proxies  = [b.createForAssemblyContext(top_occ)
                          for b in all_left_tails]
    right_tail_proxies = [b.createForAssemblyContext(top_occ)
                          for b in all_right_tails]

    combine(root, left_side_proxy,  left_tail_proxies,  CUT, True, "DT_SocketL")
    combine(root, right_side_proxy, right_tail_proxies, CUT, True, "DT_SocketR")

    # ==============================================================
    # 10. JOIN DOVETAILS INTO TOP  (Top component)
    #
    #  Timeline order: CUT (step 9) uses tail bodies before
    #  JOIN (here) consumes them.
    # ==============================================================
    combine(top_c, top_body, all_left_tails,  JOIN, False, "DT_JoinL")
    combine(top_c, top_body, all_right_tails, JOIN, False, "DT_JoinR")

    # ==============================================================
    #  FIT VIEW
    # ==============================================================
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
