# Side Table / Nightstand

A parametric modern side table — 22"L x 16"W x 24"H with single dovetailed drawer. Front apron with drawer opening, blind M&T joinery at all 8 leg-apron joints with interlocking tenon notches, 3" bar pull, leg chamfers, and top edge fillet.

![Side Table — iso top-right](screenshots/iso-top-right.png)

<p float="left">
  <img src="screenshots/front.png" width="49%" />
  <img src="screenshots/right.png" width="49%" />
</p>

### Transparent Views

<p float="left">
  <img src="screenshots/transparent-iso-top-left.png" width="49%" />
  <img src="screenshots/transparent-iso-top-right.png" width="49%" />
</p>

---

**Script:** [`side_table.py`](side_table.py) — 15 bodies (4 legs, 4 aprons, top, 5 drawer, pull handle). Uses `mortise_tenon`, `dovetailed_drawer`, and `pull` templates.

### Techniques

- **Blind M&T** — 8 joints via `mortise_tenon.blind()` with mirror planes
- **Interlocking notches** — center-half on front/back tenons, top+bottom quarter on side tenons
- **Dovetailed drawer** — half-blind front, through back
- **Bar pull** — 3" center-to-center via `pull.install()`
- **Leg chamfers** — 1/8" on bottom edges
- **Top fillet** — 1/16" on perimeter edges

### Appearance

```
apply_appearance(species="walnut")
apply_appearance(species="spalted maple", bodies=["dd_Front"])
```
