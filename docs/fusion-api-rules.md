# Fusion 360 API Rules

Reference for Fusion 360 Python API patterns used in parametric furniture scripts. Read this file at the start of any build session.

## Design Mode

```python
design.designType = adsk.fusion.DesignTypes.ParametricDesignType
```
Set this BEFORE accessing `design.userParameters`. Without it: `RuntimeError: this is not a parametric design`.

## Do NOT Use

- `TemporaryBRepManager` — creates static geometry inside `BaseFeature` blocks. Parameters exist in Change Parameters but changing them does NOT update geometry.
- `createByReal(value_in_cm)` for parameter creation — shows confusing cm values in the UI.
- Python `int()` at script time for pattern counts — use `floor()` in parameter expressions instead.
- **Python `for` loops for geometry replication** — use Rectangular Pattern or Mirror features instead. A `for` loop creates N independent features that don't update when count changes. A pattern is one parametric feature that recomputes automatically. **Note:** Bodies with CUT/JOIN history create ghost bodies when patterned — see Body Pattern Ghost Bodies under Replication Strategy for how to handle this.

## User Parameters

Create with `ValueInput.createByString("60 in")` so Change Parameters shows readable values:
```python
params.add("total_length", adsk.core.ValueInput.createByString("60 in"), "in", "Overall length")
```

## Derived Parameters

Use expression strings referencing other parameters. These auto-recompute:
```python
params.add("shoulder_length",
           adsk.core.ValueInput.createByString("total_length - 2 * leg_size"),
           "in", "Shoulder length between legs")
```

## Dimensionless Parameters (counts)

For counts derived from `floor()`, use empty string `""` as the unit:
```python
params.add("n_slats", adsk.core.ValueInput.createByString("floor(shoulder_length / slat_width)"), "", "Number of slats")
```
These update automatically when referenced dimensions change.

## Sketch Plane Selection

Two valid approaches, depending on the project:

**Approach A: Sketch on body faces.** When creating a feature that relates to an existing body (joints, pockets, decorative details), find the relevant face on that body and sketch directly on it. The sketch plane inherits the body's position — no construction plane offset to keep in sync.

```python
def find_face(body, axis, direction):
    """Find outermost planar face along axis in direction (+1=max, -1=min).
    Uses abs(normal) because face.geometry.normal doesn't always match
    the outward normal — it's the mathematical plane normal."""
    best = None
    best_val = -1e10 if direction > 0 else 1e10
    for i in range(body.faces.count):
        face = body.faces.item(i)
        geom = face.geometry
        if isinstance(geom, adsk.core.Plane):
            if abs(getattr(geom.normal, axis)) > 0.9:
                fv = getattr(face.pointOnFace, axis)
                if (direction > 0 and fv > best_val) or (direction < 0 and fv < best_val):
                    best_val = fv
                    best = face
    return best

# Example: sketch on the front face (min-Y) of a rail body
front_face = find_face(rail_body, "y", -1)
sk = comp.sketches.add(front_face)
```
Also available as `sp.find_face(body, axis, direction)`.

**Clean references before profile selection (MANDATORY):** Any sketch on a face or with `sketch.project()` calls has reference lines that split profiles into fragments. **Always call `sp.refs_to_construction(sk)` after dimensioning but before selecting a profile.** This converts reference/projected lines to construction geometry — they keep their sketch points (valid for dimensions) but stop forming profile boundaries. Then `sp.smallest_profile(sk)` returns the correct drawn profile. Omitting this step is the #1 cause of wrong-profile extrusions.

```python
# After all sketch geometry and dimensions are complete:
sp.refs_to_construction(sk)
prof = sp.smallest_profile(sk)
ext = sp.ext_new(comp, prof, "depth", "MyFeature")
```

**Extrude direction on body faces:** The default (positive) extrude direction on a face sketch follows `face.evaluator.getNormalAtPoint()` — the true outward normal, pointing AWAY from the body. Use `flip=True` (NegativeExtentDirection) for CUT extrudes on body faces so the cut goes INTO the body.

**Coincident geometry on body-face sketches:** When sketch lines fully coincide with face boundary edges (e.g., an arch baseline at the face corner), Fusion merges them and fails to create separate profiles. Fix: project the face edge via `sk.project(edge)`, then draw the arc from the projected line's sketch points. The projected edge + arc properly split the face. Position dimensions become unnecessary since the projection is already parametric.

**Axis mapping on non-XY planes (MANDATORY):** On construction planes and body faces, sketch H and V map to different model axes than expected. **Always use `sp.probe_orientations()` to get the correct `DimensionOrientation` for each model axis.** Never hardcode H/V assumptions.

```python
# One-liner: returns {'x': H_or_V, 'y': H_or_V, 'z': H_or_V}
orient = sp.probe_orientations(sk, ev("cx"), ev("cy"), ev("cz"))

# Use the dict to assign the correct orientation per model axis:
d.addDistanceDimension(origin, pt, orient['z'], placement
).parameter.expression = "ls_z + ls_w / 2"
d.addDistanceDimension(origin, pt, orient['y'], placement
).parameter.expression = "leg_d / 2"
```

This replaces `probe_sketch_axes` and `probe_sketch_signs` — it returns the orientation enum directly, which is what `addDistanceDimension` needs. No manual axis detection code required.

`sketch_rect_model` and `sketch_slot_model` handle axis mapping internally. Use `probe_orientations` only for custom sketch geometry (circles, manual rectangles) where you add dimensions yourself.

**Sketch plane preference (follow this order):**

1. **Existing body face (preferred).** If a planar face already exists at the needed location, sketch on it. This is how a designer works in the UI — click the face, start sketching. No construction plane needed. Use `sketch_rect_model` with the face as the plane argument; it works on BRepFaces the same as on construction planes.

2. **Construction plane (only when required).** Use only when one of these applies:
   - **No body exists yet** — first body in a component has no face to sketch on.
   - **Midplane for Mirror or Pattern** — no face exists at the midpoint.
   - **Sketch will be mirrored** — face-based sketches CANNOT be mirrored. MirrorFeature fails with NO_TARGET_BODY because the mirror can't find an equivalent face on the mirrored side.
   - **Root-level sketch on a component body** — assembly proxy faces CANNOT host sketches. `comp.sketches.add(proxy_face)` throws `RuntimeError: invalid argument planarEntity`. Root-level cross-component operations must use construction planes.

**During design-first planning, audit every sketch plane:** for each sketch in the plan, ask "does a body face already exist here?" If yes, use it. Only reach for a construction plane if one of the four exceptions above applies. Fewer construction planes = cleaner timeline, faster recompute, and geometry that moves parametrically with the body it belongs to.

## Sketch + Extrude Workflow

```python
# 1. Sketch with approximate geometry
sk = comp.sketches.add(plane)
rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)

# 2. Add geometric constraints FIRST — H/V constraints lock line orientation
gc = sk.geometricConstraints
gc.addHorizontal(rect[0])
gc.addHorizontal(rect[2])
gc.addVertical(rect[1])
gc.addVertical(rect[3])

# 3. Constrain dimensions parametrically
d_w = sk.sketchDimensions.addDistanceDimension(...)
d_w.parameter.expression = "slat_width"  # linked to user parameter

# 4. Extrude with parametric distance
ext_input = comp.features.extrudeFeatures.createInput(profile, operation)
ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByString("body_height"))
```

## Geometric Constraints on Sketch Lines (CRITICAL)

**Every sketch line that should be horizontal or vertical MUST have an explicit geometric constraint.** `addTwoPointRectangle` and `addByTwoPoints` create lines at the correct positions initially, but without explicit `addHorizontal`/`addVertical` constraints, lines can skew when parameters change — rectangles become parallelograms, horizontal edges tilt.

**Rule:** After creating any sketch line, ask: "Should this line stay horizontal or vertical when parameters change?" If yes, add the constraint. Omit H/V constraints on:
- Intentionally angled lines (tapers, chamfer profiles, etc.)
- Arch baselines where both endpoints share the same model Z (already horizontal by construction). On offset planes, `addHorizontal` can perturb arc geometry enough to split thin bodies via CUT.

```python
# Rectangle — constrain all 4 sides
rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)
gc = sk.geometricConstraints
gc.addHorizontal(rect[0])  # bottom
gc.addHorizontal(rect[2])  # top
gc.addVertical(rect[1])    # right
gc.addVertical(rect[3])    # left

# Arch baseline — DO NOT constrain. Both endpoints share the same Z
# (model coordinate), so the line is already horizontal. Adding addHorizontal
# on offset planes can perturb the arc geometry, causing the CUT to split
# thin bodies. The arc's shared sketch points (endSketchPoint/startSketchPoint)
# keep the profile closed without constraints.
arch_line = sk.sketchCurves.sketchLines.addByTwoPoints(p1, p2)
sk.sketchCurves.sketchArcs.addByThreePoints(
    arch_line.endSketchPoint, mid_pt, arch_line.startSketchPoint)

# Taper triangle — constrain the H and V edges, leave the angled line free
# IMPORTANT: H/V constraints are in SKETCH space, not model space.
# On XZ planes: model-X → sketch-H, model-Z → sketch-V (inverted)
# On YZ planes: model-Z → sketch-H (inverted), model-Y → sketch-V
# A line that is "horizontal in model" (same Z, varying X or Y) may be
# VERTICAL in sketch space on YZ planes. Always check probe_sketch_axes
# or modelToSketchSpace to determine the correct constraint direction.
bot = lines.addByTwoPoints(sa, sb)     # same Z, varies in X or Y
lines.addByTwoPoints(sb, sc)           # angled taper — NO constraint
vert = lines.addByTwoPoints(sc, sa)    # same X or Y, varies in Z

# XZ plane example (model-X → sketch-H, model-Z → sketch-V):
sk.geometricConstraints.addHorizontal(bot)   # bot varies in model-X → sketch-H
sk.geometricConstraints.addVertical(vert)    # vert varies in model-Z → sketch-V

# YZ plane example (model-Y → sketch-V, model-Z → sketch-H):
sk.geometricConstraints.addVertical(bot)     # bot varies in model-Y → sketch-V
sk.geometricConstraints.addHorizontal(vert)  # vert varies in model-Z → sketch-H
```

## Extrude Operations

| Operation | Use For |
|-----------|---------|
| `NewBodyFeatureOperation` | New bodies (legs, rails, slat bodies) |
| `CutFeatureOperation` | Mortises, grooves (removing material) |
| `JoinFeatureOperation` | Tenons, tongues (adding material to existing body) |

## participantBodies (CRITICAL)

When doing Cut or Join near other bodies, you MUST specify which body to target:
```python
ext_input.participantBodies = [target_body]  # Python list, NOT ObjectCollection!
```
Using `ObjectCollection` causes `TypeError`. Using no participant bodies causes accidental merging or cutting of adjacent bodies.

## Fillet and Chamfer Features

> **Full reference:** `docs/details-and-finishing.md` — edge selection strategies, chamfer types, code patterns, sizing constraints.

Quick reference:
- **Fillet:** `filletFeatures.createInput()` -> `inp.addConstantRadiusEdgeSet(edges, radius, propagate)`
- **Chamfer:** `chamferFeatures.createInput2()` -> `inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(edges, distance, propagate)`
- Note: chamfer uses `createInput2()` (not `createInput()`) and has a nested `.chamferEdgeSets` collection.
- The API requires `BRepEdge` objects, never `BRepFace`. Iterate face edges and deduplicate via `tempId`.

## Replication Strategy

### Mirror

Use `MirrorFeature` to replicate symmetric parts across construction planes:
```python
mirror_feats = comp.features.mirrorFeatures
body_coll = adsk.core.ObjectCollection.create()
body_coll.add(body)
mirror_input = mirror_feats.createInput(body_coll, midplane)
feat = mirror_feats.add(mirror_input)
```

Construction midplanes should use parametric offsets:
```python
# YZ midplane at half the length
params.add("mid_x", adsk.core.ValueInput.createByString("total_length / 2"), "in", "X midplane")
plane_input.setByOffset(yz_plane, adsk.core.ValueInput.createByString("mid_x"))
```

### Pattern (Rectangular)

For repeated elements (slats, spindles, etc.):
```python
pat_input = pat_feats.createInput(body_coll,
    comp.xConstructionAxis,
    adsk.core.ValueInput.createByString("n_slats"),     # parametric count!
    adsk.core.ValueInput.createByString("slat_width"),   # parametric spacing!
    adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
```

### Body Pattern Ghost Bodies

`RectangularPatternFeature` replays the **entire feature history** of the template body — including CUT and JOIN operations that reference it, even those added later or in different timelines (root vs component). When a CUT uses `keepTool=True`, each pattern instance creates a duplicate tool body ("ghost body"), inflating the body count.

**When body_pattern is safe:** Bodies with only NewBody extrudes and Mirror (no CUT/JOIN in their history, and none added later). Example: dovetail tail bodies before any CUT/JOIN.

**When body_pattern creates ghosts:** Any body that is or will be a CUT tool with `keepTool=True`, or that has CUT/JOIN operations applied to it at any point in the timeline. Example: shelf body CUT by domino voids -> pattern creates ghost void copies at each shelf position.

**Ghost bodies are geometrically harmless.** They sit at the same position as the intentional copies and produce identical CUT pockets. The model geometry is correct. Always prefer patterns over Python loops for parametric count updates.

**Handling ghosts in validation:** Ghost void bodies overlap with their originals, producing interferences. Filter these from `check_interference` results — exclude pairs where both bodies are void/tool bodies (identifiable by naming convention, e.g. `ShDm_*`). Real interferences involve structural bodies (boards, panels), not void-on-void overlaps.

### Mirror + Pattern Limitation (CRITICAL)

Fusion 360 CANNOT properly mirror a `RectangularPatternFeature`. When you mirror features that include a pattern, only the template body gets mirrored -- pattern copies are lost.

**Correct approach for symmetric repeated elements:**
1. Build the template on side A (body + all features like grooves, tongues)
2. Mirror ONLY the template features to side B
3. Create an INDEPENDENT pattern on side A (count = parametric expression)
4. Create an INDEPENDENT pattern on side B (same parametric count expression)

Each side gets its own pattern feature. When the user changes dimensions, ALL patterns update independently.

### Mirror Bodies vs Mirror Features

- **Mirror bodies**: captures a fixed set of bodies at script time. If pattern count increases later, the mirror won't include new bodies. Use only for simple cases (legs, rails).
- **Mirror features**: replicates the feature operations. Better for maintaining parametric behavior. Use for templates that will be patterned.

### Typical Replication Sequence

For a part with symmetric tenons/tails that repeats along an axis:

1. **Extrude** ONE tenon/tail as NewBody
2. **Mirror** across one midplane -> 2 copies
3. **Mirror** across perpendicular midplane -> 4 copies
4. **JOIN** all copies into the parent body -> single merged body
5. **Body Pattern** the merged body along the repetition axis

Result: one parametric pattern feature replaces an entire Python `for` loop.

## Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `RuntimeError: this is not a parametric design` | Accessed `userParameters` before setting `ParametricDesignType` | Set `design.designType` first |
| `RuntimeError: A valid targetBaseFeature is required` | Used `TemporaryBRepManager` | Switch to Sketch > Extrude |
| `RuntimeError: No target body found to cut` | Cut sketch drawn outside the body | Position sketch inside the body |
| Parameters don't update geometry | Used `TemporaryBRepManager` (static BRep) | Use feature-based modeling |
| Mirror only creates partial copies | Mirrored a `RectangularPatternFeature` | Mirror only template, create independent patterns |
| Mirror side doesn't update count | Mirrored bodies (fixed set at script time) | Mirror template features, independent patterns per side |
| Cut/Join affects wrong body | No `participantBodies` specified | Use `ext_input.participantBodies = [body]` |
| `TypeError` on participantBodies | Passed `ObjectCollection` instead of list | Use Python `[body]` list |
| Count doesn't update parametrically | Used Python `int()` at script time | Use `floor()` in Fusion parameter expressions |
| Body pattern creates extra bodies | `keepTool=True` CUTs in template history create ghost duplicates at each pattern instance | Ghost bodies are harmless — keep patterns for parametric counts. Filter ghost overlaps from `check_interference` by excluding void-on-void pairs. |
| Mortise CUT destroys the receiving board | CUT body diameter >= board thickness (e.g., 0.75" spindle in 0.75" rail) | Mortise diameter must be < board thickness. Leave >= 1/4 wall on each side. Use blind mortises (stub tenon), not through. |
| Fusion crashes / hangs on complex scripts | Too many individual features created in a loop (e.g., 140 dowels = 700+ timeline features). Each `dowel.single()` or `domino.single()` creates sketch + extrude + fillet + CUT. | **Use bulk CUT instead of per-element joints.** For repeated elements (spindles, slats) that insert into rails, build all bodies first (body_pattern), then CUT them ALL into the target in ONE `sp.combine(rail, [all_spindles], CUT, True)` call. 8 bulk CUTs replaced 140 individual dowels in the crib build. |
| Sketch geometry at mirrored/wrong position on non-XY plane | `probe_sketch_axes` gives axis name but not sign; model +Z -> sketch -Y on XZ planes | Use `probe_sketch_signs` or `modelToSketchSpace` for approximate positions, flip offset operator based on sign |
| Loose tenon (domino) bodies disappear | Second CUT used `keepTool=False`, consuming the body | Use `keepTool=True` on ALL CUTs for visible loose tenon joints |
| Rectangle deforms when parameter changes | `addTwoPointRectangle` lacks explicit H/V geometric constraints | Add `addHorizontal`/`addVertical` on all 4 lines after creation. Apply same rule to any sketch line that should stay H or V. |
| H/V constraint distorts triangle on YZ plane | On YZ planes, model-Y maps to sketch-V and model-Z to sketch-H — opposite of XZ planes. Using `addHorizontal` on a model-horizontal (same-Z) line that's sketch-vertical destroys the profile. | **Use `sp.probe_orientations(sk)`** to get correct H/V per model axis. Never hardcode H/V on non-XY planes. |
| Chamfer fails with `createInput()` | Chamfer API requires `createInput2()`, not `createInput()` | Always use `chamferFeatures.createInput2()` and the nested `.chamferEdgeSets` collection |
| Fillet fails — radius too large | Fillet radius exceeds half the smallest adjacent face dimension | Reduce `fl_r`; keep it < half the shortest edge on any affected face |
| Fillet/chamfer selects wrong edges | Edge coordinate filter matches unintended edges (e.g., groove interior edges) | Add `edge.body.name` check; filter by both coordinate AND body |
| Chamfer fails with non-manifold error | Chamfer selected edges at groove/mortise boundaries where two volumes meet | Only chamfer outer perimeter edges (check bounding box), skip edges at joint interfaces. Never chamfer mating lines of joints. |
| No profile created on face sketch | Drawn rectangle has same height/width as the face — edges coincide with auto-projected face boundary, Fusion merges them | Use a **construction plane** at the same position instead of the face. No auto-projected edges -> clean single profile. Common with full-width tenons. |
| Tenon extrudes into stretcher body | Default extrude direction on construction plane goes in +normal, which may point into the stretcher instead of into the leg | Place the tenon sketch plane at the **outer end** of the tenon (proud face or blind stop). Extrude inward — the default +normal direction goes toward the stretcher body. |
| Fillet API rejects BRepFace | `addConstantRadiusEdgeSet` requires edges, not faces | Iterate `face.edges`, deduplicate via `tempId`, add individual edges |
| `InternalValidationError: face` on sketch | CUT/JOIN modifies body topology, invalidating BRepFace references | Re-find face with `sp.find_face()` after each CUT/JOIN before next sketch |
| Face-sketch extrudes wrong profile | Auto-projected face edges and `sketch.project()` reference lines split profiles into fragments — `smallest_profile` picks a fragment instead of the drawn shape | **Always call `sp.refs_to_construction(sk)` before profile selection.** This converts all reference/projected lines to construction geometry so they don't form profile boundaries. Then `sp.smallest_profile(sk)` returns the correct drawn profile. This is mandatory for ANY sketch on a face or with projected references. |
| Symmetric extrude body 2x too thick | Passed full thickness to `ext_new_sym` — it applies `dist` to EACH side | Pass half-thickness: `ext_new_sym(comp, prof, "board_t / 2", ...)` |
| `sketch_rect_model` places body on wrong side of origin | Position dimensions use absolute distance — negative coordinates reflect to positive | Use manual sketch with `modelToSketchSpace` + width/height dimensions only (no position dimensions) |
| Shoulder CUT extends outward instead of into body | Default extrude direction on a body face points away from the body | Use `flip=True` on face-sketch CUT extrudes (see `docs/joinery/mortise-tenon.md`) |
| Orphan body in model from rewritten code | Rewrote a feature but only partially removed the old code (e.g., deleted old sketch but left its extrude) | Replace the entire old block when rewriting — don't patch around it. Partial cleanup like `deleteMe()` calls leaves orphan geometry. Old code is recoverable from git. |
| Domino has square corners (rectangular cross-section) | Used `sketch_rect` instead of `sketch_slot` for domino void body | **Always use `sketch_slot`** — real Festool dominos have stadium (rounded-end) cross-sections. See `docs/joinery/domino-joint.md` for the full implementation. |
