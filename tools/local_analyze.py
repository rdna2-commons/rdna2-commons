"""Map everything your own copy of a title needs from the engine, without running it, as a scrubbed report.

Usage:
  python -I tools/local_analyze.py --game DIR --exe NAME --work DIR [--runtime PATH]

Runs the engine's own analysis tools over the title's executable (and every .dll next to it) on your machine:
  - engine/tools/gdk_runtime_calls.py  which GDK runtime classes and slots the code calls, and which are served
  - engine/tools/cpu_feature_scan.py   which instructions a desktop CPU may lack (emulated by the runtime)
  - engine/tools/recomp_census.py      how many functions and instructions there are, and what the recompiler
                                       does not handle yet (for track B, docs/engine-plan.md)
  - gta6rt --dry-run (if --runtime)    which imports the runtime binds, shims, or leaves unimplemented

and keeps only an allow-list: API, class and import names (they are the platform's, not the title's), counts and
instruction mnemonics. No addresses, file contents, code, strings or paths. The result is
<work>/analysis/needs.json and needs.md: what to implement next, ranked. Read it before you share it; then attach
it to a `finding` issue or a task.
"""

import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "engine", "tools")
NAME = re.compile(r"^[A-Za-z0-9_.@?$#\-]{1,120}$")


def name_ok(s):
    return isinstance(s, str) and bool(NAME.match(s))


# ---------------------------------------------------------------- scrubbers (unit-tested on synthetic output)

def scrub_gdk(report):
    """gdk_runtime_calls.py --json -> per image: thunks, classes with served flag and slot names/counts."""
    out = []
    for img in report.get("images", []):
        classes = []
        for c in img.get("classes", []):
            if not name_ok(c.get("class")):
                continue
            slots = 0
            names = []
            for i in (c.get("interfaces") or {}).values() if isinstance(c.get("interfaces"), dict) else c.get("interfaces") or []:
                for s in (i.get("slots") or {}).values() if isinstance(i.get("slots"), dict) else i.get("slots") or []:
                    slots += 1
                    n = s.get("name") if isinstance(s, dict) else None
                    if name_ok(n):
                        names.append(n)
            classes.append({"class": c["class"], "served": c.get("served"), "thunks": c.get("thunks", 0),
                            "slots_called": slots, "slot_names": sorted(set(names))[:200]})
        out.append({"thunks": img.get("thunks"), "classes": sorted(classes, key=lambda x: x["class"]),
                    "unreached_classes": sorted(x for x in img.get("unreached_classes", []) if name_ok(x))})
    return out


def scrub_cpu(report):
    """cpu_feature_scan.py --json -> {feature: {class, total}}, no sites."""
    feats = {}
    for f, r in (report.get("features") or {}).items():
        if name_ok(f) and isinstance(r, dict):
            feats[f] = {"class": r.get("class"), "total": int(r.get("total", 0))}
    return {"instructions": report.get("instructions"), "features": feats}


def scrub_census(report):
    """recomp_census.py JSON -> totals and unhandled mnemonics, no addresses."""
    keep = ("pdata_functions", "code_bytes", "insns", "insn_coverage_pct", "functions_fully_covered",
            "functions_with_gaps", "decode_errors", "branch_insns")
    out = {k: report.get(k) for k in keep}
    out["unhandled"] = [[m, int(n)] for m, n in report.get("unhandled", []) if name_ok(m)][:40]
    out["indirect_control_flow"] = {k: v for k, v in (report.get("indirect_control_flow") or {}).items() if name_ok(k)}
    return out


DRY = re.compile(r"^\s+(UNIMPLEMENTED|SHIM)\s+([A-Za-z0-9_.\-]+)!(\S+)(\s+\[returns HRESULT\])?\s*$")


def scrub_dry_run(text):
    """gta6rt --dry-run stdout -> unimplemented and shimmed imports by DLL."""
    missing, shimmed = {}, {}
    for line in text.splitlines():
        m = DRY.match(line)
        if not m or not name_ok(m.group(2)) or not name_ok(m.group(3)):
            continue
        bucket = missing if m.group(1) == "UNIMPLEMENTED" else shimmed
        bucket.setdefault(m.group(2).lower(), set()).add(m.group(3))
    return {"unimplemented": {d: sorted(v) for d, v in sorted(missing.items())},
            "shimmed_count": sum(len(v) for v in shimmed.values())}


def markdown(needs):
    lines = ["# What this build needs from the engine", ""]
    dry = needs.get("imports")
    if dry:
        n = sum(len(v) for v in dry["unimplemented"].values())
        lines += [f"## Unimplemented imports: {n}", ""]
        for d, names in sorted(dry["unimplemented"].items(), key=lambda x: -len(x[1])):
            lines.append(f"- `{d}` ({len(names)}): " + ", ".join(f"`{x}`" for x in names[:30])
                         + (" ..." if len(names) > 30 else ""))
        lines.append("")
    for img in needs.get("gdk", []):
        unserved = [c for c in img["classes"] if c["served"] is False]
        lines += [f"## GDK runtime classes: {len(img['classes'])} called, {len(unserved)} not served", ""]
        for c in sorted(unserved, key=lambda c: -c["slots_called"]):
            lines.append(f"- `{c['class']}`: {c['slots_called']} slot(s)")
        lines.append("")
    cpu = needs.get("cpu")
    if cpu:
        flagged = {f: r for f, r in cpu["features"].items() if r["class"] not in (None, "common", "baseline", "host-query")}
        lines += [f"## CPU features to watch: {len(flagged)}", ""]
        lines += [f"- `{f}` ({r['class']}): {r['total']}" for f, r in sorted(flagged.items(), key=lambda x: -x[1]["total"])]
        lines.append("")
    c = needs.get("census")
    if c:
        lines += ["## For recompilation (track B)", "",
                  f"- functions: {c.get('pdata_functions')}, instructions: {c.get('insns')}, "
                  f"recompiler coverage: {c.get('insn_coverage_pct')}%",
                  "- unhandled mnemonics: " + ", ".join(f"`{m}` {n}" for m, n in c["unhandled"][:15]), ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- running the tools

def run_json(args):
    r = subprocess.run([sys.executable, "-I", *args], capture_output=True, text=True, cwd=TOOLS)
    if r.returncode not in (0, 1):
        print(f"warning: {args[0]} exited with {r.returncode}", file=sys.stderr)
    try:
        return json.loads(r.stdout)
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--game", required=True)
    ap.add_argument("--exe", required=True, help="the title's executable, relative to --game")
    ap.add_argument("--work", required=True)
    ap.add_argument("--runtime", help="path to a built gta6rt.exe for the import report")
    a = ap.parse_args()
    exe = os.path.abspath(os.path.join(a.game, a.exe))
    a.runtime = os.path.abspath(a.runtime) if a.runtime else None
    if not os.path.isfile(exe):
        sys.exit(f"error: {exe} not found")
    needs = {}
    gdk = run_json(["gdk_runtime_calls.py", exe, "--json"])
    if gdk:
        needs["gdk"] = scrub_gdk(gdk)
    cpu = run_json(["cpu_feature_scan.py", exe, "--json"])
    if cpu:
        needs["cpu"] = scrub_cpu(cpu)
    out = os.path.join(os.path.abspath(a.work), "analysis")
    os.makedirs(out, exist_ok=True)
    census_dir = os.path.join(out, "census-raw")
    subprocess.run([sys.executable, "-I", "recomp_census.py", exe, "--out", census_dir], cwd=TOOLS,
                   capture_output=True)
    for n in sorted(os.listdir(census_dir)) if os.path.isdir(census_dir) else []:
        if n.endswith(".json"):
            with open(os.path.join(census_dir, n), encoding="utf-8") as f:
                needs["census"] = scrub_census(json.load(f))
            break
    if a.runtime and os.path.isfile(a.runtime):
        r = subprocess.run([a.runtime, "--dry-run", exe, "--game-dir", a.game], capture_output=True, text=True,
                           errors="replace")
        needs["imports"] = scrub_dry_run(r.stdout)
    with open(os.path.join(out, "needs.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(needs, f, indent=1)
    with open(os.path.join(out, "needs.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(markdown(needs))
    print(markdown(needs))
    print(f"\nwritten: {out}/needs.json and needs.md (census-raw/ has addresses: keep it to yourself)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
