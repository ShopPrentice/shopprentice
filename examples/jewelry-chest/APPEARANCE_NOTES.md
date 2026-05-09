# Jewelry Chest Appearance Application Guide

## Overview

Three coats applied in order. Later coats override earlier on overlapping bodies.

1. **White oak** — all bodies (case, lid frame, tray, bottom, runners)
2. **Ziricote** — Pull only (regular, NOT endgrain)
3. **Spalted maple** — Lid_Panel_L and Lid_Panel_R only

## Step-by-Step Reproduction

### Step 1: Apply white oak to all bodies

```
apply_appearance(species="white oak")
```

Then fix oak texture scale (Fusion library default is too large):

```python
oak = design.appearances.itemByName("Oak")
tex = oak.connectedTexture  # via opaque_albedo ColorProperty
tex.scaleX = 12.0
tex.scaleY = 12.0
```

### Step 2: Apply ziricote to Pull

```python
pull.appearance = design.appearances.itemByName("SP_ziricote")
# Clear any endgrain face overrides
for fi in range(pull.faces.count):
    f = pull.faces.item(fi)
    if f.appearance:
        f.appearance = design.appearances.itemByName("SP_ziricote")
```

**Important**: Use `SP_ziricote`, NOT `SP_ziricote_endgrain`. The endgrain variant applies the cross-cut texture to all faces, which looks wrong on a small pull.

### Step 3: Apply spalted maple to lid panels

This is the complex step. The spalted maple is a custom photo texture that must be mapped as a continuous veneer across both panels.

#### 3a. Set body appearance

```python
spalted = design.appearances.itemByName("SP_spalted_land")
panel_l.appearance = spalted
panel_r.appearance = spalted
```

Also set all face overrides to the same appearance (face overrides persist and can't be removed):

```python
for body in [panel_l, panel_r]:
    for fi in range(body.faces.count):
        f = body.faces.item(fi)
        if f.appearance:
            f.appearance = spalted
```

#### 3b. Set texture scale

```python
tex = spalted.connectedTexture  # via opaque_albedo ColorProperty
tex.texture_RealWorldScaleX = 15.75
tex.texture_RealWorldScaleY = 9.76   # = 15.75 * 6.66 / 10.75
tex.texture_RealWorldOffsetX = 0.0
tex.texture_RealWorldOffsetY = 0.0
tex.texture_WAngle = 0.0
tex.texture_URepeat = True
tex.texture_VRepeat = True
```

#### 3c. Set TMC (shared origin for continuous grain)

Both panels must use the SAME TextureMapControl origin so the spalted maple grain flows continuously across the divider.

```python
origin = Panel_L.boundingBox.minPoint  # (4.1275, 3.3972, 12.2238) cm

m = Matrix3D.create()  # identity rotation
m.setCell(0, 3, 4.1275)   # Panel_L bbox-min X
m.setCell(1, 3, 3.3972)   # Panel_L bbox-min Y
m.setCell(2, 3, 12.2238)  # Panel_L bbox-min Z

for body in [panel_l, panel_r]:
    ptmc = ProjectedTextureMapControl.cast(body.textureMapControl)
    ptmc.projectedTextureMapType = BoxTextureMapProjection
    ptmc.transform = m
```

## Image

- **Source**: `spalted_maple.jpg` (1720x3380 px, portrait, grain vertical)
- **Pre-rotated**: `spalted_maple_landscape.jpg` (3380x1720 px, landscape, grain horizontal, 17.8" x 9.1")
- Pre-rotation avoids WAngle=90 which caused scale/projection confusion
- Registered as custom species `"spalted_land"`

## Scale Calibration

### Empirical findings (2026-05-08)

The relationship between `texture_RealWorldScale` and the visible texture period was determined empirically using three diagnostic methods:

1. **Red/green edge markers**: Red stripes on image Y edges (top/bottom), green on X edges (left/right). When tiling creates a seam on the panel, these colored stripes appear at the seam boundary.

2. **URepeat=False black boundary test**: Disabling tiling causes areas outside the image boundary to render black. The boundary between image and black shows exactly where the period ends.

3. **Percentage grid overlay**: 10% grid lines overlaid on the image to measure what fraction of the source image appears on the panels.

### Key results

| Scale | Period (empirical) | Panel coverage | Seams? | Notes |
|-------|-------------------|----------------|--------|-------|
| 10.75 | ~5" | ~47% per panel | Yes (multiple) | Period much smaller than panel span |
| 11.29 | ~5.5" | ~50% | Yes | Still too small |
| 13.0 | ~6.3" | Y too small | Y seam visible | X OK but Y runs out |
| 15.0 | ~7.3" | Y barely short | Thin Y seam | Almost covers Y |
| 15.5 | ~7.5" | Full coverage | Red marker at Y edge | Just barely covers |
| 15.75 | ~7.7" | Full coverage | Clean | Minimum safe scale |
| 16.0 | ~7.8" | Full coverage | Clean | Safe margin |
| 21.5 | ~10.5" | ~50% total | None | Original no-seam threshold |
| 22.575 | ~11" | ~48% per axis (~25% area) | None | Old calibration — too zoomed |
| 26.6 | ~13" | ~40% per axis (~20% area) | None | Original notes — way too zoomed |

The period-to-scale relationship is approximately **period ≈ scale × 0.49** (close to scale/2 but not exact). The combined panel span is 10.75" and the minimum scale that avoids seams while showing the most image is **15.75**.

At scale 15.75, the panels show approximately 68% of the source image per axis (~46% of total image area). This is a significant improvement over the original scale 26.6 which showed only ~20% of the image.

### Previous calibration was wrong

The original notes stated "period ≈ scale / 2" with scaleX=26.6, claiming ~80% image coverage. Actual coverage at that scale was only ~25% (confirmed by the user's observation and the percentage grid diagnostic). The relationship is nonlinear or has a different constant than assumed.

## Known Issues

- **Panel bottom face (-Z) does not render spalted maple texture.** Box projection on the downward-facing face of thin panels does not render the texture — it shows only the appearance's base color. This appears to be a Fusion limitation. The bottom of the lid is rarely visible (sits on the case).

- **Face-level overrides persist.** `f.appearance = None` does not truly clear face overrides. Setting them to the same appearance as the body works (they share the texture properties).

- **Panel_R rendering corruption.** After multiple appearance changes, Panel_R can become invisible (renders as transparent). Fix: suppress and unsuppress the `LPR_M` mirror feature in the timeline to recreate the body.

- **Oak scale must be set manually.** The design's Oak appearance had scaleX=80, scaleY=40 (way too large, causing blurry grain). Reset to 12x12 for proper resolution. This may have been caused by previous appearance operations corrupting the shared Oak appearance.

## Appearance Order (important)

Apply in this exact order:
1. `apply_appearance("white oak")` — all bodies
2. Fix oak scale to 12x12
3. Set Pull to `SP_ziricote` (not endgrain)
4. Set Panel_L and Panel_R to `SP_spalted_land`
5. Set spalted maple texture scale: 15.75 x 9.76
6. Set TMC on both panels: identity + translate to Panel_L bbox-min
7. Set all panel face overrides to SP_spalted_land
