# build123d spike — Midou + Ming table, headless, no Fusion

A proof-of-concept rebuild of two existing ShopPrentice pieces on
[build123d](https://build123d.readthedocs.io/) (Python + OpenCASCADE), to test
whether we can model, validate, and render furniture **without Fusion 360** —
no GUI, no single-document lock, no shared-instance crashes, runnable N-at-once.

## Run

```bash
python3 -m venv .venv-b123d
.venv-b123d/bin/pip install build123d trimesh matplotlib
.venv-b123d/bin/python midou_b123d.py        # -> out/midou.{step,stl,png}
.venv-b123d/bin/python ming_table_b123d.py   # -> out/ming_table.{step,stl,png}
```

Each script builds the model, runs `validate_design` (interference +
connectivity), exports STEP + STL, and renders an isometric/front PNG — the
whole loop ShopPrentice currently asks Fusion for, in one headless process.

## What's here

| file | role (the Fusion equivalent) |
|------|------------------------------|
| `b123d_common.py` | export (STEP/STL + per-body STL & manifest), headless render, `validate_design` (interference via pairwise boolean volume; connectivity via kernel min-distance clustering) |
| `midou_b123d.py`  |米斗 tapered through-dovetail box — full joinery |
| `ming_table_b123d.py` | 平头案 side table — full visible form, incl. spandrel coves + edge fillets/chamfers |
| `fillet_stress.py` | OCCT fillet/chamfer failure-mode battery (see "Fillet/cove robustness") |
| `viewer.html` | browser viewport — three.js, orbit/zoom/pan, per-body toggle + isolate, explode slider, wireframe, section plane, measure tool, auto-reload, model switcher |

## Browser viewer (the interactive viewport, headless)

This is the piece Fusion's GUI otherwise gives you — but you can open many at
once, and it's just a static page + files.

```bash
python3 -m http.server 8731        # from this directory
# open http://localhost:8731/viewer.html
```

Each `*_parts/` dir holds one **STL per body** plus a `*.json` manifest
(name, color, component, build stamp). The viewer loads the manifest, so every
body is individually listed, colorable, toggle-able, isolate-able, and
explodes from the assembly center. STL (not glTF) is used per-body on purpose:
it writes raw model-space triangles with no up-convention and no per-body
recentering, so the parts reassemble at exactly their model coordinates.
build123d's glTF export repositions each body (its panels landed at the wrong
height), which a symmetric model like the midou hides but the asymmetric Ming
table exposes.

Inspection tools (verified in-browser):

- **Section plane** — X/Y/Z (model axes) + position slider; look *inside*
  the joinery. three.js clipping doesn't cap the cut faces (they read hollow);
  fine for inspection, a real capped section would need stencil passes.
- **Measure** — toggle, click two surface points, distance in cm (raycast
  picks; a >5 px drag is treated as orbit, not a pick).
- **Auto-reload** — the viewer polls the manifest's `stamp` every 2.5 s and
  hot-swaps the model when a rebuild lands, preserving camera, section state,
  and per-body visibility. Verified: edit a parameter in the build script,
  re-run it, the browser updates in place. This is the agent-iteration loop:
  the agent rebuilds headless, the human just watches the tab.
- **Wood grain** — procedural streak texture, box-projected UVs with the U
  axis on each body's longest bbox axis (the same longest-axis heuristic
  `apply_appearance` uses); body color tints it. Toggle: Grain.
- **Edge lines** — `EdgesGeometry` feature outlines per body (CAD-style);
  they follow explode/hide/section. Toggle: Edges.
- **Parameters** — the build scripts now expose a `PARAMS` dict (`build(overrides)`,
  `--set k=v` CLI); the manifest carries params + units, the viewer renders an
  editable panel, and **Rebuild** POSTs to `server.py` (`POST /rebuild`), which
  re-runs the script in a subprocess — validation gates the result, the stamp
  bump hot-swaps the geometry. The Fusion palette loop, headless.
  Run `server.py` (not plain `http.server`) to get the endpoint.

Rebuild speed: profiling showed a subprocess rebuild spent **2.2 s of ~3.7 s
importing the OCP kernel** and ~1.2 s on O(n²) validation. Fixes: `server.py`
rebuilds **in-process** (kernel imported once at startup; the model script is
`importlib.reload()`ed per request, so source edits still apply; one build at
a time behind a lock), and validation got a **bounding-box broadphase** (bbox
gap is a lower bound on distance, so disjoint-box pairs skip the kernel
query). Ming table round-trip: **~5 s → 2.1 s**, including the full joinery
booleans. Next lever if needed: cache unchanged parts' meshes across rebuilds.

Parameter-validity note: the rebuild loop happily accepts geometrically
inconsistent combos (e.g. midou `dt_count=9` × `dt_tail_w=1.9` on an 18.15 cm
joint line → negative pin width; the tails fuse into a strip). The Fusion
original has no guard either. Derived-parameter sanity checks (pin width > 0,
tenon fits shoulder, …) belong in the future helper library, not each script.

## Capture → build123d converter (route 2: deterministic conversion)

`capture_to_b123d.py` converts a Fusion `capture_design` JSON into the same
solids on OpenCASCADE — no hand-porting. Proven on **pencil-box** (68 timeline
features: 21 sketches, 25 extrudes, 7 combines, 8 patterns): replay the
timeline using the capture's solved sketch coordinates + world frames,
evaluate distance/count *expressions* against the captured parameter table,
and gate the result on the capture's per-body ground truth.

Result: **exact parity** — all 6 bodies match Fusion's volumes/bboxes to
1e-4, and the rebuild reproduces the original's six real interference
overlaps (sliding-fit tongues) to the third decimal, verified against
Fusion's own `check_interference` on the same model.

The one thing the capture doesn't record is **extrude direction**. It is
resolved deterministically by building both candidates and scoring:

1. **Cut** — intersection volume with participants, **plus a lump-count
   check**: the capture records how many bodies the feature output, and the
   wrong direction often *severs* the target (lid-rabbet case — both
   directions remove identical volume; volume+bbox parity alone is provably
   blind to it).
2. **Join** — overlap with the final bbox MINUS overlap with the current
   target (a join into existing stock is a no-op — lid-lip case).
3. **NewBody intermediates** (unnamed tool bodies) — look ahead to the
   Combine that consumes them and score against its target.
4. **Mate tie-break** — a cut void is normally occupied by a mating part, so
   prefer the direction tracking another body's final bbox (groove cases).
5. **Score quantization** — OCCT boolean volumes carry ~1e-15 noise; without
   rounding, tied primaries never tie and the tie-breakers never fire.

**Coverage so far** (all repo examples, captured live in scratch docs):

| example | features | bodies | body parity | interference parity |
|---|---:|---:|---|---|
| pencil-box | 68 | 6 | exact (1e-4) | 6/6 pairs match Fusion |
| mirror-frame | 20 | 5 | exact | clean in both |
| toy-box | 111 | 18 | exact | **16/16 pairs match Fusion (4th decimal)** |

Vocabulary added for the sweep: **Mirror** in both modes — body mirror (the
`bodies` list holds copy AND source, with rename-vs-copy resolved by final
bbox; `inputBodies` may be stale pre-rename names or NewBody *feature* names)
and feature mirror (`sp.mirror_feats`: mirror the source feature's tool and
re-target by overlap, registered so later patterns can replay it) — **Arc**
curves (direction not captured; minor-arc convention, endpoints taken from
the chained neighbours because recomputed arc ends drift ~1e-3 off the
rounded capture), **patterns with multiple input features** (the toy-box
drawer patterns replay Join + its Mirror together), and **patterns of
NewBody features** (materialize Fusion-named `Body (k)` copies — later
combines consume them by name, coincident duplicates included).

Two upstream findings from the sweep, spun off as tasks: **bench** no longer
builds in Fusion at all (DofError in sketch_slot via the domino template),
and **toy-box builds but was never validation-gated** — Fusion confirms 16
real interference pairs (drawer modeled inside the case front with no
opening, BackPanel at the front face, batten clashes). The converter
reproduces all 16 to the 4th decimal, which is exactly the parity standard:
*volume + bbox + interference-set match*. Volume+bbox alone is provably
insufficient (the lid-rabbet case).

**Capture upgrades (addin/tools/_capture_helpers/)** — the add-in now records
the ground truth the converter previously had to infer:

- `extrude.py`: **start/end face centroids** (read at rollTo(False) where the
  faces are alive). Direction sign = sign(dot(endFaceCentroid − sketchOrigin,
  normal)) — exact. (`ExtrudeFeature` has no `isDirectionFlipped`; the old
  attempt silently never fired.)
- `sketch.py`: arcs record an exact **on-arc `mid` point** (and the 7-value
  `Arc3D.getData` unpack is fixed — the old 5-way unpack always threw, which
  is why `sweepAngle` never appeared in captures).
- `pattern.py`: **`elementOffsets`** — every pattern element's transform in
  element order (= Fusion's `Body (k)` copy-naming order), plus the resolved
  `directionOne/Two` vectors (the old entity-derived field could be plain
  wrong: toy-box recorded +Y for a +Z pattern).
- `modifiers.py`: mirrors classify **`inputFeatures` vs `inputBodyNames`**
  and record **`newBodies`** (entity-token diff — `MirrorFeature.bodies`
  includes the sources).

The converter prefers these fields and falls back to inference for old
captures. Re-captured pencil-box result: **zero direction warnings** (no
inference ran at all) and the interference set matches Fusion **6/6 pairs
exactly** — including the lid-rabbet case that volume+bbox parity provably
cannot distinguish.

Scope note: conversion targets are the **README-referenced examples** only
(midou-box, ming-table, pencil-box so far). mirror-frame / toy-box captures
stay in `captures/` as converter regression tests — toy-box turned out to be
an UNVALIDATED WIP example (its 16 real interference defects are faithfully
reproduced, which is how they were found).

Vocabulary now also covers: **Sweep** (straight sketch-line paths — reduce to
oblique extrudes, direction from which path end the profile sits on),
**Move** (4x4 matrix), **Symmetric extrudes**, **Circle** and
**FittedSpline** profiles, **Remove**, and unnamed-tool resolution (a combine
whose tool body the capture never named — matched by intersection with the
combine's target).

**Ming-table conversion boundary** (247 features; legs/sweeps/circles all
build): blocked on three CAPTURE gaps, not converter gaps —
`SketchEllipticalArc` is captured with no geometry at all (30 of them — the
apron coves; the elevation outline can't close), `Loft` has no capture
handler (appears as feature type "Unknown"), and `SplitBody` doesn't record
its splitting tool. Next round: capture-helper upgrades (elliptical-arc
geometry + on-arc mid via the evaluator, a Loft handler with profile refs,
SplitBody tool refs), then re-capture.

**Ming-table conversion status** (247 features, the hardest example): builds
END-TO-END and passes validation (0 interference, 1 connected cluster).
17/25 bodies at exact parity; the remaining 8 are all in the apron subsystem,
within 1.5% volume (spandrels 0.12%), with two understood geometric deltas
(apron ends ~0.9 cm, spandrel tops 0.6 mm) rooted in the original's
overshoot-then-trim choreography on the leaning apron plane.

Machinery added for the ming tier (capture side — reload_addin is invocable
from a script via `sys.modules["tools.reload_addin"].handler()`):

- **EllipticalArc geometry** (sampled on-curve points via the evaluator; the
  old capture recorded the bare type with NO geometry), **Loft** handler
  (operation + section profiles; BRepFace sections record their outer-loop
  polygon), and the arc/pattern/extrude ground-truth fields from earlier.

Converter side:

- **Planar-arrangement profile fallback** (BRepAlgoAPI_Splitter of a big
  plane face by ALL live curves) with union-of-inside-regions — Fusion
  profiles can be bounded by projected reference geometry whose construction
  flags were mutated after use, so loop chaining alone cannot close them.
  Regions are rebuilt as **fresh polygonal faces** (discretized boundaries):
  splitter-output faces carry pcurve baggage that makes OCCT pairwise
  booleans silently no-op against long-boolean-chain targets.
- **Loft as a manually triangulated sewn shell** — OCCT ThruSections picks
  its own (self-crossing) vertex correspondence for mirrored sections, and
  1e-4-rounded capture vertices fail its planarity tolerance; the manual
  build uses min-ruling-length correspondence and always closes.
- **SplitBody replay from recorded fragment geometry** (`bodyGeo`): trim the
  input to the kept fragment's bbox, volume-gated — the splitting tool is a
  face reference that cannot be replayed directly.
- **Symmetric extrudes are PER-SIDE distance** (SymmetricExtentDefinition
  with isFullLength=False — the capture should record the flag).
- **No-op cut recovery ladder**: detect zero-effect cuts, then retry with a
  micro-nudged deep copy, a ShapeFix-healed target, a fuzzy boolean, and
  finally a tessellate-and-resew rebuild of the tool. Some no-ops are
  legitimate (the original overshoots then trims; exact-built geometry has
  nothing to trim) — the parity gate distinguishes them.

Not yet covered: curved sweep paths, two-sided/tapered extrudes, circular
patterns. Converted models are **not parametric** — sketch coordinates are
baked at capture-time values (expressions survive only where the capture
carries them: extrude distances, pattern counts/pitches).

Capture lesson for the add-in: recording `isDirectionFlipped` (and an
interference summary) in the capture would remove the inference entirely.

## Result

Both build clean and pass validation (0 interference, 1 connected cluster):

```
Midou (米斗): 5 bodies   -> PASS
Ming table : 18 bodies  -> PASS
```

## The headline: complexity collapses

| | Fusion (lines) | build123d (lines) |
|---|---:|---:|
| Midou | 680 | 154 |
| Ming table | 1450 | 291 |
| shared infra | (MCP add-in) | 241 |

The Fusion scripts are ~75% **constraint-solver choreography**, not geometry:
`probe_orientations`, `set_ang` supplement handling, `isFullyConstrained`
guards, per-vertex drift checks after every constraint, `refs_to_construction`,
`smallest_profile`, and — in the Ming table — `anchor_poly`, `pin_free`,
`_poly_cut`, projected-leg-silhouette `addParallel`, and the deps sketch-quality
gate. **None of that exists here.** A board or a dovetail is `Face -> extrude
along a vector`; a position is a model coordinate. The dovetails are still
"flush by construction," but the construction is arithmetic, not a solver
fixpoint you have to verify didn't drift.

Most of the hard-won lessons in project memory (sketch reanchoring, anchor
modes, supplement-angle flips, ghost bodies from mirrored combine tools) are
**Fusion-specific** and simply don't arise in a coordinate-driven kernel.

## What this spike deliberately does NOT cover

- **Ming table concealed joinery — partially carved now.** The table carries
  real joints: **格角榫** mitered mortise-and-tenon at all four top-frame
  corners (miter thirds + tenon-waste pentagon per the Fusion template
  proportions; stiles mortised by subtracting the rails), a **panel tongue +
  frame groove** (tongue_ov 0.25", tongue_w = panel_t/2), and **full-height
  mitered shelf-rail tenons meeting inside each round leg** (45° miter plane
  through the leg axis; legs mortised by subtracting the tenons). Still
  simplified: the apron ring's **hidden full-blind dovetail corners** (this
  port's aprons butt into the legs rather than forming the original
  corner-to-corner ring) and the **sliding-dovetail battens** are omitted,
  and the 1.5° apron-plane tilt is skipped (invisible at this scale).
- **Photoreal rendering.** matplotlib gives a serviceable shaded preview but
  uses painter's-algorithm sorting (hence faint banding). The real path is
  headless **Blender** fed the STEP/STL with grain-aligned UV maps.
- **No live feature timeline.** build123d's model *is* the script (which is how
  ShopPrentice already treats it — the palette writes params back to the `.py`).
  There's no rollback history to bisect; you re-run.

## Fillet/cove robustness (OCCT 7.9.3 via OCP 7.9.3.1)

The main geometric unknown is now exercised. The Ming table carries the real
curved spec from the Fusion original: quarter-circle **coves** (`cove_r` =
0.75") at the apron-band/spandrel transitions and rounded spandrel bottom
corners (`bot_r` = 0.75") — done as **2D profile fillets** before extrude
(`poly_prism(..., fillets=[(vertex_idx, r), ...])`) — plus **3D edge
fillets** on the top frame's outer top edges (0.25" round-over, applied
*after* the leg cope) and an `sf_cham` (0.3125") **chamfer** on the shelf
rails' top outer edges. Validation stays PASS (0 interference, 1 cluster).

`fillet_stress.py` is the failure-mode battery — 25 configurations at real
model dimensions, each PASSing only if the op completes **and** yields a
valid solid with sane volume. Findings:

**What works:**

- **2D profile fillets (do these first — most robust).** Convex round-overs
  AND reflex-corner coves, multiple radii applied sequentially, radii right up
  to the geometric limit (two 1.75" arcs on a 3.5625" segment). The filleted
  face extrudes cleanly and survives later boolean copes.
- **3D edge fillets** up to 0.999× the adjacent face width; three edges
  meeting at a box vertex in one call (proper corner ball patch); two
  perpendicular edges filleted sequentially (the second lands on the first's
  surface); filleting the reflex vertical edge of an extruded bracket (a 3D
  cove) — all fine.
- **Fillet/chamfer across a boolean-cut face, if the cut crosses cleanly.**
  A chamfered edge interrupted by a leg cope works when the cope cylinder
  *crosses* the face at a healthy angle; ditto filleting the box/cylinder
  seam edge itself (r = 0.05–0.15 cm).

**What chokes:**

- **Near-tangency is the killer, not booleans.** The model's real shelf-rail
  config — cope cylinder near-tangent to the rail's outer face (the leg lean
  leaves a ~0.03 cm sliver) — fails `BRep_API: command not done` for chamfer,
  and the seam fillet fails too. Chamfering only the segments *away* from the
  grazed sliver still fails: any edge segment that **terminates on** a
  near-tangent cylindrical face is enough. (Oddly, an edge *fillet* in the
  same spot survives — fillet termination is more robust than chamfer's.)
- **Full round-over** (r = face width) fails; r = 0.999× width works. Known
  OCCT limit; use 0.999×, or `max_fillet()` to probe.
- **2D fillets whose arcs would overlap** (r sum > adjacent segment) fail —
  but *cleanly*, with an exception naming the vertex and radius. Every
  failure in the battery raised; none returned silently-invalid geometry.
  That's the property the agent loop needs: failures are catchable, not
  corrupting.

**Workarounds (both in the model now):**

1. **Order swap:** apply the chamfer to the pristine edge, boolean the cope
   *after*. Booleans resolve the same near-tangent intersection that chamfer
   termination cannot. This also matches shop order (mold the edge profile,
   then cut the joinery) — and is the Fusion original's approach too
   (`tf_cham` spline cutter bodies, i.e. cut-with-a-tool-body instead of an
   edge operation).
2. **Profile-level fillets** wherever the curve lives in a sketch plane —
   the cove/round work happens on the wire, where OCCT 2D fillet is solid.

Net: OCCT handles everything this furniture needs, but generators should
(a) fillet profiles before extruding, (b) sequence edge treatments before
booleans whose cut surfaces approach tangency, and (c) treat fillet/chamfer
exceptions as first-class search feedback — they are reliable signals, not
crashes.

## Risks surfaced

- **Connectivity for round-on-round** (pegs in holes) has the same planar-
  contact caveat as Fusion; not relevant for these two pieces.

## Verdict

Faithful form + real joinery + fillets/coves + validation + export, fully
headless, ~4x less code, no crashes, parallelizable. Strongly supports
build123d/OCCT as the backend for agent iteration, with Fusion/Blender
optional downstream targets. Next de-risking step: a Blender render pass.
