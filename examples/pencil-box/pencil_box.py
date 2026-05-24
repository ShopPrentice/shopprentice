"""
Dovetailed Pencil Box with Sliding Lid
=======================================
9"L x 3"W x 2.5"H, 1/4" board stock, 3 tails per corner.
Through dovetail corners + grooved bottom + sliding plywood lid.

Coordinate system:
  X = length (9")  Y = width (3")  Z = height (2")

Design:
  - Side boards = tail boards, Front/Back = pin boards
  - Right side board shorter (open_height) — lid slides out from right (+X)
  - Lid grooves in left, front, back (right side is the opening)
  - Bottom grooves in all 4 boards
  - Through dovetails at all 4 corners (joint height = open_height)
  - Flush bottom panel (Z=0) and lid panel (Z=box_height) with rabbeted edges

Component structure:
  Root
    +-- Case  (Front, Back, Side_Left, Side_Right, Bottom, Lid,
               all grooves, dovetails, rabbets)

Uses modelToSketchSpace probing for correct axis mapping on all planes.

Build order (grooves BEFORE dovetails):
  1. Front board (full height)
  2. Back board (full height)
  3. Left side board (full height, explicit extrusion)
  4. Right side board (open_height, explicit extrusion)
  5. Bottom grooves — all 4 boards
  6. Lid grooves — left, front, back
  7. Dovetail corners: for each corner, sketch trapezoid on YZ plane,
     extrude as CUT into pin board, extrude as JOIN into side board,
     feature pattern both extrudes along Z.
     No separate tail bodies, no Combine features.
     Fully parametric — changing dt_tail_count updates all corners.
  8. Bottom panel — board-first, rabbet cut (full board → rabbet → lip)
  9. Lid panel — board-first, rabbet cut, no rabbet on right side

Why grooves before dovetails:
  Side boards span Y=bt..box_width-bt before tails are joined.
  Groove bodies that span Y=0..box_width only CUT the interior of
  the side board (the part that exists). When tails are later joined,
  they attach ungrooved — producing clean, stopped grooves at corners.
"""
import adsk.core, adsk.fusion, math
from helpers import sp


def run(context):
    app = adsk.core.Application.get()
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
        ("box_height",    "2.5 in",   "in"),
        ("board_thick",   "0.25 in",  "in"),
        ("bottom_thick",  "0.3125 in","in"),
        ("lid_thick",     "0.3125 in","in"),
        ("groove_depth",  "0.125 in", "in"),
        ("groove_up",     "0.125 in", "in"),
        ("lid_down",      "0.125 in", "in"),
        ("dt_angle",      "8 deg",    "deg"),
        ("dt_tail_w",     "0.5 in",   "in"),
        ("dt_tail_count", "3",        ""),
    ]:
        params.add(pname, adsk.core.ValueInput.createByString(expr), unit, "")

    for pname, expr, unit in [
        ("bottom_tongue",  "bottom_thick - groove_up",                       "in"),
        ("lid_tongue",     "lid_thick - lid_down",                           "in"),
        ("open_height",    "box_height - lid_thick",                         "in"),
        ("side_inner_len", "box_width - 2 * board_thick",                    "in"),
        ("lid_down_z",     "box_height - lid_down",                          "in"),
        ("dt_pin_w",       "open_height / dt_tail_count - dt_tail_w",        "in"),
        ("dt_pitch",       "open_height / dt_tail_count",                    "in"),
        ("dt_start_z",     "dt_pin_w / 2 + dt_tail_w / 2",                  "in"),
        ("dt_narrow_w",    "dt_tail_w - 2 * board_thick * tan(dt_angle)",    "in"),
        ("dt_half_pin",    "dt_pin_w / 2",                                   "in"),
    ]:
        params.add(pname, adsk.core.ValueInput.createByString(expr), unit, "")

    # ==============================================================
    #  COMPONENT
    # ==============================================================
    case_occ = sp.make_comp(root, "Case")
    case_c = case_occ.component

    # ==============================================================
    #  BODY LOOKUP
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

    def sketch_rect_model(comp, plane, model_origin, model_size, name="Sk"):
        """
        Parametric rectangle in model coordinates.

        model_origin: (x_expr, y_expr, z_expr)
        model_size:   {axis: expr, axis: expr}  — 2 model-axis sizes
        """
        sk = comp.sketches.add(plane)
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

    def ext_op(comp, prof, dist_expr, op, body, name="Ext"):
        """Extrude a profile as CUT or JOIN into an existing body."""
        inp = comp.features.extrudeFeatures.createInput(prof, op)
        inp.setDistanceExtent(False, adsk.core.ValueInput.createByString(dist_expr))
        inp.participantBodies = [body]
        f = comp.features.extrudeFeatures.add(inp)
        f.name = name
        return f

    def feat_pattern(comp, feat, name="Pat"):
        """Feature pattern a single feature along Z by dt_tail_count / dt_pitch."""
        coll = adsk.core.ObjectCollection.create()
        coll.add(feat)
        inp = comp.features.rectangularPatternFeatures.createInput(
            coll, comp.zConstructionAxis,
            adsk.core.ValueInput.createByString("dt_tail_count"),
            adsk.core.ValueInput.createByString("dt_pitch"),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        p = comp.features.rectangularPatternFeatures.add(inp)
        p.name = name
        return p

    # ==============================================================
    #  1. FRONT BOARD — XZ plane, extrude +Y by board_thick
    # ==============================================================
    _, pr = sketch_rect_model(case_c, case_c.xZConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "box_length", "z": "box_height"},
        "Front_Sk")
    front_ext = ext_new(case_c, pr, "board_thick", "FrontBoard")
    front_body = front_ext.bodies.item(0)
    front_body.name = "Front"

    # ==============================================================
    #  2. BACK BOARD — offset XZ plane at Y=box_width-bt, full height
    # ==============================================================
    ref_front = find_body("Front")
    ref_front_bb = ref_front.boundingBox
    back_pl = off_plane(case_c, case_c.xZConstructionPlane,
                        "box_width - board_thick", "Back_Pl")
    _, pr = sketch_rect_model(case_c, back_pl,
        ("0 in", "box_width - board_thick", "0 in"),
        {"x": "box_length", "z": "box_height"},
        "Back_Sk")
    back_ext = ext_new(case_c, pr, "board_thick", "BackBoard")
    back_body = back_ext.bodies.item(0)
    back_body.name = "Back"

    # ==============================================================
    #  3. LEFT SIDE BOARD — YZ plane, full height
    # ==============================================================
    # Body-relative ref: Side_Left depends on Front
    ref_body = find_body("Front")
    ref_bb = ref_body.boundingBox
    _, pr = sketch_rect_model(case_c, case_c.yZConstructionPlane,
        ("0 in", "board_thick", "0 in"),
        {"y": "side_inner_len", "z": "box_height"},
        "LeftSide_Sk")
    left_ext = ext_new(case_c, pr, "board_thick", "LeftSide")
    left_body = left_ext.bodies.item(0)
    left_body.name = "Side_Left"

    # ==============================================================
    #  4. RIGHT SIDE BOARD — offset YZ plane, open_height (shorter)
    # ==============================================================
    # Body-relative ref: Side_Right depends on Front
    ref_body = find_body("Front")
    ref_bb = ref_body.boundingBox
    right_pl = off_plane(case_c, case_c.yZConstructionPlane,
                         "box_length - board_thick", "Right_Pl")
    _, pr = sketch_rect_model(case_c, right_pl,
        ("box_length - board_thick", "board_thick", "0 in"),
        {"y": "side_inner_len", "z": "open_height"},
        "RightSide_Sk")
    right_ext = ext_new(case_c, pr, "board_thick", "RightSide")
    right_body = right_ext.bodies.item(0)
    right_body.name = "Side_Right"

    # ==============================================================
    #  5. BOTTOM GROOVES — all 4 boards (BEFORE dovetails)
    # ==============================================================
    bg_pl = off_plane(case_c, case_c.xYConstructionPlane, "groove_up", "BG_Pl")

    # Left side bottom groove
    _, pr = sketch_rect_model(case_c, bg_pl,
        ("board_thick - groove_depth", "0 in", "groove_up"),
        {"x": "groove_depth", "y": "box_width"},
        "BGL_Sk")
    bg_l = ext_new(case_c, pr, "bottom_tongue", "BGL")
    combine(case_c, left_body, bg_l.bodies.item(0), CUT, False, "BGL_Cut")

    # Right side bottom groove
    _, pr = sketch_rect_model(case_c, bg_pl,
        ("box_length - board_thick", "0 in", "groove_up"),
        {"x": "groove_depth", "y": "box_width"},
        "BGR_Sk")
    bg_r = ext_new(case_c, pr, "bottom_tongue", "BGR")
    combine(case_c, right_body, bg_r.bodies.item(0), CUT, False, "BGR_Cut")

    # Front board bottom groove (stopped both sides — hidden behind side boards)
    _, pr = sketch_rect_model(case_c, bg_pl,
        ("board_thick", "board_thick - groove_depth", "groove_up"),
        {"x": "box_length - 2 * board_thick", "y": "groove_depth"},
        "BGF_Sk")
    bg_f = ext_new(case_c, pr, "bottom_tongue", "BGF")
    combine(case_c, front_body, bg_f.bodies.item(0), CUT, False, "BGF_Cut")

    # Back board bottom groove (stopped both sides — hidden behind side boards)
    _, pr = sketch_rect_model(case_c, bg_pl,
        ("board_thick", "box_width - board_thick", "groove_up"),
        {"x": "box_length - 2 * board_thick", "y": "groove_depth"},
        "BGB_Sk")
    bg_b = ext_new(case_c, pr, "bottom_tongue", "BGB")
    combine(case_c, back_body, bg_b.bodies.item(0), CUT, False, "BGB_Cut")

    # ==============================================================
    #  6. LID GROOVES — left, front, back (BEFORE dovetails)
    #     Right side is the lid opening — no groove there.
    # ==============================================================
    lg_pl = off_plane(case_c, case_c.xYConstructionPlane, "open_height", "LG_Pl")

    # Left side lid groove
    _, pr = sketch_rect_model(case_c, lg_pl,
        ("board_thick - groove_depth", "0 in", "open_height"),
        {"x": "groove_depth", "y": "box_width"},
        "LGL_Sk")
    lg_l = ext_new(case_c, pr, "lid_tongue", "LGL")
    combine(case_c, left_body, lg_l.bodies.item(0), CUT, False, "LGL_Cut")

    # Front lid groove (stopped: starts at board_thick, open at right)
    _, pr = sketch_rect_model(case_c, lg_pl,
        ("board_thick", "board_thick - groove_depth", "open_height"),
        {"x": "box_length - board_thick", "y": "groove_depth"},
        "LGF_Sk")
    lg_f = ext_new(case_c, pr, "lid_tongue", "LGF")
    combine(case_c, front_body, lg_f.bodies.item(0), CUT, False, "LGF_Cut")

    # Back lid groove (stopped: starts at board_thick, open at right)
    _, pr = sketch_rect_model(case_c, lg_pl,
        ("board_thick", "box_width - board_thick", "open_height"),
        {"x": "box_length - board_thick", "y": "groove_depth"},
        "LGB_Sk")
    lg_b = ext_new(case_c, pr, "lid_tongue", "LGB")
    combine(case_c, back_body, lg_b.bodies.item(0), CUT, False, "LGB_Cut")

    # ==============================================================
    #  7. DOVETAIL CORNERS — direct extrude CUT/JOIN + feature pattern
    #
    #  For each corner: sketch trapezoid → extrude as CUT into pin
    #  board → extrude same profile as JOIN into side board → feature
    #  pattern both extrudes along Z.
    #
    #  No separate tail bodies, no Combine features.
    #  Fully parametric: changing dt_tail_count in Change Parameters
    #  updates all corners automatically.
    # ==============================================================
    dt_right_pl = off_plane(case_c, case_c.yZConstructionPlane,
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
        sk = case_c.sketches.add(plane)
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
        l_short = ln.addByTwoPoints(Point3D.create(s4.x, s4.y, 0),
                                    Point3D.create(s3.x, s3.y, 0))
        l_back = ln.addByTwoPoints(l_short.endSketchPoint,
                                   Point3D.create(s2.x, s2.y, 0))
        l_wide = ln.addByTwoPoints(l_back.endSketchPoint,
                                   Point3D.create(s1.x, s1.y, 0))
        l_front = ln.addByTwoPoints(l_wide.endSketchPoint,
                                    l_short.startSketchPoint)

        # Geometric: parallel sides along model Z
        if va == "z":
            sk.geometricConstraints.addVertical(l_short)
            sk.geometricConstraints.addVertical(l_wide)
        else:
            sk.geometricConstraints.addHorizontal(l_short)
            sk.geometricConstraints.addHorizontal(l_wide)

        of = lambda a: H if a == ha else V
        d = sk.sketchDimensions

        d.addDistanceDimension(l_short.startSketchPoint, l_short.endSketchPoint,
            of("z"),
            Point3D.create(s3.x + (1 if of("z") == V else 0),
                           s3.y + (0 if of("z") == V else 1), 0)
        ).parameter.expression = "dt_narrow_w"

        d.addDistanceDimension(l_short.startSketchPoint, l_wide.endSketchPoint,
            of("y"),
            Point3D.create((s1.x + s4.x) / 2,
                           (s1.y + s4.y) / 2 + (-1 if of("y") == V else 0), 0)
        ).parameter.expression = "board_thick"

        d.addDistanceDimension(sk.originPoint, l_short.startSketchPoint,
            of("z"),
            Point3D.create(s4.x + (2 if of("z") == V else 0),
                           s4.y / 2, 0)
        ).parameter.expression = "dt_pin_w / 2 + board_thick * tan(dt_angle)"

        short_y_expr = (f"{y_wide_expr} + board_thick"
                        if yn >= yw else f"{y_wide_expr} - board_thick")
        d.addDistanceDimension(sk.originPoint, l_short.startSketchPoint,
            of("y"),
            Point3D.create(s1.x / 2,
                           s1.y + (-2 if of("y") == V else 0), 0)
        ).parameter.expression = short_y_expr

        d.addAngularDimension(
            l_front, l_short,
            Point3D.create((s1.x + s4.x) / 2, (s1.y + s4.y) / 2, 0)
        ).parameter.expression = "90 deg - dt_angle"

        prof = sk.profiles.item(0)

        # CUT pin board + JOIN side board from same profile
        ec = ext_op(case_c, prof, "board_thick", CUT, cut_body, f"{prefix}_Cut")
        ej = ext_op(case_c, prof, "board_thick", JOIN, join_body, f"{prefix}_Join")

        # Feature pattern along Z — fully parametric
        feat_pattern(case_c, ec, f"{prefix}_PatCut")
        feat_pattern(case_c, ej, f"{prefix}_PatJoin")

    # Four corners: (plane, model_x, y_wide, y_narrow, y_expr, cut_body, join_body)
    dt_corner(case_c.yZConstructionPlane, 0,  0,      bt,       "0 in",      front_body, left_body,  "DT_FL")
    dt_corner(case_c.yZConstructionPlane, 0,  bw,     bw - bt,  "box_width", back_body,  left_body,  "DT_BL")
    dt_corner(dt_right_pl,               rx,  0,      bt,       "0 in",      front_body, right_body, "DT_FR")
    dt_corner(dt_right_pl,               rx,  bw,     bw - bt,  "box_width", back_body,  right_body, "DT_BR")

    # ==============================================================
    #  8. BOTTOM PANEL — board-first, rabbet cut
    #
    #  Full board at tongue footprint → rabbet CUT removes groove_up
    #  from bottom face → lip JOIN restores inner area at Z=0.
    #  Net: tongue extends into grooves, lip is flush at Z=0.
    # ==============================================================
    # Body-relative ref: Bottom depends on Front
    ref_body = find_body("Front")
    ref_bb = ref_body.boundingBox
    # Full board (NewBody): tongue footprint, Z=0, height=bottom_thick
    _, pr = sketch_rect_model(case_c, case_c.xYConstructionPlane,
        ("board_thick - groove_depth",
         "board_thick - groove_depth",
         "0 in"),
        {"x": "box_length - 2 * board_thick + 2 * groove_depth",
         "y": "box_width - 2 * board_thick + 2 * groove_depth"},
        "Bottom_Sk")
    bot_ext = ext_new(case_c, pr, "bottom_thick", "Bottom")
    bot_body = bot_ext.bodies.item(0)
    bot_body.name = "Bottom"

    # Rabbet CUT: removes groove_up from bottom face (entire tongue footprint)
    _, pr = sketch_rect_model(case_c, case_c.xYConstructionPlane,
        ("board_thick - groove_depth",
         "board_thick - groove_depth",
         "0 in"),
        {"x": "box_length - 2 * board_thick + 2 * groove_depth",
         "y": "box_width - 2 * board_thick + 2 * groove_depth"},
        "BottomRabbet_Sk")
    ext_op(case_c, pr, "groove_up", CUT, bot_body, "BottomRabbet")

    # Lip JOIN: restores inner area at Z=0
    _, pr = sketch_rect_model(case_c, case_c.xYConstructionPlane,
        ("board_thick", "board_thick", "0 in"),
        {"x": "box_length - 2 * board_thick",
         "y": "box_width - 2 * board_thick"},
        "BottomLip_Sk")
    ext_op(case_c, pr, "groove_up", JOIN, bot_body, "BottomLip")

    # ==============================================================
    #  9. LID PANEL — board-first, rabbet cut, no rabbet on right side
    #
    #  Full board at tongue footprint → rabbet CUT removes lid_down
    #  from top face → lip JOIN restores inner area + right side at top.
    #  Right edge has no rabbet — lid slides out from right (+X).
    # ==============================================================
    # Body-relative ref: Lid depends on Front
    ref_body = find_body("Front")
    ref_bb = ref_body.boundingBox
    # Full board (NewBody): tongue footprint, Z=open_height, height=lid_thick
    _, pr = sketch_rect_model(case_c, lg_pl,
        ("board_thick - groove_depth",
         "board_thick - groove_depth",
         "open_height"),
        {"x": "box_length - board_thick + groove_depth",
         "y": "box_width - 2 * board_thick + 2 * groove_depth"},
        "Lid_Sk")
    lid_ext = ext_new(case_c, pr, "lid_thick", "Lid")
    lid_body = lid_ext.bodies.item(0)
    lid_body.name = "Lid"

    # Rabbet CUT: removes lid_down from top face (entire tongue footprint)
    ll_pl = off_plane(case_c, case_c.xYConstructionPlane,
                      "box_height - lid_down", "LidLip_Pl")
    _, pr = sketch_rect_model(case_c, ll_pl,
        ("board_thick - groove_depth",
         "board_thick - groove_depth",
         "box_height - lid_down"),
        {"x": "box_length - board_thick + groove_depth",
         "y": "box_width - 2 * board_thick + 2 * groove_depth"},
        "LidRabbet_Sk")
    ext_op(case_c, pr, "lid_down", CUT, lid_body, "LidRabbet")

    # Lip JOIN: restores inner area + right side at top (no rabbet on right)
    _, pr = sketch_rect_model(case_c, ll_pl,
        ("board_thick",
         "board_thick",
         "box_height - lid_down"),
        {"x": "box_length - board_thick",
         "y": "side_inner_len"},
        "LidLip_Sk")
    ext_op(case_c, pr, "lid_down", JOIN, lid_body, "LidLip")

    # ==============================================================
    #  HIDE CONSTRUCTION ELEMENTS
    # ==============================================================
    for comp in [case_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False
        for ca in comp.constructionAxes:
            ca.isLightBulbOn = False

    # ==============================================================
    #  DIAGNOSTIC
    # ==============================================================
    names = [case_c.bRepBodies.item(i).name for i in range(case_c.bRepBodies.count)]
    print(f"Case: {len(names)} bodies -> {names}")

    # ==============================================================
    #  FIT VIEW
    # ==============================================================
    sp.apply_appearance("brazilian rosewood")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
