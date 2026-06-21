"""Visual + interference fixture for the breadboard template.

Builds several small panel + breadboard pairs side by side along X, each with a
different breadboard configuration, then applies
``woodworking.templates.breadboard``. For visual review in Fusion and for
interference debugging of the template in isolation (far simpler than the full
table). Run via ``execute_script(clean=True)``.

Each config sits in its own X band so they don't touch:

    bfa  x=0    n=4  pins=1  through   (typical — the default, 1 pin/tenon)
    bfb  x=30   n=3  pins=1  blind     (single hidden pin)
    bfc  x=60   n=5  pins=0  through   (unpinned / glued)
    bfd  x=90   n=3  pins=2  through   (2 pins/tenon — slot spacing test)
"""
import adsk.core
import adsk.fusion


def run(context):
    import importlib
    from helpers import sp
    import woodworking.templates.breadboard as bbd
    importlib.reload(bbd)   # the add-in caches modules; pick up the latest edits

    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    des.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = des.rootComponent
    params = des.userParameters
    ev = sp._make_ev()

    VI = adsk.core.ValueInput.createByString
    P3 = adsk.core.Point3D.create
    NB = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    IN = 2.54

    PL, PW, PT, BBT = 16.0, 12.0, 0.875, 2.0   # panel len/width/thick, breadboard thick (in)

    def box(comp, name, x0, x1, y0, y1, thick):
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sk.sketchCurves.sketchLines.addTwoPointRectangle(
            P3(x0 * IN, y0 * IN, 0), P3(x1 * IN, y1 * IN, 0))
        prof = sk.profiles.item(0)
        inp = comp.features.extrudeFeatures.createInput(prof, NB)
        inp.setDistanceExtent(False, VI("%f in" % thick))
        b = comp.features.extrudeFeatures.add(inp).bodies.item(0)
        b.name = name
        return b

    configs = [
        ("bfa", 0.0,  "4", "1", "through"),
        ("bfb", 30.0, "3", "1", "blind"),
        ("bfc", 60.0, "5", "0", "through"),
        ("bfd", 90.0, "3", "2", "through"),
    ]
    for pre, xoff, n, ppt, mode in configs:
        occ = sp.make_comp(root, "Cfg_" + pre)   # each fixture is its own component
        comp = occ.component
        px1 = xoff + PL
        panel = box(comp, "Panel_" + pre, xoff, px1, -PW / 2, PW / 2, PT)
        bbbody = box(comp, "BB_" + pre, px1, px1 + BBT, -PW / 2, PW / 2, PT)
        bbd.define_params(
            params, prefix=pre,
            bb_thick="%f in" % BBT, bb_height="%f in" % PT,
            tongue_d="0.375 in", tongue_t="0.25 in",
            tenon_d="1.0 in", tenon_w="1.5 in", tenon_t="0.25 in",
            n_tenons=n, pins_per_tenon=ppt, pin_dia="0.25 in")
        try:
            res = bbd.build(
                comp, panel, bbbody,
                panel_end_face=("x", 1),
                panel_w_expr="%f in" % PW, panel_t_expr="%f in" % PT,
                end_x_expr="%f in" % px1, y0_expr="%f in" % (-PW / 2),
                z0_expr="0 in",
                n_tenons=n, pins_per_tenon=ppt, pin_mode=mode,
                prefix=pre, name="BB_" + pre.upper(), ev=ev,
                panel_occ=None, bb_occ=None)   # origin-mode: deterministic placement
                # (each config's component sits at the world origin, so origin dims
                #  are exact; passing the occ routes pins through sp.reanchor, which
                #  mis-places them — a separate non-root anchoring bug to fix.)
            print("OK  %s  n=%s pins=%s %-8s  pins_built=%d" % (
                pre, n, ppt, mode, len(res.get("pins", []))))
        except Exception as e:
            print("ERR %s  n=%s pins=%s %-8s  %s" % (pre, n, ppt, mode, e))
