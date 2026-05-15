"""
Tests for SessionManager — multi-agent document isolation.

Runs outside Fusion 360 by mocking adsk and dependent modules.
"""

import importlib.util
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, PropertyMock


# ── Mock adsk before importing SessionManager ──

def _setup_mocks():
    adsk = types.ModuleType("adsk")
    adsk.core = types.ModuleType("adsk.core")
    mock_app = MagicMock()
    mock_app.documents = MagicMock()
    mock_app.documents.count = 0
    adsk.core.Application = MagicMock()
    adsk.core.Application.get.return_value = mock_app
    adsk.core.DocumentTypes = MagicMock()
    adsk.core.DocumentEventHandler = type("DocumentEventHandler", (), {
        "__init__": lambda self: None,
        "notify": lambda self, args: None,
    })
    adsk.core.DocumentEventArgs = MagicMock()

    adsk.fusion = types.ModuleType("adsk.fusion")
    adsk.fusion.Design = MagicMock()
    adsk.fusion.DesignTypes = MagicMock()

    sys.modules["adsk"] = adsk
    sys.modules["adsk.core"] = adsk.core
    sys.modules["adsk.fusion"] = adsk.fusion

    # Mock server package
    server_pkg = types.ModuleType("server")
    server_pkg.__path__ = []
    sys.modules["server"] = server_pkg

    # Mock ActionLog
    action_log_mod = types.ModuleType("server.action_log")

    class MockActionLog:
        _entries = []
        _baseline = None
        _last_timeline_count = None
        _last_param_hash = None
        _last_read_cursor = None
        _log_file = None

        @classmethod
        def get_latest_cursor(cls):
            return cls._entries[-1]["id"] if cls._entries else None

    action_log_mod.ActionLog = MockActionLog
    sys.modules["server.action_log"] = action_log_mod

    # Mock DocumentTracker
    doc_tracker_mod = types.ModuleType("server.document_tracker")

    class MockDocumentTracker:
        _script_source = None
        _script_path = None
        _script_hash = None
        _sync_cursor = None
        _reference_model_params = None
        _doc_ref = None
        _restored = False

        @classmethod
        def _clear_memory(cls):
            cls._script_source = None
            cls._script_path = None
            cls._script_hash = None
            cls._sync_cursor = None
            cls._reference_model_params = None
            cls._doc_ref = None
            cls._restored = False

    doc_tracker_mod.DocumentTracker = MockDocumentTracker
    sys.modules["server.document_tracker"] = doc_tracker_mod

    return mock_app, MockActionLog, MockDocumentTracker


mock_app, MockActionLog, MockDocTracker = _setup_mocks()

# Import SessionManager
spec = importlib.util.spec_from_file_location(
    "server.session_manager",
    os.path.join(os.path.dirname(__file__), "..", "addin", "server", "session_manager.py"),
)
mod = importlib.util.module_from_spec(spec)
sys.modules["server.session_manager"] = mod
spec.loader.exec_module(mod)

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

    # Track attributes set on this doc
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
    adsk_fusion = sys.modules["adsk.fusion"]
    adsk_fusion.Design.cast.side_effect = lambda x: x
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

    def test_unknown_session_returns_error(self):
        result = self.sm.activate_document("nonexistent_id")
        self.assertIsInstance(result, dict)
        self.assertTrue(result["isError"])
        self.assertIn("Unknown session", result["message"])

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


class TestDocumentKeyedProvenance(unittest.TestCase):

    def setUp(self):
        SessionManager.reset()
        self.sm = SessionManager.instance()
        self.sm._subscribe_document_events = lambda: None
        MockDocTracker._clear_memory()
        MockActionLog._entries = []
        MockActionLog._baseline = None

    def test_save_and_load_provenance(self):
        sid = self.sm.create_session()
        doc = _make_doc("Doc1")
        self.sm.bind_document(sid, doc)
        doc_key = self.sm.get_session(sid).doc_key

        # Simulate tool setting tracker state
        MockDocTracker._script_hash = "hash_A"
        MockDocTracker._script_source = "script_A"
        MockActionLog._entries = [{"id": "e1"}]

        self.sm.save_provenance(doc_key)

        # Clear globals
        MockDocTracker._clear_memory()
        MockActionLog._entries = []

        # Load should restore
        self.sm._load_provenance(doc_key)
        self.assertEqual(MockDocTracker._script_hash, "hash_A")
        self.assertEqual(MockDocTracker._script_source, "script_A")
        self.assertEqual(MockActionLog._entries, [{"id": "e1"}])

    def test_load_unknown_key_clears_globals(self):
        MockDocTracker._script_hash = "stale"
        MockActionLog._entries = [{"id": "stale"}]

        self.sm._load_provenance("nonexistent_key")

        self.assertIsNone(MockDocTracker._script_hash)
        self.assertEqual(MockActionLog._entries, [])

    def test_provenance_follows_document_on_transfer(self):
        """When a document is transferred, its provenance follows it."""
        sid_a = self.sm.create_session()
        sid_b = self.sm.create_session()
        doc = _make_doc("SharedDoc")

        # A builds on doc
        self.sm.bind_document(sid_a, doc)
        doc_key = self.sm.get_session(sid_a).doc_key

        MockDocTracker._script_hash = "hash_from_A"
        self.sm.save_provenance(doc_key)

        # Transfer to B (simulating claim_document transfer)
        self.sm.unbind_document(sid_a)
        self.sm.bind_document(sid_b, doc)
        new_key = self.sm.get_session(sid_b).doc_key

        # docKey should be the same — provenance follows
        self.assertEqual(new_key, doc_key)

        # Load provenance for B's doc — should get A's state
        MockDocTracker._clear_memory()
        self.sm._load_provenance(new_key)
        self.assertEqual(MockDocTracker._script_hash, "hash_from_A")

    def test_two_docs_independent_provenance(self):
        sid_a = self.sm.create_session()
        sid_b = self.sm.create_session()
        doc_a = _make_doc("DocA")
        doc_b = _make_doc("DocB")

        self.sm.bind_document(sid_a, doc_a)
        self.sm.bind_document(sid_b, doc_b)
        key_a = self.sm.get_session(sid_a).doc_key
        key_b = self.sm.get_session(sid_b).doc_key

        # Save A's provenance
        MockDocTracker._script_hash = "hash_A"
        self.sm.save_provenance(key_a)

        # Save B's provenance
        MockDocTracker._script_hash = "hash_B"
        self.sm.save_provenance(key_b)

        # Load A — should get A's hash
        self.sm._load_provenance(key_a)
        self.assertEqual(MockDocTracker._script_hash, "hash_A")

        # Load B — should get B's hash
        self.sm._load_provenance(key_b)
        self.assertEqual(MockDocTracker._script_hash, "hash_B")

    def test_bind_does_not_clear_provenance(self):
        """bind_document should NOT wipe provenance for the document."""
        sid = self.sm.create_session()
        doc = _make_doc("Doc1")
        self.sm.bind_document(sid, doc)
        doc_key = self.sm.get_session(sid).doc_key

        MockDocTracker._script_hash = "important_hash"
        self.sm.save_provenance(doc_key)

        # Rebind to a new session — provenance should survive
        sid2 = self.sm.create_session()
        self.sm.bind_document(sid2, doc)

        self.sm._load_provenance(doc_key)
        self.assertEqual(MockDocTracker._script_hash, "important_hash")


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
