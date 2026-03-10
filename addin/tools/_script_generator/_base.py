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

        # Track which component each plane variable was created in
        self._plane_comps = {}  # plane var → component name

        # Track which component each sketch was created in ("root" or "comp")
        self._sketch_owners = {}  # sketch name → "root" or "comp"

        self._flipped_planes = set()  # reserved for future use

        # Track prior extrude distances for each face-based sketch.
        # Used to compute OffsetStartDefinition for sketch face-following variants.
        # Dict: sketch_key → list of distance strings (e.g., ["0.25 in", "0.25 in"])
        self._face_sketch_extrude_dists = {}

        # Current feature's component (set before each handler dispatch)
        self._current_comp = ""

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

    def _body_var(self, body_name):
        """Create component-scoped Python variable name for a body."""
        comp = self._current_comp
        if comp and comp != self._root_name:
            return self._var(f"{body_name}_{comp}")
        return self._var(body_name)

    def _register_body(self, body_name, var_name):
        """Register body variable with both plain and component-scoped keys."""
        if body_name in self.bodies and self.bodies[body_name] != var_name:
            self._prev_bodies[body_name] = self.bodies[body_name]
        self.bodies[body_name] = var_name
        comp = self._current_comp
        if comp and comp != self._root_name:
            self.bodies[f"{comp}:{body_name}"] = var_name

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
                if f.get("computeOption") == "Adjust":
                    self.needs.add("mirror_feats")
                    # Body-only Adjust mirrors use mirror_bodies for
                    # predictable body ordering — need both helpers.
                    self.needs.add("mirror_bodies")
                else:
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
        # Re-apply parametric expressions for deferred params (model param deps now exist)
        if getattr(self, "_deferred_params", None):
            self._section("DEFERRED PARAMETER EXPRESSIONS")
            for p in self._deferred_params:
                c = p.get("comment", "").replace("\n", " ").replace("\r", "").replace('"', '\\"')
                self._w("try:")
                self.ind += 1
                self._w(f'params.itemByName("{p["name"]}").expression = "{p["expression"]}"')
                self.ind -= 1
                self._w("except Exception:")
                self.ind += 1
                self._w("pass")
                self.ind -= 1
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

        # Known Fusion units / math tokens that are NOT parameter references
        _UNITS = {"in", "mm", "cm", "m", "ft", "deg", "rad", "pi"}

        primary, derived, deferred = [], [], []
        for p in params:
            expr = p["expression"]
            # Find all identifiers in expression
            idents = set(re.findall(r"\b([a-zA-Z_]\w*)\b", expr))
            refs_user = idents & names - {p["name"]}
            refs_external = idents - names - _UNITS - {p["name"]}
            if refs_external:
                # Depends on model params not yet available — use literal value
                deferred.append(p)
            elif refs_user:
                derived.append(p)
            else:
                primary.append(p)

        self._param_block(primary)
        if derived:
            self._w()
            self._param_block(derived)
        if deferred:
            self._w()
            self._w("# Deferred: depend on model parameters created by features")
            self._param_block_literal(deferred)
            self._deferred_params = deferred  # for post-feature expression update
        else:
            self._deferred_params = []

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

    def _param_block_literal(self, params):
        """Create params with literal values (for expressions with model param deps)."""
        for p in params:
            val = p.get("value", 0)
            unit = p["unit"]
            c = p.get("comment", "").replace("\n", " ").replace("\r", "").replace('"', '\\"')
            # value is in internal units (cm/rad); convert to a literal expression
            if unit in ("in",):
                literal = f"{val / 2.54} in"
            elif unit in ("mm",):
                literal = f"{val * 10} mm"
            elif unit in ("deg",):
                import math as _m
                literal = f"{_m.degrees(val)} deg"
            elif unit in ("ft",):
                literal = f"{val / 30.48} ft"
            else:
                literal = f"{val} cm" if unit else str(val)
            self._w(f'params.add("{p["name"]}", adsk.core.ValueInput.createByString("{literal}"), "{unit}", "{c}")')

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
        self.ind -= 2
        self._w("return None  # not found in specified component")
        self.ind -= 1
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
        self._c("Search proxied bodies by name for root-context faces")
        self._w("bodies = []")
        self._w("if body:")
        self.ind += 1
        self._w("bn = body.name")
        self._w("for i in range(root.bRepBodies.count):")
        self.ind += 1
        self._w("if root.bRepBodies.item(i).name == bn: bodies.append(root.bRepBodies.item(i))")
        self.ind -= 1
        self._w("for _occ in root.allOccurrences:")
        self.ind += 1
        self._w("for i in range(_occ.bRepBodies.count):")
        self.ind += 1
        self._w("if _occ.bRepBodies.item(i).name == bn: bodies.append(_occ.bRepBodies.item(i))")
        self.ind -= 2
        self._w("if not bodies: bodies = [body]")
        self.ind -= 1
        self._w("if not bodies:")
        self.ind += 1
        self._c("No body given — search all bodies via occurrence proxies")
        self._w("bodies = [root.bRepBodies.item(i) for i in range(root.bRepBodies.count)]")
        self._w("for _occ in root.allOccurrences:")
        self.ind += 1
        self._w("bodies.extend([_occ.bRepBodies.item(i) for i in range(_occ.bRepBodies.count)])")
        self.ind -= 2
        self._w("best, best_d = None, 1e10")
        self._w("def _search_faces(bl):")
        self.ind += 1
        self._w("nonlocal best, best_d")
        self._w("for _b in bl:")
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
        self.ind -= 4
        self._w("_search_faces(bodies)")
        self._c("Fallback: search all bodies if name-based search found no face")
        self._w("if best is None and body:")
        self.ind += 1
        self._w("_all = [root.bRepBodies.item(i) for i in range(root.bRepBodies.count)]")
        self._w("for _occ in root.allOccurrences:")
        self.ind += 1
        self._w("_all.extend([_occ.bRepBodies.item(i) for i in range(_occ.bRepBodies.count)])")
        self.ind -= 1
        self._w("_search_faces(_all)")
        self.ind -= 1
        self._w("return best")
        self.ind -= 1

        # find_face_in_comp — search only a component's native bodies.
        # Used for BRepFace sketches that need auto-projection of all
        # intersecting bodies (requires sketch to be in the component).
        self._w()
        self._w("def find_face_in_comp(comp, px, py, pz, nx=0, ny=0, nz=0):")
        self.ind += 1
        self._w("best, best_d = None, 1e10")
        self._w("for bi in range(comp.bRepBodies.count):")
        self.ind += 1
        self._w("_b = comp.bRepBodies.item(bi)")
        self._w("for fi in range(_b.faces.count):")
        self.ind += 1
        self._w("f = _b.faces.item(fi)")
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
            self._w("if target is None: return None  # no valid target body")
            self._w("coll = adsk.core.ObjectCollection.create()")
            self._w("for b in (tools if isinstance(tools, list) else [tools]):")
            self.ind += 1
            self._w("if b is not None: coll.add(b)")
            self.ind -= 1
            self._w("if coll.count == 0: return None  # no valid tool bodies")
            self._w("try:")
            self.ind += 1
            self._w("inp = comp.features.combineFeatures.createInput(target, coll)")
            self._w("inp.operation = op")
            self._w("inp.isKeepToolBodies = keep")
            self._w("f = comp.features.combineFeatures.add(inp)")
            self._w("f.name = name")
            self._w("return f")
            self.ind -= 1
            self._w("except RuntimeError:")
            self.ind += 1
            self._w("pass")
            self.ind -= 1
            self._c("Cross-component fallback: proxy bodies via occurrences, combine at root")
            self._w("def _proxy(b):")
            self.ind += 1
            self._w("pc = b.parentComponent")
            self._w("for _occ in root.allOccurrences:")
            self.ind += 1
            self._w("if _occ.component.name == pc.name:")
            self.ind += 1
            self._w("for i in range(_occ.bRepBodies.count):")
            self.ind += 1
            self._w("if _occ.bRepBodies.item(i).name == b.name: return _occ.bRepBodies.item(i)")
            self.ind -= 3
            self._w("return b")
            self.ind -= 1
            self._w("try:")
            self.ind += 1
            self._w("pt = _proxy(target)")
            self._w("pcoll = adsk.core.ObjectCollection.create()")
            self._w("for b in (tools if isinstance(tools, list) else [tools]):")
            self.ind += 1
            self._w("if b is not None: pcoll.add(_proxy(b))")
            self.ind -= 1
            self._w("if pcoll.count == 0: return None")
            self._w("inp = root.features.combineFeatures.createInput(pt, pcoll)")
            self._w("inp.operation = op")
            self._w("inp.isKeepToolBodies = keep")
            self._w("f = root.features.combineFeatures.add(inp)")
            self._w("f.name = name")
            self._w("return f")
            self.ind -= 1
            self._w("except RuntimeError:")
            self.ind += 1
            self._w("return None  # combine failed even with proxied bodies")
            self.ind -= 2

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

        if "mirror_feats" in self.needs:
            self._w()
            self._w('def mirror_feats(comp, entities, plane, name="Mir"):')
            self.ind += 1
            self._w("coll = adsk.core.ObjectCollection.create()")
            self._w("for e in entities: coll.add(e)")
            self._w("inp = comp.features.mirrorFeatures.createInput(coll, plane)")
            self._w("inp.computeOption = adsk.fusion.PatternComputeOptions.AdjustPatternCompute")
            self._w("m = comp.features.mirrorFeatures.add(inp)")
            self._w("m.name = name")
            self._w("return m")
            self.ind -= 1
