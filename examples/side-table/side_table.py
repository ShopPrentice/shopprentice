"""
Modern Side Table / Nightstand
==============================
22"L x 16"W x 24"H, 0.75" top, 1.5" square legs.
Single dovetailed drawer below top, apron frame with blind M&T joinery,
interlocking tenon notches, 3" bar pull, leg chamfers, top fillet.
Walnut body with spalted maple drawer front.

Coordinate system:
  X = length (22")  Y = width (16")  Z = height (24")

Components:
  Legs    — 4 square legs (with mortise pockets)
  Aprons  — 4 rails with blind M&T tenons + interlocking notches
             (front apron has drawer opening CUT)
  Top     — solid panel with edge fillet
  Drawer  — dovetailed drawer box with 3" bar pull

Bodies: 15
  Legs(4) + Aprons(4) + Top(1) + Drawer(5) + Pull(1) = 15
"""
import adsk.core, adsk.fusion

from helpers import sp
from woodworking.templates import dovetailed_drawer
from woodworking.templates import mortise_tenon as mt
from woodworking.templates import pull

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

    # ==============================================================
    #  PARAMETERS
    # ==============================================================
    for pname, expr, unit in [
        ("table_l",     "22 in",     "in"),
        ("table_w",     "16 in",     "in"),
        ("table_h",     "24 in",     "in"),
        ("top_thick",   "0.75 in",   "in"),
        ("leg_size",    "1.5 in",    "in"),
        ("apron_h",     "4 in",      "in"),
        ("apron_thick", "0.75 in",   "in"),
        ("drawer_gap",  "0.0625 in", "in"),
        ("leg_ch",      "0.125 in",  "in"),
        ("top_fil",     "0.0625 in", "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    # M&T parameters
    mt.define_params(params, prefix="mt",
        tenon_w="2 in", tenon_thick="0.375 in", tenon_depth="1 in")

    # Pull parameters
    pull.define_params(params, prefix="pl", style="bar_3in")

    # Derived parameters
    for pname, expr, unit in [
        ("leg_h",         "table_h - top_thick",                    "in"),
        ("apron_z",       "table_h - top_thick - apron_h",          "in"),
        ("long_apron_l",  "table_l - 2 * leg_size",                 "in"),
        ("short_apron_l", "table_w - 2 * leg_size",                 "in"),
        ("mid_x",         "table_l / 2",                            "in"),
        ("mid_y",         "table_w / 2",                            "in"),
        ("notch_d",       "mt_td - leg_size / 2 + mt_tt / 2",      "in"),
        ("drawer_w",      "long_apron_l - 2 * drawer_gap",          "in"),
        ("drawer_d",      "table_w - 2 * apron_thick - drawer_gap", "in"),
        ("drawer_h",      "apron_h - 2 * drawer_gap",               "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    # Drawer template params
    dovetailed_drawer.define_params(params, prefix="dd",
        drawer_w="drawer_w", drawer_d="drawer_d", drawer_h="drawer_h",
        front_thick="0.625 in", side_thick="0.5 in",
        bottom_thick="0.25 in",
        bg_depth="0.1875 in", bg_up="0.1875 in",
        dt_angle="8 deg", dt_tail_w="0.5 in",
        front_tail_count="2", back_tail_count="2",
        x_offset="leg_size + drawer_gap",
        z_offset="apron_z + drawer_gap")

    print(">>> Parameters done")

    # ==============================================================
    #  COMPONENTS
    # ==============================================================
    leg_occ    = sp.make_comp(root, "Legs")
    apron_occ  = sp.make_comp(root, "Aprons")
    top_occ    = sp.make_comp(root, "Top")
    drawer_occ = sp.make_comp(root, "Drawer")

    leg_c    = leg_occ.component
    apron_c  = apron_occ.component
    top_c    = top_occ.component
    drawer_c = drawer_occ.component

    # ==============================================================
    #  1. LEGS
    # ==============================================================
    _, pr = sp.sketch_rect_model(leg_c, leg_c.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_size", "y": "leg_size"},
        "LegFL_Sk", ev)
    fl_ext = sp.ext_new(leg_c, pr, "leg_h", "LegFL")
    leg_fl = fl_ext.bodies.item(0)
    leg_fl.name = "Leg_FL"

    l_xmid = sp.off_plane(leg_c, leg_c.yZConstructionPlane, "mid_x", "LXMid")
    l_ymid = sp.off_plane(leg_c, leg_c.xZConstructionPlane, "mid_y", "LYMid")

    leg_fr = sp.mirror_body(leg_c, leg_fl, l_xmid, "LegFR_Mir").bodies.item(0)
    leg_fr.name = "Leg_FR"
    leg_bl = sp.mirror_body(leg_c, leg_fl, l_ymid, "LegBL_Mir").bodies.item(0)
    leg_bl.name = "Leg_BL"
    leg_br = sp.mirror_body(leg_c, leg_bl, l_xmid, "LegBR_Mir").bodies.item(0)
    leg_br.name = "Leg_BR"

    print(">>> Legs: 4 bodies")

    # ==============================================================
    #  2. APRONS
    # ==============================================================
    apron_z_pl = sp.off_plane(apron_c, apron_c.xYConstructionPlane,
        "apron_z", "ApronZ_Pl")

    # Back apron — flush with back of legs
    _, pr = sp.sketch_rect_model(apron_c, apron_z_pl,
        ("leg_size", "table_w - apron_thick", "apron_z"),
        {"x": "long_apron_l", "y": "apron_thick"},
        "BackApron_Sk", ev)
    apron_back = sp.ext_new(apron_c, pr, "apron_h", "BackApron").bodies.item(0)
    apron_back.name = "Apron_Back"

    # Front apron — flush with front of legs
    _, pr = sp.sketch_rect_model(apron_c, apron_z_pl,
        ("leg_size", "0 in", "apron_z"),
        {"x": "long_apron_l", "y": "apron_thick"},
        "FrontApron_Sk", ev)
    apron_front = sp.ext_new(apron_c, pr, "apron_h", "FrontApron").bodies.item(0)
    apron_front.name = "Apron_Front"

    # CUT drawer opening in front apron (through-cut in Y)
    _, do_pr = sp.sketch_rect_model(apron_c, apron_c.xZConstructionPlane,
        ("leg_size + drawer_gap", "0 in", "apron_z + drawer_gap"),
        {"x": "drawer_w", "z": "drawer_h"},
        "DrawerOpening_Sk", ev)
    sp.ext_op(apron_c, do_pr, "apron_thick", CUT, apron_front,
              "DrawerOpening")

    # Left side apron — between front and back legs on left side
    _, pr = sp.sketch_rect_model(apron_c, apron_z_pl,
        ("0 in", "leg_size", "apron_z"),
        {"x": "apron_thick", "y": "short_apron_l"},
        "LeftApron_Sk", ev)
    apron_left = sp.ext_new(apron_c, pr, "apron_h", "LeftApron").bodies.item(0)
    apron_left.name = "Apron_Left"

    # (Right side apron mirrored after joinery)

    print(">>> Aprons: 3 bodies (front with opening, right after joinery)")

    # ==============================================================
    #  3. BLIND M&T JOINERY — tenons at all apron ends
    # ==============================================================
    a_xmid = sp.off_plane(apron_c, apron_c.yZConstructionPlane,
        "mid_x", "AXMid")
    a_ymid = sp.off_plane(apron_c, apron_c.xZConstructionPlane,
        "mid_y", "AYMid")

    # Back apron — tenons on left + right ends (mirror across X mid)
    ba_left_face = sp.find_face(apron_back, "x", -1)
    mt.blind(apron_c, ba_left_face,
        origin=("leg_size",
                "table_w - apron_thick / 2 - mt_tt / 2",
                "apron_z + apron_h / 2 - mt_tw / 2"),
        size={"y": "mt_tt", "z": "mt_tw"},
        depth_expr="mt_td",
        tenon_body=apron_back, mortise_body=leg_bl,
        name="BA_L", ev=ev, mirror_plane=a_xmid)

    # Front apron — tenons on left + right ends (mirror across X mid)
    fa_left_face = sp.find_face(apron_front, "x", -1)
    mt.blind(apron_c, fa_left_face,
        origin=("leg_size",
                "apron_thick / 2 - mt_tt / 2",
                "apron_z + apron_h / 2 - mt_tw / 2"),
        size={"y": "mt_tt", "z": "mt_tw"},
        depth_expr="mt_td",
        tenon_body=apron_front, mortise_body=leg_fl,
        name="FA_L", ev=ev, mirror_plane=a_xmid)

    # Left side apron — tenons on front + back ends (mirror across Y mid)
    la_front_face = sp.find_face(apron_left, "y", -1)
    mt.blind(apron_c, la_front_face,
        origin=("apron_thick / 2 - mt_tt / 2",
                "leg_size",
                "apron_z + apron_h / 2 - mt_tw / 2"),
        size={"x": "mt_tt", "z": "mt_tw"},
        depth_expr="mt_td",
        tenon_body=apron_left, mortise_body=leg_fl,
        name="LA_F", ev=ev, mirror_plane=a_ymid)

    print(">>> M&T: 6 tenons on 3 aprons (right side via body mirror)")

    # ==============================================================
    #  4. INTERLOCKING TENON NOTCHES
    # ==============================================================
    # Front/back aprons: center-half notch (remove center mt_tw/2)
    # Side aprons: top+bottom quarter notch (remove top+bottom mt_tw/4)

    # -- Back apron center notches (left + right tenons) --
    ba_notch_pl = sp.off_plane(apron_c, apron_c.xZConstructionPlane,
        "table_w - apron_thick / 2 - mt_tt / 2", "BA_NotchPl")
    # Left tenon
    _, pr = sp.sketch_rect_model(apron_c, ba_notch_pl,
        ("leg_size - mt_td",
         "table_w - apron_thick / 2 - mt_tt / 2",
         "apron_z + apron_h / 2 - mt_tw / 4"),
        {"x": "notch_d", "z": "mt_tw / 2"},
        "BA_LNotch_Sk", ev)
    sp.ext_op(apron_c, pr, "mt_tt", CUT, apron_back, "BA_LNotch")
    # Right tenon
    _, pr = sp.sketch_rect_model(apron_c, ba_notch_pl,
        ("table_l - leg_size + mt_td - notch_d",
         "table_w - apron_thick / 2 - mt_tt / 2",
         "apron_z + apron_h / 2 - mt_tw / 4"),
        {"x": "notch_d", "z": "mt_tw / 2"},
        "BA_RNotch_Sk", ev)
    sp.ext_op(apron_c, pr, "mt_tt", CUT, apron_back, "BA_RNotch")

    # -- Front apron center notches (left + right tenons) --
    fa_notch_pl = sp.off_plane(apron_c, apron_c.xZConstructionPlane,
        "apron_thick / 2 - mt_tt / 2", "FA_NotchPl")
    # Left tenon
    _, pr = sp.sketch_rect_model(apron_c, fa_notch_pl,
        ("leg_size - mt_td",
         "apron_thick / 2 - mt_tt / 2",
         "apron_z + apron_h / 2 - mt_tw / 4"),
        {"x": "notch_d", "z": "mt_tw / 2"},
        "FA_LNotch_Sk", ev)
    sp.ext_op(apron_c, pr, "mt_tt", CUT, apron_front, "FA_LNotch")
    # Right tenon
    _, pr = sp.sketch_rect_model(apron_c, fa_notch_pl,
        ("table_l - leg_size + mt_td - notch_d",
         "apron_thick / 2 - mt_tt / 2",
         "apron_z + apron_h / 2 - mt_tw / 4"),
        {"x": "notch_d", "z": "mt_tw / 2"},
        "FA_RNotch_Sk", ev)
    sp.ext_op(apron_c, pr, "mt_tt", CUT, apron_front, "FA_RNotch")

    # -- Left side apron top+bottom notches (front + back tenons) --
    la_notch_pl = sp.off_plane(apron_c, apron_c.yZConstructionPlane,
        "apron_thick / 2 - mt_tt / 2", "LA_NotchPl")

    for y_start, sfx in [("leg_size - mt_td", "F"),
                          ("table_w - leg_size + mt_td - notch_d", "B")]:
        # Top notch
        _, pr = sp.sketch_rect_model(apron_c, la_notch_pl,
            ("apron_thick / 2 - mt_tt / 2",
             y_start,
             "apron_z + apron_h / 2 + mt_tw / 4"),
            {"y": "notch_d", "z": "mt_tw / 4"},
            f"LA_{sfx}NotchT_Sk", ev)
        sp.ext_op(apron_c, pr, "mt_tt", CUT, apron_left,
                  f"LA_{sfx}NotchT")
        # Bottom notch
        _, pr = sp.sketch_rect_model(apron_c, la_notch_pl,
            ("apron_thick / 2 - mt_tt / 2",
             y_start,
             "apron_z + apron_h / 2 - mt_tw / 2"),
            {"y": "notch_d", "z": "mt_tw / 4"},
            f"LA_{sfx}NotchB_Sk", ev)
        sp.ext_op(apron_c, pr, "mt_tt", CUT, apron_left,
                  f"LA_{sfx}NotchB")

    print(">>> Notches: 8 CUTs (2 back, 2 front, 4 left)")

    # -- Mirror left side apron → right (notches + tenons included) --
    apron_right = sp.mirror_body(apron_c, apron_left, a_xmid,
        "RightApronMir").bodies.item(0)
    apron_right.name = "Apron_Right"

    print(">>> Aprons: 4 bodies complete")

    # ==============================================================
    #  5. CROSS-COMPONENT CUTs — aprons CUT mortises into legs
    # ==============================================================
    # Assembly proxies for root-level combine
    ba_proxy = apron_back.createForAssemblyContext(apron_occ)
    fa_proxy = apron_front.createForAssemblyContext(apron_occ)
    la_proxy = apron_left.createForAssemblyContext(apron_occ)
    ra_proxy = apron_right.createForAssemblyContext(apron_occ)

    fl_proxy = leg_fl.createForAssemblyContext(leg_occ)
    fr_proxy = leg_fr.createForAssemblyContext(leg_occ)
    bl_proxy = leg_bl.createForAssemblyContext(leg_occ)
    br_proxy = leg_br.createForAssemblyContext(leg_occ)

    mt.bulk_cut_mortises(root, fl_proxy, [fa_proxy, la_proxy], "Mortise_FL")
    mt.bulk_cut_mortises(root, fr_proxy, [fa_proxy, ra_proxy], "Mortise_FR")
    mt.bulk_cut_mortises(root, bl_proxy, [ba_proxy, la_proxy], "Mortise_BL")
    mt.bulk_cut_mortises(root, br_proxy, [ba_proxy, ra_proxy], "Mortise_BR")

    print(">>> Mortises: 4 legs CUT")

    # ==============================================================
    #  6. TOP
    # ==============================================================
    top_pl = sp.off_plane(top_c, top_c.xYConstructionPlane, "leg_h", "Top_Pl")
    _, pr = sp.sketch_rect_model(top_c, top_pl,
        ("0 in", "0 in", "leg_h"),
        {"x": "table_l", "y": "table_w"},
        "Top_Sk", ev)
    top_body = sp.ext_new(top_c, pr, "top_thick", "TopBoard").bodies.item(0)
    top_body.name = "Top"

    print(">>> Top: 1 body")

    # ==============================================================
    #  7. DRAWER — dovetailed box + bar pull
    # ==============================================================
    dd_result = dovetailed_drawer.build(drawer_c, prefix="dd", ev=ev)
    dd_front = dd_result["front"]

    # Install 3" bar pull on drawer front face
    pull.install(drawer_c, dd_front, drawer_c.xZConstructionPlane,
        center=("leg_size + drawer_gap + drawer_w / 2", "0 in",
                "apron_z + drawer_gap + drawer_h / 2"),
        pull_axis="x", depth_axis="y",
        prefix="pl", name="Pull", ev=ev, flip=False,
        board_thick_expr="dd_ft")

    print(">>> Drawer: %d bodies + pull" % len(dd_result["all_bodies"]))

    # ==============================================================
    #  8. DETAILS — leg chamfers + top fillet
    # ==============================================================
    # Leg bottom chamfers
    for leg_body in [leg_fl, leg_fr, leg_bl, leg_br]:
        bot_face = sp.find_face(leg_body, "z", -1)
        if bot_face is None:
            continue
        edge_coll = adsk.core.ObjectCollection.create()
        seen = set()
        for ei in range(bot_face.edges.count):
            e = bot_face.edges.item(ei)
            if e.tempId not in seen:
                seen.add(e.tempId)
                edge_coll.add(e)
        if edge_coll.count == 0:
            continue
        ch_inp = leg_c.features.chamferFeatures.createInput2()
        ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
            edge_coll, VI("leg_ch"), True)
        ch = leg_c.features.chamferFeatures.add(ch_inp)
        ch.name = f"{leg_body.name}_Ch"

    # Top edge fillet (perimeter edges of top face)
    top_face = sp.find_face(top_body, "z", +1)
    if top_face:
        edge_coll = adsk.core.ObjectCollection.create()
        seen = set()
        for ei in range(top_face.edges.count):
            e = top_face.edges.item(ei)
            if e.tempId not in seen:
                seen.add(e.tempId)
                edge_coll.add(e)
        if edge_coll.count > 0:
            fil_inp = top_c.features.filletFeatures.createInput()
            fil_inp.addConstantRadiusEdgeSet(edge_coll,
                VI("top_fil"), True)
            fil = top_c.features.filletFeatures.add(fil_inp)
            fil.name = "Top_Fillet"

    print(">>> Details: leg chamfers + top fillet")

    # ==============================================================
    #  EPILOGUE
    # ==============================================================
    # Hide construction geometry
    for comp in [leg_c, apron_c, top_c, drawer_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False
    for sk in root.sketches:
        sk.isVisible = False
    for cp in root.constructionPlanes:
        cp.isLightBulbOn = False

    # Print body inventory
    for comp_name, c in [("Legs", leg_c), ("Aprons", apron_c),
                          ("Top", top_c), ("Drawer", drawer_c)]:
        names = [c.bRepBodies.item(i).name
                 for i in range(c.bRepBodies.count)]
        print(f"{comp_name}: {len(names)} bodies -> {names}")

    # Appearances
    sp.apply_appearance("walnut")
    sp.apply_appearance("spalted maple", bodies=["dd_Front"])

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
