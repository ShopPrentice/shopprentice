# Angled Construction

Techniques for splayed legs, compound angles, and connecting parts at non-orthogonal positions. Read this topic when the design involves any angle that isn't 90 degrees.

## When to Read

- Splayed legs (chairs, stools, benches, sawhorses)
- Tapered legs (Shaker tables, mid-century furniture)
- Compound angles (splay in two planes simultaneously)
- Stretchers or rails connecting splayed legs
- Through-tenons at an angle
- **Angled chair backrests** (vertical-to-raked back legs, smooth bend transitions)
- **Tilted dominos** (connecting angled rails/slats to vertical posts)

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
LegFront_Pl = sp.off_plane(root, root.xZConstructionPlane,
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
sp.combine(root, leg_body, [seat_body], CUT, True, "LegTrim_NL")
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

### Stretcher Sketch vs. Extrude Dimension Mapping

Stretchers are sketched on a **horizontal construction plane** (XY offset at `str_h`). On this plane, the sketch spans X and Y while `ext_new_sym` extrudes in Z. For a tall, thin stretcher (shelf-style), the **height** (tall dimension) must go on the extrude, not the sketch cross-axis:

| Stretcher runs in | Sketch long axis | Sketch cross-axis | `ext_new_sym` (Z) |
|---|---|---|---|
| X (back/front) | X = `str_len` | Y = `str_t` (thickness) | `str_w / 2` (half-height) |
| Y (side) | Y = `str_len` | X = `str_t` (thickness) | `str_w / 2` (half-height) |

**Common mistake:** putting `str_w` (the larger "width/height" dimension) on the sketch cross-axis and `str_t` on the extrude. This produces a stretcher that is deep (into the table) instead of tall, and causes stretcher-to-stretcher interference at leg corners where two 3.5"-deep stretchers overlap inside a 1.5" leg.

**Rule of thumb:** On a horizontal construction plane, the extrude direction is Z (vertical). A stretcher's visible height is vertical → it goes on the extrude. The thin dimension faces the table interior → it goes on the sketch cross-axis.

## Non-Perpendicular Joinery

### The Gap Problem

When a stretcher meets a splayed leg, the standard flat shoulder CUT leaves a gap. The shoulder face is perpendicular to the stretcher axis, but the leg surface is tilted by the splay angle. At 6 deg splay, this gap is ~0.09"--0.18" -- visible and structurally weak.

### Solution: Leg CUT + Sweep Tenon

Instead of cutting shoulders from the stretcher ends, CUT the leg FROM the stretcher to create an angled mating face. Then sweep a tenon from that angled face along the stretcher axis. The shoulder naturally sits flush against the splayed leg.

See `woodworking/joinery/mortise-tenon.md` section "Angled M&T Variant" for the complete 6-step technique.

### Key Points

- Use `angled_tenon_end()` instead of `shoulder_cut_end()` when any rail meets a post at a non-perpendicular angle
- The leg is the CUT tool with `keepTool=True` -- it is not modified
- Sweep uses `PerpendicularOrientationType` -- the tenon follows the stretcher axis
- Apply before mirror -- mirrored stretchers inherit the angled geometry
- Existing mortise CUTs work unchanged -- the tenon creates an angled mortise pocket

## Stretcher Splay Matching

### When to Use

When stretchers connect splayed legs and the stretcher sides should be **parallel to the adjacent leg faces** — not horizontal. This is a refined look where the stretcher follows the leg geometry. Without this, the stretcher-to-leg junction shows a visible wedge gap between the flat stretcher side and the angled leg face.

### Technique: Move Before Joinery

Add a **Move (free rotation)** to the stretcher body **after extrude but before `angled_tenon_end`**:

1. Stretcher tilts to match the leg splay angle
2. `angled_tenon_end`'s leg CUT creates a shoulder face accounting for both the stretcher tilt and leg splay
3. Mirror features propagate the tilt automatically

**Key insight — rotation axis = stretcher's long axis.** A back stretcher runs in X and rotates around X (for Y-splay `splay_w`). A side stretcher runs in Y and rotates around Y (for X-splay `splay`). Since rotation is around the stretcher's own long axis, sweep paths along that axis are unaffected — only the cross-section tilts.

### Pivot at Stretcher Center

Unlike legs (where the pivot is at the inner edge to stay embedded in the seat), stretchers pivot at their **own center** — the point that should stay fixed is the stretcher's centroid at its splay-adjusted position:

```python
# Back stretcher: rotate -splay_w around X, pivot at (bstr_y_c, bstr_z_c)
angle_bs = -ev("splay_w")
c_bs, s_bs = math.cos(angle_bs), math.sin(angle_bs)
ty_bs = bstr_y_c - (bstr_y_c * c_bs + bstr_z_c * s_bs)
tz_bs = bstr_z_c - (-bstr_y_c * s_bs + bstr_z_c * c_bs)
xf_bs = adsk.core.Matrix3D.create()
xf_bs.setWithArray([
    1.0,  0.0,   0.0,   0.0,
    0.0,  c_bs,  s_bs,  ty_bs,
    0.0, -s_bs,  c_bs,  tz_bs,
    0.0,  0.0,   0.0,   1.0
])
```

For a side stretcher (runs in Y), use the Y-axis rotation matrix with `+splay` and pivot at `(sstr_x_c, sstr_z_c)`.

### Angle Sign Convention

| Stretcher | Runs in | Rotates around | Angle | Effect |
|-----------|---------|----------------|-------|--------|
| Back (large Y) | X | X | `-splay_w` | Bottom tilts toward +Y → matches back legs' outward lean |
| Side (small X) | Y | Y | `+splay` | Bottom tilts toward -X → matches left legs' outward lean |

The front stretcher (mirror of back across YMid) and right stretcher (mirror of left across XMid) inherit the correct tilt direction from their mirror source.

### Interference After Tilting

Tilting a stretcher can push its surface into adjacent bodies. **Always run `check_interference` after adding splay moves.** Common case: a footrest sitting directly above the front stretcher — the tilted stretcher's top edge rises by `str_w/2 × sin(splay_angle)` and may intersect the footrest. Fix with a trim CUT:

```python
sp.combine(root, footrest_body, [front_stretcher], CUT, True, "FR_FStrTrim")
```

### Build Order

```
Extrude stretcher → Splay Move → angled_tenon_end (both ends) → Mirror → Mortise CUTs
```

The Move must come after extrude (body must exist) and before `angled_tenon_end` (so the leg CUT + sweep tenon account for the tilted orientation).

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

## Angled Chair Backrests

### When to Use

Chair back legs that are vertical from floor to seat, then angle backward for the backrest. The bend point is typically 1-3" above the seat. A fillet at the bend creates a smooth transition.

### Strategy: Profile Sketch + Extrude (Tested — dining chair)

**Do NOT use two-piece JOIN for back legs with a bend.** The overlap approach (vertical box + rotated backrest box + JOIN) creates a notch on the inner face: the rotated overlap protrudes past the vertical portion's inner face due to the rotation geometry. This leaves a clean bend on the outer face but a step/notch on the inner face that cannot be filleted.

**Instead, sketch the side profile as a single closed shape and extrude by `leg_size`:**

```
Inner face:                    Outer face:
   /  ← angled                    /  ← angled
  /                               /
 |   ← bend point                |   ← bend point
 |                                |
 |   ← vertical                  |   ← vertical
 |                                |
```

The profile on a YZ plane (6 lines):
1. Inner vertical: `(Y_inner, 0)` → `(Y_inner, bend_z)`
2. Inner angled: → `(Y_inner + h*sin(rake), bend_z + h*cos(rake))`
3. Top cap: → `(Y_outer + h*sin(rake), bend_z + h*cos(rake))`
4. Outer angled: → `(Y_outer, bend_z)`
5. Outer vertical: → `(Y_outer, 0)`
6. Bottom cap: → close to point 1

Where `h = back_h - bend_z` and `Y_inner/Y_outer = seat_d - leg_size / seat_d`.

```python
sk = leg_c.sketches.add(leg_c.yZConstructionPlane)
m2s = sk.modelToSketchSpace
P3 = adsk.core.Point3D

yi = ev("seat_d - leg_size")  # inner Y
yo = ev("seat_d")              # outer Y
bz = ev("bend_z")
h = ev("back_h") - bz
dy = h * math.sin(rake_rad)
dz = h * math.cos(rake_rad)

mp = [
    P3.create(0, yi, 0),               # inner bottom
    P3.create(0, yi, bz),              # inner bend
    P3.create(0, yi + dy, bz + dz),   # inner top
    P3.create(0, yo + dy, bz + dz),   # outer top
    P3.create(0, yo, bz),              # outer bend
    P3.create(0, yo, 0),               # outer bottom
]
sp = [m2s(p) for p in mp]

# Draw closed profile with shared sketch points
lines = sk.sketchCurves.sketchLines
l0 = lines.addByTwoPoints(sp[0], sp[1])
l1 = lines.addByTwoPoints(l0.endSketchPoint, sp[2])
l2 = lines.addByTwoPoints(l1.endSketchPoint, sp[3])
l3 = lines.addByTwoPoints(l2.endSketchPoint, sp[4])
l4 = lines.addByTwoPoints(l3.endSketchPoint, sp[5])
l5 = lines.addByTwoPoints(l4.endSketchPoint, l0.startSketchPoint)

# H/V constraints on vertical and horizontal lines only
h_ax, v_ax = sp.probe_sketch_axes(sk)
gc = sk.geometricConstraints
if v_ax == "z":
    gc.addVertical(l0);  gc.addVertical(l4)   # vertical lines
    gc.addHorizontal(l2); gc.addHorizontal(l5) # caps
else:
    gc.addHorizontal(l0); gc.addHorizontal(l4)
    gc.addVertical(l2);   gc.addVertical(l5)
# DO NOT constrain angled lines (l1, l3)

# Extrude by leg_size in +X
prof = sk.profiles.item(0)
ext_inp = leg_c.features.extrudeFeatures.createInput(
    prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
ext_inp.setDistanceExtent(False, VI("leg_size"))
```

Result: single body with clean bends on ALL 4 faces. Mirror across X midplane for the opposite leg.

### Filleting the Bend Edges

After extrude, the bend creates 2 edges (inner + outer face) where the normals of adjacent planar faces are nearly parallel. Find them by checking `acos(dot)` of face normals:

```python
bend_edges = adsk.core.ObjectCollection.create()
for i in range(body.edges.count):
    edge = body.edges.item(i)
    if edge.faces.count != 2:
        continue
    g1 = edge.faces.item(0).geometry
    g2 = edge.faces.item(1).geometry
    if not (isinstance(g1, adsk.core.Plane) and isinstance(g2, adsk.core.Plane)):
        continue
    n1, n2 = g1.normal, g2.normal
    dot = max(-1.0, min(1.0, n1.x*n2.x + n1.y*n2.y + n1.z*n2.z))
    angle = math.degrees(math.acos(dot))
    if angle < 20:  # normals nearly parallel = obtuse bend
        bend_edges.add(edge)
```

**Pitfall — angle interpretation:** When two faces meet at 172° (nearly flat, 8° bend), the outward normals are 8° apart, NOT 172°. `acos(dot)` returns the small angle (8°). Filter with `angle < 20` to catch bend edges while excluding 90° corners.

Apply fillet with `propagate=True` — the 2 edges propagate to the side faces:
```python
fil_inp = comp.features.filletFeatures.createInput()
fil_inp.addConstantRadiusEdgeSet(bend_edges, VI("bend_r"), True)
```

A 6" radius at 8° bend creates a subtle but clean smooth transition.

### Backrest Components (Vertical Slats — NORDVIKEN Style)

For a ladder-back with vertical slats:
- **Top rail** + **bottom rail** between back posts (not through — dominos connect to posts)
- **N vertical slats** between the rails with stub tenons
- Top rail offset 0.5" below the post top (creates a small "ear" detail)
- All pieces built at non-raked positions, then rotated together with the same pivot-compensated transform as the backrest

**Centering on the leg cross-section:** Rails and slats should be centered on the back post, not flush with the inner face. Use `back_face_y = seat_d - leg_size/2 - rail_thick/2`. This gives equal material on both sides of the mortise/domino.

### Tilted Dominos for Angled Joints

Standard `domino.grid` creates vertical dominos (long_axis="z"). When connecting an angled rail to a vertical post, the domino should align with the rail's cross-section — tilted by `back_rake`.

Build tilted dominos manually: sketch a rotated rectangle on the interface plane, extrude symmetrically:

```python
def tilted_rail_domino(plane, center_x, rail_z_center, rail_body, leg_body, name):
    """Domino tilted by back_rake at a rail-to-post interface."""
    # Compute rotated center position
    dz = rail_z_center - bend_z_cm
    y_rot = bl_cy + sin_r * dz
    z_rot = bend_z_cm + cos_r * dz

    # Tilted rectangle corners in model space
    half_l = ev("dm_w") / 2
    half_s = ev("dm_t") / 2
    dy_l = half_l * sin_r;  dz_l = half_l * cos_r  # long direction
    dy_s = half_s * cos_r;  dz_s = -half_s * sin_r  # short direction

    corners = [
        P3.create(center_x, y_rot + dy_l + dy_s, z_rot + dz_l + dz_s),
        P3.create(center_x, y_rot + dy_l - dy_s, z_rot + dz_l - dz_s),
        P3.create(center_x, y_rot - dy_l - dy_s, z_rot - dz_l - dz_s),
        P3.create(center_x, y_rot - dy_l + dy_s, z_rot - dz_l + dz_s),
    ]
    # Sketch on interface plane, extrude symmetrically by dm_d
    sk = root.sketches.add(plane)
    sp = [sk.modelToSketchSpace(p) for p in corners]
    lines = sk.sketchCurves.sketchLines
    l0 = lines.addByTwoPoints(sp[0], sp[1])
    l1 = lines.addByTwoPoints(l0.endSketchPoint, sp[2])
    l2 = lines.addByTwoPoints(l1.endSketchPoint, sp[3])
    lines.addByTwoPoints(l2.endSketchPoint, l0.startSketchPoint)

    prof = sk.profiles.item(0)
    ext_inp = root.features.extrudeFeatures.createInput(
        prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ext_inp.setSymmetricExtent(VI("dm_d"), False)
    ext = root.features.extrudeFeatures.add(ext_inp)
    dm_body = ext.bodies.item(0)
    # CUT into both bodies
    sp.combine(root, rail_body, [dm_body], CUT, True, f"{name}_CutRail")
    sp.combine(root, leg_body, [dm_body], CUT, True, f"{name}_CutLeg")
```

This creates a domino whose long axis follows the tilted backrest direction, properly aligning with the rail cross-section at the post interface.

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
| Tilted stretcher intersects footrest/rail | Splay Move raises stretcher edge into adjacent body | Run `check_interference` after splay moves; add trim CUT if non-zero |
| Splay Move after `angled_tenon_end` — wrong shoulder | Move tilts the already-cut shoulder face | Move must come BEFORE `angled_tenon_end` — the tenon technique needs to see the tilted body |
| Stretcher 3.5" deep × 0.75" tall (swapped) | Put `str_w` (height) on sketch cross-axis, `str_t` on extrude | Sketch cross-axis = `str_t` (thickness), extrude = `str_w / 2` (half-height). See "Sketch vs. Extrude Dimension Mapping" |
| Stretcher-to-stretcher interference at corners | Two thick stretchers overlap inside a leg | Swap to correct dims (above); run `check_interference` after stretcher extrudes |
| Two-piece back leg has notch on inner face | Overlap from rotated backrest protrudes past vertical portion's inner face | Use single profile sketch + extrude instead of two-piece JOIN (see "Angled Chair Backrests") |
| Fillet misses bend edges (finds 0 or 1) | Filtering by `180 - acos(dot)` ≈ rake angle is wrong — `acos(dot)` already IS the small angle | Filter `acos(dot) < 20` for nearly-parallel normals at obtuse bends |
| Back apron dominos don't CUT into back legs | Apron at Y = seat_d - leg_size (inner face) has zero Y overlap with leg | Position apron flush with outer face: Y = seat_d - apron_thick (within leg's Y range) |
| Domino vertical on angled rail joint | Standard domino.grid uses long_axis="z" (vertical) | Build tilted dominos manually — sketch rotated rectangle on interface plane (see "Tilted Dominos") |

## Complete Build Sequence for Chair with Angled Backrest

```
1. Parameters: back_rake, bend_above, bend_r, slat/rail dimensions
2. Front legs: simple rectangular extrude
3. Back legs:
   a. Sketch side profile on YZ plane (6-line closed shape)
   b. Extrude by leg_size in X
   c. Fillet bend edges (find by acos(dot) < 20)
   d. Mirror across X midplane
4. Aprons + Stretchers: position within leg cross-section range for joinery
   a. Back apron flush with outer face of back legs (not inner face)
   b. Stretchers centered on legs (leg_size/2 - str_thick/2)
5. Seat: extrude, CUT notch for back legs
6. Backrest (NORDVIKEN style):
   a. Top rail + bottom rail between posts (not through)
   b. N vertical slats with stub tenons into rails
   c. Rotate ALL back pieces with same pivot-compensated transform
   d. CUT slats into rails (stub mortise)
   e. Tilted dominos connecting rails to posts
7. Dominos: aprons + stretchers to all legs
8. Details: leg bottom chamfers, seat edge fillet
9. Verify: check_interference, no floating pieces audit
```

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
   c. (Optional) Splay Move — tilt stretcher to match leg angle (see "Stretcher Splay Matching")
   d. Angled tenon (for splayed legs) or shoulder CUT both ends (see joinery/mortise-tenon.md)
   e. Mirror if symmetric (splay + shoulders propagate)
   f. Trim CUT adjacent bodies if splay creates interference (footrest, rails)
   g. CUT stretcher into legs (creates mortise pockets)
8. Details: chamfers on seat edges and leg bottoms
```
