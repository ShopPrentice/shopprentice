"""Fixture: Combine feature.

Tests CUT with keepTool=True and JOIN operations.
"""
import adsk.core, adsk.fusion


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters

    P = adsk.core.Point3D.create
    NEWBODY = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation

    params.add("board_w", adsk.core.ValueInput.createByString("12 cm"), "cm", "Board width")
    params.add("board_d", adsk.core.ValueInput.createByString("8 cm"), "cm", "Board depth")
    params.add("board_h", adsk.core.ValueInput.createByString("2 cm"), "cm", "Board height")
    params.add("tenon_w", adsk.core.ValueInput.createByString("4 cm"), "cm", "Tenon width")
    params.add("tenon_d", adsk.core.ValueInput.createByString("3 cm"), "cm", "Tenon depth")
    params.add("tenon_h", adsk.core.ValueInput.createByString("1.5 cm"), "cm", "Tenon height")

    ev = lambda e: params.itemByName(e).value if params.itemByName(e) else design.unitsManager.evaluateExpression(e, "cm")

    # ── Sketch 1: board ──
    sk1 = root.sketches.add(root.xYConstructionPlane)
    sk1.name = "BoardProfile"
    bw, bd = ev("board_w"), ev("board_d")
    rect = sk1.sketchCurves.sketchLines.addTwoPointRectangle(P(0, 0, 0), P(bw, bd, 0))
    gc = sk1.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    dm = sk1.sketchDimensions
    dm.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(bw/2, -1, 0)).parameter.expression = "board_w"
    dm.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(bw+1, bd/2, 0)).parameter.expression = "board_d"

    # ── Extrude: board ──
    inp1 = root.features.extrudeFeatures.createInput(sk1.profiles.item(0), NEWBODY)
    inp1.setDistanceExtent(False, adsk.core.ValueInput.createByString("board_h"))
    ext1 = root.features.extrudeFeatures.add(inp1)
    ext1.name = "BoardExtrude"
    board = ext1.bodies.item(0)
    board.name = "Board"

    # ── Sketch 2: tenon (centered on board) ──
    sk2 = root.sketches.add(root.xYConstructionPlane)
    sk2.name = "TenonProfile"
    tw, td = ev("tenon_w"), ev("tenon_d")
    ox = (bw - tw) / 2
    oy = (bd - td) / 2
    rect2 = sk2.sketchCurves.sketchLines.addTwoPointRectangle(P(ox, oy, 0), P(ox + tw, oy + td, 0))
    gc2 = sk2.geometricConstraints
    gc2.addHorizontal(rect2[0]); gc2.addHorizontal(rect2[2])
    gc2.addVertical(rect2[1]); gc2.addVertical(rect2[3])
    dm2 = sk2.sketchDimensions
    dm2.addDistanceDimension(rect2[0].startSketchPoint, rect2[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(ox + tw/2, oy - 1, 0)).parameter.expression = "tenon_w"
    dm2.addDistanceDimension(rect2[1].startSketchPoint, rect2[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(ox + tw + 1, oy + td/2, 0)).parameter.expression = "tenon_d"

    # ── Extrude: tenon body ──
    inp2 = root.features.extrudeFeatures.createInput(sk2.profiles.item(0), NEWBODY)
    inp2.setDistanceExtent(False, adsk.core.ValueInput.createByString("board_h + tenon_h"))
    ext2 = root.features.extrudeFeatures.add(inp2)
    ext2.name = "TenonExtrude"
    tenon = ext2.bodies.item(0)
    tenon.name = "Tenon"

    # ── Combine: CUT tenon into board (keepTool=True) ──
    coll = adsk.core.ObjectCollection.create()
    coll.add(tenon)
    comb_inp = root.features.combineFeatures.createInput(board, coll)
    comb_inp.operation = CUT
    comb_inp.isKeepToolBodies = True
    comb1 = root.features.combineFeatures.add(comb_inp)
    comb1.name = "MortiseCut"

    # ── Combine: JOIN tenon to board ──
    coll2 = adsk.core.ObjectCollection.create()
    coll2.add(tenon)
    comb_inp2 = root.features.combineFeatures.createInput(board, coll2)
    comb_inp2.operation = JOIN
    comb_inp2.isKeepToolBodies = False
    comb2 = root.features.combineFeatures.add(comb_inp2)
    comb2.name = "TenonJoin"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
