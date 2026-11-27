//! Track B over a PS5 executable that AnyPS5's relinker turned into a Windows PE. The relinker keeps the ELF's
//! loadable segments as sections `.elf0`, `.elf1`, ... and rewrites some instructions on the way (thread-local
//! accesses, AMD-only instructions). A function recompiled from the ELF is therefore installed only where the
//! relinked image still holds exactly the same bytes for the whole function; everything else stays native.

use std::collections::BTreeSet;

use crate::census::{Image, RuntimeFunction};
use crate::{Function, Manifest, Status};

fn u16_at(d: &[u8], o: usize) -> Option<u16> {
    Some(u16::from_le_bytes(d.get(o..o + 2)?.try_into().ok()?))
}
fn u32_at(d: &[u8], o: usize) -> Option<u32> {
    Some(u32::from_le_bytes(d.get(o..o + 4)?.try_into().ok()?))
}

/// The RVA of the relinked image's `.elf0` section: where the ELF's first loadable byte (its base) lies.
pub fn elf_base_rva(pe: &[u8]) -> Result<u32, String> {
    let header = u32_at(pe, 0x3C).ok_or("no DOS header")? as usize;
    if pe.get(header..header + 4) != Some(b"PE\0\0") {
        return Err("not a PE image".into());
    }
    let count = u16_at(pe, header + 6).ok_or("short COFF header")? as usize;
    let optional = u16_at(pe, header + 20).ok_or("short COFF header")? as usize;
    let table = header + 24 + optional;
    for i in 0..count {
        let s = table + 40 * i;
        let name = pe.get(s..s + 8).ok_or("short section table")?;
        if name == b".elf0\0\0\0" {
            return u32_at(pe, s + 12).ok_or_else(|| "short section table".into());
        }
    }
    Err("no .elf0 section: not an executable written by AnyPS5's relinker".into())
}

/// The functions whose bytes are the same in the ELF (at `begin..end` from its base) and in the relinked image
/// (at the same offsets from `base_rva`).
pub fn unchanged(elf: &Image<'_>, pe: &Image<'_>, base_rva: u32, functions: &[RuntimeFunction]) -> BTreeSet<u32> {
    functions
        .iter()
        .filter(|f| f.end > f.begin)
        .filter(|f| {
            let len = f.end - f.begin;
            let Some(at) = base_rva.checked_add(f.begin) else { return false };
            matches!((elf.bytes(f.begin, len), pe.bytes(at, len)), (Some(a), Some(b)) if a == b)
        })
        .map(|f| f.begin)
        .collect()
}

/// A manifest for the relinked executable: the verified functions of `manifest` (made from the ELF) that are
/// unchanged, keyed by the relinked executable's build, installed at the module base plus `module_offset`.
pub fn manifest_for(manifest: &Manifest, keep: &BTreeSet<u32>, build: &str, module_offset: u32) -> Manifest {
    Manifest {
        build: build.to_string(),
        library: manifest.library.clone(),
        module_offset: Some(module_offset as u64),
        functions: manifest
            .functions
            .iter()
            .filter(|f| f.status == Status::Verified && u32::try_from(f.rva).is_ok_and(|r| keep.contains(&r)))
            .cloned()
            .collect::<Vec<Function>>(),
    }
}

/// The manifest as TOML, in the format `Manifest::parse` reads.
pub fn to_toml(m: &Manifest) -> String {
    let mut out = String::from("# Track B for a relinked PS5 executable, made on this machine. Not to be committed.\n");
    out.push_str(&format!("build = \"{}\"\n", m.build));
    if let Some(lib) = &m.library {
        out.push_str(&format!("library = '{lib}'\n"));
    }
    if let Some(offset) = m.module_offset {
        out.push_str(&format!("module_offset = {offset:#x}\n"));
    }
    for f in &m.functions {
        out.push_str(&format!(
            "\n[[function]]\nname = \"{}\"\nrva = {:#x}\nprologue = \"{}\"\nstatus = \"verified\"\n",
            f.name, f.rva, f.prologue
        ));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A PE32+ with one section `.elf0` at `rva` holding `body`.
    fn pe(rva: u32, body: &[u8]) -> Vec<u8> {
        let mut d = vec![0u8; 0x400];
        d[0x3C..0x40].copy_from_slice(&0x80u32.to_le_bytes());
        d[0x80..0x84].copy_from_slice(b"PE\0\0");
        d[0x86..0x88].copy_from_slice(&1u16.to_le_bytes());
        d[0x94..0x96].copy_from_slice(&0xF0u16.to_le_bytes());
        d[0x98..0x9A].copy_from_slice(&0x20Bu16.to_le_bytes());
        d[0x98 + 108..0x98 + 112].copy_from_slice(&16u32.to_le_bytes());
        let s = 0x98 + 0xF0;
        d[s..s + 8].copy_from_slice(b".elf0\0\0\0");
        d[s + 8..s + 12].copy_from_slice(&(body.len() as u32).to_le_bytes());
        d[s + 12..s + 16].copy_from_slice(&rva.to_le_bytes());
        d[s + 16..s + 20].copy_from_slice(&(body.len() as u32).to_le_bytes());
        d[s + 20..s + 24].copy_from_slice(&0x400u32.to_le_bytes());
        d.extend_from_slice(body);
        d
    }

    /// An ELF64 with one loadable segment at 0 holding `body`.
    fn elf(body: &[u8]) -> Vec<u8> {
        let mut d = vec![0u8; 0x1000];
        d[..4].copy_from_slice(b"\x7fELF");
        d[4] = 2;
        d[5] = 1;
        d[0x10..0x12].copy_from_slice(&2u16.to_le_bytes());
        d[0x12..0x14].copy_from_slice(&0x3Eu16.to_le_bytes());
        d[0x20..0x28].copy_from_slice(&0x40u64.to_le_bytes());
        d[0x34..0x36].copy_from_slice(&64u16.to_le_bytes());
        d[0x36..0x38].copy_from_slice(&56u16.to_le_bytes());
        d[0x38..0x3A].copy_from_slice(&1u16.to_le_bytes());
        let p = 0x40;
        d[p..p + 4].copy_from_slice(&1u32.to_le_bytes());
        d[p + 4..p + 8].copy_from_slice(&5u32.to_le_bytes());
        d[p + 8..p + 16].copy_from_slice(&0x1000u64.to_le_bytes());
        d[p + 32..p + 40].copy_from_slice(&(body.len() as u64).to_le_bytes());
        d[p + 40..p + 48].copy_from_slice(&(body.len() as u64).to_le_bytes());
        d.extend_from_slice(body);
        d
    }

    fn function(name: &str, rva: u64) -> Function {
        Function { name: name.into(), rva, prologue: String::new(), status: Status::Verified }
    }

    #[test]
    fn finds_where_the_elf_lies_in_the_relinked_image() {
        assert_eq!(elf_base_rva(&pe(0x10000, &[0; 16])), Ok(0x10000));
        let mut renamed = pe(0x10000, &[0; 16]);
        let s = 0x98 + 0xF0;
        renamed[s..s + 8].copy_from_slice(b".text\0\0\0");
        assert!(elf_base_rva(&renamed).is_err());
    }

    #[test]
    fn keeps_only_functions_the_relinker_left_alone() {
        let original: Vec<u8> = (0..64u8).collect();
        let mut relinked = original.clone();
        relinked[40] ^= 0xFF; // the relinker rewrote one byte inside the second function
        let elf_data = elf(&original);
        let pe_data = pe(0x10000, &relinked);
        let elf_image = Image::parse(&elf_data).unwrap();
        let pe_image = Image::parse(&pe_data).unwrap();
        let functions = [
            RuntimeFunction { begin: 0, end: 32 },
            RuntimeFunction { begin: 32, end: 48 },
            RuntimeFunction { begin: 48, end: 64 },
        ];
        let keep = unchanged(&elf_image, &pe_image, 0x10000, &functions);
        assert_eq!(keep.into_iter().collect::<Vec<_>>(), vec![0, 48]);
        // At the wrong offset nothing matches.
        assert!(unchanged(&elf_image, &pe_image, 0x10010, &functions).is_empty());
    }

    #[test]
    fn the_new_manifest_keeps_verified_unchanged_functions_and_reads_back() {
        let mut testing = function("f_30", 0x30);
        testing.status = Status::Testing;
        let source = Manifest {
            build: "elf".into(),
            library: Some("C:/w/lib.dll".into()),
            module_offset: None,
            functions: vec![function("f_0", 0), function("f_20", 0x20), testing],
        };
        let keep: BTreeSet<u32> = [0, 0x30].into_iter().collect();
        let m = manifest_for(&source, &keep, "relinked", 0x10000);
        let back = Manifest::parse(&to_toml(&m)).unwrap();
        assert_eq!(back.build, "relinked");
        assert_eq!(back.module_offset, Some(0x10000));
        assert_eq!(back.library.as_deref(), Some("C:/w/lib.dll"));
        assert_eq!(back.functions.iter().map(|f| f.name.as_str()).collect::<Vec<_>>(), vec!["f_0"]);
    }
}
