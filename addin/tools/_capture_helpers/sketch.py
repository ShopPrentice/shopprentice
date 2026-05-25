"""Sketch capture: full detail, summary, and entity identification."""

import adsk.core
import adsk.fusion

from .plane import _capture_sketch_plane


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

