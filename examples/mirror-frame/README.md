# Mirror Frame

A parametric wall mirror frame — 24"W x 36"H mirror opening, 3" wide frame, 3/4" thick. Butt-joint corners with rabbeted inner back edge to hold glass and backing board.

![Mirror Frame — iso top-right](screenshots/iso-top-right.png)

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
Build a modern mirror frame: 24"W x 36"H mirror opening, 3" wide frame,
3/4" thick. Rabbeted inner edge for glass. Clean square profile.
```

### Appearance

```
apply_appearance(species="walnut")
```

---

## How to Run

**Via MCP (recommended):** If you have the [Fusion 360 MCP add-in](../../mcp/README.md) configured, just ask Claude to run it.

**Manual:** Fusion 360 > Utilities > Scripts and Add-Ins > (+) > select this folder > Run

**Script:** [`mirror_frame.py`](mirror_frame.py)

---

## Dimensions

| Parameter | Default | Description |
|-----------|---------|-------------|
| `mirror_w` | 24 in | Mirror opening width |
| `mirror_h` | 36 in | Mirror opening height |
| `frame_w` | 3 in | Frame board width |
| `frame_thick` | 0.75 in | Frame thickness (depth) |
| `rabbet_d` | 0.375 in | Rabbet depth into frame |
| `rabbet_w` | 0.375 in | Rabbet width (glass + backing space) |
| `glass_thick` | 0.125 in | Glass placeholder thickness |

---

## Design

### Components (5 bodies)

| Component | Bodies | Features |
|-----------|--------|----------|
| **Frame** | 4 | Bottom, Top (mirror), Left, Right (mirror). Rabbet cut on inner back edge. |
| **Glass** | 1 | Placeholder body in rabbet |

### Key Techniques

- **Rabbet via tooling body** — single rectangular body spanning the inner opening, CUTs all 4 frame pieces in sequence (keepTool on first 3, consumed on last)
- **Mirror for symmetry** — top mirrors bottom, right mirrors left
- **Glass placeholder** — thin body sitting in the rabbet, representing the actual glass
