"""Generated from capture_design — Stool v1
NOTE: Auto-generated. Features marked TODO need manual review."""
import adsk.core, adsk.fusion, math


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters

    # ── PARAMETERS ────────────────────────────────────────────────
    for name, expr, unit, comment in [
        ("seat_l", "12 in", "in", "Seat length (X)"),
        ("seat_w", "7 in", "in", "Seat width (Y)"),
        ("seat_t", "0.9 in", "in", "Seat thickness"),
        ("leg_w", "1.4 in", "in", "Leg width (X)"),
        ("leg_d", "1.1 in", "in", "Leg depth (Y)"),
        ("leg_h", "7 in", "in", "Leg height to seat bottom"),
        ("splay", "10 deg", "deg", "Leg splay along length"),
        ("splay_w", "5 deg", "deg", "Leg splay along width"),
        ("leg_inset_x", "2 in", "in", "Leg center from seat end"),
        ("leg_inset_y", "1.5 in", "in", "Leg center from seat edge"),
        ("tenon_proud", "0.125 in", "in", "Tenon above seat"),
        ("seat_bevel", "5 deg", "deg", "Seat side bevel angle"),
        ("tenon_shoulder_w", "0.3 in", "in", ""),
    ]:
        params.add(name, adsk.core.ValueInput.createByString(expr), unit, comment)

    for name, expr, unit, comment in [
        ("seat_z", "leg_h", "in", "Seat bottom Z"),
        ("leg_top_z", "leg_h + seat_t + tenon_proud", "in", "Leg extends to this Z"),
        ("splay_shift", "leg_top_z * tan(splay)", "in", "Foot offset from top"),
    ]:
        params.add(name, adsk.core.ValueInput.createByString(expr), unit, comment)

    # ── TWO COMPONENTS: Seat + Legs ──────────────────────────────
    from helpers import sp
    seat_occ = sp.make_comp(root, "Seat")
    seat_c = seat_occ.component
    legs_occ = sp.make_comp(root, "Legs")
    legs_c = legs_occ.component

    # ── HELPERS ───────────────────────────────────────────────────
    P = adsk.core.Point3D.create
    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
    NEWBODY = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation

    def ev(e):
        p = params.itemByName(e)
        return p.value if p else design.unitsManager.evaluateExpression(e, "cm")

    def off_plane(comp, base, expr, name="Pl"):
        inp = comp.constructionPlanes.createInput()
        inp.setByOffset(base, adsk.core.ValueInput.createByString(expr))
        p = comp.constructionPlanes.add(inp)
        p.name = name
        return p

    def find_body(name):
        for comp in [seat_c, legs_c]:
            for i in range(comp.bRepBodies.count):
                if comp.bRepBodies.item(i).name == name:
                    return comp.bRepBodies.item(i)
        return None

    def find_face(body, axis, direction):
        best, best_val = None, (-1e10 if direction > 0 else 1e10)
        for i in range(body.faces.count):
            f = body.faces.item(i)
            if isinstance(f.geometry, adsk.core.Plane) and abs(getattr(f.geometry.normal, axis)) > 0.9:
                fv = getattr(f.pointOnFace, axis)
                if (direction > 0 and fv > best_val) or (direction < 0 and fv < best_val):
                    best, best_val = f, fv
        return best

    def find_face_near(body, px, py, pz, nx=0, ny=0, nz=0):
        best, best_d = None, 1e10
        for i in range(body.faces.count):
            f = body.faces.item(i)
            if isinstance(f.geometry, adsk.core.Plane):
                n = f.geometry.normal
                if nx or ny or nz:
                    if abs(abs(n.x*nx+n.y*ny+n.z*nz) - 1.0) > 0.1: continue
                p = f.pointOnFace
                d = abs(p.x - px) + abs(p.y - py) + abs(p.z - pz)
                if d < best_d: best, best_d = f, d
        return best

    def combine(comp, target, tools, op, keep, name="Comb"):
        coll = adsk.core.ObjectCollection.create()
        for b in (tools if isinstance(tools, list) else [tools]): coll.add(b)
        inp = comp.features.combineFeatures.createInput(target, coll)
        inp.operation = op
        inp.isKeepToolBodies = keep
        f = comp.features.combineFeatures.add(inp)
        f.name = name
        return f

    def mirror_bodies(comp, bodies, plane, name="Mir"):
        coll = adsk.core.ObjectCollection.create()
        for b in bodies: coll.add(b)
        inp = comp.features.mirrorFeatures.createInput(coll, plane)
        m = comp.features.mirrorFeatures.add(inp)
        m.name = name
        return m

    # ── TIMELINE ──────────────────────────────────────────────────

    # [0] ConstructionPlane: XMid (in root — used for cross-component mirrors)
    XMid = off_plane(root, root.yZConstructionPlane, "seat_l / 2", "XMid")

    # [1] ConstructionPlane: YMid (in root — used for cross-component mirrors)
    YMid = off_plane(root, root.xZConstructionPlane, "seat_w / 2", "YMid")

    # [2] ConstructionPlane: Seat_Pl (in seat_c)
    Seat_Pl = off_plane(seat_c, seat_c.xYConstructionPlane, "seat_z", "Seat_Pl")

    # [3] Sketch: Seat_Sk (in seat_c)
    Seat_Sk = seat_c.sketches.add(Seat_Pl)
    Seat_Sk.name = "Seat_Sk"
    x0, y0, w, h = ev("0 cm"), ev("0 cm"), ev("seat_l"), ev("seat_w")
    rect = Seat_Sk.sketchCurves.sketchLines.addTwoPointRectangle(
        P(x0, y0, 0), P(x0 + w, y0 + h, 0))
    gc = Seat_Sk.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    d = Seat_Sk.sketchDimensions
    d.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        H, P(x0 + w/2, y0 - 1, 0)).parameter.expression = "seat_l"
    d.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        V, P(x0 + w + 1, y0 + h/2, 0)).parameter.expression = "seat_w"
    Seat_Sk_prof = Seat_Sk.profiles.item(0)

    # [4] Extrude: SeatBoard (in seat_c)
    inp = seat_c.features.extrudeFeatures.createInput(Seat_Sk_prof, NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("seat_t"))
    inp.taperAngle = adsk.core.ValueInput.createByString("seat_bevel")
    SeatBoard = seat_c.features.extrudeFeatures.add(inp)
    SeatBoard.name = "SeatBoard"
    Seat = SeatBoard.bodies.item(0)
    Seat.name = "Seat"

    # ── Assembly proxy: Seat body visible from legs_c context ─────
    Seat_proxy = Seat.createForAssemblyContext(seat_occ)

    # [5] ConstructionPlane: LegFront_Pl (in legs_c)
    LegFront_Pl = off_plane(legs_c, legs_c.xZConstructionPlane, "leg_inset_y - leg_d / 2", "LegFront_Pl")

    # Body-relative ref: Leg_NL depends on Seat
    ref_body = find_body("Seat")
    ref_bb = ref_body.boundingBox

    # [6] Sketch: Leg_NL_Sk (in legs_c)
    Leg_NL_Sk = legs_c.sketches.add(LegFront_Pl)
    Leg_NL_Sk.name = "Leg_NL_Sk"
    lns = Leg_NL_Sk.sketchCurves.sketchLines
    def _xf(sx, sy): return (sx, sy)
    ln0 = lns.addByTwoPoints(P(3.302, -20.3835, 0), P(6.858, -20.3835, 0))
    ln1 = lns.addByTwoPoints(ln0.endSketchPoint, P(3.2638, 0.0, 0))
    ln2 = lns.addByTwoPoints(ln1.endSketchPoint, P(-0.2922, 0.0, 0))
    ln3 = lns.addByTwoPoints(ln2.endSketchPoint, ln0.startSketchPoint)
    d = Leg_NL_Sk.sketchDimensions
    d.addDistanceDimension(ln0.startSketchPoint, ln0.endSketchPoint,
        H, P(0, 0, 0)).parameter.expression = "leg_w"
    d.addDistanceDimension(ln1.endSketchPoint, ln2.endSketchPoint,
        H, P(0, 0, 0)).parameter.expression = "leg_w"
    d.addDistanceDimension(Leg_NL_Sk.originPoint, ln0.startSketchPoint,
        V, P(0, 0, 0)).parameter.expression = "leg_top_z"
    d.addDistanceDimension(Leg_NL_Sk.originPoint, ln0.startSketchPoint,
        H, P(0, 0, 0)).parameter.expression = "leg_inset_x - leg_w / 2"
    d.addDistanceDimension(ln0.startSketchPoint, ln2.endSketchPoint,
        V, P(0, 0, 0)).parameter.expression = "leg_top_z"
    d.addDistanceDimension(ln0.startSketchPoint, ln2.endSketchPoint,
        H, P(0, 0, 0)).parameter.expression = "splay_shift"
    gc = Leg_NL_Sk.geometricConstraints
    gc.addHorizontal(ln0)
    gc.addHorizontal(ln2)
    Leg_NL_Sk_prof = Leg_NL_Sk.profiles.item(0)  # 1 profile(s)

    # [7] Extrude: Leg_NL (in legs_c)
    inp = legs_c.features.extrudeFeatures.createInput(Leg_NL_Sk_prof, NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("leg_d"))
    Leg_NL = legs_c.features.extrudeFeatures.add(inp)
    Leg_NL.name = "Leg_NL"
    Leg_NL_b = Leg_NL.bodies.item(0)
    Leg_NL_b.name = "Leg_NL"

    # [8] Move: YSplay_NL (in legs_c)
    xform = adsk.core.Matrix3D.create()
    xform.setWithArray([1.0, 0.0, 0.0, 0.0, 0.0, 0.996194698092, 0.087155742748, -1.839522337329, 0.0, -0.087155742748, 0.996194698092, 0.413011664712, 0.0, 0.0, 0.0, 1.0])
    move_coll = adsk.core.ObjectCollection.create()
    move_coll.add(Leg_NL_b)
    move_inp = legs_c.features.moveFeatures.createInput2(move_coll)
    move_inp.defineAsFreeMove(xform)
    move_feat = legs_c.features.moveFeatures.add(move_inp)
    move_feat.name = "YSplay_NL"

    # [9] Sketch: Sketch3 (in legs_c, on Seat's top face via proxy)
    # Get the Seat proxy face for the sketch plane
    _seat_top_face = find_face_near(Seat_proxy, 15.24, 8.89, 17.78, 0.0, 0.0, 1.0)
    Sketch3 = legs_c.sketches.add(_seat_top_face)
    Sketch3.name = "Sketch3"
    lns = Sketch3.sketchCurves.sketchLines
    # Coordinate transform: captured sketch axes -> actual sketch axes
    _cap_xd = (1.0, 0.0, 0.0)
    _cap_yd = (0.0, -1.0, 0.0)
    _act_xd = Sketch3.xDirection
    _act_yd = Sketch3.yDirection
    _m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z
    _m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z
    _m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z
    _m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z
    def _xf(sx, sy):
        return (sx * _m00 + sy * _m01, sx * _m10 + sy * _m11)
    # Intersect body 'Leg_NL' with sketch plane (same component — no proxy needed)
    _proj_body_Leg_NL = Sketch3.intersectWithSketchPlane([Leg_NL_b])
    _proj_pts = []  # [(x, y, sketchPoint), ...]
    _proj_curves = []  # [(sx, sy, ex, ey, curve), ...]
    for _ci in range(Sketch3.sketchCurves.count):
        _c = Sketch3.sketchCurves.item(_ci)
        if _c.isReference:
            for _sp in [_c.startSketchPoint, _c.endSketchPoint]:
                _g = _sp.geometry
                _proj_pts.append((_g.x, _g.y, _sp))
            _s, _e = _c.startSketchPoint.geometry, _c.endSketchPoint.geometry
            _proj_curves.append((_s.x, _s.y, _e.x, _e.y, _c))

    def _nearest_proj(x, y):
        best, best_d = None, 1e10
        for _px, _py, _sp in _proj_pts:
            _d = abs(_px - x) + abs(_py - y)
            if _d < best_d: best, best_d = _sp, _d
        return best

    def _nearest_proj_curve(sx, sy, ex, ey):
        best, best_d = None, 1e10
        for _sx, _sy, _ex, _ey, _c in _proj_curves:
            _d = min(abs(_sx-sx)+abs(_sy-sy)+abs(_ex-ex)+abs(_ey-ey),
                    abs(_sx-ex)+abs(_sy-ey)+abs(_ex-sx)+abs(_ey-sy))
            if _d < best_d: best, best_d = _c, _d
        return best
    _pcurve_4 = _nearest_proj_curve(*_xf(2.819, -2.1021), *_xf(2.8621, -4.9068))
    _pcurve_5 = _nearest_proj_curve(*_xf(2.8621, -4.9068), *_xf(6.4181, -4.9068))
    _pcurve_6 = _nearest_proj_curve(*_xf(6.4181, -4.9068), *_xf(6.375, -2.1021))
    _pcurve_7 = _nearest_proj_curve(*_xf(6.375, -2.1021), *_xf(2.819, -2.1021))
    _cs_4 = _xf(2.819, -2.1021)
    _ce_4 = _xf(2.8307, -2.864)
    _pp_4s = _nearest_proj(_cs_4[0], _cs_4[1])
    _pg_4s = _pp_4s.geometry
    _es_4 = _pcurve_4.startSketchPoint.geometry
    _ee_4 = _pcurve_4.endSketchPoint.geometry
    _el_4 = ((_ee_4.x-_es_4.x)**2+(_ee_4.y-_es_4.y)**2)**0.5
    _ed_4 = 0.76199 / _el_4 if _el_4 > 0.001 else 0
    _ds_4 = abs(_pg_4s.x-_es_4.x)+abs(_pg_4s.y-_es_4.y)
    _de_4 = abs(_pg_4s.x-_ee_4.x)+abs(_pg_4s.y-_ee_4.y)
    if _ds_4 < _de_4:
        _ex_4 = _es_4.x + (_ee_4.x-_es_4.x)*_ed_4
        _ey_4 = _es_4.y + (_ee_4.y-_es_4.y)*_ed_4
    else:
        _ex_4 = _ee_4.x + (_es_4.x-_ee_4.x)*_ed_4
        _ey_4 = _ee_4.y + (_es_4.y-_ee_4.y)*_ed_4
    ln4 = lns.addByTwoPoints(P(_pg_4s.x, _pg_4s.y, 0), P(_ex_4, _ey_4, 0))
    Sketch3.geometricConstraints.addCoincident(ln4.startSketchPoint, _pp_4s)
    _cs_5 = _xf(6.375, -2.1021)
    _ce_5 = _xf(6.3867, -2.864)
    _pp_5s = _nearest_proj(_cs_5[0], _cs_5[1])
    _pg_5s = _pp_5s.geometry
    _es_5 = _pcurve_6.startSketchPoint.geometry
    _ee_5 = _pcurve_6.endSketchPoint.geometry
    _el_5 = ((_ee_5.x-_es_5.x)**2+(_ee_5.y-_es_5.y)**2)**0.5
    _ed_5 = 0.76199 / _el_5 if _el_5 > 0.001 else 0
    _ds_5 = abs(_pg_5s.x-_es_5.x)+abs(_pg_5s.y-_es_5.y)
    _de_5 = abs(_pg_5s.x-_ee_5.x)+abs(_pg_5s.y-_ee_5.y)
    if _ds_5 < _de_5:
        _ex_5 = _es_5.x + (_ee_5.x-_es_5.x)*_ed_5
        _ey_5 = _es_5.y + (_ee_5.y-_es_5.y)*_ed_5
    else:
        _ex_5 = _ee_5.x + (_es_5.x-_ee_5.x)*_ed_5
        _ey_5 = _ee_5.y + (_es_5.y-_ee_5.y)*_ed_5
    ln5 = lns.addByTwoPoints(P(_pg_5s.x, _pg_5s.y, 0), P(_ex_5, _ey_5, 0))
    Sketch3.geometricConstraints.addCoincident(ln5.startSketchPoint, _pp_5s)
    _cs_6 = _xf(2.8621, -4.9068)
    _ce_6 = _xf(2.8504, -4.1449)
    _pp_6s = _nearest_proj(_cs_6[0], _cs_6[1])
    _pg_6s = _pp_6s.geometry
    _es_6 = _pcurve_4.startSketchPoint.geometry
    _ee_6 = _pcurve_4.endSketchPoint.geometry
    _el_6 = ((_ee_6.x-_es_6.x)**2+(_ee_6.y-_es_6.y)**2)**0.5
    _ed_6 = 0.76199 / _el_6 if _el_6 > 0.001 else 0
    _ds_6 = abs(_pg_6s.x-_es_6.x)+abs(_pg_6s.y-_es_6.y)
    _de_6 = abs(_pg_6s.x-_ee_6.x)+abs(_pg_6s.y-_ee_6.y)
    if _ds_6 < _de_6:
        _ex_6 = _es_6.x + (_ee_6.x-_es_6.x)*_ed_6
        _ey_6 = _es_6.y + (_ee_6.y-_es_6.y)*_ed_6
    else:
        _ex_6 = _ee_6.x + (_es_6.x-_ee_6.x)*_ed_6
        _ey_6 = _ee_6.y + (_es_6.y-_ee_6.y)*_ed_6
    ln6 = lns.addByTwoPoints(P(_pg_6s.x, _pg_6s.y, 0), P(_ex_6, _ey_6, 0))
    Sketch3.geometricConstraints.addCoincident(ln6.startSketchPoint, _pp_6s)
    _cs_7 = _xf(6.4181, -4.9068)
    _ce_7 = _xf(6.4064, -4.1449)
    _pp_7s = _nearest_proj(_cs_7[0], _cs_7[1])
    _pg_7s = _pp_7s.geometry
    _es_7 = _pcurve_6.startSketchPoint.geometry
    _ee_7 = _pcurve_6.endSketchPoint.geometry
    _el_7 = ((_ee_7.x-_es_7.x)**2+(_ee_7.y-_es_7.y)**2)**0.5
    _ed_7 = 0.76199 / _el_7 if _el_7 > 0.001 else 0
    _ds_7 = abs(_pg_7s.x-_es_7.x)+abs(_pg_7s.y-_es_7.y)
    _de_7 = abs(_pg_7s.x-_ee_7.x)+abs(_pg_7s.y-_ee_7.y)
    if _ds_7 < _de_7:
        _ex_7 = _es_7.x + (_ee_7.x-_es_7.x)*_ed_7
        _ey_7 = _es_7.y + (_ee_7.y-_es_7.y)*_ed_7
    else:
        _ex_7 = _ee_7.x + (_es_7.x-_ee_7.x)*_ed_7
        _ey_7 = _ee_7.y + (_es_7.y-_ee_7.y)*_ed_7
    ln7 = lns.addByTwoPoints(P(_pg_7s.x, _pg_7s.y, 0), P(_ex_7, _ey_7, 0))
    Sketch3.geometricConstraints.addCoincident(ln7.startSketchPoint, _pp_7s)
    _cs_8 = _xf(2.8307, -2.864)
    _ce_8 = _xf(6.3867, -2.864)
    ln8 = lns.addByTwoPoints(ln4.endSketchPoint, ln5.endSketchPoint)
    _cs_9 = _xf(2.8504, -4.1449)
    _ce_9 = _xf(6.4064, -4.1449)
    ln9 = lns.addByTwoPoints(ln6.endSketchPoint, ln7.endSketchPoint)
    d = Sketch3.sketchDimensions
    d.addDistanceDimension(_nearest_proj(*_xf(2.819, -2.1021)), ln4.endSketchPoint,
        adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, P(0, 0, 0)).parameter.expression = "tenon_shoulder_w"
    d.addDistanceDimension(_nearest_proj(*_xf(6.375, -2.1021)), ln5.endSketchPoint,
        adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, P(0, 0, 0)).parameter.expression = "tenon_shoulder_w"
    d.addDistanceDimension(_nearest_proj(*_xf(2.8621, -4.9068)), ln6.endSketchPoint,
        adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, P(0, 0, 0)).parameter.expression = "tenon_shoulder_w"
    d.addDistanceDimension(_nearest_proj(*_xf(6.4181, -4.9068)), ln7.endSketchPoint,
        adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, P(0, 0, 0)).parameter.expression = "tenon_shoulder_w"
    gc = Sketch3.geometricConstraints
    _best_pi, _best_a = 0, float('inf')
    for _pi in range(Sketch3.profiles.count):
        _bb = Sketch3.profiles.item(_pi).boundingBox
        _a = abs(_bb.maxPoint.x-_bb.minPoint.x)*abs(_bb.maxPoint.y-_bb.minPoint.y)
        if _a < _best_a: _best_a, _best_pi = _a, _pi
    Sketch3_prof = Sketch3.profiles.item(_best_pi)

    # [10] Sweep: Sweep1 (in legs_c — CUTs leg tenon shoulder)
    # variant 1: d1=1.00, d2=0 (swapped)
    sweep_profs = adsk.core.ObjectCollection.create()
    _target_dims = [
        (3.5677, 0.7619),
        (3.5677, 0.7619),
    ]
    _used = set()
    for _tw, _th in _target_dims:
        _best_pi, _best_d = -1, 1e10
        for _pi in range(Sketch3.profiles.count):
            if _pi not in _used:
                _bb = Sketch3.profiles.item(_pi).boundingBox
                _w = abs(_bb.maxPoint.x - _bb.minPoint.x)
                _h = abs(_bb.maxPoint.y - _bb.minPoint.y)
                _d = abs(_w - _tw) + abs(_h - _th)
                if _d < _best_d: _best_pi, _best_d = _pi, _d
        if _best_pi >= 0:
            sweep_profs.add(Sketch3.profiles.item(_best_pi))
            _used.add(_best_pi)
    # Path: edge on 'Leg_NL' from ~(-0.29, 0.56, 0.20) to ~(3.30, 2.34, 20.51)
    sweep_edge = None
    for i in range(Leg_NL_b.edges.count):
        e = Leg_NL_b.edges.item(i)
        sv, ep = e.startVertex.geometry, e.endVertex.geometry
        if (abs(sv.x - -0.2922) + abs(sv.y - 0.5643) + abs(sv.z - 0.2027) < 0.1 and
            abs(ep.x - 3.3020) + abs(ep.y - 2.3408) + abs(ep.z - 20.5086) < 0.1):
            sweep_edge = e
            break
    sweep_path = legs_c.features.createPath(sweep_edge)
    _psv = sweep_edge.startVertex.geometry
    _vtx_match = (abs(_psv.x - -0.2922) + abs(_psv.y - 0.5643) + abs(_psv.z - 0.2027) < 0.1)
    _opposed = sweep_path.item(0).isOpposedToEntity
    _path_fwd = not (_vtx_match != _opposed)
    # _path_fwd: True if path direction matches captured direction
    sweep_inp = legs_c.features.sweepFeatures.createInput(sweep_profs, sweep_path, CUT)
    sweep_inp.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
    if _path_fwd:
        sweep_inp.distanceTwo = adsk.core.ValueInput.createByString("0")
        sweep_inp.distanceOne = adsk.core.ValueInput.createByString("1.00")
    else:
        sweep_inp.distanceTwo = adsk.core.ValueInput.createByString("1.00")
        sweep_inp.distanceOne = adsk.core.ValueInput.createByString("0")
    sweep_inp.participantBodies = [Leg_NL_b]
    sweep_feat = legs_c.features.sweepFeatures.add(sweep_inp)
    sweep_feat.name = "Sweep1"

    # [11] ConstructionPlane: Plane5 (in legs_c)
    Plane5 = off_plane(legs_c, legs_c.xYConstructionPlane, "0.08 in", "Plane5")

    # [12] SplitBody: Split1 (in legs_c — splits Leg_NL_b by Plane5)
    split_inp = legs_c.features.splitBodyFeatures.createInput(Leg_NL_b, Plane5, True)
    split_feat = legs_c.features.splitBodyFeatures.add(split_inp)
    split_feat.name = "Split1"

    # Multi-tool split workaround: expected 3 pieces from 1 body
    # API only supports 1 tool per split — try additional planes
    _pre_count = legs_c.bRepBodies.count
    _need = 3 - (legs_c.bRepBodies.count - _pre_count + 2)
    # 2 = minimum pieces from first split
    _got = 0
    for _bi in range(legs_c.bRepBodies.count):
        _bn = legs_c.bRepBodies.item(_bi).name
        import re as _re
        if _re.sub(r"(\s*\(\d+\))+\s*$", "", _bn) == "Leg_NL": _got += 1
    if _got < 3:
        # Try each construction plane as supplementary split tool
        _biggest = None
        for _bi in range(legs_c.bRepBodies.count):
            _b = legs_c.bRepBodies.item(_bi)
            if _re.sub(r"(\s*\(\d+\))+\s*$", "", _b.name) == "Leg_NL":
                if _biggest is None or _b.volume > _biggest.volume: _biggest = _b
        if _biggest:
            # Try every candidate tool, score by volume match, pick best
            _tools = []
            for _pi in range(legs_c.constructionPlanes.count):
                _tools.append(legs_c.constructionPlanes.item(_pi))
            for _bi3 in range(legs_c.bRepBodies.count):
                _bod = legs_c.bRepBodies.item(_bi3)
                if _bod != _biggest:
                    for _fi in range(_bod.faces.count):
                        _tools.append(_bod.faces.item(_fi))
            # Record pre-supplementary volumes to detect new pieces
            _pre_vols = set()
            for _bi4 in range(legs_c.bRepBodies.count):
                _pre_vols.add(round(legs_c.bRepBodies.item(_bi4).volume, 4))
            _best_tool = None
            _best_new_vol = 1e10
            for _pl in _tools:
                try:
                    _si = legs_c.features.splitBodyFeatures.createInput(_biggest, _pl, True)
                    _sf = legs_c.features.splitBodyFeatures.add(_si)
                    # Find the smallest NEW piece (not in pre-split volumes)
                    _new_min = 1e10
                    for _bi2 in range(legs_c.bRepBodies.count):
                        _bx = legs_c.bRepBodies.item(_bi2)
                        _bv = round(_bx.volume, 4)
                        if _bv not in _pre_vols and _bv < _new_min: _new_min = _bv
                    if _new_min < _best_new_vol:
                        _best_new_vol = _new_min
                        _best_tool = _pl
                    _sf.deleteMe()
                except:
                    pass
            # Apply the best tool (smallest new piece = closest to trim waste)
            if _best_tool is not None:
                _si = legs_c.features.splitBodyFeatures.createInput(_biggest, _best_tool, True)
                _sf = legs_c.features.splitBodyFeatures.add(_si)
                _sf.name = "Split1_sup"
    _found = set()
    Seat = find_body("Seat")
    if Seat: _found.add("Seat")
    Leg_NL_1 = find_body("Leg_NL (1)")
    if Leg_NL_1: _found.add("Leg_NL (1)")
    Leg_NL_2 = find_body("Leg_NL (2)")
    if Leg_NL_2: _found.add("Leg_NL (2)")
    Leg_NL = find_body("Leg_NL")
    if Leg_NL: _found.add("Leg_NL")
    _expected = ['Seat', 'Leg_NL (1)', 'Leg_NL (2)', 'Leg_NL']
    _missing = [n for n in _expected if n not in _found]
    if _missing:
        _unmatched = []
        for _bi in range(legs_c.bRepBodies.count):
            _b = legs_c.bRepBodies.item(_bi)
            if _b.name not in _found: _unmatched.append(_b)
        _unmatched.sort(key=lambda b: -b.volume)
        _missing.sort(key=lambda n: -max((b.volume for b in _unmatched), default=0) if not any(b.name == n for b in _unmatched) else 0)
        for _nm in _missing:
            if _unmatched:
                _ub = _unmatched.pop(0)
                _ub.name = _nm
        if not Seat: Seat = find_body("Seat")
        if not Leg_NL_1: Leg_NL_1 = find_body("Leg_NL (1)")
        if not Leg_NL_2: Leg_NL_2 = find_body("Leg_NL (2)")
        if not Leg_NL: Leg_NL = find_body("Leg_NL")

    # [13] Remove: RemoveBody-Leg_NL (in legs_c)
    _rm = Leg_NL
    if _rm: legs_c.features.removeFeatures.add(_rm)

    # [14] Remove: RemoveBody-Leg_NL (2) (in legs_c)
    _rm = Leg_NL_2
    if _rm: legs_c.features.removeFeatures.add(_rm)

    # Body-relative refs: Leg_NR depends on Seat
    ref_body = find_body("Seat")
    ref_bb = ref_body.boundingBox

    # [15] Mirror: Leg_NR_Mirror (in legs_c, mirror across YMid in root)
    Leg_NR_Mirror = mirror_bodies(legs_c, [Leg_NL_1], YMid, "Leg_NR_Mirror")
    Leg_NR = Leg_NR_Mirror.bodies.item(0)
    Leg_NR.name = "Leg_NR"
    Leg_NL_1 = Leg_NR_Mirror.bodies.item(1)
    Leg_NL_1.name = "Leg_NL (1)"

    # Body-relative refs: Leg_FL depends on Seat
    ref_body = find_body("Seat")
    ref_bb = ref_body.boundingBox

    # [16] Mirror: Legs_Far_Mirror (in legs_c, mirror across XMid in root)
    Legs_Far_Mirror = mirror_bodies(legs_c, [Leg_NL_1, Leg_NR], XMid, "Legs_Far_Mirror")
    Leg_FR = Legs_Far_Mirror.bodies.item(0)
    Leg_FR.name = "Leg_FR"
    Leg_FL = Legs_Far_Mirror.bodies.item(1)
    Leg_FL.name = "Leg_FL"
    Leg_NL_1 = Legs_Far_Mirror.bodies.item(2)
    Leg_NL_1.name = "Leg_NL (1)"
    Leg_NR = Legs_Far_Mirror.bodies.item(3)
    Leg_NR.name = "Leg_NR"

    # Body-relative ref: Leg_FR depends on Leg_FL
    ref_body = find_body("Leg_FL")
    ref_bb = ref_body.boundingBox

    # [17] Combine: ThroughMortise (cross-component: Seat CUT by legs)
    # sp.combine auto-proxies tool bodies from legs_c into seat_c context
    sp.combine(Seat, [Leg_NL_1, Leg_NR, Leg_FL, Leg_FR], CUT, True, "ThroughMortise")

    # [18] Fillet: SeatFillet (in seat_c — Seat body edges only)
    fillet_inp_seat = seat_c.features.filletFeatures.createInput()
    fillet_items_seat = adsk.core.ObjectCollection.create()
    _seat_face_targets = [
        ("Seat", -0.1, 8.89, 18.923),
        ("Seat", 15.24, -0.1, 18.923),
        ("Seat", 30.58, 8.89, 18.923),
        ("Seat", 15.24, 17.88, 18.923),
    ]
    _added_seat = set()
    for _fb, _fx, _fy, _fz in _seat_face_targets:
        _best_face, _best_d = None, 1e10
        for _bsi in range(seat_c.bRepBodies.count):
            _body = seat_c.bRepBodies.item(_bsi)
            for _fi in range(_body.faces.count):
                _f = _body.faces.item(_fi)
                _p = _f.pointOnFace
                _d = abs(_p.x-_fx)+abs(_p.y-_fy)+abs(_p.z-_fz)
                if _d < _best_d: _best_face, _best_d = _f, _d
        if _best_face and _best_d < 0.5:
            for _ei in range(_best_face.edges.count):
                _edge = _best_face.edges.item(_ei)
                _eid = _edge.tempId
                if _eid not in _added_seat:
                    fillet_items_seat.add(_edge)
                    _added_seat.add(_eid)
    if fillet_items_seat.count > 0:
        fillet_inp_seat.addConstantRadiusEdgeSet(fillet_items_seat, adsk.core.ValueInput.createByString("0.05 in"), True)
        fillet_feat_seat = seat_c.features.filletFeatures.add(fillet_inp_seat)
        fillet_feat_seat.name = "SeatFillet"

    # [18b] Fillet: LegFillet (in legs_c — Leg body edges only)
    fillet_inp_legs = legs_c.features.filletFeatures.createInput()
    fillet_items_legs = adsk.core.ObjectCollection.create()
    _leg_face_targets = [
        ("Leg_NR", 3.0846, 13.6421, 8.9916),
        ("Leg_NR", 3.0415, 16.4468, 8.9916),
        ("Leg_NR", 1.5075, 15.8133, 0.2032),
        ("Leg_FL", 27.3954, 4.1379, 8.9916),
        ("Leg_FL", 27.4385, 1.3332, 8.9916),
        ("Leg_FL", 28.9725, 1.9667, 0.2032),
        ("Leg_FR", 27.4385, 16.4468, 8.9916),
        ("Leg_FR", 27.3954, 13.6421, 8.9916),
        ("Leg_FR", 28.9725, 15.8133, 0.2032),
        ("Leg_NL (1)", 3.0415, 1.3332, 8.9916),
        ("Leg_NL (1)", 3.0846, 4.1379, 8.9916),
        ("Leg_NL (1)", 1.5075, 1.9667, 0.2032),
    ]
    _added_legs = set()
    for _fb, _fx, _fy, _fz in _leg_face_targets:
        _best_face, _best_d = None, 1e10
        for _bsi in range(legs_c.bRepBodies.count):
            _body = legs_c.bRepBodies.item(_bsi)
            for _fi in range(_body.faces.count):
                _f = _body.faces.item(_fi)
                _p = _f.pointOnFace
                _d = abs(_p.x-_fx)+abs(_p.y-_fy)+abs(_p.z-_fz)
                if _d < _best_d: _best_face, _best_d = _f, _d
        if _best_face and _best_d < 0.5:
            for _ei in range(_best_face.edges.count):
                _edge = _best_face.edges.item(_ei)
                _eid = _edge.tempId
                if _eid not in _added_legs:
                    fillet_items_legs.add(_edge)
                    _added_legs.add(_eid)
    if fillet_items_legs.count > 0:
        fillet_inp_legs.addConstantRadiusEdgeSet(fillet_items_legs, adsk.core.ValueInput.createByString("0.05 in"), True)
        fillet_feat_legs = legs_c.features.filletFeatures.add(fillet_inp_legs)
        fillet_feat_legs.name = "LegFillet"

    # ── FIT VIEW ──────────────────────────────────────────────────
    sp.apply_appearance("white oak")
    sp.apply_appearance("teak", bodies=["Leg_NL (1)", "Leg_NR", "Leg_FR", "Leg_FL"])

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
