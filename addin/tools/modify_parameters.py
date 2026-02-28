"""
Modify Parameters Tool

Change user parameter values/expressions without re-executing the full script.
Fusion 360 does incremental recomputation — only features depending on changed
parameters are recomputed.
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


def handler(changes: list) -> dict:
    """Modify user parameter expressions and recompute."""

    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return {
                "content": [{"type": "text", "text": "No active design"}],
                "isError": True,
                "message": "No active design"
            }

        params = design.userParameters
        results = []
        errors = []

        for change in changes:
            name = change.get("name", "")
            expression = change.get("expression", "")

            param = params.itemByName(name)
            if not param:
                errors.append({"name": name, "error": f"Parameter '{name}' not found"})
                continue

            old_expression = param.expression
            old_value = param.value

            try:
                param.expression = expression
                results.append({
                    "name": name,
                    "oldExpression": old_expression,
                    "oldValue": round(old_value, 6),
                    "newExpression": expression,
                    "newValue": round(param.value, 6),
                })
            except Exception as e:
                errors.append({"name": name, "error": str(e)})

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
            "message": f"Updated {len(results)} parameter(s), {body_count} bodies" + (f", {len(errors)} error(s)" if errors else "")
        }

    except Exception as e:
        app.log(f"modify_parameters error: {e}\n{traceback.format_exc()}")
        return {
            "content": [{"type": "text", "text": f"Error: {e}\n{traceback.format_exc()}"}],
            "isError": True,
            "message": "modify_parameters failed"
        }


# Tool definition

TOOL_DESCRIPTION = \
"""Change user parameter values/expressions without re-executing the full script.

Fusion 360 does incremental recomputation — only features depending on the changed parameters recompute. This is much faster than re-running the entire script.

Use this for iterative tuning: "make the shelves deeper" → modify_parameters([{"name": "shelf_depth", "expression": "14 in"}]).

After modifying, validate with capture_design. If the result is bad, revert by setting the old expression back. If the result is good, update the .py source file to match."""

tool = Tool.create_simple(
    name="modify_parameters",
    description=TOOL_DESCRIPTION
).add_input_property(
    "changes",
    {
        "type": "array",
        "description": "Parameter changes to apply.",
        "items": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "User parameter name"},
                "expression": {"type": "string", "description": "New expression (e.g. \"14 in\", \"shelf_width / 2\")"}
            },
            "required": ["name", "expression"]
        }
    }
).add_required_input("changes").strict_schema()

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
