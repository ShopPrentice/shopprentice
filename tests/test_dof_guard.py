"""Offline test of the Tier 1 structural DOF guard (helpers/sp/dof.py).

Pure Python — no Fusion required. Run: python3 tests/test_dof_guard.py

The two non-negotiables from the brief (Section 3):
  * a deliberately-dropped dimension IS caught (DOF > 0), and
  * a correct rectangle is NOT false-alarmed.

Each case replays the constraint accounting the real sketch helpers perform, so a
pass here means those generators' topologies actually balance to 0 DOF (modulo
declared spline interiors) — and an over-counted closed loop only ever earns a
soft note, never a rejection (the failure mode that killed the old graph walker).
"""
import os, sys, importlib.util

_DOF = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "helpers", "sp", "dof.py"))
spec = importlib.util.spec_from_file_location("dof", _DOF)
dof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dof)
DofTracker, DofError, NullDof = dof.DofTracker, dof.DofError, dof.NullDof


R = []


def silent(_msg):
    pass


def case(name, fn):
    """Run fn() which returns True on the expected outcome."""
    try:
        ok = bool(fn())
    except Exception as e:
        ok = False
        print(f"        ! unexpected exception: {e!r}")
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    R.append(ok)


# ── Generator accounting replays ────────────────────────────────────────────

def acct_sketch_rect(drop_dims=0, extra_dims=0):
    """sketch_rect / sketch_rect_model (ORIGIN mode): addTwoPointRectangle = 4
    corner points; helper adds 2 H + 2 V and 4 dims (w, h, x0, y0).
    8 - 4 - 4 = 0."""
    t = DofTracker("Rect", on_under="collect", on_over="collect", log=silent)
    t.add_point(4)
    t.add_hv(4)                       # 2 horizontal + 2 vertical
    t.add_dim(4 - drop_dims + extra_dims)
    return t


def acct_rect_anchored(drop_dims=0):
    """_sketch_rect_model_anchored: 4 chained corners (closed loop) = 4 points;
    H/V on all 4 edges; 2 size dims + 2 anchor offset dims (to projected parent,
    grounded). 8 - 4 - 4 = 0."""
    t = DofTracker("RectAnchored", on_under="collect", on_over="collect", log=silent)
    t.add_point(4)
    t.add_hv(4)
    t.add_dim(2 + 2 - drop_dims)      # 2 size + 2 anchor offset
    return t


def acct_base_arch_cut(n_fit, drop_end_dim=False, drop_rail_dim=False):
    """base_arch_cut: a fitted spline (n_fit points, ends anchored, interiors
    free) whose 2 endpoints get 2 dims each (au, az) to the grounded origin =
    4 dims; then a 3-line waste rail adding 2 new points (pR, pL2; it closes on
    the spline ends), H/V on all 3 lines, and 1 rail-depth dim.
      spline ends:  2 pts * 2 = 4 DOF - 4 dims          = 0
      waste rail:   2 pts * 2 = 4 DOF - 3 HV - 1 dim    = 0
    interiors (n_fit - 2) exempt."""
    t = DofTracker("BaseArch", on_under="collect", on_over="collect", log=silent)
    t.add_spline(n_fit)               # +2 endpoints, declares n_fit-2 interiors
    t.add_dim(4 - (1 if drop_end_dim else 0))   # 4 endpoint dims
    t.add_point(2)                    # pR, pL2
    t.add_hv(3)                       # H/V on l1, l2, l3
    t.add_dim(1 - (1 if drop_rail_dim else 0))  # rail depth dim
    return t


# ── 1. The two non-negotiables ─────────────────────────────────────────────

case("correct rectangle balances to 0 (no false alarm)",
     lambda: acct_sketch_rect().assert_balanced() == 0)

def _dropped_dim_raises():
    # The bug: a rectangle helper that forgot one of its 4 dims.
    assert acct_sketch_rect(drop_dims=1).dof == 1
    raised = False
    try:
        r = DofTracker("Rect", on_under="raise", log=silent)
        r.add_point(4); r.add_hv(4); r.add_dim(3)   # only 3 of 4 dims
        r.assert_balanced()
    except DofError as e:
        raised = "UNDER-CONSTRAINED" in str(e)
    return raised

case("dropped dimension is caught (DOF>0 raises DofError)", _dropped_dim_raises)


# ── 2. Real generators balance ─────────────────────────────────────────────

case("anchored rectangle balances to 0",
     lambda: acct_rect_anchored().assert_balanced() == 0)

case("base_arch_cut (12-pt spline, FB) balances modulo interiors",
     lambda: acct_base_arch_cut(12).assert_balanced() == 0)

case("base_arch_cut (7-pt spline, LR) balances modulo interiors",
     lambda: acct_base_arch_cut(7).assert_balanced() == 0)

def _interiors_reported():
    t = acct_base_arch_cut(12)
    t.assert_balanced()
    return t._interiors == 10 and "spline_interiors=10" in t.summary()

case("12-pt spline declares 10 exempt interiors in summary", _interiors_reported)


# ── 3. Bugs in the spline generator are caught ─────────────────────────────

case("dropped spline ENDPOINT dim → under-constrained (DOF>0)",
     lambda: acct_base_arch_cut(12, drop_end_dim=True).dof == 1)

case("dropped waste-rail dim → under-constrained (DOF>0)",
     lambda: acct_base_arch_cut(12, drop_rail_dim=True).dof == 1)


# ── 4. Guard never rejects correct geometry (over-count = soft note only) ──

def _overcount_never_raises():
    # Simulate a redundant constraint / extra dim on a closed loop: DOF < 0.
    t = DofTracker("Rect", on_under="raise", on_over="warn", log=silent)
    t.add_point(4); t.add_hv(4); t.add_dim(5)   # one extra dim → DOF = -1
    d = t.assert_balanced()                      # must NOT raise
    return d == -1 and len(t.issues) == 1 and "over-counted" in t.issues[0]

case("over-constrained (DOF<0) yields a soft note, never raises",
     _overcount_never_raises)

def _on_over_raise_forbidden():
    try:
        DofTracker("x", on_over="raise")
    except ValueError:
        return True
    return False

case("on_over='raise' is forbidden by construction", _on_over_raise_forbidden)


# ── 5. Dispatch modes + misc API ───────────────────────────────────────────

def _warn_mode_records_not_raises():
    t = DofTracker("S", on_under="warn", log=silent)
    t.add_point(4); t.add_hv(4); t.add_dim(3)    # DOF = 1
    d = t.assert_balanced()
    return d == 1 and len(t.issues) == 1

case("on_under='warn' records an issue instead of raising",
     _warn_mode_records_not_raises)

def _context_manager_asserts():
    raised = False
    try:
        with DofTracker("S", on_under="raise", log=silent) as t:
            t.add_point(4); t.add_hv(4); t.add_dim(3)   # DOF = 1 → assert on exit
    except DofError:
        raised = True
    return raised

case("context manager asserts on clean exit", _context_manager_asserts)

def _unknown_constraint_raises():
    try:
        DofTracker("S", log=silent).add_constraint("frobnicate")
    except ValueError:
        return True
    return False

case("unknown constraint kind raises ValueError", _unknown_constraint_raises)

def _coincident_and_named_constraints():
    # 3 free points (6 DOF); a coincident (−2) + a perpendicular (−1) + 3 dims.
    t = DofTracker("S", on_under="collect", on_over="collect", log=silent)
    t.add_point(3).add_coincident(1).add_perpendicular(1).add_dim(3)
    return t.dof == 6 - 2 - 1 - 3   # == 0

case("named constraints (coincident/perpendicular) account correctly",
     _coincident_and_named_constraints)

def _null_dof_noops():
    n = NullDof()
    n.add_point(4).add_hv(99).add_dim(3).spline_interior(5)   # all no-ops
    return n.dof == 0 and n.assert_balanced() == 0 and n.balanced

case("NullDof is a silent no-op (guard disabled)", _null_dof_noops)


# ── 6. Slot/stadium (arcs + tangents) accounting ───────────────────────────

def acct_slot(drop_dims=0):
    """sketch_slot / sketch_slot_model: 2 lines (4 pts) + 2 arcs; H/V on the 2
    straight edges; 4 tangents + 4 coincidents joining the line↔arc junctions;
    radial + length + 2 position dims.
      pts 4(lines)+6(arcs)=10 → 20 DOF
      − [2 intrinsic arc radius + 2 H/V + 4 tangent + 8 coincident] = 16
      − 4 dims = 0   (anchored mode swaps the 2 position dims for 2 anchor dims;
                      same count)."""
    t = DofTracker("Slot", on_under="collect", on_over="collect", log=silent)
    t.add_point(4)                       # 2 lines × 2 endpoints
    t.add_arc(2)                         # 2 arcs (5 DOF each via add_arc)
    t.add_hv(2)                          # 2 vertical (or 2 horizontal)
    t.add_constraint("tangent", 4)
    t.add_coincident(4)
    t.add_dim(4 - drop_dims)             # radial + length + 2 position/anchor
    return t

case("slot/stadium balances to 0 (origin or anchored mode)",
     lambda: acct_slot().assert_balanced() == 0)

case("slot with a dropped position dim → under-constrained (DOF>0)",
     lambda: acct_slot(drop_dims=1).dof == 1)

def _add_arc_is_five_dof():
    t = DofTracker("S", on_under="collect", on_over="collect", log=silent)
    t.add_arc(1)                         # net +5 DOF (6 from 3 pts − 1 intrinsic)
    return t.dof == 5

case("add_arc models a single arc as 5 free DOF", _add_arc_is_five_dof)


# ── 7. Global SP_DOF_GUARD switch (default_tracker) ────────────────────────

def _default_tracker_switch():
    import os
    saved = os.environ.get("SP_DOF_GUARD")
    try:
        # default (unset) → raises on under-constraint
        os.environ.pop("SP_DOF_GUARD", None)
        raised = False
        try:
            t = dof.default_tracker("S", log=silent)
            t.add_point(1); t.assert_balanced()      # DOF = 2 > 0
        except DofError:
            raised = True
        # warn → records, no raise
        os.environ["SP_DOF_GUARD"] = "warn"
        tw = dof.default_tracker("S", log=silent)
        tw.add_point(1); dw = tw.assert_balanced()
        warned = (dw == 2 and len(tw.issues) == 1)
        # off → NullDof
        os.environ["SP_DOF_GUARD"] = "off"
        to = dof.default_tracker("S", log=silent)
        to.add_point(1)
        offed = isinstance(to, NullDof) and to.assert_balanced() == 0
        return raised and warned and offed
    finally:
        if saved is None:
            os.environ.pop("SP_DOF_GUARD", None)
        else:
            os.environ["SP_DOF_GUARD"] = saved

case("default_tracker honors SP_DOF_GUARD (raise/warn/off)",
     _default_tracker_switch)


print(f"\n{sum(R)}/{len(R)} cases passed")
sys.exit(0 if all(R) else 1)
