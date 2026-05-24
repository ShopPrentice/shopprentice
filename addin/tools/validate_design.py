"""
Validate Design Tool

Single-call structural validation that runs all checks:
1. Connectivity — all structural bodies form 1 connected cluster
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

TOL_CM = 0.05  # 0.5mm tolerance for bounding-box adjacency


# ── Connectivity Check ───────────────────────────────────────────────

def _collect_bodies_with_bb(root_comp):
    """Collect all bodies with world-space bounding boxes."""
    bodies = []
    for i in range(root_comp.bRepBodies.count):
        b = root_comp.bRepBodies.item(i)
        bb = b.boundingBox
        if bb:
            bodies.append({
                "name": b.name,
                "min": [bb.minPoint.x, bb.minPoint.y, bb.minPoint.z],
                "max": [bb.maxPoint.x, bb.maxPoint.y, bb.maxPoint.z],
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
                })
    return bodies


def _touches(a, b):
    for axis in range(3):
        if a["max"][axis] + TOL_CM < b["min"][axis]:
            return False
        if b["max"][axis] + TOL_CM < a["min"][axis]:
            return False
    return True


def _check_connectivity(bodies, exclude_prefixes):
    structural = []
    for i, b in enumerate(bodies):
        skip = any(b["name"].startswith(p) for p in exclude_prefixes)
        if not skip:
            structural.append((i, b))

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

    for i_idx in range(len(structural)):
        idx_a, a = structural[i_idx]
        for j_idx in range(i_idx + 1, len(structural)):
            idx_b, b = structural[j_idx]
            if _touches(a, b):
                union(idx_a, idx_b)

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

        # Filter: exclude any interference involving a void body
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

def handler(exclude_prefixes: list = None) -> dict:
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

        # Run both checks
        bodies = _collect_bodies_with_bb(root)
        connectivity = _check_connectivity(bodies, prefixes)
        interference = _check_interference(root, prefixes)

        passed = connectivity["connected"] and interference["realCount"] == 0

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

        # Build summary message
        parts = []
        if connectivity["connected"]:
            parts.append(f"connectivity OK ({connectivity['structuralBodyCount']} bodies, 1 cluster)")
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
   (bounding-box adjacency, 0.5mm tolerance)
2. **Interference** — no unintended body overlaps (excludes void-on-void
   pairs like joinery ghost bodies)
3. **Dependency tree** — if model.json exists next to the script, validates:
   single origin root, sketch origin enforcement (non-root sketches must
   not dimension from sk.originPoint), bodies in components.
   Completeness check is advisory (printed but doesn't affect pass/fail).

Returns a single pass/fail result. A valid piece passes all checks.
Run after EVERY phase (structure, joinery, details) — not just at the end."""

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
)

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
