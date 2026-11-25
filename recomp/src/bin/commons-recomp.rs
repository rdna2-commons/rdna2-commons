//! `commons-recomp <exe> --work DIR [--limit N] [--rounds N]`: track B for this build, on this machine.
//! Selects checkable functions, generates and builds the library in DIR, tests every function against the native
//! one, and writes DIR/<build>.toml for `cargo commons run` (with COMMONS_RECOMP_DIR=DIR). Nothing is written into
//! the repository.

use std::path::PathBuf;
use std::process::ExitCode;

fn arg(args: &[String], name: &str) -> Option<String> {
    args.iter().position(|a| a == name).and_then(|i| args.get(i + 1)).cloned()
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let (Some(exe), Some(work)) = (args.first().filter(|a| !a.starts_with("--")), arg(&args, "--work")) else {
        eprintln!("usage: commons-recomp <exe> --work DIR [--limit N] [--rounds N]");
        return ExitCode::from(2);
    };
    let limit = arg(&args, "--limit").and_then(|v| v.parse().ok()).unwrap_or(5000usize);
    let rounds = arg(&args, "--rounds").and_then(|v| v.parse().ok()).unwrap_or(300usize);
    let work = PathBuf::from(work);
    let data = match std::fs::read(exe) {
        Ok(d) => d,
        Err(e) => {
            eprintln!("error: {exe}: {e}");
            return ExitCode::from(1);
        }
    };
    let build = blake3::hash(&data).to_hex().to_string();
    let image = match commons_recomp::census::Image::parse(&data) {
        Ok(i) => i,
        Err(e) => {
            eprintln!("error: {exe}: {e}");
            return ExitCode::from(1);
        }
    };
    println!("build          {build}");
    let callees = commons_recomp::pipeline::CalleeCheck::new(&image);
    let rule = |code: &[u8], rva: u32| {
        commons_recomp::pipeline::checkable_with_calls(code, rva, &|t| callees.safe(t, 4))
    };
    let cands = commons_recomp::pipeline::select(&image, limit, &rule);
    println!("selected       {} functions (memory through registers and globals; loops under a watchdog; calls to safe callees)", cands.len());
    let lib_rs = match commons_recomp::pipeline::generate(&cands) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("error: generating: {e}");
            return ExitCode::from(1);
        }
    };
    println!("building       {}", work.join("gen").display());
    let dll = match commons_recomp::pipeline::build(&work, &lib_rs) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("error: {e}");
            return ExitCode::from(1);
        }
    };
    let lib = match commons_recomp::pipeline::load(&dll) {
        Ok(l) => l,
        Err(e) => {
            eprintln!("error: {e}");
            return ExitCode::from(1);
        }
    };
    let base = match commons_recomp::pipeline::map_image(&image) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("error: {e}");
            return ExitCode::from(1);
        }
    };
    println!("mapped         the image at {base:#x} for the differential test");
    let report = commons_recomp::pipeline::difftest_sandboxed(&cands, &lib, base, image.size_of_image as usize, rounds);
    let passed = report.passed;
    for rva in report.differed_rvas.iter().take(20) {
        println!("differed       {rva:#x}");
    }
    println!(
        "difftest       {} equal to the native function, {} differed, {} inconclusive (of {}; {rounds} inputs each)",
        passed.len(), report.differed, report.inconclusive, cands.len()
    );
    let manifest = commons_recomp::pipeline::manifest(&build, &dll, &cands, &passed);
    let path = work.join(format!("{build}.toml"));
    if let Err(e) = std::fs::write(&path, manifest) {
        eprintln!("error: {}: {e}", path.display());
        return ExitCode::from(1);
    }
    println!("manifest       {}", path.display());
    println!("run            set COMMONS_RECOMP_DIR={} and cargo commons run <exe> --execute", work.display());
    // The process holds the mapped image, the loaded library and the watchdog thread; tearing those down at exit has
    // crashed after the work was done. Everything is written: end here.
    use std::io::Write as _;
    let _ = std::io::stdout().flush();
    unsafe extern "system" {
        fn GetCurrentProcess() -> isize;
        fn TerminateProcess(process: isize, code: u32) -> i32;
    }
    unsafe { TerminateProcess(GetCurrentProcess(), 0) };
    ExitCode::SUCCESS
}
