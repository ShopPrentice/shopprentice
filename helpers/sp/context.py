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


# ── Standalone body lookups (no DesignContext instance needed) ───────────────
# These are the ONE site for raw `bRepBodies` iteration / name-based body
# identification. Templates call these instead of rolling their own
# `_all_bodies`/`_find_body` loops, so the fragile bits (name collisions after
# mirror/pattern renames, proxy vs native) live in a single hardenable place.

def bodies_in(comp, recursive=False):
    """All bodies in a component. Shallow by default (the component's own
    bodies — matches the old per-template `_all_bodies`); pass recursive=True to
    walk descendants."""
    if recursive:
        out = []
        _collect_bodies_recursive(comp, "*", out)
        return out
    return [comp.bRepBodies.item(i) for i in range(comp.bRepBodies.count)]


def find_body(name, comp):
    """Find a body by exact name within `comp` (checks the component's own
    bodies first, then descendants). Canonical replacement for local
    `_find_body` helpers."""
    return _find_body_recursive(comp, name)


def find_bodies(pattern, comp):
    """Bodies whose name matches a glob `pattern` within `comp` (walks
    descendants)."""
    out = []
    _collect_bodies_recursive(comp, pattern, out)
    return out
