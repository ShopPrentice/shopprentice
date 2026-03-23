# Nakashima / Live Edge Style

Furniture that celebrates the natural form of wood — live edges, organic shapes, visible grain character, and decorative bowties spanning natural cracks. Named after George Nakashima, the master woodworker who pioneered the "free edge" aesthetic, treating each slab as a unique natural object rather than raw material to be squared.

## Overview

Nakashima-style furniture uses thick wood slabs with their natural bark edges preserved. The wood's imperfections — cracks, knots, sapwood variations — are features, not defects. Bowtie (butterfly) keys span cracks as both structural reinforcement and decorative elements, typically in a contrasting wood species. The design philosophy: work WITH the wood's natural form, don't impose geometry on it.

**Key visual signatures:**
- Live (natural/bark) edges on tabletops, headboards, shelves, benches
- Thick slabs (1.5–3" typical) showing dramatic grain figure
- Bowtie/butterfly key inlays across cracks in contrasting wood
- Simple, understated bases that let the slab be the focal point
- Minimal ornamentation — the wood IS the ornamentation
- Often asymmetric — slab edges are never parallel

## Current Capabilities (Tested)

What we can build today in ShopPrentice:

| Feature | Status | Template |
|---------|--------|----------|
| Rectangular slab headboard/top | Working | `sketch_rect_model` |
| Bowtie inlay pockets | Working | `woodworking/templates/bowtie.py` |
| Bowtie row along crack line | Working | `bowtie.row()` |
| Domino slab-to-post attachment | Working | `woodworking/templates/domino.py` |
| Post chamfer alignment with slab | Working | Chamfer alignment rule in core skill |

## Planned Capabilities (Not Yet Built)

| Feature | What's needed | Impact |
|---------|--------------|--------|
| **Photo-to-STEP live edge profile** | User uploads slab photo → trace edge contour → generate STEP body with organic edge | Unlocks true Nakashima-style free-form edges instead of rectangular slabs |
| **Bed rail fastener hardware** | STEP files for hook-plate + strike-plate → installation templates | Enables disassemblable beds (currently using permanent dominos) |
| **Slab edge filleting** | Apply variable-radius fillets to simulate bark edge undulation on rectangular slabs | Approximation of live edge without photo input |

## Joinery Preferences

| Joint location | Preferred | Alternative | Avoid |
|---------------|-----------|-------------|-------|
| Crack stabilization | **Bowties** (butterfly keys) | Epoxy fill | Ignoring cracks |
| Slab to base/posts | Dominos or sliding dovetails | Through-bolts with washers | Visible screws from top |
| Base frame corners | Blind M&T or dominos | Half-lap | Pocket screws |
| Stretcher to leg | Dominos or through-tenon | Blind M&T | Butt joint |
| Slab to wall (headboard) | French cleat or dominos to posts | Through-bolts | Screws through face |

## Edge Treatments

| Element | Treatment | Notes |
|---------|-----------|-------|
| Slab top/bottom edges | **Live edge preserved** (natural bark line) | Currently modeled as straight edge — see Planned Capabilities |
| Slab ends (cross-grain) | Light chamfer or sanded round | Never sharp — 1/8" chamfer minimum |
| Post tops | Chamfer | Slab stops below chamfer line |
| Base/leg edges | Light chamfer or eased | Subtle — don't compete with slab |

## Transitions

| Transition | Treatment |
|-----------|-----------|
| Slab to posts | Slab notched around posts, or slab sits behind/on top of posts. Dominos connect through the interface. |
| Slab to base (table) | Slab overhangs base by 2–6" on all sides. Base is visually secondary. |
| Slab to wall | French cleat on back — invisible from front |
| Crack to bowtie | Bowties centered on crack, perpendicular to crack direction (= perpendicular to grain). Evenly spaced, one near each end + every 5–8". |

## Proportions

| Element | Guideline | Note |
|---------|-----------|------|
| Slab thickness | 1.5–3 in | Thicker = more dramatic. 2" is the sweet spot. |
| Bowtie length | 2–4 in | Proportional to slab thickness |
| Bowtie depth | 1/3 to 1/2 of slab thickness | Deep enough to grip, shallow enough to leave material |
| Bowtie end width | ~50% of bowtie length | 1.5" ends on a 3" bowtie |
| Bowtie waist | ~33% of end width | 0.5" waist on 1.5" ends |
| Bowtie spacing | 5–8 in along crack | One near each end of the crack |
| Base height (table) | 16–18 in for coffee, 28–30 in for dining | Standard ergonomics |
| Slab overhang (table) | 2–6 in beyond base | More = more dramatic floating effect |

## Bowtie Orientation Rule

**Bowties are ALWAYS perpendicular to the crack direction.**

Cracks in wood run parallel to the grain (fiber direction). The bowtie's long axis must cross the crack at 90° to provide mechanical resistance to the crack opening further.

| Slab fiber direction | Crack runs in | Bowtie long_axis |
|---------------------|--------------|-----------------|
| X (horizontal slab) | X | **z** (vertical bowties) |
| Y (long table slab) | Y | **x** (horizontal bowties) |
| Z (vertical panel) | Z | **x** or **y** |

Use the `bowtie.row()` template with `crack_axis` matching the fiber direction and `long_axis` perpendicular to it.

## Materials

| Element | Species | Finish |
|---------|---------|--------|
| Primary slab | Black walnut, claro walnut, or figured hardwood (maple burl, redwood) | Oil finish (Rubio Monocoat, Osmo) — NO film finishes |
| Bowties | Contrasting species — walnut bowties in maple slab, or wenge in walnut | Same oil as slab |
| Base/legs | Same species as slab, or complementary (maple base under walnut slab) | Same finish |
| Epoxy (optional) | Clear or tinted for crack filling | Matte finish to match oil |

## What NOT to Do

- **Don't square off the live edges** — the whole point is the natural profile
- **Don't use film finishes (polyurethane, lacquer)** — they mask the wood's tactile quality. Oil finishes enhance grain while keeping the natural feel.
- **Don't make the base visually dominant** — the slab is the star. Base should be simple, clean, and recede.
- **Don't orient bowties parallel to the crack** — they must cross it perpendicular to provide structural value
- **Don't use undersized bowties** — they look like afterthoughts. Size them proportionally to the slab thickness.
- **Don't skip bowties on visible cracks** — every crack needs stabilization. Unstabilized cracks will open over time with humidity changes.
- **Don't use rectangular edges and call it "live edge"** — if we can't model the organic edge yet (see Planned Capabilities), call it a "slab headboard" not "live edge." Be honest about the approximation.

## Example Builds

| Piece | File | Key features |
|-------|------|-------------|
| Twin bed with slab headboard + bowties | `examples/bed-frame/twin_live_edge.py` | 2" slab, 3 vertical bowties, notched around posts, chamfer-aligned |
