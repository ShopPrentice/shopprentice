# Type Guide Template

Copy this file to create a new furniture type guide. Fill in every section — the agent reads this during planning to know what components, openings, connections, and hardware the piece requires.

Type files answer: **"What must this piece of furniture have to function correctly?"**

They are style-independent. A chest needs a lid mechanism whether it's Shaker or Mid-century. The style file determines *how* the lid looks and what hardware to use.

---

## Components

List every component the piece must have, with its role. Mark required vs optional.

| Component | Required | Role |
|-----------|----------|------|
| _Example: Case_ | Yes | _Main enclosure — front, back, left, right boards_ |
| _Example: Lid_ | Yes | _Hinged top panel for access_ |
| _Example: Drawer_ | Optional | _Lower storage drawer_ |

### Component relationships

Describe how components connect spatially. This prevents floating parts.

```
Case sits on Feet
Bottom divides Case interior from Drawer space
Lid hinges to Case back edge
Drawer slides inside Case below Bottom
Back panel sits in rabbet in Case sides
```

## Openings & Cavities

**Every opening must be explicitly planned.** If something slides or swings out, the case board in front of it needs a CUT.

| Opening | In which board | Created by |
|---------|---------------|------------|
| _Example: Drawer opening_ | _Front case board_ | _CUT: drawer front body or explicit rectangle_ |
| _Example: Door opening_ | _Face frame or case front_ | _CUT: door body_ |

**Rule:** If a drawer or door exists, plan its opening. No exceptions.

## Connections

How each component attaches to its neighbors. Every connection needs a mechanical joint — no floating parts.

| Connection | Joint type | Template |
|-----------|-----------|----------|
| _Example: Case corners_ | _Through dovetails_ | `dovetail` |
| _Example: Bottom to case_ | _Dado_ | inline |
| _Example: Lid to case_ | _Butt hinge_ | `butt_hinge` |
| _Example: Feet to case_ | _Glue + screws or dominos_ | `domino` |

## Hardware Checklist

What hardware this type typically needs. The style file determines which specific hardware.

| Hardware | When needed | Template/catalog |
|----------|------------|-----------------|
| _Example: Lid hinge_ | _When lid opens_ | `butt_hinge` or Euro hinge |
| _Example: Lid stay_ | _When lid should hold open_ | lid_stay |
| _Example: Drawer pull_ | _When drawer exists_ | `pull` or knob |

## Build Order

Recommended sequence for building components. Earlier components provide faces and reference geometry for later ones.

```
1. Case boards (structure)
2. Bottom / shelves (internal divisions)
3. Feet / base (support)
4. Drawer (fits inside case)
5. Lid / doors (covers openings)
6. Back panel (closes the back)
7. Cross-component joinery (dovetails, dados)
8. Hardware (hinges, pulls)
9. Details (edge treatments, chamfers)
```

## Validation Rules

Expected body counts and checks after each phase.

| Phase | Expected bodies | Check |
|-------|----------------|-------|
| _Example: After case_ | _4 (front, back, left, right)_ | _Bounding box matches case_w × case_d × case_h_ |
| _Example: After drawer_ | _5 drawer bodies_ | _Drawer fits inside opening with gap_ |
| _Example: Final_ | _N total_ | _Zero interferences_ |

## Common Mistakes

Pitfalls specific to this furniture type that the agent should watch for.

- _Example: Forgetting the drawer opening in the case front_
- _Example: Lid without hinges (floating)_
- _Example: Bottom board not mechanically connected to case_

## Parameter Suggestions

Typical dimensions for this furniture type. The agent uses these as defaults when the user doesn't specify.

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| _Example: case_w_ | _24–48 in_ | _36 in_ |
| _Example: board_thick_ | _0.5–1 in_ | _0.75 in_ |
