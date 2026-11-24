"""Run the game-data guard over every file version in a range of history, not just the final tree.

Usage: python -I tools/scan_history.py [--repo DIR] <ref> [--not <base ref>]

Every blob reachable from <ref> (and not from <base>) is checked with bot/rules.check_file under the path it
appeared at. Needed before importing someone else's history: a file deleted later is still in the history, and
publishing the history publishes it. Exit 1 if anything is flagged.
"""

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bot"))
import rules  # noqa: E402


def scan(repo, ref, base=None):
    args = ["git", "-C", repo, "rev-list", "--objects", ref] + (["--not", base] if base else [])
    paths = {}
    for line in subprocess.run(args, capture_output=True, text=True, check=True).stdout.splitlines():
        sha, _, path = line.partition(" ")
        if path:
            paths.setdefault(sha, path)
    if not paths:
        return 0, []
    check = subprocess.run(["git", "-C", repo, "cat-file", "--batch-check=%(objectname) %(objecttype)"],
                           input="\n".join(paths), capture_output=True, text=True, check=True).stdout.splitlines()
    blobs = [l.split()[0] for l in check if l.split()[1] == "blob"]
    proc = subprocess.Popen(["git", "-C", repo, "cat-file", "--batch"], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE)
    flagged = []
    for sha in blobs:
        proc.stdin.write((sha + "\n").encode())
        proc.stdin.flush()
        size = int(proc.stdout.readline().split()[2])
        data = proc.stdout.read(size)
        proc.stdout.read(1)
        reason = rules.check_file(paths[sha], data)
        if reason:
            flagged.append(reason)
    proc.stdin.close()
    proc.wait()
    return len(blobs), sorted(set(flagged))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("ref")
    ap.add_argument("--not", dest="base")
    a = ap.parse_args()
    n, flagged = scan(a.repo, a.ref, a.base)
    for f in flagged:
        print(f)
    print(f"{n} file versions scanned, {len(flagged)} flagged")
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
