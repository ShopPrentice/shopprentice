"""
Check Interference Tool

Detect body intersections/collisions across the design. Essential for
validating joinery — do tenons actually fit mortises? Are any bodies overlapping?
"""

import traceback
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register
import adsk.core
import adsk.fusion

app = adsk.core.Application.get()


def _collect_bodies(root_comp, names=None):
    """Collect bodies, optionally filtered by name."""
    bodies = []
    for b in root_comp.bRepBodies:
        if names is None or b.name in names:
            bodies.append(b)
    for occ in root_comp.allOccurrences:
        for b in occ.component.bRepBodies:
            if names is None or b.name in names:
                bodies.append(b)
    return bodies


def handler(bodies: list = None) -> dict:
    """Check for body interferences in the design."""

    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return {
                "content": [{"type": "text", "text": "No active design"}],
                "isError": True,
                "message": "No active design"
            }

        body_list = _collect_bodies(
            design.rootComponent,
            names=set(bodies) if bodies else None
        )

        if len(body_list) < 2:
            return {
                "content": [{"type": "text", "text": __import__('json').dumps({
                    "interferenceCount": 0,
                    "interferences": [],
                    "bodyCount": len(body_list),
                    "note": "Need at least 2 bodies to check interference"
                }, indent=2)}],
                "isError": False,
                "message": f"Only {len(body_list)} body(s) — need at least 2"
            }

        # Build ObjectCollection of bodies
        body_collection = adsk.core.ObjectCollection.create()
        for b in body_list:
            body_collection.add(b)

        # Run interference analysis
        interference_input = design.createInterferenceInput(body_collection)
        interference_results = design.analyzeInterference(interference_input)

        interferences = []
        for i in range(interference_results.count):
            result = interference_results.item(i)
            entry = {}
            try:
                entry["body1"] = result.entityOne.name
            except:
                entry["body1"] = "unknown"
            try:
                entry["body2"] = result.entityTwo.name
            except:
                entry["body2"] = "unknown"
            try:
                entry["volume"] = round(result.interferenceBody.volume, 4)
            except:
                pass
            interferences.append(entry)

        result = {
            "interferenceCount": len(interferences),
            "interferences": interferences,
            "bodyCount": len(body_list),
        }

        return {
            "content": [{"type": "text", "text": __import__('json').dumps(result, indent=2)}],
            "isError": False,
            "message": f"{len(interferences)} interference(s) found among {len(body_list)} bodies"
        }

    except Exception as e:
        app.log(f"check_interference error: {e}\n{traceback.format_exc()}")
        return {
            "content": [{"type": "text", "text": f"Error: {e}\n{traceback.format_exc()}"}],
            "isError": True,
            "message": "check_interference failed"
        }


# Tool definition

TOOL_DESCRIPTION = \
"""Detect body intersections/collisions in the design.

Checks all bodies (or a named subset) for geometric interference. Returns the pair of overlapping bodies and the volume of their intersection.

Use this to validate joinery — confirm tenons fit mortises without unintended overlaps. A clean design should have zero interferences after all CUT/JOIN operations."""

tool = Tool.create_simple(
    name="check_interference",
    description=TOOL_DESCRIPTION
).add_input_property(
    "bodies",
    {
        "type": "array",
        "description": "Optional list of body names to check. Omit to check all bodies in the design.",
        "items": {"type": "string"}
    }
)

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
