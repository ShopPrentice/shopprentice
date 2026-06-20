"""Tier 2 — certified generator registry (pure Python, no Fusion).

A **generator** is a parameterized function that emits a sketch (or small cut)
with a *fixed, or finitely-branched, constraint topology*: the data (coordinates)
and dimensions vary per call, but which points/lines/constraints get added, and in
what order, does not. Because the topology is stable, its full-constraint property
can be certified against Fusion's solver **once** (offline, per source version) and
then **trusted at build time** — skipping the ~seconds-each pin/resolve the deps
check otherwise pays per sculpted-spline sketch.

This module is the bookkeeping spine of that scheme. It is deliberately
Fusion-free (no ``adsk`` import) so it can be unit-tested and so the build-time
lookup is cheap:

  * ``source_hash(fn)``  — sha256 of a generator's source. Editing the function
    (even a comment) changes the hash, which **auto-invalidates** its certification
    — you can never trust a stale recipe.
  * ``register(...)``    — decorator that records a :class:`GeneratorSpec` in the
    global ``REGISTRY`` (geometric contract, when-to-use, topology branches, range
    guards, source hash) and tags the function with ``_sp_generator``.
  * manifest helpers     — ``load_manifest`` / ``is_certified`` / ``record`` read
    and write ``certified.json``, keyed by ``"<name>@<sha256>"``.
  * attribution          — ``stamp(sk, name)`` writes a Fusion sketch attribute so
    the deps check can recover which certified generator produced a sketch;
    ``read_stamp(sk)`` reads it back. (These call methods on the passed sketch
    object; they do not import ``adsk``.)

The solver stays ground truth — it just runs per-generator-version in the
certification harness, not per-build. A certified entry says "this exact source,
on this Fusion version, produced a fully-constrained-modulo-interior sketch."
"""
import hashlib
import inspect
import json
import os
import textwrap


# Attribute group/name used to stamp a sketch with its producing generator.
STAMP_GROUP = "sp_gen"
STAMP_KEY = "id"

# Default manifest location: alongside this module.
DEFAULT_MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "generators", "certified.json")


def source_hash(fn):
    """sha256 hex of a generator function's source.

    The source is dedented and its lines right-stripped before hashing, so that
    re-indenting the function (e.g. moving it in/out of a class) or trailing
    whitespace churn does not spuriously invalidate certification — but ANY
    change to the actual code or comments does. That edit-sensitivity is the
    whole safety property: a changed generator re-certifies, never trusts stale.
    """
    src = inspect.getsource(fn)
    src = textwrap.dedent(src)
    norm = "\n".join(line.rstrip() for line in src.splitlines())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


class GeneratorSpec:
    """Registry entry for one generator. Identified by its GEOMETRIC CONTRACT
    (what shape + constraint topology it makes), not by furniture semantics — so
    the same generator serves a bookcase base and a table apron if the geometry
    matches."""

    __slots__ = ("name", "fn", "contract", "when_to_use", "branches",
                 "range_guards", "source_hash")

    def __init__(self, name, fn, contract, when_to_use, branches, range_guards):
        self.name = name
        self.fn = fn
        self.contract = contract
        self.when_to_use = when_to_use
        self.branches = tuple(branches)
        self.range_guards = tuple(range_guards)
        self.source_hash = source_hash(fn)

    @property
    def key(self):
        """Manifest key: ``"<name>@<sha256>"``."""
        return f"{self.name}@{self.source_hash}"

    def to_dict(self):
        return {
            "name": self.name,
            "geometric_contract": self.contract,
            "when_to_use": self.when_to_use,
            "topology_branches": list(self.branches),
            "range_guards": list(self.range_guards),
            "source_hash": self.source_hash,
        }


# Global registry: name -> GeneratorSpec.
REGISTRY = {}


def register(name, contract, when_to_use, branches=(), range_guards=()):
    """Decorator: record ``fn`` as a certified-able generator.

    Usage::

        @register("base_arch_cut",
                  contract="closed free-spline top edge + N-line waste rail …",
                  when_to_use="one continuous curve across multiple members",
                  branches=["center-shared", "center-pair"],
                  range_guards=["span > 2*foot_inset", "endpoints distinct"])
        def base_arch_cut(...): ...

    The function is tagged with ``_sp_generator = name`` and ``_sp_spec`` so a
    build can recover its spec (and source hash) for stamping + lookup.
    """
    def deco(fn):
        spec = GeneratorSpec(name, fn, contract, when_to_use, branches,
                             range_guards)
        REGISTRY[name] = spec
        fn._sp_generator = name
        fn._sp_spec = spec
        return fn
    return deco


def spec_for(name):
    """The registered :class:`GeneratorSpec` for ``name``, or None."""
    return REGISTRY.get(name)


# ── manifest (certified.json) ────────────────────────────────────────────────

def load_manifest(path=None):
    """Load the certification manifest (``{key: record}``). Missing file → ``{}``
    so a fresh checkout simply certifies nothing and the deps check falls back to
    the solver everywhere (current behavior)."""
    path = path or DEFAULT_MANIFEST
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)


def is_certified(name, src_hash, branch=None, manifest=None, path=None):
    """True iff ``"<name>@<src_hash>"`` is present, ``certified: true``, and (if a
    ``branch`` is given) that branch is listed. A hash mismatch (edited source)
    simply isn't found → not certified → solver fallback. Fail-closed by design."""
    if manifest is None:
        manifest = load_manifest(path)
    rec = manifest.get(f"{name}@{src_hash}")
    if not rec or not rec.get("certified"):
        return False
    if branch is not None and branch not in rec.get("branches", []):
        return False
    return True


def is_certified_stamp(stamp, branch=None, manifest=None, path=None):
    """``is_certified`` keyed directly by a sketch stamp string ``"name@hash"``."""
    if not stamp or "@" not in stamp:
        return False
    name, src_hash = stamp.rsplit("@", 1)
    return is_certified(name, src_hash, branch, manifest, path)


def record(spec, branches, fusion_version, certified_at, manifest=None,
           path=None):
    """Merge a passing certification into the manifest dict and return it. The
    caller (the Fusion harness) writes it back with :func:`save_manifest`. Keyed
    by source hash, so editing the generator orphans the old entry automatically."""
    if manifest is None:
        manifest = load_manifest(path)
    manifest[spec.key] = {
        "certified": True,
        "name": spec.name,
        "branches": list(branches),
        "fusion_version": fusion_version,
        "certified_at": certified_at,
        "geometric_contract": spec.contract,
    }
    return manifest


def save_manifest(manifest, path=None):
    """Write the manifest as pretty JSON, creating the parent dir if needed."""
    path = path or DEFAULT_MANIFEST
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    return path


# ── attribution: stamp a sketch with its producing generator ─────────────────

def stamp(sk, name, src_hash=None):
    """Tag a Fusion sketch with ``"<name>@<hash>"`` via a sketch attribute, so the
    deps check can later look up its certification. ``src_hash`` defaults to the
    registered spec's hash. Calls ``sk.attributes.add`` on the passed object — no
    ``adsk`` import here. Returns the stamp string (or None if no spec/hash)."""
    if src_hash is None:
        spec = REGISTRY.get(name)
        if spec is None:
            return None
        src_hash = spec.source_hash
    value = f"{name}@{src_hash}"
    sk.attributes.add(STAMP_GROUP, STAMP_KEY, value)
    return value


def read_stamp(sk):
    """Read back a sketch's generator stamp (``"name@hash"``), or None if unstamped
    or unreadable."""
    try:
        attr = sk.attributes.itemByName(STAMP_GROUP, STAMP_KEY)
    except Exception:
        return None
    return attr.value if attr else None
