"""Core mixin: generation entry points, fixups, timeline dispatch, entity context."""

import re


class _CoreMixin:
    """Orchestration: generate*, fixups, timeline dispatch, entity context rebuild."""

    def _fixup_split_body_names(self):
        """Correct extrude/sweep body names captured with post-split suffixes.

        capture_design reads body names at end-of-timeline, so an extrude body
        named "Leg_NL" at creation time shows as "Leg_NL (1)" if a downstream
        split renamed it. This fixup restores the at-creation-time name so that
        split/remove features can find bodies by their expected names.

        Also handles user renames: if the split's inputBody doesn't match any
        previous extrude body by name, find the nearest preceding NewBody
        extrude in the same component and rename its body to match.
        """
        timeline = self.cap.get("timeline", [])
        for fi, feat in enumerate(timeline):
            if feat.get("type") != "SplitBody":
                continue
            input_body = feat.get("inputBody", "")
            if not input_body:
                split_bodies = feat.get("bodies", [])
                input_body = split_bodies[0] if split_bodies else ""
            if not input_body:
                continue
            base_name = re.sub(r'\s*\(\d+\)\s*$', '', input_body)
            split_comp = feat.get("component", "")
            found_match = False
            for pi in range(fi):
                prev = timeline[pi]
                if prev.get("type") in ("Extrude", "Sweep"):
                    prev_bodies = prev.get("bodies", [])
                    for bi, bn in enumerate(prev_bodies):
                        stripped = re.sub(r'\s*\(\d+\)\s*$', '', bn)
                        if stripped == base_name:
                            found_match = True
                            if bn != base_name:
                                prev_bodies[bi] = base_name
            # Handle user renames: if no extrude/sweep body matches the
            # split's inputBody, look for the nearest preceding NewBody
            # extrude in the same component whose body isn't referenced by
            # any other split, and rename it.
            if not found_match:
                # Collect all inputBody names from other splits
                other_inputs = set()
                for oi, of in enumerate(timeline):
                    if of.get("type") == "SplitBody" and oi != fi:
                        ib = of.get("inputBody", "")
                        if ib:
                            other_inputs.add(ib)
                # Search backwards for nearest NewBody extrude in same comp
                for pi in range(fi - 1, -1, -1):
                    prev = timeline[pi]
                    if (prev.get("type") in ("Extrude", "Sweep")
                            and prev.get("operation") == "NewBody"
                            and prev.get("component", "") == split_comp):
                        prev_bodies = prev.get("bodies", [])
                        if len(prev_bodies) == 1 and prev_bodies[0] not in other_inputs:
                            prev_bodies[0] = base_name
                            break

    def _fixup_body_references(self):
        """Fix body names that reference bodies created after their usage.

        When capture reads body names at end-of-timeline, names may differ from
        at-feature-time names. Two patterns:

        1. A body named at end-of-timeline by a later Pattern (e.g., "Body7" is
           actually "wedge1" at the Combine's position).
        2. A body that becomes a separate body only after a later SplitBody
           (e.g., "notch1" is part of "post1" until Split2 separates it).
        """
        timeline = self.cap.get("timeline", [])
        for fi, feat in enumerate(timeline):
            ftype = feat.get("type")

            # Combine: fix target and tool bodies
            if ftype == "Combine":
                target = feat.get("targetBody", "")
                if target:
                    resolved = self._resolve_body_at(timeline, target, fi)
                    if resolved != target:
                        feat["targetBody"] = resolved
                tool_bodies = feat.get("toolBodies", [])
                for ti, tb_name in enumerate(tool_bodies):
                    resolved = self._resolve_body_at(timeline, tb_name, fi)
                    if resolved != tb_name:
                        tool_bodies[ti] = resolved

            # Move: fix input bodies
            if ftype == "Move":
                inputs = feat.get("inputs", [])
                for ii, inp_name in enumerate(inputs):
                    resolved = self._resolve_body_at(timeline, inp_name, fi)
                    if resolved != inp_name:
                        inputs[ii] = resolved

            # Mirror: fix input bodies (skip feature names for Adjust mirrors)
            if ftype == "Mirror":
                is_adjust = feat.get("computeOption") == "Adjust"
                inputs = feat.get("inputBodies", [])
                # Collect feature names for Adjust mirror detection
                feat_names = set()
                if is_adjust:
                    for pi in range(fi):
                        pf = timeline[pi]
                        if pf.get("type") in ("Extrude", "Sweep", "SplitBody",
                                                "RectangularPattern"):
                            feat_names.add(pf.get("name", ""))
                for ii, inp_name in enumerate(inputs):
                    if is_adjust and inp_name in feat_names:
                        continue  # Feature name, not body name
                    resolved = self._resolve_body_at(timeline, inp_name, fi)
                    if resolved != inp_name:
                        inputs[ii] = resolved

            # Sketch: fix projected body references in curves
            if ftype == "Sketch":
                for curve in feat.get("curves", []):
                    proj = curve.get("projectedFrom", {})
                    if proj.get("type") == "BRepBody" and proj.get("body"):
                        resolved = self._resolve_body_at(timeline, proj["body"], fi)
                        if resolved != proj["body"]:
                            proj["body"] = resolved

            # Sketch: fix BRepFace plane body references
            if ftype == "Sketch":
                plane = feat.get("plane", {})
                if plane.get("type") == "BRepFace" and plane.get("body"):
                    resolved = self._resolve_body_at(timeline, plane["body"], fi)
                    if resolved != plane["body"]:
                        plane["body"] = resolved

    def _resolve_body_at(self, timeline, body_name, before_index):
        """Resolve a body name to its at-feature-time name.

        Returns body_name unchanged if it already exists before before_index.
        Otherwise, traces ancestry (split inputBody, or duplicate-name surplus).
        """
        # Check if body was created or referenced before this feature.
        # Check output lists (bodies, outputBodies) AND reference fields
        # (target, tools, mirror inputs, split inputs) — a referenced body
        # definitely existed.
        for t in timeline[:before_index]:
            if body_name in t.get("bodies", []):
                return body_name
            if body_name in t.get("patternCopies", []):
                return body_name
            if body_name in t.get("outputBodies", []):
                return body_name
            if body_name == t.get("targetBody"):
                return body_name
            if body_name in t.get("toolBodies", []):
                return body_name
            if body_name in t.get("inputBodies", []):
                return body_name
            if body_name == t.get("inputBody"):
                return body_name

        # Strategy 1: trace to ancestor via SplitBody
        # If a later SplitBody creates this body, the body was part of
        # the split's inputBody at this point in the timeline.
        # NOTE: SplitBody `bodies` lists ALL component bodies at that
        # position, not just split outputs.  Only match if the body was
        # NOT referenced by any feature before the split (otherwise it
        # pre-existed the split and is not a descendant).
        for si in range(before_index, len(timeline)):
            sf = timeline[si]
            if sf.get("type") != "SplitBody":
                continue
            if body_name not in sf.get("bodies", []):
                continue
            # Verify the body wasn't referenced before the split
            referenced_before_split = False
            for ti in range(si):
                t = timeline[ti]
                if (body_name in t.get("bodies", [])
                        or body_name in t.get("outputBodies", [])
                        or body_name == t.get("targetBody")
                        or body_name in t.get("toolBodies", [])
                        or body_name in t.get("inputBodies", [])
                        or body_name == t.get("inputBody")):
                    referenced_before_split = True
                    break
            if referenced_before_split:
                continue  # Pre-existing body, not a split output
            ancestor = sf.get("inputBody", "")
            if ancestor:
                # Recursively resolve (ancestor might also be a future name)
                return self._resolve_body_at(timeline, ancestor, before_index)

        # Strategy 2: find bodies created multiple times by NewBody extrudes
        # (e.g., two extrudes both named "wedge1"). Only count NewBody extrude
        # creations, not SplitBody outputs (splits create same-name pieces that
        # aren't true duplicates).
        extrude_count = {}
        for pi in range(before_index):
            prev = timeline[pi]
            if (prev.get("type") in ("Extrude", "Sweep")
                    and prev.get("operation") == "NewBody"):
                for bn in prev.get("bodies", []):
                    extrude_count[bn] = extrude_count.get(bn, 0) + 1

        # Subtract consumptions (Combine keep=False, Remove)
        for pi in range(before_index):
            prev = timeline[pi]
            if prev.get("type") == "Combine" and not prev.get("isKeepToolBodies", True):
                for tb in prev.get("toolBodies", []):
                    if tb in extrude_count:
                        extrude_count[tb] -= 1
                        if extrude_count[tb] <= 0:
                            del extrude_count[tb]
            if prev.get("type") == "Remove":
                rn = prev.get("removedBody", "")
                if rn in extrude_count:
                    extrude_count[rn] -= 1
                    if extrude_count[rn] <= 0:
                        del extrude_count[rn]

        # Find bodies created > 1 time (true duplicates)
        best = None
        for bn, count in extrude_count.items():
            if count > 1:
                if best is None:
                    best = bn

        if best:
            return best

        # Strategy 3: body_name matches a feature name (capture stored feature
        # name instead of body name). Find the feature with this name in the
        # same component and use its output body.
        ref_comp = timeline[before_index].get("component", "root") if before_index < len(timeline) else "root"
        for pi in range(before_index):
            prev = timeline[pi]
            if (prev.get("name") == body_name
                    and prev.get("component", "root") == ref_comp
                    and prev.get("bodies")):
                # Use the first output body of this feature
                return prev["bodies"][0]

        return body_name

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
            # Set component context
            self._current_comp = feat.get("component", "")
            comp_var = self._comp_ref(feat)
            if comp_var != "root":
                self._w(f"comp = {comp_var}")
            else:
                self._w(f"comp = root")

            # Wrap each feature in try/except so individual failures
            # don't crash the full script (allows partial rebuild).
            self._w("try:")
            self.ind += 1
            self._w("pass")  # ensure non-empty try block for comment-only features

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

            self.ind -= 1
            self._w("except Exception:")
            self.ind += 1
            self._w("pass")
            self.ind -= 1
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
        self._current_comp = feat.get("component", "")
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
                # Component not yet created — find or create it by name
                cvar = self._var(comp_name)
                self._w(f"{cvar}_c = None")
                self._w(f"for _occ in root.allOccurrences:")
                self.ind += 1
                self._w(f'if _occ.component.name == "{comp_name}": {cvar}_c = _occ.component; break')
                self.ind -= 1
                self._w(f"if {cvar}_c is None:")
                self.ind += 1
                self._w(f"_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())")
                self._w(f'_occ.component.name = "{comp_name}"')
                self._w(f"{cvar}_c = _occ.component")
                self.ind -= 1
                self.components[comp_name] = f"{cvar}_c"

            if t == "ComponentCreation":
                cvar = self._var(name)
                self.components[name] = f"{cvar}_c"
                # Component exists from prior execution — find or create it
                self._w(f"{cvar}_c = None")
                self._w(f"for _occ in root.allOccurrences:")
                self.ind += 1
                self._w(f'if _occ.component.name == "{name}": {cvar}_c = _occ.component; break')
                self.ind -= 1
                self._w(f"if {cvar}_c is None:")
                self.ind += 1
                self._w(f"_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())")
                self._w(f'_occ.component.name = "{name}"')
                self._w(f"{cvar}_c = _occ.component")
                self.ind -= 1

            elif t == "ConstructionPlane":
                # Use component-scoped variable to avoid collisions
                # when multiple components have planes with the same name.
                # Planes in child components are proxied via occurrence
                # so they work in cross-component references.
                if comp_name and comp_name != self._root_name:
                    var = self._var(f"{name}_{comp_name}")
                    self._w(f'{var} = None')
                    self._w(f"for _occ in root.allOccurrences:")
                    self.ind += 1
                    self._w(f'if _occ.component.name == "{comp_name}":')
                    self.ind += 1
                    self._w(f'_p = _occ.component.constructionPlanes.itemByName("{name}")')
                    self._w(f"if _p: {var} = _p.createForAssemblyContext(_occ); break")
                    self.ind -= 2
                    self.planes[f"{comp_name}:{name}"] = var
                else:
                    var = self._var(name)
                    self._w(f'{var} = root.constructionPlanes.itemByName("{name}")')
                    self._w(f"if not {var}:")
                    self.ind += 1
                    self._w(f"for _occ in root.allOccurrences:")
                    self.ind += 1
                    self._w(f'_p = _occ.component.constructionPlanes.itemByName("{name}")')
                    self._w(f"if _p: {var} = _p.createForAssemblyContext(_occ); break")
                    self.ind -= 2
                self.planes[name] = var

            elif t == "Sketch":
                # Use component-suffixed variable name (matches _feat_sketch)
                if comp_name and comp_name != self._root_name:
                    var = self._var(f"{name}_{comp_name}")
                else:
                    var = self._var(name)
                plane_info = feat.get("plane", {})
                is_brep_face = plane_info.get("type") == "BRepFace"

                # BRepFace sketches are created in root (cross-component face
                # access), so search component first, then root, then all.
                c_ref = self.components.get(comp_name, "root")
                self._w(f'{var} = {c_ref}.sketches.itemByName("{name}")')
                if c_ref != "root":
                    # Also check root (BRepFace sketches may be created there)
                    self._w(f"if not {var}:")
                    self.ind += 1
                    self._w(f'{var} = root.sketches.itemByName("{name}")')
                    self.ind -= 1
                # Fallback: search all components
                self._w(f"if not {var}:")
                self.ind += 1
                self._w(f"for _sc in [root] + [_o.component for _o in root.allOccurrences]:")
                self.ind += 1
                self._w(f'_sk = _sc.sketches.itemByName("{name}")')
                self._w(f"if _sk: {var} = _sk; break")
                self.ind -= 2

                # Register with both plain and component-scoped keys
                self.sketches[name] = var
                if comp_name and comp_name != self._root_name:
                    self.sketches[f"{comp_name}:{name}"] = var
                # Track BRepFace info and sketch ownership.
                # BRepFace sketches go to root UNLESS they have cross-body
                # BRepFace refs (different body from the plane body), which
                # triggers _use_native_face → sketch stays in component.
                if is_brep_face:
                    self._brep_face_sketches[name] = plane_info
                    if comp_name:
                        self._brep_face_sketches[f"{comp_name}:{name}"] = plane_info
                    face_body = plane_info.get("body", "")
                    has_cross_body = any(
                        c.get("isReference")
                        and c.get("projectedFrom", {}).get("type") == "BRepFace"
                        and c.get("projectedFrom", {}).get("body", "") not in ("", face_body)
                        for c in feat.get("curves", [])
                    )
                    has_edge_proj = any(
                        c.get("isReference")
                        and c.get("projectedFrom", {}).get("type") == "BRepEdge"
                        for c in feat.get("curves", [])
                    )
                    # Cross-body refs or edge projections → sketch in comp
                    owner = "comp" if (has_cross_body or has_edge_proj) else "root"
                    self._sketch_owners[name] = owner
                    if comp_name:
                        self._sketch_owners[f"{comp_name}:{name}"] = owner
                else:
                    self._sketch_owners[name] = "comp"
                    if comp_name:
                        self._sketch_owners[f"{comp_name}:{name}"] = "comp"

                # Resolve profile for downstream extrude/sweep
                prof_count = feat.get("profileCount", 1)
                if prof_count > 0:
                    prof = f"{var}_prof"
                    # Runtime guard: sketch may be None (creation failed) or have 0 profiles
                    self._w(f"{prof} = {var}.profiles.item(0) if {var} and {var}.profiles.count > 0 else None")
                    self.profiles[name] = prof

            elif t in ("Extrude", "Sweep", "Mirror", "SplitBody",
                        "RectangularPattern", "CopyPasteBody"):
                # Set component context for _body_var scoping
                self._current_comp = comp_name
                # Register bodies from both "bodies" and "patternCopies"
                all_body_names = list(feat.get("bodies", []))
                for pc in feat.get("patternCopies", []):
                    if pc not in all_body_names:
                        all_body_names.append(pc)
                for bn in all_body_names:
                    bv = self._body_var(bn)
                    # Use component-scoped lookup to avoid name collisions
                    # (e.g., beam:Body1 vs deck5:Body1)
                    if comp_name and comp_name != self._root_name:
                        c_ref = self.components.get(comp_name, "root")
                        self._w(f'{bv} = find_body("{bn}", {c_ref})')
                    else:
                        self._w(f'{bv} = find_body("{bn}")')
                    self._register_body(bn, bv)
                # Register feature for Adjust mirror lookups
                if t == "Extrude" and name:
                    fvar = self._var(f"_feat_{name}_{comp_name}" if comp_name else f"_feat_{name}")
                    c_ref = self.components.get(comp_name, "root") if comp_name and comp_name != self._root_name else "root"
                    self._w(f'{fvar} = {c_ref}.features.extrudeFeatures.itemByName("{name}")')
                    self.feats[name] = fvar
                # Track face-based sketch extrude distances for offset computation
                if t == "Extrude":
                    sk_name = feat.get("sketch", "")
                    sk_comp = feat.get("sketchComponent", comp_name)
                    sk_key = f"{sk_comp}:{sk_name}" if sk_comp else sk_name
                    if (sk_key in self._brep_face_sketches
                            or sk_name in self._brep_face_sketches):
                        dists = self._face_sketch_extrude_dists.get(sk_key, [])
                        dists.append(feat.get("distance", "1 cm"))
                        self._face_sketch_extrude_dists[sk_key] = dists

            elif t == "Remove":
                removed = feat.get("removedBody", "")
                if removed in self.bodies:
                    del self.bodies[removed]

            elif t == "Combine":
                self._current_comp = comp_name
                if not feat.get("isKeepToolBodies"):
                    for tb in feat.get("toolBodies", []):
                        if tb in self.bodies:
                            del self.bodies[tb]
                        scoped = f"{comp_name}:{tb}" if comp_name else ""
                        if scoped and scoped in self.bodies:
                            del self.bodies[scoped]

            elif t == "Snapshot":
                # Re-apply occurrence transforms from prior Snapshots.
                # Direct occ.transform assignment persists because the scratch
                # doc has no joints/Snapshot features to override it.
                transforms = feat.get("transforms", {})
                for cname, data in transforms.items():
                    if cname not in self.components:
                        continue
                    self._w(f"for _o in root.allOccurrences:")
                    self.ind += 1
                    self._w(f'if _o.component.name == "{cname}":')
                    self.ind += 1
                    if len(data) == 16:
                        self._w(f"_xf = adsk.core.Matrix3D.create()")
                        for row in range(4):
                            for col in range(4):
                                val = data[row * 4 + col]
                                identity = 1.0 if row == col else 0.0
                                if abs(val - identity) > 1e-9:
                                    self._w(f"_xf.setCell({row}, {col}, {val})")
                        self._w(f"_o.transform = _xf")
                    else:
                        self._w(f"_xf = _o.transform")
                        self._w(f"_xf.translation = adsk.core.Vector3D.create({data[0]}, {data[1]}, {data[2]})")
                        self._w(f"_o.transform = _xf")
                    self._w(f"break")
                    self.ind -= 2

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
            self._current_comp = feat.get("component", "")
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
