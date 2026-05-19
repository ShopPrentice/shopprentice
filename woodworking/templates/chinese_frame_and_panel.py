"""Chinese 格角榫 table top — frame + panel + dovetail battens.

Components:
- Rail_Front, Rail_Back (大边, long members with tenon + miter)
- Stile_L, Stile_R (抹头, short members)
- Panel (flush with top, one-shoulder tongue)
- Batten_0, Batten_0 (1) (穿带, sliding dovetail battens)

Frame cross-section (Z axis, outer=top):
  top    ├── panel field ──┤  3/20 frame_t
         ├── tongue/groove ┤  3/20 frame_t
         ├── TENON ────────┤  3/10 frame_t (middle third)
         ├── frame body ───┤  3/10 frame_t (lower third)
         ├── recess ───────┤  1/10 frame_t
  bottom

Miter: 45° on top and bottom thirds, tenon in middle third.
Approach: overlapping members → shape rail (CUT miter triangles +
tenon pentagon) → mirror to right end → mirror to back rail →
CUT stiles with rails.
"""
import adsk.core
import adsk.fusion
import math
from helpers import sp

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation


def run(context):
    ctx = sp.DesignContext()
    root = ctx.root
    params = ctx.params
    ev = ctx.ev
    VI = adsk.core.ValueInput.createByString
    P = adsk.core.Point3D

    def _p(name, expr, unit="in", comment=""):
        e = params.itemByName(name)
        if e: e.expression = expr
        else: params.add(name, VI(expr), unit, comment)

    # ── Parameters ───────────────────────────────────────────────
    _p("frame_w", "3.5 in", "in", "Frame member width")
    _p("frame_t", "1.5 in", "in", "Frame thickness")
    _p("rail_len", "50 in", "in", "Table length (X)")
    _p("stile_len", "24 in", "in", "Table width (Y)")
    _p("recess", "frame_t / 10", "in", "Decorative recess")
    _p("third", "(frame_t - recess) / 3", "in", "One-third of remaining")
    _p("panel_t", "third", "in", "Panel thickness")
    _p("tongue_w", "third / 2", "in", "Panel tongue width")
    _p("tongue_l", "third / 2", "in", "Panel tongue protrusion")
    _p("panel_e", "frame_t - panel_t", "in", "Panel start in Z")
    _p("groove_e", "frame_t - panel_t", "in", "Groove start in Z")
    _p("tenon_shoulder_top", "1.2 in", "in", "Upper tenon shoulder")
    _p("tenon_shoulder_bot", "0.6 in", "in", "Lower tenon shoulder")
    _p("tenon_depth", "1.5 in", "in", "Tenon cutout depth")
    _p("batten_w", "1.5 in", "in", "Batten width")
    _p("batten_count", "2", "", "Number of battens")
    _p("dt_angle", "12 deg", "deg", "Dovetail angle")
    _p("slot_depth", "panel_t * 0.4", "in", "Dovetail slot depth")
    _p("batten_tenon_l", "1 in", "in", "Batten tenon into rail")
    _p("batten_narrow", "batten_w - 2 * slot_depth * tan(dt_angle)", "in",
       "Batten narrow width")

    comp = sp.make_comp(root, "ChineseTableTop").component
    fw = ev("frame_w")
    upper_z = ev("frame_t - third")

    r_mid = sp.off_plane(comp, comp.yZConstructionPlane, "rail_len / 2", "RMid")
    s_mid = sp.off_plane(comp, comp.xZConstructionPlane, "stile_len / 2", "SMid")

    # ── Helper: parametric miter triangle ────────────────────────
    def miter_triangle(plane, plane_z, name):
        sk = comp.sketches.add(plane)
        sk.name = f"{name}_Sk"
        m2s = sk.modelToSketchSpace
        orient = sp.probe_orientations(sk, 0, 0, plane_z)
        pt1 = m2s(P.create(0, 0, plane_z))
        pt2 = m2s(P.create(0, fw, plane_z))
        pt3 = m2s(P.create(fw, fw, plane_z))
        lines = sk.sketchCurves.sketchLines
        l1 = lines.addByTwoPoints(
            P.create(pt1.x, pt1.y, 0), P.create(pt2.x, pt2.y, 0))
        l2 = lines.addByTwoPoints(
            l1.endSketchPoint, P.create(pt3.x, pt3.y, 0))
        lines.addByTwoPoints(l2.endSketchPoint, l1.startSketchPoint)
        d = sk.sketchDimensions
        d.addDistanceDimension(
            sk.originPoint, l1.endSketchPoint,
            orient['y'], P.create(1, 1, 0)
        ).parameter.expression = "frame_w"
        d.addDistanceDimension(
            sk.originPoint, l2.endSketchPoint,
            orient['x'], P.create(1, 1, 0)
        ).parameter.expression = "frame_w"
        return sk, sp.smallest_profile(sk)

    # ── 1. Rail_Front ────────────────────────────────────────────
    sk, prof = sp.sketch_rect_model(
        comp, comp.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "rail_len", "y": "frame_w"},
        "RFront_Sk", ev=ev)
    r_front = sp.ext_new(comp, prof, "frame_t", "RFront").bodies.item(0)
    r_front.name = "Rail_Front"

    # ── 2. Miter CUTs (left end) ─────────────────────────────────
    upper_pl = sp.off_plane(
        comp, comp.xYConstructionPlane, "frame_t - third", "UpperPl")

    sk, prof = miter_triangle(upper_pl, upper_z, "MiterUL")
    miter_ul = sp.ext_op(comp, prof, "third", CUT, r_front, "MiterUL")

    sk, prof = miter_triangle(comp.xYConstructionPlane, 0, "MiterLL")
    miter_ll = sp.ext_op(
        comp, prof, "third + recess", CUT, r_front, "MiterLL")

    # ── 3. Tenon CUT (left end, subtractive pentagon) ────────────
    tst = ev("tenon_shoulder_top")
    tsb = ev("tenon_shoulder_bot")
    td = ev("tenon_depth")

    sk = comp.sketches.add(upper_pl)
    sk.name = "TenonL_Sk"
    m2s = sk.modelToSketchSpace
    orient = sp.probe_orientations(sk, 0, 0, upper_z)

    spts = [m2s(P.create(*p, upper_z)) for p in
            [(0, tsb), (0, fw - tst), (td, fw - tst), (td, td), (tsb, tsb)]]
    lines = sk.sketchCurves.sketchLines
    lA = lines.addByTwoPoints(
        P.create(spts[0].x, spts[0].y, 0),
        P.create(spts[1].x, spts[1].y, 0))
    lD = lines.addByTwoPoints(
        lA.endSketchPoint, P.create(spts[2].x, spts[2].y, 0))
    lB = lines.addByTwoPoints(
        lD.endSketchPoint, P.create(spts[3].x, spts[3].y, 0))
    lDg = lines.addByTwoPoints(
        lB.endSketchPoint, P.create(spts[4].x, spts[4].y, 0))
    lC = lines.addByTwoPoints(lDg.endSketchPoint, lA.startSketchPoint)

    gc = sk.geometricConstraints
    gc.addVertical(lA)
    gc.addHorizontal(lD)
    gc.addVertical(lB)
    gc.addHorizontal(lC)

    d = sk.sketchDimensions
    o = sk.originPoint
    d.addDistanceDimension(
        o, lA.startSketchPoint, orient['y'], P.create(-1, -0.5, 0)
    ).parameter.expression = "tenon_shoulder_bot"
    d.addDistanceDimension(
        o, lA.endSketchPoint, orient['y'], P.create(-1, -3, 0)
    ).parameter.expression = "frame_w - tenon_shoulder_top"
    d.addDistanceDimension(
        o, lD.endSketchPoint, orient['x'], P.create(-1.5, -4, 0)
    ).parameter.expression = "tenon_depth"
    d.addDistanceDimension(
        o, lB.endSketchPoint, orient['y'], P.create(-2, -1.5, 0)
    ).parameter.expression = "tenon_depth"
    d.addDistanceDimension(
        o, lDg.endSketchPoint, orient['x'], P.create(-0.5, -0.5, 0)
    ).parameter.expression = "tenon_shoulder_bot"

    tenon_cut = sp.ext_op(
        comp, sk.profiles.item(0), "-third", CUT, r_front, "TenonCut_L")

    # ── 4. Mirror all to right end ───────────────────────────────
    sp.mirror_feats(
        comp, [miter_ul, miter_ll, tenon_cut], r_mid, "ShapeR_M")

    # ── 5. Mirror Rail_Front → Rail_Back ─────────────────────────
    r_back = sp.mirror_body(
        comp, r_front, s_mid, "RBack_M").bodies.item(0)
    r_back.name = "Rail_Back"

    # ── 6. Stiles ────────────────────────────────────────────────
    sk, prof = sp.sketch_rect_model(
        comp, comp.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "frame_w", "y": "stile_len"},
        "SL_Sk", ev=ev)
    s_left = sp.ext_new(comp, prof, "frame_t", "SL").bodies.item(0)
    s_left.name = "Stile_L"
    s_right = sp.mirror_body(
        comp, s_left, r_mid, "SR_M").bodies.item(0)
    s_right.name = "Stile_R"

    # ── 7. Cut stiles using rails ────────────────────────────────
    sp.combine(s_left, [r_front, r_back], CUT, True, "SL_Cut")
    sp.combine(s_right, [r_front, r_back], CUT, True, "SR_Cut")

    # ── Panel ────────────────────────────────────────────────────
    panel_plane = sp.off_plane(
        comp, comp.xYConstructionPlane, "panel_e", "PanelPl")
    iw = "rail_len - 2 * frame_w"
    ih = "stile_len - 2 * frame_w"

    sk, prof = sp.sketch_rect_model(
        comp, panel_plane,
        ("frame_w", "frame_w", "panel_e"),
        {"x": iw, "y": ih},
        "Panel_Sk", ev=ev)
    panel = sp.ext_new(comp, prof, "panel_t", "Panel").bodies.item(0)
    panel.name = "Panel"

    ff = sp.find_face(panel, "y", -1)
    sk, _ = sp.sketch_rect_model(
        comp, ff,
        ("frame_w - tongue_l", "frame_w", "groove_e"),
        {"x": iw + " + 2 * tongue_l", "z": "tongue_w"},
        "P_TgFr_Sk", ev=ev)
    sp.refs_to_construction(sk)
    tgf = sp.ext_new(comp, sp.smallest_profile(sk), "tongue_l", "P_TgFr")
    tgb = sp.mirror_body(
        comp, tgf.bodies.item(0), s_mid, "P_TgBkM").bodies.item(0)

    lf = sp.find_face(panel, "x", -1)
    sk, _ = sp.sketch_rect_model(
        comp, lf,
        ("frame_w", "frame_w", "groove_e"),
        {"y": ih, "z": "tongue_w"},
        "P_TgL_Sk", ev=ev)
    sp.refs_to_construction(sk)
    tgl = sp.ext_new(comp, sp.smallest_profile(sk), "tongue_l", "P_TgL")
    tgr = sp.mirror_body(
        comp, tgl.bodies.item(0), r_mid, "P_TgRM").bodies.item(0)

    sp.combine(
        panel,
        [tgf.bodies.item(0), tgb, tgl.bodies.item(0), tgr],
        JOIN, False, "P_TgJ")

    for fb in [r_front, r_back, s_left, s_right]:
        sp.combine(fb, panel, CUT, True, f"{fb.name}_PanelCut")

    # ── Battens (octagonal dovetail, pattern) ────────────────────
    n = int(ev("batten_count"))
    pe = ev("panel_e")
    sd = ev("slot_depth")
    bw = ev("batten_w")
    taper = sd * math.tan(ev("dt_angle"))
    nh = bw / 2 - taper
    wh = bw / 2
    cx = ev("frame_w") + ev(
        "(rail_len - 2 * frame_w) / (batten_count + 1)")

    def _dt_sketch(plane, y_val, name):
        """Draw octagonal dovetail profile on an XZ plane."""
        sk = comp.sketches.add(plane)
        sk.name = name
        m2s = sk.modelToSketchSpace
        pts = [
            (cx - wh, 0), (cx - wh, pe), (cx - nh, pe),
            (cx - wh, pe + sd), (cx + wh, pe + sd),
            (cx + nh, pe), (cx + wh, pe), (cx + wh, 0),
        ]
        sps = [m2s(P.create(px, y_val, pz)) for px, pz in pts]
        lines = sk.sketchCurves.sketchLines
        fl = lines.addByTwoPoints(
            P.create(sps[0].x, sps[0].y, 0),
            P.create(sps[1].x, sps[1].y, 0))
        pv = fl.endSketchPoint
        for j in range(2, len(sps)):
            l = lines.addByTwoPoints(
                pv, P.create(sps[j].x, sps[j].y, 0))
            pv = l.endSketchPoint
        lines.addByTwoPoints(pv, fl.startSketchPoint)
        return sk

    # Through-groove tools (extend through tongues)
    gpl = sp.off_plane(
        comp, comp.xZConstructionPlane, "frame_w - tongue_l", "BT_GPl")
    gsk = _dt_sketch(gpl, ev("frame_w - tongue_l"), "BT_GSk")
    gt = sp.ext_new(
        comp, gsk.profiles.item(0),
        "stile_len - 2 * frame_w + 2 * tongue_l", "BT_GT").bodies.item(0)
    all_grooves = [gt]
    if n > 1:
        gpat = sp.body_pattern(
            comp, gt, comp.xConstructionAxis,
            "batten_count",
            "(rail_len - 2 * frame_w) / (batten_count + 1)",
            "BT_GPat")
        for j in range(gpat.bodies.count):
            all_grooves.append(gpat.bodies.item(j))
    sp.combine(panel, all_grooves, CUT, False, "BT_ThroughGroove")

    # Batten body at inner length
    bpl = sp.off_plane(
        comp, comp.xZConstructionPlane, "frame_w", "BT_Pl")
    bsk = _dt_sketch(bpl, ev("frame_w"), "BT_Sk")

    bt = sp.ext_new(
        comp, bsk.profiles.item(0),
        "stile_len - 2 * frame_w", "BT0").bodies.item(0)
    bt.name = "Batten_0"

    # Tenons on batten ends (parameter expressions, not ev() values)
    bt_cx = "frame_w + (rail_len - 2 * frame_w) / (batten_count + 1)"

    front_face = sp.find_face(bt, "y", -1)
    sk_tn, _ = sp.sketch_rect_model(comp, front_face,
        (f"({bt_cx}) - batten_narrow / 2", "frame_w", "recess + third"),
        {"x": "batten_narrow", "z": "third"},
        "BT0_TnF_Sk", ev=ev)
    sp.refs_to_construction(sk_tn)
    tn_f = sp.ext_new(
        comp, sp.smallest_profile(sk_tn), "batten_tenon_l", "BT0_TnF")
    sp.combine(bt, tn_f.bodies.item(0), JOIN, False, "BT0_TnF_J")

    back_face = sp.find_face(bt, "y", +1)
    sk_tn2, _ = sp.sketch_rect_model(comp, back_face,
        (f"({bt_cx}) - batten_narrow / 2", "stile_len - frame_w",
         "recess + third"),
        {"x": "batten_narrow", "z": "third"},
        "BT0_TnB_Sk", ev=ev)
    sp.refs_to_construction(sk_tn2)
    tn_b = sp.ext_new(
        comp, sp.smallest_profile(sk_tn2), "batten_tenon_l", "BT0_TnB")
    sp.combine(bt, tn_b.bodies.item(0), JOIN, False, "BT0_TnB_J")

    # Pattern (after tenons joined)
    all_battens = [bt]
    if n > 1:
        pat = sp.body_pattern(
            comp, bt, comp.xConstructionAxis,
            "batten_count",
            "(rail_len - 2 * frame_w) / (batten_count + 1)",
            "BT_Pat")
        for j in range(pat.bodies.count):
            all_battens.append(pat.bodies.item(j))

    # Through-groove already cut above; CUT rails with battens for mortises
    sp.combine(r_front, all_battens, CUT, True, "BT_FM")
    sp.combine(r_back, all_battens, CUT, True, "BT_BM")

    # ── F2: Vertical door (XZ) ──────────────────────────────────
    _p("door_w", "20 in", "in", "Door width")
    _p("door_h", "36 in", "in", "Door height")

    xf = adsk.core.Matrix3D.create()
    xf.setCell(0, 3, ev("rail_len") + 25.4)
    d_occ = root.occurrences.addNewComponent(xf)
    d_occ.component.name = "ChineseDoor"
    dc = d_occ.component
    fw2 = ev("frame_w"); uz2 = ev("frame_t - third")

    dr_mid = sp.off_plane(dc, dc.yZConstructionPlane, "door_w / 2", "D_RMid")
    ds_mid = sp.off_plane(dc, dc.xYConstructionPlane, "door_h / 2", "D_SMid")

    def door_miter_tri(plane, pz, name):
        sk = dc.sketches.add(plane); sk.name = f"{name}_Sk"
        m = sk.modelToSketchSpace; ori = sp.probe_orientations(sk, 0, pz, 0)
        p1 = m(P.create(0, pz, 0)); p2 = m(P.create(0, pz, fw2))
        p3 = m(P.create(fw2, pz, fw2))
        ln = sk.sketchCurves.sketchLines
        l1 = ln.addByTwoPoints(P.create(p1.x,p1.y,0), P.create(p2.x,p2.y,0))
        l2 = ln.addByTwoPoints(l1.endSketchPoint, P.create(p3.x,p3.y,0))
        ln.addByTwoPoints(l2.endSketchPoint, l1.startSketchPoint)
        d = sk.sketchDimensions
        d.addDistanceDimension(sk.originPoint, l1.endSketchPoint,
            ori['z'], P.create(1,1,0)).parameter.expression = "frame_w"
        d.addDistanceDimension(sk.originPoint, l2.endSketchPoint,
            ori['x'], P.create(1,1,0)).parameter.expression = "frame_w"
        return sk, sp.smallest_profile(sk)

    # Rail_Bot
    sk, prof = sp.sketch_rect_model(dc, dc.xZConstructionPlane,
        ("0 in","0 in","0 in"), {"x":"door_w","z":"frame_w"},
        "D_RBot_Sk", ev=ev)
    dr_bot = sp.ext_new(dc, prof, "frame_t", "D_RBot").bodies.item(0)
    dr_bot.name = "D_Rail_Bot"

    # Miter CUTs
    d_upl = sp.off_plane(dc, dc.xZConstructionPlane, "frame_t - third", "D_UPl")
    sk, prof = door_miter_tri(d_upl, uz2, "D_MUL")
    d_mul = sp.ext_op(dc, prof, "third", CUT, dr_bot, "D_MiterUL")
    sk, prof = door_miter_tri(dc.xZConstructionPlane, 0, "D_MLL")
    d_mll = sp.ext_op(dc, prof, "third + recess", CUT, dr_bot, "D_MiterLL")

    # Tenon CUT
    tst2 = ev("tenon_shoulder_top"); tsb2 = ev("tenon_shoulder_bot")
    td2 = ev("tenon_depth")
    sk = dc.sketches.add(d_upl); sk.name = "D_TenonL_Sk"
    m2 = sk.modelToSketchSpace; ori2 = sp.probe_orientations(sk, 0, uz2, 0)
    spts = [m2(P.create(px, uz2, pz)) for px,pz in
            [(0,tsb2),(0,fw2-tst2),(td2,fw2-tst2),(td2,td2),(tsb2,tsb2)]]
    ln = sk.sketchCurves.sketchLines
    lA = ln.addByTwoPoints(P.create(spts[0].x,spts[0].y,0),
                           P.create(spts[1].x,spts[1].y,0))
    lD = ln.addByTwoPoints(lA.endSketchPoint, P.create(spts[2].x,spts[2].y,0))
    lB = ln.addByTwoPoints(lD.endSketchPoint, P.create(spts[3].x,spts[3].y,0))
    lDg = ln.addByTwoPoints(lB.endSketchPoint, P.create(spts[4].x,spts[4].y,0))
    ln.addByTwoPoints(lDg.endSketchPoint, lA.startSketchPoint)
    gc = sk.geometricConstraints
    gc.addVertical(lA); gc.addHorizontal(lD)
    gc.addVertical(lB); gc.addHorizontal(ln.item(ln.count-1))
    d = sk.sketchDimensions; o = sk.originPoint
    d.addDistanceDimension(o,lA.startSketchPoint,ori2['z'],
        P.create(-1,-0.5,0)).parameter.expression = "tenon_shoulder_bot"
    d.addDistanceDimension(o,lA.endSketchPoint,ori2['z'],
        P.create(-1,-3,0)).parameter.expression = "frame_w - tenon_shoulder_top"
    d.addDistanceDimension(o,lD.endSketchPoint,ori2['x'],
        P.create(-1.5,-4,0)).parameter.expression = "tenon_depth"
    d.addDistanceDimension(o,lB.endSketchPoint,ori2['z'],
        P.create(-2,-1.5,0)).parameter.expression = "tenon_depth"
    d.addDistanceDimension(o,lDg.endSketchPoint,ori2['x'],
        P.create(-0.5,-0.5,0)).parameter.expression = "tenon_shoulder_bot"
    d_tc = sp.ext_op(dc, sk.profiles.item(0), "-third", CUT, dr_bot, "D_TenonCut_L")

    sp.mirror_feats(dc, [d_mul, d_mll, d_tc], dr_mid, "D_ShapeR_M")
    dr_top = sp.mirror_body(dc, dr_bot, ds_mid, "D_RTop_M").bodies.item(0)
    dr_top.name = "D_Rail_Top"

    # Stiles
    sk, prof = sp.sketch_rect_model(dc, dc.xZConstructionPlane,
        ("0 in","0 in","0 in"), {"x":"frame_w","z":"door_h"},
        "D_SL_Sk", ev=ev)
    ds_l = sp.ext_new(dc, prof, "frame_t", "D_SL").bodies.item(0)
    ds_l.name = "D_Stile_L"
    ds_r = sp.mirror_body(dc, ds_l, dr_mid, "D_SR_M").bodies.item(0)
    ds_r.name = "D_Stile_R"
    sp.combine(ds_l, [dr_bot, dr_top], CUT, True, "D_SL_Cut")
    sp.combine(ds_r, [dr_bot, dr_top], CUT, True, "D_SR_Cut")

    # Panel
    diw = "door_w - 2*frame_w"; dih = "door_h - 2*frame_w"
    dpp = sp.off_plane(dc, dc.xZConstructionPlane, "panel_e", "D_PPl")
    sk, prof = sp.sketch_rect_model(dc, dpp,
        ("frame_w","panel_e","frame_w"), {"x":diw,"z":dih},
        "D_Panel_Sk", ev=ev)
    dp = sp.ext_new(dc, prof, "panel_t", "D_Panel").bodies.item(0)
    dp.name = "D_Panel"

    # Tongues (bot/top wider for corners)
    ff = sp.find_face(dp, "z", -1)
    sk,_ = sp.sketch_rect_model(dc, ff,
        ("frame_w - tongue_l","panel_e","frame_w"),
        {"x":diw+" + 2*tongue_l","y":"tongue_w"}, "D_PTgBot_Sk", ev=ev)
    sp.refs_to_construction(sk)
    dtgb = sp.ext_new(dc, sp.smallest_profile(sk), "tongue_l", "D_PTgBot")
    dtgt = sp.mirror_body(dc, dtgb.bodies.item(0), ds_mid, "D_PTgTopM").bodies.item(0)
    lf = sp.find_face(dp, "x", -1)
    sk,_ = sp.sketch_rect_model(dc, lf,
        ("frame_w","panel_e","frame_w"),
        {"z":dih,"y":"tongue_w"}, "D_PTgL_Sk", ev=ev)
    sp.refs_to_construction(sk)
    dtgl = sp.ext_new(dc, sp.smallest_profile(sk), "tongue_l", "D_PTgL")
    dtgr = sp.mirror_body(dc, dtgl.bodies.item(0), dr_mid, "D_PTgRM").bodies.item(0)
    sp.combine(dp, [dtgb.bodies.item(0),dtgt,dtgl.bodies.item(0),dtgr],
               JOIN, False, "D_PTgJ")
    for fb in [dr_bot, dr_top, ds_l, ds_r]:
        sp.combine(fb, dp, CUT, True, f"D_{fb.name}_PCut")
