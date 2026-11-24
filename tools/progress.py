"""Build docs/PROGRESS.md from the task board.

Usage: python -I tools/progress.py <issues.json> <pulls.json> [results dir] [--svg FILE] [--badges DIR] [--cases DIR]
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


STATE_ICON = {"done": "✅", "claimed": "🔨", "ready": "🟦", "waiting": "⏳"}
STATE_WORD = {"done": "done", "claimed": "in progress", "ready": "ready to take", "waiting": "waiting on others"}


def badge(label, value, color):
    """A flat badge in the usual two-part style, self-contained SVG."""
    lw, vw = 7 * len(label) + 12, 7 * len(str(value)) + 12
    w = lw + vw
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" role="img" aria-label="{label}: {value}">'
            f'<rect width="{lw}" height="20" fill="#555"/><rect x="{lw}" width="{vw}" height="20" fill="{color}"/>'
            '<g fill="#fff" font-family="Verdana, DejaVu Sans, sans-serif" font-size="11" text-anchor="middle">'
            f'<text x="{lw / 2}" y="14">{label}</text><text x="{lw + vw / 2}" y="14">{value}</text></g></svg>\n')


def badges(issues, pulls, result_rows, case_count):
    tasks = [i for i in issues if "pull_request" not in i]
    done = sum(1 for i in tasks if state_of(i) == "done")
    ready = sum(1 for i in tasks if state_of(i) == "ready")
    confirmed = sum(1 for s, _ in result_rows.values() if s == "CONFIRMED")
    merged = [p for p in pulls if p.get("merged_at")]
    phase = next((num for num, _, _ in PHASES
                  if any(phase_of(i) == num and state_of(i) != "done" for i in tasks)), "4")
    return {
        "tasks": badge("tasks", f"{done}/{len(tasks)} done", "#2da44e"),
        "ready": badge("ready to take", ready, "#0969da"),
        "phase": badge("phase", f"{phase} of 4", "#8250df"),
        "cases": badge("test cases", case_count, "#bf8700"),
        "results": badge("confirmed on hardware", confirmed, "#1a7f37" if confirmed else "#6e7781"),
        "contributors": badge("contributors", len({p["user"]["login"] for p in merged}), "#cf222e"),
    }


def task_line(i):
    st = state_of(i)
    who = ", ".join("@" + a["login"] for a in i.get("assignees", []))
    url = i.get("html_url", f"../../issues/{i['number']}")
    title = i.get("title", f"#{i['number']}").replace("|", "\\|")
    return f"| {STATE_ICON[st]} | [#{i['number']}]({url}) {title} | {area_of(i)} | {who or '—'} |"


def render(issues, pulls, result_rows, generated, cases_by_group=None):
    tasks = [i for i in issues if "pull_request" not in i]
    table = count(tasks, area_of)
    phases = count(tasks, lambda i: phase_of(i) or "?")
    total = {k: sum(v[k] for v in table.values()) for k in ("done", "claimed", "ready", "waiting")}
    all_tasks = sum(total.values())
    merged = sorted((p for p in pulls if p.get("merged_at")), key=lambda p: p["merged_at"], reverse=True)
    people = {}
    for p in merged:
        people[p["user"]["login"]] = people.get(p["user"]["login"], 0) + 1
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
        "Legend: ✅ done · 🔨 in progress · 🟦 ready to take · ⏳ waiting on other tasks",
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
    order = {"claimed": 0, "ready": 1, "waiting": 2, "done": 3}
    for num, name, means in PHASES + [("?", "No phase yet", "")]:
        mine = [i for i in tasks if (phase_of(i) or "?") == num]
        if not mine:
            continue
        out += ["", f"## Phase {num}: {name}" if num != "?" else "## Tasks without a phase", ""]
        if means:
            out += [f"*{means[0].upper() + means[1:]}.*", ""]
        out += ["| | Task | Area | Who |", "|---|---|---|---|"]
        out += [task_line(i) for i in sorted(mine, key=lambda i: (order[state_of(i)], i["number"]))]
    out += ["", "## Test cases", ""]
    if cases_by_group:
        out += ["| Group | Cases |", "|---|---:|"]
        out += [f"| {g} | {n} |" for g, n in sorted(cases_by_group.items())]
        out += ["", f"**{sum(cases_by_group.values())} cases** in `cases/` (format: docs/test-format.md)."]
    else:
        out.append("No cases yet.")
    out += ["", "## Hardware results", ""]
    if result_rows:
        out += ["| Status | Test | Commit | Hardware | Reporters |", "|---|---|---|---|---:|"]
        for (test, commit, hw), (status, by) in sorted(result_rows.items()):
            out.append(f"| {status} | {test} | `{commit[:9]}` | {hw} | {sum(len(u) for u in by.values())} |")
    else:
        out.append("No reports yet. See docs/results.md.")
    out += ["", "## Recently merged", ""]
    if merged:
        out += ["| Date | Pull request | Author |", "|---|---|---|"]
        for p in merged[:15]:
            num = p.get("number", "?")
            title = p.get("title", "").replace("|", "\\|")
            url = p.get("html_url", f"../../pull/{num}")
            out.append(f"| {p['merged_at'][:10]} | [#{num}]({url}) {title} | @{p['user']['login']} |")
    else:
        out.append("Nothing merged yet.")
    out += ["", "## Contributors", ""]
    if people:
        out += ["| Contributor | Merged pull requests |", "|---|---:|"]
        out += [f"| @{u} | {n} |" for u, n in sorted(people.items(), key=lambda x: (-x[1], x[0]))]
    else:
        out.append("No one yet: be the first.")
    out += ["", "Take a ready task: see docs/getting-started.md.", ""]
    return "\n".join(out)


def arg(name):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else None


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
    groups = {}
    if arg("--cases") and os.path.isdir(arg("--cases")):
        import cases as cases_mod
        found, _ = cases_mod.load_all(arg("--cases"))
        for c in found:
            g = str(c.get("id", "?")).split("/")[0]
            groups[g] = groups.get(g, 0) + 1
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if arg("--svg"):
        with open(arg("--svg"), "w", encoding="utf-8", newline="\n") as f:
            f.write(svg(count(issues, area_of)))
    if arg("--badges"):
        os.makedirs(arg("--badges"), exist_ok=True)
        for name, text in badges(issues, pulls, rows, sum(groups.values())).items():
            with open(os.path.join(arg("--badges"), f"{name}.svg"), "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
    sys.stdout.buffer.write(render(issues, pulls, rows, now, groups).encode("utf-8"))


if __name__ == "__main__":
    main()
