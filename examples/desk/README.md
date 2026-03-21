# Writing Desk

A parametric modern writing desk — 48"L x 28"W x 30"H with single dovetailed drawer, domino joinery at apron-to-leg connections. No front apron — drawer front fills the front face.

![Desk — iso top-right](screenshots/iso-top-right.png)

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
Build a modern writing desk: 48"L x 28"W x 30"H, 1" thick top,
single dovetailed drawer, domino joinery, square legs. All parametric.
```

### Appearance

```
apply_appearance(species="walnut")
```

---

**Script:** [`desk.py`](desk.py) — 13 structural bodies + 12 domino voids. Uses `dovetailed_drawer` template for half-blind front / through back dovetails. Domino grid at 6 apron-to-leg joints.
