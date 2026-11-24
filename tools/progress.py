"""Build docs/PROGRESS.md from the task board.

Usage: python -I tools/progress.py <issues.json> <pulls.json> [results dir]  > docs/PROGRESS.md
The JSON files are GitHub API listings (issues?state=all&labels=task, pulls?state=all); the workflow fetches them.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import results  # noqa: E402

AREAS = ["shaders", "results", "system", "graphics", "audio", "storage", "input", "platforms", "infra", "docs",
         "i18n"]


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
    table = {}
    for i in issues:
        if "pull_request" in i:
            continue
        a = area_of(i)
        table.setdefault(a, {"done": 0, "claimed": 0, "ready": 0, "waiting": 0})[state_of(i)] += 1
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
    if len(sys.argv) > 3 and os.path.isdir(sys.argv[3]):
        reports, _ = results.load(sys.argv[3])
        rows = results.consensus(reports)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sys.stdout.buffer.write(render(issues, pulls, rows, now).encode("utf-8"))


if __name__ == "__main__":
    main()
