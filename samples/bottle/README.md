# Bottle

**Source:** [AutodeskFusion360/Bottle](https://github.com/AutodeskFusion360/Bottle)
**License:** MIT
**Author:** Autodesk Inc.

## What It Demonstrates

- Revolve feature from a multi-segment profile (lines + arcs)
- Shell feature to hollow a solid body
- Fillet on revolved edges (edge selection by geometry matching)
- Thread features with pitch matching via `allDesignations()`
- Scale feature to resize a body uniformly
- Material and appearance assignment from libraries
- Sketch constraints (horizontal, perpendicular) and dimensioned arcs

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| Height | 21 cm | Overall bottle height |
| Top Width | 2.8 cm | Neck opening radius |
| Top Height | 1.9 cm | Neck height |
| Body Top Width | 0.4 cm | Shoulder step width |
| Bottom Width | 3.2 cm | Base radius |
| Thickness | 0.3 cm | Wall thickness (shell) |
| Scale | 2.0 | Uniform scale factor |
| Thread Pitch | 0.4 cm | Neck thread pitch |

## Key Patterns for `/woodworking`

- **Revolve**: Creating turned/lathe shapes — table legs, spindles, bowls
- **Shell**: Hollowing a solid — boxes, drawers, planters with thin walls
- **Material/appearance**: Assigning wood materials and finishes programmatically
- **Scale**: Resizing completed geometry — useful for parametric scaling of decorative elements
- **Edge selection by geometry**: Iterating edges and matching by radius/type to target specific features
