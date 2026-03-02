"""Fixture: Sweep feature.

Tests sweep along a body edge with distances < 1.0 and Perpendicular orientation.
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

    params.add("rail_w", adsk.core.ValueInput.createByString("20 cm"), "cm", "Rail width")
    params.add("rail_h", adsk.core.ValueInput.createByString("3 cm"), "cm", "Rail height")
    params.add("rail_d", adsk.core.ValueInput.createByString("3 cm"), "cm", "Rail depth")
    params.add("bead_r", adsk.core.ValueInput.createByString("0.5 cm"), "cm", "Bead radius")

    ev = lambda e: params.itemByName(e).value if params.itemByName(e) else design.unitsManager.evaluateExpression(e, "cm")

    # ── Sketch 1: rail profile ──
    sk1 = root.sketches.add(root.xYConstructionPlane)
    sk1.name = "RailProfile"
    w, d = ev("rail_w"), ev("rail_d")
    rect = sk1.sketchCurves.sketchLines.addTwoPointRectangle(P(0, 0, 0), P(w, d, 0))
    gc = sk1.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    dm = sk1.sketchDimensions
    dm.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(w/2, -1, 0)).parameter.expression = "rail_w"
    dm.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(w+1, d/2, 0)).parameter.expression = "rail_d"

    # ── Extrude: rail ──
    inp = root.features.extrudeFeatures.createInput(sk1.profiles.item(0), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("rail_h"))
    ext = root.features.extrudeFeatures.add(inp)
    ext.name = "RailExtrude"
    rail = ext.bodies.item(0)
    rail.name = "Rail"

    # ── Find the top-front edge for sweep path ──
    h = ev("rail_h")
    best_edge = None
    best_score = -1e10
    for i in range(rail.edges.count):
        e = rail.edges.item(i)
        sv, ev2 = e.startVertex.geometry, e.endVertex.geometry
        # Look for edge along X at z=rail_h, y=0 (front-top)
        if abs(sv.z - h) < 0.01 and abs(ev2.z - h) < 0.01:
            if abs(sv.y) < 0.01 and abs(ev2.y) < 0.01:
                length = abs(sv.x - ev2.x)
                if length > best_score:
                    best_score = length
                    best_edge = e

    # ── Sketch 2: bead profile (on YZ plane at the edge start) ──
    sk2 = root.sketches.add(root.yZConstructionPlane)
    sk2.name = "BeadProfile"
    r = ev("bead_r")
    circle = sk2.sketchCurves.sketchCircles.addByCenterRadius(P(0, h, 0), r)
    dm2 = sk2.sketchDimensions
    dm2.addDiameterDimension(circle, P(r + 0.5, h, 0)).parameter.expression = "bead_r * 2"

    # ── Sweep: bead along top-front edge ──
    sweep_path = root.features.createPath(best_edge)
    sweep_inp = root.features.sweepFeatures.createInput(sk2.profiles.item(0), sweep_path, NEWBODY)
    sweep_inp.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
    sweep_feat = root.features.sweepFeatures.add(sweep_inp)
    sweep_feat.name = "BeadSweep"
    sweep_feat.bodies.item(0).name = "Bead"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
