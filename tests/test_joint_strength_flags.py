"""Offline tests for the pure per-type flag cores (issue 106).

Pure Python — no Fusion required. Run: python3 tests/test_joint_strength_flags.py

Covers joint_strength.mortise_tenon_flags + pegged_flags — the shared cores behind
both the build-time gate (mating.validate_*) and the declarative registry check
(joint_registry.validate_joint). They take dimensions in INCHES and return flag lists.
"""
import os, sys, types, importlib.util

for m in ("adsk", "adsk.core", "adsk.fusion"):
    sys.modules.setdefault(m, types.ModuleType(m))

_JS = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "helpers", "sp", "joint_strength.py"))
spec = importlib.util.spec_from_file_location("joint_strength", _JS)
js = importlib.util.module_from_spec(spec)
spec.loader.exec_module(js)

R = []
def check(name, cond):
    R.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name)

def has(flags, needle):
    return any(needle in f for f in flags)

# --- mortise_tenon_flags ------------------------------------------------------
# Healthy tenon: 2 wide x 0.75 thick x 1.5 deep — no flags.
r = js.mortise_tenon_flags(2.0, 0.75, 1.5, species="white_oak")
check("healthy M&T: no flags", r["flags"] == [])
check("healthy M&T: weakest is a capacity name", r["weakest"] in r["est"]["capacities"])

# Thin slice: thickness < 0.25 * width.
r = js.mortise_tenon_flags(3.0, 0.4, 1.0, species="white_oak")
check("thin slice flagged (t < 0.25w)", has(r["flags"], "thin slice"))

# Very thin tenon: t < 3/16 in (and also a thin slice).
r = js.mortise_tenon_flags(2.0, 0.125, 1.0, species="white_oak")
check("very thin tenon flagged (t < 3/16)", has(r["flags"], "very thin tenon"))

# Overload: tiny tenon, big expected withdrawal load.
r = js.mortise_tenon_flags(0.5, 0.5, 0.5, species="soft_pine",
                           expected={"withdrawal_tension": 1e6})
check("overload flagged when expected > capacity", has(r["flags"], "OVERLOADED"))
check("overload utilization recorded > 1", r["utilization"].get("withdrawal_tension", 0) > 1.0)

# A correctly-sized tenon under a modest expected load: no overload.
r = js.mortise_tenon_flags(2.0, 0.75, 1.5, species="white_oak",
                           expected={"withdrawal_tension": 100.0})
check("modest load: no overload flag", not has(r["flags"], "OVERLOADED"))

# Grain orientation is NOT this function's job (geometric — lives in mating).
r = js.mortise_tenon_flags(0.75, 2.0, 1.5, species="white_oak")   # t>w by number
check("flagger does NOT emit grain-orientation (geometric check elsewhere)",
      not has(r["flags"], "grain orientation"))

# --- pegged_flags -------------------------------------------------------------
# Brittle relish: end distance < 4 * D.
r = js.pegged_flags(1, 0.375, 0.5, species="white_oak")
check("brittle relish flagged (end < 4D)", has(r["flags"], "relish"))

# Adequate relish: end distance >= 4 * D -> no relish flag.
r = js.pegged_flags(1, 0.375, 2.0, species="white_oak")
check("adequate relish: no flag", not has(r["flags"], "relish"))

# With tenon dims -> EYM pin_modes + pin_withdrawal computed.
r = js.pegged_flags(1, 0.375, 2.0, species="white_oak",
                    tenon_width=2.0, tenon_thickness=0.75, tenon_depth=1.5)
check("pegged with dims: pin_modes populated", "governing" in r["pin_modes"])
check("pegged with dims: pin_withdrawal > 0", r["pin_withdrawal"] > 0)

# Without tenon dims -> relish check only, no pin_modes.
r = js.pegged_flags(1, 0.375, 0.5)
check("pegged w/o dims: relish still checked", has(r["flags"], "relish"))
check("pegged w/o dims: no pin_modes", r["pin_modes"] == {})

print("\n%d/%d cases passed" % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
