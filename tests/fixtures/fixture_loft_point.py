"""Fixture: Loft from a profile to a SketchPoint (cone/tip shape).

Demonstrates that a LoftSection accepts a SketchPoint as a degenerate
"profile" — useful for pencil tips, spires, and tapered spindle ends.
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

    params.add("pt_cx", VI("0 cm"), "cm", "Cone center X")
    params.add("pt_cy", VI("25 cm"), "cm", "Cone center Y")
    params.add("pt_r", VI("3 cm"), "cm", "Base radius")
    params.add("pt_h", VI("8 cm"), "cm", "Cone height")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    cx, cy = ev("pt_cx"), ev("pt_cy")
    r, h = ev("pt_r"), ev("pt_h")

    # Base circle on XY plane
    sk1 = root.sketches.add(root.xYConstructionPlane)
    sk1.name = "Point_Base"
    c = sk1.sketchCurves.sketchCircles.addByCenterRadius(P(cx, cy, 0), r)
    sk1.sketchDimensions.addDiameterDimension(c,
        P(cx + r + 0.5, cy, 0)).parameter.expression = "pt_r * 2"

    # Offset plane at z = pt_h
    cpi = root.constructionPlanes.createInput()
    cpi.setByOffset(root.xYConstructionPlane, VI("pt_h"))
    cp_top = root.constructionPlanes.add(cpi)
    cp_top.name = "Point_Apex_Pl"

    # Apex SketchPoint on the offset plane, centered over the base
    sk2 = root.sketches.add(cp_top)
    sk2.name = "Point_Apex"
    apex_sk = sk2.modelToSketchSpace(P(cx, cy, h))
    apex = sk2.sketchPoints.add(P(apex_sk.x, apex_sk.y, 0))

    # Loft: circle → sketch point
    loft_inp = root.features.loftFeatures.createInput(NEWBODY)
    loft_inp.loftSections.add(sk1.profiles.item(0))
    loft_inp.loftSections.add(apex)
    loft_inp.isSolid = True
    loft = root.features.loftFeatures.add(loft_inp)
    loft.name = "ConeLoft"
    loft.bodies.item(0).name = "Cone"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
