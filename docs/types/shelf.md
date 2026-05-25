# Shelf

Wall-mounted shelving — floating shelves, wall shelves, ledge shelves, bracket shelves. Distinguished from bookshelves by being wall-mounted (not freestanding) and typically single boards or small assemblies.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Shelf board | Yes | Horizontal surface |
| Brackets | Style-dependent | Support from below (visible or hidden) |
| Cleat | Style-dependent | Wall-mount strip (floating shelf) |
| Back board | Optional | Ledge shelf: vertical board behind shelf |

### Component relationships

```
Floating shelf: cleat mounts to wall, shelf slides over cleat
Bracket shelf: brackets mount to wall, shelf sits on brackets
Ledge shelf: shelf + back board + optional lip, mounts directly
```

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Shelf to bracket | Resting or screwed from below | inline |
| Shelf to cleat (floating) | Shelf hollowed to slide over cleat | inline |
| Shelf to back board (ledge) | Rabbet or butt + screws | inline |

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| shelf_l | 24–48 in | 36 in |
| shelf_d | 6–12 in | 8 in |
| shelf_thick | 0.75–1.5 in | 1.5 in |
| bracket_depth | = shelf_d | 8 in |
