"""Offline tests for the declarative joint registry (issue 106).

Pure Python — no Fusion required. Run: python3 tests/test_joint_registry.py

Covers joint_registry: validate_joint dispatch (unknown type, missing field, unresolved
body, sizing flags, hand-built joint), key_for / joint_covers, and declare_joint's
load-merge-dedup-write to model.json (auto-declare).

The module's Fusion-touching imports are all lazy, so we register a minimal
``helpers.sp`` namespace (deps + joint_strength loaded from file, a stub mating) in
sys.modules — absolute imports inside joint_registry resolve to these WITHOUT running
helpers/sp/__init__.py (which pulls in adsk-using submodules).
"""
import os, sys, types, importlib.util, json, tempfile

for m in ("adsk", "adsk.core", "adsk.fusion"):
    sys.modules.setdefault(m, types.ModuleType(m))

_SP = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "helpers", "sp"))

# Minimal package namespaces so `from helpers.sp.X import ...` resolves to file-loaded
# modules, bypassing the heavy package __init__.
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
_load("helpers.sp.deps", "deps.py")

# Stub mating.tenon_wide_direction for _grain_sanity: returns None (end-grain) only when
# the mortise body opts in with ._endgrain, else a truthy sentinel (grain is fine).
_mating = types.ModuleType("helpers.sp.mating")
def _twd(mortise_body, axis):
    return None if getattr(mortise_body, "_endgrain", False) else object()
_mating.tenon_wide_direction = _twd
sys.modules["helpers.sp.mating"] = _mating

jr = _load("helpers.sp.joint_registry", "joint_registry.py")

R = []
def check(name, cond):
    R.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name)

def has(flags, needle):
    return any(needle in f for f in flags)


# --- stub DesignContext -------------------------------------------------------
class StubBody:
    def __init__(self, name, endgrain=False):
        self.name = name
        self._endgrain = endgrain

class StubCtx:
    """find_body returns a StubBody for known names; ev evaluates '<n> in' / '<n> cm'
    / bare numbers to cm (mirrors DesignContext.ev units)."""
    def __init__(self, bodies):
        self._bodies = {b: StubBody(b) for b in bodies}
    def add(self, body):
        self._bodies[body.name] = body
    def find_body(self, name, component=None):
        return self._bodies.get(name)
    def ev(self, expr):
        if isinstance(expr, (int, float)):
            return float(expr)
        s = str(expr).strip()
        if s.endswith("in"):
            return float(s[:-2]) * 2.54
        if s.endswith("cm"):
            return float(s[:-2])
        return float(s)            # bare numeric string -> cm


# --- key_for / joint_covers ---------------------------------------------------
d1 = {"type": "mortise_tenon", "tenon": "Rail_F", "mortise": "Leg_FL"}
d2 = {"type": "mortise_tenon", "tenon": "Leg_FL", "mortise": "Rail_F"}   # swapped
check("key_for is order-independent", jr.key_for(d1) == jr.key_for(d2))
check("key_for distinguishes type",
      jr.key_for(d1) != jr.key_for({**d1, "type": "pegged_tenon"}))
check("joint_covers matches the pair", jr.joint_covers(d1, "Rail_F", "Leg_FL"))
check("joint_covers ignores unrelated pair", not jr.joint_covers(d1, "Rail_F", "Seat"))


# --- validate_joint: declaration errors --------------------------------------
ctx = StubCtx(["Rail_F", "Leg_FL"])

r = jr.validate_joint({"type": "frobnicate", "tenon": "Rail_F", "mortise": "Leg_FL"}, ctx)
check("unknown type -> error + ok False", not r["ok"] and has(r["errors"], "unknown joint type"))

r = jr.validate_joint({"type": "mortise_tenon", "tenon": "Rail_F"}, ctx)
check("missing required field -> error", not r["ok"] and has(r["errors"], "missing required field"))

r = jr.validate_joint({"type": "mortise_tenon", "tenon": "Ghost", "mortise": "Leg_FL"}, ctx)
check("unresolved tenon body -> error", not r["ok"] and has(r["errors"], "not found"))


# --- validate_joint: M&T sizing (hand-built joint, criterion 5) ---------------
r = jr.validate_joint({"type": "mortise_tenon", "tenon": "Rail_F", "mortise": "Leg_FL",
                       "axis": "y", "species": "white_oak",
                       "width": "2 in", "thickness": "0.75 in", "depth": "1.5 in"}, ctx)
check("hand-built healthy M&T validates clean", r["ok"] and r["flags"] == [])

r = jr.validate_joint({"type": "mortise_tenon", "tenon": "Rail_F", "mortise": "Leg_FL",
                       "axis": "y", "species": "white_oak",
                       "width": "3 in", "thickness": "0.4 in", "depth": "1 in"}, ctx)
check("declared thin slice -> WARN flag, still ok (advisory)",
      r["ok"] and has(r["flags"], "thin slice"))

r = jr.validate_joint({"type": "mortise_tenon", "tenon": "Rail_F", "mortise": "Leg_FL",
                       "axis": "y", "species": "white_oak"}, ctx)
check("M&T with no dims -> NOTE (sizing skipped), still ok",
      r["ok"] and has(r["notes"], "no tenon dimensions"))

# Bad dimension expression -> hard error.
r = jr.validate_joint({"type": "mortise_tenon", "tenon": "Rail_F", "mortise": "Leg_FL",
                       "axis": "y", "width": "garbage", "thickness": "0.5 in",
                       "depth": "1 in"}, ctx)
check("bad dimension expression -> error", not r["ok"] and has(r["errors"], "dimension"))


# --- validate_joint: end-grain mortise (grain sanity) -------------------------
ctx_eg = StubCtx(["Rail_F"])
ctx_eg.add(StubBody("Leg_EG", endgrain=True))
r = jr.validate_joint({"type": "mortise_tenon", "tenon": "Rail_F", "mortise": "Leg_EG",
                       "axis": "y", "width": "2 in", "thickness": "0.75 in",
                       "depth": "1.5 in"}, ctx_eg)
check("end-grain mortise -> grain WARN flag", has(r["flags"], "end-grain mortise"))


# --- validate_joint: pegged_tenon --------------------------------------------
r = jr.validate_joint({"type": "pegged_tenon", "tenon": "Rail_F", "mortise": "Leg_FL",
                       "axis": "y", "species": "white_oak",
                       "width": "1.5 in", "thickness": "0.5 in", "depth": "1 in",
                       "pins": 1, "pin_dia": "0.375 in", "pin_end_distance": "0.5 in"}, ctx)
check("pegged: brittle relish flagged", has(r["flags"], "relish"))

r = jr.validate_joint({"type": "pegged_tenon", "tenon": "Rail_F", "mortise": "Leg_FL",
                       "axis": "y", "species": "white_oak",
                       "width": "1.5 in", "thickness": "0.5 in", "depth": "1 in",
                       "pins": 1, "pin_dia": "0.375 in", "pin_end_distance": "2 in"}, ctx)
check("pegged: adequate relish -> ok, no relish flag",
      r["ok"] and not has(r["flags"], "relish"))


# --- validate_joint: wedged_tenon (forward-compat with #105) -------------------
r = jr.validate_joint({"type": "wedged_tenon", "tenon": "Rail_F", "mortise": "Leg_FL",
                       "axis": "y", "width": "2 in", "thickness": "0.75 in",
                       "depth": "1.5 in"}, ctx)
check("wedged: validates as M&T + #105 note", r["ok"] and has(r["notes"], "#105"))


# --- validate_joints: aggregate ------------------------------------------------
res = jr.validate_joints(ctx, [
    {"type": "mortise_tenon", "tenon": "Rail_F", "mortise": "Leg_FL", "axis": "y",
     "width": "2 in", "thickness": "0.75 in", "depth": "1.5 in"},
    {"type": "nope", "tenon": "Rail_F", "mortise": "Leg_FL"},
])
check("validate_joints reports the error count", res["n_err"] == 1 and not res["ok"])


# --- declare_joint: load-merge-dedup-write ------------------------------------
with tempfile.TemporaryDirectory() as d:
    mj = os.path.join(d, "model.json")

    # No-op when model.json doesn't exist yet (registry is agent-authored).
    ok = jr.declare_joint({"type": "mortise_tenon", "tenon": "Rail_F",
                           "mortise": "Leg_FL"}, metadata_path=mj)
    check("declare_joint no-ops when model.json absent", ok is False and not os.path.exists(mj))

    # Seed model.json with deps (as the agent would).
    with open(mj, "w") as f:
        json.dump({"deps": [{"body": "Leg_FL", "ref": "origin"}]}, f)

    ok = jr.declare_joint({"type": "mortise_tenon", "tenon": "Rail_F", "mortise": "Leg_FL",
                           "axis": "y", "width": "2 in", "thickness": "0.75 in",
                           "depth": "1.5 in"}, metadata_path=mj)
    meta = json.load(open(mj))
    check("declare_joint appended one joint", ok and len(meta.get("joints", [])) == 1)
    check("declare_joint preserved deps", meta.get("deps") == [{"body": "Leg_FL", "ref": "origin"}])

    # Re-declare the SAME joint (different dims) -> update in place, no duplicate.
    jr.declare_joint({"type": "mortise_tenon", "tenon": "Leg_FL", "mortise": "Rail_F",
                      "axis": "y", "width": "2.5 in", "thickness": "0.75 in",
                      "depth": "1.5 in"}, metadata_path=mj)
    meta = json.load(open(mj))
    check("re-declare same pair -> still ONE joint (deduped)", len(meta["joints"]) == 1)
    check("re-declare updated dims in place", meta["joints"][0]["width"] == "2.5 in")

    # A genuinely different joint (different type) -> appended.
    jr.declare_joint({"type": "pegged_tenon", "tenon": "Rail_F", "mortise": "Leg_FL"},
                     metadata_path=mj)
    meta = json.load(open(mj))
    check("different type same pair -> second joint appended", len(meta["joints"]) == 2)

print("\n%d/%d cases passed" % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
