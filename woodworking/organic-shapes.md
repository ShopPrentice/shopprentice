# Organic Shapes

Techniques for building furniture with sculpted, hand-shaped forms — turned legs, carved seats, free-form profiles. Read this topic when the design involves curves that can't be described by simple geometric primitives.

## When to Read

- Turned or carved legs (Windsor, Esherick, Danish)
- Sculpted seats with scoops or saddle contours
- Free-form outlines (not rectangular, circular, or regular polygon)
- Any piece where the user references a photo and wants an organic feel

## Core Workflow: Approximate → Refine → Capture

Organic shapes require iteration. The agent can't guess the exact curve the user wants from a description alone. The workflow:

1. **Agent builds approximate profile** — place spline control points based on description ("thick at lower third, thin at ends") or reference photo analysis
2. **Execute and present** — user sees the 3D result in Fusion
3. **User edits the sketch** — drags spline fit points in Fusion UI to refine the curve
4. **Agent captures changes** — use `get_timeline_state(index, include_sketches=True)` to read the updated fit point positions
5. **Agent updates script** — replace the hardcoded control points with captured values
6. **Repeat** until the user is satisfied

This loop is fast because the user edits visually (what they're good at) and the agent handles code (what it's good at).

### Capturing Spline Edits

```python
# Find the sketch index in the timeline (e.g., the leg profile sketch)
state = get_timeline_state(index=8, include_sketches=True)

# The sketch data includes fit points for each FittedSpline:
# {
#   "type": "FittedSpline",
#   "fitPoints": [[x0, y0], [x1, y1], ...]
# }
#
# Convert sketch coords back to model coords using the sketch's
# sketchXDir/sketchYDir/sketchOrigin from the state response.
```

## Revolved Profiles (Turned Legs, Spindles)

For cylindrical parts with organic taper — legs, stretchers, spindles, tool handles.

### Sketch Setup

Half-profile on the XZ construction plane. The revolve axis is a vertical construction line at X=0. The profile is a fitted spline on the right side of the axis, closed by straight lines at the top, bottom, and along the axis.

```
Axis (construction)    Spline profile
  |                    /
  |                   / ← swell (max diameter)
  |                  /
  |                 |  ← gradual taper
  |                |
  |               /   ← accelerating taper
  |             /
  |___________/       ← tip (thin but not a point)
  Bottom cap (horizontal line)
```

### Profile Structure

```python
# Half-profile: (radius_cm, height_cm) from floor to seat
profile_points = [
    (tip_r,   0.0),      # floor — thin tip
    (...,     ...),      # 3-4 points for lower taper curve
    (max_r,   swell_z),  # swell peak (widest point)
    (...,     ...),      # 4-5 points for upper taper curve
    (top_r,   seat_z),   # seat entry — transition to tenon
]

# Create fitted spline
spl_pts = ObjectCollection.create()
for r, z in profile_points:
    p = m2s_leg(Point3D.create(r, 0, z))
    spl_pts.add(Point3D.create(p.x, p.y, 0))
spline = sk.sketchCurves.sketchFittedSplines.add(spl_pts)

# Close the profile: bottom cap → spline → shoulder → tenon → top cap → axis
```

### Control Point Guidelines

**Convex taper** (Esherick style — stays thick, thins fast near ends):
- Place more control points near the endpoints where curvature changes quickly
- Fewer points in the mid-section where the curve is gentle
- The swell should be in the lower third (`swell_ratio ≈ 0.25-0.35`)
- Tip diameter should be substantial (not a needle point) — `0.5-0.7 × bot_dia`

**Concave taper** (baluster style — thins quickly from swell):
- More control points near the swell for tight curvature
- Fewer points near the ends

**Bamboo/spindle** (multiple swells):
- Use multiple groups of 3-4 control points per swell
- Each group: approach, peak, departure

### Common Mistakes

| Mistake | Fix |
|---------|-----|
| Bump/wiggle in the curve | Too many close control points — remove intermediate points and let the spline interpolate |
| Tip too thin (needle) | Increase tip diameter; real wood can't be turned to a point |
| Taper too linear | Add an extra control point near the swell to hold the thick diameter longer |
| Asymmetric swell | Ensure the swell control point is at the intended height ratio, not shifted by surrounding points |

## Organic Outlines (Seats, Slabs)

For non-rectangular plan shapes — seats, tabletops, shelves with free-form edges.

### Closed Spline Approach

Instead of straight lines + arc fillets (which look geometric), use a single closed fitted spline through control points that define the shape.

```python
# Define control points as (model_x, model_y) tuples
seat_pts = [
    (cx + sd*0.45, cy),         # front center
    (cx + sd*0.30, cy + sw*0.3), # front-right
    ...                          # continue around the perimeter
]

pts = ObjectCollection.create()
for mx, my in seat_pts:
    p = m2s(Point3D.create(mx, my, z))
    pts.add(Point3D.create(p.x, p.y, 0))

spline = sk.sketchCurves.sketchFittedSplines.add(pts)
spline.isClosed = True
```

### Shape Strategies

**Rounded hexagon** (Esherick stool seat):
- Start with a triangle (3 vertices)
- Clip each corner by a fraction (`clip ≈ 0.15`) to get 6 vertices
- Add midpoint control points on each edge, pushed slightly outward (`bulge ≈ 0.04-0.06`) for convex edges
- Total: 12 control points for organic hex with no straight edges

**Kidney/shield shape** (Windsor seat):
- 8 control points: front narrow, sides widest, back moderate
- Asymmetric front-to-back ratio

**Free-form slab** (Nakashima):
- Trace from photo or user sketch
- One straight reference edge, one organic live edge

### Convex Edge Technique

To make spline edges bow outward instead of being straight:

```python
# For each edge of the base polygon, add a midpoint pushed outward
midpoint = ((v1 + v2) / 2)
# Normal direction (away from center)
normal = outward_from_centroid(midpoint)
# Push outward by a fraction of edge length
control_point = midpoint + normal * edge_length * bulge_fraction
```

## Scoops and Carved Surfaces

### Spherical Scoop

A very large radius sphere positioned above the seat, dipping just slightly into the surface. Creates a subtle concave dish.

```python
# Sphere center: above seat top by (radius - depth)
sphere_cz = seat_top_z + scoop_r - scoop_depth

# Sketch semicircle on a vertical plane, revolve 360° to make sphere
# CUT sphere from seat body (keepTool=False)
```

- `scoop_r = 30 in` with `scoop_depth = 0.3 in` → barely perceptible curvature, very subtle
- `scoop_r = 15 in` with `scoop_depth = 0.5 in` → noticeable saddle

Center the scoop on the **geometric centroid** of the seat outline, not the bounding box center (they differ for asymmetric shapes like triangular seats).

### Scoop Footprint

The scoop circle radius on the seat surface: `footprint_r ≈ sqrt(2 × scoop_r × scoop_depth)`

With R=30", d=0.3": footprint ≈ 4.2" radius — covers the central sitting area.

## Through-Tenon Trimming on Organic Surfaces

When a through-tenon (leg, stretcher) passes through an organic surface (scooped seat, tapered leg), the tenon must be trimmed to follow the exact surface contour.

### Workflow

1. Build tenon (protrudes through the receiving body)
2. Add wedge slots on the tenon
3. **SplitBody** using the **entire receiving body** as the split tool (not a single face — the whole body follows scoop, fillets, and all surface geometry)
4. Use `sp.body_side(fragment, receiving_body, direction)` to classify fragments
5. Remove fragments on the 'outside' (excess tips above seat or beyond leg)
6. JOIN remaining fragments back to parent body
7. CUT mortise using the trimmed tenon as tool

### Direction for body_side

| Joint | Direction | Meaning |
|-------|-----------|---------|
| Leg through seat | `(0, 0, 1)` | Remove above seat |
| Stretcher through leg | Horizontal: `(leg_x - str_x, leg_y - str_y, 0)` | Remove beyond leg (tenon direction, Z zeroed) |

See `sp.body_side()`, `sp.classify_bodies()` in helpers-reference.md.
