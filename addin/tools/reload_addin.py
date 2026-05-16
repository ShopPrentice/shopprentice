"""
Reload Add-in Tool

Hot-reload the ShopPrentice add-in: flush and re-import all tool, primitive,
and helper modules, then re-register tools in the running MCP server.
The HTTP server stays alive so the MCP connection is uninterrupted.
"""

import sys
import traceback
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register

try:
    import adsk.core
    app = adsk.core.Application.get()
except:
    app = None


def handler() -> dict:
    """Hot-reload all ShopPrentice modules and re-register tools."""
    try:
        # Get MCP server ref stored on app object by ShopPrentice.run()
        mcp_server = getattr(sys, '_shopprentice_mcp', None)
        if not mcp_server:
            return {
                "content": [{"type": "text", "text": "No MCP server reference found on sys._shopprentice_mcp"}],
                "isError": True,
                "message": "MCP server not found",
            }

        # Save a reference to ourselves so we can always re-register
        _self_item = mcp_server.tools.get("reload_addin")

        # Stop ActionLog before flushing modules
        try:
            from server.action_log import ActionLog
            ActionLog.stop()
        except Exception:
            pass

        old_tool_count = len(mcp_server.tools)
        old_tool_names = sorted(mcp_server.tools.keys())

        # Clear existing registrations
        mcp_server.tools.clear()
        mcp_server.resources.clear()

        # Flush tools, primitives, server, helpers from sys.modules
        prefixes = ('tools', 'primitives', 'server', 'helpers')
        to_remove = sorted(
            [k for k in sys.modules
             if any(k == p or k.startswith(p + '.') for p in prefixes)],
            key=lambda k: k.count('.'), reverse=True)
        for mod_name in to_remove:
            sys.modules.pop(mod_name, None)

        # Re-import primitives (fresh registry singleton) then tools
        import_error = None
        try:
            import primitives.registry
            import tools
        except Exception as ie:
            import_error = ie
            # Ensure primitives.registry exists for the recovery path
            try:
                import primitives.registry
            except Exception:
                pass

        new_tools = primitives.registry.get_tools()
        new_resources = primitives.registry.get_resources()

        # Populate MCP server dicts directly (bypass isinstance check
        # which fails because Item class changed across module reload)
        for tool_item in new_tools:
            mcp_server.tools[tool_item.primitive.name] = tool_item
        for resource_item in new_resources:
            mcp_server.resources[resource_item.primitive.uri] = resource_item

        # Always ensure reload_addin is registered (even if import failed)
        if "reload_addin" not in mcp_server.tools and _self_item:
            mcp_server.tools["reload_addin"] = _self_item

        # Restart ActionLog with fresh module
        try:
            from server.action_log import ActionLog as FreshActionLog
            FreshActionLog.start()
        except Exception:
            pass

        new_tool_count = len(mcp_server.tools)
        new_tool_names = sorted(mcp_server.tools.keys())

        added = sorted(set(new_tool_names) - set(old_tool_names))
        removed = sorted(set(old_tool_names) - set(new_tool_names))

        summary = f"Reloaded: {new_tool_count} tools"
        if added:
            summary += f", added: {added}"
        if removed:
            summary += f", removed: {removed}"
        summary += f"\nModules flushed: {len(to_remove)}"

        if import_error:
            summary += f"\nIMPORT ERROR: {import_error}"

        if app:
            app.log(f"ShopPrentice hot-reload: {new_tool_count} tools" +
                    (f" (import error: {import_error})" if import_error else ""))

        return {
            "content": [{"type": "text", "text": summary}],
            "isError": bool(import_error),
            "message": summary.split('\n')[0],
        }

    except Exception as e:
        # Last resort: try to re-register ourselves
        try:
            mcp_server = getattr(sys, '_shopprentice_mcp', None)
            if mcp_server and "reload_addin" not in mcp_server.tools and _self_item:
                mcp_server.tools["reload_addin"] = _self_item
        except Exception:
            pass
        msg = f"Reload failed: {e}\n{traceback.format_exc()}"
        if app:
            app.log(msg)
        return {
            "content": [{"type": "text", "text": msg}],
            "isError": True,
            "message": f"Reload failed: {e}",
        }


# Tool definition

tool = Tool.create_simple(
    name="reload_addin",
    description=(
        "Hot-reload the ShopPrentice add-in. Flushes and re-imports all tool, "
        "primitive, and helper modules, then re-registers tools in the running "
        "MCP server. The HTTP server stays alive so the MCP connection is "
        "uninterrupted. Use after editing add-in source code."
    ),
).strict_schema()

item = Item.create_tool_item(tool=tool, handler=handler)

import os
if os.environ.get("SHOPPRENTICE_DEV"):
    register(item)
