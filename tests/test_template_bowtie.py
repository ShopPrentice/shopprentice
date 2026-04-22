"""Test fixture for bowtie (butterfly key) template.

The bowtie template is oriented for slabs with a vertical XZ face — the
classic Nakashima-style live-edge headboard / tabletop crack. The
hourglass lies *flat* on that XZ face (its long dimension is in X or Z)
and extrudes in Y into the slab body.

Each fixture builds a slab whose visible face is XZ. The crack runs in
X (along the grain), so bowties are vertical (``long_axis="z"``) and
cross the grain direction.

  F1 Single:   One bowtie CUT into a slab in the same component. 2 bodies.
  F2 Row:      Three bowties in a row along a crack, CUT into slab. 4 bodies.
  F3 Cross:    Slab in one component, bowties in another. Exercises
               the CUT's cross-component routing via sp.combine.
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

    # Slab: 24" wide (X), 10" tall (Z), 1.5" thick (Y).
    # Visible face is XZ at Y = 0; back face is at Y = slab_thick.
    params.add("slab_w", VI("24 in"),  "in", "Slab width (X)")
    params.add("slab_h", VI("10 in"),  "in", "Slab height (Z)")
    params.add("slab_thick", VI("1.5 in"), "in", "Slab thickness (Y)")
    params.add("bt_len", VI("3 in"),    "in", "Bowtie length")
    params.add("bt_end_w", VI("1.5 in"), "in", "Bowtie end width")
    params.add("bt_waist_w", VI("0.5 in"), "in", "Bowtie waist width")
    params.add("bt_depth", VI("0.5 in"),  "in", "Bowtie depth (into slab, -Y)")
    params.add("bt_spacing", VI("6 in"),  "in", "Bowtie spacing along crack")
    params.add("n_bowties", VI("3"), "", "Bowtie count in row")

    def build_slab(comp, prefix):
        """Build a vertical slab on the XZ plane, extruded in Y."""
        _, pr = sp.sketch_rect_model(comp, comp.xZConstructionPlane,
            ("0 in", "0 in", "0 in"),
            {"x": "slab_w", "z": "slab_h"}, f"{prefix}_Sk", ctx.ev)
        return sp.ext_new(comp, pr, "slab_thick", f"{prefix}").bodies.item(0)

    # ── F1: Single bowtie on a slab, one component ──
    f1 = make_comp_at(root, "BT_Single").component
    f1_slab = build_slab(f1, "f1_Slab")
    f1_slab.name = "f1_Slab"

    # Face plane: Y=0 (front face of slab). Bowtie sketch lies on XZ.
    # Long axis = Z (vertical, crossing the horizontal X-direction crack).
    bowtie.single(f1, f1.xZConstructionPlane,
        center=("slab_w / 2", "0 in", "slab_h / 2"),
        long_axis="z", length="bt_len", end_w="bt_end_w",
        waist_w="bt_waist_w", depth="bt_depth",
        slab_body=f1_slab, name="f1_BT", ev=ctx.ev)

    assert f1.bRepBodies.count == 2, \
        f"F1 expected 2 bodies, got {f1.bRepBodies.count}"
    print("BT_Single: 2 bodies — PASS")

    # ── F2: Row of 3 bowties along an X-direction crack ──
    params.add("f2_x", VI("slab_w + 4 in"), "in", "F2 X offset")
    f2 = make_comp_at(root, "BT_Row", ctx.ev("f2_x")).component
    f2_slab = build_slab(f2, "f2_Slab")
    f2_slab.name = "f2_Slab"

    bowtie.row(f2, f2.xZConstructionPlane,
        crack_axis="x",
        crack_center=("slab_w / 2", "0 in", "slab_h / 2"),
        count="n_bowties", spacing="bt_spacing",
        long_axis="z", length="bt_len", end_w="bt_end_w",
        waist_w="bt_waist_w", depth="bt_depth",
        slab_body=f2_slab, name="f2_BT", ev=ctx.ev)

    assert f2.bRepBodies.count == 4, \
        f"F2 expected 4 bodies, got {f2.bRepBodies.count}"
    print("BT_Row: 4 bodies — PASS")

    # ── F3: Cross-component — slab in one comp, bowties in another ──
    params.add("f3_x", VI("f2_x + slab_w + 4 in"), "in", "F3 X offset")
    f3_x = ctx.ev("f3_x")
    f3_Slab = make_comp_at(root, "BT_Cross_Slab", f3_x).component
    f3_BT = make_comp_at(root, "BT_Cross_BTs", f3_x).component
    f3_slab_b = build_slab(f3_Slab, "f3_Slab")
    f3_slab_b.name = "f3_Slab"

    # Bowties live in f3_BT — the CUT must route cross-component.
    bowtie.row(f3_BT, f3_BT.xZConstructionPlane,
        crack_axis="x",
        crack_center=("slab_w / 2", "0 in", "slab_h / 2"),
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
