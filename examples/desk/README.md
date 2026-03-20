# Writing Desk

A parametric modern writing desk — 48"L x 28"W x 30"H with single dovetailed drawer. No front apron — drawer front fills the front face.

![Desk — iso top-right](screenshots/iso-top-right.png)

<p float="left">
  <img src="screenshots/front.png" width="49%" />
  <img src="screenshots/right.png" width="49%" />
</p>

## Example Prompt

```
/woodworking
Build a modern writing desk: 48"L x 28"W x 30"H, 1" thick top,
single dovetailed drawer, square legs. All parametric.
```

---

**Script:** [`desk.py`](desk.py) — 13 bodies (4 legs, 3 aprons, top, 5 drawer bodies). Uses `dovetailed_drawer` template.
