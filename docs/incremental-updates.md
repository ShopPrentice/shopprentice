# Incremental Updates & Interactive Editing

Rules for modifying existing designs, and the interactive editing workflow where the user makes changes in the Fusion UI and the agent incorporates them into the script.

## Interactive Editing Mode

When working on an existing design, the agent and user collaborate through a detect-interpret-implement loop:

### Automatic Detection

**At conversation start** (when a tracked design is open):
1. Call `get_document_status` — is this a tracked script build?
2. Call `get_changes` — has anything changed since the last script execution?
3. If changes detected, report them to the user before proceeding.

**During the conversation** — check for changes:
- Before every `execute_script` on an existing design
- When the user's message implies they edited something ("I adjusted...", "I added...", "take a look...")
- When the user asks to rebuild/update the script

### UI Edits Are Design Intent, Not Literal Specs

When the user edits the model in the Fusion UI, their edit is a **signal of what they want**, not necessarily the correct implementation. The agent must:

1. **Capture** — call `sync_script` or `capture_design` to see what changed
2. **Interpret** — what is the user trying to achieve? A chamfer on a tenon face means "I want chamfers on exposed tenon ends." It does NOT mean "add this exact chamfer feature at this exact timeline position."
3. **Plan** — how to implement the intent correctly following skill rules. Run the decision framework below. The implementation may differ from the user's UI edit:
   - User adds a chamfer manually on 4 edges → agent implements it as a loop over stretcher bodies with an edge selection strategy
   - User moves a pin by dragging → agent recalculates the parametric expression for pin position
   - User adds a new body in the root → agent rebuilds it in the correct component
4. **Confirm** — if the implementation differs significantly from the UI edit, explain why and confirm with the user
5. **Execute** — rebuild the affected script section

### What NOT to Do

- Don't blindly replicate the user's UI edit into the script
- Don't add features at the end of the script that should be in a specific build-order position
- Don't create new components for geometry that belongs in an existing one
- Don't skip the decision framework because "the user already did it in the UI"

## The Core Problem

When a user requests a change, the fastest path is to patch the minimum code. But patches accumulate violations of the skill rules — absolute coordinates, wrong components, broken mirrors, missing parametric dimensions. Each patch makes the next change harder, until the model breaks on parameter changes.

**Default stance: step back before patching.** Before writing any code, evaluate the change against the rules below. If a rule would be violated, redesign the affected section, don't patch around it.

## Decision Framework

Ask these questions in order before making any change:

### 1. Does this change touch a joint?

If yes: **rebuild the joint using its template.** Never add geometry to a joint piecemeal.

- Adding pins to a tenon? Use the drawbore template's full workflow (body -> tenon -> pins -> mirror -> JOIN/CUT).
- Changing a tenon from blind to through? Rebuild the stretcher section, don't just extend the existing extrude.
- Adding a new joint type? Check if a template exists. If so, use it. If not, follow the combine-based joinery workflow (rule 6 in the skill).

**Why:** Joint geometry has strict ordering requirements (build order, mirror timing, CUT/JOIN sequence). Patching one step without updating the others creates orphan bodies, wrong extrude directions, or pins in the wrong component.

### 2. Which component owns the new geometry?

New geometry belongs in the component it's structurally part of:

| New Feature | Belongs In | NOT In |
|-------------|-----------|--------|
| Tenon on a stretcher | Stretcher component | Root, Legs |
| Drawbore pin through tenon | Stretcher component (with the tenon) | Separate Pin component, Root |
| Dog holes in the top | Top component | Root |
| Vise screw bore in leg | Root (cross-component CUT) | Vise component |
| Tongue groove in stretcher | Stretcher component (local CUT) | Root |

**Why:** Features in the wrong component don't move with their parent body. Pins in a separate component don't follow the stretcher when `leg_setback` changes. Cross-component CUT is only for joints between different assemblies.

### 3. Is the new geometry referenced correctly?

Every new sketch must be face-relative or use parametric dimensions:

- **Sketch on a face** -> dimension from face corner (`_face_fl_pt`) or projected reference
- **Sketch on a construction plane** -> dimension from origin with parametric expressions, use `sp.probe_orientations()` for H/V
- **Never** place geometry with `ev()` alone — always add `addDistanceDimension` with parameter expressions

**Check:** "If the user changes `leg_setback` or `bench_w`, does this new geometry still land in the right place?"

### 4. Does the change affect mirrored/patterned features?

If the original feature was built before a Mirror or Pattern:

- **Add the new feature BEFORE the mirror** so it gets replicated automatically
- If adding after the mirror, you must add to BOTH sides manually (error-prone — prefer before)

If the change modifies a feature that was mirrored:

- **Rebuild from the original**, not the mirror copy. The mirror will update.

### 5. Does the extrude direction need checking?

When sketching on a construction plane for a tenon or CUT:

- **Place the plane at the OUTER end** of the extrusion (proud face, blind stop)
- Default +normal direction goes inward toward the parent body
- Never assume direction — verify with a test extrude or check the plane normal

### 6. Are there profile selection risks?

If the new sketch is on a face or has projected references:

- **Always call `sp.refs_to_construction(sk)` before profile selection**
- If the drawn geometry is the same size as the face in any dimension, use a construction plane instead (coincident edge problem)

## When to Rebuild vs Patch

| Change | Patch OK? | Rebuild? |
|--------|-----------|----------|
| Change a parameter value | Patch: `modify_parameters` | -- |
| Add a chamfer to existing edges | Patch: new chamfer feature | -- |
| Move a feature (e.g., pins closer to shoulder) | **Rebuild** the joint section | Don't edit `ev()` values |
| Add a new joint type to an existing body | **Rebuild** the body's section with the new joint integrated | Don't add bodies in root |
| Change blind tenon to through | **Rebuild** the stretcher section | Don't just extend the extrude |
| Add tongue-and-groove to a sliding part | **Rebuild** or add before cross-component cuts | Don't CUT from root with root bodies |
| Widen a part that has joints | **Rebuild** if joints reference the old width | Patch only if joints use parametric expressions |

## Red Flags (Stop and Rethink)

If you find yourself doing any of these, stop and redesign:

1. **Creating a new component for geometry that belongs to an existing one** — pins in DrawborePins instead of LongStretchers
2. **Using `ev()` without adding parametric dimensions** — positions will be stale
3. **Adding features after a mirror that should be before it** — the mirror copy won't have the feature
4. **Building a tool body in root for a cross-component CUT** — crashes Fusion when mixed with proxies
5. **Sketching on a face when the geometry matches the face dimensions** — coincident edges, no profile
6. **Extruding a tenon from the stretcher end face** — direction goes into the stretcher, not the leg

## Workflow for Any Change

1. **Detect changes.** Call `get_changes` or `sync_script`. If no changes, proceed with the user's verbal request.
2. **Interpret intent.** The UI edit shows WHAT the user wants. The agent decides HOW to implement it correctly.
3. **Locate the affected section** in the script. Identify the component, the build order position (before/after mirrors, before/after cross-component cuts).
4. **Run the decision framework** (6 questions above).
5. **If rebuild needed:** replace the entire section with the correct workflow. Don't patch around old code.
6. **If patch OK:** add the feature in the correct position (before mirrors if applicable), with parametric dimensions, in the correct component.
7. **Test with `capture_design`** to verify body count, positions, and volumes.
8. **Test parametric robustness** by imagining: "What if the user changes `leg_setback`? `bench_w`? `ls_w`? Does everything still work?"

## Build Strategy (Component-by-Component)

Models are built **one component at a time**. Each component gets its own plan → build → validate cycle, keeping conversation context bounded regardless of total model complexity. The script file grows on disk between components, but each conversation cycle only deals with the current component's features.

**Small pieces** (boxes, trays — < ~8 bodies, 1-2 joint types) can be built in a single pass.

### Build Order

```
1. Plan ALL components upfront (high-level, one response)
2. For each component (separate plan → build → validate cycle):
   a. Shared parameters + helpers  (first component only)
   b. Component creation + construction planes
   c. Body extrudes + internal mirrors/patterns
   d. Splay moves if this component connects to splayed members (see angled-construction.md "Stretcher Splay Matching")
   e. Internal joinery (JOINs within the component)
   f. Validate with capture_design
3. Cross-component operations (root-level, one cycle):
   a. Assembly proxy CUTs (mortises, dados, grooves)
   b. Validate body count and interference
4. Details (final cycle):
   a. Fillets, chamfers, decorative cutouts
   b. Validate → apply_appearance → get_product_shots → present to user
```

### Why Component-by-Component

The conversation context is the bottleneck, not the script. Each component cycle adds ~5-15 features worth of code, errors, and validation to the conversation. After the cycle completes and the agent moves to the next component, only the script file carries forward — the conversation context for previous components can be compressed.

**Phase-based (old, hits token limits on complex models):**
```
Phase 1: ALL structure (all components) → huge script + debug context
Phase 2: ALL joinery (all components) → even bigger
Phase 3: ALL details → biggest
```

**Component-based (scales to any complexity):**
```
Component A: structure + internal joinery → bounded context → done
Component B: structure + internal joinery → bounded context → done
...
Cross-component: CUTs → bounded context → done
Details: fillets → bounded context → done
```

### Rules

1. **One component per build cycle.** Plan the component, write its section of the script, execute, validate. Don't combine multiple components in one cycle.
2. **Validate after each component.** Call `capture_design` to verify body count, positions, and volumes for the component just built.
3. **Auto-proceed on success.** If validation passes, immediately plan the next component. Do NOT wait for user approval between components.
4. **Same file, growing content.** All components accumulate in the same `.py` file. Each cycle appends to the existing script.
5. **Each script execution rebuilds from scratch.** The full script runs every time (document reuse pattern). This is fast — Fusion rebuilds a 100-feature timeline in seconds.
6. **Plan before code, always in separate responses.** Before each component, output its step list as text. Then write the code and execute in the next response.
7. **Cross-component operations are a separate cycle.** After all components are built, one final cycle adds root-level CUTs via assembly proxies.
8. **Details are the last cycle.** Fillets and chamfers require all geometry to exist first.
9. **Show final result.** After the last cycle, call `apply_appearance` then `get_product_shots` to capture presentation-quality images and present to the user.
10. **Replace, don't patch.** When an approach doesn't work and you rewrite it, **replace the old code block entirely** — don't add new code below while partially cleaning up the old (e.g., calling `deleteMe()` on an old sketch but leaving its extrude). Partial cleanup creates orphan bodies invisible in code review but visible in the model. The old code is always recoverable from git or undo, so replacing is safe.
11. **Detect UI changes automatically.** When working on an existing design, call `get_changes` at conversation start and before any `execute_script`. If changes are detected, capture them with `sync_script`, interpret the user's intent (UI edits are design signals, not literal specs), then implement correctly following the decision framework in `docs/incremental-updates.md`. The default is to rebuild the affected section properly, not to replicate the UI edit verbatim.

### What Goes Where

| Where | What |
|-------|------|
| **First component cycle** | Document preamble, shared parameters, shared helpers, midplanes |
| **Each component cycle** | `make_comp`, component-local planes, extrudes, internal mirrors/patterns/JOINs |
| **Cross-component cycle** | Assembly proxy creation, root-level Combine CUTs (`keepTool=True`) |
| **Details cycle** | Fillets, chamfers (edge selection by coordinate or face) |

### Keeping Each Cycle Bounded

When writing code for a new component, do NOT re-read the entire script. Instead:
- Read only the last ~20 lines (to see where to append)
- Know the parameter names and body names from the plan (established in the first cycle)
- Append the new component's code block

When debugging, focus only on the current component's features — don't re-analyze earlier components that already validated.

### Document Management — DO NOT manage documents in scripts

Scripts MUST NOT close or create documents. The `execute_script` MCP tool manages the scratch document via `clean=True`. A script that calls `doc.close(False)` or `app.documents.add()` conflicts with the transaction wrapper and causes Fusion to allocate unbounded memory (200+ GB observed), freezing the application.

A guard in `execute_script.py` rejects scripts containing this pattern.

```python
def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    root = design.rootComponent
    params = design.userParameters
    Point3D = adsk.core.Point3D
    # ... build from scratch ...
```

Use `execute_script` with `clean=True` for a fresh slate — it deletes all timeline features and user parameters before running, wrapped in a single transaction (Ctrl+Z reverts everything).

### Script Epilogue

Every script should end with five standard steps:

```python
# 1. Hide construction elements (clean viewport)
for sk in root.sketches:
    sk.isVisible = False
for cp in root.constructionPlanes:
    cp.isLightBulbOn = False
for ca in root.constructionAxes:
    ca.isLightBulbOn = False

# 2. Diagnostic body count per component
for comp_name, comp in [("Posts", post_c), ("Rails", rail_c), ...]:
    names = [comp.bRepBodies.item(i).name for i in range(comp.bRepBodies.count)]
    print(f"{comp_name}: {len(names)} bodies")
names = [root.bRepBodies.item(i).name for i in range(root.bRepBodies.count)]
print(f"Root: {len(names)} joinery voids")

# 3. Apply wood appearance (grain-aligned texture on all bodies)
sp.apply_appearance("white oak")
```

**Step 3 is required** — scripts without `sp.apply_appearance()` produce grey models. Use the species the user requested; default to white oak if none specified. See `docs/appearance.md` for species and grain details.

After the script runs, call `get_product_shots` via MCP to capture presentation images. It handles camera positioning, artifact cleanup, and framing automatically — no fit-view or hide-sketch code needed in the script.
