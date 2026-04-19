"""Fixture: Square → rounded pyramid tip via point-tangent end condition.

Same technique as the circular ogive, but with a square base. The four
edges converge toward the apex while remaining perpendicular to the
base plane at the top — producing a rounded pyramid (like a pencil-tip
eraser or a shaped obelisk top) rather than a sharp four-sided pyramid.
"""
import adsk.core, adsk.fusion


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters

    P = adsk.core.Point3D.create
    VI = adsk.core.ValueInput.createByString
    NEWBODY = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    params.add("ogs_cx", VI("25 cm"), "cm", "Anchor X")
    params.add("ogs_cy", VI("75 cm"), "cm", "Anchor Y")
    params.add("ogs_side", VI("5 cm"), "cm", "Base square side")
    params.add("ogs_h", VI("8 cm"), "cm", "Ogive height")
    params.add("ogs_w", VI("2.0"), "", "Point-tangent weight")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    cx, cy = ev("ogs_cx"), ev("ogs_cy")
    s, h = ev("ogs_side"), ev("ogs_h")
    half = s / 2

    sk1 = root.sketches.add(root.xYConstructionPlane); sk1.name = "OgS_Base"
    rect = sk1.sketchCurves.sketchLines.addTwoPointRectangle(
        P(cx - half, cy - half, 0), P(cx + half, cy + half, 0))
    gc = sk1.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    dm = sk1.sketchDimensions
    dm.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(cx, cy - half - 0.5, 0)).parameter.expression = "ogs_side"
    dm.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(cx + half + 0.5, cy, 0)).parameter.expression = "ogs_side"

    cpi = root.constructionPlanes.createInput()
    cpi.setByOffset(root.xYConstructionPlane, VI("ogs_h"))
    cp_top = root.constructionPlanes.add(cpi); cp_top.name = "OgS_ApexPl"
    sk2 = root.sketches.add(cp_top); sk2.name = "OgS_Apex"
    apex_sk = sk2.modelToSketchSpace(P(cx, cy, h))
    apex = sk2.sketchPoints.add(P(apex_sk.x, apex_sk.y, 0))

    loft_inp = root.features.loftFeatures.createInput(NEWBODY)
    loft_inp.loftSections.add(sk1.profiles.item(0))
    tip = loft_inp.loftSections.add(apex)
    tip.setPointTangentEndCondition(VI("ogs_w"))
    loft_inp.isSolid = True
    loft = root.features.loftFeatures.add(loft_inp)
    loft.name = "OgiveSquare"
    loft.bodies.item(0).name = "OgiveObelisk"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
