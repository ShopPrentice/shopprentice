"""
Export STEP Tool

Export selected occurrences (or named occurrences) as a single STEP file.
Supports flat export or hinge-assembly grouping (Pin, LeafA+screws, LeafB+screws).
"""

import traceback
import os
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register
import adsk.core
import adsk.fusion

app = adsk.core.Application.get()


def _copy_bodies(src_occ, dest_comp):
    """Copy all bodies from an occurrence into a component. Returns count."""
    comp = src_occ.component
    coll = adsk.core.ObjectCollection.create()
    for j in range(comp.bRepBodies.count):
        body = comp.bRepBodies.item(j)
        proxy = body.createForAssemblyContext(src_occ)
        coll.add(proxy)
    if coll.count > 0:
        dest_comp.features.copyPasteBodies.add(coll)
    return coll.count


def _classify_hinge_bodies_export(occ):
    """Classify hinge occurrence bodies into pin and leaves.

    Pin = smallest volume. Leaves sorted by volume descending
    (two largest bodies are the leaves).
    Returns (pin_indices, leaf_a_indices, leaf_b_indices, other_indices).
    Indices are into occ.component.bRepBodies.
    """
    comp = occ.component
    n = comp.bRepBodies.count
    bodies = [(i, comp.bRepBodies.item(i)) for i in range(n)]

    # Sort by volume
    bodies.sort(key=lambda ib: ib[1].volume)

    # Two largest are leaves, smallest is pin, rest are internals
    if n < 3:
        # Not enough bodies to classify — put all in one group
        return [b[0] for b in bodies], [], [], []

    pin_idx = [bodies[0][0]]

    # Leaves = two largest volume bodies
    leaf_candidates = bodies[-2:]  # two largest
    other_idxs = [b[0] for b in bodies[1:-2]]

    # Sort leaves by Z midpoint of their bounding box (proxy in world space)
    def z_mid(idx):
        body = comp.bRepBodies.item(idx)
        proxy = body.createForAssemblyContext(occ)
        bb = proxy.boundingBox
        return (bb.maxPoint.z + bb.minPoint.z) / 2

    leaf_a_idx, leaf_b_idx = leaf_candidates[1][0], leaf_candidates[0][0]
    # leaf_a = higher Z midpoint
    if z_mid(leaf_a_idx) < z_mid(leaf_b_idx):
        leaf_a_idx, leaf_b_idx = leaf_b_idx, leaf_a_idx

    return pin_idx, [leaf_a_idx], [leaf_b_idx], other_idxs


def _leaf_center(occ, body_idx):
    """Get world-space centroid of a leaf body."""
    body = occ.component.bRepBodies.item(body_idx)
    proxy = body.createForAssemblyContext(occ)
    bb = proxy.boundingBox
    return adsk.core.Point3D.create(
        (bb.minPoint.x + bb.maxPoint.x) / 2,
        (bb.minPoint.y + bb.maxPoint.y) / 2,
        (bb.minPoint.z + bb.maxPoint.z) / 2,
    )


def _screw_center(occ):
    """Get world-space centroid of a screw occurrence."""
    comp = occ.component
    body = comp.bRepBodies.item(0)
    proxy = body.createForAssemblyContext(occ)
    bb = proxy.boundingBox
    return adsk.core.Point3D.create(
        (bb.minPoint.x + bb.maxPoint.x) / 2,
        (bb.minPoint.y + bb.maxPoint.y) / 2,
        (bb.minPoint.z + bb.maxPoint.z) / 2,
    )


def _dist(p1, p2):
    return ((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (p1.z - p2.z)**2) ** 0.5


def _copy_body_indices(src_occ, indices, dest_comp):
    """Copy specific bodies (by index) from an occurrence into a component."""
    comp = src_occ.component
    coll = adsk.core.ObjectCollection.create()
    for idx in indices:
        body = comp.bRepBodies.item(idx)
        proxy = body.createForAssemblyContext(src_occ)
        coll.add(proxy)
    if coll.count > 0:
        dest_comp.features.copyPasteBodies.add(coll)
    return coll.count


def _export_flat(root, occs_to_export, output_path, lines):
    """Flat export — all bodies in one component."""
    tmp_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    tmp_comp = tmp_occ.component
    tmp_comp.name = "_ExportTemp"

    copied = 0
    for occ in occs_to_export:
        copied += _copy_bodies(occ, tmp_comp)

    export_mgr = adsk.fusion.Design.cast(app.activeProduct).exportManager
    opts = export_mgr.createSTEPExportOptions(output_path, tmp_comp)
    ok = export_mgr.execute(opts)
    tmp_occ.deleteMe()
    return ok, copied


def _export_hinge_assembly(root, occs_to_export, output_path, lines):
    """Structured export — Pin, LeafA+screws, LeafB+screws sub-components."""
    # Separate hinge occurrence from screw occurrences
    # Hinge = the one with the most bodies
    hinge_occ = max(occs_to_export, key=lambda o: o.component.bRepBodies.count)
    screw_occs = [o for o in occs_to_export if o is not hinge_occ]

    # Classify hinge bodies
    pin_idxs, leaf_a_idxs, leaf_b_idxs, other_idxs = \
        _classify_hinge_bodies_export(hinge_occ)

    # Get leaf centers for screw assignment
    center_a = _leaf_center(hinge_occ, leaf_a_idxs[0]) if leaf_a_idxs else None
    center_b = _leaf_center(hinge_occ, leaf_b_idxs[0]) if leaf_b_idxs else None

    # Assign each screw to nearest leaf
    screws_a = []
    screws_b = []
    for sc_occ in screw_occs:
        sc_center = _screw_center(sc_occ)
        if center_a and center_b:
            if _dist(sc_center, center_a) <= _dist(sc_center, center_b):
                screws_a.append(sc_occ)
            else:
                screws_b.append(sc_occ)
        elif center_a:
            screws_a.append(sc_occ)
        else:
            screws_b.append(sc_occ)

    lines.append(f"  Hinge: {hinge_occ.fullPathName}")
    lines.append(f"    Pin: {len(pin_idxs)} bodies, "
                 f"Other internals: {len(other_idxs)} bodies")
    lines.append(f"    LeafA: {len(leaf_a_idxs)} body + {len(screws_a)} screws")
    lines.append(f"    LeafB: {len(leaf_b_idxs)} body + {len(screws_b)} screws")

    # Create assembly structure
    identity = adsk.core.Matrix3D.create()
    tmp_occ = root.occurrences.addNewComponent(identity)
    tmp_comp = tmp_occ.component
    tmp_comp.name = "_ExportTemp"

    # Sub-component: Pin + other internals
    pin_sub_occ = tmp_comp.occurrences.addNewComponent(identity)
    pin_sub = pin_sub_occ.component
    pin_sub.name = "Pin"
    _copy_body_indices(hinge_occ, pin_idxs + other_idxs, pin_sub)

    # Sub-component: LeafA + its screws
    la_sub_occ = tmp_comp.occurrences.addNewComponent(identity)
    la_sub = la_sub_occ.component
    la_sub.name = "LeafA"
    _copy_body_indices(hinge_occ, leaf_a_idxs, la_sub)
    for sc_occ in screws_a:
        _copy_bodies(sc_occ, la_sub)

    # Sub-component: LeafB + its screws
    lb_sub_occ = tmp_comp.occurrences.addNewComponent(identity)
    lb_sub = lb_sub_occ.component
    lb_sub.name = "LeafB"
    _copy_body_indices(hinge_occ, leaf_b_idxs, lb_sub)
    for sc_occ in screws_b:
        _copy_bodies(sc_occ, lb_sub)

    copied = (len(pin_idxs) + len(other_idxs) + len(leaf_a_idxs)
              + len(leaf_b_idxs) + len(screw_occs))

    export_mgr = adsk.fusion.Design.cast(app.activeProduct).exportManager
    opts = export_mgr.createSTEPExportOptions(output_path, tmp_comp)
    ok = export_mgr.execute(opts)
    tmp_occ.deleteMe()
    return ok, copied


def handler(output_path: str, occurrences: str = "",
            grouping: str = "flat") -> dict:
    """Export occurrences as a STEP file.

    If occurrences is empty, exports the current UI selection.
    Otherwise, occurrences is a comma-separated list of full path names.

    grouping:
      "flat" — all bodies in one component (default)
      "hinge" — sub-components: Pin, LeafA+screws, LeafB+screws
    """
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return _error("No active Fusion design")

        root = design.rootComponent

        # Resolve which occurrences to export
        occs_to_export = []

        if occurrences.strip():
            names = [n.strip() for n in occurrences.split(",") if n.strip()]
            all_occs = root.allOccurrences
            for i in range(all_occs.count):
                occ = all_occs.item(i)
                if occ.fullPathName in names:
                    occs_to_export.append(occ)
        else:
            ui = app.userInterface
            sels = ui.activeSelections
            for i in range(sels.count):
                ent = sels.item(i)
                occ = adsk.fusion.Occurrence.cast(ent)
                if occ:
                    occs_to_export.append(occ)

        if not occs_to_export:
            return _error(
                "Nothing to export. Select occurrences in the UI, "
                "or pass occurrence paths via the 'occurrences' parameter."
            )

        # Log
        lines = []
        for occ in occs_to_export:
            n = occ.component.bRepBodies.count
            lines.append(f"  {occ.fullPathName} ({n} bodies)")

        # Ensure output directory exists
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        # Export based on grouping mode
        if grouping == "hinge":
            ok, copied = _export_hinge_assembly(
                root, occs_to_export, output_path, lines)
        else:
            ok, copied = _export_flat(
                root, occs_to_export, output_path, lines)

        if not ok:
            return _error("STEP export failed")

        sz = os.path.getsize(output_path)
        summary = (
            f"Exported {copied} bodies ({grouping} mode)\n"
            + "\n".join(lines)
            + f"\n\nFile: {output_path} ({sz:,} bytes)"
        )

        return {
            "content": [{"type": "text", "text": summary}],
            "isError": False,
            "message": f"Exported {output_path} ({sz:,} bytes)",
        }

    except Exception as e:
        app.log(f"export_step error: {e}\n{traceback.format_exc()}")
        return _error(f"{e}\n{traceback.format_exc()}")


def _error(msg):
    return {
        "content": [{"type": "text", "text": f"Error: {msg}"}],
        "isError": True,
        "message": str(msg),
    }


# ── Tool definition ─────────────────────────────────────────────────

TOOL_DESCRIPTION = """\
Export selected occurrences (or named occurrences) as a single STEP file.

Two grouping modes:
- **flat** (default): all bodies in one component.
- **hinge**: structured as sub-components — Pin, LeafA (+ its screws), \
LeafB (+ its screws). When a leaf moves, its screws move with it.

Two selection modes:
1. **Selection-based** (default): exports whatever the user has selected.
2. **Name-based**: pass comma-separated occurrence full path names.
"""

tool = Tool.create_simple(
    name="export_step",
    description=TOOL_DESCRIPTION,
).add_input_property(
    "output_path",
    {
        "description": "Absolute file path for the exported STEP file.",
        "type": "string",
    },
).add_required_input(
    "output_path",
).add_input_property(
    "occurrences",
    {
        "description": (
            "Comma-separated full path names of occurrences to export. "
            "Leave empty to export the current UI selection."
        ),
        "type": "string",
        "default": "",
    },
).add_input_property(
    "grouping",
    {
        "description": (
            "Grouping mode: 'flat' = all bodies in one component. "
            "'hinge' = sub-components: Pin, LeafA+screws, LeafB+screws."
        ),
        "type": "string",
        "enum": ["flat", "hinge"],
        "default": "flat",
    },
)

item = Item.create_tool_item(
    tool=tool,
    handler=handler,
)

register(item)
