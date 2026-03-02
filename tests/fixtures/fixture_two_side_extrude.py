"""Fixture: Two-sided extrude.

Tests TwoSides extent type with different distances on each side,
and taper angles on both sides.
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

    params.add("web_w", adsk.core.ValueInput.createByString("12 cm"), "cm", "Web width")
    params.add("web_d", adsk.core.ValueInput.createByString("6 cm"), "cm", "Web depth")
    params.add("ext_up", adsk.core.ValueInput.createByString("4 cm"), "cm", "Extent up")
    params.add("ext_down", adsk.core.ValueInput.createByString("2 cm"), "cm", "Extent down")
    params.add("taper_up", adsk.core.ValueInput.createByString("3 deg"), "deg", "Taper up")
    params.add("taper_down", adsk.core.ValueInput.createByString("5 deg"), "deg", "Taper down")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                     else design.unitsManager.evaluateExpression(e, "cm"))

    # ── Sketch on XZ plane (so two-sided goes +Y and -Y) ──
    sk = root.sketches.add(root.xZConstructionPlane)
    sk.name = "WebProfile"
    w, d = ev("web_w"), ev("web_d")
    rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(P(0, 0, 0), P(w, d, 0))
    gc = sk.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    dm = sk.sketchDimensions
    dm.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(w/2, -1, 0)).parameter.expression = "web_w"
    dm.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(w+1, d/2, 0)).parameter.expression = "ext_up + ext_down"

    # ── Two-sided extrude with taper on both sides ──
    inp = root.features.extrudeFeatures.createInput(sk.profiles.item(0), NEWBODY)
    inp.setTwoSidesExtent(
        adsk.fusion.DistanceExtentDefinition.create(
            adsk.core.ValueInput.createByString("ext_up")),
        adsk.fusion.DistanceExtentDefinition.create(
            adsk.core.ValueInput.createByString("ext_down")),
        adsk.core.ValueInput.createByString("taper_up"),
        adsk.core.ValueInput.createByString("taper_down"),
    )
    ext = root.features.extrudeFeatures.add(inp)
    ext.name = "WebExtrude"
    ext.bodies.item(0).name = "Web"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
