"""Offline test of the Tier 2 certified-skip in deps._check_sketch_anchoring.

Pure Python — no Fusion. Run: python3 tests/test_deps_certified.py

Proves the fast path: a spline sketch that the SOLVER would judge
under-constrained is TRUSTED (no issue, solver pin/resolve skipped) iff it carries
a certified+unchanged generator stamp — and otherwise falls back to the solver
exactly as before. The solver call is monkeypatched with a recorder so we can
assert it was (or was not) invoked.
"""
import os, sys, types, importlib.util

for m in ("adsk", "adsk.core", "adsk.fusion"):
    sys.modules[m] = types.ModuleType(m)

HELP = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "helpers", "sp"))


def _load(modname, filename):
    spec = importlib.util.spec_from_file_location(modname, os.path.join(HELP, filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod          # so deps.py's `import genreg` fallback binds it
    spec.loader.exec_module(mod)
    return mod


genreg = _load("genreg", "genreg.py")
deps = _load("deps", "deps.py")
assert deps._genreg is genreg, "deps did not bind the real genreg"


# ── minimal Fusion sketch stub (with attributes for the stamp) ───────────────
class Pt:
    def __init__(self, fixed=False):
        self.isFixed = fixed


class Coll:
    def __init__(self, items):
        self._items = list(items)

    @property
    def count(self):
        return len(self._items)

    def item(self, i):
        return self._items[i]


class Curve:
    def __init__(self, kind="Line", isRef=False, isCon=False, resolved=True,
                 spline=False, n_interior=2):
        self.objectType = f"adsk::fusion::Sketch{kind}"
        self.isReference = isRef
        self.isConstruction = isCon
        self.isFixed = False
        self.referencedEntity = object() if resolved else None
        self.startSketchPoint = Pt()
        self.endSketchPoint = Pt()
        if spline:
            self.fitPoints = Coll([Pt()] + [Pt() for _ in range(n_interior)] + [Pt()])


class FakeAttr:
    def __init__(self, value):
        self.value = value


class FakeAttrs:
    def __init__(self, stamp=None):
        self._d = {}
        if stamp is not None:
            self._d[(genreg.STAMP_GROUP, genreg.STAMP_KEY)] = FakeAttr(stamp)

    def add(self, g, k, v):
        self._d[(g, k)] = FakeAttr(v)

    def itemByName(self, g, k):
        return self._d.get((g, k))


class Sketch:
    def __init__(self, name, curves, stamp=None):
        self.name = name
        self.sketchCurves = Coll(curves)
        self.originPoint = Pt()
        self.attributes = FakeAttrs(stamp)
        # Force the expensive path: not fully constrained as-is.
        self.isFullyConstrained = False


class Comp:
    def __init__(self, sketches):
        self.sketches = Coll(sketches)


def _spline_sketch(stamp=None):
    # anchored (a ref curve that resolves) + a drawn spline, no Fix.
    return Sketch("Sculpt", [Curve(isRef=True), Curve("FittedSpline", spline=True)],
                  stamp=stamp)


# Register a fake generator so we have a real name@hash + manifest entry.
@genreg.register("sculpt_cut", contract="spline edge + waste frame",
                 when_to_use="curve across members", branches=["center-shared"])
def sculpt_cut():
    return None

SPEC = genreg.spec_for("sculpt_cut")
GOOD_STAMP = SPEC.key                         # name@<current hash>
STALE_STAMP = f"sculpt_cut@{'0' * 64}"        # edited source → wrong hash
MANIFEST = genreg.record(SPEC, ["center-shared"], "2.0.x", "2026-06-14", manifest={})


R = []


def run(name, sketch, manifest, solver_verdict, expect_issue, expect_solver_called):
    """Run the anchoring check on one sketch with _fc_modulo monkeypatched."""
    calls = {"n": 0}

    def _recorder(sk):
        calls["n"] += 1
        return solver_verdict

    orig = deps._fc_modulo_spline_interiors
    deps._fc_modulo_spline_interiors = _recorder
    try:
        issues = []
        deps._check_sketch_anchoring(Comp([sketch]), "C", False, issues, manifest)
    finally:
        deps._fc_modulo_spline_interiors = orig

    got_issue = len(issues) > 0
    got_called = calls["n"] > 0
    ok = (got_issue == expect_issue) and (got_called == expect_solver_called)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: "
          f"issue={got_issue} (exp {expect_issue}), "
          f"solver_called={got_called} (exp {expect_solver_called})")
    for it in issues:
        print(f"        - {it}")
    R.append(ok)


# Certified + unchanged → trusted: NO issue, solver NOT called.
run("certified stamp → trusted, solver skipped",
    _spline_sketch(GOOD_STAMP), MANIFEST,
    solver_verdict=False, expect_issue=False, expect_solver_called=False)

# Same sketch but NO stamp → solver runs; verdict False → issue.
run("unstamped → solver runs (verdict False → issue)",
    _spline_sketch(None), MANIFEST,
    solver_verdict=False, expect_issue=True, expect_solver_called=True)

# Edited generator (stale hash) → not certified → solver runs.
run("stale hash → not certified → solver runs",
    _spline_sketch(STALE_STAMP), MANIFEST,
    solver_verdict=False, expect_issue=True, expect_solver_called=True)

# Certified stamp but NO manifest loaded → fail-closed → solver runs.
run("certified stamp but empty manifest → solver runs (fail-closed)",
    _spline_sketch(GOOD_STAMP), {},
    solver_verdict=False, expect_issue=True, expect_solver_called=True)

# Unstamped but solver PASSES (verdict True) → no issue, solver was called.
run("unstamped, solver passes → no issue",
    _spline_sketch(None), MANIFEST,
    solver_verdict=True, expect_issue=False, expect_solver_called=True)


print(f"\n{sum(R)}/{len(R)} cases passed")
sys.exit(0 if all(R) else 1)
