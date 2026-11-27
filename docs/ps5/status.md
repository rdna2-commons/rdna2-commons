# PS5 line: readiness

Updated after each run that changes a number. A percent is written only where it is measured; "unknown" means
the denominator is not known yet.

| Component | Readiness | How it is measured | Next task |
|---|---|---|---|
| Executable conversion (relinker) | 100% | the executable and its bundled modules convert with `--windows --to-intel`; the title loads | — |
| CPU code, native | 100% | no CPU fault in a 240 s run | — |
| CPU code, track B | 29,218 functions installed | of the 29,314 functions the difftest verified on the ELF, 29,218 are byte for byte unchanged in the relinked executable (`commons-ps5-trackb`) and run as track B; the 96 the relinker rewrote stay native. Two runs each way: same menu, frames bit-identical, no errors | widen the emitter |
| System functions | 95% complete, 100% exported | `import_audit.py`: 835 of 881 imports implemented, 45 partial (throw only for unknown inputs), 0 stubs, 1 absent; 0 not-implemented calls in a run | — |
| Memory | runs | the fixed no-overwrite reservation abort is fixed (upstream PR boykopovar/AnyPS5#27543; our fork has the same change) | — |
| GPU commands (AGC) | reaches the first menu | 30 presents per second in the menu; the image covers a quarter of the output | #219 |
| Shaders | unknown | 366 shaders not prepared when their pipeline is created (resources indexed from constant buffers); the total the world needs is not known until it loads | #221 |
| Data | 100% | the player's `app0` archives open | — |
| Overall stage | first menu | furthest stage reached: start, gpu, menu, world, playable | #220 |

## Runs

| Date | Build | Stage | Seconds | Presents/s | Unprepared shaders | Not implemented | First error |
|---|---|---|---|---|---|---|---|
| 2026-11-27 | fork main, relinker AMD-only fix | gpu | 7 | 0 | — | — | fixed mapping overlaps a reservation |
| 2026-11-27 | + no-overwrite reservation fix | menu | 240 (cap) | 30 | 366 | 0 | none |
| 2026-11-27 | + `APS5_PRELOAD`, native (2 runs) | menu, steady from 40 s and 50 s | 180 to 240 (cap) | 30 | 366 | 0 | none; one run stopped logging after 70 s |
| 2026-11-27 | + track B, 29,218 functions (2 runs) | menu, steady from 20 s both times | 180 to 240 (cap) | 30 | 366 | 0 | none |

Track B was installed through AnyPS5's `APS5_PRELOAD` (fork branch `feat-host-preload`) with
`commons_ps5_preload` from `recomp/preload`. The earlier steady menu with track B was seen in both pairs of runs;
two pairs and a 10 s sampling step are not enough to call it a speed-up yet. Two of three native runs stopped
logging after about 70 s while the process stayed alive; neither track B run did. It is not yet known whether
that is chance.
