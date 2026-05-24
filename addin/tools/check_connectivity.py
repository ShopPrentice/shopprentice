"""
Check Connectivity Tool

Detect disconnected body clusters in the design. A valid piece of furniture
should be a single connected cluster — all structural bodies with sufficient
face-to-face contact. Edge-only or point-only contacts don't count.
Joinery void bodies (DM_*, domino loose tenons) are excluded from the check.
"""

import traceback
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register
import adsk.core
import adsk.fusion

app = adsk.core.Application.get()

TOL_CM = 0.05  # 0.5mm tolerance for face coplanarity
DEFAULT_MIN_CONTACT_CM2 = 1.0  # minimum contact area for structural soundness


def _collect_bodies(root_comp):
    """Collect all bodies with world-space bounding boxes and body references."""
    bodies = []

    def _add(body):
        bb = body.boundingBox
        if not bb:
            return
        mn = bb.minPoint
        mx = bb.maxPoint
        bodies.append({
            "name": body.name,
            "min": [mn.x, mn.y, mn.z],
            "max": [mx.x, mx.y, mx.z],
            "body": body,
        })

    for i in range(root_comp.bRepBodies.count):
        _add(root_comp.bRepBodies.item(i))

    for occ in root_comp.allOccurrences:
        comp = occ.component
        for i in range(comp.bRepBodies.count):
            b = comp.bRepBodies.item(i)
            proxy = b.createForAssemblyContext(occ)
            _add(proxy)

    return bodies


def _bb_touches(a, b):
    """Quick bounding-box pre-filter (within tolerance)."""
    for axis in range(3):
        if a["max"][axis] + TOL_CM < b["min"][axis]:
            return False
        if b["max"][axis] + TOL_CM < a["min"][axis]:
            return False
    return True


def _planar_faces(body):
    """Extract planar faces with outward normals and bounding boxes."""
    result = []
    for i in range(body.faces.count):
        face = body.faces.item(i)
        if face.geometry.surfaceType != adsk.core.SurfaceTypes.PlaneSurfaceType:
            continue
        ok, normal = face.evaluator.getNormalAtPoint(face.pointOnFace)
        if not ok:
            continue
        bb = face.boundingBox
        if not bb:
            continue
        result.append({
            "normal": normal,
            "point": face.pointOnFace,
            "bb_min": [bb.minPoint.x, bb.minPoint.y, bb.minPoint.z],
            "bb_max": [bb.maxPoint.x, bb.maxPoint.y, bb.maxPoint.z],
            "area": face.area,
        })
    return result


def _contact_area(faces_a, faces_b, tol_cm):
    """Compute total planar face-to-face contact area between two sets of faces.

    Contact requires opposite normals, coplanarity within tolerance,
    and overlapping bounding boxes on the shared plane.
    """
    total = 0.0
    for fa in faces_a:
        na = fa["normal"]
        pa = fa["point"]
        a_min, a_max = fa["bb_min"], fa["bb_max"]

        for fb in faces_b:
            nb = fb["normal"]
            dot = na.x * nb.x + na.y * nb.y + na.z * nb.z
            if dot > -0.95:
                continue

            dx = fb["point"].x - pa.x
            dy = fb["point"].y - pa.y
            dz = fb["point"].z - pa.z
            dist = abs(dx * na.x + dy * na.y + dz * na.z)
            if dist > tol_cm:
                continue

            b_min, b_max = fb["bb_min"], fb["bb_max"]
            abs_nx, abs_ny, abs_nz = abs(na.x), abs(na.y), abs(na.z)

            if abs_nx >= abs_ny and abs_nx >= abs_nz:
                o1 = min(a_max[1], b_max[1]) - max(a_min[1], b_min[1])
                o2 = min(a_max[2], b_max[2]) - max(a_min[2], b_min[2])
            elif abs_ny >= abs_nx and abs_ny >= abs_nz:
                o1 = min(a_max[0], b_max[0]) - max(a_min[0], b_min[0])
                o2 = min(a_max[2], b_max[2]) - max(a_min[2], b_min[2])
            else:
                o1 = min(a_max[0], b_max[0]) - max(a_min[0], b_min[0])
                o2 = min(a_max[1], b_max[1]) - max(a_min[1], b_min[1])

            if o1 <= 0 or o2 <= 0:
                continue

            area = min(o1 * o2, fa["area"], fb["area"])
            total += area

    return total


def _find_clusters(bodies, exclude_prefixes, min_contact_cm2):
    """Union-Find clustering based on face-to-face contact area."""
    structural = []
    for i, b in enumerate(bodies):
        skip = False
        for prefix in exclude_prefixes:
            if b["name"].startswith(prefix):
                skip = True
                break
        if not skip:
            structural.append((i, b))

    faces_cache = {}
    for idx, b in structural:
        faces_cache[idx] = _planar_faces(b["body"])

    parent = list(range(len(bodies)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    connections = []
    weak = []

    for i_idx in range(len(structural)):
        idx_a, a = structural[i_idx]
        for j_idx in range(i_idx + 1, len(structural)):
            idx_b, b = structural[j_idx]

            if not _bb_touches(a, b):
                continue

            area = _contact_area(
                faces_cache[idx_a], faces_cache[idx_b], TOL_CM
            )

            if area > 0.01:
                union(idx_a, idx_b)
                conn = {
                    "bodyA": a["name"],
                    "bodyB": b["name"],
                    "contactArea": round(area, 2),
                }
                connections.append(conn)
                if area < min_contact_cm2:
                    weak.append(conn)

    clusters = {}
    for idx, b in structural:
        root = find(idx)
        clusters.setdefault(root, []).append(b["name"])

    return clusters, len(structural), connections, weak


def handler(exclude_prefixes: list = None, min_contact_cm2: float = None) -> dict:
    """Check body connectivity via face-to-face contact area."""

    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return {
                "content": [{"type": "text", "text": "No active design"}],
                "isError": True,
                "message": "No active design"
            }

        prefixes = exclude_prefixes or ["DM_"]
        min_area = min_contact_cm2 if min_contact_cm2 is not None else DEFAULT_MIN_CONTACT_CM2

        bodies = _collect_bodies(design.rootComponent)

        if len(bodies) < 2:
            import json
            return {
                "content": [{"type": "text", "text": json.dumps({
                    "clusterCount": 1 if bodies else 0,
                    "structuralBodyCount": len(bodies),
                    "totalBodyCount": len(bodies),
                    "clusters": [{"id": 0, "bodyCount": len(bodies),
                                  "bodies": [b["name"] for b in bodies]}] if bodies else [],
                    "connections": [],
                    "weakConnections": [],
                    "connected": True,
                }, indent=2)}],
                "isError": False,
                "message": f"{len(bodies)} body(s) — trivially connected"
            }

        clusters, structural_count, connections, weak = _find_clusters(
            bodies, prefixes, min_area
        )

        import json
        cluster_list = []
        for i, (root, members) in enumerate(
                sorted(clusters.items(), key=lambda x: -len(x[1]))):
            cluster_list.append({
                "id": i,
                "bodyCount": len(members),
                "bodies": members,
            })

        connected = len(clusters) == 1
        result = {
            "connected": connected,
            "clusterCount": len(clusters),
            "structuralBodyCount": structural_count,
            "totalBodyCount": len(bodies),
            "excludedPrefixes": prefixes,
            "minContactArea": min_area,
            "connections": connections,
            "weakConnections": weak,
            "clusters": cluster_list,
        }

        if connected and not weak:
            msg = f"Connected: {structural_count} structural bodies form 1 cluster"
        elif connected and weak:
            msg = (f"Connected: {structural_count} bodies, 1 cluster — "
                   f"WARNING: {len(weak)} weak connection(s) (< {min_area} cm²)")
        else:
            msg = (f"DISCONNECTED: {len(clusters)} clusters found among "
                   f"{structural_count} structural bodies")

        return {
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
            "isError": False,
            "message": msg
        }

    except Exception as e:
        app.log(f"check_connectivity error: {e}\n{traceback.format_exc()}")
        return {
            "content": [{"type": "text", "text": f"Error: {e}\n{traceback.format_exc()}"}],
            "isError": True,
            "message": "check_connectivity failed"
        }


# Tool definition

TOOL_DESCRIPTION = \
"""Check that all structural bodies form a single connected cluster via
face-to-face contact area analysis.

Uses bounding-box pre-filtering, then computes actual planar face contact
area for each body pair. Bodies must share coplanar, opposite-facing faces
with overlapping area to be considered connected. Edge-only or point-only
contacts do not count.

Connections below `min_contact_cm2` (default 1.0 cm²) are flagged as weak —
insufficient contact area for structural integrity.

A valid piece of furniture should have exactly 1 cluster with no weak
connections. Multiple clusters indicate disconnected parts; weak connections
indicate misaligned or undersized joints."""

tool = Tool.create_simple(
    name="check_connectivity",
    description=TOOL_DESCRIPTION
).add_input_property(
    "exclude_prefixes",
    {
        "type": "array",
        "description": "Body name prefixes to exclude from the check (default: [\"DM_\"]). "
                       "These are typically joinery void bodies that aren't structural.",
        "items": {"type": "string"}
    }
).add_input_property(
    "min_contact_cm2",
    {
        "type": "number",
        "description": "Minimum face contact area in cm² for a connection to be considered "
                       "structurally sound (default: 1.0). Connections below this threshold "
                       "are flagged as weak.",
    }
)

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
