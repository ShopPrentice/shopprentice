# Organic Shapes

Designer's guide for sculpted, hand-shaped forms — turned legs, carved seats, free-form profiles, sculpted lenticular bodies. Read this topic when the design involves curves that can't be described by simple geometric primitives.

This file is the **application / routing** doc: identify the kind of organic shape you're making, pick the right technique, and jump to the feature-level reference for implementation details.

## Shape Taxonomy

| Class | Examples | Technique | Feature reference |
|-------|----------|-----------|-------------------|
| **1. Turned / spindled part** | Windsor leg, Esherick leg, pestle, spindle, pen | Half-profile fitted spline + Revolve | *§Revolved Profiles below* |
| **2. Flat-plan organic outline** | Rounded-hex seat footprint, kidney shelf, leaf-shaped tabletop | Closed fitted spline + Extrude | *§Organic Outlines below* |
| **3. Three-D organic solid** | Esherick seat (lens profile), chair back, hand grip, finial tip | Multi-section Loft + tangent end conditions | *§Lofted Organic Bodies below* |
| **4. Sculpted dish / saddle** | Windsor seat scoop, scooped pencil-box lid | Large-radius sphere revolve + CUT | *§Scoops and Carved Surfaces below* |
| **5. Character surface** | Ergonomic grips, animal shapes, tool handles with compound curves | Form workspace T-splines | Out of scripted scope (interactive only) |

Classes 1 – 4 are built inline in this doc — each has a self-contained recipe below with the exact API calls needed. Agents don't need to load any other topic file to build the common organic shapes. For **advanced loft variants only** (branching manifolds, closed-ring topology, rail/centerline guides, surface-only lofts, loft-as-CUT pockets, irregular closed-spline cross-sections like kidney/star/cardioid), see `loft.md` — deep feature reference, don't preload unless a build actually needs those variants.

**Scoops (class 4) and through-tenon trimming are techniques applied *on top of* any base body** — they're documented below regardless of how the base body was constructed.

## Core Workflow: Approximate → Refine → Capture

Organic shapes require iteration. The agent can't guess the exact curve the user wants from a description alone. The workflow:

1. **Agent builds approximate profile** — place spline control points based on description ("thick at lower third, thin at ends") or reference photo analysis
2. **Execute and present** — user sees the 3D result in Fusion
3. **User edits the sketch** — drags spline fit points in Fusion UI to refine the curve
4. **Agent captures changes** — use `get_timeline_state(index, include_sketches=True)` to read the updated fit point positions
5. **Agent updates script** — replace the hardcoded control points with captured values
6. **Repeat** until the user is satisfied

This loop is fast because the user edits visually (what they're good at) and the agent handles code (what it's good at). It applies to **all** classes — a revolved leg profile, a closed plan outline, or the section sketches of a lofted body.

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

For a lofted class-3 body the same loop applies across multiple section sketches — capture every edited sketch, remap to model space, and bake the updated fit points back into the script's hard-coded point lists. See `examples/esherick-stool/esherick_stool.py` for a full furniture-scale build that uses this pattern (`_BOT_PLAN`, `_MID_PLAN`, `_TOP_PLAN` are the three baked point lists, updated in place when the user edits the corresponding sketches).

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

## Lofted Organic Bodies (Class 3)

For **three-dimensional organic solids** where the silhouette changes along the vertical axis and can't be produced by Extrude-then-fillet without visible creases — seats with pillow edges, chair-back shells, sculpted handles, finial tips, twisted columns.

### When to prefer a lofted body over extrude + fillet

| Symptom | Extrude + fillet limit | Lofted body solution |
|---------|-----------------------|----------------------|
| Flat-topped seat needs a rolled edge, not a filleted one | Fillet radius creates a uniform-radius corner — reads as machined | 3-section loft with `setDirectionEndCondition(angle="0 deg", weight)` on top and bottom — flat face flows into side with zero slope, gradually building curvature |
| Side profile should bulge in the middle | Impossible with a single extrude | Middle section at 100 % scale, top/bottom sections shrunk (e.g., 0.70 ×) → lenticular body |
| End should be a **rounded tip** (bullet, egg, dome) | Fillet of a cone → still cone-like | SketchPoint section + `setPointTangentEndCondition(weight)` with a near-tip full-radius section |

### Recipe: lens-profile body with tangent flat top/bottom

This is the Esherick-seat pattern: a shallow pillow with flat-ish top, bulging midsection, and tapered underside, where the flat top rolls smoothly into the side without any fillet feature. Works for seat boards, chair-back shells, lid tops — anywhere a shallow solid needs a soft perimeter.

The **plan outline** (`base_pts`, list of `(x, y)` tuples) comes from §Organic Outlines — a closed fitted spline, typically 12 control points for a clipped-triangle hex or 8 for a kidney. The same outline is used at all three sections, just scaled about its centroid `(ctr_x, ctr_y)`.

```python
# Parameters: seat_t (thickness), bot_scale / top_scale (0.70 both for symmetric
# pillow, or e.g. 0.70 / 0.95 for asymmetric with flatter top), blend_weight
# (3.0 is a good default; higher = longer flat plateau before slope builds).

def _scale_pts(pts, s):
    return [(ctr_x + (x - ctr_x) * s, ctr_y + (y - ctr_y) * s) for x, y in pts]

def _add_section(plane, z_val, pts_xy, name):
    sk = comp.sketches.add(plane); sk.name = name
    coll = adsk.core.ObjectCollection.create()
    for mx, my in pts_xy:
        p = sk.modelToSketchSpace(P(mx, my, z_val))
        coll.add(P(p.x, p.y, 0))
    sk.sketchCurves.sketchFittedSplines.add(coll).isClosed = True
    return sk

sk_bot = _add_section(comp.xYConstructionPlane, 0,
                      _scale_pts(base_pts, bot_scale), "Seat_Bot")

mid_pl = sp.off_plane(comp, comp.xYConstructionPlane, "seat_t / 2", "Seat_MidPl")
sk_mid = _add_section(mid_pl, seat_t / 2, base_pts, "Seat_Mid")  # full scale

top_pl = sp.off_plane(comp, comp.xYConstructionPlane, "seat_t", "Seat_TopPl")
sk_top = _add_section(top_pl, seat_t,
                      _scale_pts(base_pts, top_scale), "Seat_Top")

loft_inp = comp.features.loftFeatures.createInput(NEWBODY)
sec_bot = loft_inp.loftSections.add(sk_bot.profiles.item(0))
loft_inp.loftSections.add(sk_mid.profiles.item(0))
sec_top = loft_inp.loftSections.add(sk_top.profiles.item(0))
# angle="0 deg" → surface leaves section tangent to its plane (horizontal
# on the horizontal top/bottom sections); weight stretches the flat region.
sec_bot.setDirectionEndCondition(VI("0 deg"), VI("blend_weight"))
sec_top.setDirectionEndCondition(VI("0 deg"), VI("blend_weight"))
loft_inp.isSolid = True
loft_inp.isTangentEdgesMerged = True
seat_body = comp.features.loftFeatures.add(loft_inp).bodies.item(0)
seat_body.name = "Seat"
```

**Tuning knobs:** `bot_scale` / `top_scale` control the undertuck and top flatness. `blend_weight` controls how gradually slope builds — 1.0 is a tight rollover right at the edge (looks abrupt), 3.0 is a genuine flat plateau that rolls into the side, 5.0+ is a near-flat top with a very late hard rollover.

### Recipe: rounded apex tip (bullet / egg / dome)

For finials, drawer pulls, pestle tips, turned-look caps. Default loft-to-a-point produces a sharp cone; these three ratios together produce a hemispherical cap:

| Ratio | Value |
|-------|-------|
| Near-tip section z-distance from apex | ≤ 5 % of total height |
| Near-tip section radius | ≥ 0.85 × R_max |
| Tangent weight | 4.0 – 6.0 |

```python
# Base circle at z=0, near-tip full-width section at z=0.05*h, apex at z=h.
sk_base = comp.sketches.add(comp.xYConstructionPlane)
c = sk_base.sketchCurves.sketchCircles.addByCenterRadius(P(cx, cy, 0), r_max)
sk_base.sketchDimensions.addDiameterDimension(c,
    P(cx + r_max + 0.5, cy, 0)).parameter.expression = "r_max * 2"

near_pl = sp.off_plane(comp, comp.xYConstructionPlane, "h * 0.05", "NearTipPl")
sk_near = comp.sketches.add(near_pl)
sk_near.sketchCurves.sketchCircles.addByCenterRadius(
    P(cx, cy, 0.05 * h), r_max * 0.9)

apex_pl = sp.off_plane(comp, comp.xYConstructionPlane, "h", "ApexPl")
sk_apex = comp.sketches.add(apex_pl)
apex_sk = sk_apex.modelToSketchSpace(P(cx, cy, h))
apex = sk_apex.sketchPoints.add(P(apex_sk.x, apex_sk.y, 0))

loft_inp = comp.features.loftFeatures.createInput(NEWBODY)
loft_inp.loftSections.add(sk_base.profiles.item(0))
loft_inp.loftSections.add(sk_near.profiles.item(0))
tip = loft_inp.loftSections.add(apex)
tip.setPointTangentEndCondition(VI("4.0"))  # weight ≥ 4 for dome
loft_inp.isSolid = True
comp.features.loftFeatures.add(loft_inp).bodies.item(0).name = "Finial"
```

**Anti-pattern:** inserting a small (0.2–0.3 × R_max) transitional circle between the apex and the main body — it *pinches* the surface and makes the tip pointy regardless of weight. Go directly from apex → full-radius section.

### Plan outline still matters

A lofted class-3 body still has a plan outline at each section. The **class 2 techniques** from §Organic Outlines (closed fitted splines, clipped-triangle hex, convex edge bulging) are used to draw the plan at each z-level — the loft just stacks and interpolates them into a solid. Scale the same outline differently at each section to get the lenticular profile; use the **same generator** with different rotation between sections to get a twist.

### Leg / joinery anchoring on a class-3 body

When downstream features (legs, mortises) need to attach to a class-3 body, derive their anchors from the *actual* edited geometry, not the symmetric nominal:

- **Seat centroid**: compute as the average of the mid-section's captured fit points (not `seat_d/2, seat_w/2`).
- **Leg directions**: use `atan2(corner_y - centroid_y, corner_x - centroid_x)` on the captured mid-section corner points (not the synthesized triangle vertices).

`examples/esherick-stool/esherick_stool.py` demonstrates this override — `tri_cx`, `tri_cy`, and `leg_angles_rad` are all recomputed from `_MID_PLAN` so the three legs land on the user-edited corners even when the sculpted shape shifts the centroid off-center.

### Advanced loft variants (optional deep reference)

For shapes beyond these two recipes — branching bodies (1 → N → 1 manifold), closed-ring topology, surface-only lofts, rail/centerline guides, closed-spline generators for kidney/star/cardioid cross-sections, loft-as-CUT pockets — see **`loft.md`**. It's a comprehensive feature reference covering all 12 loft variants. **Don't preload it** for a straightforward organic seat or finial — the two recipes above are self-contained.

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
