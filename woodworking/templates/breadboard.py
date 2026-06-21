"""Breadboard end joint template.

A *breadboard end* caps the end of a wide solid-wood panel (a tabletop,
a door, a drop-leaf) with a narrower board whose grain runs ACROSS the
panel.  The panel grain runs lengthwise; the breadboard runs across the
panel's end with its fibre direction PERPENDICULAR to the panel grain.
The breadboard hides the panel end grain and keeps the wide panel flat,
while a row of long tenons + a continuous shallow tongue locate it.

The defining problem of a breadboard is WOOD MOVEMENT.  A wide panel
expands and contracts across its width with the seasons; the breadboard
(running across that width) does not.  If the breadboard were glued or
pinned solid along its whole length the panel would split.  The fix:

  * The panel is fixed to the breadboard at ONE point only — the CENTRE
    tenon, whose pin hole(s) are ROUND.  Everything moves relative to the
    centreline.
  * Every OTHER tenon's pin hole is a SLOT elongated ALONG the movement
    axis (the panel's width = the breadboard's length).  The slot grows
    longer the farther the tenon sits from the centreline, because that
    tenon has to travel farther as the panel swells/shrinks.
  * The pins themselves stay ROUND and are fixed in the breadboard.  The
    elongated clearance is modelled as a void cut in the PANEL tongue /
    tenon, so there is a visible gap on the movement sides of each
    off-centre pin.
  * Usually only the centre ~1/3 of the joint is glued; the rest is a
    dry, sliding fit.

Canonical orientation (axis-aligned; everything is parametric):

  Panel length / breadboard thickness   = X   (tenons extrude +X into BB)
  Panel width / breadboard length /
      WOOD-MOVEMENT axis / slot long axis = Y
  Panel thickness / breadboard height /
      pin axis                            = Z   (pins run through in Z)

The N tenons are spaced evenly along Y.  Each tenon's WIDER cross-section
dimension lies along Y (the breadboard's fibre direction), so the mating
mortises run WITH the breadboard grain rather than across it — the
grain-correct way to mortise the breadboard.  That long axis is taken
from ``sp.grain_vector(breadboard_body)`` rather than hardcoded, so the
template still does the right thing if the breadboard is modelled on a
different axis.

Build order (mirrors mortise_tenon / drawbore):
1. Continuous shallow tongue across the full panel width  → JOIN to panel
2. N deep tenons evenly spaced along the tongue            → JOIN to panel
3. Matching groove + N mortises in the breadboard          → CUT (keepTool)
4. Round pins (one per pin position), fixed in breadboard  → CUT panel+BB
5. Per-tenon clearance void in the panel tongue: ROUND at the centre
   tenon, SLOT (elongated in Y, length growing with |offset|) elsewhere

Parameters (see ``define_params`` for defaults):

  bb_thick    Breadboard thickness along the panel length (X depth of BB)
  bb_height   Breadboard height (Z) — normally == panel thickness
  tongue_d    Continuous tongue depth into the breadboard (X)
  tongue_t    Continuous tongue thickness (Z), centred in panel thickness
  tenon_d     Deep-tenon depth into the breadboard (X), > tongue_d
  tenon_w     Deep-tenon WIDTH along the breadboard fibre / Y (the WIDE
              cross-section dim — mortise runs with BB grain)
  tenon_t     Deep-tenon thickness (Z); usually == tongue_t
  n_tenons    Number of deep tenons across the breadboard (odd ⇒ a true
              centre tenon that the round hole fixes)
  pins_per_tenon  0 (glued / unpinned), 1 (one centred pin) or 2 (a pair
              straddling the tenon WIDTH, resisting racking — NOT in-line
              along the tenon depth)
  pin_dia     Pin diameter (round in the breadboard)
  pin_sp      Centre-to-centre spacing of the 2-pin pair (along Y)
  pin_mode    "through" (pin passes fully through the panel thickness,
              visible top & bottom) or "blind" (pin enters from the
              BOTTOM face and stops short of the TOP face — invisible
              from the top)
  pin_blind_remain  For "blind": material left below the TOP face (the
              pin stops this far short of the top)
  pin_inset   Pin distance from the breadboard's outer face, into the
              tenon depth (X)
  slot_clear  Half-slot clearance per inch of off-centre distance —
              the elongation each off-centre pin hole gains per unit of
              |Y offset| from the centreline (so the slot grows with
              distance from centre)
  slot_min    Minimum slot over-length even for the tenons nearest the
              centre (a small baseline movement allowance)

Usage::

    from woodworking.templates import breadboard as bbd

    bbd.define_params(params, prefix="bbd",
        tenon_w="2 in", n_tenons="3", pins_per_tenon="1")

    bbd.build(
        comp=top_comp,
        panel=top_body,
        breadboard=bb_body,
        panel_end_face=("x", +1),       # which panel end the BB caps
        panel_w_expr="top_w",           # panel width (Y span, movement axis)
        panel_t_expr="top_t",           # panel thickness (Z)
        end_x_expr="top_len",           # panel end-face X position
        y0_expr="0 in",                 # panel min-Y edge
        z0_expr="0 in",                 # panel bottom (min-Z) face
        n_tenons="bbd_n",
        pins_per_tenon="bbd_ppt",
        pin_mode="blind",
        name="BBE", ev=ev)
"""

import adsk.core
import adsk.fusion

from helpers import sp

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
VI = adsk.core.ValueInput.createByString
P3 = adsk.core.Point3D.create

METADATA = {
    "name": "breadboard",
    "category": "joinery",
    "extends": "mortise_tenon",
    "description": "Cross-grain end cap for wide panels with movement-slotted "
                   "pins — fixed at the centre, sliding everywhere else",
    "best_for": ["tabletops", "drop-leaf tops", "cabinet doors",
                 "wide solid-wood panels needing a flat, end-grain-hiding cap"],
    "not_for": ["narrow boards (no movement problem — a plain tenon is fine)",
                "plywood / MDF panels (no seasonal movement)"],
    "variants": {
        "through": {
            "description": "Pins pass fully through the panel thickness — "
                           "visible on the top and bottom faces",
            "best_for": ["traditional / exposed-joinery tables", "workbenches"],
        },
        "blind": {
            "description": "Pins enter from the BOTTOM and stop short of the "
                           "TOP — invisible from above",
            "best_for": ["fine furniture tops", "show surfaces"],
        },
    },
    "movement_rule": "Centre tenon pin hole ROUND (fixes the panel); every "
                     "other tenon pin hole SLOTTED along the panel-width axis, "
                     "length growing with distance from the centreline.",
    "params": {
        "tenon_w": "Deep-tenon width along breadboard grain (the WIDE dim)",
        "n_tenons": "Number of deep tenons across the breadboard",
        "pins_per_tenon": "0, 1 or 2 pins per tenon",
        "pin_mode": "through | blind",
    },
}


# ── Parameters ──────────────────────────────────────────────────────

def define_params(params, prefix="bbd",
                  bb_thick="1.5 in", bb_height="0.75 in",
                  tongue_d="0.375 in", tongue_t="0.25 in",
                  tenon_d="1.25 in", tenon_w="2 in", tenon_t="0.25 in",
                  n_tenons="3", pins_per_tenon="1",
                  pin_dia="0.3125 in",
                  pin_blind_remain="0.1875 in", pin_inset="0.5 in",
                  move_frac="0.015", pin_wall_min="0.0625 in"):
    """Define breadboard-end parameters (idempotent).

    Args:
        params: design.userParameters.
        prefix: Parameter name prefix (registry prefix is ``bbd_``).
        bb_thick: Breadboard thickness along the panel length (X).
        bb_height: Breadboard height (Z) — normally == panel thickness.
        tongue_d: Continuous tongue depth into the breadboard (X).
        tongue_t: Continuous tongue thickness (Z).
        tenon_d: Deep-tenon depth into the breadboard (X), > tongue_d.
        tenon_w: Deep-tenon width along the breadboard grain (Y, the WIDE
            cross-section dimension).
        tenon_t: Deep-tenon thickness (Z), usually == tongue_t.
        n_tenons: Number of deep tenons (count).
        pins_per_tenon: 0, 1 or 2 (count).
        pin_dia: Pin diameter.
        pin_blind_remain: Material left below the top face for blind pins.
        pin_inset: Pin distance from the breadboard outer face into the
            tenon depth (X).
        move_frac: Wood-movement clearance as a FRACTION of a tenon's distance
            from the panel centre — applied to BOTH the tenon mortise (each
            side) and the pin slot over-length, so a tenon and its pin move
            together. A true centre tenon (odd n) is at the centre ⇒ 0 ⇒ tight
            mortise + round pin = the fixed anchor the panel expands away from.
        pin_wall_min: Minimum wall left between a slot end and the tenon edge
            (guards against pins crowding the edge of a too-narrow tenon).

    Returns:
        Dict of short-label → full parameter names.
    """
    p = prefix
    specs = [
        (f"{p}_bb_t",     bb_thick,         "in", "Breadboard thickness (X)"),
        (f"{p}_bb_h",     bb_height,        "in", "Breadboard height (Z)"),
        (f"{p}_tongue_d", tongue_d,         "in", "Continuous tongue depth (X)"),
        (f"{p}_tongue_t", tongue_t,         "in", "Continuous tongue thickness (Z)"),
        (f"{p}_td",       tenon_d,          "in", "Deep-tenon depth (X)"),
        (f"{p}_tw",       tenon_w,          "in", "Deep-tenon width along BB grain (Y)"),
        (f"{p}_tt",       tenon_t,          "in", "Deep-tenon thickness (Z)"),
        (f"{p}_n",        n_tenons,         "",   "Number of deep tenons"),
        (f"{p}_ppt",      pins_per_tenon,   "",   "Pins per tenon (0/1/2)"),
        (f"{p}_pin_dia",  pin_dia,          "in", "Pin diameter"),
        (f"{p}_pin_rem",  pin_blind_remain, "in", "Blind-pin material below top"),
        (f"{p}_pin_in",   pin_inset,        "in", "Pin inset from BB outer face (X)"),
        (f"{p}_move_frac", move_frac,       "",   "Movement clearance / distance-from-centre"),
        (f"{p}_wall_min", pin_wall_min,     "in", "Min wall: slot end to tenon edge"),
    ]
    for pname, expr, unit, desc in specs:
        if not params.itemByName(pname):
            params.add(pname, VI(expr), unit, desc)

    return {
        "bb_t": f"{p}_bb_t", "bb_h": f"{p}_bb_h",
        "tongue_d": f"{p}_tongue_d", "tongue_t": f"{p}_tongue_t",
        "td": f"{p}_td", "tw": f"{p}_tw", "tt": f"{p}_tt",
        "n": f"{p}_n", "ppt": f"{p}_ppt",
        "pin_dia": f"{p}_pin_dia",
        "pin_rem": f"{p}_pin_rem", "pin_in": f"{p}_pin_in",
        "move_frac": f"{p}_move_frac", "wall_min": f"{p}_wall_min",
    }


# ── Build ───────────────────────────────────────────────────────────

def build(comp, panel, breadboard,
          panel_end_face, panel_w_expr, panel_t_expr,
          end_x_expr, y0_expr, z0_expr,
          n_tenons=None, pins_per_tenon=None, pin_mode="through",
          prefix="bbd", name="BBE", ev=None,
          panel_occ=None, bb_occ=None):
    """Build a complete breadboard-end joint.

    Builds, in order: the continuous shallow tongue + ``n_tenons`` deep
    tenons (JOINed to ``panel``); the matching groove + mortises in
    ``breadboard`` (CUT, keepTool); and round pins with round/slotted
    clearance holes per the wood-movement rules.

    The deep tenons are oriented so their WIDE dimension (``{prefix}_tw``)
    runs along the breadboard's fibre direction — read from
    ``sp.grain_vector(breadboard)`` — so the mortises run WITH the
    breadboard grain.  In the canonical axis-aligned layout that fibre
    direction is Y (the panel-width / movement axis); the template asserts
    this and otherwise raises so the caller knows the breadboard is
    modelled on an unexpected axis (escalate per the anchoring-complexity
    boundary — this template owns axis-aligned breadboards only).

    Args:
        comp: Component owning the new sketches/extrudes. Must be
            ``panel.parentComponent`` (tongue/tenons are JOINed into the
            panel intra-component; the breadboard CUT and pin CUTs route
            through ``sp.combine``, which handles cross-component cases).
        panel: The wide panel / tabletop body (grain along X). The tongue
            and tenons are JOINed into it.
        breadboard: The breadboard body (grain along Y). Receives the
            groove + mortises (CUT).
        panel_end_face: (axis, dir) of the panel end the breadboard caps.
            Canonically ("x", +1). Only the X axis is supported; the
            template raises otherwise.
        panel_w_expr: Panel width — the Y span / movement axis length.
        panel_t_expr: Panel thickness (Z).
        end_x_expr: X position of the panel end face (tenon shoulder).
        y0_expr: Panel minimum-Y edge (start of the width span).
        z0_expr: Panel bottom (minimum-Z) face position.
        n_tenons: Count expression (defaults to ``{prefix}_n``).
        pins_per_tenon: 0/1/2 expression (defaults to ``{prefix}_ppt``).
        pin_mode: "through" or "blind".
        prefix: Parameter prefix.
        name: Feature name prefix.
        ev: Evaluator function.
        panel_occ: Occurrence of the panel body (for assembly-context
            anchoring on non-root components). May be None.
        bb_occ: Occurrence of the breadboard body. May be None.

    Returns:
        Dict with keys: 'tongue', 'tenons' (list of bodies), 'tongue_join',
        'tenon_join', 'bb_cut', 'pins' (list of bodies), 'pin_cut',
        'clearance_cuts' (list of CombineFeatures), 'tenon_y' (list of
        tenon centre-Y floats), 'grain_axis' ('y').
    """
    if ev is None:
        ev = sp._make_ev()

    p = prefix
    face_ax, face_dir = panel_end_face
    if face_ax != "x":
        raise ValueError(
            "breadboard.build supports an X-axis panel end only "
            f"(got {face_ax!r}); see the anchoring-complexity boundary — "
            "escalate non-axis-aligned breadboards to a human.")

    n = int(ev(n_tenons if n_tenons is not None else f"{p}_n"))
    ppt = int(ev(pins_per_tenon if pins_per_tenon is not None
                 else f"{p}_ppt"))
    if n < 1:
        raise ValueError("n_tenons must be >= 1")
    if ppt not in (0, 1, 2):
        raise ValueError("pins_per_tenon must be 0, 1 or 2")
    if pin_mode not in ("through", "blind"):
        raise ValueError("pin_mode must be 'through' or 'blind'")

    # ── Grain-correct tenon orientation ─────────────────────────────
    # The tenon's WIDE dimension (tenon_w) must lie along the breadboard's
    # fibre direction so the mortises run WITH the breadboard grain.
    # The tongues insert into the breadboard along X, so the tenon's WIDE
    # cross-section dimension should run along the perpendicular axis most aligned
    # with the breadboard's fibre (docs/joinery/grain-and-strength.md) -- which
    # must be Y in the canonical layout.
    grain_axis = sp.grain_axis(breadboard)
    wide_axis = sp.tenon_wide_axis(breadboard, "x")
    if wide_axis != "y":
        raise ValueError(
            "breadboard grain must run along Y in the canonical layout "
            f"(detected grain {grain_axis!r}, tenon wide-axis {wide_axis!r}). The "
            f"tenon WIDTH ({p}_tw) is laid along the breadboard fibre; a non-Y "
            "breadboard means the panel is on an unexpected axis — escalate per "
            "the anchoring-complexity boundary.")

    # ── Numeric geometry ────────────────────────────────────────────
    pw = ev(panel_w_expr)              # panel width (Y span)
    pt = ev(panel_t_expr)             # panel thickness (Z)
    end_x = ev(end_x_expr)            # shoulder X (panel end face)
    y0 = ev(y0_expr)                  # panel min-Y
    z0 = ev(z0_expr)                  # panel bottom (min-Z)
    sgn = 1 if face_dir > 0 else -1   # tongue/tenons extrude in +X (sgn>0)

    tongue_t = ev(f"{p}_tongue_t")
    tenon_d = ev(f"{p}_td")
    tenon_t = ev(f"{p}_tt")

    # Tongue/tenon thicknesses are centred in the panel thickness.
    tongue_z0 = z0 + (pt - tongue_t) / 2
    tenon_z0 = z0 + (pt - tenon_t) / 2

    # Even tenon spacing across the panel width, inset by half a pitch
    # so the outermost tenons are not flush with the panel edges.
    pitch = pw / n
    tenon_y = [y0 + pitch * (i + 0.5) for i in range(n)]
    centre_i = (n - 1) // 2 if n % 2 == 1 else None  # odd ⇒ true centre

    # Convenient expression strings (so dimensions stay parametric).
    def cm(v):
        return f"{v} cm"

    end_x_e = end_x_expr if isinstance(end_x_expr, str) else cm(end_x)

    result = {"tenon_y": list(tenon_y), "grain_axis": grain_axis}

    # ── 1+2. Continuous shallow tongue + N deep tenons ──────────────
    # Construction plane positioned AT the end face's X (parametric via end_x_e),
    # built off the component yZ plane. (A plane built *from* the face — or sketching
    # on the body face itself — is coincident with the face, so the full-width tongue
    # picks up the face's boundary edges and Fusion's profile detection HANGS. This
    # plane carries no body-edge association, so it's safe; its normal is +X.)
    # The plane normal is +X, so sign the extrude distance by face_dir to push the
    # tongue/tenons OUTWARD into the breadboard (+X for the +X end, -X for the other).
    # NOTE: the long-standing "tongue lands off the board" symptom was NOT a wrong
    # extrude direction here -- it was a sign-flip in sp.sketch_rect_model /
    # sketch_slot_model origin-mode dims, where a NEGATIVE model coordinate (panel
    # centred on Y=0 ⇒ y0 = -panel_w/2) was mirrored across the axis. Fixed by
    # abs()-ing those distance dims in the helpers. Interference + contact checks
    # do NOT catch it (a mirrored tongue still butts the end with 0 interference);
    # verify by body span / bbox instead.
    end_pl = sp.off_plane(comp, comp.yZConstructionPlane, end_x_e, f"{name}_EndPl")
    # Extrude OUTWARD (away from the panel, into the breadboard): +X for the +X end,
    # -X for the -X end. The plane normal is +X, so sign the distance by face_dir.
    out = (lambda e: e) if face_dir > 0 else (lambda e: "0 in - (%s)" % e)

    _, tongue_prof = sp.sketch_rect_model(
        comp, end_pl, (end_x_e, y0_expr, cm(tongue_z0)),
        {"y": panel_w_expr, "z": f"{p}_tongue_t"},
        f"{name}_TongueSk", ev=ev)
    tongue_body = sp.ext_new(comp, tongue_prof, out(f"{p}_tongue_d"),
                             f"{name}_Tongue").bodies.item(0)
    tongue_body.name = f"{name}_Tongue"
    result["tongue"] = tongue_body

    # Tenon i seats at y0 + (i + 0.5) * (panel_w / n); rect min-Y corner is that
    # centre minus half the tenon width. Fully parametric (re-spaces with panel_w
    # or tenon_w). WIDE dim (tw) on Y = breadboard grain; thickness (tt) on Z.
    def ty0_expr(i):
        return (f"({y0_expr}) + ({i} + 0.5) * ({panel_w_expr})/({n}) "
                f"- ({p}_tw)/2")

    tenon_bodies = []
    for i, yc in enumerate(tenon_y):
        _, t_prof = sp.sketch_rect_model(
            comp, end_pl, (end_x_e, ty0_expr(i), cm(tenon_z0)),
            {"y": f"{p}_tw", "z": f"{p}_tt"},
            f"{name}_T{i}Sk", ev=ev)
        tb = sp.ext_new(comp, t_prof, out(f"{p}_td"), f"{name}_T{i}").bodies.item(0)
        tb.name = f"{name}_Tenon{i}"
        tenon_bodies.append(tb)
    result["tenons"] = tenon_bodies

    # ── 3. Groove + OVERSIZED mortises in the breadboard, then seat ──
    # The continuous tongue is an EXACT groove fit (keepTool=True): it locates
    # the panel and resists cupping, but it still SLIDES along the groove in Y,
    # so it does NOT lock wood movement.
    # The deep tenons, by contrast, must be free to slide as the panel
    # expands/contracts across its grain (Y) — so each tenon mortise is cut
    # WIDER than its tenon by the movement clearance on EACH side (rule 9:
    # never lock a wide panel cross-grain). The mortise tools are oversized
    # copies of the tenons (consumed by the cut); the ACTUAL tenons are JOINed
    # to the panel and float in the oversized pockets. A true centre tenon
    # (odd n) gets ZERO clearance ⇒ its mortise == its tenon (tight) ⇒ it is
    # the anchor the panel moves away from.
    result["groove_cut"] = sp.combine(breadboard, [tongue_body], CUT, True,
                                      f"{name}_GrooveCut")
    mortise_tools = []
    for i in range(n):
        mv = _mv_expr(i, n, panel_w_expr, p)
        _, mt_prof = sp.sketch_rect_model(
            comp, end_pl,
            (end_x_e, f"({ty0_expr(i)}) - ({mv})", cm(tenon_z0)),
            {"y": f"({p}_tw) + 2 * ({mv})", "z": f"{p}_tt"},
            f"{name}_M{i}Sk", ev=ev)
        mt = sp.ext_new(comp, mt_prof, out(f"{p}_td"),
                        f"{name}_M{i}").bodies.item(0)
        mt.name = f"{name}_Mortise{i}"
        mortise_tools.append(mt)
    result["mortise_cut"] = sp.combine(breadboard, mortise_tools, CUT, False,
                                       f"{name}_MortiseCut")
    result["tongue_join"] = sp.combine(panel, [tongue_body], JOIN, False,
                                       f"{name}_TongueJoin")
    result["tenon_join"] = sp.combine(panel, tenon_bodies, JOIN, False,
                                      f"{name}_TenonJoin")

    # ── 4 & 5. Pins + round/slotted clearance holes ─────────────────
    result["pins"] = []
    result["clearance_cuts"] = []
    if ppt > 0:
        pins, clr_cuts = _build_pins(
            comp, panel, breadboard, p, name, ev,
            tenon_y, centre_i, ppt, pin_mode,
            end_x=end_x, end_x_e=end_x_e, sgn=sgn,
            z0=z0, z0_expr=z0_expr, panel_t_expr=panel_t_expr,
            tenon_d=tenon_d, y0=y0, y0_expr=y0_expr,
            panel_w_expr=panel_w_expr, n=n,
            panel_occ=panel_occ, bb_occ=bb_occ)
        result["pins"] = pins
        result["clearance_cuts"] = clr_cuts

    return result


# ── Pins + movement holes ───────────────────────────────────────────

def _build_pins(comp, panel, breadboard, p, name, ev,
                tenon_y, centre_i, ppt, pin_mode,
                end_x, end_x_e, sgn, z0, z0_expr, panel_t_expr,
                tenon_d, y0, y0_expr, panel_w_expr, n, panel_occ, bb_occ):
    """Build round pins (fixed in the breadboard) and the matching
    round/slotted clearance holes in the panel tongue/tenons.

    For each tenon:
      * Place ``ppt`` pins at the CENTRES of equal cells across the tenon
        width (1 ⇒ one centred pin; 2 ⇒ quarter-points). Deriving the offset
        from the tenon width (not a fixed spacing) keeps a pin pair from
        crowding the tenon edges; a wall guard raises if a slot would still
        reach the edge.
      * The pin is a ROUND cylinder along Z, fixed in the breadboard:
          - "through": full panel thickness (visible top & bottom).
          - "blind":   enters from the BOTTOM (min-Z) face and stops
            ``{p}_pin_rem`` short of the TOP — invisible from the top.
      * Clearance void in the PANEL: a ROUND hole where there is no movement
        (a true centre tenon — the anchor); a SLOT elongated along Y
        elsewhere, the slot over-length = 2 * the SAME wood-movement clearance
        the tenon's mortise uses, so the pin travels exactly as far as the
        tenon slides (they never fight).

    Returns ([pin_bodies], [clearance_combine_features]).
    """
    pin_x = end_x + sgn * (tenon_d - ev(f"{p}_pin_in"))   # pin X position
    pin_x_e = f"({end_x_e}) + {sgn} * ({p}_td - {p}_pin_in)"
    pin_dia = ev(f"{p}_pin_dia")
    tenon_w = ev(f"{p}_tw")
    wall_min = ev(f"{p}_wall_min")

    # Pin extrude (along Z), from the BOTTOM (min-Z) face upward.
    #   "through" → full panel thickness (pin visible top & bottom).
    #   "blind"   → stops {p}_pin_rem short of the TOP (invisible above).
    if pin_mode == "through":
        pin_depth_e = panel_t_expr
    else:  # blind
        pin_depth_e = f"({panel_t_expr}) - {p}_pin_rem"
    clr_depth_e = pin_depth_e

    pins = []
    clr_cuts = []
    pin_pl = sp.off_plane(comp, comp.xYConstructionPlane, z0_expr,
                          f"{name}_PinPl")

    for i, yc in enumerate(tenon_y):
        mv = _mv_expr(i, n, panel_w_expr, p)   # movement clearance (Y), one side
        mv_val = ev(mv)                        # numeric clearance
        for k in range(ppt):
            cell = (k + 0.5) / ppt - 0.5       # fraction of tenon_w from centre
            yoff = cell * tenon_w              # numeric Y offset within the tenon
            pin_y_e = _pin_y_expr(i, k, ppt, n, y0_expr, panel_w_expr, p)

            # Wall guard: the slot (or round hole) must leave a wall to the
            # tenon edge. half-slot = pin_dia/2 + mv (mv = 0 ⇒ round hole).
            slot_half = pin_dia / 2 + mv_val
            outer = abs(yoff) + slot_half
            if outer > tenon_w / 2 - wall_min + 1e-6:
                raise ValueError(
                    f"{name}: pin {k+1}/{ppt} of tenon {i} crowds the tenon "
                    f"edge — needs {outer + wall_min:.3f} cm half-width but the "
                    f"tenon half-width is only {tenon_w/2:.3f} cm. Widen "
                    f"{p}_tw, or reduce {p}_ppt / {p}_pin_dia / {p}_move_frac.")

            # ── Round pin, fixed in the breadboard ──
            pin_sk = comp.sketches.add(pin_pl)
            pin_sk.name = f"{name}_Pin{i}_{k}Sk"
            m2s = pin_sk.modelToSketchSpace
            ctr = m2s(P3(pin_x, yc + yoff, z0))
            circ = pin_sk.sketchCurves.sketchCircles.addByCenterRadius(
                P3(ctr.x, ctr.y, 0), pin_dia / 2)
            d = pin_sk.sketchDimensions
            g = circ.centerSketchPoint.geometry
            d.addRadialDimension(
                circ, P3(g.x + 0.5, g.y, 0)
            ).parameter.expression = f"{p}_pin_dia / 2"
            orient = sp.probe_orientations(pin_sk, pin_x, yc + yoff, z0)
            # Position the pin centre with two origin dims (root sketch on
            # the XY plane → origin dims are valid; reanchor when non-root).
            d.addDistanceDimension(
                pin_sk.originPoint, circ.centerSketchPoint, orient["x"],
                P3(g.x / 2, g.y - 1, 0)
            ).parameter.expression = f"abs({pin_x_e})"
            d.addDistanceDimension(
                pin_sk.originPoint, circ.centerSketchPoint, orient["y"],
                P3(g.x - 1, g.y / 2, 0)
            ).parameter.expression = f"abs({pin_y_e})"
            if panel_occ is not None or bb_occ is not None:
                anchor_body = breadboard if bb_occ is not None else panel
                anchor_occ = bb_occ if bb_occ is not None else panel_occ
                sp.reanchor(pin_sk, anchor_body, anchor_occ, "z", -1,
                            (pin_x_e, pin_y_e, z0_expr))
            pin_ext = sp.ext_new(comp, sp.smallest_profile(pin_sk),
                                 pin_depth_e, f"{name}_Pin{i}_{k}")
            pin_body = pin_ext.bodies.item(0)
            pin_body.name = f"{name}_Pin{i}_{k}"
            pins.append(pin_body)
            # Round hole in the BREADBOARD (the pin is fixed there — press fit).
            sp.combine(breadboard, [pin_body], CUT, True, f"{name}_PinBB{i}_{k}")

            # ── Clearance void in the panel tongue/tenon ──
            # No movement (mv ≈ 0 ⇒ a true centre tenon) ⇒ ROUND registration
            # hole that pins the panel. Otherwise a SLOT elongated along Y by
            # 2*mv so the pin can travel ±mv as the tenon slides.
            if mv_val < 1e-9:
                clr_sk = comp.sketches.add(pin_pl)
                clr_sk.name = f"{name}_Clr{i}_{k}Sk"
                m2 = clr_sk.modelToSketchSpace
                c2 = m2(P3(pin_x, yc + yoff, z0))
                cc = clr_sk.sketchCurves.sketchCircles.addByCenterRadius(
                    P3(c2.x, c2.y, 0), pin_dia / 2)
                d2 = clr_sk.sketchDimensions
                gg = cc.centerSketchPoint.geometry
                d2.addRadialDimension(
                    cc, P3(gg.x + 0.5, gg.y, 0)
                ).parameter.expression = f"{p}_pin_dia / 2"
                o2 = sp.probe_orientations(clr_sk, pin_x, yc + yoff, z0)
                d2.addDistanceDimension(
                    clr_sk.originPoint, cc.centerSketchPoint, o2["x"],
                    P3(gg.x / 2, gg.y - 1, 0)
                ).parameter.expression = f"abs({pin_x_e})"
                d2.addDistanceDimension(
                    clr_sk.originPoint, cc.centerSketchPoint, o2["y"],
                    P3(gg.x - 1, gg.y / 2, 0)
                ).parameter.expression = f"abs({pin_y_e})"
                if panel_occ is not None:
                    sp.reanchor(clr_sk, panel, panel_occ, "z", -1,
                                (pin_x_e, pin_y_e, z0_expr))
                clr_ext = sp.ext_new(comp, sp.smallest_profile(clr_sk),
                                     clr_depth_e, f"{name}_Clr{i}_{k}")
                clr_tool = clr_ext.bodies.item(0)
                clr_tool.name = f"{name}_Clr{i}_{k}"
            else:
                # Slot long axis along Y (movement axis); over-length = 2*mv.
                slot_long_expr = f"{p}_pin_dia + 2 * ({mv})"
                clr_sk, clr_prof = sp.sketch_slot_model(
                    comp, pin_pl, (pin_x_e, pin_y_e, z0_expr),
                    long_model_axis="y",
                    long_expr=slot_long_expr,
                    short_expr=f"{p}_pin_dia",
                    name=f"{name}_Slot{i}_{k}Sk", ev=ev,
                    anchor=_slot_anchor(panel, panel_occ, pin_x_e, pin_y_e,
                                        z0_expr, slot_long_expr, p))
                clr_ext = sp.ext_new(comp, clr_prof, clr_depth_e,
                                     f"{name}_Slot{i}_{k}")
                clr_tool = clr_ext.bodies.item(0)
                clr_tool.name = f"{name}_Slot{i}_{k}"

            # CUT the clearance void into the panel (consume the tool).
            cut = sp.combine(panel, [clr_tool], CUT, False,
                             f"{name}_ClrCut{i}_{k}")
            clr_cuts.append(cut)

    return pins, clr_cuts


# ── Anchor builders (non-root component support) ────────────────────

def _panel_anchor(panel, panel_occ, face_ax, face_dir, model_origin):
    """Anchor dict for a tongue/tenon rect on the panel end face.

    Returns None on a root panel (origin dims are valid there). For a
    non-root panel, anchors the rectangle to the panel's end face so the
    sketch passes the deps validator (rules 1-3). Uses corner ``which=1``
    + ``size_far`` so no dim touches the (possibly origin-coincident)
    seed corner — see sketch_rect_model's anchor docs.
    """
    if panel_occ is None:
        return None
    return {
        "parent_body": panel,
        "parent_occ": panel_occ,
        "face_axis": face_ax,
        "face_dir": face_dir,
        "anchor_xyz": model_origin,
        "off1": ("y", "0 in"),
        "off2": ("z", "0 in"),
        "which": 1,
        "size_far": True,
    }


def _slot_anchor(panel, panel_occ, cx_e, cy_e, cz_e, long_expr, p):
    """Anchor dict for a movement slot on the panel bottom face.

    None on a root panel. On a non-root panel, anchors the slot's
    reference arc centre to the panel's bottom (min-Z) face.
    """
    if panel_occ is None:
        return None
    return {
        "parent_body": panel,
        "parent_occ": panel_occ,
        "face_axis": "z",
        "face_dir": -1,
        "anchor_xyz": (cx_e, cy_e, cz_e),
        "off": (("x", "0 in"),
                ("y", f"({long_expr} - {p}_pin_dia) / 2")),
    }


# ── Parametric position-expression helpers ──────────────────────────

def _mv_expr(i, n, panel_w_expr, p):
    """Per-tenon wood-movement clearance (Y), ONE side.

    = (tenon i's distance from the panel centre) * move_frac. A true centre
    tenon (odd n) is AT the centre ⇒ 0 ⇒ tight mortise + round pin = the
    anchor the panel expands away from. Fully parametric in panel_w, so the
    clearance scales with panel width (movement is proportional to width).
    """
    frac = abs((i + 0.5) / n - 0.5)   # |offset from centre| as a fraction of width
    if frac == 0:
        return "0 in"
    return f"({frac} * ({panel_w_expr}) * {p}_move_frac)"


def _tenon_ctr_expr(i, n, y0_expr, panel_w_expr):
    """Parametric Y centre of tenon i:  y0 + (i + 0.5) * panel_w / n."""
    return f"(({y0_expr}) + ({i} + 0.5) * ({panel_w_expr}) / ({n}))"


def _pin_y_expr(i, k, ppt, n, y0_expr, panel_w_expr, p):
    """Parametric Y of pin k (of ppt) in tenon i — the centre of its cell
    within the tenon width (derived spacing keeps slots clear of the edges).
    ppt==1 → centred; ppt==2 → ±tenon_w/4 (quarter-points)."""
    ctr = _tenon_ctr_expr(i, n, y0_expr, panel_w_expr)
    cell = (k + 0.5) / ppt - 0.5      # fraction of tenon_w from the tenon centre
    if cell == 0:
        return ctr
    return f"{ctr} + ({cell} * {p}_tw)"
