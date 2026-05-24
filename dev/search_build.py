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
    python dev/search_build.py --from-fusion -o /tmp/rebuilt.py -v

    # From saved capture JSON:
    python dev/search_build.py --capture capture.json -o /tmp/rebuilt.py

    # Dry-run: show ambiguous features without executing:
    python dev/search_build.py --capture capture.json --dry-run

Requires: Fusion 360 running with MCP server on localhost:9100
"""
import argparse
import json
import os
import sys
import textwrap
import time

# Add addin/tools to import path for _script_generator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "addin", "tools"))
from _script_generator import (
    generate_script,
    generate_with_choices,
    get_ambiguous_features,
    generate_prefix_script,
    generate_feature_script,
    count_feature_variants,
)

MCP_URL = os.environ.get("MCP_URL", "http://localhost:9100")
VOLUME_TOLERANCE_PCT = 0.01  # strict: 0.01% = essentially exact match


def _set_tolerance(val):
    global VOLUME_TOLERANCE_PCT, BB_TOLERANCE_CM
    VOLUME_TOLERANCE_PCT = val
    # Scale bbox tolerance proportionally when volume tolerance is elevated
    BB_TOLERANCE_CM = BB_TOLERANCE_DEFAULT * max(1, val / 0.01)


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


def _apply_transform(bb, transform):
    """Apply occurrence translation+rotation transform to a bounding box.

    transform is the full 16-element row-major 4x4 matrix (from occ.transform.asArray()).
    Falls back to 3-element translation-only for backward compatibility.
    """
    if not bb or not transform:
        return bb
    mn = bb.get("min")
    mx = bb.get("max")
    if not mn or not mx:
        return bb
    if len(transform) == 3:
        # Legacy: translation-only [tx, ty, tz]
        tx, ty, tz = transform
        return {
            "min": [mn[0] + tx, mn[1] + ty, mn[2] + tz],
            "max": [mx[0] + tx, mx[1] + ty, mx[2] + tz],
        }
    if len(transform) == 16:
        # Full 4x4 row-major matrix
        def xf_point(p):
            x, y, z = p
            nx = transform[0]*x + transform[1]*y + transform[2]*z + transform[3]
            ny = transform[4]*x + transform[5]*y + transform[6]*z + transform[7]
            nz = transform[8]*x + transform[9]*y + transform[10]*z + transform[11]
            return [nx, ny, nz]
        # Transform all 8 corners and take new AABB
        corners = [
            [mn[0], mn[1], mn[2]], [mx[0], mn[1], mn[2]],
            [mn[0], mx[1], mn[2]], [mx[0], mx[1], mn[2]],
            [mn[0], mn[1], mx[2]], [mx[0], mn[1], mx[2]],
            [mn[0], mx[1], mx[2]], [mx[0], mx[1], mx[2]],
        ]
        transformed = [xf_point(c) for c in corners]
        new_min = [min(p[i] for p in transformed) for i in range(3)]
        new_max = [max(p[i] for p in transformed) for i in range(3)]
        return {"min": new_min, "max": new_max}
    return bb


def get_body_state(data, qualify_duplicates=True):
    """Extract {name: {volume, boundingBox}} from timeline state or capture data.

    When qualify_duplicates=True, duplicate body names across components are
    qualified with [component_name] to prevent overwriting.  This matches the
    qualification in get_changes.py and is used for final validation.

    When qualify_duplicates=False, duplicates silently overwrite (last wins).
    Use for per-feature comparison where build and source may have different
    component structures causing inconsistent qualification.
    """
    bodies = {}
    if "components" in data:
        # Collect raw list to detect duplicates
        raw = []  # [(comp_name, body_name, body_data)]
        def walk(comp, comp_name="root", parent_transform=None):
            # Compose transform: parent * current occurrence
            cur_xf = comp.get("transform")
            if parent_transform and cur_xf:
                # Both exist — compose (only supports translation-only for now)
                if len(parent_transform) == 3 and len(cur_xf) == 3:
                    combined = [parent_transform[i] + cur_xf[i] for i in range(3)]
                else:
                    combined = cur_xf  # Full matrix composition not needed yet
            elif cur_xf:
                combined = cur_xf
            else:
                combined = parent_transform

            for b in comp.get("bodies", []):
                bname = b.get("name", "?")
                bb = b.get("boundingBox", {})
                if combined:
                    bb = _apply_transform(bb, combined)
                raw.append((comp_name, bname, {
                    "volume": b.get("volume", 0),
                    "boundingBox": bb,
                }))
            for child in comp.get("children", []):
                walk(child, child.get("name", "?"), combined)
        walk(data["components"])
        if qualify_duplicates:
            # Detect duplicates
            name_counts = {}
            for _, bname, _ in raw:
                name_counts[bname] = name_counts.get(bname, 0) + 1
            for comp_name, bname, bdata in raw:
                key = f"{bname} [{comp_name}]" if name_counts[bname] > 1 else bname
                bodies[key] = bdata
        else:
            for comp_name, bname, bdata in raw:
                bodies[bname] = bdata
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


def get_body_state_from_sandbox(sandbox_result):
    """Extract {name: {volume, boundingBox}} from sandbox result."""
    if sandbox_result.get("isError"):
        return None
    snapshot = sandbox_result.get("snapshot", {})
    vols = snapshot.get("bodyVolumes", {})
    bboxes = snapshot.get("bodyBoundingBoxes", {})
    return {
        name: {"volume": vol, "boundingBox": bboxes.get(name, {})}
        for name, vol in vols.items()
    }


BB_TOLERANCE_CM = 0.05  # bounding box tolerance in cm (mirrors can shift slightly)
BB_TOLERANCE_DEFAULT = 0.05


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
    if not expected:
        return True, ["  (no ground truth — skipped)"]

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

    # Pass 2: fuzzy match by geometry (volume + bbox) for split-renamed bodies
    unmatched_actual = {n: v for n, v in actual.items() if n not in matched_actual}
    for exp_name, exp in list(unmatched_expected.items()):
        best_name, best_dist = None, float("inf")
        for act_name, act in unmatched_actual.items():
            d = _body_distance(exp, act)
            if d < best_dist:
                best_dist, best_name = d, act_name
        if best_name is not None and best_dist < 150:  # reasonable threshold
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
    # Graduated BB tolerance: when volume matches very closely, boolean
    # kernel precision artifacts can shift bboxes without changing volume.
    # Use relaxed tolerance (0.2 cm) when volume error < 0.01%.
    # (1.0 cm was too loose — let offset variants with 0.6 cm face drift
    # through, cascading bb errors to downstream face-based sketches.)
    effective_bb_tol = BB_TOLERANCE_CM
    if delta_pct < 0.01:
        effective_bb_tol = max(BB_TOLERANCE_CM, 0.2)
    bb_ok = True
    if exp_bb and act_bb:
        for key in ("min", "max"):
            ep = exp_bb.get(key, [0, 0, 0])
            ap = act_bb.get(key, [0, 0, 0])
            for i in range(3):
                if abs(ep[i] - ap[i]) > effective_bb_tol:
                    bb_ok = False

    vol_ok = delta_pct <= tolerance_pct
    if vol_ok and bb_ok:
        msgs.append(f"  + {label}: vol={exp_v:.4f} ({delta_pct:.3f}%)")
    elif vol_ok and not bb_ok:
        bb_detail = ""
        if exp_bb and act_bb:
            bb_detail = f" exp_bb={[round(v,1) for v in exp_bb.get('min',[])]}..{[round(v,1) for v in exp_bb.get('max',[])]} act_bb={[round(v,1) for v in act_bb.get('min',[])]}..{[round(v,1) for v in act_bb.get('max',[])]}"
        msgs.append(f"  x {label}: vol={exp_v:.4f} ({delta_pct:.3f}%), bb mismatch{bb_detail}")
        ok = False
    else:
        parts = [f"vol {exp_v:.4f}->{act_v:.4f} ({delta_pct:.2f}%)"]
        if not bb_ok:
            bb_d = ""
            if exp_bb and act_bb:
                bb_d = f" exp_bb={[round(v,2) for v in exp_bb.get('min',[])]}..{[round(v,2) for v in exp_bb.get('max',[])]} act_bb={[round(v,2) for v in act_bb.get('min',[])]}..{[round(v,2) for v in act_bb.get('max',[])]}"
            parts.append(f"bb mismatch{bb_d}")
        msgs.append(f"  x {label}: {', '.join(parts)}")
        ok = False
    return ok, msgs


def _body_distance(exp, act):
    """Combined volume + bbox distance score for one body pair."""
    exp_v, act_v = exp["volume"], act["volume"]
    if exp_v != 0:
        score = abs(act_v - exp_v) / abs(exp_v) * 100
    elif act_v != 0:
        score = 100
    else:
        score = 0
    # Add bbox penalty (scale: 1 cm offset ≈ 10 points)
    exp_bb = exp.get("boundingBox", {})
    act_bb = act.get("boundingBox", {})
    if exp_bb and act_bb:
        for key in ("min", "max"):
            ep = exp_bb.get(key, [0, 0, 0])
            ap = act_bb.get(key, [0, 0, 0])
            for i in range(3):
                score += abs(ep[i] - ap[i]) * 10
    return score


def state_error(expected, actual):
    """Aggregate error score from body state comparison (lower is better).

    Uses _body_distance (volume + bbox) for both scoring and fuzzy pairing.
    """
    if actual is None:
        return float("inf")
    # Body count mismatch penalty
    score = abs(len(expected) - len(actual)) * 100
    remaining = dict(actual)
    for name, exp_body in expected.items():
        act_body = remaining.pop(name, None)
        if act_body is None:
            # Fuzzy match by combined vol+bbox distance
            best_n, best_score = None, float("inf")
            for rn, rb in remaining.items():
                s = _body_distance(exp_body, rb)
                if s < best_score:
                    best_score, best_n = s, rn
            if best_n is not None and best_score < 150:
                act_body = remaining.pop(best_n)
            else:
                score += 100
                continue
        score += _body_distance(exp_body, act_body)
    return score


SKETCH_CURVE_TOLERANCE = 0.5  # cm tolerance for curve endpoint matching (world space)

CASCADE_TOLERANCE_PCT = 1.0  # max volume delta to classify as cascade (not a real error)
APPROX_TOLERANCE_PCT = 2.5  # relaxed tolerance for spline approximation residuals


def _detect_cascades(expected, actual, feat, cascade_deltas):
    """Detect Fusion parametric cascade: bodies that change volume due to a
    feature that doesn't directly modify them (e.g., fillet on body A causes
    body B's volume to shift via internal dependency chain).

    Returns new cascade deltas {body_name: volume_offset}.
    """
    # Only detect for geometry-modifying features (not Sketch, ComponentCreation, etc.)
    feat_type = feat.get("type", "")
    if feat_type in ("Sketch", "ComponentCreation", "ConstructionPlane",
                     "ConstructionAxis", "Unknown"):
        return {}

    # Bodies directly modified by this feature
    direct_bodies = set(feat.get("bodies", []))
    direct_bodies.update(feat.get("inputs", []))

    new_deltas = {}
    for name, exp in expected.items():
        act = actual.get(name)
        if act is None:
            continue
        exp_v = exp["volume"]
        act_v = act["volume"]
        if exp_v == 0:
            continue
        delta_pct = abs(act_v - exp_v) / abs(exp_v) * 100
        if delta_pct <= VOLUME_TOLERANCE_PCT:
            continue  # already matches
        if delta_pct > CASCADE_TOLERANCE_PCT:
            continue  # too large for cascade

        # Strip qualified suffix [component] for direct_bodies check
        base_name = name.split(" [")[0] if " [" in name else name
        if base_name in direct_bodies:
            continue  # directly modified — not a cascade

        # BB must match (cascade changes volume but not shape envelope)
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
        if not bb_ok:
            continue

        # This is a cascade: body volume changed without direct modification
        offset = act_v - exp_v
        new_deltas[name] = offset

    return new_deltas


def _apply_cascade_deltas(expected, actual, cascade_deltas):
    """Return adjusted expected dict with cascade deltas applied.

    For bodies with a known cascade delta, adjust expected volume.
    For new bodies whose volume mismatch matches a known offset, infer cascade.
    Requires actual data for inference (no base-name guessing).
    """
    if not cascade_deltas:
        return expected

    # Collect unique delta values for pattern-copy inference
    known_offsets = set(round(d, 2) for d in cascade_deltas.values())

    adjusted = {}
    for name, exp in expected.items():
        adj = dict(exp)
        # Direct name match
        if name in cascade_deltas:
            adj["volume"] = exp["volume"] + cascade_deltas[name]
        else:
            # Infer cascade for pattern copies via volume mismatch.
            # Only adjust local value — don't mutate cascade_deltas to avoid
            # double-counting with body drift.  Real cascades are detected
            # explicitly via _detect_cascades.
            if actual:
                act = actual.get(name)
                if act and exp["volume"] > 0:
                    diff = act["volume"] - exp["volume"]
                    for offset in known_offsets:
                        if abs(diff - offset) < 0.1:
                            adj["volume"] = exp["volume"] + offset
                            break
        adjusted[name] = adj
    return adjusted


BODY_DRIFT_MAX_PCT = 5.0  # max per-body drift before stopping drift tracking


def _apply_body_drift(expected, body_drift):
    """Adjust expected values by known per-body drift from prior features.

    body_drift tracks the accumulated difference (actual - GT) for each body.
    Adjusting expected by this delta lets the validator measure only the error
    introduced by the CURRENT feature, not accumulated drift from prior ones.
    """
    if not body_drift:
        return expected
    adjusted = {}
    for name, exp in expected.items():
        adj = dict(exp)
        drift = body_drift.get(name)
        if drift:
            adj["volume"] += drift["vol_offset"]
            if "boundingBox" in adj and drift.get("bb_offsets"):
                bb = {}
                for key in ("min", "max"):
                    ep = adj["boundingBox"].get(key, [0, 0, 0])
                    dp = drift["bb_offsets"].get(key, [0, 0, 0])
                    bb[key] = [ep[i] + dp[i] for i in range(3)]
                adj["boundingBox"] = bb
        adjusted[name] = adj
    return adjusted


def _update_body_drift(body_drift, expected_raw, actual,
                       max_bb_drift_cm=2.0, cascade_deltas=None):
    """Update per-body drift after each feature execution.

    Only tracks drift within BODY_DRIFT_MAX_PCT of GT volume AND
    max_bb_drift_cm of BB coordinates.  Larger deviations are treated
    as real errors, not drift.

    Bodies already tracked in cascade_deltas are skipped to avoid
    double-counting (drift and cascade represent the same offset).
    """
    for name, act in actual.items():
        if cascade_deltas and name in cascade_deltas:
            continue  # tracked as cascade — don't also track as drift
        exp = expected_raw.get(name)
        if exp is None or exp["volume"] == 0:
            continue
        vol_offset = act["volume"] - exp["volume"]
        drift_pct = abs(vol_offset) / exp["volume"] * 100
        if drift_pct > BODY_DRIFT_MAX_PCT:
            continue  # too large — real error, not drift
        bb_offsets = {}
        act_bb = act.get("boundingBox", {})
        exp_bb = exp.get("boundingBox", {})
        bb_ok = True
        if act_bb and exp_bb:
            for key in ("min", "max"):
                ep = exp_bb.get(key, [0, 0, 0])
                ap = act_bb.get(key, [0, 0, 0])
                offs = [ap[i] - ep[i] for i in range(3)]
                if any(abs(o) > max_bb_drift_cm for o in offs):
                    bb_ok = False
                    break
                bb_offsets[key] = offs
        if not bb_ok:
            continue  # BB too far off — real error, not drift
        body_drift[name] = {"vol_offset": vol_offset, "bb_offsets": bb_offsets}


def _build_body_component_map(capture):
    """Build mapping of body_name -> component_name from capture component tree.

    Used by _apply_snapshot_offsets to determine which component each body
    belongs to, so the correct Snapshot transform can be applied.
    """
    result = {}
    def walk(comp):
        comp_name = comp.get("name", "root")
        for body in comp.get("bodies", []):
            result[body.get("name", "?")] = comp_name
        for child in comp.get("children", []):
            walk(child)
    comp_tree = capture.get("components", {})
    if comp_tree:
        walk(comp_tree)
    return result


def _get_state_transforms(state):
    """Extract component names that have non-identity transforms in the state.

    get_timeline_state only stores transforms when they differ from identity,
    so presence means get_body_state() already applied the transform.
    """
    present = set()
    comp_tree = state.get("components")
    if not comp_tree:
        return present
    def walk(comp):
        for child in comp.get("children", []):
            if child.get("transform"):
                present.add(child.get("name", "?"))
            walk(child)
    walk(comp_tree)
    return present


def _apply_snapshot_offsets_conditional(actual, state, snapshot_transforms,
                                        body_comp_map):
    """Apply snapshot offsets only for components whose transforms are missing.

    occ.transform set by Snapshot scripts is ephemeral — Fusion may reset it
    when the timeline is modified.  get_body_state() applies transforms from
    the component tree, so we only offset bodies in components where the
    expected transform is NOT already present.
    """
    if not snapshot_transforms:
        return actual
    present = _get_state_transforms(state)
    missing = {k: v for k, v in snapshot_transforms.items() if k not in present}
    if not missing:
        return actual
    return _apply_snapshot_offsets(actual, missing, body_comp_map)


def _apply_snapshot_offsets(actual, snapshot_transforms, body_comp_map):
    """Adjust actual body bounding boxes by accumulated Snapshot transforms.

    occ.transform is ephemeral in scratch docs — reset by get_timeline_state.
    Apply known transforms to actual BBs so they match GT (which has real
    Snapshot features that persistently move occurrences).
    """
    if not snapshot_transforms:
        return actual

    adjusted = {}
    for name, body in actual.items():
        # Determine component from qualified name "body [comp]" or lookup
        comp_name = None
        if " [" in name:
            comp_name = name.split(" [")[1].rstrip("]")
        else:
            comp_name = body_comp_map.get(name)

        if comp_name and comp_name in snapshot_transforms:
            data = snapshot_transforms[comp_name]
            bb = body.get("boundingBox", {})
            if bb:
                adj = dict(body)
                if len(data) == 16:
                    # Full 4x4 matrix: apply rotation + translation to BB
                    adj_bb = {}
                    for key in ("min", "max"):
                        pt = bb.get(key, [0, 0, 0])
                        x = data[0]*pt[0] + data[1]*pt[1] + data[2]*pt[2] + data[3]
                        y = data[4]*pt[0] + data[5]*pt[1] + data[6]*pt[2] + data[7]
                        z = data[8]*pt[0] + data[9]*pt[1] + data[10]*pt[2] + data[11]
                        adj_bb[key] = [x, y, z]
                    # Rotation can swap min/max — recalculate
                    mins = [min(adj_bb["min"][i], adj_bb["max"][i]) for i in range(3)]
                    maxs = [max(adj_bb["min"][i], adj_bb["max"][i]) for i in range(3)]
                    adj_bb["min"] = mins
                    adj_bb["max"] = maxs
                    adj["boundingBox"] = adj_bb
                else:
                    # Legacy: [tx, ty, tz] translation only
                    tx, ty, tz = data
                    adj_bb = {}
                    for key in ("min", "max"):
                        pt = bb.get(key, [0, 0, 0])
                        adj_bb[key] = [pt[0] + tx, pt[1] + ty, pt[2] + tz]
                    adj["boundingBox"] = adj_bb
                adjusted[name] = adj
            else:
                adjusted[name] = body
        else:
            adjusted[name] = body
    return adjusted


def _sk_to_world(pt2d, origin, xdir, ydir):
    """Transform 2D sketch point to 3D world coordinates."""
    return [
        origin[0] + pt2d[0] * xdir[0] + pt2d[1] * ydir[0],
        origin[1] + pt2d[0] * xdir[1] + pt2d[1] * ydir[1],
        origin[2] + pt2d[0] * xdir[2] + pt2d[1] * ydir[2],
    ]


def _transform_curves_to_world(curves, origin, xdir, ydir):
    """Transform all curve coordinates from sketch space to world space."""
    out = []
    for c in curves:
        ctype = c.get("type", "?")
        wc = dict(c)
        if ctype == "Line":
            wc["start"] = _sk_to_world(c.get("start", [0, 0]), origin, xdir, ydir)
            wc["end"] = _sk_to_world(c.get("end", [0, 0]), origin, xdir, ydir)
        elif ctype == "Arc":
            wc["center"] = _sk_to_world(c.get("center", [0, 0]), origin, xdir, ydir)
            wc["start"] = _sk_to_world(c.get("start", [0, 0]), origin, xdir, ydir)
            wc["end"] = _sk_to_world(c.get("end", [0, 0]), origin, xdir, ydir)
        elif ctype == "FittedSpline":
            wc["fitPoints"] = [_sk_to_world(p, origin, xdir, ydir)
                               for p in c.get("fitPoints", [])]
        elif ctype == "Circle":
            wc["center"] = _sk_to_world(c.get("center", [0, 0]), origin, xdir, ydir)
        out.append(wc)
    return out


def _compare_sketch(expected_feat, actual_sketches, pre_sketch_ids=None, verbose=False):
    """Compare a captured sketch's curves against rebuilt sketch curves.

    All comparisons are done in world space to handle different sketch
    coordinate systems on BRepFace sketches.

    pre_sketch_ids: set of (name, component) tuples of sketches that existed
    before this feature was executed. New sketches are identified by difference.

    Returns (match: bool, details: list[str])
    """
    if pre_sketch_ids is None:
        pre_sketch_ids = set()
    sk_name = expected_feat.get("name", "?")
    sk_comp = expected_feat.get("component", "")
    exp_curves = expected_feat.get("curves", [])
    exp_profiles = expected_feat.get("profileCount", 0)

    if not exp_curves:
        return True, [f"  (no curves to compare for {sk_name})"]

    # Expected sketch coordinate system from capture
    exp_origin = expected_feat.get("sketchOrigin", [0, 0, 0])
    exp_xdir = expected_feat.get("sketchXDir", [1, 0, 0])
    exp_ydir = expected_feat.get("sketchYDir", [0, 1, 0])

    # Primary: find the newly created sketch by set difference.
    # This handles name/component changes on the rebuilt doc.
    actual_sk = None
    new_sketches = [ask for ask in actual_sketches
                    if (ask.get("name", ""), ask.get("component", "")) not in pre_sketch_ids]
    if len(new_sketches) == 1:
        actual_sk = new_sketches[0]
    elif len(new_sketches) > 1:
        # Multiple new sketches — pick the closest by origin
        best_d = float("inf")
        for ask in new_sketches:
            act_origin = ask.get("sketchOrigin", [0, 0, 0])
            d = sum(abs(exp_origin[i] - act_origin[i]) for i in range(3))
            if d < best_d:
                best_d = d
                actual_sk = ask
    # Fallback: match by origin from all sketches
    if actual_sk is None:
        best_d = float("inf")
        for ask in actual_sketches:
            act_origin = ask.get("sketchOrigin", [0, 0, 0])
            d = sum(abs(exp_origin[i] - act_origin[i]) for i in range(3))
            if d < best_d:
                best_d = d
                actual_sk = ask

    if actual_sk is None:
        return False, [f"  Sketch '{sk_name}' not found in rebuilt doc"]

    act_curves = actual_sk.get("curves", [])
    act_profiles = actual_sk.get("profileCount", 0)

    # Actual sketch coordinate system
    act_origin = actual_sk.get("sketchOrigin", [0, 0, 0])
    act_xdir = actual_sk.get("sketchXDir", [1, 0, 0])
    act_ydir = actual_sk.get("sketchYDir", [0, 1, 0])

    details = []

    # Compare profile count
    if exp_profiles != act_profiles:
        details.append(f"  x Profile count: expected={exp_profiles} actual={act_profiles}")

    # Transform to world space for comparison
    exp_drawn = [c for c in exp_curves if not c.get("isReference")]
    act_drawn = [c for c in act_curves if not c.get("isReference")]

    exp_world = _transform_curves_to_world(exp_drawn, exp_origin, exp_xdir, exp_ydir)
    act_world = _transform_curves_to_world(act_drawn, act_origin, act_xdir, act_ydir)

    if len(exp_world) != len(act_world):
        details.append(f"  x Drawn curve count: expected={len(exp_world)} actual={len(act_world)}")

    # Match curves by type and world-space endpoint proximity
    tol = SKETCH_CURVE_TOLERANCE
    matched_act = set()
    unmatched_exp = []

    for ei, ec in enumerate(exp_world):
        etype = ec.get("type", "?")
        best_ai, best_dist = None, float("inf")

        for ai, ac in enumerate(act_world):
            if ai in matched_act:
                continue
            if ac.get("type") != etype:
                continue
            d = _curve_distance(ec, ac)
            if d < best_dist:
                best_dist, best_ai = d, ai

        if best_ai is not None and best_dist < tol:
            matched_act.add(best_ai)
        else:
            unmatched_exp.append((ei, ec, best_dist))

    if unmatched_exp:
        for ei, ec, dist in unmatched_exp:
            etype = ec.get("type", "?")
            if etype == "Line":
                s = [round(v, 2) for v in ec.get("start", [])]
                e = [round(v, 2) for v in ec.get("end", [])]
                details.append(f"  x curve[{ei}] {etype} {s}->{e} not matched (dist={dist:.3f})")
            elif etype == "FittedSpline":
                pts = ec.get("fitPoints", [])
                details.append(f"  x curve[{ei}] {etype} {len(pts)} pts not matched (dist={dist:.3f})")
            else:
                details.append(f"  x curve[{ei}] {etype} not matched (dist={dist:.3f})")

    extra_act = len(act_world) - len(matched_act)
    if extra_act > 0:
        details.append(f"  x {extra_act} extra drawn curves in rebuilt sketch")

    match = len(details) == 0
    if match:
        details.append(f"  + Sketch {sk_name}: {len(exp_drawn)} curves, {exp_profiles} profiles OK")
    return match, details


def _curve_distance(exp, act):
    """Distance metric between two curves of the same type (world space)."""
    ctype = exp.get("type", "?")
    if ctype == "Line":
        es, ee = exp.get("start", [0, 0, 0]), exp.get("end", [0, 0, 0])
        a_s, ae = act.get("start", [0, 0, 0]), act.get("end", [0, 0, 0])
        # Try both orientations (line direction can be reversed)
        d_fwd = max(abs(es[i] - a_s[i]) for i in range(len(es)))
        d_fwd = max(d_fwd, max(abs(ee[i] - ae[i]) for i in range(len(ee))))
        d_rev = max(abs(es[i] - ae[i]) for i in range(len(es)))
        d_rev = max(d_rev, max(abs(ee[i] - a_s[i]) for i in range(len(ee))))
        return min(d_fwd, d_rev)
    elif ctype == "Arc":
        ec, ac_ = exp.get("center", [0, 0, 0]), act.get("center", [0, 0, 0])
        d = max(abs(ec[i] - ac_[i]) for i in range(len(ec)))
        d += abs(exp.get("radius", 0) - act.get("radius", 0))
        return d
    elif ctype == "FittedSpline":
        ep = exp.get("fitPoints", [])
        ap = act.get("fitPoints", [])
        if len(ep) != len(ap):
            return float("inf")
        d = 0
        for i in range(len(ep)):
            d = max(d, max(abs(ep[i][j] - ap[i][j]) for j in range(len(ep[i]))))
        return d
    elif ctype == "Circle":
        ec, ac_ = exp.get("center", [0, 0, 0]), act.get("center", [0, 0, 0])
        return max(abs(ec[i] - ac_[i]) for i in range(len(ec)))
    return float("inf")


# ── Document management ──────────────────────────────────────────

_CREATE_ASSEMBLY_SCRIPT = textwrap.dedent("""\
    import adsk.core, adsk.fusion
    def run(context):
        app = adsk.core.Application.get()
        doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
""")


def _is_assembly_design():
    """Check if active document is Assembly Design (supports multi-component).

    Part Design and Assembly Design both have designType=1 (Parametric).
    The distinction: Part Design restricts to one component. We detect by
    trying addNewComponent — if it fails, it's Part Design.
    """
    try:
        r = mcp("execute_script", script=textwrap.dedent("""\
            import adsk.core, adsk.fusion
            def run(context):
                app = adsk.core.Application.get()
                design = adsk.fusion.Design.cast(app.activeProduct)
                if design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
                    print("NOT_PARAMETRIC")
                    return
                root = design.rootComponent
                try:
                    xf = adsk.core.Matrix3D.create()
                    occ = root.occurrences.addNewComponent(xf)
                    # Success — it's Assembly Design. Undo the component.
                    occ.deleteMe()
                    print("ASSEMBLY")
                except:
                    print("PART")
        """), clean=False)
        text = r["content"][0]["text"]
        return "ASSEMBLY" in text
    except Exception:
        return False


def ensure_scratch_doc(verbose=False):
    """Switch to an existing unsaved Assembly Design doc, or create one.

    Never touches user-saved documents. Reuses existing untitled docs
    to avoid document proliferation. Detects and replaces Part Design
    docs that can't support multi-component designs.
    """
    if verbose:
        print("Switching to scratch document...")
    try:
        list_result = mcp("manage_documents", action="list")
        docs = json.loads(list_result["content"][0]["text"])
    except Exception:
        docs = []

    def _try_reuse(d, activate=False):
        """Try to reuse doc d. Returns True if it's an Assembly Design."""
        if activate:
            mcp("manage_documents", action="activate", index=d["index"])
        if _is_assembly_design():
            if verbose:
                print(f"  Reusing Assembly Design: {d['name']}")
            _verify_active_unsaved()
            return True
        # Part Design — close it and fall through to creation
        if verbose:
            print(f"  Closing Part Design: {d['name']}")
        mcp("manage_documents", action="close")
        return False

    # Check if already on an unsaved doc
    active = next((d for d in docs if d["isActive"]), None)
    if active and not active["isSaved"]:
        if _try_reuse(active):
            return active

    # Try to activate an existing unsaved doc
    # Re-list since we may have closed the active doc
    try:
        list_result = mcp("manage_documents", action="list")
        docs = json.loads(list_result["content"][0]["text"])
    except Exception:
        docs = []
    for d in docs:
        if not d["isSaved"] and not d["isActive"]:
            if _try_reuse(d, activate=True):
                return d

    # No suitable unsaved doc — create Assembly Design
    mcp("execute_script", script=_CREATE_ASSEMBLY_SCRIPT, clean=False)
    if verbose:
        print(f"  Created new Assembly Design scratch doc")
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

def _fix_gt_shift(ground_truth, timeline, end_state, verbose=False):
    """Detect and fix GT off-by-one caused by multi-body SplitBody lazy eval.

    Fusion's get_timeline_state has a bug: when a SplitBody feature splits
    multiple input bodies, the secondary splits don't appear until the NEXT
    timeline position.  This causes GT[i] to show the state of feature [i-1]
    for all features from the split onwards.

    Fix: detect the shift point and remap GT[i] = original GT[i+1].
    The last feature gets the end-of-timeline state.
    """
    active_fis = sorted(k for k in ground_truth if isinstance(k, int))
    if not active_fis:
        return ground_truth

    shift_point = None
    for idx, fi in enumerate(active_fis):
        feat = timeline[fi] if fi < len(timeline) else {}
        if feat.get("type") == "SplitBody":
            input_bodies = feat.get("inputBodies", [])
            if len(input_bodies) > 1:
                # Verify: body count increase should equal len(inputBodies)
                # (each split adds 1 net body).  If less, GT is shifted.
                prev_fi = active_fis[idx - 1] if idx > 0 else None
                prev_count = len(ground_truth.get(prev_fi, {})) if prev_fi is not None else 0
                curr_count = len(ground_truth[fi])
                actual_new = curr_count - prev_count
                expected_new = len(input_bodies)  # each body → 2 pieces = +1 net
                if actual_new < expected_new:
                    shift_point = fi
                    if verbose:
                        print(f"\n  GT off-by-one detected at [{fi}] SplitBody: "
                              f"{actual_new} new bodies, expected {expected_new}. "
                              f"Shifting GT[i] = GT[i+1] from here.")
                    break

    if shift_point is None:
        return ground_truth

    # Remap: for fi >= shift_point, use GT[next_fi]
    fixed = {}
    for key, val in ground_truth.items():
        if not isinstance(key, int):
            fixed[key] = val  # preserve _qualified_final etc.
            continue
        if key < shift_point:
            fixed[key] = val
        else:
            pos = active_fis.index(key)
            if pos + 1 < len(active_fis):
                fixed[key] = ground_truth[active_fis[pos + 1]]
            else:
                # Last feature: use end-of-timeline state
                fixed[key] = end_state

    return fixed


def collect_ground_truth(capture, verbose=False):
    """Collect per-feature body state from the original design.

    Uses sequential marker advancement (no_restore) to avoid Fusion's
    recompute quirk where jumping back from end-of-timeline leaves
    multi-body SplitBody features partially evaluated.

    Returns dict: {feature_index: {body_name: {volume, boundingBox}},
                   "_qualified_final": {qualified_name: {volume, boundingBox}}}
    """
    timeline = capture.get("timeline", [])
    expected_count = len(timeline)
    if verbose:
        print(f"\nCollecting ground truth ({expected_count} features)...")

    # Pre-flight check: verify active document has the expected timeline
    try:
        preflight = mcp_text("get_timeline_state", index=-1)
        actual_count = preflight.get("timelineCount", 0)
        if actual_count != expected_count:
            raise RuntimeError(
                f"Active document has {actual_count} timeline items, "
                f"but capture expects {expected_count}. "
                f"Ensure the source document is active."
            )
        if verbose:
            print(f"  Pre-flight OK: {actual_count} timeline items")
    except RuntimeError:
        raise
    except Exception as e:
        if verbose:
            print(f"  Pre-flight warning: {e}")

    ground_truth = {}
    for fi, feat in enumerate(timeline):
        if feat.get("isRolledBack"):
            continue
        t0 = time.time()
        try:
            tl_idx = feat.get("index", fi)
            # Use no_restore=True to keep the marker at the current position.
            # This means each call advances forward from the previous position
            # instead of jumping back to the end and then forward again.
            result = mcp_text("get_timeline_state", index=tl_idx,
                              no_restore=True)
            state = get_body_state(result, qualify_duplicates=True)
            ground_truth[fi] = state
            dt = time.time() - t0
            if verbose:
                body_count = len(state)
                idx_note = f" (tl={tl_idx})" if tl_idx != fi else ""
                print(f"  [{fi}] {feat.get('type', '?')}: {feat.get('name', '?')} "
                      f"-> {body_count} bodies ({dt:.1f}s){idx_note}")
        except Exception as e:
            dt = time.time() - t0
            if verbose:
                print(f"  [{fi}] {feat.get('type', '?')}: ERROR ({dt:.1f}s): {e}")
            ground_truth[fi] = {}

    # Roll timeline back to the end and capture the true final state
    end_state = {}
    try:
        end_raw = mcp_text("get_timeline_state", index=-1)
        end_state = get_body_state(end_raw, qualify_duplicates=True)
    except Exception:
        pass

    # Use end-of-timeline state for final validation (not last loop entry,
    # which may be shifted by the SplitBody off-by-one bug)
    ground_truth["_qualified_final"] = end_state

    # Detect and fix GT off-by-one shift from multi-body SplitBody
    ground_truth = _fix_gt_shift(ground_truth, timeline, end_state, verbose)

    return ground_truth


# ── Incremental build ────────────────────────────────────────────

def incremental_build(capture, ground_truth, verbose=False, no_stop=False):
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
    cascade_deltas = {}  # {body_name: volume_offset} — Fusion parametric cascade tracking
    body_drift = {}  # {body_name: {vol_offset, bb_offsets}} — accumulated per-body drift
    snapshot_transforms = {}  # {comp_name: [tx, ty, tz]} — accumulated Snapshot offsets
    body_comp_map = _build_body_component_map(capture)

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
        # Stale scratch doc — close and recreate, then retry
        print("  Closing stale scratch doc and creating fresh one...")
        try:
            mcp("manage_documents", action="close")
            time.sleep(1)
            ensure_scratch_doc(verbose=True)
            _verify_active_unsaved()
            t0 = time.time()
            result = mcp("execute_script", script=prefix, sandbox=False, clean=True)
            dt = time.time() - t0
            if result.get("isError"):
                msg2 = result.get("content", [{}])[0].get("text", "?")[:200]
                print(f"  PREFIX STILL FAILED ({dt:.1f}s): {msg2}")
                return choices, [(-1, f"prefix failed: {msg2}")], cascade_deltas, snapshot_transforms
            print(f"  OK after fresh doc ({dt:.1f}s)")
        except Exception as e:
            print(f"  Recovery failed: {e}")
            return choices, [(-1, f"prefix failed: {msg}")], cascade_deltas, snapshot_transforms
    else:
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

        # Snapshot: execute and auto-match.  occ.transform may be reset by
        # Fusion during timeline modifications.  _apply_snapshot_offsets_conditional
        # detects missing transforms and re-applies them for validation.
        if t == "Snapshot":
            print(f"  [{fi}] {t}: {name}...", end=" ", flush=True)
            transforms = feat.get("transforms", {})
            if transforms:
                for comp_name, trans in transforms.items():
                    snapshot_transforms[comp_name] = trans
            script = generate_feature_script(capture, fi, choices)
            t0 = time.time()
            result = mcp("execute_script", script=script, sandbox=False)
            dt = time.time() - t0
            total_attempts += 1
            if result.get("isError"):
                msg = result.get("content", [{}])[0].get("text", "?")[:200]
                print(f"SCRIPT ERROR ({dt:.1f}s): {msg}")
                errors.append((fi, msg))
                if not no_stop:
                    return choices, errors, cascade_deltas, snapshot_transforms
            else:
                comp_names = ", ".join(transforms.keys()) if transforms else "no transforms"
                print(f"MATCH ({dt:.1f}s) [snapshot: {comp_names}]")
            prev_expected = expected
            continue

        is_ambiguous = fi in ambiguous_map
        af = ambiguous_map.get(fi)
        n_variants = af["variantCount"] if af else 1

        # Re-check variant count for ambiguous extrudes: capture profileCount
        # may have been updated by a prior SKETCH_WARN.
        if is_ambiguous and t == "Extrude":
            fresh_count = count_feature_variants(capture, fi)
            if fresh_count > n_variants:
                n_variants = fresh_count
                # Rebuild af with placeholder descriptions
                af = {"index": fi, "name": name, "type": t,
                      "variantCount": n_variants,
                      "descriptions": [f"variant {i}" for i in range(n_variants)]}
                ambiguous_map[fi] = af

        # Detect if this step changes body volumes (sketch/cplane don't)
        volumes_unchanged = (expected == prev_expected) if prev_expected else False
        prev_expected = expected

        # Defer ambiguous features that don't change volumes — they need
        # validation at the next body-changing step
        if is_ambiguous and volumes_unchanged:
            deferred.append((fi, af))
            # Execute a working variant as placeholder (will undo+retry if deferred resolves)
            print(f"\n--- [{fi}] {t}: {name} ({n_variants} variants, deferred) ---")
            placeholder_ok = False
            for vi in range(n_variants):
                choices[fi] = vi
                script = generate_feature_script(capture, fi, choices)
                r = mcp("execute_script", script=script, sandbox=False)
                total_attempts += 1
                if not r.get("isError"):
                    placeholder_ok = True
                    break
            if not placeholder_ok:
                print(f"  WARNING: all {n_variants} variants errored for deferred [{fi}]")
                errors.append((fi, "all deferred variants errored"))
                return choices, errors, cascade_deltas, snapshot_transforms
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
                    actual = get_body_state(state, qualify_duplicates=True)
                    actual = _apply_snapshot_offsets_conditional(
                        actual, state, snapshot_transforms, body_comp_map)
                except Exception:
                    print("CAPTURE ERROR")
                    tl_now = get_timeline_count()
                    undo_timeline_items(max(0, tl_now - tl_before))
                    continue

                adj_expected = _apply_body_drift(expected, body_drift)
                adj_expected = _apply_cascade_deltas(
                    adj_expected, actual, cascade_deltas)
                match, details = states_match(adj_expected, actual)
                score = state_error(adj_expected, actual)

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
                errors.append((combo_fis[0], "no variant matched"))
                deferred.clear()
                if no_stop:
                    print(f"  -> no combo matched for features {combo_fis} (--no-stop: continuing)")
                else:
                    print(f"  -> STOPPING: no combo matched for features {combo_fis}.")
                    print(f"     Possible causes: missing search variant, reconstruction bug,")
                    print(f"     or API limitation (UI may support features the API cannot replicate).")
                    return choices, errors, cascade_deltas, snapshot_transforms

            deferred.clear()
            if is_ambiguous:
                continue  # current feature already handled in combo

            # Current non-ambiguous feature was also executed — validate it
            try:
                state = mcp_text("get_timeline_state", index=-1)
                actual = get_body_state(state, qualify_duplicates=True)
                actual = _apply_snapshot_offsets_conditional(
                    actual, state, snapshot_transforms, body_comp_map)
                adj_expected = _apply_body_drift(expected, body_drift)
                adj_expected = _apply_cascade_deltas(
                    adj_expected, actual, cascade_deltas)
                match, details = states_match(adj_expected, actual)
                score = state_error(adj_expected, actual)
                if match:
                    print(f"  [{fi}] {t}: {name}... MATCH")
                else:
                    print(f"  [{fi}] {t}: {name}... MISMATCH (err={score:.1f}%)")
                    if verbose:
                        for d in details:
                            print(f"    {d}")
                    errors.append((fi, f"volume mismatch: err={score:.1f}%"))
                _update_body_drift(body_drift, expected, actual,
                                   cascade_deltas=cascade_deltas)
            except Exception:
                pass
            continue

        if is_ambiguous:
            print(f"\n--- [{fi}] {t}: {name} ({n_variants} variants) ---")
        else:
            print(f"  [{fi}] {t}: {name}...", end=" ", flush=True)

        # Track timeline count before
        tl_before = get_timeline_count()

        # Track existing sketches for sketch validation (set-difference matching)
        pre_sketch_ids = set()
        if t == "Sketch":
            try:
                pre_state = mcp_text("get_timeline_state", index=-1, include_sketches=True)
                for sk in pre_state.get("sketches", []):
                    pre_sketch_ids.add((sk.get("name", ""), sk.get("component", "")))
            except Exception:
                pass

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

            # Save for debugging
            with open(f"/tmp/_sb_feat{fi}_v{vi}.py", "w") as _dbg:
                _dbg.write(script)

            # DEBUG: dump profile and curve data before CUT extrudes
            if fi == 26 and vi == 0:
                _dbg_script = """
import adsk.core, adsk.fusion
def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent
    f = open('/tmp/_ext11_debug.txt', 'w')
    for _occ in root.allOccurrences:
        if _occ.component.name == "posts":
            posts_c = _occ.component
            sk = posts_c.sketches.itemByName("Sketch7")
            if sk:
                f.write(f"Sketch7 origin: {sk.origin.x}, {sk.origin.y}, {sk.origin.z}\\n")
                f.write(f"Sketch7 xDir: {sk.xDirection.x}, {sk.xDirection.y}, {sk.xDirection.z}\\n")
                f.write(f"Sketch7 yDir: {sk.yDirection.x}, {sk.yDirection.y}, {sk.yDirection.z}\\n")
                f.write(f"profiles.count={sk.profiles.count}\\n")
                for pi in range(sk.profiles.count):
                    bb = sk.profiles.item(pi).boundingBox
                    f.write(f"  prof[{pi}]: ({bb.minPoint.x:.4f},{bb.minPoint.y:.4f})->({bb.maxPoint.x:.4f},{bb.maxPoint.y:.4f})\\n")
                f.write(f"\\nAll curves ({sk.sketchCurves.count}):\\n")
                for ci in range(sk.sketchCurves.count):
                    c = sk.sketchCurves.item(ci)
                    geo = c.geometry
                    isRef = c.isReference if hasattr(c, 'isReference') else '?'
                    isCons = c.isConstruction if hasattr(c, 'isConstruction') else '?'
                    ctype = type(c).__name__
                    sp = c.startSketchPoint.geometry if hasattr(c, 'startSketchPoint') else None
                    ep = c.endSketchPoint.geometry if hasattr(c, 'endSketchPoint') else None
                    if sp and ep:
                        f.write(f"  c[{ci}] {ctype}: ({sp.x:.4f},{sp.y:.4f})->({ep.x:.4f},{ep.y:.4f}) ref={isRef} cons={isCons}\\n")
                    else:
                        f.write(f"  c[{ci}] {ctype}: (no endpoints) ref={isRef} cons={isCons}\\n")
            for bi in range(posts_c.bRepBodies.count):
                b = posts_c.bRepBodies.item(bi)
                if b.name == "scarf1":
                    sbb = b.boundingBox
                    f.write(f"\\nscarf1 bb: ({sbb.minPoint.x:.4f},{sbb.minPoint.y:.4f},{sbb.minPoint.z:.4f})->({sbb.maxPoint.x:.4f},{sbb.maxPoint.y:.4f},{sbb.maxPoint.z:.4f})\\n")
                    f.write(f"scarf1 vol: {b.volume:.4f}\\n")
            break
    f.close()
"""
                try:
                    mcp("execute_script", script=_dbg_script, sandbox=False)
                except Exception:
                    pass

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
                    if no_stop:
                        print(f"  (--no-stop: continuing past error)")
                    else:
                        print(f"\n  STOPPING: feature [{fi}] script error.")
                        return choices, errors, cascade_deltas, snapshot_transforms

            if result.get("isError"):
                msg = result.get("content", [{}])[0].get("text", "?")[:2000]
                print(f"SCRIPT ERROR ({dt:.1f}s): {msg}")
                if is_ambiguous:
                    tl_after = get_timeline_count()
                    undo_timeline_items(max(0, tl_after - tl_before))
                    continue
                else:
                    errors.append((fi, msg))
                    if no_stop:
                        print(f"  (--no-stop: continuing past error)")
                    else:
                        print(f"\n  STOPPING: feature [{fi}] script error.")
                        return choices, errors, cascade_deltas, snapshot_transforms

            # Get current volumes from scratch doc
            is_sketch_feat = (t == "Sketch")
            try:
                state = mcp_text("get_timeline_state", index=-1,
                                 include_sketches=is_sketch_feat)
                actual = get_body_state(state, qualify_duplicates=True)
                actual = _apply_snapshot_offsets_conditional(
                    actual, state, snapshot_transforms, body_comp_map)
            except Exception as e:
                print(f"CAPTURE ERROR ({dt:.1f}s): {e}")
                if is_ambiguous:
                    tl_after = get_timeline_count()
                    undo_timeline_items(max(0, tl_after - tl_before))
                    continue
                else:
                    errors.append((fi, f"capture error: {e}"))
                    break

            # Apply body drift and cascade deltas to expected before comparison
            adj_expected = _apply_body_drift(expected, body_drift)
            adj_expected = _apply_cascade_deltas(adj_expected, actual, cascade_deltas)
            match, details = states_match(adj_expected, actual)
            score = state_error(adj_expected, actual)

            # For sketch features, also validate curve geometry
            if is_sketch_feat and match:
                actual_sketches = state.get("sketches", [])
                feat_data = capture["timeline"][fi]
                sk_match, sk_details = _compare_sketch(
                    feat_data, actual_sketches, pre_sketch_ids, verbose)
                if not sk_match:
                    # Sketch mismatch is a warning, not a hard failure.
                    # Downstream body validation catches geometry errors that matter.
                    print(f"SKETCH_WARN ({dt:.1f}s)")
                    for d in sk_details:
                        print(f"    {d}")
                    # Update captured profileCount if actual is higher.
                    # This lets extrude variant search try all available profiles.
                    sk_name = feat_data.get("name", "")
                    sk_comp = feat_data.get("component", "")
                    actual_sk = None
                    for ask in actual_sketches:
                        if ask.get("name") == sk_name:
                            actual_sk = ask
                    if actual_sk:
                        act_pc = actual_sk.get("profileCount", 0)
                        cap_pc = feat_data.get("profileCount", 0)
                        if act_pc > cap_pc:
                            feat_data["profileCount"] = act_pc
                    # Don't override match — body state still valid
                elif verbose:
                    for d in sk_details:
                        print(f"    {d}")

            if match:
                print(f"MATCH ({dt:.1f}s)")
                best_vi = vi
                if is_ambiguous:
                    choices[fi] = vi
                break
            else:
                # Detect cascade mismatches (Fusion parametric cascade)
                if not is_ambiguous:
                    new_cascades = _detect_cascades(
                        expected, actual, feat, cascade_deltas)
                    if new_cascades:
                        cascade_deltas.update(new_cascades)
                        cascade_names = ", ".join(new_cascades.keys())
                        # Don't apply body drift here — cascade deltas represent
                        # the same volume offset that drift tracks.  Applying
                        # both would double-count.
                        adj_expected2 = _apply_cascade_deltas(
                            dict(expected), actual, cascade_deltas)
                        match2, details2 = states_match(adj_expected2, actual)
                        if match2:
                            print(f"MATCH ({dt:.1f}s) "
                                  f"[cascade: {cascade_names}]")
                            break
                        # Fallback: accept if residual errors are small
                        # (e.g., fitted spline approximation: 0.05% volume,
                        # or spline CUT amplification: ~2% volume)
                        match3, _ = states_match(
                            adj_expected2, actual, tolerance_pct=APPROX_TOLERANCE_PCT)
                        if match3:
                            print(f"MATCH ({dt:.1f}s) "
                                  f"[cascade: {cascade_names}, approx]")
                            break
                    else:
                        # No cascades — check if all bodies within approx
                        # tolerance (spline approximation without cascades)
                        adj_approx = _apply_body_drift(expected, body_drift)
                        adj_approx = _apply_cascade_deltas(
                            adj_approx, actual, cascade_deltas)
                        match_a, details_a = states_match(
                            adj_approx, actual, tolerance_pct=APPROX_TOLERANCE_PCT)
                        if verbose and not match_a:
                            print(f"[approx check failed]")
                            for d in details_a:
                                if 'x ' in d or 'MISS' in d or 'EXTRA' in d:
                                    print(f"    {d}")
                        if match_a:
                            print(f"MATCH ({dt:.1f}s) [approx]")
                            break

                if is_ambiguous:
                    print(f"no match (err={score:.1f}%, {dt:.1f}s)")
                    if verbose:
                        for d in details:
                            print(f"    {d}")
                    # Slight penalty for offset variants — prefer the simpler
                    # no-offset variant when errors are similar.  Offset is only
                    # correct when the face at the sketch origin actually moved
                    # (full-width profile extrude), which produces a large bb
                    # improvement (>10 pts).  0.5-point penalty prevents marginal
                    # volume differences from selecting wrong offsets.
                    adj_score = score
                    if "offset" in af["descriptions"][vi]:
                        adj_score += 0.5
                    if adj_score < best_score:
                        best_score = adj_score
                        best_vi = vi
                    # Undo and try next variant
                    tl_after = get_timeline_count()
                    undo_timeline_items(max(0, tl_after - tl_before))
                else:
                    # Non-ambiguous mismatch — retry without stale body drift.
                    # JOINs/CUTs can change which sub-geometry determines BB
                    # coordinates, invalidating accumulated drift offsets.
                    if body_drift:
                        adj_no_drift = _apply_cascade_deltas(
                            dict(expected), actual, cascade_deltas)
                        match_nd, details_nd = states_match(
                            adj_no_drift, actual)
                        if match_nd:
                            body_drift.clear()
                            print(f"MATCH ({dt:.1f}s) [drift reset]")
                            break

                    print(f"MISMATCH (err={score:.1f}%, {dt:.1f}s)")
                    for d in details:
                        print(f"    {d}")
                    errors.append((fi, f"mismatch: err={score:.1f}%"))
                    if no_stop:
                        print(f"  (--no-stop: continuing past mismatch)")
                    else:
                        print(f"\n  STOPPING: feature [{fi}] does not match.")
                        print(f"  If all reconstruction options exhausted, check for API limitations")
                        print(f"  (UI may support features the Python API cannot replicate).")
                        return choices, errors, cascade_deltas, snapshot_transforms
                    break

        # Update body drift after feature resolution (match or mismatch).
        # Use the most recent actual state — only available if we didn't undo.
        # For non-ambiguous: actual is still current (not undone).
        # For ambiguous match: actual is current (chosen variant applied).
        # For ambiguous no match: actual was undone; will re-execute below.
        if not is_ambiguous and actual is not None:
            _update_body_drift(body_drift, expected, actual,
                                   cascade_deltas=cascade_deltas)

        # If ambiguous and no exact match, use best variant
        if is_ambiguous and best_vi is not None and fi not in choices:
            choices[fi] = best_vi
            print(f"  -> Best variant {best_vi}: {af['descriptions'][best_vi]} (err={best_score:.1f}%)")
            # Re-execute the best variant (it was undone)
            trial_choices = dict(choices)
            trial_choices[fi] = best_vi
            script = generate_feature_script(capture, fi, trial_choices)
            mcp("execute_script", script=script, sandbox=False)
            # Capture state and update drift after re-executing best variant
            try:
                _st = mcp_text("get_timeline_state", index=-1)
                _act = get_body_state(_st, qualify_duplicates=True)
                _act = _apply_snapshot_offsets_conditional(
                    _act, _st, snapshot_transforms, body_comp_map)
                _update_body_drift(body_drift, expected, _act,
                                   cascade_deltas=cascade_deltas)
            except Exception:
                pass
        elif is_ambiguous and fi in choices:
            # Ambiguous feature matched — update drift from current actual
            if actual is not None:
                _update_body_drift(body_drift, expected, actual,
                                   cascade_deltas=cascade_deltas)
        elif is_ambiguous and best_vi is None:
            errors.append((fi, "no variant matched"))
            if no_stop:
                print(f"  -> no variant matched for [{fi}] (--no-stop: continuing)")
                # Execute the best-scoring variant (least bad) to continue
                if best_vi is not None:
                    trial_choices = dict(choices)
                    trial_choices[fi] = best_vi
                    script = generate_feature_script(capture, fi, trial_choices)
                    mcp("execute_script", script=script, sandbox=False)
            else:
                print(f"  -> STOPPING: no variant matched for [{fi}].")
                return choices, errors, cascade_deltas, snapshot_transforms

    print(f"\nIncremental build complete: {total_attempts} feature executions")
    return choices, errors, cascade_deltas, snapshot_transforms


# ── Final validation ─────────────────────────────────────────────

def final_validate(script, expected_state, cascade_deltas=None,
                   snapshot_transforms=None, body_comp_map=None,
                   verbose=False):
    """Run final validation of the complete script via sandbox."""
    print("\n--- Final validation ---")
    t0 = time.time()
    result = mcp("execute_script", script=script, sandbox=True)
    dt = time.time() - t0

    if result.get("isError"):
        msg = result.get("content", [{}])[0].get("text", "?")[:2000]
        print(f"FAIL: Script error ({dt:.1f}s): {msg}")
        return False

    actual = get_body_state_from_sandbox(result)

    # Apply Snapshot offsets (sandbox BBs don't include occ.transform)
    if snapshot_transforms and body_comp_map:
        actual = _apply_snapshot_offsets(actual, snapshot_transforms,
                                        body_comp_map)

    # Apply cascade deltas with actual data for proper inference
    if cascade_deltas:
        adj_expected = _apply_cascade_deltas(
            expected_state, actual, dict(cascade_deltas))
    else:
        adj_expected = expected_state

    match, details = states_match(adj_expected, actual)

    if not match:
        # Retry with approx tolerance (spline approximation residuals)
        match_approx, details_approx = states_match(
            adj_expected, actual, tolerance_pct=APPROX_TOLERANCE_PCT)
        if match_approx:
            match = True
            details = details_approx

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
    parser.add_argument("--ground-truth", type=str,
                        help="Path to ground truth JSON (load if exists, save after collection)")
    parser.add_argument("--no-stop", action="store_true",
                        help="Don't stop on mismatch, continue building")

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

    # Extract final expected state (from capture, overridden by GT later)
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
        # Try loading from file first
        gt_file = args.ground_truth
        if gt_file and os.path.exists(gt_file):
            with open(gt_file) as f:
                raw = json.load(f)
            # JSON keys are strings — convert back to int (skip special keys)
            ground_truth = {}
            for k, v in raw.items():
                if k.startswith("_"):
                    ground_truth[k] = v  # preserve special keys like _qualified_final
                else:
                    ground_truth[int(k)] = v
            print(f"\nLoaded ground truth from {gt_file} ({len(ground_truth)} features)")
            # Apply shift fix for multi-body SplitBody off-by-one
            timeline = capture.get("timeline", [])
            end_state = ground_truth.get("_qualified_final", {})
            ground_truth = _fix_gt_shift(
                ground_truth, timeline, end_state, verbose=args.verbose)
        else:
            # Ensure source document is active (ground truth reads its timeline)
            src_name = capture.get("designName", "")
            src_activated = False
            if src_name:
                try:
                    list_result = mcp("manage_documents", action="list")
                    docs = json.loads(list_result["content"][0]["text"])
                    active = next((d for d in docs if d["isActive"]), None)
                    if active and active["name"] == src_name:
                        src_activated = True
                    else:
                        src_doc = next((d for d in docs if d["name"] == src_name), None)
                        if src_doc:
                            print(f"Activating source document: {src_name}")
                            mcp("manage_documents", action="activate",
                                index=src_doc["index"])
                            # Verify activation succeeded by re-listing
                            time.sleep(1)  # Allow Fusion UI to settle
                            vfy = mcp("manage_documents", action="list")
                            vfy_docs = json.loads(vfy["content"][0]["text"])
                            vfy_active = next((d for d in vfy_docs if d["isActive"]), None)
                            if vfy_active and vfy_active["name"] == src_name:
                                src_activated = True
                            else:
                                print(f"WARNING: Activation may not have taken effect. "
                                      f"Active: {vfy_active['name'] if vfy_active else '?'}")
                                src_activated = True  # Try anyway
                        else:
                            print(f"ERROR: Source document '{src_name}' not open.")
                            print(f"  Open '{src_name}' in Fusion, or use --ground-truth "
                                  f"<file> to load cached ground truth.")
                            sys.exit(1)
                except Exception as e:
                    print(f"WARNING: Could not check documents: {e}")
            if not src_name or src_name == "(Unsaved)":
                print("ERROR: Capture is from an unsaved document — ground truth "
                      "collection would read stale timeline data.")
                print("  Re-capture from the saved source document, or use "
                      "--skip-ground-truth.")
                sys.exit(1)
            ground_truth = collect_ground_truth(capture, verbose=args.verbose)
            # Save to file for reuse
            if gt_file:
                with open(gt_file, "w") as f:
                    json.dump(ground_truth, f)
                print(f"Saved ground truth to {gt_file}")
    else:
        print("\nSkipping per-feature ground truth (build-only mode)")
        print("  Per-step validation disabled — only script errors will stop the build")
        print("  Final validation against expected body state at the end")
        ground_truth = {}
        # Empty ground truth per step = no per-step volume validation.
        # Script errors still stop the build.

    # Override expected_state with GT qualified data when available
    # (capture component tree may have stale body volumes)
    gt_qualified = ground_truth.get("_qualified_final")
    if gt_qualified:
        print(f"\nOverriding expected state with GT qualified final "
              f"({len(gt_qualified)} bodies)")
        expected_state = gt_qualified

    # ── Switch to scratch doc ──
    ensure_scratch_doc(verbose=args.verbose)

    # ── Build incrementally or default ──
    if args.default_only or not ambiguous:
        if not ambiguous:
            print("\nNo ambiguous features — building with defaults...")
        choices = {}
        # Still do incremental build for validation
        choices, errors, cascade_deltas, snapshot_transforms = incremental_build(
            capture, ground_truth, verbose=args.verbose,
            no_stop=args.no_stop)
    else:
        choices, errors, cascade_deltas, snapshot_transforms = incremental_build(
            capture, ground_truth, verbose=args.verbose,
            no_stop=args.no_stop)

    print(f"\nFinal choices: {choices}")
    if cascade_deltas:
        print(f"Cascade deltas ({len(cascade_deltas)}):")
        for name, delta in sorted(cascade_deltas.items()):
            print(f"  {name}: {delta:+.4f} cm3")
    if errors:
        print(f"Errors ({len(errors)}):")
        for fi, msg in errors:
            print(f"  [{fi}]: {msg}")

    # ── Generate final script ──
    # Always use generate_with_choices (even with empty choices) so that
    # features are wrapped in try/except for graceful partial rebuild.
    script = generate_with_choices(capture, choices)
    print(f"Generated script: {len(script.splitlines())} lines")

    # ── Final validation ──
    # Pass cascade deltas to final_validate so it can apply them with actual
    # data from the sandbox run (avoids false base-name matches when actual=None)
    body_comp_map = _build_body_component_map(capture)
    ok = final_validate(script, expected_state,
                        cascade_deltas=cascade_deltas if cascade_deltas else None,
                        snapshot_transforms=snapshot_transforms if snapshot_transforms else None,
                        body_comp_map=body_comp_map,
                        verbose=args.verbose)

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
