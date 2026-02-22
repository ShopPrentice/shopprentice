# Dovetail

## Overview

A **dovetail joint** uses trapezoidal (fan-shaped) pins and tails that interlock to create an extremely strong mechanical joint. The angled faces resist pulling apart, making dovetails the premier joint for drawer construction and fine boxes.

**When to use:** Drawer fronts and sides, premium boxes, visible joints where craftsmanship is on display. Dovetails are the strongest corner joint and resist pulling forces along the tail direction without glue.

**Strength:** Very high. The trapezoidal geometry creates a mechanical lock — tails cannot pull out of pins. Combined with glue, dovetails are the strongest wood-to-wood corner joint.

## Variants

| Variant | Description |
|---------|-------------|
| Through dovetail | Tails visible on both faces — classic drawer back joint |
| Half-blind dovetail | Tails hidden on one face — drawer front joint |
| Sliding dovetail | Dovetail-shaped tongue slides into a matching groove (shelf-to-case) |
| Single dovetail | One large tail, used for structural T-connections |

## Parameters

| Parameter | Expression | Unit | Description |
|-----------|------------|------|-------------|
| `dt_angle` | `"8 deg"` | `"deg"` | Dovetail angle (7-14 deg; 8 for hardwood, 14 for softwood) |
| `dt_tail_w` | `"0.75 in"` | `"in"` | Tail width at the wide end |
| `dt_pin_w` | `"0.25 in"` | `"in"` | Pin width (narrow part between tails) |
| `dt_thick` | `"0.75 in"` | `"in"` | Board thickness (= tail/pin length) |
| `dt_board_h` | `"6 in"` | `"in"` | Board height (joint runs along this edge) |
| `dt_n_tails` | `"floor(dt_board_h / (dt_tail_w + dt_pin_w))"` | `""` | Number of tails |

```python
params = design.userParameters
params.add("dt_angle", adsk.core.ValueInput.createByString("8 deg"), "deg", "Dovetail angle")
params.add("dt_tail_w", adsk.core.ValueInput.createByString("0.75 in"), "in", "Tail width (wide end)")
params.add("dt_pin_w", adsk.core.ValueInput.createByString("0.25 in"), "in", "Pin width")
params.add("dt_thick", adsk.core.ValueInput.createByString("0.75 in"), "in", "Board thickness")
params.add("dt_board_h", adsk.core.ValueInput.createByString("6 in"), "in", "Board height")
params.add("dt_n_tails", adsk.core.ValueInput.createByString("floor(dt_board_h / (dt_tail_w + dt_pin_w))"), "", "Number of tails")
```

## Derived Parameters

| Parameter | Expression | Description |
|-----------|------------|-------------|
| `dt_n_tails` | `floor(dt_board_h / (dt_tail_w + dt_pin_w))` | Parametric tail count |
| `dt_pitch` | `dt_tail_w + dt_pin_w` | Center-to-center distance between tails |
| `dt_narrow_w` | `dt_tail_w - 2 * dt_thick * tan(dt_angle)` | Tail width at the narrow end |
| `dt_half_pin` | `dt_pin_w / 2` | Half-pin at top and bottom edges |

```python
params.add("dt_pitch", adsk.core.ValueInput.createByString("dt_tail_w + dt_pin_w"), "in", "Tail pitch")
params.add("dt_narrow_w", adsk.core.ValueInput.createByString("dt_tail_w - 2 * dt_thick * tan(dt_angle)"), "in", "Tail narrow width")
params.add("dt_half_pin", adsk.core.ValueInput.createByString("dt_pin_w / 2"), "in", "Half-pin width")
```

## Geometry Workflow

Dovetails require trapezoidal sketch profiles rather than simple rectangles. The key is the angled lines that create the dovetail shape.

### Through Dovetail

**Tail board (cut the sockets between tails in the pin board):**

1. **Plane** — End face of the pin board.
2. **Sketch** — For each tail socket, draw a trapezoid:
   - Bottom edge = `dt_tail_w` (wide end of tail)
   - Top edge = `dt_narrow_w` (narrow end)
   - Height = `dt_thick`
   - Sides angled at `dt_angle` from vertical
3. **Extrude** — Cut by `dt_thick`:
   - Operation: `CutFeatureOperation`
   - `participantBodies = [pin_board]`
4. **Pattern** — `RectangularPatternFeature` along the board height:
   - Count: `dt_n_tails`
   - Spacing: `dt_pitch`

**Pin board (cut the waste between pins in the tail board):**

1. **Plane** — End face of the tail board.
2. **Sketch** — For each pin socket, draw the inverse trapezoid:
   - This is the space left between the tails
3. **Extrude** — Cut by `dt_thick`:
   - `participantBodies = [tail_board]`
4. **Pattern** — Same count and spacing as tails.

### Half-Blind Dovetail

Same approach, but the tail socket cut depth is less than `dt_thick`, leaving material on the front face of the pin board to hide the joint.

## Replication

- **Drawer (4 corners):** Build one dovetail corner, mirror for the opposite corner. Front corners may use half-blind, back corners through dovetails.
- **Pattern the trapezoidal cut** — each socket is one pattern instance.

## Common Pitfalls

| Error | Cause | Fix |
|-------|-------|-----|
| Tails don't interlock | Tail and socket angles don't match | Both reference same `dt_angle` parameter |
| Gap between pins and tails | `dt_narrow_w` not derived correctly | Use `dt_tail_w - 2 * dt_thick * tan(dt_angle)` |
| Dovetail angle too steep | Angle > 14 degrees | Keep 7-14 deg; 8 deg for hardwood |
| Pattern misaligned | Pitch doesn't match tail + pin width | Set spacing = `dt_pitch` = `dt_tail_w + dt_pin_w` |
| Half-blind depth wrong | Socket deeper than board thickness | `dt_socket_depth < dt_thick` for half-blind |

## Example Snippet

Through dovetail — cutting tail sockets in the pin board:

```python
# -- Dovetail: cut tail sockets in pin board --
pin_end = pin_board.faces.item(0)  # end face
sk = comp.sketches.add(pin_end)

lines = sk.sketchCurves.sketchLines

# First tail socket (trapezoid)
# Points approximate — constrained parametrically below
pt1 = adsk.core.Point3D.create(0, 0.25, 0)      # bottom-left (narrow end)
pt2 = adsk.core.Point3D.create(0.75, 0.15, 0)    # top-left (wide end)
pt3 = adsk.core.Point3D.create(0.75, 0.90, 0)    # top-right (wide end)
pt4 = adsk.core.Point3D.create(0, 0.80, 0)        # bottom-right (narrow end)

l1 = lines.addByTwoPoints(pt1, pt2)  # left angled side
l2 = lines.addByTwoPoints(pt2, pt3)  # top (wide end = tail width)
l3 = lines.addByTwoPoints(pt3, pt4)  # right angled side
l4 = lines.addByTwoPoints(pt4, pt1)  # bottom (narrow end)

# Constrain wide end (tail width)
d_wide = sk.sketchDimensions.addDistanceDimension(
    l2.startSketchPoint, l2.endSketchPoint,
    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_wide.parameter.expression = "dt_tail_w"

# Constrain narrow end
d_narrow = sk.sketchDimensions.addDistanceDimension(
    l4.startSketchPoint, l4.endSketchPoint,
    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_narrow.parameter.expression = "dt_narrow_w"

# Constrain depth (board thickness)
d_depth = sk.sketchDimensions.addDistanceDimension(
    l1.startSketchPoint, l1.endSketchPoint,
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_depth.parameter.expression = "dt_thick"

# Constrain dovetail angle
d_angle = sk.sketchDimensions.addAngularDimension(
    l1, l4,
    adsk.core.Point3D.create(0, 0, 0))
d_angle.parameter.expression = "90 deg - dt_angle"

# Position first socket (half-pin offset from edge)
d_pos = sk.sketchDimensions.addDistanceDimension(
    l4.startSketchPoint, sk.originPoint,
    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_pos.parameter.expression = "dt_half_pin"

# Cut socket
prof = sk.profiles.item(0)
ext_input = comp.features.extrudeFeatures.createInput(prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByString("dt_thick"))
ext_input.participantBodies = [pin_board]
socket_feat = comp.features.extrudeFeatures.add(ext_input)

# Pattern sockets along board height
pat_feats = comp.features.rectangularPatternFeatures
feat_coll = adsk.core.ObjectCollection.create()
feat_coll.add(socket_feat)
pat_input = pat_feats.createInput(feat_coll,
    comp.yConstructionAxis,
    adsk.core.ValueInput.createByString("dt_n_tails"),
    adsk.core.ValueInput.createByString("dt_pitch"),
    adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
pat_feats.add(pat_input)
```

**See also:** [box-joint.md](box-joint.md) for a simpler interlocking alternative.
