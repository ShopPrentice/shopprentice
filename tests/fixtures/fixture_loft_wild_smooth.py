"""Fixture: Multi-section loft along a serpentine path, rounded at both ends.

Eight sections: point tip → six circles whose centres wander through
(x, y) and whose radii bulge in the middle → point tip. Both end
sections use setPointTangentEndCondition(weight) so the ends arrive
tangent (rounded caterpillar noses, not sharp cones). The middle
transitions are smooth by construction — Fusion interpolates with a
cubic-style blend between circular sections, so as long as the profile
shape stays consistent (all circles here) and the sections are spaced
apart, the surface reads as one continuous tube. isTangentEdgesMerged
cleans up any coincident tangent seams on the final body.

The resulting shape is a rounded-ended meandering worm — wild path,
smooth skin, no visible section lines.
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

    params.add("ws_cx", VI("25 cm"), "cm", "Anchor X")
    params.add("ws_cy", VI("100 cm"), "cm", "Anchor Y")
    params.add("ws_h", VI("14 cm"), "cm", "Total height")
    params.add("ws_wiggle", VI("2 cm"), "cm", "Path wiggle amplitude")
    params.add("ws_rmax", VI("2.2 cm"), "cm", "Max mid-section radius")
    params.add("ws_weight", VI("4.0"), "", "Point-tangent weight at both ends")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    cx, cy = ev("ws_cx"), ev("ws_cy")
    H = ev("ws_h")
    W = ev("ws_wiggle")
    RM = ev("ws_rmax")

    # Sections expressed as fractions of H and multiples of W and RM so
    # the whole shape scales cleanly when any parameter changes.
    # (z_frac, x_off_frac_of_W, y_off_frac_of_W, r_frac_of_RM)
    #   r == None means a point section (both ends)
    # Going STRAIGHT from tip to a full-size section (no small transitional
    # circle between them) makes the point-tangent condition produce an
    # egg/bullet-like round tip. A near-tip small circle actually pinches
    # the surface and makes the tip look pointier.
    sections = [
        (0.00,  0.0,  0.0, None),  # bottom tip
        (0.20,  0.8,  0.0, 0.75),
        (0.40,  0.6,  1.0, 1.00),
        (0.60, -0.6,  1.0, 0.95),
        (0.80, -0.8,  0.0, 0.70),
        (1.00,  0.0,  0.0, None),  # top tip
    ]

    loft_inp = root.features.loftFeatures.createInput(NEWBODY)
    tip_sections = []  # first + last for tangent conditions

    for i, (zf, xf, yf, rf) in enumerate(sections):
        z = zf * H
        bx = cx + xf * W
        by = cy + yf * W

        if zf == 0.0:
            plane = root.xYConstructionPlane
        else:
            cpi = root.constructionPlanes.createInput()
            cpi.setByOffset(root.xYConstructionPlane, VI(f"ws_h * {zf}"))
            plane = root.constructionPlanes.add(cpi)
            plane.name = f"Ws_Pl{i}"

        sk = root.sketches.add(plane)
        sk.name = f"Ws_Sk{i}"
        ctr_sk = sk.modelToSketchSpace(P(bx, by, z))

        if rf is None:
            pt = sk.sketchPoints.add(P(ctr_sk.x, ctr_sk.y, 0))
            section = loft_inp.loftSections.add(pt)
            tip_sections.append(section)
        else:
            r = rf * RM
            sk.sketchCurves.sketchCircles.addByCenterRadius(
                P(ctr_sk.x, ctr_sk.y, 0), r)
            loft_inp.loftSections.add(sk.profiles.item(0))

    # Both ends: rounded tangent tip (same weight). Remove if you want
    # sharp noses instead.
    for s in tip_sections:
        s.setPointTangentEndCondition(VI("ws_weight"))

    loft_inp.isSolid = True
    loft_inp.isTangentEdgesMerged = True
    loft = root.features.loftFeatures.add(loft_inp)
    loft.name = "WildSmoothLoft"
    loft.bodies.item(0).name = "Serpentine"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
