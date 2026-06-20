"""Offline test of the Tier 3 compute-deferral in _fc_modulo_spline_interiors.

Pure Python — no Fusion. Run: python3 tests/test_deps_deferred.py

Verifies that the pin/restore now runs under sketch.isComputeDeferred: the sketch
is deferred while interiors are pinned, resumed (one recompute) before the verdict
is read, restored under deferral, and left isComputeDeferred=False at rest — with
the verdict identical to the eager logic, and a graceful fallback when the
property is unsettable.
"""
import os, sys, types, importlib.util

for m in ("adsk", "adsk.core", "adsk.fusion"):
    sys.modules[m] = types.ModuleType(m)

_DEPS = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "helpers", "sp", "deps.py"))
spec = importlib.util.spec_from_file_location("deps", _DEPS)
deps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deps)


class Pt:
    def __init__(self, fixed=False):
        self.isFixed = fixed


class Coll:
    def __init__(self, items):
        self._items = list(items)

    @property
    def count(self):
        return len(self._items)

    def item(self, i):
        return self._items[i]


class Spline:
    isReference = False

    def __init__(self, n_interior):
        self.fitPoints = Coll([Pt()] + [Pt() for _ in range(n_interior)] + [Pt()])


class Sketch:
    """Models isFullyConstrained as 'frame_ok AND all interiors pinned', records
    the isComputeDeferred transition log, and (optionally) refuses the property."""
    def __init__(self, spline, frame_ok=True, allow_defer=True):
        self.name = "S"
        self._spline = spline
        self.sketchCurves = Coll([spline])
        self.frame_ok = frame_ok
        self.allow_defer = allow_defer
        self._deferred = False
        self.defer_log = []

    @property
    def isComputeDeferred(self):
        return self._deferred

    @isComputeDeferred.setter
    def isComputeDeferred(self, v):
        if not self.allow_defer:
            raise RuntimeError("isComputeDeferred unsupported")
        self._deferred = bool(v)
        self.defer_log.append(bool(v))

    @property
    def isFullyConstrained(self):
        for k in range(1, self._spline.fitPoints.count - 1):
            if not self._spline.fitPoints.item(k).isFixed:
                return False
        return self.frame_ok


R = []


def case(name, fn):
    try:
        ok = bool(fn())
    except Exception as e:
        ok = False
        print(f"        ! {e!r}")
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    R.append(ok)


def _verdict_true_and_restored():
    sk = Sketch(Spline(5), frame_ok=True)
    v = deps._fc_modulo_spline_interiors(sk)
    interiors_restored = all(
        not sk._spline.fitPoints.item(k).isFixed for k in range(1, 6))
    return v is True and interiors_restored

case("deferred path: verdict True (frame ok) + interiors restored to unpinned",
     _verdict_true_and_restored)

def _verdict_false_when_frame_loose():
    sk = Sketch(Spline(4), frame_ok=False)
    return deps._fc_modulo_spline_interiors(sk) is False

case("deferred path: verdict False when the frame is loose", _verdict_false_when_frame_loose)

def _deferral_toggled_and_left_false():
    sk = Sketch(Spline(3), frame_ok=True)
    deps._fc_modulo_spline_interiors(sk)
    # Expect: deferred True around pin, False before read, True/False around restore.
    log = sk.defer_log
    return (len(log) >= 2 and log[0] is True            # suspended first
            and sk.isComputeDeferred is False           # left at rest
            and False in log)                            # resumed at least once

case("isComputeDeferred toggled on/off and left False at rest",
     _deferral_toggled_and_left_false)

class GuardedSketch(Sketch):
    """Raises if isFullyConstrained is read while compute is still deferred —
    proving the resume (_set_deferred False) ran before the verdict read."""
    @property
    def isFullyConstrained(self):
        if self._deferred:
            raise AssertionError("verdict read while compute still deferred!")
        for k in range(1, self._spline.fitPoints.count - 1):
            if not self._spline.fitPoints.item(k).isFixed:
                return False
        return self.frame_ok


def _read_happens_while_resumed():
    sk = GuardedSketch(Spline(3), frame_ok=True)
    return deps._fc_modulo_spline_interiors(sk) is True

case("verdict is read only after compute is resumed (not while deferred)",
     _read_happens_while_resumed)

def _fallback_when_unsettable():
    # allow_defer=False → _set_deferred returns False, logic falls back to eager.
    sk = Sketch(Spline(4), frame_ok=True, allow_defer=False)
    v = deps._fc_modulo_spline_interiors(sk)
    interiors_restored = all(
        not sk._spline.fitPoints.item(k).isFixed for k in range(1, 5))
    return v is True and interiors_restored and sk.defer_log == []

case("graceful fallback to eager when isComputeDeferred is unsettable",
     _fallback_when_unsettable)

def _set_deferred_helper():
    ok_sk = Sketch(Spline(2))
    bad_sk = Sketch(Spline(2), allow_defer=False)
    return (deps._set_deferred(ok_sk, True) is True
            and ok_sk.isComputeDeferred is True
            and deps._set_deferred(bad_sk, True) is False)

case("_set_deferred returns True/False on success/refusal", _set_deferred_helper)


print(f"\n{sum(R)}/{len(R)} cases passed")
sys.exit(0 if all(R) else 1)
