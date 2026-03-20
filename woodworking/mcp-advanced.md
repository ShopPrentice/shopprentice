# MCP Advanced — Modifying Existing Designs

Techniques for modifying models that already have a timeline, without rebuilding from scratch.

## When to Read

- User asks to change, fix, or add features to an existing model
- User selects bodies in Fusion and asks for modifications
- You need to fix a bug in a previously-built model (e.g., swapped dimensions)
- Adding joinery or details to a model built by another agent or session

## Tools for Incremental Work

| Tool | Use Case |
|------|----------|
| `get_selection` | Read what the user selected — body names, volumes, bounding boxes |
| `capture_design` | Get current parameters, body names, timeline (read-only, safe on any doc) |
| `modify_parameters` | Change parameter values without touching the timeline — fastest fix for dimension issues |
| `execute_script` (no `clean`) | Append new features to the end of the timeline |
| `execute_script` (with feature deletion in script) | Delete specific features and rebuild them |
| `suppress_features` | Toggle features on/off for diagnostics |
| `check_interference` | Validate after modifications |

## Approach 1: Parameter Modification Only

**When to use:** The timeline structure is correct but dimensions are wrong (e.g., swapped width/thickness, wrong height).

```python
# Via modify_parameters tool:
{"parameters": [
    {"name": "str_w", "expression": "0.875 in"},
    {"name": "str_t", "expression": "1.25 in"}
]}
```

All downstream features that reference these parameters recompute automatically. No timeline changes needed.

**Limitation:** Can only change values of existing parameters. Cannot add new parameters, change which parameter an expression references, or fix structural issues (wrong sketch axis, wrong extrude direction).

## Approach 2: Additive Features

**When to use:** Adding new features to an existing model (e.g., adding dominos to a table that has legs and a top but no joinery).

1. `get_selection` — identify the bodies the user wants to modify
2. `capture_design` — get current parameter names and body geometry
3. Write a script that:
   - Uses `find_body(name)` to reference existing bodies
   - Adds new parameters (check for name conflicts with existing ones)
   - Creates new sketches, extrudes, CUTs, etc.
4. `execute_script` (without `clean=true`) — appends to the timeline
5. Ctrl+Z reverts the entire addition

**Key rules:**
- New parameter names must not collide with existing ones
- Reference existing bodies by name via `find_body()`
- Reference existing construction planes via `root.constructionPlanes.itemByName()`
- The script runs AFTER the existing timeline — all existing features are computed

## Approach 3: Delete and Rebuild Features

**When to use:** Existing features have structural problems that can't be fixed by parameter changes alone (e.g., wrong sketch-to-extrude dimension mapping, wrong feature order, missing splay moves).

### Deletion Order Matters

Features must be deleted in **reverse dependency order** — delete consumers before producers. If feature B references a body created by feature A, deleting A first causes B to lose its reference and the deletion fails.

**Correct order for stretcher rebuild:**
```
1. Mortise CUTs      (reference mirrored bodies → delete first)
2. Mirrors           (create mirrored bodies)
3. Angled tenons     (JOIN/sweep/sketch on stretcher body)
4. Splay Moves       (transform stretcher body)
5. Base extrude      (creates stretcher body)
6. Sketch + ConstrPlane  (referenced by extrude)
```

### Delete by Name, Not Index

Timeline indices shift as features are deleted. Always find features by name:

```python
def delete_feature_by_name(timeline, name):
    for i in range(timeline.count):
        item = timeline.item(i)
        if item.entity and hasattr(item.entity, 'name') and item.entity.name == name:
            item.entity.deleteMe()
            return True
    return False

# Delete in dependency order
for feat_name in [
    # Consumers first
    "BStr_Mort_NR", "BStr_Mort_FR",
    # Then mirrors
    "FStr_Mir",
    # Then angled tenons (reverse timeline order)
    "BStr_TnR_Join", "BStr_TnR_Sweep", "BStr_TnR_PathSk", "BStr_TnR_Sk", "BStr_TnR_LegCut",
    "BStr_TnL_Join", "BStr_TnL_Sweep", "BStr_TnL_PathSk", "BStr_TnL_Sk", "BStr_TnL_LegCut",
    # Then base features
    "BStr_Splay", "BStr", "BStr_Sk", "BStr_Pl",
]:
    delete_feature_by_name(timeline, feat_name)
```

### Adding New Parameters After Deletion

After deleting features, their parameter references are gone, but user parameters may still exist. Check before adding:

```python
if not params.itemByName("front_str_h"):
    params.add("front_str_h", VI("7 in"), "in", "Front stretcher height")
```

Old parameters that are no longer referenced can be deleted:
```python
p = params.itemByName("str_h")
if p:
    p.deleteMe()
```

### Surviving Features

Features that don't depend on the deleted features survive unchanged. In the bar table rebuild:
- Top, legs, dominos (before stretchers) — unaffected
- Chamfers on leg bottoms (after stretchers) — survived because they reference leg bodies, not stretcher bodies

**Caution:** If a surviving feature references a body modified by a deleted feature (e.g., a chamfer on a leg that had mortise CUTs from a stretcher), the feature recomputes with the unmodified body geometry. This may change edge counts or positions, potentially breaking the chamfer. Always verify with `capture_design` after deletion.

## Workflow Summary

```
1. get_selection → identify what the user wants to change
2. capture_design → understand current state (params, bodies, timeline)
3. Decide approach:
   a. Parameter values wrong → modify_parameters (simplest)
   b. Need to add features → additive execute_script
   c. Need to fix/replace features → delete + rebuild in execute_script
4. Execute → validate with capture_design + check_interference
5. User can Ctrl+Z to revert
```

## Common Pitfalls

| Error | Cause | Fix |
|-------|-------|-----|
| `deleteMe()` fails with "Tool Body Error / Reference Failures" | Deleting a feature that is referenced by a downstream feature still in the timeline | Delete consumers before producers — mortise CUTs before mirrors, mirrors before base extrudes |
| "param name is not valid" after deletion | Deleted a feature but its user parameter still exists with a broken expression | Delete the orphaned parameter explicitly, or reuse it |
| Chamfer fails after stretcher rebuild | Mortise CUT deletion changed leg geometry, altering edge count | Re-add chamfers after the rebuild, or verify edges still exist |
| New parameter name collides | Script tries to add a parameter that already exists | Check `params.itemByName()` before adding |
| Timeline index wrong after deletions | Used index-based deletion — indices shift as features are removed | Always find features by name, never by index |
