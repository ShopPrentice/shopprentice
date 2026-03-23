#!/bin/bash
set -e

# shopprentice uninstaller
# Removes all shopprentice-installed files from the system.

AUTOFUSION_HOME="$HOME/.shopprentice"
removed=()

echo "=== shopprentice uninstaller ==="
echo

# --- Remove ShopPrentice add-in symlink ---
if [ "$(uname)" = "Darwin" ]; then
    ADDIN_LINK="$HOME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/ShopPrentice"
else
    ADDIN_LINK="$APPDATA/Autodesk/Autodesk Fusion 360/API/AddIns/ShopPrentice"
fi
if [ -L "$ADDIN_LINK" ]; then
    rm "$ADDIN_LINK"
    removed+=("$ADDIN_LINK (symlink)")
fi

# --- Remove ~/.shopprentice/ ---
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

# --- Remove /woodworking hint from global CLAUDE.md ---
CLAUDE_MD="$HOME/.claude/CLAUDE.md"
HINT_MARKER="<!-- shopprentice -->"
if [ -f "$CLAUDE_MD" ] && grep -q "$HINT_MARKER" "$CLAUDE_MD"; then
    grep -v "$HINT_MARKER" "$CLAUDE_MD" > "$CLAUDE_MD.tmp"
    mv "$CLAUDE_MD.tmp" "$CLAUDE_MD"
    # Remove file if empty
    if [ ! -s "$CLAUDE_MD" ] || ! grep -q '[^[:space:]]' "$CLAUDE_MD"; then
        rm "$CLAUDE_MD"
        removed+=("$CLAUDE_MD (empty, removed)")
    else
        removed+=("shopprentice hint from $CLAUDE_MD")
    fi
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

# --- Summary ---
echo
if [ ${#removed[@]} -eq 0 ]; then
    echo "Nothing to remove — shopprentice was not installed."
else
    echo "Removed:"
    for item in "${removed[@]}"; do
        echo "  - $item"
    done
fi
