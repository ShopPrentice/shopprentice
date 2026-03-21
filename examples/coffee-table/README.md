# Coffee Table

A parametric modern coffee table — 48"L x 24"W x 18"H with 1" thick top, 1.75" square legs, apron frame, lower shelf, and domino joinery at all connections.

![Coffee Table — iso top-right](screenshots/iso-top-right.png)

![Coffee Table — iso top-left](screenshots/iso-top-left.png)

<p float="left">
  <img src="screenshots/front.png" width="49%" />
  <img src="screenshots/right.png" width="49%" />
</p>

### Transparent Views

All bodies at 0.15 opacity — reveals domino mortise pockets at every apron-to-leg joint.

<p float="left">
  <img src="screenshots/transparent-iso-top-left.png" width="49%" />
  <img src="screenshots/transparent-iso-top-right.png" width="49%" />
</p>

## Example Prompt

```
/woodworking
Build a modern coffee table: 48"L x 24"W x 18"H, 1" thick top,
1.75" square legs, apron frame, lower shelf, domino joinery. All parametric.
```

### Appearance

```
apply_appearance(species="walnut")
```

---

## How to Run

**Via MCP (recommended):** If you have the [Fusion 360 MCP add-in](../../mcp/README.md) configured, just ask Claude to run it.

**Manual:** Fusion 360 > Utilities > Scripts and Add-Ins > (+) > select this folder > Run

**Script:** [`coffee_table.py`](coffee_table.py)

---

## Dimensions

| Parameter | Default | Description |
|-----------|---------|-------------|
| `table_l` | 48 in | Overall length |
| `table_w` | 24 in | Overall width |
| `table_h` | 18 in | Overall height |
| `top_thick` | 1 in | Top board thickness |
| `leg_size` | 1.75 in | Leg cross-section |
| `apron_h` | 3 in | Apron height |
| `apron_thick` | 0.75 in | Apron thickness |
| `shelf_thick` | 0.75 in | Lower shelf thickness |
| `shelf_z` | 3 in | Shelf height from floor |
| `dm_t` | 8 mm | Domino cutter diameter |
| `dm_w` | 22 mm | Domino width |
| `dm_d` | 20 mm | Domino depth per side |
| `dm_count` | 2 | Dominos per apron end |

---

## Design

### Components (10 structural + 16 domino voids)

| Component | Bodies | Features |
|-----------|--------|----------|
| **Legs** | 4 | FL, FR (mirror), BL (mirror), BR (mirror) |
| **Aprons** | 4 | Front, Back (mirror), Left, Right (mirror) |
| **Top** | 1 | Solid panel on leg frame |
| **Shelf** | 1 | Lower shelf between legs |
| **Root** | 16 | Domino void bodies at all 8 apron-to-leg joints (2 per joint) |

### Key Techniques

- **Domino grid joinery** — 2 dominos per apron end, evenly spaced along the apron height. Stadium-shaped void bodies CUT mortise pockets into both the apron and leg. Uses `domino.grid()` template.
- **Mirror symmetry** — build one leg, one long apron, one short apron; mirror for the rest.
