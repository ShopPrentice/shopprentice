"""Construction plane and sketch plane capture."""

import adsk.core
import adsk.fusion

from ._common import _roll_to_feature


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
            try:
                pof = bf.pointOnFace
                result["pointOnFace"] = [round(pof.x, 4), round(pof.y, 4), round(pof.z, 4)]
            except:
                pass
            return result
    except:
        pass
    return None


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
            try:
                base = angle_def.planarEntity
                bcp = adsk.fusion.ConstructionPlane.cast(base)
                if bcp:
                    info["basePlane"] = bcp.name
                else:
                    info["basePlane"] = str(base.objectType)
            except:
                pass
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
