# HelixGenerator

**Source:** [tapnair/HelixGenerator](https://github.com/tapnair/HelixGenerator)
**License:** MIT
**Author:** Patrick Rainsberry (Autodesk)

## What It Demonstrates

- **Fitted spline** creation from computed points (`sketchFittedSplines.add()`)
- `ObjectCollection` of `Point3D` coordinates for spline input
- Mathematical helix calculation (parametric radius, pitch, resolution)
- Selection input with plane/planar face filters
- `ValueInput.createByReal()` and `addIntegerSpinnerCommandInput()`
- Construction plane visibility toggling

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| Plane | User-selected | Construction plane or planar face |
| Radius | 2 cm | Helix radius |
| Pitch | 1 cm | Vertical distance per revolution |
| Revolutions | 5 | Number of full turns |
| Resolution | 90 | Points per revolution |

## Key Patterns for `/woodworking`

- **Fitted splines**: Creating organic curves — decorative scrollwork, spiral staircase rails
- **Mathematical geometry**: Generating points from equations for complex curves
- **Sweep paths**: A helix spline can be used as a sweep path for barley-twist legs or spiral features
