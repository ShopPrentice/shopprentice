#!/bin/bash
set -e

MCP_DIR="$HOME/.autofusion/mcp-servers"
REPO_URL="https://github.com/AutodeskFusion360/FusionMCPSample.git"
REPO_DIR="$MCP_DIR/FusionMCPSample"

echo "=== Fusion 360 MCP Server Setup (FusionMCPSample) ==="
echo

# Check Python version
if ! command -v python3 &> /dev/null; then
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

# Clone or update repo
mkdir -p "$MCP_DIR"

if [ -d "$REPO_DIR" ]; then
    echo "Repository already exists at $REPO_DIR, pulling latest..."
    git -C "$REPO_DIR" pull --ff-only
else
    echo "Cloning $REPO_URL..."
    git clone "$REPO_URL" "$REPO_DIR"
fi

# Install
echo "Installing FusionMCPSample..."
pip install -e "$REPO_DIR"

echo
echo "=== Setup Complete ==="
echo
echo "Next steps:"
echo "  1. Copy the Fusion 360 add-in to your add-ins directory:"
echo
if [ "$(uname)" = "Darwin" ]; then
    ADDIN_DIR="$HOME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns"
    echo "     cp -r $REPO_DIR/FusionMCPServer \"$ADDIN_DIR/FusionMCPServer\""
else
    ADDIN_DIR="%APPDATA%\\Autodesk\\Autodesk Fusion 360\\API\\AddIns"
    echo "     Copy $REPO_DIR/FusionMCPServer to $ADDIN_DIR\\FusionMCPServer"
fi
echo
echo "  2. In Fusion 360: Tools > Add-Ins > FusionMCPServer > Run"
echo
echo "  3. Add to your Claude settings (see mcp/claude-desktop-config.json.example)"
echo
