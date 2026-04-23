"""Splayed leg set sub-assembly template.

Creates 4 compound-splayed legs using the trapezoid sketch + Move feature
technique. Builds one near-left leg, trims it against the seat/top body,
then mirrors to all 4 corners.

Usage:
    from woodworking.templates import splayed_legs

    # Define splay parameters
    splayed_legs.define_params(params,
        splay_x="5 deg", splay_y="5 deg",
        leg_w="1.5 in", leg_d="1.5 in",
        leg_h_expr="table_h - top_t",
        top_h_expr="table_h - top_t")

    # Build 4 legs
    legs = splayed_legs.build(root,
        inset_x_expr="leg_inset_x", inset_y_expr="leg_inset_y",
        seat_body=top_body, x_mid=XMid, y_mid=YMid,
        ev=ctx.ev)
    # legs = {"NL": body, "NR": body, "FL": body, "FR": body}

    # Get splay-adjusted position at a given height
    sx, sy = splayed_legs.splay_offset(height_cm, ev=ctx.ev)
"""

import adsk.core
import adsk.fusion
import math

from helpers import sp

Point3D = adsk.core.Point3D
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation

METADATA = {
    "name": "splayed_legs",
    "category": "sub_assembly",
    "description": "4 compound-splayed legs with trapezoid sketch + Move feature",
    "best_for": ["tables", "stools", "chairs", "benches with splayed legs"],
    "requires": ["seat/top body to trim against", "X and Y midplanes"],
    "params": {
        "splay": "Primary splay angle (X direction, in sketch plane)",
        "splay_w": "Secondary splay angle (Y direction, via Move rotation)",
        "leg_w": "Leg width (X dimension in sketch)",
        "leg_d": "Leg depth (Y dimension, extrude distance)",
        "leg_h": "Leg height (derived or direct)",
        "leg_top_z": "Z coordinate of leg top (= seat underside)",
        "splay_shift": "Derived: foot X offset from top",
        "splay_shift_w": "Derived: foot Y offset from top",
    },
}


def define_params(params, splay_x="5 deg", splay_y=None,
                  leg_w="1.5 in", leg_d="1.5 in",
                  leg_h_expr="table_h - top_t",
                  top_h_expr=None,
                  inset_x="3 in", inset_y="3 in"):
    """Define all splayed leg parameters.

    Args:
        params: design.userParameters
        splay_x: Primary splay angle expression (X direction).
        splay_y: Secondary splay angle expression (Y direction).
            If None, uses same angle as splay_x.
        leg_w: Leg width expression (X dimension).
        leg_d: Leg depth expression (Y dimension).
        leg_h_expr: Leg height expression.
        top_h_expr: Leg top Z expression. If None, uses leg_h_expr.
        inset_x: Leg inset from edge in X.
        inset_y: Leg inset from edge in Y.

    Returns:
        Dict of parameter names.
    """
    VI = adsk.core.ValueInput.createByString

    params.add("splay", VI(splay_x), "deg", "Leg splay (X direction)")
    if splay_y is None:
        params.add("splay_w", VI("splay"), "deg", "Leg splay (Y direction)")
    else:
        params.add("splay_w", VI(splay_y), "deg", "Leg splay (Y direction)")

    params.add("leg_w", VI(leg_w), "in", "Leg width")
    params.add("leg_d", VI(leg_d), "in", "Leg depth")
    params.add("leg_h", VI(leg_h_expr), "in", "Leg height")
    if top_h_expr is None:
        params.add("leg_top_z", VI("leg_h"), "in", "Leg top Z")
    else:
        params.add("leg_top_z", VI(top_h_expr), "in", "Leg top Z")
    params.add("leg_inset_x", VI(inset_x), "in", "Leg inset from edge (X)")
    params.add("leg_inset_y", VI(inset_y), "in", "Leg inset from edge (Y)")

    # Derived splay offsets
    params.add("splay_shift",
               VI("leg_top_z * tan(splay)"),
               "in", "Foot X offset from top")
    params.add("splay_shift_w",
               VI("leg_top_z * tan(splay_w)"),
               "in", "Foot Y offset from top")

    # Floor margin: extra length below Z=0 so after Y-splay rotation the
    # leg extends past the ground plane, allowing a clean split at Z=0.
    params.add("leg_floor_margin",
               VI("leg_d * tan(splay_w) + 0.25 in"),
               "in", "Extra leg length below ground for floor trim")

    return {
        "splay": "splay", "splay_w": "splay_w",
        "leg_w": "leg_w", "leg_d": "leg_d",
        "leg_h": "leg_h", "leg_top_z": "leg_top_z",
        "leg_inset_x": "leg_inset_x", "leg_inset_y": "leg_inset_y",
        "splay_shift": "splay_shift", "splay_shift_w": "splay_shift_w",
    }


def build(root_comp, inset_x_expr="leg_inset_x", inset_y_expr="leg_inset_y",
          seat_body=None, x_mid=None, y_mid=None, ev=None):
    """Build 4 splayed legs via trapezoid sketch + Move + trim + mirror.

    Args:
        root_comp: Root component.
        inset_x_expr: X inset expression for leg center.
        inset_y_expr: Y inset expression for leg center.
        seat_body: Seat/top body to trim legs against. If None, no trim CUT.
        x_mid: X midplane (ConstructionPlane) for far mirror.
        y_mid: Y midplane (ConstructionPlane) for side mirror.
        ev: Evaluator function.

    Returns:
        Dict {"NL": body, "NR": body, "FL": body, "FR": body,
              "plane": LegFront_Pl construction plane}.
    """
    if ev is None:
        ev = sp._make_ev()

    # ── Step 1: Construction plane at front face of near-left leg ──
    leg_front_pl = sp.off_plane(root_comp, root_comp.xZConstructionPlane,
                                f"{inset_y_expr} - leg_d / 2", "LegFront_Pl")

    # ── Step 2: Trapezoid sketch (primary X-splay in sketch plane) ──
    sk = root_comp.sketches.add(leg_front_pl)
    sk.name = "Leg_NL_Sk"
    lns = sk.sketchCurves.sketchLines
    m2s = sk.modelToSketchSpace

    inset_x = ev(inset_x_expr)
    half_w = ev("leg_w") / 2
    top_z = ev("leg_top_z")
    shift = ev("splay_shift")
    floor_margin = ev("leg_floor_margin")
    # Total shift including margin below Z=0
    total_h = top_z + floor_margin
    total_shift = total_h * math.tan(ev("splay") * math.pi / 180)
    plane_y = ev(inset_y_expr) - ev("leg_d") / 2

    # 4 corners in model space → sketch space
    # Bottom extends below Z=0 by floor_margin for clean floor trim after Y-splay
    s_tl = m2s(Point3D.create(inset_x - half_w, plane_y, top_z))
    s_tr = m2s(Point3D.create(inset_x + half_w, plane_y, top_z))
    s_br = m2s(Point3D.create(inset_x + half_w - total_shift, plane_y, -floor_margin))
    s_bl = m2s(Point3D.create(inset_x - half_w - total_shift, plane_y, -floor_margin))

    # Connected lines with shared sketch points
    ln_top = lns.addByTwoPoints(
        Point3D.create(s_tl.x, s_tl.y, 0), Point3D.create(s_tr.x, s_tr.y, 0))
    ln_right = lns.addByTwoPoints(
        ln_top.endSketchPoint, Point3D.create(s_br.x, s_br.y, 0))
    ln_bot = lns.addByTwoPoints(
        ln_right.endSketchPoint, Point3D.create(s_bl.x, s_bl.y, 0))
    ln_left = lns.addByTwoPoints(
        ln_bot.endSketchPoint, ln_top.startSketchPoint)

    # H constraints on top/bottom only — sides are intentionally angled
    gc = sk.geometricConstraints
    gc.addHorizontal(ln_top)
    gc.addHorizontal(ln_bot)

    # 6 parametric dimensions
    d = sk.sketchDimensions
    mid_top = Point3D.create((s_tl.x + s_tr.x) / 2, s_tl.y - 1, 0)
    mid_bot = Point3D.create((s_bl.x + s_br.x) / 2, s_bl.y + 1, 0)

    d.addDistanceDimension(
        ln_top.startSketchPoint, ln_top.endSketchPoint,
        sp.H, mid_top
    ).parameter.expression = "leg_w"
    d.addDistanceDimension(
        ln_bot.startSketchPoint, ln_bot.endSketchPoint,
        sp.H, mid_bot
    ).parameter.expression = "leg_w"
    d.addDistanceDimension(
        sk.originPoint, ln_top.startSketchPoint,
        sp.V, Point3D.create(s_tl.x - 1, s_tl.y / 2, 0)
    ).parameter.expression = "leg_top_z"
    d.addDistanceDimension(
        sk.originPoint, ln_top.startSketchPoint,
        sp.H, Point3D.create(s_tl.x / 2, s_tl.y - 2, 0)
    ).parameter.expression = f"{inset_x_expr} - leg_w / 2"
    d.addDistanceDimension(
        ln_top.startSketchPoint, ln_bot.endSketchPoint,
        sp.H, Point3D.create((s_tl.x + s_bl.x) / 2, (s_tl.y + s_bl.y) / 2 - 1, 0)
    ).parameter.expression = "(leg_top_z + leg_floor_margin) * tan(splay)"
    d.addDistanceDimension(
        ln_top.startSketchPoint, ln_bot.endSketchPoint,
        sp.V, Point3D.create(s_tl.x - 2, (s_tl.y + s_bl.y) / 2, 0)
    ).parameter.expression = "leg_top_z + leg_floor_margin"

    # Extrude leg depth along Y
    ext = sp.ext_new(root_comp, sk.profiles.item(0), "leg_d", "Leg_NL")
    nl_body = ext.bodies.item(0)
    nl_body.name = "Leg_NL"

    # ── Step 3: Move feature (secondary Y-splay via X-axis rotation) ──
    angle_w = ev("splay_w")
    c_w, s_w = math.cos(angle_w), math.sin(angle_w)

    # Pivot at inner edge of leg top — ensures full submersion into seat
    pivot_y = ev(inset_y_expr) + ev("leg_d") / 2
    pivot_z = top_z

    ty = pivot_y - (pivot_y * c_w + pivot_z * s_w)
    tz = pivot_z - (-pivot_y * s_w + pivot_z * c_w)

    xform = adsk.core.Matrix3D.create()
    xform.setWithArray([
        1.0, 0.0, 0.0, 0.0,
        0.0, c_w, s_w, ty,
        0.0, -s_w, c_w, tz,
        0.0, 0.0, 0.0, 1.0
    ])

    move_coll = adsk.core.ObjectCollection.create()
    move_coll.add(nl_body)
    move_inp = root_comp.features.moveFeatures.createInput2(move_coll)
    move_inp.defineAsFreeMove(xform)
    move_feat = root_comp.features.moveFeatures.add(move_inp)
    move_feat.name = "YSplay_NL"

    # Re-find body after Move
    nl_body = _find_body(root_comp, "Leg_NL")

    # ── Step 3b: Trim bottom flat at ground plane (Z=0) ──
    # After Y-splay rotation, the foot face is angled and the leg extends
    # below Z=0 (due to floor_margin). CUT away everything below Z=0
    # with a large slab, leaving a flat foot parallel to the ground.
    floor_sk = root_comp.sketches.add(root_comp.xYConstructionPlane)
    floor_sk.name = "LegFloor_Sk"
    bb = nl_body.boundingBox
    margin = 2.0  # cm
    p1 = Point3D.create(bb.minPoint.x - margin, bb.minPoint.y - margin, 0)
    p2 = Point3D.create(bb.maxPoint.x + margin, bb.maxPoint.y + margin, 0)
    floor_sk.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)
    floor_prof = floor_sk.profiles.item(0)
    floor_ext = sp.ext_op(root_comp, floor_prof, "leg_floor_margin + 1 in",
                          CUT, nl_body, "LegFloor_NL", flip=True)
    nl_body = _find_body(root_comp, "Leg_NL")

    # ── Step 4: Trim CUT against seat/top ──
    if seat_body is not None:
        sp.combine(nl_body, seat_body, CUT, True, "LegTrim_NL")
        nl_body = _find_body(root_comp, "Leg_NL")

    # ── Step 5: Mirror NL → NR across YMid ──
    nr_mir = sp.mirror_bodies(root_comp, [nl_body], y_mid, "Leg_NR_Mir")
    nr_body = nr_mir.bodies.item(0)
    nr_body.name = "Leg_NR"
    nl_body = _find_body(root_comp, "Leg_NL")

    # ── Step 6: Mirror NL+NR → FL, FR across XMid ──
    far_mir = sp.mirror_bodies(root_comp, [nl_body, nr_body], x_mid, "Legs_Far_Mir")
    fl_body = far_mir.bodies.item(0)
    fr_body = far_mir.bodies.item(1)
    fl_body.name = "Leg_FL"
    fr_body.name = "Leg_FR"
    nl_body = _find_body(root_comp, "Leg_NL")
    nr_body = _find_body(root_comp, "Leg_NR")

    return {
        "NL": nl_body, "NR": nr_body,
        "FL": fl_body, "FR": fr_body,
        "plane": leg_front_pl,
    }


def splay_offset(height_cm, ev=None):
    """Return (sx, sy) splay offsets at a given height in cm.

    Linear interpolation: at h=0 (floor) full splay; at h=leg_top_z zero.
    Use this to compute splay-adjusted positions for stretchers, rails, etc.

    Args:
        height_cm: Height in cm (e.g. ev("str_h")).
        ev: Evaluator function.

    Returns:
        (sx_cm, sy_cm) — splay offsets in cm.
    """
    if ev is None:
        ev = sp._make_ev()
    top_z = ev("leg_top_z")
    frac = (top_z - height_cm) / top_z
    return ev("splay_shift") * frac, ev("splay_shift_w") * frac


def define_stretcher_params(params, name, height_expr,
                            top_l_expr, top_w_expr,
                            inset_x_expr="leg_inset_x",
                            inset_y_expr="leg_inset_y",
                            leg_w_expr="leg_w", leg_d_expr="leg_d",
                            tenon_l_expr="st_l"):
    """Define splay-adjusted stretcher length parameters.

    Creates the splay offset and total length params for a stretcher
    at a given height, accounting for leg splay at that height.

    Args:
        params: design.userParameters
        name: Param prefix (e.g. "bstr" for back stretcher).
        height_expr: Stretcher center height expression.
        top_l_expr: Top length expression (e.g. "top_l" or "seat_l").
        top_w_expr: Top width expression.
        inset_x_expr, inset_y_expr: Leg inset expressions.
        leg_w_expr, leg_d_expr: Leg dimension expressions.
        tenon_l_expr: Tenon length expression (added to each end).

    Returns:
        Dict with "sx", "sy", "len_x", "len_y" parameter names.
    """
    VI = adsk.core.ValueInput.createByString
    p = name

    # Splay offsets at this stretcher's height
    params.add(f"{p}_sx",
               VI(f"splay_shift * (leg_top_z - {height_expr}) / leg_top_z"),
               "in", f"{name} X splay offset")
    params.add(f"{p}_sy",
               VI(f"splay_shift_w * (leg_top_z - {height_expr}) / leg_top_z"),
               "in", f"{name} Y splay offset")

    # Total stretcher lengths (face-to-face + 2× tenon)
    params.add(f"{p}_len",
               VI(f"{top_l_expr} - 2 * {inset_x_expr} + 2 * {p}_sx "
                  f"- {leg_w_expr} + 2 * {tenon_l_expr}"),
               "in", f"{name} total length (X direction)")
    params.add(f"{p}_len_y",
               VI(f"{top_w_expr} - 2 * {inset_y_expr} + 2 * {p}_sy "
                  f"- {leg_d_expr} + 2 * {tenon_l_expr}"),
               "in", f"{name} total length (Y direction)")

    return {
        "sx": f"{p}_sx", "sy": f"{p}_sy",
        "len_x": f"{p}_len", "len_y": f"{p}_len_y",
    }


def _find_body(comp, name):
    """Find body by name in component."""
    for i in range(comp.bRepBodies.count):
        b = comp.bRepBodies.item(i)
        if b.name == name:
            return b
    return sp.DesignContext().find_body(name, comp)
