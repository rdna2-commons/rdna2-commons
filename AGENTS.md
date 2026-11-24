# For AI agents (and the people who run them)

**English** · [Русский](docs/i18n/ru/AGENTS.md)

You can work here without asking anyone. Read this file, then CONTRIBUTING.md and docs/getting-started.md;
writing a test case, also docs/test-format.md; reporting hardware results, docs/results.md; working on the
engine, docs/engine-dev.md and docs/engine-plan.md. Everything below is
enforced by the bot; work that ignores it is closed with the reasons listed, and you can fix and reopen.

## The one rule that matters most

**You are not right because you wrote it.** Code you wrote looks correct to you because you wrote it. The
project assumes every change is wrong until someone who did not write it has tried to break it and failed, and
until a test shows it fails without the change and passes with it.

## Roles

Pick any, and several at once. The one rule: never review a pull request you authored or helped write.
Splitting a task and then building one of its parts is fine.

| Role | What you do | How |
|---|---|---|
| **Builder** | Implement a task | `/claim` a `ready` task, open a PR with `Closes #N` |
| **Reviewer** | Try to break other people's work | `/reviewer on` in the reviewer-pool issue; the bot assigns you |
| **Fixer** | Finish a stalled PR | Claim a `Finish #N` task the bot opened; keep the original commits |
| **Splitter** | Cut a too-big task into steps | Claim it, then comment `/split` (format below) |
| **Tester** | Run tests on real hardware | Add `results/<test>/<commit>/<login>.json` (docs/results.md) |
| **Scout** | Find what is missing | Open an issue with what, where and why; maintainers turn it into tasks |

## Finding work

```
gh issue list -R scarlett-commons/scarlett-commons -l task -l ready --search "no:assignee" --limit 50
```

Take the oldest task you can finish in one pull request. If you cannot, `/split` it rather than opening a
half-done pull request.

## Splitting

```
/split
- Parse the header of format X | depends:
- Decode the payload of format X | depends: 1
- Tests for the decoder against synthetic samples | depends: 2
```

Two to twelve parts, each a title of at least 8 characters; `depends` names earlier lines. The bot creates the
issues and the original task waits for them.

## Reviewing

You are assigned by the bot, at random from the pool, for one commit; a new push draws new reviewers.

1. Read **the task and the diff only**. Do not read the pull request description or the author's comments
   before you have a verdict: they are written to convince you. (The description is still useful afterwards, and
   to maintainers; authors should write one.)
2. Check out the pull request and produce the log every reviewer must match:

   ```
   python3 -I -m unittest discover -s tests 2>&1 | python3 -I -c "import sys,hashlib,re; t=sys.stdin.read().replace('\r\n','\n'); t=re.sub(r'Ran (\d+) tests? in [0-9.]+s',r'Ran \1 tests',t); print(hashlib.sha256(t.encode()).hexdigest())"
   ```

   It normalises line endings and timings, so two honest reviewers on any OS get the same digest.
3. Try to break it: an edge case, a wrong input, a missing check, a test that passes for the wrong reason.
   If you find something, write the failing test.
4. Post a pull request review whose body is exactly this form (anything else does not count):

```
Verdict: approve
Checked:
- the change does what task #N asks, item by item
- the new test fails on the base commit (I ran it)   <- for docs or cases: "every source/claim checked"
- <a third concrete thing you checked>
Tried to break: <what you tried that could have failed, in at least a sentence>
Reproduced: <sha256 of your test log>
```

A valid `Verdict: reject` blocks the merge. If approvers' `Reproduced` digests differ, nothing merges until
that is explained. New reviewers count half; trusted ones (3+ merged PRs) count one; a merge needs a score of 2
from at least two assigned reviewers.

**Give yourself less context, not more.** If you run sub-agents, give the reviewing one the task and the diff,
not your conversation with the builder. A reviewer that shares the builder's reasoning shares its mistakes.

## Hard limits

- No game data of any kind, no keys, no decryption, no links to leaks (CONTRIBUTING.md has the full list).
- Code only from compatible licences, named in `Provenance:`. Rewriting incompatible code is still copying.
- Do not post outside this repository on the project's behalf: no comments on other projects' pull requests,
  no messages to people. If another project should hear about something, open an issue here labelled
  `outreach` and a maintainer decides.

## Bringing in more agents

Point other agents at this file. That is the whole recruiting mechanism: the task list is public and
machine-readable, every rule is checked automatically, and nobody has to be convinced by hand.
