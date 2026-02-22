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
#   --mcp           Set up Fusion 360 MCP server + auto-configure tools
#   --all           All of the above
#   (no flags)      Auto-detect installed tools, skip MCP

AUTOFUSION_HOME="$HOME/.autofusion"
REPO_DIR="$AUTOFUSION_HOME/repo"
REPO_URL="https://github.com/YLZha/autofusion.git"
MCP_REPO_URL="https://github.com/AutodeskFusion360/FusionMCPSample.git"
MCP_DIR="$AUTOFUSION_HOME/mcp-servers/FusionMCPSample"

# --- Parse flags ---
opt_claude_code=false
opt_codex=false
opt_mcp=false
explicit_flags=false

for arg in "$@"; do
    case "$arg" in
        --claude-code) opt_claude_code=true; explicit_flags=true ;;
        --codex)       opt_codex=true;       explicit_flags=true ;;
        --mcp)         opt_mcp=true;         explicit_flags=true ;;
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
    echo
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

# --- MCP setup ---
if [ "$opt_mcp" = true ]; then
    echo "--- MCP (Fusion 360) ---"

    # Check Python version
    if ! command -v python3 &>/dev/null; then
        echo "Error: python3 not found. Install Python 3.10+ first."
        exit 1
    fi

    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
    PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')

    if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]; }; then
        echo "Error: Python 3.10+ required (found $PYTHON_VERSION)."
        exit 1
    fi

    echo "Python $PYTHON_VERSION OK"

    # Clone or update MCP server
    if [ -d "$MCP_DIR" ]; then
        echo "MCP server repo exists, pulling latest..."
        git -C "$MCP_DIR" pull --ff-only
    else
        echo "Cloning FusionMCPSample..."
        mkdir -p "$(dirname "$MCP_DIR")"
        git clone "$MCP_REPO_URL" "$MCP_DIR"
    fi

    echo "Installing FusionMCPSample..."
    pip install -e "$MCP_DIR"

    # Configure MCP for Claude Code
    if [ "$opt_claude_code" = true ]; then
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
    'command': 'python',
    'args': ['-m', 'fusion_mcp_client']
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
command = "python"
args = ["-m", "fusion_mcp_client"]
TOML
            echo "Added fusion360 MCP server to $CODEX_CONFIG"
        fi
    fi

    echo
    echo "MCP next steps:"
    echo "  1. Copy the Fusion 360 add-in to your add-ins directory:"
    if [ "$(uname)" = "Darwin" ]; then
        ADDIN_DIR="$HOME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns"
        echo "     cp -r $MCP_DIR/FusionMCPServer \"$ADDIN_DIR/FusionMCPServer\""
    else
        echo "     Copy $MCP_DIR/FusionMCPServer to %APPDATA%\\Autodesk\\Autodesk Fusion 360\\API\\AddIns\\FusionMCPServer"
    fi
    echo "  2. In Fusion 360: Tools > Add-Ins > FusionMCPServer > Run"
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
