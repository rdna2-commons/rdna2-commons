//! Track B for a relinked PS5 executable, installed from inside its process. AnyPS5 loads this library when
//! `APS5_PRELOAD` names it and calls `aps5_preload` on the main thread before the title's code starts. It reads
//! `COMMONS_RECOMP_DIR/<build of the running executable>.toml` (written by `commons-ps5-trackb`) and installs those
//! functions at the module base plus the manifest's `module_offset`. Without a directory or a manifest it installs
//! nothing and the title runs natively.
use std::path::Path;

/// Where the manifest's RVAs start in the running process.
pub fn image_base(module_base: u64, manifest: &commons_recomp::Manifest) -> u64 {
    module_base.wrapping_add(manifest.module_offset.unwrap_or(0))
}

/// The build identity of an executable: BLAKE3 of its file, as commons-ps5-trackb names the manifest.
pub fn build_of(executable: &Path) -> Result<String, String> {
    let data = std::fs::read(executable).map_err(|e| format!("{}: {e}", executable.display()))?;
    Ok(blake3::hash(&data).to_hex().to_string())
}

#[cfg(windows)]
unsafe extern "system" {
    fn GetModuleHandleW(name: *const u16) -> *mut core::ffi::c_void;
}

/// Called by AnyPS5 once, before the title runs. Returns the number of installed functions, 0 when track B is
/// not asked for, and -1 when it was asked for and could not be installed.
#[cfg(windows)]
#[unsafe(no_mangle)]
pub extern "C" fn aps5_preload() -> i32 {
    let Some(dir) = std::env::var_os("COMMONS_RECOMP_DIR") else {
        eprintln!("track B        COMMONS_RECOMP_DIR is not set: the title runs natively");
        return 0;
    };
    let dir = Path::new(&dir);
    let result = (|| -> Result<i32, String> {
        let exe = std::env::current_exe().map_err(|e| e.to_string())?;
        let build = build_of(&exe)?;
        let path = dir.join(format!("{build}.toml"));
        let text = std::fs::read_to_string(&path).map_err(|e| format!("{}: {e}", path.display()))?;
        let manifest = commons_recomp::Manifest::parse(&text)?;
        // SAFETY: a null name asks for the module the process was started from.
        let module = unsafe { GetModuleHandleW(core::ptr::null()) } as u64;
        let report = commons_recomp::install_manifest(image_base(module, &manifest), &build, &path, &manifest);
        eprintln!("{report}");
        for (name, why) in report.skipped.iter().take(5) {
            eprintln!("track B        not installed: {name}: {why}");
        }
        Ok(report.installed.len() as i32)
    })();
    result.unwrap_or_else(|e| {
        eprintln!("track B        error: {e}");
        -1
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_base_adds_the_manifest_offset() {
        let with = commons_recomp::Manifest::parse("build = \"x\"\nmodule_offset = 0x10000\n").unwrap();
        let without = commons_recomp::Manifest::parse("build = \"x\"\n").unwrap();
        assert_eq!(image_base(0x3f0000, &with), 0x400000);
        assert_eq!(image_base(0x3f0000, &without), 0x3f0000);
    }

    #[test]
    fn the_build_is_the_blake3_of_the_file() {
        let path = std::env::temp_dir().join(format!("commons-preload-{}.bin", std::process::id()));
        std::fs::write(&path, b"abc").unwrap();
        let build = build_of(&path).unwrap();
        std::fs::remove_file(&path).unwrap();
        assert_eq!(build, blake3::hash(b"abc").to_hex().to_string());
        assert!(build_of(&path).is_err());
    }
}
