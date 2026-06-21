"""End-to-end consistency check for the committed certification manifest.

Pure Python — no Fusion. Run: python3 tests/test_certified_manifest.py

Loads the REAL generators (their @register hashes) and the REAL committed
helpers/sp/generators/certified.json, and asserts the chain is consistent:
the manifest is keyed by the generator's CURRENT source hash, so a sketch stamped
at build time would be trusted by deps.

Doubles as a STALENESS ALARM: if generators.py is edited without re-certifying,
its hash changes, the manifest key no longer matches, and this test FAILS —
telling you to re-run the Fusion certification (tests/certify_base_arch_cut.py)
and tools/record_certification.py. That is the intended safety property: an edited
generator is never silently trusted on a stale certification.
"""
import os, sys, types, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
SPDIR = os.path.normpath(os.path.join(HERE, "..", "helpers", "sp"))


# Minimal adsk + synthetic sp package so the real generators register.
class _P:
    def __init__(self, x, y, z): self.x, self.y, self.z = x, y, z
    @staticmethod
    def create(x, y, z): return _P(x, y, z)


core = types.ModuleType("adsk.core")
core.Point3D = _P
core.ObjectCollection = types.SimpleNamespace(create=lambda: [])
fusion = types.ModuleType("adsk.fusion")
fusion.DimensionOrientations = types.SimpleNamespace(
    HorizontalDimensionOrientation="H", VerticalDimensionOrientation="V")
adsk = types.ModuleType("adsk")
adsk.core, adsk.fusion = core, fusion
sys.modules.update({"adsk": adsk, "adsk.core": core, "adsk.fusion": fusion})

sp = types.ModuleType("sp")
sp.__path__ = [SPDIR]
sys.modules["sp"] = sp
util = types.ModuleType("sp._util")
util._make_ev = lambda: (lambda e: 1.0)
sys.modules["sp._util"] = util


def _load(name):
    spec = importlib.util.spec_from_file_location(
        "sp." + name, os.path.join(SPDIR, name + ".py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["sp." + name] = m
    spec.loader.exec_module(m)
    setattr(sp, name, m)
    return m


genreg = _load("genreg")
_load("dof")
_load("sketch")
_load("generators")     # registers base_arch_cut


class FakeAttrs:
    def __init__(self): self._d = {}
    def add(self, g, k, v): self._d[(g, k)] = types.SimpleNamespace(value=v)
    def itemByName(self, g, k): return self._d.get((g, k))


class FakeSketch:
    def __init__(self): self.attributes = FakeAttrs()


R = []


def case(name, fn):
    try:
        ok = bool(fn())
    except Exception as e:
        ok = False
        print(f"        ! {e!r}")
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    R.append(ok)


MANIFEST = genreg.load_manifest()          # the committed certified.json
EXPECT = ["base_arch_cut", "foot_flare_cut"]

case("certified.json exists and is non-empty",
     lambda: bool(MANIFEST))

for gname in EXPECT:
    spec = genreg.spec_for(gname)

    case(f"{gname}: registered",
         lambda spec=spec: spec is not None)

    case(f"{gname}: committed manifest matches the CURRENT source hash "
         f"(else re-certify)",
         lambda gname=gname, spec=spec:
             genreg.is_certified(gname, spec.source_hash, manifest=MANIFEST))

    case(f"{gname}: every registered topology branch is certified",
         lambda gname=gname, spec=spec: all(
             genreg.is_certified(gname, spec.source_hash, branch=b, manifest=MANIFEST)
             for b in spec.branches))

    def _stamp_trusted(gname=gname):
        sk = FakeSketch()
        genreg.stamp(sk, gname)                    # what the generator writes
        stamp = genreg.read_stamp(sk)              # what deps reads
        return genreg.is_certified_stamp(stamp, manifest=MANIFEST)

    case(f"{gname}: a freshly-stamped sketch is trusted by the manifest",
         _stamp_trusted)


print(f"\n{sum(R)}/{len(R)} cases passed")
sys.exit(0 if all(R) else 1)
