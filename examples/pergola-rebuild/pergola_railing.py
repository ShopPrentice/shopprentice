"""Additive: black-aluminum deck railing around the 3 open deck edges.

Run AFTER pergola_custom.py (additive — execute_script WITHOUT clean).
Builds a `railing` component: corner posts + slim top/bottom rails + thin
vertical balusters (rectangular patterns), all powder-coat black.
Re-run guarded on an existing `railing` component.
"""
import adsk.core, adsk.fusion


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    P = adsk.core.Point3D.create
    NEWBODY = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    IN = 2.54

    for i in range(root.occurrences.count - 1, -1, -1):
        oc = root.occurrences.item(i)
        if oc.component.name == "railing":
            oc.deleteMe(); print("removed existing railing — rebuilding")

    # deck extent (cm)
    dmnx = dmny = 1e9; dmxx = dmxy = dmxz = -1e9
    for occ in root.allOccurrences:
        if occ.component.name == "deck5":
            for i in range(occ.bRepBodies.count):
                b = occ.bRepBodies.item(i).boundingBox
                dmnx = min(dmnx, b.minPoint.x); dmny = min(dmny, b.minPoint.y)
                dmxx = max(dmxx, b.maxPoint.x); dmxy = max(dmxy, b.maxPoint.y)
                dmxz = max(dmxz, b.maxPoint.z)
    # pergola posts: rail ENDS butt their inner faces; rail sits in the post depth plane
    pmny = 1e9; pbox = {}
    for occ in root.allOccurrences:
        if occ.component.name == "posts":
            for i in range(occ.bRepBodies.count):
                bd = occ.bRepBodies.item(i); bx = bd.boundingBox
                pmny = min(pmny, bx.minPoint.y)
                if bd.name in ("post1_upper", "post2_upper"):
                    pbox[bd.name] = bx
    p1, p2 = pbox["post1_upper"], pbox["post2_upper"]
    if (p1.minPoint.x + p1.maxPoint.x) > (p2.minPoint.x + p2.maxPoint.x):
        p1, p2 = p2, p1                       # p1 = left post, p2 = right post
    lp_innerX = p1.maxPoint.x                 # left post inner (+X) face
    rp_innerX = p2.minPoint.x                 # right post inner (-X) face
    rp_outerX = p2.maxPoint.x                 # right post outer (+X) face
    rp_center = (rp_innerX + rp_outerX) / 2.0 # right post X center
    post_yc = (p1.minPoint.y + p1.maxPoint.y) / 2.0   # post depth center
    post_backY = p1.maxPoint.y                # post inner (back, +Y) face
    print("deck (in): X[%.1f,%.1f] Y[%.1f,%.1f] top=%.1f  posts_minY=%.1f" % (
        dmnx/IN, dmxx/IN, dmny/IN, dmxy/IN, dmxz/IN, pmny/IN))

    rail_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    rail_occ.component.name = "railing"
    rc = rail_occ.component

    def off_plane(z_cm, name):
        inp = rc.constructionPlanes.createInput()
        inp.setByOffset(rc.xYConstructionPlane, adsk.core.ValueInput.createByString("%.6f cm" % z_cm))
        p = rc.constructionPlanes.add(inp); p.name = name
        return p

    def box(x0, y0, z0, x1, y1, z1, name):
        """Axis-aligned box (cm); XY footprint extruded +Z."""
        pl = off_plane(z0, name + "_Pl")
        sk = rc.sketches.add(pl); sk.name = name + "_Sk"
        s1 = sk.modelToSketchSpace(P(x0, y0, z0)); s2 = sk.modelToSketchSpace(P(x1, y1, z0))
        rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(P(s1.x, s1.y, 0), P(s2.x, s2.y, 0))
        gc = sk.geometricConstraints
        gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2]); gc.addVertical(rect[1]); gc.addVertical(rect[3])
        inp = rc.features.extrudeFeatures.createInput(sk.profiles.item(0), NEWBODY)
        inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("%.6f cm" % (z1 - z0)))
        f = rc.features.extrudeFeatures.add(inp); f.name = name
        bd = f.bodies.item(0); bd.name = name
        return bd, f

    def pattern(feat, axis_char, count, spacing_cm, name):
        coll = adsk.core.ObjectCollection.create(); coll.add(feat)
        qaxis = rc.xConstructionAxis if axis_char == "x" else rc.yConstructionAxis
        pf = rc.features.rectangularPatternFeatures
        inp = pf.createInput(coll, qaxis,
                             adsk.core.ValueInput.createByString(str(count)),
                             adsk.core.ValueInput.createByString("%.6f cm" % spacing_cm),
                             adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        inp.setDirectionTwo(rc.yConstructionAxis if axis_char == "x" else rc.xConstructionAxis,
                            adsk.core.ValueInput.createByString("1"),
                            adsk.core.ValueInput.createByString("0 cm"))
        p = pf.add(inp); p.name = name
        return p

    # ── geometry (cm) ────────────────────────────────────────────
    rw = 0.75 * IN             # rail half-width
    bh = 0.3125 * IN           # baluster half (0.625" sq)
    byc = dmxy                 # back line (Y=0, house)
    dz = dmxz                  # deck top
    top0, top1 = dz + 31 * IN, dz + 33 * IN   # top rail 3" lower (33" guard)
    bot0, bot1 = dz + 2 * IN, dz + 3.5 * IN
    bal0, bal1 = bot1, top0

    # No added posts. Rail ENDS butt the posts' INNER faces; rail sits in the post depth
    # plane (Y = post_yc) so the end faces actually meet the post inner faces.
    # FRONT rail: between the two posts' inner X-faces.
    box(lp_innerX, post_yc - rw, top0, rp_innerX, post_yc + rw, top1, "rail_front_top")
    box(lp_innerX, post_yc - rw, bot0, rp_innerX, post_yc + rw, bot1, "rail_front_bot")
    # RIGHT return: end butts the right post's INNER (back, +Y) face, centered on the post,
    # then runs to the house (same end-to-face connection as the front rail).
    rya, ryb = post_backY, byc - 0.5 * IN
    box(rp_center - rw, rya, top0, rp_center + rw, ryb, top1, "rail_right_top")
    box(rp_center - rw, rya, bot0, rp_center + rw, ryb, bot1, "rail_right_bot")

    # balusters
    spc = 4.5 * IN
    def balusters(axis, fixed, a, b, prefix):
        span = b - a
        n = max(1, int(round(span / spc)))
        s_act = span / n
        first = a + s_act / 2.0
        if axis == "x":
            bd, f = box(first - bh, fixed - bh, bal0, first + bh, fixed + bh, bal1, prefix + "_0")
        else:
            bd, f = box(fixed - bh, first - bh, bal0, fixed + bh, first + bh, bal1, prefix + "_0")
        pattern(f, axis, n, s_act, prefix + "_Pat")
        return n
    nf = balusters("x", post_yc, lp_innerX + 2.0 * IN, rp_innerX - 2.0 * IN, "bal_front")
    nr = balusters("y", rp_center, rya + 2.0 * IN, ryb, "bal_right")
    print("balusters front/right:", nf, nr)

    # ── black-aluminum appearance on all railing bodies ──
    try:
        alib = app.materialLibraries.itemByName("Fusion Appearance Library")
        blk = design.appearances.itemByName("RailBlack")
        if not blk:
            blk = design.appearances.addByCopy(
                alib.appearances.itemByName("Paint - Metallic (Black)"), "RailBlack")
        cnt = 0
        for i in range(rc.bRepBodies.count):
            rc.bRepBodies.item(i).appearance = blk; cnt += 1
        print("black-aluminum applied to %d railing bodies" % cnt)
    except Exception as e:
        print("RAIL APPEARANCE FAIL:", repr(e))

    total = root.bRepBodies.count
    for occ in root.allOccurrences:
        total += occ.component.bRepBodies.count
    print("RAILING_BODIES:", rc.bRepBodies.count, "TOTAL_BODIES:", total)
