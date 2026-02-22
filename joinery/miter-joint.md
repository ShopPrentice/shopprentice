# Miter Joint

## Overview

A **miter joint** cuts both pieces at an angle (typically 45 degrees) so the end grain is hidden at the joint line. Miters create clean corners but have minimal mechanical strength without reinforcement.

**When to use:** Picture frames, trim/molding, box corners where hidden end grain is desired, decorative edges. Almost always paired with reinforcement — splines, dowels, biscuits, or glue alone for small pieces.

**Strength:** Low without reinforcement. The 45-degree faces are end-grain-to-end-grain which glues poorly. Add [spline](spline-joint.md) or [dowel](dowel-joint.md) reinforcement for structural miters.

## Variants

| Variant | Description |
|---------|-------------|
| Flat miter | Both pieces mitered on their faces (picture frame style) |
| Edge miter | Mitered along the edge (box corners) |
| Compound miter | Angled in two planes (crown molding) |
| Splined miter | Miter with spline reinforcement — see [spline-joint.md](spline-joint.md) |

## Parameters

| Parameter | Expression | Unit | Description |
|-----------|------------|------|-------------|
| `mj_angle` | `"45 deg"` | `"deg"` | Miter angle (45 deg for 90-degree corners) |
| `mj_thick` | `"0.75 in"` | `"in"` | Board thickness |
| `mj_width` | `"3.5 in"` | `"in"` | Board width |
| `mj_length` | `"24 in"` | `"in"` | Board length (to miter point) |

```python
params = design.userParameters
params.add("mj_angle", adsk.core.ValueInput.createByString("45 deg"), "deg", "Miter angle")
params.add("mj_thick", adsk.core.ValueInput.createByString("0.75 in"), "in", "Board thickness")
params.add("mj_width", adsk.core.ValueInput.createByString("3.5 in"), "in", "Board width")
params.add("mj_length", adsk.core.ValueInput.createByString("24 in"), "in", "Board length to miter point")
```

## Derived Parameters

| Parameter | Expression | Description |
|-----------|------------|-------------|
| `mj_cut_len` | `mj_thick / tan(mj_angle)` | Length of the angled cut face |
| `mj_outside_len` | `mj_length` | Outside (long point) measurement |
| `mj_inside_len` | `mj_length - mj_cut_len` | Inside (short point) measurement |

```python
params.add("mj_cut_len", adsk.core.ValueInput.createByString("mj_thick / tan(mj_angle)"), "in", "Miter cut face length")
params.add("mj_inside_len", adsk.core.ValueInput.createByString("mj_length - mj_cut_len"), "in", "Inside miter length")
```

## Geometry Workflow

### Flat Miter (e.g., picture frame)

**Approach:** Build the board as a full rectangle, then cut the miter angle at each end.

1. **Board body:**
   - Sketch rectangle on XY plane: width = `mj_width`, length = `mj_length`
   - Extrude by `mj_thick` as `NewBodyFeatureOperation`

2. **Miter cut (one end):**
   - **Plane** — Face of the board at the end to be mitered.
   - **Sketch** — Draw a triangle representing the waste:
     - Start at the outside corner
     - Angled line at `mj_angle` to the inside face
     - Close the triangle along the board end
   - **Extrude** — Cut through the full board width:
     - Operation: `CutFeatureOperation`
     - `participantBodies = [board_body]`

3. **Repeat** — Mirror or build the miter cut on the opposite end.

### Edge Miter (box corner)

1. Build the board body as above.
2. Create an angled construction plane at `mj_angle` to the edge.
3. Sketch the waste triangle on the end face.
4. Extrude cut along the board width.

## Replication

- **Picture frame (4 pieces):** Build one mitered piece, then create 3 copies rotated 90/180/270 degrees. Each piece is a separate body with its own miter cuts.
- **Box with mitered corners:** Build one side with mitered edges, pattern or mirror for the remaining sides.

## Common Pitfalls

| Error | Cause | Fix |
|-------|-------|-----|
| Gap at miter line | Angle not exactly 45 degrees | Use parametric `mj_angle` expression, verify with `45 deg` |
| Miter cuts wrong direction | Triangle sketch oriented incorrectly | Verify waste triangle is on the correct side of the cut line |
| Joint weak without reinforcement | End-grain-to-end-grain glue surface | Add [spline](spline-joint.md) or [dowel](dowel-joint.md) reinforcement |
| Inside/outside length confused | Measuring from wrong miter point | `mj_length` = outside (long point), derive `mj_inside_len` |

## Example Snippet

Miter cut on one end of a frame piece:

```python
# -- Miter cut at end of frame piece --
# Build the board body first (full rectangle)
xy_plane = comp.xYConstructionPlane
sk_board = comp.sketches.add(xy_plane)
p1 = adsk.core.Point3D.create(0, 0, 0)
p2 = adsk.core.Point3D.create(10, 1, 0)  # approximate
rect = sk_board.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)

d_len = sk_board.sketchDimensions.addDistanceDimension(
    rect.item(0).startSketchPoint, rect.item(0).endSketchPoint,
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_len.parameter.expression = "mj_length"

d_w = sk_board.sketchDimensions.addDistanceDimension(
    rect.item(1).startSketchPoint, rect.item(1).endSketchPoint,
    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_w.parameter.expression = "mj_width"

prof = sk_board.profiles.item(0)
ext_input = comp.features.extrudeFeatures.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByString("mj_thick"))
board_feat = comp.features.extrudeFeatures.add(ext_input)
board_body = board_feat.bodies.item(0)

# -- Miter cut (waste triangle at one end) --
end_face = board_body.faces.item(0)  # end face
sk_miter = comp.sketches.add(end_face)

lines = sk_miter.sketchCurves.sketchLines
# Triangle: outside corner -> angled cut -> inside corner -> back to start
pt_outside = adsk.core.Point3D.create(0, 0, 0)
pt_inside = adsk.core.Point3D.create(0.75, 0, 0)  # approximate
pt_corner = adsk.core.Point3D.create(0, 0, 0)

line1 = lines.addByTwoPoints(pt_outside, pt_inside)  # angled cut
line2 = lines.addByTwoPoints(pt_inside, pt_corner)   # along end
line3 = lines.addByTwoPoints(pt_corner, pt_outside)   # close triangle

# Constrain miter angle
d_angle = sk_miter.sketchDimensions.addAngularDimension(line1, line3, adsk.core.Point3D.create(0, 0, 0))
d_angle.parameter.expression = "mj_angle"

# Cut through board width
waste_prof = sk_miter.profiles.item(0)
ext_miter = comp.features.extrudeFeatures.createInput(waste_prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
ext_miter.setDistanceExtent(False, adsk.core.ValueInput.createByString("mj_width"))
ext_miter.participantBodies = [board_body]
comp.features.extrudeFeatures.add(ext_miter)
```

**See also:** [spline-joint.md](spline-joint.md) for adding spline reinforcement to mitered joints.
