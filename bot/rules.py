"""Pure rule checks for pull requests, tasks and merges. No network: bot/main.py feeds them GitHub data."""

import math
import re

ALLOWED_LICENSES = {
    "GPL-3.0", "GPL-3.0-only", "GPL-3.0-or-later", "LGPL-3.0", "LGPL-3.0-or-later", "MIT", "BSD-2-Clause",
    "BSD-3-Clause", "Apache-2.0", "Zlib", "ISC", "CC0-1.0",
}

# Extensions that are game data or binaries in this scene; never accepted anywhere in the tree.
BLOCKED_EXTENSIONS = {
    ".rpf", ".exe", ".dll", ".sys", ".xex", ".xvd", ".msixvc", ".pkg", ".self", ".elf", ".prx", ".sprx",
    ".ttpf", ".dds", ".bk2", ".bik", ".awc", ".adat", ".xma", ".wem", ".bnk", ".ogg", ".opus", ".wav", ".mp3",
    ".mp4", ".dxbc", ".dxil", ".cso", ".spv", ".fssm", ".ydr", ".ydd", ".yft", ".ytd", ".ybn", ".ymap",
    ".ytyp", ".zip", ".7z", ".rar", ".gz", ".xz", ".zst", ".tar", ".iso", ".bin", ".dat", ".pak",
}

# Leading bytes of executables, shader containers, media and archives.
BLOCKED_MAGIC = [
    (b"MZ", "PE executable"), (b"\x7fELF", "ELF executable"), (b"DXBC", "DXBC shader"),
    (b"\x03\x02\x23\x07", "SPIR-V module"), (b"\x07\x23\x02\x03", "SPIR-V module"), (b"KB2", "Bink 2 video"),
    (b"BIK", "Bink video"), (b"OggS", "Ogg stream"), (b"RIFF", "RIFF media"), (b"DDS ", "DDS texture"),
    (b"PK\x03\x04", "zip archive"), (b"7z\xbc\xaf", "7z archive"), (b"Rar!", "rar archive"),
    (b"\x1f\x8b", "gzip stream"), (b"\x28\xb5\x2f\xfd", "zstd stream"), (b"\x78\x9c", "zlib stream"),
    (b"\x78\xda", "zlib stream"),
]

IMAGE_DIR = "docs/images/"
CODE_DIRS = ("src/", "bot/", "tools/")
ENGINE_CODE_DIRS = ("engine/tools/", "engine/runtime/src/", "engine/runtime/shims/")
ENGINE_CODE_EXT = (".py", ".cpp", ".h", ".hpp", ".c", ".rs", ".comp", ".hlsl", ".asm")
ENGINE_TEST_DIRS = ("engine/tests/", "engine/runtime/test/")
IMAGE_EXTENSIONS = {".png", ".svg", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_IMAGE_BYTES = 512 * 1024
MAX_TEXT_FILE_BYTES = 2 * 1024 * 1024
MAX_CHANGED_LINES = 1500
TRUSTED_MERGED_PRS = 3
REQUIRED_SCORE = 2.0
TRUSTED_WEIGHT = 1.0
NEW_WEIGHT = 0.5
MIN_REVIEWERS = 2
REVIEWERS_PER_PR = 3
QUIET_HOURS = 24
CLAIM_HOURS = 72


def _ext(path):
    name = path.rsplit("/", 1)[-1].lower()
    return name[name.rfind("."):] if "." in name else ""


def is_binary(data):
    if not data:
        return False
    if b"\0" in data[:8192]:
        return True
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def entropy(data):
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    n = len(data)
    return -sum(c / n * math.log2(c / n) for c in counts if c)


def check_file(path, data):
    """Return a reason string if this added or changed file may be game data, else None."""
    ext = _ext(path)
    if ext in BLOCKED_EXTENSIONS:
        return f"{path}: files of type {ext} are not accepted (possible game data or binary)"
    image = path.startswith(IMAGE_DIR) and ext in IMAGE_EXTENSIONS
    for magic, what in BLOCKED_MAGIC:
        # WebP images are RIFF containers; an image may start like one, never like an executable.
        if data.startswith(magic) and not (image and what == "RIFF media" and data[8:12] == b"WEBP"):
            return f"{path}: content starts like a {what}"
    if is_binary(data):
        if not image:
            return f"{path}: binary files are accepted only as images under {IMAGE_DIR}"
        if len(data) > MAX_IMAGE_BYTES:
            return f"{path}: images are limited to {MAX_IMAGE_BYTES // 1024} KiB"
        return None
    if len(data) > MAX_TEXT_FILE_BYTES:
        return f"{path}: text files are limited to {MAX_TEXT_FILE_BYTES // (1024 * 1024)} MiB"
    # Long runs of hex or base64 are how binaries get smuggled in as text.
    for m in re.finditer(rb"[A-Za-z0-9+/=]{4096,}", data):
        if entropy(m.group(0)) > 5.0:
            return f"{path}: contains a long encoded blob (base64 or similar); binary data is not accepted"
    if re.search(rb"(?:0x[0-9a-fA-F]{2}\s*,\s*){4096,}", data):
        return f"{path}: contains a large byte array; embedded binary data is not accepted"
    return None


TASK_RE = re.compile(r"(?im)^\s*(?:closes|fixes|resolves)\s+#(\d+)\b")
# One `- item` per line, no DOTALL: text after the list (a footer) must not be read as an item.
PROVENANCE_RE = re.compile(r"(?im)^[ \t]*provenance:[ \t]*\n((?:[ \t]*-[ \t]*.+(?:\n|$))+)")
LICENSE_IN_LINE = re.compile(r"\(([A-Za-z0-9.+\-]+)\)")


def task_number(body):
    m = TASK_RE.search(body or "")
    return int(m.group(1)) if m else None


def provenance_problems(body):
    m = PROVENANCE_RE.search(body or "")
    if not m:
        return ["no `Provenance:` section (list `- original` or each source with its licence)"]
    problems = []
    for line in m.group(1).splitlines():
        line = line.strip().lstrip("-").strip()
        if not line or line.lower() == "original":
            continue
        lic = LICENSE_IN_LINE.search(line)
        if not lic:
            problems.append(f"provenance line without a licence in parentheses: `{line}`")
        elif lic.group(1) not in ALLOWED_LICENSES:
            problems.append(f"licence {lic.group(1)} is not compatible with GPL-3.0-or-later: `{line}`")
    return problems


SYNC_PREFIX = "engine/"


def is_upstream_sync(pr, paths, sync_accounts):
    """A pull request from the engine sync workflow: labelled, from a listed account, touching only engine/."""
    paths = list(paths)
    return ("upstream-sync" in pr["labels"] and pr["author"] in sync_accounts and bool(paths)
            and all(p.startswith(SYNC_PREFIX) for p in paths))


def gate(pr, files, task, other_open_prs, commits, sync=False):
    """Check a pull request.

    pr: {"number", "author", "body", "labels", "additions", "deletions"}
    files: [(path, bytes)] for added or modified files
    task: {"number", "assignees", "labels", "state"} or None
    other_open_prs: [{"number", "body"}] excluding this one
    commits: [message]
    Returns (hard, soft): lists of reasons. Hard closes the PR now; soft gives fix_deadline_hours().
    """
    hard, soft = [], []
    for path, data in files:
        reason = check_file(path, data)
        if reason:
            hard.append(reason)
        if path.startswith(("results/", "title-runs/")) and path.rsplit("/", 1)[-1] != f"{pr['author']}.json":
            hard.append(f"{path}: a report must be named after its author ({pr['author']}.json)")
    num = task_number(pr["body"])
    if num is None:
        hard.append("no `Closes #<task>` line: claim a task with `/claim` and reference it")
    elif task is None or "task" not in task["labels"]:
        hard.append(f"#{num} is not a task issue")
    elif pr["author"] not in task["assignees"]:
        hard.append(f"task #{num} is not assigned to @{pr['author']}: comment `/claim` on it first")
    if num is not None:
        for other in other_open_prs:
            if task_number(other["body"]) == num and other["number"] < pr["number"]:
                hard.append(f"#{other['number']} already closes task #{num}")
    hard.extend(provenance_problems(pr["body"]))
    # Upstream commits keep their authors' own messages; the sync PR's Provenance names their source instead.
    if not sync and any(not re.search(r"(?m)^Signed-off-by: .+ <.+>", c) for c in commits):
        soft.append("every commit needs a `Signed-off-by:` line (`git commit -s`)")
    changed = {p for p, _ in files}
    if any(p.startswith(CODE_DIRS) for p in changed) and not any(p.startswith("tests/") for p in changed):
        soft.append("changes to code (" + ", ".join(CODE_DIRS) + ") need a test under tests/")
    engine_code = [p for p in changed if p.startswith(ENGINE_CODE_DIRS) and p.endswith(ENGINE_CODE_EXT)]
    if not sync and engine_code and not any(p.startswith(ENGINE_TEST_DIRS) for p in changed):
        soft.append("changes to engine code need a test in engine/tests/ or engine/runtime/test/ (docs/engine-dev.md)")
    if not sync and pr["additions"] + pr["deletions"] > MAX_CHANGED_LINES and "large" not in pr["labels"]:
        soft.append(f"more than {MAX_CHANGED_LINES} changed lines: split it, or ask a maintainer for `large`")
    return hard, soft


def task_ready(task_body, closed_issue_numbers):
    """A task is ready when every `Depends on #N` it lists is closed."""
    deps = [int(n) for n in re.findall(r"(?i)depends on #(\d+)", task_body or "")]
    return all(d in closed_issue_numbers for d in deps), deps


MAX_CLAIMS = 2
MAX_CLAIMS_MAINTAINER = 6


def can_claim(task, user, open_claims_by_user, max_claims=MAX_CLAIMS):
    if "task" not in task["labels"]:
        return "this issue is not a task"
    if "ready" not in task["labels"]:
        return "this task is not ready yet: the tasks it depends on are still open"
    if task["assignees"]:
        return f"already claimed by @{task['assignees'][0]}"
    if open_claims_by_user >= max_claims:
        return f"you already hold {max_claims} claims; finish one first"
    return None


def fix_deadline_hours(active_people):
    """Hours a pull request author gets to fix soft problems, shorter the busier the project is.

    active_people: distinct authors and reviewers active in the last 24 hours.
    Half-way through, the fix also becomes a task anyone can take (see adoption_due).
    """
    if active_people >= 50:
        return 4
    if active_people >= 20:
        return 8
    if active_people >= 5:
        return 24
    return 48


def adoption_due(hours_since_flag, hours_since_author_activity, active_people):
    """Open a fix task for others once half the deadline has passed with no word from the author."""
    half = fix_deadline_hours(active_people) / 2
    return hours_since_flag >= half and hours_since_author_activity >= half


def pick_reviewers(pool, exclude, seed, k=REVIEWERS_PER_PR):
    """Choose k reviewers from the opted-in pool, deterministically from `seed` (PR number + head sha).

    Reviewers are assigned, not volunteered, so an author cannot steer their pull request to friends or to
    their own second account; a new push gets a new draw.
    """
    import hashlib
    cands = sorted(set(pool) - set(exclude))
    return sorted(cands, key=lambda u: hashlib.sha256(f"{seed}:{u}".encode()).hexdigest())[:k]


VERDICT_RE = re.compile(r"(?im)^\s*verdict:\s*(approve|reject)\b")
CHECKED_RE = re.compile(r"(?ims)^\s*checked:\s*\n((?:\s*-\s*.+\n?){3,})")
REPRO_RE = re.compile(r"(?im)^\s*reproduced:\s*([0-9a-f]{64})\b")
BROKE_RE = re.compile(r"(?im)^\s*tried to break:\s*(.{20,})$")


def parse_review(body):
    """A review counts only in this form (see AGENTS.md):

        Verdict: approve | reject
        Checked:
        - three or more concrete things checked against the task, not the author's description
        Tried to break: <what you tried that could have failed, at least a sentence>
        Reproduced: <sha256 of your own test log>

    Returns (verdict or None, problems).
    """
    body = body or ""
    v = VERDICT_RE.search(body)
    problems = []
    if not v:
        problems.append("no `Verdict: approve|reject` line")
    if not CHECKED_RE.search(body):
        problems.append("`Checked:` needs three or more items")
    if not BROKE_RE.search(body):
        problems.append("no `Tried to break:` line")
    r = REPRO_RE.search(body)
    if not r:
        problems.append("no `Reproduced: <sha256 of your test log>` line")
    verdict = v.group(1).lower() if v else None
    return (verdict if not problems else None), problems, (r.group(1) if r else None)


# Files that define the rules or run with write access. A pull request touching any of them is welcome, but
# it is never merged automatically: it gets more reviewers, a longer quiet period, and a maintainer merges it.
PROTECTED = ("bot/", ".github/", "MAINTAINERS", "GOVERNANCE.md", "CONTRIBUTING.md", "AGENTS.md", "LICENSE",
             "CLAUDE.md", "GEMINI.md", ".cursorrules", "tools/fails_on_base.py", "SECURITY.md",
             "CODE_OF_CONDUCT.md", "builds/", "SYNC_ACCOUNTS", "tools/scan_history.py")
GOVERNANCE_REVIEWERS = 5
GOVERNANCE_QUIET_HOURS = 72


def protected_paths(paths):
    return sorted(p for p in paths if p.startswith(PROTECTED) or p in PROTECTED)


def governance_status(pr, reviews, ci_ok, hours_since_push, maintainers):
    """For a governance pull request: is it ready for a maintainer to merge by hand? Returns (ready, reason).

    Needs green CI, GOVERNANCE_QUIET_HOURS without a push, no valid reject from anyone, and valid approvals from
    two maintainers other than the author (one while there is only one other maintainer).
    """
    if not ci_ok:
        return False, "CI not green"
    latest = {}
    for r in reviews:
        if r["user"] == pr["author"] or r["commit"] != pr["head"]:
            continue
        verdict, _, _ = parse_review(r["body"])
        if verdict:
            latest[r["user"]] = verdict
    if any(v == "reject" for v in latest.values()):
        return False, "a reviewer rejected it"
    others = set(maintainers) - {pr["author"]}
    need = min(2, len(others))
    got = sorted(u for u, v in latest.items() if v == "approve" and u in others)
    if need == 0:
        return False, "no maintainer other than the author can approve it"
    if len(got) < need:
        return False, f"{len(got)}/{need} maintainer approvals"
    if hours_since_push < GOVERNANCE_QUIET_HOURS:
        return False, f"waiting for {GOVERNANCE_QUIET_HOURS} h without a push"
    return True, "approved by " + ", ".join("@" + u for u in got)


def merge_decision(pr, reviews, ci_ok, merged_count, hours_since_push, maintainers, assigned):
    """Return (merge, reason).

    reviews: [{"user", "body", "commit"}] in time order; the latest valid one per user counts, and only reviews
    of the current head commit from bot-assigned reviewers count.
    assigned: reviewers the bot drew for this head commit.
    Anyone may review (people and agents alike); a trusted reviewer weighs TRUSTED_WEIGHT, a new one NEW_WEIGHT.
    Any valid reject blocks. Reproduced digests from approvers must agree.
    """
    if "hold" in pr["labels"]:
        return False, "on hold"
    if "governance" in pr["labels"] or pr.get("protected"):
        return False, "changes protected files: a maintainer merges it by hand"
    if not ci_ok:
        return False, "CI not green"
    if pr.get("sync"):
        # Upstream engine commits were reviewed in their own project and scanned here; they merge on green CI
        # after the quiet period unless anyone rejects or a maintainer holds them.
        for r in reviews:
            if r["commit"] == pr["head"] and parse_review(r["body"])[0] == "reject":
                return False, "a reviewer rejected it"
        if hours_since_push < QUIET_HOURS:
            return False, f"waiting for {QUIET_HOURS} h without a push"
        return True, "upstream engine sync, green CI, no objection"
    latest = {}
    for r in reviews:
        if r["user"] == pr["author"] or r["user"] not in assigned or r["commit"] != pr["head"]:
            continue
        verdict, _, digest = parse_review(r["body"])
        if verdict:
            latest[r["user"]] = (verdict, digest)
    if any(v == "reject" for v, _ in latest.values()):
        return False, "a reviewer rejected it"
    approvers = [u for u, (v, _) in latest.items() if v == "approve"]
    digests = {d for u, (v, d) in latest.items() if v == "approve"}
    if len(digests) > 1:
        return False, "approvers' reproduced test logs differ"
    score = sum(TRUSTED_WEIGHT if merged_count.get(u, 0) >= TRUSTED_MERGED_PRS or u in maintainers
                else NEW_WEIGHT for u in approvers)
    if len(approvers) < MIN_REVIEWERS or score < REQUIRED_SCORE:
        return False, f"review score {score:g}/{REQUIRED_SCORE:g} from {len(approvers)} reviewers"
    if hours_since_push < QUIET_HOURS:
        return False, f"waiting for {QUIET_HOURS} h without a push"
    return True, "approved by " + ", ".join("@" + a for a in sorted(approvers))


SPLIT_LINE = re.compile(r"^\s*-\s*(.+?)(?:\s*\|\s*depends:\s*([\d,\s]+))?\s*$")


def parse_split(text, max_parts=12):
    """`/split` followed by lines `- <title>` or `- <title> | depends: 1, 2` (1-based, earlier lines only).

    Returns [(title, [indexes of earlier parts])] or raises ValueError.
    """
    lines = [l for l in text.splitlines()[1:] if l.strip()]
    parts = []
    for i, line in enumerate(lines, 1):
        m = SPLIT_LINE.match(line)
        if not m or len(m.group(1)) < 8:
            raise ValueError(f"line {i}: expected `- <title of 8+ characters> [| depends: N, M]`")
        deps = [int(d) for d in re.findall(r"\d+", m.group(2) or "")]
        if any(d < 1 or d >= i for d in deps):
            raise ValueError(f"line {i}: depends may only name earlier lines")
        parts.append((m.group(1).strip(), deps))
    if not 2 <= len(parts) <= max_parts:
        raise ValueError(f"split into 2 to {max_parts} parts")
    return parts


def collusion_pairs(merges, min_mutual=3, min_share=0.8):
    """Find pairs who mostly approve each other.

    merges: [(author, [approvers])] for merged pull requests.
    A pair (a, b) is flagged when each approved the other at least min_mutual times and those approvals are at
    least min_share of all approvals each of them gave.
    """
    given, pair = {}, {}
    for author, approvers in merges:
        for r in approvers:
            if r == author:
                continue
            given[r] = given.get(r, 0) + 1
            pair[(r, author)] = pair.get((r, author), 0) + 1
    flagged = []
    for (a, b), n in pair.items():
        m = pair.get((b, a), 0)
        if a < b and n >= min_mutual and m >= min_mutual and n / given[a] >= min_share and m / given[b] >= min_share:
            flagged.append((a, b))
    return sorted(flagged)


PROPOSE_MERGED_PRS = 10
PROPOSE_ACTIVE_DAYS = 30


def maintainer_candidates(merged_count, first_seen_days, maintainers, already_proposed):
    """People to propose as maintainers: PROPOSE_MERGED_PRS merged pull requests and PROPOSE_ACTIVE_DAYS since
    their first one, not maintainers yet and not proposed before. Maintainers then decide in a `decision` issue."""
    return sorted(u for u, n in merged_count.items()
                  if n >= PROPOSE_MERGED_PRS and first_seen_days.get(u, 0) >= PROPOSE_ACTIVE_DAYS
                  and u not in maintainers and u not in already_proposed and not u.endswith("[bot]"))
