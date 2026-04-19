"""Fixture: Loft as a CUT operation (shaped pocket).

Builds a block, then lofts a tapered square → circle pocket from the
block's top face down into the body. Exercises
FeatureOperations.CutFeatureOperation with participantBodies — the
loft acts as a cutting tool rather than creating a new body.
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
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation

    params.add("ct_cx", VI("46 cm"), "cm", "Anchor X (block SW corner)")
    params.add("ct_cy", VI("46 cm"), "cm", "Anchor Y (block SW corner)")
    params.add("ct_bw", VI("8 cm"), "cm", "Block width")
    params.add("ct_bd", VI("8 cm"), "cm", "Block depth")
    params.add("ct_bh", VI("6 cm"), "cm", "Block height")
    params.add("ct_top_sq", VI("4 cm"), "cm", "Top square side")
    params.add("ct_bot_r", VI("1 cm"), "cm", "Bottom circle radius")
    params.add("ct_depth", VI("4 cm"), "cm", "Pocket depth (< block height)")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    cx, cy = ev("ct_cx"), ev("ct_cy")
    bw, bd, bh = ev("ct_bw"), ev("ct_bd"), ev("ct_bh")
    sq, rb = ev("ct_top_sq"), ev("ct_bot_r")
    depth = ev("ct_depth")

    # ── Base block ──
    sk_blk = root.sketches.add(root.xYConstructionPlane)
    sk_blk.name = "Cut_Block_Sk"
    rect = sk_blk.sketchCurves.sketchLines.addTwoPointRectangle(
        P(cx, cy, 0), P(cx + bw, cy + bd, 0))
    gc = sk_blk.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    dm = sk_blk.sketchDimensions
    dm.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(cx + bw/2, cy - 1, 0)).parameter.expression = "ct_bw"
    dm.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(cx + bw + 1, cy + bd/2, 0)).parameter.expression = "ct_bd"

    blk_inp = root.features.extrudeFeatures.createInput(
        sk_blk.profiles.item(0), NEWBODY)
    blk_inp.setDistanceExtent(False, VI("ct_bh"))
    blk_ext = root.features.extrudeFeatures.add(blk_inp)
    blk_ext.name = "CutBlock_Ext"
    block = blk_ext.bodies.item(0)
    block.name = "CutBlock"

    # ── Top section: square on the block's top face (offset inward from corners) ──
    def find_top_face(body):
        best = None
        for i in range(body.faces.count):
            f = body.faces.item(i)
            g = f.geometry
            if isinstance(g, adsk.core.Plane) and abs(g.normal.z) > 0.9:
                if best is None or f.pointOnFace.z > best.pointOnFace.z:
                    best = f
        return best

    top_face = find_top_face(block)
    sk_top = root.sketches.add(top_face)
    sk_top.name = "Cut_TopSq"
    tc = sk_top.modelToSketchSpace(P(cx + bw/2, cy + bd/2, bh))
    sq_rect = sk_top.sketchCurves.sketchLines.addTwoPointRectangle(
        P(tc.x - sq/2, tc.y - sq/2, 0),
        P(tc.x + sq/2, tc.y + sq/2, 0))
    gc2 = sk_top.geometricConstraints
    gc2.addHorizontal(sq_rect[0]); gc2.addHorizontal(sq_rect[2])
    gc2.addVertical(sq_rect[1]); gc2.addVertical(sq_rect[3])
    dm2 = sk_top.sketchDimensions
    dm2.addDistanceDimension(sq_rect[0].startSketchPoint, sq_rect[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(tc.x, tc.y - sq/2 - 0.5, 0)).parameter.expression = "ct_top_sq"
    dm2.addDistanceDimension(sq_rect[1].startSketchPoint, sq_rect[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(tc.x + sq/2 + 0.5, tc.y, 0)).parameter.expression = "ct_top_sq"

    # Pick the smallest profile (the drawn square, not the surrounding face region)
    best_pi, best_area = 0, float('inf')
    for pi in range(sk_top.profiles.count):
        bb = sk_top.profiles.item(pi).boundingBox
        area = abs(bb.maxPoint.x - bb.minPoint.x) * abs(bb.maxPoint.y - bb.minPoint.y)
        if area < best_area:
            best_area, best_pi = area, pi
    top_profile = sk_top.profiles.item(best_pi)

    # ── Bottom section: small circle at z = bh - depth ──
    cpi_bot = root.constructionPlanes.createInput()
    cpi_bot.setByOffset(root.xYConstructionPlane, VI("ct_bh - ct_depth"))
    cp_bot = root.constructionPlanes.add(cpi_bot)
    cp_bot.name = "Cut_BottomPl"
    sk_bot = root.sketches.add(cp_bot)
    sk_bot.name = "Cut_BotCircle"
    bc = sk_bot.modelToSketchSpace(P(cx + bw/2, cy + bd/2, bh - depth))
    circ = sk_bot.sketchCurves.sketchCircles.addByCenterRadius(
        P(bc.x, bc.y, 0), rb)
    sk_bot.sketchDimensions.addDiameterDimension(circ,
        P(bc.x + rb + 0.5, bc.y, 0)).parameter.expression = "ct_bot_r * 2"

    # ── Loft as CUT ──
    loft_inp = root.features.loftFeatures.createInput(CUT)
    loft_inp.loftSections.add(top_profile)
    loft_inp.loftSections.add(sk_bot.profiles.item(0))
    loft_inp.participantBodies = [block]
    loft_inp.isSolid = True
    loft = root.features.loftFeatures.add(loft_inp)
    loft.name = "LoftPocket"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
