"""Fixture: Circle → rounded bullet-nose (ogive) via point-tangent end condition.

Loft from a circle to a SketchPoint apex, then call
setPointTangentEndCondition(weight) on the point section. Instead of
a sharp cone, the loft arrives at the apex TANGENT to the profile plane
normal — producing a rounded bullet/ogive tip. The tangent weight
controls fullness: low weight = pointed, high weight = near-hemispherical.
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

    params.add("ogc_cx", VI("0 cm"), "cm", "Anchor X")
    params.add("ogc_cy", VI("75 cm"), "cm", "Anchor Y")
    params.add("ogc_r", VI("2.5 cm"), "cm", "Base circle radius")
    params.add("ogc_h", VI("8 cm"), "cm", "Ogive height")
    params.add("ogc_w", VI("2.0"), "", "Point-tangent weight (bullet fullness)")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    cx, cy = ev("ogc_cx"), ev("ogc_cy")
    r, h = ev("ogc_r"), ev("ogc_h")

    sk1 = root.sketches.add(root.xYConstructionPlane); sk1.name = "OgC_Base"
    c1 = sk1.sketchCurves.sketchCircles.addByCenterRadius(P(cx, cy, 0), r)
    sk1.sketchDimensions.addDiameterDimension(c1,
        P(cx + r + 0.5, cy, 0)).parameter.expression = "ogc_r * 2"

    cpi = root.constructionPlanes.createInput()
    cpi.setByOffset(root.xYConstructionPlane, VI("ogc_h"))
    cp_top = root.constructionPlanes.add(cpi); cp_top.name = "OgC_ApexPl"
    sk2 = root.sketches.add(cp_top); sk2.name = "OgC_Apex"
    apex_sk = sk2.modelToSketchSpace(P(cx, cy, h))
    apex = sk2.sketchPoints.add(P(apex_sk.x, apex_sk.y, 0))

    loft_inp = root.features.loftFeatures.createInput(NEWBODY)
    loft_inp.loftSections.add(sk1.profiles.item(0))
    tip = loft_inp.loftSections.add(apex)
    tip.setPointTangentEndCondition(VI("ogc_w"))
    loft_inp.isSolid = True
    loft = root.features.loftFeatures.add(loft_inp)
    loft.name = "OgiveCircle"
    loft.bodies.item(0).name = "OgiveBullet"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
