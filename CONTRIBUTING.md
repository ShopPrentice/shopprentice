# Contributing to ShopPrentice

ShopPrentice needs two kinds of contributions: **code** (tools, templates, bug fixes) and **woodworking knowledge** (furniture types, styles, joinery techniques). Both are equally valuable.

## Ways to Contribute

### 1. Build something and report what happened

The most valuable contribution is simply using ShopPrentice to build furniture, then telling us what worked and what didn't. Open an issue with:

- What you asked for (the prompt)
- What went wrong or could be better
- Screenshots from Fusion 360

This is how the skill learns — through real build sessions, not Wikipedia articles.

### 2. Add a furniture type guide

Type guides tell the agent what components a piece of furniture needs, how they connect, and what hardware is required. They live in `docs/types/`.

To add one:
1. Copy `docs/types/TEMPLATE.md`
2. Fill in every section — components, connections, hardware, build order, common mistakes
3. Submit a PR

**What makes a good type guide:** It should capture knowledge that isn't obvious from the name alone. "A bookshelf has shelves" is not useful. "Shelf pins need 5mm holes at 32mm spacing, and the shelf should be 1/16" narrower than the case interior" is.

### 3. Add a style guide

Style guides define aesthetic choices — proportions, edge treatments, hardware preferences, wood species. They live in `docs/styles/`.

Copy `docs/styles/TEMPLATE.md` and fill it in. See `docs/styles/modern.md` for a complete example.

### 4. Add a joinery reference

Joinery references explain how to model a specific joint type in Fusion 360 using the parametric approach. They live in `joinery/`.

See existing files like `joinery/domino-joint.md` for the format. Key sections: when to use it, sizing rules, orientation rules, and the combine-based modeling approach.

### 5. Add an example

Complete furniture projects with scripts and screenshots. See `examples/` for the format:
1. Create `examples/<name>/`
2. Add the `.py` script, `README.md`, and `screenshots/` folder
3. Include at least an iso view screenshot

### 6. Add a joinery template

Python templates that encapsulate complex joinery into single function calls. These live in `addin/helpers/templates/`. See existing templates for the pattern — they use `sp.py` helpers and follow the combine-based approach (build shape, CUT receiver, JOIN to owner).

### 7. Bug fixes and tool improvements

Standard PR workflow. See Development Setup below.

## What NOT to submit

- Generic woodworking knowledge that an LLM already knows (wood species properties, basic tool usage)
- Changes to the main skill file (`commands/woodworking.md`) without testing against multiple furniture types — this file affects every build and regressions are common
- Style-specific rules in type guides, or type-specific rules in the main skill

## Development Setup

```bash
git clone https://github.com/ShopPrentice/shopprentice.git
cd shopprentice
./install.sh --all
```

This sets up the Claude Code skill and the Fusion 360 add-in.

### Running tests

```bash
# Unit tests (no Fusion required)
python -m pytest tests/test_document_tracker.py

# Round-trip tests (requires Fusion 360 running with add-in)
python -m pytest tests/test_round_trip.py
```

### Testing skill changes

Skill changes (`commands/woodworking.md`, `woodworking/`) are the hardest to test because they affect AI behavior across all builds. Before submitting changes to these files:

1. Build at least 2 different furniture types with your changes
2. Verify the builds complete without errors
3. Note any regressions from previous behavior

## PR Guidelines

- Keep PRs focused — one type guide, one template, one bug fix
- For knowledge contributions (types, styles, joinery), explain how you validated it (built with it, based on professional experience, etc.)
- For code changes, include before/after screenshots if the change affects model output

## Questions?

Open an issue or start a discussion. We're friendly.
