# Mirror Frame

Frame surrounding a mirror — wall mirrors, standing mirrors, looking glasses. Frame construction with a rabbet to hold the mirror glass and backing board.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Frame pieces | Yes | 4 boards forming the rectangle (mitered or jointed corners) |
| Mirror glass | Represented | Placeholder body for the glass (not modeled in detail) |
| Backing board | Optional | Thin panel holding mirror in place from behind |

### Component relationships

```
4 frame boards joined at corners (miter, bridle, or M&T)
Rabbet on inner back edge holds mirror glass + backing
Mirror glass sits in rabbet
Backing board holds glass in place
```

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Frame corners | Miter + spline, bridle, or M&T | `miter_joint` or `bridle_joint` |
| Mirror to frame | Sits in rabbet (held by backing) | inline rabbet |

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| mirror_w | 18–36 in | 24 in |
| mirror_h | 24–48 in | 36 in |
| frame_w | 2–4 in | 3 in |
| frame_thick | 0.75–1 in | 0.75 in |
| rabbet_depth | 0.375 in | 0.375 in |
