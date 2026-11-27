"""Save local work into a private workbench repository, refusing anything that may be title data or a secret.

    python -I tools/workbench.py --repo <local repo> --source <dir> [--source <dir> ...] [--depth 2]
                                 [--push <owner>/<private repo>]

Copies files with an allowed extension from each source into <repo>/<source folder name>/..., commits them on
the `workbench` branch. Without --push a repository with any remote is refused. With --push the only remote
allowed is that GitHub repository, and every push first asks GitHub (`gh api`) that it is private; a public or
unknown repository is never pushed to. Each refused file is printed with its reason. Review the branch before
publishing anything (docs/workbench.md).
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


def remote_url(full_name):
    return f"https://github.com/{full_name}.git"


def is_private(full_name, run=subprocess.run):
    """True only when GitHub answers that the repository exists and is private."""
    result = run(["gh", "api", f"repos/{full_name}", "--jq", ".private"], capture_output=True, text=True)
    return result.returncode == 0 and result.stdout.strip() == "true"


def prepare(repo, push=None):
    if not os.path.isdir(os.path.join(repo, ".git")):
        os.makedirs(repo, exist_ok=True)
        git(repo, "init", "-q", "-b", "workbench")
    remotes = git(repo, "remote").split()
    if push is None:
        if remotes:
            raise SystemExit(f"{repo} has a remote; without --push the workbench refuses to run there")
    else:
        if remotes not in ([], ["origin"]) or (remotes and git(repo, "remote", "get-url", "origin").strip() != remote_url(push)):
            raise SystemExit(f"{repo} has a remote other than {remote_url(push)}; refusing")
        if not remotes:
            git(repo, "remote", "add", "origin", remote_url(push))
    if git(repo, "symbolic-ref", "--short", "HEAD").strip() != "workbench":
        git(repo, "checkout", "-q", "-B", "workbench")


def push_private(repo, full_name, private=is_private):
    if not private(full_name):
        raise SystemExit(f"{full_name} is not a private repository (or GitHub did not answer); not pushing")
    git(repo, "push", "-q", "origin", "workbench")


def save(repo, sources, depth=2, push=None):
    """Copy allowed files, commit them, and return (copied, refused) where refused is a list of (path, reason)."""
    prepare(repo, push)
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
    parser.add_argument("--push", metavar="OWNER/REPO", help="a private GitHub repository to push the branch to")
    args = parser.parse_args()
    copied, refused = save(args.repo, args.source, args.depth, args.push)
    print(f"{copied} files saved, {len(refused)} refused")
    for path, reason in refused:
        print(f"REFUSED {path}: {reason}")
    if args.push:
        push_private(args.repo, args.push)
        print(f"pushed to {args.push} (private)")


if __name__ == "__main__":
    main()
