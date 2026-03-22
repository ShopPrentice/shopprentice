# Joinery Rules

Read this file when the project involves joinery (Phase 2+). For specific joint types beyond the ones covered inline here, read the corresponding file from `woodworking/joinery/`.

## Templates (Preferred for Complex Joints)

For joints with 4+ features and variant logic, use reusable Python templates from `addin/helpers/templates/`. Templates handle sketch geometry, CUT/JOIN operations, mirror/pattern replication, and parameter setup in a single function call.

```python
from helpers.templates import domino, mortise_tenon

# Domino grid — creates template void + body pattern + bulk CUT
domino.grid(comp, plane, start=(...), step_axis="x", step_expr="dm_sp",
            count_expr="dm_count", long_axis="x", long_expr="dm_w",
            short_expr="dm_t", depth_expr="dm_d",
            body_a=shelf, body_b=back, name="ShDm", ev=ctx.ev)

# M&T — blind mortise + tenon with optional shoulder
mortise_tenon.blind(comp, rail_body, leg_body, face_axis="y", ...)
```

**Check for a template first.** If one exists, use it. Only write inline for simple joints (dado, rabbet, T&G) or joints without templates. See `woodworking/joinery/README.md` for the full template table.

## Combine-Based Joinery (CRITICAL)

**Never draw separate mortise/socket sketches.** Build the tenon/tail as a separate body, then use Fusion 360 **Combine** to cut the receiving board. The tenon body IS the cutting tool — one shape guarantees the mortise exactly matches.

This applies to **all** joint types (whether using templates or inline code):
- **Mortise & tenon**: tenon body cuts the mortise, then joins the shelf
- **Dovetails**: tail body cuts the socket, then joins the top board
- **Tongue & groove**: tongue body cuts the groove, then joins the slat
- **Panel grooves**: panel body (with tongues from edge rabbets) cuts the groove in each receiving board via Combine CUT (`keepTool=True`). The tongue-board overlap IS the groove — guaranteed perfect fit. Through tongues produce through grooves; stopped tongues produce stopped grooves. No separate groove sketches needed.

## Tooling Body Pattern for Grooves

> **When a groove receives a paneled body with tongues** (bottoms, lids, drawer bottoms), use the panel body itself as the cutting tool instead (see **Panel grooves** above). The tooling body approach below is for standalone grooves that don't receive a panel — dados for fixed shelves, rabbets for backs, etc.

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

**Why this works:** The tooling body extends beyond the board edges, but Combine CUT only removes the intersection. Combined with the "grooves before joinery" build order (design philosophy point 8), this produces perfectly stopped grooves at corners without calculating stop positions.

**Stopped grooves for through-prevention:** When a groove must NOT be visible from the board's end (e.g., front/back bottom grooves hidden behind side boards), explicitly stop the groove by shortening its X span:
```python
# Stopped both sides — starts at board_thick, ends at box_length - board_thick
("board_thick", "board_thick - groove_depth", "groove_up"),
{"x": "box_length - 2 * board_thick", "y": "groove_depth"},
```

## Edge Rabbet Pattern for Floating Panels

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

**Pure subtractive — no JOIN step.** Corner notches where two rabbets intersect are naturally handled — the double-cut IS the corner notch.

**Rabbets are always through cuts.** The "stopped" concept applies to **grooves in case boards** (so the groove slot doesn't show on the board's end face), NOT to rabbets on panels.

**Asymmetric variation (sliding lids):** For a lid that slides out one side, skip the rabbet on the open edge.

## Cross-Component CUT via Assembly Proxies

When tenons live in component A (e.g., Shelves) but need to cut mortises in component B (e.g., Sides), use **assembly context proxies** in root:

```python
# Get proxies for bodies in their assembly context
shelf_proxy = shelf_body.createForAssemblyContext(shelves_occ)
side_proxy  = left_side.createForAssemblyContext(sides_occ)

# CUT in root component using proxies
combine(root, side_proxy, [shelf_proxy], CUT, True, "ShelfMortise")
```

This keeps features in their owning components while performing cross-component boolean operations in root.

## Bulk CUT (Preferred Over Per-Item CUT)

When multiple tool bodies (e.g., all patterned shelves) need to cut the same target, pass **all tools in a single Combine** rather than looping:

```python
# Collect ALL shelf body proxies (template + pattern copies)
all_shelf_proxies = [b.createForAssemblyContext(shelves_occ)
                     for b in all_shelf_bodies]

# ONE CUT feature creates ALL mortises at once
combine(root, left_side_proxy, all_shelf_proxies, CUT, True, "ShelfMortL")
```

Single CUT feature in the timeline instead of N separate features. When the pattern count changes, the CUT automatically picks up new bodies.

## Timeline Ordering for CUT + JOIN

When the same body serves as both a CUT tool (to create a socket/mortise) and a JOIN target (to merge into its parent):

1. **CUT first** (in root, via assembly proxies, `keepTool=True`) — the tool bodies survive
2. **JOIN second** (in the owning component) — the tool bodies merge into the parent

```python
# Step 1: Tail bodies cut sockets in side boards (tails survive)
combine(root, side_proxy, tail_proxies, CUT, True, "DT_Socket")

# Step 2: Tail bodies join into top board (tails consumed)
combine(top_comp, top_body, all_tails, JOIN, False, "DT_Join")
```

## keepTool for Visible Loose Tenons (Dominos, Dowels)

Loose tenon joints (dominos, dowels) have a **separate body** that remains visible after assembly. When a loose tenon CUTs mortises in two boards:

- **Both CUTs must use `keepTool=True`** so the tenon body survives.
- If either CUT uses `keepTool=False`, the tenon body is consumed.

```python
# Domino cuts mortise in board A (tenon survives)
combine(board_a, domino_body, CUT, True, "DM_CutA")
# Domino cuts mortise in board B (tenon STILL survives)
combine(board_b, domino_body, CUT, True, "DM_CutB")
# Result: both mortises cut, domino body visible between boards
```

## Inline Joint Types

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

## Additional Joint Types

For joints beyond M&T, T&G, and gap filling, **check for a template first** (`from helpers.templates import <name>`), then read the reference file for orientation rules and sizing constraints:

| Joint | File | Template | Prefix | Use For |
|-------|------|----------|--------|---------|
| Dado & Rabbet | `woodworking/joinery/dado-rabbet.md` | — (inline) | `dr_` | Shelves, case backs, drawer bottoms |
| Lap Joint | `woodworking/joinery/lap-joint.md` | — | `lj_` | Frames, cross braces, lattice |
| Box Joint | `woodworking/joinery/box-joint.md` | `finger_joint` | `bj_` | Boxes, drawers, decorative corners |
| Bridle Joint | `woodworking/joinery/bridle-joint.md` | — | `br_` | Frame corners, open mortise T-connections |
| Dowel Joint | `woodworking/joinery/dowel-joint.md` | — | `dw_` | Edge joining, panel glue-ups, face frames |
| Spline Joint | `woodworking/joinery/spline-joint.md` | — | `sp_` | Reinforced miters, decorative accents |
| Miter Joint | `woodworking/joinery/miter-joint.md` | — | `mj_` | Picture frames, trim, hidden end grain |
| Dovetail | `woodworking/joinery/dovetail.md` | `dovetail` | `dt_` | Drawer fronts, premium boxes, visible joints |
| Pocket Hole | `woodworking/joinery/pocket-hole.md` | — | `ph_` | Face frames, quick assemblies, tabletops |
| Domino Joint | `woodworking/joinery/domino-joint.md` | `domino` | `dm_` | Hidden structural connections, kick boards |
