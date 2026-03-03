"""
Script Generator — template-based code generation from capture_design output.

Reads the structured JSON from capture_design and emits a standalone Fusion 360
Python script that recreates the model. The generated script is self-contained
(no af.py dependency) and uses parametric expressions from the captured dimensions.

Usage:
    from ._script_generator import generate_script
    script_text = generate_script(capture_data)

    # For search-based building:
    info = get_ambiguous_features(capture_data)
    script = generate_with_choices(capture_data, {0: 2, 3: 1})
"""

import copy
import re
from contextlib import contextmanager


def generate_script(capture):
    """Generate a standalone Fusion 360 script from capture_design JSON."""
    return _Generator(capture).generate()


def get_ambiguous_features(capture):
    """Return list of {index, name, type, variants} for ambiguous features."""
    g = _Generator(capture)
    g._scan_needs()
    result = []
    for fi, feat in enumerate(capture.get("timeline", [])):
        if feat.get("isRolledBack"):
            continue
        variants = g._feature_variants(feat)
        if len(variants) > 1:
            result.append({
                "index": fi,
                "name": feat.get("name", ""),
                "type": feat.get("type", ""),
                "variantCount": len(variants),
                "descriptions": [v[1] for v in variants],
            })
    return result


def generate_with_choices(capture, choices):
    """Generate full script with specific variant choices for ambiguous features.

    Args:
        capture: capture_design JSON data
        choices: dict mapping feature index → variant index
                 (0-based; only ambiguous features need entries)

    Returns:
        Complete Fusion 360 Python script text.
    """
    return _Generator(capture).generate_with_choices(choices)


def generate_prefix_script(capture):
    """Generate a script that sets up design type + user parameters only.

    Used as the first step in incremental building. Execute with clean=true
    to start from a blank document with all parameters defined.

    Returns:
        Standalone Fusion 360 Python script text.
    """
    return _Generator(capture).generate_prefix_script()


def generate_feature_script(capture, feature_index, choices=None):
    """Generate a standalone script for ONE feature at feature_index.

    Includes helpers + entity lookups for everything created by features 0..N-1,
    then emits the single feature's code.

    Args:
        capture: capture_design JSON data
        feature_index: index into the timeline array (0-based)
        choices: optional dict mapping feature index → variant index

    Returns:
        Standalone Fusion 360 Python script text.
    """
    return _Generator(capture).generate_feature_script(feature_index, choices)


class _Generator:
    """Walks capture_design output and emits a Fusion 360 Python script."""

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

        # Fix body names captured at end-of-timeline back to at-feature-time names
        self._fixup_split_body_names()

    def _fixup_split_body_names(self):
        """Correct extrude/sweep body names captured with post-split suffixes.

        capture_design reads body names at end-of-timeline, so an extrude body
        named "Leg_NL" at creation time shows as "Leg_NL (1)" if a downstream
        split renamed it. This fixup restores the at-creation-time name so that
        split/remove features can find bodies by their expected names.
        """
        timeline = self.cap.get("timeline", [])
        for fi, feat in enumerate(timeline):
            if feat.get("type") != "SplitBody":
                continue
            # Use inputBody (the body being split) as the base name.
            # The input body's at-creation-time name is the base without suffix.
            input_body = feat.get("inputBody", "")
            if not input_body:
                split_bodies = feat.get("bodies", [])
                input_body = split_bodies[0] if split_bodies else ""
            if not input_body:
                continue
            base_name = re.sub(r'\s*\(\d+\)\s*$', '', input_body)
            for pi in range(fi):
                prev = timeline[pi]
                if prev.get("type") in ("Extrude", "Sweep"):
                    prev_bodies = prev.get("bodies", [])
                    for bi, bn in enumerate(prev_bodies):
                        stripped = re.sub(r'\s*\(\d+\)\s*$', '', bn)
                        if stripped == base_name and bn != base_name:
                            prev_bodies[bi] = base_name

    # ── Public ──

    def generate(self):
        self._scan_needs()
        self._header()
        self._parameters()
        self._helpers()
        self._timeline()
        self._footer()
        return "\n".join(self.out)

    def generate_with_choices(self, choices):
        """Generate full script using specific variant indices for ambiguous features.

        Args:
            choices: dict mapping timeline feature index → variant index.
                     Ambiguous features not in choices use variant 0 (default).
        """
        self._scan_needs()
        self._header()
        self._parameters()
        self._helpers()
        # Custom timeline: process features one at a time with variant selection
        self._section("TIMELINE")
        for fi, feat in enumerate(self.cap.get("timeline", [])):
            if feat.get("isRolledBack"):
                continue
            t = feat.get("type", "Unknown")
            idx = feat.get("index", "?")
            name = feat.get("name", "")
            self._w()
            self._c(f"[{idx}] {t}: {name}")

            # Check if ambiguous
            variants = self._feature_variants_with_state(feat)
            if len(variants) > 1:
                vi = choices.get(fi, 0)
                vi = min(vi, len(variants) - 1)
                lines, desc, state = variants[vi]
                self._c(f"variant {vi}: {desc}")
                self.out.extend(lines)
                # Apply state from chosen variant
                self._restore_state(state)
            else:
                # Non-ambiguous or single variant: run emitter directly for
                # both output lines and state side effects
                handler = getattr(self, f"_feat_{t.lower()}", None)
                if handler:
                    handler(feat)
                else:
                    self._c(f"TODO: Unsupported feature type '{t}'")
        self._footer()
        return "\n".join(self.out)

    def generate_prefix_script(self):
        """Generate a script that sets up design type + user parameters only."""
        self.out = []
        self.out.append("import adsk.core, adsk.fusion, math")
        self.out.append("")
        self.out.append("")
        self.out.append("def run(context):")
        self.ind = 1
        self._w("app = adsk.core.Application.get()")
        self._w("design = adsk.fusion.Design.cast(app.activeProduct)")
        self._w("design.designType = adsk.fusion.DesignTypes.ParametricDesignType")
        self._w("root = design.rootComponent")
        self._w("params = design.userParameters")
        self._parameters()
        return "\n".join(self.out)

    def generate_feature_script(self, feature_index, choices=None):
        """Generate a standalone script for ONE feature at feature_index.

        Includes helpers + entity lookups for features 0..N-1, then
        emits the single feature's code.
        """
        choices = choices or {}
        timeline = self.cap.get("timeline", [])
        if feature_index < 0 or feature_index >= len(timeline):
            return f"# ERROR: feature_index {feature_index} out of range"

        feat = timeline[feature_index]
        if feat.get("isRolledBack"):
            return "# Feature is rolled back — nothing to emit"

        # Reset output state
        self.out = []
        self.ind = 1

        # Scan ALL features for helper needs (we need the full set
        # because _rebuild_entity_context may use helpers)
        self._scan_needs()

        # Boilerplate
        self.out.append("import adsk.core, adsk.fusion, math")
        self.out.append("")
        self.out.append("")
        self.out.append("def run(context):")
        self._w("app = adsk.core.Application.get()")
        self._w("design = adsk.fusion.Design.cast(app.activeProduct)")
        self._w("root = design.rootComponent")
        self._w("params = design.userParameters")

        # Helpers
        self._helpers()

        # Entity context from prior features
        self._rebuild_entity_context(feature_index, choices)

        # Emit the single feature
        t = feat.get("type", "Unknown")
        idx = feat.get("index", "?")
        name = feat.get("name", "")
        self._w()
        self._c(f"[{idx}] {t}: {name}")
        # Set component context
        comp_var = self._comp_ref(feat)
        self._w(f"comp = {comp_var}")

        variants = self._feature_variants_with_state(feat)
        if len(variants) > 1:
            vi = choices.get(feature_index, 0)
            vi = min(vi, len(variants) - 1)
            lines, desc, state = variants[vi]
            self._c(f"variant {vi}: {desc}")
            self.out.extend(lines)
            self._restore_state(state)
        else:
            handler = getattr(self, f"_feat_{t.lower()}", None)
            if handler:
                handler(feat)
            else:
                self._c(f"TODO: Unsupported feature type '{t}'")

        return "\n".join(self.out)

    def _rebuild_entity_context(self, up_to_index, choices=None):
        """Emit find_body/itemByName lookups for entities from features 0..N-1.

        This lets a per-feature script reference bodies, sketches, planes, etc.
        created by previously-executed features without re-running them.
        """
        choices = choices or {}
        timeline = self.cap.get("timeline", [])

        self._section("ENTITY CONTEXT (prior features)")

        for i in range(up_to_index):
            if i >= len(timeline):
                break
            feat = timeline[i]
            if feat.get("isRolledBack"):
                continue
            t = feat.get("type")
            name = feat.get("name", "")
            comp_name = feat.get("component", "")

            # Resolve component for this feature
            if comp_name and comp_name != self._root_name and comp_name not in self.components:
                # Component not yet created — find it by name
                cvar = self._var(comp_name)
                self._w(f"for _occ in root.allOccurrences:")
                self.ind += 1
                self._w(f'if _occ.component.name == "{comp_name}": {cvar}_c = _occ.component; break')
                self.ind -= 1
                self.components[comp_name] = f"{cvar}_c"

            if t == "ComponentCreation":
                cvar = self._var(name)
                self.components[name] = f"{cvar}_c"
                # Component exists from prior execution — find it
                self._w(f"for _occ in root.allOccurrences:")
                self.ind += 1
                self._w(f'if _occ.component.name == "{name}": {cvar}_c = _occ.component; break')
                self.ind -= 1

            elif t == "ConstructionPlane":
                var = self._var(name)
                c_ref = self.components.get(comp_name)
                if c_ref:
                    self._w(f'{var} = {c_ref}.constructionPlanes.itemByName("{name}")')
                else:
                    self._w(f'{var} = root.constructionPlanes.itemByName("{name}")')
                self.planes[name] = var

            elif t == "Sketch":
                var = self._var(name)
                # Sketches all end up in root. Names may get auto-suffixed
                # (e.g., "Sketch1" → "Sketch1 (1)") when duplicated.
                # Search by name then by suffix variants.
                # Find sketch by name — take the LAST match to handle
                # auto-suffixed duplicates (e.g., "Sketch1 (1)")
                self._w(f"{var} = None")
                self._w(f"for _si in range(root.sketches.count):")
                self.ind += 1
                self._w(f'_sk = root.sketches.item(_si)')
                self._w(f'if _sk.name == "{name}" or _sk.name.startswith("{name} ("): {var} = _sk')
                self.ind -= 1
                self.sketches[name] = var
                # Resolve profile for downstream extrude/sweep
                plane_info = feat.get("plane", {})
                prof = f"{var}_prof"
                if plane_info.get("type") == "BRepFace":
                    self._brep_face_sketches[name] = plane_info
                self._w(f"{prof} = {var}.profiles.item(0)")
                self.profiles[name] = prof

            elif t in ("Extrude", "Sweep", "Mirror", "SplitBody",
                        "RectangularPattern"):
                for bn in feat.get("bodies", []):
                    bv = self._var(bn)
                    self._w(f'{bv} = find_body("{bn}")')
                    self.bodies[bn] = bv

            elif t == "Remove":
                removed = feat.get("removedBody", "")
                if removed in self.bodies:
                    del self.bodies[removed]

            elif t == "Combine":
                if not feat.get("isKeepToolBodies"):
                    for tb in feat.get("toolBodies", []):
                        if tb in self.bodies:
                            del self.bodies[tb]

    # ── Variant support ──

    @contextmanager
    def _capture_output(self):
        """Capture lines written by feature emitters into a separate list."""
        saved = self.out
        captured = []
        self.out = captured
        yield captured
        self.out = saved

    def _feature_variants(self, feat):
        """Return list of (lines, description) for all variants of a feature.

        Non-ambiguous features return a single variant (the default).
        Used by get_ambiguous_features() for introspection.
        """
        return [(v[0], v[1]) for v in self._feature_variants_with_state(feat)]

    def _feature_variants_with_state(self, feat):
        """Return list of (lines, description, state) for all variants.

        Each variant includes the generator state snapshot after emission,
        so generate_with_choices can restore state for the chosen variant.
        """
        t = feat.get("type", "")

        if t == "Sketch":
            return self._sketch_variants(feat)
        if t == "Extrude":
            return self._extrude_variants(feat)
        if t == "Sweep":
            return self._sweep_variants(feat)

        # Non-ambiguous: single default variant
        handler = getattr(self, f"_feat_{t.lower()}", None)
        if handler:
            saved = self._save_state()
            with self._capture_output() as lines:
                handler(feat)
            state = self._save_state()
            self._restore_state(saved)
            return [(lines, "default", state)]
        return [([], f"unsupported type '{t}'", self._save_state())]

    def _sketch_variants(self, feat):
        """Generate sketch variants: project vs intersect × flip_y permutations."""
        curves = feat.get("curves", [])
        refs = [c for c in curves if c.get("isReference")]
        has_body_proj = any(
            c.get("projectedFrom", {}).get("type") == "BRepBody"
            for c in refs
        )
        plane_info = feat.get("plane", {})
        is_brep_face = (
            plane_info.get("type") == "BRepFace"
            and "sketchOrigin" in feat
            and "sketchXDir" in feat
            and "sketchYDir" in feat
        )

        if not (has_body_proj and is_brep_face):
            # Not ambiguous — single default
            saved = self._save_state()
            with self._capture_output() as lines:
                self._feat_sketch(feat)
            state = self._save_state()
            self._restore_state(saved)
            return [(lines, "default", state)]

        # Ambiguous: intersect vs project (runtime coord transform handles axis differences)
        variants = []
        for method in ["intersect", "project"]:
                    f2 = copy.deepcopy(feat)
                    for c in f2.get("curves", []):
                        if c.get("isReference"):
                            pf = c.get("projectedFrom", {})
                            if pf.get("type") == "BRepBody":
                                pf["method"] = method

                    saved_state = self._save_state()
                    with self._capture_output() as lines:
                        self._feat_sketch(f2)
                    state_after = self._save_state()
                    self._restore_state(saved_state)

                    desc = f"method={method}"
                    variants.append((lines, desc, state_after))

        return variants

    def _extrude_variants(self, feat):
        """Generate extrude variants: positive vs negative direction."""
        dist = feat.get("distance", "1 cm")
        if not (dist.startswith("-(") and dist.endswith(")")):
            # Not ambiguous
            saved = self._save_state()
            with self._capture_output() as lines:
                self._feat_extrude(feat)
            state = self._save_state()
            self._restore_state(saved)
            return [(lines, "default", state)]

        variants = []
        # Variant 0: default (unwrap negative → flip)
        saved = self._save_state()
        with self._capture_output() as lines:
            self._feat_extrude(feat)
        state0 = self._save_state()
        self._restore_state(saved)
        variants.append((lines, "negative-unwrap (default)", state0))

        # Variant 1: keep as positive (don't unwrap)
        f2 = copy.deepcopy(feat)
        inner = dist[2:-1].strip()
        f2["distance"] = inner
        f2["isDirectionFlipped"] = False
        saved = self._save_state()
        with self._capture_output() as lines:
            self._feat_extrude(f2)
        state1 = self._save_state()
        self._restore_state(saved)
        variants.append((lines, "positive (no flip)", state1))

        return variants

    def _sweep_variants(self, feat):
        """Generate sweep variants: swap distanceOne/distanceTwo."""
        d1 = feat.get("distanceOne")
        d2 = feat.get("distanceTwo")
        if not (d1 and d2):
            # Not ambiguous
            saved = self._save_state()
            with self._capture_output() as lines:
                self._feat_sweep(feat)
            state = self._save_state()
            self._restore_state(saved)
            return [(lines, "default", state)]

        variants = []
        # Variant 0: as captured
        saved = self._save_state()
        with self._capture_output() as lines:
            self._feat_sweep(feat)
        state0 = self._save_state()
        self._restore_state(saved)
        variants.append((lines, f"d1={d1}, d2={d2}", state0))

        # Variant 1: swapped
        f2 = copy.deepcopy(feat)
        f2["distanceOne"] = d2
        f2["distanceTwo"] = d1
        saved = self._save_state()
        with self._capture_output() as lines:
            self._feat_sweep(f2)
        state1 = self._save_state()
        self._restore_state(saved)
        variants.append((lines, f"d1={d2}, d2={d1} (swapped)", state1))

        return variants

    def _save_state(self):
        """Snapshot mutable generator state for save/restore."""
        return {
            "planes": dict(self.planes),
            "sketches": dict(self.sketches),
            "profiles": dict(self.profiles),
            "bodies": dict(self.bodies),
            "feats": dict(self.feats),
            "_brep_face_sketches": dict(self._brep_face_sketches),
        }

    def _restore_state(self, state):
        """Restore generator state from snapshot."""
        self.planes = dict(state["planes"])
        self.sketches = dict(state["sketches"])
        self.profiles = dict(state["profiles"])
        self.bodies = dict(state["bodies"])
        self.feats = dict(state["feats"])
        self._brep_face_sketches = dict(state["_brep_face_sketches"])

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

        # find_face_near — select face by pointOnFace proximity + normal axis
        self._w()
        self._w("def find_face_near(body, px, py, pz, nx=0, ny=0, nz=0):")
        self.ind += 1
        self._w("best, best_d = None, 1e10")
        self._w("for i in range(body.faces.count):")
        self.ind += 1
        self._w("f = body.faces.item(i)")
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
        self.ind -= 2
        self._w("return best")
        self.ind -= 1

        if "combine" in self.needs:
            self._w()
            self._w('def combine(comp, target, tools, op, keep, name="Comb"):')
            self.ind += 1
            self._w("coll = adsk.core.ObjectCollection.create()")
            self._w("for b in (tools if isinstance(tools, list) else [tools]): coll.add(b)")
            self._w("inp = root.features.combineFeatures.createInput(target, coll)")
            self._w("inp.operation = op")
            self._w("inp.isKeepToolBodies = keep")
            self._w("f = root.features.combineFeatures.add(inp)")
            self._w("f.name = name")
            self._w("return f")
            self.ind -= 1

        if "mirror_bodies" in self.needs:
            self._w()
            self._w('def mirror_bodies(comp, bodies, plane, name="Mir"):')
            self.ind += 1
            self._w("coll = adsk.core.ObjectCollection.create()")
            self._w("for b in bodies: coll.add(b)")
            self._w("inp = root.features.mirrorFeatures.createInput(coll, plane)")
            self._w("m = root.features.mirrorFeatures.add(inp)")
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
            # Set component context for child components
            comp_var = self._comp_ref(feat)
            if comp_var != "root":
                self._w(f"comp = {comp_var}")
            else:
                self._w(f"comp = root")
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
                # Body projections: use find_face for accurate intersection
                # geometry on beveled/tapered faces.
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
                # Runtime coordinate transform: the reconstructed sketch may
                # have different axes than the original (rotation/reflection).
                # Store the captured axes so _emit_raw_sketch can emit the
                # transform function and wrap all drawn-curve coordinates.
                f["_coord_transform"] = {
                    "cap_xdir": f.get("sketchXDir", [1, 0, 0]),
                    "cap_ydir": f.get("sketchYDir", [0, 1, 0]),
                }
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

        # Profile reference — match by bounding box from capture when available
        prof = None
        # Find the sketch feature that matches by name AND is the most recent
        # one before this extrude (handles multiple sketches with the same name
        # in different components)
        sketch_feat = None
        feat_idx = f.get("index", len(self.cap.get("timeline", [])))
        for ti, tf in enumerate(self.cap.get("timeline", [])):
            if ti >= feat_idx:
                break
            if tf.get("type") == "Sketch" and tf.get("name") == sketch:
                sketch_feat = tf
        cap_profiles = sketch_feat.get("profiles", []) if sketch_feat else []
        target_prof = next((p for p in cap_profiles if p.get("index") == pidx), None)

        if target_prof and sketch in self.sketches:
            sk_var = self.sketches[sketch]
            mn = target_prof["min"]
            mx = target_prof["max"]
            # Match by area (width × height) — invariant to coordinate transform
            target_w = abs(mx[0] - mn[0])
            target_h = abs(mx[1] - mn[1])
            self._c(f"Match profile by area: {target_w:.2f} x {target_h:.2f}")
            self._w(f"_best_pi, _best_d = 0, 1e10")
            self._w(f"for _pi in range({sk_var}.profiles.count):")
            self.ind += 1
            self._w(f"_bb = {sk_var}.profiles.item(_pi).boundingBox")
            self._w(f"_w = abs(_bb.maxPoint.x - _bb.minPoint.x)")
            self._w(f"_h = abs(_bb.maxPoint.y - _bb.minPoint.y)")
            self._w(f"_d = abs(_w - {round(target_w, 4)}) + abs(_h - {round(target_h, 4)})")
            self._w(f"if _d < _best_d: _best_pi, _best_d = _pi, _d")
            self.ind -= 1
            prof = f"{sk_var}.profiles.item(_best_pi)"
        elif sketch in self.profiles:
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
            # Multi-profile sweep: match profiles by bounding box dimensions
            # from the capture data. This handles profile count/ordering changes
            # from BRepFace→find_face conversion.
            pdims = f.get("profileDims", [])
            self._w("sweep_profs = adsk.core.ObjectCollection.create()")
            if pdims:
                # Match by target dimensions
                self._w("_target_dims = [")
                self.ind += 1
                for pd in pdims:
                    self._w(f"({pd[0]}, {pd[1]}),")
                self.ind -= 1
                self._w("]")
                self._w("_used = set()")
                self._w("for _tw, _th in _target_dims:")
                self.ind += 1
                self._w("_best_pi, _best_d = -1, 1e10")
                self._w(f"for _pi in range({sk_var}.profiles.count):")
                self.ind += 1
                self._w("if _pi not in _used:")
                self.ind += 1
                self._w(f"_bb = {sk_var}.profiles.item(_pi).boundingBox")
                self._w(f"_w = abs(_bb.maxPoint.x - _bb.minPoint.x)")
                self._w(f"_h = abs(_bb.maxPoint.y - _bb.minPoint.y)")
                self._w(f"_d = abs(_w - _tw) + abs(_h - _th)")
                self._w(f"if _d < _best_d: _best_pi, _best_d = _pi, _d")
                self.ind -= 2
                self._w(f"if _best_pi >= 0:")
                self.ind += 1
                self._w(f"sweep_profs.add({sk_var}.profiles.item(_best_pi))")
                self._w(f"_used.add(_best_pi)")
                self.ind -= 2
            else:
                # Fallback: N smallest non-trivial profiles
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
                # Detect path direction: check which end is closer to the
                # captured startVertex. If reversed, swap distance1/distance2.
                # createPath may reverse direction from edge vertex order.
                # Check isOpposedToEntity AND vertex proximity to determine
                # the actual path direction.
                self._w(f"_psv = sweep_edge.startVertex.geometry")
                self._w(f"_vtx_match = (abs(_psv.x - {sv[0]:.4f}) + abs(_psv.y - {sv[1]:.4f}) + abs(_psv.z - {sv[2]:.4f}) < 0.1)")
                self._w(f"_opposed = sweep_path.item(0).isOpposedToEntity")
                self._w(f"_path_fwd = not (_vtx_match != _opposed)")
                self._c("_path_fwd: True if path direction matches captured direction")
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
        # If path direction is reversed, swap distanceOne and distanceTwo
        dist1 = f.get("distanceOne")
        dist2 = f.get("distanceTwo")
        if dist1 and dist2:
            if path_ents and path_ents[0].get("source") == "BRepEdge":
                self._w(f"if _path_fwd:")
                self.ind += 1
                self._w(f'sweep_inp.distanceTwo = adsk.core.ValueInput.createByString("{dist2}")')
                self._w(f'sweep_inp.distanceOne = adsk.core.ValueInput.createByString("{dist1}")')
                self.ind -= 1
                self._w(f"else:")
                self.ind += 1
                self._w(f'sweep_inp.distanceTwo = adsk.core.ValueInput.createByString("{dist1}")')
                self._w(f'sweep_inp.distanceOne = adsk.core.ValueInput.createByString("{dist2}")')
                self.ind -= 1
            else:
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
        tool_info = f.get("splitTool", {})
        extend = f.get("isSplittingToolExtended", True)

        # Resolve input body: use explicit inputBody if captured, else infer
        input_name = f.get("inputBody")
        body_code = None
        if input_name:
            body_code = self._body_ref(input_name)
            if body_code.startswith('find_body('):
                body_code = None  # fallback to inference
        if body_code is None:
            for bn in bodies:
                base = re.sub(r'\s*\(\d+\)\s*$', '', bn)
                if base in self.bodies:
                    body_code = self.bodies[base]
                    break
        if body_code is None:
            for bn in bodies:
                if bn in self.bodies:
                    body_code = self.bodies[bn]
                    break
        if body_code is None:
            for bn in bodies:
                base = re.sub(r'\s*\(\d+\)\s*$', '', bn)
                ref = self._body_ref(base)
                if not ref.startswith('find_body('):
                    body_code = ref
                    break
        if body_code is None:
            body_code = 'find_body("?")  # TODO: split input body not resolved'

        # Resolve splitting tool
        tool_type = tool_info.get("type")
        if tool_type == "ConstructionPlane":
            pname = tool_info.get("name", "")
            builtin = {"XY": "root.xYConstructionPlane",
                       "XZ": "root.xZConstructionPlane",
                       "YZ": "root.yZConstructionPlane"}
            tool_code = self.planes.get(pname, builtin.get(pname, f'root.constructionPlanes.itemByName("{pname}")'))
        elif tool_type == "BRepFace":
            body_name = tool_info.get("body", "")
            normal = tool_info.get("normal")
            bv = self._body_ref(body_name)
            if normal:
                axis, direction = self._normal_to_axis(normal)
            else:
                axis, direction = "z", 1
            tool_code = f'find_face({bv}, "{axis}", {direction})'
        elif tool_type == "BRepBody":
            tool_code = self._body_ref(tool_info.get("name", ""))
        else:
            tool_code = "None  # TODO: unknown split tool type"

        # Determine expected split-related body count (bodies derived from inputBody)
        input_base = re.sub(r'\s*\(\d+\)\s*$', '', input_name) if input_name else ""
        expected_split_bodies = [bn for bn in bodies
                                 if re.sub(r'\s*\(\d+\)\s*$', '', bn) == input_base
                                 ] if input_base else []
        needs_supplementary = len(expected_split_bodies) > 2  # >2 pieces = multi-tool

        self._w(f"split_inp = root.features.splitBodyFeatures.createInput("
                f"{body_code}, {tool_code}, {extend})")
        self._w(f"split_feat = root.features.splitBodyFeatures.add(split_inp)")
        self._w(f'split_feat.name = "{name}"')
        self.feats[name] = "split_feat"

        # API limitation: SplitBodyFeature only accepts 1 splitting tool,
        # but the UI allows multiple. When the expected output has more
        # pieces than a single tool produces, try supplementary splits
        # with each available construction plane.
        if needs_supplementary:
            n_expected = len(expected_split_bodies)
            self._w()
            self._c(f"Multi-tool split workaround: expected {n_expected} pieces from 1 body")
            self._c(f"API only supports 1 tool per split — try additional planes")
            self._w(f"_pre_count = root.bRepBodies.count")
            self._w(f"_need = {n_expected} - (root.bRepBodies.count - _pre_count + 2)")
            self._c(f"2 = minimum pieces from first split")
            # Count actual pieces from input body
            self._w(f"_got = 0")
            self._w(f"for _bi in range(root.bRepBodies.count):")
            self.ind += 1
            self._w(f"_bn = root.bRepBodies.item(_bi).name")
            base_esc = input_base.replace('"', '\\"')
            self._w(f'import re as _re')
            self._w(f'if _re.sub(r"(\\s*\\(\\d+\\))+\\s*$", "", _bn) == "{base_esc}": _got += 1')
            self.ind -= 1
            self._w(f"if _got < {n_expected}:")
            self.ind += 1
            self._c(f"Try each construction plane as supplementary split tool")
            self._w(f"_biggest = None")
            self._w(f"for _bi in range(root.bRepBodies.count):")
            self.ind += 1
            self._w(f"_b = root.bRepBodies.item(_bi)")
            self._w(f'if _re.sub(r"(\\s*\\(\\d+\\))+\\s*$", "", _b.name) == "{base_esc}":')
            self.ind += 1
            self._w(f"if _biggest is None or _b.volume > _biggest.volume: _biggest = _b")
            self.ind -= 2  # back to if _got level
            # Expected volumes computed at RUNTIME from the ground truth.
            # We can't reliably get them from capture (removed bodies are gone
            # from final components). Instead, score each tool by comparing
            # the sorted volume list against the pre-split state. The correct
            # tool produces the smallest total volume change beyond the expected
            # number of pieces.
            # As a proxy, use the volume of the biggest piece: the correct tool
            # should produce a biggest piece closest to (total - foot_vol).
            exp_vols = []  # filled at runtime

            self._w(f"if _biggest:")
            self.ind += 1
            self._c(f"Try every candidate tool, score by volume match, pick best")
            self._w(f"_tools = []")
            self._w(f"for _pi in range(root.constructionPlanes.count):")
            self.ind += 1
            self._w(f"_tools.append(root.constructionPlanes.item(_pi))")
            self.ind -= 1
            self._w(f"for _bi3 in range(root.bRepBodies.count):")
            self.ind += 1
            self._w(f"_bod = root.bRepBodies.item(_bi3)")
            self._w(f"if _bod != _biggest:")
            self.ind += 1
            self._w(f"for _fi in range(_bod.faces.count):")
            self.ind += 1
            self._w(f"_tools.append(_bod.faces.item(_fi))")
            self.ind -= 3
            self._c(f"Record pre-supplementary volumes to detect new pieces")
            self._w(f"_pre_vols = set()")
            self._w(f"for _bi4 in range(root.bRepBodies.count):")
            self.ind += 1
            self._w(f"_pre_vols.add(round(root.bRepBodies.item(_bi4).volume, 4))")
            self.ind -= 1
            self._w(f"_best_tool = None")
            self._w(f"_best_new_vol = 1e10")
            self._w(f"for _pl in _tools:")
            self.ind += 1
            self._w(f"try:")
            self.ind += 1
            self._w(f"_si = root.features.splitBodyFeatures.createInput(_biggest, _pl, True)")
            self._w(f"_sf = root.features.splitBodyFeatures.add(_si)")
            self._c(f"Find the smallest NEW piece (not in pre-split volumes)")
            self._w(f"_new_min = 1e10")
            self._w(f"for _bi2 in range(root.bRepBodies.count):")
            self.ind += 1
            self._w(f"_bx = root.bRepBodies.item(_bi2)")
            self._w(f"_bv = round(_bx.volume, 4)")
            self._w(f"if _bv not in _pre_vols and _bv < _new_min: _new_min = _bv")
            self.ind -= 1
            self._w(f"if _new_min < _best_new_vol:")
            self.ind += 1
            self._w(f"_best_new_vol = _new_min")
            self._w(f"_best_tool = _pl")
            self.ind -= 1
            self._w(f"_sf.deleteMe()")
            self.ind -= 1  # end try
            self._w(f"except:")
            self.ind += 1
            self._w(f"pass")
            self.ind -= 1  # end except
            self.ind -= 1  # end for _pl
            self._c(f"Apply the best tool (smallest new piece = closest to trim waste)")
            self._w(f"if _best_tool is not None:")
            self.ind += 1
            self._w(f"_si = root.features.splitBodyFeatures.createInput(_biggest, _best_tool, True)")
            self._w(f"_sf = root.features.splitBodyFeatures.add(_si)")
            self._w(f'_sf.name = "{name}_sup"')
            self.ind -= 1
            self.ind -= 1  # end if _biggest
            self.ind -= 1  # end if _got

        # Track ALL output bodies by name.
        # After split, Fusion auto-names pieces (e.g., "Box (1)") which may
        # differ from the captured final names. Find by name first, then
        # match remaining by volume (descending) and rename.
        self.ind = 1  # Reset: we're inside def run()
        self._w(f"_found = set()")
        for bn in bodies:
            bv = self._var(bn)
            self.bodies[bn] = bv
            self._w(f'{bv} = find_body("{bn}")')
            self._w(f'if {bv}: _found.add("{bn}")')
        # Rename unmatched bodies
        unmatched = [bn for bn in bodies if bn not in
                     {b for b in self.bodies if b in bodies}]
        if len(bodies) > 1:
            expected_names = [repr(bn) for bn in bodies]
            self._w(f"_expected = [{', '.join(expected_names)}]")
            self._w(f"_missing = [n for n in _expected if n not in _found]")
            self._w(f"if _missing:")
            self.ind += 1
            self._w(f"_unmatched = []")
            self._w(f"for _bi in range(root.bRepBodies.count):")
            self.ind += 1
            self._w(f"_b = root.bRepBodies.item(_bi)")
            self._w(f"if _b.name not in _found: _unmatched.append(_b)")
            self.ind -= 1
            self._w(f"_unmatched.sort(key=lambda b: -b.volume)")
            self._w(f"_missing.sort(key=lambda n: -max((b.volume for b in _unmatched), default=0) if not any(b.name == n for b in _unmatched) else 0)")
            self._w(f"for _nm in _missing:")
            self.ind += 1
            self._w(f"if _unmatched:")
            self.ind += 1
            self._w(f"_ub = _unmatched.pop(0)")
            self._w(f'_ub.name = _nm')
            self.ind -= 2  # end if _unmatched + for _nm
            # Re-resolve after rename (still inside if _missing)
            for bn in bodies:
                bv = self._var(bn)
                self._w(f'if not {bv}: {bv} = find_body("{bn}")')
            self.ind -= 1  # end if _missing

    def _feat_remove(self, f):
        removed = f.get("removedBody", "")
        if not removed:
            self._c("TODO: Remove — no body name captured")
            return
        body_code = self._body_ref(removed)
        # Guard: body may not exist if upstream split produced fewer pieces
        self._w(f"_rm = {body_code}")
        self._w(f"if _rm: root.features.removeFeatures.add(_rm)")
        if removed in self.bodies:
            del self.bodies[removed]

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
        any_items = False
        for si, es in enumerate(edge_sets):
            radius = es.get("radius", "0.1 cm")
            edges = es.get("edges", [])
            if not edges:
                self._c(f"TODO: edge set {si} has no captured data")
                continue

            # Check if items are BRepFace or BRepEdge
            has_faces = any(e.get("type") == "BRepFace" for e in edges)
            has_edges = any(e.get("type") == "BRepEdge" or "start" in e for e in edges)

            if has_faces:
                any_items = True
                self._emit_face_finder(f"fillet_items_{si}", edges, f.get("bodies", []))
                self._w(f"if fillet_items_{si}.count > 0:")
                self.ind += 1
                self._w(f"fillet_inp.addConstantRadiusEdgeSet(fillet_items_{si}, "
                        f'adsk.core.ValueInput.createByString("{radius}"), True)')
                self.ind -= 1
            elif has_edges:
                any_items = True
                self._emit_edge_finder(f"fillet_edges_{si}", edges, f.get("bodies", []))
                self._w(f"if fillet_edges_{si}.count > 0:")
                self.ind += 1
                self._w(f"fillet_inp.addConstantRadiusEdgeSet(fillet_edges_{si}, "
                        f'adsk.core.ValueInput.createByString("{radius}"), True)')
                self.ind -= 1
        if any_items:
            self._w(f'fillet_feat = root.features.filletFeatures.add(fillet_inp)')
            self._w(f'fillet_feat.name = "{name}"')
        else:
            self._c(f"TODO: Fillet '{name}' skipped — no edges/faces captured")

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

    def _emit_face_finder(self, var, faces, body_names):
        """Emit code that finds BRepFaces and adds their EDGES for fillet.

        Fillet API requires BRepEdge objects, not BRepFaces. When the user
        selected faces in the UI, we find the matching faces and add all
        their edges to the collection.
        """
        self._w(f"{var} = adsk.core.ObjectCollection.create()")
        if not faces:
            return
        self._w("_face_targets = [")
        self.ind += 1
        for f in faces:
            if f.get("type") != "BRepFace":
                continue
            pof = f.get("pointOnFace", [0, 0, 0])
            body = f.get("body", "")
            self._w(f'("{body}", {pof[0]}, {pof[1]}, {pof[2]}),')
        self.ind -= 1
        self._w("]")
        saved_ind = self.ind
        self._w("_added = set()")
        self._w("for _fb, _fx, _fy, _fz in _face_targets:")
        self.ind += 1
        self._c(f"Search ALL bodies (names may be swapped from mirror)")
        self._w(f"_best_face, _best_d = None, 1e10")
        self._w(f"for _bsi in range(root.bRepBodies.count):")
        self.ind += 1
        self._w(f"_body = root.bRepBodies.item(_bsi)")
        self._w(f"for _fi in range(_body.faces.count):")
        self.ind += 1
        self._w(f"_f = _body.faces.item(_fi)")
        self._w(f"_p = _f.pointOnFace")
        self._w(f"_d = abs(_p.x-_fx)+abs(_p.y-_fy)+abs(_p.z-_fz)")
        self._w(f"if _d < _best_d: _best_face, _best_d = _f, _d")
        self.ind -= 2  # back to for _fb level
        self._w(f"if _best_face and _best_d < 0.5:")
        self.ind += 1
        self._c(f"Add all edges of the matched face (fillet API needs edges)")
        self._w(f"for _ei in range(_best_face.edges.count):")
        self.ind += 1
        self._w(f"_edge = _best_face.edges.item(_ei)")
        self._w(f"_eid = _edge.tempId")
        self._w(f"if _eid not in _added:")
        self.ind += 1
        self._w(f"{var}.add(_edge)")
        self._w(f"_added.add(_eid)")
        self.ind -= 3  # back to for _fb level
        self.ind -= 1  # back to base
        self.ind = saved_ind

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
        self.components[name] = f"{var}_c"

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

    def _emit_sketch_coord_transform(self, var, cap_xdir, cap_ydir, plane_info):
        """Emit runtime code to compute the transform from captured sketch space
        to the actual reconstructed sketch space.

        The captured sketch has axes (cap_xdir, cap_ydir). The reconstructed
        sketch on the same face may have different axes. We compute the 2x2
        transform matrix at runtime by reading the actual sketch's xDirection
        and yDirection, then computing how to map (cap_sx, cap_sy) → (act_sx, act_sy).

        Both coordinate systems share the same origin (the face reference point)
        and the same plane — only the in-plane axes may differ (rotation/reflection).
        The transform is: actual_model = cap_sx * cap_xdir + cap_sy * cap_ydir
                          act_sx = dot(actual_model, act_xdir)
                          act_sy = dot(actual_model, act_ydir)
        Which gives a 2x2 matrix: [[dot(cap_x,act_x), dot(cap_y,act_x)],
                                    [dot(cap_x,act_y), dot(cap_y,act_y)]]
        """
        # Emit the captured axes as constants
        self._w(f"# Coordinate transform: captured sketch axes -> actual sketch axes")
        self._w(f"_cap_xd = ({cap_xdir[0]}, {cap_xdir[1]}, {cap_xdir[2]})")
        self._w(f"_cap_yd = ({cap_ydir[0]}, {cap_ydir[1]}, {cap_ydir[2]})")
        self._w(f"_act_xd = {var}.xDirection")
        self._w(f"_act_yd = {var}.yDirection")
        # 2x2 transform matrix: M = [[a,b],[c,d]]
        # where a = dot(cap_xdir, act_xdir), b = dot(cap_ydir, act_xdir), etc.
        self._w(f"_m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z")
        self._w(f"_m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z")
        self._w(f"_m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z")
        self._w(f"_m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z")
        self._w(f"def _xf(sx, sy):")
        self.ind += 1
        self._w(f"return (sx * _m00 + sy * _m01, sx * _m10 + sy * _m11)")
        self.ind -= 1

    def _emit_raw_sketch(self, var, name, plane_code, curves, dims, feat, on_face=False):
        """Emit raw sketch geometry with parametric dimensions and constraints."""
        self._w(f"{var} = root.sketches.add({plane_code})")
        self._w(f'{var}.name = "{name}"')
        self._w(f"lns = {var}.sketchCurves.sketchLines")

        # Emit coordinate transform if the sketch was on a BRepFace with
        # body projections (axes may differ from captured sketch)
        _has_coord_xf = False
        coord_xf = feat.get("_coord_transform")
        if coord_xf:
            _has_coord_xf = True
            self._emit_sketch_coord_transform(var, coord_xf["cap_xdir"], coord_xf["cap_ydir"], feat.get("plane", {}))
        else:
            # Identity transform — _xf passthrough for dimension references
            self._w(f"def _xf(sx, sy): return (sx, sy)")

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
        _on_edge_pts = set()    # (curve_idx, "end") pairs placed exactly on projected edge

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

        # Pass 3: emit sk.project(body) or sk.intersectWithSketchPlane([body])
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
                        method = pf.get("method", "project")
                        if method == "intersect":
                            self._c(f"Intersect body '{bname}' with sketch plane")
                            self._w(f"{pvar} = {var}.intersectWithSketchPlane([{bv}])")
                        else:
                            self._c(f"Project body '{bname}'")
                            self._w(f"{pvar} = {var}.project({bv})")

        if _has_body_projs:
            # Build runtime lookup of all projected sketch points AND curves
            self._w(f"_proj_pts = []  # [(x, y, sketchPoint), ...]")
            self._w(f"_proj_curves = []  # [(sx, sy, ex, ey, curve), ...]")
            self._w(f"for _ci in range({var}.sketchCurves.count):")
            self.ind += 1
            self._w(f"_c = {var}.sketchCurves.item(_ci)")
            self._w(f"if _c.isReference:")
            self.ind += 1
            self._w(f"for _sp in [_c.startSketchPoint, _c.endSketchPoint]:")
            self.ind += 1
            self._w(f"_g = _sp.geometry")
            self._w(f"_proj_pts.append((_g.x, _g.y, _sp))")
            self.ind -= 1
            self._w(f"_s, _e = _c.startSketchPoint.geometry, _c.endSketchPoint.geometry")
            self._w(f"_proj_curves.append((_s.x, _s.y, _e.x, _e.y, _c))")
            self.ind -= 2
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
            self._w()
            self._w(f"def _nearest_proj_curve(sx, sy, ex, ey):")
            self.ind += 1
            self._w(f"best, best_d = None, 1e10")
            self._w(f"for _sx, _sy, _ex, _ey, _c in _proj_curves:")
            self.ind += 1
            self._w(f"_d = min(abs(_sx-sx)+abs(_sy-sy)+abs(_ex-ex)+abs(_ey-ey),")
            self._w(f"        abs(_sx-ex)+abs(_sy-ey)+abs(_ex-sx)+abs(_ey-sy))")
            self._w(f"if _d < best_d: best, best_d = _c, _d")
            self.ind -= 1
            self._w(f"return best")
            self.ind -= 1

            # Register projected BRepBody curves in curve_vars for
            # constraint/dimension references (match by endpoint proximity)
            for i, c in enumerate(curves):
                if (c.get("isReference")
                        and c.get("projectedFrom", {}).get("type") == "BRepBody"):
                    _oi = c.get("_origIdx", i)
                    sx, sy = c["start"]
                    ex, ey = c["end"]
                    cv = f"_pcurve_{_oi}"
                    if _has_coord_xf:
                        # Transform captured coords to actual sketch space for matching
                        self._w(f"{cv} = _nearest_proj_curve(*_xf({sx}, {sy}), *_xf({ex}, {ey}))")
                    else:
                        self._w(f"{cv} = _nearest_proj_curve({sx}, {sy}, {ex}, {ey})")
                    curve_vars[_oi] = cv
                    # Don't register endpoints in pt_map — curve direction may
                    # be reversed vs capture. Use _nearest_proj instead for
                    # drawn lines that start at projected corners.

        for i, c in enumerate(curves):
            ctype = c.get("type", "")
            # Projected/reference curves: emit sk.project(edge/body) to recreate
            if c.get("isReference"):
                pf = c.get("projectedFrom", {})
                if pf.get("type") == "BRepBody":
                    # Body projection emitted above. Skip individual curve.
                    continue
                elif pf.get("type") == "BRepFace":
                    # Auto-boundary — skip (handled by find_face)
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
                # When coordinate transform is active, transform captured
                # coords to actual sketch space for _nearest_proj queries
                # and for computing deltas.
                if _has_coord_xf and not c.get("isReference"):
                    self._w(f"_cs_{i} = _xf({sx}, {sy})")
                    self._w(f"_ce_{i} = _xf({ex}, {ey})")
                    tsx, tsy = f"_cs_{i}[0]", f"_cs_{i}[1]"
                    tex, tey = f"_ce_{i}[0]", f"_ce_{i}[1]"
                else:
                    tsx, tsy = str(sx), str(sy)
                    tex, tey = str(ex), str(ey)
                s_ref, s_key = _pt_ref(sx, sy)
                e_ref, e_key = _pt_ref(ex, ey)
                if _has_body_projs:
                    oi = c.get("_origIdx", i)
                    s_is_proj = not s_ref and (oi, "start") in _proj_connected
                    e_is_proj = not e_ref and (oi, "end") in _proj_connected

                    if s_is_proj:
                        self._w(f"_pp_{i}s = _nearest_proj({tsx}, {tsy})")
                        self._w(f"_pg_{i}s = _pp_{i}s.geometry")
                        s_code = f"P(_pg_{i}s.x, _pg_{i}s.y, 0)"
                    elif s_ref:
                        s_code = s_ref
                    elif _has_coord_xf:
                        s_code = f"P({tsx}, {tsy}, 0)"
                    else:
                        s_code = f"P({sx}, {sy}, 0)"

                    if e_is_proj:
                        self._w(f"_pp_{i}e = _nearest_proj({tex}, {tey})")
                        self._w(f"_pg_{i}e = _pp_{i}e.geometry")
                        e_code = f"P(_pg_{i}e.x, _pg_{i}e.y, 0)"
                    elif e_ref:
                        e_code = e_ref
                    elif s_is_proj:
                        # Non-projected end: place ON the projected edge.
                        # Find which projected curve this endpoint should lie on
                        # (from coincident constraints in the capture), and compute
                        # the endpoint along the actual curve direction.
                        on_curve = self._find_online_constraint(feat, c.get("_origIdx", i), "end")
                        if on_curve is not None and on_curve in curve_vars:
                            cv_on = curve_vars[on_curve]
                            # Compute endpoint along the projected curve from start
                            # at approximate distance (will be set exactly by dimension)
                            cap_dist = ((ex - sx)**2 + (ey - sy)**2)**0.5
                            self._w(f"_es_{i} = {cv_on}.startSketchPoint.geometry")
                            self._w(f"_ee_{i} = {cv_on}.endSketchPoint.geometry")
                            self._w(f"_el_{i} = ((_ee_{i}.x-_es_{i}.x)**2+(_ee_{i}.y-_es_{i}.y)**2)**0.5")
                            self._w(f"_ed_{i} = {round(cap_dist, 6)} / _el_{i} if _el_{i} > 0.001 else 0")
                            # Pick direction: toward start or end of the curve?
                            # Compare distance from the projected start point to both curve endpoints
                            self._w(f"_ds_{i} = abs(_pg_{i}s.x-_es_{i}.x)+abs(_pg_{i}s.y-_es_{i}.y)")
                            self._w(f"_de_{i} = abs(_pg_{i}s.x-_ee_{i}.x)+abs(_pg_{i}s.y-_ee_{i}.y)")
                            self._w(f"if _ds_{i} < _de_{i}:")
                            self.ind += 1
                            self._w(f"_ex_{i} = _es_{i}.x + (_ee_{i}.x-_es_{i}.x)*_ed_{i}")
                            self._w(f"_ey_{i} = _es_{i}.y + (_ee_{i}.y-_es_{i}.y)*_ed_{i}")
                            self.ind -= 1
                            self._w(f"else:")
                            self.ind += 1
                            self._w(f"_ex_{i} = _ee_{i}.x + (_es_{i}.x-_ee_{i}.x)*_ed_{i}")
                            self._w(f"_ey_{i} = _ee_{i}.y + (_es_{i}.y-_ee_{i}.y)*_ed_{i}")
                            self.ind -= 1
                            e_code = f"P(_ex_{i}, _ey_{i}, 0)"
                            _on_edge_pts.add((c.get("_origIdx", i), "end"))
                        else:
                            # Fallback: use transformed delta
                            self._w(f"_dx_{i} = {tex} - {tsx}")
                            self._w(f"_dy_{i} = {tey} - {tsy}")
                            e_code = f"P(_pg_{i}s.x + _dx_{i}, _pg_{i}s.y + _dy_{i}, 0)"
                    elif _has_coord_xf:
                        e_code = f"P({tex}, {tey}, 0)"
                    else:
                        e_code = f"P({ex}, {ey}, 0)"

                    # Same for non-projected start with projected end
                    if not s_is_proj and not s_ref and e_is_proj:
                        if _has_coord_xf:
                            self._w(f"_dx_{i} = {tsx} - {tex}")
                            self._w(f"_dy_{i} = {tsy} - {tey}")
                            s_code = f"P(_pg_{i}e.x + _dx_{i}, _pg_{i}e.y + _dy_{i}, 0)"
                        else:
                            dx = round(sx - ex, 6)
                            dy = round(sy - ey, 6)
                            s_code = f"P(_pg_{i}e.x + {dx}, _pg_{i}e.y + {dy}, 0)"
                else:
                    if _has_coord_xf:
                        s_code = s_ref if s_ref else f"P({tsx}, {tsy}, 0)"
                        e_code = e_ref if e_ref else f"P({tex}, {tey}, 0)"
                    else:
                        s_code = s_ref if s_ref else f"P({sx}, {sy}, 0)"
                        e_code = e_ref if e_ref else f"P({ex}, {ey}, 0)"
                self._w(f"ln{i} = lns.addByTwoPoints({s_code}, {e_code})")
                # Add coincident constraints to merge drawn endpoints
                # with projected sketch points (shares the point, zero-gap)
                if _has_body_projs:
                    oi2 = c.get("_origIdx", i)
                    if (oi2, "start") in _proj_connected:
                        self._w(f"{var}.geometricConstraints.addCoincident(ln{i}.startSketchPoint, _pp_{i}s)")
                    if (oi2, "end") in _proj_connected:
                        self._w(f"{var}.geometricConstraints.addCoincident(ln{i}.endSketchPoint, _pp_{i}e)")
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

        # Emit dimensions FIRST, then geometric constraints.
        # Dimension + on-line coincident together determine point position.
        # Dimension first: sets distance along axis. Coincident second:
        # snaps to the projected edge (compatible, not over-constraining).
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
                    orient_map = {
                        "Horizontal": "H",
                        "Vertical": "V",
                        "Aligned": "adsk.fusion.DimensionOrientations.AlignedDimensionOrientation",
                    }
                    orient_code = orient_map.get(orient, "H")

                    e1_code = self._resolve_sketch_entity_ref(e1, curve_vars, var, _proj_curve_pts)
                    e2_code = self._resolve_sketch_entity_ref(e2, curve_vars, var, _proj_curve_pts)
                    if (_has_body_projs and e1_code and e2_code
                            and "_nearest_proj" in str(e1_code)
                            and "_nearest_proj" in str(e2_code)):
                        self._c(f"dim[{di}]: {expr} (both endpoints from intersection)")
                        continue
                    # Keep dims for on-edge endpoints — makes them parametric.
                    # (on-line coincident constraints are skipped separately)
                    if e1_code and e2_code:
                        self._w(f"try:")
                        self.ind += 1
                        self._w(f"d.addDistanceDimension({e1_code}, {e2_code},")
                        self.ind += 1
                        self._w(f'{orient_code}, P(0, 0, 0)).parameter.expression = "{expr}"')
                        self.ind -= 2
                        self._w(f"except: pass  # skip if already constrained")
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

        constraints = feat.get("constraints", [])
        if constraints and any(isinstance(c, dict) for c in constraints):
            self._w(f"gc = {var}.geometricConstraints")
            for ci, c in enumerate(constraints):
                if isinstance(c, str):
                    # Legacy format (just type name, no targets)
                    continue
                ctype = c.get("type", "")

                # Wrap each constraint in try/except — constraints can fail
                # if geometry is already constrained (e.g., shared points,
                # collinear lines, or implicit constraints from line creation)
                call = None
                if ctype == "HorizontalConstraint":
                    line_ref = c.get("line")
                    line_code = self._resolve_sketch_curve_ref(line_ref, curve_vars)
                    if line_code:
                        call = f"gc.addHorizontal({line_code})"

                elif ctype == "VerticalConstraint":
                    line_ref = c.get("line")
                    line_code = self._resolve_sketch_curve_ref(line_ref, curve_vars)
                    if line_code:
                        call = f"gc.addVertical({line_code})"

                elif ctype == "CoincidentConstraint":
                    pt_ref = c.get("point")
                    ent_ref = c.get("entity")
                    pt_ci = pt_ref.get("curveIndex") if pt_ref else None
                    pt_role = pt_ref.get("role", "") if pt_ref else ""
                    if pt_ci is not None and (pt_ci, pt_role) in _on_edge_pts:
                        continue
                    pt_code = self._resolve_sketch_entity_ref(pt_ref, curve_vars, var)
                    ent_code = self._resolve_sketch_entity_ref(ent_ref, curve_vars, var)
                    if pt_code and ent_code and pt_code != ent_code:
                        call = f"gc.addCoincident({pt_code}, {ent_code})"

                elif ctype == "ParallelConstraint":
                    l1 = self._resolve_sketch_curve_ref(c.get("lineOne"), curve_vars)
                    l2 = self._resolve_sketch_curve_ref(c.get("lineTwo"), curve_vars)
                    if l1 and l2:
                        call = f"gc.addParallel({l1}, {l2})"

                elif ctype == "PerpendicularConstraint":
                    l1 = self._resolve_sketch_curve_ref(c.get("lineOne"), curve_vars)
                    l2 = self._resolve_sketch_curve_ref(c.get("lineTwo"), curve_vars)
                    if l1 and l2:
                        call = f"gc.addPerpendicular({l1}, {l2})"

                elif ctype == "TangentConstraint":
                    c1 = self._resolve_sketch_curve_ref(c.get("curveOne"), curve_vars)
                    c2 = self._resolve_sketch_curve_ref(c.get("curveTwo"), curve_vars)
                    if c1 and c2:
                        call = f"gc.addTangent({c1}, {c2})"

                elif ctype == "EqualConstraint":
                    c1 = self._resolve_sketch_curve_ref(c.get("curveOne"), curve_vars)
                    c2 = self._resolve_sketch_curve_ref(c.get("curveTwo"), curve_vars)
                    if c1 and c2:
                        call = f"gc.addEqual({c1}, {c2})"

                if call:
                    self._w(f"try: {call}")
                    self._w(f"except: pass")

        # Profile — use item(0) by default; the extrude/sweep emitter
        # uses the captured profileIndex to select the correct profile.
        prof = f"{var}_prof"
        prof_count = feat.get("profileCount", 1)
        self._w(f"{prof} = {var}.profiles.item(0)  # {prof_count} profile(s)")
        self.profiles[name] = prof

    def _find_online_constraint(self, feat, curve_idx, role):
        """Find if a curve endpoint has a coincident-on-line constraint.

        Searches the captured constraints for a CoincidentConstraint where
        point=(curveIndex=curve_idx, role=role) and entity is a SketchLine.
        Returns the curveIndex of the line, or None.
        """
        for c in feat.get("constraints", []):
            if not isinstance(c, dict):
                continue
            if c.get("type") != "CoincidentConstraint":
                continue
            pt = c.get("point", {})
            ent = c.get("entity", {})
            if (pt.get("curveIndex") == curve_idx and pt.get("role") == role
                    and ent.get("type") == "SketchLine"):
                return ent.get("curveIndex")
        return None

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
            # For projected body curves, use _nearest_proj (curve direction
            # may be reversed, so startSketchPoint/endSketchPoint are unreliable).
            # Use _xf to transform captured coords if coord transform is active.
            if ci is not None and proj_curve_pts and (ci, role) in proj_curve_pts:
                x, y = proj_curve_pts[(ci, role)]
                return f"_nearest_proj(*_xf({x}, {y}))"
            if ci is not None and ci in curve_vars:
                cv = curve_vars[ci]
                if role == "start":
                    return f"{cv}.startSketchPoint"
                elif role == "end":
                    return f"{cv}.endSketchPoint"
                elif role == "center":
                    return f"{cv}.centerSketchPoint"
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
            pof = plane_info.get("pointOnFace")
            bv = self._body_ref(body_name)
            if pof:
                # Use pointOnFace + normal for precise face selection.
                n = normal or [0, 0, 0]
                return (f'find_face_near({bv}, {round(pof[0], 4)}, '
                        f'{round(pof[1], 4)}, {round(pof[2], 4)}, '
                        f'{round(n[0], 4)}, {round(n[1], 4)}, {round(n[2], 4)})')
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

    def _comp_ref(self, feat):
        """Get the component variable for a feature. Returns 'root' for root component."""
        comp_name = feat.get("component", "")
        if not comp_name or comp_name == self._root_name:
            return "root"
        if comp_name in self.components:
            return self.components[comp_name]
        return "root"

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
