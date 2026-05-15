"""
Action Log Module

Event-driven change log that listens to Fusion 360 commandTerminated events.
Records each user UI action individually so no changes are lost between
agent calls.

API-driven changes (from execute_script) do NOT fire UI command events,
so the log only captures what the user did by hand.
"""

import hashlib
import json
import os
import traceback
import uuid
from datetime import datetime, timezone

try:
    import adsk.core
    import adsk.fusion
    app = adsk.core.Application.get()
except ImportError:
    app = None

# Read-only commands that never modify the design
SKIP_COMMANDS = frozenset([
    # Navigation
    "OrbitCommand", "PanCommand", "ZoomInCommand", "ZoomOutCommand",
    "ZoomAllCommand", "ZoomWindowCommand", "ZoomToFitCommand",
    "FitToWindowCommand", "LookAtCommand", "RollCommand",
    "FreeOrbitCommand", "ConstrainedOrbitCommand",
    # Selection
    "SelectCommand", "SelectionFilterCommand",
    # View
    "ViewCubeCommand", "HomeViewCommand", "VisualStyleCommand",
    "SectionAnalysisCommand",
    # Read-only
    "MeasureCommand", "InspectCommand", "PrintCommand",
    "ShowDataPanelCommand",
])


class ActionLog:
    """
    Singleton action log that records user UI changes via commandTerminated.

    Class-method API matching the TaskManager pattern.
    """

    _is_running = False
    _suppress = False  # Set True during sandbox to ignore doc-switch events
    _event_handler = None
    _entries = []
    _baseline = None
    _last_timeline_count = None
    _last_param_hash = None
    _last_read_cursor = None  # auto-advances on each get_changes call
    _log_dir = None
    _log_file = None

    @classmethod
    def start(cls):
        """Register the commandTerminated handler and capture initial baseline."""
        if cls._is_running:
            if app:
                app.log("ActionLog: Already running")
            return

        try:
            handler = CommandTerminatedHandler()
            app.userInterface.commandTerminated.add(handler)
            cls._event_handler = handler  # prevent GC

            # Capture initial baseline
            design = adsk.fusion.Design.cast(app.activeProduct)
            if design:
                from tools.get_changes import _capture_snapshot
                cls._baseline = _capture_snapshot(design)
                cls._last_timeline_count = design.timeline.count
                cls._last_param_hash = cls._compute_param_hash(design)

            cls._entries = []
            cls._log_file = None
            cls._is_running = True

            if app:
                app.log("ActionLog: Started successfully")
        except Exception as e:
            if app:
                app.log(f"ActionLog: Failed to start - {e}\n{traceback.format_exc()}")

    @classmethod
    def stop(cls):
        """Unregister handler and clear state."""
        if not cls._is_running:
            return

        try:
            if cls._event_handler:
                app.userInterface.commandTerminated.remove(cls._event_handler)
                cls._event_handler = None

            cls._entries = []
            cls._baseline = None
            cls._last_timeline_count = None
            cls._last_param_hash = None
            cls._last_read_cursor = None
            cls._log_file = None
            cls._is_running = False

            if app:
                app.log("ActionLog: Stopped successfully")
        except Exception as e:
            if app:
                app.log(f"ActionLog: Failed to stop - {e}\n{traceback.format_exc()}")

    @classmethod
    def reset(cls):
        """Clear log and capture fresh baseline. Called by execute_script."""
        if not cls._is_running:
            return

        try:
            design = adsk.fusion.Design.cast(app.activeProduct)
            if design:
                from tools.get_changes import _capture_snapshot
                cls._baseline = _capture_snapshot(design)
                cls._last_timeline_count = design.timeline.count
                cls._last_param_hash = cls._compute_param_hash(design)

                # Also update get_changes._baseline for backward compat
                try:
                    import tools.get_changes as gc
                    gc._baseline = cls._baseline
                except Exception:
                    pass

            cls._entries = []
            cls._last_read_cursor = None
            cls._log_file = None

            if app:
                app.log("ActionLog: Reset — fresh baseline captured")
        except Exception as e:
            if app:
                app.log(f"ActionLog: Reset failed - {e}\n{traceback.format_exc()}")

    @classmethod
    def get_entries(cls, since=None):
        """Return log entries after cursor UUID. None = all entries."""
        if since is None:
            return list(cls._entries)

        # Find the entry with matching id, return everything after it
        for i, entry in enumerate(cls._entries):
            if entry["id"] == since:
                return list(cls._entries[i + 1:])

        # Cursor not found — return all entries
        return list(cls._entries)

    @classmethod
    def get_latest_cursor(cls):
        """Return the UUID of the most recent entry, or None."""
        if cls._entries:
            return cls._entries[-1]["id"]
        return None

    @classmethod
    def advance_cursor(cls):
        """Advance the auto-read cursor to the latest entry.

        Called by get_changes after returning entries, so the next call
        without `since` only returns new entries.
        """
        cls._last_read_cursor = cls.get_latest_cursor()

    @classmethod
    def get_compacted_diff(cls, since=None):
        """Merge all entry diffs since cursor into one combined diff."""
        entries = cls.get_entries(since=since)
        if not entries:
            return None

        merged = {
            "parameterChanges": [],
            "modelParameterChanges": [],
            "dimensionChanges": [],
            "bodyChanges": {"added": [], "removed": []},
            "featureCountDelta": 0,
        }

        # Track net changes by key
        param_net = {}       # name -> {first_old, latest_new}
        model_param_net = {}
        dim_net = {}
        bodies_added = {}    # (comp, name) -> True
        bodies_removed = {}  # (comp, name) -> True

        for entry in entries:
            diff = entry.get("diff", {})

            for pc in diff.get("parameterChanges", []):
                name = pc["name"]
                if name not in param_net:
                    param_net[name] = {"old": pc.get("old"), "change": pc.get("change")}
                param_net[name]["new"] = pc.get("new")
                param_net[name]["latest_change"] = pc.get("change")

            for mc in diff.get("modelParameterChanges", []):
                name = mc["name"]
                if name not in model_param_net:
                    model_param_net[name] = {"old": mc.get("old"), "change": mc.get("change")}
                model_param_net[name]["new"] = mc.get("new")
                model_param_net[name]["latest_change"] = mc.get("change")

            for dc in diff.get("dimensionChanges", []):
                key = f"{dc.get('component', '')}/{dc.get('sketch', '')}.{dc.get('param', '')}"
                if key not in dim_net:
                    dim_net[key] = {"old": dc.get("old"), "entry": dc}
                dim_net[key]["new"] = dc.get("new")
                dim_net[key]["entry_new"] = dc.get("new")

            for ba in diff.get("bodyChanges", {}).get("added", []):
                bkey = (ba["component"], ba["name"])
                if bkey in bodies_removed:
                    del bodies_removed[bkey]  # cancel add/remove pair
                else:
                    bodies_added[bkey] = True

            for br in diff.get("bodyChanges", {}).get("removed", []):
                bkey = (br["component"], br["name"])
                if bkey in bodies_added:
                    del bodies_added[bkey]  # cancel add/remove pair
                else:
                    bodies_removed[bkey] = True

            merged["featureCountDelta"] += diff.get("featureCountDelta", 0)

        # Build compacted lists, dropping no-ops (old == new after merge)
        for name, info in sorted(param_net.items()):
            if info.get("old") != info.get("new"):
                entry = {"name": name}
                if info.get("old") is not None:
                    entry["old"] = info["old"]
                if info.get("new") is not None:
                    entry["new"] = info["new"]
                if info.get("old") is None:
                    entry["change"] = "added"
                elif info.get("new") is None:
                    entry["change"] = "removed"
                merged["parameterChanges"].append(entry)

        for name, info in sorted(model_param_net.items()):
            if info.get("old") != info.get("new"):
                entry = {"name": name}
                if info.get("old") is not None:
                    entry["old"] = info["old"]
                if info.get("new") is not None:
                    entry["new"] = info["new"]
                if info.get("old") is None:
                    entry["change"] = "added"
                elif info.get("new") is None:
                    entry["change"] = "removed"
                merged["modelParameterChanges"].append(entry)

        for key, info in sorted(dim_net.items()):
            if info.get("old") != info.get("new"):
                e = dict(info["entry"])
                if info.get("new") is not None:
                    e["new"] = info["new"]
                merged["dimensionChanges"].append(e)

        for (comp, name) in sorted(bodies_added.keys()):
            merged["bodyChanges"]["added"].append({"component": comp, "name": name})
        for (comp, name) in sorted(bodies_removed.keys()):
            merged["bodyChanges"]["removed"].append({"component": comp, "name": name})

        return merged

    @classmethod
    def _on_command_terminated(cls, command_id, termination_reason):
        """Process a commandTerminated event. Called on the main thread."""
        try:
            if cls._suppress:
                return

            if termination_reason != 0:
                return

            if command_id in SKIP_COMMANDS:
                return

            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return

            # Read the active document's docKey so we can scope
            # the baseline/entries to the correct document.
            doc_key = None
            try:
                dk_attr = design.rootComponent.attributes.itemByName(
                    "ShopPrentice", "docKey")
                if dk_attr:
                    doc_key = dk_attr.value
            except Exception:
                pass

            # If the active doc differs from whatever the MCP callback
            # last loaded, swap globals to this doc's provenance first.
            if doc_key:
                try:
                    import sys as _sys
                    sm_mod = _sys.modules.get("server.session_manager")
                    if sm_mod:
                        sm = sm_mod.SessionManager.instance()
                        sm.save_provenance()       # save outgoing
                        sm._load_provenance(doc_key)  # load this doc
                except Exception:
                    pass

            tl_count = design.timeline.count
            param_hash = cls._compute_param_hash(design)

            if tl_count == cls._last_timeline_count and param_hash == cls._last_param_hash:
                if doc_key:
                    cls._save_back(doc_key)
                return

            if cls._baseline is None:
                if doc_key:
                    cls._save_back(doc_key)
                return

            from tools.get_changes import _capture_snapshot, _diff_snapshots
            current = _capture_snapshot(design)
            diff = _diff_snapshots(cls._baseline, current)

            total = (len(diff["parameterChanges"]) +
                     len(diff["modelParameterChanges"]) +
                     len(diff["dimensionChanges"]) +
                     len(diff["bodyChanges"]["added"]) +
                     len(diff["bodyChanges"]["removed"]) +
                     abs(diff["featureCountDelta"]))
            if total == 0:
                cls._last_timeline_count = tl_count
                cls._last_param_hash = param_hash
                if doc_key:
                    cls._save_back(doc_key)
                return

            entry = {
                "id": str(uuid.uuid4()),
                "commandId": command_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "diff": diff,
                "docKey": doc_key,
            }
            cls._entries.append(entry)

            cls._baseline = current
            cls._last_timeline_count = tl_count
            cls._last_param_hash = param_hash

            try:
                import tools.get_changes as gc
                gc._baseline = current
            except Exception:
                pass

            if doc_key:
                cls._save_back(doc_key)

            # Append to JSONL file
            cls._append_to_file(entry)

            if app:
                app.log(f"ActionLog: Recorded {command_id} ({total} change(s))")

        except Exception as e:
            if app:
                app.log(f"ActionLog: Error in _on_command_terminated - {e}\n{traceback.format_exc()}")

    @classmethod
    def _save_back(cls, doc_key):
        """Save current ActionLog globals back to the provenance store."""
        try:
            import sys as _sys
            sm_mod = _sys.modules.get("server.session_manager")
            if sm_mod:
                sm = sm_mod.SessionManager.instance()
                sm.save_provenance(doc_key)
        except Exception:
            pass

    @classmethod
    def _compute_param_hash(cls, design):
        """Compute a fast hash of all parameter expressions."""
        parts = []
        for i in range(design.allParameters.count):
            p = design.allParameters.item(i)
            parts.append(f"{p.name}={p.expression}")
        return hashlib.md5("|".join(parts).encode()).hexdigest()

    @classmethod
    def _ensure_log_dir(cls):
        """Ensure ~/.shopprentice/logs/ exists."""
        if cls._log_dir is None:
            cls._log_dir = os.path.join(os.path.expanduser("~"), ".shopprentice", "logs")
            os.makedirs(cls._log_dir, exist_ok=True)
        return cls._log_dir

    @classmethod
    def _append_to_file(cls, entry):
        """Append a log entry to the JSONL file."""
        try:
            if cls._log_file is None:
                log_dir = cls._ensure_log_dir()
                doc_name = "unknown"
                try:
                    doc = app.activeDocument
                    if doc:
                        doc_name = doc.name.replace(" ", "_").replace("/", "_")
                except Exception:
                    pass
                cls._log_file = os.path.join(log_dir, f"{doc_name}.jsonl")

            with open(cls._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, separators=(",", ":")) + "\n")
        except Exception as e:
            if app:
                app.log(f"ActionLog: File write error - {e}")


class CommandTerminatedHandler(adsk.core.ApplicationCommandEventHandler):
    """Fusion 360 event handler for commandTerminated."""

    def __init__(self):
        super().__init__()

    def notify(self, args):
        """Called by Fusion when any command terminates."""
        try:
            event_args = adsk.core.ApplicationCommandEventArgs.cast(args)
            command_id = event_args.commandId
            termination_reason = event_args.terminationReason
            ActionLog._on_command_terminated(command_id, termination_reason)
        except Exception as e:
            if app:
                app.log(f"ActionLog handler error: {e}\n{traceback.format_exc()}")
