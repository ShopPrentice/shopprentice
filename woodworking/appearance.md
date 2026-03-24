# Wood Appearance

Apply realistic wood appearances to bodies with grain direction aligned to fiber direction.

## Default Species

**White oak.** Use the species the user requests. If none specified, use white oak.

## How to Call (in scripts)

Every model script must apply appearance before the fit-view epilogue. Use the `sp.apply_appearance()` helper:

```python
from helpers import sp

# ... build geometry ...

sp.apply_appearance("white oak")    # all bodies, auto grain

# Fit view epilogue
cam = app.activeViewport.camera
cam.isFitView = True
app.activeViewport.camera = cam
```

This is a **required step** — scripts without appearance produce grey models.

## When to Call

After final validation (zero interferences, correct body count), before the fit-view epilogue. The appearance call is the last modeling step before presenting the model to the user.

## MCP Tool (advanced)

The `apply_appearance` MCP tool provides additional features not in the `af` helper:
- `bodies` parameter to target specific bodies
- `grain_overrides` to manually set grain direction per body
- Dovetail constraint analysis (auto-excludes end-grain axes)

```
apply_appearance(species="cherry", bodies=["Front"])      # specific bodies
apply_appearance(species="walnut",                        # override grain
                 grain_overrides={"Leg_FL": "z"})
```

## Grain Direction

Grain direction is determined automatically per-body using two rules:

1. **Longest axis** — fibers run parallel to the longest bounding box dimension (legs=Z, rails=X/Y, panels=longest).
2. **Dovetail constraint** — the tool scans the timeline for dovetail features (DT_Pat, DT_Cut*, DT_Join*). Dovetailed edges are end grain, so the joint axis (pattern direction) is excluded. If the longest axis conflicts with a dovetail constraint, the next-longest non-excluded axis is chosen.

### Example: Blanket Box

| Body | Longest axis | Dovetail constraint | Result |
|------|-------------|-------------------|--------|
| Front (41"×25"×0.75") | X (41") | none | X |
| Left (0.75"×18.5"×25") | Z (25") | Z excluded (DT edge along Z) | Y (18.5") |
| Leg (1.5"×1.5"×4.5") | Z (4.5") | none | Z |
| Rail_Front (36"×0.75"×3.5") | X (36") | none | X |
| Rail_Left (0.75"×15"×3.5") | Y (15") | none | Y |

### When Auto-Detection is Wrong

Pass `grain_overrides` for specific bodies:
```
apply_appearance(species="cherry", grain_overrides={"Panel_A": "x"})
```
This is rare — the two-rule system handles most furniture correctly.

## Supported Species

cherry, walnut, oak, white oak, red oak, maple, ash, birch, pine, cedar, mahogany, teak, beech, poplar, hickory, ebony, rosewood, sapele, bamboo, douglas fir.

## Multi-Species Designs

Call `apply_appearance` multiple times with different `bodies` lists:
```
apply_appearance(species="cherry")                                    # case
apply_appearance(species="walnut", bodies=["Drw_Front", "Drw_Back"]) # drawer accent
```

## Technical Details

- Uses `ProjectedTextureMapControl` with `BoxTextureMapProjection` for reliable grain orientation
- The texture map Z-axis is rotated to align with the detected grain axis via `Matrix3D.setToRotation`
- Appearances are copied from the Fusion 360 material library into the design on first use
