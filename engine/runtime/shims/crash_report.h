// Fatal crash report: always on, one line on stderr and one JSON line in a file, for every crash that nothing
// handles.
//
//   [rt] crash: 0xc0000005 at a.dll+0x4a00 (read of 0x0); stack: a.dll+0x4a00 < a.dll+0x2210 < b.dll+0x10
//   {"kind":"crash","code":"0xc0000005","at":"a.dll+0x4a00","access":"read","address":"0x0","stack":[...]}
//
// The JSON line goes to LEONIDA_CRASH_FILE when it is set (appended, so a run's crashes accumulate), and to the
// --trace file as a "crash" event when the trace is open. tools/local_run.py reads it for title-run reports: only
// the code, the module+offset places and the access kind, never memory contents (docs/title-runs.md).
//
// It is an unhandled-exception filter, not a vectored handler: first-chance exceptions that the title catches
// itself are not crashes and are not reported (the opt-in --trace records those). It returns
// EXCEPTION_CONTINUE_SEARCH, so the process still ends as it would have, and calls a filter installed before it.
// A title that installs its own filter through the host's kernel32 replaces this one; that case is not covered yet.
// LEONIDA_NO_CRASH_REPORT=1 turns it off.
#pragma once

#include <windows.h>

#include <cstdio>
#include <string>

#include "startup_trace.h"

namespace rt::crash_report {

namespace detail {
inline LPTOP_LEVEL_EXCEPTION_FILTER previous = nullptr;
inline volatile LONG reporting = 0;
}  // namespace detail

// The report as one JSON object (no trailing newline), and the same facts as one readable line.
struct Report {
    std::string json;
    std::string line;
};

inline Report describe(const EXCEPTION_POINTERS& info) {
    using startup_trace::hex;
    using startup_trace::quote;
    using startup_trace::where;
    const EXCEPTION_RECORD& r = *info.ExceptionRecord;
    const std::string code = hex(r.ExceptionCode);
    const std::string at = where(reinterpret_cast<uint64_t>(r.ExceptionAddress));
    Report out;
    out.json = "{\"kind\":\"crash\",\"code\":" + quote(code) + ",\"at\":" + quote(at);
    out.line = "[rt] crash: " + code + " at " + at;
    if (r.ExceptionCode == EXCEPTION_ACCESS_VIOLATION && r.NumberParameters >= 2) {
        const auto op = r.ExceptionInformation[0];
        const char* access = op == 0 ? "read" : op == 1 ? "write" : "execute";
        const std::string address = hex(r.ExceptionInformation[1]);
        out.json += ",\"access\":" + quote(access) + ",\"address\":" + quote(address);
        out.line += std::string(" (") + access + " of " + address + ")";
    }
    if (info.ContextRecord) {
        const std::string stack = startup_trace::detail::stack_from(*info.ContextRecord);
        out.json += ",\"stack\":" + stack;
        // The readable line lists the frames of the JSON array, newest first.
        std::string frames;
        for (size_t i = 0; i < stack.size(); ++i) {
            if (stack[i] == '"') {
                const size_t end = stack.find('"', i + 1);
                if (end == std::string::npos) break;
                if (!frames.empty()) frames += " < ";
                frames += stack.substr(i + 1, end - i - 1);
                i = end;
            }
        }
        if (!frames.empty()) out.line += "; stack: " + frames;
    }
    out.json += "}";
    return out;
}

inline void write(const Report& report) {
    std::fprintf(stderr, "%s\n", report.line.c_str());
    std::fflush(stderr);
    wchar_t path[MAX_PATH];
    const DWORD n = GetEnvironmentVariableW(L"LEONIDA_CRASH_FILE", path, MAX_PATH);
    if (n > 0 && n < MAX_PATH) {
        FILE* f = nullptr;
        if (_wfopen_s(&f, path, L"ab") == 0 && f) {
            std::fprintf(f, "%s\n", report.json.c_str());
            std::fclose(f);
        }
    }
    const size_t brace = report.json.find(',');  // the trace adds its own "kind"
    if (brace != std::string::npos) startup_trace::event("crash", report.json.substr(brace + 1, report.json.size() - brace - 2));
}

namespace detail {
// Separate from filter(): __try cannot share a function with objects that need destructors (C2712).
__declspec(noinline) inline void report(EXCEPTION_POINTERS* info) {
    try {
        write(describe(*info));
    } catch (...) {
        // Out of memory while formatting: the process ends as it would have, without the line.
    }
}
}  // namespace detail

inline LONG WINAPI filter(EXCEPTION_POINTERS* info) {
    // One report per process: a crash inside the report must not recurse.
    if (info && info->ExceptionRecord && InterlockedExchange(&detail::reporting, 1) == 0) {
#ifdef _MSC_VER
        __try {
            detail::report(info);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
#else
        detail::report(info);
#endif
    }
    return detail::previous ? detail::previous(info) : EXCEPTION_CONTINUE_SEARCH;
}

// Installs the filter unless LEONIDA_NO_CRASH_REPORT is set. Returns whether it is installed.
inline bool install() {
    wchar_t v[4];
    if (GetEnvironmentVariableW(L"LEONIDA_NO_CRASH_REPORT", v, 4) > 0 && v[0] != L'0') return false;
    detail::previous = SetUnhandledExceptionFilter(&filter);
    return true;
}

}  // namespace rt::crash_report
