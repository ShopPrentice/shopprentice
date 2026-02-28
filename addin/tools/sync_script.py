"""
Sync Script Tool

Auto-sync Fusion 360 UI changes back to a Python script source.
Reads the script, compares against the live Fusion state, auto-patches
user parameter expression changes, and returns structured guidance for
feature-level changes that need the agent's help.
"""

import re
import traceback
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register
import adsk.core
import adsk.fusion

from ._capture_helpers import (
    _capture_extrude,
    _capture_combine,
    _capture_mirror,
    _capture_rectangular_pattern,
    _capture_move,
    _capture_chamfer,
    _capture_fillet,
    _capture_construction_plane,
)

app = adsk.core.Application.get()


# ── Script parsing helpers ──

def _parse_script_params(script):
    """Extract user parameter tuples from the script source.

    Looks for patterns like:
        ("param_name", "expression", "unit", "description")

    Returns dict: {name: {"expr": str, "unit": str, "desc": str, "match": str}}
    where match is the full tuple string for targeted replacement.
    """
    # Match 4-element string tuples: ("name", "expr", "unit", "desc")
    # Handles optional whitespace and trailing commas
    pattern = (
        r'\(\s*"([^"]+)"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"\s*\)'
    )
    result = {}
    for m in re.finditer(pattern, script):
        name, expr, unit, desc = m.group(1), m.group(2), m.group(3), m.group(4)
        result[name] = {
            "expr": expr,
            "unit": unit,
            "desc": desc,
            "match": m.group(0),
        }
    return result


def _replace_param_expr(script, name, old_expr, new_expr):
    """Replace a parameter expression in a tuple, preserving surrounding structure.

    Targets: ("name", "old_expr", ... → ("name", "new_expr", ...
    Only replaces the first occurrence to avoid false positives.
    """
    # Escape regex special chars in the literal strings
    esc_name = re.escape(name)
    esc_old = re.escape(old_expr)
    pattern = (
        r'(\(\s*"' + esc_name + r'"\s*,\s*)"' + esc_old + r'"(\s*,)'
    )
    replacement = r'\g<1>"' + new_expr.replace('\\', '\\\\') + r'"\2'
    return re.sub(pattern, replacement, script, count=1)


def _get_script_feature_names(script):
    """Extract all feature names assigned in the script.

    Looks for patterns like:
        .name = "FeatureName"
        .name= "FeatureName"

    Returns set of feature name strings.
    """
    pattern = r'\.name\s*=\s*"([^"]+)"'
    return set(re.findall(pattern, script))


def _find_feature_context(script, feature_name, n=5):
    """Find the script context around a feature name assignment.

    Returns n lines before and after the `.name = "feature_name"` line,
    or None if not found.
    """
    lines = script.splitlines()
    esc_name = re.escape(feature_name)
    pattern = re.compile(r'\.name\s*=\s*"' + esc_name + r'"')
    for i, line in enumerate(lines):
        if pattern.search(line):
            start = max(0, i - n)
            end = min(len(lines), i + n + 1)
            return "\n".join(
                f"{'>' if j == i else ' '} {j+1}: {lines[j]}"
                for j in range(start, end)
            )
    return None


def _get_timeline_feature_names(design):
    """Get all named features from the design timeline.

    Returns dict: {name: {"index": int, "type": str, "entity": object}}
    """
    tl = design.timeline
    features = {}
    for i in range(tl.count):
        try:
            item = tl.item(i)
            entity = item.entity
        except RuntimeError:
            continue
        if entity is None:
            continue
        try:
            name = entity.name
        except:
            continue
        if not name:
            continue
        # Determine feature type
        ftype = type(entity).__name__
        features[name] = {"index": i, "type": ftype, "entity": entity}
    return features


def _capture_feature(entity, idx, tl):
    """Capture a timeline feature using the appropriate capture helper.

    Returns a dict with structured feature info, or a minimal dict if
    the feature type is not recognized.
    """
    ext = adsk.fusion.ExtrudeFeature.cast(entity)
    if ext:
        return _capture_extrude(ext, idx, tl)

    comb = adsk.fusion.CombineFeature.cast(entity)
    if comb:
        return _capture_combine(comb, idx, tl)

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

    cp = adsk.fusion.ConstructionPlane.cast(entity)
    if cp:
        return _capture_construction_plane(cp)

    # Fallback
    info = {"type": type(entity).__name__}
    try:
        info["name"] = entity.name
    except:
        pass
    return info


def handler(script: str = None) -> dict:
    """Sync a script against the live Fusion 360 state."""
    try:
        # If script not provided, read from DocumentTracker
        if script is None:
            from server.document_tracker import DocumentTracker
            script = DocumentTracker.get_script()
            if script is None:
                return {
                    "content": [{"type": "text", "text": "No script provided and no tracked script"}],
                    "isError": True,
                    "message": "No script provided and no tracked script"
                }

        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return {
                "content": [{"type": "text", "text": "No active design"}],
                "isError": True,
                "message": "No active design"
            }

        # ── 1. Parse parameter tuples from script ──
        param_tuples = _parse_script_params(script)

        # ── 2. Read current Fusion user parameters ──
        fusion_params = {}
        for i in range(design.userParameters.count):
            p = design.userParameters.item(i)
            fusion_params[p.name] = p.expression

        # ── 3. Auto-patch user parameter changes ──
        patched = script
        applied = []
        for name, info in param_tuples.items():
            if name in fusion_params and fusion_params[name] != info["expr"]:
                patched = _replace_param_expr(
                    patched, name, info["expr"], fusion_params[name]
                )
                applied.append({
                    "type": "parameterChanged",
                    "name": name,
                    "old": info["expr"],
                    "new": fusion_params[name],
                })

        # ── 4. Detect feature-level changes ──
        needs_agent = []
        script_features = _get_script_feature_names(script)
        tl_features = _get_timeline_feature_names(design)
        tl = design.timeline

        # ── 5. Model parameter changes (state-diff against reference snapshot) ──
        from server.document_tracker import DocumentTracker
        ref_params = DocumentTracker.get_reference_model_params()
        if ref_params is not None:
            current_params = DocumentTracker._capture_model_params() or {}
            all_keys = set(ref_params.keys()) | set(current_params.keys())
            feature_param_changes = {}
            for key in sorted(all_keys):
                old_val = ref_params.get(key)
                new_val = current_params.get(key)
                if old_val != new_val:
                    parts = key.split(".", 1)
                    feat_name = parts[0] if len(parts) == 2 else ""
                    param_name = parts[1] if len(parts) == 2 else key
                    if feat_name not in feature_param_changes:
                        feature_param_changes[feat_name] = []
                    entry = {"paramName": param_name}
                    if old_val is not None:
                        entry["old"] = old_val
                    if new_val is not None:
                        entry["new"] = new_val
                    feature_param_changes[feat_name].append(entry)

            for feat_name, params in feature_param_changes.items():
                if feat_name in script_features and feat_name in tl_features:
                    entry = {
                        "type": "featureParameterChanged",
                        "feature": feat_name,
                        "featureType": tl_features[feat_name]["type"],
                        "params": params,
                    }
                    ctx = _find_feature_context(script, feat_name)
                    if ctx:
                        entry["scriptContext"] = ctx
                    needs_agent.append(entry)

        # ── 6. Features removed (in script but not in timeline) ──
        # Skip sketch names — sketches are implicit, not typically named in timeline
        for name in sorted(script_features - set(tl_features.keys())):
            entry = {
                "type": "featureRemoved",
                "feature": name,
            }
            ctx = _find_feature_context(script, name)
            if ctx:
                entry["scriptContext"] = ctx
            needs_agent.append(entry)

        # ── 7. Features added (in timeline but not in script) ──
        for name in sorted(set(tl_features.keys()) - script_features):
            feat_info = tl_features[name]
            entity = feat_info["entity"]
            entry = {
                "type": "featureAdded",
                "feature": name,
                "featureType": feat_info["type"],
            }
            try:
                capture = _capture_feature(entity, feat_info["index"], tl)
                entry["capture"] = capture
            except Exception as e:
                entry["captureError"] = str(e)
            needs_agent.append(entry)

        # ── 8. Build result ──
        result = {
            "patchedScript": patched,
            "applied": applied,
            "needsAgent": needs_agent,
        }

        # Update provenance tracking
        try:
            if DocumentTracker.get_script() is not None:
                DocumentTracker.on_sync_complete(patched)
        except Exception:
            pass

        # Summary message
        parts = []
        if applied:
            parts.append(f"{len(applied)} param(s) patched")
        agent_count = len(needs_agent)
        if agent_count:
            parts.append(f"{agent_count} change(s) need agent")
        msg = ", ".join(parts) if parts else "Script is in sync"

        return {
            "content": [{"type": "text", "text": __import__('json').dumps(result, indent=2)}],
            "isError": False,
            "message": msg
        }

    except Exception as e:
        app.log(f"sync_script error: {e}\n{traceback.format_exc()}")
        return {
            "content": [{"type": "text", "text": f"Error: {e}\n{traceback.format_exc()}"}],
            "isError": True,
            "message": "sync_script failed"
        }


# Tool definition

TOOL_DESCRIPTION = \
"""Sync a Python script against the live Fusion 360 design state.

Pass the original script source, or omit it to use the tracked script from the last execute_script run. The tool diffs it against the current Fusion state and returns:

- **patchedScript** — the script with user parameter expression changes auto-applied (e.g., `tt_shoulder` changed from `"0.375 in"` to `"0.3 in"`)
- **applied** — list of auto-patched parameter changes
- **needsAgent** — list of changes that require agent intervention:
  - `featureParameterChanged` — feature-level params (chamfer sizes, extrude distances) changed in the UI. Includes old/new expressions and surrounding script code.
  - `featureRemoved` — a feature from the script was deleted in the UI. Includes the script code block to remove.
  - `featureAdded` — a new feature was added in the UI. Includes full capture data so the agent can generate code.

Model parameter changes are detected via state-diff: a reference snapshot is captured when the script executes and compared against the current model state. No cursor threading required.

Workflow:
1. Run script via `execute_script`
2. User tweaks design in Fusion UI
3. Call `sync_script` (no arguments needed)
4. Write `patchedScript` to the file
5. Apply `needsAgent` changes to the script
6. Re-execute to verify"""

tool = Tool.create_simple(
    name="sync_script",
    description=TOOL_DESCRIPTION,
).add_input_property(
    "script",
    {
        "type": "string",
        "description": "The Python script source code to sync against the live Fusion 360 state. Optional — omit to use the tracked script from the last execute_script run."
    }
).strict_schema()

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
