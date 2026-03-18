"""Butt hinge template.

Creates parametric butt hinges with interleaving knuckle segments, a pin,
leaf mortises, screw holes, and brass appearance. Brusso-inspired presets.

Anatomy of a butt hinge:
  - Each LEAF = flat rectangular plate mortised flush into the board surface.
  - KNUCKLES = cylinders at the hinge edge, interleaving along the pin axis.
    A 5-knuckle hinge has segments 0,2,4 on leaf A and 1,3 on leaf B.
    Knuckles are separate visual bodies (not JOINed to the plate, since in
    real hinges the metal bends from the plate into the knuckle — a complex
    transition not worth modeling).
  - PIN = thin cylinder through all knuckle centers, connecting the two leaves.

The leaf plate IS the mortise tool — CUT with keepTool=True creates the
pocket AND leaves the visual hardware in place.

Bodies created per hinge pair (5-knuckle):
  2 plates + 5 knuckles + 1 pin = 8 hardware bodies (plus 2 boards)

Usage:
    from helpers.templates import butt_hinge

    hp = butt_hinge.define_params(params, prefix="bh", size="medium")

    butt_hinge.pair(comp,
        board_a=back, plane_a=back_inner_pl,
        origin_a=("bh_inset", "box_w - bt", "case_h - bh_leaf_w"),
        size_a={"x": "bh_l", "z": "bh_leaf_w"},
        board_b=lid, plane_b=lid_bottom_pl,
        origin_b=("bh_inset", "box_w - bt - bh_leaf_w", "case_h"),
        size_b={"x": "bh_l", "y": "bh_leaf_w"},
        barrel_center=("bh_inset + bh_l / 2", "box_w", "case_h"),
        barrel_axis="x",
        prefix="bh", name="BH1", ev=ctx.ev,
        flip_a=True, flip_b=True)
"""

import adsk.core
import adsk.fusion

from helpers import af

Point3D = adsk.core.Point3D
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation

METADATA = {
    "name": "butt_hinge",
    "category": "hardware",
    "description": "Butt hinge with interleaving knuckles, pin, leaf mortises, and screw holes",
    "best_for": ["box lids", "cabinet doors", "chest lids", "jewelry boxes"],
    "not_for": ["piano hinges (continuous)", "concealed/European hinges"],
    "standard_sizes": {
        "small": {
            "l": "0.75 in", "leaf_w": "0.375 in",
            "leaf_t": "0.040 in", "barrel_d": "0.125 in",
            "pin_d": "0.0625 in", "knuckle_n": "3",
            "screw_d": "0.05 in", "screw_count": "2",
            "note": "Jewelry boxes, small boxes (Brusso CB-301 class)",
        },
        "medium": {
            "l": "1.25 in", "leaf_w": "0.5 in",
            "leaf_t": "0.050 in", "barrel_d": "0.1875 in",
            "pin_d": "0.09375 in", "knuckle_n": "5",
            "screw_d": "0.0625 in", "screw_count": "2",
            "note": "Small cabinets, boxes (Brusso CB-302/303 class)",
        },
        "large": {
            "l": "2 in", "leaf_w": "0.75 in",
            "leaf_t": "0.060 in", "barrel_d": "0.25 in",
            "pin_d": "0.125 in", "knuckle_n": "5",
            "screw_d": "0.09375 in", "screw_count": "3",
            "note": "Cabinet doors, chests (Brusso CB-407 class)",
        },
    },
    "params": {
        "bh_l": "Hinge length (along pin axis)",
        "bh_leaf_w": "Leaf width (from pin center to leaf edge)",
        "bh_leaf_t": "Leaf thickness (= mortise depth)",
        "bh_barrel_d": "Knuckle outer diameter",
        "bh_pin_d": "Pin diameter",
        "bh_knuckle_n": "Number of knuckle segments (odd, e.g. 3 or 5)",
        "bh_screw_d": "Screw pilot hole diameter",
        "bh_screw_n": "Number of screw holes per leaf",
    },
}


def define_params(params, prefix="bh", size="medium",
                  hinge_l=None, leaf_w=None, leaf_t=None, barrel_d=None,
                  pin_d=None, knuckle_n=None,
                  screw_d=None, screw_count=None):
    """Define butt hinge parameters.

    Use size preset ("small", "medium", "large") or override individual
    dimensions. Custom values take precedence over the preset.
    """
    VI = adsk.core.ValueInput.createByString
    p = prefix
    s = METADATA["standard_sizes"].get(size,
        METADATA["standard_sizes"]["medium"])

    params.add(f"{p}_l", VI(hinge_l or s["l"]), "in", "Hinge length")
    params.add(f"{p}_leaf_w", VI(leaf_w or s["leaf_w"]), "in", "Leaf width")
    params.add(f"{p}_leaf_t", VI(leaf_t or s["leaf_t"]), "in",
               "Leaf thickness (mortise depth)")
    params.add(f"{p}_barrel_d", VI(barrel_d or s["barrel_d"]), "in",
               "Knuckle diameter")
    params.add(f"{p}_pin_d", VI(pin_d or s["pin_d"]), "in",
               "Pin diameter")
    params.add(f"{p}_knuckle_n", VI(knuckle_n or s["knuckle_n"]), "",
               "Number of knuckle segments")
    params.add(f"{p}_screw_d", VI(screw_d or s["screw_d"]), "in",
               "Screw pilot hole diameter")
    params.add(f"{p}_screw_n", VI(screw_count or s["screw_count"]), "",
               "Screws per leaf")

    return {
        "l": f"{p}_l", "leaf_w": f"{p}_leaf_w",
        "leaf_t": f"{p}_leaf_t", "barrel_d": f"{p}_barrel_d",
        "pin_d": f"{p}_pin_d", "knuckle_n": f"{p}_knuckle_n",
        "screw_d": f"{p}_screw_d", "screw_n": f"{p}_screw_n",
    }


def leaf(comp, body, plane, origin, size_map,
         barrel_center, barrel_axis, knuckle_indices,
         prefix="bh", name="BH", ev=None, flip=False,
         appearance="Brass - Polished", screw_depth_expr=None):
    """Create a hinge leaf: flat plate + interleaving knuckle segments.

    Builds the flat plate, CUTs its mortise into the board (keepTool=True),
    adds screw holes, then creates knuckle cylinders at the barrel center.
    Knuckles are separate visual bodies (not JOINed to the plate).

    Args:
        comp: Component.
        body: Board body to CUT into.
        plane: Sketch plane for the flat plate rectangle.
        origin: (x_expr, y_expr, z_expr) — corner of flat plate.
        size_map: {axis: expr, axis: expr} — plate rectangle dimensions.
        barrel_center: (x_expr, y_expr, z_expr) — pin center in model space.
        barrel_axis: "x", "y", or "z" — axis the pin runs along.
        knuckle_indices: List of segment indices for this leaf (e.g. [0,2,4]).
        prefix: Parameter prefix from define_params.
        name: Feature name prefix.
        ev: Evaluator function.
        flip: Extrude in negative direction.
        appearance: Appearance name (None to skip).
        screw_depth_expr: Screw pilot hole depth expression.

    Returns:
        Dict with "leaf_ext", "leaf_body", "cut", "screw_cuts", "knuckle_bodies".
    """
    if ev is None:
        ev = af._make_ev()
    p = prefix

    # -- Flat plate --
    sk, prof = af.sketch_rect_model(comp, plane, origin, size_map,
                                    f"{name}_Sk", ev)
    leaf_ext = af.ext_op(comp, prof, f"{p}_leaf_t", NEW, None,
                         f"{name}_Leaf", flip=flip)
    leaf_body = leaf_ext.bodies.item(0)
    leaf_body.name = f"{name}_Leaf"

    # -- CUT mortise pocket --
    cut = af.combine(comp, body, leaf_body, CUT, True, f"{name}_Mort")

    # -- Screw holes --
    screw_cuts = _add_screw_holes(comp, body, leaf_body, plane,
                                  origin, size_map, prefix, name, ev,
                                  flip, screw_depth_expr)

    # -- Knuckle segments (separate visual bodies) --
    knuckle_bodies = _add_knuckles(comp, barrel_center, barrel_axis,
                                   knuckle_indices, prefix, name, ev)

    # -- Brass appearance --
    if appearance:
        af.apply_appearance(leaf_body, appearance)
        for kb in knuckle_bodies:
            af.apply_appearance(kb, appearance)

    return {
        "leaf_ext": leaf_ext, "leaf_body": leaf_body,
        "cut": cut, "screw_cuts": screw_cuts,
        "knuckle_bodies": knuckle_bodies,
    }


def pin(comp, barrel_center, barrel_axis,
        prefix="bh", name="BH", ev=None,
        appearance="Brass - Polished"):
    """Create the hinge pin — a thin cylinder through all knuckle centers.

    Args:
        comp: Component.
        barrel_center: (x_expr, y_expr, z_expr) — pin center in model space.
        barrel_axis: "x", "y", or "z".
        prefix: Parameter prefix.
        name: Feature name prefix.
        ev: Evaluator.
        appearance: Appearance name (None to skip).

    Returns:
        Dict with "pin_ext" and "pin_body".
    """
    if ev is None:
        ev = af._make_ev()
    p = prefix
    axis_idx = _idx_for_axis(barrel_axis)

    # Offset plane perpendicular to barrel axis at barrel center
    base_planes = {
        "x": comp.yZConstructionPlane,
        "y": comp.xZConstructionPlane,
        "z": comp.xYConstructionPlane,
    }
    pin_pl = af.off_plane(comp, base_planes[barrel_axis],
                          barrel_center[axis_idx], f"{name}_PinPl")

    # Sketch circle at barrel center
    cx = ev(barrel_center[0])
    cy = ev(barrel_center[1])
    cz = ev(barrel_center[2])
    r = ev(f"{p}_pin_d") / 2

    sk = comp.sketches.add(pin_pl)
    sk.name = f"{name}_PinSk"
    m = sk.modelToSketchSpace
    sc = m(Point3D.create(cx, cy, cz))

    circle = sk.sketchCurves.sketchCircles.addByCenterRadius(
        Point3D.create(sc.x, sc.y, 0), r)
    sk.sketchDimensions.addDiameterDimension(
        circle, Point3D.create(sc.x + r + 0.5, sc.y, 0)
    ).parameter.expression = f"{p}_pin_d"

    # Parametric center position
    h_ax, v_ax = af.probe_sketch_axes(sk)
    d = sk.sketchDimensions
    d.addDistanceDimension(
        sk.originPoint, circle.centerSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        Point3D.create(sc.x / 2, sc.y - 0.5, 0)
    ).parameter.expression = barrel_center[_idx_for_axis(h_ax)]
    d.addDistanceDimension(
        sk.originPoint, circle.centerSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        Point3D.create(sc.x - 0.5, sc.y / 2, 0)
    ).parameter.expression = barrel_center[_idx_for_axis(v_ax)]

    prof = sk.profiles.item(0)
    pin_ext = af.ext_new_sym(comp, prof, f"{p}_l", f"{name}_Pin")
    pin_body = pin_ext.bodies.item(0)
    pin_body.name = f"{name}_Pin"

    if appearance:
        af.apply_appearance(pin_body, appearance)

    return {"pin_ext": pin_ext, "pin_body": pin_body}


def pair(comp,
         board_a, plane_a, origin_a, size_a,
         board_b, plane_b, origin_b, size_b,
         barrel_center, barrel_axis="x",
         prefix="bh", name="BH", ev=None,
         flip_a=False, flip_b=False,
         appearance="Brass - Polished", screw_depth_expr=None):
    """Install a complete hinge pair: two leaves with interleaving knuckles + pin.

    Leaf A gets the even-indexed knuckle segments (0, 2, 4, ...),
    leaf B gets the odd-indexed segments (1, 3, ...).

    Bodies created (5-knuckle example):
      2 plates + 5 knuckle cylinders + 1 pin = 8 hardware bodies

    Args:
        comp: Component.
        board_a/b: Board bodies for each leaf.
        plane_a/b: Sketch planes for each leaf plate.
        origin_a/b: (x, y, z) corner of each leaf plate.
        size_a/b: {axis: expr} size mapping for each leaf.
        barrel_center: (x, y, z) pin center in model space.
        barrel_axis: "x", "y", or "z".
        prefix: Parameter prefix.
        name: Feature name prefix.
        ev: Evaluator.
        flip_a/b: Extrude direction for each leaf plate.
        appearance: Appearance name.
        screw_depth_expr: Screw hole depth.

    Returns:
        Dict with "leaf_a", "leaf_b", "pin" results.
    """
    if ev is None:
        ev = af._make_ev()

    n_knuckles = int(ev(f"{prefix}_knuckle_n"))
    indices_a = list(range(0, n_knuckles, 2))  # even: 0, 2, 4, ...
    indices_b = list(range(1, n_knuckles, 2))  # odd: 1, 3, ...

    leaf_a = leaf(comp, board_a, plane_a, origin_a, size_a,
                  barrel_center, barrel_axis, indices_a,
                  prefix=prefix, name=f"{name}_A", ev=ev,
                  flip=flip_a, appearance=appearance,
                  screw_depth_expr=screw_depth_expr)

    leaf_b = leaf(comp, board_b, plane_b, origin_b, size_b,
                  barrel_center, barrel_axis, indices_b,
                  prefix=prefix, name=f"{name}_B", ev=ev,
                  flip=flip_b, appearance=appearance,
                  screw_depth_expr=screw_depth_expr)

    pin_result = pin(comp, barrel_center, barrel_axis,
                     prefix=prefix, name=name, ev=ev,
                     appearance=appearance)

    return {
        "leaf_a": leaf_a, "leaf_b": leaf_b, "pin": pin_result,
    }


# ── Internal helpers ──

def _idx_for_axis(axis_name):
    """Map axis name to tuple index: x→0, y→1, z→2."""
    return {"x": 0, "y": 1, "z": 2}[axis_name]


def _add_knuckles(comp, barrel_center, barrel_axis,
                  knuckle_indices, prefix, name, ev):
    """Create knuckle cylinders as separate visual bodies.

    Each knuckle segment is a cylinder of diameter barrel_d, length
    hinge_l / knuckle_n, positioned along the barrel axis at the
    appropriate segment offset. Bodies are standalone (not JOINed to
    the leaf plate).

    Returns list of knuckle body references.
    """
    p = prefix
    axis_idx = _idx_for_axis(barrel_axis)

    base_planes = {
        "x": comp.yZConstructionPlane,
        "y": comp.xZConstructionPlane,
        "z": comp.xYConstructionPlane,
    }
    base_plane = base_planes[barrel_axis]

    # Barrel center for approximate sketch positioning
    bcx = ev(barrel_center[0])
    bcy = ev(barrel_center[1])
    bcz = ev(barrel_center[2])
    r = ev(f"{p}_barrel_d") / 2

    # Expression for barrel center along barrel axis
    bc_axis_expr = barrel_center[axis_idx]

    knuckle_bodies = []
    for i in knuckle_indices:
        # Offset plane at segment start along barrel axis
        seg_offset = (f"({bc_axis_expr}) - {p}_l / 2 + "
                      f"{i} * {p}_l / {p}_knuckle_n")
        off_pl = af.off_plane(comp, base_plane, seg_offset,
                              f"{name}_K{i}_Pl")

        # Circle sketch at barrel center
        sk = comp.sketches.add(off_pl)
        sk.name = f"{name}_K{i}_Sk"
        m = sk.modelToSketchSpace
        sc = m(Point3D.create(bcx, bcy, bcz))

        circle = sk.sketchCurves.sketchCircles.addByCenterRadius(
            Point3D.create(sc.x, sc.y, 0), r)
        sk.sketchDimensions.addDiameterDimension(
            circle, Point3D.create(sc.x + r + 0.5, sc.y, 0)
        ).parameter.expression = f"{p}_barrel_d"

        # Parametric center position
        h_ax, v_ax = af.probe_sketch_axes(sk)
        d = sk.sketchDimensions
        d.addDistanceDimension(
            sk.originPoint, circle.centerSketchPoint,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
            Point3D.create(sc.x / 2, sc.y - 0.5, 0)
        ).parameter.expression = barrel_center[_idx_for_axis(h_ax)]
        d.addDistanceDimension(
            sk.originPoint, circle.centerSketchPoint,
            adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
            Point3D.create(sc.x - 0.5, sc.y / 2, 0)
        ).parameter.expression = barrel_center[_idx_for_axis(v_ax)]

        prof = sk.profiles.item(0)

        # Extrude knuckle segment (one segment length)
        seg_ext = af.ext_new(comp, prof,
                             f"{p}_l / {p}_knuckle_n",
                             f"{name}_K{i}")
        seg_body = seg_ext.bodies.item(0)
        seg_body.name = f"{name}_K{i}"
        knuckle_bodies.append(seg_body)

    return knuckle_bodies


def _add_screw_holes(comp, board, leaf_body, plane,
                     origin, size_map, prefix, name, ev,
                     flip, screw_depth_expr):
    """Add screw pilot holes through the leaf body and into the board.

    Screws are evenly spaced along the longer dimension of the leaf,
    centered on the shorter dimension.
    """
    p = prefix
    n_screws = int(ev(f"{p}_screw_n"))
    if n_screws <= 0:
        return []

    screw_r = ev(f"{p}_screw_d") / 2

    # Determine which size_map axis is the long one (hinge length)
    # and which is the short one (leaf width)
    axes = list(size_map.keys())
    sizes = [ev(size_map[a]) for a in axes]
    long_idx = 0 if sizes[0] >= sizes[1] else 1
    short_idx = 1 - long_idx
    long_axis = axes[long_idx]
    short_axis = axes[short_idx]

    # Origin values
    ox = ev(origin[0])
    oy = ev(origin[1])
    oz = ev(origin[2])
    origin_vals = [ox, oy, oz]
    _ai = {"x": 0, "y": 1, "z": 2}

    long_len = sizes[long_idx]
    short_len = sizes[short_idx]

    # Depth: leaf_t + pilot depth into board
    if screw_depth_expr is None:
        screw_depth_expr = f"{p}_leaf_t + 3 * {p}_screw_d"

    screw_cuts = []
    for i in range(n_screws):
        # Position along long axis: evenly spaced
        frac = (i + 1) / (n_screws + 1)
        long_pos = origin_vals[_ai[long_axis]] + frac * long_len
        # Center on short axis
        short_pos = origin_vals[_ai[short_axis]] + short_len / 2

        pos = list(origin_vals)
        pos[_ai[long_axis]] = long_pos
        pos[_ai[short_axis]] = short_pos

        sk = comp.sketches.add(plane)
        sk.name = f"{name}_Screw{i}_Sk"
        m = sk.modelToSketchSpace
        sc = m(Point3D.create(pos[0], pos[1], pos[2]))

        circle = sk.sketchCurves.sketchCircles.addByCenterRadius(
            Point3D.create(sc.x, sc.y, 0), screw_r)
        sk.sketchDimensions.addDiameterDimension(
            circle, Point3D.create(sc.x + screw_r + 0.3, sc.y, 0)
        ).parameter.expression = f"{p}_screw_d"

        prof = sk.profiles.item(0)

        # CUT through leaf body + into board
        cut = af.ext_op(comp, prof, screw_depth_expr, CUT,
                        [leaf_body, board], f"{name}_Screw{i}", flip=flip)
        screw_cuts.append(cut)

    return screw_cuts
