"""Fixture: Surface loft (isSolid=False).

Two OPEN sketch curves (half-arcs) lofted into a surface body rather
than a solid. Surface lofts are useful for building complex shape
definitions that are later thickened, trimmed, or used as split tools.
The result is a sheet body with zero volume.
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

    params.add("sf_cx", VI("25 cm"), "cm", "Anchor X")
    params.add("sf_cy", VI("50 cm"), "cm", "Anchor Y")
    params.add("sf_r1", VI("3 cm"), "cm", "Bottom arc radius")
    params.add("sf_r2", VI("2 cm"), "cm", "Top arc radius")
    params.add("sf_h", VI("8 cm"), "cm", "Height")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    cx, cy = ev("sf_cx"), ev("sf_cy")
    r1, r2, h = ev("sf_r1"), ev("sf_r2"), ev("sf_h")

    # Bottom: a half-arc (open curve) on XY plane.
    sk1 = root.sketches.add(root.xYConstructionPlane)
    sk1.name = "Surf_Bottom"
    # Three-point arc: left end, apex, right end (open curve, not a closed profile).
    arc1 = sk1.sketchCurves.sketchArcs.addByThreePoints(
        P(cx - r1, cy, 0), P(cx, cy + r1, 0), P(cx + r1, cy, 0))

    # Top plane
    cpi = root.constructionPlanes.createInput()
    cpi.setByOffset(root.xYConstructionPlane, VI("sf_h"))
    cp_top = root.constructionPlanes.add(cpi)
    cp_top.name = "Surf_TopPl"

    sk2 = root.sketches.add(cp_top)
    sk2.name = "Surf_Top"
    tL = sk2.modelToSketchSpace(P(cx - r2, cy, h))
    tA = sk2.modelToSketchSpace(P(cx, cy + r2, h))
    tR = sk2.modelToSketchSpace(P(cx + r2, cy, h))
    arc2 = sk2.sketchCurves.sketchArcs.addByThreePoints(
        P(tL.x, tL.y, 0), P(tA.x, tA.y, 0), P(tR.x, tR.y, 0))

    # Loft the open curves as sections — must pass the curve itself, not a profile.
    loft_inp = root.features.loftFeatures.createInput(NEWBODY)
    loft_inp.loftSections.add(arc1)
    loft_inp.loftSections.add(arc2)
    loft_inp.isSolid = False  # ← surface, not solid
    loft = root.features.loftFeatures.add(loft_inp)
    loft.name = "SurfaceLoft"
    loft.bodies.item(0).name = "SurfPatch"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
