"""Test fixture for the splayed (compound-angle) dovetail template.

Gallery layout — each splayed box is built centered on its component
origin (the template's v1 requirement) and placed on a grid via its
occurrence transform, like the rotated fixtures in
``test_template_dovetail.py``.

  S1 @ (0,0):  baseline midou geometry 30/21/17 cm, t=1.2, 6 tails
  S2 @ (0,1):  shallow splay 20/16/12 (9.5°), 4 tails,
               caller-supplied tilt/thick_h params (tilt_expr path)
  S3 @ (1,0):  steep splay 36/20/15 (28.1°), thick stock 1.5, 5 tails
  S4 @ (1,1):  thin stock 0.8, many tails (9), 28/22/16 (10.6°)
  S5 @ (2,0):  recompute fixture — build 30/21/17, then live edits
               (top_w 30→25, box_h 17→20, restore) with re-checks

Each fixture relies on the template's built-in self-checks (fully
constrained sketches, vertex-drift raises, analytic sweep-volume
checks, ghost-body count check) and adds:
  - body count == 4
  - tail-board + pin-board volume invariant (joinery only TRANSFERS
    material between the pair, so F+L volume is analytic)
  - single lump per board after the joins
"""
import importlib
import math
import sys

import adsk.core
import adsk.fusion


def _expected_pair_volume(ev, top, bot, h, t, tilt_rad):
    """Analytic Front+Left volume (joinery transfer cancels out)."""
    cosT = math.cos(tilt_rad)
    btw = ev(t) / cosT
    slant = ev(h) / cosT
    tail_board = ((ev(bot) - 2 * btw) + (ev(top) - 2 * btw)) / 2 \
        * slant * ev(t)
    pin_board = (ev(bot) + ev(top)) / 2 * slant * ev(t)
    return tail_board + pin_board


def _check_fixture(ctx, sdt, comp, cfg, params, label):
    """Shared post-build assertions for one splayed box."""
    tilt_rad = params.itemByName(cfg["tilt"]).value
    exp_pair = _expected_pair_volume(
        ctx.ev, cfg["top_w"], cfg["bot_w"], cfg["height"], cfg["thick"],
        tilt_rad)
    bodies = {comp.bRepBodies.item(i).name: comp.bRepBodies.item(i)
              for i in range(comp.bRepBodies.count)}
    assert comp.bRepBodies.count == 4, \
        f"{label}: expected 4 bodies, got {comp.bRepBodies.count}"
    got_pair = bodies["Front"].volume + bodies["Left"].volume
    assert abs(got_pair - exp_pair) <= 0.02 * exp_pair, \
        f"{label}: F+L volume {got_pair:.1f}, expected {exp_pair:.1f}"
    for nm in ("Front", "Back", "Left", "Right"):
        assert bodies[nm].lumps.count == 1, \
            f"{label}: {nm} has {bodies[nm].lumps.count} lumps"
    # symmetry: mirrored boards match their templates
    assert abs(bodies["Front"].volume - bodies["Back"].volume) < 0.01
    assert abs(bodies["Left"].volume - bodies["Right"].volume) < 0.01
    print(f"  {label}: PASS (F={bodies['Front'].volume:.1f} "
          f"L={bodies['Left'].volume:.1f} pair={got_pair:.1f} "
          f"exp={exp_pair:.1f}, tilt={math.degrees(tilt_rad):.1f} deg)")


def run(context):
    # Evict cached modules — Fusion keeps Python modules hot across runs.
    for _mod in list(sys.modules):
        if _mod.startswith("woodworking") or _mod.startswith("helpers"):
            del sys.modules[_mod]

    from helpers import sp
    import woodworking.templates.splayed_dovetail as sdt
    importlib.reload(sdt)

    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    ctx = sp.DesignContext(design)

    # drop lingering params from earlier runs
    for _ in range(6):
        progress = False
        for i in range(params.count - 1, -1, -1):
            if params.item(i).deleteMe():
                progress = True
        if not progress:
            break

    def _add(name, expr):
        if not params.itemByName(name):
            params.add(name, VI(expr), "cm", "")

    _add("grid", "60 cm")
    grid_cm = ctx.ev("grid")

    def make_slot_comp(prefix, col, row):
        xf = adsk.core.Matrix3D.create()
        xf.setCell(0, 3, col * grid_cm)
        xf.setCell(1, 3, row * grid_cm)
        return sp.make_comp(root, prefix, transform=xf)

    def build(prefix, col, row, top, bot, h, t, **dt_kwargs):
        occ = make_slot_comp(prefix, col, row)
        comp = occ.component
        cfg = sdt.define_params(params, prefix=prefix.lower(),
                                top_w_expr=top, bot_w_expr=bot,
                                height_expr=h, thick_expr=t, **dt_kwargs)
        frame = sdt.frame(comp, cfg, ev=ctx.ev, name=prefix)
        bodies = sdt.boards(comp, cfg, frame, ev=ctx.ev, name=prefix)
        sdt.corners(comp, cfg, frame,
                    bodies["Front"], bodies["Back"],
                    bodies["Left"], bodies["Right"],
                    ev=ctx.ev, name=prefix)
        return occ, comp, cfg

    # ================================================================
    # S1 @ (0,0): baseline midou geometry — 30/21/17 cm, 6 tails
    # ================================================================
    print("=" * 50 + "\nS1 @ (0,0): baseline 30/21/17, 6 tails\n" + "=" * 50)
    _add("s1_top", "30 cm"); _add("s1_bot", "21 cm")
    _add("s1_h", "17 cm"); _add("s1_t", "1.2 cm")
    _, s1_comp, s1_cfg = build(
        "S1", 0, 0, "s1_top", "s1_bot", "s1_h", "s1_t",
        angle="10 deg", tail_w="1.9 cm", tail_count="6", pad="0.6 cm")
    _check_fixture(ctx, sdt, s1_comp, s1_cfg, params, "S1")

    # ================================================================
    # S2 @ (0,1): shallow splay 20/16/12 (9.5 deg), 4 tails,
    # CALLER-SUPPLIED tilt + thick_h params (tilt_expr code path)
    # ================================================================
    print("=" * 50 + "\nS2 @ (0,1): shallow splay, caller tilt param\n"
          + "=" * 50)
    _add("s2_top", "20 cm"); _add("s2_bot", "16 cm")
    _add("s2_h", "12 cm"); _add("s2_t", "1.0 cm")
    if not params.itemByName("s2_lean"):
        params.add("s2_lean", VI("atan((s2_top - s2_bot) / 2 / s2_h)"),
                   "deg", "")
    if not params.itemByName("s2_wall"):
        params.add("s2_wall", VI("s2_t / cos(s2_lean)"), "cm", "")
    _, s2_comp, s2_cfg = build(
        "S2", 0, 1, "s2_top", "s2_bot", "s2_h", "s2_t",
        angle="9 deg", tail_w="1.4 cm", tail_count="4", pad="0.4 cm",
        tilt_expr="s2_lean", thick_h_expr="s2_wall")
    assert s2_cfg["tilt"] == "s2_lean", "S2: caller tilt param not used"
    _check_fixture(ctx, sdt, s2_comp, s2_cfg, params, "S2")

    # ================================================================
    # S3 @ (1,0): steep splay 36/20/15 (28.1 deg), thick stock, 5 tails
    # ================================================================
    print("=" * 50 + "\nS3 @ (1,0): steep splay 28 deg, thick stock\n"
          + "=" * 50)
    _add("s3_top", "36 cm"); _add("s3_bot", "20 cm")
    _add("s3_h", "15 cm"); _add("s3_t", "1.5 cm")
    _, s3_comp, s3_cfg = build(
        "S3", 1, 0, "s3_top", "s3_bot", "s3_h", "s3_t",
        angle="10 deg", tail_w="2.4 cm", tail_count="5", pad="0.8 cm")
    assert ctx.ev("s3_pin_w") > 0, "S3: pin width went negative"
    _check_fixture(ctx, sdt, s3_comp, s3_cfg, params, "S3")

    # ================================================================
    # S4 @ (1,1): thin stock 0.8, many tails (9) — 28/22/16
    # ================================================================
    print("=" * 50 + "\nS4 @ (1,1): thin stock, 9 tails\n" + "=" * 50)
    _add("s4_top", "28 cm"); _add("s4_bot", "22 cm")
    _add("s4_h", "16 cm"); _add("s4_t", "0.8 cm")
    _, s4_comp, s4_cfg = build(
        "S4", 1, 1, "s4_top", "s4_bot", "s4_h", "s4_t",
        angle="8 deg", tail_w="1.0 cm", tail_count="9", pad="0.4 cm")
    _check_fixture(ctx, sdt, s4_comp, s4_cfg, params, "S4")

    # ================================================================
    # S5 @ (2,0): live recompute — the failure mode that killed the
    # original midou construction (SplitBody fragment classification).
    # Build at 30/21/17, then edit envelope params live and re-check
    # body count + analytic volume invariant at each geometry.
    # ================================================================
    print("=" * 50 + "\nS5 @ (2,0): live recompute fixture\n" + "=" * 50)
    _add("s5_top", "30 cm"); _add("s5_bot", "21 cm")
    _add("s5_h", "17 cm"); _add("s5_t", "1.2 cm")
    _, s5_comp, s5_cfg = build(
        "S5", 2, 0, "s5_top", "s5_bot", "s5_h", "s5_t",
        angle="10 deg", tail_w="1.9 cm", tail_count="6", pad="0.6 cm")
    _check_fixture(ctx, sdt, s5_comp, s5_cfg, params, "S5@build")

    params.itemByName("s5_top").expression = "25 cm"
    design.computeAll()
    _check_fixture(ctx, sdt, s5_comp, s5_cfg, params, "S5@top25")

    params.itemByName("s5_h").expression = "20 cm"
    design.computeAll()
    _check_fixture(ctx, sdt, s5_comp, s5_cfg, params, "S5@top25/h20")

    params.itemByName("s5_top").expression = "30 cm"
    params.itemByName("s5_h").expression = "17 cm"
    design.computeAll()
    _check_fixture(ctx, sdt, s5_comp, s5_cfg, params, "S5@restore")

    # ================================================================
    # Summary
    # ================================================================
    print("=" * 50 + "\nSUMMARY\n" + "=" * 50)
    total = 0
    for occ in root.occurrences:
        c = occ.component
        n = c.bRepBodies.count
        print(f"  {c.name}: {n} bodies")
        total += n
    expected = 4 * 5
    status = "PASS" if total == expected else "FAIL"
    print(f"\n{status}: expected {expected} bodies, got {total}")
    assert total == expected

    for occ in root.occurrences:
        c = occ.component
        for sk in c.sketches:
            sk.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
