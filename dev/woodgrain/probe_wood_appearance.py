"""Probe Wood Appearance Properties

Run this in Fusion 360 to dump the full property tree of wood appearances.
This confirms the exact API path for swapping texture images.

Usage: execute_script with this file, or paste into the Script Editor.
Output goes to the Text Commands palette (View > Text Commands).
"""

import adsk.core
import adsk.fusion
import traceback


def prop_type_name(prop):
    """Return a short human-readable type name for an appearance property."""
    type_map = {
        "adsk::core::ColorProperty": "Color",
        "adsk::core::FloatProperty": "Float",
        "adsk::core::IntegerProperty": "Integer",
        "adsk::core::BooleanProperty": "Boolean",
        "adsk::core::StringProperty": "String",
        "adsk::core::ChoiceProperty": "Choice",
        "adsk::core::AppearanceTextureProperty": "Texture",
    }
    return type_map.get(prop.objectType, prop.objectType)


def dump_color_property(prop, indent, lines):
    """Dump a ColorProperty including connected texture info."""
    cp = adsk.core.ColorProperty.cast(prop)
    if not cp:
        return

    # Get color values
    try:
        vals = cp.values
        if vals and len(vals) > 0:
            c = vals[0]
            lines.append(f"{indent}  color: R{c.red} G{c.green} B{c.blue} A{c.opacity}")
    except Exception as e:
        lines.append(f"{indent}  color: <error: {e}>")

    # Check for connected texture (this is the key path for image swapping)
    try:
        has_tex = cp.hasConnectedTexture
        lines.append(f"{indent}  hasConnectedTexture: {has_tex}")
        if has_tex:
            tex = cp.connectedTexture
            if tex:
                lines.append(f"{indent}  connectedTexture type: {tex.textureType}")
                dump_texture(tex, indent + "  ", lines)
    except Exception as e:
        lines.append(f"{indent}  texture check: <error: {e}>")


def dump_texture(tex, indent, lines):
    """Dump an AppearanceTexture object's properties."""
    try:
        props = tex.properties
        lines.append(f"{indent}texture properties ({props.count}):")
        for i in range(props.count):
            p = props.item(i)
            ptype = prop_type_name(p)
            line = f"{indent}  [{i}] id={p.id}  name={p.name}  type={ptype}"

            # For string props, show value (may contain file paths)
            if p.objectType == "adsk::core::StringProperty":
                sp = adsk.core.StringProperty.cast(p)
                if sp:
                    line += f"  value={sp.value}"

            # For float props, show value
            elif p.objectType == "adsk::core::FloatProperty":
                fp = adsk.core.FloatProperty.cast(p)
                if fp:
                    try:
                        line += f"  value={fp.value}"
                    except Exception:
                        pass

            # For boolean props
            elif p.objectType == "adsk::core::BooleanProperty":
                bp = adsk.core.BooleanProperty.cast(p)
                if bp:
                    try:
                        line += f"  value={bp.value}"
                    except Exception:
                        pass

            # For nested texture props
            elif p.objectType == "adsk::core::AppearanceTextureProperty":
                atp = adsk.core.AppearanceTextureProperty.cast(p)
                if atp and atp.value:
                    line += "  (nested texture)"
                    lines.append(line)
                    dump_texture(atp.value, indent + "    ", lines)
                    continue

            lines.append(line)
    except Exception as e:
        lines.append(f"{indent}  <error dumping texture props: {e}>")


def dump_appearance(appearance, lines):
    """Dump all properties of an appearance."""
    lines.append(f"\n{'='*70}")
    lines.append(f"Appearance: {appearance.name}")
    lines.append(f"  id: {appearance.id}")
    lines.append(f"  hasTexture: {appearance.hasTexture}")
    lines.append(f"  properties count: {appearance.appearanceProperties.count}")
    lines.append(f"{'='*70}")

    props = appearance.appearanceProperties
    for i in range(props.count):
        prop = props.item(i)
        ptype = prop_type_name(prop)
        lines.append(f"  [{i}] id={prop.id}  name={prop.name}  type={ptype}")

        # Detailed dump per type
        if prop.objectType == "adsk::core::ColorProperty":
            dump_color_property(prop, "  ", lines)

        elif prop.objectType == "adsk::core::FloatProperty":
            fp = adsk.core.FloatProperty.cast(prop)
            if fp:
                try:
                    lines.append(f"      value={fp.value}")
                except Exception:
                    pass

        elif prop.objectType == "adsk::core::StringProperty":
            sp = adsk.core.StringProperty.cast(prop)
            if sp:
                lines.append(f"      value={sp.value}")

        elif prop.objectType == "adsk::core::BooleanProperty":
            bp = adsk.core.BooleanProperty.cast(prop)
            if bp:
                try:
                    lines.append(f"      value={bp.value}")
                except Exception:
                    pass

        elif prop.objectType == "adsk::core::ChoiceProperty":
            chp = adsk.core.ChoiceProperty.cast(prop)
            if chp:
                try:
                    lines.append(f"      value={chp.value}")
                except Exception:
                    pass

        elif prop.objectType == "adsk::core::AppearanceTextureProperty":
            atp = adsk.core.AppearanceTextureProperty.cast(prop)
            if atp:
                try:
                    tex = atp.value
                    if tex:
                        lines.append(f"      texture type: {tex.textureType}")
                        dump_texture(tex, "      ", lines)
                    else:
                        lines.append(f"      value: None")
                except Exception as e:
                    lines.append(f"      <error: {e}>")


def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface

    try:
        lines = []
        lines.append("=" * 70)
        lines.append("WOOD APPEARANCE PROPERTY PROBE")
        lines.append("=" * 70)

        # Target appearances to probe — both image-based and 3D procedural
        targets = [
            "Oak",
            "Walnut",
            "Cherry",
            "Maple",
            "Pine",
            "Mahogany",
            "Birch",
            "3D Oak",       # procedural variant for comparison
            "3D Walnut",
        ]

        libs = app.materialLibraries
        found_count = 0

        for li in range(libs.count):
            lib = libs.item(li)
            for ai in range(lib.appearances.count):
                a = lib.appearances.item(ai)
                a_lower = a.name.lower()

                # Match any target (wood appearances don't always have
                # "wood" in the name — they're just "Oak", "Cherry", etc.)
                for target in targets:
                    if target.lower() == a_lower or target.lower() in a_lower:
                        dump_appearance(a, lines)
                        found_count += 1
                        break

            # Stop after finding enough (avoid dumping hundreds)
            if found_count >= 15:
                break

        lines.append(f"\n\nTotal appearances dumped: {found_count}")

        # Also list ALL wood appearances available (just names)
        lines.append(f"\n{'='*70}")
        lines.append("ALL WOOD APPEARANCES IN LIBRARIES:")
        lines.append("=" * 70)
        wood_names = ["oak", "walnut", "cherry", "maple", "pine",
                      "mahogany", "birch", "teak", "ash", "cedar",
                      "ebony", "rosewood", "hickory", "poplar", "elm",
                      "beech", "alder", "wood", "lumber", "timber",
                      "bamboo", "plywood", "3d oak", "3d walnut"]
        for li in range(libs.count):
            lib = libs.item(li)
            for ai in range(lib.appearances.count):
                a = lib.appearances.item(ai)
                a_lower = a.name.lower()
                if any(w in a_lower for w in wood_names):
                    lines.append(f"  {lib.name}: {a.name}")

        output = "\n".join(lines)
        print(output)

        # Also write to a file for easy reading
        import os
        out_path = os.path.join(os.path.expanduser("~"), "wood_appearance_probe.txt")
        with open(out_path, "w") as f:
            f.write(output)
        print(f"\nOutput also written to: {out_path}")

    except Exception:
        print(f"Error: {traceback.format_exc()}")
        if ui:
            ui.messageBox(f"Error:\n{traceback.format_exc()}")
