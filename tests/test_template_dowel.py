"""Test fixture for dowel joint template.

Exercises dowel.single() and dowel.grid() in intra-component and
cross-component configurations:

  F1 Intra_Single: Two abutting boards + one dowel. Same component.
                   3 bodies (left, right, dowel).
  F2 Intra_Grid:   Two abutting boards + 3 grid dowels. Same component.
                   5 bodies.
  F3 Cross_Grid:   Left in one root component, Right in another,
                   voids in a third. Exercises grid()'s cross-component
                   CUTs via combine. 5 bodies across 3 comps.

Total: 3 + 5 + 5 = 13 bodies.
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
    from woodworking.templates import dowel

    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString

    ctx = sp.DesignContext(design)

    # Shared dimensions
    params.add("bd_w", VI("10 in"), "in", "Board width (X)")
    params.add("bd_d", VI("4 in"),  "in", "Board depth (Y)")
    params.add("bd_t", VI("0.75 in"), "in", "Board thickness (Z)")
    params.add("dw_d", VI("0.375 in"), "in", "Dowel diameter")
    params.add("dw_depth", VI("0.75 in"), "in", "Dowel depth per side")
    params.add("dw_count", VI("3"), "", "Dowel count")
    params.add("dw_sp", VI("3 in"), "in", "Dowel spacing")

    # ── F1: Intra single dowel ──
    f1 = make_comp_at(root, "DW_Intra_Single").component

    _, pr = sp.sketch_rect_model(f1, f1.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "bd_w", "y": "bd_d"}, "f1_Left_Sk", ctx.ev)
    f1_left = sp.ext_new(f1, pr, "bd_t", "f1_Left").bodies.item(0)
    f1_left.name = "f1_Left"

    _, pr = sp.sketch_rect_model(f1, f1.xYConstructionPlane,
        ("0 in", "bd_d", "0 in"),
        {"x": "bd_w", "y": "bd_d"}, "f1_Right_Sk", ctx.ev)
    f1_right = sp.ext_new(f1, pr, "bd_t", "f1_Right").bodies.item(0)
    f1_right.name = "f1_Right"

    f1_joint = sp.off_plane(f1, f1.xZConstructionPlane, "bd_d", "f1_Joint")
    dowel.single(f1, f1_joint,
        center=("bd_w / 2", "bd_d", "bd_t / 2"),
        diameter="dw_d", depth="dw_depth",
        body_a=f1_left, body_b=f1_right,
        name="f1_DW", ev=ctx.ev)

    assert f1.bRepBodies.count == 3, \
        f"F1 expected 3 bodies, got {f1.bRepBodies.count}"
    print("DW_Intra_Single: 3 bodies — PASS")

    # ── F2: Intra grid of 3 dowels ──
    params.add("f2_x", VI("bd_w + 3 in"), "in", "F2 X offset")
    f2 = make_comp_at(root, "DW_Intra_Grid", ctx.ev("f2_x")).component

    _, pr = sp.sketch_rect_model(f2, f2.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "bd_w", "y": "bd_d"}, "f2_Left_Sk", ctx.ev)
    f2_left = sp.ext_new(f2, pr, "bd_t", "f2_Left").bodies.item(0)
    f2_left.name = "f2_Left"

    _, pr = sp.sketch_rect_model(f2, f2.xYConstructionPlane,
        ("0 in", "bd_d", "0 in"),
        {"x": "bd_w", "y": "bd_d"}, "f2_Right_Sk", ctx.ev)
    f2_right = sp.ext_new(f2, pr, "bd_t", "f2_Right").bodies.item(0)
    f2_right.name = "f2_Right"

    f2_joint = sp.off_plane(f2, f2.xZConstructionPlane, "bd_d", "f2_Joint")
    dowel.grid(f2, f2_joint,
        start=("2 in", "bd_d", "bd_t / 2"),
        step_axis="x", step_expr="dw_sp", count_expr="dw_count",
        diameter="dw_d", depth="dw_depth",
        body_a=f2_left, body_b=f2_right,
        name="f2_DW", ev=ctx.ev)

    assert f2.bRepBodies.count == 5, \
        f"F2 expected 5 bodies, got {f2.bRepBodies.count}"
    print("DW_Intra_Grid: 5 bodies — PASS")

    # ── F3: Cross-component grid ──
    # Left in F3_Left comp, Right in F3_Right comp, dowel voids in
    # F3_Voids comp. grid() must route the CUTs to root with proxies.
    params.add("f3_x", VI("f2_x + bd_w + 3 in"), "in", "F3 X offset")
    f3_x = ctx.ev("f3_x")

    f3_L = make_comp_at(root, "DW_Cross_Left", f3_x).component
    f3_R = make_comp_at(root, "DW_Cross_Right", f3_x).component
    f3_V = make_comp_at(root, "DW_Cross_Voids", f3_x).component

    _, pr = sp.sketch_rect_model(f3_L, f3_L.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "bd_w", "y": "bd_d"}, "f3_Left_Sk", ctx.ev)
    f3_left = sp.ext_new(f3_L, pr, "bd_t", "f3_Left").bodies.item(0)
    f3_left.name = "f3_Left"

    _, pr = sp.sketch_rect_model(f3_R, f3_R.xYConstructionPlane,
        ("0 in", "bd_d", "0 in"),
        {"x": "bd_w", "y": "bd_d"}, "f3_Right_Sk", ctx.ev)
    f3_right = sp.ext_new(f3_R, pr, "bd_t", "f3_Right").bodies.item(0)
    f3_right.name = "f3_Right"

    f3_joint = sp.off_plane(f3_V, f3_V.xZConstructionPlane, "bd_d",
                             "f3_Joint")
    dowel.grid(f3_V, f3_joint,
        start=("2 in", "bd_d", "bd_t / 2"),
        step_axis="x", step_expr="dw_sp", count_expr="dw_count",
        diameter="dw_d", depth="dw_depth",
        body_a=f3_left, body_b=f3_right,
        name="f3_DW", ev=ctx.ev)

    assert f3_L.bRepBodies.count == 1, \
        f"F3_Left expected 1 body, got {f3_L.bRepBodies.count}"
    assert f3_R.bRepBodies.count == 1, \
        f"F3_Right expected 1 body, got {f3_R.bRepBodies.count}"
    assert f3_V.bRepBodies.count == 3, \
        f"F3_Voids expected 3 dowel bodies, got {f3_V.bRepBodies.count}"
    print("DW_Cross_Grid: 5 bodies across 3 comps — PASS")

    # ── Summary ──
    total = 0
    for occ in root.occurrences:
        c = occ.component
        n = c.bRepBodies.count
        names = [c.bRepBodies.item(i).name for i in range(n)]
        print(f"  {c.name}: {n} bodies -> {names}")
        total += n
    print(f"\n{'PASS' if total == 13 else 'FAIL'}: {total}/13 bodies")

    for occ in root.occurrences:
        c = occ.component
        for sk in c.sketches:
            sk.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
