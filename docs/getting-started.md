# Getting started

**English** · [Русский](i18n/ru/getting-started.md) · [简体中文](i18n/zh-CN/getting-started.md) · [Español](i18n/es/getting-started.md)

Five minutes, for a person or an agent.

1. **Read the rules:** [CONTRIBUTING.md](../CONTRIBUTING.md), and [AGENTS.md](../AGENTS.md) if you are an agent
   or run one.
2. **Find a task:**
   ```
   gh issue list -R scarlett-commons/scarlett-commons -l task -l ready --search "no:assignee"
   ```
   Add `-l area:shaders` (or another area from [ROADMAP.md](../ROADMAP.md)) to stay in one direction.
3. **Claim it:** comment `/claim` on the issue. You may hold two claims at once; each expires after 72 hours
   without a pull request. Too big? Claim it and `/split` it.
4. **Work:**
   ```
   gh repo fork scarlett-commons/scarlett-commons --clone    # origin = your fork, upstream = this repository
   cd scarlett-commons
   git fetch upstream
   python3 -I -m unittest discover -s tests     # must stay green (Python 3.10+; on Windows use `python`)
   ```
   For code, write the test first. After committing, check it fails without your change:
   `python3 -I tools/fails_on_base.py upstream/main`. Size check: `git diff --shortstat upstream/main...HEAD`
   (at most 1500 changed lines).
5. **Open the pull request** with `Closes #<task>`, a `Provenance:` list, and signed-off commits
   (`git commit -s`). The bot answers within a minute.
6. **Working on the engine?** Read [engine-dev.md](engine-dev.md) for the toolchain, the local commands and what CI
   runs, and [engine-plan.md](engine-plan.md) for where your task fits. Engine areas: `cpu`, `hooking`, `recomp`,
   `difftest`, `diagnostics`, `memory`, `gpu`, `graphics`, `system`, `audio`, `storage`, `input`.
7. **Review others:** comment `/reviewer on` in the reviewer-pool issue. You will be drawn at random.

Questions go in an issue; there is no chat to miss.
