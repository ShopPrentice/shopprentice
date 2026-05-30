# Fusion 360 Parametric Furniture Modeling

You are generating a Fusion 360 Python script to build a parametric furniture model. Follow these rules strictly.

## Before You Start: Pick the Mode

Before writing any code, decide whether you are **building from scratch** or **adding to an existing model**. Call `capture_design` to see the current document state:

- **Empty document** → ground-up build. Use `execute_script(clean=True)` each phase; Ctrl+Z reverts.
- **Existing model you built in this session (tracked)** → iterate by editing the script and re-running `execute_script(clean=True)`.
- **Existing model the user built manually, or from a script you don't have** → **additive mode**. Do NOT use `clean=True` — it would wipe the user's work. Call `execute_script` WITHOUT `clean`, looking up bodies by name via `root.allOccurrences` and appending features to the timeline. Read `docs/mcp-advanced.md` (Approach 2) for the full pattern before writing code.
- **Tracked model with unsynced UI changes** → call `sync_script` first, then decide rebuild vs additive.

The `execute_script` tool enforces this at the tool level: `clean=True` is **rejected** on untracked or unsynced documents with a structured error telling you which mode to use. Treat the rejection as a signal that you picked the wrong mode — adjust, don't reach for `force_clean=True` unless you truly intend to wipe the document.

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
   - **Use slotted fasteners** for cross-grain top-to-apron connections: `tabletop_button` (shop-made small L-shaped wooden blocks / clips whose tongue rides in an elongated slot — all-wood, any count per side), `tabletop_bracket` (steel L-bracket with slotted screw holes), Z-clips, or figure-8 fasteners. The slot allows the panel to slide across the grain while staying flat.
   - **Rigid attachment is OK** when the apron runs WITH the grain (both parts move together).

## Topic Reference

This skill is modular. The core (this file) covers fundamentals needed for every project. **Read topic files ONLY when you need them** — do NOT pre-load all files at the start. Read the type + style file during planning. Read joinery files only when writing joinery code. Read other topics only when the specific situation arises.

### Topic Files

| Topic | When to Read | Status | File |
|-------|-------------|--------|------|
| **Angled Construction** | Splayed legs, stretchers/rails on splayed legs, through-tenons, compound angles, Sweep, Move, SplitBody | Tested (counter stool) | `docs/angled-construction.md` |
| **Details & Finishing** | Fillets, chamfers, edge treatments (Phase 3) | Planned — inline quick reference below | `docs/details-and-finishing.md` |
| **MCP Advanced** | Modifying existing designs, fixing dimensions, adding features to built models, delete-and-rebuild timeline sections | Tested (bar side table) | `docs/mcp-advanced.md` |
| **Appearance** | Applying wood species, grain direction, multi-species designs — read before calling `apply_appearance`. Includes the `# APPEARANCE SPEC` comment-block convention for persisting grain overrides / multi-pass finish across `execute_script(clean=True)` rebuilds | Tested (blanket box) | `docs/appearance.md` |
| **Hardware Installation** | Importing STEP hardware (bed rail fasteners, hinges), positioning, caching, direction detection, component organization | Tested (queen + twin beds) | `docs/hardware-installation.md` |
| **Joinery Rules** | Combine-based joinery, tooling bodies, edge rabbets, cross-component CUT patterns | Tested | `docs/joinery.md` |
| **Screenshots** | Camera positioning, standard shots, transparent views, detail framing | Tested | `docs/screenshots.md` |
| **Incremental Updates & Build Strategy** | Build order, component-by-component workflow, document management, script epilogue, interactive editing, rebuild-vs-patch | Tested | `docs/incremental-updates.md` |
| **Replication & Common Errors** | Mirror, Pattern, body pattern ghost bodies, mirror+pattern limitation, 24-row error table | Tested | `docs/fusion-api-rules.md` |
| **Helpers Reference** | `sp.*` function signatures, `sketch_rect_model`, `ev()`, feature builders | Tested | `docs/helpers-reference.md` |
| **Organic Shapes** | Self-contained designer + recipe doc for sculpted forms. Shape taxonomy (5 classes): (1) turned/spindled parts — revolve, (2) flat-plan outlines — closed spline + extrude, (3) 3-D organic solids (lens-profile seats, rounded finial tips) — multi-section loft + tangent end conditions, (4) sculpted dish/saddle — sphere CUT, (5) character surfaces — Form T-splines (out-of-scope for scripting). Classes 1–4 include inline API snippets; also covers the approximate→refine→capture iteration loop and through-tenon trimming on organic surfaces | Tested (Esherick stool) | `docs/organic-shapes.md` |
| **Loft** | Deep feature reference for advanced loft variants: closed-ring topology, rail/centerline guides, 1→N→1 branching manifolds, surface-only and loft-as-cut variants, closed-spline cross-section generators (kidney/star/cardioid), all end-condition types. **Don't preload** for common organic shapes — use the inline recipes in `organic-shapes.md` instead. Read this file only when a build actually needs one of these variants | Tested (18 fixtures) | `docs/loft.md` |

### Joinery Reference Files

Read the specific joint file **before writing joinery code**. Each file has parameters, geometry workflow, replication strategy, and pitfalls. Choose the joint type based on grain orientation at the interface (rule 9) — end-grain-to-side-grain connections need mechanical interlock (M&T, dovetail, domino), while long-grain-to-long-grain can use glue alone.

**Status key:** "Tested" means the technique was built end-to-end in a real model, hitting and resolving actual API pitfalls. "Draft" means the file has plausible instructions but hasn't been validated through a real build — expect missing pitfalls and possible wrong API sequences. When using a Draft file, validate each step with `capture_design` and be ready to debug.

| Joint | When to Read | Status | File |
|-------|-------------|--------|------|
| **Mortise & Tenon** | Leg-to-rail, stretcher-to-leg, frame-and-panel, table aprons, any rail-into-post connection | Tested (counter stool — blind, through & angled variants) | Inline in skill + `mortise_tenon` template |
| **Drawbore M&T** | Stretcher-to-leg with offset pins for permanent tightness — workbenches, trestle tables, timber frames | Tested (Roubo workbench — through & blind variants) | `docs/joinery/drawbore.md` + `drawbore` template |
| **Domino** | Hidden structural joints, kick boards, shelf-to-back, panel alignment — any time you need a loose tenon | Tested (counter stool, bookshelf) | `docs/joinery/domino-joint.md` |
| **Dovetail** | Drawer fronts, premium boxes, visible corner joints where mechanical strength matters | Tested (pencil box, wrap box) | `docs/joinery/dovetail.md` |
| **Box Joint** | Boxes, drawers, decorative interlocking corners — simpler alternative to dovetails | Draft | `docs/joinery/box-joint.md` |
| **Dado & Rabbet** | Shelves into sides, case backs, drawer bottoms, any panel-into-groove connection | Tested (bookshelf, template fixtures — through/stopped dado, rabbet, panel groove) | `docs/joinery/dado-rabbet.md` |
| **Bridle Joint** | Frame corners, T-connections, open mortise-and-tenon at end of a rail | Draft | `docs/joinery/bridle-joint.md` |
| **Lap Joint** | Flat frames, cross braces, grid assemblies, half-lap at crossings | Draft | `docs/joinery/lap-joint.md` |
| **Miter Joint** | Picture frames, trim, hidden end grain at corners | Draft | `docs/joinery/miter-joint.md` |
| **Spline Joint** | Reinforced miters, decorative accents across a joint line | Draft | `docs/joinery/spline-joint.md` |
| **Dowel Joint** | Edge joining, panel glue-ups, face frames, spindle-to-rail, round-peg alignment | Tested | `docs/joinery/dowel-joint.md` + `woodworking/templates/dowel.py` |
| **Pocket Hole** | Face frames, quick assemblies, tabletop attachment — screw-based | Draft | `docs/joinery/pocket-hole.md` |
| **Bed Rail Fastener** | Bed rail to post — detachable STEP hardware (mortise bedlock, hooks + slots) | Tested (queen + twin beds) | `woodworking/templates/bed_rail_fastener.py` + `docs/hardware-installation.md` |
| **Tenon Wedge** | Through tenon tightening, fox wedging (blind tenons), Windsor spindle/stretcher locking — rect (2 wedges) or round (1 centred, trimmed to cylinder). Grain detected via principal axes of inertia; pass `grain_dir=` for ambiguous mortise pieces (seats, slabs) | Tested (Windsor chair — splayed legs + angled stretchers) | `docs/joinery/tenon-wedge.md` + `tenon_wedge` template |
| **Bowtie / Butterfly Key** | Live edge slab crack stabilization, decorative inlay | Tested (twin bed) | `woodworking/templates/bowtie.py` |
| **Tusk Tenon** | Knock-down through-tenon with tapered key — trestle tables, knock-down furniture, timber frames. Key blade MUST be narrower than tenon width. Multi-parent joint (key bears on receiver AND rides rail) | Tested (trestle table — through + mirror) | `docs/joinery/tusk-tenon.md` + `tusk_tenon` template |
| **Tabletop Button** | Shop-made wooden top attachment — small L-shaped blocks (also: desktop clips, wood top clips) whose tongue rides in an elongated apron/frame slot, allowing cross-grain wood movement. Use instead of steel `tabletop_bracket` for all-wood builds. Caller decides pattern count (3, 4, or more per side) | Tested (trestle table) | `tabletop_button` template |

**Read the topic/joinery file BEFORE writing code** that uses those techniques. The core skill provides the routing — the reference files provide the implementation details. For Draft files, treat instructions as a starting point and validate aggressively.

### Style & Type Guides

Before planning, identify the **furniture type** and **design style** from the user's request. Load the matching files — they provide component checklists, connection requirements, hardware needs, proportions, and detail patterns specific to that combination.

**Identify type** from what the user is building:

| Type | Keywords | File |
|------|----------|------|
| Chair | chair, dining chair, side chair | `docs/types/chair.md` |
| Stool | stool, counter stool, bar stool, step stool | `docs/types/stool.md` |
| Bench | bench, entryway bench, garden bench | `docs/types/bench.md` |
| Sofa | sofa, couch, settee, loveseat | `docs/types/sofa.md` |
| Dining table | dining table, farm table, harvest table | `docs/types/dining-table.md` |
| Coffee table | coffee table, cocktail table | `docs/types/coffee-table.md` |
| Side table | side table, end table, nightstand, accent table | `docs/types/side-table.md` |
| Desk | desk, writing desk, secretary | `docs/types/desk.md` |
| Console table | console, TV console, media console, credenza | `docs/types/console-table.md` |
| Chest | chest, trunk, blanket chest, toy box, hope chest | `docs/types/chest.md` |
| Box | box, pencil box, jewelry box, keepsake box | `docs/types/box.md` |
| Cabinet | cabinet, cupboard, pantry, hutch | `docs/types/cabinet.md` |
| Dresser | dresser, bureau, chest of drawers | `docs/types/dresser.md` |
| Bookshelf | bookshelf, bookcase, shelving unit | `docs/types/bookshelf.md` |
| Wardrobe | wardrobe, armoire, closet | `docs/types/wardrobe.md` |
| Sideboard | sideboard, buffet, server | `docs/types/sideboard.md` |
| Bed frame | bed, bed frame, platform bed, four-poster | `docs/types/bed-frame.md` |
| Crib | crib, baby crib, toddler bed | `docs/types/crib.md` |
| Planter | planter, window box, plant stand | `docs/types/planter.md` |
| Pergola | pergola, arbor, trellis, gazebo | `docs/types/pergola.md` |
| Mirror frame | mirror, mirror frame, looking glass | `docs/types/mirror-frame.md` |
| Shelf | shelf, floating shelf, wall shelf, ledge | `docs/types/shelf.md` |

**Identify style** from visual cues, user description, or reference photos:

| Style | Keywords / Visual Cues | File |
|-------|----------------------|------|
| Modern | clean lines, minimal, contemporary, square edges, hidden hardware | `docs/styles/modern.md` |
| Shaker | through dovetails, tapered details, applied base, brass hardware, simple lines | `docs/styles/shaker.md` |
| Craftsman | exposed tenons, corbels, quartersawn oak, thick stock, Arts & Crafts | `docs/styles/craftsman.md` |
| Mid-century | tapered legs, floating tops, thin profiles, hidden joinery, Danish, Scandinavian | `docs/styles/mid-century.md` |
| Rustic | thick boards, farmhouse, reclaimed, visible fasteners, breadboard ends | `docs/styles/rustic.md` |
| Nakashima | live edge, natural edge, slab, organic, bowties, butterfly keys, walnut slab, free-form | `docs/styles/nakashima.md` |

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

**Anchor every non-root sketch to projected parent geometry, never to the sketch origin (MANDATORY):**
For each sketch INSIDE a component that does NOT hold the root body, `validate_deps` (run by
`validate_design`) requires all three of: (1) it PROJECTS real parent geometry (an assembly-context
proxy face for a cross-component parent), (2) it uses NO Fix/Ground constraint, and (3) it is FULLY
constrained relative to that projection with **no dimension touching the sketch origin** — the only
free DOF allowed are fit-point spline INTERIORS (each spline's start/end must be anchored). The single
root body (`ref=origin`) is exempt: its own component's sketches may dimension from the origin.

**Pick ONE of these three ways to comply — simplest first. Do NOT hand-roll origin math.**

1. **`anchor=` on the sketch helper or joinery template (preferred — compliant from the start).**
   `sketch_rect_model`, `sketch_slot_model`, and the joinery templates (`mortise_tenon`, `dovetail`,
   `half_blind_dovetail`, `domino`, `finger_joint`, …) all take an optional `anchor=dict(...)` that
   projects a parent face and dimensions the part from a projected corner instead of the origin:
   ```python
   sk, prof = sp.sketch_rect_model(comp, plane, (x0,y0,z0), {"x":"w","y":"d"}, "Shelf_Sk", ev=ev,
       anchor=dict(parent_body=side_left, parent_occ=sides_occ, face_axis="z", face_dir=+1,
                   anchor_xyz=("0 in","board_thick","z0"), off1=("x","w_off"), off2=("y","d_off")))
   ```

2. **`sp.reanchor(...)` — build normally, then ONE call (easiest retrofit).** Build the sketch in the
   default (origin) mode, then hand it a parent face + ONE real parent corner; it retargets every
   origin dimension automatically (signs via `abs()`, the origin is auto-excluded, geometry unchanged,
   full constraint preserved):
   ```python
   sk, prof = sp.sketch_rect_model(comp, plane, (x0,y0,z0), {"x":"w","y":"d"}, "Shelf_Sk", ev=ev)
   sp.reanchor(sk, side_left, sides_occ, "z", +1, ("table_l", "0 in", "z0"))
   ```

3. **Hand-anchor with the primitives** (custom geometry): `sp.project_face(sk, parent, occ, axis, dir)`,
   then `a = sp.anchor_pt(sk, mx,my,mz)`, then `sp.rdim(sk, d, a, my_pt, orient, axis, expr)`. Draw the
   profile from explicit MODEL corners with `addByTwoPoints` (NOT `addTwoPointRectangle`) and add an
   H/V constraint to EVERY edge (omitting the closing edge leaves a free DOF).

**Gotchas the tools already handle:** `anchor_pt` skips the sketch-origin point (you cannot accidentally
re-anchor to it) and finds projected CIRCLE/ARC centres (round/turned parts have no corner vertices).
The one case to watch: if the part's OWN corner sits at world (0,0), don't dimension that vertex — use
`sketch_rect_model(anchor=..., size_far=True)` to size the far edges and anchor an adjacent corner.

**Wrong pattern:** a plain `sketch_rect_model(...)` / `sketch_slot_model(...)` / template call, or any
`addDistanceDimension(sk.originPoint, …)`, on a NON-root sketch with no anchoring follow-up — it fails
`validate_deps` (origin reference + not anchored). After building, confirm `validate_design` prints
"All non-root sketches fully constrained against references".

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

> **Full reference:** `docs/details-and-finishing.md` — edge selection strategies, chamfer types, code patterns, sizing constraints.

Quick reference:
- **Fillet:** `filletFeatures.createInput()` -> `inp.addConstantRadiusEdgeSet(edges, radius, propagate)`
- **Chamfer:** `chamferFeatures.createInput2()` -> `inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(edges, distance, propagate)`
- Note: chamfer uses `createInput2()` (not `createInput()`) and has a nested `.chamferEdgeSets` collection.
- The API requires `BRepEdge` objects, never `BRepFace`. Iterate face edges and deduplicate via `tempId`.


> **Replication Strategy & Common Errors:** `docs/fusion-api-rules.md` — Mirror, Pattern, body pattern ghost bodies, mirror+pattern limitation, typical replication sequence, 24-row error table.

## Standard Helpers

> **Full reference:** `docs/helpers-reference.md` — all `sp.*` function signatures, `sketch_rect_model` usage and limitations, `ev()` semantics, feature builder table.

Scripts use `from helpers import sp` and `ctx = sp.DesignContext()`. Key functions: `sketch_rect_model`, `ext_new`, `ext_op`, `combine`, `mirror_body`, `mirror_feats`, `body_pattern`, `off_plane`, `make_comp`, `find_face`, `probe_orientations`.

## Joinery Rules

> **Full reference:** `docs/joinery.md` — combine-based workflow, tooling bodies, edge rabbets, cross-component CUT, bulk CUT, timeline ordering. Joint-specific files: see Joinery Reference Files table above.

**Core principle:** Build the tenon/tail as a body, CUT the receiving board (`keepTool=True`), JOIN to the owner. Timeline order: CUT first (root, assembly proxies), JOIN second (owning component). Cross-component: use `body.createForAssemblyContext(occ)` for CUT in root.

**Templates:** `mortise_tenon`, `domino`, `dovetail`, `finger_joint`, `half_blind_dovetail`, `splayed_legs`, `dowel`, `drawbore`, `tenon_wedge`, `tusk_tenon`, `tabletop_button`, `dovetailed_drawer`. Use for joints with 4+ features; write inline for dado/rabbet/T&G. See `docs/joinery/README.md`.

**Hardware:** use `hardware.recommend_hinge()` + `hardware.install_butt_hinge()` for hinges, plus the `pull` and `chest_lock` templates for non-hinge hardware. See `docs/hardware-installation.md`.

## Incremental Build Strategy

> **Full reference:** `docs/incremental-updates.md` — component-by-component build order, what-goes-where, document management, script epilogue, interactive editing, rebuild-vs-patch.

**Script location:**
- **ALWAYS create scripts in `~/shopprentice-projects/`.** Create the directory if it doesn't exist. Each project gets a subfolder named after the piece (e.g., `~/shopprentice-projects/dovetailed-box/`).
- **NEVER modify files in `~/.shopprentice/repo/`** — that is the installed skill/add-in, not a project directory. The `examples/` folder there is read-only reference material.
- If an example script is relevant, READ it for reference but write the new script to the project folder.

**Project structure:** Each project folder contains:
```
~/shopprentice-projects/dovetailed-box/
  dovetailed_box.py     # Fusion 360 parametric script
  README.md             # Auto-generated project doc (see below)
```

**README.md (MANDATORY):** After completing a build (or at the end of each session), write/update a `README.md` in the project folder with:
- **Description** — what was built, key design decisions
- **Status** — Complete / In Progress (what's done, what's remaining)
- **Parameters** — key user parameters and their current values
- **Build notes** — any issues encountered and how they were resolved
- **Screenshots** — paths to product shots if taken

This allows the user (or a new agent session) to resume work by reading the README to understand the project state. When resuming, ALWAYS read the project README first before making changes.

**Key rules:**
- **NEVER write more than one component's code per response.** Write Case → execute → validate → THEN write Bottom → execute → validate. Do NOT bundle multiple components in one code generation. Small pieces (< 8 bodies) may combine structure + joinery but still validate between components.
- Auto-proceed on success — do not wait for user approval between components.
- Same `.py` file, growing content. Cross-component CUTs are a separate cycle. Details last.
- Always end with `sp.apply_appearance()` + `get_product_shots`.
- Replace, don't patch — when rewriting code, remove the entire old block.

## MCP Live Execution

> **Full reference:** `docs/mcp-advanced.md` — MCP tool table, execution + validation loop, error retry rules, sandbox mode, timeline rollback diagnosis, modifying existing designs.

**Default behavior:** When MCP is available, ALWAYS execute automatically after generating code. Do not wait for user to ask.

**Loop:** execute_script → on error: fix + retry (max 3 per error) → on success: capture_design + validate_design (MANDATORY) → auto-proceed.

**Multi-agent / parallel sessions.** When agents run concurrently (a fan-out), the **Session Manager keeps a dedicated Fusion document per agent** (keyed by session ID); your `execute_script` / `capture_design` / `validate_design` calls operate on YOUR document and `clean=True` rebuilds only it, so parallel agents never collide. Fusion serializes execution — expect latency, not incorrectness — so run the normal loop with no document coordination. If you lose your binding or `claim_document` reports a conflict, re-bind (`resolution='transfer'` to take a contested doc); after a restore, `clean=True` is rejected until you `sync_script`. See `docs/mcp-advanced.md`.

**model.json:** Before writing the build script, create a `model.json` dependency tree — each entry pairs a `"body"` with its `"ref"`, the parent it was positioned from. `"ref"` may be one name or a list: every body needs ≥1 parent (a part seating against two lists both), and exactly one body references `"origin"` (the root). A two-parent sketch anchors to each parent's projected geometry on the axis that parent controls.

**Phase validation:** `validate_design` runs connectivity, interference, and dependency checks (single origin, sketch origin enforcement, bodies in components). Run it after EVERY phase. Completeness (all bodies tracked) is advisory — it won't fail the build.

**Final step:** apply_appearance → get_product_shots → present to user.

**Token efficiency:**
- `capture_design` returns a compact summary (body names + bounding boxes + params). Full capture saved to temp file (path in response) — Read it only when deep inspection is needed.
- `get_product_shots` and `get_screenshot` save images to files and return file paths. **Do NOT Read the image files** — just report the paths to the user. The user can open them directly.
- Prefer `validate_design` (text-only, ~100 tokens) over screenshots for intermediate validation.

<!-- SHOPPRENTICE_SCREENSHOT_MODE: none -->
**Screenshot mode: none** — do NOT call `get_product_shots` or `get_screenshot` at any point. Use `validate_design` for all checks. Report validation results as text only. This setting overrides any screenshot instructions in topic files.
<!-- END_SCREENSHOT_MODE -->

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
8. **`validate_design` → passed.** Single call checks connectivity (1 cluster) + interference (0 real overlaps) + dependency tree (single origin root, sketch origin enforcement, bodies in components). Run after EVERY phase.
