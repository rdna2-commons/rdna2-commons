//! Track B of RDNA2 Commons: functions of a title that are statically recompiled into our own code and
//! installed over the native ones when the runtime has mapped the executable. Everything a build's manifest does not
//! list runs natively under track A (the VIctory runtime in `victory/`).
//!
//! A manifest is `recomp/manifests/<build hash>.toml`, keyed by the build identity the runtime prints (BLAKE3 of the
//! executable). Each `[[function]]` names one replacement: its relative address, the bytes its native code starts
//! with (checked before anything is written, so a manifest never patches a build it was not made for), the name of
//! our implementation in [`REGISTRY`], and a status:
//!
//! * `verified`: its differential test passes against the native function; installed by default.
//! * `testing`: installed only when asked for by name (`COMMONS_ONLY`).
//! * `off`: never installed.
//!
//! `COMMONS_TRACK=a` installs nothing (the title runs as track A alone); `COMMONS_ONLY=name[,name]` installs just those.
//! No game code or data is kept here: addresses, byte signatures and names are interoperability facts.

pub mod census;
pub mod elf;
pub mod harness;
pub mod pipeline;
pub mod ps5;
pub mod relinked;

use std::collections::{BTreeMap, HashMap};
use std::fmt;

use serde::Deserialize;

/// One replacement implementation: the address of a function with the native one's calling convention.
pub struct Replacement {
    pub name: &'static str,
    pub code: unsafe extern "C" fn(),
}

/// Every recompiled function this build of the crate carries. Empty until the first function lands with its
/// differential test; a manifest naming something missing here is refused for that function.
pub static REGISTRY: &[Replacement] = &[];

#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Status {
    Verified,
    Testing,
    Off,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Function {
    pub name: String,
    pub rva: u64,
    /// Hex bytes the native function starts with; at least the 14 the jump overwrites.
    pub prologue: String,
    pub status: Status,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Manifest {
    pub build: String,
    /// A track B library built on this machine (commons-recomp): its functions are installed from it.
    #[serde(default)]
    pub library: Option<String>,
    /// Where the image the RVAs count from lies inside the running module: the module base plus this. Absent
    /// (0) when the module is the image itself; a relinked PS5 executable keeps its ELF at `.elf0`.
    #[serde(default)]
    pub module_offset: Option<u64>,
    #[serde(default, rename = "function")]
    pub functions: Vec<Function>,
}

impl Manifest {
    pub fn parse(text: &str) -> Result<Manifest, String> {
        toml::from_str(text).map_err(|e| e.to_string())
    }
}

/// What the runtime prints after installing: which functions run as track B and why the others do not.
#[derive(Debug, Default, PartialEq, Eq)]
pub struct Report {
    pub installed: Vec<String>,
    pub skipped: BTreeMap<String, String>,
}

impl fmt::Display for Report {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "track B        {} function(s) installed", self.installed.len())?;
        if !self.skipped.is_empty() {
            write!(f, ", {} not", self.skipped.len())?;
        }
        write!(f, "; everything else runs natively (track A)")
    }
}

/// Which manifest entries to install, from the environment (`COMMONS_TRACK`, `COMMONS_ONLY`).
#[derive(Debug, Clone, Default)]
pub struct Selection {
    pub track_a_only: bool,
    pub only: Option<Vec<String>>,
}

impl Selection {
    pub fn from_env() -> Selection {
        Selection {
            track_a_only: std::env::var("COMMONS_TRACK").is_ok_and(|v| v.eq_ignore_ascii_case("a")),
            only: std::env::var("COMMONS_ONLY")
                .ok()
                .map(|v| v.split(',').map(|s| s.trim().to_string()).filter(|s| !s.is_empty()).collect()),
        }
    }

    fn wants(&self, f: &Function) -> Result<(), &'static str> {
        if self.track_a_only {
            return Err("COMMONS_TRACK=a");
        }
        match (&self.only, &f.status) {
            (_, Status::Off) => Err("status off"),
            (Some(only), _) if !only.iter().any(|n| n == &f.name) => Err("not in COMMONS_ONLY"),
            (Some(_), _) => Ok(()),
            (None, Status::Verified) => Ok(()),
            (None, Status::Testing) => Err("status testing (name it in COMMONS_ONLY)"),
        }
    }
}

fn hex_bytes(s: &str) -> Option<Vec<u8>> {
    let s: String = s.chars().filter(|c| !c.is_whitespace()).collect();
    if s.len() % 2 != 0 {
        return None;
    }
    (0..s.len()).step_by(2).map(|i| u8::from_str_radix(&s[i..i + 2], 16).ok()).collect()
}

/// `jmp [rip+0]` followed by the absolute target: 14 bytes, no register touched.
pub const JUMP_LEN: usize = 14;
pub fn jump_to(target: u64) -> [u8; JUMP_LEN] {
    let mut j = [0u8; JUMP_LEN];
    j[..6].copy_from_slice(&[0xFF, 0x25, 0, 0, 0, 0]);
    j[6..].copy_from_slice(&target.to_le_bytes());
    j
}

/// Writes code bytes at an address (the runtime's mapped image is ours to change before it runs).
pub trait CodeWriter {
    /// The `len` bytes at `address`, or None when they cannot be read.
    fn read(&self, address: u64, len: usize) -> Option<Vec<u8>>;
    fn write(&mut self, address: u64, bytes: &[u8]) -> bool;
}

/// Installs the selected functions of `manifest` into an image mapped at `base`, through `writer`, with
/// replacements looked up in `registry`. Nothing is written for an entry whose prologue does not match.
pub fn install_with(
    manifest: &Manifest,
    base: u64,
    registry: &[Replacement],
    selection: &Selection,
    writer: &mut dyn CodeWriter,
) -> Report {
    let mut report = Report::default();
    let mut indexed = HashMap::with_capacity(registry.len());
    for replacement in registry {
        indexed.entry(replacement.name).or_insert(replacement);
    }
    for f in &manifest.functions {
        let skip = |why: String, report: &mut Report| {
            report.skipped.insert(f.name.clone(), why);
        };
        if let Err(why) = selection.wants(f) {
            skip(why.to_string(), &mut report);
            continue;
        }
        let Some(replacement) = indexed.get(f.name.as_str()) else {
            skip("no implementation in this build of commons-recomp".into(), &mut report);
            continue;
        };
        let Some(expected) = hex_bytes(&f.prologue).filter(|b| b.len() >= JUMP_LEN) else {
            skip(format!("prologue must be at least {JUMP_LEN} hex bytes"), &mut report);
            continue;
        };
        let at = base.wrapping_add(f.rva);
        if writer.read(at, expected.len()).as_deref() != Some(&expected[..]) {
            skip("native bytes differ from the manifest (another build?)".into(), &mut report);
            continue;
        }
        if !writer.write(at, &jump_to(replacement.code as usize as u64)) {
            skip("could not write the jump".into(), &mut report);
            continue;
        }
        report.installed.push(f.name.clone());
    }
    report
}

#[cfg(windows)]
mod process {
    use super::CodeWriter;

    unsafe extern "system" {
        fn VirtualProtect(address: *mut core::ffi::c_void, size: usize, protect: u32, old: *mut u32) -> i32;
        fn FlushInstructionCache(process: isize, address: *const core::ffi::c_void, size: usize) -> i32;
        fn GetCurrentProcess() -> isize;
    }
    const PAGE_EXECUTE_READWRITE: u32 = 0x40;

    /// The current process's memory.
    pub struct Process;

    impl CodeWriter for Process {
        fn read(&self, address: u64, len: usize) -> Option<Vec<u8>> {
            if address == 0 {
                return None;
            }
            // SAFETY: the address is inside the image the runtime just mapped (base + an RVA the manifest names).
            Some(unsafe { std::slice::from_raw_parts(address as *const u8, len) }.to_vec())
        }
        fn write(&mut self, address: u64, bytes: &[u8]) -> bool {
            let p = address as *mut core::ffi::c_void;
            let mut old = 0u32;
            // SAFETY: as in read; the protection is restored afterwards.
            unsafe {
                if VirtualProtect(p, bytes.len(), PAGE_EXECUTE_READWRITE, &mut old) == 0 {
                    return false;
                }
                std::ptr::copy_nonoverlapping(bytes.as_ptr(), p as *mut u8, bytes.len());
                VirtualProtect(p, bytes.len(), old, &mut old);
                FlushInstructionCache(GetCurrentProcess(), p, bytes.len());
            }
            true
        }
    }
}

/// The functions of a library commons-recomp built on this machine, as replacements named `f_<rva>`, after its
/// `commons_init(base)`. Loaded once per run; the names live as long as the process.
#[cfg(windows)]
fn library_registry(path: &std::path::Path, base: u64) -> Result<Vec<Replacement>, String> {
    let lib = pipeline::load(path)?;
    unsafe { (lib.init)(base) };
    Ok(pipeline::entries(&lib)
        .into_iter()
        .map(|(rva, entry)| Replacement {
            name: Box::leak(format!("f_{rva:x}").into_boxed_str()),
            // SAFETY: the library's entry stubs take the native calling convention.
            code: unsafe { core::mem::transmute::<usize, unsafe extern "C" fn()>(entry as usize) },
        })
        .collect())
}

/// The runtime's hook point: called once the executable is mapped, before it runs. Reads
/// `recomp/manifests/<build>.toml` from `manifest_dir`; a build without a manifest runs as track A alone.
#[cfg(windows)]
pub fn install(base: u64, build: &str, manifest_dir: &std::path::Path) -> Report {
    let path = manifest_dir.join(format!("{build}.toml"));
    let Ok(text) = std::fs::read_to_string(&path) else {
        return Report::default();
    };
    match Manifest::parse(&text) {
        Ok(manifest) => install_manifest(base, build, &path, &manifest),
        Err(e) => {
            let mut r = Report::default();
            r.skipped.insert(path.display().to_string(), e);
            r
        }
    }
}

#[cfg(windows)]
pub fn install_manifest(base: u64, build: &str, path: &std::path::Path, manifest: &Manifest) -> Report {
    if !manifest.build.eq_ignore_ascii_case(build) {
        let mut report = Report::default();
        report.skipped.insert(path.display().to_string(), "the manifest names another build".into());
        return report;
    }
    let selection = Selection::from_env();
    let mut process = process::Process;
    match &manifest.library {
        Some(lib) => match library_registry(std::path::Path::new(lib), base) {
            Ok(registry) => install_with(manifest, base, &registry, &selection, &mut process),
            Err(error) => {
                let mut report = Report::default();
                report.skipped.insert(lib.clone(), error);
                report
            }
        },
        None => install_with(manifest, base, REGISTRY, &selection, &mut process),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    struct Memory {
        base: u64,
        bytes: Vec<u8>,
    }
    impl CodeWriter for Memory {
        fn read(&self, address: u64, len: usize) -> Option<Vec<u8>> {
            let at = address.checked_sub(self.base)? as usize;
            self.bytes.get(at..at + len).map(<[u8]>::to_vec)
        }
        fn write(&mut self, address: u64, bytes: &[u8]) -> bool {
            let at = (address - self.base) as usize;
            self.bytes[at..at + bytes.len()].copy_from_slice(bytes);
            true
        }
    }

    unsafe extern "C" fn ours() {}
    static REG: &[Replacement] = &[Replacement { name: "sample", code: ours }];
    const PROLOGUE: &str = "48895c2408 4889742410 57 4883ec20 33";

    fn manifest(status: &str, prologue: &str) -> Manifest {
        Manifest::parse(&format!(
            "build = \"abc\"\n[[function]]\nname = \"sample\"\nrva = 0x100\nprologue = \"{prologue}\"\nstatus = \"{status}\"\n"
        ))
        .unwrap()
    }

    fn image() -> Memory {
        let mut bytes = vec![0xCCu8; 0x200];
        let p = hex_bytes(PROLOGUE).unwrap();
        bytes[0x100..0x100 + p.len()].copy_from_slice(&p);
        Memory { base: 0x1_4000_0000, bytes }
    }

    #[test]
    fn a_verified_function_gets_a_jump_to_ours() {
        let mut mem = image();
        let r = install_with(&manifest("verified", PROLOGUE), mem.base, REG, &Selection::default(), &mut mem);
        assert_eq!(r.installed, vec!["sample".to_string()]);
        assert_eq!(&mem.bytes[0x100..0x100 + JUMP_LEN], &jump_to(ours as usize as u64));
    }

    #[test]
    fn duplicate_replacement_names_keep_the_first_implementation() {
        unsafe extern "C" fn another() {}
        let registry = [
            Replacement { name: "sample", code: ours },
            Replacement { name: "sample", code: another },
        ];
        let mut mem = image();
        let report = install_with(&manifest("verified", PROLOGUE), mem.base, &registry, &Selection::default(), &mut mem);
        assert_eq!(report.installed, ["sample"]);
        assert_eq!(&mem.bytes[0x100..0x100 + JUMP_LEN], &jump_to(ours as usize as u64));
    }

    #[test]
    fn nothing_is_written_over_another_build() {
        let mut mem = image();
        let other = "48895c2408 4889742410 57 4883ec20 34";
        let r = install_with(&manifest("verified", other), mem.base, REG, &Selection::default(), &mut mem);
        assert!(r.installed.is_empty() && r.skipped.contains_key("sample"));
        let p = hex_bytes(PROLOGUE).unwrap();
        assert_eq!(&mem.bytes[0x100..0x100 + p.len()], &p[..]);
    }

    #[test]
    fn track_a_testing_and_off_install_nothing() {
        for (status, selection) in [
            ("verified", Selection { track_a_only: true, only: None }),
            ("testing", Selection::default()),
            ("off", Selection { track_a_only: false, only: Some(vec!["sample".into()]) }),
        ] {
            let mut mem = image();
            let r = install_with(&manifest(status, PROLOGUE), mem.base, REG, &selection, &mut mem);
            assert!(r.installed.is_empty(), "{status}");
        }
        // A testing function named in COMMONS_ONLY is installed.
        let mut mem = image();
        let only = Selection { track_a_only: false, only: Some(vec!["sample".into()]) };
        let r = install_with(&manifest("testing", PROLOGUE), mem.base, REG, &only, &mut mem);
        assert_eq!(r.installed.len(), 1);
    }

    #[test]
    fn a_function_without_an_implementation_is_skipped() {
        let mut mem = image();
        let r = install_with(&manifest("verified", PROLOGUE), mem.base, &[], &Selection::default(), &mut mem);
        assert!(r.installed.is_empty());
        assert!(r.skipped["sample"].contains("no implementation"));
    }

    #[test]
    fn short_prologues_are_refused() {
        let mut mem = image();
        let r = install_with(&manifest("verified", "4889"), mem.base, REG, &Selection::default(), &mut mem);
        assert!(r.installed.is_empty());
    }
}
