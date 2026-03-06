"""
Round-trip test harness: fixture → capture → export → execute → capture → compare.

Tests the full export_script pipeline by verifying that a generated script
reproduces the original model's body volumes within tolerance.

Usage:
    python tests/test_round_trip.py                    # run all fixtures
    python tests/test_round_trip.py fixture_extrude    # run one fixture
    python tests/test_round_trip.py --list             # list available fixtures

Requires: Fusion 360 running with MCP server on localhost:9100
"""

import json
import os
import subprocess
import sys
import time

MCP_URL = os.environ.get("MCP_URL", "http://localhost:9100")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
TOLERANCE_PCT = 0.1  # body volume tolerance in percent


def mcp(tool, **args):
    """Call an MCP tool via HTTP JSON-RPC."""
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


BB_TOLERANCE_CM = 0.05  # bounding box tolerance in cm


def get_bodies(capture_result):
    """Extract {name: {volume, boundingBox}} from capture_design result."""
    text = capture_result["content"][0]["text"]
    data = json.loads(text)

    bodies = {}
    def walk(comp):
        for b in comp.get("bodies", []):
            name = b.get("name", "?")
            vol = b.get("volume")
            if vol is not None:
                bodies[name] = {
                    "volume": vol,
                    "boundingBox": b.get("boundingBox", {}),
                }
        for child in comp.get("children", []):
            walk(child)
    walk(data["components"])
    return bodies


def get_timeline_features(capture_result):
    """Extract timeline feature list from capture_design result."""
    text = capture_result["content"][0]["text"]
    data = json.loads(text)
    return data.get("timeline", [])


def _ensure_scratch_doc():
    """Ensure we're on a scratch (unsaved) document, never a saved one.
    Reuses an existing unsaved doc if available instead of creating new ones.
    CRITICAL: Aborts if active doc is saved after all attempts — prevents
    destroying user documents with clean=True."""
    try:
        docs = json.loads(mcp("manage_documents", action="list")["content"][0]["text"])
    except Exception:
        raise RuntimeError("Cannot verify active document — aborting to protect saved docs")

    active = next((d for d in docs if d["isActive"]), None)
    if active and not active["isSaved"]:
        return  # already on an unsaved doc, reuse it

    # Try to activate an existing unsaved doc
    for d in docs:
        if not d["isSaved"] and not d["isActive"]:
            mcp("manage_documents", action="activate", index=d["index"])
            # Verify switch worked
            docs2 = json.loads(mcp("manage_documents", action="list")["content"][0]["text"])
            active2 = next((d for d in docs2 if d["isActive"]), None)
            if active2 and not active2["isSaved"]:
                return
            # Switch failed — fall through to creation

    # No unsaved doc exists — create Assembly Design (not Part Design)
    import textwrap
    mcp("execute_script", script=textwrap.dedent("""\
        import adsk.core
        def run(context):
            app = adsk.core.Application.get()
            app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    """), clean=False)

    # CRITICAL: Verify the active doc is now unsaved
    docs3 = json.loads(mcp("manage_documents", action="list")["content"][0]["text"])
    active3 = next((d for d in docs3 if d["isActive"]), None)
    if not active3 or active3["isSaved"]:
        raise RuntimeError(
            f"FATAL: Active doc '{active3['name'] if active3 else '?'}' is SAVED "
            f"after scratch doc creation. Aborting to prevent data loss."
        )


def run_fixture(name, fixture_path, verbose=False):
    """Run round-trip test for one fixture.

    Returns (passed: bool, details: dict)
    """
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    # Safety: never run fixtures on a saved document
    _ensure_scratch_doc()

    with open(fixture_path) as f:
        fixture_script = f.read()

    details = {"name": name, "steps": []}

    # Step 1: Execute fixture script (creates original design)
    print("  [1/5] Executing fixture...")
    t0 = time.time()
    r = mcp("execute_script", script=fixture_script, clean=True)
    dt = time.time() - t0
    details["steps"].append({"step": "execute_fixture", "time": round(dt, 1)})
    if r.get("isError"):
        msg = r.get("content", [{}])[0].get("text", "unknown error")
        print(f"  FAIL: Fixture execution failed:\n    {msg[:200]}")
        details["error"] = f"fixture execution: {msg[:200]}"
        return False, details

    # Step 2: Capture original design
    print("  [2/5] Capturing original...")
    t0 = time.time()
    orig_cap = mcp("capture_design")
    dt = time.time() - t0
    details["steps"].append({"step": "capture_original", "time": round(dt, 1)})
    original_bodies = get_bodies(orig_cap)
    details["originalBodies"] = {n: b["volume"] for n, b in original_bodies.items()}
    print(f"    Bodies: {list(original_bodies.keys())}")

    if not original_bodies:
        print("  FAIL: No bodies in original design")
        details["error"] = "no bodies in original"
        return False, details

    # Step 3: Export script
    print("  [3/5] Exporting script...")
    t0 = time.time()
    r = mcp("export_script")
    dt = time.time() - t0
    details["steps"].append({"step": "export_script", "time": round(dt, 1)})
    if r.get("isError"):
        msg = r.get("content", [{}])[0].get("text", "unknown error")
        print(f"  FAIL: Export failed:\n    {msg[:200]}")
        details["error"] = f"export: {msg[:200]}"
        return False, details
    exported_script = r["content"][0]["text"]
    details["exportedLines"] = len(exported_script.splitlines())

    if verbose:
        print(f"    Exported script ({details['exportedLines']} lines):")
        for i, line in enumerate(exported_script.splitlines()[:20], 1):
            print(f"      {i:3d}  {line}")
        if details["exportedLines"] > 20:
            print(f"      ... ({details['exportedLines'] - 20} more lines)")

    # Step 4: Execute exported script (overwrites original)
    print("  [4/5] Executing exported script...")
    t0 = time.time()
    r = mcp("execute_script", script=exported_script, clean=True)
    dt = time.time() - t0
    details["steps"].append({"step": "execute_export", "time": round(dt, 1)})
    if r.get("isError"):
        msg = r.get("content", [{}])[0].get("text", "unknown error")
        print(f"  FAIL: Exported script execution failed:\n    {msg[:200]}")
        details["error"] = f"export execution: {msg[:200]}"
        # Save the failing script for debugging
        fail_path = os.path.join(os.path.dirname(fixture_path), f"{name}_FAILED.py")
        with open(fail_path, "w") as f:
            f.write(exported_script)
        print(f"    Failing script saved to: {fail_path}")
        return False, details

    # Step 5: Capture replica design
    print("  [5/5] Capturing replica...")
    t0 = time.time()
    replica_cap = mcp("capture_design")
    dt = time.time() - t0
    details["steps"].append({"step": "capture_replica", "time": round(dt, 1)})
    replica_bodies = get_bodies(replica_cap)
    details["replicaBodies"] = {n: b["volume"] for n, b in replica_bodies.items()}

    # Compare volumes and bounding boxes
    print(f"\n  Volume + bbox comparison:")
    passed = True
    comparisons = []

    for bname, orig in sorted(original_bodies.items()):
        orig_vol = orig["volume"]
        rep = replica_bodies.get(bname)
        if rep is None:
            print(f"    {bname}: MISSING in replica")
            passed = False
            comparisons.append({"body": bname, "original": orig_vol, "replica": None, "status": "MISSING"})
        else:
            rep_vol = rep["volume"]
            if orig_vol == 0:
                delta_pct = 0 if rep_vol == 0 else 100
            else:
                delta_pct = abs(rep_vol - orig_vol) / abs(orig_vol) * 100
            vol_ok = delta_pct < TOLERANCE_PCT

            # Bounding box check
            orig_bb = orig.get("boundingBox", {})
            rep_bb = rep.get("boundingBox", {})
            bb_ok = True
            bb_delta = 0.0
            if orig_bb and rep_bb:
                for key in ("min", "max"):
                    op = orig_bb.get(key, [0, 0, 0])
                    rp = rep_bb.get(key, [0, 0, 0])
                    for i in range(3):
                        d = abs(op[i] - rp[i])
                        bb_delta = max(bb_delta, d)
                        if d > BB_TOLERANCE_CM:
                            bb_ok = False

            if vol_ok and bb_ok:
                status = "OK"
            elif vol_ok and not bb_ok:
                status = "BBOX_FAIL"
            else:
                status = "FAIL"

            sym = "✓" if status == "OK" else "✗"
            bb_str = f" bb={bb_delta:.4f}cm" if orig_bb and rep_bb else ""
            print(f"    {sym} {bname}: {orig_vol:.4f} → {rep_vol:.4f} ({delta_pct:.3f}%){bb_str} {status}")
            if status != "OK":
                passed = False
            comparisons.append({
                "body": bname, "original": orig_vol, "replica": rep_vol,
                "deltaPct": round(delta_pct, 4), "bbDelta": round(bb_delta, 4),
                "bbStatus": "OK" if bb_ok else "FAIL", "status": status,
            })

    # Check for extra bodies in replica
    for bname in sorted(replica_bodies.keys()):
        if bname not in original_bodies:
            print(f"    + {bname}: EXTRA body in replica (vol={replica_bodies[bname]['volume']:.4f})")
            passed = False
            comparisons.append({"body": bname, "replica": replica_bodies[bname]["volume"], "status": "EXTRA"})

    details["comparisons"] = comparisons

    total_time = sum(s["time"] for s in details["steps"])
    print(f"\n  Result: {'PASS' if passed else 'FAIL'} ({total_time:.1f}s)")
    return passed, details


def discover_fixtures():
    """Find all fixture scripts in the fixtures directory."""
    fixtures = {}
    if not os.path.isdir(FIXTURES_DIR):
        return fixtures
    for fname in sorted(os.listdir(FIXTURES_DIR)):
        if fname.startswith("fixture_") and fname.endswith(".py"):
            name = fname[:-3]  # strip .py
            fixtures[name] = os.path.join(FIXTURES_DIR, fname)
    return fixtures


def main():
    args = sys.argv[1:]
    verbose = "--verbose" in args or "-v" in args
    args = [a for a in args if a not in ("--verbose", "-v")]

    fixtures = discover_fixtures()
    if not fixtures:
        print(f"No fixtures found in {FIXTURES_DIR}")
        sys.exit(1)

    if "--list" in args:
        print("Available fixtures:")
        for name in fixtures:
            print(f"  {name}")
        sys.exit(0)

    # Filter to requested fixtures
    if args:
        selected = {}
        for a in args:
            key = a if a.startswith("fixture_") else f"fixture_{a}"
            if key in fixtures:
                selected[key] = fixtures[key]
            else:
                print(f"Unknown fixture: {a}")
                print(f"Available: {', '.join(fixtures.keys())}")
                sys.exit(1)
        fixtures = selected

    # Run tests
    results = {}
    passed_count = 0
    failed_count = 0

    print(f"\nRunning {len(fixtures)} round-trip test(s)...")
    print(f"MCP server: {MCP_URL}")

    for name, path in fixtures.items():
        ok, details = run_fixture(name, path, verbose=verbose)
        results[name] = {"passed": ok, "details": details}
        if ok:
            passed_count += 1
        else:
            failed_count += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"  SUMMARY: {passed_count} passed, {failed_count} failed, {len(fixtures)} total")
    print(f"{'='*60}")
    for name, r in results.items():
        status = "PASS" if r["passed"] else "FAIL"
        error = r["details"].get("error", "")
        suffix = f" — {error}" if error else ""
        print(f"  {'✓' if r['passed'] else '✗'} {name}: {status}{suffix}")

    # Save detailed results
    results_path = os.path.join(os.path.dirname(__file__), "round_trip_results.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results: {results_path}")

    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    main()
