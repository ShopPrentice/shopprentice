# Dado & Rabbet

## Overview

A **dado** is a rectangular channel cut across the grain of a board to receive the edge of another piece. A **rabbet** is an L-shaped step cut along the edge of a board. Both are cut joints — material is removed from the host to accept the mating piece.

**When to use:** Shelving (dados for shelf ends), case construction (rabbets for back panels), drawer bottoms, bookcase dividers. Dados and rabbets provide alignment and moderate mechanical strength with glue.

**Strength:** Medium. The channel/step resists lateral movement and provides glue surface area. Not as strong as interlocking joints (dovetails, box joints) but excellent for panel-in-frame constructions.

## Variants

| Variant | Description |
|---------|-------------|
| Through dado | Channel runs full width of host board |
| Stopped (blind) dado | Channel stops before the front edge, hiding the joint |
| Rabbet | L-step on edge, typically for back panels |
| Double rabbet | Both mating pieces rabbeted, forming an overlap |

## Parameters

| Parameter | Expression | Unit | Description |
|-----------|------------|------|-------------|
| `dr_width` | `"0.75 in"` | `"in"` | Width of dado/rabbet (matches mating piece thickness) |
| `dr_depth` | `"0.375 in"` | `"in"` | Depth of cut (typically 1/3 to 1/2 host thickness) |
| `dr_host_thick` | `"0.75 in"` | `"in"` | Thickness of host board |
| `dr_offset` | `"6 in"` | `"in"` | Distance from reference edge to dado center |
| `dr_stop_inset` | `"0.5 in"` | `"in"` | Inset from front edge for stopped dados (0 = through) |

```python
params = design.userParameters
params.add("dr_width", adsk.core.ValueInput.createByString("0.75 in"), "in", "Dado/rabbet width")
params.add("dr_depth", adsk.core.ValueInput.createByString("0.375 in"), "in", "Dado/rabbet depth")
params.add("dr_host_thick", adsk.core.ValueInput.createByString("0.75 in"), "in", "Host board thickness")
params.add("dr_offset", adsk.core.ValueInput.createByString("6 in"), "in", "Dado offset from edge")
params.add("dr_stop_inset", adsk.core.ValueInput.createByString("0.5 in"), "in", "Stop inset for blind dado")
```

## Derived Parameters

| Parameter | Expression | Description |
|-----------|------------|-------------|
| `dr_rabbet_lip` | `dr_host_thick - dr_depth` | Remaining material at rabbet edge |

```python
params.add("dr_rabbet_lip", adsk.core.ValueInput.createByString("dr_host_thick - dr_depth"), "in", "Rabbet lip thickness")
```

## Geometry Workflow

### Through Dado

1. **Plane** — Select the face of the host board where the dado opens (typically the inner face).
2. **Sketch** — Draw a rectangle spanning the full board width:
   - One edge at `dr_offset - dr_width / 2`
   - Opposite edge at `dr_offset + dr_width / 2`
   - Extend across the full board dimension
3. **Extrude** — Cut into the host board by `dr_depth`:
   - Operation: `CutFeatureOperation`
   - Direction: into the board
   - `participantBodies = [host_body]`

### Rabbet

1. **Plane** — Select the face of the host board.
2. **Sketch** — Draw a rectangle along the board edge:
   - Width = `dr_width` from the edge inward
   - Length = full board length
3. **Extrude** — Cut by `dr_depth`:
   - Operation: `CutFeatureOperation`
   - `participantBodies = [host_body]`

## Replication

- **Multiple shelf dados:** Use `RectangularPatternFeature` along the height axis with parametric count and spacing.
- **Symmetric cases:** Build dados on one side, mirror the template, then create independent patterns per side.

## Common Pitfalls

| Error | Cause | Fix |
|-------|-------|-----|
| Dado doesn't cut through | Sketch rectangle doesn't span full board width | Extend sketch lines to board edges or beyond |
| Cut affects adjacent body | Missing `participantBodies` | Set `ext_input.participantBodies = [host_body]` |
| Shelf doesn't fit | `dr_width` doesn't match shelf thickness | Link both to the same parameter |
| Rabbet too deep | `dr_depth > dr_host_thick / 2` | Keep depth to 1/3 - 1/2 of host thickness |

## Example Snippet

Through dado cut on a side panel to receive a shelf:

```python
# -- Dado cut on side panel --
# Sketch on inner face of side panel
dado_plane = side_body.faces.item(0)  # inner face
sk = comp.sketches.add(dado_plane)

# Rectangle spanning full panel depth
p1 = adsk.core.Point3D.create(0, 0, 0)  # approximate, constrained below
p2 = adsk.core.Point3D.create(1, 1, 0)
rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)

# Constrain dado position and width
d_off = sk.sketchDimensions.addDistanceDimension(
    rect.item(0).startSketchPoint, sk.originPoint,
    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_off.parameter.expression = "dr_offset - dr_width / 2"

d_w = sk.sketchDimensions.addDistanceDimension(
    rect.item(0).startSketchPoint, rect.item(0).endSketchPoint,
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_w.parameter.expression = "dr_width"

d_len = sk.sketchDimensions.addDistanceDimension(
    rect.item(1).startSketchPoint, rect.item(1).endSketchPoint,
    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_len.parameter.expression = "panel_depth"

# Extrude as cut
prof = sk.profiles.item(0)
ext_input = comp.features.extrudeFeatures.createInput(prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByString("dr_depth"))
ext_input.participantBodies = [side_body]
comp.features.extrudeFeatures.add(ext_input)
```

**See also:** Tongue and Groove rules in [woodworking.md](../commands/woodworking.md) for slat infill joints.
