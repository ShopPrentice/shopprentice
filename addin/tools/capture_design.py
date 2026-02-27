"""
Capture Design Tool

Full design introspection: parameters, component tree with body geometry,
and timeline features. Replaces running introspect.py via execute_api_script.

Key improvements over introspect.py:
1. Inline body geometry — component tree includes volume + bounding box per body
2. Structured sketch planes — returns typed objects instead of bare strings
3. Combine tool inference — walks timeline backwards when toolBodies is empty
"""

import traceback
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register
import adsk.core
import adsk.fusion

from ._capture_helpers import (
    _capture_body,
    _capture_sketch,
    _capture_sketch_summary,
    _capture_extrude,
    _capture_construction_plane,
    _capture_mirror,
    _capture_rectangular_pattern,
    _capture_combine,
    _capture_move,
    _capture_chamfer,
    _capture_fillet,
)

app = adsk.core.Application.get()


def _capture_all_bodies(root_comp):
    """Capture component tree with inline body geometry."""
    def walk(comp, occ=None):
        info = {
            "name": comp.name,
            "bodies": [_capture_body(b) for b in comp.bRepBodies],
            "children": [],
        }
        if occ:
            try:
                t = occ.transform
                info["transform"] = [
                    round(t.translation.x, 4),
                    round(t.translation.y, 4),
                    round(t.translation.z, 4),
                ]
            except:
                pass
        for child_occ in comp.occurrences:
            info["children"].append(walk(child_occ.component, child_occ))
        return info
    return walk(root_comp)


# ── Component tree (full detail for capture_design) ──

def _capture_component_tree(root_comp):
    """Recursive component tree with bodies, sketches, construction planes."""
    def walk(comp, occ=None):
        info = {
            "name": comp.name,
            "bodies": [_capture_body(b) for b in comp.bRepBodies],
            "sketches": [_capture_sketch_summary(s) for s in comp.sketches],
            "constructionPlanes": [p.name for p in comp.constructionPlanes],
            "children": [],
        }
        if occ:
            try:
                t = occ.transform
                info["transform"] = [
                    round(t.translation.x, 4),
                    round(t.translation.y, 4),
                    round(t.translation.z, 4),
                ]
            except:
                pass
        for child_occ in comp.occurrences:
            info["children"].append(walk(child_occ.component, child_occ))
        return info
    return walk(root_comp)


# ── Main handler ──

def handler() -> dict:
    """Capture full design: parameters, component tree, timeline features."""

    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return {
                "content": [{"type": "text", "text": "No active design"}],
                "isError": True,
                "message": "No active design"
            }

        out = {
            "designName": design.rootComponent.name,
            "designType": "Parametric" if design.designType == adsk.fusion.DesignTypes.ParametricDesignType else "Direct",
            "userParameters": [],
            "components": None,
            "timeline": [],
        }

        # 1. User Parameters
        for i in range(design.userParameters.count):
            p = design.userParameters.item(i)
            out["userParameters"].append({
                "name": p.name,
                "expression": p.expression,
                "unit": p.unit,
                "value": p.value,
                "comment": p.comment,
            })

        # 2. Component Tree (with inline body geometry)
        out["components"] = _capture_component_tree(design.rootComponent)

        # 3. Timeline Features
        tl = design.timeline
        for idx in range(tl.count):
            item = tl.item(idx)
            try:
                entity = item.entity
            except RuntimeError:
                continue
            if entity is None:
                continue

            feat_info = {
                "index": idx,
                "isGroup": item.isGroup,
                "isRolledBack": item.isRolledBack,
            }

            # Component
            try:
                if hasattr(entity, 'parentComponent') and entity.parentComponent:
                    feat_info["component"] = entity.parentComponent.name
            except:
                pass

            # Extrude
            ext = adsk.fusion.ExtrudeFeature.cast(entity)
            if ext:
                feat_info.update(_capture_extrude(ext, idx, tl))
                out["timeline"].append(feat_info)
                continue

            # Sketch
            sk = adsk.fusion.Sketch.cast(entity)
            if sk:
                feat_info.update(_capture_sketch(sk))
                out["timeline"].append(feat_info)
                continue

            # ConstructionPlane
            cp = adsk.fusion.ConstructionPlane.cast(entity)
            if cp:
                feat_info.update(_capture_construction_plane(cp))
                out["timeline"].append(feat_info)
                continue

            # Mirror
            mir = adsk.fusion.MirrorFeature.cast(entity)
            if mir:
                feat_info.update(_capture_mirror(mir))
                out["timeline"].append(feat_info)
                continue

            # RectangularPattern
            pat = adsk.fusion.RectangularPatternFeature.cast(entity)
            if pat:
                feat_info.update(_capture_rectangular_pattern(pat))
                out["timeline"].append(feat_info)
                continue

            # Combine
            comb = adsk.fusion.CombineFeature.cast(entity)
            if comb:
                feat_info.update(_capture_combine(comb, idx, tl))
                out["timeline"].append(feat_info)
                continue

            # ConstructionAxis
            ca = adsk.fusion.ConstructionAxis.cast(entity)
            if ca:
                feat_info["type"] = "ConstructionAxis"
                feat_info["name"] = ca.name
                out["timeline"].append(feat_info)
                continue

            # Move
            mv = adsk.fusion.MoveFeature.cast(entity)
            if mv:
                feat_info.update(_capture_move(mv))
                out["timeline"].append(feat_info)
                continue

            # Chamfer
            chamfer = adsk.fusion.ChamferFeature.cast(entity)
            if chamfer:
                feat_info.update(_capture_chamfer(chamfer))
                out["timeline"].append(feat_info)
                continue

            # Fillet
            fillet = adsk.fusion.FilletFeature.cast(entity)
            if fillet:
                feat_info.update(_capture_fillet(fillet))
                out["timeline"].append(feat_info)
                continue

            # Occurrence
            occ = adsk.fusion.Occurrence.cast(entity)
            if occ:
                feat_info["type"] = "ComponentCreation"
                feat_info["name"] = occ.component.name
                out["timeline"].append(feat_info)
                continue

            # Snapshot
            try:
                if entity.objectType == "adsk::fusion::Snapshot":
                    feat_info["type"] = "Snapshot"
                    try:
                        feat_info["name"] = entity.name
                    except:
                        pass
                    out["timeline"].append(feat_info)
                    continue
            except:
                pass

            # Unknown
            feat_info["type"] = "Unknown"
            feat_info["objectType"] = entity.objectType
            try:
                feat_info["name"] = entity.name
            except:
                pass
            out["timeline"].append(feat_info)

        return {
            "content": [{"type": "text", "text": __import__('json').dumps(out, indent=2)}],
            "isError": False,
            "message": f"Captured design: {out['designName']}"
        }

    except Exception as e:
        app.log(f"capture_design error: {e}\n{traceback.format_exc()}")
        return {
            "content": [{"type": "text", "text": f"Error: {e}\n{traceback.format_exc()}"}],
            "isError": True,
            "message": "capture_design failed"
        }


# Tool definition

TOOL_DESCRIPTION = \
"""Capture the full active design: user parameters, component tree with body geometry (volume + bounding box), and all timeline features.

Returns structured JSON with:
- userParameters: all parametric dimensions
- components: recursive tree with inline body volumes and bounding boxes
- timeline: every feature (Extrude, Sketch, Mirror, Pattern, Combine, Move, etc.) with full detail

Workflow: Call this after every successful execute_script to validate the result. Compare body count, names, positions (bounding boxes), and volumes against what the script intended. If the model state is unexpected, use get_timeline_state to bisect the timeline and find the broken feature.

Also call this before modifying an existing design to understand its current state."""

tool = Tool.create_simple(
    name="capture_design",
    description=TOOL_DESCRIPTION
).strict_schema()

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
