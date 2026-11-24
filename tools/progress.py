"""Build docs/PROGRESS.md from the task board.

Usage: python -I tools/progress.py <issues.json> <pulls.json> [results dir] [--svg docs/images/progress.svg]
       > docs/PROGRESS.md
The JSON files are GitHub API listings (issues?state=all&labels=task, pulls?state=all); the workflow fetches them.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import results  # noqa: E402

AREAS = ["shaders", "results", "system", "graphics", "audio", "storage", "input", "platforms", "infra", "docs",
         "i18n"]


PHASES = [
    ("0", "Foundation", "the bot, the rules and the docs that let anyone join"),
    ("1", "Shared knowledge", "tests that define correct behaviour, checked on real hardware"),
    ("2", "Adapters", "running other projects' translators against those tests"),
    ("3", "Upstream fixes", "fixing what the tests find, in the projects themselves"),
    ("4", "Shared components", "pieces several projects need and nobody has yet"),
]


def label_names(issue):
    return {l["name"] if isinstance(l, dict) else l for l in issue.get("labels", [])}


def phase_of(issue):
    for name in label_names(issue):
        if name.startswith("phase:"):
            return name[6:]
    return None


def count(issues, key):
    table = {}
    for i in issues:
        if "pull_request" in i:
            continue
        table.setdefault(key(i), {"done": 0, "claimed": 0, "ready": 0, "waiting": 0})[state_of(i)] += 1
    return table


def svg(by_area):
    """A horizontal stacked bar per area: done, in progress, ready, waiting. Self-contained, no external fonts."""
    colors = {"done": "#2da44e", "claimed": "#bf8700", "ready": "#0969da", "waiting": "#d0d7de"}
    rows = [a for a in AREAS + sorted(set(by_area) - set(AREAS)) if a in by_area]
    w, label_w, bar_w, row_h = 640, 110, 470, 26
    h = 40 + row_h * len(rows) + 30
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
           'font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="13">',
           f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
           '<text x="10" y="24" font-size="15" font-weight="600" fill="#1f2328">Tasks by area</text>']
    for i, a in enumerate(rows):
        r = by_area[a]
        total = sum(r.values()) or 1
        y = 40 + i * row_h
        out.append(f'<text x="10" y="{y + 15}" fill="#1f2328">{a}</text>')
        x = label_w
        for k in ("done", "claimed", "ready", "waiting"):
            bw = bar_w * r[k] / total
            if bw:
                out.append(f'<rect x="{x:.1f}" y="{y + 3}" width="{bw:.1f}" height="16" fill="{colors[k]}"/>')
            x += bw
        out.append(f'<text x="{label_w + bar_w + 8}" y="{y + 15}" fill="#57606a">{r["done"]}/{total}</text>')
    ly = 40 + row_h * len(rows) + 14
    x = 10
    for k, name in (("done", "done"), ("claimed", "in progress"), ("ready", "ready to take"),
                    ("waiting", "waiting on other tasks")):
        out.append(f'<rect x="{x}" y="{ly - 10}" width="12" height="12" fill="{colors[k]}"/>')
        out.append(f'<text x="{x + 17}" y="{ly}" fill="#57606a">{name}</text>')
        x += 30 + 8 * len(name)
    out.append("</svg>")
    return "\n".join(out) + "\n"


def area_of(issue):
    for l in issue.get("labels", []):
        name = l["name"] if isinstance(l, dict) else l
        if name.startswith("area:"):
            return name[5:]
    return "unsorted"


def state_of(issue):
    names = {l["name"] if isinstance(l, dict) else l for l in issue.get("labels", [])}
    if issue["state"] == "closed":
        return "done"
    if issue.get("assignees"):
        return "claimed"
    return "ready" if "ready" in names else "waiting"


def bar(done, total, width=20):
    if not total:
        return "`" + "·" * width + "`"
    n = round(width * done / total)
    return "`" + "█" * n + "·" * (width - n) + "`"


def render(issues, pulls, result_rows, generated):
    table = count(issues, area_of)
    phases = count(issues, lambda i: phase_of(i) or "?")
    total = {k: sum(v[k] for v in table.values()) for k in ("done", "claimed", "ready", "waiting")}
    all_tasks = sum(total.values())
    merged = [p for p in pulls if p.get("merged_at")]
    people = {p["user"]["login"] for p in merged}
    out = [
        "# Progress",
        "",
        f"Generated {generated} from the task board by `tools/progress.py`. Do not edit by hand.",
        "",
        f"**{total['done']} of {all_tasks} tasks done** {bar(total['done'], all_tasks)} · "
        f"{total['claimed']} in progress · {total['ready']} ready to take · {total['waiting']} waiting on others · "
        f"{len(merged)} pull requests merged by {len(people)} contributors",
        "",
        "![Tasks by area](images/progress.svg)",
        "",
        "## Phases",
        "",
        "| Phase | What it means | Progress | Done |",
        "|---|---|---|---:|",
    ]
    for num, name, means in PHASES:
        r = phases.get(num, {"done": 0, "claimed": 0, "ready": 0, "waiting": 0})
        n = sum(r.values())
        out.append(f"| {num}. {name} | {means} | {bar(r['done'], n, 10)} | {r['done']}/{n} |")
    out += [
        "",
        "## Areas",
        "",
        "| Area | Progress | Done | In progress | Ready | Waiting |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for a in AREAS + sorted(set(table) - set(AREAS)):
        if a not in table:
            continue
        r = table[a]
        n = sum(r.values())
        out.append(f"| {a} | {bar(r['done'], n, 10)} | {r['done']} | {r['claimed']} | {r['ready']} | {r['waiting']} |")
    out += ["", "## Hardware results", ""]
    if result_rows:
        out += ["| Status | Test | Commit | Hardware | Reporters |", "|---|---|---|---|---:|"]
        for (test, commit, hw), (status, by) in sorted(result_rows.items()):
            out.append(f"| {status} | {test} | `{commit[:9]}` | {hw} | {sum(len(u) for u in by.values())} |")
    else:
        out.append("No reports yet. See docs/results.md.")
    out += ["", "Take a ready task: see docs/getting-started.md.", ""]
    return "\n".join(out)


def main():
    import datetime as dt
    with open(sys.argv[1], encoding="utf-8") as f:
        issues = json.load(f)
    with open(sys.argv[2], encoding="utf-8") as f:
        pulls = json.load(f)
    rows = {}
    if len(sys.argv) > 3 and not sys.argv[3].startswith("--") and os.path.isdir(sys.argv[3]):
        reports, _ = results.load(sys.argv[3])
        rows = results.consensus(reports)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if "--svg" in sys.argv:
        with open(sys.argv[sys.argv.index("--svg") + 1], "w", encoding="utf-8", newline="\n") as f:
            f.write(svg(count(issues, area_of)))
    sys.stdout.buffer.write(render(issues, pulls, rows, now).encode("utf-8"))


if __name__ == "__main__":
    main()
