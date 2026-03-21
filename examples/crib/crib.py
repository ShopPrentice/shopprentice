"""
Modern Crib
===========
52"L x 28"W interior, 34"H rail height.
4 corner posts, side rails with spindles, head/foot panels.

Coordinate system:
  X = width (28" interior)  Y = length (52" interior)  Z = height (34")
"""
import adsk.core, adsk.fusion

from helpers import af


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    for pname, expr, unit in [
        ("interior_l",  "52 in",    "in"),
        ("interior_w",  "28 in",    "in"),
        ("rail_h",      "34 in",    "in"),
        ("post_size",   "2.5 in",   "in"),
        ("rail_w",      "3 in",     "in"),
        ("rail_thick",  "0.75 in",  "in"),
        ("spindle_dia", "0.75 in",  "in"),
        ("spindle_sp",  "2.25 in",  "in"),  # center-to-center (max 2.375" gap)
        ("mattress_h",  "6 in",     "in"),  # mattress support height
        ("support_thick","0.75 in", "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    for pname, expr, unit in [
        ("outer_l",     "interior_l + 2 * post_size",               "in"),
        ("outer_w",     "interior_w + 2 * post_size",               "in"),
        ("spindle_h",   "rail_h - 2 * rail_w",                      "in"),
        ("n_long_spindles", "floor(interior_l / spindle_sp)",        ""),
        ("n_short_spindles","floor(interior_w / spindle_sp)",        ""),
        ("long_sp_actual",  "interior_l / (n_long_spindles + 1)",   "in"),
        ("short_sp_actual", "interior_w / (n_short_spindles + 1)",  "in"),
        ("mid_x",       "outer_w / 2",                               "in"),
        ("mid_y",       "outer_l / 2",                               "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    print(">>> Parameters done")

    post_occ    = af.make_comp(root, "Posts")
    rail_occ    = af.make_comp(root, "Rails")
    spindle_occ = af.make_comp(root, "Spindles")
    support_occ = af.make_comp(root, "Support")

    post_c    = post_occ.component
    rail_c    = rail_occ.component
    spindle_c = spindle_occ.component
    support_c = support_occ.component

    # ==== POSTS ====
    _, pr = af.sketch_rect_model(post_c, post_c.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "post_size", "y": "post_size"}, "PostFL_Sk", ev)
    fl_ext = af.ext_new(post_c, pr, "rail_h", "PostFL")
    fl_ext.bodies.item(0).name = "Post_FL"

    p_xmid = af.off_plane(post_c, post_c.yZConstructionPlane, "mid_x", "PXMid")
    p_ymid = af.off_plane(post_c, post_c.xZConstructionPlane, "mid_y", "PYMid")
    af.mirror_body(post_c, fl_ext.bodies.item(0), p_xmid, "PostFR").bodies.item(0).name = "Post_FR"
    pbl = af.mirror_body(post_c, fl_ext.bodies.item(0), p_ymid, "PostBL").bodies.item(0)
    pbl.name = "Post_BL"
    af.mirror_body(post_c, pbl, p_xmid, "PostBR").bodies.item(0).name = "Post_BR"
    print(">>> Posts: 4")

    # ==== RAILS (top and bottom on all 4 sides) ====
    # Front bottom rail
    _, pr = af.sketch_rect_model(rail_c, rail_c.xZConstructionPlane,
        ("post_size", "0 in", "0 in"),
        {"x": "interior_w", "z": "rail_w"}, "FrontBotRail_Sk", ev)
    fbr_ext = af.ext_new(rail_c, pr, "rail_thick", "FrontBotRail")
    fbr_ext.bodies.item(0).name = "Rail_FrontBot"

    # Front top rail
    _, pr = af.sketch_rect_model(rail_c, rail_c.xZConstructionPlane,
        ("post_size", "0 in", "rail_h - rail_w"),
        {"x": "interior_w", "z": "rail_w"}, "FrontTopRail_Sk", ev)
    ftr_ext = af.ext_new(rail_c, pr, "rail_thick", "FrontTopRail")
    ftr_ext.bodies.item(0).name = "Rail_FrontTop"

    # Mirror front rails to back
    r_ymid = af.off_plane(rail_c, rail_c.xZConstructionPlane, "mid_y", "RYMid")
    af.mirror_feats(rail_c, [fbr_ext], r_ymid, "BackBotRailMir").bodies.item(0).name = "Rail_BackBot"
    af.mirror_feats(rail_c, [ftr_ext], r_ymid, "BackTopRailMir").bodies.item(0).name = "Rail_BackTop"

    # Left side rails
    _, pr = af.sketch_rect_model(rail_c, rail_c.yZConstructionPlane,
        ("0 in", "post_size", "0 in"),
        {"y": "interior_l", "z": "rail_w"}, "LeftBotRail_Sk", ev)
    lbr_ext = af.ext_new(rail_c, pr, "rail_thick", "LeftBotRail")
    lbr_ext.bodies.item(0).name = "Rail_LeftBot"

    _, pr = af.sketch_rect_model(rail_c, rail_c.yZConstructionPlane,
        ("0 in", "post_size", "rail_h - rail_w"),
        {"y": "interior_l", "z": "rail_w"}, "LeftTopRail_Sk", ev)
    ltr_ext = af.ext_new(rail_c, pr, "rail_thick", "LeftTopRail")
    ltr_ext.bodies.item(0).name = "Rail_LeftTop"

    r_xmid = af.off_plane(rail_c, rail_c.yZConstructionPlane, "mid_x", "RXMid")
    af.mirror_feats(rail_c, [lbr_ext], r_xmid, "RightBotRailMir").bodies.item(0).name = "Rail_RightBot"
    af.mirror_feats(rail_c, [ltr_ext], r_xmid, "RightTopRailMir").bodies.item(0).name = "Rail_RightTop"
    print(">>> Rails: 8")

    # ==== SPINDLES (rectangular approximation) ====
    # Front spindle template
    _, pr = af.sketch_rect_model(spindle_c, spindle_c.xZConstructionPlane,
        ("post_size + long_sp_actual - spindle_dia / 2", "0 in", "rail_w"),
        {"x": "spindle_dia", "z": "spindle_h"}, "FSpindle_Sk", ev)
    fs_ext = af.ext_new(spindle_c, pr, "spindle_dia", "FSpindle_1")
    fs_ext.bodies.item(0).name = "Spindle_F1"

    # Pattern front spindles along X (note: using short_sp for front side)
    n_short = int(ev("n_short_spindles"))
    if n_short > 1:
        af.body_pattern(spindle_c, fs_ext.bodies.item(0),
                         spindle_c.xConstructionAxis,
                         "n_short_spindles", "short_sp_actual", "FSpindlePat")

    # Left side spindle template
    _, pr = af.sketch_rect_model(spindle_c, spindle_c.yZConstructionPlane,
        ("0 in", "post_size + long_sp_actual - spindle_dia / 2", "rail_w"),
        {"y": "spindle_dia", "z": "spindle_h"}, "LSpindle_Sk", ev)
    ls_ext = af.ext_new(spindle_c, pr, "spindle_dia", "LSpindle_1")
    ls_ext.bodies.item(0).name = "Spindle_L1"

    n_long = int(ev("n_long_spindles"))
    if n_long > 1:
        af.body_pattern(spindle_c, ls_ext.bodies.item(0),
                         spindle_c.yConstructionAxis,
                         "n_long_spindles", "long_sp_actual", "LSpindlePat")

    # Mirror front spindles to back, left to right
    s_ymid = af.off_plane(spindle_c, spindle_c.xZConstructionPlane, "mid_y", "SYMid")
    s_xmid = af.off_plane(spindle_c, spindle_c.yZConstructionPlane, "mid_x", "SXMid")

    # Mirror all front spindle bodies to back
    front_spindles = [spindle_c.bRepBodies.item(i) for i in range(spindle_c.bRepBodies.count)
                      if spindle_c.bRepBodies.item(i).name.startswith("Spindle_F")]
    if front_spindles:
        af.mirror_bodies(spindle_c, front_spindles, s_ymid, "BackSpindleMir")

    left_spindles = [spindle_c.bRepBodies.item(i) for i in range(spindle_c.bRepBodies.count)
                     if spindle_c.bRepBodies.item(i).name.startswith("Spindle_L")]
    if left_spindles:
        af.mirror_bodies(spindle_c, left_spindles, s_xmid, "RightSpindleMir")

    print(">>> Spindles done")

    # ==== MATTRESS SUPPORT ====
    sup_pl = af.off_plane(support_c, support_c.xYConstructionPlane, "mattress_h", "SupPl")
    _, pr = af.sketch_rect_model(support_c, sup_pl,
        ("post_size", "post_size", "mattress_h"),
        {"x": "interior_w", "y": "interior_l"}, "Support_Sk", ev)
    af.ext_new(support_c, pr, "support_thick", "SupportBoard").bodies.item(0).name = "MattressSupport"
    print(">>> Mattress support: 1")

    # ==== EPILOGUE ====
    for comp in [post_c, rail_c, spindle_c, support_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False

    for cn, c in [("Posts", post_c), ("Rails", rail_c),
                   ("Spindles", spindle_c), ("Support", support_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{cn}: {len(names)} bodies")

    af.apply_appearance("maple")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
