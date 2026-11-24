# Governance

The project belongs to its contributors. Maintainers keep it safe, they do not own it.

- **Trusted contributor:** three merged pull requests or more. Computed by the bot from the history; nobody
  hands it out.
- **Maintainers:** listed in `MAINTAINERS`. They may add `hold`, `large`, or `ready`, revert a merge, and add
  or retire maintainers by a pull request to `MAINTAINERS` that two other maintainers approve. A maintainer
  inactive for 90 days is retired.
- **Disputes** go to an issue labelled `decision`; maintainers decide by simple majority after 72 hours.
- **Legal requests** (DMCA and similar): any maintainer may remove the named content at once, then open a
  `decision` issue. The project keeps mirrors so a takedown of one host does not lose the history.
- **Bots** do the routine: claims, expiry, rule checks, merges. A maintainer can always override them by hand
  and the override is logged in the pull request.
- **Audits.** A maintainer (or a maintainer's agent) regularly re-checks the bot: re-runs the tests of a
  random sample of merged pull requests, looks for reviewers who always approve each other, and reverts what
  does not hold up. The routine is in docs/maintainer-routine.md.
- **Bootstrap.** While the reviewer pool has fewer than three people other than a pull request's author, a
  maintainer may merge it by hand once gate, CI and verify are green, with a comment starting `bootstrap merge:`
  that says why. This ends for good once the pool is that large.
