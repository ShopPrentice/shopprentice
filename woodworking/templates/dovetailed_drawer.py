"""Dovetailed drawer box template.

Traditional high-quality drawer construction:
- Half-blind dovetails at front (hides end grain on face)
- Through dovetails at back (visible from behind — shows craftsmanship)
- Bottom panel in grooves
- Optional taller front board (lip above sides)

Usage:
    from woodworking.templates import dovetailed_drawer

    dovetailed_drawer.define_params(params, prefix="dd",
        drawer_w="22 in", drawer_d="14 in", drawer_h="4 in",
        front_thick="0.75 in", side_thick="0.5 in", ...)

    result = dovetailed_drawer.build(comp, prefix="dd", ev=ctx.ev)
    # result = {"front": body, "back": body, "left": body, "right": body,
    #           "bottom": body, "all_bodies": [...]}
"""

import adsk.core
import adsk.fusion

from helpers import sp
from woodworking.templates import dovetail
from woodworking.templates import half_blind_dovetail

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation

METADATA = {
    "name": "dovetailed_drawer",
    "category": "sub_assembly",
    "description": "Drawer box with half-blind front and through back dovetails",
    "best_for": ["fine furniture drawers", "traditional dressers", "jewelry chests"],
    "composes": ["half_blind_dovetail (front corners)", "dovetail (back corners)"],
    "params": {
        "dd_w": "Drawer width (X)",
        "dd_d": "Drawer depth (Y)",
        "dd_h": "Drawer side/back height (Z)",
        "dd_fh": "Front height (Z), >= dd_h for lip",
        "dd_ft": "Front board thickness (thicker for half-blind)",
        "dd_st": "Side and back board thickness",
        "dd_bt": "Bottom panel thickness",
    },
}


def define_params(params, prefix="dd",
                  drawer_w="22 in", drawer_d="14 in", drawer_h="4 in",
                  front_h=None,
                  front_thick="0.75 in", side_thick="0.5 in",
                  bottom_thick="0.25 in",
                  bg_depth="0.25 in", bg_up="0.25 in",
                  dt_angle="8 deg", dt_tail_w="0.75 in",
                  front_tail_count="3", back_tail_count="3",
                  hbd_lap="0.25 in",
                  x_offset="0 in", z_offset="0 in"):
    """Define all dovetailed drawer parameters.

    Args:
        params: design.userParameters
        prefix: Parameter name prefix.
        drawer_w: Overall width (X).
        drawer_d: Overall depth (Y).
        drawer_h: Side/back height (Z).
        front_h: Front height expression. None = same as drawer_h.
        front_thick: Front board thickness (thicker for half-blind).
        side_thick: Side and back board thickness.
        bottom_thick: Bottom panel thickness.
        bg_depth: Bottom groove depth into boards.
        bg_up: Groove height above drawer floor.
        dt_angle: Dovetail angle (shared front and back).
        dt_tail_w: Tail width (shared front and back).
        front_tail_count: Number of tails at front.
        back_tail_count: Number of tails at back.
        hbd_lap: Half-blind lap (outer face material on front).
        x_offset: X offset expression for building in place (e.g. inside a case).
        z_offset: Z offset expression for building in place.

    Returns:
        Dict of parameter names.
    """
    VI = adsk.core.ValueInput.createByString
    p = prefix

    # Offset params (for building drawer in place inside a case)
    params.add(f"{p}_xo", VI(x_offset), "in", "X offset")
    params.add(f"{p}_zo", VI(z_offset), "in", "Z offset")

    # Drawer dimensions
    params.add(f"{p}_w", VI(drawer_w), "in", "Drawer width")
    params.add(f"{p}_d", VI(drawer_d), "in", "Drawer depth")
    params.add(f"{p}_h", VI(drawer_h), "in", "Drawer height (sides)")
    if front_h is not None:
        params.add(f"{p}_fh", VI(front_h), "in", "Front height")
    else:
        params.add(f"{p}_fh", VI(f"{p}_h"), "in", "Front height")

    # Board thicknesses
    params.add(f"{p}_ft", VI(front_thick), "in", "Front thickness")
    params.add(f"{p}_st", VI(side_thick), "in", "Side/back thickness")
    params.add(f"{p}_bt", VI(bottom_thick), "in", "Bottom thickness")

    # Groove params
    params.add(f"{p}_bgd", VI(bg_depth), "in", "Bottom groove depth")
    params.add(f"{p}_bgu", VI(bg_up), "in", "Bottom groove offset")

    # Derived: side depth
    params.add(f"{p}_sd",
               VI(f"{p}_d - {p}_ft - {p}_st"),
               "in", "Side depth (derived)")

    # Half-blind dovetail params (front)
    half_blind_dovetail.define_params(params, prefix=f"hbd_{p}",
        angle=dt_angle, tail_w=dt_tail_w,
        tail_count=front_tail_count,
        joint_h_expr=f"{p}_h",
        pin_thick_expr=f"{p}_ft",
        lap=hbd_lap)

    # Through dovetail params (back)
    dovetail.define_params(params, prefix=f"dt_{p}",
        angle=dt_angle, tail_w=dt_tail_w,
        tail_count=back_tail_count,
        joint_h_expr=f"{p}_h",
        thick_expr=f"{p}_st")

    return {
        "w": f"{p}_w", "d": f"{p}_d", "h": f"{p}_h",
        "fh": f"{p}_fh", "ft": f"{p}_ft", "st": f"{p}_st",
        "bt": f"{p}_bt", "sd": f"{p}_sd",
    }


def build(comp, prefix="dd", ev=None):
    """Build a dovetailed drawer box.

    Creates 5 bodies: front, back, left, right, bottom.
    Grooves are cut before dovetails (clean stopped grooves at corners).
    Half-blind dovetails at front, through dovetails at back.

    Args:
        comp: Component to build in.
        prefix: Parameter prefix (from define_params).
        ev: Evaluator function.

    Returns:
        Dict with body references and feature info.
    """
    if ev is None:
        ev = sp._make_ev()

    p = prefix

    # ── Offset shorthand ──
    xo = f"{p}_xo"
    zo = f"{p}_zo"

    # ── Construction planes ──
    bg_pl = sp.off_plane(comp, comp.xYConstructionPlane,
                          f"{zo} + {p}_bgu", f"{p}_BG_Pl")

    # Offset YZ plane for left side and dovetail sketches
    left_pl = sp.off_plane(comp, comp.yZConstructionPlane,
                            xo, f"{p}_LeftPl")

    # ── Front board (thicker, possibly taller) ──
    _, pr = sp.sketch_rect_model(comp, comp.xZConstructionPlane,
        (xo, "0 in", zo),
        {"x": f"{p}_w", "z": f"{p}_fh"}, f"{p}_Front_Sk", ev)
    front = sp.ext_new(comp, pr, f"{p}_ft", f"{p}_Front").bodies.item(0)
    front.name = f"{p}_Front"

    # ── Back board ──
    back_pl = sp.off_plane(comp, comp.xZConstructionPlane,
                            f"{p}_d - {p}_st", f"{p}_Back_Pl")
    _, pr = sp.sketch_rect_model(comp, back_pl,
        (xo, f"{p}_d - {p}_st", zo),
        {"x": f"{p}_w", "z": f"{p}_h"}, f"{p}_Back_Sk", ev)
    back = sp.ext_new(comp, pr, f"{p}_st", f"{p}_Back").bodies.item(0)
    back.name = f"{p}_Back"

    # ── Midplanes ──
    x_mid = sp.off_plane(comp, comp.yZConstructionPlane,
                          f"{xo} + {p}_w / 2", f"{p}_XMid")
    y_mid = sp.off_plane(comp, comp.xZConstructionPlane,
                          f"{p}_d / 2", f"{p}_YMid")

    # ── Left side (thinner, narrower in Y) ──
    _, pr = sp.sketch_rect_model(comp, left_pl,
        (xo, f"{p}_ft", zo),
        {"y": f"{p}_sd", "z": f"{p}_h"}, f"{p}_Left_Sk", ev)
    left = sp.ext_new(comp, pr, f"{p}_st", f"{p}_Left").bodies.item(0)
    left.name = f"{p}_Left"

    # ── Right side (mirror of left) ──
    right_mir = sp.mirror_body(comp, left, x_mid, f"{p}_RightMir")
    right = right_mir.bodies.item(0)
    right.name = f"{p}_Right"

    print(f"  Boards: front({p}_fh), back({p}_h), left, right, "
          f"front_thick={ev(f'{p}_ft')/2.54:.3f}in, "
          f"side_thick={ev(f'{p}_st')/2.54:.3f}in")

    # ── Bottom panel ──
    # Panel extends bgd into all 4 boards (front, back, left, right),
    # creating grooves via CUT — "if it fits, it cuts."
    _, pr = sp.sketch_rect_model(comp, bg_pl,
        (f"{xo} + {p}_st - {p}_bgd",
         f"{p}_ft - {p}_bgd",
         f"{zo} + {p}_bgu"),
        {"x": f"{p}_w - 2 * {p}_st + 2 * {p}_bgd",
         "y": f"{p}_d - {p}_ft - {p}_st + 2 * {p}_bgd"},
        f"{p}_Bottom_Sk", ev)
    bottom = sp.ext_new(comp, pr, f"{p}_bt", f"{p}_Bottom").bodies.item(0)
    bottom.name = f"{p}_Bottom"

    # ── Bottom grooves — CUT all 4 boards with bottom panel as tool ──
    sp.combine(front, [bottom], CUT, True, f"{p}_BGF")
    sp.combine(back, [bottom], CUT, True, f"{p}_BGB")
    sp.combine(left, [bottom], CUT, True, f"{p}_BGL")
    sp.combine(right, [bottom], CUT, True, f"{p}_BGR")

    print(f"  Bottom panel + grooves done")

    # ── Half-blind dovetails at front (2-corner: FL + FR) ──
    hbd_result = half_blind_dovetail.box(
        comp, front, left,
        x_mid, y_mid,
        pin_thick_expr=f"{p}_ft",
        tail_thick_expr=f"{p}_st",
        right=right, back=None,
        prefix=f"hbd_{p}", name=f"{p}_HBD", ev=ev,
        fl_plane=left_pl,
        front_expr="0 in",
        joint_base_expr=zo)

    print(f"  Half-blind dovetails at front (FL + FR)")

    # ── Through dovetails at back (2-corner: BL + BR) ──
    # thick_dir=-1: wide at back outer face, narrow at inner face
    dt_result = dovetail.box(
        comp, back, left,
        x_mid, y_mid, thick_expr=f"{p}_st",
        right=right, back=None,
        prefix=f"dt_{p}", name=f"{p}_DT", ev=ev,
        fl_plane=left_pl,
        front_expr=f"{p}_d",
        thick_dir=-1,
        joint_base_expr=zo)

    print(f"  Through dovetails at back (BL + BR)")

    all_bodies = [front, back, left, right, bottom]

    return {
        "front": front, "back": back,
        "left": left, "right": right,
        "bottom": bottom,
        "all_bodies": all_bodies,
        "x_mid": x_mid, "y_mid": y_mid,
        "hbd_result": hbd_result,
        "dt_result": dt_result,
    }


def pattern(comp, bodies, count_expr, pitch_expr, ev=None):
    """Pattern drawer bodies along Z for multiple drawers.

    Args:
        comp: Component.
        bodies: List of bodies to pattern.
        count_expr: Number of drawers expression.
        pitch_expr: Vertical spacing expression.
        ev: Evaluator function.

    Returns:
        RectangularPatternFeature or None if count <= 1.
    """
    if ev is None:
        ev = sp._make_ev()

    n = int(ev(count_expr))
    if n <= 1:
        return None

    coll = adsk.core.ObjectCollection.create()
    for b in bodies:
        coll.add(b)

    VI = adsk.core.ValueInput.createByString
    inp = comp.features.rectangularPatternFeatures.createInput(
        coll, comp.zConstructionAxis,
        VI(count_expr), VI(pitch_expr),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    inp.quantityTwo = VI("1")
    pat = comp.features.rectangularPatternFeatures.add(inp)
    pat.name = "DDr_Pat"
    return pat
