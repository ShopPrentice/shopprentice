"""Test fixture for mortise & tenon template.

Tests both variants and orientations using face-based sketching:
  Blind_MT: Tenon on rail end face (X±), extruded into leg.
            Shoulders implicit (tenon smaller than rail face).
  Through_MT: Tenon on rail end face (X±), extends fully through leg + proud.
  Leg_Top_MT: Tenon on leg top face (Z+), extruded up into a top rail.
              Tests a different face orientation and reversed relationship
              (tenon on leg, mortise in rail).
  Cross_Through_MT: Same as Through_MT but each board (LegL, LegR, Rail)
              lives in its *own* component under root. Exercises
              through()'s cross-component routing — the mortise CUT
              must hop to root with assembly proxies via combine.

Blind_MT / Through_MT / Leg_Top_MT: 3 bodies each in one component.
Cross_Through_MT: 3 bodies across 3 components (1 body each).
Total: 4 × 3 = 12 bodies.
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


def build_frame(comp, prefix, ev):
    """Build 2 legs (mirror) + 1 rail between them."""
    from helpers import sp
    p = prefix

    mid = sp.off_plane(comp, comp.yZConstructionPlane,
                       "leg_w + rail_l / 2", f"{p}_Mid")

    # Left leg → mirror → right leg
    _, pr = sp.sketch_rect_model(comp, comp.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_w", "y": "leg_w"}, f"{p}_LegL_Sk", ev)
    leg_l = sp.ext_new(comp, pr, "leg_h", f"{p}_LegL").bodies.item(0)
    leg_l.name = f"{p}_Leg_L"
    leg_r = sp.mirror_body(comp, leg_l, mid, f"{p}_LegR_Mir").bodies.item(0)
    leg_r.name = f"{p}_Leg_R"

    # Rail (centered on leg in Y)
    rail_pl = sp.off_plane(comp, comp.xZConstructionPlane,
                           "(leg_w - rail_t) / 2", f"{p}_Rail_Pl")
    _, pr = sp.sketch_rect_model(comp, rail_pl,
        ("leg_w", "(leg_w - rail_t) / 2", "rail_z"),
        {"x": "rail_l", "z": "rail_w"}, f"{p}_Rail_Sk", ev)
    rail = sp.ext_new(comp, pr, "rail_t", f"{p}_Rail").bodies.item(0)
    rail.name = f"{p}_Rail"

    return leg_l, leg_r, rail, mid


def run(context):
    app = adsk.core.Application.get()

    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation

    global af, mt
    from helpers import sp
    from woodworking.templates import mortise_tenon as mt

    ctx = sp.DesignContext(design)

    # ── Shared parameters ──
    params.add("leg_w", VI("1.5 in"), "in", "Leg width")
    params.add("leg_h", VI("10 in"), "in", "Leg height")
    params.add("rail_w", VI("3 in"), "in", "Rail width (height)")
    params.add("rail_t", VI("0.75 in"), "in", "Rail thickness")
    params.add("rail_l", VI("12 in"), "in", "Rail length")
    params.add("rail_z", VI("5 in"), "in", "Rail Z offset")

    # ── Blind M&T ──
    # Tenon sketched on rail end face, extruded into leg.
    # Tenon is smaller than rail face → shoulders form naturally.
    #   tenon_w=2in < rail_w=3in → 0.5in shoulder top & bottom
    #   tenon_thick=0.5in < rail_t=0.75in → 0.125in shoulder each cheek
    mt.define_params(params, prefix="bmt",
        tenon_w="2 in", tenon_thick="0.5 in", tenon_depth="1 in")

    bmt_c = make_comp_at(root, "Blind_MT").component
    leg_l, leg_r, rail, mid = build_frame(bmt_c, "bmt", ctx.ev)

    left_face = sp.find_face(rail, "x", -1)
    right_face = sp.find_face(rail, "x", +1)

    mt.blind(bmt_c, left_face,
        origin=("leg_w", "(leg_w - bmt_tt) / 2",
                "rail_z + (rail_w - bmt_tw) / 2"),
        size={"y": "bmt_tt", "z": "bmt_tw"},
        depth_expr="bmt_td",
        tenon_body=rail, mortise_body=leg_l,
        name="bmt_L", ev=ctx.ev)
    mt.blind(bmt_c, right_face,
        origin=("leg_w + rail_l", "(leg_w - bmt_tt) / 2",
                "rail_z + (rail_w - bmt_tw) / 2"),
        size={"y": "bmt_tt", "z": "bmt_tw"},
        depth_expr="bmt_td",
        tenon_body=rail, mortise_body=leg_r,
        name="bmt_R", ev=ctx.ev)
    sp.combine(leg_l, [rail], CUT, True, "bmt_MortL")
    sp.combine(leg_r, [rail], CUT, True, "bmt_MortR")
    assert bmt_c.bRepBodies.count == 3
    print("Blind_MT: 3 bodies — PASS")

    # ── Through M&T ──
    # Tenon extends past far face of leg (proud).
    # through() CUTs mortise internally to avoid coplanar face splitting.
    params.add("tmt_proud", VI("0.125 in"), "in", "Through tenon proud")
    mt.define_params(params, prefix="tmt",
        tenon_w="1 in", tenon_thick="0.375 in",
        tenon_depth="leg_w + tmt_proud")
    params.add("tmt_x", VI("2 * leg_w + rail_l + 3 in"), "in",
               "TMT X offset")

    tmt_c = make_comp_at(root, "Through_MT", ctx.ev("tmt_x")).component
    leg_l, leg_r, rail, mid = build_frame(tmt_c, "tmt", ctx.ev)

    left_face = sp.find_face(rail, "x", -1)
    right_face = sp.find_face(rail, "x", +1)

    mt.through(tmt_c, left_face,
        origin=("leg_w", "(leg_w - tmt_tt) / 2",
                "rail_z + (rail_w - tmt_tw) / 2"),
        size={"y": "tmt_tt", "z": "tmt_tw"},
        depth_expr="tmt_td",
        tenon_body=rail, mortise_body=leg_l,
        name="tmt_L", ev=ctx.ev)
    mt.through(tmt_c, right_face,
        origin=("leg_w + rail_l", "(leg_w - tmt_tt) / 2",
                "rail_z + (rail_w - tmt_tw) / 2"),
        size={"y": "tmt_tt", "z": "tmt_tw"},
        depth_expr="tmt_td",
        tenon_body=rail, mortise_body=leg_r,
        name="tmt_R", ev=ctx.ev)
    # No separate CUT needed — through() CUTs mortise body internally.
    assert tmt_c.bRepBodies.count == 3
    print("Through_MT: 3 bodies — PASS")

    # ── Leg Top M&T ──
    # Tenon on leg top face (Z+), extruded upward into a top rail.
    # Tests different face orientation and reversed relationship:
    #   tenon_body = leg, mortise_body = top_rail.
    # Top rail spans both legs, sitting on top.
    params.add("lmt_rh", VI("2 in"), "in", "Top rail height")
    params.add("lmt_span", VI("10 in"), "in", "Span between legs")
    mt.define_params(params, prefix="lmt",
        tenon_w="1 in", tenon_thick="1 in", tenon_depth="1 in")
    params.add("lmt_x", VI("tmt_x + 2 * leg_w + rail_l + 3 in"), "in",
               "LMT X offset")

    lmt_c = make_comp_at(root, "Leg_Top_MT", ctx.ev("lmt_x")).component

    # Midplane for leg mirror
    lmt_mid = sp.off_plane(lmt_c, lmt_c.yZConstructionPlane,
                            "(2 * leg_w + lmt_span) / 2", "lmt_Mid")

    # Left leg
    _, pr = sp.sketch_rect_model(lmt_c, lmt_c.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_w", "y": "leg_w"}, "lmt_LegL_Sk", ctx.ev)
    leg_l = sp.ext_new(lmt_c, pr, "leg_h", "lmt_LegL").bodies.item(0)
    leg_l.name = "lmt_Leg_L"

    # Mirror → right leg
    leg_r = sp.mirror_body(lmt_c, leg_l, lmt_mid, "lmt_LegR_Mir").bodies.item(0)
    leg_r.name = "lmt_Leg_R"

    # Top rail: spans full width, sits on top of legs
    rail_pl = sp.off_plane(lmt_c, lmt_c.xYConstructionPlane,
                            "leg_h", "lmt_TopRail_Pl")
    _, pr = sp.sketch_rect_model(lmt_c, rail_pl,
        ("0 in", "0 in", "leg_h"),
        {"x": "2 * leg_w + lmt_span", "y": "leg_w"}, "lmt_Rail_Sk", ctx.ev)
    top_rail = sp.ext_new(lmt_c, pr, "lmt_rh", "lmt_TopRail").bodies.item(0)
    top_rail.name = "lmt_TopRail"

    # Tenon on left leg's top face, extruded up into rail.
    # Tenon centered on leg top: 1in × 1in square, 1in deep into rail.
    left_top = sp.find_face(leg_l, "z", +1)
    mt.blind(lmt_c, left_top,
        origin=("(leg_w - lmt_tw) / 2", "(leg_w - lmt_tt) / 2", "leg_h"),
        size={"x": "lmt_tw", "y": "lmt_tt"},
        depth_expr="lmt_td",
        tenon_body=leg_l, mortise_body=top_rail,
        name="lmt_L", ev=ctx.ev)

    right_top = sp.find_face(leg_r, "z", +1)
    mt.blind(lmt_c, right_top,
        origin=("leg_w + lmt_span + (leg_w - lmt_tw) / 2",
                "(leg_w - lmt_tt) / 2", "leg_h"),
        size={"x": "lmt_tw", "y": "lmt_tt"},
        depth_expr="lmt_td",
        tenon_body=leg_r, mortise_body=top_rail,
        name="lmt_R", ev=ctx.ev)

    # CUT rail with both legs (tenons create mortise pockets)
    sp.combine(top_rail, [leg_l], CUT, True, "lmt_MortL")
    sp.combine(top_rail, [leg_r], CUT, True, "lmt_MortR")
    assert lmt_c.bRepBodies.count == 3
    print("Leg_Top_MT: 3 bodies — PASS")

    # ── Cross-component Through M&T ──
    # LegL, LegR, Rail each in their own root-level component.
    # through() must route its mortise CUT to root with assembly
    # proxies because tenon_b (built in Rail's comp) and mortise_body
    # (LegL / LegR) live in different components.
    params.add("xmt_proud", VI("0.125 in"), "in", "Cross through proud")
    mt.define_params(params, prefix="xmt",
        tenon_w="1 in", tenon_thick="0.375 in",
        tenon_depth="leg_w + xmt_proud")
    params.add("xmt_x", VI("lmt_x + 2 * leg_w + lmt_span + 6 in"), "in",
               "XMT X offset")

    xmt_x = ctx.ev("xmt_x")

    # Each board in its own component, positioned by occurrence transform
    # so world coords match what the sketches produce.
    xmt_legL = make_comp_at(root, "XMT_LegL", xmt_x).component
    xmt_legR_x = xmt_x + ctx.ev("leg_w") + ctx.ev("rail_l")
    xmt_legR = make_comp_at(root, "XMT_LegR", xmt_legR_x).component
    xmt_rail_c = make_comp_at(root, "XMT_Rail", xmt_x).component

    # Left leg — in XMT_LegL at component origin (world at xmt_x)
    _, pr = sp.sketch_rect_model(xmt_legL, xmt_legL.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_w", "y": "leg_w"}, "xmt_LegL_Sk", ctx.ev)
    leg_l = sp.ext_new(xmt_legL, pr, "leg_h", "xmt_LegL").bodies.item(0)
    leg_l.name = "xmt_Leg_L"

    # Right leg — in XMT_LegR at component origin (world at xmt_legR_x)
    _, pr = sp.sketch_rect_model(xmt_legR, xmt_legR.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_w", "y": "leg_w"}, "xmt_LegR_Sk", ctx.ev)
    leg_r = sp.ext_new(xmt_legR, pr, "leg_h", "xmt_LegR").bodies.item(0)
    leg_r.name = "xmt_Leg_R"

    # Rail — in XMT_Rail, sketched at world-matching X (leg_w from its
    # comp origin = xmt_x → world-X = xmt_x + leg_w, i.e. right face of
    # left leg). Uses same expressions as intra-comp fixture.
    xmt_rail_pl = sp.off_plane(xmt_rail_c, xmt_rail_c.xZConstructionPlane,
                               "(leg_w - rail_t) / 2", "xmt_Rail_Pl")
    _, pr = sp.sketch_rect_model(xmt_rail_c, xmt_rail_pl,
        ("leg_w", "(leg_w - rail_t) / 2", "rail_z"),
        {"x": "rail_l", "z": "rail_w"}, "xmt_Rail_Sk", ctx.ev)
    rail = sp.ext_new(xmt_rail_c, pr, "rail_t", "xmt_Rail").bodies.item(0)
    rail.name = "xmt_Rail"

    # through() — pass xmt_rail_c as comp (where tenon lives), leg in
    # a DIFFERENT comp. combine inside through() routes the
    # mortise CUT to root with proxies.
    left_face = sp.find_face(rail, "x", -1)
    right_face = sp.find_face(rail, "x", +1)
    mt.through(xmt_rail_c, left_face,
        origin=("leg_w", "(leg_w - xmt_tt) / 2",
                "rail_z + (rail_w - xmt_tw) / 2"),
        size={"y": "xmt_tt", "z": "xmt_tw"},
        depth_expr="xmt_td",
        tenon_body=rail, mortise_body=leg_l,
        name="xmt_L", ev=ctx.ev)
    mt.through(xmt_rail_c, right_face,
        origin=("leg_w + rail_l", "(leg_w - xmt_tt) / 2",
                "rail_z + (rail_w - xmt_tw) / 2"),
        size={"y": "xmt_tt", "z": "xmt_tw"},
        depth_expr="xmt_td",
        tenon_body=rail, mortise_body=leg_r,
        name="xmt_R", ev=ctx.ev)

    assert xmt_legL.bRepBodies.count == 1, \
        f"XMT_LegL expected 1 body, got {xmt_legL.bRepBodies.count}"
    assert xmt_legR.bRepBodies.count == 1, \
        f"XMT_LegR expected 1 body, got {xmt_legR.bRepBodies.count}"
    assert xmt_rail_c.bRepBodies.count == 1, \
        f"XMT_Rail expected 1 body, got {xmt_rail_c.bRepBodies.count}"
    print("Cross_Through_MT: 3 bodies across 3 components — PASS")

    # ── Summary ──
    total = 0
    for occ in root.occurrences:
        c = occ.component
        n = c.bRepBodies.count
        names = [c.bRepBodies.item(i).name for i in range(n)]
        print(f"  {c.name}: {n} bodies -> {names}")
        total += n
    print(f"\n{'PASS' if total == 12 else 'FAIL'}: {total}/12 bodies")

    for occ in root.occurrences:
        c = occ.component
        for sk in c.sketches:
            sk.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
