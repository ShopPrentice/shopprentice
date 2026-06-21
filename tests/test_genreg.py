"""Offline test of the Tier 2 generator registry (helpers/sp/genreg.py).

Pure Python — no Fusion. Run: python3 tests/test_genreg.py

Covers the bookkeeping that lets a certified generator be trusted at build time:
source-hashing (edit-sensitive, indent-insensitive), the register/REGISTRY path,
manifest load/record/save + certification lookup (hit / miss / wrong-branch /
edited-source), and sketch attribute stamp/read round-trip against a fake sketch.
"""
import os, sys, json, tempfile, importlib.util

_GR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "helpers", "sp", "genreg.py"))
spec = importlib.util.spec_from_file_location("genreg", _GR)
genreg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(genreg)


R = []


def case(name, fn):
    try:
        ok = bool(fn())
    except Exception as e:
        ok = False
        print(f"        ! unexpected exception: {e!r}")
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    R.append(ok)


# ── source_hash ─────────────────────────────────────────────────────────────

def same_logic(x):
    y = x + 1
    return y


class _Nested:
    # Byte-identical body to module-level same_logic, just deeper indentation —
    # mimics promoting base_arch_cut from a nested local fn to a module function.
    def same_logic(x):
        y = x + 1
        return y


def gen_a_commented(x):
    y = x + 1  # an added comment changes the hash
    return y


case("source_hash is deterministic",
     lambda: genreg.source_hash(same_logic) == genreg.source_hash(same_logic))

case("source_hash ignores indentation (nested vs module-level, same body)",
     lambda: genreg.source_hash(same_logic)
     == genreg.source_hash(_Nested.same_logic))

case("source_hash changes when a comment/code is added",
     lambda: genreg.source_hash(same_logic) != genreg.source_hash(gen_a_commented))

case("source_hash is a 64-char hex sha256",
     lambda: len(genreg.source_hash(same_logic)) == 64
     and all(c in "0123456789abcdef" for c in genreg.source_hash(same_logic)))


# ── register / REGISTRY ─────────────────────────────────────────────────────

@genreg.register("demo_cut",
                 contract="closed free-spline edge + N-line waste rail frame",
                 when_to_use="one continuous curve across members",
                 branches=["center-shared", "center-pair"],
                 range_guards=["span > 0", "endpoints distinct"])
def demo_cut(span):
    return span * 2


case("register populates REGISTRY with a GeneratorSpec",
     lambda: "demo_cut" in genreg.REGISTRY
     and genreg.spec_for("demo_cut").contract.startswith("closed free-spline"))

case("register tags the function with _sp_generator + _sp_spec",
     lambda: demo_cut._sp_generator == "demo_cut"
     and demo_cut._sp_spec.source_hash == genreg.source_hash(demo_cut))

case("spec.key is name@hash",
     lambda: genreg.spec_for("demo_cut").key
     == "demo_cut@" + genreg.source_hash(demo_cut))

case("decorated generator still callable normally",
     lambda: demo_cut(21) == 42)


# ── manifest: load / record / save / is_certified ───────────────────────────

def _manifest_roundtrip():
    spec = genreg.spec_for("demo_cut")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "generators", "certified.json")
        # Missing file → empty manifest, nothing certified.
        assert genreg.load_manifest(path) == {}
        assert not genreg.is_certified(spec.name, spec.source_hash, path=path)
        # Record a pass for one branch and save.
        m = genreg.record(spec, branches=["center-shared"],
                          fusion_version="2.0.42", certified_at="2026-06-14",
                          path=path)
        genreg.save_manifest(m, path)
        # Reload from disk and check the hit.
        m2 = genreg.load_manifest(path)
        assert spec.key in m2 and m2[spec.key]["certified"] is True
        assert genreg.is_certified(spec.name, spec.source_hash, manifest=m2)
        # Branch awareness: certified branch hits, uncertified branch misses.
        assert genreg.is_certified(spec.name, spec.source_hash,
                                   branch="center-shared", manifest=m2)
        assert not genreg.is_certified(spec.name, spec.source_hash,
                                       branch="center-pair", manifest=m2)
        # Edited source (different hash) → not certified (fail-closed).
        assert not genreg.is_certified(spec.name, "deadbeef" * 8, manifest=m2)
        return True

case("manifest record → save → reload → is_certified round-trips",
     _manifest_roundtrip)

def _is_certified_stamp():
    spec = genreg.spec_for("demo_cut")
    m = genreg.record(spec, ["center-shared"], "2.0.42", "2026-06-14",
                      manifest={})
    good = f"{spec.name}@{spec.source_hash}"
    return (genreg.is_certified_stamp(good, manifest=m)
            and not genreg.is_certified_stamp("demo_cut@stale", manifest=m)
            and not genreg.is_certified_stamp(None, manifest=m)
            and not genreg.is_certified_stamp("malformed-no-at", manifest=m))

case("is_certified_stamp keys off a 'name@hash' sketch stamp",
     _is_certified_stamp)


# ── attribution: stamp / read_stamp against a fake sketch ────────────────────

class FakeAttr:
    def __init__(self, value):
        self.value = value


class FakeAttrs:
    def __init__(self):
        self._d = {}

    def add(self, group, key, value):
        self._d[(group, key)] = FakeAttr(value)

    def itemByName(self, group, key):
        return self._d.get((group, key))


class FakeSketch:
    def __init__(self):
        self.attributes = FakeAttrs()


def _stamp_roundtrip():
    sk = FakeSketch()
    written = genreg.stamp(sk, "demo_cut")          # uses registered spec hash
    read = genreg.read_stamp(sk)
    expect = f"demo_cut@{genreg.spec_for('demo_cut').source_hash}"
    return written == expect and read == expect

case("stamp(sk) writes 'name@hash' and read_stamp recovers it",
     _stamp_roundtrip)

case("read_stamp returns None on an unstamped sketch",
     lambda: genreg.read_stamp(FakeSketch()) is None)

case("stamp returns None for an unregistered name (no hash known)",
     lambda: genreg.stamp(FakeSketch(), "not_registered") is None)


print(f"\n{sum(R)}/{len(R)} cases passed")
sys.exit(0 if all(R) else 1)
