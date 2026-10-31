# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

The GitHub profile repository for `pushpam2404` (its `README.md` is rendered on the profile page). There is no build system, package manifest, linter or test suite. The only code is one stdlib-only Python script plus one GitHub Actions workflow.

## Commands

Regenerate the contribution graph locally (needs an authenticated `gh` CLI, or `GITHUB_TOKEN`/`GH_TOKEN` set):

```
python3 scripts/build_contribution_graph.py pushpam2404 contributions.svg snake.svg
```

All arguments are optional and default to `pushpam2404`, `contributions.svg` and `snake.svg`. The GraphQL contributions calendar needs authentication, so the script cannot run without a token.

## Architecture

Two generated images are embedded in `README.md` under "Activity", both produced by `scripts/build_contribution_graph.py` and committed to `main`:

- **`contributions.svg`** is the contribution graph (dark background, rose ramp). It is self-hosted deliberately: third-party graph hosts hardcode a light grey for empty days or are out of quota.
- **`snake.svg`** is a snake animation (SMIL, no JS) drawn by `build_snake()`. `snake_route()` plans it: the snake eats the smallest contributions first, heads for the nearest dot of its current level, and never leaves the grid or steps on its own body. The `Platane/snk` action was dropped because its snake roams outside the grid and that cannot be configured.

`.github/workflows/contribution-graph.yml` rebuilds both daily at 01:30 UTC and on pushes to `main` that touch the script or the workflow file. It commits only when either file changed, with the message `chore: refresh contribution graph [skip ci]`. That is where the bot commits in `git log` come from. The old `output` branch from the `snk` workflow is no longer used.

Script details that span several parts of the file:

- `fetch()` tries `gh api graphql` first, then falls back to a direct urllib request with a token.
- `build()` picks the colour thresholds from quartiles of this user's non-zero daily counts, so the ramp adapts to activity level. The `level()` function maps a count to the 0 (empty) to 4 (brightest) levels.
- The SVG is built as a list of strings with no templating or SVG library. The layout constants (`CELL`, `GAP`, `PAD_*`, `LABEL_W`) at the top drive every coordinate, including the month labels and legend.

## Editing notes

- `contributions.svg` and `snake.svg` are generated output. Change the script and regenerate; don't hand-edit the SVG.
- The CI workflow runs on `github.repository_owner`, so the script's username argument is the repo owner there.
- `assets/banner.svg` and `assets/divider.svg` are hand-written SVGs (rose/blush/champagne palette, SMIL animation) referenced from the README by relative path, as are the uniform `assets/pill-*.svg` link buttons used in the projects table. Edit them directly and check them with `xmllint --noout`.
- `README.md` holds the profile content (projects, stack, hackathons). Recent history shows it is kept deliberately short and factual; keep claims in it accurate.
