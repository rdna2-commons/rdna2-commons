"""Prove a pull request's tests test something: they must fail on the base code and pass on the new code.

Usage: python -I tools/fails_on_base.py <base ref> [head ref, default HEAD]

Takes the test files the pull request adds or changes under tests/, copies them into a worktree of the base
commit, and runs each there. When the pull request changes code under src/, at least one of those tests must
fail on the base; a test that already passes on the old code proves nothing about the change. Tests whose names
start with `test_regression_` are exempt (they pin existing behaviour on purpose).

Runs in the unprivileged `verify` workflow (pull_request event, read-only token, no secrets), because it executes
the pull request's code.
"""

import os
import shutil
import subprocess
import sys
import tempfile

CODE_DIRS = ("src/", "bot/", "tools/")  # keep in step with bot/rules.py


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def changed(base, head):
    out = git("diff", "--name-status", "--no-renames", f"{base}...{head}")
    files = []
    for line in out.splitlines():
        status, _, path = line.partition("\t")
        if status[0] in "AM":
            files.append(path)
    return files


def run_test(root, rel):
    mod = rel[:-3].replace("/", ".")
    # Not -I: unittest must import the worktree's own modules from its root.
    r = subprocess.run([sys.executable, "-E", "-s", "-m", "unittest", mod], cwd=root, capture_output=True, text=True,
                       timeout=600)
    return r.returncode == 0, (r.stdout + r.stderr)[-2000:]


def main():
    base = sys.argv[1]
    head = sys.argv[2] if len(sys.argv) > 2 else "HEAD"
    files = changed(base, head)
    src = [f for f in files if f.startswith(CODE_DIRS)]
    tests = [f for f in files if f.startswith("tests/") and f.endswith(".py")
             and os.path.basename(f).startswith("test_") and not os.path.basename(f).startswith("test_regression_")]
    if not src:
        print("no code changes: nothing to prove")
        return 0
    if not tests:
        print("FAIL: code changed but no new or changed tests/test_*.py")
        return 1
    tmp = tempfile.mkdtemp()
    wt = os.path.join(tmp, "base")
    git("worktree", "add", "--detach", wt, base)
    try:
        failed_on_base = []
        for t in tests:
            dst = os.path.join(wt, t)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "w", encoding="utf-8", newline="\n") as f:
                f.write(git("show", f"{head}:{t}"))
            ok, log = run_test(wt, t)
            print(f"{'passes' if ok else 'fails '} on base: {t}")
            if not ok:
                failed_on_base.append(t)
        if not failed_on_base:
            print("FAIL: every new or changed test already passes on the base code, so none of them tests this "
                  "change. Add a test that fails without it.")
            return 1
        print(f"ok: {len(failed_on_base)} test file(s) fail on the base and are fixed by this change")
        return 0
    finally:
        git("worktree", "remove", "--force", wt)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
