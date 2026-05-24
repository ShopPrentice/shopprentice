"""
Modern Crib
===========
52"L x 28"W interior, 34"H rail height.
4 corner posts, top+bottom rails on all 4 sides with spindles,
slatted mattress support with ledger strips.
All joints mechanically connected: rails with dominos, spindles with dowels.

Safety (CPSC): spindle gap ≤ 2.375", post tops flush with rails.

Coordinate system:
  X = width (33" outer)  Y = length (57" outer)  Z = height (34")
"""
import adsk.core, adsk.fusion

from helpers import sp
from woodworking.templates import domino

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation


def find_body(name, comp=None):
    c = comp or _root_comp
    for i in range(c.bRepBodies.count):
        if c.bRepBodies.item(i).name == name:
            return c.bRepBodies.item(i)
    for j in range(c.occurrences.count):
        r = find_body(name, c.occurrences.item(j).component)
        if r:
            return r
    return None


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    global _root_comp
    _root_comp = root
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    # === USER PARAMETERS ===
    for pname, expr, unit in [
        ("interior_l",    "52 in",    "in"),
        ("interior_w",    "28 in",    "in"),
        ("rail_h",        "34 in",    "in"),
        ("post_size",     "2.5 in",   "in"),
        ("rail_w",        "3 in",     "in"),
        ("rail_thick",    "1.5 in",   "in"),   # thick enough for spindle mortises
        ("spindle_dia",   "0.75 in",  "in"),
        ("spindle_tenon", "0.5 in",   "in"),  # how deep spindle inserts into rail
        ("spindle_sp",    "2.25 in",  "in"),   # center-to-center (gap = sp - dia ≤ 2.375")
        # Mattress support
        ("mattress_h",    "6 in",     "in"),   # lowest position
        ("support_thick", "0.75 in",  "in"),
        ("slat_w",        "2.5 in",   "in"),
        ("n_slats",       "8",        ""),
        ("sup_rail_w",    "1.5 in",   "in"),
        ("sup_rail_h",    "1.5 in",   "in"),
        # Dominos (6mm for rails)
        ("dm_t",          "6 mm",     "in"),
        ("dm_w",          "20 mm",    "in"),
        ("dm_d",          "15 mm",    "in"),
        # (Spindle mortises created by bulk CUT — no separate dowel params needed)
        # Details
        ("post_chamfer",  "0.0625 in","in"),   # 1/16" — post tops, safety
        ("edge_chamfer",  "0.03125 in","in"),  # 1/32" — general edge break
    ]:
        params.add(pname, VI(expr), unit, "")

    # === DERIVED PARAMETERS ===
    for pname, expr, unit in [
        ("outer_w",       "interior_w + 2 * post_size",                "in"),
        ("outer_l",       "interior_l + 2 * post_size",                "in"),
        ("mid_x",         "outer_w / 2",                                "in"),
        ("mid_y",         "outer_l / 2",                                "in"),
        # Spindle counts + actual spacing
        ("spindle_h",     "rail_h - 2 * rail_w + 2 * spindle_tenon",    "in"),
        ("spindle_z",     "rail_w - spindle_tenon",                    "in"),
        ("n_short_sp",    "floor(interior_w / spindle_sp)",             ""),
        ("n_long_sp",     "floor(interior_l / spindle_sp)",             ""),
        ("short_sp_act",  "interior_w / (n_short_sp + 1)",             "in"),
        ("long_sp_act",   "interior_l / (n_long_sp + 1)",              "in"),
        # Support rail positioning — centered on post inner X face for mortise overlap
        ("sup_rail_inset","post_size - sup_rail_w / 2",                "in"),
        # Slat support — slats span between support rail inner faces, flush at top
        ("slat_l",        "outer_w - 2 * sup_rail_inset - 2 * sup_rail_w", "in"),
        ("slat_sp",       "(interior_l - slat_w) / (n_slats - 1)",    "in"),
        ("slat_z",        "mattress_h - 2 * support_thick",            "in"),
        # Rail domino Z positions (2 per rail end, evenly in rail height)
        ("dm_z1",         "rail_w / 3",                                "in"),
        ("dm_sp",         "rail_w / 3",                                "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    print(">>> Parameters done")

    # === COMPONENTS ===
    post_occ    = sp.make_comp(root, "Posts")
    rail_occ    = sp.make_comp(root, "Rails")
    spindle_occ = sp.make_comp(root, "Spindles")
    support_occ = sp.make_comp(root, "Support")

    post_c    = post_occ.component
    rail_c    = rail_occ.component
    spindle_c = spindle_occ.component
    support_c = support_occ.component

    # ================================================================
    #  1. POSTS — 4 corners, all same height (flush with top rails)
    # ================================================================
    _, pr = sp.sketch_rect_model(post_c, post_c.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "post_size", "y": "post_size"}, "PostFL_Sk", ev)
    fl_ext = sp.ext_new(post_c, pr, "rail_h", "PostFL")
    post_fl = fl_ext.bodies.item(0); post_fl.name = "Post_FL"

    p_xmid = sp.off_plane(post_c, post_c.yZConstructionPlane, "mid_x", "PXMid")
    p_ymid = sp.off_plane(post_c, post_c.xZConstructionPlane, "mid_y", "PYMid")

    # Body-relative reference: Post_FR, Post_BL, Post_BR depend on Post_FL
    ref_post_fl = find_body("Post_FL")
    ref_post_fl_bb = ref_post_fl.boundingBox

    post_fr = sp.mirror_body(post_c, post_fl, p_xmid, "PostFR").bodies.item(0)
    post_fr.name = "Post_FR"
    post_bl = sp.mirror_body(post_c, post_fl, p_ymid, "PostBL").bodies.item(0)
    post_bl.name = "Post_BL"
    post_br = sp.mirror_body(post_c, post_bl, p_xmid, "PostBR").bodies.item(0)
    post_br.name = "Post_BR"

    print(">>> Posts: 4")

    # ================================================================
    #  2. RAILS — top + bottom on all 4 sides, centered on posts
    # ================================================================
    # Body-relative references: Rails depend on Post_FL
    ref_post_fl2 = find_body("Post_FL")
    ref_post_fl2_bb = ref_post_fl2.boundingBox

    # Front bottom rail (short side, X direction)
    fbr_pl = sp.off_plane(rail_c, rail_c.xZConstructionPlane,
                           "post_size / 2 - rail_thick / 2", "FBR_Pl")
    _, pr = sp.sketch_rect_model(rail_c, fbr_pl,
        ("post_size", "post_size / 2 - rail_thick / 2", "0 in"),
        {"x": "interior_w", "z": "rail_w"}, "FrontBotRail_Sk", ev)
    fbr_ext = sp.ext_new(rail_c, pr, "rail_thick", "FrontBotRail")
    fbr = fbr_ext.bodies.item(0); fbr.name = "Rail_FrontBot"

    # Body-relative reference: Rail_FrontTop depends on Rail_FrontBot
    ref_fbr = find_body("Rail_FrontBot")
    ref_fbr_bb = ref_fbr.boundingBox

    # Front top rail
    _, pr = sp.sketch_rect_model(rail_c, fbr_pl,
        ("post_size", "post_size / 2 - rail_thick / 2", "rail_h - rail_w"),
        {"x": "interior_w", "z": "rail_w"}, "FrontTopRail_Sk", ev)
    ftr_ext = sp.ext_new(rail_c, pr, "rail_thick", "FrontTopRail")
    ftr = ftr_ext.bodies.item(0); ftr.name = "Rail_FrontTop"

    # Body-relative reference: Rail_BackBot depends on Rail_FrontBot
    ref_fbr2 = find_body("Rail_FrontBot")
    ref_fbr2_bb = ref_fbr2.boundingBox

    # Mirror front rails to back
    r_ymid = sp.off_plane(rail_c, rail_c.xZConstructionPlane, "mid_y", "RYMid")
    sp.mirror_feats(rail_c, [fbr_ext], r_ymid, "BackBotRailMir").bodies.item(0).name = "Rail_BackBot"

    # Body-relative reference: Rail_BackTop depends on Rail_BackBot
    ref_bbr = find_body("Rail_BackBot")
    ref_bbr_bb = ref_bbr.boundingBox

    sp.mirror_feats(rail_c, [ftr_ext], r_ymid, "BackTopRailMir").bodies.item(0).name = "Rail_BackTop"

    # Left bottom rail (long side, Y direction)
    lbr_pl = sp.off_plane(rail_c, rail_c.yZConstructionPlane,
                           "post_size / 2 - rail_thick / 2", "LBR_Pl")
    _, pr = sp.sketch_rect_model(rail_c, lbr_pl,
        ("post_size / 2 - rail_thick / 2", "post_size", "0 in"),
        {"y": "interior_l", "z": "rail_w"}, "LeftBotRail_Sk", ev)
    lbr_ext = sp.ext_new(rail_c, pr, "rail_thick", "LeftBotRail")
    lbr_ext.bodies.item(0).name = "Rail_LeftBot"

    # Body-relative reference: Rail_LeftTop depends on Rail_LeftBot
    ref_lbr = find_body("Rail_LeftBot")
    ref_lbr_bb = ref_lbr.boundingBox

    _, pr = sp.sketch_rect_model(rail_c, lbr_pl,
        ("post_size / 2 - rail_thick / 2", "post_size", "rail_h - rail_w"),
        {"y": "interior_l", "z": "rail_w"}, "LeftTopRail_Sk", ev)
    ltr_ext = sp.ext_new(rail_c, pr, "rail_thick", "LeftTopRail")
    ltr_ext.bodies.item(0).name = "Rail_LeftTop"

    # Body-relative reference: Rail_RightBot depends on Rail_LeftBot
    ref_lbr2 = find_body("Rail_LeftBot")
    ref_lbr2_bb = ref_lbr2.boundingBox

    r_xmid = sp.off_plane(rail_c, rail_c.yZConstructionPlane, "mid_x", "RXMid")
    sp.mirror_feats(rail_c, [lbr_ext], r_xmid, "RightBotRailMir").bodies.item(0).name = "Rail_RightBot"

    # Body-relative reference: Rail_RightTop depends on Rail_RightBot
    ref_rbr = find_body("Rail_RightBot")
    ref_rbr_bb = ref_rbr.boundingBox

    sp.mirror_feats(rail_c, [ltr_ext], r_xmid, "RightTopRailMir").bodies.item(0).name = "Rail_RightTop"

    print(">>> Rails: 8")

    # ================================================================
    #  3. SPINDLES — cylindrical, between top and bottom rails
    # ================================================================
    # Body-relative references: Spindle_F depends on Rail_FrontBot, Spindle_L depends on Rail_LeftBot
    ref_fbr3 = find_body("Rail_FrontBot")
    ref_fbr3_bb = ref_fbr3.boundingBox
    ref_lbr3 = find_body("Rail_LeftBot")
    ref_lbr3_bb = ref_lbr3.boundingBox
    P3 = adsk.core.Point3D

    # Front spindle: circle on XY offset at spindle_z, extrude vertically by spindle_h
    # Spindle inserts spindle_tenon deep into each rail (blind, not through)
    sp_z_pl = sp.off_plane(spindle_c, spindle_c.xYConstructionPlane, "spindle_z", "SpZ_Pl")
    sk_fs2 = spindle_c.sketches.add(sp_z_pl)
    sk_fs2.name = "FSpindle_Sk"
    first_x_cm = ev("post_size") + ev("short_sp_act")
    center_y_cm = ev("post_size") / 2
    sk_fs2.sketchCurves.sketchCircles.addByCenterRadius(
        P3.create(first_x_cm, center_y_cm, 0), ev("spindle_dia") / 2)
    fs_prof2 = sk_fs2.profiles.item(0)
    fs_ext2 = sp.ext_new(spindle_c, fs_prof2, "spindle_h", "FSpindle_1")
    fs_body2 = fs_ext2.bodies.item(0); fs_body2.name = "Spindle_F1"

    # Pattern front spindles along X
    n_short = int(ev("n_short_sp"))
    if n_short > 1:
        sp.body_pattern(spindle_c, fs_body2, spindle_c.xConstructionAxis,
                         "n_short_sp", "short_sp_act", "FSpindlePat")

    # Left spindle template (long side)
    sk_ls = spindle_c.sketches.add(sp_z_pl)
    sk_ls.name = "LSpindle_Sk"
    center_x_cm = ev("post_size") / 2
    first_y_cm = ev("post_size") + ev("long_sp_act")
    sk_ls.sketchCurves.sketchCircles.addByCenterRadius(
        P3.create(center_x_cm, first_y_cm, 0), ev("spindle_dia") / 2)
    ls_prof = sk_ls.profiles.item(0)
    ls_ext = sp.ext_new(spindle_c, ls_prof, "spindle_h", "LSpindle_1")
    ls_body = ls_ext.bodies.item(0); ls_body.name = "Spindle_L1"

    n_long = int(ev("n_long_sp"))
    if n_long > 1:
        sp.body_pattern(spindle_c, ls_body, spindle_c.yConstructionAxis,
                         "n_long_sp", "long_sp_act", "LSpindlePat")

    # Mirror front spindles to back, left to right
    s_ymid = sp.off_plane(spindle_c, spindle_c.xZConstructionPlane, "mid_y", "SYMid")
    s_xmid = sp.off_plane(spindle_c, spindle_c.yZConstructionPlane, "mid_x", "SXMid")

    front_spindles = [spindle_c.bRepBodies.item(i) for i in range(spindle_c.bRepBodies.count)
                      if spindle_c.bRepBodies.item(i).name.startswith("Spindle_F")]
    if front_spindles:
        sp.mirror_bodies(spindle_c, front_spindles, s_ymid, "BackSpindleMir")

    left_spindles = [spindle_c.bRepBodies.item(i) for i in range(spindle_c.bRepBodies.count)
                     if spindle_c.bRepBodies.item(i).name.startswith("Spindle_L")]
    if left_spindles:
        sp.mirror_bodies(spindle_c, left_spindles, s_xmid, "RightSpindleMir")

    print(f">>> Spindles: {spindle_c.bRepBodies.count}")

    # ================================================================
    #  4. MATTRESS SUPPORT — 2 support rails + slats
    # ================================================================
    # Body-relative reference: SupRail_Left depends on Post_FL
    ref_post_fl3 = find_body("Post_FL")
    ref_post_fl3_bb = ref_post_fl3.boundingBox
    # Support rails run lengthwise (Y), centered on post inner X face.
    # Each end extends into the post (blind mortise — CUT rail into post).
    # Slats span widthwise (X) between the two support rails, tops flush.

    # Left support rail — Y extends into both front and back posts
    sup_lpl = sp.off_plane(support_c, support_c.yZConstructionPlane,
                            "sup_rail_inset", "SupL_Pl")
    _, pr = sp.sketch_rect_model(support_c, sup_lpl,
        ("sup_rail_inset", "post_size / 2", "mattress_h - support_thick - sup_rail_h"),
        {"y": "outer_l - post_size", "z": "sup_rail_h"}, "SupRailL_Sk", ev)
    srl_ext = sp.ext_new(support_c, pr, "sup_rail_w", "SupRailLeft")
    sup_rail_l = srl_ext.bodies.item(0); sup_rail_l.name = "SupRail_Left"

    # Body-relative reference: SupRail_Right depends on SupRail_Left
    ref_sup_rail_l = find_body("SupRail_Left")
    ref_sup_rail_l_bb = ref_sup_rail_l.boundingBox

    # Right support rail (mirror)
    sup_xmid = sp.off_plane(support_c, support_c.yZConstructionPlane, "mid_x", "SupXMid")
    sp.mirror_feats(support_c, [srl_ext], sup_xmid, "SupRailRMir").bodies.item(0).name = "SupRail_Right"

    # Body-relative reference: Slat_1 depends on SupRail_Left
    ref_sup_rail_l2 = find_body("SupRail_Left")
    ref_sup_rail_l2_bb = ref_sup_rail_l2.boundingBox

    # Slats span between support rail inner faces, tops flush with rail tops
    slat_z_pl = sp.off_plane(support_c, support_c.xYConstructionPlane,
                              "slat_z", "SlatZ_Pl")
    _, pr = sp.sketch_rect_model(support_c, slat_z_pl,
        ("sup_rail_inset + sup_rail_w", "post_size", "slat_z"),
        {"x": "slat_l", "y": "slat_w"}, "Slat_Sk", ev)
    slat_ext = sp.ext_new(support_c, pr, "support_thick", "Slat_1")
    slat_body = slat_ext.bodies.item(0); slat_body.name = "Slat_1"

    if int(ev("n_slats")) > 1:
        sp.body_pattern(support_c, slat_body, support_c.yConstructionAxis,
                         "n_slats", "slat_sp", "SlatPat")

    # Assembly proxies for cross-component operations
    srl_p = sup_rail_l.createForAssemblyContext(support_occ)
    srr_body = None
    for i in range(support_c.bRepBodies.count):
        if support_c.bRepBodies.item(i).name == "SupRail_Right":
            srr_body = support_c.bRepBodies.item(i)
            break
    srr_p = srr_body.createForAssemblyContext(support_occ) if srr_body else None

    print(f">>> Support: 2 rails + {int(ev('n_slats'))} slats")

    # ================================================================
    #  5. CROSS-COMPONENT: Dominos (rails→posts) + Dowels (spindles→rails)
    # ================================================================
    params.add("dm_count", VI("2"), "", "")

    fl_p = post_fl.createForAssemblyContext(post_occ)
    fr_p = post_fr.createForAssemblyContext(post_occ)
    bl_p = post_bl.createForAssemblyContext(post_occ)
    br_p = post_br.createForAssemblyContext(post_occ)

    # Get native rail bodies in rail_c (for domino body_a — owning component)
    def get_rail_body(name):
        for i in range(rail_c.bRepBodies.count):
            b = rail_c.bRepBodies.item(i)
            if b.name == name:
                return b
        return None

    # Get rail bodies as proxies (for cross-component CUT targets)
    def get_rail_proxy(name):
        for i in range(rail_c.bRepBodies.count):
            b = rail_c.bRepBodies.item(i)
            if b.name == name:
                return b.createForAssemblyContext(rail_occ)
        return None

    fbr_b = get_rail_body("Rail_FrontBot")
    ftr_b = find_body("Rail_FrontTop"); ftr_bb = ftr_b.boundingBox
    bbr_b = get_rail_body("Rail_BackBot")
    btr_b = find_body("Rail_BackTop"); btr_bb = btr_b.boundingBox
    lbr_b = get_rail_body("Rail_LeftBot")
    ltr_b = find_body("Rail_LeftTop"); ltr_bb = ltr_b.boundingBox
    rbr_b = get_rail_body("Rail_RightBot")
    rtr_b = find_body("Rail_RightTop"); rtr_bb = rtr_b.boundingBox

    fbr_p = get_rail_proxy("Rail_FrontBot")
    ftr_p = get_rail_proxy("Rail_FrontTop")
    bbr_p = get_rail_proxy("Rail_BackBot")
    btr_p = get_rail_proxy("Rail_BackTop")
    lbr_p = get_rail_proxy("Rail_LeftBot")
    ltr_p = get_rail_proxy("Rail_LeftTop")
    rbr_p = get_rail_proxy("Rail_RightBot")
    rtr_p = get_rail_proxy("Rail_RightTop")

    # Domino planes at post inner faces (inside rail component)
    dm_xl = sp.off_plane(rail_c, rail_c.yZConstructionPlane, "post_size", "DM_XL")
    dm_xr = sp.off_plane(rail_c, rail_c.yZConstructionPlane, "outer_w - post_size", "DM_XR")
    dm_yf = sp.off_plane(rail_c, rail_c.xZConstructionPlane, "post_size", "DM_YF")
    dm_yb = sp.off_plane(rail_c, rail_c.xZConstructionPlane, "outer_l - post_size", "DM_YB")

    # --- Front bottom rail → FL, FR (2 dominos per end) ---
    domino.grid(rail_c, dm_xl,
        ("post_size", "post_size / 2", "dm_z1"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        fbr_b, fl_p, "DM_FBR_L", ev)
    domino.grid(rail_c, dm_xr,
        ("outer_w - post_size", "post_size / 2", "dm_z1"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        fbr_b, fr_p, "DM_FBR_R", ev)

    # --- Front top rail → FL, FR ---
    domino.grid(rail_c, dm_xl,
        ("post_size", "post_size / 2", "rail_h - rail_w + dm_z1"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        ftr_b, fl_p, "DM_FTR_L", ev)
    domino.grid(rail_c, dm_xr,
        ("outer_w - post_size", "post_size / 2", "rail_h - rail_w + dm_z1"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        ftr_b, fr_p, "DM_FTR_R", ev)

    # --- Back rails (mirror positions) ---
    domino.grid(rail_c, dm_xl,
        ("post_size", "outer_l - post_size / 2", "dm_z1"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        bbr_b, bl_p, "DM_BBR_L", ev)
    domino.grid(rail_c, dm_xr,
        ("outer_w - post_size", "outer_l - post_size / 2", "dm_z1"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        bbr_b, br_p, "DM_BBR_R", ev)
    domino.grid(rail_c, dm_xl,
        ("post_size", "outer_l - post_size / 2", "rail_h - rail_w + dm_z1"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        btr_b, bl_p, "DM_BTR_L", ev)
    domino.grid(rail_c, dm_xr,
        ("outer_w - post_size", "outer_l - post_size / 2", "rail_h - rail_w + dm_z1"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        btr_b, br_p, "DM_BTR_R", ev)

    # --- Left side rails → FL, BL ---
    domino.grid(rail_c, dm_yf,
        ("post_size / 2", "post_size", "dm_z1"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        lbr_b, fl_p, "DM_LBR_F", ev)
    domino.grid(rail_c, dm_yb,
        ("post_size / 2", "outer_l - post_size", "dm_z1"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        lbr_b, bl_p, "DM_LBR_B", ev)
    domino.grid(rail_c, dm_yf,
        ("post_size / 2", "post_size", "rail_h - rail_w + dm_z1"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        ltr_b, fl_p, "DM_LTR_F", ev)
    domino.grid(rail_c, dm_yb,
        ("post_size / 2", "outer_l - post_size", "rail_h - rail_w + dm_z1"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        ltr_b, bl_p, "DM_LTR_B", ev)

    # --- Right side rails → FR, BR ---
    domino.grid(rail_c, dm_yf,
        ("outer_w - post_size / 2", "post_size", "dm_z1"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        rbr_b, fr_p, "DM_RBR_F", ev)
    domino.grid(rail_c, dm_yb,
        ("outer_w - post_size / 2", "outer_l - post_size", "dm_z1"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        rbr_b, br_p, "DM_RBR_B", ev)
    domino.grid(rail_c, dm_yf,
        ("outer_w - post_size / 2", "post_size", "rail_h - rail_w + dm_z1"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        rtr_b, fr_p, "DM_RTR_F", ev)
    domino.grid(rail_c, dm_yb,
        ("outer_w - post_size / 2", "outer_l - post_size", "rail_h - rail_w + dm_z1"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        rtr_b, br_p, "DM_RTR_B", ev)

    print(">>> Dominos: 16 rail-to-post joints (32 voids)")

    # --- Spindle mortises: bulk CUT spindles into rails ---
    # Spindles span full height (Z=0 to rail_h) and overlap with both
    # top and bottom rails. CUT the spindle bodies into the rails —
    # the cylindrical shape creates perfect round mortises. 8 bulk CUTs
    # instead of 140 individual dowels.

    # Collect spindle proxies by side
    def get_spindle_proxies(prefix):
        proxies = []
        for i in range(spindle_c.bRepBodies.count):
            b = spindle_c.bRepBodies.item(i)
            if b.name.startswith(prefix):
                proxies.append(b.createForAssemblyContext(spindle_occ))
        return proxies

    front_sp = get_spindle_proxies("Spindle_F")
    # Back spindles are mirrored — their names start with "Spindle_F" too
    # but they're at different Y positions. Use bounding box to separate.
    all_f_named = [spindle_c.bRepBodies.item(i) for i in range(spindle_c.bRepBodies.count)
                   if spindle_c.bRepBodies.item(i).name.startswith("Spindle_F")]
    mid_y_cm = ev("mid_y")
    front_bodies = [b for b in all_f_named
                    if (b.boundingBox.minPoint.y + b.boundingBox.maxPoint.y) / 2 < mid_y_cm]
    back_bodies_f = [b for b in all_f_named
                     if (b.boundingBox.minPoint.y + b.boundingBox.maxPoint.y) / 2 > mid_y_cm]
    front_sp = [b.createForAssemblyContext(spindle_occ) for b in front_bodies]
    back_sp = [b.createForAssemblyContext(spindle_occ) for b in back_bodies_f]

    all_l_named = [spindle_c.bRepBodies.item(i) for i in range(spindle_c.bRepBodies.count)
                   if spindle_c.bRepBodies.item(i).name.startswith("Spindle_L")]
    mid_x_cm = ev("mid_x")
    left_bodies = [b for b in all_l_named
                   if (b.boundingBox.minPoint.x + b.boundingBox.maxPoint.x) / 2 < mid_x_cm]
    right_bodies = [b for b in all_l_named
                    if (b.boundingBox.minPoint.x + b.boundingBox.maxPoint.x) / 2 > mid_x_cm]
    left_sp = [b.createForAssemblyContext(spindle_occ) for b in left_bodies]
    right_sp = [b.createForAssemblyContext(spindle_occ) for b in right_bodies]

    # 8 bulk CUTs (one per rail)
    if front_sp:
        sp.combine(fbr_p, front_sp, CUT, True, "SpindleCut_FBot")
        sp.combine(ftr_p, front_sp, CUT, True, "SpindleCut_FTop")
    if back_sp:
        sp.combine(bbr_p, back_sp, CUT, True, "SpindleCut_BBot")
        sp.combine(btr_p, back_sp, CUT, True, "SpindleCut_BTop")
    if left_sp:
        sp.combine(lbr_p, left_sp, CUT, True, "SpindleCut_LBot")
        sp.combine(ltr_p, left_sp, CUT, True, "SpindleCut_LTop")
    if right_sp:
        sp.combine(rbr_p, right_sp, CUT, True, "SpindleCut_RBot")
        sp.combine(rtr_p, right_sp, CUT, True, "SpindleCut_RTop")

    print(">>> Spindle mortises: 8 bulk CUTs into rails")

    # --- Support rails → posts (blind mortise — CUT rail ends into posts) ---
    # Support rail ends extend into the posts. CUT creates mortise pockets.
    post_fl_p = post_fl.createForAssemblyContext(post_occ)
    post_fr_p = post_fr.createForAssemblyContext(post_occ)
    post_bl_p = post_bl.createForAssemblyContext(post_occ)
    post_br_p = post_br.createForAssemblyContext(post_occ)

    sp.combine(post_fl_p, [srl_p], CUT, True, "SupRailMort_FL")
    sp.combine(post_bl_p, [srl_p], CUT, True, "SupRailMort_BL")
    if srr_p:
        sp.combine(post_fr_p, [srr_p], CUT, True, "SupRailMort_FR")
        sp.combine(post_br_p, [srr_p], CUT, True, "SupRailMort_BR")
    print(">>> Support rail mortises: CUT into 4 posts")

    # --- Slats → support rails (dominos at each slat end) ---
    # Interface planes at support rail inner faces (inside support component)
    dm_slat_xl = sp.off_plane(support_c, support_c.yZConstructionPlane,
                               "sup_rail_inset + sup_rail_w", "DM_SlatXL")
    dm_slat_xr = sp.off_plane(support_c, support_c.yZConstructionPlane,
                               "outer_w - sup_rail_inset - sup_rail_w", "DM_SlatXR")
    # Domino center Z = middle of slat thickness
    params.add("slat_dm_z", VI("slat_z + support_thick / 2"), "in", "")
    # First slat Y center
    params.add("slat_dm_y0", VI("post_size + slat_w / 2"), "in", "")

    # Body-relative ref: slat dominos depend on support rails
    ref_sr_r = find_body("SupRail_Right")
    ref_sr_r_bb = ref_sr_r.boundingBox

    # Create domino voids without CUT (we'll CUT manually)
    left_voids = domino.grid(support_c, dm_slat_xl,
        ("sup_rail_inset + sup_rail_w", "slat_dm_y0", "slat_dm_z"),
        "y", "slat_sp", "n_slats", "y", "dm_w", "dm_t", "dm_d",
        body_a=None, body_b=None, name="DM_SlatL", ev=ev, cut=False)
    right_voids = domino.grid(support_c, dm_slat_xr,
        ("outer_w - sup_rail_inset - sup_rail_w", "slat_dm_y0", "slat_dm_z"),
        "y", "slat_sp", "n_slats", "y", "dm_w", "dm_t", "dm_d",
        body_a=None, body_b=None, name="DM_SlatR", ev=ev, cut=False)

    # Bulk CUT all domino voids into support rails (all overlap the long rail)
    sp.combine(srl_p, left_voids, CUT, True, "DM_SlatL_CutRail")
    if srr_p:
        sp.combine(srr_p, right_voids, CUT, True, "DM_SlatR_CutRail")

    # Collect slat proxies and bulk CUT all voids into each slat
    # (only the domino at each slat's Y position actually intersects)
    slat_bodies_proxies = []
    for i in range(support_c.bRepBodies.count):
        b = support_c.bRepBodies.item(i)
        if b.name.startswith("Slat_"):
            slat_bodies_proxies.append(b.createForAssemblyContext(support_occ))

    all_voids = left_voids + right_voids
    for slat_p in slat_bodies_proxies:
        sp.combine(slat_p, all_voids, CUT, True, "DM_Slat_Cut")
    print(f">>> Slat dominos: {int(ev('n_slats')) * 2} joints (into support rails)")

    # ================================================================
    #  6. DETAILS — chamfers on all exposed edges
    # ================================================================
    # Post tops first (larger chamfer for safety), then general edge break.
    # Order matters: general chamfer runs on already-chamfered post tops,
    # but the small size (1/32") on the new chamfer faces is fine.

    # 6a. Post top chamfers (larger, safety)
    post_top_edges = adsk.core.ObjectCollection.create()
    for body_name in ["Post_FL", "Post_FR", "Post_BL", "Post_BR"]:
        body = None
        for bi in range(post_c.bRepBodies.count):
            if post_c.bRepBodies.item(bi).name == body_name:
                body = post_c.bRepBodies.item(bi)
                break
        if not body:
            continue
        top_z = -1e10
        for fi in range(body.faces.count):
            f = body.faces.item(fi)
            if isinstance(f.geometry, adsk.core.Plane):
                if abs(f.geometry.normal.z) > 0.9 and f.pointOnFace.z > top_z:
                    top_z = f.pointOnFace.z
        for ei in range(body.edges.count):
            edge = body.edges.item(ei)
            sv = edge.startVertex.geometry
            ev_p = edge.endVertex.geometry
            if sv.z > top_z - 0.1 and ev_p.z > top_z - 0.1:
                post_top_edges.add(edge)
    if post_top_edges.count > 0:
        ch_inp = post_c.features.chamferFeatures.createInput2()
        ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
            post_top_edges, VI("post_chamfer"), True)
        post_c.features.chamferFeatures.add(ch_inp).name = "PostTops_Ch"

    # 6b. General edge break — one chamfer per component, all structural edges
    # Skip Spindles (already round) — chamfer posts, rails, support only
    for comp_name, comp in [("Posts", post_c), ("Rails", rail_c),
                             ("Support", support_c)]:
        edges = adsk.core.ObjectCollection.create()
        for bi in range(comp.bRepBodies.count):
            body = comp.bRepBodies.item(bi)
            if body.name.startswith("DM_"):
                continue
            for ei in range(body.edges.count):
                edges.add(body.edges.item(ei))
        if edges.count > 0:
            ch_inp = comp.features.chamferFeatures.createInput2()
            ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                edges, VI("edge_chamfer"), True)
            comp.features.chamferFeatures.add(ch_inp).name = f"{comp_name}_Ch"

    print(">>> Chamfers: post tops + 3 component edge breaks")

    # ================================================================
    #  EPILOGUE
    # ================================================================
    for comp in [post_c, rail_c, spindle_c, support_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False
    for sk in root.sketches:
        sk.isVisible = False
    for cp in root.constructionPlanes:
        cp.isLightBulbOn = False

    for cn, c in [("Posts", post_c), ("Rails", rail_c),
                   ("Spindles", spindle_c), ("Support", support_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{cn}: {len(names)} bodies")
    print(f"Root: {root.bRepBodies.count} joinery voids")

    sp.apply_appearance("maple")

    # Set visual style with edge lines visible
    vp = app.activeViewport
    vp.visualStyle = adsk.core.VisualStyles.ShadedWithVisibleEdgesOnlyVisualStyle
    cam = vp.camera
    cam.isFitView = True
    vp.camera = cam
