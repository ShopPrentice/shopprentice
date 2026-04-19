"""Fixture: Centerline-guided loft.

Two circular sections connected by a single spline centerline
(addCenterLine). Unlike a rail, which must touch each profile at a
coincident point, a centerline threads through the profile interiors
and forces sections to orient perpendicular to the curve — useful for
sweeping-but-changing-diameter shapes like flexible tubing.
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

    params.add("cen_cx", VI("50 cm"), "cm", "Fixture anchor X")
    params.add("cen_cy", VI("25 cm"), "cm", "Fixture anchor Y")
    params.add("cen_r1", VI("2 cm"), "cm", "Bottom section radius")
    params.add("cen_r2", VI("1.2 cm"), "cm", "Top section radius")
    params.add("cen_h", VI("10 cm"), "cm", "Height")
    params.add("cen_bow", VI("3 cm"), "cm", "Centerline mid-bow offset in X")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    cx, cy = ev("cen_cx"), ev("cen_cy")
    r1, r2, h, bow = ev("cen_r1"), ev("cen_r2"), ev("cen_h"), ev("cen_bow")

    # Bottom circle on XY at (cx, cy, 0)
    sk1 = root.sketches.add(root.xYConstructionPlane)
    sk1.name = "Cen_Bottom"
    c1 = sk1.sketchCurves.sketchCircles.addByCenterRadius(P(cx, cy, 0), r1)
    sk1.sketchDimensions.addDiameterDimension(c1,
        P(cx + r1 + 0.5, cy, 0)).parameter.expression = "cen_r1 * 2"

    # Top plane at z = cen_h
    cpi = root.constructionPlanes.createInput()
    cpi.setByOffset(root.xYConstructionPlane, VI("cen_h"))
    cp_top = root.constructionPlanes.add(cpi)
    cp_top.name = "Cen_TopPl"

    # Top circle at (cx, cy, h)
    sk2 = root.sketches.add(cp_top)
    sk2.name = "Cen_Top"
    top_sk = sk2.modelToSketchSpace(P(cx, cy, h))
    c2 = sk2.sketchCurves.sketchCircles.addByCenterRadius(
        P(top_sk.x, top_sk.y, 0), r2)
    sk2.sketchDimensions.addDiameterDimension(c2,
        P(top_sk.x + r2 + 0.5, top_sk.y, 0)).parameter.expression = "cen_r2 * 2"

    # Centerline spline on XZ-parallel plane through y=cy
    cpi_cl = root.constructionPlanes.createInput()
    cpi_cl.setByOffset(root.xZConstructionPlane, VI("cen_cy"))
    pl_cl = root.constructionPlanes.add(cpi_cl)
    pl_cl.name = "Cen_RailPl"
    sk3 = root.sketches.add(pl_cl)
    sk3.name = "Cen_Centerline"
    p_bot = sk3.modelToSketchSpace(P(cx, cy, 0))
    p_mid = sk3.modelToSketchSpace(P(cx + bow, cy, h / 2))
    p_top = sk3.modelToSketchSpace(P(cx, cy, h))
    pts = adsk.core.ObjectCollection.create()
    pts.add(P(p_bot.x, p_bot.y, 0))
    pts.add(P(p_mid.x, p_mid.y, 0))
    pts.add(P(p_top.x, p_top.y, 0))
    centerline = sk3.sketchCurves.sketchFittedSplines.add(pts)

    # Loft with centerline (NOT a rail — sections orient perpendicular to the curve)
    loft_inp = root.features.loftFeatures.createInput(NEWBODY)
    loft_inp.loftSections.add(sk1.profiles.item(0))
    loft_inp.loftSections.add(sk2.profiles.item(0))
    loft_inp.centerLineOrRails.addCenterLine(centerline)
    loft_inp.isSolid = True
    loft = root.features.loftFeatures.add(loft_inp)
    loft.name = "CenterlineLoft"
    loft.bodies.item(0).name = "CenterlineTube"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
