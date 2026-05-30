import adsk.core
import adsk.fusion


def _resolves(curve):
    """True if a reference curve resolves to real BRep geometry it was projected from."""
    try:
        return curve.referencedEntity is not None
    except Exception:
        # Some projected/intersected refs (e.g. intersectWithSketchPlane) have
        # no referencedEntity but are still genuine references — treat as resolved.
        return True


def _curve_points(curve):
    """All defining SketchPoints of a curve (start/end/center where present)."""
    pts = []
    for attr in ("startSketchPoint", "endSketchPoint", "centerSketchPoint"):
        try:
            p = getattr(curve, attr, None)
            if p:
                pts.append(p)
        except Exception:
            pass
    return pts


def _is_spline(curve):
    try:
        return hasattr(curve, "fitPoints")
    except Exception:
        return False


def _fc_modulo_spline_interiors(sk):
    """Is the sketch fully constrained once fit-point spline INTERIORS are
    exempted?

    A free spline interior point makes the whole sketch report
    isFullyConstrained == False, which on its own can't tell a legitimate
    'constrained frame + draggable sculpted edge' profile apart from a genuinely
    loose one. So we temporarily pin each spline's interior fit points (start/end
    excluded — those must still anchor), ask Fusion's solver, then restore the
    exact prior state. If the answer is True, the ONLY free DOF were the
    draggable spline interiors; if False, something else (a loose line, a free
    radius, an unanchored spline end) remains under-constrained.

    Mutates-and-restores within a try/finally so the model is left untouched.
    This is safe for the document tracker: ActionLog logs UI commandTerminated
    events, not API mutations, so this toggle adds no entries and does not affect
    pendingChanges / clean=True gating. Cost is one solver recompute per
    under-constrained spline sketch.
    """
    saved = []
    pin_failures = 0
    try:
        for ci in range(sk.sketchCurves.count):
            cur = sk.sketchCurves.item(ci)
            if getattr(cur, "isReference", False) or not _is_spline(cur):
                continue
            try:
                fps = cur.fitPoints
            except Exception:
                continue
            for k in range(1, fps.count - 1):       # interiors only
                fp = fps.item(k)
                try:
                    saved.append((fp, fp.isFixed))
                    fp.isFixed = True
                except Exception:
                    pin_failures += 1
        if pin_failures:
            # Don't fail silently: a legitimate sculpted profile would look
            # under-constrained if pinning didn't take (e.g. a Fusion-version
            # regression making SketchPoint.isFixed unsettable).
            print(f"  WARN  could not pin {pin_failures} spline interior point(s) "
                  f"in '{getattr(sk, 'name', '?')}' — traceability result may be "
                  f"spurious (is SketchPoint.isFixed settable in this Fusion build?)")
        return _is_fully_constrained(sk)
    finally:
        for fp, val in saved:
            try:
                fp.isFixed = val
            except Exception:
                pass


def _is_fixed(entity):
    """True if the entity is pinned by a Fix/Ground constraint (absolute coords)."""
    try:
        return bool(entity.isFixed)
    except Exception:
        return False


def _has_fix(curve):
    """True if a drawn curve, or ANY of its points (including spline fit points),
    is pinned by a Fix/Ground constraint. Inspecting fit points matters: an
    author could pin spline interiors to force full constraint and slip the
    absolute-coordinate shortcut past the check."""
    if _is_fixed(curve):
        return True
    for p in _curve_points(curve):
        if _is_fixed(p):
            return True
    if _is_spline(curve):
        try:
            fps = curve.fitPoints
            for k in range(fps.count):
                if _is_fixed(fps.item(k)):
                    return True
        except Exception:
            pass
    return False


def _is_fully_constrained(sk):
    """Fusion's own verdict that zero free DOF remain. Ground truth for 'no
    unreferenced coordinate survives' — defaults False (stricter) if unavailable."""
    try:
        return bool(sk.isFullyConstrained)
    except Exception:
        return False


def _curve_kind(curve):
    try:
        return curve.objectType.split("::")[-1]
    except Exception:
        return "curve"


def _check_sketch_anchoring(comp, comp_name, is_root_comp, issues):
    """Verify every drawn sketch entity is positioned by a reference, not a
    computed coordinate — using Fusion's own solver as the judge of 'no free
    coordinate remains', rather than re-implementing constraint propagation.

    Per non-root sketch, all of:
      (a) ANCHORED — contains >=1 projected reference resolving to real BRep
          geometry. (Root component exempt: may anchor to the world origin.)
      (b) NO FIX — no drawn curve/point is pinned by a Fix/Ground constraint
          (that bypasses the reference with an absolute coordinate).
      (c) DETERMINED — the sketch is fully constrained, EXCEPT that fit-point
          spline interiors may stay free (the drag-to-shape workflow). Combined
          with (a), (b), and the separate origin check, full constraint proves
          every point is solved relative to the projected reference (a rigid
          sketch that floats freely is, by definition, NOT fully constrained).

    For (c): if sketch.isFullyConstrained is True, done. Otherwise the only
    sanctioned freedom is spline interiors — so pin those interiors and re-ask
    the solver (`_fc_modulo_spline_interiors`). This lets a 'constrained frame +
    draggable sculpted edge' profile pass (the common real case: Foot, Cap,
    Stretcher, …) while still failing a genuinely loose line, a free radius, or
    an unanchored spline END. It does NOT re-implement constraint propagation,
    so it never false-positives a correct rectangle/slot/arc whose interior
    vertices the solver grounds through geometry rather than dimensions.
    """
    for si in range(comp.sketches.count):
        sk = comp.sketches.item(si)

        ref_curves, drawn_curves = [], []
        for ci in range(sk.sketchCurves.count):
            c = sk.sketchCurves.item(ci)
            is_ref = bool(getattr(c, "isReference", False))
            is_con = bool(getattr(c, "isConstruction", False))
            if is_ref:
                ref_curves.append(c)
            elif not is_con:
                drawn_curves.append(c)

        if not drawn_curves:
            continue  # pure reference / identify sketch — nothing to anchor

        resolved = [c for c in ref_curves if _resolves(c)]

        # (a) Anchored to real projected geometry.
        if not is_root_comp and not resolved:
            issues.append(
                f"{comp_name}/{sk.name}: NOT ANCHORED — no projected reference "
                f"geometry; {len(drawn_curves)} drawn curve(s) placed at computed "
                f"coordinates")
            continue

        # (b) No Fix/Ground shortcut (inspects spline fit points too).
        fixed = [c for c in drawn_curves if _has_fix(c)]
        if fixed:
            issues.append(
                f"{comp_name}/{sk.name}: {len(fixed)} drawn curve(s) use a "
                f"Fix/Ground constraint — pins absolute coordinates instead of "
                f"referencing a parent")
            continue

        # (c) Let Fusion's solver decide. Fully constrained ⟹ every point is
        # determined relative to the projected reference (given a, b, no-origin).
        if _is_fully_constrained(sk):
            continue

        # Not fully constrained. The only sanctioned freedom is fit-point spline
        # interiors. If there's no spline at all, the free DOF can't be excused.
        if not any(_is_spline(c) for c in drawn_curves):
            kinds = ", ".join(sorted({_curve_kind(c) for c in drawn_curves}))
            issues.append(
                f"{comp_name}/{sk.name}: UNDER-CONSTRAINED — free coordinates "
                f"remain ({kinds}) and there is no draggable spline to excuse "
                f"them. Fully constrain against the projected reference.")
            continue

        # Pin spline interiors and re-ask the solver. If still not fully
        # constrained, something beyond the interiors is loose — a line, a
        # radius, or an unanchored spline start/end.
        if not _fc_modulo_spline_interiors(sk):
            issues.append(
                f"{comp_name}/{sk.name}: UNDER-CONSTRAINED — free coordinates "
                f"remain even after exempting spline interiors. Anchor every "
                f"line/arc and each spline's start/end to the projected reference "
                f"(only fit-point spline interiors may stay free).")
            continue
        # else: only spline interiors are free → legitimate sculpted profile.


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

    def _parents(entry):
        """Parent reference(s) for a dep entry. Accepts a single "ref" string OR
        a list (a body may bear on more than one parent — e.g. a wedge that seats
        against a post AND rides a stretcher; a shelf into two sides). Every body
        must reference at least one parent, but the count is not capped at one —
        only the ORIGIN root is unique. Returns a list of parent names."""
        r = entry.get("refs", entry.get("ref"))
        if r is None:
            return []
        return list(r) if isinstance(r, (list, tuple)) else [r]

    origin_refs = [d["body"] for d in deps if "origin" in _parents(d)]
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
        body = ctx.find_body(body_name)
        for ref_name in _parents(entry):
            if body:
                print(f"   OK   {body_name} → {ref_name}")
            else:
                print(f"  SKIP  {body_name} → {ref_name}: body not found")

    origin_bodies = set(d["body"] for d in deps if "origin" in _parents(d))
    origin_dim_issues = []
    anchor_issues = []

    def _check_sketch_origin(comp, comp_name):
        for si in range(comp.sketches.count):
            sk = comp.sketches.item(si)
            origin_pt = sk.originPoint
            try:
                otok = origin_pt.entityToken
            except Exception:
                otok = None
            try:
                ogeo = origin_pt.geometry
            except Exception:
                ogeo = None
            for di in range(sk.sketchDimensions.count):
                dim = sk.sketchDimensions.item(di)
                try:
                    # Match the origin point by IDENTITY, not coordinate
                    # coincidence. A legitimately-anchored sketch can dimension
                    # from a PROJECTED parent corner that happens to land on the
                    # sketch origin (e.g. a parent body at the world origin) —
                    # that is a real reference, not an origin dim, and a
                    # proximity test would false-flag it. Only sk.originPoint
                    # itself counts.
                    #
                    # Fallback: if the entityToken is unavailable, drop back to
                    # the old coordinate-proximity test so the check fails CLOSED
                    # (a tokenless sketch is still checked) rather than silently
                    # passing.
                    uses_origin = False
                    for ent in (dim.entityOne, dim.entityTwo):
                        try:
                            if otok is not None:
                                if ent.entityToken == otok:
                                    uses_origin = True
                                    break
                            elif ogeo is not None:
                                g = ent.geometry
                                if (abs(g.x - ogeo.x) < 0.001 and
                                        abs(g.y - ogeo.y) < 0.001):
                                    uses_origin = True
                                    break
                        except Exception:
                            pass
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
        _check_sketch_anchoring(comp, comp.name, has_root_body, anchor_issues)

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

    if anchor_issues:
        print("--- Sketch traceability check ---")
        for issue in anchor_issues[:15]:
            print(f"  FAIL  {issue}")
        if len(anchor_issues) > 15:
            print(f"         ... and {len(anchor_issues) - 15} more")
        print(f"  Every non-root sketch must (1) project real reference geometry, "
              f"(2) avoid Fix/Ground constraints, and (3) be fully constrained "
              f"relative to that reference (Fusion's solver is the judge). Only "
              f"fit-point spline interiors may remain free; their start/end may not.")
        all_ok = False
    else:
        print("   OK   All non-root sketches fully constrained against references")

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
