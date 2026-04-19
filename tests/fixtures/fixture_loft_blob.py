"""Fixture: Serpentine blob with truly hemispherical rounded ends.

Same wild-path concept as fixture_loft_wild_smooth, but tuned so the
ends look like proper egg caps instead of pointy noses:

 - The first non-tip section sits only 5 % of total height away from
   the apex SketchPoint.
 - That section's radius is 0.9 × RM — nearly the full body width.
 - A high tangent weight (6.0) on setPointTangentEndCondition makes
   the surface take off almost horizontally from the point, so the
   tip bulges out to meet that big neighbouring circle in a bubbly,
   hemispherical curve rather than a narrow cone.

Net effect: two round caps joined by a fat meandering middle. Looks
like a wide-bodied gummy candy or a pebble worn smooth in a river.
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

    params.add("bl_cx", VI("50 cm"), "cm", "Anchor X")
    params.add("bl_cy", VI("100 cm"), "cm", "Anchor Y")
    params.add("bl_h", VI("14 cm"), "cm", "Total height")
    params.add("bl_wiggle", VI("2 cm"), "cm", "Path wiggle amplitude")
    params.add("bl_rmax", VI("2.2 cm"), "cm", "Max mid-section radius")
    params.add("bl_weight", VI("6.0"), "", "Point-tangent weight (very rounded)")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    cx, cy = ev("bl_cx"), ev("bl_cy")
    H = ev("bl_h")
    W = ev("bl_wiggle")
    RM = ev("bl_rmax")

    # The two critical sections are at zf=0.05 and zf=0.95 with r ≈ 0.9·RM.
    # They're very close to the tip AND nearly full-width, forcing the
    # point-tangent surface to bend into a hemispherical cap.
    # (z_frac, x_off_frac_of_W, y_off_frac_of_W, r_frac_of_RM)
    sections = [
        (0.00,  0.0,  0.0, None),   # bottom tip
        (0.05,  0.0,  0.0, 0.90),   # near-hemisphere cap
        (0.25,  0.7,  0.0, 1.00),
        (0.45,  0.4,  1.0, 1.00),
        (0.55, -0.4,  1.0, 1.00),
        (0.75, -0.7,  0.0, 1.00),
        (0.95,  0.0,  0.0, 0.90),   # near-hemisphere cap
        (1.00,  0.0,  0.0, None),   # top tip
    ]

    loft_inp = root.features.loftFeatures.createInput(NEWBODY)
    tip_sections = []

    for i, (zf, xf, yf, rf) in enumerate(sections):
        z = zf * H
        bx = cx + xf * W
        by = cy + yf * W

        if zf == 0.0:
            plane = root.xYConstructionPlane
        else:
            cpi = root.constructionPlanes.createInput()
            cpi.setByOffset(root.xYConstructionPlane, VI(f"bl_h * {zf}"))
            plane = root.constructionPlanes.add(cpi)
            plane.name = f"Bl_Pl{i}"

        sk = root.sketches.add(plane)
        sk.name = f"Bl_Sk{i}"
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

    for s in tip_sections:
        s.setPointTangentEndCondition(VI("bl_weight"))

    loft_inp.isSolid = True
    loft_inp.isTangentEdgesMerged = True
    loft = root.features.loftFeatures.add(loft_inp)
    loft.name = "BlobLoft"
    loft.bodies.item(0).name = "Blob"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
