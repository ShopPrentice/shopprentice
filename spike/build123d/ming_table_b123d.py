"""Classic Ming side table (平头案) — visible form, in build123d.

Port of the form of examples/ming-table/ming_table.py (1450 lines of Fusion).
28"L x 13.75"D x 30.875"H, round 1-3/8" legs splayed 1.5 deg, mitered
frame-and-panel top, an apron band with carved spandrel brackets flanking
each leg, and a frame-and-panel shelf coped to the round legs.

SCOPE: this reproduces everything you can SEE. The Ming table's signature is
that almost every joint is *concealed* (hidden full-blind dovetails, blind
mitered tenons inside the round legs) -- by design they don't show. The
1450-line Fusion script is mostly machinery to make those hidden joints while
fighting the sketch constraint solver (anchor_poly, pin_free, _poly_cut,
projected-leg-silhouette addParallel, the deps gate). Here, parts are seated
against the legs with booleans so the assembly is interference-free and
connected; the dovetail/tenon-carving technique itself is shown in full on
the midou. The leg splay plane for the apron is taken vertical (the real 1.5
deg apron tilt is omitted -- invisible at this scale).
"""
import math

from build123d import Solid, Face, Wire, Vector, Plane, Location, fillet, chamfer
from b123d_common import Model, summarize, run_cli

IN = 2.54

# user parameters (inches / deg) -- the key rows of the Fusion table
PARAMS = {
    "table_l": 28.0, "table_d": 13.75, "table_h": 30.875, "splay_deg": 1.5,
    "tf_t": 1.0625, "tf_w": 2.0, "panel_t": 0.3125,
    "leg_dia": 1.375, "leg_setback_x": 5.375, "leg_setback_y": 1.125,
    "apron_t": 0.375, "apron_w": 1.125, "spandrel_depth": 3.5625,
    "ap_end_inset": 0.875, "sp_edge_gap": 1.0,
    "shelf_z": 20.0, "sf_t": 0.875, "sp_panel_t": 0.3125,
}


def inch(x):
    return x * IN


def V(t):
    return Vector(t[0], t[1], t[2])


def poly_prism(corners_2d, fixed_axis, fixed_val, extrude_vec, fillets=None):
    """Polygon given as (a,b) pairs in a plane; `fixed_axis` ('x'|'y'|'z')
    held at fixed_val supplies the third coord. Extruded along extrude_vec.

    fillets: optional [(corner_index, radius), ...] — rounds those profile
    vertices BEFORE extruding (2D wire fillet). Works on both convex corners
    (round-over) and reflex corners (cove); this is how the Fusion script's
    sketch addFillet coves are reproduced. Profile-level filleting is far more
    robust than filleting the extruded solid's edges afterwards."""
    pts = []
    for a, b in corners_2d:
        if fixed_axis == "y":
            pts.append((a, fixed_val, b))        # (x, y=fix, z)
        elif fixed_axis == "x":
            pts.append((fixed_val, a, b))        # (x=fix, y, z)
        else:
            pts.append((a, b, fixed_val))        # (x, y, z=fix)
    face = Face(Wire.make_polygon([V(p) for p in pts]))
    if fillets:
        by_r = {}
        for idx, r in fillets:
            by_r.setdefault(r, []).append(pts[idx])
        for r, locs in by_r.items():
            vs = [v for v in face.vertices()
                  if any(abs(v.X - p[0]) < 1e-6 and abs(v.Y - p[1]) < 1e-6
                         and abs(v.Z - p[2]) < 1e-6 for p in locs)]
            assert len(vs) == len(locs), \
                f"fillet vertex pick: wanted {len(locs)} got {len(vs)}"
            face = fillet(vs, r).faces()[0]
    return Solid.extrude(face, V(extrude_vec))


def edges_at(solid, x=None, y=None, z=None, tol=0.05):
    """Edges whose bounding box is pinned to the given coordinate(s) — e.g.
    z=top and y=outer selects the top outer edge run (possibly split into
    several segments by boolean cuts)."""
    out = []
    for e in solid.edges():
        bb = e.bounding_box()
        ok = True
        for val, lo, hi in ((x, bb.min.X, bb.max.X), (y, bb.min.Y, bb.max.Y),
                            (z, bb.min.Z, bb.max.Z)):
            if val is not None and not (abs(lo - val) < tol and abs(hi - val) < tol):
                ok = False
        if ok:
            out.append(e)
    return out


def one_solid(shape):
    """fillet()/chamfer() return a Part (compound); unwrap the single solid."""
    sols = shape.solids()
    assert len(sols) == 1, f"expected 1 solid, got {len(sols)}"
    return sols[0]


def box(x0, x1, y0, y1, z0, z1):
    return Solid.make_box(x1 - x0, y1 - y0, z1 - z0).moved(Location((x0, y0, z0)))


def fuse(solids):
    out = solids[0]
    for s in solids[1:]:
        out = out + s
    return out


def build(overrides=None):
    p = {**PARAMS, **(overrides or {})}
    # ---- parameters (converted to cm) ----
    table_l, table_d, table_h = inch(p["table_l"]), inch(p["table_d"]), inch(p["table_h"])
    splay = math.radians(p["splay_deg"])
    tf_t, tf_w = inch(p["tf_t"]), inch(p["tf_w"])
    tf_bot = table_h - tf_t
    panel_t = inch(p["panel_t"])
    panel_under = table_h - panel_t

    leg_r = inch(p["leg_dia"]) / 2
    ltx = table_l / 2 - inch(p["leg_setback_x"])
    lty = table_d / 2 - inch(p["leg_setback_y"])
    leg_embed = inch(0.5)
    leg_tip_z = tf_bot + leg_embed
    foot_off = leg_tip_z * math.tan(splay)

    apron_t, apron_w = inch(p["apron_t"]), inch(p["apron_w"])
    spandrel_depth = inch(p["spandrel_depth"])
    ap_end_inset = inch(p["ap_end_inset"])
    la_half = table_l / 2 - ap_end_inset
    sp_edge_gap = inch(p["sp_edge_gap"])

    shelf_z = inch(p["shelf_z"])
    sf_t = inch(p["sf_t"])
    sp_panel_t = inch(p["sp_panel_t"])

    LEGC, FRAME, PANEL, APRON, SHELF = (
        "#7a4a28", "#b07a45", "#9c6b3f", "#a06a3c", "#8a5a30")
    m = Model("Ming table (平头案)", params=p, units="in")

    # =====================================================================
    # LEGS -- a circle swept along the splayed centerline (foot on floor ->
    # top under the frame). The centerline carries the compound splay; no
    # extrude-then-rotate.
    # =====================================================================
    def leg(sx, sy, name):
        top = (sx * ltx, sy * lty, leg_tip_z)
        foot = (sx * ltx + sx * foot_off, sy * lty + sy * foot_off, 0.0)
        axis = (top[0] - foot[0], top[1] - foot[1], top[2] - foot[2])
        length = math.sqrt(sum(c * c for c in axis))
        zdir = Vector(*[c / length for c in axis])
        pl = Plane(origin=Vector(*foot), z_dir=zdir)
        return Solid.make_cylinder(leg_r, length, pl)

    legs = {
        "Leg_FL": leg(-1, -1, "Leg_FL"), "Leg_FR": leg(1, -1, "Leg_FR"),
        "Leg_BL": leg(-1, 1, "Leg_BL"), "Leg_BR": leg(1, 1, "Leg_BR"),
    }
    legunion = fuse(list(legs.values()))

    # =====================================================================
    # TOP -- 格角榫 mitered mortise-and-tenon frame + panel with tongue.
    # Faithful port of the Fusion shape_rail_end(): each rail is a FULL box
    # overlapping the corner; at each end the TOP and BOTTOM thirds lose a
    # 45-deg miter triangle and the MIDDLE third loses the tenon-waste
    # pentagon -- leaving a shouldered, mitered, CONCEALED tenon. The stiles
    # are then CUT by the rails, inheriting the mating miter + mortise.
    # Template proportions: depth 1.5/3.5, inner shoulder 1.2/3.5, outer
    # shoulder 0.6/3.5 of the member width.
    # =====================================================================
    l2, d2 = table_l / 2, table_d / 2
    tn_d, tn_st, tn_sb = tf_w * 1.5 / 3.5, tf_w * 1.2 / 3.5, tf_w * 0.6 / 3.5
    t3 = tf_t / 3
    OYf, IYf = -d2, -d2 + tf_w
    tri = [(l2, OYf), (l2, IYf), (l2 - tf_w, IYf)]
    pent = [(l2, OYf + tn_sb), (l2, IYf - tn_st), (l2 - tn_d, IYf - tn_st),
            (l2 - tn_d, OYf + tn_d), (l2 - tn_sb, OYf + tn_sb)]
    end_cut_r = fuse([
        poly_prism(tri, "z", tf_bot + 2 * t3, (0, 0, t3)),   # top miter
        poly_prism(tri, "z", tf_bot, (0, 0, t3)),            # bottom miter
        poly_prism(pent, "z", tf_bot + t3, (0, 0, t3)),      # tenon waste
    ])
    end_cuts = end_cut_r + end_cut_r.mirror(Plane.YZ)
    rail_f = box(-l2, l2, OYf, IYf, tf_bot, tf_bot + tf_t) - end_cuts
    rail_b = rail_f.mirror(Plane.XZ)
    stile_l = (box(-l2, -l2 + tf_w, -d2, d2, tf_bot, tf_bot + tf_t)
               - rail_f - rail_b)        # inherits mating miter + mortise
    stile_r = stile_l.mirror(Plane.YZ)
    # panel: flush field + a tongue slab lapping tongue_ov into the frame;
    # subtracting the panel from the frame members cuts their groove.
    tongue_ov, tongue_w = inch(0.25), panel_t / 2
    iw, ih = l2 - tf_w, d2 - tf_w
    top_panel = (box(-iw, iw, -ih, ih, panel_under, table_h)
                 + box(-(iw + tongue_ov), iw + tongue_ov,
                       -(ih + tongue_ov), ih + tongue_ov,
                       panel_under, panel_under + tongue_w))

    # =====================================================================
    # APRONS -- long sides carry the spandrel brackets; short sides plain.
    # The bracket elevation is the same polygon the Fusion long_side() draws,
    # now with the real curved treatments: quarter-circle coves (cove_r) at
    # the band/spandrel transitions -- reflex corners, so the 2D fillet cuts
    # a concave arc -- and rounded spandrel bottom corners (bot_r). Same
    # radii/vertices as the Fusion fil() calls at lines 3,6,7,10 / 4,5,8,9.
    # (The Fusion gable miter lines are interior split lines between the band
    # and spandrel BOARDS -- part decomposition, not outline geometry -- so
    # they don't appear here where each side is one body.)
    # =====================================================================
    cove_r, bot_r = inch(0.75), inch(0.75)
    AT, AB = tf_bot, tf_bot - apron_w
    SB = AB - spandrel_depth
    spo = ltx + leg_r + sp_edge_gap
    spi = ltx - leg_r - sp_edge_gap
    LH = la_half
    bracket = [(-LH, AT), (LH, AT), (LH, AB), (spo, AB), (spo, SB), (spi, SB),
               (spi, AB), (-spi, AB), (-spi, SB), (-spo, SB), (-spo, AB), (-LH, AB)]
    coves = [(i, cove_r) for i in (3, 6, 7, 10)]     # band/spandrel coves
    bots = [(i, bot_r) for i in (4, 5, 8, 9)]        # spandrel bottom rounds
    apron_f = poly_prism(bracket, "y", -lty - apron_t / 2, (0, apron_t, 0),
                         fillets=coves + bots)
    apron_b = apron_f.mirror(Plane.XZ)
    # short aprons: plain band between the legs, running in Y at x = -+ltx
    sd_half = d2 - ap_end_inset
    short = [(-sd_half, AT), (sd_half, AT), (sd_half, AB), (-sd_half, AB)]
    apron_l = poly_prism(short, "x", -ltx - apron_t / 2, (apron_t, 0, 0))
    apron_r = apron_l.mirror(Plane.YZ)

    # =====================================================================
    # SHELF -- frame-and-panel coped to the legs. Leg X/Y are further out at
    # shelf height (the leg leans), so the frame tracks them.
    # =====================================================================
    lxs = ltx + (leg_tip_z - (shelf_z - sf_t / 2)) * math.tan(splay)
    lys = lty + (leg_tip_z - (shelf_z - sf_t / 2)) * math.tan(splay)
    sz0, sz1 = shelf_z - sf_t, shelf_z
    sh_long_f = box(-lxs, lxs, -lys - leg_r, -lys + leg_r, sz0, sz1)
    sh_long_b = sh_long_f.mirror(Plane.XZ)
    sh_short_l = box(-lxs - leg_r, -lxs + leg_r, -lys, lys, sz0, sz1)
    # short rails cope to the long rails at the corners (the mitered tenons
    # meet inside the leg) -- same as the Fusion ShS_*_cope combine
    sh_short_l = sh_short_l - sh_long_f - sh_long_b
    sh_short_r = sh_short_l.mirror(Plane.YZ)
    sh_panel = box(-(lxs - leg_r), lxs - leg_r, -(lys - leg_r), lys - leg_r,
                   sz0 + (sf_t - sp_panel_t) / 2, sz0 + (sf_t + sp_panel_t) / 2)

    # =====================================================================
    # Seat everything against the round legs: subtract the legs from every
    # member that embeds into them (the cope / blind-tenon shoulder). This is
    # the boolean half of the concealed joinery -- it removes all overlaps and
    # leaves coped contact faces, so the assembly is interference-free and
    # connected.
    # =====================================================================
    def cope(s):
        return s - legunion

    # =====================================================================
    # 3D edge treatments -- applied AFTER the leg cope, so the fillet /
    # chamfer terminates against boolean-cut faces (the OCCT stress case
    # this spike exercises):
    #   * top frame: round-over on the outer top edge of each mitered rail
    #     (the Fusion original does this with spline cutter bodies, tf_cham;
    #     here it's a native OCCT edge fillet)
    #   * shelf rails: sf_cham chamfer on the top outer edge. Chamfering
    #     AFTER the cope fails here ("BRep_API: command not done"): the cope
    #     cylinder is near-tangent to the rail's outer face, and OCCT cannot
    #     terminate the chamfer face against that cylindrical cut surface.
    #     Workaround: chamfer the pristine edge FIRST, cope after -- booleans
    #     resolve the same intersection fine (and it matches shop order:
    #     mold the edge profile, then cut the joinery).
    # =====================================================================
    tf_round = inch(0.25)
    sf_cham = inch(0.3125)

    def soften_top(s, x=None, y=None):
        es = edges_at(s, x=x, y=y, z=table_h)
        return one_solid(fillet(es, tf_round))

    rail_f = soften_top(cope(rail_f), y=-d2)
    rail_b = soften_top(cope(rail_b), y=d2)
    stile_l = soften_top(cope(stile_l), x=-l2)
    stile_r = soften_top(cope(stile_r), x=l2)

    # the panel tongue cuts its groove into all four frame members
    top_panel = cope(top_panel)
    rail_f, rail_b = rail_f - top_panel, rail_b - top_panel
    stile_l, stile_r = stile_l - top_panel, stile_r - top_panel

    def cham_top(s, x=None, y=None):
        es = edges_at(s, x=x, y=y, z=sz1)
        return one_solid(chamfer(es, sf_cham))

    sh_long_f = cope(cham_top(sh_long_f, y=-lys - leg_r))
    sh_long_b = cope(cham_top(sh_long_b, y=lys + leg_r))
    sh_short_l = cope(cham_top(sh_short_l, x=-lxs - leg_r))
    sh_short_r = cope(cham_top(sh_short_r, x=lxs + leg_r))

    # ------------------------------------------------------------------
    # Shelf-rail tenons: full-height mitered tenons that MEET INSIDE each
    # round leg (the original's coped-shoulder M&T). Per corner, the long
    # and the short rail each send a tenon_w x sf_t tenon into the leg; a
    # 45-deg plane through the leg axis miters the pair against each other.
    # Tenons JOIN their rails; each leg is mortised by subtracting both.
    # Local coords: u grows toward the long rail's body, v toward the
    # short rail's body (x = X - sx*u, y = Y - sy*v); miter plane is u = v.
    # ------------------------------------------------------------------
    tenon_w = inch(0.5)
    L3 = 3 * leg_r

    def shelf_tenons(sx, sy, cyl):
        X, Y = sx * lxs, sy * lys

        def half(st):
            return poly_prism([(X - sx * s, Y - sy * t) for s, t in st],
                              "z", sz0, (0, 0, sf_t))
        rm_long = half([(-L3, -L3), (-L3, L3), (L3, L3)])    # v > u half
        rm_short = half([(-L3, -L3), (L3, -L3), (L3, L3)])   # u > v half
        t_long = (box(X - leg_r, X + leg_r, Y - tenon_w / 2, Y + tenon_w / 2,
                      sz0, sz1) & cyl) - rm_long
        t_short = (box(X - tenon_w / 2, X + tenon_w / 2, Y - leg_r, Y + leg_r,
                       sz0, sz1) & cyl) - rm_short
        return t_long, t_short

    shelf_longs = {"F": sh_long_f, "B": sh_long_b}
    shelf_shorts = {"L": sh_short_l, "R": sh_short_r}
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        lk, sk = ("F" if sy < 0 else "B"), ("L" if sx < 0 else "R")
        key = "Leg_" + lk + sk
        t_long, t_short = shelf_tenons(sx, sy, legs[key])
        legs[key] = legs[key] - t_long - t_short             # the mortise
        shelf_longs[lk] = shelf_longs[lk] + t_long
        shelf_shorts[sk] = shelf_shorts[sk] + t_short
    sh_long_f, sh_long_b = shelf_longs["F"], shelf_longs["B"]
    sh_short_l, sh_short_r = shelf_shorts["L"], shelf_shorts["R"]

    parts = {
        "Leg_FL": (legs["Leg_FL"], LEGC), "Leg_FR": (legs["Leg_FR"], LEGC),
        "Leg_BL": (legs["Leg_BL"], LEGC), "Leg_BR": (legs["Leg_BR"], LEGC),
        "TF_Front": (rail_f, FRAME), "TF_Back": (rail_b, FRAME),
        "TF_Left": (stile_l, FRAME), "TF_Right": (stile_r, FRAME),
        "TopPanel": (top_panel, PANEL),      # already coped (groove source)
        "Apron_Front": (cope(apron_f), APRON), "Apron_Back": (cope(apron_b), APRON),
        "Apron_Left": (cope(apron_l), APRON), "Apron_Right": (cope(apron_r), APRON),
        "ShelfLong_F": (sh_long_f, SHELF), "ShelfLong_B": (sh_long_b, SHELF),
        "ShelfShort_L": (sh_short_l, SHELF), "ShelfShort_R": (sh_short_r, SHELF),
        "ShelfPanel": (cope(sh_panel), PANEL),
    }
    comp = {"Leg": "Legs", "TF": "Top", "Top": "Top", "Apron": "Aprons",
            "Shelf": "Shelf"}
    for name, (solid, col) in parts.items():
        c = comp.get(name.split("_")[0], "")
        m.add(name, solid, col, c)
    return m


if __name__ == "__main__":
    run_cli(build, "out/ming_table")
