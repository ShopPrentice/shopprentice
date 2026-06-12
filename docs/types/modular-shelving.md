# Modular Shelving

A **shelving system** assembled from repeated parts, whose defining trait is
**modularity**: shelves can be added, removed, or repositioned — and bays extended —
without rebuilding the piece. This is a *system* type, not a single object: the design
work is choosing how the shelves are supported and made adjustable, and making sure the
load path and stability hold for whatever configuration the user picks.

Distinguished from a **shelf** (one wall board on brackets/cleat) by being a multi-support
system, and from a **bookshelf** (a freestanding case with solid sides and shelves fixed
in dados) by having adjustable/removable shelves on a repeating support grid.

Covers: modular wall shelving, post-and-peg systems, shelf-pin (32mm) uprights,
standards-and-brackets, cube/box modular shelving, cable/rod suspension shelving, lean
(ladder) shelving.

---

## The core design decision: how shelves are supported

Pick ONE support method — it determines the vertical-support type, the joinery, the
adjustability, and the load path. Everything else follows from it. This is the first
thing to settle with the user; don't default to the post-and-peg version just because
the example uses it.

| Support method | Vertical support | How the shelf is held | Adjustable? | Notes |
|----------------|------------------|-----------------------|-------------|-------|
| **Post-and-peg** | Posts (to floor) | Shelf slides over post via through-mortise; rests on pegs in a ladder of holes | Yes — move pegs | Strong, knock-down, sculptural. The example build. |
| **Shelf pins (32mm)** | Uprights / gables | Pins in line-bored holes; shelf rests on pins | Yes — move pins | The standard cabinet/casework method; least visible. |
| **Standards & brackets** | Slotted standards (usually wall-mounted) | Brackets clip into slots; shelf rests on brackets | Yes — move brackets | Fully wall-borne; retail/utility look; cheap to reconfigure. |
| **Cleats / ledgers** | Uprights or the wall | Shelf rests on strips screwed at height | Semi (re-screw) | Simplest; not freely adjustable. |
| **Dado / housing** | Gables | Shelf captured in a groove | No (fixed) | Strongest fixed shelf — but that's really a *bookshelf*, not modular. |
| **Cube / box modules** | Each box is self-supporting | Boxes stack or bolt together | Rearrange boxes | Modularity is at the box level, not the shelf level. |
| **Suspension (cable / rod)** | Tension rods or cables, floor-to-ceiling or wall-hung | Shelf clamped between collars on the rods | Yes — slide collars | Mid-century / industrial; needs top + bottom anchoring. |
| **Lean / ladder** | Leaning A-frame against the wall | Shelves fixed to the frame, set back per rung | No | Freestanding, no wall fasteners; shallow shelves. |

## Functional requirements (must hold for ANY variant)

These are what make a shelving *system* work, independent of method. Audit each one
during planning.

1. **Continuous load path.** Every shelf's load must reach the floor or the wall through
   an unbroken bearing chain (shelf → support element → vertical member → floor/wall).
   Name the path for each shelf; a shelf that only "touches" a support with no bearing
   surface is floating.
2. **Stability / tip resistance.** A tall, shallow unit *will* tip forward when loaded
   unless it is restrained: anchor wall-standing units to the wall (angle bracket,
   French cleat, or rail), tension floor-to-ceiling units top and bottom, or give a
   freestanding unit a deep/weighted base. This is a requirement, not an option.
3. **Racking resistance.** A frame of verticals + horizontals is a parallelogram unless
   something triangulates it — a fixed shelf, a back panel, a diagonal, or rigid
   wall/floor anchoring. Without it the unit shears sideways.
4. **Shelf span vs. deflection.** Distance between supports is limited by shelf thickness
   and material (sag). Long shelves need more supports, thicker stock, a front edge
   stiffener, or a back cleat. Derive shelf length from `(supports−1)·pitch + 2·overhang`
   rather than picking an arbitrary length.
5. **A repeating, consistent support interface.** The thing that makes it *modular* is
   that the support points repeat at a regular pitch so any shelf fits any bay and parts
   interchange. Make the **count a parameter and the spacing derived** (or vice-versa) so
   the grid always fills the support evenly.
6. **A common datum.** Shelves register to a shared reference — typically the wall (back)
   plane and the support grid — so a shelf seats correctly in every position.
7. **Adjustable ⇒ bearing joints, not glue.** If shelves move, they *rest on* their
   supports (mechanical seating). Glue/dado a shelf only where it is intentionally the
   fixed, racking-resisting member.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Vertical supports | Yes | Posts, standards, gables, or rods. Repeated on a grid; carry load to floor or wall. |
| Shelves | Yes | Horizontal surfaces. Often several lengths/widths (staggered or uniform). |
| Shelf-support elements | Yes | Pegs, pins, brackets, cleats, or dados — the rest-on / capture interface (per the chosen method). |
| Anchoring | Yes (function) | Wall anchor, floor base, or ceiling tension — provides tip + racking resistance. |
| Back / spacer / brace | Optional | Holds supports parallel and at a uniform wall offset; can supply racking resistance. |

### Component relationships

```
Vertical supports stand on the floor OR hang from a wall rail/cleat, on a regular grid
The support interface (holes / slots / dados / cleats) repeats up each vertical member
Shelves engage a contiguous subset of supports → that subset sets each shelf's length
Each shelf bears on its support elements (pegs/pins/brackets) OR is captured (dado)
Anchoring ties the system to wall/floor/ceiling for stability
```

## Connections

| Connection | Typical joint | Template |
|-----------|---------------|----------|
| Shelf ↔ support element | Rests on (bearing): peg / pin / bracket | inline / `dowel` |
| Shelf ↔ vertical (slide-over variant) | Snug through-mortise sized to the post | inline |
| Shelf ↔ vertical (fixed variant) | Dado / housing | inline |
| Support element ↔ vertical | Dowel in hole, pin in hole, bracket in slot | `dowel` / inline |
| Vertical ↔ wall/floor/ceiling | Angle bracket, French cleat, rail, base, tension foot | hardware |

Grain/load: vertical members run long-grain (compression to floor, or hung in tension);
shelf load is transferred in bearing, so the critical surfaces are the *contact* faces,
not glue lines (except for the deliberately-fixed bracing member).

## Hardware Checklist

| Hardware | When needed | Template/catalog |
|----------|------------|-----------------|
| Pegs / shelf pins / brackets | Always (the support method) | `dowel` or shop-made; catalog pins/brackets |
| Wall / floor / ceiling anchor | Always (stability) | angle, French cleat, rail, tension foot |
| Back or diagonal brace | When nothing else resists racking | inline |

## Build Order (generalized)

```
1. Vertical support — build ONE, pattern/replicate to the full count
2. Support interface — create the repeating holes/slots/dados/cleats as a PATTERN
3. Shelves — build one per distinct size; place on the grid
4. Support elements — pegs/pins/brackets (one, then patterned to the engaged supports)
5. Anchoring — wall/floor/ceiling attachment
6. Details + appearance
```

Reuse is the point: build one of each repeated part and let Fusion patterns make the
rest (count parametric). For repeated *voids* (peg holes, mortises), pattern plain tool
BODIES and bulk-cut — feature-patterning an extrude-cut fails; pattern the part before
cutting its holes. See `feedback_pattern_cut_toolbody`.

## Validation Rules

| Phase | Check |
|-------|-------|
| After verticals | Each carries the full, evenly-spaced support interface |
| After shelves | Shelves engage the intended supports and register to the back datum |
| After supports | Support elements seat with zero interference |
| Final | 0 interferences; the load-bearing members form **1 connected cluster** |

Note on connectivity: bearing contact must be **planar** to register. Slide-over shelves
get a snug mortise (post-sized) so walls contact the post; round pegs/rods make
line/curved contact that the planar check won't count, so carry the structure with the
planar joint and exclude the round parts from the connectivity check. See
`feedback_round_dowel_connectivity`.

## Common Mistakes (design-level)

- **No wall/ceiling anchor on a tall unit** → tips forward under load. Anchoring is a
  functional requirement, not a finishing touch.
- **No racking resistance** → the verticals-and-shelves frame shears into a
  parallelogram. Add a back, a diagonal, a fixed shelf, or rigid anchoring.
- **Shelf span too long for the stock** → visible sag. Add supports, thicken, or stiffen
  the front edge.
- **Gluing/fixing shelves in an "adjustable" system** → defeats the modularity the type
  exists for.
- **Inconsistent support pitch** → shelves don't interchange between bays; the system
  stops being modular. Keep the support grid uniform (parametric count, derived spacing).
- **Picking the support method by habit** → choose post-and-peg vs. shelf-pin vs.
  standards-and-brackets vs. suspension from the user's intent (look, wall vs. freestanding,
  knock-down, budget), not from this doc's example.

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| support_pitch (grid) | 24–36 in | 32 in |
| n_supports | 2–5 | 3 |
| vertical_len/height | 48–96 in | 72 in |
| shelf_thick | 0.75–1 in | 0.875 in |
| shelf_depth | 7–14 in | 10 in |
| max clear span (3/4" hardwood) | ≤ ~32 in before sag | — |
| support increment (height steps) | 1–2 in | depends on method |

## Worked Example (one realization)

`examples/modular-wall-shelf/` builds the **post-and-peg** variant (Fine Woodworking,
Jan/Feb 2025): 4 posts to the floor on a 36" grid, shelves that slide over the posts on
snug through-mortises and rest on dowel pegs set in a ladder of holes. It is *one* way to
satisfy this type — the shelf-pin, standards-and-brackets, suspension, and cube-module
variants are equally valid and use different supports, joinery, and anchoring.
