"""Fixture: Extrude feature variants.

Tests one-side, two-side, symmetric, taper, direction flip, and CUT with participantBodies.
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

    # Parameters
    params.add("block_w", adsk.core.ValueInput.createByString("10 cm"), "cm", "Block width")
    params.add("block_h", adsk.core.ValueInput.createByString("5 cm"), "cm", "Block height")
    params.add("block_d", adsk.core.ValueInput.createByString("8 cm"), "cm", "Block depth")
    params.add("taper_angle", adsk.core.ValueInput.createByString("5 deg"), "deg", "Taper")
    params.add("slot_w", adsk.core.ValueInput.createByString("3 cm"), "cm", "Slot width")
    params.add("slot_d", adsk.core.ValueInput.createByString("2 cm"), "cm", "Slot depth")
    params.add("sym_ext", adsk.core.ValueInput.createByString("4 cm"), "cm", "Symmetric extent")

    ev = lambda e: params.itemByName(e).value if params.itemByName(e) else design.unitsManager.evaluateExpression(e, "cm")

    # ── Sketch 1: main block rectangle ──
    sk1 = root.sketches.add(root.xYConstructionPlane)
    sk1.name = "BlockProfile"
    w, d = ev("block_w"), ev("block_d")
    rect = sk1.sketchCurves.sketchLines.addTwoPointRectangle(P(0, 0, 0), P(w, d, 0))
    gc = sk1.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    dm = sk1.sketchDimensions
    dm.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(w/2, -1, 0)).parameter.expression = "block_w"
    dm.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(w+1, d/2, 0)).parameter.expression = "block_d"

    # ── Extrude 1: one-side with taper ──
    inp = root.features.extrudeFeatures.createInput(sk1.profiles.item(0), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("block_h"))
    inp.taperAngle = adsk.core.ValueInput.createByString("taper_angle")
    ext1 = root.features.extrudeFeatures.add(inp)
    ext1.name = "TaperedBlock"
    block = ext1.bodies.item(0)
    block.name = "Block"

    # ── Sketch 2: slot for CUT (on top face) ──
    top_face = None
    for i in range(block.faces.count):
        f = block.faces.item(i)
        if isinstance(f.geometry, adsk.core.Plane) and abs(f.geometry.normal.z) > 0.9:
            if top_face is None or f.pointOnFace.z > top_face.pointOnFace.z:
                top_face = f

    sk2 = root.sketches.add(top_face)
    sk2.name = "SlotProfile"
    sw, sd = ev("slot_w"), ev("slot_d")
    # Slot centered on the face
    pt = sk2.modelToSketchSpace(P(w/2, d/2, top_face.pointOnFace.z))
    cx, cy = pt.x, pt.y
    rect2 = sk2.sketchCurves.sketchLines.addTwoPointRectangle(
        P(cx - sw/2, cy - sd/2, 0), P(cx + sw/2, cy + sd/2, 0))
    gc2 = sk2.geometricConstraints
    gc2.addHorizontal(rect2[0]); gc2.addHorizontal(rect2[2])
    gc2.addVertical(rect2[1]); gc2.addVertical(rect2[3])
    dm2 = sk2.sketchDimensions
    dm2.addDistanceDimension(rect2[0].startSketchPoint, rect2[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(cx, cy - 1, 0)).parameter.expression = "slot_w"
    dm2.addDistanceDimension(rect2[1].startSketchPoint, rect2[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(cx + sw/2 + 1, cy, 0)).parameter.expression = "slot_d"

    # Find smallest profile (the slot, not the surrounding face region)
    best_pi, best_area = 0, float('inf')
    for pi in range(sk2.profiles.count):
        bb = sk2.profiles.item(pi).boundingBox
        area = abs(bb.maxPoint.x - bb.minPoint.x) * abs(bb.maxPoint.y - bb.minPoint.y)
        if area < best_area:
            best_area = area
            best_pi = pi

    # ── Extrude 2: CUT into block (flipped direction) ──
    inp2 = root.features.extrudeFeatures.createInput(sk2.profiles.item(best_pi), CUT)
    inp2.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByString("block_h / 2")),
        adsk.fusion.ExtentDirections.NegativeExtentDirection)
    inp2.participantBodies = [block]
    ext2 = root.features.extrudeFeatures.add(inp2)
    ext2.name = "SlotCut"

    # ── Sketch 3: symmetric extrude ──
    sk3 = root.sketches.add(root.xZConstructionPlane)
    sk3.name = "SymProfile"
    rect3 = sk3.sketchCurves.sketchLines.addTwoPointRectangle(P(-1, -1, 0), P(1, 1, 0))
    gc3 = sk3.geometricConstraints
    gc3.addHorizontal(rect3[0]); gc3.addHorizontal(rect3[2])
    gc3.addVertical(rect3[1]); gc3.addVertical(rect3[3])
    dm3 = sk3.sketchDimensions
    dm3.addDistanceDimension(rect3[0].startSketchPoint, rect3[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(0, -2, 0)).parameter.expression = "2 cm"
    dm3.addDistanceDimension(rect3[1].startSketchPoint, rect3[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(2, 0, 0)).parameter.expression = "2 cm"

    # ── Extrude 3: symmetric ──
    inp3 = root.features.extrudeFeatures.createInput(sk3.profiles.item(0), NEWBODY)
    inp3.setSymmetricExtent(adsk.core.ValueInput.createByString("sym_ext"), True)
    ext3 = root.features.extrudeFeatures.add(inp3)
    ext3.name = "SymBlock"
    ext3.bodies.item(0).name = "SymBody"

    # Fit view
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
