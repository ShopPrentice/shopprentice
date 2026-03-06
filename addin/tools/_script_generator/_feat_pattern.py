"""Pattern mixin: rectangular pattern, construction axis, component, snapshot."""


class _PatternMixin:
    """Feature emitters for pattern, axis, component creation, and snapshot."""

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
        negative = False
        if axis_name in axis_map:
            axis_code = axis_map[axis_name]
        elif direction:
            # Infer axis from direction vector (preserving sign)
            dx, dy, dz = direction
            adx, ady, adz = abs(dx), abs(dy), abs(dz)
            if adx >= ady and adx >= adz:
                axis_code = "root.xConstructionAxis"
                negative = dx < 0
            elif ady >= adx and ady >= adz:
                axis_code = "root.yConstructionAxis"
                negative = dy < 0
            else:
                axis_code = "root.zConstructionAxis"
                negative = dz < 0
        else:
            axis_code = "root.xConstructionAxis"
            self._c(f"TODO: axis '{axis_name}' not resolved, defaulting to X")

        # Wrap distance for negative direction
        if negative:
            dist = f"-({dist})"

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

        self._w(f"pat_inp = comp.features.rectangularPatternFeatures.createInput(")
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

        # Track output bodies — rename pattern copies to match original names.
        pattern_copies = f.get("patternCopies", [])
        if pattern_copies:
            # pat.bodies API is unreliable — scan comp.bRepBodies for new copies.
            # Record body names BEFORE pattern creation to find the delta after.
            self._w("_before_pat = set(comp.bRepBodies.item(_i).name"
                     " for _i in range(comp.bRepBodies.count))")

        self._w(f"{var} = comp.features.rectangularPatternFeatures.add(pat_inp)")
        self._w(f'{var}.name = "{name}"')
        self.feats[name] = var

        if pattern_copies:
            direction = f.get("directionOne", [1, 0, 0])
            dx, dy, dz = direction
            adx, ady, adz = abs(dx), abs(dy), abs(dz)
            if ady >= adx and ady >= adz:
                sort_attr = "y"
            elif adz >= adx and adz >= ady:
                sort_attr = "z"
            else:
                sort_attr = "x"
            # Find new bodies created by pattern
            self._w("_pat_copies = []")
            self._w("for _i in range(comp.bRepBodies.count):")
            self.ind += 1
            self._w("_b = comp.bRepBodies.item(_i)")
            self._w("if _b.name not in _before_pat:")
            self.ind += 1
            self._w("_pat_copies.append(_b)")
            self.ind -= 2
            # Sort ascending by coordinate — matches capture's patternCopies order
            self._w(f"_pat_copies.sort(key=lambda _b:"
                     f" getattr(_b.boundingBox.minPoint, '{sort_attr}'))")
            for i, bn in enumerate(pattern_copies):
                bv = self._body_var(bn)
                self._register_body(bn, bv)
                self._w(f"if {i} < len(_pat_copies):")
                self.ind += 1
                self._w(f"{bv} = _pat_copies[{i}]")
                self._w(f'{bv}.name = "{bn}"')
                self.ind -= 1
        else:
            # Fallback: use pat.bodies directly (works when capture has full list)
            input_set = set(inputs)
            new_bodies = [bn for bn in bodies if bn not in input_set]
            for i, bn in enumerate(new_bodies):
                bv = self._body_var(bn)
                self._register_body(bn, bv)
                self._w(f'{bv} = {var}.bodies.item({i})')
                self._w(f'{bv}.name = "{bn}"')

    def _feat_constructionaxis(self, f):
        name = f.get("name", "Axis")
        self._c(f"ConstructionAxis: {name}")
        self._c("TODO: Reconstruct construction axis")

    def _feat_componentcreation(self, f):
        name = f.get("name", "Component")
        var = self._var(name)
        self._w(f"{var}_occ = comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())")
        self._w(f'{var}_occ.component.name = "{name}"')
        self._w(f"{var}_c = {var}_occ.component")
        self.components[name] = f"{var}_c"

    def _feat_snapshot(self, f):
        self._c("Snapshot (informational only, no code needed)")
