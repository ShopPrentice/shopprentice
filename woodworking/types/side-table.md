# Side Table

Small accent table — end tables, nightstands, accent tables, lamp tables. Typically 20–26" tall, smaller footprint than dining tables. Nightstands often have a drawer or small cabinet.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Top | Yes | Small flat surface |
| Legs | Yes | 4 supports |
| Aprons/Rails | Yes | Connect legs below top |
| Drawer | Optional | Single drawer below top (nightstand) |
| Shelf | Optional | Lower shelf between stretchers |
| Stretchers | Optional | Lower braces |

### Component relationships

```
Same frame construction as dining table.
If drawer: front apron has opening CUT, drawer slides inside frame.
If shelf: shelf sits on stretchers or in dados on legs.
```

## Openings & Cavities

| Opening | In which board | Created by |
|---------|---------------|------------|
| Drawer opening | Front apron | Drawer front CUT or apron split |

**If a drawer exists, the front apron must have an opening.**

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Apron to leg | Blind M&T | `mortise_tenon` |
| Top to apron | Buttons or dominos | inline or `domino` |
| Drawer box | Half-blind front, through back | `dovetailed_drawer` |

## Hardware Checklist

| Hardware | When needed | Template/catalog |
|----------|------------|-----------------|
| Drawer pull | When drawer exists | Knob or pull hardware |

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| table_l | 18–26 in | 22 in |
| table_w | 14–20 in | 16 in |
| table_h | 22–26 in | 24 in |
| top_thick | 0.75 in | 0.75 in |
| leg_size | 1.25–1.75 in | 1.5 in |

Refer to `types/dining-table.md` for detailed build order and common mistakes.
