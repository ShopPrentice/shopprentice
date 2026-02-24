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
  6. Dovetail corners: for each corner, sketch trapezoid on YZ plane,
     extrude as CUT into pin board, extrude as JOIN into side board,
     feature pattern both extrudes along Z.
     No separate tail bodies, no Combine features.
     Fully parametric — changing dt_tail_count updates all corners.
  7. Bottom panel
  8. Lid panel

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

    def ext_op(prof, dist_expr, op, body, name="Ext"):
        """Extrude a profile as CUT or JOIN into an existing body."""
        inp = root.features.extrudeFeatures.createInput(prof, op)
        inp.setDistanceExtent(False, adsk.core.ValueInput.createByString(dist_expr))
        inp.participantBodies = [body]
        f = root.features.extrudeFeatures.add(inp)
        f.name = name
        return f

    def feat_pattern(feat, name="Pat"):
        """Feature pattern a single feature along Z by dt_tail_count / dt_pitch."""
        coll = adsk.core.ObjectCollection.create()
        coll.add(feat)
        inp = root.features.rectangularPatternFeatures.createInput(
            coll, root.zConstructionAxis,
            adsk.core.ValueInput.createByString("dt_tail_count"),
            adsk.core.ValueInput.createByString("dt_pitch"),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        p = root.features.rectangularPatternFeatures.add(inp)
        p.name = name
        return p

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
    #  6. DOVETAIL CORNERS — direct extrude CUT/JOIN + feature pattern
    #
    #  For each corner: sketch trapezoid → extrude as CUT into pin
    #  board → extrude same profile as JOIN into side board → feature
    #  pattern both extrudes along Z.
    #
    #  No separate tail bodies, no Combine features.
    #  Fully parametric: changing dt_tail_count in Change Parameters
    #  updates all corners automatically.
    # ==============================================================
    dt_right_pl = off_plane(root.yZConstructionPlane,
                            "box_length - board_thick", "DT_Right_Pl")

    bt    = ev("board_thick")
    bw    = ev("box_width")
    hp    = ev("dt_half_pin")
    tw    = ev("dt_tail_w")
    delta = bt * math.tan(ev("dt_angle"))
    rx    = ev("box_length - board_thick")

    def dt_corner(plane, mx, yw, yn, y_wide_expr, cut_body, join_body, prefix):
        """
        One dovetail corner: trapezoid sketch + CUT extrude into pin board
        + JOIN extrude into side board + feature pattern both along Z.

        mx: model X of sketch plane (cm)
        yw: model Y of wide (outer) face (cm)
        yn: model Y of narrow (inner) face (cm)
        y_wide_expr: parametric expression for origin-to-wide-face Y distance
        """
        sk = root.sketches.add(plane)
        sk.name = f"{prefix}_Sk"
        ha, va = probe_sketch_axes(sk)

        # Trapezoid in model coordinates
        m1 = Point3D.create(mx, yw, hp)
        m2 = Point3D.create(mx, yw, hp + tw)
        m3 = Point3D.create(mx, yn, hp + tw - delta)
        m4 = Point3D.create(mx, yn, hp + delta)

        # Convert to sketch space
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
        l4 = ln.addByTwoPoints(l3.endSketchPoint, l1.startSketchPoint)

        # Geometric: parallel sides along model Z
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

        # CUT pin board + JOIN side board from same profile
        ec = ext_op(prof, "board_thick", CUT, cut_body, f"{prefix}_Cut")
        ej = ext_op(prof, "board_thick", JOIN, join_body, f"{prefix}_Join")

        # Feature pattern along Z — fully parametric
        feat_pattern(ec, f"{prefix}_PatCut")
        feat_pattern(ej, f"{prefix}_PatJoin")

    # Four corners: (plane, model_x, y_wide, y_narrow, y_expr, cut_body, join_body)
    dt_corner(root.yZConstructionPlane, 0,  0,      bt,       "0 in",      front_body, left_body,  "DT_FL")
    dt_corner(root.yZConstructionPlane, 0,  bw,     bw - bt,  "box_width", back_body,  left_body,  "DT_BL")
    dt_corner(dt_right_pl,             rx,  0,      bt,       "0 in",      front_body, right_body, "DT_FR")
    dt_corner(dt_right_pl,             rx,  bw,     bw - bt,  "box_width", back_body,  right_body, "DT_BR")

    # ==============================================================
    #  7. BOTTOM PANEL
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
    #  8. LID PANEL
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
