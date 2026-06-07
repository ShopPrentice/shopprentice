"""Offline test of deps.py model.json resolution + missing-file skip path.

Pure Python — no Fusion required. Run: python3 tests/test_deps_model_json_skip.py

Covers the fix for the silent green light: when no model.json sits next to the
script, validate_deps must return None (skip) AND print an actionable message,
and resolve_model_json must report found=False with the path it looked for.
This is what lets validate_design surface "DEPS SKIPPED — add model.json"
instead of a clean PASS.
"""
import os, sys, types, importlib.util, io, contextlib, tempfile

for m in ("adsk", "adsk.core", "adsk.fusion"):
    sys.modules[m] = types.ModuleType(m)

_DEPS = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "helpers", "sp", "deps.py"))
spec = importlib.util.spec_from_file_location("deps", _DEPS)
deps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deps)

passed = 0
failed = 0


def check(label, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"[PASS] {label}")
    else:
        failed += 1
        print(f"[FAIL] {label}")


# 1. Explicit metadata_path that does not exist → found=False, returns None,
#    and prints the actionable "create model.json" message.
missing = os.path.join(tempfile.gettempdir(), "definitely_no_such_model.json")
path, found = deps.resolve_model_json(missing)
check("resolve: explicit missing path returns found=False", path == missing and found is False)

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    result = deps.validate_deps(ctx=None, metadata_path=missing)
out = buf.getvalue()
check("validate_deps: missing model.json returns None (skip)", result is None)
check("validate_deps: prints actionable model.json message",
      "model.json" in out and "skipping" in out)
check("validate_deps: does not touch ctx on skip path (ctx=None survived)", True)

# 2. Explicit metadata_path that DOES exist → found=True.
with tempfile.NamedTemporaryFile("w", suffix="_model.json", delete=False) as f:
    f.write("{}")
    existing = f.name
try:
    path2, found2 = deps.resolve_model_json(existing)
    check("resolve: existing path returns found=True", path2 == existing and found2 is True)
finally:
    os.unlink(existing)

# 3. No metadata_path and no tracked script path → (None, False).
#    DocumentTracker import fails offline, so script_path stays None.
path3, found3 = deps.resolve_model_json(None)
check("resolve: no script path returns (None, False)", path3 is None and found3 is False)

print(f"\n{passed}/{passed + failed} cases passed")
sys.exit(1 if failed else 0)
