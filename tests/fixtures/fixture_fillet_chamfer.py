"""Fixture: Fillet and Chamfer features.

Tests constant radius fillet and equal distance chamfer.
Expected: These will likely FAIL until edge capture/selection is solved.
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

    params.add("box_w", adsk.core.ValueInput.createByString("8 cm"), "cm", "Box width")
    params.add("box_d", adsk.core.ValueInput.createByString("6 cm"), "cm", "Box depth")
    params.add("box_h", adsk.core.ValueInput.createByString("4 cm"), "cm", "Box height")
    params.add("fillet_r", adsk.core.ValueInput.createByString("0.5 cm"), "cm", "Fillet radius")
    params.add("chamfer_d", adsk.core.ValueInput.createByString("0.3 cm"), "cm", "Chamfer distance")

    ev = lambda e: params.itemByName(e).value if params.itemByName(e) else design.unitsManager.evaluateExpression(e, "cm")

    # ── Sketch: box profile ──
    sk = root.sketches.add(root.xYConstructionPlane)
    sk.name = "BoxProfile"
    w, d = ev("box_w"), ev("box_d")
    rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(P(0, 0, 0), P(w, d, 0))
    gc = sk.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    dm = sk.sketchDimensions
    dm.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(w/2, -1, 0)).parameter.expression = "box_w"
    dm.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(w+1, d/2, 0)).parameter.expression = "box_d"

    # ── Extrude ──
    inp = root.features.extrudeFeatures.createInput(sk.profiles.item(0), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("box_h"))
    ext = root.features.extrudeFeatures.add(inp)
    ext.name = "BoxExtrude"
    box = ext.bodies.item(0)
    box.name = "Box"

    # ── Fillet: top edges (z = box_h) ──
    h = ev("box_h")
    fillet_edges = adsk.core.ObjectCollection.create()
    for i in range(box.edges.count):
        e = box.edges.item(i)
        sv, ev2 = e.startVertex.geometry, e.endVertex.geometry
        if abs(sv.z - h) < 0.01 and abs(ev2.z - h) < 0.01:
            fillet_edges.add(e)

    fillet_inp = root.features.filletFeatures.createInput()
    fillet_inp.addConstantRadiusEdgeSet(fillet_edges, adsk.core.ValueInput.createByString("fillet_r"), True)
    fillet = root.features.filletFeatures.add(fillet_inp)
    fillet.name = "TopFillet"

    # ── Chamfer: bottom edges (z = 0) ──
    chamfer_edges = adsk.core.ObjectCollection.create()
    for i in range(box.edges.count):
        e = box.edges.item(i)
        sv, ev2 = e.startVertex.geometry, e.endVertex.geometry
        if abs(sv.z) < 0.01 and abs(ev2.z) < 0.01:
            chamfer_edges.add(e)

    chamfer_inp = root.features.chamferFeatures.createInput2()
    chamfer_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
        chamfer_edges, adsk.core.ValueInput.createByString("chamfer_d"), True)
    chamfer = root.features.chamferFeatures.add(chamfer_inp)
    chamfer.name = "BottomChamfer"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
