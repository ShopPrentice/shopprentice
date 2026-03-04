"""Base mixin: instance state, output helpers, script structure."""

import copy
import re


class _BaseMixin:
    """Instance state initialisation, output primitives, and script structure.

    Listed last in _Generator's MRO so __init__ is the canonical initialiser.
    Calls _fixup_split_body_names / _fixup_body_references from _CoreMixin
    via MRO (they exist on self at runtime).
    """

    def __init__(self, capture):
        # Deep-copy timeline so preprocessing can mutate body names safely
        self.cap = dict(capture)
        self.cap["timeline"] = copy.deepcopy(capture.get("timeline", []))
        self.out = []       # accumulated lines
        self.ind = 1        # indent level (inside run())

        # Entity name → Python variable
        self.planes = {}    # construction plane name → var
        self.sketches = {}  # sketch name → var (the Sketch object)
        self.profiles = {}  # sketch name → var (the profile used by next feature)
        self.bodies = {}    # body name → var
        self.feats = {}     # feature name → var
        self.components = {} # component name → var (e.g., "posts" → "posts_c")
        self._root_name = capture.get("designName", "")  # root component name

        # Track BRepFace sketch info for CUT extrude direction fixing
        self._brep_face_sketches = {}  # sketch name → plane_info dict

        # Track which helpers the timeline needs
        self.needs = set()

        # Track overwritten body variables (when two extrudes create same-name body)
        self._prev_bodies = {}  # body_name → previous var (before overwrite)

        # Fix body names — calls _CoreMixin methods via MRO
        self._fixup_split_body_names()
        self._fixup_body_references()

    # ── Output primitives ──

    def _w(self, text=""):
        self.out.append("    " * self.ind + text if text else "")

    def _c(self, text):
        self._w(f"# {text}")

    def _section(self, title):
        self._w()
        bar = "─" * max(1, 58 - len(title))
        self._c(f"── {title} {bar}")

    def _var(self, name):
        """Sanitise entity name → Python identifier."""
        v = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        v = re.sub(r"_+", "_", v).strip("_")
        if not v or v[0].isdigit():
            v = "v_" + v
        return v

    # ── Scanning ──

    def _scan_needs(self):
        for f in self.cap.get("timeline", []):
            t = f.get("type")
            if t == "ConstructionPlane":
                self.needs.add("off_plane")
            elif t in ("Sketch", "Extrude", "Sweep"):
                self.needs.add("ev")
                # BRepFace sketches need off_plane for construction plane replacement
                if t == "Sketch":
                    plane = f.get("plane", {})
                    if (plane.get("type") == "BRepFace"
                            and "sketchOrigin" in f
                            and "sketchXDir" in f
                            and "sketchYDir" in f):
                        self.needs.add("off_plane")
            elif t == "Combine":
                self.needs.add("combine")
            elif t == "Mirror":
                self.needs.add("mirror_bodies")

    # ── Header / Footer ──

    def _header(self):
        name = self.cap.get("designName", "Untitled")
        self.out.append(f'"""Generated from capture_design \u2014 {name}')
        self.out.append('NOTE: Auto-generated. Features marked TODO need manual review."""')
        self.out.append("import adsk.core, adsk.fusion, math")
        self.out.append("")
        self.out.append("")
        self.out.append("def run(context):")
        self._w("app = adsk.core.Application.get()")
        self._w("design = adsk.fusion.Design.cast(app.activeProduct)")
        self._w("design.designType = adsk.fusion.DesignTypes.ParametricDesignType")
        self._w("root = design.rootComponent")
        self._w("params = design.userParameters")

    def _footer(self):
        self._section("FIT VIEW")
        self._w("cam = app.activeViewport.camera")
        self._w("cam.isFitView = True")
        self._w("app.activeViewport.camera = cam")

    # ── Parameters ──

    def _parameters(self):
        params = self.cap.get("userParameters", [])
        if not params:
            return
        self._section("PARAMETERS")
        names = {p["name"] for p in params}

        primary, derived = [], []
        for p in params:
            expr = p["expression"]
            is_ref = any(
                pn != p["name"] and re.search(r"\b" + re.escape(pn) + r"\b", expr)
                for pn in names
            )
            (derived if is_ref else primary).append(p)

        self._param_block(primary)
        if derived:
            self._w()
            self._param_block(derived)

    def _param_block(self, params):
        self._w("for name, expr, unit, comment in [")
        self.ind += 1
        for p in params:
            c = p.get("comment", "").replace("\n", " ").replace("\r", "").replace('"', '\\"')
            self._w(f'("{p["name"]}", "{p["expression"]}", "{p["unit"]}", "{c}"),')
        self.ind -= 1
        self._w("]:")
        self.ind += 1
        self._w("params.add(name, adsk.core.ValueInput.createByString(expr), unit, comment)")
        self.ind -= 1

    # ── Helpers ──

    def _helpers(self):
        self._section("HELPERS")
        self._w("P = adsk.core.Point3D.create")
        self._w("H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation")
        self._w("V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation")
        self._w("NEWBODY = adsk.fusion.FeatureOperations.NewBodyFeatureOperation")
        self._w("CUT = adsk.fusion.FeatureOperations.CutFeatureOperation")
        self._w("JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation")

        if "ev" in self.needs:
            self._w()
            self._w("def ev(e):")
            self.ind += 1
            self._w("p = params.itemByName(e)")
            self._w('return p.value if p else design.unitsManager.evaluateExpression(e, "cm")')
            self.ind -= 1

        if "off_plane" in self.needs:
            self._w()
            self._w('def off_plane(comp, base, expr, name="Pl"):')
            self.ind += 1
            self._w("inp = comp.constructionPlanes.createInput()")
            self._w("inp.setByOffset(base, adsk.core.ValueInput.createByString(expr))")
            self._w("p = comp.constructionPlanes.add(inp)")
            self._w("p.name = name")
            self._w("return p")
            self.ind -= 1

        # find_body — searches comp first (native), then root+occurrences (proxied)
        self._w()
        self._w("def find_body(name, search_comp=None):")
        self.ind += 1
        self._w("if search_comp:")
        self.ind += 1
        self._w("for i in range(search_comp.bRepBodies.count):")
        self.ind += 1
        self._w("if search_comp.bRepBodies.item(i).name == name:")
        self.ind += 1
        self._w("return search_comp.bRepBodies.item(i)")
        self.ind -= 3
        self._w("for i in range(root.bRepBodies.count):")
        self.ind += 1
        self._w("if root.bRepBodies.item(i).name == name:")
        self.ind += 1
        self._w("return root.bRepBodies.item(i)")
        self.ind -= 2
        self._w("for occ in root.allOccurrences:")
        self.ind += 1
        self._w("for i in range(occ.bRepBodies.count):")
        self.ind += 1
        self._w("if occ.bRepBodies.item(i).name == name:")
        self.ind += 1
        self._w("return occ.bRepBodies.item(i)")
        self.ind -= 3
        self._w("return None")
        self.ind -= 1

        # find_face — for face-based sketches and sweeps
        self._w()
        self._w("def find_face(body, axis, direction):")
        self.ind += 1
        self._w("best, best_val = None, (-1e10 if direction > 0 else 1e10)")
        self._w("for i in range(body.faces.count):")
        self.ind += 1
        self._w("f = body.faces.item(i)")
        self._w("if isinstance(f.geometry, adsk.core.Plane) and abs(getattr(f.geometry.normal, axis)) > 0.9:")
        self.ind += 1
        self._w("fv = getattr(f.pointOnFace, axis)")
        self._w("if (direction > 0 and fv > best_val) or (direction < 0 and fv < best_val):")
        self.ind += 1
        self._w("best, best_val = f, fv")
        self.ind -= 3
        self._w("return best")
        self.ind -= 1

        # find_face_near — select face by pointOnFace proximity + normal axis
        # If body is None, search ALL bodies in the design.
        self._w()
        self._w("def find_face_near(body, px, py, pz, nx=0, ny=0, nz=0):")
        self.ind += 1
        self._w("bodies = [body] if body else []")
        self._w("if not bodies:")
        self.ind += 1
        self._c("Search all bodies via occurrence proxies (root context)")
        self._w("bodies = [root.bRepBodies.item(i) for i in range(root.bRepBodies.count)]")
        self._w("for _occ in root.allOccurrences:")
        self.ind += 1
        self._w("bodies.extend([_occ.bRepBodies.item(i) for i in range(_occ.bRepBodies.count)])")
        self.ind -= 2
        self._w("best, best_d = None, 1e10")
        self._w("for _b in bodies:")
        self.ind += 1
        self._w("for i in range(_b.faces.count):")
        self.ind += 1
        self._w("f = _b.faces.item(i)")
        self._w("if isinstance(f.geometry, adsk.core.Plane):")
        self.ind += 1
        self._w("n = f.geometry.normal")
        self._w("if nx or ny or nz:")
        self.ind += 1
        self._w("if abs(abs(n.x*nx+n.y*ny+n.z*nz) - 1.0) > 0.1: continue")
        self.ind -= 1
        self._w("p = f.pointOnFace")
        self._w("d = abs(p.x - px) + abs(p.y - py) + abs(p.z - pz)")
        self._w("if d < best_d: best, best_d = f, d")
        self.ind -= 3
        self._w("return best")
        self.ind -= 1

        if "combine" in self.needs:
            self._w()
            self._w('def combine(comp, target, tools, op, keep, name="Comb"):')
            self.ind += 1
            self._w("coll = adsk.core.ObjectCollection.create()")
            self._w("for b in (tools if isinstance(tools, list) else [tools]): coll.add(b)")
            self._w("inp = comp.features.combineFeatures.createInput(target, coll)")
            self._w("inp.operation = op")
            self._w("inp.isKeepToolBodies = keep")
            self._w("f = comp.features.combineFeatures.add(inp)")
            self._w("f.name = name")
            self._w("return f")
            self.ind -= 1

        if "mirror_bodies" in self.needs:
            self._w()
            self._w('def mirror_bodies(comp, bodies, plane, name="Mir"):')
            self.ind += 1
            self._w("coll = adsk.core.ObjectCollection.create()")
            self._w("for b in bodies: coll.add(b)")
            self._w("inp = comp.features.mirrorFeatures.createInput(coll, plane)")
            self._w("m = comp.features.mirrorFeatures.add(inp)")
            self._w("m.name = name")
            self._w("return m")
            self.ind -= 1
