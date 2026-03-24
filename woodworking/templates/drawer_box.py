"""Drawer box sub-assembly template.

Creates a complete drawer box: 4 boards (front, back, left, right) +
bottom panel + bottom grooves + optional pull groove. Designed for
stacking in a case via body_pattern.

Usage:
    from woodworking.templates import drawer_box

    # Define drawer parameters
    drawer_box.define_params(params,
        n_drawers="3", front_thick="0.75 in", side_thick="0.5 in",
        bottom_thick="0.25 in", gap="0.125 in",
        case_w_expr="case_w", case_d_expr="case_d",
        case_h_expr="case_h", ...)

    # Build the drawer box
    result = drawer_box.build(drawers_comp, ev=ctx.ev)
    # result = {"front": body, "back": body, "left": body, "right": body,
    #           "bottom": body, "all_bodies": [...], "base_plane": pl}

    # Pattern multiple drawers
    drawer_box.pattern(drawers_comp, result["all_bodies"],
                       count_expr="n_drawers", pitch_expr="drawer_pitch")
"""

import adsk.core
import adsk.fusion

from helpers import sp

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation

METADATA = {
    "name": "drawer_box",
    "category": "sub_assembly",
    "description": "Complete drawer box with 4 boards, bottom panel, and grooves",
    "best_for": ["dressers", "cabinets", "desks", "nightstands"],
    "composes": ["dovetail (corners)", "domino (optional)"],
    "params": {
        "n_drawers": "Number of drawers (count)",
        "drawer_w": "Derived: inner case width minus gaps",
        "drawer_h": "Derived: available height / count",
        "drawer_d": "Derived: case depth minus back minus gaps",
        "drawer_front_thick": "Front board thickness",
        "drawer_side_thick": "Side/back board thickness",
        "drawer_bottom_thick": "Bottom panel thickness",
        "drawer_gap": "Gap between drawer and case on all sides",
    },
}


def define_params(params, n_drawers="3",
                  front_thick="0.75 in", side_thick="0.5 in",
                  bottom_thick="0.25 in", gap="0.125 in",
                  bg_depth="0.25 in", bg_up="0.25 in",
                  pull_depth="0.375 in", pull_h="0.75 in",
                  case_w_expr="case_w", case_d_expr="case_d",
                  board_thick_expr="board_thick",
                  back_thick_expr="back_thick",
                  usable_h_expr="case_h - kick_h - bot_thick - top_thick"):
    """Define all drawer parameters with proper derivations.

    Args:
        params: design.userParameters
        n_drawers: Number of drawers.
        front_thick: Front board thickness.
        side_thick: Side and back board thickness.
        bottom_thick: Bottom panel thickness.
        gap: Gap between drawer and case.
        bg_depth: Bottom groove depth into boards.
        bg_up: Height of groove above drawer floor.
        pull_depth: Pull groove depth.
        pull_h: Pull groove height.
        case_w_expr: Case inner width reference.
        case_d_expr: Case depth reference.
        board_thick_expr: Case side board thickness.
        back_thick_expr: Case back board thickness.
        usable_h_expr: Available vertical space for drawers.

    Returns:
        Dict of parameter names.
    """
    VI = adsk.core.ValueInput.createByString

    # Independent
    params.add("n_drawers", VI(n_drawers), "", "Number of drawers")
    params.add("drawer_gap", VI(gap), "in", "Drawer gap")
    params.add("drawer_front_thick", VI(front_thick), "in", "Drawer front thickness")
    params.add("drawer_side_thick", VI(side_thick), "in", "Drawer side/back thickness")
    params.add("drawer_bottom_thick", VI(bottom_thick), "in", "Drawer bottom thickness")
    params.add("bg_depth", VI(bg_depth), "in", "Bottom groove depth")
    params.add("bg_up", VI(bg_up), "in", "Bottom groove height above floor")
    params.add("pull_depth", VI(pull_depth), "in", "Pull groove depth")
    params.add("pull_h", VI(pull_h), "in", "Pull groove height")

    # Derived
    inner_w = f"{case_w_expr} - 2 * {board_thick_expr}"
    params.add("inner_w", VI(inner_w), "in", "Case inner width")
    params.add("usable_h", VI(usable_h_expr), "in", "Usable height for drawers")
    params.add("drawer_h",
               VI("(usable_h - (n_drawers + 1) * drawer_gap) / n_drawers"),
               "in", "Drawer height")
    params.add("drawer_w",
               VI("inner_w - 2 * drawer_gap"),
               "in", "Drawer width")
    params.add("drawer_d",
               VI(f"{case_d_expr} - {back_thick_expr} - 2 * drawer_gap"),
               "in", "Drawer depth")
    params.add("drawer_pitch",
               VI("drawer_h + drawer_gap"),
               "in", "Drawer pitch (height + gap)")

    return {
        "n_drawers": "n_drawers", "drawer_gap": "drawer_gap",
        "drawer_h": "drawer_h", "drawer_w": "drawer_w",
        "drawer_d": "drawer_d", "drawer_pitch": "drawer_pitch",
        "drawer_front_thick": "drawer_front_thick",
        "drawer_side_thick": "drawer_side_thick",
        "drawer_bottom_thick": "drawer_bottom_thick",
        "bg_depth": "bg_depth", "bg_up": "bg_up",
        "pull_depth": "pull_depth", "pull_h": "pull_h",
    }


def build(comp, z_base_expr="kick_h + bot_thick + drawer_gap",
          x_origin_expr="board_thick + drawer_gap",
          ev=None, include_pull=True):
    """Build a single drawer box template (4 boards + bottom + grooves).

    Args:
        comp: Drawers component.
        z_base_expr: Z coordinate of the first drawer's bottom.
        x_origin_expr: X origin (left case wall inner face + gap).
        ev: Evaluator function.
        include_pull: If True, adds a pull groove on the front board bottom.

    Returns:
        Dict with body references and construction planes.
    """
    if ev is None:
        ev = sp._make_ev()

    # ── Construction planes ──
    d_pl = sp.off_plane(comp, comp.xYConstructionPlane,
                        z_base_expr, "Dr_Pl")
    bg_pl = sp.off_plane(comp, comp.xYConstructionPlane,
                         f"{z_base_expr} + bg_up", "DrBG_Pl")

    # ── Front board ──
    _, pr = sp.sketch_rect(comp, d_pl,
                           x_origin_expr, "0 in",
                           "drawer_w", "drawer_front_thick",
                           "DrFront_Sk", ev=ev)
    front = sp.ext_new(comp, pr, "drawer_h", "DrFront").bodies.item(0)
    front.name = "Dr_Front"

    # ── Back board ──
    _, pr = sp.sketch_rect(comp, d_pl,
                           x_origin_expr, "drawer_d - drawer_side_thick",
                           "drawer_w", "drawer_side_thick",
                           "DrBack_Sk", ev=ev)
    back = sp.ext_new(comp, pr, "drawer_h", "DrBack").bodies.item(0)
    back.name = "Dr_Back"

    # ── Left side ──
    _, pr = sp.sketch_rect(comp, d_pl,
                           x_origin_expr, "0 in",
                           "drawer_side_thick", "drawer_d",
                           "DrLeft_Sk", ev=ev)
    left = sp.ext_new(comp, pr, "drawer_h", "DrLeft").bodies.item(0)
    left.name = "Dr_Left"

    # ── Right side ──
    _, pr = sp.sketch_rect(comp, d_pl,
                           f"{x_origin_expr} + drawer_w - drawer_side_thick",
                           "0 in",
                           "drawer_side_thick", "drawer_d",
                           "DrRight_Sk", ev=ev)
    right = sp.ext_new(comp, pr, "drawer_h", "DrRight").bodies.item(0)
    right.name = "Dr_Right"

    # ── Bottom panel ──
    zbg = f"{z_base_expr} + bg_up"
    _, pr = sp.sketch_rect_model(comp, bg_pl,
        (f"{x_origin_expr} + drawer_side_thick - bg_depth",
         "drawer_front_thick - bg_depth",
         zbg),
        {"x": "drawer_w - 2 * drawer_side_thick + 2 * bg_depth",
         "y": "drawer_d - drawer_front_thick - drawer_side_thick + 2 * bg_depth"},
        "DrBottom_Sk", ev=ev)
    bottom = sp.ext_new(comp, pr, "drawer_bottom_thick", "DrBottom").bodies.item(0)
    bottom.name = "Dr_Bottom"

    # ── Bottom grooves (CUT into all 4 boards) ──
    # Front groove
    _, pr = sp.sketch_rect_model(comp, bg_pl,
        (x_origin_expr, "drawer_front_thick - bg_depth", zbg),
        {"x": "drawer_w", "y": "bg_depth"},
        "DrBGF_Sk", ev=ev)
    sp.ext_op(comp, pr, "drawer_bottom_thick", CUT, front, "DrBGF")

    # Back groove
    _, pr = sp.sketch_rect_model(comp, bg_pl,
        (x_origin_expr, "drawer_d - drawer_side_thick", zbg),
        {"x": "drawer_w", "y": "bg_depth"},
        "DrBGB_Sk", ev=ev)
    sp.ext_op(comp, pr, "drawer_bottom_thick", CUT, back, "DrBGB")

    # Left groove
    _, pr = sp.sketch_rect_model(comp, bg_pl,
        (f"{x_origin_expr} + drawer_side_thick - bg_depth",
         "drawer_front_thick", zbg),
        {"x": "bg_depth",
         "y": "drawer_d - drawer_front_thick - drawer_side_thick"},
        "DrBGL_Sk", ev=ev)
    sp.ext_op(comp, pr, "drawer_bottom_thick", CUT, left, "DrBGL")

    # Right groove
    _, pr = sp.sketch_rect_model(comp, bg_pl,
        (f"{x_origin_expr} + drawer_w - drawer_side_thick",
         "drawer_front_thick", zbg),
        {"x": "bg_depth",
         "y": "drawer_d - drawer_front_thick - drawer_side_thick"},
        "DrBGR_Sk", ev=ev)
    sp.ext_op(comp, pr, "drawer_bottom_thick", CUT, right, "DrBGR")

    # ── Pull groove (optional) ──
    if include_pull:
        _, pr = sp.sketch_rect_model(comp, d_pl,
            (x_origin_expr, "-pull_depth", z_base_expr),
            {"x": "drawer_w", "y": "pull_depth"},
            "Pull_Sk", ev=ev)
        sp.ext_op(comp, pr, "pull_h", CUT, front, "PullGroove")

    all_bodies = [front, back, left, right, bottom]

    return {
        "front": front, "back": back,
        "left": left, "right": right,
        "bottom": bottom,
        "all_bodies": all_bodies,
        "base_plane": d_pl,
        "bg_plane": bg_pl,
    }


def pattern(comp, bodies, count_expr="n_drawers", pitch_expr="drawer_pitch",
            ev=None):
    """Pattern drawer bodies along Z for multiple drawers.

    Only call this AFTER all joinery (dovetails, etc.) is applied to the
    template drawer. The pattern replicates all 5 bodies (and their
    feature history) upward.

    Args:
        comp: Drawers component.
        bodies: List of drawer bodies to pattern [front, back, left, right, bottom].
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
    pat.name = "Dr_Pat"
    return pat
