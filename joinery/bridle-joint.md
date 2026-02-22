# Bridle Joint

## Overview

A **bridle joint** (open mortise and tenon) is a frame joint where one piece has a slot (open mortise) cut into its end and the other has a matching tongue (tenon) that slides into the slot. Unlike a standard mortise and tenon, the slot is open on one or both sides.

**When to use:** Frame corners, T-connections in frames, gate construction, chair frames. Bridle joints are stronger than lap joints and easier to assemble than blind mortise-and-tenon. The exposed joint can be decorative.

**Strength:** High. Three-way glue surface (both cheeks plus the bottom of the slot) provides strong mechanical interlock. Resists racking forces well in frame constructions.

## Variants

| Variant | Description |
|---------|-------------|
| Corner bridle | Open slot at the end of one piece, tenon on the other (L-corner) |
| T-bridle | Slot cut in the middle of one piece, tenon on the end of the other |
| Mitered bridle | Bridle joint with a 45-degree miter on the visible face |

## Parameters

| Parameter | Expression | Unit | Description |
|-----------|------------|------|-------------|
| `br_width` | `"3.5 in"` | `"in"` | Width of both pieces (must match for flush joint) |
| `br_thick` | `"1.5 in"` | `"in"` | Thickness of both pieces |
| `br_slot_w` | `"br_thick / 3"` | `"in"` | Slot width (typically 1/3 thickness) |
| `br_slot_depth` | `"br_width"` | `"in"` | Slot depth (matches mating piece width) |
| `br_cheek` | `"(br_thick - br_slot_w) / 2"` | `"in"` | Cheek thickness on each side of slot |

```python
params = design.userParameters
params.add("br_width", adsk.core.ValueInput.createByString("3.5 in"), "in", "Piece width")
params.add("br_thick", adsk.core.ValueInput.createByString("1.5 in"), "in", "Piece thickness")
params.add("br_slot_w", adsk.core.ValueInput.createByString("br_thick / 3"), "in", "Slot width")
params.add("br_slot_depth", adsk.core.ValueInput.createByString("br_width"), "in", "Slot depth")
params.add("br_cheek", adsk.core.ValueInput.createByString("(br_thick - br_slot_w) / 2"), "in", "Cheek thickness")
```

## Derived Parameters

| Parameter | Expression | Description |
|-----------|------------|-------------|
| `br_cheek` | `(br_thick - br_slot_w) / 2` | Material on each side of the slot |
| `br_tenon_len` | `br_width` | Tenon length matches slot depth |

```python
params.add("br_tenon_len", adsk.core.ValueInput.createByString("br_width"), "in", "Tenon length")
```

## Geometry Workflow

### Corner Bridle

**Slot piece (open mortise):**

1. **Plane** — End face of the slot piece.
2. **Sketch** — Rectangle centered on the piece thickness:
   - Width = `br_slot_w`, centered (offset `br_cheek` from each edge)
   - Height = full piece width
3. **Extrude** — Cut by `br_slot_depth`:
   - Operation: `CutFeatureOperation`
   - `participantBodies = [slot_body]`

**Tenon piece:**

1. **Plane** — End face of the tenon piece.
2. **Sketch** — Two rectangles for the cheek waste (material to remove on each side):
   - Rectangle 1: width = `br_cheek`, full piece width
   - Rectangle 2: width = `br_cheek`, opposite side, full piece width
3. **Extrude** — Cut each cheek waste by `br_tenon_len`:
   - Operation: `CutFeatureOperation`
   - `participantBodies = [tenon_body]`

### T-Bridle

Same as corner bridle except the slot is cut in the middle of one piece (at `br_offset` from end) rather than at the end.

## Replication

- **Frame with 4 corners:** Build one corner bridle, mirror across midplanes for opposite corners.
- **T-connections:** Build one T-bridle, pattern or mirror for repeated connections.

## Common Pitfalls

| Error | Cause | Fix |
|-------|-------|-----|
| Tenon doesn't fit | Slot width and tenon width don't match | Both reference `br_slot_w` |
| Slot not centered | Cheek calculation wrong | Use `(br_thick - br_slot_w) / 2` for both cheeks |
| Joint not flush | Pieces have different widths | Ensure both reference `br_width` |
| Cut removes wrong cheek | Sketch positioned incorrectly | Dimension from known reference edge |

## Example Snippet

Corner bridle — slot in vertical post, tenon on horizontal rail:

```python
# -- Bridle: slot in post --
post_end = post_body.faces.item(0)  # top end face
sk_slot = comp.sketches.add(post_end)

p1 = adsk.core.Point3D.create(0, 0, 0)
p2 = adsk.core.Point3D.create(1, 1, 0)
rect = sk_slot.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)

# Slot width centered on thickness
d_w = sk_slot.sketchDimensions.addDistanceDimension(
    rect.item(0).startSketchPoint, rect.item(0).endSketchPoint,
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_w.parameter.expression = "br_slot_w"

d_off = sk_slot.sketchDimensions.addDistanceDimension(
    rect.item(0).startSketchPoint, sk_slot.originPoint,
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_off.parameter.expression = "br_cheek"

d_h = sk_slot.sketchDimensions.addDistanceDimension(
    rect.item(1).startSketchPoint, rect.item(1).endSketchPoint,
    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_h.parameter.expression = "br_width"

prof = sk_slot.profiles.item(0)
ext_input = comp.features.extrudeFeatures.createInput(prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByString("br_slot_depth"))
ext_input.participantBodies = [post_body]
comp.features.extrudeFeatures.add(ext_input)

# -- Bridle: tenon on rail (cut cheek waste) --
rail_end = rail_body.faces.item(0)  # end face
sk_tenon = comp.sketches.add(rail_end)

# Cheek waste rectangle (near side)
p1 = adsk.core.Point3D.create(0, 0, 0)
p2 = adsk.core.Point3D.create(1, 1, 0)
cheek_rect = sk_tenon.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)

d_cw = sk_tenon.sketchDimensions.addDistanceDimension(
    cheek_rect.item(0).startSketchPoint, cheek_rect.item(0).endSketchPoint,
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_cw.parameter.expression = "br_cheek"

d_ch = sk_tenon.sketchDimensions.addDistanceDimension(
    cheek_rect.item(1).startSketchPoint, cheek_rect.item(1).endSketchPoint,
    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
    adsk.core.Point3D.create(0, 0, 0))
d_ch.parameter.expression = "br_width"

cheek_prof = sk_tenon.profiles.item(0)
ext_cheek = comp.features.extrudeFeatures.createInput(cheek_prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
ext_cheek.setDistanceExtent(False, adsk.core.ValueInput.createByString("br_tenon_len"))
ext_cheek.participantBodies = [rail_body]
comp.features.extrudeFeatures.add(ext_cheek)
# Repeat for far-side cheek waste (offset by br_cheek + br_slot_w)
```

**See also:** Mortise and Tenon rules in [woodworking.md](../commands/woodworking.md) for blind mortise joints.
