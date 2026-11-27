"""Check that your own copy of a title matches a known build, by hash only.

Usage: python -I tools/check_build.py <your install dir> <hash list>

The hash list is a text file of `<sha256>  <relative path>` lines (sha256sum format). This repository ships the
format, not the files: a hash identifies a file without containing it. Nothing is read except to hash it, and
nothing is copied, uploaded, or written. Prints MATCH / MISMATCH / MISSING per file; exit 0 only if all match.
"""

import hashlib
import os
import sys


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse(lines):
    out = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, _, rel = line.partition(" ")
        rel = rel.strip().lstrip("*")
        parts = rel.replace("\\", "/")
        rooted = parts.startswith("/") or (len(parts) > 1 and parts[1] == ":") or os.path.isabs(rel)
        if len(digest) != 64 or not rel or rooted or ".." in parts.split("/"):
            raise ValueError(f"bad line: {line}")
        out.append((digest.lower(), rel))
    return out


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    root, listing = sys.argv[1], sys.argv[2]
    with open(listing, encoding="utf-8") as f:
        entries = parse(f)
    bad = 0
    for digest, rel in entries:
        p = os.path.join(root, rel)
        if not os.path.isfile(p):
            print("MISSING ", rel)
            bad += 1
        elif sha256(p) != digest:
            print("MISMATCH", rel)
            bad += 1
        else:
            print("MATCH   ", rel)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
