"""
Execute Script Tool

Execute Fusion API Python scripts within a transaction.
Adapted from Fusion MCP Addin's execute_api_script.
"""

import os
import re
import tempfile
import traceback
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register
import adsk.core

app = adsk.core.Application.get()


def _execute_sandbox(script):
    """Run script in a throwaway document and return a design snapshot."""
    import adsk.fusion
    from server.action_log import ActionLog
    from tools.get_changes import _capture_snapshot

    temp_file = None
    temp_doc = None
    original_doc = None
    transaction_started = False

    try:
        ActionLog._suppress = True

        original_doc = app.activeDocument

        # Create throwaway document
        temp_doc = app.documents.add(
            adsk.core.DocumentTypes.FusionDesignDocumentType)
        design = adsk.fusion.Design.cast(app.activeProduct)
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType

        app.executeTextCommand('PTransaction.Start "Sandbox Script"')
        transaction_started = True

        script += "\nrun(None)"
        with tempfile.NamedTemporaryFile(
                mode='w', prefix='sandbox_', suffix='.py',
                delete=False, encoding='utf-8') as f:
            f.write(script)
            temp_file = f.name

        res = app.executeTextCommand(f'Python.Run "{temp_file}"')

        # Commit so geometry computes before snapshotting
        app.executeTextCommand('PTransaction.Commit')
        transaction_started = False

        # Force B-Rep evaluation before snapshot (volume needs computed geometry)
        adsk.doEvents()

        snapshot = _capture_snapshot(design)

        # Close temp doc without saving
        temp_doc.close(False)
        temp_doc = None

        # Restore original document
        if original_doc and original_doc.isValid:
            original_doc.activate()

        result = {
            "sandbox": True,
            "snapshot": snapshot,
            "isError": False,
            "message": "Sandbox script executed successfully"
        }
        if res:
            result["content"] = [{"type": "text", "text": res}]
        return result

    except Exception as e:
        if transaction_started:
            try:
                app.executeTextCommand('PTransaction.Abort')
            except Exception:
                pass

        if temp_doc and temp_doc.isValid:
            try:
                temp_doc.close(False)
            except Exception:
                pass

        if original_doc and original_doc.isValid:
            try:
                original_doc.activate()
            except Exception:
                pass

        tb = traceback.format_exc()
        app.log(f"Sandbox error: {e}:\n{tb}")
        return {
            "sandbox": True,
            "content": [{"type": "text", "text": tb}],
            "isError": True,
            "message": "Sandbox script execution failed"
        }
    finally:
        ActionLog._suppress = False
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except Exception:
                pass


def _clean_design():
    """Delete all timeline features and user parameters from the active design."""
    import adsk.fusion
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        return

    # Delete timeline features in reverse order (later features depend on earlier ones)
    tl = design.timeline
    for i in range(tl.count - 1, -1, -1):
        try:
            item = tl.item(i)
            entity = item.entity
            if entity and hasattr(entity, 'deleteMe'):
                entity.deleteMe()
        except Exception:
            pass

    # Delete user parameters
    params = design.userParameters
    for i in range(params.count - 1, -1, -1):
        try:
            params.item(i).deleteMe()
        except Exception:
            pass


def handler(script: str, sandbox: bool = False, clean: bool = False) -> dict:
    """Execute a Fusion API Python script."""

    run_function_match = re.search(r'def\s+run\s*\(\s*(\w+)\s*\):', script)
    if not run_function_match:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Script does not have a run function that takes a single argument"
                }
            ],
            "isError": True,
            "message": "Script does not have a run function that takes a single argument",
        }

    if sandbox:
        return _execute_sandbox(script)

    temp_file = None
    transaction_started = False
    transacted_doc = None
    original_script = script  # preserve before appending run(None)
    try:
        script += "\nrun(None)"

        with tempfile.NamedTemporaryFile(mode='w', prefix='script', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(script)
            temp_file = f.name

        try:
            transacted_doc = app.activeDocument
        except:
            app.log("No active document to transact")
        if transacted_doc:
            app.executeTextCommand('PTransaction.Start "Execute Prompt Script"')
            transaction_started = True

        # Clean existing model before rebuilding (all in one transaction for Ctrl+Z revert)
        if clean and transaction_started:
            _clean_design()

        res = app.executeTextCommand(f'Python.Run "{temp_file}"')

        if transaction_started and transacted_doc.isValid:
            current_doc = app.activeDocument
            if current_doc is transacted_doc:
                app.executeTextCommand('PTransaction.Commit')
            else:
                app.log("Active document has changed since transaction started")
                transacted_doc.activate()
                app.executeTextCommand('PTransaction.Commit')
                current_doc.activate()

        # Reset ActionLog so future get_changes calls start from a clean baseline
        try:
            from server.action_log import ActionLog
            ActionLog.reset()
        except Exception:
            pass

        # Track document provenance
        try:
            from server.document_tracker import DocumentTracker
            DocumentTracker.on_script_executed(original_script, app.activeDocument)
        except Exception:
            pass

        result = {
            "isError": False,
            "message": "Script executed successfully"
        }
        if res:
            result["content"] = [
                {
                    "type": "text",
                    "text": res
                }
            ]
        return result
    except Exception as e:
        if transaction_started and transacted_doc.isValid:
            try:
                current_doc = app.activeDocument
                if current_doc is transacted_doc:
                    app.executeTextCommand('PTransaction.Abort')
                else:
                    app.log("Active document has changed since transaction started")
                    transacted_doc.activate()
                    app.executeTextCommand('PTransaction.Abort')
                    current_doc.activate()
            except Exception:
                pass
        res = traceback.format_exc()
        app.log(f"Error executing script: {e}:\n{res}")
        return {
            "content": [
                {
                    "type": "text",
                    "text": res
                }
            ],
            "isError": True,
            "message": "Script execution failed"
        }
    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except Exception:
                pass


# Tool definition

def_file_path = os.path.realpath(os.path.join(app.applicationFolders.defaultPathForScriptsAndAddIns, 'Python/defs/adsk'))

TOOL_DESCRIPTION = \
f"""Execute Fusion API Python script source code.

IMPORTANT! DO NOT present any UI with a `messageBox`.
IMPORTANT! DO NOT catch any errors unless you want to ignore an error. Or use a `print()` statment with the specific error so you can determine what the error is.
DO use `print()` statements to return any information or values from the script through the `result` field in the response.

MAKE SURE the script defines a "run" function that will be run. For example:
    ```python
    def run(context):
        print("result value")
    ```

IMPORTANT! DO NOT handle exceptions. Let them be raised to Fusion so that changes already made in the script are aborted, and so the error message and location is returned to the agent.

DO refer to the documentation of the Fusion API by searching in the Python module files located in the "{def_file_path}" folder.

Workflow: Build complex models in phases (Structure → Joinery → Details). After each successful execution, call capture_design to validate body count and positions before proceeding to the next phase. On error, analyze the stack trace, fix the script, and re-execute (max 3 retries per distinct error). Failed scripts are automatically rolled back.

Helper library: Scripts can `from helpers import af` to use shared utilities:
- `af.DesignContext()` — replaces app/design/root/params/ev boilerplate
- `af.find_face(body, axis, direction)` — outermost planar face along axis
- `af.find_face_at(body, axis, position)` — planar face at specific coordinate
- `af.sketch_rect(comp, plane, ...)` — parametric rectangle with H/V constraints
- `af.sketch_rect_model(comp, plane, ...)` — parametric rectangle on any plane
- `af.probe_sketch_axes(sk)` — detect model axis → sketch H/V mapping
- `af.smallest_profile(sk)` — smallest-area profile in a sketch

Sandbox mode: Set sandbox=true to run the script in a temporary document. Returns a design snapshot without modifying the user's active document. Useful for validating scripts before committing to the real design.

Clean rebuild: Set clean=true to delete all existing timeline features and user parameters before running the script. The clean step and script execution are wrapped in a single transaction — the user can Ctrl+Z to revert the entire operation back to the previous model state. Use this when re-executing a modified script on a document that already has a model.
"""

tool = Tool.create_simple(
    name="execute_script",
    description=TOOL_DESCRIPTION
).add_input_property(
    "script", {"type": "string", "description": "Fusion API Python script source code to execute."}
).add_input_property(
    "sandbox", {
        "type": "boolean",
        "description": "Run in a temporary document. Returns design snapshot without modifying the user's active document."
    }
).add_input_property(
    "clean", {
        "type": "boolean",
        "description": "Delete all existing features and parameters before running. Enables clean rebuild of an existing model. Ctrl+Z reverts the entire operation."
    }
).add_required_input("script").strict_schema()

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
