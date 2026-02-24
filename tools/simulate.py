#!/usr/bin/env python3
"""
Headless 3D Geometry Simulator
===============================
Replays Fusion 360 timeline features using manifold3d for fast local
validation — no Fusion 360 roundtrip needed.

Reads introspection JSON (from introspect.py) and optional bodies ground
truth (from introspect_bodies.py), simulates geometry, and compares
per-body volume and bounding box against ground truth.

Usage:
    python tools/simulate.py introspect.json --bodies bodies.json [--verbose]

Dependencies:
    pip install manifold3d
"""
import argparse
import json
import math
import re
import sys

from manifold3d import CrossSection, Manifold

# ── Parameter Resolver ────────────────────────────────────────────


class ParamResolver:
    """Evaluate Fusion 360 parameter expressions to cm values."""

    UNITS = {
        "in": 2.54, "mm": 0.1, "cm": 1.0, "m": 100.0,
        "ft": 30.48, "deg": 1.0,
    }

    def __init__(self, params_list):
        # params_list: [{"name", "expression", "value", "unit"}, ...]
        # "value" is already in internal units (cm for length, rad for angle)
        self.params = {}
        for p in params_list:
            self.params[p["name"]] = p["value"]

    # Regex for "N unit" patterns within expressions (e.g. "1.5 in", "0.25 mm")
    _UNIT_RE = re.compile(
        r'(\d+(?:\.\d+)?)\s*(in|mm|cm|m|ft|deg)\b'
    )

    def ev(self, expr):
        """Evaluate expression string -> float (cm for lengths)."""
        if expr is None:
            return 0.0
        expr = str(expr).strip()
        if not expr:
            return 0.0

        # 1. Simple numeric literal with unit suffix: "69.5 in", "-1.5 mm"
        m = re.match(r'^([+-]?\d+(?:\.\d+)?)\s*(in|mm|cm|m|ft|deg)$', expr)
        if m:
            return float(m.group(1)) * self.UNITS[m.group(2)]

        # 2. Plain numeric literal
        try:
            return float(expr)
        except ValueError:
            pass

        # 3. Expression — substitute units and param references, then eval
        #    Replace all "N unit" tokens with their cm values first
        text = self._UNIT_RE.sub(
            lambda m: str(float(m.group(1)) * self.UNITS[m.group(2)]), expr)
        # Then substitute parameter names (longest first to avoid partial matches)
        for name, val in sorted(self.params.items(), key=lambda x: -len(x[0])):
            text = text.replace(name, str(val))

        safe_ns = {
            "floor": math.floor, "ceil": math.ceil, "abs": abs,
            "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "sqrt": math.sqrt, "pi": math.pi,
        }
        try:
            return float(eval(text, {"__builtins__": {}}, safe_ns))
        except Exception:
            return 0.0


# ── Sketch Analysis ───────────────────────────────────────────────


def classify_sketch(feat):
    """Classify a sketch as 'rect', 'slot', 'raw', or 'unknown'.
    Mirrors generate.py:classify_sketch exactly."""
    curves = feat.get("curves", [])
    lines = [c for c in curves if c["type"] == "Line" and not c.get("isConstruction")]
    arcs = [c for c in curves if c["type"] == "Arc"]
    circles = [c for c in curves if c["type"] == "Circle"]

    if len(lines) == 4 and len(arcs) == 0 and len(circles) == 0:
        return "rect"
    if len(arcs) == 2 and len(lines) >= 2:
        return "slot"
    if lines or arcs or circles:
        return "raw"
    return "unknown"


# ── Sketch Builder ────────────────────────────────────────────────


class SketchBuilder:
    """Convert introspected sketch data to manifold3d CrossSection."""

    def build_cross_section(self, sketch_feat, profile_index=0):
        """Returns CrossSection or None if sketch can't be built."""
        # If the sketch has profile bounds for the requested index, prefer
        # using those bounds directly — this is more reliable than chaining
        # raw curves, especially for multi-profile sketches.
        profiles = sketch_feat.get("profiles", [])
        prof = None
        for p in profiles:
            if p.get("index") == profile_index:
                prof = p
                break

        kind = classify_sketch(sketch_feat)
        if kind == "rect":
            return self._build_rect(sketch_feat, profile_index)
        elif kind == "slot":
            return self._build_slot(sketch_feat)
        elif kind == "raw":
            return self._build_raw(sketch_feat, prof)
        return None

    def _build_rect(self, feat, prof_idx):
        profiles = feat.get("profiles", [])
        if profiles and prof_idx < len(profiles):
            prof = profiles[prof_idx]
            x0, y0 = prof["min"]
            x1, y1 = prof["max"]
        else:
            # Fall back to curve bounding box
            x0, y0, x1, y1 = self._curves_bbox(feat)
        w = x1 - x0
        h = y1 - y0
        if w <= 0 or h <= 0:
            return None
        cs = CrossSection.square([w, h]).translate([x0, y0])
        return cs

    def _build_slot(self, feat):
        # Approximate stadium as bounding rectangle of arcs + lines
        arcs = [c for c in feat.get("curves", []) if c["type"] == "Arc"]
        if len(arcs) >= 2:
            # Use arc centers and radius to compute bounds
            centers = [a["center"] for a in arcs]
            r = arcs[0].get("radius", 0)
            xs = [c[0] for c in centers]
            ys = [c[1] for c in centers]
            x0 = min(xs) - r
            y0 = min(ys) - r
            x1 = max(xs) + r
            y1 = max(ys) + r
        else:
            x0, y0, x1, y1 = self._curves_bbox(feat)
        w = x1 - x0
        h = y1 - y0
        if w <= 0 or h <= 0:
            return None
        return CrossSection.square([w, h]).translate([x0, y0])

    def _build_raw(self, feat, profile=None):
        # For multi-profile sketches, use the profile's bounding box directly.
        # This is more reliable than chaining all lines (which span ALL profiles).
        if profile is not None:
            x0, y0 = profile["min"]
            x1, y1 = profile["max"]
            w, h = x1 - x0, y1 - y0
            if w > 0 and h > 0:
                return CrossSection.square([w, h]).translate([x0, y0])

        lines = [c for c in feat.get("curves", [])
                 if c["type"] == "Line" and not c.get("isConstruction")]
        if not lines:
            return None

        # Try to chain endpoints into a closed polygon
        pts = self._chain_lines(lines)
        if len(pts) < 3:
            # Fall back to bounding box
            x0, y0, x1, y1 = self._curves_bbox(feat)
            w, h = x1 - x0, y1 - y0
            if w <= 0 or h <= 0:
                return None
            return CrossSection.square([w, h]).translate([x0, y0])

        try:
            return CrossSection([pts])
        except Exception:
            # If polygon is invalid, fall back to bbox
            x0, y0, x1, y1 = self._curves_bbox(feat)
            w, h = x1 - x0, y1 - y0
            if w <= 0 or h <= 0:
                return None
            return CrossSection.square([w, h]).translate([x0, y0])

    def _chain_lines(self, lines):
        """Chain line segments into an ordered polygon.
        Returns list of [x, y] points."""
        if not lines:
            return []
        EPS = 0.001
        remaining = list(lines)
        chain = [remaining.pop(0)]
        # Keep trying to extend the chain
        changed = True
        while remaining and changed:
            changed = False
            tip = chain[-1]["end"]
            for i, seg in enumerate(remaining):
                if self._close(seg["start"], tip, EPS):
                    chain.append(remaining.pop(i))
                    changed = True
                    break
                elif self._close(seg["end"], tip, EPS):
                    # Reverse segment
                    remaining.pop(i)
                    chain.append({"start": seg["end"], "end": seg["start"]})
                    changed = True
                    break
        return [[s["start"][0], s["start"][1]] for s in chain]

    @staticmethod
    def _close(a, b, eps):
        return abs(a[0] - b[0]) < eps and abs(a[1] - b[1]) < eps

    @staticmethod
    def _curves_bbox(feat):
        """Compute bounding box of all non-construction curves."""
        xs, ys = [], []
        for c in feat.get("curves", []):
            if c.get("isConstruction"):
                continue
            if c["type"] == "Line":
                xs.extend([c["start"][0], c["end"][0]])
                ys.extend([c["start"][1], c["end"][1]])
            elif c["type"] == "Arc":
                cx, cy = c["center"]
                r = c.get("radius", 0)
                xs.extend([cx - r, cx + r])
                ys.extend([cy - r, cy + r])
            elif c["type"] == "Circle":
                cx, cy = c["center"]
                r = c.get("radius", 0)
                xs.extend([cx - r, cx + r])
                ys.extend([cy - r, cy + r])
        if not xs:
            return 0, 0, 0, 0
        return min(xs), min(ys), max(xs), max(ys)


# ── Simulator ─────────────────────────────────────────────────────


class Simulator:
    """Walk introspection timeline and build manifold3d geometry."""

    def __init__(self, data, params):
        self.timeline = data.get("timeline", [])
        self.params = params
        self.sketch_builder = SketchBuilder()
        self.sketch_data = {}       # (comp, name) -> sketch feat
        self.comp_bodies = {}       # comp_name -> {body_name: Manifold}
        self.planes = {}            # (comp, name) -> plane info dict
        self.body_created_at = {}   # (comp, body_name) -> timeline index
        self.comp_move_count = {}   # comp_name -> number of Moves applied
        self.verbose = False
        # Feature statistics
        self.stats = {"applied": 0, "skipped_err": 0, "skipped_nosk": 0,
                      "skipped_nocs": 0, "skipped_notgt": 0, "by_type": {}}

    def run(self):
        """Execute all timeline features. Returns comp_bodies dict."""
        for feat in self.timeline:
            ftype = feat.get("type", "")
            handler = {
                "Sketch": self._handle_sketch,
                "Extrude": self._handle_extrude,
                "ConstructionPlane": self._handle_construction_plane,
                "Mirror": self._handle_mirror,
                "Combine": self._handle_combine,
                "Move": self._handle_move,
                "RectangularPattern": self._handle_pattern,
                "ComponentCreation": self._handle_component,
            }.get(ftype)
            if handler:
                try:
                    handler(feat)
                except Exception as e:
                    if self.verbose:
                        print(f"  WARN [{feat.get('index')}] {ftype} "
                              f"{feat.get('name','')}: {e}", file=sys.stderr)
            if self.verbose and ftype in ("Extrude", "Mirror", "Combine",
                                          "Move", "RectangularPattern"):
                self._print_state(feat)
        return self.comp_bodies

    def _stat(self, ftype, applied=True, reason=None):
        """Record feature execution statistics."""
        self.stats["by_type"].setdefault(ftype, {"applied": 0, "skipped": 0})
        if applied:
            self.stats["applied"] += 1
            self.stats["by_type"][ftype]["applied"] += 1
        else:
            self.stats["by_type"][ftype]["skipped"] += 1
            if reason:
                self.stats[reason] = self.stats.get(reason, 0) + 1

    def _print_state(self, feat):
        comp = feat.get("component", "?")
        bodies = self.comp_bodies.get(comp, {})
        if not bodies:
            return
        print(f"  [{feat.get('index')}] {feat['type']} {feat.get('name','')} "
              f"({comp}):", file=sys.stderr)
        for bname, solid in bodies.items():
            bb = solid.bounding_box()
            print(f"    {bname}: vol={solid.volume():.1f} "
                  f"bb=({bb[0]:.1f},{bb[1]:.1f},{bb[2]:.1f})-"
                  f"({bb[3]:.1f},{bb[4]:.1f},{bb[5]:.1f})", file=sys.stderr)

    # ── Feature handlers ──────────────────────────────────────────

    def _handle_sketch(self, feat):
        comp = feat.get("component", "root")
        name = feat.get("name", "")
        self.sketch_data[(comp, name)] = feat

    def _handle_component(self, feat):
        # Just ensure the component exists in our body map
        name = feat.get("name", "")
        if name:
            self.comp_bodies.setdefault(name, {})

    def _handle_construction_plane(self, feat):
        comp = feat.get("component", "root")
        name = feat.get("name", "")
        # Store plane info — offset, base plane, etc.
        self.planes[(comp, name)] = feat

    def _resolve_target_body(self, feat, comp):
        """Resolve the target body name for an extrude operation.
        Uses feat['bodies'][0] if available, otherwise falls back to
        the first body in the component (Fusion's default behavior)."""
        bodies = feat.get("bodies", [])
        if bodies:
            return bodies[0]
        # Fall back: if the component has exactly one body, use it
        comp_bodies = self.comp_bodies.get(comp, {})
        if len(comp_bodies) == 1:
            return next(iter(comp_bodies))
        # Multiple bodies — default to "Body1" (Fusion convention)
        if "Body1" in comp_bodies:
            return "Body1"
        return None

    def _handle_extrude(self, feat):
        comp = feat.get("component", "root")
        operation = feat.get("operation", "NewBody")

        # Resolve sketch
        sk_name = feat.get("sketch") or feat.get("sketchName")
        sk_comp = feat.get("sketchComponent", comp)
        if not sk_name:
            self._stat("Extrude", False, "skipped_nosk")
            return

        if feat.get("sketchError"):
            self._stat("Extrude", False, "skipped_err")
            return

        sk_feat = self.sketch_data.get((sk_comp, sk_name))
        if not sk_feat:
            # Try finding sketch in root component
            sk_feat = self.sketch_data.get(("root", sk_name))
        if not sk_feat:
            self._stat("Extrude", False, "skipped_nosk")
            return

        prof_idx = feat.get("profileIndex", 0)
        cs = self.sketch_builder.build_cross_section(sk_feat, prof_idx)
        if cs is None:
            self._stat("Extrude", False, "skipped_nocs")
            return

        dist_cm = self.params.ev(feat.get("distance"))
        if dist_cm == 0:
            self._stat("Extrude", False, "skipped_nocs")
            return

        plane = sk_feat.get("plane", "XY")

        if operation == "NewBody":
            solid = self._extrude_on_plane(cs, dist_cm, plane)
            bodies = feat.get("bodies", [])
            body_name = bodies[0] if bodies else \
                f"Body{len(self.comp_bodies.get(comp, {})) + 1}"
            self.comp_bodies.setdefault(comp, {})[body_name] = solid
            self.body_created_at[(comp, body_name)] = feat.get("index", 0)
            self._stat("Extrude")

        elif operation == "Cut":
            target_name = self._resolve_target_body(feat, comp)
            tool = self._extrude_on_plane(cs, abs(dist_cm), plane)
            if target_name and target_name in self.comp_bodies.get(comp, {}):
                try:
                    self.comp_bodies[comp][target_name] -= tool
                    self._stat("Extrude")
                except Exception:
                    self._stat("Extrude", False, "skipped_nocs")
            else:
                self._stat("Extrude", False, "skipped_notgt")

        elif operation == "Join":
            target_name = self._resolve_target_body(feat, comp)
            addition = self._extrude_on_plane(cs, abs(dist_cm), plane)
            if target_name and target_name in self.comp_bodies.get(comp, {}):
                try:
                    self.comp_bodies[comp][target_name] += addition
                    self._stat("Extrude")
                except Exception:
                    self._stat("Extrude", False, "skipped_nocs")
            else:
                self._stat("Extrude", False, "skipped_notgt")

    def _extrude_on_plane(self, cs, dist, plane_str):
        """Extrude CrossSection on the given plane, return positioned Manifold.

        manifold3d builds in XY (cross section) extruded along +Z.
        We use 3x4 transform matrices to remap axes to world space.

        XY plane: sketch X→world X, sketch Y→world Y, extrude→world Z
        XZ plane: sketch X→world X, sketch Y→world Z, extrude→world Y
        YZ plane: sketch X→world Y, sketch Y→world Z, extrude→world X
        """
        height = abs(dist)
        solid = cs.extrude(height)

        if plane_str == "XZ":
            # manifold (X,Y,Z) → world (X, Z_extrude, Y_sketch)
            y_off = dist if dist < 0 else 0
            solid = solid.transform([
                [1, 0, 0, 0],
                [0, 0, 1, y_off],
                [0, 1, 0, 0],
            ])
        elif plane_str == "YZ":
            # manifold (X,Y,Z) → world (Z_extrude, X_sketch, Y_sketch)
            x_off = dist if dist < 0 else 0
            solid = solid.transform([
                [0, 0, 1, x_off],
                [1, 0, 0, 0],
                [0, 1, 0, 0],
            ])
        elif plane_str and plane_str.startswith("BRepFace"):
            # Can't fully resolve face geometry — leave as XY extrusion
            if dist < 0:
                solid = solid.translate([0, 0, dist])
        else:
            # XY or unknown — extrude along +Z (default)
            if dist < 0:
                solid = solid.translate([0, 0, dist])

        return solid

    def _handle_mirror(self, feat):
        comp = feat.get("component", "root")
        bodies_list = feat.get("bodies", [])
        if not bodies_list or comp not in self.comp_bodies:
            return

        mirror_plane = feat.get("mirrorPlane", "")

        # Determine mirror normal from plane reference
        # Default: mirror across XZ plane (Y-axis normal)
        normal = [0, 1, 0]
        if mirror_plane in ("XY", "xYConstructionPlane"):
            normal = [0, 0, 1]
        elif mirror_plane in ("XZ", "xZConstructionPlane"):
            normal = [0, 1, 0]
        elif mirror_plane in ("YZ", "yZConstructionPlane"):
            normal = [1, 0, 0]
        # Named planes (e.g. "Plane1") — try to find in construction planes
        # For now, default to midpoint mirror approach

        comp_bodies = self.comp_bodies[comp]

        # Mirror creates new bodies. In Fusion, mirror with "Adjust" creates
        # new bodies (listed after originals). Bodies list contains all
        # resulting bodies (originals + mirrors).
        # The first half are originals, second half are mirrors.
        n = len(bodies_list)
        if n >= 2:
            # Assume first half are new mirrored bodies, second half are sources
            # Actually in introspection, bodies lists the result bodies
            # For Mirror, the pattern is: [new_body1, new_body2, source1, source2]
            # or [new_body, source_body]
            half = n // 2
            new_names = bodies_list[:half]
            source_names = bodies_list[half:]
            for new_name, src_name in zip(new_names, source_names):
                if src_name in comp_bodies:
                    mirrored = comp_bodies[src_name].mirror(normal)
                    comp_bodies[new_name] = mirrored
        elif n == 1:
            # Single body mirrored onto itself (union)
            bname = bodies_list[0]
            if bname in comp_bodies:
                mirrored = comp_bodies[bname].mirror(normal)
                try:
                    comp_bodies[bname] = comp_bodies[bname] + mirrored
                except Exception:
                    pass

    def _handle_combine(self, feat):
        comp = feat.get("component", "root")
        operation = feat.get("operation", "Join")
        # Combine features in introspection often lack explicit target/tool
        # references — they operate on bodies within the same component.
        # Without explicit target/tool info, we skip.
        # Future: parse from additional introspection data.
        pass

    def _handle_move(self, feat):
        comp = feat.get("component", "root")
        matrix = feat.get("matrix")
        translation = feat.get("translation")
        bodies_list = feat.get("bodies", [])

        if comp not in self.comp_bodies:
            self._stat("Move", False, "skipped_notgt")
            return

        comp_bodies = self.comp_bodies[comp]
        if not comp_bodies:
            self._stat("Move", False, "skipped_notgt")
            return

        # Determine which bodies to move
        if bodies_list:
            targets = bodies_list
        else:
            move_idx = feat.get("index", 0)
            prev_moves = self.comp_move_count.get(comp, 0)

            if prev_moves == 0 or len(comp_bodies) == 1:
                # First Move in component or single body: move all
                targets = list(comp_bodies.keys())
            else:
                # Subsequent Move with multiple bodies: only move the
                # most recently created body (likely a sub-feature being
                # positioned, not the main body being shifted again).
                recent = None
                recent_idx = -1
                for bname in comp_bodies:
                    idx = self.body_created_at.get((comp, bname), -1)
                    if idx > recent_idx:
                        recent_idx = idx
                        recent = bname
                targets = [recent] if recent else list(comp_bodies.keys())

        self.comp_move_count[comp] = self.comp_move_count.get(comp, 0) + 1

        if matrix:
            # manifold3d transform takes 3x4 matrix
            m3x4 = [matrix[0], matrix[1], matrix[2]]
            for bname in targets:
                if bname in comp_bodies:
                    comp_bodies[bname] = comp_bodies[bname].transform(m3x4)
            self._stat("Move")
        elif translation:
            for bname in targets:
                if bname in comp_bodies:
                    comp_bodies[bname] = comp_bodies[bname].translate(translation)
            self._stat("Move")

    def _handle_pattern(self, feat):
        comp = feat.get("component", "root")
        quantity = int(self.params.ev(feat.get("quantityOne", "1")))
        total_dist = self.params.ev(feat.get("distanceOne", "0"))
        bodies_list = feat.get("bodies", [])
        dist_type = feat.get("distanceType", "Spacing")

        if quantity <= 1 or total_dist == 0:
            return
        if comp not in self.comp_bodies:
            return

        comp_bodies = self.comp_bodies[comp]

        # Determine spacing per copy
        if dist_type == "Extent":
            spacing = total_dist / (quantity - 1) if quantity > 1 else total_dist
        else:
            spacing = total_dist

        # Determine pattern axis from the body's extent
        # Default: pattern along longest dimension of first body's bounding box
        axis = [1, 0, 0]  # default X
        if bodies_list and bodies_list[0] in comp_bodies:
            bb = comp_bodies[bodies_list[0]].bounding_box()
            dx = bb[3] - bb[0]
            dy = bb[4] - bb[1]
            dz = bb[5] - bb[2]
            if dy > dx and dy > dz:
                axis = [0, 1, 0]
            elif dz > dx and dz > dy:
                axis = [0, 0, 1]

        for bname in bodies_list:
            if bname not in comp_bodies:
                continue
            original = comp_bodies[bname]
            result = original
            for i in range(1, quantity):
                offset = [axis[0] * spacing * i,
                          axis[1] * spacing * i,
                          axis[2] * spacing * i]
                copy = original.translate(offset)
                try:
                    result = result + copy
                except Exception:
                    pass
            comp_bodies[bname] = result


# ── Comparator ────────────────────────────────────────────────────


class ComparisonResult:
    __slots__ = ("comp", "body", "status", "gt_vol", "sim_vol",
                 "vol_err", "bb_err", "gt_bb_min", "gt_bb_max",
                 "sim_bb_min", "sim_bb_max")

    def __init__(self, comp, body, status, gt_vol=0, sim_vol=0,
                 vol_err=0, bb_err=0, gt_bb_min=None, gt_bb_max=None,
                 sim_bb_min=None, sim_bb_max=None):
        self.comp = comp
        self.body = body
        self.status = status
        self.gt_vol = gt_vol
        self.sim_vol = sim_vol
        self.vol_err = vol_err
        self.bb_err = bb_err
        self.gt_bb_min = gt_bb_min or [0, 0, 0]
        self.gt_bb_max = gt_bb_max or [0, 0, 0]
        self.sim_bb_min = sim_bb_min or [0, 0, 0]
        self.sim_bb_max = sim_bb_max or [0, 0, 0]


class Comparator:
    """Compare simulated bodies against ground truth from bodies.json."""

    def __init__(self, bodies_data):
        self.expected = {}  # comp_name -> {body_name: {volume, bbMin, bbMax, size}}
        self._flatten(bodies_data.get("components", {}))

    def _flatten(self, comp, parent_name=None):
        """Flatten hierarchical component tree into flat map."""
        name = comp.get("name", "root")
        bodies = comp.get("bodies", [])
        if bodies:
            body_map = {}
            for b in bodies:
                body_map[b["name"]] = {
                    "volume": b.get("volume", 0),
                    "bbMin": b.get("bbMin", [0, 0, 0]),
                    "bbMax": b.get("bbMax", [0, 0, 0]),
                    "size": b.get("size", [0, 0, 0]),
                }
            self.expected[name] = body_map

        for child in comp.get("children", []):
            self._flatten(child, name)

    def compare(self, sim_bodies):
        """Compare simulated bodies against ground truth.
        Returns list of ComparisonResult."""
        results = []
        for comp, bodies in self.expected.items():
            sim_comp = sim_bodies.get(comp, {})
            for body_name, gt in bodies.items():
                sim_body = sim_comp.get(body_name)
                if sim_body is None:
                    results.append(ComparisonResult(
                        comp, body_name, "MISSING", gt_vol=gt["volume"],
                        gt_bb_min=gt["bbMin"], gt_bb_max=gt["bbMax"]))
                    continue

                bb = sim_body.bounding_box()
                sim_vol = sim_body.volume()
                gt_vol = gt["volume"]

                vol_err = abs(sim_vol - gt_vol) / gt_vol if gt_vol > 0 else 0

                sim_min = [bb[0], bb[1], bb[2]]
                sim_max = [bb[3], bb[4], bb[5]]
                gt_min = gt["bbMin"]
                gt_max = gt["bbMax"]

                # Max component-wise error across both min and max corners
                bb_err = max(
                    max(abs(a - b) for a, b in zip(sim_min, gt_min)),
                    max(abs(a - b) for a, b in zip(sim_max, gt_max)),
                )

                if vol_err < 0.05 and bb_err < 0.5:
                    status = "OK"
                else:
                    status = "MISMATCH"

                results.append(ComparisonResult(
                    comp, body_name, status,
                    gt_vol=gt_vol, sim_vol=sim_vol,
                    vol_err=vol_err, bb_err=bb_err,
                    gt_bb_min=gt_min, gt_bb_max=gt_max,
                    sim_bb_min=sim_min, sim_bb_max=sim_max))

        # Check for extra simulated bodies not in ground truth
        for comp, bodies in sim_bodies.items():
            if comp not in self.expected:
                for bname, solid in bodies.items():
                    bb = solid.bounding_box()
                    results.append(ComparisonResult(
                        comp, bname, "EXTRA",
                        sim_vol=solid.volume(),
                        sim_bb_min=[bb[0], bb[1], bb[2]],
                        sim_bb_max=[bb[3], bb[4], bb[5]]))
            else:
                for bname, solid in bodies.items():
                    if bname not in self.expected[comp]:
                        bb = solid.bounding_box()
                        results.append(ComparisonResult(
                            comp, bname, "EXTRA",
                            sim_vol=solid.volume(),
                            sim_bb_min=[bb[0], bb[1], bb[2]],
                            sim_bb_max=[bb[3], bb[4], bb[5]]))

        return results


# ── Report ────────────────────────────────────────────────────────


def print_report(results):
    """Print per-body comparison report to stderr."""
    # Group by component
    by_comp = {}
    for r in results:
        by_comp.setdefault(r.comp, []).append(r)

    ok = mismatch = missing = extra = 0

    for comp in sorted(by_comp.keys()):
        print(f"Component: {comp}", file=sys.stderr)
        for r in sorted(by_comp[comp], key=lambda x: x.body):
            if r.status == "OK":
                ok += 1
                print(f"  {r.body}: OK  vol={r.sim_vol:.1f} "
                      f"(err={r.vol_err:.1%})  bb_err={r.bb_err:.2f}cm",
                      file=sys.stderr)
            elif r.status == "MISMATCH":
                mismatch += 1
                print(f"  {r.body}: MISMATCH  vol={r.sim_vol:.1f} "
                      f"(expected {r.gt_vol:.1f}, err={r.vol_err:.1%})  "
                      f"bb_err={r.bb_err:.2f}cm",
                      file=sys.stderr)
                print(f"    sim_bb: ({r.sim_bb_min[0]:.1f},{r.sim_bb_min[1]:.1f},"
                      f"{r.sim_bb_min[2]:.1f})-({r.sim_bb_max[0]:.1f},"
                      f"{r.sim_bb_max[1]:.1f},{r.sim_bb_max[2]:.1f})",
                      file=sys.stderr)
                print(f"     gt_bb: ({r.gt_bb_min[0]:.1f},{r.gt_bb_min[1]:.1f},"
                      f"{r.gt_bb_min[2]:.1f})-({r.gt_bb_max[0]:.1f},"
                      f"{r.gt_bb_max[1]:.1f},{r.gt_bb_max[2]:.1f})",
                      file=sys.stderr)
            elif r.status == "MISSING":
                missing += 1
                print(f"  {r.body}: MISSING (expected vol={r.gt_vol:.1f})",
                      file=sys.stderr)
            elif r.status == "EXTRA":
                extra += 1
                print(f"  {r.body}: EXTRA (sim vol={r.sim_vol:.1f})",
                      file=sys.stderr)

    total = ok + mismatch + missing
    print(f"\nSUMMARY: {ok}/{total} OK, {mismatch} MISMATCH, "
          f"{missing} MISSING", file=sys.stderr)
    if extra:
        print(f"  (+{extra} EXTRA simulated bodies not in ground truth)",
              file=sys.stderr)
    return mismatch == 0 and missing == 0


def print_body_summary(comp_bodies):
    """Print summary of all simulated bodies (no ground truth needed)."""
    total = 0
    for comp in sorted(comp_bodies.keys()):
        bodies = comp_bodies[comp]
        if not bodies:
            continue
        print(f"Component: {comp}", file=sys.stderr)
        for bname in sorted(bodies.keys()):
            solid = bodies[bname]
            bb = solid.bounding_box()
            size = [bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2]]
            print(f"  {bname}: vol={solid.volume():.1f}  "
                  f"size=({size[0]:.1f}, {size[1]:.1f}, {size[2]:.1f})",
                  file=sys.stderr)
            total += 1
    print(f"\nTotal: {total} bodies simulated", file=sys.stderr)


# ── CLI ───────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Headless 3D geometry simulator for Fusion 360 designs")
    parser.add_argument("introspect", help="Introspection JSON file")
    parser.add_argument("--bodies", help="Bodies ground truth JSON file")
    parser.add_argument("--verbose", action="store_true",
                        help="Print body state after each geometry feature")
    args = parser.parse_args()

    # Load introspection data
    with open(args.introspect) as f:
        data = json.load(f)

    # Resolve parameters
    params = ParamResolver(data.get("userParameters", []))

    # Run simulation
    sim = Simulator(data, params)
    sim.verbose = args.verbose
    comp_bodies = sim.run()

    # Print feature statistics
    st = sim.stats
    print(f"\nFeatures: {st['applied']} applied, "
          f"{st.get('skipped_err',0)} skipped(sketchError), "
          f"{st.get('skipped_nosk',0)} skipped(noSketch), "
          f"{st.get('skipped_nocs',0)} skipped(noCrossSection), "
          f"{st.get('skipped_notgt',0)} skipped(noTarget)",
          file=sys.stderr)
    for ftype in sorted(st["by_type"]):
        t = st["by_type"][ftype]
        print(f"  {ftype}: {t['applied']} applied, {t['skipped']} skipped",
              file=sys.stderr)

    # Compare or summarize
    if args.bodies:
        with open(args.bodies) as f:
            bodies_data = json.load(f)
        comparator = Comparator(bodies_data)
        results = comparator.compare(comp_bodies)
        all_ok = print_report(results)
        sys.exit(0 if all_ok else 1)
    else:
        print_body_summary(comp_bodies)


if __name__ == "__main__":
    main()
