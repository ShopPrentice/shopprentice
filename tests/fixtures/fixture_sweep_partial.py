"""Fixture: Sweep with partial distance.

Tests sweep with distanceOne < 1.0 (partial path sweep) and taper angle.
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

    params.add("bar_l", adsk.core.ValueInput.createByString("30 cm"), "cm", "Bar length")
    params.add("bar_w", adsk.core.ValueInput.createByString("3 cm"), "cm", "Bar width")
    params.add("bar_h", adsk.core.ValueInput.createByString("3 cm"), "cm", "Bar height")
    params.add("bead_r", adsk.core.ValueInput.createByString("0.4 cm"), "cm", "Bead radius")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                     else design.unitsManager.evaluateExpression(e, "cm"))

    # ── Sketch 1: bar profile ──
    sk1 = root.sketches.add(root.xYConstructionPlane)
    sk1.name = "BarProfile"
    l, w = ev("bar_l"), ev("bar_w")
    rect = sk1.sketchCurves.sketchLines.addTwoPointRectangle(P(0, 0, 0), P(l, w, 0))
    gc = sk1.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    dm = sk1.sketchDimensions
    dm.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(l/2, -1, 0)).parameter.expression = "bar_l"
    dm.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(l+1, w/2, 0)).parameter.expression = "bar_w"

    # ── Extrude: bar ──
    inp = root.features.extrudeFeatures.createInput(sk1.profiles.item(0), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("bar_h"))
    ext = root.features.extrudeFeatures.add(inp)
    ext.name = "BarExtrude"
    bar = ext.bodies.item(0)
    bar.name = "Bar"

    # ── Find the top-front edge (along X, at z=bar_h, y=0) ──
    h = ev("bar_h")
    best_edge = None
    best_len = 0
    for i in range(bar.edges.count):
        e = bar.edges.item(i)
        sv, ev2 = e.startVertex.geometry, e.endVertex.geometry
        if abs(sv.z - h) < 0.01 and abs(ev2.z - h) < 0.01:
            if abs(sv.y) < 0.01 and abs(ev2.y) < 0.01:
                length = abs(sv.x - ev2.x)
                if length > best_len:
                    best_len = length
                    best_edge = e

    # ── Sketch 2: bead circle profile ──
    sk2 = root.sketches.add(root.yZConstructionPlane)
    sk2.name = "BeadProfile"
    r = ev("bead_r")
    circle = sk2.sketchCurves.sketchCircles.addByCenterRadius(P(0, h, 0), r)
    dm2 = sk2.sketchDimensions
    dm2.addDiameterDimension(circle, P(r + 0.5, h, 0)).parameter.expression = "bead_r * 2"

    # ── Sweep: partial distance (75% of path) ──
    sweep_path = root.features.createPath(best_edge)
    sweep_inp = root.features.sweepFeatures.createInput(sk2.profiles.item(0), sweep_path, NEWBODY)
    sweep_inp.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
    sweep_inp.distanceOne = adsk.core.ValueInput.createByString("0.75")
    sweep_feat = root.features.sweepFeatures.add(sweep_inp)
    sweep_feat.name = "PartialBead"
    sweep_feat.bodies.item(0).name = "Bead"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
