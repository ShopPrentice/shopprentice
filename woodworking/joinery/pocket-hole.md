# Pocket Hole

## Overview

A **pocket hole** joint uses an angled pilot hole drilled through one piece, with a screw driven at an angle into the mating piece. It's the fastest structural joint to model and produces strong, hidden connections.

**When to use:** Face frames, quick cabinet assembly, tabletop attachment, any joint where speed matters and the pocket hole side is hidden. Pocket holes are not traditional fine woodworking but are ubiquitous in modern cabinet and furniture construction.

**Strength:** Medium. Relies on screw thread engagement in the mating piece. Stronger than butt joints, comparable to dowels. Can loosen over time under repeated stress, but performs well in static assemblies.

## Variants

| Variant | Description |
|---------|-------------|
| Standard pocket hole | Angled hole + screw, pocket hidden on back/underside |
| Face-frame pocket | Joining face frame stiles to rails |
| Edge pocket | Joining panels edge-to-edge (tabletops) |

## Parameters

| Parameter | Expression | Unit | Description |
|-----------|------------|------|-------------|
| `ph_angle` | `"15 deg"` | `"deg"` | Pocket hole drill angle (typically 15 deg) |
| `ph_dia` | `"0.375 in"` | `"in"` | Pilot hole diameter |
| `ph_pocket_dia` | `"0.625 in"` | `"in"` | Pocket (counterbore) diameter |
| `ph_thick` | `"0.75 in"` | `"in"` | Board thickness |
| `ph_pocket_depth` | `"0.5 in"` | `"in"` | Pocket counterbore depth |
| `ph_edge_dist` | `"2 in"` | `"in"` | Distance from board edge to first pocket hole |
| `ph_spacing` | `"6 in"` | `"in"` | Spacing between pocket holes |
| `ph_count` | `"2"` | `""` | Number of pocket holes per joint |

```python
params = design.userParameters
params.add("ph_angle", adsk.core.ValueInput.createByString("15 deg"), "deg", "Pocket hole angle")
params.add("ph_dia", adsk.core.ValueInput.createByString("0.375 in"), "in", "Pilot hole diameter")
params.add("ph_pocket_dia", adsk.core.ValueInput.createByString("0.625 in"), "in", "Pocket counterbore diameter")
params.add("ph_thick", adsk.core.ValueInput.createByString("0.75 in"), "in", "Board thickness")
params.add("ph_pocket_depth", adsk.core.ValueInput.createByString("0.5 in"), "in", "Pocket depth")
params.add("ph_edge_dist", adsk.core.ValueInput.createByString("2 in"), "in", "Edge distance to first pocket")
params.add("ph_spacing", adsk.core.ValueInput.createByString("6 in"), "in", "Pocket hole spacing")
params.add("ph_count", adsk.core.ValueInput.createByString("2"), "", "Pocket holes per joint")
```

## Derived Parameters

| Parameter | Expression | Description |
|-----------|------------|-------------|
| `ph_pilot_len` | `ph_thick / cos(ph_angle)` | Angled pilot hole length through material |
| `ph_exit_offset` | `ph_thick * tan(ph_angle)` | How far the pilot exits from the entry point |

```python
params.add("ph_pilot_len", adsk.core.ValueInput.createByString("ph_thick / cos(ph_angle)"), "in", "Pilot hole length")
params.add("ph_exit_offset", adsk.core.ValueInput.createByString("ph_thick * tan(ph_angle)"), "in", "Pilot exit offset")
```

## Geometry Workflow

Pocket holes require an angled construction plane for the pilot hole sketch.

### Pocket Hole (angled pilot + counterbore)

1. **Angled construction plane:**
   - Create a construction plane at `ph_angle` to the back face of the board
   - Positioned at `ph_edge_dist` from the board edge

2. **Pilot hole:**
   - **Plane** — The angled construction plane
   - **Sketch** — Circle with diameter `ph_dia`, centered on the plane
   - **Extrude** — Cut through the board thickness at the angle:
     - Operation: `CutFeatureOperation`
     - Distance: `ph_pilot_len`
     - `participantBodies = [board_body]`

3. **Pocket counterbore:**
   - **Plane** — Back face of the board (where the screw enters)
   - **Sketch** — Circle with diameter `ph_pocket_dia`, centered on pilot hole entry
   - **Extrude** — Cut by `ph_pocket_depth`:
     - Operation: `CutFeatureOperation`
     - `participantBodies = [board_body]`

4. **Pattern** — Pattern both features along the board length:
   - Count: `ph_count`
   - Spacing: `ph_spacing`

### Simplified Approach (for visualization only)

If the angled construction plane is complex, model pocket holes as simple angled cylinders:
1. Create the angled plane using `createByAngle` on the back face.
2. Sketch circle and extrude at angle.

## Replication

- **Face frame:** Build pocket holes on one stile-to-rail joint, repeat for each rail connection.
- **Tabletop attachment:** Pattern pocket holes along the apron, spaced by `ph_spacing`.

## Common Pitfalls

| Error | Cause | Fix |
|-------|-------|-----|
| Pilot hole misses mating piece | Angle too steep or too shallow | Use standard `15 deg` for 3/4" stock |
| Counterbore too deep | `ph_pocket_depth` > half board thickness | Keep pocket depth reasonable for stock thickness |
| Angled plane wrong direction | Angle reference face incorrect | Verify construction plane angles from the back face inward |
| Hole exits wrong face | Angle direction reversed | Check extrude direction on the angled plane |
| Pattern doesn't include both features | Only one feature in pattern collection | Add both pilot hole and counterbore features to the pattern `ObjectCollection` |

## Example Snippet

Pocket hole in a face frame rail:

```python
# -- Pocket hole: angled construction plane --
back_face = rail_body.faces.item(1)  # back face of rail

# Create angled construction plane
planes = comp.constructionPlanes
plane_input = planes.createInput()
# Angle from back face, tilted toward the mating piece
angle_val = adsk.core.ValueInput.createByString("ph_angle")
edge = back_face.edges.item(0)  # edge to rotate around
plane_input.setByAngle(edge, angle_val, back_face)
angled_plane = planes.add(plane_input)

# -- Pilot hole on angled plane --
sk_pilot = comp.sketches.add(angled_plane)
center = adsk.core.Point3D.create(0, 0, 0)  # approximate
circle_pilot = sk_pilot.sketchCurves.sketchCircles.addByCenterRadius(center, 0.2)

d_r = sk_pilot.sketchDimensions.addRadialDimension(circle_pilot, adsk.core.Point3D.create(0, 0, 0))
d_r.parameter.expression = "ph_dia / 2"

# Position along rail
d_pos = sk_pilot.sketchDimensions.addDistanceDimension(
    circle_pilot.centerSketchPoint, sk_pilot.originPoint,
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_pos.parameter.expression = "ph_edge_dist"

prof_pilot = sk_pilot.profiles.item(0)
ext_pilot = comp.features.extrudeFeatures.createInput(prof_pilot, adsk.fusion.FeatureOperations.CutFeatureOperation)
ext_pilot.setDistanceExtent(False, adsk.core.ValueInput.createByString("ph_pilot_len"))
ext_pilot.participantBodies = [rail_body]
pilot_feat = comp.features.extrudeFeatures.add(ext_pilot)

# -- Pocket counterbore on back face --
sk_pocket = comp.sketches.add(back_face)
center_pocket = adsk.core.Point3D.create(0, 0, 0)
circle_pocket = sk_pocket.sketchCurves.sketchCircles.addByCenterRadius(center_pocket, 0.3)

d_rp = sk_pocket.sketchDimensions.addRadialDimension(circle_pocket, adsk.core.Point3D.create(0, 0, 0))
d_rp.parameter.expression = "ph_pocket_dia / 2"

# Align with pilot hole entry
d_pos_p = sk_pocket.sketchDimensions.addDistanceDimension(
    circle_pocket.centerSketchPoint, sk_pocket.originPoint,
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_pos_p.parameter.expression = "ph_edge_dist"

prof_pocket = sk_pocket.profiles.item(0)
ext_pocket = comp.features.extrudeFeatures.createInput(prof_pocket, adsk.fusion.FeatureOperations.CutFeatureOperation)
ext_pocket.setDistanceExtent(False, adsk.core.ValueInput.createByString("ph_pocket_depth"))
ext_pocket.participantBodies = [rail_body]
pocket_feat = comp.features.extrudeFeatures.add(ext_pocket)

# -- Pattern both features along rail --
pat_feats = comp.features.rectangularPatternFeatures
feat_coll = adsk.core.ObjectCollection.create()
feat_coll.add(pilot_feat)
feat_coll.add(pocket_feat)
pat_input = pat_feats.createInput(feat_coll,
    comp.xConstructionAxis,
    adsk.core.ValueInput.createByString("ph_count"),
    adsk.core.ValueInput.createByString("ph_spacing"),
    adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
pat_feats.add(pat_input)
```
