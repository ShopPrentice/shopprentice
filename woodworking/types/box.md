# Box

Small enclosed containers — pencil boxes, jewelry boxes, keepsake boxes, trinket boxes. Typically under 12" in any dimension. Distinguished from chests by size and the absence of feet, drawers, or hinged hardware (often uses sliding lids or simple lift-off lids).

## Components

| Component | Required | Role |
|-----------|----------|------|
| Case | Yes | Front, Back, Left, Right boards forming the enclosure |
| Bottom | Yes | Panel sitting in grooves in case boards |
| Lid | Yes | Top panel — sliding, lift-off, or hinged |

### Component relationships

```
Case boards join at corners (dovetails or box joints)
Bottom panel sits in grooves in all 4 case boards
Lid sits on top or slides in grooves
  - Sliding lid: grooves in front, back, left — open on right
  - Lift-off lid: rabbeted edges sit inside case opening
  - Hinged lid: butt hinges at back edge
```

## Openings & Cavities

| Opening | In which board | Created by |
|---------|---------------|------------|
| Lid slot (sliding) | Front, back, left side boards | Lid body CUTs groove into each board |
| Bottom groove | All 4 case boards | Bottom panel body CUTs groove via combine |

**Sliding lid note:** One side board (typically right) is shorter — `open_height = box_height - lid_thick`. The lid slides out from this open side.

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Case corners (4) | Through dovetails or box/finger joints | `dovetail` or `finger_joint` |
| Bottom to case | Panel in grooves (rabbeted edges) | inline (panel CUT into boards) |
| Lid (sliding) | Grooves in 3 sides, open on 4th | inline (lid CUT into boards) |
| Lid (hinged) | Butt hinges at back | `butt_hinge` |

## Hardware Checklist

| Hardware | When needed | Template/catalog |
|----------|------------|-----------------|
| Hinges | When lid is hinged (not sliding) | `butt_hinge` |
| Lock/clasp | For keepsake or jewelry boxes | `chest_lock` |

## Build Order

```
1. Case boards (front, back, left, right)
2. Bottom grooves (CUT before dovetails for implicit stopped grooves)
3. Lid grooves (CUT before dovetails)
4. Corner joinery (dovetails or box joints at all 4 corners)
5. Bottom panel (rabbeted edges, CUT grooves into case boards)
6. Lid panel (rabbeted edges for sliding, or flat for hinged)
7. Hardware (hinges if applicable)
8. Details (chamfers, fillets)
```

## Validation Rules

| Phase | Expected bodies | Check |
|-------|----------------|-------|
| After case | 4 (front, back, left, right) | Box dimensions match |
| After panels | 6 (+ bottom + lid) | Panels fit in grooves |
| Final | 6 | Zero interferences |

## Common Mistakes

- Forgetting to make one side shorter for sliding lid opening
- Cutting lid grooves after dovetails (produces through grooves visible at corners)
- Bottom panel grooves visible on end grain faces (need stopped grooves on front/back)
- Lid and bottom panel overlap (derive positions from shared parameters)

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| box_length | 6–12 in | 9 in |
| box_width | 3–6 in | 3 in |
| box_height | 2–4 in | 2.5 in |
| board_thick | 0.25–0.5 in | 0.25 in |
| bottom_thick | 0.1875–0.3125 in | 0.25 in |
| lid_thick | 0.1875–0.3125 in | 0.25 in |
| dt_tail_count | 2–4 | 3 |
