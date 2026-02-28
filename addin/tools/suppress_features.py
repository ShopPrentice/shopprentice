"""
Suppress Features Tool

Toggle timeline features on/off for "what if" analysis without re-running scripts.
Suppress a feature to see if it's causing problems, then unsuppress to restore.
"""

import traceback
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register
import adsk.core
import adsk.fusion

app = adsk.core.Application.get()


def _count_bodies(root_comp):
    """Count all visible bodies across all components."""
    count = 0
    for b in root_comp.bRepBodies:
        if b.isVisible:
            count += 1
    for occ in root_comp.allOccurrences:
        for b in occ.component.bRepBodies:
            if b.isVisible:
                count += 1
    return count


def _find_feature_by_name(tl, name):
    """Find a timeline item by its entity name."""
    for i in range(tl.count):
        item = tl.item(i)
        try:
            if item.entity and item.entity.name == name:
                return item
        except:
            continue
    return None


def handler(features: list) -> dict:
    """Suppress or unsuppress timeline features."""

    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return {
                "content": [{"type": "text", "text": "No active design"}],
                "isError": True,
                "message": "No active design"
            }

        tl = design.timeline
        results = []
        errors = []

        for spec in features:
            suppress = spec.get("suppress", True)
            index = spec.get("index")
            name = spec.get("name")

            tl_item = None

            # Find by index
            if index is not None:
                try:
                    idx = int(index)
                    if 0 <= idx < tl.count:
                        tl_item = tl.item(idx)
                    else:
                        errors.append({"spec": spec, "error": f"Index {idx} out of range (0-{tl.count - 1})"})
                        continue
                except (ValueError, TypeError):
                    errors.append({"spec": spec, "error": f"Invalid index: {index}"})
                    continue

            # Find by name
            elif name:
                tl_item = _find_feature_by_name(tl, name)
                if not tl_item:
                    errors.append({"spec": spec, "error": f"Feature '{name}' not found"})
                    continue

            else:
                errors.append({"spec": spec, "error": "Must specify 'index' or 'name'"})
                continue

            # Apply suppression
            try:
                old_state = tl_item.isSuppressed
                tl_item.isSuppressed = suppress
                feature_name = "unknown"
                try:
                    feature_name = tl_item.entity.name
                except:
                    pass
                results.append({
                    "name": feature_name,
                    "index": tl_item.index,
                    "wasSuppressed": old_state,
                    "isSuppressed": suppress,
                })
            except Exception as e:
                errors.append({"spec": spec, "error": str(e)})

        # Recompute
        adsk.doEvents()

        body_count = _count_bodies(design.rootComponent)

        # Reset ActionLog baseline (API-driven changes don't fire commandTerminated)
        try:
            from server.action_log import ActionLog
            ActionLog.reset()
        except Exception:
            pass

        # Advance provenance cursor and update reference snapshot
        try:
            from server.document_tracker import DocumentTracker
            DocumentTracker.advance_cursor(ActionLog.get_latest_cursor())
            DocumentTracker.update_reference()
        except Exception:
            pass

        result = {
            "updated": results,
            "updatedCount": len(results),
            "bodyCount": body_count,
        }
        if errors:
            result["errors"] = errors
            result["errorCount"] = len(errors)

        return {
            "content": [{"type": "text", "text": __import__('json').dumps(result, indent=2)}],
            "isError": len(errors) > 0 and len(results) == 0,
            "message": f"Updated {len(results)} feature(s), {body_count} bodies" + (f", {len(errors)} error(s)" if errors else "")
        }

    except Exception as e:
        app.log(f"suppress_features error: {e}\n{traceback.format_exc()}")
        return {
            "content": [{"type": "text", "text": f"Error: {e}\n{traceback.format_exc()}"}],
            "isError": True,
            "message": "suppress_features failed"
        }


# Tool definition

TOOL_DESCRIPTION = \
"""Toggle timeline features on/off for "what if" analysis without re-running scripts.

Suppress a feature to see if it's causing problems, then unsuppress to restore. Returns the updated feature states and body count after recompute.

Diagnostic tool: suppress a suspicious feature, check if body count/geometry improves, then unsuppress to restore the original state."""

tool = Tool.create_simple(
    name="suppress_features",
    description=TOOL_DESCRIPTION
).add_input_property(
    "features",
    {
        "type": "array",
        "description": "Features to suppress/unsuppress. Each: {\"index\": 5, \"suppress\": true} or {\"name\": \"DT_FL_Cut\", \"suppress\": true}",
        "items": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "description": "0-based timeline index"},
                "name": {"type": "string", "description": "Feature name (from capture_design timeline)"},
                "suppress": {"type": "boolean", "description": "true to suppress, false to unsuppress", "default": True}
            }
        }
    }
).add_required_input("features").strict_schema()

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
