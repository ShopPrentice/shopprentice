"""Tabletop button template — shop-made wooden fastener for cross-grain tops.

Also known as: desktop clip, wood top clip, shop-made top fastener,
L-block top holder, wooden tabletop clip.  Use this template when the user
describes small L-shaped wooden blocks that hold a tabletop to an apron or
frame while allowing seasonal wood movement (expansion / contraction).

A tabletop button is an L-shaped wooden block whose tongue rides in a slot
cut into the apron or cap.  The slot is elongated along the movement axis
(across the grain), allowing the top to expand and contract seasonally
without splitting.

Canonical orientation:
  Through axis = X  (tongue into apron, body toward table center)
  Width axis   = Y  (movement direction — slot elongated here)
  Drive axis   = Z  (button hangs below apron inner face)

Build order:
1. Sketch L-body profile (anchored to apron inner face) in through x drive
   plane, extrude symmetric by btn_w / 2
2. Sketch slot tool via sketch_slot_model (anchored), extrude into apron
3. Caller patterns the (body_ext, slot_ext) pair, mirrors, then bulk-CUTs
   the apron with all slot bodies

Usage:
    from woodworking.templates import tabletop_button as btn

    btn.define_params(params)

    be, se = btn.attach(
        comp=top_comp,
        apron=cap_l, apron_occ=caps_occ,
        button_plane=top_comp.xZConstructionPlane,
        button_plane_offset="y_mid - btn_off",
        apron_inner_face=("x", +1),
        apron_anchor_xyz=("cap_inner_x", "y_mid", "cap_top_z"),
        ci_expr="cap_inner_x",
        top_expr="cap_top_z",
        y_center_expr="y_mid - btn_off",
        sgn=+1,
        name="BTN", ev=ev)

    # Pattern any count — caller decides how many buttons per side:
    sp.feat_pattern(comp, be, axis, count_expr, "btn_off", "Btn_Pat")
    sp.feat_pattern(comp, se, axis, count_expr, "btn_off", "Slot_Pat")
    # mirror, bulk-CUT apron with slot bodies
"""

import adsk.core
import adsk.fusion

from helpers import sp

P3 = adsk.core.Point3D.create
VI = adsk.core.ValueInput.createByString

METADATA = {
    "name": "tabletop_button",
    "category": "top-attachment",
    "extends": None,
    "also_known_as": [
        "desktop clip", "wood top clip", "shop-made top fastener",
        "L-block top holder", "wooden tabletop clip",
    ],
    "variants": {
        "attach": {
            "description": "L-shaped wooden block with tongue in elongated apron/frame slot, allowing cross-grain movement",
            "best_for": ["tabletop attachment", "cross-grain movement",
                         "all-wood top fastening", "frame-to-panel connection"],
        },
    },
    "params": {
        "body_w": "Button width (movement axis, symmetric extrude)",
        "body_h": "Button body height (drive axis)",
        "body_len": "Body length toward table center (through axis)",
        "tongue_d": "Tongue depth into apron (through axis)",
        "tongue_h": "Tongue height (drive axis)",
        "slot_extra": "Slot overrun past button width for wood movement",
    },
}


def define_params(params, prefix="btn",
                  body_w="0.75 in", body_h="0.75 in",
                  body_len="0.625 in", tongue_d="0.625 in",
                  tongue_h="0.25 in", slot_extra="0.375 in"):
    """Define tabletop button parameters.

    Returns dict of parameter names keyed by short label.
    """
    p = prefix
    for pname, expr, unit, desc in [
        (f"{p}_w",          body_w,     "in", "Button width (Y)"),
        (f"{p}_h",          body_h,     "in", "Button body height (Z)"),
        (f"{p}_body_len",   body_len,   "in", "Body length toward center (X)"),
        (f"{p}_tongue_d",   tongue_d,   "in", "Tongue depth into apron (X)"),
        (f"{p}_tongue_h",   tongue_h,   "in", "Tongue height (Z)"),
        (f"{p}_slot_extra", slot_extra, "in", "Slot overrun for wood movement (Y)"),
    ]:
        if not params.itemByName(pname):
            params.add(pname, VI(expr), unit, desc)

    return {
        "w": f"{p}_w", "h": f"{p}_h", "body_len": f"{p}_body_len",
        "tongue_d": f"{p}_tongue_d", "tongue_h": f"{p}_tongue_h",
        "slot_extra": f"{p}_slot_extra",
    }


def attach(comp,
           apron, apron_occ,
           button_plane, button_plane_offset,
           apron_inner_face, apron_anchor_xyz,
           ci_expr, top_expr, y_center_expr,
           sgn,
           name="BTN", ev=None,
           prefix="btn"):
    """Build one tabletop button (L-body + apron slot tool).

    The button body hangs below the apron's inner-top edge.  The tongue
    extends into the apron; the slot tool is wider in Y for movement.

    Args:
        comp: Component to create features in (top component).
        apron: Apron/cap body (projected for anchoring).
        apron_occ: Occurrence of apron body's component.
        button_plane: Base construction plane for button sketch (through x drive).
        button_plane_offset: Offset expression (Y position of this button).
        apron_inner_face: (axis, dir) for the apron's inner face.
        apron_anchor_xyz: (x, y, z) model point on inner face for anchor_pt.
        ci_expr: Expression for apron inner face position (through axis).
        top_expr: Expression for top of button (apron top Z).
        y_center_expr: Expression for button center on width/movement axis.
        sgn: +1 or -1 — direction the button body extends from the apron
            (toward table center).  Tongue extends in -sgn direction.
        name: Feature name prefix.
        ev: Evaluator function.
        prefix: Parameter name prefix.

    Returns:
        (body_ext, slot_ext) — ExtrudeFeatures for the caller to pattern,
        mirror, then bulk-CUT the apron with all slot bodies.
    """
    if ev is None:
        ev = sp._make_ev()

    p = prefix

    # ── Apron inner-face reference helper ──
    face_ax, face_dir = apron_inner_face

    def _anchor(sk, face_ax=face_ax, face_dir=face_dir):
        for fa, fd in [(face_ax, face_dir),
                       ("z", +1)]:
            face = sp.find_face(apron, fa, fd)
            if face is not None:
                if apron_occ is not None:
                    face = face.createForAssemblyContext(apron_occ)
                sk.project(face)
        sp.refs_to_construction(sk)
        return sp.anchor_pt(sk,
                            ev(apron_anchor_xyz[0]),
                            ev(apron_anchor_xyz[1]),
                            ev(apron_anchor_xyz[2]))

    # ── 1. L-body profile ──
    bpl = sp.off_plane(comp, button_plane, button_plane_offset,
                        f"{name}_Pl")
    sk = comp.sketches.add(bpl)
    sk.name = f"{name}_Sk"
    orient = sp.probe_orientations(
        sk, ev(ci_expr), ev(y_center_expr), ev(top_expr))
    m2s = sk.modelToSketchSpace
    anchor = _anchor(sk)

    ci = ev(ci_expr)
    ymv = ev(y_center_expr)
    tu = ev(top_expr)
    bl = ev(f"{p}_body_len")
    td = ev(f"{p}_tongue_d")
    bh = ev(f"{p}_h")
    th = ev(f"{p}_tongue_h")
    bot = tu - bh
    ttop = bot + th
    bxe = ci + sgn * bl
    txe = ci - sgn * td

    pts = [(txe, bot), (bxe, bot), (bxe, tu), (ci, tu), (ci, ttop), (txe, ttop)]
    Pp = [m2s(P3(x, ymv, z)) for (x, z) in pts]
    sptp = [P3(pp.x, pp.y, 0) for pp in Pp]
    lines = sk.sketchCurves.sketchLines
    L = [lines.addByTwoPoints(sptp[0], sptp[1])]
    for k in range(1, 5):
        L.append(lines.addByTwoPoints(L[-1].endSketchPoint, sptp[k + 1]))
    L.append(lines.addByTwoPoints(L[-1].endSketchPoint, L[0].startSketchPoint))

    gc = sk.geometricConstraints
    H_DIM = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    through_ax = face_ax
    drive_ax = 'z' if through_ax != 'z' else 'x'
    for ln_, ax in [(L[0], through_ax), (L[2], through_ax), (L[4], through_ax),
                    (L[1], drive_ax), (L[3], drive_ax), (L[5], drive_ax)]:
        try:
            if orient[ax] == H_DIM:
                gc.addHorizontal(ln_)
            else:
                gc.addVertical(ln_)
        except Exception:
            pass

    d = sk.sketchDimensions
    sp.rdim(sk, d, L[2].startSketchPoint, L[2].endSketchPoint,
            orient, through_ax, f"{p}_body_len")
    sp.rdim(sk, d, L[1].startSketchPoint, L[1].endSketchPoint,
            orient, drive_ax, f"{p}_h")
    sp.rdim(sk, d, L[3].startSketchPoint, L[3].endSketchPoint,
            orient, drive_ax, f"{p}_h - {p}_tongue_h")
    sp.rdim(sk, d, L[4].startSketchPoint, L[4].endSketchPoint,
            orient, through_ax, f"{p}_tongue_d")
    sp.rdim(sk, d, L[5].startSketchPoint, L[5].endSketchPoint,
            orient, drive_ax, f"{p}_tongue_h")

    if anchor is not None:
        try:
            gc.addCoincident(L[2].endSketchPoint, anchor)
        except Exception:
            pass

    be = sp.ext_new_sym(comp, sp.smallest_profile(sk),
                         f"{p}_w / 2", name)
    be.bodies.item(0).name = name

    # ── 2. Slot tool (stadium, elongated for movement) ──
    spl = sp.off_plane(comp, button_plane, button_plane_offset,
                        f"{name}Slot_SlotPl")
    slot_center = (ci_expr,
                   y_center_expr,
                   f"{top_expr} - {p}_h + {p}_tongue_h / 2")
    ssk, sprof = sp.sketch_slot_model(
        comp, spl, slot_center,
        long_model_axis=drive_ax,
        long_expr=f"{p}_tongue_h",
        short_expr=f"{p}_tongue_d",
        name=f"{name}Slot_Sk", ev=ev,
        anchor={
            "parent_body": apron,
            "parent_occ": apron_occ,
            "face_axis": face_ax,
            "face_dir": face_dir,
            "anchor_xyz": apron_anchor_xyz,
            "off": (
                (through_ax, f"{p}_tongue_d / 2"),
                (drive_ax, f"{top_expr} - ({top_expr} - {p}_h + {p}_tongue_h / 2)"),
            ),
        })
    se = sp.ext_new_sym(comp, sprof,
                         f"{p}_w / 2 + {p}_slot_extra", f"{name}Slot")
    se.bodies.item(0).name = f"{name}Slot"

    return be, se
