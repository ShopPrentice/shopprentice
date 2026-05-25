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

## Custom Photo Textures (1:1 mapping)

When you need to map a specific photo onto one face exactly once (no tiling) — e.g. mapping a real photograph of a finished desk top onto the model's `top` body — there are two Fusion-API gotchas to know about:

### Gotcha 1: `texture_RealWorldScale*` and `texture_RealWorldOffset*` are stored in **INCHES**, not cm

The rest of the Fusion API uses cm internally (positions, parameters, body geometry), so it is natural to set a 47 cm desk-width scale as `47.0`. **It will not work.** Fusion stores these particular four properties in inches. You must convert:

```python
def cm_to_in(cm): return cm * 0.3937   # 1 cm = 0.3937 in

setf("texture_RealWorldScaleX",  cm_to_in(47.0))   # body width  in cm → 18.5 in
setf("texture_RealWorldScaleY",  cm_to_in(108.0))  # body length in cm → 42.5 in
setf("texture_RealWorldOffsetX", cm_to_in(-23.5))  # body min-X  → -9.25 in
setf("texture_RealWorldOffsetY", cm_to_in(-54.0))  # body min-Y  → -21.26 in
```

**`_SPECIES_TEXTURE` config values are in INCHES, matching their texture filenames.** For example `teak_15.8x60.3.jpg` is a 15.8 in × 60.3 in board sample — a real-world board roughly 16" wide × 5' long. The species config stores `scale_x=15.8, scale_y=60.3` and `_apply_custom_texture` writes those values directly to Fusion (which expects inches). **No cm-to-in conversion is performed inside the species wrappers** — the values are already in Fusion's storage unit.

When you need a custom texture sized to a specific body (e.g. mapping a desk-top photograph 1:1 onto a 47×108 cm body), you do the conversion at the call site:

```python
custom_cfg = dict(sp._SPECIES_TEXTURE["teak"])
custom_cfg["texture"] = "teak_desk_top.jpg"
custom_cfg["scale_x"] = 47.0 / 2.54     # body width  cm → 18.5 in
custom_cfg["scale_y"] = 108.0 / 2.54    # body length cm → 42.5 in
sp._SPECIES_TEXTURE["teak_top"] = custom_cfg
```

Historical note: an earlier version of `_apply_custom_texture` multiplied `scale_x`/`scale_y` by `_CM_TO_TEX_IN`, on the (incorrect) assumption that the species config was in cm. The wood textures actually came from inch-sized board scans, so that conversion shrank every veneer by 2.54× — masquerading as fine grain on slats, but showing up as visible "stitch" seams on bodies longer than the shrunk period (e.g. a 105 cm apron with `scale_y = 77 cm` instead of `77 in = 196 cm`). Fix: drop the conversion in the wrappers; species values stay as inches.

### Gotcha 2: Photo on one face only → Box+grain projection on the body, photo on a face appearance

The body's `textureMapControl` (TMC) is a single shared config — all appearances on the body share its projection mode and transform. So a body cannot mix Planar projection for the photo face with Box projection for the side faces; one TMC governs all.

Two projection modes were considered for a desk top with a photo on the top face only and tiled teak on the sides:

| TMC mode | Photo face | Side faces |
|----------|-----------|-----------|
| `PlanarTextureMapProjection` from +Z | 1:1 photo (face point XY → texture UV) | Wrong: side face has constant X (or Y), so the projected UV barely varies along the face — the photo collapses into a thin striped/smeared band running the length of the side. |
| `BoxTextureMapProjection` + grain rotation + bbox-min translate | 1:1 photo (top face is the +Z box-side projection) | Correct: side face gets the ±X box-side projection — image axes span the side's Y and Z, so the tiled species on the body renders as normal wood grain. |

**Use Box, not Planar.** Planar produces the side-face smearing the user sees as "split along length / sides look wrong." Box projects each face from its closest box-side, so each face gets a clean projection in the appropriate axes.

**Seam-at-center fix:** the default Box transform has texture origin at world origin. When the body is centered on world origin (e.g. a desk top spanning ±23.5 cm × ±54 cm), the texture coordinate `0` lands at the body center, and with `period == body extent` the seam (texture edge at coord 0 and at coord `period`) falls down the body's middle — visible as a vertical/horizontal split with the "two original ends meeting at center" pattern. **Fix:** translate the TMC transform so the texture origin lands at the body's bbox-min corner. The seam then falls at a body edge, where it's invisible.

```python
def box_grain_at_bbox_min(body):
    grain_vec = sp._grain_vector(body)         # principal-axes-of-inertia
    m = sp._grain_transform(grain_vec)         # rotation only
    bb = body.boundingBox
    m.setCell(0, 3, bb.minPoint.x)             # add translate to bbox-min
    m.setCell(1, 3, bb.minPoint.y)
    m.setCell(2, 3, bb.minPoint.z)
    ptmc = adsk.core.ProjectedTextureMapControl.cast(body.textureMapControl)
    ptmc.projectedTextureMapType = (
        adsk.core.ProjectedTextureMapTypes.BoxTextureMapProjection)
    ptmc.transform = m
```

This recipe is validated on the teak desk slats, top, legs, aprons, and round side stretchers — no visible seams, grain runs along each body's long axis, and a 47×108 cm photo lands exactly once on the 47×108 cm top face.

### Thin veneer / ear bodies for projection isolation

Fusion gives each body one `textureMapControl`. Face appearance overrides can
change the bitmap/appearance on a face, but they do **not** give that face an
independent projection transform. When one physical body needs incompatible
projection modes on adjacent surfaces, split the visual surface into a separate
thin body and apply the special appearance only to that body.

Use this when:

- A flat face needs Box projection for a 1:1 photo, but a neighboring fillet or
  edge needs Cylindrical projection to wrap smoothly.
- Face-level appearance overrides smear, stretch, or share the wrong body TMC.
- Box, Planar, and Cylindrical cannot all be made correct on one body because
  the body-level TMC is the limiting factor.

Desk-top "ear" pattern:

1. Keep the main desk-top body as the structural body. Use Box projection for
   the flat faces and photo/top mapping.
2. Select/copy the long-edge fillet faces that need smooth wrapped grain.
3. Thicken those faces outward by a tiny amount, e.g. `0.001 cm` (0.01 mm), as
   NewBody. Name them clearly, e.g. `ear_R`, `ear_L`.
4. Assign each ear its own copied appearance object. Do not reuse one appearance
   if you need to A/B test scale or offsets independently.
5. Apply Cylindrical projection on the ear body only, with the cylinder axis
   matching the fillet centerline.
6. Hide or ignore the main body's underlying fillet appearance where the ear
   covers it. The ear is a visual veneer, not a structural part.

Rules:

- The veneer body should sit just outside the real surface so it avoids z-fight
  flicker. `0.01 mm` is usually enough.
- Keep veneer bodies named and grouped with their source body so future agents
  do not treat them as real joinery or stock.
- Do not use the veneer body for interference, mass, or cut-list reasoning.
- Prefer independent appearances per veneer body while debugging; Fusion may
  report copied appearances with the same internal `Prism-*` id, so use
  appearance names and `usedBy` to confirm independence.

### Gotcha 3: Repeat off + a body smaller than one period → black borders

Setting `texture_URepeat = False` and `texture_VRepeat = False` clamps UVs outside `[0,1]` — anything past the texture edge becomes black. Combine this with the Gotcha-1 cm-vs-inch bug and you end up seeing the top face with the texture stretched (because it covered only ~39% of one period) plus mirrored/black borders where the body extended beyond the period.

When using `repeat=False` for a 1:1 mapping, also pad the source image by a few pixels of edge-extended content so any near-boundary UV sample doesn't hit black. Or stay with `repeat=True` once your scale is correct — visually identical because the period exactly equals the body size.

### Recipe: Photo on top face + tiled species on the rest of the body

For a desk top (or any body where one face shows a 1:1 photographic texture and the rest shows a tiled wood species):

```python
# 1. Pick a tile veneer (e.g. teak b: 13.9 × 89.2 cm period) for the body.
sp.apply_appearance("teak b", bodies=["top"])

# 2. Override the body TMC to Box projection with bbox-min translate.
#    Use IDENTITY rotation on the photo body — a grain rotation rotates the
#    photo image axes 90° relative to world X/Y and the photo no longer lands
#    1:1. Other (tiled) bodies use the grain rotation so their image-Y axis
#    follows the body's long axis; the photo body is the special case.
m = adsk.core.Matrix3D.create()                    # identity rotation
bb = top_body.boundingBox
m.setCell(0, 3, bb.minPoint.x)                     # translate cm
m.setCell(1, 3, bb.minPoint.y)
m.setCell(2, 3, bb.minPoint.z)
ptmc = adsk.core.ProjectedTextureMapControl.cast(top_body.textureMapControl)
ptmc.projectedTextureMapType = (
    adsk.core.ProjectedTextureMapTypes.BoxTextureMapProjection)
ptmc.transform = m

# 3. Register the photo as a custom species (period = body bbox extent).
custom_cfg = dict(sp._SPECIES_TEXTURE["teak"])     # inherit reflectance etc.
custom_cfg["texture"] = "teak_desk_top.jpg"
custom_cfg["scale_x"] = 47.0                        # cm — body width
custom_cfg["scale_y"] = 108.0                       # cm — body length
sp._SPECIES_TEXTURE["teak_top"] = custom_cfg

# 4. Create SP_teak_top by copying the tile and swapping in the photo.
photo_app = design.appearances.addByCopy(
    design.appearances.itemByName("SP_teak b"), "SP_teak_top")
sp._apply_custom_texture(photo_app, "teak_top")

# 5. CRITICAL: also set the PHOTO's RealWorldOffset to bbox-min in INCHES.
#    The body TMC translate alone is NOT enough for a non-tiling photo —
#    Fusion's Box projection adds the appearance's RealWorldOffset on top of
#    the TMC translate, and a stale or default offset shows up as a hard seam
#    at body center (because period == body extent for a 1:1 photo).
CM_TO_IN = 1.0 / 2.54
cp = adsk.core.ColorProperty.cast(
    photo_app.appearanceProperties.itemById("opaque_albedo"))
tex = cp.connectedTexture
def setf(name, val):
    p = tex.properties.itemById(name)
    adsk.core.FloatProperty.cast(p).value = val
setf("texture_RealWorldOffsetX", bb.minPoint.x * CM_TO_IN)
setf("texture_RealWorldOffsetY", bb.minPoint.y * CM_TO_IN)
setf("texture_UOffset", 0.0)
setf("texture_VOffset", 0.0)
setf("texture_WAngle", 0.0)

# 6. Apply the photo to the top BRepFace only.
top_face = ...  # the +Z planar face at z = bbox_max.z
top_face.appearance = photo_app
```

The body shows the tile veneer everywhere except the top face, which shows the photo at 1:1. Both share the body's Box TMC, which is what enables the mixed appearance.

**Why both offsets matter (and why slats only need the TMC translate):** A tiled veneer has period much smaller than the body. The slat veneers wrap many times along their length, and any sub-period offset just shifts where the (visually identical) repeat lands — not perceptible. The desk-top photo has period == body extent. Any offset modulo period shows up as a hard, visible seam, and any sub-pixel mismatch shows up as a fractional shift of unique photo features. Empirically: setting only the body TMC translate left a stale `RealWorldOffset = -1 period` on the appearance from earlier sessions; modulo a period that is mathematically zero, but Fusion's float arithmetic put the seam ~0.27 mm inside the body. Forcing `RealWorldOffsetX/Y = bbox.minPoint × CM_TO_IN` aligns the photo content edges exactly to the body bbox edges, with no seam visible on any face.

## Box projection deterministic recipe

For tile-repeating veneer photos (low-resolution wood scans where `px/cm` is below the threshold for natural rendering), the goal is no visible "seam" — the line where one image period ends and the next begins — on any visible face of the body.

### The rule (validated)

For a flat body where the natural image size along the grain (`natural_y_cm`) is **>= the body's grain-axis extent**:

```
period_along_grain = body_grain_cm × (1 + seam_buffer)  # 5% buffer is sufficient
period_cross_grain = natural_x_cm                        # leave at natural
translate_grain    = bbox_min_grain - (period_along_grain - body_grain_cm) / 2
translate_other    = bbox_min for those axes              # cross-grain at bbox-min
```

Implemented in `sp.fit_scale_y_cm(body, species, seam_buffer=0.05)` (period) plus the per-body recenter step in `_apply_textures()` (translate). With `seam_buffer = 0.05`, the period boundary lands ~2.5% of body length off-body on each side — small enough that float-precision drift does not push it back onto the body.

**Edge case — `body_grain >= natural`:** the texture must tile (cannot avoid a period boundary on the body). Either use a seamless texture or apply the photo to a single face via face-level appearance.

**Curved revolved bodies (legs, dowels):** Box's *direction-transition* artifact is separate from the period seam — see "Box on curved bodies" below.

### How this rule was derived — and how to re-derive it

The methodology is codified in `helpers/box_diagnostic.py`. Don't iterate by hand if you can avoid it.

**Modules and what they do:**

| Function | Purpose |
|----------|---------|
| `recommend_period_cm(body_grain, natural_grain, ppi, …)` | Pure-math: returns the recommended period and a label of which rule branch fired (sharp source / forced tile / compress with buffer / aesthetic floor). Use as the source of truth. |
| `recenter_translate_grain_cm(bbox_min_grain, period, body_grain)` | Returns the grain-axis translate that places both period boundaries off-body. |
| `analytical_seams(bbox_min, bbox_max, period, translate)` | Pure-math regression check. Lists period-boundary positions inside the body. Empty list = no seam *should* be visible. |
| `make_marker_image(src_path, dst_path)` | Generates a copy of a wood texture with red stripes on image-Y edges and green stripes on image-X edges. Apply this bitmap to a body via `_apply_custom_texture` to make seam locations obvious in screenshots. |
| `apply_box_grain_recipe(body, species, sp_module)` | High-level applier. Computes period via `recommend_period_cm`, sets a per-body appearance with that scale, builds the Box+grain TMC with the recentered translate, applies it. Returns a dict with the analytical state for logging. |
| `calibrate_seam_buffer(body, species, sp_module, screenshot_fn, oracle_fn)` | Sweep procedure: tests an ascending list of buffer candidates, takes a screenshot at each (with the marker bitmap on the body), and asks an oracle (`oracle_fn(image, buffer) → bool`) whether seams are visible. Returns the smallest seam-free buffer. Use to re-derive the baseline after a Fusion update. |

**Re-deriving the baseline after a Fusion change**

If a Fusion update or a new species or a new body shape introduces visible seams that the analytical rule says should not exist, run `calibrate_seam_buffer()` against a scratch document with representative test cuboids:

```python
from helpers import sp, box_diagnostic as bd

# scratch doc with parametric bodies of representative sizes already built
results = bd.calibrate_seam_buffer(
    body=test_body,
    species_key="teak b",
    sp_module=sp,
    buffer_candidates=(0.005, 0.01, 0.025, 0.05, 0.10, 0.20),
    screenshot_fn=lambda: mcp_get_screenshot("current"),  # returns image path
    oracle_fn=lambda path, buf: agent_check_for_red_lines(path),
)
print("Min seam-free buffer:", results["min_seam_free_buffer"])
```

`oracle_fn` is the only step that requires a visual-classification step — supply either a multimodal-LLM call that reads the screenshot, or a hand-rolled image analysis. The rest is deterministic.

The marker convention for `oracle_fn` to look for:
- **Red horizontal lines on the body** = period-along-grain boundary on body (= seam, increase buffer).
- **Green vertical lines on the body** = period-cross-grain boundary on body (= cross-grain too small, use natural).
- **Vertical band with no marker correlation** = Box-direction transition on a curved surface. Buffer cannot fix; rotate TMC instead (see "Box on curved bodies" below).

### Box on curved revolved bodies (legs, turned posts)

Box-projection direction transitions on a curved cylindrical surface produce visible vertical bands where one box-side projection ends and the next begins. The period seam rule above does **not** fix these.

**Recipe:** use Box+grain with the TMC rotated **45° around the body's grain axis**, scaled `body_grain × 3` along grain and `max_cross × 5` cross-grain. The 45° rotation moves the box-side direction transitions onto the diagonals of the body, where Fusion's shading on the curved surface visually masks them. Empirically validated on 70 cm tall lathe-turned legs.

```python
m = adsk.core.Matrix3D.create()
m.setToRotation(math.pi / 4.0,
                adsk.core.Vector3D.create(0, 0, 1),  # grain axis (Z for legs)
                adsk.core.Point3D.create(cx, cy, 0))  # body's center on the cross-grain plane
m.setCell(2, 3, bbox_min_grain - (period_grain - body_grain) / 2.0)
ptmc.projectedTextureMapType = adsk.core.ProjectedTextureMapTypes.BoxTextureMapProjection
ptmc.transform = m
```

If you discover (via the red-marker method) that the band shifts visibly off the curved diagonal — for example because Fusion changed how Box-projection direction transitions are computed — sweep the rotation angle (try 0, π/8, π/4, π/3, π/2) and pick the angle that puts the band on the most-curved part of the surface.

### When to use Box vs Cylindrical vs Spherical

In our experience Box+grain works for nearly every body shape (flat panels, lathe-turned posts, square stretchers). Cylindrical and Spherical we tested but reverted:

| Projection | When useful | Why we don't default to it |
|------------|------------|---------------------------|
| Box+grain (with 45° rotation for curved revolved bodies) | Default for everything | Works reliably; deterministic rule above |
| Cylindrical along axis | Round bars where grain MUST run perfectly along the axis | Requires `texture_WAngle = π/2` to swap Fusion's image axes; visually similar to Box+45° on most bars; one more knob to remember |
| Spherical | None we found that beat Box+45° | Looked worse on legs (compressed pole regions) |

If you find a future case where Box doesn't work, use the red-marker method to verify whether it's a period seam (fixable with buffer/translate) or a direction transition (needs rotation or alternative projection).

## Cylindrical and Spherical projection — corrected findings

Empirically validated against Fusion 360 (April 2026) using the red-marker
method. The previous notes elsewhere in the codebase had errors; the rules
below are correct.

### Cylindrical (`CylindricalTextureMapProjection`)

| Property | What it actually controls |
|----------|---------------------------|
| `texture_RealWorldScaleX` | Period along the cylinder axis (V direction) |
| `texture_RealWorldScaleY` | Period around the circumference (U direction) |
| `texture_WAngle` | **Silently ignored** by Cylindrical in this Fusion build |
| image-X (left/right edges) | Maps to axial direction |
| image-Y (top/bottom edges) | Maps to circumferential direction |

The mapping is **opposite** of the natural reading. Two consequences:

1. **Wood photos store grain along image-Y, but Cylindrical maps image-Y around the cylinder.** Native, the grain wraps perpendicular to the bar's length. To get grain along the cylinder axis, you must **pre-rotate the bitmap 90°** on disk (since WAngle has no effect). `helpers/cylindrical_diagnostic.make_axial_bitmap()` does this.

2. **For circumferential period, use N=1 (one wrap).** Higher N (e.g. 4) does NOT hide seams — it makes them MULTIPLY. With N>1 the natural bitmap fills only `1/N` of one period and the rest is filled by Fusion's repeat, producing N visible seam bands instead of one.

Recipe (validated on bars R=1, 1.3, 2, 3 cm × 38 cm and a 70 cm × 1.7 cm post):

```python
# helpers/cylindrical_diagnostic.py — apply_cylindrical_recipe(...)
period_axial = body_axial × 1.05          # Box rule: 5% buffer
period_circ  = circumference              # N=1 single wrap
offset_axial = bbox_min_axial − (period_axial − body_axial) / 2  # recenter
offset_circ  = circumference / 2          # rotate the one seam to back
# WAngle = 0 (ignored anyway)
# TMC: rotate texture-local +Z to body's long-axis vector; no translate
```

**Recommendation: prefer Box+45° for curved revolved bodies.** Box+45° hides the projection direction-transition in the curvature shading, uses the natural bitmap unrotated, and avoids the one inevitable azimuthal seam where the photo's image-Y top and bottom rows meet on the cylinder. Cylindrical is included for completeness and for cases where the user specifically wants the texture to wrap exactly once around a perfect cylinder.

### Cylindrical seam debugging with a baked bitmap marker

When a cylindrical seam is still visible after the analytical offset looks
right, do **not** draw Fusion overlay geometry as the seam marker. Overlay
lines only mark where you think the seam is. Instead, bake a high-contrast
stripe into the bitmap edge that participates in the repeat seam, apply that
diagnostic bitmap, and use screenshots to see where Fusion actually projects
the image boundary.

Workflow:

1. Identify which image axis maps to the physical direction you are debugging.
   For Cylindrical, image-X / `texture_RealWorldScaleX` maps along the
   cylinder axis, and image-Y / `texture_RealWorldScaleY` maps around the
   circumference. If the bitmap was pre-rotated 90° to make grain axial, the
   model's physical length direction may be controlled by
   `texture_RealWorldOffsetX`, not `texture_RealWorldOffsetY`.
2. Make a diagnostic copy of the bitmap with a thick red stripe on the relevant
   image boundary. Mark both ends when debugging the repeat join; mark one end
   when you need to track a single image edge.
3. Apply the diagnostic bitmap to the same appearance. Do not change scale,
   projection type, TMC axis, body geometry, or appearance assignment.
4. Sweep only the offset property for that image axis. Take the same screenshot
   view after each offset.
5. Use visual inspection or a simple pixel scan for red pixels to pick the
   offset where the red stripe leaves the visible body span or lands exactly on
   the intended end/underside.
6. Restore the clean bitmap and keep the winning offset.

Example from the desk-edge ear fix:

```python
# The edge bitmap was rotated 90° so grain ran along the cylindrical axis.
# Fusion cylindrical maps image-X to the physical Y/length direction, so the
# lengthwise seam was moved with RealWorldOffsetX, even though the user-facing
# intent was "move the seam along Y".
setf("texture_RealWorldOffsetX", 30.0 / 2.54)  # 30 cm winning sweep value
setf("texture_RealWorldOffsetY", 0.0)
```

Keep the diagnostic bitmap in `.context/` (not as a production texture) and
name it clearly, e.g. `*_RED_BOLD_BOTH_X_BOUNDARIES.jpg`. The production model
must be restored to the clean bitmap before final screenshots.

### Spherical (`SphericalTextureMapProjection`) — sphere-only recipe

Spherical projection works **only for bodies whose shape is close to a sphere** (aspect ≈ 1) or has a geometric pinch point that hides the polar singularity (e.g. a cone tapering to a tip). For other curved revolved bodies — cylinders, ellipsoids, hemispheres, bullets, squat disks — the polar pinching artifact persists at every value of `pole_clearance_factor` because Fusion's spherical projection maps image-Y to **latitude angle**, not meridian arc length. Increasing scale_y just relocates the pinch stripes; it doesn't eliminate them. (This was a corrected understanding from the initial "equatorial band" hypothesis, which was wrong.)

Recipe (sphere-like bodies only):

```
scale_x  = body_circumference                 # one azimuthal wrap
scale_y  = body_axial_extent × N (>= 3)       # default 3
offset_x = scale_x / 2                        # azimuthal seam to back
offset_y = scale_y / 2                        # body centered on equator
TMC translate = body bbox center
Projection axis = body's long axis
```

Body shape → recommended projection:

| Shape | Projection |
|-------|-----------|
| Sphere (aspect ≈ 1) | Spherical, N=3 |
| Cone (tapers to a tip) | Spherical, N=5 (apex pinch hides in geometric tip) |
| Cylinder (any aspect) | Cylindrical |
| Hemisphere / bullet / ellipsoid / squat disk | Box+grain |

`is_body_sphere_like(axial, radius)` returns True iff aspect ratio is within ±15% of 1 — the empirical heuristic for Spherical reliability. `apply_spherical_recipe()` accepts `warn_if_not_sphere_like` (default True) which prints a warning when the heuristic fails.

Implementation: `helpers/spherical_diagnostic.apply_spherical_recipe(body, species, sp_module, pole_clearance_factor=3.0)`. Use `calibrate_pole_clearance(...)` to re-derive the minimum `N` after Fusion updates.

## Which projection to use — quick reference

| Body shape | Use |
|------------|-----|
| Flat panel (top, slat, apron) | Box+grain + per-body fit + recenter (`helpers/box_diagnostic.apply_box_grain_recipe`) |
| Photo on one face only | Box+identity + photo `RealWorldOffset = bbox_min × CM_TO_IN` |
| Curved revolved body (legs, posts) | Box+grain with TMC rotated 45° around grain axis, scale_y = body × 3 (see "Box on curved bodies" above) |
| Round bar / dowel where exact one-wrap-around is desired | Cylindrical with `helpers/cylindrical_diagnostic.apply_cylindrical_recipe` (pre-rotated bitmap, N=1, recentered axial translate) |
| Sphere / dome / hemisphere | Box+grain (Spherical is unusable — see above) |

## When `sp.apply_appearance()` vs `box_diagnostic.apply_box_grain_recipe()`

- `sp.apply_appearance(species, bodies=...)` is the **simple shared-species flow**: assigns one design-level appearance to one or more bodies, sets each body's TMC to Box+grain rotation. **Does NOT do per-body fit, does NOT recenter the translate.** Suitable for small bodies where the texture's natural period covers the body comfortably (e.g. dovetail blocks, hardware).
- `box_diagnostic.apply_box_grain_recipe(body, species, sp_module)` is the **deterministic seam-free recipe**: per-body appearance copy, computed period via `recommend_period_cm`, recentered translate. Use when the body's grain extent approaches or exceeds 50% of the species' natural period (e.g. aprons on `teak c`).

Project scripts that want full seam control should call `apply_box_grain_recipe()` directly per body — that's how `teak_desk.py`'s `_apply_textures()` operates.

## Per-body appearance safety

**Rule: never modify a shared `SP_<species>` appearance after any body references it.**

Shared appearances are mutable global state in Fusion — modifying one
affects every body that references it. This caused accidental texture
resets during the teak desk build: applying Cylindrical to the legs
refreshed the shared `SP_teak b` appearance, which also reset the
stretchers that were using the same shared appearance.

### Enforcement

1. **`sp.per_body_appearance(body, species_key)`** — the approved way to
   get a modifiable appearance for a body. Creates `SP_<species>_<body.name>`
   by copying from the Fusion material library base directly. No shared
   `SP_<species>` is created or touched. The per-body copy is safe to
   modify (scale, bitmap, reflectance) without affecting any other body.

2. **Guard in `_apply_custom_texture`** — refuses to modify an appearance
   referenced by more than one body. Raises `ValueError` with a message
   pointing to `per_body_appearance()`.

### Usage in recipe functions

All three projection recipe functions use `per_body_appearance()`:

```python
# In apply_box_grain_recipe / apply_cylindrical_recipe / apply_spherical_recipe:
local = sp_module.per_body_appearance(body, species_key)
# Now safe to modify local's scale, bitmap, offsets:
tex = local.connectedTexture...
tex.properties.itemById("texture_RealWorldScaleY").value = ...
```

For Cylindrical projection (which needs a pre-rotated bitmap), call
`per_body_appearance()` first (sets up the species texture), then
override the bitmap path to the rotated version:

```python
local = sp_module.per_body_appearance(body, species_key)
fp = ...get bitmap property...
fp.value = "/tmp/teak_b_rot90.jpg"  # override to pre-rotated
```
