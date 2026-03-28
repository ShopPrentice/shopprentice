# Custom Wood Grain Textures

Custom high-resolution wood textures for 5 exotic/specialty species not available in Fusion 360's built-in material library.

## Species

| Species | Base Appearance | Pixels (WxH) | Physical Size | Reflectance |
|---------|----------------|---------------|---------------|-------------|
| Teak | Mahogany | 1560x3160 | 9.9" x 20.1" | 0.035 |
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
  teak.jpg                   # face grain (used by _apply_custom_texture)
  teak_endgrain.jpg          # end grain (used by _apply_endgrain_texture)
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

## Usage in Scripts

```python
from helpers import sp
sp.apply_appearance("teak")                          # all bodies
sp.apply_appearance("cocobolo", bodies=["Top"])      # specific body
```

## TODO

- [ ] End grain textures are still the original small versions — find larger replacements
- [ ] Consider adding more species (purpleheart, wenge, padauk, bubinga)
- [ ] Investigate seamless tiling for very large surfaces (panels > 24")
