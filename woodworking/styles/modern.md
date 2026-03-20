# Modern Style

Clean, minimal furniture with tapered profiles, hidden joinery, and light proportions. The default style when no specific style is identified.

## Overview

Modern furniture emphasizes function, clean geometry, and visual lightness. Joints are hidden unless their visibility is intentional (e.g., through dovetails on a premium box). Edges are crisp or lightly eased. Hardware is minimal and functional — concealed hinges, simple pulls. **Proportions should be lighter and thinner than you think** — err on the side of slim stock and tapered legs.

## Design Principles

1. **Less structure is better.** Don't add aprons, stretchers, or rails unless the piece needs them. Modern pieces derive stability from geometry (tapered legs, angled connections) rather than additional members. A coffee table might be just a top + 4 tapered legs + dominos.

2. **Proportions follow ergonomics.** A desk is 18" deep because that's laptop depth. A bench seat is 12" deep because you sit upright. A chair seat is 16" deep because you lean back. Derive dimensions from how the body uses the furniture, not from aesthetics.

3. **Comfort features are functional requirements.** Rounded seat edges on a bench, contoured seat on a chair, tapered legs for visual lightness — these aren't decorative choices, they're what separates a finished piece from a construction project.

4. **Tapered legs, not square.** The defining visual of modern wood furniture. Legs taper from top (full size at the joint) to bottom (narrower at the floor). Even a subtle 5° taper transforms the look.

## Joinery Preferences

| Joint location | Preferred | Alternative | Avoid |
|---------------|-----------|-------------|-------|
| Visible case corners | Through dovetails | Finger/box joints | Exposed screws, nails |
| Hidden structural (rails, stretchers) | Dominos | Blind M&T | Pocket screws on visible faces |
| Drawer front | Half-blind dovetails | Dominos | Butt joint |
| Drawer back | Through dovetails | Box joints | Butt joint |
| Panel in frame | Floating in groove | Tongue & groove | Glued-in panel |
| Shelf to case | Dados or shelf pins | Dominos | Cleats only |
| Top to legs (no apron) | Dominos directly into underside | Buttons + apron | — |
| Top attachment (with apron) | Buttons or dominos | Figure-8 fasteners | Glue (restricts movement) |
| Leg to rail/apron | Domino grid (2 per joint) | Blind M&T | Dowels alone |
| Bed rail to post | Bed rail fastener or bed bolt | — | Permanent M&T (can't disassemble) |

### Leg-Frame Joinery Pattern (Tables, Benches, Chairs, Desks)

For any piece with legs + aprons/rails, use `domino.grid()` at each apron-to-leg interface:
- **2 dominos per joint** evenly spaced along the apron height
- **Interface plane** at the leg-apron boundary (YZ for long aprons, XZ for short)
- **Stretchers** get a single domino per end (lower in the leg than aprons)
- **Cross-component**: aprons and legs are in separate components; domino CUTs happen in root via assembly proxies
- **Minimal designs** (no aprons): dominos go directly from leg top into the underside of the top board

This pattern applies to: coffee table, bench, chair, desk, side table, sofa frame, dining table.

## Edge Treatments

| Element | Treatment | Parameter |
|---------|-----------|-----------|
| Tabletops, lids | Light ease (1/16" roundover or chamfer) | `ch_d = 0.0625 in` |
| Bench/chair seats | Rounded edges for comfort | `fl_r = 0.125 in` |
| Case edges | Square or very light chamfer | `ch_d = 0.0625 in` |
| Leg bottoms | Small chamfer to prevent splintering | `ch_d = 0.0625 in` |
| Drawer fronts | Square edges, tight reveal gap | — |

## Transitions

| Transition | Treatment |
|-----------|-----------|
| Case to base/feet | Flush kick (kick boards flush with case sides) or recessed kick (inset 1") |
| Lid/top to case | Flush or minimal overhang (0–0.25") |
| Drawer to case | Flush front with 1/16" reveal gap |
| Back panel | Rabbeted into sides, flush with back edge |
| Shelf to side | Dado (hidden) or shelf pin holes |

## Proportions

| Ratio | Value | Note |
|-------|-------|------|
| Kick/foot height | 3–4" or 1:8 of total height | Recessed, not decorative |
| Top/lid overhang | 0–0.25" | Minimal or flush |
| Board thickness | 0.75" (4/4 stock) | Standard for case boards |
| Leg size | 1.25–1.75" | Lighter than traditional (2"+) |
| Drawer gap/reveal | 1/16" (0.0625") | Tight, consistent |
| Coffee table L:W ratio | 2:1 to 3.5:1 | Elongated, not square |
| Headboard:footboard height | ~3:1 | Tall headboard, low footboard |

## Hardware

| Hardware | Specification | Aesthetic |
|---------|--------------|-----------|
| Hinges (doors) | Euro concealed (35mm cup) | Completely hidden |
| Hinges (lids) | Brass or stainless butt hinge | Minimal profile |
| Pulls | Simple cylindrical bar or rectangular | Brushed metal or wood |
| Catches | Magnetic or push-to-open | No visible catch hardware |
| Shelf supports | 5mm shelf pins | Standard pattern, hidden holes |
| Bed rail | Bed rail fastener or bed bolt | Hidden, detachable |

## Materials

| Element | Species | Finish |
|---------|---------|--------|
| Primary | Walnut, white oak, maple, ash | Oil, lacquer, or water-based poly |
| Secondary | Baltic birch plywood, poplar | Match or complement primary |
| Panels | Plywood | Veneer-matched to primary |

## What NOT to Do

- **Don't over-build.** If a piece works without aprons, don't add them. If legs can be 1.5", don't make them 2.5".
- Don't add decorative moldings, corbels, or ornamental details
- Don't use turned legs or spindles (use tapered or square)
- Don't leave end grain exposed at visible joints without purpose
- Don't use contrasting wood for structural joints (unless intentionally decorative)
- Don't leave seat edges sharp/square on seating furniture — always round or ease
- Don't assume every table needs 4 aprons — many modern designs skip them
- Don't make flat seats on chairs — contour or deepen for comfort
