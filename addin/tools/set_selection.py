"""
Set Selection Tool

Programmatically select entities in Fusion 360 so the user can see
what the agent is referring to.
"""

import traceback
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register
import adsk.core
import adsk.fusion

app = adsk.core.Application.get()


def _find_body_by_name(root_comp, name):
    """Walk all components to find a body by name."""
    for b in root_comp.bRepBodies:
        if b.name == name:
            return b
    for occ in root_comp.allOccurrences:
        for b in occ.component.bRepBodies:
            if b.name == name:
                return b
    return None


def _find_occurrence_by_name(root_comp, name):
    """Find an occurrence by name or fullPathName."""
    for occ in root_comp.allOccurrences:
        if occ.name == name or occ.fullPathName == name:
            return occ
    return None


def _find_face_by_name(root_comp, body_name, face_index=0):
    """Find a face on a named body by index."""
    body = _find_body_by_name(root_comp, body_name)
    if body and face_index < body.faces.count:
        return body.faces.item(face_index)
    return None


def _resolve_entity(design, spec):
    """Resolve an entity spec to a Fusion entity."""
    # Token-based lookup
    token = spec.get("token")
    if token:
        entities = design.findEntityByToken(token)
        if entities and entities.count > 0:
            return entities.item(0)
        return None

    # Name-based lookup
    entity_type = spec.get("type", "body")
    name = spec.get("name", "")
    root = design.rootComponent

    if entity_type == "body":
        return _find_body_by_name(root, name)
    elif entity_type == "occurrence":
        return _find_occurrence_by_name(root, name)
    elif entity_type == "face":
        body_name = spec.get("bodyName", name)
        face_index = spec.get("faceIndex", 0)
        try:
            face_index = int(face_index)
        except (ValueError, TypeError):
            face_index = 0
        return _find_face_by_name(root, body_name, face_index)

    return None


def handler(action: str = "set", entities: list = None) -> dict:
    """Select entities in the Fusion 360 UI."""

    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return {
                "content": [{"type": "text", "text": "No active design"}],
                "isError": True,
                "message": "No active design"
            }

        ui = app.userInterface
        entities = entities or []

        # Clear
        if action in ("clear", "set"):
            ui.activeSelections.clear()

        if action == "clear":
            return {
                "content": [{"type": "text", "text": "Selection cleared."}],
                "isError": False,
                "message": "Selection cleared"
            }

        # Resolve and add entities
        added = []
        failed = []
        for spec in entities:
            entity = _resolve_entity(design, spec)
            if entity:
                try:
                    ui.activeSelections.add(entity)
                    name = getattr(entity, 'name', str(spec))
                    added.append(name)
                except Exception as e:
                    failed.append({"spec": spec, "error": str(e)})
            else:
                failed.append({"spec": spec, "error": "Entity not found"})

        result = {"added": added, "addedCount": len(added)}
        if failed:
            result["failed"] = failed
            result["failedCount"] = len(failed)

        return {
            "content": [{"type": "text", "text": __import__('json').dumps(result, indent=2)}],
            "isError": len(failed) > 0 and len(added) == 0,
            "message": f"Selected {len(added)} entity(s)" + (f", {len(failed)} failed" if failed else "")
        }

    except Exception as e:
        app.log(f"set_selection error: {e}\n{traceback.format_exc()}")
        return {
            "content": [{"type": "text", "text": f"Error: {e}\n{traceback.format_exc()}"}],
            "isError": True,
            "message": "set_selection failed"
        }


# Tool definition

TOOL_DESCRIPTION = \
"""Programmatically select entities in the Fusion 360 UI to highlight them for the user.

Use this to show the user which body/face/occurrence you're referring to. After capture_design identifies a problem body, select it so the user can see which one.

Entities can be specified by name or by entityToken (from get_selection)."""

tool = Tool.create_simple(
    name="set_selection",
    description=TOOL_DESCRIPTION
).add_input_property(
    "action",
    {
        "type": "string",
        "enum": ["clear", "add", "set"],
        "default": "set",
        "description": "clear: deselect all. add: add to existing selection. set: clear first, then add."
    }
).add_input_property(
    "entities",
    {
        "type": "array",
        "description": "Entities to select. Each item: {\"type\": \"body\"|\"face\"|\"occurrence\", \"name\": \"Front\"} or {\"token\": \"abc123...\"}",
        "items": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["body", "face", "occurrence"]},
                "name": {"type": "string"},
                "token": {"type": "string"},
                "bodyName": {"type": "string", "description": "For face selection: the parent body name"},
                "faceIndex": {"type": "integer", "description": "For face selection: 0-based face index on the body"}
            }
        }
    }
)

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
