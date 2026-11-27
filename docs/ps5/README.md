# The PS5 line

The same game ships for Xbox Series and for PS5, and both machines run x86-64 on an RDNA2 GPU. The PS5 line
takes the player's own decrypted copy (`eboot.bin`, the modules beside it and the `app0` data) and runs it on
a PC.

Nothing of a title goes into this repository: no code, no data, no shaders, no NIDs read from a title, no logs
quoting them. Tools read the player's copy on the player's machine and print counts.

| Page | What is in it |
|---|---|
| [status.md](status.md) | Readiness per component, how each number is measured, the latest runs |
| [plan.md](plan.md) | The tasks, their order, which can run in parallel, where each one's code lands |
| [running.md](running.md) | Build, convert, run and score the title on your machine |
| [../workbench.md](../workbench.md) | How local work is saved automatically and reviewed before it is published |

## How it runs

| Layer | What does it | Where its code lives |
|---|---|---|
| Executable | AnyPS5's relinker turns the PS5 ELF into a Windows (or Linux) executable; `--to-intel` rewrites AMD-only instructions | AnyPS5 fork |
| CPU code | native x86-64; track B translations, verified function by function, can be installed over it | track B here (`recomp/`) |
| System services | AnyPS5's own libraries (`libs/*.prx`), keyed by library and NID | AnyPS5 fork |
| GPU commands | AnyPS5's AGC driver: the PS5's command buffers to Vulkan | AnyPS5 fork |
| Shaders | AnyPS5's recompiler: RDNA2 ISA to SPIR-V at run time | AnyPS5 fork |
| Files | the player's `app0`, read in place | the player's machine |
| Scouting and measuring | `commons-ps5-scout`, readiness scoring | here (`recomp/`, `tools/`) |

## Licences

AnyPS5 is GPL-2.0-only and cannot be combined with this repository's GPL-3.0. Its code is never copied here.
We work in a fork of it (`rdna2-commons/anyps5`), send fixes upstream to `boykopovar/AnyPS5`, and run it as a
separate program. This repository holds what is ours: the plan, the measurements, track B and our tools.

## Tools here

- `commons-ps5-scout <eboot.elf|.prx>`: the modules and libraries the executable imports, how many symbols
  from each, its functions, and how much of their code track B covers. A signed (encrypted) executable is
  refused with the reason. Decryption happens on the console the copy came from, never here.
- `commons-census`, `commons-recomp`: take an ELF as well as a PE.
