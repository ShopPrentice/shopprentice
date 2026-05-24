"""Body geometry and edge vertex capture."""

import adsk.core
import adsk.fusion


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
