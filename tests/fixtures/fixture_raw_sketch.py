"""Fixture: Non-rectangle sketch with arcs and parametric dimensions.

Tests the raw sketch emitter path (not rectangle detection). Creates an
arch-shaped profile with lines + arc, constrained dimensions, and extrudes it.
"""
import adsk.core, adsk.fusion, math


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters

    P = adsk.core.Point3D.create
    NEWBODY = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    params.add("arch_w", adsk.core.ValueInput.createByString("8 cm"), "cm", "Arch width")
    params.add("arch_h", adsk.core.ValueInput.createByString("6 cm"), "cm", "Arch straight height")
    params.add("arch_d", adsk.core.ValueInput.createByString("3 cm"), "cm", "Arch depth")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                     else design.unitsManager.evaluateExpression(e, "cm"))

    # ── Sketch: arch profile (2 vertical lines + 1 bottom line + 1 top arc) ──
    sk = root.sketches.add(root.xYConstructionPlane)
    sk.name = "ArchProfile"
    lns = sk.sketchCurves.sketchLines
    arcs = sk.sketchCurves.sketchArcs

    w, h = ev("arch_w"), ev("arch_h")
    r = w / 2  # semicircle radius = half width

    # Bottom line
    ln0 = lns.addByTwoPoints(P(0, 0, 0), P(w, 0, 0))
    # Right vertical line
    ln1 = lns.addByTwoPoints(ln0.endSketchPoint, P(w, h, 0))
    # Top arc (semicircle from right-top to left-top)
    arc0 = arcs.addByCenterStartSweep(P(w/2, h, 0), P(w, h, 0), math.pi)
    # Left vertical line (closing the profile)
    ln2 = lns.addByTwoPoints(arc0.endSketchPoint, ln0.startSketchPoint)

    # Constraints
    gc = sk.geometricConstraints
    gc.addHorizontal(ln0)
    gc.addVertical(ln1)
    gc.addVertical(ln2)

    # Dimensions
    dm = sk.sketchDimensions
    dm.addDistanceDimension(ln0.startSketchPoint, ln0.endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(w/2, -1, 0)).parameter.expression = "arch_w"
    dm.addDistanceDimension(ln1.startSketchPoint, ln1.endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(w+1, h/2, 0)).parameter.expression = "arch_h"

    # ── Extrude: arch body ──
    # Find the profile that includes the arch (should be the only closed region)
    inp = root.features.extrudeFeatures.createInput(sk.profiles.item(0), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("arch_d"))
    ext = root.features.extrudeFeatures.add(inp)
    ext.name = "ArchExtrude"
    ext.bodies.item(0).name = "Arch"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
