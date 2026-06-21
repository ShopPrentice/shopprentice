# Breadboard End

**Status: Draft**

## Overview

A **breadboard end** caps the end of a wide solid-wood panel — a tabletop, a drop-leaf, a cabinet door — with a narrower board whose grain runs **across** the panel. The panel grain runs lengthwise; the breadboard runs across the panel's end with its fibre direction **perpendicular** to the panel grain. The breadboard hides the panel's end grain and keeps the wide panel flat.

The defining problem of a breadboard is **wood movement**. A wide panel expands and contracts across its width with the seasons; the breadboard (running across that width) does not. If the breadboard were glued or pinned solid along its whole length, the panel would split. The classic solution:

- The panel is fixed to the breadboard at **one point only** — the **centre** tenon, whose pin hole(s) are **round**.
- Every **other** tenon's pin hole is a **slot elongated along the movement axis** (the panel's width = the breadboard's length). The slot grows longer the farther the tenon sits from the centreline, because that tenon travels farther as the panel swells and shrinks.
- The **pins stay round** and are fixed in the breadboard. The elongated clearance is a **void cut in the panel** tongue/tenon, so there is a visible gap on the movement sides of each off-centre pin.
- Typically only the centre ~1/3 of the joint is glued; the rest is a dry, sliding fit.

**When to use:** Wide solid-wood tabletops, drop-leaf tops, cabinet/passage doors — any wide panel that needs a flat, end-grain-hiding cap while remaining free to move seasonally.

**When NOT to use:** Narrow boards (no real movement problem — a plain tenon suffices) and engineered panels like plywood or MDF (which barely move).

**Strength:** High locating strength, deliberately low restraint across the width. The joint is engineered to *allow* movement, not resist it.

## Variants

| Variant | Description |
|---------|-------------|
| `through` | Pins pass fully through the panel thickness — visible on the top **and** bottom faces. Traditional / exposed joinery. |
| `blind` | Pins enter from the **bottom** face and stop short of the **top** — invisible from above. Fine furniture show surfaces. The panel clearance void is extruded to the same depth, so it never breaks the top surface. |

## Canonical Orientation

Everything is axis-aligned and parametric. This template owns **axis-aligned** breadboards only — non-axis-aligned cases escalate to a human (see the anchoring-complexity boundary).

| Model axis | Role |
|------------|------|
| **X** | Panel length / breadboard thickness. Tenons extrude **+X** into the breadboard. |
| **Y** | Panel width / breadboard length / **wood-movement axis** / slot long axis. |
| **Z** | Panel thickness / breadboard height / **pin axis** (pins run through in Z). |

The N tenons are spaced evenly along Y. Each tenon's **wider** cross-section dimension (`bbd_tw`) lies along Y — the breadboard's fibre direction — so the mating mortises run **with** the breadboard grain rather than across it. That fibre direction is read from `sp.grain_vector(breadboard)` rather than hardcoded; if it is not Y the template raises (the panel is on an unexpected axis → escalate).

## Parameters

| Parameter | Expression | Unit | Description |
|-----------|------------|------|-------------|
| `bbd_bb_t` | `"1.5 in"` | `"in"` | Breadboard thickness along the panel length (X) |
| `bbd_bb_h` | `"0.75 in"` | `"in"` | Breadboard height (Z) — normally == panel thickness |
| `bbd_tongue_d` | `"0.375 in"` | `"in"` | Continuous tongue depth into the breadboard (X) |
| `bbd_tongue_t` | `"0.25 in"` | `"in"` | Continuous tongue thickness (Z), centred in panel thickness |
| `bbd_td` | `"1.25 in"` | `"in"` | Deep-tenon depth into the breadboard (X), > tongue depth |
| `bbd_tw` | `"2 in"` | `"in"` | Deep-tenon **width** along the breadboard grain (Y) — the WIDE dim |
| `bbd_tt` | `"0.25 in"` | `"in"` | Deep-tenon thickness (Z); usually == tongue thickness |
| `bbd_n` | `"3"` | `""` | Number of deep tenons (odd ⇒ a true centre tenon) |
| `bbd_ppt` | `"1"` | `""` | Pins per tenon: 0 (glued), 1 (centred), 2 (straddling the width) |
| `bbd_pin_dia` | `"0.3125 in"` | `"in"` | Pin diameter (round in the breadboard) |
| `bbd_pin_sp` | `"1.25 in"` | `"in"` | Centre-to-centre spacing of the 2-pin pair (Y) |
| `bbd_pin_rem` | `"0.1875 in"` | `"in"` | Blind-pin: material left below the TOP face |
| `bbd_pin_in` | `"0.5 in"` | `"in"` | Pin inset from the breadboard outer face, into tenon depth (X) |
| `bbd_slot_clr` | `"0.0625 in"` | `"in"` | Slot half-elongation gained per tenon-step from the centreline |
| `bbd_slot_min` | `"0.0625 in"` | `"in"` | Baseline slot over-length for the near-centre tenons |

The registry prefix is `bbd_`.

## Build Workflow

The breadboard follows the standard combine-based joinery pattern, with the tongue/tenons belonging to the **panel** and the pins fixed in the **breadboard**:

1. **Continuous shallow tongue** across the full panel width — sketch on the panel end-face YZ plane, extrude +X by `bbd_tongue_d`, **JOIN** to the panel. This is the always-present stub running the full width between the deeper tenons.
2. **N deep tenons** evenly spaced along Y — each `bbd_tw` wide (along the breadboard grain) × `bbd_tt` thick, extruded +X by `bbd_td`, **JOIN**ed to the panel. Spacing is derived from the count: pitch = panel_width / `bbd_n`, with tenon *i* centred at `y0 + (i + 0.5) * pitch` (half-pitch inset keeps the outer tenons off the panel edges).
3. **Groove + mortises in the breadboard** — rebuild standalone tool bodies with the *same* geometry as the tongue + tenons (the JOINed originals can't be reused without consuming panel material), **CUT** the breadboard (keepTool), then delete the tools. The result is the exact negative of the panel's tongue + tenons (a press fit).
4. **Round pins**, one per pin position, sketched on the panel bottom (min-Z) face and extruded +Z. Fixed in the breadboard via the **CUT**. `through` = full panel thickness; `blind` = `panel_t − bbd_pin_rem` (stops short of the top).
5. **Clearance voids in the panel** — per the movement rules below.

### Pin Count Per Tenon

| `bbd_ppt` | Meaning |
|-----------|---------|
| 0 | Unpinned — glued stub only. No pins or holes are built. |
| 1 | One pin, centred on the tenon. |
| 2 | A pair straddling the tenon **width** along Y at `bbd_pin_sp` apart — resists racking. **Not** in-line along the tenon depth. |

### Wood-Movement Rule (critical)

The panel moves along **Y** (its width = the breadboard's length). Therefore:

- **Centre tenon** (only when `bbd_n` is odd, so a true centre exists): pin hole is **round**, equal to the pin diameter. This is the single fixed point — it pins the panel to the breadboard and everything else moves relative to it.
- **Every other tenon**: pin hole is a **slot elongated along Y**. The slot's long dimension is `bbd_pin_dia + bbd_slot_min + step * bbd_slot_clr * 2`, where `step` is the tenon's distance from the centreline measured in tenon pitches — so the slot grows the farther the tenon is from centre. The short dimension stays `bbd_pin_dia`.

Because the pin is round and fixed in the breadboard and the **clearance void lives in the panel**, there is a visible gap on the Y (movement) sides of every off-centre pin. The slot is built with `sp.sketch_slot_model` (a stadium: two arcs + two lines), long axis on Y.

### Blind-from-Bottom Pins

For `blind`, the pin is sketched on the panel bottom face and extruded **upward** (+Z) only `panel_t − bbd_pin_rem`, so it stops short of the top — invisible from above. The matching panel clearance void is extruded to the **same** depth from the same bottom face, so a blind hole likewise never breaks the top surface.

## Replication Strategy

- **Tenon count is the driver.** Pitch and per-tenon Y centres are derived from `bbd_n` and the panel width, so changing the count re-spaces every tenon, mortise, pin, and slot.
- **Two breadboards per top.** Call `build()` once per panel end. For the opposite end, pass the other end face (e.g. `("x", +1)` then `("x", -1)` with the appropriate `end_x_expr`), or mirror the whole panel assembly.
- **The slots are not a uniform pattern.** Each off-centre slot has a *different* length (growing with distance from centre), so they cannot be a single rectangular pattern — the template emits them individually. The round centre hole is likewise special-cased.
- **Pins are built per position**, not patterned, because each carries its own CUT history (round vs slotted clearance differs per tenon).

## Example

```python
from woodworking.templates import breadboard as bbd

# Define parameters
bbd.define_params(params, prefix="bbd",
    tenon_w="2 in", n_tenons="3", pins_per_tenon="1")

# Cap the +X end of a tabletop, blind pins (invisible from the top)
bbd.build(
    comp=top_comp,
    panel=top_body,
    breadboard=bb_body,
    panel_end_face=("x", +1),       # which panel end the BB caps
    panel_w_expr="top_w",           # panel width (Y span, movement axis)
    panel_t_expr="top_t",           # panel thickness (Z)
    end_x_expr="top_len",           # panel end-face X position (shoulder)
    y0_expr="0 in",                 # panel min-Y edge
    z0_expr="0 in",                 # panel bottom (min-Z) face
    n_tenons="bbd_n",
    pins_per_tenon="bbd_ppt",
    pin_mode="blind",
    name="BBE", ev=ev)
```

## Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| Panel splits in dry weather | All pin holes round (panel glued/pinned solid) | Only the centre hole is round; slot every other hole along Y |
| Mortises run across the breadboard grain | Tenon wide dim laid on the wrong axis | Lay `bbd_tw` along the breadboard fibre (Y) — the template reads `sp.grain_vector(breadboard)` and raises if it is not Y |
| Slot pointing across the movement axis | Slot long axis on X instead of Y | Movement is along Y; `long_model_axis="y"` |
| Slots all the same length | Fixed over-length instead of a gradient | Length grows with distance from the centreline (`step * bbd_slot_clr`) |
| Blind pin hole shows through the top | Clearance void extruded full thickness | Extrude the void to `panel_t − bbd_pin_rem`, matching the pin |
| Two-pin pair racks the joint anyway | Pins placed in-line along the tenon depth (X) | Straddle the tenon **width** (Y) so the pair resists rotation |
| No true centre fix | Even `bbd_n` (no centre tenon) | Use an odd count for a real round-pinned centre, or accept the nearest-to-centre tenons get the smallest slots |
| `ANCHOR REJECTED` on a non-root panel | Clipped/proud panel corner picked by the anchor | Pass `panel_occ`; anchor to a clean rectangular face, or build axis-aligned + bake a Move (see anchored-rect deterministic fallback) |
