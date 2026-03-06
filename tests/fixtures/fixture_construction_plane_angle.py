"""Fixture: AtAngle construction plane + sketch + extrude.

Tests at-angle construction plane (rotated around a body edge),
then sketching and extruding on the angled plane.
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

    params.add("base_w", adsk.core.ValueInput.createByString("10 cm"), "cm", "Base width")
    params.add("base_d", adsk.core.ValueInput.createByString("8 cm"), "cm", "Base depth")
    params.add("base_h", adsk.core.ValueInput.createByString("3 cm"), "cm", "Base height")
    params.add("angle_val", adsk.core.ValueInput.createByString("45 deg"), "deg", "Plane angle")
    params.add("wedge_w", adsk.core.ValueInput.createByString("6 cm"), "cm", "Wedge width")
    params.add("wedge_d", adsk.core.ValueInput.createByString("4 cm"), "cm", "Wedge depth")
    params.add("wedge_h", adsk.core.ValueInput.createByString("2 cm"), "cm", "Wedge height")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                     else design.unitsManager.evaluateExpression(e, "cm"))

    # ── Base box ──
    sk1 = root.sketches.add(root.xYConstructionPlane)
    sk1.name = "BaseProfile"
    w, d = ev("base_w"), ev("base_d")
    rect = sk1.sketchCurves.sketchLines.addTwoPointRectangle(P(0, 0, 0), P(w, d, 0))
    gc = sk1.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    dm = sk1.sketchDimensions
    dm.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(w/2, -1, 0)).parameter.expression = "base_w"
    dm.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(w+1, d/2, 0)).parameter.expression = "base_d"

    inp1 = root.features.extrudeFeatures.createInput(sk1.profiles.item(0), NEWBODY)
    inp1.setDistanceExtent(False, adsk.core.ValueInput.createByString("base_h"))
    ext1 = root.features.extrudeFeatures.add(inp1)
    ext1.name = "BaseExtrude"
    ext1.bodies.item(0).name = "Base"

    # ── Find a top edge of the base (along X axis at Z = base_h, Y = 0) ──
    base_body = ext1.bodies.item(0)
    h = ev("base_h")
    target_edge = None
    for ei in range(base_body.edges.count):
        e = base_body.edges.item(ei)
        sv, ev2 = e.startVertex.geometry, e.endVertex.geometry
        # Edge along X at Y=0, Z=base_h
        if (abs(sv.z - h) < 0.01 and abs(ev2.z - h) < 0.01 and
            abs(sv.y) < 0.01 and abs(ev2.y) < 0.01):
            target_edge = e
            break
    if not target_edge:
        target_edge = root.xConstructionAxis

    # ── AtAngle plane: rotate 45 deg around the top edge, from XY plane ──
    cp_inp = root.constructionPlanes.createInput()
    cp_inp.setByAngle(target_edge, adsk.core.ValueInput.createByString("angle_val"), root.xYConstructionPlane)
    angled_plane = root.constructionPlanes.add(cp_inp)
    angled_plane.name = "AngledPlane"

    # ── Sketch on angled plane ──
    sk2 = root.sketches.add(angled_plane)
    sk2.name = "WedgeProfile"
    ww, wd = ev("wedge_w"), ev("wedge_d")
    rect2 = sk2.sketchCurves.sketchLines.addTwoPointRectangle(P(0, 0, 0), P(ww, wd, 0))
    gc2 = sk2.geometricConstraints
    gc2.addHorizontal(rect2[0]); gc2.addHorizontal(rect2[2])
    gc2.addVertical(rect2[1]); gc2.addVertical(rect2[3])
    dm2 = sk2.sketchDimensions
    dm2.addDistanceDimension(rect2[0].startSketchPoint, rect2[0].endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        P(ww/2, -1, 0)).parameter.expression = "wedge_w"
    dm2.addDistanceDimension(rect2[1].startSketchPoint, rect2[1].endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        P(ww+1, wd/2, 0)).parameter.expression = "wedge_d"

    # ── Extrude on angled plane ──
    inp2 = root.features.extrudeFeatures.createInput(sk2.profiles.item(0), NEWBODY)
    inp2.setDistanceExtent(False, adsk.core.ValueInput.createByString("wedge_h"))
    ext2 = root.features.extrudeFeatures.add(inp2)
    ext2.name = "WedgeExtrude"
    ext2.bodies.item(0).name = "Wedge"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
