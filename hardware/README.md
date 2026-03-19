# Hardware Catalog

Parametric hardware installation for Fusion 360 furniture models. Imports real McMaster-Carr STEP files, positions them, and CUTs rebate pockets into boards.

## Catalog

Hardware parts are registered in `catalog.json` with STEP files in subdirectories (e.g., `hinges/`).

```python
from helpers import hardware

hardware.list_parts(category="hinge")
hardware.recommend_hinge(lid_length_cm=25.4)
```

## Butt Hinge Installation

`install_butt_hinge()` handles the complete installation in one call: STEP import, rotation, positioning, folding, and rebate CUTs. Screws from the assembly STEP are visual only (not boolean-CUT — thread geometry causes extreme memory usage in Fusion).

### Style Selection Guide

**Step 1: Lid or Door?**
- Lid: two boards meeting at a **horizontal** edge (lid flips up/down). Use `back_body` + `lid_body`.
- Door: two boards meeting at a **vertical** edge (door swings left/right). Use `door_body` + `case_body`.

**Step 2: Surface or Flush?**
- Surface: hinge leaves **visible** — rebated into board surfaces for a clean but visible look.
- Flush: hinge leaves **hidden** — folded closed between the boards, mortised into mating edges.

**Decision table:**

| Board Relationship | Hinge Visible? | Style | Pin Position |
|---|---|---|---|
| Lid hinged to back board | Yes, on back face | `lid_surface` | `(x_along, y_back_face, z_joint_line)` |
| Lid hinged to back board | No, hidden | `lid_flush` | `(x_along, y_back_face, z_joint_line)` |
| Door hinged to case side | Yes, at seam | `door_surface` | `(x_at_edge, y_seam, z_along)` |
| Door hinged to case side | No, hidden | `door_flush` | `(x_seam, y_front_edge, z_along)` |

**How to determine pin_position from board geometry:**
- Find the **joint line** where the two boards meet
- The pin sits at this joint line
- For lids: pin runs along X (horizontal), positioned at (x_fraction, y_back, z_top)
- For doors: pin runs along Z (vertical), positioned at the seam corner

### `lid_surface` — Box Lid, Visible Hinge

Leaves on the back face, rebated flush, hinge recessed into pockets. Barrel behind the back face.

```
        lid
  ======[===]======    <- leaf rebated into lid underside
        |   |
  ------[---]------    <- leaf rebated into back board
       (barrel)        <- projects behind back face
```

```python
hardware.install_butt_hinge(
    part_id="1603a3", comp=comp,
    back_body=back, lid_body=lid,
    pin_position=("box_l / 4", "box_w", "box_h"),
    style="lid_surface", ev=ctx.ev, name="H1")
```

**pin_position**: `(x_along_edge, y_back_face, z_joint_line)`

### `lid_flush` — Box Lid, Hidden Hinge

Hinge folded closed between lid underside and back board top edge. Hidden from outside. Barrel behind the back face.

```
  =====================    <- lid top surface clean
        |   |
  ------[---]---           <- leaf in back board top edge
        [   ]
  ======[===]======        <- leaf in lid underside
       (barrel)
```

```python
hardware.install_butt_hinge(
    part_id="1603a3", comp=comp,
    back_body=back, lid_body=lid,
    pin_position=("box_l / 4", "box_w", "box_h"),
    style="lid_flush", ev=ctx.ev, name="H1")
```

**pin_position**: `(x_along_edge, y_back_face, z_joint_line)`

### `door_surface` — Cabinet Door, Surface Mount

Hinge folded closed at Y seam between door and case side. Both leaves between boards, body-CUT mortise into both. Pin vertical at the board edge.

```
  case   [hinge]   door
  side   [bodies]  panel
  (deep) inserted  (thin)
         at seam
```

```python
hardware.install_butt_hinge(
    part_id="1603a7", comp=comp,
    door_body=door, case_body=side,
    pin_position=("0 in", "side_y", "h / 4"),
    style="door_surface", ev=ctx.ev, name="H1")
```

**pin_position**: `(x_at_edge, y_seam_between_boards, z_along_edge)`

### `door_flush` — Cabinet Door, Inset, Hidden

Inset door flush with case side. Hinge folded closed, hidden between boards. Barrel at front edge.

```
  case  [leaf]  door
  side  [leaf]  panel
       (barrel)
```

```python
hardware.install_butt_hinge(
    part_id="1603a3", comp=comp,
    door_body=door, case_body=side,
    pin_position=("seam_x", "side_y", "h / 4"),
    style="door_flush", ev=ctx.ev, name="H1")
```

**pin_position**: `(x_seam_between_boards, y_front_edge, z_along_edge)`

### Gap Support (door_flush only)

For reveal gaps between inset door and case side:

```python
hardware.install_butt_hinge(
    ..., style="door_flush", gap=ctx.ev("door_gap"), ...)
```

Rebate depth is computed from the actual positioned leaf geometry — how far each leaf extends past the board face after rotation, positioning, and folding. Pockets are open mortises (extended to the nearest board edge). Works for both left-side and right-side hinges — the offset and flip directions are auto-detected from the door body position relative to the pin.

**Gap scenarios (validated in `test_hinge_gap_logic.py`):**
- `gap = 0` → two-side rebate, symmetric, both boards cut
- `gap < barrel_d - plate_t` → two-side rebate
- `barrel_d - plate_t ≤ gap < barrel_d` → one-side rebate (case only)
- `gap ≈ barrel_d` → no rebate (surface mount)
- `gap > barrel_d` → ValueError

## Assembly STEP Files

Assembly STEPs in `assemblies/` contain hinge + screws in standard frame:
- **Pin along X**, leaves in XZ plane, thin in Y, centered at origin
- Both leaves coplanar (open flat)
- Screws pre-positioned in leaf holes

On import, bodies are classified by volume: 2 largest = leaves, 3rd = pin, rest = screws.
Screws are assigned to leaf_a (+Z side) or leaf_b (-Z side) by Z midpoint.

## API Reference

### `recommend_hinge(lid_length_cm=None, lid_length_expr=None, ev=None)`

Returns recommended part_id based on lid/door edge length. Uses `selection_guide` rules from catalog.

### `install_butt_hinge(part_id, comp, ...)`

Install a single butt hinge with rebate CUTs. Screws are visual only (included in assembly STEP but not CUT).

| Parameter | Description |
|-----------|-------------|
| `part_id` | Catalog part ID (e.g., `"1603a3"`) |
| `comp` | Target component |
| `back_body` / `lid_body` | Board bodies for lid styles |
| `door_body` / `case_body` | Board bodies for door styles |
| `pin_position` | `(x, y, z)` — barrel center (cm floats or expression strings) |
| `style` | `"lid_surface"`, `"lid_flush"`, `"door_surface"`, `"door_flush"` |
| `gap` | Door gap in cm (door_flush only) |
| `install_screws` | Accepted for compat; screws are visual only via assembly STEP |
| `ev` | Expression evaluator |
| `name` | Feature name prefix |

Returns dict with `occurrence`, `bodies`, `pin`, `leaves`, `part`, `barrel_d_cm`, `plate_t_cm`, `cuts`, `screws`.

### `install_butt_hinge_pair(part_id, comp, pin_y, pin_z, ...)`

Install a pair at 1/5 and 4/5 of the length along the pin axis. Accepts all `install_butt_hinge` parameters plus `lid_length_cm`/`lid_length_expr`.

### `install(part_id, comp, position, board=None, ...)`

Generic hardware install (pulls, locks, etc.). CUTs the entire part as a mortise.

## McMaster-Carr Parts

| Part ID | PN | Size | Length | Leaf Width | Screws |
|---------|-----|------|--------|------------|--------|
| `1603a2` | 1603A2 | Small | 0.75" | 0.313" | 2x #2 x 3/8" |
| `1603a3` | 1603A3 | Medium | 1.0" | 0.375" | 4x #2 x 3/8" |
| `1603a7` | 1603A7 | Large | 2.0" | 0.5" | 6x #8 x 5/8" |

Assembly STEPs in `assemblies/`. Bare hinge STEPs in `hinges/`. Screw STEPs in `screws/`.
