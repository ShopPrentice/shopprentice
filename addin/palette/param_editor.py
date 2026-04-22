"""
Parameter Editor Palette

Dockable HTML panel showing all user parameters grouped by prefix.
Edit values inline → updates Fusion parameter immediately.
Rebuild button → patches user's current values into the tracked script,
re-executes it, and keeps the palette with current values.
"""

import json
import os
import re
import time
import traceback

import adsk.core
import adsk.fusion

PALETTE_ID = "ShopPrentice_ParamEditor"
PALETTE_NAME = "ShopPrentice"
PALETTE_WIDTH = 380
PALETTE_HEIGHT = 600

_html_path = os.path.join(os.path.dirname(__file__), "param_editor.html")
_handler = None  # prevent GC


def _get_user_params():
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        return []

    params = []
    for i in range(design.userParameters.count):
        p = design.userParameters.item(i)
        params.append({
            "name": p.name,
            "expression": p.expression,
            "value": p.value,
            "unit": p.unit,
            "comment": p.comment,
        })

    param_names = {p["name"] for p in params}

    def is_derived(p):
        expr = p["expression"]
        return any(n in expr for n in param_names if n != p["name"])

    params.sort(key=lambda p: (is_derived(p), p["name"]))
    return params


def _set_param(name, expression):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        return
    p = design.userParameters.itemByName(name)
    if p:
        try:
            p.expression = expression
        except Exception:
            pass


def _patch_script(script, current_params):
    """Patch parameter default values in the script with current Fusion values.

    Looks for lines like:  ("param_name", "old_value", "unit", "comment"),
    and replaces "old_value" with the current expression.
    """
    for p in current_params:
        name = p["name"]
        new_expr = p["expression"]
        # Match: ("name", "anything", ...) — replace the second quoted string
        pattern = rf'(\(\s*"{re.escape(name)}"\s*,\s*)"([^"]*)"'
        replacement = rf'\1"{new_expr}"'
        script = re.sub(pattern, replacement, script)
    return script


def _build_html(params_json):
    with open(_html_path, "r") as f:
        html = f.read()
    inject = (
        f'\n<script>window.onload = function() {{'
        f' loadParams({json.dumps(params_json)}); }};</script>\n'
    )
    html = html.replace('</body>', inject + '</body>')
    tmp_path = os.path.join(os.path.dirname(_html_path), "_param_editor_live.html")
    with open(tmp_path, "w") as f:
        f.write(html)
    return tmp_path


def _refresh_callback(data):
    """Called by TaskManager on the main thread to do the actual rebuild."""
    app = adsk.core.Application.get()
    try:
        from server.document_tracker import DocumentTracker

        script = DocumentTracker._script_source
        if not script:
            DocumentTracker._try_restore()
            script = DocumentTracker._script_source
        if not script:
            app.log("ParamEditor: no tracked script — run execute_script first")
            return

        # Capture current param values (user's edits) and patch into script
        current_params = _get_user_params()
        patched_script = _patch_script(script, current_params)

        # Write patched script back to file on disk (if path is known)
        script_path = DocumentTracker._script_path
        if script_path and os.path.isfile(script_path):
            with open(script_path, "w") as f:
                f.write(patched_script)
            app.log(f"ParamEditor: saved params to {script_path}")

        from tools.execute_script import handler as exec_handler
        start = time.time()
        # Palette Rebuild is explicit user action — bypass the clean=True
        # provenance guard (may legitimately fire with needsSync=true right
        # after an add-in restart when the user edits params and rebuilds).
        result = exec_handler(script=patched_script, clean=True, force_clean=True)
        elapsed = round(time.time() - start, 1)
        is_error = result.get("isError", False)
        app.log(f"ParamEditor: rebuild {'FAILED' if is_error else 'OK'} in {elapsed}s")

    except Exception:
        app.log(f"ParamEditor refresh error: {traceback.format_exc()}")


def _sync_callback(data):
    """Called by TaskManager to run sync_script and cache results."""
    app = adsk.core.Application.get()
    try:
        from tools.sync_script import handler as sync_handler
        result = sync_handler()
        applied = result.get("applied", [])
        needs = result.get("needsAgent", [])
        app.log(f"ParamEditor: sync captured {len(applied)} param changes, "
                f"{len(needs)} structural changes")
    except Exception:
        app.log(f"ParamEditor sync error: {traceback.format_exc()}")


class _HTMLHandler(adsk.core.HTMLEventHandler):
    def notify(self, args: adsk.core.HTMLEventArgs):
        try:
            action = args.action
            data = args.data

            if action == "paramChange":
                info = json.loads(data)
                _set_param(info["name"], info["expression"])

            elif action == "ping":
                pass  # just return — lets HTML know we're responsive

            elif action == "sync":
                # Capture UI changes via sync_script (async via TaskManager)
                import threading
                def _deferred_sync():
                    import time
                    time.sleep(0.2)
                    from server.task_manager import TaskManager
                    TaskManager.post("param_sync", _sync_callback, {})
                threading.Thread(target=_deferred_sync, daemon=True).start()

            elif action == "refresh":
                import threading
                def _deferred_post():
                    import time
                    time.sleep(0.2)
                    from server.task_manager import TaskManager
                    TaskManager.post("param_refresh", _refresh_callback, {})
                threading.Thread(target=_deferred_post, daemon=True).start()

        except Exception:
            app = adsk.core.Application.get()
            if app:
                app.log(f"ParamEditor error: {traceback.format_exc()}")


class ParamEditorPalette:

    @staticmethod
    def create():
        global _handler

        app = adsk.core.Application.get()
        ui = app.userInterface
        palettes = ui.palettes

        # Delete existing palette
        existing = palettes.itemById(PALETTE_ID)
        if existing:
            existing.deleteMe()

        params = _get_user_params()
        tmp_path = _build_html(json.dumps(params))
        html_url = f"file:///{tmp_path.replace(os.sep, '/')}"

        palette = palettes.add(
            PALETTE_ID,
            PALETTE_NAME,
            html_url,
            True, True, True,
            PALETTE_WIDTH, PALETTE_HEIGHT,
        )

        _handler = _HTMLHandler()
        palette.incomingFromHTML.add(_handler)

        app.log(f"ParamEditor: {len(params)} params loaded")
        return palette

    @staticmethod
    def destroy():
        global _handler
        app = adsk.core.Application.get()
        if not app:
            return
        palette = app.userInterface.palettes.itemById(PALETTE_ID)
        if palette:
            palette.deleteMe()
        _handler = None

    @staticmethod
    def refresh_params():
        ParamEditorPalette.create()
