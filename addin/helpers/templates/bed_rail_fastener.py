"""Bed rail fastener (mortise bedlock) installation template.

Imports hook plate and strike plate from STEP files, positions them at the
joint interface, and CUTs recess pockets into both boards.

The hook plate goes into the rail END face.
The strike plate goes into the post SIDE face.
Hardware STEP files must exist at: ~/.autofusion/hardware/bed_rail_fastener/

Usage:
    from helpers.templates import bed_rail_fastener

    bed_rail_fastener.install(
        root, post_body=post_proxy, rail_body=rail_proxy,
        interface_axis="x", interface_coord=7.62,
        center_z=19.05, size="100mm", name="BedRail_RL_F", ev=ev,
    )
"""

import adsk.core
import adsk.fusion
import math
import os

from helpers import af

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
HARDWARE_DIR = os.path.expanduser("~/.autofusion/hardware/bed_rail_fastener")

# Plate thickness for pocket depth (must match hardware generator)
PLATE_T = 0.25  # cm


def install(comp, post_body, rail_body,
            interface_axis, interface_coord,
            center_z, size="100mm", name="BedRail", ev=None):
    """Install a bedlock pair by importing STEP hardware and cutting recesses.

    Args:
        comp: Root component.
        post_body: Post body (assembly proxy). Strike plate recesses into its face.
        rail_body: Rail body (assembly proxy). Hook plate recesses into its end.
        interface_axis: "x" or "y" — axis where the two boards meet.
        interface_coord: Float (cm) — coordinate on interface_axis where they meet.
        center_z: Float (cm) — Z center of the fastener.
        size: "80mm", "100mm", or "120mm".
        name: Feature name prefix.
        ev: Parameter evaluator (unused but kept for API consistency).
    """
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent
    VI = adsk.core.ValueInput.createByString
    P3 = adsk.core.Point3D

    iface = float(interface_coord)
    cz = float(center_z)
    other_axis = "y" if interface_axis == "x" else "x"

    # Find center of the post on the other axis
    post_bb = post_body.boundingBox
    other_center = (getattr(post_bb.minPoint, other_axis) +
                    getattr(post_bb.maxPoint, other_axis)) / 2

    # ================================================================
    # 1. Import STEP hardware into the design
    # ================================================================
    step_file = os.path.join(HARDWARE_DIR, f"bedlock_{size}.step")
    if not os.path.exists(step_file):
        print(f">>> ERROR: STEP file not found: {step_file}")
        print(f">>> Run tools/bed_rail_fastener.py first to generate hardware")
        return

    import_mgr = app.importManager
    step_opts = import_mgr.createSTEPImportOptions(step_file)
    # Import into the root component
    import_mgr.importToTarget2(step_opts, root)

    # Find the imported occurrence (most recent one added)
    hw_occ = root.occurrences.item(root.occurrences.count - 1)
    hw_comp = hw_occ.component
    print(f">>> Imported {size} hardware: {hw_comp.bRepBodies.count} bodies")

    # Identify hook plate and strike plate by volume (2 largest bodies)
    # and Y position (hook plate near Y=0, strike plate at Y>0 in STEP space)
    all_bodies = [(hw_comp.bRepBodies.item(i), hw_comp.bRepBodies.item(i).volume)
                  for i in range(hw_comp.bRepBodies.count)]
    all_bodies.sort(key=lambda x: -x[1])  # largest first
    plate_a, plate_b = all_bodies[0][0], all_bodies[1][0]

    # Hook plate is at Y≈0, strike plate at Y>0 in STEP space
    ya = (plate_a.boundingBox.minPoint.y + plate_a.boundingBox.maxPoint.y) / 2
    yb = (plate_b.boundingBox.minPoint.y + plate_b.boundingBox.maxPoint.y) / 2
    if ya < yb:
        hook_plate, strike_plate = plate_a, plate_b
    else:
        hook_plate, strike_plate = plate_b, plate_a

    print(f">>> Identified: hook plate vol={hook_plate.volume:.2f}, strike plate vol={strike_plate.volume:.2f}")

    # ================================================================
    # 2. Position the hardware at the joint interface using MoveFeature
    # ================================================================
    # The STEP hardware was generated flat on XY plane:
    #   STEP X = plate length direction
    #   STEP Y = plate width direction (hook plate at Y≈0, strike at Y≈5)
    #   STEP Z = plate thickness direction
    # We need to rotate + translate so:
    #   plate length → model Z (vertical)
    #   plate width → model other_axis
    #   plate thickness → model interface_axis

    hw_occ.component.name = f"{name}_Hardware"

    # Get hook plate center in STEP space for offset calculation
    hp_bb = hook_plate.boundingBox
    hp_cx = (hp_bb.minPoint.x + hp_bb.maxPoint.x) / 2
    hp_cy = (hp_bb.minPoint.y + hp_bb.maxPoint.y) / 2
    hp_cz_step = (hp_bb.minPoint.z + hp_bb.maxPoint.z) / 2

    # Collect all bodies in the hardware component for the Move
    move_coll = adsk.core.ObjectCollection.create()
    for i in range(hw_comp.bRepBodies.count):
        move_coll.add(hw_comp.bRepBodies.item(i))

    # Build rotation+translation matrix
    # For interface_axis="x": STEP_X→Z, STEP_Y→Y, STEP_Z→X
    # For interface_axis="y": STEP_X→Z, STEP_Y→X, STEP_Z→Y
    xf = adsk.core.Matrix3D.create()

    if interface_axis == "x":
        # Ry(-90°): STEP_X→model_Z, STEP_Y→model_Y, STEP_Z→-model_X
        # model X = -STEP_Z + tx, model Y = STEP_Y + ty, model Z = STEP_X + tz
        tx = iface + hp_cz_step
        ty = other_center - hp_cy
        tz = cz - hp_cx
        xf.setCell(0, 0, 0);  xf.setCell(0, 1, 0); xf.setCell(0, 2, -1); xf.setCell(0, 3, tx)
        xf.setCell(1, 0, 0);  xf.setCell(1, 1, 1); xf.setCell(1, 2, 0);  xf.setCell(1, 3, ty)
        xf.setCell(2, 0, 1);  xf.setCell(2, 1, 0); xf.setCell(2, 2, 0);  xf.setCell(2, 3, tz)
    else:
        # Rx(-90°): STEP_X→model_Z, STEP_Y→-model_Y, STEP_Z→model_X... not right
        # Actually: Rx(90°) then swap as needed. For now, handle x case first.
        # interface_axis="y": STEP_X→model_Z, STEP_Z→-model_Y, STEP_Y→model_X
        tx = other_center - hp_cy
        ty = iface + hp_cz_step
        tz = cz - hp_cx
        xf.setCell(0, 0, 0); xf.setCell(0, 1, 1);  xf.setCell(0, 2, 0);  xf.setCell(0, 3, tx)
        xf.setCell(1, 0, 0); xf.setCell(1, 1, 0);  xf.setCell(1, 2, -1); xf.setCell(1, 3, ty)
        xf.setCell(2, 0, 1); xf.setCell(2, 1, 0);  xf.setCell(2, 2, 0);  xf.setCell(2, 3, tz)

    move_inp = hw_comp.features.moveFeatures.createInput2(move_coll)
    move_inp.defineAsFreeMove(xf)
    hw_comp.features.moveFeatures.add(move_inp).name = f"{name}_Position"

    # ================================================================
    # 3. CUT recess pockets into the wood using the hardware bodies
    # ================================================================
    # Use the positioned hardware bodies as CUT tools
    hp_proxy = hook_plate.createForAssemblyContext(hw_occ)
    sp_proxy = strike_plate.createForAssemblyContext(hw_occ)

    # CUT hook plate shape into rail (creates recess pocket)
    af.combine(root, rail_body, [hp_proxy], CUT, True, f"{name}_HookRecess")

    # CUT strike plate shape into post (creates recess pocket)
    af.combine(root, post_body, [sp_proxy], CUT, True, f"{name}_StrikeRecess")

    print(f">>> {name}: {size} bedlock installed (STEP imported + recesses cut)")
