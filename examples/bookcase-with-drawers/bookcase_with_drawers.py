"""Bookcase with Drawers — FWW plan #SU94 (Taunton #065304), by Mike Korsak.
Figured maple case on a bubinga (sapele in-model) base; two bubinga drawers.

Overall: 60 in tall x 44-3/4 in wide (top) x 17-3/4 in deep (top).
Case: 39 x 13-1/4 x 51-1/4 on a 7-7/8 in curved-foot base.

Coordinates: X = width (0..39 at the case), Y = depth (0 = case front,
13.25 = case back), Z = height (0 = floor).

Joinery per plan:
- Bottom <-> sides: half-blind dovetails (11/16 tails, 1/8 lap)
- Shelves / drawer shelf <-> sides: sliding half-dovetails 5/16 deep x 3/4
- Stiles glued in 11/16 x 5/8 rabbets on side front edges (1/8 reveal w/
  stopped chamfer)
- Front rail <-> stiles, rear top rail <-> sides: slip tenons
- Dividers <-> drawer shelf: 3/16 x 5/8 splines; back: 5 splined boards
  (tongues into side/bottom/rail grooves)
- Base: aprons <-> feet paired slip tenons; stretcher housed in aprons;
  bead in rabbet; screw plates in rabbets
- Drawers: half-blind dovetail fronts, sliding-dovetail backs, grooved bottoms

Known simplifications (see README): foot miter splines omitted (45-degree
tilted interface — escalated to human review); brass tabs/screws omitted;
stretcher shortened to 12-3/16 to honor the 15/32 mortise; beads butted,
not mitered.
"""
import adsk.core, adsk.fusion, math
from helpers import sp
from woodworking.templates import half_blind_dovetail

CUT  = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
NEW  = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
P    = adsk.core.Point3D.create
VI   = adsk.core.ValueInput.createByString


def run(context):
    ctx = sp.DesignContext()
    app, design, root, params = ctx.app, ctx.design, ctx.root, ctx.params
    ev = ctx.ev

    def padd(name, expr, unit, comment=""):
        p = params.itemByName(name)
        if p is not None:
            try: p.expression = expr
            except Exception: pass
            return p
        return params.add(name, VI(expr), unit, comment)

    # ════════════════ PARAMETERS ════════════════
    # ── Case envelope ──
    padd("case_w",  "39 in",    "in", "Case outside width")
    padd("case_d",  "13.25 in", "in", "Case outside depth (side width)")
    padd("base_h",  "7.875 in", "in", "Base (foot) height")
    padd("board_t", "0.8125 in","in", "Case stock thickness (13/16)")
    padd("x_mid",   "case_w / 2", "in", "X midplane")
    padd("y_mid",   "case_d / 2", "in", "Y midplane")

    # ── Stiles / face frame ──
    padd("lip",     "0.125 in", "in", "Side reveal beside stile (1/8)")
    padd("stile_t", "0.625 in", "in", "Stile thickness (5/8)")
    padd("stile_w", "1.5 in",   "in", "Stile width (1-1/2)")
    padd("stile_in","lip + stile_w", "in", "Stile inner edge from side outer face")
    padd("rab_w",   "board_t - lip", "in", "Stile rabbet width across side thickness")

    # ── Vertical opening stack (front elevation, bottom to top) ──
    padd("open4",  "12.1875 in", "in", "Bottom opening (12-3/16)")
    padd("open3",  "10.75 in",   "in", "Opening 3")
    padd("open2",  "9.375 in",   "in", "Opening 2")
    padd("open1",  "8 in",       "in", "Opening 1")
    padd("open_dr","5.625 in",   "in", "Drawer compartment opening (5-5/8)")
    padd("rail_h", "1.25 in",    "in", "Rail height (1-1/4)")
    padd("frail_t","0.625 in",   "in", "Front rail thickness (5/8)")
    padd("rrail_t","0.875 in",   "in", "Rear top rail thickness (7/8)")
    padd("side_l", "5 * board_t + open4 + open3 + open2 + open1 + open_dr + rail_h",
         "in", "Side length (51-1/4 derived)")
    padd("z_sh3", "base_h + board_t + open4", "in", "Shelf 3 bottom Z")
    padd("z_sh2", "z_sh3 + board_t + open3",  "in", "Shelf 2 bottom Z")
    padd("z_sh1", "z_sh2 + board_t + open2",  "in", "Shelf 1 bottom Z")
    padd("z_dsh", "z_sh1 + board_t + open1",  "in", "Drawer shelf bottom Z")
    padd("z_rail","z_dsh + board_t + open_dr","in", "Rail bottom Z")
    padd("z_top", "base_h + side_l",          "in", "Case top Z (59-1/8)")
    padd("in_w",  "case_w - 2 * board_t",     "in", "Interior width (37-3/8)")

    # ── Sliding dovetails (shelves) ──
    padd("sd_d",    "0.3125 in", "in", "Sliding dovetail housing depth (5/16)")
    padd("sd_h",    "0.75 in",   "in", "Sliding dovetail height at root (3/4)")
    padd("sd_drop", "0.0625 in", "in", "Dovetail flare drop at tip (1/16)")
    padd("shelf_d", "12.0625 in","in", "Shelf depth (12-1/16)")
    padd("dshelf_d","12.6875 in","in", "Drawer shelf depth (12-11/16)")
    padd("shelf_len","in_w + 2 * sd_d", "in", "Shelf length incl. tongues (38)")

    # ── Bottom + half-blind dovetails ──
    padd("bot_len", "case_w - 2 * lip", "in", "Bottom length (38-3/4)")

    # ── Back ──
    padd("bg_off", "0.3125 in", "in", "Back groove offset from rear face (5/16)")
    padd("bg_w",   "0.25 in",   "in", "Back groove width (1/4)")
    padd("bg_d",   "0.3125 in", "in", "Back groove depth (5/16)")
    padd("back_t", "0.375 in",  "in", "Back board thickness (3/8)")
    padd("bsp_t",  "0.125 in",  "in", "Back spline thickness (1/8)")
    padd("bsp_w",  "0.625 in",  "in", "Back spline width (5/8)")
    padd("ebd_w",  "7.6875 in", "in", "End back board width (7-11/16)")
    padd("mbd_w",  "7.4375 in", "in", "Middle back board width (7-7/16)")
    padd("back_y0","case_d - bg_off - bg_w", "in", "Back board front face Y (12-11/16)")
    padd("back_z0","base_h + board_t - bg_d", "in", "Back board bottom Z")
    padd("back_len","z_rail + bg_d - back_z0", "in", "Back board length (49-13/16)")

    # ── Top + cove molding ──
    padd("top_t",   "0.875 in",  "in", "Top thickness (7/8)")
    padd("top_w",   "44.75 in",  "in", "Top width (44-3/4)")
    padd("top_dp",  "17.75 in",  "in", "Top depth (17-3/4)")
    padd("top_f_oh","2.1875 in", "in", "Top front overhang past case front")
    padd("bevel_v", "0.5 in",    "in", "Top bevel vertical drop (1/2)")
    padd("cm_h",    "0.8125 in", "in", "Cove molding height (13/16)")
    padd("cm_w",    "0.9375 in", "in", "Cove molding projection (15/16)")

    # ── Base ──
    padd("foot_t",   "1.5625 in",  "in", "Foot stock thickness (1-9/16)")
    padd("foot_w",   "3.625 in",   "in", "Foot stock width (3-5/8)")
    padd("foot_bw",  "1.8125 in",  "in", "Foot width at floor (1-13/16)")
    padd("foot_fb_z","0.6 in",     "in", "Foot curve end height above floor")
    padd("joint_off","2.34375 in", "in", "Apron joint face from base corner (2-11/32)")
    padd("apron_t",  "1 in",       "in", "Apron thickness")
    padd("apron_h",  "3.125 in",   "in", "Apron width/height (3-1/8)")
    padd("shoulder_z","base_h - apron_h", "in", "Apron bottom Z (4-3/4)")
    padd("foot_rake", "7 deg",     "deg", "Foot flare rake at the floor")
    padd("foot_plumb","apron_h",   "in", "Plumb band = full apron width (flat foot-apron meeting)")
    padd("foot_kick", "(base_h - apron_h) * tan(foot_rake) / 2",
         "in", "Foot face flare: proud at the floor (derived from foot_rake)")
    padd("fapron_l", "case_w - 2 * joint_off", "in", "Front apron length (34-5/16)")
    padd("eapron_l", "case_d - 2 * joint_off", "in", "End apron length (8-9/16)")
    padd("fap_arch", "0.75 in",   "in", "Front apron hump rise (double arch, center dip)")
    padd("eap_arch", "0.875 in",  "in", "End apron arch rise at center")
    padd("st_t", "0.375 in", "in", "Base slip tenon thickness (3/8)")
    padd("st_w", "0.75 in",  "in", "Base slip tenon width (3/4)")
    padd("st_l", "2 in",     "in", "Base slip tenon length (2)")
    padd("str_t", "0.875 in", "in", "Stretcher thickness/height (7/8)")
    padd("str_w", "1.25 in",  "in", "Stretcher width (1-1/4)")
    padd("str_m", "0.46875 in","in", "Stretcher mortise depth (15/32)")
    padd("plate_t", "0.375 in", "in", "Screw plate thickness (3/8)")
    padd("plate_w", "5 in",     "in", "Screw plate width (5)")
    padd("bead_t",  "0.125 in", "in", "Bead thickness (1/8)")
    padd("bead_w",  "0.375 in", "in", "Bead width (3/8)")
    padd("bead_pr", "0.125 in", "in", "Bead proud of base face (1/8)")

    # ── Rail slip tenons ──
    padd("ft_t", "0.25 in",   "in", "Front rail slip tenon thickness")
    padd("ft_w", "1.1875 in", "in", "Front rail slip tenon width (1-3/16)")
    padd("ft_l", "2.1875 in", "in", "Front rail slip tenon length (2-3/16)")
    padd("rt_t", "0.25 in",   "in", "Rear rail slip tenon thickness")
    padd("rt_w", "0.9375 in", "in", "Rear rail slip tenon width (15/16)")
    padd("rt_l", "1.3125 in", "in", "Rear rail slip tenon length (1-5/16)")

    # ── Dividers / drawer guide ──
    padd("div_t",  "0.5 in",    "in", "Divider thickness (1/2)")
    padd("div_h",  "6.875 in",  "in", "Divider height (6-7/8)")
    padd("div_d",  "12.625 in", "in", "Divider depth (12-5/8)")
    padd("div_set","0.0625 in", "in", "Divider front setback (1/16)")
    padd("drw_w",  "8.625 in",  "in", "Drawer opening width (8-5/8)")
    padd("div1_c", "stile_in + drw_w + div_t / 2", "in", "Divider 1 center X")
    padd("div2_c", "div1_c + drw_w + div_t",       "in", "Divider 2 center X")
    padd("dsp_t",  "0.1875 in", "in", "Divider spline thickness (3/16)")
    padd("dsp_w",  "0.625 in",  "in", "Divider spline width (5/8)")
    padd("dsg_d",  "0.3125 in", "in", "Divider spline groove depth (5/16)")
    padd("guide_w","0.8125 in", "in", "Drawer guide thickness in X (13/16)")
    padd("guide_h","1.125 in",  "in", "Drawer guide height (1-1/8)")
    padd("guide_l","11.9375 in","in", "Drawer guide length (11-15/16)")

    # ── Drawers ──
    padd("drw_fh", "5.625 in",  "in", "Drawer front height (5-5/8)")
    padd("drw_sh", "5.5 in",    "in", "Drawer side height (5-1/2)")
    padd("drw_ft", "0.6875 in", "in", "Drawer front thickness (11/16)")
    padd("drw_st", "0.4375 in", "in", "Drawer side thickness (7/16)")
    padd("drw_d",  "12.625 in", "in", "Drawer overall depth (12-5/8)")
    padd("drw_lap","0.25 in",   "in", "Half-blind lap on drawer front (1/4)")
    padd("drw_bk_t","0.375 in", "in", "Drawer back thickness (3/8)")
    padd("drw_bk_h","4.875 in", "in", "Drawer back height (4-7/8)")
    padd("drw_bot_t","0.3125 in","in","Drawer bottom thickness (5/16)")

    # ── Chamfers ──
    padd("cham",   "0.125 in",  "in", "Stopped chamfer width (1/8)")
    padd("cham_ts","1.9375 in", "in", "Chamfer stop from side top (1-15/16)")
    padd("cham_bs","1.75 in",   "in", "Chamfer stop from side bottom (1-3/4)")

    # ════════════════ helpers ════════════════
    def rect_far(comp, plane, xa, ya, xb, yb, name):
        """Rectangle on an XY-type plane spanning model [xa,xb]x[ya,yb],
        dimensioned from the far corner (xb,yb must be positive exprs)."""
        sk = comp.sketches.add(plane); sk.name = name
        m = sk.modelToSketchSpace
        pa = m(P(ev(xa), ev(ya), 0)); pb = m(P(ev(xb), ev(yb), 0))
        rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(
            P(pa.x, pa.y, 0), P(pb.x, pb.y, 0))
        gc = sk.geometricConstraints
        gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
        gc.addVertical(rect[1]); gc.addVertical(rect[3])
        ori = sp.probe_orientations(sk, (ev(xa)+ev(xb))/2, (ev(ya)+ev(yb))/2, 0)
        d = sk.sketchDimensions; far = rect[1].endSketchPoint
        d.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
            ori['x'], P(pb.x, pa.y - 1, 0)).parameter.expression = f"({xb}) - ({xa})"
        d.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
            ori['y'], P(pb.x + 1, pb.y, 0)).parameter.expression = f"({yb}) - ({ya})"
        d.addDistanceDimension(sk.originPoint, far, ori['x'],
            P(pb.x / 2, pb.y + 1, 0)).parameter.expression = xb
        d.addDistanceDimension(sk.originPoint, far, ori['y'],
            P(pb.x + 2, pb.y / 2, 0)).parameter.expression = yb
        return sk, sk.profiles.item(0)

    def arect(comp, plane, axes, third_expr, ua, va, ub, vb, name,
              anchor_face=None, seed=None, off=None, coincide=False,
              opos=None):
        """Anchored rectangle for non-root components. axes = (ax1, ax2) model
        axes of the rect plane; third_expr = plane coordinate. Rect spans
        [ua..ub] x [va..vb] (model exprs, ub>ua, vb>va). anchor_face =
        (parent_body, parent_occ, face_axis, face_dir) projected for
        reference; seed = model Point3D locating the projected anchor
        vertex; off = ((axis, expr), (axis, expr)) offset dims from the
        anchor to the nearest rect corner, or coincide=True to glue them."""
        sk = comp.sketches.add(plane); sk.name = name
        if anchor_face is not None:
            sp.project_face(sk, *anchor_face)
        ax1, ax2 = axes
        third_ax = ({"x", "y", "z"} - {ax1, ax2}).pop()
        def MP(ue, ve):
            c = {"x": 0.0, "y": 0.0, "z": 0.0}
            c[ax1] = ev(ue); c[ax2] = ev(ve); c[third_ax] = ev(third_expr)
            return P(c["x"], c["y"], c["z"])
        m = sk.modelToSketchSpace
        pa = m(MP(ua, va)); pb = m(MP(ub, vb))
        rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(
            P(pa.x, pa.y, 0), P(pb.x, pb.y, 0))
        gc = sk.geometricConstraints
        gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
        gc.addVertical(rect[1]); gc.addVertical(rect[3])
        midp = MP(f"(({ua}) + ({ub})) / 2", f"(({va}) + ({vb})) / 2")
        ori = sp.probe_orientations(sk, midp.x, midp.y, midp.z)
        d = sk.sketchDimensions
        corners = [rect[0].startSketchPoint, rect[0].endSketchPoint,
                   rect[1].endSketchPoint, rect[2].endSketchPoint]
        c00 = corners[0]; c11 = corners[2]
        sp.rdim(sk, d, c00, c11, ori, ax1, f"({ub}) - ({ua})")
        sp.rdim(sk, d, c00, c11, ori, ax2, f"({vb}) - ({va})")
        if opos is not None:
            # Origin-position dims (root-component sketches only)
            sp.rdim(sk, d, sk.originPoint, c00, ori, ax1, opos[0])
            sp.rdim(sk, d, sk.originPoint, c00, ori, ax2, opos[1])
        if seed is not None:
            sm = m(seed)
            ap = sp.anchor_pt(sk, seed.x, seed.y, seed.z)
            if ap is None:
                print(f"  arect {name}: no anchor point found")
            else:
                ag = ap.geometry
                if (ag.x - sm.x) ** 2 + (ag.y - sm.y) ** 2 > 0.01:
                    raise RuntimeError(
                        f"arect {name}: anchor snapped to ({ag.x:.3f},{ag.y:.3f}) "
                        f"but seed projects to ({sm.x:.3f},{sm.y:.3f}) — wrong vertex")
                best = min(corners,
                           key=lambda c: (c.geometry.x - ag.x) ** 2 +
                                         (c.geometry.y - ag.y) ** 2)
                if coincide:
                    gc.addCoincident(best, ap)
                else:
                    for axn, expr in off:
                        sp.rdim(sk, d, ap, best, ori, axn, expr)
        # Self-check: constraints must not have moved the as-drawn rectangle
        lo_x, hi_x = min(pa.x, pb.x), max(pa.x, pb.x)
        lo_y, hi_y = min(pa.y, pb.y), max(pa.y, pb.y)
        for c in corners:
            g = c.geometry
            if (min(abs(g.x - lo_x), abs(g.x - hi_x)) > 0.02 or
                    min(abs(g.y - lo_y), abs(g.y - hi_y)) > 0.02):
                raise RuntimeError(
                    f"arect {name}: solver moved geometry — corner at "
                    f"({g.x:.3f},{g.y:.3f}) vs drawn [{lo_x:.3f}..{hi_x:.3f}]"
                    f"x[{lo_y:.3f}..{hi_y:.3f}]")
        sp.refs_to_construction(sk)
        return sp.smallest_profile(sk)

    def profile_of(sk, want_min_x=None):
        """Pick a profile from a multi-profile sketch by centroid test."""
        best = None
        for i in range(sk.profiles.count):
            pr = sk.profiles.item(i)
            c = pr.areaProperties().centroid
            if want_min_x is None:
                return pr
            if (want_min_x and c.x < c.y) or ((not want_min_x) and c.x >= c.y):
                best = pr
        return best

    # ════════════════ PHASE 1 — BASE: FEET ════════════════
    # Foot FL front piece is THE root body (sits on the floor at the origin).
    base_occ = sp.make_comp(root, "Base"); base_c = base_occ.component

    def foot_blank(plane, axis, name):
        """Foot pattern outline on XZ (axis='x', front piece) or YZ
        (axis='y', side piece), drawn in final position. The stock sits
        plumb with its wide face foot_kick PROUD of the case plane; the
        corner end is oversized to -1 in (the vertical 45-deg miter trims
        it); the apron notch and the inner curve are in the pattern. The
        outward flare comes from the face-flare cuts below, not from this
        profile."""
        sk = base_c.sketches.add(plane); sk.name = name + "_Sk"
        m = sk.modelToSketchSpace
        def mp(u, z):
            return m(P(u, 0, z)) if axis == "x" else m(P(0, u, z))
        A = mp(-1 * 2.54, 0)                          # corner end (oversize)
        B = mp(-1 * 2.54, ev("base_h"))
        C = mp(ev("joint_off"), ev("base_h"))
        D = mp(ev("joint_off"), ev("shoulder_z"))
        E = mp(ev("foot_w") - ev("foot_kick"), ev("shoulder_z"))
        # The inner edge stays straight — the unified base-arch cut
        # (one continuous leg-cyma + apron-arch curve per elevation)
        # carves it together with the apron underside.
        G = mp(ev("foot_w") - ev("foot_kick"), 0)
        L = sk.sketchCurves.sketchLines
        l1 = L.addByTwoPoints(P(A.x, A.y, 0), P(B.x, B.y, 0))     # corner end
        l2 = L.addByTwoPoints(l1.endSketchPoint, P(C.x, C.y, 0))  # top edge
        l3 = L.addByTwoPoints(l2.endSketchPoint, P(D.x, D.y, 0))  # notch face
        l4 = L.addByTwoPoints(l3.endSketchPoint, P(E.x, E.y, 0))  # shoulder
        l5 = L.addByTwoPoints(l4.endSketchPoint, P(G.x, G.y, 0))  # inner edge
        l6 = L.addByTwoPoints(l5.endSketchPoint, l1.startSketchPoint)
        gc = sk.geometricConstraints
        for ln in (l1, l2, l3, l4, l5, l6):
            sp_ = ln.startSketchPoint.geometry; ep = ln.endSketchPoint.geometry
            if abs(ep.x - sp_.x) >= abs(ep.y - sp_.y):
                gc.addHorizontal(ln)
            else:
                gc.addVertical(ln)
        ori = sp.probe_orientations(sk, (1.0 if axis == "x" else 0.0),
                                    (0.0 if axis == "x" else 1.0), 1.0)
        ax = ori[axis]; az = ori['z']
        d = sk.sketchDimensions
        d.addDistanceDimension(sk.originPoint, l1.startSketchPoint, ax,
            P(A.x - 1, A.y - 1, 0)).parameter.expression = "1 in"
        d.addDistanceDimension(sk.originPoint, l1.startSketchPoint, az,
            P(A.x - 2, A.y - 1, 0)).parameter.expression = "0 in"
        d.addDistanceDimension(l1.startSketchPoint, l1.endSketchPoint, az,
            P(A.x - 1, (A.y + B.y) / 2, 0)).parameter.expression = "base_h"
        d.addDistanceDimension(l2.startSketchPoint, l2.endSketchPoint, ax,
            P((B.x + C.x) / 2, B.y + 1, 0)).parameter.expression = "joint_off + 1 in"
        d.addDistanceDimension(l3.startSketchPoint, l3.endSketchPoint, az,
            P(C.x + 1, (C.y + D.y) / 2, 0)).parameter.expression = "apron_h"
        d.addDistanceDimension(l4.startSketchPoint, l4.endSketchPoint, ax,
            P((D.x + E.x) / 2, D.y - 1, 0)
        ).parameter.expression = "foot_w - foot_kick - joint_off"
        sp.refs_to_construction(sk)
        return sp.smallest_profile(sk)

    # Stock set foot_kick proud of the case plane, plumb
    foot_f_pl = sp.off_plane(base_c, root.xZConstructionPlane,
                             "0 in - foot_kick", "FootF_Pl")
    prof_f = foot_blank(foot_f_pl, "x", "Foot_F")
    foot_fl_f = sp.ext_new(base_c, prof_f, "foot_t", "Foot_FL_F_Ext").bodies.item(0)
    foot_fl_f.name = "Foot_FL_F"

    # ── Face-flare cuts: the show faces are sawn to a curve — vertical
    #    for the top foot_plumb band (seamless against the apron plane),
    #    sweeping out to foot_kick proud at the floor. Each cut runs
    #    across the assembled corner and shapes BOTH pieces (sawn after
    #    glue-up), so the corner arris follows the curve diagonally. ──
    def face_flare(plane, axis, name):
        """Cut tool profile in (axis, z): removes everything outboard of
        the flare curve. axis='y' cuts the front face (extrude +X),
        axis='x' cuts the outer side face (extrude +Y)."""
        sk = base_c.sketches.add(plane); sk.name = name + "_Sk"
        m = sk.modelToSketchSpace
        def mp(u, z):
            return m(P(0, u, z)) if axis == "y" else m(P(u, 0, z))
        kick = ev("foot_kick")
        pA = mp(-kick, 0)                                  # curve at floor
        pV = mp(0, ev("base_h") - ev("foot_plumb"))        # curve top
        pB = mp(0, ev("base_h"))
        # The tool's outer boundary must clear the blank's oversized
        # corner end (-1 in) at ANY kick, or the cut splits the foot.
        pT = mp(-kick - 1.2 * 2.54, ev("base_h"))
        pL = mp(-kick - 1.2 * 2.54, 0)
        # Parabolic sweep u(z) = -kick * (1 - z/H)^2: steepest rake at the
        # floor (foot_rake), easing monotonically to vertical at the top
        # of the curve (interior fit points stay draggable).
        Hc = ev("base_h") - ev("foot_plumb")
        ipts = [mp(-kick * (1.0 - f) ** 2, f * Hc)
                for f in (0.21, 0.42, 0.63, 0.80, 0.93)]
        coll = adsk.core.ObjectCollection.create()
        for q in [pA] + ipts + [pV]:
            coll.add(P(q.x, q.y, 0))
        spline = sk.sketchCurves.sketchFittedSplines.add(coll)
        L = sk.sketchCurves.sketchLines
        l1 = L.addByTwoPoints(spline.endSketchPoint, P(pB.x, pB.y, 0))
        l2 = L.addByTwoPoints(l1.endSketchPoint, P(pT.x, pT.y, 0))
        l3 = L.addByTwoPoints(l2.endSketchPoint, P(pL.x, pL.y, 0))
        l4 = L.addByTwoPoints(l3.endSketchPoint, spline.startSketchPoint)
        gc = sk.geometricConstraints
        for ln in (l1, l2, l3, l4):
            sp_ = ln.startSketchPoint.geometry; ep = ln.endSketchPoint.geometry
            if abs(ep.x - sp_.x) >= abs(ep.y - sp_.y):
                gc.addHorizontal(ln)
            else:
                gc.addVertical(ln)
        ori = sp.probe_orientations(sk, (0.0 if axis == "y" else 1.0),
                                    (1.0 if axis == "y" else 0.0), 1.0)
        au = ori[axis]; az = ori['z']
        d = sk.sketchDimensions
        d.addDistanceDimension(sk.originPoint, l1.endSketchPoint, az,
            P(pB.x - 1, pB.y / 2, 0)).parameter.expression = "base_h"
        d.addDistanceDimension(sk.originPoint, l1.endSketchPoint, au,
            P(pB.x - 2, pB.y / 2, 0)).parameter.expression = "0 in"
        d.addDistanceDimension(l1.startSketchPoint, l1.endSketchPoint, az,
            P(pV.x - 1, (pV.y + pB.y) / 2, 0)).parameter.expression = "foot_plumb"
        d.addDistanceDimension(sk.originPoint, spline.startSketchPoint, au,
            P(pA.x - 1, pA.y - 1, 0)).parameter.expression = "foot_kick"
        d.addDistanceDimension(sk.originPoint, spline.startSketchPoint, az,
            P(pA.x - 2, pA.y - 1, 0)).parameter.expression = "0 in"
        d.addDistanceDimension(l2.startSketchPoint, l2.endSketchPoint, au,
            P((pB.x + pT.x) / 2, pB.y + 1, 0)).parameter.expression = "foot_kick + 1.2 in"
        sp.refs_to_construction(sk)
        return sp.smallest_profile(sk)

    flare_y_pl = sp.off_plane(base_c, root.yZConstructionPlane,
                              "0 in - 1.5 in", "FlareY_Pl")
    pr = face_flare(flare_y_pl, "y", "FootFlare_Y")
    sp.ext_op(base_c, pr, "8 in", CUT, foot_fl_f, "FootFlare_Y")
    flare_x_pl = sp.off_plane(base_c, root.xZConstructionPlane,
                              "0 in - 1.5 in", "FlareX_Pl")
    pr = face_flare(flare_x_pl, "x", "FootFlare_X")
    sp.ext_op(base_c, pr, "8 in", CUT, foot_fl_f, "FootFlare_X")
    if base_c.bRepBodies.count != 1:
        raise RuntimeError(
            f"Face-flare cuts split the foot: {base_c.bRepBodies.count} "
            f"bodies in Base (expected 1) — widen the flare tool margin")

    # ── Miter the FL corner (45 deg in plan, vertical) ──
    def tri_cut(comp, plane, pts_model, dist_expr, body, name, flip=False,
                e_a=None, e_b=None, pos=None, co_pt="start",
                anchor_face=None, seed=None, seed_off=None):
        """Triangular prism CUT. Right-triangle: v0->v1 (leg a), v1->v2
        (leg b), hypotenuse free. e_a/e_b = leg length exprs; pos =
        (axis1, expr1, axis2, expr2) origin dims for v0, or None to
        constrain v0 coincident with the sketch origin."""
        sk = comp.sketches.add(plane); sk.name = name + "_Sk"
        if anchor_face is not None:
            sp.project_face(sk, *anchor_face)
        m = sk.modelToSketchSpace
        s = [m(p) for p in pts_model]
        L = sk.sketchCurves.sketchLines
        a = L.addByTwoPoints(P(s[0].x, s[0].y, 0), P(s[1].x, s[1].y, 0))
        b = L.addByTwoPoints(a.endSketchPoint, P(s[2].x, s[2].y, 0))
        L.addByTwoPoints(b.endSketchPoint, a.startSketchPoint)
        gc = sk.geometricConstraints
        for ln in (a, b):
            s_ = ln.startSketchPoint.geometry; e_ = ln.endSketchPoint.geometry
            if abs(e_.x - s_.x) >= abs(e_.y - s_.y):
                gc.addHorizontal(ln)
            else:
                gc.addVertical(ln)
        cmid = pts_model[1]
        ori = sp.probe_orientations(sk, cmid.x, cmid.y, cmid.z)
        d = sk.sketchDimensions
        def dom_axis(p0, p1):
            dx, dy, dz = abs(p1.x - p0.x), abs(p1.y - p0.y), abs(p1.z - p0.z)
            return "x" if dx >= dy and dx >= dz else ("y" if dy >= dz else "z")
        try:
            if e_a:
                d.addDistanceDimension(a.startSketchPoint, a.endSketchPoint,
                    ori[dom_axis(pts_model[0], pts_model[1])],
                    P(s[0].x - 1, s[0].y - 1, 0)).parameter.expression = e_a
            if e_b:
                d.addDistanceDimension(b.startSketchPoint, b.endSketchPoint,
                    ori[dom_axis(pts_model[1], pts_model[2])],
                    P(s[1].x + 1, s[1].y + 1, 0)).parameter.expression = e_b
            if pos is None:
                anchor_sp = a.startSketchPoint if co_pt == "start" else a.endSketchPoint
                if seed is not None:
                    sm = m(seed)
                    ap = sp.anchor_pt(sk, seed.x, seed.y, seed.z)
                    if ap is None:
                        print(f"  tri_cut {name}: no anchor point found")
                    else:
                        ag = ap.geometry
                        if (ag.x - sm.x) ** 2 + (ag.y - sm.y) ** 2 > 0.01:
                            raise RuntimeError(
                                f"tri_cut {name}: anchor snapped wrong "
                                f"({ag.x:.3f},{ag.y:.3f}) vs ({sm.x:.3f},{sm.y:.3f})")
                        if seed_off is None:
                            gc.addCoincident(anchor_sp, ap)
                        else:
                            for axn, expr in seed_off:
                                sp.rdim(sk, d, ap, anchor_sp, ori, axn, expr)
                else:
                    gc.addCoincident(anchor_sp, sk.originPoint)
            else:
                ax1, ex1, ax2, ex2 = pos
                d.addDistanceDimension(sk.originPoint, a.startSketchPoint,
                    ori[ax1], P(s[0].x - 2, s[0].y, 0)).parameter.expression = ex1
                d.addDistanceDimension(sk.originPoint, a.startSketchPoint,
                    ori[ax2], P(s[0].x, s[0].y - 2, 0)).parameter.expression = ex2
        except Exception as e:
            print(f"  tri_cut dim warn {name}: {e}")
        # Self-check: constraints must not have moved the triangle
        for ln, idx in ((a, 0), (b, 1)):
            g = ln.startSketchPoint.geometry
            if (g.x - s[idx].x) ** 2 + (g.y - s[idx].y) ** 2 > 0.0004:
                raise RuntimeError(
                    f"tri_cut {name}: solver moved vertex {idx} to "
                    f"({g.x:.3f},{g.y:.3f}) from ({s[idx].x:.3f},{s[idx].y:.3f})")
        sp.refs_to_construction(sk)
        sp.ext_op(comp, sp.smallest_profile(sk), dist_expr, CUT, body, name,
                  flip=flip)

    # The vertical 45-deg seam plane (x=y) is invariant under the diagonal
    # tilt, so the miter stays a plain vertical cut — sized to cover the
    # kicked region near the floor.
    mm_lo = -1.5 * 2.54; mm_hi = 1.75 * 2.54
    tri_cut(base_c, root.xYConstructionPlane,
            [P(mm_lo, mm_lo, 0), P(mm_lo, mm_hi, 0), P(mm_hi, mm_hi, 0)],
            "base_h", foot_fl_f, "FootMiter_F",
            e_a="3.25 in", e_b="3.25 in",
            pos=("x", "1.5 in", "y", "1.5 in"))

    # The mating half is the same piece mirrored across the miter plane
    # (the vertical 45-deg plane x=y through the corner)
    diag_in = base_c.constructionPlanes.createInput()
    diag_in.setByAngle(root.zConstructionAxis, VI("45 deg"),
                       root.xZConstructionPlane)
    diag_pl = base_c.constructionPlanes.add(diag_in)
    diag_pl.name = "FootMiter_Pl"
    foot_fl_s = sp.mirror_body(base_c, foot_fl_f, diag_pl,
                               "Foot_FL_S_Mir").bodies.item(0)
    foot_fl_s.name = "Foot_FL_S"
    sbb = foot_fl_s.boundingBox
    if sbb.maxPoint.y <= sbb.maxPoint.x:
        raise RuntimeError(
            "Foot mirror across the miter plane landed wrong — check the "
            "diagonal plane angle sign")

    # ── Mirror to the other 3 corners ──
    xmid_pl = sp.off_plane(base_c, root.yZConstructionPlane, "x_mid", "Base_XMid")
    ymid_pl = sp.off_plane(base_c, root.xZConstructionPlane, "y_mid", "Base_YMid")
    foot_fr_f = sp.mirror_body(base_c, foot_fl_f, xmid_pl, "Foot_FR_F_Mir").bodies.item(0); foot_fr_f.name = "Foot_FR_F"
    foot_fr_s = sp.mirror_body(base_c, foot_fl_s, xmid_pl, "Foot_FR_S_Mir").bodies.item(0); foot_fr_s.name = "Foot_FR_S"
    foot_bl_f = sp.mirror_body(base_c, foot_fl_f, ymid_pl, "Foot_BL_F_Mir").bodies.item(0); foot_bl_f.name = "Foot_BL_F"
    foot_bl_s = sp.mirror_body(base_c, foot_fl_s, ymid_pl, "Foot_BL_S_Mir").bodies.item(0); foot_bl_s.name = "Foot_BL_S"
    foot_br_f = sp.mirror_body(base_c, foot_fr_f, ymid_pl, "Foot_BR_F_Mir").bodies.item(0); foot_br_f.name = "Foot_BR_F"
    foot_br_s = sp.mirror_body(base_c, foot_fr_s, ymid_pl, "Foot_BR_S_Mir").bodies.item(0); foot_br_s.name = "Foot_BR_S"
    print(f">>> Feet: {base_c.bRepBodies.count} bodies (8 expected)")

    # ════════════════ PHASE 2 — BASE: APRONS, TENONS, STRETCHER, PLATES, BEADS ════════════════
    padd("st_z1", "shoulder_z + apron_h / 2 - 0.5 in - st_w / 2", "in", "Lower slip tenon bottom Z")
    padd("st_z2", "st_z1 + 1 in", "in", "Upper slip tenon bottom Z")
    # Flat run = exactly the foot shoulder width, so the arch springs at
    # the very end of the leg's inner curve (continuous line)

    # Aprons are plain rectangles — their arched undersides are carved by
    # the unified base-arch cuts below (one continuous curve per elevation)
    pr = arect(base_c, root.xZConstructionPlane, ("x", "z"), "0 in",
               "joint_off", "shoulder_z", "case_w - joint_off", "base_h",
               "Apron_F_Sk", opos=("joint_off", "shoulder_z"))
    apron_f = sp.ext_new(base_c, pr, "apron_t", "Apron_F_Ext").bodies.item(0)
    apron_f.name = "Apron_F"
    apron_b = sp.mirror_body(base_c, apron_f, ymid_pl, "Apron_B_Mir").bodies.item(0)
    apron_b.name = "Apron_B"

    pr = arect(base_c, root.yZConstructionPlane, ("y", "z"), "0 in",
               "joint_off", "shoulder_z", "case_d - joint_off", "base_h",
               "Apron_L_Sk", opos=("joint_off", "shoulder_z"))
    apron_l = sp.ext_new(base_c, pr, "apron_t", "Apron_L_Ext").bodies.item(0)
    apron_l.name = "Apron_L"
    apron_r = sp.mirror_body(base_c, apron_l, xmid_pl, "Apron_R_Mir").bodies.item(0)
    apron_r.name = "Apron_R"

    # ── Unified base-arch cuts: ONE continuous curve per elevation —
    #    leg inner cyma, apron arch, leg inner cyma — sawn across the
    #    feet and the rail together (the same saw-after-glue-up idea as
    #    the face flares), so the leg-to-rail curve continuity is exact
    #    by construction. fracs = (spring, quarter, center) arch heights. ──
    def base_arch_cut(axis, span_e, half_uz, targets, dist_e, name):
        base_pl = (root.xZConstructionPlane if axis == "x"
                   else root.yZConstructionPlane)
        plane = sp.off_plane(base_c, base_pl, "0 in - 2 in", name + "_Pl")
        sk = base_c.sketches.add(plane); sk.name = name + "_Sk"
        m = sk.modelToSketchSpace
        def mp(u, z):
            return m(P(u, -2 * 2.54, z)) if axis == "x" else m(P(-2 * 2.54, u, z))
        kick = ev("foot_kick"); sh = ev("shoulder_z")
        span = ev(span_e)                   # cm (model units)
        gL = ev("foot_bw") - kick           # foot inner edge at the floor (cm)
        ctr = span / 2.0
        # half_uz is sculpted in INCHES; convert to cm so the mirror (span - u)
        # and the mp() placement below are all in model units. (The cm-based
        # generator this replaced hid this; passing inch coords without the
        # conversion scales the whole curve down by 2.54 — the collapse bug.)
        half = [(u * 2.54, z * 2.54) for (u, z) in half_uz]
        # Mirror about the span center -> one continuous, exactly symmetric
        # curve (leg cyma, apron arch, leg cyma). Floor endpoints anchored
        # below; interior points stay free (drag-to-shape, re-bake).
        if abs(half[-1][0] - ctr) < 0.05:
            # last point on the centerline -> single shared crest (end aprons)
            pts = half + [(span - u, z) for (u, z) in reversed(half[:-1])]
        else:
            # last point left of center -> mirror forms a center pair (front)
            pts = half + [(span - u, z) for (u, z) in reversed(half)]
        coll = adsk.core.ObjectCollection.create()
        for u, z in pts:
            q = mp(u, z)
            coll.add(P(q.x, q.y, 0))
        spline = sk.sketchCurves.sketchFittedSplines.add(coll)
        # CONSTRAINT ORDER MATTERS: anchor the spline ENDPOINTS first, while the
        # spline is the only geometry. Once the closing rail lines + H/V are
        # added, the loop determines the endpoints and any later endpoint dim
        # reads as redundant and over-constrains. (Diagnostic: end-z dims apply
        # pre-lines, fail post-lines; the fit points are NOT auto-fixed, so
        # these dims match the drawn cm coords and move nothing; interior free.)
        ori = sp.probe_orientations(sk, (ctr if axis == "x" else -2 * 2.54),
                                    (-2 * 2.54 if axis == "x" else ctr), sh)
        au = ori[axis]; az = ori['z']
        d = sk.sketchDimensions
        d.addDistanceDimension(sk.originPoint, spline.startSketchPoint, au,
            P(pts[0][0] - 2, 1, 0)).parameter.expression = "foot_bw - foot_kick"
        d.addDistanceDimension(sk.originPoint, spline.startSketchPoint, az,
            P(pts[0][0] - 3, 1, 0)).parameter.expression = "0 in"
        d.addDistanceDimension(sk.originPoint, spline.endSketchPoint, au,
            P(pts[-1][0] + 2, 1, 0)
        ).parameter.expression = f"({span_e}) - (foot_bw - foot_kick)"
        d.addDistanceDimension(sk.originPoint, spline.endSketchPoint, az,
            P(pts[-1][0] + 3, 1, 0)).parameter.expression = "0 in"
        # Now the closing waste rail; H/V link pR/pL2 to the (now-fixed)
        # endpoints, and one length dim pins the rail's depth.
        L = sk.sketchCurves.sketchLines
        pR = mp(span - gL, -0.5 * 2.54); pL2 = mp(gL, -0.5 * 2.54)
        l1 = L.addByTwoPoints(spline.endSketchPoint, P(pR.x, pR.y, 0))
        l2 = L.addByTwoPoints(l1.endSketchPoint, P(pL2.x, pL2.y, 0))
        l3 = L.addByTwoPoints(l2.endSketchPoint, spline.startSketchPoint)
        gc = sk.geometricConstraints
        for ln in (l1, l2, l3):
            s_ = ln.startSketchPoint.geometry; e_ = ln.endSketchPoint.geometry
            if abs(e_.x - s_.x) >= abs(e_.y - s_.y):
                gc.addHorizontal(ln)
            else:
                gc.addVertical(ln)
        try:
            d.addDistanceDimension(l1.startSketchPoint, l1.endSketchPoint, az,
                P(pR.x + 1, pR.y, 0)).parameter.expression = "0.5 in"
        except Exception as e:
            print(f"  base_arch rail dim skip {name}: {e}")
        if not sk.isFullyConstrained:
            print(f"  base_arch NOTE {name}: not fully constrained")
        sp.refs_to_construction(sk)
        sp.ext_op(base_c, sp.smallest_profile(sk), dist_e, CUT, targets, name)

    # Half-curves baked from the user's UI edits (floor endpoint -> center),
    # mirrored to full symmetry inside base_arch_cut. To reshape: drag the
    # BaseArch_*_Sk spline fit points in Fusion and re-bake one half here.
    FB_HALF = [(1.5209, 0.0), (1.8159, 2.7187), (2.473, 4.0203),
               (3.9564, 5.1414), (7.6496, 5.4789), (12.5688, 5.0499),
               (18.5863, 4.8535)]
    LR_HALF = [(1.5209, 0.0), (1.8569, 1.995), (3.3334, 4.75),
               (5.0377, 5.46), (6.625, 5.625)]
    base_arch_cut("x", "case_w", FB_HALF,
                  [apron_f, apron_b, foot_fl_f, foot_fr_f, foot_bl_f, foot_br_f],
                  "case_d + 4 in", "BaseArch_FB")
    base_arch_cut("y", "case_d", LR_HALF,
                  [apron_l, apron_r, foot_fl_s, foot_fr_s, foot_bl_s, foot_br_s],
                  "case_w + 4 in", "BaseArch_LR")

    # ── Slip tenons (2 per apron-foot joint, 16 total) — round-ended
    #    (domino-style) per the oval mortises in the plan's foot pattern ──
    stx_pl = sp.off_plane(base_c, root.yZConstructionPlane,
                          "joint_off - st_l / 2", "ST_X_Pl")
    sty_pl = sp.off_plane(base_c, root.xZConstructionPlane,
                          "joint_off - st_l / 2", "ST_Y_Pl")

    def slip_tenon(plane, center, dist_expr, name):
        _, pr = sp.sketch_slot_model(base_c, plane, center, "z",
                                     "st_w", "st_t", name + "_Sk", ev=ev)
        b = sp.ext_new(base_c, pr, dist_expr, name + "_Ext").bodies.item(0)
        b.name = name
        return b

    # FL corner, front-apron joint (tenons run in X through the joint
    # face). Centered in the foot/apron overlap band (the foot's back
    # face sits at foot_t - foot_kick).
    t_flf = [slip_tenon(stx_pl, ("joint_off", "(foot_t - foot_kick) / 2",
                                 "st_z1 + st_w / 2"), "st_l", "ST_FLF_1"),
             slip_tenon(stx_pl, ("joint_off", "(foot_t - foot_kick) / 2",
                                 "st_z2 + st_w / 2"), "st_l", "ST_FLF_2")]
    # FL corner, end-apron joint (tenons run in Y)
    t_fls = [slip_tenon(sty_pl, ("(foot_t - foot_kick) / 2", "joint_off",
                                 "st_z1 + st_w / 2"), "st_l", "ST_FLS_1"),
             slip_tenon(sty_pl, ("(foot_t - foot_kick) / 2", "joint_off",
                                 "st_z2 + st_w / 2"), "st_l", "ST_FLS_2")]

    def mir_pair(pair, plane, base):
        out = []
        for j, b in enumerate(pair):
            mb = sp.mirror_body(base_c, b, plane, f"{base}_{j+1}_Mir").bodies.item(0)
            mb.name = f"{base}_{j+1}"
            out.append(mb)
        return out

    t_frf = mir_pair(t_flf, xmid_pl, "ST_FRF")
    t_blf = mir_pair(t_flf, ymid_pl, "ST_BLF")
    t_brf = mir_pair(t_frf, ymid_pl, "ST_BRF")
    t_frs = mir_pair(t_fls, xmid_pl, "ST_FRS")
    t_bls = mir_pair(t_fls, ymid_pl, "ST_BLS")
    t_brs = mir_pair(t_frs, ymid_pl, "ST_BRS")

    # Mortise cuts — feet
    sp.combine(foot_fl_f, t_flf, CUT, True, "ST_FootFLF_Cut")
    sp.combine(foot_fr_f, t_frf, CUT, True, "ST_FootFRF_Cut")
    sp.combine(foot_bl_f, t_blf, CUT, True, "ST_FootBLF_Cut")
    sp.combine(foot_br_f, t_brf, CUT, True, "ST_FootBRF_Cut")
    sp.combine(foot_fl_s, t_fls, CUT, True, "ST_FootFLS_Cut")
    sp.combine(foot_fr_s, t_frs, CUT, True, "ST_FootFRS_Cut")
    sp.combine(foot_bl_s, t_bls, CUT, True, "ST_FootBLS_Cut")
    sp.combine(foot_br_s, t_brs, CUT, True, "ST_FootBRS_Cut")
    # Mortise cuts — aprons
    sp.combine(apron_f, t_flf + t_frf, CUT, True, "ST_ApronF_Cut")
    sp.combine(apron_b, t_blf + t_brf, CUT, True, "ST_ApronB_Cut")
    sp.combine(apron_l, t_fls + t_bls, CUT, True, "ST_ApronL_Cut")
    sp.combine(apron_r, t_frs + t_brs, CUT, True, "ST_ApronR_Cut")

    # ── Stretcher (housed in apron mortises, 15/32 deep) ──
    str_pl = sp.off_plane(base_c, root.xYConstructionPlane, "base_h - str_t", "Str_Pl")
    _, pr = rect_far(base_c, str_pl, "x_mid - str_w / 2", "apron_t - str_m",
                     "x_mid + str_w / 2", "case_d - apron_t + str_m", "Stretcher_Sk")
    stretcher = sp.ext_new(base_c, pr, "str_t", "Stretcher_Ext").bodies.item(0)
    stretcher.name = "Stretcher"
    sp.combine(apron_f, stretcher, CUT, True, "Str_MortF_Cut")
    sp.combine(apron_b, stretcher, CUT, True, "Str_MortB_Cut")

    # ── Screw plate rabbets (full length, top inner edge of each apron) ──
    rab_pl = sp.off_plane(base_c, root.xYConstructionPlane, "base_h - plate_t", "PlateRab_Pl")
    def rab_cut(xa, ya, xb, yb, body, name):
        _, prr = rect_far(base_c, rab_pl, xa, ya, xb, yb, name + "_Sk")
        sp.ext_op(base_c, prr, "plate_t", CUT, body, name)
    rab_cut("joint_off", "apron_t - plate_t", "case_w - joint_off", "apron_t",
            apron_f, "PlateRab_F")
    rab_cut("joint_off", "case_d - apron_t", "case_w - joint_off",
            "case_d - apron_t + plate_t", apron_b, "PlateRab_B")
    rab_cut("apron_t - plate_t", "joint_off", "apron_t", "case_d - joint_off",
            apron_l, "PlateRab_L")
    rab_cut("case_w - apron_t", "joint_off", "case_w - apron_t + plate_t",
            "case_d - joint_off", apron_r, "PlateRab_R")

    # ── Screw plates (rest in the rabbets, span front to rear apron) ──
    _, pr = rect_far(base_c, rab_pl, "apron_t - plate_t", "apron_t - plate_t",
                     "apron_t - plate_t + plate_w", "case_d - apron_t + plate_t",
                     "Plate_L_Sk")
    plate_l = sp.ext_new(base_c, pr, "plate_t", "Plate_L_Ext").bodies.item(0)
    plate_l.name = "ScrewPlate_L"
    plate_r = sp.mirror_body(base_c, plate_l, xmid_pl, "Plate_R_Mir").bodies.item(0)
    plate_r.name = "ScrewPlate_R"
    # The plan rabbets the FOOT tops for the plates as well (page 8 corner
    # detail) — the plate body cuts its own seat across the feet it crosses.
    sp.combine(foot_fl_f, plate_l, CUT, True, "PlateRab_FootFLF")
    sp.combine(foot_fl_s, plate_l, CUT, True, "PlateRab_FootFLS")
    sp.combine(foot_bl_f, plate_l, CUT, True, "PlateRab_FootBLF")
    sp.combine(foot_bl_s, plate_l, CUT, True, "PlateRab_FootBLS")
    sp.combine(foot_fr_f, plate_r, CUT, True, "PlateRab_FootFRF")
    sp.combine(foot_fr_s, plate_r, CUT, True, "PlateRab_FootFRS")
    sp.combine(foot_br_f, plate_r, CUT, True, "PlateRab_FootBRF")
    sp.combine(foot_br_s, plate_r, CUT, True, "PlateRab_FootBRS")

    # ── Beads (1/8 x 3/8, proud 1/8, in rabbets they cut themselves) ──
    bead_pl = sp.off_plane(base_c, root.xYConstructionPlane, "base_h - bead_t", "Bead_Pl")
    _, pr = rect_far(base_c, bead_pl, "0 in - bead_pr", "0 in - bead_pr",
                     "case_w + bead_pr", "bead_w - bead_pr", "Bead_F_Sk")
    bead_f = sp.ext_new(base_c, pr, "bead_t", "Bead_F_Ext").bodies.item(0)
    bead_f.name = "Bead_F"
    _, pr = rect_far(base_c, bead_pl, "0 in - bead_pr", "bead_w - bead_pr",
                     "bead_w - bead_pr", "case_d - bead_w + bead_pr", "Bead_L_Sk")
    bead_l = sp.ext_new(base_c, pr, "bead_t", "Bead_L_Ext").bodies.item(0)
    bead_l.name = "Bead_L"
    bead_b = sp.mirror_body(base_c, bead_f, ymid_pl, "Bead_B_Mir").bodies.item(0)
    bead_b.name = "Bead_B"
    bead_r = sp.mirror_body(base_c, bead_l, xmid_pl, "Bead_R_Mir").bodies.item(0)
    bead_r.name = "Bead_R"
    # Bead rabbet cuts (bead body IS the rabbet tool — keepTool)
    for tool, targets, nm in [
        (bead_f, [apron_f, foot_fl_f, foot_fr_f, foot_fl_s, foot_fr_s], "BeadF"),
        (bead_b, [apron_b, foot_bl_f, foot_br_f, foot_bl_s, foot_br_s], "BeadB"),
        (bead_l, [apron_l, foot_fl_s, foot_bl_s, foot_fl_f, foot_bl_f], "BeadL"),
        (bead_r, [apron_r, foot_fr_s, foot_br_s, foot_fr_f, foot_br_f], "BeadR"),
    ]:
        for k, tgt in enumerate(targets):
            try:
                sp.combine(tgt, tool, CUT, True, f"{nm}_Cut{k}")
            except Exception as e:
                print(f"  bead cut skip {nm}_{k}: {e}")
    print(f">>> Base complete: {base_c.bRepBodies.count} bodies (35 expected)")

    # ════════════════ PHASE 3 — CASE: SIDES + STILES ════════════════
    case_occ = sp.make_comp(root, "Case"); case_c = case_occ.component
    case_z_pl = sp.off_plane(case_c, root.xYConstructionPlane, "base_h", "Case_Z_Pl")
    cx_mid = sp.off_plane(case_c, root.yZConstructionPlane, "x_mid", "Case_XMid")

    # Side board (full rectangle in plan; the stile cuts its own rabbet
    # later, leaving the 1/8 reveal lip). Anchored to the FL foot's front
    # face projected into the sketch — corner at the foot's outer corner.
    pr = arect(case_c, case_z_pl, ("x", "y"), "base_h",
               "0 in", "0 in", "board_t", "case_d", "Side_L_Sk",
               anchor_face=(foot_fl_f, base_occ, "z", 1),
               seed=P(ev("joint_off"), ev("bead_w") - ev("bead_pr"), ev("base_h")),
               off=(("x", "joint_off - board_t"), ("y", "bead_w - bead_pr")))
    side_l_body = sp.ext_new(case_c, pr, "side_l", "Side_L_Ext").bodies.item(0)
    side_l_body.name = "Side_L"

    # Back groove (through, 1/4 wide x 5/16 deep, 5/16 from the rear face),
    # anchored to the side's own bottom face (rear-inner corner)
    pr = arect(case_c, case_z_pl, ("x", "y"), "base_h",
               "board_t - bg_d", "back_y0", "board_t", "back_y0 + bg_w",
               "SideGrv_L_Sk",
               anchor_face=(side_l_body, None, "z", -1),
               seed=P(ev("board_t"), ev("case_d"), ev("base_h")),
               off=(("x", "0 in"), ("y", "bg_off")))
    sp.ext_op(case_c, pr, "side_l", CUT, side_l_body, "SideGrv_L")

    # Stopped chamfer on the front-outer corner (1/8, stopped 1-3/4 from
    # bottom and 1-15/16 from top of the side)
    cham_pl = sp.off_plane(case_c, root.xYConstructionPlane, "base_h + cham_bs", "Cham_Pl")
    ch = ev("cham")
    tri_cut(case_c, cham_pl,
            [P(0, ch, 0), P(0, 0, 0), P(ch, 0, 0)],
            "side_l - cham_bs - cham_ts", side_l_body, "Cham_L",
            e_a="cham", e_b="cham", co_pt="start",
            anchor_face=(side_l_body, None, "x", -1),
            seed=P(0, ev("case_d"), ev("base_h") + ev("cham_bs")),
            seed_off=(("x", "0 in"), ("y", "case_d - cham")))

    side_r_body = sp.mirror_body(case_c, side_l_body, cx_mid, "Side_R_Mir").bodies.item(0)
    side_r_body.name = "Side_R"

    # Stiles (5/8 x 1-1/2, full side length, in the side rabbets) — anchored
    # coincident to the side's lip corner B
    pr = arect(case_c, case_z_pl, ("x", "y"), "base_h",
               "lip", "0 in", "stile_in", "stile_t", "Stile_L_Sk",
               anchor_face=(side_l_body, None, "z", -1),
               seed=P(ev("board_t"), 0, ev("base_h")),
               off=(("x", "board_t - lip"), ("y", "0 in")))
    stile_l = sp.ext_new(case_c, pr, "side_l", "Stile_L_Ext").bodies.item(0)
    stile_l.name = "Stile_L"
    stile_r = sp.mirror_body(case_c, stile_l, cx_mid, "Stile_R_Mir").bodies.item(0)
    stile_r.name = "Stile_R"
    # Stile cuts its own rabbet in the side ("if it fits, it cuts")
    sp.combine(side_l_body, stile_l, CUT, True, "StileRab_L")
    sp.combine(side_r_body, stile_r, CUT, True, "StileRab_R")
    print(f">>> Case sides+stiles: {case_c.bRepBodies.count} bodies (4 expected)")

    # ════════════════ PHASE 4 — CASE: BOTTOM + HALF-BLIND DOVETAILS ════════════════
    # Bottom slab spans the interior; the dovetail tails (added by the
    # template) extend it into the sides to within 1/8 of their outer faces.
    pr = arect(case_c, case_z_pl, ("x", "y"), "base_h",
               "board_t", "0 in", "case_w - board_t", "case_d", "Bottom_Sk",
               anchor_face=(side_l_body, None, "z", -1),
               seed=P(ev("board_t"), ev("case_d"), ev("base_h")),
               coincide=True)
    bottom_body = sp.ext_new(case_c, pr, "board_t", "Bottom_Ext").bodies.item(0)
    bottom_body.name = "Bottom"

    # Half-blind dovetails: tails on the bottom, sockets in both sides.
    # socket_depth = board_t - lip = 11/16; lap = 1/8 at the side outer face.
    half_blind_dovetail.define_params(params, prefix="hbb",
        angle="8 deg", tail_w="1.7 in", tail_count="6",
        joint_h_expr="case_d - stile_t", pin_thick_expr="board_t", lap="lip")
    half_blind_dovetail.box(case_c, side_l_body, bottom_body,
        cx_mid, cx_mid,
        pin_thick_expr="board_t", tail_thick_expr="board_t",
        right=None, back=side_r_body,
        prefix="hbb", name="HBB", ev=ev,
        fl_plane=case_z_pl, front_expr="0 in",
        joint_axis="y", thick_axis="x", joint_base_expr="stile_t",
        anchor=dict(parent_body=side_l_body, parent_occ=None,
                    face_axis="z", face_dir=-1,
                    anchor_xyz=("board_t", "stile_t", "base_h"),
                    off1=("x", "0 in"),
                    off2=("y", "hbb_pad + hbb_pin_w / 2 + hbb_socket_depth * tan(hbb_angle)")))

    # Back groove in the bottom (1/4 x 5/16, 5/16 from the rear face) —
    # cut AFTER the dovetail join and extended into the housings so the
    # end back boards' tongues seat through the tails (the real groove is
    # plowed full length before the dovetails are cut)
    bot_top_pl = sp.off_plane(case_c, root.xYConstructionPlane,
                              "base_h + board_t", "BotTop_Pl")
    pr = arect(case_c, bot_top_pl, ("x", "y"), "base_h + board_t",
               "board_t - bg_d", "back_y0", "case_w - board_t + bg_d",
               "back_y0 + bg_w", "BotGrv_Sk",
               anchor_face=(bottom_body, None, "z", 1),
               seed=P(ev("case_w") - ev("board_t"), ev("case_d"),
                      ev("base_h") + ev("board_t")),
               off=(("x", "bg_d"), ("y", "bg_off")))
    sp.ext_op(case_c, pr, "bg_d", CUT, bottom_body, "BotGrv", flip=True)

    # Stile notches in the bottom front corners (1-1/2 x 5/8 per plan) —
    # the stiles themselves are the cutting tools
    sp.combine(bottom_body, stile_l, CUT, True, "BotNotch_L")
    sp.combine(bottom_body, stile_r, CUT, True, "BotNotch_R")
    print(f">>> Bottom + dovetails: {case_c.bRepBodies.count} case bodies (5 expected)")

    # ════════════════ PHASE 5 — SHELVES + DRAWER SHELF (sliding dovetails) ════════════════
    padd("sd_ovl", "0.0875 in", "in", "Tongue root overlap into the shelf body")

    def shelf_unit(z0e, y0e, depth_e, name):
        """One shelf: slab + sliding half-dovetail tongues both ends.
        Tongue: 5/16 into the side, 3/4 tall at the root, bottom face
        angled down 1/16 toward the tip (mechanical lock), 1/16 shoulder
        at the top of the shelf."""
        z_pl = sp.off_plane(case_c, root.xYConstructionPlane, z0e, f"{name}_Z_Pl")
        pr = arect(case_c, z_pl, ("x", "y"), z0e,
                   "board_t", y0e, "case_w - board_t", f"({y0e}) + ({depth_e})",
                   f"{name}_Sk",
                   anchor_face=(side_l_body, None, "x", -1),
                   seed=P(0, ev("case_d"), ev(z0e)),
                   off=(("x", "board_t"),
                        ("y", f"case_d - ({y0e}) - ({depth_e})")))
        slab = sp.ext_new(case_c, pr, "board_t", f"{name}_Ext").bodies.item(0)
        slab.name = name

        # Tongue profile on an XZ plane at the shelf front edge
        t_pl = sp.off_plane(case_c, root.xZConstructionPlane, y0e, f"{name}_T_Pl")
        tsk = case_c.sketches.add(t_pl); tsk.name = f"{name}_T_Sk"
        sp.project_face(tsk, side_l_body, None, "x", -1)
        m = tsk.modelToSketchSpace
        z0 = ev(z0e); y0 = ev(y0e)
        TR = m(P(ev("board_t") + ev("sd_ovl"), y0, z0 + ev("sd_h")))
        TL = m(P(ev("board_t") - ev("sd_d"), y0, z0 + ev("sd_h")))
        BL = m(P(ev("board_t") - ev("sd_d"), y0, z0 - ev("sd_drop")))
        BR = m(P(ev("board_t") + ev("sd_ovl"), y0,
                 z0 + ev("sd_drop") * ev("sd_ovl") / ev("sd_d")))
        L = tsk.sketchCurves.sketchLines
        lt = L.addByTwoPoints(P(TR.x, TR.y, 0), P(TL.x, TL.y, 0))
        ll = L.addByTwoPoints(lt.endSketchPoint, P(BL.x, BL.y, 0))
        lb = L.addByTwoPoints(ll.endSketchPoint, P(BR.x, BR.y, 0))
        lr = L.addByTwoPoints(lb.endSketchPoint, lt.startSketchPoint)
        gc = tsk.geometricConstraints
        for ln in (lt, ll, lr):
            a_ = ln.startSketchPoint.geometry; b_ = ln.endSketchPoint.geometry
            if abs(b_.x - a_.x) >= abs(b_.y - a_.y):
                gc.addHorizontal(ln)
            else:
                gc.addVertical(ln)
        ori = sp.probe_orientations(tsk, ev("board_t"), y0, z0)
        d = tsk.sketchDimensions
        sp.rdim(tsk, d, lt.startSketchPoint, lt.endSketchPoint, ori, "x",
                "sd_d + sd_ovl")
        sp.rdim(tsk, d, ll.startSketchPoint, ll.endSketchPoint, ori, "z",
                "sd_h + sd_drop")
        sp.rdim(tsk, d, lr.startSketchPoint, lr.endSketchPoint, ori, "z",
                "sd_h - sd_drop * sd_ovl / sd_d")
        ap = sp.anchor_pt(tsk, 0, y0, ev("base_h"))
        if ap is not None:
            sp.rdim(tsk, d, ap, lt.startSketchPoint, ori, "x", "board_t + sd_ovl")
            sp.rdim(tsk, d, ap, lt.startSketchPoint, ori, "z",
                    f"({z0e}) + sd_h - base_h")
        else:
            print(f"  {name}: tongue anchor not found")
        # Self-check
        for pt, want in ((lt.startSketchPoint, TR), (ll.endSketchPoint, BL)):
            g = pt.geometry
            if (g.x - want.x) ** 2 + (g.y - want.y) ** 2 > 0.0004:
                raise RuntimeError(f"{name} tongue moved: ({g.x:.3f},{g.y:.3f})")
        sp.refs_to_construction(tsk)
        t_l = sp.ext_new(case_c, sp.smallest_profile(tsk), depth_e,
                         f"{name}_TL_Ext").bodies.item(0)
        t_l.name = f"{name}_TongueL"
        t_r = sp.mirror_body(case_c, t_l, cx_mid, f"{name}_TR_Mir").bodies.item(0)
        t_r.name = f"{name}_TongueR"
        # Housing cuts, then join tongues into the slab (CUT before JOIN)
        sp.combine(side_l_body, t_l, CUT, True, f"{name}_HousL")
        sp.combine(side_r_body, t_r, CUT, True, f"{name}_HousR")
        sp.combine(slab, [t_l, t_r], JOIN, False, f"{name}_TJoin")
        return slab

    shelf3 = shelf_unit("z_sh3", "stile_t", "shelf_d", "Shelf_3")
    shelf2 = shelf_unit("z_sh2", "stile_t", "shelf_d", "Shelf_2")
    shelf1 = shelf_unit("z_sh1", "stile_t", "shelf_d", "Shelf_1")
    dshelf = shelf_unit("z_dsh", "0 in", "dshelf_d", "DrawerShelf")
    # Shelf front edges butt the stile backs exactly — trim any boolean
    # tolerance skin with the stiles themselves
    for shf, nm in ((shelf3, "Sh3"), (shelf2, "Sh2"), (shelf1, "Sh1")):
        sp.combine(shf, stile_l, CUT, True, f"{nm}_StileTrim_L")
        sp.combine(shf, stile_r, CUT, True, f"{nm}_StileTrim_R")
    # Drawer shelf notches around the stiles (1-1/8 x 5/8 per plan)
    sp.combine(dshelf, stile_l, CUT, True, "DShNotch_L")
    sp.combine(dshelf, stile_r, CUT, True, "DShNotch_R")
    # The notch boundary lands exactly on the tongue front face — boolean
    # tolerance can split off paper-thin slivers; purge them.
    for i in range(case_c.bRepBodies.count - 1, -1, -1):
        b = case_c.bRepBodies.item(i)
        if b.name.startswith("DrawerShelf (") and b.volume < 1.0:
            case_c.features.removeFeatures.add(b)
            print(f"  removed sliver {b.name}")
    print(f">>> Shelves: {case_c.bRepBodies.count} case bodies (9 expected)")

    # ════════════════ PHASE 6 — RAILS + SLIP TENONS ════════════════
    rail_z_pl = sp.off_plane(case_c, root.xYConstructionPlane, "z_rail", "Rail_Z_Pl")

    # Front rail (5/8 x 1-1/4 x 35-3/4 between the stiles)
    pr = arect(case_c, rail_z_pl, ("x", "y"), "z_rail",
               "stile_in", "0 in", "case_w - stile_in", "frail_t", "Rail_F_Sk",
               anchor_face=(stile_l, None, "x", 1),
               seed=P(ev("stile_in"), ev("stile_t"), ev("z_rail")),
               coincide=True)
    rail_f = sp.ext_new(case_c, pr, "rail_h", "Rail_F_Ext").bodies.item(0)
    rail_f.name = "Rail_F"

    # Rear top rail (7/8 x 1-1/4 x 37-3/8 between the sides)
    pr = arect(case_c, rail_z_pl, ("x", "y"), "z_rail",
               "board_t", "case_d - rrail_t", "case_w - board_t", "case_d",
               "Rail_R_Sk",
               anchor_face=(side_l_body, None, "y", 1),
               seed=P(ev("board_t"), ev("case_d"), ev("z_rail")),
               coincide=True)
    rail_r = sp.ext_new(case_c, pr, "rail_h", "Rail_R_Ext").bodies.item(0)
    rail_r.name = "Rail_R"

    # Back groove in the rear rail (1/8 wide x 5/16 deep, aligned with the
    # back boards' centered top tongue), cut up from the rail bottom face
    padd("rg_y0", "back_y0 + 0.125 in", "in", "Rear rail back-groove front wall Y")
    pr = arect(case_c, rail_z_pl, ("x", "y"), "z_rail",
               "board_t", "rg_y0", "case_w - board_t", "rg_y0 + bsp_t",
               "RailGrv_Sk",
               anchor_face=(rail_r, None, "z", -1),
               seed=P(ev("case_w") - ev("board_t"), ev("case_d"), ev("z_rail")),
               off=(("x", "0 in"), ("y", "case_d - rg_y0 - bsp_t")))
    sp.ext_op(case_c, pr, "bg_d", CUT, rail_r, "RailGrv")

    # Front rail slip tenons (1/4 x 1-3/16 x 2-3/16 into the stiles) —
    # round-ended (domino-style), reanchored to the stile inner face
    ftx_pl = sp.off_plane(case_c, root.yZConstructionPlane,
                          "stile_in - ft_l / 2", "FT_X_Pl")
    ft_sk, pr = sp.sketch_slot_model(case_c, ftx_pl,
        ("stile_in", "frail_t / 2", "z_rail + rail_h / 2"), "z",
        "ft_w", "ft_t", "FT_L_Sk", ev=ev,
        anchor=dict(parent_body=stile_l, parent_occ=None,
                    face_axis="x", face_dir=1,
                    anchor_xyz=("stile_in", "stile_t", "z_top"),
                    off=(("y", "stile_t - frail_t / 2"),
                         ("z", "z_top - z_rail - rail_h / 2 - (ft_w - ft_t) / 2"))))
    ft_l_b = sp.ext_new(case_c, pr, "ft_l", "FT_L_Ext").bodies.item(0)
    ft_l_b.name = "FT_L"
    ft_r_b = sp.mirror_body(case_c, ft_l_b, cx_mid, "FT_R_Mir").bodies.item(0)
    ft_r_b.name = "FT_R"

    # Rear rail slip tenons (1/4 x 15/16 x 1-5/16 into the sides, kept
    # forward of the back groove) — round-ended, reanchored to the side
    rtx_pl = sp.off_plane(case_c, root.yZConstructionPlane,
                          "board_t - rt_l / 2", "RT_X_Pl")
    rt_sk, pr = sp.sketch_slot_model(case_c, rtx_pl,
        ("board_t", "back_y0 - rt_t / 2", "z_rail + rail_h / 2"), "z",
        "rt_w", "rt_t", "RT_L_Sk", ev=ev,
        anchor=dict(parent_body=side_l_body, parent_occ=None,
                    face_axis="y", face_dir=1,
                    anchor_xyz=("board_t", "case_d", "z_top"),
                    off=(("y", "case_d - back_y0 + rt_t / 2"),
                         ("z", "z_top - z_rail - rail_h / 2 - (rt_w - rt_t) / 2"))))
    rt_l_b = sp.ext_new(case_c, pr, "rt_l", "RT_L_Ext").bodies.item(0)
    rt_l_b.name = "RT_L"
    rt_r_b = sp.mirror_body(case_c, rt_l_b, cx_mid, "RT_R_Mir").bodies.item(0)
    rt_r_b.name = "RT_R"

    # Mortise cuts
    sp.combine(stile_l, ft_l_b, CUT, True, "FT_StileL_Cut")
    sp.combine(stile_r, ft_r_b, CUT, True, "FT_StileR_Cut")
    sp.combine(rail_f, [ft_l_b, ft_r_b], CUT, True, "FT_Rail_Cut")
    sp.combine(side_l_body, rt_l_b, CUT, True, "RT_SideL_Cut")
    sp.combine(side_r_body, rt_r_b, CUT, True, "RT_SideR_Cut")
    sp.combine(rail_r, [rt_l_b, rt_r_b], CUT, True, "RT_Rail_Cut")
    print(f">>> Rails: {case_c.bRepBodies.count} case bodies (15 expected)")

    # ════════════════ PHASE 7 — DIVIDERS, SPLINES, DRAWER GUIDE ════════════════
    dsh_top_pl = sp.off_plane(case_c, root.xYConstructionPlane,
                              "z_dsh + board_t", "DShTop_Pl")
    spl_pl = sp.off_plane(case_c, root.xYConstructionPlane,
                          "z_dsh + board_t - dsg_d", "DivSpl_Pl")

    def divider_unit(ce, idx):
        # Divider (1/2 x 6-7/8 x 12-5/8, front edge set back 1/16)
        pr = arect(case_c, dsh_top_pl, ("x", "y"), "z_dsh + board_t",
                   f"{ce} - div_t / 2", "div_set",
                   f"{ce} + div_t / 2", "div_set + div_d", f"Div{idx}_Sk",
                   anchor_face=(dshelf, None, "z", 1),
                   seed=P(ev("case_w") - ev("board_t"), ev("dshelf_d"),
                          ev("z_dsh") + ev("board_t")),
                   off=(("x", f"case_w - board_t - ({ce}) - div_t / 2"),
                        ("y", "0 in")))
        div = sp.ext_new(case_c, pr, "div_h", f"Div{idx}_Ext").bodies.item(0)
        div.name = f"Divider_{idx}"
        # The rails cut their own notches in the divider
        sp.combine(div, rail_f, CUT, True, f"Div{idx}_NotchF")
        sp.combine(div, rail_r, CUT, True, f"Div{idx}_NotchR")
        # Spline (3/16 x 5/8 x 12-7/16): cuts its groove in BOTH the drawer
        # shelf (stopped 1/4 from the front) and the divider bottom edge
        pr = arect(case_c, spl_pl, ("x", "y"), "z_dsh + board_t - dsg_d",
                   f"{ce} - dsp_t / 2", "0.25 in",
                   f"{ce} + dsp_t / 2", "dshelf_d", f"DivSpl{idx}_Sk",
                   anchor_face=(dshelf, None, "z", 1),
                   seed=P(ev("case_w") - ev("board_t"), ev("dshelf_d"),
                          ev("z_dsh") + ev("board_t")),
                   off=(("x", f"case_w - board_t - ({ce}) - dsp_t / 2"),
                        ("y", "0 in")))
        spl = sp.ext_new(case_c, pr, "dsp_w", f"DivSpl{idx}_Ext").bodies.item(0)
        spl.name = f"DivSpline_{idx}"
        sp.combine(dshelf, spl, CUT, True, f"DivSpl{idx}_ShelfCut")
        sp.combine(div, spl, CUT, True, f"DivSpl{idx}_DivCut")
        return div

    div1 = divider_unit("div1_c", 1)
    div2 = divider_unit("div2_c", 2)

    # Drawer guide (13/16 x 1-1/8 x 11-15/16 on the shelf against the left
    # side, guiding face flush with the stile inner edge)
    pr = arect(case_c, dsh_top_pl, ("x", "y"), "z_dsh + board_t",
               "board_t", "stile_t", "stile_in", "stile_t + guide_l",
               "Guide_Sk",
               anchor_face=(dshelf, None, "z", 1),
               seed=P(ev("board_t"), ev("dshelf_d"), ev("z_dsh") + ev("board_t")),
               off=(("x", "0 in"), ("y", "dshelf_d - stile_t - guide_l")))
    guide = sp.ext_new(case_c, pr, "guide_h", "Guide_Ext").bodies.item(0)
    guide.name = "DrawerGuide"
    print(f">>> Dividers + guide: {case_c.bRepBodies.count} case bodies (20 expected)")

    # ════════════════ PHASE 8 — BACK (5 splined boards) ════════════════
    back_occ = sp.make_comp(root, "Back"); back_c = back_occ.component
    padd("bk_g",  "(in_w + 2 * bg_d - 2 * ebd_w - 3 * mbd_w) / 4", "in", "Back board expansion gap")
    padd("bk_x1", "board_t - bg_d", "in", "Back board 1 left edge X")
    padd("bk_x2", "bk_x1 + ebd_w + bk_g", "in", "Back board 2 left edge X")
    padd("bk_x3", "bk_x2 + mbd_w + bk_g", "in", "Back board 3 left edge X")
    padd("bk_x4", "bk_x3 + mbd_w + bk_g", "in", "Back board 4 left edge X")
    padd("bk_x5", "bk_x4 + mbd_w + bk_g", "in", "Back board 5 left edge X")
    bk_z_pl = sp.off_plane(back_c, root.xYConstructionPlane, "back_z0", "Back_Z_Pl")
    bk_rail_pl = sp.off_plane(back_c, root.xYConstructionPlane, "z_rail", "BackTop_Pl")

    def back_board(x0e, we, name, outer=None, offx=None):
        """One back board: slab + tongue rabbets. Tongues: 1/4 front-quarter
        at the bottom and outer edges (rear-face rabbet), centered 1/8 at
        the top (both-face rabbets) into the rear rail groove. offx =
        POSITIVE-magnitude x-offset expr from the side inner face to the
        board's nearest corner."""
        if offx is None:
            offx = f"({x0e}) - board_t"
        pr = arect(back_c, bk_z_pl, ("x", "y"), "back_z0",
                   x0e, "back_y0", f"({x0e}) + ({we})", "back_y0 + back_t",
                   f"{name}_Sk",
                   anchor_face=(side_l_body, case_occ, "y", 1),
                   seed=P(ev("board_t"), ev("case_d"), ev("back_z0")),
                   off=(("x", offx),
                        ("y", "case_d - back_y0 - back_t")))
        bd = sp.ext_new(back_c, pr, "back_len", f"{name}_Ext").bodies.item(0)
        bd.name = name
        x0 = ev(x0e); w = ev(we)
        # Top tongue: front-face rabbet
        pr = arect(back_c, bk_rail_pl, ("x", "y"), "z_rail",
                   f"({x0e}) - 0.1 in", "back_y0",
                   f"({x0e}) + ({we}) + 0.1 in", "rg_y0", f"{name}_TTF_Sk",
                   anchor_face=(bd, None, "y", -1),
                   seed=P(x0 + w, ev("back_y0"), ev("z_rail")),
                   off=(("x", "0.1 in"), ("y", "0 in")))
        sp.ext_op(back_c, pr, "bg_d + 0.5 in", CUT, bd, f"{name}_TTF")
        # Top tongue: rear-face rabbet
        pr = arect(back_c, bk_rail_pl, ("x", "y"), "z_rail",
                   f"({x0e}) - 0.1 in", "rg_y0 + bsp_t",
                   f"({x0e}) + ({we}) + 0.1 in", "back_y0 + back_t",
                   f"{name}_TTR_Sk",
                   anchor_face=(bd, None, "y", 1),
                   seed=P(x0 + w, ev("back_y0") + ev("back_t"), ev("z_rail")),
                   off=(("x", "0.1 in"), ("y", "0 in")))
        sp.ext_op(back_c, pr, "bg_d + 0.5 in", CUT, bd, f"{name}_TTR")
        # Bottom tongue: rear-face rabbet
        pr = arect(back_c, bk_z_pl, ("x", "y"), "back_z0",
                   f"({x0e}) - 0.1 in", "back_y0 + bg_w",
                   f"({x0e}) + ({we}) + 0.1 in", "back_y0 + back_t",
                   f"{name}_BT_Sk",
                   anchor_face=(bd, None, "y", 1),
                   seed=P(x0 + w, ev("back_y0") + ev("back_t"), ev("back_z0")),
                   off=(("x", "0.1 in"), ("y", "0 in")))
        sp.ext_op(back_c, pr, "bg_d", CUT, bd, f"{name}_BT")
        # Outer edge tongue (end boards): rear-face rabbet, full height
        if outer == "L":
            pr = arect(back_c, bk_z_pl, ("x", "y"), "back_z0",
                       f"({x0e}) - 0.1 in", "back_y0 + bg_w",
                       "board_t", "back_y0 + back_t", f"{name}_ET_Sk",
                       anchor_face=(bd, None, "y", 1),
                       seed=P(x0, ev("back_y0") + ev("back_t"), ev("back_z0")),
                       off=(("x", "0.1 in"), ("y", "0 in")))
            sp.ext_op(back_c, pr, "back_len", CUT, bd, f"{name}_ET")
        elif outer == "R":
            pr = arect(back_c, bk_z_pl, ("x", "y"), "back_z0",
                       "case_w - board_t", "back_y0 + bg_w",
                       f"({x0e}) + ({we}) + 0.1 in", "back_y0 + back_t",
                       f"{name}_ET_Sk",
                       anchor_face=(bd, None, "y", 1),
                       seed=P(x0 + w, ev("back_y0") + ev("back_t"), ev("back_z0")),
                       off=(("x", "0.1 in"), ("y", "0 in")))
            sp.ext_op(back_c, pr, "back_len", CUT, bd, f"{name}_ET")
        return bd

    bk1 = back_board("bk_x1", "ebd_w", "BackBoard_1", outer="L", offx="bg_d")
    bk2 = back_board("bk_x2", "mbd_w", "BackBoard_2")
    bk3 = back_board("bk_x3", "mbd_w", "BackBoard_3")
    bk4 = back_board("bk_x4", "mbd_w", "BackBoard_4")
    bk5 = back_board("bk_x5", "ebd_w", "BackBoard_5", outer="R")

    # Splines between boards (1/8 x 5/8, centered; they cut their own
    # grooves in both neighbours)
    def back_spline(gce, left_bd, right_bd, idx):
        pr = arect(back_c, bk_z_pl, ("x", "y"), "back_z0",
                   f"({gce}) - bsp_w / 2", "rg_y0",
                   f"({gce}) + bsp_w / 2", "rg_y0 + bsp_t", f"BkSpl{idx}_Sk",
                   anchor_face=(side_l_body, case_occ, "y", 1),
                   seed=P(ev("board_t"), ev("case_d"), ev("back_z0")),
                   off=(("x", f"({gce}) - bsp_w / 2 - board_t"),
                        ("y", "case_d - rg_y0 - bsp_t")))
        s = sp.ext_new(back_c, pr, "back_len", f"BkSpl{idx}_Ext").bodies.item(0)
        s.name = f"BackSpline_{idx}"
        sp.combine(left_bd, s, CUT, True, f"BkSpl{idx}_CutL")
        sp.combine(right_bd, s, CUT, True, f"BkSpl{idx}_CutR")
        return s

    back_spline("bk_x2 - bk_g / 2", bk1, bk2, 1)
    back_spline("bk_x3 - bk_g / 2", bk2, bk3, 2)
    back_spline("bk_x4 - bk_g / 2", bk3, bk4, 3)
    back_spline("bk_x5 - bk_g / 2", bk4, bk5, 4)
    print(f">>> Back: {back_c.bRepBodies.count} bodies (9 expected)")

    # ════════════════ PHASE 9 — TOP (beveled) ════════════════
    top_occ = sp.make_comp(root, "Top"); top_c = top_occ.component
    top_z_pl = sp.off_plane(top_c, root.xYConstructionPlane, "z_top", "Top_Z_Pl")
    pr = arect(top_c, top_z_pl, ("x", "y"), "z_top",
               "x_mid - top_w / 2", "0 in - top_f_oh",
               "x_mid + top_w / 2", "top_dp - top_f_oh", "Top_Sk",
               anchor_face=(side_l_body, case_occ, "z", 1),
               seed=P(0, ev("case_d"), ev("z_top")),
               off=(("x", "top_w / 2 - x_mid"),
                    ("y", "top_dp - top_f_oh - case_d")))
    top_body = sp.ext_new(top_c, pr, "top_t", "Top_Ext").bodies.item(0)
    top_body.name = "Top"

    # Underside bevels: 1/2 rise, running from each edge to the molding face
    zt = ev("z_top"); bv = ev("bevel_v")
    yF = -ev("top_f_oh"); yB = ev("top_dp") - ev("top_f_oh")
    xL = ev("x_mid") - ev("top_w") / 2; xR = ev("x_mid") + ev("top_w") / 2
    cmw = ev("cm_w")
    bev_x_pl = sp.off_plane(top_c, root.yZConstructionPlane,
                            "x_mid - top_w / 2", "BevX_Pl")
    tri_cut(top_c, bev_x_pl,
            [P(xL, yF, zt + bv), P(xL, yF, zt), P(xL, yF + ev("top_f_oh") - cmw, zt)],
            "top_w", top_body, "Bevel_F",
            e_a="bevel_v", e_b="top_f_oh - cm_w", co_pt="start",
            anchor_face=(top_body, None, "y", -1),
            seed=P(xL, yF, zt), seed_off=(("y", "0 in"), ("z", "bevel_v")))
    tri_cut(top_c, bev_x_pl,
            [P(xL, yB, zt + bv), P(xL, yB, zt), P(xL, yB - (ev("top_dp") - ev("top_f_oh") - ev("case_d") - cmw), zt)],
            "top_w", top_body, "Bevel_B",
            e_a="bevel_v", e_b="top_dp - top_f_oh - case_d - cm_w", co_pt="start",
            anchor_face=(top_body, None, "y", 1),
            seed=P(xL, yB, zt), seed_off=(("y", "0 in"), ("z", "bevel_v")))
    bev_y_pl = sp.off_plane(top_c, root.xZConstructionPlane,
                            "0 in - top_f_oh", "BevY_Pl")
    tri_cut(top_c, bev_y_pl,
            [P(xL, yF, zt + bv), P(xL, yF, zt), P(xL + (ev("top_w") - ev("case_w")) / 2 - cmw, yF, zt)],
            "top_dp", top_body, "Bevel_L",
            e_a="bevel_v", e_b="(top_w - case_w) / 2 - cm_w", co_pt="start",
            anchor_face=(top_body, None, "x", -1),
            seed=P(xL, yF, zt), seed_off=(("x", "0 in"), ("z", "bevel_v")))
    tri_cut(top_c, bev_y_pl,
            [P(xR, yF, zt + bv), P(xR, yF, zt), P(xR - (ev("top_w") - ev("case_w")) / 2 + cmw, yF, zt)],
            "top_dp", top_body, "Bevel_R",
            e_a="bevel_v", e_b="(top_w - case_w) / 2 - cm_w", co_pt="start",
            anchor_face=(top_body, None, "x", 1),
            seed=P(xR, yF, zt), seed_off=(("x", "0 in"), ("z", "bevel_v")))
    print(f">>> Top: {top_c.bRepBodies.count} bodies (1 expected)")

    # ════════════════ PHASE 10 — COVE MOLDINGS, RETURNS, CLEATS ════════════════
    padd("cm_of", "0.125 in",  "in", "Cove molding outer flat")
    padd("cm_bf", "0.1875 in", "in", "Cove molding bottom flat")
    padd("cleat_t", "0.1875 in", "in", "Dovetail cleat thickness (3/16)")
    padd("cleat_w", "0.375 in",  "in", "Dovetail cleat width (3/8)")
    padd("cleat_l", "3 in",      "in", "Dovetail cleat length")

    def cove_profile(plane, ax, base_e, sgn, name, anchor_face, seed):
        """Cove molding cross-section. ax = horizontal model axis; base_e =
        inner (case) face coordinate; sgn = outward direction sign."""
        sk = top_c.sketches.add(plane); sk.name = name + "_Sk"
        sp.project_face(sk, *anchor_face)
        m = sk.modelToSketchSpace
        zt2 = ev("z_top"); u_in = ev(base_e)
        u_out = u_in + sgn * ev("cm_w")
        u_bf = u_in + sgn * ev("cm_bf")
        def MP(u, z):
            c = {"x": 0.0, "y": 0.0, "z": z}
            c[ax] = u
            return P(c["x"], c["y"], c["z"])
        T1 = m(MP(u_in, zt2)); T2 = m(MP(u_out, zt2))
        F1 = m(MP(u_out, zt2 - ev("cm_of")))
        F2 = m(MP(u_bf, zt2 - ev("cm_h")))
        B1 = m(MP(u_in, zt2 - ev("cm_h")))
        SM = m(MP(u_in + sgn * ev("cm_w") * 0.55, zt2 - ev("cm_h") * 0.75))
        coll = adsk.core.ObjectCollection.create()
        for q in (F1, SM, F2):
            coll.add(P(q.x, q.y, 0))
        spline = sk.sketchCurves.sketchFittedSplines.add(coll)
        L = sk.sketchCurves.sketchLines
        l_top = L.addByTwoPoints(P(T1.x, T1.y, 0), P(T2.x, T2.y, 0))
        l_out = L.addByTwoPoints(l_top.endSketchPoint, spline.startSketchPoint)
        l_bot = L.addByTwoPoints(spline.endSketchPoint, P(B1.x, B1.y, 0))
        l_in = L.addByTwoPoints(l_bot.endSketchPoint, l_top.startSketchPoint)
        gc = sk.geometricConstraints
        for ln in (l_top, l_out, l_bot, l_in):
            a_ = ln.startSketchPoint.geometry; b_ = ln.endSketchPoint.geometry
            if abs(b_.x - a_.x) >= abs(b_.y - a_.y):
                gc.addHorizontal(ln)
            else:
                gc.addVertical(ln)
        mid = MP(u_in + sgn * ev("cm_w") / 2, zt2 - ev("cm_h") / 2)
        ori = sp.probe_orientations(sk, mid.x, mid.y, mid.z)
        d = sk.sketchDimensions
        sp.rdim(sk, d, l_top.startSketchPoint, l_top.endSketchPoint, ori, ax, "cm_w")
        sp.rdim(sk, d, l_out.startSketchPoint, l_out.endSketchPoint, ori, "z", "cm_of")
        sp.rdim(sk, d, l_bot.startSketchPoint, l_bot.endSketchPoint, ori, ax, "cm_bf")
        sp.rdim(sk, d, l_in.startSketchPoint, l_in.endSketchPoint, ori, "z", "cm_h")
        sm_pt = m(seed)
        ap = sp.anchor_pt(sk, seed.x, seed.y, seed.z)
        if ap is not None:
            ag = ap.geometry
            if (ag.x - sm_pt.x) ** 2 + (ag.y - sm_pt.y) ** 2 > 0.01:
                raise RuntimeError(f"cove {name}: anchor snapped wrong")
            gc.addCoincident(l_top.startSketchPoint, ap)
        else:
            print(f"  cove {name}: anchor not found")
        g = l_top.startSketchPoint.geometry
        if (g.x - T1.x) ** 2 + (g.y - T1.y) ** 2 > 0.0004:
            raise RuntimeError(f"cove {name}: solver moved T1")
        sp.refs_to_construction(sk)
        return sp.smallest_profile(sk)

    # Front molding (40-7/8 outer length, mitered both ends)
    cmf_pl = sp.off_plane(top_c, root.yZConstructionPlane, "0 in - cm_w", "CMF_Pl")
    pr = cove_profile(cmf_pl, "y", "0 in", -1, "CM_F",
                      (rail_f, case_occ, "y", -1),
                      P(-ev("cm_w"), 0, ev("z_top")))
    cm_f = sp.ext_new(top_c, pr, "case_w + 2 * cm_w", "CM_F_Ext").bodies.item(0)
    cm_f.name = "CoveMolding_F"

    # Side molding L (15-1/8: mitered at the front corner, mitered to the
    # return at the rear)
    cml_pl = sp.off_plane(top_c, root.xZConstructionPlane, "0 in - cm_w", "CML_Pl")
    pr = cove_profile(cml_pl, "x", "0 in", -1, "CM_L",
                      (side_l_body, case_occ, "x", -1),
                      P(0, -ev("cm_w"), ev("z_top")))
    cm_l = sp.ext_new(top_c, pr, "case_d + 2 * cm_w", "CM_L_Ext").bodies.item(0)
    cm_l.name = "CoveMolding_L"

    # Back molding (39, butted between the returns)
    pr = cove_profile(root.yZConstructionPlane, "y", "case_d", 1, "CM_B",
                      (side_l_body, case_occ, "y", 1),
                      P(0, ev("case_d"), ev("z_top")))
    cm_b = sp.ext_new(top_c, pr, "case_w", "CM_B_Ext").bodies.item(0)
    cm_b.name = "CoveMolding_B"

    # Return L (15/16 corner block carrying the profile around the corner)
    ret_pl = sp.off_plane(top_c, root.yZConstructionPlane, "0 in - cm_w", "RetL_Pl")
    pr = cove_profile(ret_pl, "y", "case_d", 1, "Return_L",
                      (side_l_body, case_occ, "y", 1),
                      P(-ev("cm_w"), ev("case_d"), ev("z_top")))
    ret_l = sp.ext_new(top_c, pr, "cm_w", "RetL_Ext").bodies.item(0)
    ret_l.name = "Return_L"

    # ── Miters (45-deg vertical cuts at the corners) ──
    cm_z_pl = sp.off_plane(top_c, root.xYConstructionPlane, "z_top - cm_h", "CM_Z_Pl")
    cw = ev("case_w"); cd = ev("case_d")
    # Front corners: the front molding keeps the half adjacent to its own
    # inner face (x >= y), the side molding keeps x <= y — each piece's
    # CUT removes the other half of the corner square.
    tri_cut(top_c, cm_z_pl,
            [P(0, 0, 0), P(-cmw, 0, 0), P(-cmw, -cmw, 0)],
            "cm_h", cm_f, "MiterF_L", e_a="cm_w", e_b="cm_w", co_pt="start",
            anchor_face=(stile_l, case_occ, "y", -1),
            seed=P(ev("lip"), 0, ev("z_top") - ev("cm_h")),
            seed_off=(("x", "lip"), ("y", "0 in")))
    tri_cut(top_c, cm_z_pl,
            [P(cw, 0, 0), P(cw + cmw, 0, 0), P(cw + cmw, -cmw, 0)],
            "cm_h", cm_f, "MiterF_R", e_a="cm_w", e_b="cm_w", co_pt="start",
            anchor_face=(stile_r, case_occ, "y", -1),
            seed=P(cw - ev("lip"), 0, ev("z_top") - ev("cm_h")),
            seed_off=(("x", "lip"), ("y", "0 in")))
    tri_cut(top_c, cm_z_pl,
            [P(0, 0, 0), P(0, -cmw, 0), P(-cmw, -cmw, 0)],
            "cm_h", cm_l, "MiterL_F", e_a="cm_w", e_b="cm_w", co_pt="start",
            anchor_face=(stile_l, case_occ, "y", -1),
            seed=P(ev("lip"), 0, ev("z_top") - ev("cm_h")),
            seed_off=(("x", "lip"), ("y", "0 in")))
    tri_cut(top_c, cm_z_pl,
            [P(0, cd, 0), P(0, cd + cmw, 0), P(-cmw, cd + cmw, 0)],
            "cm_h", cm_l, "MiterL_B", e_a="cm_w", e_b="cm_w", co_pt="start",
            anchor_face=(side_l_body, case_occ, "y", 1),
            seed=P(0, cd, ev("z_top") - ev("cm_h")))
    tri_cut(top_c, cm_z_pl,
            [P(0, cd, 0), P(-cmw, cd, 0), P(-cmw, cd + cmw, 0)],
            "cm_h", ret_l, "MiterRet_L", e_a="cm_w", e_b="cm_w", co_pt="start",
            anchor_face=(side_l_body, case_occ, "y", 1),
            seed=P(0, cd, ev("z_top") - ev("cm_h")))

    # Mirror side molding + return to the right (clean: extrude-cuts only)
    top_xmid = sp.off_plane(top_c, root.yZConstructionPlane, "x_mid", "Top_XMid")
    cm_r = sp.mirror_body(top_c, cm_l, top_xmid, "CM_R_Mir").bodies.item(0)
    cm_r.name = "CoveMolding_R"
    ret_r = sp.mirror_body(top_c, ret_l, top_xmid, "RetR_Mir").bodies.item(0)
    ret_r.name = "Return_R"

    # Cleats (3/16 x 3/8 x 3 on the side outer faces near the back, hidden
    # inside the groove they cut in the side moldings; modeled rectangular)
    cleat_pl = sp.off_plane(top_c, root.xYConstructionPlane,
                            "z_top - cm_h / 2 - cleat_w / 2", "Cleat_Pl")
    pr = arect(top_c, cleat_pl, ("x", "y"), "z_top - cm_h / 2 - cleat_w / 2",
               "0 in - cleat_t", "case_d - 0.25 in - cleat_l",
               "0 in", "case_d - 0.25 in", "Cleat_L_Sk",
               anchor_face=(side_l_body, case_occ, "x", -1),
               seed=P(0, ev("case_d"),
                      ev("z_top") - ev("cm_h") / 2 - ev("cleat_w") / 2),
               off=(("x", "0 in"), ("y", "0.25 in")))
    cleat_l_b = sp.ext_new(top_c, pr, "cleat_w", "Cleat_L_Ext").bodies.item(0)
    cleat_l_b.name = "Cleat_L"
    cleat_r_b = sp.mirror_body(top_c, cleat_l_b, top_xmid, "Cleat_R_Mir").bodies.item(0)
    cleat_r_b.name = "Cleat_R"
    sp.combine(cm_l, cleat_l_b, CUT, True, "CleatGrv_L")
    sp.combine(cm_r, cleat_r_b, CUT, True, "CleatGrv_R")
    print(f">>> Moldings: {top_c.bRepBodies.count} top bodies (9 expected)")

    # ════════════════ PHASE 11 — DRAWERS ════════════════
    drawers_occ = sp.make_comp(root, "Drawers"); drawers_c = drawers_occ.component
    padd("d2_x0",  "stile_in + drw_w + div_t", "in", "Drawer 2 opening left edge X")
    padd("dbk_w",  "0.3125 in", "in", "Drawer back sliding dovetail width (5/16)")
    padd("dbk_d",  "0.15625 in","in", "Drawer back dovetail depth into side (5/32)")
    padd("dbk_ovl","0.05 in",   "in", "Drawer back dovetail root overlap")
    padd("dbk_yc", "drw_d - 0.4375 in - drw_bk_t / 2", "in", "Drawer back centerline Y (local)")
    padd("dbk_rw", "dbk_w - 2 * (dbk_d + dbk_ovl) * tan(8 deg)", "in", "Drawer back dovetail root width")
    padd("drw_bg_d", "0.15625 in", "in", "Drawer bottom groove depth (5/32)")
    half_blind_dovetail.define_params(params, prefix="hbd",
        angle="8 deg", tail_w="1.25 in", tail_count="3",
        joint_h_expr="drw_sh", pin_thick_expr="drw_ft", lap="drw_lap")
    dw_z_pl = sp.off_plane(drawers_c, root.xYConstructionPlane,
                           "z_dsh + board_t", "Drw_Z_Pl")
    dbk_z_pl = sp.off_plane(drawers_c, root.xYConstructionPlane,
                            "z_dsh + board_t + 0.625 in", "DrwBk_Z_Pl")
    dbot_z_pl = sp.off_plane(drawers_c, root.xYConstructionPlane,
                             "z_dsh + board_t + 0.1875 in", "DrwBot_Z_Pl")
    dknob_pl = sp.off_plane(drawers_c, root.xYConstructionPlane,
                            "z_dsh + board_t + drw_fh / 2", "DrwKnob_Pl")

    def build_drawer(s, x0e):
        x0 = ev(x0e)
        zsh = ev("z_dsh") + ev("board_t")
        # Anchor parent: the front rail's bottom face (single clean face —
        # the drawer shelf's top face is fragmented by the spline grooves)
        rail_seed = P(ev("stile_in"), 0, ev("z_rail"))
        # Front (11/16 x 5-5/8 x 8-5/8)
        pr = arect(drawers_c, dw_z_pl, ("x", "y"), "z_dsh + board_t",
                   x0e, "0 in", f"({x0e}) + drw_w", "drw_ft", f"{s}_Front_Sk",
                   anchor_face=(rail_f, case_occ, "z", -1), seed=rail_seed,
                   off=(("x", f"({x0e}) - stile_in"), ("y", "0 in")))
        front = sp.ext_new(drawers_c, pr, "drw_fh", f"{s}_Front_Ext").bodies.item(0)
        front.name = f"{s}_Front"
        # Left side (7/16 x 5-1/2; the 12-3/8 cut-list length INCLUDES the
        # dovetail tails). The slab body starts at the front's inner face —
        # only the joined tails penetrate forward to the 1/4 lap, so the
        # front gets true dovetail sockets, not a full-width housing.
        pr = arect(drawers_c, dw_z_pl, ("x", "y"), "z_dsh + board_t",
                   x0e, "drw_ft", f"({x0e}) + drw_st", "drw_d", f"{s}_SideL_Sk",
                   anchor_face=(rail_f, case_occ, "z", -1), seed=rail_seed,
                   off=(("x", f"({x0e}) - stile_in"), ("y", "drw_ft")))
        side_dl = sp.ext_new(drawers_c, pr, "drw_sh", f"{s}_SideL_Ext").bodies.item(0)
        side_dl.name = f"{s}_SideL"
        dx_mid = sp.off_plane(drawers_c, root.yZConstructionPlane,
                              f"({x0e}) + drw_w / 2", f"{s}_XMid")
        side_dr = sp.mirror_body(drawers_c, side_dl, dx_mid, f"{s}_SideR_Mir").bodies.item(0)
        side_dr.name = f"{s}_SideR"
        # Half-blind dovetails at the front (3 tails)
        dfl_pl = sp.off_plane(drawers_c, root.yZConstructionPlane, x0e, f"{s}_FL_Pl")
        half_blind_dovetail.box(drawers_c, front, side_dl,
            dx_mid, dx_mid,
            pin_thick_expr="drw_ft", tail_thick_expr="drw_st",
            right=side_dr, back=None,
            prefix="hbd", name=f"HBD_{s}", ev=ev,
            fl_plane=dfl_pl, front_expr="0 in",
            joint_axis="z", thick_axis="y",
            joint_base_expr="z_dsh + board_t",
            anchor=dict(parent_body=rail_f, parent_occ=case_occ,
                        face_axis="z", face_dir=-1,
                        anchor_xyz=(x0e, "0 in", "z_rail"),
                        off1=("y", "drw_ft"),
                        off2=("z", "open_dr - hbd_pad - hbd_pin_w / 2 - hbd_socket_depth * tan(hbd_angle)")))
        # Back (3/8 x 4-7/8 x 8-1/16) with sliding dovetail ends
        pr = arect(drawers_c, dbk_z_pl, ("x", "y"), "z_dsh + board_t + 0.625 in",
                   f"({x0e}) + drw_st", "dbk_yc - drw_bk_t / 2",
                   f"({x0e}) + drw_w - drw_st", "dbk_yc + drw_bk_t / 2",
                   f"{s}_Back_Sk",
                   anchor_face=(side_dl, None, "y", 1),
                   seed=P(x0 + ev("drw_st"), ev("drw_d"),
                          zsh + 0.625 * 2.54),
                   off=(("x", "0 in"), ("y", "drw_d - dbk_yc - drw_bk_t / 2")))
        back_bd = sp.ext_new(drawers_c, pr, "drw_bk_h", f"{s}_Back_Ext").bodies.item(0)
        back_bd.name = f"{s}_Back"
        # Sliding dovetail tails on the back ends (vertical, 5/16 wide,
        # 5/32 into each side)
        tsk = drawers_c.sketches.add(dbk_z_pl); tsk.name = f"{s}_BkDT_Sk"
        sp.project_face(tsk, side_dl, None, "y", 1)
        m = tsk.modelToSketchSpace
        x_in = x0 + ev("drw_st")
        x_t = x_in - ev("dbk_d"); x_r = x_in + ev("dbk_ovl")
        yc = ev("dbk_yc"); hw = ev("dbk_w") / 2; rw2 = ev("dbk_rw") / 2
        TT = m(P(x_t, yc + hw, 0)); TB = m(P(x_t, yc - hw, 0))
        RT = m(P(x_r, yc + rw2, 0)); RB = m(P(x_r, yc - rw2, 0))
        L = tsk.sketchCurves.sketchLines
        l_tip = L.addByTwoPoints(P(TB.x, TB.y, 0), P(TT.x, TT.y, 0))
        l_t = L.addByTwoPoints(l_tip.endSketchPoint, P(RT.x, RT.y, 0))
        l_root = L.addByTwoPoints(l_t.endSketchPoint, P(RB.x, RB.y, 0))
        l_b = L.addByTwoPoints(l_root.endSketchPoint, l_tip.startSketchPoint)
        gc = tsk.geometricConstraints
        for ln in (l_tip, l_root):
            a_ = ln.startSketchPoint.geometry; b_ = ln.endSketchPoint.geometry
            if abs(b_.x - a_.x) >= abs(b_.y - a_.y):
                gc.addHorizontal(ln)
            else:
                gc.addVertical(ln)
        ori = sp.probe_orientations(tsk, x_in, yc, zsh + 0.625 * 2.54)
        d = tsk.sketchDimensions
        sp.rdim(tsk, d, l_tip.startSketchPoint, l_tip.endSketchPoint, ori, "y", "dbk_w")
        sp.rdim(tsk, d, l_root.startSketchPoint, l_root.endSketchPoint, ori, "y", "dbk_rw")
        sp.rdim(tsk, d, l_tip.endSketchPoint, l_t.endSketchPoint, ori, "x", "dbk_d + dbk_ovl")
        sp.rdim(tsk, d, l_tip.endSketchPoint, l_t.endSketchPoint, ori, "y",
                "(dbk_w - dbk_rw) / 2")
        ap = sp.anchor_pt(tsk, x_in, ev("drw_d"), zsh + 0.625 * 2.54)
        if ap is not None:
            sp.rdim(tsk, d, ap, l_t.endSketchPoint, ori, "x", "dbk_ovl")
            sp.rdim(tsk, d, ap, l_t.endSketchPoint, ori, "y",
                    "drw_d - dbk_yc - dbk_rw / 2")
        else:
            print(f"  {s}: back dovetail anchor not found")
        g = l_t.endSketchPoint.geometry
        if (g.x - RT.x) ** 2 + (g.y - RT.y) ** 2 > 0.0004:
            raise RuntimeError(f"{s} back dovetail moved")
        sp.refs_to_construction(tsk)
        bdt_l = sp.ext_new(drawers_c, sp.smallest_profile(tsk), "drw_bk_h",
                           f"{s}_BkDTL_Ext").bodies.item(0)
        bdt_l.name = f"{s}_BkDT_L"
        bdt_r = sp.mirror_body(drawers_c, bdt_l, dx_mid, f"{s}_BkDTR_Mir").bodies.item(0)
        bdt_r.name = f"{s}_BkDT_R"
        sp.combine(side_dl, bdt_l, CUT, True, f"{s}_BkDado_L")
        sp.combine(side_dr, bdt_r, CUT, True, f"{s}_BkDado_R")
        sp.combine(back_bd, [bdt_l, bdt_r], JOIN, False, f"{s}_BkDT_Join")
        # Bottom (5/16, rabbeted tongues into 5/32 grooves it cuts itself)
        pr = arect(drawers_c, dbot_z_pl, ("x", "y"), "z_dsh + board_t + 0.1875 in",
                   f"({x0e}) + drw_st - drw_bg_d", "drw_ft - drw_bg_d",
                   f"({x0e}) + drw_w - drw_st + drw_bg_d", "drw_d",
                   f"{s}_Bottom_Sk",
                   anchor_face=(side_dl, None, "y", 1),
                   seed=P(x_in, ev("drw_d"), zsh + 0.1875 * 2.54),
                   off=(("x", "drw_bg_d"), ("y", "0 in")))
        dbot = sp.ext_new(drawers_c, pr, "drw_bot_t", f"{s}_Bottom_Ext").bodies.item(0)
        dbot.name = f"{s}_Bottom"
        # Edge rabbets (leave a 3/16 tongue at the top of the panel edges)
        for tag, ua, va, ub, vb, sx, sy, oxe, oye in [
            ("F", f"({x0e}) + drw_st - drw_bg_d - 0.1 in", "drw_ft - drw_bg_d",
             f"({x0e}) + drw_w - drw_st + drw_bg_d + 0.1 in", "drw_ft",
             x0 + ev("drw_st") - ev("drw_bg_d"), ev("drw_ft") - ev("drw_bg_d"),
             "0.1 in", "0 in"),
            ("L", f"({x0e}) + drw_st - drw_bg_d", "drw_ft - drw_bg_d - 0.1 in",
             f"({x0e}) + drw_st", "drw_d + 0.1 in",
             x0 + ev("drw_st") - ev("drw_bg_d"), ev("drw_d"),
             "0 in", "0.1 in"),
            ("R", f"({x0e}) + drw_w - drw_st", "drw_ft - drw_bg_d - 0.1 in",
             f"({x0e}) + drw_w - drw_st + drw_bg_d", "drw_d + 0.1 in",
             x0 + ev("drw_w") - ev("drw_st") + ev("drw_bg_d"), ev("drw_d"),
             "0 in", "0.1 in"),
        ]:
            pr = arect(drawers_c, dbot_z_pl, ("x", "y"),
                       "z_dsh + board_t + 0.1875 in",
                       ua, va, ub, vb, f"{s}_BotRab{tag}_Sk",
                       anchor_face=(dbot, None, "z", -1),
                       seed=P(sx, sy, zsh + 0.1875 * 2.54),
                       off=(("x", oxe), ("y", oye)))
            sp.ext_op(drawers_c, pr, "drw_bot_t - drw_bg_d - 0.03125 in", CUT,
                      dbot, f"{s}_BotRab{tag}")
        # The panel cuts its own grooves in the front and sides
        sp.combine(front, dbot, CUT, True, f"{s}_BotGrvF")
        sp.combine(side_dl, dbot, CUT, True, f"{s}_BotGrvL")
        sp.combine(side_dr, dbot, CUT, True, f"{s}_BotGrvR")
        # Knob (turned: 3/8 tenon, 1/2 base, 5/16 waist, 13/16 cap)
        ksk = drawers_c.sketches.add(dknob_pl); ksk.name = f"{s}_Knob_Sk"
        sp.project_face(ksk, front, None, "y", -1)
        m = ksk.modelToSketchSpace
        kz = ev("z_dsh") + ev("board_t") + ev("drw_fh") / 2
        xc = x0 + ev("drw_w") / 2
        A = m(P(xc, 0.625 * 2.54, 0)); B = m(P(xc + 0.1875 * 2.54, 0.625 * 2.54, 0))
        C = m(P(xc + 0.1875 * 2.54, 0, 0)); D = m(P(xc + 0.25 * 2.54, 0, 0))
        E = m(P(xc + 0.15625 * 2.54, -0.35 * 2.54, 0))
        F = m(P(xc + 0.40625 * 2.54, -0.85 * 2.54, 0))
        G = m(P(xc, -1.125 * 2.54, 0))
        coll = adsk.core.ObjectCollection.create()
        for q in (D, E, F, G):
            coll.add(P(q.x, q.y, 0))
        spl = ksk.sketchCurves.sketchFittedSplines.add(coll)
        L = ksk.sketchCurves.sketchLines
        k1 = L.addByTwoPoints(P(A.x, A.y, 0), P(B.x, B.y, 0))
        k2 = L.addByTwoPoints(k1.endSketchPoint, P(C.x, C.y, 0))
        k3 = L.addByTwoPoints(k2.endSketchPoint, P(D.x, D.y, 0))
        gc = ksk.geometricConstraints
        gc.addCoincident(k3.endSketchPoint, spl.startSketchPoint)
        k_ax = L.addByTwoPoints(spl.endSketchPoint, k1.startSketchPoint)
        for ln in (k1, k2, k3, k_ax):
            a_ = ln.startSketchPoint.geometry; b_ = ln.endSketchPoint.geometry
            if abs(b_.x - a_.x) >= abs(b_.y - a_.y):
                gc.addHorizontal(ln)
            else:
                gc.addVertical(ln)
        ori = sp.probe_orientations(ksk, xc, 0, kz)
        d = ksk.sketchDimensions
        sp.rdim(ksk, d, k1.startSketchPoint, k1.endSketchPoint, ori, "x", "0.1875 in")
        sp.rdim(ksk, d, k2.startSketchPoint, k2.endSketchPoint, ori, "y", "0.625 in")
        sp.rdim(ksk, d, k3.startSketchPoint, k3.endSketchPoint, ori, "x", "0.0625 in")
        sp.rdim(ksk, d, k_ax.startSketchPoint, k_ax.endSketchPoint, ori, "y", "1.75 in")
        ap = sp.anchor_pt(ksk, x0, 0, kz)
        if ap is not None:
            sp.rdim(ksk, d, ap, k2.endSketchPoint, ori, "x", "drw_w / 2 + 0.1875 in")
            sp.rdim(ksk, d, ap, k2.endSketchPoint, ori, "y", "0 in")
        g = k2.endSketchPoint.geometry
        if (g.x - C.x) ** 2 + (g.y - C.y) ** 2 > 0.0004:
            raise RuntimeError(f"{s} knob moved")
        sp.refs_to_construction(ksk)
        rin = drawers_c.features.revolveFeatures.createInput(
            sp.smallest_profile(ksk), k_ax, NEW)
        rin.setAngleExtent(False, VI("360 deg"))
        knob = drawers_c.features.revolveFeatures.add(rin).bodies.item(0)
        knob.name = f"{s}_Knob"
        sp.combine(front, knob, CUT, True, f"{s}_KnobMort")
        return front

    build_drawer("D1", "stile_in")
    build_drawer("D2", "d2_x0")
    print(f">>> Drawers: {drawers_c.bRepBodies.count} bodies (12 expected)")

    # ════════ epilogue ════════
    all_comps = [base_c, case_c, back_c, top_c, drawers_c]
    for c in all_comps:
        for s in c.sketches: s.isVisible = False
        for cp in c.constructionPlanes: cp.isLightBulbOn = False
    total = sum(c.bRepBodies.count for c in all_comps)
    print(f"Total bodies: {total}")

    # ── Appearance: figured maple case, sapele (bubinga stand-in) base,
    #    drawer fronts and knobs ──
    base_names = [base_c.bRepBodies.item(i).name
                  for i in range(base_c.bRepBodies.count)]
    sp.apply_appearance("maple")
    sp.apply_appearance("sapele", bodies=base_names +
                        ["D1_Front", "D2_Front", "D1_Knob", "D2_Knob"])
    print(">>> Appearance: maple + sapele base/drawer fronts")

    sp.validate_deps(ctx, metadata_path="/Users/frankzha/shopprentice-projects/bookcase-with-drawers/model.json")
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
    print(">>> BOOKCASE WITH DRAWERS BUILD COMPLETE")
