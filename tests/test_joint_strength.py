"""Offline tests for the joint-strength estimator + the wedged-tenon / dovetail
mechanical-interlock model (issue 105).

Pure Python (joint_strength.py imports only `math`, no Fusion). Run:
    python3 tests/test_joint_strength.py

Loads helpers/sp/joint_strength.py DIRECTLY (importlib) to skip the adsk-heavy
helpers.sp package __init__, so it runs anywhere.

Covers:
  * the M&T glue baseline (locks the wood-limited withdrawal number);
  * the interlock free body — value, governing mode, brittle flag, mode ordering;
  * withdrawal = max(glue, interlock) integration (glued vs DRY);
  * THE FIXTURE: wedged-vs-plain-M&T withdrawal difference (the glue-independent floor);
  * undercut-angle monotonicity; fox derate; species sweep (split always governs in wood);
  * the cut-dovetail generalization (sawn-fiber knockdown + tail-neck shear bound);
  * input validation.
"""
import os
import math
import importlib.util

_PATH = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "..", "helpers", "sp", "joint_strength.py"))
_spec = importlib.util.spec_from_file_location("joint_strength", _PATH)
js = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(js)

# Canonical wedged through-tenon (the issue's worked example).
W, T, L = 1.5, 0.5, 2.0            # in: width (along grain) x thickness (across) x depth
SP = "white_oak"


def approx(a, b, tol=2.0):
    return abs(a - b) <= tol


def test_mt_glue_baseline():
    """Plain M&T withdrawal is the wood-limited long-grain glue number (~11.7k lbf).
    Locks the foundation the interlock is compared against."""
    mt = js.estimate_mortise_tenon(W, T, L, species=SP)
    glue = mt["capacities"]["withdrawal_tension"]["value"]
    assert approx(glue, 11675, 5), glue
    assert "GLUE" in mt["capacities"]["withdrawal_tension"]["mechanism"]
    print("  glue baseline: %.0f lbf  OK" % glue)


def test_interlock_free_body():
    """Interlock value, governing mode, brittle flag, and mode ordering."""
    il = js.estimate_interlock(W, T, L, species=SP)
    assert approx(il["value"], 1730, 3), il["value"]
    assert il["governing"] == "split", il["governing"]
    assert il["brittle"] is True
    m = il["modes"]
    assert approx(m["split"], 1730, 3) and approx(m["crush"], 2314, 3) and approx(m["bend"], 7600, 3), m
    # split < crush < bend — the realistic ordering for a continuous-fiber wedge
    assert m["split"] < m["crush"] < m["bend"], m
    # friction-independent hook floor is a positive fraction of the value
    assert 0 < il["contact"]["hook_only_lbf"] < il["value"]
    print("  interlock: %.0f lbf (gov=%s, brittle=%s)  modes %s  OK"
          % (il["value"], il["governing"], il["brittle"], {k: round(v) for k, v in m.items()}))


def test_glue_max_integration():
    """withdrawal = max(glue, interlock): glued -> glue governs (interlock is the floor);
    dry -> interlock IS the withdrawal."""
    glued = js.estimate_wedged_tenon(W, T, L, species=SP, glue=True)
    dry = js.estimate_wedged_tenon(W, T, L, species=SP, glue=False)
    g = glued["capacities"]["withdrawal_tension"]["value"]
    d = dry["capacities"]["withdrawal_tension"]["value"]
    assert approx(g, 11675, 5) and "GLUE" in glued["capacities"]["withdrawal_tension"]["mechanism"]
    assert approx(d, 1730, 3) and "INTERLOCK" in dry["capacities"]["withdrawal_tension"]["mechanism"]
    # the interlock floor is reported on both, identical, glue-independent
    assert approx(glued["interlock_withdrawal"], dry["interlock_withdrawal"], 1)
    assert approx(glued["glue_withdrawal"], 11675, 5)
    print("  max(glue,interlock): glued=%.0f (glue) dry=%.0f (interlock floor)  OK" % (g, d))


def test_fixture_wedged_vs_plain_dry():
    """THE FIXTURE (acceptance): the wedged-vs-plain-M&T withdrawal difference.

    A plain M&T has NO mechanical withdrawal path — it relies ENTIRELY on glue, so
    DRY / glue-failed it pulls out (~0). A wedged tenon adds the interlock floor that
    holds DRY. That glue-independent floor IS 'far stronger than a plain M&T' in the
    regime that matters (failed/absent glue)."""
    plain = js.estimate_mortise_tenon(W, T, L, species=SP)
    wedged = js.estimate_wedged_tenon(W, T, L, species=SP)
    # plain M&T exposes no interlock path at all
    assert "interlock_withdrawal" not in plain
    # wedged dry floor is substantial and glue-independent; plain dry floor is ~0
    floor = wedged["interlock_withdrawal"]
    assert floor > 1000, floor
    # with a perfect glue line both reach the same wood-limited glue ceiling (honest:
    # the wedge does NOT beat a sound glue line on raw lbf — it insures against its loss)
    assert approx(plain["capacities"]["withdrawal_tension"]["value"],
                  wedged["glue_withdrawal"], 5)
    print("  FIXTURE wedged-vs-plain (DRY): wedged floor=%.0f lbf vs plain ~0 (glue-only)  OK"
          % floor)
    print("            (glued, both reach the same %.0f lbf glue ceiling)"
          % wedged["glue_withdrawal"])


def test_undercut_monotonic():
    """Interlock increases with the undercut angle in the realistic band; stays split-governed."""
    vals = [js.estimate_interlock(W, T, L, species=SP, undercut_deg=th)["value"]
            for th in (4, 8, 12, 16)]
    assert vals == sorted(vals) and vals[0] < vals[-1], vals
    print("  undercut sweep 4-16 deg: %s  OK" % [round(v) for v in vals])


def test_fox_derate():
    """Fox (blind) wedging derates the achieved spread vs a driven-to-seat through wedge."""
    thru = js.estimate_interlock(W, T, L, species=SP, fox=False)["value"]
    fox = js.estimate_interlock(W, T, L, species=SP, fox=True)["value"]
    assert approx(fox, thru * js.FOX_WEDGE_FACTOR, 2), (fox, thru)
    assert fox < thru
    print("  fox derate: through=%.0f fox=%.0f (x%.2f)  OK" % (thru, fox, js.FOX_WEDGE_FACTOR))


def test_species_split_governs():
    """For clear wood tens_perp < comp_perp, so the wedge is ALWAYS split-governed (brittle) —
    the flare-crush bound is a higher ceiling. This is the issue's 'fails by mortise-cheek
    splitting' result, correctly producing the brittle flag for every species."""
    for sp in js.SPECIES:
        il = js.estimate_interlock(W, T, L, species=sp)
        assert il["governing"] == "split" and il["brittle"] is True, (sp, il["governing"])
        assert il["modes"]["crush"] > il["modes"]["split"], sp
    print("  all %d species: split-governed + brittle  OK" % len(js.SPECIES))


def test_dovetail_generalization():
    """Cut dovetail: same wall statics, but sawn fiber knocks the bend reserve down and
    adds a tail-neck shear bound. A thin-necked tail fails by tail-neck shear (not split),
    exercising the non-brittle path + the cut-face-vs-continuous-fiber distinction."""
    dt = js.estimate_dovetail(3.0, 0.75, 0.75, species=SP, dovetail_deg=9.5)
    assert "tail_neck" in dt["modes"], dt["modes"]
    # sawn bend reserve is knocked down vs the continuous-fiber equivalent (same geometry,
    # so identical flare_delta — the ONLY difference is the fiber-continuity factor).
    ddelta = 0.75 * math.tan(math.radians(9.5))
    cont = js.estimate_interlock(3.0, 0.75, 0.75, species=SP, undercut_deg=9.5,
                                 kerf_fraction=1.0, n_halves=1, continuous_fiber=True,
                                 flare_delta=ddelta)
    assert dt["modes"]["bend"] < cont["modes"]["bend"], (dt["modes"]["bend"], cont["modes"]["bend"])
    assert approx(dt["modes"]["bend"], js.DOVETAIL_FIBER_KNOCKDOWN * cont["modes"]["bend"], 5)
    # a thin-necked tail shears off at the neck -> tail_neck governs (a non-split mode)
    thin = js.estimate_dovetail(3.0, 0.75, 0.75, species=SP, dovetail_deg=9.5,
                                tail_neck_thickness=0.1)
    assert thin["governing"] == "tail_neck", thin["governing"]
    assert thin["brittle"] is False
    print("  dovetail: gov=%s, thin-neck gov=%s, bend knocked %.2f  OK"
          % (dt["governing"], thin["governing"], js.DOVETAIL_FIBER_KNOCKDOWN))


def test_input_validation():
    for bad in (dict(width=0), dict(thickness=-1), dict(depth=0), dict(undercut_deg=0),
                dict(undercut_deg=60), dict(species="unobtanium")):
        kw = dict(width=W, thickness=T, depth=L, species=SP)
        kw.update(bad)
        try:
            js.estimate_interlock(**kw)
            assert False, "expected ValueError for %s" % bad
        except ValueError:
            pass
    print("  input validation: rejects bad geometry/angle/species  OK")


def run():
    print("test_joint_strength (interlock model, issue 105)")
    for fn in (test_mt_glue_baseline, test_interlock_free_body, test_glue_max_integration,
               test_fixture_wedged_vs_plain_dry, test_undercut_monotonic, test_fox_derate,
               test_species_split_governs, test_dovetail_generalization, test_input_validation):
        fn()
    print("ALL PASS")


if __name__ == "__main__":
    run()
