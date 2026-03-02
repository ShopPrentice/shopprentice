"""Fixture: Mirror feature.

Tests body mirror across a construction midplane.
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

    params.add("leg_w", adsk.core.ValueInput.createByString("3 cm"), "cm", "Leg width")
    params.add("leg_d", adsk.core.ValueInput.createByString("3 cm"), "cm", "Leg depth")
    params.add("leg_h", adsk.core.ValueInput.createByString("12 cm"), "cm", "Leg height")
    params.add("span", adsk.core.ValueInput.createByString("20 cm"), "cm", "Center span")

    ev = lambda e: params.itemByName(e).value if params.itemByName(e) else design.unitsManager.evaluateExpression(e, "cm")

    # ── Sketch: leg profile ──
    sk = root.sketches.add(root.xYConstructionPlane)
    sk.name = "LegProfile"
    w, d = ev("leg_w"), ev("leg_d")
    rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(P(0, 0, 0), P(w, d, 0))
    gc = sk.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    dm = sk.sketchDimensions
    dm.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(w/2, -1, 0)).parameter.expression = "leg_w"
    dm.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(w+1, d/2, 0)).parameter.expression = "leg_d"

    # ── Extrude: leg ──
    inp = root.features.extrudeFeatures.createInput(sk.profiles.item(0), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("leg_h"))
    ext = root.features.extrudeFeatures.add(inp)
    ext.name = "LegExtrude"
    leg = ext.bodies.item(0)
    leg.name = "Leg_L"

    # ── Construction plane at midpoint for mirror ──
    cp_inp = root.constructionPlanes.createInput()
    cp_inp.setByOffset(root.yZConstructionPlane, adsk.core.ValueInput.createByString("span / 2"))
    midplane = root.constructionPlanes.add(cp_inp)
    midplane.name = "MirrorPlane"

    # ── Mirror the leg ──
    coll = adsk.core.ObjectCollection.create()
    coll.add(leg)
    mir_inp = root.features.mirrorFeatures.createInput(coll, midplane)
    mir = root.features.mirrorFeatures.add(mir_inp)
    mir.name = "LegMirror"
    mir.bodies.item(0).name = "Leg_R"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
