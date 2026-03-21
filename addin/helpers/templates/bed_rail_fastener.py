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

    # Separate bodies into hook plate group (Y≈0) and strike plate group (Y>2)
    sp_bb = strike_plate.boundingBox
    sp_cy = (sp_bb.minPoint.y + sp_bb.maxPoint.y) / 2
    threshold_y = sp_cy / 2  # midpoint between the two plate groups

    hook_bodies = adsk.core.ObjectCollection.create()
    strike_bodies = adsk.core.ObjectCollection.create()
    for i in range(hw_comp.bRepBodies.count):
        b = hw_comp.bRepBodies.item(i)
        by = (b.boundingBox.minPoint.y + b.boundingBox.maxPoint.y) / 2
        if by < threshold_y:
            hook_bodies.add(b)
        else:
            strike_bodies.add(b)

    sp_cx = (sp_bb.minPoint.x + sp_bb.maxPoint.x) / 2

    # Step 1: Ry(-90°) for ALL bodies — makes plate vertical (STEP_X→+Z, STEP_Z→-X)
    # Then Step 2: Rx(180°) for ALL bodies — flips so hooks point DOWN (Z→-Z, Y→-Y)
    # Combined: Rx(180°)·Ry(-90°)
    # = [-1,0,0]   [0,0,-1]   [0, 0, 1]
    #   [0,-1,0] × [0,1, 0] = [0,-1, 0]
    #   [0,0, 1]   [1,0, 0]   [1, 0, 0]
    # model_X = STEP_Z, model_Y = -STEP_Y, model_Z = STEP_X  (det=+1 ✓)
    # Hooks at +STEP_X → +model_Z → UP. Not down! Need the other combo.
    #
    # Try: Rx(180°)·Ry(90°)
    # = [-1,0,0]   [0, 0,1]   [0,  0,-1]
    #   [0,-1,0] × [0, 1,0] = [0, -1, 0]
    #   [0, 0,1]   [-1,0,0]   [-1, 0, 0]
    # model_X = -STEP_Z, model_Y = -STEP_Y, model_Z = -STEP_X  (det=+1 ✓)
    # Hooks at +STEP_X → -model_Z → DOWN ✓
    # Outside face +STEP_Z → -model_X → hooks toward post ✓ (for hook plate)

    # HOOK PLATE: Rx(180°)·Ry(90°) + translation
    xf_hook = adsk.core.Matrix3D.create()
    if interface_axis == "x":
        tx_h = iface + PLATE_T         # -STEP_Z=0 + tx = iface+t → base inside rail
        ty_h = other_center + hp_cy    # -STEP_Y + ty = other_center → ty = oc + hp_cy
        tz_h = cz + hp_cx             # -STEP_X + tz = cz → tz = cz + hp_cx
        xf_hook.setCell(0, 0, 0);  xf_hook.setCell(0, 1, 0);  xf_hook.setCell(0, 2, -1); xf_hook.setCell(0, 3, tx_h)
        xf_hook.setCell(1, 0, 0);  xf_hook.setCell(1, 1, -1); xf_hook.setCell(1, 2, 0);  xf_hook.setCell(1, 3, ty_h)
        xf_hook.setCell(2, 0, -1); xf_hook.setCell(2, 1, 0);  xf_hook.setCell(2, 2, 0);  xf_hook.setCell(2, 3, tz_h)
    else:  # interface_axis == "y"
        # Hook plate: STEP_Z→-Y (hooks toward post), STEP_X→-Z (hooks down), STEP_Y→X
        tx_h = other_center - hp_cy
        ty_h = iface + PLATE_T
        tz_h = cz + hp_cx
        xf_hook.setCell(0, 0, 0);  xf_hook.setCell(0, 1, 1);  xf_hook.setCell(0, 2, 0);  xf_hook.setCell(0, 3, tx_h)
        xf_hook.setCell(1, 0, 0);  xf_hook.setCell(1, 1, 0);  xf_hook.setCell(1, 2, -1); xf_hook.setCell(1, 3, ty_h)
        xf_hook.setCell(2, 0, -1); xf_hook.setCell(2, 1, 0);  xf_hook.setCell(2, 2, 0);  xf_hook.setCell(2, 3, tz_h)

    move_hook = hw_comp.features.moveFeatures.createInput2(hook_bodies)
    move_hook.defineAsFreeMove(xf_hook)
    hw_comp.features.moveFeatures.add(move_hook).name = f"{name}_HookPos"

    # STRIKE PLATE: Ry(90°) only (no X flip — slots face +X toward rail)
    # model_X = STEP_Z, model_Y = STEP_Y, model_Z = -STEP_X  (det=+1 ✓)
    # Hooks/slots at same -STEP_X → same model_Z ✓ (aligned!)
    # But wait — strike Y is NOT flipped, hook Y IS flipped. Different Y centers.
    # Hook: model_Y = -STEP_Y + ty = -0 + ty = other_center → OK (hp_cy≈0)
    # Strike: model_Y = STEP_Y + ty = sp_cy + ty = other_center → ty = oc - sp_cy
    xf_strike = adsk.core.Matrix3D.create()
    if interface_axis == "x":
        tx_s = iface - PLATE_T          # STEP_Z=0 + tx = iface-t → base inside post
        ty_s = other_center - sp_cy    # STEP_Y=sp_cy + ty = other_center
        tz_s = cz + sp_cx             # -STEP_X + tz = cz → tz = cz + sp_cx
        xf_strike.setCell(0, 0, 0);  xf_strike.setCell(0, 1, 0); xf_strike.setCell(0, 2, 1);  xf_strike.setCell(0, 3, tx_s)
        xf_strike.setCell(1, 0, 0);  xf_strike.setCell(1, 1, 1); xf_strike.setCell(1, 2, 0);  xf_strike.setCell(1, 3, ty_s)
        xf_strike.setCell(2, 0, -1); xf_strike.setCell(2, 1, 0); xf_strike.setCell(2, 2, 0);  xf_strike.setCell(2, 3, tz_s)
    else:  # interface_axis == "y"
        # Strike plate: STEP_Z→+Y (slots face rail), STEP_X→-Z (aligned with hooks), STEP_Y→-X
        tx_s = other_center + sp_cy   # Y flipped
        ty_s = iface - PLATE_T
        tz_s = cz + sp_cx
        xf_strike.setCell(0, 0, 0);  xf_strike.setCell(0, 1, -1); xf_strike.setCell(0, 2, 0);  xf_strike.setCell(0, 3, tx_s)
        xf_strike.setCell(1, 0, 0);  xf_strike.setCell(1, 1, 0);  xf_strike.setCell(1, 2, 1);  xf_strike.setCell(1, 3, ty_s)
        xf_strike.setCell(2, 0, -1); xf_strike.setCell(2, 1, 0);  xf_strike.setCell(2, 2, 0);  xf_strike.setCell(2, 3, tz_s)

    move_strike = hw_comp.features.moveFeatures.createInput2(strike_bodies)
    move_strike.defineAsFreeMove(xf_strike)
    hw_comp.features.moveFeatures.add(move_strike).name = f"{name}_StrikePos"

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
