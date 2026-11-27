"""Save local work into a private workbench repository, refusing anything that may be title data or a secret.

    python -I tools/workbench.py --repo <local repo> --source <dir> [--source <dir> ...] [--depth 2]

Copies files with an allowed extension from each source into <repo>/<source folder name>/..., commits them on
the `workbench` branch, and never pushes: a repository with any remote is refused. Each refused file is printed
with its reason. Review the branch before publishing anything (docs/workbench.md).
"""

import argparse
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bot"))
import rules  # noqa: E402

ALLOWED = {".ps1", ".py", ".sh", ".md"}
MAX_BYTES = 256 * 1024
SKIP_DIRS = {".git", "node_modules", "__pycache__", "target", "build"}
SECRET = re.compile(
    rb"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|gh[ousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}"
    rb"|-----BEGIN [A-Z ]*PRIVATE KEY-----|xox[abpr]-[A-Za-z0-9-]{10,}|sk-[A-Za-z0-9_-]{32,}"
    rb"|(?i:(?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*['\"][^'\"\s]{8,}['\"])"
)


def refusal(rel, data):
    """Why this file must not enter the workbench, or None."""
    if len(data) > MAX_BYTES:
        return f"larger than {MAX_BYTES // 1024} KiB"
    if rules.is_binary(data):
        return "binary content"
    reason = rules.check_file(rel, data)
    if reason:
        return reason.split(": ", 1)[-1]
    if SECRET.search(data):
        return "looks like a secret (token, key or password)"
    return None


def candidates(source, depth):
    base = os.path.abspath(source)
    for top, dirs, files in os.walk(base):
        rel_top = os.path.relpath(top, base)
        level = 0 if rel_top == "." else rel_top.count(os.sep) + 1
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and level < depth)
        for name in sorted(files):
            if os.path.splitext(name)[1].lower() in ALLOWED:
                path = os.path.join(top, name)
                yield path, os.path.relpath(path, base).replace(os.sep, "/")


def git(repo, *args, check=True):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=check).stdout


def prepare(repo):
    if not os.path.isdir(os.path.join(repo, ".git")):
        os.makedirs(repo, exist_ok=True)
        git(repo, "init", "-q", "-b", "workbench")
    if git(repo, "remote").strip():
        raise SystemExit(f"{repo} has a remote; the workbench never pushes, so it refuses to run there")
    if git(repo, "symbolic-ref", "--short", "HEAD").strip() != "workbench":
        git(repo, "checkout", "-q", "-B", "workbench")


def save(repo, sources, depth=2):
    """Copy allowed files, commit them, and return (copied, refused) where refused is a list of (path, reason)."""
    prepare(repo)
    copied, refused = 0, []
    for source in sources:
        prefix = os.path.basename(os.path.normpath(source)) or "root"
        for path, rel in candidates(source, depth):
            with open(path, "rb") as f:
                data = f.read(MAX_BYTES + 1)
            reason = refusal(f"{prefix}/{rel}", data)
            target = os.path.join(repo, prefix, *rel.split("/"))
            if reason:
                refused.append((path, reason))
                if os.path.exists(target):
                    os.remove(target)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(path, target)
            copied += 1
    git(repo, "add", "-A")
    if git(repo, "status", "--porcelain").strip():
        git(repo, "-c", "user.name=workbench", "-c", "user.email=workbench@localhost", "commit", "-q", "-m",
            "workbench: save local work")
    return copied, refused


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--depth", type=int, default=2)
    args = parser.parse_args()
    copied, refused = save(args.repo, args.source, args.depth)
    print(f"{copied} files saved, {len(refused)} refused")
    for path, reason in refused:
        print(f"REFUSED {path}: {reason}")


if __name__ == "__main__":
    main()
