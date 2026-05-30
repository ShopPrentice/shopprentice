# Wedged Through-Tenon Trestle Table

A parametric Fusion 360 model of **"The Versatile Trestle Table"** by Gary Rogowski
(Fine Woodworking, Sept/Oct 2010) — a knock-down trestle table whose signature joint
is a curved stretcher locked to the posts with **wedged through-tenons** (tusk wedges).
Tap the wedges out and the base disassembles flat. 54"L × 27"W × 29"H, white-oak base
with a walnut top, wedges, and drawbore pegs.

![Trestle Table — iso top-right](screenshots/iso-top-right.png)

![Trestle Table — iso top-left](screenshots/iso-top-left.png)

<p float="left">
  <img src="screenshots/front.png" width="49%" />
  <img src="screenshots/right.png" width="49%" />
</p>

## Joinery & details

- **Tusk through-tenons** — the curved stretcher's tenons pass through the posts and protrude;
  a tapered key drives down through each proud tenon, bearing on the post face and drawing the
  shoulder tight. The defining knock-down joint.
- **Twin drawbore tenons** post-to-foot (¼" walnut pegs), single pegged tenon post-to-cap.
- **Tabletop buttons** — shop-made wooden buttons with a tongue in an elongated cap slot, so the
  solid top moves across the grain while staying held down.
- **Battens** stiffening the top, each with a fixed center screw + two Y-slotted holes for movement.
- **Sculpted profiles** — arched stretcher, relieved feet, cap underside, rounded tenon noses, and
  the wedge crown are draggable fit-point splines (placed at the FW positions, free to fine-tune).

## Build notes

Every part is anchored to its parent's projected geometry (no origin-based coordinates) and every
sketch is fully constrained except sculpted spline interiors — `validate_design` passes connectivity,
interference, and the dependency-tree traceability checks. The base is built once on the left and
mirrored; the stretcher tenon and tusk wedge are built once and mirrored; battens and buttons are
patterned. See `model.json` for the dependency tree.

## Files

- `trestle_table.py` — the parametric build script
- `model.json` — dependency tree metadata
- `screenshots/` — product shots

## Example Prompt

> Build "The Versatile Trestle Table" by Gary Rogowski (Fine Woodworking, Sept/Oct 2010) as a fully
> parametric Fusion 360 model — knock-down trestle base, curved stretcher locked with wedged
> through-tenons, drawbore-pegged post joints, tabletop buttons, and battens.
