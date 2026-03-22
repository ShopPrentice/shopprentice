# Crib

A parametric modern crib — 52"L × 28"W interior, 34"H rail height. CPSC-compliant spindle spacing (2.25" center-to-center, gap ≤ 2.375"). Maple appearance.

![Crib — iso top-right](screenshots/iso-top-right.png)

<p float="left">
  <img src="screenshots/front.png" width="49%" />
  <img src="screenshots/right.png" width="49%" />
</p>

### Transparent View

<p float="left">
  <img src="screenshots/transparent-iso-top-right.png" width="49%" />
</p>

---

**Script:** [`crib.py`](crib.py) — 92 structural bodies + 48 joinery voids.

### Structure
- **4 corner posts** — chamfered tops for safety
- **8 rails** — top + bottom on all 4 sides
- **70 spindles** — 12 per short side, 23 per long side (patterned + mirrored)
- **2 support rails** — mortised into corner posts at mattress height
- **8 slats** — spanning between support rails, tops flush

### Joinery
- **Rails → posts:** 2 dominos per joint (32 total)
- **Spindles → rails:** bulk CUT stub tenons (8 CUTs for 70 spindles)
- **Support rails → posts:** blind mortise (CUT rail ends into posts)
- **Slats → support rails:** dominos at each end (16 total)

### Notes

Mattress support is at a fixed height (`mattress_h = 6"`). A production crib would need adjustable height positions — multiple sets of mortise holes in the posts at different Z levels, with the support rails removable and re-insertable.

### Appearance

```
apply_appearance(species="maple")
```
