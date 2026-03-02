"""Fixture: Sketch on YZ-normal BRepFace.

Tests the BRepFace → construction plane conversion for a face whose normal
is along the X axis (YZ plane). Exercises the coordinate transform logic
for non-Z-normal faces.
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

    params.add("post_w", adsk.core.ValueInput.createByString("4 cm"), "cm", "Post width")
    params.add("post_d", adsk.core.ValueInput.createByString("4 cm"), "cm", "Post depth")
    params.add("post_h", adsk.core.ValueInput.createByString("15 cm"), "cm", "Post height")
    params.add("mortise_w", adsk.core.ValueInput.createByString("2 cm"), "cm", "Mortise width")
    params.add("mortise_h", adsk.core.ValueInput.createByString("3 cm"), "cm", "Mortise height")
    params.add("mortise_depth", adsk.core.ValueInput.createByString("1.5 cm"), "cm", "Mortise depth")
    params.add("mortise_z", adsk.core.ValueInput.createByString("6 cm"), "cm", "Mortise Z offset")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                     else design.unitsManager.evaluateExpression(e, "cm"))

    # ── Sketch 1: post cross-section on XY ──
    sk1 = root.sketches.add(root.xYConstructionPlane)
    sk1.name = "PostProfile"
    pw, pd = ev("post_w"), ev("post_d")
    rect = sk1.sketchCurves.sketchLines.addTwoPointRectangle(P(0, 0, 0), P(pw, pd, 0))
    gc = sk1.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    dm = sk1.sketchDimensions
    dm.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(pw/2, -1, 0)).parameter.expression = "post_w"
    dm.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(pw+1, pd/2, 0)).parameter.expression = "post_d"

    # ── Extrude: post ──
    inp1 = root.features.extrudeFeatures.createInput(sk1.profiles.item(0), NEWBODY)
    inp1.setDistanceExtent(False, adsk.core.ValueInput.createByString("post_h"))
    ext1 = root.features.extrudeFeatures.add(inp1)
    ext1.name = "PostExtrude"
    post = ext1.bodies.item(0)
    post.name = "Post"

    # ── Find the front face (y = 0, normal along -Y) ──
    front_face = None
    for i in range(post.faces.count):
        f = post.faces.item(i)
        if isinstance(f.geometry, adsk.core.Plane) and abs(f.geometry.normal.y) > 0.9:
            if front_face is None or f.pointOnFace.y < front_face.pointOnFace.y:
                front_face = f

    # ── Sketch 2: mortise on front face (YZ-normal BRepFace) ──
    sk2 = root.sketches.add(front_face)
    sk2.name = "MortiseProfile"

    mw, mh = ev("mortise_w"), ev("mortise_h")
    mz = ev("mortise_z")
    # Center the mortise horizontally on the face
    cx = pw / 2
    pt1 = sk2.modelToSketchSpace(P(cx - mw/2, 0, mz))
    pt2 = sk2.modelToSketchSpace(P(cx + mw/2, 0, mz + mh))

    rect2 = sk2.sketchCurves.sketchLines.addTwoPointRectangle(
        P(pt1.x, pt1.y, 0), P(pt2.x, pt2.y, 0))
    gc2 = sk2.geometricConstraints
    gc2.addHorizontal(rect2[0]); gc2.addHorizontal(rect2[2])
    gc2.addVertical(rect2[1]); gc2.addVertical(rect2[3])
    dm2 = sk2.sketchDimensions
    dm2.addDistanceDimension(rect2[0].startSketchPoint, rect2[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P((pt1.x+pt2.x)/2, pt1.y - 1, 0)).parameter.expression = "mortise_w"
    dm2.addDistanceDimension(rect2[1].startSketchPoint, rect2[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(pt2.x + 1, (pt1.y+pt2.y)/2, 0)).parameter.expression = "mortise_h"

    # Smallest profile = the mortise
    best_pi, best_area = 0, float('inf')
    for pi in range(sk2.profiles.count):
        bb = sk2.profiles.item(pi).boundingBox
        area = abs(bb.maxPoint.x - bb.minPoint.x) * abs(bb.maxPoint.y - bb.minPoint.y)
        if area < best_area:
            best_area = area
            best_pi = pi

    # ── Extrude: mortise CUT into post ──
    inp2 = root.features.extrudeFeatures.createInput(sk2.profiles.item(best_pi), CUT)
    inp2.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(
            adsk.core.ValueInput.createByString("mortise_depth")),
        adsk.fusion.ExtentDirections.NegativeExtentDirection)
    inp2.participantBodies = [post]
    ext2 = root.features.extrudeFeatures.add(inp2)
    ext2.name = "MortiseCut"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
