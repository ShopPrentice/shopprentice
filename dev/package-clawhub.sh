#!/usr/bin/env bash
# Package ShopPrentice as a ClawHub-compatible .skill bundle.
#
# Usage:
#   ./dev/package-clawhub.sh [version]
#
# If version is omitted, reads from the latest git tag.
# Outputs: dist/shopprentice-<version>.skill (a zip file)
#
# What it does:
#   1. Reads commands/woodworking.md (source of truth)
#   2. Prepends OpenClaw YAML frontmatter → SKILL.md
#   3. Collects all skill files (woodworking/, helpers/, hardware/, templates, etc.)
#   4. Zips into a .skill package
#
# The SKILL.md is generated — never edit it directly.
# Edit commands/woodworking.md instead.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Determine version
VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  VERSION=$(git describe --tags --abbrev=0 2>/dev/null || echo "0.0.0")
  VERSION="${VERSION#v}"  # strip leading v
fi

echo "Packaging ShopPrentice v${VERSION} for ClawHub..."

# Create clean build directory
BUILD_DIR=$(mktemp -d)
DIST_DIR="$REPO_ROOT/dist"
mkdir -p "$DIST_DIR"

# 1. Generate SKILL.md from woodworking.md with OpenClaw frontmatter
cat > "$BUILD_DIR/SKILL.md" << FRONTMATTER
---
name: woodworking
description: AI-powered parametric furniture modeling for Fusion 360. Generates production-ready CAD models with real joinery from natural language, images, or reference links.
version: ${VERSION}
metadata:
  openclaw:
    requires:
      bins: [git]
      anyBins: []
      env: []
    primaryEnv: ""
    emoji: "🪵"
    homepage: https://github.com/ShopPrentice/shopprentice
    os: ["macos", "linux", "windows"]
    install:
      - kind: brew
        formula: git
        bins: [git]
    security:
      networkAccess:
        - description: "MCP JSON-RPC server on localhost:9100 for live Fusion 360 script execution"
          host: "localhost"
          port: 9100
          direction: "local-only"
      installMethod:
        - description: "One-line installer clones the GitHub repo and symlinks the Fusion 360 add-in. Source is fully auditable at https://github.com/ShopPrentice/shopprentice/blob/main/install.sh"
          command: "curl -sSL https://raw.githubusercontent.com/ShopPrentice/shopprentice/main/install.sh | bash"
      codeExecution:
        - description: "The skill generates Fusion 360 Python scripts and executes them via the MCP add-in. Scripts are saved locally and can be reviewed before execution. Without the add-in, the skill still generates correct scripts — users can run them manually."
    compatibility:
      recommended: ["Claude Opus"]
      tested: ["Claude Opus (claude-opus-4-6) via Claude Code"]
      note: "This skill requires frontier-level LLMs with strong long-context reasoning and code generation. Developed and tested with Claude Opus. Other models are untested and may fail to follow the multi-step procedural instructions."
---

FRONTMATTER

# Append the actual skill content (skip any existing frontmatter in woodworking.md)
if head -1 "$REPO_ROOT/commands/woodworking.md" | grep -q "^---$"; then
  # Has frontmatter — skip it
  sed -n '/^---$/,/^---$/!p' "$REPO_ROOT/commands/woodworking.md" | tail -n +1 >> "$BUILD_DIR/SKILL.md"
else
  cat "$REPO_ROOT/commands/woodworking.md" >> "$BUILD_DIR/SKILL.md"
fi

# 2. Copy skill topic files
#    docs/ holds the guides (joinery, types, styles, etc.) referenced by SKILL.md;
#    woodworking/ now holds only the joinery templates.
cp -r "$REPO_ROOT/docs" "$BUILD_DIR/docs"
cp -r "$REPO_ROOT/woodworking" "$BUILD_DIR/woodworking"

# 3. Copy helper library
cp -r "$REPO_ROOT/helpers" "$BUILD_DIR/helpers"

# 4. Copy hardware catalog + templates
cp -r "$REPO_ROOT/hardware" "$BUILD_DIR/hardware"

# 5. Copy config
cp "$REPO_ROOT/config.json" "$BUILD_DIR/config.json" 2>/dev/null || true

# 6. Remove any __pycache__, .DS_Store, etc.
find "$BUILD_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -name ".DS_Store" -delete 2>/dev/null || true
find "$BUILD_DIR" -name "*.pyc" -delete 2>/dev/null || true

# 7. Zip into .skill package
SKILL_FILE="$DIST_DIR/shopprentice-${VERSION}.skill"
(cd "$BUILD_DIR" && zip -r "$SKILL_FILE" . -x ".*")

# Also create a latest symlink
cp "$SKILL_FILE" "$DIST_DIR/shopprentice-latest.skill"

# Cleanup
rm -rf "$BUILD_DIR"

echo ""
echo "Package created:"
echo "  $SKILL_FILE"
echo "  $DIST_DIR/shopprentice-latest.skill"
echo ""
FILESIZE=$(ls -lh "$SKILL_FILE" | awk '{print $5}')
FILECOUNT=$(unzip -l "$SKILL_FILE" | tail -1 | awk '{print $2}')
echo "  Size: $FILESIZE"
echo "  Files: $FILECOUNT"
