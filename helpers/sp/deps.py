import adsk.core
import adsk.fusion


def validate_deps(ctx, metadata_path=None):
    """Validate dependency tree from model.json.

    Hard checks (affect pass/fail):
    1. Single origin — only 1 body may reference "origin"
    2. Sketch origin — non-root sketches must not dimension from sk.originPoint
    3. Bodies in components — no bodies in root component

    Advisory (printed but don't affect pass/fail):
    4. Completeness — are all design bodies tracked in model.json?

    Returns True/False, or None if no model.json found.
    """
    import json
    import os
    import re

    if metadata_path is None:
        script_path = None
        try:
            from server.document_tracker import DocumentTracker
            script_path = DocumentTracker._script_path
        except Exception:
            pass
        if script_path:
            script_dir = os.path.dirname(script_path)
            stem = os.path.splitext(os.path.basename(script_path))[0]
            per_script = os.path.join(script_dir, f"{stem}_model.json")
            if os.path.exists(per_script):
                metadata_path = per_script
            else:
                metadata_path = os.path.join(script_dir, "model.json")
        else:
            print("validate_deps: no metadata path and no script path found")
            return None

    if not os.path.exists(metadata_path):
        print(f"validate_deps: {metadata_path} not found — skipping "
              f"(create model.json to enable dependency validation)")
        return None

    with open(metadata_path, "r") as f:
        meta = json.load(f)

    deps = meta.get("deps", [])
    if not deps:
        print("validate_deps: no deps entries in metadata")
        return True

    print(f"\n=== Dependency tree ({len(deps)} entries) ===")
    all_ok = True

    origin_refs = [d["body"] for d in deps if d["ref"] == "origin"]
    if len(origin_refs) > 1:
        print(f"  FAIL  {len(origin_refs)} bodies reference origin "
              f"(only 1 allowed): {origin_refs}")
        print(f"         Chain other bodies off the first one instead.")
        all_ok = False
    elif len(origin_refs) == 1:
        print(f"   OK   Single origin root: {origin_refs[0]}")
    else:
        print(f"  FAIL  No body references origin — need exactly 1 root")
        all_ok = False

    for entry in deps:
        body_name = entry["body"]
        ref_name = entry["ref"]
        body = ctx.find_body(body_name)
        if body:
            print(f"   OK   {body_name} → {ref_name}")
        else:
            print(f"  SKIP  {body_name} → {ref_name}: body not found")

    origin_bodies = set(d["body"] for d in deps if d["ref"] == "origin")
    origin_dim_issues = []

    def _check_sketch_origin(comp, comp_name):
        for si in range(comp.sketches.count):
            sk = comp.sketches.item(si)
            origin_pt = sk.originPoint
            for di in range(sk.sketchDimensions.count):
                dim = sk.sketchDimensions.item(di)
                try:
                    e1 = dim.entityOne
                    e2 = dim.entityTwo
                    uses_origin = False
                    if hasattr(e1, 'geometry') and hasattr(origin_pt, 'geometry'):
                        if (abs(e1.geometry.x - origin_pt.geometry.x) < 0.001 and
                            abs(e1.geometry.y - origin_pt.geometry.y) < 0.001):
                            uses_origin = True
                    if hasattr(e2, 'geometry') and hasattr(origin_pt, 'geometry'):
                        if (abs(e2.geometry.x - origin_pt.geometry.x) < 0.001 and
                            abs(e2.geometry.y - origin_pt.geometry.y) < 0.001):
                            uses_origin = True
                    if uses_origin:
                        expr = dim.parameter.expression if dim.parameter else "?"
                        origin_dim_issues.append(
                            f"{comp_name}/{sk.name}: dim '{expr}' "
                            f"references sketch origin")
                except Exception:
                    pass

    for j in range(ctx.root.occurrences.count):
        occ = ctx.root.occurrences.item(j)
        comp = occ.component
        comp_bodies_in = set()
        for bi in range(comp.bRepBodies.count):
            comp_bodies_in.add(comp.bRepBodies.item(bi).name)
        has_root_body = bool(comp_bodies_in & origin_bodies)
        if not has_root_body:
            _check_sketch_origin(comp, comp.name)

    if origin_dim_issues:
        print("--- Sketch origin check ---")
        for issue in origin_dim_issues[:10]:
            print(f"  FAIL  {issue}")
        if len(origin_dim_issues) > 10:
            print(f"         ... and {len(origin_dim_issues) - 10} more")
        print(f"  Non-root sketches must dimension from projected "
              f"reference geometry, not sketch origin.")
        all_ok = False
    else:
        print("   OK   No non-root sketches dimension from origin")

    root_bodies = []
    for i in range(ctx.root.bRepBodies.count):
        root_bodies.append(ctx.root.bRepBodies.item(i).name)

    if root_bodies:
        print(f"  FAIL  {len(root_bodies)} bodies in root component "
              f"(should be inside a component):")
        for rb in root_bodies[:10]:
            print(f"         - {rb}")
        if len(root_bodies) > 10:
            print(f"         ... and {len(root_bodies) - 10} more")
        all_ok = False

    import fnmatch as _fnmatch
    print("--- Completeness check (advisory) ---")
    tracked = set(entry["body"] for entry in deps)
    replica_patterns = []
    for entry in deps:
        if "replicas" in entry:
            replica_patterns.append(entry["replicas"])

    comp_bodies = []
    for j in range(ctx.root.occurrences.count):
        comp = ctx.root.occurrences.item(j).component
        for i in range(comp.bRepBodies.count):
            comp_bodies.append(comp.bRepBodies.item(i).name)

    all_bodies = root_bodies + comp_bodies
    orphans = []
    for name in all_bodies:
        if name in tracked:
            continue
        base = re.sub(r'(\s*\(\d+\))+$', '', name)
        if base in tracked:
            continue
        if any(_fnmatch.fnmatch(name, pat) for pat in replica_patterns):
            continue
        orphans.append(name)

    if orphans:
        for o in orphans:
            print(f"  NOTE  {o}: exists in design but not in model.json")
    else:
        print(f"   OK   All {len(all_bodies)} bodies are tracked")

    status = "PASS" if all_ok else "FAIL"
    print(f"=== Dependency validation: {status} ===\n")
    return all_ok
