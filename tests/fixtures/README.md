# Round-Trip Test Fixtures

## How to Write a Fixture

Each fixture is a standalone Fusion 360 script that creates a minimal design exercising
one or two feature types. The round-trip harness runs:

```
fixture → capture_design → export_script → execute(clean) → capture_design → compare volumes
```

### Template

```python
"""Fixture: <what it tests>.

<One-line description of the feature combinations being exercised.>
"""
import adsk.core, adsk.fusion


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters

    P = adsk.core.Point3D.create
    NEWBODY = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    # 1. Add parameters (always use expressions, never hardcode dimensions)
    params.add("my_param", adsk.core.ValueInput.createByString("10 cm"), "cm", "Description")

    # 2. Helper to evaluate parameter values for sketch positioning
    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                     else design.unitsManager.evaluateExpression(e, "cm"))

    # 3. Create sketch with explicit H/V constraints and parametric dimensions
    sk = root.sketches.add(root.xYConstructionPlane)
    sk.name = "MySketch"
    # ... add curves, constraints, dimensions ...

    # 4. Create features (extrude, sweep, etc.)
    # ... always name features and bodies ...

    # 5. Fit view
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
```

### Rules

1. **Name everything** — `sk.name`, `ext.name`, `body.name`. The export pipeline
   tracks entities by name; unnamed bodies get auto-names that don't round-trip.

2. **Use parametric expressions** — Dimension values should reference user parameters
   (`"my_width"`) not literals (`"10 cm"`). The test verifies that parametric expressions
   survive the round-trip.

3. **Use explicit constraints** — `addHorizontal`/`addVertical` on rectangle lines,
   `addCoincident` for shared points. Without these, Fusion may not preserve the
   intended geometry under parameter changes.

4. **Keep it minimal** — Each fixture should isolate one or two feature types.
   A fixture with 3 extrudes, a mirror, 2 combines, and a fillet tests everything
   and debugs nothing. Split into separate fixtures.

5. **Non-default properties** — Use taper angles, direction flips, symmetric extents,
   keepTool=True, etc. The default/happy path usually works; it's the non-default
   properties that break.

6. **File naming** — `fixture_<feature_type>.py`. The harness auto-discovers files
   matching `fixture_*.py`.

### Debugging a Failure

When a fixture fails, the harness saves the generated script to
`tests/fixtures/fixture_<name>_FAILED.py`. To debug:

1. Read the FAILED script — is the generated code correct?
2. Execute it in sandbox mode for a full traceback:
   ```
   curl -s -X POST http://localhost:9100 \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
          "params":{"name":"execute_script",
                    "arguments":{"script":"...","clean":true,"sandbox":true}}}'
   ```
3. Check the capture JSON — is the feature data complete?
   ```
   curl ... capture_design | python3 -c "import sys,json; ..."
   ```
4. Fix the capture (`_capture_helpers.py`) or generator (`_script_generator.py`)
5. Restart the add-in (both files run inside Fusion's Python process)
6. Re-run: `python3 tests/test_round_trip.py fixture_<name>`

### Running Tests

```bash
python3 tests/test_round_trip.py                     # all fixtures
python3 tests/test_round_trip.py fixture_extrude     # one fixture
python3 tests/test_round_trip.py extrude sweep       # multiple (prefix optional)
python3 tests/test_round_trip.py -v                  # verbose (show generated script)
python3 tests/test_round_trip.py --list              # list available fixtures
```
