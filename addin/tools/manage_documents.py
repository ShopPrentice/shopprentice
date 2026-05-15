"""
Manage Documents Tool

List all open documents and activate a specific one by name or index.
"""

import json
import traceback
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register
import adsk.core
import adsk.fusion

app = adsk.core.Application.get()


def handler(action: str = "list", name: str = "", index: int = -1) -> dict:
    """List or activate Fusion 360 documents.

    Actions:
        list   — return all open documents with name, saved status, active flag
        activate — switch to a document by name or index
        new    — create a new untitled design document
        close  — close the active document (unsaved changes discarded)
    """
    try:
        if action == "list":
            docs = []
            active_doc = app.activeDocument
            for i in range(app.documents.count):
                doc = app.documents.item(i)
                entry = {
                    "index": i,
                    "name": doc.name,
                    "isSaved": doc.isSaved,
                    "isActive": doc == active_doc,
                }
                try:
                    design = adsk.fusion.Design.cast(doc.products.itemByProductType("DesignProductType"))
                    if design:
                        entry["bodyCount"] = sum(
                            design.rootComponent.bRepBodies.count
                            for _ in [None]
                        )
                        # Count all bodies recursively
                        def count_bodies(comp):
                            n = comp.bRepBodies.count
                            for occ in comp.occurrences:
                                n += count_bodies(occ.component)
                            return n
                        entry["bodyCount"] = count_bodies(design.rootComponent)
                except:
                    pass
                docs.append(entry)
            return {
                "content": [{"type": "text", "text": json.dumps(docs, indent=2)}],
                "isError": False,
                "message": f"{len(docs)} document(s)",
            }

        elif action == "activate":
            if name:
                for i in range(app.documents.count):
                    doc = app.documents.item(i)
                    if doc.name == name:
                        doc.activate()
                        return {
                            "content": [{"type": "text", "text": f"Activated: {doc.name}"}],
                            "isError": False,
                            "message": f"Activated: {doc.name}",
                        }
                return {
                    "content": [{"type": "text", "text": f"Document '{name}' not found"}],
                    "isError": True,
                    "message": f"Document '{name}' not found",
                }
            elif index >= 0:
                if index < app.documents.count:
                    doc = app.documents.item(index)
                    doc.activate()
                    return {
                        "content": [{"type": "text", "text": f"Activated: {doc.name}"}],
                        "isError": False,
                        "message": f"Activated: {doc.name}",
                    }
                return {
                    "content": [{"type": "text", "text": f"Index {index} out of range"}],
                    "isError": True,
                    "message": f"Index {index} out of range",
                }
            return {
                "content": [{"type": "text", "text": "Specify 'name' or 'index'"}],
                "isError": True,
                "message": "Specify 'name' or 'index'",
            }

        elif action == "new":
            doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
            design = adsk.fusion.Design.cast(app.activeProduct)
            if design:
                design.designType = adsk.fusion.DesignTypes.ParametricDesignType
            # Bind to current session if one is active
            try:
                from server.session_manager import SessionManager
                sm = SessionManager.instance()
                sid = sm.current_session_id
                if sid:
                    sm.bind_document(sid, doc)
            except Exception:
                pass
            return {
                "content": [{"type": "text", "text": f"Created and bound: {doc.name}"}],
                "isError": False,
                "message": f"Created: {doc.name}",
            }

        elif action == "close":
            doc = app.activeDocument
            doc_name = doc.name
            doc.close(False)
            return {
                "content": [{"type": "text", "text": f"Closed: {doc_name}"}],
                "isError": False,
                "message": f"Closed: {doc_name}",
            }

        else:
            return {
                "content": [{"type": "text", "text": f"Unknown action: {action}"}],
                "isError": True,
                "message": f"Unknown action: {action}",
            }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {e}\n{traceback.format_exc()}"}],
            "isError": True,
            "message": f"manage_documents failed: {e}",
        }


tool = Tool(
    name="manage_documents",
    description="List open documents, activate by name/index, create new, or close active.",
    input_schema={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "activate", "new", "close"],
                "description": "Action: list, activate, new, close",
            },
            "name": {
                "type": "string",
                "description": "Document name (for activate)",
            },
            "index": {
                "type": "integer",
                "description": "Document index (for activate)",
            },
        },
    },
)

item = Item.create_tool_item(tool=tool, handler=handler)
register(item)
