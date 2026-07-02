"""Classic Ming side table (平头案) — authored as STOCK + JOINTS.

28"L x 13.75"D x 30.875"H. Round legs splayed 1.5deg. The joinery schedule —
every joint a named form from joints.py, the vocabulary the piece is
"written" in:

  top frame corners     格角榫    miter_tenon_frame      (concealed tenon,
                                                          reads as a miter)
  top / shelf panels    槽口装板  tongue_panel           (floating in grooves,
                                                          free to move)
  top battens           带        sliding_batten         (anti-cup, sliding)
  shelf batten          穿带      sliding_batten
  apron ring corners    闷齿斗角榫 full_blind_dovetail_corner (locked ring,
                                                          nothing shows)
  shelf rails -> legs   圆包圆内榫 mitered_leg_tenons     (tenons meet at 45deg
                                                          inside the round leg)
  aprons -> legs        夹头式     leg_slot               (the leg yields; the
                                                          band stays whole)

Details carried outside the joint vocabulary: the spandrel bracket profile
with quarter-circle coves, the hollow spline edge molding (curve sampled
from the Fusion original), and the 1.5deg lean of the apron plane — built
vertical, rotated rigidly about the leg-top axis (the dovetail pieces ride
the same rotation, so the joint fit survives), then sheared flat against
the frame underside.
"""
import importlib
import math

from build123d import Solid, Vector, Plane, Location, Axis, chamfer

import joints
importlib.reload(joints)        # dev: pick up vocabulary edits on rebuild
from joints import (box, fuse, poly_prism, edges_at, one_solid,
                    miter_tenon_frame, tongue_panel,
                    full_blind_dovetail_corner, sliding_batten,
                    mitered_leg_tenons, leg_slot)
from b123d_common import Model, run_cli

IN = 2.54

PARAMS = {
    "table_l": 28.0, "table_d": 13.75, "table_h": 30.875, "splay_deg": 1.5,
    "tf_t": 1.0625, "tf_w": 2.0, "panel_t": 0.3125,
    "leg_dia": 1.375, "leg_setback_x": 5.375, "leg_setback_y": 1.125,
    "apron_t": 0.375, "apron_w": 1.125, "spandrel_depth": 3.5625,
    "ap_end_inset": 0.875, "sp_edge_gap": 1.0,
    "shelf_z": 20.0, "sf_t": 0.875, "sp_panel_t": 0.3125,
    "fbd_lip": 0.1, "fbd_pad": 0.1, "fbd_angle_deg": 10.0,
    "fbd_tail_w": 0.225, "fbd_tail_count": 2,
}


def inch(x):
    return x * IN


# hollow edge-molding profile: the original's designed curve, sampled from
# the Fusion capture (dz up from the frame underside, dy inward from the
# outer face, cm)
MOLDING = [(0.0, 0.2171), (0.0131, 0.162), (0.2257, 0.1407),
           (0.5282, 0.1383), (0.7732, 0.1334), (0.8897, 0.1122),
           (0.9667, 0.079), (1.1405, 0.0477), (1.4297, 0.0259),
           (1.7613, 0.0137), (2.0509, 0.0081), (2.2662, 0.0057),
           (2.4266, 0.0043), (2.5648, 0.0026), (2.6988, 0.0)]


def build(overrides=None):
    p = {**PARAMS, **(overrides or {})}
    table_l, table_d, table_h = inch(p["table_l"]), inch(p["table_d"]), inch(p["table_h"])
    splay = math.radians(p["splay_deg"])
    tf_t, tf_w = inch(p["tf_t"]), inch(p["tf_w"])
    tf_bot = table_h - tf_t
    panel_t = inch(p["panel_t"])
    panel_under = table_h - panel_t
    leg_r = inch(p["leg_dia"]) / 2
    ltx = table_l / 2 - inch(p["leg_setback_x"])
    lty = table_d / 2 - inch(p["leg_setback_y"])
    leg_tip_z = tf_bot + inch(0.5)          # legs embed 1/2" up into the frame
    foot_off = leg_tip_z * math.tan(splay)
    apron_t, apron_w = inch(p["apron_t"]), inch(p["apron_w"])
    spandrel_depth = inch(p["spandrel_depth"])
    la_half = table_l / 2 - inch(p["ap_end_inset"])
    sp_edge_gap = inch(p["sp_edge_gap"])
    shelf_z, sf_t = inch(p["shelf_z"]), inch(p["sf_t"])
    sp_panel_t = inch(p["sp_panel_t"])
    l2, d2 = table_l / 2, table_d / 2

    LEGC, FRAME, PANEL, APRON, SHELF = (
        "#7a4a28", "#b07a45", "#9c6b3f", "#a06a3c", "#8a5a30")
    m = Model("Ming table (平头案)", params=p, units="in")

    # ================= STOCK: legs (splayed, swept) ======================
    def leg(sx, sy):
        top = Vector(sx * ltx, sy * lty, leg_tip_z)
        foot = Vector(sx * (ltx + foot_off), sy * (lty + foot_off), 0.0)
        axis = top - foot
        return Solid.make_cylinder(
            leg_r, axis.length, Plane(origin=foot, z_dir=axis.normalized()))

    legs = {"Leg_FL": leg(-1, -1), "Leg_FR": leg(1, -1),
            "Leg_BL": leg(-1, 1), "Leg_BR": leg(1, 1)}
    legunion = fuse(list(legs.values()))

    def cope(s):
        return s - legunion

    # ================= TOP: 格角榫 frame + floating panel =================
    rail_f, rail_b, stile_l, stile_r = miter_tenon_frame(
        l2, d2, tf_w, tf_t, tf_bot)

    iw, ih = l2 - tf_w, d2 - tf_w
    top_panel = cope(tongue_panel(iw, ih, panel_under, table_h,
                                  tongue_ov=inch(0.25), tongue_w=panel_t / 2))

    # hollow spline molding wraps the frame's outer faces (the miters let
    # it run around the corners)
    mold_f = poly_prism([(-d2 + dy, tf_bot + dz) for dz, dy in MOLDING]
                        + [(-d2, tf_bot)], "x", -l2 - 1, (2 * (l2 + 1), 0, 0))
    mold_l = poly_prism([(-l2 + dy, tf_bot + dz) for dz, dy in MOLDING]
                        + [(-l2, tf_bot)], "y", -d2 - 1, (0, 2 * (d2 + 1), 0))
    molding = mold_f + mold_f.mirror(Plane.XZ) + mold_l + mold_l.mirror(Plane.YZ)

    rail_f = cope(rail_f) - molding - top_panel      # cope: round leg mortises
    rail_b = cope(rail_b) - molding - top_panel      # - panel: tongue grooves
    stile_l = cope(stile_l) - molding - top_panel
    stile_r = cope(stile_r) - molding - top_panel

    # 带 battens keep the wide top panel flat; the panel still slides
    bt_w, bt_h = inch(0.875), tf_t - panel_t
    batten_r = sliding_batten(inch(7.0), bt_w, panel_under - bt_h, panel_under,
                              ridge_narrow=inch(0.5), ridge_wide=inch(0.75),
                              ridge_depth=inch(0.1875), y_half=ih,
                              tenon_len=inch(0.6), tenon_h=bt_h * 2 / 3)
    batten_l = batten_r.mirror(Plane.YZ)
    battens = batten_r + batten_l
    top_panel = top_panel - battens                  # sliding dovetail grooves
    rail_f, rail_b = rail_f - battens, rail_b - battens   # tenon mortises

    # ================= APRON RING (leaning, dovetailed) ==================
    AT, AB = tf_bot, tf_bot - apron_w
    ATT = AT + 0.15               # overshoot; sheared flat after the lean
    SB = AB - spandrel_depth
    spo, spi = ltx + leg_r + sp_edge_gap, ltx - leg_r - sp_edge_gap
    LH = la_half
    bracket = [(-LH, ATT), (LH, ATT), (LH, AB), (spo, AB), (spo, SB),
               (spi, SB), (spi, AB), (-spi, AB), (-spi, SB), (-spo, SB),
               (-spo, AB), (-LH, AB)]
    cove_r = inch(0.75)
    apron_f = poly_prism(bracket, "y", -lty - apron_t / 2, (0, apron_t, 0),
                         fillets=[(i, cove_r) for i in (3, 6, 7, 10)]     # coves
                         + [(i, cove_r) for i in (4, 5, 8, 9)])           # feet

    # 闷齿斗角榫 at the ring corners: tails on the short aprons, sockets in
    # the long aprons, lip conceals everything
    X0, y0, y1 = -la_half, -lty - apron_t / 2, -lty + apron_t / 2
    Ys = lty + apron_t / 2
    tailsFL, cubeFL = full_blind_dovetail_corner(
        X0, y0, y1, AB, AT, apron_t,
        lip=inch(p["fbd_lip"]), pad=inch(p["fbd_pad"]),
        angle=math.radians(p["fbd_angle_deg"]),
        tail_w=inch(p["fbd_tail_w"]), n=int(p["fbd_tail_count"]))
    tailsFR, cubeFR = tailsFL.mirror(Plane.YZ), cubeFL.mirror(Plane.YZ)
    apron_f = apron_f - tailsFL - tailsFR            # dovetail sockets

    # the 1.5deg lean: rotate the whole front assembly rigidly about the
    # leg-top axis (dovetail pieces ride along -> fit preserved), then
    # shear the overshot top flat against the frame underside
    ax_f = Axis((0, -lty, leg_tip_z), (1, 0, 0))
    shear = box(-l2 - 2, l2 + 2, -d2 - 5, d2 + 5, tf_bot, tf_bot + 3)
    apron_f = apron_f.rotate(ax_f, -p["splay_deg"]) - shear
    tailsFL = tailsFL.rotate(ax_f, -p["splay_deg"])
    tailsFR = tailsFR.rotate(ax_f, -p["splay_deg"])
    cubeFL = cubeFL.rotate(ax_f, -p["splay_deg"])
    cubeFR = cubeFR.rotate(ax_f, -p["splay_deg"])
    apron_b = apron_f.mirror(Plane.XZ)
    tailsBL, tailsBR = tailsFL.mirror(Plane.XZ), tailsFR.mirror(Plane.XZ)
    cubeBL, cubeBR = cubeFL.mirror(Plane.XZ), cubeFR.mirror(Plane.XZ)

    # short aprons stay vertical; subtracting the LEANED corner blocks
    # gives them leaning end faces that mate the long aprons flush
    apron_l = (box(X0, X0 + apron_t, -Ys, Ys, AB, AT)
               - cubeFL - cubeBL + tailsFL + tailsBL)
    apron_r = (box(la_half - apron_t, la_half, -Ys, Ys, AB, AT)
               - cubeFR - cubeBR + tailsFR + tailsBR)

    # 夹头式: the legs are slotted so the band+spandrel sides pass through
    # whole — cutting the aprons on the legs would sever the band
    ring_fb = apron_f + apron_b
    for k in list(legs):
        legs[k] = leg_slot(legs[k], ring_fb)

    # ================= SHELF: frame, leg tenons, panel, 穿带 =============
    lxs = ltx + (leg_tip_z - (shelf_z - sf_t / 2)) * math.tan(splay)
    lys = lty + (leg_tip_z - (shelf_z - sf_t / 2)) * math.tan(splay)
    sz0, sz1 = shelf_z - sf_t, shelf_z
    sh_long_f = box(-lxs, lxs, -lys - leg_r, -lys + leg_r, sz0, sz1)
    sh_long_b = sh_long_f.mirror(Plane.XZ)
    sh_short_l = (box(-lxs - leg_r, -lxs + leg_r, -lys, lys, sz0, sz1)
                  - sh_long_f - sh_long_b)           # coped at the corners
    sh_short_r = sh_short_l.mirror(Plane.YZ)

    sf_cham = inch(0.3125)

    def cham_top(s, x=None, y=None):                 # edge profile, then cope
        return one_solid(chamfer(edges_at(s, x=x, y=y, z=sz1), sf_cham))

    sh_long_f = cope(cham_top(sh_long_f, y=-lys - leg_r))
    sh_long_b = cope(cham_top(sh_long_b, y=lys + leg_r))
    sh_short_l = cope(cham_top(sh_short_l, x=-lxs - leg_r))
    sh_short_r = cope(cham_top(sh_short_r, x=lxs + leg_r))

    # 圆包圆内榫: each corner's rail pair sends full-height tenons that
    # meet at 45deg INSIDE the round leg; the legs get exact mortises
    shelf_longs = {"F": sh_long_f, "B": sh_long_b}
    shelf_shorts = {"L": sh_short_l, "R": sh_short_r}
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        lk, sk_ = ("F" if sy < 0 else "B"), ("L" if sx < 0 else "R")
        key = "Leg_" + lk + sk_
        t_long, t_short = mitered_leg_tenons(
            sx * lxs, sy * lys, sx, sy, legs[key], sz0, sz1,
            tenon_w=inch(0.5), leg_r=leg_r)
        legs[key] = legs[key] - t_long - t_short
        shelf_longs[lk] = shelf_longs[lk] + t_long
        shelf_shorts[sk_] = shelf_shorts[sk_] + t_short
    sh_long_f, sh_long_b = shelf_longs["F"], shelf_longs["B"]
    sh_short_l, sh_short_r = shelf_shorts["L"], shelf_shorts["R"]

    # flush shelf panel + 穿带 batten holding it flat
    sh_panel = box(-(lxs - leg_r), lxs - leg_r, -(lys - leg_r), lys - leg_r,
                   sz1 - sp_panel_t, sz1)
    sh_batten = sliding_batten(0.0, inch(0.875), sz0, sz1 - sp_panel_t,
                               ridge_narrow=inch(0.5), ridge_wide=inch(0.75),
                               ridge_depth=inch(0.1875),
                               y_half=(lys - leg_r) + inch(0.5))
    sh_panel = sh_panel - sh_batten                  # sliding dovetail groove
    sh_long_f = sh_long_f - sh_batten                # housed ends
    sh_long_b = sh_long_b - sh_batten

    # ================= assembly =========================================
    parts = {
        "Leg_FL": (legs["Leg_FL"], LEGC), "Leg_FR": (legs["Leg_FR"], LEGC),
        "Leg_BL": (legs["Leg_BL"], LEGC), "Leg_BR": (legs["Leg_BR"], LEGC),
        "TF_Front": (rail_f, FRAME), "TF_Back": (rail_b, FRAME),
        "TF_Left": (stile_l, FRAME), "TF_Right": (stile_r, FRAME),
        "TopPanel": (top_panel, PANEL),
        "Batten_R": (batten_r, FRAME), "Batten_L": (batten_l, FRAME),
        "Apron_Front": (apron_f, APRON), "Apron_Back": (apron_b, APRON),
        "Apron_Left": (apron_l, APRON), "Apron_Right": (apron_r, APRON),
        "ShelfLong_F": (sh_long_f, SHELF), "ShelfLong_B": (sh_long_b, SHELF),
        "ShelfShort_L": (sh_short_l, SHELF), "ShelfShort_R": (sh_short_r, SHELF),
        "ShelfPanel": (cope(sh_panel), PANEL),
        "ShelfBatten": (sh_batten, SHELF),
    }
    comp = {"Leg": "Legs", "TF": "Top", "Top": "Top", "Batten": "Top",
            "Apron": "Aprons", "Shelf": "Shelf"}
    for name, (solid, col) in parts.items():
        m.add(name, solid, col, comp.get(name.split("_")[0], ""))
    return m


if __name__ == "__main__":
    run_cli(build, "out/ming_table")
