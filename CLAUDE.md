# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

The GitHub profile repository for `pushpam2404` (its `README.md` is rendered on the profile page). There is no build system, package manifest, linter or test suite. The only code is one stdlib-only Python script plus two GitHub Actions workflows.

## Commands

Regenerate the contribution graph locally (needs an authenticated `gh` CLI, or `GITHUB_TOKEN`/`GH_TOKEN` set):

```
python3 scripts/build_contribution_graph.py pushpam2404 contributions.svg
```

Both arguments are optional and default to `pushpam2404` and `contributions.svg`. The GraphQL contributions calendar needs authentication, so the script cannot run without a token.

## Architecture

Two generated images are embedded in `README.md` under "Activity", and the two are produced differently:

- **`contributions.svg`** is committed to `main`. `scripts/build_contribution_graph.py` renders it (dark background, rose ramp), and `.github/workflows/contribution-graph.yml` rebuilds it daily at 01:30 UTC. The workflow also runs on pushes to `main` that touch the script or the workflow file. It commits only when the file changed, with the message `chore: refresh contribution graph [skip ci]`. That is where the bot commits in `git log` come from. The script is self-hosted deliberately: third-party graph hosts hardcode a light grey for empty days or are out of quota.
- **The snake animation** is not in the repo. `.github/workflows/snake.yml` (daily, 02:00 UTC) uses `Platane/snk/svg-only` and publishes to the `output` branch, which `README.md` references via a `raw.githubusercontent.com/.../output/...` URL. It is kept off `main` so the daily run adds no commits there.

Script details that span several parts of the file:

- `fetch()` tries `gh api graphql` first, then falls back to a direct urllib request with a token.
- `build()` picks the colour thresholds from quartiles of this user's non-zero daily counts, so the ramp adapts to activity level. The `level()` function maps a count to the 0 (empty) to 4 (brightest) levels.
- The SVG is built as a list of strings with no templating or SVG library. The layout constants (`CELL`, `GAP`, `PAD_*`, `LABEL_W`) at the top drive every coordinate, including the month labels and legend.

## Editing notes

- `contributions.svg` is generated output. Change the script and regenerate; don't hand-edit the SVG.
- The CI workflow runs on `github.repository_owner`, so the script's username argument is the repo owner there.
- `assets/banner.svg` and `assets/divider.svg` are hand-written SVGs (rose/blush/champagne palette, SMIL animation) referenced from the README by relative path, as are the uniform `assets/pill-*.svg` link buttons used in the projects table. Edit them directly and check them with `xmllint --noout`.
- `README.md` holds the profile content (projects, stack, hackathons). Recent history shows it is kept deliberately short and factual; keep claims in it accurate.
