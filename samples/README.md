# Sample Scripts

Reference scripts from open-source Fusion 360 projects. These demonstrate API patterns that the `/woodworking` skill can draw on for advanced features like sweep, revolve, shell, threads, chamfer, fillet, circular pattern, finger joints, text engraving, and material assignment.

These are **read-only references** — they are not meant to be run directly. Consult them when you need to see how a particular Fusion 360 API feature is used.

## Samples

| Sample | Source | License | Key API Patterns |
|--------|--------|---------|------------------|
| [spur-gear](spur-gear/) | [AutodeskFusion360/SpurGear](https://github.com/AutodeskFusion360/SpurGear) | MIT | Involute splines, circular pattern, construction planes, sketch constraints |
| [bolt](bolt/) | [AutodeskFusion360/Bolt](https://github.com/AutodeskFusion360/Bolt) | MIT | Extrude, chamfer, fillet, revolve cut, thread features, join operation |
| [bottle](bottle/) | [AutodeskFusion360/Bottle](https://github.com/AutodeskFusion360/Bottle) | MIT | Revolve from profile, shell, fillet, thread, scale, material/appearance assignment |
| [pipe](pipe/) | [AutodeskFusion360/Pipe](https://github.com/AutodeskFusion360/Pipe) | MIT | Sweep along path, shell, construction plane on path |
| [box-maker](box-maker/) | [lukecyca/BoxMaker](https://github.com/lukecyca/BoxMaker) | MIT | Finger/box joints, multi-plane sketching, move features, parametric notches |
| [surface-text](surface-text/) | [AutodeskFusion360/SurfaceText_python](https://github.com/AutodeskFusion360/SurfaceText_python) | MIT | Text engraving, surface evaluators, coordinate transforms, timeline grouping |
| [voronoi](voronoi/) | [hanskellner/Fusion360Voronoi](https://github.com/hanskellner/Fusion360Voronoi) | MIT | SVG import into sketch, profile loop analysis, decorative cut patterns |
| [helix-generator](helix-generator/) | [tapnair/HelixGenerator](https://github.com/tapnair/HelixGenerator) | MIT | Fitted spline from math, helix curves, sweep paths for spiral features |
| [duplicate-component](duplicate-component/) | [AutodeskFusion360/DuplicateComponent](https://github.com/AutodeskFusion360/DuplicateComponent) | MIT | Component duplication, bounding box, Matrix3D transforms |

## GPL-3.0 Projects (Not Included)

The following projects have useful patterns but use GPL-3.0. Including their code would force this repo to GPL, so they are listed as external references only:

- [nraynaud/Dovetails](https://github.com/nraynaud/Dovetails) — Dovetail joint generation
- [AcademyOfAdventurers/EasyFusionAPI](https://github.com/AcademyOfAdventurers/EasyFusionAPI) — Simplified wrapper for Fusion 360 API

## Attribution

All sample scripts are copyright their respective authors and redistributed under their original MIT licenses. See each sample's README for specific attribution.
