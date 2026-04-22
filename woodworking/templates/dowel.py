"""Dowel joint template.

Creates cylindrical dowel joints between two mating bodies.
Simpler than dominos — round cross-section means no orientation concerns.
Edges are slightly filleted for easier insertion.

Usage:
    from woodworking.templates import dowel

    # Single dowel at a position
    dowel.single(comp, plane, center=("x0", "y0", "z0"),
                 diameter="dw_d", depth="dw_depth",
                 body_a=board_a, body_b=board_b,
                 name="DW_1", ev=ev)

    # Row of dowels along a joint line
    dowel.grid(comp, plane, start=("x0", "y0", "z0"),
               step_axis="z", step_expr="dw_sp", count_expr="dw_count",
               diameter="dw_d", depth="dw_depth",
               body_a=board_a, body_b=board_b,
               name="DW", ev=ev)
"""

import adsk.core
import adsk.fusion

from helpers import sp

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation

METADATA = {
    "name": "dowel",
    "category": "joinery",
    "description": "Round dowel joint — cylindrical pin bridging two boards",
    "best_for": ["edge joining (panel glue-ups)", "face frames", "shelf alignment",
                 "crib spindle-to-rail connections", "simple structural joints"],
    "not_for": ["high-strength structural joints (use M&T or domino instead)",
                "visible decorative joints (use dovetails)"],
    "standard_sizes": {
        "1/4 in":  {"diameter": "0.25 in", "depth": "0.5 in"},
        "5/16 in": {"diameter": "0.3125 in", "depth": "0.625 in"},
        "3/8 in":  {"diameter": "0.375 in", "depth": "0.75 in"},
        "1/2 in":  {"diameter": "0.5 in", "depth": "1 in"},
    },
    "rules": {
        "diameter": "≤ 1/2 of thinnest board at the joint",
        "depth": "typically 2× diameter per side",
        "spacing": "3-4 inches apart for edge joints",
        "fillet": "slight edge fillet for easy insertion (r ≈ diameter/10)",
    },
}


def single(comp, plane, center, diameter, depth,
           body_a=None, body_b=None, name="DW", ev=None, cut=True):
    """Create a single dowel joint between two bodies.

    Sketches a circle on the interface plane, extrudes symmetrically,
    then fillets the edges. CUTs into both bodies with keepTool=True.

    Args:
        comp: Component to create features in (usually root).
        plane: Construction plane at the mating interface.
        center: (x_expr, y_expr, z_expr) — center of the dowel in model space.
        diameter: Diameter expression (e.g. "dw_d" or "0.375 in").
        depth: Depth per side expression (e.g. "dw_depth" or "0.75 in").
        body_a: First body to CUT into.
        body_b: Second body to CUT into.
        name: Feature name prefix.
        ev: Evaluator function.
        cut: If True, CUT into both bodies. If False, just create the dowel body.

    Returns:
        The dowel void body (BRepBody).
    """
    if ev is None:
        ev = sp._make_ev()

    VI = adsk.core.ValueInput.createByString
    P3 = adsk.core.Point3D

    # Evaluate center and diameter
    cx = ev(center[0]) if isinstance(center[0], str) else center[0]
    cy = ev(center[1]) if isinstance(center[1], str) else center[1]
    cz = ev(center[2]) if isinstance(center[2], str) else center[2]
    dia = ev(diameter) if isinstance(diameter, str) else diameter
    radius = dia / 2

    # Sketch circle on the interface plane
    sk = comp.sketches.add(plane)
    sk.name = f"{name}_Sk"
    m2s = sk.modelToSketchSpace
    sc = m2s(P3.create(cx, cy, cz))
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        P3.create(sc.x, sc.y, 0), radius)

    prof = sk.profiles.item(0)

    # Extrude symmetrically (depth per side)
    ext = sp.ext_new_sym(comp, prof, depth, f"{name}")
    void_body = ext.bodies.item(0)
    void_body.name = name

    # Fillet both circular edges (slight rounding for easy insertion)
    fillet_r = dia / 10  # 10% of diameter
    try:
        edges = adsk.core.ObjectCollection.create()
        for i in range(void_body.edges.count):
            edge = void_body.edges.item(i)
            # Circular edges are at the cylinder ends
            if not edge.geometry.curveType == adsk.core.Curve3DTypes.Line3DCurveType:
                edges.add(edge)
        if edges.count > 0:
            fil_inp = comp.features.filletFeatures.createInput()
            fil_inp.addConstantRadiusEdgeSet(edges,
                VI(f"{fillet_r} cm"), False)
            comp.features.filletFeatures.add(fil_inp).name = f"{name}_Fil"
    except Exception:
        pass  # fillet failure is cosmetic, don't block the joint

    sk.isVisible = False

    if cut:
        # combine routes intra-comp or to root based on where
        # body_a / body_b live relative to the dowel void.
        sp.combine(body_a, void_body, CUT, True, f"{name}_CutA")
        sp.combine(body_b, void_body, CUT, True, f"{name}_CutB")

    return void_body


def grid(comp, plane, start, step_axis, step_expr, count_expr,
         diameter, depth, body_a=None, body_b=None,
         name="DW", ev=None, cut=True):
    """Create a row of dowels along a joint line.

    Creates one template dowel, then uses body_pattern to replicate.

    Args:
        comp: Component to create features in.
        plane: Construction plane at the mating interface.
        start: (x_expr, y_expr, z_expr) — center of the FIRST dowel.
        step_axis: 'x', 'y', or 'z' — axis to step along.
        step_expr: Spacing expression (e.g. "dw_sp").
        count_expr: Count expression (e.g. "dw_count"). Parametric.
        diameter: Diameter expression.
        depth: Depth per side expression.
        body_a, body_b: Bodies to CUT into.
        name: Feature name prefix.
        ev: Evaluator function.
        cut: If True, bulk CUT all dowels into both bodies.

    Returns:
        List of dowel void bodies.
    """
    if ev is None:
        ev = sp._make_ev()

    # Create template dowel (no CUT yet — pattern first)
    template = single(comp, plane, start, diameter, depth,
                       name=f"{name}_0", ev=ev, cut=False)

    # Pattern along step axis
    count = int(ev(count_expr) if isinstance(count_expr, str) else count_expr)
    bodies = [template]

    if count > 1:
        axis_map = {
            "x": comp.xConstructionAxis,
            "y": comp.yConstructionAxis,
            "z": comp.zConstructionAxis,
        }
        pat = sp.body_pattern(comp, template, axis_map[step_axis],
                               count_expr, step_expr, f"{name}_Pat")
        for i in range(pat.bodies.count):
            bodies.append(pat.bodies.item(i))

    # Bulk CUT all dowels into both bodies (combine handles
    # cross-component routing when body_a / body_b are elsewhere).
    if cut and body_a is not None and body_b is not None:
        sp.combine(body_a, bodies, CUT, True, f"{name}_CutA")
        sp.combine(body_b, bodies, CUT, True, f"{name}_CutB")

    return bodies
