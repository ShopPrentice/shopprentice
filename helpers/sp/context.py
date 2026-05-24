import adsk.core
import adsk.fusion

from ._util import _find_body_recursive, _collect_bodies_recursive


class DesignContext:
    """Replaces the 5-line boilerplate at the top of every script.

    Usage:
        ctx = sp.DesignContext()
        depth = ctx.ev("shelf_depth")
        shelf = ctx.find_body("shelf_top")
    """

    def __init__(self, design=None):
        self.app = adsk.core.Application.get()
        self.design = design or adsk.fusion.Design.cast(self.app.activeProduct)
        self.root = self.design.rootComponent
        self.params = self.design.userParameters
        self.units = self.design.unitsManager

    def ev(self, expr):
        """Evaluate parameter name or expression string to float (cm).

        Also accepts int/float (returned as-is, assumed cm).
        """
        if isinstance(expr, (int, float)):
            return float(expr)
        p = self.params.itemByName(expr)
        return p.value if p else self.units.evaluateExpression(expr, "cm")

    def find_body(self, name, component=None):
        """Find body by exact name. Walks all descendants if component is None."""
        comp = component or self.root
        return _find_body_recursive(comp, name)

    def find_bodies(self, pattern, component=None):
        """Find all bodies matching glob pattern. Walks all descendants."""
        import fnmatch
        comp = component or self.root
        results = []
        _collect_bodies_recursive(comp, pattern, results)
        return results
