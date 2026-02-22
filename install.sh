#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$HOME/.claude/commands"

mkdir -p "$TARGET_DIR"

installed=()
for file in "$SCRIPT_DIR"/commands/*.md; do
    [ -f "$file" ] || continue
    name="$(basename "$file")"
    cp "$file" "$TARGET_DIR/$name"
    installed+=("$name")
done

if [ ${#installed[@]} -eq 0 ]; then
    echo "No skill files found in commands/."
    exit 1
fi

echo "Installed ${#installed[@]} skill(s) to $TARGET_DIR:"
for name in "${installed[@]}"; do
    echo "  - $name"
done
