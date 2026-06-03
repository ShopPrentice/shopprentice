"""Offline test of validate_design's detail-after-replicate advisory.

Pure Python (no Fusion). Run: python3 tests/test_detail_after_replicate.py

Stubs adsk + primitives so the module imports, then drives
`_check_detail_after_replicate` with fake sketches. sketchToModelSpace is the
identity here, so each profile's centroid IS its world centroid.

Verifies the key discrimination: congruent sketches that are 1-axis-symmetric
(mirror/pattern copies) are flagged; congruent-but-not (e.g. the two
perpendicular taper faces of ONE leg) are not.
"""
import os, sys, types, importlib.util

adsk = types.ModuleType("adsk")
core = types.ModuleType("adsk.core")
fusion = types.ModuleType("adsk.fusion")
class _A:
    def log(self, *a, **k): pass
core.Application = types.SimpleNamespace(get=staticmethod(lambda: _A()))
adsk.core, adsk.fusion = core, fusion
for _n, _m in (("adsk", adsk), ("adsk.core", core), ("adsk.fusion", fusion)):
    sys.modules[_n] = _m
class _Chain:
    def __getattr__(self, _n): return lambda *a, **k: self
def _mk(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items(): setattr(m, k, v)
    sys.modules[name] = m
_mk("primitives")
_mk("primitives.tool", Tool=types.SimpleNamespace(create_simple=lambda *a, **k: _Chain()))
_mk("primitives.item", Item=types.SimpleNamespace(create_tool_item=lambda *a, **k: object()))
_mk("primitives.registry", register=lambda *a, **k: None)

_PATH = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "..", "addin", "tools", "validate_design.py"))
spec = importlib.util.spec_from_file_location("validate_design", _PATH)
vd = importlib.util.module_from_spec(spec); spec.loader.exec_module(vd)


class Pt:
    def __init__(self, x, y, z): self.x, self.y, self.z = x, y, z
class Coll:
    def __init__(self, items): self._i = items
    @property
    def count(self): return len(self._i)
    def item(self, i): return self._i[i]
class AP:
    def __init__(self, area, ctr): self.area = area; self.centroid = ctr
class Loop:
    def __init__(self, ncurves): self.profileCurves = Coll([0] * ncurves)
class Profile:
    def __init__(self, area, ctr, ncurves):
        self._ap = AP(area, ctr); self.profileLoops = Coll([Loop(ncurves)])
    def areaProperties(self): return self._ap
class Sketch:
    def __init__(self, name, area, ctr, ncurves):
        self.name = name; self.profiles = Coll([Profile(area, Pt(*ctr), ncurves)])
    def sketchToModelSpace(self, p): return p          # identity
class Comp:
    def __init__(self, name, sketches): self.name = name; self.sketches = Coll(sketches)
class Root:
    def __init__(self, sketches=None):
        self.name = "root"; self.sketches = Coll(sketches or []); self.allOccurrences = Coll([])

def comp_root(sketches):
    # one component "Table" holding the sketches, hung under the root
    occ = types.SimpleNamespace(component=Comp("Table", sketches))
    r = Root(); r.allOccurrences = Coll([occ]); return r

def run(name, sketches, expect_flag):
    res = vd._check_detail_after_replicate(comp_root(sketches))
    flagged = len(res["groups"]) > 0
    ok = flagged == expect_flag
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {len(res['groups'])} group(s) "
          f"(expected {'flag' if expect_flag else 'none'})")
    for g in res["groups"]:
        print(f"        - {'/'.join(g['sketches'])}")
    return ok

R = []
TRI = dict(area=0.94, ncurves=3)   # a taper-triangle-ish signature

# 1. BAD taper: 4 congruent x-face sketches at mirror-symmetric leg positions
R.append(run("bad: per-leg taper (4 mirror-symmetric sketches)", [
    Sketch("Leg_FL_Tp_x", ctr=(3, 2, 12), **TRI),
    Sketch("Leg_FR_Tp_x", ctr=(57, 2, 12), **TRI),
    Sketch("Leg_BL_Tp_x", ctr=(3, 28, 12), **TRI),
    Sketch("Leg_BR_Tp_x", ctr=(57, 28, 12), **TRI),
], True))

# 2. GOOD taper: ONE leg, two PERPENDICULAR faces — congruent but not 1-axis
R.append(run("good: one leg, two perpendicular taper faces", [
    Sketch("Leg_FL_Tp_x", ctr=(3, 2, 12), **TRI),
    Sketch("Leg_FL_Tp_y", ctr=(2, 3, 12), **TRI),
], False))

# 3. Tenons: two mirror-symmetric tenon sketches -> flagged (real opportunity)
R.append(run("tenons: mirror pair flagged", [
    Sketch("Ten_FL_Sk", ctr=(10, 1.5, 27), area=1.5, ncurves=4),
    Sketch("Ten_FR_Sk", ctr=(50, 1.5, 27), area=1.5, ncurves=4),
], True))

# 4. _norep opt-out: skipped
R.append(run("opt-out: _norep skips", [
    Sketch("Foo_norep_a", ctr=(3, 2, 12), **TRI),
    Sketch("Foo_norep_b", ctr=(57, 2, 12), **TRI),
], False))

# 5. Different signatures -> not grouped
R.append(run("different shapes: not grouped", [
    Sketch("A", ctr=(3, 2, 12), area=1.0, ncurves=4),
    Sketch("B", ctr=(57, 2, 12), area=9.0, ncurves=4),
], False))

# 6. Pattern (translation along one axis) -> flagged
R.append(run("pattern: 3 in a row along X", [
    Sketch("Slat0", ctr=(10, 5, 0), area=2.0, ncurves=4),
    Sketch("Slat1", ctr=(20, 5, 0), area=2.0, ncurves=4),
    Sketch("Slat2", ctr=(30, 5, 0), area=2.0, ncurves=4),
], True))

print(f"\n{sum(R)}/{len(R)} cases passed")
sys.exit(0 if all(R) else 1)
