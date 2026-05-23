"""
Modern Platform Bed Frame (Queen)
=================================
60"W x 80"L mattress, 36"H headboard, 10"H side rails.
4 corner posts, side rails with ledger strips, foot rail,
framed headboard with vertical slats, slat system, center support beam.
All joints mechanically connected (dominos + stub tenons).

Coordinate system:
  X = width (66" outer)  Y = length (86" outer)  Z = height
"""
import adsk.core, adsk.fusion

from helpers import sp
from woodworking.templates import domino
from woodworking.templates import bed_rail_fastener as brf
from helpers import hardware as hw_mgr

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    # === BODY-RELATIVE LOOKUP ===
    def find_body(name, comp=None):
        c = comp or root
        for i in range(c.bRepBodies.count):
            if c.bRepBodies.item(i).name == name:
                return c.bRepBodies.item(i)
        for j in range(c.occurrences.count):
            r = find_body(name, c.occurrences.item(j).component)
            if r:
                return r
        return None

    # === USER PARAMETERS ===
    for pname, expr, unit in [
        # Mattress
        ("bed_w",         "60 in",   "in"),
        ("bed_l",         "80 in",   "in"),
        # Structure
        ("post_size",     "3 in",    "in"),
        ("rail_h",        "10 in",   "in"),
        ("rail_thick",    "1.5 in",  "in"),
        ("leg_clearance", "4 in",    "in"),   # space under rails to floor
        ("mattress_recess","1.5 in", "in"),   # slat top below rail top (secures mattress)
        ("headboard_h",   "36 in",   "in"),
        ("back_rail_h",   "5 in",    "in"),   # shorter than side rails (headboard adds rigidity)
        # Headboard frame
        ("hb_top_rail_h", "3 in",    "in"),
        ("hb_bot_rail_h", "3 in",    "in"),
        ("hb_rail_thick", "1 in",    "in"),
        ("n_hb_slats",    "5",       ""),
        ("hb_slat_w",     "2.5 in",  "in"),
        ("hb_slat_thick", "0.75 in", "in"),
        # Slats
        ("n_slats",       "13",      ""),
        ("slat_w",        "3 in",    "in"),
        ("slat_thick",    "0.75 in", "in"),
        # Support
        ("ledger_h",      "1.5 in",  "in"),
        ("ledger_thick",  "0.75 in", "in"),
        ("beam_w",        "3 in",    "in"),
        ("beam_thick",    "1.5 in",  "in"),
        ("beam_leg_size", "1.5 in",  "in"),
        # Dominos
        ("dm_t",          "8 mm",    "in"),
        ("dm_w",          "40 mm",   "in"),
        ("dm_d",          "20 mm",   "in"),
        # Details
        ("post_chamfer",  "0.25 in", "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    # === DERIVED PARAMETERS ===
    for pname, expr, unit in [
        ("outer_w",       "bed_w + 2 * post_size",                    "in"),
        ("outer_l",       "bed_l + 2 * post_size",                    "in"),
        ("side_rail_l",   "bed_l",                                     "in"),
        ("end_rail_l",    "bed_w",                                     "in"),
        ("mid_x",         "outer_w / 2",                               "in"),
        ("mid_y",         "outer_l / 2",                               "in"),
        # Post heights (legs extend from floor, rails sit above clearance)
        ("front_post_h",  "leg_clearance + rail_h",                    "in"),
        # Rail Z positions (raised off floor by leg_clearance)
        ("rail_z",        "leg_clearance",                             "in"),
        ("rail_top_z",    "leg_clearance + rail_h - post_chamfer",     "in"),
        # Slat top sits below rail top by mattress_recess
        ("slat_top_z",    "rail_top_z - mattress_recess",              "in"),
        ("slat_z",        "slat_top_z - slat_thick",                   "in"),
        # Ledger supports slats from below
        ("ledger_z",      "slat_z - ledger_h",                        "in"),
        # Slats span from inner face of left rail to inner face of right rail
        ("slat_l",        "outer_w - post_size - rail_thick",          "in"),
        ("slat_sp",       "(bed_l - slat_w) / (n_slats - 1)",         "in"),
        # Headboard slat spacing
        ("hb_zone_h",     "headboard_h - front_post_h - hb_top_rail_h - hb_bot_rail_h", "in"),
        ("hb_slat_gap",   "(end_rail_l - n_hb_slats * hb_slat_w) / (n_hb_slats + 1)", "in"),
        ("hb_slat_pitch", "hb_slat_w + hb_slat_gap",                  "in"),
        ("hb_slat_start", "post_size + hb_slat_gap + hb_slat_w / 2",  "in"),
        ("hb_slat_tenon", "dm_d",                                      "in"),
        # Headboard rail center Y on post
        ("hb_face_y",     "outer_l - post_size / 2 - hb_rail_thick / 2", "in"),
        # Center beam (from floor to ledger top)
        ("beam_h",        "ledger_z + ledger_h",                       "in"),
        # Domino Z positions (within rail, offset from rail_z)
        ("rail_dm_z1",    "rail_z + (rail_h - post_chamfer) / 3",     "in"),
        ("rail_dm_sp",    "(rail_h - post_chamfer) / 3",              "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    print(">>> Parameters done")

    # === COMPONENTS ===
    post_occ    = sp.make_comp(root, "Posts")
    rail_occ    = sp.make_comp(root, "Rails")
    hb_occ      = sp.make_comp(root, "Headboard")
    slat_occ    = sp.make_comp(root, "Slats")
    support_occ = sp.make_comp(root, "Support")

    post_c    = post_occ.component
    rail_c    = rail_occ.component
    hb_c      = hb_occ.component
    slat_c    = slat_occ.component
    support_c = support_occ.component

    # ================================================================
    #  1. POSTS — 4 corner posts (front short, back tall for headboard)
    # ================================================================
    _, pr = sp.sketch_rect_model(post_c, post_c.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "post_size", "y": "post_size"}, "PostFL_Sk", ev)
    fl_ext = sp.ext_new(post_c, pr, "front_post_h", "PostFL")
    post_fl = fl_ext.bodies.item(0); post_fl.name = "Post_FL"

    p_xmid = sp.off_plane(post_c, post_c.yZConstructionPlane, "mid_x", "PXMid")
    post_fr = sp.mirror_body(post_c, post_fl, p_xmid, "PostFR").bodies.item(0)
    post_fr.name = "Post_FR"

    _, pr = sp.sketch_rect_model(post_c, post_c.xYConstructionPlane,
        ("0 in", "bed_l + post_size", "0 in"),
        {"x": "post_size", "y": "post_size"}, "PostBL_Sk", ev)
    bl_ext = sp.ext_new(post_c, pr, "headboard_h", "PostBL")
    post_bl = bl_ext.bodies.item(0); post_bl.name = "Post_BL"

    post_br = sp.mirror_body(post_c, post_bl, p_xmid, "PostBR").bodies.item(0)
    post_br.name = "Post_BR"

    print(">>> Posts: 4 (front posts, back headboard posts)")

    # ================================================================
    #  2. RAILS — side rails, foot rail, ledger strips
    # ================================================================
    # Body-relative references for rail positioning
    ref_post_fl = find_body("Post_FL")
    ref_post_fl_bb = ref_post_fl.boundingBox
    ref_post_fr = find_body("Post_FR")
    ref_post_fr_bb = ref_post_fr.boundingBox
    ref_post_bl = find_body("Post_BL")
    ref_post_bl_bb = ref_post_bl.boundingBox

    # Side rails: between posts, centered on post cross-section
    lr_pl = sp.off_plane(rail_c, rail_c.yZConstructionPlane,
                          "post_size / 2 - rail_thick / 2", "LR_Pl")
    _, pr = sp.sketch_rect_model(rail_c, lr_pl,
        ("post_size / 2 - rail_thick / 2", "post_size", "rail_z"),
        {"y": "side_rail_l", "z": "rail_h - post_chamfer"}, "LeftRail_Sk", ev)
    lr_ext = sp.ext_new(rail_c, pr, "rail_thick", "LeftRail")
    rail_left = lr_ext.bodies.item(0); rail_left.name = "Rail_Left"

    r_xmid = sp.off_plane(rail_c, rail_c.yZConstructionPlane, "mid_x", "RXMid")
    rail_right = sp.mirror_feats(rail_c, [lr_ext], r_xmid, "RightRailMir").bodies.item(0)
    rail_right.name = "Rail_Right"

    # Foot rail: between front posts, centered on post
    fr_pl = sp.off_plane(rail_c, rail_c.xZConstructionPlane,
                          "post_size / 2 - rail_thick / 2", "FR_Pl")
    _, pr = sp.sketch_rect_model(rail_c, fr_pl,
        ("post_size", "post_size / 2 - rail_thick / 2", "rail_z"),
        {"x": "end_rail_l", "z": "rail_h - post_chamfer"}, "FootRail_Sk", ev)
    fr_ext = sp.ext_new(rail_c, pr, "rail_thick", "FootRail")
    rail_foot = fr_ext.bodies.item(0); rail_foot.name = "Rail_Foot"

    # Back rail: between back posts, narrower, forward of headboard
    br_pl = sp.off_plane(rail_c, rail_c.xZConstructionPlane,
                          "outer_l - post_size + post_size / 2 - rail_thick / 2", "BR_Pl")
    _, pr = sp.sketch_rect_model(rail_c, br_pl,
        ("post_size", "outer_l - post_size + post_size / 2 - rail_thick / 2", "rail_z"),
        {"x": "end_rail_l", "z": "back_rail_h"}, "BackRail_Sk", ev)
    back_rail_ext = sp.ext_new(rail_c, pr, "rail_thick", "BackRail")
    rail_back = back_rail_ext.bodies.item(0); rail_back.name = "Rail_Back"

    # Body-relative references for ledger positioning
    ref_rail_left = find_body("Rail_Left")
    ref_rail_left_bb = ref_rail_left.boundingBox
    ref_rail_right = find_body("Rail_Right")
    ref_rail_right_bb = ref_rail_right.boundingBox

    # Ledger strips: on inside face of side rails, supporting slats
    ldg_pl = sp.off_plane(rail_c, rail_c.yZConstructionPlane,
                           "post_size / 2 + rail_thick / 2", "LDG_Pl")
    _, pr = sp.sketch_rect_model(rail_c, ldg_pl,
        ("post_size / 2 + rail_thick / 2", "post_size", "ledger_z"),
        {"y": "side_rail_l", "z": "ledger_h"}, "LedgerL_Sk", ev)
    ll_ext = sp.ext_new(rail_c, pr, "ledger_thick", "LedgerLeft")
    ledger_left = ll_ext.bodies.item(0); ledger_left.name = "Ledger_Left"

    sp.mirror_feats(rail_c, [ll_ext], r_xmid, "LedgerRMir").bodies.item(0).name = "Ledger_Right"

    print(">>> Rails: 4 rails + 2 ledgers")

    # ================================================================
    #  3. HEADBOARD — framed: top rail + bottom rail + vertical slats
    # ================================================================
    # Rails and slats centered on back post cross-section
    hb_y_pl = sp.off_plane(hb_c, hb_c.xZConstructionPlane, "hb_face_y", "HB_Y_Pl")

    # Top rail (between posts)
    _, pr = sp.sketch_rect_model(hb_c, hb_y_pl,
        ("post_size", "hb_face_y", "headboard_h - hb_top_rail_h"),
        {"x": "end_rail_l", "z": "hb_top_rail_h"}, "HBTopRail_Sk", ev)
    hb_tr_ext = sp.ext_new(hb_c, pr, "hb_rail_thick", "HBTopRail")
    hb_top_rail = hb_tr_ext.bodies.item(0); hb_top_rail.name = "HB_TopRail"

    # Bottom rail (between posts, at side rail height)
    _, pr = sp.sketch_rect_model(hb_c, hb_y_pl,
        ("post_size", "hb_face_y", "front_post_h"),
        {"x": "end_rail_l", "z": "hb_bot_rail_h"}, "HBBotRail_Sk", ev)
    hb_br_ext = sp.ext_new(hb_c, pr, "hb_rail_thick", "HBBotRail")
    hb_bot_rail = hb_br_ext.bodies.item(0); hb_bot_rail.name = "HB_BotRail"

    # Body-relative references for headboard slat positioning
    ref_hb_bot_rail = find_body("HB_BotRail")
    ref_hb_bot_rail_bb = ref_hb_bot_rail.boundingBox
    ref_hb_top_rail = find_body("HB_TopRail")
    ref_hb_top_rail_bb = ref_hb_top_rail.boundingBox

    # Vertical slats with stub tenons into rails
    _, pr = sp.sketch_rect_model(hb_c, hb_y_pl,
        ("hb_slat_start - hb_slat_w / 2", "hb_face_y",
         "front_post_h + hb_bot_rail_h - hb_slat_tenon"),
        {"x": "hb_slat_w", "z": "hb_zone_h + 2 * hb_slat_tenon"}, "HBSlat_Sk", ev)
    hb_slat_ext = sp.ext_new(hb_c, pr, "hb_slat_thick", "HBSlat_1")
    hb_slat = hb_slat_ext.bodies.item(0); hb_slat.name = "HBSlat_1"

    n_hbs = int(ev("n_hb_slats"))
    hb_pat = None
    if n_hbs > 1:
        hb_pat = sp.body_pattern(hb_c, hb_slat, hb_c.xConstructionAxis,
                                  "n_hb_slats", "hb_slat_pitch", "HBSlatPat")
        for i in range(hb_pat.bodies.count):
            hb_pat.bodies.item(i).name = f"HBSlat_{i+2}"

    print(f">>> Headboard: 2 rails + {n_hbs} slats")

    # ================================================================
    #  4. SLATS — mattress support, resting on ledger strips
    # ================================================================
    # Body-relative references for slat positioning
    ref_ledger_left = find_body("Ledger_Left")
    ref_ledger_left_bb = ref_ledger_left.boundingBox
    ref_ledger_right = find_body("Ledger_Right")
    ref_ledger_right_bb = ref_ledger_right.boundingBox
    slat_z_pl = sp.off_plane(slat_c, slat_c.xYConstructionPlane, "slat_z", "SlatZ_Pl")
    _, pr = sp.sketch_rect_model(slat_c, slat_z_pl,
        ("post_size / 2 + rail_thick / 2", "post_size", "slat_z"),
        {"x": "slat_l", "y": "slat_w"}, "Slat_Sk", ev)
    slat_ext = sp.ext_new(slat_c, pr, "slat_thick", "Slat_1")
    slat_body = slat_ext.bodies.item(0); slat_body.name = "Slat_1"

    if int(ev("n_slats")) > 1:
        pat = sp.body_pattern(slat_c, slat_body, slat_c.yConstructionAxis,
                               "n_slats", "slat_sp", "SlatPat")
        for i in range(pat.bodies.count):
            pat.bodies.item(i).name = f"Slat_{i+2}"

    print(f">>> Slats: {int(ev('n_slats'))} bodies")

    # ================================================================
    #  5. CENTER SUPPORT — beam with 2 legs
    # ================================================================
    # Body-relative reference for center beam positioning
    ref_slat_1 = find_body("Slat_1")
    if ref_slat_1:
        ref_slat_1_bb = ref_slat_1.boundingBox

    # Beam: runs lengthwise (Y) at mid_x, from post to post, up to ledger top
    beam_pl = sp.off_plane(support_c, support_c.yZConstructionPlane,
                            "mid_x - beam_thick / 2", "Beam_Pl")
    _, pr = sp.sketch_rect_model(support_c, beam_pl,
        ("mid_x - beam_thick / 2", "post_size", "beam_h - beam_w"),
        {"y": "bed_l", "z": "beam_w"}, "Beam_Sk", ev)
    beam_ext = sp.ext_new(support_c, pr, "beam_thick", "CenterBeam")
    beam = beam_ext.bodies.item(0); beam.name = "CenterBeam"

    # Body-relative reference for beam leg positioning
    ref_beam = find_body("CenterBeam")
    ref_beam_bb = ref_beam.boundingBox

    # Two legs under the beam (at 1/3 and 2/3 along length)
    _, pr = sp.sketch_rect_model(support_c, support_c.xYConstructionPlane,
        ("mid_x - beam_leg_size / 2", "post_size + bed_l / 3 - beam_leg_size / 2", "0 in"),
        {"x": "beam_leg_size", "y": "beam_leg_size"}, "BeamLeg1_Sk", ev)
    bl1_ext = sp.ext_new(support_c, pr, "beam_h - beam_w", "BeamLeg1")
    bl1_ext.bodies.item(0).name = "BeamLeg_1"

    _, pr = sp.sketch_rect_model(support_c, support_c.xYConstructionPlane,
        ("mid_x - beam_leg_size / 2", "post_size + 2 * bed_l / 3 - beam_leg_size / 2", "0 in"),
        {"x": "beam_leg_size", "y": "beam_leg_size"}, "BeamLeg2_Sk", ev)
    bl2_ext = sp.ext_new(support_c, pr, "beam_h - beam_w", "BeamLeg2")
    bl2_ext.bodies.item(0).name = "BeamLeg_2"

    print(">>> Support: 1 beam + 2 legs")

    # ================================================================
    #  6. CROSS-COMPONENT: Slat mortises in headboard + domino planes
    # ================================================================
    # Headboard slat stub-mortises into rails
    hb_tr_p = hb_top_rail.createForAssemblyContext(hb_occ)
    hb_br_p = hb_bot_rail.createForAssemblyContext(hb_occ)

    all_hb_slats = [hb_slat]
    if hb_pat:
        for i in range(hb_pat.bodies.count):
            all_hb_slats.append(hb_pat.bodies.item(i))

    hb_slat_proxies = [b.createForAssemblyContext(hb_occ) for b in all_hb_slats]
    for i, slat_proxy in enumerate(hb_slat_proxies):
        sp.combine(hb_tr_p, [slat_proxy], CUT, True, f"HBSlatMort_TR_{i}")
        sp.combine(hb_br_p, [slat_proxy], CUT, True, f"HBSlatMort_BR_{i}")

    print(">>> Headboard slat mortises done")

    # ================================================================
    #  7. DOMINO JOINERY — all rail/ledger connections to posts
    # ================================================================
    params.add("dm_count", VI("2"), "", "")

    # Assembly proxies
    fl_p = post_fl.createForAssemblyContext(post_occ)
    fr_p = post_fr.createForAssemblyContext(post_occ)
    bl_p = post_bl.createForAssemblyContext(post_occ)
    br_p = post_br.createForAssemblyContext(post_occ)
    rl_p = rail_left.createForAssemblyContext(rail_occ)
    rr_p = rail_right.createForAssemblyContext(rail_occ)
    rf_p = rail_foot.createForAssemblyContext(rail_occ)
    ll_p = ledger_left.createForAssemblyContext(rail_occ)
    hb_tr_rp = hb_top_rail.createForAssemblyContext(hb_occ)
    hb_br_rp = hb_bot_rail.createForAssemblyContext(hb_occ)

    # Domino planes at post inner faces (kept in root for bed rail fasteners)
    dm_xl = sp.off_plane(root, root.yZConstructionPlane, "post_size", "DM_XL")
    dm_xr = sp.off_plane(root, root.yZConstructionPlane, "outer_w - post_size", "DM_XR")
    dm_yf = sp.off_plane(root, root.xZConstructionPlane, "post_size", "DM_YF")
    dm_yb = sp.off_plane(root, root.xZConstructionPlane, "outer_l - post_size", "DM_YB")

    # Domino planes inside headboard component (for HB rail joints)
    hb_dm_xl = sp.off_plane(hb_c, hb_c.yZConstructionPlane, "post_size", "DM_XL")
    hb_dm_xr = sp.off_plane(hb_c, hb_c.yZConstructionPlane, "outer_w - post_size", "DM_XR")

    # --- Side rails → posts (bed rail fasteners — detachable) ---
    rail_center_z = ev("rail_z") + (ev("rail_top_z") - ev("rail_z")) / 2
    # Left rail → front post
    brf.install(root, fl_p, rl_p,
                interface_axis="y", interface_coord=ev("post_size"),
                center_z=rail_center_z,
                size="100mm", name="BRF_RL_F", ev=ev)
    # Left rail → back post
    brf.install(root, bl_p, rl_p,
                interface_axis="y", interface_coord=ev("outer_l") - ev("post_size"),
                center_z=rail_center_z,
                size="100mm", name="BRF_RL_B", ev=ev)
    # Right rail → front post
    brf.install(root, fr_p, rr_p,
                interface_axis="y", interface_coord=ev("post_size"),
                center_z=rail_center_z,
                size="100mm", name="BRF_RR_F", ev=ev)
    # Right rail → back post
    brf.install(root, br_p, rr_p,
                interface_axis="y", interface_coord=ev("outer_l") - ev("post_size"),
                center_z=rail_center_z,
                size="100mm", name="BRF_RR_B", ev=ev)

    # --- Foot rail → front posts (bed rail fasteners) ---
    brf.install(root, fl_p, rf_p,
                interface_axis="x", interface_coord=ev("post_size"),
                center_z=rail_center_z,
                size="100mm", name="BRF_RF_L", ev=ev)
    brf.install(root, fr_p, rf_p,
                interface_axis="x", interface_coord=ev("outer_w") - ev("post_size"),
                center_z=rail_center_z,
                size="100mm", name="BRF_RF_R", ev=ev)

    # --- Back rail → back posts (bed rail fasteners, smaller size) ---
    rb_p = rail_back.createForAssemblyContext(rail_occ)
    back_rail_center_z = ev("rail_z") + ev("back_rail_h") / 2
    brf.install(root, bl_p, rb_p,
                interface_axis="x", interface_coord=ev("post_size"),
                center_z=back_rail_center_z,
                size="80mm", name="BRF_RB_L", ev=ev)
    brf.install(root, br_p, rb_p,
                interface_axis="x", interface_coord=ev("outer_w") - ev("post_size"),
                center_z=back_rail_center_z,
                size="80mm", name="BRF_RB_R", ev=ev)

    # --- Headboard rails → back posts (2 dominos per rail end, 8 total) ---
    # HB top rail center Z
    hb_tr_z = ev("headboard_h") - ev("hb_top_rail_h") / 2
    # HB bottom rail center Z
    hb_br_z = ev("front_post_h") + ev("hb_bot_rail_h") / 2

    domino.grid(hb_c, hb_dm_xl,
        ("post_size", f"{ev('outer_l') - ev('post_size') / 2} cm", f"{hb_tr_z} cm"),
        "z", "0 in", "1", "z", "dm_w", "dm_t", "dm_d",
        hb_top_rail, bl_p, "DM_HBT_L", ev)
    domino.grid(hb_c, hb_dm_xr,
        ("outer_w - post_size", f"{ev('outer_l') - ev('post_size') / 2} cm", f"{hb_tr_z} cm"),
        "z", "0 in", "1", "z", "dm_w", "dm_t", "dm_d",
        hb_top_rail, br_p, "DM_HBT_R", ev)
    domino.grid(hb_c, hb_dm_xl,
        ("post_size", f"{ev('outer_l') - ev('post_size') / 2} cm", f"{hb_br_z} cm"),
        "z", "0 in", "1", "z", "dm_w", "dm_t", "dm_d",
        hb_bot_rail, bl_p, "DM_HBB_L", ev)
    domino.grid(hb_c, hb_dm_xr,
        ("outer_w - post_size", f"{ev('outer_l') - ev('post_size') / 2} cm", f"{hb_br_z} cm"),
        "z", "0 in", "1", "z", "dm_w", "dm_t", "dm_d",
        hb_bot_rail, br_p, "DM_HBB_R", ev)

    # --- Ledger strips → side rails (smaller dominos for thin ledger) ---
    params.add("ldm_t", VI("5 mm"), "in", "")     # 5mm cutter for 0.75" ledger
    params.add("ldm_w", VI("30 mm"), "in", "")
    params.add("ldm_d", VI("15 mm"), "in", "")
    params.add("ledger_dm_count", VI("4"), "", "")
    params.add("ledger_dm_sp", VI("(side_rail_l - 2 * post_size) / (ledger_dm_count + 1)"), "in", "")
    params.add("ledger_dm_y0", VI("post_size + ledger_dm_sp"), "in", "")
    params.add("ledger_dm_z", VI("ledger_z + ledger_h / 2"), "in", "")

    # Left ledger → left rail (both in rail_c — use native bodies)
    ledger_dm_pl_l = sp.off_plane(rail_c, rail_c.yZConstructionPlane,
        "post_size / 2 + rail_thick / 2", "LedgerDM_PlL")
    # Ledger (grain Y) → rail (grain Y): domino lays flat, wide face in YZ plane
    # long_axis="y" (parallel to grain, wide face in the board surface plane)
    domino.grid(rail_c, ledger_dm_pl_l,
        ("post_size / 2 + rail_thick / 2", "ledger_dm_y0", "ledger_dm_z"),
        "y", "ledger_dm_sp", "ledger_dm_count", "y", "ldm_w", "ldm_t", "ldm_d",
        ledger_left, rail_left, "DM_LL", ev)

    # Right ledger → right rail (both in rail_c — use native bodies)
    ledger_dm_pl_r = sp.off_plane(rail_c, rail_c.yZConstructionPlane,
        "outer_w - post_size / 2 - rail_thick / 2", "LedgerDM_PlR")
    ledger_right_b = None
    for i in range(rail_c.bRepBodies.count):
        if rail_c.bRepBodies.item(i).name == "Ledger_Right":
            ledger_right_b = rail_c.bRepBodies.item(i)
            break

    if ledger_right_b:
        domino.grid(rail_c, ledger_dm_pl_r,
            ("outer_w - post_size / 2 - rail_thick / 2", "ledger_dm_y0", "ledger_dm_z"),
            "y", "ledger_dm_sp", "ledger_dm_count", "y", "ldm_w", "ldm_t", "ldm_d",
            ledger_right_b, rail_right, "DM_LR", ev)

    print(">>> Dominos: all rail + headboard + ledger joints")

    # ================================================================
    #  8. DETAILS — post top chamfers
    # ================================================================
    ch_size = ev("post_chamfer")
    if ch_size > 0:
        for body_name in ["Post_FL", "Post_FR", "Post_BL", "Post_BR"]:
            body = None
            for bi in range(post_c.bRepBodies.count):
                if post_c.bRepBodies.item(bi).name == body_name:
                    body = post_c.bRepBodies.item(bi)
                    break
            if not body:
                continue
            # Find top face, then chamfer its edges
            top_z = -1e10
            for fi in range(body.faces.count):
                f = body.faces.item(fi)
                if isinstance(f.geometry, adsk.core.Plane):
                    if abs(f.geometry.normal.z) > 0.9:
                        if f.pointOnFace.z > top_z:
                            top_z = f.pointOnFace.z
            top_edges = adsk.core.ObjectCollection.create()
            for ei in range(body.edges.count):
                edge = body.edges.item(ei)
                sv = edge.startVertex.geometry
                ev_p = edge.endVertex.geometry
                if sv.z > top_z - 0.1 and ev_p.z > top_z - 0.1:
                    top_edges.add(edge)
            if top_edges.count > 0:
                ch_inp = post_c.features.chamferFeatures.createInput2()
                ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                    top_edges, VI("post_chamfer"), True)
                post_c.features.chamferFeatures.add(ch_inp).name = f"{body_name}_TopCh"

        print(">>> Post top chamfers applied")

    # Hardware cleanup: hide STEP templates (installed hardware already in parent components)
    furniture_names = {"Posts", "Rails", "Headboard", "Slats", "Support"}
    templates = []
    for i in range(root.occurrences.count):
        occ = root.occurrences.item(i)
        if occ.component.name not in furniture_names:
            templates.append(occ)

    if templates:
        hw_container = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        hw_container.component.name = "_HW"
        hw_container.isLightBulbOn = False
        for occ in templates:
            if occ.isValid:
                try:
                    occ.moveToComponent(hw_container)
                except Exception:
                    pass
    print(f">>> Cleanup: {len(templates)} templates hidden")

    # ================================================================
    #  EPILOGUE
    # ================================================================
    for comp in [post_c, rail_c, hb_c, slat_c, support_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False
    for sk in root.sketches:
        sk.isVisible = False
    for cp in root.constructionPlanes:
        cp.isLightBulbOn = False

    for cn, c in [("Posts", post_c), ("Rails", rail_c),
                   ("Headboard", hb_c), ("Slats", slat_c),
                   ("Support", support_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{cn}: {len(names)} -> {names}")
    print(f"Root: {root.bRepBodies.count} domino voids")

    sp.apply_appearance("white oak")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
