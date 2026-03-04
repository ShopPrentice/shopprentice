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
