"""Bed rail fastener (mortise bedlock) installation template.

INSTALLATION RULE:
  - Hook plate → RAIL end face (hooks face OUTWARD from rail, toward the post)
  - Strike plate → POST/LEG side face (slots face toward the rail)
  - Hardware auto-moves into a "Hardwares" sub-folder in the parent component
  - Templates hidden in _HW

STEP files at: ~/.shopprentice/hardware/bed_rail_fastener/
Generate with: dev/bed_rail_fastener.py
"""

import adsk.core
import adsk.fusion
import os

from helpers import sp
from helpers import hardware as hw_mgr

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
HARDWARE_DIR = os.path.expanduser("~/.shopprentice/hardware/bed_rail_fastener")
PLATE_T = 0.25  # cm

# Module-level cache: import each plate STEP once, copy for each use
_plate_cache = {}  # key: part_id → value: template occurrence


def install(comp, post_body, rail_body,
            interface_axis, interface_coord,
            center_z, size="100mm", name="BedRail", ev=None):
    """Install a bedlock pair. Hook in rail, strike in post."""
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent
    P3 = adsk.core.Point3D

    iface = float(interface_coord)
    cz = float(center_z)
    other_axis = "y" if interface_axis == "x" else "x"

    # Body centers on the other axis
    post_bb = post_body.boundingBox
    post_center = (getattr(post_bb.minPoint, other_axis) +
                   getattr(post_bb.maxPoint, other_axis)) / 2
    rail_bb = rail_body.boundingBox
    rail_center = (getattr(rail_bb.minPoint, other_axis) +
                   getattr(rail_bb.maxPoint, other_axis)) / 2

    # Determine which side of interface each body is on
    rail_iface_center = (getattr(rail_bb.minPoint, interface_axis) +
                         getattr(rail_bb.maxPoint, interface_axis)) / 2
    rail_on_positive_side = rail_iface_center > iface
    # Hooks face OUTWARD from rail = AWAY from rail center = TOWARD post
    # If rail is on +side of iface: hooks face -direction
    # If rail is on -side of iface: hooks face +direction
    hook_dir = -1 if rail_on_positive_side else +1

    # ================================================================
    # Import/copy plates
    # ================================================================
    hook_step = os.path.join(HARDWARE_DIR, f"hook_plate_{size}.step")
    strike_step = os.path.join(HARDWARE_DIR, f"strike_plate_{size}.step")

    if not os.path.exists(hook_step) or not os.path.exists(strike_step):
        print(f">>> ERROR: STEP files not found. Run dev/bed_rail_fastener.py first.")
        return

    def _get_or_import(part_id, step_file):
        global _plate_cache
        if part_id in _plate_cache:
            tmpl = _plate_cache[part_id]
            if tmpl.isValid:
                return hw_mgr._copy_from_template(tmpl, root)
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
    hw_mgr._hardware_occurrences.append((hook_occ, root))
    hw_mgr._hardware_occurrences.append((strike_occ, root))

    # Main plate bodies
    hook_plate = max(hook_bodies, key=lambda b: b.volume)
    strike_plate = max(strike_bodies, key=lambda b: b.volume)

    # STEP-space centers
    hp_bb = hook_plate.boundingBox
    hp_cx = (hp_bb.minPoint.x + hp_bb.maxPoint.x) / 2
    hp_cy = (hp_bb.minPoint.y + hp_bb.maxPoint.y) / 2

    sp_bb = strike_plate.boundingBox
    sp_cx = (sp_bb.minPoint.x + sp_bb.maxPoint.x) / 2
    sp_cy = (sp_bb.minPoint.y + sp_bb.maxPoint.y) / 2

    # ================================================================
    # Position plates with direction-aware rotation
    # ================================================================
    VI = adsk.core.ValueInput.createByString

    def move_bodies(plate_comp, bodies, matrix, plate_name):
        coll = adsk.core.ObjectCollection.create()
        for b in bodies:
            coll.add(b)
        move_inp = plate_comp.features.moveFeatures.createInput2(coll)
        move_inp.defineAsFreeMove(matrix)
        plate_comp.features.moveFeatures.add(move_inp).name = plate_name

    # HOOK PLATE — direction-aware rotation
    # hook_dir=+1: hooks face +interface_axis (STEP_Z → +iface_axis)
    # hook_dir=-1: hooks face -interface_axis (STEP_Z → -iface_axis)
    xf_hook = adsk.core.Matrix3D.create()
    if interface_axis == "x":
        if hook_dir > 0:
            # Ry(90°): STEP_Z→+X, hooks face +X
            tx = iface - PLATE_T - hp_bb.minPoint.z
            ty = rail_center - hp_cy
            tz = cz + hp_cx
            xf_hook.setCell(0,0,0); xf_hook.setCell(0,1,0); xf_hook.setCell(0,2,1);  xf_hook.setCell(0,3,tx)
            xf_hook.setCell(1,0,0); xf_hook.setCell(1,1,1); xf_hook.setCell(1,2,0);  xf_hook.setCell(1,3,ty)
            xf_hook.setCell(2,0,-1);xf_hook.setCell(2,1,0); xf_hook.setCell(2,2,0);  xf_hook.setCell(2,3,tz)
        else:
            # Ry(-90°): STEP_Z→-X, hooks face -X
            tx = iface + PLATE_T + hp_bb.minPoint.z
            ty = rail_center - hp_cy
            tz = cz - hp_cx
            xf_hook.setCell(0,0,0); xf_hook.setCell(0,1,0); xf_hook.setCell(0,2,-1); xf_hook.setCell(0,3,tx)
            xf_hook.setCell(1,0,0); xf_hook.setCell(1,1,1); xf_hook.setCell(1,2,0);  xf_hook.setCell(1,3,ty)
            xf_hook.setCell(2,0,1); xf_hook.setCell(2,1,0); xf_hook.setCell(2,2,0);  xf_hook.setCell(2,3,tz)
    else:  # Y-interface
        if hook_dir > 0:
            # STEP_Z→+Y, hooks face +Y
            tx = rail_center + hp_cy
            ty = iface - PLATE_T - hp_bb.minPoint.z
            tz = cz + hp_cx
            xf_hook.setCell(0,0,0); xf_hook.setCell(0,1,-1);xf_hook.setCell(0,2,0);  xf_hook.setCell(0,3,tx)
            xf_hook.setCell(1,0,0); xf_hook.setCell(1,1,0); xf_hook.setCell(1,2,1);  xf_hook.setCell(1,3,ty)
            xf_hook.setCell(2,0,-1);xf_hook.setCell(2,1,0); xf_hook.setCell(2,2,0);  xf_hook.setCell(2,3,tz)
        else:
            # STEP_Z→-Y, STEP_Y→-X, STEP_X→+Z (det=+1)
            tx = rail_center + hp_cy  # -STEP_Y→X, center at rail_center
            ty = iface + PLATE_T + hp_bb.minPoint.z
            tz = cz - hp_cx           # +STEP_X→Z
            xf_hook.setCell(0,0,0); xf_hook.setCell(0,1,-1); xf_hook.setCell(0,2,0);  xf_hook.setCell(0,3,tx)
            xf_hook.setCell(1,0,0); xf_hook.setCell(1,1,0);  xf_hook.setCell(1,2,-1); xf_hook.setCell(1,3,ty)
            xf_hook.setCell(2,0,1); xf_hook.setCell(2,1,0);  xf_hook.setCell(2,2,0);  xf_hook.setCell(2,3,tz)

    move_bodies(hook_comp, hook_bodies, xf_hook, f"{name}_HookPos")

    # STRIKE PLATE — faces toward rail (opposite direction from hooks)
    strike_dir = -hook_dir  # strike faces the opposite way from hooks
    xf_strike = adsk.core.Matrix3D.create()
    if interface_axis == "x":
        if strike_dir > 0:
            tx = iface - sp_bb.minPoint.z
            ty = post_center - sp_cy
            tz = cz + sp_cx
            xf_strike.setCell(0,0,0); xf_strike.setCell(0,1,0); xf_strike.setCell(0,2,1);  xf_strike.setCell(0,3,tx)
            xf_strike.setCell(1,0,0); xf_strike.setCell(1,1,1); xf_strike.setCell(1,2,0);  xf_strike.setCell(1,3,ty)
            xf_strike.setCell(2,0,-1);xf_strike.setCell(2,1,0); xf_strike.setCell(2,2,0);  xf_strike.setCell(2,3,tz)
        else:
            tx = iface + sp_bb.minPoint.z
            ty = post_center - sp_cy
            tz = cz - sp_cx
            xf_strike.setCell(0,0,0); xf_strike.setCell(0,1,0); xf_strike.setCell(0,2,-1); xf_strike.setCell(0,3,tx)
            xf_strike.setCell(1,0,0); xf_strike.setCell(1,1,1); xf_strike.setCell(1,2,0);  xf_strike.setCell(1,3,ty)
            xf_strike.setCell(2,0,1); xf_strike.setCell(2,1,0); xf_strike.setCell(2,2,0);  xf_strike.setCell(2,3,tz)
    else:  # Y-interface
        if strike_dir > 0:
            tx = post_center + sp_cy
            ty = iface - sp_bb.minPoint.z
            tz = cz + sp_cx
            xf_strike.setCell(0,0,0); xf_strike.setCell(0,1,-1);xf_strike.setCell(0,2,0);  xf_strike.setCell(0,3,tx)
            xf_strike.setCell(1,0,0); xf_strike.setCell(1,1,0); xf_strike.setCell(1,2,1);  xf_strike.setCell(1,3,ty)
            xf_strike.setCell(2,0,-1);xf_strike.setCell(2,1,0); xf_strike.setCell(2,2,0);  xf_strike.setCell(2,3,tz)
        else:
            # STEP_Z→-Y, STEP_Y→-X, STEP_X→+Z (det=+1)
            tx = post_center + sp_cy
            ty = iface + sp_bb.minPoint.z
            tz = cz - sp_cx
            xf_strike.setCell(0,0,0); xf_strike.setCell(0,1,-1); xf_strike.setCell(0,2,0);  xf_strike.setCell(0,3,tx)
            xf_strike.setCell(1,0,0); xf_strike.setCell(1,1,0);  xf_strike.setCell(1,2,-1); xf_strike.setCell(1,3,ty)
            xf_strike.setCell(2,0,1); xf_strike.setCell(2,1,0);  xf_strike.setCell(2,2,0);  xf_strike.setCell(2,3,tz)

    move_bodies(strike_comp, strike_bodies, xf_strike, f"{name}_StrikePos")

    # ================================================================
    # CUT recess pockets
    # ================================================================
    sp_proxy = strike_plate.createForAssemblyContext(strike_occ)
    sp.combine(post_body, [sp_proxy], CUT, True, f"{name}_StrikeRecess")

    hp_proxy = hook_plate.createForAssemblyContext(hook_occ)
    sp.combine(rail_body, [hp_proxy], CUT, True, f"{name}_HookRecess")

    # ================================================================
    # Move into parent components' "Hardwares" sub-folder
    # ================================================================
    hook_comp.name = f"{name}_Hook"
    strike_comp.name = f"{name}_Strike"

    try:
        rail_parent = None
        post_parent = None
        for i in range(root.occurrences.count):
            occ = root.occurrences.item(i)
            if occ.component == rail_body.parentComponent:
                rail_parent = occ
            if occ.component == post_body.parentComponent:
                post_parent = occ

        # Create or find "Hardwares" folder in each parent
        def _get_hw_folder(parent_occ):
            # Search by name in child occurrences
            for j in range(parent_occ.childOccurrences.count):
                ch = parent_occ.childOccurrences.item(j)
                if "Hardwares" in ch.component.name:
                    return ch
            hw = parent_occ.component.occurrences.addNewComponent(
                adsk.core.Matrix3D.create())
            hw.component.name = "Hardwares"
            return hw

        if rail_parent and hook_occ.isValid:
            rail_hw = _get_hw_folder(rail_parent)
            hook_occ.moveToComponent(rail_hw)
        if post_parent and strike_occ.isValid:
            post_hw = _get_hw_folder(post_parent)
            strike_occ.moveToComponent(post_hw)
    except Exception:
        pass

    print(f">>> {name}: {size} bedlock — hook in rail, strike in post (hooks face {'+'if hook_dir>0 else '-'}{interface_axis})")
