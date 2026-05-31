"""Offline test of deps.py geometry-loop advisory. Pure Python — no Fusion.

Run: python3 tests/test_deps_loops.py   (also pytest-discoverable)

Exercises _geometry_loop_findings: a Python for/while loop that CREATES geometry
should be flagged (use a Rectangular Pattern / Mirror instead); a loop that
patterns/mirrors, or does no geometry, should not be.
"""
import os, sys, types, tempfile, importlib.util

for m in ("adsk", "adsk.core", "adsk.fusion"):
    sys.modules[m] = types.ModuleType(m)

_DEPS = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "helpers", "sp", "deps.py"))
spec = importlib.util.spec_from_file_location("deps", _DEPS)
deps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deps)


def _find(src):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(src); path = f.name
    try:
        return deps._geometry_loop_findings(path)
    finally:
        os.unlink(path)


CASES = [
    # (name, source, expect_flagged)
    ("for-loop of CUTs (dog holes)", """
def run(ctx):
    for j in range(6):
        sp.ext_op(top_c, prof, "t", CUT, top_front, "Dog_%d" % j, flip=False)
""", True),
    ("while-loop creating sketches", """
def run(ctx):
    j = 0
    while j < n:
        sk = top_c.sketches.add(pl)
        j += 1
""", True),
    ("for-loop of cyl_ helper", """
def run(ctx):
    for k in range(4):
        cyl_y(cx, z, ya, dia, ylen, "Hole_%d" % k)
""", True),
    ("loop that patterns — NOT flagged", """
def run(ctx):
    bodies = []
    for k in range(n):
        bodies.append(make_template(k))
    sp.body_pattern(comp, seed, axis, "n", "sp", "Pat")
""", False),
    ("loop with no geometry — NOT flagged", """
def run(ctx):
    for b in comp.bRepBodies:
        b.name = classify(b)
""", False),
    ("syntax error / missing — no crash", "def run(ctx): this is not python", False),
]


def test_geometry_loop_findings():
    ok = True
    for name, src, expect in CASES:
        flagged = len(_find(src)) > 0
        passed = (flagged == expect)
        ok = ok and passed
        print(f"  {'PASS' if passed else 'FAIL'}  {name} "
              f"(flagged={flagged}, expect={expect})")
    assert deps._geometry_loop_findings(None) == []      # None path → no crash
    assert deps._geometry_loop_findings("/no/such.py") == []
    assert ok, "geometry-loop detector cases failed"


if __name__ == "__main__":
    try:
        test_geometry_loop_findings()
        print("\nall geometry-loop cases passed")
        sys.exit(0)
    except AssertionError as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)
