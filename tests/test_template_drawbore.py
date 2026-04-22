"""Test fixture for drawbore template.

  F1 Horizontal X  — apron (+X) into leg, pins in Y. Template API.
  F2 Horizontal Y  — stretcher (+Y) into leg, pins in X. Template API.
  F3 Cross-comp    — same as F1, two components. Template API.
  F4 Vertical      — beam tenon down into post, pins horizontal. Inline.
  F5 Angled (30°)  — rail into post at 30° tilt, pins perpendicular. Inline.

All tenons have SHOULDERS (smaller than the rail cross-section).
F4/F5 are built inline because the template's pin spacing is
hardcoded in Z and doesn't rotate for non-horizontal tenons.
"""
import adsk.core
import adsk.fusion
import math


def make_comp_at(root, name, x_cm=0.0, y_cm=0.0):
    xf = adsk.core.Matrix3D.create()
    if x_cm != 0.0: xf.setCell(0, 3, x_cm)
    if y_cm != 0.0: xf.setCell(1, 3, y_cm)
    occ = root.occurrences.addNewComponent(xf)
    occ.component.name = name
    return occ


def run(context):
    from helpers import sp
    from woodworking.templates import drawbore as db

    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    P3 = adsk.core.Point3D.create
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
    NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    ctx = sp.DesignContext(design)

    params.add("leg_w", VI("3 in"),   "in", "Leg width")
    params.add("leg_d", VI("3 in"),   "in", "Leg depth")
    params.add("leg_h", VI("10 in"),  "in", "Leg height")
    params.add("ap_l",  VI("8 in"),   "in", "Apron/stretcher length")
    params.add("ap_w",  VI("3 in"),   "in", "Apron height (Z)")
    params.add("ap_t",  VI("1.5 in"), "in", "Apron thickness")
    params.add("ap_z",  VI("5 in"),   "in", "Apron bottom Z")
    params.add("tn_w",  VI("2 in"),   "in", "Tenon width (< ap_w)")
    params.add("tn_t",  VI("0.75 in"), "in", "Tenon thickness (< ap_t)")
    params.add("pin_d", VI("0.375 in"), "in", "Pin diameter")
    params.add("pin_sp", VI("1 in"),  "in", "Pin spacing")

    db.define_params(params, prefix="db",
        tenon_w="tn_w", tenon_thick="tn_t",
        pin_dia="pin_d", pin_sp="pin_sp")

    # ═══════════════════════════════════════════════════════
    # F1: Horizontal X — apron (+X) into leg
    # ═══════════════════════════════════════════════════════
    f1 = make_comp_at(root, "F1_Horiz_X").component

    _, pr = sp.sketch_rect_model(f1, f1.xYConstructionPlane,
        ("ap_l", "0 in", "0 in"),
        {"x": "leg_w", "y": "leg_d"}, "f1_Leg_Sk", ctx.ev)
    f1_leg = sp.ext_new(f1, pr, "leg_h", "f1_Leg").bodies.item(0)
    f1_leg.name = "f1_Leg"

    f1_ap_pl = sp.off_plane(f1, f1.xZConstructionPlane,
                             "(leg_d - ap_t) / 2", "f1_Ap_Pl")
    _, pr = sp.sketch_rect_model(f1, f1_ap_pl,
        ("0 in", "(leg_d - ap_t) / 2", "ap_z"),
        {"x": "ap_l", "z": "ap_w"}, "f1_Ap_Sk", ctx.ev)
    f1_ap = sp.ext_new(f1, pr, "ap_t", "f1_Ap").bodies.item(0)
    f1_ap.name = "f1_Apron"

    db.through(f1,
        tenon_plane=f1.yZConstructionPlane, tenon_plane_offset="ap_l",
        tenon_origin=("ap_l", "(leg_d - db_tt) / 2",
                      "ap_z + (ap_w - db_tw) / 2"),
        tenon_size={"y": "db_tt", "z": "db_tw"},
        tenon_depth="leg_w + 0.25 in",
        pin_plane=f1.xZConstructionPlane, pin_plane_offset="0 in",
        pin_tenon_pos_expr="ap_l + 2 * db_pin_dia",
        pin_z_ctr="ap_z + ap_w / 2", pin_through="leg_d",
        stretcher=f1_ap, name="f1_DB", ev=ctx.ev)

    sp.combine(f1_leg, [f1_ap], CUT, True, "f1_Mort")
    f1_n = f1.bRepBodies.count
    print(f"F1 Horiz_X: {f1_n} bodies — PASS")

    # ═══════════════════════════════════════════════════════
    # F2: Horizontal Y — stretcher (+Y) into leg
    # ═══════════════════════════════════════════════════════
    db.define_params(params, prefix="db2",
        tenon_w="tn_w", tenon_thick="tn_t",
        pin_dia="pin_d", pin_sp="pin_sp")

    f2 = make_comp_at(root, "F2_Horiz_Y",
                       ctx.ev("ap_l + leg_w + 4 in")).component

    _, pr = sp.sketch_rect_model(f2, f2.xYConstructionPlane,
        ("0 in", "ap_l", "0 in"),
        {"x": "leg_w", "y": "leg_d"}, "f2_Leg_Sk", ctx.ev)
    f2_leg = sp.ext_new(f2, pr, "leg_h", "f2_Leg").bodies.item(0)
    f2_leg.name = "f2_Leg"

    f2_st_pl = sp.off_plane(f2, f2.yZConstructionPlane,
                             "(leg_w - ap_t) / 2", "f2_St_Pl")
    _, pr = sp.sketch_rect_model(f2, f2_st_pl,
        ("(leg_w - ap_t) / 2", "0 in", "ap_z"),
        {"y": "ap_l", "z": "ap_w"}, "f2_St_Sk", ctx.ev)
    f2_str = sp.ext_new(f2, pr, "ap_t", "f2_Str").bodies.item(0)
    f2_str.name = "f2_Str"

    db.through(f2,
        tenon_plane=f2.xZConstructionPlane, tenon_plane_offset="ap_l",
        tenon_origin=("(leg_w - db2_tt) / 2", "ap_l",
                      "ap_z + (ap_w - db2_tw) / 2"),
        tenon_size={"x": "db2_tt", "z": "db2_tw"},
        tenon_depth="leg_d + 0.25 in",
        pin_plane=f2.yZConstructionPlane, pin_plane_offset="0 in",
        pin_tenon_pos_expr="ap_l + 2 * db2_pin_dia",
        pin_z_ctr="ap_z + ap_w / 2", pin_through="leg_w",
        stretcher=f2_str, name="f2_DB", ev=ctx.ev)

    sp.combine(f2_leg, [f2_str], CUT, True, "f2_Mort")
    f2_n = f2.bRepBodies.count
    print(f"F2 Horiz_Y: {f2_n} bodies — PASS")

    # ═══════════════════════════════════════════════════════
    # F3: Cross-component (same as F1, 2 comps)
    # ═══════════════════════════════════════════════════════
    f3_x = ctx.ev("ap_l + leg_w + 4 in") * 2
    f3_L = make_comp_at(root, "F3_Leg", f3_x).component
    f3_A = make_comp_at(root, "F3_Apron", f3_x).component

    _, pr = sp.sketch_rect_model(f3_L, f3_L.xYConstructionPlane,
        ("ap_l", "0 in", "0 in"),
        {"x": "leg_w", "y": "leg_d"}, "f3_Leg_Sk", ctx.ev)
    f3_leg = sp.ext_new(f3_L, pr, "leg_h", "f3_Leg").bodies.item(0)
    f3_leg.name = "f3_Leg"

    f3_ap_pl = sp.off_plane(f3_A, f3_A.xZConstructionPlane,
                             "(leg_d - ap_t) / 2", "f3_Ap_Pl")
    _, pr = sp.sketch_rect_model(f3_A, f3_ap_pl,
        ("0 in", "(leg_d - ap_t) / 2", "ap_z"),
        {"x": "ap_l", "z": "ap_w"}, "f3_Ap_Sk", ctx.ev)
    f3_ap = sp.ext_new(f3_A, pr, "ap_t", "f3_Ap").bodies.item(0)
    f3_ap.name = "f3_Apron"

    db.through(f3_A,
        tenon_plane=f3_A.yZConstructionPlane, tenon_plane_offset="ap_l",
        tenon_origin=("ap_l", "(leg_d - db_tt) / 2",
                      "ap_z + (ap_w - db_tw) / 2"),
        tenon_size={"y": "db_tt", "z": "db_tw"},
        tenon_depth="leg_w + 0.25 in",
        pin_plane=f3_A.xZConstructionPlane, pin_plane_offset="0 in",
        pin_tenon_pos_expr="ap_l + 2 * db_pin_dia",
        pin_z_ctr="ap_z + ap_w / 2", pin_through="leg_d",
        stretcher=f3_ap, name="f3_DB", ev=ctx.ev)

    sp.combine(f3_leg, [f3_ap], CUT, True, "f3_Mort")
    f3_n = f3_L.bRepBodies.count + f3_A.bRepBodies.count
    assert f3_n == f1_n
    print(f"F3 Cross: {f3_n} bodies — PASS")

    # ═══════════════════════════════════════════════════════
    # F4: Vertical — beam tenon DOWN into post (inline, no template)
    # ═══════════════════════════════════════════════════════
    # Post standing Z=[0, post_h]. Beam sits on top at Z=post_h,
    # tenon extrudes DOWN (-Z) into post.
    params.add("post_w", VI("4 in"), "in", "Post width")
    params.add("post_h", VI("8 in"), "in", "Post height")
    params.add("beam_l", VI("10 in"), "in", "Beam length")
    params.add("beam_w", VI("3 in"), "in", "Beam width")
    params.add("beam_t", VI("2 in"), "in", "Beam thickness")
    f4_x = f3_x + ctx.ev("ap_l + leg_w + 4 in")
    f4 = make_comp_at(root, "F4_Vertical", f4_x).component
    ev = ctx.ev

    pw = ev("post_w"); ph = ev("post_h")
    bl = ev("beam_l"); bw = ev("beam_w"); bt = ev("beam_t")
    tw = ev("tn_w"); tt = ev("tn_t")
    pd = ev("pin_d"); ps = ev("pin_sp")

    # Post
    _, pr = sp.sketch_rect_model(f4, f4.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "post_w", "y": "post_w"}, "f4_Post_Sk", ctx.ev)
    f4_post = sp.ext_new(f4, pr, "post_h", "f4_Post").bodies.item(0)
    f4_post.name = "f4_Post"

    # Beam on top, centered on post
    beam_pl = sp.off_plane(f4, f4.xYConstructionPlane, "post_h", "f4_BeamPl")
    bx0 = (pw - bt) / 2  # beam centered on post in X
    by0 = (pw - bl) / 2  # centered in Y (beam overhangs)
    _, pr = sp.sketch_rect_model(f4, beam_pl,
        (f"{bx0} cm", f"{by0} cm", "post_h"),
        {"x": f"{bt} cm", "y": f"{bl} cm"}, "f4_Beam_Sk", ctx.ev)
    f4_beam = sp.ext_new(f4, pr, f"{bw} cm", "f4_Beam").bodies.item(0)
    f4_beam.name = "f4_Beam"

    # Tenon: sketch rect on the beam's BOTTOM face, extrude DOWN
    # into the post. Tenon smaller than beam cross-section.
    tn_sk = f4.sketches.add(beam_pl)
    tn_sk.name = "f4_Tn_Sk"
    m = tn_sk.modelToSketchSpace
    tx0 = (pw - tt) / 2; ty0 = (pw - tw) / 2
    sp1 = m(P3(tx0, ty0, ph)); sp2 = m(P3(tx0 + tt, ty0 + tw, ph))
    tn_sk.sketchCurves.sketchLines.addTwoPointRectangle(
        P3(sp1.x, sp1.y, 0), P3(sp2.x, sp2.y, 0))
    tn_prof = sp.smallest_profile(tn_sk)
    tn_inp = f4.features.extrudeFeatures.createInput(tn_prof, NEW)
    tn_inp.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(VI("post_w")),
        adsk.fusion.ExtentDirections.NegativeExtentDirection)
    tn_body = f4.features.extrudeFeatures.add(tn_inp).bodies.item(0)
    tn_body.name = "f4_Tenon"

    # Pins: 2 circles on post's FRONT face (Y=0 plane), extrude in +Y.
    # Pin positions: X = post center, Z = tenon center ± pin_sp/2.
    pin_sk = f4.sketches.add(f4.xZConstructionPlane)
    pin_sk.name = "f4_Pin_Sk"
    m2 = pin_sk.modelToSketchSpace
    tn_ctr_z = ph - pw / 2  # tenon mid-Z inside post
    for dz in [-ps / 2, ps / 2]:
        c = m2(P3(pw / 2, 0, tn_ctr_z + dz))
        pin_sk.sketchCurves.sketchCircles.addByCenterRadius(
            P3(c.x, c.y, 0), pd / 2)
    pin_bodies = []
    for j in range(pin_sk.profiles.count):
        p = pin_sk.profiles.item(j)
        if p.areaProperties().area < 1.0:
            ext = sp.ext_new(f4, p, "post_w", f"f4_Pin_{j}")
            ext.bodies.item(0).name = f"f4_Pin_{j}"
            pin_bodies.append(ext.bodies.item(0))

    # JOIN tenon to beam, CUT beam with pins, CUT post with beam
    sp.combine(f4_beam, tn_body, JOIN, False, "f4_TnJoin")
    if pin_bodies:
        sp.combine(f4_beam, pin_bodies, CUT, True, "f4_PinCut")
    sp.combine(f4_post, [f4_beam], CUT, True, "f4_Mort")

    f4_n = f4.bRepBodies.count
    print(f"F4 Vertical: {f4_n} bodies — PASS")

    # ═══════════════════════════════════════════════════════
    # F5: Angled 30° — rail into post at an angle (inline)
    # ═══════════════════════════════════════════════════════
    # Post vertical. Rail meets post at Z=ap_z, tilted 30° from
    # horizontal. Tenon + pins built at the angle.
    ang = 30  # degrees
    ang_r = math.radians(ang)
    f5_x = f4_x + pw + 6 * 2.54
    f5 = make_comp_at(root, "F5_Angled_30", f5_x).component

    # Post
    _, pr = sp.sketch_rect_model(f5, f5.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "post_w", "y": "post_w"}, "f5_Post_Sk", ctx.ev)
    f5_post = sp.ext_new(f5, pr, "post_h", "f5_Post").bodies.item(0)
    f5_post.name = "f5_Post"

    # Rail extends in +Y from the post's +Y face. Sketch on yZ plane
    # so the rail's length (Y) and height (Z) are the in-plane axes.
    rl = ev("ap_l"); rw = ev("ap_w"); rt = ev("ap_t")
    rail_z = ev("ap_z")
    rail_pl = sp.off_plane(f5, f5.yZConstructionPlane,
                            "(post_w - ap_t) / 2", "f5_RailPl")
    _, pr = sp.sketch_rect_model(f5, rail_pl,
        ("(post_w - ap_t) / 2", "post_w", "ap_z"),
        {"y": "ap_l", "z": "ap_w"}, "f5_Rail_Sk", ctx.ev)
    f5_rail = sp.ext_new(f5, pr, "ap_t", "f5_Rail").bodies.item(0)
    f5_rail.name = "f5_Rail"

    # Tenon: sketch on xZ plane at Y=post_w (post's +Y face),
    # extrude in -Y into the post. Tenon smaller than rail.
    tn_pl5 = sp.off_plane(f5, f5.xZConstructionPlane,
                           "post_w", "f5_TnPl")
    tn_sk5 = f5.sketches.add(tn_pl5)
    tn_sk5.name = "f5_Tn_Sk"
    m5 = tn_sk5.modelToSketchSpace
    tx = (pw - tt) / 2; tz = rail_z + (rw - tw) / 2
    s1 = m5(P3(tx, pw, tz)); s2 = m5(P3(tx + tt, pw, tz + tw))
    tn_sk5.sketchCurves.sketchLines.addTwoPointRectangle(
        P3(s1.x, s1.y, 0), P3(s2.x, s2.y, 0))
    tn_prof5 = sp.smallest_profile(tn_sk5)
    tn_inp5 = f5.features.extrudeFeatures.createInput(tn_prof5, NEW)
    tn_inp5.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(VI("post_w + 0.25 in")),
        adsk.fusion.ExtentDirections.NegativeExtentDirection)
    tn5 = f5.features.extrudeFeatures.add(tn_inp5).bodies.item(0)
    tn5.name = "f5_Tenon"

    # Pins: sketch on post's front face (xZ at Y=0), extrude +Y
    # through the post and tenon. Two pins spaced in Z.
    pin_sk5 = f5.sketches.add(f5.xZConstructionPlane)
    pin_sk5.name = "f5_Pin_Sk"
    m5p = pin_sk5.modelToSketchSpace
    pin_y5 = pw * 2 / 3  # 2/3 into the post from the shoulder
    for dz in [-ps / 2, ps / 2]:
        c = m5p(P3(pw / 2, 0, rail_z + rw / 2 + dz))
        pin_sk5.sketchCurves.sketchCircles.addByCenterRadius(
            P3(c.x, c.y, 0), pd / 2)
    pin5_bodies = []
    for j in range(pin_sk5.profiles.count):
        p = pin_sk5.profiles.item(j)
        if p.areaProperties().area < 1.0:
            ext = sp.ext_new(f5, p, "post_w", f"f5_Pin_{j}")
            ext.bodies.item(0).name = f"f5_Pin_{j}"
            pin5_bodies.append(ext.bodies.item(0))

    # JOIN tenon to rail, CUT rail with pins, CUT post with rail
    sp.combine(f5_rail, tn5, JOIN, False, "f5_TnJoin")
    if pin5_bodies:
        sp.combine(f5_rail, pin5_bodies, CUT, True, "f5_PinCut")
    sp.combine(f5_post, [f5_rail], CUT, True, "f5_Mort")

    # Tilt rail + pins by 30° around X axis at the junction point.
    # The post stays vertical; the rail rotates upward.
    pivot = P3(pw / 2, pw, rail_z + rw / 2)
    rot = adsk.core.Matrix3D.create()
    rot.setToRotation(ang_r, adsk.core.Vector3D.create(1, 0, 0), pivot)
    tilt_coll = adsk.core.ObjectCollection.create()
    for bi in range(f5.bRepBodies.count):
        b = f5.bRepBodies.item(bi)
        if b.name != "f5_Post":
            tilt_coll.add(b)
    if tilt_coll.count > 0:
        tilt_inp = f5.features.moveFeatures.createInput2(tilt_coll)
        tilt_inp.defineAsFreeMove(rot)
        f5.features.moveFeatures.add(tilt_inp).name = "f5_Tilt"

    f5_n = f5.bRepBodies.count
    print(f"F5 Angled_30: {f5_n} bodies — PASS")

    # ── Summary ──
    total = 0
    for occ in root.occurrences:
        c = occ.component
        n = c.bRepBodies.count
        names = [c.bRepBodies.item(i).name for i in range(n)]
        print(f"  {c.name}: {n} -> {names}")
        total += n
    print(f"\nTotal: {total} bodies")

    for occ in root.occurrences:
        c = occ.component
        for sk in c.sketches:
            sk.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
