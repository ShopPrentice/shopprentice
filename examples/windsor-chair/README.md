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

Each leg is positioned from its own seat corner: `leg_to_edge` along the near side edge, then `leg_to_edge` perpendicular inward. All four legs are built **independently** by `build_leg` (its `front_y`/`side_x` args select the corner) rather than mirrored — see Build Status below for why. Stretchers are built with the `turned_stretcher` template from the leg axes (`_leg_axis` through each leg's end circles): the two side stretchers connect front-to-back legs at `str_z` height, the cross stretcher connects the side stretchers. Wedges are added per joint. Positions derive from shared parameters so geometry follows parameter changes.

## Wedge Notes

- Leg-to-seat wedges pass `grain_dir=(0, 1, 0)` because the seat is nearly square (18" x 15") — auto-detection is ambiguous
- Stretcher wedges use auto-detected grain via principal axes of inertia — works correctly for splayed legs and angled stretchers
- FL and BL legs are wedged independently (not mirrored from FL) to ensure correct slot orientation on each side of the angled mirror plane

## Build Status (2026-07-04)

The example was committed **unvalidated** (`3273fc7 WIP: fan-out anchor drafts …`)
and did not build. It now **builds start-to-finish** and is substantially closer to
green, but `validate_design` does **not** yet pass. Fixed so far:

- **Line-770 anchoring over-constraint** (`VCS_SKETCH_SOLVING_FAILED`). The
  side-edge mirror-plane sketch drew a construction line between the seat's
  front-left (0,0) and back-left corners, then projected the whole seat outline —
  whose left edge is the *same* line — and pinned the drawn line's endpoints onto
  the fixed projected duplicate (one endpoint on the origin), over-constraining the
  projected-geometry solve. Now the projected left edge is reused directly for the
  path (no drawn duplicate, no coincidence).
- **Mirror-recompute corruption.** Legs and the right stretcher were mirrored, then
  the trim phase split/combined them — Fusion regenerated the mirrors and scrambled
  body identities (`Leg_FL → "Leg_FR (1) (1)"`), making the per-leg seat mortise and
  wedge cuts miss. Now all four legs and both side stretchers are built
  **independently** (`build_leg` takes `front_y`/`side_x` to anchor to any corner),
  so body references stay stable through the trim.
- **Interference 18 → 0.** Added spindle→seat and spindle→crest **socket cuts**
  (spindles were full cylinders interpenetrating both). The crest+spindles+seat are
  now one connected cluster.

### Remaining defects (punch-list — NOT yet green)

1. **Connectivity: 8 clusters, need 1.** `check_connectivity` counts only **planar**
   face contact. The leg→seat and stretcher→leg joints are **turned/round** (conical
   shoulders, cylindrical tenons) → zero planar contact → read as disconnected though
   physically joined. Fix requires **redesigning those joints to have flat mating
   faces** (flat shoulder at the seat underside; blind flat-bottomed leg mortises for
   stretcher tenons) — a joinery/aesthetic decision.
2. **featureImpact: zero-impact `tenon_wedge` cuts.** Every wedge slot/mortise
   combine removes nothing — a **pre-existing bug in the shared `tenon_wedge`
   template**, plus the 4 leg-foot chamfers modify no faces (the foot's full-circle
   edge has no start/end vertices, so the z<0.5 vertex filter selects nothing usable).
3. **deps: sketch traceability.** ~19 non-root sketches (from `build_leg` profiles and
   the shared `turned_stretcher` / `tenon_wedge` templates) aren't anchored to
   projected parent geometry — same class as line 770 but systemic across shared
   templates. Also `model.json`'s leg entries (`Leg_FL` …) need updating: the trim
   renames them (`Leg_FL (1)` …), so the `Leg_* → Seat` deps rows report "body not
   found".
