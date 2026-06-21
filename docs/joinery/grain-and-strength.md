# Wood Grain, Strength, and Tenon Orientation

**Read this before designing ANY mortise-and-tenon (or any joint that cuts a
pocket into a piece).** It explains why fiber direction governs joint strength,
and gives the mathematical rule — and the helpers/validator — for orienting a
tenon's cross-section. This generalizes the kerf rule in `tenon-wedge.md` and the
joint-choice rules in the core skill (rule 9).

## Why fiber direction is everything

Wood is a bundle of long fibers (cellulose, bonded by lignin) running parallel to
the **longest dimension** of the part — leg fibers run vertically, a rail's run
along its length, a stretcher's along its length, a wide board's along its length.
Strength is wildly directional:

- **Along the grain** (with the fibers): very strong in tension and compression —
  you are loading continuous fibers end-to-end.
- **Across the grain** (perpendicular to the fibers): weak. Wood **splits/cleaves**
  along the grain because only the lignin between fibers resists — think of how
  easily a log splits with the grain but not across it.

Every joinery decision follows from this. Two consequences matter most:

1. **Glue:** long-grain-to-long-grain glues as strong as the wood; end-grain glue
   is nearly worthless (rule 9 in the core skill covers joint *choice* from this).
2. **Material removal:** cutting a mortise *removes* fibers from the mortise piece.
   **Where** and **how** you remove them decides whether the piece stays strong —
   which is what this document is about.

## The rule: orient the mortise WITH the grain

> **A rectangular tenon's WIDER cross-section dimension must run ALONG the mortise
> piece's fiber direction.** (A square cross-section must keep at least one edge
> parallel to the fiber.)

Equivalently: the **mortise is long with the grain, narrow across it** — never the
reverse.

### Why — the fibers you cut

Picture a slender leg, grain vertical (Z), and a rail tenoning into its face. The
mortise is a rectangular hole. It can be oriented two ways:

```
   CORRECT: tall (along grain)        WRONG: wide (across grain)
   mortise long axis ‖ fiber          mortise long axis ⟂ fiber

      leg (fiber │ vertical)             leg (fiber │ vertical)
      ┌─────────────┐                    ┌─────────────┐
      │ │ │ ▓▓ │ │ │ │   few fibers      │ │ ▓▓▓▓▓▓▓ │ │  many fibers
      │ │ │ ▓▓ │ │ │ │   cut; long       │ │         │ │  cut clean
      │ │ │ ▓▓ │ │ │ │   side cheeks     │ │ ▓▓▓▓▓▓▓ │ │  through; thin
      │ │ │ ▓▓ │ │ │ │   are long grain  │ │ │ │ │ │ │ │  short-grain cheeks
      └─────────────┘                    └─────────────┘
```

- **Tall mortise (long axis along the grain):** the mortise spans many fibers
  *lengthwise* but severs **few** of them across — and the wood on either side
  (the cheeks) is full-length **long grain** that resists splitting. Strong.
- **Wide mortise (long axis across the grain):** it severs a **whole band of long
  fibers**, and the remaining cheeks above/below are short, cross-grain slivers
  that snap or split out. Weak — especially in a slender piece where there isn't
  much section to begin with.

So the tenon that fills it must be **taller than wide** for a vertical-grain leg —
**not because "tenons are tall," but because the leg's grain is vertical.** Put the
same rail into a piece whose grain runs *horizontally* and the correct tenon is
**wider than tall**. The shape is derived from the mortise piece, every time.

### The breadboard example (grain runs the other way)

A breadboard cap runs **across** the tabletop, so its fiber runs across the
panel. The panel's tongues/tenons seat into mortises in the breadboard, so the
**mortise piece is the breadboard** and its fiber is the cross-panel axis. The
rule therefore makes the tongues **wide and flat** (wide dimension along the
breadboard's length = its grain) — exactly the classic breadboard tongue. Same
rule, opposite-looking result, because the grain runs the other way.

### Slender vs. wide mortise pieces

The rule bites hardest on **slender** mortise pieces (legs, rails, stretchers,
spindles): there's little wood to spare, so a cross-grain mortise is a structural
mistake. On a **wide board/slab** the fiber axis can be ambiguous (width ≈ length
of the local region) — detect it explicitly and, if needed, pass the grain
direction by hand (see `grain_dir` in `tenon-wedge.md`).

### Related rules (same principle)

- **Wedge kerfs** (`tenon-wedge.md`): a wedge slot is cut ⟂ to the *mortise*
  piece's grain so the wedge spreads the tenon **across** the grain onto long
  fibers, not splitting along them. Same fiber-direction logic, applied to the kerf.
- **Drawbore pins / any pin**: a pin must cross the grain of every piece it
  pierces — a pin *along* the grain is a splitting wedge.

## Sizing the tenon: maximize long-grain glue, minimize fibers cut

Orientation (above) is only half the job — the **dimensions** follow from the same
two facts, and they decide the joint's actual strength:

1. **A joint's strength is its long-grain-to-long-grain glue area.** Only faces
   that are long grain on BOTH pieces carry load; an end-grain contact glues to
   almost nothing. So first identify which of the tenon's faces are the
   load-bearing glue faces and which are not:
   - **Cheeks** — the tenon faces parallel to BOTH the insertion axis AND the
     mortise piece's fiber. Long grain on the tenon (they run along its fiber)
     AND long grain on the mortise wall they meet (it runs along the mortise
     fiber). **These faces ARE the joint.** Maximize their area.
   - **Faces perpendicular to the mortise fiber** meet end-grain mortise walls →
     weak. **The shoulder** seats the joint and hides the gap but is end grain →
     not structural. Don't size the joint around either.

2. **Cutting the mortise severs the mortise piece's fibers — cut as few as
   possible.** The count severed ∝ the mortise cross-section *perpendicular to the
   fiber* = (dimension across the fiber) × (depth).

Put together, the dimensioning rule is:

> **Grow the tenon along the directions that add long-grain glue area (along the
> mortise fiber, and into the depth); keep it thin in the one direction that only
> severs fibers (across the mortise fiber).**

| Tenon dimension | Direction | Rule | Why |
|---|---|---|---|
| **Width** | along the fiber (in-section) | as large as the joint allows, less shoulder/relish | grows cheek glue; runs *with* the fiber so it severs none extra |
| **Depth** | along the insertion axis | as deep as practical (through, or ≥⅔ for blind) | grows cheek glue |
| **Thickness** | across the fiber (in-section) | ~⅓ of the stock it passes through (≈⅓ long-grain walls each side) | the ONLY dimension that severs fibers — minimal, but not so thin it shears |

Caps on the maxima:
- **Across-fiber walls** (long-grain cheeks left in the mortise piece): keep ~⅓
  each — what the ⅓ thickness rule buys.
- **End relish** (material between the mortise and the *end* of the mortise
  piece): that end face is short/cross grain and blows out if the mortise crowds
  it — keep the mortise back from the end.
- **Shoulder** on the tenon piece: enough for a clean seat; it's end grain, so
  more buys appearance, not strength.

The orientation rule is just this rule's consequence: the *wide* dimension lands
along the fiber because that is the dimension you grow for glue while the
across-fiber dimension stays thin.

### Worked example — a stretcher tenoning into a cross-member

A spine (fiber X) tenons through a cross-stretcher (fiber **Y**), both 2″×2.75″
stock, through the cross-stretcher's 2″ thickness:
- **Cheeks** = the tenon's top/bottom faces (⊥ Z): long grain on the spine *and*
  on the cross-stretcher. Area = width(Y) × depth(X) → **maximize Y and depth.**
- **Thickness** is the Z dimension (across the cross-stretcher fiber): ~⅓ of
  2.75″ ≈ 0.9″, leaving ~0.9″ long-grain walls top and bottom.
- **Width** (Y) as wide as the spine allows less shoulders ≈ ~1.5″ of the 2″.
- **Depth** = through (2″) + proud for the wedge.
- Result: **wide-in-Y, thin-in-Z** — the opposite of a "tall" tenon, *because the
  cross-stretcher's grain runs in Y.* (`validate_tenon_grain` confirms it.)

## The math (and how to apply it in code)

Let **f** = the mortise piece's unit fiber direction, and **a** = the tenon
insertion axis (unit). The tenon's cross-section lies in the plane ⟂ **a**.

1. Project **f** into that plane: `f_proj = f − (f·a)·a`.
2. The tenon's **wide** cross-section dimension runs along `normalize(f_proj)`;
   the **narrow** dimension runs along `a × f_proj`.
3. Degenerate case: if `f_proj ≈ 0` the fiber is parallel to the insertion axis
   (an end-grain mortise — rare); the cross-section orientation is then
   unconstrained by this rule.

Helpers in `sp` (in `helpers/sp/mating.py`):

| Function | Use |
|---|---|
| `sp.grain_vector(body)` | mortise piece's fiber as a unit `Vector3D` (principal axes of inertia; falls back to longest bbox axis). Works for slender and angled members. |
| `sp.grain_axis(body)` | fiber as an axis name `'x'`/`'y'`/`'z'` (longest bbox axis). |
| `sp.tenon_wide_direction(mortise_body, tenon_axis)` | the `Vector3D` the tenon's wide dimension should run (step 1–2 above); `None` for end-grain mortises. |
| `sp.tenon_wide_axis(mortise_body, tenon_axis)` | axis-aligned convenience: which perpendicular axis (`'x'`/`'y'`/`'z'`) to make the tenon's wide dimension; build the narrow dimension along the other. |

**Design-time use** — derive the orientation instead of guessing:

```python
wide = sp.tenon_wide_axis(leg, "y")   # tenon inserts into the leg along +Y
# build the tenon's larger cross-section dimension along `wide`,
# its smaller dimension along the remaining perpendicular axis.
```

## Validator

`sp.validate_tenon_grain(tenon_body, mortise_body, tenon_axis, tol=0.12)` checks a
built tenon against the rule. It measures the tenon's extent along the in-section
fiber direction vs. across it; if the tenon is **wider across the grain** (the
90°-wrong orientation) it prints a `WARNING` and returns `{"ok": False, ...}`. A
square section passes (an edge is parallel to the fiber by definition). It never
raises — mirroring `validate_joint_contact` / `check_domino_exposure`.

Call it **at build time on the tenon body before you JOIN it** to its owner (after
JOIN the tenon is no longer a separate body to measure):

```python
ten = sp.ext_new(comp, prof, "tenon_len", "Rail_Tenon").bodies.item(0)
sp.validate_tenon_grain(ten, leg, "y")   # warns if the section is rotated wrong
sp.combine(comp, [ten], JOIN, ...)       # then join it on
```

Joinery templates that cut mortises (`mortise_tenon`, `breadboard`, `drawbore`,
`tenon_wedge`, …) should orient with `tenon_wide_axis` and assert with
`validate_tenon_grain`, so the rule is enforced by construction and re-checked.

## Checklist when designing a mortise-and-tenon

1. Identify the **mortise piece** (the one the tenon goes into) and get its fiber
   direction (`sp.grain_vector`). For slender pieces this is the long axis.
2. **Orient:** make the tenon's **wider** cross-section dimension run **along**
   that fiber (`sp.tenon_wide_axis`). Square section → keep an edge along the fiber.
3. **Size** (maximize long-grain glue, minimize fibers cut):
   a. **Width** along the fiber — as wide as the joint allows, less shoulder/relish
      (grows the long-grain cheeks).
   b. **Depth** along the insertion axis — as deep as practical (through, or ≥⅔ for
      blind) (grows the long-grain cheeks).
   c. **Thickness** across the fiber — ~⅓ of the stock it passes through, leaving
      ~⅓ long-grain walls each side (the only dimension that severs fibers).
4. Keep the mortise back from the **end** of the piece (long-grain relish — the end
   face is short grain and blows out).
5. If wedged, cut the kerf ⟂ to the mortise grain (`tenon-wedge.md`).
6. If pinned, run the pin **across** the grain of both pieces, never along it.
7. Assert with `sp.validate_tenon_grain` before joining the tenon.
</content>
