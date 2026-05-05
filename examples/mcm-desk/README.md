# Teak Desk

Parametric recreation of Teak Desk v21 — entasis legs, arched/scalloped aprons, straight round side stretchers, stepped slats with tenons, full joinery.

## Status
**Validation passed** — 25 bodies, 1 connected cluster, 0 interferences. Teak appearance applied with grain-aligned textures and 112 end-grain faces.

## Components

| Component | Bodies | Description |
|-----------|--------|-------------|
| top | 1 | 470×1080×17mm slab, 15mm bottom fillet + 3.75mm top fillet |
| legs | 4 | 15-point entasis spline revolve, 3° splay, foot fillet, through-mortises for aprons/slats/stretchers |
| aprons | 2 | Front + back rail with arched bottom + scalloped ends (two 15-pt splines per side), 3mm fillets on top + bottom edges, mortises for slat tenons |
| outer_slats | 2 | Cross-rails at ±leg_dist_y/2 — main body (3×5.4cm, X span 362mm between aprons) + tenons (12×28mm) extending past to leg outer face |
| inner_slats | 2 | Cross-rails at ±leg_dist_y/6 — main body (3×2.5cm) + tenons (12×20mm) extending 12mm past apron inner face |
| side_stretchers | 2 | Straight round bars r=13mm at splayed Y=±44.82, Z=250mm (v21-matching) |
| dovetail_blocks | 12 | 3×4 grid under top — simple rectangular blocks (flange+dovetail-tongue shape not yet implemented) |

## Parameters

### Envelope
| Parameter | Value |
|-----------|-------|
| `total_height` | 720mm |
| `top_thickness` × `top_width` × `top_length` | 17 × 470 × 1080mm |
| `leg_dist_x` × `leg_dist_y` | 380 × 850mm |
| `leg_length` | 700mm |
| `angle_y` (splay) | 3° |

### Apron
| Parameter | Value |
|-----------|-------|
| `stretcher_width × _height × _thickness` | 1050 × 75 × 18mm |
| `stretcher_to_top` | 10mm |
| `apron_edge_fillet` | 3mm |

### Slats
| Parameter | Value |
|-----------|-------|
| `slat_thickness` | 30mm (Y) |
| `slat_outer_h` / `slat_inner_h` | 54 / 25mm (Z) |
| `slat_tenon_y` | 12mm |
| `slat_outer_tenon_z` / `slat_inner_tenon_z` | 28 / 20mm |
| `slat_inner_tenon_extend` | 12mm |

### Side Stretchers
| Parameter | Value |
|-----------|-------|
| `side_stretcher_r` | 13mm |
| `side_stretcher_z` | 250mm |

### Dovetails
| Parameter | Value |
|-----------|-------|
| `dovetail_width` × `_bottom_width` × `_thickness` × `_length` | 30 × 25 × 15 × 80mm |
| `dovetail_quantity` | 3 per row |
| `dovetail_angle` | 74° (not yet used — blocks are rectangular) |

## Design Fidelity
- **Leg entasis**: 15 fit points (r=11mm foot, 16.8mm waist, 14mm top) — matches v21 spline exactly
- **Apron arch**: 15 fit points per half (center peak Z=643mm, shoulder Z=618mm @ Y=±433mm)
- **Apron scallop**: 15 fit points per end — curves from shoulder up to Y=±507mm at top
- **Side stretcher** Y parametrically shifts with splay: `-leg_dist_y/2 - (to_floor - leg_to_top - side_stretcher_z) * sin(angle_y)`
- **Slat tenons** reduced cross-section (12mm Y × 28mm Z outer, 20mm Z inner)

## Joinery (Phase 7 cross-component CUTs)
- Leg mortises: each leg CUT by aprons + outer slats + side stretchers (keep tools)
- Apron mortises: aprons CUT by outer + inner slats (keep tools) — rectangular holes for slat tenon passage
- Dovetail sockets: outer + inner slats CUT by their dovetail blocks

## Known deviations from v21 (next session TODO)
These were identified via direct inspection of v21 but not yet implemented:

1. **Housed dovetail apron→leg (task #15)**: The apron end tapers in Y at 8° (`stretcher_dovetail_angle`) for the last 18mm inside the leg. Leg has matching dovetail-shaped mortise with sloped walls + 3mm corner fillets. Currently apron-leg joint is just a rectangular mortise without the 8° taper.

2. **DT block flange+tongue shape (task #16)**:
   - Top flange: 3×8cm × 5mm Z flat rectangle flush with table underside
   - Dovetail tongue below: 3cm X × 2.2cm Y × 10mm Z with tilted parallelogram cross-section (sides leaning 16° = 90-`dovetail_angle`), rounded Y-end caps (r=10mm fillet cylinders)
   - Currently DT blocks are simple rectangular prisms (15mm thick × 30×80mm flat)

## Build Notes
- `addCenterPointRectangle` with center at (0,0,0) doesn't anchor — adding coincident to sk.originPoint crashes Fusion (degenerate). Use `addTwoPointRectangle` + diagonal construction line + `addMidPoint(origin, diag)` instead.
- Distance dimensions in Fusion can't take negative expressions (they become absolute). Solutions: offset the sketch plane so the origin sits where you need it, then use positive expressions.
- `rectangularPatternFeatures.createInput` defaults to patterning in BOTH directions. Must explicitly set `pat_inp.quantityTwo = VI("1")` and `distanceTwo = VI("0 cm")` to suppress direction-two pattern.
- Revolve profile axis line must NOT be `isConstruction=True` — a construction line isn't part of profile detection, profile stays open.
- User parameters must be declared in dependency order.
- `sp.make_comp()` returns an Occurrence, not a Component — use `.component` to access.
- Fusion trig in expressions: `sin(angle_y)` works when parameter has `deg` units; no unit conversion needed.
- When a stepped body has a tenon extending the X bbox, main body Z range must be ≥ tenon Z range — otherwise tenon sticks out above/below the slat.

## Ear Bodies (Fillet Edge Wrapping)
Thin 0.01mm shells on the long-edge fillets for smooth cylindrical texture wrapping:
- Created via Copy → SurfaceDeleteFace (keep only long-edge fillet faces) → Thicken 0.01mm outward
- Cylindrical projection with axis along Y (desk length) at bottom fillet center (x=±22, z=71.8)
- Uses rotated desk photo (`teak_desk_top_rot90.jpg`) so grain maps axially along desk length
- OffsetX=55cm hides axial seam past desk ends, OffsetY=11.75cm hides circumferential seam
- Box projection on the main desk body handles flat faces at 1:1 — no distortion

## Apron Face Matching
Box projection mirrors texture between +X/-X faces. Per-face appearance copies with half-period offset on +X faces ensure all 4 large apron side faces show the same grain region.

## Files
- `teak_desk.py` — parametric build script (~1970 lines, 8 phases)
- `README.md` — this file
- `assets/teak_desk_top.jpg` — desk top photo (2868×6528 = 47×108cm)
- `assets/teak_desk_top_rot90.jpg` — rotated 90° for cylindrical ear projection
- `assets/teak_e_top_tone.jpg` — color-graded teak e veneer for frame bodies
- `assets/teak_endgrain_dark.jpg` — darkened endgrain (75% brightness)
- `assets/teak_endgrain_top_tone.jpg` — color-graded endgrain (original brightness)
