# Writing Desk

A parametric modern writing desk — 48"L × 24"W × 30"H with tapered legs, two dovetailed drawers with center divider, drawer runners and stops, front rail, cable grommet, L-bracket top attachment for wood movement. Walnut appearance.

![Desk — iso top-right](screenshots/iso-top-right.png)

<p float="left">
  <img src="screenshots/front.png" width="49%" />
  <img src="screenshots/right.png" width="49%" />
</p>

### Transparent View

<p float="left">
  <img src="screenshots/transparent-iso-top-left.png" width="49%" />
</p>

---

**Script:** [`desk.py`](desk.py) — 27 structural bodies + 18 domino voids.

### Structure
- **4 tapered legs** — 2" square at top, taper to 1.25" at floor on inner faces
- **3 aprons** — back + 2 sides (no front apron — drawer fronts fill it)
- **Front stretcher** — 1.5" rail below drawer openings
- **Center divider** — dado'd into front rail + back apron
- **2 drawer runners** — on side aprons (not divider — would block drawer slide)
- **2 drawer stops** — blocks at back of each runner
- **Top** — 1" thick with 2" cable grommet at back-right corner

### Drawers
- 2 dovetailed drawer boxes (half-blind front, through back)
- Each slides on wooden runners, stopped by blocks at back
- 5 bodies per drawer (10 total)

### Joinery
- **Aprons → legs:** 2 dominos per joint (6 apron joints)
- **Front stretcher → legs:** 1 domino each side (2 joints)
- **Divider → front rail + back apron:** 2 dominos each end (short depth to fit thin divider)
- **Top → aprons:** 8 L-brackets with slotted holes (wood movement, 2 per side)
- **Drawers:** dovetails at all 4 corners

### Appearance

```
apply_appearance(species="maple")
```
