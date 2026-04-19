"""Fixture: Loft between cardioid (leaf / teardrop) closed-spline sections.

Each section is a cardioid — r(a) = scale · (1 − cos(a)) rotated to face
a given direction. The cusp ends up at the tip; the round end opposite.
Three sections stack: large leaf at the bottom, medium twisted 60° at
the middle, small twisted 120° at the top, so the tip spirals as it rises.

Cardioid fit points include a zero-radius point at the cusp, which the
fitted spline smooths into a sharp but continuous tail (not a true cusp,
but close enough visually).
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

    params.add("lf_cx", VI("50 cm"), "cm", "Anchor X")
    params.add("lf_cy", VI("125 cm"), "cm", "Anchor Y")
    params.add("lf_scale_bot", VI("2.0 cm"), "cm", "Bottom leaf scale")
    params.add("lf_scale_mid", VI("1.5 cm"), "cm", "Middle leaf scale")
    params.add("lf_scale_top", VI("1.0 cm"), "cm", "Top leaf scale")
    params.add("lf_h", VI("12 cm"), "cm", "Loft height")
    params.add("lf_twist", VI("120"), "", "Total twist (deg)")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    cx, cy = ev("lf_cx"), ev("lf_cy")
    sb, sm, st = ev("lf_scale_bot"), ev("lf_scale_mid"), ev("lf_scale_top")
    h = ev("lf_h")
    twist = ev("lf_twist")

    def leaf_offsets(scale, rot_deg, n=24):
        """Cardioid: r(a) = scale*(1 - cos(a)). Tip points along +rot direction."""
        rot = math.radians(rot_deg)
        # Skip a=0 (r=0, degenerate) — start at a>0 to avoid duplicate
        # sketch points at the cusp.
        offs = []
        for i in range(1, n + 1):
            a = i * 2.0 * math.pi / (n + 1)
            r = scale * (1.0 - math.cos(a))
            # Cardioid natural orientation has cusp at +x. Rotate by rot_deg.
            x = r * math.cos(a)
            y = r * math.sin(a)
            xr = x * math.cos(rot) - y * math.sin(rot)
            yr = x * math.sin(rot) + y * math.cos(rot)
            offs.append((xr, yr))
        return offs

    def add_closed_spline(sketch, ctr_sk, offsets):
        pts = adsk.core.ObjectCollection.create()
        for (dx, dy) in offsets:
            pts.add(P(ctr_sk.x + dx, ctr_sk.y + dy, 0))
        sp = sketch.sketchCurves.sketchFittedSplines.add(pts)
        sp.isClosed = True
        return sp

    section_specs = [
        (0.0, sb, 0.0),
        (0.5, sm, twist * 0.5),
        (1.0, st, twist),
    ]

    loft_inp = root.features.loftFeatures.createInput(NEWBODY)
    for i, (zf, scale, rot) in enumerate(section_specs):
        if zf == 0.0:
            plane = root.xYConstructionPlane
        else:
            cpi = root.constructionPlanes.createInput()
            cpi.setByOffset(root.xYConstructionPlane, VI(f"lf_h * {zf}"))
            plane = root.constructionPlanes.add(cpi)
            plane.name = f"Lf_Pl{i}"
        sk = root.sketches.add(plane); sk.name = f"Lf_Sk{i}"
        ctr_sk = sk.modelToSketchSpace(P(cx, cy, zf * h))
        add_closed_spline(sk, ctr_sk, leaf_offsets(scale, rot))
        loft_inp.loftSections.add(sk.profiles.item(0))

    loft_inp.isSolid = True
    loft_inp.isTangentEdgesMerged = True
    loft = root.features.loftFeatures.add(loft_inp)
    loft.name = "LeafLoft"
    loft.bodies.item(0).name = "TwistLeaf"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
