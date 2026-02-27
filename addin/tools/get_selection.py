"""
Get Selection Tool

Read the user's current selection in Fusion 360 and return structured info
about each selected entity (bodies, faces, edges, occurrences, features, etc.).
"""

import traceback
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register
import adsk.core
import adsk.fusion

from ._capture_helpers import (
    _capture_sketch as _capture_sketch_full,
    _capture_extrude,
    _capture_combine,
    _capture_mirror,
    _capture_rectangular_pattern,
    _capture_move,
    _capture_chamfer,
    _capture_fillet,
    _capture_construction_plane as _capture_construction_plane_full,
)

app = adsk.core.Application.get()


def _round3(vals):
    return [round(v, 4) for v in vals]


def _bounding_box(bb):
    return {
        "min": _round3([bb.minPoint.x, bb.minPoint.y, bb.minPoint.z]),
        "max": _round3([bb.maxPoint.x, bb.maxPoint.y, bb.maxPoint.z]),
    }


def _capture_body(body):
    """Extract info from a BRepBody."""
    info = {"type": "BRepBody", "name": body.name}
    try:
        info["parentComponent"] = body.parentComponent.name
    except:
        pass
    try:
        info["volume"] = round(body.volume, 4)
    except:
        pass
    try:
        info["area"] = round(body.area, 4)
    except:
        pass
    try:
        info["boundingBox"] = _bounding_box(body.boundingBox)
    except:
        pass
    try:
        info["entityToken"] = body.entityToken
    except:
        pass
    return info


def _capture_face(face):
    """Extract info from a BRepFace."""
    info = {"type": "BRepFace"}
    try:
        info["parentBody"] = face.body.name
    except:
        pass

    # Geometry type
    geom = face.geometry
    geom_types = {
        adsk.core.Plane: "Plane",
        adsk.core.Cylinder: "Cylinder",
        adsk.core.Cone: "Cone",
        adsk.core.Sphere: "Sphere",
        adsk.core.Torus: "Torus",
    }
    info["geometryType"] = "Spline"
    for cls, name in geom_types.items():
        if isinstance(geom, cls):
            info["geometryType"] = name
            break

    # Plane-specific: normal + origin
    if isinstance(geom, adsk.core.Plane):
        try:
            info["normal"] = _round3([geom.normal.x, geom.normal.y, geom.normal.z])
            info["origin"] = _round3([geom.origin.x, geom.origin.y, geom.origin.z])
        except:
            pass
    # Cylinder-specific: radius
    elif isinstance(geom, adsk.core.Cylinder):
        try:
            info["radius"] = round(geom.radius, 4)
        except:
            pass

    try:
        info["area"] = round(face.area, 4)
    except:
        pass
    try:
        info["centroid"] = _round3([face.centroid.x, face.centroid.y, face.centroid.z])
    except:
        pass
    try:
        info["entityToken"] = face.entityToken
    except:
        pass
    return info


def _capture_edge(edge):
    """Extract info from a BRepEdge."""
    info = {"type": "BRepEdge"}
    try:
        info["parentBody"] = edge.body.name
    except:
        pass

    geom = edge.geometry
    geom_types = {
        adsk.core.Line3D: "Line",
        adsk.core.Circle3D: "Circle",
        adsk.core.Arc3D: "Arc",
        adsk.core.Ellipse3D: "Ellipse",
        adsk.core.EllipticalArc3D: "EllipticalArc",
    }
    info["geometryType"] = "Spline"
    for cls, name in geom_types.items():
        if isinstance(geom, cls):
            info["geometryType"] = name
            break

    try:
        info["length"] = round(edge.length, 4)
    except:
        pass
    try:
        info["entityToken"] = edge.entityToken
    except:
        pass
    return info


def _capture_occurrence(occ):
    """Extract info from an Occurrence."""
    info = {"type": "Occurrence", "name": occ.name}
    try:
        info["fullPathName"] = occ.fullPathName
    except:
        pass
    try:
        info["component"] = occ.component.name
    except:
        pass
    try:
        info["bodyCount"] = occ.component.bRepBodies.count
    except:
        pass
    try:
        info["boundingBox"] = _bounding_box(occ.boundingBox)
    except:
        pass
    return info


def _capture_timeline_object(tl_obj):
    """Extract info from a TimelineObject."""
    info = {"type": "TimelineObject"}
    try:
        info["name"] = tl_obj.entity.name
    except:
        pass
    try:
        info["index"] = tl_obj.index
    except:
        pass
    try:
        info["featureType"] = tl_obj.entity.objectType.split("::")[-1]
    except:
        pass
    try:
        info["isSuppressed"] = tl_obj.isSuppressed
    except:
        pass
    try:
        info["healthState"] = str(tl_obj.healthState)
    except:
        pass
    return info


def _capture_sketch_entity(entity):
    """Extract info from a sketch entity."""
    info = {"type": "SketchEntity"}
    try:
        info["parentSketch"] = entity.parentSketch.name
    except:
        pass
    try:
        info["entityType"] = type(entity).__name__
    except:
        pass
    try:
        info["boundingBox"] = _bounding_box(entity.boundingBox)
    except:
        pass
    return info


def _capture_entity(entity):
    """Route entity to the appropriate capture function."""
    body = adsk.fusion.BRepBody.cast(entity)
    if body:
        return _capture_body(body)

    face = adsk.fusion.BRepFace.cast(entity)
    if face:
        return _capture_face(face)

    edge = adsk.fusion.BRepEdge.cast(entity)
    if edge:
        return _capture_edge(edge)

    occ = adsk.fusion.Occurrence.cast(entity)
    if occ:
        return _capture_occurrence(occ)

    cp = adsk.fusion.ConstructionPlane.cast(entity)
    if cp:
        return _capture_construction_plane_full(cp)

    # Feature types — rich detail via shared helpers
    sk = adsk.fusion.Sketch.cast(entity)
    if sk:
        return _capture_sketch_full(sk)

    ext = adsk.fusion.ExtrudeFeature.cast(entity)
    if ext:
        return _capture_extrude(ext, None, None)

    comb = adsk.fusion.CombineFeature.cast(entity)
    if comb:
        return _capture_combine(comb, None, None)

    mir = adsk.fusion.MirrorFeature.cast(entity)
    if mir:
        return _capture_mirror(mir)

    pat = adsk.fusion.RectangularPatternFeature.cast(entity)
    if pat:
        return _capture_rectangular_pattern(pat)

    mv = adsk.fusion.MoveFeature.cast(entity)
    if mv:
        return _capture_move(mv)

    chamfer = adsk.fusion.ChamferFeature.cast(entity)
    if chamfer:
        return _capture_chamfer(chamfer)

    fillet = adsk.fusion.FilletFeature.cast(entity)
    if fillet:
        return _capture_fillet(fillet)

    tl_obj = adsk.fusion.TimelineObject.cast(entity)
    if tl_obj:
        return _capture_timeline_object(tl_obj)

    # Sketch entities (lines, arcs, circles, etc.)
    sk_entity = adsk.fusion.SketchEntity.cast(entity)
    if sk_entity:
        return _capture_sketch_entity(sk_entity)

    # Fallback
    info = {"type": entity.objectType.split("::")[-1] if hasattr(entity, 'objectType') else "Unknown"}
    try:
        info["name"] = entity.name
    except:
        pass
    return info


def handler() -> dict:
    """Read the current UI selection and return structured info."""

    try:
        ui = app.userInterface
        sels = ui.activeSelections

        selections = []
        for i in range(sels.count):
            sel = sels.item(i)
            entity = sel.entity
            selections.append(_capture_entity(entity))

        result = {
            "selectionCount": len(selections),
            "selections": selections,
        }

        return {
            "content": [{"type": "text", "text": __import__('json').dumps(result, indent=2)}],
            "isError": False,
            "message": f"{len(selections)} entity(s) selected"
        }

    except Exception as e:
        app.log(f"get_selection error: {e}\n{traceback.format_exc()}")
        return {
            "content": [{"type": "text", "text": f"Error: {e}\n{traceback.format_exc()}"}],
            "isError": True,
            "message": "get_selection failed"
        }


# Tool definition

TOOL_DESCRIPTION = \
"""Read the user's current selection in the Fusion 360 UI.

Returns structured info for each selected entity: bodies (name, volume, bounding box), faces (geometry type, normal, area), edges (geometry type, length), occurrences, timeline objects, sketch entities, construction planes, and full feature details (Sketch with curves/dimensions/constraints, Extrude with operation/distance/sketch, Combine with target/tool bodies, Mirror, Pattern, Move, Chamfer, Fillet).

Use this when the user says "what is this?" or "make this thicker" — read their selection to understand what they're pointing at."""

tool = Tool.create_simple(
    name="get_selection",
    description=TOOL_DESCRIPTION
).strict_schema()

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
