"""
Modern Platform Bed Frame (Queen)
=================================
60"W x 80"L x 12"H (platform), headboard 36"H from floor.
4 corner posts, side rails, headboard panel, slat system.

Coordinate system:
  X = width (60")  Y = length (80")  Z = height
"""
import adsk.core, adsk.fusion

from helpers import af

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    # ==============================================================
    #  PARAMETERS
    # ==============================================================
    for pname, expr, unit in [
        ("bed_w",       "60 in",    "in"),   # mattress width (Queen)
        ("bed_l",       "80 in",    "in"),   # mattress length
        ("rail_h",      "10 in",    "in"),
        ("rail_thick",  "1.5 in",   "in"),
        ("post_size",   "3 in",     "in"),
        ("headboard_h", "36 in",    "in"),   # from floor
        ("hb_thick",    "0.75 in",  "in"),
        ("slat_w",      "3 in",     "in"),
        ("slat_thick",  "0.75 in",  "in"),
        ("n_slats",     "13",       ""),
        ("ledger_h",    "1.5 in",   "in"),
        ("ledger_thick","0.75 in",  "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    for pname, expr, unit in [
        ("outer_w",    "bed_w + 2 * post_size",                     "in"),
        ("outer_l",    "bed_l + 2 * post_size",                     "in"),
        ("side_rail_l","bed_l",                                      "in"),
        ("end_rail_l", "bed_w",                                      "in"),
        ("slat_l",     "bed_w",                                      "in"),
        ("slat_sp",    "(bed_l - slat_w) / (n_slats - 1)",          "in"),
        ("mid_x",      "outer_w / 2",                                "in"),
        ("mid_y",      "outer_l / 2",                                "in"),
        ("ledger_z",   "rail_h - ledger_h - slat_thick",            "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    print(">>> Parameters done")

    # ==============================================================
    #  COMPONENTS
    # ==============================================================
    post_occ  = af.make_comp(root, "Posts")
    rail_occ  = af.make_comp(root, "Rails")
    hb_occ    = af.make_comp(root, "Headboard")
    slat_occ  = af.make_comp(root, "Slats")

    post_c  = post_occ.component
    rail_c  = rail_occ.component
    hb_c    = hb_occ.component
    slat_c  = slat_occ.component

    # ==============================================================
    #  1. POSTS — 4 corner posts
    # ==============================================================
    # Front-left post (footboard height — 12")
    params.add("footboard_h", VI("12 in"), "in", "")

    _, pr = af.sketch_rect_model(post_c, post_c.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "post_size", "y": "post_size"}, "PostFL_Sk", ev)
    fl_ext = af.ext_new(post_c, pr, "footboard_h", "PostFL")
    fl_ext.bodies.item(0).name = "Post_FL"

    p_xmid = af.off_plane(post_c, post_c.yZConstructionPlane, "mid_x", "PXMid")
    p_ymid = af.off_plane(post_c, post_c.xZConstructionPlane, "mid_y", "PYMid")

    af.mirror_body(post_c, fl_ext.bodies.item(0), p_xmid, "PostFR").bodies.item(0).name = "Post_FR"

    # Back posts are taller (headboard height — 36")
    _, pr = af.sketch_rect_model(post_c, post_c.xYConstructionPlane,
        ("0 in", "bed_l + post_size", "0 in"),
        {"x": "post_size", "y": "post_size"}, "PostBL_Sk", ev)
    bl_ext = af.ext_new(post_c, pr, "headboard_h", "PostBL")
    bl_ext.bodies.item(0).name = "Post_BL"

    af.mirror_body(post_c, bl_ext.bodies.item(0), p_xmid, "PostBR").bodies.item(0).name = "Post_BR"

    print(">>> Posts: 4 (front 12\", back 36\")")

    # ==============================================================
    #  2. RAILS — side rails + foot rail
    # ==============================================================
    # Left side rail (sketch on YZ plane — Y runs along bed length)
    _, pr = af.sketch_rect_model(rail_c, rail_c.yZConstructionPlane,
        ("0 in", "post_size", "0 in"),
        {"y": "side_rail_l", "z": "rail_h"}, "LeftRail_Sk", ev)
    lr_ext = af.ext_new(rail_c, pr, "rail_thick", "LeftRail")
    lr_ext.bodies.item(0).name = "Rail_Left"

    # Right side rail: mirror
    r_xmid = af.off_plane(rail_c, rail_c.yZConstructionPlane, "mid_x", "RXMid")
    af.mirror_feats(rail_c, [lr_ext], r_xmid, "RightRailMir").bodies.item(0).name = "Rail_Right"

    # Foot rail (between front posts)
    _, pr = af.sketch_rect_model(rail_c, rail_c.xZConstructionPlane,
        ("post_size", "0 in", "0 in"),
        {"x": "end_rail_l", "z": "rail_h"}, "FootRail_Sk", ev)
    af.ext_new(rail_c, pr, "rail_thick", "FootRail").bodies.item(0).name = "Rail_Foot"

    # Ledger strips on side rails (slat support — sketch on YZ)
    _, pr = af.sketch_rect_model(rail_c, rail_c.yZConstructionPlane,
        ("rail_thick", "post_size", "ledger_z"),
        {"y": "side_rail_l", "z": "ledger_h"}, "LedgerL_Sk", ev)
    ll_ext = af.ext_new(rail_c, pr, "ledger_thick", "LedgerLeft")
    ll_ext.bodies.item(0).name = "Ledger_Left"

    af.mirror_feats(rail_c, [ll_ext], r_xmid, "LedgerRightMir").bodies.item(0).name = "Ledger_Right"

    print(">>> Rails: 3 rails + 2 ledgers")

    # ==============================================================
    #  3. HEADBOARD — panel between back posts
    # ==============================================================
    _, pr = af.sketch_rect_model(hb_c, hb_c.xZConstructionPlane,
        ("post_size", "bed_l + post_size", "rail_h"),
        {"x": "end_rail_l", "z": "headboard_h - rail_h"}, "HB_Sk", ev)
    af.ext_new(hb_c, pr, "hb_thick", "HeadboardPanel").bodies.item(0).name = "Headboard"

    print(">>> Headboard: 1 body")

    # ==============================================================
    #  4. SLATS — template + pattern
    # ==============================================================
    slat_z_pl = af.off_plane(slat_c, slat_c.xYConstructionPlane,
                              "rail_h - slat_thick", "SlatZ_Pl")
    _, pr = af.sketch_rect_model(slat_c, slat_z_pl,
        ("post_size", "post_size", "rail_h - slat_thick"),
        {"x": "slat_l", "y": "slat_w"}, "Slat_Sk", ev)
    slat_ext = af.ext_new(slat_c, pr, "slat_thick", "Slat_1")
    slat_body = slat_ext.bodies.item(0)
    slat_body.name = "Slat_1"

    # Pattern slats along Y
    if int(ev("n_slats")) > 1:
        pat = af.body_pattern(slat_c, slat_body, slat_c.yConstructionAxis,
                               "n_slats", "slat_sp", "SlatPat")
        for i in range(pat.bodies.count):
            pat.bodies.item(i).name = f"Slat_{i+2}"

    print(">>> Slats: %d bodies" % int(ev("n_slats")))

    # ==============================================================
    #  5. CENTER SUPPORT BEAM (required for Queen+)
    #     Runs lengthwise under the slats at the midpoint
    # ==============================================================
    support_occ = af.make_comp(root, "Support")
    support_c = support_occ.component

    # Center beam: runs along Y (bed length) at mid_x, from floor to ledger top
    cb_pl = af.off_plane(support_c, support_c.yZConstructionPlane,
                          "mid_x - rail_thick / 2", "CB_Pl")
    _, pr = af.sketch_rect_model(support_c, cb_pl,
        ("mid_x - rail_thick / 2", "post_size", "0 in"),
        {"y": "bed_l", "z": "ledger_z + ledger_h"}, "CenterBeam_Sk", ev)
    af.ext_new(support_c, pr, "rail_thick", "CenterBeam").bodies.item(0).name = "CenterBeam"

    print(">>> Center support beam: 1 body")

    # ==============================================================
    #  EPILOGUE
    # ==============================================================
    for comp in [post_c, rail_c, hb_c, slat_c, support_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False

    for cn, c in [("Posts", post_c), ("Rails", rail_c),
                   ("Headboard", hb_c), ("Slats", slat_c),
                   ("Support", support_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{cn}: {len(names)} bodies -> {names}")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
