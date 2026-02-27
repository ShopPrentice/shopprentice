"""
Get Changes Tool

Snapshot & diff tool for detecting what changed in the design since the last call.
First call captures a baseline; subsequent calls diff against it and update the baseline.
"""

import traceback
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register
import adsk.core
import adsk.fusion

app = adsk.core.Application.get()

# Module-level baseline storage (persists across calls within the add-in session)
_baseline = None


def _capture_snapshot(design):
    """Capture a lightweight snapshot of the design state."""
    snapshot = {
        "parameters": {},
        "dimensions": {},
        "bodies": {},
        "featureCount": design.timeline.count,
    }

    # User parameter expressions
    for i in range(design.userParameters.count):
        p = design.userParameters.item(i)
        snapshot["parameters"][p.name] = p.expression

    # Sketch dimension expressions + body names, walking all components
    def walk(comp, prefix=""):
        comp_name = prefix + comp.name if prefix else comp.name

        # Sketch dimensions
        for si in range(comp.sketches.count):
            sk = comp.sketches.item(si)
            for di in range(sk.sketchDimensions.count):
                d = sk.sketchDimensions.item(di)
                if d.parameter:
                    key = f"{comp_name}/{sk.name}.{d.parameter.name}"
                    snapshot["dimensions"][key] = d.parameter.expression

        # Body names
        body_names = []
        for bi in range(comp.bRepBodies.count):
            body_names.append(comp.bRepBodies.item(bi).name)
        if body_names:
            snapshot["bodies"][comp_name] = body_names

        for occ in comp.occurrences:
            walk(occ.component, comp_name + "/")

    walk(design.rootComponent)
    return snapshot


def _diff_snapshots(old, new):
    """Compute diff between two snapshots."""
    diff = {
        "parameterChanges": [],
        "dimensionChanges": [],
        "bodyChanges": {"added": [], "removed": []},
        "featureCountDelta": new["featureCount"] - old["featureCount"],
    }

    # Parameter changes
    all_param_keys = set(old["parameters"].keys()) | set(new["parameters"].keys())
    for key in sorted(all_param_keys):
        old_val = old["parameters"].get(key)
        new_val = new["parameters"].get(key)
        if old_val != new_val:
            entry = {"name": key}
            if old_val is not None:
                entry["old"] = old_val
            if new_val is not None:
                entry["new"] = new_val
            if old_val is None:
                entry["change"] = "added"
            elif new_val is None:
                entry["change"] = "removed"
            diff["parameterChanges"].append(entry)

    # Dimension changes
    all_dim_keys = set(old["dimensions"].keys()) | set(new["dimensions"].keys())
    for key in sorted(all_dim_keys):
        old_val = old["dimensions"].get(key)
        new_val = new["dimensions"].get(key)
        if old_val != new_val:
            # Parse key: "CompName/SketchName.paramName"
            parts = key.rsplit("/", 1)
            if len(parts) == 2:
                component = parts[0]
                sk_param = parts[1]
            else:
                component = ""
                sk_param = parts[0]
            sk_parts = sk_param.split(".", 1)
            sketch = sk_parts[0] if len(sk_parts) > 0 else ""
            param = sk_parts[1] if len(sk_parts) > 1 else ""

            entry = {"sketch": sketch, "component": component, "param": param}
            if old_val is not None:
                entry["old"] = old_val
            if new_val is not None:
                entry["new"] = new_val
            diff["dimensionChanges"].append(entry)

    # Body changes
    all_comp_keys = set(old["bodies"].keys()) | set(new["bodies"].keys())
    for comp_name in sorted(all_comp_keys):
        old_bodies = set(old["bodies"].get(comp_name, []))
        new_bodies = set(new["bodies"].get(comp_name, []))
        for b in sorted(new_bodies - old_bodies):
            diff["bodyChanges"]["added"].append({"component": comp_name, "name": b})
        for b in sorted(old_bodies - new_bodies):
            diff["bodyChanges"]["removed"].append({"component": comp_name, "name": b})

    return diff


def handler() -> dict:
    """Capture snapshot and diff against previous baseline."""
    global _baseline

    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return {
                "content": [{"type": "text", "text": "No active design"}],
                "isError": True,
                "message": "No active design"
            }

        current = _capture_snapshot(design)

        if _baseline is None:
            _baseline = current
            result = {"baseline": True, "featureCount": current["featureCount"],
                      "parameterCount": len(current["parameters"]),
                      "dimensionCount": len(current["dimensions"]),
                      "bodyCount": sum(len(v) for v in current["bodies"].values())}
            return {
                "content": [{"type": "text", "text": __import__('json').dumps(result, indent=2)}],
                "isError": False,
                "message": "Baseline captured"
            }

        diff = _diff_snapshots(_baseline, current)
        _baseline = current

        # Summarize for message
        total_changes = (len(diff["parameterChanges"]) +
                        len(diff["dimensionChanges"]) +
                        len(diff["bodyChanges"]["added"]) +
                        len(diff["bodyChanges"]["removed"]) +
                        (1 if diff["featureCountDelta"] != 0 else 0))

        return {
            "content": [{"type": "text", "text": __import__('json').dumps(diff, indent=2)}],
            "isError": False,
            "message": f"{total_changes} change(s) detected" if total_changes > 0 else "No changes detected"
        }

    except Exception as e:
        app.log(f"get_changes error: {e}\n{traceback.format_exc()}")
        return {
            "content": [{"type": "text", "text": f"Error: {e}\n{traceback.format_exc()}"}],
            "isError": True,
            "message": "get_changes failed"
        }


# Tool definition

TOOL_DESCRIPTION = \
"""Detect what changed in the design since the last call.

First call: captures a baseline snapshot (parameters, sketch dimensions, bodies, feature count). Returns summary counts.
Subsequent calls: diffs current state vs baseline. Returns structured changes: parameter expression changes, sketch dimension changes, body additions/removals, and timeline feature count delta. Updates the baseline after each diff.

Use this after the user says "I changed something" or between iterations to see what was modified without re-reading the full design."""

tool = Tool.create_simple(
    name="get_changes",
    description=TOOL_DESCRIPTION
).strict_schema()

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
