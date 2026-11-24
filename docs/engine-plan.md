# Engine plan: the hybrid recompiler

**English** · how the recompiler in `engine/` gets from "loads" to "plays", broken into one-pull-request tasks.

## The approach

1. **Run the title's own x86-64 code natively.** The console CPU (Zen 2) is the same family as a PC's, so code
   runs as is once the loader maps it and the console's system libraries are replaced. A few instructions Zen 2
   has and many PCs lack are emulated on the spot.
2. **Replace the console underneath it:** system services (kernel, runtime classes, storage, audio, input) and the
   GPU (shaders translated to SPIR-V or DXIL, the console D3D12 on Vulkan or D3D12).
3. **Recompile function by function.** Hook a function, lift it to C or LLVM with the native calling convention,
   build it into a replacement DLL, and swap it in only after a differential test shows it does exactly what the
   original does on recorded inputs. Over time more and more of the title runs as our own source.

Every task below names the ready-made open-source solution found for it (licences checked: code only from
GPL-3.0-compatible licences, everything else as reference or as a separate program) or says that none exists.
Where none existed the work was split further. The research is summarised in [landscape.md](landscape.md).

**Critical path for recompilation:** Zydis → prologue hooks → swap registry → lifter choice → Win64-ABI lifting →
replacement DLL → input capture → differential runner.

**Gaps no project fills yet:** lifting that keeps the native calling convention; differential testing of x86-64
code against itself; wave64 LDS and cross-lane code on 32-wide GPUs; synthesising render-target metadata;
GPU-to-CPU coherency for title memory; merged NGG stages; detiling on the GPU; the audio DSP; swizzled
DirectStorage destinations.

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
| #64 | Lifter choice: remill vs RetDec vs Ghidra | `recomp` | #59 |
| #65 | Lifting pipeline keeping the native Win64 ABI | `recomp` | #64 |
| #66 | Calls out of lifted code | `recomp` | #58, #65 |
| #67 | Build lifted functions into a replacement DLL | `recomp` | #58, #65 |
| #68 | Capture inputs of a hooked function | `difftest` | #58 |
| #69 | Native differential runner: original vs lifted | `difftest` | #67, #68 |
| #70 | Isolated replay of the original under Unicorn | `difftest` | #69 |
| #71 | Shadow mode during real runs | `difftest` | #69 |
| #72 | Per-function port progress census | `recomp` | #51, #69 |
| #73 | Import trace with arguments | `system` | — |
| #126 | Patch hot #UD sites into stubs | `cpu` | #55 |

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
