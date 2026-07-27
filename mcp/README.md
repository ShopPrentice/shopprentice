# MCP Integration for Fusion 360

Run Fusion 360 scripts and inspect designs directly from Claude Code using the ShopPrentice add-in — a built-in MCP-compatible JSON-RPC server.

## Prerequisites

- Fusion 360 installed and running
- Node.js (for `npx mcp-remote` proxy)
- Claude Code with MCP support

## Install

```bash
# Via the main installer
./install.sh --mcp

# Or manually: symlink the add-in
ln -sf ~/.shopprentice/repo/addin \
  ~/Library/Application\ Support/Autodesk/Autodesk\ Fusion\ 360/API/AddIns/ShopPrentice
```

Then in Fusion 360: **Tools > Add-Ins > ShopPrentice > Run**

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
| `sync_script` | Auto-sync Fusion UI changes back to a Python script — patches parameter expressions, reports feature-level changes |

## Claude Code Config

The installer (`./install.sh --mcp`) auto-configures this. To set it up manually, add to `~/.claude/settings.json`:

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

## Security

The add-in runs on startup and listens on `localhost:9100` for as long as Fusion is open, and `execute_script` runs arbitrary Python as you. The server therefore refuses any request that looks like it came from a web page:

| Rule | Why |
|------|-----|
| Requests carrying an `Origin` header are rejected | Browsers always send it; MCP clients (`mcp-remote`, Claude Code, `codex`, `curl`) never do |
| `POST` must be `Content-Type: application/json` | Forces a CORS preflight the server does not answer, so a cross-site `fetch()` never delivers its body. Parameters like `; charset=utf-8` are fine |
| `Host` must name the loopback server | Blocks DNS rebinding |
| No `Access-Control-Allow-Origin` is sent | A browser cannot read a reply even if a request slips through |

`GET /health` and `GET /tools` are gated too, but exempt from the Content-Type rule so the `curl` examples below keep working.

### Optional shared secret

The rules above stop web pages, not other programs running as you. To also require a token, create the file — it is **opt-in**, and existing client configs keep working unchanged while it is absent:

```bash
mkdir -p ~/.shopprentice
umask 077 && openssl rand -hex 32 > ~/.shopprentice/mcp_token
chmod 600 ~/.shopprentice/mcp_token
```

Then pass it on every request, as either header:

```bash
curl -H "X-ShopPrentice-Token: $(cat ~/.shopprentice/mcp_token)" http://localhost:9100/health
# or:  -H "Authorization: Bearer <token>"
```

For Claude Code:

```bash
claude mcp add --transport http -s user fusion360 http://localhost:9100/ \
  --header "X-ShopPrentice-Token: $(cat ~/.shopprentice/mcp_token)"
```

The file is re-read per request, so creating or deleting it takes effect without restarting Fusion. Delete it to turn the requirement back off.

## Workflow with `/woodworking`

1. Invoke `/woodworking` and describe your piece
2. Claude generates a complete parametric Fusion 360 script
3. Claude executes it via `execute_script`
4. On error: Claude reads the stack trace, fixes the script, and retries
5. On success: Claude takes a screenshot with `get_screenshot`

## Verify

```bash
curl http://localhost:9100/health    # {"status": "healthy", "server": "ShopPrentice"}
curl http://localhost:9100/tools     # lists all 11 tools
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Connection refused" | Make sure the ShopPrentice add-in is running (Tools > Add-Ins) |
| Add-in not visible | Verify the symlink exists in your AddIns directory |
| Script errors | Check Fusion 360's Text Commands window for stack traces |
| MCP server not detected | Restart Claude Code after editing settings.json |
| `403 Origin header not accepted` | Something browser-like is calling the server. Use an MCP client or `curl`, not a web page |
| `403 Host header does not name this loopback server` | Connect to `localhost`/`127.0.0.1`, not a hostname that resolves to them |
| `415 POST requires Content-Type: application/json` | Add `-H "Content-Type: application/json"` to the POST |
| `401 Missing or invalid ShopPrentice MCP token` | `~/.shopprentice/mcp_token` exists — send the token header, or delete the file |
