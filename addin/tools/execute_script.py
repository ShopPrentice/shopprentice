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


def handler(script: str) -> dict:
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

    temp_file = None
    transaction_started = False
    transacted_doc = None
    try:
        script += "\nrun(None)"

        with tempfile.NamedTemporaryFile(mode='w', prefix='script', suffix='.py', delete=False) as f:
            f.write(script)
            temp_file = f.name

        try:
            transacted_doc = app.activeDocument
        except:
            app.log("No active document to transact")
        if transacted_doc:
            app.executeTextCommand('PTransaction.Start "Execute Prompt Script"')
            transaction_started = True

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
DO take a screenshot before editing an existing document to understand the model.
DO take a screenshot after making changes to ensure the changes worked as expected.
DO use `print()` statements to return any information or values from the script through the `result` field in the response.

MAKE SURE the script defines a "run" function that will be run. For example:
    ```python
    def run(context):
        print("result value")
    ```

IMPORTANT! DO NOT handle exceptions. Let them be raised to Fusion so that changes already made in the script are aborted, and so the error message and location is returned to the agent.

DO refer to the documentation of the Fusion API by searching in the Python module files located in the "{def_file_path}" folder.
"""

tool = Tool.create_with_string_input(
    name="execute_script",
    description=TOOL_DESCRIPTION,
    input_param_name="script",
    input_param_description="Fusion API Python script source code to execute."
)

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
