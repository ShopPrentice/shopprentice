# Drawbore Mortise & Tenon

## Overview

A **drawbore joint** is a mortise and tenon reinforced with offset wooden pins. The pin holes in the tenon are drilled slightly closer to the shoulder than the holes in the mortise cheeks. When the tapered pin is driven through, it pulls the tenon tight into the mortise, creating a permanent mechanical lock that needs no clamps or glue to stay tight.

**When to use:** Stretcher-to-leg joints, workbench construction, timber framing, trestle tables, any structural M&T joint where long-term tightness is critical. Both through and blind tenon variants work with drawbore pins.

**Strength:** Very high. The offset pins create a permanent draw force that keeps the shoulder tight. Even if glue fails, the mechanical lock holds. Two pins per tenon is standard for stretcher-width joints.

## Variants

| Variant | Description |
|---------|-------------|
| Through drawbore | Tenon extends through mortise piece (+ proud), pins visible on both cheeks |
| Blind drawbore | Tenon stops inside mortise piece, pins visible on outer cheeks only |

## Parameters

| Parameter | Expression | Unit | Description |
|-----------|------------|------|-------------|
| `db_tw` | `"ls_w"` | `"in"` | Tenon width (typically full stretcher height) |
| `db_tt` | `"1.5 in"` | `"in"` | Tenon thickness (narrower than stretcher) |
| `db_depth` | `"leg_w + ls_proud"` | `"in"` | Tenon depth (through leg + proud, or blind) |
| `db_pin_dia` | `"0.375 in"` | `"in"` | Pin diameter (3/8" standard) |
| `db_pin_sp` | `"2 in"` | `"in"` | Vertical spacing between 2 pins |

## Build Workflow

The drawbore follows the standard combine-based joinery pattern with an extra pin step:

1. **Build stretcher body** — full cross-section, between inner leg faces
2. **Sketch tenon** on construction plane at the outer end of the tenon (proud face for through, blind stop for blind). Extrude inward toward the stretcher end. The default extrude direction (+normal) goes toward the stretcher body.
3. **Sketch drawbore pins** on a perpendicular construction plane. Pin center at 1/3 of tenon depth from the shoulder. Two circles spaced `db_pin_sp` apart, centered on the tenon height. Extrude through the full mortise piece depth.
4. **Mirror** tenon + pins to the other end of the stretcher
5. **JOIN** all tenons to the stretcher body
6. **CUT** tenons with pin bodies (creates pin holes through the tenon)
7. **Mirror** the entire stretcher assembly for the opposite side (e.g., front to back)

### Pin Positioning Rule

The pin is always at **1/3 of the tenon length from the shoulder** (inner face of the mortise piece). This places the pin where it has maximum draw force while keeping enough wood between the pin and the mortise opening.

- Through tenon: pin at `leg_w / 3` from the inner face
- Blind tenon: pin at `(leg_d - st_blind) / 3` from the inner face

### Pin Direction

The pin axis must be **perpendicular to the tenon**:

| Tenon Direction | Pin Direction | Sketch Plane |
|-----------------|---------------|--------------|
| X (long stretcher) | Y (through leg cheek) | XZ plane |
| Y (short stretcher) | X (through leg side) | YZ plane |

### Construction Plane for Tenon (Extrude Direction)

Place the construction plane at the **outer end** of the tenon (not at the stretcher end face). This ensures the default extrude direction goes inward toward the stretcher:

- Through tenon: plane at `leg_setback - ls_proud` (proud face), extrude +X by `leg_w + ls_proud`
- Blind tenon: plane at `st_blind` (blind stop), extrude +Y by `leg_d - st_blind`

This avoids needing to flip the extrude direction.

### Profile Selection

When the tenon height equals the stretcher height (full-width tenon), sketching on the stretcher end face causes coincident edges. Use a **construction plane** instead of the face to avoid this. The construction plane sketch has exactly one profile.

## Example

```python
from woodworking.templates import drawbore as db

# Define parameters
db.define_params(params, prefix="db",
    tenon_w="ls_w", tenon_thick="1.5 in",
    pin_dia="0.375 in", pin_sp="2 in")

# Through drawbore at left end of stretcher
db.through(ls_c,
    plane_expr="leg_setback - ls_proud",        # outer end
    plane_base=root.yZConstructionPlane,
    tenon_origin=("leg_setback - ls_proud",
                   "(leg_d - db_tt) / 2", "ls_z"),
    tenon_size={"y": "db_tt", "z": "db_tw"},
    depth_expr="leg_w + ls_proud",
    pin_plane_base=root.xZConstructionPlane,     # perpendicular to tenon
    pin_depth_expr="leg_w / 3",                  # 1/3 from shoulder
    pin_x_expr="leg_setback + 2 * leg_w / 3",
    pin_z_ctr_expr="ls_z + ls_w / 2",
    pin_through_expr="leg_d",
    stretcher_body=ls_front,
    name="DB_L", ev=ev)
```

## Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| Pin goes along tenon instead of through cheek | Sketch plane normal parallel to tenon | Use perpendicular plane: XZ for X-tenons, YZ for Y-tenons |
| Tenon extrudes into stretcher body | Default direction points away from leg | Place construction plane at outer end, extrude inward |
| Coincident edges on end face sketch | Tenon height = stretcher height | Use construction plane instead of face sketch |
| Pin too close to mortise opening | Fixed offset instead of proportional | Use 1/3 of tenon depth from shoulder |
