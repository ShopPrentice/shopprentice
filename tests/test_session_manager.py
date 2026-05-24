"""
Tests for SessionManager — multi-agent document isolation.

Runs outside Fusion 360 using shared mock fixtures.
"""

import importlib.util
import os
import sys
import unittest
from unittest.mock import MagicMock

# Shared mocks — compatible with test_document_tracker
from tests.fixtures.mock_adsk import setup as _setup_mocks
_m = _setup_mocks()
mock_app = _m["app"]
MockActionLog = _m["ActionLog"]
MockDocTracker = _m["DocumentTracker"]

# Import SessionManager
if "server.session_manager" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "server.session_manager",
        os.path.join(os.path.dirname(__file__), "..", "addin", "server", "session_manager.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["server.session_manager"] = mod
    spec.loader.exec_module(mod)
else:
    mod = sys.modules["server.session_manager"]

SessionManager = mod.SessionManager
Session = mod.Session


def _make_doc(name="Untitled"):
    doc = MagicMock()
    doc.isValid = True
    doc.name = name
    products = MagicMock()
    design = MagicMock()
    root = MagicMock()
    root.attributes = MagicMock()

    doc._attrs = {}

    def add_attr(group, name, value):
        doc._attrs[f"{group}.{name}"] = value

    def get_attr(group, name):
        key = f"{group}.{name}"
        if key in doc._attrs:
            attr = MagicMock()
            attr.value = doc._attrs[key]
            return attr
        return None

    root.attributes.add = add_attr
    root.attributes.itemByName = get_attr
    design.rootComponent = root
    sys.modules["adsk.fusion"].Design.cast.side_effect = lambda x: x
    products.itemByProductType.return_value = design
    doc.products = products
    return doc


class TestSessionCRUD(unittest.TestCase):

    def setUp(self):
        SessionManager.reset()
        self.sm = SessionManager.instance()
        # Disable document events (no real Fusion)
        self.sm._subscribe_document_events = lambda: None

    def test_create_session(self):
        sid = self.sm.create_session()
        self.assertIsNotNone(sid)
        self.assertEqual(len(sid), 32)  # hex UUID
        session = self.sm.get_session(sid)
        self.assertIsNotNone(session)
        self.assertEqual(session.status, "active")

    def test_max_sessions_evicts_orphan(self):
        sids = []
        for _ in range(4):
            sids.append(self.sm.create_session())
        self.sm.mark_orphaned(sids[0])
        # 5th session should evict the orphan
        sid5 = self.sm.create_session()
        self.assertIsNone(self.sm.get_session(sids[0]))
        self.assertIsNotNone(self.sm.get_session(sid5))

    def test_unknown_session_returns_none(self):
        self.assertIsNone(self.sm.get_session("nonexistent"))


class TestDocumentBinding(unittest.TestCase):

    def setUp(self):
        SessionManager.reset()
        self.sm = SessionManager.instance()
        self.sm._subscribe_document_events = lambda: None

    def test_bind_document(self):
        sid = self.sm.create_session()
        doc = _make_doc("TestDoc")
        self.sm.bind_document(sid, doc)
        session = self.sm.get_session(sid)
        self.assertEqual(session.document_name, "TestDoc")
        self.assertIsNotNone(session.doc_key)

    def test_bind_sets_attributes(self):
        sid = self.sm.create_session()
        doc = _make_doc("TestDoc")
        self.sm.bind_document(sid, doc)
        self.assertEqual(doc._attrs.get("ShopPrentice.sessionId"), sid)
        self.assertIn("ShopPrentice.docKey", doc._attrs)

    def test_doc_key_stable_on_rebind(self):
        """Rebinding same doc preserves docKey."""
        sid1 = self.sm.create_session()
        doc = _make_doc("TestDoc")
        self.sm.bind_document(sid1, doc)
        key1 = self.sm.get_session(sid1).doc_key

        sid2 = self.sm.create_session()
        self.sm.bind_document(sid2, doc)
        key2 = self.sm.get_session(sid2).doc_key

        self.assertEqual(key1, key2)

    def test_unbind_clears_state(self):
        sid = self.sm.create_session()
        doc = _make_doc("TestDoc")
        self.sm.bind_document(sid, doc)
        self.sm.unbind_document(sid)
        session = self.sm.get_session(sid)
        self.assertIsNone(session.doc_key)
        self.assertIsNone(session.document_name)


class TestActivationGate(unittest.TestCase):

    def setUp(self):
        SessionManager.reset()
        self.sm = SessionManager.instance()
        self.sm._subscribe_document_events = lambda: None

    def test_unknown_session_auto_recreated(self):
        """Stale session IDs are auto-recreated so agents survive add-in restarts."""
        result = self.sm.activate_document("nonexistent_id")
        self.assertEqual(result, "session_recovered")
        session = self.sm.get_session("nonexistent_id")
        self.assertIsNotNone(session)
        self.assertEqual(session.status, "active")
        self.assertIsNone(session.doc_key)

    def test_no_doc_returns_none(self):
        sid = self.sm.create_session()
        result = self.sm.activate_document(sid)
        self.assertIsNone(result)

    def test_doc_gone_returns_sentinel(self):
        sid = self.sm.create_session()
        session = self.sm.get_session(sid)
        session.status = "doc_gone"
        session._doc_ref = MagicMock()  # has a ref but status is gone
        result = self.sm.activate_document(sid)
        self.assertEqual(result, "doc_gone")


def _get_DT():
    """Get the DocumentTracker class that _load_provenance actually writes to."""
    return sys.modules["server.document_tracker"].DocumentTracker

def _get_AL():
    """Get the ActionLog class that _load_provenance actually writes to."""
    return sys.modules["server.action_log"].ActionLog


class TestDocumentKeyedProvenance(unittest.TestCase):

    def setUp(self):
        SessionManager.reset()
        self.sm = SessionManager.instance()
        self.sm._subscribe_document_events = lambda: None
        _get_DT()._clear_memory()
        AL = _get_AL()
        AL._entries = []
        AL._baseline = None

    def test_save_and_load_provenance(self):
        DT, AL = _get_DT(), _get_AL()
        sid = self.sm.create_session()
        doc = _make_doc("Doc1")
        self.sm.bind_document(sid, doc)
        doc_key = self.sm.get_session(sid).doc_key

        DT._script_hash = "hash_A"
        DT._script_source = "script_A"
        AL._entries = [{"id": "e1"}]

        self.sm.save_provenance(doc_key)

        DT._clear_memory()
        AL._entries = []

        self.sm._load_provenance(doc_key)
        self.assertEqual(DT._script_hash, "hash_A")
        self.assertEqual(DT._script_source, "script_A")
        self.assertEqual(AL._entries, [{"id": "e1"}])

    def test_load_unknown_key_clears_globals(self):
        DT, AL = _get_DT(), _get_AL()
        DT._script_hash = "stale"
        AL._entries = [{"id": "stale"}]

        self.sm._load_provenance("nonexistent_key")

        self.assertIsNone(DT._script_hash)
        self.assertEqual(AL._entries, [])

    def test_provenance_follows_document_on_transfer(self):
        """When a document is transferred, its provenance follows it."""
        DT = _get_DT()
        sid_a = self.sm.create_session()
        sid_b = self.sm.create_session()
        doc = _make_doc("SharedDoc")

        self.sm.bind_document(sid_a, doc)
        doc_key = self.sm.get_session(sid_a).doc_key

        DT._script_hash = "hash_from_A"
        self.sm.save_provenance(doc_key)

        self.sm.unbind_document(sid_a)
        self.sm.bind_document(sid_b, doc)
        new_key = self.sm.get_session(sid_b).doc_key

        self.assertEqual(new_key, doc_key)

        DT._clear_memory()
        self.sm._load_provenance(new_key)
        self.assertEqual(DT._script_hash, "hash_from_A")

    def test_two_docs_independent_provenance(self):
        DT = _get_DT()
        sid_a = self.sm.create_session()
        sid_b = self.sm.create_session()
        doc_a = _make_doc("DocA")
        doc_b = _make_doc("DocB")

        self.sm.bind_document(sid_a, doc_a)
        self.sm.bind_document(sid_b, doc_b)
        key_a = self.sm.get_session(sid_a).doc_key
        key_b = self.sm.get_session(sid_b).doc_key

        DT._script_hash = "hash_A"
        self.sm.save_provenance(key_a)

        DT._script_hash = "hash_B"
        self.sm.save_provenance(key_b)

        self.sm._load_provenance(key_a)
        self.assertEqual(DT._script_hash, "hash_A")

        self.sm._load_provenance(key_b)
        self.assertEqual(DT._script_hash, "hash_B")

    def test_bind_does_not_clear_provenance(self):
        """bind_document should NOT wipe provenance for the document."""
        DT = _get_DT()
        sid = self.sm.create_session()
        doc = _make_doc("Doc1")
        self.sm.bind_document(sid, doc)
        doc_key = self.sm.get_session(sid).doc_key

        DT._script_hash = "important_hash"
        self.sm.save_provenance(doc_key)

        sid2 = self.sm.create_session()
        self.sm.bind_document(sid2, doc)

        self.sm._load_provenance(doc_key)
        self.assertEqual(DT._script_hash, "important_hash")


class TestClaimDocument(unittest.TestCase):

    def setUp(self):
        SessionManager.reset()
        self.sm = SessionManager.instance()
        self.sm._subscribe_document_events = lambda: None

    def test_claim_unowned_doc(self):
        sid = self.sm.create_session()
        doc = _make_doc("FreeDoc")
        mock_app.activeDocument = doc
        result = self.sm.claim_document(sid)
        self.assertTrue(result.get("success"))
        self.assertEqual(self.sm.get_session(sid).document_name, "FreeDoc")

    def test_claim_conflict_returns_options(self):
        sid_a = self.sm.create_session()
        sid_b = self.sm.create_session()
        doc = _make_doc("Owned")
        self.sm.bind_document(sid_a, doc)
        mock_app.activeDocument = doc

        result = self.sm.claim_document(sid_b)
        self.assertTrue(result.get("conflict"))
        self.assertIn("transfer", result["message"])
        self.assertIn("keep_existing", result["message"])

    def test_claim_transfer(self):
        sid_a = self.sm.create_session()
        sid_b = self.sm.create_session()
        doc = _make_doc("Shared")
        self.sm.bind_document(sid_a, doc)
        mock_app.activeDocument = doc

        result = self.sm.claim_document(sid_b, resolution="transfer")
        self.assertTrue(result.get("success"))
        self.assertIsNone(self.sm.get_session(sid_a).doc_key)
        self.assertIsNotNone(self.sm.get_session(sid_b).doc_key)

    def test_claim_keep_existing(self):
        sid_a = self.sm.create_session()
        sid_b = self.sm.create_session()
        doc = _make_doc("Kept")
        self.sm.bind_document(sid_a, doc)
        mock_app.activeDocument = doc

        result = self.sm.claim_document(sid_b, resolution="keep_existing")
        self.assertFalse(result.get("success"))
        self.assertIsNotNone(self.sm.get_session(sid_a).doc_key)

    def test_claim_orphaned_succeeds(self):
        sid_a = self.sm.create_session()
        sid_b = self.sm.create_session()
        doc = _make_doc("Orphaned")
        self.sm.bind_document(sid_a, doc)
        self.sm.mark_orphaned(sid_a)
        mock_app.activeDocument = doc

        result = self.sm.claim_document(sid_b)
        self.assertTrue(result.get("success"))


class TestThrottleGate(unittest.TestCase):

    def setUp(self):
        SessionManager.reset()
        self.sm = SessionManager.instance()

    def test_throttle_no_delay_on_first_call(self):
        import time
        start = time.time()
        self.sm.throttle_gate()
        elapsed = time.time() - start
        self.assertLess(elapsed, 0.1)

    def test_record_execution_end_updates_timestamp(self):
        self.sm._last_execution = 0.0
        self.sm.record_execution_end()
        self.assertGreater(self.sm._last_execution, 0.0)


ExecutionQueue = mod.ExecutionQueue


class TestExecutionQueue(unittest.TestCase):

    def setUp(self):
        SessionManager.reset()
        self.sm = SessionManager.instance()

    def test_queue_exists(self):
        self.assertIsInstance(self.sm._execution_queue, ExecutionQueue)

    def test_immediate_enter_returns_zero_wait(self):
        q = self.sm._execution_queue
        meta = q.enter("test_tool", "abc12345")
        try:
            self.assertEqual(meta["queue_depth_on_entry"], 0)
            self.assertEqual(meta["wait_time"], 0.0)
        finally:
            q.leave()

    def test_queue_serializes_execution(self):
        """Two threads entering the queue don't overlap."""
        import threading
        import time

        q = self.sm._execution_queue
        order = []

        def worker(name, hold_time):
            q.enter(name, None)
            try:
                order.append(f"{name}_start")
                time.sleep(hold_time)
                order.append(f"{name}_end")
            finally:
                q.leave()

        t1 = threading.Thread(target=worker, args=("A", 0.1))
        t2 = threading.Thread(target=worker, args=("B", 0.05))
        t1.start()
        time.sleep(0.01)  # let A enter first
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(order, ["A_start", "A_end", "B_start", "B_end"])

    def test_queue_reports_depth_and_wait(self):
        """Second entrant sees depth=1 and positive wait_time."""
        import threading
        import time

        q = self.sm._execution_queue
        meta_b = {}

        def worker_a():
            q.enter("tool_a", None)
            time.sleep(0.15)
            q.leave()

        def worker_b():
            time.sleep(0.02)  # ensure A enters first
            m = q.enter("tool_b", None)
            meta_b.update(m)
            q.leave()

        ta = threading.Thread(target=worker_a)
        tb = threading.Thread(target=worker_b)
        ta.start()
        tb.start()
        ta.join()
        tb.join()

        self.assertEqual(meta_b["queue_depth_on_entry"], 1)
        self.assertGreater(meta_b["wait_time"], 0.05)

    def test_mark_callback_started(self):
        q = self.sm._execution_queue
        q.enter("tool_x", "sess1234")
        try:
            self.assertFalse(q.get_status()["callback_started"])
            q.mark_callback_started()
            self.assertTrue(q.get_status()["callback_started"])
        finally:
            q.leave()

    def test_check_health_ok_after_callback_started(self):
        import time
        q = self.sm._execution_queue
        q.enter("tool_x", None)
        try:
            q.mark_callback_started()
            self.assertIsNone(q.check_health(time.time() - 999))
        finally:
            q.leave()

    def test_check_health_error_when_stuck(self):
        import time
        q = self.sm._execution_queue
        q.enter("tool_x", None)
        try:
            posted_at = time.time() - (q.CALLBACK_START_TIMEOUT + 5)
            err = q.check_health(posted_at, tool_name="tool_x")
            self.assertIsNotNone(err)
            self.assertIn("frozen or crashed", err)
            self.assertIn("restarted", err)
        finally:
            q.leave()

    def test_check_health_execute_script_prompts_review(self):
        import time
        q = self.sm._execution_queue
        q.enter("execute_script", None)
        try:
            posted_at = time.time() - (q.CALLBACK_START_TIMEOUT + 5)
            err = q.check_health(posted_at, tool_name="execute_script")
            self.assertIn("review the script", err.lower())
            self.assertIn("Infinite loops", err)
            self.assertIn("Prepare a corrected script", err)
        finally:
            q.leave()

    def test_get_status_shows_waiters(self):
        import threading
        import time

        q = self.sm._execution_queue
        q.enter("active_tool", "sess_a")
        q.mark_callback_started()

        ready = threading.Event()
        done = threading.Event()

        def waiter():
            ready.set()
            q.enter("waiting_tool", "sess_b")
            q.leave()
            done.set()

        t = threading.Thread(target=waiter)
        t.start()
        ready.wait()
        time.sleep(0.05)  # let waiter block on enter()

        status = q.get_status()
        self.assertEqual(status["active_tool"], "active_tool")
        self.assertEqual(status["queue_depth"], 1)
        self.assertEqual(status["waiting"][0]["tool"], "waiting_tool")

        q.leave()  # release the waiter
        done.wait(timeout=2)
        t.join()

    def test_queue_survives_reset(self):
        old_q = self.sm._execution_queue
        SessionManager.reset()
        new_sm = SessionManager.instance()
        self.assertIsInstance(new_sm._execution_queue, ExecutionQueue)
        self.assertIsNot(new_sm._execution_queue, old_q)


class TestReinitializeResumesSession(unittest.TestCase):
    """Verify that re-sending initialize with an existing session ID
    resumes the session instead of creating a new one."""

    def setUp(self):
        SessionManager.reset()
        self.sm = SessionManager.instance()
        self.sm._subscribe_document_events = lambda: None

    def test_reinitialize_preserves_document_binding(self):
        sid = self.sm.create_session()
        doc = _make_doc("MyProject")
        self.sm.bind_document(sid, doc)

        session = self.sm.get_session(sid)
        self.assertEqual(session.document_name, "MyProject")
        doc_key = session.doc_key

        # Simulate reconnect: get_session with existing ID should find it
        resumed = self.sm.get_session(sid)
        self.assertIsNotNone(resumed)
        self.assertEqual(resumed.document_name, "MyProject")
        self.assertEqual(resumed.doc_key, doc_key)

    def test_reinitialize_reactivates_orphaned_session(self):
        sid = self.sm.create_session()
        doc = _make_doc("MyProject")
        self.sm.bind_document(sid, doc)
        self.sm.mark_orphaned(sid)

        session = self.sm.get_session(sid)
        self.assertEqual(session.status, "orphaned")

        # After setting status back to active (as the mcp_server fix does)
        session.status = "active"
        self.assertEqual(session.status, "active")
        self.assertEqual(session.document_name, "MyProject")

    def test_no_duplicate_session_on_reinitialize(self):
        sid = self.sm.create_session()
        initial_count = len(self.sm.list_sessions())

        # get_session with existing ID should NOT create a new session
        self.sm.get_session(sid)
        self.assertEqual(len(self.sm.list_sessions()), initial_count)


class TestDocGone(unittest.TestCase):

    def setUp(self):
        SessionManager.reset()
        self.sm = SessionManager.instance()
        self.sm._subscribe_document_events = lambda: None

    def test_mark_doc_gone(self):
        sid = self.sm.create_session()
        doc = _make_doc("Closing")
        self.sm.bind_document(sid, doc)
        session = self.sm.get_session(sid)
        self.sm._mark_doc_gone(session)
        self.assertEqual(session.status, "doc_gone")
        self.assertIsNone(session._doc_ref)
        self.assertIsNone(session.document_name)


if __name__ == "__main__":
    unittest.main()
