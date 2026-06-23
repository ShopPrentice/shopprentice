#!/usr/bin/env python3
"""Offline joinery strength report for the joints declared in model.json.

This is a convenience demo. The build-time check is the real gate: with the
`joints` array in model.json (joint-registry schema), `validate_deps` /
`validate_design` runs `helpers/sp/joint_registry.validate_joints` on every
build (per-type M&T sizing + grain, plus relish tear-out >= 4xD and EYM peg
capacity for pegged/drawbore joints).

Here we just load the repo's estimator directly (importlib, to skip the
adsk-heavy `helpers.sp` package init -- same trick the offline tests use) and
print full capacity numbers for each declared M&T:

    python3 strength_check.py
"""
import json
import os
import re
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
_JS = os.path.normpath(os.path.join(HERE, "..", "..", "helpers", "sp", "joint_strength.py"))
_spec = importlib.util.spec_from_file_location("joint_strength", _JS)
js = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(js)

_MT_TYPES = {"mortise_tenon", "pegged_tenon", "drawbore", "wedged_tenon"}


def inch(expr):
    """Resolve a literal length expression ('3.5 in') to inches. None passes through."""
    if expr is None:
        return None
    return float(re.sub(r"[^0-9.\-]", "", str(expr)))


model = json.load(open(os.path.join(HERE, "model.json")))
joints = model.get("joints", [])
print("JOINERY STRENGTH CHECK  --  %s   (%d declared M&T joints)\n"
      % (model.get("name", "model"), len(joints)))

for j in joints:
    typ = j.get("type")
    print("=" * 72)
    print("%-26s [%s]   %s -> %s" % (
        "%s~%s" % (j.get("tenon"), j.get("mortise")), typ, j.get("tenon"), j.get("mortise")))
    if typ not in _MT_TYPES:
        print("  (no closed-form estimator for this type)\n")
        continue

    peg_sp, note = j.get("peg_species"), ""
    if peg_sp and peg_sp not in js.SPECIES:
        note = "  (peg %s -> 'hardwood' proxy)" % peg_sp
        peg_sp = "hardwood"

    r = js.estimate_mortise_tenon(
        width=inch(j["width"]), thickness=inch(j["thickness"]), depth=inch(j["depth"]),
        species=j.get("species", "hardwood"),
        pins=int(j.get("pins", 0) or 0), pin_dia=inch(j.get("pin_dia")) or 0.0,
        peg_species=peg_sp, pin_end_distance=inch(j.get("pin_end_distance")))
    c = r["capacities"]
    pw = c.get("pin_withdrawal", {}).get("value", 0.0)

    print("  tenon %s x %s x %s   %s, %s x %s pin%s" % (
        j["width"], j["thickness"], j["depth"], j.get("species"),
        j.get("pins"), j.get("pin_dia"), note))
    print("  pull-out, drawbored (pins):  %6.0f lbf   [%s]" % (pw, r["pin_modes"].get("governing", "-")))
    print("  shear, gravity direction:    %6.0f lbf" % c["shear_along_w"]["value"])
    print("  bending (about tenon width): %6.0f in-lbf" % c["bending_about_w"]["value"])
    for nt in r["notes"]:
        if "BRITTLE" in nt:
            print("  !! " + nt)
    print()
