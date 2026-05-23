"""Frame-and-panel assembly template.

Builds a complete frame-and-panel: rails, stiles, optional dividers,
and floating panels with tongued edges in grooved frame members.

Uses mirrors and patterns for efficiency — build one piece, replicate.

Usage:
    from woodworking.templates import frame_and_panel as fp

    fp.define_params(params, prefix="fp",
        frame_w="1.25 in", frame_t="0.5625 in",
        groove_w="0.3125 in", groove_d="0.5 in",
        panel_t="0.4375 in", tongue_l="0.25 in")

    result = fp.build(comp, plane,
        origin=("0 in", "0 in", "0 in"),
        rail_axis="x", rail_len="12 in",
        stile_axis="z", stile_len="18 in",
        frame_t="fp_ft", frame_w="fp_fw",
        groove_w="fp_gw", groove_d="fp_gd",
        panel_t="fp_pt", tongue_l="fp_tl",
        prefix="FP", ev=ctx.ev)
"""

import adsk.core
import adsk.fusion

from helpers import sp

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation

METADATA = {
    "name": "frame_and_panel",
    "category": "sub-assembly",
    "variants": {
        "flat": {
            "description": "Flat panel floating in grooved frame",
            "best_for": ["cabinet doors", "chest lids", "side panels",
                         "table tops", "wainscoting"],
        },
    },
    "params": {
        "frame_w": "Frame member width (visible face dimension)",
        "frame_t": "Frame member thickness (extrusion depth)",
        "groove_w": "Groove/tongue width (shared by tenons and panel tongues)",
        "groove_d": "Groove depth (tenon length into mating rail)",
        "panel_t": "Panel total thickness (tongue + field)",
        "tongue_l": "Panel tongue protrusion length",
    },
}


def define_params(params, prefix="fp",
                  frame_w="1.25 in", frame_t="0.5625 in",
                  groove_w="0.3125 in", groove_d="0.5 in",
                  panel_t="0.4375 in", tongue_l="0.25 in"):
    VI = adsk.core.ValueInput.createByString
    p = prefix
    defs = [
        (f"{p}_fw", frame_w, "Frame member width"),
        (f"{p}_ft", frame_t, "Frame thickness"),
        (f"{p}_gw", groove_w, "Groove / tongue width"),
        (f"{p}_gd", groove_d, "Groove depth"),
        (f"{p}_pt", panel_t, "Panel thickness"),
        (f"{p}_tl", tongue_l, "Panel tongue length"),
    ]
    for name, val, comment in defs:
        existing = params.itemByName(name)
        if existing:
            existing.expression = val
        else:
            params.add(name, VI(val), "in", comment)
    return {
        "fw": f"{p}_fw", "ft": f"{p}_ft",
        "gw": f"{p}_gw", "gd": f"{p}_gd",
        "pt": f"{p}_pt", "tl": f"{p}_tl",
    }


def _axis_index(axis):
    return {"x": 0, "y": 1, "z": 2}[axis]


def _third_axis(a, b):
    return ({"x", "y", "z"} - {a, b}).pop()


def _make_origin(R, S, E, r_val, s_val, e_val):
    m = {R: r_val, S: s_val, E: e_val}
    return (m["x"], m["y"], m["z"])


def _make_size(a1, e1, a2, e2):
    return {a1: e1, a2: e2}


def _miter_corner(comp, base_plane, ext_axis,
                  v_outer, v_stile, v_inner,
                  frame_t, rail_body, stile_body,
                  name, ev):
    P = adsk.core.Point3D
    sk = comp.sketches.add(base_plane)
    sk.name = f"{name}_Sk"
    m2s = sk.modelToSketchSpace

    p1 = m2s(P.create(ev(v_outer[0]), ev(v_outer[1]), ev(v_outer[2])))
    p2 = m2s(P.create(ev(v_stile[0]), ev(v_stile[1]), ev(v_stile[2])))
    p3 = m2s(P.create(ev(v_inner[0]), ev(v_inner[1]), ev(v_inner[2])))

    lines = sk.sketchCurves.sketchLines
    l1 = lines.addByTwoPoints(
        P.create(p1.x, p1.y, 0), P.create(p2.x, p2.y, 0))
    l2 = lines.addByTwoPoints(
        l1.endSketchPoint, P.create(p3.x, p3.y, 0))
    lines.addByTwoPoints(l2.endSketchPoint, l1.startSketchPoint)

    prof = sp.smallest_profile(sk)
    tri_ext = sp.ext_new(comp, prof, frame_t, f"{name}_Tri")
    tri_body = tri_ext.bodies.item(0)

    sp.combine(rail_body, tri_body, CUT, True, f"{name}_RailCut")
    sp.combine(stile_body, tri_body, JOIN, False, f"{name}_StileJoin")


def build(comp, base_plane, origin,
          rail_axis, rail_len,
          stile_axis, stile_len,
          frame_t, frame_w,
          groove_w, groove_d,
          panel_t, tongue_l,
          div_along_stile=0,
          div_along_rail=0,
          corner_joint="stub_tenon",
          panel_position="centered",
          tenon_depth=None,
          tenon_shoulder=None,
          prefix="FP", ev=None):
    """Build a frame-and-panel assembly using mirrors for efficiency.

    Args:
        comp: Target component.
        base_plane: Construction plane for the frame's outer face.
        origin: (x_expr, y_expr, z_expr) — ext-axis component must be "0 in".
        rail_axis: Model axis rails run along ("x", "y", or "z").
        rail_len: Overall length along rail axis.
        stile_axis: Model axis stiles run along.
        stile_len: Overall length along stile axis.
        frame_t, frame_w: Frame thickness and member width.
        groove_w, groove_d: Groove/tongue width and depth (for panel).
        panel_t: Panel total thickness.
        tongue_l: Panel tongue protrusion.
        div_along_stile: Vertical dividers (parallel to stiles).
        div_along_rail: Horizontal dividers (parallel to rails).
        corner_joint: "stub_tenon" or "mitered_mt".
        panel_position: "centered" or "flush_outer" (Chinese style).
        tenon_depth: Stile tenon depth into rail. Defaults to frame_w*2/3.
        prefix: Name prefix.
        ev: Evaluator function.
    """
    if ev is None:
        ev = sp._make_ev()
    if tenon_depth is None:
        tenon_depth = f"({frame_w}) * 2 / 3"
    if tenon_shoulder is None:
        tenon_shoulder = tongue_l

    R, S, E = rail_axis, stile_axis, _third_axis(rail_axis, stile_axis)
    o_r = origin[_axis_index(R)]
    o_s = origin[_axis_index(S)]
    o_e = origin[_axis_index(E)]

    def _o(r, s, e):
        return _make_origin(R, S, E, r, s, e)

    def _sz(a1, e1, a2, e2):
        return _make_size(a1, e1, a2, e2)

    n_v = div_along_stile
    n_h = div_along_rail

    # ── Midplanes for mirror ──────────────────────────────────────
    # Perpendicular to each axis for correct mirror direction
    perp_base = {
        "x": comp.yZConstructionPlane,
        "y": comp.xZConstructionPlane,
        "z": comp.xYConstructionPlane,
    }
    r_mid = sp.off_plane(comp, perp_base[R],
                         f"({o_r}) + ({rail_len}) / 2", f"{prefix}_RMid")
    s_mid = sp.off_plane(comp, perp_base[S],
                         f"({o_s}) + ({stile_len}) / 2", f"{prefix}_SMid")

    # ── Groove plane ──────────────────────────────────────────────
    if panel_position == "flush_outer":
        groove_e = f"({frame_t}) - ({groove_w})"
    else:
        groove_e = f"({frame_t} - {groove_w}) / 2"
    groove_plane = sp.off_plane(comp, base_plane, groove_e, f"{prefix}_GPl")

    # ── Rail_Bot → mirror → Rail_Top ─────────────────────────────
    sk, prof = sp.sketch_rect_model(
        comp, base_plane,
        _o(o_r, o_s, o_e),
        _sz(R, rail_len, S, frame_w),
        f"{prefix}_RBot_Sk", ev=ev)
    r_bot_ext = sp.ext_new(comp, prof, frame_t, f"{prefix}_RBot")
    r_bot = r_bot_ext.bodies.item(0)
    r_bot.name = f"{prefix}_Rail_Bot"

    r_top = sp.mirror_body(comp, r_bot, s_mid,
                           f"{prefix}_RTop_M").bodies.item(0)
    r_top.name = f"{prefix}_Rail_Top"
    rails = [r_bot, r_top]

    # ── Stile_L: build one end → mirror to other → mirror whole piece ──
    # No explicit groove — panel CUT creates it ("if it fits, it cuts").
    # Tenon sketched on end face so it follows the piece.
    # Tenon cross-section on the stile end face:
    #   OUTER ─┤ shoulder ├── TENON ──┤ tongue_l ├─ INNER
    #          └ tongue   ┘           (panel groove area)
    stile_inner = f"{stile_len} - 2 * {frame_w}"
    sk, prof = sp.sketch_rect_model(
        comp, base_plane,
        _o(o_r, f"{o_s} + {frame_w}", o_e),
        _sz(R, frame_w, S, stile_inner),
        f"{prefix}_SL_Sk", ev=ev)
    s_left_ext = sp.ext_new(comp, prof, frame_t, f"{prefix}_SL")
    s_left = s_left_ext.bodies.item(0)
    s_left.name = f"{prefix}_Stile_L"

    # Build tenon + outer tongue on the BOTTOM end face only
    bot_face = sp.find_face(s_left, S, -1)
    bot_s = f"{o_s} + {frame_w}"

    # Tenon — shouldered from both edges
    sk, _p = sp.sketch_rect_model(
        comp, bot_face,
        _o(f"({o_r}) + ({tenon_shoulder})", bot_s, groove_e),
        _sz(R, f"{frame_w} - {tenon_shoulder} - {tongue_l}", E, groove_w),
        f"{prefix}_SL_T_Sk", ev=ev)
    prof = sp.smallest_profile(sk)
    tenon_ext = sp.ext_new(comp, prof, tenon_depth, f"{prefix}_SL_T")

    # Outer-edge tongue — fills rail groove at frame perimeter
    sk, _p = sp.sketch_rect_model(
        comp, bot_face,
        _o(o_r, bot_s, groove_e),
        _sz(R, tenon_shoulder, E, groove_w),
        f"{prefix}_SL_Tg_Sk", ev=ev)
    prof = sp.smallest_profile(sk)
    tongue_ext = sp.ext_new(comp, prof, tongue_l, f"{prefix}_SL_Tg")

    # JOIN both into stile
    sp.combine(s_left, [tenon_ext.bodies.item(0), tongue_ext.bodies.item(0)],
               JOIN, False, f"{prefix}_SL_J")

    # Mirror tenon+tongue to the other end via stile midplane
    stile_s_mid = sp.off_plane(comp, perp_base[S],
        f"({o_s}) + ({stile_len}) / 2", f"{prefix}_SL_SMid")
    mir_feat = sp.mirror_body(comp, s_left, stile_s_mid, f"{prefix}_SL_EndM")
    mir_body = mir_feat.bodies.item(0)
    sp.combine(s_left, mir_body, JOIN, False, f"{prefix}_SL_EndMJ")

    # Mirror whole Stile_L → Stile_R
    s_right = sp.mirror_body(comp, s_left, r_mid,
                             f"{prefix}_SR_M").bodies.item(0)
    s_right.name = f"{prefix}_Stile_R"
    stiles = [s_left, s_right]

    # CUT stiles into rails (bulk — both stiles per rail)
    for rail in rails:
        sp.combine(rail, stiles, CUT, True,
                   f"{prefix}_{rail.name}_Mort")

    # ── Vertical dividers ─────────────────────────────────────────
    dividers_v = []
    if n_v > 0:
        inner_rail = f"{rail_len} - 2 * {frame_w}"
        for i in range(n_v):
            bay_w = f"({inner_rail}) / {n_v + 1}"
            div_r = f"{o_r} + {frame_w} + ({bay_w}) * {i + 1} - {frame_w} / 2"

            # Divider body (no explicit grooves — panel CUT creates them)
            sk, prof = sp.sketch_rect_model(
                comp, base_plane,
                _o(div_r, f"{o_s} + {frame_w}", o_e),
                _sz(R, frame_w, S, stile_inner),
                f"{prefix}_DV{i}_Sk", ev=ev)
            dv_ext = sp.ext_new(comp, prof, frame_t, f"{prefix}_DV{i}")
            dv = dv_ext.bodies.item(0)
            dv.name = f"{prefix}_Div_V{i}"

            # Bot face: tenon + left tongue, mirror R → right, mirror S → top
            bot_face = sp.find_face(dv, S, -1)
            bot_s = f"{o_s} + {frame_w}"

            # Divider R-midplane for tongue mirror
            dv_r_mid = sp.off_plane(comp, perp_base[R],
                f"({div_r}) + ({frame_w}) / 2", f"{prefix}_DV{i}_RMid")

            # Tenon on bot face
            sk, _p = sp.sketch_rect_model(
                comp, bot_face,
                _o(f"({div_r}) + {tongue_l}", bot_s, groove_e),
                _sz(R, f"{frame_w} - 2 * {tongue_l}", E, groove_w),
                f"{prefix}_DV{i}_TBot_Sk", ev=ev)
            prof = sp.smallest_profile(sk)
            t_bot = sp.ext_new(comp, prof, tenon_depth,
                               f"{prefix}_DV{i}_TBot")

            # Left tongue on bot face
            sk, _p = sp.sketch_rect_model(
                comp, bot_face,
                _o(div_r, bot_s, groove_e),
                _sz(R, tongue_l, E, groove_w),
                f"{prefix}_DV{i}_TgLBot_Sk", ev=ev)
            prof = sp.smallest_profile(sk)
            tgL_bot = sp.ext_new(comp, prof, tongue_l,
                                  f"{prefix}_DV{i}_TgLBot")

            # Mirror left tongue → right tongue
            tgR_mir = sp.mirror_body(comp, tgL_bot.bodies.item(0),
                dv_r_mid, f"{prefix}_DV{i}_TgRBotM")

            # Mirror all bot features → top end
            top_mir = sp.mirror_feats(comp, [t_bot, tgL_bot, tgR_mir],
                s_mid, f"{prefix}_DV{i}_TopM")

            # JOIN all to divider
            dv_join = [t_bot.bodies.item(0), tgL_bot.bodies.item(0),
                       tgR_mir.bodies.item(0)]
            for j in range(top_mir.bodies.count):
                dv_join.append(top_mir.bodies.item(j))
            sp.combine(dv, dv_join, JOIN, False, f"{prefix}_DV{i}_AllJ")

            # CUT divider into rails
            for rail in rails:
                sp.combine(rail, dv, CUT, True,
                           f"{prefix}_{rail.name}_{dv.name}_Mort")
            dividers_v.append(dv)

    # ── Horizontal dividers (segmented between vertical members) ──
    dividers_h = []
    if n_h > 0:
        inner_stile = f"{stile_len} - 2 * {frame_w}"
        v_left_edges = [f"{o_r} + {frame_w}"]
        v_right_edges = [f"{o_r} + {rail_len} - {frame_w}"]
        if n_v > 0:
            inner_rail_v = f"{rail_len} - 2 * {frame_w}"
            for vi in range(n_v):
                bay_v = f"({inner_rail_v}) / {n_v + 1}"
                dv_l = f"{o_r} + {frame_w} + ({bay_v}) * {vi + 1} - {frame_w} / 2"
                dv_r = f"{o_r} + {frame_w} + ({bay_v}) * {vi + 1} + {frame_w} / 2"
                v_right_edges.insert(-1, dv_l)
                v_left_edges.insert(len(v_left_edges), dv_r)

        n_segs = n_v + 1
        for i in range(n_h):
            bay_h = f"({inner_stile}) / {n_h + 1}"
            div_s = f"{o_s} + {frame_w} + ({bay_h}) * {i + 1} - {frame_w} / 2"
            for seg in range(n_segs):
                seg_l = v_left_edges[seg]
                seg_r = v_right_edges[seg]
                seg_w = f"({seg_r}) - ({seg_l})"
                lbl = f"DH{i}S{seg}"

                sk, prof = sp.sketch_rect_model(
                    comp, base_plane,
                    _o(seg_l, div_s, o_e),
                    _sz(R, seg_w, S, frame_w),
                    f"{prefix}_{lbl}_Sk", ev=ev)
                dh_ext = sp.ext_new(comp, prof, frame_t, f"{prefix}_{lbl}")
                dh = dh_ext.bodies.item(0)
                dh.name = f"{prefix}_Div_H{i}_S{seg}"

                # Left tenon, mirror → right tenon
                sk, prof = sp.sketch_rect_model(
                    comp, groove_plane,
                    _o(f"({seg_l}) - ({groove_d})", div_s, groove_e),
                    _sz(R, groove_d, S, frame_w),
                    f"{prefix}_{lbl}_TL_Sk", ev=ev)
                tL = sp.ext_new(comp, prof, groove_w,
                                f"{prefix}_{lbl}_TL")
                seg_r_mid = sp.off_plane(comp, perp_base[R],
                    f"({seg_l}) + ({seg_w}) / 2",
                    f"{prefix}_{lbl}_RMid")
                tR_mir = sp.mirror_body(comp, tL.bodies.item(0),
                    seg_r_mid, f"{prefix}_{lbl}_TRM")
                sp.combine(dh, [tL.bodies.item(0), tR_mir.bodies.item(0)],
                           JOIN, False, f"{prefix}_{lbl}_TJ")

                for fb in rails + stiles + dividers_v:
                    sp.combine(fb, dh, CUT, True,
                               f"{prefix}_{fb.name}_{dh.name}_Mort")
                dividers_h.append(dh)

    # ── Panel(s) ──────────────────────────────────────────────────
    # Panel position along ext axis
    if panel_position == "flush_outer":
        panel_e = f"({frame_t}) - ({panel_t})"
    else:
        panel_e = f"({frame_t} - {panel_t}) / 2"
    panel_plane = sp.off_plane(comp, base_plane, panel_e, f"{prefix}_PPl")

    n_cols = n_v + 1
    n_rows = n_h + 1
    inner_rail_expr = f"{rail_len} - 2 * {frame_w}"
    inner_stile_expr = f"{stile_len} - 2 * {frame_w}"

    panels = []
    all_panels = []
    all_panel_positions = []

    for col in range(n_cols):
        col_panels = []
        if n_v == 0:
            col_start_r = f"{o_r} + {frame_w} - {tongue_l}"
            col_w = f"{inner_rail_expr} + 2 * {tongue_l}"
        else:
            bay_w = f"({inner_rail_expr}) / {n_cols}"
            if col == 0:
                col_start_r = f"{o_r} + {frame_w} - {tongue_l}"
                col_w = f"{bay_w} - {frame_w} / 2 + {tongue_l}"
            elif col == n_cols - 1:
                col_start_r = (f"{o_r} + {frame_w} + ({bay_w}) * {col}"
                               f" + {frame_w} / 2 - {tongue_l}")
                col_w = f"{bay_w} - {frame_w} / 2 + {tongue_l}"
            else:
                col_start_r = (f"{o_r} + {frame_w} + ({bay_w}) * {col}"
                               f" + {frame_w} / 2 - {tongue_l}")
                col_w = f"{bay_w} - {frame_w} + 2 * {tongue_l}"

        for row in range(n_rows):
            if n_h == 0:
                row_start_s = f"{o_s} + {frame_w} - {tongue_l}"
                row_h = f"{inner_stile_expr} + 2 * {tongue_l}"
            else:
                bay_h = f"({inner_stile_expr}) / {n_rows}"
                if row == 0:
                    row_start_s = f"{o_s} + {frame_w} - {tongue_l}"
                    row_h = f"{bay_h} - {frame_w} / 2 + {tongue_l}"
                elif row == n_rows - 1:
                    row_start_s = (f"{o_s} + {frame_w} + ({bay_h}) * {row}"
                                   f" + {frame_w} / 2 - {tongue_l}")
                    row_h = f"{bay_h} - {frame_w} / 2 + {tongue_l}"
                else:
                    row_start_s = (f"{o_s} + {frame_w} + ({bay_h}) * {row}"
                                   f" + {frame_w} / 2 - {tongue_l}")
                    row_h = f"{bay_h} - {frame_w} + 2 * {tongue_l}"

            # Check if this panel can be produced by mirroring an earlier one
            mirror_src = None
            mirror_plane = None
            if n_v > 0 and col == n_cols - 1 and col == 1 and n_cols == 2:
                # 2-column: mirror col 0 across rail midplane
                if row < len(panels[0]):
                    mirror_src = panels[0][row]
                    mirror_plane = r_mid

            pname = f"{prefix}_P{col}{row}"

            if mirror_src is not None:
                panel = sp.mirror_body(comp, mirror_src, mirror_plane,
                                       f"{pname}_M").bodies.item(0)
                panel.name = f"{prefix}_Panel_{col}_{row}"
            else:
                # Field body (without tongue extensions)
                field_start_r = f"({col_start_r}) + ({tongue_l})"
                field_start_s = f"({row_start_s}) + ({tongue_l})"
                field_w = f"({col_w}) - 2 * ({tongue_l})"
                field_h = f"({row_h}) - 2 * ({tongue_l})"

                sk, prof = sp.sketch_rect_model(
                    comp, panel_plane,
                    _o(field_start_r, field_start_s, panel_e),
                    _sz(R, field_w, S, field_h),
                    f"{pname}_Sk", ev=ev)
                p_ext = sp.ext_new(comp, prof, panel_t, pname)
                panel = p_ext.bodies.item(0)
                panel.name = f"{prefix}_Panel_{col}_{row}"

                # Bottom tongue — thin extrusion on bottom face
                bot_face = sp.find_face(panel, S, -1)
                sk, _p = sp.sketch_rect_model(
                    comp, bot_face,
                    _o(field_start_r, field_start_s, groove_e),
                    _sz(R, field_w, E, groove_w),
                    f"{pname}_TgBot_Sk", ev=ev)
                prof = sp.smallest_profile(sk)
                tg_bot = sp.ext_new(comp, prof, tongue_l,
                                    f"{pname}_TgBot")
                tg_bot_body = tg_bot.bodies.item(0)

                # Mirror bottom → top (reuse frame midplane for single panels)
                if n_v == 0 and n_h == 0:
                    p_s_mid = s_mid
                else:
                    p_s_mid = sp.off_plane(comp, perp_base[S],
                        f"({row_start_s}) + ({row_h}) / 2",
                        f"{pname}_SMid")
                tg_top_body = sp.mirror_body(
                    comp, tg_bot_body, p_s_mid,
                    f"{pname}_TgTopM").bodies.item(0)

                # Left tongue — thin extrusion on left face
                left_face = sp.find_face(panel, R, -1)
                sk, _p = sp.sketch_rect_model(
                    comp, left_face,
                    _o(field_start_r, field_start_s, groove_e),
                    _sz(S, field_h, E, groove_w),
                    f"{pname}_TgL_Sk", ev=ev)
                prof = sp.smallest_profile(sk)
                tg_left = sp.ext_new(comp, prof, tongue_l,
                                     f"{pname}_TgL")
                tg_left_body = tg_left.bodies.item(0)

                # Mirror left → right (reuse frame midplane for single panels)
                if n_v == 0 and n_h == 0:
                    p_r_mid = r_mid
                else:
                    p_r_mid = sp.off_plane(comp, perp_base[R],
                        f"({col_start_r}) + ({col_w}) / 2",
                        f"{pname}_RMid")
                tg_right_body = sp.mirror_body(
                    comp, tg_left_body, p_r_mid,
                    f"{pname}_TgRM").bodies.item(0)

                # JOIN all tongues to panel field
                sp.combine(panel,
                           [tg_bot_body, tg_top_body,
                            tg_left_body, tg_right_body],
                           JOIN, False, f"{pname}_TgJ")

            col_panels.append(panel)
            all_panels.append(panel)
            all_panel_positions.append((col_start_r, row_start_s,
                                        col_w, row_h))
        panels.append(col_panels)

    # ── Panel CUTs into frame members ─────────────────────────────
    all_frame = rails + stiles + dividers_v + dividers_h
    for fb in all_frame:
        sp.combine(fb, all_panels, CUT, True,
                   f"{prefix}_{fb.name}_PanelGroove")

    # ── Mitered corners (格角榫) ─────────────────────────────────
    if corner_joint == "mitered_mt":
        r_bot, r_top = rails[0], rails[1]
        s_left, s_right = stiles[0], stiles[1]

        _miter_corner(comp, base_plane, E,
            _o(o_r, o_s, o_e),
            _o(o_r, f"{o_s} + {frame_w}", o_e),
            _o(f"{o_r} + {frame_w}", f"{o_s} + {frame_w}", o_e),
            frame_t, r_bot, s_left, f"{prefix}_MBL", ev)

        _miter_corner(comp, base_plane, E,
            _o(f"{o_r} + {rail_len}", o_s, o_e),
            _o(f"{o_r} + {rail_len}", f"{o_s} + {frame_w}", o_e),
            _o(f"{o_r} + {rail_len} - {frame_w}",
               f"{o_s} + {frame_w}", o_e),
            frame_t, r_bot, s_right, f"{prefix}_MBR", ev)

        _miter_corner(comp, base_plane, E,
            _o(o_r, f"{o_s} + {stile_len}", o_e),
            _o(o_r, f"{o_s} + {stile_len} - {frame_w}", o_e),
            _o(f"{o_r} + {frame_w}",
               f"{o_s} + {stile_len} - {frame_w}", o_e),
            frame_t, r_top, s_left, f"{prefix}_MTL", ev)

        _miter_corner(comp, base_plane, E,
            _o(f"{o_r} + {rail_len}",
               f"{o_s} + {stile_len}", o_e),
            _o(f"{o_r} + {rail_len}",
               f"{o_s} + {stile_len} - {frame_w}", o_e),
            _o(f"{o_r} + {rail_len} - {frame_w}",
               f"{o_s} + {stile_len} - {frame_w}", o_e),
            frame_t, r_top, s_right, f"{prefix}_MTR", ev)

        for stile in stiles:
            sp.combine(stile, all_panels, CUT, True,
                       f"{prefix}_{stile.name}_MiterGroove")

    all_bodies = rails + stiles + dividers_v + dividers_h + all_panels

    return {
        "rails": rails,
        "stiles": stiles,
        "dividers_v": dividers_v,
        "dividers_h": dividers_h,
        "panels": panels,
        "panel_positions": all_panel_positions,
        "all_bodies": all_bodies,
    }


def add_battens(comp, panel_body, base_plane,
                rail_axis, stile_axis,
                rail_len, stile_len,
                frame_w, frame_t, panel_t,
                groove_d,
                count=2,
                batten_w="1 in",
                slot_depth_ratio="0.4",
                dovetail_angle_deg=12,
                flush_bottom=False,
                panel_position="centered",
                prefix="BT", ev=None):
    """Add sliding dovetail battens (穿带) to a panel underside.

    When flush_bottom=True, the batten extends from the frame bottom
    (base_plane) up into the panel — batten bottom flush with frame bottom.
    """
    if ev is None:
        ev = sp._make_ev()

    ext_axis = _third_axis(rail_axis, stile_axis)
    R, S, E = rail_axis, stile_axis, ext_axis

    def _o(r, s, e):
        return _make_origin(R, S, E, r, s, e)
    def _sz(a1, e1, a2, e2):
        return _make_size(a1, e1, a2, e2)

    slot_depth = f"({panel_t}) * ({slot_depth_ratio})"

    if flush_bottom:
        # Batten from frame bottom up into panel
        batten_base_e = "0 in"
        if panel_position == "flush_outer":
            batten_height = f"({frame_t}) - ({panel_t}) + ({slot_depth})"
        else:
            batten_height = f"({frame_t} - {panel_t}) / 2 + ({slot_depth})"
    else:
        if panel_position == "flush_outer":
            batten_base_e = f"({frame_t}) - ({panel_t})"
        else:
            batten_base_e = f"({frame_t} - {panel_t}) / 2"
        batten_height = slot_depth

    batten_plane = sp.off_plane(comp, base_plane, batten_base_e,
                                f"{prefix}_BasePl")
    batten_len = f"{stile_len} - 2 * {frame_w}"
    inner_rail = f"{rail_len} - 2 * {frame_w}"

    battens = []
    for i in range(count):
        spacing = f"({inner_rail}) / {count + 1}"
        center_r = f"{frame_w} + ({spacing}) * {i + 1}"
        start_r = f"({center_r}) - ({batten_w}) / 2"

        bname = f"{prefix}_{i}"
        sk, prof = sp.sketch_rect_model(
            comp, batten_plane,
            _o(start_r, f"{frame_w}", batten_base_e),
            _sz(R, batten_w, S, batten_len),
            f"{bname}_Sk", ev=ev)
        bt_ext = sp.ext_new(comp, prof, batten_height, bname)
        bt = bt_ext.bodies.item(0)
        bt.name = f"{prefix}_Batten_{i}"

        # Dovetail chamfer on the face closest to the panel surface.
        # When flush_bottom: top face (inside panel groove).
        # When not: bottom face (at panel surface = narrow opening).
        if flush_bottom:
            dt_face = sp.find_face(bt, ext_axis, +1)
        else:
            dt_face = sp.find_face(bt, ext_axis, -1)
            if dt_face is None:
                dt_face = sp.find_face(bt, ext_axis, +1)

        dt_edges = adsk.core.ObjectCollection.create()
        s_idx = _axis_index(stile_axis)
        for j in range(dt_face.edges.count):
            edge = dt_face.edges.item(j)
            sp1 = edge.startVertex.geometry
            sp2 = edge.endVertex.geometry
            delta = [sp2.x - sp1.x, sp2.y - sp1.y, sp2.z - sp1.z]
            length = sum(d * d for d in delta) ** 0.5
            if length > 0.01 and abs(delta[s_idx]) / length > 0.9:
                dt_edges.add(edge)

        if dt_edges.count == 2:
            ch_input = comp.features.chamferFeatures.createInput2()
            d1 = adsk.core.ValueInput.createByString(
                f"({slot_depth}) * tan({dovetail_angle_deg} * 1 deg)")
            d2 = adsk.core.ValueInput.createByString(slot_depth)
            ch_input.chamferEdgeSets.addTwoDistancesChamferEdgeSet(
                dt_edges, d1, d2, False, False)
            comp.features.chamferFeatures.add(ch_input)

        sp.combine(panel_body, bt, CUT, True, f"{bname}_Groove")
        battens.append(bt)

    return battens


def add_raised_bevel(comp, panel_bodies, panel_positions,
                     rail_axis, stile_axis,
                     frame_t, panel_t, groove_w, tongue_l,
                     bevel_width="1.5 in",
                     prefix="Bev", ev=None):
    """Add raised bevel profile via triangular wedge CUTs on the outer face."""
    if ev is None:
        ev = sp._make_ev()

    ext_axis = _third_axis(rail_axis, stile_axis)
    R, S, E = rail_axis, stile_axis, ext_axis

    field_outer = f"({frame_t} + {panel_t}) / 2"
    tongue_outer = f"({frame_t} + {groove_w}) / 2"
    P = adsk.core.Point3D

    perp_base = {
        "x": comp.yZConstructionPlane,
        "y": comp.xZConstructionPlane,
        "z": comp.xYConstructionPlane,
    }

    for pi, (panel, pos) in enumerate(zip(panel_bodies, panel_positions)):
        col_start_r, row_start_s, col_w, row_h = pos
        pn = f"{prefix}_{pi}"

        edges_info = [
            ("Bot", R, col_w, perp_base[R], col_start_r,
             f"{row_start_s} + {tongue_l} + {bevel_width}",
             f"{row_start_s} + {tongue_l}"),
            ("Top", R, col_w, perp_base[R], col_start_r,
             f"{row_start_s} + {row_h} - {tongue_l} - {bevel_width}",
             f"{row_start_s} + {row_h} - {tongue_l}"),
            ("L", S, row_h, perp_base[S], row_start_s,
             f"{col_start_r} + {tongue_l} + {bevel_width}",
             f"{col_start_r} + {tongue_l}"),
            ("R", S, row_h, perp_base[S], row_start_s,
             f"{col_start_r} + {col_w} - {tongue_l} - {bevel_width}",
             f"{col_start_r} + {col_w} - {tongue_l}"),
        ]

        for label, edge_ax, ext_len, cp_base, cp_off, p_inner, p_step in edges_info:
            wname = f"{pn}_{label}"
            cross_pl = sp.off_plane(comp, cp_base, cp_off, f"{wname}_CrPl")
            perp_ax = S if edge_ax == R else R

            def _pt3(perp_val, ext_val):
                m = {edge_ax: ev(cp_off),
                     perp_ax: ev(perp_val),
                     ext_axis: ev(ext_val)}
                return P.create(m["x"], m["y"], m["z"])

            sk = comp.sketches.add(cross_pl)
            sk.name = f"{wname}_Sk"
            m2s = sk.modelToSketchSpace
            sp1 = m2s(_pt3(p_inner, field_outer))
            sp2 = m2s(_pt3(p_step, field_outer))
            sp3 = m2s(_pt3(p_step, tongue_outer))

            lines = sk.sketchCurves.sketchLines
            l1 = lines.addByTwoPoints(
                P.create(sp1.x, sp1.y, 0), P.create(sp2.x, sp2.y, 0))
            l2 = lines.addByTwoPoints(
                l1.endSketchPoint, P.create(sp3.x, sp3.y, 0))
            lines.addByTwoPoints(l2.endSketchPoint, l1.startSketchPoint)

            prof = sp.smallest_profile(sk)
            w_ext = sp.ext_new(comp, prof, ext_len, wname)
            sp.combine(panel, w_ext.bodies.item(0), CUT, False,
                       f"{wname}_Cut")

    return panel_bodies
