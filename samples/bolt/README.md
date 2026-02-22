# Bolt

**Source:** [AutodeskFusion360/Bolt](https://github.com/AutodeskFusion360/Bolt)
**License:** MIT
**Author:** Autodesk Inc.

## What It Demonstrates

- Hexagonal sketch geometry (computed vertices)
- Extrude with `NewBodyFeatureOperation` and `JoinFeatureOperation`
- Chamfer features on edges
- Fillet features with edge loop selection
- Revolve cut for hex head shaping
- Thread features using `threadDataQuery.recommendThreadData()`
- Component creation via `occurrences.addNewComponent()`

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| Head Diameter | 0.75 cm | Hex head across-corners |
| Body Diameter | 0.5 cm | Bolt shaft diameter |
| Head Height | 0.3125 cm | Height of hex head |
| Body Length | 2.0 cm | Shaft length |
| Cut Angle | 30 deg | Revolve cut angle for hex facets |
| Chamfer Distance | 0.03845 cm | Chamfer on shaft end |
| Fillet Radius | 0.02994 cm | Fillet at head-to-shaft transition |

## Key Patterns for `/woodworking`

- **Chamfer + Fillet**: Rounding edges and breaking sharp corners — common on furniture legs and tabletops
- **Revolve cut**: Shaping operations using revolution — useful for turned legs or decorative profiles
- **Thread features**: API for adding threaded holes or bolts to furniture hardware
- **Join operation**: Adding material to an existing body — same pattern used for tenons
