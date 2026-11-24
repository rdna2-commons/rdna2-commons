"""Repository bot: `gate <pr>`, `command`, `sweep`. Runs in GitHub Actions with GITHUB_TOKEN and GITHUB_REPOSITORY.

It never checks out or runs code from a pull request: it reads files through the API only, which is what makes
running it on `pull_request_target` (with a write token, for pull requests from forks) safe.
"""

import base64
import datetime as dt
import json
import re
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules  # noqa: E402

API = "https://api.github.com"
REPO = os.environ.get("GITHUB_REPOSITORY", "")
MARK = "<!-- commons-bot -->"
# COMMONS_DRY_RUN=1: post comments saying what would happen, change nothing else (no labels, closes, merges,
# assignments or new issues). For trying the bot on a project before it is allowed to act.
DRY_RUN = os.environ.get("COMMONS_DRY_RUN") == "1"
DRY_LOG = []


def is_comment_post(method, path):
    return method == "POST" and path.endswith("/comments")


def call(method, path, data=None):
    if DRY_RUN and method != "GET" and not is_comment_post(method, path):
        DRY_LOG.append((method, path, data))
        print(f"dry run: would {method} {path} {json.dumps(data) if data else ''}")
        return {"number": 0}
    url = path if path.startswith("http") else f"{API}{path}"
    req = urllib.request.Request(url, method=method, data=None if data is None else json.dumps(data).encode())
    req.add_header("Authorization", "Bearer " + os.environ["GITHUB_TOKEN"])
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "commons-bot")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
            return json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def pages(path):
    out, page = [], 1
    sep = "&" if "?" in path else "?"
    while True:
        chunk = call("GET", f"{path}{sep}per_page=100&page={page}") or []
        out.extend(chunk)
        if len(chunk) < 100:
            return out
        page += 1


def now():
    return dt.datetime.now(dt.timezone.utc)


def ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def comment(number, text):
    if DRY_RUN:
        text = "**Dry run: nothing was changed.** This is what the bot would do.\n\n" + text
    call("POST", f"/repos/{REPO}/issues/{number}/comments", {"body": f"{MARK}\n{text}"})


def labels(issue):
    return [l["name"] for l in issue.get("labels", [])]


def add_label(number, name):
    call("POST", f"/repos/{REPO}/issues/{number}/labels", {"labels": [name]})


def remove_label(number, name):
    call("DELETE", f"/repos/{REPO}/issues/{number}/labels/{urllib.parse.quote(name)}")


def maintainers():
    try:
        with open(os.path.join(os.path.dirname(__file__), "..", "MAINTAINERS"), encoding="utf-8") as f:
            return {l.strip() for l in f if l.strip() and not l.startswith("#")}
    except OSError:
        return set()


def merged_counts():
    counts = {}
    for p in pages(f"/repos/{REPO}/pulls?state=closed"):
        if p.get("merged_at"):
            counts[p["user"]["login"]] = counts.get(p["user"]["login"], 0) + 1
    return counts


def hours_ago(stamp):
    return (now() - ts(stamp)).total_seconds() / 3600


def active_people():
    """Distinct people who opened, pushed to, reviewed or commented on anything in the last 24 hours."""
    since = (now() - dt.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    people = {c["user"]["login"] for c in pages(f"/repos/{REPO}/issues/comments?since={since}")}
    people |= {i["user"]["login"] for i in pages(f"/repos/{REPO}/issues?state=all&since={since}")}
    return len({p for p in people if not p.endswith("[bot]")})


def reviewer_pool():
    """Latest `/reviewer on|off` per person in the issue labelled reviewer-pool."""
    pool = {}
    for issue in pages(f"/repos/{REPO}/issues?state=open&labels=reviewer-pool"):
        for c in pages(f"/repos/{REPO}/issues/{issue['number']}/comments"):
            t = c["body"].strip().lower()
            if t.startswith("/reviewer on"):
                pool[c["user"]["login"]] = True
            elif t.startswith("/reviewer off"):
                pool[c["user"]["login"]] = False
    return {u for u, on in pool.items() if on}


ASSIGN_RE = re.compile(r"<!-- reviewers:([0-9a-f]{40}):([^ >]*) -->")


def assigned_reviewers(number, sha):
    for c in reversed(pages(f"/repos/{REPO}/issues/{number}/comments")):
        m = ASSIGN_RE.search(c["body"])
        if m and m.group(1) == sha and c["user"]["login"].endswith("[bot]"):
            return set(filter(None, m.group(2).split(",")))
    return set()


def task_body(num):
    issue = call("GET", f"/repos/{REPO}/issues/{num}")
    return (issue or {}).get("body") or ""


def assign_reviewers(pr, task):
    """Draw reviewers for the current head commit and post a blind brief: the task, not the author's pitch."""
    sha = pr["head"]["sha"]
    if assigned_reviewers(pr["number"], sha):
        return
    chosen = rules.pick_reviewers(reviewer_pool(), {pr["user"]["login"]}, f"{pr['number']}:{sha}")
    if not chosen:
        return
    spec = task_body(task["number"]) if task else ""
    comment(pr["number"],
            f"<!-- reviewers:{sha}:{','.join(chosen)} -->\n"
            f"Review requested from {', '.join('@' + u for u in chosen)} for commit `{sha[:9]}`.\n\n"
            "**Blind review.** Judge the diff against the task below, not against the author's description or "
            "comments: read those only after you have written your verdict. Assume the code is wrong until you "
            "have failed to break it. Use the review form in AGENTS.md; a review in any other form does not "
            f"count.\n\n**Task #{task['number'] if task else '?'}:**\n\n> " + spec.replace("\n", "\n> "))


def pr_files(pr):
    head = pr["head"]
    out = []
    for f in pages(f"/repos/{REPO}/pulls/{pr['number']}/files"):
        if f["status"] == "removed":
            continue
        blob = call("GET", f"/repos/{head['repo']['full_name']}/contents/"
                           f"{urllib.parse.quote(f['filename'])}?ref={head['sha']}")
        data = base64.b64decode(blob["content"]) if blob and blob.get("content") else b""
        if blob and blob.get("size", 0) > 1024 * 1024 and not data:
            data = b"\0" * 16  # too large for the contents API: treat as binary, the size rule applies
        out.append((f["filename"], data))
    return out


def task_of(body):
    num = rules.task_number(body)
    if num is None:
        return None
    issue = call("GET", f"/repos/{REPO}/issues/{num}")
    if not issue or "pull_request" in issue:
        return None
    return {"number": num, "assignees": [a["login"] for a in issue["assignees"]], "labels": labels(issue),
            "state": issue["state"]}


def gate(number):
    pr = call("GET", f"/repos/{REPO}/pulls/{number}")
    if pr["state"] != "open":
        return
    info = {"number": number, "author": pr["user"]["login"], "body": pr["body"] or "", "labels": labels(pr),
            "additions": pr["additions"], "deletions": pr["deletions"]}
    others = [{"number": p["number"], "body": p["body"] or ""} for p in pages(f"/repos/{REPO}/pulls?state=open")
              if p["number"] != number]
    commits = [c["commit"]["message"] for c in pages(f"/repos/{REPO}/pulls/{number}/commits")]
    hard, soft = rules.gate(info, pr_files(pr), task_of(info["body"]), others, commits)
    if hard:
        comment(number, "Closing: this pull request breaks the rules in CONTRIBUTING.md.\n\n"
                + "\n".join(f"- {r}" for r in hard + soft)
                + "\n\nFix them and open a new pull request.")
        add_label(number, "rejected")
        call("PATCH", f"/repos/{REPO}/pulls/{number}", {"state": "closed"})
    elif soft:
        if "needs-fix" not in info["labels"]:
            hours = rules.fix_deadline_hours(active_people())
            comment(number, f"Please fix within {hours} hours, or this pull request is closed. Half-way "
                    "through with no word from you, the fix becomes a task anyone can take.\n\n"
                    + "\n".join(f"- {r}" for r in soft))
            add_label(number, "needs-fix")
        if "gate-ok" in info["labels"]:
            remove_label(number, "gate-ok")
    else:
        if "needs-fix" in info["labels"]:
            remove_label(number, "needs-fix")
        if "gate-ok" not in info["labels"]:
            add_label(number, "gate-ok")
        assign_reviewers(pr, task_of(info["body"]))


def command():
    event = json.load(open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8"))
    issue, user = event["issue"], event["comment"]["user"]["login"]
    text = event["comment"]["body"].strip().lower()
    if "pull_request" in issue or event["comment"]["user"]["type"] == "Bot":
        return
    num = issue["number"]
    task = {"assignees": [a["login"] for a in issue["assignees"]], "labels": labels(issue)}
    if text.startswith("/claim"):
        held = len(pages(f"/repos/{REPO}/issues?state=open&assignee={urllib.parse.quote(user)}&labels=task"))
        why = rules.can_claim(task, user, held)
        if why:
            comment(num, f"@{user} cannot claim this: {why}.")
        else:
            call("POST", f"/repos/{REPO}/issues/{num}/assignees", {"assignees": [user]})
            comment(num, f"Assigned to @{user}. Open a pull request with `Closes #{num}` within "
                         f"{rules.CLAIM_HOURS} hours or the claim expires.")
    elif text.startswith("/split") and (user in task["assignees"] or user in maintainers()):
        try:
            parts = rules.parse_split(event["comment"]["body"].strip())
        except ValueError as e:
            comment(num, f"@{user} `/split` not done: {e}.")
            return
        made = []
        for title, deps in parts:
            body = f"Part of #{num}.\n\n" + "".join(f"Depends on #{made[d - 1]}\n" for d in deps)
            new = call("POST", f"/repos/{REPO}/issues", {"title": title, "body": body, "labels": ["task"]})
            made.append(new["number"])
        body = (issue.get("body") or "") + "\n\n" + "".join(f"Depends on #{n}\n" for n in made)
        call("PATCH", f"/repos/{REPO}/issues/{num}", {"body": body})
        if task["assignees"]:
            call("DELETE", f"/repos/{REPO}/issues/{num}/assignees", {"assignees": task["assignees"]})
        if "ready" in task["labels"]:
            remove_label(num, "ready")
        comment(num, f"Split by @{user} into " + ", ".join(f"#{n}" for n in made)
                     + ". This task is ready again when they are closed.")
    elif text.startswith("/unclaim") and user in task["assignees"]:
        call("DELETE", f"/repos/{REPO}/issues/{num}/assignees", {"assignees": [user]})
        comment(num, f"@{user} released this task.")


def checks_green(sha):
    runs = (call("GET", f"/repos/{REPO}/commits/{sha}/check-runs?per_page=100") or {}).get("check_runs", [])
    runs = [r for r in runs if r["name"] != "automerge"]
    return bool(runs) and all(r["status"] == "completed" and r["conclusion"] in ("success", "skipped", "neutral")
                              for r in runs)


def sweep():
    tasks = pages(f"/repos/{REPO}/issues?state=all&labels=task")
    closed = {i["number"] for i in pages(f"/repos/{REPO}/issues?state=closed")}
    open_prs = pages(f"/repos/{REPO}/pulls?state=open")
    claimed_by_pr = {rules.task_number(p["body"] or "") for p in open_prs}
    for t in tasks:
        if t["state"] != "open":
            continue
        ready, _ = rules.task_ready(t["body"], closed)
        has = "ready" in labels(t)
        if ready and not has:
            add_label(t["number"], "ready")
        elif not ready and has:
            remove_label(t["number"], "ready")
        if t["assignees"] and t["number"] not in claimed_by_pr:
            events = pages(f"/repos/{REPO}/issues/{t['number']}/events")
            assigned = [e for e in events if e["event"] == "assigned"]
            if assigned and now() - ts(assigned[-1]["created_at"]) > dt.timedelta(hours=rules.CLAIM_HOURS):
                who = [a["login"] for a in t["assignees"]]
                call("DELETE", f"/repos/{REPO}/issues/{t['number']}/assignees", {"assignees": who})
                comment(t["number"], f"Claim by @{who[0]} expired after {rules.CLAIM_HOURS} hours with no pull "
                                     "request. The task is free again.")
    counts, maint, active = merged_counts(), maintainers(), active_people()
    deadline = rules.fix_deadline_hours(active)
    for p in open_prs:
        lab = labels(p)
        if "needs-fix" in lab:
            events = pages(f"/repos/{REPO}/issues/{p['number']}/events")
            added = [e for e in events if e["event"] == "labeled" and e["label"]["name"] == "needs-fix"]
            if not added:
                continue
            flagged = hours_ago(added[-1]["created_at"])
            author = p["user"]["login"]
            said = [c for c in pages(f"/repos/{REPO}/issues/{p['number']}/comments") if c["user"]["login"] == author]
            head = call("GET", f"/repos/{REPO}/commits/{p['head']['sha']}")
            quiet = hours_ago(head["commit"]["committer"]["date"])
            if said:
                quiet = min(quiet, hours_ago(said[-1]["created_at"]))
            if flagged > deadline:
                comment(p["number"], f"Closing: not fixed within {deadline} hours. Reopen it when it is, or "
                                     "finish it through its fix task.")
                call("PATCH", f"/repos/{REPO}/pulls/{p['number']}", {"state": "closed"})
            elif "adopt-open" not in lab and rules.adoption_due(flagged, quiet, active):
                fix = call("POST", f"/repos/{REPO}/issues", {
                    "title": f"Finish #{p['number']}: {p['title']}", "labels": ["task"],
                    "body": f"#{p['number']} by @{author} needs fixing (see the bot's comment there) and its "
                            f"author has been quiet. Take its commits (`gh pr checkout {p['number']}`), keep their "
                            "authorship, fix the listed problems, and open a pull request that closes this task."})
                add_label(p["number"], "adopt-open")
                comment(p["number"], f"Opened #{fix['number']} so anyone can finish this. @{author}, you can "
                                     "still fix it yourself first.")
            continue
        if "gate-ok" not in lab:
            continue
        reviews = [{"user": r["user"]["login"], "body": r.get("body") or "", "commit": r.get("commit_id")}
                   for r in pages(f"/repos/{REPO}/pulls/{p['number']}/reviews")]
        commit = call("GET", f"/repos/{REPO}/commits/{p['head']['sha']}")
        pushed = ts(commit["commit"]["committer"]["date"])
        ok, why = rules.merge_decision({"author": p["user"]["login"], "labels": lab, "head": p["head"]["sha"]},
                                       reviews, checks_green(p["head"]["sha"]), counts,
                                       (now() - pushed).total_seconds() / 3600, maint,
                                       assigned_reviewers(p["number"], p["head"]["sha"]))
        if ok:
            call("PUT", f"/repos/{REPO}/pulls/{p['number']}/merge",
                 {"merge_method": "squash", "sha": p["head"]["sha"]})
            comment(p["number"], f"Merged automatically: {why}.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "gate":
        gate(int(sys.argv[2]))
    elif cmd == "command":
        command()
    elif cmd == "sweep":
        sweep()
    else:
        sys.exit("usage: main.py gate <pr> | command | sweep")
