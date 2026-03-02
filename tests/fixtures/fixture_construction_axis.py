"""Fixture: Construction axis used by pattern.

Tests construction axis creation and pattern using a custom axis.
This exercises the construction axis capture + emitter.
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

    params.add("pin_r", adsk.core.ValueInput.createByString("0.3 cm"), "cm", "")
    params.add("pin_h", adsk.core.ValueInput.createByString("2 cm"), "cm", "")
    params.add("pin_count", adsk.core.ValueInput.createByString("3"), "", "")
    params.add("pin_spacing", adsk.core.ValueInput.createByString("4 cm"), "cm", "")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                     else design.unitsManager.evaluateExpression(e, "cm"))

    # ── Sketch: pin on YZ plane at Y=2 ──
    sk = root.sketches.add(root.yZConstructionPlane)
    sk.name = "PinProfile"
    r = ev("pin_r")
    circle = sk.sketchCurves.sketchCircles.addByCenterRadius(P(2, 0, 0), r)
    dm = sk.sketchDimensions
    dm.addDiameterDimension(circle, P(2 + r + 0.5, 0, 0)).parameter.expression = "pin_r * 2"

    inp = root.features.extrudeFeatures.createInput(sk.profiles.item(0), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("pin_h"))
    ext = root.features.extrudeFeatures.add(inp)
    ext.name = "PinExtrude"
    pin = ext.bodies.item(0)
    pin.name = "Pin"

    # ── Pattern along Y axis (use built-in Y axis) ──
    coll = adsk.core.ObjectCollection.create()
    coll.add(pin)
    pat_inp = root.features.rectangularPatternFeatures.createInput(
        coll, root.yConstructionAxis,
        adsk.core.ValueInput.createByString("pin_count"),
        adsk.core.ValueInput.createByString("pin_spacing"),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    pat_inp.quantityTwo = adsk.core.ValueInput.createByReal(1)
    pat = root.features.rectangularPatternFeatures.add(pat_inp)
    pat.name = "PinPattern"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
