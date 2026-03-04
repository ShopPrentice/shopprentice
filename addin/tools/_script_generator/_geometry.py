"""Geometry mixin: plane resolution, body references, BRepFace-to-cplane."""

import re


class _GeometryMixin:
    """Plane resolution, body/component references, BRepFace→cplane conversion."""

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
            # No pointOnFace — use find_face_near with origin if available,
            # or find_face with axis/direction as last resort.
            origin = plane_info.get("origin")
            if origin:
                n = normal or [0, 0, 0]
                return (f'find_face_near({bv}, {round(origin[0], 4)}, '
                        f'{round(origin[1], 4)}, {round(origin[2], 4)}, '
                        f'{round(n[0], 4)}, {round(n[1], 4)}, {round(n[2], 4)})')
            if normal:
                axis, direction = self._normal_to_axis(normal)
                return f'find_face({bv}, "{axis}", {direction})'
            # Last resort: no pointOnFace, no origin, no normal.
            # Search all bodies for any planar face (None body = search all)
            return f'find_face_near({bv}, 0, 0, 0)'

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
