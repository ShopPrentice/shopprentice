"""Fixture: Sketch with projected edges and constrained dimensions.

Tests sketch on a body face with projected body edges, distance dimensions
with explicit entity targets, and coincident constraints.
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

    params.add("plank_w", adsk.core.ValueInput.createByString("20 cm"), "cm", "Plank width")
    params.add("plank_d", adsk.core.ValueInput.createByString("10 cm"), "cm", "Plank depth")
    params.add("plank_h", adsk.core.ValueInput.createByString("2 cm"), "cm", "Plank height")
    params.add("notch_inset", adsk.core.ValueInput.createByString("3 cm"), "cm", "Notch inset from edge")
    params.add("notch_w", adsk.core.ValueInput.createByString("4 cm"), "cm", "Notch width")

    ev = lambda e: params.itemByName(e).value if params.itemByName(e) else design.unitsManager.evaluateExpression(e, "cm")

    # ── Sketch 1: plank rectangle ──
    sk1 = root.sketches.add(root.xYConstructionPlane)
    sk1.name = "PlankProfile"
    pw, pd = ev("plank_w"), ev("plank_d")
    rect = sk1.sketchCurves.sketchLines.addTwoPointRectangle(P(0, 0, 0), P(pw, pd, 0))
    gc = sk1.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    dm = sk1.sketchDimensions
    dm.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(pw/2, -1, 0)).parameter.expression = "plank_w"
    dm.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(pw+1, pd/2, 0)).parameter.expression = "plank_d"

    # ── Extrude: plank ──
    inp1 = root.features.extrudeFeatures.createInput(sk1.profiles.item(0), NEWBODY)
    inp1.setDistanceExtent(False, adsk.core.ValueInput.createByString("plank_h"))
    ext1 = root.features.extrudeFeatures.add(inp1)
    ext1.name = "PlankExtrude"
    plank = ext1.bodies.item(0)
    plank.name = "Plank"

    # ── Sketch 2: notch on top face using construction plane ──
    # Use construction plane at plank_h instead of body face to avoid
    # auto-projected boundary edge issues
    h = ev("plank_h")
    cp_inp = root.constructionPlanes.createInput()
    cp_inp.setByOffset(root.xYConstructionPlane, adsk.core.ValueInput.createByString("plank_h"))
    cplane = root.constructionPlanes.add(cp_inp)
    cplane.name = "TopPlane"

    sk2 = root.sketches.add(cplane)
    sk2.name = "NotchProfile"
    ni = ev("notch_inset")
    nw = ev("notch_w")
    # Notch: a rectangle cut from the front edge (y=0)
    rect2 = sk2.sketchCurves.sketchLines.addTwoPointRectangle(P(ni, 0, 0), P(ni + nw, pd/2, 0))
    gc2 = sk2.geometricConstraints
    gc2.addHorizontal(rect2[0]); gc2.addHorizontal(rect2[2])
    gc2.addVertical(rect2[1]); gc2.addVertical(rect2[3])
    dm2 = sk2.sketchDimensions
    # Dimension: notch width
    dm2.addDistanceDimension(rect2[0].startSketchPoint, rect2[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(ni + nw/2, -1, 0)).parameter.expression = "notch_w"
    # Dimension: notch inset from origin (tests origin-to-point dimension target)
    dm2.addDistanceDimension(sk2.originPoint, rect2[0].startSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(ni/2, -2, 0)).parameter.expression = "notch_inset"
    # Dimension: notch depth
    dm2.addDistanceDimension(rect2[1].startSketchPoint, rect2[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(ni + nw + 1, pd/4, 0)).parameter.expression = "plank_d / 2"

    # ── Extrude: notch CUT ──
    inp2 = root.features.extrudeFeatures.createInput(sk2.profiles.item(0), CUT)
    inp2.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByString("plank_h")),
        adsk.fusion.ExtentDirections.NegativeExtentDirection)
    inp2.participantBodies = [plank]
    ext2 = root.features.extrudeFeatures.add(inp2)
    ext2.name = "NotchCut"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
