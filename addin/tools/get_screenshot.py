"""
Get Screenshot Tool

Capture viewport screenshots with optional camera orientation.
Adapted from Fusion MCP Addin's get_screenshot.
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
from adsk.core import ViewOrientations

app = adsk.core.Application.get()


def handler(view: str = "current", width: int = 512, height: int = 512) -> dict:
    """Capture a screenshot of the current Fusion 360 viewport."""

    try:
        app.log(f"Getting screenshot: view: {view}, width: {width}, height: {height}")

        try:
            width = int(width) if isinstance(width, str) else width
        except (ValueError, TypeError):
            width = 512
        try:
            height = int(height) if isinstance(height, str) else height
        except (ValueError, TypeError):
            height = 512

        orientation_map = {
            'top': ViewOrientations.TopViewOrientation,
            'bottom': ViewOrientations.BottomViewOrientation,
            'front': ViewOrientations.FrontViewOrientation,
            'back': ViewOrientations.BackViewOrientation,
            'left': ViewOrientations.LeftViewOrientation,
            'right': ViewOrientations.RightViewOrientation,
            'iso-top-left': ViewOrientations.IsoTopLeftViewOrientation,
            'iso-top-right': ViewOrientations.IsoTopRightViewOrientation,
            'iso-bottom-left': ViewOrientations.IsoBottomLeftViewOrientation,
            'iso-bottom-right': ViewOrientations.IsoBottomRightViewOrientation,
        }
        orientation = orientation_map.get(view, ViewOrientations.IsoTopLeftViewOrientation)
        viewport = app.activeViewport

        if view and view != "current":
            camera = viewport.camera
            camera.viewOrientation = orientation
            viewport.camera = camera

            start_time = time.time()
            while time.time() - start_time < 1.0:
                adsk.doEvents()

            camera = viewport.camera
            camera.isFitView = True
            viewport.camera = camera

        timestamp = str(int(time.time() * 1000))
        with tempfile.NamedTemporaryFile(prefix=f'autofusion_screenshot_{timestamp}_', suffix='.png',
                                         delete=False) as temp_file:
            image_path = os.path.abspath(temp_file.name)

        success = viewport.saveAsImageFile(image_path, width, height)

        if not success:
            return {
                "content": [{"type": "text", "text": "Failed to save screenshot"}],
                "isError": True,
                "message": "Failed to save screenshot"
            }

        if not os.path.exists(image_path):
            return {
                "content": [{"type": "text", "text": f"Screenshot file not created: {image_path}"}],
                "isError": True,
                "message": f"Screenshot file not created: {image_path}"
            }

        file_size = os.path.getsize(image_path)
        if file_size == 0:
            return {
                "content": [{"type": "text", "text": "Screenshot file is empty"}],
                "isError": True,
                "message": "Screenshot file is empty"
            }

        with open(image_path, 'rb') as image_file:
            image_data = image_file.read()
            base64_image = base64.b64encode(image_data).decode('utf-8')

        try:
            os.unlink(image_path)
        except:
            pass

        return {
            "content": [
                {
                    "type": "image",
                    "data": base64_image,
                    "mimeType": 'image/png',
                    "width": width,
                    "height": height,
                    "view": view
                }
            ],
            "isError": False,
            "message": "Screenshot captured"
        }
    except Exception as e:
        app.log(f"Error getting screenshot: {e}\n{traceback.format_exc()}")
        return {
            "content": [{"type": "text", "text": str(e)}],
            "isError": True,
            "message": "Error getting screenshot"
        }


# Tool definition

TOOL_DESCRIPTION = \
"""Get a screenshot of the current Fusion view.
Use the `view` param to get a specific view orientation.

DO take a screenshot before editing an existing document to understand the current state.
DO take a screenshot after executing a script to make changes to ensure the changes are what you expect."""

tool = Tool.create_simple(
    name="get_screenshot",
    description=TOOL_DESCRIPTION
).add_input_property(
    "view",
    {
        "description": "Sets the camera orientation to use.",
        "type": "string",
        "enum": ["current", "top", "bottom", "front", "back", "left", "right", "iso-top-left", "iso-top-right", "iso-bottom-left", "iso-bottom-right"],
        "default": "current"
    }
).add_input_property(
    "width",
    {
        "description": "The width of the screenshot in pixels.",
        "type": "integer",
        "minimum": 1,
        "maximum": 4096,
        "default": 512
    }
).add_input_property(
    "height",
    {
        "description": "The height of the screenshot in pixels.",
        "type": "integer",
        "minimum": 1,
        "maximum": 4096,
        "default": 512
    }
)

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
