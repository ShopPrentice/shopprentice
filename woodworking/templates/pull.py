"""Bar pull / knob template.

Creates parametric drawer pulls or knobs with bolt holes and visual
handle bodies. Bolt holes are CUT through the board; the handle body
sits proud of the surface.

Usage:
    from woodworking.templates import pull

    pp = pull.define_params(params, prefix="pl", style="bar_3in")

    # Install pull on drawer front
    pull.install(comp, drawer_front, front_plane,
        center=("drawer_w / 2", "front_y", "pull_z"),
        pull_axis="x",          # Bar runs along X
        depth_axis="y",         # Bolt holes go through Y
        prefix="pl", name="Pull", ev=ctx.ev, flip=True)
"""

import adsk.core
import adsk.fusion

from helpers import sp

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation

Point3D = adsk.core.Point3D

METADATA = {
    "name": "pull",
    "category": "hardware",
    "description": "Bar pulls and knobs with bolt holes",
    "best_for": ["drawer fronts", "cabinet doors", "box lids"],
    "not_for": ["integrated/routed pulls (model inline)"],
    "standard_sizes": {
        "bar_3in": {
            "cc": "3 in", "bar_d": "0.375 in", "standoff": "1 in",
            "bolt_d": "0.25 in", "post_d": "0.375 in",
            "note": "3-inch center-to-center bar pull",
        },
        "bar_4in": {
            "cc": "4 in", "bar_d": "0.375 in", "standoff": "1 in",
            "bolt_d": "0.25 in", "post_d": "0.375 in",
            "note": "4-inch center-to-center bar pull",
        },
        "bar_6in": {
            "cc": "6 in", "bar_d": "0.5 in", "standoff": "1.25 in",
            "bolt_d": "0.25 in", "post_d": "0.5 in",
            "note": "6-inch center-to-center bar pull",
        },
        "knob": {
            "cc": "0 in", "bar_d": "0 in", "standoff": "1 in",
            "bolt_d": "0.25 in", "post_d": "1.25 in",
            "note": "Single knob (cc=0 disables bar, one bolt hole)",
        },
    },
    "params": {
        "pl_cc": "Center-to-center distance (0 = single knob)",
        "pl_bar_d": "Bar diameter",
        "pl_standoff": "Handle standoff from board surface",
        "pl_bolt_d": "Bolt hole diameter",
        "pl_post_d": "Post diameter at board surface",
    },
}


def define_params(params, prefix="pl", style="bar_3in",
                  cc=None, bar_d=None, standoff=None,
                  bolt_d=None, post_d=None):
    """Define pull parameters.

    Args:
        params: design.userParameters
        prefix: Parameter name prefix.
        style: Preset name from standard_sizes.
        cc, bar_d, standoff, bolt_d, post_d: Custom overrides.

    Returns:
        Dict of parameter name strings.
    """
    VI = adsk.core.ValueInput.createByString
    p = prefix
    s = METADATA["standard_sizes"].get(style,
        METADATA["standard_sizes"]["bar_3in"])

    params.add(f"{p}_cc", VI(cc or s["cc"]), "in",
               "Pull center-to-center")
    params.add(f"{p}_bar_d", VI(bar_d or s["bar_d"]), "in",
               "Bar diameter")
    params.add(f"{p}_standoff", VI(standoff or s["standoff"]), "in",
               "Standoff from surface")
    params.add(f"{p}_bolt_d", VI(bolt_d or s["bolt_d"]), "in",
               "Bolt hole diameter")
    params.add(f"{p}_post_d", VI(post_d or s["post_d"]), "in",
               "Post diameter")

    return {
        "cc": f"{p}_cc", "bar_d": f"{p}_bar_d",
        "standoff": f"{p}_standoff", "bolt_d": f"{p}_bolt_d",
        "post_d": f"{p}_post_d",
    }


def install(comp, body, plane, center, pull_axis, depth_axis,
            prefix="pl", name="Pull", ev=None, flip=False,
            board_thick_expr=None):
    """Install a pull: CUT bolt holes + create visual handle body.

    Bolt holes are cylinders CUT through the board. The visual handle
    (two posts + connecting bar) sits proud of the board surface.

    Args:
        comp: Component.
        body: Board body to CUT bolt holes into.
        plane: Sketch plane on the board face (perpendicular to depth_axis).
        center: (x_expr, y_expr, z_expr) — center of pull in model space.
        pull_axis: "x", "y", or "z" — axis the bar runs along.
        depth_axis: "x", "y", or "z" — axis bolt holes go through.
        prefix: Parameter prefix.
        name: Feature name prefix.
        ev: Evaluator function.
        flip: Extrude bolt holes in negative direction.
        board_thick_expr: Board thickness (for bolt hole depth).
            If None, uses the body's extent along depth_axis.

    Returns:
        Dict with "bolt_cuts", "post_bodies", "bar_body".
    """
    if ev is None:
        ev = sp._make_ev()
    p = prefix
    _idx = {"x": 0, "y": 1, "z": 2}

    cc = ev(f"{p}_cc")
    bolt_r = ev(f"{p}_bolt_d") / 2
    post_r = ev(f"{p}_post_d") / 2
    standoff = ev(f"{p}_standoff")
    bar_r = ev(f"{p}_bar_d") / 2
    is_knob = cc < 0.01  # cc ≈ 0 means single knob

    cx = ev(center[0])
    cy = ev(center[1])
    cz = ev(center[2])

    # Board thickness for bolt hole depth
    if board_thick_expr is None:
        # Estimate from body bounding box
        bb = body.boundingBox
        di = _idx[depth_axis]
        mins = [bb.minPoint.x, bb.minPoint.y, bb.minPoint.z]
        maxs = [bb.maxPoint.x, bb.maxPoint.y, bb.maxPoint.z]
        bt_cm = maxs[di] - mins[di]
        board_thick_expr = f"{bt_cm} cm"

    # -- Bolt holes --
    offsets = [0.0] if is_knob else [-cc / 2, cc / 2]
    bolt_cuts = []

    for i, off in enumerate(offsets):
        pos = [cx, cy, cz]
        pos[_idx[pull_axis]] += off

        sk = comp.sketches.add(plane)
        sk.name = f"{name}_Bolt{i}_Sk"
        m = sk.modelToSketchSpace
        sc = m(Point3D.create(pos[0], pos[1], pos[2]))

        circle = sk.sketchCurves.sketchCircles.addByCenterRadius(
            Point3D.create(sc.x, sc.y, 0), bolt_r)
        sk.sketchDimensions.addDiameterDimension(
            circle, Point3D.create(sc.x + bolt_r + 0.5, sc.y, 0)
        ).parameter.expression = f"{p}_bolt_d"

        prof = sk.profiles.item(0)
        cut = sp.ext_op(comp, prof, board_thick_expr, CUT, body,
                        f"{name}_Bolt{i}", flip=flip)
        bolt_cuts.append(cut)

    # -- Visual handle --
    # Posts: cylinders extending from board surface
    post_bodies = []
    for i, off in enumerate(offsets):
        pos = [cx, cy, cz]
        pos[_idx[pull_axis]] += off

        sk = comp.sketches.add(plane)
        sk.name = f"{name}_Post{i}_Sk"
        m = sk.modelToSketchSpace
        sc = m(Point3D.create(pos[0], pos[1], pos[2]))

        circle = sk.sketchCurves.sketchCircles.addByCenterRadius(
            Point3D.create(sc.x, sc.y, 0), post_r)
        sk.sketchDimensions.addDiameterDimension(
            circle, Point3D.create(sc.x + post_r + 0.5, sc.y, 0)
        ).parameter.expression = f"{p}_post_d"

        prof = sk.profiles.item(0)
        # Posts extend opposite to bolt holes (outward from surface)
        post_ext = sp.ext_op(comp, prof, f"{p}_standoff", NEW, None,
                             f"{name}_Post{i}", flip=not flip)
        pb = post_ext.bodies.item(0)
        pb.name = f"{name}_Post{i}"
        post_bodies.append(pb)

    # Bar connecting posts (skip for knobs)
    bar_body = None
    if not is_knob and len(post_bodies) == 2:
        # JOIN posts together, then create connecting bar
        # Bar sketch on a plane at standoff height
        bar_pos = [cx, cy, cz]
        bar_pos[_idx[depth_axis]] += (
            -standoff if flip else standoff)

        # Use a rectangle for the bar cross-section, extruded along pull_axis
        third_axis = ({"x", "y", "z"} - {pull_axis, depth_axis}).pop()
        bar_sk_origin = list(bar_pos)
        bar_sk_origin[_idx[pull_axis]] -= cc / 2

        sk = comp.sketches.add(plane)
        sk.name = f"{name}_Bar_Sk"
        m = sk.modelToSketchSpace

        # Bar rectangle: along pull_axis by cc, along third_axis by bar_d
        c1 = list(bar_pos)
        c1[_idx[pull_axis]] -= cc / 2
        c1[_idx[third_axis]] -= bar_r
        c2 = list(bar_pos)
        c2[_idx[pull_axis]] += cc / 2
        c2[_idx[third_axis]] += bar_r

        s1 = m(Point3D.create(c1[0], c1[1], c1[2]))
        s2 = m(Point3D.create(c2[0], c2[1], c2[2]))

        rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(
            Point3D.create(s1.x, s1.y, 0),
            Point3D.create(s2.x, s2.y, 0))

        gc = sk.geometricConstraints
        gc.addHorizontal(rect.item(0))
        gc.addHorizontal(rect.item(2))
        gc.addVertical(rect.item(1))
        gc.addVertical(rect.item(3))

        prof = sp.smallest_profile(sk)
        bar_ext = sp.ext_op(comp, prof, f"{p}_bar_d", NEW, None,
                            f"{name}_Bar", flip=not flip)
        bar_body = bar_ext.bodies.item(0)
        bar_body.name = f"{name}_Bar"

        # JOIN bar + posts into one handle body
        sp.combine(post_bodies[0], [post_bodies[1], bar_body],
                   JOIN, False, f"{name}_HandleJoin")

    return {
        "bolt_cuts": bolt_cuts,
        "post_bodies": post_bodies,
        "bar_body": bar_body,
    }
