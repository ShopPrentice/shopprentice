#!/bin/bash
set -e

# autofusion installer
# Usage:
#   Remote: curl -sSL https://raw.githubusercontent.com/YLZha/autofusion/main/install.sh | bash
#           curl -sSL ... | bash -s -- --codex --mcp
#   Local:  ./install.sh [flags]
#
# Flags:
#   --claude-code   Install for Claude Code
#   --codex         Install for OpenAI Codex CLI
#   --mcp           Install AutoFusion add-in + auto-configure MCP tools
#   --no-mcp        Skip MCP setup
#   --all           All of the above
#   (no flags)      Auto-detect installed tools + install MCP

AUTOFUSION_HOME="$HOME/.autofusion"
REPO_DIR="$AUTOFUSION_HOME/repo"
REPO_URL="https://github.com/YLZha/autofusion.git"

# --- Parse flags ---
opt_claude_code=false
opt_codex=false
opt_mcp=false
opt_no_mcp=false
explicit_flags=false

for arg in "$@"; do
    case "$arg" in
        --claude-code) opt_claude_code=true; explicit_flags=true ;;
        --codex)       opt_codex=true;       explicit_flags=true ;;
        --mcp)         opt_mcp=true;         explicit_flags=true ;;
        --no-mcp)      opt_no_mcp=true;      explicit_flags=true ;;
        --all)         opt_claude_code=true; opt_codex=true; opt_mcp=true; explicit_flags=true ;;
        *)             echo "Unknown flag: $arg"; exit 1 ;;
    esac
done

# --- Bootstrap: ensure ~/.autofusion/repo/ exists ---
echo "=== autofusion installer ==="
echo

# Detect if we're running from inside a repo checkout (local install)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
LOCAL_REPO=false

if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/commands/woodworking.md" ]; then
    LOCAL_REPO=true
fi

if [ "$LOCAL_REPO" = true ]; then
    echo "Local repo detected at $SCRIPT_DIR"
    if [ "$SCRIPT_DIR" != "$REPO_DIR" ]; then
        echo "Copying to $REPO_DIR..."
        mkdir -p "$REPO_DIR"
        rsync -a --exclude='.git' "$SCRIPT_DIR/" "$REPO_DIR/"
    else
        echo "Already at $REPO_DIR"
    fi
else
    echo "No local repo detected — cloning from $REPO_URL..."
    if [ -d "$REPO_DIR" ]; then
        echo "Existing install found at $REPO_DIR, pulling latest..."
        git -C "$REPO_DIR" pull --ff-only
    else
        mkdir -p "$AUTOFUSION_HOME"
        git clone "$REPO_URL" "$REPO_DIR"
    fi
fi

echo

# --- Auto-detect tools (when no explicit flags) ---
if [ "$explicit_flags" = false ]; then
    if [ -d "$HOME/.claude" ]; then
        opt_claude_code=true
        echo "Auto-detected: Claude Code"
    fi
    if [ -d "$HOME/.codex" ] || command -v codex &>/dev/null; then
        opt_codex=true
        echo "Auto-detected: Codex CLI"
    fi
    if [ "$opt_claude_code" = false ] && [ "$opt_codex" = false ]; then
        echo "No supported tools detected. Use --claude-code, --codex, or --all."
        echo "Continuing with Claude Code as default."
        opt_claude_code=true
    fi
    opt_mcp=true
    echo "MCP server will be installed (use --no-mcp to skip)"
    echo
fi

# Apply --no-mcp override (works with both explicit and auto-detect)
if [ "$opt_no_mcp" = true ]; then
    opt_mcp=false
fi

# --- Claude Code setup ---
if [ "$opt_claude_code" = true ]; then
    echo "--- Claude Code ---"

    # Install skill
    CLAUDE_CMD_DIR="$HOME/.claude/commands"
    mkdir -p "$CLAUDE_CMD_DIR"

    # Copy woodworking.md with patched joinery paths
    sed 's|joinery/|'"$REPO_DIR"'/joinery/|g' "$REPO_DIR/commands/woodworking.md" \
        > "$CLAUDE_CMD_DIR/woodworking.md"

    echo "Installed /woodworking skill to $CLAUDE_CMD_DIR/woodworking.md"

    # Add global hint so agents know /woodworking exists
    CLAUDE_MD="$HOME/.claude/CLAUDE.md"
    HINT_MARKER="<!-- autofusion -->"
    HINT_LINE="$HINT_MARKER For Fusion 360 furniture modeling, invoke the \`/woodworking\` skill."
    if [ -f "$CLAUDE_MD" ] && grep -q "$HINT_MARKER" "$CLAUDE_MD"; then
        echo "Global /woodworking hint already in $CLAUDE_MD"
    else
        echo "" >> "$CLAUDE_MD"
        echo "$HINT_LINE" >> "$CLAUDE_MD"
        echo "Added /woodworking hint to $CLAUDE_MD"
    fi
    echo
fi

# --- Codex CLI setup ---
if [ "$opt_codex" = true ]; then
    echo "--- Codex CLI ---"

    CODEX_DIR="$HOME/.codex"
    mkdir -p "$CODEX_DIR"
    AGENTS_FILE="$CODEX_DIR/AGENTS.md"

    # Generate adapted content (patch joinery paths, remove slash-command framing)
    AUTOFUSION_CONTENT=$(sed \
        -e 's|joinery/|'"$REPO_DIR"'/joinery/|g' \
        -e 's|`/woodworking`|this skill|g' \
        -e 's|See `mcp/README.md` for setup instructions.|See '"$REPO_DIR"'/mcp/README.md for setup instructions.|g' \
        "$REPO_DIR/commands/woodworking.md")

    START_MARKER="<!-- autofusion:start -->"
    END_MARKER="<!-- autofusion:end -->"

    # Write the new autofusion block to a temp file
    AUTOFUSION_BLOCK="$(mktemp)"
    printf '%s\n%s\n%s\n' "$START_MARKER" "$AUTOFUSION_CONTENT" "$END_MARKER" > "$AUTOFUSION_BLOCK"

    if [ -f "$AGENTS_FILE" ] && grep -q "$START_MARKER" "$AGENTS_FILE"; then
        # Replace existing block using Python for reliable multi-line handling
        python3 -c "
import sys
start = '$START_MARKER'
end = '$END_MARKER'
with open('$AGENTS_FILE') as f:
    lines = f.readlines()
with open(sys.argv[1]) as f:
    block = f.read()
out = []
skip = False
for line in lines:
    stripped = line.rstrip('\n')
    if stripped == start:
        skip = True
        continue
    if stripped == end:
        skip = False
        continue
    if not skip:
        out.append(line)
# Remove trailing blank lines before inserting block
while out and out[-1].strip() == '':
    out.pop()
if out:
    out.append('\n')
out.append(block)
with open('$AGENTS_FILE', 'w') as f:
    f.writelines(out)
" "$AUTOFUSION_BLOCK"
        echo "Updated autofusion section in $AGENTS_FILE"
    elif [ -f "$AGENTS_FILE" ]; then
        # Append with markers
        printf '\n' >> "$AGENTS_FILE"
        cat "$AUTOFUSION_BLOCK" >> "$AGENTS_FILE"
        echo "Appended autofusion section to $AGENTS_FILE"
    else
        # Create new file
        cp "$AUTOFUSION_BLOCK" "$AGENTS_FILE"
        echo "Created $AGENTS_FILE"
    fi
    rm -f "$AUTOFUSION_BLOCK"
    echo
fi

# --- MCP setup (AutoFusion add-in) ---
if [ "$opt_mcp" = true ]; then
    echo "--- MCP (AutoFusion Add-in) ---"

    # Check Node.js (required for mcp-remote proxy)
    if ! command -v npx &>/dev/null; then
        echo "Error: npx not found. Install Node.js first: https://nodejs.org"
        exit 1
    fi
    echo "Node.js $(node --version) OK"

    # Install the AutoFusion add-in via symlink
    ADDIN_SRC="$REPO_DIR/addin"
    if [ "$(uname)" = "Darwin" ]; then
        ADDIN_DIR="$HOME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns"
    else
        ADDIN_DIR="$APPDATA/Autodesk/Autodesk Fusion 360/API/AddIns"
    fi
    ADDIN_LINK="$ADDIN_DIR/AutoFusion"

    if [ -d "$ADDIN_DIR" ]; then
        # Remove old Fusion MCP Addin if present
        OLD_ADDIN="$ADDIN_DIR/Fusion MCP Addin"
        if [ -d "$OLD_ADDIN" ] && [ ! -L "$OLD_ADDIN" ]; then
            echo "Removing old Fusion MCP Addin..."
            rm -rf "$OLD_ADDIN"
        fi

        echo "Symlinking AutoFusion add-in..."
        ln -sf "$ADDIN_SRC" "$ADDIN_LINK"
        echo "Installed: $ADDIN_LINK -> $ADDIN_SRC"
    else
        echo "Warning: Fusion 360 AddIns directory not found at $ADDIN_DIR"
        echo "Create a symlink manually:"
        echo "  ln -sf \"$ADDIN_SRC\" \"<your AddIns dir>/AutoFusion\""
    fi

    # Configure MCP for Claude Code (uses npx mcp-remote to proxy HTTP)
    if [ "$opt_claude_code" = true ] || [ "$explicit_flags" = false ]; then
        CLAUDE_SETTINGS="$HOME/.claude/settings.json"
        echo "Configuring MCP for Claude Code..."

        python3 -c "
import json, os

path = os.path.expanduser('$CLAUDE_SETTINGS')
data = {}
if os.path.isfile(path):
    with open(path) as f:
        data = json.load(f)

data.setdefault('mcpServers', {})
data['mcpServers']['fusion360'] = {
    'command': 'npx',
    'args': ['mcp-remote', 'http://localhost:9100/']
}

os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
"
        echo "Added fusion360 MCP server to $CLAUDE_SETTINGS"
    fi

    # Configure MCP for Codex
    if [ "$opt_codex" = true ]; then
        CODEX_CONFIG="$HOME/.codex/config.toml"
        echo "Configuring MCP for Codex CLI..."

        mkdir -p "$HOME/.codex"
        if [ -f "$CODEX_CONFIG" ] && grep -q '\[mcp_servers\.fusion360\]' "$CODEX_CONFIG"; then
            echo "fusion360 MCP already configured in $CODEX_CONFIG"
        else
            cat >> "$CODEX_CONFIG" <<'TOML'

[mcp_servers.fusion360]
command = "npx"
args = ["mcp-remote", "http://localhost:9100/"]
TOML
            echo "Added fusion360 MCP server to $CODEX_CONFIG"
        fi
    fi

    echo
    echo "MCP setup complete!"
    echo "  Next: In Fusion 360, go to Tools > Add-Ins > AutoFusion > Run"
    echo "  Then restart Claude Code to pick up the MCP config."
    echo
fi

# --- Summary ---
echo "=== Done ==="
echo "  Source:  $REPO_DIR"
[ "$opt_claude_code" = true ] && echo "  Claude Code: /woodworking skill installed"
[ "$opt_codex" = true ]       && echo "  Codex CLI:   AGENTS.md configured"
[ "$opt_mcp" = true ]         && echo "  MCP:         fusion360 server installed + configured"
echo
echo "To update later: cd $REPO_DIR && git pull && ./install.sh"
