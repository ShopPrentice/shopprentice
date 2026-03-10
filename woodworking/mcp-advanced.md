# MCP Advanced Workflow

Read this file when modifying an existing design, syncing UI changes, or using selection-driven interaction. The basic MCP execution loop is in the core skill.

## Modifying an Existing Design

When the user asks to change an existing design (e.g., "make the shelves wider"):

**Step 1: Check provenance** — call `get_document_status` first:

- `tracked=false` → The agent can't safely modify this design incrementally. Ask the user: "I can't safely modify this design incrementally. Would you like me to create a new script for it?"
- `tracked=true`, `needsSync=true` → Provenance was restored from disk. Call `sync_script` to reconcile before proceeding.
- `tracked=true`, `pendingChanges > 0` → The user made UI changes. Call `sync_script` to reconcile, then proceed.
- `tracked=true`, `pendingChanges == 0` → Proceed directly.

**Step 2: Apply the change:**

**For dimension changes** (most common) — use `modify_parameters` for fast incremental tuning:

1. Call `capture_design` to understand the current model state.
2. Call `modify_parameters` to change the relevant parameter expression(s).
3. Fusion does **incremental recomputation** — only affected features recompute.
4. Validate with `capture_design`.
5. **Good** → update the `.py` source file to match the new expression.
6. **Bad** → revert via `modify_parameters` with the old expression.

**For structural changes** (add a component, change joinery type) — read the tracked script, make targeted changes, and re-run with `execute_script(clean=true)`. This deletes the existing model and rebuilds from the modified script. The entire operation is one transaction — **the user can Ctrl+Z to revert to the previous state**.

## Selection-Driven Interaction

When the user points at something in Fusion 360 and asks about it:

1. Call `get_selection` to read what they've selected.
2. Use the structured entity info (type, name, dimensions) to understand their intent.
3. If they want a change, use `modify_parameters` for dimension tweaks or `execute_script` for structural changes.
4. Use `set_selection` to highlight the result or related entities.

## Change Detection

When iterating on a design with the user making manual changes in Fusion 360:

1. Call `get_changes` once at the start (or after a script run) to capture a baseline.
2. When the user says "I changed something" or between iterations, call `get_changes` again.
3. The diff tells you exactly what moved — parameter expression changes, sketch dimension edits, body additions/removals, and timeline feature count delta.
4. Use the diff to decide next steps: `modify_parameters` to adjust related dimensions, or `execute_script` if structural changes are needed.

This avoids re-reading the full design with `capture_design` when you only need to know what changed.

## Script Sync (after UI tweaks)

When the user tweaks a design in the Fusion UI and you need to update the `.py` script to match:

1. Call `sync_script` — no arguments needed. It reads the tracked script from the DocumentTracker and diffs automatically.
2. The tool auto-patches user parameter expression changes (e.g., `tt_shoulder` from `"0.375 in"` to `"0.3 in"`) and returns the patched script.
3. For changes that need agent help (`needsAgent`), apply each one:
   - `featureParameterChanged` — update hardcoded expressions near the feature's `.name = "..."` line.
   - `featureRemoved` — delete the code block that created the feature.
   - `featureAdded` — generate new code from the capture data and insert it at the appropriate timeline position.
4. Write the updated script to the file.
5. Re-execute via `execute_script(clean=true)` to verify the model matches.

## Sandbox Mode

Use `execute_script` with `sandbox=true` to run a script in a throwaway document. The script executes in a fresh temporary document; on completion, a design snapshot is returned and the temp document is discarded.

**When to use sandbox:**
- Validating a script before committing to the real design (especially complex joinery phases)
- Testing helper imports or sketch logic without risk
- Exploring "what if" variations without polluting the undo history

**Behavior:**
- ActionLog events are suppressed during the sandbox run
- The sandbox document has no user parameters from the real design — scripts must create their own
- Returns `{sandbox: true, snapshot: {...}}` on success
- On error, the temp document is closed and the original document is restored

**Not a substitute for the real execution loop.** Sandbox validates error-free execution but the real design's parameter expressions and timeline context may differ.
