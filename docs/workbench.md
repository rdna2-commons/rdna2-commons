# Workbench: local work, saved and reviewed

Scripts written while chasing a bug change every few minutes; pull requests take hours. The workbench keeps
that local work safe without publishing it unreviewed.

## How it works

1. **Auto-commit, local only.** A timer commits an allowlist of files (`*.ps1`, `*.py`, `*.sh`, `*.md`) from
   the working folders into a local repository, on the `workbench` branch. It never pushes.
2. **Refusals.** A file is skipped and reported if it looks like title data or a secret: the repository's
   game-data guard, a size limit, binary content, or a token pattern. Logs, frames, dumps and anything under a
   title's folder are never on the allowlist.
3. **Review.** An agent session (or a person) reviews the workbench before anything leaves the machine.
4. **Publish.** What is worth keeping becomes an ordinary pull request here: a claimed task, `Closes #N`,
   `Provenance:`, a test, sign-off.

The tool:

```sh
python -I tools/workbench.py --repo <local workbench repo> --source <folder> [--source <folder> ...] [--depth 2]
```

It refuses a repository that has any remote, so nothing it saves can be pushed by accident. A file that turns
into a refusal later is removed from the next commit. On Windows, run it every 30 minutes with Task Scheduler:

```powershell
schtasks /Create /TN workbench /SC MINUTE /MO 30 /TR "python -I C:\path\to\tools\workbench.py --repo C:\dev\workbench --source C:\dev\run1"
```

## Reviewing the workbench (for agents)

Review with fresh eyes, as for any pull request (AGENTS.md, "Reviewing"): assume each change is wrong.

1. `git log --stat workbench` since the last review tag `reviewed/<date>`. Read every diff.
2. For each file decide one of:
   - **publish**: generic, useful to others, no machine-specific paths left. Move it into `tools/` with a test
     and open a pull request against a task.
   - **keep local**: useful only on this machine. Leave it.
   - **drop**: dead experiments. Note them in the review summary; the history keeps them.
3. Before publishing, remove user names, home folders, local drive paths, and anything read from a title. Run
   `python -I tools/scan_history.py` over the branch you are about to push.
4. Tag the reviewed commit `reviewed/<date>` and write a short summary: what was published, kept and dropped.

## Continuing work in a new session

A new session starts from what is written down, not from memory:

1. Read AGENTS.md, then the plan of the line you work on: [ps5/plan.md](ps5/plan.md) for the PS5 line,
   [engine-plan.md](engine-plan.md) for the Xbox line.
2. Take the highest-priority `ready` task whose files no other open task touches, and `/claim` it.
3. Read the current numbers in [ps5/status.md](ps5/status.md); after your run, update them.
4. Leave the state in the task issue when you stop: what was tried, what the last run showed, what is next.
