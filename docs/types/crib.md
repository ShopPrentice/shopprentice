# Crib

Baby crib / toddler bed. Safety-critical — spindle spacing, rail heights, and hardware strength have regulatory requirements.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Head panel | Yes | Tall end with spindles or solid panel |
| Foot panel | Yes | Shorter end, may match head or be different |
| Side rails | Yes | Long rails with spindles connecting head to foot |
| Mattress support | Yes | Platform or slat system for mattress |
| Posts | Yes | 4 corner posts (integrated into head/foot panels) |

### Component relationships

```
Posts at 4 corners
Head/foot panels span between post pairs with spindles
Side rails connect head posts to foot posts with spindles
Mattress support sits inside the crib frame
```

## Safety Requirements (CRITICAL)

- **Spindle spacing: max 2-3/8" (6 cm)** — prevents head entrapment
- **Rail height: min 26" above mattress** in highest position
- **No decorative cutouts** that could trap limbs
- **Post tops: flush or less than 1/16" above rails** — no finials that catch clothing
- **Mattress fit: no more than 2 finger widths gap** between mattress and sides
- **Drop-side rails: BANNED** in the US since 2011

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Side rail to post | Bed bolt hardware (for disassembly) | `bed_rail` hardware |
| Spindles to rails | Blind holes (drilled, glued in) | inline |
| Mattress platform | Rests on ledger strips or in grooves | inline |

## Hardware Checklist

| Hardware | When needed | Template/catalog |
|----------|------------|-----------------|
| Bed bolts | For side rail connection | `bed_rail` hardware |
| Mattress height adjusters | Adjustable mattress platform | — |

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| interior_l | 52 in (standard) | 52 in |
| interior_w | 28 in (standard) | 28 in |
| rail_h | 30–36 in | 34 in |
| post_size | 2–3 in | 2.5 in |
| spindle_dia | 0.75–1 in | 0.75 in |
| spindle_spacing | 2–2.375 in (max) | 2.25 in |
