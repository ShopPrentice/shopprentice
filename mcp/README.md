# MCP Integration for Fusion 360

Run Fusion 360 scripts directly from Claude Code using the Model Context Protocol (MCP).

This project uses [AutodeskFusion360/FusionMCPSample](https://github.com/AutodeskFusion360/FusionMCPSample) — Autodesk's official MCP server. It provides full stack traces on errors, automatic transaction rollback on failure, and API documentation search.

## Prerequisites

- Fusion 360 installed and running
- Python 3.10+
- Claude Desktop or Claude Code with MCP support

## Install

```bash
git clone https://github.com/AutodeskFusion360/FusionMCPSample.git ~/.autofusion/mcp-servers/FusionMCPSample
cd ~/.autofusion/mcp-servers/FusionMCPSample
pip install -e .
```

Or use the installer with `--mcp`:

```bash
./install.sh --mcp
```

## Fusion 360 Add-In

Copy the `FusionMCPServer` add-in from the cloned repo to Fusion 360's add-in directory:

- **macOS:** `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/`
- **Windows:** `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\`

```bash
# macOS
cp -r ~/.autofusion/mcp-servers/FusionMCPSample/FusionMCPServer \
  ~/Library/Application\ Support/Autodesk/Autodesk\ Fusion\ 360/API/AddIns/FusionMCPServer
```

Then in Fusion 360: **Tools > Add-Ins > Add-Ins tab > FusionMCPServer > Run**

## Claude Code / Claude Desktop Config

The installer (`./install.sh --mcp`) auto-configures this. To set it up manually, add to your Claude settings:

```json
{
  "mcpServers": {
    "fusion360": {
      "command": "python",
      "args": ["-m", "fusion_mcp_client"]
    }
  }
}
```

- **Claude Code:** `~/.claude/settings.json` under `mcpServers`
- **Claude Desktop:** `~/.claude/claude_desktop_config.json`

## Available Tools

| Tool | Purpose |
|------|---------|
| `execute_api_script` | Run a complete Python script in Fusion 360. Returns `isError` flag + full stack trace on failure. |
| `get_screenshot` | Capture the current Fusion 360 viewport. |
| `get_api_documentation` | Search Fusion 360 API docs by class/member name. |
| `get_best_practices` | Retrieve Fusion 360 scripting best practices. |

## Workflow with `/woodworking`

1. Invoke `/woodworking` and describe your piece
2. Claude generates a complete parametric Fusion 360 script
3. Claude automatically executes it via `execute_api_script`
4. On error: Claude reads the stack trace, fixes the script, and retries (up to 3 attempts per error)
5. On success: Claude takes a screenshot with `get_screenshot` and shows you the result

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Connection refused" | Make sure the Fusion 360 add-in is running (Tools > Add-Ins) |
| "No module named fusion_mcp_client" | Run `pip install -e .` in the FusionMCPSample directory |
| Script errors in Fusion 360 | Check Fusion 360's Text Commands window for stack traces |
| Add-in not visible | Verify the add-in folder is in the correct path for your OS |
| MCP server not detected | Restart Claude Desktop/Code after editing config |
