"""
Food Wrap Dispenser Box with Dovetails
=======================================
14"L x 4"W x 3.5"H, 1/2" board stock, 3 tails per corner.
Through dovetails + edge-rabbeted bottom + slide-in lid + dispensing slot.
Cutter groove on raised lip at top of back board.

Coordinate system:
  X = length (14")  Y = width (4")  Z = height (3.5")

Design:
  - End boards (Left/Right) = tail boards, Front/Back = pin boards
  - Left end board built with corner block; right end mirrored after groove CUTs
  - Front corners are part of end boards (above dispensing slot)
  - Lid slides in from front — no front tongue, grooves in back + both ends
  - Bottom grooves in all 4 boards (stopped front/back, through sides)
  - Through dovetails at all 4 corners (joint height = open_height)
  - Dispensing slot: CUT through front wall top (Z=open_height..box_height)
  - Back board flush at box_height; thickened inward at top holds cutter groove on top face
  - Film exits front slot, drapes over lid, cut at back cutter flush with top

Component structure:
  Root
    +-- Case    (Front, Back with cutter lip, End_Left + corner block)
    +-- Bottom  (bottom panel with edge rabbets)
    +-- Lid     (lid panel with edge rabbets, no back tongue)
    (root)      End_Right (mirror of left after groove CUTs)
    (root timeline)  panel-body groove CUTs, end mirror, dovetails, dispensing slot

Build order:
  Case component:
    1. Front board
    2. Back board (height = box_height, flush with top)
    3. Left end board + corner block (ext_op JOIN)
    4. Cutter lip JOIN to back board (inward thickening at top, within box height)
    5. Cutter groove CUT into top surface of thickened section
  Bottom component:
    6. Full board at tongue footprint
    7. Front edge rabbet CUT (stopped)
    8. Mirror front -> back rabbet
    9. Left edge rabbet CUT (through)
    10. Mirror left -> right rabbet
  Lid component:
    11. Full board (narrower — no front or back tongue, clears cutter lip)
    12. Left edge rabbet CUT (through)
    13. Mirror left -> right rabbet
  Root timeline:
    14. Bottom panel CUTs -> front, back, left case boards (3)
    15. Lid panel CUTs -> left case board only (1)
    16. Mirror left end -> right end (carries grooves)
    17. Dovetails — 4 corners (sketch + CUT + JOIN + pattern)
    18. Dispensing slot — CUT front
"""
import adsk.core, adsk.fusion, math


def run(context):
    app = adsk.core.Application.get()

    # Close existing WrapBox document (if any), then create fresh.
    for i in range(app.documents.count - 1, -1, -1):
        doc = app.documents.item(i)
        if doc.name.startswith("WrapBox"):
            doc.close(False)
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    Point3D = adsk.core.Point3D

    # ==============================================================
    #  PARAMETERS
    # ==============================================================
    for pname, expr, unit, desc in [
        ("box_length",       "14 in",    "in",  "Overall box length (X)"),
        ("box_width",        "4 in",     "in",  "Overall box width (Y)"),
        ("box_height",       "3.5 in",   "in",  "Overall box height (Z)"),
        ("board_thick",      "0.5 in",   "in",  "Case board thickness"),
        ("bottom_thick",     "0.25 in",  "in",  "Bottom panel total thickness"),
        ("lid_thick",        "0.375 in", "in",  "Lid panel total thickness"),
        ("groove_depth",     "0.25 in",  "in",  "Tongue insertion depth into groove"),
        ("groove_up",        "0.125 in", "in",  "Bottom panel rabbet offset from floor"),
        ("lid_down",         "0.2 in",   "in",  "Lid panel rabbet offset from top"),
        ("dt_angle",         "8 deg",    "deg", "Dovetail angle"),
        ("dt_tail_w",        "0.5 in",   "in",  "Dovetail tail width"),
        ("dt_tail_count",    "3",        "",    "Number of dovetail tails per corner"),
        ("cutter_size",      "0.375 in", "in",  "Cutter track groove size"),
        ("cutter_lip_h",     "0.5 in",   "in",  "Cutter lip height above box top"),
        ("cutter_lip_depth", "0.375 in", "in",  "Cutter lip inward extension depth"),
        ("film_gap",         "0.015625 in", "in", "Gap between lid and front board for film exit"),
    ]:
        params.add(pname, adsk.core.ValueInput.createByString(expr), unit, desc)

    for pname, expr, unit, desc in [
        ("bottom_tongue",  "bottom_thick - groove_up",                       "in",
         "Bottom tongue height (sits in groove)"),
        ("lid_tongue",     "lid_thick - lid_down",                           "in",
         "Lid tongue height (sits in groove)"),
        ("open_height",    "box_height - lid_thick",                         "in",
         "Height below lid (dovetail zone)"),
        ("side_inner_len", "box_width - 2 * board_thick",                    "in",
         "Inner width between end boards"),
        ("dt_pin_w",       "open_height / dt_tail_count - dt_tail_w",        "in",
         "Dovetail half-pin width"),
        ("dt_pitch",       "open_height / dt_tail_count",                    "in",
         "Dovetail pitch (tail + pin spacing)"),
        ("dt_narrow_w",    "dt_tail_w - 2 * board_thick * tan(dt_angle)",    "in",
         "Dovetail narrow face width"),
        ("dt_half_pin",    "dt_pin_w / 2",                                   "in",
         "Half of pin width"),
    ]:
        params.add(pname, adsk.core.ValueInput.createByString(expr), unit, desc)

    # ==============================================================
    #  HELPERS
    # ==============================================================
    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
    CUT  = adsk.fusion.FeatureOperations.CutFeatureOperation

    def ev(e):
        p = params.itemByName(e)
        return p.value if p else design.unitsManager.evaluateExpression(e, "cm")

    def probe_sketch_axes(sk):
        o  = sk.modelToSketchSpace(Point3D.create(0, 0, 0))
        ux = sk.modelToSketchSpace(Point3D.create(1, 0, 0))
        uy = sk.modelToSketchSpace(Point3D.create(0, 1, 0))
        uz = sk.modelToSketchSpace(Point3D.create(0, 0, 1))
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
        ox, oy, oz = ev(model_origin[0]), ev(model_origin[1]), ev(model_origin[2])
        corner = {"x": ox, "y": oy, "z": oz}
        for a, expr in model_size.items():
            corner[a] += ev(expr)
        sk_o = sk.modelToSketchSpace(Point3D.create(ox, oy, oz))
        sk_f = sk.modelToSketchSpace(
            Point3D.create(corner["x"], corner["y"], corner["z"]))
        rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(
            Point3D.create(sk_o.x, sk_o.y, 0),
            Point3D.create(sk_f.x, sk_f.y, 0))
        d = sk.sketchDimensions
        axis_to_origin = {
            "x": model_origin[0], "y": model_origin[1], "z": model_origin[2]}
        mid_x = (sk_o.x + sk_f.x) / 2
        mid_y = (sk_o.y + sk_f.y) / 2
        dy = -1 if sk_f.y >= sk_o.y else 1
        dx = -1 if sk_f.x >= sk_o.x else 1
        d.addDistanceDimension(
            rect[0].startSketchPoint, rect[0].endSketchPoint,
            H, Point3D.create(mid_x, sk_o.y + dy, 0)
        ).parameter.expression = model_size[h_axis]
        d.addDistanceDimension(
            rect[1].startSketchPoint, rect[1].endSketchPoint,
            V, Point3D.create(sk_f.x - dx, mid_y, 0)
        ).parameter.expression = model_size[v_axis]
        d.addDistanceDimension(
            sk.originPoint, rect[0].startSketchPoint,
            H, Point3D.create(sk_o.x / 2, sk_o.y + 2 * dy, 0)
        ).parameter.expression = axis_to_origin[h_axis]
        d.addDistanceDimension(
            sk.originPoint, rect[0].startSketchPoint,
            V, Point3D.create(sk_o.x + dx, sk_o.y / 2, 0)
        ).parameter.expression = axis_to_origin[v_axis]
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

    def ext_op(comp, prof, dist_expr, op, body, name="Ext"):
        inp = comp.features.extrudeFeatures.createInput(prof, op)
        inp.setDistanceExtent(False, adsk.core.ValueInput.createByString(dist_expr))
        inp.participantBodies = [body]
        f = comp.features.extrudeFeatures.add(inp)
        f.name = name
        return f

    def mirror_body(comp, body, plane, name="Mirror"):
        coll = adsk.core.ObjectCollection.create()
        coll.add(body)
        inp = comp.features.mirrorFeatures.createInput(coll, plane)
        m = comp.features.mirrorFeatures.add(inp)
        m.name = name
        return m

    def mirror_feats(comp, features, plane, name="Mirror"):
        coll = adsk.core.ObjectCollection.create()
        for f in features:
            coll.add(f)
        inp = comp.features.mirrorFeatures.createInput(coll, plane)
        m = comp.features.mirrorFeatures.add(inp)
        m.name = name
        return m

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

    def make_comp(name):
        occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        occ.component.name = name
        return occ

    # ==============================================================
    #  COMPONENTS
    # ==============================================================
    case_occ = make_comp("Case")
    bot_occ  = make_comp("Bottom")
    lid_occ  = make_comp("Lid")

    case_c = case_occ.component
    bot_c  = bot_occ.component
    lid_c  = lid_occ.component

    # ==============================================================
    #  CASE COMPONENT
    # ==============================================================

    # 1. FRONT BOARD
    _, pr = sketch_rect_model(case_c, case_c.xZConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "box_length", "z": "box_height"},
        "Front_Sk")
    front_ext = ext_new(case_c, pr, "board_thick", "FrontBoard")
    front_body = front_ext.bodies.item(0)
    front_body.name = "Front"

    # 2. BACK BOARD — flush at box_height (thickened section added later)
    back_pl = off_plane(case_c, case_c.xZConstructionPlane,
                        "box_width - board_thick", "Back_Pl")
    _, pr = sketch_rect_model(case_c, back_pl,
        ("0 in", "box_width - board_thick", "0 in"),
        {"x": "box_length", "z": "box_height"},
        "Back_Sk")
    back_ext = ext_new(case_c, pr, "board_thick", "BackBoard")
    back_body = back_ext.bodies.item(0)
    back_body.name = "Back"

    # 3. LEFT END BOARD + CORNER BLOCK
    _, pr = sketch_rect_model(case_c, case_c.yZConstructionPlane,
        ("0 in", "board_thick", "0 in"),
        {"y": "side_inner_len", "z": "box_height"},
        "LeftEnd_Sk")
    left_ext = ext_new(case_c, pr, "board_thick", "LeftEnd")
    left_body = left_ext.bodies.item(0)
    left_body.name = "End_Left"

    # Corner block JOINed directly — fills lid-groove corner area
    lg_pl = off_plane(case_c, case_c.xYConstructionPlane, "open_height", "LG_Pl")
    _, pr = sketch_rect_model(case_c, lg_pl,
        ("0 in", "0 in", "open_height"),
        {"x": "board_thick", "y": "board_thick"},
        "CornerL_Sk")
    ext_op(case_c, pr, "lid_thick", JOIN, left_body, "CornerL_Join")

    # 4. CUTTER LIP — inward thickening at top of back board (within box height)
    lip_pl = off_plane(case_c, case_c.xYConstructionPlane,
                       "box_height - cutter_lip_h", "CutterLip_Pl")
    _, pr = sketch_rect_model(case_c, lip_pl,
        ("board_thick", "box_width - board_thick - cutter_lip_depth",
         "box_height - cutter_lip_h"),
        {"x": "box_length - 2 * board_thick", "y": "cutter_lip_depth"},
        "CutterLip_Sk")
    ext_op(case_c, pr, "cutter_lip_h", JOIN, back_body, "CutterLip_Join")

    # 5. CUTTER GROOVE — CUT into top surface of thickened section (stopped at end boards)
    cutter_groove_pl = off_plane(case_c, case_c.xYConstructionPlane,
                                 "box_height - cutter_size", "CutterGroove_Pl")
    _, pr = sketch_rect_model(case_c, cutter_groove_pl,
        ("board_thick",
         "box_width - board_thick",
         "box_height - cutter_size"),
        {"x": "box_length - 2 * board_thick", "y": "cutter_size"},
        "CutterGroove_Sk")
    ext_op(case_c, pr, "cutter_size", CUT, back_body, "CutterGroove")

    # NO end mirror here — deferred to root after groove CUTs

    # ==============================================================
    #  BOTTOM COMPONENT — edge rabbets
    # ==============================================================

    # 6. FULL BOARD at tongue footprint
    _, pr = sketch_rect_model(bot_c, bot_c.xYConstructionPlane,
        ("board_thick - groove_depth",
         "board_thick - groove_depth",
         "0 in"),
        {"x": "box_length - 2 * board_thick + 2 * groove_depth",
         "y": "box_width - 2 * board_thick + 2 * groove_depth"},
        "Bottom_Sk")
    bot_ext = ext_new(bot_c, pr, "bottom_thick", "Bottom")
    bot_body = bot_ext.bodies.item(0)
    bot_body.name = "Bottom"

    # 7. FRONT EDGE RABBET (stopped: X = board_thick to box_length - board_thick)
    _, pr = sketch_rect_model(bot_c, bot_c.xYConstructionPlane,
        ("board_thick", "board_thick - groove_depth", "0 in"),
        {"x": "box_length - 2 * board_thick",
         "y": "groove_depth"},
        "BotRab_F_Sk")
    rab_f = ext_op(bot_c, pr, "groove_up", CUT, bot_body, "BotRab_F")

    # 8. MIRROR front -> back across Y midplane
    y_mid_pl = off_plane(bot_c, bot_c.xZConstructionPlane,
                         "box_width / 2", "YMid_Pl")
    mirror_feats(bot_c, [rab_f], y_mid_pl, "BotRab_MirrorY")

    # 9. LEFT EDGE RABBET (through: full Y extent)
    _, pr = sketch_rect_model(bot_c, bot_c.xYConstructionPlane,
        ("board_thick - groove_depth", "0 in", "0 in"),
        {"x": "groove_depth",
         "y": "box_width"},
        "BotRab_L_Sk")
    rab_l = ext_op(bot_c, pr, "groove_up", CUT, bot_body, "BotRab_L")

    # 10. MIRROR left -> right across X midplane
    bot_x_mid = off_plane(bot_c, bot_c.yZConstructionPlane,
                          "box_length / 2", "XMid_Pl")
    mirror_feats(bot_c, [rab_l], bot_x_mid, "BotRab_MirrorX")

    # ==============================================================
    #  LID COMPONENT — edge rabbets (no front tongue, back tongue restored)
    # ==============================================================

    # Construction planes
    lid_base_pl = off_plane(lid_c, lid_c.xYConstructionPlane,
                            "open_height", "LidBase_Pl")
    lid_rab_pl = off_plane(lid_c, lid_c.xYConstructionPlane,
                           "box_height - lid_down", "LidRab_Pl")

    # 11. FULL BOARD (no front tongue, back tongue into thickened lip)
    _, pr = sketch_rect_model(lid_c, lid_base_pl,
        ("board_thick - groove_depth",
         "0 in",
         "open_height"),
        {"x": "box_length - 2 * board_thick + 2 * groove_depth",
         "y": "box_width - board_thick - cutter_lip_depth + groove_depth"},
        "Lid_Sk")
    lid_ext = ext_new(lid_c, pr, "lid_thick", "Lid")
    lid_body = lid_ext.bodies.item(0)
    lid_body.name = "Lid"

    # 12. BACK EDGE RABBET (stopped, tongue into lip inner face)
    _, pr = sketch_rect_model(lid_c, lid_rab_pl,
        ("board_thick",
         "box_width - board_thick - cutter_lip_depth",
         "box_height - lid_down"),
        {"x": "box_length - 2 * board_thick",
         "y": "groove_depth"},
        "LidRab_B_Sk")
    ext_op(lid_c, pr, "lid_down", CUT, lid_body, "LidRab_B")

    # 13. LEFT EDGE RABBET (through: full Y extent)
    _, pr = sketch_rect_model(lid_c, lid_rab_pl,
        ("board_thick - groove_depth", "0 in", "box_height - lid_down"),
        {"x": "groove_depth",
         "y": "box_width"},
        "LidRab_L_Sk")
    lid_rab_l = ext_op(lid_c, pr, "lid_down", CUT, lid_body, "LidRab_L")

    # 14. MIRROR left -> right across X midplane
    lid_x_mid = off_plane(lid_c, lid_c.yZConstructionPlane,
                          "box_length / 2", "XMid_Pl")
    mirror_feats(lid_c, [lid_rab_l], lid_x_mid, "LidRab_MirrorX")

    # ==============================================================
    #  ROOT TIMELINE — cross-component operations
    # ==============================================================

    # Construction planes (root needs planes — proxy faces can't host sketches)
    x_mid_pl = off_plane(root, root.yZConstructionPlane,
                         "box_length / 2", "XMid_Pl")
    root_lg_pl = off_plane(root, root.xYConstructionPlane,
                           "open_height", "LG_Pl")
    right_pl = off_plane(root, root.yZConstructionPlane,
                         "box_length - board_thick", "Right_Pl")

    # Assembly proxies
    front_proxy = front_body.createForAssemblyContext(case_occ)
    back_proxy  = back_body.createForAssemblyContext(case_occ)
    left_proxy  = left_body.createForAssemblyContext(case_occ)
    bot_proxy   = bot_body.createForAssemblyContext(bot_occ)
    lid_proxy   = lid_body.createForAssemblyContext(lid_occ)

    # ----------------------------------------------------------
    #  14. BOTTOM PANEL GROOVE CUTs — left only (right from mirror)
    # ----------------------------------------------------------
    combine(root, front_proxy, bot_proxy, CUT, True, "BotGroove_Front")
    combine(root, back_proxy,  bot_proxy, CUT, True, "BotGroove_Back")
    combine(root, left_proxy,  bot_proxy, CUT, True, "BotGroove_Left")

    # ----------------------------------------------------------
    #  15. LID PANEL GROOVE CUTs — back + left (right from mirror)
    # ----------------------------------------------------------
    combine(root, back_proxy,  lid_proxy, CUT, True, "LidGroove_Back")
    combine(root, left_proxy,  lid_proxy, CUT, True, "LidGroove_Left")

    # ----------------------------------------------------------
    #  16. MIRROR LEFT END -> RIGHT END (carries grooves)
    # ----------------------------------------------------------
    end_mirror = mirror_body(root, left_proxy, x_mid_pl, "EndRight_Mirror")
    right_body = end_mirror.bodies.item(0)
    right_body.name = "End_Right"

    # ----------------------------------------------------------
    #  17. DOVETAIL CORNERS
    # ----------------------------------------------------------
    bt    = ev("board_thick")
    bw    = ev("box_width")
    hp    = ev("dt_half_pin")
    tw    = ev("dt_tail_w")
    delta = bt * math.tan(ev("dt_angle"))
    rx    = ev("box_length - board_thick")

    def dt_corner(plane, mx, yw, yn, y_wide_expr, cut_body, join_body, prefix):
        sk = root.sketches.add(plane)
        sk.name = f"{prefix}_Sk"
        ha, va = probe_sketch_axes(sk)

        m1 = Point3D.create(mx, yw, hp)
        m2 = Point3D.create(mx, yw, hp + tw)
        m3 = Point3D.create(mx, yn, hp + tw - delta)
        m4 = Point3D.create(mx, yn, hp + delta)

        s1 = sk.modelToSketchSpace(m1)
        s2 = sk.modelToSketchSpace(m2)
        s3 = sk.modelToSketchSpace(m3)
        s4 = sk.modelToSketchSpace(m4)

        ln = sk.sketchCurves.sketchLines
        l1 = ln.addByTwoPoints(Point3D.create(s1.x, s1.y, 0),
                               Point3D.create(s2.x, s2.y, 0))
        l2 = ln.addByTwoPoints(l1.endSketchPoint,
                               Point3D.create(s3.x, s3.y, 0))
        l3 = ln.addByTwoPoints(l2.endSketchPoint,
                               Point3D.create(s4.x, s4.y, 0))
        ln.addByTwoPoints(l3.endSketchPoint, l1.startSketchPoint)

        if va == "z":
            sk.geometricConstraints.addVertical(l1)
            sk.geometricConstraints.addVertical(l3)
        else:
            sk.geometricConstraints.addHorizontal(l1)
            sk.geometricConstraints.addHorizontal(l3)

        of = lambda a: H if a == ha else V
        d = sk.sketchDimensions

        d.addDistanceDimension(l1.startSketchPoint, l1.endSketchPoint,
            of("z"),
            Point3D.create(s1.x + (-1 if of("z") == V else 0),
                           s1.y + (0 if of("z") == V else -1), 0)
        ).parameter.expression = "dt_tail_w"

        d.addDistanceDimension(l3.startSketchPoint, l3.endSketchPoint,
            of("z"),
            Point3D.create(s3.x + (1 if of("z") == V else 0),
                           s3.y + (0 if of("z") == V else 1), 0)
        ).parameter.expression = "dt_narrow_w"

        d.addDistanceDimension(l1.startSketchPoint, l3.endSketchPoint,
            of("y"),
            Point3D.create((s1.x + s4.x) / 2,
                           (s1.y + s4.y) / 2 + (-1 if of("y") == V else 0), 0)
        ).parameter.expression = "board_thick"

        d.addDistanceDimension(sk.originPoint, l1.startSketchPoint,
            of("z"),
            Point3D.create(s1.x + (-1 if of("z") == V else 0),
                           s1.y / 2, 0)
        ).parameter.expression = "dt_pin_w / 2"

        d.addDistanceDimension(sk.originPoint, l1.startSketchPoint,
            of("y"),
            Point3D.create(s1.x / 2,
                           s1.y + (-2 if of("y") == V else 0), 0)
        ).parameter.expression = y_wide_expr

        d.addDistanceDimension(sk.originPoint, l3.endSketchPoint,
            of("z"),
            Point3D.create(s4.x + (2 if of("z") == V else 0),
                           s4.y / 2, 0)
        ).parameter.expression = "dt_pin_w / 2 + board_thick * tan(dt_angle)"

        prof = sk.profiles.item(0)

        # Tail as NewBody — safe to pattern (no cross-component refs)
        tail_ext = ext_new(root, prof, "board_thick", f"{prefix}_Tail")
        tail_body = tail_ext.bodies.item(0)
        tail_body.name = prefix

        # Pattern along Z
        coll = adsk.core.ObjectCollection.create()
        coll.add(tail_ext)
        inp = root.features.rectangularPatternFeatures.createInput(
            coll, root.zConstructionAxis,
            adsk.core.ValueInput.createByString("dt_tail_count"),
            adsk.core.ValueInput.createByString("dt_pitch"),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        pat = root.features.rectangularPatternFeatures.add(inp)
        pat.name = f"{prefix}_Pat"

        # Collect all tail bodies (template + pattern copies)
        all_tails = [tail_body]
        for i in range(pat.bodies.count):
            all_tails.append(pat.bodies.item(i))

        # Bulk CUT into pin board, then JOIN into tail board
        combine(root, cut_body, all_tails, CUT, True, f"{prefix}_Cut")
        combine(root, join_body, all_tails, JOIN, False, f"{prefix}_Join")

    dt_corner(root.yZConstructionPlane, 0,  0,      bt,
              "0 in",      front_proxy, left_proxy,  "DT_FL")
    dt_corner(root.yZConstructionPlane, 0,  bw,     bw - bt,
              "box_width", back_proxy,  left_proxy,  "DT_BL")
    dt_corner(right_pl,                rx,  0,      bt,
              "0 in",      front_proxy, right_body, "DT_FR")
    dt_corner(right_pl,                rx,  bw,     bw - bt,
              "box_width", back_proxy,  right_body, "DT_BR")

    # ----------------------------------------------------------
    #  18. DISPENSING SLOT (full length) + FILM GAP (stopped at sides)
    # ----------------------------------------------------------
    # Full-length slot removes front board above open_height
    _, pr = sketch_rect_model(root, root_lg_pl,
        ("0 in", "0 in", "open_height"),
        {"x": "box_length", "y": "board_thick"},
        "Slot_Sk")
    ext_op(root, pr, "box_height - open_height", CUT, front_proxy, "SlotCut")

    # Stopped film gap — 1/64" below lid, only between side boards
    gap_pl = off_plane(root, root.xYConstructionPlane,
                       "open_height - film_gap", "FilmGap_Pl")
    _, pr = sketch_rect_model(root, gap_pl,
        ("board_thick", "0 in", "open_height - film_gap"),
        {"x": "box_length - 2 * board_thick", "y": "board_thick"},
        "FilmGap_Sk")
    ext_op(root, pr, "film_gap", CUT, front_proxy, "FilmGapCut")

    # ==============================================================
    #  HIDE CONSTRUCTION ELEMENTS
    # ==============================================================
    for comp in [root, case_c, bot_c, lid_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False
        for ca in comp.constructionAxes:
            ca.isLightBulbOn = False

    # ==============================================================
    #  DIAGNOSTIC
    # ==============================================================
    all_bodies = []
    body_names = []

    # Root bodies (End_Right from mirror)
    for i in range(root.bRepBodies.count):
        body = root.bRepBodies.item(i)
        all_bodies.append(body)
        body_names.append(f"Root/{body.name}")

    # Component bodies
    for i in range(root.occurrences.count):
        occ = root.occurrences.item(i)
        comp = occ.component
        for j in range(comp.bRepBodies.count):
            body = comp.bRepBodies.item(j)
            proxy = body.createForAssemblyContext(occ)
            all_bodies.append(proxy)
            body_names.append(f"{comp.name}/{body.name}")
    print(f"Components: {root.occurrences.count}, Bodies: {len(all_bodies)} -> {body_names}")

    # Interference check
    tbm = adsk.fusion.TemporaryBRepManager.get()
    overlaps = []
    for i in range(len(all_bodies)):
        for j in range(i + 1, len(all_bodies)):
            b1, b2 = all_bodies[i], all_bodies[j]
            bb1, bb2 = b1.boundingBox, b2.boundingBox
            if (bb1.minPoint.x < bb2.maxPoint.x and bb1.maxPoint.x > bb2.minPoint.x and
                bb1.minPoint.y < bb2.maxPoint.y and bb1.maxPoint.y > bb2.minPoint.y and
                bb1.minPoint.z < bb2.maxPoint.z and bb1.maxPoint.z > bb2.minPoint.z):
                c1 = tbm.copy(b1)
                c2 = tbm.copy(b2)
                tbm.booleanOperation(c1, c2,
                    adsk.fusion.BooleanTypes.IntersectionBooleanType)
                if c1.volume > 0.001:
                    overlaps.append(
                        f"  '{body_names[i]}' vs '{body_names[j]}': {c1.volume:.4f} cm3")
    if overlaps:
        print("INTERFERENCES:")
        for s in overlaps:
            print(s)
    else:
        print("No interferences - clean!")

    # ==============================================================
    #  FIT VIEW
    # ==============================================================
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam

    # ==============================================================
    #  SAVE
    # ==============================================================
    doc = app.activeDocument
    if not doc.isSaved:
        project = app.data.activeProject
        doc.saveAs("WrapBox", project.rootFolder, "Food wrap dispenser box", "")
        print("Saved as: {}".format(doc.name))
