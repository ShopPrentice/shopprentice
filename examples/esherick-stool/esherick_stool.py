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

# ═══════════════ APPEARANCE SPEC ══════════════════════════
# After execute_script(clean=True), agent parses this block
# and applies each coat in order via the apply_appearance MCP
# tool. After coats, if hide_construction is true, hide all
# sketches and construction geometry. See docs/appearance.md
# for the full schema and agent workflow.
# {
#   "coats": [
#     {"species": "oak"},
#     {"species": "walnut",
#      "bodies": ["Seat", "TW_L*", "TW_Str_*"],
#      "grain_overrides": {"Seat": "x"}}
#   ],
#   "hide_construction": true
# }
# ══════════════════════════════════════════════════════════
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
        ("splay", "12 deg", "deg", "Leg splay from vertical"),
        ("tenon_proud", "0.25 in", "in", "Through-tenon above seat"),
        ("tenon_dia", "0.625 in", "in", "Through-tenon diameter above seat"),
        ("str_h1", "6.5 in", "in", "Stretcher 1-2 height"),
        ("str_h2", "8 in", "in", "Stretcher 2-3 height"),
        ("str_h3", "9.5 in", "in", "Stretcher 3-1 height"),
        ("ts_mid_dia", "0.6 in", "in", "Stretcher body diameter"),
        ("ts_end_dia", "0.45 in", "in", "Stretcher tenon diameter"),
        ("ts_tenon_len", "1.5 in", "in", "Stretcher tenon length"),
        ("ts_shoulder_len", "0.25 in", "in", "Shoulder transition"),
        ("ts_ext", "0.25 in", "in", "Tenon extension beyond leg surface"),
        ("ts_barrel_dist", "2 in", "in", "Barrel ctrl point dist from mid"),
        ("ts_barrel_r", "0.32 in", "in", "Barrel ctrl point radius"),
        ("leg_spread", "3 in", "in", "Leg center distance from seat center"),
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

    # ── Captured seat plan (12 pts/section, 5 pts/rail) from user's loft-based
    # fixture_loft_esherick_seat edits. Baseline fixture coords in cm at
    # fixture_cx=7, fixture_cy=157.5 (centred on geometric seat centre).
    _BOT_PLAN = [
        (9.6705, 156.7913), (6.9535, 154.7876), (3.8395, 153.4837),
        (3.1864, 153.7881), (2.5900, 154.1925), (2.1931, 157.5000),
        (2.5900, 160.8075), (3.1864, 161.2119), (3.8395, 161.5163),
        (6.9535, 160.2124), (9.6705, 158.2087), (9.7272, 157.5000),
    ]
    _MID_PLAN = [
        (10.6680, 154.9400), (7.7545, 153.3976), (3.8862, 151.9521),
        (2.2520, 152.1974), (1.4000, 152.7750), (0.7389, 157.2908),
        (1.5257, 162.1657), (2.2520, 162.8026), (3.2460, 163.1417),
        (7.2552, 161.5582), (10.6875, 160.0208), (11.5960, 157.5000),
    ]
    _TOP_PLAN = [
        (9.6705, 156.7913), (8.0358, 154.8266), (3.8395, 153.4837),
        (3.1864, 153.7881), (2.5929, 154.3090), (2.1931, 157.5000),
        (2.5900, 160.8075), (3.1864, 161.2119), (3.8395, 161.5163),
        (6.9535, 160.2124), (9.6705, 158.2087), (9.7272, 157.5000),
    ]
    _RAIL_0_CTRLS = [(2.2980, 152.2539, 0.2949), (2.2948, 152.2485, 0.9625)]
    _RAIL_1_CTRLS = [(2.4760, 162.4193, 0.2437), (2.3200, 162.6845, 0.9751)]
    _RAIL_2_CTRLS = [(11.0660, 157.5000, 0.1912), (11.3109, 157.5000, 0.9781)]

    _FIX_CX, _FIX_CY = 7.0, 157.5
    _FIX_SD, _FIX_SW, _FIX_ST = 14.0, 15.0, 1.25

    # Scale from fixture cm to stool internal cm. At default (seat_d=14 in,
    # seat_w=15 in, seat_t=1.25 in) each scale ≈ 2.54. Changing any of those
    # parameters in the palette rescales the seat.
    _scale_x = sd / _FIX_SD
    _scale_y = sw / _FIX_SW
    _scale_z = ev("seat_t") / _FIX_ST

    def _map_xy(fx, fy):
        return (cx + (fx - _FIX_CX) * _scale_x,
                cy + (fy - _FIX_CY) * _scale_y)

    # Use the captured MID_PLAN centroid (NOT the geometric centre of seat_d/w)
    # as tri_cx, tri_cy — the user's edits shifted the centroid slightly and
    # downstream leg/scoop positioning must follow the real outline.
    _mid_cent_fx = sum(p[0] for p in _MID_PLAN) / len(_MID_PLAN)
    _mid_cent_fy = sum(p[1] for p in _MID_PLAN) / len(_MID_PLAN)
    tri_cx, tri_cy = _map_xy(_mid_cent_fx, _mid_cent_fy)

    # leg_angles_rad: directions to the 3 edited corners (MID_PLAN indices
    # 11 = front apex, 3 = back-left, 7 = back-right) — matches the stool's
    # expected tv[0]/tv[1]/tv[2] ordering.
    _CORNER_IDX_TV = [11, 3, 7]
    leg_angles_rad = []
    for _idx in _CORNER_IDX_TV:
        cfx, cfy = _MID_PLAN[_idx]
        leg_angles_rad.append(math.atan2(cfy - _mid_cent_fy, cfx - _mid_cent_fx))

    # Keep tv synthesised for any downstream code that still reads it.
    tv = [_map_xy(*_MID_PLAN[i]) for i in _CORNER_IDX_TV]

    # Note: body-relative refs are added after each major section below
    # using ctx.find_body() + .boundingBox to document dependencies.

    # ── COMPONENTS ────────────────────────────────────────────────
    seat_occ = sp.make_comp(root, "Seat")
    seat_comp = seat_occ.component
    legs_occ = sp.make_comp(root, "Legs")
    legs_comp = legs_occ.component
    str_occ = sp.make_comp(root, "Stretchers")
    str_comp = str_occ.component

    # ══════════════════════════════════════════════════════════════
    # STEP 1: SEAT (3-section loft with 3 adjustable rails)
    # Captured from fixture_loft_esherick_seat. Plan points and rail
    # control points are already baked into _BOT_PLAN/_MID_PLAN/_TOP_PLAN
    # and _RAIL_*_CTRLS above; the section anchors on the 3 rails snap
    # exactly onto the plan splines (CORNER_IDX_TV indices).
    # ══════════════════════════════════════════════════════════════
    _seat_z = ev("seat_z")
    _seat_t_val = ev("seat_t")

    def _add_section(plane, z_abs, pts_xy, name):
        sk_s = seat_comp.sketches.add(plane); sk_s.name = name
        coll = adsk.core.ObjectCollection.create()
        for fx, fy in pts_xy:
            mx, my = _map_xy(fx, fy)
            p = sk_s.modelToSketchSpace(P(mx, my, z_abs))
            coll.add(P(p.x, p.y, 0))
        sc = sk_s.sketchCurves.sketchFittedSplines.add(coll)
        sc.isClosed = True
        return sk_s

    bot_pl = sp.off_plane(seat_comp, seat_comp.xYConstructionPlane,
                          "seat_z", "Seat_BotPl")
    sk_bot = _add_section(bot_pl, _seat_z, _BOT_PLAN, "Seat_Bot")

    mid_pl = sp.off_plane(seat_comp, seat_comp.xYConstructionPlane,
                          "seat_z + seat_t / 2", "Seat_MidPl")
    sk_mid = _add_section(mid_pl, _seat_z + _seat_t_val / 2, _MID_PLAN, "Seat_Mid")

    top_pl = sp.off_plane(seat_comp, seat_comp.xYConstructionPlane,
                          "seat_z + seat_t", "Seat_TopPl")
    sk_top = _add_section(top_pl, _seat_z + _seat_t_val, _TOP_PLAN, "Seat_Top")

    def _build_rail(rail_i, ctrl_fixture_pts, corner_idx):
        # Anchor sketch-points at the bot / mid / top corner positions —
        # the rail plane is then defined THROUGH those three anchors, so
        # their 3D positions lie exactly on the plane (no projection drift).
        _bmx, _bmy = _map_xy(*_BOT_PLAN[corner_idx])
        _bs = sk_bot.modelToSketchSpace(P(_bmx, _bmy, _seat_z))
        _bot_corner = sk_bot.sketchPoints.add(P(_bs.x, _bs.y, 0))

        _mmx, _mmy = _map_xy(*_MID_PLAN[corner_idx])
        _ms = sk_mid.modelToSketchSpace(P(_mmx, _mmy, _seat_z + _seat_t_val / 2))
        _mid_corner = sk_mid.sketchPoints.add(P(_ms.x, _ms.y, 0))

        _tmx, _tmy = _map_xy(*_TOP_PLAN[corner_idx])
        _ts = sk_top.modelToSketchSpace(P(_tmx, _tmy, _seat_z + _seat_t_val))
        _top_corner = sk_top.sketchPoints.add(P(_ts.x, _ts.y, 0))

        cpi_r = seat_comp.constructionPlanes.createInput()
        cpi_r.setByThreePoints(_bot_corner, _mid_corner, _top_corner)
        rail_pl = seat_comp.constructionPlanes.add(cpi_r)
        rail_pl.name = f"Seat_RailPl{rail_i}"

        sk_r = seat_comp.sketches.add(rail_pl); sk_r.name = f"Seat_Rail{rail_i}"
        fit = adsk.core.ObjectCollection.create()
        ap = sk_r.modelToSketchSpace(P(_bmx, _bmy, _seat_z))
        fit.add(P(ap.x, ap.y, 0))
        lfx, lfy, lfz = ctrl_fixture_pts[0]
        lmx, lmy = _map_xy(lfx, lfy)
        lp = sk_r.modelToSketchSpace(P(lmx, lmy, _seat_z + lfz * _scale_z))
        fit.add(P(lp.x, lp.y, 0))
        ap = sk_r.modelToSketchSpace(P(_mmx, _mmy, _seat_z + _seat_t_val / 2))
        fit.add(P(ap.x, ap.y, 0))
        hfx, hfy, hfz = ctrl_fixture_pts[1]
        hmx, hmy = _map_xy(hfx, hfy)
        hp = sk_r.modelToSketchSpace(P(hmx, hmy, _seat_z + hfz * _scale_z))
        fit.add(P(hp.x, hp.y, 0))
        ap = sk_r.modelToSketchSpace(P(_tmx, _tmy, _seat_z + _seat_t_val))
        fit.add(P(ap.x, ap.y, 0))
        return sk_r.sketchCurves.sketchFittedSplines.add(fit)

    _rail_splines = [
        _build_rail(0, _RAIL_0_CTRLS, 3),
        _build_rail(1, _RAIL_1_CTRLS, 7),
        _build_rail(2, _RAIL_2_CTRLS, 11),
    ]

    loft_inp = seat_comp.features.loftFeatures.createInput(NEWBODY)
    _sec_bot = loft_inp.loftSections.add(sk_bot.profiles.item(0))
    loft_inp.loftSections.add(sk_mid.profiles.item(0))
    _sec_top = loft_inp.loftSections.add(sk_top.profiles.item(0))
    _sec_bot.setDirectionEndCondition(VI("0 deg"), VI("3.0"))
    _sec_top.setDirectionEndCondition(VI("0 deg"), VI("3.0"))
    for _rs in _rail_splines:
        loft_inp.centerLineOrRails.addRail(_rs)
    loft_inp.isSolid = True
    loft_inp.isTangentEdgesMerged = True
    seat_loft = seat_comp.features.loftFeatures.add(loft_inp)
    seat_loft.name = "SeatLoft"
    seat_body = seat_loft.bodies.item(0)
    seat_body.name = "Seat"

    # Scoop removed — the loft's tangent top + rail-shaped sides already
    # give a comfortable pillowed seat without a separate sphere CUT.
    print("Seat (lofted, no scoop) done")

    # Body-relative ref: Seat refs Leg1 for positioning
    ref_leg1 = ctx.find_body("Leg1")
    # Leg1 may not exist yet on first build — ref checked after legs built

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
        (0.3454, 0.0), (0.4905, 0.0613), (0.5935, 0.4374),
        (0.7436, 2.0844), (1.2032, 14.7896), (1.3170, 20.0660),
        (1.3198, 25.9935), (1.2011, 34.1837), (1.0265, 42.3219),
        (0.9006, 50.7089), (0.7970, 56.8458), (0.7503, 60.96),
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

    # Body-relative refs: legs reference each other, wedges reference legs
    ref_leg1 = ctx.find_body("Leg1")
    ref_leg1_bb = ref_leg1.boundingBox
    ref_leg2 = ctx.find_body("Leg2")
    ref_leg2_bb = ref_leg2.boundingBox
    ref_leg3 = ctx.find_body("Leg3")
    ref_leg3_bb = ref_leg3.boundingBox

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
                           # Seat grain runs along X (see appearance override
                           # on "Seat" — grain="x"). Per tenon-wedge.md the
                           # slot must be PERPENDICULAR to mortise grain so
                           # the wedge expansion is PARALLEL to grain (wood
                           # resists compression along fibers but splits
                           # easily across them). Template computes
                           # slot_dir = face_normal × grain_dir — with
                           # face_normal = Z and grain_dir=(1,0,0) we get
                           # slot_dir = Y, i.e. wedge long axis crosses the
                           # seat's X grain — the correct orientation.
                           grain_dir=(1, 0, 0),
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
                    sp.combine(main_proxy,
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
        sp.combine(seat_proxy, lp, CUT, True, f"Leg{i+1}_Mortise")
    print("Leg mortises cut with trimmed tenons")

    # Body-relative refs: stretchers reference legs for positioning
    ref_leg1_str = ctx.find_body("Leg1")
    ref_leg1_str_bb = ref_leg1_str.boundingBox if ref_leg1_str else None
    ref_leg2_str = ctx.find_body("Leg2")
    ref_leg2_str_bb = ref_leg2_str.boundingBox if ref_leg2_str else None
    ref_leg3_str = ctx.find_body("Leg3")
    ref_leg3_str_bb = ref_leg3_str.boundingBox if ref_leg3_str else None

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
                sp.combine(str_proxies[i], str_proxies[j], CUT, True,
                           f"Str{i}{j}_Fix")
            except: pass

    # Body-relative refs: stretcher wedges reference stretchers
    ref_str12 = ctx.find_body("Str_12")
    ref_str12_bb = ref_str12.boundingBox if ref_str12 else None
    ref_str23 = ctx.find_body("Str_23")
    ref_str23_bb = ref_str23.boundingBox if ref_str23 else None
    ref_str31 = ctx.find_body("Str_31")
    ref_str31_bb = ref_str31.boundingBox if ref_str31 else None

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
                    sp.combine(main_proxy,
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
        sp.combine(leg_proxies[a_idx], sp_body, CUT, True,
                   f"{str_name}_MortA")
        sp.combine(leg_proxies[b_idx], sp_body, CUT, True,
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
                sp.combine(seat_proxy,
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
                sp.combine(leg_proxies[leg_idx],
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

    # Seat top/bottom perimeter fillets are redundant with the 3-section
    # loft — direction-tangent end conditions already blend the flat top
    # and bottom into the sides. Skipping preserves the clean loft surface.

    print("All steps complete")
