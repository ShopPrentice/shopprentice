# ShopPrentice Script Generator — Developer Workflow

When working on the search-based script builder (`dev/search_build.py`) or the script generator (`addin/tools/_script_generator/`), follow these rules strictly.

## Document Safety — ABSOLUTE RULES

| Action | Allowed On | NEVER On |
|--------|-----------|----------|
| `capture_design` | Any document (read-only) | — |
| `get_timeline_state` | Scratch (Untitled) docs ONLY | **Saved documents** — rolls timeline marker, can corrupt |
| `execute_script` | Scratch docs ONLY | **Saved documents** — `clean=true` destroys timeline |
| `execute_script(sandbox=true)` | Any (uses temp doc) | — |

**Before ANY `execute_script` or `get_timeline_state`:**
1. Call `_verify_active_unsaved()` or manually check with `manage_documents(action="list")`
2. If the active doc is saved → switch to scratch doc first
3. Never assume the active doc is safe — always verify

**Capture caching:**
- Save captures to `/tmp/<design_name>_capture.json` after the first `capture_design`
- Reuse with `--capture <file>` on subsequent runs
- Only recapture if the capture code (`_capture_helpers.py`) was modified

## Diagnostic Framework — When a Feature Fails

When the search builder stops at a feature, follow this decision tree:

### 1. Is it a SCRIPT ERROR or a MISMATCH?

**SCRIPT ERROR** — the generated code crashes:
- Check the error line number in the per-feature script
- Common causes:
  - `NoneType` — entity lookup failed (body not found, sketch not found, plane not found)
  - "not in assembly context" — cross-component reference without proxy
  - "over-constrained" — redundant dimension or constraint
  - SyntaxError — indentation drift in generator code

**MISMATCH** — volumes/positions don't match ground truth:
- Check volume error percentage
- Check bounding box positions
- Compare profile count and curve positions if sketch-related

### 1b. Is it a CASCADE?

**CASCADE** — a body's volume changes but it's not a direct target of the feature:
- Caused by Fusion's internal parametric dependency chain (e.g., fillet on wall changes deck board volume because deck sketch has partial coincidence with wall face boundary)
- Signs: volume mismatch < 1%, bounding box matches, body not in feature's `bodies` or `inputs` list
- The search builder auto-detects cascades and tracks volume deltas through subsequent features
- Pattern copies of cascade bodies inherit the same delta (detected by matching known offsets against actual data)
- **Never use base-name matching** to propagate cascades — bodies in different components can share names (e.g., "Body1 [deck5]" vs "Body1 [rafts (1)]")

### 2. Identify the Root Cause Category

| Category | Signs | Fix Location |
|----------|-------|-------------|
| **Missing capture data** | Feature field is empty/None, edges=[], bodies=[] | `_capture_helpers.py` |
| **Wrong entity resolution** | `NoneType` error, wrong body/sketch found | `_core.py` → `_rebuild_entity_context` |
| **Coordinate mismatch** | Correct shape but wrong position/orientation | `_feat_sketch.py` → `_coord_transform`, `_xf` |
| **Cross-component context** | "not in assembly context" error | `_base.py` → `find_body` proxy, `_feat_sketch.py` → `sketch_comp` |
| **Dimension/constraint conflict** | "over-constrained", "already has dimension" | `_feat_sketch.py` → try/except guards, constraint order |
| **API limitation** | All variants fail, geometry looks correct visually | Check UI vs API — file Autodesk forum issue |
| **Missing search variant** | Best variant has >0% error, correct option not tried | `_variants.py` → `_*_variants()` methods |
| **Profile selection** | Wrong profile index, extrude creates wrong body | `_feat_extrude.py` → profile bbox matching |
| **Body naming** | Bodies exist but with wrong names (split/rename) | `_core.py` → `_fixup_split_body_names`, rename logic |
| **New feature type** | "TODO: Unsupported feature type" | Add `_feat_<type>` emitter |
| **Parametric cascade** | Volume shifts on non-target bodies, < 1% | `search_build.py` → `_detect_cascades` auto-handles |

### 3. Capture Issues — What to Check

When a feature's capture data looks incomplete:

```
Capture field missing?
├── edges: []           → Check _capture_edge_vertices: BRepFace vs BRepEdge
├── bodies: []          → Check rollTo mode: use markerPosition, not rollTo(True)
├── splitTool: error    → Needs rollTo(True) for BRep-dependent properties
├── dimensions: []      → Check if sketch was rolled to correct position
├── constraints: []     → Check if constraints are dict format (not legacy string)
├── sketchXDir: None    → Capture doesn't record axes for construction plane sketches
└── profileCount wrong  → Downstream features may have altered sketch profiles
```

**After fixing capture**: `reload_addin` to pick up changes, then recapture.

### 4. Generator Issues — What to Check

When the generated code doesn't match the original:

**Entity not found:**
- Multiple entities with same name across components → use component-scoped lookup
- Body renamed by downstream split → `_fixup_split_body_names` with `inputBody`
- Body name at end-of-timeline vs at-feature-time → compare with `get_timeline_state`

**Wrong coordinates:**
- BRepFace sketch with different axes → `_coord_transform` + `_xf`
- Construction plane sketch (XZ/YZ) with flipped axes → capture `sketchXDir`/`sketchYDir`
- Negative offset in rect sketch → use `abs()` for distance dimensions

**Cross-component:**
- Sketch on face from other component → create sketch in root (proxied access)
- Body projection with `intersectWithSketchPlane` → bodies must be proxied via `occ.bRepBodies`
- Construction plane in child component → search all occurrences

### 5. API Limitation Detection

When NO variant produces a 100% match and the geometry looks correct visually:

1. Check if the Fusion UI exposes more options than the Python API
2. Known API gaps:
   - `SplitBodyFeature`: UI supports multiple tools, API only accepts one
   - `SplitBodyFeature.splittingTool`: singular, read-only — can't read second tool
   - `FilletEdgeSet.edges`: returns BRepFaces in edit mode, not BRepEdges
   - `face.geometry.normal`: mathematical normal, NOT outward normal
3. Workaround patterns:
   - Multi-tool split → emit sequential single-tool splits, validate by volume
   - Face fillets → find faces by pointOnFace, add edges of matched faces
   - Wrong normal → use `pointOnFace` with `find_face_near` instead of normal direction
4. File issue on Autodesk forum: https://forums.autodesk.com/t5/fusion-api-and-scripts-forum/

### 6. New Fixture Needed?

Create a fixture in `tests/fixtures/` when:
- A new feature type is implemented (e.g., `fixture_split_body.py`)
- An API behavior needs regression testing
- A capture/generator fix affects a specific geometry pattern

**Fixture rules:**
- Name everything (bodies, features, sketches, planes)
- Use parametric expressions, not hardcoded values
- Use explicit constraints (H/V, coincident)
- Keep minimal — test ONE specific behavior
- Run `python tests/test_round_trip.py fixture_<name>` to verify

## Development Loop

```
1. Run search_build on saved capture: --capture /tmp/<name>_capture.json
2. Feature N fails → identify category from decision tree above
3. Fix in _capture_helpers.py or _script_generator/ package
4. reload_addin (if capture fix)
5. Run round-trip tests: python tests/test_round_trip.py (must stay 21/21)
6. Re-run search_build with --capture (reuse saved capture)
7. Feature N passes → continue to N+1
8. Commit when a batch of features passes
```

**Never:**
- Modify user's saved document
- Accept approximate matches (tolerance > 0.01%)
- Skip validation steps
- Run ground truth collection on saved documents
- Use base-name matching to propagate cascade deltas across components

**Always:**
- Verify active doc is unsaved before execute_script
- Check positions AND volumes (not just volumes)
- Wrap constraints/dimensions in try/except for robustness
- Use occurrence-proxied bodies for cross-component access
- Save captures to files for reuse
- Close and recreate the scratch doc if `clean=True` fails silently (stale params/features survive)

## Scratch Document Stale State

`_clean_design()` deletes timeline features + user parameters inside a transaction. If deletions fail silently (caught by `except: pass`), the document retains stale state. Subsequent `params.add()` calls fail with "param name is not valid" because the parameter already exists.

**Signs:** prefix script reports OK but features immediately fail with `evaluateExpression` errors (parameters not found) or "param name is not valid".

**Fix:** Close the Untitled scratch document via `manage_documents(action="close")` and let `ensure_scratch_doc` create a fresh one. This is faster than debugging which specific deletion failed.
