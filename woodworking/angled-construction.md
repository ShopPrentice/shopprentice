# Angled Construction

Techniques for furniture with non-rectilinear members: splayed legs (stools, chairs, Windsor chairs, workbenches), angled braces, and through-tenon joinery.

## When to Read This File

Read this file when the project involves:
- Legs or members at an angle to the seat/top (splay)
- Through-tenons (tenon extends through and proud of the receiving board)
- Compound angles (splay in two directions simultaneously)
- Sweep-based mortises (mortise follows an angled body's path)

## Splay Parameters

Splayed legs require careful parameter design. The leg leans outward — the foot is offset from the top.

### Single Splay (one direction)
```python
params.add("splay", VI("10 deg"), "deg", "Leg splay angle")
params.add("leg_h", VI("7 in"), "in", "Leg height to seat bottom")
params.add("seat_t", VI("0.9 in"), "in", "Seat thickness")
params.add("tenon_proud", VI("0.125 in"), "in", "Tenon above seat")

# Derived
params.add("leg_top_z", VI("leg_h + seat_t + tenon_proud"), "in", "Total leg Z")
params.add("splay_shift", VI("leg_top_z * tan(splay)"), "in", "Foot offset from top")
```

### Compound Splay (two directions)
For legs that lean both forward/backward AND outward:
```python
params.add("splay", VI("10 deg"), "deg", "Leg splay along length")
params.add("splay_w", VI("5 deg"), "deg", "Leg splay along width")
params.add("splay_shift", VI("leg_top_z * tan(splay)"), "in", "Foot offset along length")
params.add("splay_shift_w", VI("leg_top_z * tan(splay_w)"), "in", "Foot offset along width")
```

### Sketch the Leg Profile

The leg is sketched as a **trapezoid** (not a rectangle) — the foot is offset from the top by `splay_shift`. Sketch on a construction plane parallel to the splay direction:

```python
# Construction plane at the leg's front face position
LegFront_Pl = af.off_plane(comp, root.xZConstructionPlane,
    "leg_inset_y - leg_d / 2", "LegFront_Pl")

# Sketch trapezoid: top is at (inset_x, leg_top_z), foot is offset by splay_shift
sk = comp.sketches.add(LegFront_Pl)
sk.name = "Leg_Sk"
lns = sk.sketchCurves.sketchLines

# Top edge (at seat level + tenon proud)
top_left_x = ev("leg_inset_x - leg_w / 2")
top_right_x = ev("leg_inset_x + leg_w / 2")
top_z = ev("leg_top_z")

# Bottom edge (shifted by splay at ground)
bot_left_x = top_left_x - ev("splay_shift")
bot_right_x = top_right_x - ev("splay_shift")

top = lns.addByTwoPoints(P(top_left_x, top_z, 0), P(top_right_x, top_z, 0))
right = lns.addByTwoPoints(top.endSketchPoint, P(bot_right_x, 0, 0))
bot = lns.addByTwoPoints(right.endSketchPoint, P(bot_left_x, 0, 0))
left = lns.addByTwoPoints(bot.endSketchPoint, top.startSketchPoint)

# Constrain: top and bottom are horizontal, sides are angled (no H/V constraint)
gc = sk.geometricConstraints
gc.addHorizontal(top)
gc.addHorizontal(bot)

# Dimension everything parametrically
d = sk.sketchDimensions
d.addDistanceDimension(top.startSketchPoint, top.endSketchPoint,
    H, P(0, 0, 0)).parameter.expression = "leg_w"
d.addDistanceDimension(bot.startSketchPoint, bot.endSketchPoint,
    H, P(0, 0, 0)).parameter.expression = "leg_w"
d.addDistanceDimension(sk.originPoint, top.startSketchPoint,
    V, P(0, 0, 0)).parameter.expression = "leg_top_z"
d.addDistanceDimension(top.startSketchPoint, bot.endSketchPoint,
    H, P(0, 0, 0)).parameter.expression = "splay_shift"
d.addDistanceDimension(top.startSketchPoint, bot.endSketchPoint,
    V, P(0, 0, 0)).parameter.expression = "leg_top_z"
```

Extrude with `leg_d` (depth) as NewBody. The result is a straight-profiled leg with splay built into the sketch geometry.

## Move Feature (Splay Application)

The leg from above has splay in one direction (from the trapezoid sketch). For the perpendicular splay direction, use a **Move** feature with a rotation matrix.

### Single-Axis Rotation

```python
import math

# Rotate around X axis by splay_w angle (Y-direction splay)
angle = ev("splay_w")  # radians (ev returns cm for lengths, rad for angles)
c, s = math.cos(angle), math.sin(angle)

# Rotation matrix around X axis (row-major 4x4)
xform = adsk.core.Matrix3D.create()
xform.setWithArray([
    1.0, 0.0, 0.0, 0.0,     # X unchanged
    0.0,   c,   s, ty,       # Y rotated
    0.0,  -s,   c, tz,       # Z rotated
    0.0, 0.0, 0.0, 1.0
])

# ty, tz compensate so the rotation pivots around the leg top (not origin)
# Pivot point: (leg_inset_x, leg_inset_y, leg_top_z)
# ty = pivot_y - (pivot_y * c + pivot_z * s)
# tz = pivot_z - (-pivot_y * s + pivot_z * c)
pivot_y = ev("leg_inset_y")
pivot_z = ev("leg_top_z")
ty = pivot_y - (pivot_y * c + pivot_z * s)
tz = pivot_z - (-pivot_y * s + pivot_z * c)

move_coll = adsk.core.ObjectCollection.create()
move_coll.add(leg_body)
move_inp = comp.features.moveFeatures.createInput2(move_coll)
move_inp.defineAsFreeMove(xform)
move_feat = comp.features.moveFeatures.add(move_inp)
move_feat.name = "YSplay_NL"
```

### Compound Angle (Two Rotations)

For compound splay, apply **two sequential Move features** — one for each splay direction. The order matters: apply the smaller splay first, then the larger. Each Move uses `defineAsFreeMove` with a rotation matrix pivoting around the leg top.

```python
# Move 1: Y-splay (rotate around X axis)
# ... same pattern as above with splay_w angle ...
move_feat1 = comp.features.moveFeatures.add(move_inp1)
move_feat1.name = "YSplay"

# Move 2: X-splay is already in the trapezoid sketch — no second move needed
# OR if both splays are done via Move (starting from a straight rectangular leg):
# Rotate around Y axis by splay angle
```

**Design choice:** You can build splay into the sketch profile (trapezoid) for one direction and use Move for the other, or use Move for both directions starting from a straight rectangular leg. The stool uses the hybrid approach — trapezoid sketch for the primary splay, Move for the secondary.

### Matrix Reference

Common rotation matrices (row-major 4x4, for `setWithArray`):

| Rotation | Matrix (3x3 part) |
|----------|-------------------|
| Around X by θ | `[1,0,0], [0,cos,-sin], [0,sin,cos]` |
| Around Y by θ | `[cos,0,sin], [0,1,0], [-sin,0,cos]` |
| Around Z by θ | `[cos,-sin,0], [sin,cos,0], [0,0,1]` |

Note: Fusion uses `setWithArray` with **row-major** order: `[r0c0, r0c1, r0c2, r0c3, r1c0, ...]`. The 4th column (indices 3, 7, 11) is translation.

**Pivot compensation:** To rotate around a point P (not the origin), set translation column to:
```
tx = Px - (Px*m00 + Py*m01 + Pz*m02)
ty = Py - (Px*m10 + Py*m11 + Pz*m12)
tz = Pz - (Px*m20 + Py*m21 + Pz*m22)
```

## Sweep Feature

Sweep extrudes a profile along a path (edge or curve). Essential for mortises that follow an angled body's path — a planar extrude can't match a compound-angle entry.

### Basic Sweep

```python
# Find the leg edge that runs from foot to top
sweep_edge = None
foot_pt = (ev("foot_x"), ev("foot_y"), 0)
top_pt = (ev("top_x"), ev("top_y"), ev("leg_top_z"))
for i in range(leg_body.edges.count):
    e = leg_body.edges.item(i)
    sp, ep = e.startVertex.geometry, e.endVertex.geometry
    d_start = abs(sp.x - foot_pt[0]) + abs(sp.y - foot_pt[1]) + abs(sp.z - foot_pt[2])
    d_end = abs(ep.x - top_pt[0]) + abs(ep.y - top_pt[1]) + abs(ep.z - top_pt[2])
    if d_start < 0.1 and d_end < 0.1:
        sweep_edge = e
        break

sweep_path = comp.features.createPath(sweep_edge)
```

### Sweep as CUT (Through-Mortise)

```python
# Profile: the tenon shoulder cross-section on the seat face (see Body Projection below)
sweep_inp = comp.features.sweepFeatures.createInput(profiles, sweep_path, CUT)
sweep_inp.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
sweep_inp.participantBodies = [seat_body]

# Distance control: what fraction of the path to sweep
# distanceOne = 1.0 means full path from start, distanceTwo = 0 means no extension
sweep_inp.distanceOne = adsk.core.ValueInput.createByString("1.00")
sweep_inp.distanceTwo = adsk.core.ValueInput.createByString("0")

sweep_feat = comp.features.sweepFeatures.add(sweep_inp)
sweep_feat.name = "ThroughMortise"
```

### Path Direction

The sweep path has a direction based on the edge orientation. `distanceOne` sweeps in the path direction; `distanceTwo` sweeps opposite. To determine which end of the edge matches your intended start point:

```python
# Check if path start matches our expected start vertex
path_start_vertex = sweep_edge.startVertex.geometry
expected_start = (foot_x, foot_y, foot_z)
vtx_match = (abs(path_start_vertex.x - expected_start[0]) +
             abs(path_start_vertex.y - expected_start[1]) +
             abs(path_start_vertex.z - expected_start[2]) < 0.1)

# isOpposedToEntity indicates if the path item is reversed relative to the edge
opposed = sweep_path.item(0).isOpposedToEntity
path_fwd = not (vtx_match != opposed)

if path_fwd:
    sweep_inp.distanceOne = VI("1.00")
    sweep_inp.distanceTwo = VI("0")
else:
    sweep_inp.distanceOne = VI("0")
    sweep_inp.distanceTwo = VI("1.00")
```

### Sweep Orientation Types

| Type | Behavior |
|------|----------|
| `PerpendicularOrientationType` | Profile stays perpendicular to path (most common for mortises) |
| `ParallelOrientationType` | Profile maintains original orientation along path |

## Body Projection (`intersectWithSketchPlane`)

Projects a body's cross-section onto a sketch plane. Returns reference curves showing where the body passes through the plane. Essential for laying out through-tenon shoulders.

### When to Use

| Technique | Use When |
|-----------|----------|
| `sk.project(edge)` | Project specific edges (slot boundaries, dado lines) |
| `sk.intersectWithSketchPlane([body])` | Project full body cross-section (angled body through a face) |

### Usage

```python
# Sketch on the seat's top face
top_face = af.find_face(seat_body, "z", +1)
sk = comp.sketches.add(top_face)
sk.name = "Mortise_Sk"

# Project the angled leg body onto this sketch plane
projected = sk.intersectWithSketchPlane([leg_body])

# Collect projected reference curves and their sketch points
proj_pts = []    # [(x, y, sketchPoint), ...]
proj_curves = [] # [(sx, sy, ex, ey, curve), ...]
for i in range(sk.sketchCurves.count):
    c = sk.sketchCurves.item(i)
    if c.isReference:
        sp, ep = c.startSketchPoint, c.endSketchPoint
        sg, eg = sp.geometry, ep.geometry
        proj_pts.append((sg.x, sg.y, sp))
        proj_curves.append((sg.x, sg.y, eg.x, eg.y, c))
```

### Finding Projected Points

```python
def nearest_proj(proj_pts, x, y):
    """Find the nearest projected sketch point to (x, y)."""
    best, best_d = None, 1e10
    for px, py, sp in proj_pts:
        d = abs(px - x) + abs(py - y)
        if d < best_d:
            best, best_d = sp, d
    return best

def nearest_proj_curve(proj_curves, sx, sy, ex, ey):
    """Find the projected curve closest to a line from (sx,sy) to (ex,ey)."""
    best, best_d = None, 1e10
    for _sx, _sy, _ex, _ey, c in proj_curves:
        d = min(abs(_sx-sx)+abs(_sy-sy)+abs(_ex-ex)+abs(_ey-ey),
                abs(_sx-ex)+abs(_sy-ey)+abs(_ex-sx)+abs(_ey-sy))
        if d < best_d:
            best, best_d = c, d
    return best
```

### Shoulder Lines from Projected Corners

Draw lines inward from each projected corner to create the tenon shoulder. The distance is parametric (`tenon_shoulder_w`):

```python
# For each projected corner, draw a line along the projected edge
# to a point tenon_shoulder_w inward
corner_pt = nearest_proj(proj_pts, corner_x, corner_y)
corner_geom = corner_pt.geometry

# Find the projected curve starting from this corner
proj_edge = nearest_proj_curve(proj_curves, corner_x, corner_y, far_x, far_y)

# Calculate point at tenon_shoulder_w along the projected edge
es = proj_edge.startSketchPoint.geometry
ee = proj_edge.endSketchPoint.geometry
edge_len = ((ee.x-es.x)**2 + (ee.y-es.y)**2)**0.5
frac = ev("tenon_shoulder_w") / edge_len if edge_len > 0.001 else 0

# Direction: from corner toward far end
ds = abs(corner_geom.x - es.x) + abs(corner_geom.y - es.y)
de = abs(corner_geom.x - ee.x) + abs(corner_geom.y - ee.y)
if ds < de:
    end_x = es.x + (ee.x - es.x) * frac
    end_y = es.y + (ee.y - es.y) * frac
else:
    end_x = ee.x + (es.x - ee.x) * frac
    end_y = ee.y + (es.y - ee.y) * frac

# Draw the shoulder line
shoulder = lns.addByTwoPoints(P(corner_geom.x, corner_geom.y, 0),
                               P(end_x, end_y, 0))
# Coincident constraint ties shoulder start to projected corner
sk.geometricConstraints.addCoincident(shoulder.startSketchPoint, corner_pt)

# Add parametric dimension
sk.sketchDimensions.addDistanceDimension(
    corner_pt, shoulder.endSketchPoint,
    adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
    P(0, 0, 0)).parameter.expression = "tenon_shoulder_w"
```

After drawing all four shoulder lines, connect their endpoints to close the shoulder rectangle. The smallest profile in the sketch is the tenon cross-section:

```python
# Connect shoulder line endpoints to form the inner rectangle
lns.addByTwoPoints(shoulder_top_left.endSketchPoint, shoulder_top_right.endSketchPoint)
lns.addByTwoPoints(shoulder_bot_left.endSketchPoint, shoulder_bot_right.endSketchPoint)

# Select the smallest profile (the tenon shoulder area)
prof = af.smallest_profile(sk)
```

## SplitBody Feature

Splits a body into multiple pieces using a plane or face as the cutting tool.

### Basic Split

```python
# Split leg at the seat bottom plane
split_inp = comp.features.splitBodyFeatures.createInput(
    leg_body,           # body to split
    seat_bottom_plane,  # splitting tool (construction plane or BRepFace)
    True                # keep both pieces
)
split_feat = comp.features.splitBodyFeatures.add(split_inp)
split_feat.name = "LegSplit"
```

After splitting, Fusion renames the pieces: original keeps its name, copies get `(1)`, `(2)`, etc. Use `find_body()` to locate each piece.

### Multi-Tool Split (API Limitation)

Fusion's API only accepts ONE splitting tool per `SplitBodyFeature`. For multiple split planes, use sequential splits:

```python
# Split 1: separate tenon from leg
split1 = comp.features.splitBodyFeatures.createInput(leg_body, seat_pl, True)
feat1 = comp.features.splitBodyFeatures.add(split1)
feat1.name = "Split_Seat"

# Split 2: separate waste from tenon (find the largest remaining piece)
biggest = None
for i in range(comp.bRepBodies.count):
    b = comp.bRepBodies.item(i)
    if "Leg" in b.name and (biggest is None or b.volume > biggest.volume):
        biggest = b

split2 = comp.features.splitBodyFeatures.createInput(biggest, waste_plane, True)
feat2 = comp.features.splitBodyFeatures.add(split2)
feat2.name = "Split_Waste"
```

## RemoveBody Feature

Removes unwanted bodies (waste pieces after split, construction helper bodies).

```python
waste = find_body("Leg_NL (2)")  # waste piece from split
if waste:
    comp.features.removeFeatures.add(waste)
```

**Naming after split:** When a body "Leg" is split into 3 pieces, they become "Leg", "Leg (1)", "Leg (2)". Identify which piece is which by checking bounding boxes or volumes — don't rely on the numbering order being predictable.

## Through-Tenon Joinery — Complete Pattern

A through-tenon passes completely through the receiving board, with a small proud section visible on the far side. Common in stool seats, workbench tops, and trestle tables.

### Workflow Summary

```
1. Sketch leg profile (trapezoid for splay) → Extrude through seat
2. Move to apply perpendicular splay (compound angle)
3. Sketch tenon shoulders on seat top face (body projection + shoulder lines)
4. Sweep along leg edge → CUT angled through-mortise in seat
5. SplitBody at seat bottom → separate proud tenon from leg
6. RemoveBody waste pieces
7. Mirror to replicate all legs
8. Combine CUT all legs into seat (through-mortise)
```

### Step-by-Step

**1. Leg extends through seat:**
```python
# leg_top_z = leg_h + seat_t + tenon_proud
# The leg profile goes from z=0 (foot) to z=leg_top_z (above seat)
# Extrude depth = leg_d
```

**2. Apply compound splay (if needed):**
```python
# First Move: Y-direction splay (rotate around X, pivot at leg top)
# Second Move: Already in trapezoid sketch (X-direction splay)
```

**3. Project and draw shoulders:**
```python
# Sketch on seat top face
# intersectWithSketchPlane([leg_body]) → projected outline
# Draw 4 shoulder lines inward from projected corners
# Connect endpoints → tenon shoulder rectangle
# Select smallest profile
```

**4. Sweep CUT:**
```python
# Find the leg edge from foot to top
# Create path from edge
# Sweep the shoulder profile along path → CUT into seat
# PerpendicularOrientationType keeps profile square to leg angle
```

**5–6. Split and remove waste:**
```python
# Split leg at seat bottom plane (construction plane at seat_z)
# Result: 3 pieces — leg below seat, tenon through seat, waste above
# Remove waste piece(s)
# Remaining: leg body + proud tenon extending above seat
```

**7. Mirror:**
```python
# Mirror the leg across midplanes to create all 4 legs
# Use mirror_bodies for the final leg body (after split/remove)
# Each mirrored leg inherits the compound splay angle
```

**8. Through-mortise CUT:**
```python
# The sweep already cut the angled mortise in step 4
# Mirror creates matching mortises for all legs
# Alternative: CUT all legs into seat via Combine after mirror
```

### Parameter Summary for Through-Tenon with Compound Splay

```python
# Primary dimensions
("leg_w", "1.4 in", "in", "Leg width (cross-section)")
("leg_d", "1.1 in", "in", "Leg depth (cross-section)")
("leg_h", "7 in", "in", "Leg height to seat bottom")
("seat_t", "0.9 in", "in", "Seat thickness")

# Splay angles
("splay", "10 deg", "deg", "Leg splay along length")
("splay_w", "5 deg", "deg", "Leg splay along width")

# Through-tenon
("tenon_proud", "0.125 in", "in", "Tenon extension above seat")
("tenon_shoulder_w", "0.3 in", "in", "Shoulder width (material around mortise)")

# Derived
("leg_top_z", "leg_h + seat_t + tenon_proud", "in", "Total leg Z extent")
("splay_shift", "leg_top_z * tan(splay)", "in", "Foot offset from top, along length")
("splay_shift_w", "leg_top_z * tan(splay_w)", "in", "Foot offset from top, along width")
("leg_inset_x", "2 in", "in", "Leg center from seat end")
("leg_inset_y", "1.5 in", "in", "Leg center from seat edge")
("seat_z", "leg_h", "in", "Seat bottom Z position")
```

## Coordinate Transform for Body-Face Sketches

When sketching on a body face (e.g., seat top), the sketch coordinate system may differ from the captured/expected axes. Use a coordinate transform to map between captured and actual sketch directions:

```python
# Captured sketch axes (from design intent or capture data)
cap_xd = (1.0, 0.0, 0.0)
cap_yd = (0.0, -1.0, 0.0)

# Actual sketch axes (from the runtime sketch)
act_xd = sk.xDirection
act_yd = sk.yDirection

# Build 2x2 rotation matrix
m00 = cap_xd[0]*act_xd.x + cap_xd[1]*act_xd.y + cap_xd[2]*act_xd.z
m01 = cap_yd[0]*act_xd.x + cap_yd[1]*act_xd.y + cap_yd[2]*act_xd.z
m10 = cap_xd[0]*act_yd.x + cap_xd[1]*act_yd.y + cap_xd[2]*act_yd.z
m11 = cap_yd[0]*act_yd.x + cap_yd[1]*act_yd.y + cap_yd[2]*act_yd.z

def xf(sx, sy):
    """Transform from captured sketch space to actual sketch space."""
    return (sx * m00 + sy * m01, sx * m10 + sy * m11)
```

This is needed because body faces can have different sketch orientations depending on which face is selected and how Fusion sets up the sketch axes. Always compare the expected vs actual `xDirection`/`yDirection` and apply the transform to all sketch coordinates.
