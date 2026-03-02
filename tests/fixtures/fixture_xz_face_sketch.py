"""Fixture: Sketch on XZ-normal BRepFace (top face).

Tests coordinate mapping for a Z-normal face where sketch Y may be
flipped relative to model Y.
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

    params.add("slab_w", adsk.core.ValueInput.createByString("15 cm"), "cm", "")
    params.add("slab_d", adsk.core.ValueInput.createByString("10 cm"), "cm", "")
    params.add("slab_h", adsk.core.ValueInput.createByString("3 cm"), "cm", "")
    params.add("pocket_w", adsk.core.ValueInput.createByString("4 cm"), "cm", "")
    params.add("pocket_d", adsk.core.ValueInput.createByString("3 cm"), "cm", "")
    params.add("pocket_depth", adsk.core.ValueInput.createByString("1 cm"), "cm", "")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                     else design.unitsManager.evaluateExpression(e, "cm"))

    # ── Slab on XY ──
    sk1 = root.sketches.add(root.xYConstructionPlane)
    sk1.name = "SlabProfile"
    sw, sd = ev("slab_w"), ev("slab_d")
    rect = sk1.sketchCurves.sketchLines.addTwoPointRectangle(P(0, 0, 0), P(sw, sd, 0))
    gc = sk1.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    dm = sk1.sketchDimensions
    dm.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(sw/2, -1, 0)).parameter.expression = "slab_w"
    dm.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(sw+1, sd/2, 0)).parameter.expression = "slab_d"

    inp1 = root.features.extrudeFeatures.createInput(sk1.profiles.item(0), NEWBODY)
    inp1.setDistanceExtent(False, adsk.core.ValueInput.createByString("slab_h"))
    ext1 = root.features.extrudeFeatures.add(inp1)
    ext1.name = "SlabExtrude"
    slab = ext1.bodies.item(0)
    slab.name = "Slab"

    # ── Find top face (z = slab_h, Z-normal) ──
    h = ev("slab_h")
    top_face = None
    for i in range(slab.faces.count):
        f = slab.faces.item(i)
        if isinstance(f.geometry, adsk.core.Plane) and abs(f.geometry.normal.z) > 0.9:
            if top_face is None or f.pointOnFace.z > top_face.pointOnFace.z:
                top_face = f

    # ── Pocket sketch on top face ──
    sk2 = root.sketches.add(top_face)
    sk2.name = "PocketProfile"
    pw, pd = ev("pocket_w"), ev("pocket_d")
    pt1 = sk2.modelToSketchSpace(P(sw/2 - pw/2, sd/2 - pd/2, h))
    pt2 = sk2.modelToSketchSpace(P(sw/2 + pw/2, sd/2 + pd/2, h))
    rect2 = sk2.sketchCurves.sketchLines.addTwoPointRectangle(
        P(pt1.x, pt1.y, 0), P(pt2.x, pt2.y, 0))
    gc2 = sk2.geometricConstraints
    gc2.addHorizontal(rect2[0]); gc2.addHorizontal(rect2[2])
    gc2.addVertical(rect2[1]); gc2.addVertical(rect2[3])
    dm2 = sk2.sketchDimensions
    dm2.addDistanceDimension(rect2[0].startSketchPoint, rect2[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P((pt1.x+pt2.x)/2, pt1.y - 1, 0)).parameter.expression = "pocket_w"
    dm2.addDistanceDimension(rect2[1].startSketchPoint, rect2[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(pt2.x + 1, (pt1.y+pt2.y)/2, 0)).parameter.expression = "pocket_d"

    best_pi, best_area = 0, float('inf')
    for pi in range(sk2.profiles.count):
        bb = sk2.profiles.item(pi).boundingBox
        area = abs(bb.maxPoint.x - bb.minPoint.x) * abs(bb.maxPoint.y - bb.minPoint.y)
        if area < best_area:
            best_area = area
            best_pi = pi

    inp2 = root.features.extrudeFeatures.createInput(sk2.profiles.item(best_pi), CUT)
    inp2.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(
            adsk.core.ValueInput.createByString("pocket_depth")),
        adsk.fusion.ExtentDirections.NegativeExtentDirection)
    inp2.participantBodies = [slab]
    ext2 = root.features.extrudeFeatures.add(inp2)
    ext2.name = "PocketCut"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
