"""Tests for tenon_wedge template.

Fixtures
--------
F1  Rect through M&T + 2 wedges         → 4 bodies
F2  Round through tenon + 1 wedge       → 3 bodies (shoulder, through seat)
F3  Rect blind M&T + 2 fox wedges       → 4 bodies
F4  Round tenon into round leg          → 3 bodies
F5  Angled round tenon (15° tilt)       → 3 bodies (leg+tenon, slab, wedge)
F6  Compound-angle round-in-round      → 3 bodies (leg, stretcher, wedge)
F7  Cross-component round tenon+wedge  → 3 bodies across 3 comps
    (Seat, Spindle, Tenon each in their own component). Exercises
    tw.round_tenon()'s intersect-trim + wedge CUT via combine.

Total: 22 bodies (F1-F6 = 19 bodies in 6 comps, F7 = 3 bodies in 3 comps).
"""

import adsk.core
import adsk.fusion
import math


def run(context):
    import importlib
    from helpers import sp
    from woodworking.templates import tenon_wedge as tw
    importlib.reload(tw)

    VI = adsk.core.ValueInput.createByString
    P3 = adsk.core.Point3D.create
    V3 = adsk.core.Vector3D.create
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
    NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    NEG = adsk.fusion.ExtentDirections.NegativeExtentDirection
    ctx = sp.DesignContext()
    root = ctx.root
    params = ctx.params
    ev = ctx.ev

    # ── Shared parameters ─────────────────────────────────────
    for pname, expr, unit in [
        ("leg_w",      "2 in",     "in"),
        ("leg_h",      "10 in",    "in"),
        ("rail_w",     "2 in",     "in"),
        ("rail_t",     "1 in",     "in"),
        ("rail_l",     "10 in",    "in"),
        ("mt_tw",      "1.5 in",   "in"),
        ("mt_tt",      "0.5 in",   "in"),
        ("mt_td",      "1.5 in",   "in"),
        ("mt_proud",   "1 mm",     "in"),
        ("sp_dia",     "1 in",     "in"),
        ("sp_tn_dia",  "0.625 in", "in"),
        ("sp_td",      "1 mm",     "in"),
        ("sp_len",     "6 in",     "in"),
        ("rleg_dia",   "1.5 in",   "in"),
        ("rleg_h",     "10 in",    "in"),
        ("str_dia",    "0.75 in",  "in"),
        ("str_tn_dia", "0.375 in", "in"),
        ("str_td",     "1 mm",     "in"),
        ("seat_l",     "10 in",    "in"),
        ("seat_w",     "6 in",     "in"),
        ("seat_t",     "1 in",     "in"),
        ("tilt_ang",   "15",       ""),
        ("tilt_tn_d",  "0.625 in", "in"),
        ("tilt_tn_l",  "1.25 in",  "in"),
        ("tilt_leg_d", "1 in",     "in"),
        ("tilt_leg_l", "8 in",     "in"),
        ("f6_leg_d",   "1.5 in",   "in"),
        ("f6_leg_h",   "10 in",    "in"),
        ("f6_str_d",   "0.75 in",  "in"),
        ("f6_tn_d",    "0.375 in", "in"),
        ("f6_tn_ext",  "1 mm",     "in"),
        ("f6_splay",   "12",       ""),
        ("f6_rake",    "8",        ""),
    ]:
        params.add(pname, VI(expr), unit, "")

    tw.define_params(params)

    def move_comp(comp, x_cm):
        bodies = adsk.core.ObjectCollection.create()
        for i in range(comp.bRepBodies.count):
            bodies.add(comp.bRepBodies.item(i))
        if bodies.count == 0:
            return
        inp = comp.features.moveFeatures.createInput2(bodies)
        mat = adsk.core.Matrix3D.create()
        mat.translation = V3(x_cm, 0, 0)
        inp.defineAsFreeMove(mat)
        comp.features.moveFeatures.add(inp)

    # ══════════════════════════════════════════════════════════
    #  F1: Rectangular through tenon + 2 wedges
    # ══════════════════════════════════════════════════════════
    f1 = sp.make_comp(root, "F1_RectThrough").component

    _, pr = sp.sketch_rect_model(f1, f1.xYConstructionPlane,
        ("0 in", "0 in", "0 in"), {"x": "leg_w", "y": "leg_w"},
        "F1_LegSk", ev)
    f1_leg = sp.ext_new(f1, pr, "leg_h", "F1_Leg").bodies.item(0)
    f1_leg.name = "Leg"

    rail_pl = sp.off_plane(f1, f1.xZConstructionPlane,
        "(leg_w - rail_t) / 2", "F1_RailPl")
    _, pr = sp.sketch_rect_model(f1, rail_pl,
        ("leg_w", "(leg_w - rail_t) / 2", "leg_h / 2 - rail_w / 2"),
        {"x": "rail_l", "z": "rail_w"}, "F1_RailSk", ev)
    f1_rail = sp.ext_new(f1, pr, "rail_t", "F1_Rail").bodies.item(0)
    f1_rail.name = "Rail"

    tenon_pl = sp.off_plane(f1, f1.yZConstructionPlane, "leg_w", "F1_TenonPl")
    _, tn_prof = sp.sketch_rect_model(f1, tenon_pl,
        ("leg_w", "(leg_w - mt_tt) / 2", "leg_h / 2 - mt_tw / 2"),
        {"y": "mt_tt", "z": "mt_tw"}, "F1_TenonSk", ev)
    feats = f1.features.extrudeFeatures
    inp = feats.createInput(tn_prof, NEW)
    inp.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(VI("leg_w + mt_proud")), NEG)
    f1_tenon = feats.add(inp).bodies.item(0)
    f1_tenon.name = "Tenon"

    tw.rect(f1, tenon_body=f1_tenon, mortise_body=f1_leg,
            tenon_axis="x", tenon_depth_expr="leg_w + mt_proud",
            slot_span_expr="mt_tt", offset_dim_expr="mt_tw",
            name="F1_TW", ev=ev)

    sp.combine(f1_rail, f1_tenon, JOIN, False, "F1_Join")
    sp.combine(f1_leg, f1_rail, CUT, True, "F1_Mortise")

    assert f1.bRepBodies.count == 4, f"F1: expected 4, got {f1.bRepBodies.count}"
    print(f"F1 Rect through: {f1.bRepBodies.count} bodies ✓")

    # ══════════════════════════════════════════════════════════
    #  F2: Round through tenon + 1 wedge (shoulder)
    # ══════════════════════════════════════════════════════════
    f2 = sp.make_comp(root, "F2_RoundThrough").component

    seat_l = ev("seat_l"); seat_w = ev("seat_w"); seat_t = ev("seat_t")
    sp_dia = ev("sp_dia"); sp_tn = ev("sp_tn_dia")
    cx, cy = seat_l / 2, seat_w / 2

    seat_pl = sp.off_plane(f2, f2.xYConstructionPlane, "sp_len", "F2_SeatPl")
    _, pr = sp.sketch_rect_model(f2, seat_pl,
        ("0 in", "0 in", "sp_len"),
        {"x": "seat_l", "y": "seat_w"}, "F2_SeatSk", ev)
    f2_seat = sp.ext_new(f2, pr, "seat_t", "F2_Seat").bodies.item(0)
    f2_seat.name = "Seat"

    sk_sp = f2.sketches.add(f2.xYConstructionPlane)
    sp_circle = sk_sp.sketchCurves.sketchCircles.addByCenterRadius(
        P3(cx, cy, 0), sp_dia / 2)
    sk_sp.sketchDimensions.addDiameterDimension(
        sp_circle, P3(cx + sp_dia, cy, 0)).parameter.expression = "sp_dia"
    sk_sp.name = "F2_SpindleSk"
    f2_spindle = sp.ext_new(f2, sp.smallest_profile(sk_sp),
        "sp_len", "F2_Spindle").bodies.item(0)
    f2_spindle.name = "Spindle"

    sk_tn = f2.sketches.add(seat_pl)
    tn_circle = sk_tn.sketchCurves.sketchCircles.addByCenterRadius(
        P3(cx, cy, 0), sp_tn / 2)
    sk_tn.sketchDimensions.addDiameterDimension(
        tn_circle, P3(cx + sp_tn, cy, 0)).parameter.expression = "sp_tn_dia"
    sk_tn.name = "F2_TenonSk"
    f2_tenon = sp.ext_new(f2, sp.smallest_profile(sk_tn),
        "seat_t + sp_td", "F2_Tenon").bodies.item(0)
    f2_tenon.name = "Tenon"

    tw.round_tenon(f2, tenon_body=f2_tenon, mortise_body=f2_seat,
                   tenon_axis="z", tenon_depth_expr="seat_t + sp_td",
                   tenon_diam_expr="sp_tn_dia", name="F2_TW", ev=ev)

    sp.combine(f2_spindle, f2_tenon, JOIN, False, "F2_Join")
    sp.combine(f2_seat, f2_spindle, CUT, True, "F2_Mortise")

    assert f2.bRepBodies.count == 3, f"F2: expected 3, got {f2.bRepBodies.count}"
    move_comp(f2, 30)
    print(f"F2 Round through: {f2.bRepBodies.count} bodies ✓")

    # ══════════════════════════════════════════════════════════
    #  F3: Rect blind M&T + 2 fox wedges
    # ══════════════════════════════════════════════════════════
    f3 = sp.make_comp(root, "F3_RectBlind").component

    lw = ev("leg_w"); lh = ev("leg_h")

    _, pr = sp.sketch_rect_model(f3, f3.xYConstructionPlane,
        ("0 in", "0 in", "0 in"), {"x": "leg_w", "y": "leg_w"},
        "F3_LegSk", ev)
    f3_leg = sp.ext_new(f3, pr, "leg_h", "F3_Leg").bodies.item(0)
    f3_leg.name = "Leg"

    rail_pl3 = sp.off_plane(f3, f3.yZConstructionPlane,
        "(leg_w - rail_t) / 2", "F3_RailPl")
    _, pr = sp.sketch_rect_model(f3, rail_pl3,
        ("(leg_w - rail_t) / 2", "leg_w", "leg_h / 2 - rail_w / 2"),
        {"y": "rail_l", "z": "rail_w"}, "F3_RailSk", ev)
    f3_rail = sp.ext_new(f3, pr, "rail_t", "F3_Rail").bodies.item(0)
    f3_rail.name = "Rail"

    tenon_pl3 = sp.off_plane(f3, f3.xZConstructionPlane, "leg_w", "F3_TenonPl")
    _, tn_prof3 = sp.sketch_rect_model(f3, tenon_pl3,
        ("(leg_w - mt_tt) / 2", "leg_w", "leg_h / 2 - mt_tw / 2"),
        {"x": "mt_tt", "z": "mt_tw"}, "F3_TenonSk", ev)
    feats3 = f3.features.extrudeFeatures
    inp3 = feats3.createInput(tn_prof3, NEW)
    inp3.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(VI("mt_td")), NEG)
    f3_tenon = feats3.add(inp3).bodies.item(0)
    f3_tenon.name = "Tenon"

    tw.rect(f3, tenon_body=f3_tenon, mortise_body=f3_leg,
            tenon_axis="y", tenon_depth_expr="mt_td",
            slot_span_expr="mt_tt", offset_dim_expr="mt_tw",
            name="F3_TW", ev=ev)

    sp.combine(f3_rail, f3_tenon, JOIN, False, "F3_Join")
    sp.combine(f3_leg, f3_rail, CUT, True, "F3_Mortise")

    assert f3.bRepBodies.count == 4, f"F3: expected 4, got {f3.bRepBodies.count}"
    move_comp(f3, 60)
    print(f"F3 Rect blind (fox wedge): {f3.bRepBodies.count} bodies ✓")

    # ══════════════════════════════════════════════════════════
    #  F4: Round tenon into round leg
    # ══════════════════════════════════════════════════════════
    f4 = sp.make_comp(root, "F4_RoundInRound").component

    rleg_dia = ev("rleg_dia"); rleg_h = ev("rleg_h")
    str_dia = ev("str_dia"); str_tn = ev("str_tn_dia")
    str_z = rleg_h / 2

    sk_rl = f4.sketches.add(f4.xYConstructionPlane)
    rl_circle = sk_rl.sketchCurves.sketchCircles.addByCenterRadius(
        P3(0, 0, 0), rleg_dia / 2)
    sk_rl.sketchDimensions.addDiameterDimension(
        rl_circle, P3(rleg_dia, 0, 0)).parameter.expression = "rleg_dia"
    sk_rl.name = "F4_LegSk"
    f4_leg = sp.ext_new(f4, sp.smallest_profile(sk_rl),
        "rleg_h", "F4_Leg").bodies.item(0)
    f4_leg.name = "Leg"

    str_pl = sp.off_plane(f4, f4.xZConstructionPlane,
        "rleg_dia / 2", "F4_StrPl")
    sk_str = f4.sketches.add(str_pl)
    m2s4 = sk_str.modelToSketchSpace
    s_ctr = m2s4(P3(0, rleg_dia / 2, str_z))
    str_circle = sk_str.sketchCurves.sketchCircles.addByCenterRadius(
        P3(s_ctr.x, s_ctr.y, 0), str_dia / 2)
    sk_str.sketchDimensions.addDiameterDimension(
        str_circle, P3(s_ctr.x + str_dia, s_ctr.y, 0)
    ).parameter.expression = "str_dia"
    sk_str.name = "F4_StrSk"
    f4_str = sp.ext_new(f4, sp.smallest_profile(sk_str),
        "rail_l", "F4_Str").bodies.item(0)
    f4_str.name = "Stretcher"

    sk_tn4 = f4.sketches.add(str_pl)
    s_ctr2 = m2s4(P3(0, rleg_dia / 2, str_z))
    tn4_circle = sk_tn4.sketchCurves.sketchCircles.addByCenterRadius(
        P3(s_ctr2.x, s_ctr2.y, 0), str_tn / 2)
    sk_tn4.sketchDimensions.addDiameterDimension(
        tn4_circle, P3(s_ctr2.x + str_tn, s_ctr2.y, 0)
    ).parameter.expression = "str_tn_dia"
    sk_tn4.name = "F4_TenonSk"
    feats4 = f4.features.extrudeFeatures
    inp4 = feats4.createInput(sp.smallest_profile(sk_tn4), NEW)
    inp4.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(
            VI("rleg_dia + str_td")), NEG)
    f4_tenon = feats4.add(inp4).bodies.item(0)
    f4_tenon.name = "Tenon"

    tw.round_tenon(f4, tenon_body=f4_tenon, mortise_body=f4_leg,
                   tenon_axis="y", tenon_depth_expr="rleg_dia + str_td",
                   tenon_diam_expr="str_tn_dia", name="F4_TW", ev=ev)

    sp.combine(f4_str, f4_tenon, JOIN, False, "F4_Join")
    sp.combine(f4_leg, f4_str, CUT, True, "F4_Mortise")

    assert f4.bRepBodies.count == 3, f"F4: expected 3, got {f4.bRepBodies.count}"
    move_comp(f4, 90)
    print(f"F4 Round in round: {f4.bRepBodies.count} bodies ✓")

    # ══════════════════════════════════════════════════════════
    #  F5: Angled round tenon (15° tilt — simulates splayed leg)
    # ══════════════════════════════════════════════════════════
    f5 = sp.make_comp(root, "F5_Angled").component

    # Slab (grain in X, flat)
    _, pr = sp.sketch_rect_model(f5, f5.xYConstructionPlane,
        ("0 in", "0 in", "0 in"), {"x": "seat_l", "y": "seat_w"},
        "F5_SlabSk", ev)
    f5_slab = sp.ext_new(f5, pr, "seat_t", "F5_Slab").bodies.item(0)
    f5_slab.name = "Slab"

    # Tilted leg + tenon through the slab (like a splayed chair leg)
    slab_cx = ev("seat_l") / 2
    slab_cy = ev("seat_w") / 2
    slab_t = ev("seat_t")
    tleg_d = ev("tilt_leg_d")
    tn_dia = ev("tilt_tn_d")
    tn_len = ev("tilt_tn_l")

    # Build leg + tenon vertical, then tilt both together
    # Leg: larger cylinder from z = -(leg_length) to z = 0
    sk_leg5 = f5.sketches.add(f5.xYConstructionPlane)
    lg5_circle = sk_leg5.sketchCurves.sketchCircles.addByCenterRadius(
        P3(slab_cx, slab_cy, 0), tleg_d / 2)
    sk_leg5.sketchDimensions.addDiameterDimension(
        lg5_circle, P3(slab_cx + tleg_d, slab_cy, 0)
    ).parameter.expression = "tilt_leg_d"
    sk_leg5.name = "F5_LegSk"
    feats5 = f5.features.extrudeFeatures
    inp5l = feats5.createInput(sp.smallest_profile(sk_leg5), NEW)
    inp5l.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(VI("tilt_leg_l")), NEG)
    f5_leg = feats5.add(inp5l).bodies.item(0)
    f5_leg.name = "Leg"

    # Tenon: smaller cylinder from z = 0 upward through slab
    sk_t5 = f5.sketches.add(f5.xYConstructionPlane)
    t5_circle = sk_t5.sketchCurves.sketchCircles.addByCenterRadius(
        P3(slab_cx, slab_cy, 0), tn_dia / 2)
    sk_t5.sketchDimensions.addDiameterDimension(
        t5_circle, P3(slab_cx + tn_dia, slab_cy, 0)
    ).parameter.expression = "tilt_tn_d"
    sk_t5.name = "F5_TenonSk"
    f5_tenon = sp.ext_new(f5, sp.smallest_profile(sk_t5),
        "tilt_tn_l", "F5_Tenon").bodies.item(0)
    f5_tenon.name = "Tenon"

    # Tilt leg + tenon 15° around Y axis at slab center
    ang5 = ev("tilt_ang") * math.pi / 180
    tilt_coll = adsk.core.ObjectCollection.create()
    tilt_coll.add(f5_leg)
    tilt_coll.add(f5_tenon)
    tilt_inp = f5.features.moveFeatures.createInput2(tilt_coll)
    rot5 = adsk.core.Matrix3D.create()
    rot5.setToRotation(ang5, V3(0, 1, 0), P3(slab_cx, slab_cy, 0))
    tilt_inp.defineAsFreeMove(rot5)
    f5.features.moveFeatures.add(tilt_inp).name = "F5_Tilt"

    # Find the tilted end face
    end_f5 = sp.find_face(f5_tenon, "z", +1)

    # Wedge on the angled tenon
    tw.round_tenon(f5, tenon_body=f5_tenon, mortise_body=f5_slab,
                   end_face=end_f5,
                   tenon_depth_expr="tilt_tn_l",
                   tenon_diam_expr="tilt_tn_d",
                   name="F5_TW", ev=ev)

    # JOIN tenon into leg, CUT slab
    sp.combine(f5_leg, f5_tenon, JOIN, False, "F5_Join")
    sp.combine(f5_slab, f5_leg, CUT, True, "F5_Mortise")

    assert f5.bRepBodies.count == 3, f"F5: expected 3, got {f5.bRepBodies.count}"
    move_comp(f5, 120)
    print(f"F5 Angled (15°): {f5.bRepBodies.count} bodies ✓")

    # ══════════════════════════════════════════════════════════
    #  F6: Compound-angle round-in-round (splay + rake)
    # ══════════════════════════════════════════════════════════
    f6 = sp.make_comp(root, "F6_CompoundAngle").component

    f6_ld = ev("f6_leg_d"); f6_lh = ev("f6_leg_h")
    f6_sd = ev("f6_str_d"); f6_td = ev("f6_tn_d")

    # Vertical round leg
    sk_l6 = f6.sketches.add(f6.xYConstructionPlane)
    l6_c = sk_l6.sketchCurves.sketchCircles.addByCenterRadius(
        P3(0, 0, 0), f6_ld / 2)
    sk_l6.sketchDimensions.addDiameterDimension(
        l6_c, P3(f6_ld, 0, 0)).parameter.expression = "f6_leg_d"
    sk_l6.name = "F6_LegSk"
    f6_leg = sp.ext_new(f6, sp.smallest_profile(sk_l6),
        "f6_leg_h", "F6_Leg").bodies.item(0)
    f6_leg.name = "Leg"

    # Stretcher: build horizontal at mid-height, then tilt with compound angle
    str_z6 = f6_lh * 0.4
    str_start_y = f6_ld / 2  # start at leg surface

    str_pl6 = sp.off_plane(f6, f6.xZConstructionPlane,
        f"{str_start_y} cm", "F6_StrPl")
    sk_s6 = f6.sketches.add(str_pl6)
    m2s6 = sk_s6.modelToSketchSpace
    sc6 = m2s6(P3(0, str_start_y, str_z6))
    s6_c = sk_s6.sketchCurves.sketchCircles.addByCenterRadius(
        P3(sc6.x, sc6.y, 0), f6_sd / 2)
    sk_s6.sketchDimensions.addDiameterDimension(
        s6_c, P3(sc6.x + f6_sd, sc6.y, 0)).parameter.expression = "f6_str_d"
    sk_s6.name = "F6_StrSk"
    f6_str = sp.ext_new(f6, sp.smallest_profile(sk_s6),
        "rail_l", "F6_Str").bodies.item(0)
    f6_str.name = "Stretcher"

    # Tenon: smaller dia, through leg in -Y
    sk_tn6 = f6.sketches.add(str_pl6)
    sc6b = m2s6(P3(0, str_start_y, str_z6))
    t6_c = sk_tn6.sketchCurves.sketchCircles.addByCenterRadius(
        P3(sc6b.x, sc6b.y, 0), f6_td / 2)
    sk_tn6.sketchDimensions.addDiameterDimension(
        t6_c, P3(sc6b.x + f6_td, sc6b.y, 0)).parameter.expression = "f6_tn_d"
    sk_tn6.name = "F6_TenonSk"
    inp6 = f6.features.extrudeFeatures.createInput(
        sp.smallest_profile(sk_tn6), NEW)
    inp6.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(
            VI("f6_leg_d + f6_tn_ext")), NEG)
    f6_tenon = f6.features.extrudeFeatures.add(inp6).bodies.item(0)
    f6_tenon.name = "Tenon"

    # Tilt stretcher + tenon with compound angle (splay in X, rake in Z)
    splay_rad = ev("f6_splay") * math.pi / 180
    rake_rad = ev("f6_rake") * math.pi / 180
    # Rotate around Z (splay), then around X (rake), pivot at leg center
    pivot = P3(0, 0, str_z6)
    rot_splay = adsk.core.Matrix3D.create()
    rot_splay.setToRotation(splay_rad, V3(0, 0, 1), pivot)
    rot_rake = adsk.core.Matrix3D.create()
    rot_rake.setToRotation(rake_rad, V3(1, 0, 0), pivot)
    compound = adsk.core.Matrix3D.create()
    compound.transformBy(rot_splay)
    compound.transformBy(rot_rake)

    tilt6_coll = adsk.core.ObjectCollection.create()
    tilt6_coll.add(f6_str)
    tilt6_coll.add(f6_tenon)
    tilt6_inp = f6.features.moveFeatures.createInput2(tilt6_coll)
    tilt6_inp.defineAsFreeMove(compound)
    f6.features.moveFeatures.add(tilt6_inp).name = "F6_Tilt"

    # Find the tilted tenon end face
    end_f6 = sp.find_face(f6_tenon, "y", -1)

    # Wedge
    tw.round_tenon(f6, tenon_body=f6_tenon, mortise_body=f6_leg,
                   end_face=end_f6,
                   tenon_depth_expr="f6_leg_d + f6_tn_ext",
                   tenon_diam_expr="f6_tn_d",
                   name="F6_TW", ev=ev)

    # JOIN tenon into stretcher, CUT leg
    sp.combine(f6_str, f6_tenon, JOIN, False, "F6_Join")
    sp.combine(f6_leg, f6_str, CUT, True, "F6_Mortise")

    assert f6.bRepBodies.count == 3, f"F6: expected 3, got {f6.bRepBodies.count}"
    move_comp(f6, 150)
    print(f"F6 Compound angle (splay+rake): {f6.bRepBodies.count} bodies ✓")

    # ══════════════════════════════════════════════════════════
    #  F7: Cross-component — Seat, Spindle, and Tenon each in
    #      their own root-level component. Exercises round_tenon()
    #      routing its intersect-trim and CUT across components.
    # ══════════════════════════════════════════════════════════
    f7_seat = sp.make_comp(root, "F7_Seat").component
    f7_spindle = sp.make_comp(root, "F7_Spindle").component
    f7_tenon_c = sp.make_comp(root, "F7_Tenon").component

    cx7, cy7 = ev("seat_l") / 2, ev("seat_w") / 2

    # Seat in F7_Seat (flat plate like F2)
    seat_pl7 = sp.off_plane(f7_seat, f7_seat.xYConstructionPlane,
                             "sp_len", "F7_SeatPl")
    _, pr = sp.sketch_rect_model(f7_seat, seat_pl7,
        ("0 in", "0 in", "sp_len"),
        {"x": "seat_l", "y": "seat_w"}, "F7_SeatSk", ev)
    f7_seat_b = sp.ext_new(f7_seat, pr, "seat_t", "F7_Seat").bodies.item(0)
    f7_seat_b.name = "F7_SeatBody"

    # Spindle in F7_Spindle (at same world coords as F2's spindle)
    sk_sp7 = f7_spindle.sketches.add(f7_spindle.xYConstructionPlane)
    sp7_circle = sk_sp7.sketchCurves.sketchCircles.addByCenterRadius(
        P3(cx7, cy7, 0), ev("sp_dia") / 2)
    sk_sp7.sketchDimensions.addDiameterDimension(
        sp7_circle, P3(cx7 + ev("sp_dia"), cy7, 0)
    ).parameter.expression = "sp_dia"
    sk_sp7.name = "F7_SpindleSk"
    f7_spindle_b = sp.ext_new(f7_spindle, sp.smallest_profile(sk_sp7),
        "sp_len", "F7_Spindle").bodies.item(0)
    f7_spindle_b.name = "F7_SpindleBody"

    # Tenon in F7_Tenon — each sub-component needs its OWN construction
    # plane; Fusion rejects a sketch when the planar entity lives in a
    # different component's assembly context.
    tenon_pl7 = sp.off_plane(f7_tenon_c, f7_tenon_c.xYConstructionPlane,
                             "sp_len", "F7_TenonPl")
    sk_tn7 = f7_tenon_c.sketches.add(tenon_pl7)
    tn7_circle = sk_tn7.sketchCurves.sketchCircles.addByCenterRadius(
        P3(cx7, cy7, 0), ev("sp_tn_dia") / 2)
    sk_tn7.sketchDimensions.addDiameterDimension(
        tn7_circle, P3(cx7 + ev("sp_tn_dia"), cy7, 0)
    ).parameter.expression = "sp_tn_dia"
    sk_tn7.name = "F7_TenonSk"
    f7_tenon_b = sp.ext_new(f7_tenon_c, sp.smallest_profile(sk_tn7),
        "seat_t + sp_td", "F7_Tenon").bodies.item(0)
    f7_tenon_b.name = "F7_TenonBody"

    # round_tenon: tenon_body in F7_Tenon, mortise_body in F7_Seat —
    # different components. Both intersect-trim and wedge CUT must
    # route through combine to land at root with proxies.
    tw.round_tenon(f7_tenon_c,
                   tenon_body=f7_tenon_b, mortise_body=f7_seat_b,
                   tenon_axis="z",
                   tenon_depth_expr="seat_t + sp_td",
                   tenon_diam_expr="sp_tn_dia",
                   name="F7_TW", ev=ev)

    # JOIN tenon into spindle; CUT seat with spindle (both cross-comp)
    sp.combine(f7_spindle_b, f7_tenon_b, JOIN, False, "F7_Join")
    sp.combine(f7_seat_b, f7_spindle_b, CUT, True, "F7_Mortise")

    assert f7_seat.bRepBodies.count == 1, \
        f"F7_Seat expected 1 body, got {f7_seat.bRepBodies.count}"
    assert f7_spindle.bRepBodies.count == 1, \
        f"F7_Spindle expected 1 body, got {f7_spindle.bRepBodies.count}"
    assert f7_tenon_c.bRepBodies.count == 1, \
        f"F7_Tenon expected 1 body (wedge only, tenon absorbed by JOIN), got {f7_tenon_c.bRepBodies.count}"
    move_comp(f7_seat, 180)
    move_comp(f7_spindle, 180)
    move_comp(f7_tenon_c, 180)
    print("F7 Cross-component round tenon: 3 bodies across 3 comps ✓")

    # ── Epilogue ──────────────────────────────────────────────
    total = sum(root.occurrences.item(i).component.bRepBodies.count
                for i in range(root.occurrences.count))
    n_fixtures = root.occurrences.count
    print(f"\nTotal: {total} bodies across {n_fixtures} components")

    sp.apply_appearance("white oak")
    sp.apply_appearance("walnut", bodies=[
        "F1_TW_1", "F1_TW_2", "F2_TW", "F3_TW_1", "F3_TW_2",
        "F4_TW", "F5_TW", "F6_TW", "F7_TW"])

    for i in range(root.occurrences.count):
        c = root.occurrences.item(i).component
        for j in range(c.sketches.count):
            c.sketches.item(j).isVisible = False
        for j in range(c.constructionPlanes.count):
            c.constructionPlanes.item(j).isLightBulbOn = False
