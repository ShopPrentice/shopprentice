"""Fixture: Two-rail loft.

Two elliptical sections connected by two rails — one on the +X side,
one on the -X side — that define independent envelopes on each side.
This gives asymmetric control over the shape, common for boat hulls,
seat buckets, and handle grips.
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

    params.add("tr_cx", VI("0 cm"), "cm", "Anchor X")
    params.add("tr_cy", VI("50 cm"), "cm", "Anchor Y")
    params.add("tr_rx", VI("3 cm"), "cm", "Ellipse X radius (bottom)")
    params.add("tr_ry", VI("2 cm"), "cm", "Ellipse Y radius (bottom)")
    params.add("tr_h", VI("10 cm"), "cm", "Height")
    params.add("tr_top_rx", VI("1.5 cm"), "cm", "Ellipse X radius (top)")
    params.add("tr_top_ry", VI("1.2 cm"), "cm", "Ellipse Y radius (top)")
    params.add("tr_right_bulge", VI("1.5 cm"), "cm", "+X rail bulge")
    params.add("tr_left_bulge", VI("0.4 cm"), "cm", "-X rail bulge")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    cx, cy = ev("tr_cx"), ev("tr_cy")
    rx, ry = ev("tr_rx"), ev("tr_ry")
    top_rx, top_ry = ev("tr_top_rx"), ev("tr_top_ry")
    h = ev("tr_h")
    rb, lb = ev("tr_right_bulge"), ev("tr_left_bulge")

    def ellipse(sk, cx_m, cy_m, rxm, rym, tag):
        """Draw a parametric ellipse as a 4-arc approximation (single profile)."""
        ctr = sk.modelToSketchSpace(P(cx_m, cy_m, 0))
        axis_end = sk.modelToSketchSpace(P(cx_m + rxm, cy_m, 0))
        circ_pt = sk.modelToSketchSpace(P(cx_m, cy_m + rym, 0))
        el = sk.sketchCurves.sketchEllipses.add(
            P(ctr.x, ctr.y, 0),
            P(axis_end.x, axis_end.y, 0),
            P(circ_pt.x, circ_pt.y, 0))
        return el, ctr

    # Bottom ellipse on XY
    sk1 = root.sketches.add(root.xYConstructionPlane)
    sk1.name = "TR_Bottom"
    el1, c1_ctr = ellipse(sk1, cx, cy, rx, ry, "bot")

    # Anchor points on the bottom ellipse for the rails (at +X and -X extremes)
    a_bot_R = sk1.sketchPoints.add(P(c1_ctr.x + rx, c1_ctr.y, 0))
    sk1.geometricConstraints.addCoincident(a_bot_R, el1)
    a_bot_L = sk1.sketchPoints.add(P(c1_ctr.x - rx, c1_ctr.y, 0))
    sk1.geometricConstraints.addCoincident(a_bot_L, el1)

    # Top plane at z=h
    cpi = root.constructionPlanes.createInput()
    cpi.setByOffset(root.xYConstructionPlane, VI("tr_h"))
    cp_top = root.constructionPlanes.add(cpi)
    cp_top.name = "TR_TopPl"

    sk2 = root.sketches.add(cp_top)
    sk2.name = "TR_Top"
    el2, c2_ctr = ellipse(sk2, cx, cy, top_rx, top_ry, "top")
    a_top_R = sk2.sketchPoints.add(P(c2_ctr.x + top_rx, c2_ctr.y, 0))
    sk2.geometricConstraints.addCoincident(a_top_R, el2)
    a_top_L = sk2.sketchPoints.add(P(c2_ctr.x - top_rx, c2_ctr.y, 0))
    sk2.geometricConstraints.addCoincident(a_top_L, el2)

    # Rail R: spline on XZ-parallel plane through y=cy, bulging outward
    cpi_rail = root.constructionPlanes.createInput()
    cpi_rail.setByOffset(root.xZConstructionPlane, VI("tr_cy"))
    pl_rail = root.constructionPlanes.add(cpi_rail)
    pl_rail.name = "TR_RailPl"

    sk3 = root.sketches.add(pl_rail)
    sk3.name = "TR_RailR"
    pbR = sk3.project(a_bot_R).item(0)
    ptR = sk3.project(a_top_R).item(0)
    # Intermediate points above bottom anchor and below top anchor, bulged +X
    m1 = sk3.modelToSketchSpace(P(cx + rx + rb, cy, h / 3))
    m2 = sk3.modelToSketchSpace(P(cx + top_rx + rb * 0.5, cy, 2 * h / 3))
    midR1 = sk3.sketchPoints.add(P(m1.x, m1.y, 0))
    midR2 = sk3.sketchPoints.add(P(m2.x, m2.y, 0))
    ptsR = adsk.core.ObjectCollection.create()
    ptsR.add(pbR); ptsR.add(midR1); ptsR.add(midR2); ptsR.add(ptR)
    rail_R = sk3.sketchCurves.sketchFittedSplines.add(ptsR)

    # Rail L: same plane, different spline on the -X side
    sk4 = root.sketches.add(pl_rail)
    sk4.name = "TR_RailL"
    pbL = sk4.project(a_bot_L).item(0)
    ptL = sk4.project(a_top_L).item(0)
    n1 = sk4.modelToSketchSpace(P(cx - rx - lb, cy, h / 3))
    n2 = sk4.modelToSketchSpace(P(cx - top_rx - lb * 0.5, cy, 2 * h / 3))
    midL1 = sk4.sketchPoints.add(P(n1.x, n1.y, 0))
    midL2 = sk4.sketchPoints.add(P(n2.x, n2.y, 0))
    ptsL = adsk.core.ObjectCollection.create()
    ptsL.add(pbL); ptsL.add(midL1); ptsL.add(midL2); ptsL.add(ptL)
    rail_L = sk4.sketchCurves.sketchFittedSplines.add(ptsL)

    # Loft with two rails
    loft_inp = root.features.loftFeatures.createInput(NEWBODY)
    loft_inp.loftSections.add(sk1.profiles.item(0))
    loft_inp.loftSections.add(sk2.profiles.item(0))
    loft_inp.centerLineOrRails.addRail(rail_R)
    loft_inp.centerLineOrRails.addRail(rail_L)
    loft_inp.isSolid = True
    loft = root.features.loftFeatures.add(loft_inp)
    loft.name = "TwoRailLoft"
    loft.bodies.item(0).name = "HullShape"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
