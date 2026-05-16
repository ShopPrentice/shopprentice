"""
Tests for DocumentTracker singleton.

Runs outside Fusion 360 using shared mock fixtures.
"""

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

# Shared mocks — compatible with test_session_manager
from tests.fixtures.mock_adsk import setup as _setup_mocks
_m = _setup_mocks()
mock_app = _m["app"]
MockActionLog = _m["ActionLog"]

# Import DocumentTracker from its file location
if "server.document_tracker" not in sys.modules or not hasattr(sys.modules["server.document_tracker"], "_PROVENANCE_FILE"):
    spec = importlib.util.spec_from_file_location(
        "server.document_tracker",
        os.path.join(os.path.dirname(__file__), "..", "addin", "server", "document_tracker.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["server.document_tracker"] = mod
    spec.loader.exec_module(mod)
else:
    mod = sys.modules["server.document_tracker"]

DocumentTracker = mod.DocumentTracker


class TestDocumentTracker(unittest.TestCase):

    def setUp(self):
        DocumentTracker.reset()
        MockActionLog.reset_entries()
        # Design.cast returns None by default (tests override per-test)
        sys.modules["adsk.fusion"].Design.cast.side_effect = None
        sys.modules["adsk.fusion"].Design.cast.return_value = None
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

    def test_on_sync_complete_updates_script(self):
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc()
        mock_app.activeDocument = doc

        DocumentTracker.on_script_executed(script, doc)

        patched = 'def run(ctx):\n    print("patched")'
        DocumentTracker.on_sync_complete(patched)

        self.assertEqual(DocumentTracker.get_script(), patched)
        self.assertEqual(
            DocumentTracker._script_hash,
            hashlib.sha256(patched.encode()).hexdigest()
        )

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
        DocumentTracker.on_sync_complete(patched)

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
        DocumentTracker.on_sync_complete(script)
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


    # ── 12. Different wrapper, same document ──

    def test_different_wrapper_same_doc_stays_tracked(self):
        """Fusion returns different Python objects for the same document.
        get_status must compare by name, not identity."""
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc("MyBox")
        mock_app.activeDocument = doc

        DocumentTracker.on_script_executed(script, doc)

        # Simulate Fusion returning a different wrapper for the same doc
        wrapper2 = self._make_doc("MyBox")
        mock_app.activeDocument = wrapper2
        self.assertIsNot(wrapper2, doc)  # different Python object

        status = DocumentTracker.get_status()
        self.assertTrue(status["tracked"])
        self.assertNotIn("needsSync", status)  # NOT restored from disk


    # ── 13. Reference model parameters ──

    def test_reference_captured_on_script_executed(self):
        """on_script_executed captures reference model params."""
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc()
        mock_app.activeDocument = doc

        fake_params = {"Extrude1.d0": "10 mm", "Extrude1.d1": "20 mm"}
        with unittest.mock.patch.object(
            DocumentTracker, '_capture_model_params', return_value=fake_params
        ):
            DocumentTracker.on_script_executed(script, doc)

        self.assertEqual(DocumentTracker._reference_model_params, fake_params)

    def test_reference_updated_on_sync_complete(self):
        """on_sync_complete recaptures reference model params."""
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc()
        mock_app.activeDocument = doc

        with unittest.mock.patch.object(
            DocumentTracker, '_capture_model_params', return_value={"a.b": "1 mm"}
        ):
            DocumentTracker.on_script_executed(script, doc)

        new_params = {"a.b": "2 mm", "c.d": "5 mm"}
        patched = 'def run(ctx):\n    print("v2")'
        with unittest.mock.patch.object(
            DocumentTracker, '_capture_model_params', return_value=new_params
        ):
            DocumentTracker.on_sync_complete(patched)

        self.assertEqual(DocumentTracker._reference_model_params, new_params)

    def test_update_reference_recaptures(self):
        """update_reference() recaptures current model params."""
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc()
        mock_app.activeDocument = doc

        with unittest.mock.patch.object(
            DocumentTracker, '_capture_model_params', return_value={"x.y": "1 in"}
        ):
            DocumentTracker.on_script_executed(script, doc)

        self.assertEqual(DocumentTracker._reference_model_params, {"x.y": "1 in"})

        with unittest.mock.patch.object(
            DocumentTracker, '_capture_model_params', return_value={"x.y": "2 in"}
        ):
            DocumentTracker.update_reference()

        self.assertEqual(DocumentTracker._reference_model_params, {"x.y": "2 in"})

    def test_reference_persists_to_disk_and_restores(self):
        """Reference model params are saved to provenance.json and restored."""
        script = 'def run(ctx):\n    pass'
        doc = self._make_doc("RefDoc")
        mock_app.activeDocument = doc

        fake_params = {"Ext1.d0": "5 mm", "Fillet1.radius": "2 mm"}
        with unittest.mock.patch.object(
            DocumentTracker, '_capture_model_params', return_value=fake_params
        ):
            DocumentTracker.on_script_executed(script, doc)

        # Verify written to disk
        with open(mod._PROVENANCE_FILE, "r") as f:
            data = json.load(f)
        self.assertEqual(data["RefDoc"]["referenceModelParams"], fake_params)

        # Clear memory, restore
        DocumentTracker._clear_memory()
        new_doc = self._make_doc("RefDoc")
        mock_app.activeDocument = new_doc

        status = DocumentTracker.get_status()
        self.assertTrue(status["tracked"])
        self.assertEqual(DocumentTracker._reference_model_params, fake_params)

    def test_old_provenance_without_reference_restores_gracefully(self):
        """Old provenance.json without referenceModelParams restores with None."""
        # Write old-format provenance manually
        old_data = {
            "OldDoc": {
                "scriptSource": 'def run(ctx):\n    pass',
                "scriptHash": hashlib.sha256(b'def run(ctx):\n    pass').hexdigest(),
            }
        }
        os.makedirs(mod._PROVENANCE_DIR, exist_ok=True)
        with open(mod._PROVENANCE_FILE, "w") as f:
            json.dump(old_data, f)

        doc = self._make_doc("OldDoc")
        mock_app.activeDocument = doc

        status = DocumentTracker.get_status()
        self.assertTrue(status["tracked"])
        self.assertIsNone(DocumentTracker._reference_model_params)

    def test_get_reference_model_params_returns_none_initially(self):
        """No reference when nothing has been executed."""
        self.assertIsNone(DocumentTracker.get_reference_model_params())

    def test_clear_memory_clears_reference(self):
        """_clear_memory resets reference model params."""
        DocumentTracker._reference_model_params = {"a.b": "1 mm"}
        DocumentTracker._clear_memory()
        self.assertIsNone(DocumentTracker._reference_model_params)


if __name__ == "__main__":
    unittest.main()
