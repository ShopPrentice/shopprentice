# Loft

## Overview

A **loft** interpolates a surface between two or more cross-section curves placed on different planes. Fusion threads an approximate cubic blend through the sections in order, producing a single smooth body.

**When to use:** Shape transitions that can't be extruded or revolved — tapered pockets, finials with rounded tips, branching tubes, organic sculpted forms, vases, hull/seat shells. Also the fastest way to combine several disparate profile shapes (square → circle → ellipse) into one solid.

**When NOT to use:** Constant-profile sweeps (use Sweep), rotationally symmetric shapes (use Revolve), precision joinery fits (hand-cut geometry with Extrude). Loft surfaces are approximate — don't rely on them for mating faces that need sub-mm accuracy.

**Strength/behaviour:** Loft is strictly sequential (section 0 → section 1 → … → section N). It cannot natively branch (1 → 3 → 1). Use multiple lofts + JOIN, or the Form/T-spline workspace (`Bridge` command) for organic branching.

## Variants

| Variant | Sections | Key API | Fixture |
|---------|----------|---------|---------|
| Basic multi-section | 2–N profiles | `loftSections.add(profile)` | `fixture_loft.py` |
| Rail-guided | 2 profiles + 1 rail curve | `centerLineOrRails.addRail(spline)` | `fixture_loft_rail.py` |
| Two-rail | 2 profiles + 2 rails (opposite envelopes) | `addRail(...)` twice | `fixture_loft_two_rails.py` |
| Centerline-guided | 2 profiles + 1 interior spline | `centerLineOrRails.addCenterLine(spline)` | `fixture_loft_centerline.py` |
| Closed (ring) | ≥3 profiles, loops back to first | `loft_inp.isClosed = True` | `fixture_loft_closed.py` |
| Point apex (sharp) | profile + `SketchPoint` | `setPointSharpEndCondition()` (default) | `fixture_loft_point.py` |
| Point apex (rounded) | profile + `SketchPoint` | `setPointTangentEndCondition(weight)` | `fixture_loft_ogive_{circle,square,ellipse}.py`, `fixture_loft_blob.py` |
| Surface | open curves (arcs, splines) | `loft_inp.isSolid = False` | `fixture_loft_surface.py` |
| Cut (shaped pocket) | 2 profiles as cut-tool | `FeatureOperations.CutFeatureOperation` + `participantBodies` | `fixture_loft_cut.py` |
| Branching (1→N→1) | multiple lofts + JOIN | N independent lofts sharing start/end profiles | `fixture_loft_manifold.py` |
| Irregular sections | closed fitted splines | `sketchFittedSplines.add(pts); sp.isClosed = True` | `fixture_loft_spline_{kidney,star,leaf}.py` |
| Multi-section smooth ends | N profiles + tangent point caps | Repeat the point-tangent recipe at both ends | `fixture_loft_wild_smooth.py`, `fixture_loft_blob.py` |

## Section Types

A loft section is any of the following. Mix-and-match within one loft:

| Type | How to add | Notes |
|------|-----------|-------|
| `Profile` | `sk.profiles.item(i)` | Closed region in a sketch. Most common. |
| `BRepFace` | `body.faces.item(i)` | Re-use an existing face as a section — handy for blending onto existing geometry. |
| `SketchPoint` | `sk.sketchPoints.add(P(x, y, 0))` | Degenerate (zero-radius) section — tip/apex. Combine with end conditions. |
| `ConstructionPoint` | component construction point | Like SketchPoint but in model space. |
| `Path` | open curve wrapped in a Path | Open-curve sections force `isSolid = False`. |
| `ObjectCollection` | coll. of contiguous profiles | Composite section made of adjacent profiles. Profiles must be **contiguous**; disjoint profiles don't work for branching. |

## Parameters (typical)

| Parameter | Expression | Unit | Description |
|-----------|-----------|------|-------------|
| `*_cx`, `*_cy` | `"0 cm"` | `cm` | Fixture anchor — centre of the loft footprint. Always expose so fixtures can be placed on a grid. |
| `*_h` | `"10 cm"` | `cm` | Total loft height. |
| `*_r1`, `*_r2`, … | `"2 cm"` | `cm` | Per-section radii or half-widths. |
| `*_weight` | `"2.0"` | `""` | Point-tangent weight (unitless, >0). 1.0 default; 4–6 for near-hemispherical caps. |

## Geometry Workflow

### 1. Sketch each section on its own plane

Offset construction planes from a base plane (`xYConstructionPlane` at z=0, then `setByOffset` with `"*_h * 0.25"` etc.). Always anchor sections off the fixture `cx`/`cy` params, not off origin.

```python
cpi = root.constructionPlanes.createInput()
cpi.setByOffset(root.xYConstructionPlane, VI("mf_h / 3"))
cp_lo = root.constructionPlanes.add(cpi)
sk = root.sketches.add(cp_lo)
ctr = sk.modelToSketchSpace(P(cx, cy, h / 3))  # convert model → sketch coords
sk.sketchCurves.sketchCircles.addByCenterRadius(P(ctr.x, ctr.y, 0), r)
```

### 2. Create the loft input and add sections in order

```python
loft_inp = root.features.loftFeatures.createInput(
    adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
loft_inp.loftSections.add(sk1.profiles.item(0))
loft_inp.loftSections.add(sk2.profiles.item(0))
loft_inp.loftSections.add(sk3.profiles.item(0))
```

`loftSections.add()` returns a `LoftSection` object — keep the reference if you need to set end conditions on it later.

### 3. Set options and add the feature

```python
loft_inp.isSolid = True                  # False → surface body (zero volume)
loft_inp.isClosed = False                # True → ring topology (≥3 sections)
loft_inp.isTangentEdgesMerged = True     # clean up coincident tangent seams
loft = root.features.loftFeatures.add(loft_inp)
loft.name = "MyLoft"
```

## End Conditions

End conditions apply only to the **first** and **last** sections (not middle sections — those are always interpolated). Call on the `LoftSection` returned from `loftSections.add()`.

| Method | Valid section | Effect |
|--------|--------------|--------|
| `setFreeEndCondition()` | any | Default — no imposed tangency. |
| `setDirectionEndCondition(angle, weight)` | sketch-curve sections | Exit in a specified direction. |
| `setTangentEndCondition(weight)` | `BRepEdge`-defined sections only | Tangent to the adjacent face. Ignored if section is a plain profile. |
| `setSmoothEndCondition(weight)` | `BRepEdge`-defined sections only | G2 (curvature-continuous) to adjacent face. |
| `setPointSharpEndCondition()` | `SketchPoint`/`ConstructionPoint` sections | Default for point — sharp cone/pyramid apex. |
| `setPointTangentEndCondition(weight)` | `SketchPoint`/`ConstructionPoint` sections | Rounded bullet/ogive apex. Weight controls fullness. |

### Rounded-Cap Recipe (bullet / egg / dome) — agent-usable

A plain `setPointTangentEndCondition(1.0)` with a far-away full-size section still looks conical. Three ratios, all of which must hold, produce a genuinely hemispherical cap:

| Ratio | Value | What it does |
|-------|-------|--------------|
| near-tip section distance | ≤ 5 % of total height | forces the surface to bend sharply near the apex |
| near-tip section radius | ≥ 0.85 × `R_max` | gives the curve something big to close against |
| tangent weight | 4.0 – 6.0 | makes the apex take-off nearly horizontal |

**Anti-pattern:** inserting a small transitional circle (0.2–0.3 × `R_max`) between the apex and the main body. That *pinches* the surface and makes the tip pointy regardless of weight. **Go directly from apex → full-radius section.**

**Complete pattern (both ends rounded, any wild mid-section path):**

```python
import adsk.core, adsk.fusion
P  = adsk.core.Point3D.create
VI = adsk.core.ValueInput.createByString
NEWBODY = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

# Each section: (z_frac_of_H, x_offset_frac_of_W, y_offset_frac_of_W, r_frac_of_R)
# r=None ⇒ SketchPoint apex. Sections with r close to 1.0 adjacent to the
# apex (zf≈0.05, rf≥0.85) are what produces the rounded dome.
sections = [
    (0.00,  0.0,  0.0, None),   # bottom apex
    (0.05,  0.0,  0.0, 0.90),   # ← KEY: near-hemisphere cap
    (0.25,  0.7,  0.0, 1.00),
    (0.50,  0.0,  1.0, 1.00),   # wild mid
    (0.75, -0.7,  0.0, 1.00),
    (0.95,  0.0,  0.0, 0.90),   # ← KEY: near-hemisphere cap
    (1.00,  0.0,  0.0, None),   # top apex
]

loft_inp = root.features.loftFeatures.createInput(NEWBODY)
tip_sections = []

for i, (zf, xf, yf, rf) in enumerate(sections):
    if zf == 0.0:
        plane = root.xYConstructionPlane
    else:
        cpi = root.constructionPlanes.createInput()
        cpi.setByOffset(root.xYConstructionPlane, VI(f"bl_h * {zf}"))
        plane = root.constructionPlanes.add(cpi)

    sk = root.sketches.add(plane)
    ctr = sk.modelToSketchSpace(P(cx + xf*W, cy + yf*W, zf*H))

    if rf is None:                                # apex
        pt = sk.sketchPoints.add(P(ctr.x, ctr.y, 0))
        tip_sections.append(loft_inp.loftSections.add(pt))
    else:
        sk.sketchCurves.sketchCircles.addByCenterRadius(
            P(ctr.x, ctr.y, 0), rf * R)
        loft_inp.loftSections.add(sk.profiles.item(0))

for s in tip_sections:
    s.setPointTangentEndCondition(VI("bl_weight"))   # weight ≥ 4.0

loft_inp.isSolid = True
loft_inp.isTangentEdgesMerged = True
root.features.loftFeatures.add(loft_inp)
```

Swap circle profiles for any closed profile (square, ellipse, fitted spline — see next section) without changing the apex logic. The tuple list is the only thing to edit when tuning shape; body radius stays parametric via `bl_rmax`. Live-validated: `fixture_loft_blob.py`, `fixture_loft_ogive_circle.py`.

## Rails vs Centerlines

Both are "guide curves" but they behave differently:

| | Rail | Centerline |
|---|------|-----------|
| Must touch a profile point? | **Yes** — rail endpoint must coincide with a sketch point on each profile | No — threads through profile interiors |
| Section orientation | Edge of each profile snaps to the rail | Sections rotate to stay perpendicular to the curve |
| Use case | Shape the *edge* envelope (boat hulls, handles) | Shape the *centreline path* (flexible tubing, snaking pockets) |
| API | `loft_inp.centerLineOrRails.addRail(curve)` | `loft_inp.centerLineOrRails.addCenterLine(curve)` |

You can use multiple rails (`fixture_loft_two_rails.py`) or a single centerline, but not a mix. A loft with only one rail and no profile-point coincidence will fail to compute.

### Critical Gotcha: Rail Tangency to Profile Planes

A rail **cannot be tangent to a profile plane** at the profile where it meets. Straight horizontal splines through the profile centre fail with "Rail is tangent to one or more profiles".

**Fix:** control points of the rail spline must have a component perpendicular to each profile plane at the endpoints. Sketch the rail on a plane like `xZConstructionPlane` offset to `y = cy`, and build control points *above* (for the bottom anchor) and *below* (for the top anchor) the profile plane so the tangent leaves/enters non-tangentially.

### Critical Gotcha: Sketch-Y on xZ-Parallel Planes

On an `xZConstructionPlane`-based sketch, **sketch-Y maps to negative model-Z**. A point you think is "above" in the sketch is actually "below" in the model. Always use `sketch.modelToSketchSpace(Point3D(...))` to convert model coordinates into the sketch's frame before placing rail control points:

```python
m1 = sk3.modelToSketchSpace(P(cx + offset, cy, h / 3))   # model point above bottom
midR1 = sk3.sketchPoints.add(P(m1.x, m1.y, 0))
```

Building rail points with raw (x, z) pairs will put them at the wrong z in the model — the rail will be tangent, and the loft will fail.

## Branching Topology (1 → N → 1)

Loft cannot branch natively. Two approaches:

### Approach A — Multiple lofts + JOIN (stays parametric)

1. Create shared start and end profiles (e.g., circular trunks at `z=0` and `z=H`).
2. Build **N independent lofts**, each using the shared profiles as first/last sections and its own branch profile(s) in the middle (different XY positions).
3. The same `Profile` object can be reused across multiple `LoftFeatureInput`s — it isn't consumed.
4. `combineFeatures` with `JoinFeatureOperation` to fuse the N bodies into one manifold.

Because the start and end profiles are identical across branches, the surfaces stitch cleanly at the trunks — no leaks or overlaps.

See `fixture_loft_manifold.py` for a 1 → 3 → 1 tube manifold.

### Approach B — Form workspace (T-spline, organic)

Switch to the Form environment, primitive a cylinder, use `Modify > Bridge` to connect extruded faces into smooth branches. One continuous surface, no seams. **Not parametric** in the timeline-dimension sense — edits are positional. Good for ergonomic handles, sculpted seats, organic junctions. Scripting T-splines from the API is possible but much more complex than Loft.

## Closed Spline Sections (irregular, adjustable profiles) — agent-usable

For kidney, star, teardrop, and other non-standard shapes. Two pieces compose: a **shape generator** (returns a list of `(dx, dy)` offsets from the section centre) and a fixed **helper** that turns offsets into a closed profile.

**Helper (never changes):**

```python
def add_closed_spline(sketch, ctr_sk, offsets_xy):
    pts = adsk.core.ObjectCollection.create()
    for (dx, dy) in offsets_xy:
        pts.add(P(ctr_sk.x + dx, ctr_sk.y + dy, 0))
    sp = sketch.sketchCurves.sketchFittedSplines.add(pts)
    sp.isClosed = True          # ← MANDATORY: open spline → no profile → loft fails
    return sp
```

Omitting `isClosed = True` silently leaves `sketch.profiles.count == 0` and the loft fails with "no valid profile".

**Shape generators (swap to change the silhouette):**

```python
import math

def kidney(scale, rot_deg=0, n=16):
    """Asymmetric bean: small on right, bulged on left."""
    rot = math.radians(rot_deg)
    return [
        (s := scale * (1.0 + 0.30 * math.sin(2*a) - 0.45 * math.cos(a)),
         (s * math.cos(a + rot), s * math.sin(a + rot)))[1]
        for a in (i * 2 * math.pi / n for i in range(n))
    ]

def star(outer, inner, rot_deg=0, lobes=5):
    """Alternating outer/inner radii → N-lobed spline."""
    rot = math.radians(rot_deg)
    n = lobes * 2
    return [
        ((outer if i % 2 == 0 else inner) * math.cos(i * 2*math.pi/n + rot),
         (outer if i % 2 == 0 else inner) * math.sin(i * 2*math.pi/n + rot))
        for i in range(n)
    ]

def cardioid(scale, rot_deg=0, n=24):
    """Teardrop/leaf — sharp at one end, round at the other."""
    rot = math.radians(rot_deg)
    offs = []
    for i in range(1, n + 1):             # skip a=0 (degenerate fit point)
        a = i * 2 * math.pi / (n + 1)
        r = scale * (1.0 - math.cos(a))
        x = r * math.cos(a);  y = r * math.sin(a)
        offs.append((x * math.cos(rot) - y * math.sin(rot),
                     x * math.sin(rot) + y * math.cos(rot)))
    return offs
```

**Stacking sections with twist (parametric, adjustable):**

```python
# (z_frac_of_H, scale_of_R, rotation_deg) — edit freely to tune the shape
specs = [(0.0, 1.00, 0.0),
         (0.5, 0.90, 24.0),
         (1.0, 1.00, 48.0)]

loft_inp = root.features.loftFeatures.createInput(NEWBODY)
for i, (zf, scale, rot) in enumerate(specs):
    plane = (root.xYConstructionPlane if zf == 0.0 else _offset_plane(zf))
    sk = root.sketches.add(plane)
    ctr = sk.modelToSketchSpace(P(cx, cy, zf * H))
    add_closed_spline(sk, ctr, star(R * scale, R * scale * 0.5, rot))  # swap: kidney / cardioid
    loft_inp.loftSections.add(sk.profiles.item(0))

loft_inp.isSolid = True
loft_inp.isTangentEdgesMerged = True
root.features.loftFeatures.add(loft_inp)
```

### Tuning knobs (what to edit to change the shape)

| Want to change | Edit |
|---------------|------|
| How lumpy / what shape | Swap generator: `kidney` ↔ `star` ↔ `cardioid`, or write your own formula returning `(dx, dy)` pairs |
| How smooth the silhouette | Increase fit-point count `n` (≥16 for smooth curves, 10 for angular stars) |
| How much twist | Rotation deltas between `specs` entries (try 0 → 30 → 60, or negative for counter-twist) |
| Taper | Scale deltas between `specs` entries (1.0 → 0.7 → 1.0 for pinched waist) |
| Number of lobes | `lobes` arg to `star`, or the `2a` term in `kidney` (try `3a` for trefoil) |
| Combine with rounded ends | Wrap the `specs` list with apex tuples + apply the Rounded-Cap Recipe above |

### Agent guidance

- **User asks for an adjustable/custom shape:** pick the closest generator (kidney / star / cardioid), expose `scale`, `rotation`, and `lobes`/`n` as user parameters, and let the user tweak in the palette.
- **User wants rounded closed ends on a splined body:** combine both recipes — use the rounded-cap section tuples at the ends and spline profiles for the mid-section sketches (same `add_closed_spline` helper).
- **Fitted splines smooth through fit points** — sharp stars become soft-petaled lobes. If the user wants real sharp corners, sketch with lines, not splines.
- **Fit-point `a=0` with a cardioid/cusp formula gives radius 0** — degenerate point at the origin kills the spline. Always start the loop at `i=1` for cusp curves.

Live-validated: `fixture_loft_spline_kidney.py`, `fixture_loft_spline_star.py`, `fixture_loft_spline_leaf.py`.

## Replication

Lofts usually aren't patterned — each has unique section geometry. For symmetric lofts (hulls, grips), build one side then Mirror the feature (sections, rails, and end conditions are all preserved). `isTangentEdgesMerged = True` merges coincident tangent edges on the *output body* so the surfaces read as one face — it doesn't replicate anything.

## Common Pitfalls

| Error | Cause | Fix |
|-------|-------|-----|
| "Rail is tangent to one or more profiles" | Rail tangent vector parallel to profile plane at the endpoint | Add control points with Z-component offset so rail enters non-tangentially |
| Rail ends in wrong place | Using raw (x, z) for points on xZ-parallel sketch (sketch-Y is −model-Z) | Use `sketch.modelToSketchSpace(Point3D(...))` for every rail control point |
| Point section gives sharp cone | Default `setPointSharpEndCondition` on SketchPoint section | Call `setPointTangentEndCondition(weight)` and follow the rounded-cap recipe |
| Rounded cap still looks pointy | Near-tip small circle pinches the surface | Go directly apex → full-radius section, weight ≥ 4 |
| Closed spline doesn't form a profile | Missing `sp.isClosed = True` | Set `isClosed = True` immediately after `add()` |
| Surface loft fails on mixed sections | Mixing open curves and closed profiles with `isSolid = True` | Set `isSolid = False` when any section is an open curve |
| Cut-loft creates new body instead of a pocket | Forgot `loft_inp.participantBodies = [target_body]` | Always assign participant bodies for `CutFeatureOperation` |
| Closed (ring) loft fails | Only 2 sections with `isClosed = True` | Need ≥3 sections to define a loop |
| Branching loft has leaks at trunks | Each branch uses a *different* start/end profile | Reuse the same `Profile` object across all N `LoftFeatureInput`s |
| Face-on-body sketch yields wrong profile | Sketching on a face creates multiple profiles | Pick by bounding-box area (smallest = drawn region) |

## Fixtures Reference

All 18 loft fixtures live in `tests/fixtures/fixture_loft*.py`. They arrange on a 25 cm grid for side-by-side comparison:

| Row | `x=0` | `x=25` | `x=50` |
|-----|-------|--------|--------|
| y=0 | Basic square→circle | Vase (3-section) | Rail-guided |
| y=25 | Cone (sharp apex) | Closed ring | Centerline tube |
| y=50 | Two-rail hull | Surface (isSolid=False) | Cut pocket |
| y=75 | Ogive circle → bullet | Ogive square → rounded obelisk | Ogive ellipse → egg |
| y=100 | 1→3→1 manifold | Serpentine (6 sections) | Blob (rounded caps) |
| y=125 | Kidney spline | Twisted star spline | Twisted cardioid/leaf |
| y=150 | Esherick lens-profile seat (3-section + rails + tangent top) | — | — |

Each fixture is self-contained and runnable individually via `execute_script(sandbox=True)`, or as a batch via the gallery loop used in development.

**See also:**
- `organic-shapes.md` — designer-level application doc for sculpted forms (turned legs, seat outlines, lens-profile seats, finial tips, scoops). The common organic-shape use cases have **self-contained inline recipes** there. This file is the deep reference for advanced loft variants (branching, closed ring, rails/centerlines, surface-only, loft-as-cut, closed-spline sections) — needed only when those variants are in scope.
- `fusion-api-rules.md` — general `modelToSketchSpace` rule on non-XY construction planes (relevant to rail control points).
