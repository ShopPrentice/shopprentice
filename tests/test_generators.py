"""Offline test of helpers/sp/generators.py (the promoted base_arch_cut).

Pure Python — no Fusion. Run: python3 tests/test_generators.py

Runs the REAL base_arch_cut generator against a spline-capable Fusion stub, under
the default (raising) DOF guard, for BOTH topology branches (center-shared and
center-pair). A pass proves the promoted generator's constraint accounting nets to
0 (modulo spline interiors) and that it stamps its sketch. Geometry/solver
correctness is certified separately in Fusion (tests/certify_base_arch_cut.py).
"""
import os, sys, types, importlib.util

os.environ.pop("SP_DOF_GUARD", None)   # default-raise: imbalance fails the test

HERE = os.path.dirname(os.path.abspath(__file__))
SPDIR = os.path.normpath(os.path.join(HERE, "..", "helpers", "sp"))


# ── stub adsk ───────────────────────────────────────────────────────────────
class Point3D:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z

    @staticmethod
    def create(x, y, z):
        return Point3D(x, y, z)


class _OC(list):
    def add(self, x):
        self.append(x)


core = types.ModuleType("adsk.core")
core.Point3D = Point3D
core.ObjectCollection = types.SimpleNamespace(create=lambda: _OC())
fusion = types.ModuleType("adsk.fusion")
fusion.DimensionOrientations = types.SimpleNamespace(
    HorizontalDimensionOrientation="H", VerticalDimensionOrientation="V")
adsk = types.ModuleType("adsk")
adsk.core, adsk.fusion = core, fusion
sys.modules.update({"adsk": adsk, "adsk.core": core, "adsk.fusion": fusion})


# ── synthetic sp package ────────────────────────────────────────────────────
sp = types.ModuleType("sp")
sp.__path__ = [SPDIR]
sys.modules["sp"] = sp
util = types.ModuleType("sp._util")
util._make_ev = lambda: (lambda e: 1.0)
sys.modules["sp._util"] = util


def _load(name, fn):
    spec = importlib.util.spec_from_file_location("sp." + name, os.path.join(SPDIR, fn))
    m = importlib.util.module_from_spec(spec)
    sys.modules["sp." + name] = m
    spec.loader.exec_module(m)
    setattr(sp, name, m)
    return m


dof_mod = _load("dof", "dof.py")
_load("genreg", "genreg.py")
_load("sketch", "sketch.py")
generators = _load("generators", "generators.py")
DofError = dof_mod.DofError


# ── Fusion geometry stub (lines + fitted spline + profiles + attributes) ─────
class SP:
    def __init__(self, x=0.0, y=0.0):
        self.geometry = Point3D(x, y, 0)


class Line:
    def __init__(self, p1, p2):
        self.startSketchPoint = p1 if isinstance(p1, SP) else SP(p1.x, p1.y)
        self.endSketchPoint = p2 if isinstance(p2, SP) else SP(p2.x, p2.y)
        self.isReference = False
        self.isConstruction = False


class Spline:
    def __init__(self, coll):
        self.startSketchPoint = SP(coll[0].x, coll[0].y)
        self.endSketchPoint = SP(coll[-1].x, coll[-1].y)
        self.isReference = False
        self.isConstruction = False


class _Splines:
    def __init__(self, owner):
        self._owner = owner

    def add(self, coll):
        sp = Spline(coll)
        self._owner._all.append(sp)
        return sp


class _Lines:
    def __init__(self, owner):
        self._owner = owner
        self._items = []

    def addByTwoPoints(self, p1, p2):
        ln = Line(p1, p2)
        self._items.append(ln)
        self._owner._all.append(ln)
        return ln

    @property
    def count(self):
        return len(self._items)

    def item(self, i):
        return self._items[i]


class Curves:
    """Aggregates all curves so sk.sketchCurves.count/.item work (the access
    pattern of the current refs_to_construction, which iterates every curve type
    — lines, arcs, splines — not just lines)."""
    def __init__(self):
        self._all = []
        self.sketchFittedSplines = _Splines(self)
        self.sketchLines = _Lines(self)

    @property
    def count(self):
        return len(self._all)

    def item(self, i):
        return self._all[i]


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


class _Prof:
    def areaProperties(self):
        return types.SimpleNamespace(area=1.0)


class Profiles:
    count = 1

    def item(self, _i):
        return _Prof()


class Attrs:
    def __init__(self):
        self.added = []

    def add(self, g, k, v):
        self.added.append((g, k, v))


class Sketch:
    def __init__(self):
        self.name = ""
        self.sketchCurves = Curves()
        self.geometricConstraints = GC()
        self.sketchDimensions = Dims()
        self.profiles = Profiles()
        self.originPoint = SP()
        self.attributes = Attrs()

    def modelToSketchSpace(self, p):
        return p           # identity — fine for the structural accounting


class Comp:
    class _Sketches:
        def add(self, _plane):
            return Sketch()
    def __init__(self):
        self.sketches = Comp._Sketches()


# ── run ─────────────────────────────────────────────────────────────────────
EV = {"span": 20.0, "ei": 3.0, "0 in": 0.0, "0.5 in": 1.27,
      "kick": 3.0, "height": 20.0, "plumb": 4.0, "waste": 6.0}
ev = lambda e: EV[e]

# center-shared: last half point on the centreline (u*2.54 ≈ span/2 = 10 → u≈3.937)
HALF_SHARED = [(1.0, 0.0), (2.0, 1.5), (3.937, 2.5)]
# center-pair: last half point left of centre (3.0*2.54 = 7.62 < 10)
HALF_PAIR = [(1.0, 0.0), (2.0, 1.5), (3.0, 2.5)]

R = []


def case(name, fn):
    try:
        fn()
        ok = True
    except DofError as e:
        ok = False
        print(f"        ! guard false-alarmed: {e}")
    except Exception as e:
        ok = False
        print(f"        ! unexpected: {e!r}")
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    R.append(ok)


def _run(half, branch_expect):
    sk, prof = generators.base_arch_cut(
        Comp(), None, "x", "span", half, "ei", off_axis_cm=-5.08,
        name="BaseArch", ev=ev)
    # mirror branch sanity
    _, branch = generators._mirror([(u * generators.IN, z) for (u, z) in half], 10.0)
    assert branch == branch_expect, f"branch {branch} != {branch_expect}"
    # stamped with name@hash
    assert sk.attributes.added, "sketch was not stamped"
    g, k, v = sk.attributes.added[0]
    assert v.startswith("base_arch_cut@"), v
    return sk, prof


case("base_arch_cut center-shared branch balances + stamps",
     lambda: _run(HALF_SHARED, "center-shared"))

case("base_arch_cut center-pair branch balances + stamps",
     lambda: _run(HALF_PAIR, "center-pair"))

case("base_arch_cut is registered with both topology branches",
     lambda: (lambda s: s is not None and set(s.branches)
              == {"center-shared", "center-pair"})(
                  sys.modules["sp.genreg"].spec_for("base_arch_cut")))


# foot_flare_cut: floor (-kick,0) → top (0, height-plumb), 3 free interiors.
FLARE_PTS = [(-3.0, 0.0), (-2.0, 4.0), (-1.0, 9.0), (-0.4, 13.0), (0.0, 16.0)]


def _run_flare(axis):
    sk, prof = generators.foot_flare_cut(
        Comp(), None, axis, FLARE_PTS, "kick", "height", "plumb",
        name="FootFlare", off_axis_cm=0.0, waste_expr="waste", ev=ev)
    assert sk.attributes.added, "sketch was not stamped"
    assert sk.attributes.added[0][2].startswith("foot_flare_cut@")
    return sk, prof

case("foot_flare_cut (axis y) balances + stamps", lambda: _run_flare("y"))
case("foot_flare_cut (axis x) balances + stamps", lambda: _run_flare("x"))

case("foot_flare_cut is registered (single 'default' branch)",
     lambda: (lambda s: s is not None and list(s.branches) == ["default"])(
         sys.modules["sp.genreg"].spec_for("foot_flare_cut")))


print(f"\n{sum(R)}/{len(R)} cases passed")
sys.exit(0 if all(R) else 1)
