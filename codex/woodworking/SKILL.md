---
name: woodworking
description: Use when the user wants to design, modify, or analyze parametric furniture in Fusion 360 with ShopPrentice. Applies to greenfield builds, additive edits to existing models, joinery, hardware, lofted/organic forms, screenshots, and Fusion MCP workflows.
metadata:
  short-description: Fusion 360 parametric furniture modeling with ShopPrentice
---

# ShopPrentice For Codex

ShopPrentice's primary operating rules live in [`../../commands/woodworking.md`](../../commands/woodworking.md). Read that file first when this skill is invoked. It contains core modeling discipline, parametric rules, planning requirements, additive-vs-clean rebuild guidance, and Fusion 360 API expectations.

Then load only the supporting references you need from `../../woodworking/`:

- `mcp-advanced.md` for additive mode, proxy/body lookup patterns, and working against existing user-built models
- `joinery.md` and `joinery/*.md` for specific joint construction rules
- `organic-shapes.md` and `loft.md` for spline, loft, turned, and sculpted forms
- `templates-and-hardware.md`, `hardware-installation.md`, and `templates/*.py` for reusable hardware and joinery templates
- `appearance.md`, `details-and-finishing.md`, and `screenshots.md` for finish passes and presentation output
- `types/*.md` and `styles/*.md` when the user asks for a specific furniture type or style
- `fusion-api-rules.md`, `helpers-reference.md`, and `incremental-updates.md` for implementation details and update workflows

## Codex Notes

- Preserve the rules and workflow from `../../commands/woodworking.md`; do not substitute a shorter generic summary if the detailed rule exists there.
- Treat `../../woodworking/` as the reference library backing the core instructions.
- If the Fusion MCP server is available, use its tools in the mode prescribed by `../../commands/woodworking.md`.
- If the MCP server is not available, still use the same planning and parametric modeling discipline when reasoning about scripts or reviewing generated code.
