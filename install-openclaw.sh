#!/bin/bash
set -e

# ShopPrentice OpenClaw Installer
# Single command install for OpenClaw users with Fusion 360
# Usage: curl -sSL https://raw.githubusercontent.com/ShopPrentice/shopprentice/main/install-openclaw.sh | bash

echo "=== ShopPrentice for OpenClaw ==="
echo

# 1. Clone/sync shopprentice repo
AUTOFUSION_DIR="$HOME/.shopprentice/repo"
if [ -d "$AUTOFUSION_DIR" ]; then
    echo "Updating ShopPrentice repo..."
    git -C "$AUTOFUSION_DIR" pull --ff-only 2>/dev/null || echo "Pull failed, using existing"
else
    echo "Cloning ShopPrentice repo..."
    mkdir -p "$(dirname "$AUTOFUSION_DIR")"
    git clone https://github.com/ShopPrentice/shopprentice.git "$AUTOFUSION_DIR"
fi

# 2. Install Fusion 360 add-in
echo "Installing Fusion 360 add-in..."
if [ "$(uname)" = "Darwin" ]; then
    ADDIN_DIR="$HOME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns"
else
    ADDIN_DIR="$APPDATA/Autodesk/Autodesk Fusion 360/API/AddIns"
fi

if [ -d "$ADDIN_DIR" ]; then
    ln -sf "$AUTOFUSION_DIR/addin" "$ADDIN_DIR/ShopPrentice"
    echo "  ✓ Added: $ADDIN_DIR/ShopPrentice"
else
    echo "  ⚠ Fusion 360 AddIns directory not found"
    echo "    Expected: $ADDIN_DIR"
    echo "    Install Fusion 360 first, then run this again"
fi

# 3. Configure mcporter for OpenClaw
echo "Configuring mcporter for OpenClaw..."
MCPORTER_CONFIG="$HOME/.openclaw/config/mcporter.json"
mkdir -p "$(dirname "$MCPORTER_CONFIG")"

python3 -c "
import json
import os

config = {}
path = os.path.expanduser('$MCPORTER_CONFIG')
if os.path.exists(path):
    with open(path) as f:
        config = json.load(f)

config['servers'] = config.get('servers', {})
config['servers']['fusion360'] = {
    'url': 'http://localhost:9100/'
}

os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, 'w') as f:
    json.dump(config, f, indent=2)
    f.write('\n')
"
echo "  ✓ Configured mcporter: fusion360 MCP server"

echo
echo "=== Installation Complete ==="
echo
echo "Next steps:"
echo "1. Start Fusion 360"
echo "2. In Fusion 360: Tools > Add-Ins > ShopPrentice > Run"
echo "3. Say hi! Try: /woodworking Build a simple shelf"
echo
echo "To update later: git -C ~/.shopprentice/repo pull"
