"""Fixture: Twisted 5-lobed star loft from closed-spline sections.

Three closed-spline sections: 10 fit points alternating between an outer
and an inner radius, making a 5-pointed star. Each section is rotated a
bit more than the last (0°, 24°, 48°) so the loft has a visible twist —
the star pattern spirals as it rises.

Fitted splines soften the star points into rounded lobes. The result is
a twisted 5-lobed column with smooth flanks — the kind of shape that's
hard to make with prismatic extrudes.
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

    params.add("st_cx", VI("25 cm"), "cm", "Anchor X")
    params.add("st_cy", VI("125 cm"), "cm", "Anchor Y")
    params.add("st_ro", VI("3 cm"), "cm", "Outer (point) radius")
    params.add("st_ri", VI("1.5 cm"), "cm", "Inner (valley) radius")
    params.add("st_h", VI("12 cm"), "cm", "Total height")
    params.add("st_twist", VI("48"), "", "Total twist (degrees over full height)")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    cx, cy = ev("st_cx"), ev("st_cy")
    ro, ri, h = ev("st_ro"), ev("st_ri"), ev("st_h")
    twist = ev("st_twist")

    def star_offsets(outer, inner, rot_deg, points=5):
        rot = math.radians(rot_deg)
        n = points * 2
        offs = []
        for i in range(n):
            a = i * 2.0 * math.pi / n + rot
            r = outer if i % 2 == 0 else inner
            offs.append((r * math.cos(a), r * math.sin(a)))
        return offs

    def add_closed_spline(sketch, ctr_sk, offsets):
        pts = adsk.core.ObjectCollection.create()
        for (dx, dy) in offsets:
            pts.add(P(ctr_sk.x + dx, ctr_sk.y + dy, 0))
        sp = sketch.sketchCurves.sketchFittedSplines.add(pts)
        sp.isClosed = True
        return sp

    # 3 sections at z = 0, h/2, h — star radii: full, slightly shrunk, full
    section_specs = [
        (0.0, 1.00, 0.00),
        (0.5, 0.90, twist * 0.5),
        (1.0, 1.00, twist),
    ]

    loft_inp = root.features.loftFeatures.createInput(NEWBODY)
    for i, (zf, scale, rot) in enumerate(section_specs):
        if zf == 0.0:
            plane = root.xYConstructionPlane
        else:
            cpi = root.constructionPlanes.createInput()
            cpi.setByOffset(root.xYConstructionPlane, VI(f"st_h * {zf}"))
            plane = root.constructionPlanes.add(cpi)
            plane.name = f"St_Pl{i}"
        sk = root.sketches.add(plane); sk.name = f"St_Sk{i}"
        ctr_sk = sk.modelToSketchSpace(P(cx, cy, zf * h))
        add_closed_spline(sk, ctr_sk, star_offsets(ro * scale, ri * scale, rot))
        loft_inp.loftSections.add(sk.profiles.item(0))

    loft_inp.isSolid = True
    loft_inp.isTangentEdgesMerged = True
    loft = root.features.loftFeatures.add(loft_inp)
    loft.name = "StarLoft"
    loft.bodies.item(0).name = "TwistStar"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
