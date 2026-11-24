"""Test a set of pull requests at once: each alone, and all of them stacked, to see quickly what works together.

Usage:
  python -I tools/try_prs.py [--repo DIR] [--remote origin] [--base main] [--test "CMD"] [--out FILE] PR [PR ...]

For every PR number it fetches `refs/pull/<N>/head` from the remote, then:
  1. alone:   base + that PR, run the test command;
  2. stacked: base + every PR in the order given, skipping the ones that conflict, run the test command once;
and prints a Markdown table (also written to --out, e.g. $GITHUB_STEP_SUMMARY).

Works on any git repository, ours or another project's (point --repo at a clone of it).

**This runs other people's code.** Run it in a throwaway VM, container or CI job with no credentials, never on a
machine holding tokens, keys or anyone's files. The `try` workflow does exactly that.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile


def git(repo, *args, check=True):
    return subprocess.run(["git", "-C", repo, *args], check=check, capture_output=True, text=True)


def run(cmd, cwd, timeout):
    try:
        r = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout + r.stderr)[-1500:]
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout} s"


def worktree(repo, base):
    path = tempfile.mkdtemp(prefix="try-")
    shutil.rmtree(path)
    git(repo, "worktree", "add", "--detach", path, base)
    for k, v in (("user.name", "try-prs"), ("user.email", "try-prs@localhost")):
        git(path, "config", k, v)
    return path


def drop(repo, path):
    git(repo, "worktree", "remove", "--force", path, check=False)
    shutil.rmtree(path, ignore_errors=True)


def merge(path, ref):
    r = git(path, "merge", "--no-edit", "--no-ff", ref, check=False)
    if r.returncode != 0:
        git(path, "merge", "--abort", check=False)
        return False
    return True


def try_prs(repo, remote, base, prs, test, timeout=1800):
    refs = {}
    for n in prs:
        ref = f"refs/try/{n}"
        if git(repo, "fetch", "-q", remote, f"+refs/pull/{n}/head:{ref}", check=False).returncode != 0:
            refs[n] = None
        else:
            refs[n] = ref
    git(repo, "fetch", "-q", remote, base, check=False)
    base_ref = f"{remote}/{base}" if git(repo, "rev-parse", "-q", "--verify", f"{remote}/{base}",
                                         check=False).returncode == 0 else base
    rows = {}
    wt = worktree(repo, base_ref)
    try:
        ok, _ = run(test, wt, timeout)
        base_ok = ok
    finally:
        drop(repo, wt)
    for n in prs:
        if refs[n] is None:
            rows[n] = {"fetch": False}
            continue
        wt = worktree(repo, base_ref)
        try:
            merged = merge(wt, refs[n])
            ok, log = run(test, wt, timeout) if merged else (False, "")
            rows[n] = {"fetch": True, "merges": merged, "alone": ok, "log": log}
        finally:
            drop(repo, wt)
    wt = worktree(repo, base_ref)
    try:
        stacked = [n for n in prs if refs[n] and rows[n]["merges"] and merge(wt, refs[n])]
        for n in prs:
            if n in rows and rows[n].get("fetch"):
                rows[n]["in_stack"] = n in stacked
        stack_ok, stack_log = run(test, wt, timeout) if stacked else (False, "")
    finally:
        drop(repo, wt)
    return base_ok, rows, stacked, stack_ok, stack_log


def table(base, base_ok, rows, stacked, stack_ok, test):
    yes = lambda b: "yes" if b else "**no**"  # noqa: E731
    out = [f"### try_prs on `{base}`", "", f"Test command: `{test}`", "",
           f"Base alone: {'passes' if base_ok else '**fails**'}", "",
           "| PR | merges on base | tests alone | in the stack |", "|---|---|---|---|"]
    for n, r in rows.items():
        if not r.get("fetch"):
            out.append(f"| #{n} | could not fetch | | |")
            continue
        out.append(f"| #{n} | {yes(r['merges'])} | {yes(r['alone']) if r['merges'] else ''} | "
                   f"{yes(r.get('in_stack'))} |")
    out += ["", f"Stack of {len(stacked)} ({', '.join('#' + str(n) for n in stacked) or 'none'}): "
            + ("tests **pass**" if stack_ok else "tests **fail**" if stacked else "nothing to test")]
    alone_fail = [n for n, r in rows.items() if r.get("merges") and not r.get("alone")]
    if stack_ok is False and stacked and not alone_fail:
        out.append("Every PR passes alone but the stack fails: they conflict in behaviour. Bisect the stack.")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--base", default="main")
    ap.add_argument("--test", default="python3 -I -m unittest discover -s tests")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--out")
    ap.add_argument("prs", nargs="+", type=int)
    a = ap.parse_args()
    base_ok, rows, stacked, stack_ok, _ = try_prs(os.path.abspath(a.repo), a.remote, a.base, a.prs, a.test,
                                                  a.timeout)
    text = table(a.base, base_ok, rows, stacked, stack_ok, a.test)
    sys.stdout.write(text)
    if a.out:
        with open(a.out, "a", encoding="utf-8") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
