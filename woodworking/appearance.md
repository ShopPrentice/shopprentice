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

Grain direction is determined automatically per-body using **principal axes of inertia**:

1. **Principal axis** — `body.physicalProperties.getPrincipalAxes()` returns three orthogonal axes. The axis with the **smallest moment of inertia** is the elongation axis (grain direction). This works for any orientation: axis-aligned boards, compound-angle splayed legs, angled stretchers, turned spindles. Falls back to bounding-box longest axis if the API call fails.
2. **Dovetail constraint** — the MCP tool scans the timeline for dovetail features (DT_Pat, DT_Cut*, DT_Join*). Dovetailed edges are end grain, so the joint axis (pattern direction) is excluded. If the principal axis conflicts with a dovetail constraint, the next axis is chosen.

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

### Built-in (from Fusion 360 material library)

cherry, walnut, oak, white oak, red oak, maple, ash, birch, pine, cedar, mahogany, beech, poplar, hickory, ebony, rosewood, sapele, bamboo, douglas fir.

### Custom (high-res textures with end grain)

teak, brazilian rosewood, cocobolo, ziricote, spalted maple.

Custom species use photo-based textures stored in `textures/wood/`. No Fusion installation needed — `sp.apply_appearance()` clones a base appearance and swaps the bitmap at runtime. See `woodgrain/README.md` for image specs and scale calibration.

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

## Persisting Appearance Across Rebuilds

**Problem:** Fusion stores appearance on body entity tokens in the design database, not in the script. `execute_script(clean=True)` destroys bodies and creates new ones with fresh tokens, so all prior appearance assignments are lost. The simple `sp.apply_appearance()` call inside a script handles species + body filter, but **cannot** apply `grain_overrides` or multi-pass coats — those are MCP-tool-only features.

**Solution:** Declare the appearance intent as a structured comment block near the top of the script. The agent parses this block after every successful `execute_script(clean=True)` and replays it via the `apply_appearance` MCP tool.

### Format

```python
# ═══════════════ APPEARANCE SPEC ══════════════════════════
# After execute_script(clean=True), agent parses this block
# and applies each coat in order via the apply_appearance MCP
# tool. After coats, if hide_construction is true, hide all
# sketches and construction geometry.
# {
#   "coats": [
#     {"species": "oak"},
#     {"species": "walnut",
#      "bodies": ["Seat", "TW_L*", "TW_Str_*"],
#      "grain_overrides": {"Seat": "x"}}
#   ],
#   "hide_construction": true
# }
# ══════════════════════════════════════════════════════════
```

### Schema

| Field | Type | Notes |
|-------|------|-------|
| `coats` | array, required | Applied **in order** — later coats override earlier on overlapping bodies |
| `coats[].species` | string, required | Any species supported by `apply_appearance` (see *Supported Species*) |
| `coats[].bodies` | list, optional | Body names. Supports `*` suffix as prefix glob (e.g. `TW_L*` = all `TW_L…`). Omit or use `"*"` alone for all bodies |
| `coats[].grain_overrides` | object, optional | `{bodyName: "x"|"y"|"z"}` — forces grain axis for auto-detection-wrong cases |
| `hide_construction` | bool, optional | If `true`, hide all `sketches`, `constructionPlanes`, `constructionAxes`, and `constructionPoints` across every component after coats are applied |

### Agent Workflow

After a successful `execute_script(clean=True)`:

1. Read the script source from `script_path`.
2. Locate the `# ═══════ APPEARANCE SPEC` header, then concatenate subsequent `#`-prefixed lines with the leading `# ` stripped.
3. Parse the concatenated text as JSON.
4. For each entry in `coats`:
   - Expand body globs (`TW_L*` → list of matching body names from `capture_design`).
   - Call `apply_appearance(species=..., bodies=..., grain_overrides=...)`.
5. If `hide_construction` is true, run the hide-construction pass.

If the block is absent, fall back to the default: `apply_appearance(species="white oak")` on all bodies (matches the skill default species).

### When to Add the Block

Add an APPEARANCE SPEC block whenever:

- The model uses **more than one species** (seat + structure, inlays, accents)
- Any body needs a **grain_override** because auto-detection picks the wrong axis (common on wide panels like seats, tabletops, slabs)
- The agent or user has explicitly chosen a finish during a build session that should persist through later rebuilds

For single-species models where the auto-detected grain is correct, calling `sp.apply_appearance("white oak")` inside the script is sufficient — no spec block needed.

### Reference Example

`examples/esherick-stool/esherick_stool.py` uses this convention: oak baseline, walnut on the seat + all tenon wedges, with a grain override on the seat (X). See the block at the top of that file.
