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

## MCP Live Execution

When an MCP connection to Fusion 360 is available (via the ShopPrentice add-in), you MUST automatically execute the script after generating it. Do not wait for the user to ask — the full generate-execute-verify loop is the default workflow.

### Available MCP Tools

| Tool | Purpose |
|------|---------|
| `capture_design` | Full design introspection: parameters, component tree with body geometry and sketch dimension details, timeline features (including chamfers and fillets). |
| `get_timeline_state` | Roll timeline to any index, capture body geometry at that point, restore position. |
| `execute_script` | Run a complete Python script in Fusion 360. Returns `isError` flag + full stack trace on failure. Failed scripts are rolled back automatically. Set `sandbox=true` to run in a throwaway document. Set `clean=true` to delete all existing features before running — enables clean rebuild of an existing model. The entire clean+execute is one transaction: Ctrl+Z reverts to the previous state. |
| `get_screenshot` | Quick viewport capture for build validation (1024x1024, as-is with artifacts). Use during builds to verify geometry. |
| `get_product_shots` | Final presentation screenshots. Hides construction artifacts, FOV-aware framing, multiple views in one call (default: iso-top-right + front + right at 2048x2048). Supports `style` (shaded/transparent) and `bodies` (detail framing). Use after `apply_appearance`. |
| `get_selection` | Read the user's current UI selection. Returns structured info per entity type (body, face, edge, occurrence) AND full feature details when a feature is selected (Sketch with curves/dimensions/constraints, Extrude with operation/distance/sketch, Combine with target/tool bodies, Mirror, Pattern, Move, Chamfer, Fillet). Use when the user says "what is this?" or "make this thicker". |
| `set_selection` | Highlight entities in the UI by name or token. Use after `capture_design` identifies a problem body — select it so the user sees which one. |
| `modify_parameters` | Change parameter expressions with incremental recompute. Much faster than re-running the script. Use for iterative tuning ("make shelves deeper"). |
| `validate_design` | **Single-call structural validation.** Runs connectivity (1 cluster?) + interference (0 real overlaps?) and returns pass/fail. Call this after the final build cycle — replaces separate `check_connectivity` + `check_interference` calls. |
| `check_interference` | Detect body collisions. Diagnostic — use standalone when investigating a specific interference. Normally called via `validate_design`. |
| `check_connectivity` | Verify all structural bodies form 1 connected cluster. Diagnostic — use standalone when investigating disconnected parts. Normally called via `validate_design`. |
| `suppress_features` | Toggle timeline features on/off. Diagnostic tool — suppress a suspicious feature, check if it fixes the problem, unsuppress to restore. |
| `get_changes` | Snapshot & diff. First call captures a baseline; subsequent calls return what changed — parameter expression changes, sketch dimension changes, body additions/removals, feature count delta. Use between iterations or when the user says "I changed something". |
| `sync_script` | Auto-sync UI changes back to a script. Pass the original script source (or omit to use the tracked script from the last execute_script run) — auto-patches user parameter expression changes, reports feature-level param edits, feature additions, and feature removals with script context for the agent to apply. |
| `get_document_status` | Check if the active document was built by a known script. Returns `tracked` (true/false), `pendingChanges` count, and `canUpdate` flag. Call before attempting incremental updates. |
| `apply_appearance` | Apply wood appearance with grain-aligned texture. Auto-detects fiber direction from bounding box longest axis, with dovetail-aware constraints (dovetailed edges = end grain → grain excluded from that axis). Call once after final validation, before screenshots. |

### Execution + Validation Loop

After generating each component's code, run this loop:

1. **Execute** — call `execute_script` to run the full script in Fusion 360. The script rebuilds from scratch each time (document reuse pattern).
2. **On error** — the `content` field contains the full Python stack trace. Analyze, fix only the current component's code, and re-execute (see Error Retry Rules below).
3. **On success — validate with `capture_design` + `validate_design`:**
   - Call `capture_design` to verify body count, names, bounding boxes.
   - **ALWAYS call `validate_design`** — checks connectivity (1 cluster) and interference (0 overlaps). This is mandatory after every successful execution, not just the final cycle. Skipping it risks undetected body collisions (e.g., a divider overlapping a rail).
   - Report: `"12 bodies, validate_design PASSED."`
4. **If validation fails** — use `get_timeline_state` to bisect the timeline and pinpoint the problem feature (see Diagnosing with Timeline Rollback below). Fix and re-execute.
5. **Auto-proceed** to the next component if validation passes.
7. **Appearance + product shots at the end** — after structural validation passes, call `apply_appearance` then `get_product_shots`. Product shots auto-hide construction artifacts, frame the model properly, and capture multiple views in one call. See `docs/appearance.md` for species and grain details.

### Diagnosing with Timeline Rollback

When `capture_design` reveals unexpected state (wrong body count, bad positions), use `get_timeline_state` to narrow down which feature went wrong:

1. Call `get_timeline_state` at the midpoint of the timeline.
2. Check body count — is it correct for that point in the build?
3. Binary search forward or backward to find the exact feature where the model diverges from the plan.
4. Correlate with the `timeline` array from `capture_design` to identify the feature by name and type.

This is like `git bisect` for the modeling timeline — fast, cheap, and precise.

### Error Retry Rules

- **Max 3 attempts per distinct error.** An error is "the same" if its core message is unchanged (ignore line numbers and memory addresses when comparing).
- **Different errors reset the counter.** If a fix resolves one error but surfaces a new one, the new error gets its own 3-attempt budget.
- **No infinite loops.** If you hit 3 distinct errors in a row (each failing 3 times), stop and present a summary of all errors to the user.
- After each failed attempt, explain what error occurred and what you changed before retrying.
- Failed scripts are automatically rolled back (transaction abort), so each retry starts from a clean state.

### Modifying an Existing Design

> **Full reference:** `docs/mcp-advanced.md` — provenance checking, selection-driven interaction, change detection, script sync, sandbox mode.

Quick reference:
- **Dimension changes:** `get_document_status` → `modify_parameters` → `capture_design` to validate → update `.py` file.
- **Structural changes:** Read tracked script → edit → `execute_script(clean=true)`.
- **UI tweaks:** `sync_script` auto-patches parameter expression changes, reports feature-level edits for agent.
- **Sandbox:** `execute_script(sandbox=true)` runs in throwaway document for safe validation.

### Example Flow

```
Response 1 (plan): High-level plan — all components, build order, joinery strategy

Response 2 (plan): Case component — Front, Back, Left, Right boards
Response 3 (build): write box.py (preamble + params + helpers + Case component)
  → execute → capture_design → validate 4 bodies, positions OK → auto-proceed

Response 4 (plan): Bottom component — panel + edge rabbets
Response 5 (build): append Bottom code to box.py
  → execute → capture_design → validate Bottom body + 4 Case bodies → auto-proceed

Response 6 (plan): Lid component — panel + edge rabbets
Response 7 (build): append Lid code to box.py
  → execute → capture_design → validate 6 bodies total → auto-proceed

Response 8 (plan): Cross-component CUTs — panel grooves, dovetails
Response 9 (build): append root-level CUTs to box.py
  → execute → capture_design → validate mortises cut, body count correct
  → body count wrong? → get_timeline_state to bisect → fix → retry
  → validation OK → auto-proceed

Response 10 (plan): Details — lid chamfer, edge fillets
Response 11 (build): append details to box.py
  → execute → capture_design → validate
  → validate_design → apply_appearance → get_product_shots → present to user
```

### Sandbox Mode

Use `execute_script` with `sandbox=true` to run a script in a throwaway document. The script executes in a fresh temporary document; on completion, a design snapshot (parameters, bodies, dimensions, feature count) is returned and the temp document is discarded. The user's active document is never modified.

**When to use sandbox:**
- Validating a script before committing to the real design (especially complex joinery phases)
- Testing helper imports or sketch logic without risk
- Exploring "what if" variations without polluting the undo history

**Behavior:**
- ActionLog events are suppressed during the sandbox run — the user's `get_changes` baseline is unaffected
- The sandbox document has no user parameters from the real design — scripts that reference existing parameters will fail unless they create their own
- Returns `{sandbox: true, snapshot: {...}}` on success
- On error, the temp document is closed and the original document is restored automatically

**Not a substitute for the real execution loop.** Sandbox validates that a script runs without errors and produces expected geometry, but the real design's parameter expressions and timeline context may differ. Always follow sandbox validation with a real `execute_script` run.

### Multi-Agent / Parallel Sessions

Multiple agents can drive Fusion at the same time (e.g. a fan-out where each agent builds or fixes a different piece in parallel). The **Session Manager** makes this safe and transparent:

- **One document per agent, assigned automatically.** The Session Manager finds and maintains a dedicated Fusion document for each agent, keyed by the session ID carried on every request. Your `execute_script` / `capture_design` / `validate_design` / `get_document_status` calls operate on YOUR assigned document by default. You normally do **not** choose, create, activate, or `claim_document` a document (see Re-binding for the exceptions), and you do not read or depend on "which document is visually active" — that is the Session Manager's job, not yours.
- **No cross-agent collisions.** `execute_script(clean=True)` rebuilds only *your* document. Another agent rebuilding, validating, or wiping its own document never affects yours, so parallel agents don't step on each other and don't need to coordinate or take turns.
- **Execution is serialized, not parallel.** Fusion is single-threaded, so the Session Manager queues requests across all agents and spaces them out to keep Fusion responsive (and avoid crashes from bursts). Your calls may therefore wait briefly behind other agents' calls — budget for some extra latency, but correctness is unaffected. Keep individual scripts reasonably sized so one agent's long build doesn't starve the queue.
- **You still run the normal loop.** Author the script, `execute_script`, fix-and-retry on error, then `capture_design` + `validate_design` — exactly as a solo agent would. The only difference is that the document you're acting on was provisioned for you.
- **Re-binding.** A session can lose its document binding — after an add-in restart, or after an operation that detaches it (e.g. closing the active document via `manage_documents`). The next call then returns a "session restored" message listing available documents with their `doc_key`s; call `claim_document` (preferably by `doc_key`) to re-adopt yours. If the document you target is already bound to another live session, `claim_document` reports a **conflict** with two options — pass `resolution='transfer'` to take it, or `keep_existing` to leave it and bind elsewhere. In normal operation you never call `claim_document`.
- **After a restore/transfer, `clean=True` is gated.** A restored or transferred session is flagged `needsSync` (visible via `get_document_status`), and `execute_script(clean=True)` is **rejected** even when `pendingChanges=0`. Call `sync_script` to reconcile and retry — or pass `force_clean=True` ONLY when `pendingChanges=0` (nothing to lose). Never `force_clean` past real pending UI work.

### Important

- Always generate complete, standalone parametric scripts. MCP is the delivery mechanism — the script must also work when pasted into Fusion 360's script editor.
- Scripts using `from helpers import sp` need the addin's `helpers/` directory on the Python path (automatic when run via `execute_script`). For standalone use outside MCP, copy `addin/helpers/` alongside the script.
- Never generate partial snippets that only work via MCP.
- Scripts must NOT catch exceptions — let them propagate so Fusion 360 aborts the transaction and returns the full error to the agent.

### Screenshots

After the final phase, call `get_product_shots` for presentation images. It handles everything automatically — artifact cleanup, FOV-aware framing, multiple views, visual style. See [docs/screenshots.md](docs/screenshots.md) for camera direction details.

- **Validation during builds**: `get_screenshot` (quick, 1024x1024, as-is)
- **Final presentation**: `get_product_shots` (2048x2048, cleaned up, multiple views)
- **Transparent views**: `get_product_shots(style="transparent")`
- **Detail shots**: `get_product_shots(bodies=["Post_FL", "Rail_FrontBot"], fill=0.90)`

### MCP Timeout

The ShopPrentice add-in's main-thread execution timeout is set in:
`addin/server/mcp_server.py` → `_execute_on_main_thread` → `timeout = 300`

Default is 300s (5 min). If scripts still time out, increase this value and restart the add-in.

See `mcp/README.md` for setup instructions.
