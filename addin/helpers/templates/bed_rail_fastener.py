"""Bed rail fastener (mortise bedlock) installation template.

Creates mortise pockets in a post and rail, then inserts the hook plate
and strike plate hardware. The joint is detachable — rail lifts off the post.

The hook plate mortises into the rail END face.
The strike plate mortises into the post SIDE face.
Both plates are flush with the wood surface when installed.

Hardware STEP files at: ~/.autofusion/hardware/bed_rail_fastener/

Usage:
    from helpers.templates import bed_rail_fastener

    # Install a pair of bedlocks connecting a side rail to a post
    bed_rail_fastener.install(
        root,                          # root component (cross-component CUTs)
        post_body=post_proxy,          # post body (assembly proxy)
        rail_body=rail_proxy,          # rail body (assembly proxy)
        post_face_axis="y",            # which axis the post face is on
        post_face_dir=-1,              # -1=min face, +1=max face
        rail_face_axis="y",            # which axis the rail end face is on
        rail_face_dir=+1,              # rail end facing the post
        center_z="rail_h / 2",         # Z center of the fastener on the boards
        size="100mm",                  # 80mm, 100mm, or 120mm
        name="BedRail_RL_F",
        ev=ev,
    )

Three sizes available:
  80mm  — 1 hook, for lighter rails or secondary connections
  100mm — 2 hooks, standard for side rails (recommended)
  120mm — 2 hooks, for heavy-duty or tall rails

Each rail needs TWO pairs (upper and lower) for stability.
"""

import adsk.core
import adsk.fusion
import os

from helpers import af

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

# Hardware dimensions (must match bed_rail_fastener.py generator)
SIZES = {
    "80mm":  {"length": 8.0, "width": 1.5, "thickness": 0.25},
    "100mm": {"length": 10.0, "width": 1.5, "thickness": 0.25},
    "120mm": {"length": 12.0, "width": 1.5, "thickness": 0.25},
}

HARDWARE_DIR = os.path.expanduser("~/.autofusion/hardware/bed_rail_fastener")


def install(comp, post_body, rail_body,
            post_face_axis, post_face_dir,
            rail_face_axis, rail_face_dir,
            center_z, size="100mm", name="BedRail", ev=None):
    """Install a bedlock pair (hook plate in rail, strike plate in post).

    Creates stadium-shaped mortise pockets in both boards at plate_thickness
    depth, flush with the surface. The pockets accept the STEP hardware.

    Args:
        comp: Root component (for cross-component CUTs).
        post_body: Post body (assembly proxy) — strike plate goes here.
        rail_body: Rail body (assembly proxy) — hook plate goes here.
        post_face_axis: "x", "y", or "z" — axis of the post face.
        post_face_dir: +1 or -1 — which face of the post.
        rail_face_axis: "x", "y", or "z" — axis of the rail end face.
        rail_face_dir: +1 or -1 — which face of the rail.
        center_z: Expression or float — Z center of the fastener.
        size: "80mm", "100mm", or "120mm".
        name: Feature name prefix.
        ev: Parameter evaluator.
    """
    if ev is None:
        design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
        ev = lambda e: (design.userParameters.itemByName(e).value
                        if design.userParameters.itemByName(e)
                        else design.unitsManager.evaluateExpression(e, "cm"))

    dims = SIZES[size]
    plate_l = dims["length"]
    plate_w = dims["width"]
    plate_t = dims["thickness"]

    cz = ev(center_z) if isinstance(center_z, str) else center_z

    VI = adsk.core.ValueInput.createByString
    P3 = adsk.core.Point3D

    # Find the target faces
    post_face = af.find_face(post_body, post_face_axis, post_face_dir)
    rail_face = af.find_face(rail_body, rail_face_axis, rail_face_dir)

    if not post_face or not rail_face:
        print(f">>> WARNING: Could not find faces for {name}")
        return

    # === STRIKE PLATE POCKET (in post face) ===
    # Sketch stadium on post face, CUT by plate_t depth
    sk_post = comp.sketches.add(post_face)
    sk_post.name = f"{name}_StrikePocket_Sk"

    # Determine face center and orientation
    face_pt = post_face.pointOnFace
    m2s = sk_post.modelToSketchSpace

    # Stadium centered on face at center_z
    # The plate length runs vertically (along Z in model space)
    r = plate_w / 2
    face_center_model = P3.create(face_pt.x, face_pt.y, cz)
    sc = m2s(face_center_model)

    # Approximate points for the stadium in model space
    # Plate length runs in Z, plate width perpendicular to face axis
    half_l = plate_l / 2

    # Determine which model axes are "along plate" and "across plate"
    # Plate length always runs in Z (vertical)
    # Plate width runs in the axis perpendicular to both Z and the face normal
    z_top = cz + half_l
    z_bot = cz - half_l

    # Get the face-parallel axis that isn't Z
    face_axes = {"x", "y", "z"} - {post_face_axis}
    cross_axis = (face_axes - {"z"}).pop() if "z" in face_axes else "x"

    cross_center = getattr(face_pt, cross_axis)

    # Build stadium points in model space
    def mp(ca_val, z_val):
        pt = [0, 0, 0]
        pt["xyz".index(post_face_axis)] = getattr(face_pt, post_face_axis)
        pt["xyz".index(cross_axis)] = ca_val
        pt[2] = z_val  # Z is always vertical
        return P3.create(*pt)

    lines = sk_post.sketchCurves.sketchLines
    arcs = sk_post.sketchCurves.sketchArcs

    sp_tl = m2s(mp(cross_center - r, z_top - r))
    sp_tr = m2s(mp(cross_center + r, z_top - r))
    sp_br = m2s(mp(cross_center + r, z_bot + r))
    sp_bl = m2s(mp(cross_center - r, z_bot + r))
    sp_top = m2s(mp(cross_center, z_top))
    sp_bot = m2s(mp(cross_center, z_bot))

    l_left = lines.addByTwoPoints(sp_tl, sp_bl)
    l_right = lines.addByTwoPoints(sp_br, sp_tr)
    arcs.addByThreePoints(l_right.endSketchPoint, sp_top, l_left.startSketchPoint)
    arcs.addByThreePoints(l_left.endSketchPoint, sp_bot, l_right.startSketchPoint)

    prof = sk_post.profiles.item(0)
    pocket_ext = comp.features.extrudeFeatures.createInput(prof, CUT)
    pocket_ext.setDistanceExtent(False, VI(f"{plate_t} cm"))
    pocket_ext.participantBodies = [post_body]
    comp.features.extrudeFeatures.add(pocket_ext).name = f"{name}_StrikePocket"
    sk_post.isVisible = False

    # === HOOK PLATE POCKET (in rail end face) ===
    sk_rail = comp.sketches.add(rail_face)
    sk_rail.name = f"{name}_HookPocket_Sk"

    face_pt_r = rail_face.pointOnFace
    m2s_r = sk_rail.modelToSketchSpace

    face_axes_r = {"x", "y", "z"} - {rail_face_axis}
    cross_axis_r = (face_axes_r - {"z"}).pop() if "z" in face_axes_r else "x"
    cross_center_r = getattr(face_pt_r, cross_axis_r)

    def mp_r(ca_val, z_val):
        pt = [0, 0, 0]
        pt["xyz".index(rail_face_axis)] = getattr(face_pt_r, rail_face_axis)
        pt["xyz".index(cross_axis_r)] = ca_val
        pt[2] = z_val
        return P3.create(*pt)

    lines_r = sk_rail.sketchCurves.sketchLines
    arcs_r = sk_rail.sketchCurves.sketchArcs

    sp_tl_r = m2s_r(mp_r(cross_center_r - r, z_top - r))
    sp_tr_r = m2s_r(mp_r(cross_center_r + r, z_top - r))
    sp_br_r = m2s_r(mp_r(cross_center_r + r, z_bot + r))
    sp_bl_r = m2s_r(mp_r(cross_center_r - r, z_bot + r))
    sp_top_r = m2s_r(mp_r(cross_center_r, z_top))
    sp_bot_r = m2s_r(mp_r(cross_center_r, z_bot))

    l_left_r = lines_r.addByTwoPoints(sp_tl_r, sp_bl_r)
    l_right_r = lines_r.addByTwoPoints(sp_br_r, sp_tr_r)
    arcs_r.addByThreePoints(l_right_r.endSketchPoint, sp_top_r, l_left_r.startSketchPoint)
    arcs_r.addByThreePoints(l_left_r.endSketchPoint, sp_bot_r, l_right_r.startSketchPoint)

    prof_r = sk_rail.profiles.item(0)
    pocket_ext_r = comp.features.extrudeFeatures.createInput(prof_r, CUT)
    pocket_ext_r.setDistanceExtent(False, VI(f"{plate_t} cm"))
    pocket_ext_r.participantBodies = [rail_body]
    comp.features.extrudeFeatures.add(pocket_ext_r).name = f"{name}_HookPocket"
    sk_rail.isVisible = False

    # === INSERT PLATE BODIES into the pockets ===
    # Strike plate in post pocket (stadium body, flush with post face)
    sk_sp_body = comp.sketches.add(post_face)
    sk_sp_body.name = f"{name}_StrikePlateBody_Sk"
    m2s_spb = sk_sp_body.modelToSketchSpace
    lines_spb = sk_sp_body.sketchCurves.sketchLines
    arcs_spb = sk_sp_body.sketchCurves.sketchArcs

    sp_tl_b = m2s_spb(mp(cross_center - r, z_top - r))
    sp_tr_b = m2s_spb(mp(cross_center + r, z_top - r))
    sp_br_b = m2s_spb(mp(cross_center + r, z_bot + r))
    sp_bl_b = m2s_spb(mp(cross_center - r, z_bot + r))
    sp_top_b = m2s_spb(mp(cross_center, z_top))
    sp_bot_b = m2s_spb(mp(cross_center, z_bot))

    l_left_b = lines_spb.addByTwoPoints(sp_tl_b, sp_bl_b)
    l_right_b = lines_spb.addByTwoPoints(sp_br_b, sp_tr_b)
    arcs_spb.addByThreePoints(l_right_b.endSketchPoint, sp_top_b, l_left_b.startSketchPoint)
    arcs_spb.addByThreePoints(l_left_b.endSketchPoint, sp_bot_b, l_right_b.startSketchPoint)

    sp_body_prof = sk_sp_body.profiles.item(0)
    sp_body_ext = comp.features.extrudeFeatures.createInput(sp_body_prof, NEW)
    sp_body_ext.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(VI(f"{plate_t} cm")),
        adsk.fusion.ExtentDirections.NegativeExtentDirection)
    sp_body_feat = comp.features.extrudeFeatures.add(sp_body_ext)
    sp_body_feat.name = f"{name}_StrikePlate"
    sp_body_feat.bodies.item(0).name = f"{name}_StrikePlate"
    sk_sp_body.isVisible = False

    # Hook plate in rail pocket
    sk_hp_body = comp.sketches.add(rail_face)
    sk_hp_body.name = f"{name}_HookPlateBody_Sk"
    m2s_hpb = sk_hp_body.modelToSketchSpace
    lines_hpb = sk_hp_body.sketchCurves.sketchLines
    arcs_hpb = sk_hp_body.sketchCurves.sketchArcs

    hp_tl_b = m2s_hpb(mp_r(cross_center_r - r, z_top - r))
    hp_tr_b = m2s_hpb(mp_r(cross_center_r + r, z_top - r))
    hp_br_b = m2s_hpb(mp_r(cross_center_r + r, z_bot + r))
    hp_bl_b = m2s_hpb(mp_r(cross_center_r - r, z_bot + r))
    hp_top_b = m2s_hpb(mp_r(cross_center_r, z_top))
    hp_bot_b = m2s_hpb(mp_r(cross_center_r, z_bot))

    l_left_hb = lines_hpb.addByTwoPoints(hp_tl_b, hp_bl_b)
    l_right_hb = lines_hpb.addByTwoPoints(hp_br_b, hp_tr_b)
    arcs_hpb.addByThreePoints(l_right_hb.endSketchPoint, hp_top_b, l_left_hb.startSketchPoint)
    arcs_hpb.addByThreePoints(l_left_hb.endSketchPoint, hp_bot_b, l_right_hb.startSketchPoint)

    hp_body_prof = sk_hp_body.profiles.item(0)
    hp_body_ext = comp.features.extrudeFeatures.createInput(hp_body_prof, NEW)
    hp_body_ext.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(VI(f"{plate_t} cm")),
        adsk.fusion.ExtentDirections.NegativeExtentDirection)
    hp_body_feat = comp.features.extrudeFeatures.add(hp_body_ext)
    hp_body_feat.name = f"{name}_HookPlate"
    hp_body_feat.bodies.item(0).name = f"{name}_HookPlate"
    sk_hp_body.isVisible = False

    print(f">>> {name}: {size} bedlock installed (pockets + plates in post + rail)")
