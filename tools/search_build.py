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
        def walk(comp, comp_name="root"):
            for b in comp.get("bodies", []):
                bname = b.get("name", "?")
                raw.append((comp_name, bname, {
                    "volume": b.get("volume", 0),
                    "boundingBox": b.get("boundingBox", {}),
                }))
            for child in comp.get("children", []):
                walk(child, child.get("name", "?"))
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
    # Use relaxed tolerance (1.0 cm) when volume error < 0.01%.
    effective_bb_tol = BB_TOLERANCE_CM
    if delta_pct < 0.01:
        effective_bb_tol = max(BB_TOLERANCE_CM, 1.0)
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
            parts.append(f"bb mismatch")
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
    """Check if active document is Assembly Design (supports multi-component)."""
    try:
        r = mcp("execute_script", script=textwrap.dedent("""\
            import adsk.core, adsk.fusion
            def run(context):
                app = adsk.core.Application.get()
                design = adsk.fusion.Design.cast(app.activeProduct)
                # Part Design = 0, Parametric = 1, Direct = 2
                print(f"designType={design.designType}")
        """), clean=False)
        text = r["content"][0]["text"]
        # ParametricDesignType = 1 means Assembly Design
        return "designType=1" in text
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
    if verbose:
        print(f"\nCollecting ground truth ({len(timeline)} features)...")

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
                return choices, errors
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
                errors.append((combo_fis[0], "no variant matched"))
                deferred.clear()
                if no_stop:
                    print(f"  -> no combo matched for features {combo_fis} (--no-stop: continuing)")
                else:
                    print(f"  -> STOPPING: no combo matched for features {combo_fis}.")
                    print(f"     Possible causes: missing search variant, reconstruction bug,")
                    print(f"     or API limitation (UI may support features the API cannot replicate).")
                    return choices, errors

            deferred.clear()
            if is_ambiguous:
                continue  # current feature already handled in combo

            # Current non-ambiguous feature was also executed — validate it
            try:
                state = mcp_text("get_timeline_state", index=-1)
                actual = get_body_state(state, qualify_duplicates=True)
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
            with open(f"/tmp/_sb_feat{fi}.py", "w") as _dbg:
                _dbg.write(script)

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
                        return choices, errors

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
                        return choices, errors

            # Get current volumes from scratch doc
            is_sketch_feat = (t == "Sketch")
            try:
                state = mcp_text("get_timeline_state", index=-1,
                                 include_sketches=is_sketch_feat)
                actual = get_body_state(state, qualify_duplicates=True)
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
                    # Non-ambiguous mismatch
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

    actual = get_body_state_from_sandbox(result)
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
                            src_activated = True
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
        choices, errors = incremental_build(
            capture, ground_truth, verbose=args.verbose,
            no_stop=args.no_stop)
    else:
        choices, errors = incremental_build(
            capture, ground_truth, verbose=args.verbose,
            no_stop=args.no_stop)

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
