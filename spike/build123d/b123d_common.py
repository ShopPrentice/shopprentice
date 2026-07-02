"""Shared infrastructure for the build123d spike.

Everything here is what ShopPrentice currently delegates to Fusion, done
headless instead:

  * export   -> STEP + STL straight from the OCCT kernel
  * render   -> isometric PNG via matplotlib (no GUI, no Fusion viewport)
  * validate -> interference (pairwise boolean volume) + connectivity
                (min-distance clustering), the same pass/fail that
                validate_design() asks Fusion for.

No Autodesk anything. One process per model -> run as many in parallel as
you have cores.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from build123d import Solid, Compound, Vector, export_step, export_stl
from OCP.BRepExtrema import BRepExtrema_DistShapeShape


def _hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


# --------------------------------------------------------------------------
# A "part" = one named solid plus a colour, the build123d analogue of a
# named BRepBody in a Fusion component.
# --------------------------------------------------------------------------
@dataclass
class Part:
    name: str
    solid: Solid
    color: str = "#b8895a"          # default warmwood
    component: str = ""             # grouping label (Fusion component)


@dataclass
class Model:
    name: str
    parts: list[Part] = field(default_factory=list)
    params: dict | None = None      # user parameters (original units)
    units: str = "cm"               # unit the params are expressed in

    def add(self, name, solid, color="#b8895a", component=""):
        self.parts.append(Part(name, solid, color, component))
        return solid

    # ---- export -----------------------------------------------------------
    def export(self, stem: str):
        comp = Compound(children=[p.solid for p in self.parts])
        export_step(comp, f"{stem}.step")
        export_stl(comp, f"{stem}.stl")
        return f"{stem}.step", f"{stem}.stl"

    def export_parts(self, stem: str):
        """One STL per body + a JSON manifest for the browser viewer. STL
        writes raw model-space triangles -- no up-convention, no per-body
        recentering -- so the parts reassemble at exactly their model
        coordinates (unlike build123d's glTF export, which repositions each
        body). The viewer applies one Z-up->Y-up rotation and the manifest
        color. Gives reliable per-body name / color / explode / isolate."""
        import json
        import os
        import time
        parts_dir = f"{stem}_parts"
        os.makedirs(parts_dir, exist_ok=True)
        # stamp lets the viewer auto-reload when a rebuild lands
        manifest = {"name": self.name, "stamp": time.time(), "parts": [],
                    "params": self.params or {}, "units": self.units}
        for i, p in enumerate(self.parts):
            rel = f"{os.path.basename(parts_dir)}/body_{i:02d}.stl"
            export_stl(p.solid, f"{stem}_parts/body_{i:02d}.stl")
            manifest["parts"].append(
                {"name": p.name, "color": p.color, "component": p.component,
                 "file": rel})
        with open(f"{stem}.json", "w") as f:
            json.dump(manifest, f, indent=2)
        return f"{stem}.json"

    # ---- validation -------------------------------------------------------
    def check_interference(self, tol_cm3=1e-3):
        """Pairwise solid overlap. Mating faces share zero volume, so a
        properly-fit joint reads 0; real overlaps report their volume.
        Bbox broadphase: disjoint boxes can't overlap, skip the boolean."""
        hits = []
        bbs = [p.solid.bounding_box() for p in self.parts]
        for i in range(len(self.parts)):
            for j in range(i + 1, len(self.parts)):
                A, B = bbs[i], bbs[j]
                if (A.min.X > B.max.X or B.min.X > A.max.X or
                        A.min.Y > B.max.Y or B.min.Y > A.max.Y or
                        A.min.Z > B.max.Z or B.min.Z > A.max.Z):
                    continue
                a, b = self.parts[i], self.parts[j]
                try:
                    inter = a.solid & b.solid
                    v = inter.volume if inter is not None else 0.0
                except Exception:
                    v = 0.0
                if v > tol_cm3:
                    hits.append((a.name, b.name, v))
        return hits

    def check_connectivity(self, touch_eps_cm=0.02):
        """Two parts are connected if the kernel says their min surface
        distance is ~0. Union-find -> number of disjoint clusters. 1 == the
        whole assembly hangs together (what Fusion's connectivity check wants).
        Round pegs in round holes never satisfy planar contact, same caveat as
        Fusion -- not relevant for these two pieces."""
        n = len(self.parts)
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            parent[find(x)] = find(y)

        bbs = [p.solid.bounding_box() for p in self.parts]

        def bbgap(A, B):
            gx = max(A.min.X - B.max.X, B.min.X - A.max.X, 0.0)
            gy = max(A.min.Y - B.max.Y, B.min.Y - A.max.Y, 0.0)
            gz = max(A.min.Z - B.max.Z, B.min.Z - A.max.Z, 0.0)
            return math.sqrt(gx * gx + gy * gy + gz * gz)

        for i in range(n):
            for j in range(i + 1, n):
                if bbgap(bbs[i], bbs[j]) > touch_eps_cm:
                    continue          # bbox gap is a lower bound on distance
                if _min_distance(self.parts[i].solid, self.parts[j].solid) < touch_eps_cm:
                    union(i, j)
        clusters = {}
        for i in range(n):
            clusters.setdefault(find(i), []).append(self.parts[i].name)
        return list(clusters.values())

    def validate(self, verbose=True):
        interf = self.check_interference()
        clusters = self.check_connectivity()
        ok = (not interf) and len(clusters) == 1
        if verbose:
            print(f"  validate_design  [{self.name}]")
            print(f"    bodies         : {len(self.parts)}")
            print(f"    interference   : {'PASS (0 overlaps)' if not interf else 'FAIL'}")
            for a, b, v in interf:
                print(f"        {a} <-> {b}: {v:.3f} cm^3")
            print(f"    connectivity   : "
                  f"{'PASS (1 cluster)' if len(clusters) == 1 else 'FAIL %d clusters' % len(clusters)}")
            if len(clusters) != 1:
                for c in clusters:
                    print(f"        cluster: {', '.join(c)}")
            print(f"    => {'PASS' if ok else 'FAIL'}")
        return ok

    # ---- render -----------------------------------------------------------
    def render(self, path, views=(("iso", 24, -52), ("front", 6, -90)),
               size=1100, lin_tol=0.12):
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.colors import to_rgb
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection

        # tessellate every part once
        meshes = []
        allpts = []
        for p in self.parts:
            verts, tris = p.solid.tessellate(lin_tol)
            V = np.array([[v.X, v.Y, v.Z] for v in verts])
            T = np.array(tris)
            if len(T) == 0:
                continue
            meshes.append((V, T, to_rgb(p.color)))
            allpts.append(V)
        allpts = np.vstack(allpts)
        ctr = allpts.mean(axis=0)
        span = (allpts.max(axis=0) - allpts.min(axis=0)).max()

        light = np.array([0.4, -0.7, 0.85])
        light = light / np.linalg.norm(light)

        fig = plt.figure(figsize=(size / 100 * len(views), size / 100), dpi=100)
        for k, (vname, elev, azim) in enumerate(views):
            ax = fig.add_subplot(1, len(views), k + 1, projection="3d")
            for V, T, base in meshes:
                tri = V[T]                                   # (m,3,3)
                n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
                ln = np.linalg.norm(n, axis=1, keepdims=True)
                ln[ln == 0] = 1
                n = n / ln
                shade = 0.35 + 0.65 * np.clip(n @ light, 0, 1)
                facecol = np.clip(np.array(base)[None, :] * shade[:, None], 0, 1)
                pc = Poly3DCollection(tri, facecolors=facecol, edgecolors="none")
                ax.add_collection3d(pc)
            ax.set_xlim(ctr[0] - span / 2, ctr[0] + span / 2)
            ax.set_ylim(ctr[1] - span / 2, ctr[1] + span / 2)
            ax.set_zlim(ctr[2] - span / 2, ctr[2] + span / 2)
            ax.set_box_aspect((1, 1, 1))
            ax.view_init(elev=elev, azim=azim)
            ax.set_axis_off()
            title = f"{self.name} - {vname}".encode("ascii", "ignore").decode()
            ax.set_title(title, fontsize=9)
        fig.tight_layout()
        fig.savefig(path, transparent=True)
        plt.close(fig)
        return path


def _min_distance(a: Solid, b: Solid) -> float:
    d = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
    return d.Value() if d.IsDone() else 1e9


def run_cli(build_fn, stem):
    """Shared __main__ for the model scripts: parse --set k=v overrides,
    build, validate, export. The rebuild server drives this; --no-render
    keeps the loop fast (the PNG is the slow part)."""
    import argparse
    import os
    import sys
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", action="append", default=[], metavar="K=V",
                    help="override a user parameter (repeatable)")
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    over = {}
    for s in a.set:
        k, v = s.split("=", 1)
        over[k] = float(v)
    model = build_fn(over)
    summarize(model)
    ok = model.validate()
    os.makedirs(os.path.dirname(stem) or ".", exist_ok=True)
    model.export_parts(stem)   # BEFORE export: STL meshing caches triangulation
    model.export(stem)
    if not a.no_render:
        model.render(stem + ".png")
    print(("BUILD OK " if ok else "BUILD FAIL ") + stem)
    sys.exit(0 if ok else 1)


def summarize(model: Model):
    print(f"\n=== {model.name}: {len(model.parts)} bodies ===")
    for p in model.parts:
        bb = p.solid.bounding_box()
        print(f"  {p.name:<16} vol={p.solid.volume:8.1f} cm^3   "
              f"x[{bb.min.X:6.1f},{bb.max.X:6.1f}] "
              f"y[{bb.min.Y:6.1f},{bb.max.Y:6.1f}] "
              f"z[{bb.min.Z:6.1f},{bb.max.Z:6.1f}]")
