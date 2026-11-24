"""Title runs: how far the engine gets on a real title, reported by build hash and confirmed by agreement.

A build is registered in builds/<id>.json:
  {"id": "build-a", "exe_sha256": "<64 hex>", "exe_size": 123, "note": "neutral description"}
The id is neutral; the hash identifies the build without naming or containing anything from it. Check your own
copy against it with tools/check_build.py before reporting.

A report is title-runs/<build id>/<engine commit>/<github login>.json:
  {"build": "build-a", "commit": "<40 hex>", "hw_class": "nvidia-ada", "os": "windows-11", "driver": "621.24",
   "stage": "first-frame", "fps": 30.0, "stop": "module+0x1234 access violation", "notes": "short text"}

`stage` is the furthest point reached, one of STAGES. `stop` says where it stopped, as a module name and offset
and a short reason, never a dump or a quote of the title's code or data. `notes` is free text with the same rule.

A stage is CONFIRMED for a (build, commit) when two different people report reaching it or further.

Usage: python -I tools/title_runs.py [builds dir] [title-runs dir]   (prints the table; exit 1 on invalid files)
"""

import json
import os
import re
import sys

STAGES = ["loads", "imports-resolved", "device-created", "first-frame", "menu", "in-world", "playable"]
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
BUILD_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,39}$")
STOP = re.compile(r"^$|^[A-Za-z0-9_.\-]+\+0x[0-9a-fA-F]{1,16}( .{1,120})?$|^[a-z][a-z0-9 ,.\-]{2,120}$")
MAX_NOTES = 500


def validate_build(build, name):
    p = []
    if set(build) != {"id", "exe_sha256", "exe_size", "note"}:
        p.append("needs exactly id, exe_sha256, exe_size, note")
        return p
    if build["id"] != name or not BUILD_ID.match(build["id"]):
        p.append("id must equal the file name and be lower-case letters, digits and dashes")
    if not isinstance(build["exe_sha256"], str) or not HEX64.match(build["exe_sha256"]):
        p.append("exe_sha256 must be 64 lower-case hex digits")
    if not isinstance(build["exe_size"], int) or build["exe_size"] <= 0:
        p.append("exe_size must be a positive integer")
    if not isinstance(build["note"], str) or len(build["note"]) > 200:
        p.append("note must be a string of at most 200 characters")
    return p


def validate_run(run, build_id, commit, builds):
    p = []
    need = {"build", "commit", "hw_class", "os", "driver", "stage", "fps", "stop", "notes"}
    if set(run) != need:
        return [f"needs exactly {', '.join(sorted(need))}"]
    if run["build"] != build_id or run["build"] not in builds:
        p.append("build must match the folder and a registered build")
    if run["commit"] != commit or not HEX40.match(run["commit"]):
        p.append("commit must be 40 hex digits and match the folder")
    if run["stage"] not in STAGES:
        p.append("stage must be one of " + ", ".join(STAGES))
    if run["fps"] is not None and (not isinstance(run["fps"], (int, float)) or not 0 <= run["fps"] <= 1000):
        p.append("fps must be null or a number from 0 to 1000")
    if not isinstance(run["stop"], str) or not STOP.match(run["stop"]):
        p.append("stop must be empty, `module+0xOFFSET reason`, or a short lower-case phrase")
    if not isinstance(run["notes"], str) or len(run["notes"]) > MAX_NOTES or re.search(r"[0-9a-fA-F]{64,}",
                                                                                       run["notes"]):
        p.append(f"notes must be at most {MAX_NOTES} characters with no long hex dumps")
    for k in ("hw_class", "os", "driver"):
        if not isinstance(run[k], str) or not 1 <= len(run[k]) <= 40:
            p.append(f"{k} must be a short string")
    return p


def confirmed(reports):
    """reports: [(login, run)] -> {(build, commit): (furthest confirmed stage or None, furthest single report)}."""
    out = {}
    groups = {}
    for login, r in reports:
        groups.setdefault((r["build"], r["commit"]), {}).setdefault(login, []).append(STAGES.index(r["stage"]))
    for key, by in groups.items():
        best_each = sorted((max(v) for v in by.values()), reverse=True)
        conf = STAGES[best_each[1]] if len(best_each) >= 2 else None
        out[key] = (conf, STAGES[best_each[0]])
    return out


def load(builds_dir, runs_dir):
    builds, problems, reports = {}, [], []
    if os.path.isdir(builds_dir):
        for n in sorted(x for x in os.listdir(builds_dir) if not x.startswith(".")):
            path = os.path.join(builds_dir, n)
            try:
                b = json.load(open(path, encoding="utf-8"))
            except (OSError, ValueError) as e:
                problems.append(f"builds/{n}: {e}")
                continue
            errs = validate_build(b, n[:-5]) if n.endswith(".json") and isinstance(b, dict) else ["not a build"]
            problems += [f"builds/{n}: {e}" for e in errs]
            if not errs:
                builds[b["id"]] = b
    if os.path.isdir(runs_dir):
        for dirpath, _, names in os.walk(runs_dir):
            for n in (x for x in names if not x.startswith(".")):
                path = os.path.join(dirpath, n)
                rel = os.path.relpath(path, runs_dir).replace("\\", "/")
                parts = rel.split("/")
                if len(parts) != 3 or not n.endswith(".json"):
                    problems.append(f"title-runs/{rel}: must be <build>/<commit>/<login>.json")
                    continue
                try:
                    r = json.load(open(path, encoding="utf-8"))
                except (OSError, ValueError) as e:
                    problems.append(f"title-runs/{rel}: {e}")
                    continue
                errs = validate_run(r, parts[0], parts[1], builds) if isinstance(r, dict) else ["not an object"]
                problems += [f"title-runs/{rel}: {e}" for e in errs]
                if not errs:
                    reports.append((n[:-5], r))
    return builds, reports, problems


def main():
    builds_dir = sys.argv[1] if len(sys.argv) > 1 else "builds"
    runs_dir = sys.argv[2] if len(sys.argv) > 2 else "title-runs"
    builds, reports, problems = load(builds_dir, runs_dir)
    for p in problems:
        print("invalid:", p)
    for (b, c), (conf, best) in sorted(confirmed(reports).items()):
        print(f"{b} {c[:9]}  confirmed: {conf or '-'}  furthest reported: {best}")
    print(f"{len(builds)} builds, {len(reports)} reports, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
