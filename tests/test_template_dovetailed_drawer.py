"""Test fixture for dovetailed drawer template.

Tests define_params and build() with 3 configurations, each drawer
built to fit inside a case box:
  F1: Standard drawer in 22x15x6 case
  F2: Taller front drawer in 22x15x8 case (front fills opening, sides shorter)
  F3: Small drawer in 14x11x5 case

Each component is created at its final position via addNewComponent(transform).
Case is built with mirror (1 side + mirror, 1 bottom + mirror = 4 boards).
Drawer is built in place inside the case via x_offset/z_offset (no MoveFeature).
Total: 3 × (4 case + 5 drawer) = 27 bodies.
"""
import adsk.core
import adsk.fusion
import math


def make_comp_at(root, name, x_cm=0.0, z_cm=0.0, rot_z_deg=0.0):
    """Create a component at the given world position with optional Z rotation."""
    xf = adsk.core.Matrix3D.create()
    if rot_z_deg != 0.0:
        a = math.radians(rot_z_deg)
        xf.setCell(0, 0, math.cos(a))
        xf.setCell(0, 1, -math.sin(a))
        xf.setCell(1, 0, math.sin(a))
        xf.setCell(1, 1, math.cos(a))
    if x_cm != 0.0:
        xf.setCell(0, 3, x_cm)
    if z_cm != 0.0:
        xf.setCell(2, 3, z_cm)
    occ = root.occurrences.addNewComponent(xf)
    occ.component.name = name
    return occ


def build_case(comp, prefix, ev):
    """Build 4-board case via mirror at component origin."""
    p = prefix

    x_mid = sp.off_plane(comp, comp.yZConstructionPlane,
                         f"{p}_cw / 2", f"{p}_XMid")
    z_mid = sp.off_plane(comp, comp.xYConstructionPlane,
                         f"{p}_ch / 2", f"{p}_ZMid")

    # Left side → mirror → right
    _, pr = sp.sketch_rect_model(comp, comp.yZConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"y": f"{p}_cd", "z": f"{p}_ch"}, f"{p}_CL_Sk", ev)
    cl = sp.ext_new(comp, pr, f"{p}_ct", f"{p}_CL").bodies.item(0)
    cl.name = f"{p}_Case_Left"
    cr = sp.mirror_body(comp, cl, x_mid, f"{p}_CR_Mir").bodies.item(0)
    cr.name = f"{p}_Case_Right"

    # Bottom → mirror → top
    _, pr = sp.sketch_rect_model(comp, comp.xYConstructionPlane,
        (f"{p}_ct", "0 in", "0 in"),
        {"x": f"{p}_cw - 2 * {p}_ct", "y": f"{p}_cd"}, f"{p}_CB_Sk", ev)
    cb = sp.ext_new(comp, pr, f"{p}_ct", f"{p}_CB").bodies.item(0)
    cb.name = f"{p}_Case_Bot"
    ct = sp.mirror_body(comp, cb, z_mid, f"{p}_CT_Mir").bodies.item(0)
    ct.name = f"{p}_Case_Top"

    return [cl, cr, cb, ct]


def build_drawer_in_case(comp, case_prefix, drawer_prefix, ev,
                         drawer_h=None, front_h=None,
                         front_thick="0.75 in", side_thick="0.5 in",
                         bottom_thick="0.25 in",
                         dt_angle="8 deg", dt_tail_w="0.75 in",
                         front_tail_count="3", back_tail_count="3",
                         hbd_lap="0.25 in"):
    """Build drawer inside the case.

    Drawer position is relative to the case opening — the inner face of
    the case side board defines the opening boundary, and the drawer is
    offset from that boundary by dr_gap.
    """
    cp = case_prefix
    dp = drawer_prefix
    params = comp.parentDesign.userParameters

    h_expr = drawer_h if drawer_h else f"{cp}_ch - 2 * {cp}_ct - 2 * dr_gap"

    # Opening boundary: inner face of case side board (at X = ct)
    # and top face of case bottom board (at Z = ct).
    # Drawer is offset from each boundary by dr_gap.
    opening_x = f"{cp}_ct"
    opening_z = f"{cp}_ct"

    dovetailed_drawer.define_params(params, prefix=dp,
        drawer_w=f"{cp}_cw - 2 * {cp}_ct - 2 * dr_gap",
        drawer_d=f"{cp}_cd - dr_gap",
        drawer_h=h_expr,
        front_h=front_h,
        front_thick=front_thick, side_thick=side_thick,
        bottom_thick=bottom_thick,
        dt_angle=dt_angle, dt_tail_w=dt_tail_w,
        front_tail_count=front_tail_count,
        back_tail_count=back_tail_count,
        hbd_lap=hbd_lap,
        x_offset=f"{opening_x} + dr_gap",
        z_offset=f"{opening_z} + dr_gap")

    result = dovetailed_drawer.build(comp, prefix=dp, ev=ev)

    return result


def run(context):
    app = adsk.core.Application.get()

    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString

    global af, dovetailed_drawer
    from helpers import sp
    from woodworking.templates import dovetailed_drawer

    ctx = sp.DesignContext(design)

    params.add("dr_gap", VI("0.0625 in"), "in", "Drawer-to-case gap")
    params.add("case_thick", VI("0.75 in"), "in", "Case board thickness")

    # ── F1: Standard drawer in 22x15x6 case (at origin) ──
    params.add("f1_cw", VI("22 in"), "in", "F1 case width")
    params.add("f1_cd", VI("15 in"), "in", "F1 case depth")
    params.add("f1_ch", VI("6 in"), "in", "F1 case height")
    params.add("f1_ct", VI("case_thick"), "in", "F1 case thickness")

    f1_c = make_comp_at(root, "F1").component
    build_case(f1_c, "f1", ctx.ev)
    build_drawer_in_case(f1_c, "f1", "d1", ctx.ev)
    assert f1_c.bRepBodies.count == 9
    print("F1: 9 bodies — PASS")

    # ── F2: Taller front drawer in 22x15x8 case ──
    params.add("f2_cw", VI("22 in"), "in", "F2 case width")
    params.add("f2_cd", VI("15 in"), "in", "F2 case depth")
    params.add("f2_ch", VI("8 in"), "in", "F2 case height")
    params.add("f2_ct", VI("case_thick"), "in", "F2 case thickness")
    params.add("f2_dh", VI("4 in"), "in", "F2 drawer side height")
    params.add("f2_x", VI("f1_cw + 2 in"), "in", "F2 X offset")

    f2_c = make_comp_at(root, "F2", ctx.ev("f2_x")).component
    build_case(f2_c, "f2", ctx.ev)
    build_drawer_in_case(f2_c, "f2", "d2", ctx.ev,
        drawer_h="f2_dh",
        front_h="f2_ch - 2 * f2_ct - 2 * dr_gap")
    assert f2_c.bRepBodies.count == 9
    print("F2: 9 bodies — PASS")

    # ── F3: Small drawer in 14x11x5 case — lifted + rotated 30° CCW ──
    params.add("f3_cw", VI("14 in"), "in", "F3 case width")
    params.add("f3_cd", VI("11 in"), "in", "F3 case depth")
    params.add("f3_ch", VI("5 in"), "in", "F3 case height")
    params.add("f3_ct", VI("case_thick"), "in", "F3 case thickness")
    params.add("f3_x", VI("f2_x + f2_cw + 8 in"), "in", "F3 X offset")
    params.add("f3_lift", VI("5 in"), "in", "F3 lift off ground")

    f3_c = make_comp_at(root, "F3",
        x_cm=ctx.ev("f3_x"),
        z_cm=ctx.ev("f3_lift"),
        rot_z_deg=30.0).component
    build_case(f3_c, "f3", ctx.ev)
    build_drawer_in_case(f3_c, "f3", "d3", ctx.ev,
        front_thick="0.625 in", side_thick="0.375 in",
        bottom_thick="0.25 in",
        dt_tail_w="0.5 in",
        front_tail_count="2", back_tail_count="2",
        hbd_lap="0.1875 in")
    assert f3_c.bRepBodies.count == 9
    print("F3: 9 bodies — PASS")

    # ── Summary ──
    total = 0
    for occ in root.occurrences:
        c = occ.component
        n = c.bRepBodies.count
        names = [c.bRepBodies.item(i).name for i in range(n)]
        print(f"  {c.name}: {n} bodies -> {names}")
        total += n
    print(f"\n{'PASS' if total == 27 else 'FAIL'}: {total}/27 bodies")

    for occ in root.occurrences:
        c = occ.component
        for sk in c.sketches:
            sk.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
