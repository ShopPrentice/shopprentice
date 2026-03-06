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
        "modelParameters": {},
        "dimensions": {},
        "bodies": {},
        "featureCount": design.timeline.count,
    }

    # User parameter expressions
    user_param_names = set()
    for i in range(design.userParameters.count):
        p = design.userParameters.item(i)
        snapshot["parameters"][p.name] = p.expression
        user_param_names.add(p.name)

    # Model parameters (feature-level: chamfer sizes, extrude distances, etc.)
    for i in range(design.allParameters.count):
        p = design.allParameters.item(i)
        if p.name not in user_param_names:
            # Include the parent feature name for context
            try:
                parent = p.createdBy
                if parent:
                    key = f"{parent.name}.{p.name}"
                else:
                    key = p.name
            except:
                key = p.name
            snapshot["modelParameters"][key] = p.expression

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

    # Body volumes and bounding boxes for sandbox validation
    # Collect raw list first to detect duplicate names across components
    _body_raw = []  # [(body_name, comp_name, volume, bbox_dict)]
    def walk_bodies(comp, comp_name="root"):
        for bi in range(comp.bRepBodies.count):
            body = comp.bRepBodies.item(bi)
            try:
                vol = round(body.volume, 4)
            except:
                continue
            bbox = {}
            try:
                bb = body.boundingBox
                bbox = {
                    "min": [round(bb.minPoint.x, 4), round(bb.minPoint.y, 4), round(bb.minPoint.z, 4)],
                    "max": [round(bb.maxPoint.x, 4), round(bb.maxPoint.y, 4), round(bb.maxPoint.z, 4)],
                }
            except:
                pass
            _body_raw.append((body.name, comp_name, vol, bbox))
        for occ in comp.occurrences:
            walk_bodies(occ.component, occ.component.name)
    walk_bodies(design.rootComponent)
    # Detect duplicate names and qualify with [component]
    _name_counts = {}
    for bname, _, _, _ in _body_raw:
        _name_counts[bname] = _name_counts.get(bname, 0) + 1
    body_volumes = {}
    body_bboxes = {}
    for bname, cname, vol, bbox in _body_raw:
        key = "{} [{}]".format(bname, cname) if _name_counts[bname] > 1 else bname
        body_volumes[key] = vol
        if bbox:
            body_bboxes[key] = bbox
    snapshot["bodyVolumes"] = body_volumes
    snapshot["bodyBoundingBoxes"] = body_bboxes

    return snapshot


def _diff_snapshots(old, new):
    """Compute diff between two snapshots."""
    diff = {
        "parameterChanges": [],
        "modelParameterChanges": [],
        "dimensionChanges": [],
        "bodyChanges": {"added": [], "removed": []},
        "featureCountDelta": new["featureCount"] - old["featureCount"],
    }

    # User parameter changes
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

    # Model parameter changes (feature-level: chamfer sizes, extrude distances, etc.)
    all_model_keys = set(old.get("modelParameters", {}).keys()) | set(new.get("modelParameters", {}).keys())
    for key in sorted(all_model_keys):
        old_val = old.get("modelParameters", {}).get(key)
        new_val = new.get("modelParameters", {}).get(key)
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
            diff["modelParameterChanges"].append(entry)

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


def handler(since: str = None) -> dict:
    """Capture snapshot and diff against previous baseline.

    If ActionLog is running, returns individual per-action entries plus a
    compacted merged diff.  Falls back to snapshot-based approach otherwise.

    Args:
        since: Optional cursor UUID. When provided, only returns entries
               recorded after that cursor.
    """
    global _baseline

    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return {
                "content": [{"type": "text", "text": "No active design"}],
                "isError": True,
                "message": "No active design"
            }

        # ── Try ActionLog path first ──
        try:
            from server.action_log import ActionLog
            action_log_available = ActionLog._is_running
        except Exception:
            action_log_available = False

        if action_log_available:
            # Use explicit `since` if provided, otherwise auto-advance cursor
            effective_since = since if since is not None else ActionLog._last_read_cursor
            entries = ActionLog.get_entries(since=effective_since)
            cursor = ActionLog.get_latest_cursor()

            if not entries and effective_since is None and ActionLog._baseline is None:
                # First call ever — capture baseline via ActionLog
                ActionLog.reset()
                current = _capture_snapshot(design)
                _baseline = current
                result = {
                    "baseline": True,
                    "cursor": ActionLog.get_latest_cursor(),
                    "featureCount": current["featureCount"],
                    "parameterCount": len(current["parameters"]),
                    "dimensionCount": len(current["dimensions"]),
                    "bodyCount": sum(len(v) for v in current["bodies"].values()),
                }
                return {
                    "content": [{"type": "text", "text": __import__('json').dumps(result, indent=2)}],
                    "isError": False,
                    "message": "Baseline captured"
                }

            if entries:
                # Strip full diff from entry summaries to keep response concise
                entry_summaries = []
                for e in entries:
                    summary = {
                        "id": e["id"],
                        "commandId": e["commandId"],
                        "timestamp": e["timestamp"],
                        "diff": e["diff"],
                    }
                    entry_summaries.append(summary)

                compacted = ActionLog.get_compacted_diff(since=effective_since)
                ActionLog.advance_cursor()
                result = {
                    "cursor": cursor,
                    "entryCount": len(entries),
                    "entries": entry_summaries,
                    "compacted": compacted,
                }
                return {
                    "content": [{"type": "text", "text": __import__('json').dumps(result, indent=2)}],
                    "isError": False,
                    "message": f"{len(entries)} action(s) recorded"
                }

            # No new entries since cursor
            ActionLog.advance_cursor()
            result = {
                "cursor": cursor,
                "entryCount": 0,
                "entries": [],
                "compacted": None,
            }
            return {
                "content": [{"type": "text", "text": __import__('json').dumps(result, indent=2)}],
                "isError": False,
                "message": "No changes detected"
            }

        # ── Fallback: snapshot-based approach ──
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
                        len(diff["modelParameterChanges"]) +
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

First call: captures a baseline snapshot (parameters, sketch dimensions, bodies, feature count). Returns summary counts + cursor.
Subsequent calls: returns individual per-action entries (each user UI command that modified the design) plus a compacted merged diff. Pass the `since` cursor to get only new changes since your last call.

Response fields:
- **cursor** — pass back as `since` on next call to get incremental changes
- **entryCount** — number of individual UI actions recorded
- **entries** — per-action diffs with commandId, timestamp, and structured diff
- **compacted** — merged diff across all entries (parameter changes, body add/remove, feature count delta)

Use this after the user says "I changed something" or between iterations to see what was modified without re-reading the full design."""

tool = Tool.create_simple(
    name="get_changes",
    description=TOOL_DESCRIPTION
).add_input_property(
    "since",
    {
        "type": "string",
        "description": "Cursor UUID from a previous get_changes call. Only returns changes after this cursor. Omit for all changes since baseline."
    }
).strict_schema()

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
