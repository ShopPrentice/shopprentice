"""
ShopPrentice Runtime Helpers

Shared utilities for Fusion 360 scripts executed via execute_script.
Import with: from helpers import sp

All functions accept explicit objects (body, sketch, component) rather than
relying on module-level globals, so they work in both normal and sandbox mode.
"""

# Re-export everything so `from helpers import sp; sp.ext_new(...)` works unchanged.
from helpers.sp._util import *
# `import *` skips underscore names, but many templates (and the anchored
# trapezoid path) call `sp._make_ev()` — export it explicitly.
from helpers.sp._util import _make_ev
from helpers.sp.context import *
from helpers.sp.faces import *
from helpers.sp.sketch import *
from helpers.sp.sketch_slot import *
from helpers.sp.anchoring import *
from helpers.sp.features import *
from helpers.sp.spatial import *
from helpers.sp.mating import *
from helpers.sp.appearance import *
from helpers.sp.camera import *
from helpers.sp.deps import *

# Module-level constants that were in the original sp.py
import adsk.core
import adsk.fusion

Point3D = adsk.core.Point3D
H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
