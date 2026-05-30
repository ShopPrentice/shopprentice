# ShopPrentice

Parametric furniture modeling for Fusion 360, driven by AI agents via MCP.

Describe a piece of furniture in natural language (or show a photo) and ShopPrentice generates a Fusion 360 parametric model, executes it live in Fusion via MCP, and iterates with you until it's right.

| Overview demo | Getting started tutorial |
|---|---|
| [![ShopPrentice Demo](https://img.youtube.com/vi/yb9XpCFWsMs/mqdefault.jpg)](https://www.youtube.com/watch?v=yb9XpCFWsMs) | [![Getting Started](https://img.youtube.com/vi/nQNU3LeYulE/mqdefault.jpg)](https://www.youtube.com/watch?v=nQNU3LeYulE) |

## How It Works

```
You: "Build a bar-height side table, 36" tall, 4 splayed legs, shelf stretchers with angled tenons"

ShopPrentice agent:
  1. Plans the build (components, features, joinery)
  2. Writes a parametric Fusion 360 Python script
  3. Executes it in Fusion 360 via MCP
  4. Validates with capture_design (body count, volumes, positions)
  5. Fixes any issues and re-executes
  6. Waits for the next prompt from you
```

Rectilinear dimensions are parameter-driven — change any value in the palette or in Modify > Change Parameters and those features recompute incrementally. Organic features (spline outlines, lofted sections, revolved profiles) carry baked fit-point coordinates instead of named dimensions; refine them by dragging control points in Fusion, or prompt the agent to reshape, and it re-bakes the captured points into the script.

## Install

One command — no clone needed:

```bash
curl -sSL https://raw.githubusercontent.com/ShopPrentice/shopprentice/main/install.sh | bash
```

This installs the woodworking skill for supported clients it detects, including Claude Code and Codex, and optionally sets up the MCP server for live Fusion 360 execution. For installer flags, OpenClaw users, and local clone installs, see [DEVELOPMENT.md](DEVELOPMENT.md#install-options).

## Usage

```
/woodworking
Build a 48" x 18" coffee table with tapered legs and a slatted top
```

In Codex, invoke the `woodworking` skill instead of using the Claude-style slash command.

The agent can also work from images — show it a photo or sketch of a piece and it will extract dimensions, proportions, and joint types to generate the parametric model.

## Examples

<table>
<tr>
<td align="center"><a href="examples/jewelry-chest/"><img src="examples/jewelry-chest/product_iso.png" width="200" /><br /><b>Jewelry Chest</b></a><br />Dovetails, mitered trays, spalted maple veneer, frame-and-panel lid</td>
<td align="center"><a href="examples/mcm-desk/"><img src="examples/mcm-desk/assets/rendered_model.png" width="200" /><br /><b>MCM Teak Desk</b></a><br />Real wood photography, entasis legs, ear fillet wrapping</td>
<td align="center"><a href="examples/esherick-stool/"><img src="examples/esherick-stool/iso-top-right.png" width="200" /><br /><b>Esherick Stool</b></a><br />Lofted lens-profile seat, turned legs, wedged through-tenons</td>
</tr>
<tr>
<td align="center"><a href="examples/roubo_workbench/"><img src="examples/roubo_workbench/screenshots/front.png" width="200" /><br /><b>Roubo Workbench</b></a><br />Leg vise, drawbore tenons, sliding deadman, dog holes</td>
<td align="center"><a href="examples/tv-console/"><img src="examples/tv-console/screenshots/iso-top-left.png" width="200" /><br /><b>TV Console</b></a><br />Interlocking M&T, dovetails, dominos</td>
<td align="center"><a href="examples/stool-rebuild/"><img src="examples/stool-rebuild/screenshots/iso-top-right.png" width="200" /><br /><b>Step Stool</b></a><br />Splayed legs, through tenons (rebuilt)</td>
</tr>
<tr>
<td align="center"><a href="examples/windsor-chair/"><img src="examples/windsor-chair/iso.png" width="200" /><br /><b>Windsor Chair</b></a><br />Splayed legs, turned stretchers, scooped seat</td>
<td align="center"><a href="examples/bed-frame/"><img src="examples/bed-frame/screenshots/twin-live-edge-slab.png" width="200" /><br /><b>Twin Bed (Live Edge)</b></a><br />Slab headboard, bowtie inlays, Nakashima style</td>
<td align="center"><a href="examples/loft-bunk-bed/"><img src="examples/loft-bunk-bed/screenshots/iso-top-right.png" width="200" /><br /><b>Loft Bunk Bed</b></a><br />56 domino joints, hook-tab ladder, integrated desk</td>
</tr>
<tr>
<td align="center"><a href="examples/crib/"><img src="examples/crib/screenshots/iso-top-right.png" width="200" /><br /><b>Crib</b></a><br />CPSC spindles, dominos, mattress support</td>
<td align="center"><a href="examples/rachels-table/"><img src="examples/rachels-table/screenshots/iso-top-right.png" width="200" /><br /><b>Rachel's Table</b></a><br />Bridle joints, arched rails, tapered legs</td>
<td align="center"><a href="examples/bookshelf/"><img src="examples/bookshelf/screenshots/iso-top-right.png" width="200" /><br /><b>Bookshelf</b></a><br />Through M&T shelves, dovetail top</td>
</tr>
<tr>
<td align="center"><a href="examples/shaker-nightstand/"><img src="examples/shaker-nightstand/screenshots/iso-top-right.png" width="200" /><br /><b>Shaker Nightstand</b></a><br />Sliding dovetails, half-blind dovetail drawers, revolved knobs</td>
<td align="center"><a href="examples/wrap-box/"><img src="examples/wrap-box/screenshots/iso-top-right.png" width="200" /><br /><b>Wrap Box</b></a><br />Dovetailed dispenser with cutter slot</td>
<td align="center"><a href="examples/pencil-box/"><img src="examples/pencil-box/screenshots/iso-top-right.png" width="200" /><br /><b>Pencil Box</b></a><br />Dovetailed box with sliding lid</td>
</tr>
<tr>
<td align="center"><a href="examples/wood-planter/"><img src="examples/wood-planter/screenshots/iso-top-right.png" width="200" /><br /><b>Wood Planter</b></a><br />Frame construction, T&G slat infill</td>
<td align="center"><a href="examples/pergola-rebuild/"><img src="examples/pergola-rebuild/screenshots/overview.png" width="200" /><br /><b>Pergola + Deck</b></a><br />43 bodies, scarf joints (rebuilt)</td>
<td align="center"><a href="examples/dresser/"><img src="examples/dresser/screenshots/iso-top-right.png" width="200" /><br /><b>Dresser</b></a><br />3-drawer, through dovetail case, maple + poplar</td>
</tr>
<tr>
<td align="center"><a href="examples/chair/"><img src="examples/chair/screenshots/iso-top-right.png" width="200" /><br /><b>Dining Chair</b></a><br />Bent-back legs, vertical slats, tilted dominos</td>
<td align="center"><a href="examples/desk/"><img src="examples/desk/screenshots/iso-top-right.png" width="200" /><br /><b>Desk</b></a><br />Writing desk with aprons</td>
<td align="center"><a href="examples/trestle-table/"><img src="examples/trestle-table/screenshots/iso-top-right.png" width="200" /><br /><b>Trestle Table</b></a><br />Knock-down wedged through-tenons (tusk wedges), drawbore pegs, tabletop buttons</td>
</tr>
</table>

The **Step Stool** and **Pergola** were reverse-engineered from existing Fusion 360 designs using the capture-and-rebuild pipeline (search-based feature matching with per-body volume validation at 0.000% tolerance).

## Capabilities

### Parametric Modeling (rectilinear parts)

Every rectilinear part — boards, cases, frames, rails, drawer boxes, square-stock legs, hardware cutouts — is built on a full Fusion 360 parametric timeline: Sketch > Constrain > Extrude, with Mirror/Pattern for symmetric replication and component structure for logical grouping. Every dimension is a named parameter expression, so the whole piece rebuilds when a palette value changes. This covers the bulk of most furniture.

### Organic Shapes (splined parts)

Sculpted seats, turned legs, carved profiles, scooped surfaces, and lofted lens-profile bodies aren't driven by named dimensions — they're described by curves. ShopPrentice handles them via an **approximate → refine → capture** loop:

1. Agent seeds the shape with a closed fitted spline (plan outline), a half-profile spline + Revolve (turned part), or a multi-section loft with rails (3-D organic solid).
2. You refine interactively: drag fit points in the Fusion UI, or prompt the agent ("make the back edge narrower", "round the corner more").
3. Agent captures edited fit points via `get_timeline_state(include_sketches=True)` and bakes them back into the script as the new defaults — edits survive `clean=true` rebuilds.

Supported organic techniques: revolved turned parts, closed-spline plan outlines, multi-section lofts with direction-tangent end conditions, rail-guided loft shaping, rounded apex tips (bullets/domes/eggs), spherical scoops, through-tenon trimming that follows curved surfaces. See `docs/organic-shapes.md` (shape taxonomy + inline recipes) and `docs/loft.md` (loft feature reference). The Esherick Stool example is the end-to-end showcase of the loop.

### Parameter Editor

Dockable palette in Fusion 360 for iterating without Claude — edit parameters inline, click Rebuild (~14s), and changes write back to the `.py` file. Includes history with restore and a sync tab for capturing UI edits.

### Joinery

12 joint types with reusable Python templates: mortise & tenon, dovetail, box joint, domino, drawbore, dowel, dado/rabbet, lap, bridle, miter, spline, pocket hole. Plus hardware templates for bed rail fasteners and tabletop brackets.

All joinery uses the **combine-based** approach: build the tenon/tail as a body, CUT the receiving board, JOIN to the owner. See [joinery/README.md](docs/joinery/README.md) for the full reference.

### Wood Appearance

20+ built-in species from Fusion's library plus 5 custom high-res species (teak, brazilian rosewood, cocobolo, ziricote, spalted maple) with grain direction auto-aligned to each body's longest axis. Multi-species designs supported.

## Project Structure

```
shopprentice/
  commands/            Canonical woodworking instructions + Claude Code entrypoint
  codex/               Codex skill wrapper(s)
  woodworking/         Skill topic files + joinery reference guides + templates
  helpers/             Standalone script library (sp.py)
  addin/               Fusion 360 add-in (MCP server + tools + parameter palette)
  woodgrain/           Custom wood textures
  examples/            Complete furniture projects with scripts + screenshots
  tools/               Utility scripts (search_build, generate, simulate)
  tests/               Round-trip test suite
```

## Updating

```bash
cd ~/.shopprentice/repo && ./install.sh
```

## Configuration

Settings are in `~/.shopprentice/config.json` (created on first install). Edit the file, then re-run the install command to apply.

```json
{"screenshots": "none"}
```

| Setting | Options | Default | Effect |
|---------|---------|---------|--------|
| `screenshots` | `"none"` | `"none"` | No screenshots — text validation only (most token-efficient) |
| | `"final-only"` | | Product shots once at the very end |
| | `"every-step"` | | Screenshot after each component (uses most tokens) |

Projects are saved to `~/shopprentice-projects/<project-name>/` with a script and README for each build.

## Roadmap

- **Advanced curved forms** — bent laminations, cabriole legs, steam-bent backs, Chinese traditional furniture (sculpted organic solids, turned parts, scooped surfaces, and lofted bodies are already supported — see Organic Shapes above)
- **More joinery** — castle joint, sliding dovetail, Japanese joinery (mortise & tenon, dovetail, box joint, domino, drawbore, dowel, dado/rabbet, lap, bridle, miter, spline, pocket hole, and wedged tenon are already implemented)
- **Output** — cut lists, CNC toolpath hints, shop drawings
- **Other CAD platforms** — FreeCAD, Shapr3D, Onshape
- **Image-to-model** — better dimension extraction and 3D reconstruction from reference photos

## License

MIT — see [LICENSE](LICENSE).
