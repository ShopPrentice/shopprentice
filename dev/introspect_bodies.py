"""
Fusion 360 Body Geometry Introspection

Dumps the final-state geometry of every body in the design:
bounding box, volume, centroid, faces with normals/points.
Also captures occurrence transforms for component positioning.

Output is JSON, keyed by component → body.
"""
import adsk.core, adsk.fusion
import json


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent

    out = {
        "designName": design.rootComponent.name,
        "components": [],
    }

    def dump_body(body, occ=None):
        """Dump a single body's geometry."""
        info = {"name": body.name}

        try:
            bb = body.boundingBox
            info["bbMin"] = [round(bb.minPoint.x, 4), round(bb.minPoint.y, 4), round(bb.minPoint.z, 4)]
            info["bbMax"] = [round(bb.maxPoint.x, 4), round(bb.maxPoint.y, 4), round(bb.maxPoint.z, 4)]
            # Derived dimensions
            dx = bb.maxPoint.x - bb.minPoint.x
            dy = bb.maxPoint.y - bb.minPoint.y
            dz = bb.maxPoint.z - bb.minPoint.z
            info["size"] = [round(dx, 4), round(dy, 4), round(dz, 4)]
            info["center"] = [
                round((bb.minPoint.x + bb.maxPoint.x) / 2, 4),
                round((bb.minPoint.y + bb.maxPoint.y) / 2, 4),
                round((bb.minPoint.z + bb.maxPoint.z) / 2, 4),
            ]
        except:
            pass

        try:
            info["volume"] = round(body.volume, 4)
        except:
            pass

        # Key faces (up to 20 largest by area)
        faces = []
        try:
            face_list = []
            for i in range(body.faces.count):
                f = body.faces.item(i)
                try:
                    area = f.area
                    face_list.append((area, f))
                except:
                    pass
            # Sort by area descending, take top 20
            face_list.sort(key=lambda x: -x[0])
            for area, f in face_list[:20]:
                face_info = {"area": round(area, 4)}
                try:
                    eva = f.evaluator
                    ok, pt, norm = eva.getNormalAtPoint(f.pointOnFace)
                    if ok:
                        face_info["normal"] = [round(norm.x, 4), round(norm.y, 4), round(norm.z, 4)]
                        face_info["point"] = [
                            round(f.pointOnFace.x, 4),
                            round(f.pointOnFace.y, 4),
                            round(f.pointOnFace.z, 4),
                        ]
                except:
                    pass
                faces.append(face_info)
        except:
            pass
        if faces:
            info["faces"] = faces

        return info

    def dump_comp(comp, occ=None):
        """Dump all bodies in a component, with occurrence transform."""
        comp_info = {
            "name": comp.name,
            "bodies": [],
            "children": [],
        }

        # Occurrence transform (world position of this component)
        if occ:
            try:
                t = occ.transform
                comp_info["transform"] = {
                    "translation": [
                        round(t.translation.x, 4),
                        round(t.translation.y, 4),
                        round(t.translation.z, 4),
                    ],
                    "matrix": [
                        [round(t.getCell(r, c), 6) for c in range(4)]
                        for r in range(4)
                    ],
                }
            except:
                pass

        # Bodies in this component
        for i in range(comp.bRepBodies.count):
            b = comp.bRepBodies.item(i)
            if not b.isVisible:
                continue
            comp_info["bodies"].append(dump_body(b, occ))

        # Child occurrences
        for i in range(comp.occurrences.count):
            child_occ = comp.occurrences.item(i)
            comp_info["children"].append(dump_comp(child_occ.component, child_occ))

        return comp_info

    out["components"] = dump_comp(root)

    print(json.dumps(out, indent=2))
