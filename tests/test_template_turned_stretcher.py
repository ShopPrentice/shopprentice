"""Test fixtures for turned_stretcher template.

F1: Two legs at random XY positions, different splay/rake, non-level stretcher
F2: Four legs at random positions, H-stretcher with wedges at all joints

After build, parameters are changed via Fusion to validate the profile
recomputes correctly at runtime.
"""
import adsk.core
import adsk.fusion
import math


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters

    P = adsk.core.Point3D.create
    V = adsk.core.ValueInput.createByString
    NEWBODY = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    from helpers import sp
    import importlib
    importlib.reload(sp)

    def ev(expr):
        if isinstance(expr, (int, float)):
            return float(expr)
        p = params.itemByName(expr)
        if p:
            return p.value
        return design.unitsManager.evaluateExpression(expr, "cm")

    def add_param(name, expr, unit="in", comment=""):
        existing = params.itemByName(name)
        if existing:
            existing.expression = expr
        else:
            params.add(name, V(expr), unit, comment)

    # ── Shared parameters ──────────────────────────────────────────
    # All params defined here so the palette can patch them on Rebuild.
    for pname, expr, unit, desc in [
        ("leg_dia", "1.375 in", "in", "Leg diameter"),
        ("leg_h", "16 in", "in", "Leg height"),
        # Stretcher profile
        ("ts_mid_dia", "0.75 in", "in", "Stretcher body diameter"),
        ("ts_end_dia", "0.5 in", "in", "Stretcher tenon diameter"),
        ("ts_tenon_len", "1.6 in", "in", "Stretcher tenon length"),
        ("ts_shoulder_len", "0.91 in", "in", "Stretcher shoulder length"),
        ("ts_ext", "0.1 in", "in", "Stretcher extension beyond leg"),
        ("ts_barrel_dist", "1.5 in", "in", "Barrel control dist from mid"),
        ("ts_barrel_r", "0.375 in", "in", "Barrel control radius"),
    ]:
        add_param(pname, expr, unit, desc)

    from woodworking.templates import turned_stretcher as ts
    from woodworking.templates import tenon_wedge as tw
    importlib.reload(ts)
    importlib.reload(tw)
    # ts.define_params skips existing — won't overwrite the values above
    ts.define_params(params)
    try:
        tw.define_params(params, prefix="tw", slot_w="0.08 in",
                         depth_ratio="1 / 2")
    except Exception as e:
        print(f"tw.define_params warning: {e}")

    leg_h = ev("leg_h")
    leg_dia = ev("leg_dia")

    def angled_leg(comp, foot_x_expr, foot_y_expr, splay_deg, rake_deg, name):
        """Cylinder from foot position, tilted by splay/rake.

        Returns (body, axis_line) where axis_line is a sketch line
        representing the leg center axis (foot to top).
        """
        splay_r = splay_deg * math.pi / 180
        rake_r = rake_deg * math.pi / 180

        fx_param = f"{name}_fx"
        fy_param = f"{name}_fy"
        add_param(fx_param, foot_x_expr, "cm", f"{name} foot X")
        add_param(fy_param, foot_y_expr, "cm", f"{name} foot Y")

        foot_x = ev(fx_param)
        foot_y = ev(fy_param)

        # Circle sketch for extrude
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sk.name = f"{name}_Sk"
        m2s = sk.modelToSketchSpace
        fc = m2s(P(foot_x, foot_y, 0))

        circle = sk.sketchCurves.sketchCircles.addByCenterRadius(
            P(fc.x, fc.y, 0), leg_dia / 2)

        dims = sk.sketchDimensions
        orient = adsk.fusion.DimensionOrientations
        dims.addDistanceDimension(
            sk.originPoint, circle.centerSketchPoint,
            orient.HorizontalDimensionOrientation,
            P(fc.x / 2, fc.y + 2, 0)
        ).parameter.expression = fx_param
        dims.addDistanceDimension(
            sk.originPoint, circle.centerSketchPoint,
            orient.VerticalDimensionOrientation,
            P(fc.x + 2, fc.y / 2, 0)
        ).parameter.expression = fy_param
        dims.addRadialDimension(circle,
            P(fc.x + leg_dia/2 + 1, fc.y, 0)
        ).parameter.expression = "leg_dia / 2"

        prof = sk.profiles.item(0)
        ext_inp = comp.features.extrudeFeatures.createInput(prof, NEWBODY)
        ext_inp.setDistanceExtent(False, V("leg_h"))
        feat = comp.features.extrudeFeatures.add(ext_inp)
        feat.name = f"{name}_Ext"
        body = feat.bodies.item(0)
        body.name = name

        if abs(splay_deg) > 0.1 or abs(rake_deg) > 0.1:
            foot_pt = P(foot_x, foot_y, 0)
            body_coll = adsk.core.ObjectCollection.create()
            body_coll.add(body)
            transform = adsk.core.Matrix3D.create()
            if abs(splay_deg) > 0.1:
                m1 = adsk.core.Matrix3D.create()
                m1.setToRotation(-splay_r, adsk.core.Vector3D.create(0, 1, 0), foot_pt)
                transform.transformBy(m1)
            if abs(rake_deg) > 0.1:
                m2 = adsk.core.Matrix3D.create()
                m2.setToRotation(rake_r, adsk.core.Vector3D.create(1, 0, 0), foot_pt)
                transform.transformBy(m2)
            move_inp = comp.features.moveFeatures.createInput2(body_coll)
            move_inp.defineAsFreeMove(transform)
            comp.features.moveFeatures.add(move_inp).name = f"{name}_Tilt"

        # Finite axis line through the two end face centers.
        # Find the circular edges at each end of the cylinder.
        circ_edges = []
        for ei in range(body.edges.count):
            e = body.edges.item(ei)
            if isinstance(e.geometry, adsk.core.Circle3D):
                circ_edges.append(e)
        # Sort by Z of center to identify bottom vs top
        circ_edges.sort(key=lambda e: e.geometry.center.z)

        if len(circ_edges) < 2:
            print(f"{name}: expected 2 circular edges, found {len(circ_edges)}")
            return body, None

        # Construction points at each circular edge center (parametric)
        cp_bot_inp = comp.constructionPoints.createInput()
        cp_bot_inp.setByCenter(circ_edges[0])
        cp_bot = comp.constructionPoints.add(cp_bot_inp)
        cp_bot.name = f"{name}_BotCp"

        cp_top_inp = comp.constructionPoints.createInput()
        cp_top_inp.setByCenter(circ_edges[-1])
        cp_top = comp.constructionPoints.add(cp_top_inp)
        cp_top.name = f"{name}_TopCp"

        # Construction axis through the two end centers = finite leg axis
        ax_inp = comp.constructionAxes.createInput()
        ax_inp.setByTwoPoints(cp_bot, cp_top)
        con_axis = comp.constructionAxes.add(ax_inp)
        con_axis.name = f"{name}_Axis"

        return body, con_axis

    # ════════════════════════════════════════════════════════════════
    # F1: Two legs at random XY, non-level stretcher
    # Legs NOT on the same axis — offset in both X and Y
    # ════════════════════════════════════════════════════════════════
    f1_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    f1_occ.component.name = "F1_NonLevel"
    f1 = f1_occ.component

    # Leg A: at (3, 7), splayed 8° left, -5° forward
    f1_la, f1_ax_a = angled_leg(f1, "3 cm", "7 cm", 8, -5, "F1_LA")
    # Leg B: at (8, 35), splayed -6° right, 12° backward — 28cm apart diagonally
    f1_lb, f1_ax_b = angled_leg(f1, "8 cm", "35 cm", -6, 12, "F1_LB")

    if f1_la and f1_lb:
        # Non-level: A at 38%, B at 44% of leg_h
        add_param("f1_dist_a", "leg_h * 0.38", "in", "F1 stretcher height A")
        add_param("f1_dist_b", "leg_h * 0.44", "in", "F1 stretcher height B")
        f1_str = ts.build(f1, axis_a=f1_ax_a, axis_b=f1_ax_b,
                          dist_a="f1_dist_a", dist_b="f1_dist_b",
                          profile="barrel",
                          name="F1_Str", ev=ev)

        # Wedges on the stretcher tenon ends
        if f1_str:
            pfaces = []
            for fi in range(f1_str.faces.count):
                f = f1_str.faces.item(fi)
                if isinstance(f.geometry, adsk.core.Plane):
                    pfaces.append(f)
            pfaces.sort(key=lambda f: f.area)
            print(f"F1_Str: {len(pfaces)} planar faces, smallest area={pfaces[0].area:.4f}" if pfaces else "F1_Str: no planar faces")
            for wi, ef in enumerate(pfaces[:2]):
                fc = ef.pointOnFace
                bb_a = f1_la.boundingBox
                ca_x = (bb_a.minPoint.x + bb_a.maxPoint.x) / 2
                ca_y = (bb_a.minPoint.y + bb_a.maxPoint.y) / 2
                d_a = math.sqrt((fc.x - ca_x)**2 + (fc.y - ca_y)**2)
                mort = f1_la if d_a < 20 else f1_lb
                try:
                    w = tw.round_tenon(f1, tenon_body=f1_str,
                                   mortise_body=mort, end_face=ef,
                                   tenon_depth_expr="leg_dia",
                                   tenon_diam_expr="ts_end_dia",
                                   name=f"F1_TW_{wi}", ev=ev)
                    print(f"F1_TW_{wi}: built")
                except Exception as e:
                    print(f"F1_TW_{wi}: failed: {e}")

        print(f"F1 Non-level: {f1.bRepBodies.count} bodies")
    else:
        print("F1: leg build failed")

    # ════════════════════════════════════════════════════════════════
    # F2: Four legs at random positions, H-stretcher + wedges
    # No two legs on the same X or Y coordinate
    # ════════════════════════════════════════════════════════════════
    f2_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    f2_occ.component.name = "F2_HStretcher"
    f2 = f2_occ.component

    ox = 55  # X offset from F1

    # Four legs with distinct random positions and angles
    add_param("f2_ox", "55 cm", "cm", "F2 X offset")
    f2_fl, f2_ax_fl = angled_leg(f2, "f2_ox + 2 cm",  "4 cm",   -11, -7,  "F2_FL")
    f2_bl, f2_ax_bl = angled_leg(f2, "f2_ox + 6 cm",  "33 cm",  -8,  13,  "F2_BL")
    f2_fr, f2_ax_fr = angled_leg(f2, "f2_ox + 27 cm", "6 cm",    9,  -4,  "F2_FR")
    f2_br, f2_ax_br = angled_leg(f2, "f2_ox + 30 cm", "36 cm",   7,   11, "F2_BR")

    if all([f2_fl, f2_bl, f2_fr, f2_br]):
        # Side stretchers at different heights (parametric expressions)
        add_param("f2_sl_da", "leg_h * 0.36", "in", "F2 SL dist A")
        add_param("f2_sl_db", "leg_h * 0.42", "in", "F2 SL dist B")
        add_param("f2_sr_da", "leg_h * 0.38", "in", "F2 SR dist A")
        add_param("f2_sr_db", "leg_h * 0.40", "in", "F2 SR dist B")

        f2_sl = ts.build(f2, axis_a=f2_ax_fl, axis_b=f2_ax_bl,
                         dist_a="f2_sl_da", dist_b="f2_sl_db",
                         name="F2_SL", ev=ev)
        f2_sr = ts.build(f2, axis_a=f2_ax_fr, axis_b=f2_ax_br,
                         dist_a="f2_sr_da", dist_b="f2_sr_db",
                         name="F2_SR", ev=ev)

        # Skip cross stretcher for now (needs turned body axis lines)

        # Wedges on all stretcher joints
        for str_body, str_name, legs in [
            (f2_sl, "SL", [(f2_fl, "FL"), (f2_bl, "BL")]),
            (f2_sr, "SR", [(f2_fr, "FR"), (f2_br, "BR")]),
        ]:
            if not str_body:
                continue
            pfaces = []
            for fi in range(str_body.faces.count):
                f = str_body.faces.item(fi)
                if isinstance(f.geometry, adsk.core.Plane):
                    pfaces.append(f)
            pfaces.sort(key=lambda f: f.area)
            for wi, ef in enumerate(pfaces[:2]):
                fc = ef.pointOnFace
                # Match to nearest leg
                best_leg = None
                best_d = 1e10
                for leg, lname in legs:
                    bb = leg.boundingBox
                    cx = (bb.minPoint.x + bb.maxPoint.x) / 2
                    cy = (bb.minPoint.y + bb.maxPoint.y) / 2
                    d = math.sqrt((fc.x - cx)**2 + (fc.y - cy)**2)
                    if d < best_d:
                        best_d = d
                        best_leg = leg
                        best_lname = lname
                tw.round_tenon(f2, tenon_body=str_body,
                               mortise_body=best_leg, end_face=ef,
                               tenon_depth_expr="leg_dia",
                               tenon_diam_expr="ts_end_dia",
                               name=f"F2_TW_{str_name}_{best_lname}", ev=ev)

        print(f"F2 H-stretcher: {f2.bRepBodies.count} bodies")
    else:
        print("F2: some legs failed")

    # ── Hide construction ──────────────────────────────────────────
    for _comp in [root, f1, f2]:
        for si in range(_comp.sketches.count):
            _comp.sketches.item(si).isVisible = False
        for ci in range(_comp.constructionPlanes.count):
            _comp.constructionPlanes.item(ci).isLightBulbOn = False

    # ── Appearance ─────────────────────────────────────────────────
    _all = []
    def _collect(c):
        for i in range(c.bRepBodies.count):
            _all.append(c.bRepBodies.item(i).name)
        for i in range(c.occurrences.count):
            _collect(c.occurrences.item(i).component)
    _collect(root)
    _non_wedge = [n for n in _all if not n.startswith("F1_TW") and not n.startswith("F2_TW")]
    _wedge = [n for n in _all if n.startswith("F1_TW") or n.startswith("F2_TW")]
    sp.apply_appearance("white oak", bodies=_non_wedge)
    if _wedge:
        sp.apply_appearance("rosewood", bodies=_wedge)

    # ── Fit view ───────────────────────────────────────────────────
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam

    total = f1.bRepBodies.count + f2.bRepBodies.count
    print(f"\nTotal: {total} bodies across 2 fixtures")
