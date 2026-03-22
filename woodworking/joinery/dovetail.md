# Dovetail

## Overview

A **dovetail joint** uses trapezoidal (fan-shaped) pins and tails that interlock to create an extremely strong mechanical joint. The angled faces resist pulling apart, making dovetails the premier joint for drawer construction and fine boxes.

**When to use:** Drawer fronts and sides, premium boxes, visible joints where craftsmanship is on display. Dovetails are the strongest corner joint and resist pulling forces along the tail direction without glue.

**Strength:** Very high. The trapezoidal geometry creates a mechanical lock — tails cannot pull out of pins. Combined with glue, dovetails are the strongest wood-to-wood corner joint.

**Taper direction (critical):** Tails must be **wider at the outside face** of the pin board and **narrower at the inside face**. This is what creates the mechanical lock — the wide end cannot pass through the narrower socket opening. If the taper is reversed (wider inside, narrower outside), the joint has no mechanical strength and pulls apart freely. In the CAD model, the triangular wedge cuts that create the dovetail angle must be placed on the **inner** face of the pin board (the side facing the interior of the piece), leaving the outer face at full tail width.

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
| `dt_tail_count` | `"6"` | `""` | Number of tails |
| `dt_thick` | `"0.75 in"` | `"in"` | Board thickness (= tail/pin length) |
| `dt_board_h` | `"6 in"` | `"in"` | Board height (joint runs along this edge) |

```python
params = design.userParameters
params.add("dt_angle", adsk.core.ValueInput.createByString("8 deg"), "deg", "Dovetail angle")
params.add("dt_tail_w", adsk.core.ValueInput.createByString("0.75 in"), "in", "Tail width (wide end)")
params.add("dt_tail_count", adsk.core.ValueInput.createByString("6"), "", "Number of tails")
params.add("dt_thick", adsk.core.ValueInput.createByString("0.75 in"), "in", "Board thickness")
params.add("dt_board_h", adsk.core.ValueInput.createByString("6 in"), "in", "Board height")
```

## Derived Parameters

| Parameter | Expression | Description |
|-----------|------------|-------------|
| `dt_pin_w` | `dt_board_h / dt_tail_count - dt_tail_w` | Pin width (derived from board height and tail count) |
| `dt_pitch` | `dt_board_h / dt_tail_count` | Center-to-center distance between tails |
| `dt_start_y` | `dt_pin_w / 2 + dt_tail_w / 2` | Center of first tail (half-pin offset from edge) |
| `dt_narrow_w` | `dt_tail_w - 2 * dt_thick * tan(dt_angle)` | Tail width at the narrow end |
| `dt_half_pin` | `dt_pin_w / 2` | Half-pin at top and bottom edges |

**Layout equation:** `n * dt_tail_w + n * dt_pin_w = dt_board_h`, where n = `dt_tail_count`. Layout is always `[half_pin] [tail] [pin] [tail] ... [tail] [half_pin]`, ensuring symmetric half-pins on both outer edges.

**Why count-based, not width-based:** Defining `dt_tail_w` + `dt_tail_count` as user parameters and deriving `dt_pin_w` guarantees the tails always fill the board exactly. The alternative — defining both `dt_tail_w` and `dt_pin_w` independently and using `floor()` to compute count — leaves uneven leftover space that makes front and back edges asymmetric.

**Centering requirement:** The first tail's sketch position MUST be parametrically constrained to `dt_start_y` via a sketch dimension (not evaluated once at script time). If the position is baked in via `ev()` / `evaluateExpression()`, changing `dt_tail_count` in Change Parameters will update the pattern spacing but NOT the first tail's position — the front half-pin stays fixed while the back half-pin drifts. Constraining the sketch dimension to `"dt_start_y"` ensures both half-pins stay equal at `dt_pin_w / 2`.

```python
params.add("dt_pin_w", adsk.core.ValueInput.createByString("dt_board_h / dt_tail_count - dt_tail_w"), "in", "Pin width (derived)")
params.add("dt_pitch", adsk.core.ValueInput.createByString("dt_board_h / dt_tail_count"), "in", "Tail pitch")
params.add("dt_start_y", adsk.core.ValueInput.createByString("dt_pin_w / 2 + dt_tail_w / 2"), "in", "Center of first tail")
params.add("dt_narrow_w", adsk.core.ValueInput.createByString("dt_tail_w - 2 * dt_thick * tan(dt_angle)"), "in", "Tail narrow width")
params.add("dt_half_pin", adsk.core.ValueInput.createByString("dt_pin_w / 2"), "in", "Half-pin width")
```

## Geometry Workflow

Dovetails require trapezoidal sketch profiles rather than simple rectangles. The key is sketching the full trapezoid in a single sketch so one extrude produces the complete dovetail shape — no separate CUT features needed.

### Through Dovetail

**Why sketch the trapezoid directly:** A multi-feature approach (rectangle extrude + separate CUT wedges to create the taper) breaks when combined with body patterns. The pattern replicates the tail body at new Y positions, but the CUT features' sketches stay at their original fixed Y positions — so the taper cuts don't follow the patterned tails. Sketching the full trapezoid in one sketch gives one extrude = one body. Body pattern replicates the complete trapezoidal body and everything moves together.

**Tail bodies (one sketch + one extrude per tail, then body pattern):**

1. **Plane** — offset plane at the tail board end (e.g., `total_height - board_thick`).
2. **Sketch** — Draw a closed trapezoid with 4 lines:
   - L1: P1→P2 — wide side (vertical, at X=0, outside face)
   - L2: P2→P3 — angled back edge
   - L3: P3→P4 — narrow side (vertical, at X=board_thick, inside face)
   - L4: P4→P1 — angled front edge
   - Where: P1=(0, dt_pin_w/2), P2=(0, dt_pin_w/2 + dt_tail_w), P3=(board_thick, dt_pin_w/2 + dt_tail_w - delta), P4=(board_thick, dt_pin_w/2 + delta), delta=board_thick*tan(dt_angle)
3. **Constrain** — 8 constraints for 8 DOF:
   - 2 geometric: L1 vertical, L3 vertical
   - 6 dimensional: L1 length = `dt_tail_w`, L3 length = `dt_narrow_w`, horiz P1→P4 = `board_thick`, Y of P1 from origin = `dt_pin_w / 2`, X of P1 from origin = `0 in`, Y of P4 from origin = `dt_pin_w / 2 + board_thick * tan(dt_angle)`
4. **Extrude** — NewBody by `board_thick` → one trapezoidal tail body.
5. **Mirror** — across center plane → opposite-side tail.
6. **Body pattern** — along the joint edge:
   - Count: `dt_tail_count`, Spacing: `dt_pitch`
   - Pattern left tails separately from right tails.

**Socket CUT (in the pin board):**

1. Create assembly proxies for all tail bodies.
2. `CombineFeature` with CUT operation against the pin board, `keepTool=True`.

### Half-Blind Dovetail

Same approach, but the tail extrude depth is less than `dt_thick`, leaving material on the front face of the pin board to hide the joint.

## Replication

- **Drawer (4 corners):** Build one dovetail corner, mirror for the opposite corner. Front corners may use half-blind, back corners through dovetails.
- **Pattern the trapezoidal cut** — each socket is one pattern instance.

## Common Pitfalls

| Error | Cause | Fix |
|-------|-------|-----|
| Tails don't interlock | Tail and socket angles don't match | Both reference same `dt_angle` parameter |
| Gap between pins and tails | `dt_narrow_w` not derived correctly | Use `dt_tail_w - 2 * dt_thick * tan(dt_angle)` |
| Dovetail angle too steep | Angle > 14 degrees | Keep 7-14 deg; 8 deg for hardwood |
| Pattern misaligned | Pitch doesn't match board division | Set spacing = `dt_pitch` = `dt_board_h / dt_tail_count`; first tail at `dt_start_y` |
| Half-pins asymmetric after parameter change | First tail position baked in at script time (not parametrically constrained) | Add sketch dimension from origin to first tail edge = `"dt_pin_w / 2"`, or to first tail center = `"dt_start_y"` |
| Half-blind depth wrong | Socket deeper than board thickness | `dt_socket_depth < dt_thick` for half-blind |
| Reverse dovetail (no lock) | Wedge cuts placed on outer face instead of inner face — tails wider inside, narrower outside | Cut the taper from the **inner** face of the pin board; the outer (visible) face keeps full `dt_tail_w` |
| Taper missing on patterned tails | Rectangle extrude + separate CUT wedge features — body pattern copies the rect body but CUT sketches stay at fixed Y positions | Sketch the full trapezoid in one sketch; one extrude = one body; body pattern replicates the complete shape |

## Example Snippet

Through dovetail — single trapezoid sketch per tail, then body pattern:

```python
# -- Dovetail tail: trapezoid sketch + extrude + body pattern --
# Plane at the tail board end
dt_pl = off_plane(comp, comp.xYConstructionPlane,
                  "total_height - board_thick", "DT_Plane")

# Approximate positions for sketch lines (constrained parametrically below)
bt = ev("board_thick")
hp = ev("dt_pin_w") / 2
delta = bt * math.tan(ev("dt_angle"))
tw = ev("dt_tail_w")

sk = comp.sketches.add(dt_pl)
sk.name = "DT_Sk"
lines = sk.sketchCurves.sketchLines

# Trapezoid vertices: wide end at X=0 (outside face), narrow at X=bt (inside)
p1 = adsk.core.Point3D.create(0, hp, 0)              # outside-front
p2 = adsk.core.Point3D.create(0, hp + tw, 0)          # outside-back
p3 = adsk.core.Point3D.create(bt, hp + tw - delta, 0) # inside-back
p4 = adsk.core.Point3D.create(bt, hp + delta, 0)      # inside-front

l1 = lines.addByTwoPoints(p1, p2)                                  # wide side (X=0)
l2 = lines.addByTwoPoints(l1.endSketchPoint, p3)                   # angled back
l3 = lines.addByTwoPoints(l2.endSketchPoint, p4)                   # narrow side (X=bt)
l4 = lines.addByTwoPoints(l3.endSketchPoint, l1.startSketchPoint)  # angled front

# 8 constraints for 8 DOF
sk.geometricConstraints.addVertical(l1)   # #1
sk.geometricConstraints.addVertical(l3)   # #2
d = sk.sketchDimensions
d.addDistanceDimension(l1.startSketchPoint, l1.endSketchPoint,      # #3
    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
    adsk.core.Point3D.create(-1, hp + tw / 2, 0)
).parameter.expression = "dt_tail_w"
d.addDistanceDimension(l3.startSketchPoint, l3.endSketchPoint,      # #4
    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
    adsk.core.Point3D.create(bt + 1, hp + tw / 2, 0)
).parameter.expression = "dt_narrow_w"
d.addDistanceDimension(l1.startSketchPoint, l3.endSketchPoint,      # #5
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    adsk.core.Point3D.create(bt / 2, hp - 1, 0)
).parameter.expression = "board_thick"
d.addDistanceDimension(sk.originPoint, l1.startSketchPoint,         # #6
    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
    adsk.core.Point3D.create(-1, hp / 2, 0)
).parameter.expression = "dt_pin_w / 2"
d.addDistanceDimension(sk.originPoint, l1.startSketchPoint,         # #7
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    adsk.core.Point3D.create(0, hp - 2, 0)
).parameter.expression = "0 in"
d.addDistanceDimension(sk.originPoint, l3.endSketchPoint,           # #8
    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
    adsk.core.Point3D.create(bt + 2, (hp + delta) / 2, 0)
).parameter.expression = "dt_pin_w / 2 + board_thick * tan(dt_angle)"

# Extrude trapezoid → one tail body
ext = ext_new(comp, sk.profiles.item(0), "board_thick", "DT_Tail")
tail = ext.bodies.item(0)

# Body pattern along joint edge
body_pattern(comp, tail, comp.yConstructionAxis,
             "dt_tail_count", "dt_pitch", "DT_Pattern")
```

**See also:** [box-joint.md](box-joint.md) for a simpler interlocking alternative.
