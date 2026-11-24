# Roadmap

**English** · [Русский](docs/i18n/ru/ROADMAP.md) · [简体中文](docs/i18n/zh-CN/ROADMAP.md) · [Español](docs/i18n/es/ROADMAP.md)

This is the plan everyone works from. Each item becomes task issues labelled with its area; the bot hands them
out in dependency order. Progress is tracked automatically in [the progress page](https://github.com/scarlett-commons/scarlett-commons/blob/status/PROGRESS.md).

**Goal:** make the hard, shared parts of running Xbox Series X|S software on PC correct and verified once, for
every compatibility project, instead of fifteen times. We build knowledge, tests and checked components;
other projects use them.

**Never:** game data, keys, decryption, links to leaks, code from incompatible licences (see CONTRIBUTING.md).

## Priority

First a stable, playable build, as fast as possible: tasks labelled `priority:playable` (docs/engine-plan.md, "Priority"). Everything else supports it or follows it.

## The engine track (alongside every phase)

The recompiler in `engine/`, imported from the Leonida continuation with its history and kept in step with it
by a daily sync (docs/engine-sync.md). Work on it follows the same rules as everything else, and its progress on
real titles is reported by build hash (docs/title-runs.md): loads, imports resolved, device created, first frame,
menu, in world, playable. The phases below make it correct; the engine track makes it run. Its tasks, with the ready-made tools for each: [docs/engine-plan.md](docs/engine-plan.md).

## Phase 0: Foundation (done)

The machinery that lets people and agents join without anyone onboarding them.

- Bot: rule gate, claims, deadlines, fix tasks, `/split`, blind reviewers, automerge, dry-run mode.
- Docs: this roadmap, architecture, getting started, AGENTS.md, translations.
- Progress page generated from the task board.
- Mirror to a second host; restore procedure.
- Automatic maintainer proposals.

**Done when:** a new agent can read AGENTS.md, take a task, and get a pull request merged with no human but
its reviewers involved.

## Phase 1: Shared knowledge

A test library that defines correct behaviour, checked on real hardware.

| Area | What | Label |
|---|---|---|
| Shaders | Format-neutral RDNA2 cases: VALU f16/f32/f64 (rounding, denormals, FMA), SALU, LDS, wave64 and cross-lane, image and sampler, buffer addressing, interpolation and exports | `area:shaders` |
| Hardware oracle | Expected outputs confirmed on real AMD RDNA2 and the common PC GPUs, by consensus (docs/results.md) | `area:results` |
| System APIs | Behaviour specs, from public documentation and tests on homebrew or Microsoft samples: memory, threads, files, timing | `area:system` |
| Graphics API | Console D3D12 extensions vs desktop D3D12/Vulkan: what differs and how each project maps it | `area:graphics` |
| Audio, storage, input | XAudio2, DirectStorage, GameInput behaviour specs and tests | `area:audio`, `area:storage`, `area:input` |

**Done when:** every case has an expected result confirmed by two independent reports.

## Phase 2: Adapters and the compatibility table

- A runner per translator: SPIR-V on Vulkan, DXIL on D3D12, HLSL. Each project's translator plugs in by command.
- A public table: which project passes which cases, regenerated on every run.
- Linux and macOS runs (Vulkan, MoltenVK). Label `area:platforms`.

**Done when:** at least three external translators run in the table.

## Phase 3: Upstream fixes

Every failure the table shows in another project becomes a small, tested fix offered to that project.
Outreach goes through an `outreach` issue first; a maintainer decides what is sent, once, in that project's own
tracker.

## Phase 4: Shared components

Where several projects need the same piece and none has a good one under a compatible licence, build it here as
a library with its own tests (for example a reference RDNA2 interpreter used as the oracle when hardware is not
available).

## Directions in parallel

All phases after 0 run at once; tasks only wait for their own dependencies. Labels: `area:shaders`,
`area:results`, `area:system`, `area:graphics`, `area:audio`, `area:storage`, `area:input`, `area:platforms`,
`area:infra`, `area:docs`, `area:i18n`; the engine track adds `area:cpu`, `area:hooking`, `area:recomp`,
`area:difftest`, `area:diagnostics`, `area:memory`, `area:gpu` (docs/engine-plan.md).
