---
name: woodworking
description: Use when the user wants to design, modify, or analyze parametric furniture in Fusion 360 with ShopPrentice. Applies to greenfield builds, additive edits to existing models, joinery, hardware, lofted/organic forms, screenshots, and Fusion MCP workflows.
metadata:
  short-description: Fusion 360 parametric furniture modeling with ShopPrentice
---

# ShopPrentice For Codex

ShopPrentice's primary operating rules live in [`WOODWORKING.md`](WOODWORKING.md). Read that file first when this skill is invoked. It is a generated local copy of the canonical `commands/woodworking.md`, with the user's screenshot-mode config applied at install time.

Then load only the supporting references you need from the ShopPrentice repo:

- `__REPO_DIR__/woodworking/mcp-advanced.md` for additive mode, proxy/body lookup patterns, and working against existing user-built models
- `__REPO_DIR__/woodworking/joinery.md` and `__REPO_DIR__/woodworking/joinery/*.md` for specific joint construction rules
- `__REPO_DIR__/woodworking/organic-shapes.md` and `__REPO_DIR__/woodworking/loft.md` for spline, loft, turned, and sculpted forms
- `__REPO_DIR__/woodworking/templates-and-hardware.md`, `__REPO_DIR__/woodworking/hardware-installation.md`, and `__REPO_DIR__/woodworking/templates/*.py` for reusable hardware and joinery templates
- `__REPO_DIR__/woodworking/appearance.md`, `__REPO_DIR__/woodworking/details-and-finishing.md`, and `__REPO_DIR__/woodworking/screenshots.md` for finish passes and presentation output
- `__REPO_DIR__/woodworking/types/*.md` and `__REPO_DIR__/woodworking/styles/*.md` when the user asks for a specific furniture type or style
- `__REPO_DIR__/woodworking/fusion-api-rules.md`, `__REPO_DIR__/woodworking/helpers-reference.md`, and `__REPO_DIR__/woodworking/incremental-updates.md` for implementation details and update workflows

## Codex Notes

- Preserve the rules and workflow from `WOODWORKING.md`; do not substitute a shorter generic summary if the detailed rule exists there.
- Treat `__REPO_DIR__/woodworking/` as the reference library backing the core instructions.
- If the Fusion MCP server is available, use its tools in the mode prescribed by `WOODWORKING.md`.
- If the MCP server is not available, still use the same planning and parametric modeling discipline when reasoning about scripts or reviewing generated code.
