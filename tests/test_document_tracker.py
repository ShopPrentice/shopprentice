"""
Tests for DocumentTracker singleton.

Runs outside Fusion 360 by mocking the adsk module and ActionLog.
"""

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock


# ── Mock adsk before importing DocumentTracker ──

def _setup_mocks():
    """Install fake adsk and ActionLog modules so document_tracker can import."""
    # Mock adsk.core
    adsk = types.ModuleType("adsk")
    adsk.core = types.ModuleType("adsk.core")
    mock_app = MagicMock()
    adsk.core.Application = MagicMock()
    adsk.core.Application.get.return_value = mock_app
    sys.modules["adsk"] = adsk
    sys.modules["adsk.core"] = adsk.core

    # Mock ActionLog as a class with classmethods
    class MockActionLog:
        _entries = []

        @classmethod
        def get_latest_cursor(cls):
            if cls._entries:
                return cls._entries[-1]["id"]
            return None

        @classmethod
        def get_entries(cls, since=None):
            if since is None:
                return list(cls._entries)
            for i, entry in enumerate(cls._entries):
                if entry["id"] == since:
                    return list(cls._entries[i + 1:])
            return list(cls._entries)

        @classmethod
        def reset_entries(cls):
            cls._entries = []

    # Install the server package mock
    server_pkg = types.ModuleType("server")
    server_pkg.__path__ = []  # make it a package

    action_log_mod = types.ModuleType("server.action_log")
    action_log_mod.ActionLog = MockActionLog

    sys.modules["server"] = server_pkg
    sys.modules["server.action_log"] = action_log_mod

    return mock_app, MockActionLog


mock_app, MockActionLog = _setup_mocks()

# Import DocumentTracker from its file location
spec = importlib.util.spec_from_file_location(
    "server.document_tracker",
    "/Users/frankzha/projects/autofusion/addin/server/document_tracker.py"
)
mod = importlib.util.module_from_spec(spec)
sys.modules["server.document_tracker"] = mod
spec.loader.exec_module(mod)

DocumentTracker = mod.DocumentTracker


class TestDocumentTracker(unittest.TestCase):

    def setUp(self):
        DocumentTracker.reset()
        MockActionLog.reset_entries()
        # Redirect provenance file to a temp location
        self._tmp_dir = tempfile.mkdtemp()
        self._orig_dir = mod._PROVENANCE_DIR
        self._orig_file = mod._PROVENANCE_FILE
        mod._PROVENANCE_DIR = self._tmp_dir
        mod._PROVENANCE_FILE = os.path.join(self._tmp_dir, "provenance.json")

    def tearDown(self):
        # Restore original paths
        mod._PROVENANCE_DIR = self._orig_dir
        mod._PROVENANCE_FILE = self._orig_file
        # Clean up temp
        prov_file = os.path.join(self._tmp_dir, "provenance.json")
        if os.path.exists(prov_file):
            os.unlink(prov_file)
        os.rmdir(self._tmp_dir)

    def _make_doc(self, name="TestDoc"):
        doc = MagicMock()
        doc.isValid = True
        doc.name = name
        return doc

    # ── 1. Fresh session ──

    def test_fresh_session_not_tracked(self):
        status = DocumentTracker.get_status()
        self.assertFalse(status["tracked"])
        self.assertEqual(status["reason"], "No script has been executed in this session")

    def test_get_script_returns_none_initially(self):
        self.assertIsNone(DocumentTracker.get_script())

    # ── 2. After script execution ──

    def test_on_script_executed_tracks_script(self):
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc()
        mock_app.activeDocument = doc

        DocumentTracker.on_script_executed(script, doc)

        self.assertEqual(DocumentTracker.get_script(), script)
        self.assertEqual(
            DocumentTracker._script_hash,
            hashlib.sha256(script.encode()).hexdigest()
        )
        self.assertIs(DocumentTracker._doc_ref, doc)

    def test_tracked_status_after_execution(self):
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc()
        mock_app.activeDocument = doc

        DocumentTracker.on_script_executed(script, doc)
        status = DocumentTracker.get_status()

        self.assertTrue(status["tracked"])
        self.assertEqual(status["pendingChanges"], 0)
        self.assertTrue(status["canUpdate"])
        self.assertEqual(
            status["scriptHash"],
            hashlib.sha256(script.encode()).hexdigest()
        )

    # ── 3. Pending UI changes ──

    def test_pending_changes_counted(self):
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc()
        mock_app.activeDocument = doc

        DocumentTracker.on_script_executed(script, doc)

        # Simulate 2 pending UI changes recorded after the cursor
        MockActionLog._entries = [
            {"id": "e1", "commandId": "Extrude"},
            {"id": "e2", "commandId": "Chamfer"},
        ]

        status = DocumentTracker.get_status()
        self.assertTrue(status["tracked"])
        self.assertEqual(status["pendingChanges"], 2)

    # ── 4. Document changed ──

    def test_document_changed_not_tracked(self):
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc("DocA")
        mock_app.activeDocument = doc

        DocumentTracker.on_script_executed(script, doc)

        # Switch to different document (unknown name)
        other_doc = self._make_doc("UnknownDoc")
        mock_app.activeDocument = other_doc

        status = DocumentTracker.get_status()
        # Should try restore, but no entry for "UnknownDoc" on disk
        self.assertFalse(status["tracked"])

    def test_document_invalidated_restores_if_same_name(self):
        """If doc ref is invalid but active doc has same name, restore from disk."""
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc("MyDoc")
        mock_app.activeDocument = doc

        DocumentTracker.on_script_executed(script, doc)

        # Simulate reopen: old ref invalid, new doc object with same name
        doc.isValid = False
        new_doc = self._make_doc("MyDoc")
        mock_app.activeDocument = new_doc

        status = DocumentTracker.get_status()
        # Should restore from disk since same document name exists
        self.assertTrue(status["tracked"])
        self.assertEqual(DocumentTracker.get_script(), script)

    # ── 5. Sync complete ──

    def test_on_sync_complete_updates_script_and_cursor(self):
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc()
        mock_app.activeDocument = doc

        DocumentTracker.on_script_executed(script, doc)

        patched = 'def run(ctx):\n    print("patched")'
        DocumentTracker.on_sync_complete(patched, "cursor-2")

        self.assertEqual(DocumentTracker.get_script(), patched)
        self.assertEqual(
            DocumentTracker._script_hash,
            hashlib.sha256(patched.encode()).hexdigest()
        )
        self.assertEqual(DocumentTracker._sync_cursor, "cursor-2")

    # ── 6. Advance cursor ──

    def test_advance_cursor(self):
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc()
        mock_app.activeDocument = doc

        DocumentTracker.on_script_executed(script, doc)

        DocumentTracker.advance_cursor("cursor-3")
        self.assertEqual(DocumentTracker._sync_cursor, "cursor-3")

    def test_advance_cursor_clears_pending(self):
        """After advance_cursor, pending changes from before the cursor are gone."""
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc()
        mock_app.activeDocument = doc

        DocumentTracker.on_script_executed(script, doc)

        # Simulate entries, then advance past them
        MockActionLog._entries = [
            {"id": "e1", "commandId": "Extrude"},
            {"id": "e2", "commandId": "Chamfer"},
        ]
        DocumentTracker.advance_cursor("e2")

        status = DocumentTracker.get_status()
        self.assertEqual(status["pendingChanges"], 0)

    # ── 7. Reset ──

    def test_reset_clears_all_state(self):
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc()
        mock_app.activeDocument = doc

        DocumentTracker.on_script_executed(script, doc)
        DocumentTracker.reset()

        self.assertIsNone(DocumentTracker._script_source)
        self.assertIsNone(DocumentTracker._script_hash)
        self.assertIsNone(DocumentTracker._sync_cursor)
        self.assertIsNone(DocumentTracker._doc_ref)

    # ── 8. Idempotency ──

    def test_get_status_is_idempotent(self):
        """get_status doesn't mutate observable state."""
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc()
        mock_app.activeDocument = doc

        DocumentTracker.on_script_executed(script, doc)

        s1 = DocumentTracker.get_status()
        s2 = DocumentTracker.get_status()
        self.assertEqual(s1, s2)

    # ── 9. Script re-execution overwrites previous tracking ──

    def test_re_execution_overwrites(self):
        doc = self._make_doc()
        mock_app.activeDocument = doc

        script1 = 'def run(ctx):\n    pass'
        DocumentTracker.on_script_executed(script1, doc)

        script2 = 'def run(ctx):\n    print("v2")'
        DocumentTracker.on_script_executed(script2, doc)

        self.assertEqual(DocumentTracker.get_script(), script2)
        self.assertEqual(
            DocumentTracker._script_hash,
            hashlib.sha256(script2.encode()).hexdigest()
        )

    # ── 10. Persistence — save and restore ──

    def test_save_creates_provenance_file(self):
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc("MyBookshelf")
        mock_app.activeDocument = doc

        DocumentTracker.on_script_executed(script, doc)

        # File should exist
        self.assertTrue(os.path.exists(mod._PROVENANCE_FILE))

        with open(mod._PROVENANCE_FILE, "r") as f:
            data = json.load(f)
        self.assertIn("MyBookshelf", data)
        self.assertEqual(data["MyBookshelf"]["scriptSource"], script)
        self.assertEqual(
            data["MyBookshelf"]["scriptHash"],
            hashlib.sha256(script.encode()).hexdigest()
        )

    def test_restore_after_memory_clear(self):
        """Simulates add-in restart: memory cleared, disk has provenance."""
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc("MyBookshelf")
        mock_app.activeDocument = doc

        DocumentTracker.on_script_executed(script, doc)

        # Simulate restart — clear memory
        DocumentTracker._clear_memory()
        self.assertIsNone(DocumentTracker._script_source)

        # New doc object (same name, different identity — restart scenario)
        new_doc = self._make_doc("MyBookshelf")
        mock_app.activeDocument = new_doc

        # get_status should restore from disk
        status = DocumentTracker.get_status()
        self.assertTrue(status["tracked"])
        self.assertEqual(DocumentTracker.get_script(), script)
        self.assertIs(DocumentTracker._doc_ref, new_doc)
        # Cursor is session-only, not restored
        self.assertIsNone(DocumentTracker._sync_cursor)

    def test_restore_unknown_doc_fails(self):
        """No provenance on disk for an unknown document."""
        doc = self._make_doc("NeverSeenBefore")
        mock_app.activeDocument = doc

        status = DocumentTracker.get_status()
        self.assertFalse(status["tracked"])

    def test_sync_complete_persists(self):
        """on_sync_complete also saves to disk."""
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc("MyTable")
        mock_app.activeDocument = doc

        DocumentTracker.on_script_executed(script, doc)

        patched = 'def run(ctx):\n    print("patched")'
        DocumentTracker.on_sync_complete(patched, "cursor-2")

        with open(mod._PROVENANCE_FILE, "r") as f:
            data = json.load(f)
        self.assertEqual(data["MyTable"]["scriptSource"], patched)

    def test_multiple_documents_coexist(self):
        """Provenance for different documents stored side by side."""
        script_a = 'def run(ctx):\n    # bookshelf'
        doc_a = self._make_doc("Bookshelf")
        mock_app.activeDocument = doc_a
        DocumentTracker.on_script_executed(script_a, doc_a)

        script_b = 'def run(ctx):\n    # table'
        doc_b = self._make_doc("Table")
        mock_app.activeDocument = doc_b
        DocumentTracker.on_script_executed(script_b, doc_b)

        with open(mod._PROVENANCE_FILE, "r") as f:
            data = json.load(f)
        self.assertEqual(data["Bookshelf"]["scriptSource"], script_a)
        self.assertEqual(data["Table"]["scriptSource"], script_b)

    def test_get_script_restores_from_disk(self):
        """get_script also triggers restore if memory is empty."""
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc("MyBox")
        mock_app.activeDocument = doc

        DocumentTracker.on_script_executed(script, doc)
        DocumentTracker._clear_memory()

        new_doc = self._make_doc("MyBox")
        mock_app.activeDocument = new_doc

        self.assertEqual(DocumentTracker.get_script(), script)

    def test_document_switch_restores_other_doc(self):
        """Switching to a doc that has provenance on disk restores it."""
        script_a = 'def run(ctx):\n    # A'
        doc_a = self._make_doc("DocA")
        mock_app.activeDocument = doc_a
        DocumentTracker.on_script_executed(script_a, doc_a)

        script_b = 'def run(ctx):\n    # B'
        doc_b = self._make_doc("DocB")
        mock_app.activeDocument = doc_b
        DocumentTracker.on_script_executed(script_b, doc_b)

        # Switch back to DocA (new object, same name)
        new_doc_a = self._make_doc("DocA")
        mock_app.activeDocument = new_doc_a

        status = DocumentTracker.get_status()
        self.assertTrue(status["tracked"])
        self.assertEqual(DocumentTracker.get_script(), script_a)


    # ── 11. needsSync flag ──

    def test_no_needs_sync_after_execution(self):
        """Fresh execution has no needsSync flag."""
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc()
        mock_app.activeDocument = doc

        DocumentTracker.on_script_executed(script, doc)

        status = DocumentTracker.get_status()
        self.assertNotIn("needsSync", status)

    def test_needs_sync_after_restore(self):
        """Restored from disk → needsSync=true."""
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc("MyShelf")
        mock_app.activeDocument = doc

        DocumentTracker.on_script_executed(script, doc)
        DocumentTracker._clear_memory()

        new_doc = self._make_doc("MyShelf")
        mock_app.activeDocument = new_doc

        status = DocumentTracker.get_status()
        self.assertTrue(status["tracked"])
        self.assertTrue(status["needsSync"])

    def test_needs_sync_cleared_by_sync_complete(self):
        """on_sync_complete clears needsSync."""
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc("MyShelf")
        mock_app.activeDocument = doc

        DocumentTracker.on_script_executed(script, doc)
        DocumentTracker._clear_memory()

        new_doc = self._make_doc("MyShelf")
        mock_app.activeDocument = new_doc

        # Trigger restore
        status = DocumentTracker.get_status()
        self.assertTrue(status["needsSync"])

        # Sync clears the flag
        DocumentTracker.on_sync_complete(script, "cursor-x")
        status = DocumentTracker.get_status()
        self.assertNotIn("needsSync", status)

    def test_needs_sync_cleared_by_execution(self):
        """on_script_executed also clears needsSync."""
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc("MyShelf")
        mock_app.activeDocument = doc

        DocumentTracker.on_script_executed(script, doc)
        DocumentTracker._clear_memory()

        new_doc = self._make_doc("MyShelf")
        mock_app.activeDocument = new_doc

        # Trigger restore
        DocumentTracker.get_status()

        # Re-execution clears the flag
        DocumentTracker.on_script_executed(script, new_doc)
        status = DocumentTracker.get_status()
        self.assertNotIn("needsSync", status)


if __name__ == "__main__":
    unittest.main()
