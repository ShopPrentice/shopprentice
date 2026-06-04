"""
Wall Shelf — inspired by Becksvoort's "Modern Wall Shelf" (Fine Woodworking #284)
================================================================================
An interpretation, not an exact reproduction.
Asymmetric Shaker wall shelf: two vertical uprights + two long horizontal
shelves joined with dadoed cross-laps, plus two suspended drawers.

Coordinate system:
  X = length   (wall runs left->right)
  Y = depth    (Y=0 FRONT / viewer side, Y=part_d back / wall side)
  Z = height   (Z=0 bottom of uprights)

Layout (drawing p.32):
  Uprights : 3/4" x 8.5" x 15", centers at X = 6" and 39" (33" on center)
  Shelves  : 3/4" x 8.5" x 42", offset opposite directions
             bottom shelf X[0,42], top shelf X[3,45]
             bottom shelf bottom face Z=2 (upright drops 2" below)
             6" clear gap between shelves -> top shelf bottom face Z=8.75

Cross-lap joint (p.34-35) — at each of the 4 crossings:
  FRONT half (Y[0,half_d]):
    * upright stays full, but gets a 1/8"-deep DADO on BOTH faces -> leaves a
      1/2"-thick central tongue.
    * shelf gets a 1/2"-wide SLOT (front-facing opening) that rides the tongue;
      the shelf shoulders (1/8" each side) seat INTO the upright dadoes ->
      mechanical support + alignment.
  BACK half (Y[half_d,part_d]):
    * upright is fully notched away (3/4" slot); the shelf passes through it.

Drawers (two approaches, p.36-38), fronts on the Y=0 side:
  Top drawer    : hangs from a tongued cleat under the top shelf.
  Bottom drawer : straddles a beveled center cleat on the bottom shelf.
"""
import adsk.core, adsk.fusion
from helpers import sp
from woodworking.templates import dovetailed_drawer as ddt

CUT  = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
NEW  = adsk.fusion.FeatureOperations.NewBodyFeatureOperation


def run(context):
    ctx = sp.DesignContext()
    design = ctx.design
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = ctx.root
    params = ctx.params
    ev = ctx.ev
    VI = adsk.core.ValueInput.createByString
    P3 = adsk.core.Point3D

    # ==============================================================
    #  PARAMETERS
    # ==============================================================
    USER = [
        ("board_t", "0.75 in", "in"), ("part_d", "8.5 in", "in"),
        ("shelf_l", "42 in", "in"), ("upright_h", "15 in", "in"),
        ("up_spacing", "33 in", "in"), ("top_inset", "3 in", "in"),
        ("bot_inset", "6 in", "in"), ("up_below", "2 in", "in"),
        ("shelf_gap", "6 in", "in"), ("drawer_w", "10.5 in", "in"),
        ("drawer_d", "8 in", "in"), ("front_t", "0.75 in", "in"),
        ("side_t", "0.4375 in", "in"), ("bottom_t", "0.125 in", "in"),
        ("topdr_h", "2.4375 in", "in"), ("botdr_h", "3.4375 in", "in"),
        ("slot_w", "0.5 in", "in"),          # shelf front slot width (rides tongue)
    ]
    for n, e, u in USER:
        if not params.itemByName(n):
            params.add(n, VI(e), u, "")

    DERIVED = [
        ("clr", "0.0625 in", "in"),                   # running clearance (drawer gaps)
        ("half_d", "part_d / 2", "in"), ("lup_cx", "bot_inset", "in"),
        ("rup_cx", "lup_cx + up_spacing", "in"), ("xmid", "(lup_cx + rup_cx) / 2", "in"),
        ("bot_z", "up_below", "in"), ("top_z", "up_below + board_t + shelf_gap", "in"),
        ("top_x0", "lup_cx - top_inset", "in"), ("bot_x0", "lup_cx - bot_inset", "in"),
        ("dado_d", "(board_t - slot_w) / 2", "in"),   # upright dado depth = 1/8
        ("ch_rise", "board_t * 3 / 4", "in"),         # end chamfer: 3/4 of board width
        ("ch_run",  "board_t * 3 / 4", "in"),         # = ch_rise -> 45 deg
        ("gu", "0.25 in", "in"),                      # bottom-panel height = cleat-top height
        ("run_w", "0.5 in", "in"),                    # runner width / cleat side gap
        ("dr_right", "rup_cx - board_t / 2 - clr", "in"),
        ("dr_left", "dr_right - drawer_w", "in"), ("dr_cx", "dr_right - drawer_w / 2", "in"),
        ("dr_cy", "drawer_d / 2", "in"), ("dr_intw", "drawer_w - 2 * side_t", "in"),
        ("int_ylen", "drawer_d - side_t - front_t", "in"),  # interior depth front..back boards
        ("cleat_t", "0.5 in", "in"),
        ("cleat_wu", "drawer_d - front_t - side_t - 0.5 in", "in"),
        ("cg_d", "0.25 in", "in"), ("cg_w", "0.25 in", "in"),
        ("cg_zc", "top_z - cleat_t / 2", "in"), ("topdr_top", "top_z - clr", "in"),
        ("topdr_zbot", "topdr_top - topdr_h", "in"),
        ("bcz0", "bot_z + board_t", "in"),
        ("botdr_zbot", "bot_z + board_t + clr", "in"),
        ("bot_panel_z", "botdr_zbot + gu", "in"),
        ("bclw", "dr_intw - 2 * run_w", "in"),
        ("cleat_chf", "0.25 in", "in"),
        ("bcl_y0", "front_t + 0.5 in", "in"), ("bcl_ylen", "int_ylen - 1.0 in", "in"),
    ]
    for n, e, u in DERIVED:
        if not params.itemByName(n):
            params.add(n, VI(e), u, "")
    print(">>> Parameters done")

    # ---- generic axis-aligned box builder (XY sketch extruded in +Z) ----
    def build_box(comp, name, x0, sx, y0, sy, z0, sz):
        pl = sp.off_plane(comp, comp.xYConstructionPlane, z0, name + "_Pl")
        _, prf = sp.sketch_rect_model(comp, pl, (x0, y0, z0),
                                      {"x": sx, "y": sy}, name + "_Sk", ev)
        b = sp.ext_new(comp, prf, sz, name).bodies.item(0)
        b.name = name
        return b

    # ---- extrude an arbitrary polygon (model-space pts on a plane) ----
    def poly_body(comp, name, axis, at_expr, pts, ext_expr, op=NEW, target=None):
        base = {"x": comp.yZConstructionPlane, "y": comp.xZConstructionPlane,
                "z": comp.xYConstructionPlane}[axis]
        pl = sp.off_plane(comp, base, at_expr, name + "_Pl")
        sk = comp.sketches.add(pl)
        sps = [sk.modelToSketchSpace(p) for p in pts]
        L = sk.sketchCurves.sketchLines
        for i in range(len(sps)):
            L.addByTwoPoints(sps[i], sps[(i + 1) % len(sps)])
        ei = comp.features.extrudeFeatures.createInput(sk.profiles.item(0), op)
        ei.setDistanceExtent(False, VI(ext_expr))
        if target is not None:
            ei.participantBodies = [target]
        f = comp.features.extrudeFeatures.add(ei)
        f.name = name
        if op == NEW:
            b = f.bodies.item(0)
            b.name = name
            return b
        return None

    # ---- chamfer the long (Y-parallel) edges of a box at given X/Z ----
    def chamfer_y_edges(comp, body, x_targets, z_target, dist_expr, name):
        z_cm = ev(z_target)
        xs = [ev(x) for x in x_targets]
        edges = adsk.core.ObjectCollection.create()
        for i in range(body.edges.count):
            e = body.edges.item(i)
            g = e.geometry
            if not isinstance(g, adsk.core.Line3D):
                continue
            p0, p1 = g.startPoint, g.endPoint
            if abs(p1.x - p0.x) < 1e-4 and abs(p1.z - p0.z) < 1e-4 \
                    and abs(p1.y - p0.y) > 1e-3:
                mx, mz = (p0.x + p1.x) / 2, (p0.z + p1.z) / 2
                if abs(mz - z_cm) < 0.05 and any(abs(mx - xc) < 0.05 for xc in xs):
                    edges.add(e)
        if edges.count == 0:
            print("WARN: no chamfer edges for", name)
            return None
        inp = comp.features.chamferFeatures.createInput2()
        inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(edges, VI(dist_expr), False)
        f = comp.features.chamferFeatures.add(inp)
        f.name = name
        return f

    # ==============================================================
    #  COMPONENTS
    # ==============================================================
    up_occ = sp.make_comp(root, "Uprights")
    sh_occ = sp.make_comp(root, "Shelves")
    dt_occ = sp.make_comp(root, "DrawerTop")
    db_occ = sp.make_comp(root, "DrawerBot")
    cl_occ = sp.make_comp(root, "Cleats")
    up_c, sh_c, dt_c, db_c, cl_c = (o.component for o in
                                    (up_occ, sh_occ, dt_occ, db_occ, cl_occ))

    # ==============================================================
    #  1. UPRIGHTS
    # ==============================================================
    upl_pl = sp.off_plane(up_c, up_c.yZConstructionPlane,
                          "lup_cx - board_t / 2", "UpL_Pl")
    _, pr = sp.sketch_rect_model(up_c, upl_pl,
        ("lup_cx - board_t / 2", "0 in", "0 in"),
        {"y": "part_d", "z": "upright_h"}, "UpL_Sk", ev)
    upl = sp.ext_new(up_c, pr, "board_t", "UprightL").bodies.item(0)
    upl.name = "upright_L"
    xmid_pl = sp.off_plane(up_c, up_c.yZConstructionPlane, "xmid", "XMid_Pl")
    upr = sp.mirror_body(up_c, upl, xmid_pl, "UprightR_Mir").bodies.item(0)
    upr.name = "upright_R"
    print(">>> Uprights: 2 bodies")

    # ==============================================================
    #  2. SHELVES
    # ==============================================================
    bsh_pl = sp.off_plane(sh_c, sh_c.xYConstructionPlane, "bot_z", "BotSh_Pl")
    _, pr = sp.sketch_rect_model(sh_c, bsh_pl, ("bot_x0", "0 in", "bot_z"),
        {"x": "shelf_l", "y": "part_d"}, "BotSh_Sk", ev)
    bsh = sp.ext_new(sh_c, pr, "board_t", "BotShelf").bodies.item(0)
    bsh.name = "shelf_bottom"
    tsh_pl = sp.off_plane(sh_c, sh_c.xYConstructionPlane, "top_z", "TopSh_Pl")
    _, pr = sp.sketch_rect_model(sh_c, tsh_pl, ("top_x0", "0 in", "top_z"),
        {"x": "shelf_l", "y": "part_d"}, "TopSh_Sk", ev)
    tsh = sp.ext_new(sh_c, pr, "board_t", "TopShelf").bodies.item(0)
    tsh.name = "shelf_top"
    print(">>> Shelves: 2 bodies")

    # ==============================================================
    #  3. DADOED CROSS-LAP JOINTS  (4 crossings x 4 cuts)
    # ==============================================================
    def lap_joint(shelf, upright, xc, z, tag):
        # shelf front slot (1/2 wide), opening on the FRONT (Y=0)
        t = build_box(sh_c, tag + "_slotT", f"({xc}) - slot_w / 2", "slot_w",
                      "0 in", "half_d", z, "board_t")
        sp.combine(shelf, t, CUT, False, tag + "_slot")
        # upright back-half notch (full board thickness) -> shelf passes through
        t = build_box(up_c, tag + "_bnT", f"({xc}) - board_t / 2", "board_t",
                      "half_d", "half_d", z, "board_t")
        sp.combine(upright, t, CUT, False, tag + "_bn")
        # upright front dadoes on BOTH faces -> shelf shoulders seat in them
        t = build_box(up_c, tag + "_dlT", f"({xc}) - board_t / 2", "dado_d",
                      "0 in", "half_d", z, "board_t")
        sp.combine(upright, t, CUT, False, tag + "_dl")
        t = build_box(up_c, tag + "_drT", f"({xc}) + board_t / 2 - dado_d", "dado_d",
                      "0 in", "half_d", z, "board_t")
        sp.combine(upright, t, CUT, False, tag + "_dr")

    lap_joint(bsh, upl, "lup_cx", "bot_z", "LB")
    lap_joint(bsh, upr, "rup_cx", "bot_z", "RB")
    lap_joint(tsh, upl, "lup_cx", "top_z", "LT")
    lap_joint(tsh, upr, "rup_cx", "top_z", "RT")
    print(">>> Cross-lap joints: 16 cuts")

    # ==============================================================
    #  4. TOP DRAWER (dovetailed) + side grooves for cleat tongues
    #     half-blind dovetails at front, through dovetails at back.
    # ==============================================================
    ddt.define_params(params, prefix="td",
        drawer_w="drawer_w", drawer_d="drawer_d", drawer_h="topdr_h",
        front_thick="front_t", side_thick="side_t", bottom_thick="bottom_t",
        bg_up="gu",
        x_offset="dr_left", y_offset="0 in", z_offset="topdr_zbot",
        dt_tail_w="0.625 in", front_tail_count="3", back_tail_count="3")
    td = ddt.build(dt_c, prefix="td", ev=ev)
    tf, tsL, tsR = td["front"], td["left"], td["right"]
    # trim the bottom panel where dovetail tails intrude (clean corner notch)
    sp.combine(td["bottom"], [td["front"], td["back"], tsL, tsR], CUT, True, "TD_BotTrim")
    print(">>> Top drawer: dovetailed, 5 bodies")

    def cleat_groove(side_x0, name):
        pl = sp.off_plane(dt_c, dt_c.xYConstructionPlane, "cg_zc - cg_w / 2",
                          name + "_Pl")
        _, prf = sp.sketch_rect_model(dt_c, pl,
            (side_x0, "front_t", "cg_zc - cg_w / 2"),
            {"x": "cg_d", "y": "drawer_d - front_t - side_t"}, name + "_Sk", ev)
        return sp.ext_new(dt_c, prf, "cg_w", name + "_Tool").bodies.item(0)
    sp.combine(tsL, cleat_groove("dr_left + side_t - cg_d", "GrL"), CUT, False, "GrL_Cut")
    sp.combine(tsR, cleat_groove("dr_right - side_t", "GrR"), CUT, False, "GrR_Cut")
    # back relief: drop the back top below the (full-width) upper cleat so the
    # drawer slides out without the back hitting it; trims orphan side tails too.
    tdr = build_box(dt_c, "TD_BackRelief", "dr_left", "drawer_w",
                    "drawer_d - side_t - clr", "side_t + 2 * clr",
                    "top_z - cleat_t - clr", "cleat_t + board_t")
    sp.combine(td["back"], tdr, CUT, True, "TD_BackReliefB")
    sp.combine(tsL, tdr, CUT, True, "TD_BackReliefL")
    sp.combine(tsR, tdr, CUT, False, "TD_BackReliefR")
    print(">>> Top drawer cleat grooves + back relief cut")

    # ==============================================================
    #  5. UPPER CLEAT
    # ==============================================================
    cleat = build_box(cl_c, "cleat_upper", "dr_left + side_t", "dr_intw",
                      "dr_cy - cleat_wu / 2", "cleat_wu", "top_z - cleat_t", "cleat_t")
    tongL = build_box(cl_c, "cleat_tongueL", "dr_left + side_t - cg_d", "cg_d",
                      "dr_cy - cleat_wu / 2", "cleat_wu", "cg_zc - cg_w / 2", "cg_w")
    tongR = build_box(cl_c, "cleat_tongueR", "dr_right - side_t", "cg_d",
                      "dr_cy - cleat_wu / 2", "cleat_wu", "cg_zc - cg_w / 2", "cg_w")
    sp.combine(cleat, [tongL, tongR], JOIN, False, "CleatTongues")
    print(">>> Upper cleat: 1 body")

    # ==============================================================
    #  6. BOTTOM DRAWER (dovetailed) + beveled runners
    # ==============================================================
    ddt.define_params(params, prefix="bd",
        drawer_w="drawer_w", drawer_d="drawer_d", drawer_h="botdr_h",
        front_thick="front_t", side_thick="side_t", bottom_thick="bottom_t",
        bg_up="gu",
        x_offset="dr_left", y_offset="0 in", z_offset="botdr_zbot",
        dt_tail_w="0.625 in", front_tail_count="4", back_tail_count="4")
    bd = ddt.build(db_c, prefix="bd", ev=ev)
    bf = bd["front"]
    sp.combine(bd["bottom"], [bd["front"], bd["back"], bd["left"], bd["right"]],
               CUT, True, "BD_BotTrim")
    print(">>> Bottom drawer: dovetailed, 5 bodies")
    # Beveled runners: a quad whose top-inner edge is a 45 deg bevel that mates
    # the cleat's BOTTOM bevel (the runner hooks under the cleat overhang).
    chf = ev("cleat_chf")
    bcz = ev("bcz0")
    yf = ev("front_t")
    xwl = ev("dr_left + side_t");   xclL = ev("dr_cx - bclw / 2")
    xwr = ev("dr_right - side_t");  xclR = ev("dr_cx + bclw / 2")
    # runners stop short of the back (clr gap) so they don't butt the back board
    poly_body(db_c, "botdr_runnerL", "y", "front_t",
              [P3.create(xwl, yf, bcz), P3.create(xclL + chf, yf, bcz),
               P3.create(xclL, yf, bcz + chf), P3.create(xwl, yf, bcz + chf)],
              "int_ylen - clr")
    poly_body(db_c, "botdr_runnerR", "y", "front_t",
              [P3.create(xwr, yf, bcz), P3.create(xclR - chf, yf, bcz),
               P3.create(xclR, yf, bcz + chf), P3.create(xwr, yf, bcz + chf)],
              "int_ylen - clr")
    print(">>> Bottom drawer runners: 2 bodies")
    # back relief: central notch (cleat width) in the back's below-panel strip so
    # the back clears the center cleat. Central -> clear of the corner dovetails.
    bdr = build_box(db_c, "BD_BackRelief",
                    "dr_cx - bclw / 2 - clr", "bclw + 2 * clr",
                    "drawer_d - side_t - clr", "side_t + 2 * clr",
                    "botdr_zbot - board_t", "gu + board_t + clr")
    sp.combine(bd["back"], bdr, CUT, False, "BD_BackReliefCut")
    print(">>> Bottom drawer back relief cut")

    # ==============================================================
    #  7. LOWER CLEAT  (beveled on the DOWNSIDE; bevels mate the runners)
    # ==============================================================
    lcleat = build_box(cl_c, "cleat_lower", "dr_cx - bclw / 2", "bclw",
                       "bcl_y0", "bcl_ylen", "bcz0", "bot_panel_z - bcz0")
    chamfer_y_edges(cl_c, lcleat, ["dr_cx - bclw / 2", "dr_cx + bclw / 2"],
                    "bcz0", "cleat_chf", "LCleat_Ch")
    print(">>> Lower cleat: 1 body (bottom-beveled)")

    # ==============================================================
    #  8. CHAMFERED ENDS  (sharp ~18 deg rake: ch_rise up x ch_run along)
    #     Cut with explicit wedge tools for an exact, deterministic angle.
    #     Same chamfer on shelf ends (bottom) AND upright ends (top+bottom).
    # ==============================================================
    P3 = adsk.core.Point3D
    rise = ev("ch_rise")
    run = ev("ch_run")

    def wedge_cut(comp, target, name, axis, at_expr, pts):
        base = {"x": comp.yZConstructionPlane, "y": comp.xZConstructionPlane,
                "z": comp.xYConstructionPlane}[axis]
        ext_expr = {"x": "board_t", "y": "part_d"}[axis]
        pl = sp.off_plane(comp, base, at_expr, name + "_Pl")
        sk = comp.sketches.add(pl)
        m2s = sk.modelToSketchSpace
        sp_pts = [m2s(p) for p in pts]
        L = sk.sketchCurves.sketchLines
        L.addByTwoPoints(sp_pts[0], sp_pts[1])
        L.addByTwoPoints(sp_pts[1], sp_pts[2])
        L.addByTwoPoints(sp_pts[2], sp_pts[0])
        ei = comp.features.extrudeFeatures.createInput(sk.profiles.item(0), CUT)
        ei.setDistanceExtent(False, VI(ext_expr))
        ei.participantBodies = [target]
        comp.features.extrudeFeatures.add(ei).name = name

    # shelf ends (axis Y, full depth) — rake the bottom-end corner
    for shelf, x0p, zp, tag in [(bsh, "bot_x0", "bot_z", "B"), (tsh, "top_x0", "top_z", "T")]:
        xL, zb = ev(x0p), ev(zp)
        xR = xL + ev("shelf_l")
        wedge_cut(sh_c, shelf, "ChShL" + tag, "y", "0 in",
                  [P3.create(xL, 0, zb), P3.create(xL + run, 0, zb), P3.create(xL, 0, zb + rise)])
        wedge_cut(sh_c, shelf, "ChShR" + tag, "y", "0 in",
                  [P3.create(xR, 0, zb), P3.create(xR - run, 0, zb), P3.create(xR, 0, zb + rise)])

    # upright ends — chamfer the INNER edge (top & bottom), full depth (axis Y).
    # rise (0.5) across the thin top face in X; run (1.5) down the inner face in Z.
    bt = ev("board_t")
    uh = ev("upright_h")
    for upb, cxp, side in [(upl, "lup_cx", +1), (upr, "rup_cx", -1)]:
        x_in = ev(cxp) + side * bt / 2     # inner face X (+1 inner=+X, -1 inner=-X)
        s = -side                          # rake across the top toward the OUTER side
        wedge_cut(up_c, upb, "ChUp" + cxp + "Top", "y", "0 in",
                  [P3.create(x_in, 0, uh), P3.create(x_in + s * rise, 0, uh),
                   P3.create(x_in, 0, uh - run)])
        wedge_cut(up_c, upb, "ChUp" + cxp + "Bot", "y", "0 in",
                  [P3.create(x_in, 0, 0), P3.create(x_in + s * rise, 0, 0),
                   P3.create(x_in, 0, run)])
    print(">>> End chamfers: 4 shelf + 4 upright wedge cuts")

    # ==============================================================
    #  9. DRAWER PULLS  (river stones on 1/8" shafts; proud on FRONT, -Y)
    # ==============================================================
    P3 = adsk.core.Point3D
    IN = 2.54

    def make_stone(comp, name, cx, cy, cz, r):
        pl = sp.off_plane(comp, comp.xYConstructionPlane, f"{cz} cm", name + "_Pl")
        sk = comp.sketches.add(pl)
        m2s = sk.modelToSketchSpace
        a = m2s(P3.create(cx, cy - r, cz))
        b = m2s(P3.create(cx, cy + r, cz))
        mid = m2s(P3.create(cx + r, cy, cz))
        axis = sk.sketchCurves.sketchLines.addByTwoPoints(a, b)
        sk.sketchCurves.sketchArcs.addByThreePoints(a, mid, b)
        ri = comp.features.revolveFeatures.createInput(sk.profiles.item(0), axis, NEW)
        ri.setAngleExtent(False, VI("360 deg"))
        body = comp.features.revolveFeatures.add(ri).bodies.item(0)
        body.name = name
        return body

    def make_shaft(comp, name, cx, cy0, cylen, cz, r):
        pl = sp.off_plane(comp, comp.xZConstructionPlane, f"{cy0} cm", name + "_Pl")
        sk = comp.sketches.add(pl)
        c = sk.modelToSketchSpace(P3.create(cx, cy0, cz))
        sk.sketchCurves.sketchCircles.addByCenterRadius(c, r)
        ei = comp.features.extrudeFeatures.createInput(sk.profiles.item(0), NEW)
        ei.setDistanceExtent(False, VI(f"{cylen} cm"))
        body = comp.features.extrudeFeatures.add(ei).bodies.item(0)
        body.name = name
        return body

    dcx = ev("dr_cx")
    r_stone = 0.30 * IN            # smaller knob
    cy_stone = -0.20 * IN          # stone centre proud of the front face (Y=0)
    cy0 = -0.20 * IN               # shaft starts at the stone, extrudes +Y into front
    cylen = 0.375 * IN - cy0       # 3/8" embedded in the drawer front
    r_sh = 0.0625 * IN

    def make_pull(comp, name, front_body, cz):
        st = make_stone(comp, name + "_st", dcx, cy_stone, cz, r_stone)
        sh = make_shaft(comp, name + "_sh", dcx, cy0, cylen, cz, r_sh)
        sp.combine(st, sh, JOIN, False, name + "_join")
        sp.combine(front_body, st, CUT, True, name + "_drill")
        st.name = name

    make_pull(dt_c, "PULL_top", tf, ev("(topdr_zbot + topdr_top) / 2"))
    make_pull(db_c, "PULL_bot", bf, ev("botdr_zbot + botdr_h / 2"))
    print(">>> Drawer pulls: 2 stones")

    # ==============================================================
    #  EPILOGUE
    # ==============================================================
    for comp in [up_c, sh_c, dt_c, db_c, cl_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False

    for cname, c in [("Uprights", up_c), ("Shelves", sh_c), ("DrawerTop", dt_c),
                     ("DrawerBot", db_c), ("Cleats", cl_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{cname}: {len(names)} bodies -> {names}")

    # Appearance: cherry primary, pine secondary (drawer boxes), rosewood pulls.
    # apply_appearance(species, bodies=<list of body NAME strings>)
    sp.apply_appearance("cherry")
    sp.apply_appearance("pine",
        ["td_Left", "td_Right", "td_Back", "td_Bottom",
         "bd_Left", "bd_Right", "bd_Back", "bd_Bottom",
         "botdr_runnerL", "botdr_runnerR"])
    sp.apply_appearance("rosewood", ["PULL_top", "PULL_bot"])

    app = adsk.core.Application.get()
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
