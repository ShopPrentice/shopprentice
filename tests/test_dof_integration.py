"""Integration test: run the REAL wired sketch helpers against a stubbed Fusion
API and confirm the Tier 1 guard balances on correct geometry.

Pure Python — no Fusion. Run: python3 tests/test_dof_integration.py

Why this exists: the unit test (test_dof_guard.py) checks the DOF *arithmetic*.
This checks that the feed calls actually wired into sketch.py / sketch_slot.py
MATCH the geometry those helpers build — by executing them with the default
(raising) guard. A miscount (e.g. add_hv(4) where only 2 are added) would make a
*correct* sketch report DOF != 0 and raise here, failing the test. That false-
alarm-on-correct-geometry is the single regression Tier 1 must never introduce.

Covers sketch_rect (origin) and sketch_slot (both orientations) — the helpers
that need no modelToSketchSpace/anchoring stubs. The *_model and anchored paths
share the identical feed pattern, validated arithmetically in test_dof_guard.py
(acct_rect_anchored, acct_slot).
"""
import os, sys, types, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
SPDIR = os.path.normpath(os.path.join(HERE, "..", "helpers", "sp"))

# Default-raise guard: an imbalance on correct geometry must blow up the test.
os.environ.pop("SP_DOF_GUARD", None)


# ── stub adsk ───────────────────────────────────────────────────────────────
class Point3D:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z

    @staticmethod
    def create(x, y, z):
        return Point3D(x, y, z)


core = types.ModuleType("adsk.core")
core.Point3D = Point3D
core.ObjectCollection = types.SimpleNamespace(create=lambda: [])
fusion = types.ModuleType("adsk.fusion")
fusion.DimensionOrientations = types.SimpleNamespace(
    HorizontalDimensionOrientation="H", VerticalDimensionOrientation="V")
adsk = types.ModuleType("adsk")
adsk.core, adsk.fusion = core, fusion
sys.modules.update({"adsk": adsk, "adsk.core": core, "adsk.fusion": fusion})


# ── synthetic `sp` package: fake _util, real dof/sketch/sketch_slot ──────────
sp = types.ModuleType("sp")
sp.__path__ = [SPDIR]
sys.modules["sp"] = sp

util = types.ModuleType("sp._util")
util._make_ev = lambda: (lambda e: 1.0)
sys.modules["sp._util"] = util


def _load(modname, filename):
    path = os.path.join(SPDIR, filename)
    spec = importlib.util.spec_from_file_location("sp." + modname, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules["sp." + modname] = m
    spec.loader.exec_module(m)
    setattr(sp, modname, m)
    return m


dof_mod = _load("dof", "dof.py")
sketch = _load("sketch", "sketch.py")
sketch_slot = _load("sketch_slot", "sketch_slot.py")
DofError = dof_mod.DofError


# ── minimal Fusion geometry stub ────────────────────────────────────────────
class SP:
    def __init__(self, x=0.0, y=0.0):
        self.geometry = Point3D(x, y, 0)
        self.isFixed = False


class Line:
    def __init__(self, p1, p2):
        self.startSketchPoint, self.endSketchPoint = p1, p2


class Arc:
    def __init__(self, center, start):
        self.centerSketchPoint = center
        self.startSketchPoint = start
        self.endSketchPoint = SP()


def _asSP(p):
    return p if isinstance(p, SP) else SP(p.x, p.y)


class Lines:
    def addTwoPointRectangle(self, p1, p2):
        c = [SP(p1.x, p1.y), SP(p2.x, p1.y), SP(p2.x, p2.y), SP(p1.x, p2.y)]
        return [Line(c[0], c[1]), Line(c[1], c[2]),
                Line(c[2], c[3]), Line(c[3], c[0])]

    def addByTwoPoints(self, p1, p2):
        return Line(_asSP(p1), _asSP(p2))


class Arcs:
    def addByCenterStartSweep(self, center, start, sweep):
        return Arc(_asSP(center), _asSP(start))


class Curves:
    def __init__(self):
        self.sketchLines = Lines()
        self.sketchArcs = Arcs()


class GC:
    def __getattr__(self, _n):
        return lambda *a, **k: None


class _Param:
    expression = None


class _Dim:
    def __init__(self):
        self.parameter = _Param()


class Dims:
    def addDistanceDimension(self, *a, **k):
        return _Dim()

    def addRadialDimension(self, *a, **k):
        return _Dim()


class Profiles:
    count = 1

    def item(self, _i):
        return "profile"


class Sketch:
    def __init__(self):
        self.name = ""
        self.sketchCurves = Curves()
        self.geometricConstraints = GC()
        self.sketchDimensions = Dims()
        self.profiles = Profiles()
        self.originPoint = SP()

    def modelToSketchSpace(self, p):
        return p


class Comp:
    class _Sketches:
        def add(self, _plane):
            return Sketch()
    def __init__(self):
        self.sketches = Comp._Sketches()


# ── run the real helpers ────────────────────────────────────────────────────
R = []


def case(name, fn):
    try:
        fn()
        ok = True
    except DofError as e:
        ok = False
        print(f"        ! guard false-alarmed on correct geometry: {e}")
    except Exception as e:
        ok = False
        print(f"        ! unexpected error: {e!r}")
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    R.append(ok)


ev = lambda e: 2.0   # any numeric evaluator; geometry values are irrelevant here

case("sketch_rect (origin) balances under the raising guard",
     lambda: sketch.sketch_rect(Comp(), None, "x0", "y0", "w", "h",
                                name="Rect", ev=ev))

case("sketch_slot vertical balances under the raising guard",
     lambda: sketch_slot.sketch_slot(Comp(), None, "cx", "cy", "lg", "sh",
                                     vertical=True, name="SlotV", ev=ev))

case("sketch_slot horizontal balances under the raising guard",
     lambda: sketch_slot.sketch_slot(Comp(), None, "cx", "cy", "lg", "sh",
                                     vertical=False, name="SlotH", ev=ev))


# Negative control: prove the guard WOULD fire end-to-end if a helper were
# under-fed. We can't under-build a correct helper, so monkeypatch its tracker
# factory to return a tracker pre-loaded with an extra free point (simulating a
# dropped dimension) and confirm the real sketch_rect run raises.
def _guard_fires_when_underfed():
    orig = sketch.default_tracker

    def underfed(name=None, log=print):
        t = orig(name, log=log)
        t.add_point(1)              # phantom free point the helper won't pin → DOF>0
        return t

    sketch.default_tracker = underfed
    try:
        raised = False
        try:
            sketch.sketch_rect(Comp(), None, "x0", "y0", "w", "h",
                               name="RectBad", ev=ev)
        except DofError:
            raised = True
        if not raised:
            raise AssertionError("guard did not fire on an under-fed sketch")
    finally:
        sketch.default_tracker = orig


case("guard fires end-to-end when a helper is under-constrained",
     _guard_fires_when_underfed)


print(f"\n{sum(R)}/{len(R)} cases passed")
sys.exit(0 if all(R) else 1)
