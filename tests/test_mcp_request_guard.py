"""
Tests for the MCP server request gate and script_path validation.

Both modules live inside the add-in and import ``adsk`` at module level,
which only exists inside Fusion 360. They are loaded here via importlib
with a minimal stub package tree in ``sys.modules`` — same trick as
test_document_tracker / test_session_manager, but with its own stubs
because the guard needs neither the adsk mocks nor the real
TaskManager/SessionManager.

Guards under test:
  - C1: Origin / Host / Content-Type gating of the HTTP endpoint
  - M5: containment of the caller-supplied script_path
"""

import http.client
import importlib.util
import os
import stat
import sys
import tempfile
import types
import unittest
from email import message_from_string
from unittest.mock import MagicMock

_ADDIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "addin")
_ADDIN = os.path.realpath(_ADDIN)
_REPO_ROOT = os.path.dirname(_ADDIN)


def _install_stubs():
    """Stub out everything the two add-in modules import at load time.

    Returns the sys.modules keys we invented, so they can be withdrawn
    again once the modules are loaded — leaving a fake
    ``server.session_manager`` behind would shadow the real one for
    test_session_manager, which collects after this file alphabetically.
    """
    created = []
    if "adsk" not in sys.modules:
        adsk = types.ModuleType("adsk")
        core = types.ModuleType("adsk.core")
        core.Application = MagicMock()
        core.Application.get.return_value = MagicMock()
        adsk.core = core
        sys.modules["adsk"] = adsk
        sys.modules["adsk.core"] = core

    # Applies whether we made the mock or tests.fixtures.mock_adsk did:
    # execute_script joins this into a path at import time, so it has to
    # be a real string, not a MagicMock.
    sys.modules["adsk.core"].Application.get().applicationFolders \
        .defaultPathForScriptsAndAddIns = "/nonexistent/fusion"

    for pkg, attrs in (
        ("primitives", ()),
        ("primitives.tool", ("Tool",)),
        ("primitives.resource", ("Resource",)),
        ("primitives.item", ("Item",)),
        ("primitives.registry", ("register",)),
        ("server", ()),
        ("server.task_manager", ("TaskManager",)),
        ("server.session_manager", ("SessionManager",)),
    ):
        mod = sys.modules.get(pkg)
        if mod is None:
            mod = types.ModuleType(pkg)
            mod.__path__ = []
            sys.modules[pkg] = mod
            created.append(pkg)
        for attr in attrs:
            if not hasattr(mod, attr):
                setattr(mod, attr, MagicMock())

    # The real server package directory, so `from .task_manager import ...`
    # inside mcp_server resolves to our stub rather than exploding.
    sys.modules["server"].__path__ = [os.path.join(_ADDIN, "server")]
    return created


def _remove_stubs(created):
    """Withdraw the invented modules; keep `adsk` (shared convention)."""
    for name in created:
        if name.startswith("adsk") or name == "server":
            continue
        sys.modules.pop(name, None)
    if "server" in sys.modules:
        sys.modules["server"].__path__ = []


def _load(module_name, rel_path):
    if module_name in sys.modules and hasattr(sys.modules[module_name], "__file__"):
        existing = sys.modules[module_name]
        if getattr(existing, "__file__", None):
            return existing
    spec = importlib.util.spec_from_file_location(
        module_name, os.path.join(_ADDIN, rel_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


_created = _install_stubs()
if _ADDIN not in sys.path:
    sys.path.insert(0, _ADDIN)
mcp_server = _load("server.mcp_server", "server/mcp_server.py")
execute_script = _load("tools.execute_script", "tools/execute_script.py")
_remove_stubs(_created)

check_request_allowed = mcp_server.check_request_allowed
loopback_hosts = mcp_server.loopback_hosts
read_shared_secret = mcp_server.read_shared_secret
validate_script_path = execute_script.validate_script_path

HOSTS = loopback_hosts(9100)


def _headers(**kwargs):
    """Build the same case-insensitive header object http.server hands us."""
    raw = "".join(f"{k.replace('_', '-')}: {v}\r\n" for k, v in kwargs.items())
    return message_from_string(raw, _class=http.client.HTTPMessage)


class TestRequestGate(unittest.TestCase):
    """C1 — the endpoint must be unreachable from a web page."""

    def _check(self, command="POST", **headers):
        return check_request_allowed(
            _headers(**headers), command, allowed_hosts=HOSTS)

    # ── the happy paths real clients use ──

    def test_plain_json_post_is_allowed(self):
        """mcp-remote / Claude Code HTTP transport / curl -H json."""
        allowed, status, reason = self._check(
            Host="localhost:9100", Content_Type="application/json")
        self.assertTrue(allowed, reason)
        self.assertIsNone(status)

    def test_content_type_parameters_are_ignored(self):
        """Prefix match — charset must not break a conforming client."""
        allowed, _, reason = self._check(
            Host="127.0.0.1:9100",
            Content_Type="application/json; charset=utf-8")
        self.assertTrue(allowed, reason)

    def test_documented_health_curl_is_allowed(self):
        """`curl http://localhost:9100/health` sends no Content-Type."""
        allowed, _, reason = self._check("GET", Host="localhost:9100")
        self.assertTrue(allowed, reason)

    # ── the browser vector ──

    def test_origin_header_is_rejected(self):
        """Only browsers send Origin; an MCP client never does."""
        allowed, status, _ = self._check(
            Host="localhost:9100",
            Content_Type="application/json",
            Origin="https://evil.example")
        self.assertFalse(allowed)
        self.assertEqual(status, 403)

    def test_same_origin_looking_origin_is_still_rejected(self):
        """A spoofable Origin value must not buy access either."""
        allowed, status, _ = self._check(
            Host="localhost:9100",
            Content_Type="application/json",
            Origin="http://localhost:9100")
        self.assertFalse(allowed)
        self.assertEqual(status, 403)

    def test_text_plain_post_is_rejected(self):
        """text/plain is what makes a cross-origin POST preflight-free."""
        allowed, status, _ = self._check(
            Host="localhost:9100", Content_Type="text/plain;charset=UTF-8")
        self.assertFalse(allowed)
        self.assertEqual(status, 415)

    def test_missing_content_type_post_is_rejected(self):
        allowed, status, _ = self._check(Host="localhost:9100")
        self.assertFalse(allowed)
        self.assertEqual(status, 415)

    def test_form_urlencoded_post_is_rejected(self):
        allowed, status, _ = self._check(
            Host="localhost:9100",
            Content_Type="application/x-www-form-urlencoded")
        self.assertFalse(allowed)
        self.assertEqual(status, 415)

    # ── DNS rebinding ──

    def test_rebound_host_is_rejected(self):
        """attacker.example re-resolved to 127.0.0.1 still says so in Host."""
        allowed, status, _ = self._check(
            Host="attacker.example:9100", Content_Type="application/json")
        self.assertFalse(allowed)
        self.assertEqual(status, 403)

    def test_missing_host_is_rejected(self):
        allowed, status, _ = self._check(Content_Type="application/json")
        self.assertFalse(allowed)
        self.assertEqual(status, 403)

    def test_get_is_gated_too(self):
        """/tools leaks the tool surface, so GET is gated as well."""
        allowed, status, _ = self._check("GET", Host="localhost:9100",
                                         Origin="https://evil.example")
        self.assertFalse(allowed)
        self.assertEqual(status, 403)

    def test_loopback_host_variants(self):
        for host in ("localhost:9100", "127.0.0.1:9100", "[::1]:9100",
                     "LOCALHOST:9100"):
            with self.subTest(host=host):
                allowed, _, reason = self._check(
                    Host=host, Content_Type="application/json")
                self.assertTrue(allowed, reason)

    def test_reason_strings_cannot_split_the_status_line(self):
        """Reasons land in the HTTP status line — no caller-controlled text."""
        for headers in (
            {"Host": "evil\r\nX-Injected: 1"},
            {"Host": "localhost:9100", "Content_Type": "text/plain"},
            {"Host": "localhost:9100", "Origin": "http://x\r\ny"},
        ):
            with self.subTest(headers=headers):
                _, _, reason = check_request_allowed(
                    _headers(**headers), "POST", allowed_hosts=HOSTS)
                self.assertNotIn("\r", reason)
                self.assertNotIn("\n", reason)
                reason.encode("ascii")  # raises if non-latin1 leaked in


class TestOptionalSharedSecret(unittest.TestCase):
    """The token is opt-in: absent file must not change behaviour."""

    def _check(self, secret, **headers):
        headers.setdefault("Host", "localhost:9100")
        headers.setdefault("Content_Type", "application/json")
        return check_request_allowed(
            _headers(**headers), "POST", allowed_hosts=HOSTS, secret=secret)

    def test_no_secret_configured_keeps_working(self):
        allowed, _, reason = self._check(None)
        self.assertTrue(allowed, reason)

    def test_secret_configured_rejects_missing_token(self):
        allowed, status, _ = self._check("s3cret")
        self.assertFalse(allowed)
        self.assertEqual(status, 401)

    def test_secret_configured_rejects_wrong_token(self):
        allowed, status, _ = self._check(
            "s3cret", X_ShopPrentice_Token="not-it")
        self.assertFalse(allowed)
        self.assertEqual(status, 401)

    def test_custom_header_token_accepted(self):
        allowed, _, reason = self._check(
            "s3cret", X_ShopPrentice_Token="s3cret")
        self.assertTrue(allowed, reason)

    def test_bearer_token_accepted(self):
        allowed, _, reason = self._check("s3cret", Authorization="Bearer s3cret")
        self.assertTrue(allowed, reason)

    def test_read_shared_secret_absent_file(self):
        self.assertIsNone(read_shared_secret(
            os.path.join(tempfile.gettempdir(), "sp-no-such-token-file")))

    def test_read_shared_secret_reads_and_strips(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "mcp_token")
            with open(path, "w") as f:
                f.write("  hunter2\n")
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
            self.assertEqual(read_shared_secret(path), "hunter2")

    def test_read_shared_secret_empty_file_is_none(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "mcp_token")
            open(path, "w").close()
            self.assertIsNone(read_shared_secret(path))


class TestScriptPathValidation(unittest.TestCase):
    """M5 — the deferred arbitrary-file-overwrite primitive."""

    def test_none_is_passthrough(self):
        path, err = validate_script_path(None)
        self.assertIsNone(path)
        self.assertIsNone(err)

    def test_repo_script_is_allowed(self):
        path, err = validate_script_path(
            os.path.join(_REPO_ROOT, "examples", "demo.py"))
        self.assertIsNone(err)
        self.assertEqual(path, os.path.join(_REPO_ROOT, "examples", "demo.py"))

    def test_non_py_suffix_is_rejected(self):
        path, err = validate_script_path(os.path.join(_REPO_ROOT, "evil.plist"))
        self.assertIsNone(path)
        self.assertIn(".py", err)

    def test_outside_root_is_rejected(self):
        for candidate in ("~/.zshrc.py",
                          "/Library/LaunchAgents/x.py",
                          os.path.join(_REPO_ROOT, "..", "elsewhere", "x.py")):
            with self.subTest(candidate=candidate):
                path, err = validate_script_path(candidate)
                self.assertIsNone(path)
                self.assertIsNotNone(err)

    def test_traversal_out_of_root_is_rejected(self):
        path, err = validate_script_path(
            os.path.join(_REPO_ROOT, "..", "..", "etc", "x.py"))
        self.assertIsNone(path)
        self.assertIsNotNone(err)

    def test_symlink_target_is_what_gets_checked(self):
        """realpath first — a .py symlink must not smuggle in a target."""
        with tempfile.TemporaryDirectory() as td:
            outside = os.path.join(os.path.realpath(td), "outside.py")
            open(outside, "w").close()
            link = os.path.join(_REPO_ROOT, "_guardtest_link.py")
            try:
                os.symlink(outside, link)
                path, err = validate_script_path(link)
                self.assertIsNone(path)
                self.assertIsNotNone(err)
            finally:
                if os.path.islink(link):
                    os.unlink(link)

    def test_env_override_adds_a_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = os.path.realpath(td)
            prev = os.environ.get(execute_script.SCRIPT_ROOTS_ENV)
            os.environ[execute_script.SCRIPT_ROOTS_ENV] = root
            try:
                path, err = validate_script_path(os.path.join(root, "model.py"))
                self.assertIsNone(err)
                self.assertEqual(path, os.path.join(root, "model.py"))
            finally:
                if prev is None:
                    os.environ.pop(execute_script.SCRIPT_ROOTS_ENV, None)
                else:
                    os.environ[execute_script.SCRIPT_ROOTS_ENV] = prev


class TestLiveEndpoint(unittest.TestCase):
    """The gate must actually be *wired* — pure-function tests can't show that.

    Binds an ephemeral loopback port and speaks real HTTP to the real
    MCPHandler, so a future refactor that drops the ``_gate()`` call from
    do_POST/do_GET (or puts back the wildcard CORS header) fails here.
    """

    @classmethod
    def setUpClass(cls):
        cls.mcp, cls.http_server, cls.thread = mcp_server.start_mcp_server(
            host="127.0.0.1", port=0)
        if not cls.http_server:
            raise unittest.SkipTest("could not bind a loopback port")
        cls.port = cls.http_server.server_address[1]
        # start_mcp_server saw port 0; teach the gate the real one.
        mcp_server._allowed_hosts = mcp_server.loopback_hosts(cls.port)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "http_server", None):
            mcp_server.stop_mcp_server(cls.http_server, cls.thread)

    def _request(self, method, path, headers=None, body=None, host=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            hdrs = dict(headers or {})
            hdrs["Host"] = host or f"localhost:{self.port}"
            conn.request(method, path, body=body, headers=hdrs)
            return conn.getresponse()
        finally:
            conn.close()

    JSON_BODY = '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

    def test_legit_json_post_succeeds(self):
        r = self._request("POST", "/", {"Content-Type": "application/json"},
                          self.JSON_BODY)
        self.assertEqual(r.status, 200)

    def test_documented_health_curl_succeeds(self):
        self.assertEqual(self._request("GET", "/health").status, 200)

    def test_browser_post_is_blocked(self):
        r = self._request("POST", "/", {
            "Content-Type": "text/plain;charset=UTF-8",
            "Origin": "https://evil.example",
        }, self.JSON_BODY)
        self.assertEqual(r.status, 403)

    def test_rebound_host_is_blocked(self):
        r = self._request("POST", "/", {"Content-Type": "application/json"},
                          self.JSON_BODY, host=f"evil.example:{self.port}")
        self.assertEqual(r.status, 403)

    def test_no_wildcard_cors_header_on_success(self):
        """A browser must not be able to read a reply that slips through."""
        r = self._request("GET", "/tools")
        self.assertEqual(r.status, 200)
        self.assertIsNone(r.getheader("Access-Control-Allow-Origin"))

    def test_optional_token_is_off_then_on(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "mcp_token")
            prev = mcp_server.TOKEN_FILE
            mcp_server.TOKEN_FILE = path
            try:
                # No file => existing configs keep working untouched.
                self.assertEqual(
                    self._request("POST", "/",
                                  {"Content-Type": "application/json"},
                                  self.JSON_BODY).status, 200)
                with open(path, "w") as f:
                    f.write("s3cret-token\n")
                os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
                self.assertEqual(
                    self._request("POST", "/",
                                  {"Content-Type": "application/json"},
                                  self.JSON_BODY).status, 401)
                self.assertEqual(
                    self._request("POST", "/", {
                        "Content-Type": "application/json",
                        "X-ShopPrentice-Token": "s3cret-token",
                    }, self.JSON_BODY).status, 200)
            finally:
                mcp_server.TOKEN_FILE = prev


if __name__ == "__main__":
    unittest.main()
