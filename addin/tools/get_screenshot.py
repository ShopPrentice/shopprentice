"""
Get Screenshot Tool

Capture product-quality viewport screenshots with proper camera framing.
Uses af.screenshot_cam() internally to compute FOV-aware camera positioning
so the model fills the frame correctly.
"""

import base64
import math
import traceback
import time
import tempfile
import os
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register
import adsk.core
import adsk.fusion

app = adsk.core.Application.get()

# Named views → eye direction vectors for screenshot_cam
_VIEW_DIRECTIONS = {
    "iso-top-right":    ( 1, -1,  0.7),
    "iso-top-left":     (-1, -1,  0.7),
    "iso-bottom-right": ( 1, -1, -0.7),
    "iso-bottom-left":  (-1, -1, -0.7),
    "front":            ( 0, -1,  0),
    "back":             ( 0,  1,  0),
    "right":            ( 1,  0,  0),
    "left":             (-1,  0,  0),
    "top":              ( 0,  0,  1),
    "bottom":           ( 0,  0, -1),
}


def _find_bodies_by_name(root_comp, names):
    """Find bodies by name across all components."""
    name_set = set(names)
    result = []
    for i in range(root_comp.bRepBodies.count):
        b = root_comp.bRepBodies.item(i)
        if b.name in name_set:
            result.append(b)
    for occ in root_comp.allOccurrences:
        comp = occ.component
        for i in range(comp.bRepBodies.count):
            b = comp.bRepBodies.item(i)
            if b.name in name_set:
                result.append(b)
    return result


def handler(view: str = "iso-top-right", width: int = 2048, height: int = 2048,
            bodies: list = None, fill: float = 0.80,
            style: str = "shaded") -> dict:
    """Capture a product-quality screenshot with proper camera framing."""

    try:
        from helpers import af

        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return {
                "content": [{"type": "text", "text": "No active design"}],
                "isError": True,
                "message": "No active design"
            }

        root = design.rootComponent
        viewport = app.activeViewport

        # Parse dimensions
        try:
            width = int(width) if isinstance(width, str) else width
        except (ValueError, TypeError):
            width = 2048
        try:
            height = int(height) if isinstance(height, str) else height
        except (ValueError, TypeError):
            height = 2048

        # Set visual style
        style_map = {
            "shaded": adsk.core.VisualStyles.ShadedVisualStyle,
            "transparent": adsk.core.VisualStyles.ShadedWithHiddenEdgesVisualStyle,
            "wireframe": adsk.core.VisualStyles.WireframeVisualStyle,
        }
        if style in style_map:
            viewport.visualStyle = style_map[style]

        # Resolve bodies for framing
        target_bodies = None
        if bodies:
            target_bodies = _find_bodies_by_name(root, bodies)
            if not target_bodies:
                target_bodies = None  # fallback to all bodies

        # Position camera using screenshot_cam
        eye_dir = _VIEW_DIRECTIONS.get(view)
        if eye_dir:
            af.screenshot_cam(eye_dir=eye_dir, bodies=target_bodies, fill=fill)
            adsk.doEvents()
        else:
            # "current" — just fit view
            cam = viewport.camera
            cam.isFitView = True
            viewport.camera = cam

        # Capture
        timestamp = str(int(time.time() * 1000))
        with tempfile.NamedTemporaryFile(
                prefix=f'autofusion_screenshot_{timestamp}_',
                suffix='.png', delete=False) as temp_file:
            image_path = os.path.abspath(temp_file.name)

        success = viewport.saveAsImageFile(image_path, width, height)

        # Reset visual style to shaded if we changed it
        if style != "shaded":
            viewport.visualStyle = adsk.core.VisualStyles.ShadedVisualStyle

        if not success or not os.path.exists(image_path):
            return {
                "content": [{"type": "text", "text": "Failed to save screenshot"}],
                "isError": True,
                "message": "Failed to save screenshot"
            }

        file_size = os.path.getsize(image_path)
        if file_size == 0:
            return {
                "content": [{"type": "text", "text": "Screenshot file is empty"}],
                "isError": True,
                "message": "Screenshot file is empty"
            }

        with open(image_path, 'rb') as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        try:
            os.unlink(image_path)
        except Exception:
            pass

        return {
            "content": [
                {
                    "type": "image",
                    "data": base64_image,
                    "mimeType": "image/png",
                    "width": width,
                    "height": height,
                    "view": view
                }
            ],
            "isError": False,
            "message": f"Screenshot captured ({view}, {width}x{height})"
        }
    except Exception as e:
        # Reset visual style on error
        try:
            app.activeViewport.visualStyle = adsk.core.VisualStyles.ShadedVisualStyle
        except Exception:
            pass
        app.log(f"Error getting screenshot: {e}\n{traceback.format_exc()}")
        return {
            "content": [{"type": "text", "text": f"Error: {e}\n{traceback.format_exc()}"}],
            "isError": True,
            "message": "Error getting screenshot"
        }


# Tool definition

TOOL_DESCRIPTION = \
"""Capture a product-quality screenshot with proper camera framing.

Uses FOV-aware camera positioning (af.screenshot_cam) to compute the exact
camera distance so the model fills the frame correctly. No manual camera
setup needed — just specify the view direction.

Defaults to 2048x2048, iso-top-right view, 80% fill. For detail shots,
pass specific body names to frame only those bodies."""

tool = Tool.create_simple(
    name="get_screenshot",
    description=TOOL_DESCRIPTION
).add_input_property(
    "view",
    {
        "description": "Camera direction. Named views use FOV-aware framing.",
        "type": "string",
        "enum": ["current", "iso-top-right", "iso-top-left", "iso-bottom-right",
                 "iso-bottom-left", "front", "back", "right", "left", "top", "bottom"],
        "default": "iso-top-right"
    }
).add_input_property(
    "width",
    {
        "description": "Image width in pixels.",
        "type": "integer",
        "minimum": 1,
        "maximum": 4096,
        "default": 2048
    }
).add_input_property(
    "height",
    {
        "description": "Image height in pixels.",
        "type": "integer",
        "minimum": 1,
        "maximum": 4096,
        "default": 2048
    }
).add_input_property(
    "bodies",
    {
        "description": "Optional list of body names to frame. Camera zooms to their bounding box. Omit to frame all visible bodies.",
        "type": "array",
        "items": {"type": "string"}
    }
).add_input_property(
    "fill",
    {
        "description": "Fraction of frame the subject should fill (0.0-1.0). Default 0.80. Use 0.90 for tight detail shots, 0.70 for overview with breathing room.",
        "type": "number",
        "default": 0.80
    }
).add_input_property(
    "style",
    {
        "description": "Visual style for the screenshot.",
        "type": "string",
        "enum": ["shaded", "transparent", "wireframe"],
        "default": "shaded"
    }
)

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
