"""Test fixture for the taper_legs template + the zero-impact validator.

Gallery layout — each leg lives in its own component on a grid:

  T1 @ (0,0):    straight 1.5" leg, inner_pair taper — EXACT analytic
                 volume (ls²·h − 2·wedge + overlap)
  T2 @ (20,0):   raked leg (6° rotation about X via Move), same taper —
                 the cut anchors to the rotated faces, so the removed
                 volume is rotation-invariant and the SAME analytic
                 formula must hold exactly
  T3 @ (40,0):   compound rake+splay (6° about X, then −5° about Y) —
                 same exact analytic check
  T4 @ (60,0):   zero-impact validator: a deliberate no-op CUT extrude +
                 no-op CUT combine must be flagged BY NAME by
                 tools.validate_design._check_feature_impact, while all
                 healthy features (including every taper cut above) pass

Volume formula (leg-local frame, rotation-invariant):
  wedge   = 0.5 · amt · run · ls          (one face's taper wedge)
  overlap = amt² · run / 3                (the two wedges' shared corner)
  removed = 2 · wedge − overlap
"""
import importlib
import importlib.util
import math
import sys

import adsk.core
import adsk.fusion


REPO = "/Users/frankzha/projects/shopprentice"


def run(context):
    # Pin the canonical checkout ahead of any stale dev worktrees that a
    # previous session may have prepended to sys.path, then evict cached
    # modules — Fusion keeps Python modules hot across runs.
    for p in (REPO + "/addin", REPO):
        if p in sys.path:
            sys.path.remove(p)
        sys.path.insert(0, p)
    for _mod in list(sys.modules):
        if _mod.startswith("woodworking") or _mod.startswith("helpers"):
            del sys.modules[_mod]
    importlib.invalidate_caches()   # pick up newly created module files

    from helpers import sp
    import woodworking.templates.taper_legs as tl
    importlib.reload(tl)

    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    P3 = adsk.core.Point3D.create
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation

    ctx = sp.DesignContext()
    ev = ctx.ev

    for pname, expr in [("ls", "1.5 in"), ("lh", "28.5 in")]:
        params.add(pname, VI(expr), "in", "")
    tl.define_params(params, amount="0.5 in", run="25 in")

    ls_v, lh_v = ev("ls"), ev("lh")
    amt_v, run_v = ev("tp_amt"), ev("tp_run")
    wedge = 0.5 * amt_v * run_v * ls_v
    overlap = amt_v * amt_v * run_v / 3.0
    expected = ls_v * ls_v * lh_v - 2 * wedge + overlap

    def build_leg(comp, name):
        _, pr = sp.sketch_rect_model(comp, comp.xYConstructionPlane,
            ("0 in", "0 in", "0 in"), {"x": "ls", "y": "ls"},
            f"{name}_Sk", ev)
        body = sp.ext_new(comp, pr, "lh", name).bodies.item(0)
        body.name = name
        return body

    def rotate(comp, body, axis_vec, deg):
        coll = adsk.core.ObjectCollection.create()
        coll.add(body)
        tx = adsk.core.Matrix3D.create()
        tx.setToRotation(math.radians(deg),
                         adsk.core.Vector3D.create(*axis_vec),
                         P3(0, 0, 0))
        mi = comp.features.moveFeatures.createInput2(coll)
        mi.defineAsFreeMove(tx)
        comp.features.moveFeatures.add(mi)

    def place(occ_name, x):
        occ = sp.make_comp(root, occ_name)
        tf = occ.transform2
        tf.translation = adsk.core.Vector3D.create(x, 0, 0)
        occ.transform2 = tf
        return occ

    def check(label, body):
        got = body.volume
        assert abs(got - expected) <= 0.01 * expected, \
            f"{label}: volume {got:.2f}, expected {expected:.2f}"
        print(f"  {label}: PASS (vol={got:.2f}, exp={expected:.2f})")

    # ── T1: straight leg ─────────────────────────────────────────────
    occ1 = place("T1_Straight", 0)
    c1 = occ1.component
    leg1 = build_leg(c1, "Leg_T1")
    tl.inner_pair(c1, leg1, (ev("ls") * 5, ev("ls") * 5, 0), ev,
                  thick_expr="ls * 2", name="T1")
    check("T1 straight", leg1)

    # ── T2: raked leg (6° about X) ───────────────────────────────────
    occ2 = place("T2_Rake", 20)
    c2 = occ2.component
    leg2 = build_leg(c2, "Leg_T2")
    rotate(c2, leg2, (1, 0, 0), 6)
    tl.inner_pair(c2, leg2, (ev("ls") * 5, ev("ls") * 5, 0), ev,
                  thick_expr="ls * 2", name="T2")
    check("T2 rake 6deg", leg2)

    # ── T3: compound rake + splay ────────────────────────────────────
    occ3 = place("T3_Splay", 40)
    c3 = occ3.component
    leg3 = build_leg(c3, "Leg_T3")
    rotate(c3, leg3, (1, 0, 0), 6)
    rotate(c3, leg3, (0, 1, 0), -5)
    tl.inner_pair(c3, leg3, (ev("ls") * 5, ev("ls") * 5, 0), ev,
                  thick_expr="ls * 2", name="T3")
    check("T3 rake+splay", leg3)

    # ── T4: zero-impact validator flags no-op cuts by name ──────────
    occ4 = place("T4_Validator", 60)
    c4 = occ4.component
    box = build_leg(c4, "Box_T4")

    # healthy cut
    skg = c4.sketches.add(c4.xYConstructionPlane)
    skg.sketchCurves.sketchLines.addTwoPointRectangle(
        P3(ls_v - 1, 1, 0), P3(ls_v + 1, 2, 0))
    inp = c4.features.extrudeFeatures.createInput(skg.profiles.item(0), CUT)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(5))
    inp.participantBodies = [box]
    f_good = c4.features.extrudeFeatures.add(inp)
    f_good.name = "T4_GoodCut"

    # no-op cut extrude (profile entirely outside the box)
    skn = c4.sketches.add(c4.xYConstructionPlane)
    skn.sketchCurves.sketchLines.addTwoPointRectangle(
        P3(50, 50, 0), P3(52, 52, 0))
    inp = c4.features.extrudeFeatures.createInput(skn.profiles.item(0), CUT)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(5))
    inp.participantBodies = [box]
    f_noop = c4.features.extrudeFeatures.add(inp)
    f_noop.name = "T4_NoopCut"

    # no-op combine cut (tool far from target)
    skt = c4.sketches.add(c4.xYConstructionPlane)
    skt.sketchCurves.sketchLines.addTwoPointRectangle(
        P3(60, 60, 0), P3(62, 62, 0))
    inp = c4.features.extrudeFeatures.createInput(skt.profiles.item(0), NEW)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(2))
    tool = c4.features.extrudeFeatures.add(inp).bodies.item(0)
    tool.name = "T4_Tool"
    cin = c4.features.combineFeatures.createInput(
        box, adsk.core.ObjectCollection.create())
    cin.toolBodies.add(tool)
    cin.operation = CUT
    cin.isKeepToolBodies = True
    f_cmb = c4.features.combineFeatures.add(cin)
    f_cmb.name = "T4_NoopCombine"

    # mirror whose products are consumed by a later JOIN — the white-oak
    # table's MT_*_Mirror case. Reports 0 bodies AND 0 faces afterwards,
    # and must NOT be flagged as zero-impact.
    skm = c4.sketches.add(c4.xYConstructionPlane)
    skm.sketchCurves.sketchLines.addTwoPointRectangle(
        P3(0.2, 0.2, 0), P3(1.0, 1.0, 0))
    inp = c4.features.extrudeFeatures.createInput(skm.profiles.item(0), NEW)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(2))
    nub_ext = c4.features.extrudeFeatures.add(inp)
    nub_ext.name = "T4_Nub"
    nub = nub_ext.bodies.item(0)
    mid_pl = sp.off_plane(c4, c4.yZConstructionPlane, "ls / 2", "T4_Mid")
    mirf = sp.mirror_feats(c4, [nub_ext], mid_pl, "T4_NubMir")
    mir_body = mirf.bodies.item(0)
    sp.combine(box, [nub, mir_body], JOIN, False, "T4_NubJoin")
    assert mirf.bodies.count == 0 and mirf.faces.count == 0, \
        "test setup: expected the JOIN to consume the mirror's products"

    # Load validate_design.py directly from the canonical checkout —
    # importing the `tools` package would re-register every tool and
    # collide with the live registry. Stub register() during load.
    import primitives.registry as _reg
    _orig_register = _reg.register
    _reg.register = lambda item: None
    try:
        spec = importlib.util.spec_from_file_location(
            "vd_under_test", REPO + "/addin/tools/validate_design.py")
        vd = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vd)
    finally:
        _reg.register = _orig_register
    impact = vd._check_feature_impact(design)
    flagged = {z["feature"] for z in impact["zeroImpactFeatures"]}
    assert "T4_NoopCut" in flagged, \
        f"validator missed the no-op cut extrude; flagged={flagged}"
    assert "T4_NoopCombine" in flagged, \
        f"validator missed the no-op combine; flagged={flagged}"
    extras = flagged - {"T4_NoopCut", "T4_NoopCombine"}
    assert not extras, \
        f"validator false positives on healthy features: {extras}"
    assert impact["passed"] is False
    print(f"  T4 validator: PASS (flagged exactly {sorted(flagged)}; "
          f"{len(impact['unhealthyFeatures'])} health warning(s) listed)")

    print("ALL TAPER_LEGS TESTS PASSED")
