import adsk.core, adsk.fusion
from helpers import sp

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation


def run(context):
    ctx = sp.DesignContext()
    app, design, root = ctx.app, ctx.design, ctx.root
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    params = design.userParameters
    ev = ctx.ev

    def P(name, expr, unit, comment=""):
        existing = params.itemByName(name)
        if existing:
            existing.expression = expr
            return existing
        return params.add(name, adsk.core.ValueInput.createByString(expr), unit, comment)

    VI = adsk.core.ValueInput.createByString

    def bpat(comp, bodies, axis, count, spacing, name):
        """Rectangular pattern of a LIST of bodies along an axis. Plain bodies only."""
        coll = adsk.core.ObjectCollection.create()
        if not isinstance(bodies, (list, tuple)):
            bodies = [bodies]
        for b in bodies:
            coll.add(b)
        inp = comp.features.rectangularPatternFeatures.createInput(
            coll, axis, VI(count), VI(spacing),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        inp.quantityTwo = VI("1")
        p = comp.features.rectangularPatternFeatures.add(inp)
        p.name = name
        return p

    # ============================================================
    # PARAMETERS
    # ============================================================
    P("post_size", "1.5625 in", "in", "Post cross-section (1-9/16 in sq)")
    P("post_len", "90 in", "in", "Post length")
    P("post_spacing", "36 in", "in", "Post center-to-center spacing (36 in max)")
    P("n_posts", "4", "", "Number of support posts")
    P("post_x0", "18 in", "in", "Leftmost post center X (positive space; = 72in-shelf overhang so left edge at X=0)")
    P("post_y", "4.5 in", "in", "Post center Y = mortise distance from back edge")
    P("peg_dia", "0.75 in", "in", "Peg / peg-hole diameter (3/4 in)")
    P("peg_first_z", "5.5 in", "in", "Lowest peg hole center Z (5-1/2 in from bottom)")
    P("peg_pitch", "2 in", "in", "Hole spacing within a trio (2 in on center)")
    P("trio_pitch", "12.5 in", "in", "Trio center-to-center spacing")
    P("n_trio", "7", "", "Number of hole trios per post")
    # Shelves
    P("shelf_thick", "0.875 in", "in", "Shelf board thickness (7/8 in)")
    P("sw_narrow", "7 in", "in", "Narrow shelf width")
    P("sw_med", "9 in", "in", "Medium shelf width")
    P("sw_wide", "11 in", "in", "Wide shelf width")
    P("sl_short", "72 in", "in", "Short shelf length (2 posts)")
    P("sl_long", "96 in", "in", "Long shelf length (3 posts)")
    P("over72", "(sl_short - post_spacing) / 2", "in", "72in-shelf overhang past outer mortise")
    P("over96", "(sl_long - 2 * post_spacing) / 2", "in", "96in-shelf overhang past outer mortise")
    # Pegs
    P("peg_actual_dia", "peg_dia - 0.015625 in", "in", "Peg dowel diameter (a hair undersize of the hole)")
    P("peg_len_long", "6 in", "in", "Long peg length (wider shelves)")
    P("peg_len_short", "4.5 in", "in", "Short peg length (narrow shelves)")
    # Details
    P("roundover", "0.25 in", "in", "1/4 in roundover (post corners + shelf top edges)")
    P("bevel_w", "1.25 in", "in", "Underbevel width (1-1/4 in)")
    P("bevel_h", "0.5 in", "in", "Underbevel height (1/2 in)")

    # ============================================================
    # COMPONENT: Posts
    # ref: origin (floor). Build one post + peg holes, pattern x4.
    # ============================================================
    posts_occ = sp.make_comp(root, "Posts")
    posts = posts_occ.component

    # --- Post body: square cross-section on floor, extrude up ---
    sk, prof = sp.sketch_rect_model(
        posts, posts.xYConstructionPlane,
        ("post_x0 - post_size / 2", "post_y - post_size / 2", "0 in"),
        {"x": "post_size", "y": "post_size"},
        "Post_Sk", ev=ev)
    post = sp.ext_new(posts, prof, "post_len", "PostBoard").bodies.item(0)
    post.name = "Post_0"

    # --- Pattern the post along X (x4) FIRST, while it has no cut history ---
    sp.body_pattern(posts, post, posts.xConstructionAxis,
                    "n_posts", "post_spacing", "Post_Pat")
    posts_bodies = [b for b in posts.bRepBodies
                    if (b.boundingBox.maxPoint.z - b.boundingBox.minPoint.z) > ev("post_len") * 0.5]

    # --- Peg-hole tool cylinder: circle on XZ plane (axis Y), extrude through ---
    hsk = posts.sketches.add(posts.xZConstructionPlane)
    cx, cz = ev("post_x0"), ev("peg_first_z")
    cen_sk = hsk.modelToSketchSpace(adsk.core.Point3D.create(cx, 0, cz))
    circ = hsk.sketchCurves.sketchCircles.addByCenterRadius(cen_sk, ev("peg_dia / 2"))
    d = hsk.sketchDimensions
    d.addRadialDimension(circ, adsk.core.Point3D.create(cen_sk.x + 1.0, cen_sk.y + 1.0, 0)
                         ).parameter.expression = "peg_dia / 2"
    orient = sp.probe_orientations(hsk, cx, 0, cz)
    d.addDistanceDimension(hsk.originPoint, circ.centerSketchPoint, orient['x'],
                           adsk.core.Point3D.create(cen_sk.x, cen_sk.y - 1.0, 0)
                           ).parameter.expression = "post_x0"
    d.addDistanceDimension(hsk.originPoint, circ.centerSketchPoint, orient['z'],
                           adsk.core.Point3D.create(cen_sk.x - 1.0, cen_sk.y, 0)
                           ).parameter.expression = "peg_first_z"
    cprof = sp.smallest_profile(hsk)
    # symmetric about XZ plane so the tool spans the post in Y regardless of normal sign
    cyl = sp.ext_new_sym(posts, cprof, "post_y + post_size", "PegToolSeed").bodies.item(0)
    cyl.name = "PegTool"

    # --- Pattern the tool into the full grid: trio (Z) -> trios (Z) -> posts (X) ---
    def small_cyls():
        return [b for b in posts.bRepBodies
                if (b.boundingBox.maxPoint.z - b.boundingBox.minPoint.z) < ev("post_len") * 0.5]
    bpat(posts, [cyl], posts.zConstructionAxis, "3", "peg_pitch", "Trio_Pat")
    bpat(posts, small_cyls(), posts.zConstructionAxis, "n_trio", "trio_pitch", "Trios_Pat")
    bpat(posts, small_cyls(), posts.xConstructionAxis, "n_posts", "post_spacing", "Posts_Pat")

    # --- Bulk-cut grouped tools into each post ---
    cyls = small_cyls()
    half = ev("post_size")
    for pb in posts_bodies:
        pcx = (pb.boundingBox.minPoint.x + pb.boundingBox.maxPoint.x) / 2.0
        tools = [c for c in cyls
                 if abs((c.boundingBox.minPoint.x + c.boundingBox.maxPoint.x) / 2.0 - pcx) < half]
        if tools:
            sp.combine(pb, tools, CUT, False, "PegHoles_" + pb.name)

    # ============================================================
    # COMPONENT: Shelves
    # ref: Posts. Through-mortises (snug = post cross-section) slide over posts.
    # 7 staggered shelves; each shelf's mortises are a Fusion pattern along X.
    # ============================================================
    shelves_occ = sp.make_comp(root, "Shelves")
    shelves = shelves_occ.component

    def build_shelf(name, x_left, length, width, zbot, post1x, n_mort):
        # board: rectangle on offset plane at z=zbot, extrude up shelf_thick
        pl = sp.off_plane(shelves, shelves.xYConstructionPlane, zbot, name + "_Pl")
        sk, prof = sp.sketch_rect_model(
            shelves, pl, (x_left, "0 in", zbot),
            {"x": length, "y": width}, name + "_Sk", ev=ev)
        board = sp.ext_new(shelves, prof, "shelf_thick", name + "Board").bodies.item(0)
        board.name = name
        # mortise tool: snug square prism through the board, patterned along X
        msk, mprof = sp.sketch_rect_model(
            shelves, pl,
            (post1x + " - post_size / 2", "post_y - post_size / 2", zbot),
            {"x": "post_size", "y": "post_size"}, name + "_MSk", ev=ev)
        sp.ext_new_sym(shelves, mprof, "shelf_thick + 0.5 in", name + "_MTool")
        psz = ev("post_size") * 2.0
        tools = [b for b in shelves.bRepBodies
                 if (b.boundingBox.maxPoint.x - b.boundingBox.minPoint.x) < psz]
        if n_mort > 1 and tools:
            bpat(shelves, tools, shelves.xConstructionAxis,
                 str(n_mort), "post_spacing", name + "_MPat")
            tools = [b for b in shelves.bRepBodies
                     if (b.boundingBox.maxPoint.x - b.boundingBox.minPoint.x) < psz]
        sp.combine(board, tools, CUT, False, name + "_Mortise")
        return board

    # spec: (name, first_post_idx, n_mort, width, length_is_long, height_idx)
    specs = [
        ("Shelf_1", 0, 2, "sw_wide",   False, 0),
        ("Shelf_2", 1, 3, "sw_narrow", True,  1),
        ("Shelf_3", 2, 2, "sw_med",    False, 2),
        ("Shelf_4", 0, 3, "sw_wide",   True,  3),
        ("Shelf_5", 0, 2, "sw_med",    False, 4),
        ("Shelf_6", 1, 3, "sw_narrow", True,  5),
        ("Shelf_7", 2, 2, "sw_med",    False, 6),
    ]
    for name, idx, n_mort, width, is_long, hi in specs:
        post1x = "post_x0 + %d * post_spacing" % idx
        if is_long:
            length = "sl_long"
            x_left = "%s - over96" % post1x
        else:
            length = "sl_short"
            x_left = "%s - over72" % post1x
        zbot = "peg_first_z + %d * trio_pitch + peg_dia / 2" % hi
        build_shelf(name, x_left, length, width, zbot, post1x, n_mort)

    # ============================================================
    # COMPONENT: Pegs
    # ref: Posts (dowel through peg hole) + Shelves (shelf rests on peg).
    # One peg per shelf-post intersection; patterned along X per shelf.
    # ============================================================
    pegs_occ = sp.make_comp(root, "Pegs")
    pegs = pegs_occ.component
    P3 = adsk.core.Point3D.create
    xz_ny = pegs.xZConstructionPlane.geometry.normal.y
    yexpr = "post_y" if xz_ny > 0 else "-1 * post_y"

    def build_pegs(name, post1x, peg_z, plen, n_peg):
        pl = sp.off_plane(pegs, pegs.xZConstructionPlane, yexpr, name + "_Pl")
        psk = pegs.sketches.add(pl)
        cxm, czm = ev(post1x), ev(peg_z)
        cen = psk.modelToSketchSpace(P3(cxm, ev("post_y"), czm))
        circ = psk.sketchCurves.sketchCircles.addByCenterRadius(cen, ev("peg_actual_dia / 2"))
        dd = psk.sketchDimensions
        dd.addRadialDimension(circ, P3(cen.x + 1.0, cen.y + 1.0, 0)
                              ).parameter.expression = "peg_actual_dia / 2"
        ori = sp.probe_orientations(psk, cxm, ev("post_y"), czm)
        dd.addDistanceDimension(psk.originPoint, circ.centerSketchPoint, ori['x'],
                                P3(cen.x, cen.y - 1.0, 0)).parameter.expression = post1x
        dd.addDistanceDimension(psk.originPoint, circ.centerSketchPoint, ori['z'],
                                P3(cen.x - 1.0, cen.y, 0)).parameter.expression = peg_z
        prof = sp.smallest_profile(psk)
        peg = sp.ext_new_sym(pegs, prof, plen + " / 2", name + "Seed").bodies.item(0)
        peg.name = name
        if n_peg > 1:
            bpat(pegs, [peg], pegs.xConstructionAxis, str(n_peg), "post_spacing", name + "_Pat")

    for name, idx, n_mort, width, is_long, hi in specs:
        post1x = "post_x0 + %d * post_spacing" % idx
        peg_z = "peg_first_z + %d * trio_pitch" % hi
        plen = "peg_len_short" if width == "sw_narrow" else "peg_len_long"
        build_pegs("Peg%d" % (hi + 1), post1x, peg_z, plen, n_mort)

    # ============================================================
    # DETAILS: roundovers + underbevels
    # ============================================================
    import adsk.core as _c

    def fillet_edges(comp, edges, r_expr, name):
        coll = adsk.core.ObjectCollection.create()
        for e in edges:
            coll.add(e)
        inp = comp.features.filletFeatures.createInput()
        inp.addConstantRadiusEdgeSet(coll, VI(r_expr), True)
        f = comp.features.filletFeatures.add(inp)
        f.name = name
        return f

    def chamfer2_edges(comp, edges, d1_expr, d2_expr, name):
        coll = adsk.core.ObjectCollection.create()
        for e in edges:
            coll.add(e)
        inp = comp.features.chamferFeatures.createInput2()
        inp.chamferEdgeSets.addTwoDistancesChamferEdgeSet(coll, VI(d1_expr), VI(d2_expr), False, False)
        f = comp.features.chamferFeatures.add(inp)
        f.name = name
        return f

    def vert_edges(body):
        out = []
        for e in body.edges:
            g = e.geometry
            if isinstance(g, _c.Line3D):
                p1 = e.startVertex.geometry
                p2 = e.endVertex.geometry
                if abs(p1.x - p2.x) < 0.01 and abs(p1.y - p2.y) < 0.01 and abs(p1.z - p2.z) > 1.0:
                    out.append(e)
        return out

    def horiz_perim_edges(body, z_target, min_len, exclude_back=False):
        out = []
        for e in body.edges:
            g = e.geometry
            if not isinstance(g, _c.Line3D):
                continue
            p1 = e.startVertex.geometry
            p2 = e.endVertex.geometry
            if abs(p1.z - z_target) < 0.05 and abs(p2.z - z_target) < 0.05:
                if p1.distanceTo(p2) > min_len:
                    if exclude_back and (p1.y + p2.y) / 2.0 < 0.5:
                        continue
                    out.append(e)
        return out

    # Post corner roundovers (4 vertical edges per post)
    pedges = []
    for pb in posts.bRepBodies:
        pedges += vert_edges(pb)
    fillet_edges(posts, pedges, "roundover", "PostRound")

    # Shelf bottom underbevels FIRST (chamfer changes topology), then re-find top edges
    minlen = ev("post_size") * 2.0
    bot_edges = []
    for b in shelves.bRepBodies:
        bot_edges += horiz_perim_edges(b, b.boundingBox.minPoint.z, minlen, exclude_back=True)
    n_bot = len(bot_edges)
    chamfer2_edges(shelves, bot_edges, "bevel_h", "bevel_w", "ShelfUnderbevel")
    # re-query top edges after the chamfer
    top_edges = []
    for b in shelves.bRepBodies:
        top_edges += horiz_perim_edges(b, b.boundingBox.maxPoint.z, minlen)
    fillet_edges(shelves, top_edges, "roundover", "ShelfTopRound")

    # ============================================================
    # Diagnostics
    # ============================================================
    print("posts:", len(posts_bodies), "shelves:", shelves.bRepBodies.count,
          "pegs:", pegs.bRepBodies.count)
    print("post vert edges filleted:", len(pedges),
          "shelf top edges:", len(top_edges), "shelf bottom edges:", n_bot)
