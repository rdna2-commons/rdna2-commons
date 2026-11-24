# Landscape: what exists and what we can use

Facts as of 2026-11-24 (licence as reported by GitHub; check the project's own files before taking code).
Status lines are what each project says about itself, not our measurement.

## How we use other projects

There are two ways, and the licence matters only for the first:

1. **Taking code into this repository.** Only under a licence compatible with GPL-3.0-or-later, with
   `Provenance:` naming the source. GPL-2.0-only and unlicensed code: never, not even rewritten.
2. **Running a project's tool as a separate program** (an adapter calls its translator binary on our test cases
   and reads the output). That combines no code, so it works for every project whatever its licence. This is
   how the compatibility table (phase 2) covers everyone.

## Compatibility layers and translators

| Project | Licence | Language | Approach | Useful to us |
|---|---|---|---|---|
| ubiquitarianism/leonida | GPL-3.0 | Python, C++ | Static recompilation; RDNA2 → SPIR-V; D3D12 → Vulkan | Code (compatible): hand-written semantic tests, GPU fixtures, hardware-oracle runner. Adapter: `tools/rdna2spirv.py` |
| Marvisak/VIctory | GPL-3.0 | Rust | Native execution plus reimplemented console APIs; RDNA2 → DXIL on first use | Code (compatible). Adapter: its shader recompiler |
| ivall/xcl | GPL-2.0 | Rust | Wine-style layer; reimplements kernel, graphics, storage, audio APIs | Facts and an adapter only, no code |
| omonkeyz/xbox-emulator | GPL-3.0 | Rust | Continuation of TomBox; RDNA2 translation, OS DLLs, per-function progress maps | Code (compatible); progress-map idea |
| drycheetah84/TomBox | none | Rust | Upstream of xbox-emulator | Facts only |
| californiaAlmonds/OpenScarlett | MIT | C++ | Clean-room layer; PE loader, graphics proxy, RDNA2 → SPIR-V/DXIL, codecs | Code (compatible). Adapter: its lifter |
| OpenCommunityEdition/OpenScarlett | AGPL-3.0 | C++ | Replacement DLLs on D3D12; RDNA2 → HLSL; runs under Wine | Adapter; code only by a maintainer decision (AGPL terms) |
| Freminet/ScarlettX | none | C++ | Clean-room high-level emulator | Facts only |
| sammwyy/xvalkyrie | GPL-3.0 | C++ | Layer for Xbox One and Series; compatibility table of 49 titles | Code (compatible); its compatibility-table format |
| brcly/TuxBox | Apache-2.0 | Rust | Native-first layer under Proton on Linux | Code (compatible); Linux path |
| rpatty-dev/PercyScarlett | GPL-2.0 (GitHub); README mentions custom terms | Rust | Shim DLLs; strict shader lifter to HLSL | Facts and an adapter only |
| ThatRecompDev/five-star-recomp | GPL-3.0 | C# | Own RDNA2 disassembler and HLSL translator, module loader | Code (compatible). Adapter |
| R0Y00/Xbox2Windows | MIT | Python, C++ | Static recompilation research; gfx1013 → DXIL | Code (compatible). Adapter |
| LooperSalty/AnyXboxX | GPL-3.0 | Python, C++, Rust | Unicorn-based and native loaders; **RDNA2 disassembler and reference interpreter** | Code (compatible): candidate for the reference interpreter (#19) |

## Format and reverse-engineering tools

Most of these read one title's archives, which is not our business. What is useful to us is the part that is
**generic to the console**: its texture compression (BCPack), its GPU tiling and swizzle modes (GFX10), its
audio codecs (XMA2, Opus in its containers) and video (Bink 2). We take only those decoders, only from compatible
licences, and test them on data we generate ourselves.

| Project | Licence | Generic console part | Use |
|---|---|---|---|
| paryzius/ttpf-viewer | MIT | Exact GFX10 tile and mip layouts, cube maps | Code: GFX10 detiling for `area:graphics` cases |
| Tim0219800/bcpack-decoder | MIT | Clean-room BCPack decoder, no fitted tables; spec in English and French | Code and spec |
| holdmysocks/SixNG | GPL-3.0 | BCPack decoding for all six BC formats (fitted tables) | Code (compatible), with its caveats |
| ifBars/rage-texture | GPL-3.0 | Texture library on top of the BCPack entropy layer | Code (compatible) |
| Ahmet-Dedeler/bcpack-rs | not stated to GitHub (README: MIT OR Apache-2.0) | BCPack entropy layer, BC1 | Check its licence file first |
| Librett0/vice-lens | MIT | Stream carving by zlib scan, Opus remux | Ideas; nothing title-specific |
| jaylikesbunda/rpf9-audio | MIT | Opus packet extraction and Ogg remux | Code for audio-format tests |
| woreksami/ttpf-studio | MIT | GPU unswizzling, BC1-BC7 | Code (compatible) |
| shrewbrewsh/OpenRPF9 | MIT | Plain BC1-BC7 decoding | Reference |
| zeozeozeo/rpf9 | Unlicense | Clean-room container library | Reference |
| rpatty-dev/PercyStar, Ahmet-Dedeler/Percy6Stars | not stated to GitHub | Bink 2, Opus, viewers | Facts only until a licence is clear |
| breadbbbb/rpf9-explorer, meetox80/6stars, offs/rpf9-extract | none | Viewers and extractors | Facts only |

**How their work becomes ours.** Never by copying their test data (it comes from a title). Instead: take the
decoder (compatible licence, credited), write a generator that produces our own inputs (random textures
compressed by an encoder we write, synthetic audio), and pin the decoder's output as a case. Where an encoder
does not exist, a `known` entry documents what was measured and by whom.

## How the leading projects present themselves

What we took from their READMEs for ours: a status table by subsystem with what is verified by what (xcl,
VIctory), milestone tables and generated progress badges (xbox-emulator), "what runs and what was compared"
(Xbox2Windows), a clear "no game data in git" notice up front (SixNG). What we do differently: our status is
generated from the task board, and every claim of "works" names the case and the independent reports behind it.

## What this means for the plan

- **Phase 1** does not start from zero: Leonida's hand-written semantic tests (now in `engine/tests`) and AnyXboxX's reference
  interpreter are both GPL-3.0 and can be brought in, credited, as the first shared cases and the first oracle.
- **Phase 2** adapters can cover every translator above, including GPL-2.0 and unlicensed ones, because the
  adapter only runs their program.
- The furthest projects (native execution plus API reimplementation) are bottlenecked on rendering
  correctness, which is exactly what the shared shader cases test.
