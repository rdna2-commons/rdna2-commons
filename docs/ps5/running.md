# PS5 line: build, run, score

Paths below are examples; set your own.

## 1. Build the AnyPS5 fork

```powershell
git clone --recurse-submodules https://github.com/scarlett-commons/anyps5 C:\dev\ext\anyps5
```

Windows needs MinGW-w64 GCC (WinLibs UCRT, the version AnyPS5's CI uses) and the system CMake (the CMake
shipped with WinLibs fails to download FFmpeg over TLS).

```powershell
cmake -S C:\dev\ext\anyps5 -B C:\dev\ext\ab -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ -DBUILD_TESTING=OFF
cmake --build C:\dev\ext\ab --target libs relinker --parallel
```

Copy `libgcc_s_seh-1.dll`, `libstdc++-6.dll` and `libwinpthread-1.dll` from the compiler into
`C:\dev\ext\ab\core\libs\libs`.

## 2. Convert the executable

The input is a plain ELF and its modules in `sce_module/` beside it, from your own console.

```powershell
relinker.exe --windows --to-intel --registry <dir>\eboot.elf <run>\eboot.exe
```

## 3. Lay out the run folder

```
<run>\eboot.exe
<run>\libs\            AnyPS5's built libraries only (core\libs\libs), plus the three compiler DLLs
<run>\app0\            your app0 files (hard links are enough), without eboot.bin
<run>\app0\sce_module\ the converted *.guest.prx the relinker wrote
```

## 4. Check the imports

```powershell
python tools\import_audit.py --libs C:\dev\ext\ab\core\libs\libs --modules <run>\app0\sce_module <run>\*.registry.json
```

## 5. Run

```powershell
$env:APS5_PROFILE_DRAW = '1'; $env:APS5_DUMP_FRAMES = '20'; $env:APS5_DUMP_FRAMES_EVERY = '600'
cmd /c '.\eboot.exe > run.log 2>&1'
```

`APS5_TRACE_MEMORY=1` logs every reservation and mapping. `APS5_NO_PAD_INPUT=1` ignores the keyboard.

## 6. Score

Score every run and copy the row into [status.md](status.md) (#223 automates this): the furthest stage, seconds
alive, presents per second, unprepared shaders, not-implemented calls and the first error.
