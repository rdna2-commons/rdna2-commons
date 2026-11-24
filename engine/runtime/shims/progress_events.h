// Run milestones in the --trace file, for title-run reports (tools/local_run.py, docs/title-runs.md):
//   {"kind":"device_created"}                      the title's D3D12 device proxy exists
//   {"kind":"first_frame"}                         the first PresentX
//   {"kind":"frames","count":N,"fps":F}            every 5 s while frames are presented
// Nothing is recorded without --trace; each call is then one relaxed load.
#pragma once

#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <mutex>

#include "startup_trace.h"

namespace rt::progress_events {

inline void device_created() {
    static std::atomic<bool> once{false};
    if (startup_trace::enabled() && !once.exchange(true)) startup_trace::event("device_created");
}

inline void frame_presented() {
    if (!startup_trace::enabled()) return;
    using clock = std::chrono::steady_clock;
    static std::mutex m;
    static uint64_t total = 0, window = 0;
    static clock::time_point since;
    const std::lock_guard lock(m);
    const auto now = clock::now();
    if (total++ == 0) {
        since = now;
        startup_trace::event("first_frame");
        return;
    }
    ++window;
    const double seconds = std::chrono::duration<double>(now - since).count();
    if (seconds >= 5.0) {
        char f[64];
        std::snprintf(f, sizeof f, "\"count\":%llu,\"fps\":%.2f", static_cast<unsigned long long>(total),
                      window / seconds);
        startup_trace::event("frames", f);
        window = 0;
        since = now;
    }
}

}  // namespace rt::progress_events
