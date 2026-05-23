"""Generated from capture_design — Pergola v8
NOTE: Auto-generated. Features marked TODO need manual review."""
import adsk.core, adsk.fusion, math
from helpers import sp


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters

    # ── PARAMETERS ────────────────────────────────────────────────
    for name, expr, unit, comment in [
        ("yard_w", "240 in", "in", "yard width"),
        ("yard_d", "240 in", "in", "yard depth"),
        ("perg_x", "45 in", "in", "x cord of the pergola"),
        ("perg_w", "90 in", "ft", "pergola width"),
        ("deck_d", "70 in", "in", "deck depth"),
        ("perg_d", "60 in", "in", "pergola_depth"),
        ("perg_height", "168 in", "in", "pergola height"),
        ("deck_height", "60 in", "in", "deck height"),
        ("post_w", "3.5 in", "in", "post width"),
        ("top_beam_height", "6 in", "in", "top_beam_height"),
        ("top_beam_width", "3.5 in", "in", "top beam width"),
        ("top_beam_side", "12 in", "in", "top beam side extrusion"),
        ("stretcher_offset", "0.1 in", "in", "distance from stretcher to top beam"),
        ("rafter_w", "1.5 in", "in", "rafter width"),
        ("rafter_h", "3.5 in", "in", "rafter height"),
        ("rafter_offset", "2 in", "in", "how deep rafter connect with stretcher"),
        ("floor_width", "4 in", "in", "deck floor wid"),
        ("floor_thickness", "1 in", "in", "deck floor thickness"),
        ("floor_gap", "0.1 in", "in", "deck floor gap "),
        ("rafter_count", "10", "", "number of rafts "),
        ("rafter_x_offset", "8 in", "in", "distance of rafter to the edge "),
        ("stretcher_h", "5.5 in", "in", "stretcher height"),
        ("scarf_length", "13 in", "in", "scarf_joint length"),
        ("scarf_notch", "( 5 / 8 ) * 1 in", "in", ""),
        ("post_e_length", "70 in", "in", ""),
        ("brace_dist", "15 in", "in", ""),
        ("beam_recess", "50 mm", "mm", ""),
    ]:
        params.add(name, adsk.core.ValueInput.createByString(expr), unit, comment)

    for name, expr, unit, comment in [
        ("deck_w", "perg_w + perg_x", "in", "deck width"),
        ("post_height", "perg_height - top_beam_height", "in", "post height"),
        ("top_beam_length", "perg_w", "in", "top beam length"),
        ("stretcher_w", "post_w", "in", "stretcher width"),
        ("stretcher_height", "post_height - stretcher_w - stretcher_offset", "in", "height of the stretcher"),
        ("stretcher_length", "deck_w", "in", "stretcher length"),
        ("rafter_length", "( perg_d + post_w ) * 1.15", "in", "rafter length"),
        ("scarf_tilt", "asin(scarf_notch / scarf_length)", "deg", ""),
    ]:
        params.add(name, adsk.core.ValueInput.createByString(expr), unit, comment)

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

    def find_body(name, search_comp=None):
        if search_comp:
            for i in range(search_comp.bRepBodies.count):
                if search_comp.bRepBodies.item(i).name == name:
                    return search_comp.bRepBodies.item(i)
            return None  # not found in specified component
        for i in range(root.bRepBodies.count):
            if root.bRepBodies.item(i).name == name:
                return root.bRepBodies.item(i)
        for occ in root.allOccurrences:
            for i in range(occ.bRepBodies.count):
                if occ.bRepBodies.item(i).name == name:
                    return occ.bRepBodies.item(i)
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
        # Search proxied bodies by name for root-context faces
        bodies = []
        if body:
            bn = body.name
            for i in range(root.bRepBodies.count):
                if root.bRepBodies.item(i).name == bn: bodies.append(root.bRepBodies.item(i))
            for _occ in root.allOccurrences:
                for i in range(_occ.bRepBodies.count):
                    if _occ.bRepBodies.item(i).name == bn: bodies.append(_occ.bRepBodies.item(i))
            if not bodies: bodies = [body]
        if not bodies:
            # No body given — search all bodies via occurrence proxies
            bodies = [root.bRepBodies.item(i) for i in range(root.bRepBodies.count)]
            for _occ in root.allOccurrences:
                bodies.extend([_occ.bRepBodies.item(i) for i in range(_occ.bRepBodies.count)])
        best, best_d = None, 1e10
        def _search_faces(bl):
            nonlocal best, best_d
            for _b in bl:
                for i in range(_b.faces.count):
                    f = _b.faces.item(i)
                    if isinstance(f.geometry, adsk.core.Plane):
                        n = f.geometry.normal
                        if nx or ny or nz:
                            if abs(abs(n.x*nx+n.y*ny+n.z*nz) - 1.0) > 0.1: continue
                        p = f.pointOnFace
                        d = abs(p.x - px) + abs(p.y - py) + abs(p.z - pz)
                        if d < best_d: best, best_d = f, d
        _search_faces(bodies)
        # Fallback: search all bodies if name-based search found no face
        if best is None and body:
            _all = [root.bRepBodies.item(i) for i in range(root.bRepBodies.count)]
            for _occ in root.allOccurrences:
                _all.extend([_occ.bRepBodies.item(i) for i in range(_occ.bRepBodies.count)])
            _search_faces(_all)
        return best

    def find_face_in_comp(comp, px, py, pz, nx=0, ny=0, nz=0):
        best, best_d = None, 1e10
        for bi in range(comp.bRepBodies.count):
            _b = comp.bRepBodies.item(bi)
            for fi in range(_b.faces.count):
                f = _b.faces.item(fi)
                if isinstance(f.geometry, adsk.core.Plane):
                    n = f.geometry.normal
                    if nx or ny or nz:
                        if abs(abs(n.x*nx+n.y*ny+n.z*nz) - 1.0) > 0.1: continue
                    p = f.pointOnFace
                    d = abs(p.x - px) + abs(p.y - py) + abs(p.z - pz)
                    if d < best_d: best, best_d = f, d
        return best

    def combine(comp, target, tools, op, keep, name="Comb"):
        if target is None: return None  # no valid target body
        coll = adsk.core.ObjectCollection.create()
        for b in (tools if isinstance(tools, list) else [tools]):
            if b is not None: coll.add(b)
        if coll.count == 0: return None  # no valid tool bodies
        try:
            inp = comp.features.combineFeatures.createInput(target, coll)
            inp.operation = op
            inp.isKeepToolBodies = keep
            f = comp.features.combineFeatures.add(inp)
            f.name = name
            return f
        except RuntimeError:
            pass
        # Cross-component fallback: proxy bodies via occurrences, combine at root
        def _proxy(b):
            pc = b.parentComponent
            for _occ in root.allOccurrences:
                if _occ.component.name == pc.name:
                    for i in range(_occ.bRepBodies.count):
                        if _occ.bRepBodies.item(i).name == b.name: return _occ.bRepBodies.item(i)
            return b
        try:
            pt = _proxy(target)
            pcoll = adsk.core.ObjectCollection.create()
            for b in (tools if isinstance(tools, list) else [tools]):
                if b is not None: pcoll.add(_proxy(b))
            if pcoll.count == 0: return None
            inp = root.features.combineFeatures.createInput(pt, pcoll)
            inp.operation = op
            inp.isKeepToolBodies = keep
            f = root.features.combineFeatures.add(inp)
            f.name = name
            return f
        except RuntimeError:
            return None  # combine failed even with proxied bodies

    def mirror_feats(comp, entities, plane, name="Mir"):
        coll = adsk.core.ObjectCollection.create()
        for e in entities: coll.add(e)
        inp = comp.features.mirrorFeatures.createInput(coll, plane)
        inp.computeOption = adsk.fusion.PatternComputeOptions.AdjustPatternCompute
        m = comp.features.mirrorFeatures.add(inp)
        m.name = name
        return m

    # ── TIMELINE ──────────────────────────────────────────────────

    # [0] ComponentCreation: Surranding
    comp = root
    Surranding_occ = comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    Surranding_occ.component.name = "Surranding"
    Surranding_c = Surranding_occ.component

    # [1] Sketch: Sketch1
    comp = Surranding_c
    Sketch1_Surranding = comp.sketches.add(root.xZConstructionPlane)
    Sketch1_Surranding.name = "Sketch1"
    _cap_xd = (1.0, 0.0, 0.0)
    _cap_yd = (0.0, 0.0, -1.0)
    _act_xd = Sketch1_Surranding.xDirection
    _act_yd = Sketch1_Surranding.yDirection
    _m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z
    _m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z
    _m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z
    _m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z
    _w0, _h0 = ev("yard_w"), ev("360 in")
    _x0c, _y0c = ev("0 cm"), ev("-914.4 cm")
    _c1x, _c1y = _x0c*_m00 + _y0c*_m01, _x0c*_m10 + _y0c*_m11
    _c2x, _c2y = (_x0c+_w0)*_m00 + (_y0c+_h0)*_m01, (_x0c+_w0)*_m10 + (_y0c+_h0)*_m11
    x0, y0 = min(_c1x, _c2x), min(_c1y, _c2y)
    w, h = abs(_c2x - _c1x), abs(_c2y - _c1y)
    rect = Sketch1_Surranding.sketchCurves.sketchLines.addTwoPointRectangle(
        P(x0, y0, 0), P(x0 + w, y0 + h, 0))
    gc = Sketch1_Surranding.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    d = Sketch1_Surranding.sketchDimensions
    d.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        H, P(x0 + w/2, y0 - 1, 0)).parameter.expression = "yard_w"
    d.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        V, P(x0 + w + 1, y0 + h/2, 0)).parameter.expression = "360 in"
    _hd = abs(x0)
    if _hd > 0.01:
        d.addDistanceDimension(Sketch1_Surranding.originPoint, rect[0].startSketchPoint,
            H, P(x0/2, y0 - 2, 0)).parameter.expression = f"{round(_hd, 4)} cm"
    _vd = abs(y0)
    if _vd > 0.01:
        d.addDistanceDimension(Sketch1_Surranding.originPoint, rect[0].startSketchPoint,
            V, P(x0 - 1, y0/2, 0)).parameter.expression = f"{round(_vd, 4)} cm"
    Sketch1_Surranding_prof = Sketch1_Surranding.profiles.item(0)

    # [2] Extrude: Extrude1
    comp = Surranding_c
    _cx = (1.0, 0.0, 0.0)
    _cy = (0.0, 0.0, -1.0)
    _ax = Sketch1_Surranding.xDirection
    _ay = Sketch1_Surranding.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Match profile by bbox (transformed): (0.0, -914.4) to (609.6, 0.0)
    _t1 = (0.0*_m00 + -914.4*_m01, 0.0*_m10 + -914.4*_m11)
    _t2 = (609.6*_m00 + 0.0*_m01, 609.6*_m10 + 0.0*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch1_Surranding.profiles.count):
        _bb = Sketch1_Surranding.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    inp = comp.features.extrudeFeatures.createInput(Sketch1_Surranding.profiles.item(_best_pi), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("12 in"))
    Extrude1 = comp.features.extrudeFeatures.add(inp)
    Extrude1.name = "Extrude1"
    wall_Surranding = Extrude1.bodies.item(0)
    wall_Surranding.name = "wall"

    # Body-relative ref: ground depends on wall
    ref_wall = find_body("wall")
    ref_wall_bb = ref_wall.boundingBox

    # [3] Sketch: Sketch2
    comp = Surranding_c
    Sketch2_Surranding = comp.sketches.add(root.xYConstructionPlane)
    Sketch2_Surranding.name = "Sketch2"
    _cap_xd = (1.0, 0.0, 0.0)
    _cap_yd = (0.0, 1.0, 0.0)
    _act_xd = Sketch2_Surranding.xDirection
    _act_yd = Sketch2_Surranding.yDirection
    _m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z
    _m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z
    _m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z
    _m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z
    _w0, _h0 = ev("yard_d"), ev("609.6 cm")
    _x0c, _y0c = ev("0 cm"), ev("-609.6 cm")
    _c1x, _c1y = _x0c*_m00 + _y0c*_m01, _x0c*_m10 + _y0c*_m11
    _c2x, _c2y = (_x0c+_w0)*_m00 + (_y0c+_h0)*_m01, (_x0c+_w0)*_m10 + (_y0c+_h0)*_m11
    x0, y0 = min(_c1x, _c2x), min(_c1y, _c2y)
    w, h = abs(_c2x - _c1x), abs(_c2y - _c1y)
    rect = Sketch2_Surranding.sketchCurves.sketchLines.addTwoPointRectangle(
        P(x0, y0, 0), P(x0 + w, y0 + h, 0))
    gc = Sketch2_Surranding.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    d = Sketch2_Surranding.sketchDimensions
    d.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        H, P(x0 + w/2, y0 - 1, 0)).parameter.expression = "yard_d"
    d.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        V, P(x0 + w + 1, y0 + h/2, 0)).parameter.expression = "609.6 cm"
    _hd = abs(x0)
    if _hd > 0.01:
        d.addDistanceDimension(Sketch2_Surranding.originPoint, rect[0].startSketchPoint,
            H, P(x0/2, y0 - 2, 0)).parameter.expression = f"{round(_hd, 4)} cm"
    _vd = abs(y0)
    if _vd > 0.01:
        d.addDistanceDimension(Sketch2_Surranding.originPoint, rect[0].startSketchPoint,
            V, P(x0 - 1, y0/2, 0)).parameter.expression = f"{round(_vd, 4)} cm"
    Sketch2_Surranding_prof = Sketch2_Surranding.profiles.item(0)

    # [4] Extrude: Extrude2
    comp = Surranding_c
    _cx = (1.0, 0.0, 0.0)
    _cy = (0.0, 1.0, 0.0)
    _ax = Sketch2_Surranding.xDirection
    _ay = Sketch2_Surranding.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Match profile by bbox (transformed): (0.0, -609.6) to (609.6, 0.0)
    _t1 = (0.0*_m00 + -609.6*_m01, 0.0*_m10 + -609.6*_m11)
    _t2 = (609.6*_m00 + 0.0*_m01, 609.6*_m10 + 0.0*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch2_Surranding.profiles.count):
        _bb = Sketch2_Surranding.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    inp = comp.features.extrudeFeatures.createInput(Sketch2_Surranding.profiles.item(_best_pi), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("-4 in"))
    Extrude2 = comp.features.extrudeFeatures.add(inp)
    Extrude2.name = "Extrude2"
    ground_Surranding = Extrude2.bodies.item(0)
    ground_Surranding.name = "ground"

    # Body-relative reference: posts sit on ground
    ref_ground = find_body("ground")
    ref_ground_bb = ref_ground.boundingBox

    # [5] ComponentCreation: posts
    comp = root
    posts_occ = comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    posts_occ.component.name = "posts"
    posts_c = posts_occ.component

    # [6] Sketch: Sketch1
    comp = posts_c
    Sketch1_posts = comp.sketches.add(find_face_near(ground_Surranding, 304.8, -304.8, 0.0, 0.0, 0.0, 1.0))
    Sketch1_posts.name = "Sketch1"
    lns = Sketch1_posts.sketchCurves.sketchLines
    # Coordinate transform: captured sketch axes -> actual sketch axes
    _cap_xd = (-1.0, 0.0, 0.0)
    _cap_yd = (0.0, -1.0, 0.0)
    _act_xd = Sketch1_posts.xDirection
    _act_yd = Sketch1_posts.yDirection
    _m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z
    _m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z
    _m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z
    _m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z
    def _xf(sx, sy):
        return (sx * _m00 + sy * _m01, sx * _m10 + sy * _m11)
    _proj_pts = []  # [(x, y, sketchPoint), ...]
    _proj_curves = []  # [(sx, sy, ex, ey, curve), ...]
    for _ci in range(Sketch1_posts.sketchCurves.count):
        _c = Sketch1_posts.sketchCurves.item(_ci)
        if _c.isReference:
            for _sp in [_c.startSketchPoint, _c.endSketchPoint]:
                _g = _sp.geometry
                _proj_pts.append((_g.x, _g.y, _sp))
            _s, _e = _c.startSketchPoint.geometry, _c.endSketchPoint.geometry
            _proj_curves.append((_s.x, _s.y, _e.x, _e.y, _c))

    _fallback_pts = {}
    def _nearest_proj(x, y):
        best, best_d = None, 1e10
        for _px, _py, _sp in _proj_pts:
            _d = abs(_px - x) + abs(_py - y)
            if _d < best_d: best, best_d = _sp, _d
        if best_d > 5.0: best = None
        if best is None:
            _fk = (round(x,2), round(y,2))
            best = _fallback_pts.get(_fk)
        if best is None:
            best = Sketch1_posts.sketchPoints.add(P(x, y, 0))
        return best

    def _nearest_proj_curve(sx, sy, ex, ey):
        best, best_d = None, 1e10
        for _sx, _sy, _ex, _ey, _c in _proj_curves:
            _d = min(abs(_sx-sx)+abs(_sy-sy)+abs(_ex-ex)+abs(_ey-ey),
                    abs(_sx-ex)+abs(_sy-ey)+abs(_ex-sx)+abs(_ey-sy))
            if _d < best_d: best, best_d = _c, _d
        if best_d > 10.0: best = None
        if best is None:
            _sk = (round(sx,2), round(sy,2))
            _ek = (round(ex,2), round(ey,2))
            _sp = _fallback_pts.get(_sk)
            _ep = _fallback_pts.get(_ek)
            if _sp and _ep:
                best = Sketch1_posts.sketchCurves.sketchLines.addByTwoPoints(_sp, _ep)
            elif _sp:
                best = Sketch1_posts.sketchCurves.sketchLines.addByTwoPoints(_sp, P(ex, ey, 0))
                _fallback_pts[_ek] = best.endSketchPoint
            elif _ep:
                best = Sketch1_posts.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), _ep)
                _fallback_pts[_sk] = best.startSketchPoint
            else:
                best = Sketch1_posts.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), P(ex, ey, 0))
                _fallback_pts[_sk] = best.startSketchPoint
                _fallback_pts[_ek] = best.endSketchPoint
            try: Sketch1_posts.geometricConstraints.addFix(best)
            except: pass
        return best
    _pcurve_0 = _nearest_proj_curve(*_xf(0.0, 609.6), *_xf(-609.6, 609.6))
    _pcurve_1 = _nearest_proj_curve(*_xf(-609.6, 609.6), *_xf(-609.6, 0.0))
    _pcurve_2 = _nearest_proj_curve(*_xf(-609.6, 0.0), *_xf(0.0, 0.0))
    _pcurve_3 = _nearest_proj_curve(*_xf(0.0, 0.0), *_xf(0.0, 609.6))
    _cs_0 = _xf(0.0, 0.0)
    _ce_0 = _xf(-114.3, 0.0)
    ln0 = lns.addByTwoPoints(P(_cs_0[0], _cs_0[1], 0), P(_ce_0[0], _ce_0[1], 0))
    _cs_1 = _xf(-114.3, 0.0)
    _ce_1 = _xf(-114.3, 168.91)
    ln1 = lns.addByTwoPoints(ln0.endSketchPoint, P(_ce_1[0], _ce_1[1], 0))
    _cs_2 = _xf(-114.3, 168.91)
    _ce_2 = _xf(-123.19, 168.91)
    ln2 = lns.addByTwoPoints(ln1.endSketchPoint, P(_ce_2[0], _ce_2[1], 0))
    _cs_3 = _xf(-123.19, 168.91)
    _ce_3 = _xf(-123.19, 177.8)
    ln3 = lns.addByTwoPoints(ln2.endSketchPoint, P(_ce_3[0], _ce_3[1], 0))
    _cs_4 = _xf(-123.19, 177.8)
    _ce_4 = _xf(-114.3, 177.8)
    ln4 = lns.addByTwoPoints(ln3.endSketchPoint, P(_ce_4[0], _ce_4[1], 0))
    _cs_5 = _xf(-114.3, 177.8)
    _ce_5 = _xf(-114.3, 168.91)
    ln5 = lns.addByTwoPoints(ln4.endSketchPoint, ln1.endSketchPoint)
    _cs_6 = _xf(-123.19, 168.91)
    _ce_6 = _xf(-334.01, 168.91)
    ln6 = lns.addByTwoPoints(ln2.endSketchPoint, P(_ce_6[0], _ce_6[1], 0))
    _cs_7 = _xf(-334.01, 168.91)
    _ce_7 = _xf(-342.9, 168.91)
    ln7 = lns.addByTwoPoints(ln6.endSketchPoint, P(_ce_7[0], _ce_7[1], 0))
    _cs_8 = _xf(-342.9, 168.91)
    _ce_8 = _xf(-342.9, 177.8)
    ln8 = lns.addByTwoPoints(ln7.endSketchPoint, P(_ce_8[0], _ce_8[1], 0))
    _cs_9 = _xf(-342.9, 177.8)
    _ce_9 = _xf(-334.01, 177.8)
    ln9 = lns.addByTwoPoints(ln8.endSketchPoint, P(_ce_9[0], _ce_9[1], 0))
    _cs_10 = _xf(-334.01, 177.8)
    _ce_10 = _xf(-334.01, 168.91)
    ln10 = lns.addByTwoPoints(ln9.endSketchPoint, ln6.endSketchPoint)
    d = Sketch1_posts.sketchDimensions
    try:
        d.addDistanceDimension(Sketch1_posts.originPoint, ln0.endSketchPoint,
            adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, P(0, 0, 0)).parameter.expression = "perg_x"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln0.endSketchPoint, ln1.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "deck_d - post_w"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln1.endSketchPoint, ln2.endSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "post_w"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln4.endSketchPoint, ln1.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "post_w"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln2.endSketchPoint, ln6.endSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "perg_w - 2 * post_w"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln6.endSketchPoint, ln7.endSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "post_w"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln9.endSketchPoint, ln6.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "post_w"
    except: pass  # skip if already constrained
    gc = Sketch1_posts.geometricConstraints
    try: gc.addPerpendicular(ln0, _pcurve_3)
    except: pass
    try: gc.addPerpendicular(ln1, ln0)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln2)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln3)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln4)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln5)
    except: pass
    try: gc.addPerpendicular(ln6, ln3)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln7)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln8)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln9)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln10)
    except: pass
    Sketch1_posts_prof = Sketch1_posts.profiles.item(0)  # 3 profile(s)

    # [7] Extrude: Extrude1
    comp = posts_c
    _cx = (-1.0, 0.0, 0.0)
    _cy = (0.0, -1.0, 0.0)
    _ax = Sketch1_posts.xDirection
    _ay = Sketch1_posts.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Match profile by bbox (transformed): (-123.19, 168.91) to (-114.3, 177.8)
    _t1 = (-123.19*_m00 + 168.91*_m01, -123.19*_m10 + 168.91*_m11)
    _t2 = (-114.3*_m00 + 177.8*_m01, -114.3*_m10 + 177.8*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch1_posts.profiles.count):
        _bb = Sketch1_posts.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    inp = comp.features.extrudeFeatures.createInput(Sketch1_posts.profiles.item(_best_pi), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("post_height"))
    Extrude1 = comp.features.extrudeFeatures.add(inp)
    Extrude1.name = "Extrude1"
    post1_posts = Extrude1.bodies.item(0)
    post1_posts.name = "post1"

    # [8] Sketch: Sketch3
    comp = posts_c
    Sketch3_posts = comp.sketches.add(find_face_near(post1_posts, 118.745, -176.3183, 411.48, 0.0, 0.0, 1.0))
    Sketch3_posts.name = "Sketch3"
    lns = Sketch3_posts.sketchCurves.sketchLines
    # Coordinate transform: captured sketch axes -> actual sketch axes
    _cap_xd = (-1.0, 0.0, 0.0)
    _cap_yd = (0.0, -1.0, 0.0)
    _act_xd = Sketch3_posts.xDirection
    _act_yd = Sketch3_posts.yDirection
    _m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z
    _m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z
    _m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z
    _m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z
    def _xf(sx, sy):
        return (sx * _m00 + sy * _m01, sx * _m10 + sy * _m11)
    _proj_pts = []  # [(x, y, sketchPoint), ...]
    _proj_curves = []  # [(sx, sy, ex, ey, curve), ...]
    for _ci in range(Sketch3_posts.sketchCurves.count):
        _c = Sketch3_posts.sketchCurves.item(_ci)
        if _c.isReference:
            for _sp in [_c.startSketchPoint, _c.endSketchPoint]:
                _g = _sp.geometry
                _proj_pts.append((_g.x, _g.y, _sp))
            _s, _e = _c.startSketchPoint.geometry, _c.endSketchPoint.geometry
            _proj_curves.append((_s.x, _s.y, _e.x, _e.y, _c))

    _fallback_pts = {}
    def _nearest_proj(x, y):
        best, best_d = None, 1e10
        for _px, _py, _sp in _proj_pts:
            _d = abs(_px - x) + abs(_py - y)
            if _d < best_d: best, best_d = _sp, _d
        if best_d > 5.0: best = None
        if best is None:
            _fk = (round(x,2), round(y,2))
            best = _fallback_pts.get(_fk)
        if best is None:
            best = Sketch3_posts.sketchPoints.add(P(x, y, 0))
        return best

    def _nearest_proj_curve(sx, sy, ex, ey):
        best, best_d = None, 1e10
        for _sx, _sy, _ex, _ey, _c in _proj_curves:
            _d = min(abs(_sx-sx)+abs(_sy-sy)+abs(_ex-ex)+abs(_ey-ey),
                    abs(_sx-ex)+abs(_sy-ey)+abs(_ex-sx)+abs(_ey-sy))
            if _d < best_d: best, best_d = _c, _d
        if best_d > 10.0: best = None
        if best is None:
            _sk = (round(sx,2), round(sy,2))
            _ek = (round(ex,2), round(ey,2))
            _sp = _fallback_pts.get(_sk)
            _ep = _fallback_pts.get(_ek)
            if _sp and _ep:
                best = Sketch3_posts.sketchCurves.sketchLines.addByTwoPoints(_sp, _ep)
            elif _sp:
                best = Sketch3_posts.sketchCurves.sketchLines.addByTwoPoints(_sp, P(ex, ey, 0))
                _fallback_pts[_ek] = best.endSketchPoint
            elif _ep:
                best = Sketch3_posts.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), _ep)
                _fallback_pts[_sk] = best.startSketchPoint
            else:
                best = Sketch3_posts.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), P(ex, ey, 0))
                _fallback_pts[_sk] = best.startSketchPoint
                _fallback_pts[_ek] = best.endSketchPoint
            try: Sketch3_posts.geometricConstraints.addFix(best)
            except: pass
        return best
    _pcurve_0 = _nearest_proj_curve(*_xf(-114.3, 177.8), *_xf(-123.19, 177.8))
    _pcurve_1 = _nearest_proj_curve(*_xf(-123.19, 177.8), *_xf(-123.19, 168.91))
    _pcurve_2 = _nearest_proj_curve(*_xf(-123.19, 168.91), *_xf(-114.3, 168.91))
    _pcurve_3 = _nearest_proj_curve(*_xf(-114.3, 168.91), *_xf(-114.3, 177.8))
    _cs_0 = _xf(-114.3, 168.91)
    _ce_0 = _xf(-114.3, 171.8733)
    ln0 = lns.addByTwoPoints(P(_cs_0[0], _cs_0[1], 0), P(_ce_0[0], _ce_0[1], 0))
    _cs_1 = _xf(-114.3, 171.8733)
    _ce_1 = _xf(-123.19, 171.8733)
    ln1 = lns.addByTwoPoints(ln0.endSketchPoint, P(_ce_1[0], _ce_1[1], 0))
    _cs_2 = _xf(-123.19, 171.8733)
    _ce_2 = _xf(-123.19, 174.8367)
    ln2 = lns.addByTwoPoints(ln1.endSketchPoint, P(_ce_2[0], _ce_2[1], 0))
    _cs_3 = _xf(-123.19, 174.8367)
    _ce_3 = _xf(-114.3, 174.8367)
    ln3 = lns.addByTwoPoints(ln2.endSketchPoint, P(_ce_3[0], _ce_3[1], 0))
    _cs_4 = _xf(-114.3, 174.8367)
    _ce_4 = _xf(-114.3, 171.8733)
    ln4 = lns.addByTwoPoints(ln3.endSketchPoint, ln0.endSketchPoint)
    d = Sketch3_posts.sketchDimensions
    try:
        d.addDistanceDimension(_nearest_proj(*_xf(-114.3, 168.91)), ln0.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "post_w / 3"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln0.endSketchPoint, ln1.endSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "post_w"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln3.endSketchPoint, ln0.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "post_w / 3"
    except: pass  # skip if already constrained
    gc = Sketch3_posts.geometricConstraints
    try: gc.addPerpendicular(ln0, _pcurve_2)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln1)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln2)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln3)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln4)
    except: pass
    Sketch3_posts_prof = Sketch3_posts.profiles.item(0)  # 3 profile(s)

    # [9] Extrude: Extrude3
    comp = posts_c
    _cx = (-1.0, 0.0, 0.0)
    _cy = (0.0, -1.0, 0.0)
    _ax = Sketch3_posts.xDirection
    _ay = Sketch3_posts.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Match profile by bbox (transformed): (-123.19, 171.8733) to (-114.3, 174.8367)
    _t1 = (-123.19*_m00 + 171.8733*_m01, -123.19*_m10 + 171.8733*_m11)
    _t2 = (-114.3*_m00 + 174.8367*_m01, -114.3*_m10 + 174.8367*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch3_posts.profiles.count):
        _bb = Sketch3_posts.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    inp = comp.features.extrudeFeatures.createInput(Sketch3_posts.profiles.item(_best_pi), JOIN)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("top_beam_height * 2 / 3"))
    inp.participantBodies = [post1_posts]
    Extrude3 = comp.features.extrudeFeatures.add(inp)
    Extrude3.name = "Extrude3"
    post1_posts = Extrude3.bodies.item(0)
    post1_posts.name = "post1"

    # [10] ConstructionPlane: Plane2
    comp = posts_c
    # BRepFace base → computed offset from origin [118.745, -173.355, 243.84]
    Plane2_posts = off_plane(comp, comp.xYConstructionPlane, "243.84 cm", "Plane2")

    # [11] Sketch: Sketch5
    comp = posts_c
    Sketch5_posts = comp.sketches.add(Plane2_posts)
    Sketch5_posts.name = "Sketch5"
    lns = Sketch5_posts.sketchCurves.sketchLines
    # Coordinate transform: captured sketch axes -> actual sketch axes
    _cap_xd = (1.0, 0.0, 0.0)
    _cap_yd = (0.0, 1.0, 0.0)
    _act_xd = Sketch5_posts.xDirection
    _act_yd = Sketch5_posts.yDirection
    _m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z
    _m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z
    _m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z
    _m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z
    def _xf(sx, sy):
        return (sx * _m00 + sy * _m01, sx * _m10 + sy * _m11)
    # Intersect body 'post1' with sketch plane
    _bodies_post1 = []
    for _bi in range(comp.bRepBodies.count):
        if comp.bRepBodies.item(_bi).name == "post1":
            _bodies_post1.append(comp.bRepBodies.item(_bi))
    if not _bodies_post1:
        for _occ in root.allOccurrences:
            for _bi in range(_occ.bRepBodies.count):
                if _occ.bRepBodies.item(_bi).name == "post1":
                    _bodies_post1.append(_occ.bRepBodies.item(_bi))
    if _bodies_post1: _proj_body_post1 = Sketch5_posts.intersectWithSketchPlane(_bodies_post1)
    _proj_pts = []  # [(x, y, sketchPoint), ...]
    _proj_curves = []  # [(sx, sy, ex, ey, curve), ...]
    for _ci in range(Sketch5_posts.sketchCurves.count):
        _c = Sketch5_posts.sketchCurves.item(_ci)
        if _c.isReference:
            for _sp in [_c.startSketchPoint, _c.endSketchPoint]:
                _g = _sp.geometry
                _proj_pts.append((_g.x, _g.y, _sp))
            _s, _e = _c.startSketchPoint.geometry, _c.endSketchPoint.geometry
            _proj_curves.append((_s.x, _s.y, _e.x, _e.y, _c))

    _fallback_pts = {}
    def _nearest_proj(x, y):
        best, best_d = None, 1e10
        for _px, _py, _sp in _proj_pts:
            _d = abs(_px - x) + abs(_py - y)
            if _d < best_d: best, best_d = _sp, _d
        if best_d > 5.0: best = None
        if best is None:
            _fk = (round(x,2), round(y,2))
            best = _fallback_pts.get(_fk)
        if best is None:
            best = Sketch5_posts.sketchPoints.add(P(x, y, 0))
        return best

    def _nearest_proj_curve(sx, sy, ex, ey):
        best, best_d = None, 1e10
        for _sx, _sy, _ex, _ey, _c in _proj_curves:
            _d = min(abs(_sx-sx)+abs(_sy-sy)+abs(_ex-ex)+abs(_ey-ey),
                    abs(_sx-ex)+abs(_sy-ey)+abs(_ex-sx)+abs(_ey-sy))
            if _d < best_d: best, best_d = _c, _d
        if best_d > 10.0: best = None
        if best is None:
            _sk = (round(sx,2), round(sy,2))
            _ek = (round(ex,2), round(ey,2))
            _sp = _fallback_pts.get(_sk)
            _ep = _fallback_pts.get(_ek)
            if _sp and _ep:
                best = Sketch5_posts.sketchCurves.sketchLines.addByTwoPoints(_sp, _ep)
            elif _sp:
                best = Sketch5_posts.sketchCurves.sketchLines.addByTwoPoints(_sp, P(ex, ey, 0))
                _fallback_pts[_ek] = best.endSketchPoint
            elif _ep:
                best = Sketch5_posts.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), _ep)
                _fallback_pts[_sk] = best.startSketchPoint
            else:
                best = Sketch5_posts.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), P(ex, ey, 0))
                _fallback_pts[_sk] = best.startSketchPoint
                _fallback_pts[_ek] = best.endSketchPoint
            try: Sketch5_posts.geometricConstraints.addFix(best)
            except: pass
        return best
    _pcurve_0 = _nearest_proj_curve(*_xf(114.3, -168.91), *_xf(114.3, -177.8))
    _pcurve_1 = _nearest_proj_curve(*_xf(114.3, -177.8), *_xf(123.19, -177.8))
    _pcurve_2 = _nearest_proj_curve(*_xf(123.19, -177.8), *_xf(123.19, -168.91))
    _pcurve_3 = _nearest_proj_curve(*_xf(123.19, -168.91), *_xf(114.3, -168.91))
    _cs_4 = _xf(123.19, -177.8)
    _ce_4 = _xf(118.745, -177.8)
    _pp_4s = _nearest_proj(_cs_4[0], _cs_4[1])
    _pg_4s = _pp_4s.geometry
    _dx_4 = _ce_4[0] - _cs_4[0]
    _dy_4 = _ce_4[1] - _cs_4[1]
    ln4 = lns.addByTwoPoints(P(_pg_4s.x, _pg_4s.y, 0), P(_pg_4s.x + _dx_4, _pg_4s.y + _dy_4, 0))
    Sketch5_posts.geometricConstraints.addCoincident(ln4.startSketchPoint, _pp_4s)
    _cs_5 = _xf(118.745, -177.8)
    _ce_5 = _xf(118.745, -168.91)
    ln5 = lns.addByTwoPoints(ln4.endSketchPoint, P(_ce_5[0], _ce_5[1], 0))
    _cs_6 = _xf(123.19, -177.8)
    _ce_6 = _xf(123.19, -174.1488)
    _pp_6s = _nearest_proj(_cs_6[0], _cs_6[1])
    _pg_6s = _pp_6s.geometry
    _dx_6 = _ce_6[0] - _cs_6[0]
    _dy_6 = _ce_6[1] - _cs_6[1]
    ln6 = lns.addByTwoPoints(P(_pg_6s.x, _pg_6s.y, 0), P(_pg_6s.x + _dx_6, _pg_6s.y + _dy_6, 0))
    Sketch5_posts.geometricConstraints.addCoincident(ln6.startSketchPoint, _pp_6s)
    _cs_7 = _xf(123.19, -174.1488)
    _ce_7 = _xf(118.745, -174.1488)
    ln7 = lns.addByTwoPoints(ln6.endSketchPoint, P(_ce_7[0], _ce_7[1], 0))
    _cs_8 = _xf(118.745, -174.1488)
    _ce_8 = _xf(118.745, -172.5613)
    ln8 = lns.addByTwoPoints(ln7.endSketchPoint, P(_ce_8[0], _ce_8[1], 0))
    _cs_9 = _xf(118.745, -172.5613)
    _ce_9 = _xf(123.19, -172.5613)
    ln9 = lns.addByTwoPoints(ln8.endSketchPoint, P(_ce_9[0], _ce_9[1], 0))
    _cs_10 = _xf(123.19, -172.5613)
    _ce_10 = _xf(123.19, -174.1488)
    ln10 = lns.addByTwoPoints(ln9.endSketchPoint, ln6.endSketchPoint)
    d = Sketch5_posts.sketchDimensions
    try:
        d.addDistanceDimension(_nearest_proj(*_xf(123.19, -177.8)), ln4.endSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "post_w / 2"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln4.endSketchPoint, ln5.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "post_w"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(_nearest_proj(*_xf(123.19, -177.8)), ln6.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "( post_w - scarf_notch ) / 2"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln6.endSketchPoint, ln7.endSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "post_w / 2"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln9.endSketchPoint, ln6.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "scarf_notch"
    except: pass  # skip if already constrained
    gc = Sketch5_posts.geometricConstraints
    try: gc.addPerpendicular(ln4, _pcurve_2)
    except: pass
    try: gc.addPerpendicular(ln5, _pcurve_3)
    except: pass
    try: gc.addPerpendicular(ln6, ln4)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln7)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln8)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln9)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln10)
    except: pass
    Sketch5_posts_prof = Sketch5_posts.profiles.item(0)  # 4 profile(s)

    # [12] ConstructionPlane: Plane3
    comp = posts_c
    # No base plane captured — using last plane: Plane2_posts
    _angle_line = None
    for _ci in range(Sketch5_posts.sketchCurves.count):
        _c = Sketch5_posts.sketchCurves.item(_ci)
        _sl = adsk.fusion.SketchLine.cast(_c)
        if _sl:
            _s, _e = _sl.startSketchPoint.worldGeometry, _sl.endSketchPoint.worldGeometry
            if (abs(_s.x-118.7450)+abs(_s.y--177.8000)+abs(_s.z-243.8400) < 0.1 and abs(_e.x-118.7450)+abs(_e.y--168.9100)+abs(_e.z-243.8400) < 0.1) or (abs(_s.x-118.7450)+abs(_s.y--168.9100)+abs(_s.z-243.8400) < 0.1 and abs(_e.x-118.7450)+abs(_e.y--177.8000)+abs(_e.z-243.8400) < 0.1):
                _angle_line = _sl; break
    _pl_inp = comp.constructionPlanes.createInput()
    _pl_inp.setByAngle(_angle_line, adsk.core.ValueInput.createByString("90 deg - asin(scarf_notch / scarf_length)"), Plane2_posts)
    Plane3_posts = comp.constructionPlanes.add(_pl_inp)
    Plane3_posts.name = "Plane3"

    # [13] Extrude: Extrude5
    comp = posts_c
    _cx = (1.0, 0.0, 0.0)
    _cy = (0.0, 1.0, 0.0)
    _ax = Sketch5_posts.xDirection
    _ay = Sketch5_posts.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Match profile by bbox (transformed): (114.3, -177.8) to (118.745, -168.91)
    _t1 = (114.3*_m00 + -177.8*_m01, 114.3*_m10 + -177.8*_m11)
    _t2 = (118.745*_m00 + -168.91*_m01, 118.745*_m10 + -168.91*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch5_posts.profiles.count):
        _bb = Sketch5_posts.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    inp = comp.features.extrudeFeatures.createInput(Sketch5_posts.profiles.item(_best_pi), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("scarf_length"))
    Extrude5 = comp.features.extrudeFeatures.add(inp)
    Extrude5.name = "Extrude5"
    scarf1_posts = Extrude5.bodies.item(0)
    scarf1_posts.name = "scarf1"

    # [14] SplitBody: Split1
    comp = posts_c
    split_inp = comp.features.splitBodyFeatures.createInput(scarf1_posts, Plane3_posts, True)
    split_feat = comp.features.splitBodyFeatures.add(split_inp)
    split_feat.name = "Split1"
    # Rename 3 bodies by volume+position matching
    _all_comp_bodies = [comp.bRepBodies.item(_i) for _i in range(comp.bRepBodies.count)]
    for _ti, _tb in enumerate(_all_comp_bodies): _tb.name = f'__tmp_{_ti}'
    _expected_geo = [
        ("post1", 32787.7839, [114.3, -177.8, 0.0]),
        ("scarf1", 1071.5467, [114.3, -177.8, 243.84]),
        ("Body4", 233.2733, [117.1557, -177.8, 243.84]),
    ]
    _used = set()
    for _nm, _ev, _emin in _expected_geo:
        _best_i, _best_d = -1, 1e10
        for _bi, _b in enumerate(_all_comp_bodies):
            if _bi in _used: continue
            _d = abs(_b.volume - _ev)
            try:
                _bb = _b.boundingBox
                _d += abs(_bb.minPoint.x - _emin[0]) + abs(_bb.minPoint.y - _emin[1]) + abs(_bb.minPoint.z - _emin[2])
            except: pass
            if _d < _best_d: _best_i, _best_d = _bi, _d
        if _best_i >= 0:
            _all_comp_bodies[_best_i].name = _nm
            _used.add(_best_i)
    if comp.bRepBodies.count != 3:
        app.log(f'WARNING: Split body count mismatch: expected 3, got {comp.bRepBodies.count}')
        for _bi in range(comp.bRepBodies.count):
            app.log(f'  body[{_bi}]: {comp.bRepBodies.item(_bi).name} vol={round(comp.bRepBodies.item(_bi).volume, 2)}')
    post1_posts = find_body("post1", comp)
    post1_bb = post1_posts.boundingBox  # body-relative reference for upper post, wedges
    scarf1_posts = find_body("scarf1", comp)
    Body4_posts = find_body("Body4", comp)

    # [15] Sketch: Sketch6
    comp = posts_c
    Sketch6_posts = comp.sketches.add(find_face_near(Body4_posts, 118.745, -173.355, 243.84, 1.0, 0.0, 0.0))
    Sketch6_posts.name = "Sketch6"
    lns = Sketch6_posts.sketchCurves.sketchLines
    # Coordinate transform: captured sketch axes -> actual sketch axes
    _cap_xd = (0.0, 1.0, 0.0)
    _cap_yd = (0.0, 0.0, 1.0)
    _act_xd = Sketch6_posts.xDirection
    _act_yd = Sketch6_posts.yDirection
    _m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z
    _m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z
    _m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z
    _m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z
    def _xf(sx, sy):
        return (sx * _m00 + sy * _m01, sx * _m10 + sy * _m11)
    _proj_pts = []  # [(x, y, sketchPoint), ...]
    _proj_curves = []  # [(sx, sy, ex, ey, curve), ...]
    for _ci in range(Sketch6_posts.sketchCurves.count):
        _c = Sketch6_posts.sketchCurves.item(_ci)
        if _c.isReference:
            for _sp in [_c.startSketchPoint, _c.endSketchPoint]:
                _g = _sp.geometry
                _proj_pts.append((_g.x, _g.y, _sp))
            _s, _e = _c.startSketchPoint.geometry, _c.endSketchPoint.geometry
            _proj_curves.append((_s.x, _s.y, _e.x, _e.y, _c))

    _fallback_pts = {}
    def _nearest_proj(x, y):
        best, best_d = None, 1e10
        for _px, _py, _sp in _proj_pts:
            _d = abs(_px - x) + abs(_py - y)
            if _d < best_d: best, best_d = _sp, _d
        if best_d > 5.0: best = None
        if best is None:
            _fk = (round(x,2), round(y,2))
            best = _fallback_pts.get(_fk)
        if best is None:
            best = Sketch6_posts.sketchPoints.add(P(x, y, 0))
        return best

    def _nearest_proj_curve(sx, sy, ex, ey):
        best, best_d = None, 1e10
        for _sx, _sy, _ex, _ey, _c in _proj_curves:
            _d = min(abs(_sx-sx)+abs(_sy-sy)+abs(_ex-ex)+abs(_ey-ey),
                    abs(_sx-ex)+abs(_sy-ey)+abs(_ex-sx)+abs(_ey-sy))
            if _d < best_d: best, best_d = _c, _d
        if best_d > 10.0: best = None
        if best is None:
            _sk = (round(sx,2), round(sy,2))
            _ek = (round(ex,2), round(ey,2))
            _sp = _fallback_pts.get(_sk)
            _ep = _fallback_pts.get(_ek)
            if _sp and _ep:
                best = Sketch6_posts.sketchCurves.sketchLines.addByTwoPoints(_sp, _ep)
            elif _sp:
                best = Sketch6_posts.sketchCurves.sketchLines.addByTwoPoints(_sp, P(ex, ey, 0))
                _fallback_pts[_ek] = best.endSketchPoint
            elif _ep:
                best = Sketch6_posts.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), _ep)
                _fallback_pts[_sk] = best.startSketchPoint
            else:
                best = Sketch6_posts.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), P(ex, ey, 0))
                _fallback_pts[_sk] = best.startSketchPoint
                _fallback_pts[_ek] = best.endSketchPoint
            try: Sketch6_posts.geometricConstraints.addFix(best)
            except: pass
        return best
    _pcurve_0 = _nearest_proj_curve(*_xf(-177.8, 243.84), *_xf(-168.91, 243.84))
    _pcurve_1 = _nearest_proj_curve(*_xf(-168.91, 243.84), *_xf(-168.91, 276.86))
    _pcurve_2 = _nearest_proj_curve(*_xf(-168.91, 276.86), *_xf(-177.8, 276.86))
    _pcurve_3 = _nearest_proj_curve(*_xf(-177.8, 276.86), *_xf(-177.8, 243.84))
    _cs_0 = _xf(-177.8, 276.86)
    _ce_0 = _xf(-177.8, 260.35)
    ln0 = lns.addByTwoPoints(P(_cs_0[0], _cs_0[1], 0), P(_ce_0[0], _ce_0[1], 0))
    _cs_1 = _xf(-177.8, 260.35)
    _ce_1 = _xf(-168.91, 260.35)
    ln1 = lns.addByTwoPoints(ln0.endSketchPoint, P(_ce_1[0], _ce_1[1], 0))
    d = Sketch6_posts.sketchDimensions
    try:
        d.addDistanceDimension(_nearest_proj(*_xf(-177.8, 276.86)), ln0.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "scarf_length / 2"
    except: pass  # skip if already constrained
    gc = Sketch6_posts.geometricConstraints
    try: gc.addPerpendicular(ln0, _pcurve_2)
    except: pass
    try: gc.addMidPoint(ln1.endSketchPoint, _pcurve_1)
    except: pass
    Sketch6_posts_prof = Sketch6_posts.profiles.item(0)  # 2 profile(s)

    # [16] ConstructionPlane: Plane4
    comp = posts_c
    # No base plane captured — using last plane: Plane3_posts
    _angle_line = None
    for _ci in range(Sketch6_posts.sketchCurves.count):
        _c = Sketch6_posts.sketchCurves.item(_ci)
        _sl = adsk.fusion.SketchLine.cast(_c)
        if _sl:
            _s, _e = _sl.startSketchPoint.worldGeometry, _sl.endSketchPoint.worldGeometry
            if (abs(_s.x-118.7450)+abs(_s.y--177.8000)+abs(_s.z-260.3500) < 0.1 and abs(_e.x-118.7450)+abs(_e.y--168.9100)+abs(_e.z-260.3500) < 0.1) or (abs(_s.x-118.7450)+abs(_s.y--168.9100)+abs(_s.z-260.3500) < 0.1 and abs(_e.x-118.7450)+abs(_e.y--177.8000)+abs(_e.z-260.3500) < 0.1):
                _angle_line = _sl; break
    _pl_inp = comp.constructionPlanes.createInput()
    _pl_inp.setByAngle(_angle_line, adsk.core.ValueInput.createByString("-asin(scarf_notch / scarf_length)"), Plane3_posts)
    Plane4_posts = comp.constructionPlanes.add(_pl_inp)
    Plane4_posts.name = "Plane4"

    # [17] Sketch: Sketch7
    comp = posts_c
    # Native face sketch: Sketch7 (cross-body refs)
    _native_face = find_face_in_comp(comp, 116.8998, -177.8, 260.35, 0.0, -1.0, 0.0)
    if not _native_face: _native_face = find_face_near(find_body("scarf1"), 116.8998, -177.8, 260.35, 0.0, -1.0, 0.0)
    Sketch7_posts = comp.sketches.add(_native_face)
    Sketch7_posts.name = "Sketch7"
    lns = Sketch7_posts.sketchCurves.sketchLines
    # Coordinate transform: captured sketch axes -> actual sketch axes
    _cap_xd = (1.0, 0.0, 0.0)
    _cap_yd = (0.0, 0.0, 1.0)
    _act_xd = Sketch7_posts.xDirection
    _act_yd = Sketch7_posts.yDirection
    _m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z
    _m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z
    _m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z
    _m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z
    def _xf(sx, sy):
        return (sx * _m00 + sy * _m01, sx * _m10 + sy * _m11)
    # Intersect body 'Body4' with sketch plane
    _bodies_Body4 = []
    for _bi in range(comp.bRepBodies.count):
        if comp.bRepBodies.item(_bi).name == "Body4":
            _bodies_Body4.append(comp.bRepBodies.item(_bi))
    if not _bodies_Body4:
        for _occ in root.allOccurrences:
            for _bi in range(_occ.bRepBodies.count):
                if _occ.bRepBodies.item(_bi).name == "Body4":
                    _bodies_Body4.append(_occ.bRepBodies.item(_bi))
    if _bodies_Body4: _proj_body_Body4 = Sketch7_posts.intersectWithSketchPlane(_bodies_Body4)
    _proj_pts = []  # [(x, y, sketchPoint), ...]
    _proj_curves = []  # [(sx, sy, ex, ey, curve), ...]
    for _ci in range(Sketch7_posts.sketchCurves.count):
        _c = Sketch7_posts.sketchCurves.item(_ci)
        if _c.isReference:
            for _sp in [_c.startSketchPoint, _c.endSketchPoint]:
                _g = _sp.geometry
                _proj_pts.append((_g.x, _g.y, _sp))
            _s, _e = _c.startSketchPoint.geometry, _c.endSketchPoint.geometry
            _proj_curves.append((_s.x, _s.y, _e.x, _e.y, _c))

    _fallback_pts = {}
    def _nearest_proj(x, y):
        best, best_d = None, 1e10
        for _px, _py, _sp in _proj_pts:
            _d = abs(_px - x) + abs(_py - y)
            if _d < best_d: best, best_d = _sp, _d
        if best_d > 5.0: best = None
        if best is None:
            _fk = (round(x,2), round(y,2))
            best = _fallback_pts.get(_fk)
        if best is None:
            best = Sketch7_posts.sketchPoints.add(P(x, y, 0))
        return best

    def _nearest_proj_curve(sx, sy, ex, ey):
        best, best_d = None, 1e10
        for _sx, _sy, _ex, _ey, _c in _proj_curves:
            _d = min(abs(_sx-sx)+abs(_sy-sy)+abs(_ex-ex)+abs(_ey-ey),
                    abs(_sx-ex)+abs(_sy-ey)+abs(_ex-sx)+abs(_ey-sy))
            if _d < best_d: best, best_d = _c, _d
        if best_d > 10.0: best = None
        if best is None:
            _sk = (round(sx,2), round(sy,2))
            _ek = (round(ex,2), round(ey,2))
            _sp = _fallback_pts.get(_sk)
            _ep = _fallback_pts.get(_ek)
            if _sp and _ep:
                best = Sketch7_posts.sketchCurves.sketchLines.addByTwoPoints(_sp, _ep)
            elif _sp:
                best = Sketch7_posts.sketchCurves.sketchLines.addByTwoPoints(_sp, P(ex, ey, 0))
                _fallback_pts[_ek] = best.endSketchPoint
            elif _ep:
                best = Sketch7_posts.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), _ep)
                _fallback_pts[_sk] = best.startSketchPoint
            else:
                best = Sketch7_posts.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), P(ex, ey, 0))
                _fallback_pts[_sk] = best.startSketchPoint
                _fallback_pts[_ek] = best.endSketchPoint
            try: Sketch7_posts.geometricConstraints.addFix(best)
            except: pass
        return best
    _pcurve_0 = _nearest_proj_curve(*_xf(117.1557, 276.86), *_xf(118.745, 243.84))
    _pcurve_1 = _nearest_proj_curve(*_xf(118.745, 243.84), *_xf(118.745, 276.86))
    _pcurve_2 = _nearest_proj_curve(*_xf(118.745, 276.86), *_xf(117.1557, 276.86))
    _pcurve_3 = _nearest_proj_curve(*_xf(113.4172, 260.0936), *_xf(124.0728, 260.6064))
    _pcurve_12 = _nearest_proj_curve(*_xf(118.745, 243.84), *_xf(117.1557, 276.86))
    _pcurve_13 = _nearest_proj_curve(*_xf(117.1557, 276.86), *_xf(114.3, 276.86))
    _pcurve_14 = _nearest_proj_curve(*_xf(114.3, 276.86), *_xf(114.3, 243.84))
    _pcurve_15 = _nearest_proj_curve(*_xf(114.3, 243.84), *_xf(118.745, 243.84))
    # curve[3] is a projected reference (source not captured)
    _cs_4 = _xf(117.9522, 260.3118)
    _ce_4 = _xf(117.914, 261.1047)
    ln4 = lns.addByTwoPoints(P(_cs_4[0], _cs_4[1], 0), P(_ce_4[0], _ce_4[1], 0))
    _cs_5 = _xf(117.914, 261.1047)
    _ce_5 = _xf(119.4997, 261.181)
    ln5 = lns.addByTwoPoints(ln4.endSketchPoint, P(_ce_5[0], _ce_5[1], 0))
    _cs_6 = _xf(119.4997, 261.181)
    _ce_6 = _xf(119.576, 259.5953)
    ln6 = lns.addByTwoPoints(ln5.endSketchPoint, P(_ce_6[0], _ce_6[1], 0))
    _cs_7 = _xf(119.576, 259.5953)
    _ce_7 = _xf(117.9903, 259.519)
    ln7 = lns.addByTwoPoints(ln6.endSketchPoint, P(_ce_7[0], _ce_7[1], 0))
    _cs_8 = _xf(118.745, 276.86)
    _ce_8 = _xf(119.4997, 261.181)
    ln8 = lns.addByTwoPoints(P(_cs_8[0], _cs_8[1], 0), ln5.endSketchPoint)
    _cs_9 = _xf(118.745, 276.86)
    _ce_9 = _xf(118.8213, 275.2743)
    ln9 = lns.addByTwoPoints(ln8.startSketchPoint, P(_ce_9[0], _ce_9[1], 0))
    _cs_10 = _xf(118.8213, 275.2743)
    _ce_10 = _xf(117.2357, 275.198)
    ln10 = lns.addByTwoPoints(ln9.endSketchPoint, P(_ce_10[0], _ce_10[1], 0))
    _cs_11 = _xf(117.2357, 275.198)
    _ce_11 = _xf(114.3, 275.198)
    ln11 = lns.addByTwoPoints(ln10.endSketchPoint, P(_ce_11[0], _ce_11[1], 0))
    _cs_12 = _xf(118.745, 243.84)
    _ce_12 = _xf(118.6687, 245.4257)
    ln12 = lns.addByTwoPoints(P(_cs_12[0], _cs_12[1], 0), P(_ce_12[0], _ce_12[1], 0))
    _cs_13 = _xf(118.6687, 245.4257)
    _ce_13 = _xf(120.2543, 245.502)
    ln13 = lns.addByTwoPoints(ln12.endSketchPoint, P(_ce_13[0], _ce_13[1], 0))
    _cs_14 = _xf(118.6687, 245.4257)
    _ce_14 = _xf(120.2562, 245.4257)
    ln14 = lns.addByTwoPoints(ln12.endSketchPoint, P(_ce_14[0], _ce_14[1], 0))
    ln14.isConstruction = True
    _cs_15 = _xf(118.745, 243.84)
    _ce_15 = _xf(123.19, 243.84)
    ln15 = lns.addByTwoPoints(ln12.startSketchPoint, P(_ce_15[0], _ce_15[1], 0))
    _cs_16 = _xf(120.2543, 245.502)
    _ce_16 = _xf(120.3343, 243.84)
    ln16 = lns.addByTwoPoints(ln13.endSketchPoint, P(_ce_16[0], _ce_16[1], 0))
    _cs_17 = _xf(120.2543, 245.502)
    _ce_17 = _xf(121.9183, 245.502)
    ln17 = lns.addByTwoPoints(ln13.endSketchPoint, P(_ce_17[0], _ce_17[1], 0))
    ln17.isConstruction = True
    _cs_18 = _xf(123.19, 243.84)
    _ce_18 = _xf(123.19, 245.502)
    ln18 = lns.addByTwoPoints(ln15.endSketchPoint, P(_ce_18[0], _ce_18[1], 0))
    _cs_19 = _xf(123.19, 245.502)
    _ce_19 = _xf(120.2543, 245.502)
    ln19 = lns.addByTwoPoints(ln18.endSketchPoint, ln13.endSketchPoint)
    _pd = Sketch7_posts.sketchDimensions
    try: _pd.addDistanceDimension(ln14.startSketchPoint, ln14.endSketchPoint, H, P(0, 0, 0)).parameter.value = 1.5875
    except: pass
    try: _pd.addDistanceDimension(ln17.startSketchPoint, ln17.endSketchPoint, H, P(0, 0, 0)).parameter.value = 1.664
    except: pass
    d = Sketch7_posts.sketchDimensions
    try:
        d.addDistanceDimension(ln4.startSketchPoint, ln4.endSketchPoint,
            adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, P(0, 0, 0)).parameter.expression = "scarf_notch / 2"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln4.endSketchPoint, ln5.endSketchPoint,
            adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, P(0, 0, 0)).parameter.expression = "scarf_notch"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln5.endSketchPoint, ln6.endSketchPoint,
            adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, P(0, 0, 0)).parameter.expression = "scarf_notch"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(_nearest_proj(*_xf(118.745, 276.86)), ln9.endSketchPoint,
            adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, P(0, 0, 0)).parameter.expression = "scarf_notch"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(_nearest_proj(*_xf(118.745, 243.84)), ln12.endSketchPoint,
            adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, P(0, 0, 0)).parameter.expression = "scarf_notch"
    except: pass  # skip if already constrained
    try:
        d.addAngularDimension(ln14, ln13, P(*_xf(120.2553, 245.4639), 0)).parameter.expression = "scarf_tilt"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln12.endSketchPoint, ln13.endSketchPoint,
            adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, P(0, 0, 0)).parameter.expression = "scarf_notch"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(_nearest_proj(*_xf(118.745, 243.84)), ln15.endSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "post_w / 2"
    except: pass  # skip if already constrained
    try:
        d.addAngularDimension(ln17, ln16, P(*_xf(121.1263, 244.671), 0)).parameter.expression = "90 deg - scarf_tilt"
    except: pass  # skip if already constrained
    gc = Sketch7_posts.geometricConstraints
    try: gc.addCoincident(ln4.startSketchPoint, _pcurve_3)
    except: pass
    try: gc.addCoincident(ln4.startSketchPoint, _pcurve_0)
    except: pass
    try: gc.addPerpendicular(ln4, _pcurve_3)
    except: pass
    try: gc.addPerpendicular(ln5, ln4)
    except: pass
    try: gc.addPerpendicular(ln6, ln5)
    except: pass
    try: gc.addCoincident(ln7.endSketchPoint, _pcurve_0)
    except: pass
    try: gc.addPerpendicular(ln7, _pcurve_0)
    except: pass
    try: gc.addParallel(ln9, ln8)
    except: pass
    try: gc.addCoincident(ln10.endSketchPoint, _pcurve_0)
    except: pass
    try: gc.addPerpendicular(ln10, _pcurve_0)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln11)
    except: pass
    try: gc.addParallel(ln12, _pcurve_12)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln14)
    except: pass
    try: gc.addParallel(ln15, _pcurve_15)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln17)
    except: pass
    try: gc.addCoincident(ln16.endSketchPoint, ln15)
    except: pass
    try: gc.addPerpendicular(ln18, ln15)
    except: pass
    try: gc.addPerpendicular(ln19, ln18)
    except: pass
    Sketch7_posts_prof = Sketch7_posts.profiles.item(0)  # 15 profile(s)

    # [18] Extrude: Extrude6
    comp = posts_c
    _cx = (1.0, 0.0, 0.0)
    _cy = (0.0, 0.0, 1.0)
    _ax = Sketch7_posts.xDirection
    _ay = Sketch7_posts.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Multi-profile extrude: 2 profiles
    _prof_coll = adsk.core.ObjectCollection.create()
    _used = set()
    # Match profile by bbox (transformed): (118.745, 261.1447) to (119.4997, 275.2743)
    _t1 = (118.745*_m00 + 261.1447*_m01, 118.745*_m10 + 261.1447*_m11)
    _t2 = (119.4997*_m00 + 275.2743*_m01, 119.4997*_m10 + 275.2743*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch7_posts.profiles.count):
        if _pi in _used: continue
        _bb = Sketch7_posts.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch7_posts.profiles.item(_best_pi))
    _used.add(_best_pi)
    # Match profile by bbox (transformed): (118.745, 275.2707) to (118.8213, 276.86)
    _t1 = (118.745*_m00 + 275.2707*_m01, 118.745*_m10 + 275.2707*_m11)
    _t2 = (118.8213*_m00 + 276.86*_m01, 118.8213*_m10 + 276.86*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch7_posts.profiles.count):
        if _pi in _used: continue
        _bb = Sketch7_posts.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch7_posts.profiles.item(_best_pi))
    _used.add(_best_pi)
    inp = comp.features.extrudeFeatures.createInput(_prof_coll, JOIN)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("-post_w"))
    inp.participantBodies = [Body4_posts]
    Extrude6 = comp.features.extrudeFeatures.add(inp)
    Extrude6.name = "Extrude6"

    # [19] Extrude: Extrude7
    comp = posts_c
    _cx = (1.0, 0.0, 0.0)
    _cy = (0.0, 0.0, 1.0)
    _ax = Sketch7_posts.xDirection
    _ay = Sketch7_posts.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Multi-profile extrude: 2 profiles
    _prof_coll = adsk.core.ObjectCollection.create()
    _used = set()
    # Match profile by bbox (transformed): (118.6687, 243.84) to (118.745, 245.4293)
    _t1 = (118.6687*_m00 + 243.84*_m01, 118.6687*_m10 + 243.84*_m11)
    _t2 = (118.745*_m00 + 245.4293*_m01, 118.745*_m10 + 245.4293*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch7_posts.profiles.count):
        if _pi in _used: continue
        _bb = Sketch7_posts.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch7_posts.profiles.item(_best_pi))
    _used.add(_best_pi)
    # Match profile by bbox (transformed): (117.9903, 245.4257) to (118.745, 259.5553)
    _t1 = (117.9903*_m00 + 245.4257*_m01, 117.9903*_m10 + 245.4257*_m11)
    _t2 = (118.745*_m00 + 259.5553*_m01, 118.745*_m10 + 259.5553*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch7_posts.profiles.count):
        if _pi in _used: continue
        _bb = Sketch7_posts.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch7_posts.profiles.item(_best_pi))
    _used.add(_best_pi)
    inp = comp.features.extrudeFeatures.createInput(_prof_coll, CUT)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("-post_w"))
    inp.participantBodies = [Body4_posts]
    Extrude7 = comp.features.extrudeFeatures.add(inp)
    Extrude7.name = "Extrude7"

    # [20] Extrude: Extrude8
    comp = posts_c
    _cx = (1.0, 0.0, 0.0)
    _cy = (0.0, 0.0, 1.0)
    _ax = Sketch7_posts.xDirection
    _ay = Sketch7_posts.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Multi-profile extrude: 2 profiles
    _prof_coll = adsk.core.ObjectCollection.create()
    _used = set()
    # Match profile by bbox (transformed): (118.6687, 243.84) to (118.745, 245.4293)
    _t1 = (118.6687*_m00 + 243.84*_m01, 118.6687*_m10 + 243.84*_m11)
    _t2 = (118.745*_m00 + 245.4293*_m01, 118.745*_m10 + 245.4293*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch7_posts.profiles.count):
        if _pi in _used: continue
        _bb = Sketch7_posts.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch7_posts.profiles.item(_best_pi))
    _used.add(_best_pi)
    # Match profile by bbox (transformed): (117.9903, 245.4257) to (118.745, 259.5553)
    _t1 = (117.9903*_m00 + 245.4257*_m01, 117.9903*_m10 + 245.4257*_m11)
    _t2 = (118.745*_m00 + 259.5553*_m01, 118.745*_m10 + 259.5553*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch7_posts.profiles.count):
        if _pi in _used: continue
        _bb = Sketch7_posts.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch7_posts.profiles.item(_best_pi))
    _used.add(_best_pi)
    inp = comp.features.extrudeFeatures.createInput(_prof_coll, NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("-post_w"))
    Extrude8 = comp.features.extrudeFeatures.add(inp)
    Extrude8.name = "Extrude8"
    Body5_posts = Extrude8.bodies.item(0)
    Body5_posts.name = "Body5"

    # [21] Combine: Combine3
    comp = posts_c
    Combine3 = combine(comp, scarf1_posts, [Body5_posts], CUT, False, "Combine3")

    # [22] Extrude: Extrude9
    comp = posts_c
    _cx = (1.0, 0.0, 0.0)
    _cy = (0.0, 0.0, 1.0)
    _ax = Sketch7_posts.xDirection
    _ay = Sketch7_posts.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Multi-profile extrude: 4 profiles
    _prof_coll = adsk.core.ObjectCollection.create()
    _used = set()
    # Match profile by bbox (transformed): (117.914, 260.3118) to (118.745, 261.1447)
    _t1 = (117.914*_m00 + 260.3118*_m01, 117.914*_m10 + 260.3118*_m11)
    _t2 = (118.745*_m00 + 261.1447*_m01, 118.745*_m10 + 261.1447*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch7_posts.profiles.count):
        if _pi in _used: continue
        _bb = Sketch7_posts.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch7_posts.profiles.item(_best_pi))
    _used.add(_best_pi)
    # Match profile by bbox (transformed): (117.9522, 259.519) to (118.745, 260.35)
    _t1 = (117.9522*_m00 + 259.519*_m01, 117.9522*_m10 + 259.519*_m11)
    _t2 = (118.745*_m00 + 260.35*_m01, 118.745*_m10 + 260.35*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch7_posts.profiles.count):
        if _pi in _used: continue
        _bb = Sketch7_posts.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch7_posts.profiles.item(_best_pi))
    _used.add(_best_pi)
    # Match profile by bbox (transformed): (118.745, 259.5553) to (119.576, 260.3882)
    _t1 = (118.745*_m00 + 259.5553*_m01, 118.745*_m10 + 259.5553*_m11)
    _t2 = (119.576*_m00 + 260.3882*_m01, 119.576*_m10 + 260.3882*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch7_posts.profiles.count):
        if _pi in _used: continue
        _bb = Sketch7_posts.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch7_posts.profiles.item(_best_pi))
    _used.add(_best_pi)
    # Match profile by bbox (transformed): (118.745, 260.35) to (119.5378, 261.181)
    _t1 = (118.745*_m00 + 260.35*_m01, 118.745*_m10 + 260.35*_m11)
    _t2 = (119.5378*_m00 + 261.181*_m01, 119.5378*_m10 + 261.181*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch7_posts.profiles.count):
        if _pi in _used: continue
        _bb = Sketch7_posts.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch7_posts.profiles.item(_best_pi))
    _used.add(_best_pi)
    inp = comp.features.extrudeFeatures.createInput(_prof_coll, NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("-post_w"))
    Extrude9 = comp.features.extrudeFeatures.add(inp)
    Extrude9.name = "Extrude9"
    wedge1_posts = Extrude9.bodies.item(0)
    wedge1_posts.name = "wedge1"

    # [23] Combine: Combine4
    comp = posts_c
    Combine4 = combine(comp, scarf1_posts, [wedge1_posts], CUT, True, "Combine4")

    # [24] Sketch: Sketch8
    comp = posts_c
    Sketch8_posts = comp.sketches.add(find_face_near(scarf1_posts, 117.1557, -173.355, 276.86, 0.0, 0.0, 1.0))
    Sketch8_posts.name = "Sketch8"
    lns = Sketch8_posts.sketchCurves.sketchLines
    # Coordinate transform: captured sketch axes -> actual sketch axes
    _cap_xd = (-1.0, 0.0, 0.0)
    _cap_yd = (0.0, -1.0, 0.0)
    _act_xd = Sketch8_posts.xDirection
    _act_yd = Sketch8_posts.yDirection
    _m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z
    _m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z
    _m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z
    _m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z
    def _xf(sx, sy):
        return (sx * _m00 + sy * _m01, sx * _m10 + sy * _m11)
    _proj_pts = []  # [(x, y, sketchPoint), ...]
    _proj_curves = []  # [(sx, sy, ex, ey, curve), ...]
    for _ci in range(Sketch8_posts.sketchCurves.count):
        _c = Sketch8_posts.sketchCurves.item(_ci)
        if _c.isReference:
            for _sp in [_c.startSketchPoint, _c.endSketchPoint]:
                _g = _sp.geometry
                _proj_pts.append((_g.x, _g.y, _sp))
            _s, _e = _c.startSketchPoint.geometry, _c.endSketchPoint.geometry
            _proj_curves.append((_s.x, _s.y, _e.x, _e.y, _c))

    _fallback_pts = {}
    def _nearest_proj(x, y):
        best, best_d = None, 1e10
        for _px, _py, _sp in _proj_pts:
            _d = abs(_px - x) + abs(_py - y)
            if _d < best_d: best, best_d = _sp, _d
        if best_d > 5.0: best = None
        if best is None:
            _fk = (round(x,2), round(y,2))
            best = _fallback_pts.get(_fk)
        if best is None:
            best = Sketch8_posts.sketchPoints.add(P(x, y, 0))
        return best

    def _nearest_proj_curve(sx, sy, ex, ey):
        best, best_d = None, 1e10
        for _sx, _sy, _ex, _ey, _c in _proj_curves:
            _d = min(abs(_sx-sx)+abs(_sy-sy)+abs(_ex-ex)+abs(_ey-ey),
                    abs(_sx-ex)+abs(_sy-ey)+abs(_ex-sx)+abs(_ey-sy))
            if _d < best_d: best, best_d = _c, _d
        if best_d > 10.0: best = None
        if best is None:
            _sk = (round(sx,2), round(sy,2))
            _ek = (round(ex,2), round(ey,2))
            _sp = _fallback_pts.get(_sk)
            _ep = _fallback_pts.get(_ek)
            if _sp and _ep:
                best = Sketch8_posts.sketchCurves.sketchLines.addByTwoPoints(_sp, _ep)
            elif _sp:
                best = Sketch8_posts.sketchCurves.sketchLines.addByTwoPoints(_sp, P(ex, ey, 0))
                _fallback_pts[_ek] = best.endSketchPoint
            elif _ep:
                best = Sketch8_posts.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), _ep)
                _fallback_pts[_sk] = best.startSketchPoint
            else:
                best = Sketch8_posts.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), P(ex, ey, 0))
                _fallback_pts[_sk] = best.startSketchPoint
                _fallback_pts[_ek] = best.endSketchPoint
            try: Sketch8_posts.geometricConstraints.addFix(best)
            except: pass
        return best
    _pcurve_0 = _nearest_proj_curve(*_xf(-117.1557, 177.8), *_xf(-117.1557, 168.91))
    _pcurve_1 = _nearest_proj_curve(*_xf(-117.1557, 168.91), *_xf(-114.3, 168.91))
    _pcurve_2 = _nearest_proj_curve(*_xf(-114.3, 168.91), *_xf(-114.3, 177.8))
    _pcurve_3 = _nearest_proj_curve(*_xf(-114.3, 177.8), *_xf(-117.1557, 177.8))
    _cs_0 = _xf(-114.3, 177.8)
    _ce_0 = _xf(-114.3, 174.1488)
    ln0 = lns.addByTwoPoints(P(_cs_0[0], _cs_0[1], 0), P(_ce_0[0], _ce_0[1], 0))
    _cs_1 = _xf(-114.3, 174.1488)
    _ce_1 = _xf(-117.475, 174.1488)
    ln1 = lns.addByTwoPoints(ln0.endSketchPoint, P(_ce_1[0], _ce_1[1], 0))
    _cs_2 = _xf(-117.475, 174.1488)
    _ce_2 = _xf(-117.475, 172.5613)
    ln2 = lns.addByTwoPoints(ln1.endSketchPoint, P(_ce_2[0], _ce_2[1], 0))
    _cs_3 = _xf(-117.475, 172.5613)
    _ce_3 = _xf(-114.3, 172.5613)
    ln3 = lns.addByTwoPoints(ln2.endSketchPoint, P(_ce_3[0], _ce_3[1], 0))
    _cs_4 = _xf(-114.3, 172.5613)
    _ce_4 = _xf(-114.3, 174.1488)
    ln4 = lns.addByTwoPoints(ln3.endSketchPoint, ln0.endSketchPoint)
    d = Sketch8_posts.sketchDimensions
    try:
        d.addDistanceDimension(_nearest_proj(*_xf(-114.3, 177.8)), ln0.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "( post_w - scarf_notch ) / 2"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln0.endSketchPoint, ln1.endSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "scarf_notch * 2"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln3.endSketchPoint, ln0.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "scarf_notch"
    except: pass  # skip if already constrained
    gc = Sketch8_posts.geometricConstraints
    try: gc.addPerpendicular(ln0, _pcurve_3)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln1)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln2)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln3)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln4)
    except: pass
    Sketch8_posts_prof = Sketch8_posts.profiles.item(0)  # 4 profile(s)

    # [25] Extrude: Extrude10
    comp = posts_c
    _cx = (-1.0, 0.0, 0.0)
    _cy = (0.0, -1.0, 0.0)
    _ax = Sketch8_posts.xDirection
    _ay = Sketch8_posts.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Multi-profile extrude: 2 profiles
    _prof_coll = adsk.core.ObjectCollection.create()
    _used = set()
    # Match profile by bbox (transformed): (-117.1557, 172.5613) to (-114.3, 174.1488)
    _t1 = (-117.1557*_m00 + 172.5613*_m01, -117.1557*_m10 + 172.5613*_m11)
    _t2 = (-114.3*_m00 + 174.1488*_m01, -114.3*_m10 + 174.1488*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch8_posts.profiles.count):
        if _pi in _used: continue
        _bb = Sketch8_posts.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch8_posts.profiles.item(_best_pi))
    _used.add(_best_pi)
    # Match profile by bbox (transformed): (-117.475, 172.5613) to (-117.1557, 174.1488)
    _t1 = (-117.475*_m00 + 172.5613*_m01, -117.475*_m10 + 172.5613*_m11)
    _t2 = (-117.1557*_m00 + 174.1488*_m01, -117.1557*_m10 + 174.1488*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch8_posts.profiles.count):
        if _pi in _used: continue
        _bb = Sketch8_posts.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch8_posts.profiles.item(_best_pi))
    _used.add(_best_pi)
    inp = comp.features.extrudeFeatures.createInput(_prof_coll, NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("-scarf_notch - 10 mm"))
    Extrude10 = comp.features.extrudeFeatures.add(inp)
    Extrude10.name = "Extrude10"
    Body7_posts = Extrude10.bodies.item(0)
    Body7_posts.name = "Body7"

    # [26] Extrude: Extrude11
    comp = posts_c
    _cx = (1.0, 0.0, 0.0)
    _cy = (0.0, 0.0, 1.0)
    _ax = Sketch7_posts.xDirection
    _ay = Sketch7_posts.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Match profile by bbox (transformed): (114.3, 275.198) to (117.2357, 276.86)
    _t1 = (114.3*_m00 + 275.198*_m01, 114.3*_m10 + 275.198*_m11)
    _t2 = (117.2357*_m00 + 276.86*_m01, 117.2357*_m10 + 276.86*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch7_posts.profiles.count):
        _bb = Sketch7_posts.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    inp = comp.features.extrudeFeatures.createInput(Sketch7_posts.profiles.item(_best_pi), CUT)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("-post_w"))
    inp.participantBodies = [scarf1_posts]
    Extrude11 = comp.features.extrudeFeatures.add(inp)
    Extrude11.name = "Extrude11"

    # [27] Extrude: Extrude2
    comp = posts_c
    _cx = (-1.0, 0.0, 0.0)
    _cy = (0.0, -1.0, 0.0)
    _ax = Sketch1_posts.xDirection
    _ay = Sketch1_posts.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Match profile by bbox (transformed): (-342.9, 168.91) to (-334.01, 177.8)
    _t1 = (-342.9*_m00 + 168.91*_m01, -342.9*_m10 + 168.91*_m11)
    _t2 = (-334.01*_m00 + 177.8*_m01, -334.01*_m10 + 177.8*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch1_posts.profiles.count):
        _bb = Sketch1_posts.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    inp = comp.features.extrudeFeatures.createInput(Sketch1_posts.profiles.item(_best_pi), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("post_height"))
    Extrude2 = comp.features.extrudeFeatures.add(inp)
    Extrude2.name = "Extrude2"
    post2_posts = Extrude2.bodies.item(0)
    post2_posts.name = "post2"

    # [28] Combine: Combine5
    comp = posts_c
    Combine5 = combine(comp, Body4_posts, [wedge1_posts], CUT, True, "Combine5")

    # [29] Combine: Combine6
    comp = posts_c
    Combine6 = combine(comp, scarf1_posts, [Body4_posts], JOIN, False, "Combine6")

    # [30] Combine: Combine7
    comp = posts_c
    Combine7 = combine(comp, scarf1_posts, [Body7_posts], JOIN, False, "Combine7")

    # [31] Extrude: Extrude12
    comp = posts_c
    _cx = (1.0, 0.0, 0.0)
    _cy = (0.0, 0.0, 1.0)
    _ax = Sketch7_posts.xDirection
    _ay = Sketch7_posts.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Match profile by bbox (transformed): (120.2543, 243.84) to (123.19, 245.502)
    _t1 = (120.2543*_m00 + 243.84*_m01, 120.2543*_m10 + 243.84*_m11)
    _t2 = (123.19*_m00 + 245.502*_m01, 123.19*_m10 + 245.502*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch7_posts.profiles.count):
        _bb = Sketch7_posts.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    inp = comp.features.extrudeFeatures.createInput(Sketch7_posts.profiles.item(_best_pi), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("-post_w"))
    Extrude12 = comp.features.extrudeFeatures.add(inp)
    Extrude12.name = "Extrude12"
    notch1_posts = Extrude12.bodies.item(0)
    notch1_posts.name = "notch1"

    # [32] Extrude: Extrude13
    comp = posts_c
    _cx = (1.0, 0.0, 0.0)
    _cy = (0.0, 1.0, 0.0)
    _ax = Sketch5_posts.xDirection
    _ay = Sketch5_posts.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Match profile by bbox (transformed): (118.745, -174.1488) to (123.19, -172.5613)
    _t1 = (118.745*_m00 + -174.1488*_m01, 118.745*_m10 + -174.1488*_m11)
    _t2 = (123.19*_m00 + -172.5613*_m01, 123.19*_m10 + -172.5613*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch5_posts.profiles.count):
        _bb = Sketch5_posts.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    inp = comp.features.extrudeFeatures.createInput(Sketch5_posts.profiles.item(_best_pi), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("scarf_notch + 10 mm"))
    Extrude13 = comp.features.extrudeFeatures.add(inp)
    Extrude13.name = "Extrude13"
    Body9_posts = Extrude13.bodies.item(0)
    Body9_posts.name = "Body9"

    # [33] Combine: Combine8
    comp = posts_c
    _pre_cut_tool_bb = Body9_posts.boundingBox
    _pre_cut_names = set()
    for _bi in range(comp.bRepBodies.count): _pre_cut_names.add(comp.bRepBodies.item(_bi).name)
    Combine8 = combine(comp, notch1_posts, [Body9_posts], CUT, False, "Combine8")
    if Combine8 is not None and Combine8.bodies.count > 1:
        notch2_posts = Combine8.bodies.item(1)
        notch2_posts.name = "notch2"
    else:
        # CUT did not split (coincident face issue) — 2-plane SplitBody fallback
        _tbb = _pre_cut_tool_bb
        _dx = _tbb.maxPoint.x - _tbb.minPoint.x
        _dy = _tbb.maxPoint.y - _tbb.minPoint.y
        _dz = _tbb.maxPoint.z - _tbb.minPoint.z
        if _dy <= _dx and _dy <= _dz:
            _off_min, _off_max, _base_pl, _ax = _tbb.minPoint.y, _tbb.maxPoint.y, comp.xZConstructionPlane, "y"
        elif _dx <= _dy and _dx <= _dz:
            _off_min, _off_max, _base_pl, _ax = _tbb.minPoint.x, _tbb.maxPoint.x, comp.yZConstructionPlane, "x"
        else:
            _off_min, _off_max, _base_pl, _ax = _tbb.minPoint.z, _tbb.maxPoint.z, comp.xYConstructionPlane, "z"
        _pl_inp1 = comp.constructionPlanes.createInput()
        _pl_inp1.setByOffset(_base_pl, adsk.core.ValueInput.createByReal(_off_min))
        _pln1 = comp.constructionPlanes.add(_pl_inp1)
        _pl_inp2 = comp.constructionPlanes.createInput()
        _pl_inp2.setByOffset(_base_pl, adsk.core.ValueInput.createByReal(_off_max))
        _pln2 = comp.constructionPlanes.add(_pl_inp2)
        try:
            _spi = comp.features.splitBodyFeatures.createInput(notch1_posts, _pln1, False)
            comp.features.splitBodyFeatures.add(_spi)
        except: pass
        try:
            _spi2 = comp.features.splitBodyFeatures.createInput(notch1_posts, _pln2, False)
            comp.features.splitBodyFeatures.add(_spi2)
        except:
            # Target didn't span max plane — try auto-named pieces from first split
            for _bi in range(comp.bRepBodies.count):
                _b = comp.bRepBodies.item(_bi)
                if _b.name not in _pre_cut_names:
                    try:
                        _spi2 = comp.features.splitBodyFeatures.createInput(_b, _pln2, False)
                        comp.features.splitBodyFeatures.add(_spi2)
                        break
                    except: pass
        for _bi in range(comp.bRepBodies.count - 1, -1, -1):
            _b = comp.bRepBodies.item(_bi)
            if _b.name not in _pre_cut_names and _b.volume < 1.0:
                try: comp.features.removeFeatures.add(_b)
                except: pass
        _new_bodies = []
        for _bi in range(comp.bRepBodies.count):
            _b = comp.bRepBodies.item(_bi)
            if _b.name not in _pre_cut_names:
                _new_bodies.append(_b)
        _new_bodies.sort(key=lambda _b: getattr(_b.boundingBox.minPoint, _ax))
        if _new_bodies:
            notch2_posts = _new_bodies.pop(0)
            notch2_posts.name = "notch2"
        else:
            notch2_posts = find_body("notch2", comp)

    # [34] ComponentCreation: beam
    comp = root
    beam_occ = comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    beam_occ.component.name = "beam"
    beam_c = beam_occ.component

    # [35] Sketch: Sketch1
    comp = beam_c
    Sketch1_beam = comp.sketches.add(find_face_near(wall_Surranding, 304.8, 0.0, 457.35, 0.0, 1.0, -0.0))
    Sketch1_beam.name = "Sketch1"
    lns = Sketch1_beam.sketchCurves.sketchLines
    # Coordinate transform: captured sketch axes -> actual sketch axes
    _cap_xd = (1.0, 0.0, 0.0)
    _cap_yd = (0.0, 0.0, 1.0)
    _act_xd = Sketch1_beam.xDirection
    _act_yd = Sketch1_beam.yDirection
    _m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z
    _m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z
    _m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z
    _m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z
    def _xf(sx, sy):
        return (sx * _m00 + sy * _m01, sx * _m10 + sy * _m11)
    _proj_pts = []  # [(x, y, sketchPoint), ...]
    _proj_curves = []  # [(sx, sy, ex, ey, curve), ...]
    for _ci in range(Sketch1_beam.sketchCurves.count):
        _c = Sketch1_beam.sketchCurves.item(_ci)
        if _c.isReference:
            for _sp in [_c.startSketchPoint, _c.endSketchPoint]:
                _g = _sp.geometry
                _proj_pts.append((_g.x, _g.y, _sp))
            _s, _e = _c.startSketchPoint.geometry, _c.endSketchPoint.geometry
            _proj_curves.append((_s.x, _s.y, _e.x, _e.y, _c))

    _fallback_pts = {}
    def _nearest_proj(x, y):
        best, best_d = None, 1e10
        for _px, _py, _sp in _proj_pts:
            _d = abs(_px - x) + abs(_py - y)
            if _d < best_d: best, best_d = _sp, _d
        if best_d > 5.0: best = None
        if best is None:
            _fk = (round(x,2), round(y,2))
            best = _fallback_pts.get(_fk)
        if best is None:
            best = Sketch1_beam.sketchPoints.add(P(x, y, 0))
        return best

    def _nearest_proj_curve(sx, sy, ex, ey):
        best, best_d = None, 1e10
        for _sx, _sy, _ex, _ey, _c in _proj_curves:
            _d = min(abs(_sx-sx)+abs(_sy-sy)+abs(_ex-ex)+abs(_ey-ey),
                    abs(_sx-ex)+abs(_sy-ey)+abs(_ex-sx)+abs(_ey-sy))
            if _d < best_d: best, best_d = _c, _d
        if best_d > 10.0: best = None
        if best is None:
            _sk = (round(sx,2), round(sy,2))
            _ek = (round(ex,2), round(ey,2))
            _sp = _fallback_pts.get(_sk)
            _ep = _fallback_pts.get(_ek)
            if _sp and _ep:
                best = Sketch1_beam.sketchCurves.sketchLines.addByTwoPoints(_sp, _ep)
            elif _sp:
                best = Sketch1_beam.sketchCurves.sketchLines.addByTwoPoints(_sp, P(ex, ey, 0))
                _fallback_pts[_ek] = best.endSketchPoint
            elif _ep:
                best = Sketch1_beam.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), _ep)
                _fallback_pts[_sk] = best.startSketchPoint
            else:
                best = Sketch1_beam.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), P(ex, ey, 0))
                _fallback_pts[_sk] = best.startSketchPoint
                _fallback_pts[_ek] = best.endSketchPoint
            try: Sketch1_beam.geometricConstraints.addFix(best)
            except: pass
        return best
    _pcurve_0 = _nearest_proj_curve(*_xf(609.6, 914.4), *_xf(0.0, 914.4))
    _pcurve_1 = _nearest_proj_curve(*_xf(0.0, 914.4), *_xf(0.0, 0.0))
    _pcurve_2 = _nearest_proj_curve(*_xf(0.0, 0.0), *_xf(609.6, 0.0))
    _pcurve_3 = _nearest_proj_curve(*_xf(609.6, 0.0), *_xf(609.6, 914.4))
    _cs_0 = _xf(0.0, 0.0)
    _ce_0 = _xf(114.3, -0.0)
    ln0 = lns.addByTwoPoints(P(_cs_0[0], _cs_0[1], 0), P(_ce_0[0], _ce_0[1], 0))
    _cs_1 = _xf(114.3, -0.0)
    _ce_1 = _xf(114.3, 411.48)
    ln1 = lns.addByTwoPoints(ln0.endSketchPoint, P(_ce_1[0], _ce_1[1], 0))
    _cs_2 = _xf(114.3, 411.48)
    _ce_2 = _xf(83.82, 411.48)
    ln2 = lns.addByTwoPoints(ln1.endSketchPoint, P(_ce_2[0], _ce_2[1], 0))
    _cs_3 = _xf(83.82, 411.48)
    _ce_3 = _xf(83.82, 426.72)
    ln3 = lns.addByTwoPoints(ln2.endSketchPoint, P(_ce_3[0], _ce_3[1], 0))
    _cs_4 = _xf(83.82, 426.72)
    _ce_4 = _xf(373.38, 426.72)
    ln4 = lns.addByTwoPoints(ln3.endSketchPoint, P(_ce_4[0], _ce_4[1], 0))
    _cs_5 = _xf(373.38, 426.72)
    _ce_5 = _xf(373.38, 411.48)
    ln5 = lns.addByTwoPoints(ln4.endSketchPoint, P(_ce_5[0], _ce_5[1], 0))
    _cs_6 = _xf(373.38, 411.48)
    _ce_6 = _xf(114.3, 411.48)
    ln6 = lns.addByTwoPoints(ln5.endSketchPoint, ln1.endSketchPoint)
    _cs_7 = _xf(228.6, 426.72)
    _ce_7 = _xf(228.6, 411.48)
    ln7 = lns.addByTwoPoints(P(_cs_7[0], _cs_7[1], 0), P(_ce_7[0], _ce_7[1], 0))
    _spl_pts8 = adsk.core.ObjectCollection.create()
    _sfp_8_0 = _xf(83.82, 421.2719)
    _spl_pts8.add(P(_sfp_8_0[0], _sfp_8_0[1], 0))
    _sfp_8_1 = _xf(90.8445, 420.0364)
    _spl_pts8.add(P(_sfp_8_1[0], _sfp_8_1[1], 0))
    _sfp_8_2 = _xf(94.5, 419.0)
    _spl_pts8.add(P(_sfp_8_2[0], _sfp_8_2[1], 0))
    _sfp_8_3 = _xf(100.0, 416.0)
    _spl_pts8.add(P(_sfp_8_3[0], _sfp_8_3[1], 0))
    _sfp_8_4 = _xf(104.0675, 411.48)
    _spl_pts8.add(P(_sfp_8_4[0], _sfp_8_4[1], 0))
    spl8 = Sketch1_beam.sketchCurves.sketchFittedSplines.add(_spl_pts8)
    _spl_pts9 = adsk.core.ObjectCollection.create()
    _sfp_9_0 = _xf(373.38, 421.2719)
    _spl_pts9.add(P(_sfp_9_0[0], _sfp_9_0[1], 0))
    _sfp_9_1 = _xf(366.3555, 420.0364)
    _spl_pts9.add(P(_sfp_9_1[0], _sfp_9_1[1], 0))
    _sfp_9_2 = _xf(362.7, 419.0)
    _spl_pts9.add(P(_sfp_9_2[0], _sfp_9_2[1], 0))
    _sfp_9_3 = _xf(357.2, 416.0)
    _spl_pts9.add(P(_sfp_9_3[0], _sfp_9_3[1], 0))
    _sfp_9_4 = _xf(353.1325, 411.48)
    _spl_pts9.add(P(_sfp_9_4[0], _sfp_9_4[1], 0))
    spl9 = Sketch1_beam.sketchCurves.sketchFittedSplines.add(_spl_pts9)
    _cs_10 = _xf(114.3, 411.48)
    _ce_10 = _xf(114.3, 411.226)
    ln10 = lns.addByTwoPoints(ln1.endSketchPoint, P(_ce_10[0], _ce_10[1], 0))
    _cs_11 = _xf(114.3, 411.226)
    _ce_11 = _xf(123.19, 411.226)
    ln11 = lns.addByTwoPoints(ln10.endSketchPoint, P(_ce_11[0], _ce_11[1], 0))
    _cs_12 = _xf(123.19, 411.226)
    _ce_12 = _xf(123.19, 397.891)
    ln12 = lns.addByTwoPoints(ln11.endSketchPoint, P(_ce_12[0], _ce_12[1], 0))
    _cs_13 = _xf(123.19, 397.891)
    _ce_13 = _xf(114.3, 397.891)
    ln13 = lns.addByTwoPoints(ln12.endSketchPoint, P(_ce_13[0], _ce_13[1], 0))
    _cs_14 = _xf(114.3, 397.891)
    _ce_14 = _xf(114.3, 411.226)
    ln14 = lns.addByTwoPoints(ln13.endSketchPoint, ln10.endSketchPoint)
    d = Sketch1_beam.sketchDimensions
    try:
        d.addDistanceDimension(Sketch1_beam.originPoint, ln0.endSketchPoint,
            adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, P(0, 0, 0)).parameter.expression = "perg_x"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln0.endSketchPoint, ln1.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "post_height"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln1.endSketchPoint, ln2.endSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "top_beam_side"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln2.endSketchPoint, ln3.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "top_beam_height"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln3.endSketchPoint, ln4.endSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "top_beam_length + top_beam_side * 2"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln4.endSketchPoint, ln5.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "top_beam_height"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln1.endSketchPoint, ln10.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "stretcher_offset"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln10.endSketchPoint, ln11.endSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "stretcher_w"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln13.endSketchPoint, ln10.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "stretcher_w * 1.5"
    except: pass  # skip if already constrained
    gc = Sketch1_beam.geometricConstraints
    try: gc.addPerpendicular(ln0, _pcurve_1)
    except: pass
    try: gc.addPerpendicular(ln1, _pcurve_2)
    except: pass
    try: gc.addPerpendicular(ln2, ln1)
    except: pass
    try: gc.addPerpendicular(ln3, ln2)
    except: pass
    try: gc.addPerpendicular(ln4, ln3)
    except: pass
    try: gc.addPerpendicular(ln5, ln4)
    except: pass
    try: gc.addMidPoint(ln7.startSketchPoint, ln4)
    except: pass
    try: gc.addCoincident(ln7.endSketchPoint, ln6)
    except: pass
    try: gc.addPerpendicular(ln7, ln6)
    except: pass
    try: gc.addCoincident(spl8.fitPoints.item(0), ln3)
    except: pass
    try: gc.addCoincident(spl8.fitPoints.item(4), ln2)
    except: pass
    try: gc.addSymmetry(spl8.fitPoints.item(0), spl9.fitPoints.item(0), ln7)
    except: pass
    try: gc.addSymmetry(spl8.fitPoints.item(1), spl9.fitPoints.item(1), ln7)
    except: pass
    try: gc.addSymmetry(spl8.fitPoints.item(2), spl9.fitPoints.item(2), ln7)
    except: pass
    try: gc.addSymmetry(spl8.fitPoints.item(3), spl9.fitPoints.item(3), ln7)
    except: pass
    try: gc.addSymmetry(spl8.fitPoints.item(4), spl9.fitPoints.item(4), ln7)
    except: pass
    try: gc.addPerpendicular(ln10, ln2)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln11)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln12)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln13)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln14)
    except: pass
    Sketch1_beam_prof = Sketch1_beam.profiles.item(0)  # 6 profile(s)

    # [36] ComponentCreation: deck5
    comp = root
    deck5_occ = comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    deck5_occ.component.name = "deck5"
    deck5_c = deck5_occ.component

    # [37] Sketch: Sketch1
    comp = deck5_c
    Sketch1_deck5 = comp.sketches.add(find_face_near(ground_Surranding, 304.8, -304.8, 0.0, 0.0, 0.0, 1.0))
    Sketch1_deck5.name = "Sketch1"
    _cap_xd = (-1.0, 0.0, 0.0)
    _cap_yd = (0.0, -1.0, 0.0)
    _act_xd = Sketch1_deck5.xDirection
    _act_yd = Sketch1_deck5.yDirection
    _m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z
    _m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z
    _m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z
    _m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z
    _w0, _h0 = ev("deck_w"), ev("floor_width")
    _x0c, _y0c = ev("-342.9 cm"), ev("0 cm")
    _c1x, _c1y = _x0c*_m00 + _y0c*_m01, _x0c*_m10 + _y0c*_m11
    _c2x, _c2y = (_x0c+_w0)*_m00 + (_y0c+_h0)*_m01, (_x0c+_w0)*_m10 + (_y0c+_h0)*_m11
    x0, y0 = min(_c1x, _c2x), min(_c1y, _c2y)
    w, h = abs(_c2x - _c1x), abs(_c2y - _c1y)
    rect = Sketch1_deck5.sketchCurves.sketchLines.addTwoPointRectangle(
        P(x0, y0, 0), P(x0 + w, y0 + h, 0))
    gc = Sketch1_deck5.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    d = Sketch1_deck5.sketchDimensions
    d.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
        H, P(x0 + w/2, y0 - 1, 0)).parameter.expression = "deck_w"
    d.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
        V, P(x0 + w + 1, y0 + h/2, 0)).parameter.expression = "floor_width"
    _hd = abs(x0)
    if _hd > 0.01:
        d.addDistanceDimension(Sketch1_deck5.originPoint, rect[0].startSketchPoint,
            H, P(x0/2, y0 - 2, 0)).parameter.expression = f"{round(_hd, 4)} cm"
    _vd = abs(y0)
    if _vd > 0.01:
        d.addDistanceDimension(Sketch1_deck5.originPoint, rect[0].startSketchPoint,
            V, P(x0 - 1, y0/2, 0)).parameter.expression = f"{round(_vd, 4)} cm"
    _best_pi, _best_a = 0, float('inf')
    for _pi in range(Sketch1_deck5.profiles.count):
        _bb = Sketch1_deck5.profiles.item(_pi).boundingBox
        _a = abs(_bb.maxPoint.x-_bb.minPoint.x)*abs(_bb.maxPoint.y-_bb.minPoint.y)
        if _a < _best_a: _best_a, _best_pi = _a, _pi
    Sketch1_deck5_prof = Sketch1_deck5.profiles.item(_best_pi)

    # [38] Extrude: Extrude1
    comp = deck5_c
    _cx = (-1.0, 0.0, 0.0)
    _cy = (0.0, -1.0, 0.0)
    _ax = Sketch1_deck5.xDirection
    _ay = Sketch1_deck5.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Match profile by bbox (transformed): (-342.9, 0.0) to (0.0, 10.16)
    _t1 = (-342.9*_m00 + 0.0*_m01, -342.9*_m10 + 0.0*_m11)
    _t2 = (0.0*_m00 + 10.16*_m01, 0.0*_m10 + 10.16*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch1_deck5.profiles.count):
        _bb = Sketch1_deck5.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    inp = comp.features.extrudeFeatures.createInput(Sketch1_deck5.profiles.item(_best_pi), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("floor_thickness"))
    Extrude1 = comp.features.extrudeFeatures.add(inp)
    Extrude1.name = "Extrude1"
    Body1_deck5 = Extrude1.bodies.item(0)
    Body1_deck5.name = "Body1"

    # [39] Fillet: Fillet1
    comp = Surranding_c
    fillet_inp = comp.features.filletFeatures.createInput()
    fillet_edges_0 = adsk.core.ObjectCollection.create()
    _targets = [
        ((0.0, 0.0, 0.0), (609.6, 0.0, 0.0)),
    ]
    _body = wall_Surranding
    if _body:
        for _ei in range(_body.edges.count):
            _e = _body.edges.item(_ei)
            _sv, _ev = _e.startVertex.geometry, _e.endVertex.geometry
            for _ts, _te in _targets:
                if ((abs(_sv.x-_ts[0])+abs(_sv.y-_ts[1])+abs(_sv.z-_ts[2]) < 0.05 and
                     abs(_ev.x-_te[0])+abs(_ev.y-_te[1])+abs(_ev.z-_te[2]) < 0.05) or
                    (abs(_sv.x-_te[0])+abs(_sv.y-_te[1])+abs(_sv.z-_te[2]) < 0.05 and
                     abs(_ev.x-_ts[0])+abs(_ev.y-_ts[1])+abs(_ev.z-_ts[2]) < 0.05)):
                    fillet_edges_0.add(_e)
                    break
    if fillet_edges_0.count > 0:
        fillet_inp.addConstantRadiusEdgeSet(fillet_edges_0, adsk.core.ValueInput.createByString("3.00 mm"), True)
    fillet_feat = comp.features.filletFeatures.add(fillet_inp)
    fillet_feat.name = "Fillet1"

    # [40] Move: Move2
    comp = deck5_c
    xform = adsk.core.Matrix3D.create()
    xform.setWithArray([1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 149.86, 0.0, 0.0, 0.0, 1.0])
    move_coll = adsk.core.ObjectCollection.create()
    move_coll.add(Body1_deck5)
    move_inp = comp.features.moveFeatures.createInput2(move_coll)
    move_inp.defineAsFreeMove(xform)
    move_feat = comp.features.moveFeatures.add(move_inp)
    move_feat.name = "Move2"

    # [41] RectangularPattern: R-Pattern3
    comp = deck5_c
    pat_coll = adsk.core.ObjectCollection.create()
    pat_coll.add(Body1_deck5)
    pat_inp = comp.features.rectangularPatternFeatures.createInput(
        pat_coll,
        root.yConstructionAxis,
        adsk.core.ValueInput.createByString("17"),
        adsk.core.ValueInput.createByString("-(floor_gap + floor_width)"),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType,
    )
    pat_inp.quantityTwo = adsk.core.ValueInput.createByReal(1)
    _before_pat = set(comp.bRepBodies.item(_i).name for _i in range(comp.bRepBodies.count))
    R_Pattern3 = comp.features.rectangularPatternFeatures.add(pat_inp)
    R_Pattern3.name = "R-Pattern3"
    _pat_copies = []
    for _i in range(comp.bRepBodies.count):
        _b = comp.bRepBodies.item(_i)
        if _b.name not in _before_pat:
            _pat_copies.append(_b)
    _pat_copies.sort(key=lambda _b: getattr(_b.boundingBox.minPoint, 'y'))
    if 0 < len(_pat_copies):
        Body117_deck5 = _pat_copies[0]
        Body117_deck5.name = "Body117"
    if 1 < len(_pat_copies):
        Body116_deck5 = _pat_copies[1]
        Body116_deck5.name = "Body116"
    if 2 < len(_pat_copies):
        Body115_deck5 = _pat_copies[2]
        Body115_deck5.name = "Body115"
    if 3 < len(_pat_copies):
        Body114_deck5 = _pat_copies[3]
        Body114_deck5.name = "Body114"
    if 4 < len(_pat_copies):
        Body113_deck5 = _pat_copies[4]
        Body113_deck5.name = "Body113"
    if 5 < len(_pat_copies):
        Body112_deck5 = _pat_copies[5]
        Body112_deck5.name = "Body112"
    if 6 < len(_pat_copies):
        Body111_deck5 = _pat_copies[6]
        Body111_deck5.name = "Body111"
    if 7 < len(_pat_copies):
        Body110_deck5 = _pat_copies[7]
        Body110_deck5.name = "Body110"
    if 8 < len(_pat_copies):
        Body109_deck5 = _pat_copies[8]
        Body109_deck5.name = "Body109"
    if 9 < len(_pat_copies):
        Body108_deck5 = _pat_copies[9]
        Body108_deck5.name = "Body108"
    if 10 < len(_pat_copies):
        Body107_deck5 = _pat_copies[10]
        Body107_deck5.name = "Body107"
    if 11 < len(_pat_copies):
        Body106_deck5 = _pat_copies[11]
        Body106_deck5.name = "Body106"
    if 12 < len(_pat_copies):
        Body105_deck5 = _pat_copies[12]
        Body105_deck5.name = "Body105"
    if 13 < len(_pat_copies):
        Body104_deck5 = _pat_copies[13]
        Body104_deck5.name = "Body104"
    if 14 < len(_pat_copies):
        Body103_deck5 = _pat_copies[14]
        Body103_deck5.name = "Body103"
    if 15 < len(_pat_copies):
        Body102_deck5 = _pat_copies[15]
        Body102_deck5.name = "Body102"

    # [42] Extrude: Extrude1
    comp = beam_c
    _cx = (1.0, 0.0, 0.0)
    _cy = (0.0, 0.0, 1.0)
    _ax = Sketch1_beam.xDirection
    _ay = Sketch1_beam.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Multi-profile extrude: 2 profiles
    _prof_coll = adsk.core.ObjectCollection.create()
    _used = set()
    # Match profile by bbox (transformed): (228.6, 411.48) to (373.38, 426.72)
    _t1 = (228.6*_m00 + 411.48*_m01, 228.6*_m10 + 411.48*_m11)
    _t2 = (373.38*_m00 + 426.72*_m01, 373.38*_m10 + 426.72*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch1_beam.profiles.count):
        if _pi in _used: continue
        _bb = Sketch1_beam.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch1_beam.profiles.item(_best_pi))
    _used.add(_best_pi)
    # Match profile by bbox (transformed): (83.82, 411.48) to (228.6, 426.72)
    _t1 = (83.82*_m00 + 411.48*_m01, 83.82*_m10 + 411.48*_m11)
    _t2 = (228.6*_m00 + 426.72*_m01, 228.6*_m10 + 426.72*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch1_beam.profiles.count):
        if _pi in _used: continue
        _bb = Sketch1_beam.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch1_beam.profiles.item(_best_pi))
    _used.add(_best_pi)
    inp = comp.features.extrudeFeatures.createInput(_prof_coll, NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("top_beam_width"))
    Extrude1 = comp.features.extrudeFeatures.add(inp)
    Extrude1.name = "Extrude1"
    Body1_beam = Extrude1.bodies.item(0)
    Body1_beam.name = "Body1"

    # [43] Move: Move4
    comp = beam_c
    xform = adsk.core.Matrix3D.create()
    xform.setWithArray([1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, -168.91, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0])
    move_coll = adsk.core.ObjectCollection.create()
    move_coll.add(Body1_beam)
    move_inp = comp.features.moveFeatures.createInput2(move_coll)
    move_inp.defineAsFreeMove(xform)
    move_feat = comp.features.moveFeatures.add(move_inp)
    move_feat.name = "Move4"

    # [44] ConstructionPlane: Plane3
    comp = beam_c
    # BRepFace base → computed offset from origin [228.6, -16.51, 419.1]
    Plane3_beam = off_plane(comp, comp.xZConstructionPlane, "-16.51 cm", "Plane3")

    # [45] CopyPasteBody: CopyPasteBodies1
    comp = beam_c
    _cpb = comp.features.copyPasteBodies.add(Body1_beam)
    _cpb_body = _cpb.bodies.item(0)
    _cpb_body.name = "Body2"
    Body2_beam = find_body("Body2", beam_c)
    Body2_bb = Body2_beam.boundingBox  # body-relative reference for Body4, Body6

    # [46] Move: Align1
    comp = beam_c
    xform = adsk.core.Matrix3D.create()
    xform.setWithArray([1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 152.4, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0])
    move_coll = adsk.core.ObjectCollection.create()
    move_coll.add(Body2_beam)
    move_inp = comp.features.moveFeatures.createInput2(move_coll)
    move_inp.defineAsFreeMove(xform)
    move_feat = comp.features.moveFeatures.add(move_inp)
    move_feat.name = "Align1"

    # Body-relative reference: stretcher (Body3) refs top beam (Body1)
    ref_body1 = find_body("Body1", beam_c)
    ref_body1_bb = ref_body1.boundingBox

    # [47] Extrude: Extrude2
    comp = beam_c
    _cx = (1.0, 0.0, 0.0)
    _cy = (0.0, 0.0, 1.0)
    _ax = Sketch1_beam.xDirection
    _ay = Sketch1_beam.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Match profile by bbox (transformed): (114.3, 397.891) to (123.19, 411.226)
    _t1 = (114.3*_m00 + 397.891*_m01, 114.3*_m10 + 397.891*_m11)
    _t2 = (123.19*_m00 + 411.226*_m01, 123.19*_m10 + 411.226*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch1_beam.profiles.count):
        _bb = Sketch1_beam.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    inp = comp.features.extrudeFeatures.createInput(Sketch1_beam.profiles.item(_best_pi), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("deck_d - post_w"))
    Extrude2 = comp.features.extrudeFeatures.add(inp)
    Extrude2.name = "Extrude2"
    Body3_beam = Extrude2.bodies.item(0)
    Body3_beam.name = "Body3"

    # [48] Sketch: Sketch4
    comp = beam_c
    # Native face sketch: Sketch4 (cross-body refs)
    _native_face = find_face_in_comp(comp, 114.3, -84.455, 404.5585, -1.0, 0.0, 0.0)
    if not _native_face: _native_face = find_face_near(find_body("Body3"), 114.3, -84.455, 404.5585, -1.0, 0.0, 0.0)
    Sketch4_beam = comp.sketches.add(_native_face)
    Sketch4_beam.name = "Sketch4"
    lns = Sketch4_beam.sketchCurves.sketchLines
    # Coordinate transform: captured sketch axes -> actual sketch axes
    _cap_xd = (0.0, -1.0, 0.0)
    _cap_yd = (0.0, 0.0, 1.0)
    _act_xd = Sketch4_beam.xDirection
    _act_yd = Sketch4_beam.yDirection
    _m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z
    _m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z
    _m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z
    _m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z
    def _xf(sx, sy):
        return (sx * _m00 + sy * _m01, sx * _m10 + sy * _m11)
    # Intersect body 'Body2' with sketch plane
    _bodies_Body2 = []
    for _bi in range(comp.bRepBodies.count):
        if comp.bRepBodies.item(_bi).name == "Body2":
            _bodies_Body2.append(comp.bRepBodies.item(_bi))
    if not _bodies_Body2:
        for _occ in root.allOccurrences:
            for _bi in range(_occ.bRepBodies.count):
                if _occ.bRepBodies.item(_bi).name == "Body2":
                    _bodies_Body2.append(_occ.bRepBodies.item(_bi))
    if _bodies_Body2: _proj_body_Body2 = Sketch4_beam.intersectWithSketchPlane(_bodies_Body2)
    _proj_pts = []  # [(x, y, sketchPoint), ...]
    _proj_curves = []  # [(sx, sy, ex, ey, curve), ...]
    for _ci in range(Sketch4_beam.sketchCurves.count):
        _c = Sketch4_beam.sketchCurves.item(_ci)
        if _c.isReference:
            for _sp in [_c.startSketchPoint, _c.endSketchPoint]:
                _g = _sp.geometry
                _proj_pts.append((_g.x, _g.y, _sp))
            _s, _e = _c.startSketchPoint.geometry, _c.endSketchPoint.geometry
            _proj_curves.append((_s.x, _s.y, _e.x, _e.y, _c))

    _fallback_pts = {}
    def _nearest_proj(x, y):
        best, best_d = None, 1e10
        for _px, _py, _sp in _proj_pts:
            _d = abs(_px - x) + abs(_py - y)
            if _d < best_d: best, best_d = _sp, _d
        if best_d > 5.0: best = None
        if best is None:
            _fk = (round(x,2), round(y,2))
            best = _fallback_pts.get(_fk)
        if best is None:
            best = Sketch4_beam.sketchPoints.add(P(x, y, 0))
        return best

    def _nearest_proj_curve(sx, sy, ex, ey):
        best, best_d = None, 1e10
        for _sx, _sy, _ex, _ey, _c in _proj_curves:
            _d = min(abs(_sx-sx)+abs(_sy-sy)+abs(_ex-ex)+abs(_ey-ey),
                    abs(_sx-ex)+abs(_sy-ey)+abs(_ex-sx)+abs(_ey-sy))
            if _d < best_d: best, best_d = _c, _d
        if best_d > 10.0: best = None
        if best is None:
            _sk = (round(sx,2), round(sy,2))
            _ek = (round(ex,2), round(ey,2))
            _sp = _fallback_pts.get(_sk)
            _ep = _fallback_pts.get(_ek)
            if _sp and _ep:
                best = Sketch4_beam.sketchCurves.sketchLines.addByTwoPoints(_sp, _ep)
            elif _sp:
                best = Sketch4_beam.sketchCurves.sketchLines.addByTwoPoints(_sp, P(ex, ey, 0))
                _fallback_pts[_ek] = best.endSketchPoint
            elif _ep:
                best = Sketch4_beam.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), _ep)
                _fallback_pts[_sk] = best.startSketchPoint
            else:
                best = Sketch4_beam.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), P(ex, ey, 0))
                _fallback_pts[_sk] = best.startSketchPoint
                _fallback_pts[_ek] = best.endSketchPoint
            try: Sketch4_beam.geometricConstraints.addFix(best)
            except: pass
        return best
    _pcurve_0 = _nearest_proj_curve(*_xf(0.0, 411.226), *_xf(0.0, 397.891))
    _pcurve_1 = _nearest_proj_curve(*_xf(0.0, 397.891), *_xf(168.91, 397.891))
    _pcurve_2 = _nearest_proj_curve(*_xf(168.91, 397.891), *_xf(168.91, 411.226))
    _pcurve_3 = _nearest_proj_curve(*_xf(168.91, 411.226), *_xf(0.0, 411.226))
    _pcurve_4 = _nearest_proj_curve(*_xf(16.51, 411.48), *_xf(25.4, 411.48))
    _cs_1 = _xf(25.4, 411.48)
    _ce_1 = _xf(25.4, 411.226)
    ln1 = lns.addByTwoPoints(P(_cs_1[0], _cs_1[1], 0), P(_ce_1[0], _ce_1[1], 0))
    _cs_2 = _xf(25.4, 411.226)
    _ce_2 = _xf(30.4, 411.226)
    ln2 = lns.addByTwoPoints(ln1.endSketchPoint, P(_ce_2[0], _ce_2[1], 0))
    _cs_3 = _xf(30.4, 411.226)
    _ce_3 = _xf(30.4, 406.226)
    ln3 = lns.addByTwoPoints(ln2.endSketchPoint, P(_ce_3[0], _ce_3[1], 0))
    _cc_4 = _xf(30.4, 411.226)
    circ4 = Sketch4_beam.sketchCurves.sketchCircles.addByCenterRadius(P(_cc_4[0], _cc_4[1], 0), 5.0)
    _cs_5 = _xf(30.4, 406.226)
    _ce_5 = _xf(168.91, 406.226)
    ln5 = lns.addByTwoPoints(ln3.endSketchPoint, P(_ce_5[0], _ce_5[1], 0))
    d = Sketch4_beam.sketchDimensions
    try:
        d.addDistanceDimension(ln1.endSketchPoint, ln2.endSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "beam_recess"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln2.endSketchPoint, ln3.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "beam_recess"
    except: pass  # skip if already constrained
    d.addDiameterDimension(circ4, P(11.0, 0, 0)).parameter.expression = "beam_recess * 2"
    gc = Sketch4_beam.geometricConstraints
    try: gc.addCoincident(ln1.endSketchPoint, _pcurve_3)
    except: pass
    try: gc.addPerpendicular(ln1, _pcurve_3)
    except: pass
    try: gc.addPerpendicular(ln2, ln1)
    except: pass
    try: gc.addPerpendicular(ln3, ln2)
    except: pass
    try: gc.addCoincident(ln5.endSketchPoint, _pcurve_2)
    except: pass
    try: gc.addTangent(ln5, circ4)
    except: pass
    try: gc.addPerpendicular(ln5, _pcurve_2)
    except: pass
    Sketch4_beam_prof = Sketch4_beam.profiles.item(0)  # 5 profile(s)

    # [49] Extrude: Extrude5
    comp = beam_c
    _cx = (0.0, -1.0, 0.0)
    _cy = (0.0, 0.0, 1.0)
    _ax = Sketch4_beam.xDirection
    _ay = Sketch4_beam.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Multi-profile extrude: 3 profiles
    _prof_coll = adsk.core.ObjectCollection.create()
    _used = set()
    # Match profile by bbox (transformed): (30.4, 406.226) to (35.4, 411.226)
    _t1 = (30.4*_m00 + 406.226*_m01, 30.4*_m10 + 406.226*_m11)
    _t2 = (35.4*_m00 + 411.226*_m01, 35.4*_m10 + 411.226*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch4_beam.profiles.count):
        if _pi in _used: continue
        _bb = Sketch4_beam.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch4_beam.profiles.item(_best_pi))
    _used.add(_best_pi)
    # Match profile by bbox (transformed): (30.4, 406.226) to (168.91, 411.226)
    _t1 = (30.4*_m00 + 406.226*_m01, 30.4*_m10 + 406.226*_m11)
    _t2 = (168.91*_m00 + 411.226*_m01, 168.91*_m10 + 411.226*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch4_beam.profiles.count):
        if _pi in _used: continue
        _bb = Sketch4_beam.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch4_beam.profiles.item(_best_pi))
    _used.add(_best_pi)
    # Match profile by bbox (transformed): (25.4, 406.226) to (30.4, 411.226)
    _t1 = (25.4*_m00 + 406.226*_m01, 25.4*_m10 + 406.226*_m11)
    _t2 = (30.4*_m00 + 411.226*_m01, 30.4*_m10 + 411.226*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch4_beam.profiles.count):
        if _pi in _used: continue
        _bb = Sketch4_beam.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch4_beam.profiles.item(_best_pi))
    _used.add(_best_pi)
    inp = comp.features.extrudeFeatures.createInput(_prof_coll, CUT)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("-stretcher_w"))
    inp.participantBodies = [Body3_beam]
    Extrude5 = comp.features.extrudeFeatures.add(inp)
    Extrude5.name = "Extrude5"
    Body3_beam = Extrude5.bodies.item(0)
    Body3_beam.name = "Body3"

    # [50] Sketch: Sketch2
    comp = beam_c
    Sketch2_beam = comp.sketches.add(find_face_near(Body3_beam, 121.7083, -168.91, 402.0585, 0.0, -1.0, 0.0))
    Sketch2_beam.name = "Sketch2"
    lns = Sketch2_beam.sketchCurves.sketchLines
    # Coordinate transform: captured sketch axes -> actual sketch axes
    _cap_xd = (1.0, 0.0, 0.0)
    _cap_yd = (0.0, 0.0, 1.0)
    _act_xd = Sketch2_beam.xDirection
    _act_yd = Sketch2_beam.yDirection
    _m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z
    _m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z
    _m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z
    _m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z
    def _xf(sx, sy):
        return (sx * _m00 + sy * _m01, sx * _m10 + sy * _m11)
    _proj_pts = []  # [(x, y, sketchPoint), ...]
    _proj_curves = []  # [(sx, sy, ex, ey, curve), ...]
    for _ci in range(Sketch2_beam.sketchCurves.count):
        _c = Sketch2_beam.sketchCurves.item(_ci)
        if _c.isReference:
            for _sp in [_c.startSketchPoint, _c.endSketchPoint]:
                _g = _sp.geometry
                _proj_pts.append((_g.x, _g.y, _sp))
            _s, _e = _c.startSketchPoint.geometry, _c.endSketchPoint.geometry
            _proj_curves.append((_s.x, _s.y, _e.x, _e.y, _c))

    _fallback_pts = {}
    def _nearest_proj(x, y):
        best, best_d = None, 1e10
        for _px, _py, _sp in _proj_pts:
            _d = abs(_px - x) + abs(_py - y)
            if _d < best_d: best, best_d = _sp, _d
        if best_d > 5.0: best = None
        if best is None:
            _fk = (round(x,2), round(y,2))
            best = _fallback_pts.get(_fk)
        if best is None:
            best = Sketch2_beam.sketchPoints.add(P(x, y, 0))
        return best

    def _nearest_proj_curve(sx, sy, ex, ey):
        best, best_d = None, 1e10
        for _sx, _sy, _ex, _ey, _c in _proj_curves:
            _d = min(abs(_sx-sx)+abs(_sy-sy)+abs(_ex-ex)+abs(_ey-ey),
                    abs(_sx-ex)+abs(_sy-ey)+abs(_ex-sx)+abs(_ey-sy))
            if _d < best_d: best, best_d = _c, _d
        if best_d > 10.0: best = None
        if best is None:
            _sk = (round(sx,2), round(sy,2))
            _ek = (round(ex,2), round(ey,2))
            _sp = _fallback_pts.get(_sk)
            _ep = _fallback_pts.get(_ek)
            if _sp and _ep:
                best = Sketch2_beam.sketchCurves.sketchLines.addByTwoPoints(_sp, _ep)
            elif _sp:
                best = Sketch2_beam.sketchCurves.sketchLines.addByTwoPoints(_sp, P(ex, ey, 0))
                _fallback_pts[_ek] = best.endSketchPoint
            elif _ep:
                best = Sketch2_beam.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), _ep)
                _fallback_pts[_sk] = best.startSketchPoint
            else:
                best = Sketch2_beam.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), P(ex, ey, 0))
                _fallback_pts[_sk] = best.startSketchPoint
                _fallback_pts[_ek] = best.endSketchPoint
            try: Sketch2_beam.geometricConstraints.addFix(best)
            except: pass
        return best
    _pcurve_0 = _nearest_proj_curve(*_xf(114.3, 397.891), *_xf(123.19, 397.891))
    _pcurve_1 = _nearest_proj_curve(*_xf(123.19, 397.891), *_xf(123.19, 406.226))
    _pcurve_2 = _nearest_proj_curve(*_xf(114.3, 406.226), *_xf(114.3, 397.891))
    _pcurve_8 = _nearest_proj_curve(*_xf(123.19, 406.226), *_xf(114.3, 406.226))
    _cs_0 = _xf(114.3, 406.226)
    _ce_0 = _xf(117.2633, 406.226)
    ln0 = lns.addByTwoPoints(P(_cs_0[0], _cs_0[1], 0), P(_ce_0[0], _ce_0[1], 0))
    _cs_1 = _xf(117.2633, 406.226)
    _ce_1 = _xf(120.2267, 406.226)
    ln1 = lns.addByTwoPoints(ln0.endSketchPoint, P(_ce_1[0], _ce_1[1], 0))
    _cs_2 = _xf(120.2267, 406.226)
    _ce_2 = _xf(120.2267, 397.891)
    ln2 = lns.addByTwoPoints(ln1.endSketchPoint, P(_ce_2[0], _ce_2[1], 0))
    _cs_3 = _xf(120.2267, 397.891)
    _ce_3 = _xf(117.2633, 397.891)
    ln3 = lns.addByTwoPoints(ln2.endSketchPoint, P(_ce_3[0], _ce_3[1], 0))
    _cs_4 = _xf(117.2633, 397.891)
    _ce_4 = _xf(117.2633, 406.226)
    ln4 = lns.addByTwoPoints(ln3.endSketchPoint, ln0.endSketchPoint)
    d = Sketch2_beam.sketchDimensions
    try:
        d.addDistanceDimension(_nearest_proj(*_xf(114.3, 406.226)), ln0.endSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "stretcher_w / 3"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln0.endSketchPoint, ln1.endSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "stretcher_w / 3"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln3.endSketchPoint, ln0.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "stretcher_w * 1.5 - beam_recess"
    except: pass  # skip if already constrained
    gc = Sketch2_beam.geometricConstraints
    try: gc.addPerpendicular(ln0, _pcurve_2)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln1)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln2)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln3)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln4)
    except: pass
    Sketch2_beam_prof = Sketch2_beam.profiles.item(0)  # 3 profile(s)

    # [51] Extrude: Extrude3
    comp = beam_c
    _cx = (1.0, 0.0, 0.0)
    _cy = (0.0, 0.0, 1.0)
    _ax = Sketch2_beam.xDirection
    _ay = Sketch2_beam.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Match profile by bbox (transformed): (117.2633, 397.891) to (120.2267, 406.226)
    _t1 = (117.2633*_m00 + 397.891*_m01, 117.2633*_m10 + 397.891*_m11)
    _t2 = (120.2267*_m00 + 406.226*_m01, 120.2267*_m10 + 406.226*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch2_beam.profiles.count):
        _bb = Sketch2_beam.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    inp = comp.features.extrudeFeatures.createInput(Sketch2_beam.profiles.item(_best_pi), JOIN)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("post_w * 3 / 4"))
    inp.participantBodies = [Body3_beam]
    Extrude3 = comp.features.extrudeFeatures.add(inp)
    Extrude3.name = "Extrude3"
    Body3_beam = Extrude3.bodies.item(0)
    Body3_beam.name = "Body3"

    # [52] ConstructionPlane: Plane1
    comp = beam_c
    _pl_inp = comp.constructionPlanes.createInput()
    _pl_inp.setByTwoPlanes(find_face_near(Body2_beam, 373.38, -20.955, 423.9959), find_face_near(Body2_beam, 83.82, -20.955, 423.9959))
    Plane1_beam = comp.constructionPlanes.add(_pl_inp)
    Plane1_beam.name = "Plane1"

    # [53] Mirror: Mirror1
    comp = beam_c
    Mirror1 = mirror_feats(comp, [Body3_beam], Plane1_beam, "Mirror1")
    Body4_beam = Mirror1.bodies.item(0)
    Body4_beam.name = "Body4"
    Body3_beam = Mirror1.bodies.item(1)
    Body3_beam.name = "Body3"

    # [54] Sketch: Sketch3
    comp = beam_c
    Sketch3_beam = comp.sketches.add(find_face_near(Body3_beam, 118.745, -102.9888, 406.226, 0.0, 0.0, -1.0))
    Sketch3_beam.name = "Sketch3"
    lns = Sketch3_beam.sketchCurves.sketchLines
    # Coordinate transform: captured sketch axes -> actual sketch axes
    _cap_xd = (-1.0, 0.0, 0.0)
    _cap_yd = (0.0, -1.0, 0.0)
    _act_xd = Sketch3_beam.xDirection
    _act_yd = Sketch3_beam.yDirection
    _m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z
    _m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z
    _m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z
    _m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z
    def _xf(sx, sy):
        return (sx * _m00 + sy * _m01, sx * _m10 + sy * _m11)
    _proj_pts = []  # [(x, y, sketchPoint), ...]
    _proj_curves = []  # [(sx, sy, ex, ey, curve), ...]
    for _ci in range(Sketch3_beam.sketchCurves.count):
        _c = Sketch3_beam.sketchCurves.item(_ci)
        if _c.isReference:
            for _sp in [_c.startSketchPoint, _c.endSketchPoint]:
                _g = _sp.geometry
                _proj_pts.append((_g.x, _g.y, _sp))
            _s, _e = _c.startSketchPoint.geometry, _c.endSketchPoint.geometry
            _proj_curves.append((_s.x, _s.y, _e.x, _e.y, _c))

    _fallback_pts = {}
    def _nearest_proj(x, y):
        best, best_d = None, 1e10
        for _px, _py, _sp in _proj_pts:
            _d = abs(_px - x) + abs(_py - y)
            if _d < best_d: best, best_d = _sp, _d
        if best_d > 5.0: best = None
        if best is None:
            _fk = (round(x,2), round(y,2))
            best = _fallback_pts.get(_fk)
        if best is None:
            best = Sketch3_beam.sketchPoints.add(P(x, y, 0))
        return best

    def _nearest_proj_curve(sx, sy, ex, ey):
        best, best_d = None, 1e10
        for _sx, _sy, _ex, _ey, _c in _proj_curves:
            _d = min(abs(_sx-sx)+abs(_sy-sy)+abs(_ex-ex)+abs(_ey-ey),
                    abs(_sx-ex)+abs(_sy-ey)+abs(_ex-sx)+abs(_ey-sy))
            if _d < best_d: best, best_d = _c, _d
        if best_d > 10.0: best = None
        if best is None:
            _sk = (round(sx,2), round(sy,2))
            _ek = (round(ex,2), round(ey,2))
            _sp = _fallback_pts.get(_sk)
            _ep = _fallback_pts.get(_ek)
            if _sp and _ep:
                best = Sketch3_beam.sketchCurves.sketchLines.addByTwoPoints(_sp, _ep)
            elif _sp:
                best = Sketch3_beam.sketchCurves.sketchLines.addByTwoPoints(_sp, P(ex, ey, 0))
                _fallback_pts[_ek] = best.endSketchPoint
            elif _ep:
                best = Sketch3_beam.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), _ep)
                _fallback_pts[_sk] = best.startSketchPoint
            else:
                best = Sketch3_beam.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), P(ex, ey, 0))
                _fallback_pts[_sk] = best.startSketchPoint
                _fallback_pts[_ek] = best.endSketchPoint
            try: Sketch3_beam.geometricConstraints.addFix(best)
            except: pass
        return best
    _pcurve_0 = _nearest_proj_curve(*_xf(-114.3, 30.4), *_xf(-114.3, 168.91))
    _pcurve_1 = _nearest_proj_curve(*_xf(-114.3, 168.91), *_xf(-117.2633, 168.91))
    _pcurve_2 = _nearest_proj_curve(*_xf(-117.2633, 168.91), *_xf(-117.2633, 175.5775))
    _pcurve_3 = _nearest_proj_curve(*_xf(-117.2633, 175.5775), *_xf(-120.2267, 175.5775))
    _pcurve_4 = _nearest_proj_curve(*_xf(-120.2267, 175.5775), *_xf(-120.2267, 168.91))
    _pcurve_5 = _nearest_proj_curve(*_xf(-120.2267, 168.91), *_xf(-123.19, 168.91))
    _pcurve_6 = _nearest_proj_curve(*_xf(-123.19, 168.91), *_xf(-123.19, 30.4))
    _pcurve_12 = _nearest_proj_curve(*_xf(-123.19, 30.4), *_xf(-114.3, 30.4))
    _cs_0 = _xf(-114.3, 30.4)
    _ce_0 = _xf(-114.3, 16.51)
    ln0 = lns.addByTwoPoints(P(_cs_0[0], _cs_0[1], 0), P(_ce_0[0], _ce_0[1], 0))
    _cs_1 = _xf(-114.3, 16.51)
    _ce_1 = _xf(-123.19, 16.51)
    ln1 = lns.addByTwoPoints(ln0.endSketchPoint, P(_ce_1[0], _ce_1[1], 0))
    _cs_2 = _xf(-123.19, 16.51)
    _ce_2 = _xf(-123.19, 25.4)
    ln2 = lns.addByTwoPoints(ln1.endSketchPoint, P(_ce_2[0], _ce_2[1], 0))
    _cs_3 = _xf(-123.19, 25.4)
    _ce_3 = _xf(-114.3, 25.4)
    ln3 = lns.addByTwoPoints(ln2.endSketchPoint, P(_ce_3[0], _ce_3[1], 0))
    _cs_4 = _xf(-114.3, 25.4)
    _ce_4 = _xf(-114.3, 16.51)
    ln4 = lns.addByTwoPoints(ln3.endSketchPoint, ln0.endSketchPoint)
    d = Sketch3_beam.sketchDimensions
    try:
        d.addDistanceDimension(_nearest_proj(*_xf(-114.3, 30.4)), ln0.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "beam_recess + post_w"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln0.endSketchPoint, ln1.endSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "post_w"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln3.endSketchPoint, ln0.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "post_w"
    except: pass  # skip if already constrained
    gc = Sketch3_beam.geometricConstraints
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln1)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln2)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln3)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln4)
    except: pass
    Sketch3_beam_prof = Sketch3_beam.profiles.item(0)  # 2 profile(s)

    # [55] Extrude: Extrude4
    comp = beam_c
    _cx = (-1.0, 0.0, 0.0)
    _cy = (0.0, -1.0, 0.0)
    _ax = Sketch3_beam.xDirection
    _ay = Sketch3_beam.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Match profile by bbox (transformed): (-123.19, 16.51) to (-114.3, 25.4)
    _t1 = (-123.19*_m00 + 16.51*_m01, -123.19*_m10 + 16.51*_m11)
    _t2 = (-114.3*_m00 + 25.4*_m01, -114.3*_m10 + 25.4*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch3_beam.profiles.count):
        _bb = Sketch3_beam.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    inp = comp.features.extrudeFeatures.createInput(Sketch3_beam.profiles.item(_best_pi), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("stretcher_offset"))
    Extrude4 = comp.features.extrudeFeatures.add(inp)
    Extrude4.name = "Extrude4"
    Body5_beam = Extrude4.bodies.item(0)
    Body5_beam.name = "Body5"

    # [56] Move: Move6
    comp = beam_c
    xform = adsk.core.Matrix3D.create()
    xform.setWithArray([1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0])
    move_coll = adsk.core.ObjectCollection.create()
    move_coll.add(Body5_beam)
    move_inp = comp.features.moveFeatures.createInput2(move_coll)
    move_inp.defineAsFreeMove(xform)
    move_feat = comp.features.moveFeatures.add(move_inp)
    move_feat.name = "Move6"

    # [57] Mirror: Mirror2
    comp = beam_c
    Mirror2 = mirror_feats(comp, [Body5_beam], Plane1_beam, "Mirror2")
    Body6_beam = Mirror2.bodies.item(0)
    Body6_beam.name = "Body6"
    Body5_beam = Mirror2.bodies.item(1)
    Body5_beam.name = "Body5"

    # Body-relative reference: rafters ref stretcher (Body3)
    ref_body3 = find_body("Body3", beam_c)
    ref_body3_bb = ref_body3.boundingBox

    # [58] ComponentCreation: rafts (1)
    comp = root
    rafts_1_occ = comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    rafts_1_occ.component.name = "rafts (1)"
    rafts_1_c = rafts_1_occ.component

    # [59] ConstructionPlane: Plane1
    comp = rafts_1_c
    _pl_inp = comp.constructionPlanes.createInput()
    _pl_inp.setByTwoPlanes(find_face_near(Body2_beam, 83.82, -20.955, 423.9959), find_face_near(Body2_beam, 373.38, -20.955, 423.9959))
    Plane1_rafts_1 = comp.constructionPlanes.add(_pl_inp)
    Plane1_rafts_1.name = "Plane1"

    # [60] Sketch: Sketch1
    comp = rafts_1_c
    Sketch1_rafts_1 = comp.sketches.add(Plane1_rafts_1)
    Sketch1_rafts_1.name = "Sketch1"
    lns = Sketch1_rafts_1.sketchCurves.sketchLines
    # Coordinate transform: captured sketch axes -> actual sketch axes
    _cap_xd = (0.0, -1.0, 0.0)
    _cap_yd = (0.0, 0.0, 1.0)
    _act_xd = Sketch1_rafts_1.xDirection
    _act_yd = Sketch1_rafts_1.yDirection
    _m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z
    _m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z
    _m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z
    _m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z
    def _xf(sx, sy):
        return (sx * _m00 + sy * _m01, sx * _m10 + sy * _m11)
    # Intersect body 'Body2' with sketch plane
    _bodies_Body2 = []
    for _occ in root.allOccurrences:
        if _occ.component.name == "beam":
            for _bi in range(_occ.bRepBodies.count):
                if _occ.bRepBodies.item(_bi).name == "Body2":
                    _bodies_Body2.append(_occ.bRepBodies.item(_bi))
            break
    if _bodies_Body2: _proj_body_Body2 = Sketch1_rafts_1.intersectWithSketchPlane(_bodies_Body2)
    _proj_pts = []  # [(x, y, sketchPoint), ...]
    _proj_curves = []  # [(sx, sy, ex, ey, curve), ...]
    for _ci in range(Sketch1_rafts_1.sketchCurves.count):
        _c = Sketch1_rafts_1.sketchCurves.item(_ci)
        if _c.isReference:
            for _sp in [_c.startSketchPoint, _c.endSketchPoint]:
                _g = _sp.geometry
                _proj_pts.append((_g.x, _g.y, _sp))
            _s, _e = _c.startSketchPoint.geometry, _c.endSketchPoint.geometry
            _proj_curves.append((_s.x, _s.y, _e.x, _e.y, _c))

    _fallback_pts = {}
    def _nearest_proj(x, y):
        best, best_d = None, 1e10
        for _px, _py, _sp in _proj_pts:
            _d = abs(_px - x) + abs(_py - y)
            if _d < best_d: best, best_d = _sp, _d
        if best_d > 5.0: best = None
        if best is None:
            _fk = (round(x,2), round(y,2))
            best = _fallback_pts.get(_fk)
        if best is None:
            best = Sketch1_rafts_1.sketchPoints.add(P(x, y, 0))
        return best

    def _nearest_proj_curve(sx, sy, ex, ey):
        best, best_d = None, 1e10
        for _sx, _sy, _ex, _ey, _c in _proj_curves:
            _d = min(abs(_sx-sx)+abs(_sy-sy)+abs(_ex-ex)+abs(_ey-ey),
                    abs(_sx-ex)+abs(_sy-ey)+abs(_ex-sx)+abs(_ey-sy))
            if _d < best_d: best, best_d = _c, _d
        if best_d > 10.0: best = None
        if best is None:
            _sk = (round(sx,2), round(sy,2))
            _ek = (round(ex,2), round(ey,2))
            _sp = _fallback_pts.get(_sk)
            _ep = _fallback_pts.get(_ek)
            if _sp and _ep:
                best = Sketch1_rafts_1.sketchCurves.sketchLines.addByTwoPoints(_sp, _ep)
            elif _sp:
                best = Sketch1_rafts_1.sketchCurves.sketchLines.addByTwoPoints(_sp, P(ex, ey, 0))
                _fallback_pts[_ek] = best.endSketchPoint
            elif _ep:
                best = Sketch1_rafts_1.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), _ep)
                _fallback_pts[_sk] = best.startSketchPoint
            else:
                best = Sketch1_rafts_1.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), P(ex, ey, 0))
                _fallback_pts[_sk] = best.startSketchPoint
                _fallback_pts[_ek] = best.endSketchPoint
            try: Sketch1_rafts_1.geometricConstraints.addFix(best)
            except: pass
        return best
    _pcurve_0 = _nearest_proj_curve(*_xf(16.51, 411.48), *_xf(25.4, 411.48))
    _pcurve_1 = _nearest_proj_curve(*_xf(25.4, 411.48), *_xf(25.4, 426.72))
    _pcurve_2 = _nearest_proj_curve(*_xf(25.4, 426.72), *_xf(16.51, 426.72))
    _pcurve_3 = _nearest_proj_curve(*_xf(16.51, 426.72), *_xf(16.51, 411.48))
    _cs_4 = _xf(16.51, 426.72)
    _ce_4 = _xf(4.4133, 426.72)
    _pp_4s = _nearest_proj(_cs_4[0], _cs_4[1])
    _pg_4s = _pp_4s.geometry
    _dx_4 = _ce_4[0] - _cs_4[0]
    _dy_4 = _ce_4[1] - _cs_4[1]
    ln4 = lns.addByTwoPoints(P(_pg_4s.x, _pg_4s.y, 0), P(_pg_4s.x + _dx_4, _pg_4s.y + _dy_4, 0))
    Sketch1_rafts_1.geometricConstraints.addCoincident(ln4.startSketchPoint, _pp_4s)
    _cs_5 = _xf(4.4133, 426.72)
    _ce_5 = _xf(4.4133, 421.64)
    ln5 = lns.addByTwoPoints(ln4.endSketchPoint, P(_ce_5[0], _ce_5[1], 0))
    _cs_6 = _xf(4.4133, 421.64)
    _ce_6 = _xf(189.8968, 421.64)
    ln6 = lns.addByTwoPoints(ln5.endSketchPoint, P(_ce_6[0], _ce_6[1], 0))
    _cs_7 = _xf(189.8968, 421.64)
    _ce_7 = _xf(189.8968, 430.53)
    ln7 = lns.addByTwoPoints(ln6.endSketchPoint, P(_ce_7[0], _ce_7[1], 0))
    _cs_8 = _xf(189.8968, 430.53)
    _ce_8 = _xf(4.4133, 430.53)
    ln8 = lns.addByTwoPoints(ln7.endSketchPoint, P(_ce_8[0], _ce_8[1], 0))
    _cs_9 = _xf(4.4133, 430.53)
    _ce_9 = _xf(4.4133, 421.64)
    ln9 = lns.addByTwoPoints(ln8.endSketchPoint, ln5.endSketchPoint)
    _cc_10 = _xf(4.4133, 421.64)
    circ10 = Sketch1_rafts_1.sketchCurves.sketchCircles.addByCenterRadius(P(_cc_10[0], _cc_10[1], 0), 5.9267)
    _cc_11 = _xf(189.8968, 421.64)
    circ11 = Sketch1_rafts_1.sketchCurves.sketchCircles.addByCenterRadius(P(_cc_11[0], _cc_11[1], 0), 5.9267)
    d = Sketch1_rafts_1.sketchDimensions
    try:
        d.addDistanceDimension(_nearest_proj(*_xf(16.51, 426.72)), ln4.endSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "( rafter_length - perg_d - post_w ) / 2"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln4.endSketchPoint, ln5.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "rafter_offset"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln5.endSketchPoint, ln6.endSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "rafter_length"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln8.endSketchPoint, ln5.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "rafter_h"
    except: pass  # skip if already constrained
    d.addDiameterDimension(circ10, P(12.853333, 0, 0)).parameter.expression = "rafter_h * 4 / 3"
    d.addDiameterDimension(circ11, P(12.853333, 0, 0)).parameter.expression = "rafter_h * 4 / 3"
    gc = Sketch1_rafts_1.geometricConstraints
    try: gc.addPerpendicular(ln4, _pcurve_3)
    except: pass
    try: gc.addPerpendicular(ln5, ln4)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln6)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln7)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln8)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln9)
    except: pass
    Sketch1_rafts_1_prof = Sketch1_rafts_1.profiles.item(0)  # 9 profile(s)

    # [61] Extrude: Extrude1
    comp = rafts_1_c
    _cx = (0.0, -1.0, 0.0)
    _cy = (0.0, 0.0, 1.0)
    _ax = Sketch1_rafts_1.xDirection
    _ay = Sketch1_rafts_1.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Multi-profile extrude: 3 profiles
    _prof_coll = adsk.core.ObjectCollection.create()
    _used = set()
    # Match profile by bbox (transformed): (16.51, 421.64) to (25.4, 426.72)
    _t1 = (16.51*_m00 + 421.64*_m01, 16.51*_m10 + 421.64*_m11)
    _t2 = (25.4*_m00 + 426.72*_m01, 25.4*_m10 + 426.72*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch1_rafts_1.profiles.count):
        if _pi in _used: continue
        _bb = Sketch1_rafts_1.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch1_rafts_1.profiles.item(_best_pi))
    _used.add(_best_pi)
    # Match profile by bbox (transformed): (4.4133, 421.64) to (189.8968, 430.53)
    _t1 = (4.4133*_m00 + 421.64*_m01, 4.4133*_m10 + 421.64*_m11)
    _t2 = (189.8968*_m00 + 430.53*_m01, 189.8968*_m10 + 430.53*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch1_rafts_1.profiles.count):
        if _pi in _used: continue
        _bb = Sketch1_rafts_1.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch1_rafts_1.profiles.item(_best_pi))
    _used.add(_best_pi)
    # Match profile by bbox (transformed): (7.466, 421.64) to (16.51, 426.72)
    _t1 = (7.466*_m00 + 421.64*_m01, 7.466*_m10 + 421.64*_m11)
    _t2 = (16.51*_m00 + 426.72*_m01, 16.51*_m10 + 426.72*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch1_rafts_1.profiles.count):
        if _pi in _used: continue
        _bb = Sketch1_rafts_1.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch1_rafts_1.profiles.item(_best_pi))
    _used.add(_best_pi)
    inp = comp.features.extrudeFeatures.createInput(_prof_coll, NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("rafter_w"))
    Extrude1 = comp.features.extrudeFeatures.add(inp)
    Extrude1.name = "Extrude1"
    Body1_rafts_1 = Extrude1.bodies.item(0)
    Body1_rafts_1.name = "Body1"

    # [62] Move: Move1
    comp = rafts_1_c
    xform = adsk.core.Matrix3D.create()
    xform.setWithArray([1.0, 0.0, 0.0, 124.46, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0])
    move_coll = adsk.core.ObjectCollection.create()
    move_coll.add(Body1_rafts_1)
    move_inp = comp.features.moveFeatures.createInput2(move_coll)
    move_inp.defineAsFreeMove(xform)
    move_feat = comp.features.moveFeatures.add(move_inp)
    move_feat.name = "Move1"

    # [63] Sketch: Sketch2
    comp = rafts_1_c
    # variant 0: method=intersect
    Sketch2_rafts_1 = comp.sketches.add(find_face_near(Body1_rafts_1, 351.155, -97.155, 421.64, 0.0, 0.0, -1.0))
    Sketch2_rafts_1.name = "Sketch2"
    lns = Sketch2_rafts_1.sketchCurves.sketchLines
    # Coordinate transform: captured sketch axes -> actual sketch axes
    _cap_xd = (1.0, 0.0, 0.0)
    _cap_yd = (0.0, -1.0, 0.0)
    _act_xd = Sketch2_rafts_1.xDirection
    _act_yd = Sketch2_rafts_1.yDirection
    _m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z
    _m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z
    _m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z
    _m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z
    def _xf(sx, sy):
        return (sx * _m00 + sy * _m01, sx * _m10 + sy * _m11)
    # Intersect body 'Body1' with sketch plane
    _bodies_Body1 = []
    for _occ in root.allOccurrences:
        if _occ.component.name == "beam":
            for _bi in range(_occ.bRepBodies.count):
                if _occ.bRepBodies.item(_bi).name == "Body1":
                    _bodies_Body1.append(_occ.bRepBodies.item(_bi))
            break
    if _bodies_Body1: _proj_body_Body1 = Sketch2_rafts_1.intersectWithSketchPlane(_bodies_Body1)
    _proj_pts = []  # [(x, y, sketchPoint), ...]
    _proj_curves = []  # [(sx, sy, ex, ey, curve), ...]
    for _ci in range(Sketch2_rafts_1.sketchCurves.count):
        _c = Sketch2_rafts_1.sketchCurves.item(_ci)
        if _c.isReference:
            for _sp in [_c.startSketchPoint, _c.endSketchPoint]:
                _g = _sp.geometry
                _proj_pts.append((_g.x, _g.y, _sp))
            _s, _e = _c.startSketchPoint.geometry, _c.endSketchPoint.geometry
            _proj_curves.append((_s.x, _s.y, _e.x, _e.y, _c))

    _fallback_pts = {}
    def _nearest_proj(x, y):
        best, best_d = None, 1e10
        for _px, _py, _sp in _proj_pts:
            _d = abs(_px - x) + abs(_py - y)
            if _d < best_d: best, best_d = _sp, _d
        if best_d > 5.0: best = None
        if best is None:
            _fk = (round(x,2), round(y,2))
            best = _fallback_pts.get(_fk)
        if best is None:
            best = Sketch2_rafts_1.sketchPoints.add(P(x, y, 0))
        return best

    def _nearest_proj_curve(sx, sy, ex, ey):
        best, best_d = None, 1e10
        for _sx, _sy, _ex, _ey, _c in _proj_curves:
            _d = min(abs(_sx-sx)+abs(_sy-sy)+abs(_ex-ex)+abs(_ey-ey),
                    abs(_sx-ex)+abs(_sy-ey)+abs(_ex-sx)+abs(_ey-sy))
            if _d < best_d: best, best_d = _c, _d
        if best_d > 10.0: best = None
        if best is None:
            _sk = (round(sx,2), round(sy,2))
            _ek = (round(ex,2), round(ey,2))
            _sp = _fallback_pts.get(_sk)
            _ep = _fallback_pts.get(_ek)
            if _sp and _ep:
                best = Sketch2_rafts_1.sketchCurves.sketchLines.addByTwoPoints(_sp, _ep)
            elif _sp:
                best = Sketch2_rafts_1.sketchCurves.sketchLines.addByTwoPoints(_sp, P(ex, ey, 0))
                _fallback_pts[_ek] = best.endSketchPoint
            elif _ep:
                best = Sketch2_rafts_1.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), _ep)
                _fallback_pts[_sk] = best.startSketchPoint
            else:
                best = Sketch2_rafts_1.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), P(ex, ey, 0))
                _fallback_pts[_sk] = best.startSketchPoint
                _fallback_pts[_ek] = best.endSketchPoint
            try: Sketch2_rafts_1.geometricConstraints.addFix(best)
            except: pass
        return best
    _pcurve_0 = _nearest_proj_curve(*_xf(353.06, 10.3399), *_xf(353.06, 183.9701))
    _pcurve_1 = _nearest_proj_curve(*_xf(353.06, 183.9701), *_xf(349.25, 183.9701))
    _pcurve_2 = _nearest_proj_curve(*_xf(349.25, 183.9701), *_xf(349.25, 10.3399))
    _pcurve_3 = _nearest_proj_curve(*_xf(349.25, 10.3399), *_xf(353.06, 10.3399))
    _pcurve_4 = _nearest_proj_curve(*_xf(373.38, 168.91), *_xf(373.38, 177.8))
    _pcurve_5 = _nearest_proj_curve(*_xf(373.38, 177.8), *_xf(83.82, 177.8))
    _pcurve_6 = _nearest_proj_curve(*_xf(83.82, 177.8), *_xf(83.82, 168.91))
    _pcurve_7 = _nearest_proj_curve(*_xf(83.82, 168.91), *_xf(373.38, 168.91))
    Sketch2_rafts_1_prof = Sketch2_rafts_1.profiles.item(0)  # 5 profile(s)

    # [64] Extrude: Extrude2
    comp = rafts_1_c
    _cx = (1.0, 0.0, 0.0)
    _cy = (0.0, -1.0, 0.0)
    _ax = Sketch2_rafts_1.xDirection
    _ay = Sketch2_rafts_1.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Match profile by bbox (transformed): (349.25, 168.91) to (353.06, 177.8)
    _t1 = (349.25*_m00 + 168.91*_m01, 349.25*_m10 + 168.91*_m11)
    _t2 = (353.06*_m00 + 177.8*_m01, 353.06*_m10 + 177.8*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch2_rafts_1.profiles.count):
        _bb = Sketch2_rafts_1.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    inp = comp.features.extrudeFeatures.createInput(Sketch2_rafts_1.profiles.item(_best_pi), CUT)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("-rafter_offset"))
    inp.participantBodies = [Body1_rafts_1]
    Extrude2 = comp.features.extrudeFeatures.add(inp)
    Extrude2.name = "Extrude2"
    Body1_rafts_1 = Extrude2.bodies.item(0)
    Body1_rafts_1.name = "Body1"

    # [65] ConstructionPlane: Plane2
    comp = rafts_1_c
    _pl_inp = comp.constructionPlanes.createInput()
    _pl_inp.setByTwoPlanes(find_face_near(Body1_rafts_1, 351.155, -189.8968, 429.0483), find_face_near(Body1_rafts_1, 351.155, -4.4133, 429.0483))
    Plane2_rafts_1 = comp.constructionPlanes.add(_pl_inp)
    Plane2_rafts_1.name = "Plane2"

    # [66] Mirror: Mirror1
    comp = rafts_1_c
    Mirror1 = mirror_feats(comp, [Extrude2], Plane2_rafts_1, "Mirror1")
    Body1_rafts_1 = Mirror1.bodies.item(0)
    Body1_rafts_1.name = "Body1"

    # [67] RectangularPattern: R-Pattern1
    comp = rafts_1_c
    pat_coll = adsk.core.ObjectCollection.create()
    pat_coll.add(Body1_rafts_1)
    pat_inp = comp.features.rectangularPatternFeatures.createInput(
        pat_coll,
        root.xConstructionAxis,
        adsk.core.ValueInput.createByString("rafter_count"),
        adsk.core.ValueInput.createByString("-(( perg_w + top_beam_side * 2 - rafter_x_offset * 2 - rafter_w ) / ( rafter_count - 1 ))"),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType,
    )
    pat_inp.quantityTwo = adsk.core.ValueInput.createByReal(1)
    _before_pat = set(comp.bRepBodies.item(_i).name for _i in range(comp.bRepBodies.count))
    R_Pattern1 = comp.features.rectangularPatternFeatures.add(pat_inp)
    R_Pattern1.name = "R-Pattern1"
    _pat_copies = []
    for _i in range(comp.bRepBodies.count):
        _b = comp.bRepBodies.item(_i)
        if _b.name not in _before_pat:
            _pat_copies.append(_b)
    _pat_copies.sort(key=lambda _b: getattr(_b.boundingBox.minPoint, 'x'))
    if 0 < len(_pat_copies):
        Body11_rafts_1 = _pat_copies[0]
        Body11_rafts_1.name = "Body11"
    if 1 < len(_pat_copies):
        Body9_rafts_1 = _pat_copies[1]
        Body9_rafts_1.name = "Body9"
    if 2 < len(_pat_copies):
        Body8_rafts_1 = _pat_copies[2]
        Body8_rafts_1.name = "Body8"
    if 3 < len(_pat_copies):
        Body7_rafts_1 = _pat_copies[3]
        Body7_rafts_1.name = "Body7"
    if 4 < len(_pat_copies):
        Body6_rafts_1 = _pat_copies[4]
        Body6_rafts_1.name = "Body6"
    if 5 < len(_pat_copies):
        Body5_rafts_1 = _pat_copies[5]
        Body5_rafts_1.name = "Body5"
    if 6 < len(_pat_copies):
        Body4_rafts_1 = _pat_copies[6]
        Body4_rafts_1.name = "Body4"
    if 7 < len(_pat_copies):
        Body3_rafts_1 = _pat_copies[7]
        Body3_rafts_1.name = "Body3"
    if 8 < len(_pat_copies):
        Body2_rafts_1 = _pat_copies[8]
        Body2_rafts_1.name = "Body2"

    # [68] Sketch: Sketch4
    comp = posts_c
    # Native face sketch: Sketch4 (cross-body refs)
    _native_face = find_face_in_comp(comp, 338.455, -170.3917, 411.48, 0.0, 0.0, 1.0)
    if not _native_face: _native_face = find_face_near(find_body("post1"), 338.455, -170.3917, 411.48, 0.0, 0.0, 1.0)
    Sketch4_posts = comp.sketches.add(_native_face)
    Sketch4_posts.name = "Sketch4"
    lns = Sketch4_posts.sketchCurves.sketchLines
    # Coordinate transform: captured sketch axes -> actual sketch axes
    _cap_xd = (-1.0, 0.0, 0.0)
    _cap_yd = (0.0, -1.0, 0.0)
    _act_xd = Sketch4_posts.xDirection
    _act_yd = Sketch4_posts.yDirection
    _m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z
    _m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z
    _m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z
    _m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z
    def _xf(sx, sy):
        return (sx * _m00 + sy * _m01, sx * _m10 + sy * _m11)
    # Intersect body 'post2' with sketch plane
    _bodies_post2 = []
    for _bi in range(comp.bRepBodies.count):
        if comp.bRepBodies.item(_bi).name == "post2":
            _bodies_post2.append(comp.bRepBodies.item(_bi))
    if not _bodies_post2:
        for _occ in root.allOccurrences:
            for _bi in range(_occ.bRepBodies.count):
                if _occ.bRepBodies.item(_bi).name == "post2":
                    _bodies_post2.append(_occ.bRepBodies.item(_bi))
    if _bodies_post2: _proj_body_post2 = Sketch4_posts.intersectWithSketchPlane(_bodies_post2)
    _proj_pts = []  # [(x, y, sketchPoint), ...]
    _proj_curves = []  # [(sx, sy, ex, ey, curve), ...]
    for _ci in range(Sketch4_posts.sketchCurves.count):
        _c = Sketch4_posts.sketchCurves.item(_ci)
        if _c.isReference:
            for _sp in [_c.startSketchPoint, _c.endSketchPoint]:
                _g = _sp.geometry
                _proj_pts.append((_g.x, _g.y, _sp))
            _s, _e = _c.startSketchPoint.geometry, _c.endSketchPoint.geometry
            _proj_curves.append((_s.x, _s.y, _e.x, _e.y, _c))

    _fallback_pts = {}
    def _nearest_proj(x, y):
        best, best_d = None, 1e10
        for _px, _py, _sp in _proj_pts:
            _d = abs(_px - x) + abs(_py - y)
            if _d < best_d: best, best_d = _sp, _d
        if best_d > 5.0: best = None
        if best is None:
            _fk = (round(x,2), round(y,2))
            best = _fallback_pts.get(_fk)
        if best is None:
            best = Sketch4_posts.sketchPoints.add(P(x, y, 0))
        return best

    def _nearest_proj_curve(sx, sy, ex, ey):
        best, best_d = None, 1e10
        for _sx, _sy, _ex, _ey, _c in _proj_curves:
            _d = min(abs(_sx-sx)+abs(_sy-sy)+abs(_ex-ex)+abs(_ey-ey),
                    abs(_sx-ex)+abs(_sy-ey)+abs(_ex-sx)+abs(_ey-sy))
            if _d < best_d: best, best_d = _c, _d
        if best_d > 10.0: best = None
        if best is None:
            _sk = (round(sx,2), round(sy,2))
            _ek = (round(ex,2), round(ey,2))
            _sp = _fallback_pts.get(_sk)
            _ep = _fallback_pts.get(_ek)
            if _sp and _ep:
                best = Sketch4_posts.sketchCurves.sketchLines.addByTwoPoints(_sp, _ep)
            elif _sp:
                best = Sketch4_posts.sketchCurves.sketchLines.addByTwoPoints(_sp, P(ex, ey, 0))
                _fallback_pts[_ek] = best.endSketchPoint
            elif _ep:
                best = Sketch4_posts.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), _ep)
                _fallback_pts[_sk] = best.startSketchPoint
            else:
                best = Sketch4_posts.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), P(ex, ey, 0))
                _fallback_pts[_sk] = best.startSketchPoint
                _fallback_pts[_ek] = best.endSketchPoint
            try: Sketch4_posts.geometricConstraints.addFix(best)
            except: pass
        return best
    _pcurve_0 = _nearest_proj_curve(*_xf(-334.01, 177.8), *_xf(-342.9, 177.8))
    _pcurve_1 = _nearest_proj_curve(*_xf(-342.9, 177.8), *_xf(-342.9, 168.91))
    _pcurve_2 = _nearest_proj_curve(*_xf(-342.9, 168.91), *_xf(-334.01, 168.91))
    _pcurve_3 = _nearest_proj_curve(*_xf(-334.01, 168.91), *_xf(-334.01, 177.8))
    _cs_4 = _xf(-334.01, 168.91)
    _ce_4 = _xf(-334.01, 171.8733)
    ln4 = lns.addByTwoPoints(P(_cs_4[0], _cs_4[1], 0), P(_ce_4[0], _ce_4[1], 0))
    _cs_5 = _xf(-334.01, 171.8733)
    _ce_5 = _xf(-342.9, 171.8733)
    ln5 = lns.addByTwoPoints(ln4.endSketchPoint, P(_ce_5[0], _ce_5[1], 0))
    _cs_6 = _xf(-342.9, 171.8733)
    _ce_6 = _xf(-342.9, 168.91)
    ln6 = lns.addByTwoPoints(ln5.endSketchPoint, P(_ce_6[0], _ce_6[1], 0))
    _cs_7 = _xf(-342.9, 168.91)
    _ce_7 = _xf(-334.01, 168.91)
    ln7 = lns.addByTwoPoints(ln6.endSketchPoint, ln4.startSketchPoint)
    _cs_8 = _xf(-334.01, 168.91)
    _ce_8 = _xf(-334.01, 171.8733)
    ln8 = lns.addByTwoPoints(ln4.startSketchPoint, ln4.endSketchPoint)
    _cs_9 = _xf(-334.01, 171.8733)
    _ce_9 = _xf(-342.9, 171.8733)
    ln9 = lns.addByTwoPoints(ln4.endSketchPoint, ln5.endSketchPoint)
    _cs_10 = _xf(-342.9, 171.8733)
    _ce_10 = _xf(-342.9, 174.8367)
    ln10 = lns.addByTwoPoints(ln5.endSketchPoint, P(_ce_10[0], _ce_10[1], 0))
    _cs_11 = _xf(-342.9, 174.8367)
    _ce_11 = _xf(-334.01, 174.8367)
    ln11 = lns.addByTwoPoints(ln10.endSketchPoint, P(_ce_11[0], _ce_11[1], 0))
    _cs_12 = _xf(-334.01, 174.8367)
    _ce_12 = _xf(-334.01, 171.8733)
    ln12 = lns.addByTwoPoints(ln11.endSketchPoint, ln4.endSketchPoint)
    d = Sketch4_posts.sketchDimensions
    try:
        d.addDistanceDimension(_nearest_proj(*_xf(-334.01, 168.91)), ln4.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "post_w / 3"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln4.endSketchPoint, ln5.endSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "post_w"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(_nearest_proj(*_xf(-334.01, 168.91)), ln4.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "post_w / 3"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln11.endSketchPoint, ln4.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "post_w / 3"
    except: pass  # skip if already constrained
    gc = Sketch4_posts.geometricConstraints
    try: gc.addPerpendicular(ln4, _pcurve_2)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln5)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln6)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln7)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln8)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln9)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln10)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln11)
    except: pass
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln12)
    except: pass
    Sketch4_posts_prof = Sketch4_posts.profiles.item(0)  # 3 profile(s)

    # [69] Extrude: Extrude4
    comp = posts_c
    _cx = (-1.0, 0.0, 0.0)
    _cy = (0.0, -1.0, 0.0)
    _ax = Sketch4_posts.xDirection
    _ay = Sketch4_posts.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Match profile by bbox (transformed): (-342.9, 171.8733) to (-334.01, 174.8367)
    _t1 = (-342.9*_m00 + 171.8733*_m01, -342.9*_m10 + 171.8733*_m11)
    _t2 = (-334.01*_m00 + 174.8367*_m01, -334.01*_m10 + 174.8367*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch4_posts.profiles.count):
        _bb = Sketch4_posts.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    inp = comp.features.extrudeFeatures.createInput(Sketch4_posts.profiles.item(_best_pi), JOIN)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("top_beam_height / 3 * 2"))
    inp.participantBodies = [post2_posts]
    Extrude4 = comp.features.extrudeFeatures.add(inp)
    Extrude4.name = "Extrude4"
    post2_posts = Extrude4.bodies.item(0)
    post2_posts.name = "post2"

    # [70] Combine: Combine3
    comp = beam_c
    Combine3 = combine(comp, Body1_beam, [post1_posts, post2_posts], CUT, True, "Combine3")

    # [71] Combine: Combine1
    comp = deck5_c
    Combine1 = combine(comp, Body117_deck5, [post1_posts, post2_posts], CUT, True, "Combine1")

    # [72] Combine: Combine1
    comp = posts_c
    Combine1 = combine(comp, post1_posts, [Body3_beam], CUT, True, "Combine1")

    # [73] Combine: Combine2
    comp = posts_c
    Combine2 = combine(comp, post2_posts, [Body4_beam], CUT, True, "Combine2")

    # [74] Mirror: Mirror1
    comp = posts_c
    _Plane1_proxy = Plane1_beam
    for _occ in root.allOccurrences:
        if _occ.component.name == "beam":
            _Plane1_proxy = Plane1_beam.createForAssemblyContext(_occ); break
    Mirror1 = mirror_feats(comp, [scarf1_posts], _Plane1_proxy, "Mirror1")
    scarf1_1_posts = Mirror1.bodies.item(0)
    scarf1_1_posts.name = "scarf1 (1)"
    scarf1_posts = Mirror1.bodies.item(1)
    scarf1_posts.name = "scarf1"

    # [75] Mirror: Mirror2
    comp = posts_c
    _Plane1_proxy = Plane1_beam
    for _occ in root.allOccurrences:
        if _occ.component.name == "beam":
            _Plane1_proxy = Plane1_beam.createForAssemblyContext(_occ); break
    Mirror2 = mirror_feats(comp, [notch1_posts, notch2_posts], _Plane1_proxy, "Mirror2")
    notch1_1_posts = Mirror2.bodies.item(0)
    notch1_1_posts.name = "notch1 (1)"
    notch2_1_posts = Mirror2.bodies.item(1)
    notch2_1_posts.name = "notch2 (1)"
    notch1_posts = Mirror2.bodies.item(2)
    notch1_posts.name = "notch1"
    notch2_posts = Mirror2.bodies.item(3)
    notch2_posts.name = "notch2"

    # [76] SplitBody: Split2
    comp = posts_c
    split_inp = comp.features.splitBodyFeatures.createInput(post1_posts, Plane2_posts, True)
    split_feat = comp.features.splitBodyFeatures.add(split_inp)
    split_feat.name = "Split2"
    split_inp = comp.features.splitBodyFeatures.createInput(post2_posts, Plane2_posts, True)
    comp.features.splitBodyFeatures.add(split_inp)
    # Rename 11 bodies by volume+position matching
    _all_comp_bodies = [comp.bRepBodies.item(_i) for _i in range(comp.bRepBodies.count)]
    for _ti, _tb in enumerate(_all_comp_bodies): _tb.name = f'__tmp_{_ti}'
    _expected_geo = [
        ("post1", 19271.1873, [114.3, -177.8, 0.0]),
        ("post2", 19271.1873, [334.01, -177.8, 0.0]),
        ("post1_upper", 13351.9135, [114.3, -177.8, 243.84]),
        ("post2_upper", 13351.9135, [334.01, -177.8, 243.84]),
        ("scarf1", 1258.4742, [114.3, -177.8, 243.84]),
        ("scarf1 (1)", 1258.4742, [337.7003, -177.8, 243.84]),
        ("wedge1", 22.4042, [117.914, -177.8, 259.519]),
        ("notch1 (1)", 17.5718, [334.01, -177.8, 243.84]),
        ("notch2 (1)", 17.5718, [334.01, -172.5613, 243.84]),
        ("notch1", 17.5718, [120.2543, -177.8, 243.84]),
        ("notch2", 17.5718, [120.2543, -172.5613, 243.84]),
    ]
    _used = set()
    for _nm, _ev, _emin in _expected_geo:
        _best_i, _best_d = -1, 1e10
        for _bi, _b in enumerate(_all_comp_bodies):
            if _bi in _used: continue
            _d = abs(_b.volume - _ev)
            try:
                _bb = _b.boundingBox
                _d += abs(_bb.minPoint.x - _emin[0]) + abs(_bb.minPoint.y - _emin[1]) + abs(_bb.minPoint.z - _emin[2])
            except: pass
            if _d < _best_d: _best_i, _best_d = _bi, _d
        if _best_i >= 0:
            _all_comp_bodies[_best_i].name = _nm
            _used.add(_best_i)
    if comp.bRepBodies.count != 11:
        app.log(f'WARNING: Split body count mismatch: expected 11, got {comp.bRepBodies.count}')
        for _bi in range(comp.bRepBodies.count):
            app.log(f'  body[{_bi}]: {comp.bRepBodies.item(_bi).name} vol={round(comp.bRepBodies.item(_bi).volume, 2)}')
    post1_posts = find_body("post1", comp)
    post2_posts = find_body("post2", comp)
    post1_upper_posts = find_body("post1_upper", comp)
    post2_upper_posts = find_body("post2_upper", comp)
    # Body-relative bounding box reads for beam/brace positioning
    post1_bb = post1_posts.boundingBox
    post2_bb = post2_posts.boundingBox
    post1_upper_bb = post1_upper_posts.boundingBox
    post2_upper_bb = post2_upper_posts.boundingBox
    scarf1_posts = find_body("scarf1", comp)
    scarf1_1_posts = find_body("scarf1 (1)", comp)
    wedge1_posts = find_body("wedge1", comp)
    notch1_1_posts = find_body("notch1 (1)", comp)
    notch2_1_posts = find_body("notch2 (1)", comp)
    notch1_posts = find_body("notch1", comp)
    notch2_posts = find_body("notch2", comp)

    # [77] Combine: Combine9
    comp = posts_c
    Combine9 = combine(comp, post1_posts, [scarf1_posts, notch1_posts, notch2_posts], JOIN, False, "Combine9")

    # [78] Combine: Combine10
    comp = posts_c
    Combine10 = combine(comp, post1_upper_posts, [post1_posts], CUT, True, "Combine10")

    # [79] Combine: Combine11
    comp = posts_c
    Combine11 = combine(comp, post2_posts, [scarf1_1_posts, notch1_1_posts, notch2_1_posts], JOIN, False, "Combine11")

    # [80] Combine: Combine12
    comp = posts_c
    Combine12 = combine(comp, post2_upper_posts, [post2_posts], CUT, True, "Combine12")

    # [81] Combine: Combine13
    comp = posts_c
    Combine13 = combine(comp, post1_upper_posts, [wedge1_posts], CUT, True, "Combine13")

    # [82] Mirror: Mirror3
    comp = posts_c
    _Plane1_proxy = Plane1_beam
    for _occ in root.allOccurrences:
        if _occ.component.name == "beam":
            _Plane1_proxy = Plane1_beam.createForAssemblyContext(_occ); break
    Mirror3 = mirror_feats(comp, [wedge1_posts], _Plane1_proxy, "Mirror3")
    wedge2_posts = Mirror3.bodies.item(0)
    wedge2_posts.name = "wedge2"
    wedge1_posts = Mirror3.bodies.item(1)
    wedge1_posts.name = "wedge1"

    # [83] Combine: Combine14
    comp = posts_c
    Combine14 = combine(comp, post2_upper_posts, [wedge2_posts], CUT, True, "Combine14")

    # [84] ComponentCreation: braces
    comp = root
    braces_occ = comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    braces_occ.component.name = "braces"
    braces_c = braces_occ.component

    # [85] Sketch: Sketch1
    comp = braces_c
    # Native face sketch: Sketch1 (cross-body refs)
    _native_face = find_face_in_comp(comp, 228.6, -177.8, 419.1, 0.0, -1.0, 0.0)
    if not _native_face: _native_face = find_face_near(find_body("Body1"), 228.6, -177.8, 419.1, 0.0, -1.0, 0.0)
    Sketch1_braces = comp.sketches.add(_native_face)
    Sketch1_braces.name = "Sketch1"
    lns = Sketch1_braces.sketchCurves.sketchLines
    # Coordinate transform: captured sketch axes -> actual sketch axes
    _cap_xd = (1.0, 0.0, 0.0)
    _cap_yd = (0.0, 0.0, 1.0)
    _act_xd = Sketch1_braces.xDirection
    _act_yd = Sketch1_braces.yDirection
    _m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z
    _m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z
    _m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z
    _m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z
    def _xf(sx, sy):
        return (sx * _m00 + sy * _m01, sx * _m10 + sy * _m11)
    arcs = Sketch1_braces.sketchCurves.sketchArcs
    # Intersect body 'post1_upper' with sketch plane
    _bodies_post1_upper = []
    for _bi in range(comp.bRepBodies.count):
        if comp.bRepBodies.item(_bi).name == "post1_upper":
            _bodies_post1_upper.append(comp.bRepBodies.item(_bi))
    if not _bodies_post1_upper:
        for _occ in root.allOccurrences:
            for _bi in range(_occ.bRepBodies.count):
                if _occ.bRepBodies.item(_bi).name == "post1_upper":
                    _bodies_post1_upper.append(_occ.bRepBodies.item(_bi))
    if _bodies_post1_upper: _proj_body_post1_upper = Sketch1_braces.intersectWithSketchPlane(_bodies_post1_upper)
    _proj_pts = []  # [(x, y, sketchPoint), ...]
    _proj_curves = []  # [(sx, sy, ex, ey, curve), ...]
    for _ci in range(Sketch1_braces.sketchCurves.count):
        _c = Sketch1_braces.sketchCurves.item(_ci)
        if _c.isReference:
            for _sp in [_c.startSketchPoint, _c.endSketchPoint]:
                _g = _sp.geometry
                _proj_pts.append((_g.x, _g.y, _sp))
            _s, _e = _c.startSketchPoint.geometry, _c.endSketchPoint.geometry
            _proj_curves.append((_s.x, _s.y, _e.x, _e.y, _c))

    _fallback_pts = {}
    def _nearest_proj(x, y):
        best, best_d = None, 1e10
        for _px, _py, _sp in _proj_pts:
            _d = abs(_px - x) + abs(_py - y)
            if _d < best_d: best, best_d = _sp, _d
        if best_d > 5.0: best = None
        if best is None:
            _fk = (round(x,2), round(y,2))
            best = _fallback_pts.get(_fk)
        if best is None:
            best = Sketch1_braces.sketchPoints.add(P(x, y, 0))
        return best

    def _nearest_proj_curve(sx, sy, ex, ey):
        best, best_d = None, 1e10
        for _sx, _sy, _ex, _ey, _c in _proj_curves:
            _d = min(abs(_sx-sx)+abs(_sy-sy)+abs(_ex-ex)+abs(_ey-ey),
                    abs(_sx-ex)+abs(_sy-ey)+abs(_ex-sx)+abs(_ey-sy))
            if _d < best_d: best, best_d = _c, _d
        if best_d > 10.0: best = None
        if best is None:
            _sk = (round(sx,2), round(sy,2))
            _ek = (round(ex,2), round(ey,2))
            _sp = _fallback_pts.get(_sk)
            _ep = _fallback_pts.get(_ek)
            if _sp and _ep:
                best = Sketch1_braces.sketchCurves.sketchLines.addByTwoPoints(_sp, _ep)
            elif _sp:
                best = Sketch1_braces.sketchCurves.sketchLines.addByTwoPoints(_sp, P(ex, ey, 0))
                _fallback_pts[_ek] = best.endSketchPoint
            elif _ep:
                best = Sketch1_braces.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), _ep)
                _fallback_pts[_sk] = best.startSketchPoint
            else:
                best = Sketch1_braces.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), P(ex, ey, 0))
                _fallback_pts[_sk] = best.startSketchPoint
                _fallback_pts[_ek] = best.endSketchPoint
            try: Sketch1_braces.geometricConstraints.addFix(best)
            except: pass
        return best
    _pcurve_0 = _nearest_proj_curve(*_xf(83.82, 421.2719), *_xf(104.0675, 411.48))
    _pcurve_1 = _nearest_proj_curve(*_xf(104.0675, 411.48), *_xf(353.1325, 411.48))
    _pcurve_2 = _nearest_proj_curve(*_xf(353.1325, 411.48), *_xf(373.38, 421.2719))
    _pcurve_3 = _nearest_proj_curve(*_xf(373.38, 421.2719), *_xf(373.38, 426.72))
    _pcurve_4 = _nearest_proj_curve(*_xf(373.38, 426.72), *_xf(83.82, 426.72))
    _pcurve_5 = _nearest_proj_curve(*_xf(83.82, 426.72), *_xf(83.82, 421.2719))
    _pcurve_6 = _nearest_proj_curve(*_xf(119.576, 259.5953), *_xf(117.9903, 259.519))
    _pcurve_7 = _nearest_proj_curve(*_xf(117.9903, 259.519), *_xf(118.745, 243.84))
    _pcurve_8 = _nearest_proj_curve(*_xf(118.745, 243.84), *_xf(120.3343, 243.84))
    _pcurve_9 = _nearest_proj_curve(*_xf(120.3343, 243.84), *_xf(120.2543, 245.502))
    _pcurve_10 = _nearest_proj_curve(*_xf(120.2543, 245.502), *_xf(123.19, 245.502))
    _pcurve_11 = _nearest_proj_curve(*_xf(123.19, 245.502), *_xf(123.19, 411.48))
    _pcurve_12 = _nearest_proj_curve(*_xf(123.19, 411.48), *_xf(114.3, 411.48))
    _pcurve_13 = _nearest_proj_curve(*_xf(114.3, 411.48), *_xf(114.3, 275.198))
    _pcurve_14 = _nearest_proj_curve(*_xf(114.3, 275.198), *_xf(117.2357, 275.198))
    _pcurve_15 = _nearest_proj_curve(*_xf(117.2357, 275.198), *_xf(117.1557, 276.86))
    _pcurve_16 = _nearest_proj_curve(*_xf(117.1557, 276.86), *_xf(118.745, 276.86))
    _pcurve_17 = _nearest_proj_curve(*_xf(118.745, 276.86), *_xf(119.576, 259.5953))
    # curve[0] is a projected reference (source not captured)
    # curve[1] is a projected reference (source not captured)
    _cs_14 = _xf(123.19, 411.48)
    _ce_14 = _xf(161.29, 411.48)
    ln14 = lns.addByTwoPoints(P(_cs_14[0], _cs_14[1], 0), P(_ce_14[0], _ce_14[1], 0))
    _cs_15 = _xf(123.19, 411.48)
    _ce_15 = _xf(123.19, 410.0)
    ln15 = lns.addByTwoPoints(ln14.startSketchPoint, P(_ce_15[0], _ce_15[1], 0))
    _cs_16 = _xf(123.19, 411.48)
    _ce_16 = _xf(123.19, 373.38)
    ln16 = lns.addByTwoPoints(ln14.startSketchPoint, P(_ce_16[0], _ce_16[1], 0))
    _cs_17 = _xf(161.29, 411.48)
    _ce_17 = _xf(123.19, 373.38)
    ln17 = lns.addByTwoPoints(ln14.endSketchPoint, ln16.endSketchPoint)
    _cs_18 = _xf(123.19, 373.38)
    _ce_18 = _xf(129.4762, 367.0938)
    ln18 = lns.addByTwoPoints(ln16.endSketchPoint, P(_ce_18[0], _ce_18[1], 0))
    _cs_19 = _xf(161.29, 411.48)
    _ce_19 = _xf(167.5762, 405.1938)
    ln19 = lns.addByTwoPoints(ln14.endSketchPoint, P(_ce_19[0], _ce_19[1], 0))
    _cs_20 = _xf(129.4762, 367.0938)
    _ce_20 = _xf(167.5762, 405.1938)
    ln20 = lns.addByTwoPoints(ln18.endSketchPoint, ln19.endSketchPoint)
    _cs_21 = _xf(167.5762, 405.1938)
    _ce_21 = _xf(172.2908, 409.9085)
    ln21 = lns.addByTwoPoints(ln19.endSketchPoint, P(_ce_21[0], _ce_21[1], 0))
    _cs_22 = _xf(172.2908, 409.9085)
    _ce_22 = _xf(172.2908, 411.48)
    ln22 = lns.addByTwoPoints(ln21.endSketchPoint, P(_ce_22[0], _ce_22[1], 0))
    _cs_23 = _xf(129.4762, 367.0938)
    _ce_23 = _xf(124.7615, 362.3792)
    ln23 = lns.addByTwoPoints(ln18.endSketchPoint, P(_ce_23[0], _ce_23[1], 0))
    _cs_24 = _xf(124.7615, 362.3792)
    _ce_24 = _xf(123.19, 362.3792)
    ln24 = lns.addByTwoPoints(ln23.endSketchPoint, P(_ce_24[0], _ce_24[1], 0))
    _cs_25 = _xf(148.5262, 386.1438)
    _ce_25 = _xf(146.9546, 387.7154)
    ln25 = lns.addByTwoPoints(P(_cs_25[0], _cs_25[1], 0), P(_ce_25[0], _ce_25[1], 0))
    _ac_26 = _xf(263.2008, 271.4692)
    _as_26 = _xf(167.5762, 405.1938)
    arc26 = arcs.addByCenterStartSweep(P(_ac_26[0], _ac_26[1], 0), P(_as_26[0], _as_26[1], 0), 3.14159)
    _cs_27 = _xf(161.29, 411.48)
    _ce_27 = _xf(166.0046, 416.1946)
    ln27 = lns.addByTwoPoints(ln14.endSketchPoint, P(_ce_27[0], _ce_27[1], 0))
    _cs_28 = _xf(166.0046, 416.1946)
    _ce_28 = _xf(172.2908, 416.1946)
    ln28 = lns.addByTwoPoints(ln27.endSketchPoint, P(_ce_28[0], _ce_28[1], 0))
    _cs_29 = _xf(172.2908, 416.1946)
    _ce_29 = _xf(172.2908, 411.48)
    ln29 = lns.addByTwoPoints(ln28.endSketchPoint, ln22.endSketchPoint)
    d = Sketch1_braces.sketchDimensions
    try:
        d.addDistanceDimension(_nearest_proj(*_xf(123.19, 411.48)), ln14.endSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "brace_dist"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(_nearest_proj(*_xf(123.19, 411.48)), ln16.endSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "brace_dist"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln16.endSketchPoint, ln18.endSketchPoint,
            adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, P(0, 0, 0)).parameter.expression = "post_w"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln14.endSketchPoint, ln19.endSketchPoint,
            adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, P(0, 0, 0)).parameter.expression = "post_w"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln19.endSketchPoint, ln21.endSketchPoint,
            adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, P(0, 0, 0)).parameter.expression = "post_w * 3 / 4"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln18.endSketchPoint, ln23.endSketchPoint,
            adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, P(0, 0, 0)).parameter.expression = "post_w / 4 * 3"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln25.startSketchPoint, ln25.endSketchPoint,
            adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, P(0, 0, 0)).parameter.expression = "post_w / 4"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln14.endSketchPoint, ln27.endSketchPoint,
            adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, P(0, 0, 0)).parameter.expression = "post_w / 4 * 3"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln27.endSketchPoint, ln28.endSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "post_w * cos(45 deg)"
    except: pass  # skip if already constrained
    gc = Sketch1_braces.geometricConstraints
    try: gc.addPerpendicular(ln14, _pcurve_11)
    except: pass
    try: gc.addCoincident(ln15.endSketchPoint, _pcurve_11)
    except: pass
    try: gc.addPerpendicular(ln16, _pcurve_1)
    except: pass
    try: gc.addPerpendicular(ln18, ln17)
    except: pass
    try: gc.addPerpendicular(ln19, ln17)
    except: pass
    try: gc.addPerpendicular(ln21, ln19)
    except: pass
    try: gc.addCoincident(ln22.endSketchPoint, _pcurve_1)
    except: pass
    try: gc.addPerpendicular(ln22, _pcurve_1)
    except: pass
    try: gc.addPerpendicular(ln23, ln18)
    except: pass
    try: gc.addCoincident(ln24.endSketchPoint, _pcurve_11)
    except: pass
    try: gc.addPerpendicular(ln24, _pcurve_11)
    except: pass
    try: gc.addMidPoint(ln25.startSketchPoint, ln20)
    except: pass
    try: gc.addPerpendicular(ln25, ln20)
    except: pass
    try: gc.addCoincident(ln25.endSketchPoint, arc26)
    except: pass
    try: gc.addPerpendicular(ln27, ln19)
    except: pass
    try: (gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)(ln28)
    except: pass
    Sketch1_braces_prof = Sketch1_braces.profiles.item(0)  # 9 profile(s)

    # [86] Extrude: Extrude1
    comp = braces_c
    _cx = (1.0, 0.0, 0.0)
    _cy = (0.0, 0.0, 1.0)
    _ax = Sketch1_braces.xDirection
    _ay = Sketch1_braces.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Multi-profile extrude: 3 profiles
    _prof_coll = adsk.core.ObjectCollection.create()
    _used = set()
    # Match profile by bbox (transformed): (161.29, 405.1938) to (172.2908, 411.48)
    _t1 = (161.29*_m00 + 405.1938*_m01, 161.29*_m10 + 405.1938*_m11)
    _t2 = (172.2908*_m00 + 411.48*_m01, 172.2908*_m10 + 411.48*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch1_braces.profiles.count):
        if _pi in _used: continue
        _bb = Sketch1_braces.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch1_braces.profiles.item(_best_pi))
    _used.add(_best_pi)
    # Match profile by bbox (transformed): (123.19, 367.0938) to (167.5762, 411.48)
    _t1 = (123.19*_m00 + 367.0938*_m01, 123.19*_m10 + 367.0938*_m11)
    _t2 = (167.5762*_m00 + 411.48*_m01, 167.5762*_m10 + 411.48*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch1_braces.profiles.count):
        if _pi in _used: continue
        _bb = Sketch1_braces.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch1_braces.profiles.item(_best_pi))
    _used.add(_best_pi)
    # Match profile by bbox (transformed): (123.19, 362.3792) to (129.4762, 373.38)
    _t1 = (123.19*_m00 + 362.3792*_m01, 123.19*_m10 + 362.3792*_m11)
    _t2 = (129.4762*_m00 + 373.38*_m01, 129.4762*_m10 + 373.38*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch1_braces.profiles.count):
        if _pi in _used: continue
        _bb = Sketch1_braces.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    _prof_coll.add(Sketch1_braces.profiles.item(_best_pi))
    _used.add(_best_pi)
    inp = comp.features.extrudeFeatures.createInput(_prof_coll, NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("-post_w"))
    Extrude1 = comp.features.extrudeFeatures.add(inp)
    Extrude1.name = "Extrude1"
    left_brace_braces = Extrude1.bodies.item(0)
    left_brace_braces.name = "left_brace"

    # [87] Mirror: Mirror1
    comp = braces_c
    _Plane1_proxy = Plane1_beam
    for _occ in root.allOccurrences:
        if _occ.component.name == "beam":
            _Plane1_proxy = Plane1_beam.createForAssemblyContext(_occ); break
    Mirror1 = mirror_feats(comp, [left_brace_braces], _Plane1_proxy, "Mirror1")
    right_brace_braces = Mirror1.bodies.item(0)
    right_brace_braces.name = "right_brace"
    left_brace_braces = Mirror1.bodies.item(1)
    left_brace_braces.name = "left_brace"

    # [88] Extrude: Extrude2
    comp = braces_c
    _cx = (1.0, 0.0, 0.0)
    _cy = (0.0, 0.0, 1.0)
    _ax = Sketch1_braces.xDirection
    _ay = Sketch1_braces.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Match profile by bbox (transformed): (161.29, 411.48) to (172.2908, 416.1946)
    _t1 = (161.29*_m00 + 411.48*_m01, 161.29*_m10 + 411.48*_m11)
    _t2 = (172.2908*_m00 + 416.1946*_m01, 172.2908*_m10 + 416.1946*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch1_braces.profiles.count):
        _bb = Sketch1_braces.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    inp = comp.features.extrudeFeatures.createInput(Sketch1_braces.profiles.item(_best_pi), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("-post_w / 3 * 2"))
    Extrude2 = comp.features.extrudeFeatures.add(inp)
    Extrude2.name = "Extrude2"
    Body3_braces = Extrude2.bodies.item(0)
    Body3_braces.name = "Body3"

    # [89] Extrude: Extrude3
    comp = braces_c
    _cx = (1.0, 0.0, 0.0)
    _cy = (0.0, 0.0, 1.0)
    _ax = Sketch1_braces.xDirection
    _ay = Sketch1_braces.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    # Match profile by bbox (transformed): (161.29, 411.48) to (172.2908, 416.1946)
    _t1 = (161.29*_m00 + 411.48*_m01, 161.29*_m10 + 411.48*_m11)
    _t2 = (172.2908*_m00 + 416.1946*_m01, 172.2908*_m10 + 416.1946*_m11)
    _t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])
    _t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])
    _best_pi, _best_d = 0, 1e10
    for _pi in range(Sketch1_braces.profiles.count):
        _bb = Sketch1_braces.profiles.item(_pi).boundingBox
        _d = abs(_bb.minPoint.x - _t_mnx) + abs(_bb.minPoint.y - _t_mny) + abs(_bb.maxPoint.x - _t_mxx) + abs(_bb.maxPoint.y - _t_mxy)
        if _d < _best_d: _best_pi, _best_d = _pi, _d
    inp = comp.features.extrudeFeatures.createInput(Sketch1_braces.profiles.item(_best_pi), CUT)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("-post_w / 3"))
    inp.participantBodies = [Body3_braces]
    Extrude3 = comp.features.extrudeFeatures.add(inp)
    Extrude3.name = "Extrude3"

    # [90] ConstructionPlane: Plane1
    comp = braces_c
    _pl_inp = comp.constructionPlanes.createInput()
    _pl_inp.setByTwoPlanes(find_face_near(left_brace_braces, 123.19, -176.3183, 367.8796), find_face_near(left_brace_braces, 166.7904, -176.3183, 411.48))
    Plane1_braces = comp.constructionPlanes.add(_pl_inp)
    Plane1_braces.name = "Plane1"

    # [91] Mirror: Mirror2
    comp = braces_c
    Mirror2 = mirror_feats(comp, [Body3_braces], Plane1_braces, "Mirror2")
    Body4_braces = Mirror2.bodies.item(0)
    Body4_braces.name = "Body4"
    Body3_braces = Mirror2.bodies.item(1)
    Body3_braces.name = "Body3"

    # [92] Mirror: Mirror3
    comp = braces_c
    _Plane1_proxy = Plane1_beam
    for _occ in root.allOccurrences:
        if _occ.component.name == "beam":
            _Plane1_proxy = Plane1_beam.createForAssemblyContext(_occ); break
    Mirror3 = mirror_feats(comp, [Body3_braces, Body4_braces], _Plane1_proxy, "Mirror3")
    Body5_braces = Mirror3.bodies.item(0)
    Body5_braces.name = "Body5"
    Body6_braces = Mirror3.bodies.item(1)
    Body6_braces.name = "Body6"
    Body3_braces = Mirror3.bodies.item(2)
    Body3_braces.name = "Body3"
    Body4_braces = Mirror3.bodies.item(3)
    Body4_braces.name = "Body4"

    # [93] Combine: Combine1
    comp = braces_c
    Combine1 = combine(comp, left_brace_braces, [Body3_braces, Body4_braces], JOIN, False, "Combine1")

    # [94] Combine: Combine2
    comp = braces_c
    Combine2 = combine(comp, right_brace_braces, [Body5_braces, Body6_braces], JOIN, False, "Combine2")

    # [95] Combine: Combine1
    comp = beam_c
    Combine1 = combine(comp, Body2_beam, [Body1_rafts_1, Body2_rafts_1, Body3_rafts_1, Body4_rafts_1, Body5_rafts_1, Body6_rafts_1, Body7_rafts_1, Body8_rafts_1], CUT, True, "Combine1")

    # [96] Combine: Combine2
    comp = beam_c
    Combine2 = combine(comp, Body1_beam, [Body1_rafts_1, Body2_rafts_1, Body3_rafts_1, Body4_rafts_1, Body5_rafts_1, Body6_rafts_1, Body7_rafts_1, Body8_rafts_1], CUT, True, "Combine2")

    # ── FIT VIEW ──────────────────────────────────────────────────
    sp.apply_appearance("white oak")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam