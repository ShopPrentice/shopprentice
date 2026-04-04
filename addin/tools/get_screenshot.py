"""
Get Screenshot Tool

Quick viewport capture for build validation. Low overhead — captures
whatever Fusion is currently showing. Use during incremental builds
to verify geometry visually.

For final product shots, use get_product_shots instead.
"""

import base64
import traceback
import time
import tempfile
import os
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register
import adsk.core

app = adsk.core.Application.get()

# Eye directions for screenshot_cam
_VIEW_DIRECTIONS = {
    "iso-top-right":    ( 1, -1,  0.7),
    "iso-top-left":     (-1, -1,  0.7),
    "front":            ( 0, -1,  0),
    "back":             ( 0,  1,  0),
    "right":            ( 1,  0,  0),
    "left":             (-1,  0,  0),
    "top":              ( 0,  0,  1),
    "bottom":           ( 0,  0, -1),
}


def handler(view: str = "current", width: int = 1024, height: int = 1024) -> dict:
    """Quick screenshot for build validation."""

    try:
        viewport = app.activeViewport

        # Parse dimensions
        try:
            width = int(width) if isinstance(width, str) else width
        except (ValueError, TypeError):
            width = 1024
        try:
            height = int(height) if isinstance(height, str) else height
        except (ValueError, TypeError):
            height = 1024

        # Position camera if a named view is requested
        if view and view != "current":
            eye_dir = _VIEW_DIRECTIONS.get(view)
            if eye_dir:
                from helpers import sp
                sp.screenshot_cam(eye_dir=eye_dir, fill=0.80)
                adsk.doEvents()
            else:
                # Fallback: just fit view
                cam = viewport.camera
                cam.isFitView = True
                viewport.camera = cam

        # Capture to file (not inline base64 — saves context tokens)
        shots_dir = os.path.join(tempfile.gettempdir(), "shopprentice_shots")
        os.makedirs(shots_dir, exist_ok=True)
        timestamp = str(int(time.time() * 1000))
        image_path = os.path.join(shots_dir, f"screenshot_{timestamp}.png")

        success = viewport.saveAsImageFile(image_path, width, height)

        if not success or not os.path.exists(image_path) or os.path.getsize(image_path) == 0:
            return {
                "content": [{"type": "text", "text": "Failed to save screenshot"}],
                "isError": True,
                "message": "Failed to save screenshot"
            }

        return {
            "content": [{"type": "text", "text": f"Screenshot saved: {image_path}\n\nUse Read tool to view."}],
            "isError": False,
            "message": f"Screenshot saved ({view}, {width}x{height}): {image_path}"
        }
    except Exception as e:
        app.log(f"Error getting screenshot: {e}\n{traceback.format_exc()}")
        return {
            "content": [{"type": "text", "text": f"Error: {e}\n{traceback.format_exc()}"}],
            "isError": True,
            "message": "Error getting screenshot"
        }


TOOL_DESCRIPTION = \
"""Quick viewport screenshot for build validation.

Captures the current Fusion viewport as-is (construction planes,
sketches, and all). Use during incremental builds to verify geometry.

For final product shots (high-res, cleaned up, multiple views),
use get_product_shots instead."""

tool = Tool.create_simple(
    name="get_screenshot",
    description=TOOL_DESCRIPTION
).add_input_property(
    "view",
    {
        "description": "Camera direction. 'current' captures as-is.",
        "type": "string",
        "enum": ["current", "iso-top-right", "iso-top-left",
                 "front", "back", "right", "left", "top", "bottom"],
        "default": "current"
    }
).add_input_property(
    "width",
    {
        "description": "Image width in pixels.",
        "type": "integer",
        "minimum": 1,
        "maximum": 4096,
        "default": 1024
    }
).add_input_property(
    "height",
    {
        "description": "Image height in pixels.",
        "type": "integer",
        "minimum": 1,
        "maximum": 4096,
        "default": 1024
    }
)

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
