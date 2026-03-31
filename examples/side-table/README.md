# Side Table / Nightstand

A parametric modern side table — 22"L x 16"W x 24"H with single dovetailed drawer. Three aprons (back + two sides) with blind M&T joinery, two front stretchers (upper + lower) framing the drawer opening, interlocking tenon notches at back corners, 3" bar pull, leg chamfers, and top edge fillet. Drawer front is the visible front face framed by horizontal rails.

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

**Script:** [`side_table.py`](side_table.py) — 16 bodies (4 legs, 3 aprons, 2 stretchers, top, 5 drawer, pull handle). Uses `mortise_tenon`, `dovetailed_drawer`, and `pull` templates.

### Techniques

- **Blind M&T** — 6 apron joints + 4 stretcher joints via `mortise_tenon.blind()` with mirror planes
- **Interlocking notches** — center-half on back tenons, top+bottom quarter on side back-end tenons
- **Two front stretchers** — upper + lower rails framing the drawer opening with smaller M&T (0.75" tenon width)
- **Dovetailed drawer** — half-blind front, through back
- **Bar pull** — 3" center-to-center via `pull.install()`
- **Leg chamfers** — 1/8" on bottom edges
- **Top fillet** — 1/16" on perimeter edges

### Appearance

```
apply_appearance(species="walnut")
apply_appearance(species="spalted maple", bodies=["dd_Front"])
```
