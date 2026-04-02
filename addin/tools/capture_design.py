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
    _capture_sweep,
    _capture_split_body,
    _capture_remove,
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
                # Store full 4x4 matrix in row-major order using getCell
                # for unambiguous layout: [r00,r01,r02,tx, r10,r11,r12,ty, ...]
                cells = []
                is_identity = True
                for row in range(4):
                    for col in range(4):
                        val = t.getCell(row, col)
                        cells.append(round(val, 6))
                        if abs(val - (1.0 if row == col else 0.0)) > 1e-9:
                            is_identity = False
                if not is_identity:
                    info["transform"] = cells
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
                # Store full 4x4 matrix in row-major order using getCell
                # for unambiguous layout: [r00,r01,r02,tx, r10,r11,r12,ty, ...]
                cells = []
                is_identity = True
                for row in range(4):
                    for col in range(4):
                        val = t.getCell(row, col)
                        cells.append(round(val, 6))
                        if abs(val - (1.0 if row == col else 0.0)) > 1e-9:
                            is_identity = False
                if not is_identity:
                    info["transform"] = cells
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

        # Ensure timeline is fully evaluated (rolled to end) so all feature
        # properties read correctly.  Save/restore the original position.
        tl = design.timeline
        original_marker = tl.markerPosition
        if original_marker != tl.count:
            tl.markerPosition = tl.count
            adsk.doEvents()

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
        # Expand all timeline groups so every feature is accessible.
        # Iterate backwards so index shifts from expansion don't affect
        # items we haven't visited yet.
        tl = design.timeline
        _expanded_any = False
        for gi in range(tl.count - 1, -1, -1):
            gitem = tl.item(gi)
            if gitem.isGroup:
                try:
                    if not gitem.isExpanded:
                        gitem.isExpanded = True
                        _expanded_any = True
                except AttributeError:
                    pass
        if _expanded_any:
            adsk.doEvents()

        for idx in range(tl.count):
            item = tl.item(idx)
            try:
                entity = item.entity
            except RuntimeError:
                # item.entity fails for some feature types (e.g. CopyPasteBody).
                # Search component features for the one at this timeline index.
                cpb_found = False
                try:
                    for _comp in [design.rootComponent] + [
                            occ.component for occ in design.rootComponent.allOccurrences]:
                        for _fi in range(_comp.features.copyPasteBodies.count):
                            cpb = _comp.features.copyPasteBodies.item(_fi)
                            if cpb.timelineObject.index == idx:
                                src_names = []
                                for _si in range(cpb.sourceBody.count):
                                    src_names.append(cpb.sourceBody.item(_si).name)
                                out_names = []
                                for _bi in range(cpb.bodies.count):
                                    out_names.append(cpb.bodies.item(_bi).name)
                                feat_info = {
                                    "index": idx,
                                    "isGroup": item.isGroup,
                                    "isRolledBack": item.isRolledBack,
                                    "type": "CopyPasteBody",
                                    "name": cpb.name,
                                    "component": _comp.name,
                                    "sourceBody": src_names,
                                    "bodies": out_names,
                                }
                                out["timeline"].append(feat_info)
                                cpb_found = True
                                break
                        if cpb_found:
                            break
                except:
                    pass
                if not cpb_found:
                    try:
                        out["timeline"].append({
                            "index": idx,
                            "isGroup": item.isGroup,
                            "isRolledBack": item.isRolledBack,
                            "type": "Unknown",
                            "name": f"_skipped_{idx}",
                            "_entityError": "RuntimeError",
                        })
                    except:
                        pass
                continue
            if entity is None:
                try:
                    out["timeline"].append({
                        "index": idx,
                        "isGroup": item.isGroup,
                        "isRolledBack": item.isRolledBack,
                        "type": "Unknown",
                        "name": f"_skipped_{idx}",
                        "_entityError": "None",
                    })
                except:
                    pass
                continue

            feat_info = {
                "index": idx,
                "isGroup": item.isGroup,
                "isRolledBack": item.isRolledBack,
            }

            # Component — Feature subclasses use .parentComponent,
            # construction entities (ConstructionPlane/Axis) use .parent
            try:
                pc = getattr(entity, 'parentComponent', None)
                if pc is None:
                    pc = getattr(entity, 'parent', None)
                if pc and hasattr(pc, 'name'):
                    feat_info["component"] = pc.name
            except:
                pass

            # Extrude
            ext = adsk.fusion.ExtrudeFeature.cast(entity)
            if ext:
                feat_info.update(_capture_extrude(ext, idx, tl, design))
                out["timeline"].append(feat_info)
                continue

            # Sketch
            sk = adsk.fusion.Sketch.cast(entity)
            if sk:
                feat_info.update(_capture_sketch(sk, design))
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
                feat_info.update(_capture_mirror(mir, design))
                out["timeline"].append(feat_info)
                continue

            # RectangularPattern
            pat = adsk.fusion.RectangularPatternFeature.cast(entity)
            if pat:
                feat_info.update(_capture_rectangular_pattern(pat, design))
                out["timeline"].append(feat_info)
                continue

            # Combine
            comb = adsk.fusion.CombineFeature.cast(entity)
            if comb:
                feat_info.update(_capture_combine(comb, idx, tl, design))
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
                feat_info.update(_capture_move(mv, design))
                out["timeline"].append(feat_info)
                continue

            # Chamfer
            chamfer = adsk.fusion.ChamferFeature.cast(entity)
            if chamfer:
                feat_info.update(_capture_chamfer(chamfer, design))
                out["timeline"].append(feat_info)
                continue

            # Fillet
            fillet = adsk.fusion.FilletFeature.cast(entity)
            if fillet:
                feat_info.update(_capture_fillet(fillet, design))
                out["timeline"].append(feat_info)
                continue

            # Sweep
            sweep = adsk.fusion.SweepFeature.cast(entity)
            if sweep:
                feat_info.update(_capture_sweep(sweep, design))
                out["timeline"].append(feat_info)
                continue

            # SplitBody
            split = adsk.fusion.SplitBodyFeature.cast(entity)
            if split:
                feat_info.update(_capture_split_body(split, design))
                out["timeline"].append(feat_info)
                continue

            # Remove
            remove = adsk.fusion.RemoveFeature.cast(entity)
            if remove:
                feat_info.update(_capture_remove(remove))
                out["timeline"].append(feat_info)
                continue

            # Occurrence
            occ = adsk.fusion.Occurrence.cast(entity)
            if occ:
                feat_info["type"] = "ComponentCreation"
                feat_info["name"] = occ.component.name
                out["timeline"].append(feat_info)
                continue

            # Snapshot (Capture Position) — records joint positions that move
            # component occurrences.  Capture the occurrence transforms at this
            # marker position so the generator can emit the corresponding moves.
            try:
                if entity.objectType == "adsk::fusion::Snapshot":
                    feat_info["type"] = "Snapshot"
                    try:
                        feat_info["name"] = entity.name
                    except:
                        pass
                    # Roll marker to just after this feature to read transforms
                    try:
                        tl.markerPosition = idx + 1
                        adsk.doEvents()
                        transforms = {}
                        for occ in design.rootComponent.allOccurrences:
                            t = occ.transform
                            is_identity = True
                            for row in range(4):
                                for col in range(4):
                                    if abs(t.getCell(row, col) - (1.0 if row == col else 0.0)) > 1e-9:
                                        is_identity = False
                                        break
                                if not is_identity:
                                    break
                            if not is_identity:
                                # Store full 4x4 row-major matrix to preserve
                                # rotation, not just translation.
                                matrix = []
                                for row in range(4):
                                    for col in range(4):
                                        matrix.append(round(t.getCell(row, col), 6))
                                transforms[occ.component.name] = matrix
                        if transforms:
                            feat_info["transforms"] = transforms
                        # Restore to end
                        tl.markerPosition = tl.count
                        adsk.doEvents()
                    except:
                        pass
                    out["timeline"].append(feat_info)
                    continue
            except:
                pass

            # CopyPasteBody (when item.entity succeeds)
            try:
                if entity.objectType == "adsk::fusion::CopyPasteBody":
                    cpb = adsk.fusion.CopyPasteBody.cast(entity)
                    if cpb:
                        src_names = [cpb.sourceBody.item(i).name
                                     for i in range(cpb.sourceBody.count)]
                        out_names = [cpb.bodies.item(i).name
                                     for i in range(cpb.bodies.count)]
                        feat_info["type"] = "CopyPasteBody"
                        feat_info["name"] = cpb.name
                        feat_info["sourceBody"] = src_names
                        feat_info["bodies"] = out_names
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

        # Restore original timeline position
        if original_marker != tl.count:
            try:
                tl.markerPosition = original_marker
                adsk.doEvents()
            except:
                pass

        # Build compact inline summary (body names + bounding boxes + params)
        # Save full capture to temp file for deep inspection when needed
        import json, tempfile, os
        full_json = json.dumps(out, indent=2)

        # Save full capture to temp file
        tmp_dir = os.path.join(tempfile.gettempdir(), "shopprentice_captures")
        os.makedirs(tmp_dir, exist_ok=True)
        import time
        capture_path = os.path.join(tmp_dir, f"capture_{int(time.time())}.json")
        with open(capture_path, "w") as f:
            f.write(full_json)

        # Build compact summary: bodies with bounding boxes + parameter list
        def _flatten_bodies(comp, prefix=""):
            bodies = []
            for b in comp.get("bodies", []):
                bodies.append({
                    "name": b["name"],
                    "component": comp["name"],
                    "boundingBox": b.get("boundingBox"),
                    "volume_cm3": round(b.get("volume", 0), 2) if b.get("volume") else None,
                })
            for child in comp.get("children", []):
                bodies.extend(_flatten_bodies(child))
            return bodies

        all_bodies = _flatten_bodies(out["components"])
        summary = {
            "designName": out["designName"],
            "bodyCount": len(all_bodies),
            "featureCount": len(out["timeline"]),
            "parameterCount": len(out["userParameters"]),
            "bodies": all_bodies,
            "userParameters": out["userParameters"],
            "fullCapture": capture_path,
        }

        return {
            "content": [{"type": "text", "text": json.dumps(summary, indent=2)}],
            "isError": False,
            "message": f"Captured design: {out['designName']} ({len(all_bodies)} bodies, {len(out['timeline'])} features). Full capture: {capture_path}"
        }

    except Exception as e:
        # Restore timeline position on error too
        try:
            if 'original_marker' in dir():
                tl_err = design.timeline
                if tl_err.markerPosition != original_marker:
                    tl_err.markerPosition = original_marker
                    adsk.doEvents()
        except:
            pass
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
