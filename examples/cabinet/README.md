# Wall Cabinet

A parametric modern wall cabinet — 24"W x 12"D x 30"H with 2 inset doors, adjustable shelf, and plywood back. Dado joints for top/bottom into sides.

![Cabinet — iso top-right](screenshots/iso-top-right.png)

<p float="left">
  <img src="screenshots/front.png" width="49%" />
  <img src="screenshots/right.png" width="49%" />
</p>

### Transparent Views

<p float="left">
  <img src="screenshots/transparent-iso-top-left.png" width="49%" />
  <img src="screenshots/transparent-iso-top-right.png" width="49%" />
</p>

## Example Prompt

```
/woodworking
Build a modern wall cabinet: 24"W x 12"D x 30"H, 2 inset doors,
adjustable shelf, plywood back, dado joints. All parametric.
```

### Appearance

```
apply_appearance(species="cherry")
```

---

**Script:** [`cabinet.py`](cabinet.py) — 8 bodies (4 case, 2 doors, shelf, back panel). Dado joints, back rabbet.
