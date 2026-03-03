"""Fixture: SplitBody with multiple splitting tools.

Creates a tall box, then splits it with two planes to produce 3 pieces.
Tests that capture correctly records splitting tools and output bodies.
"""
import adsk.core, adsk.fusion


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters

    params.add("box_w", adsk.core.ValueInput.createByString("4 cm"), "cm", "")
    params.add("box_d", adsk.core.ValueInput.createByString("3 cm"), "cm", "")
    params.add("box_h", adsk.core.ValueInput.createByString("10 cm"), "cm", "")
    params.add("cut_z1", adsk.core.ValueInput.createByString("2 cm"), "cm", "Lower cut")
    params.add("cut_z2", adsk.core.ValueInput.createByString("8 cm"), "cm", "Upper cut")

    P = adsk.core.Point3D.create
    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
    NEWBODY = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    # ev helper
    def ev(e):
        p = params.itemByName(e)
        return p.value if p else design.unitsManager.evaluateExpression(e, "cm")

    # Sketch a rectangle on XY
    sk = root.sketches.add(root.xYConstructionPlane)
    sk.name = "BoxSketch"
    w, d = ev("box_w"), ev("box_d")
    rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(
        P(0, 0, 0), P(w, d, 0))
    gc = sk.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    dims = sk.sketchDimensions
    dims.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        H, P(w/2, -1, 0)).parameter.expression = "box_w"
    dims.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        V, P(w+1, d/2, 0)).parameter.expression = "box_d"
    prof = sk.profiles.item(0)

    # Extrude the box
    inp = root.features.extrudeFeatures.createInput(prof, NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("box_h"))
    ext = root.features.extrudeFeatures.add(inp)
    ext.name = "BoxExtrude"
    box = ext.bodies.item(0)
    box.name = "Box"

    # Construction planes for cuts
    def off_plane(base, expr, name):
        pinp = root.constructionPlanes.createInput()
        pinp.setByOffset(base, adsk.core.ValueInput.createByString(expr))
        p = root.constructionPlanes.add(pinp)
        p.name = name
        return p

    cut_pl1 = off_plane(root.xYConstructionPlane, "cut_z1", "CutPlane1")
    cut_pl2 = off_plane(root.xYConstructionPlane, "cut_z2", "CutPlane2")

    # Split 1: split box with lower plane → 2 pieces
    split_inp1 = root.features.splitBodyFeatures.createInput(box, cut_pl1, True)
    split1 = root.features.splitBodyFeatures.add(split_inp1)
    split1.name = "Split1"

    # Find the upper piece (larger volume) for the second split
    upper = None
    for i in range(root.bRepBodies.count):
        b = root.bRepBodies.item(i)
        if b.name.startswith("Box") and b.volume > 50:
            upper = b
            break

    # Split 2: split upper piece with upper plane → now 3 total pieces
    if upper:
        split_inp2 = root.features.splitBodyFeatures.createInput(upper, cut_pl2, True)
        split2 = root.features.splitBodyFeatures.add(split_inp2)
        split2.name = "Split2"

    # Name the final bodies
    for i in range(root.bRepBodies.count):
        b = root.bRepBodies.item(i)
        if "Box" in b.name:
            if b.volume < 30:
                if b.boundingBox.minPoint.z < 1:
                    b.name = "Bottom"
                else:
                    b.name = "Top"
            else:
                b.name = "Middle"

    # Fit view
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
