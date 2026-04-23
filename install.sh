#!/bin/bash
set -e

# shopprentice installer
# Usage:
#   Remote: curl -sSL https://raw.githubusercontent.com/ShopPrentice/shopprentice/main/install.sh | bash
#           curl -sSL ... | bash -s -- --mcp
#   Local:  ./install.sh [flags]
#
# Flags:
#   --claude-code   Install for Claude Code
#   --codex         Install for Codex
#   --mcp           Install ShopPrentice add-in + auto-configure MCP tools
#   --no-mcp        Skip MCP setup
#   --all           All of the above
#   (no flags)      Auto-detect installed tools + install MCP

AUTOFUSION_HOME="$HOME/.shopprentice"
REPO_DIR="$AUTOFUSION_HOME/repo"
REPO_URL="https://github.com/ShopPrentice/shopprentice.git"

ensure_config_file() {
    CONFIG_FILE="$AUTOFUSION_HOME/config.json"
    if [ ! -f "$CONFIG_FILE" ]; then
        echo '{"screenshots": "none"}' > "$CONFIG_FILE"
        echo "Created default config: $CONFIG_FILE"
    fi
}

load_screenshot_mode() {
    ensure_config_file
    echo "Applying config from $CONFIG_FILE"
    SS_MODE=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE')).get('screenshots','final-only'))" 2>/dev/null || echo "final-only")
    case "$SS_MODE" in
        none)
            SS_TEXT="**Screenshot mode: none** — do NOT call \`get_product_shots\` or \`get_screenshot\` at any point. Use \`validate_design\` for all checks. Report validation results as text only. This setting overrides any screenshot instructions in topic files."
            ;;
        every-step)
            SS_TEXT="**Screenshot mode: every-step** — call \`get_screenshot\` after each component for visual validation, and \`get_product_shots\` at the end. Do NOT Read the image files — report paths to the user. This setting overrides any screenshot instructions in topic files."
            ;;
        *)
            SS_TEXT="**Screenshot mode: final-only** — call \`get_product_shots\` ONCE at the very end after \`apply_appearance\`. Do NOT call \`get_screenshot\` or \`get_product_shots\` mid-build. Use \`validate_design\` for intermediate checks. This setting overrides any screenshot instructions in topic files."
            ;;
    esac
}

patch_screenshot_mode() {
    local target_file="$1"
    python3 -c "
import re
with open('$target_file') as f:
    content = f.read()
content = re.sub(
    r'<!-- SHOPPRENTICE_SCREENSHOT_MODE:.*?-->.*?<!-- END_SCREENSHOT_MODE -->',
    '<!-- SHOPPRENTICE_SCREENSHOT_MODE: $SS_MODE -->\n$SS_TEXT\n<!-- END_SCREENSHOT_MODE -->',
    content, flags=re.DOTALL)
with open('$target_file', 'w') as f:
    f.write(content)
" 2>/dev/null
}

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

# --- Bootstrap: ensure ~/.shopprentice/repo/ exists ---
echo "=== shopprentice installer ==="
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
        # Symlink so edits to the source repo are immediately live
        mkdir -p "$AUTOFUSION_HOME"
        if [ -d "$REPO_DIR" ] && [ ! -L "$REPO_DIR" ]; then
            echo "Removing old copy at $REPO_DIR..."
            rm -rf "$REPO_DIR"
        fi
        ln -sfn "$SCRIPT_DIR" "$REPO_DIR"
        echo "Linked $REPO_DIR -> $SCRIPT_DIR"
    else
        echo "Already at $REPO_DIR"
    fi
else
    echo "No local repo detected — cloning from $REPO_URL..."
    if [ -d "$REPO_DIR" ]; then
        echo "Existing install found at $REPO_DIR, updating..."
        git -C "$REPO_DIR" checkout main --quiet 2>/dev/null || true
        git -C "$REPO_DIR" fetch --tags
        git -C "$REPO_DIR" pull --ff-only
    else
        mkdir -p "$AUTOFUSION_HOME"
        git clone --depth 1 --filter=blob:none --sparse "$REPO_URL" "$REPO_DIR"
        git -C "$REPO_DIR" sparse-checkout set --no-cone '/*' '!examples/*/screenshots/'
        git -C "$REPO_DIR" fetch --tags
    fi
    # Checkout latest release tag if available
    LATEST_TAG=$(git -C "$REPO_DIR" tag --sort=-v:refname | head -1)
    if [ -n "$LATEST_TAG" ]; then
        echo "Checking out release: $LATEST_TAG"
        git -C "$REPO_DIR" checkout "$LATEST_TAG" --quiet
    fi
fi

echo

# --- Auto-detect tools (when no explicit flags) ---
if [ "$explicit_flags" = false ]; then
    if [ -d "$HOME/.claude" ]; then
        opt_claude_code=true
        echo "Auto-detected: Claude Code"
    fi
    if [ -d "$HOME/.codex" ] || command -v codex >/dev/null 2>&1; then
        opt_codex=true
        echo "Auto-detected: Codex"
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

# --- Codex setup ---
if [ "$opt_codex" = true ]; then
    echo "--- Codex ---"

    CODEX_SKILLS_DIR="$HOME/.codex/skills"
    CODEX_SKILL_DIR="$CODEX_SKILLS_DIR/woodworking"
    CODEX_SKILL_TEMPLATE_DIR="$REPO_DIR/codex/woodworking"
    CODEX_MANAGED_MARKER="$CODEX_SKILL_DIR/.shopprentice-managed"
    CODEX_SKILL_TEMPLATE_REAL=$(python3 -c "import os; print(os.path.realpath('$CODEX_SKILL_TEMPLATE_DIR'))")

    mkdir -p "$CODEX_SKILLS_DIR"

    if [ ! -f "$CODEX_SKILL_TEMPLATE_DIR/SKILL.md" ]; then
        echo "Error: Codex skill source missing at $CODEX_SKILL_TEMPLATE_DIR"
        exit 1
    fi

    if [ -e "$CODEX_SKILL_DIR" ] || [ -L "$CODEX_SKILL_DIR" ]; then
        if [ -L "$CODEX_SKILL_DIR" ]; then
            EXISTING_TARGET="$(readlink "$CODEX_SKILL_DIR")"
            EXISTING_TARGET_REAL="$(python3 -c "import os; print(os.path.realpath('$EXISTING_TARGET'))")"
            if [ "$EXISTING_TARGET_REAL" = "$CODEX_SKILL_TEMPLATE_REAL" ]; then
                rm "$CODEX_SKILL_DIR"
                echo "Migrating previous ShopPrentice Codex symlink install to managed directory"
            else
                echo "Error: $CODEX_SKILL_DIR already exists and points to:"
                echo "  $EXISTING_TARGET"
                echo "Refusing to overwrite a non-ShopPrentice Codex skill."
                exit 1
            fi
        elif [ -f "$CODEX_MANAGED_MARKER" ]; then
            rm -rf "$CODEX_SKILL_DIR"
        else
            echo "Error: $CODEX_SKILL_DIR already exists and is not a ShopPrentice-managed install."
            echo "Refusing to overwrite an existing local Codex skill."
            exit 1
        fi
    fi

    mkdir -p "$CODEX_SKILL_DIR"
    load_screenshot_mode

    cp "$REPO_DIR/commands/woodworking.md" "$CODEX_SKILL_DIR/WOODWORKING.md"
    patch_screenshot_mode "$CODEX_SKILL_DIR/WOODWORKING.md" && echo "  Screenshot mode: $SS_MODE"
    python3 -c "
from pathlib import Path
path = Path('$CODEX_SKILL_DIR/WOODWORKING.md')
content = path.read_text()
content = content.replace('woodworking/', '$REPO_DIR/woodworking/')
path.write_text(content)
"

    python3 -c "
from pathlib import Path
template = Path('$CODEX_SKILL_TEMPLATE_DIR/SKILL.md').read_text()
template = template.replace('__REPO_DIR__', '$REPO_DIR')
Path('$CODEX_SKILL_DIR/SKILL.md').write_text(template)
"
    printf '%s\n' "$REPO_DIR" > "$CODEX_MANAGED_MARKER"
    echo "Installed woodworking skill to $CODEX_SKILL_DIR"
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

    load_screenshot_mode
    patch_screenshot_mode "$CLAUDE_CMD_DIR/woodworking.md" && echo "  Screenshot mode: $SS_MODE"

    echo "Installed /woodworking skill to $CLAUDE_CMD_DIR/woodworking.md"

    # Add global hint so agents know /woodworking exists
    CLAUDE_MD="$HOME/.claude/CLAUDE.md"
    HINT_MARKER="<!-- shopprentice -->"
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

# --- MCP setup (ShopPrentice add-in) ---
if [ "$opt_mcp" = true ]; then
    echo "--- MCP (ShopPrentice Add-in) ---"

    # Install the ShopPrentice add-in via symlink
    ADDIN_SRC="$REPO_DIR/addin"
    if [ "$(uname)" = "Darwin" ]; then
        ADDIN_DIR="$HOME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns"
    else
        ADDIN_DIR="$APPDATA/Autodesk/Autodesk Fusion 360/API/AddIns"
    fi
    ADDIN_LINK="$ADDIN_DIR/ShopPrentice"

    if [ -d "$ADDIN_DIR" ]; then
        # Remove old Fusion MCP Addin if present
        OLD_ADDIN="$ADDIN_DIR/Fusion MCP Addin"
        if [ -d "$OLD_ADDIN" ] && [ ! -L "$OLD_ADDIN" ]; then
            echo "Removing old Fusion MCP Addin..."
            rm -rf "$OLD_ADDIN"
        fi

        echo "Symlinking ShopPrentice add-in..."
        ln -sf "$ADDIN_SRC" "$ADDIN_LINK"
        echo "Installed: $ADDIN_LINK -> $ADDIN_SRC"
    else
        echo "Warning: Fusion 360 AddIns directory not found at $ADDIN_DIR"
        echo "Create a symlink manually:"
        echo "  ln -sf \"$ADDIN_SRC\" \"<your AddIns dir>/ShopPrentice\""
    fi

    if [ "$opt_claude_code" = true ]; then
        echo "Configuring MCP server for Claude Code..."

        if command -v claude >/dev/null 2>&1; then
            # Check if fusion360 MCP server is already configured
            if claude mcp get fusion360 >/dev/null 2>&1; then
                echo "fusion360 MCP server already configured in Claude Code"
            else
                claude mcp add --transport http -s user fusion360 http://localhost:9100/
                echo "Added fusion360 MCP server to Claude Code (user scope)"
            fi
        else
            echo "Warning: 'claude' CLI not found — skipping Claude Code MCP registration."
            echo "Install Claude Code, then run:"
            echo "  claude mcp add --transport http -s user fusion360 http://localhost:9100/"
        fi
    fi

    if [ "$opt_codex" = true ]; then
        echo "Configuring MCP server for Codex..."

        if command -v codex >/dev/null 2>&1; then
            if codex mcp get fusion360 >/dev/null 2>&1; then
                echo "fusion360 MCP server already configured in Codex"
            else
                codex mcp add fusion360 --url http://localhost:9100/
                echo "Added fusion360 MCP server to Codex"
            fi
        else
            echo "Warning: 'codex' CLI not found — skipping Codex MCP registration."
            echo "Install Codex, then run:"
            echo "  codex mcp add fusion360 --url http://localhost:9100/"
        fi
    fi

    echo
    echo "MCP setup complete!"
    echo "  Next: In Fusion 360, go to Tools > Add-Ins > ShopPrentice > Run"
    if [ "$opt_claude_code" = true ] || [ "$opt_codex" = true ]; then
        echo "  Then restart your client to pick up the MCP config."
    fi
    echo
fi

# --- Summary ---
echo "=== Done ==="
echo "  Source:  $REPO_DIR"
[ "$opt_codex" = true ]       && echo "  Codex:       woodworking skill installed"
[ "$opt_claude_code" = true ] && echo "  Claude Code: /woodworking skill installed"
[ "$opt_mcp" = true ]         && echo "  MCP:         fusion360 server installed + configured"
echo
echo "To update later: cd $REPO_DIR && ./install.sh"
