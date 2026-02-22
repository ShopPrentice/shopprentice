# Fusion 360 Parametric Furniture Modeling

You are generating a Fusion 360 Python script to build a parametric furniture model. Follow these rules strictly.

## Design Philosophy: Build Like a Human

1. **Build one, replicate the rest.** Never build every piece from scratch. Build one representative instance, then use Mirror, Pattern, and Copy features for the rest. This makes the model manageable and editable.

2. **Everything parametric.** When the user changes any dimension in Modify > Change Parameters, the entire model must recompute automatically -- lengths, mirror positions, pattern counts, everything.

3. **Organize with components.** Group related bodies into named components (e.g., Legs, Rails, Slats, Panels). Never dump everything flat in the root component.

4. **Feature-based modeling only.** Every shape is: Sketch rectangle > Constrain dimensions parametrically > Extrude. This creates timeline features that recompute when parameters change.

## Fusion 360 API Rules

### Design Mode (MUST be first)
```python
design.designType = adsk.fusion.DesignTypes.ParametricDesignType
```
Set this BEFORE accessing `design.userParameters`. Without it: `RuntimeError: this is not a parametric design`.

### Do NOT Use
- `TemporaryBRepManager` -- creates static geometry inside `BaseFeature` blocks. Parameters exist in Change Parameters but changing them does NOT update geometry.
- `createByReal(value_in_cm)` for parameter creation -- shows confusing cm values in the UI.
- Python `int()` at script time for pattern counts -- use `floor()` in parameter expressions instead.

### User Parameters
Create with `ValueInput.createByString("60 in")` so Change Parameters shows readable values:
```python
params.add("total_length", adsk.core.ValueInput.createByString("60 in"), "in", "Overall length")
```

### Derived Parameters
Use expression strings referencing other parameters. These auto-recompute:
```python
params.add("shoulder_length",
           adsk.core.ValueInput.createByString("total_length - 2 * leg_size"),
           "in", "Shoulder length between legs")
```

### Dimensionless Parameters (counts)
For counts derived from `floor()`, use empty string `""` as the unit:
```python
params.add("n_slats", adsk.core.ValueInput.createByString("floor(shoulder_length / slat_width)"), "", "Number of slats")
```
These update automatically when referenced dimensions change.

### Sketch + Extrude Workflow
```python
# 1. Sketch with approximate geometry
sk = comp.sketches.add(plane)
rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)

# 2. Constrain dimensions parametrically
d_w = sk.sketchDimensions.addDistanceDimension(...)
d_w.parameter.expression = "slat_width"  # linked to user parameter

# 3. Extrude with parametric distance
ext_input = comp.features.extrudeFeatures.createInput(profile, operation)
ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByString("body_height"))
```

### Extrude Operations
| Operation | Use For |
|-----------|---------|
| `NewBodyFeatureOperation` | New bodies (legs, rails, slat bodies) |
| `CutFeatureOperation` | Mortises, grooves (removing material) |
| `JoinFeatureOperation` | Tenons, tongues (adding material to existing body) |

### participantBodies (CRITICAL)
When doing Cut or Join near other bodies, you MUST specify which body to target:
```python
ext_input.participantBodies = [target_body]  # Python list, NOT ObjectCollection!
```
Using `ObjectCollection` causes `TypeError`. Using no participant bodies causes accidental merging or cutting of adjacent bodies.

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

## Joinery Rules

### Mortise and Tenon
- Mortise sketch profiles must be positioned INSIDE the target body. Drawing mortises outside causes "No target body found to cut" errors.
- At corners where tenons from two directions enter the same post, STAGGER them in Z to prevent collision:
  ```python
  long_tenon_z  = "(rail_height - 2 * tenon_height) / 3"
  short_tenon_z = "2 * (rail_height - 2 * tenon_height) / 3 + tenon_height"
  ```

### Tongue and Groove
- Frame grooves: centered on rail thickness, receive slat tongues
- Inter-slat T&G: one side groove, other side tongue, consistent across all slats
- Edge tongues: first/last slat gets a tongue into the leg/post groove

### Gap Filling
When `floor(space / element_width)` leaves a remainder, add a gap-filling piece:
- Width = `space - element_width * count` (parametric expression)
- Position = `offset + element_width * count`
- Use `participantBodies` on ALL cut/join operations
- Only build if gap > 0.01 cm at script time
- Mirror gap features to opposite side

## Component Structure Template
```
Root
  +-- Posts/Legs      (build 1, mirror to all corners)
  +-- LongRails       (build front pair, mirror to back)
  +-- ShortRails      (build side pair, mirror to opposite)
  +-- Panels/Slats    (template per orientation, mirror + independent patterns)
  +-- Top/Bottom      (single panel)
```

## Construction Planes
All positioned with parametric offset expressions. Common planes:
- Body Z (visible area bottom)
- Upper/Lower rail planes
- Tongue planes (rail height minus groove depth)
- Midplanes for X and Y mirror operations

## Verification Checklist
1. Component tree shows logical grouping
2. Timeline shows: build features > mirror, template > mirror > pattern
3. Change a major dimension > verify ALL sides update correctly
4. Change element width > verify counts increase/decrease on all sides
5. Section Analysis > verify joinery alignment
6. Verify no overlapping joints at corners

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
