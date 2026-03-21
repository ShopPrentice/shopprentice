"""Bowtie (butterfly key) inlay template.

Creates decorative bowtie/butterfly key inlays that span cracks in live edge
slabs. The bowtie is an hourglass-shaped body that CUTs into the slab surface,
creating a pocket for a contrasting wood inlay.

Orientation rule: bowties are always perpendicular to the crack direction.
Since cracks run parallel to the wood fiber, the bowtie's long axis must
cross the grain. On a slab with fiber in X, bowties are vertical (long_axis="z").

Usage:
    from helpers.templates import bowtie

    # Single bowtie at a specific position
    bowtie.single(comp, plane, center=("12 in", "y0", "20 in"),
                  long_axis="z", length="bt_len", end_w="bt_end_w",
                  waist_w="bt_waist_w", depth="bt_depth",
                  slab_body=slab, name="BT_1", ev=ev)

    # Row of bowties along a crack line
    bowtie.row(comp, plane, crack_axis="x", crack_center=("mid_x", "y0", "mid_z"),
               count=3, spacing="bt_spacing",
               long_axis="z", length="bt_len", end_w="bt_end_w",
               waist_w="bt_waist_w", depth="bt_depth",
               slab_body=slab, name="BT", ev=ev)
"""

import adsk.core
import adsk.fusion
import math

from helpers import af

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation

METADATA = {
    "name": "bowtie",
    "category": "decorative_joinery",
    "description": "Butterfly key / bowtie inlay for stabilizing cracks in live edge slabs",
    "best_for": ["live edge slab cracks", "decorative inlays", "tabletop crack repair"],
    "not_for": ["structural joints", "hidden joinery"],
    "sizing_guide": {
        "small":  {"length": "2 in",   "end_w": "1 in",   "waist_w": "0.375 in", "depth": "0.5 in"},
        "medium": {"length": "3 in",   "end_w": "1.5 in", "waist_w": "0.5 in",   "depth": "0.67 in"},
        "large":  {"length": "4 in",   "end_w": "2 in",   "waist_w": "0.75 in",  "depth": "0.75 in"},
    },
    "rules": {
        "depth": "1/3 to 1/2 of slab thickness",
        "spacing": "one near each end of crack, others every 5-8 inches",
        "orientation": "perpendicular to crack (= perpendicular to grain)",
    },
}


def _bowtie_points(cx, cz, half_l, half_ew, half_ww, long_axis):
    """Compute 6 corners of a bowtie in the XZ plane.

    Returns list of (x, z) tuples for the hourglass shape.
    long_axis determines whether the bowtie is vertical or horizontal.
    """
    if long_axis == "z":
        # Long axis vertical: bowtie tall in Z, narrow in X
        return [
            (cx - half_ew, cz + half_l),   # top-left (wide end)
            (cx + half_ew, cz + half_l),   # top-right (wide end)
            (cx + half_ww, cz),             # waist right
            (cx + half_ew, cz - half_l),   # bottom-right (wide end)
            (cx - half_ew, cz - half_l),   # bottom-left (wide end)
            (cx - half_ww, cz),             # waist left
        ]
    else:  # long_axis == "x"
        # Long axis horizontal: bowtie wide in X, narrow in Z
        return [
            (cx - half_l, cz + half_ew),   # left-top (wide end)
            (cx - half_l, cz - half_ew),   # left-bottom (wide end)
            (cx,          cz - half_ww),    # waist bottom
            (cx + half_l, cz - half_ew),   # right-bottom (wide end)
            (cx + half_l, cz + half_ew),   # right-top (wide end)
            (cx,          cz + half_ww),    # waist top
        ]


def single(comp, plane, center, long_axis, length, end_w, waist_w,
           depth, slab_body, name="BT", ev=None, cut=True):
    """Create a single bowtie inlay on a slab.

    Args:
        comp: Component to create features in.
        plane: Construction plane or BRepFace for the sketch.
        center: (x_expr, y_expr, z_expr) — model-space center of the bowtie.
        long_axis: "x" or "z" — direction of the bowtie's long dimension.
        length: Expression for bowtie length (long dimension).
        end_w: Expression for width at the wide ends.
        waist_w: Expression for width at the narrow waist.
        depth: Expression for inlay depth (how deep to CUT into slab).
        slab_body: The slab body to CUT into (or assembly proxy).
        name: Feature name prefix.
        ev: Parameter evaluator function.
        cut: If True, CUT the bowtie into the slab. If False, just create the body.

    Returns:
        The bowtie body.
    """
    if ev is None:
        design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
        ev = lambda e: (design.userParameters.itemByName(e).value
                        if design.userParameters.itemByName(e)
                        else design.unitsManager.evaluateExpression(e, "cm"))

    # Evaluate center and dimensions
    cx = ev(center[0]) if isinstance(center[0], str) else center[0]
    cy = ev(center[1]) if isinstance(center[1], str) else center[1]
    cz = ev(center[2]) if isinstance(center[2], str) else center[2]
    half_l = ev(length) / 2
    half_ew = ev(end_w) / 2
    half_ww = ev(waist_w) / 2

    # Compute 6 corners
    pts_xz = _bowtie_points(cx, cz, half_l, half_ew, half_ww, long_axis)

    # Sketch on the plane
    sk = comp.sketches.add(plane)
    sk.name = f"{name}_Sk"
    m2s = sk.modelToSketchSpace
    P3 = adsk.core.Point3D

    sp = [m2s(P3.create(px, cy, pz)) for px, pz in pts_xz]
    lines = sk.sketchCurves.sketchLines
    prev = lines.addByTwoPoints(sp[0], sp[1])
    for j in range(2, len(sp)):
        prev = lines.addByTwoPoints(prev.endSketchPoint, sp[j])
    lines.addByTwoPoints(prev.endSketchPoint,
                          sk.sketchCurves.sketchLines.item(0).startSketchPoint)

    prof = sk.profiles.item(0)
    VI = adsk.core.ValueInput.createByString

    ext_inp = comp.features.extrudeFeatures.createInput(
        prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ext_inp.setDistanceExtent(False, VI(depth))
    ext = comp.features.extrudeFeatures.add(ext_inp)
    ext.name = name
    bt_body = ext.bodies.item(0)
    bt_body.name = name

    if cut and slab_body:
        af.combine(comp, slab_body, [bt_body], CUT, True, f"{name}_Cut")

    sk.isVisible = False
    return bt_body


def row(comp, plane, crack_axis, crack_center, count, spacing,
        long_axis, length, end_w, waist_w, depth,
        slab_body, name="BT", ev=None):
    """Create a row of bowties along a crack line.

    Args:
        comp: Component.
        plane: Construction plane for sketches.
        crack_axis: "x" or "z" — direction the crack runs.
        crack_center: (x_expr, y_expr, z_expr) — center of the crack line.
        count: Number of bowties (int or expression string).
        spacing: Expression for center-to-center spacing along crack_axis.
        long_axis: "x" or "z" — bowtie orientation (should be perpendicular to crack_axis).
        length, end_w, waist_w, depth: Dimension expressions.
        slab_body: Slab body to CUT into.
        name: Name prefix.
        ev: Parameter evaluator.

    Returns:
        List of bowtie bodies.
    """
    if ev is None:
        design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
        ev = lambda e: (design.userParameters.itemByName(e).value
                        if design.userParameters.itemByName(e)
                        else design.unitsManager.evaluateExpression(e, "cm"))

    n = int(ev(count)) if isinstance(count, str) else int(count)
    sp_cm = ev(spacing) if isinstance(spacing, str) else spacing

    # Crack center
    cc = [ev(c) if isinstance(c, str) else c for c in crack_center]

    bodies = []
    for i in range(n):
        # Offset from center along crack axis
        offset = (i - (n - 1) / 2) * sp_cm
        center = list(cc)
        if crack_axis == "x":
            center[0] += offset
        else:  # "z"
            center[2] += offset

        bt = single(comp, plane, tuple(center), long_axis,
                     length, end_w, waist_w, depth,
                     slab_body, f"{name}_{i+1}", ev)
        bodies.append(bt)

    return bodies
