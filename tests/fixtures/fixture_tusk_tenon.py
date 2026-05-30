"""Fixture: Tusk tenon (knock-down through-tenon).

Builds a minimal assembly: two posts + a rail, applies tusk_tenon.through()
with mirror to exercise both ends.  Validates connectivity (1 cluster),
interference (0), and sketch traceability (all non-root sketches anchored).
"""
import adsk.core
import adsk.fusion

from helpers import sp
from woodworking.templates import tusk_tenon as tk


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters

    P3 = adsk.core.Point3D.create
    VI = adsk.core.ValueInput.createByString
    NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    # ── Parameters ──
    for pname, expr, unit in [
        ("post_thick", "1.5 in",  "in"),
        ("post_w",     "4 in",    "in"),
        ("post_h",     "20 in",   "in"),
        ("spacing",    "20 in",   "in"),
        ("rail_w",     "2 in",    "in"),
        ("rail_h",     "4 in",    "in"),
        ("rail_z",     "8 in",    "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    tk.define_params(params, prefix="tk",
                     tenon_w="1.5 in", tenon_h="3 in", proud="1 in",
                     key_thin="0.25 in", key_taper_ang="8 deg",
                     key_blade="0.375 in", key_len="6 in")

    ev = sp._make_ev()

    # ── Posts component (origin root) ──
    posts_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    posts_comp = posts_occ.component
    posts_comp.name = "Posts"

    sk1 = posts_comp.sketches.add(posts_comp.xYConstructionPlane)
    sk1.name = "PostL_Sk"
    pt = ev("post_thick"); pw = ev("post_w")
    rect = sk1.sketchCurves.sketchLines.addTwoPointRectangle(
        P3(0, 0, 0), P3(pt, pw, 0))
    gc = sk1.geometricConstraints
    gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
    gc.addVertical(rect[1]); gc.addVertical(rect[3])
    d = sk1.sketchDimensions
    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
    d.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
                           H, P3(pt / 2, -1, 0)).parameter.expression = "post_thick"
    d.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
                           V, P3(pt + 1, pw / 2, 0)).parameter.expression = "post_w"

    ext1 = sp.ext_new(posts_comp, sk1.profiles.item(0), "post_h", "PostL_Ext")
    post_l = ext1.bodies.item(0)
    post_l.name = "Post_L"

    # Post_R: second extrude at X = post_thick + spacing
    sk2 = posts_comp.sketches.add(posts_comp.xYConstructionPlane)
    sk2.name = "PostR_Sk"
    ox = ev("post_thick + spacing")
    rect2 = sk2.sketchCurves.sketchLines.addTwoPointRectangle(
        P3(ox, 0, 0), P3(ox + pt, pw, 0))
    gc2 = sk2.geometricConstraints
    gc2.addHorizontal(rect2[0]); gc2.addHorizontal(rect2[2])
    gc2.addVertical(rect2[1]); gc2.addVertical(rect2[3])
    d2 = sk2.sketchDimensions
    d2.addDistanceDimension(rect2[0].startSketchPoint, rect2[0].endSketchPoint,
                            H, P3(ox + pt / 2, -1, 0)).parameter.expression = "post_thick"
    d2.addDistanceDimension(rect2[1].startSketchPoint, rect2[1].endSketchPoint,
                            V, P3(ox + pt + 1, pw / 2, 0)).parameter.expression = "post_w"
    d2.addDistanceDimension(sk2.originPoint, rect2[0].startSketchPoint,
                            H, P3(ox / 2, -2, 0)).parameter.expression = "post_thick + spacing"

    ext2 = sp.ext_new(posts_comp, sk2.profiles.item(0), "post_h", "PostR_Ext")
    post_r = ext2.bodies.item(0)
    post_r.name = "Post_R"

    # ── Rail component ──
    rail_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    rail_comp = rail_occ.component
    rail_comp.name = "Rail"

    rail_plane = sp.off_plane(rail_comp, rail_comp.xYConstructionPlane,
                               "rail_z", "Rail_Pl")
    rail_origin = ("post_thick", "(post_w - rail_w) / 2", "rail_z")
    rail_size = {"x": "spacing", "y": "rail_w"}
    _, rpr = sp.sketch_rect_model(
        rail_comp, rail_plane, rail_origin, rail_size,
        "Rail_Sk", ev=ev,
        anchor={
            "parent_body": post_l, "parent_occ": posts_occ,
            "face_axis": "z", "face_dir": +1,
            "anchor_xyz": ("post_thick", "post_w", "post_h"),
            "off1": ("y", "(post_w + rail_w) / 2"),
            "off2": ("x", "0 in"),
            "which": 2,
        })
    rail_ext = sp.ext_new(rail_comp, rpr, "rail_h", "Rail_Ext")
    rail = rail_ext.bodies.item(0)
    rail.name = "Rail"

    # ── Tusk tenon (left end, mirrored to right) ──
    mid_plane = sp.off_plane(rail_comp, rail_comp.yZConstructionPlane,
                              "post_thick + spacing / 2", "MidPl")

    tk.through(
        comp=rail_comp,
        receiver=post_l, receiver_occ=posts_occ,
        rail=rail,
        tenon_plane=rail_comp.yZConstructionPlane,
        tenon_plane_offset="post_thick",
        tenon_origin=("post_thick",
                       "(post_w - tk_tw) / 2",
                       "rail_z + (rail_h - tk_th) / 2"),
        tenon_size={"y": "tk_tw", "z": "tk_th"},
        tenon_depth="post_thick + tk_proud",
        tenon_anchor={
            "parent_body": post_l, "parent_occ": posts_occ,
            "face_axis": "z", "face_dir": +1,
            "anchor_xyz": ("post_thick", "post_w", "post_h"),
            "off1": ("y", "(post_w + tk_tw) / 2"),
            "off2": ("x", "0 in"),
            "which": 2,
        },
        key_plane=rail_comp.xZConstructionPlane,
        key_plane_offset="post_w / 2",
        key_bearing_face=("x", -1),
        key_anchor_xyz=("0 in", "post_w / 2", "post_h"),
        key_center_expr="rail_z + rail_h / 2",
        key_anchor_offset_expr="post_h - rail_z - rail_h / 2 + tk_key_len / 2",
        name="TK",
        ev=ev,
        mirror_plane=mid_plane,
        mirror_receiver=post_r,
        mirror_receiver_occ=posts_occ,
        prefix="tk",
        combine=True)

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
