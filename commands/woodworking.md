# Fusion 360 Parametric Furniture Modeling

You are generating a Fusion 360 Python script to build a parametric furniture model. Follow these rules strictly.

## Design Philosophy: Think Like a Furniture Maker at the Fusion 360 UI

Before writing any code, plan the modeling steps the way an experienced designer would approach the Fusion 360 UI — component by component, feature by feature. You are not a software engineer writing a program. You are a craftsperson building a piece of furniture, and the API is just your hands on the mouse.

1. **Plan before building.** Before writing code, outline every modeling step in order: which component, which feature, which replication strategy. Think: "If I were clicking through the Fusion 360 UI, what would I do next?" Write the plan as a step list (see Design-First Planning below).

2. **Build one, replicate the rest.** Prefer building one template and using **Mirror** and **Rectangular Pattern** features for the rest. If you find yourself reaching for a Python `for` loop to create geometry, stop — use a Fusion 360 pattern instead. **Exception:** Per-corner joinery (dovetails, box joints) where CUT/JOIN targets differ per corner requires independent construction at each corner — mirrors of CUT/JOIN extrudes inherit the original `participantBodies` reference and fail.

3. **Everything parametric.** When the user changes any dimension in Modify > Change Parameters, the entire model must recompute automatically — lengths, mirror positions, pattern counts, everything.

4. **Organize with components — or don't.** For multi-assembly furniture (bookshelves, tables, dressers with 10+ bodies), group related bodies into named components (e.g., Sides, Shelves, Top, Kick). Features live inside their respective components; cross-component operations (like CUT) live in root via assembly proxies. **For small, single-piece items** (boxes, trays, small drawers with < ~8 bodies), use a **root-only build** — all bodies and features directly in root. This eliminates assembly-proxy complexity with no loss of parametric behavior.

5. **Feature-based modeling only.** Every shape is: Sketch > Constrain dimensions parametrically > Extrude. This creates timeline features that recompute when parameters change.

6. **Joinery = one shape, two operations.** Never draw mortises and tenons (or sockets and tails) as separate sketches. Build the positive shape (tenon/tail) as a body, CUT it into the receiving board, then JOIN it to the owning board. One shape guarantees perfect fit.

7. **Build order matters.** Cut grooves and dados **before** joining corner joinery (dovetails, box joints). Side boards span only their initial footprint before tails are joined; groove tool bodies that extend beyond the board only CUT the material that exists at that moment. When tails are later joined, they attach ungrooved — producing clean, stopped grooves at corners with zero extra geometry. This "implicit stopped groove" technique eliminates manual stop calculations.

## Parameter Planning

Choosing which values are user parameters vs. derived is critical. The goal: adjusting any single parameter always produces a clean, valid model — no broken geometry, no asymmetric gaps.

**Principle: define count, derive spacing.** When elements repeat across a dimension (tails, slats, fingers), make the *count* a user parameter and derive the *spacing* from `board_dimension / count`. This guarantees elements always fill the space exactly. The alternative — defining element width + gap width independently and using `floor()` to compute count — leaves uneven remainders that break symmetry.

**Principle: every sketch position must be parametric.** Evaluating a parameter at script time (`ev("param")`) bakes the current value into the sketch geometry. If the user later changes the parameter in Change Parameters, the sketch doesn't move. Always add a sketch dimension linked to the parameter expression so Fusion recomputes the position automatically.

**How to decide:**
1. Ask: "If the user changes this value, does the model stay valid?" If increasing a width could overflow available space, that width should be derived from a count instead.
2. Ask: "Does changing this parameter require other values to adjust?" If yes, those other values must be derived expressions, not independent parameters.
3. Ask: "Is any geometry positioned using a value computed at script time?" If yes, add a sketch dimension with a parameter expression so it updates live.

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
- **Python `for` loops for geometry replication** — use Rectangular Pattern or Mirror features instead. A `for` loop creates N independent features that don't update when count changes. A pattern is one parametric feature that recomputes automatically.

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

**Approach A: Sketch on body faces.** When creating a feature that relates to an existing body (joints, pockets, decorative details), find the relevant face on that body and sketch directly on it. Position relative to a projected face corner for positive offsets.

```python
# Find the back face of a shelf body (face at Y=shelf_depth, normal +Y)
target_val = ev("shelf_depth")
back_face = None
for face in body.faces:
    geom = face.geometry
    if isinstance(geom, adsk.core.Plane):
        if geom.normal.y > 0.99:
            if abs(face.pointOnFace.y - target_val) < 0.01:
                back_face = face
                break
sk = comp.sketches.add(back_face)  # sketch directly on the BRepFace
```

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

**When to use which:**
- **Body faces** — best for component-based builds where faces already exist and you want corner-referenced positioning
- **Construction planes + probing** — best for root-only builds, model-coordinate workflows, and when `sketch_rect_model` handles all sketching
- **Construction planes always** — midplanes for Mirror operations, offset planes for positioning before bodies exist

### Sketch + Extrude Workflow
```python
# 1. Sketch with approximate geometry
sk = comp.sketches.add(plane)
rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)

# 2. Constrain dimensions parametrically
d_w = sk.sketchDimensions.addDistanceDimension(...)
d_w.parameter.expression = "slat_width"  # linked to user parameter

# 3. Extrude with parametric distance
ext_input = comp.features.extrudeFeatures.createInput(profile, operation)
ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByString("body_height"))
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

    # Draw rectangle
    rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(
        Point3D.create(sk_o.x, sk_o.y, 0),
        Point3D.create(sk_f.x, sk_f.y, 0))

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

### Tooling Body Pattern for Grooves

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

### Board-First Rabbet Pattern for Floating Panels

For bottom panels, lids, and drawer bottoms that sit in grooves with a rabbeted edge, use a three-step **board-first** approach that models how a woodworker actually builds — start with a full board, then cut the rabbet:

1. **Full board (NewBody):** Extrude at the tongue footprint (extends into groove area), full panel thickness
2. **Rabbet CUT:** Remove the lip offset from one face across the entire footprint
3. **Lip JOIN:** Restore the inner area (between board inner faces) at the lip height

```python
# 1. Full board at tongue footprint, Z=0, height=bottom_thick
_, pr = sketch_rect_model(root.xYConstructionPlane,
    ("board_thick - groove_depth", "board_thick - groove_depth", "0 in"),
    {"x": "box_length - 2*board_thick + 2*groove_depth",
     "y": "box_width - 2*board_thick + 2*groove_depth"},
    "Bottom_Sk")
bot_ext = ext_new(pr, "bottom_thick", "Bottom")
bot_body = bot_ext.bodies.item(0)
bot_body.name = "Bottom"

# 2. Rabbet CUT: removes groove_up from bottom face
_, pr = sketch_rect_model(root.xYConstructionPlane,
    ("board_thick - groove_depth", "board_thick - groove_depth", "0 in"),
    {"x": "box_length - 2*board_thick + 2*groove_depth",
     "y": "box_width - 2*board_thick + 2*groove_depth"},
    "BottomRabbet_Sk")
ext_op(pr, "groove_up", CUT, bot_body, "BottomRabbet")

# 3. Lip JOIN: restores inner area at Z=0
_, pr = sketch_rect_model(root.xYConstructionPlane,
    ("board_thick", "board_thick", "0 in"),
    {"x": "box_length - 2*board_thick",
     "y": "box_width - 2*board_thick"},
    "BottomLip_Sk")
ext_op(pr, "groove_up", JOIN, bot_body, "BottomLip")
```

**Net result:** Tongue extends into grooves on all sides, lip is flush at Z=0. Panel thickness params (`bottom_thick`, `lid_thick`) represent the total board thickness — not just the tongue.

**Asymmetric variation (sliding lids):** For a lid that slides out one side, skip the rabbet on that edge by making the lip JOIN footprint extend to the opening edge. The full-thickness board remains on the sliding side — no rabbet step interferes with sliding.

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
```
Root
  +-- Posts/Legs      (build 1, mirror to all corners)
  +-- LongRails       (build front pair, mirror to back)
  +-- ShortRails      (build side pair, mirror to opposite)
  +-- Panels/Slats    (template per orientation, mirror + independent patterns)
  +-- Top/Bottom      (single panel)
  (root timeline)     bulk CUT features via assembly proxies
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

### Document Management — DO NOT manage documents in scripts

Scripts MUST NOT close or create documents. The `execute_script` MCP tool manages the scratch document via `clean=True`. A script that calls `doc.close(False)` or `app.documents.add()` conflicts with the transaction wrapper and causes Fusion to allocate unbounded memory (200+ GB observed), freezing the application.

A guard in `execute_script.py` rejects scripts containing this pattern.

```python
def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    root = design.rootComponent
    params = design.userParameters
    Point3D = adsk.core.Point3D
    # ... build from scratch ...
```

Use `execute_script` with `clean=True` for a fresh slate — it deletes all timeline features and user parameters before running, wrapped in a single transaction (Ctrl+Z reverts everything).

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
| `capture_design` | Full design introspection: parameters, component tree with body geometry, timeline features. |
| `get_timeline_state` | Roll timeline to any index, capture body geometry at that point, restore position. |
| `execute_script` | Run a complete Python script in Fusion 360. Returns `isError` flag + full stack trace on failure. Failed scripts are rolled back automatically. |
| `get_screenshot` | Capture the current Fusion 360 viewport. Use to verify results visually. |
| `get_selection` | Read the user's current UI selection. Returns structured info per entity type (body, face, edge, occurrence, etc.). Use when the user says "what is this?" or "make this thicker". |
| `set_selection` | Highlight entities in the UI by name or token. Use after `capture_design` identifies a problem body — select it so the user sees which one. |
| `modify_parameters` | Change parameter expressions with incremental recompute. Much faster than re-running the script. Use for iterative tuning ("make shelves deeper"). |
| `check_interference` | Detect body collisions. Use to validate joinery — confirm tenons fit, no unintended overlaps. Clean designs have zero interferences. |
| `suppress_features` | Toggle timeline features on/off. Diagnostic tool — suppress a suspicious feature, check if it fixes the problem, unsuppress to restore. |

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

### Screenshots

After the final phase, take screenshots for documentation. See [woodworking/screenshots.md](woodworking/screenshots.md) for the full guide:

- **Resolution**: 2048x2048 via `get_screenshot(width=2048, height=2048)`
- **Visual style**: `ShadedWithVisibleEdgesOnlyVisualStyle` (enum value 2) — edge lines required
- **Framing**: entire model inside frame, centered, filling ~70-80% of the image
- **Cleanup**: clear selections, hide sketches/construction planes before capture
- **Transparent views**: use `body.opacity = 0.2` to reveal internal joinery (M&T, dovetails, dominos)

### MCP Timeout

The AutoFusion add-in's main-thread execution timeout is set in:
`addin/server/mcp_server.py` → `_execute_on_main_thread` → `timeout = 300`

Default is 300s (5 min). If scripts still time out, increase this value and restart the add-in.

See `mcp/README.md` for setup instructions.
