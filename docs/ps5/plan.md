# PS5 line: plan

The PS5 line is the first priority: it is the shortest path to a playable title. Tasks are split so that two
sessions working at once do not touch the same files.

## Tasks

| Priority | Task | Where the code lands | Files it touches | Runs in parallel with |
|---|---|---|---|---|
| 1 | #219 PS5-A: the menu fills the output | AnyPS5 fork | VideoOut, flip, present | C, D, E |
| 1 | #220 PS5-B: from the menu into the world | AnyPS5 fork, wherever the blocker is | varies | D, E (A first) |
| 1 | #221 PS5-C: resources indexed from constant buffers | AnyPS5 fork | shader recompiler | A, D, E |
| 2 | #222 PS5-D: track B installed into the relinked executable | here (`recomp/`) | track B output, a loader for it | all |
| 2 | #223 PS5-E: readiness measured after every run | here (`tools/`) | the scorer, `status.md` numbers | all |
| 2 | #224 Workbench: safe auto-commit and review | here (`tools/`, `docs/`) | workbench scripts | all |
| 3 | Xbox line: GPU time per pipeline, wave64 compute, large mesh outputs | here (`victory/`) | the Xbox runtime | all; paused while the PS5 line has priority |

## Order

1. A: a readable picture first, so every later run can be judged from its frames.
2. B: drive the title forward one blocker at a time: run, score, fix the first blocker, run again. A blocker
   that needs more than one pull request becomes its own task.
3. C alongside A and B: the shader count only falls when the recompiler learns the pattern.
4. D and E in their own sessions: they share no files with A to C.

## Rules for each task

- Code for AnyPS5 goes to a branch of the fork, based on current upstream `main`, with a test, following
  AnyPS5's own CONTRIBUTING.md. Check for an open upstream pull request on the same functions first; if one
  exists, test it on the title and comment there instead of opening a second one.
- After a run that changes a number, update [status.md](status.md) in the same pull request that closes the
  task here.
- Never commit anything read from the title: no logs, frames, addresses, shader code or names from it.
