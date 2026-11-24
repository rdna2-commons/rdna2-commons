# Engine sync

`engine/` follows [ubiquitarianism/leonida](https://github.com/ubiquitarianism/leonida) automatically, keeping
every upstream commit and its author.

**What happens, every day:**

1. The `sync-engine` workflow clones upstream and filters it to the same paths the import took (`tools/`,
   `runtime/`, `tests/`, `scripts/`, compatibly licensed `third_party/`), under `engine/`.
2. If there is anything new, it runs `tools/scan_history.py` over **every new file version**, not just the final
   tree, and stops if the game-data guard flags anything.
3. It opens one pull request labelled `upstream-sync`, closing a task it claims for itself.
4. The bot treats it as an upstream sync only if it comes from an account in `SYNC_ACCOUNTS` and touches nothing
   outside `engine/`. Then sign-off and size rules are skipped (the commits are upstream's, credited by
   `Provenance:`), and it merges **with a merge commit** on green CI after 24 hours, unless any valid review
   rejects it or a maintainer adds `hold`. Anything else in it, and it is an ordinary pull request.

**Setting it up (once, by a maintainer):** create or pick the account that will open the sync pull requests,
add its login to `SYNC_ACCOUNTS` (a governance change), and store a fine-grained token of that account with
contents and pull request write access to this repository as the secret `SYNC_TOKEN`. Until then the workflow
does nothing.

**Our own changes to engine/** go upstream first when they are general, so the two stay close; changes that only
make sense here are fine too, and merge conflicts in a sync pull request are resolved by hand like any other.
