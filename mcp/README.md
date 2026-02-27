# MCP Integration for Fusion 360

Run Fusion 360 scripts and inspect designs directly from Claude Code using the AutoFusion add-in — a built-in MCP-compatible JSON-RPC server.

## Prerequisites

- Fusion 360 installed and running
- Node.js (for `npx mcp-remote` proxy)
- Claude Code or Codex CLI with MCP support

## Install

```bash
# Via the main installer
./install.sh --mcp

# Or manually: symlink the add-in
ln -sf ~/.autofusion/repo/addin \
  ~/Library/Application\ Support/Autodesk/Autodesk\ Fusion\ 360/API/AddIns/AutoFusion
```

Then in Fusion 360: **Tools > Add-Ins > AutoFusion > Run**

## Available Tools

| Tool | Purpose |
|------|---------|
| `capture_design` | Full design introspection: parameters, component tree with body geometry (volume + bounding box), all timeline features |
| `get_timeline_state` | Roll timeline to any index, capture all body geometry at that point, restore position |
| `execute_script` | Run a Python script in Fusion 360 with automatic transaction wrapping |
| `get_screenshot` | Capture the viewport with optional camera orientation |
| `get_selection` | Read the user's current selection — returns structured info per entity type |
| `set_selection` | Programmatically select/highlight entities by name or token |
| `modify_parameters` | Change parameter expressions with incremental recompute (no script re-run) |
| `check_interference` | Detect body intersections/collisions for joinery validation |
| `suppress_features` | Toggle timeline features on/off for "what if" diagnostics |
| `get_changes` | Snapshot & diff — detect parameter, dimension, body, and feature count changes since last call |

## Claude Code / Codex Config

The installer (`./install.sh --mcp`) auto-configures this. To set it up manually:

**Claude Code** — add to `~/.claude/settings.json`:
```json
{
  "mcpServers": {
    "fusion360": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:9100/"]
    }
  }
}
```

**Codex CLI** — add to `~/.codex/config.toml`:
```toml
[mcp_servers.fusion360]
command = "npx"
args = ["mcp-remote", "http://localhost:9100/"]
```

## Workflow with `/woodworking`

1. Invoke `/woodworking` and describe your piece
2. Claude generates a complete parametric Fusion 360 script
3. Claude executes it via `execute_script`
4. On error: Claude reads the stack trace, fixes the script, and retries
5. On success: Claude takes a screenshot with `get_screenshot`

## Verify

```bash
curl http://localhost:9100/health    # {"status": "healthy", "server": "AutoFusion"}
curl http://localhost:9100/tools     # lists all 10 tools
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Connection refused" | Make sure the AutoFusion add-in is running (Tools > Add-Ins) |
| Add-in not visible | Verify the symlink exists in your AddIns directory |
| Script errors | Check Fusion 360's Text Commands window for stack traces |
| MCP server not detected | Restart Claude Code after editing settings.json |
