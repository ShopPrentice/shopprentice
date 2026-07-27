"""
MCP Server Module

Simple MCP-compatible server implementation that runs within Fusion 360's
Python environment. Implements MCP protocol over HTTP without external dependencies.

Session isolation: the server reads/writes the ``Mcp-Session-Id`` HTTP
header (MCP streamable-HTTP spec) so each connected agent gets its own
Fusion 360 document.  Clients that omit the header fall back to
single-session (legacy) behaviour.
"""

import asyncio
import hmac
import json
import os
import threading
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Any, Dict, Tuple, Optional
from primitives.tool import Tool
from primitives.resource import Resource
from primitives.item import Item
from .task_manager import TaskManager
from .session_manager import SessionManager

try:
    import adsk.core
    app = adsk.core.Application.get()
except:
    pass


# ─────────────────────────────────────────────────────────────────────
# Request gating — DO NOT "simplify" these checks away.
#
# The add-in auto-starts with Fusion (runOnStartup) and listens on a
# loopback port for as long as Fusion is open, so *any* web page the
# user happens to visit can aim a cross-origin fetch() at it.  The
# execute_script tool runs arbitrary Python as the user, which makes an
# unguarded endpoint a drive-by remote-code-execution hole.  Three
# header checks close the browser vector; each one matters on its own:
#
#   1. Origin        Browsers attach it to every cross-origin request
#                    (and to every cross-origin POST, simple or not).
#                    Real MCP clients — mcp-remote, Claude Code's HTTP
#                    transport, mcporter, curl — never send it.  So
#                    "Origin present" means "a browser sent this", and
#                    we reject it.  The MCP spec requires local HTTP
#                    servers to validate Origin for exactly this reason.
#   2. Content-Type  Requiring application/json on POST makes the
#                    request non-"simple" under CORS, so a browser must
#                    preflight with OPTIONS first.  We answer no
#                    preflight, so the request dies before its body is
#                    ever delivered.  Without this rule an attacker just
#                    uses text/plain and skips preflight entirely.
#   3. Host          Pins the request to our own loopback authority.
#                    Closes DNS rebinding: attacker.example re-resolved
#                    to 127.0.0.1 still arrives as Host: attacker.example.
#
# Responses deliberately carry no Access-Control-Allow-Origin header —
# without it a browser cannot read a reply even if a request slips past
# the checks above.
# ─────────────────────────────────────────────────────────────────────

# Optional shared secret guarding the *local-process* vector (see
# read_shared_secret).  Lives beside the add-in's other state.
TOKEN_FILE = os.path.join(os.path.expanduser("~"), ".shopprentice", "mcp_token")

# Populated by start_mcp_server() once the listening port is known.
_allowed_hosts = frozenset()


def loopback_hosts(port: int) -> frozenset:
    """``Host:`` values that legitimately name this server's own socket."""
    hosts = set()
    for name in ("localhost", "127.0.0.1", "[::1]", "::1"):
        hosts.add(name)
        hosts.add(f"{name}:{port}")
    return frozenset(hosts)


def read_shared_secret(path: Optional[str] = None) -> Optional[str]:
    """Return the optional shared secret, or ``None`` when not configured.

    The header checks above stop web pages, but any *other process* or
    local account on this machine can still talk to the port directly.
    Creating ``~/.shopprentice/mcp_token`` (mode 0600) switches on a
    required token header for every request.

    This is opt-in on purpose: making it mandatory would break every
    existing client config the moment the add-in is upgraded.  Absent or
    empty file => unchanged behaviour.

    Read per request (not cached) so creating or deleting the token file
    takes effect without restarting Fusion.
    """
    try:
        with open(path or TOKEN_FILE, "r", encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def _token_matches(headers, secret: str) -> bool:
    """Constant-time check of ``X-ShopPrentice-Token`` / bearer token."""
    presented = headers.get("X-ShopPrentice-Token")
    if not presented:
        auth = headers.get("Authorization") or ""
        if auth[:7].lower() == "bearer ":
            presented = auth[7:]
    if not presented:
        return False
    return hmac.compare_digest(presented.strip(), secret)


def check_request_allowed(
    headers,
    command: str,
    allowed_hosts=None,
    secret: Optional[str] = None,
) -> Tuple[bool, Optional[int], Optional[str]]:
    """Decide whether an inbound HTTP request may reach the tool surface.

    Returns ``(True, None, None)`` when allowed, else
    ``(False, status_code, reason)``.  Kept as a pure function of the
    request headers — no Fusion, no socket — so it can be unit-tested
    outside Fusion 360 (see ``tests/test_mcp_request_guard.py``).

    *headers* is any case-insensitive mapping with ``.get()`` (the
    ``email.message.Message`` that BaseHTTPRequestHandler hands us).
    *secret* of ``None`` means no shared secret is configured.

    Every returned reason is a fixed ASCII literal: it goes into the
    HTTP status line, so it must never carry caller-controlled text
    (that would be a response-splitting hole).
    """
    # 1. Only browsers send Origin. Legitimate MCP clients never do.
    if headers.get("Origin") is not None:
        return False, 403, "Origin header not accepted"

    # 2. Host must name our own loopback socket (anti DNS-rebinding).
    host = (headers.get("Host") or "").strip().lower()
    allowed = _allowed_hosts if allowed_hosts is None else allowed_hosts
    if host not in allowed:
        return False, 403, "Host header does not name this loopback server"

    # 3. Bodies must be JSON, which forces a CORS preflight we never
    #    answer.  GET carries no body, and the documented
    #    `curl http://localhost:9100/health` sends no Content-Type, so
    #    the rule applies to POST only.
    if command == "POST":
        ctype = (headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if ctype != "application/json":
            return False, 415, "POST requires Content-Type: application/json"

    # 4. Optional shared secret — off unless the user created the file.
    if secret and not _token_matches(headers, secret):
        return False, 401, "Missing or invalid ShopPrentice MCP token"

    return True, None, None


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTP server that handles requests in separate threads."""
    daemon_threads = True
    allow_reuse_address = True


class SimpleMCPServer:
    """Simple MCP-compatible server that can run in Fusion 360's Python environment."""

    def __init__(self, name: str = "ShopPrentice"):
        self.name = name
        self.tools: Dict[str, Item] = {}
        self.resources: Dict[str, Item] = {}
        self.server_info = {
            "name": name,
            "version": "1.0.0"
        }

    def register(self, item: Item):
        """Register an Item (Tool, Resource, or Prompt) in the server."""
        if not isinstance(item, Item):
            raise ValueError("Can only register Item instances")

        primitive = item.primitive
        item_type = item.get_type()

        if item_type == "tool":
            self.tools[primitive.name] = item
            if app:
                app.log(f"Tool registered: {primitive.name}")
        elif item_type == "resource":
            self.resources[primitive.uri] = item
            if app:
                app.log(f"Resource registered: {primitive.uri}")
        elif item_type == "prompt":
            if app:
                app.log(f"Prompt registered: {primitive.name} (not yet supported)")
        else:
            raise ValueError(f"Unknown item type: {item_type}")

    async def handle_request(
        self, request: Dict[str, Any], session_id: Optional[str] = None
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """Handle MCP protocol requests.

        Returns ``(response_dict, session_id)`` so the HTTP handler can
        set the ``Mcp-Session-Id`` response header.
        """
        try:
            method = request.get("method")
            request_id = request.get("id")
            params = request.get("params", {})

            if method == "initialize":
                sm = SessionManager.instance()
                existing = sm.get_session(session_id) if session_id else None
                if existing:
                    existing.status = "active"
                    resp = self._handle_initialize(request_id, params)
                    app.log(f"[session] reinitialize — resumed {session_id[:8]}")
                    return resp, session_id
                new_sid = sm.create_session()
                resp = self._handle_initialize(request_id, params)
                return resp, new_sid
            elif method == "tools/list":
                return self._handle_tools_list(request_id), session_id
            elif method == "tools/call":
                resp = await self._handle_tools_call(request_id, params, session_id=session_id)
                return resp, session_id
            elif method == "resources/list":
                return self._handle_resources_list(request_id), session_id
            elif method == "resources/templates/list":
                return self._handle_resources_templates_list(request_id), session_id
            elif method == "resources/read":
                resp = await self._handle_resources_read(request_id, params)
                return resp, session_id
            else:
                return self._create_error_response(request_id, -32601, f"Method not found: {method}"), session_id

        except Exception as e:
            return self._create_error_response(request.get("id"), -32603, str(e)), session_id

    def _handle_initialize(self, request_id: Any, _params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {
                        "listChanged": False
                    }
                },
                "serverInfo": self.server_info
            }
        }

    def _handle_tools_list(self, request_id: Any) -> Dict[str, Any]:
        """Handle tools/list request."""
        tools = []
        for name, tool_item in self.tools.items():
            tools.append({
                "name": name,
                "description": tool_item.primitive.description,
                "inputSchema": tool_item.primitive.input_schema
            })

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": tools}
        }

    async def _handle_tools_call(
        self, request_id: Any, params: Dict[str, Any], session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in self.tools:
            return self._create_error_response(request_id, -32601, f"Tool not found: {tool_name}")

        if app:
            app.log(f"Calling tool: {tool_name}")

        try:
            tool_item = self.tools[tool_name]

            if tool_item.run_on_main_thread:
                result = await self._execute_on_main_thread(
                    tool_item.handler, arguments, request_id, "tool",
                    session_id=session_id, tool_name=tool_name,
                )
            else:
                result = tool_item.handler(**arguments)

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }
        except Exception as e:
            if app:
                app.log(f"Tool execution error: {str(e)}")
            return self._create_error_response(request_id, -32603, f"Tool execution error: {str(e)}")

    async def _execute_on_main_thread(
        self, handler_func, arguments: Dict[str, Any], request_id: Any,
        operation_type: str = "operation", session_id: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> Any:
        """Execute a handler function on the main thread using TaskManager.

        When *session_id* is provided the SessionManager activates the
        correct document and sets ``current_session_id`` before calling
        the handler so tools can read it without extra plumbing.
        """
        import threading
        import time
        import asyncio

        result_container = {'result': None, 'exception': None, 'completed': False}
        result_lock = threading.Lock()

        # Grab the execution queue before defining the callback so the
        # closure captures the same queue object used by enter()/leave().
        sm_for_queue = SessionManager.instance()
        queue = sm_for_queue._execution_queue

        def callback(data):
            # Tell the queue that Fusion is alive and processing.
            queue.mark_callback_started()

            # Resolve SessionManager via sys.modules so we always get the
            # current singleton, even after a hot-reload that replaced the
            # module-level import.
            import sys as _sys
            _sm_mod = _sys.modules.get("server.session_manager")
            sm = _sm_mod.SessionManager.instance() if _sm_mod else None
            try:
                if sm and session_id:
                    gate_result = sm.activate_document(session_id)
                    sm.current_session_id = session_id
                    if gate_result == "session_recovered":
                        can_recover = (
                            tool_name == "claim_document"
                            or data.get('arguments', {}).get('clean')
                            or data.get('arguments', {}).get('force_clean')
                        )
                        if not can_recover:
                            import json as _json
                            docs = [d for d in sm.list_available_documents()
                                    if d.get("doc_key")]
                            doc_list = "\n".join(
                                f"  - '{d['name']}'  doc_key={d['doc_key']}  "
                                f"bodies={d['body_count']}  "
                                f"owner={d['owner_session'] or 'none'}  "
                                f"status={d['owner_status']}"
                                for d in docs
                            ) or "  (no tagged documents found)"
                            with result_lock:
                                result_container['result'] = {
                                    "content": [{"type": "text", "text": (
                                        "Your session was restored after an "
                                        "add-in restart, but you have no "
                                        "document bound.\n\n"
                                        "Open documents with ShopPrentice tags:\n"
                                        f"{doc_list}\n\n"
                                        "To reclaim your document, call "
                                        "claim_document(doc_key='...') with the "
                                        "key of the document you were working on. "
                                        "If you're unsure which one, ask the user. "
                                        "To start fresh, use "
                                        "execute_script(clean=True)."
                                    )}],
                                    "isError": True,
                                    "message": "Session restored — claim a document to continue",
                                }
                                result_container['completed'] = True
                            return
                    elif gate_result == "doc_gone":
                        args = data.get('arguments', {})
                        can_recover = (
                            args.get('clean') or args.get('force_clean')
                            or tool_name == "claim_document"
                        )
                        if not can_recover:
                            with result_lock:
                                result_container['result'] = {
                                    "content": [{"type": "text", "text": (
                                        "Your document was closed. Use "
                                        "execute_script(clean=True) to create "
                                        "a new one, or call claim_document to "
                                        "adopt an existing document."
                                    )}],
                                    "isError": True,
                                    "message": "Session document was closed",
                                }
                                result_container['completed'] = True
                            return
                    elif gate_result is not None:
                        with result_lock:
                            result_container['result'] = gate_result
                            result_container['completed'] = True
                        return
                if sm:
                    sm.throttle_gate()
                result = handler_func(**data['arguments'])
                with result_lock:
                    result_container['result'] = result
                    result_container['completed'] = True
            except Exception as e:
                with result_lock:
                    result_container['exception'] = e
                    result_container['completed'] = True
            finally:
                if sm:
                    sm.record_execution_end()
                    if session_id:
                        sess = sm.get_session(session_id)
                        if sess:
                            sm._save_global_state(sess)
                        sm.current_session_id = None

        # ── queue serialization ───────────────────────────────────────
        # Block until it is this request's turn.  The queue tells us
        # how long we waited and how many tools were ahead so we can
        # relay that to the agent (avoids "is Fusion broken?" confusion).
        queue_meta = queue.enter(tool_name or operation_type, session_id)

        try:
            if not TaskManager.is_running():
                if app:
                    app.log("TaskManager is not running, attempting to start it")
                TaskManager.start()

            task_id = TaskManager.post(
                command=f"execute_{operation_type}",
                callback=callback,
                data={"arguments": arguments}
            )

            if not task_id:
                raise Exception("Failed to post task to TaskManager")

            if app:
                app.log(f"Posted {operation_type} execution task {task_id} to main thread")

            timeout = 1800  # 30 minute timeout
            start_time = time.time()
            posted_at = time.time()

            while time.time() - start_time < timeout:
                with result_lock:
                    if result_container['completed']:
                        if result_container['exception'] is not None:
                            raise result_container['exception']
                        result = result_container['result']

                        # Inject queue wait info so the agent knows
                        # the delay was normal queuing, not a failure.
                        if (queue_meta['wait_time'] > 1.0
                                and isinstance(result, dict)
                                and isinstance(
                                    result.get('content'), list)):
                            result['content'].insert(0, {
                                "type": "text",
                                "text": (
                                    f"[Queue: waited "
                                    f"{queue_meta['wait_time']:.1f}s, "
                                    f"{queue_meta['queue_depth_on_entry']}"
                                    " tool(s) ahead of yours. Fusion 360 "
                                    "processes one tool at a time; this "
                                    "is normal.]"
                                ),
                            })

                        return result

                # Outside the result_lock — check whether Fusion even
                # started processing our callback.
                health_err = queue.check_health(
                    posted_at, tool_name=tool_name,
                )
                if health_err:
                    return {
                        "content": [{"type": "text", "text": health_err}],
                        "isError": True,
                    }

                await asyncio.sleep(0.01)

            # Callback started but never completed within the timeout.
            lines = [
                f"The '{tool_name or operation_type}' tool has been "
                f"running for {timeout}s without completing. "
                "Fusion 360 is likely frozen.",
                "",
                "**Action required:**",
                "1. Tell the user that Fusion 360 appears frozen and "
                "needs to be restarted.",
            ]
            if tool_name == "execute_script":
                lines.extend([
                    "2. Review the script you sent for crash-causing "
                    "bugs:",
                    "   - Infinite loops or unbounded recursion",
                    "   - doc.close() / app.documents.add() calls "
                    "(forbidden)",
                    "   - TemporaryBRepManager use (unsupported)",
                    "   - Very large body counts or complex boolean "
                    "operations",
                    "3. Prepare a corrected script to run after the "
                    "restart.",
                ])
            else:
                lines.append(
                    "2. Once Fusion is restarted, retry this tool call."
                )
            return {
                "content": [{"type": "text", "text": "\n".join(lines)}],
                "isError": True,
            }
        finally:
            queue.leave()

    def _handle_resources_list(self, request_id: Any) -> Dict[str, Any]:
        """Handle resources/list request."""
        resources = []
        for uri, resource_item in self.resources.items():
            if resource_item.primitive.uri:
                resource_dict = resource_item.primitive.to_dict()
                resources.append(resource_dict)

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"resources": resources}
        }

    def _handle_resources_templates_list(self, request_id: Any) -> Dict[str, Any]:
        """Handle resources/templates/list request."""
        resources = []
        for uri, resource_item in self.resources.items():
            if resource_item.primitive.uri_template:
                resource_dict = resource_item.primitive.to_dict()
                resources.append(resource_dict)

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"resources": resources}
        }

    def _find_resource_by_template(self, uri: str):
        """Find a resource by matching URI templates."""
        import re
        from urllib.parse import urlparse, parse_qs

        for resource_uri, resource_item in self.resources.items():
            if resource_item.primitive.uri_template:
                template = resource_item.primitive.uri_template

                if '{?' in template:
                    base_template = re.sub(r'\{[?]?[^}]+\}', '', template).rstrip('/')
                    parsed_uri = urlparse(uri)
                    base_uri = f"{parsed_uri.scheme}://{parsed_uri.netloc}{parsed_uri.path}"

                    if base_template == base_uri:
                        return resource_item
                else:
                    if self._match_template_path(template, uri):
                        return resource_item

        return None

    def _match_template_path(self, template: str, uri: str) -> bool:
        """Match a URI template path against a URI."""
        import re

        pattern = template
        for var in re.findall(r'\{(\w+)\}', pattern):
            pattern = pattern.replace(f'{{{var}}}', f'(?P<{var}>[^/]+)')

        pattern = f'^{pattern}$'
        match = re.match(pattern, uri)
        return match is not None

    async def _handle_resources_read(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/read request."""
        uri = params.get("uri")

        resource_item = self.resources.get(uri)

        if not resource_item:
            resource_item = self._find_resource_by_template(uri)

        if not resource_item:
            return self._create_error_response(request_id, -32601, f"Resource not found: {uri}")

        try:
            handler_args = {k: v for k, v in params.items() if k != "uri"}

            from urllib.parse import urlparse, parse_qs
            parsed_uri = urlparse(uri)
            if parsed_uri.query:
                query_params = parse_qs(parsed_uri.query)
                for key, value_list in query_params.items():
                    handler_args[key] = value_list[0] if value_list else None

            if resource_item.run_on_main_thread:
                result = await self._execute_on_main_thread(resource_item.handler, handler_args, request_id, "resource")
            else:
                result = resource_item.handler(**handler_args)

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": resource_item.primitive.mime_type or "application/json",
                            "text": result
                        }
                    ]
                }
            }
        except Exception as e:
            if app:
                app.log(f"Resource execution error: {str(e)}")
            return self._create_error_response(request_id, -32603, f"Resource read error: {str(e)}")

    def _create_error_response(self, request_id: Any, code: int, message: str) -> Dict[str, Any]:
        """Create an error response."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }


class MCPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for MCP protocol over HTTP."""

    # Cap on how much of a *rejected* request body we drain before
    # replying, so a bogus Content-Length cannot keep us reading.
    _MAX_DRAIN = 65536

    def __init__(self, *args, mcp_server=None, **kwargs):
        self.mcp_server = mcp_server
        super().__init__(*args, **kwargs)

    def _drain_body(self):
        """Discard a rejected request's body.

        Without this the client sees a connection reset instead of our
        error response, which turns a clear "you're missing the token"
        into a mystery for anyone with a misconfigured client.
        """
        try:
            remaining = min(max(int(self.headers.get('Content-Length', 0)), 0),
                            self._MAX_DRAIN)
        except (TypeError, ValueError):
            return
        while remaining > 0:
            chunk = self.rfile.read(min(remaining, 8192))
            if not chunk:
                break
            remaining -= len(chunk)

    def _gate(self) -> bool:
        """Apply the request gate; answer the client and return False on deny.

        Called from every do_* method. Any HTTP method without a do_*
        handler is already refused by BaseHTTPRequestHandler with 501,
        so gating GET and POST covers everything that can reach a tool.
        """
        allowed, status, reason = check_request_allowed(
            self.headers, self.command, secret=read_shared_secret(),
        )
        if allowed:
            return True
        if app:
            app.log(
                f"[security] rejected {self.command} {self.path}: {reason} "
                f"(Origin={self.headers.get('Origin')!r} "
                f"Host={self.headers.get('Host')!r})"
            )
        self._drain_body()
        self.send_error(status, reason)
        return False

    def do_POST(self):
        """Handle MCP protocol requests"""
        if not self._gate():
            return
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            request_data = json.loads(post_data.decode('utf-8'))

            session_id = self.headers.get('Mcp-Session-Id')
            method = request_data.get("method", "?")
            if app:
                app.log(f"[session] {method} | header={session_id or '(none)'}")

            response, response_session_id = asyncio.run(
                self.mcp_server.handle_request(request_data, session_id=session_id)
            )

            self._send_json_response(response, session_id=response_session_id)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
        except Exception as e:
            self.send_error(500, str(e))

    def do_GET(self):
        """Handle GET requests for health checks"""
        # Gated too: /tools leaks the whole tool surface, and a wide-open
        # /health is a fingerprint telling a page the add-in is running.
        if not self._gate():
            return
        if self.path == '/health':
            self._send_json_response({"status": "healthy", "server": "ShopPrentice"})
        elif self.path == '/tools':
            response = self.mcp_server._handle_tools_list(1)
            self._send_json_response(response)
        elif self.path == '/':
            self._send_json_response({
                "message": "ShopPrentice MCP Server",
                "endpoints": ["POST / (MCP protocol)", "GET /health", "GET /tools"]
            })
        else:
            self.send_error(404, "Not Found")

    def _send_json_response(self, data, session_id: str = None):
        """Send JSON response, optionally including ``Mcp-Session-Id``."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        # No Access-Control-Allow-Origin: a browser must not be able to
        # read these replies. Removing the old wildcard is the backstop
        # behind the Origin/Host/Content-Type gate.
        self.send_header('X-Content-Type-Options', 'nosniff')
        if session_id:
            self.send_header('Mcp-Session-Id', session_id)
        self.end_headers()

        response_json = json.dumps(data, indent=2)
        self.wfile.write(response_json.encode())

    def log_message(self, format, *args):
        """Override to reduce logging noise"""
        pass


def start_mcp_server(
    host: str = '127.0.0.1',
    port: int = 9100,
    tools: Optional[Dict[str, Any]] = None,
    resources: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[SimpleMCPServer], Optional[ThreadedHTTPServer], Optional[threading.Thread]]:
    """Start the ShopPrentice MCP server over HTTP.

    *host* defaults to the literal loopback address rather than the name
    ``localhost`` so a hijacked resolver cannot widen the bind.
    """
    global _allowed_hosts
    try:
        # Teach the request gate which Host: values name this socket.
        _allowed_hosts = loopback_hosts(port)

        mcp = SimpleMCPServer("ShopPrentice")

        if tools:
            for tool in tools:
                mcp.register(tool)

        if resources:
            for resource_item in resources:
                mcp.register(resource_item)

        server_address = (host, port)

        class HandlerWithMCP(MCPHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, mcp_server=mcp, **kwargs)

        http_server = ThreadedHTTPServer(server_address, HandlerWithMCP)

        server_thread = threading.Thread(
            target=http_server.serve_forever,
            daemon=True,
            name=f"ShopPrentice-Server-{host}:{port}"
        )
        server_thread.start()

        auth = "token required" if read_shared_secret() else f"no token ({TOKEN_FILE} absent)"
        print(f"ShopPrentice server started on http://{host}:{port} [{auth}]")
        if app:
            app.log(f"ShopPrentice server started on http://{host}:{port} [{auth}]")
        return mcp, http_server, server_thread

    except Exception as e:
        print(f"Failed to start ShopPrentice server: {str(e)}")
        if app:
            app.log(f"Failed to start ShopPrentice server: {str(e)}\n{traceback.format_exc()}")
        return None, None, None


def stop_mcp_server(http_server, server_thread, timeout=5):
    """Stop the ShopPrentice MCP server."""
    try:
        if http_server:
            http_server.shutdown()
            http_server.server_close()

        if server_thread and server_thread.is_alive():
            server_thread.join(timeout=timeout)
            return not server_thread.is_alive()

        return True

    except Exception as e:
        print(f"Error stopping ShopPrentice server: {str(e)}")
        if app:
            app.log(f"Error stopping ShopPrentice server: {str(e)}")
        return False
