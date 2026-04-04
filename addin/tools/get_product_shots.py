"""
Get Product Shots Tool

Capture presentation-quality screenshots for README and documentation.
Automatically cleans up construction artifacts (planes, sketches, axes),
positions camera with FOV-aware framing, and captures multiple views
in a single call. Restores visibility state after capture.
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
import adsk.fusion

app = adsk.core.Application.get()

# Standard product shot views
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

# Default product shot set
_DEFAULT_VIEWS = ["iso-top-right", "front", "right"]


def _hide_construction(root_comp):
    """Hide all construction artifacts. Returns state for restore."""
    saved = {"sketches": [], "planes": [], "axes": []}

    def _process_comp(comp):
        for i in range(comp.sketches.count):
            sk = comp.sketches.item(i)
            saved["sketches"].append((sk, sk.isVisible))
            sk.isVisible = False
        for i in range(comp.constructionPlanes.count):
            cp = comp.constructionPlanes.item(i)
            saved["planes"].append((cp, cp.isLightBulbOn))
            cp.isLightBulbOn = False
        for i in range(comp.constructionAxes.count):
            ca = comp.constructionAxes.item(i)
            saved["axes"].append((ca, ca.isLightBulbOn))
            ca.isLightBulbOn = False

    _process_comp(root_comp)
    for occ in root_comp.allOccurrences:
        _process_comp(occ.component)

    return saved


def _restore_construction(saved):
    """Restore construction element visibility."""
    for sk, vis in saved["sketches"]:
        try:
            sk.isVisible = vis
        except Exception:
            pass
    for cp, vis in saved["planes"]:
        try:
            cp.isLightBulbOn = vis
        except Exception:
            pass
    for ca, vis in saved["axes"]:
        try:
            ca.isLightBulbOn = vis
        except Exception:
            pass


def _find_bodies_by_name(root_comp, names):
    """Find bodies by name across all components."""
    name_set = set(names)
    result = []
    for i in range(root_comp.bRepBodies.count):
        b = root_comp.bRepBodies.item(i)
        if b.name in name_set:
            result.append(b)
    for occ in root_comp.allOccurrences:
        for i in range(occ.component.bRepBodies.count):
            b = occ.component.bRepBodies.item(i)
            if b.name in name_set:
                result.append(b)
    return result


def _capture_one(viewport, width, height):
    """Save viewport to temp file and return file path (not base64)."""
    shots_dir = os.path.join(tempfile.gettempdir(), "shopprentice_shots")
    os.makedirs(shots_dir, exist_ok=True)
    timestamp = str(int(time.time() * 1000))
    image_path = os.path.join(shots_dir, f"product_{timestamp}.png")

    success = viewport.saveAsImageFile(image_path, width, height)

    if not success or not os.path.exists(image_path) or os.path.getsize(image_path) == 0:
        return None

    return image_path


def handler(views: list = None, width: int = 2048, height: int = 2048,
            bodies: list = None, fill: float = 0.80,
            style: str = "shaded-edges") -> dict:
    """Capture product-quality screenshots with artifact cleanup."""

    try:
        from helpers import sp

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

        # Resolve views
        view_list = views or _DEFAULT_VIEWS
        # Validate
        view_list = [v for v in view_list if v in _VIEW_DIRECTIONS]
        if not view_list:
            view_list = _DEFAULT_VIEWS

        # Resolve bodies for framing
        target_bodies = None
        if bodies:
            target_bodies = _find_bodies_by_name(root, bodies)
            if not target_bodies:
                target_bodies = None

        # Clean up construction artifacts
        saved_state = _hide_construction(root)

        # Set visual style
        style_map = {
            "shaded": adsk.core.VisualStyles.ShadedVisualStyle,
            "shaded-edges": adsk.core.VisualStyles.ShadedWithVisibleEdgesOnlyVisualStyle,
            "transparent": adsk.core.VisualStyles.ShadedWithHiddenEdgesVisualStyle,
            "wireframe": adsk.core.VisualStyles.WireframeVisualStyle,
        }
        original_style = viewport.visualStyle
        if style in style_map:
            viewport.visualStyle = style_map[style]

        # Capture each view
        results = []
        for view_name in view_list:
            eye_dir = _VIEW_DIRECTIONS[view_name]
            sp.screenshot_cam(eye_dir=eye_dir, bodies=target_bodies, fill=fill)
            # Let Fusion fully update the viewport before capturing
            import time
            adsk.doEvents()
            time.sleep(0.5)
            adsk.doEvents()

            path = _capture_one(viewport, width, height)
            if path:
                results.append({"view": view_name, "path": path})

        # Restore state
        viewport.visualStyle = original_style
        _restore_construction(saved_state)

        # Return file paths (not inline images) to avoid context bloat
        paths_text = "\n".join(f"  {r['view']}: {r['path']}" for r in results)
        msg = f"{len(results)} product shot(s) saved ({', '.join(view_list)}, {width}x{height})"
        return {
            "content": [{"type": "text", "text": f"{msg}\n{paths_text}\n\nUse Read tool to view any image."}],
            "isError": False,
            "message": msg
        }

    except Exception as e:
        # Restore on error
        try:
            app.activeViewport.visualStyle = adsk.core.VisualStyles.ShadedVisualStyle
        except Exception:
            pass
        try:
            _restore_construction(saved_state)
        except Exception:
            pass
        app.log(f"Error getting product shots: {e}\n{traceback.format_exc()}")
        return {
            "content": [{"type": "text", "text": f"Error: {e}\n{traceback.format_exc()}"}],
            "isError": True,
            "message": "Error getting product shots"
        }


TOOL_DESCRIPTION = \
"""Capture presentation-quality product screenshots for README/docs.

Automatically:
1. Hides construction artifacts (sketches, planes, axes)
2. Positions camera with FOV-aware framing (sp.screenshot_cam)
3. Captures multiple views in one call
4. Restores all visibility state after capture

Default: 3 views (iso-top-right, front, right) at 2048x2048.
Use after final validation + apply_appearance, before presenting to user."""

tool = Tool.create_simple(
    name="get_product_shots",
    description=TOOL_DESCRIPTION
).add_input_property(
    "views",
    {
        "description": "List of views to capture. Default: ['iso-top-right', 'front', 'right'].",
        "type": "array",
        "items": {
            "type": "string",
            "enum": ["iso-top-right", "iso-top-left", "iso-bottom-right",
                     "iso-bottom-left", "front", "back", "right", "left", "top", "bottom"]
        }
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
        "description": "Optional body names to frame. Camera zooms to their bounding box. Omit for all visible bodies.",
        "type": "array",
        "items": {"type": "string"}
    }
).add_input_property(
    "fill",
    {
        "description": "Fraction of frame to fill (0.0-1.0). Default 0.80. Use 0.90+ for detail shots, 0.60 for extra whitespace.",
        "type": "number",
        "default": 0.80
    }
).add_input_property(
    "style",
    {
        "description": "Visual style.",
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
