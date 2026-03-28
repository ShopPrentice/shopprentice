# TV Console

A parametric TV console modeled in Fusion 360 via Python script. 60"W x 18"D, dovetailed case with 3-drawer center section and side door panels with flush-mount McMaster-Carr brass hinges, M&T leg frame with interlocking tenons, cleats connecting case to frame with blind tenons and Festool Domino joints.

![TV Console — iso top-left](screenshots/iso-top-left.png)

![TV Console — iso top-right](screenshots/iso-top-right.png)

<p float="left">
  <img src="screenshots/front.png" width="49%" />
  <img src="screenshots/right.png" width="49%" />
</p>

### Full Transparent Views

All bodies at 0.15 opacity — reveals internal joinery, mortise pockets, and hidden connections.

<p float="left">
  <img src="screenshots/transparent-iso-top-left.png" width="49%" />
  <img src="screenshots/transparent-iso-bottom-right.png" width="49%" />
</p>

### Joinery Detail — Frame + Cleats

Interlocking M&T at leg corners, cleat blind tenons through rails, domino loose tenons at cleat-to-case interface.

<p float="left">
  <img src="screenshots/frame-detail-iso-top-left.png" width="49%" />
  <img src="screenshots/frame-detail-iso-bottom-right.png" width="49%" />
</p>

### Joinery Detail — Case Dovetails + Hinges

Through dovetails at case corners. Flush-mount brass hinges with gap-aware rebate mortises on inset doors.

<p float="left">
  <img src="screenshots/detail-dovetail-corner.png" width="49%" />
  <img src="screenshots/detail-door-hinge.png" width="49%" />
</p>

### Joinery Detail — Divider Dominos + Drawers

Domino loose tenons connecting dividers to top and bottom boards. Half-blind dovetails at drawer fronts, through dovetails at backs.

<p float="left">
  <img src="screenshots/detail-divider-dominos.png" width="49%" />
  <img src="screenshots/detail-drawer-dovetails.png" width="49%" />
</p>

### Joinery Detail — Cleat Dominos + Case Bottom

Domino voids straddling the cleat top / case bottom interface. Case dovetails and back rabbet visible.

<p float="left">
  <img src="screenshots/detail-cleat-dominos.png" width="49%" />
  <img src="screenshots/case-detail-iso-top-right.png" width="49%" />
</p>

## Example Prompt

```
/woodworking
Build a TV console: 60"W x 18"D, 12" case height on a 6" leg frame. Dovetailed case
(top, bottom, sides) with 3 center drawers and side door panels. M&T leg frame with
interlocking tenons at corners. Cleats connecting case to frame with blind tenons through
rails and Festool Domino joints into the case bottom. All joinery fully parametric.
```

### Appearance

Multi-species: white oak case and frame with ziricote drawer fronts.

```python
sp.apply_appearance("white oak")
sp.apply_appearance("ziricote", bodies=["dd_Front", "dd_Front (1)", "dd_Front (2)"])
```

---

## How to Run

**Via MCP (recommended):** If you have the [Fusion 360 MCP add-in](../../mcp/README.md) configured, just ask Claude to run it.

**Manual:** Fusion 360 > Utilities > Scripts and Add-Ins > (+) > select this folder > Run

**Script:** [`tv_console.py`](tv_console.py)

---

## Dimensions

All exposed as User Parameters (Modify > Change Parameters):

### Envelope

| Parameter | Default | Description |
|-----------|---------|-------------|
| `console_w` | 60 in | Overall width |
| `console_d` | 18 in | Overall depth |
| `case_h` | 12 in | Case interior height |
| `leg_h` | 6 in | Leg height below case |
| `frame_gap` | 0.25 in | Gap between frame top and case bottom |

### Case Boards

| Parameter | Default | Description |
|-----------|---------|-------------|
| `board_thick` | 0.75 in | Case board thickness |
| `back_thick` | 0.375 in | Back panel thickness |
| `n_sections` | 3 | Number of sections |
| `divider_thick` | 0.75 in | Divider thickness |

### Frame

| Parameter | Default | Description |
|-----------|---------|-------------|
| `leg_size` | 1.5 in | Leg cross-section |
| `rail_w` | 2.5 in | Rail width (height) |
| `rail_thick` | 0.75 in | Rail thickness |

### M&T Joinery

| Parameter | Default | Description |
|-----------|---------|-------------|
| `mt_tw` | 2 in | Tenon width |
| `mt_tt` | 0.375 in | Tenon thickness |
| `mt_td` | 1 in | Tenon depth |

### Cleats

| Parameter | Default | Description |
|-----------|---------|-------------|
| `cleat_w` | 1.25 in | Cleat width |
| `cleat_thick` | 2.5 in | Cleat thickness (height) |
| `tt_shoulder` | 0.25 in | Cleat tenon shoulder |

### Dominos (Cleat-to-Case)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `dm_cl_short` | 8 mm | Domino cutter diameter |
| `dm_cl_long` | 40 mm | Domino long dimension |
| `dm_cl_depth` | 20 mm | Domino depth per side |
| `dm_cl_count` | 3 | Dominos per cleat |

### Drawers

| Parameter | Default | Description |
|-----------|---------|-------------|
| `n_drawers` | 3 | Number of drawers |
| `drawer_gap` | 0.0625 in | Drawer clearance gap |
| `drawer_front_thick` | 0.75 in | Drawer front thickness |
| `drawer_side_thick` | 0.5 in | Drawer side thickness |
| `drawer_bottom_thick` | 0.25 in | Drawer bottom thickness |

### Doors

| Parameter | Default | Description |
|-----------|---------|-------------|
| `door_thick` | 0.75 in | Door panel thickness |
| `door_gap` | 0.0625 in | Door inset gap |

### Door Hinges

| Parameter | Default | Description |
|-----------|---------|-------------|
| `door_gap` | 0.0625 in | Door reveal gap (hinge rebate auto-computed) |

Hinges are McMaster 1603A3 brass butt hinges, auto-selected by `recommend_hinge()` based on door height. Installed at 1/4 and 3/4 of case height on each door.

### Case Dovetails

| Parameter | Default | Description |
|-----------|---------|-------------|
| `dt_angle` | 8 deg | Dovetail angle |
| `dt_tail_w` | 1.5 in | Tail width |
| `dt_tail_count` | 4 | Tails per corner |

---

## Design

### Components (48 bodies total)

| Component | Bodies | Features |
|-----------|--------|----------|
| **Case** | 7 | Top, Bottom, Left, Right, Back, 2 Dividers. Through dovetails at corners, back rabbet. |
| **Frame** | 8 | 4 Legs, Front/Back Rails, 2 Side Rails. Interlocking M&T at all 4 corners. |
| **Drawers** | 15 | 3 drawer boxes (5 bodies each). Half-blind dovetails at front, through at back, bottom grooves. |
| **Doors** | 2 | Left + Right inset door panels (mirror). Flush-mount McMaster 1603A3 brass hinges with gap-aware rebate mortises. |
| **Cleats** | 4 | 4 cleats with blind tenons through front/back rails. |
| **Root** | 12 | 12 domino loose tenons (3 per cleat) connecting cleats to case bottom. |

### Key Techniques

- **Interlocking tenons** — When perpendicular tenons collide inside a leg, complementary notches let them weave past each other at full depth. Front/back rail: center half removed. Side rail: top + bottom quarters removed. Full bonding surface preserved.
- **Blind cleat tenons** — Tenon straddles the rail-cleat boundary, extending half into the rail (hidden from outside) and shoulder-depth into the cleat body for JOIN overlap.
- **Domino loose tenons** — Stadium-shaped void bodies straddling the cleat-top / case-bottom interface. Each domino CUTs mortise pockets into both the cleat and bottom board with `keepTool=True`.
- **Through dovetails** — Independent construction at each case corner (not mirrored) for correct CUT/JOIN targeting.
- **Dovetailed drawer boxes** — Half-blind dovetails at front (hides end grain), through dovetails at back, bottom panel in grooves cut before dovetails (implicit stopped grooves).
- **Wood grain direction** — Every joint designed with grain direction in mind. Fibers parallel to longest dimension; all connections use mechanical interlock (M&T, domino, dovetail) rather than relying on weak end-grain-to-side-grain glue bonds.
- **Door hinges** — McMaster 1603A3 brass butt hinges installed via `hardware.install_butt_hinge()` with `door_flush` style and 1/16" reveal gap. Geometry-based rebate mortises auto-sized to leaf overlap, open at the front edge. Left and right doors get symmetric cuts (offset direction auto-detected).

### Screenshot Techniques

Joinery detail views use Fusion 360's body opacity API:
- `body.opacity = 0.2` — semi-transparent (case boards, frame)
- `occ.isLightBulbOn = False` — hide entire component
- Domino/tenon bodies at full opacity stand out against transparent surroundings
