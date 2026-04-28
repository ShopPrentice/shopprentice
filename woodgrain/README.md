# Custom Wood Grain Textures

Custom high-resolution wood textures for 5 exotic/specialty species not available in Fusion 360's built-in material library.

## Species

| Species | Base Appearance | Pixels (WxH) | Physical Size | Reflectance |
|---------|----------------|---------------|---------------|-------------|
| Teak | Mahogany | 3120x6320 | 9.9" x 20.1" | 0.035 |
| Brazilian Rosewood | Walnut | 1400x3440 | 8.1" x 19.8" | 0.06 |
| Cocobolo | Walnut | 1460x3120 | 9.8" x 20.8" | 0.07 |
| Ziricote | Walnut | 1330x3520 | 9.0" x 23.9" | 0.05 |
| Spalted Maple | Pine | 1720x3380 | 9.1" x 17.8" | 0.025 |

Physical size = the real-world dimensions of the wood piece in the source photo, measured from scale references (rulers, labeled dimensions) in the original product shots.

## How It Works

No Fusion installation needed. The textures are loaded at runtime by `sp.apply_appearance()`:

1. Copies a base appearance (e.g. "Walnut") from Fusion's built-in material library into the design
2. Swaps the bitmap path to point to the custom `.jpg` file on disk
3. Sets `texture_RealWorldScaleX/Y` to the physical size so the texture maps at correct scale
4. Sets reflectance (`opaque_f0`) to match the species
5. Applies `ProjectedTextureMapControl` with `BoxTextureMapProjection`, rotating the texture Z-axis to align with the body's longest axis (grain direction)

End grain faces (the two smallest faces perpendicular to grain) get a separate end grain appearance with its own texture.

## Directory Structure

```
woodgrain/
  README.md                  # this file
  face_grain/                # current large face grain textures (deployed)
    teak.jpg
    brazilian_rosewood.jpg
    cocobolo.jpg
    ziricote.jpg
    spalted_maple.jpg
  endgrain/                  # current end grain textures
    teak_endgrain.jpg
    brazilian_rosewood_endgrain.jpg
    cocobolo_endgrain.jpg
    ziricote_endgrain.jpg
    spalted_maple_endgrain.jpg
  backup_small/              # previous smaller textures (replaced)
  probe_wood_appearance.py   # dumps Fusion appearance property tree (diagnostic)
  refresh_appearance.py      # force-reloads sp module + re-applies appearance
```

## Deployed Locations

Textures are deployed to `textures/wood/` in the project root. At runtime, `sp.py` resolves `_TEXTURE_DIR` relative to its own `__file__` path:

```
textures/wood/
  teak.jpg                   # final face grain (used by _apply_custom_texture)
  teak_endgrain.jpg          # final end grain (used by _apply_endgrain_texture)
  ... (same pattern for all 5 species)
```

## Configuration

Scale values and base appearances are defined in `helpers/sp.py` → `_SPECIES_TEXTURE` dict. To add a new species:

1. Drop `species_name.jpg` (portrait orientation, grain vertical) in `textures/wood/`
2. Optionally add `species_name_endgrain.jpg`
3. Add an entry to `_SPECIES_TEXTURE` with:
   - `base`: closest built-in Fusion appearance to clone (for material properties)
   - `texture`: filename
   - `scale_x`, `scale_y`: physical size in inches (measure from source photo)
   - `reflectance`: surface sheen (0.02 = matte, 0.07 = glossy)
   - `endgrain`, `eg_scale_x`, `eg_scale_y`: end grain texture + scale

## Image Requirements

- **Portrait orientation**: grain must run vertically (along image Y axis). The `_grain_transform` function assumes this.
- **Clean edges**: no background, rulers, scale markers, or non-wood pixels at image boundaries. These cause visible bleeding when the texture tiles.
- **Minimum 1200px wide**: smaller images produce visible repetition on furniture-scale bodies.
- **Source photos**: product shots from wood veneer retailers with visible rulers or labeled dimensions for accurate scale calculation.

## Asset Management Policy

Keep only final, canonical texture assets in `textures/wood/`. Raw photos, rectification attempts, color-grade variants, model comparisons, and upscaling candidates belong outside the tracked skill texture directory, under `.context/wood_texture_pipeline/`.

For example:

```
.context/wood_texture_pipeline/
  teak/
    raw/                # source/cropped/color-graded inputs
    final_candidates/   # generated candidates such as *_2x_blend40
```

When a candidate is accepted, copy it into `textures/wood/` using the canonical filename (`teak_a.jpg`, not `teak_a_2x_blend40.jpg`) and update `helpers/sp.py` metadata if the pixel dimensions changed. Physical scale values do not change when an image is upscaled.

## Production Pipeline

Use this pipeline for new veneer/board photos and for refreshing existing teak variants.

### 1. Crop and rectify

Perspective-correct the source photo to a physical board rectangle:

```bash
scripts/wood_veneer_rectify.py \
  source.jpg .context/wood_texture_pipeline/species/raw/species_variant_rectified.jpg \
  --corners "TLx,TLy TRx,TRy BRx,BRy BLx,BLy" \
  --physical-size "width,height" \
  --unit in \
  --px-per-mm 3 \
  --crop-px "left,top,right,bottom" \
  --reflect-pad-px 12
```

This writes the texture and a JSON sidecar containing physical size, Fusion scale, DPI, and reflected edge padding metadata.

### 2. Color grade

Normalize low-frequency color/reflection without destroying grain detail:

```bash
scripts/wood_texture_color_grade.py \
  .context/wood_texture_pipeline/species/raw/species_variant_rectified.jpg \
  .context/wood_texture_pipeline/species/final_candidates/species_variant_color.jpg \
  --reference-image textures/wood/reference.jpg \
  --reference-rect "x,y,w,h" \
  --target-mode auto \
  --ignore-padding 12 \
  --regenerate-padding \
  --preview .context/species_variant_color_preview.jpg
```

For teak variants, use a known-good teak region as the reference and preserve horizontal color variation with `auto`/`per-x` where the reference spans enough board width.

### 3. Upscale with the 40% blend

The default final teak upscale is:

- 60% native Real-ESRGAN x2 (`realesr-animevideov3`, NCNN/Vulkan)
- 40% generic 2x Lanczos + mild unsharp mask

Run:

```bash
scripts/wood_texture_upscale_blend.py \
  .context/wood_texture_pipeline/species/final_candidates/species_variant_color.jpg
```

By default the output is written outside the tracked texture directory:

```
.context/wood_texture_pipeline/candidates/species_variant_2x_blend40.jpg
```

If the source has a JSON sidecar, the script writes a matching sidecar with doubled pixel dimensions/DPI while preserving the same physical board size and Fusion scale.

Batch example for teak candidates from archived source/corrected images:

```bash
scripts/wood_texture_upscale_blend.py \
  --output-dir .context/wood_texture_pipeline/teak/final_candidates \
  .context/wood_texture_pipeline/teak/raw/teak.jpg \
  .context/wood_texture_pipeline/teak/raw/teak_a.jpg \
  .context/wood_texture_pipeline/teak/raw/teak_b.jpg \
  .context/wood_texture_pipeline/teak/raw/teak_c.jpg \
  .context/wood_texture_pipeline/teak/raw/teak_d.jpg \
  .context/wood_texture_pipeline/teak/raw/teak_e.jpg \
  .context/wood_texture_pipeline/teak/raw/teak_desk_top.jpg \
  .context/wood_texture_pipeline/teak/raw/teak_endgrain.jpg
```

### 4. Promote the accepted final

Copy the accepted candidate into `textures/wood/` using the canonical filename:

```bash
cp .context/wood_texture_pipeline/candidates/species_variant_2x_blend40.jpg \
   textures/wood/species_variant.jpg
```

If the candidate has a JSON sidecar, promote it too and set `output_image` to the canonical texture path. Then update `helpers/sp.py` → `_SPECIES_TEXTURE` with the final `px_w`/`px_h`. Do not change `texture`, `scale_x`, or `scale_y` unless the final asset filename or physical source board changed. Upscaling increases pixel density, not physical board size.

## Usage in Scripts

```python
from helpers import sp
sp.apply_appearance("teak")                          # all bodies
sp.apply_appearance("cocobolo", bodies=["Top"])      # specific body
```

## TODO

- [ ] Find true higher-resolution end grain photos; current teak end grain is AI-assisted 2x, not a new source photo
- [ ] Consider adding more species (purpleheart, wenge, padauk, bubinga)
- [ ] Investigate seamless tiling for very large surfaces (panels > 24")
