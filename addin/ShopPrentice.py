"""
ShopPrentice Add-in for Fusion 360

Provides MCP-compatible JSON-RPC tools for design introspection,
timeline state capture, script execution, and viewport screenshots.
"""

import os
import sys
import traceback

# Ensure the addin directory is on sys.path so absolute imports resolve
# when Fusion 360 loads this file directly (no parent package context).
_addin_dir = os.path.dirname(os.path.abspath(__file__))
if _addin_dir not in sys.path:
    sys.path.insert(0, _addin_dir)

# Also add repo root so scripts can import from woodworking/templates/
_repo_root = os.path.dirname(os.path.realpath(_addin_dir))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import adsk.core
import adsk.fusion

# Global variables
app = adsk.core.Application.get()
ui = app.userInterface
mcp = None
server = None
thread = None

HOST = 'localhost'
PORT = 9100


def _reload_modules():
    """Flush and re-import tools, primitives, and server modules.

    Ensures a clean slate on every run(), even if a previous stop()
    corrupted module state by partially flushing sys.modules.
    """
    # Flush tools, primitives, server (children first, then parents)
    prefixes = ('tools', 'primitives', 'server', 'helpers', 'palette')
    to_remove = sorted(
        [k for k in sys.modules
         if any(k == p or k.startswith(p + '.') for p in prefixes)],
        key=lambda k: k.count('.'), reverse=True)
    for mod_name in to_remove:
        sys.modules.pop(mod_name, None)

    # Re-import primitives first (creates fresh singleton registry)
    import primitives.registry  # noqa: F811

    # Re-import tools (triggers module-level register() calls)
    import tools  # noqa: F811

    # Return fresh references from the newly imported modules
    return (
        primitives.registry.get_tools(),
        primitives.registry.get_resources(),
    )


def run(context):
    """Called when add-in starts"""

    try:
        global app, mcp, server, thread, ui

        registered_tools, registered_resources = _reload_modules()

        # Re-import server modules (also flushed above)
        from server.mcp_server import start_mcp_server
        from server.task_manager import TaskManager

        TaskManager.start()

        from server.action_log import ActionLog
        ActionLog.start()

        from server.session_manager import SessionManager
        SessionManager.instance().start()

        mcp, server, thread = start_mcp_server(
            host=HOST,
            port=PORT,
            tools=registered_tools,
            resources=registered_resources
        )

        # Create parameter editor palette
        from palette.param_editor import ParamEditorPalette
        ParamEditorPalette.create()

        # Store MCP ref for hot-reload access
        sys._shopprentice_mcp = mcp

        if mcp:
            app.log(
                f"ShopPrentice started successfully!\n\n"
                f"MCP server running on {HOST}:{PORT}\n"
                f"Tools: {len(registered_tools)}"
            )
        else:
            if ui:
                ui.messageBox("Failed to start ShopPrentice")
            if app:
                app.log("Failed to start ShopPrentice")
    except Exception:
        app.log(f'Failed to start ShopPrentice:\n{traceback.format_exc()}')


def stop(context):
    """Called when add-in stops"""

    try:
        from server.action_log import ActionLog
        from server.task_manager import TaskManager
        from server.mcp_server import stop_mcp_server

        from palette.param_editor import ParamEditorPalette
        ParamEditorPalette.destroy()

        try:
            from server.session_manager import SessionManager
            SessionManager.reset()
        except Exception:
            pass

        ActionLog.stop()
        TaskManager.stop()

        if stop_mcp_server(server, thread):
            if app:
                app.log("ShopPrentice stopped successfully.")
        else:
            if app:
                app.log("Error stopping ShopPrentice")

    except Exception:
        if app:
            app.log(f"Error stopping ShopPrentice:\n{traceback.format_exc()}")
