#!/usr/bin/env python3
"""
Fusion 360 Design-to-Code Generator
====================================
Reads introspection JSON (from introspect.py) and emits a complete
standalone Fusion 360 Python script using helper functions.

Usage:
    python generate.py introspection.json > output.py
    cat introspection.json | python generate.py > output.py
"""
import json
import re
import sys
import textwrap


# ── Utilities ──────────────────────────────────────────────────────

def snake(name):
    """Convert PascalCase / camelCase / mixed name to snake_case."""
    s = re.sub(r'[^a-zA-Z0-9]', '_', name)
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', s)
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s)
    s = re.sub(r'_+', '_', s).strip('_').lower()
    return s


def unique_var(base, used):
    """Return a unique variable name based on `base`."""
    if base not in used:
        used.add(base)
        return base
    i = 2
    while f"{base}_{i}" in used:
        i += 1
    name = f"{base}_{i}"
    used.add(name)
    return name


# ── Symbol Table ──────────────────────────────────────────────────

class SymbolTable:
    """Track mappings from Fusion feature/body names to Python variable names."""

    def __init__(self):
        self.planes = {}       # "Groove_Pl" → "grv_pl"
        self.bodies = {}       # "Leg_FL" → "fl_leg"
        self.sketches = {}     # "FL_Leg_Sk" → ("sk", "pr")
        self.extrudes = {}     # "FL_Leg" → "ext_fl"
        self.mirrors = {}      # "Mir_FL_FR" → "mir_fl_fr"
        self.patterns = {}     # "Pat_FrontSlats" → "pat_front"
        self.components = {}   # "Legs" → ("leg_c", "leg_occ")
        self.combines = {}     # "Mort_FL" → "comb_mort_fl"
        self._used = set()
        # Reserve common names
        for r in ("root", "design", "app", "params", "cam"):
            self._used.add(r)

    def add_component(self, name):
        base = snake(name)
        occ_var = unique_var(f"{base}_occ", self._used)
        comp_var = unique_var(f"{base}_c", self._used)
        self.components[name] = (comp_var, occ_var)
        return comp_var, occ_var

    def add_plane(self, name):
        var = unique_var(snake(name), self._used)
        self.planes[name] = var
        return var

    def add_body(self, name):
        var = unique_var(snake(name), self._used)
        self.bodies[name] = var
        return var

    def add_sketch(self, name):
        """Register a sketch. If already created, return existing var."""
        if name in self.sketches:
            return self.sketches[name]
        sk_var = unique_var(f"sk_{snake(name)}", self._used)
        self.sketches[name] = (sk_var, "pr")
        return sk_var, "pr"

    def add_extrude(self, name):
        var = unique_var(f"ext_{snake(name)}", self._used)
        self.extrudes[name] = var
        return var

    def add_mirror(self, name):
        s = snake(name)
        # Avoid double-prefix: if name already starts with "mir", don't add "mir_"
        if s.startswith("mir_"):
            var = unique_var(s, self._used)
        else:
            var = unique_var(f"mir_{s}", self._used)
        self.mirrors[name] = var
        return var

    def add_pattern(self, name):
        s = snake(name)
        if s.startswith("pat_"):
            var = unique_var(s, self._used)
        else:
            var = unique_var(f"pat_{s}", self._used)
        self.patterns[name] = var
        return var

    def add_combine(self, name):
        s = snake(name)
        if s.startswith("comb_"):
            var = unique_var(s, self._used)
        else:
            var = unique_var(f"comb_{s}", self._used)
        self.combines[name] = var
        return var

    def resolve_comp(self, comp_name):
        """Return (comp_var, occ_var) for a component name, or ('root', None) for root."""
        if comp_name in self.components:
            return self.components[comp_name]
        return ("root", None)

    def resolve_plane_ref(self, plane_str, comp_var):
        """Resolve a plane reference string to a Python expression."""
        std = {"XY": "xYConstructionPlane",
               "XZ": "xZConstructionPlane",
               "YZ": "yZConstructionPlane"}
        if plane_str in std:
            return f"{comp_var}.{std[plane_str]}"
        if plane_str in self.planes:
            return self.planes[plane_str]
        return f"{comp_var}.xYConstructionPlane"  # unresolved plane '{plane_str}'

    def resolve_axis_ref(self, axis_name, comp_var):
        """Resolve an axis name to a Python expression."""
        std = {"X": "xConstructionAxis",
               "Y": "yConstructionAxis",
               "Z": "zConstructionAxis"}
        if axis_name in std:
            return f"{comp_var}.{std[axis_name]}"
        return f"{comp_var}.xConstructionAxis"

    def resolve_body(self, body_name):
        """Return the Python variable for a body name."""
        if body_name in self.bodies:
            return self.bodies[body_name]
        return None


# ── Sketch Analysis ───────────────────────────────────────────────

def classify_sketch(feat):
    """Classify a sketch as 'rect', 'slot', 'raw', or 'unknown'."""
    curves = feat.get("curves", [])
    lines = [c for c in curves if c["type"] == "Line" and not c.get("isConstruction")]
    arcs = [c for c in curves if c["type"] == "Arc"]
    circles = [c for c in curves if c["type"] == "Circle"]

    if len(lines) == 4 and len(arcs) == 0 and len(circles) == 0:
        return "rect"
    if len(arcs) == 2 and len(lines) >= 2:
        return "slot"
    # Any sketch with geometry we can replay → raw
    if lines or arcs or circles:
        return "raw"
    return "unknown"


def detect_slot_vertical(feat):
    """For a slot sketch, detect orientation from arc centers."""
    curves = feat.get("curves", [])
    arcs = [c for c in curves if c["type"] == "Arc"]
    if len(arcs) >= 2:
        c1 = arcs[0]["center"]
        c2 = arcs[1]["center"]
        dy = abs(c1[1] - c2[1])
        dx = abs(c1[0] - c2[0])
        return dy > dx
    return True


# ── Code Emitter ──────────────────────────────────────────────────

class CodeEmitter:
    """Accumulates lines of Python code."""

    def __init__(self):
        self.lines = []
        self._indent = 1  # inside def run(context):

    def blank(self):
        self.lines.append("")

    def comment(self, text):
        self.lines.append(f"{'    ' * self._indent}# {text}")

    def section(self, title):
        bar = "=" * 60
        self.blank()
        self.lines.append(f"{'    ' * self._indent}# {bar}")
        self.lines.append(f"{'    ' * self._indent}#  {title}")
        self.lines.append(f"{'    ' * self._indent}# {bar}")

    def emit(self, code):
        for line in code.split("\n"):
            self.lines.append(f"{'    ' * self._indent}{line}")

    def indent(self):
        self._indent += 1

    def dedent(self):
        self._indent -= 1

    def get_code(self):
        return "\n".join(self.lines)


# ── Main Generator ────────────────────────────────────────────────

class Generator:
    def __init__(self, data, body_data=None):
        self.data = data
        self.sym = SymbolTable()
        self.code = CodeEmitter()
        self.timeline = data.get("timeline", [])
        # Track body→component ownership for proxy generation
        self.body_component = {}  # body_name → component_name
        # Track features for mirror inference
        self.recent_extrudes = []  # list of (feat_name, ext_var, body_var, comp_name, op)
        # Track bodies per component for combine inference
        # Resets after each combine within that component
        self.comp_bodies = {}   # comp_name → [body_var, ...]
        self.comp_first_body = {}  # comp_name → body_var (first NewBody = target for Join)
        # Track body variable → component for cross-component face proxies
        self.bodyvar_component = {}  # body_var → comp_name
        # Track if we're inside a conditional gap block
        self.in_gap_block = False
        # Body ground truth for fallback generation
        self.expected_bodies = {}      # comp_name → [body_info, ...]
        self.expected_transforms = {}  # comp_name → transform_dict
        self.gt_all_comps = set()      # all component names in ground truth
        if body_data:
            self._load_body_ground_truth(body_data)

    def _load_body_ground_truth(self, body_data):
        """Flatten hierarchical body data into per-component body lists."""
        self.gt_root_name = None
        def walk(comp, is_root=False):
            name = comp["name"]
            if is_root:
                self.gt_root_name = name
            bodies = comp.get("bodies", [])
            if bodies:
                self.expected_bodies[name] = bodies
            transform = comp.get("transform")
            if transform:
                self.expected_transforms[name] = transform
            # Track ALL component names (even 0-body) for skip logic
            self.gt_all_comps.add(name)
            for child in comp.get("children", []):
                walk(child)
        self.gt_all_comps = set()
        root = body_data.get("components", {})
        if root:
            walk(root, is_root=True)

    def generate(self):
        self._emit_header()
        self._emit_params()
        self._emit_helpers()
        self._emit_constants()
        self._walk_timeline()
        self._emit_body_fallbacks()
        self._emit_fit_view()
        return self._assemble()

    # ── Header ──

    def _emit_header(self):
        pass  # handled in _assemble

    # ── Parameters ──

    def _emit_params(self):
        user_params = self.data.get("userParameters", [])
        if not user_params:
            return

        self.code.section("PARAMETERS")

        # Separate: dimensioned (unit != "") vs dimensionless (unit == "")
        dimensioned = [p for p in user_params if p.get("unit")]
        dimensionless = [p for p in user_params if not p.get("unit")]

        # Further split dimensioned into direct (no param refs) vs derived
        direct = []
        derived = []
        param_names = {p["name"] for p in user_params}
        for p in dimensioned:
            expr = p["expression"]
            if self._is_literal_expr(expr, param_names):
                direct.append(p)
            else:
                derived.append(p)

        # Topologically sort derived params so dependencies come first
        derived = self._topo_sort_params(derived, param_names)

        # 1. Direct dimensioned (no dependencies)
        if direct:
            self.code.emit("for pname, expr, unit in [")
            for p in direct:
                self.code.emit(f'    ("{p["name"]}", "{p["expression"]}", "{p["unit"]}"),')
            self.code.emit("]:")
            self.code.emit('    params.add(pname, adsk.core.ValueInput.createByString(expr), unit, "")')
            self.code.blank()

        # 2. Dimensionless BEFORE derived (derived may reference them)
        if dimensionless:
            self.code.emit("for pname, expr in [")
            for p in dimensionless:
                self.code.emit(f'    ("{p["name"]}", "{p["expression"]}"),')
            self.code.emit("]:")
            self.code.emit('    params.add(pname, adsk.core.ValueInput.createByString(expr), "", "")')
            self.code.blank()

        # 3. Derived dimensioned (depend on other params)
        if derived:
            # Check for refs to non-user params (model params); substitute value
            all_param_names = {p["name"] for p in user_params}
            units_kw = {'in', 'mm', 'cm', 'm', 'ft', 'deg', 'rad'}
            funcs_kw = {'floor', 'ceil', 'sin', 'cos', 'tan', 'sqrt', 'abs'}
            safe_derived = []
            for p in derived:
                tokens = set(re.findall(r'[a-zA-Z_]\w*', p["expression"]))
                refs = tokens - units_kw - funcs_kw
                missing = refs - all_param_names
                if missing:
                    # Expression references model params; use evaluated value
                    val = p.get("value", 0)
                    safe_derived.append({**p, "expression": f"{val} {p['unit']}"})
                else:
                    safe_derived.append(p)

            self.code.emit("for pname, expr, unit in [")
            for p in safe_derived:
                self.code.emit(f'    ("{p["name"]}", "{p["expression"]}", "{p["unit"]}"),')
            self.code.emit("]:")
            self.code.emit('    params.add(pname, adsk.core.ValueInput.createByString(expr), unit, "")')
            self.code.blank()

    def _is_literal_expr(self, expr, param_names):
        """Check if expression is a literal value (no parameter references)."""
        for name in param_names:
            if name in expr:
                return False
        # Also check for operators that suggest derived
        # But "60 in" has a space, "0.375 in" etc are fine
        # If it has +, -, *, /, (, floor, etc. it's derived
        stripped = re.sub(r'[\d.\s]', '', expr)
        # Remove unit suffixes
        stripped = re.sub(r'^(in|mm|cm|m|ft|deg|rad)$', '', stripped)
        if any(op in expr for op in ['+', '-', '*', '/', '(', 'floor', 'ceil', 'tan', 'sin', 'cos']):
            # But "0.375 in" has no ops — the minus could be in negative numbers
            # Check more carefully: is there an operator not part of a number?
            tokens = re.findall(r'[+\-*/()]', expr)
            # Filter out leading minus on numbers
            clean = re.sub(r'^\s*-?\s*[\d.]+\s*\w*\s*$', '', expr)
            if clean.strip():
                return False
        return True

    def _topo_sort_params(self, params_list, all_names):
        """Topologically sort derived params so dependencies come first."""
        if not params_list:
            return params_list
        name_to_param = {p["name"]: p for p in params_list}
        derived_names = set(name_to_param.keys())

        # Build dependency graph within derived params
        deps = {}
        for p in params_list:
            expr = p["expression"]
            deps[p["name"]] = {n for n in derived_names if n != p["name"] and n in expr}

        # Kahn's algorithm
        in_degree = {n: 0 for n in derived_names}
        for n, d in deps.items():
            for dep in d:
                in_degree[dep] = in_degree.get(dep, 0)  # ensure exists
            # n depends on d → d must come first → in_degree of n += len(d)
        # Recalculate properly: edge dep→n means n depends on dep
        in_degree = {n: 0 for n in derived_names}
        for n, d in deps.items():
            in_degree[n] = len(d)

        queue = [n for n in derived_names if in_degree[n] == 0]
        result = []
        while queue:
            queue.sort()  # deterministic
            node = queue.pop(0)
            result.append(name_to_param[node])
            for n, d in deps.items():
                if node in d:
                    in_degree[n] -= 1
                    if in_degree[n] == 0 and n not in [r["name"] for r in result]:
                        queue.append(n)

        # Append any remaining (circular deps) in original order
        seen = {r["name"] for r in result}
        for p in params_list:
            if p["name"] not in seen:
                result.append(p)

        return result

    # ── Helpers ──

    def _emit_helpers(self):
        self.code.section("HELPERS")
        self.code.emit(textwrap.dedent("""\
            def ev(e):
                p = params.itemByName(e)
                return p.value if p else design.unitsManager.evaluateExpression(e, "cm")

            def sketch_rect(comp, plane, x0e, y0e, we, he, name="Sk"):
                sk = comp.sketches.add(plane)
                sk.name = name
                x0, y0, w, h = ev(x0e), ev(y0e), ev(we), ev(he)
                rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(
                    adsk.core.Point3D.create(x0, y0, 0),
                    adsk.core.Point3D.create(x0 + w, y0 + h, 0))
                d = sk.sketchDimensions
                d.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,
                    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
                    adsk.core.Point3D.create(x0+w/2, y0-1, 0)).parameter.expression = we
                d.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,
                    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
                    adsk.core.Point3D.create(x0+w+1, y0+h/2, 0)).parameter.expression = he
                d.addDistanceDimension(sk.originPoint, rect[0].startSketchPoint,
                    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
                    adsk.core.Point3D.create(x0/2, y0-2, 0)).parameter.expression = x0e
                d.addDistanceDimension(sk.originPoint, rect[0].startSketchPoint,
                    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
                    adsk.core.Point3D.create(x0-1, y0/2, 0)).parameter.expression = y0e
                return sk, sk.profiles.item(0)

            def sketch_slot(comp, plane, cxe, cye, long_e, short_e, vertical=True, name="Sk"):
                sk = comp.sketches.add(plane)
                sk.name = name
                cx, cy = ev(cxe), ev(cye)
                lv, sv = ev(long_e), ev(short_e)
                r, s = sv / 2, (lv - sv) / 2
                P = adsk.core.Point3D.create
                arcs = sk.sketchCurves.sketchArcs
                lns = sk.sketchCurves.sketchLines
                if vertical:
                    a1 = arcs.addByCenterStartSweep(P(cx, cy+s, 0), P(cx+r, cy+s, 0), math.pi)
                    a2 = arcs.addByCenterStartSweep(P(cx, cy-s, 0), P(cx-r, cy-s, 0), math.pi)
                    lns.addByTwoPoints(P(cx-r, cy+s, 0), P(cx-r, cy-s, 0))
                    lns.addByTwoPoints(P(cx+r, cy-s, 0), P(cx+r, cy+s, 0))
                else:
                    a1 = arcs.addByCenterStartSweep(P(cx+s, cy, 0), P(cx+s, cy+r, 0), math.pi)
                    a2 = arcs.addByCenterStartSweep(P(cx-s, cy, 0), P(cx-s, cy-r, 0), math.pi)
                    lns.addByTwoPoints(P(cx-s, cy+r, 0), P(cx+s, cy+r, 0))
                    lns.addByTwoPoints(P(cx+s, cy-r, 0), P(cx-s, cy-r, 0))
                sk.geometricConstraints.addEqual(a1, a2)
                d = sk.sketchDimensions
                H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
                V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
                d.addRadialDimension(a1,
                    P(cx + r*0.7, cy + s + r*0.3, 0) if vertical
                    else P(cx + s + r*0.3, cy + r*0.7, 0)
                ).parameter.expression = f"{short_e} / 2"
                d.addDistanceDimension(a1.centerSketchPoint, a2.centerSketchPoint,
                    V if vertical else H, P(cx + r + 1, cy, 0)
                ).parameter.expression = f"{long_e} - {short_e}"
                d.addDistanceDimension(sk.originPoint, a1.centerSketchPoint,
                    H, P(cx/2, cy + s - 1, 0)).parameter.expression = cxe
                d.addDistanceDimension(sk.originPoint, a1.centerSketchPoint,
                    V, P(cx - 1, (cy + s)/2, 0)
                ).parameter.expression = (f"{cye} + ({long_e} - {short_e}) / 2"
                                          if vertical else cye)
                prof = sk.profiles.item(0)
                if sk.profiles.count > 1:
                    for i in range(sk.profiles.count):
                        p = sk.profiles.item(i)
                        if p.profileLoops.count == 1:
                            prof = p
                            break
                return sk, prof

            def ext_new(comp, prof, dist, name="Ext"):
                inp = comp.features.extrudeFeatures.createInput(
                    prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
                inp.setDistanceExtent(False, adsk.core.ValueInput.createByString(dist))
                f = comp.features.extrudeFeatures.add(inp)
                f.name = name
                return f

            def ext_cut(comp, prof, dist, body, name="Cut"):
                inp = comp.features.extrudeFeatures.createInput(
                    prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
                inp.setDistanceExtent(False, adsk.core.ValueInput.createByString(dist))
                inp.participantBodies = [body]
                f = comp.features.extrudeFeatures.add(inp)
                f.name = name
                return f

            def ext_join(comp, prof, dist, body, name="Join"):
                inp = comp.features.extrudeFeatures.createInput(
                    prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
                inp.setDistanceExtent(False, adsk.core.ValueInput.createByString(dist))
                inp.participantBodies = [body]
                f = comp.features.extrudeFeatures.add(inp)
                f.name = name
                return f

            def ext_new_sym(comp, prof, dist, name="Ext"):
                inp = comp.features.extrudeFeatures.createInput(
                    prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
                inp.setSymmetricExtent(adsk.core.ValueInput.createByString(dist), True)
                f = comp.features.extrudeFeatures.add(inp)
                f.name = name
                return f

            def off_plane(comp, base, expr, name="Pl"):
                inp = comp.constructionPlanes.createInput()
                inp.setByOffset(base, adsk.core.ValueInput.createByString(expr))
                p = comp.constructionPlanes.add(inp)
                p.name = name
                return p

            def combine(comp, target, tool_bodies, op, keep_tool, name="Comb"):
                coll = adsk.core.ObjectCollection.create()
                if isinstance(tool_bodies, list):
                    for b in tool_bodies:
                        coll.add(b)
                else:
                    coll.add(tool_bodies)
                inp = comp.features.combineFeatures.createInput(target, coll)
                inp.operation = op
                inp.isKeepToolBodies = keep_tool
                f = comp.features.combineFeatures.add(inp)
                f.name = name
                return f

            def mirror_feat(comp, features, plane, name="Mir"):
                coll = adsk.core.ObjectCollection.create()
                for f in features:
                    coll.add(f)
                inp = comp.features.mirrorFeatures.createInput(coll, plane)
                m = comp.features.mirrorFeatures.add(inp)
                m.name = name
                return m

            def mirror_bodies(comp, bodies, plane, name="Mir"):
                coll = adsk.core.ObjectCollection.create()
                for b in bodies:
                    coll.add(b)
                inp = comp.features.mirrorFeatures.createInput(coll, plane)
                m = comp.features.mirrorFeatures.add(inp)
                m.name = name
                return m

            def body_pattern(comp, body, axis, count_expr, spacing_expr, name="Pat"):
                coll = adsk.core.ObjectCollection.create()
                coll.add(body)
                inp = comp.features.rectangularPatternFeatures.createInput(
                    coll, axis,
                    adsk.core.ValueInput.createByString(count_expr),
                    adsk.core.ValueInput.createByString(spacing_expr),
                    adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
                pat = comp.features.rectangularPatternFeatures.add(inp)
                pat.name = name
                return pat

            def make_comp(name, matrix=None):
                m = matrix if matrix else adsk.core.Matrix3D.create()
                occ = root.occurrences.addNewComponent(m)
                occ.component.name = name
                return occ

            def box_body(comp, x0, y0, z0, sx, sy, sz, name="Body"):
                if abs(z0) > 0.001:
                    pl = off_plane(comp, comp.xYConstructionPlane, f"{z0} cm", f"{name}_Pl")
                else:
                    pl = comp.xYConstructionPlane
                sk = comp.sketches.add(pl)
                sk.sketchCurves.sketchLines.addTwoPointRectangle(
                    adsk.core.Point3D.create(x0, y0, 0),
                    adsk.core.Point3D.create(x0 + sx, y0 + sy, 0))
                f = ext_new(comp, sk.profiles.item(0), f"{sz} cm", name)
                b = f.bodies.item(0)
                b.name = name
                return b

"""))

    # ── Constants ──

    def _emit_constants(self):
        self.code.blank()
        self.code.emit("JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation")
        self.code.emit("CUT  = adsk.fusion.FeatureOperations.CutFeatureOperation")

    # ── Timeline Walk ──

    def _walk_timeline(self):
        # Build sketch lookup: (component, sketch_name) → sketch feature data
        # Also keep simple name lookup as fallback (last wins)
        self.sketch_data = {}
        self.sketch_data_by_comp = {}
        for feat in self.timeline:
            if feat.get("type") == "Sketch":
                self.sketch_data[feat["name"]] = feat
                key = (feat.get("component", ""), feat["name"])
                self.sketch_data_by_comp[key] = feat

        # Build per-feature lookup by index for context
        self.feat_by_idx = {f["index"]: f for f in self.timeline}

        # Track feature lists for mirror_feat inference
        self.feat_list_tracker = {}  # comp_name → list of ext_vars

        current_section = None
        prev_comp = None

        # Components with ground truth — skip all geometry features
        gt_comps = getattr(self, 'gt_all_comps', set())

        for feat in self.timeline:
            if feat.get("isRolledBack"):
                continue

            ftype = feat.get("type")
            comp_name = feat.get("component", "")

            # Close gap block if current feature is not a gap feature
            fname = feat.get("name", "")
            is_gap = "Gap" in fname or "gap" in fname
            if self.in_gap_block and not is_gap and ftype != "Sketch":
                self.code.dedent()
                self.in_gap_block = False

            # Skip ALL features for components with ground truth
            # (including ComponentCreation — we create them in the fallback section)
            in_gt = comp_name in gt_comps or (gt_comps and comp_name == "")
            if in_gt:
                continue
            # Also skip ComponentCreation for gt components
            if ftype == "ComponentCreation" and feat.get("name", "") in gt_comps:
                continue

            # Section headers on component change
            if comp_name and comp_name != prev_comp:
                self.code.section(comp_name.upper())
                prev_comp = comp_name

            if ftype == "ComponentCreation":
                self._gen_component(feat)
            elif ftype == "ConstructionPlane":
                self._gen_plane(feat)
            elif ftype == "Sketch":
                # Sketches are emitted inline with their consuming extrude
                pass
            elif ftype == "Extrude":
                self._gen_extrude(feat)
            elif ftype == "Mirror":
                self._gen_mirror(feat)
            elif ftype == "RectangularPattern":
                self._gen_pattern(feat)
            elif ftype == "Combine":
                self._gen_combine(feat)
            elif ftype == "Move":
                self._gen_move(feat)
            elif ftype == "Snapshot":
                pass  # position capture only, no geometry

    # ── Component Creation ──

    def _gen_component(self, feat):
        name = feat["name"]
        comp_var, occ_var = self.sym.add_component(name)
        self.code.blank()
        self.code.emit(f'{occ_var} = make_comp("{name}")')
        self.code.emit(f"{comp_var} = {occ_var}.component")

    # ── Construction Plane ──

    def _gen_plane(self, feat):
        name = feat["name"]
        comp_name = feat.get("component", "")
        comp_var, _ = self.sym.resolve_comp(comp_name)

        offset_expr = feat.get("offset", "0 in")
        base_plane = feat.get("basePlane", "XY")

        # Resolve base plane — strip Fusion type prefixes
        base_ref = self._resolve_base_plane(base_plane, comp_var)

        var = self.sym.add_plane(name)
        self.code.blank()
        self.code.emit(f'{var} = off_plane({comp_var}, {base_ref}, "{offset_expr}", "{name}")')

    def _resolve_base_plane(self, base_plane, comp_var):
        """Resolve base plane string to Python expression."""
        std_map = {
            "XY": "xYConstructionPlane",
            "XZ": "xZConstructionPlane",
            "YZ": "yZConstructionPlane",
        }
        # Check standard planes
        for key, attr in std_map.items():
            if key in base_plane:
                return f"{comp_var}.{attr}"
        # Check if it's a named construction plane we know
        if base_plane in self.sym.planes:
            return self.sym.planes[base_plane]
        # Fallback
        return f"{comp_var}.xYConstructionPlane"  # unresolved base_plane

    # ── Extrude ──

    def _gen_extrude(self, feat):
        name = feat["name"]
        comp_name = feat.get("component", "")
        comp_var, occ_var = self.sym.resolve_comp(comp_name)
        operation = feat.get("operation", "NewBody")
        extent_type = feat.get("extentType", "Distance")
        distance = feat.get("distance", "1 in")
        sketch_name = feat.get("sketch", "")
        bodies = feat.get("bodies", [])

        # Check for gap features — wrap in conditional
        is_gap = "Gap" in name or "gap" in name
        if is_gap and not self.in_gap_block:
            self._start_gap_block(feat)

        # Get sketch data — prefer component-qualified lookup
        sk_data = self.sketch_data_by_comp.get((comp_name, sketch_name))
        if not sk_data:
            sk_data = self.sketch_data.get(sketch_name)
        sk_type = classify_sketch(sk_data) if sk_data else "unknown"

        # Unique sketch key for shared tracking (component-qualified)
        sk_key = f"{comp_name}::{sketch_name}" if comp_name else sketch_name

        # Shared sketch: if already created, reuse and just select profile
        if sketch_name and sk_key in self.sym.sketches:
            sk_var, _ = self.sym.sketches[sk_key]
            pr_var = self._emit_profile_selection(feat, sk_data, sk_var)
            self.code.blank()
            self._emit_extrude_call(feat, comp_var, pr_var)
            return

        # Store sk_key for sub-methods to register with
        self._current_sk_key = sk_key

        # Resolve the sketch plane
        plane_ref = self._resolve_sketch_plane(sk_data, comp_var) if sk_data else f"{comp_var}.xYConstructionPlane"

        # Determine if this is a BRepFace sketch
        plane = sk_data.get("plane", "") if sk_data else ""
        if isinstance(plane, dict):
            is_face_sketch = plane.get("type") == "BRepFace"
        else:
            is_face_sketch = str(plane).startswith("BRepFace")

        if is_face_sketch:
            self._gen_face_sketch_extrude(feat, sk_data, comp_var)
            return

        if sk_type == "rect":
            self._gen_rect_extrude(feat, sk_data, comp_var, plane_ref)
        elif sk_type == "slot":
            self._gen_slot_extrude(feat, sk_data, comp_var, plane_ref)
        elif sk_type == "raw":
            self._gen_raw_sketch_extrude(feat, sk_data, comp_var, plane_ref)
        else:
            self.code.blank()
            self.code.comment(f"SKIPPED {name}: no sketch data")
            # Register bodies so downstream references don't break
            for body_name in feat.get("bodies", []):
                if body_name not in self.sym.bodies:
                    self.code.comment(f"  body '{body_name}' not created")

    def _resolve_sketch_plane(self, sk_data, comp_var):
        """Get the plane reference for a sketch."""
        if not sk_data:
            return f"{comp_var}.xYConstructionPlane"
        plane = sk_data.get("plane", "XY")
        # Handle structured dict from capture_design tool
        if isinstance(plane, dict):
            if plane.get("type") == "BRepFace":
                return None  # handled separately
            plane_str = plane.get("name", "XY")
        else:
            plane_str = plane
            if plane_str.startswith("BRepFace"):
                return None  # handled separately
        return self.sym.resolve_plane_ref(plane_str, comp_var)

    def _gen_rect_extrude(self, feat, sk_data, comp_var, plane_ref):
        """Generate sketch_rect + extrude."""
        name = feat["name"]
        sk_name = sk_data["name"]
        dims = sk_data.get("dimensions", [])

        # Register sketch as created for shared sketch tracking
        sk_key = getattr(self, '_current_sk_key', sk_name)
        self.sym.add_sketch(sk_key)

        # Map dimensions: [width, height, x_offset, y_offset]
        if len(dims) >= 4:
            we = dims[0]["expression"]
            he = dims[1]["expression"]
            x0e = dims[2]["expression"]
            y0e = dims[3]["expression"]
        else:
            # Dimensionless: compute from line coordinates
            bbox = self._compute_bbox(sk_data)
            we = dims[0]["expression"] if len(dims) > 0 else f"{bbox['w']} cm"
            he = dims[1]["expression"] if len(dims) > 1 else f"{bbox['h']} cm"
            x0e = dims[2]["expression"] if len(dims) > 2 else f"{bbox['x0']} cm"
            y0e = dims[3]["expression"] if len(dims) > 3 else f"{bbox['y0']} cm"

        self.code.blank()
        self.code.emit(
            f'_, pr = sketch_rect({comp_var}, {plane_ref},\n'
            f'    "{x0e}", "{y0e}", "{we}", "{he}", "{sk_name}")')

        self._emit_extrude_call(feat, comp_var, "pr")

    def _gen_slot_extrude(self, feat, sk_data, comp_var, plane_ref):
        """Generate sketch_slot + extrude."""
        sk_name = sk_data["name"]
        sk_key = getattr(self, '_current_sk_key', sk_name)
        self.sym.add_sketch(sk_key)
        dims = sk_data.get("dimensions", [])
        vertical = detect_slot_vertical(sk_data)

        # Stadium dims: [radius_dim, center_dist_dim, cx, cy]
        # dims[0] is SketchRadialDimension → expression is "short_e / 2"
        # dims[1] is SketchLinearDimension → expression is "long_e - short_e"
        # dims[2] → cx, dims[3] → cy (may have offset correction)

        short_e, long_e, cxe, cye = self._parse_slot_dims(dims, vertical)

        vert_str = "True" if vertical else "False"
        self.code.blank()
        self.code.emit(
            f'_, pr = sketch_slot({comp_var}, {plane_ref},\n'
            f'    "{cxe}",\n'
            f'    "{cye}",\n'
            f'    "{long_e}", "{short_e}", vertical={vert_str}, name="{sk_name}")')

        self._emit_extrude_call(feat, comp_var, "pr")

    def _parse_slot_dims(self, dims, vertical):
        """Parse slot dimensions into (short_e, long_e, cxe, cye)."""
        if len(dims) < 4:
            return "0.25 in", "0.5 in", "0 in", "0 in"

        # dims[0]: radial → "param / 2" → extract param (the short dim)
        rad_expr = dims[0].get("expression", "0.25 in")
        # The radial dim expression is "short_e / 2", so short_e = expression * 2
        # But in our helper, we pass short_e directly and the helper does /2
        # So we need to recover short_e from the expression
        short_e = self._recover_short_from_radial(rad_expr)

        # dims[1]: linear → "long_e - short_e" (center distance)
        # In our helper, we pass long_e directly and the helper computes long_e - short_e
        # So we need long_e = expression + short_e
        dist_expr = dims[1].get("expression", "0.5 in")
        long_e = self._recover_long_from_dist(dist_expr, short_e)

        # dims[2]: cx position
        cxe = dims[2].get("expression", "0 in")

        # dims[3]: cy position — may include offset correction for vertical
        cye_expr = dims[3].get("expression", "0 in")
        # The helper adds "(long_e - short_e) / 2" when vertical, so the dim expression
        # is "cye + (long_e - short_e) / 2". We need to recover just cye.
        cye = self._recover_cy(cye_expr, long_e, short_e, vertical)

        return short_e, long_e, cxe, cye

    def _recover_short_from_radial(self, expr):
        """From radial dim expression 'param / 2', recover param name."""
        # Expression is like "dm_bt_w / 2" → we want "dm_bt_w"
        m = re.match(r'^\s*(.+?)\s*/\s*2\s*$', expr)
        if m:
            return m.group(1).strip()
        # Could also be a raw value
        return expr

    def _recover_long_from_dist(self, expr, short_e):
        """From center-distance expression 'long - short', recover long."""
        # Expression is like "dm_bt_h - dm_bt_w" → we want "dm_bt_h"
        m = re.match(r'^\s*(.+?)\s*-\s*' + re.escape(short_e) + r'\s*$', expr)
        if m:
            return m.group(1).strip()
        # Fallback: expression + short_e
        return f"({expr}) + {short_e}"

    def _recover_cy(self, expr, long_e, short_e, vertical):
        """From dim[3] expression, recover the raw cy value.

        When vertical=True, the helper sets dim[3] to:
            cye + (long_e - short_e) / 2
        So we need to subtract that offset to get cye.
        """
        if not vertical:
            return expr

        # Try to detect and strip the offset pattern
        # Pattern: "base_expr + (long_e - short_e) / 2"
        suffix = f"({long_e} - {short_e}) / 2"
        if suffix in expr:
            cye = expr.replace(f" + {suffix}", "").replace(f"+ {suffix}", "").strip()
            if cye:
                return cye

        # If we can't parse it, return as-is (user may need to fix)
        return expr

    def _compute_bbox(self, sk_data):
        """Compute bounding box from sketch line coordinates. Returns dict with x0, y0, w, h."""
        curves = sk_data.get("curves", [])
        xs, ys = [], []
        for c in curves:
            if c["type"] == "Line" and not c.get("isConstruction"):
                xs.extend([c["start"][0], c["end"][0]])
                ys.extend([c["start"][1], c["end"][1]])
            elif c["type"] in ("Arc", "Circle"):
                cx, cy = c.get("center", [0, 0])
                r = c.get("radius", 0)
                xs.extend([cx - r, cx + r])
                ys.extend([cy - r, cy + r])
        if not xs:
            return {"x0": 0, "y0": 0, "w": 1, "h": 1}
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        return {
            "x0": round(x_min, 4),
            "y0": round(y_min, 4),
            "w": round(x_max - x_min, 4),
            "h": round(y_max - y_min, 4),
        }

    def _gen_face_sketch_extrude(self, feat, sk_data, comp_var):
        """Generate face-finding code + sketch + extrude for BRepFace sketches."""
        name = feat["name"]
        sk_name = sk_data["name"]
        comp_name = feat.get("component", "")
        plane_data = sk_data.get("plane", "")
        # Handle structured dict from capture_design tool
        if isinstance(plane_data, dict):
            body_name = plane_data.get("body", "")
            normal = plane_data.get("normal", [0, 0, 0])
            point = plane_data.get("origin", [0, 0, 0])
        else:
            normal = sk_data.get("faceNormal", [0, 0, 0])
            point = sk_data.get("facePoint", [0, 0, 0])
            m = re.match(r'BRepFace\(body=(.+)\)', str(plane_data))
            body_name = m.group(1) if m else ""
        body_var = self.sym.resolve_body(body_name)

        if not body_var:
            self.code.blank()
            self.code.comment(f"TODO: resolve body '{body_name}' for face sketch")
            body_var = snake(body_name)

        # Check if body is in a different component → need assembly proxy for face
        body_comp = self.bodyvar_component.get(body_var, self.body_component.get(body_name, ""))
        needs_proxy = body_comp and body_comp != comp_name

        # Determine which face to find based on normal/point
        axis, direction = self._face_selection_strategy(normal, point)

        # If cross-component, create proxy body first
        if needs_proxy:
            _, body_occ = self.sym.resolve_comp(body_comp)
            if body_occ:
                proxy_body = unique_var(f"{body_var}_proxy", self.sym._used)
                self.code.blank()
                self.code.emit(f"{proxy_body} = {body_var}.createForAssemblyContext({body_occ})")
                body_var = proxy_body

        face_var = unique_var("target_face", self.sym._used)
        self.code.blank()
        self.code.emit(f"{face_var} = None")
        if direction == "min":
            self.code.emit(f"min_val = float('inf')")
            self.code.emit(f"for i in range({body_var}.faces.count):")
            self.code.emit(f"    f = {body_var}.faces.item(i)")
            self.code.emit(f"    if f.pointOnFace.{axis} < min_val:")
            self.code.emit(f"        min_val = f.pointOnFace.{axis}")
            self.code.emit(f"        {face_var} = f")
        else:
            self.code.emit(f"max_val = float('-inf')")
            self.code.emit(f"for i in range({body_var}.faces.count):")
            self.code.emit(f"    f = {body_var}.faces.item(i)")
            self.code.emit(f"    if f.pointOnFace.{axis} > max_val:")
            self.code.emit(f"        max_val = f.pointOnFace.{axis}")
            self.code.emit(f"        {face_var} = f")

        # Now emit the sketch on that face
        sk_type = classify_sketch(sk_data)
        if sk_type == "slot":
            dims = sk_data.get("dimensions", [])
            vertical = detect_slot_vertical(sk_data)
            short_e, long_e, cxe, cye = self._parse_slot_dims(dims, vertical)
            vert_str = "True" if vertical else "False"
            self.code.blank()
            self.code.emit(
                f'_, pr = sketch_slot({comp_var}, {face_var},\n'
                f'    "{cxe}",\n'
                f'    "{cye}",\n'
                f'    "{long_e}", "{short_e}", vertical={vert_str}, name="{sk_name}")')
        elif sk_type == "rect":
            dims = sk_data.get("dimensions", [])
            we = dims[0]["expression"] if len(dims) > 0 else "1 in"
            he = dims[1]["expression"] if len(dims) > 1 else "1 in"
            x0e = dims[2]["expression"] if len(dims) > 2 else "0 in"
            y0e = dims[3]["expression"] if len(dims) > 3 else "0 in"
            self.code.blank()
            self.code.emit(
                f'_, pr = sketch_rect({comp_var}, {face_var},\n'
                f'    "{x0e}", "{y0e}", "{we}", "{he}", "{sk_name}")')
        elif sk_type == "raw":
            sk_var = self._gen_raw_sketch(sk_data, comp_var, face_var)
            pr_var = self._emit_profile_selection(feat, sk_data, sk_var)
            self._emit_extrude_call(feat, comp_var, pr_var)
            return
        else:
            self.code.blank()
            self.code.comment(f"TODO: no sketch geometry for face sketch {sk_name}")

        self._emit_extrude_call(feat, comp_var, "pr")

    def _gen_raw_sketch_extrude(self, feat, sk_data, comp_var, plane_ref):
        """Generate raw sketch geometry replay + extrude for non-rect/non-slot sketches."""
        sk_var = self._gen_raw_sketch(sk_data, comp_var, plane_ref)
        pr_var = self._emit_profile_selection(feat, sk_data, sk_var)
        self._emit_extrude_call(feat, comp_var, pr_var)

    def _gen_raw_sketch(self, sk_data, comp_var, plane_ref):
        """Emit raw Fusion 360 API code that replays exact sketch geometry from coordinates.
        Returns the sketch variable name."""
        sk_name = sk_data["name"]
        curves = sk_data.get("curves", [])

        # Register in symbol table (component-qualified key)
        sk_key = getattr(self, '_current_sk_key', sk_name)
        sk_var = unique_var(f"sk_{snake(sk_name)}", self.sym._used)
        self.sym.sketches[sk_key] = (sk_var, "pr")

        self.code.blank()
        self.code.emit(f'{sk_var} = {comp_var}.sketches.add({plane_ref})')
        self.code.emit(f'{sk_var}.name = "{sk_name}"')
        self.code.emit(f'P = adsk.core.Point3D.create')

        has_lines = any(c["type"] == "Line" for c in curves if not c.get("isConstruction"))
        has_arcs = any(c["type"] == "Arc" for c in curves)
        has_circles = any(c["type"] == "Circle" for c in curves)

        if has_lines:
            self.code.emit(f'lns = {sk_var}.sketchCurves.sketchLines')
        if has_arcs:
            self.code.emit(f'arcs = {sk_var}.sketchCurves.sketchArcs')
        if has_circles:
            self.code.emit(f'circs = {sk_var}.sketchCurves.sketchCircles')

        for c in curves:
            if c["type"] == "Line" and not c.get("isConstruction"):
                s, e = c["start"], c["end"]
                self.code.emit(
                    f'lns.addByTwoPoints(P({s[0]}, {s[1]}, 0), P({e[0]}, {e[1]}, 0))')
            elif c["type"] == "Line" and c.get("isConstruction"):
                s, e = c["start"], c["end"]
                self.code.emit(
                    f'cl = {sk_var}.sketchCurves.sketchLines.addByTwoPoints('
                    f'P({s[0]}, {s[1]}, 0), P({e[0]}, {e[1]}, 0))')
                self.code.emit(f'cl.isConstruction = True')
            elif c["type"] == "Arc":
                cx, cy = c["center"]
                sx, sy = c["start"]
                sweep = c.get("sweepAngle", 3.1416)
                self.code.emit(
                    f'arcs.addByCenterStartSweep(P({cx}, {cy}, 0), '
                    f'P({sx}, {sy}, 0), {sweep})')
            elif c["type"] == "Circle":
                cx, cy = c["center"]
                r = c["radius"]
                self.code.emit(
                    f'circs.addByCenterRadius(P({cx}, {cy}, 0), {r})')

        return sk_var

    def _emit_profile_selection(self, feat, sk_data, sk_var):
        """Emit profile selection code. Returns the profile variable name."""
        profile_idx = feat.get("profileIndex", 0)
        profile_count = feat.get("profileCount", sk_data.get("profileCount", 1) if sk_data else 1)

        if profile_count <= 1:
            pr_var = unique_var("pr", self.sym._used)
            self.code.emit(f'{pr_var} = {sk_var}.profiles.item(0)')
            return pr_var

        # Multi-profile sketch — use bounding box matching
        pr_var = unique_var("pr", self.sym._used)
        self.code.emit(f'{pr_var} = {sk_var}.profiles.item({profile_idx})')
        return pr_var

    def _face_selection_strategy(self, normal, point):
        """Determine axis and min/max for face selection based on normal vector."""
        # The face with the strongest normal component on an axis
        # and whether we want the min or max face along that axis
        abs_n = [abs(normal[0]), abs(normal[1]), abs(normal[2])]
        max_idx = abs_n.index(max(abs_n))
        axes = ['x', 'y', 'z']
        axis = axes[max_idx]

        # If normal points in negative direction, the face is at the min end
        if normal[max_idx] < 0:
            return axis, "min"
        else:
            return axis, "max"

    def _emit_extrude_call(self, feat, comp_var, pr_var):
        """Emit the extrude function call and body registration."""
        name = feat["name"]
        operation = feat.get("operation", "NewBody")
        extent_type = feat.get("extentType", "Distance")
        distance = feat.get("distance", "1 in")
        bodies = feat.get("bodies", [])
        comp_name = feat.get("component", "")

        if operation == "NewBody":
            ext_var = self.sym.add_extrude(name)
            if extent_type == "Symmetric":
                self.code.emit(f'{ext_var} = ext_new_sym({comp_var}, {pr_var}, "{distance}", "{name}")')
            else:
                self.code.emit(f'{ext_var} = ext_new({comp_var}, {pr_var}, "{distance}", "{name}")')

            # Register created body (synthesize name from feature name if empty)
            body_name = bodies[0] if bodies else name
            body_var = self.sym.add_body(body_name)
            self.code.emit(f"{body_var} = {ext_var}.bodies.item(0)")
            self.code.emit(f'{body_var}.name = "{body_name}"')
            self.body_component[body_name] = comp_name
            self.bodyvar_component[body_var] = comp_name
            # Track for mirror/combine inference: (name, ext_var, body_var, comp, op)
            self.recent_extrudes.append((name, ext_var, body_var, comp_name, "NewBody"))
            if comp_name not in self.comp_bodies:
                self.comp_bodies[comp_name] = []
            self.comp_bodies[comp_name].append(body_var)
            if comp_name not in self.comp_first_body:
                self.comp_first_body[comp_name] = body_var

        elif operation == "Cut":
            ext_var = self.sym.add_extrude(name)
            target = self._resolve_cut_join_target(feat)
            self.code.emit(f'{ext_var} = ext_cut({comp_var}, {pr_var}, "{distance}", {target}, "{name}")')
            self.recent_extrudes.append((name, ext_var, None, comp_name, "Cut"))

        elif operation == "Join":
            ext_var = self.sym.add_extrude(name)
            target = self._resolve_cut_join_target(feat)
            self.code.emit(f'{ext_var} = ext_join({comp_var}, {pr_var}, "{distance}", {target}, "{name}")')
            self.recent_extrudes.append((name, ext_var, None, comp_name, "Join"))

    def _resolve_cut_join_target(self, feat):
        """Resolve the target body for Cut/Join operations."""
        # Try participantBodies first
        participants = feat.get("participantBodies", [])
        if participants:
            body_var = self.sym.resolve_body(participants[0])
            if body_var:
                return body_var

        # Try bodies list (the body that was modified)
        bodies = feat.get("bodies", [])
        if bodies:
            body_var = self.sym.resolve_body(bodies[0])
            if body_var:
                return body_var

        # Infer: first body in this component is likely the target
        comp_name = feat.get("component", "")
        if comp_name in self.comp_first_body:
            return self.comp_first_body[comp_name]

        return "None"

    # ── Mirror ──

    def _gen_mirror(self, feat):
        name = feat["name"]
        comp_name = feat.get("component", "")
        comp_var, _ = self.sym.resolve_comp(comp_name)
        mirror_plane_raw = feat.get("mirrorPlane", "")
        # Handle structured dict from capture_design tool
        if isinstance(mirror_plane_raw, dict):
            mirror_plane = mirror_plane_raw.get("name", "")
        else:
            mirror_plane = mirror_plane_raw
        bodies = feat.get("bodies", [])

        plane_ref = self.sym.resolve_plane_ref(mirror_plane, comp_var)
        mir_var = self.sym.add_mirror(name)

        # Split bodies into known (originals = inputs) vs new (created by mirror)
        known_vars = []  # already-registered bodies → these were the inputs
        new_bodies = []  # unregistered → these are the new mirrored copies
        for b in bodies:
            existing = self.sym.resolve_body(b)
            if existing:
                known_vars.append(existing)
            else:
                new_bodies.append(b)

        # Determine mirror type from context
        recent_in_comp = [r for r in self.recent_extrudes if r[3] == comp_name]

        self.code.blank()

        if not bodies:
            # Empty bodies → feature mirror (tenon pattern: bodies consumed by combine)
            # Use only the most recent NewBody extrude (not cuts on existing bodies)
            if recent_in_comp:
                new_body_feats = [r for r in recent_in_comp
                                  if r[2] is not None]  # has a body var = NewBody
                if new_body_feats:
                    feat_vars = [new_body_feats[-1][1]]  # last NewBody extrude only
                else:
                    feat_vars = [recent_in_comp[-1][1]]
                feat_list = "[" + ", ".join(feat_vars) + "]"
                self.code.emit(f'{mir_var} = mirror_feat({comp_var}, {feat_list}, {plane_ref}, "{name}")')
            else:
                self.code.comment(f"TODO: determine mirror inputs for {name}")
                self.code.emit(f'{mir_var} = mirror_bodies({comp_var}, [], {plane_ref}, "{name}")')

            # Synthesize body name for the mirrored output
            synth_name = name.replace("Mir", "").strip("_") + "_Mir"
            body_var = self.sym.add_body(synth_name)
            self.code.emit(f"{body_var} = {mir_var}.bodies.item(0)")
            self.code.emit(f'{body_var}.name = "{synth_name}"')
            self.body_component[synth_name] = comp_name
            self.bodyvar_component[body_var] = comp_name
            if comp_name not in self.comp_bodies:
                self.comp_bodies[comp_name] = []
            self.comp_bodies[comp_name].append(body_var)

        elif known_vars:
            # Determine if this should be mirror_feat or mirror_bodies.
            # mirror_feat: when building a composite template (NewBody + Cuts + Joins)
            # mirror_bodies: for simple body duplication (even with cuts-only modifications)
            # Key signal: Join operations indicate material was ADDED (tongues, etc.)
            has_join = any(r[4] == "Join" for r in recent_in_comp)
            use_feat = has_join and len(recent_in_comp) >= 2

            if use_feat:
                feat_vars = [r[1] for r in recent_in_comp]
                feat_list = "[" + ", ".join(feat_vars) + "]"
                self.code.emit(f'{mir_var} = mirror_feat({comp_var}, {feat_list}, {plane_ref}, "{name}")')
            else:
                body_list = "[" + ", ".join(known_vars) + "]"
                self.code.emit(f'{mir_var} = mirror_bodies({comp_var}, {body_list}, {plane_ref}, "{name}")')

            # Register only the NEW bodies
            for i, body_name in enumerate(new_bodies):
                body_var = self.sym.add_body(body_name)
                self.code.emit(f"{body_var} = {mir_var}.bodies.item({i})")
                self.code.emit(f'{body_var}.name = "{body_name}"')
                self.body_component[body_name] = comp_name
                self.bodyvar_component[body_var] = comp_name
                if comp_name not in self.comp_bodies:
                    self.comp_bodies[comp_name] = []
                self.comp_bodies[comp_name].append(body_var)

        else:
            # All bodies are new — infer inputs from recent extrudes
            if recent_in_comp:
                input_vars = [r[2] for r in recent_in_comp if r[2]]
                body_list = "[" + ", ".join(input_vars) + "]"
                self.code.emit(f'{mir_var} = mirror_bodies({comp_var}, {body_list}, {plane_ref}, "{name}")')
            else:
                self.code.comment(f"TODO: determine mirror inputs for {name}")
                self.code.emit(f'{mir_var} = mirror_bodies({comp_var}, [], {plane_ref}, "{name}")')

            for i, body_name in enumerate(new_bodies):
                body_var = self.sym.add_body(body_name)
                self.code.emit(f"{body_var} = {mir_var}.bodies.item({i})")
                self.code.emit(f'{body_var}.name = "{body_name}"')
                self.body_component[body_name] = comp_name
                self.bodyvar_component[body_var] = comp_name
                if comp_name not in self.comp_bodies:
                    self.comp_bodies[comp_name] = []
                self.comp_bodies[comp_name].append(body_var)

        # Clear recent extrudes after mirror consumes them
        self.recent_extrudes = []

    # ── Rectangular Pattern ──

    def _gen_pattern(self, feat):
        name = feat["name"]
        comp_name = feat.get("component", "")
        comp_var, _ = self.sym.resolve_comp(comp_name)
        quantity = feat.get("quantityOne", "2")
        distance = feat.get("distanceOne", "1 in")
        axis_name = feat.get("axisOne", "X")
        inputs = feat.get("inputs", [])
        bodies = feat.get("bodies", [])

        axis_ref = self.sym.resolve_axis_ref(axis_name, comp_var)
        pat_var = self.sym.add_pattern(name)

        # Resolve the template body from inputs or recent context
        template_var = None
        if inputs:
            template_var = self.sym.resolve_body(inputs[0])

        if not template_var:
            # Infer: the most recent body in this component is the template
            tracked = self.comp_bodies.get(comp_name, [])
            if tracked:
                template_var = tracked[-1]
            else:
                self.code.blank()
                self.code.comment(f"TODO: resolve pattern template body for {name}")
                template_var = "template_body"

        self.code.blank()
        self.code.emit(
            f'{pat_var} = body_pattern({comp_var}, {template_var}, {axis_ref},\n'
            f'    "{quantity}", "{distance}", "{name}")')

        # Register patterned bodies
        if bodies:
            base_prefix = bodies[0].rsplit("_", 1)[0] if "_" in bodies[0] else bodies[0]
            self.code.emit(f"for i in range({pat_var}.bodies.count):")
            self.code.emit(f'    {pat_var}.bodies.item(i).name = f"{base_prefix}_{{i + 2}}"')
            for body_name in bodies:
                self.body_component[body_name] = comp_name

    # ── Combine ──

    def _gen_combine(self, feat):
        name = feat["name"]
        comp_name = feat.get("component", "")
        comp_var, _ = self.sym.resolve_comp(comp_name)
        operation = feat.get("operation", "Join")
        target_name = feat.get("targetBody", "")
        tool_names = feat.get("toolBodies", [])
        keep_tools = feat.get("isKeepToolBodies", False)

        op_str = "JOIN" if operation == "Join" else "CUT"

        # Resolve target/tools — use JSON data if available, else infer
        target_var = self.sym.resolve_body(target_name) if target_name else None
        tool_vars = []
        if tool_names:
            for tn in tool_names:
                tv = self.sym.resolve_body(tn)
                if tv:
                    tool_vars.append(tv)

        # If target/tools missing, infer from tracked bodies in component
        if not target_var or not tool_vars:
            target_var, tool_vars = self._infer_combine_bodies(
                comp_name, operation, target_var, tool_vars, name)

        # Detect cross-component combine (mortise pattern)
        is_cross_comp = self._is_cross_component_combine(
            comp_name, target_name, tool_names, name)

        comb_var = self.sym.add_combine(name)
        self.code.blank()

        # Skip if target or tools are unresolved (None)
        if target_var == "None" or "None" in tool_vars:
            self.code.comment(f"SKIPPED {name}: unresolved target/tools")
        elif is_cross_comp:
            self._gen_proxy_combine(feat, comp_var, op_str, target_var,
                                    tool_vars, keep_tools, name, comb_var)
        else:
            tool_list = "[" + ", ".join(tool_vars) + "]"
            self.code.emit(
                f'{comb_var} = combine({comp_var}, {target_var}, {tool_list}, '
                f'{op_str}, {keep_tools}, "{name}")')

        # Reset body tracking unless keep_tools is True (bodies still exist)
        if not keep_tools:
            self.comp_bodies[comp_name] = []

    def _infer_combine_bodies(self, comp_name, operation, target_var, tool_vars, name):
        """Infer combine target/tools from tracked bodies in component."""
        # For mortise combines, use component tree to find legs and rails
        if "Mort" in name and not target_var:
            return self._infer_mortise(name)

        tracked = self.comp_bodies.get(comp_name, [])

        if operation == "Join" and tracked:
            if not target_var:
                target_var = self.comp_first_body.get(comp_name, tracked[0])
            if not tool_vars:
                tool_vars = [b for b in tracked if b != target_var]

        elif operation == "Cut" and tracked:
            if not target_var:
                target_var = self.comp_first_body.get(comp_name, tracked[0])
            if not tool_vars:
                tool_vars = [b for b in tracked if b != target_var]

        if not target_var:
            self.code.comment(f"TODO: resolve combine target for {name}")
            target_var = "None"
        if not tool_vars:
            self.code.comment(f"TODO: resolve combine tools for {name}")
            tool_vars = ["None"]

        return target_var, tool_vars

    def _infer_mortise(self, name):
        """Infer target leg and tool rails for a mortise combine by naming convention.

        Mort_FL → target=Leg_FL, tools=[front_lower, front_upper, left_lower, left_upper]
        Mort_FR → target=Leg_FR, tools=[front_lower, front_upper, right_lower, right_upper]
        Mort_BL → target=Leg_BL, tools=[back_lower, back_upper, left_lower, left_upper]
        Mort_BR → target=Leg_BR, tools=[back_lower, back_upper, right_lower, right_upper]
        """
        # Extract corner from name: Mort_FL, Mort_FR, Mort_BL, Mort_BR
        corner = name.split("_")[-1] if "_" in name else ""

        # Map corner to leg body
        leg_map = {"FL": "Leg_FL", "FR": "Leg_FR", "BL": "Leg_BL", "BR": "Leg_BR"}
        leg_name = leg_map.get(corner, "")
        target_var = self.sym.resolve_body(leg_name)

        if not target_var:
            self.code.comment(f"TODO: resolve mortise target leg for {name}")
            return "None", ["None"]

        # Map corner to adjacent rails
        rail_map = {
            "FL": ["LR_Front_Lower", "LR_Front_Upper", "SR_Left_Lower", "SR_Left_Upper"],
            "FR": ["LR_Front_Lower", "LR_Front_Upper", "SR_Right_Lower", "SR_Right_Upper"],
            "BL": ["LR_Back_Lower", "LR_Back_Upper", "SR_Left_Lower", "SR_Left_Upper"],
            "BR": ["LR_Back_Lower", "LR_Back_Upper", "SR_Right_Lower", "SR_Right_Upper"],
        }
        rail_names = rail_map.get(corner, [])
        tool_vars = []
        for rn in rail_names:
            rv = self.sym.resolve_body(rn)
            if rv:
                tool_vars.append(rv)

        if not tool_vars:
            self.code.comment(f"TODO: resolve mortise tool rails for {name}")
            tool_vars = ["None"]

        return target_var, tool_vars

    def _is_cross_component_combine(self, comp_name, target_name, tool_names, name):
        """Detect if a combine is cross-component (needs assembly proxies)."""
        root_name = self.data.get("designName", "")
        # Explicit root-level
        if comp_name == root_name or comp_name == "" or not comp_name:
            return True
        # Mortise pattern: combine on Legs that cuts with rail bodies
        if "Mort" in name:
            return True
        # Check if target/tools span different components
        if target_name:
            target_comp = self.body_component.get(target_name, comp_name)
            for tn in tool_names:
                tool_comp = self.body_component.get(tn, "")
                if tool_comp and tool_comp != target_comp:
                    return True
        return False

    def _gen_proxy_combine(self, feat, comp_var, op_str, target_var,
                           tool_vars, keep_tools, name, comb_var):
        """Generate assembly proxy code for cross-component combines."""
        self.code.comment("Assembly proxies for cross-component combine")

        # Build reverse map: var_name → body_name for component lookup
        var_to_body = {v: k for k, v in self.sym.bodies.items()}

        # Generate proxy for target
        target_body_name = var_to_body.get(target_var, "")
        target_comp = self.body_component.get(target_body_name, "")
        _, target_occ = self.sym.resolve_comp(target_comp)

        if target_var != "None" and target_occ:
            proxy_target = unique_var(f"{target_var}_proxy", self.sym._used)
            self.code.emit(f"{proxy_target} = {target_var}.createForAssemblyContext({target_occ})")
        else:
            proxy_target = target_var
            if target_var == "None":
                self.code.comment(f"TODO: create proxy for target in {name}")

        # Generate proxies for tools
        proxy_tools = []
        for tv in tool_vars:
            tool_body_name = var_to_body.get(tv, "")
            tool_comp = self.body_component.get(tool_body_name, "")
            _, tool_occ = self.sym.resolve_comp(tool_comp)

            if tv != "None" and tool_occ:
                proxy_tool = unique_var(f"{tv}_proxy", self.sym._used)
                self.code.emit(f"{proxy_tool} = {tv}.createForAssemblyContext({tool_occ})")
                proxy_tools.append(proxy_tool)
            else:
                proxy_tools.append(tv)

        tool_list = "[" + ", ".join(proxy_tools) + "]"
        self.code.emit(
            f'{comb_var} = combine(root, {proxy_target}, {tool_list}, '
            f'{op_str}, {keep_tools}, "{name}")')

    # ── Move Feature ──

    def _gen_move(self, feat):
        """Generate MoveFeature API calls from captured translation/matrix."""
        name = feat["name"]
        comp_name = feat.get("component", "")
        comp_var, _ = self.sym.resolve_comp(comp_name)
        translation = feat.get("translation", [0, 0, 0])
        inputs = feat.get("inputs", [])
        matrix = feat.get("matrix")

        # Resolve input bodies
        body_vars = []
        for body_name in inputs:
            bv = self.sym.resolve_body(body_name)
            if bv:
                body_vars.append(bv)

        if not body_vars:
            self.code.blank()
            self.code.comment(f"TODO: resolve move inputs for {name}")
            return

        self.code.blank()
        self.code.emit(f'# Move: {name}')
        self.code.emit(f'move_coll = adsk.core.ObjectCollection.create()')
        for bv in body_vars:
            self.code.emit(f'move_coll.add({bv})')
        self.code.emit(f'move_inp = {comp_var}.features.moveFeatures.createInput2(move_coll)')

        if matrix:
            self.code.emit(f'move_mat = adsk.core.Matrix3D.create()')
            for r in range(4):
                for c in range(4):
                    val = matrix[r][c]
                    # Skip identity values
                    identity = 1.0 if r == c else 0.0
                    if abs(val - identity) > 1e-9:
                        self.code.emit(f'move_mat.setCell({r}, {c}, {val})')
            self.code.emit(f'move_inp.defineAsFreeMove(move_mat)')
        else:
            tx, ty, tz = translation
            self.code.emit(f'move_vec = adsk.core.Vector3D.create({tx}, {ty}, {tz})')
            self.code.emit(f'move_mat = adsk.core.Matrix3D.create()')
            self.code.emit(f'move_mat.translation = move_vec')
            self.code.emit(f'move_inp.defineAsFreeMove(move_mat)')

        mv_var = unique_var(f"mv_{snake(name)}", self.sym._used)
        self.code.emit(f'{mv_var} = {comp_var}.features.moveFeatures.add(move_inp)')
        self.code.emit(f'{mv_var}.name = "{name}"')

    # ── Gap Block ──

    def _start_gap_block(self, feat):
        """Emit conditional wrapper for gap slat features."""
        fname = feat.get("name", "")
        # FGap_ = front gap (long shoulder), LGap_ = left gap (short shoulder)
        # Detect based on feature name prefix
        if fname.startswith("LGap") or fname.startswith("RGap"):
            self.code.blank()
            self.code.emit('if ev("short_shoulder - slat_width * n_short_slats") > 0.01:')
        else:
            self.code.blank()
            self.code.emit('if ev("long_shoulder - slat_width * n_long_slats") > 0.01:')
        self.code.indent()
        self.in_gap_block = True

    # ── Body Fallbacks ──

    def _emit_body_fallbacks(self):
        """Emit ground truth box bodies for components with body data."""
        if not self.expected_bodies:
            return

        self.code.section("GROUND TRUTH BODIES")

        for comp_name, bodies in self.expected_bodies.items():
            if not bodies:
                continue

            # Build transform matrix (pass at creation time)
            transform = self.expected_transforms.get(comp_name)
            has_transform = False
            if transform:
                matrix = transform.get("matrix")
                if matrix:
                    cells = []
                    for r in range(4):
                        for c in range(4):
                            val = matrix[r][c]
                            identity = 1.0 if r == c else 0.0
                            if abs(val - identity) > 1e-9:
                                cells.append((r, c, val))
                    has_transform = bool(cells)

            # Create component with transform baked into occurrence
            comp_var, occ_var = self.sym.add_component(comp_name)
            self.code.blank()
            self.code.comment(f"{comp_name}: {len(bodies)} bodies")
            if has_transform:
                self.code.emit(f"_m = adsk.core.Matrix3D.create()")
                for r, c, val in cells:
                    self.code.emit(f"_m.setCell({r}, {c}, {val})")
                self.code.emit(f'{occ_var} = make_comp("{comp_name}", _m)')
            else:
                self.code.emit(f'{occ_var} = make_comp("{comp_name}")')
            self.code.emit(f"{comp_var} = {occ_var}.component")

            # Create box bodies from ground truth
            for body in bodies:
                bmin = body["bbMin"]
                size = body["size"]
                bname = body.get("name", "Body")
                self.code.emit(
                    f'box_body({comp_var}, {bmin[0]}, {bmin[1]}, {bmin[2]}, '
                    f'{size[0]}, {size[1]}, {size[2]}, "{bname}")')

    # ── Fit View ──

    def _emit_fit_view(self):
        if self.in_gap_block:
            self.code.dedent()
            self.in_gap_block = False
        self.code.section("FIT VIEW")
        self.code.emit("cam = app.activeViewport.camera")
        self.code.emit("cam.isFitView = True")
        self.code.emit("app.activeViewport.camera = cam")

    # ── Final Assembly ──

    def _assemble(self):
        design_name = self.data.get("designName", "Design")
        header = textwrap.dedent(f'''\
            """Generated from Fusion 360 introspection — {design_name}"""
            import adsk.core, adsk.fusion, adsk.cam, math


            def run(context):
                app = adsk.core.Application.get()
                design = adsk.fusion.Design.cast(app.activeProduct)
                design.designType = adsk.fusion.DesignTypes.ParametricDesignType
                root = design.rootComponent
                params = design.userParameters
        ''')
        return header + "\n" + self.code.get_code() + "\n"


# ── CLI Entry Point ───────────────────────────────────────────────

def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    body_data = None
    if "--bodies" in sys.argv:
        idx = sys.argv.index("--bodies")
        with open(sys.argv[idx + 1]) as f:
            body_data = json.load(f)

    gen = Generator(data, body_data=body_data)
    print(gen.generate())


if __name__ == "__main__":
    main()
