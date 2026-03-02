"""Fixture: Construction plane offset + sketch + extrude.

Tests offset construction plane creation from a non-origin base plane,
then sketching and extruding on it. Exercises chained plane references.
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

    params.add("offset_1", adsk.core.ValueInput.createByString("5 cm"), "cm", "First offset")
    params.add("offset_2", adsk.core.ValueInput.createByString("3 cm"), "cm", "Second offset")
    params.add("plate_w", adsk.core.ValueInput.createByString("8 cm"), "cm", "Plate width")
    params.add("plate_d", adsk.core.ValueInput.createByString("6 cm"), "cm", "Plate depth")
    params.add("plate_h", adsk.core.ValueInput.createByString("1 cm"), "cm", "Plate height")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                     else design.unitsManager.evaluateExpression(e, "cm"))

    # ── Construction plane 1: offset from XY ──
    cp_inp = root.constructionPlanes.createInput()
    cp_inp.setByOffset(root.xYConstructionPlane, adsk.core.ValueInput.createByString("offset_1"))
    cp1 = root.constructionPlanes.add(cp_inp)
    cp1.name = "Shelf1"

    # ── Sketch on construction plane 1 ──
    sk1 = root.sketches.add(cp1)
    sk1.name = "Plate1Profile"
    w, d = ev("plate_w"), ev("plate_d")
    rect = sk1.sketchCurves.sketchLines.addTwoPointRectangle(P(0, 0, 0), P(w, d, 0))
    gc = sk1.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    dm = sk1.sketchDimensions
    dm.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(w/2, -1, 0)).parameter.expression = "plate_w"
    dm.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(w+1, d/2, 0)).parameter.expression = "plate_d"

    # ── Extrude on plane 1 ──
    inp1 = root.features.extrudeFeatures.createInput(sk1.profiles.item(0), NEWBODY)
    inp1.setDistanceExtent(False, adsk.core.ValueInput.createByString("plate_h"))
    ext1 = root.features.extrudeFeatures.add(inp1)
    ext1.name = "Plate1Extrude"
    ext1.bodies.item(0).name = "Plate1"

    # ── Construction plane 2: offset from plane 1 (chained) ──
    cp_inp2 = root.constructionPlanes.createInput()
    cp_inp2.setByOffset(cp1, adsk.core.ValueInput.createByString("offset_2"))
    cp2 = root.constructionPlanes.add(cp_inp2)
    cp2.name = "Shelf2"

    # ── Sketch on construction plane 2 ──
    sk2 = root.sketches.add(cp2)
    sk2.name = "Plate2Profile"
    rect2 = sk2.sketchCurves.sketchLines.addTwoPointRectangle(P(0, 0, 0), P(w, d, 0))
    gc2 = sk2.geometricConstraints
    gc2.addHorizontal(rect2[0]); gc2.addHorizontal(rect2[2])
    gc2.addVertical(rect2[1]); gc2.addVertical(rect2[3])
    dm2 = sk2.sketchDimensions
    dm2.addDistanceDimension(rect2[0].startSketchPoint, rect2[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(w/2, -1, 0)).parameter.expression = "plate_w"
    dm2.addDistanceDimension(rect2[1].startSketchPoint, rect2[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(w+1, d/2, 0)).parameter.expression = "plate_d"

    # ── Extrude on plane 2 ──
    inp2 = root.features.extrudeFeatures.createInput(sk2.profiles.item(0), NEWBODY)
    inp2.setDistanceExtent(False, adsk.core.ValueInput.createByString("plate_h"))
    ext2 = root.features.extrudeFeatures.add(inp2)
    ext2.name = "Plate2Extrude"
    ext2.bodies.item(0).name = "Plate2"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
