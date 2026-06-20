"""Offline step 2 of generator certification: turn a Fusion verdict into a
manifest entry keyed by the generator's REAL source hash.

Flow:
  1. (Fusion) execute_script(sandbox=true) runs tests/certify_base_arch_cut.py,
     which writes the pass/fail verdict to /tmp/arch_cert.json.
  2. (here)   python3 tools/record_certification.py [verdict.json]
     imports the real helpers/sp/generators.py to recover each generator's
     source hash, and writes helpers/sp/generators/certified.json.

Keeping the hash computation here (not in the Fusion harness) guarantees the
manifest key matches the source deps.py will hash at build time — even though the
harness runs against an exec'd copy with a no-op register decorator.

Usage: python3 tools/record_certification.py [path-to-verdict-json]
       (default verdict path: /tmp/arch_cert.json)
"""
import os, sys, json, types, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
SPDIR = os.path.normpath(os.path.join(HERE, "..", "helpers", "sp"))

# Map verdict["generator"] → its source module file under helpers/sp.
GENERATOR_MODULES = {"base_arch_cut": "generators.py"}

CERTIFIED_AT = os.environ.get("SP_CERT_DATE", "2026-06-14")


def _stub_adsk():
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


def _synthetic_sp():
    sp = types.ModuleType("sp")
    sp.__path__ = [SPDIR]
    sys.modules["sp"] = sp
    util = types.ModuleType("sp._util")
    util._make_ev = lambda: (lambda e: 1.0)
    sys.modules["sp._util"] = util

    def load(name):
        spec = importlib.util.spec_from_file_location(
            "sp." + name, os.path.join(SPDIR, name + ".py"))
        m = importlib.util.module_from_spec(spec)
        sys.modules["sp." + name] = m
        spec.loader.exec_module(m)
        setattr(sp, name, m)
        return m

    genreg = load("genreg")
    load("dof")
    load("sketch")
    # Loading a generator module registers its generators in genreg.REGISTRY.
    for mod in set(GENERATOR_MODULES.values()):
        load(mod[:-3])
    return genreg


def main():
    verdict_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/arch_cert.json"
    with open(verdict_path) as f:
        verdict = json.load(f)

    _stub_adsk()
    genreg = _synthetic_sp()

    name = verdict["generator"]
    spec = genreg.spec_for(name)
    if spec is None:
        sys.exit(f"generator {name!r} is not registered — did its module load?")

    certified_branches = [b for b, r in verdict["branches"].items()
                          if r.get("certified")]
    if not certified_branches:
        sys.exit("no certified branches in the verdict; refusing to record")
    if set(certified_branches) != set(spec.branches):
        print(f"  WARN  certified {certified_branches} != registered "
              f"{list(spec.branches)} — recording only the certified set")

    manifest = genreg.record(spec, certified_branches,
                             verdict.get("fusion_version", "?"), CERTIFIED_AT)
    path = genreg.save_manifest(manifest)
    print(f"  OK  recorded {spec.key}")
    print(f"      branches: {certified_branches}")
    print(f"      manifest: {path}")


if __name__ == "__main__":
    main()
