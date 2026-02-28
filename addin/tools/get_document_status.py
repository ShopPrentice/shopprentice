"""
Get Document Status Tool

Exposes document provenance tracking so the agent can determine whether
the active document was built by a known script and whether there are
pending UI changes since the last sync.
"""

import json
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register


def handler() -> dict:
    """Return the current document provenance status."""
    from server.document_tracker import DocumentTracker
    status = DocumentTracker.get_status()

    return {
        "content": [{"type": "text", "text": json.dumps(status, indent=2)}],
        "isError": False,
        "message": "tracked" if status["tracked"] else status["reason"]
    }


# Tool definition

TOOL_DESCRIPTION = \
"""Check whether the active document was built by a known script.

Returns provenance status:
- **tracked=false** — No script has been executed in this session, or the active document changed. The agent cannot safely make incremental updates.
- **tracked=true** — The document was built by a known script. Additional fields:
  - `scriptHash` — SHA-256 of the tracked script
  - `syncCursor` — ActionLog cursor for the last sync point
  - `pendingChanges` — number of UI changes since the last sync (0 = clean)
  - `needsSync` — present and true when provenance was restored from disk (e.g. after add-in restart). The script may be out of sync with the model — call sync_script before making changes.
  - `canUpdate` — true if incremental updates are safe

Use this before attempting to modify an existing design. If needsSync is true or pendingChanges > 0, call sync_script first to reconcile."""

tool = Tool.create_simple(
    name="get_document_status",
    description=TOOL_DESCRIPTION
).strict_schema()

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
