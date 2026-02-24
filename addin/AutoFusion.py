"""
AutoFusion Add-in for Fusion 360

Provides MCP-compatible JSON-RPC tools for design introspection,
timeline state capture, script execution, and viewport screenshots.
"""

import traceback
import adsk.core
import adsk.fusion
from .server.mcp_server import start_mcp_server, stop_mcp_server
from .primitives.registry import get_tools, get_resources
from .server.task_manager import TaskManager
# Import tools to register them
from . import tools

# Global variables
app = adsk.core.Application.get()
ui = app.userInterface
mcp = None
server = None
thread = None

HOST = 'localhost'
PORT = 9100


def run(context):
    """Called when add-in starts"""

    try:
        global app, mcp, server, thread, ui

        TaskManager.start()

        registered_tools = get_tools()
        registered_resources = get_resources()
        mcp, server, thread = start_mcp_server(
            host=HOST,
            port=PORT,
            tools=registered_tools,
            resources=registered_resources
        )

        if mcp:
            app.log(
                f"AutoFusion started successfully!\n\n"
                f"MCP server running on {HOST}:{PORT}\n"
                f"Tools: {len(registered_tools)}"
            )
        else:
            if ui:
                ui.messageBox("Failed to start AutoFusion")
            if app:
                app.log("Failed to start AutoFusion")
    except Exception:
        app.log(f'Failed to start AutoFusion:\n{traceback.format_exc()}')


def stop(context):
    """Called when add-in stops"""

    try:
        TaskManager.stop()

        if stop_mcp_server(server, thread):
            if app:
                app.log("AutoFusion stopped successfully.")
        else:
            if app:
                app.log("Error stopping AutoFusion")

    except Exception:
        if app:
            app.log(f"Error stopping AutoFusion:\n{traceback.format_exc()}")
