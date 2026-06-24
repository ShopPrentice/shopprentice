"""Declarative joint registry + per-joint-type strength checks (issue 106).

WHY
  The build-time strength gate only runs where a template bakes it in (today: the
  ``mortise_tenon`` template). A hand-built or novel-geometry joint that skips the
  template also skips the check, and ``validate_design`` can't reliably auto-discover
  "which bodies form a joint and which way the load runs" from geometry alone.

  So we DECLARE joints, the same discipline already owed for dependencies. model.json
  grows a top-level ``joints`` array; ``validate_deps`` runs the right PER-TYPE check on
  each declared joint. Templates AUTO-DECLARE the joint they build (``declare_joint``),
  so the convenient path stays zero-effort; the registry is the safety net for the rest.

REGISTRY (model.json)
  "joints": [
    {"type":"mortise_tenon","tenon":"Rail_F","mortise":"Leg_FL","axis":"y",
     "species":"white_oak","width":"2 in","thickness":"0.75 in","depth":"1.5 in"},
    {"type":"pegged_tenon","tenon":"Stretcher","mortise":"Leg_FL","axis":"y",
     "species":"white_oak","width":"1.5 in","thickness":"0.5 in","depth":"1 in",
     "pins":1,"pin_dia":"0.375 in","pin_end_distance":"1.5 in"}
  ]
  - ``tenon`` / ``mortise`` are the OWNING body names (the rail and the leg) — they
    persist after the tenon is fused, so find_body resolves them and the completeness
    check can match contacts to declared joints.
  - ``axis`` is the insertion direction 'x'/'y'/'z'. LENGTH fields are EXPRESSION
    strings ("0.375 in", "rail_w") evaluated via ctx.ev. The tenon is gone post-build,
    so the registry check reads dims from the DECLARATION, not by re-measuring.

PER-TYPE CHECKS (dispatched on ``type``)
  mortise_tenon : sizing flags (joint_strength.mortise_tenon_flags) + mortise-grain sanity
  pegged_tenon  : the above + the dedicated pegged check (joint_strength.pegged_flags:
  / drawbore      relish tear-out >= 4xD + European-Yield-Model peg capacity)
  wedged_tenon  : plain M&T for now; the interlock mechanism lands with issue #105

This module keeps adsk OUT of the import path (all Fusion/sp imports are lazy, inside
functions) so deps.py can import it without breaking the offline test harness.
"""

# type name -> {required decl fields, list of per-type checks to run}
JOINT_TYPES = {
    "mortise_tenon": {"required": ["tenon", "mortise"], "checks": ["mt"]},
    "pegged_tenon":  {"required": ["tenon", "mortise"], "checks": ["mt", "peg"]},
    "drawbore":      {"required": ["tenon", "mortise"], "checks": ["mt", "peg"]},
    "wedged_tenon":  {"required": ["tenon", "mortise"], "checks": ["mt", "wedge_todo"]},
}

_IN = 2.54   # cm per inch


def key_for(decl):
    """Stable dedup/identity key for a joint declaration: (type, sorted body pair).

    Body order doesn't matter, so a joint is the same whether declared tenon-first or
    mortise-first. Used to update-in-place rather than duplicate on repeated builds."""
    bodies = tuple(sorted([str(decl.get("tenon", "")), str(decl.get("mortise", ""))]))
    return (decl.get("type"), bodies)


def joint_covers(decl, name_a, name_b):
    """True if a joint declaration accounts for the contact between two named bodies."""
    pair = {str(decl.get("tenon", "")), str(decl.get("mortise", ""))}
    return name_a in pair and name_b in pair


def declare_joint(decl, metadata_path=None):
    """Append a joint declaration to model.json's ``joints`` array (auto-declare).

    Idempotent: an existing entry with the same ``key_for`` is UPDATED in place rather
    than duplicated, so repeated ``clean=True`` rebuilds don't pile up. Preserves
    ``deps`` and every other key. NO-OP (returns False) when no model.json is resolvable
    or it doesn't exist yet — the registry is agent-authored (mandatory per the skill);
    templates augment it, they don't bootstrap it. So this never creates surprise files
    in tests / sandbox runs.

    Returns True if model.json was written, else False.
    """
    import json
    from helpers.sp.deps import resolve_model_json

    path, found = resolve_model_json(metadata_path)
    if not path or not found:
        return False
    try:
        with open(path, "r") as f:
            meta = json.load(f)
    except Exception:
        return False
    if not isinstance(meta, dict):
        return False

    joints = meta.setdefault("joints", [])
    k = key_for(decl)
    for i, existing in enumerate(joints):
        if key_for(existing) == k:
            joints[i] = decl
            break
    else:
        joints.append(decl)

    try:
        with open(path, "w") as f:
            json.dump(meta, f, indent=2)
            f.write("\n")
    except Exception:
        return False
    return True


def _ev_in(ctx, expr):
    """Evaluate a length expression to INCHES (ctx.ev returns cm). None passes through."""
    if expr is None:
        return None
    return ctx.ev(expr) / _IN


def _mt_dims_in(decl, ctx):
    """(width, thickness, depth) in inches from the decl, or None if any is absent."""
    vals = []
    for f in ("width", "thickness", "depth"):
        v = decl.get(f)
        if v is None:
            return None
        vals.append(_ev_in(ctx, v))
    return tuple(vals)


def _grain_sanity(mortise_body, axis, result):
    """Best-effort mortise-grain check (the tenon is fused post-build, so we can only
    inspect the persistent mortise body). Flags an end-grain mortise — where the
    insertion axis runs along the mortise fiber, leaving weak short-grain glue walls.
    Silently skips if grain can't be read (e.g. offline stub context)."""
    if not axis:
        return
    try:
        from helpers.sp.mating import tenon_wide_direction
        if tenon_wide_direction(mortise_body, axis) is None:
            result["flags"].append(
                "mortise grain runs ALONG the insertion axis (end-grain mortise) -> "
                "weak short-grain cheeks; reorient the joint or add mechanical reinforcement")
    except Exception:
        pass


def validate_joint(decl, ctx):
    """Validate one declared joint by dispatching on ``decl['type']``. Never raises.

    Resolves the tenon/mortise bodies (missing -> hard error), evaluates the declared
    dimensions, and runs the per-type checks. DECLARATION problems (unknown type,
    missing required field, unresolved body, bad expression) are HARD errors; strength
    problems (thin slice, relish tear-out, end-grain mortise, ...) are advisory flags.

    Returns {type, tenon, mortise, ok, flags, errors, notes}.
    """
    typ = decl.get("type")
    result = {"type": typ, "tenon": decl.get("tenon"), "mortise": decl.get("mortise"),
              "ok": True, "flags": [], "errors": [], "notes": []}

    spec = JOINT_TYPES.get(typ)
    if spec is None:
        result["errors"].append(
            "unknown joint type %r (known: %s)" % (typ, ", ".join(sorted(JOINT_TYPES))))
        result["ok"] = False
        return result

    for f in spec["required"]:
        if not decl.get(f):
            result["errors"].append("missing required field %r" % f)
    if result["errors"]:
        result["ok"] = False
        return result

    tenon_body = ctx.find_body(decl["tenon"]) if ctx is not None else None
    mortise_body = ctx.find_body(decl["mortise"]) if ctx is not None else None
    if tenon_body is None:
        result["errors"].append("tenon body %r not found in design" % decl["tenon"])
    if mortise_body is None:
        result["errors"].append("mortise body %r not found in design" % decl["mortise"])
    if result["errors"]:
        result["ok"] = False
        return result

    species = decl.get("species", "hardwood")
    checks = spec["checks"]

    if "mt" in checks:
        try:
            dims = _mt_dims_in(decl, ctx)
        except Exception as e:
            result["errors"].append("could not evaluate tenon dimensions: %s" % e)
            dims = None
        if not result["errors"]:
            if dims:
                from helpers.sp.joint_strength import mortise_tenon_flags
                try:
                    r = mortise_tenon_flags(
                        dims[0], dims[1], dims[2], species=species,
                        through=bool(decl.get("through", False)),
                        sized=bool(decl.get("sized", False)),
                        expected=decl.get("expected"))
                    result["flags"].extend(r["flags"])
                except Exception as e:
                    result["errors"].append("M&T estimate failed: %s" % e)
            else:
                result["notes"].append(
                    "no tenon dimensions declared (width/thickness/depth) -> strength "
                    "sizing skipped; add them for a real check")
            _grain_sanity(mortise_body, decl.get("axis"), result)

    if "peg" in checks and not result["errors"]:
        from helpers.sp.joint_strength import pegged_flags
        try:
            pins = int(decl.get("pins", 1) or 1)
            pin_dia = _ev_in(ctx, decl.get("pin_dia"))
            end_d = _ev_in(ctx, decl.get("pin_end_distance"))
        except Exception as e:
            result["errors"].append("could not evaluate peg parameters: %s" % e)
            pin_dia = end_d = None
            pins = 0
        if not result["errors"]:
            if not pin_dia:
                result["notes"].append(
                    "pegged joint declared without 'pin_dia' -> relish / peg-capacity "
                    "check skipped")
            else:
                dims = None
                try:
                    dims = _mt_dims_in(decl, ctx)
                except Exception:
                    dims = None
                tw, tt, td = dims if dims else (None, None, None)
                try:
                    r = pegged_flags(pins, pin_dia, end_d, species=species,
                                     peg_species=decl.get("peg_species"),
                                     tenon_width=tw, tenon_thickness=tt, tenon_depth=td)
                    result["flags"].extend(r["flags"])
                except Exception as e:
                    result["errors"].append("pegged estimate failed: %s" % e)

    if "wedge_todo" in checks:
        result["notes"].append(
            "wedged-tenon interlock check pending (issue #105) — validated as a plain "
            "M&T for now")

    result["ok"] = not result["errors"]
    return result


def validate_joints(ctx, joints):
    """Run the per-type check on every declared joint and print a report section.

    Declaration ERRORS fail the gate (so a typo'd body name or unknown type is caught
    like a bad dep); strength FLAGS are advisory WARNINGs. Returns
    {ok, n_warn, n_err, results}.
    """
    results = []
    n_warn = n_err = 0
    print("--- Joint strength check (%d declared) ---" % len(joints))
    for decl in joints:
        r = validate_joint(decl, ctx)
        results.append(r)
        label = "%s -> %s" % (r.get("tenon"), r.get("mortise"))
        typ = r.get("type")
        for e in r["errors"]:
            n_err += 1
            print("  FAIL  %s [%s]: %s" % (label, typ, e))
        for fl in r["flags"]:
            n_warn += 1
            print("  WARN  %s [%s]: %s" % (label, typ, fl))
        for nt in r["notes"]:
            print("  NOTE  %s [%s]: %s" % (label, typ, nt))
        if not r["errors"] and not r["flags"]:
            print("   OK   %s [%s]" % (label, typ))
    ok = n_err == 0
    print("--- Joint check: %s (%d warning(s), %d error(s)) ---"
          % ("PASS" if ok else "FAIL", n_warn, n_err))
    return {"ok": ok, "n_warn": n_warn, "n_err": n_err, "results": results}
