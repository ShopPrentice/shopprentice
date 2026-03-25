"""Test fixture for Japanese scarf joint (kanawa tsugi) template.

Creates two abutting posts along Z-axis and applies the scarf joint
to splice them. Validates:
  - Scarf geometry builds without errors
  - Wedge body is created
  - Both posts receive their interlocking halves

Expected bodies: 2 posts + 1 wedge + 1 hidden key_tool = 3 visible.
"""
import adsk.core
import adsk.fusion


def run(context):
    app = adsk.core.Application.get()

    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString

    # Force fresh import (Fusion caches modules)
    import sys
    import importlib
    for k in list(sys.modules):
        if 'scarf_joint' in k or k == 'woodworking.templates':
            del sys.modules[k]

    from helpers import sp
    from woodworking.templates import scarf_joint as sj
    importlib.reload(sj)

    ctx = sp.DesignContext(design)

    # ── Parameters ──
    params.add("post_w", VI("3.5 in"), "in", "Post width")
    params.add("post_h", VI("48 in"), "in", "Post height (each half)")

    sj.define_params(params, prefix="sj",
                     scarf_length="13 in",
                     scarf_notch="(5/8) * 1 in")

    # ── Build two posts butting at z=48 in ──
    _, pr = sp.sketch_rect_model(root, root.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "post_w", "y": "post_w"}, "Post_A_Sk", ctx.ev)
    post_a = sp.ext_new(root, pr, "post_h", "Post_A").bodies.item(0)
    post_a.name = "post_a"

    _, pr2 = sp.sketch_rect_model(root, root.xYConstructionPlane,
        ("0 in", "0 in", "post_h"),
        {"x": "post_w", "y": "post_w"}, "Post_B_Sk", ctx.ev)
    post_b = sp.ext_new(root, pr2, "post_h", "Post_B").bodies.item(0)
    post_b.name = "post_b"

    # ── Apply scarf joint ──
    splice_face = sp.find_face(post_a, "z", +1)

    result = sj.kanawa_tsugi(
        root,
        body_a=post_a,
        body_b=post_b,
        splice_face=splice_face,
        grain_axis="z",
        cross_axis="x",
        prefix="sj",
        name="SJ1",
        ev=ctx.ev,
    )

    app.log(f"Scarf joint created: {len(result['features'])} features")
    app.log(f"Wedge body: {result['wedge'].name}")
