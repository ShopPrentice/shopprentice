# Classic Ming-Style Side Table

A parametric side table inspired by classical Chinese Ming-dynasty furniture, modeled in Fusion 360 via Python script. 28"L x 13.75"D x 30.875"H. Round splayed legs, a floating frame-and-panel top, a mid shelf, carved spandrel brackets under the apron, and **hidden (full-blind) dovetails at all four apron corners** — the joinery is completely concealed, reading as clean miters from the outside.

![Ming Table — iso top-right](screenshots/iso-top-right.png)

![Ming Table — iso top-left](screenshots/iso-top-left.png)

<p float="left">
  <img src="screenshots/front.png" width="49%" />
  <img src="screenshots/right.png" width="49%" />
</p>

## Example Prompt

```
/woodworking
Build a classic Ming-style side table, 28"L x 13.75"D x 30.875"H, with round 1-3/8"
legs splayed 1.5 degrees, a floating frame-and-panel top with sliding-dovetail battens,
an apron band with carved spandrel brackets, a floating frame-and-panel mid shelf coped
into the legs, and a hollow spline edge profile on the top frame. Join the short aprons
to the long aprons with hidden full-blind dovetails at all four corners. Fully parametric.
```

### Appearance

```
apply_appearance(species="cherry")
```

---

## How to Run

**Via MCP (recommended):** If you have the [Fusion 360 MCP add-in](../../mcp/README.md) configured, just ask Claude to run it.

**Manual:** Fusion 360 > Utilities > Scripts and Add-Ins > (+) > select this folder > Run

**Script:** [`ming_table.py`](ming_table.py)

---

## Dimensions

All exposed as User Parameters (Modify > Change Parameters):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `table_l` | 28 in | Overall table length (X) |
| `table_d` | 13.75 in | Overall table depth (Y) |
| `table_h` | 30.875 in | Overall height, floor to top surface |
| `splay` | 1.5 deg | Leg splay/rake angle from vertical, per axis |
| `tf_t` | 0.6875 in | Top-frame stock thickness (vertical) |
| `tf_w` | 2 in | Top-frame member width |
| `panel_t` | 0.3125 in | Top-panel thickness |
| `tongue_ov` | 0.25 in | Panel tongue protrusion into the frame groove |
| `tf_cham_d` | 0.104 in | Top-frame edge-profile depth (inward from outer face) |
| `tf_cham_h` | tf_t | Top-frame edge-profile height (up from bottom face) |
| `leg_dia` | 1.375 in | Leg diameter (round leg) |
| `leg_setback_x` | 5.375 in | Distance each leg is set in from the table END (X) |
| `leg_setback_y` | 1.125 in | Distance each leg is set in from the table SIDE (Y) |
| `leg_embed` | 0.5 in | How far the leg top embeds up into the frame |
| `apron_t` | 0.375 in | Apron stock thickness |
| `apron_w` | 1.125 in | Apron height (band width) |
| `fbd_lip` | 0.1 in | Hidden-dovetail lip thickness |
| `fbd_pad` | 0.1 in | Hidden-dovetail end padding |
| `fbd_angle` | 10 deg | Hidden-dovetail flank angle |
| `fbd_tail_w` | 0.225 in | Dovetail tail width at the wide face |
| `fbd_tail_count` | 3 | Number of dovetail tails per corner |
| `spandrel_depth` | 3 9/16 in | Spandrel vertical extent below the apron |
| `shelf_z` | 20 in | Shelf top height above the floor |
| `sf_t` | 0.875 in | Shelf-frame stock thickness |
| `sf_w` | 1.375 in | Shelf-frame member width |
| `sp_panel_t` | 0.3125 in | Shelf-panel thickness |
| `bt_w` | 0.875 in | Top-batten width |
| `bt_off` | 7 in | Top-batten offset from center (+/-) |
| `bt_dt_base` | 0.5 in | Batten dovetail base width (narrow side) |
| `bt_dt_top` | 0.75 in | Batten dovetail top width (wide side) |

### Derived Parameters

| Parameter | Expression | Description |
|-----------|------------|-------------|
| `tf_bot` | `table_h - tf_t` | Z of the frame underside |
| `ltx` | `table_l / 2 - leg_setback_x` | Leg half-spread in X (legs at ±ltx) |
| `lty` | `table_d / 2 - leg_setback_y` | Leg half-spread in Y (legs at ±lty) |
| `leg_tip_z` | `tf_bot + leg_embed` | Z of the leg top |
| `fbd_socket` | `apron_t - fbd_lip` | Tail penetration depth into the long apron |
| `fbd_narrow_w` | `fbd_tail_w - 2 * fbd_socket * tan(fbd_angle)` | Tail narrow width |
| `fbd_pitch` | `(apron_w - 2 * fbd_pad) / fbd_tail_count` | Tail pitch (centered field) |

---

## Design

### Components and Features

| Component | Features |
|-----------|----------|
| **Legs** | FL round leg swept with 1.5° splay, top embedded into the frame; mirror to all 4 |
| **Top** | Frame-and-panel: 4 mitered frame members grooved for a floating panel, panel with one-shoulder tongues, two sliding-dovetail battens underneath; hollow spline edge profile cut on all 4 outer bottom edges |
| **Aprons** | Long-apron band + carved spandrel brackets joined via internal 1/8" tongues; short aprons lofted between the long-apron miter faces; hidden full-blind dovetails at all 4 corners |
| **Shelf** | Frame-and-panel mid shelf, rails coped (rounded shoulder) and M&T into the round legs, floating panel with a sliding-dovetail batten |

### Key Techniques

- **Hidden (full-blind) dovetail** — the marquee joint. Tails on the short aprons drop into sockets in the long aprons behind a concealing end lip, so nothing shows from outside. Built once on the front-left corner and **mirrored to all four**: lip mirrored to every corner and JOINed to the long aprons, tails built on one end + mirrored to the other, then the short apron mirrored left→right; the long aprons are finally CUT by the short aprons to carve the sockets.
- **Splayed round legs** — each leg is swept along a raked centerline (1.5° per axis), so it leans out toward the floor; positions are derived so the apron and shelf track the lean parametrically.
- **Floating frame-and-panel** (top and shelf) — grooved frames with one-shoulder panel tongues; sliding-dovetail battens keep the panels flat while allowing wood movement.
- **Spandrel brackets** — carved brackets under the apron, joined to the band with internal tongues so the apron + spandrels act as one member at each corner.
- **Spline edge profile** — a custom fitted-spline cutter sweeps a hollow molding along the top-frame outer bottom edge (cut on one edge, mirrored to all four).
- **Mirror-based replication** — symmetric parts (legs, frame members, aprons, shelf rails, battens, dovetails) are built once and mirrored, so the whole piece rebuilds from a single corner's geometry.

---

## Customization

Change any parameter in Fusion 360's Change Parameters dialog. Key relationships:

- `ltx = table_l / 2 - leg_setback_x` and `lty = table_d / 2 - leg_setback_y` — leg spread tracks the overall size and setbacks automatically.
- `fbd_socket = apron_t - fbd_lip` — tail depth follows apron thickness so the lip always conceals the joint.
- `fbd_pitch = (apron_w - 2 * fbd_pad) / fbd_tail_count` — the dovetail field stays centered in the apron height; change `fbd_tail_count` to add or remove tails.
- `leg_tip_z = tf_bot + leg_embed` — the leg top embeds a fixed amount into the frame regardless of height.

Changing `splay` re-rakes the legs and the derived apron/shelf positions follow. Changing `leg_dia`, `apron_w`, or `fbd_tail_count` updates the joinery proportions automatically.
