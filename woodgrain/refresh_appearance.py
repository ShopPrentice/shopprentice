"""Force-reload sp module and re-apply custom wood appearance.
Run via execute_script to test new larger textures."""
import adsk.core
import adsk.fusion
import sys

def run(context):
    # Force reload of helpers.sp so it picks up the new texture config
    for key in list(sys.modules.keys()):
        if key.startswith('helpers'):
            del sys.modules[key]

    from helpers import sp

    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent

    # Detect which SP_ appearance is currently in use
    species = None
    for i in range(design.appearances.count):
        a = design.appearances.item(i)
        name = a.name
        if name.startswith("SP_") and not name.endswith("_endgrain"):
            # Extract species from "SP_teak" -> "teak"
            species = name[3:]
            break

    if not species:
        # Check body appearances for standard library names
        species = "white oak"  # fallback default
        print("No SP_ appearance found, defaulting to white oak")
    else:
        print(f"Detected custom species: {species}")

    # Re-apply — the updated sp.apply_appearance always refreshes textures
    sp.apply_appearance(species)

    # Fit view
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam

    print(f"Done — re-applied {species} with new textures")
