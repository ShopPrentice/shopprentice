"""Dev server for the build123d viewer.

Serves the spike directory (viewer.html, out/) and adds one endpoint:

  POST /rebuild   {"model": "midou", "set": {"top_w": 24, ...}}

Rebuilds run IN-PROCESS: build123d/OCP is imported once at server startup
(~2 s), and each rebuild importlib.reload()s the model script (picks up
source edits) and calls build(overrides) directly — profiling showed the
subprocess approach spent 60% of its wall clock re-importing the kernel.
One rebuild at a time (lock); a crash in OCCT would take the server down,
which is acceptable for a dev tool (restart is 2 s).

The script bumps the manifest stamp, so the open viewer hot-swaps the new
geometry on its next poll. Binds localhost only.

Run:  ../../.venv-b123d/bin/python server.py     (from spike/build123d/)
"""
import contextlib
import importlib
import io
import json
import os
import threading
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import b123d_common          # imports build123d/OCP once, at startup

PORT = 8731
MODELS = {
    "midou": ("midou_b123d", "out/midou"),
    "ming_table": ("ming_table_b123d", "out/ming_table"),
}
# capture-converted models rebuild from their capture JSON, not a script.
# README-referenced examples only (mirror-frame/toy-box captures remain in
# captures/ as converter regression fixtures but are not served).
CAPTURES = {
    "pencil_box": "captures/pencil_box_capture.json",
}
LABELS = {"midou": "Midou 米斗", "ming_table": "Ming 平头案",
          "pencil_box": "Pencil box"}
_lock = threading.Lock()


def _rebuild(model, overrides):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        if model in CAPTURES:
            if overrides:
                raise ValueError("capture-converted models are not parametric")
            conv = importlib.reload(importlib.import_module("capture_to_b123d"))
            m, _parity = conv.convert(CAPTURES[model])
            stem = "out/" + model
        else:
            modname, stem = MODELS[model]
            mod = importlib.reload(importlib.import_module(modname))
            m = mod.build(overrides)
        b123d_common.summarize(m)
        ok = m.validate()
        m.export_parts(stem)   # BEFORE export: STL meshing caches triangulation
        m.export(stem)
    return ok, buf.getvalue()


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/models":
            # dynamic model index: every known model whose manifest exists.
            # The viewer builds its selector from this, so newly converted
            # examples appear without touching viewer.html.
            models = []
            for key in list(MODELS) + list(CAPTURES):
                if key not in [m["key"] for m in models] and \
                        os.path.exists(f"out/{key}.json"):
                    models.append({"key": key,
                                   "label": LABELS.get(key, key),
                                   "file": f"out/{key}.json",
                                   "parametric": key in MODELS})
            self._json(models)
            return
        super().do_GET()

    def do_POST(self):
        if self.path != "/rebuild":
            self.send_error(404)
            return
        n = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            self._json({"ok": False, "log": "bad JSON"})
            return
        if req.get("model") not in MODELS and req.get("model") not in CAPTURES:
            self._json({"ok": False, "log": "unknown model %r" % req.get("model")})
            return
        with _lock:
            try:
                ok, log = _rebuild(req["model"], req.get("set") or {})
            except Exception:
                ok, log = False, traceback.format_exc()[-4000:]
        self._json({"ok": ok, "log": log[-4000:]})

    def _json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *a):     # quiet the GET spam from polling
        if "POST" in (a[0] if a else ""):
            super().log_message(fmt, *a)


if __name__ == "__main__":
    print(f"viewer:  http://localhost:{PORT}/viewer.html")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
