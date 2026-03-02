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

def _capture_sketch_plane(sk):
    """Return structured plane info for a sketch's reference plane."""
    try:
        ref = sk.referencePlane
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
    plane = _capture_sketch_plane(sk)
    if plane:
        info["plane"] = plane

    # Sketch coordinate system (for BRepFace → construction plane conversion)
    if plane and plane.get("type") == "BRepFace":
        try:
            info["sketchOrigin"] = [round(sk.origin.x, 4), round(sk.origin.y, 4), round(sk.origin.z, 4)]
            info["sketchXDir"] = [round(sk.xDirection.x, 6), round(sk.xDirection.y, 6), round(sk.xDirection.z, 6)]
            info["sketchYDir"] = [round(sk.yDirection.x, 6), round(sk.yDirection.y, 6), round(sk.yDirection.z, 6)]
        except:
            pass

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

    # Restore timeline after projection capture
    if _rolled:
        try:
            design.timeline.moveToEnd()
        except:
            pass

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
    elif "sketchError" not in info:
        info["sketchError"] = "no sketch found (all strategies failed)"

    body_names = [b.name for b in ext.bodies]

    # If bodies list is empty (consumed by downstream combine/join), infer the
    # body name by scanning downstream Combine features for toolBodies references.
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

    # Strategy: walk timeline backwards
    if not sk_found:
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
    except Exception as e:
        info["sketchError"] = f"profile access: {e}"

    return sk_found


def _match_profile_index(ext, sk_found, info):
    """Match extrude profile bounding box to sketch profiles."""
    try:
        profile = ext.profile
        profiles_coll = adsk.core.ObjectCollection.cast(profile)
        ext_prof = profiles_coll.item(0) if profiles_coll else adsk.fusion.Profile.cast(profile)
        if ext_prof:
            ext_bb = ext_prof.boundingBox
            ext_min = (round(ext_bb.minPoint.x, 3), round(ext_bb.minPoint.y, 3))
            ext_max = (round(ext_bb.maxPoint.x, 3), round(ext_bb.maxPoint.y, 3))
            info["profileCount"] = sk_found.profiles.count
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
            info["profileIndex"] = best_idx
    except:
        pass


# ── Construction Plane ──

def _capture_construction_plane(cp):
    """Capture a ConstructionPlane feature."""
    info = {"type": "ConstructionPlane", "name": cp.name}

    try:
        defn = cp.definition
        offset_def = adsk.fusion.ConstructionPlaneOffsetDefinition.cast(defn)
        if offset_def:
            info["definitionType"] = "Offset"
            info["offset"] = offset_def.offset.expression
            base = offset_def.planarEntity
            bcp = adsk.fusion.ConstructionPlane.cast(base)
            if bcp:
                info["basePlane"] = bcp.name
            else:
                info["basePlane"] = str(base.objectType)
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

    # Output bodies (accessible without rollTo)
    info["bodies"] = [b.name for b in mir.bodies]

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
            try:
                line = ca.geometry
                info["directionOne"] = [round(line.direction.x, 6), round(line.direction.y, 6), round(line.direction.z, 6)]
            except:
                pass
        else:
            try:
                edge = adsk.fusion.BRepEdge.cast(axis)
                if edge:
                    geom = edge.geometry
                    line = adsk.core.Line3D.cast(geom)
                    if line:
                        info["directionOne"] = [round(line.direction.x, 6), round(line.direction.y, 6), round(line.direction.z, 6)]
            except:
                pass
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

    if design:
        try:
            with _roll_to_feature(pat, design):
                _try_inputs()
        except:
            _try_inputs()
    else:
        _try_inputs()

    info["bodies"] = [b.name for b in pat.bodies]

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

    # If body access failed, retry with rollTo
    if ("targetBodyError" in info or "toolBodiesError" in info) and design:
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
    """Capture vertex positions for a collection of edges."""
    edge_list = []
    for ei in range(edges.count):
        e = edges.item(ei)
        try:
            sv = e.startVertex.geometry
            ev = e.endVertex.geometry
            edge_info = {
                "start": [round(sv.x, 4), round(sv.y, 4), round(sv.z, 4)],
                "end": [round(ev.x, 4), round(ev.y, 4), round(ev.z, 4)],
            }
            # Body name for matching
            try:
                edge_info["body"] = e.body.name
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

            # Output bodies (also BRep-dependent, need rollTo)
            try:
                info["bodies"] = [b.name for b in split.splitBodies]
            except:
                info["bodies"] = []
    except Exception as e:
        info["rollToError"] = str(e)

    if "bodies" not in info:
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
