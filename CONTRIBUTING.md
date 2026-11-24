# Contributing

AI agents are welcome on the same terms as people. The person who runs an agent answers for what it posts.

## The pull request

- One task per pull request, with `Closes #<task number>` in the description. The task must be assigned to
  you (comment `/claim` on it first).
- Every change to code (`src/`, `bot/`, `tools/`) comes with a test under `tests/` that fails without it.
- At most 1500 changed lines, unless a maintainer adds the `large` label.
- Every commit carries a `Signed-off-by:` line ([DCO](https://developercertificate.org/)): you certify you
  have the right to submit it under this project's licence.
- A `Provenance:` section in the description lists where the code comes from, one line per source:

      Provenance:
      - original
      - https://github.com/owner/repo (GPL-3.0-or-later): src/foo.rs, adapted

  Allowed licences: GPL-3.0, GPL-3.0-or-later, LGPL-3.0, MIT, BSD-2-Clause, BSD-3-Clause, Apache-2.0, Zlib,
  ISC. Code read from a project under any other licence (GPL-2.0-only, none at all) cannot be rewritten into
  this one either: that is still a derived work. Write down the facts instead (a format, a behaviour) in
  `docs/`, citing where you learned them.

## What the bot closes at once (hard rules)

- Any file that looks like game data: a blocked extension, a known media or executable signature, or a binary
  file outside `docs/images/`.
- No `Closes #<task>`, or a task not assigned to the author.
- Another open pull request already closes the same task (the later one is closed).
- A `Provenance:` line with a licence that is not allowed, or no `Provenance:` section.

## What the bot gives a short time to fix (soft rules)

- Failing CI, missing test, a test that already passes without the change, missing sign-off, too large.
- The time depends on how busy the project is: 48 hours with fewer than 5 active people, 24 with 5 or more,
  8 with 20 or more, 4 with 50 or more. Half-way through, if the author is quiet, the bot opens a
  `Finish #N` task so someone else can complete it.

## Tests must prove something

`verify` runs the tests a pull request adds or changes against the **old** code. When code (`src/`, `bot/`,
`tools/`) changed, at least one of them must fail there. A test that passes without the change does not test it.

## Reviews

Anyone may review, people and agents alike, but only reviewers the bot draws at random for the current commit
count, and only in the form in AGENTS.md. Trusted reviewers (three merged pull requests or more) weigh 1, new
ones 0.5; a merge needs a score of 2 from at least two of them, no valid reject, matching reproduced test
logs, green CI and 24 hours without a push. A maintainer can stop it with `hold`.

## Hardware results

See [docs/results.md](docs/results.md): a result counts when two different people report the same output
digest for the same test, commit, and hardware class.
