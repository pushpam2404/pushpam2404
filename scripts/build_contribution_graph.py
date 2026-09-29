#!/usr/bin/env python3
"""Render the contribution graph as an SVG with a dark background and a pink ramp.

Why this exists rather than a third-party image host: every embeddable
contribution-graph service either hardcodes a light grey for empty days
(ghchart) or is out of quota (github-readme-activity-graph returns HTTP 402).
Generating it here means the colours are exactly what we want and the graph
cannot break because somebody else's free Vercel plan ran out.

Colour rule: a day with no contributions is dark, and the pink deepens as the
count rises.

Usage:
    python3 scripts/build_contribution_graph.py <github-username> <output.svg>

Needs a token in GITHUB_TOKEN or GH_TOKEN (the contributions calendar is only
available through the GraphQL API, which requires authentication).
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

BACKGROUND = "#0D1117"
EMPTY = "#161B22"          # a day with zero contributions
RAMP = [
    "#FFC2EC",             # 1  - palest pink
    "#FF7AD4",             # 2
    "#E91E8C",             # 3
    "#A1105E",             # 4  - deepest pink
]
BORDER = "#21262D"
TEXT = "#8B949E"

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


def build(calendar, username):
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]

    # Scale the ramp to this person's actual activity, so the graph stays
    # readable whether their busiest day is 3 commits or 300.
    counts = sorted(d["contributionCount"]
                    for w in weeks for d in w["contributionDays"]
                    if d["contributionCount"] > 0)
    if counts:
        q = [counts[min(len(counts) - 1, int(len(counts) * f))] for f in (0.25, 0.5, 0.75)]
        thresholds = [max(1, q[0]), max(2, q[1]), max(3, q[2])]
    else:
        thresholds = [1, 2, 3]

    width = PAD_X * 2 + LABEL_W + len(weeks) * (CELL + GAP)
    height = PAD_TOP + 7 * (CELL + GAP) + PAD_BOTTOM

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{total} contributions by {username} in the last year">',
        "<style>",
        f"  .lbl {{ font: 400 9px -apple-system, BlinkMacSystemFont, 'Segoe UI', Ubuntu, Sans-Serif; fill: {TEXT}; }}",
        f"  .ttl {{ font: 600 12px -apple-system, BlinkMacSystemFont, 'Segoe UI', Ubuntu, Sans-Serif; fill: #C9D1D9; }}",
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


def main():
    username = sys.argv[1] if len(sys.argv) > 1 else "pushpam2404"
    target = sys.argv[2] if len(sys.argv) > 2 else "contributions.svg"

    calendar = fetch(username)
    svg, total, thresholds = build(calendar, username)

    with open(target, "w", encoding="utf-8") as fh:
        fh.write(svg)

    print(f"wrote {target}")
    print(f"  contributions: {total}")
    print(f"  ramp thresholds (<=): {thresholds}")
    print(f"  empty colour: {EMPTY}  ramp: {' -> '.join(RAMP)}")


if __name__ == "__main__":
    main()
