# Wood Grain, Strength, and Tenon Design

**Read this before designing ANY mortise-and-tenon (or any joint that cuts a
pocket into a piece).** It explains why fiber direction governs joint strength,
then gives the rules for both **orienting** and **sizing** a tenon — the math +
helpers/validator, the two factors that *bound* the size (the tenon's own
cross-section and its depth), and a **strength estimator** (`joint_strength.py`)
that scores a joint's capacity in every direction so you can size for the loads
you expect. Generalizes the kerf rule in `tenon-wedge.md` and the joint-choice
rules in the core skill (rule 9).

The design follows four facts, in order: **(1)** strength is long-grain-to-long-grain
glue area; **(2)** cutting the mortise should sever as few fibers as possible;
**(3)** the tenon must keep enough cross-section to carry shear/bending/twist itself;
**(4)** depth adds glue and leverage but with diminishing returns and practical
limits. (1)+(2) set the orientation and the wide/thin proportions; (3)+(4) keep
you from optimizing (1)+(2) into a weak thin slice.

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

1. **Glue — what "long grain" actually means:** a glue bond is full-strength
   **long-grain-to-long-grain when BOTH pieces' fibers lie PARALLEL TO the mating
   (glue) face** — both grains running *in the plane of* that surface. This is the
   precise definition of "glue along the grain," and it is **angle-independent**: a
   tilted or angled joint keeps full long-grain glue as long as both fibers lie in
   the face — **the joint's angle does not create end grain.** End grain appears
   only where a fiber pokes *out of* the face (perpendicular to it); a face where a
   fiber is *partly* perpendicular is *partly* end grain — grade it by that angle
   (Hankinson, below). A sound long-long line is **wood-limited** — rate it at the
   wood's shear-parallel strength (`fl = τ`), not the adhesive's datasheet psi (PVA
   ~3,400–4,200; the wood gives first). End-grain glue is weak but **not zero**:
   ~**15%** raw, up to ~**25%** sized (primed) — the documented ceiling (USDA FPL
   Wood Handbook). For a face at angle *x* to a fiber, interpolate with **Hankinson**
   `N = fl·fe / (fl·sinⁿx + fe·cosⁿx)`, n≈2 (`glue_shear_per_area(x)`; a linear
   `cos/sin` blend over-predicts mid-angles 2–4×). Rule 9 covers joint *choice*.
2. **Material removal:** cutting a mortise *removes* fibers from the mortise piece.
   **Where** and **how** you remove them decides whether the piece stays strong —
   which is what this document is about.

## The rule: orient the mortise WITH the grain

> **A rectangular tenon's WIDER cross-section dimension must run ALONG the mortise
> piece's fiber direction.** (A square cross-section must keep at least one edge
> parallel to the fiber.)

Equivalently: the **mortise is long with the grain, narrow across it** — never the
reverse.

**This is the axis-aligned *shorthand* for the glue + fiber rules, not a separate
law.** "Wider dimension along the mortise grain" is just what "both fibers parallel
to the large glue cheeks, and few fibers severed" works out to when the pieces meet
square. For an **angled** joint, do NOT apply it literally or flag the joint as
"grain-wrong" — go back to the definitions: (a) are both fibers parallel to the
cheek faces? and (b) does the mortise sever few fibers? A strut tenoning into a
spine at 40° — both members horizontal — still has full long-grain glue on its
horizontal cheeks, because both fibers lie in those faces; the plan angle changes
nothing there. The angle is fine. What still binds at *any* angle: maximize the
long-long cheek area, keep enough section + depth, and minimize fibers severed.

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

## Beyond glue & fiber: the tenon's own strength, and depth

Maximizing glue area and minimizing fibers cut can be pushed too far — to a thin
slice with huge cheeks that **shears or snaps**. Two more factors bound the size.

### Factor 3 — the tenon's own strength is its CROSS-SECTION

The cheeks carry pull-out (tension); the tenon *body* carries **shear, bending,
and twist**, and those scale with the tenon's **cross-section (w × t)**, not its
glue area. Optimize (1)+(2) to an extreme thin slice and the joint fails in
shear/bending even with "maximal" glue.
- Transverse shear ≈ (w·t)·τ. Bending ≈ section modulus · MOR, *capped by the
  section*. Note the across-fiber **thickness** — the dimension the fiber rule
  wants thin — is also what resists bending in the weak plane, so don't starve
  it. The **~⅓ thickness** rule is the floor that keeps the section honest.

### Factor 4 — depth (length): more is stronger, until it isn't

A deeper tenon ⇒ more cheek glue and a longer bending lever (~L²). But the glue
gain is **sublinear** — Eckelman (Purdue) found withdrawal ∝ **depth^0.89** (the
deep end of the joint carries less load), so returns fall off past ~2.5× the tenon
width. And:
- **Blind:** leave a **mortise-bottom wall** at the far face — too thin and it
  blows through when cut. The glue depth is the *tenon length*, not the mortise
  depth (the mortise is cut slightly deeper; the wall stays).
- **Through:** the **proud** part adds **no glue** — it's outside the joint. It
  adds strength only if it carries a **tusk** (then a *mechanical* pull-out
  couple, sized by the tusk + relish, not by glue).
- **Diminishing returns + limits:** past **L\* = t·√(MOR/C⊥)** the tenon's own
  section governs bending, so deeper stops adding moment capacity. And mortise
  depth is limited by chisel reach and by a small mortise mouth (a deep mortise
  behind a small opening is hard to cut). So don't reflexively max depth — track
  it to the cross-section.

## Glue carries pull-out; bearing carries the rest

Not every direction is a glue problem — which is why a dry-fit joint still
resists some loads. When sizing, ask *which mechanism* carries each direction:

- **Pull-out (tension along the tenon axis)** is almost entirely **glue** (cheek
  shear + a little end grain + any pin/wedge/tusk); friction is minor. Size the
  glue cheeks for it (wide × deep).
- **Transverse force (the member pushed sideways / down)** is carried by
  **BEARING** — the tenon pressing on the mortise walls — and holds with **no
  glue**. A stretcher between two legs resists being pushed to the floor because
  the legs' inner **end grain bears the tenon's side** (compression *parallel* to
  the leg grain — strong). The two transverse directions differ: a force *along*
  the mortise grain bears on strong end grain (C∥); *across* it, on weak long
  grain (C⊥). Size the tenon's **section** (and pick its orientation) for whichever
  way the load actually comes.
- **Racking / bending** is the bearing couple over the tenon depth (deeper = more)
  capped by the tenon's own section; **twist** is the tenon's torsional section.
- **Pegs / drawbore pins** add *mechanical* pull-out. Size them by the **European
  Yield Model**: capacity = the **minimum** over yield modes — wood crushing under
  the peg (bearing), the peg shearing, or the peg bending into hinges
  (`Md = Fb·D³/6`) — and report which governs. Add a **relish tear-out** check (the
  wood between the peg and the tenon end shears out; keep the peg ≥ **4×D** from the
  end — a brittle mode). Glue and peg don't add (glue is stiffer, carries first; the
  peg is the backstop, or the whole joint if unglued). **Drawboring is prestress
  only** — it pulls the shoulder tight but adds no ultimate capacity.

So: **glue for pull-out; wood section + bearing for everything else.** The
estimator below reports each direction with its mechanism and flags the glue-free
ones — so a joint that will mostly see side load isn't sized as if glue were
holding it.

## Strength estimator (code)

`helpers/sp/joint_strength.py` turns all four factors into a tool. Given a tenon
size it estimates the capacity in **every direction**, names the governing
failure mode, and prints design guidance. Pure Python (no Fusion) — runs/tests
anywhere:

```python
from helpers.sp.joint_strength import estimate_mortise_tenon, summarize, glue_shear_per_area
print(summarize(estimate_mortise_tenon(width=1.5, thickness=0.875, depth=2.0,
                                       species="white_oak", sized=True,
                                       pins=1, pin_dia=0.375, pin_end_distance=1.5)))
#   withdrawal_tension   ~12k lbf  [GLUE, wood-limited; end grain 25% sized; ~depth^0.89]
#   shear_along_w/_t      ...  lbf [GLUE-FREE bearing — the side/down-load path]
#   bending_about_w      ... in-lbf[embedment bearing; deeper helps to L*]
#   pin_withdrawal       ...  lbf  [peg, EYM min over shear/bending/bearing]
#   + guidance: thin-tenon, sublinear depth, relish 4xD/brittle, Hankinson, etc.
# glue_shear_per_area(45, "white_oak")  -> off-axis face strength (Hankinson)
```

Use it while designing: pick a size, read which direction is weak for the loads
you expect, and adjust — **more width/depth** for pull-out and moment, **more
thickness** for shear/twist. Capacities are first-order (mean clear-wood
strengths, simple failure models) — relative guidance and a sanity check, not a
structural certification. `width` is the along-grain (cheek) dimension, `depth`
is the *glue-engaged* length (exclude through-proud).

### Two roles: design-time advisory + build-time gate

The estimator is cheap (~5 µs, no Fusion), so it has two jobs:

- **Design time (advisory):** call `estimate_mortise_tenon(...)` *while choosing*
  dimensions — before any geometry — to find the weak direction and size for it.
  This is where it prevents the mistake.
- **Build time (gate):** `sp.validate_joint_strength(tenon_body, mortise_body,
  tenon_axis, species=…, …)` measures the tenon off the body, runs the estimator,
  and prints a WARNING for the **load-independent red flags** — grain rotated
  wrong, a **thin slice** (thickness < ¼ width → its own shear/bending governs),
  a **brittle peg** (drawbore end distance < 4×D) — and, if you pass
  `expected={mode: lbf}`, any **overloaded** direction. It never raises. The
  **joinery templates call it automatically** (e.g. `mortise_tenon` runs it on the
  tenon before the JOIN), so the gate fires without the agent remembering — agents
  reliably honor forcing functions, not advisories. For a hand-built joint, call
  it yourself before JOINing (same place as `validate_tenon_grain`). Full adequacy
  needs the expected loads, which furniture rarely quantifies, so the dependable
  wins are the load-independent flags plus comparing candidate sizes.

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
4. Keep enough **cross-section** (w·t) for the tenon's OWN shear/bending/twist —
   don't thin to a slice chasing glue (factor 3).
5. Mind the **depth** limits: blind → leave a mortise-bottom wall; through → proud
   adds no glue (tusk for mechanical pull-out); diminishing returns past
   L\* = t·√(MOR/C⊥); watch chisel reach / small mouths (factor 4).
6. Keep the mortise back from the **end** of the piece (long-grain relish — the end
   face is short grain and blows out).
7. **Score it (design time):** `estimate_mortise_tenon(...)` → capacities per
   direction + the weak axis for your expected loads; adjust width/depth (pull-out,
   moment) or thickness (shear, twist).
8. If wedged, cut the kerf ⟂ to the mortise grain (`tenon-wedge.md`); if pinned,
   run the pin **across** the grain (and keep it ≥ 4×D from the tenon end).
9. **Gate it (build time):** assert `sp.validate_joint_strength(tenon_body,
   mortise_body, tenon_axis, …)` before JOINing (the joinery templates do this
   automatically) — it folds in `validate_tenon_grain` and WARNs on grain-wrong,
   thin-slice, brittle-peg, or overload.
</content>
