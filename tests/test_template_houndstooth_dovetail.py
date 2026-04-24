"""Test fixture for houndstooth dovetail template.

Houndstooth composes on top of through or half-blind — each tail gets
a smaller inverted-trapezoid void cut from its wide face. This fixture
exercises:

  H1: Through-houndstooth, default proportions (intra-component corner)
  H2: Half-blind-houndstooth, default proportions (intra-component corner)
  H3: Through-houndstooth with explicit ht_small_w / ht_depth (overrides)
  H4: Through-houndstooth with edge padding (pad > 0)
  H5: Half-blind-houndstooth with edge padding
  H6: Through-houndstooth cross-component (pin + tail in separate comps)

Each component has one front (pin) board + one side (tail) board,
meeting at a single corner, with 5 houndstooth tails joining them.
"""
import adsk.core
import adsk.fusion
import sys


def _add_param(params, name, expr, unit, comment):
    """Add a param, skipping if one with the same name already exists."""
    existing = params.itemByName(name)
    if existing is None:
        VI = adsk.core.ValueInput.createByString
        params.add(name, VI(expr), unit, comment)


def build_houndstooth_box(root, prefix, variant,
                          l_expr, w_expr, h_expr,
                          front_t_expr, side_t_expr,
                          x_off_expr, y_off_expr,
                          dt_prefix, ev,
                          lap_expr=None):
    """Build a 1-corner box with houndstooth dovetails.

    Creates a front (pin) board and a left (tail) board in a single
    component, then calls houndstooth_dovetail.corner() at the FL corner.

    Args:
        root: Root component.
        prefix: Name prefix for the component + bodies.
        variant: "through" or "half_blind".
        l_expr, w_expr, h_expr: Box dimension expressions.
        front_t_expr: Front (pin) board thickness.
        side_t_expr: Side (tail) board thickness.
        x_off_expr, y_off_expr: Grid position.
        dt_prefix: Dovetail parameter prefix (e.g. "dt1", "dt2").
        ev: Evaluator.
        lap_expr: Required for variant="half_blind".
    """
    from helpers import sp
    from woodworking.templates import houndstooth_dovetail

    occ = sp.make_comp(root, prefix)
    comp = occ.component

    # Front (pin) board: lies in xZ plane at y = y_off_expr, runs in X
    front_pl = sp.off_plane(comp, comp.xZConstructionPlane,
                             y_off_expr, f"{prefix}_FrontPl")
    sk, pr = sp.sketch_rect_model(comp, front_pl,
        (x_off_expr, y_off_expr, "0 in"),
        {"x": l_expr, "z": h_expr}, f"{prefix}_Front_Sk", ev)
    front = sp.ext_new(comp, pr, front_t_expr, f"{prefix}_Front").bodies.item(0)
    front.name = f"{prefix}_Front"

    # Left (tail) board: inset by front_t on the y axis so its front end
    # meets the front board's back face
    tail_y_expr = f"{y_off_expr} + {front_t_expr}"
    left_pl = sp.off_plane(comp, comp.yZConstructionPlane,
                            x_off_expr, f"{prefix}_LeftPl")
    sk, pr = sp.sketch_rect_model(comp, left_pl,
        (x_off_expr, tail_y_expr, "0 in"),
        {"y": f"{w_expr} - {front_t_expr}", "z": h_expr},
        f"{prefix}_Left_Sk", ev)
    left = sp.ext_new(comp, pr, side_t_expr, f"{prefix}_Left").bodies.item(0)
    left.name = f"{prefix}_Left"

    # Call houndstooth.corner with the right thick / y_wide for the variant
    if variant == "through":
        y_wide_v = ev(y_off_expr)
        y_narrow_v = ev(y_off_expr) + ev(front_t_expr)
        y_wide_expr_v = y_off_expr
        thick_expr_v = front_t_expr
    elif variant == "half_blind":
        if lap_expr is None:
            raise ValueError("half_blind variant requires lap_expr")
        y_wide_v = ev(y_off_expr) + ev(lap_expr)
        y_narrow_v = ev(y_off_expr) + ev(front_t_expr)
        y_wide_expr_v = f"{y_off_expr} + {lap_expr}"
        thick_expr_v = f"{dt_prefix}_socket_depth"
    else:
        raise ValueError(f"Unknown variant: {variant}")

    houndstooth_dovetail.corner(
        pin_body=front, tail_body=left, plane=left_pl,
        x_model=ev(x_off_expr),
        y_wide=y_wide_v, y_narrow=y_narrow_v,
        y_wide_expr=y_wide_expr_v,
        thick_expr=thick_expr_v,
        dist_expr=side_t_expr,
        name=prefix, prefix=dt_prefix, ev=ev)

    n = comp.bRepBodies.count
    names = [comp.bRepBodies.item(i).name for i in range(n)]
    print(f"  {prefix} {variant}-houndstooth: {n} bodies -> {names}")
    return {"comp": comp, "count": n, "names": names}


def run(context):
    app = adsk.core.Application.get()

    for name in list(sys.modules):
        if name == "helpers" or name.startswith("helpers."):
            del sys.modules[name]
        if name == "woodworking" or name.startswith("woodworking."):
            del sys.modules[name]

    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    root = design.rootComponent
    params = design.userParameters

    from helpers import sp
    from woodworking.templates import dovetail as through_dovetail
    from woodworking.templates import half_blind_dovetail
    from woodworking.templates import houndstooth_dovetail

    ctx = sp.DesignContext(design)
    ev = ctx.ev

    # Grid spacing between fixtures along X
    _add_param(params, "ht_grid_x", "14 in", "in", "Houndstooth grid X spacing")
    _add_param(params, "ht_grid_y", "12 in", "in", "Houndstooth grid Y spacing")

    # ================================================================
    # H1: Through-houndstooth, default proportions
    # ================================================================
    print("=" * 50)
    print("H1: Through-houndstooth, default proportions")
    print("=" * 50)

    _add_param(params, "h1_l", "8 in", "in", "H1 length")
    _add_param(params, "h1_w", "6 in", "in", "H1 width")
    _add_param(params, "h1_h", "5 in", "in", "H1 height")
    _add_param(params, "h1_ft", "0.75 in", "in", "H1 front thick")
    _add_param(params, "h1_st", "0.5 in", "in", "H1 side thick")

    through_dovetail.define_params(params, prefix="dt1",
        angle="8 deg", tail_w="0.75 in", tail_count="5",
        joint_h_expr="h1_h", thick_expr="h1_ft")
    houndstooth_dovetail.add_params(params, prefix="dt1")  # defaults

    # Validate derived defaults
    ht_small_v = ev("dt1_ht_small_w") / 2.54
    ht_depth_v = ev("dt1_ht_depth") / 2.54
    tail_w_v = ev("dt1_tail_w") / 2.54
    assert abs(ht_small_v - tail_w_v / 7) < 0.001, (
        f"H1: ht_small_w default should be tail_w/7, got {ht_small_v:.4f}")
    assert abs(ht_depth_v - tail_w_v * 3 / 5) < 0.001, (
        f"H1: ht_depth default should be tail_w*3/5, got {ht_depth_v:.4f}")

    r1 = build_houndstooth_box(root, "H1", "through",
        "h1_l", "h1_w", "h1_h", "h1_ft", "h1_st",
        "0 in", "0 in", "dt1", ev)
    assert r1["count"] == 2, f"H1: expected 2, got {r1['count']}"
    print(f"H1: PASS (defaults: small_w={ht_small_v:.4f}\", depth={ht_depth_v:.4f}\")\n")

    # ================================================================
    # H2: Half-blind-houndstooth, default proportions
    # ================================================================
    print("=" * 50)
    print("H2: Half-blind-houndstooth, default proportions")
    print("=" * 50)

    _add_param(params, "h2_l", "8 in", "in", "H2 length")
    _add_param(params, "h2_w", "6 in", "in", "H2 width")
    _add_param(params, "h2_h", "5 in", "in", "H2 height")
    _add_param(params, "h2_ft", "0.75 in", "in", "H2 front thick")
    _add_param(params, "h2_st", "0.5 in", "in", "H2 side thick")
    _add_param(params, "h2_x", "ht_grid_x", "in", "H2 X offset")

    half_blind_dovetail.define_params(params, prefix="dt2",
        angle="8 deg", tail_w="0.75 in", tail_count="5",
        joint_h_expr="h2_h", pin_thick_expr="h2_ft", lap="0.25 in")
    houndstooth_dovetail.add_params(params, prefix="dt2")

    # Void depth must be less than socket depth or the void punches through
    assert ev("dt2_ht_depth") < ev("dt2_socket_depth"), (
        "H2: ht_depth should be < socket_depth for half-blind houndstooth")

    r2 = build_houndstooth_box(root, "H2", "half_blind",
        "h2_l", "h2_w", "h2_h", "h2_ft", "h2_st",
        "h2_x", "0 in", "dt2", ev, lap_expr="dt2_lap")
    assert r2["count"] == 2, f"H2: expected 2, got {r2['count']}"
    print("H2: PASS (half-blind void stops short of socket opening)\n")

    # ================================================================
    # H3: Through-houndstooth with explicit ht_small_w / ht_depth overrides
    # ================================================================
    print("=" * 50)
    print("H3: Through-houndstooth with custom proportions")
    print("=" * 50)

    _add_param(params, "h3_l", "8 in", "in", "H3 length")
    _add_param(params, "h3_w", "6 in", "in", "H3 width")
    _add_param(params, "h3_h", "5 in", "in", "H3 height")
    _add_param(params, "h3_ft", "0.75 in", "in", "H3 front thick")
    _add_param(params, "h3_st", "0.5 in", "in", "H3 side thick")
    _add_param(params, "h3_x", "2 * ht_grid_x", "in", "H3 X offset")

    through_dovetail.define_params(params, prefix="dt3",
        angle="8 deg", tail_w="0.75 in", tail_count="5",
        joint_h_expr="h3_h", thick_expr="h3_ft")
    houndstooth_dovetail.add_params(params, prefix="dt3",
        ht_small_w="0.15 in",      # override default tail_w/7 (~0.107)
        ht_depth="0.35 in")        # override default tail_w*3/5 (=0.45)

    # Overrides should be literal
    assert abs(ev("dt3_ht_small_w") / 2.54 - 0.15) < 0.001
    assert abs(ev("dt3_ht_depth") / 2.54 - 0.35) < 0.001
    # Inset is derived: (tail_w - ht_small_w) / 2 = (0.75 - 0.15) / 2 = 0.30
    assert abs(ev("dt3_ht_inset") / 2.54 - 0.30) < 0.001, (
        f"H3: expected ht_inset=0.30, got {ev('dt3_ht_inset') / 2.54:.4f}")

    r3 = build_houndstooth_box(root, "H3", "through",
        "h3_l", "h3_w", "h3_h", "h3_ft", "h3_st",
        "h3_x", "0 in", "dt3", ev)
    assert r3["count"] == 2
    print("H3: PASS (ht_inset=0.30\" derived from small_w=0.15\")\n")

    # ================================================================
    # H4: Through-houndstooth + edge padding (pad > 0)
    # ================================================================
    print("=" * 50)
    print("H4: Through-houndstooth with pad=1/8\"")
    print("=" * 50)

    _add_param(params, "h4_l", "8 in", "in", "H4 length")
    _add_param(params, "h4_w", "6 in", "in", "H4 width")
    _add_param(params, "h4_h", "5 in", "in", "H4 height")
    _add_param(params, "h4_ft", "0.75 in", "in", "H4 front thick")
    _add_param(params, "h4_st", "0.5 in", "in", "H4 side thick")
    _add_param(params, "h4_y", "ht_grid_y", "in", "H4 Y offset")

    through_dovetail.define_params(params, prefix="dt4",
        angle="8 deg", tail_w="0.75 in", tail_count="5",
        joint_h_expr="h4_h", thick_expr="h4_ft",
        pad="0.125 in")  # NEW: padding combines with houndstooth
    houndstooth_dovetail.add_params(params, prefix="dt4")

    assert ev("dt4_pad") > 0
    # Edge pin = pad + half_pin; houndstooth corner z_base should use it
    edge_pin_v = (ev("dt4_pad") + ev("dt4_half_pin")) / 2.54
    assert edge_pin_v > ev("dt4_half_pin") / 2.54, (
        "H4: edge pin should be thicker than inner half_pin with pad > 0")

    r4 = build_houndstooth_box(root, "H4", "through",
        "h4_l", "h4_w", "h4_h", "h4_ft", "h4_st",
        "0 in", "h4_y", "dt4", ev)
    assert r4["count"] == 2
    print(f"H4: PASS (pad shifts houndstooth pattern by {ev('dt4_pad')/2.54:.4f}\")\n")

    # ================================================================
    # H5: Half-blind-houndstooth + edge padding
    # ================================================================
    print("=" * 50)
    print("H5: Half-blind-houndstooth with pad=1/16\"")
    print("=" * 50)

    _add_param(params, "h5_l", "8 in", "in", "H5 length")
    _add_param(params, "h5_w", "6 in", "in", "H5 width")
    _add_param(params, "h5_h", "5 in", "in", "H5 height")
    _add_param(params, "h5_ft", "0.75 in", "in", "H5 front thick")
    _add_param(params, "h5_st", "0.5 in", "in", "H5 side thick")
    _add_param(params, "h5_x", "ht_grid_x", "in", "H5 X offset")
    _add_param(params, "h5_y", "ht_grid_y", "in", "H5 Y offset")

    half_blind_dovetail.define_params(params, prefix="dt5",
        angle="8 deg", tail_w="0.75 in", tail_count="5",
        joint_h_expr="h5_h", pin_thick_expr="h5_ft", lap="0.25 in",
        pad="0.0625 in")
    houndstooth_dovetail.add_params(params, prefix="dt5")

    assert ev("dt5_pad") > 0

    r5 = build_houndstooth_box(root, "H5", "half_blind",
        "h5_l", "h5_w", "h5_h", "h5_ft", "h5_st",
        "h5_x", "h5_y", "dt5", ev, lap_expr="dt5_lap")
    assert r5["count"] == 2
    print(f"H5: PASS (half-blind + houndstooth + pad combine cleanly)\n")

    # ================================================================
    # H6: Through-houndstooth, cross-component (pin + tail in separate comps)
    # ================================================================
    print("=" * 50)
    print("H6: Through-houndstooth, cross-component")
    print("=" * 50)

    _add_param(params, "h6_h", "5 in", "in", "H6 height")
    _add_param(params, "h6_ft", "0.75 in", "in", "H6 front thick")
    _add_param(params, "h6_st", "0.5 in", "in", "H6 side thick")
    _add_param(params, "h6_x", "2 * ht_grid_x", "in", "H6 X offset")
    _add_param(params, "h6_y", "ht_grid_y", "in", "H6 Y offset")

    through_dovetail.define_params(params, prefix="dt6",
        angle="8 deg", tail_w="0.75 in", tail_count="5",
        joint_h_expr="h6_h", thick_expr="h6_ft")
    houndstooth_dovetail.add_params(params, prefix="dt6")

    # Front component (pin body)
    fo = sp.make_comp(root, "H6_Front")
    fc = fo.component
    fp = sp.off_plane(fc, fc.xZConstructionPlane, "h6_y", "H6_FrontPl")
    sk, pr = sp.sketch_rect_model(fc, fp,
        ("h6_x", "h6_y", "0 in"),
        {"x": "6 in", "z": "h6_h"}, "H6_Front_Sk", ev)
    front6 = sp.ext_new(fc, pr, "h6_ft", "H6_Front").bodies.item(0)
    front6.name = "H6_Front"

    # Left component (tail body) in a separate component
    lo = sp.make_comp(root, "H6_Left")
    lc = lo.component
    lp = sp.off_plane(lc, lc.yZConstructionPlane, "h6_x", "H6_LeftPl")
    sk, pr = sp.sketch_rect_model(lc, lp,
        ("h6_x", "h6_y + h6_ft", "0 in"),
        {"y": f"5 in - h6_ft", "z": "h6_h"}, "H6_Left_Sk", ev)
    left6 = sp.ext_new(lc, pr, "h6_st", "H6_Left").bodies.item(0)
    left6.name = "H6_Left"

    houndstooth_dovetail.corner(
        pin_body=front6, tail_body=left6, plane=lp,
        x_model=ev("h6_x"),
        y_wide=ev("h6_y"),
        y_narrow=ev("h6_y") + ev("h6_ft"),
        y_wide_expr="h6_y",
        thick_expr="h6_ft",
        dist_expr="h6_st",
        name="H6", prefix="dt6", ev=ev)

    total6 = fc.bRepBodies.count + lc.bRepBodies.count
    assert total6 == 2, f"H6: expected 2 across two comps, got {total6}"
    print("H6: PASS (cross-component corner)\n")

    # ================================================================
    # Summary
    # ================================================================
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)

    total = 0
    for occ in root.occurrences:
        c = occ.component
        n = c.bRepBodies.count
        names = [c.bRepBodies.item(i).name for i in range(n)]
        print(f"  {c.name}: {n} bodies -> {names}")
        total += n

    # H1, H2, H3, H4, H5 : 2 bodies each = 10
    # H6_Front, H6_Left  : 1 body each   = 2
    expected = 5 * 2 + 2
    status = "PASS" if total == expected else "FAIL"
    print(f"\n{status}: expected {expected} bodies, got {total}")

    for occ in root.occurrences:
        c = occ.component
        for sk in c.sketches:
            sk.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
