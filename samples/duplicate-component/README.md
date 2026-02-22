# DuplicateComponent

**Source:** [AutodeskFusion360/DuplicateComponent](https://github.com/AutodeskFusion360/DuplicateComponent)
**License:** MIT
**Author:** Autodesk Inc.

## What It Demonstrates

- Component duplication via `occurrences.addExistingComponent()`
- Bounding box access (`occurrence.boundingBox`, `minPoint`, `maxPoint`)
- `Matrix3D` transform with `Vector3D.create()` and `scaleBy()` for positional offset
- Command framework with selection, integer spinner, and boolean inputs

## Parameters

| Parameter | Description |
|-----------|-------------|
| Component | Source component to duplicate |
| Count | Number of copies |
| Spacing | Gap between copies (or auto from bounding box) |

## Key Patterns for `/woodworking`

- **Component duplication**: Placing multiple identical sub-assemblies (e.g., drawer units, shelf supports)
- **Matrix transforms**: Positioning bodies/components at computed offsets
- **Bounding box**: Measuring component extents for automatic spacing calculations
