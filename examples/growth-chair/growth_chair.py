"""Growth Chair — Tripp Trapp-inspired adjustable children's chair.

Two leaning L-side frames (leg + floor runner, through-M&T), a 13-slot
horizontal dado ladder on each leg's inner face, adjustable seat and
footrest panels, two curved back rails, a floor stretcher, and two steel
tie rods.

Coordinates: X = width, Y = depth (front at y=0), Z = up.
Left leg front-bottom corner at the world origin (root body).
"""

import math

import adsk.core
import adsk.fusion

from helpers import sp

NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
P3 = adsk.core.Point3D
HOR = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation

USER_PARAMS = [
    ("chair_h", "31.5 in", "in", "Overall height (top of legs)"),
    ("leg_lean", "20", "", "Leg lean from vertical (degrees)"),
    ("leg_thick", "0.875 in", "in", "Leg board thickness"),
    ("leg_w", "2.75 in", "in", "Leg board width (along lean)"),
    ("runner_len", "18.5 in", "in", "Floor runner length"),
    ("runner_thick", "leg_thick", "in", "Runner thickness (flush with legs)"),
    ("runner_h", "1.75 in", "in", "Runner height"),
    ("outer_w", "18 in", "in", "Overall width over runners"),
    ("panel_thick", "0.75 in", "in", "Seat/footrest panel thickness"),
    ("groove_d", "0.3 in", "in", "Ladder groove depth into leg"),
    ("slot_pitch", "1.5 in", "in", "Ladder slot vertical pitch"),
    ("ladder_z0", "4 in", "in", "First slot height above floor"),
    ("n_slots", "13", "", "Number of ladder slots"),
    ("seat_slot", "10", "", "Seat slot index (0-based)"),
    ("foot_slot", "4", "", "Footrest slot index (0-based)"),
    ("seat_d", "9 in", "in", "Seat panel depth"),
    ("foot_d", "11 in", "in", "Footrest panel depth"),
    ("rail_h", "2.4 in", "in", "Back rail height"),
    ("rail_thick", "0.8 in", "in", "Back rail thickness"),
    ("rail_gap", "1.4 in", "in", "Gap between back rails"),
    ("rail_top_off", "1 in", "in", "Leg top above top rail"),
    ("rail_sag", "0.75 in", "in", "Back rail curve sagitta"),
    ("rod_dia", "0.375 in", "in", "Tie rod diameter"),
    ("str_z0", "0.25 in", "in", "Stretcher bottom above floor"),
    ("str_h", "runner_h - str_z0", "in", "Stretcher height (top flush w/ runner)"),
    ("str_thick", "0.8 in", "in", "Floor stretcher thickness"),
    ("str_setback", "3 in", "in", "Stretcher rear face from runner rear"),
    ("run_ten_h", "1.25 in", "in", "Runner tenon height"),
    ("run_ten_t", "0.375 in", "in", "Runner tenon thickness"),
    ("run_ten_z0", "0.25 in", "in", "Runner tenon bottom above floor"),
    ("rt_tt", "0.4 in", "in", "Rail tenon thickness"),
    ("rt_td", "0.5 in", "in", "Rail tenon depth into leg"),
    ("st_tw", "0.45 in", "in", "Stretcher tenon height (z)"),
    ("st_tt", "0.55 in", "in", "Stretcher tenon width (y, along runner grain)"),
    ("st_td", "0.5 in", "in", "Stretcher tenon depth"),
    ("st_tz0", "0.5 in", "in", "Stretcher tenon bottom above floor"),
    ("rod_z_off", "0.35 in", "in", "Tie rod center below panel underside"),
]

DERIVED_PARAMS = [
    ("lean_t", "tan(leg_lean * 1 deg)", "", "tan of leg lean"),
    ("lean_c", "cos(leg_lean * 1 deg)", "", "cos of leg lean"),
    ("leg_len", "chair_h / lean_c", "in", "Leg length along its axis"),
    ("leg_run", "leg_w / lean_c", "in", "Leg horizontal footprint depth"),
    ("leg_x0", "(runner_thick - leg_thick) / 2", "in", "Left leg outer face x"),
    ("leg_in_x", "(runner_thick + leg_thick) / 2", "in", "Left leg inner face x"),
    ("ladder_top", "ladder_z0 + (n_slots - 1) * slot_pitch + panel_thick", "in",
     "Top of highest slot"),
    ("slot_y0", "ladder_z0 * lean_t - 0.3 in", "in", "Slot tool front y"),
    ("slot_ylen", "ladder_top * lean_t + leg_run + 0.3 in - slot_y0", "in",
     "Slot tool y length"),
    ("panel_w", "outer_w - 2 * leg_in_x + 2 * groove_d", "in", "Panel width"),
    ("panel_x0", "leg_in_x - groove_d", "in", "Panel left edge x"),
    ("seat_z", "ladder_z0 + seat_slot * slot_pitch", "in", "Seat underside z"),
    ("foot_z", "ladder_z0 + foot_slot * slot_pitch", "in", "Footrest underside z"),
    ("seat_y1", "(seat_z + panel_thick) * lean_t + leg_run", "in", "Seat rear edge y"),
    ("foot_y1", "(foot_z + panel_thick) * lean_t + leg_run", "in", "Footrest rear edge y"),
    ("rail1_z", "chair_h - rail_top_off - rail_h", "in", "Top rail bottom z"),
    ("rail2_z", "rail1_z - rail_gap - rail_h", "in", "Low rail bottom z"),
    ("rail_chord", "outer_w - runner_thick - leg_thick", "in", "Rail chord between legs"),
    ("rail1_yc", "(rail1_z + rail_h / 2) * lean_t + leg_run / 2", "in",
     "Rail end mating face centered on the leg at rail mid-height"),
    ("rail_R", "rail_chord ^ 2 / (8 * rail_sag) + rail_sag / 2", "in", "Rail arc radius"),
    ("rt_tw", "rail_h - 0.8 in", "in", "Rail tenon height"),
]


def _line(coll_or_sk):
    """Longest SketchLine in a projection result collection."""
    best, best_l = None, 0.0
    for i in range(coll_or_sk.count):
        e = coll_or_sk.item(i)
        if isinstance(e, adsk.fusion.SketchLine):
            ln = e.length
            if ln > best_l:
                best, best_l = e, ln
    return best


def _tp(pt, dx=1.0, dy=1.0):
    return P3.create(pt.geometry.x + dx, pt.geometry.y + dy, 0)


def run(context):
    ctx = sp.DesignContext()
    design, root, params = ctx.design, ctx.root, ctx.params
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    ev = ctx.ev
    VI = adsk.core.ValueInput.createByString

    for n, e, u, c in USER_PARAMS + DERIVED_PARAMS:
        params.add(n, VI(e), u, c)

    # ---------------- Phase 1: Sides (legs + runners + ladder) ----------------
    sides_occ = sp.make_comp(root, "Sides")
    sides = sides_occ.component
    legmid = sp.off_plane(sides, sides.yZConstructionPlane, "runner_thick / 2",
                          "LegMid_Pl")

    # --- Left leg: leaning parallelogram profile, built in place ---
    sk = sides.sketches.add(legmid)
    sk.name = "Leg_Sk"
    m2s = sk.modelToSketchSpace
    rc = ev("runner_thick / 2")
    lr = ev("leg_run")
    ch = ev("chair_h")
    lt = ev("lean_t")
    a = math.radians(ev("leg_lean"))
    axis_len = ev("leg_len") - ev("leg_w") * math.tan(a)

    p1 = m2s(P3.create(rc, 0, 0))
    p2 = m2s(P3.create(rc, lr, 0))
    p3 = m2s(P3.create(rc, lr + math.sin(a) * axis_len, math.cos(a) * axis_len))
    p4 = m2s(P3.create(rc, ch * lt, ch))
    lines = sk.sketchCurves.sketchLines
    lb = lines.addByTwoPoints(P3.create(p1.x, p1.y, 0), P3.create(p2.x, p2.y, 0))
    lrear = lines.addByTwoPoints(lb.endSketchPoint, P3.create(p3.x, p3.y, 0))
    ltop = lines.addByTwoPoints(lrear.endSketchPoint, P3.create(p4.x, p4.y, 0))
    lfront = lines.addByTwoPoints(ltop.endSketchPoint, lb.startSketchPoint)

    gc = sk.geometricConstraints
    gc.addCoincident(lb.startSketchPoint, sk.originPoint)
    orient = sp.probe_orientations(sk, rc, 5.0, 5.0)
    if orient['y'] == HOR:
        gc.addHorizontal(lb)
    else:
        gc.addVertical(lb)
    gc.addParallel(lrear, lfront)
    gc.addPerpendicular(ltop, lfront)
    d = sk.sketchDimensions
    d.addDistanceDimension(lb.startSketchPoint, lb.endSketchPoint, orient['y'],
                           _tp(lb.endSketchPoint)).parameter.expression = "leg_run"
    d.addDistanceDimension(sk.originPoint, lfront.startSketchPoint, orient['y'],
                           _tp(lfront.startSketchPoint, 2, 0)
                           ).parameter.expression = "chair_h * lean_t"
    d.addDistanceDimension(sk.originPoint, lfront.startSketchPoint, orient['z'],
                           _tp(lfront.startSketchPoint, 0, 2)
                           ).parameter.expression = "chair_h"
    leg_f = sp.ext_new_sym(sides, sk.profiles.item(0), "leg_thick / 2", "LegBoard")
    leg = leg_f.bodies.item(0)
    leg.name = "Leg_Left"

    # --- Left runner: main body behind the leg + through-tenon in one sketch ---
    f_front = sp.find_face(leg, 'y', -1)
    f_rear = sp.find_face(leg, 'y', +1)
    f_bot = sp.find_face(leg, 'z', -1)
    sk2 = sides.sketches.add(legmid)
    sk2.name = "Runner_Sk"
    ln_bot = _line(sk2.project(f_bot))
    ln_front = _line(sk2.project(f_front))
    ln_rear = _line(sk2.project(f_rear))
    m2 = sk2.modelToSketchSpace
    rh = ev("runner_h")
    rl = ev("runner_len")

    A = m2(P3.create(rc, lr, 0))
    B = m2(P3.create(rc, rl, 0))
    C = m2(P3.create(rc, rl, rh))
    D = m2(P3.create(rc, lr + rh * lt, rh))
    lines2 = sk2.sketchCurves.sketchLines
    Lb = lines2.addByTwoPoints(P3.create(A.x, A.y, 0), P3.create(B.x, B.y, 0))
    Lv = lines2.addByTwoPoints(Lb.endSketchPoint, P3.create(C.x, C.y, 0))
    Lt = lines2.addByTwoPoints(Lv.endSketchPoint, P3.create(D.x, D.y, 0))
    Ls = lines2.addByTwoPoints(Lt.endSketchPoint, Lb.startSketchPoint)

    gc2 = sk2.geometricConstraints
    orient2 = sp.probe_orientations(sk2, rc, 10.0, 1.0)
    gc2.addCollinear(Lb, ln_bot)
    gc2.addCollinear(Ls, ln_rear)
    if orient2['z'] == HOR:
        gc2.addHorizontal(Lv)
    else:
        gc2.addVertical(Lv)
    if orient2['y'] == HOR:
        gc2.addHorizontal(Lt)
    else:
        gc2.addVertical(Lt)
    d2 = sk2.sketchDimensions
    d2.addDistanceDimension(sk2.originPoint, Lb.endSketchPoint, orient2['y'],
                            _tp(Lb.endSketchPoint)).parameter.expression = "runner_len"
    d2.addDistanceDimension(Lb.endSketchPoint, Lv.endSketchPoint, orient2['z'],
                            _tp(Lv.endSketchPoint)).parameter.expression = "runner_h"

    # Tenon strip: parallelogram from the leg's front edge back to the shoulder
    tz0 = ev("run_ten_z0")
    tz1 = tz0 + ev("run_ten_h")
    E = m2(P3.create(rc, tz0 * lt, tz0))
    F = m2(P3.create(rc, lr + tz0 * lt, tz0))
    G = m2(P3.create(rc, tz1 * lt, tz1))
    H = m2(P3.create(rc, lr + tz1 * lt, tz1))
    tb = lines2.addByTwoPoints(P3.create(E.x, E.y, 0), P3.create(F.x, F.y, 0))
    tt = lines2.addByTwoPoints(P3.create(G.x, G.y, 0), P3.create(H.x, H.y, 0))
    tf = lines2.addByTwoPoints(tb.startSketchPoint, tt.startSketchPoint)
    if orient2['y'] == HOR:
        gc2.addHorizontal(tb)
        gc2.addHorizontal(tt)
    else:
        gc2.addVertical(tb)
        gc2.addVertical(tt)
    gc2.addCoincident(tb.startSketchPoint, ln_front)
    gc2.addCoincident(tt.startSketchPoint, ln_front)
    gc2.addCoincident(tb.endSketchPoint, Ls)
    gc2.addCoincident(tt.endSketchPoint, Ls)
    d2.addDistanceDimension(sk2.originPoint, tb.startSketchPoint, orient2['z'],
                            _tp(tb.startSketchPoint, -2, 0)
                            ).parameter.expression = "run_ten_z0"
    d2.addDistanceDimension(sk2.originPoint, tt.startSketchPoint, orient2['z'],
                            _tp(tt.startSketchPoint, -2, 1)
                            ).parameter.expression = "run_ten_z0 + run_ten_h"

    sp.refs_to_construction(sk2)
    profs = sorted((sk2.profiles.item(i) for i in range(sk2.profiles.count)),
                   key=lambda p: p.areaProperties().area)
    if len(profs) != 2:
        print(f"ERROR: Runner_Sk expected 2 profiles, got {len(profs)}")
    prof_ten, prof_run = profs[0], profs[-1]
    run_f = sp.ext_new_sym(sides, prof_run, "runner_thick / 2", "RunnerBoard")
    runner = run_f.bodies.item(0)
    runner.name = "Runner_Left"
    ten_f = sp.ext_new_sym(sides, prof_ten, "run_ten_t / 2", "RunnerTenon")
    tenon = ten_f.bodies.item(0)

    res = sp.validate_joint_strength(tenon, leg, 'y', species="hardwood",
                                     through=True)
    print(f"runner tenon strength: ok={res.get('ok')} flags={res.get('flags')}")
    sp.combine(leg, tenon, CUT, True, "RunMort_Cut")
    sp.combine(runner, tenon, JOIN, False, "RunTen_Join")

    # --- Ladder: one slot tool, Z-pattern, bulk CUT into the left leg ---
    inner = sp.find_face(leg, 'x', +1)
    sk3, prof3 = sp.sketch_rect_model(
        sides, inner, ("leg_in_x", "slot_y0", "ladder_z0"),
        {"y": "slot_ylen", "z": "panel_thick"}, "Slot_Sk", ev=ev)
    # Face sketches auto-project the face boundary as solid lines, which
    # fragment the rect into multiple profiles — demote them and re-grab.
    sp.refs_to_construction(sk3)
    if sk3.profiles.count != 1:
        print(f"WARNING: Slot_Sk has {sk3.profiles.count} profiles, expected 1")
    prof3 = sk3.profiles.item(0)
    n0 = sides.bRepBodies.count
    tool_f = sp.ext_op(sides, prof3, "groove_d", NEW, None, "SlotTool", flip=True)
    sp.body_pattern(sides, tool_f.bodies.item(0), sides.zConstructionAxis,
                    "n_slots", "slot_pitch", "Ladder_Pat")
    tools = [sides.bRepBodies.item(i)
             for i in range(n0, sides.bRepBodies.count)]
    sp.combine(leg, tools, CUT, False, "Ladder_Cut")

    # --- Mirror the finished left side to the right ---
    xmid = sp.off_plane(root, root.yZConstructionPlane, "outer_w / 2", "XMid_Pl")
    n1 = sides.bRepBodies.count
    sp.mirror_bodies(sides, [leg, runner], xmid, "Side_Mirror")
    for i in range(n1, sides.bRepBodies.count):
        b = sides.bRepBodies.item(i)
        b.name = "Leg_Right" if "Leg" in b.name else "Runner_Right"

    # ---------------- Phase 2: Panels (seat + footrest in the ladder) --------
    panels_occ = sp.make_comp(root, "Panels")
    panels = panels_occ.component

    seat_pl = sp.off_plane(panels, panels.xYConstructionPlane, "seat_z", "Seat_Pl")
    skS, profS = sp.sketch_rect_model(
        panels, seat_pl, ("panel_x0", "seat_y1 - seat_d", "seat_z"),
        {"x": "panel_w", "y": "seat_d"}, "Seat_Sk", ev=ev,
        anchor=dict(parent_body=leg, parent_occ=sides_occ,
                    face_axis="x", face_dir=-1,
                    anchor_xyz=("leg_x0", "leg_run", "0 in"),
                    off1=("x", "panel_x0 - leg_x0"),
                    off2=("y", "abs(seat_y1 - seat_d - leg_run)")))
    seat_f = sp.ext_new(panels, profS, "panel_thick", "SeatBoard")
    seat = seat_f.bodies.item(0)
    seat.name = "Seat"

    foot_pl = sp.off_plane(panels, panels.xYConstructionPlane, "foot_z", "Foot_Pl")
    skF, profF = sp.sketch_rect_model(
        panels, foot_pl, ("panel_x0", "foot_y1 - foot_d", "foot_z"),
        {"x": "panel_w", "y": "foot_d"}, "Foot_Sk", ev=ev,
        anchor=dict(parent_body=leg, parent_occ=sides_occ,
                    face_axis="x", face_dir=-1,
                    anchor_xyz=("leg_x0", "leg_run", "0 in"),
                    off1=("x", "panel_x0 - leg_x0"),
                    off2=("y", "abs(foot_y1 - foot_d - leg_run)")))
    foot_f = sp.ext_new(panels, profF, "panel_thick", "FootBoard")
    foot = foot_f.bodies.item(0)
    foot.name = "Footrest"

    # ---------------- Phase 3: Back (2 curved rails, lean-axis pattern) ------
    back_occ = sp.make_comp(root, "Back")
    back = back_occ.component
    legL_proxy = leg.createForAssemblyContext(sides_occ)
    legR = ctx.find_body("Leg_Right")
    legR_proxy = legR.createForAssemblyContext(sides_occ)

    # Lean reference: projected leg front face line -> pattern direction
    sk_lean, _ = sp.sketch_on_plane(
        back, back.yZConstructionPlane,
        project=[sp.find_face(legL_proxy, 'y', -1)], name="LeanRef_Sk")
    lean_line = _line(sk_lean.sketchCurves.sketchLines)

    # Rail band: concentric arc pair between the legs' inner faces
    rail1_pl = sp.off_plane(back, back.xYConstructionPlane, "rail1_z", "Rail1_Pl")
    skR = back.sketches.add(rail1_pl)
    skR.name = "Rail_Sk"
    fL = sp.find_face(legL_proxy, 'x', -1)
    fR = sp.find_face(legR_proxy, 'x', +1)
    skR.project(fL)
    skR.project(fR)
    sp.refs_to_construction(skR)
    aL = sp.anchor_pt(skR, ev("leg_x0"), ev("leg_run"), 0)
    aR = sp.anchor_pt(skR, ev("outer_w - leg_x0"), ev("leg_run"), 0)
    m2r = skR.modelToSketchSpace
    x_in_l = ev("leg_in_x")
    x_in_r = ev("outer_w - leg_in_x")
    yc_v = ev("rail1_yc")
    sag = ev("rail_sag")
    rz = ev("rail1_z")
    xc = ev("outer_w / 2")
    Rv = ev("rail_R")
    x_ov = ev("0.05 in")

    arcs = skR.sketchCurves.sketchArcs

    def s2(x, y):
        p = m2r(P3.create(x, y, rz))
        return P3.create(p.x, p.y, 0)

    # Centerline arc, thin-extruded to rail_thick (Center wall) — the 0.05 in
    # end overlap into each leg is trimmed flush by a leg CUT below.
    # Pin 3 standalone points first (drawn exactly at target, so the solver
    # moves nothing), then snap the arc to them — no rigid-arc branch flips.
    gcR = skR.geometricConstraints
    orR = sp.probe_orientations(skR, xc, yc_v, rz)
    dR = skR.sketchDimensions

    def pin_pt(x, y, anchor, ex, ey):
        p = skR.sketchPoints.add(s2(x, y))
        sp.rdim(skR, dR, anchor, p, orR, 'x', ex)
        sp.rdim(skR, dR, anchor, p, orR, 'y', ey)
        return p

    # Draw the arc at the rail CENTERLINE. The thin-extrude wall side is not
    # stable across rebuilds (it follows the arc's internal orientation), so
    # after extruding, measure which way the wall grew and parametrically
    # shift the pinned-point dims to re-center the band on the centerline.
    ptS = pin_pt(x_in_l - x_ov, yc_v, aL, "leg_thick - 0.05 in",
                 "abs(rail1_yc - leg_run)")
    ptM = pin_pt(xc, yc_v + sag, aL, "outer_w / 2 - leg_x0",
                 "abs(rail1_yc + rail_sag - leg_run)")
    ptE = pin_pt(x_in_r + x_ov, yc_v, aR, "leg_thick - 0.05 in",
                 "abs(rail1_yc - leg_run)")
    arcF = arcs.addByThreePoints(ptS, s2(xc, yc_v + sag), ptE)
    gcR.addCoincident(ptM, arcF)
    if not skR.isFullyConstrained:
        print("WARNING: Rail_Sk not fully constrained")
    open_prof = back.createOpenProfile(arcF, False)
    ext_in = back.features.extrudeFeatures.createInput(open_prof, NEW)
    ext_in.setThinExtrude(adsk.fusion.ThinExtrudeWallLocation.Center,
                          VI("rail_thick"))
    ext_in.setDistanceExtent(False, VI("rail_h"))
    band_f = back.features.extrudeFeatures.add(ext_in)
    band_f.name = "RailBand"
    band = band_f.bodies.item(0)

    ymax = band.boundingBox.maxPoint.y
    shift = None
    if abs(ymax - ev("rail1_yc + rail_sag + rail_thick / 2")) < 0.1:
        pass  # wall centered on the arc — as intended
    elif abs(ymax - ev("rail1_yc + rail_sag + rail_thick")) < 0.1:
        shift = "- rail_thick / 2"  # wall grew rearward — pull arc forward
    elif abs(ymax - ev("rail1_yc + rail_sag")) < 0.1:
        shift = "+ rail_thick / 2"  # wall grew forward — push arc rearward
    else:
        print(f"WARNING: unexpected band ymax {ymax:.2f}")
    if shift:
        for idx, base_expr in ((1, "rail1_yc"), (3, "rail1_yc + rail_sag"),
                               (5, "rail1_yc")):
            dim = dR.item(idx)
            if "rail1_yc" not in dim.parameter.expression:
                print(f"WARNING: Rail_Sk dim {idx} unexpected: "
                      f"{dim.parameter.expression}")
            dim.parameter.expression = f"abs({base_expr} {shift} - leg_run)"
        print(f"band wall one-sided; arc dims shifted {shift}")

    # Tenon tabs (left built, right mirrored), then pattern all 3 down the lean
    ten_pl = sp.off_plane(back, back.xYConstructionPlane,
                          "rail1_z + (rail_h - rt_tw) / 2", "RailTen_Pl")
    skT, profT = sp.sketch_rect_model(
        back, ten_pl,
        ("leg_in_x - rt_td", "rail1_yc - rt_tt / 2",
         "rail1_z + (rail_h - rt_tw) / 2"),
        {"x": "rt_td + 0.2 in", "y": "rt_tt"}, "RailTenL_Sk", ev=ev,
        anchor=dict(parent_body=leg, parent_occ=sides_occ,
                    face_axis="x", face_dir=-1,
                    anchor_xyz=("leg_x0", "leg_run", "0 in"),
                    off1=("x", "leg_thick - rt_td"),
                    off2=("y", "abs(rail1_yc - rt_tt / 2 - leg_run)")))
    tenL_f = sp.ext_new(back, profT, "rt_tw", "RailTenL")
    tenL = tenL_f.bodies.item(0)
    tenR = sp.mirror_body(back, tenL, xmid, "RailTenR_Mirror").bodies.item(0)

    nb0 = back.bRepBodies.count
    coll = adsk.core.ObjectCollection.create()
    for b in (band, tenL, tenR):
        coll.add(b)
    pat_in = back.features.rectangularPatternFeatures.createInput(
        coll, lean_line, VI("2"), VI("(rail_h + rail_gap) / lean_c"),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    pat_in.quantityTwo = VI("1")
    pat = back.features.rectangularPatternFeatures.add(pat_in)
    pat.name = "Rail_Pat"
    new_rail = [back.bRepBodies.item(i) for i in range(nb0, back.bRepBodies.count)]
    if new_rail and new_rail[0].boundingBox.minPoint.z > band.boundingBox.minPoint.z:
        pat.distanceOne.expression = "-(rail_h + rail_gap) / lean_c"
    band2 = max(new_rail, key=lambda b: b.volume)
    tens2 = sorted([b for b in new_rail if b is not band2],
                   key=lambda b: b.boundingBox.minPoint.x)
    band.name = "Rail_Top"
    band2.name = "Rail_Low"

    res = sp.validate_joint_strength(tenL, leg, 'x', species="hardwood")
    print(f"rail tenon strength: ok={res.get('ok')} flags={res.get('flags')}")
    sp.combine(leg, tenL, CUT, True, "RailMortTL_Cut")
    sp.combine(legR, tenR, CUT, True, "RailMortTR_Cut")
    sp.combine(leg, tens2[0], CUT, True, "RailMortLL_Cut")
    sp.combine(legR, tens2[1], CUT, True, "RailMortLR_Cut")
    sp.combine(band, [leg, legR], CUT, True, "RailTop_Trim")
    sp.combine(band2, [leg, legR], CUT, True, "RailLow_Trim")
    sp.combine(band, [tenL, tenR], JOIN, False, "RailTop_Join")
    sp.combine(band2, tens2, JOIN, False, "RailLow_Join")

    # ---------------- Phase 4: Base (stretcher) + Hardware (tie rods) --------
    base_occ = sp.make_comp(root, "Base")
    base = base_occ.component
    str_pl = sp.off_plane(base, base.xYConstructionPlane, "str_z0", "Str_Pl")
    skStr, profStr = sp.sketch_rect_model(
        base, str_pl,
        ("runner_thick", "runner_len - str_setback - str_thick", "str_z0"),
        {"x": "outer_w - 2 * runner_thick", "y": "str_thick"}, "Str_Sk", ev=ev,
        anchor=dict(parent_body=runner, parent_occ=sides_occ,
                    face_axis="x", face_dir=-1,
                    anchor_xyz=("0 in", "runner_len", "0 in"),
                    off1=("x", "runner_thick"),
                    off2=("y", "str_setback + str_thick")))
    str_f = sp.ext_new(base, profStr, "str_h", "StretcherBoard")
    stretcher = str_f.bodies.item(0)
    stretcher.name = "Stretcher"

    stz_pl = sp.off_plane(base, base.xYConstructionPlane, "st_tz0", "StrTen_Pl")
    skSt, profSt = sp.sketch_rect_model(
        base, stz_pl,
        ("runner_thick - st_td",
         "runner_len - str_setback - (str_thick + st_tt) / 2", "st_tz0"),
        {"x": "st_td + 0.2 in", "y": "st_tt"}, "StrTenL_Sk", ev=ev,
        anchor=dict(parent_body=runner, parent_occ=sides_occ,
                    face_axis="x", face_dir=-1,
                    anchor_xyz=("0 in", "runner_len", "0 in"),
                    off1=("x", "runner_thick - st_td"),
                    off2=("y", "str_setback + (str_thick + st_tt) / 2")))
    stenL_f = sp.ext_new(base, profSt, "st_tw", "StrTenL")
    stenL = stenL_f.bodies.item(0)
    stenR = sp.mirror_body(base, stenL, xmid, "StrTenR_Mirror").bodies.item(0)

    runnerR = ctx.find_body("Runner_Right")
    res = sp.validate_joint_strength(stenL, runner, 'x', species="hardwood")
    print(f"stretcher tenon strength: ok={res.get('ok')} flags={res.get('flags')}")
    sp.combine(runner, stenL, CUT, True, "StrMortL_Cut")
    sp.combine(runnerR, stenR, CUT, True, "StrMortR_Cut")
    sp.combine(stretcher, [stenL, stenR], JOIN, False, "StrTen_Join")

    hw_occ = sp.make_comp(root, "Hardware")
    hw = hw_occ.component
    sk_lean2, _ = sp.sketch_on_plane(
        hw, hw.yZConstructionPlane,
        project=[sp.find_face(legL_proxy, 'y', -1)], name="LeanRefHw_Sk")
    lean_line2 = _line(sk_lean2.sketchCurves.sketchLines)

    rod_pl = sp.off_plane(hw, hw.yZConstructionPlane, "leg_x0", "Rod_Pl")
    outerL = sp.find_face(legL_proxy, 'x', -1)
    skRod, anchors = sp.sketch_on_plane(
        hw, rod_pl, project=[outerL],
        identify={"c": P3.create(ev("leg_x0"), ev("leg_run"), 0)},
        name="Rod_Sk")
    aRod = anchors["c"]
    m2h = skRod.modelToSketchSpace
    rod_c = m2h(P3.create(ev("leg_x0"),
                          ev("seat_z * lean_t + leg_run / 2"),
                          ev("seat_z - rod_z_off")))
    circ = skRod.sketchCurves.sketchCircles.addByCenterRadius(
        P3.create(rod_c.x, rod_c.y, 0), ev("rod_dia / 2"))
    orH = sp.probe_orientations(skRod, ev("leg_x0"), 10.0, 10.0)
    dH = skRod.sketchDimensions
    dH.addRadialDimension(circ, _tp(circ.centerSketchPoint, 1, 1)
                          ).parameter.expression = "rod_dia / 2"
    sp.rdim(skRod, dH, aRod, circ.centerSketchPoint, orH, 'y',
            "abs(seat_z * lean_t - leg_run / 2)")
    sp.rdim(skRod, dH, aRod, circ.centerSketchPoint, orH, 'z',
            "seat_z - rod_z_off")
    if not skRod.isFullyConstrained:
        print("WARNING: Rod_Sk not fully constrained")
    rod_prof = sp.smallest_profile(skRod)
    nrm = rod_pl.geometry.normal
    rod_f = sp.ext_op(hw, rod_prof, "outer_w - runner_thick + leg_thick",
                      NEW, None, "RodSeat", flip=(nrm.x < 0))
    rod1 = rod_f.bodies.item(0)
    rod1.name = "Rod_Seat"

    nh1 = hw.bRepBodies.count
    coll2 = adsk.core.ObjectCollection.create()
    coll2.add(rod1)
    pat2_in = hw.features.rectangularPatternFeatures.createInput(
        coll2, lean_line2, VI("2"),
        VI("(seat_slot - foot_slot) * slot_pitch / lean_c"),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    pat2_in.quantityTwo = VI("1")
    pat2 = hw.features.rectangularPatternFeatures.add(pat2_in)
    pat2.name = "Rod_Pat"
    rod2 = hw.bRepBodies.item(nh1)
    if rod2.boundingBox.minPoint.z > rod1.boundingBox.minPoint.z:
        pat2.distanceOne.expression = \
            "-(seat_slot - foot_slot) * slot_pitch / lean_c"
    rod2.name = "Rod_Foot"

    sp.combine(leg, [rod1, rod2], CUT, True, "RodHolesL_Cut")
    sp.combine(legR, [rod1, rod2], CUT, True, "RodHolesR_Cut")

    # ---------------- Phase 5: Details (roundovers, chamfers) ----------------
    def _dir_edges(face, axis):
        out = adsk.core.ObjectCollection.create()
        for i in range(face.edges.count):
            e = face.edges.item(i)
            g = e.geometry
            if isinstance(g, adsk.core.Line3D):
                v = g.startPoint.vectorTo(g.endPoint)
                v.normalize()
                if abs(getattr(v, axis)) > 0.9:
                    out.add(e)
            elif axis == 'arc' and isinstance(g, (adsk.core.Arc3D,
                                                  adsk.core.Circle3D)):
                out.add(e)
        return out

    def _arc_edges(face, out=None):
        out = out or adsk.core.ObjectCollection.create()
        for i in range(face.edges.count):
            e = face.edges.item(i)
            if not isinstance(e.geometry, adsk.core.Line3D):
                out.add(e)
        return out

    def _fillet(comp, edges, rexpr, name):
        if edges.count == 0:
            print(f"WARNING: no edges for fillet {name}")
            return
        fi = comp.features.filletFeatures.createInput()
        fi.addConstantRadiusEdgeSet(edges, VI(rexpr), False)
        f = comp.features.filletFeatures.add(fi)
        f.name = name

    def _chamfer(comp, edges, dexpr, name):
        if edges.count == 0:
            print(f"WARNING: no edges for chamfer {name}")
            return
        ci = comp.features.chamferFeatures.createInput2()
        ci.chamferEdgeSets.addEqualDistanceChamferEdgeSet(edges, VI(dexpr),
                                                          False)
        c = comp.features.chamferFeatures.add(ci)
        c.name = name

    for pbody, tag in ((seat, "Seat"), (foot, "Foot")):
        front = sp.find_face(pbody, 'y', -1)
        _fillet(panels, _dir_edges(front, 'z'), "0.5 in", f"{tag}Corner_Fil")
        front = sp.find_face(pbody, 'y', -1)
        _fillet(panels, _dir_edges(front, 'x'), "0.2 in", f"{tag}Edge_Fil")

    for lbody, lcomp, tag in ((leg, sides, "LegL"), (legR, sides, "LegR")):
        top = sp.find_face(lbody, 'z', +1)
        edges = adsk.core.ObjectCollection.create()
        for i in range(top.edges.count):
            edges.add(top.edges.item(i))
        _chamfer(lcomp, edges, "0.1 in", f"{tag}Top_Ch")

    rail_edges = adsk.core.ObjectCollection.create()
    for rbody in (band, band2):
        zmin = rbody.boundingBox.minPoint.z
        zmax = rbody.boundingBox.maxPoint.z
        for i in range(rbody.edges.count):
            e = rbody.edges.item(i)
            if isinstance(e.geometry, adsk.core.Line3D):
                continue
            eb = e.boundingBox
            flat = abs(eb.maxPoint.z - eb.minPoint.z) < 0.01
            at_ext = (abs(eb.minPoint.z - zmin) < 0.01
                      or abs(eb.maxPoint.z - zmax) < 0.01)
            if flat and at_ext:
                rail_edges.add(e)
    _fillet(back, rail_edges, "0.08 in", "RailEdge_Fil")

    _chamfer(base, _dir_edges(sp.find_face(stretcher, 'z', +1), 'x'),
             "0.15 in", "StrTop_Ch")

    for comp in (sides, panels, back, base, hw):
        for b in [comp.bRepBodies.item(i) for i in range(comp.bRepBodies.count)]:
            bb = b.boundingBox
            print(f"{b.name}: vol={b.volume:.1f}cm3 "
                  f"x[{bb.minPoint.x:.2f},{bb.maxPoint.x:.2f}] "
                  f"y[{bb.minPoint.y:.2f},{bb.maxPoint.y:.2f}] "
                  f"z[{bb.minPoint.z:.2f},{bb.maxPoint.z:.2f}]")

    # ---------------- Appearance + fit view ----------------------------------
    sp.apply_appearance("cherry")
    def _find_app(coll, name):
        try:
            return coll.itemByName(name)
        except Exception:
            return None

    lib = None
    try:
        lib = ctx.app.materialLibraries.itemByName("Fusion Appearance Library")
    except Exception:
        pass
    black = None
    if lib:
        for nm in ("Powder Coat (Black)", "Paint - Enamel Glossy (Black)",
                   "Plastic - Matte (Black)", "Steel - Satin"):
            black = _find_app(lib.appearances, nm)
            if black:
                break
    if black:
        used = (_find_app(design.appearances, black.name)
                or design.appearances.addByCopy(black, black.name))
        for rb in (rod1, rod2):
            rb.appearance = used
        print(f"rods appearance: {used.name}")
    else:
        print("NOTE: no black appearance found for rods")

    cam = ctx.app.activeViewport.camera
    cam.isFitView = True
    ctx.app.activeViewport.camera = cam
