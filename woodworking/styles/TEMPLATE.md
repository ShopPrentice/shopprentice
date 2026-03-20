# Style Guide Template

Copy this file to create a new furniture style guide. Fill in every section — the agent reads this during planning to determine how components should look, what joinery to prefer, and what details to add.

Style files answer: **"How should this piece look and feel?"**

They compose with type files. The type says "this chest needs a lid mechanism." The style says "use brass butt hinges, through dovetails at case corners, and tapered cleat ends."

---

## Overview

_One paragraph describing the style's origin, key visual characteristics, and design philosophy._

## Joinery Preferences

What joint type to use at each location. The agent picks from this table based on the connection type from the type file.

| Joint location | Preferred | Alternative | Avoid |
|---------------|-----------|-------------|-------|
| _Visible case corners_ | _Through dovetails_ | _Box joints_ | _Pocket screws_ |
| _Hidden structural_ | _Dominos_ | _M&T_ | _Nails_ |
| _Drawer front_ | _Half-blind dovetails_ | _Box joints_ | _Butt joint_ |
| _Panel in frame_ | _Floating in groove_ | _Tongue & groove_ | _Glued in_ |
| _Shelf to case_ | _Dado_ | _Shelf pins_ | _Cleats only_ |

## Edge Treatments

How edges and transitions should be finished.

| Element | Treatment | Parameter |
|---------|-----------|-----------|
| _Lid edges_ | _Edge banding with tapered profile_ | _banding_thick = 0.375 in_ |
| _Case top edge_ | _Small chamfer_ | _ch_d = 0.0625 in_ |
| _Foot arches_ | _Smooth arc_ | _arch_h = 2.5 in_ |
| _Cleat ends_ | _Tapered / angled cut_ | _taper_angle = 15 deg_ |

## Transitions

How components meet each other. This is where styles differ most visually.

| Transition | Treatment |
|-----------|-----------|
| _Case to base_ | _Applied base: foot boards wider than case, cove molding transition_ |
| _Lid to case_ | _Lid overhangs 1/4" on front and sides, flush at back (hinge edge)_ |
| _Drawer to case_ | _Flush front, 1/16" reveal gap all around_ |
| _Back panel_ | _Rabbeted into sides, flush with back edge_ |

## Proportions

Visual ratios and rules of thumb for this style.

| Ratio | Value | Note |
|-------|-------|------|
| _Foot height : total height_ | _1:6_ | _4" feet on 24" chest_ |
| _Lid overhang_ | _0.25 in_ | _Subtle, not a shelf_ |
| _Board thickness_ | _0.75 in_ | _Standard 4/4 stock_ |
| _Dovetail spacing_ | _1.25" tails, 4 per side_ | _Visible but not busy_ |
| _Base overhang_ | _0.5 in per side_ | _Wider than case_ |

## Hardware

What hardware this style uses and how it should look.

| Hardware | Specification | Aesthetic |
|---------|--------------|-----------|
| _Hinges_ | _Brass butt hinges_ | _Visible from back, traditional_ |
| _Pulls_ | _Turned wood knobs_ | _Simple mushroom shape_ |
| _Lid stay_ | _Brass chain or quadrant stay_ | _Functional, not decorative_ |
| _Catches_ | _None (gravity hold)_ | — |

## Materials

Preferred wood species and finish expectations for this style.

| Element | Species | Finish |
|---------|---------|--------|
| _Primary_ | _Cherry, walnut, or maple_ | _Oil or shellac_ |
| _Secondary (drawer sides, back)_ | _Poplar or pine_ | _Unfinished or light seal_ |
| _Panels (bottom, back)_ | _Plywood or solid_ | _Match primary_ |

## What NOT to Do

Anti-patterns for this style. The agent should avoid these.

- _Example: Don't use Euro concealed hinges — they're modern, not traditional_
- _Example: Don't leave edges sharp/square — always break edges with small chamfer_
- _Example: Don't use pocket screws for visible joints_
