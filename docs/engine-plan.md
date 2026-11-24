# Engine plan: the hybrid recompiler

How the recompiler in `engine/` gets from "loads" to "plays", broken into one-pull-request tasks.
How to build and test it: [engine-dev.md](engine-dev.md).

## Priority

**Priority now: a stable, playable build as fast as possible.** Tasks on that path carry the label [`priority:playable`](https://github.com/scarlett-commons/scarlett-commons/issues?q=is%3Aissue+is%3Aopen+label%3Apriority%3Aplayable): comparing with and porting from VIctory where it is ahead (#137), function swap for patching crash sites (#55, #56, #58), shaders translated on first use (#75), texture tiling (#81), title memory uploads (#86), DirectStorage and BCPack (#110, #111), audio (#115-#117), input (#121, #122), the open GPU bug (#130), and the title-run loop (#124 done, #125). Take these first.

## Two tracks at once

**Track A, playable fast.** Run the title's own x86-64 code natively and replace the console underneath it. The
console CPU (Zen 2) is the same family as a PC's, so code runs as is once the loader maps it and the console's
system libraries are replaced (a few instructions Zen 2 has and many PCs lack are emulated on the spot). This is
how every project that reaches menus or the world got there, without recompiling anything. Where another project
is ahead and its licence allows (VIctory is GPL-3.0), we take its approach or its code, under our tests. Title-run
reports (docs/title-runs.md) decide what to fix next.

**Track B, recompile what matters, in parallel.** Static recompilation in layers, each useful on its own:

| Layer | What it gives | Tasks |
|---|---|---|
| 1. Native execution | The title runs on the engine | the system, GPU and storage tasks below |
| 2. Function swap | Replace any function with our own: patch crash sites by hand right away | #55 Zydis → #56 prologue hooks → #58 swap registry |
| 3. Semi-automatic translation | Decompile a chosen function to C, fix it up, verify, swap it in | #134, with #68 input recording and #69 the differential runner |
| 4. Automatic lifting | Lift functions in bulk behind one generic register-state wrapper, verify each, swap | #64 lifter choice → #65 wrapper → #67 replacement DLL |

What to recompile first (#135): crash and stop sites from title-run reports, the hottest functions from the
sampling profiler (#136), and the functions mods need. Track B never blocks track A.

Every task below names the ready-made open-source solution found for it (licences checked: code only from
GPL-3.0-compatible licences, everything else as reference or as a separate program) or says that none exists.
Where none existed the work was split further. The research is summarised in [landscape.md](landscape.md).

**Gaps no project fills yet:** differential testing of x86-64 code against itself; wave64 LDS and cross-lane code
on 32-wide GPUs; synthesising render-target metadata; GPU-to-CPU coherency for title memory; merged NGG stages;
detiling on the GPU; the audio DSP; swizzled DirectStorage destinations.

## Testing and the loop with real titles

| Task | What | Area | Needs |
|---|---|---|---|
| #124 | Local run with an automatic, scrubbed report | `infra` | #49 |
| #125 | Before/after comparison of local runs | `infra` | #124 |

Plus the engine CI (#46): translator, semantic, standard-library and runtime tests on every change, including the
hand-written GPU tests on a software Vulkan driver.

## CPU, hooking and recompilation

| Task | What | Area | Needs |
|---|---|---|---|
| #48 | Loader: read the load-config directory | `cpu` | — |
| #49 | Crash handler that prints module+offset and a stack | `diagnostics` | — |
| #50 | Local minidumps on crash, never uploaded | `diagnostics` | #49 |
| #51 | Function map file (RVA, size, name, source) | `diagnostics` | #49 |
| #52 | Emulate RDPID, RDPRU and SHA in the #UD handler | `cpu` | — |
| #53 | TSC and QPC rate shim | `cpu` | — |
| #54 | Physical page aliasing in xmem | `memory` | — |
| #55 | Vendor Zydis as the runtime's x86-64 decoder | `hooking` | — |
| #56 | Inline prologue hooks with trampolines | `hooking` | #55 |
| #57 | Redirect indirect calls (vtables, function tables) | `hooking` | #51, #56 |
| #58 | Runtime function-swap registry | `hooking` | #56 |
| #59 | Function database exporter (headless Ghidra) | `recomp` | #51 |
| #60 | Cross-check function discovery with angr | `recomp` | #59 |
| #61 | Name statically linked CRT and STL functions | `recomp` | #59 |
| #62 | Fiber and thread audit | `cpu` | — |
| #63 | Map the console's game cores onto host topology | `cpu` | #62 |
| #64 | Lifter choice: remill vs RetDec vs Ghidra on 20 functions | `recomp` | #59 |
| #65 | Layer 4: generic register-state wrapper for lifted functions | `recomp` | #64 |
| #66 | Calls out of lifted code | `recomp` | #58, #65 |
| #67 | Build lifted functions into a replacement DLL | `recomp` | #58, #65 |
| #68 | Record inputs of a hooked function (registers, pages read and written) | `difftest` | #58 |
| #69 | Differential runner: original vs replacement on recorded inputs | `difftest` | #58, #68 |
| #70 | Isolated replay of the original under Unicorn | `difftest` | #69 |
| #71 | Shadow mode during real runs | `difftest` | #69 |
| #72 | Per-function port progress census | `recomp` | #51, #69 |
| #73 | Import trace with arguments | `system` | — |
| #126 | Patch hot #UD sites into stubs | `cpu` | #55 |
| #134 | Layer 3: decompile one function to C, fix it up, verify it, swap it in | `recomp` | #59, #69 |
| #135 | Which functions to recompile first: crash sites, hot functions, mod points | `recomp` | #51 |
| #136 | Sampling profiler in the runtime (hot functions by module+offset) | `diagnostics` | — |

## GPU and graphics

| Task | What | Area | Needs |
|---|---|---|---|
| #74 | RDNA2 decoder in C++ for the runtime | `gpu` | — |
| #75 | Shader translation on first use, with a disk cache | `gpu` | — |
| #76 | A shared intermediate form inside the translator | `gpu` | — |
| #77 | SPIR-V to DXIL output path | `gpu` | #76 |
| #78 | Evaluate VIctory's shader recompiler as a second frontend | `gpu` | #77 |
| #79 | Native wave64 where the GPU supports it | `gpu` | #75 |
| #80 | Wave64 LDS and cross-lane code on wave32-only GPUs | `gpu` | #79 |
| #81 | All 14 GFX10 2D swizzle modes | `graphics` | — |
| #82 | Mip chains and mip tails | `graphics` | #81 |
| #83 | 3D thick modes, arrays and cubes | `graphics` | #82 |
| #84 | Detile on the GPU | `graphics` | #81 |
| #85 | GPU DEFLATE decoding for DirectStorage | `storage` | — |
| #86 | Upload only the title memory the CPU changed | `memory` | — |
| #87 | GPU-to-CPU coherency for title memory | `memory` | #86 |
| #88 | Track descriptors written at run time | `gpu` | #86 |
| #89 | Inventory and add console-only D3D12.X entry points | `graphics` | — |
| #90 | NGG merged stages (ES/GS, LS/HS) | `gpu` | #76 |
| #91 | Emulate image_bvh_intersect_ray | `gpu` | #76 |
| #92 | Console BVH to host acceleration structures | `graphics` | #91 |
| #93 | HTILE and DCC layout | `graphics` | #82 |
| #94 | Fill render-target metadata from host targets | `graphics` | #93 |
| #95 | Frame pacing with present_wait | `graphics` | — |
| #96 | HDR output and resolution scaling | `graphics` | #95 |
| #97 | Record and replay pipelines with Fossilize | `gpu` | #75 |
| #98 | Background pipeline compilation with stand-ins | `gpu` | #75, #97 |
| #127 | Native, parallel BCPack decoding | `storage` | #111 |

## System services, storage, audio, input

| Task | What | Area | Needs |
|---|---|---|---|
| #99 | Parse MicrosoftGame.Config properly | `system` | — |
| #100 | CI census of runtime classes and slots | `system` | — |
| #101 | XPackage: remaining slots | `system` | #99, #100 |
| #102 | Remaining small runtime classes | `system` | #100 |
| #103 | App-state (PLM) notifications | `system` | — |
| #104 | Close, suspend, save, exit | `system` | #103 |
| #105 | Own WerXboxGc and wer.dll, never upload | `system` | #50 |
| #106 | Winsock offline guard | `system` | — |
| #107 | Media Foundation resolver limited to local files | `system` | #106 |
| #108 | Kernel pass-through census and fixes | `system` | — |
| #109 | Linux: run under Wine/Proton in CI | `platforms` | #108 |
| #110 | DirectStorage worker pool and priorities | `storage` | — |
| #111 | BCPack stage in DirectStorage | `storage` | #110 |
| #112 | GDeflate requests | `storage` | #110 |
| #113 | Swizzled and physical-page destinations | `storage` | #110, #54 |
| #114 | Harden save storage | `storage` | #99 |
| #115 | Console XAudio2 shim | `audio` | — |
| #116 | XMA2 source voices | `audio` | #115 |
| #117 | Opus decoding in xapu | `audio` | — |
| #118 | AcpHal XMA contexts and WASAPI output | `audio` | #116 |
| #119 | SHAPE / chad DSP: measure, then mix | `audio` | #118 |
| #120 | Bink 2 at run time | `audio` | #115 |
| #121 | GameInput keyboard and mouse | `input` | — |
| #122 | XInput shim on SDL3 | `input` | — |
| #123 | Input binding file | `input` | #121 |
