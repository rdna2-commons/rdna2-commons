# Getting started

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
   gh repo fork scarlett-commons/scarlett-commons --clone
   cd scarlett-commons
   python3 -I -m unittest discover -s tests     # must stay green
   ```
   Write the test first and check it fails without your change: `python3 -I tools/fails_on_base.py origin/main`.
5. **Open the pull request** with `Closes #<task>`, a `Provenance:` list, and signed-off commits
   (`git commit -s`). The bot answers within a minute.
6. **Review others:** comment `/reviewer on` in the reviewer-pool issue. You will be drawn at random.

Questions go in an issue; there is no chat to miss.
