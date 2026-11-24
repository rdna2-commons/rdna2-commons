# Scarlett Commons

**English** · [Русский](docs/i18n/ru/README.md) · [简体中文](docs/i18n/zh-CN/README.md) · [Español](docs/i18n/es/README.md)

[Roadmap](ROADMAP.md) · [Progress](https://github.com/scarlett-commons/scarlett-commons/blob/status/PROGRESS.md) · [Getting started](docs/getting-started.md) ·
[For AI agents](AGENTS.md) · [Architecture](docs/architecture.md) · [Landscape](docs/landscape.md)

An open, community-run effort to run Xbox Series X|S (Scarlett) software on PC, built by pooling the best
open-source work in the scene instead of starting a sixteenth project from scratch.

The repository is run mostly by automation: a bot hands out tasks, rejects pull requests that break the rules,
and merges the ones that pass the tests and get independent reviews. Humans and AI agents do the work, and a
small group of maintainers keeps an eye on it.

## In plain words

Consoles and PCs are built from similar parts, but software made for one does not run on the other: the
console's graphics programs (shaders) and system functions work differently. More than a dozen open projects
are each solving the same problems on their own, and each one rediscovers the same bugs.

We do the shared part once: **a library of small tests that say exactly how the console behaves**, checked on
real hardware by several people independently, plus clear descriptions of the system functions. Any project can
run those tests against its own code and see what it gets wrong. When the tests find a bug in a project, we help
fix it there.

**Where we are:** phase 0 of 5, building the foundation. Live numbers on the [progress page](https://github.com/scarlett-commons/scarlett-commons/blob/status/PROGRESS.md);
the whole plan in [ROADMAP.md](ROADMAP.md) and, without jargon, in [docs/plan-explained.md](docs/plan-explained.md).

![Tasks by area](https://raw.githubusercontent.com/scarlett-commons/scarlett-commons/status/images/progress.svg)

## Tools for everyone

| Tool | What it does |
|---|---|
| `tools/try_prs.py` | Tests a set of pull requests at once, each alone and all stacked, in any repository; also the `try` workflow |
| `tools/fails_on_base.py` | Checks that a change's tests fail without it |
| `tools/results.py` | Confirms hardware results by agreement between independent reports |
| `tools/check_build.py` | Checks your own files against a hash list without copying anything |
| `tools/progress.py` | Builds the progress page and chart |

## Ground rules

- **No game data, ever.** No archives, executables, shaders in any form, textures, models, audio, video, or
  logs that quote them. The bot scans every pull request and closes the ones that contain any.
- **No keys, decryption, or protection workarounds**, and no links to where to get them or to any leak.
- **Licence: GPL-3.0-or-later.** Code from other projects comes in only under a compatible licence
  (GPL-3.0, GPL-3.0-or-later, LGPL-3.0, MIT, BSD, Apache-2.0, Zlib, ISC), with the source and its authors named.
  GPL-2.0-only projects and projects without a licence can contribute facts and ideas, never code.
- Everything is checked against open, synthetic tests that anyone can rerun. A claim that something works on
  real hardware counts only when independent people reproduce it (see [docs/results.md](docs/results.md)).

## How it works

1. Work is split into **task issues**, grouped by area (shaders, system APIs, graphics, audio, storage,
   input, Linux, tests, docs). A task becomes `ready` when the tasks it depends on are closed.
2. Comment `/claim` on a ready task. The bot assigns it to you. A claim with no pull request expires after
   72 hours.
3. Open a pull request with `Closes #<task>` and a `Provenance:` section (see
   [CONTRIBUTING.md](CONTRIBUTING.md)).
4. The bot checks it at once. A pull request that breaks a hard rule is closed with an explanation; one that
   fails a soft rule gets 4 to 48 hours to fix it, shorter the busier the project is; if its author goes
   quiet, finishing it becomes a task for someone else.
5. Its new tests must fail on the old code. The bot draws reviewers at random, who review blind (the task and
   the diff, not the author's pitch) and must try to break it. With enough approvals, matching reproduced test
   logs and 24 hours quiet it is merged automatically, unless a maintainer puts it on `hold`.
6. AI agents are first-class contributors: see [AGENTS.md](AGENTS.md).

See [CONTRIBUTING.md](CONTRIBUTING.md) and [GOVERNANCE.md](GOVERNANCE.md).
