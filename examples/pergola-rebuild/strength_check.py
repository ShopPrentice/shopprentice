#!/usr/bin/env python3
"""Joinery strength check, tied to model.json.

Reads the `joints` array from model.json and runs the joinery strength
estimator (vendored joint_strength.py) on each drawbore mortise-and-tenon.
Pure Python — no Fusion needed.

    python3 strength_check.py

Capacities are first-order engineering estimates (USDA Wood Handbook order of
magnitude) for relative comparison, not a code-stamped analysis.
"""
import json
import os
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "joint_strength", os.path.join(HERE, "joint_strength.py"))
js = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(js)

model = json.load(open(os.path.join(HERE, "model.json")))
joints = model.get("joints", [])

print("JOINERY STRENGTH CHECK  —  %s" % model.get("name", "model"))
print("%d joints declared in model.json\n" % len(joints))

for j in joints:
    typ, name = j["type"], j["name"]
    print("=" * 72)
    print("%-22s [%s]   %s" % (name, typ, " <-> ".join(j["members"])))

    if typ != "drawbore_mt":
        print("  %s" % j.get("note", "(no estimator for this joint type)"))
        print()
        continue

    t, pg = j["tenon"], j.get("pegs", {})
    depth = t["depth"]
    frac = pg.get("from_shoulder_frac", 0.333)
    # joint_strength's species table; substitute unknown peg woods (e.g. teak)
    peg_sp = pg.get("species")
    peg_note = ""
    if peg_sp and peg_sp not in js.SPECIES:
        peg_note = " (%s -> 'hardwood' proxy)" % peg_sp
        peg_sp = "hardwood"

    r = js.estimate_mortise_tenon(
        width=t["w"], thickness=t["t"], depth=depth, species=j["species"],
        pins=pg.get("count", 0), pin_dia=pg.get("dia", 0.0),
        peg_species=peg_sp, pin_end_distance=depth * (1.0 - frac))
    c = r["capacities"]
    pw = c.get("pin_withdrawal", {}).get("value", 0.0)

    print("  tenon %.2f x %.2f x %.2f in   %s,  %d x %.3f\" peg%s" % (
        t["w"], t["t"], depth, j["species"], pg.get("count", 0), pg.get("dia", 0), peg_note))
    print("  pull-out, drawbored (pegs):  %6.0f lbf   [%s]" % (pw, r["pin_modes"].get("governing", "-")))
    print("  shear, gravity direction:    %6.0f lbf" % c["shear_along_w"]["value"])
    print("  bending (about tenon width): %6.0f in-lbf" % c["bending_about_w"]["value"])
    print("  pull-out IF glued:           %6.0f lbf" % c["withdrawal_tension"]["value"])
    for note in r["notes"]:
        if "BRITTLE" in note:
            print("  !! " + note)
    print()

print("=" * 72)
print("Note: members white oak; teak pegs estimated as 'hardwood'. Switch the")
print("structure to a softwood (cedar) and the wood shear/bearing modes drop")
print("~40-50%, but peg pull-out stays peg-shear-limited.")
