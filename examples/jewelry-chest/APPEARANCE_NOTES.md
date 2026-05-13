# Jewelry Chest Appearance Application Guide

## Overview

Three coats applied in order. Later coats override earlier on overlapping bodies.

1. **White oak** — all bodies (case, lid frame, tray, bottom, runners)
2. **Ziricote** — Pull only (regular, NOT endgrain)
3. **Spalted maple** — Lid_Panel_L and Lid_Panel_R only (via `helpers.veneer`)

## Appearance Order (after every `execute_script(clean=True)`)

```python
from helpers import sp
from helpers.veneer import apply_veneer_realsize

# 1. White oak on all bodies + fix scale
sp.apply_appearance("white oak")
oak = design.appearances.itemByName("Oak")
cp = adsk.core.ColorProperty.cast(oak.appearanceProperties.itemById("opaque_albedo"))
if cp and cp.hasConnectedTexture:
    tex = cp.connectedTexture
    tex.properties.itemById("texture_RealWorldScaleX").value = 12.0
    tex.properties.itemById("texture_RealWorldScaleY").value = 12.0

# 2. Ziricote on Pull
sp.apply_appearance("ziricote", bodies=["Pull"])

# 3. Suppress/unsuppress Panel_R mirror (prevents rendering corruption)
for i in range(lid_c.features.mirrorFeatures.count):
    mf = lid_c.features.mirrorFeatures.item(i)
    if mf.name == "LPR_M":
        mf.isSuppressed = True
        mf.isSuppressed = False
        break

# 4. Spalted maple veneer at real size
apply_veneer_realsize(
    bodies=[panel_l, panel_r],
    image_path="/Users/frankzha/projects/shopprentice/textures/wood/spalted_maple_landscape.jpg",
    real_width_inches=12.0,
    real_height_inches=7.0,
    origin_body=panel_l,
    appearance_name="SP_spalted_land",
    fix_bottom_face=True,   # uses flipped image + scale compensation for -Z faces
)

# 5. (Optional) Brass hinges
# Apply `Brass - Satin` to hinge bodies if installed
```

## Veneer Library (`helpers.veneer`)

The `apply_veneer_realsize` function handles all the complexity that previously required 11 manual steps:
- Creates appearance from Fusion library base ("Pine")
- Sets bitmap, scale, offsets, tiling via property IDs (not names — more reliable)
- Applies to all body faces (prevents stale face-level overrides)
- Sets shared TMC origin at `origin_body.boundingBox.minPoint` for continuous grain
- Creates a flipped-image bottom appearance for -Z faces (mirror of top)

### Scale-to-Period Relationship

Confirmed empirically and via `FloatProperty.units` → `'Inch'`:

    texture_RealWorldScaleX/Y is in INCHES
    period_inches = scale_inches / 2
    scale = desired_period_inches * 2

To cover a span of W inches with one tile: `scale = W * 2`.

### Real-Size Application

The spalted maple landscape image (`spalted_maple_landscape.jpg`, 3380×1720 px) maps to approximately **12" × 7"** of real wood. This was tuned visually — the grain pattern looks natural at this size on the jewelry chest panels.

For pieces smaller than 12" × 7": no seams, shows a portion of the image.
For pieces larger: image tiles at 12"/7" intervals, which is acceptable.

### Bottom Face (-Z) Fix

Box projection maps -Z faces with inverted UV axes. The veneer function:
1. Auto-generates a horizontally flipped copy of the image (`*_flipped.jpg` via macOS `sips`)
2. Applies the flipped image with negated scales + Y offset to compensate for UV inversion
3. Result: bottom is a true mirror of top (like looking through thin veneer from behind)

## Image Files

| File | Description |
|------|-------------|
| `spalted_maple.jpg` | 1720×3380 px, portrait, grain vertical |
| `spalted_maple_landscape.jpg` | 3380×1720 px, landscape, grain horizontal |
| `spalted_maple_landscape_flipped.jpg` | Horizontally flipped landscape (auto-generated for bottom faces) |

All in `/Users/frankzha/projects/shopprentice/textures/wood/`.

## Known Issues

- **Panel_R rendering corruption.** After multiple appearance changes, Panel_R can become transparent. Fix: suppress and unsuppress `LPR_M` mirror feature (done automatically in the appearance script).

- **Face-level overrides persist.** `f.appearance = None` does not truly clear overrides. The veneer function sets ALL faces explicitly to prevent stale overrides.

- **Oak scale corruption.** The Oak appearance scale can drift to 80×40 after appearance operations. Always reset to 12×12 after `sp.apply_appearance("white oak")`.

## Previous Calibration (superseded)

The old notes used `scaleX=15.75, scaleY=9.76` with an approximate `period ≈ scale × 0.49`. This was incorrect — the exact relationship is `period = scale / 2` (confirmed via URepeat=False boundary tests and `FloatProperty.units`). The old values produced periods of 7.88" × 4.88" which were too small for the 10.75" × 6.66" panel span, causing recurring seam issues on every rebuild.
