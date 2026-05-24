import adsk.core
import adsk.fusion


def _make_ev():
    """Create an ev() function from the active design."""
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    params = design.userParameters
    units = design.unitsManager

    def ev(expr):
        p = params.itemByName(expr)
        return p.value if p else units.evaluateExpression(expr, "cm")
    return ev


def _find_body_recursive(comp, name):
    """Walk component tree to find body by exact name."""
    for i in range(comp.bRepBodies.count):
        body = comp.bRepBodies.item(i)
        if body.name == name:
            return body
    for occ in comp.occurrences:
        result = _find_body_recursive(occ.component, name)
        if result:
            return result
    return None


def _collect_bodies_recursive(comp, pattern, results):
    """Walk component tree to find bodies matching glob pattern."""
    import fnmatch
    for i in range(comp.bRepBodies.count):
        body = comp.bRepBodies.item(i)
        if fnmatch.fnmatch(body.name, pattern):
            results.append(body)
    for occ in comp.occurrences:
        _collect_bodies_recursive(occ.component, pattern, results)
