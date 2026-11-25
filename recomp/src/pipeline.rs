//! `commons-recomp`: track B for one build, made on the player's machine from their own copy.
//!
//! 1. Select: functions the emitter covers that the differential test can check with generated inputs alone, i.e.
//!    leaves (no calls) without loops, whose memory accesses are their own stack only, at least 16 bytes long, with no
//!    branch into the 14 bytes the installed jump overwrites.
//! 2. Generate: a Rust crate in `<work>/gen` (the emitter's prelude, each function, its entry stub, and two exports:
//!    `commons_init(base)` and `commons_function(i, &rva, &entry)`), never committed.
//! 3. Build it into `<work>/target/release/commons_track_b.dll`.
//! 4. Differential test: each function's native bytes run in this process and its translation runs through its entry
//!    stub, on the same random registers, ymm registers and stack; only identical results pass.
//! 5. Write `<work>/<build>.toml`: the library and the passing functions as `verified`.
#![cfg(all(windows, target_arch = "x86_64"))]

use std::fmt::Write as _;
use std::path::{Path, PathBuf};

use commons_recomp_emit::{decode, emit_entry, emit_function, supported, PRELUDE};
use iced_x86::{FlowControl, OpKind, Register};

use crate::census::Image;
use crate::harness::{run_native, HostCtx, Rng, LOCK};

pub struct Candidate {
    pub rva: u32,
    pub code: Vec<u8>,
}

/// Whether a function can be checked with generated inputs alone (see the module comment): memory only on its own
/// stack.
pub fn checkable(code: &[u8], rva: u32) -> bool {
    checkable_with(code, rva, false)
}

/// The rule the sandboxed differential test uses: memory through any register is fine (registers point into a
/// sandbox), reads of the image's globals are fine (the image is mapped at its base); writes to globals and FS/GS
/// memory are not.
pub fn checkable_sandboxed(code: &[u8], rva: u32) -> bool {
    checkable_with(code, rva, true)
}

fn checkable_with(code: &[u8], rva: u32, sandboxed: bool) -> bool {
    checkable_calling(code, rva, sandboxed, &|_| false)
}

/// The sandboxed rule, with direct calls to callees `safe_callee` accepts (they run natively in the test).
pub fn checkable_with_calls(code: &[u8], rva: u32, safe_callee: &dyn Fn(u64) -> bool) -> bool {
    checkable_calling(code, rva, true, safe_callee)
}

fn checkable_calling(code: &[u8], rva: u32, sandboxed: bool, safe_callee: &dyn Fn(u64) -> bool) -> bool {
    if code.len() < 16 {
        return false;
    }
    let insns = decode(code, u64::from(rva));
    if insns.is_empty() {
        return false;
    }
    // A .pdata entry can be a fragment of a larger function (code split off with chained unwind info) that ends
    // without returning; only a function whose last instruction returns can be run and compared on its own.
    if insns.last().map(|i| i.flow_control()) != Some(FlowControl::Return) {
        return false;
    }
    // An epilogue fragment (entered by a jump with the stack inside another function's frame) pops more than it
    // pushed. A function that stands alone has the stack where it found it at its ret, with rsp changed only by
    // push, pop and add/sub of a constant.
    let mut depth: i64 = 0;
    for i in &insns {
        use iced_x86::Mnemonic::*;
        let writes_rsp = i.op_count() > 0 && i.op_kind(0) == OpKind::Register && i.op_register(0) == Register::RSP;
        match i.mnemonic() {
            Push => depth -= 8,
            Pop if !writes_rsp => depth += 8,
            Sub if writes_rsp && i.op_kind(1) != OpKind::Register && i.op_kind(1) != OpKind::Memory => depth -= i.immediate(1) as i64,
            Add if writes_rsp && i.op_kind(1) != OpKind::Register && i.op_kind(1) != OpKind::Memory => depth += i.immediate(1) as i64,
            Ret => {
                if depth != 0 {
                    return false;
                }
            }
            _ if writes_rsp => return false,
            _ => {}
        }
        if depth > 0 {
            return false; // above the return address: not its own frame
        }
    }
    let start = u64::from(rva);
    for i in &insns {
        if i.is_invalid() || !supported(i) {
            return false;
        }
        match i.flow_control() {
            FlowControl::IndirectCall => return false,
            FlowControl::Call => {
                if !(i.op0_kind() == OpKind::NearBranch64 && safe_callee(i.near_branch_target())) {
                    return false;
                }
            }
            _ => {}
        }
        if matches!(i.op0_kind(), OpKind::NearBranch64) && i.flow_control() != FlowControl::Call {
            let t = i.near_branch_target();
            // The sandboxed test bounds each run with a watchdog, so it can take loops; the other cannot.
            let backward = t <= i.ip() && !sandboxed;
            if backward || (t >= start && t < start + crate::JUMP_LEN as u64) || t >= start + code.len() as u64 {
                return false; // a loop, a branch into the bytes the jump overwrites, or one out of the function
            }
        }
        let accesses_memory = (0..i.op_count()).any(|n| i.op_kind(n) == OpKind::Memory)
            && i.mnemonic() != iced_x86::Mnemonic::Lea;
        if accesses_memory {
            if matches!(i.memory_segment(), Register::FS | Register::GS) {
                return false;
            }
            if !sandboxed {
                if i.memory_base() != Register::RSP || i.memory_index() != Register::None {
                    return false;
                }
            } else {
                // iced reports a RIP-relative access with its absolute address and no base, so the operand decides
                // whether it is a global, and the access list whether it is written.
                let mut factory = iced_x86::InstructionInfoFactory::new();
                let writes_global = i.is_ip_rel_memory_operand() && factory.info(i).used_memory().iter().any(|m| {
                    matches!(
                            m.access(),
                            iced_x86::OpAccess::Write
                                | iced_x86::OpAccess::ReadWrite
                                | iced_x86::OpAccess::CondWrite
                                | iced_x86::OpAccess::ReadCondWrite
                        )
                });
                // Writes to globals are compared and undone through the image's write watch (difftest_sandboxed).
                let _ = writes_global;
            }
        }
    }
    true
}

pub fn select(image: &Image<'_>, limit: usize, rule: &dyn Fn(&[u8], u32) -> bool) -> Vec<Candidate> {
    let mut out = Vec::new();
    for f in image.functions() {
        let Some(code) = image.bytes(f.begin, f.end - f.begin) else { continue };
        if rule(code, f.begin) {
            out.push(Candidate { rva: f.begin, code: code.to_vec() });
            if out.len() >= limit {
                break;
            }
        }
    }
    out
}

/// Callees a translation may call in the differential test, where they run natively: every function reachable
/// from them by direct calls and jumps, to `depth`, decodes, stays off FS/GS, makes no indirect call or jump (an
/// import, an unknown target) and no system call. Their code need not be covered: it is not translated.
pub struct CalleeCheck<'a> {
    image: &'a Image<'a>,
    starts: std::collections::BTreeMap<u32, u32>,
    memo: std::cell::RefCell<std::collections::HashMap<u32, bool>>,
}

impl<'a> CalleeCheck<'a> {
    pub fn new(image: &'a Image<'a>) -> CalleeCheck<'a> {
        let starts = image.functions().into_iter().map(|f| (f.begin, f.end)).collect();
        CalleeCheck { image, starts, memo: Default::default() }
    }

    pub fn safe(&self, target: u64, depth: u32) -> bool {
        let Ok(rva) = u32::try_from(target) else { return false };
        if let Some(&known) = self.memo.borrow().get(&rva) {
            return known;
        }
        self.memo.borrow_mut().insert(rva, false); // a cycle counts as unsafe until proven
        let ok = depth > 0 && self.check(rva, depth);
        self.memo.borrow_mut().insert(rva, ok);
        ok
    }

    fn check(&self, rva: u32, depth: u32) -> bool {
        use iced_x86::Mnemonic::*;
        let Some(&end) = self.starts.get(&rva) else { return false };
        let Some(code) = self.image.bytes(rva, end - rva) else { return false };
        for i in decode(code, u64::from(rva)) {
            if i.is_invalid() || matches!(i.memory_segment(), Register::FS | Register::GS) {
                return false;
            }
            if matches!(i.mnemonic(), Syscall | Sysenter | Int | Int1 | Int3 | Into | Hlt | Cli | Sti | In | Out | Rdmsr | Wrmsr) {
                return false;
            }
            match i.flow_control() {
                FlowControl::IndirectCall | FlowControl::IndirectBranch | FlowControl::Interrupt => return false,
                FlowControl::Call | FlowControl::UnconditionalBranch | FlowControl::ConditionalBranch => {
                    if i.op0_kind() != OpKind::NearBranch64 {
                        return false;
                    }
                    let t = i.near_branch_target();
                    let inside = t >= u64::from(rva) && t < u64::from(end);
                    if !inside && !self.safe(t, depth - 1) {
                        return false;
                    }
                }
                _ => {}
            }
        }
        true
    }
}

/// The generated crate's lib.rs.
pub fn generate(cands: &[Candidate]) -> Result<String, String> {
    let mut s = String::from("#![allow(warnings)]\n");
    s += PRELUDE;
    for c in cands {
        let name = format!("f_{:x}", c.rva);
        s += &emit_function(&name, &c.code, u64::from(c.rva)).map_err(|e| format!("{name}: {e}"))?;
        s += &emit_entry(&name);
    }
    s += "#[unsafe(no_mangle)]\npub unsafe extern \"C\" fn commons_init(base: u64) { unsafe { set_image_base(base); setup(); } }\n";
    s += "#[unsafe(no_mangle)]\npub unsafe extern \"C\" fn commons_reset_thread() { unsafe { reset_thread(); } }\n";
    s += "#[unsafe(no_mangle)]\npub unsafe extern \"C\" fn commons_function(i: usize, rva: *mut u64, entry: *mut u64) -> bool {\n    let (r, e): (u64, u64) = match i {\n";
    for (k, c) in cands.iter().enumerate() {
        let _ = writeln!(s, "        {k} => ({:#x}, e_f_{:x} as usize as u64),", c.rva, c.rva);
    }
    s += "        _ => return false,\n    };\n    unsafe { *rva = r; *entry = e; }\n    true\n}\n";
    Ok(s)
}

const CARGO_TOML: &str = r#"[package]
name = "commons-track-b"
version = "0.0.0"
edition = "2024"
publish = false

[lib]
crate-type = ["cdylib"]
path = "src/lib.rs"

[profile.release]
opt-level = 2
panic = "abort"
debug = false

[workspace]
"#;

/// Writes the crate and builds it; the library's path.
pub fn build(work: &Path, lib_rs: &str) -> Result<PathBuf, String> {
    let gen_dir = work.join("gen");
    std::fs::create_dir_all(gen_dir.join("src")).map_err(|e| e.to_string())?;
    std::fs::write(gen_dir.join("Cargo.toml"), CARGO_TOML).map_err(|e| e.to_string())?;
    std::fs::write(gen_dir.join("src/lib.rs"), lib_rs).map_err(|e| e.to_string())?;
    let target = work.join("target");
    let status = std::process::Command::new("cargo")
        .args(["build", "--release", "--quiet"])
        .current_dir(&gen_dir)
        .env("CARGO_TARGET_DIR", &target)
        .status()
        .map_err(|e| format!("cargo: {e}"))?;
    if !status.success() {
        return Err(format!("cargo build failed ({status})"));
    }
    Ok(target.join("release").join("commons_track_b.dll"))
}

unsafe extern "system" {
    fn LoadLibraryW(name: *const u16) -> isize;
    fn GetProcAddress(module: isize, name: *const u8) -> *const core::ffi::c_void;
    fn VirtualAlloc(address: *mut core::ffi::c_void, size: usize, kind: u32, protect: u32) -> *mut core::ffi::c_void;
    fn GetWriteWatch(flags: u32, base: *mut core::ffi::c_void, size: usize, addresses: *mut *mut core::ffi::c_void,
                     count: *mut usize, granularity: *mut u32) -> u32;
}

const PAGE: usize = 4096;

/// The image's pages written since the last call (and the watch reset), or None when more than `MAX_DIRTY` were.
fn dirty_pages(base: u64, size: usize) -> Option<Vec<u64>> {
    const MAX_DIRTY: usize = 4096;
    let mut addresses = vec![core::ptr::null_mut::<core::ffi::c_void>(); MAX_DIRTY];
    let (mut count, mut granularity) = (MAX_DIRTY, 0u32);
    let r = unsafe {
        GetWriteWatch(1, base as *mut core::ffi::c_void, size, addresses.as_mut_ptr(), &mut count, &mut granularity)
    };
    if r != 0 || count >= MAX_DIRTY {
        return None;
    }
    Some(addresses[..count].iter().map(|&a| a as u64).collect())
}

pub struct Library {
    pub init: unsafe extern "C" fn(u64),
    pub function: unsafe extern "C" fn(usize, *mut u64, *mut u64) -> bool,
    pub reset_thread: Option<unsafe extern "C" fn()>,
}

pub fn load(path: &Path) -> Result<Library, String> {
    let wide: Vec<u16> = path.as_os_str().to_string_lossy().encode_utf16().chain(Some(0)).collect();
    unsafe {
        let h = LoadLibraryW(wide.as_ptr());
        if h == 0 {
            return Err(format!("cannot load {}", path.display()));
        }
        let init = GetProcAddress(h, b"commons_init\0".as_ptr());
        let function = GetProcAddress(h, b"commons_function\0".as_ptr());
        if init.is_null() || function.is_null() {
            return Err(format!("{} lacks commons_init or commons_function", path.display()));
        }
        let reset = GetProcAddress(h, b"commons_reset_thread\0".as_ptr());
        Ok(Library {
            init: core::mem::transmute(init),
            function: core::mem::transmute(function),
            reset_thread: if reset.is_null() { None } else { Some(core::mem::transmute(reset)) },
        })
    }
}

/// Every function the library has, as (rva, entry address).
pub fn entries(lib: &Library) -> Vec<(u64, u64)> {
    let mut out = Vec::new();
    for i in 0.. {
        let (mut rva, mut entry) = (0u64, 0u64);
        if !unsafe { (lib.function)(i, &mut rva, &mut entry) } {
            break;
        }
        out.push((rva, entry));
    }
    out
}

/// Runs each candidate natively and translated on `rounds` random inputs; the RVAs whose results all agree.
pub fn difftest(cands: &[Candidate], lib: &Library, rounds: usize) -> Vec<u32> {
    let _guard = LOCK.lock().unwrap_or_else(|e| e.into_inner());
    let entry_of: std::collections::HashMap<u64, u64> = entries(lib).into_iter().collect();
    let size: usize = cands.iter().map(|c| (c.code.len() + 63) & !63).sum::<usize>().max(64);
    let exec = unsafe { VirtualAlloc(core::ptr::null_mut(), size, 0x3000, 0x40) } as *mut u8;
    assert!(!exec.is_null(), "no executable memory for the differential test");
    unsafe { (lib.init)(0) };
    let mut stack = vec![0u8; 1 << 16];
    let base = stack.as_mut_ptr() as u64;
    let top = (base + (1 << 15)) & !0xf;
    let above = (top - base) as usize;
    let mut rng = Rng(0x9e37_79b9_7f4a_7c15);
    let mut passed = Vec::new();
    let mut at = 0usize;
    for c in cands {
        let native = unsafe { exec.add(at) };
        unsafe { std::ptr::copy_nonoverlapping(c.code.as_ptr(), native, c.code.len()) };
        at += (c.code.len() + 63) & !63;
        let Some(&entry) = entry_of.get(&u64::from(c.rva)) else { continue };
        if std::env::var_os("COMMONS_RECOMP_TRACE").is_some() {
            eprintln!("difftest {:#x} ({} bytes)", c.rva, c.code.len());
        }
        let mut ok = true;
        for _ in 0..rounds {
            let mut start = HostCtx::default();
            for r in 0..16 {
                start.r[r] = rng.value();
                for q in 0..4 {
                    start.x[r][q] = rng.vector();
                }
            }
            start.r[4] = top;
            let initial: Vec<u8> = (0..stack.len()).map(|_| rng.next() as u8).collect();

            stack.copy_from_slice(&initial);
            let mut a = start;
            unsafe { run_native(native as u64, &mut a) };
            let after_native = stack[above..].to_vec();

            stack.copy_from_slice(&initial);
            let mut b = start;
            unsafe { run_native(entry, &mut b) };
            if a.r != b.r || a.x != b.x || stack[above..] != after_native[..] {
                ok = false;
                break;
            }
        }
        if ok {
            passed.push(c.rva);
        }
    }
    passed
}

/// Maps the image into this process at its preferred base when that is free, else anywhere: native functions then
/// run in place and RIP-relative reads see the image's own data. Returns the base.
pub fn map_image(image: &Image<'_>) -> Result<u64, String> {
    let size = image.size_of_image as usize;
    // MEM_RESERVE | MEM_COMMIT | MEM_WRITE_WATCH: the differential test learns which pages a run wrote.
    let kind = 0x3000 | 0x0020_0000;
    let mut p = unsafe { VirtualAlloc(image.image_base as *mut core::ffi::c_void, size, kind, 0x40) };
    if p.is_null() {
        p = unsafe { VirtualAlloc(core::ptr::null_mut(), size, kind, 0x40) };
    }
    if p.is_null() {
        return Err(format!("cannot map {size} bytes for the image"));
    }
    image.map_into(unsafe { std::slice::from_raw_parts_mut(p as *mut u8, size) });
    Ok(p as u64)
}

pub struct SandboxReport {
    pub passed: Vec<u32>,
    /// Functions whose translation differed from the native function, or faulted where it did not.
    pub differed: usize,
    pub differed_rvas: Vec<u32>,
    /// Functions without enough inputs on which the native function ran to completion.
    pub inconclusive: usize,
}

const SANDBOX: usize = 1 << 16;

/// The translation an entry stub enters: the stub is `push rax; lea rax, [rip + disp32]; jmp ...`.
fn translation_of(entry: u64) -> u64 {
    unsafe {
        let p = entry as *const u8;
        if *p == 0x50 && *p.add(1) == 0x48 && *p.add(2) == 0x8D && *p.add(3) == 0x05 {
            let disp = (p.add(4) as *const i32).read_unaligned();
            return (entry + 8).wrapping_add(disp as i64 as u64);
        }
    }
    0
}
const GUARD: usize = 1 << 16;

/// `size` writable bytes between two reserved, never committed guard regions, so a write past either end faults
/// (and the differential test skips that input) instead of reaching this process's own memory.
fn guarded(size: usize) -> &'static mut [u8] {
    unsafe {
        let base = VirtualAlloc(core::ptr::null_mut(), GUARD + size + GUARD, 0x2000, 0x01) as *mut u8; // reserve
        assert!(!base.is_null(), "cannot reserve guarded memory");
        let inner = VirtualAlloc(base.add(GUARD) as *mut core::ffi::c_void, size, 0x1000, 0x04) as *mut u8; // commit
        assert!(!inner.is_null(), "cannot commit guarded memory");
        std::slice::from_raw_parts_mut(inner, size)
    }
}

/// The differential test with memory: the image mapped at `base` (native functions run in place), each register
/// either a generated value or a pointer into a sandbox of random bytes, the same sandbox and stack for both runs.
/// An input on which the native function faults is skipped; the translation must then match on every other input,
/// and at least a quarter of the inputs must have run.
pub fn difftest_sandboxed(cands: &[Candidate], lib: &Library, base: u64, image_size: usize, rounds: usize) -> SandboxReport {
    use crate::harness::{run_native_timed, Outcome};
    let _guard = LOCK.lock().unwrap_or_else(|e| e.into_inner());
    let entry_of: std::collections::HashMap<u64, u64> = entries(lib).into_iter().collect();
    unsafe { (lib.init)(base) };
    // The image as mapped, to undo what a run wrote to it.
    let pristine: Vec<u8> = unsafe { std::slice::from_raw_parts(base as *const u8, image_size) }.to_vec();
    let image = unsafe { std::slice::from_raw_parts_mut(base as *mut u8, image_size) };
    let restore = |image: &mut [u8], pages: &[u64]| {
        for &p in pages {
            let at = (p - base) as usize;
            let end = (at + PAGE).min(image.len());
            image[at..end].copy_from_slice(&pristine[at..end]);
        }
    };
    let sandbox = guarded(SANDBOX);
    let sbase = sandbox.as_mut_ptr() as u64;
    let stack = guarded(1 << 16);
    let top = (stack.as_mut_ptr() as u64 + (1 << 15)) & !0xf;
    let above = (top - stack.as_ptr() as u64) as usize;
    let mut rng = Rng(0x2545_f491_4f6c_dd1d);
    let mut report = SandboxReport { passed: Vec::new(), differed: 0, differed_rvas: Vec::new(), inconclusive: 0 };
    for c in cands {
        let Some(&entry) = entry_of.get(&u64::from(c.rva)) else { continue };
        if std::env::var_os("COMMONS_RECOMP_TRACE").is_some() {
            eprintln!("difftest {:#x} ({} bytes)", c.rva, c.code.len());
        }
        let native = base + u64::from(c.rva);
        let (mut ran, mut differs) = (0usize, false);
        for _ in 0..rounds {
            let mut start = HostCtx::default();
            for r in 0..16 {
                start.r[r] = if rng.next() % 2 == 0 {
                    (sbase + 4096 + rng.next() % (SANDBOX as u64 - 8192)) & !7
                } else {
                    rng.value()
                };
                for q in 0..4 {
                    start.x[r][q] = rng.vector();
                }
            }
            start.r[4] = top;
            let initial_sandbox: Vec<u8> = (0..SANDBOX).map(|_| rng.next() as u8).collect();
            let initial_stack: Vec<u8> = (0..stack.len()).map(|_| rng.next() as u8).collect();

            sandbox.copy_from_slice(&initial_sandbox);
            stack.copy_from_slice(&initial_stack);
            // The entry stub and commons_entry store rax, rcx and the translation's address below the return address
            // (where the callee's own frame starts, uninitialised). Put the same words there for the native run, so a
            // function that reads its uninitialised frame reads the same bytes in both.
            let slot = (top - 8 - stack.as_ptr() as u64) as usize; // the return address of the thunk's call
            for (k, v) in [start.r[0], start.r[1], translation_of(entry)].iter().enumerate() {
                let at = slot - 8 * (k + 1);
                stack[at..at + 8].copy_from_slice(&v.to_le_bytes());
            }
            let mut a = start;
            let _ = dirty_pages(base, image_size); // reset the watch
            // A fault or a run past 2 ms (a loop on a generated count): this input is outside what the function
            // accepts, or too long to compare.
            let native_outcome = unsafe { run_native_timed(native, &mut a, 2_000) };
            let Some(native_pages) = dirty_pages(base, image_size) else {
                continue; // wrote too much of the image to compare
            };
            let native_image: Vec<(u64, Vec<u8>)> = native_pages
                .iter()
                .map(|&p| {
                    let at = (p - base) as usize;
                    (p, image[at..(at + PAGE).min(image_size)].to_vec())
                })
                .collect();
            restore(image, &native_pages);
            if !matches!(native_outcome, Outcome::Done(_)) {
                continue;
            }
            let (native_sandbox, native_stack) = (sandbox.to_vec(), stack[above..].to_vec());

            sandbox.copy_from_slice(&initial_sandbox);
            stack.copy_from_slice(&initial_stack);
            let mut b = start;
            let translated = unsafe { run_native_timed(entry, &mut b, 100_000) };
            if let Some(reset) = lib.reset_thread {
                unsafe { reset() };
            }
            let translated_pages = dirty_pages(base, image_size);
            // The image must have been written alike: the same pages, the same bytes.
            let image_differs = match &translated_pages {
                None => true,
                Some(pages) => {
                    let mut all: Vec<u64> = native_pages.iter().chain(pages.iter()).copied().collect();
                    all.sort_unstable();
                    all.dedup();
                    all.iter().any(|&p| {
                        let at = (p - base) as usize;
                        let end = (at + PAGE).min(image_size);
                        let native_bytes = native_image
                            .iter()
                            .find(|(q, _)| *q == p)
                            .map(|(_, b)| &b[..])
                            .unwrap_or(&pristine[at..end]);
                        native_bytes != &image[at..end]
                    })
                }
            };
            if let Some(pages) = &translated_pages {
                restore(image, pages);
            }
            let why = if !matches!(translated, Outcome::Done(_)) {
                Some(format!("translation {translated:?}"))
            } else if a.r != b.r {
                let r = (0..16).find(|&r| a.r[r] != b.r[r]).unwrap_or(0);
                Some(format!("r{r}: native {:#x}, translated {:#x}", a.r[r], b.r[r]))
            } else if a.x != b.x {
                Some("a ymm register".to_string())
            } else if sandbox[..] != native_sandbox[..] {
                let at = (0..SANDBOX).find(|&k| sandbox[k] != native_sandbox[k]).unwrap_or(0);
                Some(format!("sandbox byte {at:#x}"))
            } else if stack[above..] != native_stack[..] {
                Some("the caller's stack".to_string())
            } else if image_differs {
                Some("the image's globals".to_string())
            } else {
                None
            };
            if let Some(why) = why {
                if std::env::var_os("COMMONS_RECOMP_TRACE").is_some() {
                    eprintln!("differed {:#x}: {why}; start {:x?}", c.rva, start.r);
                }
                differs = true;
                break;
            }
            ran += 1;
        }
        if differs {
            report.differed += 1;
            report.differed_rvas.push(c.rva);
        } else if ran * 4 < rounds {
            report.inconclusive += 1;
        } else {
            report.passed.push(c.rva);
        }
    }
    report
}

/// The manifest `cargo commons run` reads for this build.
pub fn manifest(build: &str, library: &Path, cands: &[Candidate], passed: &[u32]) -> String {
    let mut s = format!(
        "# Track B for this build, made on this machine (commons-recomp). Not to be committed.\nbuild = \"{build}\"\nlibrary = '{}'\n",
        library.display()
    );
    for c in cands.iter().filter(|c| passed.contains(&c.rva)) {
        let prologue: String = c.code[..16].iter().map(|b| format!("{b:02x}")).collect();
        let _ = write!(
            s,
            "\n[[function]]\nname = \"f_{:x}\"\nrva = {:#x}\nprologue = \"{prologue}\"\nstatus = \"verified\"\n",
            c.rva, c.rva
        );
    }
    s
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_checkable_functions_are_selected() {
        // lea rax, [rcx + rdx]; add rax, 1; imul rax, rax; xor r8d, r8d; ret: 16 bytes, pure, no loop
        let pure = [0x48, 0x8D, 0x04, 0x11, 0x48, 0x83, 0xC0, 0x01, 0x48, 0x0F, 0xAF, 0xC0, 0x45, 0x31, 0xC0, 0xC3];
        assert!(checkable(&pure, 0x1000));
        // the same, but its first instruction reads memory through rcx: random registers cannot test it
        let mut reads = pure;
        reads[..4].copy_from_slice(&[0x48, 0x8B, 0x01, 0x90]); // mov rax, [rcx]; nop
        assert!(!checkable(&reads, 0x1000));
        // a stack read is fine: mov rax, [rsp + 8]
        let mut stack = pure;
        stack[..5].copy_from_slice(&[0x48, 0x8B, 0x44, 0x24, 0x08]);
        stack[5..8].copy_from_slice(&[0x48, 0x01, 0xC8]); // add rax, rcx
        assert!(checkable(&stack, 0x1000));
        // a loop (a branch backwards) is refused: dec rcx; jnz back
        let mut lp = pure;
        lp[12..16].copy_from_slice(&[0x75, 0xF2, 0x90, 0xC3]); // jnz -14 (to the start)
        assert!(!checkable(&lp, 0x1000));
        // a fragment that ends without returning is refused: three moves and no ret
        let fragment = [0x4C, 0x8B, 0xBC, 0x24, 0x60, 0x40, 0, 0, 0xB8, 0x01, 0, 0, 0, 0x48, 0x8B, 0x9C, 0x24, 0x70, 0x40, 0, 0];
        assert!(!checkable(&fragment, 0x1000));
        // an epilogue fragment is refused: mov rbp, [rsp+38h]; mov rsi, [rsp+40h]; add rsp, 20h; pop rdi; ret
        let tail = [0x48, 0x8B, 0x6C, 0x24, 0x38, 0x48, 0x8B, 0x74, 0x24, 0x40, 0x48, 0x83, 0xC4, 0x20, 0x5F, 0xC3];
        assert!(!checkable(&tail, 0x1000));
        // sandboxed: memory through a register, and reading or writing a global, are all fine
        let mut through = pure;
        through[..4].copy_from_slice(&[0x48, 0x8B, 0x01, 0x90]); // mov rax, [rcx]; nop
        assert!(checkable_sandboxed(&through, 0x1000));
        let tail = [0x48, 0x89, 0xC8, 0x48, 0x89, 0xC8, 0x90, 0xC3];
        let mut read_global = vec![0xC5, 0xFC, 0x28, 0x05, 0x00, 0x01, 0x00, 0x00]; // vmovaps ymm0, [rip+100h]
        read_global.extend_from_slice(&tail);
        assert!(checkable_sandboxed(&read_global, 0x1000));
        let mut write_global = vec![0xC5, 0xFC, 0x29, 0x05, 0x00, 0x01, 0x00, 0x00]; // vmovaps [rip+100h], ymm0
        write_global.extend_from_slice(&tail);
        assert!(checkable_sandboxed(&write_global, 0x1000)); // compared and undone through the write watch
        // loops: refused without the watchdog, taken by the sandboxed rule (but never a branch to the first 14 bytes)
        // the 15 bytes before pure's ret, then `dec rcx; jnz -5` (a loop back to offset 15) and ret
        let mut lp2 = pure[..15].to_vec();
        lp2.extend_from_slice(&[0x48, 0xFF, 0xC9, 0x75, 0xFB, 0xC3]);
        assert!(!checkable(&lp2, 0x1000));
        assert!(checkable_sandboxed(&lp2, 0x1000));
        assert!(!checkable_sandboxed(&lp, 0x1000)); // jnz to the start, inside the jump's bytes
        // a function shorter than 16 bytes is refused (the jump needs 14)
        assert!(!checkable(&[0x48, 0x89, 0xC8, 0xC3], 0x1000));
    }
}
