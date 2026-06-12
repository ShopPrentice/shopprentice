"""
Validate Design Tool

Single-call structural validation that runs all checks:
1. Connectivity — all structural bodies form 1 connected cluster via face contact
2. Interference — no unintended body overlaps (excludes void-on-void)

Returns a combined pass/fail result with details from each check.
"""

import traceback
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register
import adsk.core
import adsk.fusion

app = adsk.core.Application.get()

TOL_CM = 0.05  # 0.5mm tolerance for face coplanarity
DEFAULT_MIN_CONTACT_CM2 = 1.0


# ── Connectivity Check ───────────────────────────────────────────────

def _collect_bodies(root_comp):
    """Collect all bodies with world-space bounding boxes and body references."""
    bodies = []
    for i in range(root_comp.bRepBodies.count):
        b = root_comp.bRepBodies.item(i)
        bb = b.boundingBox
        if bb:
            bodies.append({
                "name": b.name,
                "min": [bb.minPoint.x, bb.minPoint.y, bb.minPoint.z],
                "max": [bb.maxPoint.x, bb.maxPoint.y, bb.maxPoint.z],
                "body": b,
            })
    for occ in root_comp.allOccurrences:
        comp = occ.component
        for i in range(comp.bRepBodies.count):
            b = comp.bRepBodies.item(i)
            proxy = b.createForAssemblyContext(occ)
            bb = proxy.boundingBox
            if bb:
                bodies.append({
                    "name": b.name,
                    "min": [bb.minPoint.x, bb.minPoint.y, bb.minPoint.z],
                    "max": [bb.maxPoint.x, bb.maxPoint.y, bb.maxPoint.z],
                    "body": proxy,
                })
    return bodies


def _bb_touches(a, b):
    for axis in range(3):
        if a["max"][axis] + TOL_CM < b["min"][axis]:
            return False
        if b["max"][axis] + TOL_CM < a["min"][axis]:
            return False
    return True


def _planar_faces(body):
    result = []
    for i in range(body.faces.count):
        face = body.faces.item(i)
        if face.geometry.surfaceType != adsk.core.SurfaceTypes.PlaneSurfaceType:
            continue
        ok, normal = face.evaluator.getNormalAtPoint(face.pointOnFace)
        if not ok:
            continue
        bb = face.boundingBox
        if not bb:
            continue
        result.append({
            "normal": normal,
            "point": face.pointOnFace,
            "bb_min": [bb.minPoint.x, bb.minPoint.y, bb.minPoint.z],
            "bb_max": [bb.maxPoint.x, bb.maxPoint.y, bb.maxPoint.z],
            "area": face.area,
        })
    return result


def _contact_area(faces_a, faces_b, tol_cm):
    total = 0.0
    for fa in faces_a:
        na = fa["normal"]
        pa = fa["point"]
        a_min, a_max = fa["bb_min"], fa["bb_max"]
        for fb in faces_b:
            nb = fb["normal"]
            dot = na.x * nb.x + na.y * nb.y + na.z * nb.z
            if dot > -0.95:
                continue
            dx = fb["point"].x - pa.x
            dy = fb["point"].y - pa.y
            dz = fb["point"].z - pa.z
            dist = abs(dx * na.x + dy * na.y + dz * na.z)
            if dist > tol_cm:
                continue
            b_min, b_max = fb["bb_min"], fb["bb_max"]
            abs_nx, abs_ny, abs_nz = abs(na.x), abs(na.y), abs(na.z)
            if abs_nx >= abs_ny and abs_nx >= abs_nz:
                o1 = min(a_max[1], b_max[1]) - max(a_min[1], b_min[1])
                o2 = min(a_max[2], b_max[2]) - max(a_min[2], b_min[2])
            elif abs_ny >= abs_nx and abs_ny >= abs_nz:
                o1 = min(a_max[0], b_max[0]) - max(a_min[0], b_min[0])
                o2 = min(a_max[2], b_max[2]) - max(a_min[2], b_min[2])
            else:
                o1 = min(a_max[0], b_max[0]) - max(a_min[0], b_min[0])
                o2 = min(a_max[1], b_max[1]) - max(a_min[1], b_min[1])
            if o1 <= 0 or o2 <= 0:
                continue
            area = min(o1 * o2, fa["area"], fb["area"])
            total += area
    return total


def _check_connectivity(bodies, exclude_prefixes, min_contact_cm2):
    structural = []
    for i, b in enumerate(bodies):
        skip = any(b["name"].startswith(p) for p in exclude_prefixes)
        if not skip:
            structural.append((i, b))

    faces_cache = {}
    for idx, b in structural:
        faces_cache[idx] = _planar_faces(b["body"])

    parent = list(range(len(bodies)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    connections = []
    weak = []

    for i_idx in range(len(structural)):
        idx_a, a = structural[i_idx]
        for j_idx in range(i_idx + 1, len(structural)):
            idx_b, b = structural[j_idx]
            if not _bb_touches(a, b):
                continue
            area = _contact_area(
                faces_cache[idx_a], faces_cache[idx_b], TOL_CM
            )
            if area > 0.01:
                union(idx_a, idx_b)
                conn = {
                    "bodyA": a["name"],
                    "bodyB": b["name"],
                    "contactArea": round(area, 2),
                }
                connections.append(conn)
                if area < min_contact_cm2:
                    weak.append(conn)

    clusters = {}
    for idx, b in structural:
        root = find(idx)
        clusters.setdefault(root, []).append(b["name"])

    cluster_list = []
    for _, members in sorted(clusters.items(), key=lambda x: -len(x[1])):
        cluster_list.append({"bodyCount": len(members), "bodies": members})

    return {
        "connected": len(clusters) == 1,
        "clusterCount": len(clusters),
        "structuralBodyCount": len(structural),
        "connections": connections,
        "weakConnections": weak,
        "clusters": cluster_list,
    }


# ── Interference Check ───────────────────────────────────────────────

def _check_interference(root_comp, exclude_prefixes):
    body_list = []
    for i in range(root_comp.bRepBodies.count):
        body_list.append(root_comp.bRepBodies.item(i))
    for occ in root_comp.allOccurrences:
        for i in range(occ.component.bRepBodies.count):
            body_list.append(occ.component.bRepBodies.item(i))

    if len(body_list) < 2:
        return {"interferenceCount": 0, "realCount": 0, "interferences": []}

    design = adsk.fusion.Design.cast(app.activeProduct)
    body_collection = adsk.core.ObjectCollection.create()
    for b in body_list:
        body_collection.add(b)

    interference_input = design.createInterferenceInput(body_collection)
    interference_results = design.analyzeInterference(interference_input)

    all_interferences = []
    real_interferences = []

    for i in range(interference_results.count):
        result = interference_results.item(i)
        entry = {}
        try:
            entry["body1"] = result.entityOne.name
        except Exception:
            entry["body1"] = "unknown"
        try:
            entry["body2"] = result.entityTwo.name
        except Exception:
            entry["body2"] = "unknown"
        try:
            entry["volume"] = round(result.interferenceBody.volume, 4)
        except Exception:
            pass
        all_interferences.append(entry)

        b1_void = any(entry["body1"].startswith(p) for p in exclude_prefixes)
        b2_void = any(entry["body2"].startswith(p) for p in exclude_prefixes)
        if not (b1_void or b2_void):
            real_interferences.append(entry)

    return {
        "interferenceCount": len(all_interferences),
        "realCount": len(real_interferences),
        "interferences": real_interferences,
    }


# ── Feature Impact Check ─────────────────────────────────────────────

def _check_feature_impact(design):
    """Find timeline features that exist but change no geometry.

    A CUT whose profile/tool never intersects its target is a silent
    modeling bug (e.g. a taper wedge sketched on the wrong side of a
    construction plane lands below the floor and removes nothing) — the
    feature computes "successfully", the body keeps its full volume, and
    connectivity/interference/deps checks all still pass. Empirically
    (probed June 2026):
      - no-op CUT extrude:  healthState=WARNING, faces.count == 0
      - no-op CUT combine:  healthState=HEALTHY(!), faces.count == 0
      - healthy cuts always create/modify faces (faces.count > 0)
    So faces.count == 0 on a material-removing feature is the reliable
    signal; health warnings are reported as advisory context.

    Mirrors/patterns are deliberately NOT flagged on zero bodies/faces:
    a mirror whose products are consumed by a later JOIN (e.g. mirrored
    tenons joined into their rail) legitimately reports zero of both —
    verify replication by body COUNT in the build script instead.

    Returns {"passed", "zeroImpactFeatures": [...], "unhealthyFeatures":
    [...]} — zero-impact features fail validation and are named so the
    agent knows exactly which feature to fix.
    """
    F = adsk.fusion
    Hs = F.FeatureHealthStates
    CUT = F.FeatureOperations.CutFeatureOperation
    INT = F.FeatureOperations.IntersectFeatureOperation

    zero = []
    unhealthy = []
    tl = design.timeline
    for i in range(tl.count):
        item = tl.item(i)
        try:
            if item.isSuppressed:
                continue
            ent = item.entity
        except Exception:
            continue
        if ent is None:
            continue
        tname = ent.objectType.split("::")[-1]
        name = getattr(ent, "name", tname)

        try:
            health = ent.healthState
        except Exception:
            health = Hs.HealthyFeatureHealthState
        msg = ""
        if health != Hs.HealthyFeatureHealthState:
            try:
                msg = ent.errorOrWarningMessage
            except Exception:
                pass
            unhealthy.append({
                "feature": name, "type": tname,
                "state": ("error" if health == Hs.ErrorFeatureHealthState
                          else "warning"),
                "message": msg,
            })

        def _count(attr):
            try:
                return getattr(ent, attr).count
            except Exception:
                return None

        faces = _count("faces")
        op = getattr(ent, "operation", None)

        reason = None
        if tname == "ExtrudeFeature":
            # Require unhealthy too: a (rare) healthy faces==0 extrude is
            # a cut consuming an entire body — real impact, don't flag.
            if (op in (CUT, INT) and faces == 0
                    and health != Hs.HealthyFeatureHealthState):
                reason = ("cut/intersect extrude created no faces — the "
                          "profile does not intersect the participant "
                          "bodies; it removed NOTHING")
        elif tname == "CombineFeature":
            # No-op combines stay HEALTHY — faces==0 is the only signal.
            if op in (CUT, INT) and faces == 0:
                reason = ("cut/intersect combine modified no faces — the "
                          "tool body does not intersect the target; it "
                          "removed NOTHING")
        elif tname in ("FilletFeature", "ChamferFeature"):
            if faces == 0:
                reason = "fillet/chamfer modified no faces"

        if reason:
            zero.append({"feature": name, "type": tname, "reason": reason,
                         "healthMessage": msg})

    return {
        "passed": len(zero) == 0,
        "zeroImpactFeatures": zero,
        "unhealthyFeatures": unhealthy,
    }


# ── Handler ──────────────────────────────────────────────────────────

def _native_token(b):
    """Entity token of a body's native object (proxies resolve to their native)."""
    try:
        nb = getattr(b, "nativeObject", None) or b
        return nb.entityToken
    except Exception:
        try:
            return b.entityToken
        except Exception:
            return None


def _shape_signature(entry):
    """Reflection/translation-invariant shape signature for congruence grouping:
    (volume, sorted bbox dims, face count). Mirror twins and pattern repeats share
    a signature; a leg and a coincidentally-same-volume stretcher almost never do
    (different bbox dims and/or face count). Returns None if geometry unreadable."""
    b = entry["body"]
    mn, mx = entry["min"], entry["max"]
    dims = tuple(sorted(round(abs(mx[i] - mn[i]), 1) for i in range(3)))
    try:
        vol = round(b.volume, 2)
        nf = b.faces.count
    except Exception:
        return None
    if vol <= 0:
        return None
    return (vol, dims, nf)


def _replicated_tokens(design):
    """Native entity tokens of bodies PRODUCED by Mirror/Pattern features — i.e.
    bodies the agent already replicated. Used to suppress advisories: if any member
    of a congruence group is such an output, the group is being replicated and is
    never flagged (keeps false positives low)."""
    toks = set()
    try:
        tl = design.timeline
        for i in range(tl.count):
            try:
                feat = tl.item(i).entity
                ot = getattr(feat, "objectType", "") or ""
                if ("MirrorFeature" in ot or "RectangularPatternFeature" in ot
                        or "CircularPatternFeature" in ot):
                    fb = getattr(feat, "bodies", None)
                    if fb:
                        for k in range(fb.count):
                            t = _native_token(fb.item(k))
                            if t:
                                toks.add(t)
            except Exception:
                pass
    except Exception:
        pass
    return toks


def _check_replication(design, bodies, exclude_prefixes, min_group=2):
    """ADVISORY (never affects pass/fail): congruent structural bodies built
    independently instead of via Mirror/Pattern — the token-wasteful, non-parametric
    anti-pattern. Conservative by design (low false positives):
      - structural bodies only (exclude_prefixes covers DM_/joinery voids);
      - strong shape signature (volume + bbox dims + face count);
      - a group is flagged ONLY if NONE of its members is a Mirror/Pattern output
        (so a set that's already being replicated is never flagged);
      - opt-out via a `_norep` substring in a body name (intentional independent
        construction — e.g. per-corner joinery that can't be mirrored)."""
    repl = _replicated_tokens(design)
    groups = {}
    for e in bodies:
        nm = e["name"]
        if any(nm.startswith(p) for p in exclude_prefixes):
            continue
        if "_norep" in nm:
            continue
        sig = _shape_signature(e)
        if sig is None:
            continue
        groups.setdefault(sig, []).append(e)

    findings = []
    for sig, members in groups.items():
        if len(members) < min_group:
            continue
        if any(_native_token(m["body"]) in repl for m in members):
            continue  # already replicated — don't nag
        findings.append({
            "names": sorted(m["name"] for m in members),
            "count": len(members),
            # crude hint: a pair is usually a mirror, 3+ usually a pattern
            "suggest": ("Rectangular Pattern" if len(members) >= 3
                        else "Mirror"),
        })
    return {"advisory": True, "groups": findings}


def _sketch_detail_sig(sk):
    """(shape-signature, world-centroid) of a sketch's drawn profiles, or None.

    Signature = (rounded total profile area, total curve count) — a cheap
    congruence proxy. Centroid is in WORLD space so positions of sketches on
    different planes are comparable.
    """
    try:
        if sk.profiles.count == 0:
            return None
        area = 0.0; ncurves = 0; cx = cy = cz = 0.0; n = 0
        for pi in range(sk.profiles.count):
            pr = sk.profiles.item(pi)
            ap = pr.areaProperties()
            area += ap.area
            c = sk.sketchToModelSpace(ap.centroid)
            cx += c.x; cy += c.y; cz += c.z; n += 1
            for lp in range(pr.profileLoops.count):
                ncurves += pr.profileLoops.item(lp).profileCurves.count
        if n == 0 or area <= 0:
            return None
        return (round(area, 2), ncurves), (cx / n, cy / n, cz / n)
    except Exception:
        return None


def _check_detail_after_replicate(root_comp, tol=0.05):
    """ADVISORY (never affects pass/fail): the SAME detail sketched separately for
    each copy instead of detailed on the template before the Mirror/Pattern — e.g.
    tapering every leg after mirroring (8 taper sketches) instead of tapering one
    leg first (2). Catches what the body-level replication check can't: the copy
    BODIES are proper mirror outputs, but the per-copy detail FEATURES are redundant.

    Roll-free (reads persistent sketches, not the fragile timeline-feature APIs):
    group drawn sketches by congruence (area + curve count); within a group, flag
    members whose world centroids differ on EXACTLY ONE axis — i.e. mirror/pattern
    copies of each other. Congruent-but-not-1-axis-aligned sketches (e.g. the two
    perpendicular taper faces of ONE leg) are NOT flagged. Opt out with `_norep` in
    the sketch name.
    """
    import collections
    seen = set(); items = []
    comps = [root_comp]
    try:
        for i in range(root_comp.allOccurrences.count):
            comps.append(root_comp.allOccurrences.item(i).component)
    except Exception:
        pass
    for comp in comps:
        key = getattr(comp, "name", None)
        if key in seen:
            continue
        seen.add(key)
        for si in range(comp.sketches.count):
            sk = comp.sketches.item(si)
            if "_norep" in sk.name:
                continue
            r = _sketch_detail_sig(sk)
            if r is None:
                continue
            items.append((sk.name, r[0], r[1]))

    groups = collections.defaultdict(list)
    for nm, sig, ctr in items:
        groups[sig].append((nm, ctr))

    findings = []
    for sig, members in groups.items():
        if len(members) < 2:
            continue
        flagged = set()
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                ca, cb = members[a][1], members[b][1]
                axes_differ = sum(1 for k in range(3) if abs(ca[k] - cb[k]) > tol)
                if axes_differ == 1:           # mirror/translation copies
                    flagged.add(members[a][0]); flagged.add(members[b][0])
        if len(flagged) >= 2:
            findings.append({"sketches": sorted(flagged), "count": len(flagged)})
    return {"advisory": True, "groups": findings}


def handler(exclude_prefixes: list = None, min_contact_cm2: float = None) -> dict:
    """Run all structural validation checks on the current design."""

    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return {
                "content": [{"type": "text", "text": "No active design"}],
                "isError": True,
                "message": "No active design"
            }

        root = design.rootComponent
        prefixes = exclude_prefixes or ["DM_"]
        min_area = min_contact_cm2 if min_contact_cm2 is not None else DEFAULT_MIN_CONTACT_CM2

        bodies = _collect_bodies(root)
        connectivity = _check_connectivity(bodies, prefixes, min_area)
        interference = _check_interference(root, prefixes)
        impact = _check_feature_impact(design)

        passed = (connectivity["connected"]
                  and not connectivity["weakConnections"]
                  and interference["realCount"] == 0
                  and impact["passed"])

        # Run dependency tree validation if model.json exists
        deps_result = None
        try:
            from helpers import sp
            import io, contextlib
            ctx = sp.DesignContext()
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                deps_passed = sp.validate_deps(ctx)
            deps_output = buf.getvalue()
            if deps_passed is not None:
                deps_result = {
                    "passed": deps_passed,
                    "output": deps_output.strip(),
                }
                if not deps_passed:
                    passed = False
        except Exception as de:
            deps_result = {"passed": None, "error": str(de)}

        # Replication advisory — congruent bodies built independently instead of
        # via Mirror/Pattern. ADVISORY ONLY: never changes `passed`. It's an
        # optimization (parametric + token-cheaper), not a correctness bug, so it
        # must not force a redo of a working build.
        replication = None
        try:
            replication = _check_replication(design, bodies, prefixes)
        except Exception as re:
            replication = {"advisory": True, "error": str(re), "groups": []}

        # Detail-after-replicate advisory — the same detail sketched per copy
        # instead of detailed on the template before the Mirror/Pattern. ADVISORY
        # ONLY (the body-level replication check can't see it; this catches it via
        # repeated congruent sketches).
        detail_repl = None
        try:
            detail_repl = _check_detail_after_replicate(root)
        except Exception as dre:
            detail_repl = {"advisory": True, "error": str(dre), "groups": []}

        import json
        result = {
            "passed": passed,
            "connectivity": connectivity,
            "interference": interference,
            "featureImpact": impact,
        }
        if deps_result is not None:
            result["deps"] = deps_result
        if replication is not None and replication.get("groups"):
            result["replication"] = replication
        if detail_repl is not None and detail_repl.get("groups"):
            result["detail_replication"] = detail_repl

        parts = []
        if connectivity["connected"] and not connectivity["weakConnections"]:
            parts.append(f"connectivity OK ({connectivity['structuralBodyCount']} bodies, 1 cluster)")
        elif connectivity["connected"]:
            parts.append(f"CONNECTIVITY WARN ({len(connectivity['weakConnections'])} weak connection(s))")
        else:
            parts.append(f"CONNECTIVITY FAIL ({connectivity['clusterCount']} clusters)")

        if interference["realCount"] == 0:
            parts.append("interference OK (0 real)")
        else:
            parts.append(f"INTERFERENCE FAIL ({interference['realCount']} real)")

        if impact["zeroImpactFeatures"]:
            names = ", ".join(z["feature"]
                              for z in impact["zeroImpactFeatures"])
            parts.append(f"FEATURE IMPACT FAIL — zero-impact feature(s): "
                         f"{names}")
        elif impact["unhealthyFeatures"]:
            parts.append(f"feature impact OK "
                         f"({len(impact['unhealthyFeatures'])} health "
                         f"warning(s) — see featureImpact.unhealthyFeatures)")
        else:
            parts.append("feature impact OK")

        if deps_result is not None:
            if deps_result.get("passed"):
                parts.append("deps OK")
            elif deps_result.get("passed") is False:
                parts.append("DEPS FAIL")

        if replication is not None and replication.get("groups"):
            g = replication["groups"]
            ex = "; ".join(
                f"{'/'.join(grp['names'])} → {grp['suggest']}" for grp in g[:3])
            parts.append(
                f"replication ADVISORY ({len(g)} group(s) built independently — "
                f"{ex}) [does not affect pass/fail]")

        if detail_repl is not None and detail_repl.get("groups"):
            dg = detail_repl["groups"]
            dex = "; ".join("/".join(grp["sketches"]) for grp in dg[:3])
            parts.append(
                f"detail-after-replicate ADVISORY ({len(dg)} group(s) — same detail "
                f"sketched per copy; detail the template before mirroring: {dex}) "
                f"[does not affect pass/fail]")

        status = "PASSED" if passed else "FAILED"
        msg = f"{status}: {', '.join(parts)}"

        return {
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
            "isError": False,
            "message": msg
        }

    except Exception as e:
        app.log(f"validate_design error: {e}\n{traceback.format_exc()}")
        return {
            "content": [{"type": "text", "text": f"Error: {e}\n{traceback.format_exc()}"}],
            "isError": True,
            "message": "validate_design failed"
        }


TOOL_DESCRIPTION = \
"""Run all validation checks on the current design.

Combines all structural checks in a single call:
1. **Connectivity** — all structural bodies must form 1 connected cluster
   with sufficient face-to-face contact area. Edge-only or point-only
   contacts don't count. Connections below min_contact_cm2 are flagged weak.
2. **Interference** — no unintended body overlaps (excludes void-on-void
   pairs like joinery ghost bodies)
3. **Feature impact** — every CUT/INTERSECT extrude or combine must
   actually change geometry. A cut whose profile/tool misses its target
   computes "successfully" but removes nothing (classic cause: a sketch
   drawn with raw coordinates on a plane whose sketch-Y maps to model -Z).
   Zero-impact features FAIL validation and are returned by name in
   featureImpact.zeroImpactFeatures so the agent knows which feature to
   fix. No-op fillets/chamfers are flagged too; features in warning/error
   health are listed as advisory context. Mirrors/patterns are exempt
   (a later JOIN may legitimately consume their products — verify those
   by body count).
4. **Dependency tree** — if model.json exists next to the script, validates:
   single origin root, sketch origin enforcement (non-root sketches must
   not dimension from sk.originPoint), sketch traceability (every non-root
   sketch must project real reference geometry, use no Fix/Ground constraint,
   and be fully constrained relative to that reference — Fusion's solver is
   the judge; only fit-point spline interiors may stay free), bodies in
   components.
   Completeness check is advisory (printed but doesn't affect pass/fail).
5. **Replication advisory** (ADVISORY — never affects pass/fail): congruent
   structural bodies built independently instead of via Mirror/Pattern (the
   token-wasteful, non-parametric anti-pattern). Suppressed when the bodies are
   already a Mirror/Pattern output, when a body name contains `_norep`, or for
   excluded prefixes. Surfaced as a note so a working build is never forced into
   a redo; the recommended response is to refactor the named group to one
   template + Mirror/Pattern (a sub-agent can do this so the main build's context
   stays lean).
6. **Detail-after-replicate advisory** (ADVISORY — never affects pass/fail): the
   SAME detail sketched separately for each copy (e.g. tapering every leg AFTER
   mirroring) instead of detailing the template BEFORE the Mirror/Pattern. The
   copy bodies are proper mirror outputs (so check 5 stays quiet), but the
   per-copy detail SKETCHES are redundant. Detected roll-free via congruent
   sketches at mirror/pattern-symmetric positions; opt out with `_norep` in the
   sketch name.

Returns a single pass/fail result. Fails if disconnected, has weak
connections, has interference, or has zero-impact features (NOT for the
two advisories). Run after EVERY phase."""

tool = Tool.create_simple(
    name="validate_design",
    description=TOOL_DESCRIPTION
).add_input_property(
    "exclude_prefixes",
    {
        "type": "array",
        "description": "Body name prefixes to exclude (default: [\"DM_\"]). "
                       "Joinery void bodies that aren't structural.",
        "items": {"type": "string"}
    }
).add_input_property(
    "min_contact_cm2",
    {
        "type": "number",
        "description": "Minimum face contact area in cm² for a connection to be "
                       "structurally sound (default: 1.0). Connections below this are "
                       "flagged as weak and cause the check to fail.",
    }
)

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
