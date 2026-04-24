"""Shared sketch helper for dovetail templates.

Half-blind and through dovetails differ only in the depth of tail
penetration into the pin board:
  - through:    tails span the full pin thickness (lap = 0)
  - half-blind: tails stop short of the outer face by ``lap``

The 4-line trapezoid sketch itself is identical — same short-face anchor,
same flank angular constraint, same line order. This module houses the
shared sketch function so fixes propagate to both templates.
"""

import adsk.core
import adsk.fusion

from helpers import sp

Point3D = adsk.core.Point3D
H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation


def trapezoid_sketch(comp, plane, m1_pt, m2_pt, m3_pt, m4_pt,
                     thick_expr, short_joint_expr, short_base_expr,
                     prefix, name, narrow_w_expr=None):
    """Shared dovetail trapezoid sketch (through + half-blind + houndstooth).

    The four model-space corner points define the trapezoid:
      m1 = wide-side joint-low corner    (outer face for through,
                                          socket bottom for half-blind)
      m2 = wide-side joint-high corner
      m3 = narrow-side joint-high corner - delta
      m4 = narrow-side joint-low corner  + delta
    where delta = thick_expr * tan({prefix}_angle).

    Args:
        comp: Component owning the sketch.
        plane: Construction plane or BRepFace to sketch on.
        m1_pt..m4_pt: Point3D corners in model space.
        thick_expr: Depth between wide and narrow faces (board_thick
            for through, socket_depth for half-blind, ht_depth for
            houndstooth void).
        short_joint_expr: origin → short-face low endpoint, joint axis.
        short_base_expr:  origin → short-face low endpoint, thickness axis.
        prefix: Parameter prefix (e.g. "dt"). References
            ``{prefix}_angle`` for the flank angular dim.
        name: Sketch name prefix (sketch will be named ``{name}_Sk``).
        narrow_w_expr: Expression for the short face length. Defaults
            to ``{prefix}_narrow_w``. Override for a secondary (e.g.
            houndstooth void) trapezoid that shares the main angle but
            has its own narrow width.

    Returns:
        The smallest profile in the sketch.
    """
    if narrow_w_expr is None:
        narrow_w_expr = f"{prefix}_narrow_w"
    p = prefix
    sk = comp.sketches.add(plane)
    sk.name = f"{name}_Sk"
    m = sk.modelToSketchSpace

    m1 = m(m1_pt)
    m2 = m(m2_pt)
    m3 = m(m3_pt)
    m4 = m(m4_pt)

    # Line order: short (P4→P3), back (P3→P2), wide (P2→P1), front (P1→P4).
    lines = sk.sketchCurves.sketchLines
    l_short = lines.addByTwoPoints(
        Point3D.create(m4.x, m4.y, 0), Point3D.create(m3.x, m3.y, 0))
    l_back = lines.addByTwoPoints(
        l_short.endSketchPoint, Point3D.create(m2.x, m2.y, 0))
    l_wide = lines.addByTwoPoints(
        l_back.endSketchPoint, Point3D.create(m1.x, m1.y, 0))
    l_front = lines.addByTwoPoints(
        l_wide.endSketchPoint, l_short.startSketchPoint)

    joint_is_sketch_h = abs(m3.x - m4.x) > abs(m3.y - m4.y)

    gc = sk.geometricConstraints
    if joint_is_sketch_h:
        gc.addHorizontal(l_short)
        gc.addHorizontal(l_wide)
    else:
        gc.addVertical(l_short)
        gc.addVertical(l_wide)

    JOINT_DIM = H if joint_is_sketch_h else V
    THICK_DIM = V if joint_is_sketch_h else H

    d = sk.sketchDimensions
    # Dim 1: short face length = narrow_w (or overridden for houndstooth void).
    d.addDistanceDimension(
        l_short.startSketchPoint, l_short.endSketchPoint,
        JOINT_DIM, Point3D.create(m4.x + 0.5, (m4.y + m3.y) / 2, 0)
    ).parameter.expression = narrow_w_expr
    # Dim 2: wide ↔ short face separation = tail penetration depth.
    d.addDistanceDimension(
        l_short.startSketchPoint, l_wide.endSketchPoint,
        THICK_DIM, Point3D.create((m1.x + m4.x) / 2, (m1.y + m4.y) / 2, 0)
    ).parameter.expression = thick_expr
    # Dim 3: origin → short-face low endpoint, joint axis.
    d.addDistanceDimension(
        sk.originPoint, l_short.startSketchPoint,
        JOINT_DIM, Point3D.create(m4.x + 1, m4.y / 2, 0)
    ).parameter.expression = short_joint_expr
    # Dim 4: origin → short-face low endpoint, thickness axis.
    d.addDistanceDimension(
        sk.originPoint, l_short.startSketchPoint,
        THICK_DIM, Point3D.create(m4.x / 2, m4.y + 1, 0)
    ).parameter.expression = short_base_expr
    # Dim 5: flank angle — measured at base (narrow/short face).
    d.addAngularDimension(
        l_front, l_short,
        Point3D.create((m1.x + m4.x) / 2, (m1.y + m4.y) / 2, 0)
    ).parameter.expression = f"90 deg - {p}_angle"

    return sp.smallest_profile(sk)
