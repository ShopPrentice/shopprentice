#!/bin/bash
set -e

# autofusion uninstaller
# Removes all autofusion-installed files from the system.

AUTOFUSION_HOME="$HOME/.autofusion"
removed=()

echo "=== autofusion uninstaller ==="
echo

# --- Remove ~/.autofusion/ ---
if [ -d "$AUTOFUSION_HOME" ]; then
    rm -rf "$AUTOFUSION_HOME"
    removed+=("$AUTOFUSION_HOME/")
fi

# --- Remove Claude Code skill ---
CLAUDE_SKILL="$HOME/.claude/commands/woodworking.md"
if [ -f "$CLAUDE_SKILL" ]; then
    rm "$CLAUDE_SKILL"
    removed+=("$CLAUDE_SKILL")
fi

# --- Remove fusion360 MCP from Claude Code settings ---
CLAUDE_SETTINGS="$HOME/.claude/settings.json"
if [ -f "$CLAUDE_SETTINGS" ] && grep -q '"fusion360"' "$CLAUDE_SETTINGS"; then
    python3 -c "
import json, os

path = os.path.expanduser('$CLAUDE_SETTINGS')
with open(path) as f:
    data = json.load(f)

if 'mcpServers' in data and 'fusion360' in data['mcpServers']:
    del data['mcpServers']['fusion360']
    if not data['mcpServers']:
        del data['mcpServers']

with open(path, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
" 2>/dev/null && removed+=("fusion360 MCP from $CLAUDE_SETTINGS")
fi

# --- Remove autofusion block from Codex AGENTS.md ---
AGENTS_FILE="$HOME/.codex/AGENTS.md"
START_MARKER="<!-- autofusion:start -->"
END_MARKER="<!-- autofusion:end -->"

if [ -f "$AGENTS_FILE" ] && grep -q "$START_MARKER" "$AGENTS_FILE"; then
    awk -v start="$START_MARKER" -v end="$END_MARKER" '
        $0 == start { skip=1; next }
        $0 == end { skip=0; next }
        !skip { print }
    ' "$AGENTS_FILE" > "$AGENTS_FILE.tmp"
    mv "$AGENTS_FILE.tmp" "$AGENTS_FILE"
    # Remove file if empty (only whitespace)
    if [ ! -s "$AGENTS_FILE" ] || ! grep -q '[^[:space:]]' "$AGENTS_FILE"; then
        rm "$AGENTS_FILE"
        removed+=("$AGENTS_FILE (empty, removed)")
    else
        removed+=("autofusion section from $AGENTS_FILE")
    fi
fi

# --- Remove fusion360 MCP from Codex config.toml ---
CODEX_CONFIG="$HOME/.codex/config.toml"
if [ -f "$CODEX_CONFIG" ] && grep -q '\[mcp_servers\.fusion360\]' "$CODEX_CONFIG"; then
    # Remove the [mcp_servers.fusion360] section and its key-value lines
    awk '
        /^\[mcp_servers\.fusion360\]/ { skip=1; next }
        skip && /^\[/ { skip=0 }
        skip && /^[a-z]/ { next }
        skip && /^$/ { next }
        !skip { print }
    ' "$CODEX_CONFIG" > "$CODEX_CONFIG.tmp"
    mv "$CODEX_CONFIG.tmp" "$CODEX_CONFIG"
    removed+=("fusion360 MCP from $CODEX_CONFIG")
fi

# --- Summary ---
echo
if [ ${#removed[@]} -eq 0 ]; then
    echo "Nothing to remove — autofusion was not installed."
else
    echo "Removed:"
    for item in "${removed[@]}"; do
        echo "  - $item"
    done
fi
