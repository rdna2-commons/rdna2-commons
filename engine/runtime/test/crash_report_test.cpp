// Tests for the fatal crash report (shims/crash_report.h).
//
// 1. describe() on a captured context with a synthetic access-violation record: code, module+offset place, access
//    kind and a stack that starts in this executable.
// 2. End to end: the test starts itself as a child with --crash-child; the child installs the report and reads
//    address 0. The parent checks the child's exit code, its stderr line and the JSON line in LEONIDA_CRASH_FILE.
// No game data and no GPU are involved.
#include <windows.h>

#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>

#include "../shims/crash_report.h"

namespace {

int g_checks = 0;
int g_failed = 0;

void check(bool ok, const std::string& what) {
    ++g_checks;
    std::printf("%s %s\n", ok ? "ok   " : "FAIL ", what.c_str());
    if (!ok) ++g_failed;
}

std::string exe_name() {
    wchar_t path[MAX_PATH];
    GetModuleFileNameW(nullptr, path, MAX_PATH);
    return std::filesystem::path(path).filename().string();
}

__declspec(noinline) int crash_now() {
    volatile int* p = nullptr;
    return *p;
}

void test_describe() {
    CONTEXT ctx{};
    RtlCaptureContext(&ctx);
    EXCEPTION_RECORD rec{};
    rec.ExceptionCode = EXCEPTION_ACCESS_VIOLATION;
    rec.ExceptionAddress = reinterpret_cast<void*>(ctx.Rip);
    rec.NumberParameters = 2;
    rec.ExceptionInformation[0] = 1;  // write
    rec.ExceptionInformation[1] = 0x10;
    EXCEPTION_POINTERS info{&rec, &ctx};
    const auto r = rt::crash_report::describe(info);
    const std::string me = "host:" + exe_name();  // a host module, not a mapped image: module_offset marks it
    check(r.json.rfind("{\"kind\":\"crash\",\"code\":\"0xc0000005\",\"at\":\"" + me + "+0x", 0) == 0,
          "json starts with the code and a module+offset place in this executable");
    check(r.json.find("\"access\":\"write\",\"address\":\"0x10\"") != std::string::npos, "json has the access");
    check(r.json.find("\"stack\":[\"" + me + "+0x") != std::string::npos, "json stack starts in this executable");
    check(r.json.back() == '}', "json is closed");
    check(r.line.rfind("[rt] crash: 0xc0000005 at " + me + "+0x", 0) == 0, "line names the code and place");
    check(r.line.find("(write of 0x10); stack: " + me + "+0x") != std::string::npos, "line has access and stack");

    EXCEPTION_RECORD plain{};
    plain.ExceptionCode = 0xC000001D;  // illegal instruction: no access fields
    plain.ExceptionAddress = reinterpret_cast<void*>(ctx.Rip);
    EXCEPTION_POINTERS no_ctx{&plain, nullptr};
    const auto p = rt::crash_report::describe(no_ctx);
    check(p.json.find("access") == std::string::npos && p.json.find("stack") == std::string::npos &&
              p.json.back() == '}',
          "a record without access info or context gives code and place only");
}

void test_end_to_end() {
    const auto dir = std::filesystem::temp_directory_path() / ("crash_report_test_" + std::to_string(GetCurrentProcessId()));
    std::filesystem::create_directories(dir);
    const auto crash_file = dir / "crash.jsonl";
    const auto err_file = dir / "stderr.txt";
    std::filesystem::remove(crash_file);
    SetEnvironmentVariableW(L"LEONIDA_CRASH_FILE", crash_file.c_str());
    SetEnvironmentVariableW(L"LEONIDA_NO_CRASH_REPORT", nullptr);

    SECURITY_ATTRIBUTES sa{sizeof sa, nullptr, TRUE};
    HANDLE err = CreateFileW(err_file.c_str(), GENERIC_WRITE, FILE_SHARE_READ, &sa, CREATE_ALWAYS, 0, nullptr);
    wchar_t self[MAX_PATH];
    GetModuleFileNameW(nullptr, self, MAX_PATH);
    std::wstring cmd = L"\"" + std::wstring(self) + L"\" --crash-child";
    STARTUPINFOW si{sizeof si};
    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdError = err;
    si.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
    si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    PROCESS_INFORMATION pi{};
    // No Windows Error Reporting dialog for the child's crash.
    const UINT old_mode = SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
    const BOOL started = CreateProcessW(nullptr, cmd.data(), nullptr, nullptr, TRUE, 0, nullptr, nullptr, &si, &pi);
    SetErrorMode(old_mode);
    check(started != FALSE, "the crashing child starts");
    if (!started) {
        CloseHandle(err);
        return;
    }
    WaitForSingleObject(pi.hProcess, 60000);
    DWORD code = 0;
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    CloseHandle(err);
    check(code == EXCEPTION_ACCESS_VIOLATION, "the child still ends with the access violation");

    std::ifstream e(err_file);
    std::stringstream es;
    es << e.rdbuf();
    const std::string me = "host:" + exe_name();  // a host module, not a mapped image: module_offset marks it
    check(es.str().find("[rt] crash: 0xc0000005 at " + me + "+0x") != std::string::npos,
          "stderr has the crash line with module+offset");
    std::ifstream c(crash_file);
    std::string line;
    std::getline(c, line);
    check(line.rfind("{\"kind\":\"crash\",\"code\":\"0xc0000005\",\"at\":\"" + me + "+0x", 0) == 0 &&
              line.find("\"access\":\"read\",\"address\":\"0x0\"") != std::string::npos,
          "the crash file has one JSON line with code, place and access");
    std::error_code ec;
    std::filesystem::remove_all(dir, ec);
}

}  // namespace

int main(int argc, char** argv) {
    if (argc > 1 && std::string(argv[1]) == "--crash-child") {
        SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
        rt::crash_report::install();
        return crash_now();
    }
    test_describe();
    test_end_to_end();
    std::printf("%d checks, %d failed\n", g_checks, g_failed);
    return g_failed ? 1 : 0;
}
