# Dovetailed Jewelry Chest

![Jewelry Chest](product_iso.png)

![Lid Open](product_open.png)

Parametric jewelry chest with through dovetails, frame-and-panel lid with spalted maple panels, 3 removable trays (1 upper + 2 lower), and support panels.

## Dimensions

| Parameter | Value | Description |
|-----------|-------|-------------|
| box_length | 14 in | Overall length (X) |
| box_width | 9 in | Overall depth (Y) |
| case_height | 5.25 in | Total height including lid |
| board_thick | 5/8 in | Case board thickness |
| tray_height | 1-5/8 in | Upper tray side height |
| tray_thick | 1/4 in | Tray side thickness |
| lower_tray_height | 1-7/8 in | Lower tray side height |
| bottom_full_thick | 1/2 in | Case bottom panel full thickness (rabbeted edges) |
| support_thick | 1/8 in | Front/back support panel thickness |

## Components (33 bodies)

- **Case** (6): End_L, End_R, Front, Back, Support_F, Support_B
- **Bottom** (1): Rabbeted panel — 1/4" tongue in grooves, 1/2" thick center
- **UpperTray** (6): Mitered sides, grooved bottom, divider with handle + arch notch
- **LowerTrays** (12): 2 side-by-side trays, mitered sides, grooved bottoms, dividers with handles + arch notches
- **Lid** (8): Rail_F, Rail_B, Stile_L, Stile_R, center Div, Panel_L, Panel_R, Pull

## Key Construction Details

- **Dovetails**: Through dovetails at all 4 corners, proud offset (Krenov-style)
- **Tray miters**: Chamfer-based 45° miter joints at tray corners
- **Tray grooves**: Bottom panels sit in grooves (if-it-fits-it-cuts)
- **Tray dados**: Dividers held in dados in front/back sides
- **Divider handles**: Extend above tray sides with arch-shaped finger notch below
- **Support panels**: 1/8" panels on front/back inner faces, replacing runners. Lower trays fit between them; upper tray sits on top.
- **Bottom panel**: Rabbeted edge design — thin tongue (1/4") fits in case groove, thicker center (1/2") extends below for rigidity
- **Lid frame**: Continuous groove approach — panel tongues and frame tenons share one groove

## Appearance

- White oak case, lid frame, trays (scale 12×12)
- Spalted maple lid panels via `helpers.veneer.apply_veneer_realsize` (12" × 7" real size, flipped bottom face)
- Ziricote pull
- See `APPEARANCE_NOTES.md` for the full recipe

## TODO

- Model the hemp twine cord wrapped around divider handles (needs Sweep along helix or coil feature)

## Reference

Design based on the jewelry chest from [Fine Woodworking issue #319](https://www.finewoodworking.com/2025/09/15/online-extras-from-fww-issue-319).
