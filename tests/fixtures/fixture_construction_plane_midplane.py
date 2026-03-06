"""Fixture: MidPlane construction plane + sketch + extrude.

Tests MidPlane construction plane (between two offset planes),
then sketching and extruding on the resulting midplane.
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

    params.add("offset_a", adsk.core.ValueInput.createByString("2 cm"), "cm", "Plane A offset")
    params.add("offset_b", adsk.core.ValueInput.createByString("8 cm"), "cm", "Plane B offset")
    params.add("plate_w", adsk.core.ValueInput.createByString("6 cm"), "cm", "Plate width")
    params.add("plate_d", adsk.core.ValueInput.createByString("4 cm"), "cm", "Plate depth")
    params.add("plate_h", adsk.core.ValueInput.createByString("1 cm"), "cm", "Plate height")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                     else design.unitsManager.evaluateExpression(e, "cm"))

    # ── Plane A: offset from XY at 2 cm ──
    cp_inp_a = root.constructionPlanes.createInput()
    cp_inp_a.setByOffset(root.xYConstructionPlane, adsk.core.ValueInput.createByString("offset_a"))
    plane_a = root.constructionPlanes.add(cp_inp_a)
    plane_a.name = "PlaneA"

    # ── Plane B: offset from XY at 8 cm ──
    cp_inp_b = root.constructionPlanes.createInput()
    cp_inp_b.setByOffset(root.xYConstructionPlane, adsk.core.ValueInput.createByString("offset_b"))
    plane_b = root.constructionPlanes.add(cp_inp_b)
    plane_b.name = "PlaneB"

    # ── MidPlane between Plane A and Plane B (should be at Z = 5 cm) ──
    cp_inp_mid = root.constructionPlanes.createInput()
    cp_inp_mid.setByTwoPlanes(plane_a, plane_b)
    mid_plane = root.constructionPlanes.add(cp_inp_mid)
    mid_plane.name = "MidPlane"

    # ── Sketch on MidPlane ──
    sk = root.sketches.add(mid_plane)
    sk.name = "MidPlateProfile"
    w, d = ev("plate_w"), ev("plate_d")
    rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(P(0, 0, 0), P(w, d, 0))
    gc = sk.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    dm = sk.sketchDimensions
    dm.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(w/2, -1, 0)).parameter.expression = "plate_w"
    dm.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(w+1, d/2, 0)).parameter.expression = "plate_d"

    # ── Extrude on MidPlane ──
    inp = root.features.extrudeFeatures.createInput(sk.profiles.item(0), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("plate_h"))
    ext = root.features.extrudeFeatures.add(inp)
    ext.name = "MidPlateExtrude"
    ext.bodies.item(0).name = "MidPlate"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
