"""
Get Timeline State Tool

Roll the timeline to a specific index, capture all body geometry at that
point, then restore the timeline position. This eliminates the need for
the headless simulator.

Parameters:
    index: 0-based timeline index (-1 for end of timeline)

Returns:
    Component tree with per-body volume and bounding box at that timeline point.
"""

import traceback
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register
import adsk.core
import adsk.fusion

app = adsk.core.Application.get()


def _capture_body(body):
    """Capture a single body's geometry."""
    info = {"name": body.name}
    try:
        info["volume"] = round(body.volume, 4)
    except:
        pass
    try:
        bb = body.boundingBox
        info["boundingBox"] = {
            "min": [round(bb.minPoint.x, 4), round(bb.minPoint.y, 4), round(bb.minPoint.z, 4)],
            "max": [round(bb.maxPoint.x, 4), round(bb.maxPoint.y, 4), round(bb.maxPoint.z, 4)],
        }
    except:
        pass
    return info


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


def handler(index: int) -> dict:
    """Roll timeline to index, capture bodies, restore."""

    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return {
                "content": [{"type": "text", "text": "No active design"}],
                "isError": True,
                "message": "No active design"
            }

        tl = design.timeline
        original = tl.markerPosition

        # Convert string to int if needed (JSON-RPC may send strings)
        try:
            index = int(index)
        except (ValueError, TypeError):
            return {
                "content": [{"type": "text", "text": f"Invalid index: {index}"}],
                "isError": True,
                "message": f"Invalid index: {index}"
            }

        # Handle -1 = end of timeline
        if index == -1:
            target_position = tl.count
        else:
            # markerPosition is 1-based "after index", so index+1
            target_position = index + 1

        # Validate range
        if target_position < 0 or target_position > tl.count:
            return {
                "content": [{"type": "text", "text": f"Index {index} out of range (timeline has {tl.count} items)"}],
                "isError": True,
                "message": f"Index out of range"
            }

        try:
            tl.markerPosition = target_position
            adsk.doEvents()  # wait for recompute

            result = _capture_all_bodies(design.rootComponent)

            return {
                "content": [{"type": "text", "text": __import__('json').dumps({
                    "index": index,
                    "markerPosition": target_position,
                    "timelineCount": tl.count,
                    "components": result,
                }, indent=2)}],
                "isError": False,
                "message": f"Captured state at timeline index {index}"
            }
        finally:
            tl.markerPosition = original
            adsk.doEvents()

    except Exception as e:
        app.log(f"get_timeline_state error: {e}\n{traceback.format_exc()}")
        return {
            "content": [{"type": "text", "text": f"Error: {e}\n{traceback.format_exc()}"}],
            "isError": True,
            "message": "get_timeline_state failed"
        }


# Tool definition

TOOL_DESCRIPTION = \
"""Roll the design timeline to a specific index and capture all body geometry (volume + bounding box) at that point, then restore the original position.

Parameters:
- index: 0-based timeline index. Use -1 for end of timeline (fully computed state).

Returns the component tree with per-body volume and bounding box at the specified timeline point.

Workflow: This is a diagnostic tool. When capture_design reveals unexpected state (wrong body count, bad positions, missing bodies), use this to binary-search the timeline and pinpoint which feature went wrong. Call at the midpoint, check body count, narrow forward or backward until you find the exact feature that broke the model."""

tool = Tool.create_simple(
    name="get_timeline_state",
    description=TOOL_DESCRIPTION
).add_input_property(
    "index",
    {
        "type": "integer",
        "description": "0-based timeline index. Use -1 for end of timeline."
    }
).add_required_input("index").strict_schema()

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
