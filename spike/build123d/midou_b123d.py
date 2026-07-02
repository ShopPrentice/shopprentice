"""Midou (米斗) — tapered through-dovetail rice measure, in build123d.

Port of examples/midou-box/midou.py (680 lines of Fusion) to a coordinate-
driven kernel. Same geometry, same joinery: a lidless square frustum (30x30
rim, 21x21 foot, 17 tall) with through dovetails on all four splayed corners
and a rabbeted bottom panel.

The Fusion version spends most of its length fighting the sketch constraint
solver -- probe_orientations, set_ang supplement handling, isFullyConstrained
guards, per-vertex drift checks after every constraint. None of that exists
here: every point is placed at an exact model coordinate, and a board or a
tail is just `Face -> extrude along a vector`. The dovetails are still "flush
by construction" -- but the construction is arithmetic, not a solver.
"""
import math

from build123d import Solid, Face, Wire, Vector, Plane, Location
from b123d_common import Model, summarize, run_cli

# user parameters (cm / deg / count) -- the Fusion userParameters table
PARAMS = {
    "top_w": 30.0, "bot_w": 21.0, "box_h": 17.0, "board_t": 1.2,
    "dt_count": 6, "dt_tail_w": 1.9, "dt_angle_deg": 10.0, "dt_pad": 0.6,
    "panel_t": 0.8, "panel_z0": 1.0, "groove_d": 0.5,
}


def V(t):
    return Vector(t[0], t[1], t[2])


def add(a, b, s=1.0):
    return (a[0] + s * b[0], a[1] + s * b[1], a[2] + s * b[2])


def prism(corners, direction):
    """A planar polygon (model-space corners) swept along `direction`."""
    face = Face(Wire.make_polygon([V(c) for c in corners]))
    return Solid.extrude(face, V(direction))


def fuse(solids):
    out = solids[0]
    for s in solids[1:]:
        out = out + s
    return out


def build(overrides=None):
    p = {**PARAMS, **(overrides or {})}
    top_w, bot_w, box_h, board_t = p["top_w"], p["bot_w"], p["box_h"], p["board_t"]
    dt_count = int(p["dt_count"])
    dt_tail_w, dt_angle = p["dt_tail_w"], math.radians(p["dt_angle_deg"])
    dt_pad = p["dt_pad"]
    panel_t, panel_z0, groove_d = p["panel_t"], p["panel_z0"], p["groove_d"]

    # ---- derived ----
    tilt = math.atan((top_w - bot_w) / 2 / box_h)
    tanT, cosT, sinT = math.tan(tilt), math.cos(tilt), math.sin(tilt)
    btw = board_t / cosT                                   # horizontal wall thickness
    jl = math.sqrt(2 * ((top_w - bot_w) / 2) ** 2 + box_h ** 2)
    dt_pitch = (jl - 2 * dt_pad) / dt_count
    dt_half_pin = (dt_pitch - dt_tail_w) / 2
    panel_half = bot_w / 2 - btw + (panel_z0 + panel_t) * tanT + groove_d
    rabbet_half = bot_w / 2 - btw + panel_z0 * tanT

    bw2, tw2, H = bot_w / 2, top_w / 2, box_h
    dvec = (-(tw2 - bw2) / jl, -(tw2 - bw2) / jl, H / jl)  # unit shoulder/joint line, up
    u_out = (-1.0, 0.0, 0.0)                               # grain dir, outboard left
    vvec = (0.0, -sinT, cosT)                              # in-face up-slope dir

    m = Model("Midou (米斗)", params=p, units="cm")

    # =====================================================================
    # PHASE A -- the four splayed boards
    # Front/Back span the inner width (pin boards seat in the corners);
    # Left/Right span the full outer width. Each is a trapezoid on its tilted
    # outer face, swept horizontally by the wall thickness.
    # =====================================================================
    front = prism([(-(bw2 - btw), -bw2, 0.0), (bw2 - btw, -bw2, 0.0),
                   (tw2 - btw, -tw2, H), (-(tw2 - btw), -tw2, H)], (0, btw, 0))
    left = prism([(-bw2, -bw2, 0.0), (-bw2, bw2, 0.0),
                  (-tw2, tw2, H), (-tw2, -tw2, H)], (btw, 0, 0))
    back = front.mirror(Plane.XZ)
    right = left.mirror(Plane.YZ)

    # =====================================================================
    # PHASE B -- dovetails. One tail trapezoid on the front outer face: base
    # on the slanted shoulder line (unequal flank lengths), tips on the box
    # corner line. Swept along the pin board's grain (+Y) it lands flush on
    # the side board by construction. Pattern along the shoulder, mirror to
    # four corners, CUT the pin boards, JOIN the tail boards.
    # =====================================================================
    aa = dt_angle
    P0 = (-(bw2 - btw), -bw2, 0.0)
    f_lo = (-math.cos(aa), sinT * math.sin(aa), -cosT * math.sin(aa))
    f_hi = (-math.cos(aa), -sinT * math.sin(aa), cosT * math.sin(aa))
    B_lo = add(P0, dvec, dt_pad + dt_half_pin)
    B_hi = add(P0, dvec, dt_pad + dt_half_pin + dt_tail_w)
    # tips: intersect each flank ray with the box corner line (x + z*tanT = -bw2)
    t_lo = -btw / (f_lo[0] + f_lo[2] * tanT)
    t_hi = -btw / (f_hi[0] + f_hi[2] * tanT)
    T_lo = add(B_lo, f_lo, t_lo)
    T_hi = add(B_hi, f_hi, t_hi)

    tail0 = prism([B_lo, B_hi, T_hi, T_lo], (0, btw, 0))
    fl_tails = [tail0.moved(Location(V(add((0, 0, 0), dvec, i * dt_pitch))))
                for i in range(dt_count)]
    fr_tails = [t.mirror(Plane.YZ) for t in fl_tails]
    bk_tails = [t.mirror(Plane.XZ) for t in fl_tails + fr_tails]
    bkl = [t for t in bk_tails if t.bounding_box().center().X < 0]
    bkr = [t for t in bk_tails if t.bounding_box().center().X > 0]

    # sockets cut into the pin boards; tails join the tail boards
    left = left - fuse(fl_tails + bkl)
    right = right - fuse(fr_tails + bkr)
    front = front + fuse(fl_tails + fr_tails)
    back = back + fuse(bk_tails)

    # =====================================================================
    # PHASE C -- bottom panel: full-size tongue (upper half) enters the wall
    # grooves; lower half is a taper (loft) so the rabbet shoulder mates the
    # tilted inner walls. The panel cuts its own housing into all four boards.
    # =====================================================================
    z0, pt = panel_z0, panel_t
    tongue = Solid.make_box(2 * panel_half, 2 * panel_half, pt / 2).moved(
        Location((-panel_half, -panel_half, z0 + pt / 2)))
    exp_top = rabbet_half + (pt / 2) * tanT
    rab_bot = Face(Wire.make_polygon([
        (-rabbet_half, -rabbet_half, z0), (rabbet_half, -rabbet_half, z0),
        (rabbet_half, rabbet_half, z0), (-rabbet_half, rabbet_half, z0)]))
    rab_top = Face(Wire.make_polygon([
        (-exp_top, -exp_top, z0 + pt / 2), (exp_top, -exp_top, z0 + pt / 2),
        (exp_top, exp_top, z0 + pt / 2), (-exp_top, exp_top, z0 + pt / 2)]))
    rabbet = Solid.make_loft([rab_bot.outer_wire(), rab_top.outer_wire()])
    panel = tongue + rabbet

    front = front - panel
    back = back - panel
    left = left - panel
    right = right - panel

    WOOD = "#c79a6b"
    PANEL = "#9c6b3f"
    m.add("Front", front, WOOD, "Case")
    m.add("Back", back, WOOD, "Case")
    m.add("Left", left, WOOD, "Case")
    m.add("Right", right, WOOD, "Case")
    m.add("Panel", panel, PANEL, "Bottom")
    return m


if __name__ == "__main__":
    run_cli(build, "out/midou")
