# Lap Joint

## Overview

A **lap joint** removes material from one or both mating pieces so they overlap and sit flush. The large glue surface area provides good strength for flat frame assemblies.

**When to use:** Frame constructions, flat panel frames, cross braces, workbench stretchers, lattice/grid structures. Lap joints are simpler to model than mortise-and-tenon but provide less mechanical interlock.

**Strength:** Medium. Relies on glue surface area. The half-lap removes 50% of material at the joint, creating a potential weak point under tension, but the wide face-to-face contact provides good shear resistance.

## Variants

| Variant | Description |
|---------|-------------|
| Half-lap | Both pieces notched halfway, flush on both faces |
| Cross-lap | Pieces cross at an angle (typically 90 deg), both notched |
| T-lap | One piece ends at the middle of the other |
| End lap | Both pieces notched at their ends, forming an L |
| Mitered half-lap | Half-lap with a 45-degree miter on the visible face |

## Parameters

| Parameter | Expression | Unit | Description |
|-----------|------------|------|-------------|
| `lj_width_a` | `"3.5 in"` | `"in"` | Width of piece A |
| `lj_width_b` | `"3.5 in"` | `"in"` | Width of piece B |
| `lj_thick` | `"1.5 in"` | `"in"` | Common thickness of both pieces |
| `lj_depth` | `"lj_thick / 2"` | `"in"` | Notch depth (half thickness for flush lap) |
| `lj_offset` | `"12 in"` | `"in"` | Distance from reference edge to lap position |

```python
params = design.userParameters
params.add("lj_width_a", adsk.core.ValueInput.createByString("3.5 in"), "in", "Piece A width")
params.add("lj_width_b", adsk.core.ValueInput.createByString("3.5 in"), "in", "Piece B width")
params.add("lj_thick", adsk.core.ValueInput.createByString("1.5 in"), "in", "Common thickness")
params.add("lj_depth", adsk.core.ValueInput.createByString("lj_thick / 2"), "in", "Lap notch depth")
params.add("lj_offset", adsk.core.ValueInput.createByString("12 in"), "in", "Lap offset from edge")
```

## Derived Parameters

| Parameter | Expression | Description |
|-----------|------------|-------------|
| `lj_depth` | `lj_thick / 2` | Half-thickness for flush surface |
| `lj_notch_len_a` | `lj_width_b` | Notch in A matches width of B |
| `lj_notch_len_b` | `lj_width_a` | Notch in B matches width of A |

```python
params.add("lj_notch_len_a", adsk.core.ValueInput.createByString("lj_width_b"), "in", "Notch length in piece A")
params.add("lj_notch_len_b", adsk.core.ValueInput.createByString("lj_width_a"), "in", "Notch length in piece B")
```

## Geometry Workflow

### Cross-Lap (both pieces notched)

1. **Piece A notch:**
   - **Plane** — Top face of piece A
   - **Sketch** — Rectangle: width = `lj_notch_len_a`, positioned at `lj_offset` along piece A's length
   - **Extrude** — Cut by `lj_depth` into piece A
   - `participantBodies = [body_a]`

2. **Piece B notch:**
   - **Plane** — Bottom face of piece B (opposite side from A's notch)
   - **Sketch** — Rectangle: width = `lj_notch_len_b`, positioned at crossing point
   - **Extrude** — Cut by `lj_depth` into piece B
   - `participantBodies = [body_b]`

### T-Lap

1. **Cross piece** — Cut a notch as above at the meeting point.
2. **End piece** — Cut a notch at the end of the piece (no offset, starts at piece end).

## Replication

- **Lattice/grid:** Build one cross-lap intersection, then use `RectangularPatternFeature` in both X and Y.
- **Symmetric frames:** Build lap joints on one side, mirror template, independent patterns per side.

## Common Pitfalls

| Error | Cause | Fix |
|-------|-------|-----|
| Pieces not flush | `lj_depth` doesn't equal half thickness | Set `lj_depth = lj_thick / 2` |
| Notch too wide/narrow | Notch width not linked to mating piece | Use `lj_width_b` for notch in A and vice versa |
| Cut goes through both pieces | Missing `participantBodies` | Specify `[body_a]` or `[body_b]` per cut |
| T-lap end piece too short | Notch extends past piece end | Position sketch so notch starts at piece end |

## Example Snippet

Cross-lap joint between two rails:

```python
# -- Cross-lap: notch in piece A --
sk_a = comp.sketches.add(body_a.faces.item(0))  # top face
p1 = adsk.core.Point3D.create(0, 0, 0)
p2 = adsk.core.Point3D.create(1, 1, 0)
rect_a = sk_a.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)

# Position notch at crossing point
d_pos = sk_a.sketchDimensions.addDistanceDimension(
    rect_a.item(0).startSketchPoint, sk_a.originPoint,
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_pos.parameter.expression = "lj_offset - lj_notch_len_a / 2"

d_w = sk_a.sketchDimensions.addDistanceDimension(
    rect_a.item(0).startSketchPoint, rect_a.item(0).endSketchPoint,
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_w.parameter.expression = "lj_notch_len_a"

d_h = sk_a.sketchDimensions.addDistanceDimension(
    rect_a.item(1).startSketchPoint, rect_a.item(1).endSketchPoint,
    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_h.parameter.expression = "lj_width_a"

# Cut notch
prof = sk_a.profiles.item(0)
ext_input = comp.features.extrudeFeatures.createInput(prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByString("lj_depth"))
ext_input.participantBodies = [body_a]
comp.features.extrudeFeatures.add(ext_input)

# -- Cross-lap: notch in piece B (from opposite face) --
sk_b = comp.sketches.add(body_b.faces.item(1))  # bottom face
p1 = adsk.core.Point3D.create(0, 0, 0)
p2 = adsk.core.Point3D.create(1, 1, 0)
rect_b = sk_b.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)

d_pos_b = sk_b.sketchDimensions.addDistanceDimension(
    rect_b.item(0).startSketchPoint, sk_b.originPoint,
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_pos_b.parameter.expression = "lj_offset - lj_notch_len_b / 2"

d_w_b = sk_b.sketchDimensions.addDistanceDimension(
    rect_b.item(0).startSketchPoint, rect_b.item(0).endSketchPoint,
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_w_b.parameter.expression = "lj_notch_len_b"

d_h_b = sk_b.sketchDimensions.addDistanceDimension(
    rect_b.item(1).startSketchPoint, rect_b.item(1).endSketchPoint,
    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_h_b.parameter.expression = "lj_width_b"

prof_b = sk_b.profiles.item(0)
ext_input_b = comp.features.extrudeFeatures.createInput(prof_b, adsk.fusion.FeatureOperations.CutFeatureOperation)
ext_input_b.setDistanceExtent(False, adsk.core.ValueInput.createByString("lj_depth"))
ext_input_b.participantBodies = [body_b]
comp.features.extrudeFeatures.add(ext_input_b)
```
