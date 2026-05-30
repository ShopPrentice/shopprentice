"""
Moravian Workbench — after Barry NM Dima, Fine Woodworking #293 (Tools & Shops 2022).

Knock-down trestle bench:
  - 4 legs splayed 15 deg along the length (X), laminated stock (modelled solid)
  - 4 short stretchers (2 per trestle, run in Y) with bareface tenons into legs
  - 2 long stretchers (front/back, run in X) with wedged half-dovetail through-tenons (knockdown)
  - split benchtop (front + rear board, 5/16" gap)
  - lower shelf on cleats
  - leg vise (chop + parallel guide + screw) on the front-left leg

Coordinate system (inches; Fusion works in cm internally):
  X = length (0..64), Y = depth (0 front .. ~28.25 back), Z = height (0 floor up)

Built in phases. Each phase grows this file; re-run as a clean rebuild.
"""

import adsk.core, adsk.fusion, math, os
from helpers import sp

_MODEL_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.json")

# ═══════════════ APPEARANCE SPEC ══════════════════════════
# After execute_script(clean=True), agent parses this block and applies each
# coat in order via the apply_appearance MCP tool, then hides construction.
# Species follow the article: pine mortised legs, oak tenoned stretchers,
# maple benchtop, cherry vise chop.
# {
#   "coats": [
#     {"species": "oak"},
#     {"species": "pine", "bodies": ["Leg_*"]},
#     {"species": "maple", "bodies": ["Top_*", "Wedge_*", "Parallel_Guide"]},
#     {"species": "pine", "bodies": ["Cleat_*", "Shelf_Board_*"]},
#     {"species": "cherry", "bodies": ["Vise_Chop"]}
#   ],
#   "black": {"appearance": "Powder Coat - Rough (Black)", "bodies": ["Guide_Wedge_*"]},
#   "hide_construction": true
# }
# Vise_Screw is ONE body but gets per-FACE appearances via script (apply_appearance
# is wood-only + body-level). Classify its faces and assign library appearances:
#   - handle bar + end knobs (X-axis cylinders / X-normal caps) -> same as chop ("3D Cherry - Figured")
#   - threaded rod (Y-axis cylinder ~screw_dia/2, + far-back Y-normal cap)  -> "Stainless Steel - Satin"
#   - hub + collar castings (remaining Y-axis cylinders / Y-normal caps)    -> "Powder Coat - Rough (Black)"
# ══════════════════════════════════════════════════════════

P = adsk.core.Point3D
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation


def run(context):
    ctx = sp.DesignContext()
    app, design, root = ctx.app, ctx.design, ctx.root
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    params = design.userParameters
    ev = ctx.ev
    VI = adsk.core.ValueInput.createByString

    def param(name, expr, unit, comment):
        existing = params.itemByName(name)
        if existing:
            existing.expression = expr
            return existing
        return params.add(name, VI(expr), unit, comment)

    # ───────────────────────── PARAMETERS ─────────────────────────
    # Overall envelope
    param("bench_l",     "64 in",     "in", "Overall bench / top length (X)")
    param("bench_h",     "31 in",     "in", "Overall bench height")
    param("top_thick",   "2.25 in",   "in", "Benchtop thickness")
    param("front_top_w", "17.3125 in","in", "Front benchtop width (Y)")
    param("rear_top_w",  "10.625 in", "in", "Rear benchtop width (Y)")
    param("top_gap",     "0.3125 in", "in", "Gap between the two benchtops")
    param("depth",       "front_top_w + top_gap + rear_top_w", "in", "Overall top depth (Y)")

    # Legs
    param("splay",        "15 deg",   "deg", "Leg splay from vertical, in X")
    param("leg_w",        "4.375 in", "in",  "Leg width (perpendicular to length)")
    param("leg_thick",    "3.75 in",  "in",  "Leg thickness (Y), two laminated 1-7/8 halves")
    param("under_top",    "bench_h - top_thick", "in", "Height from floor to top underside")
    param("leg_face_w",   "leg_w / cos(splay)",  "in", "Horizontal width of the 15-deg cut faces")
    param("leg_run",      "under_top * tan(splay)", "in", "X shift of foot vs top over leg height")
    param("leg_top_inset","12 in",    "in",  "X inset of leg-top center from each bench end")
    param("ltx_L",        "leg_top_inset",          "in", "Left trestle leg-top center X")
    param("ltx_R",        "bench_l - leg_top_inset", "in", "Right trestle leg-top center X")
    param("leg_inset_y",  "4 in",     "in",  "Leg center inset from front/back top edge")
    param("front_leg_y",  "leg_inset_y",          "in", "Front leg Y center")
    param("back_leg_y",   "depth - leg_inset_y",  "in", "Back leg Y center")

    # Midplanes
    param("x_mid", "bench_l / 2", "in", "Length midplane")
    param("y_mid", "depth / 2",   "in", "Depth midplane")

    # ───────────────────────── LEGS ─────────────────────────
    # Reference: origin (floor). Root-level part — legs sit on the floor at Z=0,
    # splayed 15 deg in X. Build Leg_LF, then mirror to all four corners.
    legs_occ = sp.make_comp(root, "Legs")
    legs = legs_occ.component

    LegFront_Pl = sp.off_plane(legs, legs.xZConstructionPlane,
                               "front_leg_y - leg_thick / 2", "LegFront_Pl")
    YMid_Pl = sp.off_plane(legs, legs.xZConstructionPlane, "y_mid", "YMid_Pl")
    XMid_Pl = sp.off_plane(legs, legs.yZConstructionPlane, "x_mid", "XMid_Pl")

    fw  = ev("leg_face_w")
    run = ev("leg_run")
    ut  = ev("under_top")
    ltx = ev("ltx_L")

    sk = legs.sketches.add(LegFront_Pl)
    sk.name = "Leg_LF_Sk"
    m2s = sk.modelToSketchSpace

    # model (X, Z) corners; LF leans so the foot is toward -X
    A = m2s(P.create(ltx - fw/2,        0, ut))   # top, low-X
    B = m2s(P.create(ltx + fw/2,        0, ut))   # top, high-X
    C = m2s(P.create(ltx - run + fw/2,  0, 0))    # bottom, high-X
    D = m2s(P.create(ltx - run - fw/2,  0, 0))    # bottom, low-X

    lns = sk.sketchCurves.sketchLines
    lab = lns.addByTwoPoints(P.create(A.x, A.y, 0), P.create(B.x, B.y, 0))   # top
    lbc = lns.addByTwoPoints(lab.endSketchPoint, P.create(C.x, C.y, 0))       # right (angled)
    lcd = lns.addByTwoPoints(lbc.endSketchPoint, P.create(D.x, D.y, 0))       # bottom
    lda = lns.addByTwoPoints(lcd.endSketchPoint, lab.startSketchPoint)        # left (angled)

    gc = sk.geometricConstraints
    gc.addHorizontal(lab)   # top edge horizontal
    gc.addHorizontal(lcd)   # bottom edge horizontal

    orient = sp.probe_orientations(sk, ltx, ev("front_leg_y"), ut)
    d = sk.sketchDimensions
    org = sk.originPoint
    pA, pB = lab.startSketchPoint, lab.endSketchPoint
    pD = lcd.endSketchPoint
    pC = lcd.startSketchPoint
    d.addDistanceDimension(pA, pB, orient['x'],
        P.create(A.x, A.y + 1, 0)).parameter.expression = "leg_face_w"
    d.addDistanceDimension(pC, pD, orient['x'],
        P.create(C.x, C.y - 1, 0)).parameter.expression = "leg_face_w"
    d.addDistanceDimension(org, pA, orient['x'],
        P.create(A.x/2 if A.x else 1, A.y, 0)).parameter.expression = "ltx_L - leg_face_w / 2"
    d.addDistanceDimension(org, pA, orient['z'],
        P.create(A.x, A.y/2 if A.y else 1, 0)).parameter.expression = "under_top"
    d.addDistanceDimension(pA, pD, orient['x'],
        P.create(A.x - 1, A.y - 2, 0)).parameter.expression = "leg_run"
    d.addDistanceDimension(pA, pD, orient['z'],
        P.create(A.x - 2, A.y/2 if A.y else 1, 0)).parameter.expression = "under_top"

    prof = sp.smallest_profile(sk)
    ext = sp.ext_new(legs, prof, "leg_thick", "Leg_LF_Ext")
    leg_lf = ext.bodies.item(0)
    leg_lf.name = "Leg_LF"

    # Mirror to all four corners
    m1 = sp.mirror_body(legs, leg_lf, YMid_Pl, "Leg_LB_Mir")
    m2 = sp.mirror_bodies(legs, [leg_lf, m1.bodies.item(0)], XMid_Pl, "Leg_R_Mir")

    # Name all four legs deterministically by center position (mirror body
    # collections are unreliable — rescan and classify by quadrant).
    xm, ym = ev("x_mid"), ev("y_mid")
    for i in range(legs.bRepBodies.count):
        b = legs.bRepBodies.item(i)
        bb = b.boundingBox
        cx = (bb.minPoint.x + bb.maxPoint.x) / 2
        cy = (bb.minPoint.y + bb.maxPoint.y) / 2
        side = "L" if cx < xm else "R"
        fb = "F" if cy < ym else "B"
        b.name = "Leg_%s%s" % (side, fb)

    def get_leg(name):
        return legs.bRepBodies.itemByName(name)

    # ───────────────────────── SHORT STRETCHERS ─────────────────────────
    # Reference: legs (read leg inner Y-faces + splay-adjusted X center).
    # 4 stretchers (upper/lower per trestle) run in Y between the front and
    # back leg of each trestle, with centered bareface tenons into stopped
    # leg mortises. The leg's Y-faces are flat constant-Y planes (leg leans
    # only in X), so a level box butts flush — no shoulder gap.
    param("ss_thick",      "3.5 in",   "in", "Short stretcher thickness (X), laminated 2x1-3/4")
    param("ss_w",          "4.875 in", "in", "Short stretcher width / height (Z)")
    param("ss_tenon_len",  "2.75 in",  "in", "Short stretcher tenon length into leg (Y)")
    param("ss_tenon_thick","1.75 in",  "in", "Short stretcher tenon thickness (X)")
    param("ss_tenon_h",    "3.375 in", "in", "Short stretcher tenon height (Z)")
    param("ss_upper_zc",   "under_top - ss_w / 2", "in", "Upper short stretcher Z center (top flush w/ leg tops)")
    param("ss_lower_zc",   "16.5 in",  "in", "Lower short stretcher Z center (lowered; stays clear of the long-stretcher through-tenon)")

    short_occ = sp.make_comp(root, "ShortStretchers")
    short = short_occ.component

    front_inner = "front_leg_y + leg_thick / 2"
    back_inner  = "back_leg_y - leg_thick / 2"
    span_y      = "back_leg_y - front_leg_y - leg_thick"

    def legcx(side, zc):
        if side == "L":
            return "(ltx_L - leg_run * (under_top - (%s)) / under_top)" % zc
        return "(ltx_R + leg_run * (under_top - (%s)) / under_top)" % zc

    def corner_x(side):
        # Bottom-low-X corner of the leg's inner face (a real parent vertex)
        if side == "L":
            return "ltx_L - leg_run - leg_face_w / 2"
        return "ltx_R + leg_run - leg_face_w / 2"

    def box_yrun(comp, cx_e, zc_e, wx_e, hz_e, ya_e, ylen_e, name,
                 parent, anchor_xyz, face_dir, op=NEW, target=None):
        # XZ side-profile sketch, extruded in Y. Anchored to the parent leg's
        # face_dir Y-face via explicit off-axis dims (reanchor mis-maps Z->Y here).
        plane = sp.off_plane(comp, comp.xZConstructionPlane, ya_e, name + "_Pl")
        anc_x, anc_y = anchor_xyz[0], anchor_xyz[1]
        origin = ("(%s) - (%s) / 2" % (cx_e, wx_e), ya_e, "(%s) - (%s) / 2" % (zc_e, hz_e))
        anchor = dict(parent_body=parent, parent_occ=legs_occ, face_axis="y", face_dir=face_dir,
                      anchor_xyz=(anc_x, anc_y, "0 in"), which=0,
                      off1=("x", "abs((%s) - (%s) / 2 - (%s))" % (cx_e, wx_e, anc_x)),
                      off2=("z", "abs((%s) - (%s) / 2)" % (zc_e, hz_e)))
        sk, prof = sp.sketch_rect_model(comp, plane, origin, {"x": wx_e, "z": hz_e},
                                        name + "_Sk", ev=ev, anchor=anchor)
        prof = sp.smallest_profile(sk)
        if op == NEW:
            f = sp.ext_new(comp, prof, ylen_e, name + "_Ext")
            b = f.bodies.item(0); b.name = name
            return b
        return sp.ext_op(comp, prof, ylen_e, op, target, name + "_Ext", flip=False)

    def move_rot_y(bodies, px_e, pz_e, angle_rad):
        # Rotate bodies about a Y-parallel axis through (px, pz). Splay is a
        # design constant, so a (non-parametric) Move is acceptable here.
        c, s = math.cos(angle_rad), math.sin(angle_rad)
        px, pz = ev(px_e), ev(pz_e)
        tx = px - (px * c - pz * s)
        tz = pz - (px * s + pz * c)
        xf = adsk.core.Matrix3D.create()
        xf.setWithArray([c, 0, -s, tx,  0, 1, 0, 0,  s, 0, c, tz,  0, 0, 0, 1])
        coll = adsk.core.ObjectCollection.create()
        for b in bodies:
            coll.add(b)
        comp = bodies[0].parentComponent
        mi = comp.features.moveFeatures.createInput2(coll)
        mi.defineAsFreeMove(xf)
        comp.features.moveFeatures.add(mi)

    def build_short_stretcher(side, zc_e, name):
        cx_e = legcx(side, zc_e)
        fleg = get_leg("Leg_%sF" % side)
        bleg = get_leg("Leg_%sB" % side)
        # Anchor every sketch to the front leg's inner (+Y) face — a single,
        # reliably-projected reference (reanchor mis-picks the back leg's -Y
        # face vertex). The dependency is tracked by body, not by sketch.
        cor_f = (corner_x(side), "front_leg_y + leg_thick / 2", "0 in")
        main = box_yrun(short, cx_e, zc_e, "ss_thick", "ss_w", front_inner, span_y, name,
                        fleg, cor_f, +1)
        # Tenons overlap the main body by 0.25" so JOIN has real volume
        # (a coplanar face-to-face JOIN is unreliable).
        ften = box_yrun(short, cx_e, zc_e, "ss_tenon_thick", "ss_tenon_h",
                        "(%s) - ss_tenon_len" % front_inner, "ss_tenon_len + 0.25 in",
                        name + "_FTen", fleg, cor_f, +1)
        bten = box_yrun(short, cx_e, zc_e, "ss_tenon_thick", "ss_tenon_h",
                        "(%s) - 0.25 in" % back_inner, "ss_tenon_len + 0.25 in",
                        name + "_BTen", fleg, cor_f, +1)
        # Tilt the stretcher (and its tenons) about its Y long-axis so its side
        # faces run parallel to the leaning legs. Left leg leans top-toward +X
        # (rotate -splay); right leg top-toward -X (rotate +splay).
        ang = -ev("splay") if side == "L" else ev("splay")
        move_rot_y([main, ften, bten], cx_e, zc_e, ang)
        sp.combine(fleg.createForAssemblyContext(legs_occ),
                   [ften.createForAssemblyContext(short_occ)], CUT, True, name + "_FMort")
        sp.combine(bleg.createForAssemblyContext(legs_occ),
                   [bten.createForAssemblyContext(short_occ)], CUT, True, name + "_BMort")
        sp.combine(main, [ften], JOIN, False, name + "_JoinF")
        sp.combine(main, [bten], JOIN, False, name + "_JoinB")
        return main

    build_short_stretcher("L", "ss_upper_zc", "SS_LU")
    build_short_stretcher("L", "ss_lower_zc", "SS_LL")
    build_short_stretcher("R", "ss_upper_zc", "SS_RU")
    build_short_stretcher("R", "ss_lower_zc", "SS_RL")

    # ───────────────────────── LONG STRETCHERS (knockdown) ─────────────────────────
    # Reference: legs. 2 long stretchers (front/back row) run in X. Following the
    # trestle-table joint: a solid beam between the legs with shoulders trimmed to
    # the 15-deg leaning leg faces, plus a small REDUCED through-tenon (keeps the
    # leg strong) that protrudes past the outer face and is locked by a tusk
    # wedge driven down through it.
    param("ls_thick",     "2.5 in",   "in", "Long stretcher beam thickness (Y)")
    param("ls_w",         "4.875 in", "in", "Long stretcher beam height (Z)")
    param("ls_bot_z",     "10.375 in","in", "Long stretcher bottom height off floor")
    param("ls_proud",     "2.5 in",   "in", "Tenon protrusion past the outer leg face")
    param("ls_zc",        "ls_bot_z + ls_w / 2", "in", "Long stretcher Z center")
    param("ls_ten_thick", "1.5 in",   "in", "Through-tenon thickness (Y); flush with the inner face (bareface)")
    param("ls_ten_h",     "2.5 in",   "in", "Reduced through-tenon height (Z)")
    param("ls_ten_embed", "ls_w * tan(splay) + 0.75 in", "in", "Tenon root embed into beam (clears the angled shoulder at all heights)")
    # Tusk key — tapered, bears on the leg's OUTER face; tilted to follow the
    # 15° leg splay so driving it down pulls the long stretcher into the leg.
    param("key_thin",  "0.25 in", "in",  "Tusk key thickness at the thin (bottom) end")
    param("key_ang",   "8 deg",   "deg", "Tusk key taper angle (draws shoulder tight)")
    param("key_blade", "0.5 in",  "in",  "Tusk key blade width (Y) — < tenon so the tip stays attached")
    param("key_len",   "ls_ten_h + 2.5 in", "in", "Tusk key length (Z), protrudes above the tenon")
    param("key_taper", "key_len * tan(key_ang)", "in", "Tusk key taper run (derived)")
    param("key_crown", "0.4 in",  "in",  "Tusk key rounded-crown rise at the top")

    long_occ = sp.make_comp(root, "LongStretchers")
    long_c = long_occ.component
    wedge_occ = sp.make_comp(root, "Wedges")
    wedge_c = wedge_occ.component

    cxL = "(ltx_L - leg_run * (under_top - ls_bot_z) / under_top)"
    cxR = "(ltx_R + leg_run * (under_top - ls_bot_z) / under_top)"
    left_outer  = "(%s - leg_face_w / 2)" % cxL
    right_outer = "(%s + leg_face_w / 2)" % cxR
    left_inner  = "(%s + leg_face_w / 2)" % cxL
    right_inner = "(%s - leg_face_w / 2)" % cxR
    left_tip    = "(%s - leg_face_w / 2 - ls_proud)" % cxL
    right_tip   = "(%s + leg_face_w / 2 + ls_proud)" % cxR

    def box_zrun(comp, x0, y0, z_a, wx, wy, z_len, name, parent, anchor_xyz, face_dir=-1):
        # XY-plan sketch, extruded in Z. Anchored to a parent leg's z-face
        # via explicit off-axis dims.
        plane = sp.off_plane(comp, comp.xYConstructionPlane, z_a, name + "_Pl")
        anc_x, anc_y = anchor_xyz[0], anchor_xyz[1]
        anchor = dict(parent_body=parent, parent_occ=legs_occ, face_axis="z", face_dir=face_dir,
                      anchor_xyz=anchor_xyz, which=0,
                      off1=("x", "abs((%s) - (%s))" % (x0, anc_x)),
                      off2=("y", "abs((%s) - (%s))" % (y0, anc_y)))
        sk, prof = sp.sketch_rect_model(comp, plane, (x0, y0, z_a), {"x": wx, "y": wy},
                                        name + "_Sk", ev=ev, anchor=anchor)
        prof = sp.smallest_profile(sk)
        f = sp.ext_new(comp, prof, z_len, name + "_Ext")
        b = f.bodies.item(0); b.name = name
        return b

    # Beam spans only between the leg INNER faces (at the beam bottom); the
    # shoulder cut then trims each end inward to the angled leg face with no
    # outer-side sliver left over.
    beam_cx = "((%s) + (%s)) / 2" % (left_inner, right_inner)
    beam_wx = "(%s) - (%s)" % (right_inner, left_inner)
    def build_long_stretcher(row, name):
        if row == "F":
            legL, legR = get_leg("Leg_LF"), get_leg("Leg_RF")
            beam_ya = "front_leg_y - leg_thick / 2"            # flush front
            anc_y = "front_leg_y + leg_thick / 2"
        else:
            legL, legR = get_leg("Leg_LB"), get_leg("Leg_RB")
            beam_ya = "back_leg_y + leg_thick / 2 - ls_thick"  # flush back
            anc_y = "back_leg_y + leg_thick / 2"
        anc = (corner_x("L"), anc_y, "0 in")
        beam_yc = "(%s) + ls_thick / 2" % beam_ya
        # Tenon is bareface: flush with the beam's INNER face, shoulder on the
        # outer (front) side only. ten_pl_y = tenon front face, ten_yc = its center.
        ten_pl_y = "(%s) + ls_thick - ls_ten_thick" % beam_ya
        ten_yc = "(%s) + ls_thick - ls_ten_thick / 2" % beam_ya

        # Beam between the legs; ends trimmed to the leaning leg faces (angled shoulders)
        beam = box_yrun(long_c, beam_cx, "ls_zc", beam_wx, "ls_w",
                        beam_ya, "ls_thick", name, legL, anc, +1)
        sp.combine(beam, [legL.createForAssemblyContext(legs_occ)], CUT, True, name + "_ShL")
        sp.combine(beam, [legR.createForAssemblyContext(legs_occ)], CUT, True, name + "_ShR")

        # Reduced through-tenon at each end, drawn as the stretcher's SIDE PROFILE
        # (X-Z) and extruded along Y (the tenon thickness) — the tenon axis is the
        # stretcher length (X). Rounded nose at the proud tip; root runs deep into
        # the beam so it meets the angled shoulder at every height. Anchored to
        # the BEAM (the stretcher), not the leg.
        def make_long_tenon(end):
            if end == "L":
                x_tip, x_inner, nsg, leg = left_tip, left_inner, +1, legL
                x_root = "(%s) + ls_ten_embed" % left_inner
            else:
                x_tip, x_inner, nsg, leg = right_tip, right_inner, -1, legR
                x_root = "(%s) - ls_ten_embed" % right_inner
            nm = "%s_Ten%s" % (name, end)
            pl = sp.off_plane(long_c, long_c.xZConstructionPlane, ten_pl_y, nm + "_Pl")
            sk = long_c.sketches.add(pl); sk.name = nm + "_Sk"
            rootx, tip, zc = ev(x_root), ev(x_tip), ev("ls_zc")
            w = ev("ls_ten_h") / 2; yc = ev(ten_pl_y)
            # Nose roundness proportional to the trestle table's tenon nose.
            a, m, mz = w * 0.34, w * 0.10, w * 0.75

            def pt(x, z):
                s = sk.modelToSketchSpace(P.create(x, yc, z)); return P.create(s.x, s.y, 0)
            col = adsk.core.ObjectCollection.create()
            for x, z in [(tip + nsg * a, zc + w), (tip + nsg * m, zc + mz), (tip, zc),
                         (tip + nsg * m, zc - mz), (tip + nsg * a, zc - w)]:
                col.add(pt(x, z))
            nose = sk.sketchCurves.sketchFittedSplines.add(col)   # rounded tip (draggable)
            ln = sk.sketchCurves.sketchLines
            bot = ln.addByTwoPoints(nose.endSketchPoint, pt(rootx, zc - w))
            root = ln.addByTwoPoints(bot.endSketchPoint, pt(rootx, zc + w))
            top = ln.addByTwoPoints(root.endSketchPoint, nose.startSketchPoint)
            gc = sk.geometricConstraints
            gc.addHorizontal(bot); gc.addHorizontal(top); gc.addVertical(root)
            orient = sp.probe_orientations(sk, rootx, yc, zc)
            sp.project_face(sk, beam, None, "z", -1)
            aP = sp.anchor_pt(sk, ev(x_inner), yc, ev("ls_bot_z"))
            d = sk.sketchDimensions
            rbot, rtop = root.startSketchPoint, root.endSketchPoint
            straight = "leg_face_w + ls_proud + ls_ten_embed - ls_ten_h / 2 * 0.34"
            sp.rdim(sk, d, aP, rbot, orient, "x", "ls_ten_embed")
            sp.rdim(sk, d, aP, rbot, orient, "z", "ls_zc - ls_ten_h / 2 - ls_bot_z")
            sp.rdim(sk, d, rbot, rtop, orient, "z", "ls_ten_h")
            sp.rdim(sk, d, rbot, bot.startSketchPoint, orient, "x", straight)
            sp.rdim(sk, d, rtop, top.endSketchPoint, orient, "x", straight)
            prof = sp.smallest_profile(sk)
            tb = sp.ext_new(long_c, prof, "ls_ten_thick", nm + "_Ext").bodies.item(0)
            tb.name = nm
            return tb

        lten = make_long_tenon("L")
        rten = make_long_tenon("R")
        sp.combine(legL.createForAssemblyContext(legs_occ),
                   [lten.createForAssemblyContext(long_occ)], CUT, True, name + "_MortL")
        sp.combine(legR.createForAssemblyContext(legs_occ),
                   [rten.createForAssemblyContext(long_occ)], CUT, True, name + "_MortR")
        sp.combine(beam, [lten], JOIN, False, name + "_JoinL")
        sp.combine(beam, [rten], JOIN, False, name + "_JoinR")

        # Tusk key driven DOWN through each protruding tenon. Bearing edge lies on
        # the leg's OUTER face; tapered so tapping it down draws the shoulder tight.
        # Rounded crown at the top (like the trestle table). Built vertical, then
        # rotated to follow the 15° leg splay so it lands flat on the leg face.
        def tusk_key(end):
            leg = legL if end == "L" else legR
            if end == "L":
                outer_dir, sgn, rot = -1, -1, -ev("splay")
                xb = "(ltx_L - leg_run * (under_top - ls_zc) / under_top - leg_face_w / 2)"
                oc_x = "(ltx_L - leg_run - leg_face_w / 2)"           # leg outer floor corner
            else:
                outer_dir, sgn, rot = +1, +1, ev("splay")
                xb = "(ltx_R + leg_run * (under_top - ls_zc) / under_top + leg_face_w / 2)"
                oc_x = "(ltx_R + leg_run + leg_face_w / 2)"
            wname = "Wedge_%s%s" % (row, end)
            pl = sp.off_plane(wedge_c, wedge_c.xZConstructionPlane, ten_yc, wname + "_Pl")
            sk = wedge_c.sketches.add(pl); sk.name = wname + "_Sk"
            xbv, ycv, zcv = ev(xb), ev(ten_yc), ev("ls_zc")
            zb, zt = zcv - ev("key_len") / 2, zcv + ev("key_len") / 2
            thin, taper, crown = ev("key_thin"), ev("key_taper"), ev("key_crown")

            def wp(x, z):
                s = sk.modelToSketchSpace(P.create(x, ycv, z)); return P.create(s.x, s.y, 0)
            cx_top = xbv + sgn * (thin + taper)
            # Trestle-style crown: bearing-side top (D) is the high point; the
            # angled-side top (C) drops 'crown' below it, mid only slightly below.
            col = adsk.core.ObjectCollection.create()
            for x, z in [(cx_top, zt - crown), ((cx_top + xbv) / 2, zt - crown * 0.25), (xbv, zt)]:
                col.add(wp(x, z))
            crown_sp = sk.sketchCurves.sketchFittedSplines.add(col)   # C(low) -> mid -> D(high)
            ln = sk.sketchCurves.sketchLines
            lAB = ln.addByTwoPoints(wp(xbv, zb), wp(xbv + sgn * thin, zb))
            lBC = ln.addByTwoPoints(lAB.endSketchPoint, crown_sp.startSketchPoint)
            lDA = ln.addByTwoPoints(crown_sp.endSketchPoint, lAB.startSketchPoint)
            gc = sk.geometricConstraints
            gc.addHorizontal(lAB); gc.addVertical(lDA)
            wor = sp.probe_orientations(sk, xbv, ycv, zcv)
            sp.project_face(sk, leg, legs_occ, "x", outer_dir)
            aP = sp.anchor_pt(sk, ev(oc_x), ycv, 0)
            d = sk.sketchDimensions
            A, B = lAB.startSketchPoint, lAB.endSketchPoint
            C, D = crown_sp.startSketchPoint, crown_sp.endSketchPoint
            sp.rdim(sk, d, aP, A, wor, "x", "leg_run * ls_zc / under_top")
            sp.rdim(sk, d, aP, A, wor, "z", "ls_zc - key_len / 2")
            sp.rdim(sk, d, A, B, wor, "x", "key_thin")
            sp.rdim(sk, d, A, D, wor, "z", "key_len")
            sp.rdim(sk, d, A, C, wor, "z", "key_len - key_crown")
            sp.rdim(sk, d, D, C, wor, "x", "key_thin + key_taper")
            prof = sp.smallest_profile(sk)
            key = sp.ext_new_sym(wedge_c, prof, "key_blade / 2", wname).bodies.item(0)
            key.name = wname
            move_rot_y([key], xb, "ls_zc", rot)   # tilt key to follow the leg splay
            sp.combine(beam.createForAssemblyContext(long_occ),
                       [key.createForAssemblyContext(wedge_occ)], CUT, True, wname + "_Slot")

        tusk_key("L")
        tusk_key("R")
        return beam

    # Front row built directly; back row is an exact mirror across y_mid (the
    # back legs are themselves mirrors of the front legs, so the trimmed
    # shoulders + wedge slots transfer perfectly).
    ls_f = build_long_stretcher("F", "LS_F")
    ymid_long = sp.off_plane(long_c, long_c.xZConstructionPlane, "y_mid", "LS_YMid_Pl")
    ls_b = sp.mirror_body(long_c, ls_f, ymid_long, "LS_B_Mir").bodies.item(0)
    ls_b.name = "LS_B"
    sp.combine(get_leg("Leg_LB").createForAssemblyContext(legs_occ),
               [ls_b.createForAssemblyContext(long_occ)], CUT, True, "LS_B_MortL")
    sp.combine(get_leg("Leg_RB").createForAssemblyContext(legs_occ),
               [ls_b.createForAssemblyContext(long_occ)], CUT, True, "LS_B_MortR")
    ymid_wedge = sp.off_plane(wedge_c, wedge_c.xZConstructionPlane, "y_mid", "Wedge_YMid_Pl")
    for wf_name, wb_name in [("Wedge_FL", "Wedge_BL"), ("Wedge_FR", "Wedge_BR")]:
        wf = wedge_c.bRepBodies.itemByName(wf_name)
        wm = sp.mirror_body(wedge_c, wf, ymid_wedge, wb_name + "_Mir")
        wm.bodies.item(0).name = wb_name

    # ───────────────────────── SPLIT BENCHTOP ─────────────────────────
    # Reference: legs (rests on the leg tops + upper short stretchers at
    # Z=under_top). Two boards (front wide + rear narrow) with a 5/16" gap.
    param("front_top_y0", "front_leg_y - leg_thick / 2", "in", "Front benchtop front edge (flush w/ leg fronts)")
    param("rear_top_y0",  "front_leg_y - leg_thick / 2 + front_top_w + top_gap", "in", "Rear benchtop front edge")

    top_occ = sp.make_comp(root, "Top")
    top_c = top_occ.component
    leg_lf = get_leg("Leg_LF")
    top_anc = ("ltx_L - leg_face_w / 2", "front_leg_y + leg_thick / 2", "under_top")
    top_front = box_zrun(top_c, "0 in", "front_top_y0", "under_top", "bench_l",
                         "front_top_w", "top_thick", "Top_Front", leg_lf, top_anc, +1)
    top_rear = box_zrun(top_c, "0 in", "rear_top_y0", "under_top", "bench_l",
                        "rear_top_w", "top_thick", "Top_Rear", leg_lf, top_anc, +1)

    # Dog holes — two rows between the trestles, evenly spaced and clear of the
    # legs/short stretchers so a holdfast drops into open space. Built as ONE seed
    # hole + a RECTANGULAR PATTERN (n_dog columns × 2 rows). The cut is a SYMMETRIC
    # extent about the board mid-plane, so it passes fully through the board
    # regardless of the sketch-plane normal direction (the old single-direction
    # cut was going the wrong way and removing nothing).
    param("dog_dia",     "0.75 in", "in", "Dog-hole diameter")
    param("dog_margin",  "4 in",    "in", "Clear margin from each trestle to the first/last dog hole")
    param("n_dog",       "6",       "",   "Dog-hole columns between the trestles")
    param("dog_end",     "8 in",    "in", "End dog-hole inset from each bench end (outside the legs)")
    param("dog_row1_y",  "front_top_y0 + 5 in",  "in", "Front dog-hole row Y")
    param("dog_row2_y",  "front_top_y0 + 12 in", "in", "Rear dog-hole row Y")

    def make_dog_holes():
        ztop = ev("under_top") + ev("top_thick")
        zc = ev("under_top") + ev("top_thick") / 2
        pl = sp.off_plane(top_c, top_c.xYConstructionPlane, "under_top + top_thick / 2", "Dog_Pl")
        EXT = adsk.fusion.PatternDistanceType.ExtentPatternDistanceType
        rpf = top_c.features.rectangularPatternFeatures

        def seed_hole(x_e, nm):
            # one through-hole at (x_e, front row); SYMMETRIC cut (direction-proof)
            sk = top_c.sketches.add(pl); sk.name = nm + "_Sk"
            x0, y0 = ev(x_e), ev("dog_row1_y")
            ctr = sk.modelToSketchSpace(P.create(x0, y0, zc))
            circ = sk.sketchCurves.sketchCircles.addByCenterRadius(P.create(ctr.x, ctr.y, 0), ev("dog_dia") / 2)
            d = sk.sketchDimensions
            d.addRadialDimension(circ, P.create(ctr.x + ev("dog_dia"), ctr.y, 0)
                                 ).parameter.expression = "dog_dia / 2"
            sp.project_face(sk, top_front, None, "z", +1)
            anc = sp.anchor_pt(sk, ev("bench_l"), ev("front_top_y0"), ztop)
            orient = sp.probe_orientations(sk, x0, y0, zc)
            sp.rdim(sk, d, anc, circ.centerSketchPoint, orient, "x", "abs((%s) - bench_l)" % x_e)
            sp.rdim(sk, d, anc, circ.centerSketchPoint, orient, "y", "abs(dog_row1_y - front_top_y0)")
            prof = sp.smallest_profile(sk)
            ext_in = top_c.features.extrudeFeatures.createInput(prof, CUT)
            ext_in.setSymmetricExtent(VI("top_thick + 0.5 in"), True, VI("0 deg"))
            ext_in.participantBodies = [top_front]
            f = top_c.features.extrudeFeatures.add(ext_in); f.name = nm
            return f

        def grid(seed, nx_e, span_e, nm):
            coll = adsk.core.ObjectCollection.create(); coll.add(seed)
            pat_in = rpf.createInput(coll, top_c.xConstructionAxis, VI(nx_e), VI(span_e), EXT)
            pat_in.setDirectionTwo(top_c.yConstructionAxis, VI("2"), VI("dog_row2_y - dog_row1_y"))
            p = rpf.add(pat_in); p.name = nm

        # Main grid: n_dog columns × 2 rows, filling between the trestles.
        grid(seed_hole("ltx_L + dog_margin", "Dog_Hole"), "n_dog",
             "ltx_R - ltx_L - 2 * dog_margin", "Dog_Pat")
        # End holes: one column at each bench end (outside the legs) × 2 rows.
        grid(seed_hole("dog_end", "Dog_Hole_End"), "2",
             "bench_l - 2 * dog_end", "Dog_End_Pat")

    make_dog_holes()

    # Bevel the tilted upper short stretchers flush with the benchtop UNDERSIDE.
    # Cut against a PLANE at Z = under_top (not the dog-holed / split top body),
    # so the bevel is clean regardless of what details sit in the top.
    ut = ev("under_top")
    ss_trim_pl = sp.off_plane(short, short.xYConstructionPlane, "under_top", "SS_TopTrim_Pl")
    for ssn in ("SS_LU", "SS_RU"):
        ssb = short.bRepBodies.itemByName(ssn)
        sbf = short.features.splitBodyFeatures
        sbf.add(sbf.createInput(ssb, ss_trim_pl, True))
        frags = [short.bRepBodies.item(i) for i in range(short.bRepBodies.count)
                 if short.bRepBodies.item(i).name == ssn
                 or short.bRepBodies.item(i).name.startswith(ssn + " ")]
        keep = None
        for b in frags:
            if b.boundingBox.minPoint.z > ut - 0.05:
                short.features.removeFeatures.add(b)      # off-cut above the top underside
            else:
                keep = b
        if keep:
            keep.name = ssn

    # ───────────────────────── LOWER SHELF ─────────────────────────
    # Reference: legs / long stretchers. Cleats glued to the inner faces of the
    # long stretchers carry random-width shelf boards spanning front-to-back.
    param("cleat_sq",       "1 in", "in", "Square cleat stock")
    param("front_cleat_y0", "front_leg_y - leg_thick / 2 + ls_thick", "in", "Front cleat front edge (long stretcher inner face)")
    param("shelf_t",        "1 in", "in", "Shelf board thickness")
    param("n_shelf",        "5", "", "Number of shelf boards")
    param("shelf_bw",       "(ltx_R - ltx_L) / n_shelf", "in", "Shelf board pitch")
    param("shelf_z",        "ls_bot_z + cleat_sq", "in", "Shelf board underside (on cleat tops)")
    param("shelf_len_y",    "depth - 2 * front_cleat_y0", "in", "Shelf board length (Y span between cleats)")

    shelf_occ = sp.make_comp(root, "Shelf")
    shelf_c = shelf_occ.component
    leg_anc = (corner_x("L"), "front_leg_y + leg_thick / 2", "0 in")

    # Front cleat (along X on the front long stretcher inner face); mirror to back
    cleat_f = box_zrun(shelf_c, "ltx_L", "front_cleat_y0", "ls_bot_z",
                       "ltx_R - ltx_L", "cleat_sq", "cleat_sq", "Cleat_F", leg_lf, leg_anc)
    ymid_shelf = sp.off_plane(shelf_c, shelf_c.xZConstructionPlane, "y_mid", "Shelf_YMid_Pl")
    cleat_b = sp.mirror_body(shelf_c, cleat_f, ymid_shelf, "Cleat_B_Mir").bodies.item(0)
    cleat_b.name = "Cleat_B"

    # Shelf boards resting on the cleats, patterned across X
    board = box_zrun(shelf_c, "ltx_L", "front_cleat_y0", "shelf_z",
                     "shelf_bw - 0.125 in", "shelf_len_y", "shelf_t", "Shelf_Board_1",
                     leg_lf, leg_anc)
    sp.body_pattern(shelf_c, board, shelf_c.xConstructionAxis, "n_shelf", "shelf_bw", "Shelf_Pat")

    # ───────────────────────── LEG VISE ─────────────────────────
    # Reference: front-left leg (Leg_LF). A chop in front of the leg, a screw
    # and a parallel guide both passing through the leg. The leg leans, so the
    # chop is centred on the leg X midway between the screw and guide heights
    # so both still pass through the leg.
    param("screw_z",        "22 in", "in", "Vise screw height (collar centers in the clear gap below the upper short stretcher)")
    param("vise_chop_thick","1.875 in", "in", "Chop thickness (Y)")
    param("vise_chop_foot", "0.25 in",  "in", "Chop foot height (bottom edge, 1/4 above floor)")
    param("guide_z",        "7.5 in", "in", "Parallel-guide height — low on the chop, well below the long stretcher")
    param("guide_cx",       "ltx_L - leg_run * (under_top - guide_z) / under_top",
          "in", "Parallel-guide X center (leg centerline at the guide height)")
    param("guide_len",      "14.375 in", "in", "Parallel-guide length (Y), runs back through the leg")
    param("guide_hole_dia", "0.25 in", "in", "Parallel-guide pin-hole diameter")
    param("vise_chop_w",    "6.5 in",   "in", "Chop head width (X, wide clamping top)")
    param("chop_shaft_w",   "leg_w",    "in", "Chop shaft width (X, narrow lower leg) = leg width")
    param("chop_head_z",    "screw_z",  "in", "Height where the wide head begins")
    param("chop_trans_z",   "screw_z - 5 in", "in", "Height where the narrow shaft ends (curve spans trans..head)")
    # Chop cove spline mids — picked up from your manual drag of each side
    # (asymmetric). X offset is measured from the leg centerline at that height.
    # Drag the splines in Vise_Chop_Sk to refine; re-sync to capture.
    param("cove_R_x",       "2.587 in",  "in", "Right cove spline mid — X offset from leg centerline")
    param("cove_R_z",       "21.196 in", "in", "Right cove spline mid — Z height")
    param("cove_L_x",       "2.431 in",  "in", "Left cove spline mid — X offset from leg centerline")
    param("cove_L_z",       "20.627 in", "in", "Left cove spline mid — Z height")
    param("screw_dia",      "1.125 in", "in", "Vise screw diameter (Lee Valley 70G0152 tail-vise screw, 1-1/8 in Acme)")
    param("handle_dia",     "1.125 in", "in", "Vise handle bar diameter (1-1/8 in turned wooden tommy bar)")
    param("handle_len",     "13 in",    "in", "Vise handle bar length (X)")
    param("hub_dia",        "1.875 in", "in", "Screw front hub/boss diameter (the cross-handle passes through it)")
    param("hub_len",        "1.5 in",   "in", "Screw front hub length (Y)")
    param("knob_dia",       "1.5 in",   "in", "Handle end-knob (turned bead) diameter")
    param("knob_len",       "0.875 in", "in", "Handle end-knob length")
    param("guide_w",        "2.375 in", "in", "Parallel-guide width (X)")
    param("guide_t",        "0.5 in",   "in", "Parallel-guide thickness (Z)")
    param("front_face_y",   "front_leg_y - leg_thick / 2", "in", "Front leg front face Y")
    param("inner_face_y",   "front_leg_y + leg_thick / 2", "in", "Front leg inner (+Y) face Y — anchor reference")
    param("chop_gap",       "0.5 in",   "in", "Gap between the chop back and the leg front (vise held slightly open)")
    param("chop_front_y",   "front_face_y - chop_gap - vise_chop_thick", "in", "Chop front face Y")
    param("handle_y",       "chop_front_y - 2.1 in", "in", "Handle bar Y — through the hub, in front of the chop")
    param("collar_t",       "0.5 in",   "in", "Screw collar/garter thickness at the leg back")
    # Parallel-guide WEDGED through-tenon into the chop (fox-wedge style: kerfs in
    # the protruding tenon end, wedges driven IN along the tenon axis to spread it)
    param("chop_back_y",    "chop_front_y + vise_chop_thick", "in", "Chop back face Y (toward the leg)")
    param("guide_ten_h",    "1.5 in",   "in", "Guide through-tenon height (Z), reduced from guide_w (shoulders top+bottom)")
    param("gw_sw",          "0.25 in",  "in", "Wedge mouth width (Z) at the tenon end face")
    param("gw_depth",       "1.25 in",  "in", "Wedge / kerf depth into the tenon (< guide_proud, stays in the protruding end)")
    param("gw_off",         "guide_ten_h / 4", "in", "Wedge offset (Z) each side of the tenon center")

    vise_occ = sp.make_comp(root, "LegVise")
    vise_c = vise_occ.component

    def cyl_y(cx_e, cz_e, ya_e, dia_e, ylen_e, name, op=NEW, target=None):
        plane = sp.off_plane(vise_c, vise_c.xZConstructionPlane, ya_e, name + "_Pl")
        sk = vise_c.sketches.add(plane); sk.name = name + "_Sk"
        ctr = sk.modelToSketchSpace(P.create(ev(cx_e), ev(ya_e), ev(cz_e)))
        circ = sk.sketchCurves.sketchCircles.addByCenterRadius(P.create(ctr.x, ctr.y, 0), ev(dia_e) / 2)
        d = sk.sketchDimensions
        d.addRadialDimension(circ, P.create(ctr.x + ev(dia_e), ctr.y, 0)).parameter.expression = "(" + dia_e + ") / 2"
        sp.project_face(sk, leg_lf, legs_occ, "y", 1)
        anc = sp.anchor_pt(sk, ev(corner_x("L")), ev("inner_face_y"), 0)
        orient = sp.probe_orientations(sk, ev(cx_e), ev(ya_e), ev(cz_e))
        sp.rdim(sk, d, anc, circ.centerSketchPoint, orient, "x", "abs((%s) - (%s))" % (cx_e, corner_x("L")))
        sp.rdim(sk, d, anc, circ.centerSketchPoint, orient, "z", "abs(%s)" % cz_e)
        prof = sp.smallest_profile(sk)
        if op == NEW:
            f = sp.ext_new(vise_c, prof, ylen_e, name + "_Ext")
            b = f.bodies.item(0); b.name = name; return b
        return sp.ext_op(vise_c, prof, ylen_e, op, target, name + "_Ext", flip=False)

    def cyl_x(cy_e, cz_e, xa_e, dia_e, xlen_e, name):
        plane = sp.off_plane(vise_c, vise_c.yZConstructionPlane, xa_e, name + "_Pl")
        sk = vise_c.sketches.add(plane); sk.name = name + "_Sk"
        ctr = sk.modelToSketchSpace(P.create(ev(xa_e), ev(cy_e), ev(cz_e)))
        circ = sk.sketchCurves.sketchCircles.addByCenterRadius(P.create(ctr.x, ctr.y, 0), ev(dia_e) / 2)
        d = sk.sketchDimensions
        d.addRadialDimension(circ, P.create(ctr.x + ev(dia_e), ctr.y, 0)).parameter.expression = "(" + dia_e + ") / 2"
        sp.project_face(sk, leg_lf, legs_occ, "y", 1)
        anc = sp.anchor_pt(sk, ev(xa_e), ev("inner_face_y"), 0)
        orient = sp.probe_orientations(sk, ev(xa_e), ev(cy_e), ev(cz_e))
        sp.rdim(sk, d, anc, circ.centerSketchPoint, orient, "y", "abs((%s) - inner_face_y)" % cy_e)
        sp.rdim(sk, d, anc, circ.centerSketchPoint, orient, "z", "abs(%s)" % cz_e)
        prof = sp.smallest_profile(sk)
        f = sp.ext_new(vise_c, prof, xlen_e, name + "_Ext")
        b = f.bodies.item(0); b.name = name; return b

    # Build the vise parts DIRECTLY in the leg-parallel (tilted) orientation —
    # every sketch references the leaning leg centerline lx(z), so there is no
    # axis-aligned build + Move rotation (fully parametric: recomputes if splay
    # changes). lx(z) = LEFT-leg centerline X at height z.
    def lx(z):
        return ev("ltx_L") - ev("leg_run") * (ev("under_top") - z) / ev("under_top")
    cornerL = corner_x("L")
    def lxe(z_e):
        return legcx("L", z_e)

    # Curved chop, leaning with the leg: centerline follows lx(z) at every height
    # (slanted shaft + head sides), horizontal foot (1/4" off the floor) and top
    # (level with the benchtop) — built to final shape, no proud blank, no trims.
    # Draggable fit-point spline coves neck the wide head to the leg-width shaft.
    def build_curved_chop():
        chf = "chop_front_y"
        pl = sp.off_plane(vise_c, vise_c.xZConstructionPlane, chf, "Vise_Chop_Pl")
        sk = vise_c.sketches.add(pl); sk.name = "Vise_Chop_Sk"
        m2 = sk.modelToSketchSpace
        hw = ev("vise_chop_w") / 2; sw = ev("chop_shaft_w") / 2
        fz = ev("vise_chop_foot"); tz = ev("bench_h")
        zt = ev("chop_trans_z"); zh = ev("chop_head_z")
        rmx, rmz = ev("cove_R_x"), ev("cove_R_z")   # right cove mid (your drag)
        lmx, lmz = ev("cove_L_x"), ev("cove_L_z")   # left cove mid (your drag)

        def mp(x, z):
            s = m2(P.create(x, ev(chf), z)); return P.create(s.x, s.y, 0)

        def spline(p2, mid, p3):
            col = adsk.core.ObjectCollection.create()
            for x, z in (p2, mid, p3):
                col.add(mp(x, z))
            return sk.sketchCurves.sketchFittedSplines.add(col)

        # Right + left coves (draggable mid). Centerline follows the leg at each Z.
        spR = spline((lx(zt) + sw, zt), (lx(rmz) + rmx, rmz), (lx(zh) + hw, zh))
        spL = spline((lx(zh) - hw, zh), (lx(lmz) - lmx, lmz), (lx(zt) - sw, zt))
        ln = sk.sketchCurves.sketchLines
        l_shaftR = ln.addByTwoPoints(mp(lx(fz) + sw, fz), spR.startSketchPoint)
        l_headR = ln.addByTwoPoints(spR.endSketchPoint, mp(lx(tz) + hw, tz))
        l_top = ln.addByTwoPoints(l_headR.endSketchPoint, mp(lx(tz) - hw, tz))
        l_headL = ln.addByTwoPoints(l_top.endSketchPoint, spL.startSketchPoint)
        l_shaftL = ln.addByTwoPoints(spL.endSketchPoint, mp(lx(fz) - sw, fz))
        l_bot = ln.addByTwoPoints(l_shaftL.endSketchPoint, l_shaftR.startSketchPoint)
        gc = sk.geometricConstraints
        gc.addHorizontal(l_top); gc.addHorizontal(l_bot)   # level top + foot
        # Each corner is also pinned by an absolute (x, z) dim; the shaft/head
        # sides slant naturally with the leg (redundant z dims skip harmlessly).
        zc_mid = (ev("bench_h") + ev("vise_chop_foot")) / 2
        orient = sp.probe_orientations(sk, lx(zc_mid), ev(chf), zc_mid)
        sp.project_face(sk, leg_lf, legs_occ, "y", 1)
        aP = sp.anchor_pt(sk, ev(cornerL), ev("inner_face_y"), 0)
        d = sk.sketchDimensions
        P1 = l_shaftR.startSketchPoint; P2 = spR.startSketchPoint
        P3 = spR.endSketchPoint;        P4 = l_headR.endSketchPoint
        P5 = l_top.endSketchPoint;      P6 = spL.startSketchPoint
        P7 = spL.endSketchPoint;        P8 = l_shaftL.endSketchPoint

        def pin(pt, xe, ze):
            sp.rdim(sk, d, aP, pt, orient, "x", "abs((%s) - (%s))" % (xe, cornerL))
            sp.rdim(sk, d, aP, pt, orient, "z", "abs(%s)" % ze)
        pin(P1, "%s + chop_shaft_w / 2" % lxe("vise_chop_foot"), "vise_chop_foot")
        pin(P2, "%s + chop_shaft_w / 2" % lxe("chop_trans_z"),   "chop_trans_z")
        pin(P3, "%s + vise_chop_w / 2"  % lxe("chop_head_z"),    "chop_head_z")
        pin(P4, "%s + vise_chop_w / 2"  % lxe("bench_h"),        "bench_h")
        pin(P5, "%s - vise_chop_w / 2"  % lxe("bench_h"),        "bench_h")
        pin(P6, "%s - vise_chop_w / 2"  % lxe("chop_head_z"),    "chop_head_z")
        pin(P7, "%s - chop_shaft_w / 2" % lxe("chop_trans_z"),   "chop_trans_z")
        pin(P8, "%s - chop_shaft_w / 2" % lxe("vise_chop_foot"), "vise_chop_foot")
        prof = sp.smallest_profile(sk)
        f = sp.ext_new(vise_c, prof, "vise_chop_thick", "Vise_Chop_Ext")
        b = f.bodies.item(0); b.name = "Vise_Chop"
        return b

    chop = build_curved_chop()

    # Vise screw + handle hardware — modelled after the Lee Valley 70G0152 tail-
    # vise screw the article specs: a 1-1/8" Acme rod running in Y through the chop
    # head + leg, a front hub/boss, a turned cross-handle (tommy bar) with end
    # knobs passing through the hub, and a back collar/garter. Built as ONE SEPARATE
    # body "Vise_Screw" (so the hardware reads as metal, not the cherry chop); it
    # ties to the bench through the collar's planar contact on the leg back.
    sx_e = legcx("L", "screw_z")
    screw = cyl_y(sx_e, "screw_z", "chop_front_y - 3 in",
                  "screw_dia", "guide_len + 3 in", "Vise_Screw")
    hub = cyl_y(sx_e, "screw_z", "chop_front_y - 3 in", "hub_dia", "hub_len", "Vise_Hub")
    handle = cyl_x("handle_y", "screw_z", "%s - handle_len / 2" % sx_e,
                   "handle_dia", "handle_len", "Vise_Handle")
    knobL = cyl_x("handle_y", "screw_z", "%s - handle_len / 2 - knob_len" % sx_e,
                  "knob_dia", "knob_len + 0.15 in", "Vise_KnobL")
    knobR = cyl_x("handle_y", "screw_z", "%s + handle_len / 2 - 0.15 in" % sx_e,
                  "knob_dia", "knob_len + 0.15 in", "Vise_KnobR")
    collar = cyl_y(sx_e, "screw_z", "inner_face_y", "screw_dia + 0.5 in",
                   "collar_t", "Vise_Collar")
    # Assemble the hardware into one body (each tool overlaps the rod/bar → solid JOINs).
    sp.combine(screw, [hub], JOIN, False, "Vise_JoinHub")
    sp.combine(screw, [handle], JOIN, False, "Vise_JoinHandle")
    sp.combine(screw, [knobL], JOIN, False, "Vise_JoinKnobL")
    sp.combine(screw, [knobR], JOIN, False, "Vise_JoinKnobR")
    sp.combine(screw, [collar], JOIN, False, "Vise_JoinCollar")

    # On-edge bar running in Y whose cross-section is a true RECTANGLE rotated by
    # the leg splay — its long faces parallel to the leg's leaning side faces, its
    # thin faces perpendicular (not a sheared parallelogram). Used for the guide
    # shaft + its tenon. Corners are the rect center (on the leg centerline)
    # ± (h/2)·û_long ± (t/2)·û_perp, with û_long=(sin,cos), û_perp=(cos,-sin).
    def box_yrun_tilt(zc_e, thick_e, height_e, ya_e, ylen_e, name):
        pl = sp.off_plane(vise_c, vise_c.xZConstructionPlane, ya_e, name + "_Pl")
        sk = vise_c.sketches.add(pl); sk.name = name + "_Sk"
        t = ev(thick_e); h = ev(height_e); zc = ev(zc_e); ya = ev(ya_e)
        th = math.sin(ev("splay")), math.cos(ev("splay"))
        s, c = th
        cx0 = lx(zc); h2, t2 = h / 2.0, t / 2.0

        def mp(x, z):
            q = sk.modelToSketchSpace(P.create(x, ya, z)); return P.create(q.x, q.y, 0)
        # corner sign pairs: (long, perp)
        signs = [(1, 1), (1, -1), (-1, -1), (-1, 1)]
        pos = [(cx0 + sl * h2 * s + sp_ * t2 * c, zc + sl * h2 * c - sp_ * t2 * s)
               for (sl, sp_) in signs]
        ln = sk.sketchCurves.sketchLines
        l0 = ln.addByTwoPoints(mp(*pos[0]), mp(*pos[1]))
        l1 = ln.addByTwoPoints(l0.endSketchPoint, mp(*pos[2]))
        l2 = ln.addByTwoPoints(l1.endSketchPoint, mp(*pos[3]))
        ln.addByTwoPoints(l2.endSketchPoint, l0.startSketchPoint)
        pts = [l0.startSketchPoint, l0.endSketchPoint, l1.endSketchPoint, l2.endSketchPoint]
        orient = sp.probe_orientations(sk, cx0, ya, zc)
        sp.project_face(sk, leg_lf, legs_occ, "y", 1)
        aP = sp.anchor_pt(sk, ev(cornerL), ev("inner_face_y"), 0)
        d = sk.sketchDimensions
        cxe = lxe(zc_e); h2e = "(%s) / 2" % height_e; t2e = "(%s) / 2" % thick_e

        def pin(pt, sl, sp_):   # all 4 corners pinned absolutely; edges are tilted
            xe = "(%s) + (%s) * (%s) * sin(splay) + (%s) * (%s) * cos(splay)" % (cxe, sl, h2e, sp_, t2e)
            ze = "(%s) + (%s) * (%s) * cos(splay) - (%s) * (%s) * sin(splay)" % (zc_e, sl, h2e, sp_, t2e)
            sp.rdim(sk, d, aP, pt, orient, "x", "abs((%s) - (%s))" % (xe, cornerL))
            sp.rdim(sk, d, aP, pt, orient, "z", "abs(%s)" % ze)
        for pt, (sl, sp_) in zip(pts, signs):
            pin(pt, str(sl), str(sp_))
        prof = sp.smallest_profile(sk)
        f = sp.ext_new(vise_c, prof, ylen_e, name + "_Ext")
        b = f.bodies.item(0); b.name = name
        return b

    # Parallel guide — a SEPARATE body from the chop. On-edge, leaning parallel to
    # the leg, running in Y. Shaft from the chop back through the leg + out; a
    # reduced through-tenon runs the chop thickness (flush at the front) locked by
    # two wedges. The guide ties to the chop ONLY through the tenon-in-mortise +
    # wedges (mechanical) — it is never JOINed into the chop body.
    guide = box_yrun_tilt("guide_z", "guide_t", "guide_w",
                          "chop_back_y", "guide_len", "Parallel_Guide")
    gten = box_yrun_tilt("guide_z", "guide_t", "guide_ten_h",
                         "chop_front_y", "vise_chop_thick + 0.25 in", "Guide_Tenon")
    sp.combine(guide, [gten], JOIN, False, "Vise_JoinTenon")

    def build_guide_wedge(zc_e, name):
        # Fox/wedged tenon: a wedge in a kerf at the tenon end (flush at the chop
        # front face). Built in the tenon-CENTER plane (X = guide_cx), offset in Z;
        # the pair is then leaned (below) so it follows the tilted tenon — the two
        # wedges end up stacked along the tenon's tall (leg-parallel) axis and each
        # spreads the tenon across that axis.
        pl = sp.off_plane(vise_c, vise_c.yZConstructionPlane, "guide_cx", name + "_Pl")
        sk = vise_c.sketches.add(pl); sk.name = name + "_Sk"
        ytip = ev("chop_front_y")
        zc, sw, dep = ev(zc_e), ev("gw_sw"), ev("gw_depth")
        wx = ev("guide_cx")

        def wp(y, z):
            s = sk.modelToSketchSpace(P.create(wx, y, z)); return P.create(s.x, s.y, 0)
        ln = sk.sketchCurves.sketchLines
        lbase = ln.addByTwoPoints(wp(ytip, zc + sw / 2), wp(ytip, zc - sw / 2))
        ls1 = ln.addByTwoPoints(lbase.endSketchPoint, wp(ytip + dep, zc))
        ln.addByTwoPoints(ls1.endSketchPoint, lbase.startSketchPoint)
        gc = sk.geometricConstraints

        def hv(line):
            a, b = line.startSketchPoint.geometry, line.endSketchPoint.geometry
            if abs(a.x - b.x) < abs(a.y - b.y):
                gc.addVertical(line)
            else:
                gc.addHorizontal(line)
        hv(lbase)
        wor = sp.probe_orientations(sk, wx, ytip, zc)
        sp.project_face(sk, leg_lf, legs_occ, "y", 1)
        aP = sp.anchor_pt(sk, wx, ev("inner_face_y"), 0)
        d = sk.sketchDimensions
        M1, M2 = lbase.startSketchPoint, lbase.endSketchPoint
        AP = ls1.endSketchPoint
        sp.rdim(sk, d, aP, M1, wor, "y", "abs(chop_front_y - inner_face_y)")
        sp.rdim(sk, d, aP, M1, wor, "z", "(%s) + gw_sw / 2" % zc_e)
        sp.rdim(sk, d, M1, M2, wor, "z", "gw_sw")
        sp.rdim(sk, d, M1, AP, wor, "y", "gw_depth")
        sp.rdim(sk, d, M1, AP, wor, "z", "gw_sw / 2")
        prof = sp.smallest_profile(sk)
        wb = sp.ext_new_sym(vise_c, prof, "guide_t / 2", name).bodies.item(0)
        wb.name = name
        return wb

    gw1 = build_guide_wedge("guide_z + gw_off", "Guide_Wedge_1")
    gw2 = build_guide_wedge("guide_z - gw_off", "Guide_Wedge_2")
    # Lean the wedges 15° about the tenon center so they follow the tilted tenon:
    # the Z-stacked pair rotates onto the tenon's tall (leg-parallel) axis.
    move_rot_y([gw1, gw2], "guide_cx", "guide_z", -ev("splay"))

    def make_guide_holes(g):
        # Pin holes through the guide's thin (X) dimension behind the leg,
        # patterned along Y. Anchored to the leg inner face (robust).
        xf = "guide_cx - guide_t"
        pl = sp.off_plane(vise_c, vise_c.yZConstructionPlane, xf, "GuideHole_Pl")
        sk = vise_c.sketches.add(pl); sk.name = "GuideHoles_Sk"
        xfv, y0, gz = ev(xf), ev("inner_face_y") + ev("1.5 in"), ev("guide_z")
        ctr = sk.modelToSketchSpace(P.create(xfv, y0, gz))
        circ = sk.sketchCurves.sketchCircles.addByCenterRadius(P.create(ctr.x, ctr.y, 0),
                                                               ev("guide_hole_dia") / 2)
        d = sk.sketchDimensions
        d.addRadialDimension(circ, P.create(ctr.x + ev("guide_hole_dia"), ctr.y, 0)
                             ).parameter.expression = "guide_hole_dia / 2"
        sp.project_face(sk, leg_lf, legs_occ, "y", 1)
        anc = sp.anchor_pt(sk, xfv, ev("inner_face_y"), 0)
        orient = sp.probe_orientations(sk, xfv, y0, gz)
        sp.rdim(sk, d, anc, circ.centerSketchPoint, orient, "y", "abs(inner_face_y + 1.5 in - inner_face_y)")
        sp.rdim(sk, d, anc, circ.centerSketchPoint, orient, "z", "abs(guide_z)")
        prof = sp.smallest_profile(sk)
        f = sp.ext_op(vise_c, prof, "2 * guide_t", CUT, g, "GuideHole", flip=False)
        sp.feat_pattern(vise_c, f, vise_c.yConstructionAxis, "6", "1 in", "GuideHole_Pat")

    make_guide_holes(guide)

    # ── Cuts (no Move — every piece was built in its final leaning position) ──
    # Leg: screw hole + guide-shaft mortise.
    sp.combine(leg_lf.createForAssemblyContext(legs_occ),
               [screw.createForAssemblyContext(vise_occ)], CUT, True, "Vise_ScrewHole")
    sp.combine(leg_lf.createForAssemblyContext(legs_occ),
               [guide.createForAssemblyContext(vise_occ)], CUT, True, "Vise_GuideMortise")
    # Chop: the guide tenon cuts its through-mortise (keepTool). The guide stays a
    # SEPARATE body, tied to the chop only by this tenon-in-mortise face contact.
    sp.combine(chop, [guide], CUT, True, "Vise_GuideTenonMort")
    # Wedge kerfs cut into the guide tenon (guide is separate → no JOIN refill).
    # Also nick the chop mortise wall so the wedge (built straight, tenon tilted)
    # never overlaps chop material at the front face.
    sp.combine(guide, [gw1], CUT, True, "Guide_Wedge_1_Kerf")
    sp.combine(guide, [gw2], CUT, True, "Guide_Wedge_2_Kerf")
    sp.combine(chop, [gw1], CUT, True, "Guide_Wedge_1_ChopClr")
    sp.combine(chop, [gw2], CUT, True, "Guide_Wedge_2_ChopClr")

    # Screw clearance hole through the chop head (the screw is a SEPARATE body, so
    # it must not interfere with the chop). The chop stays in the cluster via the
    # parallel guide; the screw stays in the cluster via its collar on the leg back.
    sp.combine(chop, [screw], CUT, True, "Vise_ScrewClearance")

    sp.validate_deps(ctx, metadata_path=_MODEL_JSON)

    # ───────────────────────── FINISH ─────────────────────────
    # Baseline species in-script (multi-species coats replayed via MCP from the
    # APPEARANCE SPEC block above).
    sp.apply_appearance("oak")
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
    print("Build complete — bodies: Legs:%d Short:%d Long:%d Wedge:%d Top:%d Shelf:%d Vise:%d" % (
        legs.bRepBodies.count, short.bRepBodies.count, long_c.bRepBodies.count,
        wedge_c.bRepBodies.count, top_c.bRepBodies.count, shelf_c.bRepBodies.count,
        vise_c.bRepBodies.count))
