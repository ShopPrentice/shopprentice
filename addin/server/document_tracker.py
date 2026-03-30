"""
Document Tracker Module

Provenance tracking for the active Fusion 360 document.
Remembers which script built the current model, tracks the ActionLog
sync cursor, and stores a reference snapshot of model parameters for
state-diff based change detection in sync_script.

In-memory state is authoritative during a session. A JSON sidecar file
at ~/.shopprentice/provenance.json persists script source, hash, and
reference model parameters across add-in restarts, keyed by document name.
"""

import hashlib
import json
import os
import traceback

try:
    import adsk.core
    app = adsk.core.Application.get()
except ImportError:
    app = None

_PROVENANCE_DIR = os.path.join(os.path.expanduser("~"), ".shopprentice")
_PROVENANCE_FILE = os.path.join(_PROVENANCE_DIR, "provenance.json")


class DocumentTracker:
    """
    Singleton tracker that records which script built the active document.

    Tracks (in memory):
    - The full script source from the last execute_script (non-sandbox)
    - A SHA-256 hash of that script
    - The ActionLog cursor after the last script execution or sync
    - A reference snapshot of model parameters for state-diff detection
    - A reference to the Fusion Document for identity checking

    Persists (to JSON file):
    - Script source, hash, and reference model parameters, keyed by document name
    - Restored automatically when get_status finds no in-memory state
      but a matching entry exists on disk
    """

    _script_source = None     # str: full script text from last execute_script
    _script_path = None       # str: file path of the script (if known)
    _script_hash = None       # str: SHA-256 of script_source
    _sync_cursor = None       # str: ActionLog cursor UUID after last script/sync
    _reference_model_params = None  # dict: {featureName.paramName: expression}
    _doc_ref = None           # Fusion Document reference (for identity check)
    _restored = False         # True when state was loaded from disk (needs sync)

    @classmethod
    def on_script_executed(cls, script, doc):
        """Called by execute_script after successful non-sandbox execution."""
        cls._script_source = script
        cls._script_hash = hashlib.sha256(script.encode()).hexdigest()
        cls._doc_ref = doc
        cls._restored = False
        # Get the ActionLog cursor AFTER ActionLog.reset()
        try:
            from server.action_log import ActionLog
            cls._sync_cursor = ActionLog.get_latest_cursor()
        except Exception:
            cls._sync_cursor = None
        # Capture reference snapshot of model parameters for state-diff
        cls._reference_model_params = cls._capture_model_params()
        cls._save(doc)

    @classmethod
    def on_sync_complete(cls, patched_script):
        """Called by sync_script after successful sync."""
        cls._script_source = patched_script
        cls._script_hash = hashlib.sha256(patched_script.encode()).hexdigest()
        # Obtain cursor internally
        try:
            from server.action_log import ActionLog
            cls._sync_cursor = ActionLog.get_latest_cursor()
        except Exception:
            pass
        cls._restored = False
        # Capture reference snapshot of model parameters for state-diff
        cls._reference_model_params = cls._capture_model_params()
        cls._save(cls._doc_ref)

    @classmethod
    def advance_cursor(cls, cursor):
        """Advance sync cursor after modify_parameters/suppress_features."""
        cls._sync_cursor = cursor

    # ── Reference model parameters (state-diff) ──

    @classmethod
    def _capture_model_params(cls):
        """Capture current model parameter expressions (excluding user params).

        Returns dict: {featureName.paramName: expression}, or None if no design.
        """
        import adsk.fusion
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return None
        user_names = set()
        for i in range(design.userParameters.count):
            user_names.add(design.userParameters.item(i).name)
        result = {}
        for i in range(design.allParameters.count):
            p = design.allParameters.item(i)
            if p.name not in user_names:
                try:
                    parent = p.createdBy
                    key = f"{parent.name}.{p.name}" if parent else p.name
                except Exception:
                    key = p.name
                result[key] = p.expression
        return result

    @classmethod
    def update_reference(cls):
        """Recapture reference model params after API-driven changes."""
        cls._reference_model_params = cls._capture_model_params()
        cls._save(cls._doc_ref)

    @classmethod
    def get_reference_model_params(cls):
        """Return the reference model params, attempting restore if None."""
        if cls._reference_model_params is None and cls._script_source is None:
            cls._try_restore()
        return cls._reference_model_params

    @classmethod
    def get_status(cls):
        """Return current provenance status."""
        # Check if tracked doc is still the active doc
        if cls._doc_ref is not None:
            try:
                active_doc = app.activeDocument
                if not cls._doc_ref.isValid or cls._doc_key(active_doc) != cls._doc_key(cls._doc_ref):
                    # Active doc changed — try to restore from disk
                    cls._clear_memory()
                    if cls._try_restore():
                        return cls._tracked_status()
                    return {"tracked": False, "reason": "Active document changed"}
            except Exception:
                return {"tracked": False, "reason": "Cannot check active document"}

        if cls._script_source is None:
            # No in-memory state — try to restore from disk for the active doc
            if cls._try_restore():
                return cls._tracked_status()
            return {"tracked": False, "reason": "No script has been executed in this session"}

        return cls._tracked_status()

    @classmethod
    def _tracked_status(cls):
        """Build the status dict for a tracked document."""
        pending = 0
        try:
            from server.action_log import ActionLog
            entries = ActionLog.get_entries(since=cls._sync_cursor)
            pending = len(entries)
        except Exception:
            pass

        status = {
            "tracked": True,
            "scriptHash": cls._script_hash,
            "syncCursor": cls._sync_cursor,
            "pendingChanges": pending,
            "canUpdate": True,
        }
        if cls._restored:
            status["needsSync"] = True
        return status

    @classmethod
    def get_script(cls):
        """Return the tracked script source, or None."""
        if cls._script_source is None:
            cls._try_restore()
        return cls._script_source

    @classmethod
    def reset(cls):
        """Clear all tracking state (in-memory only)."""
        cls._clear_memory()

    @classmethod
    def _clear_memory(cls):
        """Clear in-memory state without touching disk."""
        cls._script_source = None
        cls._script_hash = None
        cls._sync_cursor = None
        cls._reference_model_params = None
        cls._doc_ref = None
        cls._restored = False

    # ── Persistence ──

    @classmethod
    def _doc_key(cls, doc):
        """Get a stable key for a Fusion document."""
        if doc is None:
            return None
        try:
            return doc.name
        except Exception:
            return None

    @classmethod
    def _save(cls, doc):
        """Persist script source and hash to the JSON sidecar."""
        key = cls._doc_key(doc)
        if key is None or cls._script_source is None:
            return
        try:
            data = cls._load_file()
            entry = {
                "scriptSource": cls._script_source,
                "scriptHash": cls._script_hash,
            }
            if cls._reference_model_params is not None:
                entry["referenceModelParams"] = cls._reference_model_params
            data[key] = entry
            os.makedirs(_PROVENANCE_DIR, exist_ok=True)
            with open(_PROVENANCE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, separators=(",", ":"))
        except Exception as e:
            if app:
                app.log(f"DocumentTracker: save failed - {e}")

    @classmethod
    def _try_restore(cls):
        """Try to restore tracking state from disk for the active document.

        Returns True if restored successfully.
        """
        try:
            doc = app.activeDocument
            if doc is None:
                return False
            key = cls._doc_key(doc)
            if key is None:
                return False
            data = cls._load_file()
            entry = data.get(key)
            if entry is None:
                return False
            cls._script_source = entry["scriptSource"]
            cls._script_hash = entry["scriptHash"]
            cls._reference_model_params = entry.get("referenceModelParams")  # graceful if missing
            cls._doc_ref = doc
            cls._sync_cursor = None  # cursor is session-only, can't restore
            cls._restored = True     # signal that sync is needed
            return True
        except Exception as e:
            if app:
                app.log(f"DocumentTracker: restore failed - {e}")
            return False

    @classmethod
    def _load_file(cls):
        """Load the provenance JSON file, returning {} if missing."""
        try:
            with open(_PROVENANCE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
