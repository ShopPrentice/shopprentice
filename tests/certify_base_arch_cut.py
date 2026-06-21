"""Fusion-side certification harness for base_arch_cut (Tier 2).

Run via the MCP: execute_script(sandbox=true, script=<this file's contents>).
Builds the REAL helpers/sp/generators.py base_arch_cut in a sandbox document, once
per topology branch (center-shared, center-pair), and runs the brief §4 diagnostic
— pin each spline interior fit point, read sketch.isFullyConstrained, restore —
which is EXACTLY what deps._fc_modulo_spline_interiors does. True ⇒ the topology is
fully-constrained-modulo-interiors ⇒ deps would pass it.

Zero-drift: it execs the actual generators.py source (stripping relative imports,
injecting the staged sp utilities), so what is certified is the source that gets
hashed. Also checks property (2) no Fix on drawn geometry, and that a profile is
produced. Writes a verdict to /tmp/arch_cert.json and prints it.
"""
import adsk.core
import json
import os
import traceback


def _gen_path():
    """Path to the generators.py that is actually importable as helpers.sp —
    so the harness certifies the same source the deps check will hash, wherever
    the repo lives."""
    import helpers
    repo = os.path.dirname(os.path.dirname(os.path.abspath(helpers.__file__)))
    return os.path.join(repo, "helpers", "sp", "generators.py")


HALF_SHARED = [(1.5209, 0.0), (1.8159, 2.7187), (2.473, 4.0203),
               (3.9564, 5.1414), (5.2, 5.45)]          # last ≈ centre → shared
HALF_PAIR = [(1.5209, 0.0), (1.8569, 1.995), (3.3334, 4.75),
             (5.0377, 5.46), (6.0, 5.55)]              # last left of centre → pair


def _load_generator():
    """Exec the real generators.py with relative imports stripped and deps injected."""
    from helpers import sp
    gen_path = _gen_path()
    src = open(gen_path).read()
    keep = []
    for ln in src.splitlines():
        s = ln.strip()
        if s.startswith("from .") or s.startswith("import adsk"):
            continue
        keep.append(ln)

    class _NoDof:
        def __getattr__(self, _n):
            return lambda *a, **k: self
        def assert_balanced(self, name=None):
            return 0

    ns = {
        "__name__": "gen_inline",
        "adsk": adsk,
        "register": lambda *a, **k: (lambda fn: fn),
        "stamp": lambda *a, **k: None,
        "default_tracker": lambda *a, **k: _NoDof(),
        "probe_orientations": sp.probe_orientations,
        "refs_to_construction": sp.refs_to_construction,
        "smallest_profile": sp.smallest_profile,
    }
    exec(compile("\n".join(keep), gen_path, "exec"), ns)
    return ns["base_arch_cut"]


def _has_fix_on_drawn(sk):
    """Property (2): no drawn curve/point pinned by Fix/Ground."""
    for ci in range(sk.sketchCurves.count):
        c = sk.sketchCurves.item(ci)
        if getattr(c, "isReference", False) or getattr(c, "isConstruction", False):
            continue
        try:
            if c.isFixed:
                return True
        except Exception:
            pass
        if hasattr(c, "fitPoints"):
            fps = c.fitPoints
            for k in range(fps.count):
                try:
                    if fps.item(k).isFixed:
                        return True
                except Exception:
                    pass
    return False


def _fc_modulo_spline_interiors(sk):
    """Pin spline interiors, read isFullyConstrained, restore (deps §4 diagnostic)."""
    saved = []
    try:
        for ci in range(sk.sketchCurves.count):
            cur = sk.sketchCurves.item(ci)
            if getattr(cur, "isReference", False) or not hasattr(cur, "fitPoints"):
                continue
            fps = cur.fitPoints
            for k in range(1, fps.count - 1):
                fp = fps.item(k)
                saved.append((fp, fp.isFixed))
                fp.isFixed = True
        return bool(sk.isFullyConstrained)
    finally:
        for fp, v in saved:
            try:
                fp.isFixed = v
            except Exception:
                pass


def run(context):
    app = adsk.core.Application.get()
    design = app.activeProduct
    root = design.rootComponent
    from helpers import sp

    # Sandbox params the generator's dim expressions reference.
    up = design.userParameters
    def addp(name, cm):
        if up.itemByName(name) is None:
            up.add(name, adsk.core.ValueInput.createByReal(cm),
                   design.unitsManager.defaultLengthUnits, "")
    addp("span", 50.8)     # 20 in
    addp("ei", 3.81)       # 1.5 in
    ev = sp._make_ev()

    base_arch_cut = _load_generator()
    fusion_version = app.version

    results = {}
    branches = [("center-shared", HALF_SHARED), ("center-pair", HALF_PAIR)]
    off = -5.08            # plane offset on the off (y) axis, cm
    for i, (branch, half) in enumerate(branches):
        # Offset plane on the off-axis (y) for an x-spanning cut.
        planes = root.constructionPlanes
        pin = planes.createInput()
        pin.setByOffset(root.xZConstructionPlane,
                        adsk.core.ValueInput.createByReal(off))
        plane = planes.add(pin)

        sk, prof = base_arch_cut(root, plane, "x", "span", half, "ei",
                                 off_axis_cm=off, name=f"Cert_{i}", ev=ev)

        has_profile = prof is not None
        no_fix = not _has_fix_on_drawn(sk)
        fc_mod = _fc_modulo_spline_interiors(sk)
        raw_fc = bool(sk.isFullyConstrained)
        certified = bool(has_profile and no_fix and fc_mod)
        results[branch] = {
            "certified": certified,
            "fully_constrained_modulo_interiors": fc_mod,
            "raw_isFullyConstrained": raw_fc,
            "no_fix_on_drawn": no_fix,
            "has_profile": has_profile,
            "fit_points": int(len(half) * 2 - (2 if branch == "center-shared" else 0)),
        }

    verdict = {
        "generator": "base_arch_cut",
        "fusion_version": fusion_version,
        "all_certified": all(r["certified"] for r in results.values()),
        "branches": results,
    }
    try:
        with open("/tmp/arch_cert.json", "w") as f:
            json.dump(verdict, f, indent=2)
    except Exception:
        pass
    print("ARCH_CERT_RESULT " + json.dumps(verdict))
