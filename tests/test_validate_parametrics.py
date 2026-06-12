"""Test fixture for validate_parametrics — parameter robustness sweep.

Builds three single-box components with deliberately different fragility,
then runs the sweep and asserts each failure class is caught BY NAME and
the healthy parameter passes:

  notch_d ("9.8 cm" notch in a 10 cm box): +5% cuts THROUGH the floor,
      splitting the box → flagged via NEW/stranded body (and floating).
  edge_w  (10 cm box, fixed cut overlapping its edge by 0.3 cm): -5%
      shrinks the box away from the cut → the cut becomes ZERO-IMPACT.
  ctrl_w  (plain box): must NOT be flagged.

Also asserts the sweep restored every body volume to baseline (the
document round-trips).
"""
import importlib
import sys
import types

import adsk.core
import adsk.fusion

REPO = "/Users/frankzha/projects/shopprentice"


def run(context):
    for p in (REPO + "/addin", REPO):
        if p in sys.path:
            sys.path.remove(p)
        sys.path.insert(0, p)
    for _mod in list(sys.modules):
        if _mod.startswith("helpers") or _mod.startswith("cantools"):
            del sys.modules[_mod]
    importlib.invalidate_caches()

    from helpers import sp

    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    P3 = adsk.core.Point3D.create
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    ctx = sp.DesignContext()
    ev = ctx.ev

    for pname, expr in [("box_s", "10 cm"), ("notch_d", "9.8 cm"),
                        ("edge_w", "10 cm"), ("ctrl_w", "10 cm")]:
        params.add(pname, VI(expr), "cm", "")

    def box(comp, size_expr, name):
        _, pr = sp.sketch_rect_model(comp, comp.xYConstructionPlane,
            ("0 cm", "0 cm", "0 cm"),
            {"x": size_expr, "y": "box_s"}, f"{name}_Sk", ev)
        b = sp.ext_new(comp, pr, "box_s", name).bodies.item(0)
        b.name = name
        return b

    # F1: notch almost through — +5% splits the box
    c1 = sp.make_comp(root, "F_Notch").component
    b1 = box(c1, "box_s", "NotchBox")
    top_pl = sp.off_plane(c1, c1.xYConstructionPlane, "box_s", "N_Pl")
    # NOTE: keep the notch inside positive coordinates — sketch_rect_model
    # position dims are unsigned, a "-1 cm" origin reflects to +1 and
    # leaves a connecting strip (so the box would never split)
    sk, _ = sp.sketch_rect_model(c1, top_pl,
        ("4 cm", "0 cm", "box_s"),
        {"x": "2 cm", "y": "box_s"}, "Notch_Sk", ev)
    sp.ext_op(c1, sp.smallest_profile(sk), "notch_d", CUT, b1,
              "Notch_Cut", flip=True)

    # F2: cut overlapping the box edge by only 0.3 cm — -5% box width
    # pulls the box away and the cut becomes zero-impact
    c2 = sp.make_comp(root, "F_Edge").component
    b2 = box(c2, "edge_w", "EdgeBox")
    sk2 = c2.sketches.add(c2.xYConstructionPlane)
    sk2.sketchCurves.sketchLines.addTwoPointRectangle(
        P3(9.7, 2, 0), P3(10.3, 4, 0))
    sk2.name = "Edge_Sk"
    inp = c2.features.extrudeFeatures.createInput(sk2.profiles.item(0), CUT)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(5))
    inp.participantBodies = [b2]
    f2 = c2.features.extrudeFeatures.add(inp)
    f2.name = "Edge_Cut"

    # F3: control — nothing fragile about it
    c3 = sp.make_comp(root, "F_Ctrl").component
    box(c3, "ctrl_w", "CtrlBox")

    # Baseline volumes for the round-trip assertion
    def volumes():
        out = {}
        for occ in root.allOccurrences:
            for i in range(occ.component.bRepBodies.count):
                b = occ.component.bRepBodies.item(i)
                out[occ.name + "/" + b.name] = round(b.volume, 3)
        return out
    before = volumes()

    # Load the canonical tool under a synthetic package (importing the
    # real `tools` package would re-register everything)
    import primitives.registry as reg
    pkg = types.ModuleType("cantools")
    pkg.__path__ = [REPO + "/addin/tools"]
    sys.modules["cantools"] = pkg
    orig = reg.register
    reg.register = lambda i: None
    try:
        vp = importlib.import_module("cantools.validate_parametrics")
        importlib.reload(vp)
    finally:
        reg.register = orig

    res = vp.handler(params=["notch_d", "edge_w", "ctrl_w"])
    import json
    data = json.loads(res["content"][0]["text"])
    frag = {f["parameter"]: f["issues"] for f in data["fragileParameters"]}
    print("fragile:", json.dumps(frag, indent=1))

    assert "notch_d" in frag, "sweep missed the splitting notch cut"
    notch_iss = json.dumps(frag["notch_d"])
    assert "NEW/stranded" in notch_iss or "MISSING" in notch_iss, \
        f"notch_d flagged but not as a body change: {notch_iss}"
    assert "edge_w" in frag, "sweep missed the cut that misses the box"
    assert "ZERO-IMPACT" in json.dumps(frag["edge_w"]), \
        f"edge_w flagged but not as zero-impact: {frag['edge_w']}"
    assert "ctrl_w" not in frag, \
        f"false positive on the control parameter: {frag.get('ctrl_w')}"
    assert data.get("aborted") is None, f"sweep aborted: {data.get('aborted')}"

    after = volumes()
    assert after == before, \
        f"document did not round-trip: {before} -> {after}"

    print("ALL VALIDATE_PARAMETRICS TESTS PASSED")
