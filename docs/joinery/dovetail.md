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

**Centering requirement:** The first tail's sketch position MUST be parametrically constrained from the board edge (not evaluated once at script time). If the position is baked in via `ev()` / `evaluateExpression()`, changing `dt_tail_count` in Change Parameters will update the pattern spacing but NOT the first tail's position — the front half-pin stays fixed while the back half-pin drifts. Constraining the short face to `"dt_pin_w / 2 + dt_thick * tan(dt_angle)"` keeps both half-pins equal at `dt_pin_w / 2`.

```python
params.add("dt_pin_w", adsk.core.ValueInput.createByString("dt_board_h / dt_tail_count - dt_tail_w"), "in", "Pin width (derived)")
params.add("dt_pitch", adsk.core.ValueInput.createByString("dt_board_h / dt_tail_count"), "in", "Tail pitch")
params.add("dt_start_y", adsk.core.ValueInput.createByString("dt_pin_w / 2 + dt_tail_w / 2"), "in", "Center of first tail")
params.add("dt_narrow_w", adsk.core.ValueInput.createByString("dt_tail_w - 2 * dt_thick * tan(dt_angle)"), "in", "Tail narrow width")
params.add("dt_half_pin", adsk.core.ValueInput.createByString("dt_pin_w / 2"), "in", "Half-pin width")
```

## Proportions & Defaults

Use these rules when picking parameters from scratch. Defaults in the template `define_params` / `add_params` calls already follow them — override only when the piece demands it.

### Angle (`dt_angle`)
| Wood | Angle | Ratio | Rationale |
|------|-------|-------|-----------|
| Hardwood (oak, walnut, cherry, maple) | 7-9° | ~1:7 | Firm fibers hold a shallower taper |
| Softwood (pine, cedar, fir) | 10-14° | ~1:5 | Softer fibers need deeper mechanical engagement; glue grabs less reliably |
| **Default** | **8°** | **1:7** | Good all-purpose value for hardwoods |

Limits: **< 7°** risks the joint pulling apart (insufficient mechanical lock). **> 14°** creates short-grain at tail tips that breaks under stress.

### Tail Count (`dt_tail_count`)
Scale with board height, not stock thickness:

| Use case | Tails per inch of `board_h` | Example (6" board) |
|----------|----------------------------|---------------------|
| Fine box / jewelry work | ~1 tail / 1" | 5-6 tails |
| Casework, drawers | ~1 tail / 1.5-2" | 3-4 tails |
| Utility | ~1 tail / 2.5-3" | 2-3 tails |

- **Minimum: 3 tails** for visual balance (unless the piece is under 3" tall).
- **Maximum** is bounded by `pin_w > 0`: if `board_h / tail_count - tail_w` goes negative, reduce `tail_count` or `tail_w`.

### Tail : Pin Ratio (visual)
`pin_w` is derived — it's whatever fills the remaining height after tails. The ratio you see is implicit in your `tail_w` + `tail_count` choice.

| Style | Ratio (tail : pin) | Effect |
|-------|-------------------|--------|
| Classic fine work (handcut look) | 3:1 to 4:1 | Tails dominant, pins read as thin vertical lines |
| Modern / utilitarian | 2:1 | Pins more prominent, machine-cut aesthetic |
| Router-jig box-joint look | 1:1 | Equal-width tails and pins |

### Half-Blind Lap (`dt_lap`)
Only relevant for half-blind dovetails. The lap is the material hiding the joint from the outer face.

- **Typical:** 1/3 of pin board thickness. For 3/4" stock, `lap = 1/4"` → `socket_depth = 1/2"`.
- **Minimum:** 1/4" (0.25"). Thinner laps blow out when glue swells the wood or the joint is tapped home.
- **Maximum:** 1/2 of pin thickness. More than half leaves insufficient socket depth for the tail to grip.

Verify `socket_depth > tail_w / 2` (roughly) for adequate mechanical grip around each tail.

### Edge Padding (`dt_pad`)
Extra material beyond half a normal pin on each end of the board. End pin width becomes `pad + pin_w/2` instead of just `pin_w/2`.

- **Default: 0** — classic symmetric-half-pin layout.
- **Use when** `pin_w` gets thin (< ~1/8" / 3mm) and the unpadded half-pins would crack off easily. Common trigger: ultra-dense pins from high `tail_count` or wide `tail_w` near the pin_w > 0 limit.
- **Typical values:** 1/16" (1.5mm) to 3/16" (5mm). Keep below `tail_w / 2` so the edge pin doesn't visually dominate.
- **Effect:** tail pattern now packs into `board_h - 2·pad` instead of `board_h`. Inner pitch and inner `pin_w` shrink slightly; end pins grow by `pad`.

### Houndstooth Void (`dt_ht_small_w`, `dt_ht_depth`)
The void is decorative. It should read as a slot inside each tail, not as a competing feature.

| Param | Default | Range | Never |
|-------|---------|-------|-------|
| `ht_small_w` (free) | `tail_w / 7` | `tail_w / 10` (hairline) to `tail_w / 4` (bold) | > `tail_w / 3` — void starts overpowering the tail |
| `ht_depth` (free) | `tail_w * 3/5` | `tail_w / 2` (subtle) to `tail_w` (dramatic) | > `thick` (through) or `> socket_depth * 0.9` (half-blind) — void punches through |
| `ht_inset` (derived) | `(tail_w - ht_small_w) / 2` | — | Not user-tunable; auto-centers |

Since the void shares the main dovetail angle, a deeper void widens more at its far end. `ht_depth > tail_w` is allowed geometrically but the widening gets hard to control.

## Geometry Workflow

Dovetails require trapezoidal sketch profiles rather than simple rectangles. The key is sketching the full trapezoid in a single sketch so one extrude produces the complete dovetail shape — no separate CUT features needed.

### Through Dovetail

**Why sketch the trapezoid directly:** A multi-feature approach (rectangle extrude + separate CUT wedges to create the taper) breaks when combined with body patterns. The pattern replicates the tail body at new Y positions, but the CUT features' sketches stay at their original fixed Y positions — so the taper cuts don't follow the patterned tails. Sketching the full trapezoid in one sketch gives one extrude = one body. Body pattern replicates the complete trapezoidal body and everything moves together.

**Tail bodies (one sketch + one extrude per tail, then body pattern):**

1. **Plane** — offset plane at the tail board end (e.g., `total_height - board_thick`).
2. **Sketch** — Draw a closed trapezoid with 4 lines, but treat the short face as the anchor:
   - L1: P4→P3 — short side (inside face)
   - L2: P3→P2 — angled back edge
   - L3: P2→P1 — wide side (outside face)
   - L4: P1→P4 — angled front edge
   - Where: P1=(0, dt_pin_w/2), P2=(0, dt_pin_w/2 + dt_tail_w), P3=(board_thick, dt_pin_w/2 + dt_tail_w - delta), P4=(board_thick, dt_pin_w/2 + delta), delta=board_thick*tan(dt_angle)
3. **Constrain** — short face drives the whole tail:
   - 2 geometric: short + wide faces parallel to the joint axis
   - 5 dimensional: short-face length = `dt_narrow_w`, wide↔short separation = `board_thick`, short-face start along the joint axis = `dt_pin_w / 2 + board_thick * tan(dt_angle)`, short-face start along the thickness axis = `board_thick`, one flank angle to the short face = `90 deg - dt_angle`
   - The opposite flank is implied by the closed profile; do not independently position the wide face from the sketch origin.
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
| Half-pins asymmetric after parameter change | First tail position baked in at script time (not parametrically constrained) | Constrain the short-face start from the board edge with `"dt_pin_w / 2 + dt_thick * tan(dt_angle)"` |
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

# Trapezoid vertices: wide end at X=0 (outside face), short end at X=bt (inside)
p1 = adsk.core.Point3D.create(0, hp, 0)               # outside-front
p2 = adsk.core.Point3D.create(0, hp + tw, 0)          # outside-back
p3 = adsk.core.Point3D.create(bt, hp + tw - delta, 0) # inside-back
p4 = adsk.core.Point3D.create(bt, hp + delta, 0)      # inside-front

l_short = lines.addByTwoPoints(p4, p3)
l_back = lines.addByTwoPoints(l_short.endSketchPoint, p2)
l_wide = lines.addByTwoPoints(l_back.endSketchPoint, p1)
l_front = lines.addByTwoPoints(l_wide.endSketchPoint, l_short.startSketchPoint)

sk.geometricConstraints.addVertical(l_short)
sk.geometricConstraints.addVertical(l_wide)
d = sk.sketchDimensions
d.addDistanceDimension(l_short.startSketchPoint, l_short.endSketchPoint,
    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
    adsk.core.Point3D.create(bt + 1, hp + tw / 2, 0)
).parameter.expression = "dt_narrow_w"
d.addDistanceDimension(l_short.startSketchPoint, l_wide.endSketchPoint,
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    adsk.core.Point3D.create(bt / 2, hp - 1, 0)
).parameter.expression = "board_thick"
d.addDistanceDimension(sk.originPoint, l_short.startSketchPoint,
    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
    adsk.core.Point3D.create(bt + 1, (hp + delta) / 2, 0)
).parameter.expression = "dt_pin_w / 2 + board_thick * tan(dt_angle)"
d.addDistanceDimension(sk.originPoint, l_short.startSketchPoint,
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    adsk.core.Point3D.create(bt / 2, hp - 2, 0)
).parameter.expression = "board_thick"
d.addAngularDimension(
    l_front, l_short, adsk.core.Point3D.create(bt / 2, hp + delta / 2, 0)
).parameter.expression = "90 deg - dt_angle"

# Extrude trapezoid → one tail body
ext = ext_new(comp, sk.profiles.item(0), "board_thick", "DT_Tail")
tail = ext.bodies.item(0)

# Body pattern along joint edge
body_pattern(comp, tail, comp.yConstructionAxis,
             "dt_tail_count", "dt_pitch", "DT_Pattern")
```

**See also:** [box-joint.md](box-joint.md) for a simpler interlocking alternative.
