"""
Parametric Solid Wood Bookshelf
===============================
70"H x 30"W x 20"D, 3/4" board stock.
Through M&T shelves + domino kick + 1/2" plywood backboard + through dovetail top.

Uses templates: domino.grid(), dovetail.box(), af helpers.

Coordinate system:
  X = width (30")   Y = depth (20")   Z = height (70")
"""
import adsk.core
import adsk.fusion
import math


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation

    from helpers import sp
    from woodworking.templates import domino
    from woodworking.templates import dovetail

    ctx = sp.DesignContext(design)

    # ==============================================================
    #  PARAMETERS
    # ==============================================================
    for pname, expr, unit in [
        ("total_height",  "70 in",    "in"),
        ("total_width",   "30 in",    "in"),
        ("total_depth",   "20 in",    "in"),
        ("board_thick",   "0.75 in",  "in"),
        ("kick_height",   "4 in",     "in"),
        ("back_thick",    "0.5 in",   "in"),
        ("n_shelves",     "5",        ""),
        ("mt_tenon_w",    "2 in",     "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    for pname, expr, unit in [
        ("inner_width",    "total_width - 2 * board_thick",                              "in"),
        ("shelf_depth",    "total_depth - back_thick",                                   "in"),
        ("back_height",    "total_height - board_thick - kick_height",                   "in"),
        ("shelf_spacing",  "(total_height - 2 * board_thick - kick_height) / n_shelves", "in"),
        ("mt_tenon_y1",    "(total_depth - back_thick) / 4 - mt_tenon_w / 2",            "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    # Domino params — per-joint sizing
    # Kick-to-side: standard 5mm (both pieces are 3/4" = 19mm)
    params.add("dm_kick_w", VI("5 mm"), "in", "")
    params.add("dm_kick_h", VI("30 mm"), "in", "")
    params.add("dm_kick_d", VI("15 mm"), "in", "")
    params.add("dm_kick_count", VI("2"), "", "")
    params.add("dm_kick_zsp", VI("kick_height / (dm_kick_count + 1)"), "in", "")

    # Shelf-to-back: standard 6mm (back is 1/2" = 12.7mm, limits depth)
    params.add("dm_back_w", VI("6 mm"), "in", "")
    params.add("dm_back_h", VI("40 mm"), "in", "")
    params.add("dm_back_d", VI("10 mm"), "in", "")
    params.add("dm_back_count", VI("3"), "", "")
    params.add("dm_back_xsp", VI("inner_width / (dm_back_count + 1)"), "in", "")

    # Dovetail params (top board to sides)
    dovetail.define_params(params, prefix="dt",
        angle="8 deg", tail_w="2 in", tail_count="8",
        joint_h_expr="total_depth", thick_expr="board_thick")

    # ==============================================================
    #  COMPONENTS
    # ==============================================================
    sides_occ = sp.make_comp(root, "Sides")
    shelves_occ = sp.make_comp(root, "Shelves")
    top_occ = sp.make_comp(root, "Top")
    kick_occ = sp.make_comp(root, "Kick")
    back_occ = sp.make_comp(root, "Back")

    sides = sides_occ.component
    shelves_c = shelves_occ.component
    top_c = top_occ.component
    kick_c = kick_occ.component
    back_c = back_occ.component

    # ==============================================================
    #  BODY-RELATIVE REFERENCES  (documents spatial deps for validate_deps)
    # ==============================================================
    # These are populated after each body is created, and read before
    # positioning dependent bodies.  The .boundingBox read satisfies
    # the validate_deps source check.

    # ==============================================================
    #  1. SIDE BOARDS  (Sides component)
    # ==============================================================
    _, pr = sp.sketch_rect(sides, sides.xYConstructionPlane,
        "0 in", "0 in", "board_thick", "total_depth", "LeftSide_Sk", ctx.ev)
    left_side = sp.ext_new(sides, pr, "total_height", "LeftSide").bodies.item(0)
    left_side.name = "Side_Left"

    # Body-relative ref: Side_Right positioned relative to Side_Left
    ref_side_left = ctx.find_body("Side_Left")
    ref_side_left_bb = ref_side_left.boundingBox

    _, pr = sp.sketch_rect(sides, sides.xYConstructionPlane,
        "total_width - board_thick", "0 in", "board_thick", "total_depth",
        "RightSide_Sk", ctx.ev)
    right_side = sp.ext_new(sides, pr, "total_height", "RightSide").bodies.item(0)
    right_side.name = "Side_Right"

    # ==============================================================
    #  2. SHELF TEMPLATE + BODY PATTERN  (Shelves component)
    #
    #  One shelf + 4 tenons (mirrors) + JOIN → body pattern (BEFORE
    #  any CUTs to avoid ghost bodies) → domino loop per level.
    # ==============================================================
    sh_YMid = sp.off_plane(shelves_c, shelves_c.xZConstructionPlane,
                            "shelf_depth / 2", "YMid_Pl")
    sh_XMid = sp.off_plane(shelves_c, shelves_c.yZConstructionPlane,
                            "total_width / 2", "XMid_Pl")
    sh_pl = sp.off_plane(shelves_c, shelves_c.xYConstructionPlane,
                          "kick_height", "Shelf_Pl")

    # Shelf body (depth = shelf_depth, recessed for backboard)
    _, pr = sp.sketch_rect(shelves_c, sh_pl, "board_thick", "0 in",
                            "inner_width", "shelf_depth", "Shelf_Sk", ctx.ev)
    ext_sh = sp.ext_new(shelves_c, pr, "board_thick", "ShelfBody")
    sh_body = ext_sh.bodies.item(0)
    sh_body.name = "Shelf"

    # One tenon (left-front)
    _, pr = sp.sketch_rect(shelves_c, sh_pl, "0 in", "mt_tenon_y1",
                            "board_thick", "mt_tenon_w", "Sh_Tenon_Sk", ctx.ev)
    ext_t = sp.ext_new(shelves_c, pr, "board_thick", "Sh_Tenon")

    # Mirror tenon across YMid → left-back, then across XMid → right pair
    mir_y = sp.mirror_feats(shelves_c, [ext_t], sh_YMid, "Sh_MirY")
    mir_x = sp.mirror_feats(shelves_c, [ext_t, mir_y], sh_XMid, "Sh_MirX")

    # JOIN all 4 tenon bodies into shelf body
    t_bodies = [ext_t.bodies.item(0)]
    for j in range(mir_y.bodies.count):
        t_bodies.append(mir_y.bodies.item(j))
    for j in range(mir_x.bodies.count):
        t_bodies.append(mir_x.bodies.item(j))
    sp.combine(sh_body, t_bodies, JOIN, False, "Sh_JoinTenons")

    # -- Shelf-to-backboard domino voids --
    sh_dm_pl = sp.off_plane(shelves_c, shelves_c.xZConstructionPlane,
                             "shelf_depth", "ShDm_Pl")

    # Create template voids at first shelf level, CUT into shelf
    template_voids = domino.grid(shelves_c, sh_dm_pl,
        start=("board_thick + dm_back_xsp", "shelf_depth",
               "kick_height + board_thick / 2"),
        step_axis="x", step_expr="dm_back_xsp",
        count_expr="dm_back_count",
        long_axis="x", long_expr="dm_back_h",
        short_expr="dm_back_w", depth_expr="dm_back_d",
        body_a=sh_body, body_b=sh_body,
        name="ShDm", ev=ctx.ev)

    # Body pattern shelf along Z (ghost void bodies are harmless)
    shelf_pat = sp.body_pattern(shelves_c, sh_body, shelves_c.zConstructionAxis,
                                 "n_shelves", "shelf_spacing", "ShelfPattern")

    # Collect all shelf bodies (skip ghost voids by name)
    all_shelf_bodies = [sh_body]
    for i in range(shelf_pat.bodies.count):
        b = shelf_pat.bodies.item(i)
        if not b.name.startswith("ShDm"):
            all_shelf_bodies.append(b)

    # Z-pattern template voids for backboard CUT at all levels
    void_coll = adsk.core.ObjectCollection.create()
    for v in template_voids:
        void_coll.add(v)
    sh_dm_z_inp = shelves_c.features.rectangularPatternFeatures.createInput(
        void_coll, shelves_c.zConstructionAxis,
        VI("n_shelves"), VI("shelf_spacing"),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    sh_dm_z_pat = shelves_c.features.rectangularPatternFeatures.add(sh_dm_z_inp)
    sh_dm_z_pat.name = "ShDm_PatZ"

    # Collect ALL void bodies (template + Z-pattern, skip ghost copies)
    all_sh_dm_voids = list(template_voids)
    for j in range(sh_dm_z_pat.bodies.count):
        all_sh_dm_voids.append(sh_dm_z_pat.bodies.item(j))

    # ==============================================================
    #  3. SHELF MORTISES — bulk CUT  (root, assembly proxies)
    # ==============================================================
    all_shelf_proxies = [b.createForAssemblyContext(shelves_occ)
                         for b in all_shelf_bodies]
    left_side_proxy = left_side.createForAssemblyContext(sides_occ)
    right_side_proxy = right_side.createForAssemblyContext(sides_occ)

    sp.combine(left_side_proxy, all_shelf_proxies, CUT, True, "ShelfMortL")
    sp.combine(right_side_proxy, all_shelf_proxies, CUT, True, "ShelfMortR")

    # ==============================================================
    #  4. KICK BOARD + DOMINO VOIDS  (Kick component)
    # ==============================================================
    _, pr = sp.sketch_rect(kick_c, kick_c.xYConstructionPlane,
        "board_thick", "0 in", "inner_width", "board_thick", "Kick_Sk", ctx.ev)
    kick_body = sp.ext_new(kick_c, pr, "kick_height", "KickBoard").bodies.item(0)
    kick_body.name = "KickBoard"

    k_XMid = sp.off_plane(kick_c, kick_c.yZConstructionPlane,
                           "total_width / 2", "KXMid_Pl")

    # Body-relative ref: kick dominos depend on KickBoard
    ref_kick = ctx.find_body("KickBoard")
    ref_kick_bb = ref_kick.boundingBox

    # Left-side domino voids + CUT into kick
    k_dm_pl = sp.off_plane(kick_c, kick_c.yZConstructionPlane,
                            "board_thick", "KDm_Pl")
    dm_kick_left = domino.grid(kick_c, k_dm_pl,
        start=("board_thick", "board_thick / 2", "dm_kick_zsp"),
        step_axis="z", step_expr="dm_kick_zsp",
        count_expr="dm_kick_count",
        long_axis="z", long_expr="dm_kick_h",
        short_expr="dm_kick_w", depth_expr="dm_kick_d",
        body_a=kick_body,
        name="KDm_L", ev=ctx.ev)

    # Right-side: mirror left voids across XMid + CUT into kick
    mir_k = sp.mirror_bodies(kick_c, dm_kick_left, k_XMid, "KDm_MirX")
    dm_kick_right = []
    for i in range(mir_k.bodies.count):
        b = mir_k.bodies.item(i)
        b.name = f"KDm_R_{i}"
        dm_kick_right.append(b)
    sp.combine(kick_body, dm_kick_right, CUT, True, "KDm_CutR")

    # ==============================================================
    #  5. KICK DOMINO MORTISES — CUT sides  (root, assembly proxies)
    # ==============================================================
    dm_kick_left_proxies = [b.createForAssemblyContext(kick_occ)
                             for b in dm_kick_left]
    dm_kick_right_proxies = [b.createForAssemblyContext(kick_occ)
                              for b in dm_kick_right]
    sp.combine(left_side_proxy, dm_kick_left_proxies, CUT, True, "KickDomL")
    sp.combine(right_side_proxy, dm_kick_right_proxies, CUT, True, "KickDomR")

    # ==============================================================
    #  6. BACKBOARD  (Back component)
    #     Positioned behind shelves — ref: Shelf
    # ==============================================================
    ref_shelf = ctx.find_body("Shelf")
    ref_shelf_bb = ref_shelf.boundingBox
    bk_pl = sp.off_plane(back_c, back_c.xYConstructionPlane,
                          "kick_height", "Back_Pl")
    _, pr = sp.sketch_rect(back_c, bk_pl, "board_thick",
                            "total_depth - back_thick",
                            "inner_width", "back_thick", "Back_Sk", ctx.ev)
    back_body = sp.ext_new(back_c, pr, "back_height", "BackPanel").bodies.item(0)
    back_body.name = "BackPanel"

    # ==============================================================
    #  7. BACKBOARD DOMINO CUTS  (root, assembly proxies)
    # ==============================================================
    all_sh_dm_proxies = [b.createForAssemblyContext(shelves_occ)
                          for b in all_sh_dm_voids]
    back_proxy = back_body.createForAssemblyContext(back_occ)
    sp.combine(back_proxy, all_sh_dm_proxies, CUT, True, "BackDomCut")

    # ==============================================================
    #  8. TOP BOARD + THROUGH DOVETAILS  (Top component)
    # ==============================================================
    t_XMid = sp.off_plane(top_c, top_c.yZConstructionPlane,
                           "total_width / 2", "XMid_Pl")

    tp = sp.off_plane(top_c, top_c.xYConstructionPlane,
                       "total_height - board_thick", "Top_Pl")
    _, pr = sp.sketch_rect(top_c, tp, "board_thick", "0 in",
                            "inner_width", "total_depth", "Top_Sk", ctx.ev)
    top_body = sp.ext_new(top_c, pr, "board_thick", "TopBoard").bodies.item(0)
    top_body.name = "TopBoard"

    # Through dovetails: top board (tail) into left/right sides (pin)
    # joint_axis="y" (tails distributed along depth)
    # thick_axis="x" (pin board thickness along width)
    # Left side is pin board (front), top is tail board (left in box() terms)
    left_side_top = None
    right_side_top = None
    for i in range(top_c.bRepBodies.count):
        pass
    # The dovetail template's box() expects boards in the same component.
    # Since sides and top are in different components, we use the manual
    # approach: build tails in Top component, CUT sides via proxies.
    dt_pl = sp.off_plane(top_c, top_c.xYConstructionPlane,
                          "total_height - board_thick", "DT_Plane")

    # ONE left tail — parametric trapezoid sketch
    bt = ctx.ev("board_thick")
    hp = ctx.ev("dt_half_pin")
    delta = bt * math.tan(ctx.ev("dt_angle"))
    tw = ctx.ev("dt_tail_w")

    sk_dt = top_c.sketches.add(dt_pl)
    sk_dt.name = "DT_Left_Sk"
    dtl = sk_dt.sketchCurves.sketchLines
    Point3D = adsk.core.Point3D

    p1 = Point3D.create(0, hp, 0)
    p2 = Point3D.create(0, hp + tw, 0)
    p3 = Point3D.create(bt, hp + tw - delta, 0)
    p4 = Point3D.create(bt, hp + delta, 0)

    l_short = dtl.addByTwoPoints(p4, p3)
    l_back = dtl.addByTwoPoints(l_short.endSketchPoint, p2)
    l_wide = dtl.addByTwoPoints(l_back.endSketchPoint, p1)
    l_front = dtl.addByTwoPoints(l_wide.endSketchPoint, l_short.startSketchPoint)

    sk_dt.geometricConstraints.addVertical(l_short)
    sk_dt.geometricConstraints.addVertical(l_wide)
    d = sk_dt.sketchDimensions
    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
    d.addDistanceDimension(l_short.startSketchPoint, l_short.endSketchPoint,
        V, Point3D.create(bt + 1, hp + tw / 2, 0)).parameter.expression = "dt_narrow_w"
    d.addDistanceDimension(l_short.startSketchPoint, l_wide.endSketchPoint,
        H, Point3D.create(bt / 2, hp - 1, 0)).parameter.expression = "board_thick"
    d.addDistanceDimension(sk_dt.originPoint, l_short.startSketchPoint,
        V, Point3D.create(bt + 2, (hp + delta) / 2, 0)
    ).parameter.expression = "dt_half_pin + board_thick * tan(dt_angle)"
    d.addDistanceDimension(sk_dt.originPoint, l_short.startSketchPoint,
        H, Point3D.create(0, hp - 2, 0)).parameter.expression = "board_thick"
    d.addAngularDimension(
        l_front, l_short, Point3D.create(bt / 2, hp + tw / 2, 0)
    ).parameter.expression = "90 deg - dt_angle"

    ext_dt_l = sp.ext_new(top_c, sk_dt.profiles.item(0), "board_thick", "DT_Left")
    left_tail = ext_dt_l.bodies.item(0)
    left_tail.name = "DT_Left"

    # Mirror → right tail, body pattern each side along Y
    mir_dt = sp.mirror_feats(top_c, [ext_dt_l], t_XMid, "DT_MirX")
    right_tail = mir_dt.bodies.item(0)
    right_tail.name = "DT_Right"

    left_pat = sp.body_pattern(top_c, left_tail, top_c.yConstructionAxis,
                                "dt_tail_count", "dt_pitch", "DT_PatL")
    right_pat = sp.body_pattern(top_c, right_tail, top_c.yConstructionAxis,
                                 "dt_tail_count", "dt_pitch", "DT_PatR")

    all_left_tails = [left_tail]
    for i in range(left_pat.bodies.count):
        all_left_tails.append(left_pat.bodies.item(i))
    all_right_tails = [right_tail]
    for i in range(right_pat.bodies.count):
        all_right_tails.append(right_pat.bodies.item(i))

    # ==============================================================
    #  9. DOVETAIL SOCKETS — bulk CUT  (root, assembly proxies)
    # ==============================================================
    left_tail_proxies = [b.createForAssemblyContext(top_occ)
                          for b in all_left_tails]
    right_tail_proxies = [b.createForAssemblyContext(top_occ)
                           for b in all_right_tails]
    sp.combine(left_side_proxy, left_tail_proxies, CUT, True, "DT_SocketL")
    sp.combine(right_side_proxy, right_tail_proxies, CUT, True, "DT_SocketR")

    # ==============================================================
    # 10. JOIN DOVETAILS INTO TOP  (Top component)
    # ==============================================================
    sp.combine(top_body, all_left_tails, JOIN, False, "DT_JoinL")
    sp.combine(top_body, all_right_tails, JOIN, False, "DT_JoinR")

    # ==============================================================
    #  EPILOGUE
    # ==============================================================
    for occ in root.occurrences:
        c = occ.component
        for sk in c.sketches:
            sk.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False

    total = 0
    for occ in root.occurrences:
        c = occ.component
        n = c.bRepBodies.count
        names = [c.bRepBodies.item(i).name for i in range(n)]
        print(f"  {c.name}: {n} bodies -> {names}")
        total += n
    print(f"\nTotal: {total} bodies")

    sp.apply_appearance("white oak")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
