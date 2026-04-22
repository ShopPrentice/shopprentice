"""Test fixture for drawbore template.

Geometry
--------
Leg: 3×3×10" box, origin at (0,0,0). Axes: X=width, Y=depth, Z=height.
Stretcher: 10" long, attached to leg's -X face (at X<0). Tenon extrudes
    in +X INTO the leg. Pins extrude in +Y, CROSSING the tenon's
    Y-thickness (perpendicular to the tenon axis, as real drawbore pins
    do — not running parallel to the tenon).

Fixtures
--------
  F1 Intra: Leg + Stretcher in one component. 4 bodies (leg,
            stretcher with tenon+pin-holes, 2 pin bodies).
  F2 Cross: Same geometry but Leg and Stretcher in separate root
            components — exercises combine's cross-component routing.
            4 bodies across 2 components.

Total: 8 bodies in 3 components.
"""
import adsk.core
import adsk.fusion


def make_comp_at(root, name, x_cm=0.0):
    xf = adsk.core.Matrix3D.create()
    if x_cm != 0.0:
        xf.setCell(0, 3, x_cm)
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

    params.add("leg_w", VI("3 in"), "in", "Leg width (X)")
    params.add("leg_d", VI("3 in"), "in", "Leg depth (Y)")
    params.add("leg_h", VI("10 in"), "in", "Leg height (Z)")
    params.add("st_l",  VI("10 in"), "in", "Stretcher length (X)")
    params.add("st_w",  VI("3 in"),  "in", "Stretcher height (Z)")
    params.add("st_t",  VI("1.5 in"), "in", "Stretcher thickness (Y)")
    params.add("st_z",  VI("3 in"),  "in", "Stretcher bottom Z")
    db.define_params(params, prefix="db",
        tenon_w="st_w", tenon_thick="st_t",
        pin_dia="0.375 in", pin_sp="2 in")

    # ── F1: Intra-component ──
    f1 = make_comp_at(root, "DB_Intra").component

    # Leg at origin
    _, pr = sp.sketch_rect_model(f1, f1.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_w", "y": "leg_d"}, "f1_Leg_Sk", ctx.ev)
    leg = sp.ext_new(f1, pr, "leg_h", "f1_Leg").bodies.item(0)
    leg.name = "f1_Leg"

    # Stretcher on the -X side, centered in Y on the leg.
    st_pl = sp.off_plane(f1, f1.xZConstructionPlane,
                         "(leg_d - st_t) / 2", "f1_St_Pl")
    _, pr = sp.sketch_rect_model(f1, st_pl,
        ("-st_l", "(leg_d - st_t) / 2", "st_z"),
        {"x": "st_l", "z": "st_w"}, "f1_St_Sk", ctx.ev)
    stretcher = sp.ext_new(f1, pr, "st_t", "f1_St").bodies.item(0)
    stretcher.name = "f1_St"

    # Drawbore through tenon + 2 pins.
    # Tenon extrudes in +X. Pins must extrude perpendicular — in +Y
    # through the leg and tenon — so pin_plane is xZ (normal Y),
    # offset to Y=0 (leg's near cheek). pin_through = leg_d so the
    # pin fully traverses both cheeks.
    db.through(
        comp=f1,
        tenon_plane=f1.yZConstructionPlane,
        tenon_plane_offset="0 in",
        tenon_origin=("0 in", "(leg_d - db_tt) / 2",
                      "st_z + (st_w - db_tw) / 2"),
        tenon_size={"y": "db_tt", "z": "db_tw"},
        tenon_depth="leg_w + 0.25 in",
        pin_plane=f1.xZConstructionPlane,
        pin_plane_offset="0 in",
        pin_tenon_pos_expr="leg_w * 2 / 3",
        pin_z_ctr="st_z + st_w / 2",
        pin_through="leg_d",
        stretcher=stretcher,
        name="f1_DB", ev=ctx.ev)

    # Caller CUTs the leg with the pinned stretcher.
    sp.combine(leg, [stretcher], CUT, True, "f1_Leg_Cut")

    f1_count = f1.bRepBodies.count
    f1_names = [f1.bRepBodies.item(i).name for i in range(f1_count)]
    print(f"  DB_Intra bodies ({f1_count}): {f1_names}")
    assert f1_count >= 2, \
        f"F1 expected at least 2 bodies, got {f1_count}"
    print(f"DB_Intra: {f1_count} bodies — PASS")

    # ── F2: Cross-component (same geometry, 2 comps) ──
    params.add("f2_x", VI("20 in"), "in", "F2 X offset")
    f2_x = ctx.ev("f2_x")
    f2_Leg = make_comp_at(root, "DB_Cross_Leg", f2_x).component
    f2_St  = make_comp_at(root, "DB_Cross_Stretcher", f2_x).component

    _, pr = sp.sketch_rect_model(f2_Leg, f2_Leg.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_w", "y": "leg_d"}, "f2_Leg_Sk", ctx.ev)
    f2_leg = sp.ext_new(f2_Leg, pr, "leg_h", "f2_Leg").bodies.item(0)
    f2_leg.name = "f2_Leg"

    f2_st_pl = sp.off_plane(f2_St, f2_St.xZConstructionPlane,
                             "(leg_d - st_t) / 2", "f2_St_Pl")
    _, pr = sp.sketch_rect_model(f2_St, f2_st_pl,
        ("-st_l", "(leg_d - st_t) / 2", "st_z"),
        {"x": "st_l", "z": "st_w"}, "f2_St_Sk", ctx.ev)
    f2_stretcher = sp.ext_new(f2_St, pr, "st_t", "f2_St").bodies.item(0)
    f2_stretcher.name = "f2_St"

    db.through(
        comp=f2_St,
        tenon_plane=f2_St.yZConstructionPlane,
        tenon_plane_offset="0 in",
        tenon_origin=("0 in", "(leg_d - db_tt) / 2",
                      "st_z + (st_w - db_tw) / 2"),
        tenon_size={"y": "db_tt", "z": "db_tw"},
        tenon_depth="leg_w + 0.25 in",
        pin_plane=f2_St.xZConstructionPlane,
        pin_plane_offset="0 in",
        pin_tenon_pos_expr="leg_w * 2 / 3",
        pin_z_ctr="st_z + st_w / 2",
        pin_through="leg_d",
        stretcher=f2_stretcher,
        name="f2_DB", ev=ctx.ev)

    sp.combine(f2_leg, [f2_stretcher], CUT, True, "f2_Leg_Cut")

    f2_leg_count = f2_Leg.bRepBodies.count
    f2_st_count = f2_St.bRepBodies.count
    f2_leg_names = [f2_Leg.bRepBodies.item(i).name for i in range(f2_leg_count)]
    f2_st_names = [f2_St.bRepBodies.item(i).name for i in range(f2_st_count)]
    print(f"  F2_Leg bodies ({f2_leg_count}): {f2_leg_names}")
    print(f"  F2_St bodies ({f2_st_count}): {f2_st_names}")
    # Cross-component routing assertion: F2 produces the same body
    # layout as F1.
    f2_total = f2_leg_count + f2_st_count
    assert f2_total == f1_count, \
        f"F2 total {f2_total} should match F1 intra-comp total {f1_count}"
    assert f2_leg_count == 1, \
        f"F2_Leg should have exactly 1 body, got {f2_leg_count}"
    print(f"DB_Cross: {f2_total} bodies across 2 comps — PASS")

    # ── Summary ──
    total = 0
    for occ in root.occurrences:
        c = occ.component
        n = c.bRepBodies.count
        names = [c.bRepBodies.item(i).name for i in range(n)]
        print(f"  {c.name}: {n} bodies -> {names}")
        total += n
    print(f"\nTotal bodies: {total} across {sum(1 for _ in root.occurrences)} components")

    for occ in root.occurrences:
        c = occ.component
        for sk in c.sketches:
            sk.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
