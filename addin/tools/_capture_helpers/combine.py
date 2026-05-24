"""Combine feature capture and tool body inference."""

import adsk.core
import adsk.fusion

from ._common import _roll_to_feature


def _capture_combine(comb, idx, tl, design=None):
    """Capture a CombineFeature with tool body inference."""
    info = {"type": "Combine", "name": comb.name}

    op_map = {
        adsk.fusion.FeatureOperations.JoinFeatureOperation: "Join",
        adsk.fusion.FeatureOperations.CutFeatureOperation: "Cut",
        adsk.fusion.FeatureOperations.IntersectFeatureOperation: "Intersect",
    }
    info["operation"] = op_map.get(comb.operation, str(comb.operation))

    def _get_target_and_tools():
        tool_names = []
        # Target body
        try:
            tb = comb.targetBody
            info["targetBody"] = tb.name
            try:
                info["targetComponent"] = tb.parentComponent.name
            except:
                pass
        except Exception as e:
            info["targetBodyError"] = str(e)

        # Tool bodies
        try:
            tools = comb.toolBodies
            tool_info = []
            for i in range(tools.count):
                t = tools.item(i)
                entry = {"name": t.name}
                try:
                    entry["component"] = t.parentComponent.name
                except:
                    pass
                tool_info.append(entry)
            tool_names = [t["name"] for t in tool_info]
            info["toolBodies"] = tool_names
            if any("component" in t for t in tool_info):
                info["toolComponents"] = [t.get("component", "") for t in tool_info]
        except Exception as e:
            info["toolBodiesError"] = str(e)
        return tool_names

    # Try direct access first
    tool_names = _get_target_and_tools()

    # Retry with rollTo if body access failed OR if tool names have duplicates
    # (duplicates indicate stale body references at end-of-timeline — Fusion API
    # quirk where comb.toolBodies returns wrong BRepBody objects after timeline
    # recomputation, e.g. pattern copies resolving to the source body).
    has_error = "targetBodyError" in info or "toolBodiesError" in info
    has_dupes = len(tool_names) != len(set(tool_names))
    if (has_error or has_dupes) and design:
        for key in ["targetBody", "targetBodyError", "targetComponent",
                     "toolBodies", "toolBodiesError", "toolComponents"]:
            info.pop(key, None)
        try:
            with _roll_to_feature(comb, design):
                tool_names = _get_target_and_tools()
        except Exception as e:
            info["rollToError"] = str(e)

    # Inference: if toolBodies is empty, walk timeline backwards
    if not tool_names and idx is not None and tl is not None:
        inferred = _infer_combine_tool_bodies(comb, idx, tl)
        if inferred:
            info["toolBodiesInferred"] = inferred

    try:
        info["isKeepToolBodies"] = comb.isKeepToolBodies
    except:
        pass

    # Capture output bodies — CUT operations may split the target into multiple pieces,
    # creating new bodies that the user may rename.  Use rollTo(False) to get current names.
    if info.get("operation") == "Cut" and design:
        try:
            comb.timelineObject.rollTo(False)
            try:
                out_bodies = [b.name for b in comb.bodies]
                if out_bodies:
                    info["outputBodies"] = out_bodies
            finally:
                design.timeline.moveToEnd()
        except:
            pass

    return info


def _infer_combine_tool_bodies(comb, idx, tl):
    """Walk timeline backwards to infer which bodies were consumed as tools."""
    inferred = []
    try:
        target_name = comb.targetBody.name
    except:
        return inferred

    try:
        target_comp = comb.targetBody.parentComponent
    except:
        return inferred

    for back_idx in range(idx - 1, max(idx - 10, -1), -1):
        try:
            back_item = tl.item(back_idx)
            back_entity = back_item.entity
        except:
            continue
        if back_entity is None:
            continue

        back_ext = adsk.fusion.ExtrudeFeature.cast(back_entity)
        if back_ext and back_ext.operation == adsk.fusion.FeatureOperations.NewBodyFeatureOperation:
            try:
                if back_ext.parentComponent == target_comp:
                    for b in back_ext.bodies:
                        if b.name != target_name:
                            try:
                                _ = b.volume
                            except:
                                inferred.append(b.name)
            except:
                pass

    return inferred

