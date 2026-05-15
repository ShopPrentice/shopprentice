"""
Session Manager

Maps MCP sessions to Fusion 360 documents so multiple agents can work on
separate documents without stepping on each other.  The MCP server reads
the Mcp-Session-Id HTTP header to identify the caller, then the
SessionManager activates the correct document before every tool execution.

Lifecycle:
    initialize  →  SessionManager.create_session()  →  new UUID
    tool call   →  SessionManager.activate_document(sid) → doc.activate()
    disconnect  →  SessionManager.mark_orphaned(sid)
    doc closed  →  SessionManager.on_document_closed(name)
"""

import time
import uuid
from typing import Dict, List, Optional

import adsk.core

app = adsk.core.Application.get()


class Session:
    """State for one MCP client connection."""

    def __init__(self, session_id: str):
        self.session_id: str = session_id
        self.document_name: Optional[str] = None
        self._doc_ref = None
        self.status: str = "active"  # active | orphaned | doc_gone
        self.created_at: float = time.time()
        self.last_active: float = time.time()
        self._tracker_state: Optional[dict] = None
        self._action_log_state: Optional[dict] = None

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


class SessionManager:
    """Singleton that owns the session→document registry."""

    _instance: Optional["SessionManager"] = None

    MIN_COOLDOWN: float = 0.2  # seconds between main-thread executions
    MAX_SESSIONS: int = 4

    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        self._doc_to_session: Dict[str, str] = {}  # doc_name → session_id
        self._last_execution: float = 0.0
        self._current_session_id: Optional[str] = None
        self._doc_closing_handler = None

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

        # unbind previous document — only delete OUR entry, not another session's
        if session.document_name and session.document_name in self._doc_to_session:
            if self._doc_to_session[session.document_name] == session_id:
                del self._doc_to_session[session.document_name]

        session.document = doc
        session.status = "active"
        session._tracker_state = None
        session._action_log_state = None
        if doc is not None:
            self._doc_to_session[doc.name] = session_id
            self._tag_document(doc, session_id)
        app.log(
            f"Session {session_id[:8]} bound to "
            f"{doc.name if doc else '(none)'}"
        )

    def unbind_document(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        if session.document_name and session.document_name in self._doc_to_session:
            del self._doc_to_session[session.document_name]
        session.document = None

    # ── document activation gate ───────────────────────────────────────

    def activate_document(self, session_id: str):
        """Activate the session's document before a tool runs.

        Returns None on success, or an error-result dict if the session's
        document is gone (so the callback can short-circuit the tool).
        Does nothing when the session has no bound document — tools like
        execute_script handle that case themselves.

        Also saves the outgoing session's ActionLog/DocumentTracker state
        and restores the incoming session's, so each session has its own
        provenance context.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return {
                "content": [{
                    "type": "text",
                    "text": (
                        "Unknown session ID — your session may have "
                        "expired after an add-in restart. Reconnect by "
                        "sending a new initialize request."
                    ),
                }],
                "isError": True,
                "message": "Unknown session ID",
            }

        if session.status == "doc_gone":
            self._restore_global_state(session)
            return "doc_gone"

        if session._doc_ref is None:
            self._restore_global_state(session)
            return None  # no doc bound yet — let tool handle it

        # Scan open documents for our tag — don't trust proxy refs
        if not self._verify_and_activate(session):
            self._mark_doc_gone(session)
            return "doc_gone"

        # Restore incoming session's provenance state
        self._restore_global_state(session)
        return None

    # ── throttle gate ──────────────────────────────────────────────────

    def throttle_gate(self) -> None:
        now = time.time()
        gap = now - self._last_execution
        if gap < self.MIN_COOLDOWN:
            time.sleep(self.MIN_COOLDOWN - gap)
        self._last_execution = time.time()

    # ── claim / transfer ───────────────────────────────────────────────

    def claim_document(
        self,
        session_id: str,
        document_name: Optional[str] = None,
        resolution: Optional[str] = None,
    ) -> dict:
        """Attempt to claim a document for *session_id*.

        Returns a result dict.  When the target doc belongs to a live
        session and no *resolution* is given, returns a ``conflict`` dict
        with available options.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return {"error": True, "message": "Session not found."}

        # resolve target document
        target_doc, err = self._resolve_target_doc(document_name)
        if err:
            return err
        doc_name = target_doc.name

        # check existing owner
        owner_sid = self._doc_to_session.get(doc_name)
        if owner_sid and owner_sid != session_id:
            owner = self._sessions.get(owner_sid)
            if owner and owner.status == "active":
                return self._handle_conflict(
                    session_id, owner_sid, doc_name, target_doc, resolution
                )
            # orphaned or gone — safe to reclaim
            if owner:
                self.unbind_document(owner_sid)

        # unbind this session's old doc (if any)
        self.unbind_document(session_id)
        self.bind_document(session_id, target_doc)
        return {
            "success": True,
            "message": f"Document '{doc_name}' bound to your session.",
            "document_name": doc_name,
        }

    # ── document-closed event ──────────────────────────────────────────

    def on_document_closed(self) -> None:
        """After a document closes, scan for sessions with stale refs."""
        for sid, session in self._sessions.items():
            if session._doc_ref is not None:
                try:
                    valid = session._doc_ref.isValid
                except Exception:
                    valid = False
                if not valid:
                    old_name = session.document_name
                    if old_name and old_name in self._doc_to_session:
                        if self._doc_to_session[old_name] == sid:
                            del self._doc_to_session[old_name]
                    session.status = "doc_gone"
                    session._doc_ref = None
                    session.document_name = None
                    app.log(f"Document '{old_name}' closed — session {sid[:8]} marked doc_gone")

    # ── diagnostics ────────────────────────────────────────────────────

    def list_sessions(self) -> List[dict]:
        out = []
        for s in self._sessions.values():
            out.append({
                "session_id": s.session_id[:8],
                "document": s.document_name,
                "status": s.status,
            })
        return out

    # ── current-session context (set by MCP server during execution) ──

    @property
    def current_session_id(self) -> Optional[str]:
        return self._current_session_id

    @current_session_id.setter
    def current_session_id(self, value: Optional[str]):
        self._current_session_id = value

    # ── internals ──────────────────────────────────────────────────────

    def _resolve_target_doc(self, name: Optional[str]):
        """Return (doc, None) or (None, error_dict)."""
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

        # no resolution — present the conflict
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

    # ── per-session provenance save/restore ──────────────────────────

    def _save_global_state(self, session) -> None:
        """Snapshot ActionLog + DocumentTracker globals into the session."""
        try:
            from server.document_tracker import DocumentTracker as DT
            session._tracker_state = {
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
            session._action_log_state = {
                "entries": list(AL._entries),
                "baseline": AL._baseline,
                "last_timeline_count": AL._last_timeline_count,
                "last_param_hash": AL._last_param_hash,
                "last_read_cursor": AL._last_read_cursor,
                "log_file": AL._log_file,
            }
        except Exception:
            pass

    def _restore_global_state(self, session) -> None:
        """Restore ActionLog + DocumentTracker globals from the session."""
        if session._tracker_state is not None:
            try:
                from server.document_tracker import DocumentTracker as DT
                s = session._tracker_state
                DT._script_source = s["script_source"]
                DT._script_path = s["script_path"]
                DT._script_hash = s["script_hash"]
                DT._sync_cursor = s["sync_cursor"]
                DT._reference_model_params = s["reference_model_params"]
                DT._doc_ref = s["doc_ref"]
                DT._restored = s["restored"]
            except Exception:
                pass
        else:
            try:
                from server.document_tracker import DocumentTracker as DT
                DT._clear_memory()
            except Exception:
                pass

        if session._action_log_state is not None:
            try:
                from server.action_log import ActionLog as AL
                s = session._action_log_state
                AL._entries = s["entries"]
                AL._baseline = s["baseline"]
                AL._last_timeline_count = s["last_timeline_count"]
                AL._last_param_hash = s["last_param_hash"]
                AL._last_read_cursor = s["last_read_cursor"]
                AL._log_file = s["log_file"]
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

    def _tag_document(self, doc, session_id: str) -> None:
        """Stamp the design with our session ID so we can verify later."""
        try:
            import adsk.fusion
            design = adsk.fusion.Design.cast(
                doc.products.itemByProductType("DesignProductType"))
            if design:
                design.rootComponent.attributes.add(
                    "ShopPrentice", "sessionId", session_id)
        except Exception as e:
            app.log(f"[session] failed to tag document: {e}")

    def _verify_and_activate(self, session) -> bool:
        """Find this session's document by scanning for its attribute tag.

        Does NOT trust proxy references (Fusion recycles them after close).
        Scans all open documents, finds the one tagged with this session's
        ID, updates ``_doc_ref`` to the current proxy, and activates it.
        """
        import adsk.fusion
        target_sid = session.session_id
        doc_count = app.documents.count
        app.log(f"[verify] scanning {doc_count} docs for session {target_sid[:8]}")
        for i in range(doc_count):
            doc = app.documents.item(i)
            try:
                design = adsk.fusion.Design.cast(
                    doc.products.itemByProductType("DesignProductType"))
                if not design:
                    app.log(f"[verify]   doc[{i}] '{doc.name}' — no design")
                    continue
                attr = design.rootComponent.attributes.itemByName(
                    "ShopPrentice", "sessionId")
                attr_val = attr.value if attr else None
                app.log(f"[verify]   doc[{i}] '{doc.name}' — tag={attr_val}")
                if attr and attr.value == target_sid:
                    session._doc_ref = doc
                    try:
                        if app.activeDocument is not doc:
                            doc.activate()
                    except Exception:
                        pass
                    return True
            except Exception as e:
                app.log(f"[verify]   doc[{i}] exception: {e}")
                continue
        app.log(f"[verify] no match for {target_sid[:8]} — doc_gone")
        return False

    def _mark_doc_gone(self, session) -> None:
        sid = session.session_id
        old_name = session.document_name
        if old_name and old_name in self._doc_to_session:
            if self._doc_to_session[old_name] == sid:
                del self._doc_to_session[old_name]
        session.status = "doc_gone"
        session._doc_ref = None
        session.document_name = None
        app.log(f"[activate] {sid[:8]} marked doc_gone (was '{old_name}')")

    def _evict_oldest_orphan(self):
        oldest = None
        for s in self._sessions.values():
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


class _DocClosedHandler(adsk.core.DocumentEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.DocumentEventArgs):
        try:
            SessionManager.instance().on_document_closed()
        except Exception:
            pass
