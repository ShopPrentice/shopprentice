# Woodworking Skill — Developer Mode

You are improving the woodworking skill based on what we just learned from building a real model. This is a meta-skill: you are updating the teaching material, not building furniture.

## When to Invoke

After completing a build (or a build session with notable discoveries), when the user says things like:
- "What did we learn?"
- "Update the skill with what we found"
- "That pitfall should be documented"
- "Promote that joint to tested"
- "Add this technique to the skill"

## What You Have Access To

### Skill files (the things you're improving)

| File | Purpose |
|------|---------|
| `commands/woodworking.md` | Core skill — design philosophy, API rules, parameter planning, routing tables, build order |
| `docs/angled-construction.md` | Topic: splayed legs, compound angles, Move, Sweep, SplitBody, stretcher splay |
| `docs/details-and-finishing.md` | Topic: fillets, chamfers, edge treatments (planned) |
| `docs/mcp-advanced.md` | Topic: modify existing designs, sync, selection workflow (planned) |

### Joinery reference files (in the repo, not in commands/)

| File | Status |
|------|--------|
| Mortise & Tenon | Tested (inline in skill + `mortise_tenon` template) |
| `docs/joinery/domino-joint.md` | Tested |
| `docs/joinery/dovetail.md` | Tested |
| `docs/joinery/dado-rabbet.md` | Tested |
| `docs/joinery/box-joint.md` | Tested (template) |
| `docs/joinery/bridle-joint.md` | Draft |
| `docs/joinery/lap-joint.md` | Draft |
| `docs/joinery/miter-joint.md` | Draft |
| `docs/joinery/spline-joint.md` | Draft |
| `docs/joinery/dowel-joint.md` | Draft |
| `docs/joinery/pocket-hole.md` | Draft |

Joinery files live at: `~/.shopprentice/repo/joinery/` (or the repo's `joinery/` directory)

### Joinery templates (reusable Python modules in addin/helpers/templates/)

| Template | Status | Used In |
|----------|--------|---------|
| `domino.py` | Tested | bookshelf, counter stool |
| `mortise_tenon.py` | Tested | bookshelf |
| `finger_joint.py` | Tested | (test fixture) |
| `dovetail.py` | Tested | pencil box, wrap box, dresser |
| `half_blind_dovetail.py` | Tested | dresser |
| `splayed_legs.py` | Tested | counter stool |
| `dovetailed_drawer.py` | Tested | dresser |

#### Inline hardware templates

| Template | Status | Used In |
|----------|--------|---------|
| `pull.py` | Tested | (test fixture) |
| `chest_lock.py` | Tested | (test fixture) |

Templates encapsulate complex joinery (4+ features with variant logic) into single function calls. Simple joints (dado/rabbet, T&G) are written inline. Inline hardware templates are limited to non-hinge fixtures such as pulls and chest locks; hinges should use the imported hardware flow in `helpers/hardware.py`.

### Context from the build

- The model script we just built (e.g., `counter_stool.py`)
- The conversation history — errors we hit, workarounds we found, techniques that worked
- Auto-memory (Claude Code's project memory for this repo)

## Workflow

### 1. Identify what we learned

Review the build session. Look for:

- **New techniques** — something we did that isn't in any skill file yet (e.g., stretcher splay matching)
- **Pitfalls discovered** — API gotchas, ordering traps, Fusion quirks that caused errors (e.g., Move after tenon = wrong shoulder)
- **Corrections** — something a skill file says that turned out to be wrong or incomplete
- **Status promotions** — a Draft joint file we actually used successfully in a build

Summarize findings to the user before making changes.

### 2. Decide where each finding goes

| Finding type | Where it goes |
|-------------|---------------|
| New technique for an existing topic | New section in the topic file |
| New pitfall for an existing topic | Add to that topic's Common Pitfalls table |
| New topic area (doesn't fit existing files) | New file in `docs/` + routing entry in `woodworking.md` |
| Joint-specific finding | The specific `docs/joinery/*.md` file |
| Routing gap (agent wouldn't have found the right file) | Update trigger phrases in the routing tables in `woodworking.md` |
| General API rule | Core skill `woodworking.md` |
| Stable pattern confirmed across multiple builds | Auto-memory `MEMORY.md` |

### 3. Write the updates

**Rules for writing skill content:**

- **Ground in the actual build.** Every technique should trace back to real code that ran. Include the pattern/snippet that worked, not a theoretical example.
- **Pitfalls need the symptom, cause, and fix.** "The body flies off" is the symptom. "Forgot pivot compensation" is the cause. "Include T = P - R×P translation" is the fix.
- **Triggers must be furniture features, not joint terminology.** The agent sees "drawer fronts" in a design brief, not "dovetail." Write triggers in terms of what the agent will encounter during planning.
- **Don't pad.** If we learned one thing, write one thing. Don't speculatively fill out sections we haven't tested.
- **Mark confidence.** If something worked once, say "Tested (project name)." If it worked in multiple projects, it's a confirmed pattern. If we're extrapolating, say so.

### 4. Update the routing table

After adding or modifying any topic/joinery file, check the routing tables in `woodworking.md`:
- Are the trigger phrases accurate for what the agent will see during planning?
- Is the Status column correct?
- Does the build order (step 2a-f) reference the new technique at the right moment?

### 5. Update auto-memory if needed

If the finding is a stable pattern (confirmed across 2+ builds), add it to `MEMORY.md`. If it's project-specific, it belongs in the skill files only — not memory.

## Status Promotion Rules

| Current | Promote to | Requirement |
|---------|-----------|-------------|
| Draft | Tested (project) | Built end-to-end in a real model. All API calls verified. Pitfalls section reflects actual errors encountered. |
| Tested (1 project) | Tested (multiple) | Used successfully in a second, different project. |
| Planned (no file) | Draft | File created with plausible content, but not yet built. |
| Planned (no file) | Tested | File created AND validated through a real build in the same session. |

## Skill Validation

After updating the skill files, validate that the documentation is sufficient to guide a fresh build without prior knowledge of the project.

### Process

1. **Design a similar-but-different project** that exercises the same techniques as the build you just completed. Change the piece type, dimensions, and proportions — but keep the same structural challenges (e.g., if you built a counter stool with splayed legs and angled tenons, test with a bar-height side table with splayed legs and angled tenons).

2. **Launch a subagent** (via the Agent tool) with a design brief for the new piece. The subagent:
   - Invokes `/woodworking` to load the skill
   - Plans and generates the full script
   - Writes the script to a file (e.g., `/tmp/validation_<name>.py`)
   - Does NOT have MCP access — it only generates code

3. **Execute the generated script** yourself via MCP (`execute_script`) on a scratch document. Validate with `capture_design`.

4. **Assess results:**
   - **Script runs clean, correct body count** → skill documentation is sufficient
   - **Script has errors** → identify whether the cause is a documentation gap (missing technique, unclear instruction, wrong build order) vs. a one-off bug (typo, wrong variable name)
   - **Documentation gaps** → update the skill files and re-run validation

### Design Brief Template

> Build me a [piece]: [key dimensions], [number] splayed legs ([angles]), [stretcher/rail arrangement] with [joint type], [other joints] connecting [parts], [detail features]. Use `/woodworking`.

Keep the brief at the same level of detail a real user would provide — don't over-specify implementation details.

### What This Tests

- Routing tables lead to the right topic/joinery files
- Build order is correct for the techniques involved
- Technique descriptions are complete enough to generate working code
- Pitfall warnings prevent known errors
- Parameter planning guidance produces correct expressions

### When to Skip

- Trivial changes (typo fixes, wording improvements, status promotions without new content)
- Changes only to memory or routing — no new technique content

## Anti-Patterns

- **Don't write speculative pitfalls.** "This might fail if..." — either we saw it fail or we didn't. Document what happened.
- **Don't bulk-update Draft files without building.** Each Draft file gets promoted by actually building something that uses it.
- **Don't duplicate between skill files and MEMORY.md.** Skill files are the authoritative source for techniques. Memory is for workflow preferences and cross-cutting patterns.
- **Don't rewrite working sections.** If a section is already tested and accurate, leave it alone. Add to it, don't reorganize it.
