"""Counter Stool — Parametric Fusion 360 Model
Splayed legs with through-tenons, stretchers with stopped tenons, footrest."""
import adsk.core, adsk.fusion, math
from helpers import af


def run(context):
    app = adsk.core.Application.get()

    # Close unsaved docs
    while True:
        doc = app.activeDocument
        if doc and not doc.isSaved:
            doc.close(False)
        else:
            break
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
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
        # Domino
        ("dm_w", "8 mm", "in", "Domino width (narrow)"),
        ("dm_h", "40 mm", "in", "Domino height (long)"),
        ("dm_d", "15 mm", "in", "Domino depth per side"),
        # Stretchers
        ("str_t", "0.875 in", "in", "Stretcher thickness"),
        ("str_w", "1.25 in", "in", "Stretcher width"),
        ("front_str_h", "7 in", "in", "Front stretcher center Z"),
        ("side_str_h", "4.5 in", "in", "Side stretcher center Z"),
        # Stopped tenon
        ("st_w", "1 in", "in", "Stopped tenon width"),
        ("st_d", "0.375 in", "in", "Stopped tenon depth"),
        ("st_l", "0.875 in", "in", "Stopped tenon length"),
        # Footrest
        ("fr_t", "0.625 in", "in", "Footrest thickness"),
        ("fr_w", "1.75 in", "in", "Footrest width"),
        ("fr_h", "7 in", "in", "Footrest height from floor"),
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

    # ── MIDPLANES ─────────────────────────────────────────────────
    XMid = af.off_plane(root, root.yZConstructionPlane, "seat_l / 2", "XMid")
    YMid = af.off_plane(root, root.xZConstructionPlane, "seat_w / 2", "YMid")

    # ── SEAT ──────────────────────────────────────────────────────
    Seat_Pl = af.off_plane(root, root.xYConstructionPlane, "seat_z", "Seat_Pl")

    sk, prof = af.sketch_rect_model(root, Seat_Pl,
        ("0 in", "0 in", "seat_z"),
        {"x": "seat_l", "y": "seat_w"},
        "Seat_Sk", ev=ev)
    SeatBoard = af.ext_new(root, prof, "seat_t", "SeatBoard")
    Seat = SeatBoard.bodies.item(0)
    Seat.name = "Seat"

    # ── NEAR-LEFT LEG ─────────────────────────────────────────────
    # Trapezoid sketch on XZ plane offset to leg front face.
    # X-splay is built into the trapezoid; Y-splay applied via Move.
    LegFront_Pl = af.off_plane(root, root.xZConstructionPlane,
        "leg_inset_y - leg_d / 2", "LegFront_Pl")

    Leg_NL_Sk = root.sketches.add(LegFront_Pl)
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

    Leg_NL_ext = af.ext_new(root, Leg_NL_Sk.profiles.item(0), "leg_d", "Leg_NL")
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
    move_inp = root.features.moveFeatures.createInput2(move_coll)
    move_inp.defineAsFreeMove(xform)
    move_feat = root.features.moveFeatures.add(move_inp)
    move_feat.name = "YSplay_NL"

    # ── TRIM LEG TOP (CUT before mirror — one CUT instead of four) ──
    Leg_NL_b = None
    Seat_tmp = None
    for i in range(root.bRepBodies.count):
        b = root.bRepBodies.item(i)
        if b.name == "Leg_NL":
            Leg_NL_b = b
        elif b.name == "Seat":
            Seat_tmp = b
    af.combine(root, Leg_NL_b, [Seat_tmp], CUT, True, "LegTrim_NL")

    # ── MIRROR LEGS ────────────────────────────────────────────────

    # Mirror NL across YMid → NR
    NR_mir = af.mirror_bodies(root, [Leg_NL_b], YMid, "Leg_NR_Mir")
    Leg_NR = NR_mir.bodies.item(0)
    Leg_NR.name = "Leg_NR"
    Leg_NL = NR_mir.bodies.item(1)
    Leg_NL.name = "Leg_NL"

    # Mirror NL+NR across XMid → FL, FR
    Far_mir = af.mirror_bodies(root, [Leg_NL, Leg_NR], XMid, "Legs_Far_Mir")
    Leg_FL = Far_mir.bodies.item(0)
    Leg_FL.name = "Leg_FL"
    Leg_FR = Far_mir.bodies.item(1)
    Leg_FR.name = "Leg_FR"
    Leg_NL = Far_mir.bodies.item(2)
    Leg_NL.name = "Leg_NL"
    Leg_NR = Far_mir.bodies.item(3)
    Leg_NR.name = "Leg_NR"

    # ── DOMINO JOINTS (legs to seat) ─────────────────────────────
    # One domino per leg, centered at (leg_inset_x, leg_inset_y, seat_z)
    # dm_h along X (leg width), dm_w along Y (leg depth), dm_d into each piece
    sk_dm, dm_prof = af.sketch_rect_model(root, Seat_Pl,
        ("leg_inset_x - dm_h / 2", "leg_inset_y - dm_w / 2", "seat_z"),
        {"x": "dm_h", "y": "dm_w"},
        "DM_NL_Sk", ev=ev)
    DM_NL = af.ext_new_sym(root, dm_prof, "dm_d", "DM_NL")
    DM_NL_b = DM_NL.bodies.item(0)
    DM_NL_b.name = "DM_NL"

    # Mirror NL → NR across YMid
    DM_NR_mir = af.mirror_bodies(root, [DM_NL_b], YMid, "DM_NR_Mir")
    DM_NR_b = DM_NR_mir.bodies.item(0)
    DM_NR_b.name = "DM_NR"
    DM_NL_b = DM_NR_mir.bodies.item(1)
    DM_NL_b.name = "DM_NL"

    # Mirror NL+NR → FL, FR across XMid
    DM_Far_mir = af.mirror_bodies(root, [DM_NL_b, DM_NR_b], XMid, "DM_Far_Mir")
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
    for i in range(root.bRepBodies.count):
        b = root.bRepBodies.item(i)
        if b.name == "Seat":
            Seat = b
            break

    # CUT all 4 domino voids into seat (keepTool=True — dominos visible)
    af.combine(root, Seat, [DM_NL_b, DM_NR_b, DM_FL_b, DM_FR_b], CUT, True, "DM_Seat_Cut")

    # CUT each domino into its leg (keepTool=True)
    af.combine(root, Leg_NL, [DM_NL_b], CUT, True, "DM_Leg_NL")
    af.combine(root, Leg_NR, [DM_NR_b], CUT, True, "DM_Leg_NR")
    af.combine(root, Leg_FL, [DM_FL_b], CUT, True, "DM_Leg_FL")
    af.combine(root, Leg_FR, [DM_FR_b], CUT, True, "DM_Leg_FR")

    # ── STRETCHER DERIVED PARAMS ───────────────────────────────────
    # Splay-adjusted lengths ensure stretchers reach into legs at any splay angle
    for name, expr, unit, comment in [
        ("bstr_sx", "splay_shift * (leg_top_z - front_str_h) / leg_top_z", "in", "Back str X splay"),
        ("bstr_sy", "splay_shift_w * (leg_top_z - front_str_h) / leg_top_z", "in", "Back str Y splay"),
        ("bstr_len", "seat_l - 2 * leg_inset_x + 2 * bstr_sx - leg_w + 2 * st_l", "in", "Back str total length"),
        ("sstr_sx", "splay_shift * (leg_top_z - side_str_h) / leg_top_z", "in", "Side str X splay"),
        ("sstr_sy", "splay_shift_w * (leg_top_z - side_str_h) / leg_top_z", "in", "Side str Y splay"),
        ("sstr_len", "seat_w - 2 * leg_inset_y + 2 * sstr_sy - leg_d + 2 * st_l", "in", "Side str total length"),
        ("fr_sx", "splay_shift * (leg_top_z - fr_h) / leg_top_z", "in", "Footrest X splay"),
        ("fr_sy", "splay_shift_w * (leg_top_z - fr_h) / leg_top_z", "in", "Footrest Y splay"),
        ("fr_len", "seat_l - 2 * leg_inset_x + 2 * fr_sx - leg_w + 2 * st_l", "in", "Footrest total length"),
    ]:
        params.add(name, VI(expr), unit, comment)

    leg_top_z_val = ev("leg_top_z")

    # Helper: compute splay-adjusted center position at a given height
    def splay_center(h):
        """Return (sx, sy) — splay offset at height h (cm values)."""
        frac = (leg_top_z_val - h) / leg_top_z_val
        return ev("splay_shift") * frac, ev("splay_shift_w") * frac

    # Helper: CUT shoulder from one end face, leaving centered tenon st_w × st_d
    def shoulder_cut_end(body, axis, direction, name):
        face = af.find_face(body, axis, direction)
        sk = root.sketches.add(face)
        sk.name = f"{name}_Sk"
        m2s_fn = sk.modelToSketchSpace
        pof = face.pointOnFace
        cx, cy, cz = pof.x, pof.y, pof.z
        hw, hd = ev("st_w") / 2, ev("st_d") / 2

        if axis == "x":   # face in YZ plane
            c0 = m2s_fn(P(cx, cy - hw, cz - hd))
            c1 = m2s_fn(P(cx, cy + hw, cz + hd))
        else:             # axis == "y", face in XZ plane
            c0 = m2s_fn(P(cx - hw, cy, cz - hd))
            c1 = m2s_fn(P(cx + hw, cy, cz + hd))

        rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(
            P(c0.x, c0.y, 0), P(c1.x, c1.y, 0))
        _gc = sk.geometricConstraints
        _gc.addHorizontal(rect[0]); _gc.addHorizontal(rect[2])
        _gc.addVertical(rect[1]); _gc.addVertical(rect[3])

        h_ax, v_ax = af.probe_sketch_axes(sk)
        h_expr = "st_d" if h_ax == "z" else "st_w"
        v_expr = "st_d" if v_ax == "z" else "st_w"

        _d = sk.sketchDimensions
        mid = P((c0.x + c1.x) / 2, (c0.y + c1.y) / 2, 0)
        _d.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
            H, P(mid.x, c0.y - 0.5, 0)).parameter.expression = h_expr
        _d.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
            V, P(c1.x + 0.5, mid.y, 0)).parameter.expression = v_expr

        shoulder_prof = max(
            (sk.profiles.item(i) for i in range(sk.profiles.count)),
            key=lambda p: p.areaProperties().area)
        af.ext_op(root, shoulder_prof, "st_l", CUT, body, name, flip=True)

    # ── BACK STRETCHER ────────────────────────────────────────────
    # Runs in X between NR and FR legs (both at large Y) at front_str_h
    bstr_sx_v, bstr_sy_v = splay_center(ev("front_str_h"))
    bstr_x0 = ev("leg_inset_x") - bstr_sx_v + ev("leg_w") / 2 - ev("st_l")
    bstr_y_c = ev("seat_w") - ev("leg_inset_y") + bstr_sy_v
    bstr_z_c = ev("front_str_h")

    BStr_Pl = af.off_plane(root, root.xYConstructionPlane, "front_str_h", "BStr_Pl")
    BStr_Sk = root.sketches.add(BStr_Pl)
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

    BStr_ext = af.ext_new_sym(root, BStr_Sk.profiles.item(0), "str_t / 2", "BStr")
    Str_Back = BStr_ext.bodies.item(0)
    Str_Back.name = "Str_Back"

    # Shoulder CUTs — reduce ends to st_w × st_d tenon
    shoulder_cut_end(Str_Back, "x", -1, "BStr_ShL")
    shoulder_cut_end(Str_Back, "x", +1, "BStr_ShR")

    # ── LEFT SIDE STRETCHER ──────────────────────────────────────
    # Runs in Y between NL and NR legs (both at small X) at side_str_h
    sstr_sx_v, sstr_sy_v = splay_center(ev("side_str_h"))
    sstr_x_c = ev("leg_inset_x") - sstr_sx_v
    sstr_y0 = ev("leg_inset_y") - sstr_sy_v + ev("leg_d") / 2 - ev("st_l")
    sstr_z_c = ev("side_str_h")

    SStr_Pl = af.off_plane(root, root.xYConstructionPlane, "side_str_h", "SStr_Pl")
    SStr_Sk = root.sketches.add(SStr_Pl)
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

    SStr_ext = af.ext_new_sym(root, SStr_Sk.profiles.item(0), "str_t / 2", "SStr")
    SStr_b = SStr_ext.bodies.item(0)
    SStr_b.name = "Str_Left"

    # Shoulder CUTs — reduce ends to st_w × st_d tenon (before mirror)
    shoulder_cut_end(SStr_b, "y", -1, "SStr_ShN")
    shoulder_cut_end(SStr_b, "y", +1, "SStr_ShF")

    # Mirror side stretcher across XMid → right side
    RStr_mir = af.mirror_bodies(root, [SStr_b], XMid, "RStr_Mir")
    Str_Right = RStr_mir.bodies.item(0)
    Str_Right.name = "Str_Right"
    SStr_b = RStr_mir.bodies.item(1)
    SStr_b.name = "Str_Left"

    # ── FOOTREST ──────────────────────────────────────────────────
    # Runs in X between NL and FL legs (both at small Y) at fr_h
    fr_sx_v, fr_sy_v = splay_center(ev("fr_h"))
    fr_x0 = ev("leg_inset_x") - fr_sx_v + ev("leg_w") / 2 - ev("st_l")
    fr_y_c = ev("leg_inset_y") - fr_sy_v
    fr_z_c = ev("fr_h")

    FR_Pl = af.off_plane(root, root.xYConstructionPlane, "fr_h", "FR_Pl")
    FR_Sk = root.sketches.add(FR_Pl)
    FR_Sk.name = "FR_Sk"
    m2s = FR_Sk.modelToSketchSpace

    s0 = m2s(P(fr_x0, fr_y_c - ev("fr_w") / 2, fr_z_c))
    s1 = m2s(P(fr_x0 + ev("fr_len"), fr_y_c + ev("fr_w") / 2, fr_z_c))
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

    FR_ext = af.ext_new_sym(root, FR_Sk.profiles.item(0), "fr_t / 2", "FootrestExt")
    FR_b = FR_ext.bodies.item(0)
    FR_b.name = "Footrest"

    # Shoulder CUTs — reduce ends to st_w × st_d tenon
    shoulder_cut_end(FR_b, "x", -1, "FR_ShL")
    shoulder_cut_end(FR_b, "x", +1, "FR_ShR")

    # ── STRETCHER MORTISES (CUT into legs) ────────────────────────
    def find_body(name):
        for i in range(root.bRepBodies.count):
            b = root.bRepBodies.item(i)
            if b.name == name:
                return b
        return None

    legs = {n: find_body(n) for n in ["Leg_NL", "Leg_NR", "Leg_FL", "Leg_FR"]}
    Str_Back = find_body("Str_Back")
    Str_Left = find_body("Str_Left")
    Str_Right = find_body("Str_Right")
    FR_b = find_body("Footrest")

    # Back stretcher CUTs NR and FR legs
    af.combine(root, legs["Leg_NR"], [Str_Back], CUT, True, "BStr_Mort_NR")
    af.combine(root, legs["Leg_FR"], [Str_Back], CUT, True, "BStr_Mort_FR")

    # Left side stretcher CUTs NL and NR legs
    af.combine(root, legs["Leg_NL"], [Str_Left], CUT, True, "SStr_Mort_NL")
    af.combine(root, legs["Leg_NR"], [Str_Left], CUT, True, "SStr_Mort_NR")

    # Right side stretcher CUTs FL and FR legs
    af.combine(root, legs["Leg_FL"], [Str_Right], CUT, True, "SStr_Mort_FL")
    af.combine(root, legs["Leg_FR"], [Str_Right], CUT, True, "SStr_Mort_FR")

    # Footrest CUTs NL and FL legs
    af.combine(root, legs["Leg_NL"], [FR_b], CUT, True, "FR_Mort_NL")
    af.combine(root, legs["Leg_FL"], [FR_b], CUT, True, "FR_Mort_FL")

    # ── DETAILS: CHAMFERS ───────────────────────────────────────────
    # Chamfer seat top edges
    Seat = None
    for i in range(root.bRepBodies.count):
        if root.bRepBodies.item(i).name == "Seat":
            Seat = root.bRepBodies.item(i)
            break

    if Seat:
        top_face = af.find_face(Seat, "z", +1)
        if top_face:
            edges = adsk.core.ObjectCollection.create()
            added = set()
            for i in range(top_face.edges.count):
                e = top_face.edges.item(i)
                if e.tempId not in added:
                    edges.add(e)
                    added.add(e.tempId)
            if edges.count > 0:
                ch_inp = root.features.chamferFeatures.createInput2()
                ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                    edges, VI("0.0625 in"), True)
                ch = root.features.chamferFeatures.add(ch_inp)
                ch.name = "Seat_Ch"

    # Chamfer leg bottom edges (all 4 legs)
    for leg_name in ["Leg_NL", "Leg_NR", "Leg_FL", "Leg_FR"]:
        leg = None
        for i in range(root.bRepBodies.count):
            if root.bRepBodies.item(i).name == leg_name:
                leg = root.bRepBodies.item(i)
                break
        if leg:
            bot_face = af.find_face(leg, "z", -1)
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
                        ch_inp = root.features.chamferFeatures.createInput2()
                        ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                            edges, VI("0.0625 in"), True)
                        ch = root.features.chamferFeatures.add(ch_inp)
                        ch.name = f"{leg_name}_Ch"
                    except:
                        pass  # Skip if chamfer fails on angled face

    # ── EPILOGUE ──────────────────────────────────────────────────
    for s in root.sketches:
        s.isVisible = False
    for cp in root.constructionPlanes:
        cp.isLightBulbOn = False
    for ca in root.constructionAxes:
        ca.isLightBulbOn = False

    names = [root.bRepBodies.item(i).name for i in range(root.bRepBodies.count)]
    print(f"Root: {len(names)} bodies -> {names}")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
