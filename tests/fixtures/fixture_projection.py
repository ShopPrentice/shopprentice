"""Fixture: Sketch with projected body edges.

Tests sk.project(edge) for reference geometry, then dimensioning from
the projected edge to drawn geometry. Common pattern in joinery:
project a body edge, draw a shoulder line offset from it, CUT.
"""
import adsk.core, adsk.fusion


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters

    P = adsk.core.Point3D.create
    NEWBODY = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation

    params.add("rail_w", adsk.core.ValueInput.createByString("20 cm"), "cm", "Rail width")
    params.add("rail_d", adsk.core.ValueInput.createByString("5 cm"), "cm", "Rail depth")
    params.add("rail_h", adsk.core.ValueInput.createByString("3 cm"), "cm", "Rail height")
    params.add("shoulder_w", adsk.core.ValueInput.createByString("1 cm"), "cm", "Tenon shoulder width")
    params.add("tenon_depth", adsk.core.ValueInput.createByString("1 cm"), "cm", "Tenon depth")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                     else design.unitsManager.evaluateExpression(e, "cm"))

    # ── Sketch 1: rail profile ──
    sk1 = root.sketches.add(root.xYConstructionPlane)
    sk1.name = "RailProfile"
    w, d = ev("rail_w"), ev("rail_d")
    rect = sk1.sketchCurves.sketchLines.addTwoPointRectangle(P(0, 0, 0), P(w, d, 0))
    gc = sk1.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    dm = sk1.sketchDimensions
    dm.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(w/2, -1, 0)).parameter.expression = "rail_w"
    dm.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(w+1, d/2, 0)).parameter.expression = "rail_d"

    # ── Extrude: rail ──
    inp1 = root.features.extrudeFeatures.createInput(sk1.profiles.item(0), NEWBODY)
    inp1.setDistanceExtent(False, adsk.core.ValueInput.createByString("rail_h"))
    ext1 = root.features.extrudeFeatures.add(inp1)
    ext1.name = "RailExtrude"
    rail = ext1.bodies.item(0)
    rail.name = "Rail"

    # ── Find the right-end face (x = rail_w) for the tenon shoulder sketch ──
    h = ev("rail_h")
    end_face = None
    for i in range(rail.faces.count):
        f = rail.faces.item(i)
        if isinstance(f.geometry, adsk.core.Plane) and abs(f.geometry.normal.x) > 0.9:
            if end_face is None or f.pointOnFace.x > end_face.pointOnFace.x:
                end_face = f

    # ── Construction plane at the end face (avoid BRepFace auto-projections) ──
    cp_inp = root.constructionPlanes.createInput()
    cp_inp.setByOffset(root.yZConstructionPlane, adsk.core.ValueInput.createByString("rail_w"))
    end_plane = root.constructionPlanes.add(cp_inp)
    end_plane.name = "EndPlane"

    # ── Sketch 2: tenon shoulder on end plane ──
    # Project the top edge of the rail for reference
    sk2 = root.sketches.add(end_plane)
    sk2.name = "ShoulderProfile"

    # Find the top edge at x=rail_w (horizontal edge at z=rail_h on the end face)
    top_edge = None
    for i in range(rail.edges.count):
        e = rail.edges.item(i)
        sv, ev2 = e.startVertex.geometry, e.endVertex.geometry
        if (abs(sv.x - w) < 0.01 and abs(ev2.x - w) < 0.01 and
            abs(sv.z - h) < 0.01 and abs(ev2.z - h) < 0.01):
            top_edge = e
            break

    # Project the top edge
    proj = sk2.project(top_edge)

    # Find the projected line
    proj_line = None
    for ci in range(proj.count):
        c = proj.item(ci)
        if adsk.fusion.SketchLine.cast(c):
            proj_line = adsk.fusion.SketchLine.cast(c)
            break

    # Draw the shoulder line: offset down by shoulder_w from the projected top edge
    # On YZ plane: sketch X = model Y, sketch Y = model Z
    sw = ev("shoulder_w")
    shoulder_y = h - sw  # model Z coordinate of shoulder
    pt_s = sk2.modelToSketchSpace(P(w, 0, shoulder_y))
    pt_e = sk2.modelToSketchSpace(P(w, d, shoulder_y))
    shoulder_line = sk2.sketchCurves.sketchLines.addByTwoPoints(
        P(pt_s.x, pt_s.y, 0), P(pt_e.x, pt_e.y, 0))
    shoulder_line.isConstruction = False

    # Draw the bottom line and sides to close the profile
    pt_bl = sk2.modelToSketchSpace(P(w, 0, 0))
    pt_br = sk2.modelToSketchSpace(P(w, d, 0))
    bottom_line = sk2.sketchCurves.sketchLines.addByTwoPoints(
        P(pt_bl.x, pt_bl.y, 0), P(pt_br.x, pt_br.y, 0))
    left_line = sk2.sketchCurves.sketchLines.addByTwoPoints(
        shoulder_line.startSketchPoint, bottom_line.startSketchPoint)
    right_line = sk2.sketchCurves.sketchLines.addByTwoPoints(
        bottom_line.endSketchPoint, shoulder_line.endSketchPoint)

    # Constraints
    gc2 = sk2.geometricConstraints
    gc2.addHorizontal(shoulder_line)
    gc2.addHorizontal(bottom_line)
    gc2.addVertical(left_line)
    gc2.addVertical(right_line)

    # Dimension: shoulder width (from projected top edge to shoulder line)
    dm2 = sk2.sketchDimensions
    dm2.addDistanceDimension(proj_line.startSketchPoint, shoulder_line.startSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(pt_s.x - 1, (pt_s.y + sk2.modelToSketchSpace(P(w, 0, h)).y) / 2, 0)
    ).parameter.expression = "shoulder_w"

    # Select the shoulder profile (rectangle below the projected edge)
    best_pi, best_area = 0, float('inf')
    for pi in range(sk2.profiles.count):
        bb = sk2.profiles.item(pi).boundingBox
        area = abs(bb.maxPoint.x - bb.minPoint.x) * abs(bb.maxPoint.y - bb.minPoint.y)
        if area < best_area:
            best_area = area
            best_pi = pi

    # ── Extrude: tenon shoulder CUT ──
    inp2 = root.features.extrudeFeatures.createInput(sk2.profiles.item(best_pi), CUT)
    inp2.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(
            adsk.core.ValueInput.createByString("tenon_depth")),
        adsk.fusion.ExtentDirections.NegativeExtentDirection)
    inp2.participantBodies = [rail]
    ext2 = root.features.extrudeFeatures.add(inp2)
    ext2.name = "ShoulderCut"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
