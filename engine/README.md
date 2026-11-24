# Engine

The static recompiler and runtime: an RDNA2 → SPIR-V shader translator (`tools/rdna2spirv.py`), a PE loader and
console API shims with a D3D12 → Vulkan layer (`runtime/`), and their tests (`tests/`, `runtime/test/`).

## Where it comes from

Imported from [ubiquitarianism/leonida](https://github.com/ubiquitarianism/leonida) (GPL-3.0-or-later), the continuation of
the Leonida project, **with its full history and authorship**: `git log -- engine/` shows every original commit
and author. Issue and pull request numbers in that history (`#1234`) refer to the original repositories, not to
this one.

Imported: `tools/`, `runtime/`, `tests/`, `scripts/`, and the compatibly licensed `third_party/` code
(bcpack-rs: MIT or Apache-2.0; xtaskqueue: MIT, from microsoft/libHttpClient; xma: only the notice and licence text of an external Cargo dependency). Not imported: the title-specific build pipeline
(`make_game.py`, `game/`), mods, the viewer, and the `rpf9-explorer` submodule, which has no licence. Every version
of every imported file, across the whole history, passed this repository's game-data guard before it was
published here.

## Titles

The engine knows nothing it ships about any title's content: it runs a title's own code from the user's own copy
on disk. It was developed against GTA VI (Xbox Series build 1.0.2.1); the profile that builds a PC copy of that
title from your own files (file list and hashes, build stages, mods) is maintained in the Leonida project, not
here. Results on a title are reported by build hash (see [docs/title-runs.md](../docs/title-runs.md)).

## Building and testing

See [docs/engine-dev.md](../docs/engine-dev.md): toolchain, local commands, what CI runs (engine-translator and engine-runtime on every change under `engine/`), the known-gaps list, and what an engine pull request needs.

## Names from upstream

`gta6rt` (the runtime executable), `LEONIDA_*` environment variables and references to `docs/...` pages inside `engine/` come from upstream and are kept so the daily sync stays clean. The upstream docs pages were not imported; read them in the Leonida continuation.
