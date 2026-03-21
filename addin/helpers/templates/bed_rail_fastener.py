"""Bed rail fastener (mortise bedlock) installation template.

Imports hook plate and strike plate from SEPARATE STEP files, positions
each independently, and CUTs recess pockets into both boards.

INSTALLATION RULE:
  - Hook plate → RAIL end face (hooks face toward the post/leg)
  - Strike plate → POST/LEG side face (slots face toward the rail)
  - The post supports the rail: hooks on rail drop into slots on post
  - Hook hardware lives inside the Rail component
  - Strike hardware lives inside the Post component

STEP files at: ~/.autofusion/hardware/bed_rail_fastener/
Generate with: tools/bed_rail_fastener.py

Usage:
    from helpers.templates import bed_rail_fastener as brf

    # post_proxy is the POST body, rail_proxy is the RAIL body
    brf.install(root, post_proxy, rail_proxy,
                interface_axis="y", interface_coord=post_size_cm,
                center_z=rail_center_z_cm,
                size="100mm", name="BRF_RL_F", ev=ev)

    # Hardware auto-moves into parent components (Rails/Posts)
    # Templates go to hidden _HW in epilogue cleanup
"""

import adsk.core
import adsk.fusion
import os

from helpers import af
from helpers import hardware as hw_mgr

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
HARDWARE_DIR = os.path.expanduser("~/.autofusion/hardware/bed_rail_fastener")
PLATE_T = 0.25  # cm

# Module-level cache: import each plate STEP once, copy for each use
_plate_cache = {}  # key: (part_id,) → value: template occurrence


def install(comp, post_body, rail_body,
            interface_axis, interface_coord,
            center_z, size="100mm", name="BedRail", ev=None):
    """Install a bedlock pair from separate STEP files.

    Each plate is imported independently (or copied from cache),
    positioned with a simple Ry(90°) rotation, and used as a CUT
    tool to create the recess pocket.
    """
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent
    P3 = adsk.core.Point3D

    iface = float(interface_coord)
    cz = float(center_z)
    other_axis = "y" if interface_axis == "x" else "x"

    # Centers on the other axis (perpendicular to interface + Z)
    post_bb = post_body.boundingBox
    post_center = (getattr(post_bb.minPoint, other_axis) +
                   getattr(post_bb.maxPoint, other_axis)) / 2
    rail_bb = rail_body.boundingBox
    rail_center = (getattr(rail_bb.minPoint, other_axis) +
                   getattr(rail_bb.maxPoint, other_axis)) / 2

    # ================================================================
    # Import/copy each plate type independently
    # ================================================================
    hook_step = os.path.join(HARDWARE_DIR, f"hook_plate_{size}.step")
    strike_step = os.path.join(HARDWARE_DIR, f"strike_plate_{size}.step")

    if not os.path.exists(hook_step) or not os.path.exists(strike_step):
        print(f">>> ERROR: STEP files not found. Run tools/bed_rail_fastener.py first.")
        return

    # Import each plate STEP once, copy for subsequent uses
    def _get_or_import(part_id, step_file):
        global _plate_cache
        if part_id in _plate_cache:
            tmpl = _plate_cache[part_id]
            if tmpl.isValid:
                return hw_mgr._copy_from_template(tmpl, root)
        # First import — hidden template
        imported = hw_mgr.import_step(step_file, root)
        if not imported:
            return None
        tmpl_occ = imported[0][0]
        tmpl_occ.isLightBulbOn = False
        for bi in range(tmpl_occ.component.bRepBodies.count):
            tmpl_occ.component.bRepBodies.item(bi).isVisible = False
        _plate_cache[part_id] = tmpl_occ
        hw_mgr._hardware_occurrences.append((tmpl_occ, root))
        return hw_mgr._copy_from_template(tmpl_occ, root)

    hook_result = _get_or_import(f"hook_{size}", hook_step)
    strike_result = _get_or_import(f"strike_{size}", strike_step)

    if not hook_result or not strike_result:
        print(f">>> ERROR: STEP import/copy failed for {name}")
        return

    hook_occ, hook_bodies = hook_result[0]
    strike_occ, strike_bodies = strike_result[0]
    hook_comp = hook_occ.component
    strike_comp = strike_occ.component

    # Register installed copies for cleanup
    hw_mgr._hardware_occurrences.append((hook_occ, root))
    hw_mgr._hardware_occurrences.append((strike_occ, root))

    # Find the main plate body (largest volume) in each
    hook_plate = max(hook_bodies, key=lambda b: b.volume)
    strike_plate = max(strike_bodies, key=lambda b: b.volume)

    # Get STEP-space centers
    hp_bb = hook_plate.boundingBox
    hp_cx = (hp_bb.minPoint.x + hp_bb.maxPoint.x) / 2  # plate length center
    hp_cy = (hp_bb.minPoint.y + hp_bb.maxPoint.y) / 2  # plate width center

    sp_bb = strike_plate.boundingBox
    sp_cx = (sp_bb.minPoint.x + sp_bb.maxPoint.x) / 2
    sp_cy = (sp_bb.minPoint.y + sp_bb.maxPoint.y) / 2

    # ================================================================
    # Position each plate with simple Ry(90°)
    # Ry(90°): STEP_X→-Z, STEP_Y→Y, STEP_Z→+X  (det=+1)
    # This maps plate length to vertical, thickness to interface axis
    # ================================================================

    def move_plate(plate_comp, bodies_list, tx, ty, tz, plate_name):
        """Position a plate with Ry(90°) + translation."""
        xf = adsk.core.Matrix3D.create()
        if interface_axis == "x":
            # Ry(90°): model_X=STEP_Z, model_Y=STEP_Y, model_Z=-STEP_X
            xf.setCell(0, 0, 0);  xf.setCell(0, 1, 0); xf.setCell(0, 2, 1);  xf.setCell(0, 3, tx)
            xf.setCell(1, 0, 0);  xf.setCell(1, 1, 1); xf.setCell(1, 2, 0);  xf.setCell(1, 3, ty)
            xf.setCell(2, 0, -1); xf.setCell(2, 1, 0); xf.setCell(2, 2, 0);  xf.setCell(2, 3, tz)
        else:
            # Y-interface: STEP_Z→+Y, STEP_Y→-X, STEP_X→-Z  (det=+1)
            xf.setCell(0, 0, 0);  xf.setCell(0, 1, -1); xf.setCell(0, 2, 0);  xf.setCell(0, 3, tx)
            xf.setCell(1, 0, 0);  xf.setCell(1, 1, 0);  xf.setCell(1, 2, 1);  xf.setCell(1, 3, ty)
            xf.setCell(2, 0, -1); xf.setCell(2, 1, 0);  xf.setCell(2, 2, 0);  xf.setCell(2, 3, tz)

        coll = adsk.core.ObjectCollection.create()
        for b in bodies_list:
            coll.add(b)
        move_inp = plate_comp.features.moveFeatures.createInput2(coll)
        move_inp.defineAsFreeMove(xf)
        plate_comp.features.moveFeatures.add(move_inp).name = plate_name

    # STRIKE PLATE → in post face
    # STEP_Z=0 (base) goes to interface_axis = iface - PLATE_T (bottom of pocket)
    # STEP_Z=PLATE_T (outside face) goes to interface_axis = iface (flush with post face)
    if interface_axis == "x":
        move_plate(strike_comp, strike_bodies,
                   tx=iface - PLATE_T - sp_bb.minPoint.z,  # base at iface-t
                   ty=post_center - sp_cy,
                   tz=cz + sp_cx,
                   plate_name=f"{name}_StrikePos")
    else:
        move_plate(strike_comp, strike_bodies,
                   tx=post_center + sp_cy,   # -STEP_Y maps to +X
                   ty=iface - PLATE_T - sp_bb.minPoint.z,
                   tz=cz + sp_cx,
                   plate_name=f"{name}_StrikePos")

    # HOOK PLATE → in rail end face (use RAIL center, not post center)
    # STEP_Z=0 (base) at iface (rail end surface)
    if interface_axis == "x":
        move_plate(hook_comp, hook_bodies,
                   tx=iface - hp_bb.minPoint.z,
                   ty=rail_center - hp_cy,        # rail center, not post center
                   tz=cz + hp_cx,
                   plate_name=f"{name}_HookPos")
    else:
        move_plate(hook_comp, hook_bodies,
                   tx=rail_center + hp_cy,         # rail center, not post center
                   ty=iface - hp_bb.minPoint.z,
                   tz=cz + hp_cx,
                   plate_name=f"{name}_HookPos")

    # ================================================================
    # CUT recess pockets using the positioned plates
    # ================================================================
    # Strike plate CUTs into the post
    sp_proxy = strike_plate.createForAssemblyContext(strike_occ)
    af.combine(root, post_body, [sp_proxy], CUT, True, f"{name}_StrikeRecess")

    # Hook plate CUTs into the rail
    hp_proxy = hook_plate.createForAssemblyContext(hook_occ)
    af.combine(root, rail_body, [hp_proxy], CUT, True, f"{name}_HookRecess")

    # Name and move into parent components
    hook_comp.name = f"{name}_Hook"
    strike_comp.name = f"{name}_Strike"

    # Move hardware into the component of the board they're attached to
    # Hook plate → rail's parent component, Strike plate → post's parent component
    try:
        # Find parent occurrences by matching the body's parentComponent
        rail_parent_occ = None
        post_parent_occ = None
        for i in range(root.occurrences.count):
            occ = root.occurrences.item(i)
            if occ.component == rail_body.parentComponent:
                rail_parent_occ = occ
            if occ.component == post_body.parentComponent:
                post_parent_occ = occ

        if rail_parent_occ and hook_occ.isValid:
            hook_occ.moveToComponent(rail_parent_occ)
        if post_parent_occ and strike_occ.isValid:
            strike_occ.moveToComponent(post_parent_occ)
    except Exception:
        pass  # keep at root if move fails

    print(f">>> {name}: {size} bedlock — hook in rail, strike in post")
