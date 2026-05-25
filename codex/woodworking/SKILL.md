---
name: woodworking
description: Use when the user wants to design, modify, or analyze parametric furniture in Fusion 360 with ShopPrentice. Applies to greenfield builds, additive edits to existing models, joinery, hardware, lofted/organic forms, screenshots, and Fusion MCP workflows.
metadata:
  short-description: Fusion 360 parametric furniture modeling with ShopPrentice
---

# ShopPrentice For Codex

ShopPrentice's primary operating rules live in [`WOODWORKING.md`](WOODWORKING.md). Read that file first when this skill is invoked. It is a generated local copy of the canonical `commands/woodworking.md`, with the user's screenshot-mode config applied at install time.

Then load only the supporting references you need from the ShopPrentice repo:

- `__REPO_DIR__/docs/mcp-advanced.md` for additive mode, proxy/body lookup patterns, and working against existing user-built models
- `__REPO_DIR__/docs/joinery.md` and `__REPO_DIR__/docs/joinery/*.md` for specific joint construction rules
- `__REPO_DIR__/docs/organic-shapes.md` and `__REPO_DIR__/docs/loft.md` for spline, loft, turned, and sculpted forms
- `__REPO_DIR__/docs/templates-and-hardware.md`, `__REPO_DIR__/docs/hardware-installation.md`, and `__REPO_DIR__/woodworking/templates/*.py` for reusable hardware and joinery templates
- `__REPO_DIR__/docs/appearance.md`, `__REPO_DIR__/docs/details-and-finishing.md`, and `__REPO_DIR__/docs/screenshots.md` for finish passes and presentation output
- `__REPO_DIR__/docs/types/*.md` and `__REPO_DIR__/docs/styles/*.md` when the user asks for a specific furniture type or style
- `__REPO_DIR__/docs/fusion-api-rules.md`, `__REPO_DIR__/docs/helpers-reference.md`, and `__REPO_DIR__/docs/incremental-updates.md` for implementation details and update workflows

## Codex Notes

- Before collecting build details or reading deep references, do a Fusion MCP preflight for ShopPrentice requests. If the Codex session is network-sandboxed (for example `CODEX_SANDBOX_NETWORK_DISABLED=1`), stop immediately and tell the user how to continue based on client:
  App: enable full access when prompted, then continue.
  CLI: relaunch the same session with `codex resume <SESSION_ID> --dangerously-bypass-approvals-and-sandbox -C __REPO_DIR__`.
  Use the current Codex session/thread id as `<SESSION_ID>`.
- Preserve the rules and workflow from `WOODWORKING.md`; do not substitute a shorter generic summary if the detailed rule exists there.
- Treat `__REPO_DIR__/docs/` as the reference library backing the core instructions.
- If the Fusion MCP server is available, use its tools in the mode prescribed by `WOODWORKING.md`.
- If the MCP server is not available, still use the same planning and parametric modeling discipline when reasoning about scripts or reviewing generated code.
