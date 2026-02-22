# Spline Joint

## Overview

A **spline joint** uses a thin strip of wood (the spline) inserted into matching slots cut across a joint line. Splines reinforce butt joints and miters by adding cross-grain strength and alignment.

**When to use:** Reinforcing miter joints, edge-to-edge joints, picture frames, box miters. Splines can be functional (hidden) or decorative (contrasting wood, visible on the surface). Often paired with [miter joints](miter-joint.md).

**Strength:** Medium. The spline bridges the joint line with cross-grain material, significantly strengthening an otherwise weak miter or butt joint. Strength depends on spline thickness and depth.

## Variants

| Variant | Description |
|---------|-------------|
| Hidden spline | Slot doesn't reach the visible face, spline invisible when assembled |
| Through spline | Slot runs full width, spline visible on both edges |
| Decorative spline | Contrasting wood, intentionally visible (often on miter corners) |
| Multiple splines | Two or more parallel splines for wider boards |

## Parameters

| Parameter | Expression | Unit | Description |
|-----------|------------|------|-------------|
| `sp_thick` | `"0.125 in"` | `"in"` | Spline thickness (= slot width) |
| `sp_depth` | `"0.75 in"` | `"in"` | Slot depth in each piece (spline goes into both) |
| `sp_length` | `"3 in"` | `"in"` | Spline length along the joint (or full board width for through) |
| `sp_offset` | `"0 in"` | `"in"` | Offset from joint center (0 = centered on joint line) |
| `sp_count` | `"1"` | `""` | Number of splines across the joint |
| `sp_spacing` | `"1.5 in"` | `"in"` | Spacing between multiple splines |

```python
params = design.userParameters
params.add("sp_thick", adsk.core.ValueInput.createByString("0.125 in"), "in", "Spline thickness")
params.add("sp_depth", adsk.core.ValueInput.createByString("0.75 in"), "in", "Spline slot depth")
params.add("sp_length", adsk.core.ValueInput.createByString("3 in"), "in", "Spline length")
params.add("sp_offset", adsk.core.ValueInput.createByString("0 in"), "in", "Spline offset from center")
params.add("sp_count", adsk.core.ValueInput.createByString("1"), "", "Number of splines")
params.add("sp_spacing", adsk.core.ValueInput.createByString("1.5 in"), "in", "Spacing between splines")
```

## Derived Parameters

| Parameter | Expression | Description |
|-----------|------------|-------------|
| `sp_total_depth` | `sp_depth * 2` | Total spline width (both sides) |
| `sp_slot_start` | `sp_offset - sp_thick / 2` | Slot edge offset from joint center |

```python
params.add("sp_total_depth", adsk.core.ValueInput.createByString("sp_depth * 2"), "in", "Total spline span")
```

## Geometry Workflow

### Spline Slot (per piece)

1. **Plane** — The mating face of the piece (the face at the joint line).
2. **Sketch** — Rectangle:
   - Width = `sp_thick` (slot width)
   - Height = `sp_length` (or full board width for through spline)
   - Centered on the face thickness
3. **Extrude** — Cut by `sp_depth`:
   - Operation: `CutFeatureOperation`
   - `participantBodies = [piece_body]`
4. **Repeat** — Cut matching slot in the mating piece.

### Spline Body (optional, for visualization)

1. **Plane** — Joint line plane.
2. **Sketch** — Rectangle: width = `sp_thick`, height = `sp_length`.
3. **Extrude** — New body by `sp_total_depth`, centered on joint line:
   - Operation: `NewBodyFeatureOperation`
   - Use symmetric extent: `sp_depth` in each direction

### Multiple Splines

Pattern the slot cut feature with `RectangularPatternFeature`:
- Count: `sp_count`
- Spacing: `sp_spacing`

## Replication

- **Picture frame (4 mitered corners):** Build spline slot on one corner, mirror to all 4.
- **Long edge joint:** Pattern splines along the joint length.

## Common Pitfalls

| Error | Cause | Fix |
|-------|-------|-----|
| Spline too thick for slot | `sp_thick` in spline body doesn't match slot width | Reference same `sp_thick` parameter |
| Slot visible on face | `sp_length` equals or exceeds board width | Reduce `sp_length` for hidden spline, or accept through spline |
| Slots don't align | Different sketch planes for each piece | Both slots cut perpendicular to the same joint face |
| Spline bottoms out | `sp_depth` too shallow for spline width | Ensure spline body height < `sp_depth * 2` |

## Example Snippet

Spline slot in a mitered corner:

```python
# -- Spline slot in piece A (miter face) --
miter_face = body_a.faces.item(0)  # the 45-degree miter face
sk = comp.sketches.add(miter_face)

# Slot rectangle centered on face
p1 = adsk.core.Point3D.create(0, 0, 0)
p2 = adsk.core.Point3D.create(1, 1, 0)
rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)

# Slot width
d_w = sk.sketchDimensions.addDistanceDimension(
    rect.item(0).startSketchPoint, rect.item(0).endSketchPoint,
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_w.parameter.expression = "sp_thick"

# Slot length
d_h = sk.sketchDimensions.addDistanceDimension(
    rect.item(1).startSketchPoint, rect.item(1).endSketchPoint,
    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_h.parameter.expression = "sp_length"

# Center slot on face
d_center = sk.sketchDimensions.addDistanceDimension(
    rect.item(0).startSketchPoint, sk.originPoint,
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_center.parameter.expression = "sp_offset - sp_thick / 2"

# Cut slot
prof = sk.profiles.item(0)
ext_input = comp.features.extrudeFeatures.createInput(prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByString("sp_depth"))
ext_input.participantBodies = [body_a]
comp.features.extrudeFeatures.add(ext_input)

# Repeat matching slot in piece B (same parameters, miter face of B)
```

**See also:** [miter-joint.md](miter-joint.md) for the base miter cut that splines typically reinforce.
