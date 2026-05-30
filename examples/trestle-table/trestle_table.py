"""Wedged Through-Tenon Trestle Table.

Source: Gary Rogowski, "The Versatile Trestle Table",
Fine Woodworking Sep/Oct 2010.

Coordinate system:
  X = table length (54"), Y = table width (27"), Z = height (29"), floor Z=0.

Build phases (this file grows each phase, re-run with clean=True):
  1+2. Shaped structure: Feet (sloped + relief), Posts (tapered), Caps,
       waisted Stretcher, Top, Battens
  3.   Joinery: post<->cap & post<->foot blind M&T;
       stretcher through-tenon + tusk wedges
  4.   Details: ease edges + appearance
"""

# ═══════════════ APPEARANCE SPEC ══════════════════════════
# After execute_script(clean=True), agent parses this block
# and applies each coat in order via the apply_appearance MCP tool.
# {
#   "coats": [
#     {"species": "white oak"},
#     {"species": "walnut",
#      "bodies": ["Top", "Wedge_L", "Wedge_R", "Peg_*"]}
#   ],
#   "hide_construction": true
# }
# ══════════════════════════════════════════════════════════

import adsk.core
import adsk.fusion

from helpers import sp

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
P3 = adsk.core.Point3D.create


def add_params(params):
    VI = adsk.core.ValueInput.createByString

    def P(name, expr, unit, desc=""):
        if not params.itemByName(name):
            params.add(name, VI(expr), unit, desc)

    # ── Envelope ──────────────────────────────────────────────
    P("table_l", "54 in", "in", "Overall top length")
    P("table_w", "27 in", "in", "Overall top width")
    P("table_h", "29 in", "in", "Overall height")
    P("top_thick", "0.75 in", "in", "Tabletop thickness")

    # ── Post ──────────────────────────────────────────────────
    P("post_thick", "1.125 in", "in", "Post thickness (X)")
    P("post_w_bot", "4 in", "in", "Post width at bottom (Y)")
    P("post_w_top", "3 in", "in", "Post width at top (Y)")

    # ── Cap ───────────────────────────────────────────────────
    P("cap_thick", "1.5 in", "in", "Cap thickness (Z) at center (thicker)")
    P("cap_end_thick", "0.5 in", "in", "Cap thickness at the ends (arched underside)")
    P("cap_w", "2.5 in", "in", "Cap width (X)")
    P("cap_len", "21 in", "in", "Cap length (Y)")

    # ── Foot ──────────────────────────────────────────────────
    P("foot_thick", "1.375 in", "in", "Foot thickness (X)")
    P("foot_len", "23 in", "in", "Foot length (Y)")
    P("foot_h", "3 in", "in", "Foot height at center (Z)")
    P("foot_end_h", "1 in", "in", "Foot height at ends (Z)")
    P("foot_center_flat", "6 in", "in", "Flat landing width on top of foot")
    P("foot_pad", "5 in", "in", "Floor-contact pad length at each end")
    P("foot_relief", "0.375 in", "in", "Center bottom relief height")

    # ── Stretcher ─────────────────────────────────────────────
    P("str_thick", "1.25 in", "in", "Stretcher thickness (Y)")
    P("str_w", "3 in", "in", "Stretcher board width — CONSTANT across the arc")
    P("str_shoulder", "33.75 in", "in", "Shoulder-to-shoulder span between posts")
    P("str_proud", "2 in", "in", "Tenon protrusion past post outer face")
    P("str_tenon_below_cap", "5.5 in", "in",
      "Distance from the cap bottom down to the top of the stretcher tenon")
    P("str_arch_rise", "1.5 in", "in",
      "How much the stretcher arches up at center above the tenon line")

    # ── Battens ───────────────────────────────────────────────
    P("bat_thick", "1 in", "in", "Batten thickness (Z) — thicker than the ⅝ FW spec")
    P("n_battens", "3", "", "Number of battens (patterned)")
    P("bat_w", "2 in", "in", "Batten width (X)")
    P("bat_len", "23 in", "in", "Batten length (Y)")
    P("bat_inset", "3 in", "in", "Batten inset from top ends")
    P("bat_end_round", "1.5 in", "in", "Length of the rounded-up zone at each batten end")
    P("bat_screw_dia", "0.1875 in", "in", "Batten screw clearance hole diameter")
    P("bat_slot_len", "0.625 in", "in", "Slotted-hole length in Y (allows top to move)")
    P("bat_hole_off", "8 in", "in", "Offset of the two outer (slotted) holes from center")

    # ── Joinery ───────────────────────────────────────────────
    P("mt_tt", "0.375 in", "in", "Post tenon thickness (X)")
    P("mt_tw_cap", "2.5 in", "in", "Upper (cap) tenon width (Y)")
    P("mt_td_cap", "1 in", "in", "Upper tenon depth (blind in 1-1/8 cap)")
    P("mt_tw_foot", "1.5 in", "in", "Lower (foot) tenon width (Y) — twin tenons")
    P("mt_td_foot", "1.25 in", "in", "Lower tenon depth into foot")
    P("foot_tenon_gap", "0.5 in", "in", "Gap between the two lower tenons")
    P("stt_round", "0.25 in", "in", "Roundover radius on the through-tenon tip")
    # Stretcher through-tenon: 3/4 thick (Y) x 2 wide (Z) x 3-1/8 long (X)
    P("stt_thk", "0.75 in", "in", "Stretcher tenon thickness (Y)")
    P("stt_wid", "2 in", "in", "Stretcher tenon width / height (Z)")
    # Tusk wedge: driven vertically; vertical face bears on the post,
    # angled (8 deg) face bears on the tenon. Thicker at top so tapping
    # down draws the stretcher shoulder tight against the post.
    P("wdg_xthin", "0.25 in", "in", "Wedge X-thickness at the thin (bottom) end")
    P("wdg_y", "0.375 in", "in",
      "Wedge blade thickness (Y) — narrower than the tenon so the mortise "
      "leaves side material connecting the tenon tip to its root")
    P("wdg_l", "6 in", "in", "Wedge length (Z) — protrudes above & below the tenon")
    P("wedge_ang", "8 deg", "deg", "Wedge / tusk-mortise taper angle")
    # Wedge crown (captured from the user's manual sketch edit; draggable):
    # angled-face top drops wdg_crown_drop below z_top, then a spline rises
    # across to the post-side top, highest at the post (bearing) edge.
    P("wdg_crown_drop", "0.3 in", "in", "Drop of the angled-side top below the crown peak")
    P("wdg_crown_mid_x", "0.6 in", "in", "Crown mid fit-point X offset from the post face")
    P("wdg_crown_mid_drop", "0.06 in", "in", "Crown mid fit-point drop below the peak")

    # ── Tabletop buttons (L-shaped: body screwed under the top + tongue into
    #    an elongated cap slot, fixing the cap to the top while allowing the
    #    top to move in Y) ──
    P("btn_w", "0.75 in", "in", "Button width (Y)")
    P("btn_h", "0.75 in", "in", "Button body height (Z)")
    P("btn_body_len", "0.625 in", "in", "Button body length toward table center (X)")
    P("btn_tongue_d", "0.625 in", "in", "Tongue depth into the cap (X)")
    P("btn_tongue_h", "0.25 in", "in", "Tongue height (Z) — the rabbet")
    P("btn_slot_extra", "0.375 in", "in", "Cap slot Y-overrun past the tongue (movement)")
    P("btn_off", "6 in", "in", "Outer buttons' Y offset from center")

    # ── Derived ───────────────────────────────────────────────
    P("x_mid", "table_l / 2", "in", "Length midplane")
    P("y_mid", "table_w / 2", "in", "Width midplane")
    P("post_spacing", "str_shoulder + post_thick", "in", "Post center spacing")
    P("post1_cx", "x_mid - post_spacing / 2", "in", "Lower-X post center")
    P("post2_cx", "x_mid + post_spacing / 2", "in", "Higher-X post center")
    P("post_bottom_z", "foot_h", "in", "Post bottom (sits on foot center)")
    P("cap_bottom_z", "table_h - top_thick - cap_thick", "in", "Cap bottom")
    P("post_body_h", "cap_bottom_z - post_bottom_z", "in", "Post visible height")
    # Stretcher end centerline: tenon top sits str_tenon_below_cap under the cap
    P("str_center_z", "cap_bottom_z - str_tenon_below_cap - stt_wid / 2", "in",
      "Stretcher end (tenon) centerline")
    P("str_tenon_d", "post_thick + str_proud", "in", "Through-tenon depth")
    P("wedge_taper", "wdg_l * tan(wedge_ang)", "in", "Wedge taper run over its length")
    P("top_bottom_z", "table_h - top_thick", "in", "Tabletop underside")
    P("bat_bottom_z", "top_bottom_z - bat_thick", "in", "Batten underside")
    P("bat_pitch", "(table_l - 2 * bat_inset) / (n_battens - 1)", "in",
      "Batten spacing for the rectangular pattern")
    P("top_crown", "1 in", "in", "Tabletop end crown — center proud of corners")
    P("top_chamfer", "0.25 in", "in",
      "Tabletop top-edge 45 chamfer (¼ of the ¾ thickness; ½ stays flat)")
    P("bat_end_thick", "0.125 in", "in", "Batten thickness at the rounded-up ends")
    P("peg_dia", "0.25 in", "in", "Drawbore / tenon peg diameter")


# ── Small geometry helpers ───────────────────────────────────────────

def oplane(comp, base, expr, name):
    return sp.off_plane(comp, base, expr, name)


def xmid_plane(comp):
    return sp.off_plane(comp, comp.yZConstructionPlane, "x_mid", "XMid")


def ext_cut_sym(comp, prof, full_expr, target, name):
    """Symmetric extrude-cut about the sketch plane (full length = full_expr)."""
    ef = comp.features.extrudeFeatures
    inp = ef.createInput(prof, CUT)
    inp.setSymmetricExtent(adsk.core.ValueInput.createByString(full_expr), True)
    inp.participantBodies = [target]
    f = ef.add(inp)
    f.name = name
    return f


_SKIPPED = []


def feat_pattern_multi(comp, feats, axis, count_expr, spacing_expr, name):
    """Rectangular-pattern a GROUP of features (e.g. an extrude + its cuts)
    so the bodies and their cuts replicate together — no ghost bodies."""
    coll = adsk.core.ObjectCollection.create()
    for f in feats:
        coll.add(f)
    VI = adsk.core.ValueInput.createByString
    inp = comp.features.rectangularPatternFeatures.createInput(
        coll, axis, VI(count_expr), VI(spacing_expr),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    inp.quantityTwo = VI("1")
    return comp.features.rectangularPatternFeatures.add(inp)


def fspline(sk, m2s, pts_model):
    """Fit-point spline through model-space points (left draggable / unconstrained).

    pts_model: list of (x, y, z) model coords. Returns the SketchFittedSpline;
    use .startSketchPoint / .endSketchPoint to connect lines to it.
    """
    col = adsk.core.ObjectCollection.create()
    for (mx, my, mz) in pts_model:
        s = m2s(P3(mx, my, mz))
        col.add(P3(s.x, s.y, 0))
    return sk.sketchCurves.sketchFittedSplines.add(col)


def face_edge_collection(face):
    col = adsk.core.ObjectCollection.create()
    for i in range(face.edges.count):
        col.add(face.edges.item(i))
    return col


def chamfer_face(comp, face, dist_expr, name):
    ci = comp.features.chamferFeatures.createInput2()
    ci.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
        face_edge_collection(face),
        adsk.core.ValueInput.createByString(dist_expr), False)
    comp.features.chamferFeatures.add(ci).name = name


def fillet_face(comp, face, r_expr, name):
    fi = comp.features.filletFeatures.createInput()
    fi.addConstantRadiusEdgeSet(
        face_edge_collection(face),
        adsk.core.ValueInput.createByString(r_expr), False)
    comp.features.filletFeatures.add(fi).name = name


def odim(sk, d, pt, orient, axis, expr):
    """Origin-anchored distance dimension for a sketch point along a model axis.

    Tolerant: if the dimension would over-constrain (the point is already
    determined by prior constraints), skip it — the geometry is already at
    the correct model position via modelToSketchSpace.
    """
    g = pt.geometry
    try:
        d.addDistanceDimension(sk.originPoint, pt, orient[axis],
                               P3(g.x + 0.4, g.y + 0.4, 0)).parameter.expression = expr
    except Exception:
        _SKIPPED.append(("odim", sk.name, axis, expr))


def rdim(sk, d, p1, p2, orient, axis, expr):
    """Relative distance dimension between two sketch points along a model axis."""
    g1, g2 = p1.geometry, p2.geometry
    try:
        d.addDistanceDimension(p1, p2, orient[axis],
                               P3((g1.x + g2.x) / 2 + 0.4, (g1.y + g2.y) / 2 + 0.4, 0)
                               ).parameter.expression = expr
    except Exception:
        _SKIPPED.append(("rdim", sk.name, axis, expr))


def run(context):
    ctx = sp.DesignContext()
    design = ctx.design
    root = ctx.root
    ev = ctx.ev
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    add_params(design.userParameters)

    # Components up front; one trestle end is built complete (shape +
    # joinery) then mirrored across the length midplane to the other end.
    feet_occ = sp.make_comp(root, "Feet"); feet = feet_occ.component
    posts_occ = sp.make_comp(root, "Posts"); posts = posts_occ.component
    caps_occ = sp.make_comp(root, "Caps"); caps = caps_occ.component
    str_occ = sp.make_comp(root, "Stretcher"); strc = str_occ.component
    top_occ = sp.make_comp(root, "Top"); topc = top_occ.component
    bat_occ = sp.make_comp(root, "Battens"); batc = bat_occ.component
    wed_occ = sp.make_comp(root, "Wedges"); wcomp = wed_occ.component
    # Pegs live in Posts (they pin the post tenons); buttons live in Top.

    # ── Cross-component dependency helpers ───────────────────────
    # Project a parent body's mating face (via its assembly proxy) into a
    # child-component sketch, then anchor the child geometry to the projected
    # reference (associative — moves with the parent). Avoids origin dims.
    def project_face(child_sk, parent_body, parent_occ, axis, direction):
        face = sp.find_face(parent_body, axis, direction)
        child_sk.project(face.createForAssemblyContext(parent_occ))
        sp.refs_to_construction(child_sk)

    def anchor_pt(child_sk, mx, my, mz):
        t = child_sk.modelToSketchSpace(P3(mx, my, mz))
        best = None; bd = 1e18
        for ci in range(child_sk.sketchCurves.count):
            c = child_sk.sketchCurves.item(ci)
            if not c.isConstruction:
                continue
            for attr in ("startSketchPoint", "endSketchPoint"):
                p = getattr(c, attr, None)
                if not p:
                    continue
                g = p.geometry
                d = (g.x - t.x) ** 2 + (g.y - t.y) ** 2
                if d < bd:
                    bd = d; best = p
        return best

    def strip_origin_dims(sk):
        # remove dims that reference the sketch origin (geometry stays placed)
        op = sk.originPoint
        for di in reversed(range(sk.sketchDimensions.count)):
            dim = sk.sketchDimensions.item(di)
            hit = False
            for a in ("entityOne", "entityTwo"):
                e = getattr(dim, a, None)
                try:
                    if e and e == op:
                        hit = True
                except Exception:
                    pass
            if hit:
                try:
                    dim.deleteMe()
                except Exception:
                    pass

    # ════════════════════════════════════════════════════════════
    # PHASE 1+2 — LEFT TRESTLE (shaped) — mirrored later
    # ════════════════════════════════════════════════════════════

    # ── Foot_L ── ref: origin (floor) ────────────────────────────
    # Shaped profile in the Y-Z plane (sloped top w/ flat landing,
    # center-relieved bottom so it stands on two end pads).
    fpl = oplane(feet, feet.yZConstructionPlane, "post1_cx", "Foot_Pl")
    sk = feet.sketches.add(fpl)
    sk.name = "Foot_Sk"
    orient = sp.probe_orientations(sk, ev("post1_cx"), ev("y_mid"), ev("foot_h"))
    m2s = sk.modelToSketchSpace
    X0 = ev("post1_cx")

    def fp(y, z):
        s = m2s(P3(X0, y, z))
        return P3(s.x, s.y, 0)

    yL = ev("y_mid - foot_len / 2"); yR = ev("y_mid + foot_len / 2")
    ym = ev("y_mid"); pad = ev("foot_pad")
    fh = ev("foot_h"); feh = ev("foot_end_h"); rel = ev("foot_relief")
    L = sk.sketchCurves.sketchLines
    ffL = ev("y_mid - foot_center_flat / 2"); ffR = ev("y_mid + foot_center_flat / 2")
    # Top: FLAT landing across the center (where the post lands), curving down
    # to foot_end_h at both ends (draggable splines).
    # Top curves: topR carries the user's manual edit; topL is its Y-mirror.
    tr_my = ev("21.667 in"); tr_mz = ev("2.347 in")     # user-tuned topR control pt
    topR = fspline(sk, m2s, [(X0, yR, feh), (X0, tr_my, tr_mz),
                             (X0, ffR, fh)])              # right curve  E->flatR
    topL = fspline(sk, m2s, [(X0, ffL, fh), (X0, 2 * ym - tr_my, tr_mz),
                             (X0, yL, feh)])              # left curve   flatL->F (mirror)
    topflat = L.addByTwoPoints(topR.endSketchPoint, topL.startSketchPoint)  # flat landing
    # Arched bottom opening: stands on two end pads (z=0), relieved at center.
    arch = fspline(sk, m2s, [(X0, yL + pad, 0), (X0, ym, rel), (X0, yR - pad, 0)])
    lle = L.addByTwoPoints(topL.endSketchPoint, fp(yL, 0))           # left end (F->A)
    llp = L.addByTwoPoints(lle.endSketchPoint, arch.startSketchPoint)  # left pad (A->B)
    lrp = L.addByTwoPoints(arch.endSketchPoint, fp(yR, 0))           # right pad (C->D)
    lre = L.addByTwoPoints(lrp.endSketchPoint, topR.startSketchPoint)  # right end (D->E)
    # Root foot: the floor IS the origin. Fully constrain every straight edge from
    # the origin/floor datum; the sculpted top + arch spline interiors stay free.
    fgc = sk.geometricConstraints
    for ln_ in (topflat, lle, llp, lrp, lre):
        g1 = ln_.startSketchPoint.geometry; g2 = ln_.endSketchPoint.geometry
        if abs(g1.x - g2.x) >= abs(g1.y - g2.y):
            fgc.addHorizontal(ln_)
        else:
            fgc.addVertical(ln_)
    fd = sk.sketchDimensions
    B = arch.startSketchPoint; C = arch.endSketchPoint               # arch ends (on floor)
    A = lle.endSketchPoint; F = topL.endSketchPoint                  # left pad / left tip
    D = lrp.endSketchPoint; E = topR.startSketchPoint                # right pad / right tip
    FR = topR.endSketchPoint; FL = topL.startSketchPoint             # landing (flat-top) ends
    rdim(sk, fd, sk.originPoint, B, orient, 'z', "0 in")             # pad on floor (z=0)
    rdim(sk, fd, sk.originPoint, B, orient, 'y', "y_mid - foot_len / 2 + foot_pad")
    rdim(sk, fd, B, A, orient, 'y', "foot_pad")                     # left pad length
    rdim(sk, fd, A, F, orient, 'z', "foot_end_h")                   # left end-tip height
    rdim(sk, fd, B, C, orient, 'y', "foot_len - 2 * foot_pad")      # span between pads
    rdim(sk, fd, B, C, orient, 'z', "0 in")                         # arch ends both on floor
    rdim(sk, fd, C, D, orient, 'y', "foot_pad")                     # right pad length
    rdim(sk, fd, D, E, orient, 'z', "foot_end_h")                   # right end-tip height
    rdim(sk, fd, E, FR, orient, 'z', "foot_h - foot_end_h")         # rise to the landing
    rdim(sk, fd, E, FR, orient, 'y', "foot_len / 2 - foot_center_flat / 2")
    rdim(sk, fd, FR, FL, orient, 'y', "foot_center_flat")           # flat landing width
    prof = sp.smallest_profile(sk)
    foot_l = sp.ext_new_sym(feet, prof, "foot_thick / 2", "FootBoard").bodies.item(0)
    foot_l.name = "Foot_L"

    # ── Post_L ── ref: Foot_L (stands on foot top, +Z) ───────────
    # Tapered trapezoid in Y-Z: post_w_bot at the foot, post_w_top at the cap.
    ref = ctx.find_body("Foot_L")
    foot_top_z = ref.boundingBox.maxPoint.z
    ppl = oplane(posts, posts.yZConstructionPlane, "post1_cx", "Post_Pl")
    psk = posts.sketches.add(ppl)
    psk.name = "Post_Sk"
    orient = sp.probe_orientations(psk, ev("post1_cx"), ev("y_mid"),
                                   ev("post_bottom_z"))
    m2s = psk.modelToSketchSpace
    z0 = ev("post_bottom_z"); z1 = ev("cap_bottom_z")
    ybL = ev("y_mid - post_w_bot / 2"); ybR = ev("y_mid + post_w_bot / 2")
    ytL = ev("y_mid - post_w_top / 2"); ytR = ev("y_mid + post_w_top / 2")

    def pp(y, z):
        s = m2s(P3(X0, y, z))
        return P3(s.x, s.y, 0)

    PL = psk.sketchCurves.sketchLines
    q0 = PL.addByTwoPoints(pp(ybL, z0), pp(ybR, z0))    # bottom
    q1 = PL.addByTwoPoints(q0.endSketchPoint, pp(ytR, z1))  # right slope
    q2 = PL.addByTwoPoints(q1.endSketchPoint, pp(ytL, z1))  # top
    PL.addByTwoPoints(q2.endSketchPoint, q0.startSketchPoint)  # left slope
    gc = psk.geometricConstraints
    # YZ plane: bottom/top edges span model-Y -> sketch-vertical
    gc.addVertical(q0); gc.addVertical(q2)
    Q0, Q1, Q2, Q3 = (q0.startSketchPoint, q0.endSketchPoint,
                      q1.endSketchPoint, q2.endSketchPoint)
    # Anchor to Foot_L's projected top-landing face (proxy) — not origin.
    project_face(psk, foot_l, feet_occ, "z", +1)
    aL = anchor_pt(psk, ev("post1_cx"), ev("y_mid - foot_center_flat / 2"), ev("foot_h"))
    d = psk.sketchDimensions
    rdim(psk, d, aL, Q0, orient, 'z', "0 in")                  # post bottom on landing top
    rdim(psk, d, aL, Q0, orient, 'y', "foot_center_flat / 2 - post_w_bot / 2")
    rdim(psk, d, aL, Q3, orient, 'y', "foot_center_flat / 2 - post_w_top / 2")
    rdim(psk, d, Q0, Q1, orient, 'y', "post_w_bot")
    rdim(psk, d, Q0, Q3, orient, 'z', "post_body_h")
    rdim(psk, d, Q3, Q2, orient, 'y', "post_w_top")
    prof = sp.smallest_profile(psk)
    post_l = sp.ext_new_sym(posts, prof, "post_thick / 2", "PostBoard").bodies.item(0)
    post_l.name = "Post_L"

    # ── Cap_L ── ref: Post_L (sits on post top, +Z) ──────────────
    # Profile in Y-Z: flat top (under the tabletop), arched underside —
    # full cap_thick at center, tapering to cap_end_thick at the ends.
    ref = ctx.find_body("Post_L")
    post_top_z = ref.boundingBox.maxPoint.z
    cpl = oplane(caps, caps.yZConstructionPlane, "post1_cx", "Cap_Pl")
    csk = caps.sketches.add(cpl)
    csk.name = "Cap_Sk"
    orient_c = sp.probe_orientations(csk, ev("post1_cx"), ev("y_mid"),
                                     ev("cap_bottom_z"))
    cm2s = csk.modelToSketchSpace
    X0c = ev("post1_cx"); cym = ev("y_mid")
    cyL = ev("y_mid - cap_len / 2"); cyR = ev("y_mid + cap_len / 2")
    ctop = ev("top_bottom_z"); cbc = ev("cap_bottom_z")
    cbe = ev("top_bottom_z - cap_end_thick")

    def cp(y, z):
        s = cm2s(P3(X0c, y, z))
        return P3(s.x, s.y, 0)

    CL = csk.sketchCurves.sketchLines
    cfL = cym - ev("cap_len") / 6.0; cfR = cym + ev("cap_len") / 6.0  # center third
    # Underside: FLAT across the center third (full cap_thick), curving up to
    # thin ends over the outer thirds (draggable splines).
    # Underside curves: undL carries the user's manual edit; undR is its Y-mirror.
    ul_my = ev("6.834 in"); ul_mz = ev("26.936 in")     # user-tuned undL control pt
    undL = fspline(csk, cm2s, [(X0c, cfL, cbc), (X0c, ul_my, ul_mz),
                               (X0c, cyL, cbe)])           # left curve   flatL->cyL
    undR = fspline(csk, cm2s, [(X0c, cyR, cbe), (X0c, 2 * cym - ul_my, ul_mz),
                               (X0c, cfR, cbc)])           # right curve  cyR->flatR (mirror)
    cflat = CL.addByTwoPoints(undR.endSketchPoint, undL.startSketchPoint)  # flat center
    ctl = CL.addByTwoPoints(undL.endSketchPoint, cp(cyL, ctop))   # left end up
    ctt = CL.addByTwoPoints(ctl.endSketchPoint, cp(cyR, ctop))    # top flat
    cre = CL.addByTwoPoints(ctt.endSketchPoint, undR.startSketchPoint)  # right end down
    # Anchor to Post_L's projected top face (proxy): the cap sits on the post top.
    # Locate the cap's top-left corner from the post-top edge, then dimension the
    # cap's length + thickness off it (the sculpted underside splines stay free).
    project_face(csk, post_l, posts_occ, "z", +1)
    cd = csk.sketchDimensions
    cgc = csk.geometricConstraints
    for ln_ in (cflat, ctl, ctt, cre):                  # lock rectilinear edges
        g1 = ln_.startSketchPoint.geometry; g2 = ln_.endSketchPoint.geometry
        if abs(g1.x - g2.x) >= abs(g1.y - g2.y):
            cgc.addHorizontal(ln_)
        else:
            cgc.addVertical(ln_)
    caL = anchor_pt(csk, X0c, ev("y_mid - post_w_top / 2"), ev("cap_bottom_z"))
    V1 = ctl.endSketchPoint; V2 = ctt.endSketchPoint    # top-left, top-right corners
    U2 = ctl.startSketchPoint; U3 = cre.endSketchPoint  # thin end-tips (underside)
    U1 = undL.startSketchPoint; U4 = undR.endSketchPoint  # underside flat-center ends
    rdim(csk, cd, caL, V1, orient_c, 'z', "cap_thick")               # cap top above post top
    rdim(csk, cd, caL, V1, orient_c, 'y', "cap_len / 2 - post_w_top / 2")
    rdim(csk, cd, V1, V2, orient_c, 'y', "cap_len")                  # overall length
    rdim(csk, cd, V1, U2, orient_c, 'z', "cap_end_thick")            # left end thickness
    rdim(csk, cd, V2, U3, orient_c, 'z', "cap_end_thick")            # right end thickness
    rdim(csk, cd, V1, U1, orient_c, 'z', "cap_thick")                # underside flat at post top
    rdim(csk, cd, V1, U1, orient_c, 'y', "cap_len / 3")              # center-third start
    rdim(csk, cd, V2, U4, orient_c, 'z', "cap_thick")
    rdim(csk, cd, V2, U4, orient_c, 'y', "cap_len / 3")
    prof = sp.smallest_profile(csk)
    cap_l = sp.ext_new_sym(caps, prof, "cap_w / 2", "CapBoard").bodies.item(0)
    cap_l.name = "Cap_L"

    # ════════════════════════════════════════════════════════════
    # PHASE 3a — LEFT TRESTLE JOINERY (blind M&T), then mirror
    # ════════════════════════════════════════════════════════════
    # Tenon profile on the post's OWN end face. The post face is projected
    # (native, same component) and the tenon rect is anchored to the projected
    # face corner — no origin reference. Centered at (post1_cx, tcen_y).
    def tenon_profile(face, z_expr, facew_expr, tcen_y_expr, tw_expr, name):
        sk = posts.sketches.add(face)
        sk.name = name + "_Sk"
        for ei in range(face.edges.count):       # project the face's own edges
            try:
                sk.project(face.edges.item(ei))  # (can't project the plane-face itself)
            except Exception:
                pass
        sp.refs_to_construction(sk)
        ori = sp.probe_orientations(sk, ev("post1_cx"), ev("y_mid"), ev(z_expr))
        m2 = sk.modelToSketchSpace; zc = ev(z_expr)
        cx = ev("post1_cx"); tcy = ev(tcen_y_expr); tw = ev(tw_expr); tt = ev("mt_tt")

        def P(x, y):
            s = m2(P3(x, y, zc)); return P3(s.x, s.y, 0)

        # Build the rectangle from explicit MODEL corners (X spans the tenon
        # thickness mt_tt, Y spans its width tw) — NOT addTwoPointRectangle, whose
        # edges run along sketch axes and make the model-axis dims degenerate.
        L = sk.sketchCurves.sketchLines
        lab = L.addByTwoPoints(P(cx - tt / 2, tcy - tw / 2), P(cx + tt / 2, tcy - tw / 2))
        lbc = L.addByTwoPoints(lab.endSketchPoint, P(cx + tt / 2, tcy + tw / 2))
        lcd = L.addByTwoPoints(lbc.endSketchPoint, P(cx - tt / 2, tcy + tw / 2))
        lda = L.addByTwoPoints(lcd.endSketchPoint, lab.startSketchPoint)
        gc = sk.geometricConstraints                     # lock rectilinearity (all 4)
        for ln_ in (lab, lbc, lcd, lda):
            g1 = ln_.startSketchPoint.geometry; g2 = ln_.endSketchPoint.geometry
            if abs(g1.x - g2.x) >= abs(g1.y - g2.y):
                gc.addHorizontal(ln_)
            else:
                gc.addVertical(ln_)
        d = sk.sketchDimensions
        # cross-section: thickness (along X) and width (along Y) — now well-defined
        rdim(sk, d, lab.startSketchPoint, lab.endSketchPoint, ori, 'x', "mt_tt")
        rdim(sk, d, lbc.startSketchPoint, lbc.endSketchPoint, ori, 'y', tw_expr)
        # anchor corner A to the projected post-face corner (no origin)
        aF = anchor_pt(sk, cx - ev("post_thick") / 2,
                       ev("y_mid") - ev(facew_expr) / 2, zc)
        rdim(sk, d, aF, lab.startSketchPoint, ori, 'x', "post_thick / 2 - mt_tt / 2")
        rdim(sk, d, aF, lab.startSketchPoint, ori, 'y',
             "(%s) - y_mid + %s / 2 - (%s) / 2" % (tcen_y_expr, facew_expr, tw_expr))
        return sp.smallest_profile(sk)

    def blind_mt(post_body, mortise_body, face, z_expr, facew_expr,
                 tcen_y_expr, tw_expr, td_expr, name):
        prof = tenon_profile(face, z_expr, facew_expr, tcen_y_expr, tw_expr, name)
        tb = sp.ext_new(posts, prof, td_expr, name + "_Tenon").bodies.item(0)
        tb.name = name + "_Tenon"
        sp.combine(mortise_body, [tb], CUT, True, name + "_Mort")
        sp.combine(post_body, [tb], JOIN, False, name + "_Join")

    # Upper (cap): single tenon centered.
    blind_mt(post_l, cap_l, sp.find_face(post_l, "z", +1),
             "cap_bottom_z", "post_w_top", "y_mid", "mt_tw_cap", "mt_td_cap", "MTC_L")

    # Lower (foot): TWIN tenons. Build BOTH on the captured post-bottom face
    # FIRST (as NewBodies, before any JOIN modifies the post), then CUT the
    # foot with both and JOIN both into the post.
    foot_off = "(mt_tw_foot / 2 + foot_tenon_gap / 2)"
    foot_face = sp.find_face(post_l, "z", -1)

    def foot_tenon(tcen_y_expr, name):
        prof = tenon_profile(foot_face, "post_bottom_z", "post_w_bot",
                             tcen_y_expr, "mt_tw_foot", name)
        tb = sp.ext_new(posts, prof, "mt_td_foot", name + "_Tenon").bodies.item(0)
        tb.name = name + "_Tenon"
        return tb

    fta = foot_tenon("y_mid - " + foot_off, "MTF_La")
    ftb = foot_tenon("y_mid + " + foot_off, "MTF_Lb")
    sp.combine(foot_l, [fta, ftb], CUT, True, "MTF_L_Mort")
    sp.combine(post_l, [fta, ftb], JOIN, False, "MTF_L_Join")

    # ── Drawbore pegs (¼" dowels through the joints) ─────────────
    # Each peg is a cylinder along X through the joint; CUT both pieces
    # (keepTool) so the peg fills the hole and pins them. Built on the left,
    # then mirrored with the trestle.
    # Pegs live in the POST's component (they pin the post tenons — same
    # convention as the drawbore template, where pins are built in the tenon's
    # component).
    # A maker bores the peg relative to the post shoulder it pins through. We
    # project that shoulder face (the post's own — same component → native) and
    # dimension the peg center: Y in from the post edge, Z off the shoulder.
    def make_peg(ycen_expr, ref_z_expr, z_sign, z_mag_expr, half_w_expr,
                 half_len_expr, cut_bodies, name):
        ppl = oplane(posts, posts.yZConstructionPlane, "post1_cx", name + "_Pl")
        psk = posts.sketches.add(ppl)
        psk.name = name + "_Sk"
        pz = ev(ref_z_expr) + z_sign * ev(z_mag_expr)
        d = psk.sketchDimensions
        orient = sp.probe_orientations(psk, ev("post1_cx"), ev(ycen_expr), pz)
        anchor = None
        f = sp.find_face_at(post_l, "z", ev(ref_z_expr))
        if f is not None:
            psk.project(f)                       # post shoulder at ref_z
            sp.refs_to_construction(psk)
            anchor = anchor_pt(psk, ev("post1_cx"),
                               ev("y_mid - (" + half_w_expr + ")"), ev(ref_z_expr))
        c = psk.modelToSketchSpace(P3(ev("post1_cx"), ev(ycen_expr), pz))
        circ = psk.sketchCurves.sketchCircles.addByCenterRadius(
            P3(c.x, c.y, 0), ev("peg_dia / 2"))
        d.addRadialDimension(
            circ, P3(c.x + 0.4, c.y, 0)).parameter.expression = "peg_dia / 2"
        if anchor is not None:
            rdim(psk, d, anchor, circ.centerSketchPoint, orient, 'y',
                 "(%s) - (y_mid - (%s))" % (ycen_expr, half_w_expr))
            rdim(psk, d, anchor, circ.centerSketchPoint, orient, 'z', z_mag_expr)
        prof = sp.smallest_profile(psk)
        peg = sp.ext_new_sym(posts, prof, half_len_expr, name).bodies.item(0)
        peg.name = name
        for b in cut_bodies:
            sp.combine(b, [peg], CUT, True, name + "_" + b.name + "_Cut")
        return peg

    # 2 foot pegs (below the post bottom shoulder, into the foot) + 1 cap peg
    # (above the post top shoulder, into the cap); all on the left.
    peg_fa = make_peg("y_mid - " + foot_off, "post_bottom_z", -1, "mt_td_foot / 2",
                      "post_w_bot / 2", "foot_thick / 2 + 0.05 in",
                      [foot_l, post_l], "Peg_Fa_L")
    peg_fb = make_peg("y_mid + " + foot_off, "post_bottom_z", -1, "mt_td_foot / 2",
                      "post_w_bot / 2", "foot_thick / 2 + 0.05 in",
                      [foot_l, post_l], "Peg_Fb_L")
    peg_c = make_peg("y_mid", "cap_bottom_z", +1, "mt_td_cap / 2",
                     "post_w_top / 2", "cap_w / 2 + 0.05 in",
                     [cap_l, post_l], "Peg_C_L")

    # ── Mirror the completed left trestle (+ pegs) to the right ──
    # mirror_body copies the final B-rep, so mortises, tenons and peg holes
    # all carry over; the mirrored pegs fill the mirrored holes.
    foot_r = sp.mirror_body(feet, foot_l, xmid_plane(feet), "Foot_Mir").bodies.item(0)
    foot_r.name = "Foot_R"
    post_r = sp.mirror_body(posts, post_l, xmid_plane(posts), "Post_Mir").bodies.item(0)
    post_r.name = "Post_R"
    cap_r = sp.mirror_body(caps, cap_l, xmid_plane(caps), "Cap_Mir").bodies.item(0)
    cap_r.name = "Cap_R"
    for src, nm in ((peg_fa, "Peg_Fa_R"), (peg_fb, "Peg_Fb_R"), (peg_c, "Peg_C_R")):
        m = sp.mirror_body(posts, src, xmid_plane(posts), nm + "_Mir").bodies.item(0)
        m.name = nm

    # ════════════════════════════════════════════════════════════
    # PHASE 1+2 (cont.) — STRETCHER (shaped)
    # ════════════════════════════════════════════════════════════
    # ── Stretcher ── ref: Post_L (spans between posts, +X) ───────
    # Tapered (waisted) silhouette in X-Z: full height at the shoulders,
    # narrowing to str_h_mid at the center.
    ref = ctx.find_body("Post_L")
    post_l_outer_x = ref.boundingBox.minPoint.x      # tenon/shoulder reference
    spl = oplane(strc, strc.xZConstructionPlane, "y_mid", "Str_Pl")
    ssk = strc.sketches.add(spl)
    ssk.name = "Str_Sk"
    orient = sp.probe_orientations(ssk, ev("x_mid"), ev("y_mid"), ev("str_center_z"))
    m2s = ssk.modelToSketchSpace
    Y0 = ev("y_mid")
    xL = ev("x_mid - str_shoulder / 2"); xR = ev("x_mid + str_shoulder / 2")
    xm = ev("x_mid")
    scz = ev("str_center_z"); ar = ev("str_arch_rise"); w2 = ev("str_w") / 2.0
    end_top = scz + w2; end_bot = scz - w2           # at the tenons
    ct_top = scz + w2 + ar; ct_bot = scz - w2 + ar   # arched up at center

    def sp_(x, z):
        s = m2s(P3(x, Y0, z))
        return P3(s.x, s.y, 0)

    # Giant ARC of CONSTANT width str_w: both edges are PARALLEL splines that
    # rise by str_arch_rise from the tenon ends to the center (the highest
    # spot). Total vertical envelope = str_w + str_arch_rise. Draggable; lines
    # chain off the spline endpoints so the loop closes via shared points.
    SL = ssk.sketchCurves.sketchLines
    top_spl = fspline(ssk, m2s, [(xL, Y0, end_top), (xm, Y0, ct_top), (xR, Y0, end_top)])
    bot_spl = fspline(ssk, m2s, [(xR, Y0, end_bot), (xm, Y0, ct_bot), (xL, Y0, end_bot)])
    rend = SL.addByTwoPoints(top_spl.endSketchPoint, bot_spl.startSketchPoint)  # right (V)
    lend = SL.addByTwoPoints(bot_spl.endSketchPoint, top_spl.startSketchPoint)  # left (V)
    gc = ssk.geometricConstraints
    gc.addVertical(lend); gc.addVertical(rend)
    # Anchor the left shoulder to Post_L's projected inner face (proxy) — the
    # stretcher bears on the post there — instead of computed coordinates.
    project_face(ssk, post_l, posts_occ, "x", +1)
    sd = ssk.sketchDimensions
    aPs = anchor_pt(ssk, ev("x_mid - str_shoulder / 2"), Y0, ev("post_bottom_z"))
    TL = top_spl.startSketchPoint; TR = top_spl.endSketchPoint
    BR = bot_spl.startSketchPoint; BL = bot_spl.endSketchPoint
    rdim(ssk, sd, aPs, TL, orient, 'x', "0 in")                     # shoulder on post face
    rdim(ssk, sd, aPs, TL, orient, 'z', "str_center_z + str_w / 2 - post_bottom_z")
    rdim(ssk, sd, TL, TR, orient, 'x', "str_shoulder")             # shoulder-to-shoulder span
    rdim(ssk, sd, TL, TR, orient, 'z', "0 in")                     # both top corners level
    rdim(ssk, sd, TL, BL, orient, 'z', "str_w")                    # left end height
    rdim(ssk, sd, TR, BR, orient, 'z', "str_w")                    # right end height
    prof = sp.smallest_profile(ssk)
    stretcher = sp.ext_new_sym(strc, prof, "str_thick / 2", "StretcherBoard").bodies.item(0)
    stretcher.name = "Stretcher"

    # ════════════════════════════════════════════════════════════
    # PHASE 3b — STRETCHER THROUGH-TENONS (build one, mirror)
    # ════════════════════════════════════════════════════════════
    # Build the tenon from its SIDE profile (X-Z) with the rounded nose already
    # in it, extruded along Y (stt_thk). One clean extrude — no fragile tip cut.
    # The rounded front is a draggable 5-point spline (top->tip->bottom). The
    # rectangular root passes through the post (square mortise); only the proud
    # nose is rounded.
    def make_tenon_body(name):
        xsh = ev("x_mid - str_shoulder / 2")      # shoulder x (post inner face)
        tip = xsh - ev("str_tenon_d")             # proud tip x
        zc = ev("str_center_z"); w = ev("stt_wid") / 2.0; ymv = ev("y_mid")
        a1x = ev("0.34 in"); mx = ev("0.1 in"); mz = ev("0.75 in")  # nose control
        rpl = oplane(strc, strc.xZConstructionPlane, "y_mid", name + "_Pl")
        tsk = strc.sketches.add(rpl)
        tsk.name = name + "_Sk"
        cm = tsk.modelToSketchSpace

        def pt(x, z):
            s = cm(P3(x, ymv, z))
            return P3(s.x, s.y, 0)

        nose = fspline(tsk, cm, [(tip + a1x, ymv, zc + w), (tip + mx, ymv, zc + mz),
                                 (tip, ymv, zc),
                                 (tip + mx, ymv, zc - mz), (tip + a1x, ymv, zc - w)])
        L = tsk.sketchCurves.sketchLines
        bot = L.addByTwoPoints(nose.endSketchPoint, pt(xsh, zc - w))   # P2 -> shoulder bot
        sh = L.addByTwoPoints(bot.endSketchPoint, pt(xsh, zc + w))     # shoulder bot -> top
        topl = L.addByTwoPoints(sh.endSketchPoint, nose.startSketchPoint)  # top -> P1 (nose)
        # Anchor the shoulder to Post_L's projected inner face (proxy) — the
        # tenon shoulder seats against it — not to a computed coordinate.
        tor = sp.probe_orientations(tsk, xsh, ymv, zc)
        project_face(tsk, post_l, posts_occ, "x", +1)
        td_ = tsk.sketchDimensions
        tgc = tsk.geometricConstraints
        for ln_ in (bot, sh, topl):                  # shoulder vertical, edges horizontal
            g1 = ln_.startSketchPoint.geometry; g2 = ln_.endSketchPoint.geometry
            if abs(g1.x - g2.x) >= abs(g1.y - g2.y):
                tgc.addHorizontal(ln_)
            else:
                tgc.addVertical(ln_)
        aPt = anchor_pt(tsk, xsh, ymv, ev("post_bottom_z"))
        rdim(tsk, td_, aPt, sh.startSketchPoint, tor, 'x', "0 in")        # shoulder on post face
        rdim(tsk, td_, aPt, sh.startSketchPoint, tor, 'z',
             "str_center_z - stt_wid / 2 - post_bottom_z")
        rdim(tsk, td_, sh.startSketchPoint, sh.endSketchPoint, tor, 'z', "stt_wid")  # tenon height
        # straight run from shoulder to the rounded-nose endpoints (nose interior free)
        rdim(tsk, td_, bot.startSketchPoint, bot.endSketchPoint, tor, 'x', "str_tenon_d - 0.34 in")
        rdim(tsk, td_, topl.startSketchPoint, topl.endSketchPoint, tor, 'x', "str_tenon_d - 0.34 in")
        prof = sp.smallest_profile(tsk)
        tb = sp.ext_new_sym(strc, prof, "stt_thk / 2", name + "_Tenon").bodies.item(0)
        tb.name = name + "_Tenon"
        return tb

    tb_l = make_tenon_body("STT_L")
    sp.combine(post_l, [tb_l], CUT, True, "STT_L_Mort")
    tb_r = sp.mirror_body(strc, tb_l, xmid_plane(strc), "STT_Mir").bodies.item(0)
    tb_r.name = "STT_R_Tenon"
    sp.combine(post_r, [tb_r], CUT, True, "STT_R_Mort")
    sp.combine(stretcher, [tb_l, tb_r], JOIN, False, "STT_Join")

    # ════════════════════════════════════════════════════════════
    # PHASE 3c — TUSK WEDGES (build one, mirror)
    # ════════════════════════════════════════════════════════════
    # A vertical key driven down through the proud tenon. Its VERTICAL face
    # sits on the post's outer face (bearing on the leg); its 8deg ANGLED
    # face bears on the tenon's mortise wall. Thicker at the top, so tapping
    # it down draws the stretcher shoulder tight against the post. The blade
    # (wdg_y) is narrower than the tenon, leaving side material so the tenon
    # tip stays attached.
    def tusk_wedge(xb_expr, name):
        # xb_expr = post outer face X (vertical bearing face); wedge grows -X
        wpl = oplane(wcomp, wcomp.xZConstructionPlane, "y_mid", name + "_Pl")
        wsk = wcomp.sketches.add(wpl)
        wsk.name = name + "_Sk"
        wor = sp.probe_orientations(wsk, ev(xb_expr), ev("y_mid"),
                                    ev("str_center_z"))
        m2 = wsk.modelToSketchSpace
        xb = ev(xb_expr); zb = ev("str_center_z - wdg_l / 2")
        zt = ev("str_center_z + wdg_l / 2")
        xthin = ev("wdg_xthin"); taper = ev("wedge_taper"); ym = ev("y_mid")

        def wp(x, z):
            s = m2(P3(x, ym, z))
            return P3(s.x, s.y, 0)

        cdrop = ev("wdg_crown_drop"); cmx = ev("wdg_crown_mid_x"); cmd = ev("wdg_crown_mid_drop")
        ln = wsk.sketchCurves.sketchLines
        la = ln.addByTwoPoints(wp(xb, zb), wp(xb - xthin, zb))            # bottom A->B
        # Rounded top (captured from the user's manual edit): the angled-side
        # top drops cdrop below the peak, then the crown spline rises across to
        # the post-side top (D), which is the highest point. Draggable.
        top_spl = fspline(wsk, m2, [(xb - xthin - taper, ym, zt - cdrop),
                                    (xb - cmx, ym, zt - cmd), (xb, ym, zt)])
        lb = ln.addByTwoPoints(la.endSketchPoint, top_spl.startSketchPoint)  # angled B->C
        bearing = ln.addByTwoPoints(top_spl.endSketchPoint, la.startSketchPoint)  # D->A
        gc = wsk.geometricConstraints
        # XZ plane: bottom spans model-X -> sketch-H; bearing spans Z -> V
        gc.addHorizontal(la); gc.addVertical(bearing)
        A, B = la.startSketchPoint, la.endSketchPoint
        C, D = top_spl.startSketchPoint, top_spl.endSketchPoint
        d = wsk.sketchDimensions
        # Anchor the bearing face to the projected POST outer face (its real
        # dependency) instead of origin; the Z is placed (rides the stretcher).
        wsk.project(sp.find_face(post_l, "x", -1).createForAssemblyContext(posts_occ))
        sp.refs_to_construction(wsk)
        # target the post-TOP corner explicitly so the Z reference is unambiguous
        # (anchor_pt picks the nearest projected endpoint; str_center_z is closer
        # to neither end reliably, so aim at the top).
        aP = anchor_pt(wsk, ev(xb_expr), ev("y_mid"), ev("cap_bottom_z"))
        rdim(wsk, d, aP, A, wor, 'x', "0 in")                    # bearing on post outer face
        rdim(wsk, d, aP, A, wor, 'z', "cap_bottom_z - str_center_z + wdg_l / 2")  # ride height
        rdim(wsk, d, A, B, wor, 'x', "wdg_xthin")
        rdim(wsk, d, A, D, wor, 'z', "wdg_l")
        rdim(wsk, d, D, C, wor, 'x', "wdg_xthin + wedge_taper")
        rdim(wsk, d, D, C, wor, 'z', "wdg_crown_drop")           # angled-side top below crown
        prof = sp.smallest_profile(wsk)
        wb = sp.ext_new_sym(wcomp, prof, "wdg_y / 2", name).bodies.item(0)
        wb.name = name
        sp.combine(stretcher, [wb], CUT, True, name + "_Slot")   # mortise the tenon
        return wb

    wedge_l = tusk_wedge("post1_cx - post_thick / 2", "Wedge_L")
    wedge_r = sp.mirror_body(wcomp, wedge_l, xmid_plane(wcomp),
                             "Wedge_Mir").bodies.item(0)
    wedge_r.name = "Wedge_R"
    sp.combine(stretcher, [wedge_r], CUT, True, "Wedge_R_Slot")

    # ════════════════════════════════════════════════════════════
    # PHASE 1+2 (cont.) — TOP + BATTENS
    # ════════════════════════════════════════════════════════════
    # ── Top ── ref: Cap_L (rests on caps, +Z) ────────────────────
    # Plan outline: straight long sides; convex short ends crowning out by
    # top_crown at the center (draggable end splines). Then a 45 chamfer on
    # the top perimeter (¼ of the ¾ thickness; the lower ½ stays flat square).
    ref = ctx.find_body("Cap_L")
    cap_top_z = ref.boundingBox.maxPoint.z
    tpl = oplane(topc, topc.xYConstructionPlane, "top_bottom_z", "Top_Pl")
    tsk = topc.sketches.add(tpl)
    tsk.name = "Top_Sk"
    tm2s = tsk.modelToSketchSpace
    tl = ev("table_l"); tw = ev("table_w"); tym = ev("y_mid")
    tz = ev("top_bottom_z"); cr = ev("top_crown")
    right_arc = fspline(tsk, tm2s, [(tl, 0, tz), (tl + cr, tym, tz), (tl, tw, tz)])
    left_arc = fspline(tsk, tm2s, [(0, tw, tz), (-cr, tym, tz), (0, 0, tz)])
    TLn = tsk.sketchCurves.sketchLines
    front = TLn.addByTwoPoints(left_arc.endSketchPoint, right_arc.startSketchPoint)  # A->B
    back = TLn.addByTwoPoints(right_arc.endSketchPoint, left_arc.startSketchPoint)   # C->D
    # Anchor the top to Cap_L's projected top face (proxy) — the slab rests on it.
    tor_top = sp.probe_orientations(tsk, ev("post1_cx"), ev("y_mid"), ev("top_bottom_z"))
    project_face(tsk, cap_l, caps_occ, "z", +1)
    topd = tsk.sketchDimensions
    tgc = tsk.geometricConstraints
    tgc.addHorizontal(front); tgc.addHorizontal(back)     # long sides run in X
    A = left_arc.endSketchPoint; B = right_arc.startSketchPoint
    C = right_arc.endSketchPoint; D = left_arc.startSketchPoint
    # anchor the front-RIGHT corner B (table_l, 0) — NOT the front-left A at world
    # (0,0), which would read as an origin reference for any dim touching it.
    aCt = anchor_pt(tsk, ev("post1_cx + cap_w / 2"), ev("y_mid - cap_len / 2"),
                    ev("top_bottom_z"))
    rdim(tsk, topd, aCt, B, tor_top, 'x', "table_l - post1_cx - cap_w / 2")
    rdim(tsk, topd, aCt, B, tor_top, 'y', "y_mid - cap_len / 2")
    # the two curved short ends are vertical stiles: link their endpoints with
    # construction lines so the corners x-align WITHOUT dimensioning the origin
    # corner A. B/C and the back length then locate everything; A falls out.
    def cstile(p_lo, p_hi):
        cl = TLn.addByTwoPoints(P3(p_lo.geometry.x, p_lo.geometry.y, 0),
                                P3(p_hi.geometry.x, p_hi.geometry.y, 0))
        cl.isConstruction = True
        tgc.addCoincident(cl.startSketchPoint, p_lo)
        tgc.addCoincident(cl.endSketchPoint, p_hi)
        tgc.addVertical(cl)
    cstile(B, C)                                          # right end: B.x == C.x
    cstile(A, D)                                          # left  end: A.x == D.x
    rdim(tsk, topd, B, C, tor_top, 'y', "table_w")        # table width
    rdim(tsk, topd, back.startSketchPoint, back.endSketchPoint, tor_top, 'x', "table_l")
    prof = sp.smallest_profile(tsk)
    top = sp.ext_new(topc, prof, "top_thick", "TopBoard").bodies.item(0)
    top.name = "Top"
    chamfer_face(topc, sp.find_face(top, "z", +1), "top_chamfer", "Top_Chamfer")

    # ── Battens ── ref: Top (fastened under top, -Z) ─────────────
    # 3 battens (ends + center). Each has a flat top against the tabletop and
    # an underside that sweeps up to thin, rounded ends (draggable spline).
    ref = ctx.find_body("Top")
    top_under_z = ref.boundingBox.minPoint.z

    def build_batten(xc_expr, name):
        bpl = oplane(batc, batc.yZConstructionPlane, xc_expr, name + "_Pl")
        bsk = batc.sketches.add(bpl)
        bsk.name = name + "_Sk"
        bm2s = bsk.modelToSketchSpace
        X0b = ev(xc_expr); bym = ev("y_mid")
        byL = ev("y_mid - bat_len / 2"); byR = ev("y_mid + bat_len / 2")
        btop = ev("top_bottom_z"); bbc = ev("bat_bottom_z")
        bbe = ev("top_bottom_z - bat_end_thick")

        def bp(y, z):
            s = bm2s(P3(X0b, y, z))
            return P3(s.x, s.y, 0)

        ber = ev("bat_end_round"); ym2 = ev("y_mid")
        # FLAT bottom; only the ends round up. leftR carries the user's manual
        # edit (mid + a slightly thicker, less-pointed tip); rightR is its
        # Y-mirror so both ends match. Draggable.
        em_y = ev("2.622 in"); em_z = ev("27.398 in"); etip_z = ev("27.905 in")
        leftR = fspline(bsk, bm2s, [(X0b, byL + ber, bbc),
                                    (X0b, em_y, em_z),
                                    (X0b, byL, etip_z)])         # left end (user)
        rightR = fspline(bsk, bm2s, [(X0b, byR, etip_z),
                                     (X0b, 2 * ym2 - em_y, em_z),
                                     (X0b, byR - ber, bbc)])     # right end (mirror)
        BLn = bsk.sketchCurves.sketchLines
        fb = BLn.addByTwoPoints(rightR.endSketchPoint, leftR.startSketchPoint)  # flat bottom RE->LS
        e1 = BLn.addByTwoPoints(leftR.endSketchPoint, bp(byL, btop))   # left end up LE->T1
        e2 = BLn.addByTwoPoints(e1.endSketchPoint, bp(byR, btop))      # top flat T1->T2
        rd = BLn.addByTwoPoints(e2.endSketchPoint, rightR.startSketchPoint)  # right end down T2->RS
        # Anchor the batten's flat top to the Top's projected underside (proxy) —
        # the batten is fastened up against it — not to a computed coordinate.
        bor = sp.probe_orientations(bsk, X0b, ev("y_mid"), ev("top_bottom_z"))
        project_face(bsk, ctx.find_body("Top"), top_occ, "z", -1)
        bd = bsk.sketchDimensions
        bgc = bsk.geometricConstraints
        for ln_ in (e1, e2, rd):                      # end faces vertical, top flat horizontal
            g1 = ln_.startSketchPoint.geometry; g2 = ln_.endSketchPoint.geometry
            if abs(g1.x - g2.x) >= abs(g1.y - g2.y):
                bgc.addHorizontal(ln_)
            else:
                bgc.addVertical(ln_)
        T1 = e2.startSketchPoint; T2 = e2.endSketchPoint     # top-flat corners (at byL, byR)
        LE = e1.startSketchPoint; RS = rd.endSketchPoint     # thin end tips
        LS = leftR.startSketchPoint; RE = rightR.endSketchPoint  # flat-bottom inboard ends
        aTb = anchor_pt(bsk, X0b, ev("y_mid - bat_len / 2"), ev("top_bottom_z"))
        rdim(bsk, bd, aTb, T1, bor, 'z', "0 in")             # batten top on the top underside
        rdim(bsk, bd, aTb, T1, bor, 'y', "y_mid - bat_len / 2")
        rdim(bsk, bd, T1, T2, bor, 'y', "bat_len")           # batten length
        # thin rounded ends (tuned tip height) + flat-bottom run (interiors stay free)
        rdim(bsk, bd, T1, LE, bor, 'z', "top_bottom_z - 27.905 in")
        rdim(bsk, bd, T2, RS, bor, 'z', "top_bottom_z - 27.905 in")
        rdim(bsk, bd, T1, LS, bor, 'y', "bat_end_round")
        rdim(bsk, bd, T1, LS, bor, 'z', "bat_thick")
        rdim(bsk, bd, T2, RE, bor, 'y', "bat_end_round")
        rdim(bsk, bd, T2, RE, bor, 'z', "bat_thick")
        prof = sp.smallest_profile(bsk)
        ext = sp.ext_new_sym(batc, prof, "bat_w / 2", name)
        ext.bodies.item(0).name = name
        return ext

    # ── Batten screw holes: center = round (the fixed point); two outer =
    #    slotted, elongated in Y so the tabletop can expand/contract across
    #    its width while the screws hold it flat. ──
    midz_expr = "(top_bottom_z + bat_bottom_z) / 2"
    hpl = oplane(batc, batc.xYConstructionPlane, midz_expr, "BatHole_Pl")

    # Reference like a maker would: project the batten's own top face (parallel
    # to the hole plane → a real rectangle) and dimension each hole from the
    # batten's near corner with an X/Y offset — not from a computed coordinate.
    def bat_anchor(sk, b, mx, my):
        sk.project(sp.find_face(b, "z", +1))    # batten top face (same comp → native)
        sp.refs_to_construction(sk)
        return anchor_pt(sk, mx, my, ev(midz_expr))

    def batten_hole(b, xexpr, yexpr, slotted, name):
        byL = "y_mid - bat_len / 2"                       # batten near (min-Y) end
        yoff = "(%s) - (%s)" % (yexpr, byL)               # hole Y from that end
        sk = batc.sketches.add(hpl)
        sk.name = name + "_Sk"
        d = sk.sketchDimensions
        orient = sp.probe_orientations(sk, ev(xexpr), ev(yexpr), ev(midz_expr))
        anchor = bat_anchor(sk, b, ev(xexpr) - ev("bat_w") / 2.0, ev(byL))
        xc = ev(xexpr); yc = ev(yexpr); zc = ev(midz_expr)
        cc = sk.modelToSketchSpace(P3(xc, yc, zc))
        if slotted:
            # stadium elongated along model-Y, drawn fresh and dimensioned to the
            # corner (same pattern-safe recipe as the round hole below).
            PI = 3.141592653589793
            r = ev("bat_screw_dia") / 2.0
            hl = (ev("bat_slot_len") - ev("bat_screw_dia")) / 2.0
            dy = sk.modelToSketchSpace(P3(xc, yc + 1, zc))
            vy = 1.0 if (dy.y - cc.y) >= 0 else -1.0
            lines = sk.sketchCurves.sketchLines
            arcs = sk.sketchCurves.sketchArcs
            br = P3(cc.x + r, cc.y - hl, 0); tr = P3(cc.x + r, cc.y + hl, 0)
            tc = P3(cc.x, cc.y + hl, 0); tl = P3(cc.x - r, cc.y + hl, 0)
            bl = P3(cc.x - r, cc.y - hl, 0); bc = P3(cc.x, cc.y - hl, 0)
            l_r = lines.addByTwoPoints(br, tr)
            a_t = arcs.addByCenterStartSweep(tc, tr, PI)
            l_l = lines.addByTwoPoints(tl, bl)
            a_b = arcs.addByCenterStartSweep(bc, bl, PI)
            gc = sk.geometricConstraints
            gc.addVertical(l_r); gc.addVertical(l_l)
            # close the loop topologically so endpoints can't slide (full constraint)
            gc.addCoincident(l_r.endSketchPoint, a_t.startSketchPoint)
            gc.addCoincident(a_t.endSketchPoint, l_l.startSketchPoint)
            gc.addCoincident(l_l.endSketchPoint, a_b.startSketchPoint)
            gc.addCoincident(a_b.endSketchPoint, l_r.startSketchPoint)
            gc.addTangent(l_r, a_t); gc.addTangent(a_t, l_l)
            gc.addTangent(l_l, a_b); gc.addTangent(a_b, l_r)
            d.addRadialDimension(a_b, P3(cc.x + r + 1, cc.y - hl, 0)
                                 ).parameter.expression = "bat_screw_dia / 2"
            d.addDistanceDimension(a_b.centerSketchPoint, a_t.centerSketchPoint,
                                   orient['y'], P3(cc.x + r + 2, cc.y, 0)
                                   ).parameter.expression = "bat_slot_len - bat_screw_dia"
            near = a_b if vy > 0 else a_t          # low-model-Y arc center
            ctr = near.centerSketchPoint
            yref = "(%s) - (bat_slot_len - bat_screw_dia) / 2" % yoff
        else:
            circ = sk.sketchCurves.sketchCircles.addByCenterRadius(
                P3(cc.x, cc.y, 0), ev("bat_screw_dia") / 2.0)
            d.addRadialDimension(
                circ, P3(cc.x + 0.3, cc.y, 0)).parameter.expression = "bat_screw_dia / 2"
            ctr = circ.centerSketchPoint
            yref = yoff
        # locate the hole from the batten corner: X centered, Y offset from the end
        rdim(sk, d, anchor, ctr, orient, 'x', "bat_w / 2")
        rdim(sk, d, anchor, ctr, orient, 'y', yref)
        prof = sp.smallest_profile(sk)
        # Build the hole as a solid TOOL body (NewBody) rather than cutting here.
        # A patterned CUT of an elongated profile fails to paste (NO_TARGET); a
        # NewBody patterns cleanly. We pattern the tools with the batten, then
        # bulk-cut once — so the holes stay referenced to the batten corner AND
        # replicate by pattern (no per-batten sketching).
        tool = sp.ext_new_sym(batc, prof, "(bat_thick + 0.2 in) / 2", name)
        tool.bodies.item(0).name = name
        return tool

    # ONE template batten + its 3 hole tools (all anchored to the batten corner),
    # then pattern the whole group to n_battens and bulk-cut each batten.
    bat_ext = build_batten("bat_inset", "Batten")
    bat_body = bat_ext.bodies.item(0)
    tc_ = batten_hole(bat_body, "bat_inset", "y_mid", False, "BatTool_C")
    ta_ = batten_hole(bat_body, "bat_inset", "y_mid - bat_hole_off", True, "BatTool_A")
    tb_ = batten_hole(bat_body, "bat_inset", "y_mid + bat_hole_off", True, "BatTool_B")
    feat_pattern_multi(batc, [bat_ext, tc_, ta_, tb_], batc.xConstructionAxis,
                       "n_battens", "bat_pitch", "Batten_Pat")

    def _bx(b):
        return (b.boundingBox.minPoint.x + b.boundingBox.maxPoint.x) / 2.0

    allb = [batc.bRepBodies.item(i) for i in range(batc.bRepBodies.count)]
    battens = sorted([b for b in allb if b.name.startswith("Batten")], key=_bx)
    tools = [b for b in allb if b.name.startswith("BatTool")]
    for bt in battens:                         # each batten loses its 3 screw holes
        mine = [t for t in tools if abs(_bx(t) - _bx(bt)) < ev("bat_w")]
        sp.combine(bt, mine, CUT, False, bt.name + "_Holes")
    for b, nm in zip(battens, ["Batten_L", "Batten_C", "Batten_R"]):
        b.name = nm

    # ════════════════════════════════════════════════════════════
    # PHASE 3d — TABLETOP BUTTONS (cap-to-top fasteners)
    # ════════════════════════════════════════════════════════════
    # Each button is an L-block (in the TOP's component): body (¾x¾) under the
    # top just inboard of the cap; a tongue into an elongated cap slot. Built
    # ONCE on the left cap, PATTERNED ×3 along Y, MIRRORED across x_mid to the
    # right cap, then each cap is bulk-cut by its 3 slot tools.
    def hvconstrain(sk, line, kind):
        try:
            if kind == "h":
                sk.geometricConstraints.addHorizontal(line)
            else:
                sk.geometricConstraints.addVertical(line)
        except Exception:
            pass

    def coincident(sk, p_a, p_b):
        try:
            sk.geometricConstraints.addCoincident(p_a, p_b)
            return True
        except Exception:
            _SKIPPED.append(("coincident", sk.name))
            return False

    # Reference the cap (a different component → assembly proxy) inner-top corner.
    # The cap is NOT patterned, so the projection is stable across the button
    # pattern. Returns the projected corner point nearest (xi, zi) on the sketch.
    def cap_corner(sk, cap_body, cap_occ, ax_in, xi, zi, ymv):
        for f in (sp.find_face(cap_body, "x", ax_in), sp.find_face(cap_body, "z", +1)):
            sk.project(f.createForAssemblyContext(cap_occ))
        sp.refs_to_construction(sk)
        return anchor_pt(sk, xi, ymv, zi)

    def button_pair(ci_expr, sgn, ycen_expr, bname, sname, cap_body, cap_occ):
        ci = ev(ci_expr); ymv = ev(ycen_expr)
        bl = ev("btn_body_len"); td = ev("btn_tongue_d")
        tu = ev("top_bottom_z"); bot = tu - ev("btn_h"); ttop = bot + ev("btn_tongue_h")
        bxe = ci + sgn * bl; txe = ci - sgn * td
        bpl = oplane(topc, topc.xZConstructionPlane, ycen_expr, bname + "_Pl")
        # ── L body, anchored to the cap's inner-top edge (ci, tu) ──
        sk = topc.sketches.add(bpl); sk.name = bname + "_Sk"
        orient = sp.probe_orientations(sk, ci, ymv, tu)
        d = sk.sketchDimensions
        anchor = cap_corner(sk, cap_body, cap_occ, sgn, ci, tu, ymv)
        m2 = sk.modelToSketchSpace
        pts = [(txe, bot), (bxe, bot), (bxe, tu), (ci, tu), (ci, ttop), (txe, ttop)]
        Pp = [m2(P3(x, ymv, z)) for (x, z) in pts]
        sptp = [P3(p.x, p.y, 0) for p in Pp]
        ln = sk.sketchCurves.sketchLines
        L = [ln.addByTwoPoints(sptp[0], sptp[1])]
        for k in range(1, 5):
            L.append(ln.addByTwoPoints(L[-1].endSketchPoint, sptp[k + 1]))
        L.append(ln.addByTwoPoints(L[-1].endSketchPoint, L[0].startSketchPoint))
        for ln_, kind in ((L[0], "h"), (L[2], "h"), (L[4], "h"),
                          (L[1], "v"), (L[3], "v"), (L[5], "v")):
            hvconstrain(sk, ln_, kind)
        # shape from the part's own parameters
        # dimension chain (spanning tree rooted at P3) so EVERY vertex grounds
        rdim(sk, d, L[2].startSketchPoint, L[2].endSketchPoint, orient, 'x', "btn_body_len")
        rdim(sk, d, L[1].startSketchPoint, L[1].endSketchPoint, orient, 'z', "btn_h")
        rdim(sk, d, L[3].startSketchPoint, L[3].endSketchPoint, orient, 'z', "btn_h - btn_tongue_h")
        rdim(sk, d, L[4].startSketchPoint, L[4].endSketchPoint, orient, 'x', "btn_tongue_d")
        rdim(sk, d, L[5].startSketchPoint, L[5].endSketchPoint, orient, 'z', "btn_tongue_h")
        # pin the cap-inner-top vertex (P3) onto the projected cap corner
        if anchor is not None:
            coincident(sk, L[2].endSketchPoint, anchor)
        be = sp.ext_new_sym(topc, sp.smallest_profile(sk), "btn_w / 2", bname)
        be.bodies.item(0).name = bname
        # ── slot tool (tongue cross-section), also anchored to the cap face ──
        ssk = topc.sketches.add(bpl); ssk.name = sname + "_Sk"
        od = ssk.sketchDimensions
        oan = cap_corner(ssk, cap_body, cap_occ, sgn, ci, tu, ymv)
        sm = ssk.modelToSketchSpace
        # rect corners: inner-top(ci,ttop) inner-bot(ci,bot) outer-bot(txe,bot) outer-top(txe,ttop)
        rp = [sm(P3(x, ymv, z)) for (x, z) in
              [(ci, ttop), (ci, bot), (txe, bot), (txe, ttop)]]
        rs = [P3(p.x, p.y, 0) for p in rp]
        sl = ssk.sketchCurves.sketchLines
        R = [sl.addByTwoPoints(rs[0], rs[1])]
        for k in range(1, 3):
            R.append(sl.addByTwoPoints(R[-1].endSketchPoint, rs[k + 1]))
        R.append(sl.addByTwoPoints(R[-1].endSketchPoint, R[0].startSketchPoint))
        for ln_, kind in ((R[0], "v"), (R[2], "v"), (R[1], "h"), (R[3], "h")):
            hvconstrain(ssk, ln_, kind)
        # chain Q3→Q0→Q1→Q2 so every rect vertex grounds off the anchored Q3
        rdim(ssk, od, R[3].startSketchPoint, R[3].endSketchPoint, orient, 'x', "btn_tongue_d")
        rdim(ssk, od, R[0].startSketchPoint, R[0].endSketchPoint, orient, 'z', "btn_tongue_h")
        rdim(ssk, od, R[1].startSketchPoint, R[1].endSketchPoint, orient, 'x', "btn_tongue_d")
        # outer-top rect corner: btn_tongue_d in from the cap face, btn_h-btn_tongue_h below cap top
        if oan is not None:
            rdim(ssk, od, oan, R[3].startSketchPoint, orient, 'x', "btn_tongue_d")
            rdim(ssk, od, oan, R[3].startSketchPoint, orient, 'z', "btn_h - btn_tongue_h")
        se = sp.ext_new_sym(topc, sp.smallest_profile(ssk),
                            "btn_w / 2 + btn_slot_extra", sname)
        se.bodies.item(0).name = sname
        return be, se

    cap_l = ctx.find_body("Cap_L"); cap_r = ctx.find_body("Cap_R")
    be, se = button_pair("post1_cx + cap_w / 2", +1, "y_mid - btn_off",
                          "Button", "Slot", cap_l, caps_occ)
    feat_pattern_multi(topc, [be, se], topc.yConstructionAxis, "3", "btn_off", "Btn_PatY")
    topbodies = lambda: [topc.bRepBodies.item(i) for i in range(topc.bRepBodies.count)]
    seed = [b for b in topbodies() if b.name.startswith(("Button", "Slot"))]
    sp.mirror_bodies(topc, seed, xmid_plane(topc), "Btn_Mir")
    # bulk-cut each cap with its 3 slot tools (consume them)
    xm_val = ev("x_mid")

    def cx(b):
        return (b.boundingBox.minPoint.x + b.boundingBox.maxPoint.x) / 2.0

    lslots = [b for b in topbodies() if b.name.startswith("Slot") and cx(b) < xm_val]
    rslots = [b for b in topbodies() if b.name.startswith("Slot") and cx(b) >= xm_val]
    sp.combine(cap_l, lslots, CUT, False, "Btn_SlotCut_L")
    sp.combine(cap_r, rslots, CUT, False, "Btn_SlotCut_R")
    # rename the 6 button bodies Btn_{L,R}{0,1,2} by position
    btns = [b for b in topbodies() if b.name.startswith("Button")]
    for side, on_left in (("L", True), ("R", False)):
        col = sorted([b for b in btns if (cx(b) < xm_val) == on_left],
                     key=lambda b: (b.boundingBox.minPoint.y + b.boundingBox.maxPoint.y))
        for i, b in enumerate(col):
            b.name = "Btn_%s%d" % (side, i)

    # ── Diagnostics ──────────────────────────────────────────────
    names = [b.name for b in ctx.find_bodies("*")]
    print("bodies:", sorted(names))
    print("count:", len(names))
    print("post_l_outer_x(cm):", round(post_l_outer_x, 3))
    print("skipped dims:", _SKIPPED)
