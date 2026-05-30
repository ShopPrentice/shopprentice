"""
Pekovich Floating-Top Table (Rachel's Table)
=============================================
26"W x 14"D x 27-3/8"H, based on Mike Pekovich's design.
Arts & Crafts side table with bridle joints, through-tenons,
arched side rails, and a floating top with filleted edges, beveled
underside, and cleats inside rails.

Coordinate system:
  X = width (26")  Y = depth (14")  Z = height (27-3/8")

Component structure:
  Root
    +-- Legs    (FL with tool-body CUTs for bridle + mortise,
                 visible drawbore pins, mirror to all 4)
    +-- Rails   (Front body + JOIN tenons, mirror Back;
                 Left body + JOIN tenons, mirror Right)
    +-- Top     (top panel + 2 cleats inside rails with through-mortises)

Build order:
  Legs:
    1. FL leg -> bridle tool body + CUT -> mortise tool body + CUT
       -> CUT X/Y tapers -> pin bodies + CUT holes -> mirror (legs + pins)
  Rails:
    2. Front rail (body between legs) -> JOIN FL bridle tenon
       -> mirror tenon to FR end -> CUT front arch -> mirror to back
    3. Left side rail (body between legs) -> JOIN FL through-tenon
       -> mirror tenon to BL end -> CUT side arch -> mirror to right
  Top:
    4. Top panel at leg_h + left cleat inside rail zone
       -> CUT arch -> mirror right cleat
  Root:
    5. CUT pin holes into front + back rails (cross-component)
    6. CUT cleat mortises into front + back rails (cross-component)
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
    for pname, expr, unit, desc in [
        ("table_w",       "26 in",     "in", "Overall width (X)"),
        ("table_d",       "14 in",     "in", "Overall depth (Y)"),
        ("table_h",       "27 in",     "in", "Overall height (Z)"),
        ("leg_size",      "1.375 in",  "in", "Leg square cross-section"),
        ("rail_thick",    "0.75 in",   "in", "Rail thickness"),
        ("front_rail_h",  "2 in",      "in", "Front/back rail height"),
        ("side_rail_h",   "2 in",      "in", "Side rail height"),
        ("top_thick",     "0.75 in",   "in", "Top panel thickness"),
        ("top_overhang",  "1 in",      "in", "Top overhang beyond base"),
        ("leg_h",         "26 in",     "in", "Leg height (floor to leg top)"),
        ("cleat_thick",   "1.75 in",   "in", "Cleat board thickness"),
        ("cleat_w",       "1.25 in",   "in", "Cleat width (X direction)"),
        ("tt_proud",      "0.25 in",   "in", "Through-tenon proud amount"),
        ("tt_shoulder",   "0.3 in",    "in", "Through-tenon Z shoulder"),
        ("arch_rise",     "1 in",      "in", "Side rail arch rise at center"),
        ("leg_taper",    "0.25 in",   "in", "Leg taper amount at foot"),
        ("front_arch_rise", "0.5 in",   "in", "Front/back rail arch rise"),
        ("pin_dia",         "0.25 in",  "in", "Drawbore pin diameter"),
        ("pin_inset",       "0.75 in",  "in", "Pin inset from rail edge"),
        ("top_bevel_face",  "0.1 in",   "in", "Top underside bevel face distance (along side)"),
        ("top_bevel_depth", "0.7 in",   "in", "Top underside bevel depth (along bottom face)"),
        ("top_fillet",      "0.10 in",  "in", "Top edge fillet radius"),
        ("cleat_arch",      "0.5 in",   "in", "Cleat arch rise"),
    ]:
        params.add(pname, adsk.core.ValueInput.createByString(expr), unit, desc)

    for pname, expr, unit, desc in [
        ("base_w",      "table_w - 2 * top_overhang",              "in", "Base width"),
        ("base_d",      "table_d - 2 * top_overhang",              "in", "Base depth"),
        ("br_slot_w",   "leg_size / 3",                            "in", "Bridle slot width"),
        ("br_cheek",    "(leg_size - br_slot_w) / 2",              "in", "Bridle cheek thickness"),
        ("tt_tenon_h",  "side_rail_h - 2 * tt_shoulder",           "in", "Through-tenon height"),
        ("rail_cheek",  "(rail_thick - br_slot_w) / 2",            "in", "Rail cheek waste width"),
        ("taper_start", "leg_h - front_rail_h - side_rail_h",     "in", "Z where leg taper begins"),
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
        gc = sk.geometricConstraints
        gc.addHorizontal(rect[0])
        gc.addHorizontal(rect[2])
        gc.addVertical(rect[1])
        gc.addVertical(rect[3])
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

    def ext_op(comp, prof, dist_expr, op, body, name="Ext", flip=False):
        inp = comp.features.extrudeFeatures.createInput(prof, op)
        if flip:
            inp.setOneSideExtent(
                adsk.fusion.DistanceExtentDefinition.create(
                    adsk.core.ValueInput.createByString(dist_expr)),
                adsk.fusion.ExtentDirections.NegativeExtentDirection)
        else:
            inp.setDistanceExtent(False,
                adsk.core.ValueInput.createByString(dist_expr))
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

    def mirror_bodies(comp, bodies, plane, name="Mirror"):
        coll = adsk.core.ObjectCollection.create()
        for b in bodies:
            coll.add(b)
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

    def find_face(body, axis, direction):
        """Find outermost planar face along axis in direction (+1=max, -1=min)."""
        best = None
        best_val = -1e10 if direction > 0 else 1e10
        for i in range(body.faces.count):
            face = body.faces.item(i)
            geom = face.geometry
            if isinstance(geom, adsk.core.Plane):
                if abs(getattr(geom.normal, axis)) > 0.9:
                    fv = getattr(face.pointOnFace, axis)
                    if (direction > 0 and fv > best_val) or (direction < 0 and fv < best_val):
                        best_val = fv
                        best = face
        return best

    def smallest_profile(sk):
        """Return the smallest-area profile. On body-face sketches, the arch
        line+arc divides the face into two regions; the arch is the smaller one."""
        best = None
        best_area = float('inf')
        for i in range(sk.profiles.count):
            p = sk.profiles.item(i)
            a = p.areaProperties().area
            if a < best_area:
                best_area = a
                best = p
        return best

    def make_comp(name):
        occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        occ.component.name = name
        return occ

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
    #  COMPONENTS
    # ==============================================================
    legs_occ  = make_comp("Legs")
    rails_occ = make_comp("Rails")
    top_occ   = make_comp("Top")

    legs_c  = legs_occ.component
    rails_c = rails_occ.component
    top_c   = top_occ.component

    # ==============================================================
    #  LEGS COMPONENT (tool-body joinery + visible pins)
    # ==============================================================

    # 1. Front-left leg
    _, pr = sketch_rect_model(legs_c, legs_c.xYConstructionPlane,
        ("top_overhang", "top_overhang", "0 in"),
        {"x": "leg_size", "y": "leg_size"},
        "FL_Sk")
    fl_ext = ext_new(legs_c, pr, "leg_h", "FL_Leg")
    fl_body = fl_ext.bodies.item(0)
    fl_body.name = "FL"

    # 2. Construction plane at FL front face (reused for taper + pin sketches)
    fl_mortise_pl = off_plane(legs_c, legs_c.xZConstructionPlane,
        "top_overhang", "FL_Mortise_Pl")

    # 4. CUT X-taper on inside +X face of FL leg
    xt_sk = legs_c.sketches.add(fl_mortise_pl)
    xt_sk.name = "FL_XTaper_Sk"
    ax = ev("top_overhang + leg_size")
    ay = ev("top_overhang")
    bx = ev("top_overhang + leg_size - leg_taper")
    ts = ev("taper_start")
    sa = xt_sk.modelToSketchSpace(Point3D.create(ax, ay, 0))
    sb = xt_sk.modelToSketchSpace(Point3D.create(bx, ay, 0))
    sc = xt_sk.modelToSketchSpace(Point3D.create(ax, ay, ts))
    lines = xt_sk.sketchCurves.sketchLines
    xt_bot = lines.addByTwoPoints(
        Point3D.create(sa.x, sa.y, 0), Point3D.create(sb.x, sb.y, 0))
    xt_taper = lines.addByTwoPoints(
        xt_bot.endSketchPoint, Point3D.create(sc.x, sc.y, 0))
    xt_vert = lines.addByTwoPoints(
        xt_taper.endSketchPoint, xt_bot.startSketchPoint)
    xt_sk.geometricConstraints.addHorizontal(xt_bot)
    xt_sk.geometricConstraints.addVertical(xt_vert)
    ext_op(legs_c, xt_sk.profiles.item(0), "leg_size", CUT, fl_body, "FL_XTaper")

    # 5. CUT Y-taper on inside +Y face of FL leg
    fl_ytaper_pl = off_plane(legs_c, legs_c.yZConstructionPlane,
        "top_overhang + leg_size", "FL_YTaper_Pl")
    yt_sk = legs_c.sketches.add(fl_ytaper_pl)
    yt_sk.name = "FL_YTaper_Sk"
    ay2 = ev("top_overhang + leg_size")
    ax2 = ev("top_overhang + leg_size")
    by2 = ev("top_overhang + leg_size - leg_taper")
    sa2 = yt_sk.modelToSketchSpace(Point3D.create(ax2, ay2, 0))
    sb2 = yt_sk.modelToSketchSpace(Point3D.create(ax2, by2, 0))
    sc2 = yt_sk.modelToSketchSpace(Point3D.create(ax2, ay2, ts))
    lines2 = yt_sk.sketchCurves.sketchLines
    yt_bot = lines2.addByTwoPoints(
        Point3D.create(sa2.x, sa2.y, 0), Point3D.create(sb2.x, sb2.y, 0))
    yt_taper = lines2.addByTwoPoints(
        yt_bot.endSketchPoint, Point3D.create(sc2.x, sc2.y, 0))
    yt_vert = lines2.addByTwoPoints(
        yt_taper.endSketchPoint, yt_bot.startSketchPoint)
    # On YZ planes: model-Y maps to sketch-vertical, model-Z maps to sketch-horizontal
    yt_sk.geometricConstraints.addVertical(yt_bot)
    yt_sk.geometricConstraints.addHorizontal(yt_vert)
    ext_op(legs_c, yt_sk.profiles.item(0), "leg_size", CUT, fl_body, "FL_YTaper", flip=True)

    # 6. Drawbore pins — visible bodies that CUT holes in FL leg
    pin_sk = legs_c.sketches.add(fl_mortise_pl)
    pin_sk.name = "FL_Pins_Sk"
    pin_cx = ev("top_overhang + leg_size / 2")
    pin_y = ev("top_overhang")
    pin_z1 = ev("leg_h - pin_inset")
    pin_z2 = ev("leg_h - front_rail_h + pin_inset")
    pin_r = ev("pin_dia / 2")
    pc1 = pin_sk.modelToSketchSpace(Point3D.create(pin_cx, pin_y, pin_z1))
    pc2 = pin_sk.modelToSketchSpace(Point3D.create(pin_cx, pin_y, pin_z2))
    pin_sk.sketchCurves.sketchCircles.addByCenterRadius(
        Point3D.create(pc1.x, pc1.y, 0), pin_r)
    pin_sk.sketchCurves.sketchCircles.addByCenterRadius(
        Point3D.create(pc2.x, pc2.y, 0), pin_r)

    pin_area = math.pi * pin_r * pin_r
    pin_profs = adsk.core.ObjectCollection.create()
    for i in range(pin_sk.profiles.count):
        p = pin_sk.profiles.item(i)
        if abs(p.areaProperties().area - pin_area) < pin_area * 0.5:
            pin_profs.add(p)
    pin_ext_inp = legs_c.features.extrudeFeatures.createInput(
        pin_profs, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    pin_ext_inp.setDistanceExtent(False,
        adsk.core.ValueInput.createByString("leg_size"))
    pin_ext_f = legs_c.features.extrudeFeatures.add(pin_ext_inp)
    pin_ext_f.name = "FL_Pins"
    fl_pin1 = pin_ext_f.bodies.item(0)
    fl_pin2 = pin_ext_f.bodies.item(1)
    fl_pin1.name = "FL_Pin1"
    fl_pin2.name = "FL_Pin2"
    combine(legs_c, fl_body, [fl_pin1, fl_pin2], CUT, True, "FL_PinsCut")

    # 7. Mirror planes + mirror FL leg + pins -> all 4 legs + 8 pins
    xmid_legs = off_plane(legs_c, legs_c.yZConstructionPlane,
        "table_w / 2", "XMid_Pl")
    ymid_legs = off_plane(legs_c, legs_c.xZConstructionPlane,
        "table_d / 2", "YMid_Pl")

    fr_mirror = mirror_bodies(legs_c, [fl_body, fl_pin1, fl_pin2],
        xmid_legs, "FR_Mirror")
    fr_body = fr_mirror.bodies.item(0)
    fr_pin1 = fr_mirror.bodies.item(1)
    fr_pin2 = fr_mirror.bodies.item(2)
    fr_body.name = "FR"
    fr_pin1.name = "FR_Pin1"
    fr_pin2.name = "FR_Pin2"

    bl_mirror = mirror_bodies(legs_c, [fl_body, fl_pin1, fl_pin2],
        ymid_legs, "BL_Mirror")
    bl_body = bl_mirror.bodies.item(0)
    bl_body.name = "BL"
    bl_mirror.bodies.item(1).name = "BL_Pin1"
    bl_mirror.bodies.item(2).name = "BL_Pin2"

    br_mirror = mirror_bodies(legs_c, [fr_body, fr_pin1, fr_pin2],
        ymid_legs, "BR_Mirror")
    br_body = br_mirror.bodies.item(0)
    br_body.name = "BR"
    br_mirror.bodies.item(1).name = "BR_Pin1"
    br_mirror.bodies.item(2).name = "BR_Pin2"

    # -- Body-relative references: rails + pins positioned relative to legs --
    ref_fl = find_body("FL")
    ref_fl_bb = ref_fl.boundingBox
    ref_fr = find_body("FR")
    ref_fr_bb = ref_fr.boundingBox
    ref_bl = find_body("BL")
    ref_bl_bb = ref_bl.boundingBox
    ref_br = find_body("BR")
    ref_br_bb = ref_br.boundingBox

    # ==============================================================
    #  RAILS COMPONENT — FRONT/BACK (bridle tenon JOIN)
    # ==============================================================

    # 1. Front rail body (between legs only)
    front_rail_pl = off_plane(rails_c, rails_c.xZConstructionPlane,
        "top_overhang + (leg_size - rail_thick) / 2", "FrontRail_Pl")
    _, pr = sketch_rect_model(rails_c, front_rail_pl,
        ("top_overhang + leg_size",
         "top_overhang + (leg_size - rail_thick) / 2",
         "leg_h - front_rail_h"),
        {"x": "base_w - 2 * leg_size", "z": "front_rail_h"},
        "FrontRail_Sk")
    front_ext = ext_new(rails_c, pr, "rail_thick", "FrontRail")
    front_body = front_ext.bodies.item(0)
    front_body.name = "Front"

    # 2. FL bridle tenon -> JOIN to front rail
    br_tenon_pl = off_plane(rails_c, rails_c.xZConstructionPlane,
        "top_overhang + (leg_size - br_slot_w) / 2", "BrTenon_Pl")
    _, pr = sketch_rect_model(rails_c, br_tenon_pl,
        ("top_overhang",
         "top_overhang + (leg_size - br_slot_w) / 2",
         "leg_h - front_rail_h"),
        {"x": "leg_size", "z": "front_rail_h"},
        "FL_BrTenon_Sk")
    fl_tenon_ext = ext_new(rails_c, pr, "br_slot_w", "FL_BrTenon")
    fl_tenon_body = fl_tenon_ext.bodies.item(0)
    fl_tenon_join = combine(rails_c, front_body, fl_tenon_body,
        JOIN, False, "FL_BrTenon_Join")

    # 3. Mirror tenon extrude + join -> FR end
    xmid_rails = off_plane(rails_c, rails_c.yZConstructionPlane,
        "table_w / 2", "XMid_Pl")
    mirror_feats(rails_c, [fl_tenon_ext, fl_tenon_join],
        xmid_rails, "FR_Tenon_Mirror")

    # 4. CUT arch from bottom of front rail (between legs)
    front_face = find_face(front_body, "y", -1)
    fr_arch_sk = rails_c.sketches.add(front_face)
    fr_arch_sk.name = "FrontArch_Sk"
    fr_bot_z = ev("leg_h - front_rail_h")
    x_leg_in = ev("top_overhang + leg_size")
    x_leg_out = ev("top_overhang + base_w - leg_size")
    x_arch_mid = (x_leg_in + x_leg_out) / 2
    y_fr = ev("top_overhang + (leg_size - rail_thick) / 2")
    fr_rise = ev("front_arch_rise")

    fp1 = fr_arch_sk.modelToSketchSpace(Point3D.create(x_leg_in, y_fr, fr_bot_z))
    fp2 = fr_arch_sk.modelToSketchSpace(Point3D.create(x_leg_out, y_fr, fr_bot_z))
    fp3 = fr_arch_sk.modelToSketchSpace(
        Point3D.create(x_arch_mid, y_fr, fr_bot_z + fr_rise))

    fr_arch_line = fr_arch_sk.sketchCurves.sketchLines.addByTwoPoints(
        Point3D.create(fp1.x, fp1.y, 0),
        Point3D.create(fp2.x, fp2.y, 0))
    fr_arch_sk.sketchCurves.sketchArcs.addByThreePoints(
        fr_arch_line.endSketchPoint,
        Point3D.create(fp3.x, fp3.y, 0),
        fr_arch_line.startSketchPoint)

    # Parametric dimensions: tie arch baseline to rail bottom edge
    # XZ plane: sketch-H = model-X, sketch-V = -model-Z
    fad = fr_arch_sk.sketchDimensions
    fad.addDistanceDimension(
        fr_arch_sk.originPoint, fr_arch_line.startSketchPoint,
        H, Point3D.create(fp1.x / 2, fp1.y - 1, 0)
    ).parameter.expression = "top_overhang + leg_size"
    fad.addDistanceDimension(
        fr_arch_sk.originPoint, fr_arch_line.startSketchPoint,
        V, Point3D.create(fp1.x + 1, fp1.y / 2, 0)
    ).parameter.expression = "leg_h - front_rail_h"
    fad.addDistanceDimension(
        fr_arch_line.startSketchPoint, fr_arch_line.endSketchPoint,
        H, Point3D.create((fp1.x + fp2.x) / 2, fp1.y - 1, 0)
    ).parameter.expression = "base_w - 2 * leg_size"

    fr_arch_prof = smallest_profile(fr_arch_sk)
    ext_op(rails_c, fr_arch_prof, "rail_thick", CUT, front_body, "FrontArch", flip=True)

    # 5. Mirror front rail -> back rail
    ymid_rails = off_plane(rails_c, rails_c.xZConstructionPlane,
        "table_d / 2", "YMid_Pl")
    back_rail_mirror = mirror_body(rails_c, front_body,
        ymid_rails, "BackRail_Mirror")
    back_rail_body = back_rail_mirror.bodies.item(0)
    back_rail_body.name = "Back"

    # ==============================================================
    #  RAILS COMPONENT — SIDE (through-tenon JOIN)
    # ==============================================================

    # 1. Left side rail body (between legs only)
    left_side_pl = off_plane(rails_c, rails_c.yZConstructionPlane,
        "top_overhang + (leg_size - rail_thick) / 2", "LeftSide_Pl")
    _, pr = sketch_rect_model(rails_c, left_side_pl,
        ("top_overhang + (leg_size - rail_thick) / 2",
         "top_overhang + leg_size",
         "leg_h - front_rail_h - side_rail_h"),
        {"y": "base_d - 2 * leg_size", "z": "side_rail_h"},
        "LeftSide_Sk")
    left_ext = ext_new(rails_c, pr, "rail_thick", "LeftSide")
    left_body = left_ext.bodies.item(0)
    left_body.name = "Left"

    # 2. FL through-tenon -> JOIN to left side rail
    _, pr = sketch_rect_model(rails_c, left_side_pl,
        ("top_overhang + (leg_size - rail_thick) / 2",
         "top_overhang - tt_proud",
         "leg_h - front_rail_h - side_rail_h + tt_shoulder"),
        {"y": "leg_size + tt_proud", "z": "tt_tenon_h"},
        "FL_TT_Sk")
    fl_tt_ext = ext_new(rails_c, pr, "rail_thick", "FL_TT")
    fl_tt_body = fl_tt_ext.bodies.item(0)
    fl_tt_join = combine(rails_c, left_body, fl_tt_body,
        JOIN, False, "FL_TT_Join")

    # 3. Mirror tenon extrude + join -> BL end
    mirror_feats(rails_c, [fl_tt_ext, fl_tt_join],
        ymid_rails, "BL_Tenon_Mirror")

    # 4. CUT arch from bottom of left side rail (between legs)
    left_face = find_face(left_body, "x", -1)
    arch_sk = rails_c.sketches.add(left_face)
    arch_sk.name = "LeftArch_Sk"
    rail_bot_z = ev("leg_h - front_rail_h - side_rail_h")
    y_leg_in = ev("top_overhang + leg_size")
    y_leg_out = ev("top_overhang + base_d - leg_size")
    y_arch_mid = (y_leg_in + y_leg_out) / 2
    x_rail = ev("top_overhang + (leg_size - rail_thick) / 2")
    rise = ev("arch_rise")

    sp1 = arch_sk.modelToSketchSpace(Point3D.create(x_rail, y_leg_in, rail_bot_z))
    sp2 = arch_sk.modelToSketchSpace(Point3D.create(x_rail, y_leg_out, rail_bot_z))
    sp3 = arch_sk.modelToSketchSpace(
        Point3D.create(x_rail, y_arch_mid, rail_bot_z + rise))

    arch_line = arch_sk.sketchCurves.sketchLines.addByTwoPoints(
        Point3D.create(sp1.x, sp1.y, 0),
        Point3D.create(sp2.x, sp2.y, 0))
    arch_sk.sketchCurves.sketchArcs.addByThreePoints(
        arch_line.endSketchPoint,
        Point3D.create(sp3.x, sp3.y, 0),
        arch_line.startSketchPoint)

    # Parametric dimensions: tie arch baseline to side rail bottom edge
    # YZ plane: sketch-H = -model-Z, sketch-V = model-Y
    sad = arch_sk.sketchDimensions
    sad.addDistanceDimension(
        arch_sk.originPoint, arch_line.startSketchPoint,
        H, Point3D.create(sp1.x / 2, sp1.y - 1, 0)
    ).parameter.expression = "taper_start"
    sad.addDistanceDimension(
        arch_sk.originPoint, arch_line.startSketchPoint,
        V, Point3D.create(sp1.x + 1, sp1.y / 2, 0)
    ).parameter.expression = "top_overhang + leg_size"
    sad.addDistanceDimension(
        arch_line.startSketchPoint, arch_line.endSketchPoint,
        V, Point3D.create(sp1.x + 1, (sp1.y + sp2.y) / 2, 0)
    ).parameter.expression = "base_d - 2 * leg_size"

    arch_prof = smallest_profile(arch_sk)
    ext_op(rails_c, arch_prof, "rail_thick", CUT, left_body, "LeftArch", flip=True)

    # 5. Mirror left side rail -> right
    right_mirror = mirror_body(rails_c, left_body,
        xmid_rails, "RightSide_Mirror")
    right_body = right_mirror.bodies.item(0)
    right_body.name = "Right"

    # ==============================================================
    #  TOP COMPONENT
    # ==============================================================

    # -- Body-relative reference: top positioned relative to FL leg --
    # (FL ref already resolved above — re-read for top positioning)
    ref_fl_top_bb = ref_fl.boundingBox

    # Top panel
    top_pl = off_plane(top_c, top_c.xYConstructionPlane,
        "table_h - top_thick", "Top_Pl")
    _, pr = sketch_rect_model(top_c, top_pl,
        ("0 in", "0 in", "table_h - top_thick"),
        {"x": "table_w", "y": "table_d"},
        "Top_Sk")
    top_ext = ext_new(top_c, pr, "top_thick", "TopBoard")
    top_body = top_ext.bodies.item(0)
    top_body.name = "Top"

    # Left cleat (between rail inside faces)
    cleat_pl = off_plane(top_c, top_c.xYConstructionPlane,
        "table_h - top_thick - cleat_thick", "Cleat_Pl")
    _, pr = sketch_rect_model(top_c, cleat_pl,
        ("table_w / 3 - cleat_w / 2",
         "top_overhang + (leg_size + rail_thick) / 2",
         "table_h - top_thick - cleat_thick"),
        {"x": "cleat_w", "y": "base_d - leg_size - rail_thick"},
        "LeftCleat_Sk")
    left_cleat_ext = ext_new(top_c, pr, "cleat_thick", "LeftCleat")
    left_cleat_body = left_cleat_ext.bodies.item(0)
    left_cleat_body.name = "LeftCleat"

    # Y midplane for mirroring tenons front -> back
    ymid_top = off_plane(top_c, top_c.xZConstructionPlane, "table_d / 2", "YMid_Pl")

    # Front cleat through-tenon (square, centered in rail, on lower half of cleat)
    cleat_tenon_pl = off_plane(top_c, top_c.xZConstructionPlane,
        "top_overhang + (leg_size - rail_thick) / 2 - tt_proud", "CleatTenon_Pl")
    ct_sk = top_c.sketches.add(cleat_tenon_pl)
    ct_sk.name = "LeftCleatTenon_Sk"
    h_axis, v_axis = probe_sketch_axes(ct_sk)

    # Model positions: cleat corner + tenon (square, centered in rail)
    ct_py = ev("top_overhang + (leg_size - rail_thick) / 2 - tt_proud")
    ct_cx = ev("table_w / 3 - cleat_w / 2")
    ct_cz = ev("table_h - top_thick - cleat_thick")
    ct_ts = ev("cleat_w - 2 * tt_shoulder")
    ct_tx = ct_cx + ev("tt_shoulder")
    ct_tz = ev("leg_h - front_rail_h / 2") - ct_ts / 2

    # Sketch-space mapping
    sc = ct_sk.modelToSketchSpace(Point3D.create(ct_cx, ct_py, ct_cz))
    so = ct_sk.modelToSketchSpace(Point3D.create(ct_tx, ct_py, ct_tz))
    sf = ct_sk.modelToSketchSpace(
        Point3D.create(ct_tx + ct_ts, ct_py, ct_tz + ct_ts))

    # Reference point at cleat bottom-left corner
    cleat_corner = ct_sk.sketchPoints.add(Point3D.create(sc.x, sc.y, 0))

    # Tenon rectangle
    ct_rect = ct_sk.sketchCurves.sketchLines.addTwoPointRectangle(
        Point3D.create(so.x, so.y, 0),
        Point3D.create(sf.x, sf.y, 0))
    ct_sk.geometricConstraints.addHorizontal(ct_rect[0])
    ct_sk.geometricConstraints.addHorizontal(ct_rect[2])
    ct_sk.geometricConstraints.addVertical(ct_rect[1])
    ct_sk.geometricConstraints.addVertical(ct_rect[3])

    # Parametric dimensions — referenced from cleat corner, not origin
    ct_d = ct_sk.sketchDimensions
    corner_expr = {"x": "table_w / 3 - cleat_w / 2",
                   "z": "table_h - top_thick - cleat_thick"}
    dy = -1 if sf.y >= sc.y else 1
    dx = -1 if sf.x >= sc.x else 1

    ct_d.addDistanceDimension(
        ct_sk.originPoint, cleat_corner, H,
        Point3D.create(sc.x / 2, sc.y + dy, 0)
    ).parameter.expression = corner_expr[h_axis]
    ct_d.addDistanceDimension(
        ct_sk.originPoint, cleat_corner, V,
        Point3D.create(sc.x + dx, sc.y / 2, 0)
    ).parameter.expression = corner_expr[v_axis]

    ct_d.addDistanceDimension(
        cleat_corner, ct_rect[0].startSketchPoint, H,
        Point3D.create((sc.x + so.x) / 2, so.y + dy, 0)
    ).parameter.expression = "tt_shoulder"
    ct_d.addDistanceDimension(
        cleat_corner, ct_rect[0].startSketchPoint, V,
        Point3D.create(so.x + dx, (sc.y + so.y) / 2, 0)
    ).parameter.expression = "((cleat_thick + top_thick + leg_h - table_h) - (cleat_w - 2 * tt_shoulder)) / 2"

    ct_d.addDistanceDimension(
        ct_rect[0].startSketchPoint, ct_rect[0].endSketchPoint, H,
        Point3D.create((so.x + sf.x) / 2, so.y + dy, 0)
    ).parameter.expression = "cleat_w - 2 * tt_shoulder"
    ct_d.addDistanceDimension(
        ct_rect[1].startSketchPoint, ct_rect[1].endSketchPoint, V,
        Point3D.create(sf.x - dx, (so.y + sf.y) / 2, 0)
    ).parameter.expression = "cleat_w - 2 * tt_shoulder"

    left_tenon_ext = ext_new(top_c, ct_sk.profiles.item(0),
        "rail_thick + 2 * tt_proud", "LeftCleatTenon")
    left_tenon_body = left_tenon_ext.bodies.item(0)

    # Mirror front tenon body -> back tenon body
    back_tenon_mirror = mirror_body(top_c, left_tenon_body,
        ymid_top, "LeftCleatBackTenon")
    back_tenon_body = back_tenon_mirror.bodies.item(0)

    # JOIN both tenons into cleat
    combine(top_c, left_cleat_body, [left_tenon_body, back_tenon_body],
        JOIN, False, "LeftCleatTenon_Join")

    # CUT arch from bottom of left cleat (construction plane avoids coincident-edge issue)
    cleat_arch_pl = off_plane(top_c, top_c.yZConstructionPlane,
        "table_w / 3 - cleat_w / 2", "CleatArch_Pl")
    ca_sk = top_c.sketches.add(cleat_arch_pl)
    ca_sk.name = "LeftCleatArch_Sk"
    ca_bot_z = ev("table_h - top_thick - cleat_thick")
    ca_y_in = ev("top_overhang + leg_size")
    ca_y_out = ev("top_overhang + base_d - leg_size")
    ca_y_mid = (ca_y_in + ca_y_out) / 2
    ca_x = ev("table_w / 3 - cleat_w / 2")
    ca_rise = ev("cleat_arch")

    cp1 = ca_sk.modelToSketchSpace(Point3D.create(ca_x, ca_y_in, ca_bot_z))
    cp2 = ca_sk.modelToSketchSpace(Point3D.create(ca_x, ca_y_out, ca_bot_z))
    cp3 = ca_sk.modelToSketchSpace(
        Point3D.create(ca_x, ca_y_mid, ca_bot_z + ca_rise))

    ca_line = ca_sk.sketchCurves.sketchLines.addByTwoPoints(
        Point3D.create(cp1.x, cp1.y, 0),
        Point3D.create(cp2.x, cp2.y, 0))
    ca_sk.sketchCurves.sketchArcs.addByThreePoints(
        ca_line.endSketchPoint,
        Point3D.create(cp3.x, cp3.y, 0),
        ca_line.startSketchPoint)

    # Parametric dimensions: YZ plane — sketch-H = model-Z, sketch-V = model-Y
    cad = ca_sk.sketchDimensions
    cad.addDistanceDimension(
        ca_sk.originPoint, ca_line.startSketchPoint,
        H, Point3D.create(cp1.x / 2, cp1.y - 1, 0)
    ).parameter.expression = "table_h - top_thick - cleat_thick"
    cad.addDistanceDimension(
        ca_sk.originPoint, ca_line.startSketchPoint,
        V, Point3D.create(cp1.x + 1, cp1.y / 2, 0)
    ).parameter.expression = "top_overhang + leg_size"
    cad.addDistanceDimension(
        ca_line.startSketchPoint, ca_line.endSketchPoint,
        V, Point3D.create(cp1.x + 1, (cp1.y + cp2.y) / 2, 0)
    ).parameter.expression = "base_d - 2 * leg_size"

    ca_prof = smallest_profile(ca_sk)
    ext_op(top_c, ca_prof, "cleat_w", CUT, left_cleat_body, "LeftCleatArch")

    # -- Body-relative reference: cleat positioned relative to top --
    ref_top = find_body("Top")
    ref_top_bb = ref_top.boundingBox

    # Mirror left cleat -> right
    xmid_top = off_plane(top_c, top_c.yZConstructionPlane,
        "table_w / 2", "XMid_Pl")
    right_cleat_mirror = mirror_body(top_c, left_cleat_body,
        xmid_top, "RightCleat_Mirror")
    right_cleat_body = right_cleat_mirror.bodies.item(0)
    right_cleat_body.name = "RightCleat"

    # ==============================================================
    #  ROOT — Cross-Component Operations
    # ==============================================================

    # Rail tenons CUT legs: each rail body (with JOINed tenons) cuts its legs
    rail_refs = {}
    for i in range(rails_c.bRepBodies.count):
        b = rails_c.bRepBodies.item(i)
        rail_refs[b.name] = b

    leg_refs = {}
    for i in range(legs_c.bRepBodies.count):
        b = legs_c.bRepBodies.item(i)
        if b.name in ("FL", "FR", "BL", "BR"):
            leg_refs[b.name] = b

    front_proxy = rail_refs["Front"].createForAssemblyContext(rails_occ)
    back_proxy = rail_refs["Back"].createForAssemblyContext(rails_occ)
    left_proxy = rail_refs["Left"].createForAssemblyContext(rails_occ)
    right_proxy = rail_refs["Right"].createForAssemblyContext(rails_occ)

    # Bridle slots: front/back rails CUT their corner legs
    combine(root, leg_refs["FL"].createForAssemblyContext(legs_occ),
        front_proxy, CUT, True, "FL_BridleSlot")
    combine(root, leg_refs["FR"].createForAssemblyContext(legs_occ),
        front_proxy, CUT, True, "FR_BridleSlot")
    combine(root, leg_refs["BL"].createForAssemblyContext(legs_occ),
        back_proxy, CUT, True, "BL_BridleSlot")
    combine(root, leg_refs["BR"].createForAssemblyContext(legs_occ),
        back_proxy, CUT, True, "BR_BridleSlot")

    # Through-tenon mortises: side rails CUT their corner legs
    combine(root, leg_refs["FL"].createForAssemblyContext(legs_occ),
        left_proxy, CUT, True, "FL_TTMortise")
    combine(root, leg_refs["BL"].createForAssemblyContext(legs_occ),
        left_proxy, CUT, True, "BL_TTMortise")
    combine(root, leg_refs["FR"].createForAssemblyContext(legs_occ),
        right_proxy, CUT, True, "FR_TTMortise")
    combine(root, leg_refs["BR"].createForAssemblyContext(legs_occ),
        right_proxy, CUT, True, "BR_TTMortise")

    # Pin holes: pin bodies CUT front/back rails
    leg_names = {"FL", "FR", "BL", "BR"}
    front_pin_proxies = []
    back_pin_proxies = []
    ymid_val = ev("table_d / 2")
    for i in range(legs_c.bRepBodies.count):
        b = legs_c.bRepBodies.item(i)
        if b.name in leg_names:
            continue
        proxy = b.createForAssemblyContext(legs_occ)
        cy = (b.boundingBox.minPoint.y + b.boundingBox.maxPoint.y) / 2
        if cy < ymid_val:
            front_pin_proxies.append(proxy)
        else:
            back_pin_proxies.append(proxy)

    # Look up rail bodies fresh (references may be stale after JOINs/mirrors)
    front_ref = back_ref = None
    for i in range(rails_c.bRepBodies.count):
        b = rails_c.bRepBodies.item(i)
        if b.name == "Front":
            front_ref = b
        elif b.name == "Back":
            back_ref = b
    front_proxy = front_ref.createForAssemblyContext(rails_occ)
    back_proxy = back_ref.createForAssemblyContext(rails_occ)

    combine(root, front_proxy, front_pin_proxies, CUT, True, "PinHoles_Front")
    combine(root, back_proxy, back_pin_proxies, CUT, True, "PinHoles_Back")

    # Cleat through-tenon mortises: cleat bodies CUT front/back rails
    top_refs = {}
    for i in range(top_c.bRepBodies.count):
        b = top_c.bRepBodies.item(i)
        top_refs[b.name] = b
    left_cleat_proxy = top_refs["LeftCleat"].createForAssemblyContext(top_occ)
    right_cleat_proxy = top_refs["RightCleat"].createForAssemblyContext(top_occ)

    # Re-lookup rail bodies (may be stale after previous CUTs)
    front_ref2 = back_ref2 = None
    for i in range(rails_c.bRepBodies.count):
        b = rails_c.bRepBodies.item(i)
        if b.name == "Front":
            front_ref2 = b
        elif b.name == "Back":
            back_ref2 = b
    front_proxy2 = front_ref2.createForAssemblyContext(rails_occ)
    back_proxy2 = back_ref2.createForAssemblyContext(rails_occ)

    combine(root, front_proxy2, [left_cleat_proxy, right_cleat_proxy],
        CUT, True, "CleatMortise_Front")
    combine(root, back_proxy2, [left_cleat_proxy, right_cleat_proxy],
        CUT, True, "CleatMortise_Back")

    # ==============================================================
    #  DETAILS
    # ==============================================================

    # Two-distance chamfer (bevel) on bottom perimeter of top panel
    bot_z = ev("table_h - top_thick")
    bot_edges = adsk.core.ObjectCollection.create()
    for i in range(top_body.edges.count):
        edge = top_body.edges.item(i)
        sv = edge.startVertex.geometry
        ep = edge.endVertex.geometry
        if abs(sv.z - bot_z) < 0.01 and abs(ep.z - bot_z) < 0.01:
            bot_edges.add(edge)
    if bot_edges.count > 0:
        bevel_inp = top_c.features.chamferFeatures.createInput2()
        bevel_inp.chamferEdgeSets.addTwoDistancesChamferEdgeSet(
            bot_edges,
            adsk.core.ValueInput.createByString("top_bevel_face"),
            adsk.core.ValueInput.createByString("top_bevel_depth"),
            True,
            True)
        bf = top_c.features.chamferFeatures.add(bevel_inp)
        bf.name = "TopBevel"

    # Fillet top panel top-face edges
    top_z = ev("table_h")
    top_edges = adsk.core.ObjectCollection.create()
    for i in range(top_body.edges.count):
        edge = top_body.edges.item(i)
        sv = edge.startVertex.geometry
        ep = edge.endVertex.geometry
        if abs(sv.z - top_z) < 0.01 and abs(ep.z - top_z) < 0.01:
            top_edges.add(edge)
    if top_edges.count > 0:
        fillet_inp = top_c.features.filletFeatures.createInput()
        fillet_inp.addConstantRadiusEdgeSet(
            top_edges,
            adsk.core.ValueInput.createByString("top_fillet"),
            True)
        ff = top_c.features.filletFeatures.add(fillet_inp)
        ff.name = "TopFillet"

    # ==============================================================
    #  EPILOGUE
    # ==============================================================
    for comp_c in [legs_c, rails_c, top_c]:
        for sk in comp_c.sketches:
            sk.isVisible = False
        for cp in comp_c.constructionPlanes:
            cp.isLightBulbOn = False

    all_bodies = []
    for comp_c in [legs_c, rails_c, top_c]:
        for i in range(comp_c.bRepBodies.count):
            all_bodies.append(comp_c.bRepBodies.item(i).name)
    print(f"Total: {len(all_bodies)} bodies -> {all_bodies}")

    sp.apply_appearance("white oak")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
