"""Validate the shared test cases (docs/test-format.md).

Usage: python -I tools/cases.py [cases dir]     prints one line per problem; exit 1 if any
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bot"))
import rules  # noqa: E402

HEX32 = re.compile(r"^0x[0-9a-f]{8}$")
SGPR = re.compile(r"^s([0-9]{1,3})$")
REQUIRED = {"id": str, "summary": str, "isa": str, "wave": int, "group": list, "sgpr": dict, "source": list,
            "expect": list, "provenance": str}
OPTIONAL = {"known": list}
MAX_LINES = 400


def validate(case, rel_id):
    """Return a list of problems for one parsed case whose path gives rel_id (`group/name`)."""
    p = []
    for k, t in REQUIRED.items():
        if k not in case:
            p.append(f"missing `{k}`")
        elif not isinstance(case[k], t) or (t is int and isinstance(case[k], bool)):
            p.append(f"`{k}` must be {t.__name__}")
    for k in case:
        if k not in REQUIRED and k not in OPTIONAL:
            p.append(f"unknown field `{k}`")
    if p:
        return p
    if case["id"] != rel_id:
        p.append(f"id `{case['id']}` must equal its path `{rel_id}`")
    if case["isa"] != "rdna2":
        p.append("isa must be `rdna2`")
    if case["wave"] not in (32, 64):
        p.append("wave must be 32 or 64")
    g = case["group"]
    if len(g) != 3 or not all(isinstance(x, int) and x >= 1 for x in g) or g[0] * g[1] * g[2] > 1024:
        p.append("group must be three positive ints, at most 1024 threads")
    regs = []
    for reg, val in case["sgpr"].items():
        m = SGPR.match(reg)
        if not m or not 4 <= int(m.group(1)) <= 103:
            p.append(f"sgpr `{reg}` must be s4..s103 (s0..s3 are the output descriptor)")
        else:
            regs.append(int(m.group(1)))
        if not isinstance(val, str) or not HEX32.match(val):
            p.append(f"sgpr `{reg}` value must be 32-bit lower-case hex like 0x0000002a")
    if regs and sorted(regs) != list(range(4, 4 + len(regs))):
        p.append("user SGPRs must be contiguous from s4")
    src = case["source"]
    if not src or len(src) > MAX_LINES or not all(isinstance(l, str) and l.strip() for l in src):
        p.append(f"source must be 1..{MAX_LINES} non-empty lines")
    elif src[-1].strip() != "s_endpgm":
        p.append("source must end with s_endpgm")
    if not case["expect"] or not all(isinstance(w, str) and HEX32.match(w) for w in case["expect"]):
        p.append("expect must be a non-empty list of 32-bit lower-case hex words")
    elif len(case["expect"]) > 64:
        p.append("expect is limited to 64 words (256 bytes)")
    for i, k in enumerate(case.get("known", [])):
        if not isinstance(k, dict) or set(k) != {"hw_class", "when", "words", "note"}:
            p.append(f"known[{i}] must have exactly hw_class, when, words, note")
        elif len(k["words"]) != len(case["expect"]) or not all(HEX32.match(w) for w in k["words"]):
            p.append(f"known[{i}].words must match expect in length and format")
    if len(case["summary"]) < 10:
        p.append("summary too short")
    return p


def load_all(root):
    out, problems = [], []
    for dirpath, _, names in os.walk(root):
        for n in sorted(names):
            path = os.path.join(dirpath, n)
            rel = os.path.relpath(path, root).replace("\\", "/")
            if not n.endswith(".json"):
                problems.append(f"{rel}: only .json files belong in cases/")
                continue
            with open(path, "rb") as f:
                data = f.read()
            guard = rules.check_file("cases/" + rel, data)
            if guard:
                problems.append(guard)
                continue
            try:
                case = json.loads(data.decode("utf-8"))
            except ValueError as e:
                problems.append(f"{rel}: not valid JSON ({e})")
                continue
            if not isinstance(case, dict):
                problems.append(f"{rel}: must be a JSON object")
                continue
            problems += [f"{rel}: {x}" for x in validate(case, rel[:-5])]
            out.append(case)
    ids = [c.get("id") for c in out]
    problems += [f"duplicate id {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    return out, problems


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "cases"
    cases, problems = load_all(root)
    for p in problems:
        print(p)
    print(f"{len(cases)} cases, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
