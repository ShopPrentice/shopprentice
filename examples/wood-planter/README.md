# Parametric Wood Planter

A parametric wood planter modeled in Fusion 360 via Python script. 60"L x 20"W x 40"H (10" legs), frame construction with mortise-and-tenon joinery, grooved rails, and vertical tongue-and-groove slat infill.

![Wood planter — iso top-right](screenshots/iso-top-right.png)

![Wood planter — iso top-left](screenshots/iso-top-left.png)

<p float="left">
  <img src="screenshots/front.png" width="49%" />
  <img src="screenshots/right.png" width="49%" />
</p>

## Example Prompt

```
/woodworking
Build a 60" x 20" x 40" wood planter with 10" legs, 3" square posts, frame construction
with mortise-and-tenon joinery, grooved rails, and vertical tongue-and-groove slat infill
on all four sides. Add a slatted bottom with drainage gaps and Festool Domino connections
to the lower rails.
```

### Appearance

```
apply_appearance(species="cedar")
```

---

## How to Run

**Via MCP (recommended):** If you have the [Fusion 360 MCP add-in](../../mcp/README.md) configured, just ask Claude to run it.

**Manual:** Fusion 360 > Utilities > Scripts and Add-Ins > (+) > select this folder > Run

**Script:** [`WoodPlanterV2.py`](WoodPlanterV2.py)

---

## Dimensions

All exposed as User Parameters (Modify > Change Parameters):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `planter_length` | 60 in | Overall planter length |
| `planter_width` | 20 in | Overall planter width |
| `total_height` | 40 in | Total height including legs |
| `leg_below_body` | 10 in | Leg height below body |
| `leg_size` | 3 in | Leg cross-section, square |
| `rail_thickness` | 2 in | Rail thickness |
| `rail_height` | 3 in | Rail height |
| `tenon_depth` | 2 in | Tenon depth into mortise |
| `tenon_width` | 1.25 in | Tenon width |
| `tenon_height` | 1.25 in | Tenon height |
| `groove_width` | 0.375 in | Frame groove width |
| `groove_depth` | 0.375 in | Frame groove depth |
| `frame_tongue_thick` | 0.34 in | Tongue thickness for frame grooves |
| `bottom_thickness` | 0.75 in | Bottom panel thickness |
| `slat_width` | 4 in | Slat face width |
| `slat_thickness` | 0.5 in | Slat body thickness |
| `slat_tg_width` | 0.25 in | Slat-to-slat T&G width |
| `slat_tg_depth` | 0.25 in | Slat-to-slat T&G depth |
| `drainage_gap` | 0.25 in | Gap between bottom slats for drainage |
| `dm_bt_w` | 0.25 in | Bottom domino narrow dimension |
| `dm_bt_h` | 0.5 in | Bottom domino long dimension (spans Z interface) |
| `dm_bt_d` | 0.75 in | Bottom domino total mortise depth |

---

## Design

Features live inside their respective components. Cross-component CUT operations (leg mortises) live in root via assembly proxies. Opposite sides are created by mirror. Slat replication uses mirror template + independent rectangular patterns.

### Components and Features

| Component | Features |
|-----------|----------|
| **Legs** | FL leg extrude, X-face groove CUT, Y-face groove CUT, midplanes, mirror FL > FR, mirror [FL,FR] > BL,BR |
| **LongRails** | Front-lower rail + left tenon + mirror tenon + JOIN tenons + groove CUT, front-upper rail (same), midplane, mirror front pair > back pair |
| **ShortRails** | Left-lower rail + front tenon + mirror tenon + JOIN tenons + groove CUT, left-upper rail (same), midplane, mirror left pair > right pair |
| **Root** | 4 leg mortise CUTs + 2 rail domino CUTs via assembly proxies |
| **Slats** | Front template (body + T&G groove + T&G tongue + frame tongues), mirror > back, independent pattern front, independent pattern back, edge tongues + mirror, gap slats + mirror; same for left/right |
| **Bottom** | Template slat (runs along Y) + domino voids (front + mirror > back) + CUT slat + pattern slat/voids along X + CUT front/back rails via proxies |

### Modeling Sequence

1. **Legs** (Legs) — extrude FL leg post, CUT X-face groove, CUT Y-face groove, midplanes, mirror FL > FR then [FL,FR] > BL,BR
2. **Long rails** (LongRails) — front-lower rail body + left tenon (NewBody) + mirror tenon across X-mid + JOIN both tenons + groove CUT; front-upper rail (same pattern); mirror front pair > back pair
3. **Short rails** (ShortRails) — same as long rails but rotated 90 degrees, staggered tenon Z offset, mirror left > right
4. **Leg mortises** (root) — CUT each leg with its 4 adjacent rail proxies via Combine (tenon overlap creates mortise pockets automatically)
5. **Slats** (Slats) — front template + mirror > back + independent patterns + edge tongues + gap slats; left template + mirror > right + independent patterns + edge tongues + gap slats
6. **Bottom** (Bottom) — template slat along Y + domino voids at front/back mating faces + CUT slat + pattern along X + CUT front/back lower rails via assembly proxies

### Key Techniques

- **Combine-based M&T** — tenons are built as NewBody on the rail, JOINed into the rail body. At step 4, the rail (with tenons) is used as a Combine CUT tool against the leg — the tenon portions that overlap the leg create mortise pockets. One shape = perfect fit.
- **Tenon stagger** — long rail tenons at `long_t_zoff`, short rail tenons at `short_t_zoff` — prevents collision inside corner legs
- **Assembly proxies** — `body.createForAssemblyContext(occurrence)` enables cross-component CUT in root
- **Mirror template + independent pattern** — Fusion 360 cannot mirror a RectangularPatternFeature; mirror only the template features, then create separate patterns per side
- **Body patterns for slats** — parametric count via `floor(long_shoulder / slat_width)` expression — updates when dimensions change
- **Domino void bodies** — stadium-shaped NewBody at mating interface, symmetric-extruded so it penetrates both pieces. CUT from each piece (keepTool=True). Pattern voids alongside the patterned slats, then CUT rails via assembly proxies in root

---

## Customization

Change any parameter in Fusion 360's Change Parameters dialog. Key relationships:

- `long_shoulder` = `planter_length - 2 * leg_size` — rail length between legs
- `short_shoulder` = `planter_width - 2 * leg_size`
- `n_long_slats` = `floor(long_shoulder / slat_width)` — auto-updates
- `n_short_slats` = `floor(short_shoulder / slat_width)`
- `long_t_zoff` = `(rail_height - 2 * tenon_height) / 3` — stagger offset
- `short_t_zoff` = `2 * (rail_height - 2 * tenon_height) / 3 + tenon_height`
- `body_z` = `leg_below_body + rail_height` — slat visible area bottom
- `body_h` = `total_height - 2 * rail_height - leg_below_body` — slat visible height
- `n_bottom_slats` = `floor((long_shoulder + drainage_gap) / (bottom_thickness + drainage_gap))` — auto-updates
- `bottom_slat_spacing` = `bottom_thickness + drainage_gap` — X-axis pattern spacing
- `bottom_slat_length` = `planter_width - 2 * rail_thickness` — slat span across width

---

## Materials & Cut List

For the default 60"L x 20"W x 40"H planter:

| Part | Qty | Dimensions |
|------|-----|------------|
| Legs | 4 | 3" x 3" x 40" |
| Long rails | 4 | 54" x 2" x 3" (with tenons) |
| Short rails | 4 | 14" x 2" x 3" (with tenons) |
| Long slats | ~28 | 4" x 0.5" x 24" (with tongues) |
| Short slats | ~8 | 4" x 0.5" x 24" (with tongues) |
| Bottom slats | ~54 | 16" x 0.75" x 0.75" (with domino pockets) |
| Bottom dominos | ~108 | 0.25" x 0.5" x 0.75" (loose tenons) |
