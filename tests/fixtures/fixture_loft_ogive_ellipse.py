"""Fixture: Ellipse → teardrop/egg tip via point-tangent end condition.

Elliptical base lofted to an apex SketchPoint with tangent end condition.
The asymmetric base (rx ≠ ry) produces an egg/teardrop profile — the
surface curves faster in the narrow axis and more gradually in the long
axis, just like the ends of a real chicken egg or a raindrop.
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

    params.add("oge_cx", VI("50 cm"), "cm", "Anchor X")
    params.add("oge_cy", VI("75 cm"), "cm", "Anchor Y")
    params.add("oge_rx", VI("3 cm"), "cm", "Ellipse X radius")
    params.add("oge_ry", VI("1.8 cm"), "cm", "Ellipse Y radius")
    params.add("oge_h", VI("9 cm"), "cm", "Ogive height")
    params.add("oge_w", VI("2.5"), "", "Point-tangent weight")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    cx, cy = ev("oge_cx"), ev("oge_cy")
    rx, ry, h = ev("oge_rx"), ev("oge_ry"), ev("oge_h")

    sk1 = root.sketches.add(root.xYConstructionPlane); sk1.name = "OgE_Base"
    sk1.sketchCurves.sketchEllipses.add(
        P(cx, cy, 0),
        P(cx + rx, cy, 0),
        P(cx, cy + ry, 0))

    cpi = root.constructionPlanes.createInput()
    cpi.setByOffset(root.xYConstructionPlane, VI("oge_h"))
    cp_top = root.constructionPlanes.add(cpi); cp_top.name = "OgE_ApexPl"
    sk2 = root.sketches.add(cp_top); sk2.name = "OgE_Apex"
    apex_sk = sk2.modelToSketchSpace(P(cx, cy, h))
    apex = sk2.sketchPoints.add(P(apex_sk.x, apex_sk.y, 0))

    loft_inp = root.features.loftFeatures.createInput(NEWBODY)
    loft_inp.loftSections.add(sk1.profiles.item(0))
    tip = loft_inp.loftSections.add(apex)
    tip.setPointTangentEndCondition(VI("oge_w"))
    loft_inp.isSolid = True
    loft = root.features.loftFeatures.add(loft_inp)
    loft.name = "OgiveEllipse"
    loft.bodies.item(0).name = "OgiveEgg"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
