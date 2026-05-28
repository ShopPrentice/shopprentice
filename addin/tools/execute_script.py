"""
Execute Script Tool

Execute Fusion API Python scripts within a transaction.
Adapted from Fusion MCP Addin's execute_api_script.
"""

import hashlib
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


def _check_clean_safe(script):
    """Return error dict if clean=True would destroy untracked or unsynced work.

    The invariant: clean=True wipes the entire timeline + user parameters.
    It must only run when the add-in knows the active document was built by
    a tracked script AND there are no pending UI changes. Otherwise, the
    user's manual geometry (or edits since last sync) would be destroyed.

    Returns None when clean=True is safe to proceed; returns an MCP error
    dict (with a decision-tree remediation) when it should be blocked.

    Three ways to pass:
      1. Empty design (nothing to lose)
      2. Tracked doc, pendingChanges == 0, not needsSync
      3. Tracked doc, pendingChanges == 0, needsSync=true BUT the script
         being executed hashes identically to the tracked script — i.e. the
         agent is rebuilding the same script after an add-in restart and
         there is no drift to lose. sync_script couldn't discover anything
         useful in this case anyway, since ActionLog was also restarted.

    pendingChanges is counted only for entries that the ActionLog recorded
    as genuinely model-changing — its SKIP_COMMANDS and empty-diff filter
    already screen out camera/selection/view-style changes, so a non-zero
    count is always a real signal.
    """
    import adsk.fusion
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        return None  # no design, clean is a no-op

    if design.timeline.count == 0 and design.userParameters.count == 0:
        return None  # empty doc — nothing to lose

    try:
        from server.document_tracker import DocumentTracker
        status = DocumentTracker.get_status()
    except Exception:
        # Fail-open if the tracker is unavailable — don't break the tool
        # because of a guard infrastructure problem.
        return None

    if not status.get("tracked"):
        return {
            "content": [{
                "type": "text",
                "text": (
                    "clean=True rejected: active document is not tracked "
                    "(tracked=false). The timeline has features or parameters "
                    "not built by a known script, so clean=True would destroy "
                    "manually-built geometry.\n\n"
                    "DECIDE WHAT THE USER WANTS:\n"
                    "  (a) If they want to ADD features (dovetails, grooves, "
                    "joinery) to this existing model — use additive mode. "
                    "Call execute_script WITHOUT clean=True. Look up existing "
                    "bodies by name (walk root.allOccurrences, match "
                    "component.name + bRepBodies) and append sketches / "
                    "extrudes / CUTs to the timeline. Ctrl+Z reverts just the "
                    "addition.\n"
                    "  (b) If they explicitly want to start over from scratch "
                    "— ASK first: \"this will erase your existing model. OK to "
                    "proceed?\" then pass force_clean=true.\n\n"
                    "Do NOT silently pass force_clean=true. When uncertain, ask "
                    "the user what they intend."
                )
            }],
            "isError": True,
            "message": "clean=True blocked on untracked document",
        }

    pending = status.get("pendingChanges", 0) or 0
    needs_sync = bool(status.get("needsSync"))

    # Fix #1: soft-pass needsSync when rebuilding the same tracked script.
    # After an add-in restart we only have the script-on-disk to go by; if
    # the script being executed matches, there's nothing for sync_script to
    # discover (ActionLog was reset too) and blocking just gets the user
    # stuck on an innocuous restart.
    if needs_sync and pending == 0:
        try:
            tracked_hash = DocumentTracker._script_hash
            current_hash = hashlib.sha256(script.encode()).hexdigest()
            if tracked_hash and current_hash == tracked_hash:
                return None  # same script, no drift — safe to rebuild
        except Exception:
            pass  # fall through to the normal rejection path

    if pending > 0 or needs_sync:
        detail = f"pendingChanges={pending}"
        if needs_sync:
            detail += ", needsSync=true"
        return {
            "content": [{
                "type": "text",
                "text": (
                    f"clean=True rejected: document has unsynced UI changes "
                    f"({detail}). clean=True would discard them.\n\n"
                    "RESOLUTION STEPS (do them in order):\n"
                    "  1. Call sync_script. One of three things happens:\n"
                    "     a. All changes auto-applied (applied list non-empty, "
                    "needsAgent empty): retry execute_script with clean=True.\n"
                    "     b. Structural changes need agent attention "
                    "(needsAgent list non-empty): read each item, edit the "
                    "script to include those features, then retry with "
                    "clean=True.\n"
                    "     c. sync_script fails or reports nothing resolvable: "
                    "go to step 2.\n"
                    "  2. When sync_script cannot make progress, ASK THE "
                    "USER. Summarize what the document shows vs what the "
                    "script produces, and offer three choices:\n"
                    "     - (i) Investigate the UI changes first (you read "
                    "the doc, explain what's there).\n"
                    "     - (ii) Incorporate the changes into the script "
                    "manually (you extend the script, then clean=True).\n"
                    "     - (iii) Discard the UI changes and rebuild from "
                    "script as-is (pass force_clean=true).\n\n"
                    "NEVER silently pass force_clean=true when there may be "
                    "user work to lose. It is always better to ask."
                )
            }],
            "isError": True,
            "message": "clean=True blocked on unsynced document",
        }

    return None


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

    # Delete remaining component occurrences (e.g. STEP imports that
    # survive timeline deletion because they are component insertions)
    root = design.rootComponent
    for i in range(root.occurrences.count - 1, -1, -1):
        try:
            root.occurrences.item(i).deleteMe()
        except Exception:
            pass

    # Delete user parameters
    params = design.userParameters
    for i in range(params.count - 1, -1, -1):
        try:
            params.item(i).deleteMe()
        except Exception:
            pass


def handler(script: str, sandbox: bool = False, clean: bool = False,
            script_path: str = None, force_clean: bool = False) -> dict:
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

    # Guard: scripts must not manage documents themselves — execute_script
    # handles doc lifecycle via clean=True.  doc.close() + documents.add()
    # inside a script conflicts with the transaction wrapper and can cause
    # Fusion to allocate unbounded memory during STEP imports.
    if re.search(r'\.close\s*\(\s*False\s*\)', script) and re.search(r'documents\.add\s*\(', script):
        return {
            "content": [
                {
                    "type": "text",
                    "text": ("Script contains doc.close()/documents.add() which conflicts "
                             "with execute_script's document management. Remove the document "
                             "cleanup loop and use clean=True instead.")
                }
            ],
            "isError": True,
        }

    if sandbox:
        return _execute_sandbox(script)

    # ── session-aware document provisioning ──
    # When running under a session, ensure the session has a document.
    # clean=True creates a fresh scratch doc; clean=False requires an
    # existing bound document (or claim_document first).
    from server.session_manager import SessionManager
    sm = SessionManager.instance()
    sid = sm.current_session_id

    app.log(f"[exec] sid={sid[:8] if sid else 'None'} clean={clean} force_clean={force_clean}")

    if sid:
        session = sm.get_session(sid)
        has_doc = session.document is not None if session else 'no_session'
        app.log(f"[exec] session found={session is not None} has_doc={has_doc}")
        if session and session.document is None:
            if clean or force_clean:
                import adsk.core as _ac, adsk.fusion as _af
                from server.session_manager import find_document_by_script_path
                # Auto-reclaim: reuse an open document this script already built
                reclaimed = False
                if script_path:
                    existing_doc, _ = find_document_by_script_path(script_path)
                    if existing_doc:
                        app.log(f"[exec] auto-reclaim: found doc tagged with {script_path}")
                        existing_doc.activate()
                        sm.bind_document(sid, existing_doc)
                        reclaimed = True
                if not reclaimed:
                    app.log("[exec] creating new scratch doc for session")
                    new_doc = app.documents.add(
                        _ac.DocumentTypes.FusionDesignDocumentType)
                    _design = _af.Design.cast(app.activeProduct)
                    _design.designType = _af.DesignTypes.ParametricDesignType
                    sm.bind_document(sid, new_doc)
                    app.log(f"[exec] bound doc={new_doc.name} docs_open={app.documents.count}")
            else:
                return {
                    "content": [{
                        "type": "text",
                        "text": (
                            "No document is bound to this session. "
                            "Use execute_script(clean=True) to create a "
                            "new scratch document, or call claim_document "
                            "to adopt an existing one first."
                        ),
                    }],
                    "isError": True,
                    "message": "No document bound to session",
                }

    # Guard: clean=True destroys the timeline + user parameters. Only allow
    # it on documents the add-in knows were built by a tracked script AND
    # have no unsynced UI changes. force_clean=True bypasses the check for
    # the rare "I really do want to wipe this doc" case.
    if clean and not force_clean:
        guard_result = _check_clean_safe(script)
        if guard_result is not None:
            return guard_result

    temp_file = None
    transaction_started = False
    transacted_doc = None
    original_script = script  # preserve before appending run(None)
    try:
        # Invalidate cached helper modules so scripts pick up file changes
        import sys as _sys
        for _k in list(_sys.modules):
            if _k.startswith('helpers'):
                del _sys.modules[_k]

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
            # Ensure design supports components (Part Design docs only allow one)
            import adsk.fusion
            design = adsk.fusion.Design.cast(app.activeProduct)
            if design and design.rootComponent.occurrences.count == 0:
                try:
                    # Test if we can create components — fails on Part Design docs
                    test_occ = design.rootComponent.occurrences.addNewComponent(
                        adsk.core.Matrix3D.create())
                    test_occ.component.name = "_test"
                    test_occ.deleteMe()
                except Exception:
                    # Part Design doc — abort transaction, create proper Fusion Design doc
                    app.executeTextCommand('PTransaction.Abort')
                    transaction_started = False
                    doc = app.activeDocument
                    if doc and not doc.isSaved:
                        doc.close(False)
                    new_doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
                    transacted_doc = app.activeDocument
                    if sid:
                        sm.bind_document(sid, new_doc)
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
            if script_path:
                DocumentTracker._script_path = script_path
        except Exception as e:
            app.log(f"[exec] provenance tracking error: {e}")

        # Persist script_path as Fusion attribute for auto-reclaim
        if script_path:
            from server.session_manager import tag_script_path
            tag_script_path(app.activeDocument, script_path)

        # Set visual style to Shaded with Visible Edges after every build
        try:
            app.activeViewport.visualStyle = adsk.core.VisualStyles.ShadedWithVisibleEdgesOnlyVisualStyle
        except:
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

Helper library: Scripts can `from helpers import sp` to use shared utilities:
- `sp.DesignContext()` — replaces app/design/root/params/ev boilerplate
- `sp.find_face(body, axis, direction)` — outermost planar face along axis
- `sp.find_face_at(body, axis, position)` — planar face at specific coordinate
- `sp.sketch_rect(comp, plane, ...)` — parametric rectangle with H/V constraints
- `sp.sketch_rect_model(comp, plane, ...)` — parametric rectangle on any plane
- `sp.probe_sketch_axes(sk)` — detect model axis → sketch H/V mapping
- `sp.smallest_profile(sk)` — smallest-area profile in a sketch

Sandbox mode: Set sandbox=true to run the script in a temporary document. Returns a design snapshot without modifying the user's active document. Useful for validating scripts before committing to the real design.

Modes:
- Additive (default, clean=false or omitted): the script appends features to the existing timeline. Safe on any document — existing bodies, parameters, and appearances are preserved. Ctrl+Z reverts just the appended features. Use this whenever adding features to an existing model.
- Clean rebuild (clean=true): deletes all timeline features + user parameters, then runs the script. Whole operation wrapped in one transaction; Ctrl+Z reverts everything. Guarded — rejected on untracked or unsynced documents to prevent destroying manual work. The rejection message tells you what to do next. force_clean=true overrides the guard; use only when you truly intend to wipe the document.
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
        "description": "Delete all existing features and parameters before running. Enables clean rebuild of an existing model. Ctrl+Z reverts the entire operation. Rejected on untracked or unsynced documents — use the default (additive mode) to modify an existing model."
    }
).add_input_property(
    "script_path", {
        "type": "string",
        "description": "File path of the script on disk. Tracked for palette parameter sync — palette Rebuild writes param changes back to this file."
    }
).add_input_property(
    "force_clean", {
        "type": "boolean",
        "description": "Bypass the clean=true safety check and wipe the document regardless of provenance. Use only when you genuinely intend to discard the current document contents (e.g., starting a completely new build over an untracked model)."
    }
).add_required_input("script").strict_schema()

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
