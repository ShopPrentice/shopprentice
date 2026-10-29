"""
Catalog Hinges + Wood Screws — Our Own STEP Files
=================================================
Builds the STEP files under hardware/ for the catalog's brass butt hinges
(ids 1603a2, 1603a3, 1603a7) and their flat head wood screws (92114a079,
92114a196) from published sizes in hardware/catalog.json. No vendor CAD is
used: McMaster-Carr's terms forbid redistributing theirs, so the catalog
keeps their part numbers only as a buy-as reference.

Run from the repo root (needs build123d, not Fusion 360):

    pip install build123d
    python dev/make_hardware_steps.py

Each file is written in the same frame and with the same body layout the
helpers/hardware.py importer expects:

    hinges/<file>       2 leaves + pin, open flat
    assemblies/<file>   2 leaves + pin + screws (flat, one product)
    screws/<file>       1 screw, axis along +X, head top at X = 0

STANDARD HINGE FRAME (mm in the file, cm once Fusion imports it):
    Pin along X, leaves in the XZ plane, thin in Y, barrel centred at origin.
    leaf_a = +Z side, leaf_b = -Z side. Each plate's screw side lies at
    Y = -barrel_d/2 and its show face plate_t inside that; the screws run
    from the show face into the wood along -Y, their flat heads seated flush
    in countersinks through the plate.

Volumes are ordered so the importer's classification holds: the 2 leaves
are the largest bodies, the pin the 3rd, the screws the rest. The script
checks that, and that no two bodies overlap, before it writes anything.
"""
import json
import math
import os
import sys

from build123d import Axis, Face, Location, Solid, Vector, Wire
from OCP.BRep import BRep_Builder
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.TopoDS import TopoDS_Compound
from OCP.XCAFDoc import XCAFDoc_DocumentTool

IN = 25.4                  # mm per inch
CLEAR = 0.05               # mm between the two leaves' knuckles
CSK_HALF = 41.0            # degrees: 82-degree flat head countersink

# gauge -> (major diameter in, threads per inch)
WOOD_SCREW_GAUGES = {2: (0.086, 26), 4: (0.112, 22), 6: (0.138, 18),
                     8: (0.164, 15), 10: (0.190, 13), 12: (0.216, 11),
                     14: (0.242, 10)}

HERE = os.path.dirname(os.path.abspath(__file__))
HARDWARE_DIR = os.path.join(os.path.dirname(HERE), "hardware")


def parse_in(s):
    """'0.375 in' -> mm."""
    v, unit = str(s).split()
    assert unit == "in", s
    return float(v) * IN


def box(x0, x1, y0, y1, z0, z1):
    return Solid.make_box(x1 - x0, y1 - y0, z1 - z0).moved(
        Location((x0, y0, z0)))


def cyl_x(x0, x1, r):
    return Solid.make_cylinder(r, x1 - x0).moved(
        Location((x0, 0, 0), (0, 1, 0), 90))


def one(shape, what):
    solids = shape.solids()
    if len(solids) != 1:
        sys.exit("%s came out as %d pieces" % (what, len(solids)))
    return solids[0]


def head_dims(gauge):
    """(major_r, head_r, head_h) in mm for an 82-degree flat head."""
    d_in, _ = WOOD_SCREW_GAUGES[gauge]
    r = d_in * IN / 2.0
    rh = 2.0 * r
    return r, rh, (rh - r) / math.tan(math.radians(CSK_HALF))


def wood_screw(gauge, length_mm):
    """Flat head wood screw revolved from its profile: head, a run of thread
    crests (rings, so it stays light), a gimlet point, and a Phillips recess.
    Overall length as screws are sold. Axis +X, head top at X = 0."""
    _, tpi = WOOD_SCREW_GAUGES[gauge]
    r, rh, hh = head_dims(gauge)
    pitch = IN / tpi
    root = 0.6 * r
    L = length_mm
    tip = 2.2 * r
    pts = [(0.0, 0.0), (0.0, rh), (hh, r)]
    x = hh + (0.35 * (L - hh) if L > IN else 0.0)   # plain shank on long ones
    pts.append((x, r))
    while x + pitch < L - tip:
        pts += [(x + 0.5 * pitch, root), (x + pitch, r)]
        x += pitch
    pts += [(L - tip, 0.9 * r), (L, 0.02), (L, 0.0)]
    wire = Wire.make_polygon([Vector(a, b, 0) for a, b in pts], close=True)
    s = Solid.revolve(Face(wire), 360, Axis.X)
    cw, cl, dp = 0.22 * rh, 1.1 * rh, min(0.7 * hh, 0.9 * r)
    s = s - box(-0.01, dp, -cl / 2, cl / 2, -cw / 2, cw / 2)
    s = s - box(-0.01, dp, -cw / 2, cw / 2, -cl / 2, cl / 2)
    return one(s, "#%d screw" % gauge)


def countersink(u, y_top, v, rh, depth):
    """Cone along -Y from radius rh at y_top, at the screw head's angle."""
    r_bot = rh - depth * math.tan(math.radians(CSK_HALF))
    c = Solid.make_cone(rh, r_bot, depth)          # along +Z from z=0
    return c.moved(Location((u, y_top, v), (1, 0, 0), 90))  # +Z -> -Y


def butt_hinge(L, W, rb, pt, pr, knuckles, holes, gauge, screw_len):
    """Returns (leaf_a, leaf_b, pin, screws) in the standard frame (mm)."""
    if pt >= rb * 2 or pr >= rb:
        sys.exit("plate and pin must be thinner than the barrel")
    n = int(knuckles)
    seg = L / n
    y_show = -rb + pt
    us = ([0.0] if holes == 1 else
          [-0.31 * L, 0.31 * L] if holes == 2 else
          [-0.36 * L, 0.0, 0.36 * L])
    r, rh, _ = head_dims(gauge)
    leaves, screws = [], []
    for side, first in ((1.0, 0), (-1.0, 1)):
        z0, z1 = sorted((0.0, side * W))
        plate = box(-L / 2, L / 2, -rb, y_show, z0, z1) - cyl_x(
            -L / 2 - 1, L / 2 + 1, rb + CLEAR)
        parts = [plate]
        for i in range(first, n, 2):
            a = -L / 2 + i * seg + (CLEAR / 2 if i > 0 else 0.0)
            b = -L / 2 + (i + 1) * seg - (CLEAR / 2 if i < n - 1 else 0.0)
            parts.append(cyl_x(a, b, rb))
            # web joining the plate to its own knuckle
            wz = sorted((0.0, side * (rb + 2 * CLEAR)))
            parts.append(box(a, b, -rb, y_show, *wz))
        leaf = parts[0]
        for p in parts[1:]:
            leaf = leaf + p
        leaf = leaf - cyl_x(-L / 2 - 1, L / 2 + 1, pr)
        v = side * 0.62 * W
        for u in us:
            leaf = leaf - countersink(u, y_show + 0.01, v, rh + 0.01 * math.tan(
                math.radians(CSK_HALF)), pt + 0.03)
            s = wood_screw(gauge, screw_len)
            # native +X -> -Y, head top on the show face
            s = s.moved(Location((u, y_show, v), (0, 0, 1), -90))
            screws.append(s)
        leaves.append(one(leaf, "hinge leaf"))
    pin = cyl_x(-L / 2, L / 2, pr)
    return leaves[0], leaves[1], pin, screws


def check(solids, what):
    vols = [s.volume for s in solids]
    hinge, screws = vols[:3], vols[3:]
    if screws and min(hinge) < 1.15 * max(screws):
        sys.exit("%s: a screw is too close in volume to the pin" % what)
    if min(vols[:2]) < 1.15 * vols[2]:
        sys.exit("%s: the pin is too close in volume to a leaf" % what)
    for i in range(len(solids)):
        for j in range(i + 1, len(solids)):
            common = solids[i].intersect(solids[j])
            if common is not None and common.volume > 1e-4:
                sys.exit("%s: bodies %d and %d overlap (%.4f mm3)"
                         % (what, i, j, common.volume))


def write_step(solids, path, name):
    """All solids as bodies of ONE named product (no sub-assemblies), in mm,
    the way the importer reads a flat assembly."""
    comp = TopoDS_Compound()
    bld = BRep_Builder()
    bld.MakeCompound(comp)
    for s in solids:
        bld.Add(comp, s.wrapped)
    doc = TDocStd_Document(TCollection_ExtendedString("doc"))
    tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    label = tool.AddShape(comp, False)          # one shape, not an assembly
    TDataStd_Name.Set_s(label, TCollection_ExtendedString(name))
    w = STEPCAFControl_Writer()
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    Interface_Static.SetCVal_s("write.step.schema", "AP214IS")
    Interface_Static.SetIVal_s("write.step.assembly", 0)
    if not w.Transfer(doc, STEPControl_AsIs) or w.Write(path) != IFSelect_RetDone:
        sys.exit("could not write " + path)


def main():
    with open(os.path.join(HARDWARE_DIR, "catalog.json")) as f:
        parts = json.load(f)["parts"]
    for pid, p in parts.items():
        if p.get("category") != "screw" or not p.get("step_file"):
            continue
        d = p["dimensions"]
        g = int(d["screw_size"].lstrip("#"))
        s = wood_screw(g, parse_in(d["length"]))
        write_step([s], os.path.join(HARDWARE_DIR, p["step_file"]), p["name"])
        print("%-10s %s" % (pid, p["step_file"]))
    for pid, p in parts.items():
        if p.get("category") != "hinge" or not p.get("step_file"):
            continue
        d = p["dimensions"]
        sd = parts[p["screw"]]["dimensions"]
        a, b, pin, screws = butt_hinge(
            parse_in(d["length"]), parse_in(d["leaf_width"]),
            parse_in(d["leaf_thickness"]) / 2, parse_in(d["plate_thickness"]),
            parse_in(d["pin_diameter"]) / 2, d["knuckles"],
            d["holes_per_leaf"], int(sd["screw_size"].lstrip("#")),
            parse_in(sd["length"]))
        check([a, b, pin] + screws, pid)
        write_step([a, b, pin], os.path.join(HARDWARE_DIR, p["step_file"]),
                   p["name"])
        write_step([a, b, pin] + screws,
                   os.path.join(HARDWARE_DIR, p["assembly_step"]),
                   p["name"] + " with screws")
        print("%-10s %s, %s (%d screws)" % (pid, p["step_file"],
                                            p["assembly_step"], len(screws)))


if __name__ == "__main__":
    main()
