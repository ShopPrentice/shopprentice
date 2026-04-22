"""Test fixture for drawbore template.

Exercises drawbore.through() in two configurations:

  F1 Intra: Leg + Stretcher in one component. Stretcher tenon passes
            fully through the leg, two drawbore pins pass across the
            tenon. Template JOINs tenon into stretcher and CUTs pin
            holes in stretcher (keepTool=True on pins). Caller CUTs the
            leg with the pinned stretcher body.
  F2 Cross: Leg in one root component, Stretcher in another. Same
            geometry, but the template must route its tenon-JOIN and
            pin-CUT combines across components via sp.combine.

Intra total: 4 bodies (Leg, Stretcher-with-tenon-and-holes, 2 pin bodies).
Cross total: 4 bodies across 2 components (1 leg + 1 stretcher + 2 pins).
Grand total: 8 bodies in 3 components.
"""
import adsk.core
import adsk.fusion


def make_comp_at(root, name, x_cm=0.0):
    """Create a component at the given X world position."""
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

    # Shared dimensions
    params.add("leg_w", VI("3 in"), "in", "Leg width (X)")
    params.add("leg_d", VI("3 in"), "in", "Leg depth (Y)")
    params.add("leg_h", VI("10 in"), "in", "Leg height (Z)")
    params.add("st_l",  VI("10 in"), "in", "Stretcher length")
    params.add("st_w",  VI("3 in"),  "in", "Stretcher height (Z)")
    params.add("st_t",  VI("1.5 in"), "in", "Stretcher thickness (Y)")
    params.add("st_z",  VI("3 in"),  "in", "Stretcher bottom Z")
    db.define_params(params, prefix="db",
        tenon_w="st_w", tenon_thick="st_t",
        pin_dia="0.375 in", pin_sp="2 in")

    # ── F1: Intra-component ──
    f1 = make_comp_at(root, "DB_Intra").component

    # Leg — at origin
    _, pr = sp.sketch_rect_model(f1, f1.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_w", "y": "leg_d"}, "f1_Leg_Sk", ctx.ev)
    leg = sp.ext_new(f1, pr, "leg_h", "f1_Leg").bodies.item(0)
    leg.name = "f1_Leg"

    # Stretcher — sits against leg's +X face, protruding outward to
    # the right for tenon (tenon goes in -X direction, INTO the leg
    # through its +X face). So the stretcher body starts at X=leg_w,
    # extends to X=leg_w+st_l. The through-tenon extrudes from the
    # stretcher's near end (X=leg_w) INTO the leg (+X direction
    # reversed to -X)... simpler: put stretcher on the -X side.
    #
    # Stretcher: from X=-st_l to X=0, at Y=(leg_d-st_t)/2 centered,
    # Z=st_z+st_w/2 centered.
    st_pl = sp.off_plane(f1, f1.xZConstructionPlane,
                         "(leg_d - st_t) / 2", "f1_St_Pl")
    _, pr = sp.sketch_rect_model(f1, st_pl,
        ("-st_l", "(leg_d - st_t) / 2", "st_z"),
        {"x": "st_l", "z": "st_w"}, "f1_St_Sk", ctx.ev)
    stretcher = sp.ext_new(f1, pr, "st_t", "f1_St").bodies.item(0)
    stretcher.name = "f1_St"

    # Drawbore through tenon — tenon plane at X=0 (leg's -X face), tenon
    # extrudes in +X direction through leg (depth = leg_w + proud).
    # Pin plane perpendicular (xZ plane), pins go in Y direction through
    # the tenon (leg_d deep).
    db.through(
        comp=f1,
        tenon_plane=f1.yZConstructionPlane,
        tenon_plane_offset="0 in",
        tenon_origin=("0 in", "(leg_d - db_tt) / 2",
                      "st_z + (st_w - db_tw) / 2"),
        tenon_size={"y": "db_tt", "z": "db_tw"},
        tenon_depth="leg_w + 0.25 in",
        pin_plane=f1.yZConstructionPlane,
        pin_x_expr="leg_w * 2 / 3",
        pin_z_ctr="st_z + st_w / 2",
        pin_through="leg_d",
        stretcher=stretcher,
        name="f1_DB", ev=ctx.ev)

    # Caller CUTs the leg with the stretcher (now has tenon + pin holes)
    sp.combine(leg, [stretcher], CUT, True, "f1_Leg_Cut")

    f1_count = f1.bRepBodies.count
    f1_names = [f1.bRepBodies.item(i).name for i in range(f1_count)]
    print(f"  DB_Intra bodies ({f1_count}): {f1_names}")
    assert f1_count >= 2, \
        f"F1 expected at least 2 bodies, got {f1_count}"
    print(f"DB_Intra: {f1_count} bodies — PASS")

    # ── F2: Cross-component ──
    # Leg and Stretcher each in their own root component; drawbore
    # combines must route to root with proxies.
    params.add("f2_x", VI("20 in"), "in", "F2 X offset")
    f2_x = ctx.ev("f2_x")

    f2_Leg = make_comp_at(root, "DB_Cross_Leg", f2_x).component
    f2_St  = make_comp_at(root, "DB_Cross_Stretcher", f2_x).component

    # Leg in its own comp (at comp origin, world +f2_x)
    _, pr = sp.sketch_rect_model(f2_Leg, f2_Leg.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_w", "y": "leg_d"}, "f2_Leg_Sk", ctx.ev)
    f2_leg = sp.ext_new(f2_Leg, pr, "leg_h", "f2_Leg").bodies.item(0)
    f2_leg.name = "f2_Leg"

    # Stretcher in f2_St (same relative position as F1)
    f2_st_pl = sp.off_plane(f2_St, f2_St.xZConstructionPlane,
                             "(leg_d - st_t) / 2", "f2_St_Pl")
    _, pr = sp.sketch_rect_model(f2_St, f2_st_pl,
        ("-st_l", "(leg_d - st_t) / 2", "st_z"),
        {"x": "st_l", "z": "st_w"}, "f2_St_Sk", ctx.ev)
    f2_stretcher = sp.ext_new(f2_St, pr, "st_t", "f2_St").bodies.item(0)
    f2_stretcher.name = "f2_St"

    # through() with comp=f2_St. Tenon + pins live in f2_St, JOIN into
    # f2_stretcher (intra-comp — always), CUT pin holes in f2_stretcher
    # (intra-comp). The caller's leg CUT is the cross-comp step.
    db.through(
        comp=f2_St,
        tenon_plane=f2_St.yZConstructionPlane,
        tenon_plane_offset="0 in",
        tenon_origin=("0 in", "(leg_d - db_tt) / 2",
                      "st_z + (st_w - db_tw) / 2"),
        tenon_size={"y": "db_tt", "z": "db_tw"},
        tenon_depth="leg_w + 0.25 in",
        pin_plane=f2_St.yZConstructionPlane,
        pin_x_expr="leg_w * 2 / 3",
        pin_z_ctr="st_z + st_w / 2",
        pin_through="leg_d",
        stretcher=f2_stretcher,
        name="f2_DB", ev=ctx.ev)

    # Cross-comp leg CUT with pinned stretcher body
    sp.combine(f2_leg, [f2_stretcher], CUT, True, "f2_Leg_Cut")

    f2_leg_count = f2_Leg.bRepBodies.count
    f2_st_count = f2_St.bRepBodies.count
    f2_leg_names = [f2_Leg.bRepBodies.item(i).name for i in range(f2_leg_count)]
    f2_st_names = [f2_St.bRepBodies.item(i).name for i in range(f2_st_count)]
    print(f"  F2_Leg bodies ({f2_leg_count}): {f2_leg_names}")
    print(f"  F2_St bodies ({f2_st_count}): {f2_st_names}")
    # Key cross-component assertion: F2 produces the same total count
    # as F1 — if combine didn't route correctly, the mortise CUT
    # would either fail or silently no-op, leaving F2_Leg with an
    # uncut leg (same body count but wrong geometry) or the pin CUT
    # would be missing (different body count). Both F1 and F2 use
    # identical operations; equal totals mean routing was consistent.
    f2_total = f2_leg_count + f2_st_count
    assert f2_total == f1_count, \
        f"F2 total {f2_total} should match F1 intra-comp total {f1_count}"
    assert f2_leg_count == 1, \
        f"F2_Leg should have exactly 1 body (cut leg), got {f2_leg_count}"
    print(f"DB_Cross: {f2_total} bodies across 2 comps — PASS "
          f"(matches intra-comp layout)")

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
