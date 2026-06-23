"""First-order strength estimator for mortise-and-tenon joinery.

PURPOSE
  Given a tenon's SIZE, estimate the joint's load capacity in every direction,
  name the governing failure mode (and whether it needs glue), and surface design
  guidance. It guides JOINERY DESIGN — compare directions, find the weak axis,
  size for the expected loads — NOT to certify a structure. Numbers are
  first-order (mean clear-wood strengths + simple, literature-backed failure
  models); treat them as RELATIVE, apply your own safety factor.

  Pure Python (only `math`) — runs and unit-tests anywhere, no Fusion dependency:
      from helpers.sp.joint_strength import estimate_mortise_tenon, summarize

THE MODEL (tenon-local frame)
  a = insertion axis; the tenon is embedded a GLUE length L (proud excluded).
  w = cross-section dim ALONG the mortise grain  -> the (w x L) faces are
      long-grain-to-long-grain GLUE CHEEKS — the joint's tension strength.
  t = cross-section dim ACROSS the mortise grain -> the (t x L) faces meet END
      grain mortise walls (weaker glue).

  Capacities (INCHES, psi -> lbf, moments in-lbf):
    withdrawal (tension //a)     cheek glue + end-grain glue (Eckelman L^0.89 depth)
    pin_withdrawal (if pegged)   peg via EYM: min(double-shear, bending, bearing)
    thrust (compression //a)     tenon end / shoulder bearing
    shear_along_w (force //w)    BEARING on end-grain walls (GLUE-FREE) vs tenon shear
    shear_along_t (force //t)    BEARING on long-grain walls (GLUE-FREE) vs tenon shear
    bending_about_w / _about_t   min(embedment bearing couple, tenon section)
    torsion (twist about a)      rectangular-section torsional shear (approx)

  EVIDENCE BASE (researched):
   - Long-grain glue is WOOD-LIMITED: a sound long-grain line fails in the wood, so
     cheek glue is capped at the wood's shear-parallel strength (tau), NOT the
     adhesive datasheet psi (PVA ~3400-4200, ASTM D905). fl = tau.
   - END-grain glue is weak but NOT zero: ~25% of long-grain is the documented
     CEILING (USDA FPL Wood Handbook: butt joint "not more than ~25%"); raw/unsized
     ~15%. Default 0.15, or 0.25 with `sized=True` (end-grain priming). fe = k*fl.
   - OFF-AXIS strength uses HANKINSON, N = P*Q/(P*sin^n + Q*cos^n), n~2 (NOT a
     linear cos/sin blend, which over-predicts mid-angles ~2-4x). glue_shear_per_area.
   - WITHDRAWAL is SUBLINEAR in depth (Eckelman, Purdue: F ~ width * depth^0.89) —
     effective glue depth L^0.89; diminishing returns past ~2.5x the tenon width.
   - PEGS/drawbore pins follow the EUROPEAN YIELD MODEL: capacity = min over yield
     modes (wood bearing/embedment vs peg bending hinge Md = Fb*D^3/6 vs peg shear),
     plus a brittle RELISH TEAR-OUT check (peg end distance should be >= 4*D).
     Drawbore is prestress only — it adds no ultimate capacity.

  Three traps the glue/fiber rule alone misses, still encoded:
   1. Tenon SECTION (w*t) sets shear/torsion and the bending CAP — a thin slice has
      max glue yet shears/snaps.
   2. Depth grows glue (now ~L^0.89) + bending lever (~L^2) until the section governs
      bending; past L* = t*sqrt(MOR/Cperp) deeper is diminishing returns.
   3. Through proud adds NO glue (tusk -> mechanical pull-out); blind needs a
      mortise-bottom wall (depth = glue length, not mortise depth).

  GLUE carries pull-out; BEARING (glue-free) carries transverse / racking loads —
  a stretcher pushed to the floor holds because the legs' inner end grain bears the
  tenon's side. NOT modeled as numbers (flagged): wedge flare, glue-line quality
  knockdown, moisture/duration, defects.
"""
import math

# Approximate clear-wood mean strengths, psi (~12% MC; USDA Wood Handbook order of
# magnitude) + specific gravity G. For ESTIMATION / relative comparison only.
#             shear//   comp//   comp_|_  tens_|_   MOR      G
SPECIES = {
    "white_oak":    dict(shear=2000, comp_par=7440, comp_perp=1070, tens_perp=800, mor=15200, G=0.68),
    "red_oak":      dict(shear=1780, comp_par=6760, comp_perp=1010, tens_perp=800, mor=14300, G=0.63),
    "hard_maple":   dict(shear=2330, comp_par=7830, comp_perp=1470, tens_perp=760, mor=15800, G=0.63),
    "black_walnut": dict(shear=1370, comp_par=7580, comp_perp=1010, tens_perp=690, mor=14600, G=0.55),
    "cherry":       dict(shear=1700, comp_par=7110, comp_perp=690,  tens_perp=570, mor=12300, G=0.50),
    "white_ash":    dict(shear=1950, comp_par=7410, comp_perp=1160, tens_perp=700, mor=15000, G=0.60),
    "douglas_fir":  dict(shear=1130, comp_par=7230, comp_perp=800,  tens_perp=340, mor=12400, G=0.48),
    "soft_pine":    dict(shear=900,  comp_par=4800, comp_perp=440,  tens_perp=300, mor=9600,  G=0.42),
    "hardwood":     dict(shear=1800, comp_par=7000, comp_perp=1050, tens_perp=700, mor=14000, G=0.60),
    "softwood":     dict(shear=1050, comp_par=5200, comp_perp=500,  tens_perp=330, mor=10500, G=0.42),
}

END_GRAIN_GLUE_UNSIZED = 0.15   # raw end grain ~15% of long-grain
END_GRAIN_GLUE_SIZED = 0.25     # end-grain PRIMED/SIZED -> ~25% ceiling (FPL Wood Handbook)
ECKELMAN_DEPTH_EXP = 0.89       # withdrawal ~ depth^0.89 (sublinear; Eckelman, Purdue)


def glue_shear_per_area(angle_to_grain_deg, species="hardwood",
                        end_grain_glue=END_GRAIN_GLUE_UNSIZED, n=2.0):
    """Per-area glue/strength (psi) for a face at an angle to the LONG grain, via
    HANKINSON's formula (the standard off-axis interpolation for wood):

        N = P*Q / (P*sin^n(x) + Q*cos^n(x)),   P = fl (x=0, long), Q = fe (x=90, end)

    x = angle of the face to the grain: 0 = long-grain face -> fl, 90 = end-grain
    face -> fe. n ~ 2 (use 1.5 for tension/bending, 2.5 for bearing). This REPLACES
    the older linear `fl*cos + fe*sin` blend, which over-predicts mid-angles ~2-4x.
    """
    m = SPECIES[species]
    fl = m["shear"]
    fe = end_grain_glue * fl
    x = math.radians(angle_to_grain_deg)
    denom = fl * math.sin(x) ** n + fe * math.cos(x) ** n
    return fl * fe / denom if denom > 0 else fl


def estimate_mortise_tenon(width, thickness, depth, species="hardwood",
                           through=False, proud=0.0, sized=False, end_grain_glue=None,
                           pins=0, pin_dia=0.0, pin_end_distance=None, peg_species=None,
                           wedged=False, tusked=False):
    """Estimate M&T capacities from the tenon size. Lengths in INCHES.

    width (w)        cross-section dim ALONG the mortise grain (the glue cheeks)
    thickness (t)    cross-section dim ACROSS the mortise grain
    depth (L)        GLUE-engaged embedded length (EXCLUDE through-proud)
    species          key into SPECIES
    through/proud    through tenon? how far proud (proud has no glue)
    sized            end-grain glue surfaces primed/sized (-> 0.25, else 0.15)
    end_grain_glue   override the end-grain fraction directly (else from `sized`)
    pins, pin_dia    drawbore/peg count + diameter (mechanical pull-out, EYM)
    pin_end_distance peg hole -> tenon end, in (for the relish tear-out check)
    peg_species      peg wood (else = mortise species)
    wedged/tusked    qualitative reinforcement flags

    Returns a dict: 'capacities' {mode: {value, unit, mechanism}}, 'cross_section',
    'glue_area_longgrain', 'effective_glue_depth', 'depth_limit_bending',
    'pin_modes', 'notes', 'inputs'.
    """
    if min(width, thickness, depth) <= 0:
        raise ValueError("width, thickness, depth must be > 0")
    m = SPECIES.get(species)
    if m is None:
        raise ValueError("unknown species %r; choose from %s"
                         % (species, ", ".join(sorted(SPECIES))))
    w, t, L = float(width), float(thickness), float(depth)
    tau, cpar, cperp, mor = m["shear"], m["comp_par"], m["comp_perp"], m["mor"]
    if end_grain_glue is None:
        end_grain_glue = END_GRAIN_GLUE_SIZED if sized else END_GRAIN_GLUE_UNSIZED
    fl, fe = tau, end_grain_glue * tau           # long-grain (wood-limited) / end-grain glue

    area = w * t
    # Eckelman: withdrawal is sublinear in depth -> effective glue depth L^0.89
    # (capped so a shallow tenon never gets >100% efficiency).
    Leff = L if L <= 1.0 else L ** ECKELMAN_DEPTH_EXP
    cheek = 2.0 * w * Leff                        # long-grain cheek glue (effective)
    side = 2.0 * t * Leff                         # end-grain wall glue (effective)

    # 1. Withdrawal (tension): glue only. (Glue cheeks are wood-limited: fl = tau.)
    glue = cheek * fl + side * fe

    # 1b. Pegs (drawbore/pinned): EYM = min over yield modes; plus relish tear-out.
    pin_modes = {}
    pin_withdrawal = 0.0
    pin_govern = None
    if pins and pin_dia:
        pm = SPECIES.get(peg_species, m)
        tau_peg, Fyb, G = pm["shear"], pm["mor"], m["G"]
        Fe = 11200.0 * G                          # NDS dowel-bearing // grain, psi
        Ap = math.pi * pin_dia ** 2 / 4.0
        mode_shear = 2.0 * Ap * tau_peg           # peg in double shear, per peg
        mode_bend = 2.0 * pin_dia ** 2 * math.sqrt(Fe * Fyb / 3.0)  # EYM mode IV (2 hinges)
        mode_bear = Fe * pin_dia * t              # peg bears across the tenon thickness
        per_peg = min(mode_shear, mode_bend, mode_bear)
        pin_govern = ("peg shear" if per_peg == mode_shear else
                      "peg bending (2 hinges)" if per_peg == mode_bend else "wood bearing")
        pin_withdrawal = pins * per_peg
        pin_modes = {"peg_double_shear": mode_shear, "peg_bending_modeIV": mode_bend,
                     "wood_bearing": mode_bear, "governing": pin_govern}
        if pin_end_distance is not None:
            tear = pins * 2.0 * pin_end_distance * t * tau   # relish plug, 2 shear planes
            pin_modes["relish_tearout"] = tear

    # 2. Thrust (compression along axis): tenon end (floor; shoulder carries more).
    thrust = area * cpar

    # 3. Transverse force: GLUE-FREE bearing on the mortise walls vs tenon shear.
    tenon_shear = area * tau
    bear_w = t * L * cpar                          # along w -> end-grain walls (strong)
    bear_t = w * L * cperp                         # along t -> long-grain walls (weak)
    shear_w = min(bear_w, tenon_shear)
    shear_t = min(bear_t, tenon_shear)

    # 4. Bending: embed bearing couple vs tenon section.
    m_embed_w, m_sect_w = cperp * w * L ** 2 / 6.0, mor * w * t ** 2 / 6.0
    m_embed_t, m_sect_t = cpar * t * L ** 2 / 6.0, mor * t * w ** 2 / 6.0
    bend_w, bend_t = min(m_embed_w, m_sect_w), min(m_embed_t, m_sect_t)

    # 5. Torsion.
    a_, b_ = max(w, t), min(w, t)
    torsion = (1.0 / (3.0 + 1.8 * (b_ / a_))) * a_ * b_ ** 2 * tau

    L_star = t * math.sqrt(mor / cperp)

    notes = ["Tenon SECTION = %.2f in^2 (w*t): shear, torsion and the bending CAP "
             "scale with it — a thin tenon stays weak no matter the glue area." % area]
    notes.append("Pull-out is GLUE; long-grain cheeks are WOOD-limited (fl=%d psi, "
                 "not adhesive psi); end grain at %.0f%% (%s). Withdrawal ~depth^0.89 "
                 "(Eckelman): effective glue depth %.2f in of %.2f — diminishing returns "
                 "past ~%.1f in (2.5x width)." % (
                     tau, end_grain_glue * 100, "SIZED" if (sized or end_grain_glue >= 0.2) else "raw",
                     Leff, L, 2.5 * w))
    notes.append("Transverse forces are GLUE-FREE bearing: along grain (shear_along_w) "
                 "on strong END grain (C//=%d); across (shear_along_t) on weak LONG grain "
                 "(C_|_=%d)." % (cpar, cperp))
    if pins and pin_dia:
        notes.append("Peg pull-out via EYM = min(shear %0.0f, bending %0.0f, bearing %0.0f) "
                     "= %0.0f lbf/peg, governed by %s. Glue and peg do NOT add — glue "
                     "carries first (stiffer), the peg is the backstop (or the whole joint "
                     "if unglued/drawbored)." % (mode_shear, mode_bend, mode_bear, per_peg, pin_govern))
        if pin_end_distance is not None and pin_end_distance < 4.0 * pin_dia:
            notes.append("BRITTLE: peg end distance %.2f in < 4xD (%.2f in) — the relish "
                         "can tear out the tenon end; move the peg back." % (pin_end_distance, 4 * pin_dia))
    if wedged:
        notes.append("Wedged: flared tenon adds MECHANICAL, glue-independent withdrawal — "
                     "quantify it with estimate_wedged_tenon() (interlock bounded by mortise "
                     "split / flare crush; the dry floor a plain M&T lacks).")
    if tusked:
        notes.append("Tusked: withdrawal is mechanical (tusk bears the far face).")
    notes.append("Off-axis grain? weight each face with glue_shear_per_area(angle) "
                 "(Hankinson). Bending(about w) is %s past L* ~%.2f in." % (
                     "tenon-limited" if bend_w == m_sect_w else "bearing-limited", L_star))

    def cap(v, unit, mech):
        return {"value": v, "unit": unit, "mechanism": mech}

    caps = {
        "withdrawal_tension": cap(glue, "lbf", "GLUE: cheeks (wood-limited) + end-grain"),
        "thrust_compression": cap(thrust, "lbf", "tenon end / shoulder bearing"),
        "shear_along_w": cap(shear_w, "lbf",
                             ("end-grain bearing" if bear_w <= tenon_shear else "tenon shear")
                             + " (GLUE-FREE) — along grain, e.g. stretcher->floor"),
        "shear_along_t": cap(shear_t, "lbf",
                             ("long-grain bearing" if bear_t <= tenon_shear else "tenon shear")
                             + " (GLUE-FREE) — across grain"),
        "bending_about_w": cap(bend_w, "in-lbf", "tenon section" if bend_w == m_sect_w else "embedment bearing"),
        "bending_about_t": cap(bend_t, "in-lbf", "tenon section" if bend_t == m_sect_t else "embedment bearing"),
        "torsion": cap(torsion, "in-lbf", "rectangular torsional shear (approx)"),
    }
    if pin_withdrawal:
        caps["pin_withdrawal"] = cap(pin_withdrawal, "lbf", "peg (EYM min): " + pin_govern)

    return {
        "inputs": dict(width=w, thickness=t, depth=L, species=species, through=through,
                       proud=proud, sized=sized, end_grain_glue=end_grain_glue, pins=pins,
                       pin_dia=pin_dia, pin_end_distance=pin_end_distance, peg_species=peg_species,
                       wedged=wedged, tusked=tusked),
        "cross_section": area,
        "glue_area_longgrain": cheek,
        "effective_glue_depth": Leff,
        "depth_limit_bending": L_star,
        "pin_modes": pin_modes,
        "capacities": caps,
        "notes": notes,
    }


def mortise_tenon_flags(width, thickness, depth, species="hardwood", through=False,
                        proud=0.0, sized=False, expected=None, thin_ratio=0.25):
    """Load-INDEPENDENT red-flag check for a mortise-and-tenon, given the tenon SIZE
    (inches). PURE — the shared core behind BOTH the build-time gate (which measures
    the tenon body) and the declarative registry check (which reads the dims from
    model.json). No Fusion dependency, so it unit-tests offline.

    Flags a designer should never ship:
      * thin slice (t < ``thin_ratio`` x w) -> the tenon's own shear/bending governs
        even with maximal glue area (the "don't optimize glue to a sliver" trap),
      * very thin tenon (t < 3/16 in) -> fragile to cut and shear-weak,
      * OVERLOADED <dir> when ``expected={capacity_name: load_lbf}`` exceeds capacity.

    Grain ORIENTATION is a geometric check (it needs the bodies) and lives in
    ``mating.validate_joint_strength`` / ``validate_tenon_grain`` — not here.

    Returns {flags, est, weakest, utilization}.
    """
    est = estimate_mortise_tenon(width, thickness, depth, species=species,
                                 through=through, proud=proud, sized=sized)
    caps = est["capacities"]
    w, t = float(width), float(thickness)

    flags = []
    if t < thin_ratio * w:
        flags.append("thin slice: thickness %.2f in < %.2f x width (%.2f in) -> the "
                     "tenon's own shear/bending governs even with full glue" % (
                         t, thin_ratio, w))
    if t < 0.1875:
        flags.append("very thin tenon (t=%.2f in): fragile to cut and shear-weak" % t)

    forces = {k: v["value"] for k, v in caps.items() if v["unit"] == "lbf"}
    weakest = min(forces, key=forces.get) if forces else None
    util = {}
    if expected:
        for k, load in expected.items():
            c = caps.get(k)
            if c and load > 0:
                util[k] = load / c["value"]
                if util[k] > 1.0:
                    flags.append("OVERLOADED %s: %.0f lbf > capacity %.0f (util %.2f)"
                                 % (k, load, c["value"], util[k]))
    return {"flags": flags, "est": est, "weakest": weakest, "utilization": util}


def pegged_flags(pins, pin_dia, pin_end_distance, species="hardwood", peg_species=None,
                 tenon_width=None, tenon_thickness=None, tenon_depth=None):
    """Red-flag + capacity check for a PEGGED / drawbore tenon — the dedicated peg
    mechanism, split out of the M&T sizing check (issue 106). PURE, offline-testable.

    Flags:
      * brittle relish: peg end distance < 4 x peg diameter -> the relish can tear
        out the tenon end (move the peg back).

    When the tenon dims (width/thickness/depth, INCHES) are supplied it also returns
    the European-Yield-Model peg-capacity breakdown (``pin_modes``) and the peg
    pull-out (``pin_withdrawal``) from ``estimate_mortise_tenon``; with no dims only
    the (geometry-free) relish check runs.

    Returns {flags, pin_modes, pin_withdrawal}.
    """
    flags = []
    if pin_dia and pin_end_distance is not None and pin_end_distance < 4.0 * pin_dia:
        flags.append("brittle: peg end distance %.2f in < 4xD (%.2f in) -> relish "
                     "tear-out" % (pin_end_distance, 4.0 * pin_dia))

    pin_modes, pin_withdrawal = {}, 0.0
    if pins and pin_dia and None not in (tenon_width, tenon_thickness, tenon_depth):
        est = estimate_mortise_tenon(tenon_width, tenon_thickness, tenon_depth,
                                     species=species, pins=pins, pin_dia=pin_dia,
                                     pin_end_distance=pin_end_distance,
                                     peg_species=peg_species)
        pin_modes = est["pin_modes"]
        pw = est["capacities"].get("pin_withdrawal")
        pin_withdrawal = pw["value"] if pw else 0.0
    return {"flags": flags, "pin_modes": pin_modes, "pin_withdrawal": pin_withdrawal}


def summarize(result):
    """Human-readable report of an estimate — the design-guidance view."""
    i = result["inputs"]
    out = ["M&T strength estimate  (%s, %s%s)" % (i["species"],
           "through" if i["through"] else "blind",
           ", %d peg(s)" % i["pins"] if i["pins"] else ""),
           "  tenon  %.3f w(along grain) x %.3f t(across) x %.3f deep   section %.2f in^2,"
           "  eff. long-grain glue %.2f in^2" % (i["width"], i["thickness"], i["depth"],
           result["cross_section"], result["glue_area_longgrain"]),
           "  capacities (first-order, relative):"]
    for k, c in result["capacities"].items():
        out.append("    %-20s %9.0f %-7s [%s]" % (k, c["value"], c["unit"], c["mechanism"]))
    if "interlock_modes" in result:
        im = result["interlock_modes"]
        out.append("  interlock (mechanical, glue-INDEPENDENT): %.0f lbf  [governing: %s%s]"
                   % (result["interlock_withdrawal"], im["governing"],
                      ", BRITTLE" if im.get("brittle") else ""))
        out.append("    modes: " + ", ".join(
            "%s=%.0f" % (k, v) for k, v in im.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)))
    out.append("  guidance:")
    out += ["    - " + n for n in result["notes"]]
    return "\n".join(out)


# ── Mechanical interlock: wedged tenon & cut dovetail (issue 105) ────────────
#
# A flared/undercut LOCKED joint resists withdrawal MECHANICALLY, independent of
# glue. A wedge splits the tenon along a kerf and bends the two halves OUTWARD into an
# undercut/flared mortise (wider at the exit than at the mouth). The kerf is cut
# PERPENDICULAR to the mortise grain (kept from the existing tenon_wedge template), so
# the spread does NOT cleave the long-grain cheeks. The hooking faces are the original
# tenon cheeks, BENT — continuous long-grain fiber, NOT sawn. To withdraw you must drive
# the flared end back through the narrower mouth: resisted until the undercut WALL fails —
# the MORTISE cheek SPLITS in tension perpendicular to grain (brittle) or the flared
# TENON end CRUSHES back to mouth width — or the half itself folds/ruptures. None of these
# touch a glue line, so the interlock is the FLOOR a DRY or glue-failed joint still holds.
#
# FREE BODY of one bent half hooking on a wall inclined at theta to the withdrawal
# axis (full derivation in docs/joinery/grain-and-strength.md): the wall reaction N
# has an axial hook component N*sin(theta); limiting friction adds mu*N*cos(theta);
# both oppose withdrawal. Per half F = N*(sin theta + mu cos theta); n halves give
# F = n*N*(sin theta + mu cos theta). N is bounded three independent ways:
#   split  N_s = tens_perp * A_cleave / cos(theta)   the lateral push N*cos(theta) opens
#                a long-grain cleavage plane in the MORTISE cheek (tens_perp; BRITTLE)
#   crush  N_c = comp_perp * A_contact                the flared TENON end is crushed back
#                toward mouth width — compression across the tenon (comp_perp; ductile)
#   bend   the half folds/ruptures: F_b = n*M_half/delta, M_half = mor*w*(kf*t)^2/6
# interlock = min(F_split, F_crush, F_bend[, F_tail_neck]); report the governing mode;
# FLAG brittle when split governs. withdrawal = max(glue, interlock) — alternative load
# paths (glue is stiffer and carries first; interlock is the dry backstop), NOT additive.
#
# A CUT DOVETAIL locks the same axis with the SAME wall statics, but its hooking faces
# are SAWN (fibers cut at the angle), so the continuous-fiber bend reserve is gone:
# knock the bend term down (k_fiber ~ 0.5) and add a tail-NECK shear bound (the sawn
# tail can shear off at its root). estimate_interlock(continuous_fiber=False, ...) and
# estimate_dovetail() cover it.
#
# HONEST SCOPE: first-order, and the ABSOLUTE value is friction-sensitive (at small
# theta ~70% of F is friction) — treat the GOVERNING MODE + BRITTLE FLAG as the robust
# outputs and the lbf as RELATIVE. Against a perfect long-grain GLUE line
# (estimate_mortise_tenon withdrawal, wood-limited ~10k+ lbf) the interlock does NOT win
# on raw lbf; against a DRY / end-grain-only / glue-failed plain M&T it is ~3x+ and
# glue-INDEPENDENT — which is the joint's whole point ("works dry"). The split/crush
# numbers assume the bent cheek bears FLAT on a planar wall; a real flare contacts at
# the lip, concentrating load, so they are an UPPER bound on N (knock down for poor fit).

FOX_WEDGE_FACTOR = 0.8          # blind fox-wedge: the mortise bottom drives the wedge
                                # during assembly, so achieved spread < a through wedge
                                # driven to seat (and it can't be re-tightened). 0.7-0.85.
DOVETAIL_FIBER_KNOCKDOWN = 0.5  # a sawn dovetail hook recovers ~half the continuous-fiber
                                # bend reserve of a bent wedged half (0.4-0.6).
WEDGE_FRICTION = 0.4            # wood-on-wood dry static friction on the undercut contact
                                # (literature 0.3-0.5; the interlock lbf is sensitive to it).


def estimate_interlock(width, thickness, depth, species="hardwood",
                       flare_delta=0.0625, undercut_deg=8.0, mu=WEDGE_FRICTION,
                       engaged_ratio=2.0 / 3.0, kerf_fraction=0.5, n_halves=2,
                       continuous_fiber=True, k_fiber=DOVETAIL_FIBER_KNOCKDOWN,
                       tail_neck_thickness=None, fox=False):
    """First-order MECHANICAL-INTERLOCK withdrawal capacity (lbf) of a flared/undercut
    LOCKED joint — a wedged through/fox tenon (continuous bent fiber) or a cut dovetail
    (sawn fiber). GLUE-INDEPENDENT: every bound is a WOOD property of the contact, none
    an adhesive, so this is the floor a DRY or glue-failed joint still holds. Lengths in
    INCHES, forces in lbf. Pure Python (no Fusion). See the module header for the free body.

    Args (tenon-local frame, same as estimate_mortise_tenon):
        width (w)      cross-section dim ALONG the mortise grain — the contact/cheek width.
        thickness (t)  cross-section dim ACROSS the grain — split by the kerf into halves.
        depth (L)      engaged length along the insertion axis.
        flare_delta    spread per half at the flare (in) — the overhang past the mouth.
        undercut_deg   undercut/flare angle theta of the wall from the withdrawal axis
                       (mortise wider at exit than mouth). Realistic band ~6-12 deg.
        mu             wood-on-wood dry friction on the undercut contact.
        engaged_ratio  fraction of depth over which the half bears (ties to template tw_dr).
        kerf_fraction  each spread half thickness = kerf_fraction * thickness (~0.5).
        n_halves       number of spread halves / hooking faces (2 for a 1-kerf wedge).
        continuous_fiber  True = bent uncut long grain (wedge); False = sawn (dovetail) ->
                       knock the bend reserve down by k_fiber.
        k_fiber        sawn-fiber bend knockdown (used when continuous_fiber is False).
        tail_neck_thickness  cut-dovetail only: tail neck thickness (in) for the tail-shear
                       bound (the sawn tail can shear off at its root). None to skip.
        fox            blind fox-wedge -> derate the achieved spread by FOX_WEDGE_FACTOR.

    Returns dict: value (lbf), governing, brittle, modes {split, crush, bend[, tail_neck]},
    contact {areas, slide_factor, ramp_len_in, hook_only_lbf}, inputs.
    """
    if min(width, thickness, depth) <= 0:
        raise ValueError("width, thickness, depth must be > 0")
    if not (0.0 < undercut_deg < 45.0):
        raise ValueError("undercut_deg must be in (0, 45)")
    m = SPECIES.get(species)
    if m is None:
        raise ValueError("unknown species %r; choose from %s"
                         % (species, ", ".join(sorted(SPECIES))))
    w, t, L = float(width), float(thickness), float(depth)
    tens_perp, cperp, mor, tau = m["tens_perp"], m["comp_perp"], m["mor"], m["shear"]
    theta = math.radians(undercut_deg)
    ct, st = math.cos(theta), math.sin(theta)
    slide = st + mu * ct                      # axial resistance per unit wall normal N

    Le = engaged_ratio * L                    # engaged bearing / cleavage length
    A_cleave = w * Le                         # long-grain split plane behind the cheek (plan)
    A_contact = w * Le / ct                   # slant bearing patch on the inclined wall

    N_split = tens_perp * A_cleave / ct       # N at which N*cos(theta) opens the mortise cleavage
    N_crush = cperp * A_contact               # N at which the flared tenon end crushes
    F_split = n_halves * N_split * slide      # brittle: mortise cheek, tension perp to grain
    F_crush = n_halves * N_crush * slide      # ductile: tenon flare crush, comp perp to tenon grain

    half_t = kerf_fraction * t
    M_half = mor * w * half_t ** 2 / 6.0      # rupture moment of one spread half
    F_bend_full = n_halves * M_half / max(flare_delta, 1e-6)
    F_bend = (1.0 if continuous_fiber else k_fiber) * F_bend_full

    modes = {"split": F_split, "crush": F_crush, "bend": F_bend}
    if tail_neck_thickness is not None:       # sawn dovetail: tail shears off at the neck
        modes["tail_neck"] = n_halves * w * float(tail_neck_thickness) * tau

    gov = min(modes, key=modes.get)
    value = modes[gov] * (FOX_WEDGE_FACTOR if fox else 1.0)
    brittle = gov == "split"
    hook_only = value * (st / slide)          # friction-INDEPENDENT floor (transparency)

    return {
        "value": value, "unit": "lbf", "governing": gov, "brittle": brittle,
        "modes": modes,
        "contact": {"area_cleave_in2": A_cleave, "area_bearing_in2": A_contact,
                    "engaged_len_in": Le, "slide_factor": slide,
                    "ramp_len_in": flare_delta / math.tan(theta),
                    "hook_only_lbf": hook_only},
        "inputs": dict(width=w, thickness=t, depth=L, species=species,
                       flare_delta=flare_delta, undercut_deg=undercut_deg, mu=mu,
                       engaged_ratio=engaged_ratio, kerf_fraction=kerf_fraction,
                       n_halves=n_halves, continuous_fiber=continuous_fiber, k_fiber=k_fiber,
                       tail_neck_thickness=tail_neck_thickness, fox=fox),
    }


def estimate_wedged_tenon(width, thickness, depth, species="hardwood",
                          flare_delta=0.0625, undercut_deg=8.0, mu=WEDGE_FRICTION,
                          engaged_ratio=2.0 / 3.0, kerf_fraction=0.5, fox=False,
                          through=None, glue=True, sized=False, end_grain_glue=None):
    """Estimate a WEDGED tenon (through or fox) — the M&T capacities PLUS the
    mechanical-interlock withdrawal. Dedicated per-joint-type check (does NOT overload
    estimate_mortise_tenon). Calls estimate_mortise_tenon for the plain capacities + glue
    withdrawal, then estimate_interlock, then sets

        withdrawal_tension = max(glue, interlock)

    so the joint NEVER drops below the glue-independent interlock floor (a wedged joint
    holds DRY; a plain M&T pulls out without glue). thrust / shear / bending / torsion are
    unchanged — the wedge only changes the withdrawal path. Lengths in INCHES.

    glue=False models the DRY / unglued / glue-failed joint (withdrawal = interlock only) —
    use it to see the glue-independent capacity (this is where a wedged tenon beats a plain
    M&T, which has ~no dry withdrawal). Other args as estimate_mortise_tenon / estimate_interlock.

    Returns the estimate_mortise_tenon dict PLUS: interlock_withdrawal (lbf), glue_withdrawal
    (lbf), interlock_modes (+ governing, brittle), interlock_contact.
    """
    if through is None:           # blind fox-wedge defaults to a blind tenon
        through = not fox
    base = estimate_mortise_tenon(width, thickness, depth, species=species, through=through,
                                  sized=sized, end_grain_glue=end_grain_glue)
    il = estimate_interlock(width, thickness, depth, species=species, flare_delta=flare_delta,
                            undercut_deg=undercut_deg, mu=mu, engaged_ratio=engaged_ratio,
                            kerf_fraction=kerf_fraction, fox=fox, continuous_fiber=True)
    glue_w = base["capacities"]["withdrawal_tension"]["value"]
    interlock = il["value"]
    gov = il["governing"]

    if glue:
        if interlock >= glue_w:
            wd, mech = interlock, ("INTERLOCK (%s), glue-independent — %.0f lbf > glue %.0f"
                                   % (gov, interlock, glue_w))
        else:
            wd, mech = glue_w, ("GLUE (cheeks, wood-limited) %.0f; interlock floor %.0f (%s) "
                                "is the dry/glue-failed backstop" % (glue_w, interlock, gov))
    else:
        wd, mech = interlock, "INTERLOCK (%s) — DRY/unglued, mechanical only" % gov

    base["capacities"]["withdrawal_tension"] = {"value": wd, "unit": "lbf", "mechanism": mech}
    base["interlock_withdrawal"] = interlock
    base["glue_withdrawal"] = glue_w
    base["interlock_modes"] = {**il["modes"], "governing": gov, "brittle": il["brittle"]}
    base["interlock_contact"] = il["contact"]
    base["inputs"].update(wedged=True, fox=fox, glue=glue, flare_delta=flare_delta,
                          undercut_deg=undercut_deg, mu=mu)

    base["notes"].append(
        "WEDGED interlock = %.0f lbf (governing: %s), GLUE-INDEPENDENT — the dry floor. "
        "withdrawal = max(glue %.0f, interlock %.0f) = %.0f (%s). Against a DRY plain M&T "
        "(~no withdrawal without glue) the wedge is the whole capacity; against a sound "
        "long-grain glue line, glue carries first and the interlock is the backstop "
        "against glue failure / seasonal movement." % (
            interlock, gov, glue_w, interlock, wd, "GLUE" if (glue and wd == glue_w) else "INTERLOCK"))
    if il["brittle"]:
        base["notes"].append(
            "BRITTLE: interlock governed by MORTISE-CHEEK SPLIT (tension perp to grain) — "
            "sudden, low-energy cleavage along the grain. Keep margin, reduce flare/undercut, "
            "or hoop/band the mortise; tens_perp is the most variable clear-wood property.")
    if fox:
        base["notes"].append(
            "FOX-wedged (blind): the mortise bottom drives the wedge during assembly, so "
            "achieved spread is derated x%.2f and the joint CANNOT be re-tightened; leave a "
            "mortise-bottom wall." % FOX_WEDGE_FACTOR)
    base["notes"].append(
        "Interlock lbf is FRICTION-sensitive (mu=%.2f; friction-independent hook floor "
        "%.0f lbf); treat the GOVERNING MODE + BRITTLE FLAG as the robust outputs, the lbf "
        "as relative." % (mu, il["contact"]["hook_only_lbf"]))
    return base


def estimate_dovetail(tail_width, tail_thickness, socket_depth, species="hardwood",
                      dovetail_deg=9.5, tail_neck_thickness=None, mu=WEDGE_FRICTION,
                      engaged_ratio=1.0, k_fiber=DOVETAIL_FIBER_KNOCKDOWN, n_tails=1):
    """Estimate a CUT DOVETAIL's locked-axis (withdrawal) capacity — the interlock model
    generalized to SAWN hooking faces. Same wall statics as the wedged tenon (split via
    tens_perp, crush via comp_perp on the socket wall), but the tail's fibers are CUT at the
    dovetail angle, so the continuous-fiber bend reserve is knocked down (k_fiber) and a
    tail-NECK shear bound is added (the sawn tail shears off at its root). This is the
    cut-face-vs-continuous-fiber distinction from issue 105: a wedged flare is tougher than
    a dovetail because its bent fiber is uninterrupted. Lengths in INCHES.

    A dovetail has ONE flare angle per tail face; dovetail_deg ~ 7-10 deg (1:8 to 1:6).
    tail_neck_thickness defaults to tail_thickness (the tail base). n_tails counts engaged
    hooking faces.

    Returns the estimate_interlock dict (value, governing, brittle, modes, contact, inputs).
    """
    neck = tail_thickness if tail_neck_thickness is None else tail_neck_thickness
    return estimate_interlock(tail_width, tail_thickness, socket_depth, species=species,
                              flare_delta=tail_thickness * math.tan(math.radians(dovetail_deg)),
                              undercut_deg=dovetail_deg, mu=mu, engaged_ratio=engaged_ratio,
                              kerf_fraction=1.0, n_halves=n_tails, continuous_fiber=False,
                              k_fiber=k_fiber, tail_neck_thickness=neck)
