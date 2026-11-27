"""Fetch the BCPack format tables the track A runtime needs, from VIctory's own repository, onto your machine.

Usage:
  python -I tools/fetch_bcpack_tables.py [--out DIR]

The VIctory runtime (victory/) decodes BCPack textures with a table file that its upstream ships as an asset-policy
exception, outside its licence. RDNA2 Commons does not distribute it. This script downloads it from the upstream
repository at a pinned commit, checks its SHA-256, and writes it as `bcpack-tables.bin` in DIR (default: next to
victory.exe in the cargo target directory), where the runtime reads it. Only the address, the commit and the hash are
kept here.
"""

import argparse
import hashlib
import os
import sys
import urllib.request

UPSTREAM = "https://raw.githubusercontent.com/Marvisak/VIctory"
COMMIT = "ffe310eb2098e52169f4c44db5ffdabf43a72622"
PATH = "crates/victory-formats/src/bcpack-tables.bin"
SHA256 = "1f1d4760419202bb5672f0c428ce51e456b5d08fbaec8f371d043fd94e01c36b"
SIZE = 77982
NAME = "bcpack-tables.bin"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def url():
    return f"{UPSTREAM}/{COMMIT}/{PATH}"


def default_out():
    target = os.environ.get("CARGO_TARGET_DIR") or os.path.join(ROOT, "victory", "target")
    return os.path.join(target, "release")


def check(data):
    """None when `data` is the pinned file, else what is wrong with it."""
    if len(data) != SIZE:
        return f"{len(data)} bytes, expected {SIZE}"
    digest = hashlib.sha256(data).hexdigest()
    if digest != SHA256:
        return f"SHA-256 {digest}, expected {SHA256}"
    return None


def write(data, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, NAME)
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)
    return path


def fetch(opener=urllib.request.urlopen):
    req = urllib.request.Request(url(), headers={"User-Agent": "rdna2-commons-fetch"})
    with opener(req, timeout=60) as r:
        return r.read(SIZE + 1)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=default_out(), help="folder to write bcpack-tables.bin into")
    a = ap.parse_args(argv)
    existing = os.path.join(a.out, NAME)
    if os.path.isfile(existing) and check(open(existing, "rb").read()) is None:
        print(f"already there: {existing}")
        return 0
    print(f"downloading {url()}")
    data = fetch()
    problem = check(data)
    if problem:
        print(f"error: the download is not the pinned file ({problem}); nothing written", file=sys.stderr)
        return 1
    print(f"written: {write(data, a.out)}")
    print("the runtime reads it from there; or point VICTORY_BCPACK_TABLES at it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
