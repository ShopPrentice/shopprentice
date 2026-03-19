"""
3-Drawer Solid Wood Dresser
============================
48"W x 20"D x 34"H, 3/4" board stock.
Through dovetail top/bottom-to-side joints, dovetailed drawer boxes,
integrated lip/groove pulls, plinth kick base with back board.

Coordinate system:
  X = width (48")   Y = depth (20")   Z = height (34")

Component-based build:
  Sides  — left + right side panels (mirror)
  Top    — top board with overhang
  Back   — plywood back panel
  Kick   — front + left + right + back plinth boards + domino joints
  Bottom — bottom board between sides at top of kick
  Drawers — each drawer built independently in a loop (fully parametric)

Build order:
  Phase 1: All boards positioned + kick dominos + kick-to-bottom dominos
           + drawer loop (boards, grooves, pulls, dovetails)
  Phase 2: Case dovetails (top/bottom-to-sides) + back rabbet
"""
import adsk.core, adsk.fusion, math, traceback


def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface
    try:
        _run(app)
    except Exception:
        ui.messageBox(traceback.format_exc())


def _run(app):
    print(">>> Script starting")
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters

    # ==============================================================
    #  PARAMETERS
    # ==============================================================
    for pname, expr, unit in [
        # Case
        ("case_w",          "48 in",    "in"),
        ("case_d",          "20 in",    "in"),
        ("case_h",          "34 in",    "in"),
        ("board_thick",     "0.75 in",  "in"),
        ("top_thick",       "0.75 in",  "in"),
        ("bot_thick",       "0.75 in",  "in"),
        ("kick_h",          "4 in",     "in"),
        ("kick_inset",      "1 in",     "in"),
        ("back_thick",      "0.25 in",  "in"),
        ("top_overhang",    "0 in",     "in"),
        # Case dovetails
        ("dt_angle",        "8 deg",    "deg"),
        ("dt_tail_w",       "1 in",     "in"),
        ("dt_tail_count",   "6",        ""),
        # Drawers
        ("n_drawers",       "3",        ""),
        ("drawer_gap",      "0.125 in", "in"),
        ("drawer_front_thick", "0.75 in", "in"),
        ("drawer_side_thick",  "0.5 in",  "in"),
        ("drawer_bottom_thick","0.25 in", "in"),
        # Drawer dovetails
        ("dd_tail_w",       "0.75 in",  "in"),
        ("dd_tail_count",   "5",        ""),
        # Pull groove
        ("pull_depth",      "0.375 in", "in"),
        ("pull_h",          "0.75 in",  "in"),
        # Bottom groove
        ("bg_depth",        "0.25 in",  "in"),
        ("bg_up",           "0.25 in",  "in"),
        # Kick dominos
        ("dm_kc_d",         "12 mm",    "in"),   # kick corner: depth per side
        ("dm_kc_h",         "1.5 in",   "in"),   # kick corner: domino long dim
        ("dm_kc_w",         "5 mm",     "in"),   # kick corner: domino short dim
        ("dm_kb_d",         "12 mm",    "in"),   # kick-to-bottom: depth per side
        ("dm_kb_h",         "1.5 in",   "in"),   # kick-to-bottom: domino long dim
        ("dm_kb_w",         "5 mm",     "in"),   # kick-to-bottom: domino short dim
        ("dm_kb_f_count",   "3",        ""),     # front kick: domino count
        ("dm_kb_s_count",   "2",        ""),     # side kick: domino count
        ("dm_kb_b_count",   "3",        ""),     # back kick: domino count
    ]:
        params.add(pname, adsk.core.ValueInput.createByString(expr), unit, "")

    for pname, expr, unit in [
        # Case derived
        ("dt_pin_w",    "case_d / dt_tail_count - dt_tail_w",          "in"),
        ("dt_pitch",    "case_d / dt_tail_count",                      "in"),
        ("dt_start_y",  "dt_pin_w / 2 + dt_tail_w / 2",               "in"),
        ("dt_narrow_w", "dt_tail_w - 2 * board_thick * tan(dt_angle)", "in"),
        # Drawer derived
        ("inner_w",     "case_w - 2 * board_thick",                    "in"),
        ("usable_h",    "case_h - kick_h - bot_thick - top_thick",      "in"),
        ("drawer_h",    "(usable_h - (n_drawers + 1) * drawer_gap) / n_drawers", "in"),
        ("drawer_w",    "inner_w - 2 * drawer_gap",                    "in"),
        ("drawer_d",    "case_d - back_thick - 2 * drawer_gap",        "in"),
        ("drawer_pitch","drawer_h + drawer_gap",                        "in"),
        # Drawer dovetail derived
        ("dd_pin_w",    "drawer_h / dd_tail_count - dd_tail_w",        "in"),
        ("dd_pitch",    "drawer_h / dd_tail_count",                    "in"),
        ("dd_narrow_f", "dd_tail_w - 2 * drawer_front_thick * tan(dt_angle)", "in"),
        ("dd_narrow_b", "dd_tail_w - 2 * drawer_side_thick * tan(dt_angle)",  "in"),
        ("dd_zbase",    "kick_h + bot_thick + drawer_gap",                     "in"),
        # Kick domino spacing
        ("dm_kb_f_sp", "(case_w - 2 * kick_inset - 2 * board_thick) / (dm_kb_f_count + 1)",   "in"),
        ("dm_kb_s_sp", "(case_d - kick_inset - 2 * board_thick) / (dm_kb_s_count + 1)",     "in"),
        ("dm_kb_b_sp", "(case_w - 2 * kick_inset - 2 * board_thick) / (dm_kb_b_count + 1)", "in"),
    ]:
        params.add(pname, adsk.core.ValueInput.createByString(expr), unit, "")
    print(">>> Parameters done")

    # ==============================================================
    #  HELPERS
    # ==============================================================
    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
    CUT  = adsk.fusion.FeatureOperations.CutFeatureOperation
    P = adsk.core.Point3D.create

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
            H, adsk.core.Point3D.create(x0 + w / 2, y0 - 1, 0)
        ).parameter.expression = we
        d.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
            V, adsk.core.Point3D.create(x0 + w + 1, y0 + h / 2, 0)
        ).parameter.expression = he
        d.addDistanceDimension(sk.originPoint, rect[0].startSketchPoint,
            H, adsk.core.Point3D.create(x0 / 2, y0 - 2, 0)
        ).parameter.expression = x0e
        d.addDistanceDimension(sk.originPoint, rect[0].startSketchPoint,
            V, adsk.core.Point3D.create(x0 - 1, y0 / 2, 0)
        ).parameter.expression = y0e
        return sk, sk.profiles.item(0)

    def probe_sketch_axes(sk):
        o  = sk.modelToSketchSpace(adsk.core.Point3D.create(0, 0, 0))
        ux = sk.modelToSketchSpace(adsk.core.Point3D.create(1, 0, 0))
        uy = sk.modelToSketchSpace(adsk.core.Point3D.create(0, 1, 0))
        uz = sk.modelToSketchSpace(adsk.core.Point3D.create(0, 0, 1))
        deltas = {
            "x": (ux.x - o.x, ux.y - o.y),
            "y": (uy.x - o.x, uy.y - o.y),
            "z": (uz.x - o.x, uz.y - o.y),
        }
        h_axis = max(deltas, key=lambda a: abs(deltas[a][0]))
        v_axis = max(deltas, key=lambda a: abs(deltas[a][1]))
        return h_axis, v_axis

    def sketch_rect_model(comp, plane, model_origin, model_size, name="Sk"):
        sk = comp.sketches.add(plane)
        sk.name = name
        h_axis, v_axis = probe_sketch_axes(sk)
        ox = ev(model_origin[0])
        oy = ev(model_origin[1])
        oz = ev(model_origin[2])
        corner = {"x": ox, "y": oy, "z": oz}
        for a, expr in model_size.items():
            corner[a] += ev(expr)
        sk_o = sk.modelToSketchSpace(adsk.core.Point3D.create(ox, oy, oz))
        sk_f = sk.modelToSketchSpace(
            adsk.core.Point3D.create(corner["x"], corner["y"], corner["z"]))
        rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(
            adsk.core.Point3D.create(sk_o.x, sk_o.y, 0),
            adsk.core.Point3D.create(sk_f.x, sk_f.y, 0))
        d = sk.sketchDimensions
        axis_to_origin = {
            "x": model_origin[0], "y": model_origin[1], "z": model_origin[2]}
        mid_x = (sk_o.x + sk_f.x) / 2
        mid_y = (sk_o.y + sk_f.y) / 2
        dy = -1 if sk_f.y >= sk_o.y else 1
        dx = -1 if sk_f.x >= sk_o.x else 1
        d.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
            H, adsk.core.Point3D.create(mid_x, sk_o.y + dy, 0)
        ).parameter.expression = model_size[h_axis]
        d.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
            V, adsk.core.Point3D.create(sk_f.x - dx, mid_y, 0)
        ).parameter.expression = model_size[v_axis]
        d.addDistanceDimension(sk.originPoint, rect[0].startSketchPoint,
            H, adsk.core.Point3D.create(sk_o.x / 2, sk_o.y + 2 * dy, 0)
        ).parameter.expression = axis_to_origin[h_axis]
        d.addDistanceDimension(sk.originPoint, rect[0].startSketchPoint,
            V, adsk.core.Point3D.create(sk_o.x + dx, sk_o.y / 2, 0)
        ).parameter.expression = axis_to_origin[v_axis]
        return sk, sk.profiles.item(0)

    def ext_new(comp, prof, dist, name="Ext"):
        inp = comp.features.extrudeFeatures.createInput(
            prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        inp.setDistanceExtent(False, adsk.core.ValueInput.createByString(dist))
        f = comp.features.extrudeFeatures.add(inp)
        f.name = name
        return f

    def ext_op(comp, prof, dist_expr, op, body, name="Ext"):
        inp = comp.features.extrudeFeatures.createInput(prof, op)
        inp.setDistanceExtent(False, adsk.core.ValueInput.createByString(dist_expr))
        inp.participantBodies = [body]
        f = comp.features.extrudeFeatures.add(inp)
        f.name = name
        return f

    def ext_new_sym(comp, prof, dist, name="Ext"):
        inp = comp.features.extrudeFeatures.createInput(
            prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        inp.setSymmetricExtent(adsk.core.ValueInput.createByString(dist), False)
        f = comp.features.extrudeFeatures.add(inp)
        f.name = name
        return f

    def sketch_slot(comp, plane, cxe, cye, long_e, short_e, vertical, name="Sk"):
        """Stadium-shaped domino mortise sketch.
        cxe/cye = center in sketch space, long_e = long dim, short_e = short dim.
        vertical=True → long axis along sketch Y; False → along sketch X.
        """
        sk = comp.sketches.add(plane)
        sk.name = name
        slines = sk.sketchCurves.sketchLines
        sarcs = sk.sketchCurves.sketchArcs
        cx, cy = ev(cxe), ev(cye)
        lg, sh = ev(long_e), ev(short_e)
        r = sh / 2
        hl = (lg - sh) / 2
        if vertical:
            br = P(cx + r, cy - hl, 0)
            tr = P(cx + r, cy + hl, 0)
            tc = P(cx, cy + hl, 0)
            tl = P(cx - r, cy + hl, 0)
            bl = P(cx - r, cy - hl, 0)
            bc = P(cx, cy - hl, 0)
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
                P(cx + r + 1, cy - hl, 0)
            ).parameter.expression = short_e + " / 2"
            d.addDistanceDimension(
                arc_bot.centerSketchPoint, arc_top.centerSketchPoint,
                V, P(cx + r + 2, cy, 0)
            ).parameter.expression = long_e + " - " + short_e
            d.addDistanceDimension(
                sk.originPoint, arc_bot.centerSketchPoint,
                H, P(cx / 2, cy - hl - 1, 0)
            ).parameter.expression = cxe
            d.addDistanceDimension(
                sk.originPoint, arc_bot.centerSketchPoint,
                V, P(cx - r - 1, (cy - hl) / 2, 0)
            ).parameter.expression = cye + " - (" + long_e + " - " + short_e + ") / 2"
        else:
            bsl = P(cx - hl, cy - r, 0)
            bsr = P(cx + hl, cy - r, 0)
            rc = P(cx + hl, cy, 0)
            tsr = P(cx + hl, cy + r, 0)
            tsl = P(cx - hl, cy + r, 0)
            lc = P(cx - hl, cy, 0)
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
                P(cx - hl - 1, cy + r + 1, 0)
            ).parameter.expression = short_e + " / 2"
            d.addDistanceDimension(
                arc_left.centerSketchPoint, arc_right.centerSketchPoint,
                H, P(cx, cy - r - 2, 0)
            ).parameter.expression = long_e + " - " + short_e
            d.addDistanceDimension(
                sk.originPoint, arc_left.centerSketchPoint,
                H, P((cx - hl) / 2, cy - r - 1, 0)
            ).parameter.expression = cxe + " - (" + long_e + " - " + short_e + ") / 2"
            d.addDistanceDimension(
                sk.originPoint, arc_left.centerSketchPoint,
                V, P(cx - hl - 2, cy / 2, 0)
            ).parameter.expression = cye
        return sk, sk.profiles.item(0)

    def sketch_slot_model(comp, plane, model_center, long_model_axis,
                          long_e, short_e, name="Sk"):
        """Stadium-shaped domino sketch positioned in model coordinates.
        model_center: (x_expr, y_expr, z_expr) — parameter expressions
        long_model_axis: 'x', 'y', or 'z' — which model axis the long dim runs along
        """
        sk = comp.sketches.add(plane)
        sk.name = name
        h_axis, v_axis = probe_sketch_axes(sk)

        # Convert model center to sketch space (handles axis flips)
        mcx = ev(model_center[0])
        mcy = ev(model_center[1])
        mcz = ev(model_center[2])
        sc = sk.modelToSketchSpace(P(mcx, mcy, mcz))
        cx, cy = sc.x, sc.y

        # Is the long axis along sketch V (vertical) or sketch H?
        vertical = (long_model_axis == v_axis)

        # Model axis expressions → sketch H/V
        axis_expr = {"x": model_center[0], "y": model_center[1],
                     "z": model_center[2]}
        h_expr = axis_expr[h_axis]
        v_expr = axis_expr[v_axis]

        lg, sh = ev(long_e), ev(short_e)
        r = sh / 2
        hl = (lg - sh) / 2
        slines = sk.sketchCurves.sketchLines
        sarcs = sk.sketchCurves.sketchArcs

        # Detect axis sign: does positive model axis → positive sketch axis?
        delta_pt = {"x": P(mcx + 1, mcy, mcz),
                    "y": P(mcx, mcy + 1, mcz),
                    "z": P(mcx, mcy, mcz + 1)}
        sd_h = sk.modelToSketchSpace(delta_pt[h_axis])
        sd_v = sk.modelToSketchSpace(delta_pt[v_axis])
        h_sign = 1 if (sd_h.x - sc.x) > 0 else -1
        v_sign = 1 if (sd_v.y - sc.y) > 0 else -1

        # Sign helpers for dimension text placement
        dy = -1 if cy >= 0 else 1
        dx = -1 if cx >= 0 else 1

        # arc_bot offset = center ± half_straight depending on axis sign
        half_str = "(" + long_e + " - " + short_e + ") / 2"
        v_bot_op = " - " if v_sign > 0 else " + "
        h_left_op = " - " if h_sign > 0 else " + "

        if vertical:
            br = P(cx + r, cy - hl, 0)
            tr = P(cx + r, cy + hl, 0)
            tc = P(cx, cy + hl, 0)
            tl = P(cx - r, cy + hl, 0)
            bl = P(cx - r, cy - hl, 0)
            bc = P(cx, cy - hl, 0)
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
                P(cx + r + 1, cy - hl, 0)
            ).parameter.expression = short_e + " / 2"
            d.addDistanceDimension(
                arc_bot.centerSketchPoint, arc_top.centerSketchPoint,
                V, P(cx + r + 2, cy, 0)
            ).parameter.expression = long_e + " - " + short_e
            d.addDistanceDimension(
                sk.originPoint, arc_bot.centerSketchPoint,
                H, P(cx / 2, cy - hl + dy, 0)
            ).parameter.expression = h_expr
            d.addDistanceDimension(
                sk.originPoint, arc_bot.centerSketchPoint,
                V, P(cx + dx, (cy - hl) / 2, 0)
            ).parameter.expression = v_expr + v_bot_op + half_str
        else:
            bsl = P(cx - hl, cy - r, 0)
            bsr = P(cx + hl, cy - r, 0)
            rc = P(cx + hl, cy, 0)
            tsr = P(cx + hl, cy + r, 0)
            tsl = P(cx - hl, cy + r, 0)
            lc = P(cx - hl, cy, 0)
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
                P(cx - hl - 1, cy + r + 1, 0)
            ).parameter.expression = short_e + " / 2"
            d.addDistanceDimension(
                arc_left.centerSketchPoint, arc_right.centerSketchPoint,
                H, P(cx, cy - r + dy, 0)
            ).parameter.expression = long_e + " - " + short_e
            d.addDistanceDimension(
                sk.originPoint, arc_left.centerSketchPoint,
                H, P((cx - hl) / 2, cy - r + dy, 0)
            ).parameter.expression = h_expr + h_left_op + half_str
            d.addDistanceDimension(
                sk.originPoint, arc_left.centerSketchPoint,
                V, P(cx - hl + dx, cy / 2, 0)
            ).parameter.expression = v_expr

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

    def feat_pattern(comp, feat, axis, count_expr, spacing_expr, name="Pat"):
        coll = adsk.core.ObjectCollection.create()
        coll.add(feat)
        inp = comp.features.rectangularPatternFeatures.createInput(
            coll, axis,
            adsk.core.ValueInput.createByString(count_expr),
            adsk.core.ValueInput.createByString(spacing_expr),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        p = comp.features.rectangularPatternFeatures.add(inp)
        p.name = name
        return p

    def make_comp(root_comp, name):
        occ = root_comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        occ.component.name = name
        return occ

    # ==============================================================
    #  COMPONENTS
    # ==============================================================
    sides_occ   = make_comp(root, "Sides")
    top_occ     = make_comp(root, "Top")
    back_occ    = make_comp(root, "Back")
    kick_occ    = make_comp(root, "Kick")
    bottom_occ  = make_comp(root, "Bottom")
    drawers_occ = make_comp(root, "Drawers")

    sides_c   = sides_occ.component
    top_c     = top_occ.component
    back_c    = back_occ.component
    kick_c    = kick_occ.component
    bottom_c  = bottom_occ.component
    drawers_c = drawers_occ.component

    # ==============================================================
    #  PHASE 1: CARCASS STRUCTURE — all boards, no joinery
    # ==============================================================
    print(">>> Phase 1: Starting carcass structure")

    # ----------------------------------------------------------
    #  1. SIDE BOARDS  (Sides component)
    #     Left side: X=0..board_thick, Y=0..case_d, Z=kick_h..case_h
    #     Mirror left → right across XMid
    # ----------------------------------------------------------
    s_XMid = off_plane(sides_c, sides_c.yZConstructionPlane,
                       "case_w / 2", "XMid_Pl")

    s_pl = off_plane(sides_c, sides_c.xYConstructionPlane,
                     "kick_h", "Side_Pl")
    _, pr = sketch_rect(sides_c, s_pl,
        "0 in", "0 in", "board_thick", "case_d", "LeftSide_Sk")
    left_ext = ext_new(sides_c, pr,
        "case_h - kick_h", "LeftSide")
    left_side = left_ext.bodies.item(0)
    left_side.name = "Side_Left"

    mir_side = mirror_feat(sides_c, [left_ext], s_XMid, "Side_MirX")
    right_side = mir_side.bodies.item(0)
    right_side.name = "Side_Right"

    print(">>> Side boards done")
    # ----------------------------------------------------------
    #  2. TOP BOARD  (Top component)
    #     X=-top_overhang .. case_w+top_overhang
    #     Y=-top_overhang .. case_d
    #     Z=case_h-top_thick .. case_h
    # ----------------------------------------------------------
    t_pl = off_plane(top_c, top_c.xYConstructionPlane,
                     "case_h - top_thick", "Top_Pl")
    _, pr = sketch_rect(top_c, t_pl,
        "board_thick - top_overhang", "-top_overhang",
        "inner_w + 2 * top_overhang", "case_d + top_overhang",
        "Top_Sk")
    top_ext = ext_new(top_c, pr, "top_thick", "TopBoard")
    top_body = top_ext.bodies.item(0)
    top_body.name = "TopBoard"
    print(">>> Top board done")

    # ----------------------------------------------------------
    #  3. BACK PANEL  (Back component)
    #     X=board_thick .. case_w-board_thick
    #     Y=case_d-back_thick .. case_d
    #     Z=kick_h .. case_h-top_thick
    # ----------------------------------------------------------
    bk_pl = off_plane(back_c, back_c.xYConstructionPlane,
                      "kick_h", "Back_Pl")
    _, pr = sketch_rect(back_c, bk_pl,
        "board_thick", "case_d - back_thick",
        "inner_w", "back_thick", "Back_Sk")
    back_ext = ext_new(back_c, pr,
        "case_h - kick_h - top_thick", "BackPanel")
    back_body = back_ext.bodies.item(0)
    back_body.name = "BackPanel"
    print(">>> Back panel done")

    # ----------------------------------------------------------
    #  4. KICK  (Kick component)
    #     Front: X=kick_inset..case_w-kick_inset,
    #            Y=kick_inset..kick_inset+board_thick, Z=0..kick_h
    #     Left:  X=kick_inset..kick_inset+board_thick,
    #            Y=kick_inset+board_thick..case_d, Z=0..kick_h
    #     Mirror left → right across XMid
    # ----------------------------------------------------------
    k_XMid = off_plane(kick_c, kick_c.yZConstructionPlane,
                       "case_w / 2", "KXMid_Pl")

    _, pr = sketch_rect(kick_c, kick_c.xYConstructionPlane,
        "kick_inset", "kick_inset",
        "case_w - 2 * kick_inset", "board_thick", "KickFront_Sk")
    kick_front_ext = ext_new(kick_c, pr, "kick_h", "KickFront")
    kick_front = kick_front_ext.bodies.item(0)
    kick_front.name = "Kick_Front"

    _, pr = sketch_rect(kick_c, kick_c.xYConstructionPlane,
        "kick_inset", "kick_inset + board_thick",
        "board_thick", "case_d - kick_inset - board_thick", "KickLeft_Sk")
    kick_left_ext = ext_new(kick_c, pr, "kick_h", "KickLeft")
    kick_left = kick_left_ext.bodies.item(0)
    kick_left.name = "Kick_Left"

    mir_kick = mirror_feat(kick_c, [kick_left_ext], k_XMid, "Kick_MirX")
    kick_right = mir_kick.bodies.item(0)
    kick_right.name = "Kick_Right"

    # Kick back board
    _, pr = sketch_rect(kick_c, kick_c.xYConstructionPlane,
        "kick_inset + board_thick", "case_d - board_thick",
        "case_w - 2 * kick_inset - 2 * board_thick", "board_thick",
        "KickBack_Sk")
    kick_back_ext = ext_new(kick_c, pr, "kick_h", "KickBack")
    kick_back = kick_back_ext.bodies.item(0)
    kick_back.name = "Kick_Back"
    print(">>> Kick boards done, starting corner dominos")

    # -- Kick corner dominos (4 corners, stadium-shaped) --
    # Use sketch_slot_model: model coords + probe_sketch_axes handles axis mapping.
    # All dominos have long axis along model Z (vertical).

    # Front-left: XZ plane at Y = kick_inset + board_thick
    kc_fl_pl = off_plane(kick_c, kick_c.xZConstructionPlane,
                         "kick_inset + board_thick", "KC_FL_Pl")
    _, pr = sketch_slot_model(kick_c, kc_fl_pl,
        ("kick_inset + board_thick / 2", "kick_inset + board_thick", "kick_h / 2"),
        "z", "dm_kc_h", "dm_kc_w", "KC_FL_Sk")
    kc_fl = ext_new_sym(kick_c, pr, "dm_kc_d", "KC_FL")
    combine(kick_c, kick_front, kc_fl.bodies.item(0), CUT, True, "KC_FL_CutF")
    combine(kick_c, kick_left, kc_fl.bodies.item(0), CUT, True, "KC_FL_CutL")

    # Front-right: same XZ plane, mirrored X
    _, pr = sketch_slot_model(kick_c, kc_fl_pl,
        ("case_w - kick_inset - board_thick / 2", "kick_inset + board_thick",
         "kick_h / 2"),
        "z", "dm_kc_h", "dm_kc_w", "KC_FR_Sk")
    kc_fr = ext_new_sym(kick_c, pr, "dm_kc_d", "KC_FR")
    combine(kick_c, kick_front, kc_fr.bodies.item(0), CUT, True, "KC_FR_CutF")
    combine(kick_c, kick_right, kc_fr.bodies.item(0), CUT, True, "KC_FR_CutR")

    # Back-left: YZ plane at X = kick_inset + board_thick
    kc_bl_pl = off_plane(kick_c, kick_c.yZConstructionPlane,
                         "kick_inset + board_thick", "KC_BL_Pl")
    _, pr = sketch_slot_model(kick_c, kc_bl_pl,
        ("kick_inset + board_thick", "case_d - board_thick / 2", "kick_h / 2"),
        "z", "dm_kc_h", "dm_kc_w", "KC_BL_Sk")
    kc_bl = ext_new_sym(kick_c, pr, "dm_kc_d", "KC_BL")
    combine(kick_c, kick_left, kc_bl.bodies.item(0), CUT, True, "KC_BL_CutL")
    combine(kick_c, kick_back, kc_bl.bodies.item(0), CUT, True, "KC_BL_CutB")

    # Back-right: YZ plane at X = case_w - kick_inset - board_thick
    kc_br_pl = off_plane(kick_c, kick_c.yZConstructionPlane,
                         "case_w - kick_inset - board_thick", "KC_BR_Pl")
    _, pr = sketch_slot_model(kick_c, kc_br_pl,
        ("case_w - kick_inset - board_thick", "case_d - board_thick / 2",
         "kick_h / 2"),
        "z", "dm_kc_h", "dm_kc_w", "KC_BR_Sk")
    kc_br = ext_new_sym(kick_c, pr, "dm_kc_d", "KC_BR")
    combine(kick_c, kick_right, kc_br.bodies.item(0), CUT, True, "KC_BR_CutR")
    combine(kick_c, kick_back, kc_br.bodies.item(0), CUT, True, "KC_BR_CutB")

    print(">>> Kick corner dominos done")
    # ----------------------------------------------------------
    #  4b. BOTTOM BOARD  (Bottom component)
    #      X=board_thick..case_w-board_thick, Y=0..case_d,
    #      Z=kick_h..kick_h+bot_thick
    # ----------------------------------------------------------
    bot_pl = off_plane(bottom_c, bottom_c.xYConstructionPlane,
                       "kick_h", "Bot_Pl")
    _, pr = sketch_rect(bottom_c, bot_pl,
        "board_thick", "0 in",
        "inner_w", "case_d", "Bottom_Sk")
    bot_ext = ext_new(bottom_c, pr, "bot_thick", "BottomBoard")
    bot_body = bot_ext.bodies.item(0)
    bot_body.name = "BottomBoard"
    print(">>> Bottom board done, starting kick-to-bottom dominos")

    # -- Kick-to-bottom dominos (cross-component: Kick + Bottom) --
    kick_front_proxy = kick_front.createForAssemblyContext(kick_occ)
    kick_left_proxy  = kick_left.createForAssemblyContext(kick_occ)
    kick_right_proxy = kick_right.createForAssemblyContext(kick_occ)
    kick_back_proxy  = kick_back.createForAssemblyContext(kick_occ)
    bot_body_proxy   = bot_body.createForAssemblyContext(bottom_occ)

    kb_pl = off_plane(root, root.xYConstructionPlane, "kick_h", "KB_Pl")

    # Front kick-to-bottom: board runs along X → long dim horizontal
    # Use loop instead of body_pattern to avoid ghost bodies from CUT replay
    _kb_f_n = int(ev("dm_kb_f_count"))
    _kb_f_sp = ev("dm_kb_f_sp")
    kb_f_bodies = []
    for _i in range(_kb_f_n):
        _cx = ev("kick_inset") + ev("board_thick") + _kb_f_sp * (_i + 1)
        _, pr = sketch_slot(root, kb_pl,
            f"{_cx} cm", "kick_inset + board_thick / 2",
            "dm_kb_h", "dm_kb_w", False, f"KB_F{_i}_Sk")
        _ext = ext_new_sym(root, pr, "dm_kb_d", f"KB_F{_i}")
        _ext.bodies.item(0).name = f"KB_F{_i}"
        kb_f_bodies.append(_ext.bodies.item(0))
    combine(root, kick_front_proxy, kb_f_bodies, CUT, True, "KB_F_CutK")
    combine(root, bot_body_proxy, kb_f_bodies, CUT, True, "KB_F_CutB")

    # Left kick-to-bottom: board runs along Y → long dim vertical
    _kb_l_n = int(ev("dm_kb_s_count"))
    _kb_l_sp = ev("dm_kb_s_sp")
    kb_l_bodies = []
    for _i in range(_kb_l_n):
        _cy = ev("kick_inset") + ev("board_thick") + _kb_l_sp * (_i + 1)
        _, pr = sketch_slot(root, kb_pl,
            "kick_inset + board_thick / 2", f"{_cy} cm",
            "dm_kb_h", "dm_kb_w", True, f"KB_L{_i}_Sk")
        _ext = ext_new_sym(root, pr, "dm_kb_d", f"KB_L{_i}")
        _ext.bodies.item(0).name = f"KB_L{_i}"
        kb_l_bodies.append(_ext.bodies.item(0))
    combine(root, kick_left_proxy, kb_l_bodies, CUT, True, "KB_L_CutK")
    combine(root, bot_body_proxy, kb_l_bodies, CUT, True, "KB_L_CutB")

    # Right kick-to-bottom: board runs along Y → long dim vertical
    _kb_r_n = int(ev("dm_kb_s_count"))
    _kb_r_sp = ev("dm_kb_s_sp")
    kb_r_bodies = []
    for _i in range(_kb_r_n):
        _cy = ev("kick_inset") + ev("board_thick") + _kb_r_sp * (_i + 1)
        _, pr = sketch_slot(root, kb_pl,
            "case_w - kick_inset - board_thick / 2", f"{_cy} cm",
            "dm_kb_h", "dm_kb_w", True, f"KB_R{_i}_Sk")
        _ext = ext_new_sym(root, pr, "dm_kb_d", f"KB_R{_i}")
        _ext.bodies.item(0).name = f"KB_R{_i}"
        kb_r_bodies.append(_ext.bodies.item(0))
    combine(root, kick_right_proxy, kb_r_bodies, CUT, True, "KB_R_CutK")
    combine(root, bot_body_proxy, kb_r_bodies, CUT, True, "KB_R_CutB")

    # Back kick-to-bottom: board runs along X → long dim horizontal
    _kb_b_n = int(ev("dm_kb_b_count"))
    _kb_b_sp = ev("dm_kb_b_sp")
    kb_b_bodies = []
    for _i in range(_kb_b_n):
        _cx = ev("kick_inset") + ev("board_thick") + _kb_b_sp * (_i + 1)
        _, pr = sketch_slot(root, kb_pl,
            f"{_cx} cm", "case_d - board_thick / 2",
            "dm_kb_h", "dm_kb_w", False, f"KB_B{_i}_Sk")
        _ext = ext_new_sym(root, pr, "dm_kb_d", f"KB_B{_i}")
        _ext.bodies.item(0).name = f"KB_B{_i}"
        kb_b_bodies.append(_ext.bodies.item(0))
    combine(root, kick_back_proxy, kb_b_bodies, CUT, True, "KB_B_CutK")
    combine(root, bot_body_proxy, kb_b_bodies, CUT, True, "KB_B_CutB")

    # Kick-to-bottom void bodies remain in root (referenced by combine features)
    print(">>> Kick-to-bottom dominos done")

    # ----------------------------------------------------------
    #  5. DRAWERS  (Drawers component)
    #     Each drawer built independently in a loop — fully parametric.
    # ----------------------------------------------------------

    d_pl = off_plane(drawers_c, drawers_c.xYConstructionPlane,
                     "kick_h + bot_thick + drawer_gap", "Dr_Pl")
    bg_pl = off_plane(drawers_c, drawers_c.xYConstructionPlane,
                      "kick_h + bot_thick + drawer_gap + bg_up", "DrBG_Pl")

    # -- Template drawer boards --
    _, pr = sketch_rect(drawers_c, d_pl,
        "board_thick + drawer_gap", "0 in",
        "drawer_w", "drawer_front_thick", "DrFront_Sk")
    dr_front = ext_new(drawers_c, pr, "drawer_h", "DrFront").bodies.item(0)
    dr_front.name = "Dr_Front"

    _, pr = sketch_rect(drawers_c, d_pl,
        "board_thick + drawer_gap", "drawer_d - drawer_side_thick",
        "drawer_w", "drawer_side_thick", "DrBack_Sk")
    dr_back = ext_new(drawers_c, pr, "drawer_h", "DrBack").bodies.item(0)
    dr_back.name = "Dr_Back"

    _, pr = sketch_rect(drawers_c, d_pl,
        "board_thick + drawer_gap", "0 in",
        "drawer_side_thick", "drawer_d", "DrLeft_Sk")
    dr_left = ext_new(drawers_c, pr, "drawer_h", "DrLeft").bodies.item(0)
    dr_left.name = "Dr_Left"

    _, pr = sketch_rect(drawers_c, d_pl,
        "board_thick + drawer_gap + drawer_w - drawer_side_thick", "0 in",
        "drawer_side_thick", "drawer_d", "DrRight_Sk")
    dr_right = ext_new(drawers_c, pr, "drawer_h", "DrRight").bodies.item(0)
    dr_right.name = "Dr_Right"

    _, pr = sketch_rect(drawers_c, bg_pl,
        "board_thick + drawer_gap + drawer_side_thick - bg_depth",
        "drawer_front_thick - bg_depth",
        "drawer_w - 2 * drawer_side_thick + 2 * bg_depth",
        "drawer_d - drawer_front_thick - drawer_side_thick + 2 * bg_depth",
        "DrBottom_Sk")
    dr_bot = ext_new(drawers_c, pr, "drawer_bottom_thick", "DrBottom").bodies.item(0)
    dr_bot.name = "Dr_Bottom"

    # -- Bottom grooves (CUT) --
    zbg = "kick_h + bot_thick + drawer_gap + bg_up"
    _, pr = sketch_rect_model(drawers_c, bg_pl,
        ("board_thick + drawer_gap", "drawer_front_thick - bg_depth", zbg),
        {"x": "drawer_w", "y": "bg_depth"}, "DrBGF_Sk")
    ext_op(drawers_c, pr, "drawer_bottom_thick", CUT, dr_front, "DrBGF")

    _, pr = sketch_rect_model(drawers_c, bg_pl,
        ("board_thick + drawer_gap", "drawer_d - drawer_side_thick", zbg),
        {"x": "drawer_w", "y": "bg_depth"}, "DrBGB_Sk")
    ext_op(drawers_c, pr, "drawer_bottom_thick", CUT, dr_back, "DrBGB")

    _, pr = sketch_rect_model(drawers_c, bg_pl,
        ("board_thick + drawer_gap + drawer_side_thick - bg_depth",
         "drawer_front_thick", zbg),
        {"x": "bg_depth", "y": "drawer_d - drawer_front_thick"}, "DrBGL_Sk")
    ext_op(drawers_c, pr, "drawer_bottom_thick", CUT, dr_left, "DrBGL")

    _, pr = sketch_rect_model(drawers_c, bg_pl,
        ("board_thick + drawer_gap + drawer_w - drawer_side_thick",
         "drawer_front_thick", zbg),
        {"x": "bg_depth", "y": "drawer_d - drawer_front_thick"}, "DrBGR_Sk")
    ext_op(drawers_c, pr, "drawer_bottom_thick", CUT, dr_right, "DrBGR")

    # -- Pull groove --
    _, pr = sketch_rect_model(drawers_c, d_pl,
        ("board_thick + drawer_gap", "-pull_depth",
         "kick_h + bot_thick + drawer_gap"),
        {"x": "drawer_w", "y": "pull_depth"}, "Pull_Sk")
    ext_op(drawers_c, pr, "pull_h", CUT, dr_front, "PullGroove")

    # -- Drawer dovetails --
    _dft = ev("drawer_front_thick")
    _dst = ev("drawer_side_thick")
    _hp  = ev("dd_pin_w") / 2
    _tw  = ev("dd_tail_w")
    _zd  = ev("dd_zbase")
    _ang = ev("dt_angle")
    _df  = _dft * math.tan(_ang)
    _db  = _dst * math.tan(_ang)
    _dd  = ev("drawer_d")

    dd_lpl = off_plane(drawers_c, drawers_c.yZConstructionPlane,
                       "board_thick + drawer_gap", "DD_L_Pl")
    dd_rpl = off_plane(drawers_c, drawers_c.yZConstructionPlane,
                       "board_thick + drawer_gap + drawer_w - drawer_side_thick",
                       "DD_R_Pl")

    def dd_corner(plane, yw, yn, delta, narrow_e, thick_e, yw_e,
                  pin_body, tail_body, dist_e, name):
        """One dovetail corner: sketch + CUT + JOIN + feat_pattern."""
        sk = drawers_c.sketches.add(plane)
        sk.name = f"{name}_Sk"
        ha, va = probe_sketch_axes(sk)
        m = sk.modelToSketchSpace
        px = plane.geometry.origin.x

        s1 = m(P(px, yw, _zd + _hp))
        s2 = m(P(px, yw, _zd + _hp + _tw))
        s3 = m(P(px, yn, _zd + _hp + _tw - delta))
        s4 = m(P(px, yn, _zd + _hp + delta))

        ln = sk.sketchCurves.sketchLines
        l1 = ln.addByTwoPoints(P(s1.x, s1.y, 0), P(s2.x, s2.y, 0))
        l2 = ln.addByTwoPoints(l1.endSketchPoint, P(s3.x, s3.y, 0))
        l3 = ln.addByTwoPoints(l2.endSketchPoint, P(s4.x, s4.y, 0))
        l4 = ln.addByTwoPoints(l3.endSketchPoint, l1.startSketchPoint)

        if va == "z":
            sk.geometricConstraints.addVertical(l1)
            sk.geometricConstraints.addVertical(l3)
        else:
            sk.geometricConstraints.addHorizontal(l1)
            sk.geometricConstraints.addHorizontal(l3)

        of = lambda a: H if a == ha else V
        d = sk.sketchDimensions
        zb = "dd_zbase + dd_pin_w / 2"

        d.addDistanceDimension(l1.startSketchPoint, l1.endSketchPoint,
            of("z"), P(s1.x - 1, (s1.y + s2.y) / 2, 0)
        ).parameter.expression = "dd_tail_w"
        d.addDistanceDimension(l3.startSketchPoint, l3.endSketchPoint,
            of("z"), P(s3.x + 1, (s3.y + s4.y) / 2, 0)
        ).parameter.expression = narrow_e
        d.addDistanceDimension(l1.startSketchPoint, l3.endSketchPoint,
            of("y"), P((s1.x + s4.x) / 2, s1.y - 1, 0)
        ).parameter.expression = thick_e
        d.addDistanceDimension(sk.originPoint, l1.startSketchPoint,
            of("z"), P(s1.x - 2, s1.y / 2, 0)
        ).parameter.expression = zb
        d.addDistanceDimension(sk.originPoint, l1.startSketchPoint,
            of("y"), P(s1.x / 2, s1.y - 2, 0)
        ).parameter.expression = yw_e
        d.addDistanceDimension(sk.originPoint, l3.endSketchPoint,
            of("z"), P(s4.x + 2, s4.y / 2, 0)
        ).parameter.expression = zb + " + " + thick_e + " * tan(dt_angle)"

        pr = sk.profiles.item(0)

        ec = ext_op(drawers_c, pr, dist_e, CUT, pin_body, f"{name}_Cut")
        ej = ext_op(drawers_c, pr, dist_e, JOIN, tail_body, f"{name}_Join")

        feat_pattern(drawers_c, ec, drawers_c.zConstructionAxis,
                     "dd_tail_count", "dd_pitch", f"{name}_PatCut")
        feat_pattern(drawers_c, ej, drawers_c.zConstructionAxis,
                     "dd_tail_count", "dd_pitch", f"{name}_PatJoin")

    print(">>>   Drawer dovetails")
    dd_corner(dd_lpl, 0, _dft, _df,
        "dd_narrow_f", "drawer_front_thick", "0 in",
        dr_front, dr_left, "drawer_side_thick", "DD_FL")
    dd_corner(dd_lpl, _dd, _dd - _dst, _db,
        "dd_narrow_b", "drawer_side_thick", "drawer_d",
        dr_back, dr_left, "drawer_side_thick", "DD_BL")
    dd_corner(dd_rpl, 0, _dft, _df,
        "dd_narrow_f", "drawer_front_thick", "0 in",
        dr_front, dr_right, "drawer_side_thick", "DD_FR")
    dd_corner(dd_rpl, _dd, _dd - _dst, _db,
        "dd_narrow_b", "drawer_side_thick", "drawer_d",
        dr_back, dr_right, "drawer_side_thick", "DD_BR")

    # -- Pattern drawers 2..n --
    n_dr = int(ev("n_drawers"))
    if n_dr > 1:
        dr_coll = adsk.core.ObjectCollection.create()
        for b in [dr_front, dr_back, dr_left, dr_right, dr_bot]:
            dr_coll.add(b)
        dr_inp = drawers_c.features.rectangularPatternFeatures.createInput(
            dr_coll, drawers_c.zConstructionAxis,
            adsk.core.ValueInput.createByString("n_drawers"),
            adsk.core.ValueInput.createByString("drawer_pitch"),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        dr_pat = drawers_c.features.rectangularPatternFeatures.add(dr_inp)
        dr_pat.name = "Dr_Pat"
    print(">>> All drawers done")

    # ==============================================================
    #  PHASE 2: CASE DOVETAILS (top/bottom to sides)
    #
    #  ext_new tail as NewBody on XY plane, feat_pattern along Y,
    #  then combine CUT into side proxy + combine JOIN into
    #  horizontal board proxy.  All operations in root.
    # ==============================================================

    print(">>> Phase 2: Starting case dovetails")
    # Assembly proxies for cross-component operations
    left_side_proxy   = left_side.createForAssemblyContext(sides_occ)
    right_side_proxy  = right_side.createForAssemblyContext(sides_occ)
    top_body_proxy    = top_body.createForAssemblyContext(top_occ)
    # bot_body_proxy already created in kick-to-bottom section

    bt    = ev("board_thick")
    hp    = ev("dt_pin_w") / 2
    tw    = ev("dt_tail_w")
    delta = bt * math.tan(ev("dt_angle"))
    cw    = ev("case_w")

    def ct_corner(plane, x_wide, x_narrow, side_proxy, horiz_proxy,
                  x_wide_e, thick_e, dist_e, name):
        """One case dovetail corner on an XY plane.
        Creates tail as NewBody, feat_patterns along Y, then
        combine CUT into side and combine JOIN into horiz board.
        """
        sk = root.sketches.add(plane)
        sk.name = f"{name}_Sk"
        ha, va = probe_sketch_axes(sk)
        of = lambda a: H if a == ha else V
        m = sk.modelToSketchSpace

        s1 = m(P(x_wide,   hp,              0))
        s2 = m(P(x_wide,   hp + tw,         0))
        s3 = m(P(x_narrow, hp + tw - delta, 0))
        s4 = m(P(x_narrow, hp + delta,      0))

        ln = sk.sketchCurves.sketchLines
        l1 = ln.addByTwoPoints(P(s1.x, s1.y, 0), P(s2.x, s2.y, 0))
        l2 = ln.addByTwoPoints(l1.endSketchPoint, P(s3.x, s3.y, 0))
        l3 = ln.addByTwoPoints(l2.endSketchPoint, P(s4.x, s4.y, 0))
        l4 = ln.addByTwoPoints(l3.endSketchPoint, l1.startSketchPoint)

        if va == "y":
            sk.geometricConstraints.addVertical(l1)
            sk.geometricConstraints.addVertical(l3)
        else:
            sk.geometricConstraints.addHorizontal(l1)
            sk.geometricConstraints.addHorizontal(l3)

        d = sk.sketchDimensions
        yb = "dt_pin_w / 2"

        d.addDistanceDimension(l1.startSketchPoint, l1.endSketchPoint,
            of("y"), P(s1.x - 1, (s1.y + s2.y) / 2, 0)
        ).parameter.expression = "dt_tail_w"
        d.addDistanceDimension(l3.startSketchPoint, l3.endSketchPoint,
            of("y"), P(s3.x + 1, (s3.y + s4.y) / 2, 0)
        ).parameter.expression = "dt_narrow_w"
        d.addDistanceDimension(l1.startSketchPoint, l3.endSketchPoint,
            of("x"), P((s1.x + s4.x) / 2, s1.y - 1, 0)
        ).parameter.expression = thick_e
        d.addDistanceDimension(sk.originPoint, l1.startSketchPoint,
            of("y"), P(s1.x - 2, s1.y / 2, 0)
        ).parameter.expression = yb
        d.addDistanceDimension(sk.originPoint, l1.startSketchPoint,
            of("x"), P(s1.x / 2, s1.y - 2, 0)
        ).parameter.expression = x_wide_e
        d.addDistanceDimension(sk.originPoint, l3.endSketchPoint,
            of("y"), P(s4.x + 2, s4.y / 2, 0)
        ).parameter.expression = yb + " + " + thick_e + " * tan(dt_angle)"

        pr = sk.profiles.item(0)

        # Tail as NewBody — no cross-component refs, safe to pattern
        tail_ext = ext_new(root, pr, dist_e, f"{name}_Tail")
        tail_body = tail_ext.bodies.item(0)
        tail_body.name = f"{name}"

        pat = feat_pattern(root, tail_ext, root.yConstructionAxis,
                           "dt_tail_count", "dt_pitch", f"{name}_Pat")

        all_tails = [tail_body]
        for i in range(pat.bodies.count):
            all_tails.append(pat.bodies.item(i))

        # Bulk CUT side, then JOIN into horizontal board
        combine(root, side_proxy, all_tails, CUT, True, f"{name}_CutSide")
        combine(root, horiz_proxy, all_tails, JOIN, False, f"{name}_JoinHz")

    # XY planes at joint interface heights
    ct_top_pl = off_plane(root, root.xYConstructionPlane,
                          "case_h - top_thick", "CT_Top_Pl")
    ct_bot_pl = off_plane(root, root.xYConstructionPlane,
                          "kick_h", "CT_Bot_Pl")

    # Top-left: tail goes UP into side overlap zone
    ct_corner(ct_top_pl, 0, bt, left_side_proxy, top_body_proxy,
              "0 in", "board_thick", "top_thick", "CT_TL")
    # Top-right
    ct_corner(ct_top_pl, cw, cw - bt, right_side_proxy, top_body_proxy,
              "case_w", "board_thick", "top_thick", "CT_TR")
    # Bottom-left: tail goes UP into side, touches bottom board for JOIN
    ct_corner(ct_bot_pl, 0, bt, left_side_proxy, bot_body_proxy,
              "0 in", "board_thick", "bot_thick", "CT_BL")
    # Bottom-right
    ct_corner(ct_bot_pl, cw, cw - bt, right_side_proxy, bot_body_proxy,
              "case_w", "board_thick", "bot_thick", "CT_BR")
    print(">>> Case dovetails done, starting rabbets")

    # ----------------------------------------------------------
    #  RABBET in sides for back panel
    #  Groove at Y=case_d-back_thick, depth=back_thick into side
    #  Runs full Z height of sides.  Sketch on YZ plane so both
    #  axes (y, z) are in-plane.
    # ----------------------------------------------------------
    # Left side rabbet — sketch on YZ plane at X=0
    _, pr = sketch_rect_model(root, root.yZConstructionPlane,
        ("0 in", "case_d - back_thick", "kick_h"),
        {"y": "back_thick", "z": "case_h - kick_h - top_thick"},
        "RabbetL_Sk")
    rab_l = ext_new(root, pr, "board_thick", "RabbetL_Tool")
    combine(root, left_side_proxy, rab_l.bodies.item(0), CUT, False, "RabbetL_Cut")

    # Right side rabbet — sketch on offset YZ plane at X=case_w-board_thick
    rab_r_pl = off_plane(root, root.yZConstructionPlane,
                         "case_w - board_thick", "RabR_Pl")
    _, pr = sketch_rect_model(root, rab_r_pl,
        ("case_w - board_thick", "case_d - back_thick", "kick_h"),
        {"y": "back_thick", "z": "case_h - kick_h - top_thick"},
        "RabbetR_Sk")
    rab_r = ext_new(root, pr, "board_thick", "RabbetR_Tool")
    combine(root, right_side_proxy, rab_r.bodies.item(0), CUT, False, "RabbetR_Cut")

    # ==============================================================
    #  HIDE CONSTRUCTION
    # ==============================================================
    for comp in [root, sides_c, top_c, back_c, kick_c, bottom_c, drawers_c]:
        for i in range(comp.sketches.count):
            comp.sketches.item(i).isVisible = False
        for i in range(comp.constructionPlanes.count):
            comp.constructionPlanes.item(i).isLightBulbOn = False

    # ==============================================================
    #  DIAGNOSTIC
    # ==============================================================
    for comp_name, comp_obj in [("Sides", sides_c), ("Top", top_c),
                                 ("Back", back_c), ("Kick", kick_c),
                                 ("Bottom", bottom_c), ("Drawers", drawers_c)]:
        names = [comp_obj.bRepBodies.item(i).name
                 for i in range(comp_obj.bRepBodies.count)]
        print(f"{comp_name}: {len(names)} bodies -> {names}")

    root_names = [root.bRepBodies.item(i).name
                  for i in range(root.bRepBodies.count)]
    print(f"Root: {len(root_names)} bodies -> {root_names}")

    # ==============================================================
    #  FIT VIEW
    # ==============================================================
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
