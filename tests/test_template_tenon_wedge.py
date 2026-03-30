"""Tests for tenon_wedge template.

Fixtures
--------
F1  Rect through M&T + 2 wedges         → 4 bodies (leg, rail, 2 wedges)
F2  Round through tenon + 1 wedge       → 3 bodies (seat, spindle, 1 wedge)
    Spindle below seat with smaller-diameter tenon through seat (shoulder)
F3  Rect blind M&T + 2 fox wedges       → 4 bodies (leg, rail, 2 wedges)
F4  Round tenon into round leg          → 3 bodies (leg, stretcher, 1 wedge)

Total: 14 bodies
"""

import adsk.core
import adsk.fusion


def run(context):
    from helpers import sp
    from woodworking.templates import tenon_wedge as tw

    VI = adsk.core.ValueInput.createByString
    P3 = adsk.core.Point3D.create
    V3 = adsk.core.Vector3D.create
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
    NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    NEG = adsk.fusion.ExtentDirections.NegativeExtentDirection
    POS = adsk.fusion.ExtentDirections.PositiveExtentDirection
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
        ("seat_t",     "1 in",     "in"),
        ("rleg_dia",   "1.5 in",   "in"),
        ("rleg_h",     "10 in",    "in"),
        ("str_dia",    "0.75 in",  "in"),
        ("str_tn_dia", "0.375 in", "in"),
        ("str_td",     "1 mm",     "in"),
        ("seat_l",     "10 in",    "in"),
        ("seat_w",     "6 in",     "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    tw.define_params(params)

    # ── Helpers ────────────────────────────────────────────────
    def move_comp(comp, x_cm):
        """Translate all bodies in a component along X."""
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

    # Leg (grain in Z)
    _, pr = sp.sketch_rect_model(f1, f1.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_w", "y": "leg_w"},
        "F1_LegSk", ev)
    f1_leg = sp.ext_new(f1, pr, "leg_h", "F1_Leg").bodies.item(0)
    f1_leg.name = "Leg"

    # Rail (grain in X) — sketch XZ profile, extrude in Y
    rail_pl = sp.off_plane(f1, f1.xZConstructionPlane,
        "(leg_w - rail_t) / 2", "F1_RailPl")
    _, pr = sp.sketch_rect_model(f1, rail_pl,
        ("leg_w", "(leg_w - rail_t) / 2", "leg_h / 2 - rail_w / 2"),
        {"x": "rail_l", "z": "rail_w"},
        "F1_RailSk", ev)
    f1_rail = sp.ext_new(f1, pr, "rail_t", "F1_Rail").bodies.item(0)
    f1_rail.name = "Rail"

    # Tenon on rail left end
    tenon_pl = sp.off_plane(f1, f1.yZConstructionPlane,
        "leg_w", "F1_TenonPl")
    _, tn_prof = sp.sketch_rect_model(f1, tenon_pl,
        ("leg_w", "(leg_w - mt_tt) / 2", "leg_h / 2 - mt_tw / 2"),
        {"y": "mt_tt", "z": "mt_tw"},
        "F1_TenonSk", ev)
    feats = f1.features.extrudeFeatures
    inp = feats.createInput(tn_prof, NEW)
    inp.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(
            VI("leg_w + mt_proud")), NEG)
    f1_tenon = feats.add(inp).bodies.item(0)
    f1_tenon.name = "Tenon"

    # Apply wedges BEFORE join
    # slot spans mt_tt (thin Y dir), wedges offset along mt_tw (wide Z dir)
    tw.rect(f1, tenon_body=f1_tenon, mortise_body=f1_leg,
            tenon_axis="x", tenon_depth_expr="leg_w + mt_proud",
            slot_span_expr="mt_tt", offset_dim_expr="mt_tw",
            name="F1_TW", ev=ev)

    # Join tenon into rail, cut mortise in leg
    sp.combine(f1, f1_rail, f1_tenon, JOIN, False, "F1_Join")
    sp.combine(f1, f1_leg, f1_rail, CUT, True, "F1_Mortise")

    assert f1.bRepBodies.count == 4, \
        f"F1: expected 4, got {f1.bRepBodies.count}"
    print(f"F1 Rect through: {f1.bRepBodies.count} bodies ✓")
    # F1 stays at origin

    # ══════════════════════════════════════════════════════════
    #  F2: Round through tenon + 1 wedge (with shoulder)
    # ══════════════════════════════════════════════════════════
    f2 = sp.make_comp(root, "F2_RoundThrough").component

    seat_l = ev("seat_l"); seat_w = ev("seat_w"); seat_t = ev("seat_t")
    sp_dia = ev("sp_dia"); sp_tn = ev("sp_tn_dia")
    cx, cy = seat_l / 2, seat_w / 2

    # Seat slab on top (z = sp_len to z = sp_len + seat_t)
    # Grain in X (seat_l > seat_w → longest axis = X)
    seat_pl = sp.off_plane(f2, f2.xYConstructionPlane,
        "sp_len", "F2_SeatPl")
    _, pr = sp.sketch_rect_model(f2, seat_pl,
        ("0 in", "0 in", "sp_len"),
        {"x": "seat_l", "y": "seat_w"},
        "F2_SeatSk", ev)
    f2_seat = sp.ext_new(f2, pr, "seat_t", "F2_Seat").bodies.item(0)
    f2_seat.name = "Seat"

    # Spindle below seat (sp_dia, from z=0 to z=sp_len)
    sk_sp = f2.sketches.add(f2.xYConstructionPlane)
    sp_circle = sk_sp.sketchCurves.sketchCircles.addByCenterRadius(
        P3(cx, cy, 0), sp_dia / 2)
    sk_sp.sketchDimensions.addDiameterDimension(
        sp_circle, P3(cx + sp_dia, cy, 0)
    ).parameter.expression = "sp_dia"
    sk_sp.name = "F2_SpindleSk"
    f2_spindle = sp.ext_new(f2, sp.smallest_profile(sk_sp),
        "sp_len", "F2_Spindle").bodies.item(0)
    f2_spindle.name = "Spindle"

    # Tenon (smaller diameter, through seat and protruding above)
    # From z = sp_len to z = sp_len + seat_t + sp_td
    sk_tn = f2.sketches.add(seat_pl)
    tn_circle = sk_tn.sketchCurves.sketchCircles.addByCenterRadius(
        P3(cx, cy, 0), sp_tn / 2)
    sk_tn.sketchDimensions.addDiameterDimension(
        tn_circle, P3(cx + sp_tn, cy, 0)
    ).parameter.expression = "sp_tn_dia"
    sk_tn.name = "F2_TenonSk"
    f2_tenon = sp.ext_new(f2, sp.smallest_profile(sk_tn),
        "seat_t + sp_td", "F2_Tenon").bodies.item(0)
    f2_tenon.name = "Tenon"

    # Wedge on the exposed end above the seat
    tw.round_tenon(f2, tenon_body=f2_tenon, mortise_body=f2_seat,
                   tenon_axis="z", tenon_depth_expr="seat_t + sp_td",
                   tenon_diam_expr="sp_tn_dia",
                   name="F2_TW", ev=ev)

    # Join tenon into spindle, cut seat
    sp.combine(f2, f2_spindle, f2_tenon, JOIN, False, "F2_Join")
    sp.combine(f2, f2_seat, f2_spindle, CUT, True, "F2_Mortise")

    assert f2.bRepBodies.count == 3, \
        f"F2: expected 3, got {f2.bRepBodies.count}"
    move_comp(f2, 30)
    print(f"F2 Round through: {f2.bRepBodies.count} bodies ✓")

    # ══════════════════════════════════════════════════════════
    #  F3: Rect blind M&T + 2 fox wedges
    # ══════════════════════════════════════════════════════════
    f3 = sp.make_comp(root, "F3_RectBlind").component

    lw = ev("leg_w"); lh = ev("leg_h")

    # Leg (grain in Z)
    _, pr = sp.sketch_rect_model(f3, f3.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_w", "y": "leg_w"},
        "F3_LegSk", ev)
    f3_leg = sp.ext_new(f3, pr, "leg_h", "F3_Leg").bodies.item(0)
    f3_leg.name = "Leg"

    # Rail (grain in Y) — sketch YZ profile, extrude in X
    rail_pl3 = sp.off_plane(f3, f3.yZConstructionPlane,
        "(leg_w - rail_t) / 2", "F3_RailPl")
    _, pr = sp.sketch_rect_model(f3, rail_pl3,
        ("(leg_w - rail_t) / 2", "leg_w", "leg_h / 2 - rail_w / 2"),
        {"y": "rail_l", "z": "rail_w"},
        "F3_RailSk", ev)
    f3_rail = sp.ext_new(f3, pr, "rail_t", "F3_Rail").bodies.item(0)
    f3_rail.name = "Rail"

    # Tenon on rail front end — extrude -Y into leg
    tenon_pl3 = sp.off_plane(f3, f3.xZConstructionPlane,
        "leg_w", "F3_TenonPl")
    _, tn_prof3 = sp.sketch_rect_model(f3, tenon_pl3,
        ("(leg_w - mt_tt) / 2", "leg_w", "leg_h / 2 - mt_tw / 2"),
        {"x": "mt_tt", "z": "mt_tw"},
        "F3_TenonSk", ev)
    feats3 = f3.features.extrudeFeatures
    inp3 = feats3.createInput(tn_prof3, NEW)
    inp3.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(VI("mt_td")), NEG)
    f3_tenon = feats3.add(inp3).bodies.item(0)
    f3_tenon.name = "Tenon"

    # Fox wedges
    # slot spans mt_tt (thin X dir), wedges offset along mt_tw (wide Z dir)
    tw.rect(f3, tenon_body=f3_tenon, mortise_body=f3_leg,
            tenon_axis="y", tenon_depth_expr="mt_td",
            slot_span_expr="mt_tt", offset_dim_expr="mt_tw",
            name="F3_TW", ev=ev)

    # Join tenon into rail, cut mortise
    sp.combine(f3, f3_rail, f3_tenon, JOIN, False, "F3_Join")
    sp.combine(f3, f3_leg, f3_rail, CUT, True, "F3_Mortise")

    assert f3.bRepBodies.count == 4, \
        f"F3: expected 4, got {f3.bRepBodies.count}"
    move_comp(f3, 60)
    print(f"F3 Rect blind (fox wedge): {f3.bRepBodies.count} bodies ✓")

    # ══════════════════════════════════════════════════════════
    #  F4: Round tenon into round leg (Windsor-style stretcher)
    # ══════════════════════════════════════════════════════════
    f4 = sp.make_comp(root, "F4_RoundInRound").component

    rleg_dia = ev("rleg_dia"); rleg_h = ev("rleg_h")
    str_dia = ev("str_dia"); str_tn = ev("str_tn_dia")
    str_z = rleg_h / 2  # stretcher at mid-height

    # Round leg (grain in Z, vertical) centered at origin
    sk_rl = f4.sketches.add(f4.xYConstructionPlane)
    rl_circle = sk_rl.sketchCurves.sketchCircles.addByCenterRadius(
        P3(0, 0, 0), rleg_dia / 2)
    sk_rl.sketchDimensions.addDiameterDimension(
        rl_circle, P3(rleg_dia, 0, 0)
    ).parameter.expression = "rleg_dia"
    sk_rl.name = "F4_LegSk"
    f4_leg = sp.ext_new(f4, sp.smallest_profile(sk_rl),
        "rleg_h", "F4_Leg").bodies.item(0)
    f4_leg.name = "Leg"

    # Stretcher (grain in Y) — starts at leg surface, extends in +Y
    # Sketch on XZ plane offset to y = rleg_dia/2 (leg surface)
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
    # +Y = positive direction on XZ plane offset to +Y
    f4_str = sp.ext_new(f4, sp.smallest_profile(sk_str),
        "rail_l", "F4_Str").bodies.item(0)
    f4_str.name = "Stretcher"

    # Round tenon (smaller dia) — from leg surface into leg in -Y,
    # through the full leg diameter + 1mm proud on far side
    sk_tn4 = f4.sketches.add(str_pl)
    s_ctr2 = m2s4(P3(0, rleg_dia / 2, str_z))
    tn4_circle = sk_tn4.sketchCurves.sketchCircles.addByCenterRadius(
        P3(s_ctr2.x, s_ctr2.y, 0), str_tn / 2)
    sk_tn4.sketchDimensions.addDiameterDimension(
        tn4_circle, P3(s_ctr2.x + str_tn, s_ctr2.y, 0)
    ).parameter.expression = "str_tn_dia"
    sk_tn4.name = "F4_TenonSk"
    # -Y = negative direction on this XZ plane
    feats4 = f4.features.extrudeFeatures
    inp4 = feats4.createInput(sp.smallest_profile(sk_tn4), NEW)
    inp4.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(
            VI("rleg_dia + str_td")), NEG)
    f4_tenon = feats4.add(inp4).bodies.item(0)
    f4_tenon.name = "Tenon"

    # Wedge — round tenon through round leg
    tw.round_tenon(f4, tenon_body=f4_tenon, mortise_body=f4_leg,
                   tenon_axis="y", tenon_depth_expr="rleg_dia + str_td",
                   tenon_diam_expr="str_tn_dia",
                   name="F4_TW", ev=ev)

    # Join tenon into stretcher, cut leg
    sp.combine(f4, f4_str, f4_tenon, JOIN, False, "F4_Join")
    sp.combine(f4, f4_leg, f4_str, CUT, True, "F4_Mortise")

    assert f4.bRepBodies.count == 3, \
        f"F4: expected 3, got {f4.bRepBodies.count}"
    move_comp(f4, 90)
    print(f"F4 Round in round: {f4.bRepBodies.count} bodies ✓")

    # ── Epilogue ──────────────────────────────────────────────
    total = sum(root.occurrences.item(i).component.bRepBodies.count
                for i in range(root.occurrences.count))
    print(f"\nTotal: {total} bodies across 4 fixtures")

    sp.apply_appearance("white oak")
    sp.apply_appearance("walnut", bodies=[
        "F1_TW_1", "F1_TW_2", "F2_TW", "F3_TW_1", "F3_TW_2", "F4_TW"])

    for i in range(root.occurrences.count):
        c = root.occurrences.item(i).component
        for j in range(c.sketches.count):
            c.sketches.item(j).isVisible = False
        for j in range(c.constructionPlanes.count):
            c.constructionPlanes.item(j).isLightBulbOn = False
