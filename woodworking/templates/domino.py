"""Domino (loose tenon) joint template.

Creates Festool-style domino joints between two mating bodies.
The void body is a stadium shape (two semicircles + straight sides)
that straddles the mating interface, CUTting into both pieces.

Orientation rule: the wide face of the domino must always be parallel to the
board surface. Choose long_axis so the domino lies flat in the board plane.

Three primary use cases:
1. M&T replacement (four_corners) — leg-to-seat, post-to-top
2. Edge jointing (grid) — aligning boards side-by-side
3. Case/panel joints (grid) — side-to-back, shelf-to-back T-joints

Usage:
    from woodworking.templates import domino

    # M&T replacement — 4 symmetric dominos (legs to seat)
    domino.four_corners(comp, seat_pl,
                        center=("leg_inset_x", "leg_inset_y", "seat_z"),
                        long_axis="x", long_expr="dm_w", short_expr="dm_t",
                        depth_expr="dm_d", top_body=seat,
                        leg_bodies=[leg_nl, leg_nr, leg_fl, leg_fr],
                        x_mid=XMid, y_mid=YMid, name="DM", ev=ctx.ev)

    # Edge jointing — boards flat on XY, long_axis="x" (parallel to surface)
    domino.grid(comp, joint_pl, start=("x0", "y0", "z0"),
                step_axis="x", step_expr="dm_sp", count_expr="dm_count",
                long_axis="x", long_expr="dm_w", short_expr="dm_t",
                depth_expr="dm_d", body_a=left, body_b=right,
                name="EJ", ev=ctx.ev)

    # Case joint — side-to-back T-joint, long_axis="z" (parallel to surfaces)
    domino.grid(comp, case_pl, start=("side_t/2", "y0", "z0"),
                step_axis="z", step_expr="dm_sp", count_expr="dm_count",
                long_axis="z", long_expr="dm_w", short_expr="dm_t",
                depth_expr="dm_d", body_a=side, body_b=back,
                name="CB", ev=ctx.ev)
"""

import adsk.core
import adsk.fusion
import math

from helpers import af

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation

METADATA = {
    "name": "domino",
    "category": "joinery",
    "description": "Festool-style loose tenon joint using stadium-shaped void bodies",
    "best_for": ["M&T replacement (leg-to-seat, post-to-top)",
                 "edge jointing (board alignment)",
                 "case/panel joints (side-to-back, shelf-to-back)"],
    "not_for": ["visible decorative joints", "end-grain joints"],
    "standard_sizes": {
        "4mm":  {"short": "4 mm",  "long": "20 mm", "depth": "12 mm"},
        "5mm":  {"short": "5 mm",  "long": "30 mm", "depth": "15 mm"},
        "6mm":  {"short": "6 mm",  "long": "40 mm", "depth": "15 mm"},
        "8mm":  {"short": "8 mm",  "long": "40 mm", "depth": "20 mm"},
        "10mm": {"short": "10 mm", "long": "50 mm", "depth": "25 mm"},
        "12mm": {"short": "12 mm", "long": "60 mm", "depth": "28 mm"},
        "14mm": {"short": "14 mm", "long": "70 mm", "depth": "35 mm"},
    },
    "params": {
        "short": "Cutter diameter / narrow dimension",
        "long": "Lateral dimension (across grain)",
        "depth": "Penetration per side (half the domino length)",
    },
}


def single(comp, plane, center, long_axis, long_expr, short_expr,
           depth_expr, body_a=None, body_b=None, name="DM", ev=None,
           use_model_coords=True, cut=True):
    """Create a single domino joint between two bodies.

    Sketches a stadium-shaped void body, extrudes symmetrically about the
    mating interface plane, then CUTs into both bodies with keepTool=True.

    Args:
        comp: Component to create features in (usually root).
        plane: Construction plane at the mating interface.
        center: (x_expr, y_expr, z_expr) — center of the domino in model space.
        long_axis: 'x', 'y', or 'z' — model axis for the long dimension.
        long_expr: Long dimension expression (e.g. "dm_w").
        short_expr: Short dimension expression (e.g. "dm_t").
        depth_expr: Depth per side expression (e.g. "dm_d").
        body_a: First body to CUT into (ignored if cut=False).
        body_b: Second body to CUT into (ignored if cut=False).
        name: Feature name prefix.
        ev: Evaluator function.
        use_model_coords: If True, use sketch_slot_model (handles axis flips).
            If False, use sketch_slot with center as sketch-space (cx, cy) only.
        cut: If True (default), CUT into body_a and body_b. If False, create
            geometry only — use for pattern-first, CUT-later workflows.

    Returns:
        The domino void body (BRepBody).
    """
    if ev is None:
        ev = af._make_ev()

    if use_model_coords:
        sk, prof = af.sketch_slot_model(
            comp, plane, center, long_axis,
            long_expr, short_expr, name=f"{name}_Sk", ev=ev)
    else:
        # center is (cx_expr, cy_expr) in sketch space, long_axis ignored
        vertical = (long_axis == "v" or long_axis == "vertical")
        sk, prof = af.sketch_slot(
            comp, plane, center[0], center[1],
            long_expr, short_expr, vertical,
            name=f"{name}_Sk", ev=ev)

    ext = af.ext_new_sym(comp, prof, depth_expr, f"{name}")
    void_body = ext.bodies.item(0)
    void_body.name = name

    if cut:
        af.combine(comp, body_a, void_body, CUT, True, f"{name}_CutA")
        af.combine(comp, body_b, void_body, CUT, True, f"{name}_CutB")

    return void_body


def grid(comp, plane, start, step_axis, step_expr, count_expr,
         long_axis, long_expr, short_expr, depth_expr,
         body_a=None, body_b=None, name="DM", ev=None, cut=True):
    """Create a grid of dominos along a joint line.

    Creates one template void, then uses body_pattern to replicate along
    the step axis. Ghost bodies from later CUT operations are harmless.

    Args:
        comp: Component to create features in.
        plane: Construction plane at the mating interface.
        start: (x_expr, y_expr, z_expr) — center of the FIRST domino.
        step_axis: 'x', 'y', or 'z' — axis to step along.
        step_expr: Spacing expression (e.g. "dm_sp").
        count_expr: Count expression (e.g. "dm_count"). Parametric.
        long_axis: Model axis for the long dimension of each slot.
        long_expr, short_expr, depth_expr: Dimension expressions.
        body_a, body_b: Bodies to CUT into (ignored if cut=False).
        name: Feature name prefix.
        ev: Evaluator function.
        cut: If True (default), bulk CUT all voids into body_a and body_b.
            If False, create geometry only.

    Returns:
        List of void bodies (template + pattern copies).
    """
    if ev is None:
        ev = af._make_ev()

    # Build ONE template void at start position
    sk, prof = af.sketch_slot_model(
        comp, plane, start, long_axis,
        long_expr, short_expr, name=f"{name}_Sk", ev=ev)
    ext = af.ext_new_sym(comp, prof, depth_expr, f"{name}")
    template = ext.bodies.item(0)
    template.name = f"{name}_0"

    # Pattern along step axis (parametric count)
    count = int(ev(count_expr))
    void_bodies = [template]
    if count > 1:
        axis_map = {"x": comp.xConstructionAxis,
                     "y": comp.yConstructionAxis,
                     "z": comp.zConstructionAxis}
        pat = af.body_pattern(comp, template, axis_map[step_axis],
                               count_expr, step_expr, f"{name}_Pat")
        for i in range(pat.bodies.count):
            void_bodies.append(pat.bodies.item(i))

    # Bulk CUT all voids into target bodies
    if cut and void_bodies:
        af.combine(comp, body_a, void_bodies, CUT, True, f"{name}_CutA")
        if body_b is not None and body_b != body_a:
            af.combine(comp, body_b, void_bodies, CUT, True, f"{name}_CutB")

    return void_bodies


def _bodies_overlap_bbox(body_a, body_b):
    """Compute the bounding box overlap of two bodies.

    Returns (min_x, min_y, min_z, max_x, max_y, max_z) of the overlap region,
    or None if they don't overlap.
    """
    bb_a = body_a.boundingBox
    bb_b = body_b.boundingBox

    min_x = max(bb_a.minPoint.x, bb_b.minPoint.x)
    min_y = max(bb_a.minPoint.y, bb_b.minPoint.y)
    min_z = max(bb_a.minPoint.z, bb_b.minPoint.z)
    max_x = min(bb_a.maxPoint.x, bb_b.maxPoint.x)
    max_y = min(bb_a.maxPoint.y, bb_b.maxPoint.y)
    max_z = min(bb_a.maxPoint.z, bb_b.maxPoint.z)

    # Check for valid overlap (with tolerance for touching faces)
    TOL = 0.01  # 0.1mm
    if max_x - min_x < -TOL or max_y - min_y < -TOL or max_z - min_z < -TOL:
        return None

    return (min_x, min_y, min_z, max_x, max_y, max_z)


def between(comp, plane, body_a, body_b, interface_axis,
            long_axis, long_expr, short_expr, depth_expr,
            count=2, name="DM", ev=None, cut=True):
    """Create dominos at the mating area between two bodies.

    Auto-computes where body_a and body_b overlap in the interface plane,
    then evenly spaces dominos within that overlap region. This avoids
    placing dominos outside the actual mating area (e.g., a narrow front
    rail meeting a full-height divider — dominos go in the rail zone only).

    Args:
        comp: Component to create features in.
        plane: Construction plane at the mating interface.
        body_a, body_b: The two bodies being joined.
        interface_axis: 'x', 'y', or 'z' — axis perpendicular to the interface.
            This is the axis the domino depth extends along.
        long_axis: Model axis for the long dimension of each slot.
        long_expr, short_expr, depth_expr: Dimension expressions.
        count: Number of dominos (int). Default 2.
        name: Feature name prefix.
        ev: Evaluator function.
        cut: If True, CUT into both bodies.

    Returns:
        List of void bodies.
    """
    if ev is None:
        ev = af._make_ev()

    overlap = _bodies_overlap_bbox(body_a, body_b)
    if overlap is None:
        print(f"WARNING: {name} — bodies don't overlap, skipping dominos")
        return []

    min_x, min_y, min_z, max_x, max_y, max_z = overlap

    # Determine the step axis (the axis to space dominos along)
    # It's the axis in the interface plane that ISN'T the long_axis
    axes = {"x", "y", "z"}
    axes.discard(interface_axis)
    axes.discard(long_axis)
    if axes:
        step_axis = axes.pop()
    else:
        # long_axis == one of the remaining — step along the other
        step_axis = long_axis  # fallback

    # Compute spacing within the overlap region along step_axis
    axis_map = {"x": (min_x, max_x), "y": (min_y, max_y), "z": (min_z, max_z)}
    step_min, step_max = axis_map[step_axis]
    step_range = step_max - step_min

    # Interface center (where the domino is placed along interface_axis)
    iface_min, iface_max = axis_map[interface_axis]
    iface_center = (iface_min + iface_max) / 2

    # Long axis center
    long_min, long_max = axis_map[long_axis]
    long_center = (long_min + long_max) / 2

    # Evenly space dominos with margins from edges
    dm_long = ev(long_expr) if isinstance(long_expr, str) else long_expr
    margin = dm_long / 2 + 0.2  # half a domino width + small clearance

    usable = step_range - 2 * margin
    if usable <= 0 or count < 1:
        # Not enough room — place one at center
        count = 1

    if count == 1:
        spacing = 0
        first = (step_min + step_max) / 2
    else:
        spacing = usable / (count - 1)
        first = step_min + margin

    # Build dominos
    void_bodies = []
    for i in range(count):
        step_pos = first + i * spacing

        # Assemble the (x, y, z) position
        pos = [0.0, 0.0, 0.0]
        axis_idx = {"x": 0, "y": 1, "z": 2}
        pos[axis_idx[interface_axis]] = iface_center
        pos[axis_idx[long_axis]] = long_center
        pos[axis_idx[step_axis]] = step_pos

        sk, prof = af.sketch_slot_model(
            comp, plane, (f"{pos[0]} cm", f"{pos[1]} cm", f"{pos[2]} cm"),
            long_axis, long_expr, short_expr,
            name=f"{name}_{i}_Sk", ev=ev)
        ext = af.ext_new_sym(comp, prof, depth_expr, f"{name}_{i}")
        void = ext.bodies.item(0)
        void.name = f"{name}_{i}"
        void_bodies.append(void)
        sk.isVisible = False

    # Bulk CUT into both bodies
    if cut and void_bodies:
        af.combine(comp, body_a, void_bodies, CUT, True, f"{name}_CutA")
        if body_b is not None and body_b != body_a:
            af.combine(comp, body_b, void_bodies, CUT, True, f"{name}_CutB")

    print(f">>> {name}: {len(void_bodies)} domino(s) in mating area "
          f"({step_axis}=[{step_min:.1f},{step_max:.1f}])")
    return void_bodies


def four_corners(comp, plane, center, long_axis, long_expr, short_expr,
                 depth_expr, top_body, leg_bodies, x_mid, y_mid,
                 name="DM", ev=None):
    """Create 4 symmetric dominos for leg-to-seat/top joints.

    Builds one domino at the near-left position, mirrors across YMid → NR,
    mirrors both across XMid → FL, FR. Then CUTs all into the top and
    each into its respective leg.

    Args:
        comp: Component (usually root).
        plane: Construction plane at the mating interface (e.g. seat bottom).
        center: (x_expr, y_expr, z_expr) — near-left domino center.
        long_axis: Model axis for long dimension.
        long_expr, short_expr, depth_expr: Dimension expressions.
        top_body: The seat/top body to CUT all 4 into.
        leg_bodies: [near_left, near_right, far_left, far_right] — 4 leg bodies.
        x_mid: X midplane (ConstructionPlane) for mirror.
        y_mid: Y midplane (ConstructionPlane) for mirror.
        name: Feature name prefix.
        ev: Evaluator function.

    Returns:
        List of 4 void bodies [NL, NR, FL, FR].
    """
    if ev is None:
        ev = af._make_ev()

    # 1. Build near-left domino
    sk, prof = af.sketch_slot_model(
        comp, plane, center, long_axis,
        long_expr, short_expr, name=f"{name}_NL_Sk", ev=ev)
    ext = af.ext_new_sym(comp, prof, depth_expr, f"{name}_NL")
    nl_body = ext.bodies.item(0)
    nl_body.name = f"{name}_NL"

    # 2. Mirror NL → NR across XMid (flips X: left → right)
    mir_nr = af.mirror_bodies(comp, [nl_body], x_mid, f"{name}_NR_Mir")
    nr_body = mir_nr.bodies.item(0)
    nr_body.name = f"{name}_NR"
    nl_body = _find_body(comp, f"{name}_NL")

    # 3. Mirror NL+NR → FL+FR across YMid (flips Y: near → far)
    mir_far = af.mirror_bodies(comp, [nl_body, nr_body], y_mid, f"{name}_Far_Mir")
    fl_body = mir_far.bodies.item(0)
    fr_body = mir_far.bodies.item(1)
    fl_body.name = f"{name}_FL"
    fr_body.name = f"{name}_FR"
    nl_body = _find_body(comp, f"{name}_NL")
    nr_body = _find_body(comp, f"{name}_NR")

    all_voids = [nl_body, nr_body, fl_body, fr_body]

    # 4. CUT all into top/seat
    af.combine(comp, top_body, all_voids, CUT, True, f"{name}_Top_Cut")

    # 5. CUT each into its leg (keepTool=True on all)
    leg_nl, leg_nr, leg_fl, leg_fr = leg_bodies
    af.combine(comp, leg_nl, [nl_body], CUT, True, f"{name}_Leg_NL")
    af.combine(comp, leg_nr, [nr_body], CUT, True, f"{name}_Leg_NR")
    af.combine(comp, leg_fl, [fl_body], CUT, True, f"{name}_Leg_FL")
    af.combine(comp, leg_fr, [fr_body], CUT, True, f"{name}_Leg_FR")

    return all_voids


def _find_body(comp, name):
    """Find body by name in component (non-recursive, fast)."""
    for i in range(comp.bRepBodies.count):
        b = comp.bRepBodies.item(i)
        if b.name == name:
            return b
    # Fall back to recursive search
    return af.DesignContext().find_body(name, comp)
