"""Fixture: Rectangular pattern.

Tests 1-axis rectangular pattern with spacing distance type.
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

    params.add("peg_r", adsk.core.ValueInput.createByString("0.5 cm"), "cm", "Peg radius")
    params.add("peg_h", adsk.core.ValueInput.createByString("3 cm"), "cm", "Peg height")
    params.add("peg_count", adsk.core.ValueInput.createByString("4"), "", "Number of pegs")
    params.add("peg_spacing", adsk.core.ValueInput.createByString("5 cm"), "cm", "Peg spacing")

    ev = lambda e: params.itemByName(e).value if params.itemByName(e) else design.unitsManager.evaluateExpression(e, "cm")

    # ── Sketch: peg profile ──
    sk = root.sketches.add(root.xYConstructionPlane)
    sk.name = "PegProfile"
    r = ev("peg_r")
    circle = sk.sketchCurves.sketchCircles.addByCenterRadius(P(0, 0, 0), r)
    dm = sk.sketchDimensions
    dm.addDiameterDimension(circle, P(r + 0.5, 0, 0)).parameter.expression = "peg_r * 2"

    # ── Extrude: single peg ──
    inp = root.features.extrudeFeatures.createInput(sk.profiles.item(0), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("peg_h"))
    ext = root.features.extrudeFeatures.add(inp)
    ext.name = "PegExtrude"
    peg = ext.bodies.item(0)
    peg.name = "Peg"

    # ── Rectangular pattern along X axis ──
    coll = adsk.core.ObjectCollection.create()
    coll.add(peg)
    pat_inp = root.features.rectangularPatternFeatures.createInput(
        coll,
        root.xConstructionAxis,
        adsk.core.ValueInput.createByString("peg_count"),
        adsk.core.ValueInput.createByString("peg_spacing"),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType,
    )
    pat_inp.quantityTwo = adsk.core.ValueInput.createByReal(1)
    pat = root.features.rectangularPatternFeatures.add(pat_inp)
    pat.name = "PegPattern"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
