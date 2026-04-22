"""Chest / box lock template.

Creates parametric lock body mortise, keyhole, and strike plate recess
for boxes and chests. The lock body is modeled as a rectangular block
that CUTs its pocket into the front board.

Usage:
    from woodworking.templates import chest_lock

    lp = chest_lock.define_params(params, prefix="lk", size="small")

    # Lock body mortise in front board
    chest_lock.lock_mortise(comp, front_body, front_inner_plane,
        origin=("case_l / 2 - lk_w / 2", "front_inner_y", "case_h - lk_h - 0.5 in"),
        size={"x": "lk_w", "z": "lk_h"},
        prefix="lk", name="Lock", ev=ctx.ev, flip=True)

    # Keyhole through front board
    chest_lock.keyhole(comp, front_body, front_outer_plane,
        center=("case_l / 2", "front_outer_y", "case_h - lk_h - 0.25 in"),
        prefix="lk", name="Lock", ev=ctx.ev, flip=True,
        board_thick_expr="board_thick")

    # Strike plate in lid
    chest_lock.strike(comp, lid_body, lid_plane,
        origin=("case_l / 2 - lk_strike_w / 2", "strike_y", "lid_z"),
        size={"x": "lk_strike_w", "y": "lk_strike_l"},
        prefix="lk", name="Strike", ev=ctx.ev)
"""

import adsk.core
import adsk.fusion

from helpers import sp

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

Point3D = adsk.core.Point3D

METADATA = {
    "name": "chest_lock",
    "category": "hardware",
    "description": "Chest/box lock with mortise, keyhole, and strike plate",
    "best_for": ["jewelry boxes", "blanket chests", "tool chests",
                 "humidors", "keepsake boxes"],
    "not_for": ["cabinet locks (different form factor)",
                "combination locks (no keyhole)"],
    "standard_sizes": {
        "small": {
            "w": "1 in", "h": "0.75 in", "d": "0.5 in",
            "keyhole_d": "0.1875 in", "slot_w": "0.0625 in",
            "slot_h": "0.25 in",
            "strike_w": "0.75 in", "strike_l": "0.375 in",
            "strike_t": "0.0625 in",
            "note": "Small jewelry box lock",
        },
        "medium": {
            "w": "1.5 in", "h": "1 in", "d": "0.625 in",
            "keyhole_d": "0.25 in", "slot_w": "0.0625 in",
            "slot_h": "0.3125 in",
            "strike_w": "1 in", "strike_l": "0.5 in",
            "strike_t": "0.0625 in",
            "note": "Medium box/chest lock",
        },
        "large": {
            "w": "2 in", "h": "1.5 in", "d": "0.75 in",
            "keyhole_d": "0.3125 in", "slot_w": "0.09375 in",
            "slot_h": "0.375 in",
            "strike_w": "1.25 in", "strike_l": "0.625 in",
            "strike_t": "0.09375 in",
            "note": "Large chest/blanket chest lock",
        },
    },
    "params": {
        "lk_w": "Lock body width",
        "lk_h": "Lock body height",
        "lk_d": "Lock body depth (mortise depth)",
        "lk_keyhole_d": "Keyhole entry diameter",
        "lk_slot_w": "Key blade slot width",
        "lk_slot_h": "Key blade slot height (below keyhole center)",
        "lk_strike_w": "Strike plate width",
        "lk_strike_l": "Strike plate length",
        "lk_strike_t": "Strike plate thickness (recess depth)",
    },
}


def define_params(params, prefix="lk", size="small",
                  w=None, h=None, d=None,
                  keyhole_d=None, slot_w=None, slot_h=None,
                  strike_w=None, strike_l=None, strike_t=None):
    """Define chest lock parameters.

    Args:
        params: design.userParameters
        prefix: Parameter name prefix.
        size: Preset name.
        Individual overrides for any dimension.

    Returns:
        Dict of parameter name strings.
    """
    VI = adsk.core.ValueInput.createByString
    p = prefix
    s = METADATA["standard_sizes"].get(size,
        METADATA["standard_sizes"]["small"])

    params.add(f"{p}_w", VI(w or s["w"]), "in", "Lock body width")
    params.add(f"{p}_h", VI(h or s["h"]), "in", "Lock body height")
    params.add(f"{p}_d", VI(d or s["d"]), "in", "Lock body depth")
    params.add(f"{p}_keyhole_d", VI(keyhole_d or s["keyhole_d"]), "in",
               "Keyhole entry diameter")
    params.add(f"{p}_slot_w", VI(slot_w or s["slot_w"]), "in",
               "Key blade slot width")
    params.add(f"{p}_slot_h", VI(slot_h or s["slot_h"]), "in",
               "Key blade slot height")
    params.add(f"{p}_strike_w", VI(strike_w or s["strike_w"]), "in",
               "Strike plate width")
    params.add(f"{p}_strike_l", VI(strike_l or s["strike_l"]), "in",
               "Strike plate length")
    params.add(f"{p}_strike_t", VI(strike_t or s["strike_t"]), "in",
               "Strike plate recess depth")

    return {
        "w": f"{p}_w", "h": f"{p}_h", "d": f"{p}_d",
        "keyhole_d": f"{p}_keyhole_d",
        "slot_w": f"{p}_slot_w", "slot_h": f"{p}_slot_h",
        "strike_w": f"{p}_strike_w", "strike_l": f"{p}_strike_l",
        "strike_t": f"{p}_strike_t",
    }


def lock_mortise(comp, body, plane, origin, size_map,
                 prefix="lk", name="Lock", ev=None, flip=False):
    """CUT the lock body pocket and place a visual lock body.

    Creates a rectangular block (the lock body), uses it to CUT the
    mortise (keepTool=True). The block stays as a visual representation.

    Args:
        comp: Component.
        body: Front board body to CUT into.
        plane: Sketch plane on the board's inner face.
        origin: (x_expr, y_expr, z_expr) — corner of lock body.
        size_map: {axis: expr, axis: expr} — two face dimensions.
            Typically {horizontal: "lk_w", vertical: "lk_h"}.
        prefix: Parameter prefix.
        name: Feature name prefix.
        ev: Evaluator.
        flip: Extrude in negative direction.

    Returns:
        Dict with "lock_ext", "lock_body", "cut".
    """
    if ev is None:
        ev = sp._make_ev()
    p = prefix

    # Create lock body block
    sk, prof = sp.sketch_rect_model(comp, plane, origin, size_map,
                                    f"{name}_Sk", ev)
    lock_ext = sp.ext_op(comp, prof, f"{p}_d", NEW, None,
                         f"{name}_Body", flip=flip)
    lock_body = lock_ext.bodies.item(0)
    lock_body.name = f"{name}_Body"

    # CUT mortise pocket
    cut = sp.combine(body, lock_body, CUT, True, f"{name}_Mort")

    return {"lock_ext": lock_ext, "lock_body": lock_body, "cut": cut}


def keyhole(comp, body, plane, center,
            prefix="lk", name="Lock", ev=None, flip=False,
            board_thick_expr="board_thick"):
    """CUT a keyhole profile through the board.

    The keyhole is a circle (key entry) plus a narrow slot below
    (key blade rotation). Both CUT through the full board thickness.

    Args:
        comp: Component.
        body: Front board body.
        plane: Sketch plane on the board face.
        center: (x_expr, y_expr, z_expr) — center of keyhole circle.
        prefix: Parameter prefix.
        name: Feature name prefix.
        ev: Evaluator.
        flip: Extrude in negative direction.
        board_thick_expr: Board thickness expression for through-hole depth.

    Returns:
        Dict with "hole_cut" and "slot_cut".
    """
    if ev is None:
        ev = sp._make_ev()
    p = prefix

    cx = ev(center[0])
    cy = ev(center[1])
    cz = ev(center[2])
    r = ev(f"{p}_keyhole_d") / 2

    # -- Keyhole circle --
    sk = comp.sketches.add(plane)
    sk.name = f"{name}_KeySk"
    m = sk.modelToSketchSpace
    sc = m(Point3D.create(cx, cy, cz))

    circle = sk.sketchCurves.sketchCircles.addByCenterRadius(
        Point3D.create(sc.x, sc.y, 0), r)
    sk.sketchDimensions.addDiameterDimension(
        circle, Point3D.create(sc.x + r + 0.5, sc.y, 0)
    ).parameter.expression = f"{p}_keyhole_d"

    prof = sk.profiles.item(0)
    hole_cut = sp.ext_op(comp, prof, board_thick_expr, CUT, body,
                         f"{name}_KeyHole", flip=flip)

    # -- Key blade slot (rectangle below the circle) --
    slot_w = ev(f"{p}_slot_w")
    slot_h = ev(f"{p}_slot_h")

    # Detect which sketch direction is "down" (away from keyhole center)
    # by probing the vertical model axis
    h_ax, v_ax = sp.probe_sketch_axes(sk)
    # Slot extends in the -v direction from the circle center

    sk2 = comp.sketches.add(plane)
    sk2.name = f"{name}_SlotSk"
    m2 = sk2.modelToSketchSpace

    # Slot corners: centered horizontally on keyhole, extending downward
    # "Down" in model space depends on the joint axis. We'll use the
    # v_axis negative direction (which is typically -Z or -Y).
    sc2 = m2(Point3D.create(cx, cy, cz))

    # Probe sign: which direction is "down" in sketch space
    _, _, _, v_sign = _probe_signs(sk2)

    # Slot rectangle in sketch space
    half_sw = slot_w / 2
    if v_sign > 0:
        # Positive v_axis → "down" is sketch -Y
        s1 = Point3D.create(sc2.x - half_sw, sc2.y - slot_h, 0)
        s2 = Point3D.create(sc2.x + half_sw, sc2.y, 0)
    else:
        # Negative v_axis → "down" is sketch +Y
        s1 = Point3D.create(sc2.x - half_sw, sc2.y, 0)
        s2 = Point3D.create(sc2.x + half_sw, sc2.y + slot_h, 0)

    rect = sk2.sketchCurves.sketchLines.addTwoPointRectangle(s1, s2)
    gc = sk2.geometricConstraints
    gc.addHorizontal(rect.item(0))
    gc.addHorizontal(rect.item(2))
    gc.addVertical(rect.item(1))
    gc.addVertical(rect.item(3))

    prof2 = sp.smallest_profile(sk2)
    slot_cut = sp.ext_op(comp, prof2, board_thick_expr, CUT, body,
                         f"{name}_KeySlot", flip=flip)

    return {"hole_cut": hole_cut, "slot_cut": slot_cut}


def strike(comp, body, plane, origin, size_map,
           prefix="lk", name="Strike", ev=None, flip=False):
    """CUT the strike plate recess and place a visual strike body.

    Same pattern as lock_mortise but using strike plate dimensions.

    Args:
        comp: Component.
        body: Lid or receiving board body.
        plane: Sketch plane on the board face.
        origin: (x_expr, y_expr, z_expr) — corner of strike plate.
        size_map: {axis: expr, axis: expr} — two face dimensions.
        prefix: Parameter prefix.
        name: Feature name prefix.
        ev: Evaluator.
        flip: Extrude in negative direction.

    Returns:
        Dict with "strike_ext", "strike_body", "cut".
    """
    if ev is None:
        ev = sp._make_ev()
    p = prefix

    sk, prof = sp.sketch_rect_model(comp, plane, origin, size_map,
                                    f"{name}_Sk", ev)
    strike_ext = sp.ext_op(comp, prof, f"{p}_strike_t", NEW, None,
                           f"{name}_Body", flip=flip)
    strike_body = strike_ext.bodies.item(0)
    strike_body.name = f"{name}_Body"

    cut = sp.combine(body, strike_body, CUT, True, f"{name}_Mort")

    return {"strike_ext": strike_ext, "strike_body": strike_body, "cut": cut}


def _probe_signs(sk):
    """Return (h_axis, v_axis, h_sign, v_sign) for a sketch."""
    h_ax, v_ax = sp.probe_sketch_axes(sk)
    P = Point3D
    sc = sk.modelToSketchSpace(P.create(0, 0, 0))
    delta = {"x": P.create(1, 0, 0), "y": P.create(0, 1, 0),
             "z": P.create(0, 0, 1)}
    sd_h = sk.modelToSketchSpace(delta[h_ax])
    sd_v = sk.modelToSketchSpace(delta[v_ax])
    h_sign = 1 if (sd_h.x - sc.x) > 0 else -1
    v_sign = 1 if (sd_v.y - sc.y) > 0 else -1
    return h_ax, v_ax, h_sign, v_sign
