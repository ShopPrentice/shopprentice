"""Fixture: Non-rectangle sketch on BRepFace with CUT.

Tests an arch-shaped profile (lines + arc) drawn on a body face and used
for a CUT extrude. Exercises the raw sketch emitter on a BRepFace where
the cplane conversion fails for CUTs at the body boundary.
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
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation

    params.add("beam_w", adsk.core.ValueInput.createByString("20 cm"), "cm", "Beam width")
    params.add("beam_d", adsk.core.ValueInput.createByString("6 cm"), "cm", "Beam depth")
    params.add("beam_h", adsk.core.ValueInput.createByString("4 cm"), "cm", "Beam height")
    params.add("arch_w", adsk.core.ValueInput.createByString("4 cm"), "cm", "Arch width")
    params.add("arch_h", adsk.core.ValueInput.createByString("2 cm"), "cm", "Arch straight height")
    params.add("arch_cut_d", adsk.core.ValueInput.createByString("1.5 cm"), "cm", "Arch cut depth")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                     else design.unitsManager.evaluateExpression(e, "cm"))

    # ── Sketch 1: beam rectangle on XY ──
    sk1 = root.sketches.add(root.xYConstructionPlane)
    sk1.name = "BeamProfile"
    bw, bd = ev("beam_w"), ev("beam_d")
    rect = sk1.sketchCurves.sketchLines.addTwoPointRectangle(P(0, 0, 0), P(bw, bd, 0))
    gc = sk1.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    dm = sk1.sketchDimensions
    dm.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(bw/2, -1, 0)).parameter.expression = "beam_w"
    dm.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(bw+1, bd/2, 0)).parameter.expression = "beam_d"

    # ── Extrude: beam ──
    inp1 = root.features.extrudeFeatures.createInput(sk1.profiles.item(0), NEWBODY)
    inp1.setDistanceExtent(False, adsk.core.ValueInput.createByString("beam_h"))
    ext1 = root.features.extrudeFeatures.add(inp1)
    ext1.name = "BeamExtrude"
    beam = ext1.bodies.item(0)
    beam.name = "Beam"

    # ── Find the right end face (x = beam_w) ──
    end_face = None
    for i in range(beam.faces.count):
        f = beam.faces.item(i)
        if isinstance(f.geometry, adsk.core.Plane) and abs(f.geometry.normal.x) > 0.9:
            if end_face is None or f.pointOnFace.x > end_face.pointOnFace.x:
                end_face = f

    # ── Sketch 2: arch on end face ──
    sk2 = root.sketches.add(end_face)
    sk2.name = "ArchCutProfile"

    aw, ah = ev("arch_w"), ev("arch_h")
    bh = ev("beam_h")
    # Position arch centered on the face, from bottom edge upward
    # On X-normal face: sketch X = model Y, sketch Y = model Z
    cy = bd / 2  # center Y in model = center of face
    pt = sk2.modelToSketchSpace(P(bw, cy - aw/2, 0))
    sx, sy = pt.x, pt.y
    pt2 = sk2.modelToSketchSpace(P(bw, cy + aw/2, ah))
    ex, ey = pt2.x, pt2.y

    lns = sk2.sketchCurves.sketchLines
    arcs = sk2.sketchCurves.sketchArcs

    # Bottom line (horizontal)
    ln0 = lns.addByTwoPoints(P(sx, sy, 0), P(ex, sy, 0))
    # Right vertical line
    ln1 = lns.addByTwoPoints(ln0.endSketchPoint, P(ex, ey, 0))
    # Top arc (semicircle)
    arc_cx = (sx + ex) / 2
    arc0 = arcs.addByCenterStartSweep(P(arc_cx, ey, 0), P(ex, ey, 0), math.pi)
    # Left vertical line (close profile)
    ln2 = lns.addByTwoPoints(arc0.endSketchPoint, ln0.startSketchPoint)

    gc2 = sk2.geometricConstraints
    gc2.addHorizontal(ln0)
    gc2.addVertical(ln1)
    gc2.addVertical(ln2)

    dm2 = sk2.sketchDimensions
    dm2.addDistanceDimension(ln0.startSketchPoint, ln0.endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(arc_cx, sy - 1, 0)).parameter.expression = "arch_w"
    dm2.addDistanceDimension(ln1.startSketchPoint, ln1.endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(ex + 1, (sy + ey)/2, 0)).parameter.expression = "arch_h"

    # Select the arch profile (smallest)
    best_pi, best_area = 0, float('inf')
    for pi in range(sk2.profiles.count):
        bb = sk2.profiles.item(pi).boundingBox
        area = abs(bb.maxPoint.x - bb.minPoint.x) * abs(bb.maxPoint.y - bb.minPoint.y)
        if area < best_area:
            best_area = area
            best_pi = pi

    # ── Extrude: arch CUT ──
    inp2 = root.features.extrudeFeatures.createInput(sk2.profiles.item(best_pi), CUT)
    inp2.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(
            adsk.core.ValueInput.createByString("arch_cut_d")),
        adsk.fusion.ExtentDirections.NegativeExtentDirection)
    inp2.participantBodies = [beam]
    ext2 = root.features.extrudeFeatures.add(inp2)
    ext2.name = "ArchCut"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
