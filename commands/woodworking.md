# Fusion 360 Parametric Furniture Modeling

You are generating a Fusion 360 Python script to build a parametric furniture model. Follow these rules strictly.

## Design Philosophy: Think Like a Furniture Maker at the Fusion 360 UI

Before writing any code, plan the modeling steps the way an experienced designer would approach the Fusion 360 UI — component by component, feature by feature. You are not a software engineer writing a program. You are a craftsperson building a piece of furniture, and the API is just your hands on the mouse.

1. **Plan before building.** Before writing code, outline every modeling step in order: which component, which feature, which replication strategy. Think: "If I were clicking through the Fusion 360 UI, what would I do next?" Write the plan as a step list (see Design-First Planning below).

2. **Build one, replicate the rest.** Never build every piece from scratch. Build one template, then use **Mirror** and **Rectangular Pattern** features for the rest. If you find yourself reaching for a Python `for` loop to create geometry, stop — use a Fusion 360 pattern instead.

3. **Everything parametric.** When the user changes any dimension in Modify > Change Parameters, the entire model must recompute automatically — lengths, mirror positions, pattern counts, everything.

4. **Organize with components.** Group related bodies into named components (e.g., Sides, Shelves, Top, Kick). Features live inside their respective components. Cross-component operations (like CUT) live in root via assembly proxies.

5. **Feature-based modeling only.** Every shape is: Sketch > Constrain dimensions parametrically > Extrude. This creates timeline features that recompute when parameters change.

6. **Joinery = one shape, two operations.** Never draw mortises and tenons (or sockets and tails) as separate sketches. Build the positive shape (tenon/tail) as a body, CUT it into the receiving board, then JOIN it to the owning board. One shape guarantees perfect fit.

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

### Sketch Plane Selection (CRITICAL)

**Always sketch on existing body surfaces, not constructed offset planes.** When creating a feature that relates to an existing body (joints, pockets, decorative details), find the relevant face on that body and sketch directly on it. Construction offset planes are fragile — they can have flipped sketch axes that silently reverse geometry positions.

**How to find the right face:**
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

**Position relative to a face corner, not the origin.** Project a corner vertex of the face into the sketch and use it as the dimension reference. Offsets from a corner are always positive (going "into" the face), eliminating axis-direction ambiguity.

```python
# Find bottom-left corner of face (min X + min Z in model space)
corner_v = min(back_face.vertices,
    key=lambda v: v.geometry.x + v.geometry.z)

# Project corner into sketch → reference point for dimensions
ref = sk.project(corner_v).item(0)

# Use modelToSketchSpace to compute correct geometry positions
center_model = adsk.core.Point3D.create(x_model, y_face, z_model)
center_ss = sk.modelToSketchSpace(center_model)

# Dimension from projected corner with positive offset expressions
# Swap point order if needed to keep dimension positive
if center_ss.x >= ref.geometry.x:
    h1, h2 = ref, sketch_point
else:
    h1, h2 = sketch_point, ref
dims.addDistanceDimension(h1, h2,
    HorizontalDimensionOrientation,
    text_pos).parameter.expression = "offset_expr"  # always positive
```

**When to use construction planes instead:**
- Midplanes for Mirror operations (`total_width / 2`)
- Z-offset planes for shelf/rail positioning (no existing face yet)
- Any case where no relevant body face exists

### Model-Space Probing for Construction Planes

When sketching on construction planes (XZ, YZ, XY, or offset planes), the mapping between model axes and sketch axes varies per plane and can swap or flip. Hard-coding `HorizontalDimensionOrientation` for one axis and `VerticalDimensionOrientation` for another produces flipped geometry on planes where the mapping differs.

**Use `modelToSketchSpace` to probe the real mapping at runtime:**

```python
def probe_sketch_axes(sk):
    """Discover which model axis maps to sketch-X (h) and sketch-Y (v)."""
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

Then use the probed axes to select dimension orientations:

```python
def orient_for(axis, h_axis):
    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
    return H if axis == h_axis else V
```

**Model-space rectangle helper:** Callers specify geometry in model coordinates — `model_origin = ("x_expr", "y_expr", "z_expr")` and `model_size = {"y": "width_expr", "z": "height_expr"}`. The helper converts corners through `modelToSketchSpace`, draws the rectangle, and assigns parametric dimensions using the probed H/V mapping. Works identically on XZ, YZ, XY, and offset planes. See `samples/pencil-box/pencil_box.py` for the full `sketch_rect_model` implementation.

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

### Direct Extrude CUT/JOIN + Feature Pattern (for dovetails and through tenons)

When a joint shape must both CUT one board (socket/mortise) and JOIN another (tail/tenon), **extrude the profile directly as CUT and JOIN** instead of creating a separate body and using Combine. Then **feature-pattern each extrude** along the repetition axis. This is fully parametric — changing the count in Change Parameters updates all instances automatically.

**Why not body pattern + Combine:** Combine features store a fixed tool-body list. When a body pattern's count increases, new bodies bypass existing Combine features, leaving orphan bodies. Feature-patterning a Combine doesn't help either — it replicates the boolean at the same position without offsetting. Feature-patterning an **extrude** correctly offsets the geometry.

```python
# Per-corner: sketch trapezoid → extrude as CUT → extrude as JOIN → feature pattern both
prof = sk.profiles.item(0)

# CUT socket in pin board
ext_cut = ext_op(prof, "board_thick", CUT, front_body, "DT_FL_Cut")

# JOIN tail into side board (same profile, no separate body)
ext_join = ext_op(prof, "board_thick", JOIN, left_body, "DT_FL_Join")

# Feature pattern along joint edge — fully parametric
feat_pattern(ext_cut, root.zConstructionAxis, "dt_tail_count", "dt_pitch", "DT_FL_PatCut")
feat_pattern(ext_join, root.zConstructionAxis, "dt_tail_count", "dt_pitch", "DT_FL_PatJoin")
```

**Key advantages:**
- No separate tail bodies — tails are part of the side board from the start
- No Combine features — extrude directly as CUT/JOIN with `participantBodies`
- Fully parametric — feature pattern of extrudes correctly offsets geometry
- No orphan bodies when count changes

**Per-corner approach:** Each corner gets its own sketch + 2 extrudes + 2 feature patterns. Mirrors don't work across corners because CUT/JOIN `participantBodies` references stay fixed to the original target body. For 4 corners: 4 sketches, 8 extrudes, 8 feature patterns.

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

**For parts merged before patterning** (tenons merged into a rail, then rail patterned):

1. **Extrude** ONE tenon/tail as NewBody
2. **Mirror** across one midplane → 2 copies
3. **Mirror** across perpendicular midplane → 4 copies
4. **JOIN** all copies into the parent body → single merged body
5. **Body Pattern** the merged body along the repetition axis

**For joinery where tails CUT one board and JOIN another** (dovetails, through tenons):

1. **Sketch** ONE trapezoid per corner on the appropriate plane
2. **Extrude as CUT** the profile into the pin board (`participantBodies=[pin_board]`)
3. **Extrude as JOIN** the same profile into the tail board (`participantBodies=[tail_board]`)
4. **Feature pattern** each CUT extrude along the repetition axis
5. **Feature pattern** each JOIN extrude along the repetition axis

Each corner is independent (4 sketches, 8 extrudes, 8 feature patterns for a box). Fully parametric — changing the count in Change Parameters updates all corners automatically.

## Joinery Rules

### Combine-Based Joinery (CRITICAL)

**Never draw separate mortise/socket sketches.** Build the tenon/tail as a separate body, then use Fusion 360 **Combine** to cut the receiving board. The tenon body IS the cutting tool — one shape guarantees the mortise exactly matches.

```python
def combine(comp, target, tool_bodies, op, keep_tool, name="Comb"):
    coll = adsk.core.ObjectCollection.create()
    if isinstance(tool_bodies, list):
        for b in tool_bodies:
            coll.add(b)
    else:
        coll.add(tool_bodies)
    inp = comp.features.combineFeatures.createInput(target, coll)
    inp.operation = op
    inp.isKeepToolBodies = keep_tool
    f = comp.features.combineFeatures.add(inp)
    f.name = name
    return f
```

This applies to **all** joint types:
- **Mortise & tenon**: tenon body cuts the mortise, then joins the shelf
- **Dovetails**: tail body cuts the socket, then joins the top board
- **Tongue & groove**: tongue body cuts the groove, then joins the slat

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

## Verification Checklist
1. Component tree shows logical grouping
2. Timeline shows: build features > mirror, template > mirror > pattern
3. Change a major dimension > verify ALL sides update correctly
4. Change element width > verify counts increase/decrease on all sides
5. Section Analysis > verify joinery alignment
6. Verify no overlapping joints at corners

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
| New tails don't join when count increases | Body pattern + Combine(JOIN) — combine has a fixed tool body list | Extrude directly as CUT/JOIN + feature-pattern the extrudes; avoid body pattern + Combine for joinery |
| Sketch geometry flipped on YZ or offset plane | Hard-coded H/V dimension orientations assume specific axis mapping | Use `probe_sketch_axes()` + `modelToSketchSpace` to discover real mapping at runtime |

## Incremental Build Strategy

Complex furniture should be built in phases. Each phase is a complete standalone script that creates a new document and builds from scratch, adding one layer of complexity.

### Phases

| Phase | What to build |
|-------|--------------|
| 1. Structure | All boards/panels in correct positions, no joinery. Verify orientation and dimensions. |
| 2. Joinery | Add tenons/tails as bodies, mirrors, patterns, JOINs. Add CUT operations for mortises/sockets. |
| 3. Details | Chamfers, fillets, decorative elements. |

### Rules

1. **One phase per script execution.** Never combine all phases into one massive script.
2. **Auto-proceed between phases.** After each phase succeeds and screenshot is verified, immediately update the script and execute the next phase. Do NOT wait for user approval between phases.
3. **Each phase script is standalone.** It creates all parameters, helpers, and geometry from scratch. Phase 2 includes phase 1's structure plus joinery.
4. **Same file, growing content.** Update the same `.py` file for each phase.
5. **Show final result.** Take a screenshot after the last phase and present it to the user.
6. **Design-first planning applies at every phase.** Before writing code for a new phase, write out the step list (see Design-First Planning).

### Document Reuse Pattern

Scripts close the existing unsaved document and create a fresh Fusion Design document. This is fast (no slow timeline clearing) and guarantees component support (Part Design can't have components).

The MCP add-in handles document switches gracefully — it detects the document change and skips committing the old transaction.

**IMPORTANT**: Do NOT try to clear the timeline feature-by-feature. Each deletion triggers a full model recompute, causing Fusion 360 to hang on complex models.

```python
def run(context):
    app = adsk.core.Application.get()

    # Close existing unsaved doc, create fresh Fusion Design doc
    try:
        if app.activeDocument and not app.activeDocument.isSaved:
            app.activeDocument.close(False)
    except:
        pass
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    root = design.rootComponent
    params = design.userParameters
    # ... build from scratch ...
```

## MCP Live Execution

When an MCP connection to Fusion 360 is available (via FusionMCPSample), you MUST automatically execute the script after generating it. Do not wait for the user to ask — the full generate-execute-verify loop is the default workflow.

### Available MCP Tools

| Tool | Purpose |
|------|---------|
| `execute_api_script` | Run a complete Python script in Fusion 360. Returns `isError` flag + full stack trace on failure. Failed scripts are rolled back automatically. |
| `get_screenshot` | Capture the current Fusion 360 viewport. Use to verify results visually. |
| `get_api_documentation` | Search Fusion 360 API docs by class/member name. Use when diagnosing API errors. |
| `get_best_practices` | Retrieve Fusion 360 scripting best practices. |

### Automatic Execution Loop

After generating the complete script, immediately run this loop:

1. **Execute** — call `execute_api_script` to run the script in Fusion 360.
2. **Check result** — inspect the `isError` flag. On failure, the `content` field contains the full Python stack trace with line numbers and exception type.
3. **On success** — take a screenshot with `get_screenshot` and present it to the user. Done.
4. **On error** — analyze the stack trace, fix the script, and re-execute. Track each distinct error by its core message. If the **same error persists after 3 attempts**, stop and report the error to the user with your analysis of what went wrong. Do not keep retrying the same failure.

### Error Retry Rules

- **Max 3 attempts per distinct error.** An error is "the same" if its core message is unchanged (ignore line numbers and memory addresses when comparing).
- **Different errors reset the counter.** If a fix resolves one error but surfaces a new one, the new error gets its own 3-attempt budget.
- **No infinite loops.** If you hit 3 distinct errors in a row (each failing 3 times), stop and present a summary of all errors to the user.
- After each failed attempt, explain what error occurred and what you changed before retrying.
- Failed scripts are automatically rolled back (transaction abort), so each retry starts from a clean state.

### Project Handling

- If the user is starting a new piece, create a new Fusion 360 document before executing.
- If this is an incremental update to an existing design, execute against the current active document. Use `get_screenshot` first to confirm the current state before modifying.

### Example Flow

```
Phase 1: Structure
  → write bookshelf.py (boards only)
  → execute → screenshot → verify ✓ → auto-proceed

Phase 2: Add joinery
  → update bookshelf.py (structure + mortise & tenon)
  → execute → screenshot → verify ✓ → auto-proceed

Phase 3: Add dovetails
  → update bookshelf.py (structure + M&T + dovetails)
  → execute → screenshot → show user final result
```

### Important

- Always generate complete, standalone parametric scripts. MCP is the delivery mechanism — the script must also work when pasted into Fusion 360's script editor.
- Never generate partial snippets that only work via MCP.
- Scripts must NOT catch exceptions — let them propagate so Fusion 360 aborts the transaction and returns the full error to the agent.

### MCP Timeout

The MCP add-in's main-thread execution timeout is set in:
`Fusion MCP Addin/server/mcp_server.py` → `_execute_on_main_thread` → `timeout = 300`

Default was 30s (too short for complex scripts). Set to 300s (5 min). If scripts still time out, increase this value and restart Fusion 360.

See `mcp/README.md` for setup instructions.
