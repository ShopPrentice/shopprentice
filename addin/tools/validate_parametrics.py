"""
Parameter Robustness Check Tool

Verifies the model survives parameter changes: perturbs each LEAF user
parameter by a narrow amount (default ±5%, ±1 for unitless counts), one
at a time, recomputes, compares against a baseline snapshot, and reverts.

Why narrow, one-at-a-time, no ranges: parameters carry no range metadata
and inventing ranges per design is busywork. The bug classes this catches
— baked literal positions, anchor dims that flipped sides, cuts that only
barely intersect their target, stranded "(1)" lumps after a JOIN missed —
all reveal themselves at small perturbations. (Limitation: an expression
that only crosses zero at a large excursion won't show at ±5%; this is a
local-robustness probe, not an envelope test.)

What "survived" means — after each perturbation the model must show:
  - no missing bodies            (parts vanishing)
  - no new bodies                (stranded "(1)" lumps from displaced joinery)
  - no features newly in warning/error health
  - no cuts that became zero-impact (profile no longer reaches its target)
  - no increase in real interference count (displaced tenons overlap)
  - no body losing ALL bounding-box contact (parts left floating in air)
and after the revert, body volumes must match the baseline exactly —
otherwise the sweep ABORTS (the document did not round-trip) so a broken
document is never mutated further.

Crash safety: parameter recomputes themselves don't hard-crash Fusion —
failures surface as feature health states and body changes, all of which
revert with the expression. The known hard-crash vector in this add-in's
history is stale viewport selections referencing rebuilt geometry, so the
sweep clears ui.activeSelections before every change.

This is a MUTATING, comparatively slow check (3 recomputes per parameter)
— it is deliberately a separate tool from validate_design (read-only,
run after every phase). Run this before final delivery or after a big
refactor.
"""

import re
import traceback
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register
import adsk.core
import adsk.fusion

from .validate_design import _check_feature_impact, _check_interference

app = adsk.core.Application.get()

# literal numeric expression, optionally with a unit: "60 in", "0.125 in", "3"
_LITERAL_RE = re.compile(r"^\s*-?\d+(\.\d+)?\s*([a-zA-Z]+)?\s*$")
BB_TOUCH_TOL = 0.05  # cm — bbox contact tolerance for the floating check


def _leaf_params(design, only=None):
    """User parameters with literal expressions. Derived parameters
    (expressions referencing other parameters) are skipped — perturbing
    them would overwrite the design's formulas."""
    out = []
    ups = design.userParameters
    for i in range(ups.count):
        p = ups.item(i)
        if only and p.name not in only:
            continue
        if not _LITERAL_RE.match(p.expression or ""):
            continue
        if abs(p.value) < 1e-9:
            continue  # multiplying zero changes nothing
        out.append(p)
    return out


def _snapshot_bodies(root):
    snap = {}

    def entry(b):
        bb = b.boundingBox
        return {
            "volume": b.volume,
            "bb": [bb.minPoint.x, bb.minPoint.y, bb.minPoint.z,
                   bb.maxPoint.x, bb.maxPoint.y, bb.maxPoint.z],
        }

    for i in range(root.bRepBodies.count):
        b = root.bRepBodies.item(i)
        try:
            snap["root/" + b.name] = entry(b)
        except Exception:
            pass
    for occ in root.allOccurrences:
        comp = occ.component
        for i in range(comp.bRepBodies.count):
            b = comp.bRepBodies.item(i)
            try:
                proxy = b.createForAssemblyContext(occ)
                snap[occ.fullPathName + "/" + b.name] = entry(proxy)
            except Exception:
                pass
    return snap


def _bb_touch(b1, b2, tol=BB_TOUCH_TOL):
    for ax in range(3):
        if b1[ax + 3] + tol < b2[ax]:
            return False
        if b2[ax + 3] + tol < b1[ax]:
            return False
    return True


def _isolated_bodies(snap, exclude_prefixes):
    """Bodies whose bounding box touches no other body's — a cheap proxy
    for 'left floating in air' (e.g. a part at a baked position after the
    rest of the model moved)."""
    names = [n for n in snap
             if not any(n.split("/")[-1].startswith(p)
                        for p in exclude_prefixes)]
    iso = set(names)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if _bb_touch(snap[names[i]]["bb"], snap[names[j]]["bb"]):
                iso.discard(names[i])
                iso.discard(names[j])
    return iso


def _baseline(design, root, prefixes):
    impact = _check_feature_impact(design)
    snap = _snapshot_bodies(root)
    return {
        "bodies": snap,
        "unhealthy": {u["feature"] for u in impact["unhealthyFeatures"]},
        "zero": {z["feature"] for z in impact["zeroImpactFeatures"]},
        "interference": _check_interference(root, prefixes)["realCount"],
        "isolated": _isolated_bodies(snap, prefixes),
    }


def _compare(base, design, root, prefixes):
    """Issues introduced by the current parameter state vs the baseline."""
    issues = []
    snap = _snapshot_bodies(root)

    missing = sorted(set(base["bodies"]) - set(snap))
    if missing:
        issues.append("bodies MISSING: " + ", ".join(missing))
    new = sorted(set(snap) - set(base["bodies"]))
    if new:
        issues.append("NEW/stranded bodies appeared: " + ", ".join(new))

    impact = _check_feature_impact(design)
    unhealthy = [u for u in impact["unhealthyFeatures"]
                 if u["feature"] not in base["unhealthy"]]
    if unhealthy:
        issues.append("features now unhealthy: " + "; ".join(
            f"{u['feature']} ({u['state']}: {u['message'][:80]})"
            for u in unhealthy))
    zero = [z for z in impact["zeroImpactFeatures"]
            if z["feature"] not in base["zero"]]
    if zero:
        issues.append("features became ZERO-IMPACT: " + ", ".join(
            z["feature"] for z in zero))

    inter = _check_interference(root, prefixes)["realCount"]
    if inter > base["interference"]:
        issues.append(f"real interference count {base['interference']} "
                      f"-> {inter}")

    floating = _isolated_bodies(snap, prefixes) - base["isolated"]
    if floating:
        issues.append("bodies lost all contact (floating): "
                      + ", ".join(sorted(floating)))
    return issues


def _restored(base_bodies, root, tol=1e-3):
    snap = _snapshot_bodies(root)
    if set(snap) != set(base_bodies):
        return False
    for name, e in base_bodies.items():
        if abs(snap[name]["volume"] - e["volume"]) > tol:
            return False
    return True


def handler(params: list = None, percent: float = None,
            both_directions: bool = None,
            exclude_prefixes: list = None) -> dict:
    """Perturb each leaf user parameter, compare, revert, report."""
    import json
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return {"content": [{"type": "text", "text": "No active design"}],
                    "isError": True, "message": "No active design"}
        root = design.rootComponent
        ui = app.userInterface
        prefixes = exclude_prefixes or ["DM_"]
        pct = (percent if percent is not None else 5.0) / 100.0
        both = both_directions if both_directions is not None else True

        leafs = _leaf_params(design, set(params) if params else None)
        if not leafs:
            return {"content": [{"type": "text",
                                 "text": "No leaf parameters to test"}],
                    "isError": False, "message": "No leaf parameters to test"}

        ui.activeSelections.clear()
        base = _baseline(design, root, prefixes)

        fragile = []
        tested = []
        aborted = None

        for p in leafs:
            orig = p.expression
            unitless = (p.unit or "") == ""
            if unitless:
                # counts: step by ±1, not a percentage
                steps = [("+1", f"({orig}) + 1")]
                if both and p.value > 1:
                    steps.append(("-1", f"({orig}) - 1"))
            else:
                steps = [(f"+{pct * 100:g}%", f"({orig}) * {1 + pct}")]
                if both:
                    steps.append((f"-{pct * 100:g}%", f"({orig}) * {1 - pct}"))

            entry = {"parameter": p.name, "original": orig, "issues": {}}
            for label, expr in steps:
                # stale selections referencing rebuilt geometry are the
                # known Fusion hard-crash vector — clear before changing
                ui.activeSelections.clear()
                try:
                    p.expression = expr
                    adsk.doEvents()
                    issues = _compare(base, design, root, prefixes)
                    if issues:
                        entry["issues"][label] = issues
                except Exception as e:
                    entry["issues"][label] = [
                        f"EXCEPTION during recompute: {e}"]
                finally:
                    try:
                        p.expression = orig
                        adsk.doEvents()
                    except Exception as re_err:
                        aborted = (f"could not revert {p.name}: {re_err} — "
                                   f"sweep stopped, restore the document "
                                   f"(Undo) before continuing")
                if aborted:
                    break

            if not aborted and not _restored(base["bodies"], root):
                entry["issues"]["revert"] = [
                    "model did NOT return to baseline after revert"]
                aborted = (f"baseline not restored after testing {p.name} — "
                           f"sweep stopped to avoid mutating a broken "
                           f"document; Undo to recover")

            tested.append(p.name)
            if entry["issues"]:
                fragile.append(entry)
            if aborted:
                break

        passed = (not fragile) and (aborted is None)
        ups = design.userParameters
        derived = [ups.item(i).name for i in range(ups.count)
                   if not _LITERAL_RE.match(ups.item(i).expression or "")]
        result = {
            "passed": passed,
            "testedParameters": tested,
            "skippedDerived": derived,
            "fragileParameters": fragile,
        }
        if aborted:
            result["aborted"] = aborted

        if passed:
            msg = (f"PASSED: {len(tested)} parameter(s) perturbed "
                   f"{'±' if both else '+'}{pct * 100:g}% and reverted "
                   f"cleanly — no missing/new bodies, no new warnings, no "
                   f"zero-impact cuts, no interference, no floating parts")
        else:
            names = ", ".join(f["parameter"] for f in fragile)
            msg = f"FAILED: fragile parameter(s): {names}"
            if aborted:
                msg += f" — ABORTED: {aborted}"

        return {"content": [{"type": "text",
                             "text": json.dumps(result, indent=2)}],
                "isError": False, "message": msg}

    except Exception as e:
        app.log(f"validate_parametrics error: {e}\n{traceback.format_exc()}")
        return {"content": [{"type": "text",
                             "text": f"Error: {e}\n{traceback.format_exc()}"}],
                "isError": True, "message": "validate_parametrics failed"}


TOOL_DESCRIPTION = \
"""Check that the model survives parameter changes (parametric robustness).

Perturbs each LEAF user parameter (literal expressions like "60 in" —
derived formulas are skipped) one at a time by a narrow step (default
±5%; ±1 for unitless counts), recomputes, compares against a baseline,
and reverts. THE DOCUMENT IS MUTATED DURING THE SWEEP and restored
parameter-by-parameter; if the model fails to return to baseline the
sweep aborts immediately and tells you to Undo.

A parameter is flagged FRAGILE if its perturbation causes any of:
- missing bodies (parts vanish)
- new/stranded bodies (the displaced-joinery "(1)"-lump signature)
- features newly in warning/error health
- cuts that become zero-impact (profile no longer reaches its target)
- an increase in real interference count
- a body losing all bounding-box contact (left floating at a baked position)

This is a local-robustness probe, not an envelope test: expressions that
only break at large excursions (e.g. a sign flip at -40%) won't show at
±5%. It is slower than validate_design (3 recomputes per parameter) —
run it before final delivery, not after every phase."""

tool = Tool.create_simple(
    name="validate_parametrics",
    description=TOOL_DESCRIPTION
).add_input_property(
    "params",
    {
        "type": "array",
        "description": "Parameter names to test (default: all leaf user "
                       "parameters).",
        "items": {"type": "string"}
    }
).add_input_property(
    "percent",
    {
        "type": "number",
        "description": "Perturbation size in percent (default 5).",
    }
).add_input_property(
    "both_directions",
    {
        "type": "boolean",
        "description": "Test both +percent and -percent (default true).",
    }
).add_input_property(
    "exclude_prefixes",
    {
        "type": "array",
        "description": "Body name prefixes excluded from body checks "
                       "(default: [\"DM_\"]).",
        "items": {"type": "string"}
    }
)

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
