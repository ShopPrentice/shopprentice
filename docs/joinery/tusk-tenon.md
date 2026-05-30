# Tusk Tenon (Knock-Down Through-Tenon)

## Overview

A **tusk tenon** is a through-tenon that protrudes past the receiver (leg or post), locked by a tapered wooden key driven perpendicular to the tenon. Unlike spreading wedges (`tenon_wedge`, which lock the tenon permanently), the tusk is **knock-down**: tap the key out to disassemble, tap it in to draw the shoulder tight. The key tapers thicker toward the drive direction, so driving it creates a cam action that pulls the shoulder against the receiver.

**When to use:** Trestle tables, knock-down furniture, timber frames, workbenches with removable stretchers, any through-tenon joint that needs to be disassembled and reassembled.

**Strength:** Very high. Mechanical lock via wedge action. Glue-free and re-tightenable. Historically used in Medieval and Arts & Crafts furniture.

## Variants

| Variant | Description |
|---------|-------------|
| Through (standard) | Tenon through receiver + proud, single tapered key |
| Mirrored | Same joint at both ends of a stretcher (mirror_plane) |

## Parameters

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `tk_tw` | `2 in` | in | Tenon width (across grain) |
| `tk_th` | `1.5 in` | in | Tenon height |
| `tk_proud` | `1 in` | in | Tenon protrusion past receiver |
| `tk_key_thin` | `0.25 in` | in | Key thickness at thin (entry) end |
| `tk_key_ang` | `8 deg` | deg | Key taper angle |
| `tk_key_blade` | `0.375 in` | in | Key blade width |
| `tk_key_len` | `6 in` | in | Key length along drive axis |
| `tk_key_taper` | (derived) | in | Key taper run = `tk_key_len * tan(tk_key_ang)` |

## Orientation

Canonical (rotate planes for other layouts):

| Axis | Direction | Role |
|------|-----------|------|
| X | Through | Tenon passes through receiver, protrudes proud |
| Y | Width | Tenon width, key blade width |
| Z | Drive | Key driven down to tighten |

The key sketch is in the through x drive plane (XZ). The bearing face of the key sits flush on the receiver's far face.

## Build Workflow

1. **Anchored tenon rectangle** on a plane at the shoulder face. Extrude through receiver + proud.
2. **CUT receiver** with tenon body (keepTool) to create the through-mortise.
3. **Tapered key** in the through x drive plane. Trapezoidal profile:
   - Bearing face (vertical): flush with receiver's far face
   - Bottom edge: `tk_key_thin` (thin end, entry direction)
   - Top edge: `tk_key_thin + tk_key_taper` (thick end, draws tight)
   - Extrude symmetric by `tk_key_blade / 2`
4. **CUT rail** with key body (keepTool) to create the angled mortise through the tenon.
5. **Mirror** tenon + key to the opposite end (optional). CUT mirrored receiver.
6. **JOIN** all tenons to rail. Keys remain as separate bodies.

## Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| Tenon tip severed by key mortise | Key blade width >= tenon width | Key blade MUST be narrower than tenon width — leaves side material |
| Shoulder doesn't draw tight | Key taper angle too shallow or wrong direction | Taper thicker toward top (+drive); 8 deg is standard |
| Key walks out under vibration | Key too short, no friction | Make key length >= 1.5x tenon height; add a slight crown or friction fit |
| Anchor grabs wrong corner | anchor_pt picks nearest projected endpoint | Aim key_anchor_xyz at the SPECIFIC receiver corner you want |

## Multi-Parent Dependency

The tusk key naturally has two parent references: it bears on the **receiver** (post/leg) far face AND rides in the **rail** (stretcher) tenon. In model.json, use multi-parent `refs`:

```json
{"body": "Wedge_L", "refs": ["Post_L", "Stretcher"], "contact": true}
```
