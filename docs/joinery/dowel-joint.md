# Dowel Joint

## Overview

A **dowel joint** uses cylindrical pegs (dowels) inserted into matching holes in two mating pieces. The dowels provide alignment, mechanical interlock, and additional glue surface within the holes.

**When to use:** Edge-to-edge panel glue-ups, face frame assembly, shelf-to-side connections, alignment pins for flat joints. Dowels are simpler to model than mortise-and-tenon for quick connections and are invisible from the outside.

**Strength:** Medium. Strength depends on dowel diameter, depth, and number. Two or more dowels per joint prevent rotation. Primarily a glue joint reinforced by the dowel shear strength.

## Variants

| Variant | Description |
|---------|-------------|
| Edge dowel | Dowels in edge grain for panel glue-ups |
| Face dowel | Dowels through face into end grain (weaker) |
| Through dowel | Dowel passes completely through, visible on surface (decorative) |
| Blind dowel | Dowel hidden inside both pieces |

## Parameters

| Parameter | Expression | Unit | Description |
|-----------|------------|------|-------------|
| `dw_dia` | `"0.375 in"` | `"in"` | Dowel diameter |
| `dw_depth` | `"1 in"` | `"in"` | Hole depth in each piece |
| `dw_spacing` | `"3 in"` | `"in"` | Center-to-center spacing between dowels |
| `dw_edge_dist` | `"1.5 in"` | `"in"` | Distance from board edge to first dowel center |
| `dw_count` | `"floor((board_length - 2 * dw_edge_dist) / dw_spacing) + 1"` | `""` | Number of dowels |

```python
params = design.userParameters
params.add("dw_dia", adsk.core.ValueInput.createByString("0.375 in"), "in", "Dowel diameter")
params.add("dw_depth", adsk.core.ValueInput.createByString("1 in"), "in", "Dowel hole depth")
params.add("dw_spacing", adsk.core.ValueInput.createByString("3 in"), "in", "Dowel spacing")
params.add("dw_edge_dist", adsk.core.ValueInput.createByString("1.5 in"), "in", "Edge distance to first dowel")
params.add("dw_count", adsk.core.ValueInput.createByString("floor((board_length - 2 * dw_edge_dist) / dw_spacing) + 1"), "", "Number of dowels")
```

## Derived Parameters

| Parameter | Expression | Description |
|-----------|------------|-------------|
| `dw_count` | `floor((board_length - 2 * dw_edge_dist) / dw_spacing) + 1` | Parametric dowel count |
| `dw_radius` | `dw_dia / 2` | Convenience for sketch circles |

```python
params.add("dw_radius", adsk.core.ValueInput.createByString("dw_dia / 2"), "in", "Dowel radius")
```

## Geometry Workflow

### Dowel Holes (blind)

1. **Plane** — Mating face of piece A (the face that will join piece B).
2. **Sketch** — Draw a circle:
   - Center at `(dw_edge_dist, board_thick / 2)` — centered on thickness
   - Radius = `dw_radius`
3. **Extrude** — Cut by `dw_depth`:
   - Operation: `CutFeatureOperation`
   - `participantBodies = [body_a]`
4. **Pattern** — `RectangularPatternFeature` along the board length:
   - Count: `dw_count`
   - Spacing: `dw_spacing`
5. **Repeat** — Same holes in piece B's mating face, mirrored orientation.

### Through Dowel (decorative)

1. After assembling pieces, drill through the joint from the outside face.
2. Extrude cut through both pieces (or use `AllExtentType`).
3. Optionally add a dowel body (cylinder extrude with `NewBodyFeatureOperation`).

## Replication

- **Panel glue-up:** Pattern dowel holes along the edge, then repeat the pattern for the mating board.
- **Multiple shelves:** Build dowel holes for one shelf, pattern vertically for shelf spacing.

## Common Pitfalls

| Error | Cause | Fix |
|-------|-------|-----|
| Holes don't align | Different reference points for each piece | Use matching parametric offsets from shared datum |
| Dowel won't fit | Hole diameter equals dowel diameter exactly | In practice, holes match; model uses same `dw_dia` for both |
| Hole too shallow | `dw_depth` less than half dowel length | Ensure `dw_depth` in each piece sums to dowel length + 1/16" clearance |
| Circle sketch won't extrude | Circle not closed or coincident lines | Use `sketchCircles.addByCenterRadius` for clean profiles |

## Example Snippet

Blind dowel holes along an edge for panel glue-up:

```python
# -- Dowel holes in piece A edge --
edge_face = body_a.faces.item(0)  # mating edge face
sk = comp.sketches.add(edge_face)

# First dowel hole (circle)
center = adsk.core.Point3D.create(1, 0.5, 0)  # approximate, constrained below
circle = sk.sketchCurves.sketchCircles.addByCenterRadius(center, 0.2)

# Constrain center position
d_x = sk.sketchDimensions.addDistanceDimension(
    circle.centerSketchPoint, sk.originPoint,
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_x.parameter.expression = "dw_edge_dist"

d_y = sk.sketchDimensions.addDistanceDimension(
    circle.centerSketchPoint, sk.originPoint,
    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_y.parameter.expression = "board_thick / 2"

# Constrain radius
d_r = sk.sketchDimensions.addRadialDimension(circle, adsk.core.Point3D.create(0, 0, 0))
d_r.parameter.expression = "dw_radius"

# Cut hole
prof = sk.profiles.item(0)
ext_input = comp.features.extrudeFeatures.createInput(prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByString("dw_depth"))
ext_input.participantBodies = [body_a]
hole_feat = comp.features.extrudeFeatures.add(ext_input)

# Pattern dowel holes along edge
pat_feats = comp.features.rectangularPatternFeatures
feat_coll = adsk.core.ObjectCollection.create()
feat_coll.add(hole_feat)
pat_input = pat_feats.createInput(feat_coll,
    comp.xConstructionAxis,
    adsk.core.ValueInput.createByString("dw_count"),
    adsk.core.ValueInput.createByString("dw_spacing"),
    adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
pat_feats.add(pat_input)
```
