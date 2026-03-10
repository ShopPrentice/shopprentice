"""
Shared capture helpers for design introspection.

Used by capture_design.py, get_selection.py, and get_changes.py.
Extracts structured info from Fusion 360 entities (sketches, extrudes,
combines, mirrors, patterns, moves, chamfers, fillets, sweeps,
split-body, remove, etc.).
"""

import adsk.core
import adsk.fusion
from contextlib import contextmanager


# ── Timeline rollTo helper ──

@contextmanager
def _roll_to_feature(entity, design):
    """Roll timeline to a feature for BRep-dependent property access, then restore."""
    tl = design.timeline
    try:
        entity.timelineObject.rollTo(True)
        yield
    finally:
        tl.moveToEnd()


# ── Body geometry ──

def _capture_body(body):
    """Capture a single body's geometry: name, volume, bounding box."""
    info = {"name": body.name}
    try:
        info["volume"] = round(body.volume, 4)
    except:
        pass
    try:
        bb = body.boundingBox
        info["boundingBox"] = {
            "min": [round(bb.minPoint.x, 4), round(bb.minPoint.y, 4), round(bb.minPoint.z, 4)],
            "max": [round(bb.maxPoint.x, 4), round(bb.maxPoint.y, 4), round(bb.maxPoint.z, 4)],
        }
    except:
        pass
    return info


# ── Sketch plane ──

def _capture_sketch_plane(sk, design=None):
    """Return structured plane info for a sketch's reference plane.

    Uses rollTo when available to access BRep-dependent reference planes
    that may not be accessible at end-of-timeline.
    """
    ref = None
    try:
        ref = sk.referencePlane
    except:
        pass
    if ref is None and design:
        try:
            with _roll_to_feature(sk, design):
                ref = sk.referencePlane
        except:
            pass
    if ref is None:
        return None
    try:
        cp = adsk.fusion.ConstructionPlane.cast(ref)
        if cp:
            result = {"type": "ConstructionPlane", "name": cp.name}
            try:
                geom = cp.geometry
                result["normal"] = [round(geom.normal.x, 6), round(geom.normal.y, 6), round(geom.normal.z, 6)]
                result["origin"] = [round(geom.origin.x, 4), round(geom.origin.y, 4), round(geom.origin.z, 4)]
            except:
                pass
            return result
        bf = adsk.fusion.BRepFace.cast(ref)
        if bf:
            result = {"type": "BRepFace", "body": bf.body.name}
            got_geo = False
            try:
                geom = bf.geometry
                plane = adsk.core.Plane.cast(geom)
                if plane:
                    result["normal"] = [round(plane.normal.x, 4), round(plane.normal.y, 4), round(plane.normal.z, 4)]
                    result["origin"] = [round(plane.origin.x, 4), round(plane.origin.y, 4), round(plane.origin.z, 4)]
                    got_geo = True
            except:
                pass
            if not got_geo:
                try:
                    eva = bf.evaluator
                    ok, pt, norm = eva.getNormalAtPoint(bf.pointOnFace)
                    if ok:
                        result["normal"] = [round(norm.x, 4), round(norm.y, 4), round(norm.z, 4)]
                        result["origin"] = [round(bf.pointOnFace.x, 4), round(bf.pointOnFace.y, 4), round(bf.pointOnFace.z, 4)]
                except:
                    pass
            # Actual point on the face (may differ from plane.origin for beveled extrudes)
            try:
                pof = bf.pointOnFace
                result["pointOnFace"] = [round(pof.x, 4), round(pof.y, 4), round(pof.z, 4)]
            except:
                pass
            return result
    except:
        pass
    return None


# ── Sketch entity identification ──

def _identify_sketch_entity(entity, sk):
    """Match a sketch entity (point, line, arc, etc.) to a stable reference.

    Returns a dict like:
      {"type": "SketchLine", "curveIndex": 4}
      {"type": "SketchPoint", "curveIndex": 4, "role": "start"}
      {"type": "SketchPoint", "role": "origin"}
    """
    if entity is None:
        return None

    # SketchPoint — match by position against curve endpoints + origin
    sp = adsk.fusion.SketchPoint.cast(entity)
    if sp:
        px = round(sp.geometry.x, 3)
        py = round(sp.geometry.y, 3)

        # Check sketch origin
        try:
            ox = round(sk.originPoint.geometry.x, 3)
            oy = round(sk.originPoint.geometry.y, 3)
            if abs(px - ox) < 0.01 and abs(py - oy) < 0.01:
                return {"type": "SketchPoint", "role": "origin"}
        except:
            pass

        # Check curve endpoints
        for ci in range(sk.sketchCurves.count):
            c = sk.sketchCurves.item(ci)
            line = adsk.fusion.SketchLine.cast(c)
            if line:
                sx = round(line.startSketchPoint.geometry.x, 3)
                sy = round(line.startSketchPoint.geometry.y, 3)
                if abs(px - sx) < 0.01 and abs(py - sy) < 0.01:
                    return {"type": "SketchPoint", "curveIndex": ci, "role": "start"}
                ex = round(line.endSketchPoint.geometry.x, 3)
                ey = round(line.endSketchPoint.geometry.y, 3)
                if abs(px - ex) < 0.01 and abs(py - ey) < 0.01:
                    return {"type": "SketchPoint", "curveIndex": ci, "role": "end"}
            arc = adsk.fusion.SketchArc.cast(c)
            if arc:
                sx = round(arc.startSketchPoint.geometry.x, 3)
                sy = round(arc.startSketchPoint.geometry.y, 3)
                if abs(px - sx) < 0.01 and abs(py - sy) < 0.01:
                    return {"type": "SketchPoint", "curveIndex": ci, "role": "start"}
                ex = round(arc.endSketchPoint.geometry.x, 3)
                ey = round(arc.endSketchPoint.geometry.y, 3)
                if abs(px - ex) < 0.01 and abs(py - ey) < 0.01:
                    return {"type": "SketchPoint", "curveIndex": ci, "role": "end"}
                cx = round(arc.centerSketchPoint.geometry.x, 3)
                cy = round(arc.centerSketchPoint.geometry.y, 3)
                if abs(px - cx) < 0.01 and abs(py - cy) < 0.01:
                    return {"type": "SketchPoint", "curveIndex": ci, "role": "center"}

        # Check spline fit points
        for ci in range(sk.sketchCurves.count):
            c = sk.sketchCurves.item(ci)
            spline = adsk.fusion.SketchFittedSpline.cast(c)
            if spline:
                for fi in range(spline.fitPoints.count):
                    fp = spline.fitPoints.item(fi)
                    fx = round(fp.geometry.x, 3)
                    fy = round(fp.geometry.y, 3)
                    if abs(px - fx) < 0.01 and abs(py - fy) < 0.01:
                        return {"type": "SketchPoint", "curveIndex": ci,
                                "role": "fitPoint", "fitIndex": fi}

        return {"type": "SketchPoint", "position": [px, py]}

    # SketchLine — match by index
    line = adsk.fusion.SketchLine.cast(entity)
    if line:
        for ci in range(sk.sketchCurves.count):
            if sk.sketchCurves.item(ci) == line:
                return {"type": "SketchLine", "curveIndex": ci}
        return {"type": "SketchLine"}

    # SketchArc — match by index
    arc = adsk.fusion.SketchArc.cast(entity)
    if arc:
        for ci in range(sk.sketchCurves.count):
            if sk.sketchCurves.item(ci) == arc:
                return {"type": "SketchArc", "curveIndex": ci}
        return {"type": "SketchArc"}

    # SketchCircle — match by index
    circle = adsk.fusion.SketchCircle.cast(entity)
    if circle:
        for ci in range(sk.sketchCurves.count):
            if sk.sketchCurves.item(ci) == circle:
                return {"type": "SketchCircle", "curveIndex": ci}
        return {"type": "SketchCircle"}

    # SketchFittedSpline — match by index
    spline = adsk.fusion.SketchFittedSpline.cast(entity)
    if spline:
        for ci in range(sk.sketchCurves.count):
            if sk.sketchCurves.item(ci) == spline:
                return {"type": "SketchFittedSpline", "curveIndex": ci}
        return {"type": "SketchFittedSpline"}

    # BRepEdge (projected edges)
    edge = adsk.fusion.BRepEdge.cast(entity)
    if edge:
        result = {"type": "BRepEdge"}
        try:
            result["body"] = edge.body.name
        except:
            pass
        return result

    return {"type": type(entity).__name__}


# ── Sketch (full detail) ──

def _capture_sketch(sk, design=None):
    """Capture a Sketch feature with curves, dimensions, constraints, profiles."""
    info = {"type": "Sketch", "name": sk.name}

    # Structured sketch plane
    plane = _capture_sketch_plane(sk, design)

    # Sketch coordinate system — always capture for coordinate transforms
    try:
        info["sketchOrigin"] = [round(sk.origin.x, 4), round(sk.origin.y, 4), round(sk.origin.z, 4)]
        info["sketchXDir"] = [round(sk.xDirection.x, 6), round(sk.xDirection.y, 6), round(sk.xDirection.z, 6)]
        info["sketchYDir"] = [round(sk.yDirection.x, 6), round(sk.yDirection.y, 6), round(sk.yDirection.z, 6)]
    except:
        pass

    # If referencePlane returned None, infer plane from sketch axes.
    # normal = cross(xDir, yDir), origin = sketchOrigin.
    if plane is None and "sketchOrigin" in info and "sketchXDir" in info and "sketchYDir" in info:
        xd = info["sketchXDir"]
        yd = info["sketchYDir"]
        normal = [
            round(xd[1]*yd[2] - xd[2]*yd[1], 6),
            round(xd[2]*yd[0] - xd[0]*yd[2], 6),
            round(xd[0]*yd[1] - xd[1]*yd[0], 6),
        ]
        plane = {
            "type": "InferredPlane",
            "normal": normal,
            "origin": info["sketchOrigin"],
        }

    if plane:
        info["plane"] = plane

    # Check if any curves are projected references — if so, need rollTo
    # for accurate edge vertex positions (downstream features may alter topology)
    _has_refs = False
    for _ci in range(sk.sketchCurves.count):
        _c = sk.sketchCurves.item(_ci)
        try:
            if _c.isReference:
                _has_refs = True
                break
        except:
            pass

    _rolled = False
    if _has_refs and design:
        try:
            sk.timelineObject.rollTo(True)
            _rolled = True
        except:
            pass

    # Curves (with projection detection)
    curves_info = []
    for ci in range(sk.sketchCurves.count):
        c = sk.sketchCurves.item(ci)
        line = adsk.fusion.SketchLine.cast(c)
        if line:
            curve_info = {
                "type": "Line",
                "start": [round(line.startSketchPoint.geometry.x, 4),
                          round(line.startSketchPoint.geometry.y, 4)],
                "end": [round(line.endSketchPoint.geometry.x, 4),
                        round(line.endSketchPoint.geometry.y, 4)],
                "isConstruction": line.isConstruction,
            }
            # Projection detection
            try:
                if line.isReference:
                    curve_info["isReference"] = True
                    try:
                        ref = line.referencedEntity
                        if ref:
                            edge = adsk.fusion.BRepEdge.cast(ref)
                            if edge:
                                pf = {"type": "BRepEdge", "body": edge.body.name}
                                try:
                                    sv = edge.startVertex.geometry
                                    ev = edge.endVertex.geometry
                                    pf["startVertex"] = [round(sv.x, 4), round(sv.y, 4), round(sv.z, 4)]
                                    pf["endVertex"] = [round(ev.x, 4), round(ev.y, 4), round(ev.z, 4)]
                                except:
                                    pass
                                curve_info["projectedFrom"] = pf
                            else:
                                body = adsk.fusion.BRepBody.cast(ref)
                                if body:
                                    pf = {"type": "BRepBody", "body": body.name}
                                    try:
                                        pf["bodyComponent"] = body.parentComponent.name
                                    except:
                                        pass
                                    # Detect intersect vs project: if body bbox
                                    # spans the sketch plane, it's an intersection
                                    try:
                                        bb = body.boundingBox
                                        plane_origin = sk.origin
                                        normal = adsk.core.Vector3D.create(
                                            sk.xDirection.y * sk.yDirection.z - sk.xDirection.z * sk.yDirection.y,
                                            sk.xDirection.z * sk.yDirection.x - sk.xDirection.x * sk.yDirection.z,
                                            sk.xDirection.x * sk.yDirection.y - sk.xDirection.y * sk.yDirection.x)
                                        # Project bbox corners onto normal to get extent
                                        n = normal
                                        plane_d = n.x * plane_origin.x + n.y * plane_origin.y + n.z * plane_origin.z
                                        min_d = n.x * bb.minPoint.x + n.y * bb.minPoint.y + n.z * bb.minPoint.z
                                        max_d = n.x * bb.maxPoint.x + n.y * bb.maxPoint.y + n.z * bb.maxPoint.z
                                        if min(min_d, max_d) < plane_d < max(min_d, max_d):
                                            pf["method"] = "intersect"
                                        else:
                                            pf["method"] = "project"
                                    except:
                                        pass
                                    curve_info["projectedFrom"] = pf
                                else:
                                    face = adsk.fusion.BRepFace.cast(ref)
                                    if face:
                                        curve_info["projectedFrom"] = {"type": "BRepFace", "body": face.body.name}
                                    else:
                                        ca = adsk.fusion.ConstructionAxis.cast(ref)
                                        if ca:
                                            curve_info["projectedFrom"] = {"type": "ConstructionAxis", "name": ca.name}
                                        else:
                                            cp = adsk.fusion.ConstructionPlane.cast(ref)
                                            if cp:
                                                curve_info["projectedFrom"] = {"type": "ConstructionPlane", "name": cp.name}
                    except:
                        pass
            except:
                pass
            curves_info.append(curve_info)
            continue
        arc = adsk.fusion.SketchArc.cast(c)
        if arc:
            arc_info = {
                "type": "Arc",
                "center": [round(arc.centerSketchPoint.geometry.x, 4),
                           round(arc.centerSketchPoint.geometry.y, 4)],
                "radius": round(arc.radius, 4),
                "start": [round(arc.startSketchPoint.geometry.x, 4),
                          round(arc.startSketchPoint.geometry.y, 4)],
                "end": [round(arc.endSketchPoint.geometry.x, 4),
                        round(arc.endSketchPoint.geometry.y, 4)],
            }
            try:
                _, _, _, _, sweep = arc.geometry.getData()
                arc_info["sweepAngle"] = round(sweep, 4)
            except:
                pass
            # Projection detection
            try:
                if arc.isReference:
                    arc_info["isReference"] = True
                    try:
                        ref = arc.referencedEntity
                        if ref:
                            edge = adsk.fusion.BRepEdge.cast(ref)
                            if edge:
                                pf = {"type": "BRepEdge", "body": edge.body.name}
                                try:
                                    sv = edge.startVertex.geometry
                                    ev = edge.endVertex.geometry
                                    pf["startVertex"] = [round(sv.x, 4), round(sv.y, 4), round(sv.z, 4)]
                                    pf["endVertex"] = [round(ev.x, 4), round(ev.y, 4), round(ev.z, 4)]
                                except:
                                    pass
                                arc_info["projectedFrom"] = pf
                            else:
                                body = adsk.fusion.BRepBody.cast(ref)
                                if body:
                                    pf = {"type": "BRepBody", "body": body.name}
                                    try:
                                        pf["bodyComponent"] = body.parentComponent.name
                                    except:
                                        pass
                                    try:
                                        bb = body.boundingBox
                                        po = sk.origin
                                        n = adsk.core.Vector3D.create(
                                            sk.xDirection.y * sk.yDirection.z - sk.xDirection.z * sk.yDirection.y,
                                            sk.xDirection.z * sk.yDirection.x - sk.xDirection.x * sk.yDirection.z,
                                            sk.xDirection.x * sk.yDirection.y - sk.xDirection.y * sk.yDirection.x)
                                        pd = n.x*po.x + n.y*po.y + n.z*po.z
                                        min_d = n.x*bb.minPoint.x + n.y*bb.minPoint.y + n.z*bb.minPoint.z
                                        max_d = n.x*bb.maxPoint.x + n.y*bb.maxPoint.y + n.z*bb.maxPoint.z
                                        pf["method"] = "intersect" if min(min_d,max_d) < pd < max(min_d,max_d) else "project"
                                    except:
                                        pass
                                    arc_info["projectedFrom"] = pf
                                else:
                                    face = adsk.fusion.BRepFace.cast(ref)
                                    if face:
                                        arc_info["projectedFrom"] = {"type": "BRepFace", "body": face.body.name}
                                    else:
                                        ca = adsk.fusion.ConstructionAxis.cast(ref)
                                        if ca:
                                            arc_info["projectedFrom"] = {"type": "ConstructionAxis", "name": ca.name}
                                        else:
                                            cp = adsk.fusion.ConstructionPlane.cast(ref)
                                            if cp:
                                                arc_info["projectedFrom"] = {"type": "ConstructionPlane", "name": cp.name}
                    except:
                        pass
            except:
                pass
            curves_info.append(arc_info)
            continue
        circle = adsk.fusion.SketchCircle.cast(c)
        if circle:
            curves_info.append({
                "type": "Circle",
                "center": [round(circle.centerSketchPoint.geometry.x, 4),
                           round(circle.centerSketchPoint.geometry.y, 4)],
                "radius": round(circle.radius, 4),
            })
            continue
        # Fitted spline
        spline = adsk.fusion.SketchFittedSpline.cast(c)
        if spline:
            pts = []
            for pi in range(spline.fitPoints.count):
                fp = spline.fitPoints.item(pi)
                pts.append([round(fp.geometry.x, 4), round(fp.geometry.y, 4)])
            # Densify: sample additional points along the spline evaluator
            # for higher-fidelity reproduction when reconstructing the sketch.
            if len(pts) >= 2:
                try:
                    geom = spline.geometry  # NurbsCurve3D in sketch space
                    ev = geom.evaluator
                    ok, sp_param, ep_param = ev.getParameterExtents()
                    if ok:
                        n_target = max(15, len(pts))
                        dense_pts = []
                        for si in range(n_target):
                            t = sp_param + (ep_param - sp_param) * si / (n_target - 1)
                            ok_pt, pt = ev.getPointAtParameter(t)
                            if ok_pt:
                                dense_pts.append([round(pt.x, 4), round(pt.y, 4)])
                        if len(dense_pts) >= len(pts):
                            pts = dense_pts
                except:
                    pass
            spline_info = {
                "type": "FittedSpline",
                "fitPoints": pts,
                "isConstruction": spline.isConstruction,
            }
            try:
                if spline.isReference:
                    spline_info["isReference"] = True
            except:
                pass
            curves_info.append(spline_info)
            continue
        # Fixed spline (B-spline with control frame)
        fixed_spline = adsk.fusion.SketchFixedSpline.cast(c)
        if fixed_spline:
            pts = []
            # Try controlFramePoints first
            try:
                for pi in range(fixed_spline.controlFramePoints.count):
                    cp = fixed_spline.controlFramePoints.item(pi)
                    pts.append([round(cp.geometry.x, 4), round(cp.geometry.y, 4)])
            except:
                pass
            # Fallback: extract from NurbsCurve3D geometry
            if not pts:
                try:
                    geom = fixed_spline.geometry
                    (ok, ctrl_pts, degree, knots, is_rational, weights, is_periodic) = geom.getData()
                    if ok:
                        for pi in range(ctrl_pts.count):
                            p = ctrl_pts.item(pi)
                            sp = sk.modelToSketchSpace(p)
                            pts.append([round(sp.x, 4), round(sp.y, 4)])
                except:
                    pass
            # Fallback 2: sample points along the curve
            if not pts:
                try:
                    ev = fixed_spline.geometry.evaluator
                    (ok, t0, t1) = ev.getParameterExtents()
                    if ok:
                        n_samples = 20
                        for si in range(n_samples + 1):
                            t = t0 + (t1 - t0) * si / n_samples
                            (ok2, pt3d) = ev.getPointAtParameter(t)
                            if ok2:
                                sp = sk.modelToSketchSpace(pt3d)
                                pts.append([round(sp.x, 4), round(sp.y, 4)])
                        sp_info["isSampled"] = True
                except:
                    pass
            sp_info = {
                "type": "SketchFixedSpline",
                "controlPoints": pts,
                "isConstruction": fixed_spline.isConstruction,
            }
            try:
                sp_info["start"] = [round(fixed_spline.startSketchPoint.geometry.x, 4),
                                    round(fixed_spline.startSketchPoint.geometry.y, 4)]
                sp_info["end"] = [round(fixed_spline.endSketchPoint.geometry.x, 4),
                                  round(fixed_spline.endSketchPoint.geometry.y, 4)]
            except:
                pass
            try:
                if fixed_spline.isReference:
                    sp_info["isReference"] = True
            except:
                pass
            curves_info.append(sp_info)
            continue
        # Unknown curve type — capture minimally
        curves_info.append({"type": type(c).__name__})

    # Restore timeline after projection capture
    if _rolled:
        try:
            design.timeline.moveToEnd()
        except:
            pass

    # Post-process: attribute un-attributed reference LINE curves by matching
    # against body edges in model space.  This handles curves from
    # intersectWithSketchPlane whose referencedEntity returns None.
    _unattr = [i for i, c in enumerate(curves_info)
               if c.get("isReference") and "projectedFrom" not in c
               and c.get("type") == "Line"
               and c.get("start") and c.get("end")]
    _plane_info = info.get("plane", {})
    if _unattr and _plane_info and _plane_info.get("body"):
        face_body_name = _plane_info.get("body", "")
        _found_bodies = {}  # body_name -> (body, comp_name)
        # Collect candidate bodies (skip the face body itself)
        _all_bodies = []
        try:
            for _occ in design.rootComponent.allOccurrences:
                for _bi in range(_occ.bRepBodies.count):
                    _b = _occ.bRepBodies.item(_bi)
                    if _b.name != face_body_name:
                        _all_bodies.append(_b)
        except:
            pass
        # Build edge cache: {body_name: [(sv, ev), ...]}
        _edge_cache = {}
        for _b in _all_bodies:
            bn = _b.name
            if bn in _edge_cache:
                continue
            edges = []
            try:
                for _ei in range(min(_b.edges.count, 500)):
                    _e = _b.edges.item(_ei)
                    _sv = _e.startVertex.geometry
                    _ev = _e.endVertex.geometry
                    edges.append((_sv.x, _sv.y, _sv.z, _ev.x, _ev.y, _ev.z))
            except:
                pass
            _edge_cache[bn] = edges
            try:
                _found_bodies[bn] = (_b, _b.parentComponent.name)
            except:
                _found_bodies[bn] = (_b, "")
        for ri in _unattr:
            c = curves_info[ri]
            sx, sy = c["start"]
            ex, ey = c["end"]
            try:
                sp3 = sk.sketchToModelSpace(adsk.core.Point3D.create(sx, sy, 0))
                ep3 = sk.sketchToModelSpace(adsk.core.Point3D.create(ex, ey, 0))
            except:
                continue
            spx, spy, spz = sp3.x, sp3.y, sp3.z
            epx, epy, epz = ep3.x, ep3.y, ep3.z
            best_bn, best_d = None, 0.5
            for bn, edges in _edge_cache.items():
                for (svx,svy,svz,evx,evy,evz) in edges:
                    d1 = (abs(svx-spx)+abs(svy-spy)+abs(svz-spz) +
                          abs(evx-epx)+abs(evy-epy)+abs(evz-epz))
                    d2 = (abs(svx-epx)+abs(svy-epy)+abs(svz-epz) +
                          abs(evx-spx)+abs(evy-spy)+abs(evz-spz))
                    d = min(d1, d2)
                    if d < best_d:
                        best_d = d
                        best_bn = bn
                        if d < 0.01:
                            break
                if best_d < 0.01:
                    break
            if best_bn:
                _, comp_name = _found_bodies.get(best_bn, (None, ""))
                c["projectedFrom"] = {
                    "type": "BRepBody",
                    "body": best_bn,
                    "method": "intersect",
                }
                if comp_name:
                    c["projectedFrom"]["bodyComponent"] = comp_name

    info["curves"] = curves_info
    info["profileCount"] = sk.profiles.count

    # Profile bounding boxes
    profiles_info = []
    for pi in range(sk.profiles.count):
        try:
            p = sk.profiles.item(pi)
            bb = p.boundingBox
            profiles_info.append({
                "index": pi,
                "min": [round(bb.minPoint.x, 4), round(bb.minPoint.y, 4)],
                "max": [round(bb.maxPoint.x, 4), round(bb.maxPoint.y, 4)],
            })
        except:
            profiles_info.append({"index": pi})
    if profiles_info:
        info["profiles"] = profiles_info

    # Dimensions (with entity targets)
    dims_info = []
    for di in range(sk.sketchDimensions.count):
        d = sk.sketchDimensions.item(di)
        dim_entry = {
            "type": type(d).__name__,
            "expression": d.parameter.expression if d.parameter else None,
            "value": round(d.parameter.value, 6) if d.parameter else None,
        }

        # Capture dimension entity targets for reconstruction
        lin = adsk.fusion.SketchLinearDimension.cast(d)
        if lin:
            try:
                dim_entry["entityOne"] = _identify_sketch_entity(lin.entityOne, sk)
            except:
                pass
            try:
                dim_entry["entityTwo"] = _identify_sketch_entity(lin.entityTwo, sk)
            except:
                pass
            try:
                orient = lin.orientation
                if orient == adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation:
                    dim_entry["orientation"] = "Horizontal"
                elif orient == adsk.fusion.DimensionOrientations.VerticalDimensionOrientation:
                    dim_entry["orientation"] = "Vertical"
                elif orient == adsk.fusion.DimensionOrientations.AlignedDimensionOrientation:
                    dim_entry["orientation"] = "Aligned"
            except:
                pass

        radial = adsk.fusion.SketchRadialDimension.cast(d)
        if radial:
            try:
                dim_entry["entity"] = _identify_sketch_entity(radial.entity, sk)
            except:
                pass

        diametral = adsk.fusion.SketchDiameterDimension.cast(d)
        if diametral:
            try:
                dim_entry["entity"] = _identify_sketch_entity(diametral.entity, sk)
            except:
                pass

        angular = adsk.fusion.SketchAngularDimension.cast(d)
        if angular:
            try:
                dim_entry["lineOne"] = _identify_sketch_entity(angular.lineOne, sk)
            except:
                pass
            try:
                dim_entry["lineTwo"] = _identify_sketch_entity(angular.lineTwo, sk)
            except:
                pass

        dims_info.append(dim_entry)
    info["dimensions"] = dims_info

    # Constraints (with entity targets)
    constraints_info = []
    for ci in range(sk.geometricConstraints.count):
        gc = sk.geometricConstraints.item(ci)
        constraint_entry = {"type": type(gc).__name__}

        # Coincident
        coinc = adsk.fusion.CoincidentConstraint.cast(gc)
        if coinc:
            try:
                constraint_entry["point"] = _identify_sketch_entity(coinc.point, sk)
            except:
                pass
            try:
                constraint_entry["entity"] = _identify_sketch_entity(coinc.entity, sk)
            except:
                pass

        # Horizontal
        horiz = adsk.fusion.HorizontalConstraint.cast(gc)
        if horiz:
            try:
                constraint_entry["line"] = _identify_sketch_entity(horiz.line, sk)
            except:
                pass

        # Vertical
        vert = adsk.fusion.VerticalConstraint.cast(gc)
        if vert:
            try:
                constraint_entry["line"] = _identify_sketch_entity(vert.line, sk)
            except:
                pass

        # Parallel
        para = adsk.fusion.ParallelConstraint.cast(gc)
        if para:
            try:
                constraint_entry["lineOne"] = _identify_sketch_entity(para.lineOne, sk)
            except:
                pass
            try:
                constraint_entry["lineTwo"] = _identify_sketch_entity(para.lineTwo, sk)
            except:
                pass

        # Perpendicular
        perp = adsk.fusion.PerpendicularConstraint.cast(gc)
        if perp:
            try:
                constraint_entry["lineOne"] = _identify_sketch_entity(perp.lineOne, sk)
            except:
                pass
            try:
                constraint_entry["lineTwo"] = _identify_sketch_entity(perp.lineTwo, sk)
            except:
                pass

        # Tangent
        tang = adsk.fusion.TangentConstraint.cast(gc)
        if tang:
            try:
                constraint_entry["curveOne"] = _identify_sketch_entity(tang.curveOne, sk)
            except:
                pass
            try:
                constraint_entry["curveTwo"] = _identify_sketch_entity(tang.curveTwo, sk)
            except:
                pass

        # Equal
        eq = adsk.fusion.EqualConstraint.cast(gc)
        if eq:
            try:
                constraint_entry["curveOne"] = _identify_sketch_entity(eq.curveOne, sk)
            except:
                pass
            try:
                constraint_entry["curveTwo"] = _identify_sketch_entity(eq.curveTwo, sk)
            except:
                pass

        # MidPoint
        mp = adsk.fusion.MidPointConstraint.cast(gc)
        if mp:
            try:
                constraint_entry["point"] = _identify_sketch_entity(mp.point, sk)
            except:
                pass
            try:
                constraint_entry["midPointCurve"] = _identify_sketch_entity(mp.midPointCurve, sk)
            except:
                pass

        # Symmetry
        sym = adsk.fusion.SymmetryConstraint.cast(gc)
        if sym:
            try:
                constraint_entry["entityOne"] = _identify_sketch_entity(sym.entityOne, sk)
            except:
                pass
            try:
                constraint_entry["entityTwo"] = _identify_sketch_entity(sym.entityTwo, sk)
            except:
                pass
            try:
                constraint_entry["symmetryLine"] = _identify_sketch_entity(sym.symmetryLine, sk)
            except:
                pass

        constraints_info.append(constraint_entry)
    info["constraints"] = constraints_info

    return info


# ── Sketch summary (lightweight, for component tree) ──

def _capture_sketch_summary(sk):
    """Lightweight sketch info for component tree."""
    info = {"name": sk.name, "dimensionCount": sk.sketchDimensions.count}
    dims = []
    for di in range(sk.sketchDimensions.count):
        d = sk.sketchDimensions.item(di)
        if d.parameter:
            dims.append({
                "name": d.parameter.name,
                "expression": d.parameter.expression,
                "value": round(d.parameter.value, 6),
            })
    info["dimensions"] = dims
    return info


# ── Extrude ──

def _capture_extrude(ext, idx, tl, design=None):
    """Capture an ExtrudeFeature."""
    info = {"type": "Extrude", "name": ext.name}

    op_map = {
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation: "NewBody",
        adsk.fusion.FeatureOperations.CutFeatureOperation: "Cut",
        adsk.fusion.FeatureOperations.JoinFeatureOperation: "Join",
        adsk.fusion.FeatureOperations.IntersectFeatureOperation: "Intersect",
    }
    info["operation"] = op_map.get(ext.operation, str(ext.operation))

    # Extent type and distance
    try:
        extent = ext.extentOne
        if isinstance(extent, adsk.fusion.DistanceExtentDefinition):
            info["extentType"] = "Distance"
            info["distance"] = extent.distance.expression
        elif isinstance(extent, adsk.fusion.SymmetricExtentDefinition):
            info["extentType"] = "Symmetric"
            info["distance"] = extent.distance.expression
        else:
            info["extentType"] = type(extent).__name__
    except:
        pass

    # Check for symmetric
    try:
        if ext.extentType == adsk.fusion.FeatureExtentTypes.SymmetricFeatureExtentType:
            info["extentType"] = "Symmetric"
            sym_ext = adsk.fusion.SymmetricExtentDefinition.cast(ext.extentOne)
            if sym_ext:
                info["distance"] = sym_ext.distance.expression
    except:
        pass

    # Taper angle
    try:
        ta = ext.taperAngleOne
        if ta:
            info["taperAngle"] = ta.expression
    except:
        pass

    # Two-sided extent
    try:
        if ext.extentType == adsk.fusion.FeatureExtentTypes.TwoSidesFeatureExtentType:
            info["hasTwoExtents"] = True
            ext2 = ext.extentTwo
            if isinstance(ext2, adsk.fusion.DistanceExtentDefinition):
                info["extentTwoType"] = "Distance"
                info["distanceTwo"] = ext2.distance.expression
            else:
                info["extentTwoType"] = type(ext2).__name__
            try:
                ta2 = ext.taperAngleTwo
                if ta2:
                    info["taperAngleTwo"] = ta2.expression
            except:
                pass
    except:
        pass

    # Direction flipped
    try:
        info["isDirectionFlipped"] = ext.isDirectionFlipped
    except:
        pass

    # Sketch — multi-strategy capture (only when timeline context is available)
    if idx is not None and tl is not None:
        sk_found = _find_sketch_for_extrude(ext, idx, tl, info)
    else:
        sk_found = _find_sketch_for_extrude_no_timeline(ext, info)

    if sk_found:
        info["sketch"] = sk_found.name
        try:
            info["sketchComponent"] = sk_found.parentComponent.name
        except:
            pass
        # Profile index matching
        _match_profile_index(ext, sk_found, info)
    elif "sketchError" not in info and info.get("profileType") not in ("BRepFace", "Inaccessible"):
        info["sketchError"] = "no sketch found (all strategies failed)"

    body_names = [b.name for b in ext.bodies]

    # Try rollTo(False) to capture user-renamed body names.  At end-of-
    # timeline a consumed body's ext.bodies may be empty or stale; rolling
    # to just AFTER the feature shows the body alive with its current name.
    # NOTE: _roll_to_feature uses rollTo(True) (before), we need (False) (after).
    if design and ext.operation == adsk.fusion.FeatureOperations.NewBodyFeatureOperation:
        try:
            tl = design.timeline
            ext.timelineObject.rollTo(False)  # roll to just after this feature
            try:
                rolled = [b.name for b in ext.bodies]
                if rolled:
                    body_names = rolled
            finally:
                tl.moveToEnd()
        except:
            pass

    # If bodies list is still empty (consumed by downstream combine/join),
    # infer the body name by scanning downstream Combine features.
    if not body_names and design and ext.operation == adsk.fusion.FeatureOperations.NewBodyFeatureOperation:
        if idx is not None and tl is not None:
            body_names = _infer_extrude_body_name(ext, idx, tl, design)

    info["bodies"] = body_names

    def _try_participants():
        try:
            pb = ext.participantBodies
            if pb and pb.count > 0:
                info["participantBodies"] = [pb.item(i).name for i in range(pb.count)]
        except:
            pass

    _try_participants()
    if "participantBodies" not in info and design:
        try:
            with _roll_to_feature(ext, design):
                _try_participants()
        except:
            pass

    # Fallback: infer participantBodies by comparing body volumes before/after
    # the extrude. The body whose volume changed is the actual JOIN/CUT target.
    if "participantBodies" not in info and info.get("operation") in ("Join", "Cut") and design:
        try:
            tl = design.timeline
            tlo = ext.timelineObject
            idx = tlo.index
            comp = ext.parentComponent

            # Volumes BEFORE the extrude
            tl.markerPosition = idx
            before = {}
            for i in range(comp.bRepBodies.count):
                b = comp.bRepBodies.item(i)
                before[b.name] = round(b.volume, 4)

            # Volumes AFTER the extrude
            tl.markerPosition = idx + 1
            after = {}
            for i in range(comp.bRepBodies.count):
                b = comp.bRepBodies.item(i)
                after[b.name] = round(b.volume, 4)

            tl.moveToEnd()

            # Bodies whose volume changed = participants
            changed = [n for n in before if n in after and before[n] != after[n]]
            if changed:
                info["participantBodies"] = changed
        except:
            try:
                design.timeline.moveToEnd()
            except:
                pass

    try:
        if ext.startFaces and ext.startFaces.count > 0:
            info["startFace"] = True
    except:
        pass

    return info


def _infer_extrude_body_name(ext, idx, tl, design):
    """Infer body name for an extrude whose body was consumed by a downstream combine.

    Walks forward in the timeline looking for CombineFeatures that reference
    a toolBody created by this extrude. Uses rollTo on the combine to access
    its toolBodies (which preserves the original body name).
    """
    try:
        ext_comp = ext.parentComponent
    except:
        return []

    for fwd in range(idx + 1, min(idx + 15, tl.count)):
        try:
            fwd_entity = tl.item(fwd).entity
        except:
            continue
        if fwd_entity is None:
            continue
        comb = adsk.fusion.CombineFeature.cast(fwd_entity)
        if not comb:
            continue
        try:
            if comb.parentComponent != ext_comp:
                continue
        except:
            continue
        # Try to get toolBodies via rollTo
        try:
            with _roll_to_feature(comb, design):
                tools = comb.toolBodies
                for ti in range(tools.count):
                    t = tools.item(ti)
                    # The tool body name is the one we're looking for
                    return [t.name]
        except:
            # Direct access fallback
            try:
                tools = comb.toolBodies
                for ti in range(tools.count):
                    return [tools.item(ti).name]
            except:
                pass
    return []


def _find_sketch_for_extrude(ext, idx, tl, info):
    """Multi-strategy sketch finding for an extrude feature (with timeline)."""
    sk_found = _find_sketch_from_profile(ext, info)

    # Strategy: walk timeline backwards (skip for face-based profiles only).
    # Inaccessible profiles still need sketch name — the variant search
    # system will try all profile indices at build time.
    if not sk_found and info.get("profileType") != "BRepFace":
        try:
            for back_idx in range(idx - 1, -1, -1):
                back_item = tl.item(back_idx)
                try:
                    back_entity = back_item.entity
                except RuntimeError:
                    continue
                if back_entity is None:
                    continue
                back_sk = adsk.fusion.Sketch.cast(back_entity)
                if back_sk:
                    try:
                        sk_comp = back_sk.parentComponent
                        ext_comp = ext.parentComponent
                        if sk_comp == ext_comp or sk_comp == ext_comp.parentDesign.rootComponent:
                            sk_found = back_sk
                            break
                    except:
                        sk_found = back_sk
                        break
        except Exception as e:
            if "sketchError" not in info:
                info["sketchError"] = f"timeline walk: {e}"

    return sk_found


def _find_sketch_for_extrude_no_timeline(ext, info):
    """Sketch finding for an extrude feature without timeline context."""
    return _find_sketch_from_profile(ext, info)


def _find_sketch_from_profile(ext, info):
    """Extract sketch from extrude's profile (shared by both timeline and no-timeline paths)."""
    sk_found = None
    try:
        profile = ext.profile
        profiles_coll = adsk.core.ObjectCollection.cast(profile)
        if profiles_coll:
            for pi in range(profiles_coll.count):
                p = profiles_coll.item(pi)
                try:
                    sk_found = adsk.fusion.Profile.cast(p).parentSketch
                except:
                    pass
                if not sk_found:
                    try:
                        sk_found = p.parentSketch
                    except:
                        pass
                if sk_found:
                    break
            # If no sketch found, check if profile items are BRepFaces
            if not sk_found:
                try:
                    f0 = adsk.fusion.BRepFace.cast(profiles_coll.item(0))
                    if f0:
                        info["profileType"] = "BRepFace"
                        return None
                except:
                    pass
        else:
            try:
                p = adsk.fusion.Profile.cast(profile)
                if p:
                    sk_found = p.parentSketch
            except:
                pass
            if not sk_found:
                try:
                    sk_found = profile.parentSketch
                except:
                    pass
            # Check BRepFace
            if not sk_found:
                try:
                    face = adsk.fusion.BRepFace.cast(profile)
                    if face:
                        info["profileType"] = "BRepFace"
                        return None
                except:
                    pass
    except Exception as e:
        # InternalValidationError at end-of-timeline often means a face-based
        # extrude whose profile can't be read.  Mark it so timeline walk-back
        # doesn't incorrectly assign a sketch.
        if "InternalValidationError" in str(e):
            info["profileType"] = "Inaccessible"
        info["sketchError"] = f"profile access: {e}"

    return sk_found


def _match_profile_index(ext, sk_found, info):
    """Match extrude profile bounding box to sketch profiles."""
    try:
        profile = ext.profile
        profiles_coll = adsk.core.ObjectCollection.cast(profile)
        # Collect ALL profiles the extrude uses
        ext_profs = []
        if profiles_coll:
            for i in range(profiles_coll.count):
                p = adsk.fusion.Profile.cast(profiles_coll.item(i))
                if p:
                    ext_profs.append(p)
        else:
            p = adsk.fusion.Profile.cast(profile)
            if p:
                ext_profs.append(p)

        if ext_profs:
            info["profileCount"] = sk_found.profiles.count
            matched_indices = []
            for ext_prof in ext_profs:
                ext_bb = ext_prof.boundingBox
                ext_min = (round(ext_bb.minPoint.x, 3), round(ext_bb.minPoint.y, 3))
                ext_max = (round(ext_bb.maxPoint.x, 3), round(ext_bb.maxPoint.y, 3))
                best_idx = 0
                best_dist = float('inf')
                for pi in range(sk_found.profiles.count):
                    sp = sk_found.profiles.item(pi)
                    sp_bb = sp.boundingBox
                    sp_min = (round(sp_bb.minPoint.x, 3), round(sp_bb.minPoint.y, 3))
                    sp_max = (round(sp_bb.maxPoint.x, 3), round(sp_bb.maxPoint.y, 3))
                    dist = (abs(sp_min[0] - ext_min[0]) + abs(sp_min[1] - ext_min[1])
                            + abs(sp_max[0] - ext_max[0]) + abs(sp_max[1] - ext_max[1]))
                    if dist < best_dist:
                        best_dist = dist
                        best_idx = pi
                matched_indices.append(best_idx)
            # Single profile → profileIndex (int), multi → profileIndices (list)
            if len(matched_indices) == 1:
                info["profileIndex"] = matched_indices[0]
            else:
                info["profileIndices"] = matched_indices
                info["profileIndex"] = matched_indices[0]  # backward compat
    except:
        pass


# ── Construction Plane ──

def _capture_construction_plane(cp):
    """Capture a ConstructionPlane feature."""
    info = {"type": "ConstructionPlane", "name": cp.name}

    try:
        defn = cp.definition
        offset_def = adsk.fusion.ConstructionPlaneOffsetDefinition.cast(defn)
        angle_def = adsk.fusion.ConstructionPlaneAtAngleDefinition.cast(defn)
        midplane_def = adsk.fusion.ConstructionPlaneMidplaneDefinition.cast(defn)

        if offset_def:
            info["definitionType"] = "Offset"
            info["offset"] = offset_def.offset.expression
            base = offset_def.planarEntity
            bcp = adsk.fusion.ConstructionPlane.cast(base)
            if bcp:
                info["basePlane"] = bcp.name
            else:
                info["basePlane"] = str(base.objectType)

        elif midplane_def:
            info["definitionType"] = "MidPlane"
            for attr, key in [("planarEntityOne", "planeOne"), ("planarEntityTwo", "planeTwo")]:
                try:
                    entity = getattr(midplane_def, attr)
                    bcp = adsk.fusion.ConstructionPlane.cast(entity)
                    if bcp:
                        info[key] = {"type": "ConstructionPlane", "name": bcp.name}
                    else:
                        face = adsk.fusion.BRepFace.cast(entity)
                        if face:
                            pof = face.pointOnFace
                            info[key] = {
                                "type": "BRepFace",
                                "body": face.body.name,
                                "pointOnFace": [round(pof.x, 4), round(pof.y, 4), round(pof.z, 4)],
                            }
                        else:
                            info[key] = {"type": str(entity.objectType)}
                except:
                    pass

        elif angle_def:
            info["definitionType"] = "AtAngle"
            info["angle"] = angle_def.angle.expression
            # Base plane
            try:
                base = angle_def.planarEntity
                bcp = adsk.fusion.ConstructionPlane.cast(base)
                if bcp:
                    info["basePlane"] = bcp.name
                else:
                    info["basePlane"] = str(base.objectType)
            except:
                pass
            # Linear entity (edge/line to rotate around)
            try:
                line = angle_def.linearEntity
                edge = adsk.fusion.BRepEdge.cast(line)
                if edge:
                    sv = edge.startVertex.geometry
                    ev = edge.endVertex.geometry
                    info["linearEntity"] = {
                        "type": "BRepEdge",
                        "body": edge.body.name,
                        "start": [round(sv.x, 4), round(sv.y, 4), round(sv.z, 4)],
                        "end": [round(ev.x, 4), round(ev.y, 4), round(ev.z, 4)],
                    }
                else:
                    ca = adsk.fusion.ConstructionAxis.cast(line)
                    sl = adsk.fusion.SketchLine.cast(line)
                    if ca:
                        info["linearEntity"] = {"type": "ConstructionAxis", "name": ca.name}
                    elif sl:
                        s = sl.startSketchPoint.geometry
                        e = sl.endSketchPoint.geometry
                        info["linearEntity"] = {
                            "type": "SketchLine",
                            "parentSketch": sl.parentSketch.name,
                            "start": [round(s.x, 4), round(s.y, 4), round(s.z, 4)],
                            "end": [round(e.x, 4), round(e.y, 4), round(e.z, 4)],
                        }
                    else:
                        info["linearEntity"] = {"type": str(line.objectType)}
            except:
                pass
    except Exception as e:
        info["definitionError"] = str(e)

    try:
        geom = cp.geometry
        info["normal"] = [round(geom.normal.x, 6), round(geom.normal.y, 6), round(geom.normal.z, 6)]
        info["origin"] = [round(geom.origin.x, 4), round(geom.origin.y, 4), round(geom.origin.z, 4)]
    except Exception as e:
        info["geometryError"] = str(e)

    return info


# ── Mirror ──

def _capture_mirror(mir, design=None):
    """Capture a MirrorFeature."""
    info = {"type": "Mirror", "name": mir.name}

    try:
        mp = mir.mirrorPlane
        bcp = adsk.fusion.ConstructionPlane.cast(mp)
        if bcp:
            info["mirrorPlane"] = {"type": "ConstructionPlane", "name": bcp.name}
            try:
                geom = bcp.geometry
                info["mirrorPlane"]["normal"] = [round(geom.normal.x, 6), round(geom.normal.y, 6), round(geom.normal.z, 6)]
                info["mirrorPlane"]["origin"] = [round(geom.origin.x, 4), round(geom.origin.y, 4), round(geom.origin.z, 4)]
            except:
                pass
        else:
            bf = adsk.fusion.BRepFace.cast(mp)
            if bf:
                info["mirrorPlane"] = {"type": "BRepFace", "body": bf.body.name}
                try:
                    eva = bf.evaluator
                    ok, pt, norm = eva.getNormalAtPoint(bf.pointOnFace)
                    if ok:
                        info["mirrorPlane"]["normal"] = [round(norm.x, 6), round(norm.y, 6), round(norm.z, 6)]
                        info["mirrorPlane"]["origin"] = [round(bf.pointOnFace.x, 4), round(bf.pointOnFace.y, 4), round(bf.pointOnFace.z, 4)]
                except:
                    pass
    except:
        pass

    # Input entities — need rollTo for BRep-dependent access
    def _try_inputs():
        try:
            inputs = mir.inputEntities
            input_names = []
            for ii in range(inputs.count):
                e = inputs.item(ii)
                if hasattr(e, 'name'):
                    input_names.append(e.name)
            if input_names:
                info["inputBodies"] = input_names
        except:
            pass

    if design:
        try:
            with _roll_to_feature(mir, design):
                _try_inputs()
        except:
            _try_inputs()
    else:
        _try_inputs()

    # Output bodies — try direct access first, rollTo if consumed downstream
    out = [b.name for b in mir.bodies]
    if not out and design:
        try:
            mir.timelineObject.rollTo(False)
            try:
                out = [b.name for b in mir.bodies]
            finally:
                design.timeline.moveToEnd()
        except:
            pass
    info["bodies"] = out

    try:
        if mir.patternComputeOption == adsk.fusion.PatternComputeOptions.IdenticalPatternCompute:
            info["computeOption"] = "Identical"
        elif mir.patternComputeOption == adsk.fusion.PatternComputeOptions.OptimizedPatternCompute:
            info["computeOption"] = "Optimized"
        elif mir.patternComputeOption == adsk.fusion.PatternComputeOptions.AdjustPatternCompute:
            info["computeOption"] = "Adjust"
    except:
        pass

    return info


# ── Rectangular Pattern ──

def _extract_linear_direction(entity):
    """Extract a normalised direction vector from any linear entity.

    Handles BRepEdge (Line3D geometry), SketchLine, BRepFace (plane normal),
    and ConstructionPlane (normal).  Returns [x, y, z] rounded to 6 decimals,
    or None if the entity type is unrecognised.
    """
    # BRepEdge — Line3D has startPoint/endPoint, NOT .direction
    try:
        edge = adsk.fusion.BRepEdge.cast(entity)
        if edge:
            line = adsk.core.Line3D.cast(edge.geometry)
            if line:
                s, e = line.startPoint, line.endPoint
                dx, dy, dz = e.x - s.x, e.y - s.y, e.z - s.z
                ln = (dx**2 + dy**2 + dz**2) ** 0.5
                if ln > 1e-6:
                    return [round(dx/ln, 6), round(dy/ln, 6), round(dz/ln, 6)]
    except:
        pass
    # SketchLine
    try:
        sl = adsk.fusion.SketchLine.cast(entity)
        if sl:
            s = sl.startSketchPoint.worldGeometry
            e = sl.endSketchPoint.worldGeometry
            dx, dy, dz = e.x - s.x, e.y - s.y, e.z - s.z
            ln = (dx**2 + dy**2 + dz**2) ** 0.5
            if ln > 1e-6:
                return [round(dx/ln, 6), round(dy/ln, 6), round(dz/ln, 6)]
    except:
        pass
    # BRepFace — use plane normal as direction
    try:
        face = adsk.fusion.BRepFace.cast(entity)
        if face:
            plane = adsk.core.Plane.cast(face.geometry)
            if plane:
                n = plane.normal
                return [round(n.x, 6), round(n.y, 6), round(n.z, 6)]
    except:
        pass
    # ConstructionPlane — use normal
    try:
        cp = adsk.fusion.ConstructionPlane.cast(entity)
        if cp:
            n = cp.geometry.normal
            return [round(n.x, 6), round(n.y, 6), round(n.z, 6)]
    except:
        pass
    return None


def _capture_rectangular_pattern(pat, design=None):
    """Capture a RectangularPatternFeature."""
    info = {"type": "RectangularPattern", "name": pat.name}

    try:
        info["quantityOne"] = pat.quantityOne.expression
        info["distanceOne"] = pat.distanceOne.expression
    except:
        pass

    try:
        q2 = pat.quantityTwo
        if q2:
            info["quantityTwo"] = q2.expression
    except:
        pass

    try:
        d2 = pat.distanceTwo
        if d2:
            info["distanceTwo"] = d2.expression
    except:
        pass

    try:
        axis = pat.directionOneEntity
        ca = adsk.fusion.ConstructionAxis.cast(axis)
        if ca:
            info["axisOne"] = ca.name
        # Don't set directionOne from entity — its natural direction may not
        # match the pattern's actual direction. Sign comes from body positions.
    except:
        pass

    # Direction two (if present)
    try:
        axis2 = pat.directionTwoEntity
        if axis2:
            ca2 = adsk.fusion.ConstructionAxis.cast(axis2)
            if ca2:
                info["axisTwo"] = ca2.name
                try:
                    line = ca2.geometry
                    info["directionTwo"] = [round(line.direction.x, 6),
                                            round(line.direction.y, 6),
                                            round(line.direction.z, 6)]
                except:
                    pass
            else:
                d2 = _extract_linear_direction(axis2)
                if d2:
                    info["directionTwo"] = d2
    except:
        pass

    try:
        if pat.patternDistanceType == adsk.fusion.PatternDistanceType.SpacingPatternDistanceType:
            info["distanceType"] = "Spacing"
        elif pat.patternDistanceType == adsk.fusion.PatternDistanceType.ExtentPatternDistanceType:
            info["distanceType"] = "Extent"
    except:
        pass

    # Input entities — may need rollTo for BRep-dependent access
    def _try_inputs():
        try:
            inputs = pat.inputEntities
            input_names = []
            for ii in range(inputs.count):
                e = inputs.item(ii)
                if hasattr(e, 'name'):
                    input_names.append(e.name)
            if input_names:
                info["inputs"] = input_names
        except:
            pass

    def _try_bodies_and_direction():
        """Capture bodies and infer direction inside rollTo.

        Must be called inside rollTo so pat.bodies returns ALL copies
        (at end-of-timeline, downstream Combines may consume pattern bodies).
        Also infers direction from body positions inside rollTo where copies
        are guaranteed to exist.
        """
        body_names = [pat.bodies.item(i).name for i in range(pat.bodies.count)]
        if body_names:
            info["bodies"] = body_names

        # Infer direction from the directionOneEntity geometry.
        # pat.bodies only returns 1 body (the input) — copies are invisible
        # both in pat.bodies and comp.bRepBodies during rollTo.
        # The axis entity (edge or construction axis) gives direction.
        if "directionOne" not in info:
            try:
                axis = pat.directionOneEntity
                direction = None
                ca = adsk.fusion.ConstructionAxis.cast(axis)
                if ca:
                    line = ca.geometry
                    direction = [line.direction.x, line.direction.y, line.direction.z]
                else:
                    edge = adsk.fusion.BRepEdge.cast(axis)
                    if edge:
                        sp = edge.startVertex.geometry
                        ep = edge.endVertex.geometry
                        direction = [ep.x - sp.x, ep.y - sp.y, ep.z - sp.z]
                if direction:
                    adx = abs(direction[0])
                    ady = abs(direction[1])
                    adz = abs(direction[2])
                    if adx >= ady and adx >= adz and adx > 0.001:
                        info["directionOne"] = [1.0 if direction[0] > 0 else -1.0, 0.0, 0.0]
                    elif ady >= adx and ady >= adz and ady > 0.001:
                        info["directionOne"] = [0.0, 1.0 if direction[1] > 0 else -1.0, 0.0]
                    elif adz > 0.001:
                        info["directionOne"] = [0.0, 0.0, 1.0 if direction[2] > 0 else -1.0]
            except:
                pass

    def _try_direction_entity():
        """Try to read directionOneEntity inside rollTo.

        Only captures axis NAME (for identification), NOT the direction vector.
        The entity's natural direction may not match the pattern's actual direction
        (e.g., pattern may use -X on the xConstructionAxis). Direction sign is
        always inferred from body positions at end-of-timeline.
        """
        if "axisOne" in info:
            return  # Already captured
        try:
            axis = pat.directionOneEntity
            ca = adsk.fusion.ConstructionAxis.cast(axis)
            if ca:
                info["axisOne"] = ca.name
        except:
            pass

    if design:
        try:
            with _roll_to_feature(pat, design):
                _try_inputs()
                _try_bodies_and_direction()
                _try_direction_entity()
        except:
            _try_inputs()
            _try_bodies_and_direction()
    else:
        _try_inputs()
        _try_bodies_and_direction()

    # Fallback: if bodies weren't captured inside rollTo
    if "bodies" not in info:
        info["bodies"] = [b.name for b in pat.bodies]

    # Transform rollTo direction from component-local to world space
    if "directionOne" in info and design:
        try:
            comp = pat.parentComponent
            root = design.rootComponent
            if comp != root:
                for occ in root.allOccurrences:
                    if occ.component == comp:
                        xf = occ.transform
                        dir_vec = adsk.core.Vector3D.create(
                            info["directionOne"][0],
                            info["directionOne"][1],
                            info["directionOne"][2])
                        dir_vec.transformBy(xf)
                        d = [dir_vec.x, dir_vec.y, dir_vec.z]
                        ad = [abs(d[0]), abs(d[1]), abs(d[2])]
                        if ad[0] >= ad[1] and ad[0] >= ad[2] and ad[0] > 0.001:
                            info["directionOne"] = [1.0 if d[0] > 0 else -1.0, 0.0, 0.0]
                        elif ad[1] >= ad[0] and ad[1] >= ad[2] and ad[1] > 0.001:
                            info["directionOne"] = [0.0, 1.0 if d[1] > 0 else -1.0, 0.0]
                        elif ad[2] > 0.001:
                            info["directionOne"] = [0.0, 0.0, 1.0 if d[2] > 0 else -1.0]
                        break
        except:
            pass

    # Pattern copy detection: scan component bodies at END-OF-TIMELINE.
    # rollTo(True) doesn't make pattern copies visible in comp.bRepBodies
    # (Fusion API quirk), but they ARE visible at end-of-timeline.
    try:
        comp = pat.parentComponent
        # Use body names (from "bodies") for seed identification.
        # "inputs" contains feature names (e.g. "Extrude2") which don't match
        # body names (e.g. "Body1"), so they can't be used for body lookup.
        seed_body_names = info.get("bodies", [])
        # Find seed body: first body matching bodies[0] in the component.
        # Store index because Fusion API proxy objects are new wrappers each
        # call — `is` comparison fails even for the same underlying entity.
        seed_idx = -1
        seed_min = None
        ref_vol = None
        if seed_body_names:
            for bi in range(comp.bRepBodies.count):
                b = comp.bRepBodies.item(bi)
                if b.name == seed_body_names[0]:
                    seed_idx = bi
                    ref_vol = b.volume
                    seed_min = [round(b.boundingBox.minPoint.x, 4),
                                round(b.boundingBox.minPoint.y, 4),
                                round(b.boundingBox.minPoint.z, 4)]
                    break
        # Fallback: use first body's volume as reference
        if ref_vol is None:
            for bi in range(comp.bRepBodies.count):
                ref_vol = comp.bRepBodies.item(bi).volume
                break
        # Find copies: same volume as seed (within 5% tolerance), exclude seed
        if ref_vol and ref_vol > 0:
            copies = []
            for bi in range(comp.bRepBodies.count):
                if bi == seed_idx:
                    continue
                b = comp.bRepBodies.item(bi)
                if abs(b.volume - ref_vol) / ref_vol < 0.05:
                    copies.append({
                        "name": b.name,
                        "min": [round(b.boundingBox.minPoint.x, 4),
                                round(b.boundingBox.minPoint.y, 4),
                                round(b.boundingBox.minPoint.z, 4)],
                    })
            if copies:
                # Infer direction from seed body → nearest copy at end-of-timeline.
                # Only used as FALLBACK when directionOneEntity wasn't readable.
                # Body positions are in component-local space, which may differ
                # from world space if the occurrence has rotation.
                if seed_min:
                    nearest = min(copies, key=lambda c:
                        sum(abs(a - b) for a, b in zip(c["min"], seed_min)))
                    dx = nearest["min"][0] - seed_min[0]
                    dy = nearest["min"][1] - seed_min[1]
                    dz = nearest["min"][2] - seed_min[2]
                    adx, ady, adz = abs(dx), abs(dy), abs(dz)
                    if adx >= ady and adx >= adz and adx > 0.001:
                        info["directionOne"] = [1.0 if dx > 0 else -1.0, 0.0, 0.0]
                    elif ady >= adx and ady >= adz and ady > 0.001:
                        info["directionOne"] = [0.0, 1.0 if dy > 0 else -1.0, 0.0]
                    elif adz > 0.001:
                        info["directionOne"] = [0.0, 0.0, 1.0 if dz > 0 else -1.0]

                # Transform direction from component-local to world space.
                # comp.bRepBodies gives positions in the component's local
                # coordinate system. If the occurrence has a rotation, the
                # local direction differs from world direction.
                if "directionOne" in info and design:
                    try:
                        root = design.rootComponent
                        if comp != root:
                            for occ in root.allOccurrences:
                                if occ.component == comp:
                                    xf = occ.transform
                                    dir_vec = adsk.core.Vector3D.create(
                                        info["directionOne"][0],
                                        info["directionOne"][1],
                                        info["directionOne"][2])
                                    dir_vec.transformBy(xf)
                                    d = [dir_vec.x, dir_vec.y, dir_vec.z]
                                    adx2, ady2, adz2 = abs(d[0]), abs(d[1]), abs(d[2])
                                    if adx2 >= ady2 and adx2 >= adz2 and adx2 > 0.001:
                                        info["directionOne"] = [1.0 if d[0] > 0 else -1.0, 0.0, 0.0]
                                    elif ady2 >= adx2 and ady2 >= adz2 and ady2 > 0.001:
                                        info["directionOne"] = [0.0, 1.0 if d[1] > 0 else -1.0, 0.0]
                                    elif adz2 > 0.001:
                                        info["directionOne"] = [0.0, 0.0, 1.0 if d[2] > 0 else -1.0]
                                    break
                    except:
                        pass

                # Sort by position along pattern axis for stable ordering
                d = info.get("directionOne", [1, 0, 0])
                ax = 0 if abs(d[0]) >= abs(d[1]) and abs(d[0]) >= abs(d[2]) else (
                     1 if abs(d[1]) >= abs(d[2]) else 2)
                copies.sort(key=lambda c: c["min"][ax])
                info["patternCopies"] = [c["name"] for c in copies]
    except Exception as e:
        import traceback
        app = adsk.core.Application.get()
        app.log(f"Pattern copy detection error: {e}\n{traceback.format_exc()}")

    return info


# ── Combine ──

def _capture_combine(comb, idx, tl, design=None):
    """Capture a CombineFeature with tool body inference."""
    info = {"type": "Combine", "name": comb.name}

    op_map = {
        adsk.fusion.FeatureOperations.JoinFeatureOperation: "Join",
        adsk.fusion.FeatureOperations.CutFeatureOperation: "Cut",
        adsk.fusion.FeatureOperations.IntersectFeatureOperation: "Intersect",
    }
    info["operation"] = op_map.get(comb.operation, str(comb.operation))

    def _get_target_and_tools():
        tool_names = []
        # Target body
        try:
            tb = comb.targetBody
            info["targetBody"] = tb.name
            try:
                info["targetComponent"] = tb.parentComponent.name
            except:
                pass
        except Exception as e:
            info["targetBodyError"] = str(e)

        # Tool bodies
        try:
            tools = comb.toolBodies
            tool_info = []
            for i in range(tools.count):
                t = tools.item(i)
                entry = {"name": t.name}
                try:
                    entry["component"] = t.parentComponent.name
                except:
                    pass
                tool_info.append(entry)
            tool_names = [t["name"] for t in tool_info]
            info["toolBodies"] = tool_names
            if any("component" in t for t in tool_info):
                info["toolComponents"] = [t.get("component", "") for t in tool_info]
        except Exception as e:
            info["toolBodiesError"] = str(e)
        return tool_names

    # Try direct access first
    tool_names = _get_target_and_tools()

    # Retry with rollTo if body access failed OR if tool names have duplicates
    # (duplicates indicate stale body references at end-of-timeline — Fusion API
    # quirk where comb.toolBodies returns wrong BRepBody objects after timeline
    # recomputation, e.g. pattern copies resolving to the source body).
    has_error = "targetBodyError" in info or "toolBodiesError" in info
    has_dupes = len(tool_names) != len(set(tool_names))
    if (has_error or has_dupes) and design:
        for key in ["targetBody", "targetBodyError", "targetComponent",
                     "toolBodies", "toolBodiesError", "toolComponents"]:
            info.pop(key, None)
        try:
            with _roll_to_feature(comb, design):
                tool_names = _get_target_and_tools()
        except Exception as e:
            info["rollToError"] = str(e)

    # Inference: if toolBodies is empty, walk timeline backwards
    if not tool_names and idx is not None and tl is not None:
        inferred = _infer_combine_tool_bodies(comb, idx, tl)
        if inferred:
            info["toolBodiesInferred"] = inferred

    try:
        info["isKeepToolBodies"] = comb.isKeepToolBodies
    except:
        pass

    # Capture output bodies — CUT operations may split the target into multiple pieces,
    # creating new bodies that the user may rename.  Use rollTo(False) to get current names.
    if info.get("operation") == "Cut" and design:
        try:
            comb.timelineObject.rollTo(False)
            try:
                out_bodies = [b.name for b in comb.bodies]
                if out_bodies:
                    info["outputBodies"] = out_bodies
            finally:
                design.timeline.moveToEnd()
        except:
            pass

    return info


def _infer_combine_tool_bodies(comb, idx, tl):
    """Walk timeline backwards to infer which bodies were consumed as tools."""
    inferred = []
    try:
        target_name = comb.targetBody.name
    except:
        return inferred

    try:
        target_comp = comb.targetBody.parentComponent
    except:
        return inferred

    for back_idx in range(idx - 1, max(idx - 10, -1), -1):
        try:
            back_item = tl.item(back_idx)
            back_entity = back_item.entity
        except:
            continue
        if back_entity is None:
            continue

        back_ext = adsk.fusion.ExtrudeFeature.cast(back_entity)
        if back_ext and back_ext.operation == adsk.fusion.FeatureOperations.NewBodyFeatureOperation:
            try:
                if back_ext.parentComponent == target_comp:
                    for b in back_ext.bodies:
                        if b.name != target_name:
                            try:
                                _ = b.volume
                            except:
                                inferred.append(b.name)
            except:
                pass

    return inferred


# ── Move ──

def _capture_move(mv, design=None):
    """Capture a MoveFeature."""
    info = {"type": "Move", "name": mv.name}

    try:
        transform = mv.transform
        info["matrix"] = [
            [round(transform.getCell(r, c), 12) for c in range(4)]
            for r in range(4)
        ]
        info["translation"] = [
            round(transform.translation.x, 4),
            round(transform.translation.y, 4),
            round(transform.translation.z, 4),
        ]
    except:
        pass

    def _try_inputs():
        try:
            inputs = mv.inputEntities
            input_names = []
            for ii in range(inputs.count):
                e = inputs.item(ii)
                if hasattr(e, 'name'):
                    input_names.append(e.name)
            if input_names:
                info["inputs"] = input_names
        except:
            pass

    if design:
        try:
            with _roll_to_feature(mv, design):
                _try_inputs()
        except:
            _try_inputs()
    else:
        _try_inputs()

    return info


# ── Edge vertex capture helper ──

def _capture_edge_vertices(edges):
    """Capture vertex positions for a collection of edges or faces.

    FilletEdgeSet.edges can contain BRepEdge or BRepFace items depending
    on how the user selected them. Handle both.
    """
    edge_list = []
    for ei in range(edges.count):
        item = edges.item(ei)
        face = adsk.fusion.BRepFace.cast(item)
        edge = adsk.fusion.BRepEdge.cast(item)
        if edge:
            try:
                sv = edge.startVertex.geometry
                ev = edge.endVertex.geometry
                edge_info = {
                    "type": "BRepEdge",
                    "start": [round(sv.x, 4), round(sv.y, 4), round(sv.z, 4)],
                    "end": [round(ev.x, 4), round(ev.y, 4), round(ev.z, 4)],
                }
                try:
                    edge_info["body"] = edge.body.name
                except:
                    pass
                edge_list.append(edge_info)
            except:
                pass
        elif face:
            try:
                pof = face.pointOnFace
                edge_info = {
                    "type": "BRepFace",
                    "pointOnFace": [round(pof.x, 4), round(pof.y, 4), round(pof.z, 4)],
                }
                try:
                    edge_info["body"] = face.body.name
                except:
                    pass
                edge_list.append(edge_info)
            except:
                pass
    return edge_list


# ── Chamfer ──

def _capture_chamfer(chamfer, design=None):
    """Capture a ChamferFeature with edge vertex positions."""
    info = {"type": "Chamfer", "name": chamfer.name}

    try:
        chamfer_type = chamfer.chamferType
        type_map = {
            adsk.fusion.ChamferTypes.EqualDistanceChamferType: "EqualDistance",
            adsk.fusion.ChamferTypes.TwoDistancesChamferType: "TwoDistances",
            adsk.fusion.ChamferTypes.DistanceAndAngleChamferType: "DistanceAndAngle",
        }
        info["chamferType"] = type_map.get(chamfer_type, str(chamfer_type))
    except:
        pass

    def _capture_edge_sets():
        try:
            edge_sets = chamfer.edgeSets
            sets_info = []
            total_edges = 0
            for si in range(edge_sets.count):
                es = edge_sets.item(si)
                set_entry = {}
                edges = _capture_edge_vertices(es.edges)
                set_entry["edges"] = edges
                total_edges += len(edges)

                # Detect edge set type and capture parameters
                eq = adsk.fusion.EqualDistanceChamferEdgeSet.cast(es)
                if eq:
                    set_entry["chamferType"] = "EqualDistance"
                    set_entry["distance"] = eq.distance.expression
                    info["distance"] = eq.distance.expression
                else:
                    two = adsk.fusion.TwoDistancesChamferEdgeSet.cast(es)
                    if two:
                        set_entry["chamferType"] = "TwoDistances"
                        set_entry["distanceOne"] = two.distanceOne.expression
                        set_entry["distanceTwo"] = two.distanceTwo.expression
                    else:
                        da = adsk.fusion.DistanceAndAngleChamferEdgeSet.cast(es)
                        if da:
                            set_entry["chamferType"] = "DistanceAndAngle"
                            set_entry["distance"] = da.distance.expression
                            set_entry["angle"] = da.angle.expression
                        else:
                            # Fallback: try generic distance property
                            try:
                                set_entry["distance"] = es.distance.expression
                            except:
                                pass

                sets_info.append(set_entry)
            info["edgeSets"] = sets_info
            info["edgeCount"] = total_edges
        except:
            pass

    # Edge sets need rollTo (BRep-dependent)
    if design:
        try:
            with _roll_to_feature(chamfer, design):
                _capture_edge_sets()
        except:
            _capture_edge_sets()
    else:
        _capture_edge_sets()

    info["bodies"] = [b.name for b in chamfer.bodies]

    return info


# ── Fillet ──

def _capture_fillet(fillet, design=None):
    """Capture a FilletFeature with edge vertex positions."""
    info = {"type": "Fillet", "name": fillet.name}

    def _capture_edge_sets():
        try:
            edge_sets = fillet.edgeSets
            sets_info = []
            total_edges = 0
            for si in range(edge_sets.count):
                es = edge_sets.item(si)
                set_entry = {
                    "radius": es.radius.expression,
                    "edges": _capture_edge_vertices(es.edges),
                }
                total_edges += len(set_entry["edges"])
                sets_info.append(set_entry)
            info["edgeSets"] = sets_info
            info["radii"] = [s["radius"] for s in sets_info]
            info["edgeCount"] = total_edges
        except:
            pass

    # Edge sets need rollTo (BRep-dependent)
    if design:
        try:
            with _roll_to_feature(fillet, design):
                _capture_edge_sets()
        except:
            _capture_edge_sets()
    else:
        _capture_edge_sets()

    info["bodies"] = [b.name for b in fillet.bodies]

    return info


# ── Sweep ──

def _capture_sweep(sweep, design):
    """Capture a SweepFeature with profile, path, and extent details."""
    info = {"type": "Sweep", "name": sweep.name}

    op_map = {
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation: "NewBody",
        adsk.fusion.FeatureOperations.CutFeatureOperation: "Cut",
        adsk.fusion.FeatureOperations.JoinFeatureOperation: "Join",
        adsk.fusion.FeatureOperations.IntersectFeatureOperation: "Intersect",
    }
    info["operation"] = op_map.get(sweep.operation, str(sweep.operation))

    # Orientation
    orient_map = {
        adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType: "Perpendicular",
        adsk.fusion.SweepOrientationTypes.ParallelOrientationType: "Parallel",
    }
    try:
        info["orientation"] = orient_map.get(sweep.orientation, str(sweep.orientation))
    except:
        pass

    # Taper / twist / direction (accessible without rollTo)
    try:
        if sweep.taperAngle:
            info["taperAngle"] = sweep.taperAngle.expression
    except:
        pass

    try:
        if sweep.twistAngle:
            info["twistAngle"] = sweep.twistAngle.expression
    except:
        pass

    try:
        info["isDirectionFlipped"] = sweep.isDirectionFlipped
    except:
        pass

    # BRep-dependent properties need rollTo (including distances)
    try:
        with _roll_to_feature(sweep, design):
            # Profile → sketch name + profile index
            # profile can be a single Profile or an ObjectCollection of Profiles
            try:
                profile = sweep.profile
                p = adsk.fusion.Profile.cast(profile)
                if not p:
                    coll = adsk.core.ObjectCollection.cast(profile)
                    if coll and coll.count > 0:
                        info["profileCollectionCount"] = coll.count
                        # Capture all profile indices
                        first_p = adsk.fusion.Profile.cast(coll.item(0))
                        if first_p:
                            sk = first_p.parentSketch
                            info["sketch"] = sk.name
                            indices = []
                            for pi in range(coll.count):
                                cp = adsk.fusion.Profile.cast(coll.item(pi))
                                if cp:
                                    idx = _match_profile_index_from_profile(cp, sk, info)
                                    if idx is not None:
                                        indices.append(idx)
                            if indices:
                                info["profileIndices"] = indices
                                # Store profile bounding box dims for runtime matching
                                pdims = []
                                for pi2 in range(coll.count):
                                    cp2 = adsk.fusion.Profile.cast(coll.item(pi2))
                                    if cp2:
                                        try:
                                            bb = cp2.boundingBox
                                            pdims.append([
                                                round(bb.maxPoint.x - bb.minPoint.x, 4),
                                                round(bb.maxPoint.y - bb.minPoint.y, 4),
                                            ])
                                        except:
                                            pass
                                if pdims:
                                    info["profileDims"] = pdims
                        p = None  # already handled
                if p:
                    sk = p.parentSketch
                    info["sketch"] = sk.name
                    _match_profile_index_from_profile(p, sk, info)
                    try:
                        bb = p.boundingBox
                        info["profileDims"] = [[
                            round(bb.maxPoint.x - bb.minPoint.x, 4),
                            round(bb.maxPoint.y - bb.minPoint.y, 4),
                        ]]
                    except:
                        pass
            except Exception as e:
                info["profileError"] = str(e)

            # Path
            try:
                path = sweep.path
                path_entities = []
                for pi in range(path.count):
                    pe = path.item(pi)
                    pe_info = {"isOpposedToEntity": pe.isOpposedToEntity}
                    curve = pe.entity
                    sk_curve = adsk.fusion.SketchCurve.cast(curve)
                    if sk_curve:
                        pe_info["source"] = "SketchCurve"
                        pe_info["parentSketch"] = sk_curve.parentSketch.name
                        pe_info["curveType"] = type(sk_curve).__name__
                        # Capture geometry for lines/arcs
                        line = adsk.fusion.SketchLine.cast(sk_curve)
                        if line:
                            pe_info["start"] = [round(line.startSketchPoint.geometry.x, 4),
                                                round(line.startSketchPoint.geometry.y, 4)]
                            pe_info["end"] = [round(line.endSketchPoint.geometry.x, 4),
                                              round(line.endSketchPoint.geometry.y, 4)]
                        arc = adsk.fusion.SketchArc.cast(sk_curve)
                        if arc:
                            pe_info["center"] = [round(arc.centerSketchPoint.geometry.x, 4),
                                                 round(arc.centerSketchPoint.geometry.y, 4)]
                            pe_info["radius"] = round(arc.radius, 4)
                    else:
                        edge = adsk.fusion.BRepEdge.cast(curve)
                        if edge:
                            pe_info["source"] = "BRepEdge"
                            try:
                                pe_info["body"] = edge.body.name
                            except:
                                pass
                            try:
                                sv = edge.startVertex.geometry
                                ev = edge.endVertex.geometry
                                pe_info["startVertex"] = [round(sv.x, 4), round(sv.y, 4), round(sv.z, 4)]
                                pe_info["endVertex"] = [round(ev.x, 4), round(ev.y, 4), round(ev.z, 4)]
                            except:
                                pass
                            pe_info["curveType"] = type(edge.geometry).__name__
                        else:
                            pe_info["source"] = "Unknown"
                            pe_info["objectType"] = curve.objectType if hasattr(curve, 'objectType') else str(type(curve))
                    path_entities.append(pe_info)
                info["path"] = path_entities
            except Exception as e:
                info["pathError"] = str(e)

            # Participant bodies
            try:
                if sweep.participantBodies:
                    info["participantBodies"] = [b.name for b in sweep.participantBodies]
            except:
                pass

            # Distances (0-1 fractions of path length)
            for attr, key in [("distanceOne", "distanceOne"), ("distanceTwo", "distanceTwo")]:
                try:
                    val = getattr(sweep, attr)
                    if val:
                        info[key] = val.expression
                except Exception as e:
                    info[key + "Error"] = str(e)

            # Guide rail
            try:
                gr = sweep.guideRail
                if gr:
                    info["hasGuideRail"] = True
                else:
                    info["hasGuideRail"] = False
            except:
                pass
    except Exception as e:
        info["rollToError"] = str(e)

    # Bodies (accessible without rollTo)
    info["bodies"] = [b.name for b in sweep.bodies]

    return info


def _match_profile_index_from_profile(profile, sk, info):
    """Match a single Profile's bounding box to its sketch profiles. Returns matched index or None."""
    try:
        ext_bb = profile.boundingBox
        ext_min = (round(ext_bb.minPoint.x, 3), round(ext_bb.minPoint.y, 3))
        ext_max = (round(ext_bb.maxPoint.x, 3), round(ext_bb.maxPoint.y, 3))
        info["profileCount"] = sk.profiles.count
        best_idx = 0
        best_dist = float('inf')
        for pi in range(sk.profiles.count):
            sp = sk.profiles.item(pi)
            sp_bb = sp.boundingBox
            sp_min = (round(sp_bb.minPoint.x, 3), round(sp_bb.minPoint.y, 3))
            sp_max = (round(sp_bb.maxPoint.x, 3), round(sp_bb.maxPoint.y, 3))
            dist = (abs(sp_min[0] - ext_min[0]) + abs(sp_min[1] - ext_min[1])
                    + abs(sp_max[0] - ext_max[0]) + abs(sp_max[1] - ext_max[1]))
            if dist < best_dist:
                best_dist = dist
                best_idx = pi
        info["profileIndex"] = best_idx
        return best_idx
    except:
        return None


# ── Split Body ──

def _capture_split_body(split, design):
    """Capture a SplitBodyFeature."""
    info = {"type": "SplitBody", "name": split.name}

    try:
        info["isSplittingToolExtended"] = split.isSplittingToolExtended
    except:
        pass

    # splittingTool needs rollTo (BRep-dependent)
    try:
        with _roll_to_feature(split, design):
            try:
                tool = split.splittingTool
                cp = adsk.fusion.ConstructionPlane.cast(tool)
                if cp:
                    info["splitTool"] = {"type": "ConstructionPlane", "name": cp.name}
                else:
                    face = adsk.fusion.BRepFace.cast(tool)
                    if face:
                        info["splitTool"] = {"type": "BRepFace", "body": face.body.name}
                        try:
                            eva = face.evaluator
                            ok, pt, norm = eva.getNormalAtPoint(face.pointOnFace)
                            if ok:
                                info["splitTool"]["normal"] = [round(norm.x, 4), round(norm.y, 4), round(norm.z, 4)]
                        except:
                            pass
                    else:
                        body = adsk.fusion.BRepBody.cast(tool)
                        if body:
                            info["splitTool"] = {"type": "BRepBody", "name": body.name}
                        else:
                            info["splitTool"] = {"type": "Unknown", "objectType": tool.objectType if hasattr(tool, 'objectType') else str(type(tool))}
            except Exception as e:
                info["splitToolError"] = str(e)

            # Input bodies being split (can be multiple)
            try:
                sb = split.splitBodies
                if sb.count == 1:
                    info["inputBody"] = sb.item(0).name
                else:
                    info["inputBodies"] = [sb.item(i).name for i in range(sb.count)]
                    info["inputBody"] = sb.item(0).name  # backwards compat
            except:
                pass
            # Output bodies read below after exiting edit mode
            pass
    except Exception as e:
        info["rollToError"] = str(e)

    # Read output bodies with marker AFTER the split (not in edit mode).
    # rollTo(True) is edit mode — split not yet applied. Set markerPosition
    # to just after the feature to see the result.
    if "bodies" not in info:
        try:
            tl = design.timeline
            tlo = split.timelineObject
            tl.markerPosition = tlo.index + 1
            comp = split.parentComponent
            # Sort by (-volume, bbox.min) for deterministic order among
            # equal-volume mirror copies — emitter uses the same sort key.
            body_keys = []
            for i in range(comp.bRepBodies.count):
                b = comp.bRepBodies.item(i)
                try:
                    bb = b.boundingBox
                    key = (-b.volume,
                           round(bb.minPoint.x, 4),
                           round(bb.minPoint.y, 4),
                           round(bb.minPoint.z, 4))
                except:
                    key = (-b.volume, 0, 0, 0)
                body_keys.append((b.name, key))
            body_keys.sort(key=lambda x: x[1])
            info["bodies"] = [name for name, key in body_keys]
            # Store volume+bbox for each body so the generator can use
            # distance-based matching instead of relying on sort order.
            body_geo = {}
            for i in range(comp.bRepBodies.count):
                b = comp.bRepBodies.item(i)
                try:
                    bb = b.boundingBox
                    body_geo[b.name] = {
                        "volume": round(b.volume, 4),
                        "bbMin": [round(bb.minPoint.x, 4), round(bb.minPoint.y, 4), round(bb.minPoint.z, 4)],
                        "bbMax": [round(bb.maxPoint.x, 4), round(bb.maxPoint.y, 4), round(bb.maxPoint.z, 4)],
                    }
                except:
                    body_geo[b.name] = {"volume": round(b.volume, 4), "bbMin": [0,0,0], "bbMax": [0,0,0]}
            info["bodyGeo"] = body_geo
            tl.moveToEnd()
        except:
            info["bodies"] = []

    return info


# ── Remove ──

def _capture_remove(remove):
    """Capture a RemoveFeature. Body name is parsed from the feature name."""
    info = {"type": "Remove", "name": remove.name}

    # Fusion names RemoveFeatures as "RemoveBody-<BodyName>"
    # The removed body is no longer accessible, but the feature name encodes it
    try:
        name = remove.name
        if "RemoveBody-" in name:
            info["removedBody"] = name.split("RemoveBody-", 1)[1]
        elif name.startswith("Remove"):
            info["removedBody"] = name[len("Remove"):].strip()
    except:
        pass

    return info
