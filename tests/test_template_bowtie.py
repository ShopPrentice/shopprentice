"""Test fixture for bowtie (butterfly key) template.

Covers every supported orientation, plus an edge-join case where one
bowtie bridges two separate boards:

  F1 Vertical slab single      — 2 bodies in 1 comp
     (Nakashima headboard — XZ face, long axis Z)
  F2 Vertical slab row         — 4 bodies in 1 comp
  F3 Vertical slab cross-comp  — 4 bodies across 2 comps
     (Slab in one comp, bowties in another — exercises combine's
      cross-component routing)
  F4 Horizontal tabletop row   — 4 bodies in 1 comp
     (Crack on top surface of a flat slab — XY face, long axis Y,
      crack runs in X)
  F5 Edge-join bowtie          — 3 bodies in 1 comp
     (Two boards glued edge-to-edge along X; bowtie inlaid across
      the joint on the top face. Long axis Y crosses the X-running
      joint line, waist X sits on the joint.)

Total: 2 + 4 + 4 + 4 + 3 = 17 bodies across 6 components.
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
    from woodworking.templates import bowtie

    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString

    ctx = sp.DesignContext(design)

    # Vertical slab (F1–F3)
    params.add("slab_w",     VI("24 in"),  "in", "Slab width (X)")
    params.add("slab_h",     VI("10 in"),  "in", "Slab height (Z)")
    params.add("slab_thick", VI("1.5 in"), "in", "Slab thickness (Y)")
    # Horizontal tabletop (F4)
    params.add("top_l",   VI("24 in"),  "in", "Tabletop length (X)")
    params.add("top_w",   VI("10 in"),  "in", "Tabletop width (Y)")
    params.add("top_t",   VI("1.5 in"), "in", "Tabletop thickness (Z)")
    # Edge-join boards (F5)
    params.add("eb_l",    VI("18 in"),  "in", "Edge board length (X)")
    params.add("eb_w",    VI("6 in"),   "in", "Edge board width (Y)")
    params.add("eb_t",    VI("1 in"),   "in", "Edge board thickness (Z)")
    # Bowtie dimensions
    params.add("bt_len",     VI("3 in"),    "in", "Bowtie length (long)")
    params.add("bt_end_w",   VI("1.5 in"),  "in", "Bowtie end width")
    params.add("bt_waist_w", VI("0.5 in"),  "in", "Bowtie waist width")
    params.add("bt_depth",   VI("0.5 in"),  "in", "Bowtie depth into slab")
    params.add("bt_spacing", VI("6 in"),    "in", "Bowtie spacing in row")
    params.add("n_bowties",  VI("3"),       "",   "Bowtie count in row")

    def build_vertical_slab(comp, prefix):
        """Slab on XZ face (sketch on XZ, extrude in Y)."""
        _, pr = sp.sketch_rect_model(comp, comp.xZConstructionPlane,
            ("0 in", "0 in", "0 in"),
            {"x": "slab_w", "z": "slab_h"}, f"{prefix}_Sk", ctx.ev)
        b = sp.ext_new(comp, pr, "slab_thick", prefix).bodies.item(0)
        b.name = prefix
        return b

    # ── F1: Vertical slab + single bowtie ──
    f1 = make_comp_at(root, "BT_Vert_Single").component
    f1_slab = build_vertical_slab(f1, "f1_Slab")

    bowtie.single(f1, f1.xZConstructionPlane,
        center=("slab_w / 2", "0 in", "slab_h / 2"),
        long_axis="z", short_axis="x",
        length="bt_len", end_w="bt_end_w",
        waist_w="bt_waist_w", depth="bt_depth",
        slab_body=f1_slab, name="f1_BT", ev=ctx.ev)

    assert f1.bRepBodies.count == 2, \
        f"F1 expected 2 bodies, got {f1.bRepBodies.count}"
    print("BT_Vert_Single: 2 bodies — PASS")

    # ── F2: Vertical slab + row of bowties ──
    f2 = make_comp_at(root, "BT_Vert_Row",
                       ctx.ev("slab_w") + 4 * 2.54).component
    f2_slab = build_vertical_slab(f2, "f2_Slab")

    bowtie.row(f2, f2.xZConstructionPlane,
        crack_axis="x",
        crack_center=("slab_w / 2", "0 in", "slab_h / 2"),
        count="n_bowties", spacing="bt_spacing",
        long_axis="z", short_axis="x",
        length="bt_len", end_w="bt_end_w",
        waist_w="bt_waist_w", depth="bt_depth",
        slab_body=f2_slab, name="f2_BT", ev=ctx.ev)

    assert f2.bRepBodies.count == 4, \
        f"F2 expected 4 bodies, got {f2.bRepBodies.count}"
    print("BT_Vert_Row: 4 bodies — PASS")

    # ── F3: Cross-component vertical slab + row of bowties ──
    f3_x = 2 * (ctx.ev("slab_w") + 4 * 2.54)
    f3_Slab = make_comp_at(root, "BT_Cross_Slab", f3_x).component
    f3_BT = make_comp_at(root, "BT_Cross_BTs", f3_x).component
    f3_slab_b = build_vertical_slab(f3_Slab, "f3_Slab")

    bowtie.row(f3_BT, f3_BT.xZConstructionPlane,
        crack_axis="x",
        crack_center=("slab_w / 2", "0 in", "slab_h / 2"),
        count="n_bowties", spacing="bt_spacing",
        long_axis="z", short_axis="x",
        length="bt_len", end_w="bt_end_w",
        waist_w="bt_waist_w", depth="bt_depth",
        slab_body=f3_slab_b, name="f3_BT", ev=ctx.ev)

    assert f3_Slab.bRepBodies.count == 1 and f3_BT.bRepBodies.count == 3, \
        f"F3 unexpected body counts: slab={f3_Slab.bRepBodies.count} bt={f3_BT.bRepBodies.count}"
    print("BT_Cross: 4 bodies across 2 comps — PASS")

    # ── F4: Horizontal tabletop + row of bowties ──
    # Flat slab on XY plane, crack on top surface running in X.
    # Bowtie long axis Y (crosses the X-crack), waist X (along crack).
    # Sketch plane is the top face at Z = top_t; extrude in -Z into the top.
    f4_y = ctx.ev("slab_h") + 4 * 2.54   # offset in Y away from F1/F2/F3
    f4 = make_comp_at(root, "BT_Top_Row", 0.0, f4_y).component

    _, pr = sp.sketch_rect_model(f4, f4.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "top_l", "y": "top_w"}, "f4_Top_Sk", ctx.ev)
    f4_top = sp.ext_new(f4, pr, "top_t", "f4_Top").bodies.item(0)
    f4_top.name = "f4_Top"

    # Top face plane at Z = top_t
    f4_top_pl = sp.off_plane(f4, f4.xYConstructionPlane, "top_t",
                              "f4_TopFace")
    bowtie.row(f4, f4_top_pl,
        crack_axis="x",
        crack_center=("top_l / 2", "top_w / 2", "top_t"),
        count="n_bowties", spacing="bt_spacing",
        long_axis="y", short_axis="x",
        length="bt_len", end_w="bt_end_w",
        waist_w="bt_waist_w", depth="-bt_depth",
        slab_body=f4_top, name="f4_BT", ev=ctx.ev)

    assert f4.bRepBodies.count == 4, \
        f"F4 expected 4 bodies, got {f4.bRepBodies.count}"
    print("BT_Top_Row: 4 bodies — PASS")

    # ── F5: Edge-joined boards + bowtie bridging ──
    # Two boards side-by-side along Y. Board A at Y=[0, eb_w], Board B
    # at Y=[eb_w, 2*eb_w]. Joint line at Y=eb_w, running in X. A single
    # bowtie straddles the joint on the top surface: long axis Y
    # (crosses the joint), waist along X (runs along joint line).
    f5_x = ctx.ev("top_l") + 4 * 2.54
    f5 = make_comp_at(root, "BT_EdgeJoin", f5_x, f4_y).component

    _, pr = sp.sketch_rect_model(f5, f5.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "eb_l", "y": "eb_w"}, "f5_A_Sk", ctx.ev)
    f5_A = sp.ext_new(f5, pr, "eb_t", "f5_A").bodies.item(0)
    f5_A.name = "f5_BoardA"

    _, pr = sp.sketch_rect_model(f5, f5.xYConstructionPlane,
        ("0 in", "eb_w", "0 in"),
        {"x": "eb_l", "y": "eb_w"}, "f5_B_Sk", ctx.ev)
    f5_B = sp.ext_new(f5, pr, "eb_t", "f5_B").bodies.item(0)
    f5_B.name = "f5_BoardB"

    # Top face (Z = eb_t). CUT from -Z (into both boards).
    f5_top_pl = sp.off_plane(f5, f5.xYConstructionPlane, "eb_t",
                              "f5_TopFace")

    # Build the bowtie body WITHOUT cutting (cut=False), then manually
    # CUT it into BOTH boards via combine_auto-style calls. The bowtie
    # bridges the Y=eb_w joint line.
    bt_body = bowtie.single(f5, f5_top_pl,
        center=("eb_l / 2", "eb_w", "eb_t"),
        long_axis="y", short_axis="x",
        length="bt_len", end_w="bt_end_w",
        waist_w="bt_waist_w", depth="-bt_depth",
        slab_body=None, name="f5_BT", ev=ctx.ev, cut=False)

    # CUT bowtie pocket into BOTH boards (keepTool=True so the bowtie
    # body persists as the inlay). This is the core edge-join use case:
    # one bowtie, two targets.
    sp.combine(f5_A, bt_body,
               adsk.fusion.FeatureOperations.CutFeatureOperation,
               True, "f5_BT_CutA")
    sp.combine(f5_B, bt_body,
               adsk.fusion.FeatureOperations.CutFeatureOperation,
               True, "f5_BT_CutB")

    assert f5.bRepBodies.count == 3, \
        f"F5 expected 3 bodies (A, B, bowtie), got {f5.bRepBodies.count}"
    print("BT_EdgeJoin: 3 bodies (bowtie bridges 2 boards) — PASS")

    # ── Summary ──
    total = 0
    for occ in root.occurrences:
        c = occ.component
        n = c.bRepBodies.count
        names = [c.bRepBodies.item(i).name for i in range(n)]
        print(f"  {c.name}: {n} bodies -> {names}")
        total += n
    expected = 17
    print(f"\n{'PASS' if total == expected else 'FAIL'}: {total}/{expected} bodies")

    for occ in root.occurrences:
        c = occ.component
        for sk in c.sketches:
            sk.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False
