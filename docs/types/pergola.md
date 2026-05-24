# Pergola

Outdoor overhead structure — pergolas, arbors, trellises, gazebos. Open-roof structure providing partial shade. Large scale (10'+ spans), heavy timber construction.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Posts | Yes | Vertical supports (4+ columns) |
| Beams | Yes | Main horizontal members spanning between posts |
| Rafters | Yes | Secondary horizontal members across beams |
| Purlins | Optional | Tertiary members across rafters (for shade density) |
| Braces | Optional | Diagonal supports between posts and beams |
| Deck | Optional | Floor platform below the pergola |

### Component relationships

```
Posts set in ground or on footings
Beams span between post pairs (long direction)
Rafters span across beams (short direction)
Purlins span across rafters (long direction, smaller)
Braces connect post top to beam (45° diagonal)
```

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Beam to post | Notch/lap, through-tenon, or bolted | inline or `mortise_tenon` |
| Rafter to beam | Notch or birdsmouth | inline |
| Purlin to rafter | Notch or resting | inline |
| Brace to post/beam | Half-lap or M&T | inline |
| Post to footing | Post base bracket | — (hardware) |

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| span_l | 10–20 ft | 12 ft |
| span_w | 8–14 ft | 10 ft |
| post_h | 8–10 ft | 9 ft |
| post_size | 4×4 – 6×6 in | 5.5 in (6×6 nominal) |
| beam_size | 2×8 – 2×12 in | 1.5 × 9.25 in (2×10 nominal) |
| rafter_count | 6–12 | 8 |
