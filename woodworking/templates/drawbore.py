"""Drawbore Mortise & Tenon joint template.

Extends M&T with offset drawbore pins that pull the tenon tight into the
mortise. The pin holes in the tenon are at 1/3 of the tenon depth from
the shoulder. Two pins per tenon is standard.

Build order:
1. Sketch tenon on construction plane at outer end, extrude inward
2. Sketch 2 pin circles on perpendicular plane, extrude through mortise piece
3. Mirror tenon + pins to other end
4. JOIN tenons to stretcher, CUT with pins

Usage:
    from woodworking.templates import drawbore as db

    db.define_params(params, prefix="db",
        tenon_w="ls_w", tenon_thick="1.5 in",
        pin_dia="0.375 in", pin_sp="2 in")

    # Through drawbore (stretcher into leg).
    # Tenon extrudes in +X (plane normal of yZ). Pins must extrude in
    # a perpendicular axis — here in Y, so pin_plane = xZ (normal Y).
    # pin_plane_offset places the sketch plane at the near cheek; the
    # pin then runs across the tenon and out the far side.
    result = db.through(
        comp=ls_c,
        tenon_plane=root.yZConstructionPlane,
        tenon_plane_offset="leg_setback - ls_proud",
        tenon_origin=("leg_setback - ls_proud",
                       "(leg_d - db_tt) / 2", "ls_z"),
        tenon_size={"y": "db_tt", "z": "db_tw"},
        tenon_depth="leg_w + ls_proud",
        pin_plane=root.xZConstructionPlane,
        pin_plane_offset="0 in",                     # near cheek at Y=0
        pin_tenon_pos_expr="leg_setback + 2 * leg_w / 3",
        pin_z_ctr="ls_z + ls_w / 2",
        pin_through="leg_d",
        stretcher=ls_front,
        name="DB_L", ev=ev)
"""

import adsk.core
import adsk.fusion

from helpers import sp

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation

METADATA = {
    "name": "drawbore",
    "category": "joinery",
    "extends": "mortise_tenon",
    "variants": {
        "through": {
            "description": "Tenon through mortise piece + proud, pins through both cheeks",
            "best_for": ["workbench stretchers", "trestle tables", "timber frames"],
        },
        "blind": {
            "description": "Tenon stops inside mortise piece, pins through outer cheek only",
            "best_for": ["hidden structural joints", "furniture stretchers"],
        },
    },
    "params": {
        "tenon_w": "Tenon width (across grain, often full stretcher height)",
        "tenon_thick": "Tenon thickness (narrower than stretcher)",
        "pin_dia": "Drawbore pin diameter",
        "pin_sp": "Spacing between 2 pins (center to center)",
    },
}


def define_params(params, prefix="db",
                  tenon_w="3 in", tenon_thick="1.5 in",
                  pin_dia="0.375 in", pin_sp="2 in"):
    """Define drawbore joint parameters.

    Args:
        params: design.userParameters
        prefix: Parameter name prefix.
        tenon_w: Tenon width (across grain).
        tenon_thick: Tenon thickness.
        pin_dia: Pin diameter.
        pin_sp: Spacing between 2 pins.

    Returns:
        Dict of parameter names.
    """
    VI = adsk.core.ValueInput.createByString
    p = prefix

    params.add(f"{p}_tw", VI(tenon_w), "in", "Drawbore tenon width")
    params.add(f"{p}_tt", VI(tenon_thick), "in", "Drawbore tenon thickness")
    params.add(f"{p}_pin_dia", VI(pin_dia), "in", "Drawbore pin diameter")
    params.add(f"{p}_pin_sp", VI(pin_sp), "in", "Drawbore pin spacing")

    return {
        "tw": f"{p}_tw", "tt": f"{p}_tt",
        "pin_dia": f"{p}_pin_dia", "pin_sp": f"{p}_pin_sp",
    }


def through(comp, tenon_plane, tenon_plane_offset, tenon_origin, tenon_size,
            tenon_depth, pin_plane, pin_plane_offset, pin_tenon_pos_expr,
            pin_z_ctr, pin_through, stretcher=None, name="DB", ev=None,
            mirror_plane=None,
            pin_dia_expr="db_pin_dia", pin_sp_expr="db_pin_sp",
            combine=True):
    """Create a through drawbore M&T joint.

    The tenon construction plane is at the outer end (proud face).
    Default extrude direction goes inward toward the stretcher.

    Pin construction plane is perpendicular to the tenon direction so
    pins cross the tenon side-faces (not run parallel to the tenon).
    Pins at 1/3 of tenon depth from the shoulder, 2 per tenon.

    Args:
        comp: Component to create features in.
        tenon_plane: Base construction plane for tenon (e.g., root.yZConstructionPlane).
        tenon_plane_offset: Offset expression for tenon plane (outer end position).
        tenon_origin: (x, y, z) model-space origin for tenon rectangle.
        tenon_size: {axis: expr, axis: expr} for tenon cross-section.
        tenon_depth: Extrude depth expression (e.g., "leg_w + ls_proud").
        pin_plane: Base construction plane for pins — must be
            perpendicular to the tenon extrude direction. If tenon
            extrudes in X, pass xZ or xY plane. The pin's extrude
            direction is the pin_plane's normal.
        pin_plane_offset: Expression for pin_plane's offset toward the
            pin-entry face (in pin_plane's normal direction). Pick a
            value so the offset plane sits just outside the near cheek;
            the pin then extrudes through the tenon and out the far
            cheek for ``pin_through`` distance.
        pin_tenon_pos_expr: Expression for pin-center position along
            the tenon axis (e.g., "leg_w * 2 / 3" — 1/3 from shoulder).
        pin_z_ctr: Expression for pin center along the tenon's second
            in-plane axis (typically Z, the stretcher mid-height).
        pin_through: Extrude depth for pin (e.g., "leg_d") — long
            enough to fully cross the tenon thickness.
        stretcher: Stretcher body to JOIN tenon into.
        name: Feature name prefix.
        ev: Evaluator function.
        mirror_plane: If provided, mirrors tenon + pins to opposite end.
        pin_dia_expr: Parameter expression for pin diameter.
        pin_sp_expr: Parameter expression for pin spacing.

    Returns:
        Dict with 'tenon_ext', 'pin_bodies', 'mirror' (if mirror_plane),
        'join', 'pin_cut'.
    """
    if ev is None:
        ev = sp._make_ev()

    P = adsk.core.Point3D
    result = {}

    # 1. Tenon
    t_pl = sp.off_plane(comp, tenon_plane, tenon_plane_offset, f"{name}_Pl")
    _, pr = sp.sketch_rect_model(comp, t_pl, tenon_origin, tenon_size,
                                  f"{name}_Sk", ev=ev)
    tenon_ext = sp.ext_new(comp, pr, tenon_depth, f"{name}_Tenon")
    tenon_body = tenon_ext.bodies.item(0)
    tenon_body.name = f"{name}_Tenon"
    result["tenon_ext"] = tenon_ext

    # 2. Pins — axis-aware placement and dimensioning.
    # Detect tenon axis from tenon_size (the missing axis).
    size_axes = set(tenon_size.keys())
    tenon_ax = [a for a in 'xyz' if a not in size_axes][0]

    p_pl = sp.off_plane(comp, pin_plane, pin_plane_offset, f"{name}Pin_Pl")
    pin_sk = comp.sketches.add(p_pl)
    pin_sk.name = f"{name}Pin_Sk"
    m = pin_sk.modelToSketchSpace

    # Detect pin plane normal from sketch transform — the axis with
    # zero in-plane displacement is the normal (pin extrude direction).
    _base = m(P.create(0, 0, 0))
    _disp = {}
    for _a, _tp in [('x', P.create(1,0,0)), ('y', P.create(0,1,0)), ('z', P.create(0,0,1))]:
        _mp = m(_tp)
        _disp[_a] = ((_mp.x - _base.x)**2 + (_mp.y - _base.y)**2)**0.5
    normal_ax = min(_disp, key=_disp.get)
    in_plane = [a for a in 'xyz' if a != normal_ax]
    spacing_ax = [a for a in in_plane if a != tenon_ax][0] if tenon_ax in in_plane else in_plane[0]
    ax_idx = {'x': 0, 'y': 1, 'z': 2}

    _pin_r = ev(pin_dia_expr) / 2
    _pin_half_sp = ev(pin_sp_expr) / 2
    _zc = ev(pin_z_ctr)
    _px = ev(pin_tenon_pos_expr)
    _nv_expr = tenon_origin[ax_idx[normal_ax]]
    _nv = ev(_nv_expr) if isinstance(_nv_expr, str) else _nv_expr

    for sp_off in [-_pin_half_sp, _pin_half_sp]:
        pt = {tenon_ax: _px, spacing_ax: _zc + sp_off, normal_ax: _nv}
        ctr = m(P.create(pt['x'], pt['y'], pt['z']))
        pin_sk.sketchCurves.sketchCircles.addByCenterRadius(
            P.create(ctr.x, ctr.y, 0), _pin_r)

    # Dimensions — use probe_orientations for correct H/V on any plane
    probe_pt = {tenon_ax: _px, spacing_ax: _zc, normal_ax: _nv}
    orient = sp.probe_orientations(pin_sk,
                                   probe_pt['x'], probe_pt['y'], probe_pt['z'])
    d = pin_sk.sketchDimensions
    c0 = pin_sk.sketchCurves.sketchCircles.item(0)
    c1 = pin_sk.sketchCurves.sketchCircles.item(1)
    g0 = c0.centerSketchPoint.geometry
    g1 = c1.centerSketchPoint.geometry

    d.addRadialDimension(c0, P.create(g0.x + 0.5, g0.y, 0)
    ).parameter.expression = f"{pin_dia_expr} / 2"
    d.addRadialDimension(c1, P.create(g1.x + 0.5, g1.y, 0)
    ).parameter.expression = f"{pin_dia_expr} / 2"

    d.addDistanceDimension(pin_sk.originPoint, c0.centerSketchPoint,
        orient[tenon_ax], P.create(g0.x / 2, g0.y - 1, 0)
    ).parameter.expression = pin_tenon_pos_expr
    d.addDistanceDimension(pin_sk.originPoint, c0.centerSketchPoint,
        orient[spacing_ax], P.create(g0.x - 1, g0.y / 2, 0)
    ).parameter.expression = f"{pin_z_ctr} - {pin_sp_expr} / 2"
    d.addDistanceDimension(c0.centerSketchPoint, c1.centerSketchPoint,
        orient[spacing_ax], P.create(g0.x - 1, (g0.y + g1.y) / 2, 0)
    ).parameter.expression = pin_sp_expr

    sp.refs_to_construction(pin_sk)
    pin_bodies = []
    for j in range(pin_sk.profiles.count):
        p = pin_sk.profiles.item(j)
        if p.areaProperties().area < 1.0:
            ext = sp.ext_new(comp, p, pin_through, f"{name}Pin_{j}")
            ext.bodies.item(0).name = f"{name}Pin_{j}"
            pin_bodies.append(ext.bodies.item(0))
    result["tenon_body"] = tenon_body
    result["pin_bodies"] = pin_bodies

    # 3. Mirror tenon + pins to other end
    if mirror_plane:
        mir = sp.mirror_bodies(comp, [tenon_body] + pin_bodies,
                                mirror_plane, f"{name}_Mirror")
        result["mirror"] = mir

    # 4. JOIN tenons, CUT with pins
    if combine and stretcher is not None:
        all_tenons = [b for b in _all_bodies(comp) if "Tenon" in b.name
                      and name in b.name]
        all_pins = [b for b in _all_bodies(comp) if "Pin" in b.name
                    and name in b.name]

        if all_tenons:
            sp.combine(stretcher, all_tenons, JOIN, False, f"{name}_Join")
            result["join"] = True

        if all_pins:
            sp.combine(stretcher, all_pins, CUT, True, f"{name}_PinCut")
            result["pin_cut"] = True

    return result


def blind(comp, tenon_plane, tenon_plane_offset, tenon_origin, tenon_size,
          tenon_depth, pin_plane, pin_plane_offset, pin_tenon_pos_expr,
          pin_z_ctr, pin_through, stretcher=None, name="DBB", ev=None,
          mirror_plane=None,
          pin_dia_expr="db_pin_dia", pin_sp_expr="db_pin_sp",
          combine=True):
    """Create a blind drawbore M&T joint.

    Same as through() but the tenon stops inside the mortise piece.
    The construction plane is at the blind stop point.

    All args same as through(). tenon_depth is the blind penetration
    (e.g., "leg_d - st_blind").
    """
    return through(comp, tenon_plane, tenon_plane_offset, tenon_origin,
                   tenon_size, tenon_depth, pin_plane, pin_plane_offset,
                   pin_tenon_pos_expr, pin_z_ctr, pin_through, stretcher,
                   name=name, ev=ev, mirror_plane=mirror_plane,
                   pin_dia_expr=pin_dia_expr, pin_sp_expr=pin_sp_expr,
                   combine=combine)


def _all_bodies(comp):
    """Get all bodies in a component."""
    return [comp.bRepBodies.item(i) for i in range(comp.bRepBodies.count)]
