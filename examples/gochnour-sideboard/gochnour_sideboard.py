"""Gochnour Sideboard — FWW #277 (mitered-dovetail case corners)
Contemporary white oak sideboard with sliding frame-and-panel doors,
side-hung dovetailed drawers, tapered legs. By Chris Gochnour.

Overall: 48 in. wide x 15-3/4 in. deep x ~36-5/8 in. tall

Build notes:
- The leg is tapered ONCE (Leg_FL) then mirrored to the other 3 corners.
- The base frame is built slightly deeper than the case (frame_d = case_d +
  2*reveal) in positive Y, then Move'd -reveal so it sits proud of the case
  front & back by `reveal`.
- Case corners: mitered dovetails. One base pair of pins per corner, JOIN'd
  then rectangular-patterned along the depth for all md_n_pairs pairs.
- Doors: frame-and-panel (2 stiles + 2 rails + spalted-maple center panel),
  with a turned knob on the OUTER stile of each door.
- Drawers: dovetailed_drawer template (half-blind front, through back), built
  at y_offset=0 then Move'd so the front is flush with the door inner face;
  each front has a spherical cove recess with a turned knob at its center;
  patterned x3 up the case.
"""
import adsk.core, adsk.fusion, math
from helpers import sp
from woodworking.templates._dovetail_common import trapezoid_sketch
from woodworking.templates import dovetailed_drawer
from woodworking.templates import domino
from woodworking.templates import dowel

CUT  = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
NEW  = adsk.fusion.FeatureOperations.NewBodyFeatureOperation


def run(context):
    ctx = sp.DesignContext()
    app, design, root, params = ctx.app, ctx.design, ctx.root, ctx.params
    ev = ctx.ev
    P = adsk.core.Point3D.create
    VI = adsk.core.ValueInput.createByString

    def padd(name, expr, unit, comment=""):
        p = params.itemByName(name)
        if p is not None:
            try: p.expression = expr
            except Exception: pass
            return p
        return params.add(name, VI(expr), unit, comment)

    # ── Global ──
    padd("case_w",  "48 in",     "in", "Case external width")
    padd("case_h",  "14.625 in", "in", "Case external height")
    padd("case_d",  "15.75 in",  "in", "Case external depth")
    padd("case_t",  "0.75 in",   "in", "Case board thickness")
    padd("leg_sq",   "1.75 in",  "in", "Leg stock square")
    padd("leg_h",    "22 in",    "in", "Leg height")
    padd("leg_foot", "0.75 in",  "in", "Leg foot dimension (tapered)")
    padd("rail_w",   "1.875 in", "in", "Rail width/height")
    # Frame slightly deeper than case: frame_d = case_d + 2*reveal, built in
    # positive Y then Move'd -reveal so it sits proud of the case.
    padd("reveal",  "0.125 in",         "in", "Frame proud of case in depth (each side)")
    padd("frame_d", "case_d + 2 * reveal", "in", "Frame total depth (deeper than case)")
    padd("taper_start_z", "leg_h - rail_w", "in", "Z where taper begins")
    padd("x_mid", "case_w / 2", "in", "X midplane")
    padd("y_mid", "frame_d / 2", "in", "Y midplane (frame center, before reveal Move)")

    # ── Doors (defined early so partition/drawer fronts can reference them) ──
    padd("door_t",  "0.6875 in",  "in", "Door thickness")
    padd("door_gap", "0.0625 in", "in", "Door sliding clearance")
    padd("door_h",  "case_h - 2 * case_t - 0.25 in", "in", "Door height")
    padd("door_inner_y", "door_t + door_gap", "in", "Door inner face Y")

    # ── Compartments ──
    padd("door_comp_w",   "15.125 in", "in", "Door compartment width")
    padd("part_t",        "0.75 in",   "in", "Partition thickness")
    padd("drawer_comp_w", "case_w - 2 * case_t - 2 * door_comp_w - 2 * part_t", "in", "Drawer compartment width")
    padd("part_front_inset", "door_inner_y", "in", "Partition front inset = door inner face")
    padd("part_back_inset",  "0.4375 in", "in", "Partition back inset")
    padd("part_h", "case_h - 2 * case_t", "in", "Partition height")
    padd("back_t", "0.4375 in", "in", "Back panel thickness")

    # ── Door frame-and-panel + knobs ──
    padd("stile_w",     "1.5 in",   "in", "Door frame stile width")
    padd("door_rail_h", "1.875 in", "in", "Door frame rail height")
    padd("panel_t",     "0.25 in",  "in", "Door center panel thickness")
    padd("door_z0",     "leg_h + case_t + (part_h - door_h) / 2", "in", "Door bottom Z")
    padd("door_w",      "door_comp_w - 2 * door_gap", "in", "Door leaf width")
    padd("knob_dia",    "1 in",     "in", "Turned knob diameter")
    padd("knob_proj",   "0.625 in", "in", "Turned knob projection past the face")
    padd("knob_base_r", "knob_dia * 0.3", "in", "Knob flat-base radius (sits ON the surface)")
    # Dowel joinery: the knob only CONTACTS the surface; a dowel seated into
    # both the knob and the board provides the mechanical connection.
    padd("knob_dowel_d", "0.3125 in", "in", "Knob-to-board dowel diameter")

    # ── Leg↔rail double-domino joinery ──
    padd("dm_t", "0.3125 in", "in", "Domino thickness (short)")
    padd("dm_w", "1 in",      "in", "Domino width (long)")
    padd("dm_d", "0.5 in",    "in", "Domino depth per side")
    # Center-to-center spacing of the pair. Kept tight (centered in the joint)
    # so neither domino sits near a show surface — more material = more strength.
    padd("dm_pair_sp", "0.625 in", "in", "Domino pair center-to-center spacing")

    # ── Sliding-door track (FWW #277 "Sweet-sliding doors" detail) ──
    # A single groove top & bottom; the two coplanar doors slide one-at-a-time
    # in front of the center drawers. Tongues on the door edges ride the grooves.
    padd("door_tongue_w",   "0.375 in",   "in", "Door tongue / groove width (3/8\")")
    padd("door_tongue_top_h","0.25 in",   "in", "Top tongue length into top groove (1/4\")")
    padd("door_tongue_bot_h","0.15625 in","in", "Bottom tongue length into bottom groove (5/32\")")
    padd("groove_top_d",    "0.3125 in",  "in", "Top groove depth (5/16\")")
    padd("groove_bot_d",    "0.0625 in",  "in", "Bottom groove depth (1/16\")")
    padd("door_tongue_y0",  "door_gap + door_t / 2 - door_tongue_w / 2", "in", "Tongue/groove near-Y edge (centered on door)")

    # ── Drawers ──
    padd("n_drawers", "3", "", "Number of drawers")
    padd("drawer_front_t", "0.625 in",  "in", "Drawer front thickness")
    padd("drawer_gap",     "0.0625 in", "in", "Gap between drawers")
    padd("drawer_h", "(case_h - 2 * case_t - 4 * drawer_gap) / n_drawers", "in", "Single drawer height")

    # ── Mitered-dovetail case joinery (paired pins) ──
    padd("md_angle",     "8 deg",    "deg", "Dovetail flank angle")
    padd("md_pin_w",     "0.5 in",   "in",  "Pin width at wide face")
    padd("md_pair_gap",  "0.1875 in","in",  "Gap between pins of a pair")
    padd("md_n_pairs",   "6",        "",    "Pin pairs per corner edge")
    padd("md_half_tail", "0.6875 in","in",  "Half-tail at each edge")
    padd("md_pair_pitch", "(case_d - 2 * md_half_tail - 2 * md_pin_w - md_pair_gap) / (md_n_pairs - 1)", "in", "Pair pitch")
    padd("md_narrow_w", "md_pin_w - 2 * case_t * tan(md_angle)", "in", "Narrow face pin width")

    # ── Turned-knob + spherical-cove helpers ───────────────────────
    def turned_knob(comp, plane_x_expr, cx, cy_face, cz, proj, r, name, proj_expr):
        """Revolved-spline turned knob whose FLAT BASE rests ON the surface at
        cy_face; the knob protrudes -Y by `proj`. There is NO submerged tenon —
        the knob only contacts the surface (a separate dowel provides the
        joinery). The revolve AXIS length (= proj) and the base radius
        (= knob_base_r) are dimensioned parametrically; only the spline INTERIOR
        fit points stay draggable."""
        pl = sp.off_plane(comp, root.yZConstructionPlane, plane_x_expr, name + "_Pl")
        sk = comp.sketches.add(pl); sk.name = name + "_Sk"
        m = sk.modelToSketchSpace
        base_r = ev("knob_base_r")
        # Silhouette (picked up from the user's reshaped drawer knob, expressed
        # as fractions of proj/r so it scales to every knob): a straight collar
        # at the base radius, swelling to a full ball near the front (widest
        # ~0.94 r), then a domed tip on the axis. The flat base disc (axis ->
        # base rim) sits at cy_face.
        prof_pts = [
            P(cx, cy_face - proj * 0.159, cz + base_r),
            P(cx, cy_face - proj * 0.301, cz + r * 0.647),
            P(cx, cy_face - proj * 0.727, cz + r * 0.939),
            P(cx, cy_face - proj,         cz),
        ]
        coll = adsk.core.ObjectCollection.create()
        for mp in prof_pts:
            s = m(mp); coll.add(P(s.x, s.y, 0))
        spline = sk.sketchCurves.sketchFittedSplines.add(coll)
        axis_base = m(P(cx, cy_face, cz))            # on axis, at the surface
        base_rim  = m(P(cx, cy_face, cz + base_r))   # base rim, on the surface
        ss = spline.startSketchPoint.geometry        # flared head (widest)
        base_line = sk.sketchCurves.sketchLines.addByTwoPoints(
            P(axis_base.x, axis_base.y, 0), P(base_rim.x, base_rim.y, 0))
        sk.sketchCurves.sketchLines.addByTwoPoints(
            base_line.endSketchPoint, P(ss.x, ss.y, 0))
        se = spline.endSketchPoint.geometry          # domed tip on axis
        closing = sk.sketchCurves.sketchLines.addByTwoPoints(
            P(se.x, se.y, 0), base_line.startSketchPoint)
        # Parameterize the axis (length = proj) and the base radius.
        orient = sp.probe_orientations(sk, cx, cy_face, cz)
        d = sk.sketchDimensions
        try:
            d.addDistanceDimension(closing.startSketchPoint, closing.endSketchPoint,
                orient['y'], P(axis_base.x, axis_base.y + 1, 0)).parameter.expression = proj_expr
            d.addDistanceDimension(base_line.startSketchPoint, base_line.endSketchPoint,
                orient['z'], P(base_rim.x + 1, base_rim.y, 0)).parameter.expression = "knob_base_r"
        except Exception as e:
            print(f"  knob dim warn {name}: {e}")
        prof = sp.smallest_profile(sk)
        rin = comp.features.revolveFeatures.createInput(prof, closing, NEW)
        rin.setAngleExtent(False, VI("360 deg"))
        b = comp.features.revolveFeatures.add(rin).bodies.item(0)
        b.name = name
        return b

    def knob_dowel(comp, cx, cy_iface, cz, body_knob, body_board, name):
        """A round dowel centered on the knob axis at the contact interface
        (cy_iface), seated into BOTH the knob and the board — this is the joint
        that holds the (merely contacting) knob to the piece."""
        pl = sp.off_plane(comp, root.xZConstructionPlane, cy_iface, name + "_Pl")
        return dowel.single(comp, pl,
            center=(cx, cy_iface, cz),
            diameter="knob_dowel_d", depth="knob_dowel_d * 0.9",
            body_a=body_knob, body_b=body_board, name=name, ev=ev)

    def sphere_cove(comp, target, plane_x_expr, cx, cy_face, cz, cr, cdepth, name):
        """Cut a non-through spherical dish into `target`'s front (-Y) face.
        Sphere center sits OUTSIDE the face (smaller Y); deepest point = cdepth."""
        yc = cy_face + cdepth - cr   # center in front of the face
        pl = sp.off_plane(comp, root.yZConstructionPlane, plane_x_expr, name + "_Pl")
        sk = comp.sketches.add(pl); sk.name = name + "_Sk"
        m = sk.modelToSketchSpace
        p_lo = m(P(cx, yc - cr, cz)); p_hi = m(P(cx, yc + cr, cz)); p_md = m(P(cx, yc, cz + cr))
        dia = sk.sketchCurves.sketchLines.addByTwoPoints(
            P(p_lo.x, p_lo.y, 0), P(p_hi.x, p_hi.y, 0))
        sk.sketchCurves.sketchArcs.addByThreePoints(
            P(p_lo.x, p_lo.y, 0), P(p_md.x, p_md.y, 0), P(p_hi.x, p_hi.y, 0))
        prof = sp.smallest_profile(sk)
        rin = comp.features.revolveFeatures.createInput(prof, dia, NEW)
        rin.setAngleExtent(False, VI("360 deg"))
        sph = comp.features.revolveFeatures.add(rin).bodies.item(0); sph.name = name + "_Tool"
        sp.combine(target, sph, CUT, False, name + "_Cut")

    # move helper (still used for the drawer setback)
    def move_y(comp, bodies, expr):
        coll = adsk.core.ObjectCollection.create()
        for b in bodies:
            coll.add(b)
        mv = comp.features.moveFeatures.createInput2(coll)
        mv.defineAsTranslateXYZ(VI("0 in"), VI(expr), VI("0 in"), False)
        comp.features.moveFeatures.add(mv).name = comp.name + "_Move"

    def rect_far(comp, plane, xa, ya, xb, yb, name):
        """Rectangle spanning model [xa,xb] x [ya,yb] (xa/ya may be negative),
        dimensioned from the FAR (xb,yb — positive) corner so no origin dim is
        negative (a negative distance dim flips to positive in Fusion)."""
        sk = comp.sketches.add(plane); sk.name = name
        m = sk.modelToSketchSpace
        pa = m(P(ev(xa), ev(ya), 0)); pb = m(P(ev(xb), ev(yb), 0))
        rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(P(pa.x, pa.y, 0), P(pb.x, pb.y, 0))
        gc = sk.geometricConstraints
        gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2]); gc.addVertical(rect[1]); gc.addVertical(rect[3])
        ori = sp.probe_orientations(sk, (ev(xa) + ev(xb)) / 2, (ev(ya) + ev(yb)) / 2, 0)
        d = sk.sketchDimensions; far = rect[1].endSketchPoint
        d.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint, ori['x'], P(pb.x, pa.y - 1, 0)).parameter.expression = f"({xb}) - ({xa})"
        d.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint, ori['y'], P(pb.x + 1, pb.y, 0)).parameter.expression = f"({yb}) - ({ya})"
        d.addDistanceDimension(sk.originPoint, far, ori['x'], P(pb.x / 2, pb.y + 1, 0)).parameter.expression = xb
        d.addDistanceDimension(sk.originPoint, far, ori['y'], P(pb.x + 2, pb.y / 2, 0)).parameter.expression = yb
        return sk, sk.profiles.item(0)

    # ── Legs — built IN PLACE (frame proud of the case, NO post-build Move). The
    #    front legs/rail sit at y=-reveal; rect_far dimensions the far (+Y) corner
    #    so the negative front edge doesn't flip. The case stays at y=0..case_d,
    #    so the frame stands `reveal` proud front and back.
    legs_occ = sp.make_comp(root, "Legs"); legs_c = legs_occ.component
    _, prof = rect_far(legs_c, root.xYConstructionPlane,
                       "0 in", "0 in - reveal", "leg_sq", "leg_sq - reveal", "Leg_FL_Sk")
    leg_fl = sp.ext_new(legs_c, prof, "leg_h", "Leg_FL_Ext").bodies.item(0); leg_fl.name = "Leg_FL"

    # X-taper (inner +X face): X-Z sketch on a plane at y=-reveal, extrude +Y by
    # leg_sq to span the full (in-place) leg depth [-reveal, leg_sq-reveal].
    taperx_pl = sp.off_plane(legs_c, root.xZConstructionPlane, "0 in - reveal", "TaperX_Pl")
    taper_sk = legs_c.sketches.add(taperx_pl); taper_sk.name = "TaperX_Sk"
    lines = taper_sk.sketchCurves.sketchLines; m2s = taper_sk.modelToSketchSpace
    sa = m2s(P(ev("leg_foot"), 0, 0)); sb = m2s(P(ev("leg_sq"), 0, 0)); sc = m2s(P(ev("leg_sq"), 0, ev("taper_start_z")))
    l1 = lines.addByTwoPoints(P(sa.x,sa.y,0), P(sb.x,sb.y,0))
    l2 = lines.addByTwoPoints(l1.endSketchPoint, P(sc.x,sc.y,0))
    lines.addByTwoPoints(l2.endSketchPoint, l1.startSketchPoint)
    taper_sk.geometricConstraints.addHorizontal(l1); taper_sk.geometricConstraints.addVertical(l2)
    ox = sp.probe_orientations(taper_sk, ev("leg_sq/2"), -ev("reveal"), ev("taper_start_z/2"))
    d = taper_sk.sketchDimensions
    d.addDistanceDimension(l1.startSketchPoint, taper_sk.originPoint, ox['x'], P(.5,-1,0)).parameter.expression = "leg_foot"
    d.addDistanceDimension(l1.endSketchPoint, taper_sk.originPoint, ox['x'], P(1.5,-1,0)).parameter.expression = "leg_sq"
    d.addDistanceDimension(l2.endSketchPoint, taper_sk.originPoint, ox['z'], P(2,1,0)).parameter.expression = "taper_start_z"
    d.addDistanceDimension(l1.startSketchPoint, taper_sk.originPoint, ox['z'], P(.5,1,0)).parameter.expression = "0 in"
    sp.refs_to_construction(taper_sk)
    sp.ext_op(legs_c, sp.smallest_profile(taper_sk), "leg_sq", CUT, leg_fl, "TaperX_Cut")

    # Y-taper (inner +Y face): the +Y face is now at y=leg_sq-reveal, so the
    # profile Y coords (and their dims) shift by -reveal. Extrude +X by leg_sq.
    taper_sk_y = legs_c.sketches.add(root.yZConstructionPlane); taper_sk_y.name = "TaperY_Sk"
    ly = taper_sk_y.sketchCurves.sketchLines; m2y = taper_sk_y.modelToSketchSpace
    rv = ev("reveal")
    say = m2y(P(0, ev("leg_foot") - rv, 0)); sby = m2y(P(0, ev("leg_sq") - rv, 0)); scy = m2y(P(0, ev("leg_sq") - rv, ev("taper_start_z")))
    l1y = ly.addByTwoPoints(P(say.x,say.y,0), P(sby.x,sby.y,0))
    l2y = ly.addByTwoPoints(l1y.endSketchPoint, P(scy.x,scy.y,0))
    ly.addByTwoPoints(l2y.endSketchPoint, l1y.startSketchPoint)
    taper_sk_y.geometricConstraints.addVertical(l1y); taper_sk_y.geometricConstraints.addHorizontal(l2y)
    oy = sp.probe_orientations(taper_sk_y, 0, ev("leg_sq/2") - rv, ev("taper_start_z/2"))
    dy = taper_sk_y.sketchDimensions
    dy.addDistanceDimension(l1y.startSketchPoint, taper_sk_y.originPoint, oy['y'], P(.5,-1,0)).parameter.expression = "leg_foot - reveal"
    dy.addDistanceDimension(l1y.endSketchPoint, taper_sk_y.originPoint, oy['y'], P(1.5,-1,0)).parameter.expression = "leg_sq - reveal"
    dy.addDistanceDimension(l2y.endSketchPoint, taper_sk_y.originPoint, oy['z'], P(2,1,0)).parameter.expression = "taper_start_z"
    dy.addDistanceDimension(l1y.startSketchPoint, taper_sk_y.originPoint, oy['z'], P(.5,1,0)).parameter.expression = "0 in"
    sp.refs_to_construction(taper_sk_y)
    sp.ext_op(legs_c, sp.smallest_profile(taper_sk_y), "leg_sq", CUT, leg_fl, "TaperY_Cut")

    # ── Leg↔rail dominoes: build the 4 FL-corner loose tenons and MIRROR them to
    #    the other corners (12 more). Everything is mirrored while CLEAN — the
    #    dominoes before they're used as cut tools, and the leg with only its taper
    #    cuts (taper extrude-cuts don't ghost; a kept combine-tool DOES ghost if
    #    mirrored, which is why we mirror BEFORE cutting). Then cut each leg and
    #    rail with its dominoes. Vertical dominoes (long_axis z), centered pair
    #    (dm_pair_sp) per the grain rule (wide face ∥ show surface).
    zc = "leg_h - rail_w / 2"
    def fl_pair(base_pl, off_expr, iax, sax, sc_expr, tag):
        vs = []
        for k, sgn in ((0, "-"), (1, "+")):
            pl = sp.off_plane(legs_c, base_pl, off_expr, f"{tag}_{k}_Pl")
            c = {iax: off_expr, "z": zc, sax: f"({sc_expr}) {sgn} dm_pair_sp / 2"}
            vs.append(domino.single(legs_c, pl, (c["x"], c["y"], c["z"]), "z",
                                    "dm_w", "dm_t", "dm_d", cut=False, name=f"{tag}_{k}", ev=ev))
        return vs
    vF = fl_pair(root.yZConstructionPlane, "leg_sq",           "x", "y", "leg_sq / 2 - reveal", "DM_FL_F")
    vS = fl_pair(root.xZConstructionPlane, "leg_sq - reveal",  "y", "x", "leg_sq / 2",          "DM_FL_S")

    x_mid_pl = sp.off_plane(legs_c, root.yZConstructionPlane, "x_mid", "XMid")
    y_mid_pl = sp.off_plane(legs_c, root.xZConstructionPlane, "frame_d / 2 - reveal", "YMid")
    def mir_list(voids, plane, base):
        # Single-body mirrors — sp.mirror_body's .bodies.item(0) is reliable,
        # whereas sp.mirror_bodies (plural) does NOT preserve input order.
        out = []
        for j, v in enumerate(voids):
            mb = sp.mirror_body(legs_c, v, plane, f"{base}_{j}_Mir").bodies.item(0)
            mb.name = f"{base}_{j}"
            out.append(mb)
        return out
    # Mirror the 4 clean dominoes -> the other 12.
    vF_FR = mir_list(vF, x_mid_pl, "DM_FR_F")
    vS_FR = mir_list(vS, x_mid_pl, "DM_FR_S")
    vB_BL = mir_list(vF,    y_mid_pl, "DM_BL_B")
    vB_BR = mir_list(vF_FR, y_mid_pl, "DM_BR_B")
    vS_BL = mir_list(vS,    y_mid_pl, "DM_BL_S")
    vS_BR = mir_list(vS_FR, y_mid_pl, "DM_BR_S")

    # Mirror the LEG (only taper history -> clean) to the other corners.
    leg_fr = sp.mirror_body(legs_c, leg_fl, x_mid_pl, "Leg_FR_Mir").bodies.item(0); leg_fr.name = "Leg_FR"
    leg_bl = sp.mirror_body(legs_c, leg_fl, y_mid_pl, "Leg_BL_Mir").bodies.item(0); leg_bl.name = "Leg_BL"
    leg_br = sp.mirror_body(legs_c, leg_fr, y_mid_pl, "Leg_BR_Mir").bodies.item(0); leg_br.name = "Leg_BR"

    # Now cut each leg's mortises with its corner dominoes (no combined body is
    # ever mirrored, so no ghost bodies).
    sp.combine(leg_fl, vF + vS,       CUT, True, "DM_FL_LegCut")
    sp.combine(leg_fr, vF_FR + vS_FR, CUT, True, "DM_FR_LegCut")
    sp.combine(leg_bl, vB_BL + vS_BL, CUT, True, "DM_BL_LegCut")
    sp.combine(leg_br, vB_BR + vS_BR, CUT, True, "DM_BR_LegCut")
    rail_voids = {"F": vF + vF_FR, "B": vB_BL + vB_BR, "SL": vS + vS_BL, "SR": vS_FR + vS_BR}
    print(">>> Legs: 4 dominoes built + mirrored to 16; 4 legs mirrored; mortises cut")

    # ── Rails — built IN PLACE; front rail at y=-reveal (rect_far), side rails at
    #    positive Y (sketch_rect_model). Then cut by their dominoes. No Move.
    rails_occ = sp.make_comp(root, "Rails"); rails_c = rails_occ.component
    rail_z_pl = sp.off_plane(rails_c, root.xYConstructionPlane, "leg_h - rail_w", "Rail_Z_Pl")
    _, fr_prof = rect_far(rails_c, rail_z_pl,
                          "leg_sq", "0 in - reveal", "case_w - leg_sq", "leg_sq - reveal", "FrontRail_Sk")
    front_rail = sp.ext_new(rails_c, fr_prof, "rail_w", "FrontRail_Ext").bodies.item(0); front_rail.name = "Rail_F"
    y_mid_r = sp.off_plane(rails_c, root.xZConstructionPlane, "frame_d / 2 - reveal", "YMid_R")
    rail_b = sp.mirror_body(rails_c, front_rail, y_mid_r, "Rail_B_Mir").bodies.item(0); rail_b.name = "Rail_B"
    sr_sk, sr_prof = sp.sketch_rect_model(rails_c, rail_z_pl,
        ("0 in", "leg_sq - reveal", "leg_h - rail_w"), {"x": "leg_sq", "y": "frame_d - 2 * leg_sq"}, "SideRail_L_Sk", ev=ev)
    side_l = sp.ext_new(rails_c, sr_prof, "rail_w", "SideRail_L_Ext").bodies.item(0); side_l.name = "Rail_SL"
    x_mid_r = sp.off_plane(rails_c, root.yZConstructionPlane, "x_mid", "XMid_R")
    side_r = sp.mirror_body(rails_c, side_l, x_mid_r, "Rail_SR_Mir").bodies.item(0); side_r.name = "Rail_SR"

    sp.combine(front_rail, rail_voids["F"],  CUT, True, "DM_RailF_Cut")
    sp.combine(rail_b,     rail_voids["B"],  CUT, True, "DM_RailB_Cut")
    sp.combine(side_l,     rail_voids["SL"], CUT, True, "DM_RailSL_Cut")
    sp.combine(side_r,     rail_voids["SR"], CUT, True, "DM_RailSR_Cut")
    print(">>> Rails: 4 built in place + dominoes cut (no Move — frame proud in place)")

    # ── Case ──
    case_occ = sp.make_comp(root, "Case"); case_c = case_occ.component
    case_z_pl = sp.off_plane(case_c, root.xYConstructionPlane, "leg_h", "Case_Z_Pl")
    bot_sk, bot_prof = sp.sketch_rect_model(case_c, case_z_pl,
        ("0 in", "0 in", "leg_h"), {"x": "case_w", "y": "case_d"}, "CaseBot_Sk", ev=ev)
    case_bot = sp.ext_new(case_c, bot_prof, "case_t", "CaseBot_Ext").bodies.item(0); case_bot.name = "Case_Bot"
    case_top_pl = sp.off_plane(case_c, root.xYConstructionPlane, "leg_h + case_h - case_t", "CaseTop_Z_Pl")
    top_sk, top_prof = sp.sketch_rect_model(case_c, case_top_pl,
        ("0 in", "0 in", "leg_h + case_h - case_t"), {"x": "case_w", "y": "case_d"}, "CaseTop_Sk", ev=ev)
    case_top = sp.ext_new(case_c, top_prof, "case_t", "CaseTop_Ext").bodies.item(0); case_top.name = "Case_Top"
    sL_sk, sL_prof = sp.sketch_rect_model(case_c, case_z_pl,
        ("0 in", "0 in", "leg_h"), {"x": "case_t", "y": "case_d"}, "CaseSideL_Sk", ev=ev)
    case_sl = sp.ext_new(case_c, sL_prof, "case_h", "CaseSideL_Ext").bodies.item(0); case_sl.name = "Case_SideL"
    x_mid_case = sp.off_plane(case_c, root.yZConstructionPlane, "x_mid", "XMid_Case")
    case_sr = sp.mirror_body(case_c, case_sl, x_mid_case, "CaseSideR_Mir").bodies.item(0); case_sr.name = "Case_SideR"

    cw = ev("case_w"); ct = ev("case_t"); ch = ev("case_h"); lh = ev("leg_h")
    pw = ev("md_pin_w"); ht = ev("md_half_tail"); pg = ev("md_pair_gap"); pp = ev("md_pair_pitch")
    npair = int(ev("md_n_pairs")); md_delta = ct * math.tan(ev("md_angle"))
    z_top_lo = lh + ch - ct; z_top_hi = lh + ch; z_bot_lo = lh; z_bot_hi = lh + ct

    def miter_cut(board, pts, name):
        sk = case_c.sketches.add(root.xZConstructionPlane); sk.name = name + "_Sk"
        m = sk.modelToSketchSpace; s = [m(P(x, 0, z)) for (x, z) in pts]
        L = sk.sketchCurves.sketchLines
        a = L.addByTwoPoints(P(s[0].x, s[0].y, 0), P(s[1].x, s[1].y, 0))
        b = L.addByTwoPoints(a.endSketchPoint, P(s[2].x, s[2].y, 0))
        L.addByTwoPoints(b.endSketchPoint, a.startSketchPoint)
        sp.ext_op(case_c, sk.profiles.item(0), "case_d", CUT, board, name)

    miter_cut(case_top, [(0, z_top_hi),  (ct, z_top_lo),      (0, z_top_lo)],   "MiterTL")
    miter_cut(case_top, [(cw, z_top_hi), (cw - ct, z_top_lo), (cw, z_top_lo)],  "MiterTR")
    miter_cut(case_bot, [(0, z_bot_lo),  (ct, z_bot_hi),      (0, z_bot_hi)],   "MiterBL")
    miter_cut(case_bot, [(cw, z_bot_lo), (cw - ct, z_bot_hi), (cw, z_bot_hi)],  "MiterBR")

    pin_pl_L = sp.off_plane(case_c, root.yZConstructionPlane, "case_t", "MD_PinL_Pl")
    pin_pl_R = sp.off_plane(case_c, root.yZConstructionPlane, "case_w - case_t", "MD_PinR_Pl")

    def dovetail_corner(pin_board, plane, x_pl, z_wide, z_narrow, z_narrow_expr, flip, tag):
        # First pair only (2 pins), JOIN each, then pattern along +Y for all pairs.
        for j in range(2):
            y0 = ht + j * (pw + pg)
            sj = "md_half_tail" + (" + md_pin_w + md_pair_gap" if j == 1 else "") + " + case_t * tan(md_angle)"
            prof = trapezoid_sketch(case_c, plane,
                P(x_pl, y0, z_wide), P(x_pl, y0 + pw, z_wide),
                P(x_pl, y0 + pw - md_delta, z_narrow), P(x_pl, y0 + md_delta, z_narrow),
                thick_expr="case_t", short_joint_expr=sj,
                short_base_expr=z_narrow_expr, prefix="md", name=f"{tag}_{j}",
                narrow_w_expr="md_narrow_w")
            jf = sp.ext_op(case_c, prof, "case_t", JOIN, pin_board, f"{tag}_{j}_J", flip=flip)
            sp.feat_pattern(case_c, jf, case_c.yConstructionAxis,
                            "md_n_pairs", "md_pair_pitch", f"{tag}_{j}_Pat")

    dovetail_corner(case_top, pin_pl_L, ct,      z_top_lo, z_top_hi, "leg_h + case_h", True,  "MDTL")
    dovetail_corner(case_top, pin_pl_R, cw - ct, z_top_lo, z_top_hi, "leg_h + case_h", False, "MDTR")
    dovetail_corner(case_bot, pin_pl_L, ct,      z_bot_hi, z_bot_lo, "leg_h", True,  "MDBL")
    dovetail_corner(case_bot, pin_pl_R, cw - ct, z_bot_hi, z_bot_lo, "leg_h", False, "MDBR")

    sp.combine(case_sl, case_top, CUT, True, "MD_CutSL_Top")
    sp.combine(case_sl, case_bot, CUT, True, "MD_CutSL_Bot")
    sp.combine(case_sr, case_top, CUT, True, "MD_CutSR_Top")
    sp.combine(case_sr, case_bot, CUT, True, "MD_CutSR_Bot")
    print(">>> Case: mitered dovetails (6 pairs x 4 corners)")

    # Partitions (front flush with door inner face)
    part_z_pl = sp.off_plane(case_c, root.xYConstructionPlane, "leg_h + case_t", "Part_Z_Pl")
    pL_sk, pL_prof = sp.sketch_rect_model(case_c, part_z_pl,
        ("case_t + door_comp_w", "part_front_inset", "leg_h + case_t"),
        {"x": "part_t", "y": "case_d - part_front_inset - part_back_inset"}, "PartL_Sk", ev=ev)
    part_l = sp.ext_new(case_c, pL_prof, "part_h", "PartL_Ext").bodies.item(0); part_l.name = "Partition_L"
    sp.mirror_body(case_c, part_l, x_mid_case, "PartR_Mir").bodies.item(0).name = "Partition_R"

    bp_y = "case_d - back_t"
    bpL = sp.ext_new(case_c, sp.sketch_rect_model(case_c, part_z_pl,
        ("case_t", bp_y, "leg_h + case_t"), {"x": "door_comp_w", "y": "back_t"}, "BPL_Sk", ev=ev)[1],
        "part_h", "BPL_Ext").bodies.item(0); bpL.name = "BackPanel_L"
    bpC = sp.ext_new(case_c, sp.sketch_rect_model(case_c, part_z_pl,
        ("case_t + door_comp_w + part_t", bp_y, "leg_h + case_t"), {"x": "drawer_comp_w", "y": "back_t"}, "BPC_Sk", ev=ev)[1],
        "part_h", "BPC_Ext").bodies.item(0); bpC.name = "BackPanel_C"
    sp.mirror_body(case_c, bpL, x_mid_case, "BPR_Mir").bodies.item(0).name = "BackPanel_R"
    print(">>> Partitions + back panels")

    # ── Doors — frame & panel + turned knob on outer stile ──
    doors_occ = sp.make_comp(root, "Doors"); doors_c = doors_occ.component
    dz_pl   = sp.off_plane(doors_c, root.xYConstructionPlane, "door_z0", "Door_Z_Pl")
    drail_pl = sp.off_plane(doors_c, root.xYConstructionPlane, "door_z0 + door_rail_h", "Door_Rail_Pl")
    dtop_pl = sp.off_plane(doors_c, root.xYConstructionPlane, "door_z0 + door_h - door_rail_h", "Door_Top_Pl")

    # Left door leaf: left stile, right stile, bottom rail, top rail, panel
    lst = sp.ext_new(doors_c, sp.sketch_rect_model(doors_c, dz_pl,
        ("case_t + door_gap", "door_gap", "door_z0"), {"x": "stile_w", "y": "door_t"}, "DLStileL_Sk", ev=ev)[1],
        "door_h", "DLStileL_Ext").bodies.item(0); lst.name = "DoorL_StileL"
    rst = sp.ext_new(doors_c, sp.sketch_rect_model(doors_c, dz_pl,
        ("case_t + door_comp_w - door_gap - stile_w", "door_gap", "door_z0"), {"x": "stile_w", "y": "door_t"}, "DLStileR_Sk", ev=ev)[1],
        "door_h", "DLStileR_Ext").bodies.item(0); rst.name = "DoorL_StileR"
    brl = sp.ext_new(doors_c, sp.sketch_rect_model(doors_c, dz_pl,
        ("case_t + door_gap + stile_w", "door_gap", "door_z0"), {"x": "door_w - 2 * stile_w", "y": "door_t"}, "DLRailB_Sk", ev=ev)[1],
        "door_rail_h", "DLRailB_Ext").bodies.item(0); brl.name = "DoorL_RailB"
    trl = sp.ext_new(doors_c, sp.sketch_rect_model(doors_c, dtop_pl,
        ("case_t + door_gap + stile_w", "door_gap", "door_z0 + door_h - door_rail_h"), {"x": "door_w - 2 * stile_w", "y": "door_t"}, "DLRailT_Sk", ev=ev)[1],
        "door_rail_h", "DLRailT_Ext").bodies.item(0); trl.name = "DoorL_RailT"
    pnl = sp.ext_new(doors_c, sp.sketch_rect_model(doors_c, drail_pl,
        ("case_t + door_gap + stile_w", "door_gap + (door_t - panel_t) / 2", "door_z0 + door_rail_h"),
        {"x": "door_w - 2 * stile_w", "y": "panel_t"}, "DLPanel_Sk", ev=ev)[1],
        "door_h - 2 * door_rail_h", "DLPanel_Ext").bodies.item(0); pnl.name = "DoorL_Panel"

    # Mirror left leaf -> right leaf
    x_mid_door = sp.off_plane(doors_c, root.yZConstructionPlane, "x_mid", "XMid_Door")
    panel_r = None; stile_r_outer = None
    for b, nm in [(lst, "DoorR_StileR"), (rst, "DoorR_StileL"), (brl, "DoorR_RailB"),
                  (trl, "DoorR_RailT"), (pnl, "DoorR_Panel")]:
        mb = sp.mirror_body(doors_c, b, x_mid_door, nm + "_Mir").bodies.item(0); mb.name = nm
        if nm == "DoorR_Panel":
            panel_r = mb
        if nm == "DoorR_StileR":
            stile_r_outer = mb

    # Turned knobs on the OUTER stiles — the flat base rests ON the stile front
    # face (door_gap); a dowel through the contact seats into both the knob and
    # the stile so the knob is held without being submerged.
    dz_cz = ev("door_z0 + door_h / 2"); knob_r = ev("knob_dia") / 2
    kdl = turned_knob(doors_c, "case_t + door_gap + stile_w / 2",
                ev("case_t + door_gap + stile_w / 2"), ev("door_gap"), dz_cz, ev("knob_proj"), knob_r, "Knob_DoorL", "knob_proj")
    kdr = turned_knob(doors_c, "case_w - case_t - door_gap - stile_w / 2",
                ev("case_w - case_t - door_gap - stile_w / 2"), ev("door_gap"), dz_cz, ev("knob_proj"), knob_r, "Knob_DoorR", "knob_proj")
    knob_dowel(doors_c, "case_t + door_gap + stile_w / 2", "door_gap",
               "door_z0 + door_h / 2", kdl, lst, "Knob_DoorL_Dwl")
    knob_dowel(doors_c, "case_w - case_t - door_gap - stile_w / 2", "door_gap",
               "door_z0 + door_h / 2", kdr, stile_r_outer, "Knob_DoorR_Dwl")
    print(">>> Doors: frame-and-panel x2 + 2 knobs (contact + dowel)")

    # ── Sliding-door track (FWW #277): single groove top & bottom + door tongues.
    # Grooves run the interior width (stopped at the dovetail baselines, x in
    # [case_t, case_w-case_t]); the two coplanar doors slide one at a time in
    # front of the center drawers. Top groove is deeper (lift door in, drop it).
    def case_groove(board, z_expr, d_expr, flip, name):
        pl = sp.off_plane(case_c, root.xYConstructionPlane, z_expr, name + "_Pl")
        _, prof = sp.sketch_rect_model(case_c, pl,
            ("case_t", "door_tongue_y0", z_expr),
            {"x": "case_w - 2 * case_t", "y": "door_tongue_w"}, name + "_Sk", ev=ev)
        sp.ext_op(case_c, prof, d_expr, CUT, board, name, flip=flip)
    case_groove(case_top, "leg_h + case_h - case_t", "groove_top_d", False, "DoorTrackTop")
    case_groove(case_bot, "leg_h + case_t",          "groove_bot_d", True,  "DoorTrackBot")

    def dbody(nm):
        for i in range(doors_c.bRepBodies.count):
            if doors_c.bRepBodies.item(i).name == nm:
                return doors_c.bRepBodies.item(i)
        return None
    def door_tongue(rail_nm, x0_expr, z_expr, h_expr, flip, name):
        pl = sp.off_plane(doors_c, root.xYConstructionPlane, z_expr, name + "_Pl")
        _, prof = sp.sketch_rect_model(doors_c, pl,
            (x0_expr, "door_tongue_y0", z_expr),
            {"x": "door_w", "y": "door_tongue_w"}, name + "_Sk", ev=ev)
        sp.ext_op(doors_c, prof, h_expr, JOIN, dbody(rail_nm), name, flip=flip)
    door_tongue("DoorL_RailT", "case_t + door_gap", "door_z0 + door_h",
                "door_tongue_top_h", False, "DoorL_TongueT")
    door_tongue("DoorL_RailB", "case_t + door_gap", "door_z0",
                "door_tongue_bot_h", True, "DoorL_TongueB")
    door_tongue("DoorR_RailT", "case_w - case_t - door_comp_w + door_gap",
                "door_z0 + door_h", "door_tongue_top_h", False, "DoorR_TongueT")
    door_tongue("DoorR_RailB", "case_w - case_t - door_comp_w + door_gap",
                "door_z0", "door_tongue_bot_h", True, "DoorR_TongueB")
    print(">>> Sliding-door track: top+bottom case grooves + 4 door tongues")

    # ── Drawers — dovetailed boxes, cove + knob, patterned x3 ──
    drawers_occ = sp.make_comp(root, "Drawers"); drawers_c = drawers_occ.component
    padd("drawer_pitch", "drawer_h + drawer_gap", "in", "Drawer vertical spacing")
    dovetailed_drawer.define_params(params, prefix="dd",
        drawer_w="drawer_comp_w - 2 * drawer_gap",
        drawer_d="case_d - door_inner_y - back_t - 0.25 in",
        drawer_h="drawer_h - drawer_gap",
        front_thick="0.625 in", side_thick="0.4375 in", bottom_thick="0.25 in",
        bg_depth="0.1875 in", bg_up="0.1875 in",
        dt_angle="8 deg", dt_tail_w="0.625 in",
        front_tail_count="3", back_tail_count="3",
        x_offset="case_t + door_comp_w + part_t + drawer_gap",
        y_offset="0 in",
        z_offset="leg_h + case_t + drawer_gap")
    # Cove params (need dd_ft from the template)
    padd("cove_dia",   "1.5 in",  "in", "Drawer cove recess diameter")
    padd("cove_depth", "dd_ft / 2", "in", "Cove depth (half front thickness)")
    padd("cove_r", "(cove_dia * cove_dia / 4 + cove_depth * cove_depth) / (2 * cove_depth)", "in", "Cove sphere radius")
    # Knob flat base sits TANGENT to the curved cove dish (a ring contact at
    # radius knob_base_r) so it doesn't bury into the curved dish wall. The
    # dowel still seats at the dish bottom into solid material.
    padd("knob_drw_base_y", "door_inner_y + cove_depth - (cove_r - sqrt(cove_r * cove_r - knob_base_r * knob_base_r))",
         "in", "Drawer knob base Y (ring-tangent to the cove dish)")
    dd = dovetailed_drawer.build(drawers_c, prefix="dd", ev=ev)
    move_y(drawers_c, dd["all_bodies"], "door_inner_y")  # front flush w/ door inner

    # Spherical cove + turned knob on the base drawer front (replicated by pattern).
    # The knob's flat base rests on the BOTTOM of the cove dish (door_inner_y +
    # cove_depth); a dowel through that contact seats into both the knob and the
    # drawer front so the knob is held without being submerged.
    cx = ev("x_mid")
    cz = ev("leg_h + case_t + drawer_gap + dd_fh / 2")
    yface = ev("door_inner_y")
    sphere_cove(drawers_c, dd["front"], "x_mid", cx, yface, cz, ev("cove_r"), ev("cove_depth"), "DrwCove")
    # Knob base ring-tangent to the dish; dowel interface at the dish bottom so
    # it seats into solid material (the short gap under the knob center is hidden).
    knob = turned_knob(drawers_c, "x_mid", cx, ev("knob_drw_base_y"), cz,
                       ev("knob_drw_base_y - door_inner_y + knob_proj"),
                       ev("knob_dia") / 2, "Knob_Drw", "knob_drw_base_y - door_inner_y + knob_proj")
    drw_dwl = knob_dowel(drawers_c, "x_mid", "door_inner_y + cove_depth",
                         "leg_h + case_t + drawer_gap + dd_fh / 2", knob, dd["front"], "Knob_Drw_Dwl")

    dovetailed_drawer.pattern(drawers_c, dd["all_bodies"] + [knob, drw_dwl], "n_drawers", "drawer_pitch", ev=ev)
    print(f">>> Drawers: {drawers_c.bRepBodies.count} bodies (dovetailed box + cove + knob, x3)")

    # ── Summary + epilogue ──
    all_comps = [("Legs", legs_c), ("Rails", rails_c), ("Case", case_c), ("Doors", doors_c), ("Drawers", drawers_c)]
    total = 0
    for cn, c in all_comps:
        n = c.bRepBodies.count; total += n
        print(f"{cn}: {n} bodies")
    print(f"Total: {total} bodies")
    for _, c in all_comps:
        for s in c.sketches: s.isVisible = False
        for cp in c.constructionPlanes: cp.isLightBulbOn = False

    # ── Appearances ──
    # Purge leftover custom appearances from prior rebuilds first — otherwise the
    # white-oak base apply substring-matches e.g. "Fumed Oak" (contains "oak")
    # and fumes the whole piece. (force_clean wipes geometry, not appearances.)
    for _nm in ("Fumed Oak", "Fumed Frame", "Walnut Light"):
        _a = design.appearances.itemByName(_nm)
        if _a:
            try: _a.deleteMe()
            except Exception: pass
    sp.apply_appearance("white oak")
    # Base frame: a custom fumed-oak tone on legs + rails. The real Gochnour
    # base is white oak FUMED WITH AMMONIA — a warm medium chocolate-brown,
    # distinct from the natural-oak case. We reproduce that by copying the
    # library Oak and enabling its texture TINT, which colorizes the oak grain
    # to the fumed tone (keeps the grain). Case/doors/drawers stay natural oak.
    FUMED_TINT = (120, 85, 55)    # warm fumed-oak brown; tune to taste
    FUMED_GAIN = 0.4              # <1 darkens the oak (the lever that actually darkens it)
    frame_names = []
    for c in [legs_c, rails_c]:
        frame_names += [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]

    def _find_lib_app(term):
        libs = app.materialLibraries; found = None
        for li in range(libs.count):
            lib = libs.item(li)
            for ai in range(lib.appearances.count):
                a = lib.appearances.item(ai)
                if term.lower() == a.name.lower() and not a.name.startswith("3D "):
                    if "appearance" in lib.name.lower():
                        return a
                    if found is None:
                        found = a
        return found

    fumed = design.appearances.itemByName("Fumed Oak")
    if not fumed:
        fumed = design.appearances.addByCopy(_find_lib_app("Oak"), "Fumed Oak")
    try:
        _cp = adsk.core.ColorProperty.cast(fumed.appearanceProperties.itemById("opaque_albedo"))
        if _cp and _cp.hasConnectedTexture:
            _tp = _cp.connectedTexture.properties
            _tp.itemById("common_Tint_toggle").value = True
            _tp.itemById("common_Tint_color").value = adsk.core.Color.create(*FUMED_TINT, 0)
            _tp.itemById("unifiedbitmap_RGBAmount").value = FUMED_GAIN   # darken
    except Exception as e:
        print(f"  fumed-oak tint warn: {e}")

    _fset = set(frame_names)
    def _assign_frame(comp):
        for i in range(comp.bRepBodies.count):
            b = comp.bRepBodies.item(i)
            if b.name in _fset:
                b.appearance = fumed
        for i in range(comp.occurrences.count):
            _assign_frame(comp.occurrences.item(i).component)
    _assign_frame(root)
    print(f">>> Fumed oak (tint {FUMED_TINT}) on {len(frame_names)} frame bodies (legs + rails)")
    # Seamless spalted maple on the door panels (real-size veneer, no tiling).
    try:
        from helpers.veneer import apply_veneer_realsize
        pL = pnl; pR = panel_r
        apply_veneer_realsize(
            bodies=[pL, pR],
            image_path="/Users/frankzha/projects/shopprentice/textures/wood/spalted_maple_landscape.jpg",
            real_width_inches=14.0, real_height_inches=11.0,
            origin_body=pL, appearance_name="SP_spalted_door", fix_bottom_face=False)
        print(">>> Spalted maple veneer on door panels")
    except Exception as e:
        print(f"veneer failed: {e}")
        sp.apply_appearance("spalted maple", bodies=["DoorL_Panel", "DoorR_Panel"])
    # Rosewood on all knobs.
    knob_names = []
    for c in [doors_c, drawers_c]:
        for i in range(c.bRepBodies.count):
            nm = c.bRepBodies.item(i).name
            if "Knob" in nm:
                knob_names.append(nm)
    if knob_names:
        sp.apply_appearance("brazilian rosewood", bodies=knob_names)
        print(f">>> Rosewood on {len(knob_names)} knobs")

    cam = app.activeViewport.camera; cam.isFitView = True; app.activeViewport.camera = cam
    print(">>> GOCHNOUR SIDEBOARD BUILD COMPLETE")
