"""Fixture: Pattern of a body that has CUT history.

Tests the ghost-body problem: when a body with CUT operations in its
timeline is patterned, Fusion replays the CUT at each instance.
The workaround is to use a Python loop instead of body_pattern.
This fixture validates that the capture→export pipeline handles
this case correctly (by detecting the loop vs pattern).
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

    params.add("board_w", adsk.core.ValueInput.createByString("20 cm"), "cm", "")
    params.add("board_d", adsk.core.ValueInput.createByString("5 cm"), "cm", "")
    params.add("board_h", adsk.core.ValueInput.createByString("2 cm"), "cm", "")
    params.add("domino_w", adsk.core.ValueInput.createByString("2 cm"), "cm", "")
    params.add("domino_d", adsk.core.ValueInput.createByString("1 cm"), "cm", "")
    params.add("domino_h", adsk.core.ValueInput.createByString("3 cm"), "cm", "")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                     else design.unitsManager.evaluateExpression(e, "cm"))

    # ── Board ──
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

    inp1 = root.features.extrudeFeatures.createInput(sk1.profiles.item(0), NEWBODY)
    inp1.setDistanceExtent(False, adsk.core.ValueInput.createByString("board_h"))
    ext1 = root.features.extrudeFeatures.add(inp1)
    ext1.name = "BoardExtrude"
    board = ext1.bodies.item(0)
    board.name = "Board"

    # ── Single domino (loop-created, not patterned) ──
    # Create 3 dominos at x = 3, 9, 15 using a loop
    dw, dd, dh = ev("domino_w"), ev("domino_d"), ev("domino_h")
    bh = ev("board_h")
    for i, x_pos in enumerate([3.0, 9.0, 15.0]):
        # Sketch for each domino on top face
        cp_inp = root.constructionPlanes.createInput()
        cp_inp.setByOffset(root.xYConstructionPlane, adsk.core.ValueInput.createByString("board_h"))
        cp = root.constructionPlanes.add(cp_inp)
        cp.name = f"DominoPlane{i}"

        sk = root.sketches.add(cp)
        sk.name = f"DominoProfile{i}"
        cy = bd / 2
        rect2 = sk.sketchCurves.sketchLines.addTwoPointRectangle(
            P(x_pos - dw/2, cy - dd/2, 0),
            P(x_pos + dw/2, cy + dd/2, 0))
        gc2 = sk.geometricConstraints
        gc2.addHorizontal(rect2[0]); gc2.addHorizontal(rect2[2])
        gc2.addVertical(rect2[1]); gc2.addVertical(rect2[3])
        dm2 = sk.sketchDimensions
        dm2.addDistanceDimension(rect2[0].startSketchPoint, rect2[0].endSketchPoint,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
            P(x_pos, cy - dd/2 - 1, 0)).parameter.expression = "domino_w"
        dm2.addDistanceDimension(rect2[1].startSketchPoint, rect2[1].endSketchPoint,
            adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
            P(x_pos + dw/2 + 1, cy, 0)).parameter.expression = "domino_d"

        inp2 = root.features.extrudeFeatures.createInput(sk.profiles.item(0), NEWBODY)
        inp2.setDistanceExtent(False, adsk.core.ValueInput.createByString("domino_h"))
        ext2 = root.features.extrudeFeatures.add(inp2)
        ext2.name = f"DominoExtrude{i}"
        domino = ext2.bodies.item(0)
        domino.name = f"Domino{i}"

        # CUT into board (keepTool=True)
        coll = adsk.core.ObjectCollection.create()
        coll.add(domino)
        comb_inp = root.features.combineFeatures.createInput(board, coll)
        comb_inp.operation = CUT
        comb_inp.isKeepToolBodies = True
        comb = root.features.combineFeatures.add(comb_inp)
        comb.name = f"DominoCut{i}"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
