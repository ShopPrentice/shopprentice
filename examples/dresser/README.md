# 3-Drawer Solid Wood Dresser

A parametric solid wood dresser modeled in Fusion 360 via Python script. 48"W x 20"D x 34"H, 3/4" board stock. Through dovetail case joints, dovetailed drawer boxes (half-blind front, through back) with integrated lip/groove pulls, plinth kick base with Festool Domino joints, and a plywood back panel.

![Dresser — iso top-right](screenshots/iso-top-right.png)

![Dresser — iso top-left](screenshots/iso-top-left.png)

<p float="left">
  <img src="screenshots/front.png" width="49%" />
  <img src="screenshots/right.png" width="49%" />
</p>

### Full Transparent Views

All bodies at 0.15 opacity — reveals drawer boxes, domino voids, and internal joinery.

<p float="left">
  <img src="screenshots/transparent-iso-top-left.png" width="49%" />
  <img src="screenshots/transparent-iso-top-right.png" width="49%" />
</p>

### Joinery Detail — Drawer Dovetails

Single drawer box isolated. Half-blind dovetails at front (hides end grain), through dovetails at back, bottom panel in grooves.

![Drawer dovetail detail](screenshots/detail-drawer-dovetails.png)

### Joinery Detail — Case Dovetails + Kick Dominos

Through dovetails joining top and bottom boards to left side. Kick-to-bottom domino loose tenons at each kick board interface.

<p float="left">
  <img src="screenshots/detail-case-dovetails.png" width="49%" />
  <img src="screenshots/detail-kick-dominos.png" width="49%" />
</p>

## Example Prompt

```
/woodworking
Build a 3-drawer solid wood dresser: 48"W x 20"D x 34"H in 3/4" stock. Through dovetails
joining top and bottom to sides, 3 dovetailed drawer boxes (half-blind front, through back)
with integrated lip/groove pulls, plinth kick base with Festool Domino joints, and 1/4"
plywood back. All joinery fully parametric — changing n_drawers should produce any number
of equal-height drawers.
```

### Appearance

```
apply_appearance(species="cherry")
```

---

## How to Run

**Via MCP (recommended):** If you have the [Fusion 360 MCP add-in](../../mcp/README.md) configured, just ask Claude to run it.

**Manual:** Fusion 360 > Utilities > Scripts and Add-Ins > (+) > select this folder > Run

**Script:** [`dresser.py`](dresser.py) — uses `dovetailed_drawer` template for drawer boxes.

---

## Dimensions

All exposed as User Parameters (Modify > Change Parameters):

### Case

| Parameter | Default | Description |
|-----------|---------|-------------|
| `case_w` | 48 in | Overall case width (X) |
| `case_d` | 20 in | Overall case depth (Y) |
| `case_h` | 34 in | Overall case height (Z) |
| `board_thick` | 0.75 in | Side board thickness |
| `top_thick` | 0.75 in | Top board thickness |
| `bot_thick` | 0.75 in | Bottom board thickness |
| `kick_h` | 4 in | Kick board height |
| `kick_inset` | 1 in | Kick inset from case front |
| `back_thick` | 0.25 in | Back panel thickness |
| `top_overhang` | 0 in | Top overhang beyond sides |

### Case Dovetails

| Parameter | Default | Description |
|-----------|---------|-------------|
| `dt_angle` | 8 deg | Dovetail angle |
| `dt_tail_w` | 1 in | Dovetail tail width |
| `dt_tail_count` | 6 | Number of tails per corner |

### Drawers

| Parameter | Default | Description |
|-----------|---------|-------------|
| `n_drawers` | 3 | Number of drawers |
| `drawer_gap` | 0.125 in | Gap around each drawer |
| `dd_ft` | 0.75 in | Drawer front board thickness |
| `dd_st` | 0.5 in | Drawer side/back board thickness |
| `dd_bt` | 0.25 in | Drawer bottom thickness |
| `pull_depth` | 0.375 in | Lip/groove pull depth |
| `pull_h` | 0.75 in | Pull groove height |

### Drawer Dovetails (via `dovetailed_drawer` template)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `hbd_dd_angle` | 8 deg | Half-blind dovetail angle (front) |
| `hbd_dd_tw` | 0.75 in | Half-blind tail width |
| `hbd_dd_tc` | 5 | Tails per front corner |
| `dt_dd_angle` | 8 deg | Through dovetail angle (back) |
| `dt_dd_tw` | 0.75 in | Through tail width |
| `dt_dd_tc` | 5 | Tails per back corner |

### Kick Dominos

| Parameter | Default | Description |
|-----------|---------|-------------|
| `dm_kc_d` | 12 mm | Kick corner domino depth per side |
| `dm_kc_h` | 1.5 in | Kick corner domino long dimension |
| `dm_kc_w` | 5 mm | Kick corner domino short dimension |
| `dm_kb_d` | 12 mm | Kick-to-bottom domino depth per side |
| `dm_kb_h` | 1.5 in | Kick-to-bottom domino long dimension |
| `dm_kb_w` | 5 mm | Kick-to-bottom domino short dimension |
| `dm_kb_f_count` | 3 | Front kick domino count |
| `dm_kb_s_count` | 2 | Side kick domino count |
| `dm_kb_b_count` | 3 | Back kick domino count |

---

## Design

### Components (38 bodies total)

| Component | Bodies | Features |
|-----------|--------|----------|
| **Sides** | 2 | Left + right side panels (mirror) |
| **Top** | 1 | Top board with overhang |
| **Bottom** | 1 | Bottom board between sides at top of kick |
| **Back** | 1 | Plywood back panel |
| **Kick** | 8 | Front, left, right, back plinth boards + 4 corner domino voids |
| **Drawers** | 15 | 3 drawers × 5 bodies (front, back, left, right, bottom) |
| **Root** | 10 | Kick-to-bottom domino loose tenon voids |

### Build Phases

**Phase 1:** Carcass structure — side boards (mirror), top, back, kick boards + corner dominos, bottom board, kick-to-bottom dominos, drawer boxes via `dovetailed_drawer` template + pull grooves

**Phase 2:** Case dovetails (top/bottom-to-sides) + back rabbets

### Key Techniques

- **Through dovetails (case)** — Independent construction at each of 4 case corners. Tails as NewBody, feature pattern along Y, bulk CUT side + JOIN horizontal board via assembly proxies.
- **Half-blind dovetails (drawer front)** — Via `dovetailed_drawer` template. Hides end grain on the drawer face — proper traditional construction.
- **Through dovetails (drawer back)** — Via `dovetailed_drawer` template. Visible from behind, shows craftsmanship.
- **Integrated lip/groove pulls** — Groove CUT into drawer front top edge, no hardware needed. Fingers hook underneath.
- **Parametric drawer count** — `n_drawers` controls height derivation; drawer body pattern along Z replicates all 5 bodies + joinery.
- **Domino joinery** — Loose tenon stadium-shaped voids span kick corner joints and kick-to-bottom interfaces. Full opacity in detail views for visibility.
- **Bottom panel grooves** — Grooved into all 4 drawer boards before dovetails are cut (implicit stopped grooves at corners).
- **Back rabbet** — Groove in each side board receives the plywood back panel.

---

## Customization

Changing `n_drawers` produces any number of equal-height drawers. Each drawer's height, position, and dovetail layout adjusts automatically. Key constraint chains:

- `dd_h = (usable_h - (n_drawers + 1) * drawer_gap) / n_drawers`
- `drawer_pitch = dd_h + drawer_gap`
- Drawer dovetail pin width derives from `dd_h / tail_count - tail_w`
