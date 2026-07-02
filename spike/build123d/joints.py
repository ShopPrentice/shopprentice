"""joints.py — joinery vocabulary for the build123d backend (sp123d seed, v0).

Each function here is a JOINT, not a boolean: it encodes the mechanical logic
of a traditional joinery form — what bears on what, what movement it permits,
what separation it resists — and returns solids that realize it. A furniture
script should read as STOCK + JOINTS; if a model needs raw booleans to
describe its joinery, the vocabulary is missing a word.

The forms below are the ones a classical Ming side table needs, but every
signature is dimension-driven and reusable:

  miter_tenon_frame        格角榫   mitered mortise-and-tenon frame corner
  tongue_panel             槽口装板  tongue-and-groove floating/flush panel
  full_blind_dovetail_corner 闷齿斗角榫 concealed dovetailed box/ring corner
  sliding_batten           穿带/带   sliding-dovetail batten (anti-cup)
  mitered_leg_tenons       圆包圆内榫 rail tenons meeting inside a round leg
  leg_slot                 夹头-style pass-through: the LEG yields to the rail

Solids in, solids out; cm units; +Z up.
"""
import math

from build123d import Solid, Face, Wire, Vector, Plane, Location, fillet


# ---------------------------------------------------------------------------
# stock helpers
# ---------------------------------------------------------------------------
def box(x0, x1, y0, y1, z0, z1):
    return Solid.make_box(x1 - x0, y1 - y0, z1 - z0).moved(Location((x0, y0, z0)))


def fuse(solids):
    out = solids[0]
    for s in solids[1:]:
        out = out + s
    return out


def poly_prism(corners_2d, fixed_axis, fixed_val, extrude_vec, fillets=None):
    """Planar polygon ((a,b) pairs; fixed_axis supplies the third coord)
    extruded along extrude_vec. Optional profile-level vertex fillets —
    convex round-overs AND reflex coves — far more robust than filleting
    the solid's edges afterwards."""
    pts = []
    for a, b in corners_2d:
        if fixed_axis == "y":
            pts.append((a, fixed_val, b))
        elif fixed_axis == "x":
            pts.append((fixed_val, a, b))
        else:
            pts.append((a, b, fixed_val))
    face = Face(Wire.make_polygon([Vector(*p) for p in pts]))
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
    return Solid.extrude(face, Vector(*extrude_vec))


def edges_at(solid, x=None, y=None, z=None, tol=0.05):
    """Edges pinned to the given coordinate(s) — selects an edge run even
    when boolean cuts have split it into segments."""
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
    sols = shape.solids()
    assert len(sols) == 1, f"expected 1 solid, got {len(sols)}"
    return sols[0]


# ---------------------------------------------------------------------------
# 格角榫 — mitered mortise-and-tenon frame corner
# ---------------------------------------------------------------------------
def miter_tenon_frame(l2, d2, w, t, z0,
                      depth_frac=1.5 / 3.5, shoulder_in_frac=1.2 / 3.5,
                      shoulder_out_frac=0.6 / 3.5):
    """Rectangular frame (outer l2/d2 half-dims, member width w, thickness t,
    underside z0) whose corners are 格角榫: the RAILS carry a concealed,
    shouldered tenon in the middle third of the thickness; the top and
    bottom thirds are mitered 45 degrees, so the joint reads as a clean
    miter from every outside face while the tenon carries the load.

    Mechanics: the miter hides end grain and lets the molding run around
    the corner; the shouldered tenon (deeper shoulder on the show side)
    resists racking; because it sits in the middle third, shrinkage of the
    stile cannot open the visible miter line.

    Returns (rail_front, rail_back, stile_left, stile_right): rails carry
    tenons, stiles carry the mating mortises (cut by subtracting the rails,
    so the fit is exact by construction)."""
    tn_d, tn_si, tn_so = w * depth_frac, w * shoulder_in_frac, w * shoulder_out_frac
    t3 = t / 3
    OY, IY = -d2, -d2 + w
    tri = [(l2, OY), (l2, IY), (l2 - w, IY)]
    pent = [(l2, OY + tn_so), (l2, IY - tn_si), (l2 - tn_d, IY - tn_si),
            (l2 - tn_d, OY + tn_d), (l2 - tn_so, OY + tn_so)]
    end_cut = fuse([
        poly_prism(tri, "z", z0 + 2 * t3, (0, 0, t3)),   # top miter
        poly_prism(tri, "z", z0, (0, 0, t3)),            # bottom miter
        poly_prism(pent, "z", z0 + t3, (0, 0, t3)),      # tenon waste
    ])
    end_cuts = end_cut + end_cut.mirror(Plane.YZ)
    rail_f = box(-l2, l2, OY, IY, z0, z0 + t) - end_cuts
    rail_b = rail_f.mirror(Plane.XZ)
    stile_l = box(-l2, -l2 + w, -d2, d2, z0, z0 + t) - rail_f - rail_b
    return rail_f, rail_b, stile_l, stile_l.mirror(Plane.YZ)


# ---------------------------------------------------------------------------
# 槽口装板 — tongue-and-groove panel
# ---------------------------------------------------------------------------
def tongue_panel(iw, ih, z_under, z_top, tongue_ov, tongue_w):
    """Panel filling a frame opening (inner half-dims iw/ih), flush at
    z_top, with a tongue lapping tongue_ov into the frame members.

    Mechanics: the tongue carries the panel in grooves on all four sides
    without glue, so the wide panel can shrink and swell across the grain
    inside the frame — the classic answer to seasonal movement. Cut the
    grooves by subtracting this solid from the frame members."""
    return (box(-iw, iw, -ih, ih, z_under, z_top)
            + box(-(iw + tongue_ov), iw + tongue_ov,
                  -(ih + tongue_ov), ih + tongue_ov,
                  z_under, z_under + tongue_w))


# ---------------------------------------------------------------------------
# 闷齿斗角榫 — hidden full-blind dovetail corner
# ---------------------------------------------------------------------------
def full_blind_dovetail_corner(X0, y0, y1, zb, zt, t,
                               lip, pad, angle, tail_w, n):
    """One ring corner where a SHORT board (running in y at x-station X0,
    thickness t) meets a LONG board (running in x within the y-band
    [y0, y1]). Fully blind: a lip of the long board conceals the joint
    from the front, and the tails stop lip short of the end, so no end
    grain or tail shows on any outside face — the corner reads as a butt.

    Mechanics: the tails (stacked in z) FLARE toward the concealed face,
    so pulling the boards apart along the long board's axis wedges the
    tails tighter — the ring cannot open. The lip also protects the
    fragile tail ends.

    Returns (tails, corner_block):
        short_board = short_stock - corner_block + tails
        long_board  = long_stock  - tails
    corner_block extends 0.3 past zb/zt so it still covers the short
    stock's column if the assembly is later rotated (e.g. a leaning ring)."""
    socket = t - lip
    nw = tail_w - 2 * socket * math.tan(angle)
    pitch = (zt - zb - 2 * pad) / n
    tails = []
    for k in range(n):
        zc = zb + pad + (k + 0.5) * pitch
        trap = [(y0 + lip, zc - tail_w / 2),   # deep end: WIDE (locks)
                (y0 + lip, zc + tail_w / 2),
                (y1, zc + nw / 2),             # entry: narrow
                (y1, zc - nw / 2)]
        tails.append(poly_prism(trap, "x", X0 + lip, (t - lip, 0, 0)))
    block = box(X0, X0 + t, y0, y1, zb - 0.3, zt + 0.3)
    return fuse(tails), block


# ---------------------------------------------------------------------------
# 穿带 — sliding-dovetail batten
# ---------------------------------------------------------------------------
def sliding_batten(cx, w, z_bottom, z_ridge_base, ridge_narrow, ridge_wide,
                   ridge_depth, y_half, tenon_len=0.0, tenon_h=0.0):
    """Batten under a panel, running in y at x-center cx: body from
    z_bottom up to the panel underside (z_ridge_base), with a dovetail
    RIDGE (narrow at the surface, wide at depth) rising ridge_depth into
    the panel. Optional tenons extend tenon_len beyond +-y_half into the
    surrounding rails/frame.

    Mechanics: the flared ridge holds the panel FLAT (anti-cup) while the
    panel remains free to slide along the ridge with seasonal movement —
    restraint across the grain, freedom along it. No glue. Cut the
    panel's groove and the rails' mortises by subtracting this solid."""
    prof = [(cx - w / 2, z_bottom), (cx - w / 2, z_ridge_base),
            (cx - ridge_narrow / 2, z_ridge_base),
            (cx - ridge_wide / 2, z_ridge_base + ridge_depth),
            (cx + ridge_wide / 2, z_ridge_base + ridge_depth),
            (cx + ridge_narrow / 2, z_ridge_base),
            (cx + w / 2, z_ridge_base), (cx + w / 2, z_bottom)]
    b = poly_prism(prof, "y", -y_half, (0, 2 * y_half, 0))
    if tenon_len > 0 and tenon_h > 0:
        tn = box(cx - w / 2, cx + w / 2, -y_half - tenon_len, -y_half,
                 z_ridge_base - tenon_h, z_ridge_base)
        b = b + tn + tn.mirror(Plane.XZ)
    return b


# ---------------------------------------------------------------------------
# 圆包圆内榫 — mitered rail tenons meeting inside a round leg
# ---------------------------------------------------------------------------
def mitered_leg_tenons(X, Y, sx, sy, leg_solid, z0, z1, tenon_w, leg_r):
    """At the corner leg centered (X*sx? no: at (X, Y) with corner signs
    sx, sy), the long rail (running in x) and the short rail (running in
    y) each send a full-height tenon_w tenon INTO the round leg; a 45-deg
    plane through the leg axis miters the pair against each other.

    Mechanics: two rails share one leg's interior — the miter lets both
    tenons reach past the leg's center for maximum glue depth without
    colliding, and full height means the shelf's load bears on the whole
    rail section, no shoulder to shear. Subtract both tenons from the leg
    to mortise it; fuse each tenon to its rail.

    Local coords: u grows toward the long rail's body, v toward the short
    rail's (x = X - sx*u, y = Y - sy*v); the miter plane is u = v.
    Returns (tenon_long, tenon_short)."""
    L3 = 3 * leg_r

    def half(st):
        return poly_prism([(X - sx * s_, Y - sy * t_) for s_, t_ in st],
                          "z", z0, (0, 0, z1 - z0))
    rm_long = half([(-L3, -L3), (-L3, L3), (L3, L3)])    # v > u half
    rm_short = half([(-L3, -L3), (L3, -L3), (L3, L3)])   # u > v half
    t_long = (box(X - leg_r, X + leg_r, Y - tenon_w / 2, Y + tenon_w / 2,
                  z0, z1) & leg_solid) - rm_long
    t_short = (box(X - tenon_w / 2, X + tenon_w / 2, Y - leg_r, Y + leg_r,
                   z0, z1) & leg_solid) - rm_short
    return t_long, t_short


# ---------------------------------------------------------------------------
# 夹头-style pass-through — the leg yields to the rail
# ---------------------------------------------------------------------------
def leg_slot(leg_solid, ring_solid):
    """Slot the LEG so a continuous rail/apron assembly threads through it.

    Mechanics: where a rail must stay continuous past a post (an apron
    band with spandrels, a stretcher), cutting the RAIL on the post would
    sever it — instead the post is slotted and keeps its bearing above
    and below, while the rail passes intact. Shoulders of the slot bear
    on the rail faces against racking."""
    return leg_solid - ring_solid
