# Incremental Updates

Rules for modifying existing designs. Read this topic when the user asks to change, add, or remove features from an already-built model.

## The Core Problem

When a user requests a change, the fastest path is to patch the minimum code. But patches accumulate violations of the skill rules — absolute coordinates, wrong components, broken mirrors, missing parametric dimensions. Each patch makes the next change harder, until the model breaks on parameter changes.

**Default stance: step back before patching.** Before writing any code, evaluate the change against the rules below. If a rule would be violated, redesign the affected section, don't patch around it.

## Decision Framework

Ask these questions in order before making any change:

### 1. Does this change touch a joint?

If yes: **rebuild the joint using its template.** Never add geometry to a joint piecemeal.

- Adding pins to a tenon? Use the drawbore template's full workflow (body → tenon → pins → mirror → JOIN/CUT).
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

- **Sketch on a face** → dimension from face corner (`_face_fl_pt`) or projected reference
- **Sketch on a construction plane** → dimension from origin with parametric expressions
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
| Change a parameter value | Patch: `modify_parameters` | — |
| Add a chamfer to existing edges | Patch: new chamfer feature | — |
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

1. **Read the request.** Identify what's changing.
2. **Locate the affected section** in the script. Identify the component, the build order position (before/after mirrors, before/after cross-component cuts).
3. **Run the decision framework** (6 questions above).
4. **If rebuild needed:** replace the entire section with the correct workflow. Don't patch around old code.
5. **If patch OK:** add the feature in the correct position (before mirrors if applicable), with parametric dimensions, in the correct component.
6. **Test with `capture_design`** to verify body count, positions, and volumes.
7. **Test parametric robustness** by imagining: "What if the user changes `leg_setback`? `bench_w`? `ls_w`? Does everything still work?"
