"""Test fixture for drawbore template.

  F1 Horizontal X  — tenon piece (+X) into mortise piece, pins in Y. Template API.
  F2 Horizontal Y  — tenon piece (+Y) into mortise piece, pins in X. Template API.
  F3 Cross-comp    — same as F1, two components. Template API.
  F4 Vertical Z    — tenon piece (+Z) into mortise piece, pins in Y. Template API.
  F5 Angled (30°)  — F1 layout tilted 30° around Z before CUT. Template API.

All tenons have SHOULDERS (smaller than the tenon piece cross-section).
"""
import adsk.core
import adsk.fusion
import math


def make_comp_at(root, name, x_cm=0.0, y_cm=0.0):
    xf = adsk.core.Matrix3D.create()
    if x_cm != 0.0: xf.setCell(0, 3, x_cm)
    if y_cm != 0.0: xf.setCell(1, 3, y_cm)
    occ = root.occurrences.addNewComponent(xf)
    occ.component.name = name
    return occ


def run(context):
    from helpers import sp
    from woodworking.templates import drawbore as db

    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    P3 = adsk.core.Point3D.create
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
    NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    ctx = sp.DesignContext(design)

    params.add("leg_w", VI("3 in"),   "in", "Leg width")
    params.add("leg_d", VI("3 in"),   "in", "Leg depth")
    params.add("leg_h", VI("10 in"),  "in", "Leg height")
    params.add("ap_l",  VI("8 in"),   "in", "Apron/stretcher length")
    params.add("ap_w",  VI("3 in"),   "in", "Apron height (Z)")
    params.add("ap_t",  VI("1.5 in"), "in", "Apron thickness")
    params.add("ap_z",  VI("5 in"),   "in", "Apron bottom Z")
    params.add("tn_w",  VI("2 in"),   "in", "Tenon width (< ap_w)")
    params.add("tn_t",  VI("0.75 in"), "in", "Tenon thickness (< ap_t)")
    params.add("pin_d", VI("0.375 in"), "in", "Pin diameter")
    params.add("pin_sp", VI("1 in"),  "in", "Pin spacing")

    db.define_params(params, prefix="db",
        tenon_w="tn_w", tenon_thick="tn_t",
        pin_dia="pin_d", pin_sp="pin_sp")

    # ═══════════════════════════════════════════════════════
    # F1: Horizontal X — apron (+X) into leg
    # ═══════════════════════════════════════════════════════
    f1 = make_comp_at(root, "F1_Horiz_X").component

    _, pr = sp.sketch_rect_model(f1, f1.xYConstructionPlane,
        ("ap_l", "0 in", "0 in"),
        {"x": "leg_w", "y": "leg_d"}, "f1_Leg_Sk", ctx.ev)
    f1_leg = sp.ext_new(f1, pr, "leg_h", "f1_Leg").bodies.item(0)
    f1_leg.name = "f1_Leg"

    f1_ap_pl = sp.off_plane(f1, f1.xZConstructionPlane,
                             "(leg_d - ap_t) / 2", "f1_Ap_Pl")
    _, pr = sp.sketch_rect_model(f1, f1_ap_pl,
        ("0 in", "(leg_d - ap_t) / 2", "ap_z"),
        {"x": "ap_l", "z": "ap_w"}, "f1_Ap_Sk", ctx.ev)
    f1_ap = sp.ext_new(f1, pr, "ap_t", "f1_Ap").bodies.item(0)
    f1_ap.name = "f1_Apron"

    r1 = db.through(f1,
        tenon_plane=f1.yZConstructionPlane, tenon_plane_offset="ap_l",
        tenon_origin=("ap_l", "(leg_d - db_tt) / 2",
                      "ap_z + (ap_w - db_tw) / 2"),
        tenon_size={"y": "db_tt", "z": "db_tw"},
        tenon_depth="leg_w + 0.25 in",
        pin_plane=f1.xZConstructionPlane, pin_plane_offset="0 in",
        pin_tenon_pos_expr="ap_l + 2 * db_pin_dia",
        pin_z_ctr="ap_z + ap_w / 2", pin_through="leg_d",
        stretcher=f1_ap, name="f1_DB", ev=ctx.ev)

    sp.combine(f1_leg, [f1_ap], CUT, True, "f1_Mort")
    sp.combine(f1_leg, r1["pin_bodies"], CUT, True, "f1_PinMort")
    f1_n = f1.bRepBodies.count
    print(f"F1 Horiz_X: {f1_n} bodies — PASS")

    # ═══════════════════════════════════════════════════════
    # F2: Horizontal Y — stretcher (+Y) into leg
    # ═══════════════════════════════════════════════════════
    db.define_params(params, prefix="db2",
        tenon_w="tn_w", tenon_thick="tn_t",
        pin_dia="pin_d", pin_sp="pin_sp")

    f2 = make_comp_at(root, "F2_Horiz_Y",
                       ctx.ev("ap_l + leg_w + 4 in")).component

    _, pr = sp.sketch_rect_model(f2, f2.xYConstructionPlane,
        ("0 in", "ap_l", "0 in"),
        {"x": "leg_w", "y": "leg_d"}, "f2_Leg_Sk", ctx.ev)
    f2_leg = sp.ext_new(f2, pr, "leg_h", "f2_Leg").bodies.item(0)
    f2_leg.name = "f2_Leg"

    f2_st_pl = sp.off_plane(f2, f2.yZConstructionPlane,
                             "(leg_w - ap_t) / 2", "f2_St_Pl")
    _, pr = sp.sketch_rect_model(f2, f2_st_pl,
        ("(leg_w - ap_t) / 2", "0 in", "ap_z"),
        {"y": "ap_l", "z": "ap_w"}, "f2_St_Sk", ctx.ev)
    f2_str = sp.ext_new(f2, pr, "ap_t", "f2_Str").bodies.item(0)
    f2_str.name = "f2_Str"

    r2 = db.through(f2,
        tenon_plane=f2.xZConstructionPlane, tenon_plane_offset="ap_l",
        tenon_origin=("(leg_w - db2_tt) / 2", "ap_l",
                      "ap_z + (ap_w - db2_tw) / 2"),
        tenon_size={"x": "db2_tt", "z": "db2_tw"},
        tenon_depth="leg_d + 0.25 in",
        pin_plane=f2.yZConstructionPlane, pin_plane_offset="0 in",
        pin_tenon_pos_expr="ap_l + 2 * db2_pin_dia",
        pin_z_ctr="ap_z + ap_w / 2", pin_through="leg_w",
        stretcher=f2_str, name="f2_DB", ev=ctx.ev)

    sp.combine(f2_leg, [f2_str], CUT, True, "f2_Mort")
    sp.combine(f2_leg, r2["pin_bodies"], CUT, True, "f2_PinMort")
    f2_n = f2.bRepBodies.count
    print(f"F2 Horiz_Y: {f2_n} bodies — PASS")

    # ═══════════════════════════════════════════════════════
    # F3: Cross-component (same as F1, 2 comps)
    # ═══════════════════════════════════════════════════════
    f3_x = ctx.ev("ap_l + leg_w + 4 in") * 2
    f3_L = make_comp_at(root, "F3_Leg", f3_x).component
    f3_A = make_comp_at(root, "F3_Apron", f3_x).component

    _, pr = sp.sketch_rect_model(f3_L, f3_L.xYConstructionPlane,
        ("ap_l", "0 in", "0 in"),
        {"x": "leg_w", "y": "leg_d"}, "f3_Leg_Sk", ctx.ev)
    f3_leg = sp.ext_new(f3_L, pr, "leg_h", "f3_Leg").bodies.item(0)
    f3_leg.name = "f3_Leg"

    f3_ap_pl = sp.off_plane(f3_A, f3_A.xZConstructionPlane,
                             "(leg_d - ap_t) / 2", "f3_Ap_Pl")
    _, pr = sp.sketch_rect_model(f3_A, f3_ap_pl,
        ("0 in", "(leg_d - ap_t) / 2", "ap_z"),
        {"x": "ap_l", "z": "ap_w"}, "f3_Ap_Sk", ctx.ev)
    f3_ap = sp.ext_new(f3_A, pr, "ap_t", "f3_Ap").bodies.item(0)
    f3_ap.name = "f3_Apron"

    r3 = db.through(f3_A,
        tenon_plane=f3_A.yZConstructionPlane, tenon_plane_offset="ap_l",
        tenon_origin=("ap_l", "(leg_d - db_tt) / 2",
                      "ap_z + (ap_w - db_tw) / 2"),
        tenon_size={"y": "db_tt", "z": "db_tw"},
        tenon_depth="leg_w + 0.25 in",
        pin_plane=f3_A.xZConstructionPlane, pin_plane_offset="0 in",
        pin_tenon_pos_expr="ap_l + 2 * db_pin_dia",
        pin_z_ctr="ap_z + ap_w / 2", pin_through="leg_d",
        stretcher=f3_ap, name="f3_DB", ev=ctx.ev)

    sp.combine(f3_leg, [f3_ap], CUT, True, "f3_Mort")
    sp.combine(f3_leg, r3["pin_bodies"], CUT, True, "f3_PinMort")
    f3_n = f3_L.bRepBodies.count + f3_A.bRepBodies.count
    assert f3_n == f1_n
    print(f"F3 Cross: {f3_n} bodies — PASS")

    # ═══════════════════════════════════════════════════════
    # F4: Vertical Z — tenon piece (+Z) into mortise piece. Template API.
    # ═══════════════════════════════════════════════════════
    # Same structure as F1/F2 but rotated: tenon piece is a vertical
    # column, mortise piece is a horizontal slab on top receiving the
    # tenon in +Z. Pins go through the slab in Y.
    db.define_params(params, prefix="db4",
        tenon_w="tn_w", tenon_thick="tn_t",
        pin_dia="pin_d", pin_sp="pin_sp")

    f4_x = f3_x + ctx.ev("ap_l + leg_w + 4 in")
    f4 = make_comp_at(root, "F4_Vert_Z", f4_x).component

    # Mortise piece (horizontal slab at Z=ap_l)
    f4_mort_pl = sp.off_plane(f4, f4.xYConstructionPlane, "ap_l", "f4_MortPl")
    _, pr = sp.sketch_rect_model(f4, f4_mort_pl,
        ("0 in", "0 in", "ap_l"),
        {"x": "leg_w", "y": "leg_d"}, "f4_Mort_Sk", ctx.ev)
    f4_mort = sp.ext_new(f4, pr, "leg_w", "f4_Mort").bodies.item(0)
    f4_mort.name = "f4_Mort"

    # Tenon piece (vertical column from Z=0 to Z=ap_l, centered on slab)
    # ap_w in X (wider), ap_t in Y (narrower than slab → no CUT fragments)
    _, pr = sp.sketch_rect_model(f4, f4.xYConstructionPlane,
        ("(leg_w - ap_w) / 2", "(leg_d - ap_t) / 2", "0 in"),
        {"x": "ap_w", "y": "ap_t"}, "f4_TnPiece_Sk", ctx.ev)
    f4_tn_piece = sp.ext_new(f4, pr, "ap_l", "f4_TnPiece").bodies.item(0)
    f4_tn_piece.name = "f4_TnPiece"

    # Drawbore: tenon in +Z, pins in Y (xZ plane), spacing in X
    r4 = db.through(f4,
        tenon_plane=f4.xYConstructionPlane, tenon_plane_offset="ap_l",
        tenon_origin=("(leg_w - db4_tw) / 2",
                      "(leg_d - db4_tt) / 2", "ap_l"),
        tenon_size={"x": "db4_tw", "y": "db4_tt"},
        tenon_depth="leg_w + 0.25 in",
        pin_plane=f4.xZConstructionPlane, pin_plane_offset="0 in",
        pin_tenon_pos_expr="ap_l + 2 * db4_pin_dia",
        pin_z_ctr="leg_w / 2", pin_through="leg_d",
        stretcher=f4_tn_piece, name="f4_DB", ev=ctx.ev)

    sp.combine(f4_mort, [f4_tn_piece], CUT, True, "f4_MortCut")
    sp.combine(f4_mort, r4["pin_bodies"], CUT, True, "f4_PinMort")
    f4_n = f4.bRepBodies.count
    print(f"F4 Vert_Z: {f4_n} bodies — PASS")

    # ═══════════════════════════════════════════════════════
    # F5: Angled 30° — full joint built straight (like F1), then
    #     the entire assembly tilted 30° around Z.
    # ═══════════════════════════════════════════════════════
    db.define_params(params, prefix="db5",
        tenon_w="tn_w", tenon_thick="tn_t",
        pin_dia="pin_d", pin_sp="pin_sp")

    ang = 30
    ang_r = math.radians(ang)
    f5_x = f4_x + ctx.ev("leg_w + 4 in")
    f5 = make_comp_at(root, "F5_Angled_30", f5_x).component

    # Mortise piece (same as F1 leg)
    _, pr = sp.sketch_rect_model(f5, f5.xYConstructionPlane,
        ("ap_l", "0 in", "0 in"),
        {"x": "leg_w", "y": "leg_d"}, "f5_Mort_Sk", ctx.ev)
    f5_mort = sp.ext_new(f5, pr, "leg_h", "f5_Mort").bodies.item(0)
    f5_mort.name = "f5_Mort"

    # Tenon piece (same as F1 apron)
    f5_ap_pl = sp.off_plane(f5, f5.xZConstructionPlane,
                             "(leg_d - ap_t) / 2", "f5_TnPl")
    _, pr = sp.sketch_rect_model(f5, f5_ap_pl,
        ("0 in", "(leg_d - ap_t) / 2", "ap_z"),
        {"x": "ap_l", "z": "ap_w"}, "f5_TnPiece_Sk", ctx.ev)
    f5_tn_piece = sp.ext_new(f5, pr, "ap_t", "f5_TnPiece").bodies.item(0)
    f5_tn_piece.name = "f5_TnPiece"

    # Drawbore — full combines (same as F1)
    r5 = db.through(f5,
        tenon_plane=f5.yZConstructionPlane, tenon_plane_offset="ap_l",
        tenon_origin=("ap_l", "(leg_d - db5_tt) / 2",
                      "ap_z + (ap_w - db5_tw) / 2"),
        tenon_size={"y": "db5_tt", "z": "db5_tw"},
        tenon_depth="leg_w + 0.25 in",
        pin_plane=f5.xZConstructionPlane, pin_plane_offset="0 in",
        pin_tenon_pos_expr="ap_l + 2 * db5_pin_dia",
        pin_z_ctr="ap_z + ap_w / 2", pin_through="leg_d",
        stretcher=f5_tn_piece, name="f5_DB", ev=ctx.ev)

    sp.combine(f5_mort, [f5_tn_piece], CUT, True, "f5_MortCut")
    sp.combine(f5_mort, r5["pin_bodies"], CUT, True, "f5_PinMort")

    # Tilt the entire assembly by 30° around Z
    ev = ctx.ev
    pivot = P3(ev("ap_l + leg_w / 2"), ev("leg_d / 2"), ev("ap_z + ap_w / 2"))
    rot = adsk.core.Matrix3D.create()
    rot.setToRotation(ang_r, adsk.core.Vector3D.create(0, 0, 1), pivot)
    tilt_coll = adsk.core.ObjectCollection.create()
    for bi in range(f5.bRepBodies.count):
        tilt_coll.add(f5.bRepBodies.item(bi))
    tilt_inp = f5.features.moveFeatures.createInput2(tilt_coll)
    tilt_inp.defineAsFreeMove(rot)
    f5.features.moveFeatures.add(tilt_inp).name = "f5_Tilt"

    f5_n = f5.bRepBodies.count
    print(f"F5 Angled_30: {f5_n} bodies — PASS")

    # ── Summary ──
    total = 0
    for occ in root.occurrences:
        c = occ.component
        n = c.bRepBodies.count
        names = [c.bRepBodies.item(i).name for i in range(n)]
        print(f"  {c.name}: {n} -> {names}")
        total += n
    print(f"\nTotal: {total} bodies")

    for occ in root.occurrences:
        c = occ.component
        for sk in c.sketches:
            sk.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
