"""Mortise & Tenon joint template.

Creates M&T joints between two bodies. The tenon is sketched on the
rail/stretcher end face and extruded into the leg/post. The tenon body
is JOINed into the tenon piece, then CUT into the mortise piece.
Never draws a mortise sketch — the tenon body IS the cutting tool.

Shoulders are implicit — when the tenon is smaller than the rail face,
the remaining material forms the shoulder naturally.

Usage:
    from woodworking.templates import mortise_tenon as mt

    mt.define_params(params, prefix="mt",
        tenon_w="2 in", tenon_thick="0.375 in", tenon_depth="1 in")

    # Blind tenon (rail into leg)
    face = sp.find_face(rail, "x", -1)
    mt.blind(comp, face,
             origin=("leg_w", "(leg_w - mt_tt) / 2",
                     "rail_z + (rail_w - mt_tw) / 2"),
             size={"y": "mt_tt", "z": "mt_tw"},
             depth_expr="mt_td",
             tenon_body=rail, mortise_body=leg,
             name="MT_L", ev=ctx.ev)

    # Through tenon (full leg width + proud)
    mt.through(comp, face,
               origin=("leg_w", "(leg_w - mt_tt) / 2",
                       "rail_z + (rail_w - mt_tw) / 2"),
               size={"y": "mt_tt", "z": "mt_tw"},
               depth_expr="leg_w + mt_proud",
               tenon_body=rail, mortise_body=leg,
               name="TT_L", ev=ctx.ev)
"""

import adsk.core
import adsk.fusion

from helpers import sp

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation

METADATA = {
    "name": "mortise_tenon",
    "category": "joinery",
    "variants": {
        "blind": {
            "description": "Tenon stops inside mortise piece — hidden joint",
            "best_for": ["leg-to-rail", "shelf-to-side", "structural frames"],
        },
        "through": {
            "description": "Tenon extends past far face, optionally proud",
            "best_for": ["visible joints", "wedged tenons", "trestle tables"],
        },
        "angled": {
            "description": "Swept tenon for non-perpendicular joints (splayed legs)",
            "best_for": ["splayed leg stretchers", "angled rails"],
            "status": "inline_only",
        },
    },
    "params": {
        "tenon_w": "Width across grain",
        "tenon_thick": "Thickness (extrude distance)",
        "tenon_depth": "Depth/penetration into mortise piece",
    },
}


def define_params(params, prefix="mt",
                  tenon_w="2 in", tenon_thick="0.375 in",
                  tenon_depth="1 in"):
    """Define M&T joint parameters.

    Args:
        params: design.userParameters
        prefix: Parameter name prefix.
        tenon_w: Tenon width (across grain, on sketch plane).
        tenon_thick: Tenon thickness (extrude distance).
        tenon_depth: Tenon penetration into mortise piece (on sketch plane).

    Returns:
        Dict of parameter names.
    """
    VI = adsk.core.ValueInput.createByString
    p = prefix

    params.add(f"{p}_tw", VI(tenon_w), "in", "Tenon width")
    params.add(f"{p}_tt", VI(tenon_thick), "in", "Tenon thickness")
    params.add(f"{p}_td", VI(tenon_depth), "in", "Tenon depth")

    return {
        "tw": f"{p}_tw", "tt": f"{p}_tt",
        "td": f"{p}_td",
    }


def select_variant(purpose, angled=False):
    """Select the best M&T variant for a given purpose.

    Args:
        purpose: "rail", "stretcher", "shelf", "through", "frame".
        angled: True if the joint is at a non-perpendicular angle.

    Returns:
        Variant name string.
    """
    if angled:
        return "angled"
    mapping = {
        "rail": "blind",
        "stretcher": "blind",
        "shelf": "through",
        "through": "through",
        "frame": "blind",
    }
    return mapping.get(purpose, "blind")


def blind(comp, plane, origin, size, depth_expr,
          tenon_body, mortise_body, name="MT",
          ev=None, mirror_plane=None, anchor=None):
    """Create a blind M&T joint.

    Sketches tenon cross-section on the rail end face, extrudes into
    the leg as a NewBody, then JOINs into tenon_body. The caller is
    responsible for CUTting the mortise body with the rail afterwards.

    Shoulders are implicit: if tenon_w < rail_w or tenon_thick < rail_t,
    the step on the rail face is the shoulder.

    Args:
        comp: Component that owns the sketch + tenon extrude. Must be
            ``tenon_body.parentComponent``. The tenon body is created
            here and JOINed into ``tenon_body`` (always intra-component).
            For a blind mortise in a *different* component, call the
            caller's mortise CUT via ``sp.combine`` — this template
            only builds the tenon side.
        plane: BRepFace (rail end face) or construction plane.
        origin: (x_expr, y_expr, z_expr) — tenon corner in model space.
        size: {axis: expr, axis: expr} — 2 model-axis dimensions.
        depth_expr: Tenon depth/penetration expression.
        tenon_body: Rail/stretcher body that owns the tenon.
        mortise_body: Leg/post body that receives the mortise.
        name: Feature name prefix.
        ev: Evaluator function.
        mirror_plane: If provided, mirrors the tenon to the opposite end
            and JOINs both into tenon_body.
        anchor: Optional ``sketch_rect_model`` anchor dict. When provided, the
            tenon cross-section is anchored to a PROJECTED parent face instead
            of the sketch origin, so the resulting non-root sketch passes the
            validator (deps rules 1-3). Default None keeps the existing
            origin-dimensioned behavior (backward compatible). See
            ``sp.sketch_rect_model`` for the dict shape.

    Returns:
        Dict with 'tenon_ext', 'join', 'mirror' (if mirror_plane).
    """
    if ev is None:
        ev = sp._make_ev()

    # Validate mating surfaces before building the joint
    sp.validate_joint_contact(tenon_body, mortise_body)

    sk, _prof = sp.sketch_rect_model(comp, plane, origin, size,
                                      name=f"{name}_Sk", ev=ev, anchor=anchor)
    # On body-face sketches the face boundary creates multiple profiles.
    # smallest_profile picks the drawn rectangle, not the surrounding region.
    prof = sp.smallest_profile(sk)
    tenon_ext = sp.ext_new(comp, prof, depth_expr, f"{name}_Tenon")
    tenon_b = tenon_ext.bodies.item(0)
    tenon_b.name = f"{name}_Tenon"

    result = {"tenon_ext": tenon_ext}

    # JOIN is always intra-component (tenon_b was just created in
    # ``comp`` == tenon_body.parentComponent), so sp.combine is fine.
    if mirror_plane:
        mir = sp.mirror_feats(comp, [tenon_ext], mirror_plane,
                              f"{name}_Mirror")
        mir_body = mir.bodies.item(0)
        join = sp.combine(tenon_body, [tenon_b, mir_body],
                          JOIN, False, f"{name}_Join")
        result["mirror"] = mir
    else:
        join = sp.combine(tenon_body, tenon_b, JOIN, False,
                          f"{name}_Join")

    result["join"] = join
    return result


def through(comp, plane, origin, size, depth_expr,
            tenon_body, mortise_body, name="TT",
            ev=None, mirror_plane=None, anchor=None):
    """Create a through M&T joint.

    Unlike blind(), CUTs the mortise body with the tenon body directly
    (before JOIN) to avoid coplanar face splitting. When the rail end
    face is flush with the leg face, using the whole rail as a CUT tool
    splits the leg at that coplanar boundary. CUTting with just the
    tenon avoids this.

    The depth_expr should include any proud amount
    (e.g. "leg_size + tt_proud").

    ``anchor``: optional ``sketch_rect_model`` anchor dict — when supplied the
    tenon cross-section is anchored to a PROJECTED parent face (deps rules 1-3)
    instead of the sketch origin. Default None = origin mode (backward
    compatible). See ``sp.sketch_rect_model``.

    Cross-component: when ``tenon_body`` and ``mortise_body`` live in
    different components, the mortise CUT is automatically placed at
    root with assembly-context proxies via ``sp.combine``. The
    sketch, tenon extrude, and tenon JOIN stay in ``comp``, which must
    be ``tenon_body.parentComponent``.

    Returns:
        Dict with 'tenon_ext', 'mortise_cut', 'join',
        'mirror' (if mirror_plane).
    """
    if ev is None:
        ev = sp._make_ev()

    # Validate mating surfaces before building the joint
    sp.validate_joint_contact(tenon_body, mortise_body)

    sk, _prof = sp.sketch_rect_model(comp, plane, origin, size,
                                      name=f"{name}_Sk", ev=ev, anchor=anchor)
    prof = sp.smallest_profile(sk)
    tenon_ext = sp.ext_new(comp, prof, depth_expr, f"{name}_Tenon")
    tenon_b = tenon_ext.bodies.item(0)
    tenon_b.name = f"{name}_Tenon"

    result = {"tenon_ext": tenon_ext}

    # CUT mortise with tenon body BEFORE joining to rail.
    # This avoids coplanar face splitting (rail end face flush with leg).
    # combine routes intra-component when mortise_body shares a
    # component with tenon_b (== tenon_body.parentComponent), else to
    # root with assembly-context proxies.
    mort_cut = sp.combine(mortise_body, [tenon_b], CUT, True,
                               f"{name}_Mort")
    result["mortise_cut"] = mort_cut

    if mirror_plane:
        mir = sp.mirror_feats(comp, [tenon_ext], mirror_plane,
                              f"{name}_Mirror")
        mir_body = mir.bodies.item(0)

        # JOIN both into tenon_body (intra-component)
        join = sp.combine(tenon_body, [tenon_b, mir_body],
                          JOIN, False, f"{name}_Join")
        result["mirror"] = mir
    else:
        join = sp.combine(tenon_body, [tenon_b], JOIN, False,
                          f"{name}_Join")

    result["join"] = join
    return result


def bulk_cut_mortises(root_comp, mortise_body_proxy, tool_body_proxies,
                      name="Mortise"):
    """Bulk CUT multiple tenon bodies into a mortise piece.

    Use after building all tenons and JOINing them into their rails.
    The rail bodies (with tenons) become the CUT tools — the tenon
    overlap with the mortise piece creates the mortise pockets.

    Args:
        root_comp: Root component (CUT is at root level for cross-component).
        mortise_body_proxy: Assembly proxy of the mortise piece.
        tool_body_proxies: List of assembly proxies (rail bodies with tenons).
        name: Feature name.

    Returns:
        CombineFeature.
    """
    return sp.combine(mortise_body_proxy, tool_body_proxies,
                      CUT, True, name)
