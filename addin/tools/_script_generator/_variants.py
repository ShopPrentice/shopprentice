"""Variants mixin: save/restore state, variant enumeration for search building."""

import copy
from contextlib import contextmanager


class _VariantsMixin:
    """State snapshots and variant enumeration for search-based script generation."""

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

        if t == "RectangularPattern":
            return self._rectangularpattern_variants(feat)

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
        """Generate extrude variants: direction flip, sequential multi-profile,
        profile-index search, and face-following offset."""
        dist = feat.get("distance", "1 cm")
        is_negative = dist.startswith("-(") and dist.endswith(")")

        # Detect multi-profile sketch created in ROOT but extruded in a
        # child component — ObjectCollection may fail with bSet.
        # Only needed when the sketch is actually in root (not when it's
        # a _use_native_face sketch created in the component).
        needs_sequential_variant = False
        profile_indices = feat.get("profileIndices", [feat.get("profileIndex", 0)])
        if len(profile_indices) > 1 and self._comp_ref(feat) != "root":
            sketch_name = feat.get("sketch", "")
            sketch_comp = feat.get("sketchComponent", feat.get("component", ""))
            sk_key = f"{sketch_comp}:{sketch_name}" if sketch_comp else sketch_name
            sk_owner = self._sketch_owners.get(
                sk_key, self._sketch_owners.get(sketch_name, ""))
            if sk_owner == "root":
                needs_sequential_variant = True

        # Detect unknown profile index: profileIndex not set AND the sketch
        # has >1 profile. Search all profile indices.
        # Also triggers when profileIndices is empty ([]) — capture didn't
        # record which profile was used, so we must search.
        profile_ambiguous = False
        num_profiles = 1
        if (not feat.get("profileIndices") and "profileIndex" not in feat
                and feat.get("sketch")):
            sketch_name = feat.get("sketch", "")
            sketch_comp = feat.get("sketchComponent", feat.get("component", ""))
            feat_idx = feat.get("index", len(self.cap.get("timeline", [])))
            for ti, tf in enumerate(self.cap.get("timeline", [])):
                if ti >= feat_idx:
                    break
                if (tf.get("type") == "Sketch" and tf.get("name") == sketch_name
                        and tf.get("component", "") == sketch_comp):
                    num_profiles = tf.get("profileCount", 1)
            if num_profiles > 1:
                profile_ambiguous = True

        # Detect face-following offset: face-based sketch reused by
        # multiple extrudes. The sketch plane may have moved with the face.
        # Whether offset is needed depends on profile overlap with the face
        # region modified by prior extrudes — we can't determine this
        # statically, so we try both with and without offset as variants.
        needs_offset_variant = False
        offset_expr = None
        sketch = feat.get("sketch", "")
        sketch_comp_key = feat.get("sketchComponent", feat.get("component", ""))
        sk_off_key = f"{sketch_comp_key}:{sketch}" if sketch_comp_key else sketch
        is_face = (sk_off_key in self._brep_face_sketches
                   or sketch in self._brep_face_sketches)
        if is_face:
            prior = (self._face_sketch_extrude_dists.get(sk_off_key)
                     or self._face_sketch_extrude_dists.get(sketch, []))
            if prior:
                needs_offset_variant = True
                offset_expr = " + ".join(f"({d})" for d in prior)

        if (not is_negative and not needs_sequential_variant
                and not profile_ambiguous and not needs_offset_variant):
            # Not ambiguous
            saved = self._save_state()
            with self._capture_output() as lines:
                self._feat_extrude(feat)
            state = self._save_state()
            self._restore_state(saved)
            return [(lines, "default", state)]

        variants = []
        # Variant 0: default (no offset)
        saved = self._save_state()
        with self._capture_output() as lines:
            self._feat_extrude(feat)
        state0 = self._save_state()
        self._restore_state(saved)
        variants.append((lines, "default (profile 0)", state0))

        if needs_offset_variant:
            # Variant: with face-following offset
            f2 = copy.deepcopy(feat)
            f2["_offset_expr"] = offset_expr
            saved = self._save_state()
            with self._capture_output() as lines:
                self._feat_extrude(f2)
            state_off = self._save_state()
            self._restore_state(saved)
            variants.append((lines, f"profile 0 + offset", state_off))

        if is_negative:
            # Variant: keep as positive (don't unwrap)
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

        if needs_sequential_variant:
            # Variant: sequential single-profile extrudes (avoids bSet error)
            f2 = copy.deepcopy(feat)
            f2["_force_sequential"] = True
            saved = self._save_state()
            with self._capture_output() as lines:
                self._feat_extrude(f2)
            state2 = self._save_state()
            self._restore_state(saved)
            variants.append((lines, "sequential multi-profile", state2))

        if profile_ambiguous:
            # Try each non-default profile index, with and without offset
            for pi in range(1, num_profiles):
                f2 = copy.deepcopy(feat)
                f2["profileIndex"] = pi
                f2["profileIndices"] = [pi]
                saved = self._save_state()
                with self._capture_output() as lines:
                    self._feat_extrude(f2)
                state_pi = self._save_state()
                self._restore_state(saved)
                variants.append((lines, f"profile {pi}", state_pi))

                if needs_offset_variant:
                    f3 = copy.deepcopy(f2)
                    f3["_offset_expr"] = offset_expr
                    saved = self._save_state()
                    with self._capture_output() as lines:
                        self._feat_extrude(f3)
                    state_pi_off = self._save_state()
                    self._restore_state(saved)
                    variants.append((lines, f"profile {pi} + offset", state_pi_off))

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

    def _rectangularpattern_variants(self, feat):
        """Generate pattern variants: try X, Y, Z axes × flip when direction is unknown."""
        axis_name = feat.get("axisOne", "")
        direction = feat.get("directionOne")
        if direction:
            # Direction known (with sign) — single default variant
            saved = self._save_state()
            with self._capture_output() as lines:
                self._feat_rectangularpattern(feat)
            state = self._save_state()
            self._restore_state(saved)
            return [(lines, "default", state)]

        # Direction unknown — try all 3 axes × positive/negative distance
        dist = feat.get("distanceOne", "5 cm")
        variants = []
        for axis in ["X", "Y", "Z"]:
            for neg in [False, True]:
                f2 = copy.deepcopy(feat)
                f2["axisOne"] = axis
                if neg:
                    f2["distanceOne"] = f"-({dist})"
                saved = self._save_state()
                with self._capture_output() as lines:
                    self._feat_rectangularpattern(f2)
                state = self._save_state()
                self._restore_state(saved)
                desc = f"axis={axis}" + (" neg" if neg else "")
                variants.append((lines, desc, state))
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
            "_sketch_owners": dict(self._sketch_owners),
            "_flipped_planes": set(self._flipped_planes),
            "_face_sketch_extrude_dists": {k: list(v) for k, v in self._face_sketch_extrude_dists.items()},
        }

    def _restore_state(self, state):
        """Restore generator state from snapshot."""
        self.planes = dict(state["planes"])
        self.sketches = dict(state["sketches"])
        self.profiles = dict(state["profiles"])
        self.bodies = dict(state["bodies"])
        self.feats = dict(state["feats"])
        self._brep_face_sketches = dict(state["_brep_face_sketches"])
        self._sketch_owners = dict(state.get("_sketch_owners", {}))
        self._flipped_planes = set(state.get("_flipped_planes", set()))
        self._face_sketch_extrude_dists = {k: list(v) for k, v in state.get("_face_sketch_extrude_dists", {}).items()}
