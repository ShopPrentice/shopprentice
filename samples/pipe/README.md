# Pipe

**Source:** [AutodeskFusion360/Pipe](https://github.com/AutodeskFusion360/Pipe)
**License:** MIT
**Author:** Autodesk Inc.

## What It Demonstrates

- Path creation from edges/sketch curves (`features.createPath()`)
- Construction plane at a point along a path (`setByDistanceOnPath()`)
- Sketch circle profile on construction plane
- **Sweep feature** (`sweepFeatures`) — profile swept along a path
- **Shell feature** (`shellFeatures`) — hollowing the swept solid

## Parameters

| Parameter | Description |
|-----------|-------------|
| Path edge | User-selected edge or sketch curve to sweep along |
| Diameter | Pipe outer diameter |
| Thickness | Wall thickness (shell) |

## Key Patterns for `/woodworking`

- **Sweep**: Creating curved rails, bent laminations, decorative trim along a path
- **Shell**: Hollowing any solid — planters, boxes, troughs
- **Construction plane on path**: Placing sketches at arbitrary positions along curves
