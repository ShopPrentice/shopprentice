"""Teak Desk — parametric recreation from Teak Desk v21 capture.

Components: top, legs (entasis + splay), aprons (arched bottom),
outer_slats, inner_slats, side_stretchers (round, lofted to legs),
dovetail_blocks.
"""
import adsk.core
import adsk.fusion
import math


LEG_ENTASIS = [
    (14.000, 693.0),
    (14.534, 611.195),
    (15.008, 538.389),
    (15.423, 474.529),
    (15.780, 419.133),
    (16.083, 370.912),
    (16.343, 327.379),
    (16.568, 285.015),
    (16.746, 240.553),
    (16.818, 192.587),
    (16.662, 142.624),
    (16.123, 94.286),
    (15.051, 51.629),
    (13.354, 17.509),
    (11.000, -7.0),
]

APRON_ARCH = [
    (0.0, 643.0),
    (-22.817, 642.551),
    (-47.585, 642.099),
    (-74.369, 641.587),
    (-103.251, 640.888),
    (-134.226, 639.834),
    (-167.052, 638.290),
    (-201.092, 636.196),
    (-235.163, 633.563),
    (-267.606, 630.464),
    (-298.117, 627.137),
    (-328.359, 623.962),
    (-360.298, 621.281),
    (-395.064, 619.274),
    (-433.043, 618.000),
]

# 15-point apron end scallop — sketch (y_mm, z_mm) from arch shoulder up to
# just short of board corner. Mirror for the other end.
APRON_END_SCALLOP = [
    (-435.036, 618.000),
    (-441.694, 617.999),
    (-450.157, 618.062),
    (-460.471, 619.977),
    (-471.588, 624.334),
    (-481.808, 629.729),
    (-490.694, 635.436),
    (-499.444, 642.416),
    (-509.033, 651.803),
    (-518.269, 663.145),
    (-524.156, 674.353),
    (-524.355, 683.198),
    (-519.603, 688.832),
    (-513.196, 691.877),
    (-507.488, 693.000),
]


def _center_rect_xy(comp, plane, size_x_expr, size_y_expr, name):
    """Two-point rectangle on an XY-parallel plane, symmetric about sketch origin.

    Uses SymmetricConstraint between opposite corners through sketch origin axes.
    """
    P3 = adsk.core.Point3D.create
    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation

    sk = comp.sketches.add(plane)
    sk.name = name

    # Initial rectangle from (-5, -5) to (5, 5) — 4 lines
    rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(
        P3(-5, -5, 0), P3(5, 5, 0))

    # Identify edges: rect has 4 lines, 2 horizontal + 2 vertical
    gc = sk.geometricConstraints
    for i in range(rect.count):
        L = rect.item(i)
        p1 = L.startSketchPoint.geometry
        p2 = L.endSketchPoint.geometry
        if abs(p1.y - p2.y) < 1e-6:
            gc.addHorizontal(L)
        elif abs(p1.x - p2.x) < 1e-6:
            gc.addVertical(L)

    # Anchor center of rectangle to origin.
    # Use a midpoint constraint: for each horizontal line, its midpoint is on
    # sketch Y-axis (x=0). For each vertical line, midpoint is on X-axis (y=0).
    # Simpler: constrain two corners to be symmetric across origin via coincidence
    # of diagonal midpoint with origin. But easier: directly constrain
    # opposite corners' midpoint = origin by SymmetricConstraint.

    # Find 2 opposite corners
    pts = []
    for i in range(rect.count):
        L = rect.item(i)
        for p in (L.startSketchPoint, L.endSketchPoint):
            if not any(abs(p.geometry.x - q.geometry.x) < 1e-6 and
                       abs(p.geometry.y - q.geometry.y) < 1e-6 for q in pts):
                pts.append(p)
    # pts is list of 4 unique corner points
    # Find diagonal pair — corner at (-, -) and corner at (+, +)
    corner_nn = next(p for p in pts
                     if p.geometry.x < 0 and p.geometry.y < 0)
    corner_pp = next(p for p in pts
                     if p.geometry.x > 0 and p.geometry.y > 0)
    # Symmetric about origin: construct a construction line through origin, or
    # use midpoint constraint with origin.
    # Fusion has addSymmetryConstraint(entity1, entity2, symmetryLine) — needs a line.
    # Simpler: add midpoint constraint between origin and diagonal line.
    diag_line = sk.sketchCurves.sketchLines.addByTwoPoints(corner_nn, corner_pp)
    diag_line.isConstruction = True
    gc.addMidPoint(sk.originPoint, diag_line)

    # Dimension width and length on one horizontal + one vertical edge
    h_line = next(rect.item(i) for i in range(rect.count)
                  if abs(rect.item(i).startSketchPoint.geometry.y
                         - rect.item(i).endSketchPoint.geometry.y) < 1e-6)
    v_line = next(rect.item(i) for i in range(rect.count)
                  if abs(rect.item(i).startSketchPoint.geometry.x
                         - rect.item(i).endSketchPoint.geometry.x) < 1e-6)

    d = sk.sketchDimensions
    d.addDistanceDimension(h_line.startSketchPoint, h_line.endSketchPoint,
                            H, P3(0, -7, 0)).parameter.expression = size_x_expr
    d.addDistanceDimension(v_line.startSketchPoint, v_line.endSketchPoint,
                            V, P3(7, 0, 0)).parameter.expression = size_y_expr
    return sk, sk.profiles.item(0)


def run(context):
    from helpers import sp

    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    P3 = adsk.core.Point3D.create
    V3 = adsk.core.Vector3D.create
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
    NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    ctx = sp.DesignContext(design)
    ev = ctx.ev

    params.add("total_height", VI("720 mm"), "mm", "Overall height")
    params.add("top_thickness", VI("17 mm"), "mm", "Top slab thickness")
    params.add("top_width", VI("470 mm"), "mm", "Top width (X)")
    params.add("top_length", VI("1080 mm"), "mm", "Top length (Y)")
    params.add("top_edge_bot", VI("15 mm"), "mm", "Top bottom-edge fillet")
    params.add("top_edge_top", VI("3.75 mm"), "mm", "Top upper-edge fillet")
    params.add("to_floor", VI("total_height - top_thickness"), "mm",
               "Underside of top height")

    params.add("leg_dist_x", VI("380 mm"), "mm", "Leg centerline X spread")
    params.add("leg_dist_y", VI("850 mm"), "mm", "Leg centerline Y spread")
    params.add("leg_length", VI("700 mm"), "mm", "Leg length")
    params.add("leg_to_top", VI("10 mm"), "mm", "Gap between leg top and underside")
    params.add("angle_y", VI("3 deg"), "deg", "Leg splay (rotation around X)")
    params.add("feet_radius", VI("5 mm"), "mm", "Foot fillet radius")

    params.add("stretcher_width", VI("1050 mm"), "mm", "Apron length (Y)")
    params.add("stretcher_height", VI("75 mm"), "mm", "Apron height (Z)")
    params.add("stretcher_thickness", VI("18 mm"), "mm", "Apron thickness (X)")
    params.add("stretcher_to_top", VI("10 mm"), "mm", "Gap apron top to underside")
    params.add("apron_edge_fillet", VI("3 mm"), "mm", "Apron top-edge fillet")
    params.add("apron_end_fillet", VI("5 mm"), "mm", "Apron end transition fillet")

    params.add("slat_outer_y", VI("leg_dist_y / 2"), "mm", "Outer slat Y position")
    params.add("slat_inner_y", VI("leg_dist_y / 6"), "mm", "Inner slat Y position")
    params.add("slat_thickness", VI("30 mm"), "mm", "Slat thickness (Y)")
    params.add("slat_outer_h", VI("54 mm"), "mm", "Outer slat height (Z)")
    params.add("slat_inner_h", VI("25 mm"), "mm", "Inner slat height (Z)")
    params.add("slat_top_gap", VI("5 mm"), "mm", "Slat top to underside gap")
    params.add("slat_outer_tenon_leg_radius", VI("16 mm"), "mm",
               "Leg radius at outer slat tenon height")
    params.add("slat_outer_tenon_proud", VI("1 mm"), "mm",
               "Outer slat tenon proud past leg surface")
    params.add("slat_outer_x_half",
               VI("leg_dist_x / 2 + slat_outer_tenon_leg_radius + slat_outer_tenon_proud"),
               "mm", "Outer slat X half-span (tenon tip position)")
    params.add("slat_inner_x_half",
               VI("leg_dist_x / 2 - stretcher_thickness / 2"),
               "mm", "Slat main-body X half-span (= apron inner face)")
    params.add("slat_tenon_y", VI("12 mm"), "mm", "Slat tenon Y thickness")
    params.add("slat_outer_tenon_z", VI("28 mm"), "mm", "Outer slat tenon Z height")
    params.add("slat_inner_tenon_z", VI("20 mm"), "mm", "Inner slat tenon Z height")
    params.add("slat_inner_tenon_extend",
               VI("12 mm"), "mm", "Inner slat tenon extends past apron inner face")
    params.add("slat_inner_tenon_x_half",
               VI("slat_inner_x_half + slat_inner_tenon_extend"),
               "mm", "Inner slat tenon tip X position")

    params.add("side_stretcher_r", VI("13 mm"), "mm", "Side stretcher radius")
    params.add("side_stretcher_r_end", VI("25 mm"), "mm", "Side stretcher end-loft radius")
    params.add("side_stretcher_z", VI("250 mm"), "mm", "Side stretcher height from floor")
    params.add("side_stretcher_to_leg", VI("30 mm"), "mm", "Side stretcher inset from leg center")
    params.add("ss_y_shift",
               VI("(to_floor - leg_to_top - side_stretcher_z) * sin(angle_y)"),
               "mm", "Leg splay Y shift at side-stretcher Z")

    params.add("dovetail_width", VI("30 mm"), "mm", "Dovetail block width X (wide face, deep in slat)")
    params.add("dovetail_bottom_width", VI("25 mm"), "mm", "Dovetail narrow face (mouth at slat surface)")
    params.add("dovetail_angle", VI("74 deg"), "deg", "Dovetail taper angle")
    params.add("dovetail_thickness", VI("15 mm"), "mm", "Dovetail block thickness Z")
    params.add("dovetail_length", VI("80 mm"), "mm", "Dovetail block length Y")
    params.add("dovetail_quantity", VI("3"), "", "Dovetail count per row")
    params.add("dovetail_col_span",
               VI("leg_dist_x - stretcher_thickness"),
               "mm", "Column span for dovetail pattern (= inner slat span)")
    params.add("dovetail_space",
               VI("(dovetail_col_span - dovetail_width * (dovetail_quantity + 2)) / (dovetail_quantity - 1)"),
               "mm", "Dovetail X gap between blocks")
    params.add("dovetail_inner_y", VI("leg_dist_y / 6"), "mm", "Inner dovetail row Y")
    params.add("dovetail_outer_y", VI("leg_dist_y / 2"), "mm", "Outer dovetail row Y")

    # ═══════════════════════════════════════════════════════
    # Phase 1: Top slab — 15mm bottom edges, 3.75mm top edges
    # ═══════════════════════════════════════════════════════
    # Body-relative reference: top depends on leg_FR (placed after legs exist)
    # Deferred to after Phase 2 — see below

    top_c = sp.make_comp(root, "top").component

    top_pl = sp.off_plane(top_c, top_c.xYConstructionPlane,
                          "to_floor", "top_Pl")
    _, pr = _center_rect_xy(top_c, top_pl, "top_width", "top_length", "top_Sk")
    top_ext = sp.ext_new(top_c, pr, "top_thickness", "top_Board")
    top_body = top_ext.bodies.item(0)
    top_body.name = "top"

    bot_edges = adsk.core.ObjectCollection.create()
    top_edges = adsk.core.ObjectCollection.create()
    z_bot = ev("to_floor")
    z_top = ev("to_floor + top_thickness")
    for i in range(top_body.edges.count):
        e = top_body.edges.item(i)
        p1z = e.startVertex.geometry.z
        p2z = e.endVertex.geometry.z
        if e.length > 0.1:
            if abs(p1z - z_bot) < 0.01 and abs(p2z - z_bot) < 0.01:
                bot_edges.add(e)
            elif abs(p1z - z_top) < 0.01 and abs(p2z - z_top) < 0.01:
                top_edges.add(e)

    if bot_edges.count > 0:
        f = top_c.features.filletFeatures.createInput()
        f.addConstantRadiusEdgeSet(bot_edges, VI("top_edge_bot"), True)
        top_c.features.filletFeatures.add(f).name = "top_FilBot"
    if top_edges.count > 0:
        f = top_c.features.filletFeatures.createInput()
        f.addConstantRadiusEdgeSet(top_edges, VI("top_edge_top"), True)
        top_c.features.filletFeatures.add(f).name = "top_FilTop"

    _build_top_ears(top_c, top_body, ev)
    print(f"Phase 1 — Top: {top_c.bRepBodies.count} bodies")

    # ═══════════════════════════════════════════════════════
    # Phase 2: Legs — 15-pt entasis revolve, 3° splay, mirrored to 4
    # ═══════════════════════════════════════════════════════
    legs_c = sp.make_comp(root, "legs").component
    _build_legs(root, legs_c, ev)
    print(f"Phase 2 — Legs: {legs_c.bRepBodies.count} bodies")

    # Body-relative references: top depends on leg_FR, ear_R/ear_L depend on top
    ref_leg_fr = ctx.find_body("leg_FR")
    ref_leg_fr_bb = ref_leg_fr.boundingBox
    ref_top = ctx.find_body("top")
    ref_top_bb = ref_top.boundingBox

    # ═══════════════════════════════════════════════════════
    # Phase 3: Aprons — arched bottom, front + back mirrored
    # ═══════════════════════════════════════════════════════
    # Body-relative reference: apron_F depends on leg_FR
    ref_leg_fr2 = ctx.find_body("leg_FR")
    ref_leg_fr2_bb = ref_leg_fr2.boundingBox

    aprons_c = sp.make_comp(root, "aprons").component
    _build_aprons(root, aprons_c, ev)
    _build_apron_bowties(aprons_c, ev)
    print(f"Phase 3 — Aprons: {aprons_c.bRepBodies.count} bodies")

    # Body-relative reference: apron_F (1) depends on leg_FR (2)
    ref_leg_fr_2 = ctx.find_body("leg_FR (2)")
    ref_leg_fr_2_bb = ref_leg_fr_2.boundingBox

    # ═══════════════════════════════════════════════════════
    # Phase 4: Outer + inner slats (horizontal cross-rails at top)
    # ═══════════════════════════════════════════════════════
    # Body-relative references: outerSlat_F depends on apron_F, outerSlat_B depends on apron_F (1)
    ref_apron_f = ctx.find_body("apron_F")
    ref_apron_f_bb = ref_apron_f.boundingBox
    ref_apron_f1 = ctx.find_body("apron_F (1)")
    ref_apron_f1_bb = ref_apron_f1.boundingBox

    outer_c = sp.make_comp(root, "outer_slats").component
    _build_outer_slats(root, outer_c, ev)
    print(f"Phase 4a — outer_slats: {outer_c.bRepBodies.count} bodies")

    # Body-relative reference: innerSlat_F depends on apron_F, innerSlat_B on apron_F (1)
    # (already looked up above)

    inner_c = sp.make_comp(root, "inner_slats").component
    _build_inner_slats(root, inner_c, ev)
    print(f"Phase 4b — inner_slats: {inner_c.bRepBodies.count} bodies")

    # ═══════════════════════════════════════════════════════
    # Phase 5: Side stretchers (round bars at ±splayed-leg-Y)
    # ═══════════════════════════════════════════════════════
    # Body-relative reference: sideStretcher_F depends on leg_FR
    ref_leg_fr3 = ctx.find_body("leg_FR")
    ref_leg_fr3_bb = ref_leg_fr3.boundingBox

    ss_c = sp.make_comp(root, "side_stretchers").component
    _build_side_stretchers(root, ss_c, ev)
    _build_stretcher_transitions(ss_c, ev)
    print(f"Phase 5 — side_stretchers: {ss_c.bRepBodies.count} bodies")

    # Body-relative references: transitions depend on sideStretcher_F, sideStretcher_F (1)
    ref_ss_f = ctx.find_body("sideStretcher_F")
    ref_ss_f_bb = ref_ss_f.boundingBox
    ref_ss_f1 = ctx.find_body("sideStretcher_F (1)")
    ref_ss_f1_bb = ref_ss_f1.boundingBox

    # ═══════════════════════════════════════════════════════
    # Phase 6: Dovetail blocks — 12 blocks (3x4 grid) on underside of top
    # ═══════════════════════════════════════════════════════
    # Body-relative references: dovetail blocks depend on outerSlat_F/B, innerSlat_F/B
    ref_outer_f = ctx.find_body("outerSlat_F")
    ref_outer_f_bb = ref_outer_f.boundingBox
    ref_outer_b = ctx.find_body("outerSlat_B")
    ref_outer_b_bb = ref_outer_b.boundingBox
    ref_inner_f = ctx.find_body("innerSlat_F")
    ref_inner_f_bb = ref_inner_f.boundingBox
    ref_inner_b = ctx.find_body("innerSlat_B")
    ref_inner_b_bb = ref_inner_b.boundingBox

    dt_c = sp.make_comp(root, "dovetail_blocks").component
    _build_dovetail_blocks(root, dt_c, ev)
    print(f"Phase 6 — dovetail_blocks: {dt_c.bRepBodies.count} bodies")

    # ═══════════════════════════════════════════════════════
    # Phase 7: Joinery — leg mortises + slat notches via cross-component CUTs
    # ═══════════════════════════════════════════════════════
    _build_joinery(root, legs_c, aprons_c, outer_c, inner_c, ss_c)
    _build_dovetail_joinery(root, outer_c, inner_c, dt_c)
    _add_apron_end_fillets(aprons_c)
    print(f"Phase 7 — joinery cuts applied")

    total = root.bRepBodies.count
    for occ in root.occurrences:
        total += occ.component.bRepBodies.count
    print(f"Total: {total} bodies")

    # Phase 8: Wood appearances (teak everywhere; real-photo texture on top)
    try:
        _apply_textures()
        print("Phase 8 — appearances applied (teak + custom photo on top)")
    except Exception as e:
        print(f"Phase 8 skipped: {e}")


def _build_top_ears(top_c, top_body, ev):
    """Thin veneer shells on the long top edges plus the right-side axis marker."""
    VI = adsk.core.ValueInput.createByString
    NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    P3 = adsk.core.Point3D.create

    def make_ear(name, sign):
        # Captured from reference Untitled (2): the ear is a 0.01mm
        # non-symmetric Thicken of the two long cylindrical side-edge faces.
        faces = adsk.core.ObjectCollection.create()
        for i in range(top_body.faces.count):
            face = top_body.faces.item(i)
            try:
                if face.geometry.objectType != "adsk::core::Cylinder":
                    continue
            except Exception:
                continue
            bb = face.boundingBox
            y_span = bb.maxPoint.y - bb.minPoint.y
            if y_span < 100.0:
                continue
            if sign > 0 and bb.minPoint.x > 21.9:
                faces.add(face)
            elif sign < 0 and bb.maxPoint.x < -21.9:
                faces.add(face)

        if faces.count == 0:
            return
        offset_in = top_c.features.offsetFeatures.createInput(
            faces, VI("0 mm"), NEW, False)
        offset = top_c.features.offsetFeatures.add(offset_in)
        offset.name = f"{name}_OffsetSurface"
        surfaces = adsk.core.ObjectCollection.create()
        for i in range(offset.bodies.count):
            surface = offset.bodies.item(i)
            if surface.isSolid:
                continue
            surface.name = f"{name}_surface"
            surface.isLightBulbOn = False
            surfaces.add(surface)
        if surfaces.count == 0:
            return

        thick_in = top_c.features.thickenFeatures.createInput(
            surfaces, VI("0.01 mm"), False, NEW, True)
        thick = top_c.features.thickenFeatures.add(thick_in)
        thick.name = f"{name}_Thicken"
        if thick.bodies.count > 0:
            thick.bodies.item(0).name = name
        for i in range(surfaces.count):
            surfaces.item(i).isLightBulbOn = False

    make_ear("ear_R", 1)
    make_ear("ear_L", -1)
    for i in range(top_c.bRepBodies.count):
        body = top_c.bRepBodies.item(i)
        if body.name.endswith("_surface"):
            body.isLightBulbOn = False

    # Cylindrical projection debug/reference axis used for the right ear.
    sk = top_c.sketches.add(top_c.xZConstructionPlane)
    sk.name = "axis_marker_R_sk"
    ctr = sk.modelToSketchSpace(P3(22.0, 0.0, 71.8))
    sk.sketchCurves.sketchCircles.addByCenterRadius(P3(ctr.x, ctr.y, 0), 0.15)
    prof = sk.profiles.item(0)
    ex_in = top_c.features.extrudeFeatures.createInput(prof, NEW)
    ex_in.setSymmetricExtent(VI("108 cm"), True)
    ex = top_c.features.extrudeFeatures.add(ex_in)
    ex.name = "axis_marker_R"
    axis_body = ex.bodies.item(0)
    axis_body.name = "axis_marker_R"
    axis_body.isLightBulbOn = False
    sk.isVisible = False


def _build_apron_bowties(aprons_c, ev):
    """Rosewood bowtie inlays copied from the v22 apron positions."""
    from woodworking.templates import bowtie

    VI = adsk.core.ValueInput.createByString

    apron = aprons_c.bRepBodies.itemByName("apron_F")
    if apron is None:
        return

    plane_in = aprons_c.constructionPlanes.createInput()
    plane_in.setByOffset(aprons_c.yZConstructionPlane, VI("19.4 cm"))
    plane = aprons_c.constructionPlanes.add(plane_in)
    plane.name = "BT_apron_F_v22_plane"

    specs = [
        ("BT_apron_F_v22_1", 33.3550, 66.4760, 4.0030, 0.8820),
        ("BT_apron_F_v22_2", 20.0150, 67.0260, 3.3610, 0.6590),
        ("BT_apron_F_v22_3", 5.9880, 66.5040, 2.6890, 0.7990),
        ("BT_apron_F_v22_4", -8.0060, 65.7440, 2.3520, 0.6960),
        ("BT_apron_F_v22_5", 45.9180, 66.5210, 3.2200, 0.7810),
    ]
    for name, cy, cz, length, end_w in specs:
        bowtie.single(
            aprons_c, plane,
            center=("19.4 cm", f"{cy} cm", f"{cz} cm"),
            long_axis="z", short_axis="y",
            length=f"{length} cm",
            end_w=f"{end_w} cm",
            waist_w=f"{max(end_w * 0.42, 0.22)} cm",
            depth="0.5 cm",
            slab_body=apron,
            name=name,
            ev=ev,
            cut=True)
    plane.isLightBulbOn = False


def _build_stretcher_transitions(side_comp, ev):
    """Editable v22-location loft transition bodies at all stretcher/leg joints."""
    P = adsk.core.Point3D.create
    VI = adsk.core.ValueInput.createByString
    NEWBODY = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    prefix = "v22loc_transition_front_right"
    local_body_name = "editable_loft_transition_front_right_v22loc_in_side_stretchers"

    x_stretcher = 16.0
    x_leg = 18.514

    stretcher_body = side_comp.bRepBodies.itemByName("sideStretcher_F")
    if stretcher_body is None:
        return

    # Captured from the manually edited Untitled source document. These are
    # the adjusted rails for the smooth stretcher-to-leg transition.
    circle_cy = -44.81848286156241
    circle_cz = 25.0
    r_circle = 1.3
    ellipse_cy = -44.8694971433198
    ellipse_cz = 25.087301127134086
    major_r = 3.0
    minor_r = 1.6
    major_y = 0.05233595624294433
    major_z = 0.9986295347545739
    minor_y = -major_z
    minor_z = major_y

    def offset_plane(x, name):
        cpi = side_comp.constructionPlanes.createInput()
        cpi.setByOffset(side_comp.yZConstructionPlane, VI(f"{x} cm"))
        plane = side_comp.constructionPlanes.add(cpi)
        plane.name = name
        plane.isLightBulbOn = False
        return plane

    def add_profile_point(sk, model_pt, curve):
        sk_pt = sk.modelToSketchSpace(model_pt)
        pt = sk.sketchPoints.add(P(sk_pt.x, sk_pt.y, 0))
        sk.geometricConstraints.addCoincident(pt, curve)
        return pt

    circle_plane = offset_plane(x_stretcher, f"{prefix}_stretcher_small_circle_plane")
    circle_sk = side_comp.sketches.add(circle_plane)
    circle_sk.name = f"{prefix}_stretcher_small_circle"
    c_ctr = circle_sk.modelToSketchSpace(P(x_stretcher, circle_cy, circle_cz))
    circle = circle_sk.sketchCurves.sketchCircles.addByCenterRadius(
        P(c_ctr.x, c_ctr.y, 0), r_circle)

    circle_top = add_profile_point(circle_sk, P(x_stretcher, circle_cy, circle_cz + r_circle), circle)
    circle_bottom = add_profile_point(circle_sk, P(x_stretcher, circle_cy, circle_cz - r_circle), circle)
    circle_front = add_profile_point(circle_sk, P(x_stretcher, circle_cy - r_circle, circle_cz), circle)
    circle_back = add_profile_point(circle_sk, P(x_stretcher, circle_cy + r_circle, circle_cz), circle)

    ellipse_plane = offset_plane(x_leg, f"{prefix}_leg_large_ellipse_plane")
    ellipse_sk = side_comp.sketches.add(ellipse_plane)
    ellipse_sk.name = f"{prefix}_leg_large_ellipse"
    e_ctr = ellipse_sk.modelToSketchSpace(P(x_leg, ellipse_cy, ellipse_cz))
    e_major = ellipse_sk.modelToSketchSpace(
        P(x_leg, ellipse_cy + major_y * major_r, ellipse_cz + major_z * major_r))
    e_minor = ellipse_sk.modelToSketchSpace(
        P(x_leg, ellipse_cy + minor_y * minor_r, ellipse_cz + minor_z * minor_r))
    ellipse = ellipse_sk.sketchCurves.sketchEllipses.add(
        P(e_ctr.x, e_ctr.y, 0), P(e_major.x, e_major.y, 0), P(e_minor.x, e_minor.y, 0))

    ellipse_top = add_profile_point(
        ellipse_sk, P(x_leg, ellipse_cy + major_y * major_r, ellipse_cz + major_z * major_r), ellipse)
    ellipse_bottom = add_profile_point(
        ellipse_sk, P(x_leg, ellipse_cy - major_y * major_r, ellipse_cz - major_z * major_r), ellipse)
    ellipse_front = add_profile_point(
        ellipse_sk, P(x_leg, ellipse_cy + minor_y * minor_r, ellipse_cz + minor_z * minor_r), ellipse)
    ellipse_back = add_profile_point(
        ellipse_sk, P(x_leg, ellipse_cy - minor_y * minor_r, ellipse_cz - minor_z * minor_r), ellipse)

    def create_three_point_plane(name, point_a, point_b, helper_model_pt):
        helper_sk = side_comp.sketches.add(side_comp.xYConstructionPlane)
        helper_sk.name = f"{name}_midpoint"
        helper = helper_sk.sketchPoints.add(P(helper_model_pt.x, helper_model_pt.y, 0))
        cpi = side_comp.constructionPlanes.createInput()
        cpi.setByThreePoints(point_a, point_b, helper)
        plane = side_comp.constructionPlanes.add(cpi)
        plane.name = f"{name}_plane"
        helper_sk.isVisible = False
        plane.isLightBulbOn = False
        return plane

    def create_rail(name, start_pt, end_pt, model_points):
        helper = model_points[len(model_points) // 2]
        plane = create_three_point_plane(name, start_pt, end_pt, helper)
        sk = side_comp.sketches.add(plane)
        sk.name = name
        ps = sk.project(start_pt).item(0)
        pe = sk.project(end_pt).item(0)
        pts = adsk.core.ObjectCollection.create()
        pts.add(ps)
        for mp in model_points:
            msp = sk.modelToSketchSpace(mp)
            pts.add(sk.sketchPoints.add(P(msp.x, msp.y, 0)))
        pts.add(pe)
        spline = sk.sketchCurves.sketchFittedSplines.add(pts)
        sk.isVisible = False
        return spline

    c_top = P(x_stretcher, circle_cy, circle_cz + r_circle)
    e_top = P(x_leg, ellipse_cy + major_y * major_r, ellipse_cz + major_z * major_r)
    c_bottom = P(x_stretcher, circle_cy, circle_cz - r_circle)
    e_bottom = P(x_leg, ellipse_cy - major_y * major_r, ellipse_cz - major_z * major_r)
    c_front = P(x_stretcher, circle_cy - r_circle, circle_cz)
    e_front = P(x_leg, ellipse_cy + minor_y * minor_r, ellipse_cz + minor_z * minor_r)
    c_back = P(x_stretcher, circle_cy + r_circle, circle_cz)
    e_back = P(x_leg, ellipse_cy - minor_y * minor_r, ellipse_cz - minor_z * minor_r)

    rail_top = create_rail(
        f"{prefix}_rail_top", circle_top, ellipse_top,
        [
            P(16.833869, -44.783326, 26.326422),
            P(17.194234, -44.768132, 26.521255),
            P(17.376192, -44.760461, 27.259215),
        ])
    rail_bottom = create_rail(
        f"{prefix}_rail_bottom", circle_bottom, ellipse_bottom,
        [
            P(16.833869, -44.887482, 23.731492),
            P(17.268005, -44.923405, 23.570466),
            P(17.376192, -44.932357, 22.836364),
        ])
    create_rail(
        f"{prefix}_rail_right_visible", circle_front, ellipse_front,
        [
            P(16.978261, -46.190665, 25.0),
            P(17.430824, -46.274032, 25.0),
            P(17.8855, -46.380099, 25.0),
        ])
    create_rail(
        f"{prefix}_rail_left_visible", circle_back, ellipse_back,
        [
            P(16.978261, -43.486003, 25.0),
            P(17.430824, -43.421003, 25.0),
            P(17.8855, -43.333388, 25.0),
        ])

    loft_in = side_comp.features.loftFeatures.createInput(NEWBODY)
    loft_in.loftSections.add(circle_sk.profiles.item(0))
    loft_in.loftSections.add(ellipse_sk.profiles.item(0))
    loft_in.centerLineOrRails.addRail(rail_top)
    loft_in.centerLineOrRails.addRail(rail_bottom)
    loft_in.isSolid = True
    loft = side_comp.features.loftFeatures.add(loft_in)
    loft.name = "v22-location editable loft transition front_right in side_stretchers"
    proto = loft.bodies.item(0)
    proto.name = local_body_name
    circle_sk.isVisible = False
    ellipse_sk.isVisible = False

    def add_mirror(name, bodies, plane):
        coll = adsk.core.ObjectCollection.create()
        for body in bodies:
            coll.add(body)
        mirror_in = side_comp.features.mirrorFeatures.createInput(coll, plane)
        mirror_in.isCombine = False
        mirror = side_comp.features.mirrorFeatures.add(mirror_in)
        mirror.name = name
        return mirror

    left_mirror = add_mirror("mirror_stretcher_transition_left", [proto], side_comp.yZConstructionPlane)
    front_left = None
    for i in range(left_mirror.bodies.count):
        b = left_mirror.bodies.item(i)
        bb = b.boundingBox
        if (bb.minPoint.x + bb.maxPoint.x) / 2 < 0:
            front_left = b
            break
    if front_left is None:
        front_left = left_mirror.bodies.item(left_mirror.bodies.count - 1)
    front_left.name = "editable_loft_transition_front_left_v22loc_in_side_stretchers"

    back_mirror = add_mirror(
        "mirror_stretcher_transition_back_pair",
        [proto, front_left],
        side_comp.xZConstructionPlane)

    for i in range(side_comp.bRepBodies.count):
        body = side_comp.bRepBodies.item(i)
        if not body.name.startswith("editable_loft_transition_"):
            continue
        bb = body.boundingBox
        cx = (bb.minPoint.x + bb.maxPoint.x) / 2
        cy = (bb.minPoint.y + bb.maxPoint.y) / 2
        if cx > 0 and cy < 0:
            body.name = "editable_loft_transition_front_right_v22loc_in_side_stretchers"
        elif cx < 0 and cy < 0:
            body.name = "editable_loft_transition_front_left_v22loc_in_side_stretchers"
        elif cx > 0 and cy > 0:
            body.name = "editable_loft_transition_back_right_v22loc_in_side_stretchers"
        elif cx < 0 and cy > 0:
            body.name = "editable_loft_transition_back_left_v22loc_in_side_stretchers"


def _build_legs(root, legs_c, ev):
    """Phase 2: entasis-profile leg, splayed 3°, mirrored to 4 legs."""
    VI = adsk.core.ValueInput.createByString
    P3 = adsk.core.Point3D.create
    V3 = adsk.core.Vector3D.create
    NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    from helpers import sp

    # Construction plane at Y = -leg_dist_y / 2 (front row)
    leg_fr_pl = sp.off_plane(legs_c, legs_c.xZConstructionPlane,
                              "-leg_dist_y / 2", "legFR_Pl")

    sk = legs_c.sketches.add(leg_fr_pl)
    sk.name = "legFR_Sk"

    axis_x_mm = ev("leg_dist_x / 2") * 10.0  # cm → mm
    y_plane_cm = ev("-leg_dist_y / 2")
    z_top_cm = ev("to_floor - leg_to_top")
    z_bot_cm = ev("to_floor - leg_to_top - leg_length")

    # Build spline fit points in sketch space
    pt_coll = adsk.core.ObjectCollection.create()
    for r_mm, z_mm in LEG_ENTASIS:
        model_pt = P3((axis_x_mm + r_mm) / 10.0, y_plane_cm, z_mm / 10.0)
        sk_pt = sk.modelToSketchSpace(model_pt)
        pt_coll.add(P3(sk_pt.x, sk_pt.y, 0))
    spline = sk.sketchCurves.sketchFittedSplines.add(pt_coll)

    # Revolve axis — vertical line at axis_x, from z_top to z_bot
    axis_top_m = P3(axis_x_mm / 10.0, y_plane_cm, z_top_cm)
    axis_bot_m = P3(axis_x_mm / 10.0, y_plane_cm, z_bot_cm)
    a_top = sk.modelToSketchSpace(axis_top_m)
    a_bot = sk.modelToSketchSpace(axis_bot_m)
    axis_line = sk.sketchCurves.sketchLines.addByTwoPoints(
        P3(a_top.x, a_top.y, 0), P3(a_bot.x, a_bot.y, 0))
    # axis_line kept as solid edge so profile closes

    # Close profile: top connector (axis_top → spline first point)
    sk.sketchCurves.sketchLines.addByTwoPoints(
        axis_line.startSketchPoint, spline.startSketchPoint)
    # Bottom connector (axis_bot → spline last point)
    sk.sketchCurves.sketchLines.addByTwoPoints(
        axis_line.endSketchPoint, spline.endSketchPoint)

    prof = sk.profiles.item(0)

    # Revolve 360° around axis_line
    rev_inp = legs_c.features.revolveFeatures.createInput(prof, axis_line, NEW)
    rev_inp.setAngleExtent(False, VI("360 deg"))
    rev = legs_c.features.revolveFeatures.add(rev_inp)
    rev.name = "legFR_Revolve"
    leg_body = rev.bodies.item(0)
    leg_body.name = "leg_FR"

    # Splay: rotate around X-axis through leg top pivot
    ang_y = ev("angle_y")
    if abs(ang_y) > 1e-6:
        pivot = P3(axis_x_mm / 10.0, y_plane_cm, z_top_cm)
        rot = adsk.core.Matrix3D.create()
        rot.setToRotation(-ang_y, V3(1, 0, 0), pivot)
        mv_coll = adsk.core.ObjectCollection.create()
        mv_coll.add(leg_body)
        mv_inp = legs_c.features.moveFeatures.createInput2(mv_coll)
        mv_inp.defineAsFreeMove(rot)
        legs_c.features.moveFeatures.add(mv_inp).name = "legFR_Splay"

    # Foot fillet
    bot_face = sp.find_face(leg_body, "z", -1)
    if bot_face is not None:
        foot_edges = adsk.core.ObjectCollection.create()
        for i in range(bot_face.edges.count):
            foot_edges.add(bot_face.edges.item(i))
        if foot_edges.count > 0:
            fi = legs_c.features.filletFeatures.createInput()
            fi.addConstantRadiusEdgeSet(foot_edges, VI("feet_radius"), True)
            legs_c.features.filletFeatures.add(fi).name = "legFR_FootFil"

    # Mirror FR → FL across YZ plane
    mir_coll = adsk.core.ObjectCollection.create()
    mir_coll.add(leg_body)
    mir_inp = legs_c.features.mirrorFeatures.createInput(
        mir_coll, legs_c.yZConstructionPlane)
    legs_c.features.mirrorFeatures.add(mir_inp).name = "legFL_Mir"

    # Mirror all FR/FL across XZ plane → back legs
    all_legs = adsk.core.ObjectCollection.create()
    for i in range(legs_c.bRepBodies.count):
        all_legs.add(legs_c.bRepBodies.item(i))
    mir_inp2 = legs_c.features.mirrorFeatures.createInput(
        all_legs, legs_c.xZConstructionPlane)
    legs_c.features.mirrorFeatures.add(mir_inp2).name = "legsBack_Mir"



def _build_aprons(root, aprons_c, ev):
    """Phase 3: Arched-bottom apron at front, mirrored to back.

    Apron centered at X = leg_dist_x/2 (front) / -leg_dist_x/2 (back), with
    thickness = stretcher_thickness. Bottom is arched via 15-point spline
    (APRON_ARCH) with mirrored halves and straight bottom segments at each end.
    """
    VI = adsk.core.ValueInput.createByString
    P3 = adsk.core.Point3D.create
    NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    from helpers import sp

    # Plane at X = leg_dist_x / 2 (center of front apron)
    ap_pl = sp.off_plane(aprons_c, aprons_c.yZConstructionPlane,
                          "leg_dist_x / 2", "apronF_Pl")

    sk = aprons_c.sketches.add(ap_pl)
    sk.name = "apronF_Sk"

    x_plane_cm = ev("leg_dist_x / 2")
    y_half_cm = ev("stretcher_width / 2")
    z_top_cm = ev("to_floor - stretcher_to_top")
    z_bot_cm = ev("to_floor - stretcher_to_top - stretcher_height")

    # Helper: convert model (y, z) → sketch Point3D (x_plane fixed)
    def sk_xy(y_cm, z_cm):
        m = P3(x_plane_cm, y_cm, z_cm)
        s = sk.modelToSketchSpace(m)
        return P3(s.x, s.y, 0)

    # The arch shape comes from APRON_ARCH (15 pts). It covers Y from 0 to
    # -43.3cm with Z from 64.3cm down to 61.8cm. Original v21 apron bbox shows
    # Y extends to ±52.5, so past the arch shoulders (±43.3) the bottom is
    # straight at Z = 61.8.

    arch_shoulder_cm = abs(APRON_ARCH[-1][0]) / 10.0      # 43.3 cm
    scallop_bot_cm = abs(APRON_END_SCALLOP[0][0]) / 10.0  # 43.5 cm (just past shoulder)
    scallop_top_y_cm = abs(APRON_END_SCALLOP[-1][0]) / 10.0  # 50.75 cm
    arch_bot_z_cm = APRON_ARCH[-1][1] / 10.0              # 61.8 cm
    top_z_cm = APRON_END_SCALLOP[-1][1] / 10.0            # 69.3 cm

    # Profile vertices (model y, z): outline traces top edge + curved bottom
    # (no straight left/right sides — the scallops carry the board from the
    # top corners down to the arch shoulders and back up).
    ul = sk_xy(-y_half_cm, z_top_cm)            # upper-left corner
    ur = sk_xy(y_half_cm, z_top_cm)             # upper-right corner
    sl_top = sk_xy(-scallop_top_y_cm, z_top_cm) # left scallop top endpoint
    sr_top = sk_xy(scallop_top_y_cm, z_top_cm)
    sl_bot = sk_xy(-scallop_bot_cm, arch_bot_z_cm)  # left scallop bottom (near shoulder)
    sr_bot = sk_xy(scallop_bot_cm, arch_bot_z_cm)
    shl = sk_xy(-arch_shoulder_cm, arch_bot_z_cm)   # arch shoulder left
    shr = sk_xy(arch_shoulder_cm, arch_bot_z_cm)

    lines = sk.sketchCurves.sketchLines
    # Top edge (full width)
    lines.addByTwoPoints(ul, ur)
    # Tiny top flats connecting corners to scallop tops
    lines.addByTwoPoints(ur, sr_top)
    lines.addByTwoPoints(sl_top, ul)
    # Tiny bottom flats connecting scallop bottoms to arch shoulders
    lines.addByTwoPoints(sr_bot, shr)
    lines.addByTwoPoints(shl, sl_bot)

    # Left half arch: (0, peak) → ... → (-43.3, bot) — APRON_ARCH direct
    left_arch_pts = adsk.core.ObjectCollection.create()
    for y_mm, z_mm in APRON_ARCH:
        left_arch_pts.add(sk_xy(y_mm / 10.0, z_mm / 10.0))
    sk.sketchCurves.sketchFittedSplines.add(left_arch_pts)

    # Right half arch: (0, peak) → ... → (+43.3, bot) — APRON_ARCH mirrored in Y
    right_arch_pts = adsk.core.ObjectCollection.create()
    for y_mm, z_mm in APRON_ARCH:
        right_arch_pts.add(sk_xy(-y_mm / 10.0, z_mm / 10.0))
    sk.sketchCurves.sketchFittedSplines.add(right_arch_pts)

    # Left scallop: (-43.5, 61.8) → ... → (-50.75, 69.3) — APRON_END_SCALLOP direct
    left_scallop_pts = adsk.core.ObjectCollection.create()
    for y_mm, z_mm in APRON_END_SCALLOP:
        left_scallop_pts.add(sk_xy(y_mm / 10.0, z_mm / 10.0))
    sk.sketchCurves.sketchFittedSplines.add(left_scallop_pts)

    # Right scallop: mirror in Y
    right_scallop_pts = adsk.core.ObjectCollection.create()
    for y_mm, z_mm in APRON_END_SCALLOP:
        right_scallop_pts.add(sk_xy(-y_mm / 10.0, z_mm / 10.0))
    sk.sketchCurves.sketchFittedSplines.add(right_scallop_pts)

    # Extrude symmetric with full extent = stretcher_thickness
    prof = sp.smallest_profile(sk)
    # smallest_profile may pick a degenerate profile — use first instead
    if sk.profiles.count == 1:
        prof = sk.profiles.item(0)
    else:
        # Pick largest-area profile (the apron body, not stray regions)
        best, ba = None, 0
        for i in range(sk.profiles.count):
            a = sk.profiles.item(i).areaProperties().area
            if a > ba:
                ba = a
                best = sk.profiles.item(i)
        prof = best

    ex_inp = aprons_c.features.extrudeFeatures.createInput(prof, NEW)
    ex_inp.setSymmetricExtent(VI("stretcher_thickness"), True)
    ext = aprons_c.features.extrudeFeatures.add(ex_inp)
    ext.name = "apronF_Board"
    apron_body = ext.bodies.item(0)
    apron_body.name = "apron_F"

    # Edge fillet: roll over ALL edges of the apron (top rectangle corners
    # + the bottom arch/scallop curves that meet each end face).
    z_apron_top = ev("to_floor - stretcher_to_top")
    top_edges = adsk.core.ObjectCollection.create()
    bot_edges = adsk.core.ObjectCollection.create()
    for i in range(apron_body.edges.count):
        e = apron_body.edges.item(i)
        if e.length < 0.05:
            continue
        p1z = e.startVertex.geometry.z
        p2z = e.endVertex.geometry.z
        if abs(p1z - z_apron_top) < 0.01 and abs(p2z - z_apron_top) < 0.01:
            top_edges.add(e)
        elif not (abs(p1z - z_apron_top) < 0.01 or abs(p2z - z_apron_top) < 0.01):
            # Edge entirely below the top plane — a spline trace along the arch/scallop
            bot_edges.add(e)
    if top_edges.count > 0:
        fi = aprons_c.features.filletFeatures.createInput()
        fi.addConstantRadiusEdgeSet(top_edges, VI("apron_edge_fillet"), True)
        aprons_c.features.filletFeatures.add(fi).name = "apronF_FilTop"
    if bot_edges.count > 0:
        fi = aprons_c.features.filletFeatures.createInput()
        fi.addConstantRadiusEdgeSet(bot_edges, VI("apron_edge_fillet"), True)
        aprons_c.features.filletFeatures.add(fi).name = "apronF_FilBot"

    # Mirror to back apron across YZ (x=0) plane
    mir_coll = adsk.core.ObjectCollection.create()
    mir_coll.add(apron_body)
    mir_inp = aprons_c.features.mirrorFeatures.createInput(
        mir_coll, aprons_c.yZConstructionPlane)
    aprons_c.features.mirrorFeatures.add(mir_inp).name = "apronB_Mir"



def _offset_yz_plane(comp, ev, x_expr, name):
    """Create a YZ-parallel plane at X=x_expr."""
    VI = adsk.core.ValueInput.createByString
    planes = comp.constructionPlanes
    inp = planes.createInput()
    inp.setByOffset(comp.yZConstructionPlane, VI(x_expr))
    pl = planes.add(inp)
    pl.name = name
    return pl


def _closed_profile_on_yz(comp, ev, plane, pts_yz, name):
    """Sketch a closed profile on a YZ plane from model-space (y, z) points."""
    P3 = adsk.core.Point3D.create
    sk = comp.sketches.add(plane)
    sk.name = name
    lines = sk.sketchCurves.sketchLines
    sketch_pts = []
    x_cm = plane.geometry.origin.x
    for y_cm, z_cm in pts_yz:
        p = sk.modelToSketchSpace(P3(x_cm, y_cm, z_cm))
        sketch_pts.append(P3(p.x, p.y, 0))
    for i, p1 in enumerate(sketch_pts):
        lines.addByTwoPoints(p1, sketch_pts[(i + 1) % len(sketch_pts)])
    return sk.profiles.item(0)


def _extrude_profile(comp, profile, distance_expr, name, operation,
                     participant=None):
    VI = adsk.core.ValueInput.createByString
    inp = comp.features.extrudeFeatures.createInput(profile, operation)
    inp.setDistanceExtent(False, VI(distance_expr))
    if participant is not None:
        inp.participantBodies = [participant]
    ext = comp.features.extrudeFeatures.add(inp)
    ext.name = name
    return ext.bodies.item(0) if ext.bodies.count > 0 else participant


def _mirror_body(comp, body, plane, feature_name, body_name=None):
    coll = adsk.core.ObjectCollection.create()
    coll.add(body)
    mir_in = comp.features.mirrorFeatures.createInput(coll, plane)
    mir = comp.features.mirrorFeatures.add(mir_in)
    mir.name = feature_name
    mirrored = mir.bodies.item(0) if mir.bodies.count > 0 else None
    if mirrored and body_name:
        mirrored.name = body_name
    return mirrored


def _build_direct_slat_pair(comp, ev, *,
                            name_prefix,
                            y_center_expr,
                            body_x_half_expr,
                            tenon_x_half_expr,
                            z_top_expr,
                            h_expr,
                            body_y_expr,
                            tenon_y_expr,
                            tenon_z_expr,
                            angled=False,
                            tenon_at_bottom=False):
    """Build front slat from a YZ cross-section, then mirror body to back.

    For the outer slats the YZ section is a tilted rectangle: the top edge
    stays level for the dovetail blocks, and the lower edge follows leg splay.
    The tenon is created from the same tilted-section recipe before the leg
    and apron CUTs, so its mortise follows the final slat angle.
    """
    NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation

    z_top = ev(z_top_expr)
    h = ev(h_expr)
    z_bot = z_top - h
    y_center = -ev(y_center_expr)
    y_half = ev(body_y_expr) / 2.0
    tenon_y_half = ev(tenon_y_expr) / 2.0
    tenon_z = ev(tenon_z_expr)
    angle = ev("angle_y") if angled else 0.0
    slope = math.tan(angle)

    # Front side is negative Y; outward tilt shifts lower points farther
    # negative in Y while leaving the top edge level.
    top_outer = y_center - y_half
    top_inner = y_center + y_half
    bottom_shift = slope * h
    bot_outer = top_outer - bottom_shift
    bot_inner = top_inner - bottom_shift
    main_pts = [
        (top_outer, z_top),
        (top_inner, z_top),
        (bot_inner, z_bot),
        (bot_outer, z_bot),
    ]

    main_plane = _offset_yz_plane(
        comp, ev, f"-({body_x_half_expr})", f"{name_prefix}_F_MainYZ")
    main_prof = _closed_profile_on_yz(
        comp, ev, main_plane, main_pts, f"{name_prefix}_F_MainSk")
    main = _extrude_profile(
        comp, main_prof, f"2 * ({body_x_half_expr})",
        f"{name_prefix}_F_Main", NEW)
    main.name = f"{name_prefix}_F"

    # Right tenon. Outer-slat tenons sit at the lower end of the slat so the
    # exposed through-tenon reads as part of the tilted rail; inner tenons
    # keep the original centered-in-height placement.
    if tenon_at_bottom:
        z_ten_bot = z_bot
        z_ten_top = z_bot + tenon_z
        tenon_center_top = y_center - slope * (h - tenon_z)
        ten_top_outer = tenon_center_top - tenon_y_half
        ten_top_inner = tenon_center_top + tenon_y_half
        ten_bottom_shift = slope * tenon_z
        ten_bot_outer = ten_top_outer - ten_bottom_shift
        ten_bot_inner = ten_top_inner - ten_bottom_shift
    else:
        z_ten_bot = z_bot + (h - tenon_z) / 2.0
        z_ten_top = z_ten_bot + tenon_z
        ten_top_outer = y_center - tenon_y_half
        ten_top_inner = y_center + tenon_y_half
        ten_bot_outer = ten_top_outer
        ten_bot_inner = ten_top_inner

    tenon_pts = [
        (ten_top_outer, z_ten_top),
        (ten_top_inner, z_ten_top),
        (ten_bot_inner, z_ten_bot),
        (ten_bot_outer, z_ten_bot),
    ]
    tenon_plane = _offset_yz_plane(
        comp, ev, body_x_half_expr, f"{name_prefix}_F_TenRYZ")
    tenon_prof = _closed_profile_on_yz(
        comp, ev, tenon_plane, tenon_pts, f"{name_prefix}_F_TenRSk")
    ten_r = _extrude_profile(
        comp, tenon_prof, f"({tenon_x_half_expr}) - ({body_x_half_expr})",
        f"{name_prefix}_F_TenR", NEW)
    ten_r.name = f"{name_prefix}_F_TenR"

    ten_l = _mirror_body(
        comp, ten_r, comp.yZConstructionPlane,
        f"{name_prefix}_F_TenL_Mirror", f"{name_prefix}_F_TenL")

    tools = adsk.core.ObjectCollection.create()
    tools.add(ten_r)
    if ten_l:
        tools.add(ten_l)
    c_in = comp.features.combineFeatures.createInput(main, tools)
    c_in.operation = JOIN
    c_in.isKeepToolBodies = False
    join = comp.features.combineFeatures.add(c_in)
    join.name = f"{name_prefix}_F_JoinTenons"
    main.name = f"{name_prefix}_F"

    # Mirror the finished front slat to the back so the timeline has one
    # authoritative section and the mirrored partner stays exactly aligned.
    back = _mirror_body(
        comp, main, comp.xZConstructionPlane,
        f"{name_prefix}_B_Mirror", f"{name_prefix}_B")
    return main, back


def _build_outer_slats(root, comp, ev):
    """Phase 4a: outer cross-rails with tilted bodies and bottom tenons."""
    _build_direct_slat_pair(
        comp, ev,
        name_prefix="outerSlat",
        y_center_expr="leg_dist_y / 2",
        body_x_half_expr="slat_inner_x_half",
        tenon_x_half_expr="slat_outer_x_half",
        z_top_expr="to_floor - slat_top_gap",
        h_expr="slat_outer_h",
        body_y_expr="slat_thickness",
        tenon_y_expr="slat_tenon_y",
        tenon_z_expr="slat_outer_tenon_z",
        angled=True,
        tenon_at_bottom=True)


def _build_inner_slats(root, comp, ev):
    """Phase 4b: inner cross-rails, built once and mirrored to the back."""
    _build_direct_slat_pair(
        comp, ev,
        name_prefix="innerSlat",
        y_center_expr="leg_dist_y / 6",
        body_x_half_expr="slat_inner_x_half",
        tenon_x_half_expr="slat_inner_tenon_x_half",
        z_top_expr="to_floor - slat_top_gap",
        h_expr="slat_inner_h",
        body_y_expr="slat_thickness",
        tenon_y_expr="slat_tenon_y",
        tenon_z_expr="slat_inner_tenon_z",
        angled=False,
        tenon_at_bottom=False)



def _build_side_stretchers(root, comp, ev):
    """Phase 5: simple straight round cross-bar at splayed-leg Y, Z=side_stretcher_z.

    Matches v21 geometry (r=13mm, full-length extrude) — prior loft version
    didn't match the original.
    """
    VI = adsk.core.ValueInput.createByString
    P3 = adsk.core.Point3D.create
    NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    from helpers import sp

    sk = comp.sketches.add(comp.yZConstructionPlane)
    sk.name = "ssF_Sk"

    y_cm = ev("-leg_dist_y / 2 - ss_y_shift")
    z_cm = ev("side_stretcher_z")
    orient = sp.probe_orientations(sk, 0, y_cm, z_cm)

    m_ctr = P3(0, y_cm, z_cm)
    s_ctr = sk.modelToSketchSpace(m_ctr)
    r_cm = ev("side_stretcher_r")
    circle = sk.sketchCurves.sketchCircles.addByCenterRadius(
        P3(s_ctr.x, s_ctr.y, 0), r_cm)

    d = sk.sketchDimensions
    d.addRadialDimension(circle, P3(s_ctr.x + r_cm * 2.5, s_ctr.y, 0)
                          ).parameter.expression = "side_stretcher_r"
    d.addDistanceDimension(sk.originPoint, circle.centerSketchPoint,
                            orient['y'], P3(s_ctr.x, s_ctr.y - r_cm * 3, 0)
                            ).parameter.expression = "leg_dist_y / 2 + ss_y_shift"
    d.addDistanceDimension(sk.originPoint, circle.centerSketchPoint,
                            orient['z'], P3(s_ctr.x + r_cm * 4, s_ctr.y / 2, 0)
                            ).parameter.expression = "side_stretcher_z"

    prof = sk.profiles.item(0)
    ex_inp = comp.features.extrudeFeatures.createInput(prof, NEW)
    ex_inp.setSymmetricExtent(VI("leg_dist_x"), True)
    ext = comp.features.extrudeFeatures.add(ex_inp)
    ext.name = "ssF_Bar"
    body = ext.bodies.item(0)
    body.name = "sideStretcher_F"

    mir_coll = adsk.core.ObjectCollection.create()
    mir_coll.add(body)
    mir_inp = comp.features.mirrorFeatures.createInput(
        mir_coll, comp.xZConstructionPlane)
    comp.features.mirrorFeatures.add(mir_inp).name = "ssB_Mir"



def _build_dovetail_row(comp, ev, y_expr, name_prefix):
    """Build 1 rectangular block + X rectangular pattern at Y = y_expr.

    Block is a rectangular prism. Socket in slat is created later via CUT
    (the block acts as the tool).
    """
    VI = adsk.core.ValueInput.createByString
    P3 = adsk.core.Point3D.create
    NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    from helpers import sp

    pl = sp.off_plane(comp, comp.xYConstructionPlane, "to_floor", f"{name_prefix}_Pl")
    sk = comp.sketches.add(pl)
    sk.name = f"{name_prefix}_Sk"

    dw = ev("dovetail_width")
    dl = ev("dovetail_length")
    ds = ev("dovetail_space")
    n = int(round(ev("dovetail_quantity")))
    col_span = (n - 1) * (dw + ds) + dw
    y_cm = ev(y_expr)

    m_corner = P3(-col_span / 2, y_cm - dl / 2, ev("to_floor"))
    m_far = P3(-col_span / 2 + dw, y_cm + dl / 2, ev("to_floor"))

    s_c = sk.modelToSketchSpace(m_corner)
    s_f = sk.modelToSketchSpace(m_far)

    rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(
        P3(s_c.x, s_c.y, 0), P3(s_f.x, s_f.y, 0))
    gc = sk.geometricConstraints
    for i in range(rect.count):
        L = rect.item(i)
        p1 = L.startSketchPoint.geometry
        p2 = L.endSketchPoint.geometry
        if abs(p1.y - p2.y) < 1e-6:
            gc.addHorizontal(L)
        elif abs(p1.x - p2.x) < 1e-6:
            gc.addVertical(L)

    prof = sk.profiles.item(0)
    ex_inp = comp.features.extrudeFeatures.createInput(prof, NEW)
    ex_inp.setDistanceExtent(False, VI("-dovetail_thickness"))
    ext = comp.features.extrudeFeatures.add(ex_inp)
    ext.name = f"{name_prefix}_Block"
    body = ext.bodies.item(0)
    body.name = f"{name_prefix}_0"

    qty = n
    if qty > 1:
        b_coll = adsk.core.ObjectCollection.create()
        b_coll.add(body)
        pat_inp = comp.features.rectangularPatternFeatures.createInput(
            b_coll,
            comp.xConstructionAxis,
            VI(str(qty)),
            VI("dovetail_width + dovetail_space"),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        pat_inp.quantityTwo = VI("1")
        pat_inp.distanceTwo = VI("0 cm")
        pat = comp.features.rectangularPatternFeatures.add(pat_inp)
        pat.name = f"{name_prefix}_PatX"


def _build_dovetail_blocks(root, comp, ev):
    """Phase 6: 12 dovetail blocks — 3 per row, 4 rows (outer + inner × front + back)."""
    VI = adsk.core.ValueInput.createByString

    # Outer-front row (Y = -leg_dist_y/2)
    _build_dovetail_row(comp, ev, "-leg_dist_y / 2", "dtOut_F")
    # Inner-front row (Y = -leg_dist_y/6)
    _build_dovetail_row(comp, ev, "-leg_dist_y / 6", "dtIn_F")

    # Mirror all current bodies (outer + inner fronts) across XZ → back rows
    all_coll = adsk.core.ObjectCollection.create()
    for i in range(comp.bRepBodies.count):
        all_coll.add(comp.bRepBodies.item(i))
    mir_inp = comp.features.mirrorFeatures.createInput(
        all_coll, comp.xZConstructionPlane)
    comp.features.mirrorFeatures.add(mir_inp).name = "dt_MirBack"



def _build_joinery(root, legs_c, aprons_c, outer_c, inner_c, ss_c):
    """Phase 7: Cross-component CUTs for physical joinery.

    Creates mortises in legs where aprons, slats, and side stretchers pass
    through. Creates rectangular mortises in aprons for slat tenons.
    All tools are kept intact — only receiving bodies are modified.
    """
    from helpers import sp
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation

    aprons = [aprons_c.bRepBodies.item(i) for i in range(aprons_c.bRepBodies.count)]
    outer_slats = [outer_c.bRepBodies.item(i) for i in range(outer_c.bRepBodies.count)]
    side_stretchers = [ss_c.bRepBodies.item(i) for i in range(ss_c.bRepBodies.count)]
    leg_tools = aprons + outer_slats + side_stretchers

    # 1. Mortise each leg for all passing bodies
    for i in range(legs_c.bRepBodies.count):
        leg = legs_c.bRepBodies.item(i)
        try:
            sp.combine(leg, leg_tools, CUT, keep_tool=True, name=f"LegMortise_{i}")
        except Exception as e:
            print(f"  LegMortise {i} failed: {e}")

    # 2. Apron mortises for slat tenons — CUT aprons by slat tenons (keep slats)
    for i, apron in enumerate(aprons):
        try:
            sp.combine(apron, outer_slats, CUT, keep_tool=True, name=f"ApronOuterMortise_{i}")
        except Exception as e:
            print(f"  ApronOuterMortise {i} failed: {e}")
    # CUT aprons by inner slats too
    for i, apron in enumerate(aprons):
        try:
            inner_slats_local = [inner_c.bRepBodies.item(j)
                                 for j in range(inner_c.bRepBodies.count)]
            sp.combine(apron, inner_slats_local, CUT, keep_tool=True, name=f"ApronInnerMortise_{i}")
        except Exception as e:
            print(f"  ApronInnerMortise {i} failed: {e}")


def _build_dovetail_joinery(root, outer_c, inner_c, dt_c):
    """Sliding-dovetail sockets — CUT each slat by its dovetail blocks."""
    from helpers import sp
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation

    outer_slats = [outer_c.bRepBodies.item(i) for i in range(outer_c.bRepBodies.count)]
    inner_slats = [inner_c.bRepBodies.item(i) for i in range(inner_c.bRepBodies.count)]
    dt_blocks = [dt_c.bRepBodies.item(i) for i in range(dt_c.bRepBodies.count)]

    # Partition blocks by their Y position matching outer vs inner slats
    # Outer slats at Y=±leg_dist_y/2, inner slats at Y=±leg_dist_y/6.
    outer_dt = []
    inner_dt = []
    for b in dt_blocks:
        if b.name.startswith("dtOut_"):
            outer_dt.append(b)
        elif b.name.startswith("dtIn_"):
            inner_dt.append(b)

    for i, slat in enumerate(outer_slats):
        try:
            sp.combine(slat, outer_dt, CUT, keep_tool=True, name=f"OuterSlatDT_{i}")
        except Exception as e:
            print(f"  OuterSlatDT {i} failed: {e}")

    for i, slat in enumerate(inner_slats):
        try:
            sp.combine(slat, inner_dt, CUT, keep_tool=True, name=f"InnerSlatDT_{i}")
        except Exception as e:
            print(f"  InnerSlatDT {i} failed: {e}")


def _add_apron_end_fillets(aprons_c):
    """Restore the larger post-cut fillet at both ends of each apron."""
    VI = adsk.core.ValueInput.createByString
    edge_set = adsk.core.ObjectCollection.create()
    for bname in ("apron_F", "apron_F (1)"):
        body = aprons_c.bRepBodies.itemByName(bname)
        if body is None:
            continue
        bb = body.boundingBox
        for fi in range(body.faces.count):
            face = body.faces.item(fi)
            fb = face.boundingBox
            near_y_end = (
                fb.minPoint.y < bb.minPoint.y + 10.0 or
                fb.maxPoint.y > bb.maxPoint.y - 10.0)
            if not near_y_end or not (20.0 < face.area < 30.0):
                continue
            for ei in range(face.edges.count):
                edge = face.edges.item(ei)
                eb = edge.boundingBox
                at_x_side = (
                    abs(eb.minPoint.x - bb.minPoint.x) < 0.01 and
                    abs(eb.maxPoint.x - bb.minPoint.x) < 0.01) or (
                    abs(eb.minPoint.x - bb.maxPoint.x) < 0.01 and
                    abs(eb.maxPoint.x - bb.maxPoint.x) < 0.01)
                if at_x_side and edge.length > 5.0:
                    edge_set.add(edge)
    if edge_set.count:
        fin = aprons_c.features.filletFeatures.createInput()
        fin.addConstantRadiusEdgeSet(edge_set, VI("apron_end_fillet"), False)
        aprons_c.features.filletFeatures.add(fin).name = "apron_end_transition_fillets"



def _apply_textures():
    """Apply teak with per-body veneer + Box+grain at bbox-min on every body.

    Strategy (validated on slats — looks great):
      - Every veneer'd body: sp.apply_appearance("teak X") followed by an
        override of the body TMC: BoxTextureMapProjection with transform =
        _grain_transform(grain_vec) plus translation = body bbox-min. This
        keeps Fusion's Box+grain alignment (image-Y axis follows the body's
        long axis) but shifts the texture origin so the seam falls at a body
        edge, not body center.
      - Per-body veneers (teak a/b/c/d) give board variety where multiple
        copies of the same shape are visible side-by-side (legs, slats,
        aprons, stretchers).
      - Top body: tile veneer on the body for sides + edges; photo overrides
        ONLY the top BRepFace via face.appearance. Both share the body's
        Box+grain TMC. Top body bbox is 47x108 cm and the photo period is
        47x108 cm, so the +Z box projection paints the photo 1:1.
    """
    import adsk.core, adsk.fusion
    from helpers import sp

    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent

    def all_bodies(comp):
        out = []
        for i in range(comp.bRepBodies.count):
            out.append(comp.bRepBodies.item(i))
        for i in range(comp.occurrences.count):
            out.extend(all_bodies(comp.occurrences.item(i).component))
        return out

    CM_TO_IN = 1.0 / 2.54
    import os as _os
    _ASSETS = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "assets")
    FRAME_TEX = _os.path.join(_ASSETS, "teak_e_top_tone.jpg")
    ENDGRAIN_TEX = _os.path.join(_ASSETS, "teak_endgrain_dark.jpg")
    TOP_TEX = _os.path.join(_ASSETS, "teak_desk_top.jpg")
    TOP_TEX_ROT90 = _os.path.join(_ASSETS, "teak_desk_top_rot90.jpg")

    def texture_for(appn):
        if not appn:
            return None
        cp = adsk.core.ColorProperty.cast(
            appn.appearanceProperties.itemById("opaque_albedo"))
        if cp and cp.hasConnectedTexture:
            return cp.connectedTexture
        return None

    def set_bitmap(appn, image_path, scale_x_cm=None, scale_y_cm=None,
                   offset_x_cm=None, offset_y_cm=None):
        tex = texture_for(appn)
        if not tex:
            return
        try:
            tex.changeTextureImage(image_path)
        except Exception:
            pass
        bmp = tex.properties.itemById("unifiedbitmap_Bitmap")
        fp = adsk.core.FilenameProperty.cast(bmp) if bmp else None
        if fp and not fp.isReadOnly:
            fp.value = image_path
        for prop, val in (
            ("texture_RealWorldScaleX", scale_x_cm),
            ("texture_RealWorldScaleY", scale_y_cm),
            ("texture_RealWorldOffsetX", offset_x_cm),
            ("texture_RealWorldOffsetY", offset_y_cm),
        ):
            if val is None:
                continue
            p = tex.properties.itemById(prop)
            v = adsk.core.FloatProperty.cast(p) if p else None
            if v:
                v.value = val * CM_TO_IN

    def box_at_bbox_min(body, rotation=None):
        """Set body TMC = Box projection with given rotation + bbox-min translate.

        rotation=None means identity rotation — image axes align with world
        X/Y/Z directly (used on the top body so the photo's 47x108 cm content
        maps 1:1 onto the 47x108 cm top face). For other bodies pass
        sp._grain_transform(grain_vec) to rotate so image-Y axis follows the
        body's grain direction.

        bbox-min translate shifts texture origin to body's bbox-min corner so
        the seam falls at a body edge instead of the body's center.
        """
        if rotation is None:
            m = adsk.core.Matrix3D.create()
        else:
            m = rotation
        bb = body.boundingBox
        m.setCell(0, 3, bb.minPoint.x)
        m.setCell(1, 3, bb.minPoint.y)
        m.setCell(2, 3, bb.minPoint.z)
        ptmc = adsk.core.ProjectedTextureMapControl.cast(body.textureMapControl)
        if ptmc:
            ptmc.projectedTextureMapType = (
                adsk.core.ProjectedTextureMapTypes.BoxTextureMapProjection)
            ptmc.transform = m

    # ── 1. Per-body veneer assignment ──
    # Mix the four veneers across visually-grouped bodies so adjacent boards
    # don't repeat the same plank pattern.
    veneer_map = {
        # Top — surrounding sides + edges (photo overlays the top FACE only)
        "top":                   "teak b",
        # Frame parts — use the final color-graded Teak E bitmap everywhere
        # so top, apron, legs, slats, and stretchers read as one veneer set.
        "leg_FR":                "teak e",
        "leg_FR (1)":            "teak e",
        "leg_FR (2)":            "teak e",
        "leg_FR (1) (1)":        "teak e",
        "apron_F":               "teak e",
        "apron_F (1)":           "teak e",
        # Slats — front body is built directly, back body mirrors it; body
        # appearances are applied after mirror so both sides get valid TMC.
        "outerSlat_F":           "teak e",
        "outerSlat_B":           "teak e",
        "innerSlat_F":           "teak e",
        "innerSlat_B":           "teak e",
        "sideStretcher_F":       "teak e",
        "sideStretcher_F (1)":   "teak e",
        "editable_loft_transition_front_right_v22loc_in_side_stretchers": "teak e",
        "editable_loft_transition_front_left_v22loc_in_side_stretchers":  "teak e",
        "editable_loft_transition_back_right_v22loc_in_side_stretchers":  "teak e",
        "editable_loft_transition_back_left_v22loc_in_side_stretchers":   "teak e",
    }

    # Baseline default teak first — covers any body not in the veneer map
    # (dovetail blocks).
    sp.apply_appearance("teak")

    # Apply each species to the bodies that map to it.
    species_groups = {}
    for body_name, species in veneer_map.items():
        species_groups.setdefault(species, []).append(body_name)
    for species, names in species_groups.items():
        sp.apply_appearance(species, bodies=names)

    bowtie_names = [
        "BT_apron_F_v22_1",
        "BT_apron_F_v22_2",
        "BT_apron_F_v22_3",
        "BT_apron_F_v22_4",
        "BT_apron_F_v22_5",
    ]
    sp.apply_appearance("brazilian rosewood", bodies=bowtie_names)

    # Replace all frame Teak E source bitmaps with the color-graded version
    # captured from this desk. Keep each body-local scale from the fit pass.
    for body in all_bodies(root):
        if body.name in veneer_map and body.name != "top":
            set_bitmap(body.appearance, FRAME_TEX)
        for i in range(body.faces.count):
            fa = body.faces.item(i).appearance
            if not fa:
                continue
            lname = fa.name.lower()
            if "endgrain" in lname:
                set_bitmap(fa, ENDGRAIN_TEX, 14.986, 4.572)
            elif "teak" in lname and not body.name.startswith("BT_"):
                set_bitmap(fa, FRAME_TEX)

    # ── 2. Override TMC on every veneer'd body to put seam at bbox edge ──
    # The top body uses identity rotation so the photo's image-X/Y axes map
    # directly to world X/Y (1:1 on the 47x108 cm top face). All other bodies
    # use _grain_transform so image-Y follows the body's long axis (grain).
    for body in all_bodies(root):
        if body.name == "top":
            box_at_bbox_min(body, rotation=None)
        elif body.name in veneer_map:
            box_at_bbox_min(body, rotation=sp._grain_transform(sp._grain_vector(body)))

    # ── 2c. Per-body fit rule for veneer'd bodies.
    #    sp.fit_scale_y_cm picks scale_y per body — for low-resolution
    #    species (px/cm below threshold), it compresses the image so one
    #    period covers the body (down to 50% of the natural size minimum).
    #    For high-res species or bodies bigger than natural, it returns the
    #    natural value (no-op). Each affected body gets its own appearance
    #    copy so species-sharing bodies don't see each other's overrides.
    for body in all_bodies(root):
        if body.name not in veneer_map or body.name == "top":
            continue
        species = veneer_map[body.name]
        cfg = sp._SPECIES_TEXTURE.get(species)
        if not cfg:
            continue
        natural_cm = sp._natural_size_cm(cfg, "y")
        fit_cm = sp.fit_scale_y_cm(body, species)
        if fit_cm is None or abs(fit_cm - natural_cm) < 0.01:
            continue   # rule is a no-op for this body
        src_app = design.appearances.itemByName(f"SP_{species}")
        if not src_app:
            continue
        local_name = f"SP_{species}_{body.name}"
        local = design.appearances.itemByName(local_name)
        if not local:
            local = design.appearances.addByCopy(src_app, local_name)
        sp._apply_custom_texture(local, species, body=body)
        if species == "teak e":
            set_bitmap(local, FRAME_TEX)
        body.appearance = local
        bb = body.boundingBox

        # Recenter the TMC translate along the grain axis so the body fits
        # in the middle of one period — both seams (translate and translate+
        # period) end up just off the body, no visible seam at body edges.
        grain_vec = sp._grain_vector(body)
        comps = [abs(grain_vec.x), abs(grain_vec.y), abs(grain_vec.z)]
        gi = comps.index(max(comps))   # 0=x, 1=y, 2=z
        body_extents = [bb.maxPoint.x - bb.minPoint.x,
                         bb.maxPoint.y - bb.minPoint.y,
                         bb.maxPoint.z - bb.minPoint.z]
        body_min_along_grain = [bb.minPoint.x, bb.minPoint.y, bb.minPoint.z][gi]
        body_grain_cm = body_extents[gi]
        if fit_cm > body_grain_cm:
            new_translate = body_min_along_grain - (fit_cm - body_grain_cm) / 2.0
            ptmc = adsk.core.ProjectedTextureMapControl.cast(body.textureMapControl)
            if ptmc:
                m = ptmc.transform
                m.setCell(gi, 3, new_translate)
                ptmc.transform = m

    # ── 2d. Legs: Box projection with two specific tweaks.
    #    Two artifacts on the curved revolved leg surface need addressing:
    #      (a) Tile-period seams along Z — fixed by a much bigger scale_y
    #          buffer than the per-body fit's 50%. Use 200% (period =
    #          body × 3) so the period boundary is well off-body.
    #      (b) Box-projection direction transitions on the cylindrical
    #          surface (where +X-side projection meets +Y-side projection,
    #          etc) — fixed by ROTATING the TMC 45° around Z about each
    #          leg's XY center. The transitions then land at world ±45°
    #          which is on the leg's rounded curved surface where the
    #          shading hides them, instead of on the apparent X/Y faces.
    #      (c) scale_x bumped to 400% (period = max(x,y) × 5) for symmetry
    #          and to keep cross-grain wraps off body.
    #    Subagent confirmed visually with marker stripes on the source images.
    # Stretchers (round bars along world X) join legs in this block — they
    # share the curved-revolved-body recipe (Box + 45° rotation around the
    # body's long axis, scale_y = body × 3, scale_x = body cross × 5).
    # Earlier the stretchers used Cylindrical projection; the cylindrical
    # diagnostic (helpers/cylindrical_diagnostic) revealed scale_x/scale_y
    # were wired backwards from how we documented them and that WAngle is
    # ignored. Rather than fix the cylindrical recipe, we switch stretchers
    # to the same Box+rotation recipe legs use — fewer special cases and a
    # natural-bitmap result.
    def _is_curved_revolved(name):
        return name.startswith("leg_")
    for body in all_bodies(root):
        if not _is_curved_revolved(body.name):
            continue
        bb = body.boundingBox
        # The "long axis" differs between legs (Z) and stretchers (X).
        # Pick the axis with maximum body extent; that's the body's grain
        # direction and the rotation axis for the 45° trick.
        spans = [bb.maxPoint.x - bb.minPoint.x,
                  bb.maxPoint.y - bb.minPoint.y,
                  bb.maxPoint.z - bb.minPoint.z]
        long_axis_idx = spans.index(max(spans))   # 0=X, 1=Y, 2=Z
        long_ext = spans[long_axis_idx]
        cross_max = max(s for i, s in enumerate(spans) if i != long_axis_idx)
        long_min = [bb.minPoint.x, bb.minPoint.y, bb.minPoint.z][long_axis_idx]
        # The two cross-axis centers (used as the rotation pivot)
        cross_centers = [(bb.minPoint.x + bb.maxPoint.x) / 2.0,
                          (bb.minPoint.y + bb.maxPoint.y) / 2.0,
                          (bb.minPoint.z + bb.maxPoint.z) / 2.0]
        xy_max = cross_max
        cx = cross_centers[0]
        cy = cross_centers[1]
        CM_TO_IN_LOCAL = 1.0 / 2.54
        scale_y_cm = long_ext * 3.0    # 200% buffer along grain
        scale_x_cm = xy_max * 5.0       # 400% buffer cross-grain
        ap = body.appearance
        cp = adsk.core.ColorProperty.cast(
            ap.appearanceProperties.itemById("opaque_albedo"))
        if cp and cp.hasConnectedTexture:
            tex = cp.connectedTexture
            for prop, val in (
                ("texture_RealWorldScaleX", scale_x_cm * CM_TO_IN_LOCAL),
                ("texture_RealWorldScaleY", scale_y_cm * CM_TO_IN_LOCAL),
                ("texture_RealWorldOffsetX", 0.0),
                ("texture_RealWorldOffsetY", 0.0),
            ):
                p = tex.properties.itemById(prop)
                v = adsk.core.FloatProperty.cast(p) if p else None
                if v:
                    v.value = val
        # Box TMC: 45° rotation around Z about leg's XY center, plus Z translate
        # to push the period boundary off-body.
        m = adsk.core.Matrix3D.create()
        import math as _math_local
        # Rotation axis = body's long axis. Pivot = body center on the
        # two cross-axis directions; long-axis component = 0.
        long_axis_vec = [0.0, 0.0, 0.0]
        long_axis_vec[long_axis_idx] = 1.0
        pivot = list(cross_centers)
        pivot[long_axis_idx] = 0.0
        m.setToRotation(_math_local.pi / 4.0,
                         adsk.core.Vector3D.create(*long_axis_vec),
                         adsk.core.Point3D.create(*pivot))
        # Translate along the long axis so the period boundary lands off-body.
        m.setCell(long_axis_idx, 3,
                   long_min - (scale_y_cm - long_ext) / 2.0)
        ptmc = adsk.core.ProjectedTextureMapControl.cast(body.textureMapControl)
        if ptmc:
            ptmc.projectedTextureMapType = (
                adsk.core.ProjectedTextureMapTypes.BoxTextureMapProjection)
            ptmc.transform = m

    # ── 3. Top: photo on top BRepFace only ──
    # The photo (47x108 cm = body bbox) sits as a face-level appearance on
    # the flat top face. The body's Box+grain TMC (set in step 2) projects
    # it from +Z onto that face exactly once. Side faces and fillets keep
    # the body-level "teak b" tile.
    # Photo period matches the body's bbox extent for a 1:1 map.
    # The desk-top photo is sized in cm (per EXIF: 470 × 1080 mm).
    # Pixel dims 1434 × 3264 ⇒ 30 px/cm — above the 20 px/cm threshold so
    # the per-body fit rule is a no-op even when applied.
    custom_cfg = dict(sp._SPECIES_TEXTURE["teak"])
    custom_cfg["texture"] = "teak_desk_top.jpg"
    custom_cfg["scale_x"] = 47.0
    custom_cfg["scale_y"] = 108.0
    custom_cfg["natural_unit"] = "cm"
    custom_cfg["px_w"] = 1434
    custom_cfg["px_h"] = 3264
    sp._SPECIES_TEXTURE["teak_top"] = custom_cfg

    base = (design.appearances.itemByName("SP_teak b")
            or design.appearances.itemByName("SP_teak"))
    photo_app = design.appearances.itemByName("SP_teak_top")
    if not photo_app and base:
        photo_app = design.appearances.addByCopy(base, "SP_teak_top")
    if photo_app:
        sp._apply_custom_texture(photo_app, "teak_top")
        set_bitmap(photo_app, TOP_TEX, 47.0, 108.0)
        # _apply_custom_texture sets scale but not offsets. The body TMC
        # translate (set in box_at_bbox_min) shifts the projection origin,
        # but for the photo to land 1:1 on the 47x108 cm top face the
        # appearance also needs its RealWorldOffsetX/Y set to the top body's
        # bbox-min in INCHES. Without these the photo wraps and a seam
        # appears at the body center. Validated visually: knot pattern
        # lands in the upper-third of the top face exactly like the source
        # photo. UOffset/VOffset and WAngle stay at zero.
        cp = adsk.core.ColorProperty.cast(
            photo_app.appearanceProperties.itemById("opaque_albedo"))
        if cp and cp.hasConnectedTexture:
            tex = cp.connectedTexture
            # Find the top body so we can read its bbox.
            top_body = None
            for b in all_bodies(root):
                if b.name == "top":
                    top_body = b
                    break
            CM_TO_IN = 1.0 / 2.54
            offsets = {"texture_UOffset": 0.0, "texture_VOffset": 0.0,
                       "texture_WAngle": 0.0}
            if top_body is not None:
                bb = top_body.boundingBox
                offsets["texture_RealWorldOffsetX"] = bb.minPoint.x * CM_TO_IN
                offsets["texture_RealWorldOffsetY"] = bb.minPoint.y * CM_TO_IN
            else:
                offsets["texture_RealWorldOffsetX"] = 0.0
                offsets["texture_RealWorldOffsetY"] = 0.0
            for prop, val in offsets.items():
                p = tex.properties.itemById(prop)
                v = adsk.core.FloatProperty.cast(p) if p else None
                if v:
                    v.value = val

    if photo_app:
        # Apply photo to the TOP planar face only. The bottom face would need
        # a different texture orientation under the same body TMC (Box
        # projection mirrors image axes on the -Z box-side), and Fusion
        # renders the photo as default-blue on the -Z face when the photo's
        # RealWorldOffset is set for the +Z face. Bottom face inherits the
        # body-level "teak b" tile species — looks like real wood underside.
        for body in all_bodies(root):
            if body.name != "top":
                continue
            z_top = body.boundingBox.maxPoint.z
            best_face, best_area = None, -1.0
            for i in range(body.faces.count):
                f = body.faces.item(i)
                if not isinstance(f.geometry, adsk.core.Plane):
                    continue
                if abs(f.geometry.normal.z) < 0.9:
                    continue
                if abs(f.pointOnFace.z - z_top) < 0.5 and f.area > best_area:
                    best_face, best_area = f, f.area
            if best_face:
                best_face.appearance = photo_app

    # ── 3b. Top ears and top endgrain ──
    end_base = (design.appearances.itemByName("SP_teak e_endgrain")
                or design.appearances.itemByName("SP_teak_endgrain"))
    end_app = design.appearances.itemByName("SP_exact_v22_apron_endgrain_1777580846")
    if not end_app and end_base:
        end_app = design.appearances.addByCopy(
            end_base, "SP_exact_v22_apron_endgrain_1777580846")
    if end_app:
        set_bitmap(end_app, ENDGRAIN_TEX, 14.986, 4.572)

    if end_app:
        for body in all_bodies(root):
            if body.name != "top":
                continue
            bb = body.boundingBox
            for i in range(body.faces.count):
                f = body.faces.item(i)
                fb = f.boundingBox
                at_y_end = (
                    fb.minPoint.y <= bb.minPoint.y + 0.04 or
                    fb.maxPoint.y >= bb.maxPoint.y - 0.04)
                is_top_photo = (
                    isinstance(f.geometry, adsk.core.Plane) and
                    abs(f.geometry.normal.z) > 0.9 and
                    abs(f.pointOnFace.z - bb.maxPoint.z) < 0.5)
                if at_y_end and not is_top_photo:
                    f.appearance = end_app

    if photo_app:
        # Ear bodies: cylindrical projection with axis along Y (desk length)
        # at the bottom fillet center (x=±22, z=71.8) inside the edge.
        # Uses rotated desk photo so grain maps axially along desk length.
        # OffsetX=55cm pushes axial seam past desk ends.
        # OffsetY=11.75cm hides circumferential seam.
        ax_z = 71.8  # to_floor + top_edge_bot
        for body_name, app_name, ax_x in (
            ("ear_R", "SP_teak_desk_edge_ear_R_final", 22.0),
            ("ear_L", "SP_teak_desk_edge_ear_L_final", -22.0),
        ):
            ear = next((b for b in all_bodies(root) if b.name == body_name), None)
            if not ear:
                continue
            ear_app = design.appearances.itemByName(app_name)
            if not ear_app:
                ear_app = design.appearances.addByCopy(photo_app, app_name)
            set_bitmap(ear_app, TOP_TEX_ROT90, 110.0, 5.0, 55.0, 0.0)
            ear.appearance = ear_app
            for i in range(ear.faces.count):
                ear.faces.item(i).appearance = ear_app
            ptmc = adsk.core.ProjectedTextureMapControl.cast(ear.textureMapControl)
            if ptmc:
                ptmc.projectedTextureMapType = (
                    adsk.core.ProjectedTextureMapTypes.CylindricalTextureMapProjection)
                m = adsk.core.Matrix3D.create()
                sign = 1.0 if ax_x > 0 else -1.0
                # Axis along Y at (ax_x, ax_z): TMC rotates default Z-axis to Y
                m.setCell(0, 0, sign); m.setCell(0, 3, ax_x)
                m.setCell(1, 0, 0); m.setCell(1, 1, 0); m.setCell(1, 2, 1); m.setCell(1, 3, 0)
                m.setCell(2, 0, 0); m.setCell(2, 1, 1); m.setCell(2, 2, 0); m.setCell(2, 3, ax_z)
                ptmc.transform = m

    # ── 3c. Apron face matching ──
    # Box projection mirrors texture between +X and -X faces. Apply per-face
    # appearance copies with half-period offset on +X faces so all 4 large
    # apron side faces show the same grain region.
    for b_name in ("apron_F", "apron_F (1)"):
        ab = next((b for b in all_bodies(root) if b.name == b_name), None)
        if not ab:
            continue
        src_ap = ab.appearance
        for fi in range(ab.faces.count):
            f = ab.faces.item(fi)
            if not isinstance(f.geometry, adsk.core.Plane):
                continue
            if abs(f.geometry.normal.x) < 0.9 or f.area < 100:
                continue
            face_ap_name = f"SP_apron_face_{b_name}_{fi}"
            face_ap = design.appearances.itemByName(face_ap_name)
            if not face_ap:
                face_ap = design.appearances.addByCopy(src_ap, face_ap_name)
            set_bitmap(face_ap, FRAME_TEX)
            nx = f.geometry.normal.x
            if nx > 0:
                tex = texture_for(face_ap)
                if tex:
                    sx = tex.properties.itemById("texture_RealWorldScaleX")
                    if sx:
                        half = adsk.core.FloatProperty.cast(sx).value / 2
                        ox = tex.properties.itemById("texture_RealWorldOffsetX")
                        if ox:
                            adsk.core.FloatProperty.cast(ox).value = half
            f.appearance = face_ap

    # ── 4. Cleanup of stale per-body appearances ──
    # An earlier iteration created per-apron appearances (SP_teak c_apron_F,
    # SP_teak d_apron_F (1)) and assigned them to faces. Reverting to the
    # shared species appearance left those orphans behind, and a couple of
    # apron faces still hold dangling references to the deleted entities,
    # which Fusion renders as broken (a face appearance access raises
    # InternalValidationError). Sweep them: any face on a veneer'd body whose
    # appearance is unreadable gets reset to None so the body appearance
    # applies, then the orphan appearances are removed from the design.
    # Stale broken-face cleanup — sweep any face with a broken ref.
    for body in all_bodies(root):
        if body.name not in veneer_map:
            continue
        for i in range(body.faces.count):
            f = body.faces.item(i)
            try:
                ap = f.appearance
                _ = ap.name if ap else None
            except Exception:
                try:
                    f.appearance = None
                except Exception:
                    pass

    # ── 4b. Exposed outer-slat tenon endgrain ──
    # The through-tenons project just beyond the leg faces. Their exposed
    # X-end faces should show real-scale end grain, while the slat sides keep
    # the long-grain veneer.
    def apply_outer_slat_tenon_endgrain():
        end_app = (design.appearances.itemByName("SP_exact_v22_apron_endgrain_1777580846")
                   or design.appearances.itemByName("SP_teak_endgrain")
                   or design.appearances.itemByName("SP_teak a_endgrain")
                   or design.appearances.itemByName("SP_teak b_endgrain")
                   or design.appearances.itemByName("SP_teak c_endgrain")
                   or design.appearances.itemByName("SP_teak d_endgrain"))
        if not end_app:
            return
        set_bitmap(end_app, ENDGRAIN_TEX, 14.986, 4.572)
        p = design.userParameters.itemByName("slat_outer_tenon_z")
        ten_z = p.value if p else 2.8
        for body in all_bodies(root):
            if body.name not in ("outerSlat_F", "outerSlat_B"):
                continue
            bb = body.boundingBox
            z_limit = bb.minPoint.z + ten_z + 0.06
            for i in range(body.faces.count):
                f = body.faces.item(i)
                try:
                    fb = f.boundingBox
                    if not isinstance(f.geometry, adsk.core.Plane):
                        continue
                    normal = f.geometry.normal
                    if abs(normal.x) < 0.9:
                        continue
                    on_x_end = (
                        abs(fb.minPoint.x - bb.minPoint.x) < 0.03 or
                        abs(fb.maxPoint.x - bb.maxPoint.x) < 0.03)
                    in_tenon_height = (
                        fb.minPoint.z >= bb.minPoint.z - 0.06 and
                        fb.maxPoint.z <= z_limit)
                    if on_x_end and in_tenon_height and f.area > 0.1:
                        f.appearance = end_app
                except Exception:
                    pass

    apply_outer_slat_tenon_endgrain()

    # ── 5. Save applied appearance state to JSON sidecar ──
    # Records, per body: which image, projection, period (scale_x/y in cm),
    # buffer used, TMC translate. Lets a future session see what was applied
    # without re-running everything blindly.
    import json as _json, os as _os, datetime as _datetime
    state = {
        "applied_at": _datetime.datetime.now().isoformat(timespec="seconds"),
        "ppi_threshold_per_cm": 20.0,
        "default_seam_buffer": 0.10,
        "bodies": {},
    }
    for body in all_bodies(root):
        if body.name not in veneer_map and body.name != "top":
            continue
        species = veneer_map.get(body.name) or "teak_top"
        cfg = sp._SPECIES_TEXTURE.get(species, {})
        ap = body.appearance
        try:
            ap_name = ap.name if ap else None
        except Exception:
            ap_name = None
        cp = adsk.core.ColorProperty.cast(
            ap.appearanceProperties.itemById("opaque_albedo")) if ap else None
        sx_in = sy_in = wangle = None
        offx_in = offy_in = None
        if cp and cp.hasConnectedTexture:
            tex = cp.connectedTexture
            for key, prop in (("sx_in", "texture_RealWorldScaleX"),
                               ("sy_in", "texture_RealWorldScaleY"),
                               ("wangle", "texture_WAngle"),
                               ("offx_in", "texture_RealWorldOffsetX"),
                               ("offy_in", "texture_RealWorldOffsetY")):
                p = tex.properties.itemById(prop)
                v = adsk.core.FloatProperty.cast(p) if p else None
                if v:
                    locals_ref = {"sx_in": "sx_in", "sy_in": "sy_in",
                                  "wangle": "wangle",
                                  "offx_in": "offx_in", "offy_in": "offy_in"}
                    if key == "sx_in": sx_in = v.value
                    elif key == "sy_in": sy_in = v.value
                    elif key == "wangle": wangle = v.value
                    elif key == "offx_in": offx_in = v.value
                    elif key == "offy_in": offy_in = v.value
        ptmc = adsk.core.ProjectedTextureMapControl.cast(body.textureMapControl)
        proj = "?"
        translate = None
        if ptmc:
            tmap_type = ptmc.projectedTextureMapType
            BoxT = adsk.core.ProjectedTextureMapTypes.BoxTextureMapProjection
            CylT = adsk.core.ProjectedTextureMapTypes.CylindricalTextureMapProjection
            PlnT = adsk.core.ProjectedTextureMapTypes.PlanarTextureMapProjection
            proj = ("box" if tmap_type == BoxT else
                    "cylindrical" if tmap_type == CylT else
                    "planar" if tmap_type == PlnT else "other")
            t = ptmc.transform
            translate = [round(t.getCell(0, 3), 3),
                          round(t.getCell(1, 3), 3),
                          round(t.getCell(2, 3), 3)]
        bb = body.boundingBox
        body_extents = [round(bb.maxPoint.x - bb.minPoint.x, 2),
                         round(bb.maxPoint.y - bb.minPoint.y, 2),
                         round(bb.maxPoint.z - bb.minPoint.z, 2)]
        natural_y_cm = sp._natural_size_cm(cfg, "y")
        scale_y_cm = sy_in * 2.54 if isinstance(sy_in, float) else None
        # Buffer = (scale_y_cm - body_grain_cm) / body_grain_cm; only when fitted
        body_grain_cm = max(body_extents)
        buffer = None
        if isinstance(scale_y_cm, float) and natural_y_cm > 0:
            if abs(scale_y_cm - natural_y_cm) > 0.01:
                # not natural — was fitted
                buffer = round((scale_y_cm - body_grain_cm) / body_grain_cm, 4)
        state["bodies"][body.name] = {
            "image": cfg.get("texture"),
            "species": species,
            "appearance": ap_name,
            "projection": proj,
            "tmc_translate_cm": translate,
            "scale_x_in": round(sx_in, 4) if isinstance(sx_in, float) else None,
            "scale_y_in": round(sy_in, 4) if isinstance(sy_in, float) else None,
            "scale_x_cm": round(sx_in * 2.54, 3) if isinstance(sx_in, float) else None,
            "scale_y_cm": round(sy_in * 2.54, 3) if isinstance(sy_in, float) else None,
            "wangle_rad": round(wangle, 4) if isinstance(wangle, float) else None,
            "offset_in": [round(offx_in, 4) if isinstance(offx_in, float) else None,
                           round(offy_in, 4) if isinstance(offy_in, float) else None],
            "natural_y_cm": round(natural_y_cm, 2),
            "body_extents_cm": body_extents,
            "buffer_used": buffer,
        }
    script_file = globals().get(
        "__file__", "/Users/frankzha/shopprentice-projects/teak-desk/teak_desk.py")
    project_dir = _os.path.dirname(_os.path.abspath(script_file))
    sidecar_path = _os.path.join(project_dir, "appearance_state.json")
    with open(sidecar_path, "w") as f:
        _json.dump(state, f, indent=2)
    print(f"Wrote appearance state → {sidecar_path}")
