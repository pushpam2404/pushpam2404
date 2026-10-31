#!/usr/bin/env python3
"""Render the contribution graph as an SVG with a dark background and a rose ramp.

Why this exists rather than a third-party image host: every embeddable
contribution-graph service either hardcodes a light grey for empty days
(ghchart) or is out of quota (github-readme-activity-graph returns HTTP 402).
Generating it here means the colours are exactly what we want and the graph
cannot break because somebody else's free Vercel plan ran out.

Colour rule: a day with no contributions is dark, and the rose brightens as the
count rises.

The same run also writes a snake animation. It is drawn here rather than with
a third-party action because those let the snake wander outside the grid; this
one sweeps column by column and stays inside it.

Usage:
    python3 scripts/build_contribution_graph.py <github-username> <graph.svg> <snake.svg>

Needs a token in GITHUB_TOKEN or GH_TOKEN (the contributions calendar is only
available through the GraphQL API, which requires authentication).
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

BACKGROUND = "#0F0809"
EMPTY = "#1E1417"          # a day with zero contributions
RAMP = [
    "#7A4350",             # 1  - dimmest rose
    "#b76e79",             # 2
    "#e8b4b8",             # 3
    "#f7e7ce",             # 4  - brightest (champagne)
]
BORDER = "#33171F"
TEXT = "#a8838a"

CELL = 11                  # square size
GAP = 3
RADIUS = 2
PAD_X = 20
PAD_TOP = 42
PAD_BOTTOM = 30
LABEL_W = 28               # room for Mon / Wed / Fri

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

QUERY = """
{
  user(login: "%s") {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
    }
  }
}
"""


def fetch(username):
    """Prefer the gh CLI (already authenticated); fall back to a raw token."""
    query = QUERY % username
    try:
        out = subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={query}"],
            capture_output=True, text=True, check=True,
        ).stdout
        return json.loads(out)["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("No gh CLI and no GITHUB_TOKEN/GH_TOKEN — cannot read the calendar.")

    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"bearer {token}",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.loads(r.read())
    except urllib.error.HTTPError as exc:
        sys.exit(f"GitHub API returned {exc.code}: {exc.read()[:200]!r}")

    if "errors" in payload:
        sys.exit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def level(count, thresholds):
    """0 for an empty day, then 1-4 as the count climbs."""
    if count <= 0:
        return 0
    for i, t in enumerate(thresholds):
        if count <= t:
            return i + 1
    return len(RAMP)


def ramp_thresholds(weeks):
    """Scale the ramp to this person's actual activity, so the graph stays
    readable whether their busiest day is 3 commits or 300."""
    counts = sorted(d["contributionCount"]
                    for w in weeks for d in w["contributionDays"]
                    if d["contributionCount"] > 0)
    if not counts:
        return [1, 2, 3]
    q = [counts[min(len(counts) - 1, int(len(counts) * f))] for f in (0.25, 0.5, 0.75)]
    return [max(1, q[0]), max(2, q[1]), max(3, q[2])]


def build(calendar, username):
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]

    thresholds = ramp_thresholds(weeks)

    width = PAD_X * 2 + LABEL_W + len(weeks) * (CELL + GAP)
    height = PAD_TOP + 7 * (CELL + GAP) + PAD_BOTTOM

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{total} contributions by {username} in the last year">',
        "<style>",
        f"  .lbl {{ font: 400 9px -apple-system, BlinkMacSystemFont, 'Segoe UI', Ubuntu, Sans-Serif; fill: {TEXT}; }}",
        f"  .ttl {{ font: 600 12px -apple-system, BlinkMacSystemFont, 'Segoe UI', Ubuntu, Sans-Serif; fill: #f7e7ce; }}",
        "</style>",
        f'<rect width="{width}" height="{height}" rx="6" fill="{BACKGROUND}" stroke="{BORDER}"/>',
        f'<text x="{PAD_X}" y="20" class="ttl">{total} contributions in the last year</text>',
    ]

    # Month labels, printed once when a month first appears. A month is skipped
    # when its label would sit on top of the previous one, which happens
    # whenever the year window opens mid-month.
    seen = set()
    last_x = -999
    for wi, week in enumerate(weeks):
        first = week["contributionDays"][0]["date"]
        year, month = first[:4], int(first[5:7])
        if (year, month) in seen:
            continue
        seen.add((year, month))
        x = PAD_X + LABEL_W + wi * (CELL + GAP)
        if x - last_x < 34 or x > width - PAD_X - 24:
            continue
        last_x = x
        out.append(f'<text x="{x}" y="{PAD_TOP - 8}" class="lbl">{MONTHS[month - 1]}</text>')

    for name, wd in (("Mon", 1), ("Wed", 3), ("Fri", 5)):
        y = PAD_TOP + wd * (CELL + GAP) + CELL - 2
        out.append(f'<text x="{PAD_X}" y="{y}" class="lbl">{name}</text>')

    for wi, week in enumerate(weeks):
        for day in week["contributionDays"]:
            count = day["contributionCount"]
            lv = level(count, thresholds)
            fill = EMPTY if lv == 0 else RAMP[lv - 1]
            x = PAD_X + LABEL_W + wi * (CELL + GAP)
            y = PAD_TOP + day["weekday"] * (CELL + GAP)
            plural = "" if count == 1 else "s"
            out.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="{RADIUS}" '
                f'fill="{fill}"><title>{count} contribution{plural} on {day["date"]}</title></rect>'
            )

    # Legend
    ly = height - 16
    lx = width - PAD_X - (len(RAMP) + 1) * (CELL + GAP) - 58
    out.append(f'<text x="{lx - 26}" y="{ly + CELL - 2}" class="lbl">Less</text>')
    for i, colour in enumerate([EMPTY, *RAMP]):
        out.append(
            f'<rect x="{lx + i * (CELL + GAP)}" y="{ly}" width="{CELL}" height="{CELL}" '
            f'rx="{RADIUS}" fill="{colour}"/>'
        )
    out.append(
        f'<text x="{lx + (len(RAMP) + 1) * (CELL + GAP) + 4}" y="{ly + CELL - 2}" class="lbl">More</text>'
    )
    out.append("</svg>")
    return "\n".join(out), total, thresholds


SNAKE = ["#e8b4b8", "#d99ea4", "#c98791", "#b76e79", "#a05a66"]   # head to tail
SNAKE_STEP = 0.04          # seconds per cell
SNAKE_HOLD = 2.5           # seconds the finished snake rests before the loop restarts


def build_snake(calendar):
    """A snake that zig-zags down one week, up the next, eating every
    contribution on the way. It never leaves the grid."""
    weeks = calendar["weeks"]
    thresholds = ramp_thresholds(weeks)
    pitch = CELL + GAP
    width = PAD_X * 2 + len(weeks) * pitch - GAP
    height = 30 + 7 * pitch - GAP

    def centre(wi, row):
        return PAD_X + wi * pitch + CELL / 2, 15 + row * pitch + CELL / 2

    # Walk order: week 0 top to bottom, week 1 bottom to top, and so on.
    path = []
    for wi in range(len(weeks)):
        for row in (range(7) if wi % 2 == 0 else range(6, -1, -1)):
            path.append((wi, row))
    index = {cell: i for i, cell in enumerate(path)}
    total = (len(path) - 1 + len(SNAKE)) * SNAKE_STEP + SNAKE_HOLD

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="A snake eating the contribution graph">',
        f'<rect width="{width}" height="{height}" rx="6" fill="{BACKGROUND}" stroke="{BORDER}"/>',
        "<defs><path id=\"walk\" d=\"" + " ".join(
            f"{'M' if i == 0 else 'L'}{centre(*c)[0]:g} {centre(*c)[1]:g}" for i, c in enumerate(path)
        ) + "\"/></defs>",
    ]

    for wi, week in enumerate(weeks):
        for day in week["contributionDays"]:
            lv = level(day["contributionCount"], thresholds)
            x = PAD_X + wi * pitch
            y = 15 + day["weekday"] * pitch
            rect = f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="{RADIUS}"'
            if lv == 0:
                out.append(f'{rect} fill="{EMPTY}"/>')
                continue
            eaten = index[(wi, day["weekday"])] * SNAKE_STEP / total
            out.append(
                f'{rect} fill="{RAMP[lv - 1]}"><animate attributeName="fill" dur="{total:.2f}s" '
                f'repeatCount="indefinite" calcMode="discrete" keyTimes="0;{eaten:.4f};1" '
                f'values="{RAMP[lv - 1]};{EMPTY};{EMPTY}"/></rect>'
            )

    # Each segment walks the same path, a little later than the one in front.
    for k, colour in reversed(list(enumerate(SNAKE))):
        size = CELL - k
        start = k * SNAKE_STEP / total
        end = (k + len(path) - 1) * SNAKE_STEP / total
        out.append(
            f'<rect x="{-size / 2:g}" y="{-size / 2:g}" width="{size}" height="{size}" rx="{RADIUS}" '
            f'fill="{colour}" stroke="{BACKGROUND}" stroke-width="1">'
            f'<animateMotion dur="{total:.2f}s" repeatCount="indefinite" calcMode="linear" '
            f'keyPoints="0;0;1;1" keyTimes="0;{start:.4f};{end:.4f};1"><mpath href="#walk"/></animateMotion></rect>'
        )
    out.append("</svg>")
    return "\n".join(out)


def main():
    username = sys.argv[1] if len(sys.argv) > 1 else "pushpam2404"
    target = sys.argv[2] if len(sys.argv) > 2 else "contributions.svg"
    snake_target = sys.argv[3] if len(sys.argv) > 3 else "snake.svg"

    calendar = fetch(username)
    svg, total, thresholds = build(calendar, username)

    with open(target, "w", encoding="utf-8") as fh:
        fh.write(svg)

    with open(snake_target, "w", encoding="utf-8") as fh:
        fh.write(build_snake(calendar))

    print(f"wrote {target} and {snake_target}")
    print(f"  contributions: {total}")
    print(f"  ramp thresholds (<=): {thresholds}")
    print(f"  empty colour: {EMPTY}  ramp: {' -> '.join(RAMP)}")


if __name__ == "__main__":
    main()
