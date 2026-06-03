# Modular Shelving

A wall-mounted **shelving system** built from repeated parts: vertical posts (or
standards) that carry the load, plus a set of shelves held at adjustable heights by
pegs, pins, or brackets. Distinguished from a **shelf** (a single wall board on
brackets/cleat) by being a multi-post system, and from a **bookshelf** (a freestanding
case with solid side panels) by having open posts instead of sides and shelves that are
adjustable/removable rather than fixed in dados.

Covers: modular wall shelving, post-and-peg shelving, standards-and-brackets systems,
ladder/library-rail shelving, staggered display walls.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Posts / standards | Yes | Vertical members; carry load to floor (or hang from a wall rail). Repeated on a grid. |
| Shelves | Yes | Horizontal boards. Often several lengths/widths, staggered. |
| Pegs / pins / brackets | Yes | Set each shelf's height and transfer its load to the posts. |
| Wall anchors | Yes (function) | Tie the unit to the wall for tip resistance (steel angle, French cleat, rail). Often hidden. |
| Back/spacer | Optional | Holds posts off the wall a uniform distance. |

### Component relationships

```
Posts stand on the floor (or hang from a wall rail) on a regular X grid
Pegs insert into post holes at the chosen heights
Shelves slide over the posts (through-mortises) OR rest on pegs/brackets
Each shelf engages a contiguous subset of posts (2, 3, ...) — that sets its length
Wall anchors fix the posts to the wall (hidden behind/under shelves)
```

## Openings & Cavities

| Opening | In which board | Created by |
|---------|---------------|------------|
| Peg holes (height adjustment) | Posts | Tool-body cylinders, patterned, bulk CUT (NOT a feature-pattern of a cut — see Common Mistakes) |
| Through-mortises (shelf slides over post) | Shelves | Snug square tool sized to the post cross-section, patterned along the shelf, bulk CUT |

**Rule:** peg holes repeat in a 2-D grid (within-group spacing × group/row spacing) — make
both the count and spacing parameters so the ladder of holes always fills the post.

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Shelf to post (slides over) | **Snug through-mortise** sized to the post cross-section | inline (square tool, bulk CUT) |
| Shelf to peg | Rests on peg (shelf load → peg → post) | inline |
| Peg to post | Dowel in hole (snug or a hair undersize) | `dowel` / inline |
| Shelf to bracket (variant) | Rests on / screwed to bracket | inline |
| Post to wall | Steel angle, French cleat, or rail | hardware (often omitted as hidden) |

**Grain & load:** posts are long-grain vertical (load in compression to floor). Shelf load
goes shelf → peg (bearing) → post wall. The shelf-to-post connection is *mechanical
seating*, not glue — the system is meant to knock down.

## Hardware Checklist

| Hardware | When needed | Template/catalog |
|----------|------------|-----------------|
| Pegs / shelf pins | Always (height support) | `dowel` or shop-made dowels |
| Wall anchor (angle / cleat / rail) | Always (tip resistance) | — (often hidden, may be omitted from model) |
| Brackets | Standards-and-brackets variant | — |

## Build Order

```
1. Posts — build ONE post, pattern along X to the full count
2. Peg holes — one tool cylinder → nested patterns (within-group → groups → posts) → bulk CUT
3. Shelves — one board per distinct size; snug through-mortises patterned along each, bulk CUT
4. Pegs — one peg per shelf, patterned along the posts that shelf engages
5. Details — roundovers (post corners + shelf top edges), underbevels (shelf bottoms)
6. Appearance
```

Pattern reuse is the whole point of this type — build one of each repeated part and let
Fusion patterns do the rest.

## Validation Rules

| Phase | Expected bodies | Check |
|-------|----------------|-------|
| After posts | n_posts | Each post has the full peg-hole grid (face count) |
| After shelves | n_posts + n_shelves | Snug mortises give post↔shelf face contact (connectivity) |
| After pegs | + one peg per shelf-post intersection | Pegs seat with zero interference |
| Final | all | 0 interferences; posts + shelves = **1 connected cluster** |

## Common Mistakes

- **Feature-patterning an extrude-CUT for the peg holes** — fails with `NO_TARGET_BODY /
  PASTE_INT_EDGES` even with `AdjustPatternCompute`. Build the hole as a plain tool BODY,
  pattern the bodies, then one bulk CUT. Pattern the post *before* cutting its holes
  (cut-then-pattern replays the consumed combine). See `feedback_pattern_cut_toolbody`.
- **Loose (clearance) mortises break connectivity** — a mortise with a gap to the post
  makes no face contact, so shelves read as disconnected. Size the mortise to the post
  cross-section (snug) so the walls contact the post; the clearance is negligible visually.
- **Round pegs never satisfy planar connectivity** — a dowel in a round hole / under a
  flat shelf makes line/curved contact, not planar. Carry the structure with the snug
  mortise and **exclude pegs** from the connectivity check
  (`exclude_prefixes=["DM_","Peg"]`). Make pegs a hair undersize so they don't interfere.
- **Negative coordinates flip** — `sketch_rect_model` position dims take absolute distance
  and reflect negative coords to the +side; keep the whole unit in **positive X space**
  (e.g. set the leftmost post X = the largest shelf overhang so the left edge lands at 0).
- **Shelf overhang exceeding the spec** — outer mortise should sit within the allowed
  overhang of the shelf end; derive shelf length from `(#posts-1)*post_spacing + 2*overhang`.

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| post_size | 1.25–2 in sq | 1.5625 in |
| post_len | 60–96 in | 90 in |
| post_spacing | 24–36 in | 36 in |
| n_posts | 2–5 | 4 |
| shelf_thick | 0.75–1 in | 0.875 in |
| peg_dia | 0.375–0.75 in | 0.75 in |
| shelf widths | 7–12 in | 9 in |

## Worked Example

`examples/modular-wall-shelf/` — the Fine Woodworking (Jan/Feb 2025) Modular Shelf
System: 4 pegged posts on a 36" grid, 7 staggered shelves on snug through-mortises, 17
dowel pegs. Demonstrates every technique above. Built end-to-end from a single prompt.
