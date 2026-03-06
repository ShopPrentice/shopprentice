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
                # Store full 4x4 matrix for rotation support.
                # Row-major: [r00,r01,r02,tx, r10,r11,r12,ty, r20,r21,r22,tz, 0,0,0,1]
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


def _capture_sketches(design):
    """Capture all visible sketch curves and profiles (lightweight)."""
    sketches = []
    def walk_comp(comp):
        for si in range(comp.sketches.count):
            sk = comp.sketches.item(si)
            sk_info = {"name": sk.name, "component": comp.name}
            # Sketch coordinate system for world-space transform
            try:
                o = sk.origin
                sk_info["sketchOrigin"] = [round(o.x, 4), round(o.y, 4), round(o.z, 4)]
                xd = sk.xDirection
                sk_info["sketchXDir"] = [round(xd.x, 4), round(xd.y, 4), round(xd.z, 4)]
                yd = sk.yDirection
                sk_info["sketchYDir"] = [round(yd.x, 4), round(yd.y, 4), round(yd.z, 4)]
            except:
                pass
            # Curves
            curves = []
            for ci in range(sk.sketchCurves.count):
                c = sk.sketchCurves.item(ci)
                line = adsk.fusion.SketchLine.cast(c)
                if line:
                    curves.append({
                        "type": "Line",
                        "start": [round(line.startSketchPoint.geometry.x, 4),
                                  round(line.startSketchPoint.geometry.y, 4)],
                        "end": [round(line.endSketchPoint.geometry.x, 4),
                                round(line.endSketchPoint.geometry.y, 4)],
                        "isReference": line.isReference,
                    })
                    continue
                arc = adsk.fusion.SketchArc.cast(c)
                if arc:
                    curves.append({
                        "type": "Arc",
                        "center": [round(arc.centerSketchPoint.geometry.x, 4),
                                   round(arc.centerSketchPoint.geometry.y, 4)],
                        "start": [round(arc.startSketchPoint.geometry.x, 4),
                                  round(arc.startSketchPoint.geometry.y, 4)],
                        "end": [round(arc.endSketchPoint.geometry.x, 4),
                                round(arc.endSketchPoint.geometry.y, 4)],
                        "isReference": arc.isReference,
                    })
                    continue
                spline = adsk.fusion.SketchFittedSpline.cast(c)
                if spline:
                    pts = []
                    for fi in range(spline.fitPoints.count):
                        fp = spline.fitPoints.item(fi)
                        pts.append([round(fp.geometry.x, 4), round(fp.geometry.y, 4)])
                    curves.append({
                        "type": "FittedSpline",
                        "fitPoints": pts,
                    })
                    continue
                circle = adsk.fusion.SketchCircle.cast(c)
                if circle:
                    curves.append({
                        "type": "Circle",
                        "center": [round(circle.centerSketchPoint.geometry.x, 4),
                                   round(circle.centerSketchPoint.geometry.y, 4)],
                        "radius": round(circle.radius, 4),
                    })
                    continue
            sk_info["curves"] = curves
            # Profile bounding boxes
            profiles = []
            for pi in range(sk.profiles.count):
                try:
                    p = sk.profiles.item(pi)
                    bb = p.boundingBox
                    profiles.append({
                        "index": pi,
                        "min": [round(bb.minPoint.x, 4), round(bb.minPoint.y, 4)],
                        "max": [round(bb.maxPoint.x, 4), round(bb.maxPoint.y, 4)],
                    })
                except:
                    pass
            sk_info["profileCount"] = sk.profiles.count
            sk_info["profiles"] = profiles
            sketches.append(sk_info)
        for occ in comp.occurrences:
            walk_comp(occ.component)
    walk_comp(design.rootComponent)
    return sketches


def handler(index: int, include_sketches: bool = False, no_restore: bool = False) -> dict:
    """Roll timeline to index, capture bodies, restore (unless no_restore)."""

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
            adsk.doEvents()

            result = _capture_all_bodies(design.rootComponent)

            output = {
                    "index": index,
                    "markerPosition": target_position,
                    "timelineCount": tl.count,
                    "components": result,
            }
            if include_sketches:
                output["sketches"] = _capture_sketches(design)

            return {
                "content": [{"type": "text", "text": __import__('json').dumps(output, indent=2)}],
                "isError": False,
                "message": f"Captured state at timeline index {index}"
            }
        finally:
            if not no_restore:
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
).add_required_input("index").add_input_property(
    "include_sketches",
    {
        "type": "boolean",
        "description": "If true, also capture sketch curves and profile bboxes."
    }
).strict_schema()

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
