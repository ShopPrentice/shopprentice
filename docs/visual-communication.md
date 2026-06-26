# Visual Communication — sketch a concept for the user before building

**Claude Code only · optional.** This requires BOTH the `show_widget` tool (the `visualize` /
"Imagine — Visual Creation Suite" MCP server) AND the ability to spawn sub-agents. If you do
not have both, IGNORE this file — it is an optional communication aid, not part of any build.
Other agents (e.g. Codex) and the build itself never depend on it; fall back to a clear text
description and post-build screenshots (`docs/screenshots.md`).

## Why and when

A scaled drawing of a joint or structure communicates shape and proportion far better than
prose, and it catches a misunderstanding *before* you commit geometry (much cheaper than
rebuilding). Reach for it when:

- a joint's shape or its **hidden internals** matter — a cross-section a screenshot can't show;
- you're **comparing** two or three design options;
- you want to **confirm a structural choice** with the user (wall thickness, tenon depth, …).

Do NOT diagram every part — only when a picture genuinely beats words. Once the model is built,
use real screenshots (`docs/screenshots.md`), not a hand-drawn SVG.

## Architecture: author in a sub-agent, render in the main agent

The `show_widget` onboarding (`read_me`) is large (~tens of KB) and SVG authoring is iterative —
neither belongs in your (main) context. AND, verified empirically: **a widget rendered by a
sub-agent is trapped in the sub-agent's hidden context and never reaches the user.** So split it:

1. **Sub-agent authors.** Spawn a sub-agent with the dimensions + what to draw. It loads
   `read_me`, does the layout math, and RETURNS the markup as `{title, loading_messages, svg}`.
   It does NOT call `show_widget`.
2. **Main agent renders.** You receive the compact SVG string and make the single `show_widget`
   call, so it appears in the user's chat.

Your context then holds only the spawn prompt + the ~2 KB returned SVG + one tool call. For more
diagrams in the same session, re-message the SAME sub-agent (e.g. `SendMessage` by its id) so
`read_me` stays loaded and follow-ups skip the onboarding. If your harness can't re-address an
existing sub-agent, just spawn a fresh one per diagram — it re-pays the onboarding, but the
architecture is unchanged.

## How — main agent

There is no registered viz agent type; spawn a general-purpose sub-agent with a prompt built from
this template, filling in the real dimensions (substitute the absolute repo path for `<REPO>`):

> You are a visualization specialist. Load the visualize guidance with
> `read_me(modules:["diagram"])` (use ToolSearch first if the visualize tools are deferred), then
> read `<REPO>/docs/visual-communication.md` (sections "Authoring rules" and "Patterns"). Draw, TO
> SCALE from these dimensions, a `<cross-section | exploded view | comparison>` of `<subject>`:
> `<list every dimension, the grain direction of each part, and exactly what to highlight>`.
> Return ONLY a JSON object: `{ "title": "...", "loading_messages": [...], "svg": "<svg ...>" }`.
> Do NOT call show_widget — the main agent will render it.

Then render it: `show_widget(title, loading_messages, widget_code=svg)`.

Getting the JSON back: in a **workflow**, `agent(..., {schema})` validates it for you. With the plain
**Agent tool** there is no schema option — the template already says "return ONLY the JSON", so parse
the returned text yourself.

## Authoring rules (for the sub-agent)

- Call `read_me(["diagram"])` FIRST — it is the authoritative, current spec; follow it over this
  summary if they ever disagree.
- **Draw to scale.** Compute every coordinate from the real dimensions (inches/mm → px at a fixed
  scale). Never eyeball proportions — an accurate picture is the whole point.
- **viewBox `0 0 680 H`** unless `read_me` says otherwise (the 680 makes units render ~1:1 with CSS
  px). Center narrow content; set H to the lowest element + ~40px.
- **Theme classes only — never hardcoded hex** (must read in light AND dark mode): shape fills use
  the `c-*` ramps (`c-amber`, `c-blue`, `c-teal`, …); every `<text>` gets a class (`t`, `ts`, `th`);
  leader/dimension lines use the prebuilt `class="leader"` (thin dashed); other neutral strokes use
  the short aliases `var(--t)` / `var(--s)` / `var(--p)`; a *colored* connector stroke uses an inline
  mid-ramp hex, never a `c-*` class on the line. (`read_me` is authoritative — defer to it.)
- **`c-*` placement:** put the class on the shape itself or the innermost group around the shapes —
  never on a wrapper `<g>` (grandchildren lose the fill and render black) and never on a `<path>`.
- Root `<svg>` carries `role="img"` with `<title>` and `<desc>` as its first children.
- **≤2 color ramps**, sentence-case labels, sparse — put detail in the text reply, not the
  drawing. Let color encode meaning (e.g. one ramp = solid stock, another = the part in focus).
- A feature too small to see (a thin web, a kerf): exaggerate it, draw a leader line, and label it
  "(not to scale)" rather than rendering it invisibly thin.

## Patterns

- **Joint cross-section** — slice the section plane (e.g. the Y–Z plane through a node); show the
  host outline, the mating part(s) filled in a focus color, the walls/relish, and dimension
  callouts. (This is what communicated the mitered strut→spine tenon.)
- **Exploded / assembly** — members pulled apart along their insertion axes, with motion arrows.
- **Plan / elevation** — a dimensioned 2-D outline for overall proportions.
- **Option comparison** — two or three small sections side by side, one per design choice.

## Cost

The drawing itself is cheap (~a few hundred output tokens of SVG). The only large cost is the
one-time `read_me` onboarding, and it lives in the SUB-AGENT's context, never yours — paid once
per session if you reuse the sub-agent via `SendMessage`.
