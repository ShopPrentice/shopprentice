"""
Session Manager

Maps MCP sessions to Fusion 360 documents so multiple agents can work on
separate documents without stepping on each other.  The MCP server reads
the Mcp-Session-Id HTTP header to identify the caller, then the
SessionManager activates the correct document before every tool execution.

Architecture:
    SessionManager  — maps session_id → document
    _doc_provenance — maps doc_key   → ActionLog/DocumentTracker state

    A session only determines which document is active.  Provenance is
    loaded/saved by document identity so transferring or claiming a
    document naturally carries its provenance with the document.

Document identity:
    Each document gets two hidden attributes on its root component:
        ShopPrentice.docKey     — stable UUID, never changes (provenance key)
        ShopPrentice.sessionId  — current owning session (changes on transfer)
"""

import threading
import time
import uuid
from typing import Dict, List, Optional

import adsk.core

app = adsk.core.Application.get()


# ── document-attribute helpers (module-level, not singleton methods) ──
# These are stateless operations on a Fusion document. Keeping them at
# module level (rather than as SessionManager methods) means a hot add-in
# reload re-binds them immediately — a cached singleton instance does not
# need to be rebuilt. Call sites import them directly:
#     from server.session_manager import tag_script_path
def tag_script_path(doc, script_path: str) -> None:
    """Persist script_path as a Fusion document attribute for auto-reclaim."""
    try:
        import adsk.fusion
        design = adsk.fusion.Design.cast(
            doc.products.itemByProductType("DesignProductType"))
        if design:
            design.rootComponent.attributes.add(
                "ShopPrentice", "scriptPath", script_path)
    except Exception as e:
        app.log(f"[session] failed to tag scriptPath: {e}")


def find_document_by_script_path(script_path: str):
    """Scan open documents for one tagged with the given scriptPath.

    Returns (doc, doc_key) if found, else (None, None).
    """
    import adsk.fusion
    for i in range(app.documents.count):
        doc = app.documents.item(i)
        try:
            design = adsk.fusion.Design.cast(
                doc.products.itemByProductType("DesignProductType"))
            if not design:
                continue
            root = design.rootComponent
            attr = root.attributes.itemByName("ShopPrentice", "scriptPath")
            if attr and attr.value == script_path:
                dk_attr = root.attributes.itemByName("ShopPrentice", "docKey")
                doc_key = dk_attr.value if dk_attr else None
                return doc, doc_key
        except Exception:
            continue
    return None, None


class Session:
    """State for one MCP client connection."""

    def __init__(self, session_id: str):
        self.session_id: str = session_id
        self.document_name: Optional[str] = None
        self.doc_key: Optional[str] = None
        self._doc_ref = None
        self.status: str = "active"  # active | orphaned | doc_gone
        self.created_at: float = time.time()
        self.last_active: float = time.time()

    @property
    def document(self):
        if self._doc_ref is not None:
            try:
                if self._doc_ref.isValid:
                    return self._doc_ref
            except Exception:
                pass
            self._doc_ref = None
            self.document_name = None
        return None

    @document.setter
    def document(self, doc):
        self._doc_ref = doc
        self.document_name = doc.name if doc else None


class _QueueEntry:
    """One pending tool execution waiting for its turn."""
    __slots__ = ('tool_name', 'session_id', 'enqueued_at', 'ready')

    def __init__(self, tool_name: str, session_id: Optional[str]):
        self.tool_name = tool_name
        self.session_id = session_id
        self.enqueued_at = time.time()
        self.ready = threading.Event()


class ExecutionQueue:
    """FIFO queue that serializes main-thread tool executions.

    Each HTTP thread calls ``enter()`` which blocks until it is that
    request's turn.  After execution completes, ``leave()`` wakes the
    next waiter.  The queue also tracks whether Fusion has started
    processing the active callback so callers can distinguish "waiting
    in queue" from "Fusion is unresponsive".
    """

    CALLBACK_START_TIMEOUT: float = 30.0

    def __init__(self):
        self._lock = threading.Lock()
        self._waiters: List[_QueueEntry] = []
        self._active: Optional[_QueueEntry] = None
        self._callback_started = False
        self._callback_started_at: Optional[float] = None

    def enter(self, tool_name: str, session_id: Optional[str]) -> dict:
        """Block until it is this request's turn.

        Returns metadata the caller can attach to the tool response:
        ``queue_depth_on_entry`` and ``wait_time``.
        """
        entry = _QueueEntry(tool_name, session_id)

        with self._lock:
            if self._active is None:
                self._active = entry
                self._callback_started = False
                self._callback_started_at = None
                return {"queue_depth_on_entry": 0, "wait_time": 0.0}

            depth = len(self._waiters) + 1
            self._waiters.append(entry)

        app.log(
            f"[queue] {tool_name} (session "
            f"{session_id[:8] if session_id else 'none'}): "
            f"queued at position {depth}"
        )

        entry.ready.wait()

        wait_time = time.time() - entry.enqueued_at
        app.log(f"[queue] {tool_name}: ready after {wait_time:.1f}s wait")

        return {
            "queue_depth_on_entry": depth,
            "wait_time": round(wait_time, 2),
        }

    def mark_callback_started(self):
        """Called from the main-thread callback to confirm Fusion is alive."""
        with self._lock:
            self._callback_started = True
            self._callback_started_at = time.time()

    def leave(self):
        """Signal the next waiter that it is their turn."""
        with self._lock:
            if self._waiters:
                nxt = self._waiters.pop(0)
                self._active = nxt
                self._callback_started = False
                self._callback_started_at = None
                nxt.ready.set()
            else:
                self._active = None
                self._callback_started = False
                self._callback_started_at = None

    def check_health(
        self, posted_at: float, tool_name: Optional[str] = None,
    ) -> Optional[str]:
        """Return ``None`` if healthy, or an error string if Fusion
        appears unresponsive (callback never started).

        When *tool_name* is ``"execute_script"`` the message prompts
        the agent to review its script for crash-causing bugs while
        the user restarts Fusion.
        """
        with self._lock:
            if self._callback_started:
                return None
            elapsed = time.time() - posted_at
            if elapsed > self.CALLBACK_START_TIMEOUT:
                lines = [
                    f"Fusion 360 has not responded to the "
                    f"'{tool_name or 'unknown'}' call after "
                    f"{elapsed:.0f}s — it appears frozen or crashed.",
                    "",
                    "**Action required:**",
                    "1. Tell the user that Fusion 360 is unresponsive "
                    "and needs to be restarted (or the ShopPrentice "
                    "add-in reloaded).",
                ]
                if tool_name == "execute_script":
                    lines.extend([
                        "2. While waiting for the restart, review the "
                        "script you just sent for crash-causing bugs:",
                        "   - Infinite loops or unbounded recursion",
                        "   - doc.close() / app.documents.add() calls "
                        "(forbidden — the harness manages documents)",
                        "   - TemporaryBRepManager use (unsupported)",
                        "   - Very large body counts or complex boolean "
                        "operations that exhaust memory",
                        "3. Prepare a corrected script so you can "
                        "re-run it immediately after the restart.",
                    ])
                else:
                    lines.append(
                        "2. Once Fusion is restarted, retry this "
                        "tool call."
                    )
                return "\n".join(lines)
        return None

    def get_status(self) -> dict:
        """Snapshot of queue state for diagnostics."""
        with self._lock:
            return {
                "active_tool": (
                    self._active.tool_name if self._active else None
                ),
                "active_session": (
                    self._active.session_id[:8]
                    if self._active and self._active.session_id
                    else None
                ),
                "callback_started": self._callback_started,
                "active_running_for": (
                    round(time.time() - self._callback_started_at, 1)
                    if self._callback_started_at else None
                ),
                "queue_depth": len(self._waiters),
                "waiting": [
                    {
                        "tool": e.tool_name,
                        "session": (
                            e.session_id[:8] if e.session_id else None
                        ),
                        "waiting_for": round(
                            time.time() - e.enqueued_at, 1
                        ),
                    }
                    for e in self._waiters
                ],
            }


class SessionManager:
    """Singleton that owns the session→document registry."""

    _instance: Optional["SessionManager"] = None

    MIN_COOLDOWN: float = 0.2
    MAX_SESSIONS: int = 4

    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        self._doc_to_session: Dict[str, str] = {}
        self._doc_provenance: Dict[str, dict] = {}  # doc_key → state
        self._loaded_doc_key: Optional[str] = None   # which doc's state is in globals
        self._last_execution: float = 0.0
        self._current_session_id: Optional[str] = None
        self._doc_closing_handler = None
        self._execution_queue = ExecutionQueue()

    # ── singleton ──────────────────────────────────────────────────────

    @classmethod
    def instance(cls) -> "SessionManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        if cls._instance is not None:
            cls._instance.stop()
        cls._instance = None

    # ── lifecycle ──────────────────────────────────────────────────────

    def start(self):
        self._subscribe_document_events()
        app.log("SessionManager started")

    def stop(self):
        self._unsubscribe_document_events()
        self._sessions.clear()
        self._doc_to_session.clear()
        self._doc_provenance.clear()
        app.log("SessionManager stopped")

    # ── session CRUD ───────────────────────────────────────────────────

    def create_session(self) -> str:
        if len(self._sessions) >= self.MAX_SESSIONS:
            self._evict_oldest_orphan()
        session_id = uuid.uuid4().hex
        self._sessions[session_id] = Session(session_id)
        app.log(f"Session created: {session_id[:8]}")
        return session_id

    def get_session(self, session_id: str) -> Optional[Session]:
        session = self._sessions.get(session_id)
        if session is not None:
            session.last_active = time.time()
        return session

    def mark_orphaned(self, session_id: str):
        session = self._sessions.get(session_id)
        if session is not None:
            session.status = "orphaned"
            app.log(f"Session {session_id[:8]} orphaned")

    # ── document binding ───────────────────────────────────────────────

    def bind_document(self, session_id: str, doc) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return

        # Unbind previous doc (by docKey, not name)
        if session.doc_key and session.doc_key in self._doc_to_session:
            if self._doc_to_session[session.doc_key] == session_id:
                del self._doc_to_session[session.doc_key]

        session.document = doc
        session.status = "active"
        if doc is not None:
            doc_key = self._tag_document(doc, session_id)
            session.doc_key = doc_key
            self._doc_to_session[doc_key] = session_id
        else:
            session.doc_key = None
        app.log(
            f"Session {session_id[:8]} bound to "
            f"{doc.name if doc else '(none)'}"
            f" (doc_key={session.doc_key[:8] if session.doc_key else 'none'})"
        )

    def unbind_document(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        if session.doc_key and session.doc_key in self._doc_to_session:
            del self._doc_to_session[session.doc_key]
        session.document = None
        session.doc_key = None

    # ── document activation gate ───────────────────────────────────────

    def activate_document(self, session_id: str):
        """Activate the session's document and load its provenance.

        Returns None on success, ``"doc_gone"`` sentinel, or an error dict.
        """
        session = self._sessions.get(session_id)
        if session is None:
            session = Session(session_id)
            self._sessions[session_id] = session
            app.log(f"Session {session_id[:8]} auto-recreated (stale)")
            return "session_recovered"

        if session.status == "doc_gone":
            self._load_provenance(session.doc_key)
            return "doc_gone"

        if session._doc_ref is None:
            self._load_provenance(session.doc_key)
            return None

        if not self._verify_and_activate(session):
            self._mark_doc_gone(session)
            return "doc_gone"

        self._load_provenance(session.doc_key)
        return None

    # ── throttle gate ──────────────────────────────────────────────────

    def throttle_gate(self) -> None:
        now = time.time()
        gap = now - self._last_execution
        if gap < self.MIN_COOLDOWN:
            time.sleep(self.MIN_COOLDOWN - gap)

    def record_execution_end(self) -> None:
        self._last_execution = time.time()

    # ── claim / transfer ───────────────────────────────────────────────

    def claim_document(
        self,
        session_id: str,
        document_name: Optional[str] = None,
        doc_key: Optional[str] = None,
        resolution: Optional[str] = None,
    ) -> dict:
        session = self._sessions.get(session_id)
        if session is None:
            return {"error": True, "message": "Session not found."}

        if doc_key:
            target_doc, err = self._resolve_doc_by_key(doc_key)
        else:
            target_doc, err = self._resolve_target_doc(document_name)
        if err:
            return err
        doc_name = target_doc.name

        target_key = self._read_doc_key(target_doc)
        owner_sid = self._doc_to_session.get(target_key) if target_key else None
        if owner_sid and owner_sid != session_id:
            owner = self._sessions.get(owner_sid)
            if owner and owner.status == "active":
                return self._handle_conflict(
                    session_id, owner_sid, doc_name, target_doc, resolution
                )
            if owner:
                self.unbind_document(owner_sid)

        self.unbind_document(session_id)
        self.bind_document(session_id, target_doc)
        return {
            "success": True,
            "message": f"Document '{doc_name}' bound to your session.",
            "document_name": doc_name,
        }

    # ── document-closed event ──────────────────────────────────────────

    def on_document_closed(self) -> None:
        for sid, session in list(self._sessions.items()):
            if session._doc_ref is not None:
                try:
                    valid = session._doc_ref.isValid
                except Exception:
                    valid = False
                if not valid:
                    if session.doc_key and session.doc_key in self._doc_to_session:
                        if self._doc_to_session[session.doc_key] == sid:
                            del self._doc_to_session[session.doc_key]
                    session.status = "doc_gone"
                    session._doc_ref = None
                    session.document_name = None
                    app.log(f"Document closed — session {sid[:8]} marked doc_gone")

    # ── diagnostics ────────────────────────────────────────────────────

    def list_sessions(self) -> List[dict]:
        out = []
        for s in self._sessions.values():
            out.append({
                "session_id": s.session_id[:8],
                "document": s.document_name,
                "doc_key": s.doc_key[:8] if s.doc_key else None,
                "status": s.status,
            })
        return out

    def list_available_documents(self) -> list:
        """Return info about all open documents with ShopPrentice tags."""
        import adsk.fusion
        docs = []
        for i in range(app.documents.count):
            doc = app.documents.item(i)
            try:
                design = adsk.fusion.Design.cast(
                    doc.products.itemByProductType("DesignProductType"))
                if not design:
                    continue
                root = design.rootComponent
                dk = root.attributes.itemByName("ShopPrentice", "docKey")
                sid = root.attributes.itemByName("ShopPrentice", "sessionId")
                doc_key = dk.value if dk else None
                owner_sid = sid.value if sid else None
                owner_session = self._sessions.get(owner_sid) if owner_sid else None
                docs.append({
                    "index": i,
                    "name": doc.name,
                    "doc_key": doc_key,
                    "owner_session": owner_sid[:8] if owner_sid else None,
                    "owner_status": owner_session.status if owner_session else "none",
                    "body_count": sum(
                        1 for _ in range(root.bRepBodies.count)
                    ) + sum(
                        occ.component.bRepBodies.count
                        for occ in root.allOccurrences
                    ),
                })
            except Exception:
                continue
        return docs

    # ── current-session context ────────────────────────────────────────

    @property
    def current_session_id(self) -> Optional[str]:
        return self._current_session_id

    @current_session_id.setter
    def current_session_id(self, value: Optional[str]):
        self._current_session_id = value

    # ── document-keyed provenance ──────────────────────────────────────

    def save_provenance(self, doc_key: Optional[str] = None) -> None:
        """Save current ActionLog + DocumentTracker globals for a document.

        When *doc_key* is omitted, saves under ``_loaded_doc_key`` (the key
        whose state is currently in the globals), NOT the active document's
        key.  This prevents saving A's globals under B when the user
        switched documents in the Fusion UI.
        """
        if doc_key is None:
            doc_key = self._loaded_doc_key
        if doc_key is None:
            return
        state = {}
        try:
            from server.document_tracker import DocumentTracker as DT
            state["tracker"] = {
                "script_source": DT._script_source,
                "script_path": DT._script_path,
                "script_hash": DT._script_hash,
                "sync_cursor": DT._sync_cursor,
                "reference_model_params": DT._reference_model_params,
                "doc_ref": DT._doc_ref,
                "restored": DT._restored,
            }
        except Exception:
            pass
        try:
            from server.action_log import ActionLog as AL
            state["action_log"] = {
                "entries": list(AL._entries),
                "baseline": AL._baseline,
                "last_timeline_count": AL._last_timeline_count,
                "last_param_hash": AL._last_param_hash,
                "last_read_cursor": AL._last_read_cursor,
                "log_file": AL._log_file,
            }
        except Exception:
            pass
        self._doc_provenance[doc_key] = state

    def _load_provenance(self, doc_key: Optional[str]) -> None:
        """Restore ActionLog + DocumentTracker globals for a document."""
        self._loaded_doc_key = doc_key
        state = self._doc_provenance.get(doc_key) if doc_key else None

        tracker = state.get("tracker") if state else None
        if tracker is not None:
            try:
                from server.document_tracker import DocumentTracker as DT
                DT._script_source = tracker["script_source"]
                DT._script_path = tracker["script_path"]
                DT._script_hash = tracker["script_hash"]
                DT._sync_cursor = tracker["sync_cursor"]
                DT._reference_model_params = tracker["reference_model_params"]
                DT._doc_ref = tracker["doc_ref"]
                DT._restored = tracker["restored"]
            except Exception:
                pass
        else:
            try:
                from server.document_tracker import DocumentTracker as DT
                DT._clear_memory()
            except Exception:
                pass

        action_log = state.get("action_log") if state else None
        if action_log is not None:
            try:
                from server.action_log import ActionLog as AL
                AL._entries = action_log["entries"]
                AL._baseline = action_log["baseline"]
                AL._last_timeline_count = action_log["last_timeline_count"]
                AL._last_param_hash = action_log["last_param_hash"]
                AL._last_read_cursor = action_log["last_read_cursor"]
                AL._log_file = action_log["log_file"]
            except Exception:
                pass
        else:
            try:
                from server.action_log import ActionLog as AL
                AL._entries = []
                AL._baseline = None
                AL._last_timeline_count = None
                AL._last_param_hash = None
                AL._last_read_cursor = None
                AL._log_file = None
            except Exception:
                pass

    # ── internals ──────────────────────────────────────────────────────

    def _resolve_doc_by_key(self, doc_key: str):
        """Find an open document by its docKey attribute."""
        import adsk.fusion
        for i in range(app.documents.count):
            doc = app.documents.item(i)
            try:
                design = adsk.fusion.Design.cast(
                    doc.products.itemByProductType("DesignProductType"))
                if not design:
                    continue
                attr = design.rootComponent.attributes.itemByName(
                    "ShopPrentice", "docKey")
                if attr and attr.value == doc_key:
                    return doc, None
            except Exception:
                continue
        return None, {
            "error": True,
            "message": f"No open document with doc_key '{doc_key[:8]}...'.",
        }

    def _read_doc_key(self, doc) -> Optional[str]:
        """Read the docKey attribute from a document without activating it."""
        try:
            import adsk.fusion
            design = adsk.fusion.Design.cast(
                doc.products.itemByProductType("DesignProductType"))
            if design:
                attr = design.rootComponent.attributes.itemByName(
                    "ShopPrentice", "docKey")
                if attr:
                    return attr.value
        except Exception:
            pass
        return None

    def _resolve_target_doc(self, name: Optional[str]):
        if name:
            for i in range(app.documents.count):
                doc = app.documents.item(i)
                if doc.name == name:
                    return doc, None
            return None, {
                "error": True,
                "message": f"No open document named '{name}'.",
            }
        else:
            try:
                doc = app.activeDocument
                if doc:
                    return doc, None
            except Exception:
                pass
            return None, {"error": True, "message": "No active document."}

    def _handle_conflict(self, claiming_sid, owner_sid, doc_name, doc, resolution):
        if resolution == "transfer":
            owner = self._sessions.get(owner_sid)
            if owner:
                self.unbind_document(owner_sid)
            self.unbind_document(claiming_sid)
            self.bind_document(claiming_sid, doc)
            return {
                "success": True,
                "message": (
                    f"Document '{doc_name}' transferred to your session. "
                    "The previous session no longer has a document."
                ),
                "document_name": doc_name,
            }

        if resolution == "keep_existing":
            return {
                "success": False,
                "message": (
                    f"Document '{doc_name}' remains with the existing session. "
                    "Your session has no document — use execute_script(clean=True) "
                    "to create a new one."
                ),
                "document_name": doc_name,
            }

        return {
            "conflict": True,
            "document_name": doc_name,
            "current_owner": owner_sid[:8],
            "message": (
                f"Document '{doc_name}' is currently bound to another active "
                "session.  Only one session can control a document at a time.\n\n"
                "Ask the user which option they prefer, then call "
                "claim_document again with the chosen resolution:\n"
                "  resolution='transfer'       — move the document to your "
                "session (the other session loses it)\n"
                "  resolution='keep_existing'  — leave it with the current "
                "session (you'll need to create or claim a different document)"
            ),
        }

    def _tag_document(self, doc, session_id: str) -> str:
        """Stamp the design with sessionId and a stable docKey.

        Returns the docKey (existing or newly created).
        """
        doc_key = None
        try:
            import adsk.fusion
            design = adsk.fusion.Design.cast(
                doc.products.itemByProductType("DesignProductType"))
            if design:
                root = design.rootComponent
                root.attributes.add(
                    "ShopPrentice", "sessionId", session_id)
                existing = root.attributes.itemByName(
                    "ShopPrentice", "docKey")
                if existing:
                    doc_key = existing.value
                else:
                    doc_key = uuid.uuid4().hex
                    root.attributes.add(
                        "ShopPrentice", "docKey", doc_key)
        except Exception as e:
            app.log(f"[session] failed to tag document: {e}")
        return doc_key or uuid.uuid4().hex

    def _verify_and_activate(self, session) -> bool:
        """Find this session's document by scanning for its sessionId tag."""
        import adsk.fusion
        target_sid = session.session_id
        for i in range(app.documents.count):
            doc = app.documents.item(i)
            try:
                design = adsk.fusion.Design.cast(
                    doc.products.itemByProductType("DesignProductType"))
                if not design:
                    continue
                attr = design.rootComponent.attributes.itemByName(
                    "ShopPrentice", "sessionId")
                if attr and attr.value == target_sid:
                    session._doc_ref = doc
                    dk = design.rootComponent.attributes.itemByName(
                        "ShopPrentice", "docKey")
                    if dk:
                        session.doc_key = dk.value
                    try:
                        if app.activeDocument is not doc:
                            doc.activate()
                    except Exception:
                        pass
                    return True
            except Exception:
                continue
        return False

    def _mark_doc_gone(self, session) -> None:
        sid = session.session_id
        if session.doc_key and session.doc_key in self._doc_to_session:
            if self._doc_to_session[session.doc_key] == sid:
                del self._doc_to_session[session.doc_key]
        session.status = "doc_gone"
        session._doc_ref = None
        session.document_name = None

    def _evict_oldest_orphan(self):
        oldest = None
        for s in list(self._sessions.values()):
            if s.status == "orphaned":
                if oldest is None or s.last_active < oldest.last_active:
                    oldest = s
        if oldest:
            self.unbind_document(oldest.session_id)
            del self._sessions[oldest.session_id]
            app.log(f"Evicted orphaned session {oldest.session_id[:8]}")

    def _subscribe_document_events(self):
        try:
            handler = _DocClosedHandler()
            app.documentClosed.add(handler)
            self._doc_closing_handler = handler
        except Exception as e:
            app.log(f"SessionManager: failed to subscribe documentClosed: {e}")

    def _unsubscribe_document_events(self):
        if self._doc_closing_handler is not None:
            try:
                app.documentClosed.remove(self._doc_closing_handler)
            except Exception:
                pass
            self._doc_closing_handler = None

    # ── back-compat shims (called from mcp_server callback) ────────────

    def _save_global_state(self, session) -> None:
        """Save provenance keyed by the session's current document."""
        self.save_provenance(session.doc_key)

    def _restore_global_state(self, session) -> None:
        """Load provenance for the session's current document."""
        self._load_provenance(session.doc_key)


class _DocClosedHandler(adsk.core.DocumentEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.DocumentEventArgs):
        try:
            SessionManager.instance().on_document_closed()
        except Exception:
            pass
