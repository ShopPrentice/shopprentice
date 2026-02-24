"""
Dovetailed Pencil Box with Sliding Lid
=======================================
9"L x 3"W x 2"H, 1/4" board stock, 2 tails per corner.
Through dovetail corners + grooved bottom + sliding plywood lid.

Coordinate system:
  X = length (9")  Y = width (3")  Z = height (2")

Design:
  - Side boards = tail boards, Front/Back = pin boards
  - Back board shorter (back_height) — lid slides out from back
  - Lid grooves in left, right, front
  - Bottom grooves in all 4 boards
  - Through dovetails at all 4 corners (joint height = back_height)

Root-only build (no sub-components, no assembly proxies).
Uses modelToSketchSpace probing for correct axis mapping on all planes.

Build order (grooves BEFORE dovetails):
  1. Front board
  2. Back board
  3. Left side + mirror → right side
  4. Bottom grooves — all 4 boards
  5. Lid grooves — left, right, front
  6. Dovetail tails: 1 extrude + 3 mirrors (4 template tails)
  7. Body pattern each tail along Z
  8. CUT sockets (all tails into pin boards, keepTool=True)
  9. JOIN tails into side boards (keepTool=False)
  10. Bottom panel
  11. Lid panel

Why grooves before dovetails:
  Side boards span Y=bt..box_width-bt before tails are joined.
  Groove bodies that span Y=0..box_width only CUT the interior of
  the side board (the part that exists). When tails are later joined,
  they attach ungrooved — producing clean, stopped grooves at corners.
"""
import adsk.core, adsk.fusion, math


def run(context):
    app = adsk.core.Application.get()

    # Close ALL unsaved documents first, then create fresh
    while True:
        doc = app.activeDocument
        if doc and not doc.isSaved:
            doc.close(False)
        else:
            break
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    Point3D = adsk.core.Point3D

    # ==============================================================
    #  PARAMETERS
    # ==============================================================
    for pname, expr, unit in [
        ("box_length",    "9 in",     "in"),
        ("box_width",     "3 in",     "in"),
        ("box_height",    "2 in",     "in"),
        ("board_thick",   "0.25 in",  "in"),
        ("bottom_thick",  "0.1875 in","in"),
        ("lid_thick",     "0.1875 in","in"),
        ("groove_depth",  "0.125 in", "in"),
        ("groove_up",     "0.125 in", "in"),
        ("lid_down",      "0.125 in", "in"),
        ("dt_angle",      "8 deg",    "deg"),
        ("dt_tail_w",     "0.5 in",   "in"),
        ("dt_tail_count", "2",        ""),
    ]:
        params.add(pname, adsk.core.ValueInput.createByString(expr), unit, "")

    for pname, expr, unit in [
        ("back_height",    "box_height - lid_down - lid_thick",           "in"),
        ("side_inner_len", "box_width - 2 * board_thick",                 "in"),
        ("mid_x",          "box_length / 2",                              "in"),
        ("mid_y",          "box_width / 2",                               "in"),
        ("dt_pin_w",       "back_height / dt_tail_count - dt_tail_w",     "in"),
        ("dt_pitch",       "back_height / dt_tail_count",                 "in"),
        ("dt_start_z",     "dt_pin_w / 2 + dt_tail_w / 2",               "in"),
        ("dt_narrow_w",    "dt_tail_w - 2 * board_thick * tan(dt_angle)", "in"),
        ("dt_half_pin",    "dt_pin_w / 2",                                "in"),
    ]:
        params.add(pname, adsk.core.ValueInput.createByString(expr), unit, "")

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
        """Which model axis maps to sketch-X (h) and sketch-Y (v)."""
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

    def sketch_rect_model(plane, model_origin, model_size, name="Sk"):
        """
        Parametric rectangle in model coordinates.

        model_origin: (x_expr, y_expr, z_expr)
        model_size:   {axis: expr, axis: expr}  — 2 model-axis sizes
        """
        sk = root.sketches.add(plane)
        sk.name = name
        h_axis, v_axis = probe_sketch_axes(sk)

        # Evaluate model-space corners
        ox, oy, oz = ev(model_origin[0]), ev(model_origin[1]), ev(model_origin[2])
        corner = {"x": ox, "y": oy, "z": oz}
        for a, expr in model_size.items():
            corner[a] += ev(expr)

        # Convert to sketch space
        sk_o = sk.modelToSketchSpace(Point3D.create(ox, oy, oz))
        sk_f = sk.modelToSketchSpace(
            Point3D.create(corner["x"], corner["y"], corner["z"]))

        # Draw rectangle
        rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(
            Point3D.create(sk_o.x, sk_o.y, 0),
            Point3D.create(sk_f.x, sk_f.y, 0))

        # Parametric dimensions
        d = sk.sketchDimensions
        axis_to_origin = {
            "x": model_origin[0], "y": model_origin[1], "z": model_origin[2]}
        mid_x = (sk_o.x + sk_f.x) / 2
        mid_y = (sk_o.y + sk_f.y) / 2
        # Outward directions (away from rectangle interior)
        dy = -1 if sk_f.y >= sk_o.y else 1
        dx = -1 if sk_f.x >= sk_o.x else 1

        # Width (sketch-X) → h_axis model size
        d.addDistanceDimension(
            rect[0].startSketchPoint, rect[0].endSketchPoint,
            H, Point3D.create(mid_x, sk_o.y + dy, 0)
        ).parameter.expression = model_size[h_axis]

        # Height (sketch-Y) → v_axis model size
        d.addDistanceDimension(
            rect[1].startSketchPoint, rect[1].endSketchPoint,
            V, Point3D.create(sk_f.x - dx, mid_y, 0)
        ).parameter.expression = model_size[v_axis]

        # H origin offset
        d.addDistanceDimension(
            sk.originPoint, rect[0].startSketchPoint,
            H, Point3D.create(sk_o.x / 2, sk_o.y + 2 * dy, 0)
        ).parameter.expression = axis_to_origin[h_axis]

        # V origin offset
        d.addDistanceDimension(
            sk.originPoint, rect[0].startSketchPoint,
            V, Point3D.create(sk_o.x + dx, sk_o.y / 2, 0)
        ).parameter.expression = axis_to_origin[v_axis]

        return sk, sk.profiles.item(0)

    def ext_new(prof, dist, name="Ext"):
        inp = root.features.extrudeFeatures.createInput(
            prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        inp.setDistanceExtent(False, adsk.core.ValueInput.createByString(dist))
        f = root.features.extrudeFeatures.add(inp)
        f.name = name
        return f

    def off_plane(base, expr, name="Pl"):
        inp = root.constructionPlanes.createInput()
        inp.setByOffset(base, adsk.core.ValueInput.createByString(expr))
        p = root.constructionPlanes.add(inp)
        p.name = name
        return p

    def combine(target, tool_bodies, op, keep_tool, name="Comb"):
        coll = adsk.core.ObjectCollection.create()
        if isinstance(tool_bodies, list):
            for b in tool_bodies:
                coll.add(b)
        else:
            coll.add(tool_bodies)
        inp = root.features.combineFeatures.createInput(target, coll)
        inp.operation = op
        inp.isKeepToolBodies = keep_tool
        f = root.features.combineFeatures.add(inp)
        f.name = name
        return f

    def mirror_feat(features, plane, name="Mir"):
        coll = adsk.core.ObjectCollection.create()
        for f in features:
            coll.add(f)
        inp = root.features.mirrorFeatures.createInput(coll, plane)
        m = root.features.mirrorFeatures.add(inp)
        m.name = name
        return m

    def body_pattern(body, axis, count_expr, spacing_expr, name="Pat"):
        coll = adsk.core.ObjectCollection.create()
        coll.add(body)
        inp = root.features.rectangularPatternFeatures.createInput(
            coll, axis,
            adsk.core.ValueInput.createByString(count_expr),
            adsk.core.ValueInput.createByString(spacing_expr),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        pat = root.features.rectangularPatternFeatures.add(inp)
        pat.name = name
        return pat

    def collect(template, pat):
        """Collect template body + all pattern-copy bodies."""
        bodies = [template]
        for i in range(pat.bodies.count):
            bodies.append(pat.bodies.item(i))
        return bodies

    # ==============================================================
    #  1. FRONT BOARD — XZ plane, extrude +Y by board_thick
    # ==============================================================
    _, pr = sketch_rect_model(root.xZConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "box_length", "z": "box_height"},
        "Front_Sk")
    front_ext = ext_new(pr, "board_thick", "FrontBoard")
    front_body = front_ext.bodies.item(0)
    front_body.name = "Front"

    # ==============================================================
    #  2. BACK BOARD — offset XZ plane at Y=box_width-bt
    # ==============================================================
    back_pl = off_plane(root.xZConstructionPlane,
                        "box_width - board_thick", "Back_Pl")
    _, pr = sketch_rect_model(back_pl,
        ("0 in", "box_width - board_thick", "0 in"),
        {"x": "box_length", "z": "back_height"},
        "Back_Sk")
    back_ext = ext_new(pr, "board_thick", "BackBoard")
    back_body = back_ext.bodies.item(0)
    back_body.name = "Back"

    # ==============================================================
    #  3. SIDE BOARDS — YZ plane, extrude +X by board_thick
    # ==============================================================
    _, pr = sketch_rect_model(root.yZConstructionPlane,
        ("0 in", "board_thick", "0 in"),
        {"y": "side_inner_len", "z": "box_height"},
        "LeftSide_Sk")
    left_ext = ext_new(pr, "board_thick", "LeftSide")
    left_body = left_ext.bodies.item(0)
    left_body.name = "Side_Left"

    xmid_pl = off_plane(root.yZConstructionPlane, "mid_x", "XMid_Pl")
    ymid_pl = off_plane(root.xZConstructionPlane, "mid_y", "YMid_Pl")

    mir_side = mirror_feat([left_ext], xmid_pl, "SideMirX")
    right_body = mir_side.bodies.item(0)
    right_body.name = "Side_Right"

    # ==============================================================
    #  4. BOTTOM GROOVES — all 4 boards (BEFORE dovetails)
    # ==============================================================
    bg_pl = off_plane(root.xYConstructionPlane, "groove_up", "BG_Pl")

    # Left side bottom groove
    _, pr = sketch_rect_model(bg_pl,
        ("board_thick - groove_depth", "0 in", "groove_up"),
        {"x": "groove_depth", "y": "box_width"},
        "BGL_Sk")
    bg_l = ext_new(pr, "bottom_thick", "BGL")
    combine(left_body, bg_l.bodies.item(0), CUT, False, "BGL_Cut")

    # Right side bottom groove
    _, pr = sketch_rect_model(bg_pl,
        ("box_length - board_thick", "0 in", "groove_up"),
        {"x": "groove_depth", "y": "box_width"},
        "BGR_Sk")
    bg_r = ext_new(pr, "bottom_thick", "BGR")
    combine(right_body, bg_r.bodies.item(0), CUT, False, "BGR_Cut")

    # Front board bottom groove
    _, pr = sketch_rect_model(bg_pl,
        ("0 in", "board_thick - groove_depth", "groove_up"),
        {"x": "box_length", "y": "groove_depth"},
        "BGF_Sk")
    bg_f = ext_new(pr, "bottom_thick", "BGF")
    combine(front_body, bg_f.bodies.item(0), CUT, False, "BGF_Cut")

    # Back board bottom groove
    _, pr = sketch_rect_model(bg_pl,
        ("0 in", "box_width - board_thick", "groove_up"),
        {"x": "box_length", "y": "groove_depth"},
        "BGB_Sk")
    bg_b = ext_new(pr, "bottom_thick", "BGB")
    combine(back_body, bg_b.bodies.item(0), CUT, False, "BGB_Cut")

    # ==============================================================
    #  5. LID GROOVES — left, right, front (BEFORE dovetails)
    # ==============================================================
    lg_pl = off_plane(root.xYConstructionPlane, "back_height", "LG_Pl")

    # Left side lid groove
    _, pr = sketch_rect_model(lg_pl,
        ("board_thick - groove_depth", "0 in", "back_height"),
        {"x": "groove_depth", "y": "box_width"},
        "LGL_Sk")
    lg_l = ext_new(pr, "lid_thick", "LGL")
    combine(left_body, lg_l.bodies.item(0), CUT, False, "LGL_Cut")

    # Right side lid groove
    _, pr = sketch_rect_model(lg_pl,
        ("box_length - board_thick", "0 in", "back_height"),
        {"x": "groove_depth", "y": "box_width"},
        "LGR_Sk")
    lg_r = ext_new(pr, "lid_thick", "LGR")
    combine(right_body, lg_r.bodies.item(0), CUT, False, "LGR_Cut")

    # Front lid groove
    _, pr = sketch_rect_model(lg_pl,
        ("0 in", "board_thick - groove_depth", "back_height"),
        {"x": "box_length", "y": "groove_depth"},
        "LGF_Sk")
    lg_f = ext_new(pr, "lid_thick", "LGF")
    combine(front_body, lg_f.bodies.item(0), CUT, False, "LGF_Cut")

    # ==============================================================
    #  6. DOVETAIL TAILS
    #
    #  Trapezoid on YZ plane using modelToSketchSpace probing.
    #  Wide side at Y=0 (outer face of front board).
    #  Narrow side at Y=bt (inner face of front board).
    #  FL template → mirror Y → BL, mirror X → FR, mirror BL X → BR
    #  CUT/JOIN templates, then feature-pattern the whole chain.
    # ==============================================================
    sk_dt = root.sketches.add(root.yZConstructionPlane)
    sk_dt.name = "DT_FL_Sk"
    h_axis, v_axis = probe_sketch_axes(sk_dt)

    bt    = ev("board_thick")
    hp    = ev("dt_half_pin")
    tw    = ev("dt_tail_w")
    delta = bt * math.tan(ev("dt_angle"))

    # Trapezoid in MODEL coordinates
    m_p1 = Point3D.create(0, 0, hp)               # outer-bottom
    m_p2 = Point3D.create(0, 0, hp + tw)           # outer-top
    m_p3 = Point3D.create(0, bt, hp + tw - delta)  # inner-top
    m_p4 = Point3D.create(0, bt, hp + delta)       # inner-bottom

    # Convert to sketch space
    s1 = sk_dt.modelToSketchSpace(m_p1)
    s2 = sk_dt.modelToSketchSpace(m_p2)
    s3 = sk_dt.modelToSketchSpace(m_p3)
    s4 = sk_dt.modelToSketchSpace(m_p4)

    dtl = sk_dt.sketchCurves.sketchLines
    l1 = dtl.addByTwoPoints(
        Point3D.create(s1.x, s1.y, 0), Point3D.create(s2.x, s2.y, 0))
    l2 = dtl.addByTwoPoints(l1.endSketchPoint, Point3D.create(s3.x, s3.y, 0))
    l3 = dtl.addByTwoPoints(l2.endSketchPoint, Point3D.create(s4.x, s4.y, 0))
    l4 = dtl.addByTwoPoints(l3.endSketchPoint, l1.startSketchPoint)

    # Geometric constraints: parallel sides along model Z
    if v_axis == "z":
        sk_dt.geometricConstraints.addVertical(l1)
        sk_dt.geometricConstraints.addVertical(l3)
    else:
        sk_dt.geometricConstraints.addHorizontal(l1)
        sk_dt.geometricConstraints.addHorizontal(l3)

    def orient_for(axis):
        return H if axis == h_axis else V

    d = sk_dt.sketchDimensions

    # dt_tail_w: wide side length (along Z)
    d.addDistanceDimension(l1.startSketchPoint, l1.endSketchPoint,
        orient_for("z"),
        Point3D.create(s1.x + (-1 if orient_for("z") == V else 0),
                       s1.y + (0 if orient_for("z") == V else -1), 0)
    ).parameter.expression = "dt_tail_w"

    # dt_narrow_w: narrow side length (along Z)
    d.addDistanceDimension(l3.startSketchPoint, l3.endSketchPoint,
        orient_for("z"),
        Point3D.create(s3.x + (1 if orient_for("z") == V else 0),
                       s3.y + (0 if orient_for("z") == V else 1), 0)
    ).parameter.expression = "dt_narrow_w"

    # board_thick: distance between wide and narrow sides (along Y)
    d.addDistanceDimension(l1.startSketchPoint, l3.endSketchPoint,
        orient_for("y"),
        Point3D.create((s1.x + s4.x) / 2 + (0 if orient_for("y") == V else 0),
                       (s1.y + s4.y) / 2 + (-1 if orient_for("y") == V else 0), 0)
    ).parameter.expression = "board_thick"

    # Origin to l1.start along Z = dt_pin_w / 2
    d.addDistanceDimension(sk_dt.originPoint, l1.startSketchPoint,
        orient_for("z"),
        Point3D.create(s1.x + (-1 if orient_for("z") == V else 0),
                       s1.y / 2, 0)
    ).parameter.expression = "dt_pin_w / 2"

    # Origin to l1.start along Y = 0
    d.addDistanceDimension(sk_dt.originPoint, l1.startSketchPoint,
        orient_for("y"),
        Point3D.create(s1.x / 2,
                       s1.y + (-2 if orient_for("y") == V else 0), 0)
    ).parameter.expression = "0 in"

    # Origin to l3.end along Z = dt_pin_w/2 + board_thick*tan(dt_angle)
    d.addDistanceDimension(sk_dt.originPoint, l3.endSketchPoint,
        orient_for("z"),
        Point3D.create(s4.x + (2 if orient_for("z") == V else 0),
                       s4.y / 2, 0)
    ).parameter.expression = "dt_pin_w / 2 + board_thick * tan(dt_angle)"

    ext_fl = ext_new(sk_dt.profiles.item(0), "board_thick", "DT_FL")
    fl_body = ext_fl.bodies.item(0)
    fl_body.name = "DT_FL"

    # Mirror FL → BL (across YMid)
    mir_bl = mirror_feat([ext_fl], ymid_pl, "DT_MirBL")
    bl_body = mir_bl.bodies.item(0)
    bl_body.name = "DT_BL"

    # Mirror FL → FR (across XMid)
    mir_fr = mirror_feat([ext_fl], xmid_pl, "DT_MirFR")
    fr_body = mir_fr.bodies.item(0)
    fr_body.name = "DT_FR"

    # Mirror BL → BR (across XMid)
    mir_br = mirror_feat([mir_bl], xmid_pl, "DT_MirBR")
    br_body = mir_br.bodies.item(0)
    br_body.name = "DT_BR"

    # ==============================================================
    #  7. BODY PATTERN each tail along Z
    # ==============================================================
    fl_pat = body_pattern(fl_body, root.zConstructionAxis,
                          "dt_tail_count", "dt_pitch", "DT_PatFL")
    bl_pat = body_pattern(bl_body, root.zConstructionAxis,
                          "dt_tail_count", "dt_pitch", "DT_PatBL")
    fr_pat = body_pattern(fr_body, root.zConstructionAxis,
                          "dt_tail_count", "dt_pitch", "DT_PatFR")
    br_pat = body_pattern(br_body, root.zConstructionAxis,
                          "dt_tail_count", "dt_pitch", "DT_PatBR")

    fl_all = collect(fl_body, fl_pat)
    bl_all = collect(bl_body, bl_pat)
    fr_all = collect(fr_body, fr_pat)
    br_all = collect(br_body, br_pat)

    # ==============================================================
    #  8. CUT SOCKETS + JOIN TAILS
    #
    #  CUT: tails cut sockets in pin boards (keepTool=True)
    #  JOIN: tails merge into tail boards (keepTool=False)
    # ==============================================================
    combine(front_body, fl_all + fr_all, CUT,  True,  "DT_SocketFront")
    combine(back_body,  bl_all + br_all, CUT,  True,  "DT_SocketBack")
    combine(left_body,  fl_all + bl_all, JOIN, False, "DT_JoinLeft")
    combine(right_body, fr_all + br_all, JOIN, False, "DT_JoinRight")

    # ==============================================================
    #  9. BOTTOM PANEL
    # ==============================================================
    _, pr = sketch_rect_model(bg_pl,
        ("board_thick - groove_depth",
         "board_thick - groove_depth",
         "groove_up"),
        {"x": "box_length - 2 * board_thick + 2 * groove_depth",
         "y": "box_width - 2 * board_thick + 2 * groove_depth"},
        "Bottom_Sk")
    ext_new(pr, "bottom_thick", "BottomPanel").bodies.item(0).name = "Bottom"

    # ==============================================================
    #  10. LID PANEL
    #
    #  Slides in from the back. X extends into side grooves.
    #  Y spans from back of front board to back edge (no front groove stop).
    # ==============================================================
    _, pr = sketch_rect_model(lg_pl,
        ("board_thick - groove_depth",
         "board_thick",
         "back_height"),
        {"x": "box_length - 2 * board_thick + 2 * groove_depth",
         "y": "side_inner_len"},
        "Lid_Sk")
    ext_new(pr, "lid_thick", "LidPanel").bodies.item(0).name = "Lid"

    # ==============================================================
    #  HIDE CONSTRUCTION ELEMENTS
    # ==============================================================
    for sk in root.sketches:
        sk.isVisible = False
    for cp in root.constructionPlanes:
        cp.isLightBulbOn = False
    for ca in root.constructionAxes:
        ca.isLightBulbOn = False

    # ==============================================================
    #  DIAGNOSTIC
    # ==============================================================
    names = [root.bRepBodies.item(i).name for i in range(root.bRepBodies.count)]
    print(f"Root: {len(names)} bodies -> {names}")

    # ==============================================================
    #  FIT VIEW
    # ==============================================================
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
