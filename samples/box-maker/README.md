# BoxMaker

**Source:** [lukecyca/BoxMaker](https://github.com/lukecyca/BoxMaker)
**License:** MIT
**Author:** Luke Cyca

## What It Demonstrates

- Parametric box with 6 interlocking panels (front, back, left, right, top, bottom)
- **Finger/box joint** notch generation via sketch lines
- Sketch creation on multiple construction planes (XY, YZ, XZ)
- Extrude with `NewBodyFeatureOperation`
- **Move features** with `Matrix3D` transforms for body positioning
- Component creation within root component

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| Width | 10 cm | Box width (X) |
| Height | 10 cm | Box height (Z) |
| Depth | 10 cm | Box depth (Y) |
| Wall Thickness | 0.3 cm | Panel/wall thickness |
| Finger Width | 1 cm | Width of each finger joint notch |

## Key Patterns for `/woodworking`

- **Finger/box joints**: Interlocking notch geometry — common in CNC-cut furniture and shop jigs
- **Multi-plane sketching**: Building panels on XY, YZ, XZ planes then positioning them
- **Move features**: Translating bodies into final assembly positions
- **Parametric notch generation**: Computing notch count and size from overall dimensions
