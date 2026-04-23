# Development

Installer options, model compatibility, and MCP tooling reference. For the project overview, examples gallery, and capabilities, see [README.md](README.md).

## Install Options

The one-line installer supports a few flags:

```bash
# Claude Code skill only
curl -sSL https://raw.githubusercontent.com/ShopPrentice/shopprentice/main/install.sh | bash -s -- --claude-code

# Codex skill only
curl -sSL https://raw.githubusercontent.com/ShopPrentice/shopprentice/main/install.sh | bash -s -- --codex

# MCP server only
curl -sSL https://raw.githubusercontent.com/ShopPrentice/shopprentice/main/install.sh | bash -s -- --mcp

# all supported clients + MCP
curl -sSL https://raw.githubusercontent.com/ShopPrentice/shopprentice/main/install.sh | bash -s -- --all

# no flags = auto-detect installed clients + MCP
curl -sSL https://raw.githubusercontent.com/ShopPrentice/shopprentice/main/install.sh | bash
```

### OpenClaw install

For [OpenClaw](https://openclaw.ai) users there's a dedicated installer:

```bash
curl -sSL https://raw.githubusercontent.com/ShopPrentice/shopprentice/main/install-openclaw.sh | bash
```

### Local clone install

For development or forks:

```bash
git clone https://github.com/ShopPrentice/shopprentice.git
cd shopprentice
./install.sh --all
```

The installer creates a `~/.shopprentice/repo` symlink pointing at your clone, so any `git pull` in the clone immediately updates the installed skill.

For Codex, the installer creates a symlink at `~/.codex/skills/woodworking` pointing back into the repo. It refuses to overwrite an existing non-ShopPrentice Codex skill at that path.

## Model Compatibility

This skill requires a frontier-level LLM with strong long-context reasoning, code generation, and instruction-following abilities.

| Model | Status | Notes |
|-------|--------|-------|
| **Claude Opus** | ✅ Tested | Developed and tested with this model via Claude Code |
| **Claude Sonnet** | ✅ Tested | Works for most builds; Opus preferred for complex joinery |
| **Codex** | ⚠️ Integration added | Codex installer + skill wrapper supported; end-to-end model performance still depends on the selected model |
| **Other frontier models** | ⚠️ Untested | May work but expect limitations |
| **Smaller / open-source models** | ❌ Not recommended | Fails to follow the multi-step procedural instructions across long context |

The skill pushes models to their limits — 50K+ tokens of structured instructions, correct Fusion 360 API code generation, parametric relationships across 50+ parameters, and iterative MCP tool use. If your model is not listed above, expect significant limitations.

## MCP Tools

The ShopPrentice add-in provides an MCP server on `localhost:9100` with tools for the full design loop:

| Tool | Purpose |
|------|---------|
| `execute_script` | Run Python in Fusion 360 (`sandbox=true` for validation, `clean=true` for rebuild) |
| `capture_design` | Full introspection: parameters, components, body geometry, timeline |
| `validate_design` | Connectivity + interference check in one call |
| `modify_parameters` | Change values with incremental recompute |
| `get_screenshot` | Viewport capture with camera orientation |
| `get_product_shots` | High-res presentation shots, multiple views |
| `get_selection` / `set_selection` | Read/highlight entities in the UI |
| `apply_appearance` | Wood species with grain-aligned textures |
| `sync_script` | Auto-patch parameter changes from UI edits into the script |
| `get_changes` | Snapshot & diff for detecting UI modifications |
| `get_timeline_state` | Capture a specific timeline feature — sketches (incl. spline fit points), bodies at that point; used for the approximate→refine→capture loop on organic shapes |
| `check_interference` / `check_connectivity` | Structural diagnostics |

Health check:

```bash
curl http://localhost:9100/health    # {"status": "healthy", "server": "ShopPrentice"}
```
