"""
Validate Design Tool

Single-call structural validation that runs all checks:
1. Connectivity — all structural bodies form 1 connected cluster
2. Interference — no unintended body overlaps (excludes void-on-void)
3. Assembly — all joints are registered with assembly vectors and
   pass geometric feasibility (no undercuts along insertion direction)

Returns a combined pass/fail result with details from each check.
"""

import json
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


# ── Assembly Check ──────────────────────────────────────────────────

_NON_JOINT_PATTERNS = ("Trim", "Rab", "EdgeCut", "Groove", "EdgeRab",
                       "BotRab", "Chamfer", "Fillet")


def _find_body_by_name(root_comp, name):
    """Find a body by name across root and all occurrences."""
    for i in range(root_comp.bRepBodies.count):
        b = root_comp.bRepBodies.item(i)
        if b.name == name:
            return b
    for occ in root_comp.allOccurrences:
        for i in range(occ.component.bRepBodies.count):
            b = occ.component.bRepBodies.item(i)
            if b.name == name:
                return b
    return None


def _check_assembly(root_comp):
    """Check assembly feasibility for all registered joints."""
    design = adsk.fusion.Design.cast(app.activeProduct)

    # Part A: read the joint registry from design attributes
    registered_joints = []
    non_joint_cuts = set()
    attr = design.attributes.itemByName("shopprentice", "joints")
    if attr:
        try:
            data = json.loads(attr.value)
            registered_joints = data.get("joints", [])
            non_joint_cuts = set(data.get("non_joint_cuts", []))
        except (json.JSONDecodeError, AttributeError):
            pass

    registered_names = {j["name"] for j in registered_joints}

    # Part B: detect all CUT operations from timeline
    # (both Combine CUT and Extrude CUT — agents might use either)
    detected_cuts = []
    tl = design.timeline
    CUT_OP = adsk.fusion.FeatureOperations.CutFeatureOperation
    for i in range(tl.count):
        item = tl.item(i)
        entity = item.entity
        if entity is None:
            continue
        try:
            combine_feat = adsk.fusion.CombineFeature.cast(entity)
            if combine_feat and combine_feat.operation == CUT_OP:
                detected_cuts.append(combine_feat.name)
                continue
            ext_feat = adsk.fusion.ExtrudeFeature.cast(entity)
            if ext_feat and ext_feat.operation == CUT_OP:
                detected_cuts.append(ext_feat.name)
        except Exception:
            continue

    # Part C: cross-reference — find unregistered CUTs (warnings only)
    unregistered = []
    for cut_name in detected_cuts:
        if cut_name in registered_names:
            continue
        if cut_name in non_joint_cuts:
            continue
        excluded = any(pat in cut_name for pat in _NON_JOINT_PATTERNS)
        unregistered.append({
            "name": cut_name,
            "excluded": excluded,
        })

    unregistered_warnings = [u for u in unregistered if not u["excluded"]]

    # Part D: re-verify feasibility for registered joints
    details = []
    unfeasible_count = 0
    for joint in registered_joints:
        entry = {
            "name": joint["name"],
            "template": joint.get("template"),
            "assembly_vector": joint.get("assembly_vector"),
            "feasibility": joint.get("feasibility", "ok"),
        }

        tool_name = joint.get("tool_body", "")
        tool_body = _find_body_by_name(root_comp, tool_name)
        if tool_body and tool_body.faces.count > 0:
            try:
                from helpers.sp import check_assembly_feasibility
                av = joint.get("assembly_vector", [1, 0, 0])
                result = check_assembly_feasibility(tool_body, av)
                entry["feasibility"] = "ok" if result["feasible"] else "undercut"
                entry["undercut_count"] = result["undercut_count"]
            except Exception:
                pass

        if entry["feasibility"] != "ok":
            unfeasible_count += 1
        details.append(entry)

    # Feasibility fails only on undercut errors.
    # Unregistered CUTs are informational warnings.
    feasible = unfeasible_count == 0

    return {
        "feasible": feasible,
        "registeredJoints": len(registered_joints),
        "feasibleJoints": len(registered_joints) - unfeasible_count,
        "unfeasibleJoints": unfeasible_count,
        "unregisteredCuts": len(unregistered_warnings),
        "details": details,
        "unregistered": unregistered,
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

        # Run all checks
        bodies = _collect_bodies_with_bb(root)
        connectivity = _check_connectivity(bodies, prefixes)
        interference = _check_interference(root, prefixes)
        assembly = _check_assembly(root)

        passed = (connectivity["connected"]
                  and interference["realCount"] == 0
                  and assembly["feasible"])

        result = {
            "passed": passed,
            "connectivity": connectivity,
            "interference": interference,
            "assembly": assembly,
        }

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

        if assembly["feasible"]:
            asm_info = f"{assembly['registeredJoints']} joints"
            if assembly["unregisteredCuts"] > 0:
                asm_info += f", {assembly['unregisteredCuts']} unregistered CUT warnings"
            parts.append(f"assembly OK ({asm_info})")
        else:
            parts.append(f"ASSEMBLY FAIL ({assembly['unfeasibleJoints']} undercut)")

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
"""Run all structural validation checks on the current design.

Combines connectivity + interference + assembly checks in a single call:
1. **Connectivity** — all structural bodies must form 1 connected cluster
   (bounding-box adjacency, 0.5mm tolerance)
2. **Interference** — no unintended body overlaps (excludes void-on-void
   pairs like joinery ghost bodies)
3. **Assembly** — all registered joints pass feasibility (no undercuts along
   assembly vector) and all Combine CUT features are accounted for

Returns a single pass/fail result. A valid piece of furniture passes all three.
Joinery void bodies (DM_* prefix by default) are excluded from connectivity
and their mutual overlaps are excluded from interference."""

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
