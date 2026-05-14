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

        # unbind previous document
        if session.document_name and session.document_name in self._doc_to_session:
            del self._doc_to_session[session.document_name]

        session.document = doc
        session.status = "active"
        if doc is not None:
            self._doc_to_session[doc.name] = session_id
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

    def activate_document(self, session_id: str) -> None:
        """Activate the session's document before a tool runs.

        Does nothing when the session has no bound document — tools like
        execute_script handle that case themselves.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return

        doc = session.document  # property validates isValid
        if doc is None:
            if session.status != "doc_gone" and session.document_name:
                session.status = "doc_gone"
                if session.document_name in self._doc_to_session:
                    del self._doc_to_session[session.document_name]
            return

        try:
            current = app.activeDocument
            if current is not doc:
                doc.activate()
        except Exception:
            session.status = "doc_gone"
            session._doc_ref = None

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

    def on_document_closed(self, doc_name: str) -> None:
        sid = self._doc_to_session.pop(doc_name, None)
        if sid is None:
            return
        session = self._sessions.get(sid)
        if session is not None:
            session.status = "doc_gone"
            session._doc_ref = None
            session.document_name = None
            app.log(f"Document '{doc_name}' closed — session {sid[:8]} marked doc_gone")

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
            handler = _DocClosingHandler()
            app.documentClosing.add(handler)
            self._doc_closing_handler = handler
        except Exception as e:
            app.log(f"SessionManager: failed to subscribe documentClosing: {e}")

    def _unsubscribe_document_events(self):
        if self._doc_closing_handler is not None:
            try:
                app.documentClosing.remove(self._doc_closing_handler)
            except Exception:
                pass
            self._doc_closing_handler = None


class _DocClosingHandler(adsk.core.DocumentEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.DocumentEventArgs):
        try:
            doc = args.document
            if doc:
                SessionManager.instance().on_document_closed(doc.name)
        except Exception:
            pass
