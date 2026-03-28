# Dovetailed Pencil Box with Sliding Lid

A parametric dovetailed pencil box modeled in Fusion 360 via Python script. 9"L x 3"W x 2.5"H, 1/4" board stock with through dovetail corners, grooved bottom panel, and a sliding plywood lid that exits from the right side.

![Pencil box — iso top-right](screenshots/iso-top-right.png)

![Pencil box — iso top-left](screenshots/iso-top-left.png)

<p float="left">
  <img src="screenshots/front.png" width="49%" />
  <img src="screenshots/right.png" width="49%" />
</p>

## Example Prompt

```
/woodworking
Build a 9" x 3" x 2.5" pencil box in 1/4" stock with through dovetails at all four
corners, a grooved bottom panel, and a sliding plywood lid that exits from the right
side. Use 3 tails per corner. The bottom and lid should be 5/16" thick boards with
rabbeted tongues that fit into the grooves.
```

### Appearance

```python
sp.apply_appearance("brazilian rosewood")
```

---

## How to Run

**Via MCP (recommended):** If you have the [Fusion 360 MCP add-in](../../mcp/README.md) configured, just ask Claude to run it.

**Manual:** Fusion 360 > Utilities > Scripts and Add-Ins > (+) > select this folder > Run

**Script:** [`pencil_box.py`](pencil_box.py)

---

## Dimensions

All exposed as User Parameters (Modify > Change Parameters):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `box_length` | 9 in | Overall length (X) |
| `box_width` | 3 in | Overall width (Y) |
| `box_height` | 2.5 in | Overall height (Z) |
| `board_thick` | 0.25 in | Side/front/back board thickness |
| `bottom_thick` | 0.3125 in | Bottom panel total thickness (5/16") |
| `lid_thick` | 0.3125 in | Lid panel total thickness (5/16") |
| `groove_depth` | 0.125 in | Groove depth into boards |
| `groove_up` | 0.125 in | Bottom groove offset from Z=0 |
| `lid_down` | 0.125 in | Lid groove offset from top |
| `dt_angle` | 8 deg | Dovetail angle |
| `dt_tail_w` | 0.5 in | Tail width |
| `dt_tail_count` | 3 | Number of tails per corner |

---

## Design

Root-only build — all 6 bodies and features directly in root. No components, no assembly proxies. Uses `probe_sketch_axes` + `modelToSketchSpace` for correct axis mapping on all construction planes.

### Bodies

| Body | Description |
|------|-------------|
| `Front` | Front board, full height |
| `Back` | Back board, full height |
| `Side_Left` | Left side board, full height |
| `Side_Right` | Right side board, shorter (`open_height`) for lid opening |
| `Bottom` | Bottom panel with rabbeted tongue |
| `Lid` | Lid panel with 3-sided rabbeted tongue, slides out right |

### Modeling Sequence

1. **Front board** — XZ plane, extrude +Y by board_thick
2. **Back board** — offset XZ plane at Y=box_width-bt, full height
3. **Left side board** — YZ plane, full height
4. **Right side board** — offset YZ plane, open_height (shorter for lid)
5. **Bottom grooves** — all 4 boards (tooling body + Combine CUT); front/back grooves stopped at board_thick to hide behind side boards
6. **Lid grooves** — left, front, back (right side is the lid opening); front/back stopped on left, open on right
7. **Dovetail corners** — per-corner: trapezoid sketch > extrude as CUT into pin board > extrude as JOIN into side board > feature pattern both along Z
8. **Bottom panel** — board-first rabbet: full board at tongue footprint > rabbet CUT removes groove_up > lip JOIN restores inner area
9. **Lid panel** — board-first rabbet: full board > rabbet CUT > lip JOIN (no rabbet on right side for sliding)

### Key Techniques

- **Grooves before dovetails** — groove tool bodies extend beyond board edges but only CUT what exists. When tails are later joined, they're ungrooved — implicit stopped grooves at corners with zero extra geometry.
- **Stopped grooves** — front/back bottom grooves shortened to `box_length - 2 * board_thick` so they don't show at the ends.
- **Board-first rabbet pattern** — models panels the way a woodworker builds: start with full-thickness board, rabbet to create tongue/lip step. `bottom_thick` and `lid_thick` are total panel thickness, not just tongue.
- **Asymmetric lid** — lip JOIN footprint extends to right edge, so no rabbet forms on the sliding side.
- **Direct CUT/JOIN + feature pattern** — dovetails use extrude operations (not separate bodies + Combine), feature-patterned along Z. Fully parametric — changing `dt_tail_count` updates all corners.
- **Tooling body pattern** — groove tool bodies are NewBody extrudes consumed by Combine CUT (`keep_tool=False`). The board edge acts as an implicit stop.

---

## Customization

Change any parameter in Fusion 360's Change Parameters dialog. Key derived relationships:

- `bottom_tongue` = `bottom_thick - groove_up` — tongue thickness for bottom grooves
- `lid_tongue` = `lid_thick - lid_down` — tongue thickness for lid grooves
- `open_height` = `box_height - lid_thick` — right side board height / dovetail joint height
- `dt_pin_w` = `open_height / dt_tail_count - dt_tail_w` — derived pin width
- `dt_pitch` = `open_height / dt_tail_count` — tail spacing

Changing `dt_tail_count` updates all 4 corners automatically. Changing `box_height` adjusts the right side board, lid position, and dovetail layout.

---

## Materials & Cut List

For the default 9"L x 3"W x 2.5"H box in 1/4" stock:

| Part | Qty | Dimensions |
|------|-----|------------|
| Front/Back boards | 2 | 9" x 1/4" x 2.5" |
| Left side board | 1 | 2.5" x 1/4" x 2.5" |
| Right side board | 1 | 2.5" x 1/4" x 2-3/16" (open_height) |
| Bottom panel | 1 | ~8.75" x 2.75" x 5/16" (rabbeted) |
| Lid panel | 1 | ~8.875" x 2.75" x 5/16" (rabbeted 3 sides) |
