"""Geometry mixin: plane resolution, body references, BRepFace-to-cplane."""

import re


class _GeometryMixin:
    """Plane resolution, body/component references, BRepFace→cplane conversion."""

    def _resolve_plane(self, plane_info, consumer_comp=""):
        if not plane_info:
            return "root.xYConstructionPlane"
        ptype = plane_info.get("type")
        pname = plane_info.get("name", "")

        if ptype == "ConstructionPlane":
            builtin = {"XY": "root.xYConstructionPlane",
                       "XZ": "root.xZConstructionPlane",
                       "YZ": "root.yZConstructionPlane"}
            if pname in builtin:
                return builtin[pname]
            # Try origin/normal matching against timeline to find correct
            # component-scoped key (prevents collision when multiple
            # components have same-named planes)
            p_origin = plane_info.get("origin")
            p_normal = plane_info.get("normal")
            if p_origin and p_normal:
                for tf in self.cap.get("timeline", []):
                    if (tf.get("type") == "ConstructionPlane"
                            and tf.get("name") == pname):
                        tf_o = tf.get("origin", [])
                        tf_n = tf.get("normal", [])
                        if (tf_o and tf_n
                                and sum(abs(a - b) for a, b in zip(p_origin, tf_o)) < 0.1
                                and sum(abs(a - b) for a, b in zip(p_normal, tf_n)) < 0.1):
                            cn = tf.get("component", "")
                            scoped = f"{cn}:{pname}" if cn else ""
                            if scoped and scoped in self.planes:
                                return self.planes[scoped]
                            break
            # No origin/normal — try consumer's own component first
            if consumer_comp:
                scoped = f"{consumer_comp}:{pname}"
                if scoped in self.planes:
                    return self.planes[scoped]
            if pname in self.planes:
                return self.planes[pname]
            return f'root.xYConstructionPlane  # TODO: "{pname}"'

        if ptype == "BRepFace":
            body_name = plane_info.get("body", "")
            normal = plane_info.get("normal")
            pof = plane_info.get("pointOnFace")
            # Check if body name is ambiguous (appears in multiple components).
            # If so and we have pointOnFace+normal, search ALL bodies instead
            # of relying on name-based resolution which may pick the wrong one.
            scoped_count = sum(
                1 for k in self.bodies if k.endswith(f":{body_name}")
            )
            ambiguous = scoped_count > 1
            bv = "None" if (ambiguous and pof and normal) else self._body_ref(body_name)
            if pof:
                # Use pointOnFace + normal for precise face selection.
                n = normal or [0, 0, 0]
                return (f'find_face_near({bv}, {round(pof[0], 4)}, '
                        f'{round(pof[1], 4)}, {round(pof[2], 4)}, '
                        f'{round(n[0], 4)}, {round(n[1], 4)}, {round(n[2], 4)})')
            origin = plane_info.get("origin")
            if origin:
                n = normal or [0, 0, 0]
                return (f'find_face_near({bv}, {round(origin[0], 4)}, '
                        f'{round(origin[1], 4)}, {round(origin[2], 4)}, '
                        f'{round(n[0], 4)}, {round(n[1], 4)}, {round(n[2], 4)})')
            if normal:
                axis, direction = self._normal_to_axis(normal)
                return f'find_face({bv}, "{axis}", {direction})'
            return f'find_face_near({bv}, 0, 0, 0)'

        if ptype == "InferredPlane":
            # Sketch plane inferred from axes when referencePlane was None.
            # Create an offset construction plane from the nearest standard plane.
            normal = plane_info.get("normal", [0, 0, 1])
            origin = plane_info.get("origin", [0, 0, 0])
            ax, ay, az = abs(normal[0]), abs(normal[1]), abs(normal[2])
            if az >= ay and az >= ax:
                base = "comp.xYConstructionPlane"
                offset = origin[2]
            elif ay >= ax:
                base = "comp.xZConstructionPlane"
                offset = origin[1]
            else:
                base = "comp.yZConstructionPlane"
                offset = origin[0]
            # If offset is near zero, use the standard plane directly
            if abs(offset) < 0.001:
                return base
            # Create a named offset plane using the off_plane helper
            plane_var = self._var(f"_inferred_pl_{len(self.planes)}")
            self._w(f'{plane_var} = off_plane(comp, {base}, "{round(offset, 4)} cm", "_inferred_{len(self.planes)}")')
            self.planes[f"_inferred_{len(self.planes)}"] = plane_var
            return plane_var

        return "root.xYConstructionPlane"

    def _resolve_plane_proxied(self, plane_info, consumer_comp):
        """Resolve plane and emit proxy code if it's from a different component.

        consumer_comp: component name of the feature using the plane.
        Returns the variable/expression to use for the plane.
        """
        plane_code = self._resolve_plane(plane_info, consumer_comp)

        # Only proxy user-created construction planes (not builtins, not BRepFace)
        ptype = plane_info.get("type") if plane_info else None
        if ptype != "ConstructionPlane":
            return plane_code

        plane_comp = self._plane_comps.get(plane_code, "")
        if (plane_comp and consumer_comp
                and plane_comp != consumer_comp
                and plane_comp != self._root_name):
            # Cross-component plane — proxy it through the occurrence
            proxy_var = f"_{self._var(plane_info.get('name', 'pl'))}_proxy"
            self._w(f"{proxy_var} = {plane_code}")
            self._w(f"for _occ in root.allOccurrences:")
            self.ind += 1
            self._w(f'if _occ.component.name == "{plane_comp}":')
            self.ind += 1
            self._w(f"{proxy_var} = {plane_code}.createForAssemblyContext(_occ); break")
            self.ind -= 2
            return proxy_var

        return plane_code

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

    def _body_ref(self, name, component=None):
        """Get variable reference for a body name, with fallback for renamed bodies.

        Args:
            component: If given, look up the body from this specific component
                       instead of the current feature's component.  When an
                       explicit component is provided and the scoped lookup fails,
                       skip unscoped fallback to avoid cross-component collisions.
        """
        # Try component-scoped key first (prevents cross-component collision)
        comp = component or getattr(self, '_current_comp', '')
        if comp:
            scoped = f"{comp}:{name}"
            if scoped in self.bodies:
                return self.bodies[scoped]
        # When an explicit component was requested and not found, don't fall back
        # to unscoped lookup — that would silently resolve to a same-named body
        # in a different component.  Use component-scoped find_body instead.
        if component:
            comp_var = self.components.get(component)
            if comp_var:
                return f'find_body("{name}", {comp_var})'
            return f'find_body("{name}")'
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
