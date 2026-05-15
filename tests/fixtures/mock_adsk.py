"""
Shared adsk + server mock setup for unit tests.

Import this module ONCE per test file before importing any addin code.
Calling setup() installs the mocks into sys.modules. The mocks are
designed to be compatible across test_session_manager and
test_document_tracker so both can run in the same pytest process.

Usage:
    from tests.fixtures.mock_adsk import setup
    mocks = setup()
    mock_app = mocks["app"]
    MockActionLog = mocks["ActionLog"]
    MockDocumentTracker = mocks["DocumentTracker"]
"""

import sys
import types
from unittest.mock import MagicMock

_installed = False
_mocks = {}


def setup():
    """Install adsk/server mocks into sys.modules. Idempotent."""
    global _installed, _mocks
    if _installed:
        return _mocks

    # ── adsk ──
    adsk = sys.modules.get("adsk")
    if adsk is None:
        adsk = types.ModuleType("adsk")
        sys.modules["adsk"] = adsk

    if not hasattr(adsk, "core") or not isinstance(adsk.core, types.ModuleType):
        adsk.core = types.ModuleType("adsk.core")
        sys.modules["adsk.core"] = adsk.core

    mock_app = MagicMock()
    mock_app.documents = MagicMock()
    mock_app.documents.count = 0
    adsk.core.Application = MagicMock()
    adsk.core.Application.get.return_value = mock_app
    adsk.core.DocumentTypes = MagicMock()
    adsk.core.DocumentEventHandler = type(
        "DocumentEventHandler", (), {
            "__init__": lambda self: None,
            "notify": lambda self, args: None,
        })
    adsk.core.DocumentEventArgs = MagicMock()
    adsk.core.Matrix3D = MagicMock()
    adsk.core.ValueInput = MagicMock()

    if not hasattr(adsk, "fusion") or not isinstance(adsk.fusion, types.ModuleType):
        adsk.fusion = types.ModuleType("adsk.fusion")
        sys.modules["adsk.fusion"] = adsk.fusion

    adsk.fusion.Design = MagicMock()
    adsk.fusion.Design.cast.side_effect = lambda x: x
    adsk.fusion.DesignTypes = MagicMock()

    # ── server package ──
    if "server" not in sys.modules:
        server_pkg = types.ModuleType("server")
        server_pkg.__path__ = []
        sys.modules["server"] = server_pkg

    # ── ActionLog ──
    class MockActionLog:
        _is_running = False
        _suppress = False
        _event_handler = None
        _entries = []
        _baseline = None
        _last_timeline_count = None
        _last_param_hash = None
        _last_read_cursor = None
        _log_dir = None
        _log_file = None

        @classmethod
        def get_latest_cursor(cls):
            return cls._entries[-1]["id"] if cls._entries else None

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
            cls._baseline = None
            cls._last_timeline_count = None
            cls._last_param_hash = None
            cls._last_read_cursor = None
            cls._log_file = None

    action_log_mod = sys.modules.get("server.action_log")
    if action_log_mod is None:
        action_log_mod = types.ModuleType("server.action_log")
        sys.modules["server.action_log"] = action_log_mod
    action_log_mod.ActionLog = MockActionLog

    # ── DocumentTracker ──
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

    doc_tracker_mod = sys.modules.get("server.document_tracker")
    if doc_tracker_mod is None:
        doc_tracker_mod = types.ModuleType("server.document_tracker")
        sys.modules["server.document_tracker"] = doc_tracker_mod
    doc_tracker_mod.DocumentTracker = MockDocumentTracker

    _mocks = {
        "app": mock_app,
        "ActionLog": MockActionLog,
        "DocumentTracker": MockDocumentTracker,
    }
    _installed = True
    return _mocks
