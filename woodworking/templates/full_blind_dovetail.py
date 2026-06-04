"""Full-blind (secret-mitred) dovetail joint template.

The strongest *hidden* corner joint: a through dovetail buried behind a 45°
mitered lip on BOTH boards' outer faces. From the outside the corner shows
only a clean miter line — no tails, no pins, no end grain. The dovetail is
entirely internal to the wood (hidden from both faces), so the joint looks
like a plain miter but has the mechanical lock of a dovetail.

Also called: secret-mitred dovetail, double-blind / double-lap dovetail.

Geometry (the "build one corner" decomposition)
------------------------------------------------
Each board is split, conceptually, into two layers at its joining end:

  * an OUTER LIP of thickness ``lip`` (the mitre) — kept solid, 45°-mitered
    to the other board's lip at the corner;
  * an INNER SLAB of thickness ``thick - lip`` — carries a normal through
    dovetail with the other board's inner slab.

Because the dovetail lives only in the inner slab, both recesses the user
asked for fall out automatically:

  * the tail's wide face sits at ``lip`` inside its own board's outer face;
  * the tail tips stop ``lip`` short of the mating board's outer face.

The two lips meet on the plane x = y at the corner (the visible miter); the
dovetail is sealed behind them.

Axis convention (one corner)
----------------------------
Outer corner arris runs along +Z at ``(x_out, y_out)``; the box interior is
toward +X / +Y.

  * board_a = TAIL board: thickness along Y (outer face y_out), runs +X.
  * board_b = PIN  board: thickness along X (outer face x_out), runs +Y.
  * tails repeat along Z (the joint height); penetration is along X.

Usage
-----
    from woodworking.templates import full_blind_dovetail as fbd

    fbd.define_params(params, prefix="fbd",
        angle="10 deg", tail_w="0.5 in", tail_count="3",
        joint_h_expr="board_h", thick_expr="board_thick",
        lip="board_thick / 3")

    res = fbd.corner(comp,
        thick_expr="board_thick", joint_h_expr="board_h",
        len_a_expr="6 in", len_b_expr="6 in",
        prefix="fbd", name="FBD", ev=ctx.ev)
    board_a, board_b = res["board_a"], res["board_b"]

Proportions & defaults
----------------------
Inherits the dovetail proportion rules for ``{prefix}_angle`` (7-9° hardwood,
10-14° softwood), ``{prefix}_tail_count`` (~1 per 1-2"), and
``{prefix}_tail_w``. One added parameter:

**{prefix}_lip** — the mitered outer-lip thickness (the recess depth):
  * Typical: 1/4 to 1/3 of board thickness. For 3/4" stock, 1/4" is a good
    default — thick enough not to blow out, thin enough that the buried
    dovetail still has ``thick - lip`` of socket depth to grip.
  * Minimum ~3/16": thinner lips chip when the miter is trimmed.
  * Maximum < 1/2 thickness: beyond that the inner slab is too thin to hold
    a meaningful dovetail.

Best for: fine casework, jewelry boxes, humidors, plinths — anywhere a corner
must read as a seamless miter while still being mechanically locked. It is the
most labor-intensive dovetail; not worth it for utility work (use through or
half-blind instead).
"""

import adsk.core
import adsk.fusion
import math

from helpers import sp
from woodworking.templates._dovetail_common import (
    trapezoid_sketch as _trapezoid_sketch,
)

Point3D = adsk.core.Point3D
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation

METADATA = {
    "name": "full_blind_dovetail",
    "category": "joinery",
    "description": "Through dovetail hidden behind a 45° mitered lip on both "
                   "faces — invisible from outside (secret-mitred dovetail)",
    "best_for": ["fine casework corners", "jewelry boxes", "humidors",
                 "plinths", "any corner that must read as a seamless miter"],
    "not_for": ["utility boxes", "high-volume production", "thin stock < 3/8 in"],
    "params": {
        "fbd_angle": "Dovetail angle (7-14 deg, 10 default)",
        "fbd_tail_w": "Tail width at the wide (recessed-outer) face",
        "fbd_tail_count": "Number of tails",
        "fbd_lip": "Mitered outer-lip thickness (the recess depth)",
        "fbd_socket": "Derived: thick - lip (inner-slab depth = tail penetration)",
        "fbd_pitch": "Derived: joint_h / tail_count",
        "fbd_pin_w": "Derived: pitch - tail_w",
        "fbd_narrow_w": "Derived: tail_w - 2 * socket * tan(angle)",
        "fbd_half_pin": "Derived: pin_w / 2 (half-pin at edges)",
    },
}


def define_params(params, prefix="fbd", angle="10 deg", tail_w="0.5 in",
                  tail_count="3", joint_h_expr="board_h",
                  thick_expr="board_thick", lip="board_thick / 3"):
    """Define all full-blind dovetail parameters with derivations.

    Args:
        params: design.userParameters
        prefix: Parameter name prefix.
        angle: Dovetail angle expression.
        tail_w: Tail width at the wide face.
        tail_count: Number of tails.
        joint_h_expr: Joint height (tail distribution axis = Z).
        thick_expr: Board thickness.
        lip: Mitered outer-lip thickness (recess depth). Default thick/3.

    Returns:
        Dict of parameter name strings.
    """
    VI = adsk.core.ValueInput.createByString
    p = prefix

    params.add(f"{p}_angle", VI(angle), "deg", "Dovetail angle")
    params.add(f"{p}_tail_w", VI(tail_w), "in", "Tail width at wide face")
    params.add(f"{p}_tail_count", VI(tail_count), "", "Number of tails")
    params.add(f"{p}_lip", VI(lip), "in", "Mitered outer-lip thickness (recess)")

    params.add(f"{p}_socket", VI(f"{thick_expr} - {p}_lip"),
               "in", "Inner-slab depth / tail penetration (derived)")
    params.add(f"{p}_pitch", VI(f"({joint_h_expr}) / {p}_tail_count"),
               "in", "Tail pitch (derived)")
    params.add(f"{p}_pin_w", VI(f"{p}_pitch - {p}_tail_w"),
               "in", "Inner pin width (derived)")
    params.add(f"{p}_narrow_w",
               VI(f"{p}_tail_w - 2 * {p}_socket * tan({p}_angle)"),
               "in", "Narrow face width (derived)")
    params.add(f"{p}_half_pin", VI(f"{p}_pin_w / 2"),
               "in", "Half-pin at edges (derived)")

    return {
        "angle": f"{p}_angle", "tail_w": f"{p}_tail_w",
        "tail_count": f"{p}_tail_count", "lip": f"{p}_lip",
        "socket": f"{p}_socket", "pitch": f"{p}_pitch",
        "pin_w": f"{p}_pin_w", "narrow_w": f"{p}_narrow_w",
        "half_pin": f"{p}_half_pin",
    }


def corner(comp, thick_expr, joint_h_expr, len_a_expr, len_b_expr,
           x_out_expr="0 in", y_out_expr="0 in", z0_expr="0 in",
           prefix="fbd", name="FBD", ev=None):
    """Build one secret-mitred (full-blind) dovetail corner.

    Generates BOTH boards and the joint between them (a corner generator —
    unlike the through/half-blind ``corner()`` which add tails to existing
    boards, the full-blind joint needs to control the inner-slab/lip split
    of both boards, so it builds them). ``define_params`` must be called
    first with the same ``prefix``.

    Topology:
      1. Four boxes: each board's inner slab + outer lip.
      2. Through dovetail between the inner slabs (trapezoid → JOIN tails
         onto slab A → feature-pattern along Z → CUT sockets into slab B).
      3. 45° miter both outer lips at the corner (triangular CUT tools).
      4. JOIN each lip back onto its slab → two finished boards.

    Args:
        comp: Component to build in.
        thick_expr: Board thickness (both boards).
        joint_h_expr: Joint height along Z (also the board height built here).
        len_a_expr: board_a length along +X (from x_out).
        len_b_expr: board_b length along +Y (from y_out).
        x_out_expr, y_out_expr: Outer-corner arris position (default origin).
        z0_expr: Base Z of the boards (default 0).
        prefix: Parameter prefix (from define_params).
        name: Feature/body name prefix.
        ev: Evaluator (defaults to active design).

    Returns:
        Dict: ``{"board_a": <tail board body>, "board_b": <pin board body>}``.
    """
    if ev is None:
        ev = sp._make_ev()
    p = prefix

    # ── Validate ──
    lip = ev(f"{p}_lip")
    t = ev(thick_expr)
    if lip <= 0 or lip >= t:
        raise ValueError(
            f"{p}_lip must be 0 < lip < thickness (got lip={lip/2.54:.3f}in, "
            f"thick={t/2.54:.3f}in).")
    pin_w = ev(f"{p}_pin_w")
    if pin_w <= 0:
        n = int(ev(f"{p}_tail_count"))
        raise ValueError(
            f"Dovetails don't fit: {n} tails x {ev(f'{p}_tail_w')/2.54:.3f}in "
            f"exceeds joint height. Reduce {p}_tail_count or {p}_tail_w.")
    narrow_w = ev(f"{p}_narrow_w")
    if narrow_w <= 0:
        raise ValueError(
            f"Tails over-taper (narrow_w <= 0): reduce {p}_angle or increase "
            f"{p}_tail_w / {p}_lip.")

    VI = adsk.core.ValueInput.createByString

    # ── Sketch boards on a base plane at z0 ──
    base_pl = sp.off_plane(comp, comp.xYConstructionPlane, z0_expr, f"{name}_Base_Pl")

    def mk_box(nm, x0, y0, w, d):
        sk, prof = sp.sketch_rect_model(
            comp, base_pl, (x0, y0, z0_expr), {"x": w, "y": d},
            f"{nm}_Sk", ev=ev)
        b = sp.ext_new(comp, prof, joint_h_expr, nm).bodies.item(0)
        b.name = nm
        return b

    xo, yo = x_out_expr, y_out_expr
    # board_a (tail, thickness Y, runs +X): inner slab S1 (end recessed in X) + lip P1
    S1 = mk_box(f"{name}_A_slab",
                f"({xo}) + {thick_expr}", f"({yo}) + {p}_lip",
                f"({len_a_expr}) - {thick_expr}", f"{thick_expr} - {p}_lip")
    P1 = mk_box(f"{name}_A_lip", xo, yo, len_a_expr, f"{p}_lip")
    # board_b (pin, thickness X, runs +Y): inner slab S2 + lip P2
    S2 = mk_box(f"{name}_B_slab",
                f"({xo}) + {p}_lip", f"({yo}) + {p}_lip",
                f"{thick_expr} - {p}_lip", f"({len_b_expr}) - {p}_lip")
    P2 = mk_box(f"{name}_B_lip", xo, yo, f"{p}_lip", len_b_expr)

    # ── Inner through dovetail: tails on S1 → sockets in S2 ──
    # Sketch the tail trapezoid on a plane at x = x_out + thick; flare across Y
    # (wide at the recessed outer face y_out+lip, narrow at the inner face
    # y_out+thick); JOIN it onto S1 and extrude -X (penetration = socket).
    tail_pl = sp.off_plane(comp, comp.yZConstructionPlane,
                           f"({xo}) + {thick_expr}", f"{name}_Tail_Pl")
    xm = ev(f"({xo}) + {thick_expr}")
    ylip = ev(f"({yo}) + {p}_lip")
    yt = ev(f"({yo}) + {thick_expr}")
    z0t = ev(f"({z0_expr}) + {p}_half_pin")
    tw = ev(f"{p}_tail_w")
    delta = ev(f"{p}_socket") * math.tan(ev(f"{p}_angle"))

    m1 = Point3D.create(xm, ylip, z0t)              # wide-low  (recessed outer)
    m2 = Point3D.create(xm, ylip, z0t + tw)         # wide-high
    m3 = Point3D.create(xm, yt, z0t + tw - delta)   # narrow-high (inner face)
    m4 = Point3D.create(xm, yt, z0t + delta)        # narrow-low
    prof = _trapezoid_sketch(
        comp, tail_pl, m1, m2, m3, m4,
        thick_expr=f"{p}_socket",
        short_joint_expr=f"({z0_expr}) + {p}_half_pin + {p}_socket * tan({p}_angle)",
        short_base_expr=f"({yo}) + {thick_expr}",
        prefix=prefix, name=f"{name}_Tail")
    join = sp.ext_op(comp, prof, f"{p}_socket", JOIN, S1,
                     f"{name}_TailJoin", flip=True)
    sp.feat_pattern(comp, join, comp.zConstructionAxis,
                    f"{p}_tail_count", f"{p}_pitch", f"{name}_TailPat")
    sp.combine(S2, S1, CUT, True, f"{name}_Sockets")

    # ── Miter the two outer lips at 45° in the corner [x_out, x_out+lip]^2 ──
    # Parametric right-isoceles triangle: right-angle vertex at (vx,vy), legs of
    # length `lip` along d1/d2. Fully dimensioned so it recomputes on param change.
    zc = ev(z0_expr)

    def tri_tool(nm, vx_expr, vy_expr, d1, d2):
        sk = comp.sketches.add(base_pl)
        gc = sk.geometricConstraints
        d = sk.sketchDimensions
        vx, vy = ev(vx_expr), ev(vy_expr)
        Vs = sk.modelToSketchSpace(Point3D.create(vx, vy, zc))
        As = sk.modelToSketchSpace(Point3D.create(vx + d1[0] * lip, vy + d1[1] * lip, zc))
        Bs = sk.modelToSketchSpace(Point3D.create(vx + d2[0] * lip, vy + d2[1] * lip, zc))
        ls = sk.sketchCurves.sketchLines
        la = ls.addByTwoPoints(Point3D.create(Vs.x, Vs.y, 0), Point3D.create(As.x, As.y, 0))
        lb = ls.addByTwoPoints(la.startSketchPoint, Point3D.create(Bs.x, Bs.y, 0))
        ls.addByTwoPoints(la.endSketchPoint, lb.endSketchPoint)  # hypotenuse
        orient = sp.probe_orientations(sk, vx, vy, zc)
        # legs are axis-aligned: horizontal if along model X, vertical if along Y
        (gc.addHorizontal if d1[0] != 0 else gc.addVertical)(la)
        (gc.addHorizontal if d2[0] != 0 else gc.addVertical)(lb)
        d.addDistanceDimension(la.startSketchPoint, la.endSketchPoint,
                               orient['x'] if d1[0] != 0 else orient['y'],
                               Point3D.create(As.x, As.y, 0)).parameter.expression = f"{p}_lip"
        d.addDistanceDimension(lb.startSketchPoint, lb.endSketchPoint,
                               orient['x'] if d2[0] != 0 else orient['y'],
                               Point3D.create(Bs.x, Bs.y, 0)).parameter.expression = f"{p}_lip"
        # position the vertex from the origin (generator/root geometry)
        d.addDistanceDimension(sk.originPoint, la.startSketchPoint, orient['x'],
                               Point3D.create(Vs.x, Vs.y - 1, 0)).parameter.expression = vx_expr
        d.addDistanceDimension(sk.originPoint, la.startSketchPoint, orient['y'],
                               Point3D.create(Vs.x - 1, Vs.y, 0)).parameter.expression = vy_expr
        prof2 = sp.smallest_profile(sk)
        body = sp.ext_new(comp, prof2, joint_h_expr, nm).bodies.item(0)
        body.name = nm
        return body

    # P1 lip (board_a, outer face y_out): remove the x<y triangle → keeps x>=y.
    # Right-angle vertex at (x_out, y_out+lip); legs down (-Y) and right (+X).
    t1 = tri_tool(f"{name}_MiterToolA", xo, f"({yo}) + {p}_lip", (0, -1), (1, 0))
    sp.combine(P1, t1, CUT, False, f"{name}_MiterA")
    # P2 lip (board_b, outer face x_out): remove the x>y triangle → keeps y>=x.
    # Right-angle vertex at (x_out+lip, y_out); legs left (-X) and up (+Y).
    t2 = tri_tool(f"{name}_MiterToolB", f"({xo}) + {p}_lip", yo, (-1, 0), (0, 1))
    sp.combine(P2, t2, CUT, False, f"{name}_MiterB")

    # ── JOIN each lip back onto its slab ──
    sp.combine(S1, P1, JOIN, False, f"{name}_BoardA")
    S1.name = f"{name}_BoardA"
    sp.combine(S2, P2, JOIN, False, f"{name}_BoardB")
    S2.name = f"{name}_BoardB"

    return {"board_a": S1, "board_b": S2}
