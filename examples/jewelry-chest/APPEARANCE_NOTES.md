# Spalted Maple Panel Appearance Notes

## What works (current best state)

The lid panels use a pre-rotated landscape spalted maple image applied with Box projection. The key challenge was getting the full image to map across both panels as a continuous veneer without seams and at full resolution.

## Image

- **Source**: `spalted_maple.jpg` (1720×3380 px, portrait, grain vertical, 9.1" × 17.8")
- **Pre-rotated**: `spalted_maple_landscape.jpg` (3380×1720 px, landscape, grain horizontal, 17.8" × 9.1")
- Pre-rotation avoids WAngle=90° which caused scale/projection confusion
- Registered as custom species `"spalted_land"` with `scale_x=17.8, scale_y=9.1`

## Projection setup

- **Projection type**: Box (`BoxTextureMapProjection`)
- **TMC transform**: Identity (no rotation) + translate to Panel_L bbox-min `(4.13, 3.40, 12.22)` cm
- **Shared origin**: Both Panel_L and Panel_R use the SAME TMC origin so the grain is continuous across the divider

## Scale values

- `texture_RealWorldScaleX = 26.6`
- `texture_RealWorldScaleY = 13.6`
- `texture_WAngle = 0.0`
- `texture_RealWorldOffsetX = 0.0`
- `texture_RealWorldOffsetY = 0.0`

### How the scale was calibrated

Fusion's `texture_RealWorldScale` property has a non-obvious unit relationship. Empirical calibration using the diagnostic image (colored borders):

1. At `scale=10`, one texture period ≈ 5 inches (Box projection)
2. Relationship: **period_inches ≈ scale / 2** (for Box projection)
3. To map the full 17.8" × 9.1" image: `scaleX = 17.8 × 2 × (panel_coverage_fraction)` 
4. Final values: `scaleX=26.6` gives ~13.3" period in X (covers 10.75" combined panels), `scaleY=13.6` gives ~6.8" period in Y (covers 6.66" panel height)
5. Panels show ~80% of image width × ~98% of image height

### Critical: must fix ALL face appearances

`sp.apply_appearance()` creates endgrain face overrides on 8 faces per panel. These face-level appearances have their OWN texture scale that is NOT linked to the body-level appearance. When adjusting scale:

```python
# Must iterate FACE appearances directly, not just design.appearances by name
for b in [panel_l, panel_r]:
    for a in [b.appearance] + [b.faces.item(fi).appearance for fi in range(b.faces.count) if b.faces.item(fi).appearance]:
        if "spalted" in a.name.lower():
            # fix scale on this appearance
```

Filtering by `design.appearances` name misses appearances that have been renamed or don't match the filter string (e.g., `"SP_diag_land"` doesn't contain `"spalted"`).

### Warning: don't change ALL appearances

When fixing spalted maple scale, do NOT loop over all `design.appearances` without filtering — this will corrupt the Oak/Cherry/other texture scales too, making them blurry.

## Other appearances

- **Case/frame**: White oak via `apply_appearance("white oak")` — uses default Fusion library appearance with auto grain detection
- **Pull**: Ziricote via `apply_appearance("ziricote", bodies=["Pull"])`
- Apply oak FIRST (all bodies), then ziricote (pull only), then spalted maple (panels only) — later calls override earlier on the same bodies

## Known issues

- The spalted maple panels still show only ~60-80% of the full image. The image represents a 17.8" × 9.1" board but the combined panel visible area is only ~10.25" × 6.16". There's no way to show 100% of a larger image on a smaller panel without distortion.
- Face-level endgrain overrides cannot be removed via `f.appearance = None` — they persist. The workaround is to set their texture properties to match the desired face grain appearance.
- The `sp.apply_appearance()` helper divides scale config values by 2.54 internally, producing compressed textures. The MCP `apply_appearance` tool writes correct values but triggers endgrain face overrides. Manual post-processing of texture properties is currently required for custom texture mapping.
