"""
Twin Bed Frame with Live Edge Slab Headboard + Bowtie Inlays
=============================================================
39"W x 75"L mattress, 36"H headboard (2" thick live edge slab),
3 decorative walnut bowties across a diagonal crack line.
4 corner posts, side rails with ledger strips, foot rail, slat system.

Coordinate system:
  X = width (45" outer)  Y = length (81" outer)  Z = height
"""
import adsk.core, adsk.fusion, math

from helpers import sp
from woodworking.templates import domino
from woodworking.templates import bowtie
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
        ("bed_w",          "39 in",   "in"),
        ("bed_l",          "75 in",   "in"),
        # Structure
        ("post_size",      "3 in",    "in"),
        ("rail_h",         "10 in",   "in"),
        ("rail_thick",     "1.5 in",  "in"),
        ("leg_clearance",  "4 in",    "in"),
        ("back_rail_h",    "5 in",    "in"),
        ("mattress_recess","1.5 in",  "in"),
        ("headboard_h",   "36 in",    "in"),
        # Headboard slab
        ("slab_thick",     "2 in",    "in"),
        # Bowties (perpendicular to crack / fiber direction)
        ("bt_len",         "3 in",    "in"),   # bowtie length (perpendicular to crack)
        ("bt_end_w",       "1.5 in",  "in"),   # width at the wide ends
        ("bt_waist_w",     "0.5 in",  "in"),   # width at the narrow waist
        ("bt_depth",       "0.67 in", "in"),   # inlay depth (~1/3 of 2" slab)
        ("n_bowties",      "3",       ""),
        # Slats
        ("n_slats",        "10",      ""),
        ("slat_w",         "3 in",    "in"),
        ("slat_thick",     "0.75 in", "in"),
        # Support
        ("ledger_h",       "1.5 in",  "in"),
        ("ledger_thick",   "0.75 in", "in"),
        # Dominos
        ("dm_t",           "8 mm",    "in"),
        ("dm_w",           "40 mm",   "in"),
        ("dm_d",           "20 mm",   "in"),
        # Ledger dominos (smaller for thin stock)
        ("ldm_t",          "5 mm",    "in"),
        ("ldm_w",          "30 mm",   "in"),
        ("ldm_d",          "15 mm",   "in"),
        # Details
        ("post_chamfer",   "0.25 in", "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    # === DERIVED PARAMETERS ===
    for pname, expr, unit in [
        ("outer_w",        "bed_w + 2 * post_size",                    "in"),
        ("outer_l",        "bed_l + 2 * post_size",                    "in"),
        ("side_rail_l",    "bed_l",                                     "in"),
        ("end_rail_l",     "bed_w",                                     "in"),
        ("mid_x",          "outer_w / 2",                               "in"),
        ("mid_y",          "outer_l / 2",                               "in"),
        # Post heights
        ("front_post_h",   "leg_clearance + rail_h",                    "in"),
        # Rail Z positions
        ("rail_z",         "leg_clearance",                             "in"),
        ("rail_top_z",     "leg_clearance + rail_h - post_chamfer",     "in"),
        # Slat positions
        ("slat_top_z",     "rail_top_z - mattress_recess",              "in"),
        ("slat_z",         "slat_top_z - slat_thick",                   "in"),
        ("ledger_z",       "slat_z - ledger_h",                        "in"),
        ("slat_l",         "outer_w - post_size - rail_thick",          "in"),
        ("slat_sp",        "(bed_l - slat_w) / (n_slats - 1)",         "in"),
        # Headboard slab (fits within posts, below chamfer line at top)
        ("slab_w",         "outer_w",                                    "in"),
        ("slab_h",         "headboard_h - front_post_h - post_chamfer", "in"),
        ("slab_z",         "front_post_h",                              "in"),
        ("slab_y",         "outer_l - post_size / 2 - slab_thick / 2",  "in"),
        # Bowtie spacing (evenly distributed across slab width)
        ("bt_spacing",     "outer_w / (n_bowties + 1)",                 "in"),
        # Domino Z positions
        ("rail_dm_z1",     "rail_z + (rail_h - post_chamfer) / 3",     "in"),
        ("rail_dm_sp",     "(rail_h - post_chamfer) / 3",              "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    print(">>> Parameters done")

    # === COMPONENTS ===
    post_occ = sp.make_comp(root, "Posts")
    rail_occ = sp.make_comp(root, "Rails")
    hb_occ   = sp.make_comp(root, "Headboard")
    slat_occ = sp.make_comp(root, "Slats")

    post_c = post_occ.component
    rail_c = rail_occ.component
    hb_c   = hb_occ.component
    slat_c = slat_occ.component

    # ================================================================
    #  1. POSTS
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

    print(">>> Posts: 4")

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

    fr_pl = sp.off_plane(rail_c, rail_c.xZConstructionPlane,
                          "post_size / 2 - rail_thick / 2", "FR_Pl")
    _, pr = sp.sketch_rect_model(rail_c, fr_pl,
        ("post_size", "post_size / 2 - rail_thick / 2", "rail_z"),
        {"x": "end_rail_l", "z": "rail_h - post_chamfer"}, "FootRail_Sk", ev)
    fr_ext = sp.ext_new(rail_c, pr, "rail_thick", "FootRail")
    rail_foot = fr_ext.bodies.item(0); rail_foot.name = "Rail_Foot"

    # Back rail: between back posts, shorter, forward of headboard
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

    # Ledger strips
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
    #  3. HEADBOARD — live edge slab + 3 bowtie inlays
    # ================================================================
    # Slab: wide plank spanning behind back posts with overhang on each side
    slab_y_pl = sp.off_plane(hb_c, hb_c.xZConstructionPlane, "slab_y", "SlabY_Pl")
    _, pr = sp.sketch_rect_model(hb_c, slab_y_pl,
        ("0 in", "slab_y", "slab_z"),
        {"x": "slab_w", "z": "slab_h"}, "Slab_Sk", ev)
    slab_ext = sp.ext_new(hb_c, pr, "slab_thick", "Slab")
    slab = slab_ext.bodies.item(0); slab.name = "Slab"

    # Body-relative reference for bowtie positioning
    ref_slab = find_body("Slab")
    ref_slab_bb = ref_slab.boundingBox

    # Bowties: perpendicular to crack (fiber in X → bowties vertical in Z).
    # Slab face is XZ; long axis Z crosses the crack, short axis X runs
    # along it.
    bt_bodies = bowtie.row(hb_c, slab_y_pl,
        crack_axis="x",
        crack_center=("mid_x", "slab_y", "slab_z + slab_h / 2"),
        count="n_bowties", spacing="bt_spacing",
        long_axis="z", short_axis="x",
        length="bt_len", end_w="bt_end_w",
        waist_w="bt_waist_w", depth="bt_depth",
        slab_body=slab, name="BT", ev=ev)

    print(f">>> Headboard: 1 slab + {len(bt_bodies)} bowties")

    # ================================================================
    #  4. SLATS
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
    #  5. CROSS-COMPONENT: Dominos everywhere
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
    slab_p = slab.createForAssemblyContext(hb_occ)

    # CUT back posts from slab (slab wraps around posts)
    sp.combine(slab_p, [bl_p, br_p], CUT, True, "SlabPostNotch")

    # Domino planes (kept in root for bed rail fasteners)
    dm_xl = sp.off_plane(root, root.yZConstructionPlane, "post_size", "DM_XL")
    dm_xr = sp.off_plane(root, root.yZConstructionPlane, "outer_w - post_size", "DM_XR")
    dm_yf = sp.off_plane(root, root.xZConstructionPlane, "post_size", "DM_YF")
    dm_yb = sp.off_plane(root, root.xZConstructionPlane, "outer_l - post_size", "DM_YB")

    # Domino planes inside headboard component (for slab joints)
    hb_dm_xl = sp.off_plane(hb_c, hb_c.yZConstructionPlane, "post_size", "DM_XL")
    hb_dm_xr = sp.off_plane(hb_c, hb_c.yZConstructionPlane, "outer_w - post_size", "DM_XR")

    # --- Rails → posts (bed rail fasteners — detachable) ---
    rail_center_z = ev("rail_z") + (ev("rail_top_z") - ev("rail_z")) / 2
    brf.install(root, fl_p, rl_p, interface_axis="y",
                interface_coord=ev("post_size"), center_z=rail_center_z,
                size="100mm", name="BRF_RL_F", ev=ev)
    brf.install(root, bl_p, rl_p, interface_axis="y",
                interface_coord=ev("outer_l") - ev("post_size"), center_z=rail_center_z,
                size="100mm", name="BRF_RL_B", ev=ev)
    brf.install(root, fr_p, rr_p, interface_axis="y",
                interface_coord=ev("post_size"), center_z=rail_center_z,
                size="100mm", name="BRF_RR_F", ev=ev)
    brf.install(root, br_p, rr_p, interface_axis="y",
                interface_coord=ev("outer_l") - ev("post_size"), center_z=rail_center_z,
                size="100mm", name="BRF_RR_B", ev=ev)
    brf.install(root, fl_p, rf_p, interface_axis="x",
                interface_coord=ev("post_size"), center_z=rail_center_z,
                size="100mm", name="BRF_RF_L", ev=ev)
    brf.install(root, fr_p, rf_p, interface_axis="x",
                interface_coord=ev("outer_w") - ev("post_size"), center_z=rail_center_z,
                size="100mm", name="BRF_RF_R", ev=ev)
    # Back rail (smaller 80mm)
    rb_p = rail_back.createForAssemblyContext(rail_occ)
    back_rail_cz = ev("rail_z") + ev("back_rail_h") / 2
    brf.install(root, bl_p, rb_p, interface_axis="x",
                interface_coord=ev("post_size"), center_z=back_rail_cz,
                size="80mm", name="BRF_RB_L", ev=ev)
    brf.install(root, br_p, rb_p, interface_axis="x",
                interface_coord=ev("outer_w") - ev("post_size"), center_z=back_rail_cz,
                size="80mm", name="BRF_RB_R", ev=ev)

    # Slab → back posts (2 per post, 4 total)
    slab_dm_z1 = ev("slab_z") + ev("slab_h") / 3
    slab_dm_sp = ev("slab_h") / 3
    domino.grid(hb_c, hb_dm_xl,
        ("post_size", f"{ev('outer_l') - ev('post_size') / 2} cm", f"{slab_dm_z1} cm"),
        "z", f"{slab_dm_sp} cm", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        slab, bl_p, "DM_SL_L", ev)
    domino.grid(hb_c, hb_dm_xr,
        ("outer_w - post_size", f"{ev('outer_l') - ev('post_size') / 2} cm", f"{slab_dm_z1} cm"),
        "z", f"{slab_dm_sp} cm", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        slab, br_p, "DM_SL_R", ev)

    # Ledger strips → side rails (smaller dominos, both in rail_c)
    params.add("ledger_dm_count", VI("4"), "", "")
    params.add("ledger_dm_sp", VI("(side_rail_l - 2 * post_size) / (ledger_dm_count + 1)"), "in", "")
    params.add("ledger_dm_y0", VI("post_size + ledger_dm_sp"), "in", "")
    params.add("ledger_dm_z", VI("ledger_z + ledger_h / 2"), "in", "")

    ledger_dm_pl_l = sp.off_plane(rail_c, rail_c.yZConstructionPlane,
        "post_size / 2 + rail_thick / 2", "LedgerDM_PlL")
    domino.grid(rail_c, ledger_dm_pl_l,
        ("post_size / 2 + rail_thick / 2", "ledger_dm_y0", "ledger_dm_z"),
        "y", "ledger_dm_sp", "ledger_dm_count", "y", "ldm_w", "ldm_t", "ldm_d",
        ledger_left, rail_left, "DM_LL", ev)

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

    print(">>> Dominos: all joints connected")

    # ================================================================
    #  6. DETAILS — post top chamfers
    # ================================================================
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

    # Hardware cleanup
    hw_container = None
    occs_to_move = []
    for i in range(root.occurrences.count):
        occ = root.occurrences.item(i)
        nm = occ.component.name
        if nm.startswith("_Hardware") or nm.startswith("_Imports") or nm.startswith("BRF_") or nm.startswith("Bedlock"):
            occs_to_move.append(occ)
        elif occ.component.sketches.count == 0 and nm not in ["Posts", "Rails", "Headboard", "Slats"]:
            occs_to_move.append(occ)
    if occs_to_move:
        hw_container = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        hw_container.component.name = "_HW"
        hw_container.isLightBulbOn = False
        for occ in occs_to_move:
            if occ.isValid:
                try:
                    occ.moveToComponent(hw_container)
                except Exception:
                    pass
    print(f">>> Hardware cleanup: {len(occs_to_move)} items moved to _HW")

    # ================================================================
    #  EPILOGUE
    # ================================================================
    for comp in [post_c, rail_c, hb_c, slat_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False
    for sk in root.sketches:
        sk.isVisible = False
    for cp in root.constructionPlanes:
        cp.isLightBulbOn = False

    for cn, c in [("Posts", post_c), ("Rails", rail_c),
                   ("Headboard", hb_c), ("Slats", slat_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{cn}: {len(names)} -> {names}")
    print(f"Root: {root.bRepBodies.count} domino voids")

    sp.apply_appearance("white oak")
    bt_names = [b.name for b in bt_bodies]
    sp.apply_appearance("walnut", bodies=bt_names)

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
