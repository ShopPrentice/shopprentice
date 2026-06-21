"""Tier 1 — script-level structural DOF guard (pure Python, no Fusion).

A cheap degrees-of-freedom accountant that the sketch helpers feed as they add
geometry, so an under-constrained sketch (the dropped/missing-dimension bug class
this project kept hitting) is caught *at build time*, in microseconds, with zero
Fusion round-trips — instead of 51 s later in the deps solver pin/resolve.

The balance it tracks (see the brief, Tier 1):

    DOF = 2 * (counted sketch points)
          - Σ(dof removed by each geometric constraint)
          - (driving dimensions)

A free point is 2 DOF. ``addHorizontal``/``addVertical`` removes 1, ``addCoincident``
removes 2, each driving dimension removes 1. Fit-point spline *interior* points are
the drag-to-shape exemption: they are neither counted (their 2 DOF) nor expected to
be removed — declare them with ``spline_interior(n)`` so the balance still lands on
0 for a "constrained frame + draggable sculpted edge" profile.

    DOF == 0  → fully constrained (modulo declared spline interiors). OK.
    DOF  > 0  → UNDER-constrained — a dimension was dropped or never added. The
                high-signal catch; this is what the guard exists to surface.
    DOF  < 0  → over-counted. Usually a *redundant* constraint the formula can't
                see through — on a closed loop (rectangle) Fusion grounds a vertex
                via H/V + loop closure with no dimension touching it, so a naive
                count over-removes. This is exactly the false-alarm direction the
                old graph-walking validator died on.

CRITICAL DESIGN RULE (from the brief): this guard is NECESSARY-not-SUFFICIENT and
must only *alert on the under-constrained direction*. It is never an authority that
rejects correct geometry. So:

  * DOF > 0 raises (or warns, per ``on_under``) — a genuine, actionable bug.
  * DOF < 0 only ever emits a soft note (``on_over`` defaults to "warn") — never
    raises, because structural counting cannot distinguish a real over-constraint
    from an invisible redundant constraint on a closed loop.

It does NOT replace Fusion's ``isFullyConstrained`` solver verdict (deps.py); it is
a fast guard in front of it. A balanced count (0) means "the explicit constraints
account for every DOF" — it cannot prove the solver agrees (redundancy/degeneracy
are invisible to counting), which is why the solver stays ground truth.

Pure Python on purpose: no ``adsk`` import, so the sketch generators can be unit
tested for constraint-completeness offline, and so this file runs anywhere.

Global kill switch: set ``SP_DOF_GUARD`` in the environment to ``warn`` (record +
log, never raise) or ``off`` (no-op) to downgrade the guard for a whole build
without editing any helper. Default is ``raise`` (fail fast on under-constraint).
Use :func:`default_tracker` in the helpers so this switch is honored everywhere.
"""
import os


class DofError(Exception):
    """Raised by ``assert_balanced`` when a sketch is under-constrained
    (DOF > 0) and ``on_under == 'raise'`` (the default)."""


# DOF removed by one instance of each geometric constraint the sketch helpers use.
# Only the under-constrained *direction* is authoritative (see module docstring);
# these values keep a correctly-built generator balanced at 0, they are not a claim
# that Fusion removes exactly this many real DOF (redundancy is invisible here).
_CONSTRAINT_DOF = {
    "horizontal": 1,
    "vertical": 1,
    "coincident": 2,
    "perpendicular": 1,
    "parallel": 1,
    "collinear": 2,
    "equal": 1,
    "tangent": 1,
    "midpoint": 2,
    "symmetry": 1,
}


class DofTracker:
    """Accumulates the DOF balance for a single sketch.

    Feed it as geometry is added (``add_point``, ``add_hv``, ``add_dim`` …), then
    call ``assert_balanced(name)`` once the sketch is complete. The counting is
    purely *structural* — it depends on the constraint topology, not on coordinate
    values — which is exactly why one generator's accounting is valid across every
    call with different data.

    Args:
        name: Sketch/generator name, used in messages.
        on_under: What to do when DOF > 0 — "raise" (default), "warn", or
            "collect" (record only, stay silent).
        on_over: What to do when DOF < 0 — "warn" (default) or "collect". Never
            "raise": over-count is the redundant-constraint false-alarm direction.
        log: Callable for messages (default ``print``). Pass a no-op to silence.
    """

    def __init__(self, name=None, on_under="raise", on_over="warn", log=print):
        if on_under not in ("raise", "warn", "collect"):
            raise ValueError(f"on_under must be raise/warn/collect, got {on_under!r}")
        if on_over not in ("warn", "collect"):
            # "raise" is deliberately forbidden — never reject correct geometry.
            raise ValueError(f"on_over must be warn/collect, got {on_over!r}")
        self.name = name
        self.on_under = on_under
        self.on_over = on_over
        self._log = log
        self._points = 0          # counted (non-exempt) sketch points
        self._removed = 0         # DOF removed by geometric constraints
        self._dims = 0            # driving dimensions
        self._interiors = 0       # exempt spline interior fit points (reporting only)
        self.issues = []          # messages from assert_balanced (when not raising)

    # ── geometry accounting ────────────────────────────────────────────────
    def add_point(self, n=1):
        """Count ``n`` free sketch points (2 DOF each). Do NOT count spline
        interior fit points here — use :meth:`spline_interior`."""
        self._points += n
        return self

    def add_dim(self, n=1):
        """Count ``n`` driving dimensions (1 DOF each)."""
        self._dims += n
        return self

    def add_constraint(self, kind, n=1):
        """Count ``n`` geometric constraints of a named ``kind`` (see
        ``_CONSTRAINT_DOF``). Raises on an unknown kind so a generator can't
        silently mis-account a constraint the formula doesn't know."""
        try:
            per = _CONSTRAINT_DOF[kind]
        except KeyError:
            raise ValueError(
                f"unknown constraint kind {kind!r}; known: "
                f"{sorted(_CONSTRAINT_DOF)} (or use remove_dof for a raw count)")
        self._removed += per * n
        return self

    def remove_dof(self, n):
        """Escape hatch: subtract ``n`` raw DOF for a constraint not in the
        table. Prefer the named helpers so the accounting stays legible."""
        self._removed += n
        return self

    # Named convenience wrappers for the constraints the sketch helpers add.
    def add_horizontal(self, n=1):
        return self.add_constraint("horizontal", n)

    def add_vertical(self, n=1):
        return self.add_constraint("vertical", n)

    def add_hv(self, n=1):
        """``n`` horizontal OR vertical constraints (1 DOF each) — the common
        rectangle/loop case where each edge gets one or the other."""
        self._removed += n
        return self

    def add_coincident(self, n=1):
        return self.add_constraint("coincident", n)

    def add_perpendicular(self, n=1):
        return self.add_constraint("perpendicular", n)

    def add_parallel(self, n=1):
        return self.add_constraint("parallel", n)

    def add_collinear(self, n=1):
        return self.add_constraint("collinear", n)

    def add_equal(self, n=1):
        return self.add_constraint("equal", n)

    # ── arcs ───────────────────────────────────────────────────────────────
    def add_arc(self, n=1):
        """Count ``n`` sketch arcs. A Fusion arc carries **5 free DOF** — center
        (2) + radius (1) + start angle (1) + sweep (1) — which this models as 3
        SketchPoints (center/start/end = 6 DOF) minus 1 *intrinsic* equal-radius
        DOF that the arc enforces by construction (|center−start| == |center−end|).
        That intrinsic −1 is NOT a constraint you added; it's baked into the arc.
        With it, a stadium/slot (2 lines + 2 arcs + tangents + coincidents) lands
        on 0. NOTE: arcs are the 'special geometry' Tier 1 is weakest on — the
        ``on_over`` soft-note path exists precisely so a mis-modeled arc can't
        reject correct geometry."""
        self._points += 3 * n
        self._removed += 1 * n
        return self

    # ── splines ────────────────────────────────────────────────────────────
    def spline_interior(self, n):
        """Declare ``n`` fit-point spline INTERIOR points as exempt: they are the
        drag-to-shape freedom, so they're neither counted nor expected constrained.
        Recorded only so ``assert_balanced`` can report "modulo N interiors". The
        spline's start/end are NOT interiors — count them with :meth:`add_point`
        (and pin them with dimensions), since deps.py requires anchored ends."""
        self._interiors += n
        return self

    def add_spline(self, n_fit):
        """Convenience for a fitted spline with ``n_fit`` fit points: counts the 2
        endpoints (which must be dimensioned) and declares the ``n_fit - 2``
        interiors exempt."""
        if n_fit < 2:
            raise ValueError(f"a fitted spline needs >=2 fit points, got {n_fit}")
        self.add_point(2)
        self.spline_interior(n_fit - 2)
        return self

    # ── verdict ────────────────────────────────────────────────────────────
    @property
    def dof(self):
        """Current DOF balance: 2*points - removed - dims (interiors exempt)."""
        return 2 * self._points - self._removed - self._dims

    @property
    def balanced(self):
        return self.dof == 0

    def summary(self):
        return (f"points={self._points} (={2 * self._points} DOF), "
                f"constraints={self._removed} DOF, dims={self._dims}, "
                f"spline_interiors={self._interiors} (exempt) → DOF={self.dof}")

    def assert_balanced(self, name=None):
        """Check the balance and dispatch per ``on_under`` / ``on_over``.

        Returns the DOF value. On DOF > 0 with ``on_under == 'raise'`` (default),
        raises :class:`DofError`. On DOF < 0, only ever logs/records — never raises.
        """
        nm = name or self.name or "<sketch>"
        d = self.dof

        if d == 0:
            return 0

        if d > 0:
            msg = (f"{nm}: UNDER-CONSTRAINED — {d} free DOF remain "
                   f"(likely a dropped/missing dimension). {self.summary()}")
            if self.on_under == "raise":
                raise DofError(msg)
            self.issues.append(msg)
            if self.on_under == "warn":
                self._log(f"  WARN  {msg}")
            return d

        # d < 0: over-counted. Almost always a redundant constraint the structural
        # formula can't see (a closed loop grounds a vertex with no dimension on
        # it). NEVER reject — just surface it as a soft note for a human to glance
        # at, exactly because correct geometry can land here.
        msg = (f"{nm}: over-counted by {-d} DOF — likely a redundant constraint "
               f"on a closed loop (NOT necessarily a real over-constraint; the "
               f"solver is the judge). {self.summary()}")
        self.issues.append(msg)
        if self.on_over == "warn":
            self._log(f"  NOTE  {msg}")
        return d

    # Context-manager sugar: `with DofTracker("S") as dof: ...` asserts on exit.
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.assert_balanced()
        return False


class NullDof:
    """A no-op tracker. Use to disable Tier 1 cheaply (e.g. a generator that opts
    out, or to turn the guard off globally) without sprinkling None-checks through
    the helpers — every method is a silent no-op and ``assert_balanced`` returns 0."""

    def __getattr__(self, _name):
        def _noop(*_a, **_k):
            return self
        return _noop

    dof = 0
    balanced = True
    issues = ()

    def assert_balanced(self, name=None):
        return 0

    def summary(self):
        return "NullDof (guard disabled)"

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def default_tracker(name=None, log=print):
    """Build the tracker the sketch helpers should use, honoring the global
    ``SP_DOF_GUARD`` env switch:

      * unset / ``raise`` (default) → ``DofTracker`` that raises on DOF > 0,
      * ``warn``                    → ``DofTracker`` that logs+records instead,
      * ``off`` / ``0`` / ``none``  → ``NullDof`` (guard fully disabled).

    Helpers call ``dof = default_tracker(name)`` so the switch reaches every
    generator without per-helper plumbing. Over-constraint (DOF < 0) is always a
    soft note regardless of the switch — the guard never rejects correct geometry.
    """
    mode = os.environ.get("SP_DOF_GUARD", "raise").strip().lower()
    if mode in ("off", "0", "none", "disabled", "false"):
        return NullDof()
    on_under = "warn" if mode == "warn" else "raise"
    return DofTracker(name, on_under=on_under, log=log)
