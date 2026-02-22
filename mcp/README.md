# MCP Integration for Fusion 360

Run Fusion 360 scripts directly from Claude Code using the Model Context Protocol (MCP).

## MCP Servers

| Server | Approach | Best For |
|--------|----------|----------|
| [mycelia1/fusion360-mcp-server](https://github.com/mycelia1/fusion360-mcp-server) | Script generation + socket execution | Interactive modeling, rich tool set (13+ tools) |
| [AutodeskFusion360/FusionMCPSample](https://github.com/AutodeskFusion360/FusionMCPSample) | HTTP server, executes complete scripts | Running full scripts, screenshots, API docs |

## Prerequisites

- Fusion 360 installed and running
- Python 3.10+
- Claude Desktop or Claude Code with MCP support

## Option A: mycelia1/fusion360-mcp-server

This server provides 13+ tools including `execute_api_script`, `get_screenshot`, parameter manipulation, and more.

### Install

Run the convenience script:

```bash
cd mcp && ./setup.sh
```

Or manually:

```bash
# Clone to a persistent location
git clone https://github.com/mycelia1/fusion360-mcp-server.git ~/.autofusion/mcp-servers/fusion360-mcp-server
cd ~/.autofusion/mcp-servers/fusion360-mcp-server
pip install -e .
```

### Fusion 360 Add-In

Copy the add-in to Fusion 360's add-in directory:

- **macOS:** `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/`
- **Windows:** `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\`

```bash
# macOS
cp -r ~/.autofusion/mcp-servers/fusion360-mcp-server/fusion_addin \
  ~/Library/Application\ Support/Autodesk/Autodesk\ Fusion\ 360/API/AddIns/Fusion360MCPAddin
```

Then in Fusion 360: **Tools > Add-Ins > Add-Ins tab > Fusion360MCPAddin > Run**

### Claude Desktop Config

Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "fusion360": {
      "command": "fusion360-mcp-server",
      "args": []
    }
  }
}
```

## Option B: AutodeskFusion360/FusionMCPSample

Autodesk's official sample. Runs an HTTP server inside Fusion 360 and accepts script payloads.

### Install

```bash
git clone https://github.com/AutodeskFusion360/FusionMCPSample.git ~/.autofusion/mcp-servers/FusionMCPSample
cd ~/.autofusion/mcp-servers/FusionMCPSample
pip install -e .
```

### Fusion 360 Add-In

Copy `FusionMCPServer` add-in from the cloned repo to the add-in directory (same paths as above), then run it from **Tools > Add-Ins**.

### Claude Desktop Config

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

## Workflow with `/woodworking`

1. Invoke `/woodworking` and describe your piece as usual
2. Claude generates a complete parametric Fusion 360 script
3. With MCP connected, use `execute_api_script` to run the script live in Fusion 360
4. Use `get_screenshot` to verify the result visually
5. Iterate: modify parameters or features and re-execute

The `/woodworking` skill generates complete, standalone scripts. MCP is just the delivery mechanism — scripts should always work when pasted into Fusion 360's script editor too.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Connection refused" | Make sure the Fusion 360 add-in is running (Tools > Add-Ins) |
| "No module named fusion360_mcp_server" | Run `pip install -e .` in the server directory |
| Script errors in Fusion 360 | Check Fusion 360's Text Commands window for stack traces |
| Add-in not visible | Verify the add-in folder is in the correct path for your OS |
| MCP server not detected | Restart Claude Desktop after editing config |
