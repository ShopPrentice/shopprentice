"""Customized pergola: base example + drawbore joinery + railing + finishes.

Run via a thin wrapper that sets __file__ and calls run(context):
    ns = {"__name__": "m", "__file__": "<path>/pergola_custom.py"}
    exec(compile(open(ns["__file__"]).read(), ns["__file__"], "exec"), ns); ns["run"](context)
(Fusion's own script runner sets __file__ automatically.)

  1. Base pergola (exec of pergola.py — the verified rebuild)
  2. Teak drawbore pins via the drawbore template's placement rule (post<->beam x2,
     stretcher<->post x2, brace foot/head x4); 1/8" proud
  3. Black matte lower post segments; beige/cream wall (house-siding background)
  4. Black-aluminum deck railing (exec of pergola_railing.py)
  5. Proper body names; hide all sketches + construction geometry
Joints are declared in model.json; strength_check.py scores them (joint_strength.py).
"""
import adsk.core, adsk.fusion
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
PERGOLA = os.path.join(_HERE, "pergola.py")


def run(context):
    app = adsk.core.Application.get()

    # ── 1. Base pergola (verified example) ──
    src = open(PERGOLA).read()
    ns = {"__name__": "pergola_base"}
    exec(compile(src, PERGOLA, "exec"), ns)
    ns["run"](context)

    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    P = adsk.core.Point3D.create
    NEWBODY = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    IN = 2.54

    def ev(e):
        p = params.itemByName(e)
        return p.value if p else design.unitsManager.evaluateExpression(e, "cm")

    # Drawbore joinery via the template's parameter API + pin-placement rule.
    from woodworking.templates import drawbore as db
    if not params.itemByName("db_pin_dia"):
        db.define_params(params, prefix="db", tenon_w="3.5 in", tenon_thick="1 in",
                         pin_dia="0.375 in", pin_sp="2 in")

    def find_body(name):
        for occ in root.allOccurrences:
            for i in range(occ.bRepBodies.count):
                if occ.bRepBodies.item(i).name == name:
                    return occ.bRepBodies.item(i)
        return None

    def bb(name):
        box = find_body(name).boundingBox
        return box.minPoint, box.maxPoint

    def off_plane(comp, base, off_cm, name):
        inp = comp.constructionPlanes.createInput()
        inp.setByOffset(base, adsk.core.ValueInput.createByString("%.6f cm" % off_cm))
        p = comp.constructionPlanes.add(inp); p.name = name
        return p

    # ── 2. Dowels (post<->beam + braces; NO scarf) ──
    pegs_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    pegs_occ.component.name = "pegs"
    pegs_c = pegs_occ.component

    def make_peg(cx, cy, cz, axis, half_len, name):
        if axis == "x":   base = root.yZConstructionPlane; off = cx
        elif axis == "y": base = root.xZConstructionPlane; off = cy
        else:             base = root.xYConstructionPlane; off = cz
        pl = off_plane(pegs_c, base, off, name + "_Pl")
        sk = pegs_c.sketches.add(pl); sk.name = name + "_Sk"
        spt = sk.modelToSketchSpace(P(cx, cy, cz))
        circ = sk.sketchCurves.sketchCircles.addByCenterRadius(P(spt.x, spt.y, 0), ev("db_pin_dia") / 2.0)
        sk.sketchDimensions.addRadialDimension(circ, P(spt.x + 1, spt.y + 1, 0)).parameter.expression = "db_pin_dia / 2"
        inp = pegs_c.features.extrudeFeatures.createInput(sk.profiles.item(0), NEWBODY)
        inp.setDistanceExtent(True, adsk.core.ValueInput.createByString("%.6f cm" % half_len))
        f = pegs_c.features.extrudeFeatures.add(inp); f.name = name
        b = f.bodies.item(0); b.name = name
        return b

    def proxy_root(body):
        pcn = body.parentComponent.name
        for occ in root.allOccurrences:
            if occ.component.name == pcn:
                for i in range(occ.bRepBodies.count):
                    if occ.bRepBodies.item(i).name == body.name:
                        return occ.bRepBodies.item(i)
        return body

    def pin(struct_name, peg_body, tag):
        t = proxy_root(find_body(struct_name)); v0 = t.volume
        coll = adsk.core.ObjectCollection.create(); coll.add(proxy_root(peg_body))
        inp = root.features.combineFeatures.createInput(t, coll)
        inp.operation = CUT; inp.isKeepToolBodies = True
        root.features.combineFeatures.add(inp)
        t2 = proxy_root(find_body(struct_name))
        dv = v0 - (t2.volume if t2 else 0.0)
        print("   cut %-14s by %-22s removed %.2f cm3 %s" % (struct_name, tag, dv, "OK" if dv > 0.05 else "*** NO ENGAGE ***"))

    peg_names = []
    proud = 0.125 * IN          # how far each peg stands proud of the surface

    def drawbore_pins(name, members, t_axis, shoulder, tip, p_axis, p_lo, p_hi, s_ctr, s_sp):
        """Drawbore pins, placed per woodworking/templates/drawbore.py `through()`:
        each pin runs PERPENDICULAR to the tenon (p_axis = through the mortise cheeks),
        at 1/3 of the tenon depth from the shoulder; two pins spaced s_sp apart, centered
        on the tenon mid-height (s_axis). CUT every member body (keepTool)."""
        s_axis = [a for a in "xyz" if a not in (t_axis, p_axis)][0]
        t_pin = shoulder + (tip - shoulder) / 3.0          # 1/3 from the shoulder
        p_ctr = (p_lo + p_hi) / 2.0; half = (p_hi - p_lo) / 2.0
        for k, off in enumerate((-s_sp / 2.0, s_sp / 2.0)):
            c = {t_axis: t_pin, s_axis: s_ctr + off, p_axis: p_ctr}
            nm = "%s_%d" % (name, k)
            pg = make_peg(c["x"], c["y"], c["z"], p_axis, half, nm); peg_names.append(nm)
            for mb in members:
                pin(mb, pg, nm)

    # POST <-> LONG BEAM (Body1): the post tenon rises into the beam. Pins run PERPENDICULAR
    # to it — front-to-back through the beam cheeks + tenon — 1/3 of the tenon depth up from
    # the shoulder (beam underside), 2 spaced across the tenon width.
    bmn, bmx = bb("Body1")
    for up in ("post1_upper", "post2_upper"):
        umn, umx = bb(up)
        drawbore_pins("peg_beam_%s" % up, ["Body1", up],
                      t_axis="z", shoulder=bmn.z, tip=umx.z,
                      p_axis="y", p_lo=bmn.y - proud, p_hi=bmx.y + proud,
                      s_ctr=(umn.x + umx.x) / 2.0, s_sp=2.0 * IN)

    # POST <-> SHORT BEAM (stretcher Body3/Body4): the stretcher tenon runs into the post.
    # Pins run PERPENDICULAR to it — horizontal through the POST cheeks + tenon — 1/3 of the
    # tenon depth in from the shoulder (post back face), 2 spaced over the tenon height.
    # Heads show on the post side faces.
    for up, st in (("post1_upper", "Body3"), ("post2_upper", "Body4")):
        umn, umx = bb(up); smn, smx = bb(st)
        drawbore_pins("peg_strut_%s" % up, [up, st],
                      t_axis="y", shoulder=umx.y, tip=umn.y + 1.0 * IN,
                      p_axis="x", p_lo=umn.x - proud, p_hi=umx.x + proud,
                      s_ctr=smn.z + 1.35 * IN, s_sp=1.0 * IN)

    # BRACES: foot into post, head into beam
    for bn, kind, post_up in [("left_brace", "low_minx", "post1_upper"),
                              ("right_brace", "low_maxx", "post2_upper")]:
        mn, mx = bb(bn); cy = (mn.y + mx.y) / 2.0; d = 1.3 * IN
        if kind == "low_minx":
            foot = (mn.x + d, mn.z + d); head = (mx.x - d, mx.z - d)
        else:
            foot = (mx.x - d, mn.z + d); head = (mn.x + d, mx.z - d)
        hl = (mx.y - mn.y) / 2.0 + proud
        for label, (px, pz), tgt in [("foot", foot, post_up), ("head", head, "Body1")]:
            nm = "peg_%s_%s" % (bn, label)
            pg = make_peg(px, cy, pz, "y", hl, nm); peg_names.append(nm)
            pin(bn, pg, nm); pin(tgt, pg, nm)

    # ── 3. Black matte lower posts ──
    def lib_appr(name):
        alib = app.materialLibraries.itemByName("Fusion Appearance Library")
        return design.appearances.itemByName(name) or design.appearances.addByCopy(
            alib.appearances.itemByName(name), name)
    try:
        blk = lib_appr("Powder Coat - Rough (Black)")
        for nm in ("post1", "post2"):
            find_body(nm).appearance = blk
        print("Black lower posts OK")
    except Exception as e:
        print("BLACK FAIL:", repr(e))

    # ── 4. Beige/cream wall (house-siding background color) ──
    def set_first_color(appr, r, g, b):
        props = appr.appearanceProperties
        for i in range(props.count):
            cp = adsk.core.ColorProperty.cast(props.item(i))
            if cp:
                cp.value = adsk.core.Color.create(r, g, b, 0); return True
        return False
    try:
        alib = app.materialLibraries.itemByName("Fusion Appearance Library")
        base_nm = None
        for cand in ("Plastic - Matte (White)", "Paint - Enamel Glossy (White)", "Powder Coat - Rough (White)"):
            if alib.appearances.itemByName(cand):
                base_nm = cand; break
        beige = design.appearances.itemByName("WallBeige")
        if not beige:
            beige = design.appearances.addByCopy(alib.appearances.itemByName(base_nm), "WallBeige")
        set_first_color(beige, 224, 214, 192)   # warm cream/beige siding
        find_body("wall").appearance = beige
        print("Beige wall OK (base:", base_nm, ")")
    except Exception as e:
        print("BEIGE FAIL:", repr(e))

    # ── 5. Teak dowels ──
    try:
        from helpers import sp
        sp.apply_appearance("teak", peg_names)
        print("Teak pegs OK (in-script)")
    except Exception as e:
        print("TEAK in-script FAIL (will retry via MCP):", repr(e))

    # ── 6. Black-aluminum deck railing ──
    rp = os.path.join(_HERE, "pergola_railing.py")
    rns = {"__name__": "rail", "__file__": rp}
    exec(compile(open(rp).read(), rp, "exec"), rns)
    rns["run"](context)

    # ── 7. Proper body names (base example leaves Body1, Body102, ... ) ──
    for occ in root.allOccurrences:
        cn = occ.component.name
        bodies = [occ.bRepBodies.item(i) for i in range(occ.bRepBodies.count)]
        if cn == "beam":
            for b in bodies:
                bx = b.boundingBox
                dx = (bx.maxPoint.x - bx.minPoint.x) / IN; dy = (bx.maxPoint.y - bx.minPoint.y) / IN
                cxb = (bx.minPoint.x + bx.maxPoint.x) / 2 / IN; cyb = (bx.minPoint.y + bx.maxPoint.y) / 2 / IN
                if dx > 50:
                    b.name = "beam_front" if cyb < -40 else "beam_back"
                elif dy > 30:
                    b.name = "stretcher_L" if cxb < 90 else "stretcher_R"
                else:
                    b.name = "pad_L" if cxb < 90 else "pad_R"
        elif cn == "deck5":
            bodies.sort(key=lambda b: -b.boundingBox.maxPoint.y)
            for i, b in enumerate(bodies, 1):
                b.name = "deck_board_%02d" % i
        elif cn == "rafts (1)":
            bodies.sort(key=lambda b: b.boundingBox.minPoint.x)
            for i, b in enumerate(bodies, 1):
                b.name = "rafter_%02d" % i

    # ── 8. Clean display: hide all sketches + construction geometry ──
    for c in design.allComponents:
        for coll, attr in ((c.sketches, "isVisible"),
                           (c.constructionPlanes, "isLightBulbOn"),
                           (c.constructionAxes, "isLightBulbOn"),
                           (c.constructionPoints, "isLightBulbOn")):
            for i in range(coll.count):
                try: setattr(coll.item(i), attr, False)
                except Exception: pass

    print("PEGS:", len(peg_names), peg_names)
    total = root.bRepBodies.count
    for occ in root.allOccurrences:
        total += occ.component.bRepBodies.count
    print("TOTAL_BODIES:", total)
