"""Fixture: Closed loft (ring).

Four circular sections positioned at N/E/S/W points of a square path
around a vertical axis. Each section sits on a plane perpendicular to
the local travel direction. isClosed=True wraps the last section back
to the first, forming a closed square-path ring.
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

    params.add("cl_cx", VI("25 cm"), "cm", "Ring center X")
    params.add("cl_cy", VI("25 cm"), "cm", "Ring center Y")
    params.add("cl_R", VI("6 cm"), "cm", "Ring radius (center-to-section)")
    params.add("cl_r", VI("0.8 cm"), "cm", "Section circle radius")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    cx, cy = ev("cl_cx"), ev("cl_cy")
    R, r = ev("cl_R"), ev("cl_r")

    # Plane 1: YZ-parallel through x=cx (hosts sections E & W, at y=cy±R)
    #   At these points the ring travels in ±Y, so plane normal = X. ✓
    cpi_yz = root.constructionPlanes.createInput()
    cpi_yz.setByOffset(root.yZConstructionPlane, VI("cl_cx"))
    pl_yz = root.constructionPlanes.add(cpi_yz)
    pl_yz.name = "Ring_YZ_Pl"

    # Plane 2: XZ-parallel through y=cy (hosts sections N & S, at x=cx±R)
    #   At these points the ring travels in ±X, so plane normal = Y. ✓
    cpi_xz = root.constructionPlanes.createInput()
    cpi_xz.setByOffset(root.xZConstructionPlane, VI("cl_cy"))
    pl_xz = root.constructionPlanes.add(cpi_xz)
    pl_xz.name = "Ring_XZ_Pl"

    def add_circle(plane, name, model_ctr):
        sk = root.sketches.add(plane)
        sk.name = name
        sk_ctr = sk.modelToSketchSpace(model_ctr)
        circ = sk.sketchCurves.sketchCircles.addByCenterRadius(
            P(sk_ctr.x, sk_ctr.y, 0), r)
        sk.sketchDimensions.addDiameterDimension(circ,
            P(sk_ctr.x + r + 0.5, sk_ctr.y, 0)).parameter.expression = "cl_r * 2"
        return sk.profiles.item(0)

    # Sections in CCW order (viewed from +Z): S → E → N → W → (back to S)
    prof_S = add_circle(pl_yz, "Ring_S", P(cx, cy - R, 0))
    prof_E = add_circle(pl_xz, "Ring_E", P(cx + R, cy, 0))
    prof_N = add_circle(pl_yz, "Ring_N", P(cx, cy + R, 0))
    prof_W = add_circle(pl_xz, "Ring_W", P(cx - R, cy, 0))

    loft_inp = root.features.loftFeatures.createInput(NEWBODY)
    loft_inp.loftSections.add(prof_S)
    loft_inp.loftSections.add(prof_E)
    loft_inp.loftSections.add(prof_N)
    loft_inp.loftSections.add(prof_W)
    loft_inp.isClosed = True
    loft_inp.isSolid = True
    loft = root.features.loftFeatures.add(loft_inp)
    loft.name = "ClosedRingLoft"
    loft.bodies.item(0).name = "Ring"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
