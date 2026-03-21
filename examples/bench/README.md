# Entryway Bench

A parametric modern entryway bench — 48"L x 14"W x 18"H with 1.5" thick seat, 2" square legs, apron frame, front/back stretchers, and domino joinery at all connections.

![Bench — iso top-right](screenshots/iso-top-right.png)

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
Build a modern entryway bench: 48"L x 14"W x 18"H, thick seat,
square legs, aprons, stretchers, domino joinery. All parametric.
```

### Appearance

```
apply_appearance(species="white oak")
```

---

**Script:** [`bench.py`](bench.py) — 11 structural bodies + 20 domino voids. Domino grid at 8 apron-to-leg joints (2 per joint) + single dominos at 4 stretcher-to-leg joints.
