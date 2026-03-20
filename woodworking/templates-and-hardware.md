# Build Templates & Hardware Inventory

Reference for available reusable templates and hardware. Check this before writing inline code — if a template exists, use it.

## Build Templates (`addin/helpers/templates/`)

| Template | Import | Status | Used by |
|----------|--------|--------|---------|
| `dovetail` | `from helpers.templates import dovetail` | Tested | pencil-box, dresser, tv-console |
| `half_blind_dovetail` | `from helpers.templates import half_blind_dovetail` | Tested | tv-console, dresser (via drawer) |
| `dovetailed_drawer` | `from helpers.templates import dovetailed_drawer` | Tested | dresser, tv-console |
| `drawer_box` | `from helpers.templates import drawer_box` | Tested | — |
| `mortise_tenon` | `from helpers.templates import mortise_tenon` | Tested | wood-planter, rachel's-table |
| `domino` | `from helpers.templates import domino` | Tested | counter-stool, tv-console, dresser |
| `finger_joint` | `from helpers.templates import finger_joint` | Tested | — |
| `splayed_legs` | `from helpers.templates import splayed_legs` | Tested | counter-stool, stool-rebuild |
| `butt_hinge` | `from helpers.templates import butt_hinge` | Tested | tv-console |
| `pull` | `from helpers.templates import pull` | Draft | — |
| `chest_lock` | `from helpers.templates import chest_lock` | Draft | — |

## Hardware (`addin/helpers/hardware.py`)

| Hardware | Function | Status |
|----------|----------|--------|
| Butt hinge (McMaster catalog) | `hardware.install_butt_hinge()` | Tested |
| Screw holes | `hardware.cut_screw_holes()` | Tested |

## Needed Templates (by type)

| Template | Needed by types | Priority | Description |
|----------|----------------|----------|-------------|
| `applied_base` | chest, dresser, cabinet, sideboard | Phase 2 | Foot boards wider than case + arch cutouts + transition molding |
| `edge_banding` | chest, box | Phase 2 | Molding pieces around panel edges with profiled cross-section |
| `breadboard_ends` | chest, table, desk | Phase 2 | M&T with elongated slots for wood movement |
| `frame_and_panel` | cabinet, wardrobe, sideboard, door | Phase 2 | Frame with M&T + floating panel |
| `shelf_pins` | cabinet, bookshelf, wardrobe | Phase 2 | Adjustable shelf hole pattern |
| `bed_rail` | bed-frame | Phase 3 | Rail-to-post connection with bed bolt hardware |
| `slat_system` | bed-frame, bench | Phase 3 | Evenly spaced slats across rails |
| `spindle_pattern` | crib, chair | Phase 3 | Evenly spaced turned spindles |

## Needed Hardware (by type)

| Hardware | Needed by types | Priority | Source |
|----------|----------------|----------|--------|
| Euro concealed hinge | cabinet, wardrobe | Phase 2 | Blum/Grass catalog dims |
| Lid stay / chain | chest | Phase 2 | McMaster or generic |
| Drawer pull / knob | dresser, desk, cabinet, chest | Phase 2 | McMaster or generic cylinder |
| Catch / latch | cabinet, wardrobe, chest | Phase 2 | McMaster |
| Shelf pin holes | cabinet, bookshelf | Phase 2 | Standard 5mm pattern |
| Bed rail fastener | bed-frame | Phase 2 | Hook plate + strike plate pair — detachable rail-to-post connection |
| Bed bolt (IKEA-style) | bed-frame | Phase 2 | Barrel nut + bolt — alternative detachable connection |
| Soft-close drawer slide | desk, dresser, cabinet | Phase 3 | Generic side-mount |
