//! `commons-ps5-trackb <eboot.elf> <eboot.exe> <elf manifest> --out DIR`: track B for a PS5 executable that
//! AnyPS5's relinker converted. Keeps the verified functions of the ELF's manifest (made by commons-recomp) whose
//! bytes the relinker left unchanged, and writes DIR/<build of eboot.exe>.toml for the preload library
//! (`commons_ps5_preload`, loaded through AnyPS5's APS5_PRELOAD). Reads the player's files and writes only to DIR.
use std::path::PathBuf;
use std::process::ExitCode;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let out = args.iter().position(|a| a == "--out").and_then(|i| args.get(i + 1)).map(PathBuf::from);
    let (Some(elf_path), Some(pe_path), Some(manifest_path), Some(out)) = (args.first(), args.get(1), args.get(2), out) else {
        eprintln!("usage: commons-ps5-trackb <eboot.elf> <eboot.exe> <elf manifest> --out DIR");
        return ExitCode::from(2);
    };
    let run = || -> Result<(), String> {
        let read = |p: &str| std::fs::read(p).map_err(|e| format!("{p}: {e}"));
        let (elf_data, pe_data) = (read(elf_path)?, read(pe_path)?);
        let text = std::fs::read_to_string(manifest_path).map_err(|e| format!("{manifest_path}: {e}"))?;
        let manifest = commons_recomp::Manifest::parse(&text)?;
        let elf_build = blake3::hash(&elf_data).to_hex().to_string();
        if !manifest.build.eq_ignore_ascii_case(&elf_build) {
            return Err(format!("{manifest_path} was made for build {}, not for {elf_path} ({elf_build})", manifest.build));
        }
        let elf = commons_recomp::census::Image::parse(&elf_data)?;
        let pe = commons_recomp::census::Image::parse(&pe_data)?;
        let base_rva = commons_recomp::relinked::elf_base_rva(&pe_data)?;
        let keep = commons_recomp::relinked::unchanged(&elf, &pe, base_rva, &elf.functions());
        let build = blake3::hash(&pe_data).to_hex().to_string();
        let relinked = commons_recomp::relinked::manifest_for(&manifest, &keep, &build, base_rva);
        std::fs::create_dir_all(&out).map_err(|e| format!("{}: {e}", out.display()))?;
        let path = out.join(format!("{build}.toml"));
        std::fs::write(&path, commons_recomp::relinked::to_toml(&relinked)).map_err(|e| format!("{}: {e}", path.display()))?;
        let verified = manifest.functions.iter().filter(|f| f.status == commons_recomp::Status::Verified).count();
        println!("elf build      {elf_build}");
        println!("relinked build {build}");
        println!("elf at         module base + {base_rva:#x}");
        println!("verified       {verified} functions in the ELF manifest");
        println!("unchanged      {} of them in the relinked executable", relinked.functions.len());
        println!("manifest       {}", path.display());
        Ok(())
    };
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("error: {e}");
            ExitCode::from(1)
        }
    }
}
