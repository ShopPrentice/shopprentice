# Full-Blind (Secret-Mitred) Dovetail

## Overview

A **full-blind dovetail** is a through dovetail buried behind a 45° mitered lip on
**both** boards' outer faces. From the outside the corner shows only a clean miter line —
no tails, no pins, no end grain. The dovetail is entirely internal to the wood (hidden
from both faces), so the corner reads as a seamless miter while keeping the mechanical
lock of a dovetail.

Also called: **secret-mitred dovetail**, **double-blind** / **double-lap dovetail**.

**When to use:** The finest casework corners — jewelry boxes, humidors, plinths,
presentation cases — anywhere a corner must look like an unbroken miter but must not rely
on a weak long-grain miter glue line. It is the most labor-intensive dovetail; for utility
work use a [through](dovetail.md) or [half-blind](dovetail.md) dovetail instead.

**Strength:** Very high (a true dovetail lock), far stronger than the plain
[miter](miter-joint.md) it imitates.

**Relationship to the other dovetails:**
- [Through](dovetail.md): tails visible on both faces.
- Half-blind: tails hidden on **one** face (drawer fronts).
- **Full-blind: hidden on _both_ faces** — only the miter shows.

## Geometry — the inner-slab / outer-lip decomposition

Each board is split, conceptually, into two layers at its joining end:

```
   outer face                          outer face
   ┌───────────── lip ──────────────┐  (mitered, solid, thickness = lip)
   │  45° miter at corner            │
   ├─────────────────────────────────┤  ← recess line (depth = lip)
   │  inner slab (thickness t − lip) │  carries a THROUGH dovetail
   └─────────────────────────────────┘
   inner face
```

- The **outer lip** (thickness `lip`) is kept solid and mitered at 45° to the other
  board's lip. This is the only thing visible from outside.
- The **inner slab** (thickness `t − lip`) carries a normal through dovetail with the
  other board's inner slab.

Because the dovetail lives only in the inner slab, both recesses fall out automatically:
- the tail's **wide face** sits `lip` inside its own board's outer face;
- the tail **tips** stop `lip` short of the mating board's outer face.

The two lips meet on the plane `x = y` at the corner (the visible miter); the dovetail is
sealed behind them.

### Axis convention (one corner)

The outer corner arris runs along **+Z** at `(x_out, y_out)`; the box interior is toward
**+X / +Y**.

| Board | Role | Thickness axis | Runs along | Outer face |
|-------|------|----------------|------------|------------|
| `board_a` | tails | Y | +X | y = y_out |
| `board_b` | pins/sockets | X | +Y | x = x_out |

Tails repeat along **Z** (the joint height); penetration is along **X**.

## Parameters

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `fbd_angle` | `"10 deg"` | deg | Dovetail angle (7-9° hardwood, 10-14° softwood) |
| `fbd_tail_w` | `"0.5 in"` | in | Tail width at the wide (recessed-outer) face |
| `fbd_tail_count` | `"3"` | "" | Number of tails |
| `fbd_lip` | `"board_thick / 3"` | in | **Mitered outer-lip thickness = the recess depth** |

### Derived

| Parameter | Expression | Description |
|-----------|------------|-------------|
| `fbd_socket` | `board_thick - fbd_lip` | inner-slab depth = tail penetration |
| `fbd_pitch` | `joint_h / fbd_tail_count` | tail center-to-center |
| `fbd_pin_w` | `fbd_pitch - fbd_tail_w` | inner pin width |
| `fbd_narrow_w` | `fbd_tail_w - 2 * fbd_socket * tan(fbd_angle)` | tail width at the narrow (inner) end |
| `fbd_half_pin` | `fbd_pin_w / 2` | half-pin at the edges |

## Proportions & defaults

Inherits the dovetail proportion rules (angle, count, tail width). The one joint-specific
parameter is the **lip**:

**`fbd_lip`** — the mitered outer-lip thickness (the recess depth):
- Typical: **1/4 to 1/3 of board thickness**. For 3/4" stock, 1/4" is a good default —
  thick enough not to chip when the miter is trimmed, thin enough that the buried dovetail
  still has `t − lip` of socket depth to grip.
- Minimum ~3/16": thinner lips blow out.
- Maximum < 1/2 thickness: beyond that the inner slab is too thin to hold a meaningful
  dovetail (`fbd_socket` too small).

Validate `fbd_pin_w > 0` (tails fit) and `fbd_narrow_w > 0` (tails don't over-taper) — the
template raises a clear `ValueError` if either fails.

## Template

```python
from woodworking.templates import full_blind_dovetail as fbd

fbd.define_params(params, prefix="fbd",
    angle="10 deg", tail_w="0.5 in", tail_count="3",
    joint_h_expr="board_h", thick_expr="board_thick",
    lip="board_thick / 3")

res = fbd.corner(comp,
    thick_expr="board_thick", joint_h_expr="board_h",
    len_a_expr="6 in", len_b_expr="6 in",
    prefix="fbd", name="FBD", ev=ctx.ev)
board_a, board_b = res["board_a"], res["board_b"]
```

**`corner()` is a generator.** Unlike `dovetail.corner` / `half_blind_dovetail.corner`
(which add tails to two boards you already built), the full-blind joint must control the
inner-slab / outer-lip split of *both* boards, so `corner()` **builds both boards and the
joint** at one corner and returns them. Place the corner with `x_out_expr` / `y_out_expr`
(default origin) and `z0_expr`; keep coordinates ≥ 0 (positive space).

### What the template does

1. Four boxes — each board's inner slab + outer lip.
2. Through dovetail between the inner slabs: trapezoid → JOIN tails onto slab A →
   feature-pattern along Z → CUT sockets into slab B.
3. 45° miter both outer lips at the corner (parametric triangular CUT tools).
4. JOIN each lip back onto its slab → two finished boards.

## Validation

A correct full-blind dovetail should show:
- **0 interferences** between the two boards.
- **1 connected cluster** (the boards meet over the dovetail + miter faces — a large
  planar contact area).
- From the outside (either face): only a 45° miter line, no dovetail.
- Exploded or in section: the tails/sockets behind the lips.

Verified end-to-end and across parameter changes (thickness, height, tail count) at 0
interference / 1 cluster.

## Pitfalls

- **Lip must recompute parametrically.** The 45° miter tools are right-isoceles triangles
  sized by `fbd_lip`; they MUST be fully dimensioned, or a later change to `board_thick`
  (and therefore `lip`) leaves the lips un-mitered and the boards interfere. (Caught in
  development: an undimensioned miter triangle produced a ~4 cm³ overlap after resizing.)
- **`lip` between 0 and thickness.** `lip ≤ 0` or `lip ≥ thick` is rejected — there must
  be both a lip and an inner slab.
- **Don't expect a visible dovetail.** This joint is *supposed* to look like a plain
  miter from every outside face; confirm it with an exploded/section view, not an external
  render.
- **Positive coordinate space.** Like all `sketch_rect_model` geometry, position dims take
  absolute distance and reflect negatives; keep the corner at `x_out, y_out ≥ 0`.

## See also

- [dovetail.md](dovetail.md) — through and half-blind variants.
- [miter-joint.md](miter-joint.md) — the plain miter this joint hides behind.
- Template: `woodworking/templates/full_blind_dovetail.py`.
