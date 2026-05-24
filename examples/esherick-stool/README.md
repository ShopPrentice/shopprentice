# Wharton Esherick Three-Legged Stool (1958 style)

![Esherick Stool](iso-top-right.png)

## Description

Parametric approximation of a Wharton Esherick-inspired three-legged stool. Walnut seat built as a **three-section loft with three adjustable spline rails** and direction-tangent top/bottom blends (no scoop, no perimeter fillets — the loft provides the smooth rollover natively). Oak turned legs with hand-tuned taper profile, barrel-profile turned stretchers at staggered heights, and wedged through-tenons on all joints. Wedge slot axes run perpendicular to the seat grain (`grain_dir=(1, 0, 0)` passed to the `tenon_wedge` template) so wedge expansion is parallel to the seat fibers — resists splitting the mortise.

This model is a close representation of an organic, hand-sculpted design — not a precise reproduction. The workflow bridges the gap between parametric modeling and organic design intent: the agent builds an initial shape with hard-coded spline control points, the user drags fit points in the Fusion UI to refine, and the agent captures the edits via `get_timeline_state(index, include_sketches=True)` and bakes them back into the script's `_BOT_PLAN` / `_MID_PLAN` / `_TOP_PLAN` / rail control-point lists as the new defaults.

## Video

[![Esherick Stool Deep Dive](https://img.youtube.com/vi/upckBvHT-xY/maxresdefault.jpg)](https://www.youtube.com/watch?v=upckBvHT-xY)

[Watch on YouTube](https://youtu.be/upckBvHT-xY) — Deep dive on building this stool: lofted lens-profile seat, 3 adjustable rails, approximate → refine → capture loop with spline edits in Fusion, wedge grain orientation, walnut/oak finish.

Reference: [Rago Arts Lot 568](https://www.ragoarts.com/auctions/2023/01/modern-design/568) — Wharton Esherick, 1958, walnut and ash.

| | |
|---|---|
| ![Front](front.png) | ![Right](right.png) |
| ![Iso Left](iso-top-left.png) | ![Iso Right](iso-top-right.png) |

## Key Techniques Demonstrated

- **Lofted organic seat** — 3-section loft (bottom outline at 70 %, full-size mid, top outline at 70 %) through a closed-spline plan at each level, with three radial-plane rails passing through the three clipped-triangle corners. `setDirectionEndCondition(angle="0 deg", weight=3.0)` on top and bottom blends the flat plateau into the sides with zero slope at the edge, building curvature gradually — no fillet features needed. See `docs/organic-shapes.md` §Lofted Organic Bodies for the recipe, and `docs/loft.md` for the full feature reference.
- **Approximate → refine → capture** — agent seeds plan + rails, user drags fit points in Fusion UI, agent re-reads sketches and bakes updated coordinates into the hard-coded `_BOT_PLAN` / `_MID_PLAN` / `_TOP_PLAN` / `_RAIL_*_CTRLS` constants.
- **Edited-centroid-aware joinery** — downstream `tri_cx` / `tri_cy` / `leg_angles_rad` derive from the actual captured `_MID_PLAN` centroid + corner indices, not the symmetric nominal triangle. Legs land on the user-edited corners even when sculpting shifts the centroid off-center.
- **Revolved legs** — half-profile fitted spline on an XZ sketch with 12 control points, revolved 360° around a vertical construction axis, then positioned at each captured corner direction via an axis-angle rotation matrix.
- **Through-tenon trim on an organic surface** — SplitBody using the **entire lofted seat body** as the split tool (follows the curved underside), `sp.body_side()` to classify fragments, remove above-seat tips, rejoin interior pieces.
- **Wedged through-tenons with correct grain orientation** — `grain_dir=(1, 0, 0)` passed to `tenon_wedge.round_tenon` so the wedge slot axis is `face_normal × grain_dir = Z × X = Y`, i.e., perpendicular to the seat's X grain. Expansion direction is parallel to grain (safe compression along fibers).
- **APPEARANCE SPEC** comment block at the top of the script — after every `execute_script(clean=True)`, the agent auto-applies oak base + walnut on seat and wedges (with Seat grain X override) and hides construction geometry. See `docs/appearance.md` §Persisting Appearance Across Rebuilds.
- **Staggered stretchers** — three different heights (6.5", 8", 9.5") to avoid weakening legs at the same point; barrel profile via fitted spline in a sketch on a construction plane perpendicular to the stretcher axis.
- **Spatial query helpers** — `sp.body_side()`, `sp.face_side()`, `sp.classify_bodies()` for fragment classification after the split.
- **Component organization** — Seat, Legs, Stretchers with cross-component CUTs orchestrated from the root timeline.

## Build Order

1. Seat — 3-section lofted lens profile + 3 corner rails + tangent top/bottom blend (no scoop)
2. Legs — revolved fitted-spline profile, positioned + splayed at each captured corner
3. Wedge slots on leg tenons (`grain_dir=(1, 0, 0)` so slot axis crosses seat grain)
4. SplitBody legs + wedges using the entire seat body → remove above seat → rejoin interior
5. CUT seat mortises with the trimmed leg tenons
6. Stretchers — barrel-profile revolved spline at three staggered heights
7. Wedge slots on stretcher tenons (template-default grain detection on cylindrical legs)
8. SplitBody stretchers + wedges using leg bodies → remove far-side tips → rejoin interior
9. CUT leg mortises with trimmed stretcher tenons
10. CUT wedge bodies into their receiving bodies (leg wedges → seat, stretcher wedges → legs)
11. (Appearance applied by agent after build, per APPEARANCE SPEC block)

Seat top/bottom perimeter fillets are intentionally skipped — the loft's direction-tangent end conditions already provide the smooth edge-to-top blend, and filleting would flatten the carefully-shaped rollover.

## Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `seat_w` | 15 in | Seat max width (Y) |
| `seat_d` | 14 in | Seat max depth (X) |
| `seat_t` | 1.25 in | Seat thickness |
| `leg_h` | 24 in | Leg height floor to seat bottom |
| `leg_mid_dia` | 1.5 in | Leg max diameter at swell |
| `leg_swell_ratio` | 0.30 | Swell position from bottom |
| `splay` | 12 deg | Leg splay from vertical |
| `tenon_dia` | 0.625 in | Through-tenon diameter |
| `tenon_proud` | 0.25 in | Tenon protrusion above seat |
| `str_h1 / str_h2 / str_h3` | 6.5 / 8 / 9.5 in | Staggered stretcher heights |
| `ts_mid_dia` | 0.6 in | Stretcher body diameter |
| `ts_end_dia` | 0.45 in | Stretcher tenon diameter |
| `ts_tenon_len` | 1.5 in | Stretcher tenon length |
| `leg_spread` | 3 in | Leg distance from seat centroid |

The legacy `scoop_r` / `scoop_depth` parameters are still registered in the script (kept for backward compatibility with saved palettes) but are no longer consumed by the build — the loft provides the rounded seat surface natively.

## Appearance

This example ships with an `APPEARANCE SPEC` block at the top of the script. After each rebuild the agent applies, in order:

1. Oak on all bodies.
2. Walnut on `Seat`, `TW_L1` / `TW_L2` / `TW_L3` (leg-tenon wedges), and `TW_Str_*` (stretcher-tenon wedges), with `Seat` grain forced to `x`.
3. Hide all sketches + construction planes / axes / points across every component.
