# Spur Gear

**Source:** [AutodeskFusion360/SpurGear](https://github.com/AutodeskFusion360/SpurGear)
**License:** MIT
**Author:** Autodesk Inc.

## What It Demonstrates

- Involute curve calculation and spline creation (`sketchCurves.sketchFittedSplines`)
- Circular pattern to replicate a single tooth around the gear
- Construction planes for positioning geometry
- Sketch geometric constraints
- Command input UI with `ValueInput` for parametric controls

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| Diametral Pitch | 7.62 cm | Gear pitch |
| Pressure Angle | 20 deg | Tooth flank angle |
| Number of Teeth | 24 | Tooth count |
| Gear Thickness | 2.0 cm | Extrusion depth |

## Key Patterns for `/woodworking`

- **Circular pattern**: Build one feature, replicate around an axis — useful for spindles, dowels, or decorative elements
- **Spline curves**: For organic shapes or non-rectangular profiles
- **Parametric command inputs**: Shows how Fusion 360 add-ins accept user parameters
