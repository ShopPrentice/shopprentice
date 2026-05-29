"""Offline test of deps.py sketch-anchoring logic with stubbed Fusion objects.

Pure Python — no Fusion required. Run: python3 tests/test_deps_anchoring.py

Exercises the hybrid contract in _check_sketch_anchoring:
  (a) anchored to a resolved projected reference,
  (b) no Fix/Ground constraint on drawn geometry,
  (c) fully constrained EXCEPT fit-point spline interiors. When the raw
      isFullyConstrained is False, the check pins spline interiors and re-asks
      the solver (_fc_modulo_spline_interiors) — so a 'constrained frame +
      draggable spline edge' profile passes while a genuinely loose line fails.

The stub models isFullyConstrained as a computed property: free iff any spline
interior fit point is unfixed, else `frame_ok` (whether the rest is determined).
Pinning interiors (what the real check does) therefore flips it exactly as
Fusion would — so this genuinely tests the modulo logic, not a frozen flag.
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
        self.geometry = object()        # points have geometry, no startSketchPoint
        self.isFixed = fixed

class Coll:
    def __init__(self, items): self._items = items
    @property
    def count(self): return len(self._items)
    def item(self, i): return self._items[i]

class Curve:
    def __init__(self, kind, isRef=False, isCon=False, resolved=True,
                 spline=False, fixed=False, n_interior=1, fixed_interior=False):
        self.objectType = f"adsk::fusion::Sketch{kind}"
        self.isReference = isRef
        self.isConstruction = isCon
        self.isFixed = fixed
        self.referencedEntity = object() if resolved else None
        self.startSketchPoint = Pt()
        self.endSketchPoint = Pt()
        if spline:
            interior = [Pt(fixed_interior) for _ in range(n_interior)]
            self.fitPoints = Coll([self.startSketchPoint] + interior + [self.endSketchPoint])

class Sketch:
    def __init__(self, name, curves, frame_ok=True):
        self.name = name
        self.sketchCurves = Coll(curves)
        self.originPoint = Pt()
        self.frame_ok = frame_ok
        self._curves = curves
    @property
    def isFullyConstrained(self):
        # Free if any spline interior point is unfixed; otherwise the rest of
        # the sketch is determined iff frame_ok.
        for c in self._curves:
            if getattr(c, "isReference", False) or not hasattr(c, "fitPoints"):
                continue
            fps = c.fitPoints
            for k in range(1, fps.count - 1):
                if not fps.item(k).isFixed:
                    return False
        return self.frame_ok

class Comp:
    def __init__(self, sketches): self.sketches = Coll(sketches)

def run(name, comp, is_root, expect_issues):
    issues = []
    deps._check_sketch_anchoring(comp, "C", is_root, issues)
    got = len(issues)
    ok = (got > 0) == expect_issues
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {got} issue(s) "
          f"(expected {'some' if expect_issues else 'none'})")
    for it in issues:
        print(f"        - {it}")
    return ok

R = []

# 1. GOOD rectangle: fully constrained, anchored. (No false positive on the
#    opposite corner — goes through isFullyConstrained, not a traversal.)
ref = Curve("Line", isRef=True)
rect = [Curve("Line") for _ in range(4)]
R.append(run("good: fully-constrained rectangle",
             Comp([Sketch("S", [ref] + rect, frame_ok=True)]), False, False))

# 2. GOOD slot: arcs + lines, fully constrained.
ref2 = Curve("Line", isRef=True)
slot = [Curve("Arc"), Curve("Line"), Curve("Arc"), Curve("Line")]
R.append(run("good: fully-constrained slot with arcs",
             Comp([Sketch("S", [ref2] + slot, frame_ok=True)]), False, False))

# 3. BAD: drawn geometry, NO reference at all.
R.append(run("bad: no reference (placed coords)",
             Comp([Sketch("S", [Curve("Line")], frame_ok=False)]), False, True))

# 4. BAD: reference present but rectangle under-constrained, no spline to excuse.
ref4 = Curve("Line", isRef=True)
R.append(run("bad: under-constrained rectangle (no spline)",
             Comp([Sketch("S", [ref4, Curve("Line"), Curve("Line")], frame_ok=False)]),
             False, True))

# 5. BAD: fully constrained but via a Fix constraint (absolute coords).
ref5 = Curve("Line", isRef=True)
R.append(run("bad: Fix/Ground constraint",
             Comp([Sketch("S", [ref5, Curve("Line", fixed=True)], frame_ok=True)]),
             False, True))

# 6. ROOT: fully constrained, origin-anchored, no projection required.
R.append(run("root: fully-constrained, origin-anchored",
             Comp([Sketch("S", [Curve("Line")], frame_ok=True)]), True, False))

# 7. *** THE FIX *** GOOD mixed: constrained frame (lines) + draggable spline
#    edge with a free interior. Raw isFullyConstrained is False; pinning the
#    spline interior makes it True -> PASS. This is the case the old code wrongly
#    flagged (Foot, Cap, Stretcher, Top, Batten, Wedge).
ref7 = Curve("Line", isRef=True)
frame = [Curve("Line"), Curve("Line"), Curve("Line")]
sculpt = Curve("FittedSpline", spline=True, n_interior=2)
R.append(run("GOOD mixed: constrained frame + draggable spline edge",
             Comp([Sketch("S", [ref7] + frame + [sculpt], frame_ok=True)]), False, False))

# 8. BAD mixed: frame + spline, but a frame line is loose (frame_ok=False).
ref8 = Curve("Line", isRef=True)
R.append(run("bad mixed: frame has a loose line",
             Comp([Sketch("S", [ref8, Curve("Line"), Curve("Line"),
                                Curve("FittedSpline", spline=True)], frame_ok=False)]),
             False, True))

# 9. GOOD all-spline: free interior, ends anchored (frame_ok=True).
ref9 = Curve("Line", isRef=True)
R.append(run("good all-spline: free interior, anchored ends",
             Comp([Sketch("S", [ref9, Curve("FittedSpline", spline=True)], frame_ok=True)]),
             False, False))

# 10. BAD spline: an end is free (frame_ok=False even with interiors pinned).
ref10 = Curve("Line", isRef=True)
R.append(run("bad spline: unanchored start/end",
             Comp([Sketch("S", [ref10, Curve("FittedSpline", spline=True)], frame_ok=False)]),
             False, True))

# 11. NEUTRAL: reference + construction only, nothing drawn -> skip.
R.append(run("neutral: reference + construction only",
             Comp([Sketch("S", [Curve("Line", isRef=True), Curve("Line", isCon=True)],
                          frame_ok=False)]), False, False))

# 12. BAD: spline interior pinned with Fix to force full constraint -> check (b)
#     must catch it (the absolute-coordinate shortcut on fit points).
ref12 = Curve("Line", isRef=True)
R.append(run("bad: spline interior pinned with Fix (shortcut)",
             Comp([Sketch("S", [ref12, Curve("FittedSpline", spline=True,
                                              fixed_interior=True)], frame_ok=True)]),
             False, True))

print(f"\n{sum(R)}/{len(R)} cases passed")
sys.exit(0 if all(R) else 1)
