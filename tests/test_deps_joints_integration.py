"""Offline integration test: validate_deps wires in the joint registry (issue 106).

Pure Python — no Fusion required. Run: python3 tests/test_deps_joints_integration.py

Drives the full validate_deps() with a model.json that carries a `joints` array, using
a stub context with no real geometry (empty root). Confirms:
  - a clean declared joint passes,
  - a malformed declaration (unknown type) folds into a HARD deps FAIL,
  - the joint-check section is printed,
  - a model with NO joints array doesn't engage the joint check at all.
"""
import os, sys, types, importlib.util, json, tempfile, io, contextlib

for m in ("adsk", "adsk.core", "adsk.fusion"):
    sys.modules.setdefault(m, types.ModuleType(m))

_SP = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "helpers", "sp"))

for pkg in ("helpers", "helpers.sp"):
    mod = types.ModuleType(pkg)
    mod.__path__ = []
    sys.modules[pkg] = mod

def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_SP, filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

_load("helpers.sp.joint_strength", "joint_strength.py")
_load("helpers.sp.joint_registry", "joint_registry.py")

# Stub mating: contacting_pairs (no contacts) + tenon_wide_direction (grain fine).
_mating = types.ModuleType("helpers.sp.mating")
_mating.contacting_pairs = lambda ctx, min_area_cm2=1.0: []
_mating.tenon_wide_direction = lambda mortise_body, axis: object()
sys.modules["helpers.sp.mating"] = _mating

deps = _load("helpers.sp.deps", "deps.py")

R = []
def check(name, cond):
    R.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name)


class _Coll:
    def __init__(self, items): self._i = items
    @property
    def count(self): return len(self._i)
    def item(self, i): return self._i[i]

class _Root:
    occurrences = _Coll([])
    bRepBodies = _Coll([])

class _Body:
    def __init__(self, name): self.name = name

class StubCtx:
    def __init__(self, bodies):
        self.root = _Root()
        self._b = {n: _Body(n) for n in bodies}
    def find_body(self, name, component=None):
        return self._b.get(name)
    def ev(self, expr):
        if isinstance(expr, (int, float)):
            return float(expr)
        s = str(expr).strip()
        if s.endswith("in"):
            return float(s[:-2]) * 2.54
        if s.endswith("cm"):
            return float(s[:-2])
        return float(s)


def run_deps(meta, bodies):
    with tempfile.NamedTemporaryFile("w", suffix="_model.json", delete=False) as f:
        json.dump(meta, f)
        path = f.name
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            res = deps.validate_deps(StubCtx(bodies), metadata_path=path)
        return res, buf.getvalue()
    finally:
        os.unlink(path)


ORIGIN_DEP = [{"body": "Leg_FL", "ref": "origin"}, {"body": "Rail_F", "ref": "Leg_FL"}]

# 1. Clean declared joint -> deps PASS, joint section printed.
res, out = run_deps({
    "deps": ORIGIN_DEP,
    "joints": [{"type": "mortise_tenon", "tenon": "Rail_F", "mortise": "Leg_FL",
                "axis": "y", "species": "white_oak",
                "width": "2 in", "thickness": "0.75 in", "depth": "1.5 in"}],
}, ["Leg_FL", "Rail_F"])
check("clean declared joint -> deps PASS", res is True)
check("joint strength section printed", "Joint strength check" in out)
check("clean joint shows OK", "OK   Rail_F -> Leg_FL" in out)

# 2. Malformed joint (unknown type) -> HARD deps FAIL.
res, out = run_deps({
    "deps": ORIGIN_DEP,
    "joints": [{"type": "bogus", "tenon": "Rail_F", "mortise": "Leg_FL"}],
}, ["Leg_FL", "Rail_F"])
check("unknown joint type -> deps FAIL", res is False)
check("unknown type reported as FAIL", "unknown joint type" in out)

# 3. Joint referencing a missing body -> HARD deps FAIL.
res, out = run_deps({
    "deps": ORIGIN_DEP,
    "joints": [{"type": "mortise_tenon", "tenon": "Ghost", "mortise": "Leg_FL",
                "axis": "y"}],
}, ["Leg_FL", "Rail_F"])
check("missing joint body -> deps FAIL", res is False and "not found" in out)

# 4. Declared thin-slice joint -> WARN but deps still PASS (advisory).
res, out = run_deps({
    "deps": ORIGIN_DEP,
    "joints": [{"type": "mortise_tenon", "tenon": "Rail_F", "mortise": "Leg_FL",
                "axis": "y", "width": "3 in", "thickness": "0.4 in", "depth": "1 in"}],
}, ["Leg_FL", "Rail_F"])
check("thin-slice joint -> WARN, deps still PASS", res is True and "thin slice" in out)

# 5. No joints array -> joint check never engages.
res, out = run_deps({"deps": ORIGIN_DEP}, ["Leg_FL", "Rail_F"])
check("no joints array -> deps PASS", res is True)
check("no joints array -> joint section NOT printed", "Joint strength check" not in out)

print("\n%d/%d cases passed" % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
