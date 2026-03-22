"""
Check Connectivity Tool

Detect disconnected body clusters in the design. A valid piece of furniture
should be a single connected cluster — all structural bodies touching or
overlapping in 3D space. Joinery void bodies (DM_*, domino loose tenons)
are excluded from the check since they're cutting tools, not structure.
"""

import traceback
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register
import adsk.core
import adsk.fusion

app = adsk.core.Application.get()

TOL_CM = 0.05  # 0.5mm tolerance for bounding-box adjacency


def _collect_bodies_with_bb(root_comp):
    """Collect all bodies with world-space bounding boxes."""
    bodies = []

    def _add(body, occ=None):
        bb = body.boundingBox
        if not bb:
            return
        mn = bb.minPoint
        mx = bb.maxPoint
        bodies.append({
            "name": body.name,
            "min": [mn.x, mn.y, mn.z],
            "max": [mx.x, mx.y, mx.z],
        })

    # Root bodies
    for i in range(root_comp.bRepBodies.count):
        _add(root_comp.bRepBodies.item(i))

    # Component bodies (occurrence transforms are applied by Fusion
    # when accessing body.boundingBox through an occurrence)
    for occ in root_comp.allOccurrences:
        comp = occ.component
        for i in range(comp.bRepBodies.count):
            b = comp.bRepBodies.item(i)
            # Get the proxy body so bounding box is in world space
            proxy = b.createForAssemblyContext(occ)
            _add(proxy, occ)

    return bodies


def _touches(a, b):
    """Do two axis-aligned bounding boxes touch or overlap (within tolerance)?"""
    for axis in range(3):
        if a["max"][axis] + TOL_CM < b["min"][axis]:
            return False
        if b["max"][axis] + TOL_CM < a["min"][axis]:
            return False
    return True


def _find_clusters(bodies, exclude_prefixes):
    """Union-Find clustering on bounding-box adjacency."""
    # Filter structural bodies
    structural = []
    for i, b in enumerate(bodies):
        skip = False
        for prefix in exclude_prefixes:
            if b["name"].startswith(prefix):
                skip = True
                break
        if not skip:
            structural.append((i, b))

    # Union-Find
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

    # Check all pairs
    for i_idx in range(len(structural)):
        idx_a, a = structural[i_idx]
        for j_idx in range(i_idx + 1, len(structural)):
            idx_b, b = structural[j_idx]
            if _touches(a, b):
                union(idx_a, idx_b)

    # Collect clusters
    clusters = {}
    for idx, b in structural:
        root = find(idx)
        clusters.setdefault(root, []).append(b["name"])

    return clusters, len(structural)


def handler(exclude_prefixes: list = None) -> dict:
    """Check body connectivity — all structural bodies should form one cluster."""

    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return {
                "content": [{"type": "text", "text": "No active design"}],
                "isError": True,
                "message": "No active design"
            }

        # Default: exclude joinery void bodies
        prefixes = exclude_prefixes or ["DM_"]

        bodies = _collect_bodies_with_bb(design.rootComponent)

        if len(bodies) < 2:
            import json
            return {
                "content": [{"type": "text", "text": json.dumps({
                    "clusterCount": 1 if bodies else 0,
                    "structuralBodyCount": len(bodies),
                    "totalBodyCount": len(bodies),
                    "clusters": [{"id": 0, "bodyCount": len(bodies),
                                  "bodies": [b["name"] for b in bodies]}] if bodies else [],
                    "connected": True,
                }, indent=2)}],
                "isError": False,
                "message": f"{len(bodies)} body(s) — trivially connected"
            }

        clusters, structural_count = _find_clusters(bodies, prefixes)

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
            "clusters": cluster_list,
        }

        if connected:
            msg = f"Connected: {structural_count} structural bodies form 1 cluster"
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
"""Check that all structural bodies in the design form a single connected cluster.

Uses bounding-box adjacency (0.5mm tolerance) and union-find clustering.
A valid piece of furniture should have exactly 1 cluster — all parts
physically touching or overlapping. Multiple clusters indicate floating
or disconnected parts that lack mechanical joinery.

Joinery void bodies (DM_* prefix by default) are excluded since they are
cutting tools, not structural elements."""

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
)

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
