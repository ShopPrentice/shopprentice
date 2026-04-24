"""Houndstooth dovetail template.

A decorative variant of through or half-blind dovetails where each
tail has a smaller trapezoidal void cut into its wide face. The void
shares the same flank angle as the main tail, giving a "tooth within
the tooth" visual effect.

The void is subtracted from the tail body BEFORE the pin board is cut.
As a result the pin board's CUT uses a tail shape that has a hole in
it — the hole leaves a matching pin-board tooth that fills the void
in the assembled joint. With contrasting woods, the pin board's tooth
shows through the tail's void for the classic houndstooth look.

Works for through OR half-blind depending on what the caller passes
for ``thick_expr`` and ``y_wide_expr``:

    Through   (lap = 0):   thick_expr = "board_thick",    y_wide_expr = "0 in"
    Half-blind:            thick_expr = "dt_socket_depth", y_wide_expr = "dt_lap"

Usage (through variant):
    from woodworking.templates import dovetail as through_dovetail
    from woodworking.templates import houndstooth_dovetail

    through_dovetail.define_params(params, prefix="dt", ...)
    houndstooth_dovetail.add_params(params, prefix="dt")  # use defaults
    houndstooth_dovetail.corner(
        pin_body=oak, tail_body=cherry, plane=dt_plane,
        x_model=..., y_wide=0, y_narrow=ev("board_thick"),
        y_wide_expr="0 in",
        thick_expr="board_thick",
        dist_expr="board_thick",
        prefix="dt", ev=ev)

Usage (half-blind variant — pass socket_depth / lap instead):
    half_blind_dovetail.define_params(params, prefix="dt", ...)
    houndstooth_dovetail.add_params(params, prefix="dt")
    houndstooth_dovetail.corner(
        ..., y_wide_expr="dt_lap",
        thick_expr="dt_socket_depth", ...)

Proportions & defaults
----------------------
The void is a DECORATIVE ACCENT, not a structural feature. It should
read as a thin vertical slot inside each tail — visible, but not so
large that it weakens the tail or dominates the joint's visual mass.

**{prefix}_ht_small_w** (free) — void short face at the surface
(main tail's wide edge). Opening width you actually see on the
outside of the pin board (for through) or on the socket floor
(for half-blind).
  - Default: `{prefix}_tail_w / 7` (narrow slot — reads as an accent).
  - Range: `tail_w / 10` (very fine, almost a hairline) to
    `tail_w / 4` (bold, almost a second pin).
  - Never > `tail_w / 3`: the void stops reading as an accent and
    starts competing visually with the pin.

**{prefix}_ht_depth** (free) — how deep the void cuts into the tail.
  - Default: `{prefix}_tail_w * 3/5`. Deep enough to read clearly,
    shallow enough to leave material around the void.
  - For through dovetails: must be < `thick_expr` (the void cannot
    cut past the narrow face of the main tail — geometric blowout).
  - For half-blind: must be < `{prefix}_socket_depth`. Stay below
    `socket_depth * 0.9` for safety margin, or the void punches
    through the tail's narrow face and into the mortise opening.

**{prefix}_ht_inset** (DERIVED) — `(tail_w - ht_small_w) / 2`.
  - Not tunable directly. Auto-centers the void in the tail.
  - Changing `ht_small_w` slides the void's edges symmetrically;
    `ht_inset` recomputes so the center stays put.

Because the void shares the main dovetail's angle, a deeper void
widens more at its far end. Keep `ht_depth < tail_w` in practice
(the widening stays manageable), otherwise the void's far face
can approach or exceed the main tail's narrow face and the
geometry becomes fragile.

Best for: premium visible joints, contrasting-wood casework where
the pin board's "tooth" peeking through the void is the design
intent. Adds pattern complexity — skip for utilitarian boxes.
"""

import adsk.core
import adsk.fusion
import math

from helpers import sp
from woodworking.templates._dovetail_common import trapezoid_sketch

Point3D = adsk.core.Point3D
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation

METADATA = {
    "name": "houndstooth_dovetail",
    "category": "joinery",
    "description": (
        "Decorative dovetail with trapezoidal void in each tail "
        "(combines with through or half-blind)"),
    "best_for": ["premium visible joints", "contrasting-wood casework"],
    "params": {
        "dt_ht_small_w": "Void short face width (free) — sits on main tail's wide edge",
        "dt_ht_depth": "Void depth into the tail (free)",
        "dt_ht_inset": "Derived: (tail_w - ht_small_w) / 2",
    },
}


def add_params(params, prefix="dt", ht_small_w=None, ht_depth=None):
    """Add houndstooth-specific params.

    Call AFTER through's or half-blind's ``define_params`` — this
    function only adds the extra void params, relying on the base
    ``{prefix}_tail_w`` and ``{prefix}_angle`` already existing.

    The free parameters are ``ht_small_w`` (the short face of the void,
    at the main tail's wide edge) and ``ht_depth`` (how deep the void
    goes into the tail). Defaults are proportional to tail_w so the
    void stays visually balanced as the main dovetail dimensions change:
      ``ht_small_w = tail_w / 7``   (narrow slot at the surface)
      ``ht_depth   = tail_w * 3/5`` (void depth into the tail)

    ``ht_inset`` (how far the void is inset from the main tail's wide-face
    ends along the joint axis) is derived from ``ht_small_w``:
      ``ht_inset = (tail_w - ht_small_w) / 2``

    Args:
        params: design.userParameters.
        prefix: Parameter name prefix (e.g. "dt"). Must match the
            prefix used for the base dovetail params.
        ht_small_w: Void short face width. Defaults to ``{prefix}_tail_w / 7``.
        ht_depth: Void depth into the tail.
            Defaults to ``{prefix}_tail_w * 3 / 5``.

    Returns:
        Dict of parameter names.
    """
    VI = adsk.core.ValueInput.createByString
    p = prefix
    if ht_small_w is None:
        ht_small_w = f"{p}_tail_w / 7"
    if ht_depth is None:
        ht_depth = f"{p}_tail_w * 3 / 5"

    # Independent: short face width (user tunes directly) + void depth.
    params.add(f"{p}_ht_small_w", VI(ht_small_w), "in",
               "Houndstooth void short face (at main tail's wide edge)")
    params.add(f"{p}_ht_depth", VI(ht_depth), "in",
               "Houndstooth void depth")
    # Derived: joint-axis inset from main tail's wide-face ends.
    params.add(f"{p}_ht_inset",
               VI(f"({p}_tail_w - {p}_ht_small_w) / 2"),
               "in",
               "Houndstooth void inset (derived from ht_small_w)")

    return {
        "ht_small_w": f"{p}_ht_small_w",
        "ht_depth": f"{p}_ht_depth",
        "ht_inset": f"{p}_ht_inset",
    }


def corner(pin_body, tail_body, plane,
           x_model, y_wide, y_narrow,
           y_wide_expr, thick_expr, dist_expr,
           name="HT", prefix="dt", ev=None,
           pattern_axis=None, z_base_expr=None):
    """Create a houndstooth dovetail corner.

    Same geometry as through/half-blind at the main tail, plus a
    smaller trapezoidal void cut into the wide face of each tail.

    Args:
        pin_body: Pin board body — receives the final CUT.
        tail_body: Tail board body — grows by the houndstooth tail.
        plane: Sketch plane in tail_body's component.
        x_model: Model coordinate of the sketch plane along ext axis.
        y_wide, y_narrow: Model coords of wide / narrow faces.
        y_wide_expr: Parametric expression for wide-face position
            ("0 in" for through, "{p}_lap" for half-blind).
        thick_expr: Depth of tail penetration
            ("board_thick" for through, "{p}_socket_depth" for half-blind).
        dist_expr: Extrude distance (typically same as tail stock thickness).
        name: Feature name prefix.
        prefix: Parameter prefix.
        ev: Evaluator function (defaults to design context's).
        pattern_axis: Construction axis for the tail pattern. Defaults
            to tail_body's parent component's Z axis.
        z_base_expr: Expression for joint-axis offset of the first
            half-pin. Defaults to ``{prefix}_half_pin``.

    Returns:
        Dict with keys: ``join_feat``, ``void_cut``, ``pattern``, ``cut_combine``.
    """
    if ev is None:
        ev = sp._make_ev()

    p = prefix
    thick = ev(thick_expr)
    tw = ev(f"{p}_tail_w")
    angle = ev(f"{p}_angle")
    delta = thick * math.tan(angle)

    ht_inset = ev(f"{p}_ht_inset")
    ht_depth = ev(f"{p}_ht_depth")
    ht_delta = ht_depth * math.tan(angle)

    comp_tail = tail_body.parentComponent

    if z_base_expr is None:
        # Edge pin = pad + half_pin
        z_base = ev(f"{p}_pad") + ev(f"{p}_half_pin")
        z_dim_expr = f"{p}_pad + {p}_pin_w / 2"
    else:
        z_base = ev(z_base_expr)
        z_dim_expr = z_base_expr

    # --- Main tail trapezoid ---
    m1_pt = Point3D.create(x_model, y_wide, z_base)
    m2_pt = Point3D.create(x_model, y_wide, z_base + tw)
    m3_pt = Point3D.create(x_model, y_narrow, z_base + tw - delta)
    m4_pt = Point3D.create(x_model, y_narrow, z_base + delta)

    prof_main = trapezoid_sketch(
        comp_tail, plane,
        m1_pt, m2_pt, m3_pt, m4_pt,
        thick_expr=thick_expr,
        short_joint_expr=f"{z_dim_expr} + {thick_expr} * tan({p}_angle)",
        short_base_expr=f"({y_wide_expr}) + ({thick_expr})",
        prefix=prefix, name=f"{name}_Tail")

    join_feat = sp.ext_op(
        comp_tail, prof_main, dist_expr, JOIN, tail_body,
        f"{name}_TailJoin")

    # --- Houndstooth void: inverted dovetail, short edge on main wide edge ---
    # Short face of void sits on the main tail's wide face (y = y_wide),
    # inset from the main's wide-face ends by ht_inset on each side.
    # Wide face of void sits ht_depth deeper into the tail, wider by
    # 2*ht_delta. Cutting this out leaves a dovetail-shaped pocket whose
    # pin-board "tooth" (when the pin_body is CUT) locks into the tail.
    direction = 1 if y_narrow > y_wide else -1
    y_void_wide = y_wide + direction * ht_depth

    # Map to trapezoid_sketch's m1..m4 convention (m1,m2 = wide face
    # corners; m3,m4 = narrow/short face corners):
    v1_pt = Point3D.create(
        x_model, y_void_wide, z_base + ht_inset - ht_delta)  # wide-low
    v2_pt = Point3D.create(
        x_model, y_void_wide, z_base + tw - ht_inset + ht_delta)  # wide-high
    v3_pt = Point3D.create(
        x_model, y_wide, z_base + tw - ht_inset)             # short-high
    v4_pt = Point3D.create(
        x_model, y_wide, z_base + ht_inset)                  # short-low

    prof_void = trapezoid_sketch(
        comp_tail, plane,
        v1_pt, v2_pt, v3_pt, v4_pt,
        thick_expr=f"{p}_ht_depth",
        short_joint_expr=f"{z_dim_expr} + {p}_ht_inset",
        short_base_expr=y_wide_expr,
        prefix=prefix, name=f"{name}_Void",
        narrow_w_expr=f"{p}_ht_small_w")

    void_cut = sp.ext_op(
        comp_tail, prof_void, dist_expr, CUT, tail_body,
        f"{name}_VoidCut")

    # --- Pattern both features (tail join + void cut) along joint axis ---
    if pattern_axis is None:
        pattern_axis = comp_tail.zConstructionAxis

    VI = adsk.core.ValueInput.createByString
    coll = adsk.core.ObjectCollection.create()
    coll.add(join_feat)
    coll.add(void_cut)
    inp = comp_tail.features.rectangularPatternFeatures.createInput(
        coll, pattern_axis,
        VI(f"{p}_tail_count"), VI(f"{p}_pitch"),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    inp.quantityTwo = VI("1")
    pattern = comp_tail.features.rectangularPatternFeatures.add(inp)
    pattern.name = f"{name}_Pat"

    # --- CUT pin_body using tail_body (with voids) as tool ---
    cut_combine = sp.combine(
        pin_body, tail_body, CUT, True, f"{name}_Cut")

    return {
        "join_feat": join_feat,
        "void_cut": void_cut,
        "pattern": pattern,
        "cut_combine": cut_combine,
    }
