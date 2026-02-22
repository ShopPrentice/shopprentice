# SurfaceText

**Source:** [AutodeskFusion360/SurfaceText_python](https://github.com/AutodeskFusion360/SurfaceText_python)
**License:** MIT
**Author:** Autodesk Inc.

## What It Demonstrates

- Surface evaluator API (`geometry.evaluator`, `getPointAtParameter()`, `getNormalsAtPoints()`)
- Construction plane creation from points and vectors
- Sketch text creation (`sketchTexts.add()`)
- Extrude with Cut/Join on curved surfaces
- `modelToSketchSpace()` coordinate transforms
- Timeline grouping for multi-feature operations

## Parameters

| Parameter | Description |
|-----------|-------------|
| Face | Target cylindrical surface |
| Text | String to emboss/engrave |
| Height | Text character height |
| Depth | Extrude depth (positive = emboss, negative = engrave) |

## Key Patterns for `/woodworking`

- **Text engraving**: Adding labels, maker marks, or decorative text to furniture surfaces
- **Surface evaluation**: Working with curved surfaces — useful for applying features to turned legs or curved panels
- **Coordinate transforms**: Converting between model space and sketch space for precise feature placement
