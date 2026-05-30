"""Fixture: Tabletop button.

Builds a minimal assembly: an apron block + a top panel, applies three
tabletop buttons via the template, then CUTs the apron with slot tools.
Validates connectivity (1 cluster), interference (0), and sketch traceability.

Layout (canonical orientation):
  Apron: X=[0, apron_w], Y=[0, apron_l], Z=[0, apron_h]
  Inner face at X=apron_w (toward table center, +X)
  Top:   rests on apron at Z=apron_h
  Through=X, Width/Movement=Y, Drive=Z
"""
import adsk.core
import adsk.fusion

from helpers import sp
from woodworking.templates import tabletop_button as btn


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters

    P3 = adsk.core.Point3D.create
    VI = adsk.core.ValueInput.createByString
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation

    # ── Parameters ──
    for pname, expr, unit in [
        ("apron_w",    "1.5 in",  "in"),
        ("apron_l",    "24 in",   "in"),
        ("apron_h",    "4 in",    "in"),
        ("top_l",      "30 in",   "in"),
        ("top_w",      "20 in",   "in"),
        ("top_thick",  "0.75 in", "in"),
        ("btn_off",    "6 in",    "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    btn.define_params(params)
    ev = sp._make_ev()

    # ── Apron component (origin root) ──
    apron_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    apron_comp = apron_occ.component
    apron_comp.name = "Apron"

    ask = apron_comp.sketches.add(apron_comp.xYConstructionPlane)
    ask.name = "Apron_Sk"
    aw = ev("apron_w"); al = ev("apron_l")
    arect = ask.sketchCurves.sketchLines.addTwoPointRectangle(
        P3(0, 0, 0), P3(aw, al, 0))
    gc = ask.geometricConstraints
    gc.addHorizontal(arect[0]); gc.addHorizontal(arect[2])
    gc.addVertical(arect[1]); gc.addVertical(arect[3])
    d = ask.sketchDimensions
    d.addDistanceDimension(arect[0].startSketchPoint, arect[0].endSketchPoint,
                           H, P3(aw / 2, -1, 0)).parameter.expression = "apron_w"
    d.addDistanceDimension(arect[1].startSketchPoint, arect[1].endSketchPoint,
                           V, P3(aw + 1, al / 2, 0)).parameter.expression = "apron_l"

    apron_ext = sp.ext_new(apron_comp, ask.profiles.item(0), "apron_h",
                            "Apron_Ext")
    apron_body = apron_ext.bodies.item(0)
    apron_body.name = "Apron"

    # ── Top component ──
    top_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    top_comp = top_occ.component
    top_comp.name = "Top"

    top_pl = sp.off_plane(top_comp, top_comp.xYConstructionPlane,
                           "apron_h", "Top_Pl")
    _, tpr = sp.sketch_rect_model(
        top_comp, top_pl,
        ("apron_w", "(apron_l - top_l) / 2", "apron_h"),
        {"x": "top_w", "y": "top_l"},
        "Top_Sk", ev=ev,
        anchor={
            "parent_body": apron_body, "parent_occ": apron_occ,
            "face_axis": "z", "face_dir": +1,
            "anchor_xyz": ("apron_w", "apron_l", "apron_h"),
            "off1": ("x", "0 in"),
            "off2": ("y", "(apron_l - top_l) / 2"),
            "which": 0,
        })
    top_ext = sp.ext_new(top_comp, tpr, "top_thick", "Top_Ext")
    top_body = top_ext.bodies.item(0)
    top_body.name = "Top"

    # ── Buttons (3 along Y for this fixture; caller decides count) ──
    be, se = btn.attach(
        comp=top_comp,
        apron=apron_body, apron_occ=apron_occ,
        button_plane=top_comp.xZConstructionPlane,
        button_plane_offset="apron_l / 2",
        apron_inner_face=("x", +1),
        apron_anchor_xyz=("apron_w", "apron_l / 2", "apron_h"),
        ci_expr="apron_w",
        top_expr="apron_h",
        y_center_expr="apron_l / 2",
        sgn=+1,
        name="BTN", ev=ev)

    sp.feat_pattern(top_comp, be, top_comp.yConstructionAxis,
                    "3", "btn_off", "Btn_Pat")
    sp.feat_pattern(top_comp, se, top_comp.yConstructionAxis,
                    "3", "btn_off", "Slot_Pat")

    # Bulk-CUT apron with all slot bodies
    slot_bodies = [top_comp.bRepBodies.item(i)
                   for i in range(top_comp.bRepBodies.count)
                   if "Slot" in top_comp.bRepBodies.item(i).name]
    if slot_bodies:
        sp.combine(apron_body, slot_bodies, CUT, False, "SlotCut")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
