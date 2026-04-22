"""Test fixture for bowtie (butterfly key) template.

Covers three cases:

  F1 Single:   One bowtie CUT into a slab in the same component. 2 bodies.
  F2 Row:      Three bowties in a row along a crack, CUT into slab. 4 bodies.
  F3 Cross:    Slab in one component, bowties in another. Exercises
               the CUT's cross-component routing via combine.
               4 bodies across 2 components.

Total: 2 + 4 + 4 = 10 bodies.

This fixture also guards against a regression where a local list
variable inside single() shadowed the imported ``sp`` module and
silently broke the CUT call.
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
    from woodworking.templates import bowtie

    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString

    ctx = sp.DesignContext(design)

    params.add("slab_l", VI("24 in"), "in", "Slab length")
    params.add("slab_w", VI("10 in"), "in", "Slab width")
    params.add("slab_t", VI("1.5 in"), "in", "Slab thickness")
    params.add("bt_len", VI("3 in"), "in", "Bowtie length")
    params.add("bt_end_w", VI("1.5 in"), "in", "Bowtie end width")
    params.add("bt_waist_w", VI("0.5 in"), "in", "Bowtie waist width")
    params.add("bt_depth", VI("0.5 in"), "in", "Bowtie depth")
    params.add("bt_spacing", VI("6 in"), "in", "Bowtie spacing")
    params.add("n_bowties", VI("3"), "", "Bowtie count in row")

    # ── F1: Single bowtie on a slab, one component ──
    f1 = make_comp_at(root, "BT_Single").component
    _, pr = sp.sketch_rect_model(f1, f1.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "slab_l", "y": "slab_w"}, "f1_Slab_Sk", ctx.ev)
    f1_slab = sp.ext_new(f1, pr, "slab_t", "f1_Slab").bodies.item(0)
    f1_slab.name = "f1_Slab"

    top_pl = sp.off_plane(f1, f1.xYConstructionPlane, "slab_t", "f1_Top")
    bowtie.single(f1, top_pl,
        center=("slab_l / 2", "slab_w / 2", "slab_t"),
        long_axis="x", length="bt_len", end_w="bt_end_w",
        waist_w="bt_waist_w", depth="bt_depth",
        slab_body=f1_slab, name="f1_BT", ev=ctx.ev)

    assert f1.bRepBodies.count == 2, \
        f"F1 expected 2 bodies (slab + bowtie), got {f1.bRepBodies.count}"
    print("BT_Single: 2 bodies — PASS")

    # ── F2: Row of 3 bowties ──
    params.add("f2_x", VI("slab_l + 3 in"), "in", "F2 X offset")
    f2 = make_comp_at(root, "BT_Row", ctx.ev("f2_x")).component

    _, pr = sp.sketch_rect_model(f2, f2.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "slab_l", "y": "slab_w"}, "f2_Slab_Sk", ctx.ev)
    f2_slab = sp.ext_new(f2, pr, "slab_t", "f2_Slab").bodies.item(0)
    f2_slab.name = "f2_Slab"

    f2_top_pl = sp.off_plane(f2, f2.xYConstructionPlane, "slab_t", "f2_Top")
    bowtie.row(f2, f2_top_pl,
        crack_axis="x",
        crack_center=("slab_l / 2", "slab_w / 2", "slab_t"),
        count="n_bowties", spacing="bt_spacing",
        long_axis="z", length="bt_len", end_w="bt_end_w",
        waist_w="bt_waist_w", depth="bt_depth",
        slab_body=f2_slab, name="f2_BT", ev=ctx.ev)

    assert f2.bRepBodies.count == 4, \
        f"F2 expected 4 bodies (slab + 3 bowties), got {f2.bRepBodies.count}"
    print("BT_Row: 4 bodies — PASS")

    # ── F3: Cross-component — slab in one comp, bowties in another ──
    params.add("f3_x", VI("f2_x + slab_l + 3 in"), "in", "F3 X offset")
    f3_x = ctx.ev("f3_x")
    f3_Slab = make_comp_at(root, "BT_Cross_Slab", f3_x).component
    f3_BT = make_comp_at(root, "BT_Cross_BTs", f3_x).component

    _, pr = sp.sketch_rect_model(f3_Slab, f3_Slab.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "slab_l", "y": "slab_w"}, "f3_Slab_Sk", ctx.ev)
    f3_slab_b = sp.ext_new(f3_Slab, pr, "slab_t", "f3_Slab").bodies.item(0)
    f3_slab_b.name = "f3_Slab"

    # Bowties live in f3_BT — the CUT must route cross-component.
    f3_top_pl = sp.off_plane(f3_BT, f3_BT.xYConstructionPlane,
                              "slab_t", "f3_Top")
    bowtie.row(f3_BT, f3_top_pl,
        crack_axis="x",
        crack_center=("slab_l / 2", "slab_w / 2", "slab_t"),
        count="n_bowties", spacing="bt_spacing",
        long_axis="z", length="bt_len", end_w="bt_end_w",
        waist_w="bt_waist_w", depth="bt_depth",
        slab_body=f3_slab_b, name="f3_BT", ev=ctx.ev)

    assert f3_Slab.bRepBodies.count == 1, \
        f"F3_Slab expected 1 body, got {f3_Slab.bRepBodies.count}"
    assert f3_BT.bRepBodies.count == 3, \
        f"F3_BT expected 3 bowtie bodies, got {f3_BT.bRepBodies.count}"
    print("BT_Cross: 4 bodies across 2 comps — PASS")

    # ── Summary ──
    total = 0
    for occ in root.occurrences:
        c = occ.component
        n = c.bRepBodies.count
        names = [c.bRepBodies.item(i).name for i in range(n)]
        print(f"  {c.name}: {n} bodies -> {names}")
        total += n
    print(f"\n{'PASS' if total == 10 else 'FAIL'}: {total}/10 bodies")

    for occ in root.occurrences:
        c = occ.component
        for sk in c.sketches:
            sk.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False
