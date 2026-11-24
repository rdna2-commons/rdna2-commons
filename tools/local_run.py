"""Run the engine on your own copy of a title and write a scrubbed title-run report (docs/title-runs.md).

Usage:
  python -I tools/local_run.py --profile DIR --game DIR --work DIR [--seconds 180] [--stage-reached STAGE]
                               [--hw-class NAME] [--driver VERSION] [--version VERSION] [--skip-build]

  --profile  a checkout of the project that holds the title's build profile (for the title the engine was
             developed against, the Leonida continuation: its make_game.py and game/<version>.json). The profile is
             combined with this repository's engine/ in <work>/tree, so the build uses OUR engine.
  --game     your own copy, readable on disk. Nothing in it is copied into this repository or the report.
  --work     a folder for the build, the trace and the reports. Everything stays on your machine.

What it does:
  1. <work>/tree = this repository's engine/ (tools, runtime, scripts, third_party) + the profile's build files.
  2. Runs the profile's build there (make_game.py), which translates the shaders and builds the runtime.
  3. Hashes the title's executable and looks it up in builds/ (an unregistered build is reported as such).
  4. Runs the runtime for --seconds with --trace and LEONIDA_CRASH_FILE, then stops it.
  5. Writes <work>/report/<login>.json in the title-runs format, from an allow-list only: the stage reached, fps,
     where it stopped as module+offset, and counts of translated and failed shaders by reason. No file contents,
     shader code, text the title prints, paths or images. Check it, then submit it as described in
     docs/title-runs.md.

Only the stages up to first-frame are detected; pass --stage-reached menu|in-world|playable when you saw more.
"""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import title_runs  # noqa: E402

ENGINE_PARTS = ("tools", "runtime", "scripts", "third_party", "LICENSE")
PROFILE_PARTS = ("make_game.py", "game", "mods", "third_party/rpf9-explorer", "Build.bat", "Build.sh")
DETECTED = ["loads", "imports-resolved", "device-created", "first-frame"]
REASON_CHARS = re.compile(r"[^A-Za-z_ :()\-]")
ISA_PREFIXES = ("v_", "s_", "ds_", "buffer_", "tbuffer_", "image_", "global_", "flat_", "scratch_", "exp_")


# ---------------------------------------------------------------- pure parts (unit-tested, no title involved)

def stage_from_trace(lines):
    """The furthest detected stage, last fps, and the crash event, from --trace JSON lines."""
    stage, fps, crash = None, None, None
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        kind = e.get("kind")
        found = {"map": "loads", "dllmain": "imports-resolved", "tls_callback": "imports-resolved",
                 "device_created": "device-created", "first_frame": "first-frame",
                 "frames": "first-frame"}.get(kind)
        if found and (stage is None or DETECTED.index(found) > DETECTED.index(stage)):
            stage = found
        if kind == "frames" and isinstance(e.get("fps"), (int, float)):
            fps = round(float(e["fps"]), 2)
        if kind == "crash":
            crash = e
    return stage, fps, crash


def place(at):
    """module+0xOFFSET without the runtime's host: marker; anything else becomes empty."""
    at = (at or "").replace("host:", "")
    return at if re.match(r"^[A-Za-z0-9_.\-]+\+0x[0-9a-fA-F]{1,16}$", at) else ""


def stop_text(crash, timed_out, exit_code):
    if crash:
        where = place(crash.get("at"))
        code = crash.get("code", "")
        if where:
            access = crash.get("access")
            reason = "access violation" if code == "0xc0000005" else f"exception {code}"
            return f"{where} {reason}{' (' + access + ')' if access else ''}"[:140]
        return "crash at an unmapped address"
    if timed_out:
        return ""
    return f"exited with code {exit_code}" if exit_code not in (0, None) else ""


def reason_bucket(error):
    """`ExceptionType: message` -> a short reason with no numbers, names or quoted text."""
    kind, _, msg = (error or "").partition(":")
    msg = re.sub(r"'[^']*'|\"[^\"]*\"", "", msg)          # quoted names
    msg = re.sub(r"0x[0-9a-fA-F]+|\b\d+\b", "", msg)      # addresses and counts
    msg = REASON_CHARS.sub(" ", msg)
    # Words with an underscore are kept only when they are instruction mnemonics; anything else (a shader or file
    # name) is dropped.
    msg = " ".join(w for w in msg.split() if "_" not in w or w.startswith(ISA_PREFIXES))
    msg = re.sub(r"\s+", " ", msg).strip()[:60]
    kind = REASON_CHARS.sub("", kind)[:40] or "error"
    return f"{kind}: {msg}" if msg else kind


def shader_stats(index):
    """{name: meta} from the translator's index.json -> (total, failed, {reason: count})."""
    total, failed, reasons = 0, 0, {}
    for meta in (index or {}).values():
        total += 1
        if isinstance(meta, dict) and meta.get("error"):
            failed += 1
            r = reason_bucket(str(meta["error"]))
            reasons[r] = reasons.get(r, 0) + 1
    return total, failed, reasons


def notes_text(total, failed, reasons, limit=480):
    if not total:
        return "no shader index"
    out = f"shaders: {total - failed} of {total} translated"
    if failed:
        top = sorted(reasons.items(), key=lambda x: (-x[1], x[0]))
        parts = [f"{n} {r}" for r, n in top]
        out += "; failed: " + "; ".join(parts)
    return out[:limit]


def build_report(build_id, commit, hw_class, os_name, driver, stage, fps, stop, notes):
    run = {"build": build_id, "commit": commit, "hw_class": hw_class, "os": os_name, "driver": driver,
           "stage": stage, "fps": fps, "stop": stop, "notes": notes}
    return run


# ---------------------------------------------------------------- the run itself

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def registered_build(exe_hash):
    builds, _, _ = title_runs.load(os.path.join(ROOT, "builds"), os.path.join(ROOT, "title-runs"))
    return next((b["id"] for b in builds.values() if b["exe_sha256"] == exe_hash), None)


def assemble(profile, tree):
    os.makedirs(tree, exist_ok=True)
    for part in ENGINE_PARTS:
        src, dst = os.path.join(ROOT, "engine", part), os.path.join(tree, part)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("build", "__pycache__"))
        elif os.path.isfile(src):
            shutil.copy2(src, dst)
    for part in PROFILE_PARTS:
        src, dst = os.path.join(profile, part), os.path.join(tree, part)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        elif os.path.isfile(src):
            shutil.copy2(src, dst)
    if not os.path.isfile(os.path.join(tree, "make_game.py")):
        sys.exit(f"error: {profile} has no make_game.py: --profile must be a checkout with the title's build profile")


def profile_exe(tree, version):
    manifests = sorted(os.listdir(os.path.join(tree, "game")))
    for name in manifests:
        if name.endswith(".json") and (not version or version in name):
            with open(os.path.join(tree, "game", name), encoding="utf-8") as f:
                v = json.load(f)
            if v.get("expected_exe"):
                return v["expected_exe"]
    sys.exit("error: no game/<version>.json with expected_exe in the profile")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--profile", required=True)
    ap.add_argument("--game", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--seconds", type=int, default=180)
    ap.add_argument("--stage-reached", choices=title_runs.STAGES)
    ap.add_argument("--hw-class", default="unknown")
    ap.add_argument("--driver", default="unknown")
    ap.add_argument("--version", default="")
    ap.add_argument("--login", default=os.environ.get("GITHUB_USER", "me"))
    ap.add_argument("--skip-build", action="store_true", help="reuse <work>/out from an earlier run")
    a = ap.parse_args()

    work = os.path.abspath(a.work)
    tree, out, build_work = (os.path.join(work, x) for x in ("tree", "out", "build"))
    if not a.skip_build:
        assemble(os.path.abspath(a.profile), tree)
        print("== building with this repository's engine (make_game.py from the profile)")
        rc = subprocess.call([sys.executable, "-I", "make_game.py", "--game", a.game, "--out", out, "--work",
                              build_work], cwd=tree)
        if rc:
            print(f"warning: the build exited with {rc}; the report records how far the run got")

    exe_name = profile_exe(tree, a.version)
    exe = os.path.join(a.game, exe_name)
    exe_hash = sha256(exe) if os.path.isfile(exe) else ""
    build_id = registered_build(exe_hash) if exe_hash else None

    trace = os.path.join(work, f"trace-{int(time.time())}.jsonl")
    crash_file = os.path.join(work, "crash.jsonl")
    if os.path.exists(crash_file):
        os.remove(crash_file)
    runtime = os.path.join(out, "gta6rt.exe")
    timed_out, exit_code = False, None
    if os.path.isfile(runtime):
        env = dict(os.environ, LEONIDA_CRASH_FILE=crash_file)
        print(f"== running for up to {a.seconds} s")
        p = subprocess.Popen([runtime, "--run", exe, "--game-dir", a.game, "--overlay", os.path.join(work, "overlay"),
                              "--trace", trace], env=env)
        try:
            exit_code = p.wait(timeout=a.seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            p.kill()
            p.wait()
    else:
        print("warning: no runtime was built; the report has the shader results only")

    lines = open(trace, encoding="utf-8", errors="replace").read().splitlines() if os.path.isfile(trace) else []
    stage, fps, crash = stage_from_trace(lines)
    if os.path.isfile(crash_file):
        crash_lines = open(crash_file, encoding="utf-8", errors="replace").read().splitlines()
        crash = crash or (stage_from_trace(crash_lines)[2])
    if a.stage_reached and (stage is None or title_runs.STAGES.index(a.stage_reached) > title_runs.STAGES.index(stage)):
        stage = a.stage_reached
    index_path = os.path.join(build_work, "spirv", "index.json")
    index = json.load(open(index_path, encoding="utf-8")) if os.path.isfile(index_path) else {}
    total, failed, reasons = shader_stats(index)
    commit = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    report = build_report(build_id or "unregistered", commit, a.hw_class, f"{platform.system().lower()}-{platform.release()}",
                          a.driver, stage or "loads", fps, stop_text(crash, timed_out, exit_code),
                          notes_text(total, failed, reasons))
    problems = title_runs.validate_run(report, report["build"], commit, {report["build"]: {}})
    folder = os.path.join(work, "report")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{a.login}.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, indent=1)
        f.write("\n")
    print(json.dumps(report, indent=1))
    print(f"\nreport: {path}")
    if not build_id:
        print(f"this build is not registered yet; its executable hash is {exe_hash or 'unknown'}. A maintainer "
              "registers a build once two people confirm the hash (docs/title-runs.md).")
    for p in problems:
        print("check:", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
