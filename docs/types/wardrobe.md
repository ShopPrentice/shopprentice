# Wardrobe

Tall freestanding closet — wardrobes, armoires, clothes cabinets. Distinguished from cabinets by height (6'+) and having a hanging rod. Essentially a tall cabinet with specialized interior.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Case | Yes | Top, bottom, sides — tall enclosure |
| Doors | Yes | Full-height doors (1 or 2) |
| Hanging rod | Yes | Bar for hanging clothes |
| Shelves | Optional | Fixed or adjustable shelves (top, side compartment) |
| Drawers | Optional | Lower drawer section |
| Divider | Optional | Vertical divider separating hanging from shelf area |
| Base/Kick | Yes | Supports the tall case |
| Back | Yes | Plywood back for rigidity (critical for tall pieces) |
| Crown molding | Optional | Decorative top trim |

### Component relationships

```
Same as cabinet but taller.
Hanging rod spans between sides at shoulder height (~60" from floor)
Back panel critical for racking resistance
Base must be sturdy (heavy piece)
```

Refer to `types/cabinet.md` for detailed connections, hardware, build order, and common mistakes. Key differences:

- **Height**: 72–84" (requires wall anchoring for safety)
- **Hanging rod**: required, at 60–66" from floor
- **Back panel**: CRITICAL for structural rigidity (tall narrow case racks without it)
- **Doors**: typically full-height, heavy — need 3 hinges each

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| case_w | 36–48 in | 42 in |
| case_d | 20–26 in | 24 in |
| case_h | 72–84 in | 78 in |
| rod_h | 60–66 in (from floor) | 63 in |
| door_count | 1–2 | 2 |
