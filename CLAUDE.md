# AutoFusion

Parametric furniture modeling for Fusion 360, driven by AI agents via MCP.

## For Agents: How to Use This System

When the user asks you to design or build furniture in Fusion 360, invoke the `/woodworking` skill. It contains the complete parametric modeling workflow: design philosophy, API rules, joinery conventions, and the phase-based execution loop.

### Quick Reference

| Tool | When to Call |
|------|-------------|
| `execute_script` | Run a Fusion 360 Python script (one phase at a time). Set `sandbox=true` for throwaway validation, `clean=true` to rebuild an existing model (Ctrl+Z reverts). |
| `capture_design` | After every `execute_script` — validate body count, positions, volumes |
| `get_timeline_state` | When `capture_design` shows unexpected state — bisect timeline to find the bad feature |
| `get_screenshot` | Once at the end — present the final result to the user |
| `get_selection` | Read what the user has selected in the Fusion 360 UI |
| `set_selection` | Highlight entities for the user (after identifying a problem body, etc.) |
| `modify_parameters` | Change parameter values without re-running the script — for iterative tuning |
| `check_interference` | Detect body collisions — validate joinery fits correctly |
| `suppress_features` | Toggle timeline features on/off for "what if" diagnostics |
| `get_changes` | Detect what changed since last call — snapshot & diff parameters, dimensions, bodies |
| `sync_script` | After UI tweaks — auto-patch parameter changes in script, report feature adds/removes/edits for agent |
| `get_document_status` | Check if the active document was built by a known script — gates incremental updates |

### Workflow

1. Invoke `/woodworking` to get full design rules
2. Plan the build (components, features, joinery)
3. Execute Phase 1 (structure) → validate with `capture_design`
4. Execute Phase 2 (joinery) → validate with `capture_design`
5. Execute Phase 3 (details) → validate → screenshot → present to user

### Key Principles

- **Parametric**: Every dimension uses parameter expressions, not hardcoded values
- **Feature-based**: Sketch > Dimension > Extrude (no TemporaryBRepManager)
- **Combine-based joinery**: Build tenon as body, CUT into receiver, JOIN to owner
- **Validate every phase**: `capture_design` after each execution, not just screenshots

### Document Safety Rules (for search_build / script generator development)

**NEVER modify user-saved documents.** All testing and building must happen on scratch (unsaved) documents.

| Action | Safe Target | NEVER On |
|--------|-------------|----------|
| `capture_design` | Any document (read-only) | — |
| `get_timeline_state` | Scratch doc only | Saved documents — rolls timeline marker |
| `execute_script` | Scratch doc only | Saved documents — `clean=true` destroys timeline |
| `execute_script(sandbox=true)` | Any (uses temp doc) | — |
| Ground truth collection | Source doc via `get_timeline_state` | Must roll back to end after |

**Workflow for search_build:**
1. **Capture** from the user's saved document (read-only `capture_design`)
2. **Save capture to file** (`/tmp/<name>_capture.json`) — reuse across runs
3. **Switch to scratch doc** before any `execute_script` or `get_timeline_state`
4. **Ground truth**: collect on the source doc, then **immediately roll back** to end
5. **Build**: all feature execution on scratch doc only
6. Use `--capture <file>` flag to skip re-capturing on subsequent runs
7. `_verify_active_unsaved()` guard before any `clean=True` call
