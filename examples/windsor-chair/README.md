# Windsor Chair

A parametric Windsor chair with splayed/raked legs, turned stretchers, curved spindle back, scooped seat, and through-tenon wedges.

| | |
|---|---|
| ![Iso](iso.png) | ![Front](front.png) |
| ![Right](right.png) | ![Transparent](iso-transparent.png) |

## Features

- **Shaped seat** with trapezoidal outline (front/back arcs, angled sides), dual comfort scoops, and filleted edges
- **4 splayed/raked legs** with turned profiles (tenon, shoulder, taper) via revolve, positioned from seat corner geometry
- **H-stretcher system** — side stretchers connect front-to-back legs, cross stretcher connects side stretchers, all body-referenced via `intersectWithSketchPlane`
- **7 curved back spindles** arranged on a comfort arc, raked backward
- **Swept crest rail** following the spindle top arc
- **Tenon extensions** on all leg and stretcher ends
- **Through-tenon wedges** at all 10 joints (4 leg-to-seat, 4 stretcher-to-leg, 2 cross-stretcher-to-side-stretcher) using `tenon_wedge` template with `end_face=` for compound angles
- **Multi-species appearance** — white oak body, rosewood wedges, grain-aligned via principal axes of inertia

## Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `seat_w` | 18 in | Seat width (front) |
| `seat_d` | 15 in | Seat depth |
| `seat_t` | 1.75 in | Seat thickness |
| `seat_h` | 17.5 in | Floor to seat top |
| `leg_splay` | 10 deg | Leg outward splay angle |
| `leg_rake` | 10 deg | Leg fore-aft rake angle |
| `leg_to_edge` | 2.2 in | Leg center distance from seat corner |
| `back_rake` | 12 deg | Back spindle rake angle |
| `n_spindles` | 7 | Number of back spindles |
| `scoop_depth` | 0.5 in | Seat scoop depth |
| `tw_sw` | 0.08 in | Wedge slot width |
| `tw_dr` | 1/2 | Wedge depth ratio |

## Parametric Behavior

Legs are positioned from the seat's front-left corner: `leg_to_edge` along the side edge, then `leg_to_edge` perpendicular inward. Back legs are mirrored across the seat side edge midplane, then both sides wedged independently before mirroring across the X midplane. Stretchers use body intersection — side stretchers intersect leg cross-sections at `str_z` height, cross stretcher intersects side stretcher cross-sections. All connections use sketch constraints (coincident, collinear) so geometry follows when parameters change.

## Wedge Notes

- Leg-to-seat wedges pass `grain_dir=(0, 1, 0)` because the seat is nearly square (18" x 15") — auto-detection is ambiguous
- Stretcher wedges use auto-detected grain via principal axes of inertia — works correctly for splayed legs and angled stretchers
- FL and BL legs are wedged independently (not mirrored from FL) to ensure correct slot orientation on each side of the angled mirror plane
