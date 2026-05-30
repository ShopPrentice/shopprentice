"""Offline test of validate_design's replication advisory (no Fusion needed).

Run: python3 tests/test_replication_check.py

Stubs adsk + primitives so the module imports, then exercises the pure detection
logic: congruence grouping, the mirror/pattern suppression (incl. proxy→native
token matching), the _norep opt-out, and prefix exclusion. The only thing NOT
covered here is whether MirrorFeature/PatternFeature actually expose `.bodies` in
Fusion — that needs a live check before relying on the suppression.
"""
import os, sys, types, importlib.util

# ── stub adsk ──
adsk = types.ModuleType("adsk")
core = types.ModuleType("adsk.core")
fusion = types.ModuleType("adsk.fusion")
class _A:
    def log(self, *a, **k): pass
core.Application = types.SimpleNamespace(get=staticmethod(lambda: _A()))
adsk.core, adsk.fusion = core, fusion
for n, m in (("adsk", adsk), ("adsk.core", core), ("adsk.fusion", fusion)):
    sys.modules[n] = m

# ── stub primitives (module runs registration at import) ──
class _Chain:
    def __getattr__(self, _n):
        return lambda *a, **k: self
def _mk(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m
_mk("primitives")
_mk("primitives.tool", Tool=types.SimpleNamespace(create_simple=lambda *a, **k: _Chain()))
_mk("primitives.item", Item=types.SimpleNamespace(create_tool_item=lambda *a, **k: object()))
_mk("primitives.registry", register=lambda *a, **k: None)

_PATH = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "addin", "tools", "validate_design.py"))
spec = importlib.util.spec_from_file_location("validate_design", _PATH)
vd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vd)


# ── geometry stubs ──
class Faces:
    def __init__(self, n): self.count = n
class Body:
    def __init__(self, vol, nf, token, native=None):
        self.volume = vol; self.faces = Faces(nf)
        self.entityToken = token; self.nativeObject = native
class _Coll:
    def __init__(self, items): self._i = items
    @property
    def count(self): return len(self._i)
    def item(self, i): return self._i[i]
class Feat:
    def __init__(self, ot, bodies): self.objectType = ot; self.bodies = _Coll(bodies)
class Design:
    def __init__(self, feats):
        self.timeline = _Coll([types.SimpleNamespace(entity=f) for f in feats])

def entry(name, token, vol=12.0, nf=6, dims=(2.0, 2.0, 3.0), native=None):
    return {"name": name, "min": [0, 0, 0],
            "max": [dims[0], dims[1], dims[2]],
            "body": Body(vol, nf, token, native)}

def run(name, design, bodies, expect_flag):
    res = vd._check_replication(design, bodies, ["DM_"])
    flagged = len(res["groups"]) > 0
    ok = flagged == expect_flag
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {len(res['groups'])} group(s) "
          f"(expected {'flag' if expect_flag else 'none'})")
    for g in res["groups"]:
        print(f"        - {'/'.join(g['names'])} → {g['suggest']}")
    return ok

R = []

# 1. 4 congruent legs, NO mirror/pattern → flagged
legs = [entry(f"leg_{s}", f"t{i}") for i, s in enumerate(["FL", "FR", "BL", "BR"])]
R.append(run("4 congruent legs built independently", Design([]), legs, True))

# 2. 4 congruent legs, 3 from a Rectangular Pattern → NOT flagged (proxy→native match)
nb = [Body(12.0, 6, f"n{i}") for i in range(1, 4)]          # native pattern outputs
patt = Feat("adsk::fusion::RectangularPatternFeature", nb)
g2 = [entry("leg_FL", "t0")] + [entry(f"leg_{s}", f"px{i}", native=nb[i])
                                for i, s in enumerate(["FR", "BL", "BR"])]
R.append(run("4 legs, 3 are pattern outputs", Design([patt]), g2, False))

# 3. opt-out: a member tagged _norep → group drops below min → not flagged
g3 = [entry("tail_norep_A", "a"), entry("tail_norep_B", "b")]
R.append(run("congruent but _norep opt-out", Design([]), g3, False))

# 4. two genuinely different shapes → not flagged
g4 = [entry("leg", "x", vol=12.0, nf=6, dims=(2, 2, 3)),
      entry("stretcher", "y", vol=12.0, nf=8, dims=(1, 1, 12))]  # diff dims+faces
R.append(run("same volume, different shape", Design([]), g4, False))

# 5. joinery void prefix excluded
g5 = [entry("DM_void_1", "v1"), entry("DM_void_2", "v2")]
R.append(run("DM_ joinery voids excluded", Design([]), g5, False))

# 6. mixed: 2 congruent legs independent + 1 stretcher → only legs flagged
g6 = [entry("leg_L", "L"), entry("leg_R", "Rr"),
      entry("stretcher", "S", vol=20.0, nf=6, dims=(1, 1, 20))]
res6 = vd._check_replication(Design([]), g6, ["DM_"])
ok6 = len(res6["groups"]) == 1 and res6["groups"][0]["count"] == 2
print(f"[{'PASS' if ok6 else 'FAIL'}] mixed: only the 2 legs flagged "
      f"({len(res6['groups'])} group(s))")
R.append(ok6)

print(f"\n{sum(R)}/{len(R)} cases passed")
sys.exit(0 if all(R) else 1)
