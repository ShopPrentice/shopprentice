# Shaker Nightstand

![Shaker Nightstand — iso top-right](screenshots/iso-top-right.png)

<p float="left">
  <img src="screenshots/front.png" width="49%" />
  <img src="screenshots/right.png" width="49%" />
</p>

Parametric Shaker-inspired nightstand with full side panels, tapered feet, two dovetailed drawers, open lower shelf, and an overhanging top. White oak case with mahogany knobs.

Design inspired by [Becksvoort's Shaker-Inspired Side Chest](https://www.finewoodworking.com/2024/06/26/becksvoorts-shaker-inspired-side-chest) from Fine Woodworking.

## Dimensions

| Parameter | Default | Description |
|-----------|---------|-------------|
| `case_w` | 24 in | Overall case width (X) |
| `case_d` | 16 in | Overall case depth (Y) |
| `side_h` | 28 in | Side panel height (Z) |
| `top_thick` | 0.75 in | Top board thickness |
| `top_overhang` | 0.5 in | Top overhang beyond case |
| `board_thick` | 0.75 in | Side/shelf board thickness |
| `back_thick` | 0.25 in | Back panel thickness |
| `drawer_h` | 5 in | Drawer opening height |
| `leg_h` | 3 in | Leg cutout height from floor |
| `leg_w` | 1.5 in | Leg width at floor |
| `taper_offset` | 0.375 in | Foot taper inset at floor |
| `frame_w` | 2.5 in | Divider frame member width |
| `drawer_gap` | 0.125 in | Gap around drawers |
| `stretcher_d` | 1.5 in | Stretcher depth (front-to-back) |
| `bot_shelf_lift` | 1.5 in | Bottom shelf lift above legs |
| `knob_dia` | 1.25 in | Drawer knob diameter |
| `knob_proj` | 0.75 in | Knob projection from front |

## Components (25 bodies)

| Component | Bodies | Description |
|-----------|--------|-------------|
| **Sides** | 2 | Left + right full-height side panels with tapered feet (mirror) |
| **Case** | 13 | Sub-top (half-blind dovetailed), 2 shelves (stretcher + rear board each), divider frame (4 pieces), back panel |
| **Top** | 1 | Overhanging top with fillet roundovers |
| **Back** | 1 | Rabbeted back panel with tapered feet |
| **Drawers** | 8 | 2 dovetailed drawer boxes (front, back, left, right each) + 2 revolved knobs |

## Key Construction Details

- **Side panels**: Full-height boards with tapered feet — front and back arched cutouts create two tapered legs per side
- **Sliding dovetails**: Stretchers join sides via trapezoidal tenons (8° angle, 2/3-depth housing). Rear boards sit in dados behind each stretcher
- **Half-blind dovetails**: Sub-top joined to side panels at top — 7 tails, 8° angle, 0.25" lap
- **Divider frame**: Front rail (sliding dovetail to sides), back rail, two stiles — separates upper and lower drawer openings
- **Dovetailed drawers**: Built via `dovetailed_drawer` template — half-blind dovetails at front, through dovetails at back, bottom panel in grooves
- **Revolved knobs**: Spline half-profile revolved around axis — drag fit points to reshape
- **Back panel**: Rabbeted into sides with matching tapered feet
- **Top**: Overhanging top with gentle fillet roundovers on all edges

## Appearance

```
apply_appearance(species="white oak")
apply_appearance(species="mahogany", bodies=["Knob", "Knob (1)"])
```

White oak case, shelves, drawers. Mahogany drawer knobs for contrast.

## Parametric Notes

Most parameters update cleanly via Modify > Change Parameters: `case_w`, `case_d`, `board_thick`, `top_thick`, `top_overhang`, `knob_dia`, `knob_proj`, `frame_w`, `stretcher_d`, `leg_h`, `leg_w`, `taper_offset`, `drawer_gap`, `bot_shelf_lift`, `back_thick`.

Changing `drawer_h` or `side_h` requires a script rebuild (`execute_script(clean=True)`) because the sliding dovetail tenon sketches use baked coordinates that don't track vertical position changes.

## Reference

Design inspired by the Shaker-inspired side chest from [Fine Woodworking](https://www.finewoodworking.com/2024/06/26/becksvoorts-shaker-inspired-side-chest).
