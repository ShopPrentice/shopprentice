"""Fixture: Loft feature — basic multi-section lofts without rails.

Tests a 2-section loft (square → circle on an offset plane) and a 3-section
loft (vase: wide → narrow → wide between three parallel planes).
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

    # Parameters
    params.add("loft_cx", VI("0 cm"), "cm", "Loft1 center X")
    params.add("loft_cy", VI("0 cm"), "cm", "Loft1 center Y")
    params.add("loft_w", VI("6 cm"), "cm", "Square base side")
    params.add("loft_h", VI("10 cm"), "cm", "Loft height")
    params.add("loft_r", VI("2 cm"), "cm", "Top circle radius")
    params.add("vase_cx", VI("25 cm"), "cm", "Vase center X")
    params.add("vase_cy", VI("0 cm"), "cm", "Vase center Y")
    params.add("vase_r1", VI("3 cm"), "cm", "Vase base radius")
    params.add("vase_r2", VI("1 cm"), "cm", "Vase waist radius")
    params.add("vase_r3", VI("2.5 cm"), "cm", "Vase top radius")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    # ════════════════════════════════════════════════════════════
    # LOFT 1 — two sections: square base → circle on offset plane
    # ════════════════════════════════════════════════════════════
    w = ev("loft_w")
    h = ev("loft_h")
    lcx, lcy = ev("loft_cx"), ev("loft_cy")
    # Square centered at (lcx, lcy)
    x0, y0 = lcx - w/2, lcy - w/2
    x1, y1 = lcx + w/2, lcy + w/2

    # Sketch 1a: square on XY plane, centered at (lcx, lcy)
    sk1 = root.sketches.add(root.xYConstructionPlane)
    sk1.name = "Loft1_Square"
    rect = sk1.sketchCurves.sketchLines.addTwoPointRectangle(P(x0, y0, 0), P(x1, y1, 0))
    gc = sk1.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    dm = sk1.sketchDimensions
    dm.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(lcx, y0 - 1, 0)).parameter.expression = "loft_w"
    dm.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(x1 + 1, lcy, 0)).parameter.expression = "loft_w"

    # Offset construction plane at z = loft_h
    cpi1 = root.constructionPlanes.createInput()
    cpi1.setByOffset(root.xYConstructionPlane, VI("loft_h"))
    cp_top = root.constructionPlanes.add(cpi1)
    cp_top.name = "Loft1_TopPlane"

    # Sketch 1b: circle on offset plane, centered over the square
    sk2 = root.sketches.add(cp_top)
    sk2.name = "Loft1_Circle"
    sk_ctr = sk2.modelToSketchSpace(P(lcx, lcy, h))
    r_top = ev("loft_r")
    circle = sk2.sketchCurves.sketchCircles.addByCenterRadius(
        P(sk_ctr.x, sk_ctr.y, 0), r_top)
    sk2.sketchDimensions.addDiameterDimension(circle,
        P(sk_ctr.x + r_top + 0.5, sk_ctr.y, 0)).parameter.expression = "loft_r * 2"

    # Create the loft — 2 sections, solid, default alignment
    loft_inp = root.features.loftFeatures.createInput(NEWBODY)
    loft_inp.loftSections.add(sk1.profiles.item(0))
    loft_inp.loftSections.add(sk2.profiles.item(0))
    loft_inp.isSolid = True
    loft1 = root.features.loftFeatures.add(loft_inp)
    loft1.name = "SquareToCircleLoft"
    loft1.bodies.item(0).name = "Loft1"

    # ════════════════════════════════════════════════════════════
    # LOFT 2 — three sections: wide → narrow → wide (vase)
    # ════════════════════════════════════════════════════════════
    r1, r2, r3 = ev("vase_r1"), ev("vase_r2"), ev("vase_r3")
    vcx, vcy = ev("vase_cx"), ev("vase_cy")

    # Sketch 3: base circle on XY
    sk3 = root.sketches.add(root.xYConstructionPlane)
    sk3.name = "Vase_Bottom"
    c1 = sk3.sketchCurves.sketchCircles.addByCenterRadius(P(vcx, vcy, 0), r1)
    sk3.sketchDimensions.addDiameterDimension(c1,
        P(vcx + r1 + 0.5, vcy, 0)).parameter.expression = "vase_r1 * 2"

    # Mid plane at z = loft_h / 2
    cpi2 = root.constructionPlanes.createInput()
    cpi2.setByOffset(root.xYConstructionPlane, VI("loft_h / 2"))
    cp_mid = root.constructionPlanes.add(cpi2)
    cp_mid.name = "Vase_MidPlane"

    # Sketch 4: waist circle on mid plane
    sk4 = root.sketches.add(cp_mid)
    sk4.name = "Vase_Waist"
    mid_ctr = sk4.modelToSketchSpace(P(vcx, vcy, h / 2))
    c2 = sk4.sketchCurves.sketchCircles.addByCenterRadius(
        P(mid_ctr.x, mid_ctr.y, 0), r2)
    sk4.sketchDimensions.addDiameterDimension(c2,
        P(mid_ctr.x + r2 + 0.5, mid_ctr.y, 0)).parameter.expression = "vase_r2 * 2"

    # Top plane at z = loft_h
    cpi3 = root.constructionPlanes.createInput()
    cpi3.setByOffset(root.xYConstructionPlane, VI("loft_h"))
    cp_vtop = root.constructionPlanes.add(cpi3)
    cp_vtop.name = "Vase_TopPlane"

    # Sketch 5: top circle on top plane
    sk5 = root.sketches.add(cp_vtop)
    sk5.name = "Vase_Top"
    top_ctr = sk5.modelToSketchSpace(P(vcx, vcy, h))
    c3 = sk5.sketchCurves.sketchCircles.addByCenterRadius(
        P(top_ctr.x, top_ctr.y, 0), r3)
    sk5.sketchDimensions.addDiameterDimension(c3,
        P(top_ctr.x + r3 + 0.5, top_ctr.y, 0)).parameter.expression = "vase_r3 * 2"

    # Create the 3-section loft
    loft_inp2 = root.features.loftFeatures.createInput(NEWBODY)
    loft_inp2.loftSections.add(sk3.profiles.item(0))
    loft_inp2.loftSections.add(sk4.profiles.item(0))
    loft_inp2.loftSections.add(sk5.profiles.item(0))
    loft_inp2.isSolid = True
    loft2 = root.features.loftFeatures.add(loft_inp2)
    loft2.name = "VaseLoft"
    loft2.bodies.item(0).name = "Vase"

    # Fit view
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
