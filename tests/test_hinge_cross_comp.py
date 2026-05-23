"""Test cross-component butt hinge installation.

S: Same-component control (should pass)
X: Cross-component — back in CaseComp, lid in LidComp (reproduces jewelry chest)
"""
import adsk.core
import adsk.fusion
import sys


def run(context):
    for _mod in list(sys.modules):
        if _mod.startswith("woodworking") or _mod.startswith("helpers"):
            del sys.modules[_mod]

    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    from helpers import sp, hardware

    hardware.clear_step_cache()
    ctx = sp.DesignContext(design)

    # ── X: Cross-component ──
    print("=== X: Cross-component hinge (back in Case, lid in Lid) ===")
    params.add("x_l", VI("8 in"), "in", "")
    params.add("x_w", VI("5 in"), "in", "")
    params.add("x_h", VI("4 in"), "in", "")
    params.add("x_bt", VI("0.375 in"), "in", "")

    occ_case = sp.make_comp(root, "CaseComp"); comp_case = occ_case.component
    bp = sp.off_plane(comp_case, comp_case.xZConstructionPlane,
                      "x_w - x_bt", "X_BackPl")
    sk, pr = sp.sketch_rect_model(comp_case, bp,
        ("0 in", "x_w - x_bt", "0 in"), {"x": "x_l", "z": "x_h"},
        "X_Back_Sk", ctx.ev)
    x_back = sp.ext_new(comp_case, pr, "x_bt", "X_Back").bodies.item(0)
    x_back.name = "X_Back"

    occ_lid = sp.make_comp(root, "LidComp"); comp_lid = occ_lid.component
    lp = sp.off_plane(comp_lid, comp_lid.xYConstructionPlane, "x_h", "X_LidPl")
    sk, pr = sp.sketch_rect_model(comp_lid, lp,
        ("0 in", "0 in", "x_h"), {"x": "x_l", "y": "x_w"}, "X_Lid_Sk", ctx.ev)
    x_lid = sp.ext_new(comp_lid, pr, "x_bt", "X_Lid").bodies.item(0)
    x_lid.name = "X_Lid"

    bv, lv = x_back.volume, x_lid.volume
    print(f"  Back vol before: {bv:.2f}, Lid vol before: {lv:.2f}")

    # Install hinge in ROOT (cross-component), bare=True for speed
    r = hardware.install_butt_hinge(part_id="1603a2", comp=root,
        back_body=x_back, lid_body=x_lid,
        pin_position=(ctx.ev("x_l / 2"), ctx.ev("x_w"), ctx.ev("x_h")),
        style="lid_flush", bare=True, ev=ctx.ev, name="XH")

    back_cut = x_back.volume < bv
    lid_cut = x_lid.volume < lv
    print(f"  Back cut: {back_cut} ({bv:.2f} -> {x_back.volume:.2f})")
    print(f"  Lid cut: {lid_cut} ({lv:.2f} -> {x_lid.volume:.2f})")
    print(f"  Bodies: {len(r.get('bodies', []))}, Cuts: {len(r.get('cuts', []))}")
    print(f"  {'PASS' if back_cut and lid_cut else 'FAIL'}")

    hardware.cleanup_step_templates()
    cam = app.activeViewport.camera; cam.isFitView = True; app.activeViewport.camera = cam
