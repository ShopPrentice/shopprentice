"""Midou (米斗) — tapered through-dovetail box.

Square frustum shell: outer 30x30 top, 21x21 bottom, 17 cm tall.
Grain horizontal on all boards; pins/sockets run with the pin board's grain.

RECOMPUTE-SAFE construction (no SplitBody, no script-time fragment picks):
the horizontal Y/X directions lie inside the shoulder planes, the face
planes, and the box-corner planes, so every board and every dovetail is an
EXACT oblique sweep — its end faces land flush on the mating planes by
construction. Live parameter edits (top_w, bot_w, box_h, board_t, dt_pad,
dt_tail_w, dt_angle, panel_*) recompute cleanly.
"""
import math
import adsk.core
import adsk.fusion
from helpers import sp

VI = adsk.core.ValueInput.createByString
P3 = adsk.core.Point3D
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
ALIGNED = adsk.fusion.DimensionOrientations.AlignedDimensionOrientation


def run(context):
    ctx = sp.DesignContext()
    design, root = ctx.design, ctx.root
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    params = design.userParameters
    ev = ctx.ev

    def addp(n, e, u, c):
        if not params.itemByName(n):
            params.add(n, VI(e), u, c)

    # ---- user parameters ----
    addp("top_w", "30 cm", "cm", "Outer edge length at top rim")
    addp("bot_w", "21 cm", "cm", "Outer edge length at bottom")
    addp("box_h", "17 cm", "cm", "Vertical height")
    addp("board_t", "1.2 cm", "cm", "Board thickness perpendicular to face")
    addp("dt_count", "6", "", "Dovetail tails per corner")
    addp("dt_tail_w", "1.9 cm", "cm", "Tail base width along joint line")
    addp("dt_angle", "10 deg", "deg", "Dovetail flank angle")
    addp("dt_pad", "0.6 cm", "cm", "Edge padding beyond the half-pin at both joint ends")
    addp("panel_t", "0.8 cm", "cm", "Bottom panel thickness")
    addp("panel_z0", "1.0 cm", "cm", "Bottom panel underside height")
    addp("groove_d", "0.5 cm", "cm", "Panel housing depth into boards")

    # ---- derived parameters ----
    addp("tilt", "atan((top_w - bot_w) / 2 / box_h)", "deg", "Side tilt from vertical")
    addp("board_tw", "board_t / cos(tilt)", "cm", "Horizontal wall thickness")
    addp("joint_len", "sqrt(2 * ((top_w - bot_w) / 2) ^ 2 + box_h ^ 2)", "cm",
         "Corner joint line length")
    addp("dt_pitch", "(joint_len - 2 * dt_pad) / dt_count", "cm", "Tail pitch along joint line")
    addp("dt_pin_w", "dt_pitch - dt_tail_w", "cm", "Pin width along joint line")
    addp("dt_half_pin", "dt_pin_w / 2", "cm", "Half-pin at both joint ends")
    addp("dt_ju", "((top_w - bot_w) / 2) / joint_len", "",
         "Joint line dir dot grain dir (in-face)")
    addp("dt_jv", "sqrt(1 - dt_ju ^ 2)", "", "Joint line dir dot in-face up dir")
    addp("shoulder_ang", "90 deg - atan(dt_ju / dt_jv)", "deg",
         "In-face angle between joint line and horizontal grain")
    addp("dt_ang_lo", "shoulder_ang + dt_angle", "deg", "Lower flank angle to joint line")
    addp("dt_ang_hi", "shoulder_ang - dt_angle", "deg", "Upper flank angle to joint line")
    addp("panel_half", "bot_w / 2 - board_tw + (panel_z0 + panel_t) * tan(tilt) + groove_d",
         "cm", "Bottom panel tongue half width")
    addp("rabbet_half", "bot_w / 2 - board_tw + panel_z0 * tan(tilt)", "cm",
         "Panel rabbet (lower half) half width at its underside")
    addp("rabbet_off", "panel_z0 * tan(tilt)", "cm",
         "Rabbet underside offset from the boards' bottom inner edge")
    addp("panel_edge_off", "(panel_z0 + panel_t) * tan(tilt) + groove_d", "cm",
         "Panel tongue edge offset from the boards' bottom inner edge")

    th = params.itemByName("tilt").value  # radians
    tanT, cosT, sinT = math.tan(th), math.cos(th), math.sin(th)
    bw2, tw2, H = ev("bot_w") / 2, ev("top_w") / 2, ev("box_h")
    btw = ev("board_tw")
    jl = ev("joint_len")

    # ---- shared helpers ----
    def vadd(a, b, s=1.0):
        return (a[0] + s * b[0], a[1] + s * b[1], a[2] + s * b[2])

    def vnorm(a):
        ln = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)
        return (a[0] / ln, a[1] / ln, a[2] / ln)

    def tri_area(p, q, r):
        ux, uy, uz = q[0] - p[0], q[1] - p[1], q[2] - p[2]
        vx, vy, vz = r[0] - p[0], r[1] - p[1], r[2] - p[2]
        cx, cy, cz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)

    def hv_on(gcx, line):
        p1, p2 = line.startSketchPoint.geometry, line.endSketchPoint.geometry
        if abs(p2.x - p1.x) >= abs(p2.y - p1.y):
            gcx.addHorizontal(line)
        else:
            gcx.addVertical(line)

    um = design.unitsManager

    def set_ang(dim_obj, base_expr):
        """Assign an angular dim expression, using the supplement when the
        as-drawn measured angle is the supplementary one (projected reference
        lines can come back direction-reversed)."""
        v = dim_obj.parameter.value                      # as-drawn, radians
        base_v = um.evaluateExpression(base_expr, "rad")
        if abs(v - base_v) <= abs(v - (math.pi - base_v)):
            dim_obj.parameter.expression = base_expr
        else:
            dim_obj.parameter.expression = "180 deg - (%s)" % base_expr

    def feat_bodies(feat):
        return [feat.bodies.item(i) for i in range(feat.bodies.count)]

    def minus(bodies, exclude):
        ex = {b.entityToken for b in exclude}
        return [b for b in bodies if b.entityToken not in ex]

    def uniq(bodies):
        seen, out = set(), []
        for b in bodies:
            t = b.entityToken
            if t not in seen:
                seen.add(t)
                out.append(b)
        return out

    # in-face directions at the front-left corner (model space)
    dvec = (-(tw2 - bw2) / jl, -(tw2 - bw2) / jl, H / jl)   # joint/shoulder line, up
    dvec_r = ((tw2 - bw2) / jl, -(tw2 - bw2) / jl, H / jl)  # right-end joint line, up
    u_out = (-1.0, 0.0, 0.0)                                 # grain dir, outboard left
    vvec = (0.0, -sinT, cosT)                                # in-face up-slope dir

    # =====================================================================
    # PHASE A — Case: the Front board is its outer-face outline swept along
    # +Y by board_tw. End faces land EXACTLY on the side boards' inner
    # planes, top/bottom land on Z=0 / Z=box_h, and the far face lands on
    # the inner wall plane — all because Y lies in each of those planes.
    # Then a 4x circular pattern around Z makes the other three boards.
    # =====================================================================
    case_occ = sp.make_comp(root, "Case")
    case = case_occ.component

    # base sketch on XY: the box's bottom-front OUTER edge (rotation axis for
    # the angled face plane, anchor for the outline, and the +Y sweep path)
    base_sk = case.sketches.add(case.xYConstructionPlane)
    base_sk.name = "Base_Sk"
    m2sb = base_sk.modelToSketchSpace

    def b2(mx, my):
        p = m2sb(P3.create(mx, my, 0.0))
        return P3.create(p.x, p.y, 0)

    lnsb = base_sk.sketchCurves.sketchLines
    ax_line = lnsb.addByTwoPoints(b2(-bw2, -bw2), b2(bw2, -bw2))      # front edge
    path_line = lnsb.addByTwoPoints(b2(0.0, -bw2), b2(0.0, -bw2 + btw))
    ax2_line = lnsb.addByTwoPoints(b2(-bw2, -bw2), b2(-bw2, bw2))     # left edge
    path2_line = lnsb.addByTwoPoints(b2(-bw2, 0.0), b2(-bw2 + btw, 0.0))
    gcb = base_sk.geometricConstraints
    for ln_ in (ax_line, path_line, ax2_line, path2_line):
        hv_on(gcb, ln_)
    gcb.addCoincident(path_line.startSketchPoint, ax_line)
    gcb.addCoincident(path2_line.startSketchPoint, ax2_line)
    gcb.addCoincident(ax2_line.startSketchPoint, ax_line.startSketchPoint)
    orient_b = sp.probe_orientations(base_sk, 0.0, -bw2, 0.0)
    db = base_sk.sketchDimensions
    db.addDistanceDimension(base_sk.originPoint, ax_line.startSketchPoint, orient_b['x'],
                            b2(-bw2 + 1, -bw2 - 1)).parameter.expression = "bot_w / 2"
    db.addDistanceDimension(base_sk.originPoint, ax_line.startSketchPoint, orient_b['y'],
                            b2(-bw2 + 2, -bw2 - 2)).parameter.expression = "bot_w / 2"
    db.addDistanceDimension(ax_line.startSketchPoint, ax_line.endSketchPoint, orient_b['x'],
                            b2(0, -bw2 - 1.5)).parameter.expression = "bot_w"
    db.addDistanceDimension(ax_line.startSketchPoint, path_line.startSketchPoint, ALIGNED,
                            b2(-bw2 / 2, -bw2 + 0.5)).parameter.expression = "bot_w / 2"
    db.addDistanceDimension(path_line.startSketchPoint, path_line.endSketchPoint, orient_b['y'],
                            b2(0.5, -bw2 + btw / 2)).parameter.expression = "board_tw"
    db.addDistanceDimension(ax2_line.startSketchPoint, ax2_line.endSketchPoint, orient_b['y'],
                            b2(-bw2 - 1.5, 0)).parameter.expression = "bot_w"
    db.addDistanceDimension(ax2_line.startSketchPoint, path2_line.startSketchPoint, ALIGNED,
                            b2(-bw2 + 0.5, -bw2 / 2)).parameter.expression = "bot_w / 2"
    db.addDistanceDimension(path2_line.startSketchPoint, path2_line.endSketchPoint,
                            orient_b['x'],
                            b2(-bw2 + btw / 2, 0.5)).parameter.expression = "board_tw"
    if not base_sk.isFullyConstrained:
        raise RuntimeError("Base_Sk is not fully constrained")

    # angled construction plane = the Front board's OUTER face plane
    def make_front_plane(expr):
        pli = case.constructionPlanes.createInput()
        pli.setByAngle(ax_line, VI(expr), case.xYConstructionPlane)
        pl = case.constructionPlanes.add(pli)
        pl.name = "FrontFace_Pl"
        return pl

    def plane_misses_top(pl):
        g = pl.geometry
        n, o = g.normal, g.origin
        return abs(n.x * (0 - o.x) + n.y * (-tw2 - o.y) + n.z * (H - o.z)) > 0.01

    fr_pl = make_front_plane("90 deg - tilt")
    if plane_misses_top(fr_pl):
        fr_pl.deleteMe()
        fr_pl = make_front_plane("-(90 deg - tilt)")
        if plane_misses_top(fr_pl):
            raise RuntimeError("FrontFace_Pl does not contain the top outer edge")

    # outline sketch (outer face of Front), anchored to the projected axis
    sk = case.sketches.add(fr_pl)
    sk.name = "Front_Sk"
    m2s = sk.modelToSketchSpace
    ref_line = sk.project(ax_line).item(0)
    ra = sk.sketchToModelSpace(ref_line.startSketchPoint.geometry)
    rb_ = sk.sketchToModelSpace(ref_line.endSketchPoint.geometry)
    ref_l = ref_line.startSketchPoint if ra.x < rb_.x else ref_line.endSketchPoint
    ref_r = ref_line.endSketchPoint if ra.x < rb_.x else ref_line.startSketchPoint

    def s2(mpt):
        p = m2s(P3.create(mpt[0], mpt[1], mpt[2]))
        return P3.create(p.x, p.y, 0)

    obl = (-(bw2 - btw), -bw2, 0.0)
    obr = (bw2 - btw, -bw2, 0.0)
    otr = (tw2 - btw, -tw2, H)
    otl = (-(tw2 - btw), -tw2, H)
    lns = sk.sketchCurves.sketchLines
    o_bot = lns.addByTwoPoints(s2(obl), s2(obr))
    o_r = lns.addByTwoPoints(o_bot.endSketchPoint, s2(otr))
    o_top = lns.addByTwoPoints(o_r.endSketchPoint, s2(otl))
    o_l = lns.addByTwoPoints(o_top.endSketchPoint, o_bot.startSketchPoint)
    gc = sk.geometricConstraints
    gc.addCoincident(o_bot.startSketchPoint, ref_line)
    gc.addCoincident(o_bot.endSketchPoint, ref_line)
    hv_on(gc, o_top)
    d = sk.sketchDimensions
    d.addDistanceDimension(ref_l, o_bot.startSketchPoint, ALIGNED,
                           s2((-bw2 + btw / 2, -bw2, 0.3))
                           ).parameter.expression = "board_tw"
    d.addDistanceDimension(ref_r, o_bot.endSketchPoint, ALIGNED,
                           s2((bw2 - btw / 2, -bw2, 0.3))
                           ).parameter.expression = "board_tw"
    set_ang(d.addAngularDimension(ref_line, o_l,
                                  s2(vadd(vadd(obl, dvec, 0.8), (1, 0, 0), 0.8))),
            "shoulder_ang")
    set_ang(d.addAngularDimension(ref_line, o_r,
                                  s2(vadd(vadd(obr, dvec_r, 0.8), (-1, 0, 0), 0.8))),
            "shoulder_ang")
    d.addOffsetDimension(ref_line, o_top,
                         s2((0.0, -tw2, H - 0.3))
                         ).parameter.expression = "box_h / cos(tilt)"

    for pt_obj, mpt in ((o_bot.startSketchPoint, obl), (o_bot.endSketchPoint, obr),
                        (o_top.startSketchPoint, otr), (o_top.endSketchPoint, otl)):
        w = sk.sketchToModelSpace(pt_obj.geometry)
        drift = math.sqrt((w.x - mpt[0]) ** 2 + (w.y - mpt[1]) ** 2 + (w.z - mpt[2]) ** 2)
        if drift > 0.02:
            raise RuntimeError("Front_Sk corner drifted %.3f cm after constraints" % drift)
    if not sk.isFullyConstrained:
        raise RuntimeError("Front_Sk is not fully constrained")

    sp.refs_to_construction(sk)
    prof = sp.smallest_profile(sk)
    path0 = case.features.createPath(path_line, False)
    sw0_in = case.features.sweepFeatures.createInput(prof, path0, NEW)
    sw0_in.orientation = adsk.fusion.SweepOrientationTypes.ParallelOrientationType
    sw0 = case.features.sweepFeatures.add(sw0_in)
    sw0.name = "FrontBoard"
    front = sw0.bodies.item(0)
    front.name = "Front"

    exp_area = ((ev("bot_w") - 2 * btw) + (ev("top_w") - 2 * btw)) / 2 * (H / cosT)
    exp_vol_f = exp_area * ev("board_t")
    if abs(front.volume - exp_vol_f) > 0.02 * exp_vol_f:
        raise RuntimeError("Front sweep volume %.1f, expected %.1f"
                           % (front.volume, exp_vol_f))

    # ---- Back = mirror of Front across XZ ----
    mb = sp.mirror_body(case, front, case.xZConstructionPlane, "Back_Mir")
    back = minus(feat_bodies(mb), [front])[0]
    back.name = "Back"

    # ---- Left board: PIN board — spans the FULL outer width, its end
    # edges ARE the box corner lines, swept along +X by board_tw (its end
    # faces land exactly on the Front/Back OUTER planes, which contain X).
    def make_left_plane(expr):
        pli = case.constructionPlanes.createInput()
        pli.setByAngle(ax2_line, VI(expr), case.xYConstructionPlane)
        pl = case.constructionPlanes.add(pli)
        pl.name = "LeftFace_Pl"
        return pl

    def lplane_misses_top(pl):
        g = pl.geometry
        n, o = g.normal, g.origin
        return abs(n.x * (-tw2 - o.x) + n.y * (0 - o.y) + n.z * (H - o.z)) > 0.01

    lf_pl = make_left_plane("90 deg - tilt")
    if lplane_misses_top(lf_pl):
        lf_pl.deleteMe()
        lf_pl = make_left_plane("-(90 deg - tilt)")
        if lplane_misses_top(lf_pl):
            raise RuntimeError("LeftFace_Pl does not contain the top outer edge")

    sk_l = case.sketches.add(lf_pl)
    sk_l.name = "Left_Sk"
    m2sl = sk_l.modelToSketchSpace
    ref2 = sk_l.project(ax2_line).item(0)
    la = sk_l.sketchToModelSpace(ref2.startSketchPoint.geometry)
    lb = sk_l.sketchToModelSpace(ref2.endSketchPoint.geometry)
    ref2_f = ref2.startSketchPoint if la.y < lb.y else ref2.endSketchPoint
    ref2_b = ref2.endSketchPoint if la.y < lb.y else ref2.startSketchPoint

    def sl2(mpt):
        p = m2sl(P3.create(mpt[0], mpt[1], mpt[2]))
        return P3.create(p.x, p.y, 0)

    lbf = (-bw2, -bw2, 0.0)
    lbb = (-bw2, bw2, 0.0)
    ltb = (-tw2, tw2, H)
    ltf = (-tw2, -tw2, H)
    dvec_b = (-(tw2 - bw2) / jl, (tw2 - bw2) / jl, H / jl)  # back corner line, up
    lnsl = sk_l.sketchCurves.sketchLines
    l_bot = lnsl.addByTwoPoints(sl2(lbf), sl2(lbb))
    l_bend = lnsl.addByTwoPoints(l_bot.endSketchPoint, sl2(ltb))
    l_top = lnsl.addByTwoPoints(l_bend.endSketchPoint, sl2(ltf))
    l_fend = lnsl.addByTwoPoints(l_top.endSketchPoint, l_bot.startSketchPoint)
    gcl = sk_l.geometricConstraints
    gcl.addCoincident(l_bot.startSketchPoint, ref2_f)
    gcl.addCoincident(l_bot.endSketchPoint, ref2_b)
    hv_on(gcl, l_top)
    dl = sk_l.sketchDimensions
    set_ang(dl.addAngularDimension(ref2, l_fend,
                                   sl2(vadd(vadd(lbf, dvec, 0.8), (0, 1, 0), 0.8))),
            "shoulder_ang")
    set_ang(dl.addAngularDimension(ref2, l_bend,
                                   sl2(vadd(vadd(lbb, dvec_b, 0.8), (0, -1, 0), 0.8))),
            "shoulder_ang")
    dl.addOffsetDimension(ref2, l_top,
                          sl2((-tw2, 0.0, H - 0.3))
                          ).parameter.expression = "box_h / cos(tilt)"

    for pt_obj, mpt in ((l_bot.startSketchPoint, lbf), (l_bot.endSketchPoint, lbb),
                        (l_bend.endSketchPoint, ltb), (l_top.endSketchPoint, ltf)):
        w = sk_l.sketchToModelSpace(pt_obj.geometry)
        drift = math.sqrt((w.x - mpt[0]) ** 2 + (w.y - mpt[1]) ** 2 + (w.z - mpt[2]) ** 2)
        if drift > 0.02:
            raise RuntimeError("Left_Sk corner drifted %.3f cm after constraints" % drift)
    if not sk_l.isFullyConstrained:
        raise RuntimeError("Left_Sk is not fully constrained")

    sp.refs_to_construction(sk_l)
    prof_l = sp.smallest_profile(sk_l)
    path2 = case.features.createPath(path2_line, False)
    swl_in = case.features.sweepFeatures.createInput(prof_l, path2, NEW)
    swl_in.orientation = adsk.fusion.SweepOrientationTypes.ParallelOrientationType
    swl = case.features.sweepFeatures.add(swl_in)
    swl.name = "LeftBoard"
    left = swl.bodies.item(0)
    left.name = "Left"

    exp_vol_l = (ev("bot_w") + ev("top_w")) / 2 * (H / cosT) * ev("board_t")
    if abs(left.volume - exp_vol_l) > 0.02 * exp_vol_l:
        raise RuntimeError("Left sweep volume %.1f, expected %.1f"
                           % (left.volume, exp_vol_l))

    # ---- Right = mirror of Left across YZ ----
    mr = sp.mirror_body(case, left, case.yZConstructionPlane, "Right_Mir")
    right = minus(feat_bodies(mr), [left])[0]
    right.name = "Right"

    print("PHASE A OK — 4 boards swept exact (no trims), body count = %d"
          % case.bRepBodies.count)

    # =====================================================================
    # PHASE B — Dovetails. One fan trapezoid on the front outer-face plane:
    # base ON the projected slanted shoulder edge (unequal flank lengths),
    # tip corners ON the projected box-corner edge — so the tail, swept
    # along the pin board's grain (+Y), is flush with the side board's
    # outer face by construction. Pattern along the shoulder edge, mirror
    # to the other corners, CUT sockets, JOIN tails.
    # =====================================================================
    front = ctx.find_body("Front")
    back = ctx.find_body("Back")
    left = ctx.find_body("Left")
    right = ctx.find_body("Right")
    aa = params.itemByName("dt_angle").value                 # radians

    P0 = (-(bw2 - btw), -bw2, 0.0)                           # shoulder line bottom
    hp, twd, pad = ev("dt_half_pin"), ev("dt_tail_w"), ev("dt_pad")
    f_lo = vadd((math.cos(aa) * u_out[0], math.cos(aa) * u_out[1], math.cos(aa) * u_out[2]),
                vvec, -math.sin(aa))
    f_hi = vadd((math.cos(aa) * u_out[0], math.cos(aa) * u_out[1], math.cos(aa) * u_out[2]),
                vvec, math.sin(aa))
    B_lo = vadd(P0, dvec, pad + hp)
    B_hi = vadd(P0, dvec, pad + hp + twd)
    # tip corners: intersect the flank rays with the box corner line
    # (Left-outer plane: x + z*tanT = -bw2)
    t_lo = -btw / (f_lo[0] + f_lo[2] * tanT)
    t_hi = -btw / (f_hi[0] + f_hi[2] * tanT)
    if t_lo <= 0 or t_hi <= 0:
        raise RuntimeError("flank/corner intersection signs wrong")
    T_lo = vadd(B_lo, f_lo, t_lo)
    T_hi = vadd(B_hi, f_hi, t_hi)

    # The fan sketch anchors ONLY to projected base-sketch geometry (never
    # modified by later cuts) — referencing body edges here would make the
    # tail pattern recompute when the boards get cut, spawning ghost bodies.
    sk2 = case.sketches.add(fr_pl)
    sk2.name = "DT_FL_Sk"
    m2s2 = sk2.modelToSketchSpace

    proj_ax = sk2.project(ax_line).item(0)
    xa = sk2.sketchToModelSpace(proj_ax.startSketchPoint.geometry)
    xb = sk2.sketchToModelSpace(proj_ax.endSketchPoint.geometry)
    ax_l = proj_ax.startSketchPoint if xa.x < xb.x else proj_ax.endSketchPoint

    def sp2d(mpt):
        p = m2s2(P3.create(mpt[0], mpt[1], mpt[2]))
        return P3.create(p.x, p.y, 0)

    lns2 = sk2.sketchCurves.sketchLines
    Q0 = (-bw2, -bw2, 0.0)                       # bottom box corner
    # construction references: the shoulder line and the box corner line
    shoulder_ref = lns2.addByTwoPoints(sp2d(P0), sp2d(vadd(P0, dvec, jl)))
    corner_ref = lns2.addByTwoPoints(sp2d(Q0), sp2d(vadd(Q0, dvec, jl)))
    shoulder_ref.isConstruction = True
    corner_ref.isConstruction = True
    gc2 = sk2.geometricConstraints
    gc2.addCoincident(shoulder_ref.startSketchPoint, proj_ax)
    gc2.addCoincident(corner_ref.startSketchPoint, ax_l)
    d2 = sk2.sketchDimensions
    d2.addDistanceDimension(ax_l, shoulder_ref.startSketchPoint, ALIGNED,
                            sp2d(vadd(Q0, (1, 0, 0), btw / 2))
                            ).parameter.expression = "board_tw"
    d2.addDistanceDimension(shoulder_ref.startSketchPoint, shoulder_ref.endSketchPoint,
                            ALIGNED, sp2d(vadd(P0, dvec, jl / 2))
                            ).parameter.expression = "joint_len"
    d2.addDistanceDimension(corner_ref.startSketchPoint, corner_ref.endSketchPoint,
                            ALIGNED, sp2d(vadd(Q0, dvec, jl / 2))
                            ).parameter.expression = "joint_len"
    set_ang(d2.addAngularDimension(proj_ax, shoulder_ref,
                                   sp2d(vadd(vadd(P0, dvec, 0.8), (1, 0, 0), 0.8))),
            "shoulder_ang")
    set_ang(d2.addAngularDimension(proj_ax, corner_ref,
                                   sp2d(vadd(vadd(Q0, dvec, 1.2), (1, 0, 0), 1.4))),
            "shoulder_ang")
    bot_pt = shoulder_ref.startSketchPoint

    base = lns2.addByTwoPoints(sp2d(B_lo), sp2d(B_hi))
    flank_hi = lns2.addByTwoPoints(base.endSketchPoint, sp2d(T_hi))
    cap = lns2.addByTwoPoints(flank_hi.endSketchPoint, sp2d(T_lo))
    flank_lo = lns2.addByTwoPoints(cap.endSketchPoint, base.startSketchPoint)

    gc2.addCoincident(base.startSketchPoint, shoulder_ref)
    gc2.addCoincident(base.endSketchPoint, shoulder_ref)
    gc2.addCoincident(flank_hi.endSketchPoint, corner_ref)
    gc2.addCoincident(cap.endSketchPoint, corner_ref)

    d2.addDistanceDimension(bot_pt, base.startSketchPoint, ALIGNED,
                            sp2d(vadd(vadd(P0, dvec, (pad + hp) / 2), u_out, 0.6))
                            ).parameter.expression = "dt_pad + dt_half_pin"
    d2.addDistanceDimension(base.startSketchPoint, base.endSketchPoint, ALIGNED,
                            sp2d(vadd(vadd(P0, dvec, pad + hp + twd / 2), u_out, -0.6))
                            ).parameter.expression = "dt_tail_w"
    set_ang(d2.addAngularDimension(shoulder_ref, flank_lo,
                                   sp2d(vadd(B_lo, vnorm(vadd(dvec, f_lo)), 0.7))),
            "dt_ang_lo")
    set_ang(d2.addAngularDimension(shoulder_ref, flank_hi,
                                   sp2d(vadd(B_hi, vnorm(vadd(dvec, f_hi)), 0.7))),
            "dt_ang_hi")

    # self-checks: solver must be a no-op and the sketch fully constrained
    for pt_obj, mpt in ((base.startSketchPoint, B_lo), (base.endSketchPoint, B_hi),
                        (cap.endSketchPoint, T_lo), (flank_hi.endSketchPoint, T_hi)):
        w = sk2.sketchToModelSpace(pt_obj.geometry)
        drift = math.sqrt((w.x - mpt[0]) ** 2 + (w.y - mpt[1]) ** 2 + (w.z - mpt[2]) ** 2)
        if drift > 0.02:
            raise RuntimeError("DT_FL_Sk vertex drifted %.3f cm after constraints" % drift)
    if not sk2.isFullyConstrained:
        raise RuntimeError("DT_FL_Sk is not fully constrained")

    sp.refs_to_construction(sk2)
    prof2 = sp.smallest_profile(sk2)

    # sweep along the pin board's grain (+Y) — flush at both wall planes
    path_t = case.features.createPath(path_line, False)
    sw_in = case.features.sweepFeatures.createInput(prof2, path_t, NEW)
    sw_in.orientation = adsk.fusion.SweepOrientationTypes.ParallelOrientationType
    swf = case.features.sweepFeatures.add(sw_in)
    swf.name = "DT_FL_Tail"
    tail0 = swf.bodies.item(0)
    tail0.name = "DT_Tail_FL_0"

    fan_area = tri_area(B_lo, B_hi, T_hi) + tri_area(B_lo, T_hi, T_lo)
    exp_vol = fan_area * ev("board_t")
    if abs(tail0.volume - exp_vol) > 0.02 * exp_vol:
        raise RuntimeError("tail sweep volume %.2f, expected %.2f"
                           % (tail0.volume, exp_vol))

    # pattern along the slanted shoulder reference line (sketch entity —
    # stable under later cuts, unlike a body edge)
    # NOTE: pattern/mirror feature.bodies INCLUDES the input bodies — dedupe
    # by entityToken to isolate the actual copies.
    n_dt = int(round(ev("dt_count")))
    sa_ = sk2.sketchToModelSpace(shoulder_ref.startSketchPoint.geometry)
    sb_ = sk2.sketchToModelSpace(shoulder_ref.endSketchPoint.geometry)
    spacing = "dt_pitch" if (sb_.z - sa_.z) > 0 else "-dt_pitch"
    pf = sp.body_pattern(case, tail0, shoulder_ref, "dt_count", spacing, "DT_FL_Pat")
    fl_tails = uniq([tail0] + feat_bodies(pf))
    if len(fl_tails) != n_dt:
        raise RuntimeError("expected %d FL tails, got %d" % (n_dt, len(fl_tails)))

    # mirror to the other three corners (bodies only)
    m1 = sp.mirror_bodies(case, fl_tails, case.yZConstructionPlane, "DT_FR_Mir")
    fr_tails = minus(uniq(feat_bodies(m1)), fl_tails)
    m2f = sp.mirror_bodies(case, fl_tails + fr_tails, case.xZConstructionPlane, "DT_B_Mir")
    bk_tails = minus(uniq(feat_bodies(m2f)), fl_tails + fr_tails)
    if len(fr_tails) != n_dt or len(bk_tails) != 2 * n_dt:
        raise RuntimeError("tail counts wrong: FR=%d back=%d" % (len(fr_tails), len(bk_tails)))

    bkl = [b for b in bk_tails if b.physicalProperties.centerOfMass.x < 0]
    bkr = [b for b in bk_tails if b.physicalProperties.centerOfMass.x > 0]
    if len(bkl) != n_dt or len(bkr) != n_dt:
        raise RuntimeError("back tail split wrong: %d/%d" % (len(bkl), len(bkr)))

    # sockets: tails CUT the pin boards (pins emerge between sockets)
    sp.combine(left, fl_tails + bkl, CUT, True, "DT_L_Cut")
    sp.combine(right, fr_tails + bkr, CUT, True, "DT_R_Cut")
    left.name, right.name = "Left", "Right"

    # tails JOIN their boards
    sp.combine(front, fl_tails + fr_tails, JOIN, False, "DT_F_Join")
    sp.combine(back, bk_tails, JOIN, False, "DT_B_Join")
    front.name, back.name = "Front", "Back"
    # tails butt the shoulder plane exactly (coplanar) — verify the join fused
    if front.lumps.count != 1 or back.lumps.count != 1:
        raise RuntimeError("tail JOIN left disconnected lumps (F=%d, B=%d)"
                           % (front.lumps.count, back.lumps.count))
    if case.bRepBodies.count != 4:
        raise RuntimeError("expected 4 case bodies after joins, got %d (ghosts?): %s"
                           % (case.bRepBodies.count,
                              [case.bRepBodies.item(i).name
                               for i in range(case.bRepBodies.count)]))

    print("PHASE B OK — dovetails done (flush by construction), body count = %d"
          % case.bRepBodies.count)

    # =====================================================================
    # PHASE C — Bottom panel: full-size tongue (upper half) enters the wall
    # grooves; lower half is taper-extruded at `tilt` so the rabbet shoulder
    # mates flush against the tilted inner walls. The panel CUTs its own
    # exact-fit housing into all four boards.
    # =====================================================================
    bottom_occ = sp.make_comp(root, "Bottom")
    bottom = bottom_occ.component

    # anchor: project Front & Left BOTTOM faces (proxies; stable whole faces)
    front = ctx.find_body("Front")
    fr_btm = sp.find_face(front.createForAssemblyContext(case_occ), "z", -1)
    lf_btm = sp.find_face(ctx.find_body("Left").createForAssemblyContext(case_occ), "z", -1)
    inner = -(bw2 - btw)

    def proj_inner_line(ents, axis):
        for i in range(ents.count):
            e = ents.item(i)
            if not isinstance(e, adsk.fusion.SketchLine):
                continue
            wa, wb = e.worldGeometry.startPoint, e.worldGeometry.endPoint
            va = wa.y if axis == "y" else wa.x
            vb = wb.y if axis == "y" else wb.x
            if abs(va - inner) < 0.01 and abs(vb - inner) < 0.01:
                return e
        raise RuntimeError("projected inner edge (%s) not found" % axis)

    def anchored_square(plane, zc, half_expr, off_expr, name):
        """Centered square profile anchored to projected bottom inner edges."""
        skx = bottom.sketches.add(plane)
        skx.name = name
        m2sx = skx.modelToSketchSpace
        fl = proj_inner_line(skx.project(fr_btm), "y")
        ll = proj_inner_line(skx.project(lf_btm), "x")
        hf = ev(half_expr)

        def sx(mx, my):
            p = m2sx(P3.create(mx, my, zc))
            return P3.create(p.x, p.y, 0)

        lx = skx.sketchCurves.sketchLines
        q_f = lx.addByTwoPoints(sx(-hf, -hf), sx(hf, -hf))
        q_r = lx.addByTwoPoints(q_f.endSketchPoint, sx(hf, hf))
        q_b = lx.addByTwoPoints(q_r.endSketchPoint, sx(-hf, hf))
        q_l = lx.addByTwoPoints(q_b.endSketchPoint, q_f.startSketchPoint)
        gcx = skx.geometricConstraints
        for ln_ in (q_f, q_r, q_b, q_l):
            hv_on(gcx, ln_)
        orx = sp.probe_orientations(skx, 0.0, 0.0, zc)
        dx = skx.sketchDimensions
        dx.addDistanceDimension(q_f.startSketchPoint, q_f.endSketchPoint, orx['x'],
                                sx(0, -hf - 1)
                                ).parameter.expression = "2 * (%s)" % half_expr
        dx.addDistanceDimension(q_f.startSketchPoint, q_b.startSketchPoint, orx['y'],
                                sx(hf + 1, 0)
                                ).parameter.expression = "2 * (%s)" % half_expr
        dx.addOffsetDimension(fl, q_f, sx(0, -hf + 0.4)
                              ).parameter.expression = off_expr
        dx.addOffsetDimension(ll, q_l, sx(-hf + 0.4, 0)
                              ).parameter.expression = off_expr
        w = skx.sketchToModelSpace(q_f.startSketchPoint.geometry)
        if math.sqrt((w.x + hf) ** 2 + (w.y + hf) ** 2) > 0.02:
            raise RuntimeError("%s corner drifted after constraints" % name)
        if not skx.isFullyConstrained:
            raise RuntimeError("%s is not fully constrained" % name)
        sp.refs_to_construction(skx)
        return sp.smallest_profile(skx)

    z0, pt_ = ev("panel_z0"), ev("panel_t")

    # tongue: upper half of the panel — full size, enters the wall grooves
    ton_pl = sp.off_plane(bottom, bottom.xYConstructionPlane,
                          "panel_z0 + panel_t / 2", "Tongue_Pl")
    prof_t = anchored_square(ton_pl, z0 + pt_ / 2, "panel_half",
                             "panel_edge_off", "Tongue_Sk")
    ext_t = sp.ext_new(bottom, prof_t, "panel_t / 2", "PanelTongue")
    panel = ext_t.bodies.item(0)
    panel.name = "Panel"
    if abs(panel.boundingBox.maxPoint.z - (z0 + pt_)) > 0.02:
        raise RuntimeError("tongue extrude direction wrong")

    # rabbet: lower half, taper-extruded at `tilt` so its shoulder faces are
    # coplanar with (and mate flush against) the tilted inner walls
    pan_pl = sp.off_plane(bottom, bottom.xYConstructionPlane, "panel_z0", "Panel_Pl")
    prof_r = anchored_square(pan_pl, z0, "rabbet_half", "rabbet_off", "Rabbet_Sk")

    def taper_extrude(sign):
        einp = bottom.features.extrudeFeatures.createInput(prof_r, NEW)
        dd = adsk.fusion.DistanceExtentDefinition.create(VI("panel_t / 2"))
        einp.setOneSideExtent(dd, adsk.fusion.ExtentDirections.PositiveExtentDirection,
                              VI(sign + "tilt"))
        return bottom.features.extrudeFeatures.add(einp)

    exp_top = ev("rabbet_half") + (pt_ / 2) * tanT
    ext_r = taper_extrude("")
    rb = ext_r.bodies.item(0)
    if abs(rb.boundingBox.maxPoint.z - (z0 + pt_ / 2)) > 0.02:
        raise RuntimeError("rabbet extrude direction wrong")
    if abs(rb.boundingBox.maxPoint.x - exp_top) > 0.02:
        ext_r.deleteMe()
        ext_r = taper_extrude("-")
        rb = ext_r.bodies.item(0)
        if abs(rb.boundingBox.maxPoint.x - exp_top) > 0.02:
            raise RuntimeError("rabbet taper sign wrong: top half-width %.3f vs %.3f"
                               % (rb.boundingBox.maxPoint.x, exp_top))
    ext_r.name = "PanelRabbet"

    sp.combine(panel, [rb], JOIN, False, "Panel_Join")
    panel.name = "Panel"
    if panel.lumps.count != 1:
        raise RuntimeError("panel join produced %d lumps" % panel.lumps.count)

    # groove cuts: panel CUTs its housing into all four boards (root, proxies)
    panel_proxy = panel.createForAssemblyContext(bottom_occ)
    for nm in ("Front", "Back", "Left", "Right"):
        b = ctx.find_body(nm)
        b_proxy = b.createForAssemblyContext(case_occ)
        sp.combine(b_proxy, [panel_proxy], CUT, True, "PanelGroove_%s" % nm)
        b.name = nm

    # ---- diagnostics ----
    names = ("Front", "Back", "Left", "Right", "Panel")
    for name in names:
        b = ctx.find_body(name)
        bb = b.boundingBox
        print("%s vol=%.1f cm3  x[%.2f,%.2f] y[%.2f,%.2f] z[%.2f,%.2f]" % (
            name, b.volume,
            bb.minPoint.x, bb.maxPoint.x,
            bb.minPoint.y, bb.maxPoint.y,
            bb.minPoint.z, bb.maxPoint.z))
    print("PHASE C OK — panel housed, total bodies = %d"
          % (case.bRepBodies.count + bottom.bRepBodies.count))
