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

        self._w(f"{var} = comp.features.rectangularPatternFeatures.add(pat_inp)")
        self._w(f'{var}.name = "{name}"')
        self.feats[name] = var

        # Track output bodies — pat.bodies only includes NEW copies, not the original.
        # Filter out bodies already tracked (the original input body).
        # Also rename pattern bodies to match captured names so downstream
        # find_body() calls work (scratch doc has different auto-numbering).
        new_bodies = [bn for bn in bodies if bn not in self.bodies]
        for i, bn in enumerate(new_bodies):
            bv = self._var(bn)
            self.bodies[bn] = bv
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
