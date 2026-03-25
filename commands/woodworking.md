# Fusion 360 Parametric Furniture Modeling

You are generating a Fusion 360 Python script to build a parametric furniture model. Follow these rules strictly.

## Prerequisites

This skill generates Fusion 360 Python scripts and optionally executes them live via MCP. To get the full experience:

1. **Fusion 360** — install from [autodesk.com/fusion-360](https://www.autodesk.com/products/fusion-360)
2. **ShopPrentice add-in** — provides the MCP server, helper library, and joinery templates:
   ```bash
   curl -sSL https://raw.githubusercontent.com/ShopPrentice/shopprentice/main/install.sh | bash
   ```
3. **Enable the add-in** in Fusion 360: **Tools > Add-Ins > ShopPrentice > Run**
4. **Verify** the MCP connection: `curl http://localhost:9100/health`

Without the add-in, the skill still generates correct Fusion 360 Python scripts — you just need to run them manually via Fusion's Script Manager instead of live execution.

Source and full documentation: [github.com/ShopPrentice/shopprentice](https://github.com/ShopPrentice/shopprentice)

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

9. **Think in grain direction and mechanical interlock.** Wood is a directional fiber material — fibers (bonded by lignin) run parallel to the longest dimension of each part: leg fibers in Z, rail fibers in X or Y, stretcher fibers along their length. This has three consequences for every joint:
   - **End grain glue is weak.** Where fiber ends meet a surface (end grain to side grain), glue alone provides almost no holding force.
   - **Mechanical joints use fiber strength.** When a tenon sits inside a mortise, the wood fibers of both pieces resist pulling apart — strong even without glue.
   - **Side grain to side grain glue is strong.** A tenon inside a socket creates side-grain contact surfaces where glue forms a bond as strong as the wood itself.

   **During planning, audit every connection:** wherever two parts meet, ask "if I built this in real wood, would gravity or use pull it apart?" If the answer is yes, there must be a physical joint — M&T, domino, dovetail, etc. — not just touching surfaces. The model must show the interlock: a tenon body occupying a mortise void, a tail body filling a socket. A CUT that creates a void is only half the joint — the mating piece must physically fill it.

   **Grain direction determines joint choice:**
   - **Long grain to long grain** (parallel fibers meeting side-to-side) — glue alone is sufficient (edge-joining boards for a panel).
   - **End grain to side grain** (fiber ends meeting a surface) — mechanical joint required (rail into leg = M&T, board corner = dovetail).
   - **End grain to end grain** — weakest possible bond. Always reinforce with a cross-grain element (spline, domino, biscuit).

   **Wood movement determines attachment method:**
   - Wood expands/contracts across the grain (perpendicular to fiber direction). Narrow parts (legs, rails) are negligible. Wide panels (desk tops, table tops, seats > ~6") move measurably with seasonal humidity changes.
   - **Never rigidly attach a wide panel to a cross-grain apron.** Dominos, dowels, or screws through fixed holes lock the panel — when it shrinks, the cross-grain apron holds it in tension, splitting it.
   - **Use slotted fasteners** for cross-grain top-to-apron connections: `tabletop_bracket` (L-bracket with slotted screw holes), Z-clips, or figure-8 fasteners. The slot allows the panel to slide across the grain while staying flat.
   - **Rigid attachment is OK** when the apron runs WITH the grain (both parts move together).

## Topic Reference

This skill is modular. The core (this file) covers fundamentals needed for every project. Read additional topic files based on your project's needs:

### Topic Files

| Topic | When to Read | Status | File |
|-------|-------------|--------|------|
| **Angled Construction** | Splayed legs, stretchers/rails on splayed legs, through-tenons, compound angles, Sweep, Move, SplitBody | Tested (counter stool) | `woodworking/angled-construction.md` |
| **Details & Finishing** | Fillets, chamfers, edge treatments (Phase 3) | Planned — inline quick reference below | `woodworking/details-and-finishing.md` |
| **MCP Advanced** | Modifying existing designs, fixing dimensions, adding features to built models, delete-and-rebuild timeline sections | Tested (bar side table) | `woodworking/mcp-advanced.md` |
| **Appearance** | Applying wood species, grain direction, multi-species designs — read before calling `apply_appearance` | Tested (blanket box) | `woodworking/appearance.md` |
| **Hardware Installation** | Importing STEP hardware (bed rail fasteners, hinges), positioning, caching, direction detection, component organization | Tested (queen + twin beds) | `woodworking/hardware-installation.md` |
| **Joinery Rules** | Combine-based joinery, tooling bodies, edge rabbets, cross-component CUT patterns | Tested | `woodworking/joinery.md` |
| **Screenshots** | Camera positioning, standard shots, transparent views, detail framing | Tested | `woodworking/screenshots.md` |
| **Incremental Updates & Interactive Editing** | Adding/changing features, detecting UI edits, interpreting user intent vs literal edit, when to rebuild vs patch, component ownership, mirror timing | Tested (Roubo workbench) | `woodworking/incremental-updates.md` |

### Joinery Reference Files

Read the specific joint file **before writing joinery code**. Each file has parameters, geometry workflow, replication strategy, and pitfalls. Choose the joint type based on grain orientation at the interface (rule 9) — end-grain-to-side-grain connections need mechanical interlock (M&T, dovetail, domino), while long-grain-to-long-grain can use glue alone.

**Status key:** "Tested" means the technique was built end-to-end in a real model, hitting and resolving actual API pitfalls. "Draft" means the file has plausible instructions but hasn't been validated through a real build — expect missing pitfalls and possible wrong API sequences. When using a Draft file, validate each step with `capture_design` and be ready to debug.

| Joint | When to Read | Status | File |
|-------|-------------|--------|------|
| **Mortise & Tenon** | Leg-to-rail, stretcher-to-leg, frame-and-panel, table aprons, any rail-into-post connection | Tested (counter stool — blind, through & angled variants) | Inline in skill + `mortise_tenon` template |
| **Drawbore M&T** | Stretcher-to-leg with offset pins for permanent tightness — workbenches, trestle tables, timber frames | Tested (Roubo workbench — through & blind variants) | `woodworking/joinery/drawbore.md` + `drawbore` template |
| **Domino** | Hidden structural joints, kick boards, shelf-to-back, panel alignment — any time you need a loose tenon | Tested (counter stool, bookshelf) | `woodworking/joinery/domino-joint.md` |
| **Dovetail** | Drawer fronts, premium boxes, visible corner joints where mechanical strength matters | Tested (pencil box, wrap box) | `woodworking/joinery/dovetail.md` |
| **Box Joint** | Boxes, drawers, decorative interlocking corners — simpler alternative to dovetails | Draft | `woodworking/joinery/box-joint.md` |
| **Dado & Rabbet** | Shelves into sides, case backs, drawer bottoms, any panel-into-groove connection | Tested (bookshelf, template fixtures — through/stopped dado, rabbet, panel groove) | `woodworking/joinery/dado-rabbet.md` |
| **Bridle Joint** | Frame corners, T-connections, open mortise-and-tenon at end of a rail | Draft | `woodworking/joinery/bridle-joint.md` |
| **Lap Joint** | Flat frames, cross braces, grid assemblies, half-lap at crossings | Draft | `woodworking/joinery/lap-joint.md` |
| **Miter Joint** | Picture frames, trim, hidden end grain at corners | Draft | `woodworking/joinery/miter-joint.md` |
| **Spline Joint** | Reinforced miters, decorative accents across a joint line | Draft | `woodworking/joinery/spline-joint.md` |
| **Dowel Joint** | Edge joining, panel glue-ups, face frames, spindle-to-rail, round-peg alignment | Tested | `woodworking/joinery/dowel-joint.md` + `woodworking/templates/dowel.py` |
| **Pocket Hole** | Face frames, quick assemblies, tabletop attachment — screw-based | Draft | `woodworking/joinery/pocket-hole.md` |
| **Bed Rail Fastener** | Bed rail to post — detachable STEP hardware (mortise bedlock, hooks + slots) | Tested (queen + twin beds) | `woodworking/templates/bed_rail_fastener.py` + `woodworking/hardware-installation.md` |
| **Bowtie / Butterfly Key** | Live edge slab crack stabilization, decorative inlay | Tested (twin bed) | `woodworking/templates/bowtie.py` |

**Read the topic/joinery file BEFORE writing code** that uses those techniques. The core skill provides the routing — the reference files provide the implementation details. For Draft files, treat instructions as a starting point and validate aggressively.

### Style & Type Guides

Before planning, identify the **furniture type** and **design style** from the user's request. Load the matching files — they provide component checklists, connection requirements, hardware needs, proportions, and detail patterns specific to that combination.

**Identify type** from what the user is building:

| Type | Keywords | File |
|------|----------|------|
| Chair | chair, dining chair, side chair | `woodworking/types/chair.md` |
| Stool | stool, counter stool, bar stool, step stool | `woodworking/types/stool.md` |
| Bench | bench, entryway bench, garden bench | `woodworking/types/bench.md` |
| Sofa | sofa, couch, settee, loveseat | `woodworking/types/sofa.md` |
| Dining table | dining table, farm table, harvest table | `woodworking/types/dining-table.md` |
| Coffee table | coffee table, cocktail table | `woodworking/types/coffee-table.md` |
| Side table | side table, end table, nightstand, accent table | `woodworking/types/side-table.md` |
| Desk | desk, writing desk, secretary | `woodworking/types/desk.md` |
| Console table | console, TV console, media console, credenza | `woodworking/types/console-table.md` |
| Chest | chest, trunk, blanket chest, toy box, hope chest | `woodworking/types/chest.md` |
| Box | box, pencil box, jewelry box, keepsake box | `woodworking/types/box.md` |
| Cabinet | cabinet, cupboard, pantry, hutch | `woodworking/types/cabinet.md` |
| Dresser | dresser, bureau, chest of drawers | `woodworking/types/dresser.md` |
| Bookshelf | bookshelf, bookcase, shelving unit | `woodworking/types/bookshelf.md` |
| Wardrobe | wardrobe, armoire, closet | `woodworking/types/wardrobe.md` |
| Sideboard | sideboard, buffet, server | `woodworking/types/sideboard.md` |
| Bed frame | bed, bed frame, platform bed, four-poster | `woodworking/types/bed-frame.md` |
| Crib | crib, baby crib, toddler bed | `woodworking/types/crib.md` |
| Planter | planter, window box, plant stand | `woodworking/types/planter.md` |
| Pergola | pergola, arbor, trellis, gazebo | `woodworking/types/pergola.md` |
| Mirror frame | mirror, mirror frame, looking glass | `woodworking/types/mirror-frame.md` |
| Shelf | shelf, floating shelf, wall shelf, ledge | `woodworking/types/shelf.md` |

**Identify style** from visual cues, user description, or reference photos:

| Style | Keywords / Visual Cues | File |
|-------|----------------------|------|
| Modern | clean lines, minimal, contemporary, square edges, hidden hardware | `woodworking/styles/modern.md` |
| Shaker | through dovetails, tapered details, applied base, brass hardware, simple lines | `woodworking/styles/shaker.md` |
| Craftsman | exposed tenons, corbels, quartersawn oak, thick stock, Arts & Crafts | `woodworking/styles/craftsman.md` |
| Mid-century | tapered legs, floating tops, thin profiles, hidden joinery, Danish, Scandinavian | `woodworking/styles/mid-century.md` |
| Rustic | thick boards, farmhouse, reclaimed, visible fasteners, breadboard ends | `woodworking/styles/rustic.md` |
| Nakashima | live edge, natural edge, slab, organic, bowties, butterfly keys, walnut slab, free-form | `woodworking/styles/nakashima.md` |

**If no style is specified or identifiable, default to Modern.**

**Read both files BEFORE the high-level plan.** The type file tells you what components and connections to plan. The style file tells you which joinery, edge treatments, and hardware to use. If a file doesn't exist yet, proceed with the core skill rules and note the gap.

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

**Parametric positions (MANDATORY):** `ev()` is for approximate placement ONLY. Every `ev()` call that positions sketch geometry MUST be followed by `addDistanceDimension` with a parametric expression. Without this, geometry stays at stale positions when parameters change. This was the #1 source of broken models in testing — dog holes, pins, and vise components all failed when parameters changed because they had `ev()` placement without parametric dimensions.

```python
# WRONG — positions baked at script time, breaks on parameter change:
ctr = m2s(P.create(ev("mid_x"), ev("leg_d / 2"), ev("ls_z + ls_w")))
sk.sketchCurves.sketchCircles.addByCenterRadius(P.create(ctr.x, ctr.y, 0), r)
# only radial dimension — center position is NOT parametric

# RIGHT — ev() for placement, then parametric dimensions:
ctr = m2s(P.create(ev("mid_x"), ev("leg_d / 2"), ev("ls_z + ls_w")))
sk.sketchCurves.sketchCircles.addByCenterRadius(P.create(ctr.x, ctr.y, 0), r)
d.addRadialDimension(circle, ...).parameter.expression = "dog_dia / 2"
d.addDistanceDimension(origin, circle.centerSketchPoint, H, ...).parameter.expression = "mid_x"
d.addDistanceDimension(origin, circle.centerSketchPoint, V, ...).parameter.expression = "ls_z + ls_w"
```

**Face-relative sketching (MANDATORY):** Sketch positions must be relative to the features they interact with — not absolute world coordinates. When a sketch CUTs or modifies a body, dimension from the body's face edges or a projected reference, not from the sketch origin with `leg_setback + ...`. For example, a tenon on a leg should reference the leg top face, not compute its position from `leg_setback`. When the leg moves, the tenon follows automatically through the face reference. Use `_face_fl_pt(sketch)` to get the face corner point for dimensioning, or project a construction plane from a face with `sp.off_plane(comp, face_proxy, "0 in", ...)` and dimension from the projected reference.

**How to decide:**
1. Ask: "If the user changes this value, does the model stay valid?" If increasing a width could overflow available space, that width should be derived from a count instead.
2. Ask: "Does changing this parameter require other values to adjust?" If yes, those other values must be derived expressions, not independent parameters.
3. Ask: "Is any geometry positioned using a value computed at script time?" If yes, add a sketch dimension with a parameter expression so it updates live.
4. Ask: "Would a maker write this dimension on a cut list or sketch?" If yes, it should be a user parameter. If it's just "whatever's left over" after other dimensions are placed, derive it.

**Example — dovetails:** `dt_tail_w` (tail width) + `dt_tail_count` are user parameters. `dt_pin_w = board_h / dt_tail_count - dt_tail_w` is derived. Changing count or tail width always produces evenly-spaced tails with symmetric half-pins. If `dt_pin_w` were an independent parameter instead, the user could easily set values where tails don't fit the board.

## Design-First Planning

Before writing any code, output a **high-level plan** covering all components and their build order. This is a single text-only response — no file writes, no code blocks longer than 5 lines.

Then, before each component's build cycle, output a **component plan** with the specific features for that component.

### High-Level Plan (one response, before any code)

```
Components: Sides, Shelves, Top, Kick
Build order: Sides → Shelves → Top → Kick → Cross-component CUTs → Details

Parameters: board_thick, shelf_depth, shelf_count, total_height, ...
Midplanes: XMid (total_length/2), YMid (total_width/2)
Joinery: M&T shelves into sides, dado for kick

Grain & joints:
  Sides: grain in Z (vertical) — end grain meets shelf side grain → M&T
  Shelves: grain in X (horizontal) — tenons into side mortises
  Kick: grain in X — dado into sides (cross-grain housing)
```

### Component Plan (one response per component, before its build cycle)

```
Shelves component (cycle 3):
  - Construction planes: shelf offset
  - Extrude ONE shelf body (NewBody)
  - Extrude ONE tenon (NewBody)
  - Mirror tenon across YMid → back tenon
  - Mirror [tenon + mirror] across XMid → right side tenons
  - JOIN all 4 tenons into shelf body
  - Body pattern shelf along Z (count=n_shelves, spacing=shelf_spacing)
  Expected: n_shelves bodies in Shelves component
```

### Cross-Component Plan (after all components built)

```
Cross-component CUTs (root):
  - CUT left side with ALL shelf proxies (keepTool=True)
  - CUT right side with ALL shelf proxies (keepTool=True)
  - CUT sides with kick proxies
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
- **Python `for` loops for geometry replication** — use Rectangular Pattern or Mirror features instead. A `for` loop creates N independent features that don't update when count changes. A pattern is one parametric feature that recomputes automatically. **Note:** Bodies with CUT/JOIN history create ghost bodies when patterned — see Body Pattern Ghost Bodies under Replication Strategy for how to handle this.

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
Also available as `sp.find_face(body, axis, direction)`.

**Clean references before profile selection (MANDATORY):** Any sketch on a face or with `sketch.project()` calls has reference lines that split profiles into fragments. **Always call `sp.refs_to_construction(sk)` after dimensioning but before selecting a profile.** This converts reference/projected lines to construction geometry — they keep their sketch points (valid for dimensions) but stop forming profile boundaries. Then `sp.smallest_profile(sk)` returns the correct drawn profile. Omitting this step is the #1 cause of wrong-profile extrusions.

```python
# After all sketch geometry and dimensions are complete:
sp.refs_to_construction(sk)
prof = sp.smallest_profile(sk)
ext = sp.ext_new(comp, prof, "depth", "MyFeature")
```

**Extrude direction on body faces:** The default (positive) extrude direction on a face sketch follows `face.evaluator.getNormalAtPoint()` — the true outward normal, pointing AWAY from the body. Use `flip=True` (NegativeExtentDirection) for CUT extrudes on body faces so the cut goes INTO the body.

**Coincident geometry on body-face sketches:** When sketch lines fully coincide with face boundary edges (e.g., an arch baseline at the face corner), Fusion merges them and fails to create separate profiles. Fix: project the face edge via `sk.project(edge)`, then draw the arc from the projected line's sketch points. The projected edge + arc properly split the face. Position dimensions become unnecessary since the projection is already parametric.

**Axis mapping on non-XY planes (MANDATORY):** On construction planes and body faces, sketch H and V map to different model axes than expected. **Always use `sp.probe_orientations()` to get the correct `DimensionOrientation` for each model axis.** Never hardcode H/V assumptions.

```python
# One-liner: returns {'x': H_or_V, 'y': H_or_V, 'z': H_or_V}
orient = sp.probe_orientations(sk, ev("cx"), ev("cy"), ev("cz"))

# Use the dict to assign the correct orientation per model axis:
d.addDistanceDimension(origin, pt, orient['z'], placement
).parameter.expression = "ls_z + ls_w / 2"
d.addDistanceDimension(origin, pt, orient['y'], placement
).parameter.expression = "leg_d / 2"
```

This replaces `probe_sketch_axes` and `probe_sketch_signs` — it returns the orientation enum directly, which is what `addDistanceDimension` needs. No manual axis detection code required.

`sketch_rect_model` and `sketch_slot_model` handle axis mapping internally. Use `probe_orientations` only for custom sketch geometry (circles, manual rectangles) where you add dimensions yourself.

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

### Fillet and Chamfer Features

> **Full reference:** `woodworking/details-and-finishing.md` — edge selection strategies, chamfer types, code patterns, sizing constraints.

Quick reference:
- **Fillet:** `filletFeatures.createInput()` → `inp.addConstantRadiusEdgeSet(edges, radius, propagate)`
- **Chamfer:** `chamferFeatures.createInput2()` → `inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(edges, distance, propagate)`
- Note: chamfer uses `createInput2()` (not `createInput()`) and has a nested `.chamferEdgeSets` collection.
- The API requires `BRepEdge` objects, never `BRepFace`. Iterate face edges and deduplicate via `tempId`.

## Standard Helpers

These reusable helpers form the foundation of the model-coordinate workflow. The caller specifies everything in model coordinates using parameter expressions; the helpers handle all sketch-space complexity.

### Helper Library (`from helpers import sp`)

The `af` helper library provides these functions as importable utilities, eliminating per-script boilerplate. Scripts can `from helpers import sp` and use them directly:

```python
from helpers import sp

def run(context):
    ctx = sp.DesignContext()          # app, design, root, params, units, ev()
    depth = ctx.ev("shelf_depth")     # evaluate parameter or expression → cm
    shelf = ctx.find_body("shelf_top")  # recursive body search by name
    shelves = ctx.find_bodies("shelf_*")  # glob pattern match

    # Queries
    top = sp.find_face(shelf, "z", +1)   # outermost planar face along axis
    at = sp.find_face_at(shelf, "z", 3.0)  # face at specific coordinate
    edges = sp.find_edges(shelf, "z")    # linear edges aligned with axis
    h, v = sp.probe_sketch_axes(sk)      # model axis → sketch H/V
    h, v, hs, vs = sp.probe_sketch_signs(sk)  # + sign detection
    p = sp.smallest_profile(sk)          # smallest-area profile in sketch

    # Sketches — rectangles
    sk, prof = sp.sketch_rect(comp, plane, "0 cm", "0 cm", "w", "d",
                               name="Sk", ev=ctx.ev)
    sk2, prof2 = sp.sketch_rect_model(comp, plane,
                                       ("x0", "y0", "z0"),
                                       {"x": "width", "z": "height"},
                                       name="Sk2", ev=ctx.ev)

    # Sketches — stadium shapes (domino mortises, slot joints)
    sk3, prof3 = sp.sketch_slot(comp, plane, "cx", "cy",
                                 "dm_l", "dm_w", vertical=True,
                                 name="DM_Sk", ev=ctx.ev)
    sk4, prof4 = sp.sketch_slot_model(comp, plane,
                                       ("cx", "cy", "cz"), "z",
                                       "dm_l", "dm_w",
                                       name="DM_Sk", ev=ctx.ev)

    # Feature builders
    f = sp.ext_new(comp, prof, "board_thick", "FrontBoard")
    f = sp.ext_new_sym(comp, prof, "board_thick / 2", "Rail")  # total = board_thick
    f = sp.ext_op(comp, prof, "groove_depth", CUT, body, "Groove", flip=True)
    pl = sp.off_plane(comp, base_plane, "box_width / 2", "YMid")
    sp.combine(comp, target, [tool1, tool2], CUT, True, "Mortise")
    m = sp.mirror_body(comp, body, mid_plane, "BackMirror")
    m = sp.mirror_bodies(comp, [b1, b2], mid_plane, "Mirror")
    m = sp.mirror_feats(comp, [ext_feat], mid_plane, "RabMirror")
    occ = sp.make_comp(root, "Shelves")
    pat = sp.feat_pattern(comp, feat, axis, "n_slats", "slat_pitch", "Pat")
    pat = sp.body_pattern(comp, body, axis, "n_shelves", "shelf_pitch", "Pat")
```

All helpers accept explicit objects (body, component, sketch) rather than relying on module globals, so they work in both normal and sandbox mode. The `ev` parameter falls back to creating one from the active design when omitted.

**Key improvements over inline versions:**
- `sketch_rect` and `sketch_rect_model` always add explicit H/V geometric constraints (some older scripts omitted these)
- `find_face` uses `pointOnFace` coordinate, not normal sign (handles both-direction normals correctly)
- `DesignContext.find_body/find_bodies` walks all descendant components recursively

**What's NOT in sp.py** (write these inline when needed): project-specific face finders (e.g., `find_top_face`), `angled_tenon_end`, `splay_center`.

### `ev()` — Dual-Mode Parameter Access

Evaluates a parameter name or expression string → float in cm. Use for computing approximate sketch positions; actual parametric behavior comes from dimension expressions, not `ev()` values.

**Preferred:** `ctx.ev("shelf_depth")` via `sp.DesignContext`. **Inline fallback** (when not using af):
```python
def ev(e):
    p = params.itemByName(e)
    return p.value if p else design.unitsManager.evaluateExpression(e, "cm")
```

### `sketch_rect_model()` — Parametric Rectangle in Model Coordinates

Available as `sp.sketch_rect_model(comp, plane, model_origin, model_size, name, ev)`.

Creates a fully parametric rectangle on ANY plane (including non-XY construction planes and BRepFaces). Internally uses `modelToSketchSpace` to convert model coordinates to sketch space, adds explicit H/V geometric constraints, and creates 4 parametric dimensions (width, height, x-offset, y-offset).

```python
sk, prof = sp.sketch_rect_model(comp, comp.xZConstructionPlane,
    ("0 in", "0 in", "0 in"),
    {"x": "box_length", "z": "box_height"},
    "Front_Sk", ev=ctx.ev)
```

- `model_origin`: `(x_expr, y_expr, z_expr)` — model-space corner expressions
- `model_size`: `{axis: expr, axis: expr}` — 2 model-axis size expressions
- Returns: `(sketch, profile)`

**Limitation — position dimensions are always positive.** `sketch_rect_model` uses `addDistanceDimension` for the x-offset and y-offset from the sketch origin, which measures absolute distance (always positive). This works correctly when the rectangle is near the origin or in the positive quadrant. For bodies at arbitrary model positions (e.g., splay-adjusted stretchers offset from origin), the position dimensions can reflect coordinates to the wrong side.

**Workaround:** For arbitrarily-positioned rectangles, use a manual sketch with `modelToSketchSpace` for approximate placement and only width/height dimensions (always positive, no position dimensions):

```python
sk = root.sketches.add(plane)
m2s = sk.modelToSketchSpace
s0 = m2s(P(x0_val, y0_val, z_val))
s1 = m2s(P(x1_val, y1_val, z_val))
rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(
    P(s0.x, s0.y, 0), P(s1.x, s1.y, 0))
# H/V constraints + width/height dimensions only — no position dimensions
```

### Feature Builder Reference (`sp.*`)

All feature builders take `comp` as first arg. Available via `from helpers import sp`.

| Function | Signature | Returns | Notes |
|----------|-----------|---------|-------|
| `ext_new` | `(comp, prof, dist, name)` | ExtrudeFeature | Body via `f.bodies.item(0)` |
| `ext_new_sym` | `(comp, prof, dist, name)` | ExtrudeFeature | Symmetric about sketch plane. **`dist` is the HALF-thickness** — extends `dist` on each side, creating a body of total thickness `2 × dist`. Use `"board_t / 2"` for a body of thickness `board_t`. |
| `ext_op` | `(comp, prof, dist_expr, op, body, name, flip)` | ExtrudeFeature | `flip=True` for NegativeExtentDirection (CUT into body on face sketches) |
| `off_plane` | `(comp, base, expr, name)` | ConstructionPlane | Offset construction plane |
| `combine` | `(comp, target, tool_bodies, op, keep_tool, name)` | CombineFeature | `tool_bodies` accepts single body or list |
| `mirror_body` | `(comp, body, plane, name)` | MirrorFeature | Mirrored body via `m.bodies.item(0)` |
| `mirror_bodies` | `(comp, bodies, plane, name)` | MirrorFeature | Multiple bodies at once |
| `mirror_feats` | `(comp, features, plane, name)` | MirrorFeature | Replays feature operations on mirrored side |
| `make_comp` | `(root_comp, name)` | Occurrence | Component via `occ.component` |
| `feat_pattern` | `(comp, feat, axis, count_expr, spacing_expr, name)` | RectangularPatternFeature | Feature pattern along axis |
| `body_pattern` | `(comp, body, axis, count_expr, spacing_expr, name)` | RectangularPatternFeature | **WARNING:** replays full feature tree — creates ghost bodies if template has CUT/JOIN history. Use Python `for` loop instead for complex bodies. |
| `sketch_slot` | `(comp, plane, cx_expr, cy_expr, long_expr, short_expr, vertical, name, ev)` | (sketch, profile) | Stadium shape in sketch-space coords. Use for domino mortises. |
| `sketch_slot_model` | `(comp, plane, model_center, long_model_axis, long_expr, short_expr, name, ev)` | (sketch, profile) | Stadium shape in model-space coords with auto sign detection. |
| `probe_sketch_signs` | `(sk)` | (h_axis, v_axis, h_sign, v_sign) | Extends `probe_sketch_axes` with sign detection for non-XY planes. |

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

### Body Pattern Ghost Bodies

`RectangularPatternFeature` replays the **entire feature history** of the template body — including CUT and JOIN operations that reference it, even those added later or in different timelines (root vs component). When a CUT uses `keepTool=True`, each pattern instance creates a duplicate tool body ("ghost body"), inflating the body count.

**When body_pattern is safe:** Bodies with only NewBody extrudes and Mirror (no CUT/JOIN in their history, and none added later). Example: dovetail tail bodies before any CUT/JOIN.

**When body_pattern creates ghosts:** Any body that is or will be a CUT tool with `keepTool=True`, or that has CUT/JOIN operations applied to it at any point in the timeline. Example: shelf body CUT by domino voids → pattern creates ghost void copies at each shelf position.

**Ghost bodies are geometrically harmless.** They sit at the same position as the intentional copies and produce identical CUT pockets. The model geometry is correct. Always prefer patterns over Python loops for parametric count updates.

**Handling ghosts in validation:** Ghost void bodies overlap with their originals, producing interferences. Filter these from `check_interference` results — exclude pairs where both bodies are void/tool bodies (identifiable by naming convention, e.g. `ShDm_*`). Real interferences involve structural bodies (boards, panels), not void-on-void overlaps.

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

> **Joint-specific references:** See the Joinery Reference Files table in Topic Reference above. Each `woodworking/joinery/*.md` file has full parameters, workflow, and pitfalls for that joint type.

**Core principle:** Never draw separate mortise/socket sketches. Build the tenon/tail as a body, CUT the receiving board (`keepTool=True`), then JOIN to the owner. The body IS the cutting tool — one shape, perfect fit.

**Timeline order:** CUT first (root, assembly proxies), JOIN second (owning component).

**Cross-component:** Use `body.createForAssemblyContext(occ)` for CUT in root. Bulk CUT all tools in one Combine.

**Loose tenons (dominos):** Use `domino.single()`, `domino.grid()`, or `domino.four_corners()` from `woodworking/templates/domino.py`. `grid()` uses body_pattern internally for parametric count. Both CUTs must use `keepTool=True` or the body disappears. Cross-section is a STADIUM (rounded ends), never a rectangle. Pick a standard Festool size (4/5/6/8/10 mm cutter) based on board thickness ≈ 3× cutter diameter. Full reference: `woodworking/joinery/domino-joint.md`.

**Bulk CUT for repeated elements (Tested — crib spindles).** When many identical bodies (spindles, slats, dowels) insert into a receiving board, do NOT create individual joints per element. Instead: (1) build all bodies with body_pattern, (2) collect all body proxies into a list, (3) CUT them ALL into the target in one `sp.combine()` call. This replaces N×(sketch+extrude+CUT) with 1 Combine feature. The crib uses 8 bulk CUTs for 72 spindles into 8 rails — 140 individual dowel calls crashed Fusion, 8 bulk CUTs take seconds.

**Mortise wall thickness rule.** Any CUT that removes material (mortise, dowel hole, domino pocket) must leave enough surrounding material for structural integrity. The remaining wall on each side of the mortise must be ≥ 1/4 of the receiving board's thickness. If a 0.75" spindle CUTs into a 0.75" rail, it removes 100% of the width — the rail breaks into chunks. Fix: either reduce the CUT body diameter or increase the receiving board thickness. Example: 0.75" spindle in a 1.5" rail leaves 0.375" wall on each side (25%) ✓. Also: mortises should be **blind** (not through) — the CUT body extends only partway into the receiving board (e.g., `spindle_tenon = 0.5 in`), leaving material on the exit side.

**Hardware (STEP imports):** When a design uses detachable or mechanical hardware (bed rail fasteners, hinges from STEP files), read `woodworking/hardware-installation.md` for import caching, positioning, direction detection, determinant validation, and component organization rules. Most furniture uses joinery templates instead — only load this topic when hardware is needed.

**Mortise-and-tenon:** Use `mt.blind()` or `mt.through()` from `woodworking/templates/mortise_tenon.py`. Sketch the tenon on the rail's end face (`sp.find_face(rail, axis, direction)`), extrude into the leg. Shoulders are implicit — size the tenon smaller than the rail face and the step forms naturally. For blind, the caller CUTs the leg with the rail afterwards. For through, `through()` CUTs internally to avoid coplanar face splitting. **Extrude direction:** if the tenon height equals the rail height (full-width), the end face causes coincident edges — use a construction plane at the **outer end** of the tenon (proud face or blind stop) and extrude inward. For drawbore M&T with offset pins, use the `drawbore` template. Full reference: `woodworking/joinery/mortise-tenon.md`, `woodworking/joinery/drawbore.md`.

**Tenon collision at corners — interlock, don't shorten.** When two rails meet in the same leg from perpendicular directions, their tenons collide inside the mortise. The naive fix — shortening one tenon — sacrifices bonding surface and therefore joint strength (less side-grain glue area, less fiber interlock). Instead, notch both tenons so they weave past each other at full depth:

- **Front/back rail tenon:** notch the CENTER half (`mt_tw / 2`, centered) from the tenon's end face, cutting `mt_tt` deep through the full tenon thickness. The notch extends `mt_td - leg_size / 2 + mt_tt / 2` into the tenon from its end (the portion that overlaps the perpendicular tenon's path). This leaves the top and bottom quarters as material.
- **Side rail tenon:** notch both top AND bottom quarters (`mt_tw / 4` each), same depth and extent. This leaves the middle half of the side tenon as material.
- Result: front rail keeps top+bottom quarters, side rail keeps the middle half — they interlock perfectly with zero collision. Both tenons penetrate the full `mt_td` into the leg, maximizing glue surface. The leg mortise (created by CUTting the notched rail bodies) automatically gets the correct complementary shape.

**When to apply:** Any corner where two or more tenons enter the same post/leg from different directions — table legs, frame corners, bed posts. The specific notch pattern depends on how many rails meet: 2 rails = one gets top notch, other gets top+bottom; 3 rails meeting = divide the tenon height into thirds, etc.

**Implementation:** Add notch CUTs after shoulder CUTs but before mirroring the rail. Use construction planes at the tenon's side face (offset from the rail's build plane by `leg_size / 2 - mt_tt / 2`). The notch rectangle dimensions reference `mt_tw / 4` and the derived notch depth expression. When the rail is mirrored, the notches mirror correctly. Tested (TV console).

### Joinery Templates (`from helpers.templates import ...`)

Reusable templates for joints that involve 4+ features with variant logic. For simpler joints (dado, rabbet, T&G), use inline `af` helpers directly — a sketch + CUT is 2 features, not worth templating.

| Template | Use Case | Key Functions |
|----------|----------|---------------|
| `mortise_tenon` | Rail-to-leg, shelf-to-side, any blind/through M&T | `define_params()`, `blind()`, `through()`, `bulk_cut_mortises()` |
| `domino` | M&T replacement, edge jointing, case/panel T-joints | `single()`, `grid()`, `four_corners()` |
| `finger_joint` | Boxes, drawers, decorative interlocking corners | `define_params()`, `box()` |
| `dovetail` | Box corners, drawer fronts, decorative joints | `define_params()`, `corner()`, `box()` |
| `half_blind_dovetail` | Drawer fronts (hides end grain) | `define_params()`, `box()` |
| `splayed_legs` | 4 compound-splayed legs with floor trim | `define_params()`, `build()`, `splay_offset()` |
| `dovetailed_drawer` | Complete drawer box (half-blind front + through back) | `define_params()`, `build()`, `pattern()` |

**When NOT to use templates:** Dado/rabbet (just `sketch_rect_model` + `ext_op CUT` — 2 features). Angled M&T (use inline `angled_tenon_end` from `woodworking/angled-construction.md`). Tongue & groove (inline pattern from `woodworking/joinery.md`).

### Hardware Templates (`from helpers.templates import ...`)

Templates for furniture hardware that create mortise pockets (CUT) and visual hardware bodies. The hardware body IS the mortise tool — CUT with `keepTool=True` creates both the recess and the visual representation.

| Template | Use Case | Key Functions |
|----------|----------|---------------|
| `butt_hinge` | Box lids, cabinet doors, chest lids | `define_params(size="small/medium/large")`, `mortise()` |
| `pull` | Drawer fronts, cabinet doors, box lids | `define_params(style="bar_3in/bar_4in/knob")`, `install()` |
| `chest_lock` | Jewelry boxes, blanket chests, tool chests | `define_params(size="small/medium/large")`, `lock_mortise()`, `keyhole()`, `strike()` |

**Trigger phrases:** hinges, pulls, knobs, handles, locks, latches, hardware, mounting holes, bolt holes, keyhole, strike plate, hinge mortise, leaf recess.

**Usage pattern (parametric templates):**
1. `define_params()` with size/style preset or custom dimensions
2. Call `mortise()` / `install()` for each hardware piece — takes a plane, origin, and size_map
3. Each function creates the hardware body AND CUTs its pocket in one operation

**STEP-based hardware install** (`from helpers import hardware`):

For McMaster-Carr STEP hinges, use `hardware.install_butt_hinge()` — one call handles import, rotation, fold, and rebate CUTs into both boards:

```python
hardware.install_butt_hinge(
    part_id="1603a3", comp=comp,
    back_body=back, lid_body=lid,                # lid styles
    # door_body=door, case_body=side,             # door styles
    pin_position=("box_l / 4", "box_w", "box_h"),
    style="lid_surface",  # lid_surface|lid_flush|door_surface|door_flush
    ev=ctx.ev, name="H1")
```

See `hardware/README.md` for pin_position meaning per style and ASCII diagrams.

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
| Fillets | `Part_Fil` | `Seat_Fil`, `LidEdge_Fil` |
| Chamfers | `Part_Ch` | `Lid_Ch`, `LegBottom_Ch` |

## Verification Checklist
1. Component tree shows logical grouping (or root-only for small pieces)
2. Timeline shows: build features > mirror, template > mirror > pattern
3. Change a major dimension > verify ALL sides update correctly
4. Change element width > verify counts increase/decrease on all sides
5. Section Analysis > verify joinery alignment
6. Verify no overlapping joints at corners
7. Body count matches expected (diagnostic print confirms no accidental merges or orphans)
8. **`validate_design` → passed.** Single call checks connectivity (1 cluster) + interference (0 real overlaps). Fix disconnected clusters by adding mechanical joinery; fix interferences by checking CUT operations.

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
| Body pattern creates extra bodies | `keepTool=True` CUTs in template history create ghost duplicates at each pattern instance | Ghost bodies are harmless — keep patterns for parametric counts. Filter ghost overlaps from `check_interference` by excluding void-on-void pairs. |
| Mortise CUT destroys the receiving board | CUT body diameter ≥ board thickness (e.g., 0.75" spindle in 0.75" rail) | Mortise diameter must be < board thickness. Leave ≥ 1/4 wall on each side. Use blind mortises (stub tenon), not through. |
| Fusion crashes / hangs on complex scripts | Too many individual features created in a loop (e.g., 140 dowels = 700+ timeline features). Each `dowel.single()` or `domino.single()` creates sketch + extrude + fillet + CUT. | **Use bulk CUT instead of per-element joints.** For repeated elements (spindles, slats) that insert into rails, build all bodies first (body_pattern), then CUT them ALL into the target in ONE `sp.combine(comp, rail, [all_spindles], CUT, True)` call. 8 bulk CUTs replaced 140 individual dowels in the crib build. |
| Sketch geometry at mirrored/wrong position on non-XY plane | `probe_sketch_axes` gives axis name but not sign; model +Z → sketch -Y on XZ planes | Use `probe_sketch_signs` or `modelToSketchSpace` for approximate positions, flip offset operator based on sign |
| Loose tenon (domino) bodies disappear | Second CUT used `keepTool=False`, consuming the body | Use `keepTool=True` on ALL CUTs for visible loose tenon joints |
| Rectangle deforms when parameter changes | `addTwoPointRectangle` lacks explicit H/V geometric constraints | Add `addHorizontal`/`addVertical` on all 4 lines after creation. Apply same rule to any sketch line that should stay H or V. |
| H/V constraint distorts triangle on YZ plane | On YZ planes, model-Y maps to sketch-V and model-Z to sketch-H — opposite of XZ planes. Using `addHorizontal` on a model-horizontal (same-Z) line that's sketch-vertical destroys the profile. | **Use `sp.probe_orientations(sk)`** to get correct H/V per model axis. Never hardcode H/V on non-XY planes. |
| Chamfer fails with `createInput()` | Chamfer API requires `createInput2()`, not `createInput()` | Always use `chamferFeatures.createInput2()` and the nested `.chamferEdgeSets` collection |
| Fillet fails — radius too large | Fillet radius exceeds half the smallest adjacent face dimension | Reduce `fl_r`; keep it < half the shortest edge on any affected face |
| Fillet/chamfer selects wrong edges | Edge coordinate filter matches unintended edges (e.g., groove interior edges) | Add `edge.body.name` check; filter by both coordinate AND body |
| Chamfer fails with non-manifold error | Chamfer selected edges at groove/mortise boundaries where two volumes meet | Only chamfer outer perimeter edges (check bounding box), skip edges at joint interfaces. Never chamfer mating lines of joints. |
| No profile created on face sketch | Drawn rectangle has same height/width as the face — edges coincide with auto-projected face boundary, Fusion merges them | Use a **construction plane** at the same position instead of the face. No auto-projected edges → clean single profile. Common with full-width tenons. |
| Tenon extrudes into stretcher body | Default extrude direction on construction plane goes in +normal, which may point into the stretcher instead of into the leg | Place the tenon sketch plane at the **outer end** of the tenon (proud face or blind stop). Extrude inward — the default +normal direction goes toward the stretcher body. |
| Fillet API rejects BRepFace | `addConstantRadiusEdgeSet` requires edges, not faces | Iterate `face.edges`, deduplicate via `tempId`, add individual edges |
| `InternalValidationError: face` on sketch | CUT/JOIN modifies body topology, invalidating BRepFace references | Re-find face with `sp.find_face()` after each CUT/JOIN before next sketch |
| Face-sketch extrudes wrong profile | Auto-projected face edges and `sketch.project()` reference lines split profiles into fragments — `smallest_profile` picks a fragment instead of the drawn shape | **Always call `sp.refs_to_construction(sk)` before profile selection.** This converts all reference/projected lines to construction geometry so they don't form profile boundaries. Then `sp.smallest_profile(sk)` returns the correct drawn profile. This is mandatory for ANY sketch on a face or with projected references. |
| Symmetric extrude body 2× too thick | Passed full thickness to `ext_new_sym` — it applies `dist` to EACH side | Pass half-thickness: `ext_new_sym(comp, prof, "board_t / 2", ...)` |
| `sketch_rect_model` places body on wrong side of origin | Position dimensions use absolute distance — negative coordinates reflect to positive | Use manual sketch with `modelToSketchSpace` + width/height dimensions only (no position dimensions) |
| Shoulder CUT extends outward instead of into body | Default extrude direction on a body face points away from the body | Use `flip=True` on face-sketch CUT extrudes (see `woodworking/joinery/mortise-tenon.md`) |
| Orphan body in model from rewritten code | Rewrote a feature but only partially removed the old code (e.g., deleted old sketch but left its extrude) | Replace the entire old block when rewriting — don't patch around it. Partial cleanup like `deleteMe()` calls leaves orphan geometry. Old code is recoverable from git. |
| Domino has square corners (rectangular cross-section) | Used `sketch_rect` instead of `sketch_slot` for domino void body | **Always use `sketch_slot`** — real Festool dominos have stadium (rounded-end) cross-sections. See `woodworking/joinery/domino-joint.md` for the full implementation. |

## Incremental Build Strategy

Models are built **one component at a time**. Each component gets its own plan → build → validate cycle, keeping conversation context bounded regardless of total model complexity. The script file grows on disk between components, but each conversation cycle only deals with the current component's features.

**Small pieces** (boxes, trays — < ~8 bodies, 1-2 joint types) can be built in a single pass.

### Build Order

```
1. Plan ALL components upfront (high-level, one response)
2. For each component (separate plan → build → validate cycle):
   a. Shared parameters + helpers  (first component only)
   b. Component creation + construction planes
   c. Body extrudes + internal mirrors/patterns
   d. Splay moves if this component connects to splayed members (see angled-construction.md "Stretcher Splay Matching")
   e. Internal joinery (JOINs within the component)
   f. Validate with capture_design
3. Cross-component operations (root-level, one cycle):
   a. Assembly proxy CUTs (mortises, dados, grooves)
   b. Validate body count and interference
4. Details (final cycle):
   a. Fillets, chamfers, decorative cutouts
   b. Validate → apply_appearance → get_product_shots → present to user
```

### Why Component-by-Component

The conversation context is the bottleneck, not the script. Each component cycle adds ~5-15 features worth of code, errors, and validation to the conversation. After the cycle completes and the agent moves to the next component, only the script file carries forward — the conversation context for previous components can be compressed.

**Phase-based (old, hits token limits on complex models):**
```
Phase 1: ALL structure (all components) → huge script + debug context
Phase 2: ALL joinery (all components) → even bigger
Phase 3: ALL details → biggest
```

**Component-based (scales to any complexity):**
```
Component A: structure + internal joinery → bounded context → done
Component B: structure + internal joinery → bounded context → done
...
Cross-component: CUTs → bounded context → done
Details: fillets → bounded context → done
```

### Rules

1. **One component per build cycle.** Plan the component, write its section of the script, execute, validate. Don't combine multiple components in one cycle.
2. **Validate after each component.** Call `capture_design` to verify body count, positions, and volumes for the component just built.
3. **Auto-proceed on success.** If validation passes, immediately plan the next component. Do NOT wait for user approval between components.
4. **Same file, growing content.** All components accumulate in the same `.py` file. Each cycle appends to the existing script.
5. **Each script execution rebuilds from scratch.** The full script runs every time (document reuse pattern). This is fast — Fusion rebuilds a 100-feature timeline in seconds.
6. **Plan before code, always in separate responses.** Before each component, output its step list as text. Then write the code and execute in the next response.
7. **Cross-component operations are a separate cycle.** After all components are built, one final cycle adds root-level CUTs via assembly proxies.
8. **Details are the last cycle.** Fillets and chamfers require all geometry to exist first.
9. **Show final result.** After the last cycle, call `apply_appearance` then `get_product_shots` to capture presentation-quality images and present to the user.
10. **Replace, don't patch.** When an approach doesn't work and you rewrite it, **replace the old code block entirely** — don't add new code below while partially cleaning up the old (e.g., calling `deleteMe()` on an old sketch but leaving its extrude). Partial cleanup creates orphan bodies invisible in code review but visible in the model. The old code is always recoverable from git or undo, so replacing is safe.
11. **Detect UI changes automatically.** When working on an existing design, call `get_changes` at conversation start and before any `execute_script`. If changes are detected, capture them with `sync_script`, interpret the user's intent (UI edits are design signals, not literal specs), then implement correctly following the decision framework in `woodworking/incremental-updates.md`. The default is to rebuild the affected section properly, not to replicate the UI edit verbatim.

### What Goes Where

| Where | What |
|-------|------|
| **First component cycle** | Document preamble, shared parameters, shared helpers, midplanes |
| **Each component cycle** | `make_comp`, component-local planes, extrudes, internal mirrors/patterns/JOINs |
| **Cross-component cycle** | Assembly proxy creation, root-level Combine CUTs (`keepTool=True`) |
| **Details cycle** | Fillets, chamfers (edge selection by coordinate or face) |

### Keeping Each Cycle Bounded

When writing code for a new component, do NOT re-read the entire script. Instead:
- Read only the last ~20 lines (to see where to append)
- Know the parameter names and body names from the plan (established in the first cycle)
- Append the new component's code block

When debugging, focus only on the current component's features — don't re-analyze earlier components that already validated.

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

Every script should end with five standard steps:

```python
# 1. Hide construction elements (clean viewport)
for sk in root.sketches:
    sk.isVisible = False
for cp in root.constructionPlanes:
    cp.isLightBulbOn = False
for ca in root.constructionAxes:
    ca.isLightBulbOn = False

# 2. Diagnostic body count per component
for comp_name, comp in [("Posts", post_c), ("Rails", rail_c), ...]:
    names = [comp.bRepBodies.item(i).name for i in range(comp.bRepBodies.count)]
    print(f"{comp_name}: {len(names)} bodies")
names = [root.bRepBodies.item(i).name for i in range(root.bRepBodies.count)]
print(f"Root: {len(names)} joinery voids")

# 3. Apply wood appearance (grain-aligned texture on all bodies)
sp.apply_appearance("white oak")
```

**Step 3 is required** — scripts without `sp.apply_appearance()` produce grey models. Use the species the user requested; default to white oak if none specified. See `woodworking/appearance.md` for species and grain details.

After the script runs, call `get_product_shots` via MCP to capture presentation images. It handles camera positioning, artifact cleanup, and framing automatically — no fit-view or hide-sketch code needed in the script.

## MCP Live Execution

When an MCP connection to Fusion 360 is available (via the ShopPrentice add-in), you MUST automatically execute the script after generating it. Do not wait for the user to ask — the full generate-execute-verify loop is the default workflow.

### Available MCP Tools

| Tool | Purpose |
|------|---------|
| `capture_design` | Full design introspection: parameters, component tree with body geometry and sketch dimension details, timeline features (including chamfers and fillets). |
| `get_timeline_state` | Roll timeline to any index, capture body geometry at that point, restore position. |
| `execute_script` | Run a complete Python script in Fusion 360. Returns `isError` flag + full stack trace on failure. Failed scripts are rolled back automatically. Set `sandbox=true` to run in a throwaway document. Set `clean=true` to delete all existing features before running — enables clean rebuild of an existing model. The entire clean+execute is one transaction: Ctrl+Z reverts to the previous state. |
| `get_screenshot` | Quick viewport capture for build validation (1024x1024, as-is with artifacts). Use during builds to verify geometry. |
| `get_product_shots` | Final presentation screenshots. Hides construction artifacts, FOV-aware framing, multiple views in one call (default: iso-top-right + front + right at 2048x2048). Supports `style` (shaded/transparent) and `bodies` (detail framing). Use after `apply_appearance`. |
| `get_selection` | Read the user's current UI selection. Returns structured info per entity type (body, face, edge, occurrence) AND full feature details when a feature is selected (Sketch with curves/dimensions/constraints, Extrude with operation/distance/sketch, Combine with target/tool bodies, Mirror, Pattern, Move, Chamfer, Fillet). Use when the user says "what is this?" or "make this thicker". |
| `set_selection` | Highlight entities in the UI by name or token. Use after `capture_design` identifies a problem body — select it so the user sees which one. |
| `modify_parameters` | Change parameter expressions with incremental recompute. Much faster than re-running the script. Use for iterative tuning ("make shelves deeper"). |
| `validate_design` | **Single-call structural validation.** Runs connectivity (1 cluster?) + interference (0 real overlaps?) and returns pass/fail. Call this after the final build cycle — replaces separate `check_connectivity` + `check_interference` calls. |
| `check_interference` | Detect body collisions. Diagnostic — use standalone when investigating a specific interference. Normally called via `validate_design`. |
| `check_connectivity` | Verify all structural bodies form 1 connected cluster. Diagnostic — use standalone when investigating disconnected parts. Normally called via `validate_design`. |
| `suppress_features` | Toggle timeline features on/off. Diagnostic tool — suppress a suspicious feature, check if it fixes the problem, unsuppress to restore. |
| `get_changes` | Snapshot & diff. First call captures a baseline; subsequent calls return what changed — parameter expression changes, sketch dimension changes, body additions/removals, feature count delta. Use between iterations or when the user says "I changed something". |
| `sync_script` | Auto-sync UI changes back to a script. Pass the original script source (or omit to use the tracked script from the last execute_script run) — auto-patches user parameter expression changes, reports feature-level param edits, feature additions, and feature removals with script context for the agent to apply. |
| `get_document_status` | Check if the active document was built by a known script. Returns `tracked` (true/false), `pendingChanges` count, and `canUpdate` flag. Call before attempting incremental updates. |
| `apply_appearance` | Apply wood appearance with grain-aligned texture. Auto-detects fiber direction from bounding box longest axis, with dovetail-aware constraints (dovetailed edges = end grain → grain excluded from that axis). Call once after final validation, before screenshots. |

### Execution + Validation Loop

After generating each component's code, run this loop:

1. **Execute** — call `execute_script` to run the full script in Fusion 360. The script rebuilds from scratch each time (document reuse pattern).
2. **On error** — the `content` field contains the full Python stack trace. Analyze, fix only the current component's code, and re-execute (see Error Retry Rules below).
3. **On success — validate with `capture_design` + `validate_design`:**
   - Call `capture_design` to verify body count, names, bounding boxes.
   - **ALWAYS call `validate_design`** — checks connectivity (1 cluster) and interference (0 overlaps). This is mandatory after every successful execution, not just the final cycle. Skipping it risks undetected body collisions (e.g., a divider overlapping a rail).
   - Report: `"12 bodies, validate_design PASSED."`
4. **If validation fails** — use `get_timeline_state` to bisect the timeline and pinpoint the problem feature (see Diagnosing with Timeline Rollback below). Fix and re-execute.
5. **Auto-proceed** to the next component if validation passes.
7. **Appearance + product shots at the end** — after structural validation passes, call `apply_appearance` then `get_product_shots`. Product shots auto-hide construction artifacts, frame the model properly, and capture multiple views in one call. See `woodworking/appearance.md` for species and grain details.

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

> **Full reference:** `woodworking/mcp-advanced.md` — provenance checking, selection-driven interaction, change detection, script sync, sandbox mode.

Quick reference:
- **Dimension changes:** `get_document_status` → `modify_parameters` → `capture_design` to validate → update `.py` file.
- **Structural changes:** Read tracked script → edit → `execute_script(clean=true)`.
- **UI tweaks:** `sync_script` auto-patches parameter expression changes, reports feature-level edits for agent.
- **Sandbox:** `execute_script(sandbox=true)` runs in throwaway document for safe validation.

### Example Flow

```
Response 1 (plan): High-level plan — all components, build order, joinery strategy

Response 2 (plan): Case component — Front, Back, Left, Right boards
Response 3 (build): write box.py (preamble + params + helpers + Case component)
  → execute → capture_design → validate 4 bodies, positions OK → auto-proceed

Response 4 (plan): Bottom component — panel + edge rabbets
Response 5 (build): append Bottom code to box.py
  → execute → capture_design → validate Bottom body + 4 Case bodies → auto-proceed

Response 6 (plan): Lid component — panel + edge rabbets
Response 7 (build): append Lid code to box.py
  → execute → capture_design → validate 6 bodies total → auto-proceed

Response 8 (plan): Cross-component CUTs — panel grooves, dovetails
Response 9 (build): append root-level CUTs to box.py
  → execute → capture_design → validate mortises cut, body count correct
  → body count wrong? → get_timeline_state to bisect → fix → retry
  → validation OK → auto-proceed

Response 10 (plan): Details — lid chamfer, edge fillets
Response 11 (build): append details to box.py
  → execute → capture_design → validate
  → validate_design → apply_appearance → get_product_shots → present to user
```

### Sandbox Mode

Use `execute_script` with `sandbox=true` to run a script in a throwaway document. The script executes in a fresh temporary document; on completion, a design snapshot (parameters, bodies, dimensions, feature count) is returned and the temp document is discarded. The user's active document is never modified.

**When to use sandbox:**
- Validating a script before committing to the real design (especially complex joinery phases)
- Testing helper imports or sketch logic without risk
- Exploring "what if" variations without polluting the undo history

**Behavior:**
- ActionLog events are suppressed during the sandbox run — the user's `get_changes` baseline is unaffected
- The sandbox document has no user parameters from the real design — scripts that reference existing parameters will fail unless they create their own
- Returns `{sandbox: true, snapshot: {...}}` on success
- On error, the temp document is closed and the original document is restored automatically

**Not a substitute for the real execution loop.** Sandbox validates that a script runs without errors and produces expected geometry, but the real design's parameter expressions and timeline context may differ. Always follow sandbox validation with a real `execute_script` run.

### Important

- Always generate complete, standalone parametric scripts. MCP is the delivery mechanism — the script must also work when pasted into Fusion 360's script editor.
- Scripts using `from helpers import sp` need the addin's `helpers/` directory on the Python path (automatic when run via `execute_script`). For standalone use outside MCP, copy `addin/helpers/` alongside the script.
- Never generate partial snippets that only work via MCP.
- Scripts must NOT catch exceptions — let them propagate so Fusion 360 aborts the transaction and returns the full error to the agent.

### Screenshots

After the final phase, call `get_product_shots` for presentation images. It handles everything automatically — artifact cleanup, FOV-aware framing, multiple views, visual style. See [woodworking/screenshots.md](woodworking/screenshots.md) for camera direction details.

- **Validation during builds**: `get_screenshot` (quick, 1024x1024, as-is)
- **Final presentation**: `get_product_shots` (2048x2048, cleaned up, multiple views)
- **Transparent views**: `get_product_shots(style="transparent")`
- **Detail shots**: `get_product_shots(bodies=["Post_FL", "Rail_FrontBot"], fill=0.90)`

### MCP Timeout

The ShopPrentice add-in's main-thread execution timeout is set in:
`addin/server/mcp_server.py` → `_execute_on_main_thread` → `timeout = 300`

Default is 300s (5 min). If scripts still time out, increase this value and restart the add-in.

See `mcp/README.md` for setup instructions.
