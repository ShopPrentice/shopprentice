"""
Claim Document Tool

Lets a session adopt an existing open Fusion 360 document.  If the
target document is already bound to another *active* session the tool
returns a conflict with options — the agent should present them to the
user and call again with the chosen ``resolution``.
"""

from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register

import adsk.core

app = adsk.core.Application.get()


def handler(
    document_name: str = None,
    doc_key: str = None,
    resolution: str = None,
) -> dict:
    from server.session_manager import SessionManager

    sm = SessionManager.instance()
    sid = sm.current_session_id
    if not sid:
        return {
            "content": [{
                "type": "text",
                "text": (
                    "claim_document requires session support.  Your MCP "
                    "client must send the Mcp-Session-Id header (MCP "
                    "streamable-HTTP transport).  Connect with a client "
                    "that supports it, or use a recent version of "
                    "mcp-remote / Claude Code."
                ),
            }],
            "isError": True,
        }

    result = sm.claim_document(
        sid, document_name=document_name, doc_key=doc_key,
        resolution=resolution,
    )

    if result.get("conflict"):
        return {
            "content": [{"type": "text", "text": result["message"]}],
            "isError": True,
            "_conflict": result,
        }

    if result.get("error"):
        return {
            "content": [{"type": "text", "text": result["message"]}],
            "isError": True,
        }

    return {
        "content": [{"type": "text", "text": result["message"]}],
        "isError": False,
        "document_name": result.get("document_name"),
    }


TOOL_DESCRIPTION = """\
Claim (adopt) an existing open Fusion 360 document for this session.

Use this when you want to work on a document that already exists — for
example, one left by a previous agent session or opened by the user.
Also use this after an add-in restart when your session was restored
but has no document bound — the error message lists available documents
with their doc_key values.

Identify the target by doc_key (preferred — stable UUID, shown in the
session-restored message) or document_name. If neither is given, claims
the currently active document in the Fusion viewport.

Each session can control at most one document.  If the target document is
already bound to another *active* session, the tool returns a conflict
with two resolution options.  Present both to the user and call again
with the chosen resolution. Do NOT auto-resolve — always ask the user.
"""

tool = (
    Tool.create_simple(name="claim_document", description=TOOL_DESCRIPTION)
    .add_input_property("doc_key", {
        "type": "string",
        "description": (
            "Stable document UUID (shown in the session-restored "
            "message). Preferred over document_name since names can "
            "collide across unsaved documents."
        ),
    })
    .add_input_property("document_name", {
        "type": "string",
        "description": (
            "Name of the open document to claim. Use doc_key instead "
            "when available. Omit both to claim the active document."
        ),
    })
    .add_input_property("resolution", {
        "type": "string",
        "enum": ["transfer", "keep_existing"],
        "description": (
            "How to resolve a conflict when the document belongs to "
            "another active session.  'transfer' moves it to your "
            "session; 'keep_existing' leaves it.  Only needed on the "
            "second call after a conflict is reported."
        ),
    })
    .strict_schema()
)

item = Item.create_tool_item(tool=tool, handler=handler)
register(item)
