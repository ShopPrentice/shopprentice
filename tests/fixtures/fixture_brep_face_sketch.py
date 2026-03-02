"""Fixture: Sketch on BRepFace.

Tests the BRepFace → construction plane conversion path. Creates a box,
then sketches a mortise pocket on the top face and CUTs it.
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
    params.add("mortise_w", adsk.core.ValueInput.createByString("4 cm"), "cm", "Mortise width")
    params.add("mortise_d", adsk.core.ValueInput.createByString("2 cm"), "cm", "Mortise depth")
    params.add("mortise_depth", adsk.core.ValueInput.createByString("1.5 cm"), "cm", "Mortise cut depth")
    params.add("mortise_inset", adsk.core.ValueInput.createByString("3 cm"), "cm", "Mortise inset from end")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                     else design.unitsManager.evaluateExpression(e, "cm"))

    # ── Sketch 1: rail profile on XY ──
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
    inp = root.features.extrudeFeatures.createInput(sk1.profiles.item(0), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("rail_h"))
    ext = root.features.extrudeFeatures.add(inp)
    ext.name = "RailExtrude"
    rail = ext.bodies.item(0)
    rail.name = "Rail"

    # ── Find top face (z = rail_h) for sketch ──
    h = ev("rail_h")
    top_face = None
    for i in range(rail.faces.count):
        f = rail.faces.item(i)
        if isinstance(f.geometry, adsk.core.Plane) and abs(f.geometry.normal.z) > 0.9:
            if top_face is None or f.pointOnFace.z > top_face.pointOnFace.z:
                top_face = f

    # ── Sketch 2: mortise on top face (BRepFace sketch) ──
    sk2 = root.sketches.add(top_face)
    sk2.name = "MortiseProfile"

    # Use modelToSketchSpace for positioning
    mw, md = ev("mortise_w"), ev("mortise_d")
    inset = ev("mortise_inset")
    pt = sk2.modelToSketchSpace(P(inset, (d - md) / 2, h))
    ox, oy = pt.x, pt.y
    pt2 = sk2.modelToSketchSpace(P(inset + mw, (d + md) / 2, h))
    ex, ey = pt2.x, pt2.y

    rect2 = sk2.sketchCurves.sketchLines.addTwoPointRectangle(P(ox, oy, 0), P(ex, ey, 0))
    gc2 = sk2.geometricConstraints
    gc2.addHorizontal(rect2[0]); gc2.addHorizontal(rect2[2])
    gc2.addVertical(rect2[1]); gc2.addVertical(rect2[3])
    dm2 = sk2.sketchDimensions
    dm2.addDistanceDimension(rect2[0].startSketchPoint, rect2[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P((ox+ex)/2, oy - 1, 0)).parameter.expression = "mortise_w"
    dm2.addDistanceDimension(rect2[1].startSketchPoint, rect2[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(ex + 1, (oy+ey)/2, 0)).parameter.expression = "mortise_d"

    # Select the smallest profile (the mortise rect, not the surrounding face)
    best_pi, best_area = 0, float('inf')
    for pi in range(sk2.profiles.count):
        bb = sk2.profiles.item(pi).boundingBox
        area = abs(bb.maxPoint.x - bb.minPoint.x) * abs(bb.maxPoint.y - bb.minPoint.y)
        if area < best_area:
            best_area = area
            best_pi = pi

    # ── Extrude: mortise CUT ──
    inp2 = root.features.extrudeFeatures.createInput(sk2.profiles.item(best_pi), CUT)
    inp2.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(
            adsk.core.ValueInput.createByString("mortise_depth")),
        adsk.fusion.ExtentDirections.NegativeExtentDirection)
    inp2.participantBodies = [rail]
    ext2 = root.features.extrudeFeatures.add(inp2)
    ext2.name = "MortiseCut"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
