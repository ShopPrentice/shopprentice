"""Counter Stool — Parametric Fusion 360 Model
Splayed legs with through-tenons, stretchers with stopped tenons, footrest."""
import adsk.core, adsk.fusion, math
from helpers import sp


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    P = adsk.core.Point3D.create
    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
    NEWBODY = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation

    def ev(e):
        p = params.itemByName(e)
        return p.value if p else design.unitsManager.evaluateExpression(e, "cm")

    # ── PARAMETERS ────────────────────────────────────────────────
    for name, expr, unit, comment in [
        # Seat
        ("seat_l", "15.75 in", "in", "Seat length (X)"),
        ("seat_w", "11 in", "in", "Seat width (Y)"),
        ("seat_t", "1.5 in", "in", "Seat thickness"),
        # Legs
        ("leg_w", "1.75 in", "in", "Leg width (front view)"),
        ("leg_d", "1.5 in", "in", "Leg depth"),
        ("leg_h", "24 in", "in", "Leg height to seat bottom"),
        ("leg_inset_x", "1.25 in", "in", "Leg center from seat X edge"),
        ("leg_inset_y", "1.25 in", "in", "Leg center from seat Y edge"),
        # Splay
        ("splay", "6 deg", "deg", "Leg splay along length"),
        ("splay_w", "4 deg", "deg", "Leg splay along width"),
        # Domino (Festool 8 × 22 × 40)
        ("dm_t", "8 mm", "in", "Domino thickness (cutter diameter)"),
        ("dm_w", "22 mm", "in", "Domino width"),
        ("dm_l", "40 mm", "in", "Domino length"),
        ("dm_d", "dm_l / 2", "in", "Domino depth per side"),
        # Stretchers
        ("str_t", "1.25 in", "in", "Stretcher thickness"),
        ("str_w", "0.875 in", "in", "Stretcher width"),
        ("front_str_h", "7 in", "in", "Front stretcher center Z"),
        ("side_str_h", "4.5 in", "in", "Side stretcher center Z"),
        # Stopped tenon
        ("st_w", "1 in", "in", "Stopped tenon width"),
        ("st_d", "0.375 in", "in", "Stopped tenon depth"),
        ("st_l", "0.875 in", "in", "Stopped tenon length"),
        # Footrest (sits on top of front stretcher)
        ("fr_t", "0.625 in", "in", "Footrest thickness"),
        ("fr_w", "1.75 in", "in", "Footrest width"),
    ]:
        params.add(name, VI(expr), unit, comment)

    # Derived parameters
    for name, expr, unit, comment in [
        ("seat_z", "leg_h", "in", "Seat bottom Z"),
        ("leg_top_z", "leg_h", "in", "Leg top Z"),
        ("splay_shift", "leg_top_z * tan(splay)", "in", "Foot X offset"),
        ("splay_shift_w", "leg_top_z * tan(splay_w)", "in", "Foot Y offset"),
    ]:
        params.add(name, VI(expr), unit, comment)

    # ── COMPONENTS ────────────────────────────────────────────────
    seat_occ = sp.make_comp(root, "Seat")
    seat_c = seat_occ.component
    legs_occ = sp.make_comp(root, "Legs")
    legs_c = legs_occ.component
    str_occ = sp.make_comp(root, "Stretchers")
    str_c = str_occ.component

    # ── MIDPLANES (root — used for cross-component mirrors) ───────
    XMid = sp.off_plane(root, root.yZConstructionPlane, "seat_l / 2", "XMid")
    YMid = sp.off_plane(root, root.xZConstructionPlane, "seat_w / 2", "YMid")

    # ── SEAT ──────────────────────────────────────────────────────
    Seat_Pl = sp.off_plane(seat_c, seat_c.xYConstructionPlane, "seat_z", "Seat_Pl")

    sk, prof = sp.sketch_rect_model(seat_c, Seat_Pl,
        ("0 in", "0 in", "seat_z"),
        {"x": "seat_l", "y": "seat_w"},
        "Seat_Sk", ev=ev)
    SeatBoard = sp.ext_new(seat_c, prof, "seat_t", "SeatBoard")
    Seat = SeatBoard.bodies.item(0)
    Seat.name = "Seat"

    # ── NEAR-LEFT LEG ─────────────────────────────────────────────
    # Trapezoid sketch on XZ plane offset to leg front face.
    # X-splay is built into the trapezoid; Y-splay applied via Move.
    LegFront_Pl = sp.off_plane(legs_c, legs_c.xZConstructionPlane,
        "leg_inset_y - leg_d / 2", "LegFront_Pl")

    Leg_NL_Sk = legs_c.sketches.add(LegFront_Pl)
    Leg_NL_Sk.name = "Leg_NL_Sk"
    lns = Leg_NL_Sk.sketchCurves.sketchLines

    # Use modelToSketchSpace — XZ-offset planes often flip sketch Y vs model Z
    m2s = Leg_NL_Sk.modelToSketchSpace

    # Model-space corners of the trapezoid
    # Top-left: (inset_x - leg_w/2, inset_y - leg_d/2, leg_top_z)
    # Top-right: (inset_x + leg_w/2, inset_y - leg_d/2, leg_top_z)
    # Bot-right: (inset_x + leg_w/2 - splay_shift, inset_y - leg_d/2, 0)
    # Bot-left: (inset_x - leg_w/2 - splay_shift, inset_y - leg_d/2, 0)
    inset_x = ev("leg_inset_x")
    half_w = ev("leg_w") / 2
    inset_y = ev("leg_inset_y")
    half_d = ev("leg_d") / 2
    top_z_val = ev("leg_top_z")
    shift = ev("splay_shift")
    plane_y = inset_y - half_d  # Y of the construction plane

    s_tl = m2s(P(inset_x - half_w, plane_y, top_z_val))
    s_tr = m2s(P(inset_x + half_w, plane_y, top_z_val))
    s_br = m2s(P(inset_x + half_w - shift, plane_y, 0))
    s_bl = m2s(P(inset_x - half_w - shift, plane_y, 0))

    ln_top = lns.addByTwoPoints(P(s_tl.x, s_tl.y, 0), P(s_tr.x, s_tr.y, 0))
    ln_right = lns.addByTwoPoints(ln_top.endSketchPoint, P(s_br.x, s_br.y, 0))
    ln_bot = lns.addByTwoPoints(ln_right.endSketchPoint, P(s_bl.x, s_bl.y, 0))
    ln_left = lns.addByTwoPoints(ln_bot.endSketchPoint, ln_top.startSketchPoint)

    gc = Leg_NL_Sk.geometricConstraints
    gc.addHorizontal(ln_top)
    gc.addHorizontal(ln_bot)

    d = Leg_NL_Sk.sketchDimensions
    d.addDistanceDimension(ln_top.startSketchPoint, ln_top.endSketchPoint,
        H, P(0, 0, 0)).parameter.expression = "leg_w"
    d.addDistanceDimension(ln_bot.startSketchPoint, ln_bot.endSketchPoint,
        H, P(0, 0, 0)).parameter.expression = "leg_w"
    d.addDistanceDimension(Leg_NL_Sk.originPoint, ln_top.startSketchPoint,
        V, P(0, 0, 0)).parameter.expression = "leg_top_z"
    d.addDistanceDimension(Leg_NL_Sk.originPoint, ln_top.startSketchPoint,
        H, P(0, 0, 0)).parameter.expression = "leg_inset_x - leg_w / 2"
    d.addDistanceDimension(ln_top.startSketchPoint, ln_bot.endSketchPoint,
        H, P(0, 0, 0)).parameter.expression = "splay_shift"
    d.addDistanceDimension(ln_top.startSketchPoint, ln_bot.endSketchPoint,
        V, P(0, 0, 0)).parameter.expression = "leg_top_z"

    Leg_NL_ext = sp.ext_new(legs_c, Leg_NL_Sk.profiles.item(0), "leg_d", "Leg_NL")
    Leg_NL_b = Leg_NL_ext.bodies.item(0)
    Leg_NL_b.name = "Leg_NL"

    # ── Y-SPLAY (Move) ───────────────────────────────────────────
    # Rotate around X axis by splay_w, pivoting at the leg top center
    angle_w = ev("splay_w")
    c_w, s_w = math.cos(angle_w), math.sin(angle_w)
    pivot_y = ev("leg_inset_y") + ev("leg_d") / 2  # inner edge — full top submerges into seat
    pivot_z = ev("leg_top_z")
    ty = pivot_y - (pivot_y * c_w + pivot_z * s_w)
    tz = pivot_z - (-pivot_y * s_w + pivot_z * c_w)

    xform = adsk.core.Matrix3D.create()
    xform.setWithArray([
        1.0,  0.0,  0.0,  0.0,
        0.0,  c_w,  s_w,  ty,
        0.0, -s_w,  c_w,  tz,
        0.0,  0.0,  0.0,  1.0
    ])
    move_coll = adsk.core.ObjectCollection.create()
    move_coll.add(Leg_NL_b)
    move_inp = legs_c.features.moveFeatures.createInput2(move_coll)
    move_inp.defineAsFreeMove(xform)
    move_feat = legs_c.features.moveFeatures.add(move_inp)
    move_feat.name = "YSplay_NL"

    # ── TRIM LEG TOP (CUT before mirror — one CUT instead of four) ──
    Leg_NL_b = None
    for i in range(legs_c.bRepBodies.count):
        b = legs_c.bRepBodies.item(i)
        if b.name == "Leg_NL":
            Leg_NL_b = b
    Seat_tmp = None
    for i in range(seat_c.bRepBodies.count):
        b = seat_c.bRepBodies.item(i)
        if b.name == "Seat":
            Seat_tmp = b
    sp.combine(Leg_NL_b, [Seat_tmp], CUT, True, "LegTrim_NL")

    # ── MIRROR LEGS ────────────────────────────────────────────────

    # Mirror NL across YMid → NR
    NR_mir = sp.mirror_bodies(legs_c, [Leg_NL_b], YMid, "Leg_NR_Mir")
    Leg_NR = NR_mir.bodies.item(0)
    Leg_NR.name = "Leg_NR"
    Leg_NL = NR_mir.bodies.item(1)
    Leg_NL.name = "Leg_NL"

    # Mirror NL+NR across XMid → FL, FR
    Far_mir = sp.mirror_bodies(legs_c, [Leg_NL, Leg_NR], XMid, "Legs_Far_Mir")
    Leg_FL = Far_mir.bodies.item(0)
    Leg_FL.name = "Leg_FL"
    Leg_FR = Far_mir.bodies.item(1)
    Leg_FR.name = "Leg_FR"
    Leg_NL = Far_mir.bodies.item(2)
    Leg_NL.name = "Leg_NL"
    Leg_NR = Far_mir.bodies.item(3)
    Leg_NR.name = "Leg_NR"

    # ── HELPERS ───────────────────────────────────────────────────
    # Helper: find body by name (searches all components)
    def find_body(name):
        def _walk(comp):
            for i in range(comp.bRepBodies.count):
                if comp.bRepBodies.item(i).name == name:
                    return comp.bRepBodies.item(i)
            for occ in comp.occurrences:
                r = _walk(occ.component)
                if r:
                    return r
            return None
        return _walk(root)

    # ── DOMINO JOINTS (legs to seat) ─────────────────────────────
    # Stadium-shaped void, one per leg, dm_w along X (leg width), dm_t along Y
    def sketch_slot(comp, plane, cxe, cye, long_e, short_e, vertical, name):
        """Stadium sketch on a construction plane (2 arcs + 2 lines)."""
        sk = comp.sketches.add(plane)
        sk.name = name
        slines = sk.sketchCurves.sketchLines
        sarcs = sk.sketchCurves.sketchArcs
        cx, cy = ev(cxe), ev(cye)
        lg, sh = ev(long_e), ev(short_e)
        r = sh / 2
        hl = (lg - sh) / 2
        if vertical:
            br = P(cx + r, cy - hl, 0); tr = P(cx + r, cy + hl, 0)
            tc = P(cx, cy + hl, 0);     tl = P(cx - r, cy + hl, 0)
            bl = P(cx - r, cy - hl, 0); bc = P(cx, cy - hl, 0)
            l_r = slines.addByTwoPoints(br, tr)
            a_t = sarcs.addByCenterStartSweep(tc, tr, math.pi)
            l_l = slines.addByTwoPoints(tl, bl)
            a_b = sarcs.addByCenterStartSweep(bc, bl, math.pi)
            sk.geometricConstraints.addVertical(l_r)
            sk.geometricConstraints.addVertical(l_l)
            sk.geometricConstraints.addTangent(l_r, a_t)
            sk.geometricConstraints.addTangent(a_t, l_l)
            sk.geometricConstraints.addTangent(l_l, a_b)
            sk.geometricConstraints.addTangent(a_b, l_r)
            d = sk.sketchDimensions
            d.addRadialDimension(a_b,
                P(cx + r + 1, cy - hl, 0)).parameter.expression = short_e + " / 2"
            d.addDistanceDimension(a_b.centerSketchPoint, a_t.centerSketchPoint,
                V, P(cx + r + 2, cy, 0)).parameter.expression = long_e + " - " + short_e
            d.addDistanceDimension(sk.originPoint, a_b.centerSketchPoint,
                H, P(cx / 2, cy - hl - 1, 0)).parameter.expression = cxe
            d.addDistanceDimension(sk.originPoint, a_b.centerSketchPoint,
                V, P(cx - r - 1, (cy - hl) / 2, 0)
            ).parameter.expression = cye + " - (" + long_e + " - " + short_e + ") / 2"
        else:
            bsl = P(cx - hl, cy - r, 0); bsr = P(cx + hl, cy - r, 0)
            rc  = P(cx + hl, cy, 0);     tsr = P(cx + hl, cy + r, 0)
            tsl = P(cx - hl, cy + r, 0); lc  = P(cx - hl, cy, 0)
            l_b = slines.addByTwoPoints(bsl, bsr)
            a_r = sarcs.addByCenterStartSweep(rc, bsr, math.pi)
            l_t = slines.addByTwoPoints(tsr, tsl)
            a_l = sarcs.addByCenterStartSweep(lc, tsl, math.pi)
            sk.geometricConstraints.addHorizontal(l_b)
            sk.geometricConstraints.addHorizontal(l_t)
            sk.geometricConstraints.addTangent(l_b, a_r)
            sk.geometricConstraints.addTangent(a_r, l_t)
            sk.geometricConstraints.addTangent(l_t, a_l)
            sk.geometricConstraints.addTangent(a_l, l_b)
            d = sk.sketchDimensions
            d.addRadialDimension(a_l,
                P(cx - hl - 1, cy + r + 1, 0)).parameter.expression = short_e + " / 2"
            d.addDistanceDimension(a_l.centerSketchPoint, a_r.centerSketchPoint,
                H, P(cx, cy - r - 2, 0)).parameter.expression = long_e + " - " + short_e
            d.addDistanceDimension(sk.originPoint, a_l.centerSketchPoint,
                H, P((cx - hl) / 2, cy - r - 1, 0)
            ).parameter.expression = cxe + " - (" + long_e + " - " + short_e + ") / 2"
            d.addDistanceDimension(sk.originPoint, a_l.centerSketchPoint,
                V, P(cx - hl - 2, cy / 2, 0)).parameter.expression = cye
        return sk, sk.profiles.item(0)

    # Body-relative ref: domino voids reference Seat for positioning
    ref_seat = find_body("Seat")
    ref_seat_bb = ref_seat.boundingBox

    # Domino void: horizontal stadium (dm_w along X, dm_t along Y)
    _, dm_prof = sketch_slot(seat_c, Seat_Pl,
        "leg_inset_x", "leg_inset_y", "dm_w", "dm_t",
        vertical=False, name="DM_NL_Sk")
    DM_NL = sp.ext_new_sym(seat_c, dm_prof, "dm_d", "DM_NL")
    DM_NL_b = DM_NL.bodies.item(0)
    DM_NL_b.name = "DM_NL"

    # Mirror NL → NR across YMid
    DM_NR_mir = sp.mirror_bodies(seat_c, [DM_NL_b], YMid, "DM_NR_Mir")
    DM_NR_b = DM_NR_mir.bodies.item(0)
    DM_NR_b.name = "DM_NR"
    DM_NL_b = DM_NR_mir.bodies.item(1)
    DM_NL_b.name = "DM_NL"

    # Mirror NL+NR → FL, FR across XMid
    DM_Far_mir = sp.mirror_bodies(seat_c, [DM_NL_b, DM_NR_b], XMid, "DM_Far_Mir")
    DM_FL_b = DM_Far_mir.bodies.item(0)
    DM_FL_b.name = "DM_FL"
    DM_FR_b = DM_Far_mir.bodies.item(1)
    DM_FR_b.name = "DM_FR"
    DM_NL_b = DM_Far_mir.bodies.item(2)
    DM_NL_b.name = "DM_NL"
    DM_NR_b = DM_Far_mir.bodies.item(3)
    DM_NR_b.name = "DM_NR"

    # Re-find Seat
    Seat = None
    for i in range(seat_c.bRepBodies.count):
        b = seat_c.bRepBodies.item(i)
        if b.name == "Seat":
            Seat = b
            break

    # CUT all 4 domino voids into seat (keepTool=True — dominos visible)
    sp.combine(Seat, [DM_NL_b, DM_NR_b, DM_FL_b, DM_FR_b], CUT, True, "DM_Seat_Cut")

    # CUT each domino into its leg (keepTool=True — cross-component, auto-proxied)
    sp.combine(Leg_NL, [DM_NL_b], CUT, True, "DM_Leg_NL")
    sp.combine(Leg_NR, [DM_NR_b], CUT, True, "DM_Leg_NR")
    sp.combine(Leg_FL, [DM_FL_b], CUT, True, "DM_Leg_FL")
    sp.combine(Leg_FR, [DM_FR_b], CUT, True, "DM_Leg_FR")

    # ── STRETCHER DERIVED PARAMS ───────────────────────────────────
    # Splay-adjusted lengths ensure stretchers reach into legs at any splay angle
    for name, expr, unit, comment in [
        ("bstr_sx", "splay_shift * (leg_top_z - front_str_h) / leg_top_z", "in", "Back str X splay"),
        ("bstr_sy", "splay_shift_w * (leg_top_z - front_str_h) / leg_top_z", "in", "Back str Y splay"),
        ("bstr_len", "seat_l - 2 * leg_inset_x + 2 * bstr_sx - leg_w + 2 * st_l", "in", "Back str total length"),
        ("sstr_sx", "splay_shift * (leg_top_z - side_str_h) / leg_top_z", "in", "Side str X splay"),
        ("sstr_sy", "splay_shift_w * (leg_top_z - side_str_h) / leg_top_z", "in", "Side str Y splay"),
        ("sstr_len", "seat_w - 2 * leg_inset_y + 2 * sstr_sy - leg_d + 2 * st_l", "in", "Side str total length"),
        ("fr_len", "bstr_len - 2 * st_l", "in", "Footrest length"),
    ]:
        params.add(name, VI(expr), unit, comment)

    leg_top_z_val = ev("leg_top_z")

    # Helper: compute splay-adjusted center position at a given height
    def splay_center(h):
        """Return (sx, sy) — splay offset at height h (cm values)."""
        frac = (leg_top_z_val - h) / leg_top_z_val
        return ev("splay_shift") * frac, ev("splay_shift_w") * frac

    # Look up legs for angled tenon CUTs
    Leg_NL = find_body("Leg_NL")
    Leg_NL_bb = Leg_NL.boundingBox
    Leg_NR = find_body("Leg_NR")
    Leg_NR_bb = Leg_NR.boundingBox
    Leg_FL = find_body("Leg_FL")
    Leg_FL_bb = Leg_FL.boundingBox
    Leg_FR = find_body("Leg_FR")
    Leg_FR_bb = Leg_FR.boundingBox

    # Helper: angled M&T at stretcher-leg interface
    def angled_tenon_end(str_body, leg_body, str_plane, axis, direction, name):
        """CUT leg from stretcher -> sketch tenon on angled face -> sweep -> JOIN."""
        # Step 1: CUT leg from stretcher -> angled mating face
        sp.combine(str_body, [leg_body], CUT, True, f"{name}_LegCut")
        str_body = find_body(str_body.name)

        # Step 2: Find angled face + sketch tenon
        face = sp.find_face(str_body, axis, direction)
        sk = str_c.sketches.add(face)
        sk.name = f"{name}_Sk"
        m2s_fn = sk.modelToSketchSpace
        pof = face.pointOnFace
        cx, cy, cz = pof.x, pof.y, pof.z
        hw, hd = ev("st_w") / 2, ev("st_d") / 2

        if axis == "x":   # st_w along Z (leg grain), st_d along Y
            c0 = m2s_fn(P(cx, cy - hd, cz - hw))
            c1 = m2s_fn(P(cx, cy + hd, cz + hw))
        else:             # st_w along Z (leg grain), st_d along X
            c0 = m2s_fn(P(cx - hd, cy, cz - hw))
            c1 = m2s_fn(P(cx + hd, cy, cz + hw))

        rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(
            P(c0.x, c0.y, 0), P(c1.x, c1.y, 0))
        _gc = sk.geometricConstraints
        _gc.addHorizontal(rect[0]); _gc.addHorizontal(rect[2])
        _gc.addVertical(rect[1]); _gc.addVertical(rect[3])

        h_ax, v_ax = sp.probe_sketch_axes(sk)
        h_expr = "st_w" if h_ax == "z" else "st_d"
        v_expr = "st_w" if v_ax == "z" else "st_d"

        _d = sk.sketchDimensions
        mid = P((c0.x + c1.x) / 2, (c0.y + c1.y) / 2, 0)
        _d.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
            H, P(mid.x, c0.y - 0.5, 0)).parameter.expression = h_expr
        _d.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
            V, P(c1.x + 0.5, mid.y, 0)).parameter.expression = v_expr

        tenon_prof = min(
            (sk.profiles.item(i) for i in range(sk.profiles.count)),
            key=lambda p: p.areaProperties().area)

        # Step 3: Sweep path on stretcher construction plane
        path_sk = str_c.sketches.add(str_plane)
        path_sk.name = f"{name}_PathSk"
        pm = path_sk.modelToSketchSpace
        offset = ev("st_l") * direction
        if axis == "x":
            sp0 = pm(P(cx, cy, cz))
            sp1 = pm(P(cx + offset, cy, cz))
            dim_orient = H
            dim_pt = P((sp0.x + sp1.x) / 2, sp0.y - 0.5, 0)
        else:
            sp0 = pm(P(cx, cy, cz))
            sp1 = pm(P(cx, cy + offset, cz))
            dim_orient = V
            dim_pt = P(sp0.x + 0.5, (sp0.y + sp1.y) / 2, 0)
        path_line = path_sk.sketchCurves.sketchLines.addByTwoPoints(
            P(sp0.x, sp0.y, 0), P(sp1.x, sp1.y, 0))
        path_sk.sketchDimensions.addDistanceDimension(
            path_line.startSketchPoint, path_line.endSketchPoint,
            dim_orient, dim_pt).parameter.expression = "st_l"
        path = str_c.features.createPath(path_line)

        # Step 4: Sweep NEW BODY
        sweep_inp = str_c.features.sweepFeatures.createInput(tenon_prof, path, NEWBODY)
        sweep_inp.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
        sweep_feat = str_c.features.sweepFeatures.add(sweep_inp)
        sweep_feat.name = f"{name}_Sweep"
        tenon_body = sweep_feat.bodies.item(0)
        tenon_body.name = f"{name}_Tenon"

        # Step 5: JOIN tenon to stretcher
        sp.combine(str_body, [tenon_body], JOIN, False, f"{name}_Join")
        return find_body(str_body.name)

    # Body-relative refs: stretchers reference legs for positioning
    ref_leg_nl = find_body("Leg_NL")
    ref_leg_nl_bb = ref_leg_nl.boundingBox
    ref_leg_nr = find_body("Leg_NR")
    ref_leg_nr_bb = ref_leg_nr.boundingBox
    ref_leg_fl = find_body("Leg_FL")
    ref_leg_fl_bb = ref_leg_fl.boundingBox

    # ── BACK STRETCHER ────────────────────────────────────────────
    # Runs in X between NR and FR legs (both at large Y) at front_str_h
    bstr_sx_v, bstr_sy_v = splay_center(ev("front_str_h"))
    bstr_x0 = ev("leg_inset_x") - bstr_sx_v + ev("leg_w") / 2 - ev("st_l")
    bstr_y_c = ev("seat_w") - ev("leg_inset_y") + bstr_sy_v
    bstr_z_c = ev("front_str_h")

    BStr_Pl = sp.off_plane(str_c, str_c.xYConstructionPlane, "front_str_h", "BStr_Pl")
    BStr_Sk = str_c.sketches.add(BStr_Pl)
    BStr_Sk.name = "BStr_Sk"
    m2s = BStr_Sk.modelToSketchSpace

    s0 = m2s(P(bstr_x0, bstr_y_c - ev("str_w") / 2, bstr_z_c))
    s1 = m2s(P(bstr_x0 + ev("bstr_len"), bstr_y_c + ev("str_w") / 2, bstr_z_c))
    rect = BStr_Sk.sketchCurves.sketchLines.addTwoPointRectangle(
        P(s0.x, s0.y, 0), P(s1.x, s1.y, 0))
    gc = BStr_Sk.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    d = BStr_Sk.sketchDimensions
    d.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        H, P((s0.x + s1.x) / 2, s0.y - 1, 0)).parameter.expression = "bstr_len"
    d.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        V, P(s1.x + 1, (s0.y + s1.y) / 2, 0)).parameter.expression = "str_w"

    BStr_ext = sp.ext_new_sym(str_c, BStr_Sk.profiles.item(0), "str_t / 2", "BStr")
    Str_Back = BStr_ext.bodies.item(0)
    Str_Back.name = "Str_Back"

    # ── BACK STRETCHER SPLAY (match leg Y-splay) ─────────────
    angle_bs = -ev("splay_w")
    c_bs, s_bs = math.cos(angle_bs), math.sin(angle_bs)
    ty_bs = bstr_y_c - (bstr_y_c * c_bs + bstr_z_c * s_bs)
    tz_bs = bstr_z_c - (-bstr_y_c * s_bs + bstr_z_c * c_bs)
    xf_bs = adsk.core.Matrix3D.create()
    xf_bs.setWithArray([
        1.0,  0.0,   0.0,   0.0,
        0.0,  c_bs,  s_bs,  ty_bs,
        0.0, -s_bs,  c_bs,  tz_bs,
        0.0,  0.0,   0.0,   1.0
    ])
    mc_bs = adsk.core.ObjectCollection.create()
    mc_bs.add(Str_Back)
    mi_bs = str_c.features.moveFeatures.createInput2(mc_bs)
    mi_bs.defineAsFreeMove(xf_bs)
    mf_bs = str_c.features.moveFeatures.add(mi_bs)
    mf_bs.name = "BStr_Splay"
    Str_Back = find_body("Str_Back")

    # Angled tenon at each end (CUT leg -> sweep tenon -> JOIN)
    Str_Back = angled_tenon_end(Str_Back, Leg_NR, BStr_Pl, "x", -1, "BStr_TnL")
    Str_Back = angled_tenon_end(Str_Back, Leg_FR, BStr_Pl, "x", +1, "BStr_TnR")

    # Mirror back stretcher across YMid → front stretcher
    FStr_mir = sp.mirror_bodies(str_c, [Str_Back], YMid, "FStr_Mir")
    Str_Front = FStr_mir.bodies.item(0)
    Str_Front.name = "Str_Front"
    Str_Back = FStr_mir.bodies.item(1)
    Str_Back.name = "Str_Back"

    # ── LEFT SIDE STRETCHER ──────────────────────────────────────
    # Runs in Y between NL and NR legs (both at small X) at side_str_h
    sstr_sx_v, sstr_sy_v = splay_center(ev("side_str_h"))
    sstr_x_c = ev("leg_inset_x") - sstr_sx_v
    sstr_y0 = ev("leg_inset_y") - sstr_sy_v + ev("leg_d") / 2 - ev("st_l")
    sstr_z_c = ev("side_str_h")

    SStr_Pl = sp.off_plane(str_c, str_c.xYConstructionPlane, "side_str_h", "SStr_Pl")
    SStr_Sk = str_c.sketches.add(SStr_Pl)
    SStr_Sk.name = "SStr_Sk"
    m2s = SStr_Sk.modelToSketchSpace

    s0 = m2s(P(sstr_x_c - ev("str_w") / 2, sstr_y0, sstr_z_c))
    s1 = m2s(P(sstr_x_c + ev("str_w") / 2, sstr_y0 + ev("sstr_len"), sstr_z_c))
    rect = SStr_Sk.sketchCurves.sketchLines.addTwoPointRectangle(
        P(s0.x, s0.y, 0), P(s1.x, s1.y, 0))
    gc = SStr_Sk.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    d = SStr_Sk.sketchDimensions
    d.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        H, P((s0.x + s1.x) / 2, s0.y - 1, 0)).parameter.expression = "str_w"
    d.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        V, P(s1.x + 1, (s0.y + s1.y) / 2, 0)).parameter.expression = "sstr_len"

    SStr_ext = sp.ext_new_sym(str_c, SStr_Sk.profiles.item(0), "str_t / 2", "SStr")
    SStr_b = SStr_ext.bodies.item(0)
    SStr_b.name = "Str_Left"

    # ── SIDE STRETCHER SPLAY (match leg X-splay) ─────────────
    angle_ss = ev("splay")
    c_ss, s_ss = math.cos(angle_ss), math.sin(angle_ss)
    tx_ss = sstr_x_c - (sstr_x_c * c_ss + sstr_z_c * s_ss)
    tz_ss = sstr_z_c - (-sstr_x_c * s_ss + sstr_z_c * c_ss)
    xf_ss = adsk.core.Matrix3D.create()
    xf_ss.setWithArray([
        c_ss,  0.0,  s_ss,  tx_ss,
        0.0,   1.0,  0.0,   0.0,
       -s_ss,  0.0,  c_ss,  tz_ss,
        0.0,   0.0,  0.0,   1.0
    ])
    mc_ss = adsk.core.ObjectCollection.create()
    mc_ss.add(SStr_b)
    mi_ss = str_c.features.moveFeatures.createInput2(mc_ss)
    mi_ss.defineAsFreeMove(xf_ss)
    mf_ss = str_c.features.moveFeatures.add(mi_ss)
    mf_ss.name = "SStr_Splay"
    SStr_b = find_body("Str_Left")

    # Angled tenon at each end (before mirror — mirror propagates tenons)
    SStr_b = angled_tenon_end(SStr_b, Leg_NL, SStr_Pl, "y", -1, "SStr_TnN")
    SStr_b = angled_tenon_end(SStr_b, Leg_NR, SStr_Pl, "y", +1, "SStr_TnF")

    # Body-relative ref: right stretcher references left stretcher
    ref_str_left = find_body("Str_Left")
    ref_str_left_bb = ref_str_left.boundingBox

    # Mirror side stretcher across XMid → right side
    RStr_mir = sp.mirror_bodies(str_c, [SStr_b], XMid, "RStr_Mir")
    Str_Right = RStr_mir.bodies.item(0)
    Str_Right.name = "Str_Right"
    SStr_b = RStr_mir.bodies.item(1)
    SStr_b.name = "Str_Left"

    # Body-relative refs: footrest references front stretcher + back stretcher
    ref_str_front = find_body("Str_Front")
    ref_str_front_bb = ref_str_front.boundingBox
    ref_str_back = find_body("Str_Back")
    ref_str_back_bb = ref_str_back.boundingBox

    # ── FOOTREST ──────────────────────────────────────────────────
    # Sits on top of front stretcher — no leg tenons needed
    bstr_sx_v2, bstr_sy_v2 = splay_center(ev("front_str_h"))
    fr_x_c = ev("seat_l") / 2
    fr_y_c = ev("leg_inset_y") - bstr_sy_v2  # front stretcher Y center
    fr_z_c = ev("front_str_h") + ev("str_t") / 2 + ev("fr_t") / 2

    FR_Pl = sp.off_plane(str_c, str_c.xYConstructionPlane,
        "front_str_h + str_t / 2 + fr_t / 2", "FR_Pl")
    FR_Sk = str_c.sketches.add(FR_Pl)
    FR_Sk.name = "FR_Sk"
    m2s = FR_Sk.modelToSketchSpace

    s0 = m2s(P(fr_x_c - ev("fr_len") / 2, fr_y_c - ev("fr_w") / 2, fr_z_c))
    s1 = m2s(P(fr_x_c + ev("fr_len") / 2, fr_y_c + ev("fr_w") / 2, fr_z_c))
    rect = FR_Sk.sketchCurves.sketchLines.addTwoPointRectangle(
        P(s0.x, s0.y, 0), P(s1.x, s1.y, 0))
    gc = FR_Sk.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    d = FR_Sk.sketchDimensions
    d.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        H, P((s0.x + s1.x) / 2, s0.y - 1, 0)).parameter.expression = "fr_len"
    d.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        V, P(s1.x + 1, (s0.y + s1.y) / 2, 0)).parameter.expression = "fr_w"

    FR_ext = sp.ext_new_sym(str_c, FR_Sk.profiles.item(0), "fr_t / 2", "FootrestExt")
    FR_b = FR_ext.bodies.item(0)
    FR_b.name = "Footrest"

    # Trim footrest where it overlaps front legs (cross-component, auto-proxied)
    sp.combine(FR_b, [Leg_NL], CUT, True, "FR_LegTrim_NL")
    FR_b = find_body("Footrest")
    sp.combine(FR_b, [Leg_FL], CUT, True, "FR_LegTrim_FL")
    FR_b = find_body("Footrest")
    Str_Front = find_body("Str_Front")
    sp.combine(FR_b, [Str_Front], CUT, True, "FR_FStrTrim")

    # ── STRETCHER MORTISES (CUT into legs) ────────────────────────
    legs = {n: find_body(n) for n in ["Leg_NL", "Leg_NR", "Leg_FL", "Leg_FR"]}
    Str_Back = find_body("Str_Back")
    Str_Front = find_body("Str_Front")
    Str_Left = find_body("Str_Left")
    Str_Right = find_body("Str_Right")

    # Back stretcher CUTs NR and FR legs
    sp.combine(legs["Leg_NR"], [Str_Back], CUT, True, "BStr_Mort_NR")
    sp.combine(legs["Leg_FR"], [Str_Back], CUT, True, "BStr_Mort_FR")

    # Front stretcher CUTs NL and FL legs
    sp.combine(legs["Leg_NL"], [Str_Front], CUT, True, "FStr_Mort_NL")
    sp.combine(legs["Leg_FL"], [Str_Front], CUT, True, "FStr_Mort_FL")

    # Left side stretcher CUTs NL and NR legs
    sp.combine(legs["Leg_NL"], [Str_Left], CUT, True, "SStr_Mort_NL")
    sp.combine(legs["Leg_NR"], [Str_Left], CUT, True, "SStr_Mort_NR")

    # Right side stretcher CUTs FL and FR legs
    sp.combine(legs["Leg_FL"], [Str_Right], CUT, True, "SStr_Mort_FL")
    sp.combine(legs["Leg_FR"], [Str_Right], CUT, True, "SStr_Mort_FR")

    # ── DETAILS: CHAMFERS ───────────────────────────────────────────
    # Chamfer seat top edges
    Seat = None
    for i in range(seat_c.bRepBodies.count):
        if seat_c.bRepBodies.item(i).name == "Seat":
            Seat = seat_c.bRepBodies.item(i)
            break

    if Seat:
        top_face = sp.find_face(Seat, "z", +1)
        if top_face:
            edges = adsk.core.ObjectCollection.create()
            added = set()
            for i in range(top_face.edges.count):
                e = top_face.edges.item(i)
                if e.tempId not in added:
                    edges.add(e)
                    added.add(e.tempId)
            if edges.count > 0:
                ch_inp = seat_c.features.chamferFeatures.createInput2()
                ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                    edges, VI("0.0625 in"), True)
                ch = seat_c.features.chamferFeatures.add(ch_inp)
                ch.name = "Seat_Ch"

    # Chamfer leg bottom edges (all 4 legs)
    for leg_name in ["Leg_NL", "Leg_NR", "Leg_FL", "Leg_FR"]:
        leg = None
        for i in range(legs_c.bRepBodies.count):
            if legs_c.bRepBodies.item(i).name == leg_name:
                leg = legs_c.bRepBodies.item(i)
                break
        if leg:
            bot_face = sp.find_face(leg, "z", -1)
            if bot_face:
                edges = adsk.core.ObjectCollection.create()
                added = set()
                for i in range(bot_face.edges.count):
                    e = bot_face.edges.item(i)
                    if e.tempId not in added:
                        edges.add(e)
                        added.add(e.tempId)
                if edges.count > 0:
                    try:
                        ch_inp = legs_c.features.chamferFeatures.createInput2()
                        ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                            edges, VI("0.0625 in"), True)
                        ch = legs_c.features.chamferFeatures.add(ch_inp)
                        ch.name = f"{leg_name}_Ch"
                    except:
                        pass  # Skip if chamfer fails on angled face

    # ── EPILOGUE ──────────────────────────────────────────────────
    for comp in [root, seat_c, legs_c, str_c]:
        for s in comp.sketches:
            s.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False
        for ca in comp.constructionAxes:
            ca.isLightBulbOn = False

    all_names = []
    for comp_name, comp in [("Seat", seat_c), ("Legs", legs_c), ("Stretchers", str_c)]:
        names = [comp.bRepBodies.item(i).name for i in range(comp.bRepBodies.count)]
        all_names.extend(names)
        print(f"{comp_name}: {len(names)} bodies -> {names}")
    print(f"Total: {len(all_names)} bodies")

    sp.apply_appearance("white oak")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
