"""
Export Script Tool

Captures the active design and generates a standalone Fusion 360 Python script
that recreates the model. Uses capture_design internally, then runs the
template-based script generator.

The generated script is self-contained (no external dependencies), parametric
(preserves dimension expressions), and syntactically valid Python.
"""

import json
import traceback
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register

from .capture_design import handler as capture_handler
from ._script_generator import generate_script


def handler() -> dict:
    """Capture design and generate a reconstruction script."""
    try:
        # Step 1: Capture the design
        capture_result = capture_handler()
        if capture_result.get("isError"):
            return capture_result

        # Step 2: Parse the capture JSON
        capture_text = capture_result["content"][0]["text"]
        capture_data = json.loads(capture_text)

        # Step 3: Generate the script
        script = generate_script(capture_data)

        design_name = capture_data.get("designName", "Untitled")
        tl_count = len(capture_data.get("timeline", []))
        param_count = len(capture_data.get("userParameters", []))

        return {
            "content": [{"type": "text", "text": script}],
            "isError": False,
            "message": (
                f"Generated script for '{design_name}': "
                f"{tl_count} features, {param_count} parameters, "
                f"{len(script.splitlines())} lines"
            ),
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {e}\n{traceback.format_exc()}"}],
            "isError": True,
            "message": "export_script failed",
        }


TOOL_DESCRIPTION = """\
Capture the active Fusion 360 design and generate a standalone Python script that recreates it.

The generated script:
- Is self-contained (no external imports beyond adsk)
- Preserves all user parameter expressions (parametric)
- Reconstructs the timeline: sketches, extrudes, construction planes, mirrors, combines, sweeps, splits, fillets
- Marks features that need manual review with TODO comments

Use this to reverse-engineer a hand-built design into a reproducible script. The output can be
executed via execute_script or saved to a file for further editing by the agent."""

tool = Tool.create_simple(
    name="export_script",
    description=TOOL_DESCRIPTION,
).strict_schema()

item = Item.create_tool_item(
    tool=tool,
    handler=handler,
)

register(item)
