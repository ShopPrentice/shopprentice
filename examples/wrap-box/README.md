# Food Wrap Dispenser Box

A parametric food wrap dispenser box modeled in Fusion 360 via Python script. 14"L x 4"W x 3.5"H, 1/2" board stock. Through dovetails at all 4 corners, edge-rabbeted bottom and lid panels, slide-in lid, dispensing slot for film exit, and a cutter groove on a raised lip at the back.

![Wrap Box — iso top-right](screenshots/iso-top-right.png)

![Wrap Box — iso top-left](screenshots/iso-top-left.png)

<p float="left">
  <img src="screenshots/front.png" width="49%" />
  <img src="screenshots/right.png" width="49%" />
</p>

## Example Prompt

```
/woodworking
Build a food wrap dispenser box: 14"L x 4"W x 3.5"H in 1/2" stock. Through dovetails
at all 4 corners, edge-rabbeted bottom panel, slide-in lid with edge rabbets, dispensing
slot in front wall for film exit, and a raised cutter lip with groove on the back board.
3 tails per corner, all joinery fully parametric.
```

### Appearance

```python
sp.apply_appearance("teak")
```

---

## How to Run

**Via MCP (recommended):** If you have the [Fusion 360 MCP add-in](../../mcp/README.md) configured, just ask Claude to run it.

**Manual:** Fusion 360 > Utilities > Scripts and Add-Ins > (+) > select this folder > Run

**Script:** [`wrap_box.py`](wrap_box.py)

---

## Dimensions

All exposed as User Parameters (Modify > Change Parameters):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `box_length` | 14 in | Overall box length (X) |
| `box_width` | 4 in | Overall box width (Y) |
| `box_height` | 3.5 in | Overall box height (Z) |
| `board_thick` | 0.5 in | Case board thickness |
| `bottom_thick` | 0.25 in | Bottom panel total thickness |
| `lid_thick` | 0.375 in | Lid panel total thickness |
| `groove_depth` | 0.25 in | Tongue insertion depth into groove |
| `groove_up` | 0.125 in | Bottom panel rabbet offset from floor |
| `lid_down` | 0.2 in | Lid panel rabbet offset from top |
| `dt_angle` | 8 deg | Dovetail angle |
| `dt_tail_w` | 0.5 in | Dovetail tail width |
| `dt_tail_count` | 3 | Number of dovetail tails per corner |
| `cutter_size` | 0.375 in | Cutter track groove size |
| `cutter_lip_h` | 0.5 in | Cutter lip height above box top |
| `cutter_lip_depth` | 0.375 in | Cutter lip inward extension depth |
| `film_gap` | 0.015625 in | Gap between lid and front board for film exit |

### Derived Parameters

| Parameter | Expression | Description |
|-----------|------------|-------------|
| `bottom_tongue` | `bottom_thick - groove_up` | Bottom tongue height |
| `lid_tongue` | `lid_thick - lid_down` | Lid tongue height |
| `open_height` | `box_height - lid_thick` | Height below lid (dovetail zone) |
| `side_inner_len` | `box_width - 2 * board_thick` | Inner width between end boards |
| `dt_pin_w` | `open_height / dt_tail_count - dt_tail_w` | Dovetail half-pin width |
| `dt_pitch` | `open_height / dt_tail_count` | Dovetail pitch |
| `dt_narrow_w` | `dt_tail_w - 2 * board_thick * tan(dt_angle)` | Dovetail narrow face width |

---

## Design

### Components and Features

| Component | Features |
|-----------|----------|
| **Case** | Front board, mirror front to back, left end board, corner block JOIN on left end top, cutter lip JOIN on back top, cutter groove CUT on back top |
| **Bottom** | Full board at tongue footprint, front edge rabbet CUT (stopped), mirror to back, left edge rabbet CUT (through), mirror to right |
| **Lid** | Full board (no front/back tongue, clears cutter lip), left edge rabbet CUT (through), mirror to right |
| **Root** | Bottom panel CUTs into case boards (3), lid panel CUTs into case boards (3), mirror left end to right end, through dovetails at 4 corners (independent), film gap CUT |

### Key Techniques

- **Edge-rabbeted panels** — bottom and lid panels have rabbeted edges that form tongues fitting into grooves CUT by the panel body itself
- **Slide-in lid** — lid has no front or back tongue; slides in from the front through grooves in back + both end boards
- **Dispensing slot** — front wall CUT at top creates opening for film to exit
- **Cutter lip** — raised extension on back board holds a cutter groove on its top face
- **Mirror-then-dovetail** — front mirrors to back, left end mirrors to right AFTER groove CUTs (carrying grooves to the mirrored copy)
- **Independent corner dovetails** — each of 4 corners built separately (sketch + pattern + CUT + JOIN) because CUT/JOIN targets differ per corner

---

## Customization

Change any parameter in Fusion 360's Change Parameters dialog. Key relationships:

- `open_height = box_height - lid_thick` — dovetails span from floor to lid underside
- `dt_pin_w = open_height / dt_tail_count - dt_tail_w` — pins derive from available height and count
- Bottom and lid groove positions defined by `groove_up` and `lid_down` offsets
- Changing `dt_tail_count` adjusts all 4 corners' dovetail layouts automatically
