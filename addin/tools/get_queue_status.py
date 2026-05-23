"""
Get Queue Status Tool

Lets agents inspect the execution queue without blocking.  Runs on the
HTTP worker thread (not the Fusion main thread) so it returns instantly
regardless of queue depth.
"""

import json
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register


def handler() -> dict:
    from server.session_manager import SessionManager
    sm = SessionManager.instance()
    status = sm._execution_queue.get_status()
    return {
        "content": [{"type": "text", "text": json.dumps(status, indent=2)}],
        "isError": False,
        "message": f"queue_depth={status['queue_depth']}",
    }


TOOL_DESCRIPTION = """\
Check the tool execution queue — returns immediately, never queued.

Returns:
- **active_tool / active_session** — which tool is running right now
- **callback_started** — whether Fusion has begun processing it
  (false after 30 s means Fusion is likely frozen)
- **active_running_for** — seconds since the active tool started
- **queue_depth** — how many tools are waiting behind the active one
- **waiting** — list of queued tools with session and wait time

Use this to understand why a previous call was slow (queuing vs. crash),
or to check Fusion responsiveness before sending a heavy script."""

tool = Tool.create_simple(
    name="get_queue_status",
    description=TOOL_DESCRIPTION,
).strict_schema()

item = Item(primitive=tool, handler=handler, run_on_main_thread=False)

register(item)
