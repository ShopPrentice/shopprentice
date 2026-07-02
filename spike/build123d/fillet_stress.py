"""OCCT fillet/chamfer robustness battery — the spike's failure-mode probe.

Each case tries a fillet/chamfer configuration known to be finicky in CAD
kernels, at the real dimensions from the Ming table (3/8" apron stock,
1-3/8" round legs, 0.75" coves). A case PASSes only if the operation
completes AND the result is a valid solid with a sane volume — OCCT can
"succeed" and hand back garbage, so both checks matter.

Run:  ../../.venv-b123d/bin/python fillet_stress.py
"""
import math

from build123d import Solid, Face, Wire, Vector, Plane, Location, fillet, chamfer

IN = 2.54
APRON_T = 0.375 * IN          # 3/8" stock — thinnest face in the model
LEG_R = 1.375 / 2 * IN
SPAN_DEPTH = 3.5625 * IN      # spandrel vertical segment length


def V(t):
    return Vector(*t)


def box(x0, x1, y0, y1, z0, z1):
    return Solid.make_box(x1 - x0, y1 - y0, z1 - z0).moved(Location((x0, y0, z0)))


results = []


def case(name):
    def deco(fn):
        try:
            note = fn() or ""
            status = "PASS"
        except Exception as e:
            status = "FAIL"
            note = f"{type(e).__name__}: {e}"
            cause = e.__cause__
            if cause is not None:
                note += f" [cause: {cause}]"
        results.append((name, status, str(note).replace("\n", " ")[:110]))
        return fn
    return deco


def check_solid(s, vol_lo, vol_hi, what=""):
    sols = s.solids() if hasattr(s, "solids") else [s]
    assert len(sols) == 1, f"{what}: {len(sols)} solids"
    sol = sols[0]
    assert sol.is_valid, f"{what}: invalid solid"
    assert vol_lo < sol.volume < vol_hi, \
        f"{what}: volume {sol.volume:.2f} outside ({vol_lo:.2f},{vol_hi:.2f})"
    return sol.volume


# ==========================================================================
# 1. 2D profile fillets (wire/face level, before extrude)
# ==========================================================================
def spandrel_face():
    """One spandrel elevation: 4.5" wide x 3.5625" deep step profile with a
    reflex (cove) corner each side at the top and convex corners at the
    bottom — the exact local topology of the Ming bracket."""
    w, d, band = 4.5 * IN, SPAN_DEPTH, 1.125 * IN
    pts = [(-3 * w, 0), (3 * w, 0), (3 * w, -band), (w / 2, -band),
           (w / 2, -band - d), (-w / 2, -band - d), (-w / 2, -band),
           (-3 * w, -band)]
    return Face(Wire.make_polygon([V((x, y, 0)) for x, y in pts])), pts


def pick(shape, pts, idxs):
    out = [v for v in shape.vertices()
           for i in idxs
           if abs(v.X - pts[i][0]) < 1e-6 and abs(v.Y - pts[i][1]) < 1e-6]
    assert len(out) == len(idxs), f"picked {len(out)} of {len(idxs)}"
    return out


def profile_fillet(r_cove, r_bot):
    f, pts = spandrel_face()
    a0 = f.area
    sk = fillet(pick(f, pts, (3, 6)), r_cove)            # reflex coves
    if r_bot:
        sk = fillet(pick(sk, pts, (4, 5)), r_bot)        # convex bottoms
    face = sk.faces()[0]
    assert face.is_valid, "invalid face"
    # face must still be a single sane face
    assert 0.2 * a0 < face.area < 2 * a0, f"area {face.area:.1f} vs {a0:.1f}"
    sol = Solid.extrude(face, V((0, 0, APRON_T)))
    assert sol.is_valid, "extrude of filleted face invalid"
    return f"area {a0:.1f}->{face.area:.1f}, extrudes ok"


@case("2D cove+round, model radii (0.75\")")
def _():
    return profile_fillet(0.75 * IN, 0.75 * IN)


@case("2D cove+round, r sum ~= segment (1.75\" each on 3.5625\" side)")
def _():
    return profile_fillet(1.75 * IN, 1.75 * IN)


@case("2D cove+round, arcs would overlap (2.0\" each on 3.5625\" side)")
def _():
    return profile_fillet(2.0 * IN, 2.0 * IN)


@case("2D cove r > adjacent segment (4\" cove on 3.5625\" side)")
def _():
    return profile_fillet(4.0 * IN, 0)


@case("2D cove r huge (10\")")
def _():
    return profile_fillet(10.0 * IN, 0)


# ==========================================================================
# 2. 3D edge fillet radius vs face width (apron stock 3/8" = 0.9525 cm)
# ==========================================================================
def edge_fillet_vs_thickness(frac):
    t = APRON_T
    b = box(0, 20, 0, 5, 0, t)
    # one long top edge
    e = [e for e in b.edges()
         if abs(e.bounding_box().min.Z - t) < 1e-6
         and abs(e.bounding_box().max.Z - t) < 1e-6
         and abs(e.bounding_box().min.Y) < 1e-6][0]
    r = frac * t
    out = fillet([e], r)
    v = check_solid(out, 20 * 5 * t * 0.5, 20 * 5 * t, f"fillet r={frac}t")
    return f"vol {v:.2f} (r={r:.3f}cm on {t:.3f}cm face)"


@case("3D fillet r = 0.5 x face width")
def _():
    return edge_fillet_vs_thickness(0.5)


@case("3D fillet r = 0.95 x face width")
def _():
    return edge_fillet_vs_thickness(0.95)


@case("3D fillet r = 0.999 x face width")
def _():
    return edge_fillet_vs_thickness(0.999)


@case("3D fillet r = face width (full round-over)")
def _():
    return edge_fillet_vs_thickness(1.0)


@case("3D fillet r = 1.05 x face width")
def _():
    return edge_fillet_vs_thickness(1.05)


# ==========================================================================
# 3. fillets meeting at a corner
# ==========================================================================
@case("corner: 3 edges at a vertex, one fillet call (r=0.6cm)")
def _():
    b = box(0, 10, 0, 10, 0, 10)
    vtx = Vector(0, 0, 10)
    es = [e for e in b.edges()
          if min((Vector(v.X, v.Y, v.Z) - vtx).length for v in e.vertices()) < 1e-6]
    assert len(es) == 3
    out = fillet(es, 0.6)
    return f"vol {check_solid(out, 900, 1000, 'corner3'):.1f}"


def top_edge(s, x=None, y=None, z=10.0):
    """The top edge of a box pinned at x= or y= (whole edge on that plane)."""
    for e in s.edges():
        bb = e.bounding_box()
        if abs(bb.min.Z - z) > 1e-3 or abs(bb.max.Z - z) > 1e-3:
            continue
        if x is not None and (abs(bb.min.X - x) > 1e-3 or abs(bb.max.X - x) > 1e-3):
            continue
        if y is not None and (abs(bb.min.Y - y) > 1e-3 or abs(bb.max.Y - y) > 1e-3):
            continue
        return e
    raise AssertionError("edge not found")


@case("corner: 2 perpendicular top edges, sequential fillet calls")
def _():
    # fillet the front-top edge, THEN the right-top edge that used to meet it
    # at the corner — the second fillet must land on the first one's surface
    b = box(0, 10, 0, 10, 0, 10)
    s = fillet([top_edge(b, y=0)], 0.6).solids()[0]
    e2 = top_edge(s, x=10)          # shortened by the first fillet, still there
    out = fillet([e2], 0.6)
    return f"vol {check_solid(out, 900, 1000, 'seq2'):.1f}"


@case("corner: 2 perpendicular top edges, one call (r=0.6cm)")
def _():
    b = box(0, 10, 0, 10, 0, 10)
    out = fillet([top_edge(b, y=0), top_edge(b, x=10)], 0.6)
    return f"vol {check_solid(out, 900, 1000, 'two-in-one'):.1f}"


# ==========================================================================
# 4. fillet/chamfer interacting with a boolean-cut (coped) face
#    — the shelf-rail x leg configuration from the model
# ==========================================================================
def coped_rail(mode="tangent", lean_cm=0.03):
    """Shelf rail with a leg cope: box minus leaning cylinder.
    mode='tangent': cylinder surface ~lean_cm inside the rail's outer face at
      the top edge — the model's near-tangent case (cope grazes the edge).
    mode='cross': cylinder protrudes 1 cm through the outer face — the cope
      cuts the top edge into segments with clean, non-tangent terminations."""
    w = 2 * LEG_R                     # rail width = leg diameter (model)
    t = 0.875 * IN                    # sf_t
    rail = box(-15, 15, 0, w, 0, t)
    ycc = LEG_R + lean_cm if mode == "tangent" else LEG_R - 1.0
    pl = Plane(origin=Vector(0, ycc, -5),
               z_dir=Vector(0, -lean_cm / (t + 10), 1).normalized())
    cyl = Solid.make_cylinder(LEG_R, t + 10, pl)
    return rail - cyl, w, t


@case("chamfer top edge AFTER cope, near-tangent cyl (model case)")
def _():
    s, w, t = coped_rail("tangent")
    es = [e for e in s.edges()
          if abs(e.bounding_box().min.Z - t) < 1e-3
          and abs(e.bounding_box().max.Z - t) < 1e-3
          and e.bounding_box().max.Y < 0.1]
    out = chamfer(es, 0.3125 * IN)
    return f"vol {check_solid(out, 1, 1e5, 'cham-cope'):.1f}"


@case("chamfer top edge AFTER cope, cyl centered (clean crossing)")
def _():
    s, w, t = coped_rail("cross")
    es = [e for e in s.edges()
          if abs(e.bounding_box().min.Z - t) < 1e-3
          and abs(e.bounding_box().max.Z - t) < 1e-3
          and e.bounding_box().max.Y < 0.1]
    out = chamfer(es, 0.3125 * IN)
    return f"vol {check_solid(out, 1, 1e5, 'cham-cope-center'):.1f}"


@case("fillet top edge AFTER cope, near-tangent cyl")
def _():
    s, w, t = coped_rail("tangent")
    es = [e for e in s.edges()
          if abs(e.bounding_box().min.Z - t) < 1e-3
          and abs(e.bounding_box().max.Z - t) < 1e-3
          and e.bounding_box().max.Y < 0.1]
    out = fillet(es, 0.3125 * IN)
    return f"vol {check_solid(out, 1, 1e5, 'fil-cope'):.1f}"


@case("chamfer BEFORE cope, then boolean (the workaround)")
def _():
    w = 2 * LEG_R
    t = 0.875 * IN
    rail = box(-15, 15, 0, w, 0, t)
    es = [e for e in rail.edges()
          if abs(e.bounding_box().min.Z - t) < 1e-6
          and abs(e.bounding_box().max.Z - t) < 1e-6
          and abs(e.bounding_box().min.Y) < 1e-6]
    railc = chamfer(es, 0.3125 * IN).solids()[0]
    lean = 0.03
    pl = Plane(origin=Vector(0, LEG_R + lean, -5),
               z_dir=Vector(0, -lean / (t + 10), 1).normalized())
    cyl = Solid.make_cylinder(LEG_R, t + 10, pl)
    out = railc - cyl
    return f"vol {check_solid(out, 1, 1e5, 'cope-after-cham'):.1f}"


@case("chamfer AFTER cope, cyl centered, tiny length (0.1cm)")
def _():
    s, w, t = coped_rail("cross")
    es = [e for e in s.edges()
          if abs(e.bounding_box().min.Z - t) < 1e-3
          and abs(e.bounding_box().max.Z - t) < 1e-3
          and e.bounding_box().max.Y < 0.1]
    out = chamfer(es, 0.1)
    return f"vol {check_solid(out, 1, 1e5, 'cham-tiny'):.1f}"


@case("chamfer AFTER cope, tangent, skipping the grazed sliver region")
def _():
    # near-tangent cope splits the top edge into two long segments around a
    # ~0.6cm-wide graze; chamfer only the long segments. Their inner ends
    # still TERMINATE on the near-tangent cylindrical face, so this tests
    # whether skipping the sliver zone is enough of a dodge. (A crossing cut
    # always leaves the segment ends on the seam — there is no "not touching
    # the cope" selection.)
    s, w, t = coped_rail("tangent")
    es = [e for e in s.edges()
          if abs(e.bounding_box().min.Z - t) < 1e-3
          and abs(e.bounding_box().max.Z - t) < 1e-3
          and e.bounding_box().max.Y < 0.1
          and all(abs(v.X) > 0.3 for v in e.vertices())]
    assert es, "no clear segments"
    out = chamfer(es, 0.3125 * IN)
    return f"{len(es)} segments, vol {check_solid(out, 1, 1e5, 'cham-clear'):.1f}"


@case("fillet the cope seam edge itself (box/cylinder intersection curve)")
def _():
    s, w, t = coped_rail("cross")
    # edges lying on the cylindrical face: non-line edges
    seam = [e for e in s.edges() if e.geom_type.name != "LINE"]
    assert seam, "no seam edges found"
    out = fillet(seam, 0.15)
    return f"{len(seam)} seam edges, vol {check_solid(out, 1, 1e5, 'seam'):.1f}"


@case("fillet cope seam, near-tangent (sliver terminations)")
def _():
    s, w, t = coped_rail("tangent")
    seam = [e for e in s.edges() if e.geom_type.name != "LINE"]
    assert seam, "no seam edges found"
    out = fillet(seam, 0.15)
    return f"{len(seam)} seam edges, vol {check_solid(out, 1, 1e5, 'seam-tan'):.1f}"


@case("fillet cope seam, tiny radius (0.05cm)")
def _():
    s, w, t = coped_rail("cross")
    seam = [e for e in s.edges() if e.geom_type.name != "LINE"]
    out = fillet(seam, 0.05)
    return f"{len(seam)} seam edges, vol {check_solid(out, 1, 1e5, 'seam-05'):.1f}"


# ==========================================================================
# 5. 3D alternative to profile fillets: fillet the extruded prism's
#    vertical edges (cove = reflex/concave 3D edge)
# ==========================================================================
@case("3D cove: fillet vertical reflex edge of extruded bracket (0.75\")")
def _():
    f, pts = spandrel_face()
    sol = Solid.extrude(f, V((0, 0, APRON_T)))
    # vertical edges at the two reflex corners (3) and (6)
    es = [e for e in sol.edges()
          if abs(e.bounding_box().min.X - e.bounding_box().max.X) < 1e-6
          and abs(e.bounding_box().min.Y - e.bounding_box().max.Y) < 1e-6
          and any(abs(e.bounding_box().min.X - pts[i][0]) < 1e-6
                  and abs(e.bounding_box().min.Y - pts[i][1]) < 1e-6
                  for i in (3, 6))]
    assert len(es) == 2
    out = fillet(es, 0.75 * IN)
    return f"vol {check_solid(out, 1, 1e6, '3dcove'):.1f}"


@case("3D cove + bottom rounds on the same prism, one call")
def _():
    f, pts = spandrel_face()
    sol = Solid.extrude(f, V((0, 0, APRON_T)))
    es = [e for e in sol.edges()
          if abs(e.bounding_box().min.X - e.bounding_box().max.X) < 1e-6
          and abs(e.bounding_box().min.Y - e.bounding_box().max.Y) < 1e-6
          and any(abs(e.bounding_box().min.X - pts[i][0]) < 1e-6
                  and abs(e.bounding_box().min.Y - pts[i][1]) < 1e-6
                  for i in (3, 4, 5, 6))]
    assert len(es) == 4
    out = fillet(es, 0.75 * IN)
    return f"vol {check_solid(out, 1, 1e6, '3dcove4'):.1f}"


# ==========================================================================
# 5. the real model members, re-run standalone for the record
# ==========================================================================
@case("model: mitered frame rail, outer-top fillet after leg cope")
def _():
    import ming_table_b123d as mt
    # cheap proxy: rebuild the whole table; its soften_top/cham_top calls are
    # the model-scale versions of the cases above
    m = mt.build()
    assert len(m.parts) == 18
    return "full model builds with all edge treatments"


print(f"\n{'=' * 78}\nOCCT fillet/chamfer robustness battery\n{'=' * 78}")
for name, status, note in results:
    print(f"  [{status}] {name}\n         {note}")
npass = sum(1 for r in results if r[1] == "PASS")
print(f"\n  {npass}/{len(results)} PASS")
