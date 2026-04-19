"""Fixture: 1→3→1 tube manifold from three parallel lofts + JOIN.

Loft is sequential (1 section → next section) — it can't branch. To get
a 1-to-3-to-1 manifold (one trunk in, three tubes in the middle, one
trunk out) we build THREE independent 4-section lofts that share the
same top and bottom profiles. Each branch bulges to its own position at
mid-height. A Combine/JOIN fuses all three bodies into one manifold.

The shared start/end profiles ensure the three branches merge seamlessly
at the trunk (no leaks, no coincident overlap — they share the identical
profile geometry, so Fusion stitches the surfaces into one solid on JOIN).
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
    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation

    params.add("mf_cx", VI("0 cm"), "cm", "Anchor X")
    params.add("mf_cy", VI("100 cm"), "cm", "Anchor Y")
    params.add("mf_r_trunk", VI("2.5 cm"), "cm", "Trunk (top+bot) radius")
    params.add("mf_r_branch", VI("1.2 cm"), "cm", "Branch tube radius")
    params.add("mf_h", VI("14 cm"), "cm", "Total height")
    params.add("mf_offset", VI("3 cm"), "cm", "Branch radial offset from axis")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    cx, cy = ev("mf_cx"), ev("mf_cy")
    rt, rb = ev("mf_r_trunk"), ev("mf_r_branch")
    h, off = ev("mf_h"), ev("mf_offset")

    # Bottom trunk at z=0
    sk_bot = root.sketches.add(root.xYConstructionPlane); sk_bot.name = "Mf_Bot"
    c_bot = sk_bot.sketchCurves.sketchCircles.addByCenterRadius(P(cx, cy, 0), rt)
    sk_bot.sketchDimensions.addDiameterDimension(c_bot,
        P(cx + rt + 0.5, cy, 0)).parameter.expression = "mf_r_trunk * 2"

    # Top trunk at z=h
    cpi_top = root.constructionPlanes.createInput()
    cpi_top.setByOffset(root.xYConstructionPlane, VI("mf_h"))
    cp_top = root.constructionPlanes.add(cpi_top); cp_top.name = "Mf_TopPl"
    sk_top = root.sketches.add(cp_top); sk_top.name = "Mf_Top"
    top_ctr = sk_top.modelToSketchSpace(P(cx, cy, h))
    c_top = sk_top.sketchCurves.sketchCircles.addByCenterRadius(
        P(top_ctr.x, top_ctr.y, 0), rt)
    sk_top.sketchDimensions.addDiameterDimension(c_top,
        P(top_ctr.x + rt + 0.5, top_ctr.y, 0)).parameter.expression = "mf_r_trunk * 2"

    # Branch planes at h/3 and 2h/3
    cpi_lo = root.constructionPlanes.createInput()
    cpi_lo.setByOffset(root.xYConstructionPlane, VI("mf_h / 3"))
    cp_lo = root.constructionPlanes.add(cpi_lo); cp_lo.name = "Mf_LoPl"

    cpi_hi = root.constructionPlanes.createInput()
    cpi_hi.setByOffset(root.xYConstructionPlane, VI("2 * mf_h / 3"))
    cp_hi = root.constructionPlanes.add(cpi_hi); cp_hi.name = "Mf_HiPl"

    sk_lo = root.sketches.add(cp_lo); sk_lo.name = "Mf_Lo"
    sk_hi = root.sketches.add(cp_hi); sk_hi.name = "Mf_Hi"

    # 3 branch circles on each mid plane, 120° apart
    branch_centers_sk = []
    for i in range(3):
        a = i * 2.0 * math.pi / 3.0
        bx = cx + off * math.cos(a)
        by = cy + off * math.sin(a)
        lo = sk_lo.modelToSketchSpace(P(bx, by, h / 3))
        hi = sk_hi.modelToSketchSpace(P(bx, by, 2 * h / 3))
        sk_lo.sketchCurves.sketchCircles.addByCenterRadius(P(lo.x, lo.y, 0), rb)
        sk_hi.sketchCurves.sketchCircles.addByCenterRadius(P(hi.x, hi.y, 0), rb)
        branch_centers_sk.append(((lo.x, lo.y), (hi.x, hi.y)))

    def profile_at(sk, x, y, tol=0.05):
        for p_i in range(sk.profiles.count):
            pr = sk.profiles.item(p_i)
            bb = pr.boundingBox
            px = (bb.minPoint.x + bb.maxPoint.x) / 2
            py = (bb.minPoint.y + bb.maxPoint.y) / 2
            if abs(px - x) < tol and abs(py - y) < tol:
                return pr
        return None

    # Build 3 lofts — each bot_profile → branch_lo_i → branch_hi_i → top_profile
    bodies = []
    for i in range(3):
        (lx, ly), (hx, hy) = branch_centers_sk[i]
        loft_inp = root.features.loftFeatures.createInput(NEWBODY)
        loft_inp.loftSections.add(sk_bot.profiles.item(0))
        loft_inp.loftSections.add(profile_at(sk_lo, lx, ly))
        loft_inp.loftSections.add(profile_at(sk_hi, hx, hy))
        loft_inp.loftSections.add(sk_top.profiles.item(0))
        loft_inp.isSolid = True
        loft = root.features.loftFeatures.add(loft_inp)
        loft.name = f"Mf_Branch{i}"
        bodies.append(loft.bodies.item(0))

    # JOIN the three branches into one manifold body
    tools = adsk.core.ObjectCollection.create()
    for b in bodies[1:]:
        tools.add(b)
    comb_inp = root.features.combineFeatures.createInput(bodies[0], tools)
    comb_inp.operation = JOIN
    root.features.combineFeatures.add(comb_inp)
    bodies[0].name = "Manifold"

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
