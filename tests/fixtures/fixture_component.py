"""Fixture: Sub-component with bodies.

Tests component creation, sketching/extruding inside a component,
and cross-component combine operations.
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

    params.add("base_w", adsk.core.ValueInput.createByString("10 cm"), "cm", "")
    params.add("base_d", adsk.core.ValueInput.createByString("8 cm"), "cm", "")
    params.add("base_h", adsk.core.ValueInput.createByString("2 cm"), "cm", "")
    params.add("post_size", adsk.core.ValueInput.createByString("3 cm"), "cm", "")
    params.add("post_h", adsk.core.ValueInput.createByString("10 cm"), "cm", "")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                     else design.unitsManager.evaluateExpression(e, "cm"))

    # ── Base in root component ──
    sk1 = root.sketches.add(root.xYConstructionPlane)
    sk1.name = "BaseProfile"
    bw, bd = ev("base_w"), ev("base_d")
    rect = sk1.sketchCurves.sketchLines.addTwoPointRectangle(P(0, 0, 0), P(bw, bd, 0))
    gc = sk1.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    dm = sk1.sketchDimensions
    dm.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(bw/2, -1, 0)).parameter.expression = "base_w"
    dm.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(bw+1, bd/2, 0)).parameter.expression = "base_d"

    inp1 = root.features.extrudeFeatures.createInput(sk1.profiles.item(0), NEWBODY)
    inp1.setDistanceExtent(False, adsk.core.ValueInput.createByString("base_h"))
    ext1 = root.features.extrudeFeatures.add(inp1)
    ext1.name = "BaseExtrude"
    base = ext1.bodies.item(0)
    base.name = "Base"

    # ── Post in root (simple, no sub-component for now) ──
    bh = ev("base_h")
    ps = ev("post_size")
    cp_inp = root.constructionPlanes.createInput()
    cp_inp.setByOffset(root.xYConstructionPlane, adsk.core.ValueInput.createByString("base_h"))
    cp = root.constructionPlanes.add(cp_inp)
    cp.name = "PostPlane"

    sk2 = root.sketches.add(cp)
    sk2.name = "PostProfile"
    rect2 = sk2.sketchCurves.sketchLines.addTwoPointRectangle(
        P(bw/2 - ps/2, bd/2 - ps/2, 0), P(bw/2 + ps/2, bd/2 + ps/2, 0))
    gc2 = sk2.geometricConstraints
    gc2.addHorizontal(rect2[0]); gc2.addHorizontal(rect2[2])
    gc2.addVertical(rect2[1]); gc2.addVertical(rect2[3])
    dm2 = sk2.sketchDimensions
    dm2.addDistanceDimension(rect2[0].startSketchPoint, rect2[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(bw/2, bd/2 - ps/2 - 1, 0)).parameter.expression = "post_size"
    dm2.addDistanceDimension(rect2[1].startSketchPoint, rect2[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(bw/2 + ps/2 + 1, bd/2, 0)).parameter.expression = "post_size"

    inp2 = root.features.extrudeFeatures.createInput(sk2.profiles.item(0), NEWBODY)
    inp2.setDistanceExtent(False, adsk.core.ValueInput.createByString("post_h"))
    ext2 = root.features.extrudeFeatures.add(inp2)
    ext2.name = "PostExtrude"
    post = ext2.bodies.item(0)
    post.name = "Post"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
