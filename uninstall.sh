#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$HOME/.claude/commands"

removed=()
for file in "$SCRIPT_DIR"/commands/*.md; do
    [ -f "$file" ] || continue
    name="$(basename "$file")"
    target="$TARGET_DIR/$name"
    if [ -f "$target" ]; then
        rm "$target"
        removed+=("$name")
    fi
done

if [ ${#removed[@]} -eq 0 ]; then
    echo "Nothing to remove."
else
    echo "Removed ${#removed[@]} skill(s) from $TARGET_DIR:"
    for name in "${removed[@]}"; do
        echo "  - $name"
    done
fi
