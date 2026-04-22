"""Test fixture for drawbore template.

Covers the two common drawbore orientations plus a cross-component
routing check:

  F1 Horizontal (rail → leg)
     Table / bench apron: vertical leg, horizontal apron pegged into
     its side. Tenon extrudes horizontally (+X) into the leg; the
     drawbore pin runs vertically (+Z)... wait actually — the pin
     runs horizontally too but in the other horizontal axis (Y),
     crossing the tenon's Y-thickness.
     4 bodies (leg, apron-with-tenon-and-pin-holes, 2 pins) in 1 comp.

  F2 Vertical (leg → top slab)
     Workbench / trestle table: horizontal slab above, leg below,
     leg tenon extrudes upward (+Z) INTO the slab. Drawbore pin
     passes horizontally (+Y) through the slab side and across the
     leg tenon.
     4 bodies (leg-with-tenon, slab-with-pin-holes, 2 pins) in 1 comp.

  F3 Cross-component (same as F1, 2 comps)
     Leg in one root component, apron in another. Exercises combine's
     cross-component routing (tenon JOIN + pin CUT inside the apron's
     comp stay intra-comp; the final leg mortise CUT is cross-comp).
     Body layout must match F1.

Body counts depend on Fusion's through-tenon split behavior (a small
fragment may appear when the tenon's proud end exits the leg's far
face). Tests assert cross-comp total == intra-comp total to detect
routing errors.
"""
import adsk.core
import adsk.fusion


def make_comp_at(root, name, x_cm=0.0, y_cm=0.0):
    xf = adsk.core.Matrix3D.create()
    if x_cm != 0.0:
        xf.setCell(0, 3, x_cm)
    if y_cm != 0.0:
        xf.setCell(1, 3, y_cm)
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
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation

    ctx = sp.DesignContext(design)

    # Horizontal rail-to-leg params (F1, F3)
    params.add("leg_w", VI("3 in"), "in", "Leg width (X)")
    params.add("leg_d", VI("3 in"), "in", "Leg depth (Y)")
    params.add("leg_h", VI("10 in"), "in", "Leg height (Z)")
    params.add("ap_l",  VI("8 in"), "in", "Apron length")
    params.add("ap_w",  VI("3 in"), "in", "Apron height (Z)")
    params.add("ap_t",  VI("1.5 in"), "in", "Apron thickness (Y)")
    params.add("ap_z",  VI("5 in"), "in", "Apron bottom Z")

    # Vertical leg-to-slab params (F2)
    params.add("slab_w", VI("12 in"), "in", "Slab width (X)")
    params.add("slab_d", VI("5 in"),  "in", "Slab depth (Y)")
    params.add("slab_t", VI("2 in"),  "in", "Slab thickness (Z)")
    params.add("vleg_w", VI("2 in"),  "in", "Vertical leg width (X)")
    params.add("vleg_d", VI("2 in"),  "in", "Vertical leg depth (Y)")
    params.add("vleg_h", VI("8 in"),  "in", "Vertical leg height (Z)")
    params.add("vt_proud", VI("0.25 in"), "in", "Vertical tenon proud")

    db.define_params(params, prefix="db",
        tenon_w="ap_w", tenon_thick="ap_t",
        pin_dia="0.375 in", pin_sp="2 in")

    # ═══════════════════════════════════════════════════════
    # F1: Horizontal — apron pegged into leg side
    # ═══════════════════════════════════════════════════════
    # Layout: apron X=[0, ap_l], leg X=[ap_l, ap_l+leg_w].
    # Shoulder at X=ap_l. Tenon extrudes +X into leg.
    # All positive coordinates (Fusion's evaluateExpression can
    # mishandle leading minus on parameter names like "-ap_l").
    f1 = make_comp_at(root, "DB_Horizontal").component

    # Leg (offset by ap_l so apron fits at origin side)
    _, pr = sp.sketch_rect_model(f1, f1.xYConstructionPlane,
        ("ap_l", "0 in", "0 in"),
        {"x": "leg_w", "y": "leg_d"}, "f1_Leg_Sk", ctx.ev)
    leg = sp.ext_new(f1, pr, "leg_h", "f1_Leg").bodies.item(0)
    leg.name = "f1_Leg"

    # Apron from X=0 to X=ap_l, shoulder touching leg at X=ap_l
    ap_pl = sp.off_plane(f1, f1.xZConstructionPlane,
                          "(leg_d - ap_t) / 2", "f1_Ap_Pl")
    _, pr = sp.sketch_rect_model(f1, ap_pl,
        ("0 in", "(leg_d - ap_t) / 2", "ap_z"),
        {"x": "ap_l", "z": "ap_w"}, "f1_Ap_Sk", ctx.ev)
    apron = sp.ext_new(f1, pr, "ap_t", "f1_Ap").bodies.item(0)
    apron.name = "f1_Apron"

    # Tenon plane at X=ap_l (shoulder), extrudes +X into leg.
    # Pin plane xZ at Y=0, pins traverse leg_d in +Y.
    db.through(
        comp=f1,
        tenon_plane=f1.yZConstructionPlane,
        tenon_plane_offset="ap_l",
        tenon_origin=("ap_l", "(leg_d - db_tt) / 2",
                      "ap_z + (ap_w - db_tw) / 2"),
        tenon_size={"y": "db_tt", "z": "db_tw"},
        tenon_depth="leg_w + 0.25 in",
        pin_plane=f1.xZConstructionPlane,
        pin_plane_offset="0 in",
        pin_tenon_pos_expr="ap_l + 2 * db_pin_dia",
        pin_z_ctr="ap_z + ap_w / 2",
        pin_through="leg_d",
        stretcher=apron,
        name="f1_DB", ev=ctx.ev)

    sp.combine(leg, [apron], CUT, True, "f1_Leg_Cut")

    f1_count = f1.bRepBodies.count
    print(f"  Horizontal bodies ({f1_count}): "
          f"{[f1.bRepBodies.item(i).name for i in range(f1_count)]}")
    assert f1_count >= 3, f"F1 expected at least 3 bodies, got {f1_count}"
    print(f"DB_Horizontal: {f1_count} bodies — PASS")

    # ═══════════════════════════════════════════════════════
    # F2: Vertical — leg tenoned up into a top slab
    # ═══════════════════════════════════════════════════════
    # Placed in +X off F1 so both are visible together.
    params.add("f2_x", VI("leg_w + ap_l + 4 in"), "in", "F2 X offset")
    f2 = make_comp_at(root, "DB_Vertical", ctx.ev("f2_x")).component

    # Vertical leg standing from Z=0 to Z=vleg_h.
    _, pr = sp.sketch_rect_model(f2, f2.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "vleg_w", "y": "vleg_d"}, "f2_VLeg_Sk", ctx.ev)
    vleg = sp.ext_new(f2, pr, "vleg_h", "f2_VLeg").bodies.item(0)
    vleg.name = "f2_VLeg"

    # Slab sits on top of the leg (bottom face at Z = vleg_h).
    # Slab is wider than the leg in X and Y for clear visualization.
    slab_pl = sp.off_plane(f2, f2.xYConstructionPlane, "vleg_h",
                            "f2_SlabPl")
    _, pr = sp.sketch_rect_model(f2, slab_pl,
        ("-(slab_w - vleg_w) / 2",
         "-(slab_d - vleg_d) / 2",
         "vleg_h"),
        {"x": "slab_w", "y": "slab_d"}, "f2_Slab_Sk", ctx.ev)
    slab = sp.ext_new(f2, pr, "slab_t", "f2_Slab").bodies.item(0)
    slab.name = "f2_Slab"

    # Through tenon extrudes +Z from the leg's top face into the slab.
    # tenon_plane = xYConstructionPlane (normal Z) offset to vleg_h
    # (leg top face). Tenon extrudes +Z by slab_t + proud.
    # Pin plane = xZConstructionPlane (normal Y), offset to slab's
    # near Y face so the pin runs +Y through the slab, crossing the
    # tenon's Y-thickness.
    db.through(
        comp=f2,
        tenon_plane=f2.xYConstructionPlane, tenon_plane_offset="vleg_h",
        tenon_origin=("(vleg_w - db_tt) / 2",
                      "(vleg_d - db_tt) / 2",
                      "vleg_h"),
        tenon_size={"x": "db_tt", "y": "db_tt"},
        tenon_depth="slab_t + vt_proud",
        pin_plane=f2.xZConstructionPlane,
        pin_plane_offset="-(slab_d - vleg_d) / 2",   # pin enters slab's -Y face
        pin_tenon_pos_expr="vleg_w / 2",             # pin centered on tenon in X
        pin_z_ctr="vleg_h + slab_t / 2",             # pin midway up the slab
        pin_through="slab_d",
        stretcher=vleg,                               # tenon JOINS into leg
        name="f2_DB", ev=ctx.ev)

    # The leg (with tenon + pin holes) cuts the slab's mortise + pin
    # path. sp.combine auto-picks target.parentComponent.
    sp.combine(slab, [vleg], CUT, True, "f2_Slab_Cut")

    f2_count = f2.bRepBodies.count
    print(f"  Vertical bodies ({f2_count}): "
          f"{[f2.bRepBodies.item(i).name for i in range(f2_count)]}")
    assert f2_count >= 3, f"F2 expected at least 3 bodies, got {f2_count}"
    print(f"DB_Vertical: {f2_count} bodies — PASS")

    # ═══════════════════════════════════════════════════════
    # F3: Cross-component horizontal (same geometry as F1, 2 comps)
    # ═══════════════════════════════════════════════════════
    params.add("f3_x", VI("f2_x + slab_w + 4 in"), "in", "F3 X offset")
    f3_x = ctx.ev("f3_x")
    f3_Leg = make_comp_at(root, "DB_Cross_Leg", f3_x).component
    f3_Ap  = make_comp_at(root, "DB_Cross_Apron", f3_x).component

    # Leg offset by ap_l (same layout as F1)
    _, pr = sp.sketch_rect_model(f3_Leg, f3_Leg.xYConstructionPlane,
        ("ap_l", "0 in", "0 in"),
        {"x": "leg_w", "y": "leg_d"}, "f3_Leg_Sk", ctx.ev)
    f3_leg = sp.ext_new(f3_Leg, pr, "leg_h", "f3_Leg").bodies.item(0)
    f3_leg.name = "f3_Leg"

    f3_ap_pl = sp.off_plane(f3_Ap, f3_Ap.xZConstructionPlane,
                             "(leg_d - ap_t) / 2", "f3_Ap_Pl")
    _, pr = sp.sketch_rect_model(f3_Ap, f3_ap_pl,
        ("0 in", "(leg_d - ap_t) / 2", "ap_z"),
        {"x": "ap_l", "z": "ap_w"}, "f3_Ap_Sk", ctx.ev)
    f3_ap = sp.ext_new(f3_Ap, pr, "ap_t", "f3_Ap").bodies.item(0)
    f3_ap.name = "f3_Apron"

    db.through(
        comp=f3_Ap,
        tenon_plane=f3_Ap.yZConstructionPlane,
        tenon_plane_offset="ap_l",
        tenon_origin=("ap_l", "(leg_d - db_tt) / 2",
                      "ap_z + (ap_w - db_tw) / 2"),
        tenon_size={"y": "db_tt", "z": "db_tw"},
        tenon_depth="leg_w + 0.25 in",
        pin_plane=f3_Ap.xZConstructionPlane,
        pin_plane_offset="0 in",
        pin_tenon_pos_expr="ap_l + 2 * db_pin_dia",
        pin_z_ctr="ap_z + ap_w / 2",
        pin_through="leg_d",
        stretcher=f3_ap,
        name="f3_DB", ev=ctx.ev)

    # Cross-comp leg CUT.
    sp.combine(f3_leg, [f3_ap], CUT, True, "f3_Leg_Cut")

    f3_leg_count = f3_Leg.bRepBodies.count
    f3_ap_count = f3_Ap.bRepBodies.count
    print(f"  F3_Leg bodies ({f3_leg_count}): "
          f"{[f3_Leg.bRepBodies.item(i).name for i in range(f3_leg_count)]}")
    print(f"  F3_Ap bodies ({f3_ap_count}): "
          f"{[f3_Ap.bRepBodies.item(i).name for i in range(f3_ap_count)]}")
    f3_total = f3_leg_count + f3_ap_count
    assert f3_total == f1_count, \
        f"F3 cross-comp total {f3_total} should match F1 intra-comp total {f1_count}"
    assert f3_leg_count == 1, \
        f"F3_Leg should have exactly 1 body, got {f3_leg_count}"
    print(f"DB_Cross: {f3_total} bodies across 2 comps — PASS")

    # ── Summary ──
    total = 0
    for occ in root.occurrences:
        c = occ.component
        n = c.bRepBodies.count
        names = [c.bRepBodies.item(i).name for i in range(n)]
        print(f"  {c.name}: {n} bodies -> {names}")
        total += n
    print(f"\nTotal bodies: {total} across "
          f"{sum(1 for _ in root.occurrences)} components")

    for occ in root.occurrences:
        c = occ.component
        for sk in c.sketches:
            sk.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
