"""Fixture: Loft between two kidney/bean-shaped closed-spline sections.

Each section is drawn as a closed fitted spline (sketchFittedSplines.add
with isClosed=True). The radius is modulated by angle to produce an
asymmetric bean: narrower on one side, bulged on the other. The top
section is rotated 90° so the loft twists between sections.

Closed fitted splines form a Profile automatically — the sketch's
profiles.item(0) is the lofted region.
"""
import math
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

    params.add("kd_cx", VI("0 cm"), "cm", "Anchor X")
    params.add("kd_cy", VI("125 cm"), "cm", "Anchor Y")
    params.add("kd_r_bot", VI("3 cm"), "cm", "Bottom kidney size")
    params.add("kd_r_top", VI("2 cm"), "cm", "Top kidney size")
    params.add("kd_h", VI("10 cm"), "cm", "Loft height")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    cx, cy = ev("kd_cx"), ev("kd_cy")
    rb, rt, h = ev("kd_r_bot"), ev("kd_r_top"), ev("kd_h")

    def kidney_offsets(scale, rot_deg, n=16):
        rot = math.radians(rot_deg)
        pts = []
        for i in range(n):
            a = i * 2.0 * math.pi / n
            # Asymmetric bean: smaller on right (a≈0), bulge on left (a≈π),
            # slight lobing from the 2a term
            r = scale * (1.0 + 0.30 * math.sin(2 * a) - 0.45 * math.cos(a))
            pts.append((r * math.cos(a + rot), r * math.sin(a + rot)))
        return pts

    def add_closed_spline(sketch, ctr_sk, offsets):
        pts = adsk.core.ObjectCollection.create()
        for (dx, dy) in offsets:
            pts.add(P(ctr_sk.x + dx, ctr_sk.y + dy, 0))
        sp = sketch.sketchCurves.sketchFittedSplines.add(pts)
        sp.isClosed = True
        return sp

    # Bottom kidney on XY
    sk1 = root.sketches.add(root.xYConstructionPlane); sk1.name = "Kd_Bot"
    ctr1 = sk1.modelToSketchSpace(P(cx, cy, 0))
    add_closed_spline(sk1, ctr1, kidney_offsets(rb, 0))

    # Top kidney on offset plane, rotated 90°
    cpi = root.constructionPlanes.createInput()
    cpi.setByOffset(root.xYConstructionPlane, VI("kd_h"))
    cp_top = root.constructionPlanes.add(cpi); cp_top.name = "Kd_TopPl"
    sk2 = root.sketches.add(cp_top); sk2.name = "Kd_Top"
    ctr2 = sk2.modelToSketchSpace(P(cx, cy, h))
    add_closed_spline(sk2, ctr2, kidney_offsets(rt, 90))

    loft_inp = root.features.loftFeatures.createInput(NEWBODY)
    loft_inp.loftSections.add(sk1.profiles.item(0))
    loft_inp.loftSections.add(sk2.profiles.item(0))
    loft_inp.isSolid = True
    loft = root.features.loftFeatures.add(loft_inp)
    loft.name = "KidneyLoft"
    loft.bodies.item(0).name = "Kidney"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
