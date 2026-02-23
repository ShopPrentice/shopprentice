"""
Parametric Solid Wood Bookshelf
===============================
70"H x 30"W x 20"D, 3/4" board stock.
Structure + through M&T + through dovetails.

Build approach:
  - Features live inside their respective components (Sides, Shelves, Top, Kick)
  - Mirrors replicate tenons/tails (1 extrude → 4 via 2 mirrors)
  - Body patterns replicate shelves and dovetail tails
  - Cross-component CUT in root via assembly proxies (bulk, keepTool=True)

Coordinate system:
  X = width (30")   Y = depth (20")   Z = height (70")
"""
import adsk.core, adsk.fusion, adsk.cam, math


def run(context):
    app = adsk.core.Application.get()

    try:
        if app.activeDocument and not app.activeDocument.isSaved:
            app.activeDocument.close(False)
    except:
        pass
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
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
        ("kick_inset",    "1 in",     "in"),
        ("n_shelves",     "5",        ""),
        ("mt_tenon_w",    "2 in",     "in"),
        ("dt_angle",      "8 deg",    "deg"),
        ("dt_tail_w",     "2 in",     "in"),
        ("dt_tail_count", "8",        ""),
    ]:
        params.add(pname, adsk.core.ValueInput.createByString(expr), unit, "")

    for pname, expr, unit in [
        ("inner_width",    "total_width - 2 * board_thick",                              "in"),
        ("shelf_spacing",  "(total_height - 2 * board_thick - kick_height) / n_shelves", "in"),
        ("mt_tenon_y1",    "total_depth / 4 - mt_tenon_w / 2",                           "in"),
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

    def sketch_dovetail(comp, plane, cy, bt, tw, nw, name):
        sk = comp.sketches.add(plane)
        sk.name = name
        ln = sk.sketchCurves.sketchLines
        ln.addByTwoPoints(adsk.core.Point3D.create(0, cy - tw/2, 0),
                          adsk.core.Point3D.create(0, cy + tw/2, 0))
        ln.addByTwoPoints(adsk.core.Point3D.create(0, cy + tw/2, 0),
                          adsk.core.Point3D.create(bt, cy + nw/2, 0))
        ln.addByTwoPoints(adsk.core.Point3D.create(bt, cy + nw/2, 0),
                          adsk.core.Point3D.create(bt, cy - nw/2, 0))
        ln.addByTwoPoints(adsk.core.Point3D.create(bt, cy - nw/2, 0),
                          adsk.core.Point3D.create(0, cy - tw/2, 0))
        return sk, sk.profiles.item(0)

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

    sides = sides_occ.component
    shelves_c = shelves_occ.component
    top_c = top_occ.component
    kick_c = kick_occ.component

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
    #  One shelf + 4 tenons (mirrors) + JOIN → body pattern along Z
    # ==============================================================
    sh_YMid = off_plane(shelves_c, shelves_c.xZConstructionPlane,
                        "total_depth / 2", "YMid_Pl")
    sh_XMid = off_plane(shelves_c, shelves_c.yZConstructionPlane,
                        "total_width / 2", "XMid_Pl")
    sh_pl = off_plane(shelves_c, shelves_c.xYConstructionPlane,
                      "kick_height", "Shelf_Pl")

    # Shelf body
    _, pr = sketch_rect(shelves_c, sh_pl, "board_thick", "0 in",
                        "inner_width", "total_depth", "Shelf_Sk")
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

    # Body pattern along Z → n_shelves identical shelf bodies
    shelf_pat = body_pattern(shelves_c, sh_body, shelves_c.zConstructionAxis,
                             "n_shelves", "shelf_spacing", "ShelfPattern")

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
    #  4. KICK BOARD + TENONS  (Kick component)
    #
    #  1 kick + 1 tenon + mirror Z + mirror X + JOIN
    # ==============================================================
    k_XMid = off_plane(kick_c, kick_c.yZConstructionPlane,
                       "total_width / 2", "XMid_Pl")
    k_ZMid = off_plane(kick_c, kick_c.xYConstructionPlane,
                       "kick_height / 2", "KZMid_Pl")

    _, pr = sketch_rect(kick_c, kick_c.xYConstructionPlane,
        "board_thick", "kick_inset", "inner_width", "board_thick", "Kick_Sk")
    kick_body = ext_new(kick_c, pr, "kick_height", "KickBoard").bodies.item(0)
    kick_body.name = "KickBoard"

    kpl = off_plane(kick_c, kick_c.xYConstructionPlane,
                    "kick_height / 4 - board_thick / 2", "K_TPl")
    _, pr = sketch_rect(kick_c, kpl, "0 in", "kick_inset",
                        "board_thick", "board_thick", "K_T")
    ext_kt = ext_new(kick_c, pr, "board_thick", "K_TBody")

    mir_kz = mirror_feat(kick_c, [ext_kt], k_ZMid, "K_MirZ")
    mir_kx = mirror_feat(kick_c, [ext_kt, mir_kz], k_XMid, "K_MirX")

    kt_bodies = [ext_kt.bodies.item(0)]
    for i in range(mir_kz.bodies.count):
        kt_bodies.append(mir_kz.bodies.item(i))
    for i in range(mir_kx.bodies.count):
        kt_bodies.append(mir_kx.bodies.item(i))
    combine(kick_c, kick_body, kt_bodies, JOIN, False, "K_JoinT")

    # ==============================================================
    #  5. KICK MORTISES — bulk CUT  (root, assembly proxies)
    # ==============================================================
    kick_proxy = kick_body.createForAssemblyContext(kick_occ)
    combine(root, left_side_proxy,  kick_proxy, CUT, True, "KickMortL")
    combine(root, right_side_proxy, kick_proxy, CUT, True, "KickMortR")

    # ==============================================================
    #  6. TOP BOARD + DOVETAIL TAILS + PATTERNS  (Top component)
    #
    #  1 top board + 1 left tail + mirror X → right tail
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

    # Evaluate dovetail dims for sketch geometry
    bt = ev("board_thick")
    tw = ev("dt_tail_w")
    nw = ev("dt_narrow_w")
    start_y = ev("dt_start_y")

    dt_pl = off_plane(top_c, top_c.xYConstructionPlane,
                      "total_height - board_thick", "DT_Plane")

    # ONE left tail at dt_start_y
    _, prof = sketch_dovetail(top_c, dt_pl, start_y, bt, tw, nw, "DT_Left_Sk")
    ext_dt_l = ext_new(top_c, prof, "board_thick", "DT_Left")
    left_tail = ext_dt_l.bodies.item(0)
    left_tail.name = "DT_Left"

    # Mirror left tail across XMid → ONE right tail
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
    #  7. DOVETAIL SOCKETS — bulk CUT  (root, assembly proxies)
    # ==============================================================
    left_tail_proxies  = [b.createForAssemblyContext(top_occ)
                          for b in all_left_tails]
    right_tail_proxies = [b.createForAssemblyContext(top_occ)
                          for b in all_right_tails]

    combine(root, left_side_proxy,  left_tail_proxies,  CUT, True, "DT_SocketL")
    combine(root, right_side_proxy, right_tail_proxies, CUT, True, "DT_SocketR")

    # ==============================================================
    #  8. JOIN DOVETAILS INTO TOP  (Top component)
    #
    #  Timeline order: CUT (step 7) uses tail bodies before
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
