# Fusion 360 Parametric Furniture Modeling

You are generating a Fusion 360 Python script to build a parametric furniture model. Follow these rules strictly.

## Design Philosophy: Think Like a Furniture Maker at the Fusion 360 UI

Before writing any code, plan the modeling steps the way an experienced designer would approach the Fusion 360 UI — component by component, feature by feature. You are not a software engineer writing a program. You are a craftsperson building a piece of furniture, and the API is just your hands on the mouse.

1. **Plan before building.** Before writing code, outline every modeling step in order: which component, which feature, which replication strategy. Think: "If I were clicking through the Fusion 360 UI, what would I do next?" Write the plan as a step list (see Design-First Planning below).

2. **Build one, replicate the rest.** Prefer building one template and using **Mirror** and **Rectangular Pattern** features for the rest. If you find yourself reaching for a Python `for` loop to create geometry, stop — use a Fusion 360 pattern instead. **Exception:** Per-corner joinery (dovetails, box joints) where CUT/JOIN targets differ per corner requires independent construction at each corner — mirrors of CUT/JOIN extrudes inherit the original `participantBodies` reference and fail.

3. **Everything parametric.** When the user changes any dimension in Modify > Change Parameters, the entire model must recompute automatically — lengths, mirror positions, pattern counts, everything.

4. **Always organize with components.** Group related bodies into named components (e.g., Sides, Shelves, Top, Kick — or Case, Bottom, Lid for boxes). Features live inside their respective components; cross-component operations (like CUT) live in root via assembly proxies. Even small boxes benefit from component structure — clearer timeline, feature isolation, and reusable assembly patterns.

5. **Feature-based modeling only.** Every shape is: Sketch > Constrain dimensions parametrically > Extrude. This creates timeline features that recompute when parameters change.

6. **If it fits, it cuts.** When body A sits inside body B, use A as a CUT tool to create its void in B — never draw the void as a separate sketch. The body IS the perfect-fit shape: one source of truth, zero redundant geometry. This applies to any mechanical mate, not just joinery:
   - **Joinery:** tenon CUTs mortise, tail CUTs socket, tongue CUTs groove. Then JOIN the tenon/tail to its owning board.
   - **Panels:** lid CUTs its slot in the front board, bottom panel CUTs its groove in each case board.
   - **Openings:** door CUTs its frame opening, drawer front CUTs its cavity, sliding panel CUTs its track.
   - **Hardware/inserts:** wedge CUTs its socket, hinge leaf CUTs its recess, inlay CUTs its pocket.

   **Recognition rule:** if you're about to sketch a void that matches an existing body's shape, stop — CUT the body instead (`keepTool=True`). If the fitting body also joins a parent, CUT first, then JOIN.

7. **No overlapping bodies.** Two physical bodies can never occupy the same space. When bodies share volume, one must CUT the other (rule 6). This must hold not just at script time but **across all valid parameter changes** — if the user increases `lid_thick`, the lid must not collide with the case boards. Achieve this by defining body positions and sizes in terms of shared parameters so they stay in agreement:
   - **Derive, don't hardcode boundaries.** A lid at Z = `open_height` with thickness `lid_thick` means `open_height` must equal `box_height - lid_thick`. If both are independent parameters, the user can set values that overlap.
   - **Use CUT to enforce fit.** When body A fits inside body B, CUT A into B (rule 6). The void updates automatically when A's dimensions change — no overlap possible.
   - **Validate with `check_interference`** after every phase. Clean designs have zero interferences at any parameter value, not just the defaults.

8. **Build order matters.** Cut grooves and dados **before** joining corner joinery (dovetails, box joints). Side boards span only their initial footprint before tails are joined; groove tool bodies that extend beyond the board only CUT the material that exists at that moment. When tails are later joined, they attach ungrooved — producing clean, stopped grooves at corners with zero extra geometry. This "implicit stopped groove" technique eliminates manual stop calculations.

## Parameter Planning

Choosing which values are user parameters vs. derived is critical. The goal: adjusting any single parameter always produces a clean, valid model — no broken geometry, no asymmetric gaps, no overlapping bodies.

**Principle: parameterize the envelope and the parts; derive the fit.** Furniture dimensions form constraint chains — for example, `table_h = leg_h + top_thick + gap`. When multiple dimensions are linked by a sum, make the physically meaningful ones user parameters and derive the leftover:

1. **Envelope dimensions** (overall height, width, depth) — always user parameters. These are what the customer specifies or the maker measures in the room.
2. **Part dimensions** (leg height, rail width, stock thickness) — user parameters when they represent a design choice the maker controls ("I want 26-inch legs", "I'm using 3/4-inch stock").
3. **Fit dimensions** (gaps, clearances, internal offsets) — derived. These are whatever is left over after the envelope and parts are placed.

When a constraint chain has N terms, at most N-1 can be independent. Choose the least meaningful dimension to derive — typically an internal gap or clearance that the maker doesn't independently decide.

**Example — table height chain:**
- User params: `table_h` (overall height), `leg_h` (leg length), `top_thick` (stock choice)
- Derived: `top_gap = table_h - leg_h - top_thick` (clearance between leg top and tabletop underside)
- The maker decides the table height, leg length, and stock. The gap is a consequence — not a design choice.

**Example — box height chain:**
- User params: `box_height` (overall), `board_thick` (stock), `lid_thick` (stock), `bottom_thick` (stock)
- Derived: `open_height = box_height - board_thick - lid_thick - bottom_thick` (usable interior)
- Or alternatively: `open_height` is the user param and `box_height` is derived — whichever the maker thinks in terms of.

**Principle: define count, derive spacing.** When elements repeat across a dimension (tails, slats, fingers), make the *count* a user parameter and derive the *spacing* from `board_dimension / count`. This guarantees elements always fill the space exactly. The alternative — defining element width + gap width independently and using `floor()` to compute count — leaves uneven remainders that break symmetry.

**Principle: every sketch position must be parametric.** Evaluating a parameter at script time (`ev("param")`) bakes the current value into the sketch geometry. If the user later changes the parameter in Change Parameters, the sketch doesn't move. Always add a sketch dimension linked to the parameter expression so Fusion recomputes the position automatically.

**Principle: sketch positions are relative to the features they interact with.** When a sketch CUTs or modifies a body (e.g., an arch CUT on a rail), its position must be defined relative to that body's features — not as an absolute coordinate. For example, an arch baseline should be dimensioned with `leg_h - front_rail_h` (the rail's bottom Z), not drawn at an `ev()` position. When the user changes `front_rail_h`, the arch follows the rail. This applies to all sketches: use `modelToSketchSpace` for approximate positions, then add parametric dimensions with expressions that reference the parent body's parameters.

**How to decide:**
1. Ask: "If the user changes this value, does the model stay valid?" If increasing a width could overflow available space, that width should be derived from a count instead.
2. Ask: "Does changing this parameter require other values to adjust?" If yes, those other values must be derived expressions, not independent parameters.
3. Ask: "Is any geometry positioned using a value computed at script time?" If yes, add a sketch dimension with a parameter expression so it updates live.
4. Ask: "Would a maker write this dimension on a cut list or sketch?" If yes, it should be a user parameter. If it's just "whatever's left over" after other dimensions are placed, derive it.

**Example — dovetails:** `dt_tail_w` (tail width) + `dt_tail_count` are user parameters. `dt_pin_w = board_h / dt_tail_count - dt_tail_w` is derived. Changing count or tail width always produces evenly-spaced tails with symmetric half-pins. If `dt_pin_w` were an independent parameter instead, the user could easily set values where tails don't fit the board.

## Design-First Planning

Before writing code for any piece, produce a step-by-step modeling plan structured like this:

```
Components: Sides, Shelves, Top, Kick

1. Sides component
   - Extrude left side board (NewBody)
   - Extrude right side board (NewBody)

2. Shelves component
   - Construction planes: YMid, XMid, shelf offset
   - Extrude ONE shelf body (NewBody)
   - Extrude ONE tenon (NewBody)
   - Mirror tenon across YMid → back tenon
   - Mirror [tenon + mirror] across XMid → right side tenons
   - JOIN all 4 tenons into shelf body
   - Body pattern shelf along Z (count=n_shelves, spacing=shelf_spacing)

3. Shelf mortises (root, assembly proxies)
   - CUT left side with ALL shelf proxies (keepTool=True)
   - CUT right side with ALL shelf proxies (keepTool=True)

4. ... (continue for each component)
```

Each step maps to exactly one Fusion 360 feature. No Python loops, no batch logic — just the sequence a designer would follow in the timeline.

## Fusion 360 API Rules

### Design Mode (MUST be first)
```python
design.designType = adsk.fusion.DesignTypes.ParametricDesignType
```
Set this BEFORE accessing `design.userParameters`. Without it: `RuntimeError: this is not a parametric design`.

### Do NOT Use
- `TemporaryBRepManager` — creates static geometry inside `BaseFeature` blocks. Parameters exist in Change Parameters but changing them does NOT update geometry.
- `createByReal(value_in_cm)` for parameter creation — shows confusing cm values in the UI.
- Python `int()` at script time for pattern counts — use `floor()` in parameter expressions instead.
- **Python `for` loops for geometry replication** — use Rectangular Pattern or Mirror features instead. A `for` loop creates N independent features that don't update when count changes. A pattern is one parametric feature that recomputes automatically. **Exception:** Bodies with CUT/JOIN in their timeline history MUST use `for` loops — body patterns replay those operations, creating ghost bodies (see Body Pattern Ghost Bodies under Replication Strategy).

### User Parameters
Create with `ValueInput.createByString("60 in")` so Change Parameters shows readable values:
```python
params.add("total_length", adsk.core.ValueInput.createByString("60 in"), "in", "Overall length")
```

### Derived Parameters
Use expression strings referencing other parameters. These auto-recompute:
```python
params.add("shoulder_length",
           adsk.core.ValueInput.createByString("total_length - 2 * leg_size"),
           "in", "Shoulder length between legs")
```

### Dimensionless Parameters (counts)
For counts derived from `floor()`, use empty string `""` as the unit:
```python
params.add("n_slats", adsk.core.ValueInput.createByString("floor(shoulder_length / slat_width)"), "", "Number of slats")
```
These update automatically when referenced dimensions change.

### Sketch Plane Selection

Two valid approaches, depending on the project:

**Approach A: Sketch on body faces.** When creating a feature that relates to an existing body (joints, pockets, decorative details), find the relevant face on that body and sketch directly on it. The sketch plane inherits the body's position — no construction plane offset to keep in sync.

```python
def find_face(body, axis, direction):
    """Find outermost planar face along axis in direction (+1=max, -1=min).
    Uses abs(normal) because face.geometry.normal doesn't always match
    the outward normal — it's the mathematical plane normal."""
    best = None
    best_val = -1e10 if direction > 0 else 1e10
    for i in range(body.faces.count):
        face = body.faces.item(i)
        geom = face.geometry
        if isinstance(geom, adsk.core.Plane):
            if abs(getattr(geom.normal, axis)) > 0.9:
                fv = getattr(face.pointOnFace, axis)
                if (direction > 0 and fv > best_val) or (direction < 0 and fv < best_val):
                    best_val = fv
                    best = face
    return best

# Example: sketch on the front face (min-Y) of a rail body
front_face = find_face(rail_body, "y", -1)
sk = comp.sketches.add(front_face)
```

**Extrude direction on body faces:** The default (positive) extrude direction on a face sketch follows `face.evaluator.getNormalAtPoint()` — the true outward normal, pointing AWAY from the body. Use `flip=True` (NegativeExtentDirection) for CUT extrudes on body faces so the cut goes INTO the body.

**Coincident geometry on body-face sketches:** When sketch lines fully coincide with face boundary edges (e.g., an arch baseline at the face corner), Fusion merges them and fails to create separate profiles. Fix: project the face edge via `sk.project(edge)`, then draw the arc from the projected line's sketch points. The projected edge + arc properly split the face. Position dimensions become unnecessary since the projection is already parametric.

**Approach B: Construction planes + `probe_sketch_axes`.** Construction planes can have flipped sketch axes, but this is fully solved by probing. Use `modelToSketchSpace` to discover the real axis mapping at runtime, then assign H/V dimensions accordingly. This approach is simpler when the design is planned in model coordinates — no face-finding or vertex-projection needed. See `sketch_rect_model` in Standard Helpers below for the complete implementation.

```python
def probe_sketch_axes(sk):
    """Which model axis maps to sketch-X (h) and sketch-Y (v)."""
    Point3D = adsk.core.Point3D
    o  = sk.modelToSketchSpace(Point3D.create(0, 0, 0))
    ux = sk.modelToSketchSpace(Point3D.create(1, 0, 0))
    uy = sk.modelToSketchSpace(Point3D.create(0, 1, 0))
    uz = sk.modelToSketchSpace(Point3D.create(0, 0, 1))
    deltas = {
        "x": (ux.x - o.x, ux.y - o.y),
        "y": (uy.x - o.x, uy.y - o.y),
        "z": (uz.x - o.x, uz.y - o.y),
    }
    h_axis = max(deltas, key=lambda a: abs(deltas[a][0]))
    v_axis = max(deltas, key=lambda a: abs(deltas[a][1]))
    return h_axis, v_axis
```

**CRITICAL: `probe_sketch_axes` returns axis names but NOT signs.** On non-XY construction planes, a model axis can map to the *negative* sketch direction. For example, on an XZ-offset plane, model +Z maps to sketch -Y. If you build dimension expressions assuming positive mapping, geometry lands at mirrored positions.

**Fix — probe signs with a delta point:**
```python
def probe_sketch_signs(sk):
    """Return (h_axis, v_axis, h_sign, v_sign) for a sketch.
    h/v_sign is +1 if increasing model coordinate → increasing sketch coordinate, else -1."""
    h_axis, v_axis = probe_sketch_axes(sk)
    P = adsk.core.Point3D
    sc = sk.modelToSketchSpace(P.create(0, 0, 0))
    delta = {"x": P.create(1, 0, 0), "y": P.create(0, 1, 0), "z": P.create(0, 0, 1)}
    sd_h = sk.modelToSketchSpace(delta[h_axis])
    sd_v = sk.modelToSketchSpace(delta[v_axis])
    h_sign = 1 if (sd_h.x - sc.x) > 0 else -1
    v_sign = 1 if (sd_v.y - sc.y) > 0 else -1
    return h_axis, v_axis, h_sign, v_sign
```

Use the sign when building offset expressions. If `v_sign` is negative, an expression like `center - half_length` must become `center + half_length` in sketch space:
```python
op = " - " if v_sign > 0 else " + "
offset_expr = v_center_expr + op + "half_length"
```

`sketch_rect_model` already handles this internally (it converts two model-space corners via `modelToSketchSpace`, so signs are implicit). You only need explicit sign detection for custom sketch geometry like stadium shapes (slots, arcs) where you build offset expressions manually.

**Sketch plane preference (follow this order):**

1. **Existing body face (preferred).** If a planar face already exists at the needed location, sketch on it. This is how a designer works in the UI — click the face, start sketching. No construction plane needed. Use `sketch_rect_model` with the face as the plane argument; it works on BRepFaces the same as on construction planes.

2. **Construction plane (only when required).** Use only when one of these applies:
   - **No body exists yet** — first body in a component has no face to sketch on.
   - **Midplane for Mirror or Pattern** — no face exists at the midpoint.
   - **Sketch will be mirrored** — face-based sketches CANNOT be mirrored. MirrorFeature fails with NO_TARGET_BODY because the mirror can't find an equivalent face on the mirrored side.
   - **Root-level sketch on a component body** — assembly proxy faces CANNOT host sketches. `comp.sketches.add(proxy_face)` throws `RuntimeError: invalid argument planarEntity`. Root-level cross-component operations must use construction planes.

**During design-first planning, audit every sketch plane:** for each sketch in the plan, ask "does a body face already exist here?" If yes, use it. Only reach for a construction plane if one of the four exceptions above applies. Fewer construction planes = cleaner timeline, faster recompute, and geometry that moves parametrically with the body it belongs to.

### Sketch + Extrude Workflow
```python
# 1. Sketch with approximate geometry
sk = comp.sketches.add(plane)
rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)

# 2. Add geometric constraints FIRST — H/V constraints lock line orientation
gc = sk.geometricConstraints
gc.addHorizontal(rect[0])
gc.addHorizontal(rect[2])
gc.addVertical(rect[1])
gc.addVertical(rect[3])

# 3. Constrain dimensions parametrically
d_w = sk.sketchDimensions.addDistanceDimension(...)
d_w.parameter.expression = "slat_width"  # linked to user parameter

# 4. Extrude with parametric distance
ext_input = comp.features.extrudeFeatures.createInput(profile, operation)
ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByString("body_height"))
```

### Geometric Constraints on Sketch Lines (CRITICAL)

**Every sketch line that should be horizontal or vertical MUST have an explicit geometric constraint.** `addTwoPointRectangle` and `addByTwoPoints` create lines at the correct positions initially, but without explicit `addHorizontal`/`addVertical` constraints, lines can skew when parameters change — rectangles become parallelograms, horizontal edges tilt.

**Rule:** After creating any sketch line, ask: "Should this line stay horizontal or vertical when parameters change?" If yes, add the constraint. Omit H/V constraints on:
- Intentionally angled lines (tapers, chamfer profiles, etc.)
- Arch baselines where both endpoints share the same model Z (already horizontal by construction). On offset planes, `addHorizontal` can perturb arc geometry enough to split thin bodies via CUT.

```python
# Rectangle — constrain all 4 sides
rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)
gc = sk.geometricConstraints
gc.addHorizontal(rect[0])  # bottom
gc.addHorizontal(rect[2])  # top
gc.addVertical(rect[1])    # right
gc.addVertical(rect[3])    # left

# Arch baseline — DO NOT constrain. Both endpoints share the same Z
# (model coordinate), so the line is already horizontal. Adding addHorizontal
# on offset planes can perturb the arc geometry, causing the CUT to split
# thin bodies. The arc's shared sketch points (endSketchPoint/startSketchPoint)
# keep the profile closed without constraints.
arch_line = sk.sketchCurves.sketchLines.addByTwoPoints(p1, p2)
sk.sketchCurves.sketchArcs.addByThreePoints(
    arch_line.endSketchPoint, mid_pt, arch_line.startSketchPoint)

# Taper triangle — constrain the H and V edges, leave the angled line free
# IMPORTANT: H/V constraints are in SKETCH space, not model space.
# On XZ planes: model-X → sketch-H, model-Z → sketch-V (inverted)
# On YZ planes: model-Z → sketch-H (inverted), model-Y → sketch-V
# A line that is "horizontal in model" (same Z, varying X or Y) may be
# VERTICAL in sketch space on YZ planes. Always check probe_sketch_axes
# or modelToSketchSpace to determine the correct constraint direction.
bot = lines.addByTwoPoints(sa, sb)     # same Z, varies in X or Y
lines.addByTwoPoints(sb, sc)           # angled taper — NO constraint
vert = lines.addByTwoPoints(sc, sa)    # same X or Y, varies in Z

# XZ plane example (model-X → sketch-H, model-Z → sketch-V):
sk.geometricConstraints.addHorizontal(bot)   # bot varies in model-X → sketch-H
sk.geometricConstraints.addVertical(vert)    # vert varies in model-Z → sketch-V

# YZ plane example (model-Y → sketch-V, model-Z → sketch-H):
sk.geometricConstraints.addVertical(bot)     # bot varies in model-Y → sketch-V
sk.geometricConstraints.addHorizontal(vert)  # vert varies in model-Z → sketch-H
```

### Extrude Operations
| Operation | Use For |
|-----------|---------|
| `NewBodyFeatureOperation` | New bodies (legs, rails, slat bodies) |
| `CutFeatureOperation` | Mortises, grooves (removing material) |
| `JoinFeatureOperation` | Tenons, tongues (adding material to existing body) |

### participantBodies (CRITICAL)
When doing Cut or Join near other bodies, you MUST specify which body to target:
```python
ext_input.participantBodies = [target_body]  # Python list, NOT ObjectCollection!
```
Using `ObjectCollection` causes `TypeError`. Using no participant bodies causes accidental merging or cutting of adjacent bodies.

## Standard Helpers

These reusable helpers form the foundation of the model-coordinate workflow. The caller specifies everything in model coordinates using parameter expressions; the helpers handle all sketch-space complexity.

### `ev()` — Dual-Mode Parameter Access
```python
def ev(e):
    """Evaluate a parameter name or expression, returning value in cm."""
    p = params.itemByName(e)
    return p.value if p else design.unitsManager.evaluateExpression(e, "cm")
```
Use for computing approximate sketch positions. Actual parametric behavior comes from dimension expressions, not `ev()` values.

### `sketch_rect_model()` — Parametric Rectangle in Model Coordinates
```python
def sketch_rect_model(plane, model_origin, model_size, name="Sk"):
    """
    Parametric rectangle in model coordinates.
    model_origin: (x_expr, y_expr, z_expr) — parameter expressions
    model_size:   {axis: expr, axis: expr} — 2 model-axis sizes
    Returns: (sketch, profile)
    """
    sk = root.sketches.add(plane)
    sk.name = name
    h_axis, v_axis = probe_sketch_axes(sk)

    # Evaluate model-space corners
    ox, oy, oz = ev(model_origin[0]), ev(model_origin[1]), ev(model_origin[2])
    corner = {"x": ox, "y": oy, "z": oz}
    for a, expr in model_size.items():
        corner[a] += ev(expr)

    # Convert to sketch space
    sk_o = sk.modelToSketchSpace(Point3D.create(ox, oy, oz))
    sk_f = sk.modelToSketchSpace(
        Point3D.create(corner["x"], corner["y"], corner["z"]))

    # Draw rectangle + lock orientation
    rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(
        Point3D.create(sk_o.x, sk_o.y, 0),
        Point3D.create(sk_f.x, sk_f.y, 0))
    gc = sk.geometricConstraints
    gc.addHorizontal(rect[0])
    gc.addHorizontal(rect[2])
    gc.addVertical(rect[1])
    gc.addVertical(rect[3])

    # Parametric dimensions
    d = sk.sketchDimensions
    axis_to_origin = {
        "x": model_origin[0], "y": model_origin[1], "z": model_origin[2]}
    mid_x = (sk_o.x + sk_f.x) / 2
    mid_y = (sk_o.y + sk_f.y) / 2
    dy = -1 if sk_f.y >= sk_o.y else 1
    dx = -1 if sk_f.x >= sk_o.x else 1

    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation

    # Width (sketch-X) → h_axis model size
    d.addDistanceDimension(
        rect[0].startSketchPoint, rect[0].endSketchPoint,
        H, Point3D.create(mid_x, sk_o.y + dy, 0)
    ).parameter.expression = model_size[h_axis]

    # Height (sketch-Y) → v_axis model size
    d.addDistanceDimension(
        rect[1].startSketchPoint, rect[1].endSketchPoint,
        V, Point3D.create(sk_f.x - dx, mid_y, 0)
    ).parameter.expression = model_size[v_axis]

    # H origin offset
    d.addDistanceDimension(
        sk.originPoint, rect[0].startSketchPoint,
        H, Point3D.create(sk_o.x / 2, sk_o.y + 2 * dy, 0)
    ).parameter.expression = axis_to_origin[h_axis]

    # V origin offset
    d.addDistanceDimension(
        sk.originPoint, rect[0].startSketchPoint,
        V, Point3D.create(sk_o.x + dx, sk_o.y / 2, 0)
    ).parameter.expression = axis_to_origin[v_axis]

    return sk, sk.profiles.item(0)
```

### Other Standard Helpers
```python
def ext_new(prof, dist, name="Ext"):
    """Extrude a profile as a new body."""
    inp = root.features.extrudeFeatures.createInput(
        prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString(dist))
    f = root.features.extrudeFeatures.add(inp)
    f.name = name
    return f

def ext_op(prof, dist_expr, op, body, name="Ext"):
    """Extrude a profile as CUT or JOIN into an existing body."""
    inp = root.features.extrudeFeatures.createInput(prof, op)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString(dist_expr))
    inp.participantBodies = [body]
    f = root.features.extrudeFeatures.add(inp)
    f.name = name
    return f

def off_plane(base, expr, name="Pl"):
    """Create an offset construction plane."""
    inp = root.constructionPlanes.createInput()
    inp.setByOffset(base, adsk.core.ValueInput.createByString(expr))
    p = root.constructionPlanes.add(inp)
    p.name = name
    return p

def combine(target, tool_bodies, op, keep_tool, name="Comb"):
    """Combine (CUT/JOIN) tool bodies into a target body."""
    coll = adsk.core.ObjectCollection.create()
    if isinstance(tool_bodies, list):
        for b in tool_bodies:
            coll.add(b)
    else:
        coll.add(tool_bodies)
    inp = root.features.combineFeatures.createInput(target, coll)
    inp.operation = op
    inp.isKeepToolBodies = keep_tool
    f = root.features.combineFeatures.add(inp)
    f.name = name
    return f

def feat_pattern(feat, axis, count_expr, spacing_expr, name="Pat"):
    """Feature pattern a single feature along an axis."""
    coll = adsk.core.ObjectCollection.create()
    coll.add(feat)
    inp = root.features.rectangularPatternFeatures.createInput(
        coll, axis,
        adsk.core.ValueInput.createByString(count_expr),
        adsk.core.ValueInput.createByString(spacing_expr),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    p = root.features.rectangularPatternFeatures.add(inp)
    p.name = name
    return p
```

## Replication Strategy

### Mirror
Use `MirrorFeature` to replicate symmetric parts across construction planes:
```python
mirror_feats = comp.features.mirrorFeatures
body_coll = adsk.core.ObjectCollection.create()
body_coll.add(body)
mirror_input = mirror_feats.createInput(body_coll, midplane)
feat = mirror_feats.add(mirror_input)
```

Construction midplanes should use parametric offsets:
```python
# YZ midplane at half the length
params.add("mid_x", adsk.core.ValueInput.createByString("total_length / 2"), "in", "X midplane")
plane_input.setByOffset(yz_plane, adsk.core.ValueInput.createByString("mid_x"))
```

### Pattern (Rectangular)
For repeated elements (slats, spindles, etc.):
```python
pat_input = pat_feats.createInput(body_coll,
    comp.xConstructionAxis,
    adsk.core.ValueInput.createByString("n_slats"),     # parametric count!
    adsk.core.ValueInput.createByString("slat_width"),   # parametric spacing!
    adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
```

### Body Pattern Ghost Bodies (CRITICAL)

`RectangularPatternFeature` replays the **entire feature history** of the template body — including CUT and JOIN operations that reference it. When a CUT uses `keepTool=True`, each pattern instance creates a duplicate tool body ("ghost body"), inflating the body count (e.g., 3× per instance instead of 1×).

**When body_pattern is safe:** Bodies with only NewBody extrudes and Mirror (no CUT/JOIN in their history). Example: plain shelf boards before mortise CUTs.

**When body_pattern creates ghosts:** Any body that has been used as a CUT tool with `keepTool=True`, or that has had CUT/JOIN operations applied to it. Example: domino loose tenons that CUT two boards.

**Fix:** For complex parts with CUT/JOIN in their history, use a Python `for` loop to create each instance independently. All dimensions stay parametric via parameter expressions; only the count is evaluated at script time with `int(ev("count_param"))`.

```python
# WRONG — ghost bodies from keepTool=True CUTs in template history
body_pattern(domino_body, axis, "dm_count", "dm_spacing")

# RIGHT — independent instances, no ghost bodies
for i in range(int(ev("dm_count"))):
    offset = f"dm_start + {i} * dm_spacing"
    _, pr = sketch_slot_model(comp, plane, (offset, cy, cz), ...)
    ext_new(pr, "dm_depth", f"DM_{i}")
```

### Mirror + Pattern Limitation (CRITICAL)
Fusion 360 CANNOT properly mirror a `RectangularPatternFeature`. When you mirror features that include a pattern, only the template body gets mirrored -- pattern copies are lost.

**Correct approach for symmetric repeated elements:**
1. Build the template on side A (body + all features like grooves, tongues)
2. Mirror ONLY the template features to side B
3. Create an INDEPENDENT pattern on side A (count = parametric expression)
4. Create an INDEPENDENT pattern on side B (same parametric count expression)

Each side gets its own pattern feature. When the user changes dimensions, ALL patterns update independently.

### Mirror Bodies vs Mirror Features
- **Mirror bodies**: captures a fixed set of bodies at script time. If pattern count increases later, the mirror won't include new bodies. Use only for simple cases (legs, rails).
- **Mirror features**: replicates the feature operations. Better for maintaining parametric behavior. Use for templates that will be patterned.

### Typical Replication Sequence

For a part with symmetric tenons/tails that repeats along an axis:

1. **Extrude** ONE tenon/tail as NewBody
2. **Mirror** across one midplane → 2 copies
3. **Mirror** across perpendicular midplane → 4 copies
4. **JOIN** all copies into the parent body → single merged body
5. **Body Pattern** the merged body along the repetition axis

Result: one parametric pattern feature replaces an entire Python `for` loop.

## Joinery Rules

### Combine-Based Joinery (CRITICAL)

**Never draw separate mortise/socket sketches.** Build the tenon/tail as a separate body, then use Fusion 360 **Combine** to cut the receiving board. The tenon body IS the cutting tool — one shape guarantees the mortise exactly matches.

This applies to **all** joint types:
- **Mortise & tenon**: tenon body cuts the mortise, then joins the shelf
- **Dovetails**: tail body cuts the socket, then joins the top board
- **Tongue & groove**: tongue body cuts the groove, then joins the slat
- **Panel grooves**: panel body (with tongues from edge rabbets) cuts the groove in each receiving board via Combine CUT (`keepTool=True`). The tongue-board overlap IS the groove — guaranteed perfect fit. Through tongues produce through grooves; stopped tongues produce stopped grooves. No separate groove sketches needed.

### Tooling Body Pattern for Grooves

> **When a groove receives a paneled body with tongues** (bottoms, lids, drawer bottoms), use the panel body itself as the cutting tool instead (see **Panel grooves** under Combine-Based Joinery above). The tooling body approach below is for standalone grooves that don't receive a panel — dados for fixed shelves, rabbets for backs, etc.

For grooves, dados, and rabbets, use a **tooling body** — a NewBody extrude that represents the material to remove:

1. Extrude a tooling body (NewBody) that spans the full groove path — intentionally extending beyond the target board's boundaries
2. Combine CUT the tooling body into the target board (`keep_tool=False`)
3. Only the intersection is removed — the board's edges act as implicit stops

```python
# Groove tooling body spans full width — only cuts where board exists
_, pr = sketch_rect_model(groove_plane,
    ("board_thick - groove_depth", "0 in", "groove_up"),
    {"x": "groove_depth", "y": "box_width"},
    "BGL_Sk")
groove_tool = ext_new(pr, "bottom_tongue", "BGL")
combine(left_body, groove_tool.bodies.item(0), CUT, False, "BGL_Cut")
```

**Why this works:** The tooling body extends beyond the board edges, but Combine CUT only removes the intersection. Combined with the "grooves before joinery" build order (design philosophy point 7), this produces perfectly stopped grooves at corners without calculating stop positions.

**Stopped grooves for through-prevention:** When a groove must NOT be visible from the board's end (e.g., front/back bottom grooves hidden behind side boards), explicitly stop the groove by shortening its X span:
```python
# Stopped both sides — starts at board_thick, ends at box_length - board_thick
("board_thick", "board_thick - groove_depth", "groove_up"),
{"x": "box_length - 2 * board_thick", "y": "groove_depth"},
```

### Edge Rabbet Pattern for Floating Panels

For bottom panels, lids, and drawer bottoms that sit in grooves with a rabbeted edge, use a pure subtractive **edge rabbet** approach — start with a full board, then cut each edge:

1. **Full board (NewBody):** Extrude at tongue footprint (extends into groove area), full panel thickness
2. **Edge rabbet CUTs:** One per edge direction — **always through cuts** (full board length). Removes `groove_up` from one face of the tongue strip.
3. **Mirror** symmetric edges (front↔back, left↔right) across midplanes

```python
# 1. Full board at tongue footprint, full bottom_thick
_, pr = sketch_rect_model(comp, root.xYConstructionPlane,
    ("board_thick - groove_depth", "board_thick - groove_depth", "0 in"),
    {"x": "box_length - 2*board_thick + 2*groove_depth",
     "y": "box_width - 2*board_thick + 2*groove_depth"},
    "Bottom_Sk")
bot_ext = ext_new(comp, pr, "bottom_thick", "Bottom")
bot_body = bot_ext.bodies.item(0)
bot_body.name = "Bottom"

# 2a. Front edge rabbet CUT (through: full X extent of board)
_, pr = sketch_rect_model(comp, root.xYConstructionPlane,
    ("board_thick - groove_depth", "board_thick - groove_depth", "0 in"),
    {"x": "box_length - 2*board_thick + 2*groove_depth",
     "y": "groove_depth"},
    "BotRab_F_Sk")
rab_f = ext_op(comp, pr, "groove_up", CUT, bot_body, "BotRab_F")

# 2b. Mirror front → back across Y midplane
mirror_feats(comp, [rab_f], y_mid_pl, "BotRab_MirrorY")

# 2c. Left edge rabbet CUT (through: full Y extent of board)
_, pr = sketch_rect_model(comp, root.xYConstructionPlane,
    ("board_thick - groove_depth", "board_thick - groove_depth", "0 in"),
    {"x": "groove_depth",
     "y": "box_width - 2*board_thick + 2*groove_depth"},
    "BotRab_L_Sk")
rab_l = ext_op(comp, pr, "groove_up", CUT, bot_body, "BotRab_L")

# 2d. Mirror left → right across X midplane
mirror_feats(comp, [rab_l], x_mid_pl, "BotRab_MirrorX")
```

**Pure subtractive — no JOIN step.** Woodworkers never add material back; they only remove it. Corner notches where two rabbets intersect are naturally handled — the double-cut IS the corner notch.

**Rabbets are always through cuts.** With hand tools, a through rabbet is a single pass with a rabbet plane — stopping the cut mid-board is unnecessary extra work. The "stopped" concept applies to **grooves in case boards** (so the groove slot doesn't show on the board's end face), NOT to rabbets on panels. See "Stopped grooves for through-prevention" above.

**Asymmetric variation (sliding lids):** For a lid that slides out one side, skip the rabbet on the open edge — the full-thickness board slides freely in the groove.

### Cross-Component CUT via Assembly Proxies

When tenons live in component A (e.g., Shelves) but need to cut mortises in component B (e.g., Sides), use **assembly context proxies** in root:

```python
# Get proxies for bodies in their assembly context
shelf_proxy = shelf_body.createForAssemblyContext(shelves_occ)
side_proxy  = left_side.createForAssemblyContext(sides_occ)

# CUT in root component using proxies
combine(root, side_proxy, [shelf_proxy], CUT, True, "ShelfMortise")
```

This keeps features in their owning components while performing cross-component boolean operations in root. The proxies are persistent — create them once and reuse across multiple CUT operations.

### Bulk CUT (Preferred Over Per-Item CUT)

When multiple tool bodies (e.g., all patterned shelves) need to cut the same target, pass **all tools in a single Combine** rather than looping:

```python
# Collect ALL shelf body proxies (template + pattern copies)
all_shelf_proxies = [b.createForAssemblyContext(shelves_occ)
                     for b in all_shelf_bodies]

# ONE CUT feature creates ALL mortises at once
combine(root, left_side_proxy, all_shelf_proxies, CUT, True, "ShelfMortL")
```

This produces a single CUT feature in the timeline instead of N separate features. Cleaner, faster, and parametric — when the pattern count changes, the CUT automatically picks up new bodies.

### Timeline Ordering for CUT + JOIN

When the same body serves as both a CUT tool (to create a socket/mortise) and a JOIN target (to merge into its parent):

1. **CUT first** (in root, via assembly proxies, `keepTool=True`) — the tool bodies survive
2. **JOIN second** (in the owning component) — the tool bodies merge into the parent

```python
# Step 1: Tail bodies cut sockets in side boards (tails survive)
combine(root, side_proxy, tail_proxies, CUT, True, "DT_Socket")

# Step 2: Tail bodies join into top board (tails consumed)
combine(top_comp, top_body, all_tails, JOIN, False, "DT_Join")
```

### keepTool for Visible Loose Tenons (Dominos, Dowels)

Loose tenon joints (dominos, dowels) have a **separate body** that remains visible after assembly — unlike integral tenons which JOIN into their parent board. When a loose tenon CUTs mortises in two boards:

- **Both CUTs must use `keepTool=True`** so the tenon body survives.
- If either CUT uses `keepTool=False`, the tenon body is consumed — only invisible mortise pockets remain.

```python
# Domino cuts mortise in board A (tenon survives)
combine(board_a, domino_body, CUT, True, "DM_CutA")
# Domino cuts mortise in board B (tenon STILL survives)
combine(board_b, domino_body, CUT, True, "DM_CutB")
# Result: both mortises cut, domino body visible between boards
```

### Mortise and Tenon
- At corners where tenons from two directions enter the same post, stagger them in Z to prevent collision.

### Tongue and Groove
- Frame grooves: centered on rail thickness, receive slat tongues
- Inter-slat T&G: one side groove, other side tongue, consistent across all slats
- Edge tongues: first/last slat gets a tongue into the leg/post groove

### Gap Filling
When `floor(space / element_width)` leaves a remainder, add a gap-filling piece:
- Width = `space - element_width * count` (parametric expression)
- Position = `offset + element_width * count`
- Use `participantBodies` on ALL cut/join operations
- Only build if gap > 0.01 cm at script time
- Mirror gap features to opposite side

### Additional Joinery Types

For joints beyond M&T, T&G, and gap filling, read the corresponding reference file from `joinery/` before generating code:

| Joint | File | Prefix | Use For |
|-------|------|--------|---------|
| Dado & Rabbet | `joinery/dado-rabbet.md` | `dr_` | Shelves, case backs, drawer bottoms |
| Lap Joint | `joinery/lap-joint.md` | `lj_` | Frames, cross braces, lattice |
| Box Joint | `joinery/box-joint.md` | `bj_` | Boxes, drawers, decorative corners |
| Bridle Joint | `joinery/bridle-joint.md` | `br_` | Frame corners, open mortise T-connections |
| Dowel Joint | `joinery/dowel-joint.md` | `dw_` | Edge joining, panel glue-ups, face frames |
| Spline Joint | `joinery/spline-joint.md` | `sp_` | Reinforced miters, decorative accents |
| Miter Joint | `joinery/miter-joint.md` | `mj_` | Picture frames, trim, hidden end grain |
| Dovetail | `joinery/dovetail.md` | `dt_` | Drawer fronts, premium boxes, visible joints |
| Pocket Hole | `joinery/pocket-hole.md` | `ph_` | Face frames, quick assemblies, tabletops |
| Domino Joint | `joinery/domino-joint.md` | `dm_` | Hidden structural connections, kick boards, shelf-to-back |

Each file includes parameters, geometry workflow, replication strategy, pitfalls, and a code snippet. All follow the same conventions: `ValueInput.createByString`, Sketch > Extrude, `participantBodies = [body]` as Python list, 2-letter parameter prefixes.

## Component Structure Template

Table / Bookshelf:
```
Root
  +-- Posts/Legs      (build 1, mirror to all corners)
  +-- LongRails       (build front pair, mirror to back)
  +-- ShortRails      (build side pair, mirror to opposite)
  +-- Panels/Slats    (template per orientation, mirror + independent patterns)
  +-- Top/Bottom      (single panel)
  (root timeline)     bulk CUT features via assembly proxies
```

Box / Case:
```
Root
  +-- Case    (Front, Back, End_Left, End_Right)
  +-- Bottom  (bottom panel with edge rabbets)
  +-- Lid     (lid panel with edge rabbets)
  (root timeline)  panel-body groove CUTs, dovetails, dispensing slot
```

### Feature Ownership

| Where | What |
|-------|------|
| **Component** | Extrudes, mirrors, patterns, JOINs — features that build the part |
| **Root** | Cross-component CUT features via assembly proxies |

## Construction Planes
All positioned with parametric offset expressions. Common planes:
- Body Z (visible area bottom)
- Upper/Lower rail planes
- Tongue planes (rail height minus groove depth)
- Midplanes for X and Y mirror operations

## Naming Convention

Name every feature and body for a readable timeline and easy debugging:

| Element | Pattern | Example |
|---------|---------|---------|
| Bodies | `Part` | `Front`, `Side_Left`, `Bottom`, `Lid` |
| Sketches | `Part_Sk` or `Feature_Sk` | `Front_Sk`, `BGL_Sk`, `DT_FL_Sk` |
| Extrudes | `PartBoard` or `Feature` | `FrontBoard`, `BGL`, `BottomLip` |
| Patterns | `Feature_Pat` | `DT_FL_PatCut`, `DT_FL_PatJoin` |
| Planes | `Part_Pl` or `Feature_Pl` | `Back_Pl`, `BG_Pl`, `LidLip_Pl` |
| Combines | `Feature_Cut` | `BGL_Cut`, `BGF_Cut` |
| Joinery | `JointType_Corner_Op` | `DT_FL_Cut`, `DT_BR_Join` |

## Verification Checklist
1. Component tree shows logical grouping (or root-only for small pieces)
2. Timeline shows: build features > mirror, template > mirror > pattern
3. Change a major dimension > verify ALL sides update correctly
4. Change element width > verify counts increase/decrease on all sides
5. Section Analysis > verify joinery alignment
6. Verify no overlapping joints at corners
7. Body count matches expected (diagnostic print confirms no accidental merges or orphans)

## Common Errors and Fixes
| Error | Cause | Fix |
|-------|-------|-----|
| `RuntimeError: this is not a parametric design` | Accessed `userParameters` before setting `ParametricDesignType` | Set `design.designType` first |
| `RuntimeError: A valid targetBaseFeature is required` | Used `TemporaryBRepManager` | Switch to Sketch > Extrude |
| `RuntimeError: No target body found to cut` | Cut sketch drawn outside the body | Position sketch inside the body |
| Parameters don't update geometry | Used `TemporaryBRepManager` (static BRep) | Use feature-based modeling |
| Mirror only creates partial copies | Mirrored a `RectangularPatternFeature` | Mirror only template, create independent patterns |
| Mirror side doesn't update count | Mirrored bodies (fixed set at script time) | Mirror template features, independent patterns per side |
| Cut/Join affects wrong body | No `participantBodies` specified | Use `ext_input.participantBodies = [body]` |
| `TypeError` on participantBodies | Passed `ObjectCollection` instead of list | Use Python `[body]` list |
| Count doesn't update parametrically | Used Python `int()` at script time | Use `floor()` in Fusion parameter expressions |
| Body pattern creates 2-3× expected bodies | `keepTool=True` CUTs in template history create ghost duplicates at each pattern instance | Use Python `for` loop for bodies with CUT/JOIN history (see Body Pattern Ghost Bodies) |
| Sketch geometry at mirrored/wrong position on non-XY plane | `probe_sketch_axes` gives axis name but not sign; model +Z → sketch -Y on XZ planes | Use `probe_sketch_signs` or `modelToSketchSpace` for approximate positions, flip offset operator based on sign |
| Loose tenon (domino) bodies disappear | Second CUT used `keepTool=False`, consuming the body | Use `keepTool=True` on ALL CUTs for visible loose tenon joints |
| Rectangle deforms when parameter changes | `addTwoPointRectangle` lacks explicit H/V geometric constraints | Add `addHorizontal`/`addVertical` on all 4 lines after creation. Apply same rule to any sketch line that should stay H or V. |
| H/V constraint distorts triangle on YZ plane | On YZ planes, model-Y maps to sketch-V and model-Z to sketch-H — opposite of XZ planes. Using `addHorizontal` on a model-horizontal (same-Z) line that's sketch-vertical destroys the profile. | Always check sketch axis mapping via `modelToSketchSpace` before assigning H/V constraints. Swap H↔V for YZ planes. |

## Incremental Build Strategy

Complex furniture (10+ bodies, 3+ joint systems) should be built in phases. Each phase is a complete standalone script that creates a new document and builds from scratch, adding one layer of complexity. **Small pieces** (boxes, trays — < ~8 bodies, 1-2 joint types) can be built in a single monolithic script.

### Phases

| Phase | What to build |
|-------|--------------|
| 1. Structure | All boards/panels in correct positions, no joinery. Verify orientation and dimensions. |
| 2. Joinery | Add tenons/tails as bodies, mirrors, patterns, JOINs. Add CUT operations for mortises/sockets. |
| 3. Details | Chamfers, fillets, decorative elements. |

### Rules

1. **One phase per script execution.** Never combine all phases into one massive script.
2. **Validate and auto-proceed.** After each phase, validate with `capture_design` (see Execution + Validation Loop). If validation passes, immediately proceed to the next phase. Do NOT wait for user approval between phases.
3. **Each phase script is standalone.** It creates all parameters, helpers, and geometry from scratch. Phase 2 includes phase 1's structure plus joinery.
4. **Same file, growing content.** Update the same `.py` file for each phase.
5. **Show final result.** Take a screenshot only after the last phase and present it to the user.
6. **Design-first planning applies at every phase.** Before writing code for a new phase, write out the step list (see Design-First Planning).

### Document Reuse Pattern

Scripts close existing unsaved documents and create a fresh Fusion Design document. This is fast (no slow timeline clearing) and guarantees component support (Part Design can't have components).

The AutoFusion add-in handles document switches gracefully — it detects the document change and skips committing the old transaction.

**IMPORTANT**: Do NOT try to clear the timeline feature-by-feature. Each deletion triggers a full model recompute, causing Fusion 360 to hang on complex models.

```python
def run(context):
    app = adsk.core.Application.get()

    # Close ALL unsaved documents (handles stacked failed runs)
    while True:
        doc = app.activeDocument
        if doc and not doc.isSaved:
            doc.close(False)
        else:
            break
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    root = design.rootComponent
    params = design.userParameters
    Point3D = adsk.core.Point3D
    # ... build from scratch ...
```

### Script Epilogue

Every script should end with three standard steps:

```python
# 1. Hide construction elements (clean viewport)
for sk in root.sketches:
    sk.isVisible = False
for cp in root.constructionPlanes:
    cp.isLightBulbOn = False
for ca in root.constructionAxes:
    ca.isLightBulbOn = False

# 2. Diagnostic body count (appears in MCP execution result)
names = [root.bRepBodies.item(i).name
         for i in range(root.bRepBodies.count)]
print(f"Root: {len(names)} bodies -> {names}")

# 3. Fit view (ensures screenshot captures complete model)
cam = app.activeViewport.camera
cam.isFitView = True
app.activeViewport.camera = cam
```

## MCP Live Execution

When an MCP connection to Fusion 360 is available (via the AutoFusion add-in), you MUST automatically execute the script after generating it. Do not wait for the user to ask — the full generate-execute-verify loop is the default workflow.

### Available MCP Tools

| Tool | Purpose |
|------|---------|
| `capture_design` | Full design introspection: parameters, component tree with body geometry and sketch dimension details, timeline features (including chamfers and fillets). |
| `get_timeline_state` | Roll timeline to any index, capture body geometry at that point, restore position. |
| `execute_script` | Run a complete Python script in Fusion 360. Returns `isError` flag + full stack trace on failure. Failed scripts are rolled back automatically. |
| `get_screenshot` | Capture the current Fusion 360 viewport. Use to verify results visually. |
| `get_selection` | Read the user's current UI selection. Returns structured info per entity type (body, face, edge, occurrence) AND full feature details when a feature is selected (Sketch with curves/dimensions/constraints, Extrude with operation/distance/sketch, Combine with target/tool bodies, Mirror, Pattern, Move, Chamfer, Fillet). Use when the user says "what is this?" or "make this thicker". |
| `set_selection` | Highlight entities in the UI by name or token. Use after `capture_design` identifies a problem body — select it so the user sees which one. |
| `modify_parameters` | Change parameter expressions with incremental recompute. Much faster than re-running the script. Use for iterative tuning ("make shelves deeper"). |
| `check_interference` | Detect body collisions. Use to validate joinery — confirm tenons fit, no unintended overlaps. Clean designs have zero interferences. |
| `suppress_features` | Toggle timeline features on/off. Diagnostic tool — suppress a suspicious feature, check if it fixes the problem, unsuppress to restore. |
| `get_changes` | Snapshot & diff. First call captures a baseline; subsequent calls return what changed — parameter expression changes, sketch dimension changes, body additions/removals, feature count delta. Use between iterations or when the user says "I changed something". |

### Execution + Validation Loop

After generating each phase's script, run this loop:

1. **Execute** — call `execute_script` to run the script in Fusion 360.
2. **On error** — the `content` field contains the full Python stack trace. Analyze, fix the script, and re-execute (see Error Retry Rules below).
3. **On success — validate with `capture_design`:**
   - Call `capture_design` to get the actual model state.
   - Compare body count and names against what the phase intended. Flag unexpected merges, missing bodies, or orphan bodies.
   - Check bounding boxes — are bodies in the right positions and orientations?
   - Check volumes — are they reasonable for the given dimensions?
   - Report a brief summary: `"Phase 1 OK: 6 bodies [Front, Back, Left, Right, Top, Bottom], all bounding boxes correct."`
4. **If validation fails** — use `get_timeline_state` to bisect the timeline and pinpoint the problem feature (see Diagnosing with Timeline Rollback below). Fix and re-execute.
5. **Auto-proceed** to the next phase if validation passes.
6. **Screenshot only at the end** — after the final phase succeeds and validates, take one screenshot with `get_screenshot` and present it to the user.

### Diagnosing with Timeline Rollback

When `capture_design` reveals unexpected state (wrong body count, bad positions), use `get_timeline_state` to narrow down which feature went wrong:

1. Call `get_timeline_state` at the midpoint of the timeline.
2. Check body count — is it correct for that point in the build?
3. Binary search forward or backward to find the exact feature where the model diverges from the plan.
4. Correlate with the `timeline` array from `capture_design` to identify the feature by name and type.

This is like `git bisect` for the modeling timeline — fast, cheap, and precise.

### Error Retry Rules

- **Max 3 attempts per distinct error.** An error is "the same" if its core message is unchanged (ignore line numbers and memory addresses when comparing).
- **Different errors reset the counter.** If a fix resolves one error but surfaces a new one, the new error gets its own 3-attempt budget.
- **No infinite loops.** If you hit 3 distinct errors in a row (each failing 3 times), stop and present a summary of all errors to the user.
- After each failed attempt, explain what error occurred and what you changed before retrying.
- Failed scripts are automatically rolled back (transaction abort), so each retry starts from a clean state.

### Modifying an Existing Design

When the user asks to change an existing design (e.g., "make the shelves wider"):

**For dimension changes** (most common) — use `modify_parameters` for fast incremental tuning:

1. Call `capture_design` to understand the current model state — parameters, bodies, timeline.
2. Call `modify_parameters` to change the relevant parameter expression(s).
3. Fusion does **incremental recomputation** — only affected features recompute.
4. Validate with `capture_design`.
5. **Good** → update the `.py` source file to match the new expression.
6. **Bad** → revert via `modify_parameters` with the old expression.

**For structural changes** (add a component, change joinery type) — re-run via `execute_script`.

### Selection-Driven Interaction

When the user points at something in Fusion 360 and asks about it:

1. Call `get_selection` to read what they've selected.
2. Use the structured entity info (type, name, dimensions) to understand their intent.
3. If they want a change, use `modify_parameters` for dimension tweaks or `execute_script` for structural changes.
4. Use `set_selection` to highlight the result or related entities.

### Change Detection

When iterating on a design with the user making manual changes in Fusion 360:

1. Call `get_changes` once at the start (or after a script run) to capture a baseline.
2. When the user says "I changed something" or between iterations, call `get_changes` again.
3. The diff tells you exactly what moved — parameter expression changes, sketch dimension edits, body additions/removals, and timeline feature count delta.
4. Use the diff to decide next steps: `modify_parameters` to adjust related dimensions, or `execute_script` if structural changes are needed.

This avoids re-reading the full design with `capture_design` when you only need to know what changed.

### Example Flow

```
Phase 1: Structure
  → write bookshelf.py (boards only)
  → execute → capture_design → validate 6 bodies, positions OK → auto-proceed

Phase 2: Add joinery
  → update bookshelf.py (structure + mortise & tenon)
  → execute → capture_design → validate body count (tenons joined), mortises cut
  → body count wrong? → get_timeline_state to bisect → find bad feature → fix → retry
  → validation OK → auto-proceed

Phase 3: Add details
  → update bookshelf.py (structure + M&T + chamfers)
  → execute → capture_design → validate → screenshot → present to user
```

### Important

- Always generate complete, standalone parametric scripts. MCP is the delivery mechanism — the script must also work when pasted into Fusion 360's script editor.
- Never generate partial snippets that only work via MCP.
- Scripts must NOT catch exceptions — let them propagate so Fusion 360 aborts the transaction and returns the full error to the agent.

### MCP Timeout

The AutoFusion add-in's main-thread execution timeout is set in:
`addin/server/mcp_server.py` → `_execute_on_main_thread` → `timeout = 300`

Default is 300s (5 min). If scripts still time out, increase this value and restart the add-in.

See `mcp/README.md` for setup instructions.
