"""Fixture: Loft feature with a rail (guide curve).

Two circular sections on parallel planes connected by an S-curve rail
sketched on an XZ-parallel plane. The rail endpoints coincide with a
sketch point on each section so Fusion can bind the rail to both sections.
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

    params.add("rail_cx", VI("50 cm"), "cm", "Fixture anchor X")
    params.add("rail_cy", VI("0 cm"), "cm", "Fixture anchor Y")
    params.add("rail_h", VI("12 cm"), "cm", "Loft height")
    params.add("rail_r1", VI("2 cm"), "cm", "Bottom circle radius")
    params.add("rail_r2", VI("1.5 cm"), "cm", "Top circle radius")
    params.add("rail_offset", VI("4 cm"), "cm", "Rail horizontal sweep (X)")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    cx, cy = ev("rail_cx"), ev("rail_cy")
    h, r1, r2, off = ev("rail_h"), ev("rail_r1"), ev("rail_r2"), ev("rail_offset")

    # Bottom circle on XY at (cx, cy, 0)
    sk1 = root.sketches.add(root.xYConstructionPlane); sk1.name = "Rail_Bottom"
    c1 = sk1.sketchCurves.sketchCircles.addByCenterRadius(P(cx, cy, 0), r1)
    sk1.sketchDimensions.addDiameterDimension(c1,
        P(cx + r1 + 0.5, cy, 0)).parameter.expression = "rail_r1 * 2"
    anchor_bot = sk1.sketchPoints.add(P(cx + r1, cy, 0))
    sk1.geometricConstraints.addCoincident(anchor_bot, c1)

    # Top plane at z = rail_h
    cpi = root.constructionPlanes.createInput()
    cpi.setByOffset(root.xYConstructionPlane, VI("rail_h"))
    cp_top = root.constructionPlanes.add(cpi); cp_top.name = "Rail_TopPl"

    sk2 = root.sketches.add(cp_top); sk2.name = "Rail_Top"
    top_ctr = sk2.modelToSketchSpace(P(cx + off, cy, h))
    c2 = sk2.sketchCurves.sketchCircles.addByCenterRadius(
        P(top_ctr.x, top_ctr.y, 0), r2)
    sk2.sketchDimensions.addDiameterDimension(c2,
        P(top_ctr.x + r2 + 0.5, top_ctr.y, 0)).parameter.expression = "rail_r2 * 2"
    top_anchor_sk = sk2.modelToSketchSpace(P(cx + off + r2, cy, h))
    anchor_top = sk2.sketchPoints.add(P(top_anchor_sk.x, top_anchor_sk.y, 0))
    sk2.geometricConstraints.addCoincident(anchor_top, c2)

    # Rail on an XZ-parallel plane through y=cy. Use modelToSketchSpace for
    # every control point (sketch-Y on xZ plane maps to -model-Z).
    cpi_r = root.constructionPlanes.createInput()
    cpi_r.setByOffset(root.xZConstructionPlane, VI("rail_cy"))
    pl_rail = root.constructionPlanes.add(cpi_r); pl_rail.name = "Rail_Pl"
    sk3 = root.sketches.add(pl_rail); sk3.name = "Rail_Curve"
    pb = sk3.project(anchor_bot).item(0)
    pt = sk3.project(anchor_top).item(0)

    # Intermediate control points — vertically above/below the anchors so the
    # spline enters/exits each profile perpendicular to the profile plane.
    ab = sk3.modelToSketchSpace(P(cx + r1, cy, h / 4))
    md = sk3.modelToSketchSpace(P(cx + (r1 + off + r2) / 2, cy, h / 2))
    bt = sk3.modelToSketchSpace(P(cx + off + r2, cy, 3 * h / 4))
    above_bot = sk3.sketchPoints.add(P(ab.x, ab.y, 0))
    mid = sk3.sketchPoints.add(P(md.x, md.y, 0))
    below_top = sk3.sketchPoints.add(P(bt.x, bt.y, 0))

    pts = adsk.core.ObjectCollection.create()
    pts.add(pb); pts.add(above_bot); pts.add(mid); pts.add(below_top); pts.add(pt)
    spline = sk3.sketchCurves.sketchFittedSplines.add(pts)

    loft_inp = root.features.loftFeatures.createInput(NEWBODY)
    loft_inp.loftSections.add(sk1.profiles.item(0))
    loft_inp.loftSections.add(sk2.profiles.item(0))
    loft_inp.centerLineOrRails.addRail(spline)
    loft_inp.isSolid = True
    loft = root.features.loftFeatures.add(loft_inp)
    loft.name = "RailGuidedLoft"
    loft.bodies.item(0).name = "RailLoft"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
