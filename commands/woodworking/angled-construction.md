# Angled Construction

Techniques for splayed legs, compound angles, and connecting parts at non-orthogonal positions. Read this topic when the design involves any angle that isn't 90 degrees.

## When to Read

- Splayed legs (chairs, stools, benches, sawhorses)
- Tapered legs (Shaker tables, mid-century furniture)
- Compound angles (splay in two planes simultaneously)
- Stretchers or rails connecting splayed legs
- Through-tenons at an angle

## Splayed Legs

### Splay Parameters

Splay is the outward lean of a leg from vertical. Compound splay means the leg leans in two planes — along the piece's length (X) and along its width (Y).

```python
# Splay angles
params.add("splay",   VI("6 deg"), "deg", "Leg splay along length (X)")
params.add("splay_w", VI("4 deg"), "deg", "Leg splay along width (Y)")

# Derived: how far the foot shifts from the top at floor level
params.add("splay_shift",   VI("leg_h * tan(splay)"),   "in", "Foot X offset from top")
params.add("splay_shift_w", VI("leg_h * tan(splay_w)"), "in", "Foot Y offset from top")
```

### Strategy: Trapezoid Sketch + Move

Build compound splay in two steps:

1. **Primary splay (along length)** — Sketch the leg as a trapezoid in the XZ plane. The top edge is at `leg_inset_x ± leg_w/2`; the bottom edge shifts by `splay_shift`. This is a single sketch feature with fully parametric dimensions.

2. **Secondary splay (along width)** — Apply a Move feature that rotates the leg body around the X axis by `splay_w`. This avoids compound-angle sketch math and keeps each splay axis independent.

**Why not a single compound-angle sketch?** The sketch would need trigonometric expressions for foreshortened dimensions, and the extrude direction wouldn't align with any principal axis. Two-step splay is simpler, more readable, and each angle is independently adjustable.

### Trapezoid Sketch (Primary Splay)

Sketch on an XZ-offset construction plane at the leg's Y position. The four corners form a trapezoid — parallel top and bottom edges, with the bottom shifted by `splay_shift`:

```
 Top-left ─────── Top-right        ← at leg_top_z
    \                 /
     \               /              ← leg tapers inward toward floor
      \             /
  Bot-left ─── Bot-right            ← at Z = 0, shifted by splay_shift
```

```python
# Construction plane at front face of leg
LegFront_Pl = af.off_plane(root, root.xZConstructionPlane,
    "leg_inset_y - leg_d / 2", "LegFront_Pl")

sk = root.sketches.add(LegFront_Pl)
m2s = sk.modelToSketchSpace  # ALWAYS use for XZ planes (Y may flip)

# Model-space corners → sketch-space points
inset_x = ev("leg_inset_x")
half_w = ev("leg_w") / 2
top_z = ev("leg_top_z")
shift = ev("splay_shift")
plane_y = ev("leg_inset_y") - ev("leg_d") / 2

s_tl = m2s(P(inset_x - half_w,          plane_y, top_z))
s_tr = m2s(P(inset_x + half_w,          plane_y, top_z))
s_br = m2s(P(inset_x + half_w - shift,  plane_y, 0))
s_bl = m2s(P(inset_x - half_w - shift,  plane_y, 0))

# Draw 4 connected lines (shared sketch points at each corner)
lns = sk.sketchCurves.sketchLines
ln_top   = lns.addByTwoPoints(P(s_tl.x, s_tl.y, 0), P(s_tr.x, s_tr.y, 0))
ln_right = lns.addByTwoPoints(ln_top.endSketchPoint,  P(s_br.x, s_br.y, 0))
ln_bot   = lns.addByTwoPoints(ln_right.endSketchPoint, P(s_bl.x, s_bl.y, 0))
ln_left  = lns.addByTwoPoints(ln_bot.endSketchPoint, ln_top.startSketchPoint)
```

**Geometric constraints:** Only the top and bottom lines get `addHorizontal`. The side lines are intentionally angled (the splay) — no H/V constraint.

**Parametric dimensions (6 total):**

| Dimension | Points | Expression | Purpose |
|-----------|--------|------------|---------|
| Top width | top start → top end | `leg_w` | Leg width at top |
| Bottom width | bot start → bot end | `leg_w` | Leg width at foot (same width, shifted position) |
| Height | origin → top start (V) | `leg_top_z` | Leg top Z |
| X position | origin → top start (H) | `leg_inset_x - leg_w / 2` | Left edge position |
| Splay H | top start → bot end (H) | `splay_shift` | Horizontal shift between top and bottom |
| Splay V | top start → bot end (V) | `leg_top_z` | Vertical span of splay (redundant with height, but constrains the diagonal) |

Extrude by `leg_d` to create the leg body.

### Move Feature (Secondary Splay)

Rotate the leg body around the X axis by `splay_w`, pivoting at a specific point so the leg top stays embedded in the seat.

```python
angle = ev("splay_w")
c, s = math.cos(angle), math.sin(angle)

# Pivot point — see "Pivot Point Selection" below
pivot_y = ev("leg_inset_y") + ev("leg_d") / 2  # inner edge of leg top
pivot_z = ev("leg_top_z")

# Translation to keep pivot fixed: T = pivot - R × pivot
ty = pivot_y - (pivot_y * c + pivot_z * s)
tz = pivot_z - (-pivot_y * s + pivot_z * c)

xform = adsk.core.Matrix3D.create()
xform.setWithArray([
    1.0,  0.0,  0.0,  0.0,   # X unchanged
    0.0,    c,    s,   ty,    # Y rotation + translation
    0.0,   -s,    c,   tz,    # Z rotation + translation
    0.0,  0.0,  0.0,  1.0
])

move_coll = adsk.core.ObjectCollection.create()
move_coll.add(leg_body)
move_inp = root.features.moveFeatures.createInput2(move_coll)
move_inp.defineAsFreeMove(xform)
move_feat = root.features.moveFeatures.add(move_inp)
move_feat.name = "YSplay_NL"
```

**Matrix construction:** The 4×4 matrix combines rotation and translation. For rotation around the X axis (splay in the YZ plane):
```
[1    0       0      0  ]
[0  cos(θ)  sin(θ)  ty ]
[0 -sin(θ)  cos(θ)  tz ]
[0    0       0      1  ]
```

For rotation around the Y axis (splay in the XZ plane), swap the affected columns/rows accordingly.

The translation components `ty` and `tz` compensate for the pivot point — without them, the rotation pivots around the origin and the leg flies off to the wrong position.

### Pivot Point Selection (CRITICAL)

The pivot point determines which part of the leg stays fixed during the rotation. **Choose the pivot at the edge of the leg top that should remain fully embedded in the seat body.**

| Pivot location | Result |
|---------------|--------|
| Outer edge of leg top | Leg top partially exits the seat — CUT leaves a split surface |
| Center of leg top | Half the leg top exits the seat |
| **Inner edge of leg top** | **Entire leg top submerges into seat — clean CUT surface** |

For a leg at `leg_inset_y` with depth `leg_d`, the inner edge (toward seat center) is at `leg_inset_y + leg_d / 2`. Using this as the pivot ensures the entire leg cross-section stays inside the seat after the Y-splay rotation.

**Why this matters:** After splay, the leg top is trimmed by CUTting the seat body from the leg. If the leg top partially exits the seat, the CUT leaves a visible split line on the leg face — an unacceptable artifact. Pivoting at the inner edge guarantees full submersion.

### Trimming the Leg Top

After both splay operations, the leg top protrudes into the seat body at an angle. CUT the seat from the leg to create a clean angled surface:

```python
af.combine(root, leg_body, [seat_body], CUT, True, "LegTrim_NL")
```

**Do this BEFORE mirroring** — one CUT instead of four. Mirror propagates the trim.

### Mirror for All Four Legs

Build one leg (near-left), then mirror:

1. Mirror NL across YMid → NR (2 legs)
2. Mirror NL + NR across XMid → FL + FR (4 legs)

All features — trapezoid sketch, splay Move, trim CUT — propagate through the mirrors.

## Splay-Adjusted Positions

### The Formula

Any horizontal member connecting splayed legs (stretcher, footrest, cross-brace) needs its position adjusted for splay. At a given height `h` from the floor, the legs have shifted inward by a fraction of the total splay:

```
splay_offset_at_h = splay_shift × (leg_top_z - h) / leg_top_z
```

This is linear interpolation: at `h = 0` (floor), offset = full `splay_shift`. At `h = leg_top_z` (top), offset = 0. At any height in between, offset is proportional.

**As a Fusion parameter expression:**

```python
params.add("str_sx", VI("splay_shift * (leg_top_z - str_h) / leg_top_z"),
           "in", "Stretcher X splay offset")
params.add("str_sy", VI("splay_shift_w * (leg_top_z - str_h) / leg_top_z"),
           "in", "Stretcher Y splay offset")
```

**As a script-time helper (for positioning sketches):**

```python
def splay_center(h):
    """Return (sx, sy) splay offsets at height h (all values in cm)."""
    frac = (ev("leg_top_z") - h) / ev("leg_top_z")
    return ev("splay_shift") * frac, ev("splay_shift_w") * frac
```

### Stretcher Length with Splay

A stretcher running along the X axis between two legs at height `str_h`:

```python
# Splay offsets at this height
params.add("str_sx", VI("splay_shift * (leg_top_z - str_h) / leg_top_z"), "in", "")

# Stretcher runs from leg inner face to leg inner face, plus tenon protrusion
params.add("str_len",
    VI("seat_l - 2 * leg_inset_x + 2 * str_sx - leg_w + 2 * mt_l"),
    "in", "Stretcher total length")
```

Breaking this down:
- `seat_l - 2 * leg_inset_x` — distance between leg centers at top
- `+ 2 * str_sx` — legs are wider apart at this lower height due to splay
- `- leg_w` — subtract leg width (stretcher starts at inner face, not center)
- `+ 2 * mt_l` — add tenon protrusion at each end

For a stretcher along Y:
```python
params.add("str_len_y",
    VI("seat_w - 2 * leg_inset_y + 2 * str_sy - leg_d + 2 * mt_l"),
    "in", "Side stretcher total length")
```

### Stretcher Center Position

The stretcher center must also be splay-adjusted:

```python
sx, sy = splay_center(ev("str_h"))
# X-axis stretcher: centered at large Y (back legs)
str_x0 = ev("leg_inset_x") - sx + ev("leg_w") / 2 - ev("mt_l")
str_y_c = ev("seat_w") - ev("leg_inset_y") + sy  # back leg row
str_z_c = ev("str_h")
```

## SplitBody

### When to Use

SplitBody separates one body into two pieces using a cutting tool (plane or body face). Used for:
- Through-tenons: split the protruding portion from the main body
- Angled cuts: split a body at a construction plane

### API

```python
split_inp = root.features.splitBodyFeatures.createInput(
    body_to_split,
    splitting_tool,  # construction plane or BRepFace
    True             # splitToolExtent: extend tool to fully cut body
)
split_feat = root.features.splitBodyFeatures.add(split_inp)
```

### API Limitation: Single Tool Only

The Fusion UI allows selecting multiple splitting tools, but the Python API accepts only a single entity. `ObjectCollection` is rejected.

**Workaround:** Chain sequential single-tool splits. Each split produces two bodies; feed the appropriate piece into the next split.

### Re-Finding Bodies After Split

After `splitBodyFeatures.add()`, the original body reference may be stale. Re-find bodies by name:

```python
split_feat = root.features.splitBodyFeatures.add(split_inp)
# Re-find bodies — split may change which body has which name
upper = None
lower = None
for i in range(root.bRepBodies.count):
    b = root.bRepBodies.item(i)
    if b.name == "MyBody":
        # Determine which piece is which by bounding box
        bb = b.boundingBox
        if bb.maxPoint.z > threshold:
            upper = b
        else:
            lower = b
```

## Move Feature

### When to Use

- Secondary splay (rotation in a second plane after the sketch-based primary splay)
- Repositioning a body to a non-axis-aligned location
- Any rotation that can't be expressed as a sketch angle

### API

```python
xform = adsk.core.Matrix3D.create()
xform.setWithArray([...])  # 4×4 row-major matrix

move_coll = adsk.core.ObjectCollection.create()
move_coll.add(body)
move_inp = root.features.moveFeatures.createInput2(move_coll)
move_inp.defineAsFreeMove(xform)
feat = root.features.moveFeatures.add(move_inp)
```

### Pivot-Compensated Rotation Matrix

To rotate by angle θ around axis A, pivoting at point P (not the origin):

```
T = P - R × P
```

Where R is the rotation matrix and T is the translation vector. This ensures point P stays fixed after the rotation.

**Rotation around X axis** (splay in YZ plane):
```python
c, s = math.cos(theta), math.sin(theta)
ty = py - (py * c + pz * s)
tz = pz - (-py * s + pz * c)
matrix = [
    1, 0,  0, 0,
    0, c,  s, ty,
    0, -s, c, tz,
    0, 0,  0, 1
]
```

**Rotation around Y axis** (splay in XZ plane):
```python
c, s = math.cos(theta), math.sin(theta)
tx = px - (px * c - pz * s)
tz = pz - (px * s + pz * c)
matrix = [
    c, 0, -s, tx,
    0, 1,  0, 0,
    s, 0,  c, tz,
    0, 0,  0, 1
]
```

**Rotation around Z axis** (rotation in XY plane):
```python
c, s = math.cos(theta), math.sin(theta)
tx = px - (px * c + py * s)
ty = py - (-px * s + py * c)
matrix = [
    c,  s, 0, tx,
    -s, c, 0, ty,
    0,  0, 1, 0,
    0,  0, 0, 1
]
```

### Move is NOT Parametric

The Move feature's matrix is baked at script time — it doesn't update when parameters change. If `splay_w` changes in Change Parameters, the Move angle stays the same.

**Mitigation:** For furniture models, splay angles are rarely adjusted after the initial design. If parametric splay is required, use a component-level rotation (via occurrence transform) instead of a Move feature, but this adds complexity to cross-component CUT operations.

### Re-Find Bodies After Move

After a Move feature, the body's geometry has changed but the Python variable still references the same object. However, if subsequent operations rely on coordinates (e.g., `find_face`), re-find the body by name to ensure the reference is fresh:

```python
body = None
for i in range(root.bRepBodies.count):
    b = root.bRepBodies.item(i)
    if b.name == "Leg_NL":
        body = b
        break
```

## Common Pitfalls

| Error | Cause | Fix |
|-------|-------|-----|
| Leg upside-down on XZ plane | Sketch Y maps to model -Z on XZ-offset planes | Use `modelToSketchSpace` for all corner points — never assume sketch Y = model Z |
| Leg top partially outside seat after Y-splay | Move pivot at outer/center edge of leg | Pivot at the **inner edge** of the leg top (`leg_inset + leg_d / 2`) |
| Stretcher doesn't reach legs | Stretcher length doesn't account for splay at its height | Use `splay_shift * (leg_top_z - h) / leg_top_z` for splay-adjusted positions |
| 4 trim CUTs needed | Trim CUT applied after mirroring all legs | Apply trim CUT to template leg BEFORE mirror — mirrors propagate the CUT |
| Move matrix wrong — body flies off | Forgot pivot compensation (T = P - R×P) | Include translation components in the matrix that compensate for pivot point |
| Splay angle changes don't update | Move feature matrix baked at script time | Expected limitation — splay angles are design-time constants |
| H/V constraint on trapezoid side line | Taper lines are intentionally angled | Only add `addHorizontal` on top/bottom edges, never on the angled sides |
| Dimension uses `addDistanceDimension` for splay but value is negative | Distance dimensions are always positive | Use the `splay_shift` parameter directly — it's always positive (derived from `tan(splay)`) |

## Complete Build Sequence for Splayed-Leg Piece

```
1. Parameters: splay, splay_w, splay_shift, splay_shift_w, leg dimensions
2. Seat: simple rectangular extrude on XY plane at seat_z
3. Near-left leg:
   a. Construction plane at leg front face (XZ offset)
   b. Trapezoid sketch (primary splay in X)
   c. Extrude by leg_d
   d. Move feature (secondary splay in Y, pivot at inner edge)
   e. Trim CUT (seat CUTs leg top — clean angled surface)
4. Mirror NL → NR across YMid
5. Mirror NL+NR → FL+FR across XMid
6. Joinery: dominos, through-tenons, or shouldered M&T (see joinery/*.md)
7. Stretchers:
   a. Splay-adjusted derived params for each stretcher
   b. Extrude stretcher at full length (includes tenon protrusion)
   c. Shoulder CUT both ends (see joinery/mortise-tenon.md)
   d. Mirror if symmetric (shoulders propagate)
   e. CUT stretcher into legs (creates mortise pockets)
8. Details: chamfers on seat edges and leg bottoms
```
