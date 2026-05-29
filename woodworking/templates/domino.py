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

from helpers import sp

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
           use_model_coords=True, cut=True, anchor=None):
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
        anchor: Optional ``sketch_slot_model`` anchor dict — when provided the
            slot is anchored to a PROJECTED parent face (deps rules 1-3)
            instead of the sketch origin. Default None = origin mode (backward
            compatible). Only used when ``use_model_coords=True``. See
            ``sp.sketch_slot_model``.

    Returns:
        The domino void body (BRepBody).
    """
    if ev is None:
        ev = sp._make_ev()

    # Validate mating surfaces before building the joint
    if body_a is not None and body_b is not None:
        sp.validate_joint_contact(body_a, body_b)

    if use_model_coords:
        sk, prof = sp.sketch_slot_model(
            comp, plane, center, long_axis,
            long_expr, short_expr, name=f"{name}_Sk", ev=ev, anchor=anchor)
    else:
        # center is (cx_expr, cy_expr) in sketch space, long_axis ignored
        vertical = (long_axis == "v" or long_axis == "vertical")
        sk, prof = sp.sketch_slot(
            comp, plane, center[0], center[1],
            long_expr, short_expr, vertical,
            name=f"{name}_Sk", ev=ev)

    ext = sp.ext_new_sym(comp, prof, depth_expr, f"{name}")
    void_body = ext.bodies.item(0)
    void_body.name = name

    if cut:
        # combine places the CUT intra-component when body_a /
        # body_b share a component with the void, or at root with
        # assembly proxies when they don't.
        sp.combine(body_a, void_body, CUT, True, f"{name}_CutA")
        sp.combine(body_b, void_body, CUT, True, f"{name}_CutB")

    return void_body


def grid(comp, plane, start, step_axis, step_expr, count_expr,
         long_axis, long_expr, short_expr, depth_expr,
         body_a=None, body_b=None, name="DM", ev=None, cut=True,
         anchor=None):
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
        anchor: Optional ``sketch_slot_model`` anchor dict — anchors the
            template slot to a PROJECTED parent face (deps rules 1-3) instead
            of the origin. Default None = origin mode (backward compatible).

    Returns:
        List of void bodies (template + pattern copies).
    """
    if ev is None:
        ev = sp._make_ev()

    # Validate mating surfaces before building the joint
    if body_a is not None and body_b is not None:
        sp.validate_joint_contact(body_a, body_b)

    # Build ONE template void at start position
    sk, prof = sp.sketch_slot_model(
        comp, plane, start, long_axis,
        long_expr, short_expr, name=f"{name}_Sk", ev=ev, anchor=anchor)
    ext = sp.ext_new_sym(comp, prof, depth_expr, f"{name}")
    template = ext.bodies.item(0)
    template.name = f"{name}_0"

    # Pattern along step axis (parametric count)
    count = int(ev(count_expr))
    void_bodies = [template]
    if count > 1:
        axis_map = {"x": comp.xConstructionAxis,
                     "y": comp.yConstructionAxis,
                     "z": comp.zConstructionAxis}
        pat = sp.body_pattern(comp, template, axis_map[step_axis],
                               count_expr, step_expr, f"{name}_Pat")
        for i in range(pat.bodies.count):
            void_bodies.append(pat.bodies.item(i))

    # Bulk CUT all voids into target bodies (combine handles
    # cross-component routing when body_a / body_b live elsewhere).
    if cut and void_bodies:
        sp.combine(body_a, void_bodies, CUT, True, f"{name}_CutA")
        if body_b is not None and body_b != body_a:
            sp.combine(body_b, void_bodies, CUT, True, f"{name}_CutB")

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


def _check_domino_containment(void_body, body_a, body_b, name):
    """Verify a domino void is fully inside the two target bodies.

    Checks bounding box corners and face center points. Any point outside
    both bodies means the domino is exposed — it protrudes into free space.
    """
    P3 = adsk.core.Point3D
    INSIDE = adsk.fusion.PointContainment.PointInsidePointContainment
    ON = adsk.fusion.PointContainment.PointOnPointContainment

    def _is_contained(pt):
        """True if point is inside or on the surface of either body."""
        try:
            c_a = body_a.pointContainment(pt)
            if c_a == INSIDE or c_a == ON:
                return True
        except Exception:
            pass
        try:
            c_b = body_b.pointContainment(pt)
            if c_b == INSIDE or c_b == ON:
                return True
        except Exception:
            pass
        return False

    # Check face center points (more precise than just corners)
    exposed = []
    for i in range(void_body.faces.count):
        face = void_body.faces.item(i)
        pt = face.pointOnFace
        if not _is_contained(pt):
            exposed.append(f"({pt.x:.2f},{pt.y:.2f},{pt.z:.2f})")

    if exposed:
        print(f"WARNING: {name} has {len(exposed)} exposed face(s) — "
              f"domino protrudes outside mating bodies")
        return False
    return True


def between(comp, plane, body_a, body_b, interface_axis,
            short_expr, depth_expr,
            long_expr=None, long_axis=None,
            count=2, name="DM", ev=None, cut=True):
    """Create dominos at the mating area between two bodies.

    Auto-computes where body_a and body_b overlap, determines the best
    domino orientation (long side along the longer mating dimension),
    and evenly spaces dominos within the overlap region.

    Args:
        comp: Component to create features in.
        plane: Construction plane at the mating interface.
        body_a, body_b: The two bodies being joined.
        interface_axis: 'x', 'y', or 'z' — axis perpendicular to the interface.
        short_expr: Domino thickness expression (e.g. "dm_t").
        depth_expr: Domino depth per side expression (e.g. "dm_d").
        long_expr: Domino width expression (e.g. "dm_w"). If None, uses
            the shorter mating dimension (auto-sized to fit).
        long_axis: Override for the long dimension axis. If None, auto-
            determined from the mating area (long side of the domino
            aligns with the longer dimension of the mating surface).
        count: Number of dominos (int). Default 2.
        name: Feature name prefix.
        ev: Evaluator function.
        cut: If True, CUT into both bodies.

    Returns:
        List of void bodies.
    """
    if ev is None:
        ev = sp._make_ev()

    overlap = _bodies_overlap_bbox(body_a, body_b)
    if overlap is None:
        print(f"WARNING: {name} — bodies don't overlap, skipping dominos")
        return []

    min_x, min_y, min_z, max_x, max_y, max_z = overlap
    axis_map = {"x": (min_x, max_x), "y": (min_y, max_y), "z": (min_z, max_z)}

    # Find the two in-plane axes (excluding interface_axis)
    in_plane = [a for a in ["x", "y", "z"] if a != interface_axis]
    dim_0 = axis_map[in_plane[0]][1] - axis_map[in_plane[0]][0]
    dim_1 = axis_map[in_plane[1]][1] - axis_map[in_plane[1]][0]

    # If long_expr not given, default to "dm_w"
    if long_expr is None:
        long_expr = "dm_w"
    dm_long = ev(long_expr) if isinstance(long_expr, str) else long_expr
    dm_short = ev(short_expr) if isinstance(short_expr, str) else short_expr

    # Auto-determine orientation: the domino long side must FIT within its
    # chosen axis. Pick axes so the domino dimensions don't exceed the
    # mating area dimensions. Step along the larger remaining axis.
    if long_axis is None:
        # Try both orientations, pick the one where both dimensions fit
        fits_0_as_long = (dm_long <= dim_0 + 0.01 and dm_short <= dim_1 + 0.01)
        fits_1_as_long = (dm_long <= dim_1 + 0.01 and dm_short <= dim_0 + 0.01)

        if fits_0_as_long and fits_1_as_long:
            # Both fit — long axis on LONGER mating dimension
            if dim_0 >= dim_1:
                long_axis = in_plane[0]
                step_axis = in_plane[1]
            else:
                long_axis = in_plane[1]
                step_axis = in_plane[0]
        elif fits_0_as_long:
            long_axis = in_plane[0]
            step_axis = in_plane[1]
        elif fits_1_as_long:
            long_axis = in_plane[1]
            step_axis = in_plane[0]
        else:
            # Neither fits at full size — pick the larger dimension for long axis
            # and the domino will need to be smaller (caller should adjust dm_w)
            if dim_0 >= dim_1:
                long_axis = in_plane[0]
                step_axis = in_plane[1]
            else:
                long_axis = in_plane[1]
                step_axis = in_plane[0]
            print(f"WARNING: {name} — domino ({dm_long:.1f}x{dm_short:.1f}mm) "
                  f"doesn't fit in mating area ({dim_0:.1f}x{dim_1:.1f}mm)")
    else:
        step_axis = in_plane[0] if in_plane[0] != long_axis else in_plane[1]

    long_min, long_max = axis_map[long_axis]
    step_min, step_max = axis_map[step_axis]
    long_range = long_max - long_min
    step_range = step_max - step_min

    # Interface center
    iface_min, iface_max = axis_map[interface_axis]
    iface_center = (iface_min + iface_max) / 2

    # Long axis center
    long_center = (long_min + long_max) / 2

    # Compute spacing along step_axis
    # Margin = half domino SHORT dimension + clearance (step-direction extent)
    margin = dm_short / 2 + 0.1

    usable = step_range - 2 * margin
    if usable <= 0 or count < 1:
        count = 1

    if count == 1:
        first = (step_min + step_max) / 2
        spacing = 0
    else:
        spacing = usable / (count - 1)
        first = step_min + margin

    # Build dominos
    axis_idx = {"x": 0, "y": 1, "z": 2}
    void_bodies = []
    for i in range(count):
        step_pos = first + i * spacing

        pos = [0.0, 0.0, 0.0]
        pos[axis_idx[interface_axis]] = iface_center
        pos[axis_idx[long_axis]] = long_center
        pos[axis_idx[step_axis]] = step_pos

        sk, prof = sp.sketch_slot_model(
            comp, plane, (f"{pos[0]} cm", f"{pos[1]} cm", f"{pos[2]} cm"),
            long_axis, long_expr, short_expr,
            name=f"{name}_{i}_Sk", ev=ev)
        ext = sp.ext_new_sym(comp, prof, depth_expr, f"{name}_{i}")
        void = ext.bodies.item(0)
        void.name = f"{name}_{i}"
        void_bodies.append(void)
        sk.isVisible = False

    # Bulk CUT into both bodies (combine routes cross-component).
    if cut and void_bodies:
        sp.combine(body_a, void_bodies, CUT, True, f"{name}_CutA")
        if body_b is not None and body_b != body_a:
            sp.combine(body_b, void_bodies, CUT, True, f"{name}_CutB")

    # Validate containment — domino must be fully inside both bodies
    all_ok = True
    for void in void_bodies:
        if not _check_domino_containment(void, body_a, body_b, void.name):
            all_ok = False

    status = "OK" if all_ok else "EXPOSED"
    print(f">>> {name}: {len(void_bodies)} domino(s), long_axis={long_axis}, "
          f"mating {step_axis}=[{step_min:.1f},{step_max:.1f}] — {status}")
    return void_bodies


def four_corners(comp, plane, center, long_axis, long_expr, short_expr,
                 depth_expr, top_body, leg_bodies, x_mid, y_mid,
                 name="DM", ev=None, anchor=None):
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
        anchor: Optional ``sketch_slot_model`` anchor dict — anchors the
            near-left defining slot to a PROJECTED parent face (deps rules 1-3)
            instead of the origin (the 3 mirrors inherit it). Default None =
            origin mode (backward compatible).

    Returns:
        List of 4 void bodies [NL, NR, FL, FR].
    """
    if ev is None:
        ev = sp._make_ev()

    # Validate mating surfaces — top must contact each leg
    for leg in leg_bodies:
        sp.validate_joint_contact(top_body, leg)

    # 1. Build near-left domino
    sk, prof = sp.sketch_slot_model(
        comp, plane, center, long_axis,
        long_expr, short_expr, name=f"{name}_NL_Sk", ev=ev, anchor=anchor)
    ext = sp.ext_new_sym(comp, prof, depth_expr, f"{name}_NL")
    nl_body = ext.bodies.item(0)
    nl_body.name = f"{name}_NL"

    # 2. Mirror NL → NR across XMid (flips X: left → right)
    mir_nr = sp.mirror_bodies(comp, [nl_body], x_mid, f"{name}_NR_Mir")
    nr_body = mir_nr.bodies.item(0)
    nr_body.name = f"{name}_NR"
    nl_body = _find_body(comp, f"{name}_NL")

    # 3. Mirror NL+NR → FL+FR across YMid (flips Y: near → far)
    mir_far = sp.mirror_bodies(comp, [nl_body, nr_body], y_mid, f"{name}_Far_Mir")
    fl_body = mir_far.bodies.item(0)
    fr_body = mir_far.bodies.item(1)
    fl_body.name = f"{name}_FL"
    fr_body.name = f"{name}_FR"
    nl_body = _find_body(comp, f"{name}_NL")
    nr_body = _find_body(comp, f"{name}_NR")

    all_voids = [nl_body, nr_body, fl_body, fr_body]

    # 4. CUT all into top/seat — combine routes cross-comp when
    # top_body lives in a different component than the voids.
    sp.combine(top_body, all_voids, CUT, True, f"{name}_Top_Cut")

    # 5. CUT each into its leg (keepTool=True on all). Each leg may
    # live in its own component.
    leg_nl, leg_nr, leg_fl, leg_fr = leg_bodies
    sp.combine(leg_nl, [nl_body], CUT, True, f"{name}_Leg_NL")
    sp.combine(leg_nr, [nr_body], CUT, True, f"{name}_Leg_NR")
    sp.combine(leg_fl, [fl_body], CUT, True, f"{name}_Leg_FL")
    sp.combine(leg_fr, [fr_body], CUT, True, f"{name}_Leg_FR")

    return all_voids


def _find_body(comp, name):
    """Find body by name in component (non-recursive, fast)."""
    for i in range(comp.bRepBodies.count):
        b = comp.bRepBodies.item(i)
        if b.name == name:
            return b
    # Fall back to recursive search
    return sp.DesignContext().find_body(name, comp)
