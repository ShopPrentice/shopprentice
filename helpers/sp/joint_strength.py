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
        notes.append("Wedged: flared tenon adds MECHANICAL withdrawal (not quantified).")
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
    out.append("  guidance:")
    out += ["    - " + n for n in result["notes"]]
    return "\n".join(out)
