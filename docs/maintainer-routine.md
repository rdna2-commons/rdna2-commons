# Maintainer routine

Short on purpose: the bot does the routine, maintainers check the bot. A maintainer's agent (Claude Code or any
other) can run this unattended; anything that needs a judgement call goes to a `decision` issue instead of being
done.

**Each run (weekly, or when someone pings `@maintainers`):**

1. **Re-verify a sample.** Pick 3 merged pull requests at random from the last week. Check each out, run its
   tests and `tools/fails_on_base.py <its base>`, and compare with what its reviewers reported. Revert a merge
   that does not hold up, with the reason in the revert.
2. **Look for collusion.** Run `rules.collusion_pairs` over the last 100 merges. A flagged pair is not proof:
   open a `decision` issue, and take their reviews out of the pool until it is settled.
3. **Read what the bot closed.** Skim the `rejected` pull requests. A rule that keeps closing good work is a
   bug in the rule: fix it in `bot/rules.py` with a test.
4. **Keep the board full.** If fewer than 20 tasks are `ready`, turn the best `Scout` issues into tasks, or
   split big ones.
5. **Keep the docs true.** Check README's status table, milestones and "Priority now" line, ROADMAP and
   docs/engine-plan.md against the board and the latest title-run reports; fix what changed (an agent can do it
   with the audit prompt in this file's history). Out-of-date status is a bug.
6. **Legal sweep.** Search the tree and the open pull requests for anything that slipped past the gate (game
   data, links to leaks, code from incompatible licences). Remove first, discuss after.

Report in one comment on the pinned `status` issue: what was checked, what was reverted, what needs a decision.
