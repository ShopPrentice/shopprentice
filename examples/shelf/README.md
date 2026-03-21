# Floating Shelf

A parametric modern floating shelf — 36"L x 8"D x 1.5" thick. Hollow shell construction (top, bottom, end caps) slides over a hidden wall-mounted cleat.

![Floating Shelf — iso top-right](screenshots/iso-top-right.png)

<p float="left">
  <img src="screenshots/front.png" width="49%" />
  <img src="screenshots/right.png" width="49%" />
</p>

### Transparent Views

<p float="left">
  <img src="screenshots/transparent-iso-top-left.png" width="49%" />
  <img src="screenshots/transparent-iso-top-right.png" width="49%" />
</p>

## Example Prompt

```
/woodworking
Build a modern floating shelf: 36" long x 8" deep x 1.5" thick.
Wall-mounted via hidden cleat. Clean square edges, all parametric.
```

### Appearance

```
apply_appearance(species="walnut")
```

---

## How to Run

**Via MCP (recommended):** If you have the [Fusion 360 MCP add-in](../../mcp/README.md) configured, just ask Claude to run it.

**Manual:** Fusion 360 > Utilities > Scripts and Add-Ins > (+) > select this folder > Run

**Script:** [`floating_shelf.py`](floating_shelf.py)

---

## Dimensions

| Parameter | Default | Description |
|-----------|---------|-------------|
| `shelf_l` | 36 in | Overall length |
| `shelf_d` | 8 in | Overall depth |
| `shelf_thick` | 1.5 in | Overall thickness |
| `board_thick` | 0.25 in | Shell wall thickness |

### Derived

| Parameter | Expression | Description |
|-----------|------------|-------------|
| `cleat_h` | `shelf_thick - 2 * board_thick` | Cleat height (fills cavity) |
| `cleat_d` | `shelf_d - board_thick` | Cleat depth (stops short of front) |
| `cleat_l` | `shelf_l - 2 * board_thick` | Cleat length (fits between caps) |

---

## Design

### Components (5 bodies)

| Component | Bodies | Features |
|-----------|--------|----------|
| **Shelf** | 4 | Top, Bottom, Cap_Left, Cap_Right — hollow shell |
| **Cleat** | 1 | Wall-mount strip fitting inside shelf cavity |

### Key Techniques

- **Hollow shell** — top/bottom boards + end caps form a box. The front edge is open (no front board) so the shelf slides over the cleat from the front.
- **Hidden cleat** — cleat is shorter than the cavity in all dimensions, positioned against the back wall. Screwed to wall studs, invisible when shelf is mounted.
- **Parametric thickness** — changing `shelf_thick` adjusts all internal dimensions. The cleat always fills the cavity height.
