#!/usr/bin/env python3
"""
Search-Based Script Builder v2 — Incremental Per-Feature
=========================================================
Resolves ambiguous feature reconstructions by executing each feature
incrementally on a scratch document and comparing body volumes against
per-step ground truth from the original design.

Key improvements over v1:
- Incremental: one feature at a time, not full-script-per-variant
- Per-step validation: catches errors at the source
- Split/Remove support: handles all feature types
- Document management: works on scratch docs, never touches saved docs

Usage:
    # From live Fusion design (capture + build):
    python tools/search_build.py --from-fusion -o /tmp/rebuilt.py -v

    # From saved capture JSON:
    python tools/search_build.py --capture capture.json -o /tmp/rebuilt.py

    # Dry-run: show ambiguous features without executing:
    python tools/search_build.py --capture capture.json --dry-run

Requires: Fusion 360 running with MCP server on localhost:9100
"""
import argparse
import json
import os
import sys
import time

# Add addin/tools to import path for _script_generator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "addin", "tools"))
from _script_generator import (
    generate_script,
    generate_with_choices,
    get_ambiguous_features,
    generate_prefix_script,
    generate_feature_script,
)

MCP_URL = os.environ.get("MCP_URL", "http://localhost:9100")
VOLUME_TOLERANCE_PCT = 0.01  # strict: 0.01% = essentially exact match


def _set_tolerance(val):
    global VOLUME_TOLERANCE_PCT
    VOLUME_TOLERANCE_PCT = val


# ── MCP helpers ──────────────────────────────────────────────────

def mcp(tool, **args):
    """Call an MCP tool via HTTP JSON-RPC."""
    import subprocess
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": args},
    })
    r = subprocess.run(
        ["curl", "-s", "-X", "POST", MCP_URL,
         "-H", "Content-Type: application/json", "-d", payload],
        capture_output=True, text=True, timeout=300,
    )
    if r.returncode != 0:
        raise RuntimeError(f"curl failed: {r.stderr}")
    resp = json.loads(r.stdout)
    if "error" in resp:
        raise RuntimeError(f"JSON-RPC error: {resp['error']}")
    return resp["result"]


def mcp_text(tool, **args):
    """Call MCP tool and return parsed text content."""
    result = mcp(tool, **args)
    if result.get("isError"):
        msg = result.get("content", [{}])[0].get("text", "?")
        raise RuntimeError(f"MCP error: {msg[:200]}")
    text = result["content"][0]["text"]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def get_body_state(data):
    """Extract {name: {volume, boundingBox}} from timeline state or capture data."""
    bodies = {}
    if "components" in data:
        def walk(comp):
            for b in comp.get("bodies", []):
                name = b.get("name", "?")
                bodies[name] = {
                    "volume": b.get("volume", 0),
                    "boundingBox": b.get("boundingBox", {}),
                }
            for child in comp.get("children", []):
                walk(child)
        walk(data["components"])
    elif "bodyVolumes" in data:
        for name, vol in data["bodyVolumes"].items():
            bodies[name] = {"volume": vol, "boundingBox": {}}
    return bodies


def get_body_volumes(data):
    """Extract {name: volume} — convenience wrapper."""
    return {n: b["volume"] for n, b in get_body_state(data).items()}


def get_body_volumes_from_sandbox(sandbox_result):
    """Extract {name: volume} from sandbox execute_script result."""
    if sandbox_result.get("isError"):
        return None
    snapshot = sandbox_result.get("snapshot", {})
    return snapshot.get("bodyVolumes", {})


BB_TOLERANCE_CM = 0.05  # bounding box tolerance in cm (mirrors can shift slightly)


def states_match(expected, actual, tolerance_pct=None):
    """Check if body states match exactly: count, names, volumes, bounding boxes.

    Requires 100% match:
    - Same body count (no extra, no missing)
    - Each body volume within tolerance (default 0.01%)
    - Each body bounding box within BB_TOLERANCE_CM

    Uses fuzzy name matching for split-renamed bodies.
    Returns (match: bool, details: list[str])
    """
    if tolerance_pct is None:
        tolerance_pct = VOLUME_TOLERANCE_PCT
    if actual is None:
        return False, ["execution failed"]

    details = []
    all_match = True
    matched_actual = set()

    # Pass 1: exact name matches
    unmatched_expected = {}
    for name, exp in expected.items():
        act = actual.get(name)
        if act is not None:
            matched_actual.add(name)
            ok, msgs = _compare_body(name, exp, act, tolerance_pct)
            details.extend(msgs)
            if not ok:
                all_match = False
        else:
            unmatched_expected[name] = exp

    # Pass 2: fuzzy match by volume for split-renamed bodies
    unmatched_actual = {n: v for n, v in actual.items() if n not in matched_actual}
    for exp_name, exp in list(unmatched_expected.items()):
        best_name, best_pct = None, float("inf")
        for act_name, act in unmatched_actual.items():
            exp_v, act_v = exp["volume"], act["volume"]
            pct = abs(act_v - exp_v) / abs(exp_v) * 100 if exp_v != 0 else (0 if act_v == 0 else 100)
            if pct < best_pct:
                best_pct, best_name = pct, act_name
        if best_name is not None and best_pct <= tolerance_pct:
            act = unmatched_actual.pop(best_name)
            del unmatched_expected[exp_name]
            ok, msgs = _compare_body(f"{exp_name} ~> {best_name}", exp, act, tolerance_pct)
            details.extend(msgs)
            if not ok:
                all_match = False

    # Strict: extra and missing bodies are failures
    for name, exp in unmatched_expected.items():
        details.append(f"  MISSING: {name} (vol={exp['volume']:.4f})")
        all_match = False
    for name, act in unmatched_actual.items():
        details.append(f"  EXTRA: {name} (vol={act['volume']:.4f})")
        all_match = False

    return all_match, details


def _compare_body(label, exp, act, tolerance_pct):
    """Compare one body's volume and bounding box. Returns (ok, messages)."""
    msgs = []
    ok = True
    exp_v, act_v = exp["volume"], act["volume"]
    if exp_v == 0:
        delta_pct = 0 if act_v == 0 else 100
    else:
        delta_pct = abs(act_v - exp_v) / abs(exp_v) * 100

    exp_bb = exp.get("boundingBox", {})
    act_bb = act.get("boundingBox", {})
    bb_ok = True
    if exp_bb and act_bb:
        for key in ("min", "max"):
            ep = exp_bb.get(key, [0, 0, 0])
            ap = act_bb.get(key, [0, 0, 0])
            for i in range(3):
                if abs(ep[i] - ap[i]) > BB_TOLERANCE_CM:
                    bb_ok = False

    vol_ok = delta_pct <= tolerance_pct
    if vol_ok:
        # Volume matches — accept even if bb differs (name swap from mirror)
        if not bb_ok:
            msgs.append(f"  + {label}: vol={exp_v:.4f} ({delta_pct:.3f}%) (bb differs, likely name swap)")
        else:
            msgs.append(f"  + {label}: vol={exp_v:.4f} ({delta_pct:.3f}%)")
    else:
        parts = [f"vol {exp_v:.4f}->{act_v:.4f} ({delta_pct:.2f}%)"]
        if not bb_ok:
            parts.append(f"bb mismatch")
        msgs.append(f"  x {label}: {', '.join(parts)}")
        ok = False
    return ok, msgs


def state_error(expected, actual):
    """Aggregate error score from body state comparison (lower is better)."""
    if actual is None:
        return float("inf")
    # Body count mismatch penalty
    score = abs(len(expected) - len(actual)) * 100
    remaining = dict(actual)
    for name, exp_body in expected.items():
        exp = exp_body["volume"]
        act_body = remaining.pop(name, None)
        if act_body is None:
            # Fuzzy match
            best_n, best_pct = None, float("inf")
            for rn, rb in remaining.items():
                rv = rb["volume"]
                pct = abs(rv - exp) / abs(exp) * 100 if exp != 0 else (0 if rv == 0 else 100)
                if pct < best_pct:
                    best_pct, best_n = pct, rn
            if best_n is not None and best_pct < 50:
                act_body = remaining.pop(best_n)
            else:
                score += 100
                continue
        act = act_body["volume"]
        if exp != 0:
            score += abs(act - exp) / abs(exp) * 100
        elif act != 0:
            score += 100
    return score


# ── Document management ──────────────────────────────────────────

def ensure_scratch_doc(verbose=False):
    """Switch to an existing unsaved doc, or create one if none exist.

    Never touches user-saved documents. Reuses existing untitled docs
    to avoid document proliferation. Verifies the switch succeeded.
    """
    if verbose:
        print("Switching to scratch document...")
    try:
        list_result = mcp("manage_documents", action="list")
        docs = json.loads(list_result["content"][0]["text"])
    except Exception:
        docs = []

    # Check if already on an unsaved doc
    active = next((d for d in docs if d["isActive"]), None)
    if active and not active["isSaved"]:
        if verbose:
            print(f"  Reusing: {active['name']}")
        _verify_active_unsaved()
        return active

    # Try to activate an existing unsaved doc
    for d in docs:
        if not d["isSaved"] and not d["isActive"]:
            mcp("manage_documents", action="activate", index=d["index"])
            if verbose:
                print(f"  Reusing: {d['name']}")
            _verify_active_unsaved()
            return d

    # No unsaved doc exists — create one
    mcp("manage_documents", action="new")
    if verbose:
        print(f"  Created new scratch doc")
    _verify_active_unsaved()
    return None


def _verify_active_unsaved():
    """Safety check: abort if the active document is saved (user data).

    This prevents clean=True from destroying a user's saved design.
    """
    try:
        list_result = mcp("manage_documents", action="list")
        docs = json.loads(list_result["content"][0]["text"])
        active = next((d for d in docs if d["isActive"]), None)
        if active and active["isSaved"]:
            print(f"\nFATAL: Active document '{active['name']}' is SAVED. "
                  f"Refusing to proceed — would destroy user data.")
            sys.exit(2)
    except Exception:
        print("\nFATAL: Cannot verify active document is unsaved. Aborting.")
        sys.exit(2)


def get_timeline_count():
    """Get current timeline item count via get_timeline_state."""
    try:
        result = mcp_text("get_timeline_state", index=-1)
        return result.get("timelineCount", -1)
    except Exception:
        return -1


def undo_timeline_items(count):
    """Delete the last `count` timeline items."""
    if count <= 0:
        return
    script = f'''
import adsk.core, adsk.fusion
def run(context):
    design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
    tl = design.timeline
    for _ in range({count}):
        if tl.count > 0:
            tl.item(tl.count - 1).entity.deleteMe()
'''
    mcp("execute_script", script=script, sandbox=False)


# ── Ground truth collection ──────────────────────────────────────

def collect_ground_truth(capture, verbose=False):
    """Collect per-feature body state from the original design.

    Calls get_timeline_state for each non-rolled-back feature.
    Returns dict: {feature_index: {body_name: {volume, boundingBox}}}
    """
    timeline = capture.get("timeline", [])
    if verbose:
        print(f"\nCollecting ground truth ({len(timeline)} features)...")

    ground_truth = {}
    for fi, feat in enumerate(timeline):
        if feat.get("isRolledBack"):
            continue
        t0 = time.time()
        try:
            result = mcp_text("get_timeline_state", index=fi)
            state = get_body_state(result)
            ground_truth[fi] = state
            dt = time.time() - t0
            if verbose:
                body_count = len(state)
                print(f"  [{fi}] {feat.get('type', '?')}: {feat.get('name', '?')} "
                      f"-> {body_count} bodies ({dt:.1f}s)")
        except Exception as e:
            dt = time.time() - t0
            if verbose:
                print(f"  [{fi}] {feat.get('type', '?')}: ERROR ({dt:.1f}s): {e}")
            ground_truth[fi] = {}

    # Roll timeline back to the end so the source doc is left in its
    # original state (not rolled back to an intermediate step)
    try:
        mcp_text("get_timeline_state", index=-1)
    except Exception:
        pass

    return ground_truth


# ── Incremental build ────────────────────────────────────────────

def incremental_build(capture, ground_truth, verbose=False):
    """Build the script incrementally, one feature at a time.

    For each feature:
    1. Generate a per-feature script
    2. Execute on the scratch doc
    3. Compare volumes against ground truth
    4. If ambiguous and wrong, undo and try next variant

    Returns:
        choices: dict mapping feature_index -> variant_index
        errors: list of (feature_index, error_msg)
    """
    timeline = capture.get("timeline", [])
    ambiguous = get_ambiguous_features(capture)
    ambiguous_map = {a["index"]: a for a in ambiguous}

    choices = {}
    errors = []
    total_attempts = 0
    deferred = []  # [(fi, af)] — ambiguous features with deferred variant selection

    # Execute prefix script (parameters only) with clean=true
    print("\nExecuting prefix script (parameters)...")
    prefix = generate_prefix_script(capture)
    _verify_active_unsaved()  # guard: never clean a saved doc
    t0 = time.time()
    result = mcp("execute_script", script=prefix, sandbox=False, clean=True)
    dt = time.time() - t0
    if result.get("isError"):
        msg = result.get("content", [{}])[0].get("text", "?")[:200]
        print(f"  PREFIX FAILED ({dt:.1f}s): {msg}")
        return choices, [(-1, f"prefix failed: {msg}")]
    print(f"  OK ({dt:.1f}s)")

    # Build list of active feature indices for prev-step comparison
    active_fis = [fi for fi, f in enumerate(timeline) if not f.get("isRolledBack")]

    # Process each feature
    prev_expected = {}
    for step_idx, fi in enumerate(active_fis):
        feat = timeline[fi]
        t = feat.get("type", "Unknown")
        name = feat.get("name", "")
        expected = ground_truth.get(fi, {})

        is_ambiguous = fi in ambiguous_map
        af = ambiguous_map.get(fi)
        n_variants = af["variantCount"] if af else 1

        # Detect if this step changes body volumes (sketch/cplane don't)
        volumes_unchanged = (expected == prev_expected) if prev_expected else False
        prev_expected = expected

        # Defer ambiguous features that don't change volumes — they need
        # validation at the next body-changing step
        if is_ambiguous and volumes_unchanged:
            deferred.append((fi, af))
            # Execute variant 0 as placeholder (will undo+retry if deferred resolves)
            print(f"\n--- [{fi}] {t}: {name} ({n_variants} variants, deferred) ---")
            choices[fi] = 0
            script = generate_feature_script(capture, fi, choices)
            mcp("execute_script", script=script, sandbox=False)
            total_attempts += 1
            continue

        # If we have deferred features AND this step changes bodies, resolve them
        if deferred and not volumes_unchanged:
            # Build variant combinations: deferred features × current feature
            import itertools
            deferred_ranges = [(dfi, range(daf["variantCount"])) for dfi, daf in deferred]
            if is_ambiguous:
                deferred_ranges.append((fi, range(n_variants)))

            # Track timeline items to undo: from first deferred feature to now
            first_deferred_fi = deferred[0][0]
            first_deferred_step = active_fis.index(first_deferred_fi)
            n_features_to_undo = step_idx - first_deferred_step + (1 if is_ambiguous else 0)

            # Count timeline items added by deferred placeholder + current step
            tl_before_deferred = get_timeline_count()
            # Undo the deferred placeholder(s) that were already executed
            n_deferred_executed = len(deferred)
            if not is_ambiguous:
                n_deferred_executed += 0  # current feature not yet executed

            print(f"\n--- Resolving deferred features + [{fi}] {t}: {name} ---")

            # Generate all combinations
            combo_keys = [dfi for dfi, _ in deferred_ranges]
            combo_vals = [list(r) for _, r in deferred_ranges]
            best_combo = None
            best_combo_score = float("inf")

            # Undo deferred placeholders
            tl_before = get_timeline_count() - n_deferred_executed
            undo_timeline_items(n_deferred_executed)

            for combo in itertools.product(*combo_vals):
                trial_choices = dict(choices)
                desc_parts = []
                for dfi, vi in zip(combo_keys, combo):
                    trial_choices[dfi] = vi
                    daf = ambiguous_map[dfi]
                    desc_parts.append(f"[{dfi}]v{vi}")

                desc_str = " + ".join(desc_parts)
                print(f"  Trying {desc_str}...", end=" ", flush=True)

                # Execute all deferred + current feature
                ok = True
                for dfi in combo_keys:
                    script = generate_feature_script(capture, dfi, trial_choices)
                    r = mcp("execute_script", script=script, sandbox=False)
                    total_attempts += 1
                    if r.get("isError"):
                        ok = False
                        break
                if not is_ambiguous:
                    # Also execute the current non-ambiguous feature
                    script = generate_feature_script(capture, fi, trial_choices)
                    r = mcp("execute_script", script=script, sandbox=False)
                    total_attempts += 1
                    if r.get("isError"):
                        ok = False

                if not ok:
                    print("SCRIPT ERROR")
                    # Undo everything we just added
                    tl_now = get_timeline_count()
                    undo_timeline_items(max(0, tl_now - tl_before))
                    continue

                # Validate
                try:
                    state = mcp_text("get_timeline_state", index=-1)
                    actual = get_body_state(state)
                except Exception:
                    print("CAPTURE ERROR")
                    tl_now = get_timeline_count()
                    undo_timeline_items(max(0, tl_now - tl_before))
                    continue

                match, details = states_match(expected, actual)
                score = state_error(expected, actual)

                if match:
                    print(f"MATCH ({score:.1f}%)")
                    best_combo = combo
                    break
                else:
                    print(f"no match (err={score:.1f}%)")
                    if verbose:
                        for d in details:
                            print(f"    {d}")
                    if score < best_combo_score:
                        best_combo_score = score
                        best_combo = combo
                    # Undo and try next combo
                    tl_now = get_timeline_count()
                    undo_timeline_items(max(0, tl_now - tl_before))

            # Apply best combo
            if best_combo is not None:
                for dfi, vi in zip(combo_keys, best_combo):
                    choices[dfi] = vi
                # Re-execute if we undid the best
                tl_now = get_timeline_count()
                if tl_now <= tl_before:
                    for dfi in combo_keys:
                        script = generate_feature_script(capture, dfi, choices)
                        mcp("execute_script", script=script, sandbox=False)
                    if not is_ambiguous:
                        script = generate_feature_script(capture, fi, choices)
                        mcp("execute_script", script=script, sandbox=False)
                descs = [f"[{dfi}]={choices[dfi]}" for dfi in combo_keys]
                print(f"  -> Selected: {', '.join(descs)}")
            else:
                # All combos failed — stop
                combo_fis = [dfi for dfi, _ in deferred]
                if is_ambiguous:
                    combo_fis.append(fi)
                print(f"  -> STOPPING: no combo matched for features {combo_fis}.")
                print(f"     Possible causes: missing search variant, reconstruction bug,")
                print(f"     or API limitation (UI may support features the API cannot replicate).")
                errors.append((combo_fis[0], "no variant matched"))
                deferred.clear()
                return choices, errors

            deferred.clear()
            if is_ambiguous:
                continue  # current feature already handled in combo

            # Current non-ambiguous feature was also executed — validate it
            try:
                state = mcp_text("get_timeline_state", index=-1)
                actual = get_body_state(state)
                match, details = states_match(expected, actual)
                score = state_error(expected, actual)
                if match:
                    print(f"  [{fi}] {t}: {name}... MATCH")
                else:
                    print(f"  [{fi}] {t}: {name}... MISMATCH (err={score:.1f}%)")
                    if verbose:
                        for d in details:
                            print(f"    {d}")
                    errors.append((fi, f"volume mismatch: err={score:.1f}%"))
            except Exception:
                pass
            continue

        if is_ambiguous:
            print(f"\n--- [{fi}] {t}: {name} ({n_variants} variants) ---")
        else:
            print(f"  [{fi}] {t}: {name}...", end=" ", flush=True)

        # Track timeline count before
        tl_before = get_timeline_count()

        best_vi = None
        best_score = float("inf")

        for vi in range(n_variants):
            trial_choices = dict(choices)
            if is_ambiguous:
                trial_choices[fi] = vi
                desc = af["descriptions"][vi]
                print(f"  Trying variant {vi}: {desc}...", end=" ", flush=True)

            # Generate per-feature script
            script = generate_feature_script(capture, fi, trial_choices)

            # Execute on scratch doc
            t0 = time.time()
            try:
                result = mcp("execute_script", script=script, sandbox=False)
                dt = time.time() - t0
                total_attempts += 1
            except Exception as e:
                dt = time.time() - t0
                total_attempts += 1
                print(f"ERROR ({dt:.1f}s): {e}")
                if is_ambiguous:
                    tl_after = get_timeline_count()
                    undo_timeline_items(max(0, tl_after - tl_before))
                    continue
                else:
                    errors.append((fi, str(e)))
                    print(f"\n  STOPPING: feature [{fi}] script error.")
                    return choices, errors

            if result.get("isError"):
                msg = result.get("content", [{}])[0].get("text", "?")[:150]
                print(f"SCRIPT ERROR ({dt:.1f}s): {msg}")
                if is_ambiguous:
                    tl_after = get_timeline_count()
                    undo_timeline_items(max(0, tl_after - tl_before))
                    continue
                else:
                    errors.append((fi, msg))
                    print(f"\n  STOPPING: feature [{fi}] script error.")
                    return choices, errors

            # Get current volumes from scratch doc
            try:
                state = mcp_text("get_timeline_state", index=-1)
                actual = get_body_state(state)
            except Exception as e:
                print(f"CAPTURE ERROR ({dt:.1f}s): {e}")
                if is_ambiguous:
                    tl_after = get_timeline_count()
                    undo_timeline_items(max(0, tl_after - tl_before))
                    continue
                else:
                    errors.append((fi, f"capture error: {e}"))
                    break

            match, details = states_match(expected, actual)
            score = state_error(expected, actual)

            if match:
                print(f"MATCH ({dt:.1f}s)")
                best_vi = vi
                if is_ambiguous:
                    choices[fi] = vi
                break
            else:
                if is_ambiguous:
                    print(f"no match (err={score:.1f}%, {dt:.1f}s)")
                    if verbose:
                        for d in details:
                            print(f"    {d}")
                    if score < best_score:
                        best_score = score
                        best_vi = vi
                    # Undo and try next variant
                    tl_after = get_timeline_count()
                    undo_timeline_items(max(0, tl_after - tl_before))
                else:
                    # Non-ambiguous mismatch: stop build
                    print(f"MISMATCH (err={score:.1f}%, {dt:.1f}s)")
                    for d in details:
                        print(f"    {d}")
                    errors.append((fi, f"mismatch: err={score:.1f}%"))
                    print(f"\n  STOPPING: feature [{fi}] does not match.")
                    print(f"  If all reconstruction options exhausted, check for API limitations")
                    print(f"  (UI may support features the Python API cannot replicate).")
                    return choices, errors
                    break

        # If ambiguous and no exact match, use best variant
        if is_ambiguous and best_vi is not None and fi not in choices:
            choices[fi] = best_vi
            print(f"  -> Best variant {best_vi}: {af['descriptions'][best_vi]} (err={best_score:.1f}%)")
            # Re-execute the best variant (it was undone)
            trial_choices = dict(choices)
            trial_choices[fi] = best_vi
            script = generate_feature_script(capture, fi, trial_choices)
            mcp("execute_script", script=script, sandbox=False)
        elif is_ambiguous and best_vi is None:
            print(f"  -> STOPPING: no variant matched for [{fi}].")
            errors.append((fi, "no variant matched"))
            return choices, errors

    print(f"\nIncremental build complete: {total_attempts} feature executions")
    return choices, errors


# ── Final validation ─────────────────────────────────────────────

def final_validate(script, expected_state, verbose=False):
    """Run final validation of the complete script via sandbox."""
    print("\n--- Final validation ---")
    t0 = time.time()
    result = mcp("execute_script", script=script, sandbox=True)
    dt = time.time() - t0

    if result.get("isError"):
        msg = result.get("content", [{}])[0].get("text", "?")[:200]
        print(f"FAIL: Script error ({dt:.1f}s): {msg}")
        return False

    actual_vols = get_body_volumes_from_sandbox(result)
    # Convert to state format for comparison
    actual = {n: {"volume": v, "boundingBox": {}} for n, v in (actual_vols or {}).items()}
    match, details = states_match(expected_state, actual)

    for d in details:
        print(d)
    print(f"\n{'PASS' if match else 'FAIL'} ({dt:.1f}s)")
    return match


# ── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Search-based script builder v2 — incremental per-feature")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--from-fusion", action="store_true",
                        help="Capture design from live Fusion 360")
    source.add_argument("--capture", type=str,
                        help="Path to saved capture_design JSON file")

    parser.add_argument("--output", "-o", type=str,
                        help="Output path for validated script")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show ambiguous features without executing")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show detailed volume comparisons")
    parser.add_argument("--tolerance", type=float, default=VOLUME_TOLERANCE_PCT,
                        help=f"Volume tolerance %% (default: {VOLUME_TOLERANCE_PCT})")
    parser.add_argument("--default-only", action="store_true",
                        help="Generate with all default variants (no search)")
    parser.add_argument("--skip-ground-truth", action="store_true",
                        help="Skip ground truth collection (use final volumes only)")

    args = parser.parse_args()
    _set_tolerance(args.tolerance)

    # ── Load capture data ──
    if args.from_fusion:
        print("Capturing design from Fusion 360...")
        cap_result = mcp("capture_design")
        if cap_result.get("isError"):
            print(f"Error: {cap_result.get('content', [{}])[0].get('text', '?')}")
            sys.exit(1)
        capture = json.loads(cap_result["content"][0]["text"])
        src_name = capture.get("designName", "?")
        print(f"Source design: {src_name}")
        if not capture.get("timeline"):
            print("Error: no timeline in capture")
            sys.exit(1)
    else:
        with open(args.capture) as f:
            capture = json.load(f)

    # Extract final expected state
    expected_state = get_body_state(capture)
    print(f"Expected bodies ({len(expected_state)}):")
    for name, body in sorted(expected_state.items()):
        print(f"  {name}: {body['volume']:.4f} cm3")

    # ── Analyze ambiguities ──
    timeline = capture.get("timeline", [])
    active_features = [f for f in timeline if not f.get("isRolledBack")]
    ambiguous = get_ambiguous_features(capture)
    print(f"\nTimeline: {len(active_features)} active features, "
          f"{len(ambiguous)} ambiguous")

    if args.dry_run:
        if not ambiguous:
            print("No ambiguous features — default generation should work.")
        else:
            for a in ambiguous:
                print(f"\n  [{a['index']}] {a['type']} '{a['name']}': "
                      f"{a['variantCount']} variants")
                for i, d in enumerate(a["descriptions"]):
                    print(f"    {i}: {d}")
            total = 1
            for a in ambiguous:
                total *= a["variantCount"]
            print(f"\nTotal search space: {total} combinations")
            print(f"Greedy search: <={sum(a['variantCount'] for a in ambiguous)} "
                  f"feature executions (incremental)")
        sys.exit(0)

    # ── Collect ground truth ──
    if not args.skip_ground_truth:
        ground_truth = collect_ground_truth(capture, verbose=args.verbose)
    else:
        print("\nSkipping per-feature ground truth (using final state only)")
        ground_truth = {}
        for fi, feat in enumerate(timeline):
            if not feat.get("isRolledBack"):
                ground_truth[fi] = expected_state

    # ── Switch to scratch doc ──
    ensure_scratch_doc(verbose=args.verbose)

    # ── Build incrementally or default ──
    if args.default_only or not ambiguous:
        if not ambiguous:
            print("\nNo ambiguous features — building with defaults...")
        choices = {}
        # Still do incremental build for validation
        choices, errors = incremental_build(
            capture, ground_truth, verbose=args.verbose)
    else:
        choices, errors = incremental_build(
            capture, ground_truth, verbose=args.verbose)

    print(f"\nFinal choices: {choices}")
    if errors:
        print(f"Errors ({len(errors)}):")
        for fi, msg in errors:
            print(f"  [{fi}]: {msg}")

    # ── Generate final script ──
    if choices:
        script = generate_with_choices(capture, choices)
    else:
        script = generate_script(capture)
    print(f"Generated script: {len(script.splitlines())} lines")

    # ── Final validation ──
    ok = final_validate(script, expected_state, verbose=args.verbose)

    # ── Output ──
    if args.output:
        with open(args.output, "w") as f:
            f.write(script)
        print(f"\nScript written to: {args.output}")
    elif not ok:
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                          prefix="search_build_", delete=False) as f:
            f.write(script)
            print(f"\nScript written to: {f.name}")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
