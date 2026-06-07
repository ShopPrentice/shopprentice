"""Classic Ming Table v2 — after John Cameron, FWW #306/#308.

Component-organized parametric build:
  Legs / Top (flush frame-and-panel + dovetail battens) / Aprons / Spandrels / Shelf
Coordinates (inches, centered): X=length, Y=depth, Z=up, floor at Z=0.
Cross-component CUTs use assembly-context proxies in root.
"""
import adsk.core, adsk.fusion, math
from helpers import sp

P = adsk.core.Point3D.create
VI = adsk.core.ValueInput.createByString
NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
IN = 2.54


def run(context):
    ctx = sp.DesignContext()
    design = ctx.design
    root = ctx.root
    ev = ctx.ev
    fb = ctx.find_body
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    params = design.userParameters

    def add(n, e, u, c=""):
        if not params.itemByName(n):
            params.add(n, VI(e), u, c)

    # ---------------- Parameters ----------------
    # Every parameter is a DIMENSION (length/width/thickness/depth/angle); positions
    # are DERIVED expressions of those dimensions so the model survives resizing and
    # moving (see the no-absolute-coordinates rule). "(derived)" = computed, not set.
    # --- Envelope ---
    add("table_l", "28 in", "in", "Overall table length (X)")
    add("table_d", "13.75 in", "in", "Overall table depth (Y)")
    add("table_h", "30.875 in", "in", "Overall table height, floor to top surface")
    add("splay", "1.5 deg", "deg", "Leg splay/rake angle from vertical, per axis")
    # --- Top frame & panel ---
    add("tf_t", "0.6875 in", "in", "Top-frame stock thickness (vertical)")
    add("tf_w", "2 in", "in", "Top-frame member width")
    add("tf_bot", "table_h - tf_t", "in", "Z of the frame underside (derived)")
    add("panel_t", "0.3125 in", "in", "Top-panel thickness")
    add("panel_under", "table_h - panel_t", "in", "Z of the panel underside (derived)")
    add("tongue_ov", "0.25 in", "in", "Panel tongue protrusion into the frame groove")
    add("tongue_w", "panel_t / 2", "in", "Panel tongue thickness")
    add("tf_cham_d", "0.104 in", "in", "Top-frame edge profile depth (inward from outer face)")
    add("tf_cham_h", "tf_t", "in", "Top-frame edge profile height (up from bottom face)")
    add("sf_cham", "0.3125 in", "in", "Shelf-frame edge profile depth/width")
    # --- Legs ---  (legs sit at X=+/-ltx, Y=+/-lty; set ltx/lty via the setbacks)
    add("leg_dia", "1.375 in", "in", "Leg diameter (round leg)")
    add("leg_r", "leg_dia / 2", "in", "Leg radius (derived)")
    add("leg_setback_x", "5.375 in", "in", "Distance each leg is set in from the table END (X)")
    add("leg_setback_y", "1.125 in", "in", "Distance each leg is set in from the table SIDE (Y)")
    add("ltx", "table_l / 2 - leg_setback_x", "in", "Leg half-spread in X = legs at +/-ltx (derived)")
    add("lty", "table_d / 2 - leg_setback_y", "in", "Leg half-spread in Y = legs at +/-lty (derived)")
    add("leg_embed", "0.5 in", "in", "How far the leg top embeds up into the frame")
    add("leg_tip_z", "tf_bot + leg_embed", "in", "Z of the leg top (derived)")
    # --- Apron ---
    add("apron_t", "0.375 in", "in", "Apron stock thickness")
    add("apron_w", "1.125 in", "in", "Apron height (band width)")
    add("fbd_lip", "0.1 in", "in", "Hidden dovetail lip thickness")
    add("fbd_pad", "0.1 in", "in", "Hidden dovetail end padding")
    add("fbd_angle", "10 deg", "deg", "Hidden dovetail angle")
    add("fbd_tail_w", "0.225 in", "in", "Dovetail tail width at wide face")
    add("fbd_tail_count", "3", "", "Number of dovetail tails")
    add("fbd_socket", "apron_t - fbd_lip", "in", "Tail penetration depth (derived)")
    add("fbd_narrow_w", "fbd_tail_w - 2 * fbd_socket * tan(fbd_angle)", "in", "Tail narrow width (derived)")
    add("fbd_pitch", "(apron_w - 2 * fbd_pad) / fbd_tail_count", "in", "Tail pitch (derived)")
    add("spandrel_depth", "3 9/16 in", "in", "Spandrel vertical extent below the apron")
    add("slot_botz", "tf_bot - apron_w - spandrel_depth", "in", "Spandrel/leg-slot bottom Z (derived)")
    # --- Shelf ---
    add("shelf_z", "20 in", "in", "Shelf top height above the floor")
    add("sf_t", "0.875 in", "in", "Shelf-frame stock thickness")
    add("sf_w", "1.375 in", "in", "Shelf-frame member width")
    add("sp_panel_t", "0.3125 in", "in", "Shelf-panel thickness")
    # --- Top battens (sliding dovetail to panel, tenon to frame) ---
    add("bt_w", "0.875 in", "in", "Top-batten width")
    add("bt_h", "tf_t - panel_t", "in", "Top-batten height (derived)")
    add("bt_off", "7 in", "in", "Top-batten offset from center (+/-)")
    add("bt_dt_base", "0.5 in", "in", "Batten dovetail base width (narrow side)")
    add("bt_dt_top", "0.75 in", "in", "Batten dovetail top width (wide side)")
    add("bt_dt_d", "0.1875 in", "in", "Batten dovetail depth into the panel")

    # ---------------- helpers ----------------
    def boxcm(comp, name, x0, x1, y0, y1, zexpr, hexpr, op=NEW, tgt=None):
        pl = sp.off_plane(comp, comp.xYConstructionPlane, zexpr, name + "_Pl")
        sk = comp.sketches.add(pl); sk.name = name + "_Sk"
        rc = sk.sketchCurves.sketchLines.addTwoPointRectangle(P(x0, y0, 0), P(x1, y1, 0))
        gc = sk.geometricConstraints
        gc.addHorizontal(rc[0]); gc.addHorizontal(rc[2])
        gc.addVertical(rc[1]); gc.addVertical(rc[3])
        if op == NEW:
            b = sp.ext_new(comp, sk.profiles.item(0), hexpr, name).bodies.item(0)
            b.name = name
            return b
        return sp.ext_op(comp, sk.profiles.item(0), hexpr, op, tgt, name)

    def pbox(comp, name, x0_e, x1_e, y0_e, y1_e, zexpr, hexpr, op=NEW, tgt=None):
        # Fully-PARAMETRIC box on the XY plane at zexpr: the 4 edges are EXPRESSION
        # strings, so the body tracks parameter changes (unlike boxcm, which bakes the
        # coords). Origin-distance position dims use positive magnitudes (geometry is
        # placed on the correct side, so the unsigned dim doesn't flip). Pass x0<x1, y0<y1.
        _H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
        _V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
        x0, x1, y0, y1 = ev(x0_e), ev(x1_e), ev(y0_e), ev(y1_e)
        pl = sp.off_plane(comp, comp.xYConstructionPlane, zexpr, name + "_Pl")
        sk = comp.sketches.add(pl); sk.name = name + "_Sk"
        rc = sk.sketchCurves.sketchLines.addTwoPointRectangle(P(x0, y0, 0), P(x1, y1, 0))
        gc = sk.geometricConstraints
        gc.addHorizontal(rc[0]); gc.addHorizontal(rc[2])
        gc.addVertical(rc[1]); gc.addVertical(rc[3])
        d = sk.sketchDimensions; bl = rc[0].startSketchPoint
        d.addDistanceDimension(rc[0].startSketchPoint, rc[0].endSketchPoint, _H,
                               P((x0+x1)/2, y0-1, 0)).parameter.expression = "(%s) - (%s)" % (x1_e, x0_e)
        d.addDistanceDimension(rc[1].startSketchPoint, rc[1].endSketchPoint, _V,
                               P(x1+1, (y0+y1)/2, 0)).parameter.expression = "(%s) - (%s)" % (y1_e, y0_e)
        d.addDistanceDimension(sk.originPoint, bl, _H, P(x0/2, y0-2, 0)
                               ).parameter.expression = ("-(%s)" % x0_e) if x0 < 0 else x0_e
        d.addDistanceDimension(sk.originPoint, bl, _V, P(x0-1, y0/2, 0)
                               ).parameter.expression = ("-(%s)" % y0_e) if y0 < 0 else y0_e
        if op == NEW:
            b = sp.ext_new(comp, sk.profiles.item(0), hexpr, name).bodies.item(0)
            b.name = name
            return b
        return sp.ext_op(comp, sk.profiles.item(0), hexpr, op, tgt, name)

    def boxin(comp, name, x0, x1, y0, y1, zexpr, hexpr):
        return boxcm(comp, name, x0*IN, x1*IN, y0*IN, y1*IN, zexpr, hexpr)

    # ============================================================
    # LEGS  (component)
    # ============================================================
    occ_legs = sp.make_comp(root, "Legs")
    legc = occ_legs.component
    splay_rad = ev("splay")
    lx, ly, tz = -ev("ltx"), -ev("lty"), ev("leg_tip_z")
    HOR = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    VER = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
    # Splayed leg via SWEEP along a sketched centerline (foot on the floor up to
    # the top under the table). The centerline carries the compound 1.5 deg splay
    # intrinsically — no extrude+rotate. The leg plane (Leg_FL_Plane) and centerline
    # are reused below to build the leg-parallel apron plane. Legs are the root
    # component, so floor-origin dims are allowed here.
    add("foot_off", "leg_tip_z * tan(splay)", "in", "Leg foot splay offset per axis (derived)")
    offv = ev("foot_off")
    Tp = (lx, ly, tz); Fp = (lx - offv, ly - offv, 0.0)
    pls = legc.constructionPlanes
    # lean-direction line on the floor: leg-top projection -> foot
    fsk = legc.sketches.add(legc.xYConstructionPlane); fsk.name = "Leg_FL_Floor_Sk"
    Lln = fsk.sketchCurves.sketchLines.addByTwoPoints(P(lx, ly, 0), P(lx - offv, ly - offv, 0))
    fd = fsk.sketchDimensions
    # Root component: the leg is laid out from the floor centerline. Dimension its
    # position by the DIMENSIONS that define it (table half-extent minus the leg
    # setback), not the coordinate-like ltx/lty.
    fd.addDistanceDimension(fsk.originPoint, Lln.startSketchPoint, HOR, P(lx/2, ly-1, 0)).parameter.expression = "table_l / 2 - leg_setback_x"
    fd.addDistanceDimension(fsk.originPoint, Lln.startSketchPoint, VER, P(lx-1, ly/2, 0)).parameter.expression = "table_d / 2 - leg_setback_y"
    fd.addDistanceDimension(Lln.startSketchPoint, Lln.endSketchPoint, HOR, P(lx-2, ly-2, 0)).parameter.expression = "foot_off"
    fd.addDistanceDimension(Lln.startSketchPoint, Lln.endSketchPoint, VER, P(lx-3, ly-2, 0)).parameter.expression = "foot_off"
    # vertical plane containing the lean line — so the centerline lives on a real plane
    _pi = pls.createInput(); _pi.setByAngle(Lln, VI("90 deg"), legc.xYConstructionPlane)
    legpl = pls.add(_pi); legpl.name = "Leg_FL_Plane"
    # leg centerline (foot on floor -> top), on that plane
    csk = legc.sketches.add(legpl); csk.name = "Leg_FL_CL_Sk"
    _m = csk.modelToSketchSpace; _sF = _m(P(*Fp)); _sT = _m(P(*Tp))
    cl = csk.sketchCurves.sketchLines.addByTwoPoints(P(_sF.x, _sF.y, 0), P(_sT.x, _sT.y, 0))
    # fully constrain: foot coincident with the (parameter-driven) floor-line foot;
    # top directly above the floor-line top-projection by leg_tip_z.
    _pfl = csk.project(Lln).item(0)
    _cgc = csk.geometricConstraints
    _cgc.addCoincident(cl.startSketchPoint, _pfl.endSketchPoint)        # foot
    _vrt = csk.sketchCurves.sketchLines.addByTwoPoints(_pfl.startSketchPoint, cl.endSketchPoint)
    _vrt.isConstruction = True
    _cgc.addVertical(_vrt)                                              # top above top-proj
    _cor = sp.probe_orientations(csk, lx, ly, 0.0)
    csk.sketchDimensions.addDistanceDimension(_pfl.startSketchPoint, cl.endSketchPoint,
        _cor['z'], P(_sT.x, _sT.y, 0)).parameter.expression = "leg_tip_z"
    legpath = legc.features.createPath(cl, False)   # isChain=False: just the centerline
    # circle profile on a plane perpendicular to the centerline at the top, then sweep
    _pp = pls.createInput(); _pp.setByDistanceOnPath(legpath, adsk.core.ValueInput.createByReal(1.0))
    perp = pls.add(_pp); perp.name = "Leg_FL_Top_Pl"
    rsk = legc.sketches.add(perp); rsk.name = "Leg_FL_Sk"
    _cT = rsk.modelToSketchSpace(P(*Tp))
    rc = rsk.sketchCurves.sketchCircles.addByCenterRadius(P(_cT.x, _cT.y, 0), ev("leg_r"))
    rsk.sketchDimensions.addRadialDimension(rc, P(_cT.x + ev("leg_r"), _cT.y, 0)).parameter.expression = "leg_r"
    # the perpendicular plane's origin sits ON the path top, so pin the circle
    # center to the sketch origin (avoids a profile->path circular reference that
    # makes the sweep invalid).
    rsk.geometricConstraints.addCoincident(rc.centerSketchPoint, rsk.originPoint)
    _sw = legc.features.sweepFeatures.createInput(rsk.profiles.item(0), legpath, NEW)
    leg = legc.features.sweepFeatures.add(_sw).bodies.item(0)
    leg.name = "Leg_FL"

    # Through-slot, SWEPT along the upper leg centerline so it follows the lean
    # (all four legs identical -> symmetric joint). Y-band gap (slot_gap, < spandrel
    # thickness) spanning the leg in X, from slot_botz up to the leg top.
    add("slot_w", "1.9685 in", "in", "Leg slot width (spans the leg in X)")
    add("slot_gap", "0.25 in", "in", "Leg slot gap in Y (< spandrel thickness)")
    _sb = ev("slot_botz"); _t = _sb / tz
    Sp = (Fp[0] + _t*(Tp[0]-Fp[0]), Fp[1] + _t*(Tp[1]-Fp[1]), _sb)
    scsk = legc.sketches.add(legpl); scsk.name = "Leg_FL_SlotCL_Sk"
    _ms = scsk.modelToSketchSpace; _sS = _ms(P(*Sp)); _sT2 = _ms(P(*Tp))
    scl = scsk.sketchCurves.sketchLines.addByTwoPoints(P(_sS.x, _sS.y, 0), P(_sT2.x, _sT2.y, 0))
    # on the leg axis: collinear with the projected centerline, top coincident with
    # the leg top; foot height set below.
    _pcl = scsk.project(cl).item(0)
    _sgc = scsk.geometricConstraints
    _sgc.addCollinear(scl, _pcl)
    _sgc.addCoincident(scl.endSketchPoint, _pcl.endSketchPoint)
    _sor = sp.probe_orientations(scsk, lx, ly, 0.0)
    scsk.sketchDimensions.addDistanceDimension(_pcl.startSketchPoint, scl.startSketchPoint,
        _sor['z'], P(_sS.x, _sS.y, 0)).parameter.expression = "slot_botz"
    spath = legc.features.createPath(scl, False)   # isChain=False: just the slot centerline
    _spp = pls.createInput(); _spp.setByDistanceOnPath(spath, adsk.core.ValueInput.createByReal(0.0))
    sperp = pls.add(_spp); sperp.name = "Leg_FL_Slot_Pl"
    rsk2 = legc.sketches.add(sperp); rsk2.name = "Leg_FL_Slot_Sk"
    _m4 = rsk2.modelToSketchSpace; _sw2, _sg = ev("slot_w"), ev("slot_gap")
    _cc = [(Sp[0]-_sw2/2, Sp[1]-_sg/2), (Sp[0]+_sw2/2, Sp[1]-_sg/2),
           (Sp[0]+_sw2/2, Sp[1]+_sg/2), (Sp[0]-_sw2/2, Sp[1]+_sg/2)]
    _pts = [_m4(P(c[0], c[1], Sp[2])) for c in _cc]
    _sl = rsk2.sketchCurves.sketchLines
    _e0 = _sl.addByTwoPoints(P(_pts[0].x,_pts[0].y,0), P(_pts[1].x,_pts[1].y,0))
    _e1 = _sl.addByTwoPoints(_e0.endSketchPoint, P(_pts[2].x,_pts[2].y,0))
    _e2 = _sl.addByTwoPoints(_e1.endSketchPoint, P(_pts[3].x,_pts[3].y,0))
    _e3 = _sl.addByTwoPoints(_e2.endSketchPoint, _e0.startSketchPoint)
    # fully constrain the slot cross-section WITHOUT forcing H/V: the perpendicular
    # plane is compound-tilted, so world X/Y map to OBLIQUE sketch directions and H/V
    # would rotate the slot off world-Y and break the fork. Keep the gap world-aligned
    # by making edges parallel to the projected world planes, sized by offset dims.
    _rgc = rsk2.geometricConstraints
    _lx = rsk2.project(legc.xConstructionAxis).item(0); _lx.isConstruction = True
    _ly = rsk2.project(legc.yConstructionAxis).item(0); _ly.isConstruction = True
    _rgc.addParallel(_e0, _lx); _rgc.addParallel(_e2, _lx)   # world-X-spanning edges
    _rgc.addParallel(_e1, _ly); _rgc.addParallel(_e3, _ly)   # world-Y-spanning edges
    _md = rsk2.sketchDimensions
    _md.addOffsetDimension(_e0, _e2, P(_pts[0].x, _pts[0].y, 0)).parameter.expression = "slot_gap"
    _md.addOffsetDimension(_e1, _e3, P(_pts[1].x, _pts[1].y, 0)).parameter.expression = "slot_w"
    _mp = rsk2.sketchPoints.add(P((_pts[0].x+_pts[2].x)/2, (_pts[0].y+_pts[2].y)/2, 0))
    _diag = rsk2.sketchCurves.sketchLines.addByTwoPoints(_e0.startSketchPoint, _e2.startSketchPoint)
    _diag.isConstruction = True
    _rgc.addMidPoint(_mp, _diag)
    _rgc.addCoincident(_mp, rsk2.originPoint)
    _ssw = legc.features.sweepFeatures.createInput(rsk2.profiles.item(0), spath, NEW)
    sbx = legc.features.sweepFeatures.add(_ssw).bodies.item(0); sbx.name = "Leg_FL_Slot"
    sp.combine(leg, [sbx], CUT, False, "Leg_FL_SlotCut")

    def move_rot(comp, body, axis, ang, px, py, pz, nm):
        c, s = math.cos(ang), math.sin(ang)
        m = adsk.core.Matrix3D.create()
        if axis == "x":
            m.setWithArray([1,0,0,0, 0,c,s,py-(py*c+pz*s), 0,-s,c,pz-(-py*s+pz*c), 0,0,0,1])
        else:
            m.setWithArray([c,0,-s,px-(px*c-pz*s), 0,1,0,0, s,0,c,pz-(px*s+pz*c), 0,0,0,1])
        coll = adsk.core.ObjectCollection.create(); coll.add(body)
        mi = comp.features.moveFeatures.createInput2(coll); mi.defineAsFreeMove(m)
        comp.features.moveFeatures.add(mi).name = nm

    # (leg is already splayed by the swept centerline — no rotate needed)
    sp.mirror_body(legc, leg, legc.yZConstructionPlane, "Leg_FR_Mir")
    fr = [legc.bRepBodies.item(i) for i in range(legc.bRepBodies.count)]
    sp.mirror_bodies(legc, fr, legc.xZConstructionPlane, "Leg_Back_Mir")
    for i in range(legc.bRepBodies.count):
        b = legc.bRepBodies.item(i); bb = b.boundingBox
        cx = (bb.minPoint.x+bb.maxPoint.x)/2; cy = (bb.minPoint.y+bb.maxPoint.y)/2
        b.name = "Leg_" + ("F" if cy < 0 else "B") + ("L" if cx < 0 else "R")

    # ============================================================
    # TOP  (component): flush frame-and-panel + dovetail battens
    # ============================================================
    occ_top = sp.make_comp(root, "Top")
    topc = occ_top.component

    def member(corners_in, name):
        pl = sp.off_plane(topc, topc.xYConstructionPlane, "tf_bot", name + "_Pl")
        sk = topc.sketches.add(pl); sk.name = name + "_Sk"
        lns = sk.sketchCurves.sketchLines
        pts = [P(x*IN, y*IN, 0) for (x, y) in corners_in]
        first = lns.addByTwoPoints(pts[0], pts[1]); prev = first
        for k in range(2, len(pts)):
            prev = lns.addByTwoPoints(prev.endSketchPoint, pts[k])
        lns.addByTwoPoints(prev.endSketchPoint, first.startSketchPoint)
        b = sp.ext_new(topc, sk.profiles.item(0), "tf_t", name).bodies.item(0)
        b.name = name
        return b

    frt = member([(-14,-6.875),(14,-6.875),(12,-4.875),(-12,-4.875)], "TF_Front")
    sp.mirror_body(topc, frt, topc.xZConstructionPlane, "TF_Back_Mir")
    lft = member([(-14,-6.875),(-14,6.875),(-12,4.875),(-12,-4.875)], "TF_Left")
    sp.mirror_body(topc, lft, topc.yZConstructionPlane, "TF_Right_Mir")
    for i in range(topc.bRepBodies.count):
        b = topc.bRepBodies.item(i)
        if b.name in ("TF_Front (1)", "TF_Left (1)"):
            bb = b.boundingBox
            cx = (bb.minPoint.x+bb.maxPoint.x)/2; cy = (bb.minPoint.y+bb.maxPoint.y)/2
            b.name = ("TF_Right" if cx > 0 else "TF_Left") if abs(cx) > abs(cy) else ("TF_Back" if cy > 0 else "TF_Front")

    # Flush panel with one-shoulder tongues (top flush, tongue below).
    # Field stops at frame inner edge; tongues extend tongue_ov into the frame.
    iw_h = "table_l / 2 - tf_w"; ih_h = "table_d / 2 - tf_w"
    panel = pbox(topc, "TopPanel",
                 "-(%s)" % iw_h, iw_h,
                 "-(%s)" % ih_h, ih_h,
                 "panel_under", "panel_t")
    # Tongue slab: wider/longer than field by tongue_ov on each side, but only
    # tongue_w thick at the panel underside. Overlaps the field's bottom, extends
    # past it on all 4 edges = the tongue. One body, one JOIN.
    tg_slab = pbox(topc, "P_Tongue",
                   "-(%s + tongue_ov)" % iw_h, "%s + tongue_ov" % iw_h,
                   "-(%s + tongue_ov)" % ih_h, "%s + tongue_ov" % ih_h,
                   "panel_under", "tongue_w")
    sp.combine(panel, [tg_slab], JOIN, False, "P_TgJ")
    for nm in ("TF_Front", "TF_Back", "TF_Left", "TF_Right"):
        sp.combine(ctx.find_body(nm), [panel], CUT, True, nm + "_Groove")

    # Dovetail battens (run in Y): dovetail ridge into panel underside; body
    # STOPS at the frame inner face (Y +/-4.875) and only a tenon enters the frame.
    def batten(name, cxb):
        zb = ev("panel_under") - ev("bt_h")
        pu = ev("panel_under")
        sd = ev("bt_dt_d")
        bw = ev("bt_w"); base = ev("bt_dt_base"); topw = ev("bt_dt_top")
        c = cxb * IN
        ys = 4.875                      # frame inner face (in)
        pl = sp.off_plane(topc, topc.xZConstructionPlane, "%g in" % -ys, name + "_Pl")
        sk = topc.sketches.add(pl); sk.name = name + "_Sk"
        m2s = sk.modelToSketchSpace
        pts = [(c-bw/2, zb), (c-bw/2, pu), (c-base/2, pu), (c-topw/2, pu+sd),
               (c+topw/2, pu+sd), (c+base/2, pu), (c+bw/2, pu), (c+bw/2, zb)]
        sps = [m2s(P(px, -ys * IN, pz)) for (px, pz) in pts]
        lns = sk.sketchCurves.sketchLines
        first = lns.addByTwoPoints(P(sps[0].x, sps[0].y, 0), P(sps[1].x, sps[1].y, 0))
        prev = first
        for k in range(2, len(sps)):
            prev = lns.addByTwoPoints(prev.endSketchPoint, P(sps[k].x, sps[k].y, 0))
        lns.addByTwoPoints(prev.endSketchPoint, first.startSketchPoint)
        b = sp.ext_new(topc, sk.profiles.item(0), "%g in" % (2 * ys), name).bodies.item(0)
        b.name = name
        # small tenon into the frame at each end (joined to batten)
        for sgn, lbl in ((-1, "F"), (1, "B")):
            yi, yo = sgn * ys * IN, sgn * (ys + 0.6) * IN
            # full-width tenon (no side shoulders); top reaches the dovetail
            # bottom (panel underside); only an under-shoulder
            tn = boxcm(topc, name + "_Tn" + lbl, c - bw/2, c + bw/2,
                       min(yi, yo), max(yi, yo), "panel_under - bt_h * 2/3", "bt_h * 2/3")
            sp.combine(b, [tn], JOIN, False, name + "_Tn" + lbl + "_J")
        return b

    bt_r = batten("Batten_R", 7)
    sp.mirror_body(topc, bt_r, topc.yZConstructionPlane, "Batten_L_Mir")
    for i in range(topc.bRepBodies.count):
        if topc.bRepBodies.item(i).name == "Batten_R (1)":
            topc.bRepBodies.item(i).name = "Batten_L"
    # battens: sliding-dovetail socket in panel + tenon socket in frame
    for bn in ("Batten_R", "Batten_L"):
        sp.combine(ctx.find_body("TopPanel"), [ctx.find_body(bn)], CUT, True, bn + "_PanelDT")
    for fn in ("TF_Front", "TF_Back"):
        sp.combine(ctx.find_body(fn),
                   [ctx.find_body("Batten_R"), ctx.find_body("Batten_L")], CUT, True, fn + "_BtMort")

    # ============================================================
    # Cross-component: legs let into top frame (rounded mortises)
    # ============================================================
    def proxy(name, occ):
        return ctx.find_body(name).createForAssemblyContext(occ)
    sp.combine(proxy("TF_Front", occ_top),
               [proxy("Leg_FL", occ_legs), proxy("Leg_FR", occ_legs)], CUT, True, "TFfront_LegCut")
    sp.combine(proxy("TF_Back", occ_top),
               [proxy("Leg_BL", occ_legs), proxy("Leg_BR", occ_legs)], CUT, True, "TFback_LegCut")
    # clear the top panel around the legs (no-op at default, but keeps the panel from
    # clipping the legs when leg_setback moves them in toward the panel)
    sp.combine(proxy("TopPanel", occ_top),
               [proxy("Leg_FL", occ_legs), proxy("Leg_FR", occ_legs),
                proxy("Leg_BL", occ_legs), proxy("Leg_BR", occ_legs)], CUT, True, "TopPanel_LegClear")

    # ============================================================
    # APRONS  (component): mitered ring (full-blind mitered DT corners,
    # dovetails concealed), same height; long aprons embed into legs.
    # ============================================================
    occ_ap = sp.make_comp(root, "Aprons")
    apc = occ_ap.component
    add("cove_r", "0.75 in", "in", "Apron/spandrel cove radius")
    add("bot_r", "0.75 in", "in", "Spandrel lower-corner transition radius")
    add("ap_end_inset", "0.875 in", "in", "Apron end inset from each frame end")
    add("la_half", "table_l / 2 - ap_end_inset", "in", "Apron half length (derived)")
    add("sp_edge_gap", "1 in", "in", "Spandrel edge to leg surface")
    add("sp_width2", "leg_dia + 2 * sp_edge_gap", "in", "Spandrel full width (derived)")

    def apmember(corners_in, name, w_expr="apron_w"):
        # Top sits at tf_bot; bottom at tf_bot - w_expr (so a narrower w_expr raises
        # the bottom edge). The short apron uses sa_w (< apron_w) so its horizontal
        # bottom meets the long apron's leaning bottom edge level — see sa_w below.
        pl = sp.off_plane(apc, apc.xYConstructionPlane, "tf_bot - " + w_expr, name + "_Pl")
        sk = apc.sketches.add(pl); sk.name = name + "_Sk"
        lns = sk.sketchCurves.sketchLines
        pts = [P(x*IN, y*IN, 0) for (x, y) in corners_in]
        first = lns.addByTwoPoints(pts[0], pts[1]); prev = first
        for k in range(2, len(pts)):
            prev = lns.addByTwoPoints(prev.endSketchPoint, pts[k])
        lns.addByTwoPoints(prev.endSketchPoint, first.startSketchPoint)
        b = sp.ext_new(apc, sk.profiles.item(0), w_expr, name).bodies.item(0)
        b.name = name
        return b

    # Combined long side = apron band + 2 spandrels in ONE elevation sketch.
    # ANCHORED to projected geometry (no origin dims): the apron top is collinear
    # with the top-frame's projected underside edge; the apron ends offset from the
    # frame's projected end edges; the spandrel sides are PARALLEL to each leg's
    # projected silhouette (carrying the leg's rake lean) and offset sp_edge_gap
    # from the leg surface. Quarter-circle coves (cove_r) + rounded spandrel bottom
    # corners (bot_r). Fully constrained against the leg + frame projections.
    def long_side(name):
        # leg-parallel TILTED plane: rotate the vertical Y=-lty plane by -splay about
        # the leg-top X-axis (FL-top -> FR-top), so the plane contains both front-leg
        # centerlines. The apron then lies in the legs' plane with NO body rotate.
        vpl = sp.off_plane(apc, apc.xZConstructionPlane, "-lty", name + "_VPl")
        axsk = apc.sketches.add(vpl); axsk.name = name + "_Axis_Sk"
        _ma = axsk.modelToSketchSpace
        _pa = _ma(P(-ev("ltx"), ev("-lty"), ev("leg_tip_z")))
        _pb = _ma(P(ev("ltx"), ev("-lty"), ev("leg_tip_z")))
        axln = axsk.sketchCurves.sketchLines.addByTwoPoints(P(_pa.x, _pa.y, 0), P(_pb.x, _pb.y, 0))
        axln.isConstruction = True                 # pure rotation-axis helper (gate skips it)
        axsk.geometricConstraints.addHorizontal(axln)
        _tin = apc.constructionPlanes.createInput()
        _tin.setByAngle(axln, VI("-splay"), vpl)
        plc = apc.constructionPlanes.add(_tin); plc.name = name + "_Pl"
        skc = apc.sketches.add(plc); skc.name = name + "_Sk"
        # project the top frame + the two front legs as reference geometry
        legFL = ctx.find_body("Leg_FL").createForAssemblyContext(occ_legs)
        legFR = ctx.find_body("Leg_FR").createForAssemblyContext(occ_legs)
        tf = ctx.find_body("TF_Front").createForAssemblyContext(occ_top)
        pj_tf = skc.project(tf); pj_l = skc.project(legFL); pj_r = skc.project(legFR)

        def hv(l):
            a = l.startSketchPoint.geometry; b = l.endSketchPoint.geometry
            return a, b, abs(a.x - b.x), abs(a.y - b.y)
        fr = [pj_tf.item(k) for k in range(pj_tf.count)
              if isinstance(pj_tf.item(k), adsk.fusion.SketchLine)]
        horiz = [l for l in fr if hv(l)[2] > hv(l)[3]]
        vert = [l for l in fr if hv(l)[3] >= hv(l)[2]]
        underside = max(horiz, key=lambda l: (hv(l)[0].y + hv(l)[1].y) / 2)
        left_end = min(vert, key=lambda l: (hv(l)[0].x + hv(l)[1].x) / 2)
        right_end = max(vert, key=lambda l: (hv(l)[0].x + hv(l)[1].x) / 2)
        # The frame underside edge, projected onto the TILTED apron plane, lands at
        # world-Z `_U` slightly BELOW the true frame underside (tf_bot) — projecting a
        # horizontal edge that is offboard of the plane drops it down the lean. So
        # "apron_w below the projected underside" would undershoot. Measure the drop
        # and correct the band-bottom offset so the band bottom edge sits at the true
        # tf_bot - apron_w (level with the vertical short apron). The drop depends only
        # on Y geometry + splay (not table_h), so it recomputes safely on clean builds.
        _u0 = underside.startSketchPoint.worldGeometry
        _u1 = underside.endSketchPoint.worldGeometry
        _band_corr = ev("tf_bot") - (_u0.z + _u1.z) / 2.0   # cm; projection drop
        # Minimum top overlap so the leaning band still pokes above the frame underside
        # across its full thickness for a clean flat trim — just the projection drop +
        # the tilt drop across the apron thickness + a little slack. (Was apron_t, which
        # built the band ~10x taller than needed and wasted it all on the trim.)
        _lap = _band_corr + ev("apron_t") * math.tan(ev("splay")) + 0.05   # cm

        def outer_leg(pj, sign):
            # The leaning cylinder's outer-tangent silhouette is one straight line;
            # the slot/cuts split it into colinear segments. Any steep segment on the
            # outboard surface works for the parallel + offset (same infinite line).
            ls = [pj.item(k) for k in range(pj.count)
                  if isinstance(pj.item(k), adsk.fusion.SketchLine)]
            cand = [l for l in ls if hv(l)[3] > 4 and hv(l)[2] < hv(l)[3]]
            return (min if sign < 0 else max)(cand, key=lambda l: (hv(l)[0].x + hv(l)[1].x) / 2)
        legL = outer_leg(pj_l, -1); legR = outer_leg(pj_r, 1)

        m2 = skc.modelToSketchSpace; ycc = ev("-lty")
        # initial placement only (inches) — derived from params so it tracks edits;
        # the Fusion dimensions below take over the final geometry.
        AT = ev("tf_bot") / IN; AB = AT - ev("apron_w") / IN
        # Top edge starts just _lap above the frame underside (minimal overlap) so the
        # leaning apron pokes up enough for LAf_TFtrim to shear it flat at the frame
        # underside -> a horizontal top face in full contact, with little waste.
        ATT = AT + _lap / IN
        SB = AB - ev("spandrel_depth") / IN
        ltx0 = ev("ltx") / IN; lr0 = ev("leg_r") / IN; gap0 = ev("sp_edge_gap") / IN
        LH = ev("la_half") / IN
        spo, spi = ltx0 + lr0 + gap0, ltx0 - lr0 - gap0
        pts = [(-LH,ATT),(LH,ATT),(LH,AB),(spo,AB),(spo,SB),(spi,SB),(spi,AB),
               (-spi,AB),(-spi,SB),(-spo,SB),(-spo,AB),(-LH,AB)]
        sps = [m2(P(x*IN, ycc, z*IN)) for (x, z) in pts]
        Lc = skc.sketchCurves.sketchLines
        f0 = Lc.addByTwoPoints(P(sps[0].x, sps[0].y, 0), P(sps[1].x, sps[1].y, 0))
        lns = [f0]; pv = f0
        for i in range(2, len(sps)):
            ln = Lc.addByTwoPoints(pv.endSketchPoint, P(sps[i].x, sps[i].y, 0))
            lns.append(ln); pv = ln
        lns.append(Lc.addByTwoPoints(pv.endSketchPoint, f0.startSketchPoint))
        g = skc.geometricConstraints
        for hi in (0, 2, 4, 6, 8, 10): g.addHorizontal(lns[hi])
        for vi in (1, 11): g.addVertical(lns[vi])           # apron ends only
        g.addCollinear(lns[2], lns[6]); g.addCollinear(lns[6], lns[10])
        g.addCollinear(lns[4], lns[8])
        # apron top is parallel to (offset above) the frame underside, not collinear,
        # so the band pokes up into the frame for the flat trim (see ATT above).
        # spandrel sides parallel to the projected leg silhouettes (rake lean)
        g.addParallel(lns[3], legR); g.addParallel(lns[5], legR)
        g.addParallel(lns[9], legL); g.addParallel(lns[7], legL)
        d = skc.sketchDimensions; z0 = P(0, 0, 0)
        def offd(a, b, expr):
            d.addOffsetDimension(a, b, z0).parameter.expression = expr
        offd(underside, lns[2], "apron_w - (%.6f cm)" % _band_corr)  # band BOTTOM at true tf_bot-apron_w
        offd(underside, lns[0], "%.5f cm" % _lap)  # band TOP just _lap above underside (min trim overlap)
        offd(lns[2], lns[4], "spandrel_depth")   # spandrel depth below apron
        offd(left_end, lns[11], "ap_end_inset")  # apron ends from frame ends
        offd(right_end, lns[1], "ap_end_inset")
        offd(legR, lns[3], "sp_edge_gap")        # R spandrel outer edge from leg
        offd(lns[3], lns[5], "sp_width2")        # R spandrel full width
        offd(legL, lns[9], "sp_edge_gap")        # L spandrel outer edge from leg
        offd(lns[9], lns[7], "sp_width2")        # L spandrel full width
        ac = skc.sketchCurves.sketchArcs
        def fil(k, rexpr):
            v = lns[k].startSketchPoint.geometry; cp = P(v.x, v.y, 0)
            arc = ac.addFillet(lns[k-1], cp, lns[k], cp, ev(rexpr))
            d.addRadialDimension(arc, cp).parameter.expression = rexpr
            return arc
        # Upper coves at spandrel tops (band/spandrel transition) — applied first so the
        # gable diagonals can connect from the post-fillet tangent points on the AB line.
        cove_arcs = {}
        for k in (3, 6, 7, 10): cove_arcs[k] = fil(k, "cove_r")
        # Gable miter lines: from each upper cove's AB-line tangent point to the
        # leg/apron-top peak. The peak is at tf_bot (below ATT), so the band closes
        # over each peak through the _lap sliver and stays one connected rail.
        lcx_top = ev("ltx") + ev("leg_embed") * math.tan(ev("splay"))
        ATm = ev("tf_bot")
        def add_gable(p_outer, p_inner, sgn):
            lox = sgn * (lcx_top + ev("leg_r")); lix = sgn * (lcx_top - ev("leg_r"))
            qo = m2(P(lox, ycc, ATm)); qi = m2(P(lix, ycc, ATm))
            do = Lc.addByTwoPoints(p_outer, P(qo.x, qo.y, 0))
            tp = Lc.addByTwoPoints(do.endSketchPoint, P(qi.x, qi.y, 0))
            Lc.addByTwoPoints(tp.endSketchPoint, p_inner)
        # R gable: outer cove center → peak → inner cove center
        add_gable(cove_arcs[3].centerSketchPoint, cove_arcs[6].centerSketchPoint, 1)
        # L gable: outer cove center → peak → inner cove center
        add_gable(cove_arcs[10].centerSketchPoint, cove_arcs[7].centerSketchPoint, -1)
        for k in (4, 5, 8, 9): fil(k, "bot_r")
        sp.refs_to_construction(skc)
        # Profiles: 1 band (largest area) + 2 spandrels. Extrude each separately.
        prs = [(pr, pr.areaProperties()) for pr in
               (skc.profiles.item(i) for i in range(skc.profiles.count))]
        prs.sort(key=lambda t: t[1].area, reverse=True)
        print("%s profiles=%d areas=%s" % (name, len(prs), [round(t[1].area, 1) for t in prs]))
        spref = name.replace("LongApron_", "Spandrel_")
        band = sp.ext_new_sym(apc, prs[0][0], "apron_t / 2", name).bodies.item(0)
        band.name = name
        spp = sorted(prs[1:3], key=lambda t: t[1].centroid.x)            # L (low x), R (high x)
        for (pr, _ap), lr in zip(spp, ("L", "R")):
            sb = sp.ext_new_sym(apc, pr, "apron_t / 2", spref + lr).bodies.item(0)
            sb.name = spref + lr
        # ---- Connecting pieces: 1/8" tongue at apron center, bridging band↔spandrel ----
        # Sketch on plc, project spandrel_R cross-section, cut 1 7/16" from top,
        # extrude the upper portion 1/8" symmetric (centered in apron thickness).
        spR_body = ctx.find_body(spref + "R")
        csk = apc.sketches.add(plc); csk.name = name + "_ConnR_Sk"
        csk.intersectWithSketchPlane([spR_body])
        min_y = 1e9; min_x = 1e9; max_x = -1e9
        for i in range(csk.sketchCurves.count):
            bb = csk.sketchCurves.item(i).boundingBox
            if bb.minPoint.y < min_y: min_y = bb.minPoint.y
            if bb.minPoint.x < min_x: min_x = bb.minPoint.x
            if bb.maxPoint.x > max_x: max_x = bb.maxPoint.x
        cut_y = min_y + 1.4375 * IN
        csk.sketchCurves.sketchLines.addByTwoPoints(
            P(min_x - 1, cut_y, 0), P(max_x + 1, cut_y, 0))
        n_pr = csk.profiles.count
        print("%s conn: curves=%d top(min_y)=%.2f cut_y=%.2f profiles=%d" %
              (name, csk.sketchCurves.count, min_y, cut_y, n_pr))
        conn_pr = None
        for pi in range(n_pr):
            pr = csk.profiles.item(pi)
            pr_min_y = 1e9
            for j in range(pr.profileLoops.count):
                loop = pr.profileLoops.item(j)
                for k in range(loop.profileCurves.count):
                    se = loop.profileCurves.item(k).sketchEntity
                    for attr in ('startSketchPoint', 'endSketchPoint'):
                        if hasattr(se, attr):
                            y = getattr(se, attr).geometry.y
                            if y < pr_min_y: pr_min_y = y
            print("  profile %d: area=%.2f min_y=%.2f" % (pi, pr.areaProperties().area, pr_min_y))
            if abs(pr_min_y - min_y) < 0.1:
                conn_pr = pr
                print("  -> SELECTED (contains gable peak at min_y=%.2f)" % min_y)
        conn_R = sp.ext_new_sym(apc, conn_pr, "0.15875 cm", name + "_ConnR").bodies.item(0)
        conn_R.name = name + "_ConnR"
        sp.mirror_bodies(apc, [conn_R], apc.yZConstructionPlane, name + "_ConnMir")
        conn_L = None
        for i in range(apc.bRepBodies.count):
            b = apc.bRepBodies.item(i)
            if b.name.endswith(" (1)") and "Conn" in b.name:
                b.name = name + "_ConnL"; conn_L = b; break
        sp.combine(band, [conn_R, conn_L], JOIN, False, name + "_Assemble")
        spL_body = ctx.find_body(spref + "L"); spR_body = ctx.find_body(spref + "R")
        sp.combine(spL_body, [band], CUT, True, spref + "L_TongueCut")
        sp.combine(spR_body, [band], CUT, True, spref + "R_TongueCut")
        return band

    apf = long_side("LongApron_F")

    # Short-apron height (needed below for the dovetail band-center too): the long apron
    # leans, so its bottom face slopes and its OUTER (front-visible) bottom edge sits
    # slightly higher than tf_bot - apron_w. A full-apron_w-tall vertical short apron
    # would dip below that edge at the corner. Read the long apron's outer bottom edge
    # from the body (rule 10) and make the short apron exactly that much NARROWER so the
    # two bottom edges meet level.
    def _band_bottom_outer_z(b):
        best = None
        for i in range(b.faces.count):
            f = b.faces.item(i); gg = f.geometry
            if isinstance(gg, adsk.core.Plane) and gg.normal.z < -0.9 and 73 < f.pointOnFace.z < 74.6:
                if best is None or f.area > best.area: best = f
        gg = best.geometry; nn = gg.normal; oo = gg.origin
        ymin = b.boundingBox.minPoint.y          # outer (front) side of the leaning band
        return oo.z - (nn.y * (ymin - oo.y)) / nn.z   # band bottom edge is const in X
    _outer_z = _band_bottom_outer_z(apf)
    _sa_narrow = max(0.0, _outer_z - (ev("tf_bot") - ev("apron_w")))   # cm
    add("sa_w", "apron_w - (%.6f cm)" % _sa_narrow, "in",
        "Short-apron height: apron_w narrowed for the long apron's lean so bottom edges meet level (derived)")

    # ---- Corner: miter the long-apron ENDS, then LOFT each short apron between the two
    #      long-apron miter faces. The short apron's end faces ARE the long-apron miter
    #      faces -> a guaranteed-flush mitered corner, no separate short-apron box/cut. ----
    def cut_tri(target_name, tri, name):
        # Vertical triangular prism (tri in plan) over the band height, CUT from target.
        zlo = ev("tf_bot") - ev("apron_w") - 0.5; zhi = ev("tf_bot") + 0.5
        pl = sp.off_plane(apc, apc.xYConstructionPlane, "%.5f cm" % zlo, name + "_Pl")
        sk = apc.sketches.add(pl); sk.name = name + "_Sk"
        m = sk.modelToSketchSpace
        ps = [m(P(x, y, zlo)) for (x, y) in tri]
        L = sk.sketchCurves.sketchLines
        l0 = L.addByTwoPoints(P(ps[0].x, ps[0].y, 0), P(ps[1].x, ps[1].y, 0))
        l1 = L.addByTwoPoints(l0.endSketchPoint, P(ps[2].x, ps[2].y, 0))
        L.addByTwoPoints(l1.endSketchPoint, l0.startSketchPoint)
        tool = sp.ext_new(apc, sk.profiles.item(0), "%.5f cm" % (zhi - zlo), name).bodies.item(0)
        tool.name = name
        sp.combine(ctx.find_body(target_name), [tool], CUT, False, name + "_Cut")

    def miter_end(long_name, sx, fbq):
        # Cut the long apron's end corner-tip on the diagonal -> a miter end face; return it.
        la = ctx.find_body(long_name); lb = la.boundingBox
        yo = lb.minPoint.y if fbq == 'F' else lb.maxPoint.y   # outer (front/back) face
        yi = lb.maxPoint.y if fbq == 'F' else lb.minPoint.y   # inner face
        xo = sx * ev("la_half"); xi = sx * (ev("la_half") - ev("apron_t"))
        cut_tri(long_name, [(xo, yo), (xo, yi), (xi, yi)], "Mit_" + fbq + ("R" if sx > 0 else "L"))
        la = ctx.find_body(long_name); cx = (xo + xi) / 2; cy = (yo + yi) / 2; best = None
        for i in range(la.faces.count):
            f = la.faces.item(i); g = f.geometry
            if isinstance(g, adsk.core.Plane):
                n = g.normal; c = f.pointOnFace
                if abs(n.x) > 0.3 and abs(n.y) > 0.3 and abs(c.x - cx) < 2.5 and abs(c.y - cy) < 3.5:
                    if best is None or f.area > best.area: best = f
        return best

    # mirror band+connectors + spandrels to back BEFORE mitering (never mirror a cut-history body).
    sp.mirror_bodies(apc, [apf, ctx.find_body("Spandrel_FL"), ctx.find_body("Spandrel_FR")],
                     apc.xZConstructionPlane, "LA_Back_Mir")
    for i in range(apc.bRepBodies.count):
        b = apc.bRepBodies.item(i)
        if b.name.endswith(" (1)"):
            b.name = b.name[:-4].replace("_F", "_B", 1)   # LongApron_F->_B, Spandrel_FL->_BL
    _fFL = miter_end("LongApron_F", -1, 'F'); _fFR = miter_end("LongApron_F", 1, 'F')
    _fBL = miter_end("LongApron_B", -1, 'B'); _fBR = miter_end("LongApron_B", 1, 'B')

    def loft_short(name, fa, fb):
        li = apc.features.loftFeatures.createInput(NEW)
        li.loftSections.add(fa); li.loftSections.add(fb)
        bd = apc.features.loftFeatures.add(li).bodies.item(0); bd.name = name
    loft_short("ShortApron_L", _fFL, _fBL)   # ONE loft only — the right short apron is a
    # mirror of the finished left one (FBD step 6 below), so there is no second loft.

    # ---- Hidden (full-blind) dovetail at all four apron corners ----
    # Tails on the SHORT aprons, sockets in the LONG aprons. Mirror-based build:
    #   1. Build the FL lip block, MIRROR it to all 4 corners, JOIN to the long aprons
    #   2. ONE loft for the LEFT short apron (right is mirrored later)
    #   3. CUT the lip recess into BOTH ends of the left short apron
    #   4. Build the FL dovetail tails, MIRROR them to the BL end
    #   5. JOIN both tail sets to the left short apron, split + trim excess (by COM)
    #   6. MIRROR the finished left short apron -> right short apron
    #   7. CUT the long aprons with the short aprons -> sockets (all 4 corners)
    _sock = ev("fbd_socket"); _tw = ev("fbd_tail_w"); _nw = ev("fbd_narrow_w")
    _lip = ev("fbd_lip"); _pad = ev("fbd_pad"); _pitch = ev("fbd_pitch")
    _lah = ev("la_half"); _apt = ev("apron_t"); _apw = ev("apron_w"); _tfb = ev("tf_bot")

    def build_lip(long_name, sgn, fb, label):
        # LIP BLOCK sketched on the LONG APRON's INNER face (the flat back face toward
        # table center) at the mitered end. Parametric rectangle:
        #   width  = fbd_socket          (along apron length X, from the miter inner corner)
        #   height = apron_w - 2*fbd_pad (along Z), top fbd_pad below tf_bot
        # extruded -apron_t through the board thickness. Returns the lip body (NOT joined).
        la = ctx.find_body(long_name)
        ny = 1.0 if fb == 'F' else -1.0          # front apron inner face faces +Y
        inner_la = None
        for i in range(la.faces.count):
            f = la.faces.item(i); g = f.geometry
            if isinstance(g, adsk.core.Plane) and g.normal.y * ny > 0.85:
                if inner_la is None or f.area > inner_la.area:
                    inner_la = f
        if not inner_la:
            raise RuntimeError("FBD %s: long-apron inner face not found" % label)
        lsk = apc.sketches.add(inner_la); lsk.name = label + "_Lip_Sk"
        m = lsk.modelToSketchSpace
        yf = inner_la.pointOnFace.y
        xo = sgn * (_lah - _apt)                 # outer edge: at the miter inner corner
        xi = sgn * (_lah - _apt + _sock)         # toward the apron end
        ztop = _tfb - _pad
        zbot = _tfb - _apw + _pad
        c00 = m(P(xo, yf, ztop)); c10 = m(P(xi, yf, ztop))
        c11 = m(P(xi, yf, zbot)); c01 = m(P(xo, yf, zbot))
        RL = lsk.sketchCurves.sketchLines
        e0 = RL.addByTwoPoints(P(c00.x, c00.y, 0), P(c10.x, c10.y, 0))
        e1 = RL.addByTwoPoints(e0.endSketchPoint, P(c11.x, c11.y, 0))
        e2 = RL.addByTwoPoints(e1.endSketchPoint, P(c01.x, c01.y, 0))
        e3 = RL.addByTwoPoints(e2.endSketchPoint, e0.startSketchPoint)
        lg = lsk.geometricConstraints
        lg.addHorizontal(e0); lg.addHorizontal(e2)
        lg.addVertical(e1); lg.addVertical(e3)
        ld = lsk.sketchDimensions
        HOR = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
        VER = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
        ld.addDistanceDimension(e0.startSketchPoint, e0.endSketchPoint, HOR,
            P(c00.x, c00.y - 0.5, 0)).parameter.expression = "fbd_socket"
        ld.addDistanceDimension(e1.startSketchPoint, e1.endSketchPoint, VER,
            P(c10.x + 0.5, c10.y, 0)).parameter.expression = "apron_w - 2 * fbd_pad"
        # Sketching on a face auto-projects its outline -> a second (huge) profile.
        # Demote projected geometry to construction, then pick the rectangle by its
        # expected area (NOT max area, which grabs the whole-apron region).
        sp.refs_to_construction(lsk)
        _lip_area = _sock * (_apw - 2 * _pad)
        lp = min((lsk.profiles.item(i) for i in range(lsk.profiles.count)),
                 key=lambda p: abs(p.areaProperties().area - _lip_area))
        lip = sp.ext_new(apc, lp, "-apron_t", label + "_Lip").bodies.item(0)
        lip.name = label + "_Lip"
        return lip

    def build_tails(short_name, sgn, fb, label):
        # Build the dovetail tail bodies on the recessed inner-slab face of the short
        # apron at one corner. The recess must already be cut. Returns the list of tail
        # bodies (NOT joined — the caller joins / mirrors / trims).
        sa = ctx.find_body(short_name)
        xi = sgn * (_lah - _apt + _sock)
        # Find the exposed inner-slab face on the short apron: it sits at the lip
        # rectangle's inner edge X (= xi), normal along +/-X, on the corner side in Y.
        cy_sgn = -1.0 if fb == 'F' else 1.0
        inner_face = None
        for i in range(sa.faces.count):
            f = sa.faces.item(i); g = f.geometry
            if isinstance(g, adsk.core.Plane) and abs(g.normal.x) > 0.85:
                c = f.centroid
                if abs(c.x - xi) < 0.4 and c.y * cy_sgn > 5.0 and f.area > 0.3:
                    if inner_face is None or f.area > inner_face.area:
                        inner_face = f
        if not inner_face:
            raise RuntimeError("FBD %s: exposed inner slab face not found" % label)
        # Step 3: tail trapezoid on the recessed inner-slab face. The dovetail flares in
        # Z (apron height): the WIDE line (fbd_tail_w) sits ON the OUTER edge of the
        # surface, the NARROW line (fbd_narrow_w) ON the INNER edge; the two flare lines
        # connect them. Both parallel lines are constrained COLLINEAR to the projected
        # face edges so they stay anchored to the surface. Patterned along the outer edge.
        tsk = apc.sketches.add(inner_face); tsk.name = label + "_Tail_Sk"
        mt = tsk.modelToSketchSpace
        xf = inner_face.pointOnFace.x
        # Identify the two vertical (Z) edges of the face: outer (toward visible face) + inner
        outer_edge = None; inner_edge = None
        yv = []; zv = []
        for i in range(inner_face.edges.count):
            e = inner_face.edges.item(i)
            a = e.startVertex.geometry; b = e.endVertex.geometry
            yv += [a.y, b.y]; zv += [a.z, b.z]
        y_lo = min(yv); y_hi = max(yv); z_lo = min(zv); z_hi = max(zv)
        y_out = y_lo if fb == 'F' else y_hi
        y_in = y_hi if fb == 'F' else y_lo   # innermost (centerward) extent of the leaning inner edge
        for i in range(inner_face.edges.count):
            e = inner_face.edges.item(i)
            a = e.startVertex.geometry; b = e.endVertex.geometry
            if abs(a.z - b.z) > abs(a.y - b.y) + 0.05:
                ey = (a.y + b.y) / 2
                if abs(ey - y_out) < 0.15: outer_edge = e
                elif abs(ey - y_in) < 0.15: inner_edge = e
        if not outer_edge or not inner_edge:
            raise RuntimeError("FBD %s: tail face outer/inner edges not found" % label)
        # The recess UPPER edge = the horizontal (Y) edge at the top of the recess face.
        upper_edge = None
        for i in range(inner_face.edges.count):
            e = inner_face.edges.item(i)
            a = e.startVertex.geometry; b = e.endVertex.geometry
            if abs(a.y - b.y) > abs(a.z - b.z) + 0.05:
                if upper_edge is None or (a.z + b.z) / 2 > (upper_edge.startVertex.geometry.z + upper_edge.endVertex.geometry.z) / 2:
                    upper_edge = e
        # Project the outer/inner/upper edges as reference geometry.
        po = tsk.project(outer_edge); pii = tsk.project(inner_edge); pue = tsk.project(upper_edge)
        ol = po.item(0); il = pii.item(0); ue = pue.item(0)
        # Center the tail pattern in the recess field so the gap to the UPPER edge equals
        # the gap to the LOWER edge. The first (top) tail's centre sits (count-1)*pitch/2
        # above the field midpoint; patterning DOWN by pitch lands the last tail the same
        # distance above the lower edge.
        _cnt = ev("fbd_tail_count")
        z_mid = (z_hi + z_lo) / 2.0
        z_c = z_mid + (_cnt - 1) * _pitch / 2.0
        def mp(yy, zz):
            q = mt(P(xf, yy, zz)); return P(q.x, q.y, 0)
        TL = tsk.sketchCurves.sketchLines
        _flr = abs(y_out - y_in) * math.tan(ev("fbd_angle"))   # flare drop (placement only)
        a1 = mp(y_out, z_c + _tw / 2)                # START point: wide-top corner on outer edge
        a0 = mp(y_out, z_c - _tw / 2)                # wide-bottom corner
        a2 = mp(y_in,  z_c + _tw / 2 - _flr)         # narrow-top on inner edge
        a3 = mp(y_in,  z_c - _tw / 2 + _flr)         # narrow-bottom on inner edge
        tl0 = TL.addByTwoPoints(a0, a1)                  # outer (wide)
        tl1 = TL.addByTwoPoints(tl0.endSketchPoint, a2)  # flank (dovetail angle)
        tl2 = TL.addByTwoPoints(tl1.endSketchPoint, a3)  # inner (narrow)
        tl3 = TL.addByTwoPoints(tl2.endSketchPoint, tl0.startSketchPoint)  # flank (dovetail angle)
        tg = tsk.geometricConstraints
        tg.addCollinear(tl0, ol)                     # wide line ON the outer edge
        tg.addParallel(tl2, tl0)                     # narrow line PARALLEL to wide
        tg.addCoincident(tl1.endSketchPoint, il)     # narrow-top ON inner edge (depth anchor / overlap)
        td = tsk.sketchDimensions
        ALN = adsk.fusion.DimensionOrientations.AlignedDimensionOrientation
        # Wide-side width
        td.addDistanceDimension(tl0.startSketchPoint, tl0.endSketchPoint, ALN,
            P(a0.x - 0.4, a0.y, 0)).parameter.expression = "fbd_tail_w"
        # SINGLE start-point position: DIRECTIONAL offset of the wide-top corner BELOW the
        # recess upper edge. Offset dims are signed; the value is NEGATIVE so the tail drops
        # DOWN into the recess (positive pushed it up past the edge into the lip/pad zone).
        td.addOffsetDimension(ue, tl0.endSketchPoint,
            P(a1.x - 0.8, a1.y, 0)).parameter.expression = "-(fbd_pitch - fbd_tail_w) / 2"
        # Fixed dovetail ANGLE on both flanks -> rigid trapezoid.
        td.addAngularDimension(tl0, tl1,
            P(a1.x + 0.3, a1.y - 0.3, 0)).parameter.expression = "90 deg + fbd_angle"
        td.addAngularDimension(tl3, tl0,
            P(a0.x + 0.3, a0.y + 0.3, 0)).parameter.expression = "90 deg + fbd_angle"
        # Step 4: extrude tail. Demote any auto-projected outline to construction, pick the
        # trapezoid profile by expected area (the projected edges are construction now).
        sp.refs_to_construction(tsk)
        _tail_area = (_tw + _nw) / 2 * abs(y_hi - y_lo)
        tprof = min((tsk.profiles.item(i) for i in range(tsk.profiles.count)),
                    key=lambda p: abs(p.areaProperties().area - _tail_area))
        tail_feat = sp.ext_new(apc, tprof, "fbd_socket", label + "_Tail")
        tail_body = tail_feat.bodies.item(0); tail_body.name = label + "_Tail"
        # Step 5: pattern tails ALONG the surface's outer edge (a BRepEdge), not a global
        # axis — so the tails march up the recess face regardless of apron lean.
        oc = adsk.core.ObjectCollection.create()
        oc.add(tail_feat)
        pi = apc.features.rectangularPatternFeatures.createInput(
            oc, outer_edge,
            VI("fbd_tail_count"), VI("-fbd_pitch"),   # negative -> pattern DOWN the edge
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        pf = apc.features.rectangularPatternFeatures.add(pi)
        pf.name = label + "_Pattern"
        # Collect all tail bodies (original + patterned)
        tail_bodies = [tail_body]
        for i in range(pf.bodies.count):
            b = pf.bodies.item(i)
            if b.name != tail_body.name:
                tail_bodies.append(b)
        # Return the tail bodies (the caller joins / mirrors / trims them).
        return tail_bodies

    # A MirrorFeature's `.bodies` returns BOTH the new copies AND the source bodies, so we
    # instead take the bodies Fusion APPENDS to the component (the true new mirror copies).
    def mirror_get_new(srcs, plane, fname):
        n0 = apc.bRepBodies.count
        sp.mirror_bodies(apc, srcs, plane, fname)
        return [apc.bRepBodies.item(i) for i in range(n0, apc.bRepBodies.count)]

    # === Step 1: lips on all four corners (build FL, mirror to FR / BL / BR, then join) ===
    fl_lip = build_lip("LongApron_F", -1, 'F', "FBD_FL")
    fr_lip = mirror_get_new([fl_lip], apc.yZConstructionPlane, "FBD_Lip_FR_Mir")[0]
    fr_lip.name = "FBD_FR_Lip"
    front_lips = [fl_lip, fr_lip]
    back_lips = mirror_get_new(front_lips, apc.xZConstructionPlane, "FBD_Lip_Back_Mir")
    sp.combine(ctx.find_body("LongApron_F"), front_lips, JOIN, False, "FBD_LipJoin_F")
    sp.combine(ctx.find_body("LongApron_B"), back_lips, JOIN, False, "FBD_LipJoin_B")

    # === Step 3: cut the lip recess into BOTH ends of the LEFT short apron ===
    # (keep_tool=True so the long aprons survive for the socket cut in step 7)
    sp.combine(ctx.find_body("ShortApron_L"), [ctx.find_body("LongApron_F")],
               CUT, True, "FBD_RecessCut_FL")
    sp.combine(ctx.find_body("ShortApron_L"), [ctx.find_body("LongApron_B")],
               CUT, True, "FBD_RecessCut_BL")

    # === Step 4: build the FL dovetail tails, MIRROR them to the BL end ===
    fl_tails = build_tails("ShortApron_L", -1, 'F', "FBD_FL")
    bl_tails = mirror_get_new(fl_tails, apc.xZConstructionPlane, "FBD_Tails_BL_Mir")

    # === Step 5: JOIN both tail sets to the left short apron, then split + trim excess ===
    sp.combine(ctx.find_body("ShortApron_L"), fl_tails + bl_tails, JOIN, False, "FBD_TailJoin_L")
    sa3 = ctx.find_body("ShortApron_L")
    # The inner surface = the big +X board face toward the table centre (the left apron sits
    # at -X, so its centre-facing face is the MAX-X planar face). Split by it (extended).
    in_surf = None; best = -1e9
    for i in range(sa3.faces.count):
        f = sa3.faces.item(i); g = f.geometry
        if isinstance(g, adsk.core.Plane) and abs(g.normal.x) > 0.85 and f.area > 10:
            if f.centroid.x > best:
                best = f.centroid.x; in_surf = f
    si = apc.features.splitBodyFeatures.createInput(sa3, in_surf, True)
    spf = apc.features.splitBodyFeatures.add(si); spf.name = "FBD_TrimSplit_L"
    frags = [spf.bodies.item(i) for i in range(spf.bodies.count)]
    # Select the body to KEEP by CENTER OF MASS: the real board's COM sits OUTER (most -X);
    # the trimmed-off overshoot fragments sit past the inner surface toward centre (+X).
    keep = min(frags, key=lambda b: b.physicalProperties.centerOfMass.x)
    keep.name = "ShortApron_L"
    # Remove the excess slivers via timeline RemoveFeature (deleteMe corrupts the recompute).
    for b in frags:
        if b is not keep:
            apc.features.removeFeatures.add(b)

    # === Step 6: MIRROR the finished left short apron -> right short apron ===
    msr = sp.mirror_body(apc, ctx.find_body("ShortApron_L"),
                         apc.yZConstructionPlane, "ShortApron_R_Mir")
    msr.bodies.item(0).name = "ShortApron_R"

    # === Step 7: CUT the long aprons with the short aprons -> sockets (all four corners) ===
    sp.combine(ctx.find_body("LongApron_F"),
               [ctx.find_body("ShortApron_L"), ctx.find_body("ShortApron_R")],
               CUT, True, "FBD_Socket_F")
    sp.combine(ctx.find_body("LongApron_B"),
               [ctx.find_body("ShortApron_L"), ctx.find_body("ShortApron_R")],
               CUT, True, "FBD_Socket_B")

    # ONLY the leg cuts the apron (not the reverse): the forked, slotted leg
    # passes through the centerline apron and leaves a neck, so the apron wraps
    # the round leg without being severed.
    sp.combine(proxy("LongApron_F", occ_ap),
               [proxy("Leg_FL", occ_legs), proxy("Leg_FR", occ_legs)], CUT, True, "LAf_LegCut")
    sp.combine(proxy("LongApron_B", occ_ap),
               [proxy("Leg_BL", occ_legs), proxy("Leg_BR", occ_legs)], CUT, True, "LAb_LegCut")
    # each spandrel straddles its own leg — let the leg through it (the leg cuts the spandrel)
    for spn, lg, tf in (("Spandrel_FL", "Leg_FL", "TF_Front"), ("Spandrel_FR", "Leg_FR", "TF_Front"),
                        ("Spandrel_BL", "Leg_BL", "TF_Back"), ("Spandrel_BR", "Leg_BR", "TF_Back")):
        sp.combine(proxy(spn, occ_ap), [proxy(lg, occ_legs)], CUT, True, spn + "_LegCut")
        sp.combine(proxy(spn, occ_ap), [proxy(tf, occ_top)], CUT, True, spn + "_TFtrim")
    # the 1.5 deg tilt nudges the apron top into the frame — trim it to the frame underside
    sp.combine(proxy("LongApron_F", occ_ap),
               [proxy("TF_Front", occ_top), proxy("TF_Left", occ_top), proxy("TF_Right", occ_top)],
               CUT, True, "LAf_TFtrim")
    sp.combine(proxy("LongApron_B", occ_ap),
               [proxy("TF_Back", occ_top), proxy("TF_Left", occ_top), proxy("TF_Right", occ_top)],
               CUT, True, "LAb_TFtrim")
    # the lofted short aprons inherit the long-apron miter faces' un-trimmed top (the
    # _lap overlap), so trim them flat to the frame underside too (else they poke into
    # the side frame members).
    sp.combine(proxy("ShortApron_L", occ_ap),
               [proxy("TF_Left", occ_top), proxy("TF_Front", occ_top), proxy("TF_Back", occ_top)],
               CUT, True, "SAL_TFtrim")
    sp.combine(proxy("ShortApron_R", occ_ap),
               [proxy("TF_Right", occ_top), proxy("TF_Front", occ_top), proxy("TF_Back", occ_top)],
               CUT, True, "SAR_TFtrim")

    # ============================================================
    # SHELF (component): coped-shoulder M&T to legs (rounded shoulder
    # wraps round leg; tenon into leg), flush frame-and-panel, batten.
    # ============================================================
    occ_sh = sp.make_comp(root, "Shelf")
    shc = occ_sh.component
    # Leg X/Y at the shelf rail mid-height (the leg leans, so it's further out than
    # at the top). Parametric, so the shelf tracks the legs when leg_setback_x changes.
    add("leg_x_shelf", "ltx + (leg_tip_z - (shelf_z - sf_t / 2)) * tan(splay)", "in", "Leg X at shelf mid-height (derived)")
    add("leg_y_shelf", "lty + (leg_tip_z - (shelf_z - sf_t / 2)) * tan(splay)", "in", "Leg Y at shelf mid-height (derived)")
    add("tenon_w", "0.875 in", "in", "Shelf-rail tenon width")
    Lx = ev("leg_x_shelf"); Ly = ev("leg_y_shelf"); r = ev("leg_r"); tw = ev("tenon_w")
    ze = "shelf_z - sf_t"; he = "sf_t"

    lf = pbox(shc, "ShelfLong_F", "-leg_x_shelf", "leg_x_shelf",
              "-leg_y_shelf - leg_r", "-leg_y_shelf + leg_r", ze, he)
    sp.mirror_body(shc, lf, shc.xZConstructionPlane, "ShLong_B_Mir")
    sl = pbox(shc, "ShelfShort_L", "-leg_x_shelf - leg_r", "-leg_x_shelf + leg_r",
              "-leg_y_shelf", "leg_y_shelf", ze, he)
    sp.mirror_body(shc, sl, shc.yZConstructionPlane, "ShShort_R_Mir")
    for i in range(shc.bRepBodies.count):
        b = shc.bRepBodies.item(i)
        if b.name == "ShelfLong_F (1)": b.name = "ShelfLong_B"
        elif b.name == "ShelfShort_L (1)": b.name = "ShelfShort_R"

    # 2. cope each rail by the legs it meets (rounded shoulder)
    cope = {"ShelfLong_F": ("Leg_FL", "Leg_FR"), "ShelfLong_B": ("Leg_BL", "Leg_BR"),
            "ShelfShort_L": ("Leg_FL", "Leg_BL"), "ShelfShort_R": ("Leg_FR", "Leg_BR")}
    for rn, legs in cope.items():
        sp.combine(proxy(rn, occ_sh), [proxy(legs[0], occ_legs), proxy(legs[1], occ_legs)],
                   CUT, True, rn + "_Cope")

    # 3. tenons into legs: build tenon body -> cut leg by tenon (mortise, tenon
    #    survives) -> join tenon to rail. Long tenons upper-Z, short lower-Z so
    #    the two tenons entering each leg don't collide.
    def tenon(name, rail, leg, x0_e, x1_e, y0_e, y1_e, zexpr, hexpr):
        t = pbox(shc, name, x0_e, x1_e, y0_e, y1_e, zexpr, hexpr)
        sp.combine(proxy(leg, occ_legs), [t.createForAssemblyContext(occ_sh)],
                   CUT, True, name + "_Mort")
        sp.combine(ctx.find_body(rail), [t], JOIN, False, name + "_J")
    zu = "shelf_z - 0.45 in"; zl = "shelf_z - sf_t + 0.075 in"; th = "0.375 in"
    HW = "tenon_w / 2"
    tenon("Tn_FL_L", "ShelfLong_F", "Leg_FL", "-leg_x_shelf - 0.2 cm", "-leg_x_shelf + leg_r + 0.3 cm", "-leg_y_shelf - "+HW, "-leg_y_shelf + "+HW, zu, th)
    tenon("Tn_FR_L", "ShelfLong_F", "Leg_FR", "leg_x_shelf - leg_r - 0.3 cm", "leg_x_shelf + 0.2 cm", "-leg_y_shelf - "+HW, "-leg_y_shelf + "+HW, zu, th)
    tenon("Tn_BL_L", "ShelfLong_B", "Leg_BL", "-leg_x_shelf - 0.2 cm", "-leg_x_shelf + leg_r + 0.3 cm", "leg_y_shelf - "+HW, "leg_y_shelf + "+HW, zu, th)
    tenon("Tn_BR_L", "ShelfLong_B", "Leg_BR", "leg_x_shelf - leg_r - 0.3 cm", "leg_x_shelf + 0.2 cm", "leg_y_shelf - "+HW, "leg_y_shelf + "+HW, zu, th)
    tenon("Tn_FL_S", "ShelfShort_L", "Leg_FL", "-leg_x_shelf - "+HW, "-leg_x_shelf + "+HW, "-leg_y_shelf - 0.2 cm", "-leg_y_shelf + leg_r + 0.3 cm", zl, th)
    tenon("Tn_BL_S", "ShelfShort_L", "Leg_BL", "-leg_x_shelf - "+HW, "-leg_x_shelf + "+HW, "leg_y_shelf - leg_r - 0.3 cm", "leg_y_shelf + 0.2 cm", zl, th)
    tenon("Tn_FR_S", "ShelfShort_R", "Leg_FR", "leg_x_shelf - "+HW, "leg_x_shelf + "+HW, "-leg_y_shelf - 0.2 cm", "-leg_y_shelf + leg_r + 0.3 cm", zl, th)
    tenon("Tn_BR_S", "ShelfShort_R", "Leg_BR", "leg_x_shelf - "+HW, "leg_x_shelf + "+HW, "leg_y_shelf - leg_r - 0.3 cm", "leg_y_shelf + 0.2 cm", zl, th)

    # 4b. trim short rails where they still overlap the long rails at corners
    sp.combine(ctx.find_body("ShelfShort_L"),
               [ctx.find_body("ShelfLong_F"), ctx.find_body("ShelfLong_B")], CUT, True, "ShS_L_trim")
    sp.combine(ctx.find_body("ShelfShort_R"),
               [ctx.find_body("ShelfLong_F"), ctx.find_body("ShelfLong_B")], CUT, True, "ShS_R_trim")

    # 5. flush shelf panel with one-shoulder tongues, grooved into rails
    siw = "leg_x_shelf - leg_r"; sih = "leg_y_shelf - leg_r"
    spanel = pbox(shc, "ShelfPanel",
                  "-(%s)" % siw, siw,
                  "-(%s)" % sih, sih,
                  "shelf_z - sp_panel_t", "sp_panel_t")
    stg_slab = pbox(shc, "SP_Tongue",
                    "-(%s + tongue_ov)" % siw, "%s + tongue_ov" % siw,
                    "-(%s + tongue_ov)" % sih, "%s + tongue_ov" % sih,
                    "shelf_z - sp_panel_t", "tongue_w")
    sp.combine(spanel, [stg_slab], JOIN, False, "SP_TgJ")
    for rn in ("ShelfLong_F", "ShelfLong_B", "ShelfShort_L", "ShelfShort_R"):
        sp.combine(ctx.find_body(rn), [spanel], CUT, True, rn + "_Groove")
    sp.combine(proxy("ShelfPanel", occ_sh),
               [proxy("Leg_FL", occ_legs), proxy("Leg_FR", occ_legs),
                proxy("Leg_BL", occ_legs), proxy("Leg_BR", occ_legs)], CUT, True, "ShPanel_LegClear")

    # 6. shelf batten: dovetail into panel; body stops at long-rail inner face,
    # only a tenon enters the rail
    pu = ev("shelf_z - sp_panel_t"); zbot = ev("shelf_z - sf_t")
    base = 0.5 * IN; topw = 0.75 * IN; sd = 0.1875 * IN; bw = 0.875 * IN
    yin = Ly - r  # long-rail inner face (cm) — for initial placement only
    sk = shc.sketches.add(sp.off_plane(shc, shc.xZConstructionPlane, "-(leg_y_shelf - leg_r)", "ShBt_Pl"))
    sk.name = "ShBatten_Sk"; m2s = sk.modelToSketchSpace
    bpts = [(-bw/2, zbot), (-bw/2, pu), (-base/2, pu), (-topw/2, pu+sd),
            (topw/2, pu+sd), (base/2, pu), (bw/2, pu), (bw/2, zbot)]
    sps = [m2s(P(px2, -yin, pz)) for (px2, pz) in bpts]
    lns = sk.sketchCurves.sketchLines
    first = lns.addByTwoPoints(P(sps[0].x, sps[0].y, 0), P(sps[1].x, sps[1].y, 0)); prev = first
    for k in range(2, len(sps)):
        prev = lns.addByTwoPoints(prev.endSketchPoint, P(sps[k].x, sps[k].y, 0))
    lns.addByTwoPoints(prev.endSketchPoint, first.startSketchPoint)
    sbt = sp.ext_new(shc, sk.profiles.item(0), "2 * (leg_y_shelf - leg_r)", "ShelfBatten").bodies.item(0)
    sbt.name = "ShelfBatten"
    _bz = "shelf_z - sp_panel_t - (sf_t - sp_panel_t)*2/3"; _bh = "(sf_t - sp_panel_t)*2/3"
    _yin_e = "leg_y_shelf - leg_r"   # long-rail inner face Y (parametric)
    tnF = pbox(shc, "ShBt_TnF", "-0.4375 in", "0.4375 in",
               "-(%s + 0.5 in)" % _yin_e, "-(%s)" % _yin_e, _bz, _bh)
    sp.combine(sbt, [tnF], JOIN, False, "ShBt_TnF_J")
    tnB = pbox(shc, "ShBt_TnB", "-0.4375 in", "0.4375 in",
               _yin_e, "%s + 0.5 in" % _yin_e, _bz, _bh)
    sp.combine(sbt, [tnB], JOIN, False, "ShBt_TnB_J")
    sp.combine(ctx.find_body("ShelfPanel"), [sbt], CUT, True, "ShBt_PanelDT")
    sp.combine(ctx.find_body("ShelfLong_F"), [sbt], CUT, True, "ShBt_MortF")
    sp.combine(ctx.find_body("ShelfLong_B"), [sbt], CUT, True, "ShBt_MortB")

    # ---- Top-frame edge profile: 7-point spline on all 4 outer edges ----
    _chd = ev("tf_cham_d"); _chh = ev("tf_cham_h")
    _tfl = ev("table_l") / 2; _tfd = ev("table_d") / 2
    zbot_ch = ev("tf_bot")
    def tf_cham_body(sketch_plane, out_coord, z, chd, chh, perp_val, name, ext_expr, axis='y', sign=1):
        opl = sp.off_plane(topc, sketch_plane, "0.001 cm", name + "_SkPl")
        sk = topc.sketches.add(opl); sk.name = name + "_Sk"
        m = sk.modelToSketchSpace
        d = sign * chd
        cpts = [
            (out_coord + d * 0.822, z),
            (out_coord + d * 0.593, z + chh * 0.013),
            (out_coord + d * 0.481, z + chh * 0.309),
            (out_coord + d * 0.324, z + chh * 0.351),
            (out_coord + d * 0.046, z + chh * 0.677),
            (out_coord + d * 0.016, z + chh * 0.902),
            (out_coord,                 z + chh),
        ]
        def mp(a, zv):
            if axis == 'y': return P(perp_val, a, zv)
            else:            return P(a, perp_val, zv)
        sall = [m(mp(cp[0], cp[1])) for cp in cpts]
        oc2 = adsk.core.ObjectCollection.create()
        for s in sall: oc2.add(P(s.x, s.y, 0))
        spl = sk.sketchCurves.sketchFittedSplines.add(oc2)
        corner = m(mp(out_coord, z))
        cl1 = sk.sketchCurves.sketchLines.addByTwoPoints(spl.endSketchPoint, P(corner.x, corner.y, 0))
        sk.sketchCurves.sketchLines.addByTwoPoints(cl1.endSketchPoint, spl.startSketchPoint)
        prof = max((sk.profiles.item(i) for i in range(sk.profiles.count)),
                   key=lambda p: p.areaProperties().area)
        return sp.ext_new_sym(topc, prof, ext_expr, name).bodies.item(0)
    tf_chF = tf_cham_body(topc.yZConstructionPlane, -_tfd, zbot_ch, _chd, _chh,
                          0, "TF_ChamF", "table_l / 2 + 1 cm", axis='y', sign=1)
    tf_chB = tf_cham_body(topc.yZConstructionPlane, _tfd, zbot_ch, _chd, _chh,
                          0, "TF_ChamB", "table_l / 2 + 1 cm", axis='y', sign=-1)
    tf_chL = tf_cham_body(topc.xZConstructionPlane, -_tfl, zbot_ch, _chd, _chh,
                          0, "TF_ChamL", "table_d / 2 + 1 cm", axis='x', sign=1)
    tf_chR = tf_cham_body(topc.xZConstructionPlane, _tfl, zbot_ch, _chd, _chh,
                          0, "TF_ChamR", "table_d / 2 + 1 cm", axis='x', sign=-1)
    sp.combine(ctx.find_body("TF_Front"), [tf_chF], CUT, False, "TF_Front_Cham")
    sp.combine(ctx.find_body("TF_Back"), [tf_chB], CUT, False, "TF_Back_Cham")
    sp.combine(ctx.find_body("TF_Left"), [tf_chL], CUT, False, "TF_Left_Cham")
    sp.combine(ctx.find_body("TF_Right"), [tf_chR], CUT, False, "TF_Right_Cham")

    allb = []
    for occ in (occ_legs, occ_top, occ_ap, occ_sh):
        c = occ.component
        for i in range(c.bRepBodies.count):
            allb.append(c.name + "/" + c.bRepBodies.item(i).name)
    print("phaseA bodies:", sorted(allb))

    # Final cleanup: hide every sketch + construction plane/axis/point + origin folder so a
    # rebuild presents a clean model. Folder light bulbs alone don't always suppress items
    # in the viewport, so also switch each individual item off (belt-and-suspenders).
    _des = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
    for _c in _des.allComponents:
        _c.isSketchFolderLightBulbOn = False
        _c.isConstructionFolderLightBulbOn = False
        _c.isOriginFolderLightBulbOn = False
        for _i in range(_c.sketches.count): _c.sketches.item(_i).isLightBulbOn = False
        for _i in range(_c.constructionPlanes.count): _c.constructionPlanes.item(_i).isLightBulbOn = False
        for _i in range(_c.constructionAxes.count): _c.constructionAxes.item(_i).isLightBulbOn = False
        for _i in range(_c.constructionPoints.count): _c.constructionPoints.item(_i).isLightBulbOn = False
