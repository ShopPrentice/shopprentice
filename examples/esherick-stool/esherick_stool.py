"""Wharton Esherick Three-Legged Stool (1958 style)

Build order:
  1. Seat (spline hex + spherical scoop)
  2. Legs (revolve + splay) — tenons protrude through seat
  3. Wedge slots on leg tenons
  4. Split legs+wedges at seat top surface, remove excess above
  5. CUT seat with trimmed leg tenons (mortise)
  6. Stretchers (barrel profile, staggered heights)
  7. Wedge slots on stretcher tenons
  8. Split stretchers+wedges at leg surface, join interior, remove exterior
  9. CUT legs with trimmed stretcher tenons (mortise)
  10. Details (fillets)

Components: Seat, Legs, Stretchers
"""
import adsk.core, adsk.fusion, math
from helpers import sp

P = adsk.core.Point3D.create
VI = adsk.core.ValueInput.createByString
NEWBODY = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
AL = adsk.fusion.DimensionOrientations.AlignedDimensionOrientation


def run(context):
    ctx = sp.DesignContext()
    design = ctx.design
    root = ctx.root
    params = ctx.params
    ev = ctx.ev

    # ── PARAMETERS ────────────────────────────────────────────────
    for name, expr, unit, comment in [
        ("seat_w", "15 in", "in", "Seat max width (Y)"),
        ("seat_d", "14 in", "in", "Seat max depth (X)"),
        ("seat_t", "1.25 in", "in", "Seat thickness"),
        ("scoop_depth", "0.3 in", "in", "Seat scoop depth"),
        ("scoop_r", "30 in", "in", "Scoop sphere radius"),
        ("leg_h", "24 in", "in", "Leg height floor to seat bottom"),
        ("leg_top_dia", "0.875 in", "in", "Leg diameter at seat entry"),
        ("leg_mid_dia", "1.5 in", "in", "Leg max diameter at swell"),
        ("leg_bot_dia", "0.625 in", "in", "Leg diameter at floor"),
        ("leg_tip_dia", "0.5 in", "in", "Leg diameter at very tip"),
        ("leg_swell_ratio", "0.30", "", "Swell position from bottom (0-1)"),
        ("splay", "8 deg", "deg", "Leg splay from vertical"),
        ("tenon_proud", "0.25 in", "in", "Through-tenon above seat"),
        ("tenon_dia", "0.75 in", "in", "Through-tenon diameter above seat"),
        ("str_h1", "5.5 in", "in", "Stretcher 1-2 height"),
        ("str_h2", "7 in", "in", "Stretcher 2-3 height"),
        ("str_h3", "8.5 in", "in", "Stretcher 3-1 height"),
        ("ts_mid_dia", "0.75 in", "in", "Stretcher body diameter"),
        ("ts_end_dia", "0.5 in", "in", "Stretcher tenon diameter"),
        ("ts_tenon_len", "1.5 in", "in", "Stretcher tenon length"),
        ("ts_shoulder_len", "0.25 in", "in", "Shoulder transition"),
        ("ts_ext", "0.25 in", "in", "Tenon extension beyond leg surface"),
        ("ts_barrel_dist", "2 in", "in", "Barrel ctrl point dist from mid"),
        ("ts_barrel_r", "0.4 in", "in", "Barrel ctrl point radius"),
        ("leg_spread", "4 in", "in", "Leg center distance from seat center"),
        ("seat_top_fil", "1 in", "in", "Seat top edge fillet"),
        ("seat_bot_fil", "0.25 in", "in", "Seat bottom edge fillet"),
        ("leg_bot_ch", "0.0625 in", "in", "Leg bottom chamfer"),
    ]:
        if not params.itemByName(name):
            params.add(name, VI(expr), unit, comment)

    for name, expr, unit, comment in [
        ("seat_z", "leg_h", "in", "Seat bottom Z"),
        ("leg_top_z", "leg_h + seat_t + tenon_proud", "in", "Leg top Z"),
        ("splay_shift", "leg_top_z * tan(splay)", "in", "Foot splay offset"),
        ("leg_swell_z", "leg_top_z * leg_swell_ratio", "in", "Swell height"),
    ]:
        if not params.itemByName(name):
            params.add(name, VI(expr), unit, comment)

    cx = ev("seat_d") / 2
    cy = ev("seat_w") / 2
    sw = ev("seat_w")
    sd = ev("seat_d")

    tv = [
        (cx + sd * 0.45, cy),
        (cx - sd * 0.40, cy - sw * 0.45),
        (cx - sd * 0.40, cy + sw * 0.45),
    ]
    tri_cx = (tv[0][0] + tv[1][0] + tv[2][0]) / 3
    tri_cy = (tv[0][1] + tv[1][1] + tv[2][1]) / 3
    leg_angles_rad = [math.atan2(vy - tri_cy, vx - tri_cx) for vx, vy in tv]

    # ── COMPONENTS ────────────────────────────────────────────────
    seat_occ = sp.make_comp(root, "Seat")
    seat_comp = seat_occ.component
    legs_occ = sp.make_comp(root, "Legs")
    legs_comp = legs_occ.component
    str_occ = sp.make_comp(root, "Stretchers")
    str_comp = str_occ.component

    # ══════════════════════════════════════════════════════════════
    # STEP 1: SEAT
    # ══════════════════════════════════════════════════════════════
    clip = 0.15
    hex_verts = []
    for i in range(3):
        j = (i + 1) % 3
        x0, y0 = tv[i]; x1, y1 = tv[j]
        dx, dy = x1 - x0, y1 - y0
        hex_verts.append((x0 + clip * dx, y0 + clip * dy))
        hex_verts.append((x1 - clip * dx, y1 - clip * dy))

    seat_pts = []
    bulge_long = 0.06
    bulge_short = 0.04
    for i in range(6):
        seat_pts.append(hex_verts[i])
        j = (i + 1) % 6
        mx = (hex_verts[i][0] + hex_verts[j][0]) / 2
        my = (hex_verts[i][1] + hex_verts[j][1]) / 2
        ex = hex_verts[j][0] - hex_verts[i][0]
        ey = hex_verts[j][1] - hex_verts[i][1]
        el = math.sqrt(ex*ex + ey*ey)
        nx, ny = -ey/el, ex/el
        dx_c = mx - tri_cx; dy_c = my - tri_cy
        if nx * dx_c + ny * dy_c < 0: nx, ny = -nx, -ny
        bulge = bulge_long if (i % 2 == 0) else bulge_short
        seat_pts.append((mx + nx * el * bulge, my + ny * el * bulge))

    seat_pl = sp.off_plane(seat_comp, seat_comp.xYConstructionPlane,
                           "seat_z", "Seat_Pl")
    sk = seat_comp.sketches.add(seat_pl)
    sk.name = "Seat_Sk"
    m2s = sk.modelToSketchSpace
    pts_sk = adsk.core.ObjectCollection.create()
    for mx, my in seat_pts:
        p = m2s(P(mx, my, ev("seat_z")))
        pts_sk.add(P(p.x, p.y, 0))
    spline = sk.sketchCurves.sketchFittedSplines.add(pts_sk)
    spline.isClosed = True
    prof = sp.smallest_profile(sk)
    seat_ext = sp.ext_new(seat_comp, prof, "seat_t", "SeatBoard")
    seat_body = seat_ext.bodies.item(0)
    seat_body.name = "Seat"

    # Scoop (spherical)
    top_z = ev("seat_z") + ev("seat_t")
    scoop_r = ev("scoop_r")
    scoop_d = ev("scoop_depth")
    sphere_cz = top_z + scoop_r - scoop_d
    scoop_pl = sp.off_plane(seat_comp, seat_comp.yZConstructionPlane,
                            f"{tri_cx} cm", "Scoop_Pl")
    sk_sc = seat_comp.sketches.add(scoop_pl)
    sk_sc.name = "Scoop_Sk"
    m2s_sc = sk_sc.modelToSketchSpace
    sc_center = m2s_sc(P(tri_cx, tri_cy, sphere_cz))
    sc_top = m2s_sc(P(tri_cx, tri_cy, sphere_cz + scoop_r))
    sc_bot = m2s_sc(P(tri_cx, tri_cy, sphere_cz - scoop_r))
    sc_right = m2s_sc(P(tri_cx, tri_cy + scoop_r, sphere_cz))
    arc = sk_sc.sketchCurves.sketchArcs.addByThreePoints(
        P(sc_bot.x, sc_bot.y, 0), P(sc_right.x, sc_right.y, 0),
        P(sc_top.x, sc_top.y, 0))
    dia_line = sk_sc.sketchCurves.sketchLines.addByTwoPoints(
        arc.endSketchPoint, arc.startSketchPoint)
    scoop_prof = sp.smallest_profile(sk_sc)
    rev_inp = seat_comp.features.revolveFeatures.createInput(
        scoop_prof, dia_line, NEWBODY)
    rev_inp.setAngleExtent(False, VI("360 deg"))
    sphere_feat = seat_comp.features.revolveFeatures.add(rev_inp)
    sphere_feat.name = "ScoopSphere"
    sphere_body = sphere_feat.bodies.item(0)
    sphere_body.name = "ScoopTool"
    sp.combine(seat_comp, seat_body, sphere_body, CUT, False, "SeatScoop")
    print("Seat + scoop done")

    # ══════════════════════════════════════════════════════════════
    # STEP 2: LEGS (no mortise CUT yet)
    # ══════════════════════════════════════════════════════════════
    leg_sk = legs_comp.sketches.add(legs_comp.xZConstructionPlane)
    leg_sk.name = "Leg_Sk"
    m2s_leg = leg_sk.modelToSketchSpace
    tenon_r = ev("tenon_dia") / 2
    seat_z_val = ev("seat_z")
    top_z_val = ev("leg_top_z")

    ax_bot_s = m2s_leg(P(0, 0, 0))
    ax_top_s = m2s_leg(P(0, 0, top_z_val))
    lns = leg_sk.sketchCurves.sketchLines
    ax_line = lns.addByTwoPoints(P(ax_bot_s.x, ax_bot_s.y, 0),
                                  P(ax_top_s.x, ax_top_s.y, 0))
    ax_line.isConstruction = True

    profile_points = [
        (0.6350, 0.0), (0.8009, 0.0467), (0.9269, 0.4374),
        (1.1034, 2.0844), (1.6441, 14.7896), (1.7780, 20.0660),
        (1.7813, 25.9935), (1.6417, 34.1837), (1.4362, 42.3219),
        (1.2881, 50.7089), (1.1663, 56.8458), (1.1113, 60.96),
    ]
    spl_pts = adsk.core.ObjectCollection.create()
    for r, z in profile_points:
        p = m2s_leg(P(r, 0, z))
        spl_pts.add(P(p.x, p.y, 0))
    spline_leg = leg_sk.sketchCurves.sketchFittedSplines.add(spl_pts)

    ln_bot = lns.addByTwoPoints(P(ax_bot_s.x, ax_bot_s.y, 0),
                                 spline_leg.startSketchPoint)
    p_tb = m2s_leg(P(tenon_r, 0, seat_z_val))
    ln_sh = lns.addByTwoPoints(spline_leg.endSketchPoint,
                                P(p_tb.x, p_tb.y, 0))
    p_tt = m2s_leg(P(tenon_r, 0, top_z_val))
    ln_tn = lns.addByTwoPoints(ln_sh.endSketchPoint, P(p_tt.x, p_tt.y, 0))
    ln_tp = lns.addByTwoPoints(ln_tn.endSketchPoint,
                                P(ax_top_s.x, ax_top_s.y, 0))
    ln_ax = lns.addByTwoPoints(ln_tp.endSketchPoint,
                                P(ax_bot_s.x, ax_bot_s.y, 0))
    leg_sk.geometricConstraints.addCoincident(
        ln_ax.endSketchPoint, ln_bot.startSketchPoint)
    leg_prof = sp.smallest_profile(leg_sk)

    leg_r = ev("leg_spread")
    splay_val = ev("splay")
    legs = []

    for i, angle_rad in enumerate(leg_angles_rad):
        rev_inp = legs_comp.features.revolveFeatures.createInput(
            leg_prof, ax_line, NEWBODY)
        rev_inp.setAngleExtent(False, VI("360 deg"))
        rev_feat = legs_comp.features.revolveFeatures.add(rev_inp)
        rev_feat.name = f"Leg{i+1}_Rev"
        body = rev_feat.bodies.item(0)
        body.name = f"Leg{i+1}"

        tx = tri_cx + leg_r * math.cos(angle_rad)
        ty = tri_cy + leg_r * math.sin(angle_rad)
        tax = -math.sin(angle_rad)
        tay = math.cos(angle_rad)
        c_s = math.cos(-splay_val); s_s = math.sin(-splay_val)
        ux, uy = tax, tay
        rot = [
            [c_s+ux*ux*(1-c_s), ux*uy*(1-c_s),      uy*s_s],
            [uy*ux*(1-c_s),     c_s+uy*uy*(1-c_s),  -ux*s_s],
            [-uy*s_s,           ux*s_s,               c_s],
        ]
        piv = [tx, ty, top_z_val]
        d = [0, 0, -top_z_val]
        rd = [sum(rot[r][c]*d[c] for c in range(3)) for r in range(3)]
        ft = [rd[j]+piv[j] for j in range(3)]
        xform = adsk.core.Matrix3D.create()
        xform.setWithArray([
            rot[0][0], rot[0][1], rot[0][2], ft[0],
            rot[1][0], rot[1][1], rot[1][2], ft[1],
            rot[2][0], rot[2][1], rot[2][2], ft[2],
            0, 0, 0, 1
        ])
        move_coll = adsk.core.ObjectCollection.create()
        move_coll.add(body)
        move_inp = legs_comp.features.moveFeatures.createInput2(move_coll)
        move_inp.defineAsFreeMove(xform)
        legs_comp.features.moveFeatures.add(move_inp).name = f"Leg{i+1}_Move"
        legs.append(body)
        print(f"Leg{i+1} positioned")

    # ══════════════════════════════════════════════════════════════
    # STEP 3: WEDGE SLOTS ON LEG TENONS (inside Legs component)
    # ══════════════════════════════════════════════════════════════
    from woodworking.templates import tenon_wedge as tw
    tw.define_params(params, prefix="tw", slot_w="0.1 in",
                     depth_ratio="2 / 3", offset_ratio="1 / 4")

    for i, leg in enumerate(legs):
        end_face = sp.find_face(leg, "z", +1)
        try:
            tw.round_tenon(legs_comp, tenon_body=leg, mortise_body=seat_body,
                           end_face=end_face,
                           tenon_depth_expr="seat_t",
                           tenon_diam_expr="tenon_dia",
                           grain_dir=(0, 1, 0),
                           prefix="tw", name=f"TW_L{i+1}", ev=ev)
            print(f"Leg{i+1} wedge done")
        except Exception as e:
            print(f"Leg{i+1} wedge failed: {e}")

    # ══════════════════════════════════════════════════════════════
    # STEP 4: SPLIT LEGS+WEDGES AT SEAT TOP, REMOVE EXCESS
    # ══════════════════════════════════════════════════════════════
    # Approach (from user):
    #   1. One split per body using seat top face (splits all at once)
    #   2. Single pass: remove ALL fragments above seat
    #   3. Single pass: join remaining fragments back to parent leg
    seat_proxy = seat_body.createForAssemblyContext(seat_occ)

    # Split all 6 bodies (3 legs + 3 wedges) using the ENTIRE seat body
    # as the split tool — this follows scoop, fillets, and all surface geometry
    leg_proxies = [leg.createForAssemblyContext(legs_occ) for leg in legs]
    all_bodies_to_split = list(legs)
    for i in range(3):
        for bi in range(legs_comp.bRepBodies.count):
            b = legs_comp.bRepBodies.item(bi)
            if b.name == f"TW_L{i+1}":
                all_bodies_to_split.append(b); break

    for b in all_bodies_to_split:
        bp = b.createForAssemblyContext(legs_occ)
        try:
            split_inp = root.features.splitBodyFeatures.createInput(
                bp, seat_proxy, True)
            root.features.splitBodyFeatures.add(split_inp)
        except: pass  # body may not intersect the seat
    print("Split all legs+wedges using seat body surface")

    # Single pass: remove ALL fragments above the seat
    removed = 0
    for bi in range(legs_comp.bRepBodies.count - 1, -1, -1):
        b = legs_comp.bRepBodies.item(bi)
        if sp.body_side(b, seat_body, (0, 0, 1)) == 'outside':
            try:
                root.features.removeFeatures.add(
                    b.createForAssemblyContext(legs_occ))
                removed += 1
            except: pass
    print(f"Removed {removed} fragments above seat")

    # Single pass: join remaining fragments back to their parent leg
    # The main leg body is the largest; smaller fragments are tenon
    # pieces inside the seat that got separated by the split
    for i in range(3):
        main = None; frags = []; main_vol = 0
        for bi in range(legs_comp.bRepBodies.count):
            b = legs_comp.bRepBodies.item(bi)
            if f"Leg{i+1}" in b.name:
                if b.volume > main_vol:
                    if main: frags.append(main)
                    main = b; main_vol = b.volume
                else:
                    frags.append(b)
        if main and frags:
            main_proxy = main.createForAssemblyContext(legs_occ)
            for frag in frags:
                try:
                    sp.combine(root, main_proxy,
                               frag.createForAssemblyContext(legs_occ),
                               JOIN, False, f"Leg{i+1}_Rejoin")
                except: pass
    print("Joined leg fragments")

    # Refresh leg references
    legs = []
    for i in range(3):
        best = None; best_vol = 0
        for bi in range(legs_comp.bRepBodies.count):
            b = legs_comp.bRepBodies.item(bi)
            if f"Leg{i+1}" in b.name and b.volume > best_vol:
                best = b; best_vol = b.volume
        if best: legs.append(best)
    leg_proxies = [leg.createForAssemblyContext(legs_occ) for leg in legs]
    print(f"Refreshed {len(legs)} legs")

    # ══════════════════════════════════════════════════════════════
    # STEP 5: CUT SEAT WITH TRIMMED LEG TENONS (mortise)
    # ══════════════════════════════════════════════════════════════
    for i, lp in enumerate(leg_proxies):
        sp.combine(root, seat_proxy, lp, CUT, True, f"Leg{i+1}_Mortise")
    print("Leg mortises cut with trimmed tenons")

    # ══════════════════════════════════════════════════════════════
    # STEP 6: STRETCHERS
    # ══════════════════════════════════════════════════════════════
    def get_leg_axis(body):
        best = None; best_area = 0
        for fi in range(body.faces.count):
            f = body.faces.item(fi)
            if isinstance(f.geometry, adsk.core.Cylinder):
                if f.area > best_area:
                    best_area = f.area; best = f
        if not best:
            print(f"WARNING: no cylindrical face on {body.name}")
            return None, None
        cyl = best.geometry
        d = cyl.axis.copy(); d.normalize()
        return cyl.origin, d

    leg_data = [get_leg_axis(leg) for leg in legs]
    for i, (o, d) in enumerate(leg_data):
        if o:
            print(f"Leg{i+1} axis: origin=({o.x:.1f},{o.y:.1f},{o.z:.1f})")
        else:
            print(f"Leg{i+1} axis: NOT FOUND")

    def axis_pt_at_z(origin, direction, z):
        t = (z - origin.z) / direction.z
        return P(origin.x + direction.x*t,
                 origin.y + direction.y*t,
                 origin.z + direction.z*t)

    connections = [
        (0, 1, "Str_12", "str_h1"),
        (1, 2, "Str_23", "str_h2"),
        (2, 0, "Str_31", "str_h3"),
    ]

    str_bodies = []
    for a_idx, b_idx, str_name, h_param in connections:
        str_h = ev(h_param)
        s_pl = sp.off_plane(str_comp, str_comp.xYConstructionPlane,
                            h_param, f"{str_name}_HPl")
        orig_a, dir_a = leg_data[a_idx]
        orig_b, dir_b = leg_data[b_idx]
        pa = axis_pt_at_z(orig_a, dir_a, str_h)
        pb = axis_pt_at_z(orig_b, dir_b, str_h)

        tmp_sk = str_comp.sketches.add(s_pl)
        tmp_sk.name = f"{str_name}_Tmp"
        m2s_t = tmp_sk.modelToSketchSpace
        pa_s = m2s_t(pa); pb_s = m2s_t(pb)
        sp_a = tmp_sk.sketchPoints.add(P(pa_s.x, pa_s.y, 0))
        sp_b = tmp_sk.sketchPoints.add(P(pb_s.x, pb_s.y, 0))
        cp_a_inp = str_comp.constructionPoints.createInput()
        cp_a_inp.setByPoint(sp_a)
        cp_a = str_comp.constructionPoints.add(cp_a_inp)
        cp_a.name = f"{str_name}_CpA"
        cp_b_inp = str_comp.constructionPoints.createInput()
        cp_b_inp.setByPoint(sp_b)
        cp_b = str_comp.constructionPoints.add(cp_b_inp)
        cp_b.name = f"{str_name}_CpB"

        ax_inp = str_comp.constructionAxes.createInput()
        ax_inp.setByTwoPoints(cp_a, cp_b)
        str_axis = str_comp.constructionAxes.add(ax_inp)
        str_axis.name = f"{str_name}_Ax"
        prof_pl_inp = str_comp.constructionPlanes.createInput()
        prof_pl_inp.setByAngle(str_axis, VI("90 deg"),
                               str_comp.xYConstructionPlane)
        prof_pl = str_comp.constructionPlanes.add(prof_pl_inp)
        prof_pl.name = f"{str_name}_Pl"

        sk2 = str_comp.sketches.add(prof_pl)
        sk2.name = f"{str_name}_Sk"
        m2s2 = sk2.modelToSketchSpace
        gc2 = sk2.geometricConstraints
        dims = sk2.sketchDimensions
        slines = sk2.sketchCurves.sketchLines
        sk2.project(cp_a); sk2.project(cp_b)
        pa_sk = m2s2(pa); pb_sk = m2s2(pb)
        best_a = None; best_b = None; da_d = 1e10; db_d = 1e10
        for pi in range(sk2.sketchPoints.count):
            pt = sk2.sketchPoints.item(pi)
            if pt == sk2.originPoint: continue
            g = pt.geometry
            d_a = math.sqrt((g.x-pa_sk.x)**2 + (g.y-pa_sk.y)**2)
            d_b = math.sqrt((g.x-pb_sk.x)**2 + (g.y-pb_sk.y)**2)
            if d_a < da_d: da_d = d_a; best_a = pt
            if d_b < db_d: db_d = d_b; best_b = pt
        pa_g = best_a.geometry; pb_g = best_b.geometry
        ctr = slines.addByTwoPoints(P(pa_g.x, pa_g.y, 0),
                                     P(pb_g.x, pb_g.y, 0))
        ctr.isConstruction = True
        gc2.addCoincident(ctr.startSketchPoint, best_a)
        gc2.addCoincident(ctr.endSketchPoint, best_b)

        sdx = pb_g.x-pa_g.x; sdy = pb_g.y-pa_g.y
        sl = math.sqrt(sdx*sdx+sdy*sdy)
        if sl < 0.01:
            print(f"{str_name}: points too close (sl={sl:.4f}), skipping")
            str_bodies.append(None)
            continue
        sux, suy = sdx/sl, sdy/sl
        snx, sny = -suy, sux
        end_r = ev("ts_end_dia")/2; mid_r_s = ev("ts_mid_dia")/2
        body_r_s = ev("leg_mid_dia")/2
        ext_total = body_r_s + ev("ts_ext")
        t_len = ev("ts_tenon_len"); s_len = ev("ts_shoulder_len")

        ea = P(pa_g.x-sux*ext_total, pa_g.y-suy*ext_total, 0)
        eb = P(pb_g.x+sux*ext_total, pb_g.y+suy*ext_total, 0)
        ax_ln = slines.addByTwoPoints(ea, eb)
        gc2.addCollinear(ax_ln, ctr)
        mid_x = (pa_g.x+pb_g.x)/2; mid_y = (pa_g.y+pb_g.y)/2
        mid_con = slines.addByTwoPoints(
            P(mid_x, mid_y, 0), P(mid_x+snx*0.5, mid_y+sny*0.5, 0))
        mid_con.isConstruction = True
        gc2.addMidPoint(mid_con.startSketchPoint, ctr)
        gc2.addMidPoint(mid_con.startSketchPoint, ax_ln)
        ax_len = math.sqrt((eb.x-ea.x)**2 + (eb.y-ea.y)**2)

        def pt_at(dist, radius):
            return P(ea.x+sux*dist+snx*radius, ea.y+suy*dist+sny*radius, 0)

        L1 = slines.addByTwoPoints(P(ea.x,ea.y,0), pt_at(0, end_r))
        gc2.addCoincident(L1.startSketchPoint, ax_ln.startSketchPoint)
        gc2.addPerpendicular(L1, ax_ln)
        L2 = slines.addByTwoPoints(L1.endSketchPoint, pt_at(t_len, end_r))
        gc2.addParallel(L2, ax_ln)
        shoulder_r = (end_r+mid_r_s)/2
        L3 = slines.addByTwoPoints(L2.endSketchPoint,
                                    pt_at(t_len+s_len, shoulder_r))
        body_end = ax_len - t_len - s_len
        barrel_r = ev("ts_barrel_r"); barrel_dist = ev("ts_barrel_dist")
        spl_pts_s = adsk.core.ObjectCollection.create()
        spl_pts_s.add(P(L3.endSketchPoint.geometry.x,
                        L3.endSketchPoint.geometry.y, 0))
        spl_pts_s.add(pt_at(ax_len/2-barrel_dist, barrel_r))
        spl_pts_s.add(pt_at(ax_len/2+barrel_dist, barrel_r))
        spl_pts_s.add(pt_at(body_end, shoulder_r))
        body_spl = sk2.sketchCurves.sketchFittedSplines.add(spl_pts_s)
        try:
            gc2.addCoincident(body_spl.startSketchPoint, L3.endSketchPoint)
        except: pass
        L6 = slines.addByTwoPoints(body_spl.endSketchPoint,
                                    pt_at(ax_len-t_len, end_r))
        L7 = slines.addByTwoPoints(L6.endSketchPoint, pt_at(ax_len, end_r))
        gc2.addParallel(L7, ax_ln)
        L8 = slines.addByTwoPoints(L7.endSketchPoint, P(eb.x,eb.y,0))
        gc2.addCoincident(L8.endSketchPoint, ax_ln.endSketchPoint)
        gc2.addPerpendicular(L8, ax_ln)

        sym = slines.addByTwoPoints(
            P(mid_x,mid_y,0), P(mid_x+snx*3,mid_y+sny*3,0))
        sym.isConstruction = True
        gc2.addPerpendicular(sym, ax_ln)
        gc2.addMidPoint(sym.startSketchPoint, ax_ln)
        gc2.addSymmetry(L1.endSketchPoint, L7.endSketchPoint, sym)
        gc2.addSymmetry(L2.endSketchPoint, L6.endSketchPoint, sym)
        gc2.addSymmetry(L3.endSketchPoint, body_spl.endSketchPoint, sym)
        gc2.addSymmetry(body_spl.fitPoints.item(1),
                        body_spl.fitPoints.item(2), sym)

        dims.addDistanceDimension(
            L1.startSketchPoint, L1.endSketchPoint, AL,
            pt_at(0,end_r+1)).parameter.expression = "ts_end_dia / 2"
        dims.addDistanceDimension(
            L2.startSketchPoint, L2.endSketchPoint, AL,
            pt_at(t_len/2,end_r+1)).parameter.expression = "ts_tenon_len"
        dims.addDistanceDimension(
            L2.endSketchPoint, L3.endSketchPoint, AL,
            pt_at(t_len+s_len/2,mid_r_s+1)
        ).parameter.expression = "ts_shoulder_len"
        ctrl_L = body_spl.fitPoints.item(1)
        ctrl_con = slines.addByTwoPoints(
            P(mid_x-sux*barrel_dist, mid_y-suy*barrel_dist, 0),
            P(ctrl_L.geometry.x, ctrl_L.geometry.y, 0))
        ctrl_con.isConstruction = True
        gc2.addPerpendicular(ctrl_con, ax_ln)
        gc2.addCoincident(ctrl_con.startSketchPoint, ax_ln)
        gc2.addCoincident(ctrl_con.endSketchPoint, ctrl_L)
        dims.addDistanceDimension(
            ctrl_con.startSketchPoint, ctrl_con.endSketchPoint, AL,
            P(mid_x+snx*2,mid_y+sny*2,0)
        ).parameter.expression = "ts_barrel_r"
        dims.addDistanceDimension(
            ctrl_con.startSketchPoint, sym.startSketchPoint, AL,
            P(mid_x-sux*2,mid_y-suy*2,0)
        ).parameter.expression = "ts_barrel_dist"

        str_prof = sp.smallest_profile(sk2)
        rev_inp = str_comp.features.revolveFeatures.createInput(
            str_prof, ax_ln, NEWBODY)
        rev_inp.setAngleExtent(False, VI("360 deg"))
        rev_feat = str_comp.features.revolveFeatures.add(rev_inp)
        rev_feat.name = str_name
        str_body = rev_feat.bodies.item(0)
        str_body.name = str_name
        str_bodies.append(str_body)
        print(f"{str_name} built")

    # Stretcher-to-stretcher overlap fix
    str_proxies = [sb.createForAssemblyContext(str_occ) for sb in str_bodies]
    for i in range(3):
        for j in range(i+1, 3):
            try:
                sp.combine(root, str_proxies[i], str_proxies[j], CUT, True,
                           f"Str{i}{j}_Fix")
            except: pass

    # ══════════════════════════════════════════════════════════════
    # STEP 7: WEDGE SLOTS ON STRETCHER TENONS (inside Stretchers)
    # ══════════════════════════════════════════════════════════════
    for ci, (a_idx, b_idx, str_name, _) in enumerate(connections):
        str_body_local = str_bodies[ci]
        end_faces = []
        for fi in range(str_body_local.faces.count):
            f = str_body_local.faces.item(fi)
            if isinstance(f.geometry, adsk.core.Plane):
                if f.area < 5.0:
                    end_faces.append(f)
        if len(end_faces) >= 2:
            for ei, ef in enumerate(end_faces[:2]):
                leg_idx = a_idx if ei == 0 else b_idx
                try:
                    tw.round_tenon(str_comp, tenon_body=str_body_local,
                                   mortise_body=legs[leg_idx],
                                   end_face=ef,
                                   tenon_depth_expr="ts_tenon_len",
                                   tenon_diam_expr="ts_end_dia",
                                   prefix="tw",
                                   name=f"TW_{str_name}_{ei}",
                                   ev=ev)
                    print(f"{str_name} end {ei} wedge done")
                except Exception as e:
                    print(f"{str_name} end {ei} wedge failed: {e}")

    # ══════════════════════════════════════════════════════════════
    # STEP 8: SPLIT STRETCHERS+WEDGES AT LEG SURFACES, TRIM EXCESS
    # ══════════════════════════════════════════════════════════════
    # For each stretcher end at a leg:
    #   1. Split stretcher + wedges using leg body
    #   2. Direction = stretcher center → leg center (tenon direction)
    #   3. Remove fragments on the FAR side of the leg (body_side == 'outside')
    #   4. Main stretcher body is on the OPPOSITE side → kept
    # After both ends trimmed, join interior tenon pieces back.
    for ci, (a_idx, b_idx, str_name, _) in enumerate(connections):
        str_body_local = str_bodies[ci]
        str_com = str_body_local.physicalProperties.centerOfMass

        for leg_idx in [a_idx, b_idx]:
            leg = legs[leg_idx]
            leg_com = leg.physicalProperties.centerOfMass
            leg_proxy = leg.createForAssemblyContext(legs_occ)

            # Tenon direction: from stretcher center toward this leg (horizontal)
            # Zero out Z — stretchers run level, tenon direction is in XY
            tenon_dir = (
                leg_com.x - str_com.x,
                leg_com.y - str_com.y,
                0,
            )

            # Collect all current bodies for this stretcher + its wedges
            bodies_to_split = []
            for bi in range(str_comp.bRepBodies.count):
                b = str_comp.bRepBodies.item(bi)
                if b.name.startswith(str_name) or \
                   b.name.startswith(f"TW_{str_name}"):
                    bodies_to_split.append(b)

            # Split each body at this leg
            for b in bodies_to_split:
                bp = b.createForAssemblyContext(str_occ)
                try:
                    split_inp = root.features.splitBodyFeatures.createInput(
                        bp, leg_proxy, True)
                    root.features.splitBodyFeatures.add(split_inp)
                except: pass

            # Remove fragments on the FAR side of this leg (tenon direction)
            removed = 0
            for bi in range(str_comp.bRepBodies.count - 1, -1, -1):
                b = str_comp.bRepBodies.item(bi)
                if not (b.name.startswith(str_name) or
                        b.name.startswith(f"TW_{str_name}")):
                    continue
                side = sp.body_side(b, leg, tenon_dir)
                if side == 'outside':
                    # Beyond the leg, away from stretcher → excess tip
                    try:
                        root.features.removeFeatures.add(
                            b.createForAssemblyContext(str_occ))
                        removed += 1
                    except: pass
            print(f"  {str_name} at Leg{leg_idx+1}: removed {removed} tips")

        # Join remaining interior fragments back to main stretcher
        main = None; main_vol = 0; frags = []
        for bi in range(str_comp.bRepBodies.count):
            b = str_comp.bRepBodies.item(bi)
            if not b.name.startswith(str_name): continue
            if b.name.startswith(f"TW_{str_name}"): continue
            if b.volume > main_vol:
                if main: frags.append(main)
                main = b; main_vol = b.volume
            else:
                frags.append(b)

        if main and frags:
            main_proxy = main.createForAssemblyContext(str_occ)
            for frag in frags:
                try:
                    sp.combine(root, main_proxy,
                               frag.createForAssemblyContext(str_occ),
                               JOIN, False, f"{str_name}_Join")
                except: pass

        print(f"{str_name} done: joined {len(frags)} interior frags")

    # ══════════════════════════════════════════════════════════════
    # STEP 9: CUT LEGS WITH TRIMMED STRETCHER TENONS (mortise)
    # ══════════════════════════════════════════════════════════════
    # Refresh stretcher bodies — find largest body for each stretcher name
    str_bodies_fresh = []
    for _, _, sn, _ in connections:
        best = None; best_vol = 0
        for bi in range(str_comp.bRepBodies.count):
            b = str_comp.bRepBodies.item(bi)
            if sn in b.name and not b.name.startswith("TW_"):
                if b.volume > best_vol:
                    best = b; best_vol = b.volume
        if best: str_bodies_fresh.append(best)
    str_proxies = [sb.createForAssemblyContext(str_occ) for sb in str_bodies_fresh]

    for ci, (a_idx, b_idx, str_name, _) in enumerate(connections):
        sp_body = str_proxies[ci]
        sp.combine(root, leg_proxies[a_idx], sp_body, CUT, True,
                   f"{str_name}_MortA")
        sp.combine(root, leg_proxies[b_idx], sp_body, CUT, True,
                   f"{str_name}_MortB")
    print("Stretcher mortises cut with trimmed tenons")

    # ══════════════════════════════════════════════════════════════
    # STEP 9b: CUT WEDGE BODIES INTO RECEIVING BODIES
    # ══════════════════════════════════════════════════════════════
    # Leg wedges → CUT into seat
    for i in range(3):
        tw = None
        for bi in range(legs_comp.bRepBodies.count):
            b = legs_comp.bRepBodies.item(bi)
            if b.name == f"TW_L{i+1}": tw = b; break
        if tw:
            try:
                sp.combine(root, seat_proxy,
                           tw.createForAssemblyContext(legs_occ),
                           CUT, True, f"TW_L{i+1}_Mortise")
            except: pass

    # Stretcher wedges → CUT into legs
    for ci, (a_idx, b_idx, sname, _) in enumerate(connections):
        for ei in range(2):
            tw_name = f"TW_{sname}_{ei}"
            tw = None
            for bi in range(str_comp.bRepBodies.count):
                b = str_comp.bRepBodies.item(bi)
                if b.name == tw_name: tw = b; break
            if not tw: continue
            leg_idx = a_idx if ei == 0 else b_idx
            try:
                sp.combine(root, leg_proxies[leg_idx],
                           tw.createForAssemblyContext(str_occ),
                           CUT, True, f"{tw_name}_Mortise")
            except: pass
    print("Wedge mortises cut")

    # ══════════════════════════════════════════════════════════════
    # STEP 10: DETAILS
    # ══════════════════════════════════════════════════════════════
    top_perim = adsk.core.ObjectCollection.create()
    bot_perim = adsk.core.ObjectCollection.create()
    top_z_val = ev("seat_z") + ev("seat_t")
    bot_z_val = ev("seat_z")

    for ei in range(seat_body.edges.count):
        e = seat_body.edges.item(ei)
        if e.faces.count < 2: continue
        f1 = e.faces.item(0); f2 = e.faces.item(1)
        g1 = type(f1.geometry).__name__; g2 = type(f2.geometry).__name__
        types = {g1, g2}
        if "Cylinder" in types or "Sphere" in types: continue
        if "Plane" not in types or "NurbsSurface" not in types: continue
        nurbs_f = f1 if g1 == "NurbsSurface" else f2
        if nurbs_f.area < 10: continue
        plane_f = f1 if g1 == "Plane" else f2
        pz = plane_f.pointOnFace.z
        if abs(pz - top_z_val) < 1.0: top_perim.add(e)
        elif abs(pz - bot_z_val) < 0.5: bot_perim.add(e)

    if bot_perim.count > 0:
        fil_inp = seat_comp.features.filletFeatures.createInput()
        fil_inp.addConstantRadiusEdgeSet(bot_perim, VI("seat_bot_fil"), False)
        try:
            seat_comp.features.filletFeatures.add(fil_inp).name = "SeatBot_Fil"
            print(f"Seat bottom fillet done")
        except: print("Seat bottom fillet failed")

    if top_perim.count > 0:
        fil_inp = seat_comp.features.filletFeatures.createInput()
        fil_inp.addConstantRadiusEdgeSet(top_perim, VI("seat_top_fil"), False)
        try:
            seat_comp.features.filletFeatures.add(fil_inp).name = "SeatTop_Fil"
            print(f"Seat top fillet done")
        except: print("Seat top fillet failed")

    print("All steps complete")
