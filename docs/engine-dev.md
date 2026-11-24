# Working on the engine

How to build and test `engine/` locally, and what an engine pull request needs. The plan the work follows is in
[engine-plan.md](engine-plan.md).

## What is where

| Path | What it is | Tests |
|---|---|---|
| `engine/tools/rdna2spirv.py` | RDNA2 → SPIR-V shader translator (Python) | `engine/tests/` (pytest and stdlib), `engine/tests/semantic/` |
| `engine/runtime/src/` | Loader (`pe_loader`), TLS host, CPU emulation, entry point `main.cpp` | `engine/runtime/test/` (CTest) |
| `engine/runtime/shims/` | Console API replacements: kernel, runtime classes, D3D12.X, D3D12 → Vulkan, storage, input, audio, crash report | `engine/runtime/test/` |
| `engine/runtime/test/shaders/` | Hand-written RDNA2 GPU fixtures | `engine/scripts/run_gpu_tests.py` |
| `engine/scripts/` | Test runners and build helpers | — |
| `engine/third_party/` | Vendored code with compatible licences (see engine/README.md) | — |

## Toolchain

| Need | For | Notes |
|---|---|---|
| Python 3.10+ (3.12 used in CI) | translator, tools, tests | `pip install -r engine/tests/requirements.txt` for the pytest files |
| `llvm-mc` from LLVM 19+ with the AMDGPU target | translator tests that assemble RDNA2 | set `LLVM_MC` to its path |
| SPIRV-Tools (`spirv-as`, `spirv-val`) | translator and semantic tests | the Vulkan SDK ships them |
| AMD RDNA2 ISA XML (`amdgpu_isa_rdna2.xml`, MIT, from AMD's GPUOpen machine-readable ISA) | decoder tables in some tests | set `LEONIDA_RDNA2_ISA_XML` |
| Windows: Visual Studio 2022 Build Tools (C++), CMake, Ninja | runtime | Linux and macOS build the cross-platform parts; see engine/runtime/README.md |
| Vulkan SDK 1.4 | Vulkan device, GPU tests | set `VULKAN_SDK` |

## Build and test

```
# translator (from engine/)
cd engine
python -I -m pytest tests -q                       # the pytest files
python -I scripts/run_semantic_tests.py tests/semantic -v

# runtime (from engine/, in a Visual Studio x64 developer prompt on Windows)
cmake -S runtime -B runtime/build -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build runtime/build
ctest --test-dir runtime/build --output-on-failure

# hand-written GPU tests on your GPU (or a software Vulkan driver such as llvmpipe)
python -I scripts/run_gpu_tests.py --build runtime/build --llvm-mc "$LLVM_MC" --work <tmp folder>
```

Build output (`engine/runtime/build/`) is ignored by git; never commit it (the bot closes pull requests with
binaries).

## What CI runs

| Workflow | Jobs | On |
|---|---|---|
| `engine-translator` | translator tests (pytest + llvm-mc), semantic tests, standard-library tests | changes under `engine/` |
| `engine-runtime` | Windows build + CTest; Linux build, CTest and GPU tests on llvmpipe; macOS build, CTest and GPU tests on MoltenVK | changes under `engine/runtime`, `engine/scripts`, `engine/third_party` and the translator files it uses |

Known red, tracked as tasks: the TFE image-load GPU fixtures on llvmpipe (#130) and a timer-granularity flake in
`crt_timed_wait` on hosted Windows (#132). Engine stdlib tests that need parts not imported here (the title
build pipeline and its docs) are listed in `.github/engine-known-gaps.txt`; only a failure outside that list fails
the job, and a listed test that starts passing is reported.

## What an engine pull request needs

- The same rules as any pull request (CONTRIBUTING.md): a claimed task, `Provenance:`, signed-off commits.
- A test next to the change: `engine/tests/` for the translator and tools, `engine/runtime/test/` (registered in
  `engine/runtime/CMakeLists.txt` with `add_test`) for the runtime. The bot asks for one when engine code changes
  without a test.
- Green engine CI for the jobs your change touches, or a note explaining a known-red job.
- Nothing from any title in tests: fixtures are written by hand; results on a real title go through
  [title-runs.md](title-runs.md).

## Trying your change on a title

`tools/local_run.py` builds your own copy with this repository's engine and writes a scrubbed report
([title-runs.md](title-runs.md)). The runtime prints `[rt] crash: <code> at <module>+0x<offset>` when it crashes
and writes the same as JSON to `LEONIDA_CRASH_FILE`.
