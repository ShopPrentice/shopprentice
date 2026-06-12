"""Splayed (compound-angle) through-dovetail template.

Through dovetails for boxes whose sides lean outward — rice measures
(米斗), splayed trays, knife boxes. Every corner interface is tilted:
tail baselines follow the slanted shoulder line (so each tail's two
flanks have different lengths), pins run horizontally with the pin
board's grain, and the whole joint recomputes under live parameter
edits (top/bottom width, height, thickness, tail width, pad, angle).

Scope (v1 — tested end-to-end on examples/midou-box): a SQUARE frustum
with equal splay on all four sides, centered on the origin, sitting on
Z=0. Front/Back are the TAIL boards (grain ±X), Left/Right the PIN
boards (grain ±Y). Rectangular plans and unequal splays are future work.

Why this construction is recompute-safe
---------------------------------------
The horizontal X/Y directions lie INSIDE every mating plane of the
splayed box: the shoulder planes (side-board inner faces), the board
face planes, and the box-corner planes. Three consequences:

1. **Every board is one exact oblique sweep** of its outer-face outline
   along a horizontal path — its end faces land flush on the mating
   planes by construction. Zero SplitBody trims (script-time fragment
   classification does NOT survive recompute — see midou-box README).
   Tail and pin boards are DIFFERENT shapes (tail boards end at the
   shoulder planes; pin boards span the full outer width to the box
   corner lines), so a circular pattern of one board is wrong: this
   template sweeps two boards and mirrors them.
2. **The tail is one fan trapezoid swept along the pin board's grain.**
   Base corners sit on the slanted shoulder reference, tip corners on
   the box-corner reference, so the swept tail is flush with both wall
   planes — pins emerge grain-parallel from the socket CUT.
3. **A body pattern along the slanted shoulder line** replicates the
   tail: translation along the interface line maps every mating plane
   onto itself, so every copy lands correctly.

Known limits: changing ``{prefix}_tail_count`` needs a script re-run
(mirror features capture a fixed body set). All other parameters edit
live in Change Parameters.

Usage:
    from woodworking.templates import splayed_dovetail as sdt

    cfg = sdt.define_params(
        design.userParameters, prefix="sdt",
        top_w_expr="top_w", bot_w_expr="bot_w",
        height_expr="box_h", thick_expr="board_t",
        angle="10 deg", tail_w="1.9 cm", tail_count="6", pad="0.6 cm")

    frame = sdt.frame(case, cfg, ev=ctx.ev)
    bodies = sdt.boards(case, cfg, frame, ev=ctx.ev)
    feats = sdt.corners(case, cfg, frame,
                        bodies["Front"], bodies["Back"],
                        bodies["Left"], bodies["Right"], ev=ctx.ev)
"""

import math

import adsk.core
import adsk.fusion

from helpers import sp

Point3D = adsk.core.Point3D
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
ALIGNED = adsk.fusion.DimensionOrientations.AlignedDimensionOrientation

METADATA = {
    "name": "splayed_dovetail",
    "category": "joinery",
    "variants": {
        "through": {
            "description": "Compound-angle through dovetails on a splayed "
                           "square box (frustum)",
            "best_for": ["rice measures (米斗)", "splayed trays",
                         "knife boxes", "wash-tub style boxes"],
            "not_for": ["rectangular plans (v1 is square-only)",
                        "unequal per-side splay"],
        },
    },
    "params": {
        "{p}_angle": "Dovetail flank angle (7-14 deg)",
        "{p}_tail_w": "Tail base width MEASURED ALONG THE SLANTED JOINT LINE",
        "{p}_tail_count": "Tails per corner (re-run script after changing)",
        "{p}_pad": "Edge padding beyond the half-pin at both joint ends",
        "{p}_tilt": "Derived (or caller-provided): side lean from vertical",
        "{p}_thick_h": "Derived: horizontal wall thickness thick/cos(tilt)",
        "{p}_joint_len": "Derived: 3D length of the slanted corner joint line",
        "{p}_pitch": "Derived: (joint_len - 2*pad) / tail_count",
        "{p}_pin_w": "Derived: pitch - tail_w (along the joint line)",
        "{p}_shoulder_ang": "Derived: in-face angle, joint line to grain",
    },
}


# ── small vector / sketch helpers ────────────────────────────────────

def _vadd(a, b, s=1.0):
    return (a[0] + s * b[0], a[1] + s * b[1], a[2] + s * b[2])


def _vnorm(a):
    ln = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)
    return (a[0] / ln, a[1] / ln, a[2] / ln)


def _tri_area(p, q, r):
    ux, uy, uz = q[0] - p[0], q[1] - p[1], q[2] - p[2]
    vx, vy, vz = r[0] - p[0], r[1] - p[1], r[2] - p[2]
    cx, cy, cz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)


def _hv_on(gc, line):
    """H or V constraint chosen from the line's SKETCH-space delta."""
    p1, p2 = line.startSketchPoint.geometry, line.endSketchPoint.geometry
    if abs(p2.x - p1.x) >= abs(p2.y - p1.y):
        gc.addHorizontal(line)
    else:
        gc.addVertical(line)


def _set_ang(dim_obj, base_expr):
    """Assign an angular dim expression, using the supplement when the
    as-drawn measured angle is the supplementary one.

    Projected reference lines can come back direction-reversed, in which
    case Fusion measures 180° - intended; assigning the intended
    expression would then ROTATE the geometry (a 9 cm drift in testing).
    """
    app = adsk.core.Application.get()
    um = app.activeProduct.unitsManager
    v = dim_obj.parameter.value                       # as-drawn, radians
    base_v = um.evaluateExpression(base_expr, "rad")
    if abs(v - base_v) <= abs(v - (math.pi - base_v)):
        dim_obj.parameter.expression = base_expr
    else:
        dim_obj.parameter.expression = "180 deg - (%s)" % base_expr


def _feat_bodies(feat):
    return [feat.bodies.item(i) for i in range(feat.bodies.count)]


def _minus(bodies, exclude):
    ex = {b.entityToken for b in exclude}
    return [b for b in bodies if b.entityToken not in ex]


def _uniq(bodies):
    seen, out = set(), []
    for b in bodies:
        t = b.entityToken
        if t not in seen:
            seen.add(t)
            out.append(b)
    return out


def _addp(params, name, expr, unit, comment):
    if not params.itemByName(name):
        VI = adsk.core.ValueInput.createByString
        params.add(name, VI(expr), unit, comment)


# ── Public API ───────────────────────────────────────────────────────

def define_params(params, prefix="sdt",
                  top_w_expr="top_w", bot_w_expr="bot_w",
                  height_expr="box_h", thick_expr="board_t",
                  angle="10 deg", tail_w="1.9 cm", tail_count="6",
                  pad="0.6 cm", tilt_expr=None, thick_h_expr=None,
                  unit="cm"):
    """Define all splayed-dovetail parameters with derivations.

    ``tail_w``, ``pitch`` and ``pin_w`` are measured ALONG the slanted
    3D joint line (length ``{p}_joint_len``), not vertically — that is
    how a maker lays the joint out on the splayed end of the board.

    Args:
        params: design.userParameters.
        prefix: Parameter name prefix.
        top_w_expr / bot_w_expr: Outer edge length at rim / foot.
        height_expr: Vertical box height.
        thick_expr: Board thickness perpendicular to the face.
        angle, tail_w, tail_count, pad: Joint layout (see dovetail.py for
            proportion guidance; pad keeps the end tails clear of the
            board ends).
        tilt_expr: Existing tilt parameter name, or None to create
            ``{p}_tilt = atan((top - bot) / 2 / height)``.
        thick_h_expr: Existing horizontal-wall-thickness parameter name,
            or None to create ``{p}_thick_h = thick / cos(tilt)``.
        unit: Display unit for created length params.

    Returns:
        cfg dict consumed by frame() / boards() / corners().
    """
    p = prefix
    half_spread = f"(({top_w_expr}) - ({bot_w_expr})) / 2"

    if tilt_expr is None:
        tilt_expr = f"{p}_tilt"
        _addp(params, tilt_expr, f"atan({half_spread} / ({height_expr}))",
              "deg", "Side lean from vertical (derived)")
    if thick_h_expr is None:
        thick_h_expr = f"{p}_thick_h"
        _addp(params, thick_h_expr, f"({thick_expr}) / cos({tilt_expr})",
              unit, "Horizontal wall thickness (derived)")

    _addp(params, f"{p}_angle", angle, "deg", "Dovetail flank angle")
    _addp(params, f"{p}_tail_w", tail_w, unit,
          "Tail base width along the slanted joint line")
    _addp(params, f"{p}_tail_count", tail_count, "",
          "Tails per corner (re-run script after changing)")
    _addp(params, f"{p}_pad", pad, unit,
          "Edge padding beyond the half-pin at both joint ends")
    _addp(params, f"{p}_joint_len",
          f"sqrt(2 * ({half_spread}) ^ 2 + ({height_expr}) ^ 2)", unit,
          "Corner joint line length (derived)")
    _addp(params, f"{p}_pitch",
          f"({p}_joint_len - 2 * {p}_pad) / {p}_tail_count", unit,
          "Tail pitch along the joint line (derived)")
    _addp(params, f"{p}_pin_w", f"{p}_pitch - {p}_tail_w", unit,
          "Pin width along the joint line (derived)")
    _addp(params, f"{p}_half_pin", f"{p}_pin_w / 2", unit,
          "Half-pin at both joint ends (derived)")
    _addp(params, f"{p}_ju", f"({half_spread}) / {p}_joint_len", "",
          "Joint line dir . grain dir, in-face (derived)")
    _addp(params, f"{p}_jv", f"sqrt(1 - {p}_ju ^ 2)", "",
          "Joint line dir . in-face up dir (derived)")
    _addp(params, f"{p}_shoulder_ang", f"90 deg - atan({p}_ju / {p}_jv)",
          "deg", "In-face angle between joint line and grain (derived)")
    _addp(params, f"{p}_ang_lo", f"{p}_shoulder_ang + {p}_angle", "deg",
          "Lower flank angle to joint line (derived)")
    _addp(params, f"{p}_ang_hi", f"{p}_shoulder_ang - {p}_angle", "deg",
          "Upper flank angle to joint line (derived)")

    return {
        "prefix": p,
        "top_w": top_w_expr, "bot_w": bot_w_expr,
        "height": height_expr, "thick": thick_expr,
        "tilt": tilt_expr, "thick_h": thick_h_expr,
    }


def frame(comp, cfg, ev, name="SDT"):
    """Base sketch + angled face planes — the stable skeleton.

    Builds one XY base sketch holding the box's bottom-front and
    bottom-left OUTER edges (the rotation axes for the two angled face
    planes) plus the two horizontal sweep paths, and the two angled
    construction planes coincident with the Front/Left outer faces.

    Everything downstream (board outlines, the dovetail fan, the sweep
    paths, the pattern direction) anchors to THIS sketch — never to body
    edges. A pattern template whose sketch references an edge of a body
    that later gets CUT recomputes mid-timeline and replays its history,
    spawning ghost bodies.

    Returns:
        dict: base_sk, ax_front, ax_left, path_y, path_x,
              front_pl, left_pl.
    """
    p = cfg["prefix"]
    bw2 = ev(cfg["bot_w"]) / 2
    tw2 = ev(cfg["top_w"]) / 2
    H = ev(cfg["height"])
    btw = ev(cfg["thick_h"])
    VI = adsk.core.ValueInput.createByString

    base_sk = comp.sketches.add(comp.xYConstructionPlane)
    base_sk.name = f"{name}_Base_Sk"
    m2sb = base_sk.modelToSketchSpace

    def b2(mx, my):
        pt = m2sb(Point3D.create(mx, my, 0.0))
        return Point3D.create(pt.x, pt.y, 0)

    lnsb = base_sk.sketchCurves.sketchLines
    ax_front = lnsb.addByTwoPoints(b2(-bw2, -bw2), b2(bw2, -bw2))
    path_y = lnsb.addByTwoPoints(b2(0.0, -bw2), b2(0.0, -bw2 + btw))
    ax_left = lnsb.addByTwoPoints(b2(-bw2, -bw2), b2(-bw2, bw2))
    path_x = lnsb.addByTwoPoints(b2(-bw2, 0.0), b2(-bw2 + btw, 0.0))
    gcb = base_sk.geometricConstraints
    for ln in (ax_front, path_y, ax_left, path_x):
        _hv_on(gcb, ln)
    gcb.addCoincident(path_y.startSketchPoint, ax_front)
    gcb.addCoincident(path_x.startSketchPoint, ax_left)
    gcb.addCoincident(ax_left.startSketchPoint, ax_front.startSketchPoint)

    orient_b = sp.probe_orientations(base_sk, 0.0, -bw2, 0.0)
    db = base_sk.sketchDimensions
    bw2_expr = f"({cfg['bot_w']}) / 2"
    db.addDistanceDimension(base_sk.originPoint, ax_front.startSketchPoint,
                            orient_b['x'], b2(-bw2 + 1, -bw2 - 1)
                            ).parameter.expression = bw2_expr
    db.addDistanceDimension(base_sk.originPoint, ax_front.startSketchPoint,
                            orient_b['y'], b2(-bw2 + 2, -bw2 - 2)
                            ).parameter.expression = bw2_expr
    db.addDistanceDimension(ax_front.startSketchPoint, ax_front.endSketchPoint,
                            orient_b['x'], b2(0, -bw2 - 1.5)
                            ).parameter.expression = cfg["bot_w"]
    db.addDistanceDimension(ax_front.startSketchPoint, path_y.startSketchPoint,
                            ALIGNED, b2(-bw2 / 2, -bw2 + 0.5)
                            ).parameter.expression = bw2_expr
    db.addDistanceDimension(path_y.startSketchPoint, path_y.endSketchPoint,
                            orient_b['y'], b2(0.5, -bw2 + btw / 2)
                            ).parameter.expression = cfg["thick_h"]
    db.addDistanceDimension(ax_left.startSketchPoint, ax_left.endSketchPoint,
                            orient_b['y'], b2(-bw2 - 1.5, 0)
                            ).parameter.expression = cfg["bot_w"]
    db.addDistanceDimension(ax_left.startSketchPoint, path_x.startSketchPoint,
                            ALIGNED, b2(-bw2 + 0.5, -bw2 / 2)
                            ).parameter.expression = bw2_expr
    db.addDistanceDimension(path_x.startSketchPoint, path_x.endSketchPoint,
                            orient_b['x'], b2(-bw2 + btw / 2, 0.5)
                            ).parameter.expression = cfg["thick_h"]
    if not base_sk.isFullyConstrained:
        raise RuntimeError(f"{name}_Base_Sk is not fully constrained")

    # angled face planes (sign of setByAngle is convention-dependent —
    # build, probe whether the plane contains the top outer edge, flip)
    ang_expr = f"90 deg - ({cfg['tilt']})"

    def _angled_plane(axis_line, probe_pt, pl_name):
        def make(expr):
            pli = comp.constructionPlanes.createInput()
            pli.setByAngle(axis_line, VI(expr), comp.xYConstructionPlane)
            pl = comp.constructionPlanes.add(pli)
            pl.name = pl_name
            return pl

        def misses(pl):
            g = pl.geometry
            n, o = g.normal, g.origin
            return abs(n.x * (probe_pt[0] - o.x) + n.y * (probe_pt[1] - o.y)
                       + n.z * (probe_pt[2] - o.z)) > 0.01

        pl = make(ang_expr)
        if misses(pl):
            pl.deleteMe()
            pl = make(f"-({ang_expr})")
            if misses(pl):
                raise RuntimeError(f"{pl_name} missed its top outer edge")
        return pl

    front_pl = _angled_plane(ax_front, (0.0, -tw2, H), f"{name}_FrontFace_Pl")
    left_pl = _angled_plane(ax_left, (-tw2, 0.0, H), f"{name}_LeftFace_Pl")

    return {
        "base_sk": base_sk, "ax_front": ax_front, "ax_left": ax_left,
        "path_y": path_y, "path_x": path_x,
        "front_pl": front_pl, "left_pl": left_pl,
    }


def boards(comp, cfg, frame_d, ev, name="SDT",
           names=("Front", "Back", "Left", "Right")):
    """The four splayed boards as exact oblique sweeps + mirrors.

    Front/Back (tail boards): outer-face outline between the SHOULDER
    lines, swept along +Y by thick_h — ends land on the side boards'
    inner planes. Left/Right (pin boards): outline spanning the FULL
    outer width (end edges = box corner lines), swept along +X — ends
    land on the Front/Back outer planes. No trims anywhere.

    Returns:
        dict name → BRepBody (keys from ``names``).
    """
    p = cfg["prefix"]
    bw2 = ev(cfg["bot_w"]) / 2
    tw2 = ev(cfg["top_w"]) / 2
    H = ev(cfg["height"])
    btw = ev(cfg["thick_h"])
    th = ev(cfg["tilt"])
    cosT = math.cos(th)
    jl = ev(f"{p}_joint_len")
    sh = tw2 - bw2
    dvec = (-sh / jl, -sh / jl, H / jl)
    dvec_r = (sh / jl, -sh / jl, H / jl)
    dvec_b = (-sh / jl, sh / jl, H / jl)
    slant_expr = f"({cfg['height']}) / cos({cfg['tilt']})"

    def _sweep_outline(plane, axis_line, corners, end_texts,
                       inset_exprs, path_line, sk_name, feat_name,
                       exp_vol):
        """Outline anchored to the projected axis line, swept along path."""
        sk = comp.sketches.add(plane)
        sk.name = sk_name
        m2s = sk.modelToSketchSpace
        ref = sk.project(axis_line).item(0)
        ra = sk.sketchToModelSpace(ref.startSketchPoint.geometry)
        rb = sk.sketchToModelSpace(ref.endSketchPoint.geometry)

        def s2(mpt):
            pt = m2s(Point3D.create(mpt[0], mpt[1], mpt[2]))
            return Point3D.create(pt.x, pt.y, 0)

        c_bl, c_br, c_tr, c_tl = corners
        lns = sk.sketchCurves.sketchLines
        o_bot = lns.addByTwoPoints(s2(c_bl), s2(c_br))
        o_r = lns.addByTwoPoints(o_bot.endSketchPoint, s2(c_tr))
        o_top = lns.addByTwoPoints(o_r.endSketchPoint, s2(c_tl))
        o_l = lns.addByTwoPoints(o_top.endSketchPoint, o_bot.startSketchPoint)
        gc = sk.geometricConstraints
        _hv_on(gc, o_top)
        d = sk.sketchDimensions

        # identify projected endpoints nearest each drawn bottom corner
        def _nearest_end(c):
            da = (ra.x - c[0]) ** 2 + (ra.y - c[1]) ** 2 + (ra.z - c[2]) ** 2
            db_ = (rb.x - c[0]) ** 2 + (rb.y - c[1]) ** 2 + (rb.z - c[2]) ** 2
            return (ref.startSketchPoint if da <= db_
                    else ref.endSketchPoint)

        for corner_pt, sk_pt, ins in (
                (c_bl, o_bot.startSketchPoint, inset_exprs[0]),
                (c_br, o_bot.endSketchPoint, inset_exprs[1])):
            end_pt = _nearest_end(corner_pt)
            if ins is None:
                gc.addCoincident(sk_pt, end_pt)       # exactly at the corner
            else:
                gc.addCoincident(sk_pt, ref)          # on the line, inset
                d.addDistanceDimension(end_pt, sk_pt, ALIGNED,
                                       s2(_vadd(corner_pt, (0, 0, 1), 0.3))
                                       ).parameter.expression = ins
        _set_ang(d.addAngularDimension(ref, o_l, s2(end_texts[0])),
                 f"{p}_shoulder_ang")
        _set_ang(d.addAngularDimension(ref, o_r, s2(end_texts[1])),
                 f"{p}_shoulder_ang")
        d.addOffsetDimension(ref, o_top, s2(end_texts[2])
                             ).parameter.expression = slant_expr

        for pt_obj, mpt in ((o_bot.startSketchPoint, c_bl),
                            (o_bot.endSketchPoint, c_br),
                            (o_r.endSketchPoint, c_tr),
                            (o_top.endSketchPoint, c_tl)):
            w = sk.sketchToModelSpace(pt_obj.geometry)
            drift = math.sqrt((w.x - mpt[0]) ** 2 + (w.y - mpt[1]) ** 2
                              + (w.z - mpt[2]) ** 2)
            if drift > 0.02:
                raise RuntimeError(
                    f"{sk_name} corner drifted {drift:.3f} cm")
        if not sk.isFullyConstrained:
            raise RuntimeError(f"{sk_name} is not fully constrained")

        sp.refs_to_construction(sk)
        prof = sp.smallest_profile(sk)
        path = comp.features.createPath(path_line, False)
        sw_in = comp.features.sweepFeatures.createInput(prof, path, NEW)
        sw_in.orientation = \
            adsk.fusion.SweepOrientationTypes.ParallelOrientationType
        sw = comp.features.sweepFeatures.add(sw_in)
        sw.name = feat_name
        body = sw.bodies.item(0)
        if abs(body.volume - exp_vol) > 0.02 * exp_vol:
            raise RuntimeError(
                f"{feat_name} volume {body.volume:.1f}, expected "
                f"{exp_vol:.1f}")
        return body

    # Front (TAIL board): outline between the shoulder lines
    front = _sweep_outline(
        frame_d["front_pl"], frame_d["ax_front"],
        corners=((-(bw2 - btw), -bw2, 0.0), (bw2 - btw, -bw2, 0.0),
                 (tw2 - btw, -tw2, H), (-(tw2 - btw), -tw2, H)),
        end_texts=(_vadd(_vadd((-(bw2 - btw), -bw2, 0.0), dvec, 0.8),
                         (1, 0, 0), 0.8),
                   _vadd(_vadd((bw2 - btw, -bw2, 0.0), dvec_r, 0.8),
                         (-1, 0, 0), 0.8),
                   (0.0, -tw2, H - 0.3)),
        inset_exprs=(cfg["thick_h"], cfg["thick_h"]),
        path_line=frame_d["path_y"],
        sk_name=f"{name}_Front_Sk", feat_name=f"{name}_FrontBoard",
        exp_vol=((ev(cfg["bot_w"]) - 2 * btw) + (ev(cfg["top_w"]) - 2 * btw))
                / 2 * (H / cosT) * ev(cfg["thick"]))
    front.name = names[0]

    mb = sp.mirror_body(comp, front, comp.xZConstructionPlane,
                        f"{name}_Back_Mir")
    back = _minus(_feat_bodies(mb), [front])[0]
    back.name = names[1]

    # Left (PIN board): full-width outline, end edges = box corner lines
    left = _sweep_outline(
        frame_d["left_pl"], frame_d["ax_left"],
        corners=((-bw2, -bw2, 0.0), (-bw2, bw2, 0.0),
                 (-tw2, tw2, H), (-tw2, -tw2, H)),
        end_texts=(_vadd(_vadd((-bw2, -bw2, 0.0), dvec, 0.8), (0, 1, 0), 0.8),
                   _vadd(_vadd((-bw2, bw2, 0.0), dvec_b, 0.8), (0, -1, 0), 0.8),
                   (-tw2, 0.0, H - 0.3)),
        inset_exprs=(None, None),       # corners AT the axis endpoints
        path_line=frame_d["path_x"],
        sk_name=f"{name}_Left_Sk", feat_name=f"{name}_LeftBoard",
        exp_vol=(ev(cfg["bot_w"]) + ev(cfg["top_w"])) / 2 * (H / cosT)
                * ev(cfg["thick"]))
    left.name = names[2]

    mr = sp.mirror_body(comp, left, comp.yZConstructionPlane,
                        f"{name}_Right_Mir")
    right = _minus(_feat_bodies(mr), [left])[0]
    right.name = names[3]

    return {names[0]: front, names[1]: back, names[2]: left,
            names[3]: right}


def corners(comp, cfg, frame_d, front, back, left, right, ev, name="SDT"):
    """Through dovetails at all four splayed corners.

    One fan trapezoid on the front face plane (base on the slanted
    shoulder reference, tips on the box-corner reference), swept along
    the pin board's grain, body-patterned along the shoulder line,
    mirrored to the other corners, then socket CUTs + tail JOINs.

    Returns:
        dict: tail_sweep, pattern, mirrors, cuts, joins.
    """
    p = cfg["prefix"]
    bw2 = ev(cfg["bot_w"]) / 2
    tw2 = ev(cfg["top_w"]) / 2
    H = ev(cfg["height"])
    btw = ev(cfg["thick_h"])
    th = ev(cfg["tilt"])
    tanT, cosT, sinT = math.tan(th), math.cos(th), math.sin(th)
    jl = ev(f"{p}_joint_len")
    sh = tw2 - bw2
    dvec = (-sh / jl, -sh / jl, H / jl)
    u_out = (-1.0, 0.0, 0.0)
    vvec = (0.0, -sinT, cosT)
    aa = ev(f"{p}_angle")

    P0 = (-(bw2 - btw), -bw2, 0.0)                  # shoulder line bottom
    Q0 = (-bw2, -bw2, 0.0)                          # box corner bottom
    hp, twd, pad = ev(f"{p}_half_pin"), ev(f"{p}_tail_w"), ev(f"{p}_pad")
    f_lo = _vadd((math.cos(aa) * u_out[0], 0.0, 0.0), vvec, -math.sin(aa))
    f_hi = _vadd((math.cos(aa) * u_out[0], 0.0, 0.0), vvec, math.sin(aa))
    B_lo = _vadd(P0, dvec, pad + hp)
    B_hi = _vadd(P0, dvec, pad + hp + twd)
    t_lo = -btw / (f_lo[0] + f_lo[2] * tanT)
    t_hi = -btw / (f_hi[0] + f_hi[2] * tanT)
    if t_lo <= 0 or t_hi <= 0:
        raise RuntimeError("flank/corner intersection signs wrong")
    T_lo = _vadd(B_lo, f_lo, t_lo)
    T_hi = _vadd(B_hi, f_hi, t_hi)

    # fan sketch — anchored ONLY to projected base-sketch geometry
    sk2 = comp.sketches.add(frame_d["front_pl"])
    sk2.name = f"{name}_Fan_Sk"
    m2s2 = sk2.modelToSketchSpace
    proj_ax = sk2.project(frame_d["ax_front"]).item(0)
    xa = sk2.sketchToModelSpace(proj_ax.startSketchPoint.geometry)
    xb = sk2.sketchToModelSpace(proj_ax.endSketchPoint.geometry)
    ax_l = (proj_ax.startSketchPoint if xa.x < xb.x
            else proj_ax.endSketchPoint)

    def sp2d(mpt):
        pt = m2s2(Point3D.create(mpt[0], mpt[1], mpt[2]))
        return Point3D.create(pt.x, pt.y, 0)

    lns2 = sk2.sketchCurves.sketchLines
    shoulder_ref = lns2.addByTwoPoints(sp2d(P0), sp2d(_vadd(P0, dvec, jl)))
    corner_ref = lns2.addByTwoPoints(sp2d(Q0), sp2d(_vadd(Q0, dvec, jl)))
    shoulder_ref.isConstruction = True
    corner_ref.isConstruction = True
    gc2 = sk2.geometricConstraints
    gc2.addCoincident(shoulder_ref.startSketchPoint, proj_ax)
    gc2.addCoincident(corner_ref.startSketchPoint, ax_l)
    d2 = sk2.sketchDimensions
    d2.addDistanceDimension(ax_l, shoulder_ref.startSketchPoint, ALIGNED,
                            sp2d(_vadd(Q0, (1, 0, 0), btw / 2))
                            ).parameter.expression = cfg["thick_h"]
    d2.addDistanceDimension(shoulder_ref.startSketchPoint,
                            shoulder_ref.endSketchPoint, ALIGNED,
                            sp2d(_vadd(P0, dvec, jl / 2))
                            ).parameter.expression = f"{p}_joint_len"
    d2.addDistanceDimension(corner_ref.startSketchPoint,
                            corner_ref.endSketchPoint, ALIGNED,
                            sp2d(_vadd(Q0, dvec, jl / 2))
                            ).parameter.expression = f"{p}_joint_len"
    _set_ang(d2.addAngularDimension(proj_ax, shoulder_ref,
                                    sp2d(_vadd(_vadd(P0, dvec, 0.8),
                                               (1, 0, 0), 0.8))),
             f"{p}_shoulder_ang")
    _set_ang(d2.addAngularDimension(proj_ax, corner_ref,
                                    sp2d(_vadd(_vadd(Q0, dvec, 1.2),
                                               (1, 0, 0), 1.4))),
             f"{p}_shoulder_ang")

    base = lns2.addByTwoPoints(sp2d(B_lo), sp2d(B_hi))
    flank_hi = lns2.addByTwoPoints(base.endSketchPoint, sp2d(T_hi))
    cap = lns2.addByTwoPoints(flank_hi.endSketchPoint, sp2d(T_lo))
    flank_lo = lns2.addByTwoPoints(cap.endSketchPoint, base.startSketchPoint)
    gc2.addCoincident(base.startSketchPoint, shoulder_ref)
    gc2.addCoincident(base.endSketchPoint, shoulder_ref)
    gc2.addCoincident(flank_hi.endSketchPoint, corner_ref)
    gc2.addCoincident(cap.endSketchPoint, corner_ref)
    d2.addDistanceDimension(shoulder_ref.startSketchPoint,
                            base.startSketchPoint, ALIGNED,
                            sp2d(_vadd(_vadd(P0, dvec, (pad + hp) / 2),
                                       u_out, 0.6))
                            ).parameter.expression = f"{p}_pad + {p}_half_pin"
    d2.addDistanceDimension(base.startSketchPoint, base.endSketchPoint,
                            ALIGNED,
                            sp2d(_vadd(_vadd(P0, dvec, pad + hp + twd / 2),
                                       u_out, -0.6))
                            ).parameter.expression = f"{p}_tail_w"
    _set_ang(d2.addAngularDimension(shoulder_ref, flank_lo,
                                    sp2d(_vadd(B_lo, _vnorm(_vadd(dvec, f_lo)),
                                               0.7))),
             f"{p}_ang_lo")
    _set_ang(d2.addAngularDimension(shoulder_ref, flank_hi,
                                    sp2d(_vadd(B_hi, _vnorm(_vadd(dvec, f_hi)),
                                               0.7))),
             f"{p}_ang_hi")

    for pt_obj, mpt in ((base.startSketchPoint, B_lo),
                        (base.endSketchPoint, B_hi),
                        (cap.endSketchPoint, T_lo),
                        (flank_hi.endSketchPoint, T_hi)):
        w = sk2.sketchToModelSpace(pt_obj.geometry)
        drift = math.sqrt((w.x - mpt[0]) ** 2 + (w.y - mpt[1]) ** 2
                          + (w.z - mpt[2]) ** 2)
        if drift > 0.02:
            raise RuntimeError(
                f"{name}_Fan_Sk vertex drifted {drift:.3f} cm")
    if not sk2.isFullyConstrained:
        raise RuntimeError(f"{name}_Fan_Sk is not fully constrained")

    sp.refs_to_construction(sk2)
    prof2 = sp.smallest_profile(sk2)

    # tail = fan swept along the PIN board's grain (+Y)
    path_t = comp.features.createPath(frame_d["path_y"], False)
    sw_in = comp.features.sweepFeatures.createInput(prof2, path_t, NEW)
    sw_in.orientation = \
        adsk.fusion.SweepOrientationTypes.ParallelOrientationType
    swf = comp.features.sweepFeatures.add(sw_in)
    swf.name = f"{name}_DT_Tail"
    tail0 = swf.bodies.item(0)
    tail0.name = f"{name}_DT_Tail_0"
    fan_area = _tri_area(B_lo, B_hi, T_hi) + _tri_area(B_lo, T_hi, T_lo)
    exp_vol = fan_area * ev(cfg["thick"])
    if abs(tail0.volume - exp_vol) > 0.02 * exp_vol:
        raise RuntimeError(
            f"tail sweep volume {tail0.volume:.2f}, expected {exp_vol:.2f}")

    # pattern along the slanted shoulder reference line
    n_dt = int(round(ev(f"{p}_tail_count")))
    sa = sk2.sketchToModelSpace(shoulder_ref.startSketchPoint.geometry)
    sb = sk2.sketchToModelSpace(shoulder_ref.endSketchPoint.geometry)
    spacing = f"{p}_pitch" if (sb.z - sa.z) > 0 else f"-{p}_pitch"
    pf = sp.body_pattern(comp, tail0, shoulder_ref, f"{p}_tail_count",
                         spacing, f"{name}_DT_Pat")
    fl_tails = _uniq([tail0] + _feat_bodies(pf))
    if len(fl_tails) != n_dt:
        raise RuntimeError(f"expected {n_dt} tails, got {len(fl_tails)}")

    m1 = sp.mirror_bodies(comp, fl_tails, comp.yZConstructionPlane,
                          f"{name}_DT_MirR")
    fr_tails = _minus(_uniq(_feat_bodies(m1)), fl_tails)
    m2f = sp.mirror_bodies(comp, fl_tails + fr_tails,
                           comp.xZConstructionPlane, f"{name}_DT_MirB")
    bk_tails = _minus(_uniq(_feat_bodies(m2f)), fl_tails + fr_tails)
    if len(fr_tails) != n_dt or len(bk_tails) != 2 * n_dt:
        raise RuntimeError(
            f"tail counts wrong: R={len(fr_tails)} back={len(bk_tails)}")
    bkl = [b for b in bk_tails if b.physicalProperties.centerOfMass.x < 0]
    bkr = [b for b in bk_tails if b.physicalProperties.centerOfMass.x > 0]

    cut_l = sp.combine(left, fl_tails + bkl, CUT, True, f"{name}_DT_L_Cut")
    cut_r = sp.combine(right, fr_tails + bkr, CUT, True, f"{name}_DT_R_Cut")
    join_f = sp.combine(front, fl_tails + fr_tails, JOIN, False,
                        f"{name}_DT_F_Join")
    join_b = sp.combine(back, bk_tails, JOIN, False, f"{name}_DT_B_Join")
    if front.lumps.count != 1 or back.lumps.count != 1:
        raise RuntimeError("tail JOIN left disconnected lumps")
    if comp.bRepBodies.count != 4:
        raise RuntimeError(
            f"expected 4 bodies after joins, got {comp.bRepBodies.count} "
            f"(ghost bodies? — fan sketch must not reference body edges)")

    return {
        "tail_sweep": swf, "pattern": pf, "mirrors": [m1, m2f],
        "cuts": [cut_l, cut_r], "joins": [join_f, join_b],
    }
