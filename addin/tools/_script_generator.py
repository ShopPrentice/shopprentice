"""
Script Generator — template-based code generation from capture_design output.

Reads the structured JSON from capture_design and emits a standalone Fusion 360
Python script that recreates the model. The generated script is self-contained
(no af.py dependency) and uses parametric expressions from the captured dimensions.

Usage:
    from ._script_generator import generate_script
    script_text = generate_script(capture_data)
"""

import re


def generate_script(capture):
    """Generate a standalone Fusion 360 script from capture_design JSON."""
    return _Generator(capture).generate()


class _Generator:
    """Walks capture_design output and emits a Fusion 360 Python script."""

    def __init__(self, capture):
        self.cap = capture
        self.out = []       # accumulated lines
        self.ind = 1        # indent level (inside run())

        # Entity name → Python variable
        self.planes = {}    # construction plane name → var
        self.sketches = {}  # sketch name → var (the Sketch object)
        self.profiles = {}  # sketch name → var (the profile used by next feature)
        self.bodies = {}    # body name → var
        self.feats = {}     # feature name → var

        # Track BRepFace sketch info for CUT extrude direction fixing
        self._brep_face_sketches = {}  # sketch name → plane_info dict

        # Track which helpers the timeline needs
        self.needs = set()

    # ── Public ──

    def generate(self):
        self._scan_needs()
        self._header()
        self._parameters()
        self._helpers()
        self._timeline()
        self._footer()
        return "\n".join(self.out)

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
            c = p.get("comment", "")
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

        # find_body — always useful
        self._w()
        self._w("def find_body(name):")
        self.ind += 1
        self._w("def _walk(comp):")
        self.ind += 1
        self._w("for i in range(comp.bRepBodies.count):")
        self.ind += 1
        self._w("if comp.bRepBodies.item(i).name == name:")
        self.ind += 1
        self._w("return comp.bRepBodies.item(i)")
        self.ind -= 2
        self._w("for occ in comp.occurrences:")
        self.ind += 1
        self._w("r = _walk(occ.component)")
        self._w("if r: return r")
        self.ind -= 1
        self._w("return None")
        self.ind -= 1
        self._w("return _walk(root)")
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

    # ── Timeline dispatch ──

    def _timeline(self):
        self._section("TIMELINE")
        for feat in self.cap.get("timeline", []):
            if feat.get("isRolledBack"):
                continue
            t = feat.get("type", "Unknown")
            idx = feat.get("index", "?")
            name = feat.get("name", "")
            self._w()
            self._c(f"[{idx}] {t}: {name}")
            handler = getattr(self, f"_feat_{t.lower()}", None)
            if handler:
                handler(feat)
            else:
                self._c(f"TODO: Unsupported feature type '{t}'")

    # ── Feature emitters ──

    def _feat_constructionplane(self, f):
        name = f.get("name", "Plane")
        var = self._var(name)
        self.planes[name] = var

        if f.get("definitionType") == "Offset":
            expr = f.get("offset", "0 cm")
            base = f.get("basePlane", "")
            base_map = {
                "XY": "root.xYConstructionPlane",
                "XZ": "root.xZConstructionPlane",
                "YZ": "root.yZConstructionPlane",
            }
            if base in base_map:
                base_code = base_map[base]
            elif base in self.planes:
                base_code = self.planes[base]
            else:
                self._c(f'TODO: unknown base plane "{base}", using XY')
                base_code = "root.xYConstructionPlane"
            self._w(f'{var} = off_plane(root, {base_code}, "{expr}", "{name}")')
        else:
            self._c(f"TODO: Non-offset plane (type={f.get('definitionType')})")
            self._w(f"{var} = None")

    def _feat_sketch(self, f):
        name = f.get("name", "Sketch")
        var = self._var(name)
        self.sketches[name] = var
        curves = f.get("curves", [])
        dims = f.get("dimensions", [])
        plane_info = f.get("plane", {})

        # BRepFace sketches: strategy depends on geometry.
        # - Has auto-projected boundary + no explicit projections → find_face
        #   (avoids cplane CUT boundary issues, works for rect and non-rect)
        # - Has explicit projections (body edges) → cplane
        #   (avoids boundary coincidence, projections need sk.project)
        is_on_face = False
        if (plane_info.get("type") == "BRepFace"
                and "sketchOrigin" in f
                and "sketchXDir" in f
                and "sketchYDir" in f):
            non_ref = [c for c in curves if not c.get("isReference")]
            refs = [c for c in curves if c.get("isReference")]
            self._brep_face_sketches[name] = plane_info
            # Check if any ref is an explicit body/edge projection
            has_body_proj = any(
                c.get("projectedFrom", {}).get("type") == "BRepBody"
                for c in refs
            )
            has_edge_proj = any(
                c.get("projectedFrom", {}).get("type") == "BRepEdge"
                for c in refs
            )
            if has_body_proj:
                # Body projections depend on the exact face geometry (bevel, taper).
                # Must use find_face — cplane gives wrong projection coordinates.
                plane_code = self._resolve_plane(plane_info)
                # Tag curves with original index before filtering
                for ci, c in enumerate(curves):
                    c["_origIdx"] = ci
                # Filter only the auto-boundary refs (BRepFace type), keep body proj refs.
                # Deep-copy dicts so Y-flip doesn't mutate feat["curves"].
                curves = [dict(c) for c in curves if not (
                    c.get("isReference") and
                    c.get("projectedFrom", {}).get("type") == "BRepFace"
                )]
                # Fix Y-flip: captured sketch may have yDir=(0,-1,0) but find_face
                # creates yDir=(0,1,0). Negate Y for all non-reference curve coords.
                ydir = f.get("sketchYDir", [0, 1, 0])
                xdir = f.get("sketchXDir", [1, 0, 0])
                # Check if sketch Y or X is flipped vs standard orientation
                # Standard for Z-normal: xDir=(1,0,0), yDir=(0,1,0)
                # Standard for Y-normal: xDir=(1,0,0), yDir=(0,0,1)
                # Standard for X-normal: xDir=(0,1,0), yDir=(0,0,1)
                flip_y = False
                normal = plane_info.get("normal", [0, 0, 1])
                ax, ay, az = abs(normal[0]), abs(normal[1]), abs(normal[2])
                if az > 0.9 and ydir[1] < 0:
                    flip_y = True  # Z-normal: standard yDir is +Y
                elif ay > 0.9 and ydir[2] < 0:
                    flip_y = True  # Y-normal: standard yDir is +Z
                elif ax > 0.9 and ydir[2] < 0:
                    flip_y = True  # X-normal: standard yDir is +Z
                if flip_y:
                    for c in curves:
                        if not c.get("isReference"):
                            if "start" in c:
                                c["start"] = [c["start"][0], -c["start"][1]]
                            if "end" in c:
                                c["end"] = [c["end"][0], -c["end"][1]]
                            if "center" in c:
                                c["center"] = [c["center"][0], -c["center"][1]]
                    f["_yflipped"] = True
                is_on_face = True
            elif refs and not has_edge_proj:
                # Only auto-boundary refs → use find_face + filter refs
                plane_code = self._resolve_plane(plane_info)
                curves = non_ref
                is_on_face = True
            else:
                # Edge projections or no refs → use cplane
                plane_code, curves = self._brep_face_to_cplane(f, curves)
        else:
            plane_code = self._resolve_plane(plane_info)

        if self._is_rect(curves):
            self._emit_rect_sketch(var, name, plane_code, curves, dims, on_face=is_on_face)
        else:
            self._emit_raw_sketch(var, name, plane_code, curves, dims, f, on_face=is_on_face)

    def _feat_extrude(self, f):
        name = f.get("name", "Extrude")
        fvar = self._var(name)

        op = f.get("operation", "NewBody")
        dist = f.get("distance", "1 cm")
        sketch = f.get("sketch", "")
        pidx = f.get("profileIndex", 0)
        taper = f.get("taperAngle")
        extent = f.get("extentType", "Distance")
        bodies = f.get("bodies", [])
        participants = f.get("participantBodies", [])
        flipped = f.get("isDirectionFlipped", False)

        # Detect negative-wrapped expressions: "-( expr )" means the extrude went
        # opposite to the sketch plane normal. Unwrap and set flip.
        if dist.startswith("-(") and dist.endswith(")"):
            dist = dist[2:-1].strip()
            flipped = True

        op_map = {"NewBody": "NEWBODY", "Cut": "CUT", "Join": "JOIN",
                  "Intersect": "adsk.fusion.FeatureOperations.IntersectFeatureOperation"}
        op_code = op_map.get(op, "NEWBODY")

        # Profile reference
        if sketch in self.profiles:
            prof = self.profiles[sketch]
        elif sketch in self.sketches:
            prof = f"{self.sketches[sketch]}.profiles.item({pidx})"
        else:
            self._c(f"TODO: sketch '{sketch}' not tracked")
            prof = "None"

        self._w(f"inp = root.features.extrudeFeatures.createInput({prof}, {op_code})")

        # Two-sided extent
        if f.get("hasTwoExtents"):
            d2 = f.get("distanceTwo", "1 cm")
            t2 = f.get("taperAngleTwo")
            taper_args = ""
            if taper and taper not in ("0.0 deg", "0 deg"):
                taper_args += f',\n{"    " * (self.ind+1)}adsk.core.ValueInput.createByString("{taper}")'
                if t2 and t2 not in ("0.0 deg", "0 deg"):
                    taper_args += f',\n{"    " * (self.ind+1)}adsk.core.ValueInput.createByString("{t2}")'
            self._w("inp.setTwoSidesExtent(")
            self.ind += 1
            self._w(f'adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByString("{dist}")),')
            self._w(f'adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByString("{d2}")){taper_args})')
            self.ind -= 1
        elif extent == "Symmetric":
            self._w(f'inp.setSymmetricExtent(adsk.core.ValueInput.createByString("{dist}"), True)')
        elif flipped:
            self._w("inp.setOneSideExtent(")
            self.ind += 1
            self._w(f'adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByString("{dist}")),')
            self._w("adsk.fusion.ExtentDirections.NegativeExtentDirection)")
            self.ind -= 1
        else:
            self._w(f'inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("{dist}"))')

        if not f.get("hasTwoExtents") and taper and taper not in ("0.0 deg", "0 deg"):
            self._w(f'inp.taperAngle = adsk.core.ValueInput.createByString("{taper}")')

        if participants and op in ("Cut", "Join"):
            self._w(f"inp.participantBodies = {self._body_list(participants)}")
        elif not participants and op in ("Cut", "Join") and bodies:
            # Infer participants from affected bodies when not explicitly captured
            self._w(f"inp.participantBodies = {self._body_list(bodies)}")

        self._w(f"{fvar} = root.features.extrudeFeatures.add(inp)")
        self._w(f'{fvar}.name = "{name}"')
        self.feats[name] = fvar

        if bodies:
            for i, bn in enumerate(bodies):
                bv = self._var(bn)
                # Avoid collision with feature variable
                if bv == fvar:
                    bv = bv + "_b"
                self.bodies[bn] = bv
                self._w(f"{bv} = {fvar}.bodies.item({i})")
                self._w(f'{bv}.name = "{bn}"')
        elif op == "NewBody":
            bv = self._var(name)
            if bv == fvar:
                bv = bv + "_b"
            self.bodies[name] = bv
            self._w(f"{bv} = {fvar}.bodies.item(0)")
            self._w(f'{bv}.name = "{name}"')

    def _feat_move(self, f):
        name = f.get("name", "Move")
        matrix = f.get("matrix")
        inputs = f.get("inputs", [])

        if not matrix:
            self._c("TODO: Move with no matrix data")
            return

        self._w("xform = adsk.core.Matrix3D.create()")
        vals = [matrix[r][c] for r in range(4) for c in range(4)]
        self._w(f"xform.setWithArray({vals})")

        self._w("move_coll = adsk.core.ObjectCollection.create()")
        if inputs:
            for inp_name in inputs:
                bv = self._body_ref(inp_name)
                self._w(f"move_coll.add({bv})")
        else:
            self._c("TODO: No input entities captured — add the body to move")
            self._w("# move_coll.add(body)")

        self._w("move_inp = root.features.moveFeatures.createInput2(move_coll)")
        self._w("move_inp.defineAsFreeMove(xform)")
        self._w(f'move_feat = root.features.moveFeatures.add(move_inp)')
        self._w(f'move_feat.name = "{name}"')
        self.feats[name] = "move_feat"

    def _feat_sweep(self, f):
        name = f.get("name", "Sweep")
        op = f.get("operation", "NewBody")
        sketch_name = f.get("sketch", "")
        pidx = f.get("profileIndex", 0)
        pcoll_count = f.get("profileCollectionCount", 1)
        path_ents = f.get("path", [])
        participants = f.get("participantBodies", [])
        bodies = f.get("bodies", [])
        orientation = f.get("orientation", "Perpendicular")

        op_map = {"NewBody": "NEWBODY", "Cut": "CUT", "Join": "JOIN"}
        op_code = op_map.get(op, "NEWBODY")

        # Profile
        indices = f.get("profileIndices", [])
        if not indices:
            indices = [pidx]

        sk_var = self.sketches.get(sketch_name)
        if not sk_var:
            self._c(f"TODO: sketch '{sketch_name}' not tracked")
            prof_code = "None"
        elif pcoll_count > 1:
            # Multi-profile sweep: select N smallest non-trivial profiles by bbox area.
            # This handles BRepFace→construction plane conversion where T-junctions
            # change profile count/ordering. Shoulder profiles (smallest meaningful
            # regions) are reliably the smallest by bounding box area.
            self._w("sweep_profs = adsk.core.ObjectCollection.create()")
            self._w("_areas = []")
            self._w(f"for _pi in range({sk_var}.profiles.count):")
            self.ind += 1
            self._w(f"_bb = {sk_var}.profiles.item(_pi).boundingBox")
            self._w(f"_a = abs(_bb.maxPoint.x - _bb.minPoint.x) * abs(_bb.maxPoint.y - _bb.minPoint.y)")
            self._w(f"_areas.append((_a, _pi))")
            self.ind -= 1
            self._w("_max_a = max(a for a, _ in _areas) if _areas else 1")
            self._w("_cands = sorted((a, i) for a, i in _areas if a > _max_a * 0.001)")
            self._w(f"for _a, _pi in _cands[:{pcoll_count}]:")
            self.ind += 1
            self._w(f"sweep_profs.add({sk_var}.profiles.item(_pi))")
            self.ind -= 1
            prof_code = "sweep_profs"
        else:
            prof_code = f"{sk_var}.profiles.item({indices[0]})"

        # Path
        if path_ents:
            pe = path_ents[0]
            if pe.get("source") == "BRepEdge":
                body_name = pe.get("body", "")
                sv = pe.get("startVertex", [0, 0, 0])
                ev = pe.get("endVertex", [0, 0, 0])
                bv = self._body_ref(body_name)
                self._c(f"Path: edge on '{body_name}' from ~{_fmt_pt(sv)} to ~{_fmt_pt(ev)}")
                self._w(f"sweep_edge = None")
                self._w(f"for i in range({bv}.edges.count):")
                self.ind += 1
                self._w(f"e = {bv}.edges.item(i)")
                self._w(f"sp, ep = e.startVertex.geometry, e.endVertex.geometry")
                # Match by approximate vertex positions
                self._w(f"if (abs(sp.x - {sv[0]:.4f}) + abs(sp.y - {sv[1]:.4f}) + abs(sp.z - {sv[2]:.4f}) < 0.1 and")
                self._w(f"    abs(ep.x - {ev[0]:.4f}) + abs(ep.y - {ev[1]:.4f}) + abs(ep.z - {ev[2]:.4f}) < 0.1):")
                self.ind += 1
                self._w(f"sweep_edge = e")
                self._w(f"break")
                self.ind -= 2
                self._w(f"sweep_path = root.features.createPath(sweep_edge)")
            elif pe.get("source") == "SketchCurve":
                sk_name = pe.get("parentSketch", "")
                self._c(f"Path: SketchCurve from '{sk_name}'")
                if sk_name in self.sketches:
                    self._w(f"sweep_path = root.features.createPath({self.sketches[sk_name]}.sketchCurves.item(0))  # TODO: correct curve")
                else:
                    self._w(f"sweep_path = None  # TODO: sketch '{sk_name}'")
            else:
                self._w("sweep_path = None  # TODO: unknown path source")
        else:
            self._w("sweep_path = None  # TODO: no path captured")

        self._w(f"sweep_inp = root.features.sweepFeatures.createInput({prof_code}, sweep_path, {op_code})")

        orient_map = {
            "Perpendicular": "adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType",
            "Parallel": "adsk.fusion.SweepOrientationTypes.ParallelOrientationType",
        }
        if orientation in orient_map:
            self._w(f"sweep_inp.orientation = {orient_map[orientation]}")

        # Distance extent (default is full path; distanceOne/Two are 0-1 fractions)
        dist1 = f.get("distanceOne")
        dist2 = f.get("distanceTwo")
        if dist1 and dist2:
            self._w(f'sweep_inp.distanceTwo = adsk.core.ValueInput.createByString("{dist2}")')
            self._w(f'sweep_inp.distanceOne = adsk.core.ValueInput.createByString("{dist1}")')
        elif dist1:
            self._w(f'sweep_inp.distanceOne = adsk.core.ValueInput.createByString("{dist1}")')

        # Taper and twist angles
        taper = f.get("taperAngle")
        if taper and taper != "0.0 deg" and taper != "0 deg":
            self._w(f'sweep_inp.taperAngle = adsk.core.ValueInput.createByString("{taper}")')
        twist = f.get("twistAngle")
        if twist and twist != "0.0 deg" and twist != "0 deg":
            self._w(f'sweep_inp.twistAngle = adsk.core.ValueInput.createByString("{twist}")')

        # Direction flip
        if f.get("isDirectionFlipped"):
            self._w(f"sweep_inp.isDirectionFlipped = True")

        if participants and op in ("Cut", "Join"):
            self._w(f"sweep_inp.participantBodies = {self._body_list(participants)}")

        self._w(f"sweep_feat = root.features.sweepFeatures.add(sweep_inp)")
        self._w(f'sweep_feat.name = "{name}"')
        self.feats[name] = "sweep_feat"

        for i, bn in enumerate(bodies):
            bv = self._var(bn)
            self.bodies[bn] = bv
            self._w(f'{bv} = sweep_feat.bodies.item({i})')
            self._w(f'{bv}.name = "{bn}"')

    def _feat_splitbody(self, f):
        name = f.get("name", "Split")
        bodies = f.get("bodies", [])

        # Split+Remove sequences use deleteMe which invalidates sibling bodies
        # in executeTextCommand mode. Skip the split — cosmetic trims only.
        self._c(f"Split+Remove skipped (deleteMe invalidates siblings in sandbox)")
        if bodies:
            input_name = bodies[0]
            self._c(f"Body '{input_name}' kept as-is (foot trim omitted)")

    def _feat_remove(self, f):
        # Remove skipped — paired with SplitBody (deleteMe invalidates siblings)
        removed = f.get("removedBody", "")
        self._c(f"Remove '{removed}' skipped (see SplitBody note above)")

    def _feat_mirror(self, f):
        name = f.get("name", "Mirror")
        var = self._var(name)
        plane_info = f.get("mirrorPlane", {})
        bodies = f.get("bodies", [])
        input_bodies = f.get("inputBodies", [])

        # Resolve plane
        pname = plane_info.get("name", "")
        if pname in self.planes:
            plane_code = self.planes[pname]
        else:
            self._c(f'TODO: mirror plane "{pname}" not tracked')
            plane_code = "None"

        # Resolve inputs
        if input_bodies:
            input_code = self._body_list(input_bodies)
        else:
            # Fallback: bodies that already exist in self.bodies are the inputs
            known = [bn for bn in bodies if bn in self.bodies]
            if known:
                input_code = self._body_list(known)
            else:
                self._c("TODO: mirror inputs unknown")
                input_code = "[]"

        self._w(f"{var} = mirror_bodies(root, {input_code}, {plane_code}, \"{name}\")")

        self.feats[name] = var
        for i, bn in enumerate(bodies):
            bv = self._var(bn)
            self.bodies[bn] = bv
            self._w(f'{bv} = {var}.bodies.item({i})')
            self._w(f'{bv}.name = "{bn}"')

    def _feat_combine(self, f):
        name = f.get("name", "Combine")
        op = f.get("operation", "Join")
        target = f.get("targetBody")
        tools = f.get("toolBodies", [])
        keep = f.get("isKeepToolBodies", False)

        op_map = {"Join": "JOIN", "Cut": "CUT"}
        op_code = op_map.get(op, "JOIN")

        if target:
            tc = self._body_ref(target)
        else:
            err = f.get("targetBodyError", "not captured")
            self._c(f"TODO: target body not captured ({err})")
            tc = "None"

        if tools:
            tools_code = self._body_list(tools)
        else:
            err = f.get("toolBodiesError", "not captured")
            self._c(f"TODO: tool bodies not captured ({err})")
            tools_code = "[]"

        self._w(f'combine(root, {tc}, {tools_code}, {op_code}, {keep}, "{name}")')

    def _feat_fillet(self, f):
        name = f.get("name", "Fillet")
        edge_sets = f.get("edgeSets", [])

        if not edge_sets:
            self._c(f"TODO: Fillet '{name}' — no edge data captured")
            return

        self._w("fillet_inp = root.features.filletFeatures.createInput()")
        any_edges = False
        for si, es in enumerate(edge_sets):
            radius = es.get("radius", "0.1 cm")
            edges = es.get("edges", [])
            if not edges:
                self._c(f"TODO: edge set {si} has no captured vertices")
                continue
            any_edges = True
            self._emit_edge_finder(f"fillet_edges_{si}", edges, f.get("bodies", []))
            self._w(f"if fillet_edges_{si}.count > 0:")
            self.ind += 1
            self._w(f"fillet_inp.addConstantRadiusEdgeSet(fillet_edges_{si}, "
                    f'adsk.core.ValueInput.createByString("{radius}"), True)')
            self.ind -= 1
        if any_edges:
            self._w(f'fillet_feat = root.features.filletFeatures.add(fillet_inp)')
            self._w(f'fillet_feat.name = "{name}"')
        else:
            self._c(f"TODO: Fillet '{name}' skipped — no edges captured")

    def _feat_chamfer(self, f):
        name = f.get("name", "Chamfer")
        edge_sets = f.get("edgeSets", [])

        if not edge_sets:
            self._c(f"TODO: Chamfer '{name}' — no edge data captured")
            return

        self._w("chamfer_inp = root.features.chamferFeatures.createInput2()")
        any_edges = False
        for si, es in enumerate(edge_sets):
            edges = es.get("edges", [])
            if not edges:
                self._c(f"TODO: edge set {si} has no captured vertices")
                continue
            any_edges = True
            ctype = es.get("chamferType", "EqualDistance")
            self._emit_edge_finder(f"chamfer_edges_{si}", edges, f.get("bodies", []))

            if ctype == "EqualDistance":
                dist = es.get("distance", f.get("distance", "0.1 cm"))
                self._w(f"chamfer_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet("
                        f'chamfer_edges_{si}, adsk.core.ValueInput.createByString("{dist}"), True)')
            elif ctype == "TwoDistances":
                d1 = es.get("distanceOne", f.get("distanceOne", "0.1 cm"))
                d2 = es.get("distanceTwo", f.get("distanceTwo", "0.1 cm"))
                self._w(f"chamfer_inp.chamferEdgeSets.addTwoDistanceChamferEdgeSet("
                        f'chamfer_edges_{si}, adsk.core.ValueInput.createByString("{d1}"), '
                        f'adsk.core.ValueInput.createByString("{d2}"), True)')
            elif ctype == "DistanceAndAngle":
                dist = es.get("distance", f.get("distance", "0.1 cm"))
                angle = es.get("angle", f.get("angle", "45 deg"))
                self._w(f"chamfer_inp.chamferEdgeSets.addDistanceAndAngleChamferEdgeSet("
                        f'chamfer_edges_{si}, adsk.core.ValueInput.createByString("{dist}"), '
                        f'adsk.core.ValueInput.createByString("{angle}"), True)')

        if any_edges:
            self._w(f'chamfer_feat = root.features.chamferFeatures.add(chamfer_inp)')
            self._w(f'chamfer_feat.name = "{name}"')
        else:
            self._c(f"TODO: Chamfer '{name}' skipped — no edges captured")

    def _emit_edge_finder(self, var, edges, body_names):
        """Emit code that finds edges by matching vertex positions."""
        self._w(f"{var} = adsk.core.ObjectCollection.create()")
        if not edges:
            self._c("TODO: no edge vertices captured")
            return

        # Build list of target vertex pairs
        self._w("_targets = [")
        self.ind += 1
        for e in edges:
            s = e["start"]
            ev = e["end"]
            self._w(f"(({s[0]}, {s[1]}, {s[2]}), ({ev[0]}, {ev[1]}, {ev[2]})),")
        self.ind -= 1
        self._w("]")

        # Search bodies for matching edges
        if body_names:
            body_code = self._body_ref(body_names[0])
        else:
            body_code = "None"
        self._w(f"_body = {body_code}")
        self._w("if _body:")
        self.ind += 1
        self._w("for _ei in range(_body.edges.count):")
        self.ind += 1
        self._w("_e = _body.edges.item(_ei)")
        self._w("_sv, _ev = _e.startVertex.geometry, _e.endVertex.geometry")
        self._w("for _ts, _te in _targets:")
        self.ind += 1
        self._w("if ((abs(_sv.x-_ts[0])+abs(_sv.y-_ts[1])+abs(_sv.z-_ts[2]) < 0.05 and")
        self._w("     abs(_ev.x-_te[0])+abs(_ev.y-_te[1])+abs(_ev.z-_te[2]) < 0.05) or")
        self._w("    (abs(_sv.x-_te[0])+abs(_sv.y-_te[1])+abs(_sv.z-_te[2]) < 0.05 and")
        self._w("     abs(_ev.x-_ts[0])+abs(_ev.y-_ts[1])+abs(_ev.z-_ts[2]) < 0.05)):")
        self.ind += 1
        self._w(f"{var}.add(_e)")
        self._w("break")
        self.ind -= 4

    def _feat_rectangularpattern(self, f):
        name = f.get("name", "Pattern")
        var = self._var(name)
        qty = f.get("quantityOne", "2")
        dist = f.get("distanceOne", "5 cm")
        inputs = f.get("inputs", [])
        bodies = f.get("bodies", [])
        axis_name = f.get("axisOne", "")
        direction = f.get("directionOne")
        dist_type = f.get("distanceType", "Spacing")

        # Resolve axis
        axis_map = {
            "X": "root.xConstructionAxis",
            "Y": "root.yConstructionAxis",
            "Z": "root.zConstructionAxis",
        }
        if axis_name in axis_map:
            axis_code = axis_map[axis_name]
        elif direction:
            # Infer axis from direction vector
            dx, dy, dz = [abs(v) for v in direction]
            if dx >= dy and dx >= dz:
                axis_code = "root.xConstructionAxis"
            elif dy >= dx and dy >= dz:
                axis_code = "root.yConstructionAxis"
            else:
                axis_code = "root.zConstructionAxis"
        else:
            axis_code = "root.xConstructionAxis"
            self._c(f"TODO: axis '{axis_name}' not resolved, defaulting to X")

        # Resolve distance type
        dist_type_code = ("adsk.fusion.PatternDistanceType.SpacingPatternDistanceType"
                          if dist_type == "Spacing"
                          else "adsk.fusion.PatternDistanceType.ExtentPatternDistanceType")

        # Input bodies
        self._w("pat_coll = adsk.core.ObjectCollection.create()")
        if inputs:
            for inp_name in inputs:
                bv = self._body_ref(inp_name)
                self._w(f"pat_coll.add({bv})")
        else:
            self._c("TODO: pattern input bodies not captured")

        self._w(f"pat_inp = root.features.rectangularPatternFeatures.createInput(")
        self.ind += 1
        self._w(f"pat_coll,")
        self._w(f"{axis_code},")
        self._w(f'adsk.core.ValueInput.createByString("{qty}"),')
        self._w(f'adsk.core.ValueInput.createByString("{dist}"),')
        self._w(f"{dist_type_code},")
        self.ind -= 1
        self._w(")")

        # Second direction: default quantityTwo to 1 (single-axis pattern)
        qty2 = f.get("quantityTwo")
        if qty2 and qty2 != "1":
            dist2 = f.get("distanceTwo", "5 cm")
            self._w(f'pat_inp.quantityTwo = adsk.core.ValueInput.createByString("{qty2}")')
            self._w(f'pat_inp.distanceTwo = adsk.core.ValueInput.createByString("{dist2}")')
        else:
            self._w("pat_inp.quantityTwo = adsk.core.ValueInput.createByReal(1)")

        self._w(f"{var} = root.features.rectangularPatternFeatures.add(pat_inp)")
        self._w(f'{var}.name = "{name}"')
        self.feats[name] = var

        # Track output bodies — pat.bodies only includes NEW copies, not the original.
        # Filter out bodies already tracked (the original input body).
        new_bodies = [bn for bn in bodies if bn not in self.bodies]
        for i, bn in enumerate(new_bodies):
            bv = self._var(bn)
            self.bodies[bn] = bv
            self._w(f'{bv} = {var}.bodies.item({i})')

    def _feat_constructionaxis(self, f):
        name = f.get("name", "Axis")
        self._c(f"ConstructionAxis: {name}")
        self._c("TODO: Reconstruct construction axis")

    def _feat_componentcreation(self, f):
        name = f.get("name", "Component")
        var = self._var(name)
        self._w(f"{var}_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())")
        self._w(f'{var}_occ.component.name = "{name}"')
        self._w(f"{var}_c = {var}_occ.component")

    def _feat_snapshot(self, f):
        self._c("Snapshot (informational only, no code needed)")

    # ── Sketch helpers ──

    def _is_rect(self, curves):
        """Check if curves are exactly 4 axis-aligned non-construction lines."""
        lines = [c for c in curves if c.get("type") == "Line" and not c.get("isConstruction")]
        if len(lines) != 4:
            return False
        for ln in lines:
            sx, sy = ln["start"]
            ex, ey = ln["end"]
            if abs(ex - sx) > 0.001 and abs(ey - sy) > 0.001:
                return False
        return True

    def _emit_rect_sketch(self, var, name, plane_code, curves, dims, on_face=False):
        """Emit a rectangle sketch with parametric dimensions."""
        lines = [c for c in curves if c.get("type") == "Line" and not c.get("isConstruction")]
        xs = [c["start"][0] for c in lines] + [c["end"][0] for c in lines]
        ys = [c["start"][1] for c in lines] + [c["end"][1] for c in lines]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        w, h = x1 - x0, y1 - y0

        # Match dimensions to geometry
        w_expr = f"{w} cm"
        h_expr = f"{h} cm"
        x0_expr = "0 cm" if abs(x0) < 0.001 else f"{x0} cm"
        y0_expr = "0 cm" if abs(y0) < 0.001 else f"{y0} cm"
        used = set()
        for i, d in enumerate(dims):
            val = d.get("value", 0)
            expr = d.get("expression", "")
            if i not in used and abs(val - w) < 0.01:
                w_expr = expr; used.add(i)
            elif i not in used and abs(val - h) < 0.01:
                h_expr = expr; used.add(i)
            elif i not in used and abs(val - abs(x0)) < 0.01 and abs(x0) > 0.001:
                x0_expr = expr; used.add(i)
            elif i not in used and abs(val - abs(y0)) < 0.01 and abs(y0) > 0.001:
                y0_expr = expr; used.add(i)

        self._w(f"{var} = root.sketches.add({plane_code})")
        self._w(f'{var}.name = "{name}"')
        self._w(f'x0, y0, w, h = ev("{x0_expr}"), ev("{y0_expr}"), ev("{w_expr}"), ev("{h_expr}")')
        self._w(f"rect = {var}.sketchCurves.sketchLines.addTwoPointRectangle(")
        self.ind += 1
        self._w("P(x0, y0, 0), P(x0 + w, y0 + h, 0))")
        self.ind -= 1
        self._w(f"gc = {var}.geometricConstraints")
        self._w("gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])")
        self._w("gc.addVertical(rect[1]); gc.addVertical(rect[3])")
        self._w(f"d = {var}.sketchDimensions")
        self._w("d.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,")
        self.ind += 1
        self._w(f'H, P(x0 + w/2, y0 - 1, 0)).parameter.expression = "{w_expr}"')
        self.ind -= 1
        self._w("d.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,")
        self.ind += 1
        self._w(f'V, P(x0 + w + 1, y0 + h/2, 0)).parameter.expression = "{h_expr}"')
        self.ind -= 1
        if x0_expr != "0 cm":
            self._w("d.addDistanceDimension({0}.originPoint, rect[0].startSketchPoint,".format(var))
            self.ind += 1
            self._w(f'H, P(x0/2, y0 - 2, 0)).parameter.expression = "{x0_expr}"')
            self.ind -= 1
        if y0_expr != "0 cm":
            self._w("d.addDistanceDimension({0}.originPoint, rect[0].startSketchPoint,".format(var))
            self.ind += 1
            self._w(f'V, P(x0 - 1, y0/2, 0)).parameter.expression = "{y0_expr}"')
            self.ind -= 1
        prof = f"{var}_prof"
        if on_face:
            # BRepFace auto-projects boundary → multiple profiles. Select smallest.
            self._w(f"_best_pi, _best_a = 0, float('inf')")
            self._w(f"for _pi in range({var}.profiles.count):")
            self.ind += 1
            self._w(f"_bb = {var}.profiles.item(_pi).boundingBox")
            self._w(f"_a = abs(_bb.maxPoint.x-_bb.minPoint.x)*abs(_bb.maxPoint.y-_bb.minPoint.y)")
            self._w(f"if _a < _best_a: _best_a, _best_pi = _a, _pi")
            self.ind -= 1
            self._w(f"{prof} = {var}.profiles.item(_best_pi)")
        else:
            self._w(f"{prof} = {var}.profiles.item(0)")
        self.profiles[name] = prof

    def _emit_raw_sketch(self, var, name, plane_code, curves, dims, feat, on_face=False):
        """Emit raw sketch geometry with parametric dimensions and constraints."""
        self._w(f"{var} = root.sketches.add({plane_code})")
        self._w(f'{var}.name = "{name}"')
        self._w(f"lns = {var}.sketchCurves.sketchLines")

        has_arcs = any(c.get("type") == "Arc" for c in curves)
        has_circles = any(c.get("type") == "Circle" for c in curves)
        if has_arcs:
            self._w(f"arcs = {var}.sketchCurves.sketchArcs")

        # Track sketch points by position to share coincident endpoints.
        # Without sharing, Fusion creates duplicate points and extra profiles.
        pt_map = {}  # (round_x, round_y) → "ln{i}.startSketchPoint" etc.

        def _pt_ref(x, y):
            """Return sketch point ref if one exists at this position, else Point3D."""
            key = (round(x, 3), round(y, 3))
            return pt_map.get(key), key

        def _register_pt(key, ref):
            if key not in pt_map:
                pt_map[key] = ref

        # curve index → variable name mapping for dimension/constraint targets
        curve_vars = {}
        arc_vars = {}
        circle_vars = {}

        # Pre-scan: collect BRepBody projections and detect which drawn line
        # endpoints coincide with projected curve endpoints (in original capture space).
        _body_proj_done = set()
        _has_body_projs = False
        _proj_endpoints = set()  # (round_x, round_y) of projected curve endpoints
        _proj_connected = set()  # (curve_idx, "start"/"end") pairs that should snap to projections

        # Pass 1: collect all projected curve endpoint positions (pre-flip coordinates)
        for i, c in enumerate(feat.get("curves", [])):
            if c.get("isReference") and c.get("projectedFrom", {}).get("type") == "BRepBody":
                sx, sy = c["start"]
                ex, ey = c["end"]
                _proj_endpoints.add((round(sx, 3), round(sy, 3)))
                _proj_endpoints.add((round(ex, 3), round(ey, 3)))

        # Pass 2: check which drawn line endpoints match projected endpoints
        for i, c in enumerate(feat.get("curves", [])):
            if not c.get("isReference"):
                sx, sy = c.get("start", [0, 0])
                ex, ey = c.get("end", [0, 0])
                if (round(sx, 3), round(sy, 3)) in _proj_endpoints:
                    _proj_connected.add((i, "start"))
                if (round(ex, 3), round(ey, 3)) in _proj_endpoints:
                    _proj_connected.add((i, "end"))

        # Pass 3: emit sk.project(body) calls
        for i, c in enumerate(curves):
            if c.get("isReference"):
                pf = c.get("projectedFrom", {})
                if pf.get("type") == "BRepBody" and pf.get("body"):
                    bname = pf["body"]
                    if bname not in _body_proj_done:
                        _body_proj_done.add(bname)
                        _has_body_projs = True
                        bv = self._body_ref(bname)
                        pvar = f"_proj_body_{self._var(bname)}"
                        self._c(f"Project body '{bname}'")
                        self._w(f"{pvar} = {var}.project({bv})")

        if _has_body_projs:
            # Build runtime lookup of all projected sketch points (no threshold —
            # _proj_connected gates which endpoints use this)
            self._w(f"_proj_pts = []  # [(x, y, sketchPoint), ...]")
            self._w(f"for _ci in range({var}.sketchCurves.count):")
            self.ind += 1
            self._w(f"_c = {var}.sketchCurves.item(_ci)")
            self._w(f"if _c.isReference:")
            self.ind += 1
            self._w(f"for _sp in [_c.startSketchPoint, _c.endSketchPoint]:")
            self.ind += 1
            self._w(f"_g = _sp.geometry")
            self._w(f"_proj_pts.append((_g.x, _g.y, _sp))")
            self.ind -= 3
            self._w()
            self._w(f"def _nearest_proj(x, y):")
            self.ind += 1
            self._w(f"best, best_d = None, 1e10")
            self._w(f"for _px, _py, _sp in _proj_pts:")
            self.ind += 1
            self._w(f"_d = abs(_px - x) + abs(_py - y)")
            self._w(f"if _d < best_d: best, best_d = _sp, _d")
            self.ind -= 1
            self._w(f"return best")
            self.ind -= 1

        for i, c in enumerate(curves):
            ctype = c.get("type", "")
            # Projected/reference curves: emit sk.project(edge/body) to recreate
            if c.get("isReference"):
                pf = c.get("projectedFrom", {})
                if pf.get("type") == "BRepBody" and pf.get("body"):
                    # Body projection emitted above. Skip individual curve —
                    # sk.project(body) creates all projected curves at once.
                    # Drawn curves connect via shared sketch points (coincident).
                    continue
                elif pf.get("type") == "BRepEdge" and "startVertex" in pf and "endVertex" in pf:
                    body_name = pf["body"]
                    sv = pf["startVertex"]
                    ev_pt = pf["endVertex"]
                    bv = self._body_ref(body_name)
                    self._c(f"Project edge from '{body_name}'")
                    self._w(f"_proj_edge_{i} = None")
                    self._w(f"for _ei in range({bv}.edges.count):")
                    self.ind += 1
                    self._w(f"_e = {bv}.edges.item(_ei)")
                    self._w(f"_sv, _ev = _e.startVertex.geometry, _e.endVertex.geometry")
                    self._w(f"if ((abs(_sv.x-{sv[0]:.4f})+abs(_sv.y-{sv[1]:.4f})+abs(_sv.z-{sv[2]:.4f}) < 0.05 and")
                    self._w(f"     abs(_ev.x-{ev_pt[0]:.4f})+abs(_ev.y-{ev_pt[1]:.4f})+abs(_ev.z-{ev_pt[2]:.4f}) < 0.05) or")
                    self._w(f"    (abs(_sv.x-{ev_pt[0]:.4f})+abs(_sv.y-{ev_pt[1]:.4f})+abs(_sv.z-{ev_pt[2]:.4f}) < 0.05 and")
                    self._w(f"     abs(_ev.x-{sv[0]:.4f})+abs(_ev.y-{sv[1]:.4f})+abs(_ev.z-{sv[2]:.4f}) < 0.05)):")
                    self.ind += 1
                    self._w(f"_proj_edge_{i} = _e")
                    self._w("break")
                    self.ind -= 2
                    self._w(f"_proj_curves_{i} = {var}.project(_proj_edge_{i})")
                    # The projected result is a collection; find the matching curve
                    self._w(f"proj{i} = _proj_curves_{i}.item(0)")
                    _oi = c.get("_origIdx", i)
                    curve_vars[_oi] = f"proj{i}"
                    sx, sy = c["start"]
                    ex, ey = c["end"]
                    _register_pt((round(sx, 3), round(sy, 3)), f"proj{i}.startSketchPoint")
                    _register_pt((round(ex, 3), round(ey, 3)), f"proj{i}.endSketchPoint")
                else:
                    self._c(f"curve[{i}] is a projected reference (source not captured)")
                continue
            if ctype == "Line":
                sx, sy = c["start"]
                ex, ey = c["end"]
                s_ref, s_key = _pt_ref(sx, sy)
                e_ref, e_key = _pt_ref(ex, ey)
                if _has_body_projs:
                    # Only snap endpoints that were coincident with projected
                    # curves in the original sketch (detected by _proj_connected).
                    # Use _origIdx to map back to original curve index.
                    oi = c.get("_origIdx", i)
                    if not s_ref and (oi, "start") in _proj_connected:
                        s_code = f"_nearest_proj({sx}, {sy})"
                    elif s_ref:
                        s_code = s_ref
                    else:
                        s_code = f"P({sx}, {sy}, 0)"
                    if not e_ref and (oi, "end") in _proj_connected:
                        e_code = f"_nearest_proj({ex}, {ey})"
                    elif e_ref:
                        e_code = e_ref
                    else:
                        e_code = f"P({ex}, {ey}, 0)"
                else:
                    s_code = s_ref if s_ref else f"P({sx}, {sy}, 0)"
                    e_code = e_ref if e_ref else f"P({ex}, {ey}, 0)"
                self._w(f"ln{i} = lns.addByTwoPoints({s_code}, {e_code})")
                _register_pt(s_key, f"ln{i}.startSketchPoint")
                _register_pt(e_key, f"ln{i}.endSketchPoint")
                _oi = c.get("_origIdx", i)
                curve_vars[_oi] = f"ln{i}"
                if c.get("isConstruction"):
                    self._w(f"ln{i}.isConstruction = True")
            elif ctype == "Arc":
                cx, cy = c.get("center", [0, 0])
                sx, sy = c.get("start", [0, 0])
                sweep = c.get("sweepAngle", 3.14159)
                self._w(f"arc{i} = arcs.addByCenterStartSweep(P({cx}, {cy}, 0), P({sx}, {sy}, 0), {sweep})")
                _oi = c.get("_origIdx", i)
                curve_vars[_oi] = f"arc{i}"
                arc_vars[i] = f"arc{i}"
                _register_pt((round(sx, 3), round(sy, 3)), f"arc{i}.startSketchPoint")
                ex, ey = c.get("end", [sx, sy])
                _register_pt((round(ex, 3), round(ey, 3)), f"arc{i}.endSketchPoint")
            elif ctype == "Circle":
                cx, cy = c.get("center", [0, 0])
                r = c.get("radius", 1)
                self._w(f"circ{i} = {var}.sketchCurves.sketchCircles.addByCenterRadius(P({cx}, {cy}, 0), {r})")
                _oi = c.get("_origIdx", i)
                curve_vars[_oi] = f"circ{i}"
                circle_vars[i] = f"circ{i}"

        # Build fallback map for projected body curve endpoints.
        # When a dimension references a BRepBody-projected curve not in curve_vars,
        # use _nearest_proj to find the actual projected point at runtime.
        _proj_curve_pts = {}  # (origIdx, role) → (x, y) in original capture space
        if _has_body_projs:
            for c in feat.get("curves", []):
                oi = c.get("_origIdx")
                if (oi is not None and c.get("isReference")
                        and c.get("projectedFrom", {}).get("type") == "BRepBody"):
                    sx, sy = c["start"]
                    ex, ey = c["end"]
                    _proj_curve_pts[(oi, "start")] = (sx, sy)
                    _proj_curve_pts[(oi, "end")] = (ex, ey)

        # Emit dimensions with entity targets
        if dims:
            self._w(f"d = {var}.sketchDimensions")
            for di, d in enumerate(dims):
                dtype = d.get("type", "")
                expr = d.get("expression")
                if not expr:
                    continue

                if dtype == "SketchLinearDimension":
                    e1 = d.get("entityOne")
                    e2 = d.get("entityTwo")
                    orient = d.get("orientation", "Horizontal")
                    orient_code = "H" if orient == "Horizontal" else "V"
                    e1_code = self._resolve_sketch_entity_ref(e1, curve_vars, var, _proj_curve_pts)
                    e2_code = self._resolve_sketch_entity_ref(e2, curve_vars, var, _proj_curve_pts)
                    if e1_code and e2_code:
                        val = d.get("value", 0)
                        self._w(f"d.addDistanceDimension({e1_code}, {e2_code},")
                        self.ind += 1
                        self._w(f'{orient_code}, P(0, 0, 0)).parameter.expression = "{expr}"')
                        self.ind -= 1
                    else:
                        self._c(f"TODO: dim[{di}] {dtype}: {expr} (targets not resolved)")

                elif dtype == "SketchDiameterDimension":
                    entity = d.get("entity")
                    entity_code = self._resolve_sketch_curve_ref(entity, curve_vars)
                    if entity_code:
                        val = d.get("value", 1)
                        self._w(f'd.addDiameterDimension({entity_code}, P({val + 1}, 0, 0)).parameter.expression = "{expr}"')
                    else:
                        self._c(f"TODO: dim[{di}] {dtype}: {expr}")

                elif dtype == "SketchRadialDimension":
                    entity = d.get("entity")
                    entity_code = self._resolve_sketch_curve_ref(entity, curve_vars)
                    if entity_code:
                        val = d.get("value", 1)
                        self._w(f'd.addRadialDimension({entity_code}, P({val + 1}, 0, 0)).parameter.expression = "{expr}"')
                    else:
                        self._c(f"TODO: dim[{di}] {dtype}: {expr}")

                else:
                    self._c(f"TODO: dim[{di}] {dtype}: {expr} = {d.get('value', 0)}")

        # Emit geometric constraints with targets
        constraints = feat.get("constraints", [])
        if constraints and any(isinstance(c, dict) for c in constraints):
            self._w(f"gc = {var}.geometricConstraints")
            for ci, c in enumerate(constraints):
                if isinstance(c, str):
                    # Legacy format (just type name, no targets)
                    continue
                ctype = c.get("type", "")

                if ctype == "HorizontalConstraint":
                    line_ref = c.get("line")
                    line_code = self._resolve_sketch_curve_ref(line_ref, curve_vars)
                    if line_code:
                        self._w(f"gc.addHorizontal({line_code})")

                elif ctype == "VerticalConstraint":
                    line_ref = c.get("line")
                    line_code = self._resolve_sketch_curve_ref(line_ref, curve_vars)
                    if line_code:
                        self._w(f"gc.addVertical({line_code})")

                elif ctype == "CoincidentConstraint":
                    pt_ref = c.get("point")
                    ent_ref = c.get("entity")
                    # Skip if either entity references a body-projected curve
                    # (those connections are handled by _nearest_proj at runtime)
                    pt_ci = pt_ref.get("curveIndex") if pt_ref else None
                    ent_ci = ent_ref.get("curveIndex") if ent_ref else None
                    if _has_body_projs and (
                        (pt_ci is not None and pt_ci not in curve_vars) or
                        (ent_ci is not None and ent_ci not in curve_vars)):
                        continue
                    pt_code = self._resolve_sketch_entity_ref(pt_ref, curve_vars, var)
                    ent_code = self._resolve_sketch_entity_ref(ent_ref, curve_vars, var)
                    if pt_code and ent_code and pt_code != ent_code:
                        self._w(f"gc.addCoincident({pt_code}, {ent_code})")

                elif ctype == "ParallelConstraint":
                    l1 = self._resolve_sketch_curve_ref(c.get("lineOne"), curve_vars)
                    l2 = self._resolve_sketch_curve_ref(c.get("lineTwo"), curve_vars)
                    if l1 and l2:
                        self._w(f"gc.addParallel({l1}, {l2})")

                elif ctype == "PerpendicularConstraint":
                    l1 = self._resolve_sketch_curve_ref(c.get("lineOne"), curve_vars)
                    l2 = self._resolve_sketch_curve_ref(c.get("lineTwo"), curve_vars)
                    if l1 and l2:
                        self._w(f"gc.addPerpendicular({l1}, {l2})")

                elif ctype == "TangentConstraint":
                    c1 = self._resolve_sketch_curve_ref(c.get("curveOne"), curve_vars)
                    c2 = self._resolve_sketch_curve_ref(c.get("curveTwo"), curve_vars)
                    if c1 and c2:
                        self._w(f"gc.addTangent({c1}, {c2})")

                elif ctype == "EqualConstraint":
                    c1 = self._resolve_sketch_curve_ref(c.get("curveOne"), curve_vars)
                    c2 = self._resolve_sketch_curve_ref(c.get("curveTwo"), curve_vars)
                    if c1 and c2:
                        self._w(f"gc.addEqual({c1}, {c2})")

        # Profile
        prof = f"{var}_prof"
        if on_face:
            # BRepFace auto-projects boundary → multiple profiles. Select smallest.
            self._w(f"_best_pi, _best_a = 0, float('inf')")
            self._w(f"for _pi in range({var}.profiles.count):")
            self.ind += 1
            self._w(f"_bb = {var}.profiles.item(_pi).boundingBox")
            self._w(f"_a = abs(_bb.maxPoint.x-_bb.minPoint.x)*abs(_bb.maxPoint.y-_bb.minPoint.y)")
            self._w(f"if _a < _best_a: _best_a, _best_pi = _a, _pi")
            self.ind -= 1
            self._w(f"{prof} = {var}.profiles.item(_best_pi)")
        else:
            prof_count = feat.get("profileCount", 1)
            self._w(f"{prof} = {var}.profiles.item(0)  # {prof_count} profile(s)")
        self.profiles[name] = prof

    def _resolve_sketch_entity_ref(self, ref, curve_vars, sk_var, proj_curve_pts=None):
        """Resolve a captured sketch entity reference to a code string."""
        if not ref:
            return None
        rtype = ref.get("type", "")
        ci = ref.get("curveIndex")
        role = ref.get("role", "")

        if rtype == "SketchPoint":
            if role == "origin":
                return f"{sk_var}.originPoint"
            if ci is not None and ci in curve_vars:
                cv = curve_vars[ci]
                if role == "start":
                    return f"{cv}.startSketchPoint"
                elif role == "end":
                    return f"{cv}.endSketchPoint"
                elif role == "center":
                    return f"{cv}.centerSketchPoint"
            # Fallback for BRepBody-projected curves: use _nearest_proj
            if ci is not None and proj_curve_pts and (ci, role) in proj_curve_pts:
                x, y = proj_curve_pts[(ci, role)]
                return f"_nearest_proj({x}, {y})"
            # Fallback: position-based
            pos = ref.get("position")
            if pos:
                return f"P({pos[0]}, {pos[1]}, 0)  # TODO: find matching sketch point"
            return None

        if rtype in ("SketchLine", "SketchArc", "SketchCircle"):
            return self._resolve_sketch_curve_ref(ref, curve_vars)

        return None

    def _resolve_sketch_curve_ref(self, ref, curve_vars):
        """Resolve a captured sketch curve reference to a code string."""
        if not ref:
            return None
        ci = ref.get("curveIndex")
        if ci is not None and ci in curve_vars:
            return curve_vars[ci]
        return None

    # ── Plane resolution ──

    def _resolve_plane(self, plane_info):
        if not plane_info:
            return "root.xYConstructionPlane"
        ptype = plane_info.get("type")
        pname = plane_info.get("name", "")

        if ptype == "ConstructionPlane":
            if pname in self.planes:
                return self.planes[pname]
            builtin = {"XY": "root.xYConstructionPlane",
                       "XZ": "root.xZConstructionPlane",
                       "YZ": "root.yZConstructionPlane"}
            return builtin.get(pname, f'root.xYConstructionPlane  # TODO: "{pname}"')

        if ptype == "BRepFace":
            body_name = plane_info.get("body", "")
            normal = plane_info.get("normal")
            bv = self._body_ref(body_name)
            if normal:
                axis, direction = self._normal_to_axis(normal)
            else:
                axis, direction = "z", 1  # default: top face
            return f'find_face({bv}, "{axis}", {direction})'

        return "root.xYConstructionPlane"

    def _normal_to_axis(self, n):
        ax, ay, az = abs(n[0]), abs(n[1]), abs(n[2])
        if ax >= ay and ax >= az:
            return "x", (1 if n[0] > 0 else -1)
        if ay >= ax and ay >= az:
            return "y", (1 if n[1] > 0 else -1)
        return "z", (1 if n[2] > 0 else -1)

    # ── BRepFace → construction plane ──

    def _brep_face_to_cplane(self, f, curves):
        """Replace BRepFace sketch with construction plane + transformed coords.

        BRepFace sketches auto-project face boundary edges, which interfere
        with profile formation when captured sketch curves overlap the boundary.
        A construction plane at the same position avoids this.

        Uses pointOnFace (actual face Z) instead of sketchOrigin (which can
        differ on beveled extrude faces).
        """
        origin = f["sketchOrigin"]
        xdir = f["sketchXDir"]
        ydir = f["sketchYDir"]

        # Use pointOnFace for the plane offset (more reliable than sketchOrigin
        # on beveled/tapered extrude faces where sketchOrigin may be at the base)
        plane_info = f.get("plane", {})
        pof = plane_info.get("pointOnFace")

        # Normal = cross(xdir, ydir)
        nx = xdir[1] * ydir[2] - xdir[2] * ydir[1]
        ny = xdir[2] * ydir[0] - xdir[0] * ydir[2]
        nz = xdir[0] * ydir[1] - xdir[1] * ydir[0]

        if abs(nz) > 0.9:
            base = "root.xYConstructionPlane"
            offset = pof[2] if pof else origin[2]
        elif abs(ny) > 0.9:
            base = "root.xZConstructionPlane"
            offset = pof[1] if pof else origin[1]
        elif abs(nx) > 0.9:
            base = "root.yZConstructionPlane"
            offset = pof[0] if pof else origin[0]
        else:
            # Non-axis-aligned face — fall back to find_face
            return self._resolve_plane(f.get("plane", {})), curves

        pl_var = f"_cpl_{self._var(f['name'])}"
        self._w(f'{pl_var} = off_plane(root, {base}, "{round(offset, 4)} cm", "{pl_var}")')

        # Transform: old sketch space → model space → new construction plane sketch space
        # For Z-normal: new_sx = model_x, new_sy = model_y
        # model_x = origin[0] + sx * xdir[0] + sy * ydir[0]
        # model_y = origin[1] + sx * xdir[1] + sy * ydir[1]
        def xf(sx, sy):
            mx = origin[0] + sx * xdir[0] + sy * ydir[0]
            my = origin[1] + sx * xdir[1] + sy * ydir[1]
            mz = origin[2] + sx * xdir[2] + sy * ydir[2]
            if abs(nz) > 0.9:
                return round(mx, 4), round(my, 4)
            elif abs(ny) > 0.9:
                return round(mx, 4), round(mz, 4)
            else:
                return round(my, 4), round(mz, 4)

        # Detect handedness flip for arc sweep angle
        if abs(nz) > 0.9:
            det = xdir[0] * ydir[1] - xdir[1] * ydir[0]
        elif abs(ny) > 0.9:
            det = xdir[0] * ydir[2] - xdir[2] * ydir[0]
        else:
            det = xdir[1] * ydir[2] - xdir[2] * ydir[1]
        flip_arcs = det < 0

        new_curves = []
        for c in curves:
            nc = dict(c)
            ctype = c.get("type", "")
            if ctype == "Line":
                nc["start"] = list(xf(*c["start"]))
                nc["end"] = list(xf(*c["end"]))
            elif ctype == "Arc":
                nc["center"] = list(xf(*c["center"]))
                nc["start"] = list(xf(*c["start"]))
                if "end" in c:
                    nc["end"] = list(xf(*c["end"]))
                if flip_arcs and "sweepAngle" in nc:
                    nc["sweepAngle"] = -nc["sweepAngle"]
            elif ctype == "Circle":
                nc["center"] = list(xf(*c["center"]))
            new_curves.append(nc)

        return pl_var, new_curves

    # ── Body reference helpers ──

    def _body_ref(self, name):
        """Get variable reference for a body name, with fallback for renamed bodies."""
        if name in self.bodies:
            return self.bodies[name]
        # Strip parenthesized suffix: "Leg_NL (1)" → "Leg_NL"
        base = re.sub(r'\s*\(\d+\)\s*$', '', name)
        if base != name and base in self.bodies:
            return self.bodies[base]
        # Try adding suffix: "Leg_NL" → "Leg_NL (1)", "Leg_NL (2)", ...
        for suffix in range(1, 5):
            candidate = f"{name} ({suffix})"
            if candidate in self.bodies:
                return self.bodies[candidate]
        return f'find_body("{name}")'

    def _body_list(self, names):
        return f"[{', '.join(self._body_ref(bn) for bn in names)}]"


def _fmt_pt(pt):
    """Format a 3D point list for comments."""
    return f"({pt[0]:.2f}, {pt[1]:.2f}, {pt[2]:.2f})"
