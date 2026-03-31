"""Generated from capture_design — (Unsaved)
NOTE: Auto-generated. Features marked TODO need manual review."""
import adsk.core, adsk.fusion, math


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters

    # Clean up stale params from previous runs
    for old_p in ["leg_splay_tan", "leg_rake_tan", "back_rake_sin", "back_rake_cos",
                   "fan_splay", "leg_tenon_len", "scoop_offset", "scoop_center_h",
                   "seat_fil"]:
        p = params.itemByName(old_p)
        if p:
            try: p.deleteMe()
            except: pass

    # ── PARAMETERS ────────────────────────────────────────────────
    for name, expr, unit, comment in [
        ("seat_w", "18 in", "in", "Seat width at widest (front)"),
        ("seat_d", "15 in", "in", "Seat depth front to back"),
        ("seat_t", "1.75 in", "in", "Seat plank thickness"),
        ("seat_h", "17.5 in", "in", "Floor to seat top"),
        ("leg_dia", "1.375 in", "in", "Leg diameter at socket (top)"),
        ("leg_foot_dia", "0.875 in", "in", "Leg diameter at foot (bottom)"),
        ("leg_splay", "10", "", "Leg outward splay (degrees)"),
        ("leg_rake", "10", "", "Leg fore-aft rake (degrees)"),
        ("crest_w", "16 in", "in", "Crest rail width"),
        ("crest_t", "0.875 in", "in", "Crest cross-section thickness (Y)"),
        ("back_rake", "12", "", "Back rake angle (degrees)"),
        ("n_spindles", "7", "", "Number of back spindles"),
        ("spindle_dia", "0.5 in", "in", "Spindle diameter"),
        ("spindle_len", "17 in", "in", "Spindle length"),
        ("spindle_start_x", "6.5 in", "in", "Outermost spindle X distance from center"),
        ("spindle_y", "14 in", "in", "Spindle base Y position on seat"),
        ("back_curve_r", "20 in", "in", "Radius of spindle base arc (comfort curve)"),
        ("crest_curve_r", "18 in", "in", "Radius of crest rail arc (top curve)"),
        ("crest_h", "2 in", "in", "Crest rail cross-section height"),
        ("ch_leg", "0.125 in", "in", "Leg foot chamfer"),
        ("seat_fil_top", "0.125 in", "in", "Seat top edge fillet radius"),
        ("seat_fil_bot", "1 in", "in", "Seat bottom/corner fillet radius"),
        ("leg_to_edge", "2.2 in", "in", "Gap between leg and seat edge"),
        ("leg_tenon_dia", "0.875 in", "in", "Leg tenon diameter (into seat)"),
        ("leg_tenon_frac", "0.10", "", "Leg tenon as fraction of total length"),
        ("leg_shoulder_frac", "0.13", "", "Leg shoulder transition fraction"),
        # Stretcher profile
        ("str_mid_dia", "0.75 in", "in", "Stretcher center diameter (thickest)"),
        ("str_end_dia", "0.5 in", "in", "Stretcher tenon diameter (at ends)"),
        ("str_tenon_frac", "0.10", "", "Fraction of length that is tenon (each end)"),
        ("str_shoulder_frac", "0.20", "", "Fraction of length for shoulder transition"),
        ("tenon_ext", "0.1 in", "in", "Tenon extension beyond body"),
        ("seat_back_w", "14.0000 in", "in", "Back edge width"),
        ("seat_front_r", "68.8753 in", "in", "Front arc radius"),
        ("seat_back_r", "124.5584 in", "in", "Back arc radius"),
        # Seat scoop
        ("scoop_depth", "0.5 in", "in", "Max scoop depth"),
        ("scoop_start_y", "9 in", "in", "Distance from back edge where scoop begins"),
        ("scoop_trans_r", "14 in", "in", "Transition arc radius (must be > scoop_r)"),
        ("scoop_end_y", "2 in", "in", "Distance from front edge where scoop ends"),
        ("scoop_r", "13 in", "in", "Gouge radius (larger = shallower scoop)"),
        ("scoop_dist", "6 in", "in", "Distance between the two scoop centers"),
    ]:
        existing = params.itemByName(name)
        if existing:
            existing.expression = expr
        else:
            params.add(name, adsk.core.ValueInput.createByString(expr), unit, comment)

    for name, expr, unit, comment in [
        ("str_height_frac", "0.4", "", "Stretcher height as fraction of leg_h"),
        ("crest_fil", "crest_t / 2 - 0.05 in", "in", "Crest rail end fillet"),
        ("leg_h", "seat_h - seat_t", "in", "Leg height"),
        ("mid_x", "seat_w / 2", "in", "X midplane"),
        ("mid_y", "seat_d / 2", "in", "Y midplane"),
        # Leg position offsets (derived from trig params)
        ("leg_inset", "leg_dia / 2 + leg_to_edge", "in", "Leg center inset from seat edge"),
        ("splay_off", "leg_h * tan(leg_splay * 1 deg)", "in", "Leg splay offset at floor"),
        ("rake_off", "leg_h * tan(leg_rake * 1 deg)", "in", "Leg rake offset at floor"),
        ("back_edge_x", "( seat_w - seat_back_w ) / 2", "in", "Back edge X offset"),
        # Stretcher positions: leg center at str_height_frac of leg_h
        # At frac from floor: x = top_x + (bot_x - top_x) * (1 - frac)
        # = leg_inset + (-splay_off) * (1 - frac) = leg_inset - (1 - frac) * splay_off
        ("str_z", "leg_h * str_height_frac", "in", "Stretcher Z height"),
        ("fl_str_x", "leg_inset - ( 1 - str_height_frac ) * splay_off", "in", "FL stretcher X"),
        ("fl_str_y", "leg_inset - ( 1 - str_height_frac ) * rake_off", "in", "FL stretcher Y"),
        ("scoop_back_y", "seat_d - scoop_start_y", "in", "Scoop start Y from origin"),
        ("scoop_front_y", "scoop_end_y", "in", "Scoop end Y from origin"),
    ]:
        existing = params.itemByName(name)
        if existing:
            existing.expression = expr
        else:
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

    def mirror_bodies(comp, bodies, plane, name="Mir"):
        coll = adsk.core.ObjectCollection.create()
        for b in bodies: coll.add(b)
        inp = comp.features.mirrorFeatures.createInput(coll, plane)
        m = comp.features.mirrorFeatures.add(inp)
        m.name = name
        return m

    def mirror_feats(comp, entities, plane, name="Mir"):
        coll = adsk.core.ObjectCollection.create()
        for e in entities: coll.add(e)
        inp = comp.features.mirrorFeatures.createInput(coll, plane)
        inp.computeOption = adsk.fusion.PatternComputeOptions.AdjustPatternCompute
        m = comp.features.mirrorFeatures.add(inp)
        m.name = name
        return m

    # ── TIMELINE ──────────────────────────────────────────────────

    # [0] ConstructionPlane: XMid
    comp = root
    XMid = off_plane(comp, comp.yZConstructionPlane, "mid_x", "XMid")

    # [1] ConstructionPlane: YMid
    comp = root
    YMid = off_plane(comp, comp.xZConstructionPlane, "mid_y", "YMid")

    # [2] ComponentCreation: Seat
    comp = root
    Seat_occ = comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    Seat_occ.component.name = "Seat"
    Seat_c = Seat_occ.component

    # [3] ConstructionPlane: Seat_Pl
    comp = Seat_c
    Seat_Pl_Seat = off_plane(comp, comp.xYConstructionPlane, "seat_h - seat_t", "Seat_Pl")

    # [4] Sketch: Seat_Sk
    comp = Seat_c
    Seat_Sk_Seat = comp.sketches.add(Seat_Pl_Seat)
    Seat_Sk_Seat.name = "Seat_Sk"
    lns = Seat_Sk_Seat.sketchCurves.sketchLines
    # Coordinate transform: captured sketch axes -> actual sketch axes
    _cap_xd = (1.0, 0.0, 0.0)
    _cap_yd = (0.0, 1.0, 0.0)
    _act_xd = Seat_Sk_Seat.xDirection
    _act_yd = Seat_Sk_Seat.yDirection
    _m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z
    _m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z
    _m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z
    _m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z
    _cap_o = (0.0, 0.0, 40.005)
    _act_o = Seat_Sk_Seat.origin
    _do = (_cap_o[0]-_act_o.x, _cap_o[1]-_act_o.y, _cap_o[2]-_act_o.z)
    _dox = _do[0]*_act_xd.x + _do[1]*_act_xd.y + _do[2]*_act_xd.z
    _doy = _do[0]*_act_yd.x + _do[1]*_act_yd.y + _do[2]*_act_yd.z
    def _xf(sx, sy):
        return (sx * _m00 + sy * _m01 + _dox, sx * _m10 + sy * _m11 + _doy)
    arcs = Seat_Sk_Seat.sketchCurves.sketchArcs
    _cs_0 = _xf(45.72, 0.0)
    _ce_0 = _xf(40.64, 43.18)
    ln0 = lns.addByTwoPoints(P(_cs_0[0], _cs_0[1], 0), P(_ce_0[0], _ce_0[1], 0))
    _cs_1 = _xf(5.08, 43.18)
    _ce_1 = _xf(0.0, 0.0)
    ln1 = lns.addByTwoPoints(P(_cs_1[0], _cs_1[1], 0), P(_ce_1[0], _ce_1[1], 0))
    # Front arc: gentle bow from (0,0) to (seat_w,0)
    # Sagitta = R - sqrt(R^2 - (chord/2)^2) for the front arc
    import math as _m
    _fr = ev("seat_front_r")
    _sw = ev("seat_w")
    _sag_f = _fr - _m.sqrt(_fr*_fr - (_sw/2)*(_sw/2))
    _a2_s = _xf(0.0, 0.0)
    _a2_m = _xf(_sw/2, -_sag_f)  # midpoint bows forward (negative Y)
    _a2_e = _xf(_sw, 0.0)
    arc2 = arcs.addByThreePoints(P(_a2_s[0], _a2_s[1], 0), P(_a2_m[0], _a2_m[1], 0), P(_a2_e[0], _a2_e[1], 0))
    # Back arc: gentle curve from (back_right_x, seat_d) to (back_left_x, seat_d)
    _br = ev("seat_back_r")
    _bw = ev("seat_back_w")
    _bex = (ev("seat_w") - _bw) / 2  # back edge X offset
    _sag_b = _br - _m.sqrt(_br*_br - (_bw/2)*(_bw/2))
    _sd = ev("seat_d")
    _a3_s = _xf(_bex + _bw, _sd)
    _a3_m = _xf(_bex + _bw/2, _sd + _sag_b)  # midpoint bows backward (positive Y)
    _a3_e = _xf(_bex, _sd)
    arc3 = arcs.addByThreePoints(P(_a3_s[0], _a3_s[1], 0), P(_a3_m[0], _a3_m[1], 0), P(_a3_e[0], _a3_e[1], 0))
    _cs_4 = _xf(22.86, -5.0)
    _ce_4 = _xf(22.86, 48.18)
    ln4 = lns.addByTwoPoints(P(_cs_4[0], _cs_4[1], 0), P(_ce_4[0], _ce_4[1], 0))
    ln4.isConstruction = True
    # Connect endpoints to form a closed profile:
    # ln0: (seat_w, 0) -> (back_right_x, seat_d)   [right side line]
    # ln1: (back_left_x, seat_d) -> (0, 0)          [left side line]
    # arc2: center at (mid_x, front_r_offset), starts (0,0) sweeps pi -> (seat_w, 0) [front arc]
    # arc3: center at (mid_x, -back_r_offset), starts (back_right_x, seat_d) sweeps pi -> (back_left_x, seat_d) [back arc]
    # Connections: arc2.end -> ln0.start, ln0.end -> arc3.start, arc3.end -> ln1.start, ln1.end -> arc2.start
    gc_seat = Seat_Sk_Seat.geometricConstraints
    # Connect: front_arc end -> right_line start -> back_arc start -> ... -> left_line end -> front_arc start
    gc_seat.addCoincident(ln1.endSketchPoint, arc2.startSketchPoint)   # left line end = front arc start
    gc_seat.addCoincident(arc2.endSketchPoint, ln0.startSketchPoint)   # front arc end = right line start
    gc_seat.addCoincident(ln0.endSketchPoint, arc3.startSketchPoint)   # right line end = back arc start
    gc_seat.addCoincident(arc3.endSketchPoint, ln1.startSketchPoint)   # back arc end = left line start
    d = Seat_Sk_Seat.sketchDimensions
    try:
        d.addDistanceDimension(Seat_Sk_Seat.originPoint, ln4.startSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "seat_w / 2"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(Seat_Sk_Seat.originPoint, ln0.startSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "seat_w"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(Seat_Sk_Seat.originPoint, ln1.startSketchPoint,
            V if abs(_m01) < 0.5 else H, P(0, 0, 0)).parameter.expression = "seat_d"
    except: pass  # skip if already constrained
    try:
        d.addDistanceDimension(ln1.startSketchPoint, ln0.endSketchPoint,
            H if abs(_m10) < 0.5 else V, P(0, 0, 0)).parameter.expression = "seat_back_w"
    except: pass  # skip if already constrained
    d.addRadialDimension(arc2, P(175.943262, 0, 0)).parameter.expression = "seat_front_r"
    d.addRadialDimension(arc3, P(317.378336, 0, 0)).parameter.expression = "seat_back_r"
    gc = Seat_Sk_Seat.geometricConstraints
    try: (gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)(ln4)
    except: pass
    try: gc.addSymmetry(Seat_Sk_Seat.originPoint, ln0.startSketchPoint, ln4)
    except: pass
    try: gc.addSymmetry(ln1.startSketchPoint, ln0.endSketchPoint, ln4)
    except: pass
    Seat_Sk_Seat_prof = Seat_Sk_Seat.profiles.item(0) if Seat_Sk_Seat.profiles.count > 0 else None  # 1 profile(s)

    # [5] Extrude: SeatSlab
    comp = Seat_c
    _cx = (1.0, 0.0, 0.0)
    _cy = (0.0, 1.0, 0.0)
    _ax = Seat_Sk_Seat.xDirection
    _ay = Seat_Sk_Seat.yDirection
    _m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z
    _m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z
    _m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z
    _m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z
    _co = (0.0, 0.0, 40.005)
    _ao = Seat_Sk_Seat.origin
    _od = (_co[0]-_ao.x, _co[1]-_ao.y, _co[2]-_ao.z)
    _odx = _od[0]*_ax.x + _od[1]*_ax.y + _od[2]*_ax.z
    _ody = _od[0]*_ay.x + _od[1]*_ay.y + _od[2]*_ay.z
    # Debug: check sketch state
    print("Seat sketch: " + str(Seat_Sk_Seat.profiles.count) + " profiles, " + str(Seat_Sk_Seat.sketchCurves.count) + " curves")
    for ci in range(Seat_Sk_Seat.sketchCurves.count):
        c = Seat_Sk_Seat.sketchCurves.item(ci)
        print("  curve " + str(ci) + ": " + c.objectType + " isCon=" + str(c.isConstruction))
    # Select largest profile (the seat outline, not fragments from construction line)
    _best_pi, _best_area = 0, 0
    for _pi in range(Seat_Sk_Seat.profiles.count):
        _bb = Seat_Sk_Seat.profiles.item(_pi).boundingBox
        _area = abs(_bb.maxPoint.x - _bb.minPoint.x) * abs(_bb.maxPoint.y - _bb.minPoint.y)
        if _area > _best_area: _best_pi, _best_area = _pi, _area
    inp = comp.features.extrudeFeatures.createInput(Seat_Sk_Seat.profiles.item(_best_pi), NEWBODY)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("seat_t"))
    SeatSlab = comp.features.extrudeFeatures.add(inp)
    SeatSlab.name = "SeatSlab"
    Seat_Seat = SeatSlab.bodies.item(0)
    Seat_Seat.name = "Seat"

    # [6] ComponentCreation: Legs
    comp = root
    Legs_occ = comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    Legs_occ.component.name = "Legs"
    Legs_c = Legs_occ.component

    # ==== PARAMETRIC LOFTED LEGS ====
    comp = Legs_c

    # Compute splay/rake offsets in Python (Fusion expressions don't support tan/pi)
    def build_leg(comp, seat_body, seat_occ, name,
                  top_x_expr, top_y_expr, splay_dir_x, splay_dir_y):
        """Turned leg via Revolve. Axis sketch at seat underside.
        Top point (seat joint) is fixed. Foot position derived from splay offset.
        splay_dir_x/y: -1 or +1 for foot offset direction from top point.
        """
        import math as _ml
        from helpers import sp as _sp

        top_x_val = ev(top_x_expr)
        top_y_val = ev(top_y_expr)
        splay_off_val = ev("splay_off")
        rake_off_val = ev("rake_off")
        bot_x_val = top_x_val + splay_dir_x * splay_off_val
        bot_y_val = top_y_val + splay_dir_y * rake_off_val
        top_z = ev("leg_h")

        # ---- Axis sketch at seat underside (Z = leg_h) ----
        seat_pl = off_plane(comp, comp.xYConstructionPlane, "leg_h", name + "_SeatPl")
        ax_sk = comp.sketches.add(seat_pl)
        ax_sk.name = name + "_AxisSk"
        m2s_ax = ax_sk.modelToSketchSpace

        # Project seat for reference
        seat_proxy = seat_body.createForAssemblyContext(seat_occ)
        ax_sk.project(seat_proxy)
        _sp.refs_to_construction(ax_sk)

        # ---- Find projected seat edges ----
        front_edge = None; side_edge = None
        front_ref_pt = m2s_ax(P(ev("mid_x"), 0, top_z))
        side_ref_pt = m2s_ax(P(0, ev("mid_y"), top_z))

        best_front_d = 1e10; best_side_d = 1e10
        for ci in range(ax_sk.sketchCurves.count):
            c = ax_sk.sketchCurves.item(ci)
            if not (c.isConstruction or c.isReference): continue
            sg = c.startSketchPoint.geometry; eg = c.endSketchPoint.geometry
            mid_x_c = (sg.x + eg.x) / 2; mid_y_c = (sg.y + eg.y) / 2

            if c.objectType.endswith('SketchArc'):
                d = _ml.sqrt((mid_x_c - front_ref_pt.x)**2 + (mid_y_c - front_ref_pt.y)**2)
                if d < best_front_d:
                    best_front_d = d; front_edge = c
            elif c.objectType.endswith('SketchLine'):
                dx = abs(eg.x - sg.x); dy = abs(eg.y - sg.y)
                if dy > dx * 0.5:
                    d = _ml.sqrt((mid_x_c - side_ref_pt.x)**2 + (mid_y_c - side_ref_pt.y)**2)
                    if d < best_side_d:
                        best_side_d = d; side_edge = c

        print(name + " edges: front=" + str(front_edge is not None) + " side=" + str(side_edge is not None))

        # ---- Find front-left corner (closest endpoints between front_edge and side_edge) ----
        corner_pt = None
        corner_arc_pt = None
        if front_edge and side_edge:
            best_d = 1e10
            for sp1 in [side_edge.startSketchPoint, side_edge.endSketchPoint]:
                for sp2 in [front_edge.startSketchPoint, front_edge.endSketchPoint]:
                    d = _ml.sqrt((sp1.geometry.x - sp2.geometry.x)**2 +
                                 (sp1.geometry.y - sp2.geometry.y)**2)
                    if d < best_d:
                        best_d = d; corner_pt = sp1; corner_arc_pt = sp2
            pass  # corner found

        # ---- Leg top from corner: along side edge + perpendicular ----
        gc_ax = ax_sk.geometricConstraints
        ax_dims = ax_sk.sketchDimensions
        AL = adsk.fusion.DimensionOrientations.AlignedDimensionOrientation
        lte = ev("leg_to_edge")

        if corner_pt and side_edge:
            # Side edge direction from corner
            other_end = side_edge.endSketchPoint if \
                _ml.sqrt((side_edge.startSketchPoint.geometry.x - corner_pt.geometry.x)**2 +
                         (side_edge.startSketchPoint.geometry.y - corner_pt.geometry.y)**2) < 0.1 \
                else side_edge.startSketchPoint
            se_dx = other_end.geometry.x - corner_pt.geometry.x
            se_dy = other_end.geometry.y - corner_pt.geometry.y
            se_len = _ml.sqrt(se_dx**2 + se_dy**2)
            se_ux, se_uy = se_dx/se_len, se_dy/se_len

            # Perpendicular direction (inward toward seat center)
            perp_ux, perp_uy = -se_uy, se_ux
            mid_sk = m2s_ax(P(ev("mid_x"), ev("mid_y"), top_z))
            if (mid_sk.x - corner_pt.geometry.x) * perp_ux + \
               (mid_sk.y - corner_pt.geometry.y) * perp_uy < 0:
                perp_ux, perp_uy = -perp_ux, -perp_uy

            # Point along side edge at leg_to_edge from corner
            along_end = P(corner_pt.geometry.x + se_ux * lte,
                          corner_pt.geometry.y + se_uy * lte, 0)
            along_line = ax_sk.sketchCurves.sketchLines.addByTwoPoints(
                corner_pt, along_end)
            along_line.isConstruction = True
            gc_ax.addCollinear(along_line, side_edge)

            # Perpendicular from that point, length = leg_to_edge
            leg_top = P(along_end.x + perp_ux * lte,
                        along_end.y + perp_uy * lte, 0)
            perp_line = ax_sk.sketchCurves.sketchLines.addByTwoPoints(
                along_line.endSketchPoint, leg_top)
            perp_line.isConstruction = True
            gc_ax.addPerpendicular(perp_line, along_line)

            # Dimension both construction lines = leg_to_edge
            ax_dims.addDistanceDimension(
                along_line.startSketchPoint, along_line.endSketchPoint, AL,
                P(along_end.x + perp_ux, along_end.y + perp_uy, 0)
            ).parameter.expression = "leg_to_edge"
            ax_dims.addDistanceDimension(
                perp_line.startSketchPoint, perp_line.endSketchPoint, AL,
                P(leg_top.x + se_ux, leg_top.y + se_uy, 0)
            ).parameter.expression = "leg_to_edge"
            print(name + " leg top: corner + leg_to_edge along side + perpendicular")

            # Leg top position = end of perpendicular line
            tc = perp_line.endSketchPoint.geometry
            # Recompute foot from actual leg top (not old leg_inset position)
            s2m_ax = ax_sk.sketchToModelSpace
            tc_model = s2m_ax(P(tc.x, tc.y, 0))
            bot_x_val = tc_model.x + splay_dir_x * splay_off_val
            bot_y_val = tc_model.y + splay_dir_y * rake_off_val
        else:
            # Fallback: use computed position
            tc = m2s_ax(P(top_x_val, top_y_val, top_z))
            print(name + " leg top: fallback to computed position")

        # Foot projection on this plane
        bc = m2s_ax(P(bot_x_val, bot_y_val, top_z))

        # Draw axis line from leg top to foot projection
        ax_line = ax_sk.sketchCurves.sketchLines.addByTwoPoints(
            P(tc.x, tc.y, 0), P(bc.x, bc.y, 0))

        # Constrain axis start to perp line end (parametric link)
        if corner_pt and side_edge:
            gc_ax.addCoincident(ax_line.startSketchPoint, perp_line.endSketchPoint)

        # Dimension foot offset FROM top point (always positive splay_off/rake_off)
        _orient = _sp.probe_orientations(ax_sk, top_x_val, top_y_val, top_z)
        ax_dims.addDistanceDimension(
            ax_line.startSketchPoint, ax_line.endSketchPoint, _orient["x"],
            P((tc.x + bc.x) / 2, tc.y - 1, 0)
        ).parameter.expression = "splay_off"
        ax_dims.addDistanceDimension(
            ax_line.startSketchPoint, ax_line.endSketchPoint, _orient["y"],
            P(tc.x - 1, (tc.y + bc.y) / 2, 0)
        ).parameter.expression = "rake_off"

        # ---- Profile plane: vertical plane through the axis projection ----
        # ---- Profile plane + revolve ----
        prof_pl_inp = comp.constructionPlanes.createInput()
        prof_pl_inp.setByAngle(ax_line, adsk.core.ValueInput.createByString("90 deg"), seat_pl)
        prof_pl = comp.constructionPlanes.add(prof_pl_inp)
        prof_pl.name = name + "_ProfPl"

        prof_sk = comp.sketches.add(prof_pl)
        prof_sk.name = name + "_Prof"
        lines_p = prof_sk.sketchCurves.sketchLines
        gc = prof_sk.geometricConstraints
        m2s_prof = prof_sk.modelToSketchSpace

        # Step 1: Project the axis line → 2 reference endpoints
        prof_sk.project(ax_line)
        _sp.refs_to_construction(prof_sk)

        # Step 2: Identify inside vs outside using known model coords
        ax_s2m = ax_sk.sketchToModelSpace
        start_model = ax_s2m(P(ax_line.startSketchPoint.geometry.x,
                                ax_line.startSketchPoint.geometry.y, 0))
        end_model = ax_s2m(P(ax_line.endSketchPoint.geometry.x,
                              ax_line.endSketchPoint.geometry.y, 0))
        # Convert to profile sketch coords
        start_in_prof = m2s_prof(start_model)
        end_in_prof = m2s_prof(end_model)

        # Find the projected axis line (only construction line so far)
        proj_ax = None
        for ci in range(prof_sk.sketchCurves.count):
            c = prof_sk.sketchCurves.item(ci)
            if c.isConstruction and c.objectType.endswith('SketchLine'):
                proj_ax = c; break

        if not proj_ax:
            print(name + ": no projected axis"); return None, None

        # Match projected endpoints to known model positions
        ps = proj_ax.startSketchPoint.geometry
        pe = proj_ax.endSketchPoint.geometry
        d_start_to_start = _ml.sqrt((ps.x-start_in_prof.x)**2 + (ps.y-start_in_prof.y)**2)
        d_start_to_end = _ml.sqrt((ps.x-end_in_prof.x)**2 + (ps.y-end_in_prof.y)**2)

        if d_start_to_start < d_start_to_end:
            # proj start = ax_line start, proj end = ax_line end
            # ax_line start is (leg_inset, leg_inset) = inside
            inside_pt = proj_ax.startSketchPoint
            outside_pt = proj_ax.endSketchPoint
        else:
            inside_pt = proj_ax.endSketchPoint
            outside_pt = proj_ax.startSketchPoint

        # Step 3: Compute seat top and floor positions in profile sketch coords
        seat_ref = m2s_prof(P(start_model.x, start_model.y, ev("seat_h")))
        floor_ref = m2s_prof(P(end_model.x, end_model.y, 0))

        # Step 4: Project seat body for reference
        seat_proxy = seat_body.createForAssemblyContext(seat_occ)
        prof_sk.project(seat_proxy)
        _sp.refs_to_construction(prof_sk)

        # Find seat top line by proximity to known seat top position
        seat_top_line = _sp.find_nearest_line(prof_sk,
            P(start_model.x, start_model.y, ev("seat_h")))
        print(name + " seat_top_line: " + ("found" if seat_top_line else "NOT FOUND"))

        # Step 5: Construct floor reference line at model Z=0
        floor_line = _sp.construct_ref_line(prof_sk, model_z=0,
            model_x_range=(end_model.x - 10, end_model.x + 10),
            model_y=end_model.y)

        # Step 6: Drop inside point to seat top, outside point to floor
        if seat_top_line:
            seat_drop = lines_p.addByTwoPoints(
                inside_pt, P(inside_pt.geometry.x, seat_ref.y, 0))
            seat_drop.isConstruction = True
            gc.addPerpendicular(seat_drop, seat_top_line)
            seat_joint = seat_drop.endSketchPoint
        else:
            seat_joint = inside_pt

        floor_drop = lines_p.addByTwoPoints(
            outside_pt, P(outside_pt.geometry.x, floor_ref.y, 0))
        floor_drop.isConstruction = True
        gc.addPerpendicular(floor_drop, floor_line)
        foot_point = floor_drop.endSketchPoint

        # Step 7: Compute axis direction from seat joint to foot
        s_t = seat_joint.geometry
        s_b = foot_point.geometry
        adx = s_b.x - s_t.x; ady = s_b.y - s_t.y
        alen = _ml.sqrt(adx*adx + ady*ady)
        if alen < 0.1:
            print(name + ": axis too short"); return None, None
        aux, auy = adx/alen, ady/alen
        anx, any_ = -auy, aux

        top_r = ev("leg_dia") / 2
        bot_r = ev("leg_foot_dia") / 2
        tenon_r = ev("leg_tenon_dia") / 2
        tenon_frac = ev("leg_tenon_frac")
        shoulder_frac = ev("leg_shoulder_frac")
        total_len = alen

        # Step 8: Draw turned profile from seat joint to foot
        pts = [(0.0, tenon_r), (tenon_frac, tenon_r),
               (shoulder_frac, top_r), (1.0, bot_r)]
        sk_pts = [P(s_t.x+aux*total_len*f+anx*r,
                     s_t.y+auy*total_len*f+any_*r, 0) for f,r in pts]

        L0 = lines_p.addByTwoPoints(sk_pts[0], sk_pts[1])
        L1 = lines_p.addByTwoPoints(L0.endSketchPoint, sk_pts[2])
        L2 = lines_p.addByTwoPoints(L1.endSketchPoint, sk_pts[3])
        # Close profile using the drop endpoints directly (not fresh points)
        L_r = lines_p.addByTwoPoints(L2.endSketchPoint, foot_point)
        L_bot = lines_p.addByTwoPoints(foot_point, seat_joint)
        L_l = lines_p.addByTwoPoints(seat_joint, L0.startSketchPoint)

        gc.addParallel(L0, L_bot)

        len_param = name + "_len"
        tl_in = total_len / 2.54
        ep_p = design.userParameters.itemByName(len_param)
        if ep_p: ep_p.expression = str(round(tl_in, 6)) + " in"
        else: design.userParameters.add(len_param,
            adsk.core.ValueInput.createByString(str(round(tl_in, 6)) + " in"), "in", "")

        dims = prof_sk.sketchDimensions
        AL = adsk.fusion.DimensionOrientations.AlignedDimensionOrientation
        dims.addDistanceDimension(L_l.startSketchPoint, L_l.endSketchPoint, AL,
            P(L_l.startSketchPoint.geometry.x+anx*2, L_l.startSketchPoint.geometry.y+any_*2, 0)
        ).parameter.expression = "leg_tenon_dia / 2"
        dims.addDistanceDimension(L_r.startSketchPoint, L_r.endSketchPoint, AL,
            P(L_r.startSketchPoint.geometry.x+anx*2, L_r.startSketchPoint.geometry.y+any_*2, 0)
        ).parameter.expression = "leg_foot_dia / 2"
        dims.addDistanceDimension(L0.startSketchPoint, L0.endSketchPoint, AL,
            P(sk_pts[0].x+aux, sk_pts[0].y+auy, 0)
        ).parameter.expression = "leg_tenon_frac * " + len_param

        scon = lines_p.addByTwoPoints(
            P(s_t.x+aux*total_len*shoulder_frac, s_t.y+auy*total_len*shoulder_frac, 0),
            L1.endSketchPoint)
        scon.isConstruction = True
        gc.addPerpendicular(scon, L_bot)
        gc.addCoincident(scon.startSketchPoint, L_bot)
        dims.addDistanceDimension(scon.startSketchPoint, scon.endSketchPoint, AL,
            P(scon.startSketchPoint.geometry.x+anx*2, scon.startSketchPoint.geometry.y+any_*2, 0)
        ).parameter.expression = "leg_dia / 2"
        dims.addDistanceDimension(L_bot.endSketchPoint, scon.startSketchPoint, AL,
            P(scon.startSketchPoint.geometry.x-aux*2, scon.startSketchPoint.geometry.y-auy*2, 0)
        ).parameter.expression = "leg_shoulder_frac * " + len_param

        prof = _sp.smallest_profile(prof_sk) if prof_sk.profiles.count > 0 else None
        if not prof:
            print(name + ": no profile"); return None, None

        rev = comp.features.revolveFeatures.createInput(prof, L_bot, NEWBODY)
        rev.setAngleExtent(False, adsk.core.ValueInput.createByString("360 deg"))
        rf = comp.features.revolveFeatures.add(rev)
        rf.name = name; body = rf.bodies.item(0); body.name = name

        # Tenon extension: extrude the tenon end face outward
        tenon_face = find_face(body, "z", +1)
        if tenon_face and tenon_face.loops.count > 0:
            te_ext = comp.features.extrudeFeatures.createInput(
                tenon_face, JOIN)
            te_ext.setDistanceExtent(False, adsk.core.ValueInput.createByString("tenon_ext"))
            te_ext.participantBodies = [body]
            te_f = comp.features.extrudeFeatures.add(te_ext)
            te_f.name = name + "_TenExt"

        print("Built " + name)
        return rf, body







    # Find Seat body for face-relative sketching
    Seat_body_ref = None
    Seat_occ_ref = None
    for i in range(root.occurrences.count):
        occ = root.occurrences.item(i)
        if occ.component.name == "Seat":
            Seat_occ_ref = occ
            for j in range(occ.component.bRepBodies.count):
                if occ.component.bRepBodies.item(j).name == "Seat":
                    Seat_body_ref = occ.component.bRepBodies.item(j)
            break

    # FL: front-left. Top at (leg_inset, leg_inset). Foot splays outward (-X, -Y)
    # Build FL only, then mirror for all other legs
    # FL: foot splays outward (-X = left, -Y = forward)
    fl_feat, fl_body = build_leg(comp, Seat_body_ref, Seat_occ_ref, "Leg_FL",
        "leg_inset", "leg_inset", -1, -1)

    # Mirror plane perpendicular to seat side edge at its midpoint
    # Draw line from (0,0) to (back_edge_x, seat_d) with parametric dimensions
    # so it updates when seat_d or seat_back_w change.
    import math as _mlg
    from helpers import sp as _sp_mir

    side_sk = comp.sketches.add(comp.xYConstructionPlane)
    side_sk.name = "SideEdge_Sk"
    m2s_side = side_sk.modelToSketchSpace
    bex = ev("back_edge_x")
    sd = ev("seat_d")
    s_front = m2s_side(P(0, 0, 0))
    s_back = m2s_side(P(bex, sd, 0))
    side_line = side_sk.sketchCurves.sketchLines.addByTwoPoints(
        P(s_front.x, s_front.y, 0), P(s_back.x, s_back.y, 0))
    side_line.isConstruction = True

    # Parametric dimensions: pin start at origin, dimension end point
    orient_side = _sp_mir.probe_orientations(side_sk, bex/2, sd/2, 0)
    side_dims = side_sk.sketchDimensions
    # Fix start point to origin
    side_sk.geometricConstraints.addCoincident(
        side_line.startSketchPoint, side_sk.originPoint)
    # End point X = back_edge_x
    side_dims.addDistanceDimension(
        side_sk.originPoint, side_line.endSketchPoint, orient_side["x"],
        P(s_back.x / 2, s_back.y + 1, 0)
    ).parameter.expression = "back_edge_x"
    # End point Y = seat_d
    side_dims.addDistanceDimension(
        side_sk.originPoint, side_line.endSketchPoint, orient_side["y"],
        P(s_back.x + 1, s_back.y / 2, 0)
    ).parameter.expression = "seat_d"

    # Create path from side line, then plane at midpoint (0.5 = 50%)
    side_path = comp.features.createPath(side_line, False)
    side_mid_inp = comp.constructionPlanes.createInput()
    side_mid_inp.setByDistanceOnPath(side_path, adsk.core.ValueInput.createByString("0.5"))
    side_mid_pl = comp.constructionPlanes.add(side_mid_inp)
    side_mid_pl.name = "LegSideMid"

    # Chamfer FL leg foot edges BEFORE mirroring (mirrors replicate it)
    if ev("ch_leg") > 0:
        bot_edges = adsk.core.ObjectCollection.create()
        for ei in range(fl_body.edges.count):
            e = fl_body.edges.item(ei)
            if e.startVertex and e.endVertex and e.startVertex.geometry.z < 0.5 and e.endVertex.geometry.z < 0.5:
                bot_edges.add(e)
        if bot_edges.count > 0:
            ch = comp.features.chamferFeatures.createInput2()
            ch.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                bot_edges, adsk.core.ValueInput.createByString("ch_leg"), True)
            comp.features.chamferFeatures.add(ch).name = "Leg_FL_Ch"

    # Mirror FL across side edge midplane → BL (before wedges)
    mir_y = mirror_bodies(comp, [fl_body], side_mid_pl, "LegMirY")
    bl_body = mir_y.bodies.item(0)
    bl_body.name = "Leg_BL"

    # Tenon wedges on FL and BL independently (correct grain_dir on each)
    from woodworking.templates import tenon_wedge as tw
    import importlib; importlib.reload(tw)
    tw.define_params(params, prefix="tw", slot_w="0.08 in",
                     depth_ratio="1 / 2", offset_ratio="1 / 4")
    fl_end_face = find_face(fl_body, "z", +1)
    fl_wedge = tw.round_tenon(comp, tenon_body=fl_body,
        mortise_body=Seat_body_ref,
        end_face=fl_end_face,
        tenon_depth_expr="seat_t",
        tenon_diam_expr="leg_tenon_dia",
        grain_dir=(0, 1, 0),  # seat grain front-to-back (Y)
        name="TW_FL", ev=ev)
    bl_end_face = find_face(bl_body, "z", +1)
    bl_wedge = tw.round_tenon(comp, tenon_body=bl_body,
        mortise_body=Seat_body_ref,
        end_face=bl_end_face,
        tenon_depth_expr="seat_t",
        tenon_diam_expr="leg_tenon_dia",
        grain_dir=(0, 1, 0),  # seat grain front-to-back (Y)
        name="TW_BL", ev=ev)

    # Mirror FL+BL across XMid → FR+BR (slots replicate via mirror)
    mir_coll = adsk.core.ObjectCollection.create()
    mir_coll.add(fl_body)
    mir_coll.add(bl_body)
    mir_inp = comp.features.mirrorFeatures.createInput(mir_coll, XMid)
    mir_feat = comp.features.mirrorFeatures.add(mir_inp)
    mir_feat.name = "LegMirX"
    for i in range(mir_feat.bodies.count):
        b = mir_feat.bodies.item(i)
        if b.boundingBox.minPoint.y < ev("mid_y"):
            b.name = "Leg_FR"
        else:
            b.name = "Leg_BR"
    # Mirror wedge bodies separately across XMid
    mir_w_x = mirror_bodies(comp, [fl_wedge, bl_wedge], XMid, "WedgeMirX")
    for i in range(mir_w_x.bodies.count):
        b = mir_w_x.bodies.item(i)
        if b.boundingBox.minPoint.y < ev("mid_y"):
            b.name = "TW_FR"
        else:
            b.name = "TW_BR"
    print("Legs: 4 + 4 wedges (chamfered, wedged, mirrored)")

    # ==== STRETCHERS (H-stretcher via Loft between leg centers) ====
    # Each side stretcher is a Loft connecting FL and BL leg centers at stretcher height.
    # Cross stretcher connects midpoints of the two side stretchers.
    comp = root
    Stretchers_occ = comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    Stretchers_occ.component.name = "Stretchers"
    Stretchers_c = Stretchers_occ.component
    comp = Stretchers_c

    str_z = ev("str_z")
    from helpers import sp as _sps2

    # ---- Left stretcher: project FL and BL legs, connect their centers ----
    str_pl = off_plane(comp, comp.xYConstructionPlane, "str_z", "Str_Hz")
    str_sk = comp.sketches.add(str_pl)
    str_sk.name = "StrLeft_Axis"

    # Use the FL and BL body references saved during leg building
    # fl_body and bl_body are still valid from the leg section above
    _legs_occ = None
    for oi in range(root.occurrences.count):
        occ = root.occurrences.item(oi)
        if occ.component.name == "Legs":
            _legs_occ = occ; break
    fl_leg = fl_body  # saved from build_leg call
    bl_leg = bl_body  # saved from mirror
    legs_occ = _legs_occ
    # Intersect leg bodies with sketch plane → cross-section at str_z
    fl_proxy = fl_leg.createForAssemblyContext(legs_occ)
    bl_proxy = bl_leg.createForAssemblyContext(legs_occ)
    str_sk.intersectWithSketchPlane([fl_proxy, bl_proxy])
    _sps2.refs_to_construction(str_sk)

    # Find projected ellipses (closest to approximate leg positions)
    import math as _mstr
    m2s_str = str_sk.modelToSketchSpace
    fl_approx = m2s_str(P(ev("fl_str_x"), ev("fl_str_y"), str_z))
    bl_bb = bl_leg.boundingBox
    bl_ax = (bl_bb.minPoint.x + bl_bb.maxPoint.x) / 2
    bl_ay = (bl_bb.minPoint.y + bl_bb.maxPoint.y) / 2
    bl_approx = m2s_str(P(bl_ax, bl_ay, str_z))

    fl_info = None  # (center_sketch_point, distance, curve)
    bl_info = None
    for ci in range(str_sk.sketchCurves.count):
        c = str_sk.sketchCurves.item(ci)
        if hasattr(c, 'centerSketchPoint') and c.centerSketchPoint:
            cp = c.centerSketchPoint.geometry
            d_fl = _mstr.sqrt((cp.x-fl_approx.x)**2 + (cp.y-fl_approx.y)**2)
            d_bl = _mstr.sqrt((cp.x-bl_approx.x)**2 + (cp.y-bl_approx.y)**2)
            if fl_info is None or d_fl < fl_info[1]:
                fl_info = (c.centerSketchPoint, d_fl, c)
            if bl_info is None or d_bl < bl_info[1]:
                bl_info = (c.centerSketchPoint, d_bl, c)

    def _outer_extreme(curve, dir_x, dir_y, m2s_fn):
        """Sample curve to find point most extreme in direction (dir_x, dir_y)."""
        geo = curve.worldGeometry
        evaluator = geo.evaluator
        _, min_p, max_p = evaluator.getParameterExtents()
        best_proj = -1e10
        best_pt = None
        for i in range(72):
            t = min_p + (max_p - min_p) * i / 72
            ok, pt = evaluator.getPointAtParameter(t)
            if ok:
                s = m2s_fn(pt)
                proj = s.x * dir_x + s.y * dir_y
                if proj > best_proj:
                    best_proj = proj
                    best_pt = s
        return best_pt

    if fl_info and bl_info and fl_info[0] != bl_info[0]:
        fl_c = fl_info[0].geometry
        bl_c = bl_info[0].geometry
        # Direction FL→BL
        dx = bl_c.x - fl_c.x; dy = bl_c.y - fl_c.y
        dd = _mstr.sqrt(dx*dx + dy*dy)
        ux, uy = dx/dd, dy/dd

        # Sample actual outer extremes — no constraint ambiguity
        fl_outer = _outer_extreme(fl_info[2], -ux, -uy, m2s_str)
        bl_outer = _outer_extreme(bl_info[2], ux, uy, m2s_str)

        if fl_outer and bl_outer:
            ax_line = str_sk.sketchCurves.sketchLines.addByTwoPoints(
                P(fl_outer.x, fl_outer.y, 0), P(bl_outer.x, bl_outer.y, 0))
            print("Stretcher axis: sampled outer extremes")
        else:
            ax_line = str_sk.sketchCurves.sketchLines.addByTwoPoints(fl_info[0], bl_info[0])
            print("Stretcher axis: fallback to centers")
    else:
        fl_s = m2s_str(P(ev("fl_str_x"), ev("fl_str_y"), str_z))
        bl_s = m2s_str(P(bl_ax, bl_ay, str_z))
        ax_line = str_sk.sketchCurves.sketchLines.addByTwoPoints(
            P(fl_s.x, fl_s.y, 0), P(bl_s.x, bl_s.y, 0))
        print("Stretcher axis: fallback positions")

    # Profile plane + turned profile
    vert_inp = comp.constructionPlanes.createInput()
    vert_inp.setByAngle(ax_line, adsk.core.ValueInput.createByString("90 deg"), str_pl)
    vert_pl = comp.constructionPlanes.add(vert_inp)
    vert_pl.name = "StrLeft_Vert"

    p_sk = comp.sketches.add(vert_pl)
    p_sk.name = "StrLeft_Prof"
    m2s_p = p_sk.modelToSketchSpace

    # Project the axis line into the profile sketch → parametric reference endpoints
    p_sk.project(ax_line)
    _sps2.refs_to_construction(p_sk)

    # Find the projected axis line (the construction line in the profile sketch)
    proj_ax = None
    for ci in range(p_sk.sketchCurves.count):
        c = p_sk.sketchCurves.item(ci)
        if (c.isConstruction or c.isReference) and c.objectType.endswith('SketchLine'):
            proj_ax = c; break

    if proj_ax:
        ps_s = proj_ax.startSketchPoint.geometry
        ps_e = proj_ax.endSketchPoint.geometry
    else:
        # Fallback: compute from script-time coords
        sm = str_sk.sketchToModelSpace
        s_m = sm(P(ax_line.startSketchPoint.geometry.x, ax_line.startSketchPoint.geometry.y, 0))
        e_m = sm(P(ax_line.endSketchPoint.geometry.x, ax_line.endSketchPoint.geometry.y, 0))
        ps_s = m2s_p(s_m)
        ps_e = m2s_p(e_m)

    adx = ps_e.x - ps_s.x
    ady = ps_e.y - ps_s.y
    alen = _mstr.sqrt(adx*adx + ady*ady)
    aux_s, auy_s = adx/alen, ady/alen
    anx_s, any_s = -auy_s, aux_s

    end_r = ev("str_end_dia") / 2
    mid_r = ev("str_mid_dia") / 2
    # Tenon must pass fully through the leg — use leg_dia * 1.5 to account
    # for the elliptical cross-section when the leg is tilted (splay + rake)
    through_dist = ev("leg_dia") * 1.5
    tenon_f = min(through_dist / alen, 0.25)  # cap at 25%
    shldr_f = tenon_f + ev("str_shoulder_frac") * (0.5 - tenon_f)

    pts = [(0.0, end_r), (tenon_f, end_r), (shldr_f, mid_r),
           (0.5, mid_r), (1.0-shldr_f, mid_r), (1.0-tenon_f, end_r), (1.0, end_r)]
    sk_pts = [P(ps_s.x+aux_s*alen*f+anx_s*r, ps_s.y+auy_s*alen*f+any_s*r, 0) for f,r in pts]

    lns = p_sk.sketchCurves.sketchLines
    L0=lns.addByTwoPoints(sk_pts[0],sk_pts[1]); L1=lns.addByTwoPoints(L0.endSketchPoint,sk_pts[2])
    L2=lns.addByTwoPoints(L1.endSketchPoint,sk_pts[3]); L3=lns.addByTwoPoints(L2.endSketchPoint,sk_pts[4])
    L4=lns.addByTwoPoints(L3.endSketchPoint,sk_pts[5]); L5=lns.addByTwoPoints(L4.endSketchPoint,sk_pts[6])
    L_r=lns.addByTwoPoints(L5.endSketchPoint,P(ps_e.x,ps_e.y,0))
    L_bot=lns.addByTwoPoints(L_r.endSketchPoint,P(ps_s.x,ps_s.y,0))
    L_l=lns.addByTwoPoints(L_bot.endSketchPoint,L0.startSketchPoint)

    gc=p_sk.geometricConstraints
    gc.addParallel(L0,L_bot); gc.addParallel(L5,L_bot); gc.addParallel(L2,L_bot); gc.addParallel(L3,L_bot)
    gc.addEqual(L5,L0); gc.addEqual(L3,L2)
    # Constrain L_bot endpoints to projected axis endpoints (parametric link)
    if proj_ax:
        gc.addCoincident(L_r.endSketchPoint, proj_ax.endSketchPoint)
        gc.addCoincident(L_bot.endSketchPoint, proj_ax.startSketchPoint)

    dims=p_sk.sketchDimensions; AL=adsk.fusion.DimensionOrientations.AlignedDimensionOrientation
    dims.addDistanceDimension(L_l.startSketchPoint,L_l.endSketchPoint,AL,
        P(L_l.startSketchPoint.geometry.x+anx_s*2,L_l.startSketchPoint.geometry.y+any_s*2,0)
    ).parameter.expression="str_end_dia / 2"
    mid_con=lns.addByTwoPoints(P((ps_s.x+ps_e.x)/2,(ps_s.y+ps_e.y)/2,0),L2.endSketchPoint)
    mid_con.isConstruction=True; gc.addPerpendicular(mid_con,L_bot); gc.addCoincident(mid_con.startSketchPoint,L_bot)
    dims.addDistanceDimension(mid_con.startSketchPoint,mid_con.endSketchPoint,AL,
        P(mid_con.startSketchPoint.geometry.x+anx_s*2,mid_con.startSketchPoint.geometry.y+any_s*2,0)
    ).parameter.expression="str_mid_dia / 2"

    prof=p_sk.profiles.item(0) if p_sk.profiles.count>0 else None
    Str_Left = None
    if prof:
        rev=comp.features.revolveFeatures.createInput(prof,L_bot,NEWBODY)
        rev.setAngleExtent(False,adsk.core.ValueInput.createByString("360 deg"))
        rf=comp.features.revolveFeatures.add(rev); rf.name="Str_Left"
        Str_Left=rf.bodies.item(0); Str_Left.name="Str_Left"

        # Tenon extensions on both ends of side stretcher
        str_faces = []
        for fi in range(Str_Left.faces.count):
            f = Str_Left.faces.item(fi)
            if isinstance(f.geometry, adsk.core.Plane):
                str_faces.append(f)
        str_faces.sort(key=lambda f: f.area)
        for tfi, tf in enumerate(str_faces[:2]):
            if tf.loops.count > 0:
                te_inp2 = comp.features.extrudeFeatures.createInput(tf, JOIN)
                te_inp2.setDistanceExtent(False, adsk.core.ValueInput.createByString("tenon_ext"))
                te_inp2.participantBodies = [Str_Left]
                te_f2 = comp.features.extrudeFeatures.add(te_inp2)
                te_f2.name = "StrL_TenExt" + str(tfi)

        # Wedges on Str_Left tenon ends (before mirror so slots replicate)
        # Find the 2 smallest planar faces = tenon ends
        sl_pfaces = []
        for fi in range(Str_Left.faces.count):
            f = Str_Left.faces.item(fi)
            if isinstance(f.geometry, adsk.core.Plane):
                sl_pfaces.append(f)
        sl_pfaces.sort(key=lambda f: f.area)
        # Identify FL vs BL end by face center proximity to leg positions
        fl_bb = fl_body.boundingBox
        fl_cx = (fl_bb.minPoint.x + fl_bb.maxPoint.x) / 2
        fl_cy = (fl_bb.minPoint.y + fl_bb.maxPoint.y) / 2
        sl_wedges = []
        for tfi, ef in enumerate(sl_pfaces[:2]):
            ok, fn = ef.evaluator.getNormalAtPoint(ef.pointOnFace)
            fc = ef.pointOnFace
            d_fl = _mstr.sqrt((fc.x - fl_cx)**2 + (fc.y - fl_cy)**2)
            # Closer to FL leg = FL end, else BL end
            if d_fl < 5:  # cm threshold
                mort_ref = fl_body
                wname = "TW_SL_FL"
            else:
                mort_ref = bl_body
                wname = "TW_SL_BL"
            sw = tw.round_tenon(comp, tenon_body=Str_Left,
                mortise_body=mort_ref, end_face=ef,
                tenon_depth_expr="leg_dia",
                tenon_diam_expr="str_end_dia",
                name=wname, ev=ev)
            sl_wedges.append(sw)
        print("Side stretcher wedges: " + str(len(sl_wedges)))

        StrMirX=mirror_bodies(comp,[Str_Left],XMid,"StrMirX")
        Str_Right=StrMirX.bodies.item(0); Str_Right.name="Str_Right"
        # Mirror side stretcher wedge bodies
        if sl_wedges:
            sl_w_mir = mirror_bodies(comp, sl_wedges, XMid, "StrWedgeMirX")
            for wi in range(sl_w_mir.bodies.count):
                wb = sl_w_mir.bodies.item(wi)
                wb.name = "TW_SR_" + str(wi)
        print("Side stretchers: revolved + tenon ext + wedged + mirrored")

    # ---- Cross stretcher: body-referenced via intersection in profile sketch ----
    # Create vertical plane at mid_y (cross stretcher runs left-right)
    cross_pl = off_plane(comp, comp.xZConstructionPlane, "mid_y", "StrCross_Pl")
    cross_sk = comp.sketches.add(cross_pl)
    cross_sk.name = "StrCross_Prof"

    # Intersect side stretcher bodies → 2 ellipse cross-sections
    # Need assembly proxies for cross-component intersection
    _str_occ = None
    for oi in range(root.occurrences.count):
        if root.occurrences.item(oi).component.name == "Stretchers":
            _str_occ = root.occurrences.item(oi); break
    if Str_Left and Str_Right:
        # Try direct bodies first (same component), fallback to proxies
        try:
            result_curves = cross_sk.intersectWithSketchPlane([Str_Left, Str_Right])
        except:
            if _str_occ:
                sl_p = Str_Left.createForAssemblyContext(_str_occ)
                sr_p = Str_Right.createForAssemblyContext(_str_occ)
                result_curves = cross_sk.intersectWithSketchPlane([sl_p, sr_p])
            else:
                result_curves = []
        print("Cross intersect: " + str(len(result_curves) if result_curves else 0) + " curves")
        # Force ALL intersection curves to construction
        for rc in (result_curves if result_curves else []):
            if hasattr(rc, 'isConstruction'):
                rc.isConstruction = True
    _sps2.refs_to_construction(cross_sk)

    # Find the 2 intersection ellipses (left and right side stretcher cross-sections)
    m2s_cx = cross_sk.modelToSketchSpace
    mid_x_val = ev("mid_x")

    # Identify left vs right ellipse by center X relative to mid_x
    left_info = None; right_info = None
    for ci in range(cross_sk.sketchCurves.count):
        c = cross_sk.sketchCurves.item(ci)
        if not (c.isConstruction or c.isReference): continue
        if hasattr(c, 'centerSketchPoint') and c.centerSketchPoint:
            cp = c.centerSketchPoint.geometry
            cp_model = cross_sk.sketchToModelSpace(P(cp.x, cp.y, 0))
            if cp_model.x < mid_x_val:
                if left_info is None or cp_model.x < left_info[1]:
                    left_info = (c.centerSketchPoint, cp_model.x, c)
            else:
                if right_info is None or cp_model.x > right_info[1]:
                    right_info = (c.centerSketchPoint, cp_model.x, c)

    if left_info and right_info:
        lc = left_info[0].geometry; rc = right_info[0].geometry
        cx_dx = rc.x - lc.x; cx_dy = rc.y - lc.y
        cx_dd = _mstr.sqrt(cx_dx*cx_dx + cx_dy*cx_dy)
        cx_ux, cx_uy = cx_dx/cx_dd, cx_dy/cx_dd

        # Sample actual outer extremes on side stretcher ellipses
        m2s_cx = cross_sk.modelToSketchSpace
        l_outer = _outer_extreme(left_info[2], -cx_ux, -cx_uy, m2s_cx)
        r_outer = _outer_extreme(right_info[2], cx_ux, cx_uy, m2s_cx)

        if l_outer and r_outer:
            cross_axis = cross_sk.sketchCurves.sketchLines.addByTwoPoints(
                P(l_outer.x, l_outer.y, 0), P(r_outer.x, r_outer.y, 0))
            print("Cross stretcher: sampled outer extremes")
        else:
            cross_axis = cross_sk.sketchCurves.sketchLines.addByTwoPoints(
                left_info[0], right_info[0])
            print("Cross stretcher: fallback to centers")
    else:
        # Fallback
        cl = m2s_cx(P(ev("fl_str_x"), ev("mid_y"), str_z))
        cr = m2s_cx(P(ev("seat_w") - ev("fl_str_x"), ev("mid_y"), str_z))
        cross_axis = cross_sk.sketchCurves.sketchLines.addByTwoPoints(
            P(cl.x, cl.y, 0), P(cr.x, cr.y, 0))
        print("Cross stretcher: fallback")

    # Draw turned profile around this axis
    cs_s = cross_axis.startSketchPoint.geometry
    cs_e = cross_axis.endSketchPoint.geometry
    cs_dx = cs_e.x - cs_s.x; cs_dy = cs_e.y - cs_s.y
    cs_len = _mstr.sqrt(cs_dx*cs_dx + cs_dy*cs_dy)
    cs_ux, cs_uy = cs_dx/cs_len, cs_dy/cs_len
    cs_nx, cs_ny = -cs_uy, cs_ux

    # Cross stretcher tenon covers side stretcher diameter
    cs_tenon_f = min(ev("str_mid_dia") / cs_len, 0.25)
    cs_shldr_f = cs_tenon_f + ev("str_shoulder_frac") * (0.5 - cs_tenon_f)
    cs_pts = [(0.0, end_r), (cs_tenon_f, end_r), (cs_shldr_f, mid_r),
              (0.5, mid_r), (1.0-cs_shldr_f, mid_r), (1.0-cs_tenon_f, end_r), (1.0, end_r)]
    cs_sk_pts = [P(cs_s.x+cs_ux*cs_len*f+cs_nx*r, cs_s.y+cs_uy*cs_len*f+cs_ny*r, 0)
                 for f, r in cs_pts]

    cs_lns = cross_sk.sketchCurves.sketchLines
    cL0=cs_lns.addByTwoPoints(cs_sk_pts[0],cs_sk_pts[1])
    cL1=cs_lns.addByTwoPoints(cL0.endSketchPoint,cs_sk_pts[2])
    cL2=cs_lns.addByTwoPoints(cL1.endSketchPoint,cs_sk_pts[3])
    cL3=cs_lns.addByTwoPoints(cL2.endSketchPoint,cs_sk_pts[4])
    cL4=cs_lns.addByTwoPoints(cL3.endSketchPoint,cs_sk_pts[5])
    cL5=cs_lns.addByTwoPoints(cL4.endSketchPoint,cs_sk_pts[6])
    cL_r=cs_lns.addByTwoPoints(cL5.endSketchPoint,P(cs_e.x,cs_e.y,0))
    cL_bot=cs_lns.addByTwoPoints(cL_r.endSketchPoint,P(cs_s.x,cs_s.y,0))
    cL_l=cs_lns.addByTwoPoints(cL_bot.endSketchPoint,cL0.startSketchPoint)

    cs_gc = cross_sk.geometricConstraints
    cs_gc.addParallel(cL0,cL_bot); cs_gc.addParallel(cL5,cL_bot)
    cs_gc.addParallel(cL2,cL_bot); cs_gc.addParallel(cL3,cL_bot)
    cs_gc.addEqual(cL5,cL0); cs_gc.addEqual(cL3,cL2)
    # Constrain revolve axis endpoints to cross_axis endpoints (parametric link)
    cs_gc.addCoincident(cL_r.endSketchPoint, cross_axis.endSketchPoint)
    cs_gc.addCoincident(cL_bot.endSketchPoint, cross_axis.startSketchPoint)

    # Radius dimensions only (tenon/shoulder proportions maintained by constraints)
    cs_dims = cross_sk.sketchDimensions
    cs_dims.addDistanceDimension(cL_l.startSketchPoint,cL_l.endSketchPoint,AL,
        P(cL_l.startSketchPoint.geometry.x+cs_nx*2,cL_l.startSketchPoint.geometry.y+cs_ny*2,0)
    ).parameter.expression="str_end_dia / 2"
    cs_mid=cs_lns.addByTwoPoints(P((cs_s.x+cs_e.x)/2,(cs_s.y+cs_e.y)/2,0),cL2.endSketchPoint)
    cs_mid.isConstruction=True
    cs_gc.addPerpendicular(cs_mid,cL_bot); cs_gc.addCoincident(cs_mid.startSketchPoint,cL_bot)
    cs_dims.addDistanceDimension(cs_mid.startSketchPoint,cs_mid.endSketchPoint,AL,
        P(cs_mid.startSketchPoint.geometry.x+cs_nx*2,cs_mid.startSketchPoint.geometry.y+cs_ny*2,0)
    ).parameter.expression="str_mid_dia / 2"

    cs_prof = _sps2.smallest_profile(cross_sk) if cross_sk.profiles.count > 0 else None
    print("Cross profiles: " + str(cross_sk.profiles.count))
    Str_Cross = None
    if cs_prof:
        cs_rev = comp.features.revolveFeatures.createInput(cs_prof, cL_bot, NEWBODY)
        cs_rev.setAngleExtent(False, adsk.core.ValueInput.createByString("360 deg"))
        cs_rf = comp.features.revolveFeatures.add(cs_rev)
        cs_rf.name = "Str_Cross"
        Str_Cross = cs_rf.bodies.item(0); Str_Cross.name = "Str_Cross"

        # Tenon extensions on both ends of cross stretcher
        cs_faces = []
        for fi in range(Str_Cross.faces.count):
            f = Str_Cross.faces.item(fi)
            if isinstance(f.geometry, adsk.core.Plane):
                cs_faces.append(f)
        cs_faces.sort(key=lambda f: f.area)
        for tfi, tf in enumerate(cs_faces[:2]):
            if tf.loops.count > 0:
                te_inp3 = comp.features.extrudeFeatures.createInput(tf, JOIN)
                te_inp3.setDistanceExtent(False, adsk.core.ValueInput.createByString("tenon_ext"))
                te_inp3.participantBodies = [Str_Cross]
                te_f3 = comp.features.extrudeFeatures.add(te_inp3)
                te_f3.name = "StrC_TenExt" + str(tfi)

    # Wedges on cross stretcher tenon ends (into side stretchers)
    cs_wedges = []
    if Str_Cross:
        cs_pfaces = []
        for fi in range(Str_Cross.faces.count):
            f = Str_Cross.faces.item(fi)
            if isinstance(f.geometry, adsk.core.Plane):
                cs_pfaces.append(f)
        cs_pfaces.sort(key=lambda f: f.area)
        for csi, ef in enumerate(cs_pfaces[:2]):
            fc = ef.pointOnFace
            # Identify left vs right end by X position relative to mid_x
            if fc.x < ev("mid_x"):
                mort_ref = Str_Left
                wname = "TW_SC_L"
            else:
                mort_ref = Str_Right
                wname = "TW_SC_R"
            cw = tw.round_tenon(comp, tenon_body=Str_Cross,
                mortise_body=mort_ref, end_face=ef,
                tenon_depth_expr="str_mid_dia",
                tenon_diam_expr="str_end_dia",
                name=wname, ev=ev)
            cs_wedges.append(cw)
        print("Cross stretcher wedges: " + str(len(cs_wedges)))

    print("Stretchers: 3 (all revolved + tenon ext + wedged)")

    # ==== BACK: Spindles on curved arc + Curved crest rail ====
    # Spindles arranged along an arc for comfort.
    # Each spindle: turned cylinder from seat to crest, tilted by back_rake.
    # Crest rail: sweep of cross-section along top arc.
    import math as _mb

    comp = root
    Back_occ = comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    Back_occ.component.name = "Back"
    Back_c = Back_occ.component
    comp = Back_c

    n_sp = int(ev("n_spindles"))
    sp_dia = ev("spindle_dia")
    sp_len = ev("spindle_len")
    sp_start_x = ev("spindle_start_x")
    sp_y = ev("spindle_y")
    back_cr = ev("back_curve_r")
    crest_cr = ev("crest_curve_r")
    br_rad = _mb.radians(ev("back_rake"))
    br_sin = _mb.sin(br_rad)
    br_cos = _mb.cos(br_rad)
    seat_top = ev("seat_h")
    mid_x_v = ev("mid_x")

    # Bottom arc: center at (mid_x, spindle_y + back_curve_r), radius = back_curve_r
    # Spindles sit on this arc at Z = seat_h (seat surface)
    # Arc wraps around sitter's back — center is in front, arc bows backward
    bot_arc_cy = sp_y - back_cr  # arc center Y (in front of spindles)

    # Compute spindle base positions along the bottom arc
    # X positions: evenly distributed from -spindle_start_x to +spindle_start_x relative to mid_x
    spindle_bases = []
    for i in range(n_sp):
        if n_sp > 1:
            frac = i / (n_sp - 1)  # 0 to 1
        else:
            frac = 0.5
        x_offset = -sp_start_x + 2 * sp_start_x * frac  # from -start_x to +start_x
        x = mid_x_v + x_offset
        # Y on arc: y = arc_center_y - sqrt(R^2 - x_offset^2)
        y = bot_arc_cy + _mb.sqrt(max(back_cr*back_cr - x_offset*x_offset, 0.01))
        spindle_bases.append((x, y, seat_top))

    # Top arc: crest rail arc, center at (mid_x, crest_center_y), radius = crest_curve_r
    # Crest position using sin/cos params directly
    crest_z = seat_top + sp_len * br_cos
    crest_base_y = sp_y + sp_len * br_sin
    crest_arc_cy = crest_base_y - crest_cr  # center in front, arc bows backward

    spindle_tops = []
    # Top positions: evenly spaced along top arc using same X range scaled by crest_w
    crest_w_v = ev("crest_w")
    crest_half = crest_w_v / 2
    for i in range(n_sp):
        if n_sp > 1:
            frac = i / (n_sp - 1)
        else:
            frac = 0.5
        x_offset = -crest_half + crest_w_v * frac
        x = mid_x_v + x_offset
        y = crest_arc_cy + _mb.sqrt(max(crest_cr*crest_cr - x_offset*x_offset, 0.01))
        spindle_tops.append((x, y, crest_z))

    # Build each spindle using the turned_spindle revolve template
    # (reuse the turned_spindle function from stretchers section — it's still in scope)
    # But spindles don't have a bulge, they're constant diameter with tenons at both ends.
    # Use the same function with end_r = tenon size, mid_r = spindle_dia/2

    # Create spindle length parameter
    for i in range(n_sp):
        base = spindle_bases[i]
        top = spindle_tops[i]
        sp_name = "Spin_" + str(i)

        # Axis from base to top
        ax_sk = comp.sketches.add(comp.xYConstructionPlane)
        ax_sk.name = sp_name + "_Ax"
        m2s_ax = ax_sk.modelToSketchSpace
        s_b = m2s_ax(P(base[0], base[1], base[2]))
        s_t = m2s_ax(P(top[0], top[1], top[2]))
        ax_line = ax_sk.sketchCurves.sketchLines.addByTwoPoints(
            P(s_b.x, s_b.y, 0), P(s_t.x, s_t.y, 0))
        ax_line.isConstruction = True

        # Profile plane: 90° from XY around axis
        pp_inp = comp.constructionPlanes.createInput()
        pp_inp.setByAngle(ax_line, adsk.core.ValueInput.createByString("90 deg"),
                          comp.xYConstructionPlane)
        pp = comp.constructionPlanes.add(pp_inp)
        pp.name = sp_name + "_Pl"

        # Profile sketch: simple rectangle (constant radius spindle)
        p_sk = comp.sketches.add(pp)
        p_sk.name = sp_name + "_Prof"
        m2s_p = p_sk.modelToSketchSpace
        ps_b = m2s_p(P(base[0], base[1], base[2]))
        ps_t = m2s_p(P(top[0], top[1], top[2]))

        adx = ps_t.x - ps_b.x
        ady = ps_t.y - ps_b.y
        alen = _mb.sqrt(adx*adx + ady*ady)
        aux_s, auy_s = adx/alen, ady/alen
        anx_s, any_s = -auy_s, aux_s

        r = sp_dia / 2
        tl = P(ps_b.x + anx_s * r, ps_b.y + any_s * r, 0)
        tr = P(ps_t.x + anx_s * r, ps_t.y + any_s * r, 0)

        lns_s = p_sk.sketchCurves.sketchLines
        L_top = lns_s.addByTwoPoints(tl, tr)
        L_r = lns_s.addByTwoPoints(L_top.endSketchPoint, P(ps_t.x, ps_t.y, 0))
        L_bot = lns_s.addByTwoPoints(L_r.endSketchPoint, P(ps_b.x, ps_b.y, 0))
        L_l = lns_s.addByTwoPoints(L_bot.endSketchPoint, L_top.startSketchPoint)

        p_sk.geometricConstraints.addParallel(L_top, L_bot)

        # Dimension: radius
        ALIGNED = adsk.fusion.DimensionOrientations.AlignedDimensionOrientation
        lp = L_l.startSketchPoint.geometry
        p_sk.sketchDimensions.addDistanceDimension(
            L_l.startSketchPoint, L_l.endSketchPoint, ALIGNED,
            P(lp.x + anx_s * 2, lp.y + any_s * 2, 0)
        ).parameter.expression = "spindle_dia / 2"

        prof = p_sk.profiles.item(0) if p_sk.profiles.count > 0 else None
        if not prof:
            print(sp_name + ": no profile, skipping")
            continue

        rev_inp = comp.features.revolveFeatures.createInput(prof, L_bot, NEWBODY)
        rev_inp.setAngleExtent(False, adsk.core.ValueInput.createByString("360 deg"))
        rev_feat = comp.features.revolveFeatures.add(rev_inp)
        rev_feat.name = sp_name
        body = rev_feat.bodies.item(0)
        body.name = sp_name

    print("Spindles: " + str(n_sp) + " built on curved arc")

    # ==== CREST RAIL: sweep cross-section along top arc ====
    # Draw the top arc in a sketch at crest Z height
    crest_z_pl = off_plane(comp, comp.xYConstructionPlane, str(crest_z) + " cm", "CrestZ_Pl")
    crest_sk = comp.sketches.add(crest_z_pl)
    crest_sk.name = "CrestArc_Sk"
    m2s_cr = crest_sk.modelToSketchSpace

    # Arc extends past outermost spindles by crest_t (thickness) on each side
    left_top = spindle_tops[0]
    right_top = spindle_tops[-1]
    ext = ev("crest_t")  # extension beyond outermost spindles
    # Extend X range: left goes further left, right goes further right
    left_x_off = -(crest_half + ext)
    right_x_off = crest_half + ext
    left_ext_y = crest_arc_cy + _mb.sqrt(max(crest_cr*crest_cr - left_x_off*left_x_off, 0.01))
    right_ext_y = crest_arc_cy + _mb.sqrt(max(crest_cr*crest_cr - right_x_off*right_x_off, 0.01))
    mid_top_x = mid_x_v
    mid_top_y = crest_arc_cy + _mb.sqrt(max(crest_cr*crest_cr - 0, 0.01))

    cl = m2s_cr(P(mid_x_v + left_x_off, left_ext_y, crest_z))
    cr = m2s_cr(P(mid_x_v + right_x_off, right_ext_y, crest_z))
    cm = m2s_cr(P(mid_top_x, mid_top_y, crest_z))

    crest_arc = crest_sk.sketchCurves.sketchArcs.addByThreePoints(
        P(cl.x, cl.y, 0), P(cm.x, cm.y, 0), P(cr.x, cr.y, 0))

    # Crest cross-section: on a plane perpendicular to the arc at its midpoint
    crest_path = comp.features.createPath(crest_arc, False)
    crest_perp_inp = comp.constructionPlanes.createInput()
    crest_perp_inp.setByDistanceOnPath(crest_path, adsk.core.ValueInput.createByString("0.5"))
    crest_perp = comp.constructionPlanes.add(crest_perp_inp)
    crest_perp.name = "CrestProf_Pl"

    # Cross-section: rounded rectangle (ellipse for simplicity)
    crest_prof_sk = comp.sketches.add(crest_perp)
    crest_prof_sk.name = "CrestProf_Sk"
    crest_t_v = ev("crest_t")
    crest_h_v = ev("crest_h")
    # Ellipse at origin of perpendicular plane (center of arc at midpoint)
    crest_prof_sk.sketchCurves.sketchEllipses.add(
        P(0, 0, 0),
        P(0, crest_h_v / 2, 0),  # major axis point (vertical)
        P(crest_t_v / 2, 0, 0))  # point on ellipse (horizontal)

    crest_dims = crest_prof_sk.sketchDimensions
    crest_ellipse = crest_prof_sk.sketchCurves.item(0)
    crest_dims.addEllipseMajorRadiusDimension(
        crest_ellipse, P(0, crest_h_v / 2 + 1, 0)
    ).parameter.expression = "crest_h / 2"
    crest_dims.addEllipseMinorRadiusDimension(
        crest_ellipse, P(crest_t_v / 2 + 1, 0, 0)
    ).parameter.expression = "crest_t / 2"

    crest_prof = crest_prof_sk.profiles.item(0) if crest_prof_sk.profiles.count > 0 else None

    if crest_prof:
        # Sweep cross-section along the arc
        sweep_inp = comp.features.sweepFeatures.createInput(crest_prof, crest_path, NEWBODY)
        sweep_inp.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
        crest_sweep = comp.features.sweepFeatures.add(sweep_inp)
        crest_sweep.name = "CrestRail"
        crest_body = crest_sweep.bodies.item(0)
        crest_body.name = "CrestRail"
        print("Crest rail: swept along arc")
    else:
        print("Crest rail: no profile, skipped")

    # ==== SEAT SCOOP (one sweep + mirror) ====
    # Path: straight line at seat surface from front toward back, with arc
    #       transition curving up at the back end (smooth exit from surface)
    # Profile: circle offset to one side, sweep + mirror for both scoops
    comp = Seat_c
    seat_top_z = ev("seat_h")

    # Profile: circle with face-relative dimensions
    # Project seat top face into sketch for reference, then dimension from it.
    # Center Z = scoop_r - scoop_depth above seat top (face-relative)
    # Center X = scoop_dist / 2 from seat centerline
    from helpers import sp as _sp
    Scoop_Pl_Seat = off_plane(comp, comp.xZConstructionPlane, "scoop_back_y", "Scoop_Pl")
    scoop_sk = comp.sketches.add(Scoop_Pl_Seat)
    scoop_sk.name = "Scoop_Sk"
    m2s_sc = scoop_sk.modelToSketchSpace

    # Project seat top face and XMid plane as references
    seat_top_face = _sp.find_face(Seat_Seat, "z", +1)
    seat_top_ref = scoop_sk.project(seat_top_face)  # horizontal ref at seat_h
    xmid_ref = scoop_sk.project(XMid)  # vertical ref at mid_x

    # Find the projected reference points for dimensioning
    # seat_top_ref gives edges at Z=seat_h; xmid_ref gives edge at X=mid_x
    # Get sketch points from these projections
    seat_ref_pt = None
    xmid_ref_pt = None
    for ci in range(scoop_sk.sketchCurves.count):
        c = scoop_sk.sketchCurves.item(ci)
        if c.isReference or c.isConstruction:
            # Check if horizontal (seat top) or vertical (xmid)
            sp_s = c.startSketchPoint.geometry
            sp_e = c.endSketchPoint.geometry
            if hasattr(c, 'startSketchPoint'):
                if abs(sp_s.y - sp_e.y) < 0.01 and seat_ref_pt is None:
                    # Horizontal → seat top reference (in sketch Y maps to Z)
                    # Actually need to check based on sketch axes
                    seat_ref_pt = c.startSketchPoint
                elif abs(sp_s.x - sp_e.x) < 0.01 and xmid_ref_pt is None:
                    xmid_ref_pt = c.startSketchPoint

    # Approximate placement, then parametric dimensions override
    cx_model = ev("mid_x") - ev("scoop_dist") / 2
    cz_model = seat_top_z + ev("scoop_r") - ev("scoop_depth")
    sc_ctr = m2s_sc(P(cx_model, ev("scoop_back_y"), cz_model))
    circ = scoop_sk.sketchCurves.sketchCircles.addByCenterRadius(
        P(sc_ctr.x, sc_ctr.y, 0), ev("scoop_r"))

    # Convert references to construction so they don't split the profile
    _sp.refs_to_construction(scoop_sk)

    # Parametric dimensions relative to seat face references
    orient_sc = _sp.probe_orientations(scoop_sk, cx_model, ev("scoop_back_y"), cz_model)
    sc_dims = scoop_sk.sketchDimensions

    sc_dims.addRadialDimension(
        circ, P(sc_ctr.x + 2, sc_ctr.y, 0)
    ).parameter.expression = "scoop_r"

    # X distance from XMid reference → scoop_dist / 2
    if xmid_ref_pt:
        sc_dims.addDistanceDimension(
            xmid_ref_pt, circ.centerSketchPoint, orient_sc["x"],
            P(sc_ctr.x, sc_ctr.y + 2, 0)
        ).parameter.expression = "scoop_dist / 2"

    # Z distance from seat top reference → scoop_r - scoop_depth
    if seat_ref_pt:
        sc_dims.addDistanceDimension(
            seat_ref_pt, circ.centerSketchPoint, orient_sc["z"],
            P(sc_ctr.x - 2, sc_ctr.y, 0)
        ).parameter.expression = "scoop_r - scoop_depth"

    scoop_prof = _sp.smallest_profile(scoop_sk)
    path_z = cz_model  # path at circle center Z

    # Path: straight line + arc transition at back
    # Line at Z = path_z from back_y toward front
    # Arc at back end curves upward (smooth entry)
    path_sk = comp.sketches.add(XMid)
    path_sk.name = "ScoopPath_Sk"
    m2s_pa = path_sk.modelToSketchSpace
    import math as _m

    back_y_v  = ev("scoop_back_y")
    front_y_v = ev("scoop_front_y")
    R_v       = ev("scoop_trans_r")
    d_v       = ev("scoop_depth")
    seat_d_v  = ev("seat_d")

    ps_back = m2s_pa(P(0, back_y_v, path_z))
    ps_front = m2s_pa(P(0, -seat_d_v * 0.1, path_z))

    main_line = path_sk.sketchCurves.sketchLines.addByTwoPoints(
        P(ps_back.x, ps_back.y, 0),
        P(ps_front.x, ps_front.y, 0))

    # Arc: quarter circle from line back end, curving upward and backward
    arc_end_y = back_y_v + R_v
    arc_end_z = path_z + R_v
    arc_mid_y = back_y_v + R_v * _m.sin(_m.pi/4)
    arc_mid_z = path_z + R_v * (1 - _m.cos(_m.pi/4))
    ps_arc_mid = m2s_pa(P(0, arc_mid_y, arc_mid_z))
    ps_arc_end = m2s_pa(P(0, arc_end_y, arc_end_z))
    arc = path_sk.sketchCurves.sketchArcs.addByThreePoints(
        main_line.startSketchPoint,
        P(ps_arc_mid.x, ps_arc_mid.y, 0),
        P(ps_arc_end.x, ps_arc_end.y, 0))

    from helpers import sp as _sp
    path_dims = path_sk.sketchDimensions
    path_dims.addRadialDimension(
        arc, P(ps_arc_mid.x + 0.5, ps_arc_mid.y + 0.5, 0)
    ).parameter.expression = "scoop_trans_r"
    orient_pa = _sp.probe_orientations(path_sk, 0, ev("mid_y"), seat_top_z)
    origin_pa = path_sk.originPoint
    path_dims.addDistanceDimension(
        origin_pa, main_line.startSketchPoint, orient_pa['z'],
        P(ps_back.x - 2, ps_back.y, 0)
    ).parameter.expression = "seat_h + scoop_r - scoop_depth"
    path_dims.addDistanceDimension(
        origin_pa, main_line.startSketchPoint, orient_pa['y'],
        P(ps_back.x, ps_back.y + 2, 0)
    ).parameter.expression = "scoop_back_y"

    # Create chained path (arc + line)
    sweep_path = comp.features.createPath(main_line, True)  # chain picks up arc

    # Sweep CUT — one direction, left scoop only
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    sweep_inp = comp.features.sweepFeatures.createInput(scoop_prof, sweep_path, CUT)
    sweep_inp.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
    sweep_inp.participantBodies = [Seat_Seat]
    sweep_feat = comp.features.sweepFeatures.add(sweep_inp)
    sweep_feat.name = "Scoop_L"
    Seat_Seat = sweep_feat.bodies.item(0)
    Seat_Seat.name = "Seat"
    print("Left scoop sweep done")

    # Mirror across XMid for right scoop
    mir_coll = adsk.core.ObjectCollection.create()
    mir_coll.add(sweep_feat)
    mir_inp = comp.features.mirrorFeatures.createInput(mir_coll, XMid)
    mir_inp.computeOption = adsk.fusion.PatternComputeOptions.AdjustPatternCompute
    mir_feat = comp.features.mirrorFeatures.add(mir_inp)
    mir_feat.name = "Scoop_R_Mir"
    Seat_Seat = mir_feat.bodies.item(0)
    Seat_Seat.name = "Seat"
    print("Both scoops done")

    # ── SEAT FILLET ───────────────────────────────────────────────
    # Two fillet passes: top edges (small radius), bottom/corner edges (large radius)
    seat_top_z_val = ev("seat_h")
    seat_bot_z_val = ev("seat_h") - ev("seat_t")

    # Top edges: edges where both vertices are near seat_h (top face perimeter + scoop edges)
    if ev("seat_fil_top") > 0:
        top_edges = adsk.core.ObjectCollection.create()
        seen_top = set()
        for ei in range(Seat_Seat.edges.count):
            e = Seat_Seat.edges.item(ei)
            tid = e.tempId
            if tid in seen_top: continue
            sv = e.startVertex; ev_ = e.endVertex
            if sv and ev_:
                if sv.geometry.z > (seat_bot_z_val + seat_top_z_val) / 2 and \
                   ev_.geometry.z > (seat_bot_z_val + seat_top_z_val) / 2:
                    seen_top.add(tid)
                    top_edges.add(e)
        if top_edges.count > 0:
            fil_top = Seat_c.features.filletFeatures.createInput()
            fil_top.addConstantRadiusEdgeSet(
                top_edges, adsk.core.ValueInput.createByString("seat_fil_top"), True)
            fil_tf = Seat_c.features.filletFeatures.add(fil_top)
            fil_tf.name = "Seat_Fil_Top"
            # Re-find seat body after fillet
            Seat_Seat = fil_tf.bodies.item(0)
            Seat_Seat.name = "Seat"
            print("Seat fillet top: " + str(top_edges.count) + " edges")

    # Bottom/corner edges: remaining edges (near seat_bot or vertical side edges)
    if ev("seat_fil_bot") > 0:
        bot_edges = adsk.core.ObjectCollection.create()
        seen_bot = set()
        for ei in range(Seat_Seat.edges.count):
            e = Seat_Seat.edges.item(ei)
            tid = e.tempId
            if tid in seen_bot: continue
            sv = e.startVertex; ev_ = e.endVertex
            if sv and ev_:
                # Bottom edges: at least one vertex near seat_bot, or vertical edges
                near_bot = sv.geometry.z < (seat_bot_z_val + seat_top_z_val) / 2 or \
                           ev_.geometry.z < (seat_bot_z_val + seat_top_z_val) / 2
                if near_bot:
                    seen_bot.add(tid)
                    bot_edges.add(e)
        if bot_edges.count > 0:
            fil_bot = Seat_c.features.filletFeatures.createInput()
            fil_bot.addConstantRadiusEdgeSet(
                bot_edges, adsk.core.ValueInput.createByString("seat_fil_bot"), True)
            fil_bf = Seat_c.features.filletFeatures.add(fil_bot)
            fil_bf.name = "Seat_Fil_Bot"
            print("Seat fillet bottom: " + str(bot_edges.count) + " edges")

    # ── HIDE CONSTRUCTION ─────────────────────────────────────────
    for _comp in [root, Seat_c, comp]:  # comp = Legs_c at this point
        for si in range(_comp.sketches.count):
            _comp.sketches.item(si).isVisible = False
        for ci in range(_comp.constructionPlanes.count):
            _comp.constructionPlanes.item(ci).isLightBulbOn = False
    for _occ in root.allOccurrences:
        _oc = _occ.component
        for si in range(_oc.sketches.count):
            _oc.sketches.item(si).isVisible = False
        for ci in range(_oc.constructionPlanes.count):
            _oc.constructionPlanes.item(ci).isLightBulbOn = False

    # ── APPEARANCE ────────────────────────────────────────────────
    from helpers import sp as _sp_app
    # Collect all body names, split wedge (TW_ prefix) vs non-wedge
    def _all_body_names(comp):
        names = []
        for i in range(comp.bRepBodies.count):
            names.append(comp.bRepBodies.item(i).name)
        for i in range(comp.occurrences.count):
            names.extend(_all_body_names(comp.occurrences.item(i).component))
        return names
    _all_names = _all_body_names(root)
    _non_wedge = [n for n in _all_names if not n.startswith("TW_")]
    _wedge_actual = [n for n in _all_names if n.startswith("TW_")]
    _sp_app.apply_appearance("white oak", bodies=_non_wedge)
    if _wedge_actual:
        _sp_app.apply_appearance("rosewood", bodies=_wedge_actual)

    # ── FIT VIEW ──────────────────────────────────────────────────
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam