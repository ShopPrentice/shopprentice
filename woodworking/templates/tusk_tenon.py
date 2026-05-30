"""Tusk tenon (knock-down through-tenon) template.

A through-tenon that protrudes past the receiver (leg/post), locked by a
tapered key driven perpendicular to the tenon axis.  Unlike tenon_wedge
(which spreads the tenon permanently), the tusk is knock-down: tap the key
out to disassemble.  Driving the key in draws the shoulder tight because it
tapers thicker toward the drive direction.

Canonical orientation (rotate planes for other layouts):
  Through axis = X  (rail tenon passes through leg, protrudes proud)
  Width axis   = Y  (tenon width, key blade width)
  Drive axis   = Z  (key driven down)

Build order:
1. Sketch tenon rectangle (anchored) at shoulder face -> extrude through
   receiver + proud -> CUT receiver (through-mortise), JOIN to rail
2. Sketch tapered key trapezoid (anchored) in through x drive plane ->
   extrude symmetric by blade width -> CUT rail tenon (keepTool) ->
   angled mortise in tenon, key body remains
3. Optional mirror to second receiver

Usage:
    from woodworking.templates import tusk_tenon as tk

    tk.define_params(params)

    result = tk.through(
        comp=rail_comp,
        receiver=post_l, receiver_occ=posts_occ,
        rail=rail_body,
        tenon_plane=root.yZConstructionPlane,
        tenon_plane_offset="post_thick",
        tenon_origin=("post_thick",
                       "(post_w - tk_tw) / 2",
                       "rail_z + (rail_h - tk_th) / 2"),
        tenon_size={"y": "tk_tw", "z": "tk_th"},
        tenon_depth="post_thick + tk_proud",
        tenon_anchor={
            "parent_body": post_l, "parent_occ": posts_occ,
            "face_axis": "z", "face_dir": +1,
            "anchor_xyz": ("post_thick", "post_w", "post_h"),
            "off1": ("y", "(post_w + tk_tw) / 2"),
            "off2": ("z", "post_h - rail_z - (rail_h + tk_th) / 2"),
            "which": 2,
        },
        key_plane=rail_comp.xZConstructionPlane,
        key_plane_offset="post_w / 2",
        key_bearing_face=("x", -1),
        key_anchor_xyz=("0 in", "post_w / 2", "post_h"),
        key_center_expr="rail_z + rail_h / 2",
        key_anchor_offset_expr="post_h - rail_z - rail_h / 2 + tk_key_len / 2",
        name="TK_L", ev=ev)

    # Caller CUTs mirrored receiver if using mirror_plane + mirror_receiver.
"""

import adsk.core
import adsk.fusion

from helpers import sp

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
P3 = adsk.core.Point3D.create
VI = adsk.core.ValueInput.createByString

METADATA = {
    "name": "tusk_tenon",
    "category": "joinery",
    "extends": "mortise_tenon",
    "variants": {
        "through": {
            "description": "Through-tenon + tapered key for knock-down assembly",
            "best_for": ["trestle tables", "knock-down furniture", "timber frames"],
        },
    },
    "params": {
        "tenon_w": "Tenon width (cross-grain)",
        "tenon_h": "Tenon height",
        "proud": "How far tenon protrudes past receiver",
        "key_thin": "Key thickness at thin (entry) end",
        "key_taper_ang": "Key taper angle (draws shoulder tight)",
        "key_blade": "Key blade width (MUST be < tenon width)",
        "key_len": "Key length along drive axis",
    },
}


def define_params(params, prefix="tk",
                  tenon_w="2 in", tenon_h="1.5 in",
                  proud="1 in",
                  key_thin="0.25 in", key_taper_ang="8 deg",
                  key_blade="0.375 in", key_len="6 in"):
    """Define tusk tenon parameters.

    Returns dict of parameter names keyed by short label.
    """
    p = prefix
    for pname, expr, unit, desc in [
        (f"{p}_tw",        tenon_w,       "in",  "Tusk tenon width"),
        (f"{p}_th",        tenon_h,       "in",  "Tusk tenon height"),
        (f"{p}_proud",     proud,         "in",  "Tenon proud protrusion"),
        (f"{p}_key_thin",  key_thin,      "in",  "Key thin-end thickness"),
        (f"{p}_key_ang",   key_taper_ang, "deg", "Key taper angle"),
        (f"{p}_key_blade", key_blade,     "in",  "Key blade width"),
        (f"{p}_key_len",   key_len,       "in",  "Key length"),
    ]:
        if not params.itemByName(pname):
            params.add(pname, VI(expr), unit, desc)

    taper_name = f"{p}_key_taper"
    if not params.itemByName(taper_name):
        params.add(taper_name,
                   VI(f"{p}_key_len * tan({p}_key_ang)"),
                   "in", "Key taper run (derived)")

    return {
        "tw": f"{p}_tw", "th": f"{p}_th", "proud": f"{p}_proud",
        "key_thin": f"{p}_key_thin", "key_ang": f"{p}_key_ang",
        "key_blade": f"{p}_key_blade", "key_len": f"{p}_key_len",
        "key_taper": taper_name,
    }


def through(comp,
            receiver, receiver_occ,
            rail,
            tenon_plane, tenon_plane_offset,
            tenon_origin, tenon_size, tenon_depth,
            tenon_anchor,
            key_plane, key_plane_offset,
            key_bearing_face, key_anchor_xyz,
            key_center_expr, key_anchor_offset_expr,
            name="TK", ev=None,
            mirror_plane=None,
            mirror_receiver=None, mirror_receiver_occ=None,
            prefix="tk",
            combine=True):
    """Create a tusk (knock-down) through-tenon joint.

    Builds one tenon + one tapered key.  With ``mirror_plane``, mirrors
    both to the opposite end; pass ``mirror_receiver``/``mirror_receiver_occ``
    so the mirrored tenon also CUTs the second receiver.

    Args:
        comp: Component to create features in (rail/stretcher component).
        receiver: Receiver body (post/leg) for the through-mortise CUT.
        receiver_occ: Occurrence of receiver's component.
        rail: Rail/stretcher body the tenon JOINs to.
        tenon_plane: Base construction plane for tenon sketch.
        tenon_plane_offset: Offset expression placing plane at the shoulder.
        tenon_origin: (x, y, z) model-space corner of tenon rectangle.
        tenon_size: {axis: expr, axis: expr} tenon cross-section.
        tenon_depth: Extrude depth expression (receiver_thick + proud).
        tenon_anchor: Dict for sketch_rect_model ANCHORED mode.
        key_plane: Base construction plane for key sketch (through x drive plane).
        key_plane_offset: Offset expression centering key on tenon width.
        key_bearing_face: (axis, dir) for receiver's far face where key bears.
        key_anchor_xyz: (x, y, z) model point on far face for anchor_pt.
        key_center_expr: Expression for key center along drive axis.
        key_anchor_offset_expr: Expression for drive-axis distance from
            anchor to key bottom (vertex A).  Must be positive.
        name: Feature name prefix.
        ev: Evaluator function.
        mirror_plane: Construction plane to mirror tenon + key across.
        mirror_receiver: Second receiver body (CUT with mirrored tenon).
        mirror_receiver_occ: Occurrence for mirror_receiver.
        prefix: Parameter name prefix.
        combine: If True, CUT receiver and JOIN rail.

    Returns:
        Dict with tenon_body, key_body, tenon_ext, key_ext, and optionally
        mirror, mirror_tenon, mirror_key.
    """
    if ev is None:
        ev = sp._make_ev()

    result = {}

    # ── 1. Through-tenon (anchored rectangle) ──
    t_pl = sp.off_plane(comp, tenon_plane, tenon_plane_offset, f"{name}_Pl")
    _, pr = sp.sketch_rect_model(comp, t_pl, tenon_origin, tenon_size,
                                  f"{name}_Sk", ev=ev, anchor=tenon_anchor)
    tenon_ext = sp.ext_new(comp, pr, tenon_depth, f"{name}_Tenon")
    tenon_body = tenon_ext.bodies.item(0)
    tenon_body.name = f"{name}_Tenon"
    result["tenon_ext"] = tenon_ext
    result["tenon_body"] = tenon_body

    # ── 2. CUT receiver (keepTool) before mirror/JOIN ──
    if combine and receiver is not None:
        sp.combine(receiver, [tenon_body], CUT, True, f"{name}_Mort")

    # ── 3. Tapered key ──
    through_ax = [a for a in 'xyz' if a not in tenon_size][0]
    k_pl = sp.off_plane(comp, key_plane, key_plane_offset, f"{name}Key_Pl")
    k_sk = comp.sketches.add(k_pl)
    k_sk.name = f"{name}Key_Sk"
    m2s = k_sk.modelToSketchSpace

    _base = m2s(P3(0, 0, 0))
    _disps = {}
    for _a, _tp in [('x', P3(1, 0, 0)), ('y', P3(0, 1, 0)), ('z', P3(0, 0, 1))]:
        _mp = m2s(_tp)
        _disps[_a] = ((_mp.x - _base.x) ** 2 + (_mp.y - _base.y) ** 2) ** 0.5
    width_ax = min(_disps, key=_disps.get)
    drive_ax = [a for a in 'xyz' if a != through_ax and a != width_ax][0]
    ax_idx = {'x': 0, 'y': 1, 'z': 2}

    bf_axis, bf_dir = key_bearing_face
    orient = sp.probe_orientations(
        k_sk,
        ev(key_anchor_xyz[0]), ev(key_anchor_xyz[1]), ev(key_anchor_xyz[2]))

    bearing_v = ev(key_anchor_xyz[ax_idx[through_ax]])
    center_v = ev(key_center_expr)
    width_v = ev(key_anchor_xyz[ax_idx[width_ax]])
    half_len = ev(f"{prefix}_key_len") / 2
    thin_v = ev(f"{prefix}_key_thin")
    taper_v = ev(f"{prefix}_key_taper")
    sign = bf_dir

    def _mkv(thru, drv):
        pt = [0.0, 0.0, 0.0]
        pt[ax_idx[through_ax]] = thru
        pt[ax_idx[drive_ax]] = drv
        pt[ax_idx[width_ax]] = width_v
        return pt

    vA = _mkv(bearing_v, center_v - half_len)
    vB = _mkv(bearing_v + sign * thin_v, center_v - half_len)
    vC = _mkv(bearing_v + sign * (thin_v + taper_v), center_v + half_len)
    vD = _mkv(bearing_v, center_v + half_len)

    def _s(v):
        p = m2s(P3(v[0], v[1], v[2]))
        return P3(p.x, p.y, 0)

    pA, pB, pC, pD = _s(vA), _s(vB), _s(vC), _s(vD)
    ln = k_sk.sketchCurves.sketchLines
    lAB = ln.addByTwoPoints(pA, pB)
    lBC = ln.addByTwoPoints(lAB.endSketchPoint, pC)
    lCD = ln.addByTwoPoints(lBC.endSketchPoint, pD)
    lDA = ln.addByTwoPoints(lCD.endSketchPoint, lAB.startSketchPoint)

    H_DIM = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    gc = k_sk.geometricConstraints
    for line, ax in [(lAB, through_ax), (lCD, through_ax), (lDA, drive_ax)]:
        try:
            if orient[ax] == H_DIM:
                gc.addHorizontal(line)
            else:
                gc.addVertical(line)
        except Exception:
            pass

    sp.project_face(k_sk, receiver, receiver_occ, bf_axis, bf_dir)
    aP = sp.anchor_pt(k_sk,
                       ev(key_anchor_xyz[0]),
                       ev(key_anchor_xyz[1]),
                       ev(key_anchor_xyz[2]))
    d = k_sk.sketchDimensions
    A_pt = lAB.startSketchPoint
    B_pt = lAB.endSketchPoint
    D_pt = lCD.endSketchPoint
    C_pt = lBC.endSketchPoint

    if aP is not None:
        sp.rdim(k_sk, d, aP, A_pt, orient, through_ax, "0 in")
        sp.rdim(k_sk, d, aP, A_pt, orient, drive_ax, key_anchor_offset_expr)
    sp.rdim(k_sk, d, A_pt, B_pt, orient, through_ax, f"{prefix}_key_thin")
    sp.rdim(k_sk, d, A_pt, D_pt, orient, drive_ax, f"{prefix}_key_len")
    sp.rdim(k_sk, d, D_pt, C_pt, orient, through_ax,
            f"{prefix}_key_thin + {prefix}_key_taper")

    prof = sp.smallest_profile(k_sk)
    key_ext = sp.ext_new_sym(comp, prof,
                              f"{prefix}_key_blade / 2", f"{name}_Key")
    key_body = key_ext.bodies.item(0)
    key_body.name = f"{name}_Key"
    result["key_ext"] = key_ext
    result["key_body"] = key_body

    # ── 4. Mirror tenon + key ──
    if mirror_plane:
        mir = sp.mirror_bodies(comp, [tenon_body, key_body],
                                mirror_plane, f"{name}_Mir")
        result["mirror"] = mir
        mir_tenon = None
        mir_key = None
        for i in range(mir.bodies.count):
            b = mir.bodies.item(i)
            if "Tenon" in b.name:
                mir_tenon = b
                b.name = f"{name}_Tenon_Mir"
            else:
                mir_key = b
                b.name = f"{name}_Key_Mir"
        result["mirror_tenon"] = mir_tenon
        result["mirror_key"] = mir_key

        if combine and mirror_receiver is not None and mir_tenon is not None:
            sp.combine(mirror_receiver, [mir_tenon], CUT, True,
                       f"{name}_Mort_Mir")

    # ── 5. JOIN all tenons to rail ──
    if combine and rail is not None:
        all_tenons = [b for b in _all_bodies(comp)
                      if "Tenon" in b.name and name in b.name]
        if all_tenons:
            sp.combine(rail, all_tenons, JOIN, False, f"{name}_Join")

    # ── 6. CUT rail with all keys (keepTool) ──
    if combine and rail is not None:
        all_keys = [b for b in _all_bodies(comp)
                    if "Key" in b.name and name in b.name]
        for kb in all_keys:
            sp.combine(rail, [kb], CUT, True, f"{kb.name}_Slot")

    return result


def _all_bodies(comp):
    return [comp.bRepBodies.item(i) for i in range(comp.bRepBodies.count)]
