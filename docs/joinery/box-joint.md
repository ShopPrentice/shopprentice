# Box Joint

## Template

Use `from helpers.templates import finger_joint` for box/finger joints. The template handles sketch geometry, JOIN/CUT operations, mirror/pattern replication for 1/2/4-corner boxes, and supports any joint axis orientation.

```python
from helpers.templates import finger_joint

fp = finger_joint.define_params(params, prefix="fj",
    finger_w="0.375 in", finger_count="8",
    joint_h_expr="box_height", thick_expr="board_thick")

finger_joint.box(comp, front, left,
                 x_mid, y_mid, thick_expr="board_thick",
                 right=right, back=back,
                 prefix="fj", name="FJ", ev=ctx.ev)
```

## Overview

A **box joint** (finger joint) uses interlocking rectangular fingers cut into the ends of two boards. The alternating pins and slots create a large glue surface area and strong mechanical interlock.

**When to use:** Box and drawer construction, decorative corners, any right-angle joint where visible end grain is acceptable or desired. Box joints are easier to model parametrically than dovetails while providing comparable strength.

**Strength:** High. The interlocking fingers resist pulling apart in all directions, and the large face-grain-to-face-grain glue surface provides excellent bond strength.

**Typical sizing:** Finger width < board thickness (narrow fingers). Common: 3/8" fingers on 3/4" stock.

## Variants

| Variant | Description |
|---------|-------------|
| Standard box joint | Equal-width fingers and slots |
| Decorative box joint | Contrasting wood or varied finger widths |
| Double box joint | Two rows of fingers (for thick stock) |

## Parameters

| Parameter | Expression | Unit | Description |
|-----------|------------|------|-------------|
| `bj_finger_w` | `"0.375 in"` | `"in"` | Width of each finger/slot |
| `bj_thick` | `"0.75 in"` | `"in"` | Board thickness (= finger length) |
| `bj_board_h` | `"6 in"` | `"in"` | Board height (joint runs along this edge) |
| `bj_n_fingers` | `"floor(bj_board_h / bj_finger_w)"` | `""` | Number of fingers (auto-calculated) |

```python
params = design.userParameters
params.add("bj_finger_w", adsk.core.ValueInput.createByString("0.375 in"), "in", "Finger/slot width")
params.add("bj_thick", adsk.core.ValueInput.createByString("0.75 in"), "in", "Board thickness")
params.add("bj_board_h", adsk.core.ValueInput.createByString("6 in"), "in", "Board height")
params.add("bj_n_fingers", adsk.core.ValueInput.createByString("floor(bj_board_h / bj_finger_w)"), "", "Number of fingers")
```

## Derived Parameters

| Parameter | Expression | Description |
|-----------|------------|-------------|
| `bj_n_fingers` | `floor(bj_board_h / bj_finger_w)` | Auto-count of fingers |
| `bj_n_slots_a` | `floor(bj_n_fingers / 2)` | Slots cut in piece A (every other finger) |
| `bj_remainder` | `bj_board_h - bj_n_fingers * bj_finger_w` | Leftover at top edge |

```python
params.add("bj_n_slots_a", adsk.core.ValueInput.createByString("floor(bj_n_fingers / 2)"), "", "Slots in piece A")
params.add("bj_remainder", adsk.core.ValueInput.createByString("bj_board_h - bj_n_fingers * bj_finger_w"), "in", "Remainder at top")
```

## Geometry Workflow

Box joints use a slot-cutting approach: cut slots in piece A at even positions, cut slots in piece B at odd positions.

### Piece A Slots

1. **Plane** — End face of piece A.
2. **Sketch** — Rectangle: width = `bj_thick` (full board thickness), height = `bj_finger_w`.
3. **Constrain** — Position at the bottom edge (first slot at index 0).
4. **Extrude** — Cut by `bj_thick`:
   - Operation: `CutFeatureOperation`
   - `participantBodies = [body_a]`
5. **Pattern** — `RectangularPatternFeature` along the height axis:
   - Count: `bj_n_slots_a`
   - Spacing: `bj_finger_w * 2` (skip every other position)

### Piece B Slots

1. Same as above, but offset by `bj_finger_w` (start at index 1 instead of 0).
2. Pattern count: `floor((bj_n_fingers - 1) / 2)`

## Replication

- **Four-corner box:** Build A-side and B-side slots on one corner, mirror to opposite corners. Each corner pair shares the same pattern.
- **Pattern the slot feature** rather than individual bodies — the pattern replicates the cut operation.

## Common Pitfalls

| Error | Cause | Fix |
|-------|-------|-----|
| Fingers don't interlock | Both pieces cut at same positions | Offset piece B by `bj_finger_w` |
| Gap at top/bottom | `bj_board_h` not evenly divisible | Use `bj_remainder` parameter for gap-fill piece |
| Pattern cuts wrong body | Missing `participantBodies` on pattern seed | Set `participantBodies` before patterning |
| Fingers too loose/tight | `bj_finger_w` mismatch between pieces | Both pieces reference same `bj_finger_w` parameter |

## Example Snippet

Box joint slots on one corner (piece A):

```python
# -- Box joint: cut slots in piece A --
end_face_a = body_a.faces.item(0)  # end face
sk = comp.sketches.add(end_face_a)

# First slot rectangle
p1 = adsk.core.Point3D.create(0, 0, 0)
p2 = adsk.core.Point3D.create(1, 1, 0)
rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)

# Constrain: full thickness width, one finger height, at bottom
d_w = sk.sketchDimensions.addDistanceDimension(
    rect.item(0).startSketchPoint, rect.item(0).endSketchPoint,
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_w.parameter.expression = "bj_thick"

d_h = sk.sketchDimensions.addDistanceDimension(
    rect.item(1).startSketchPoint, rect.item(1).endSketchPoint,
    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_h.parameter.expression = "bj_finger_w"

# Position at bottom edge
d_pos = sk.sketchDimensions.addDistanceDimension(
    rect.item(0).startSketchPoint, sk.originPoint,
    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_pos.parameter.expression = "0 in"

# Cut slot
prof = sk.profiles.item(0)
ext_input = comp.features.extrudeFeatures.createInput(prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByString("bj_thick"))
ext_input.participantBodies = [body_a]
slot_feat = comp.features.extrudeFeatures.add(ext_input)

# Pattern slots along height (every other position)
pat_feats = comp.features.rectangularPatternFeatures
body_coll = adsk.core.ObjectCollection.create()
body_coll.add(slot_feat)
pat_input = pat_feats.createInput(body_coll,
    comp.yConstructionAxis,
    adsk.core.ValueInput.createByString("bj_n_slots_a"),
    adsk.core.ValueInput.createByString("bj_finger_w * 2"),
    adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
pat_feats.add(pat_input)
```
