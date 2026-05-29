"""
Validate Design Tool

Single-call structural validation that runs all checks:
1. Connectivity — all structural bodies form 1 connected cluster via face contact
2. Interference — no unintended body overlaps (excludes void-on-void)

Returns a combined pass/fail result with details from each check.
"""

import traceback
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register
import adsk.core
import adsk.fusion

app = adsk.core.Application.get()

TOL_CM = 0.05  # 0.5mm tolerance for face coplanarity
DEFAULT_MIN_CONTACT_CM2 = 1.0


# ── Connectivity Check ───────────────────────────────────────────────

def _collect_bodies(root_comp):
    """Collect all bodies with world-space bounding boxes and body references."""
    bodies = []
    for i in range(root_comp.bRepBodies.count):
        b = root_comp.bRepBodies.item(i)
        bb = b.boundingBox
        if bb:
            bodies.append({
                "name": b.name,
                "min": [bb.minPoint.x, bb.minPoint.y, bb.minPoint.z],
                "max": [bb.maxPoint.x, bb.maxPoint.y, bb.maxPoint.z],
                "body": b,
            })
    for occ in root_comp.allOccurrences:
        comp = occ.component
        for i in range(comp.bRepBodies.count):
            b = comp.bRepBodies.item(i)
            proxy = b.createForAssemblyContext(occ)
            bb = proxy.boundingBox
            if bb:
                bodies.append({
                    "name": b.name,
                    "min": [bb.minPoint.x, bb.minPoint.y, bb.minPoint.z],
                    "max": [bb.maxPoint.x, bb.maxPoint.y, bb.maxPoint.z],
                    "body": proxy,
                })
    return bodies


def _bb_touches(a, b):
    for axis in range(3):
        if a["max"][axis] + TOL_CM < b["min"][axis]:
            return False
        if b["max"][axis] + TOL_CM < a["min"][axis]:
            return False
    return True


def _planar_faces(body):
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


def _check_connectivity(bodies, exclude_prefixes, min_contact_cm2):
    structural = []
    for i, b in enumerate(bodies):
        skip = any(b["name"].startswith(p) for p in exclude_prefixes)
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

    cluster_list = []
    for _, members in sorted(clusters.items(), key=lambda x: -len(x[1])):
        cluster_list.append({"bodyCount": len(members), "bodies": members})

    return {
        "connected": len(clusters) == 1,
        "clusterCount": len(clusters),
        "structuralBodyCount": len(structural),
        "connections": connections,
        "weakConnections": weak,
        "clusters": cluster_list,
    }


# ── Interference Check ───────────────────────────────────────────────

def _check_interference(root_comp, exclude_prefixes):
    body_list = []
    for i in range(root_comp.bRepBodies.count):
        body_list.append(root_comp.bRepBodies.item(i))
    for occ in root_comp.allOccurrences:
        for i in range(occ.component.bRepBodies.count):
            body_list.append(occ.component.bRepBodies.item(i))

    if len(body_list) < 2:
        return {"interferenceCount": 0, "realCount": 0, "interferences": []}

    design = adsk.fusion.Design.cast(app.activeProduct)
    body_collection = adsk.core.ObjectCollection.create()
    for b in body_list:
        body_collection.add(b)

    interference_input = design.createInterferenceInput(body_collection)
    interference_results = design.analyzeInterference(interference_input)

    all_interferences = []
    real_interferences = []

    for i in range(interference_results.count):
        result = interference_results.item(i)
        entry = {}
        try:
            entry["body1"] = result.entityOne.name
        except Exception:
            entry["body1"] = "unknown"
        try:
            entry["body2"] = result.entityTwo.name
        except Exception:
            entry["body2"] = "unknown"
        try:
            entry["volume"] = round(result.interferenceBody.volume, 4)
        except Exception:
            pass
        all_interferences.append(entry)

        b1_void = any(entry["body1"].startswith(p) for p in exclude_prefixes)
        b2_void = any(entry["body2"].startswith(p) for p in exclude_prefixes)
        if not (b1_void or b2_void):
            real_interferences.append(entry)

    return {
        "interferenceCount": len(all_interferences),
        "realCount": len(real_interferences),
        "interferences": real_interferences,
    }


# ── Handler ──────────────────────────────────────────────────────────

def handler(exclude_prefixes: list = None, min_contact_cm2: float = None) -> dict:
    """Run all structural validation checks on the current design."""

    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return {
                "content": [{"type": "text", "text": "No active design"}],
                "isError": True,
                "message": "No active design"
            }

        root = design.rootComponent
        prefixes = exclude_prefixes or ["DM_"]
        min_area = min_contact_cm2 if min_contact_cm2 is not None else DEFAULT_MIN_CONTACT_CM2

        bodies = _collect_bodies(root)
        connectivity = _check_connectivity(bodies, prefixes, min_area)
        interference = _check_interference(root, prefixes)

        passed = (connectivity["connected"]
                  and not connectivity["weakConnections"]
                  and interference["realCount"] == 0)

        # Run dependency tree validation if model.json exists
        deps_result = None
        try:
            from helpers import sp
            import io, contextlib
            ctx = sp.DesignContext()
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                deps_passed = sp.validate_deps(ctx)
            deps_output = buf.getvalue()
            if deps_passed is not None:
                deps_result = {
                    "passed": deps_passed,
                    "output": deps_output.strip(),
                }
                if not deps_passed:
                    passed = False
        except Exception as de:
            deps_result = {"passed": None, "error": str(de)}

        import json
        result = {
            "passed": passed,
            "connectivity": connectivity,
            "interference": interference,
        }
        if deps_result is not None:
            result["deps"] = deps_result

        parts = []
        if connectivity["connected"] and not connectivity["weakConnections"]:
            parts.append(f"connectivity OK ({connectivity['structuralBodyCount']} bodies, 1 cluster)")
        elif connectivity["connected"]:
            parts.append(f"CONNECTIVITY WARN ({len(connectivity['weakConnections'])} weak connection(s))")
        else:
            parts.append(f"CONNECTIVITY FAIL ({connectivity['clusterCount']} clusters)")

        if interference["realCount"] == 0:
            parts.append("interference OK (0 real)")
        else:
            parts.append(f"INTERFERENCE FAIL ({interference['realCount']} real)")

        if deps_result is not None:
            if deps_result.get("passed"):
                parts.append("deps OK")
            elif deps_result.get("passed") is False:
                parts.append("DEPS FAIL")

        status = "PASSED" if passed else "FAILED"
        msg = f"{status}: {', '.join(parts)}"

        return {
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
            "isError": False,
            "message": msg
        }

    except Exception as e:
        app.log(f"validate_design error: {e}\n{traceback.format_exc()}")
        return {
            "content": [{"type": "text", "text": f"Error: {e}\n{traceback.format_exc()}"}],
            "isError": True,
            "message": "validate_design failed"
        }


TOOL_DESCRIPTION = \
"""Run all validation checks on the current design.

Combines three checks in a single call:
1. **Connectivity** — all structural bodies must form 1 connected cluster
   with sufficient face-to-face contact area. Edge-only or point-only
   contacts don't count. Connections below min_contact_cm2 are flagged weak.
2. **Interference** — no unintended body overlaps (excludes void-on-void
   pairs like joinery ghost bodies)
3. **Dependency tree** — if model.json exists next to the script, validates:
   single origin root, sketch origin enforcement (non-root sketches must
   not dimension from sk.originPoint), sketch traceability (every non-root
   sketch must project real reference geometry, use no Fix/Ground constraint,
   and be fully constrained relative to that reference — Fusion's solver is
   the judge; only fit-point spline interiors may stay free), bodies in
   components.
   Completeness check is advisory (printed but doesn't affect pass/fail).

Returns a single pass/fail result. Fails if disconnected, has weak
connections, or has interference. Run after EVERY phase."""

tool = Tool.create_simple(
    name="validate_design",
    description=TOOL_DESCRIPTION
).add_input_property(
    "exclude_prefixes",
    {
        "type": "array",
        "description": "Body name prefixes to exclude (default: [\"DM_\"]). "
                       "Joinery void bodies that aren't structural.",
        "items": {"type": "string"}
    }
).add_input_property(
    "min_contact_cm2",
    {
        "type": "number",
        "description": "Minimum face contact area in cm² for a connection to be "
                       "structurally sound (default: 1.0). Connections below this are "
                       "flagged as weak and cause the check to fail.",
    }
)

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
