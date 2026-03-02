"""Fixture: Move feature.

Tests free move with translation.
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

    params.add("box_size", adsk.core.ValueInput.createByString("4 cm"), "cm", "Box size")
    params.add("move_x", adsk.core.ValueInput.createByString("10 cm"), "cm", "Move X")
    params.add("move_z", adsk.core.ValueInput.createByString("5 cm"), "cm", "Move Z")

    ev = lambda e: params.itemByName(e).value if params.itemByName(e) else design.unitsManager.evaluateExpression(e, "cm")

    # ── Sketch: box profile ──
    sk = root.sketches.add(root.xYConstructionPlane)
    sk.name = "BoxProfile"
    s = ev("box_size")
    rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(P(0, 0, 0), P(s, s, 0))
    gc = sk.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    dm = sk.sketchDimensions
    dm.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(s/2, -1, 0)).parameter.expression = "box_size"
    dm.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(s+1, s/2, 0)).parameter.expression = "box_size"

    # ── Extrude ──
    inp = root.features.extrudeFeatures.createInput(sk.profiles.item(0), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("box_size"))
    ext = root.features.extrudeFeatures.add(inp)
    ext.name = "BoxExtrude"
    box = ext.bodies.item(0)
    box.name = "Box"

    # ── Move: translate ──
    xform = adsk.core.Matrix3D.create()
    xform.translation = adsk.core.Vector3D.create(ev("move_x"), 0, ev("move_z"))

    move_coll = adsk.core.ObjectCollection.create()
    move_coll.add(box)
    move_inp = root.features.moveFeatures.createInput2(move_coll)
    move_inp.defineAsFreeMove(xform)
    move_feat = root.features.moveFeatures.add(move_inp)
    move_feat.name = "BoxMove"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
