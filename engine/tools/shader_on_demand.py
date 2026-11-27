"""Translate one compute DXBC/FSSM container into a reusable shader-library entry.

    python -I tools/shader_on_demand.py shader.dxbc --cache <local cache>

Prints a JSON object with the absolute shader-library directory and whether it
was already cached. Cold translations need spirv-val on PATH.
"""

import argparse
from dataclasses import dataclass
from functools import cache
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zlib

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))  # python -I

import fssm_unpack
import shader_disasm

STEM = "cs_shader"


class ShaderCompileError(Exception):
    """The worker could not produce or read a complete shader-library entry."""


@dataclass(frozen=True)
class CompileResult:
    directory: Path
    cache_hit: bool


@cache
def _tool_fingerprint() -> bytes:
    # The decoder, translator, assembler and metadata writers live alongside this worker. Include their sources
    # so a cache from an older checkout cannot select an obsolete module or runtime metadata.
    version = hashlib.sha256()
    for path in sorted(TOOLS.glob("*.py")):
        version.update(path.name.encode("utf-8") + b"\0")
        version.update(hashlib.sha256(path.read_bytes()).digest())
    return version.digest()


def cache_key(bytecode: bytes) -> str:
    digest = hashlib.sha256(_tool_fingerprint())
    digest.update(bytecode)
    return digest.hexdigest()


def _compute_fssm(bytecode: bytes) -> bytes:
    try:
        if bytecode[:4] != b"DXBC":
            raise ValueError("missing DXBC magic")
        dxil = fssm_unpack.parts(bytecode).get(b"DXIL", b"")
        # The DXIL version word precedes the u16 shader kind (5 for compute).
        if len(dxil) < 4 or struct.unpack_from("<H", dxil, 2)[0] != 5:
            raise ValueError("expected a compute DXBC container")
        native, _ = fssm_unpack.unpack(bytecode)
        if not native:
            raise ValueError("compute shader has no FSSM payload")
        return native
    except (ValueError, struct.error, zlib.error) as error:
        raise ShaderCompileError(str(error)) from error


def _entry(directory: Path) -> tuple[dict, str]:
    with (directory / "index.json").open(encoding="utf-8") as source:
        index = json.load(source)
    if not isinstance(index, dict) or set(index) != {STEM}:
        raise ValueError("index must contain exactly one compute shader")
    metadata = index[STEM]
    if (not isinstance(metadata, dict) or metadata.get("stage") != "cs"
            or not isinstance(metadata.get("fssm_sha256"), str)):
        raise ValueError("missing compute stage or FSSM hash")
    module = (directory / f"{STEM}.spv").read_bytes()
    if len(module) < 20 or len(module) % 4 or module[:4] != b"\x03\x02\x23\x07":
        raise ValueError("invalid SPIR-V framing")
    return index, hashlib.sha256(module).hexdigest()


def _index_checksum(index: dict) -> str:
    return hashlib.sha256(json.dumps(index, sort_keys=True).encode("utf-8")).hexdigest()


def _require_cached(directory: Path, key: str) -> CompileResult:
    try:
        index, digest = _entry(directory)
        metadata = index[STEM]
        index_digest = metadata.pop("on_demand_index_sha256", None)
        if (metadata.get("on_demand_key") != key or metadata.get("on_demand_spirv_sha256") != digest
                or index_digest != _index_checksum(index)):
            raise ValueError("cache key, metadata or module digest mismatch")
    except (OSError, ValueError) as error:
        raise ShaderCompileError(f"invalid cached shader at {directory}: {error}") from error
    return CompileResult(directory, cache_hit=True)


def translate_compute(bytecode: bytes, native: bytes, out: Path) -> None:
    source = out.parent / "source"
    disasm, fssm = source / "disasm", source / "fssm"
    disasm.mkdir(parents=True)
    fssm.mkdir()
    (source / f"{STEM}.dxbc").write_bytes(bytecode)
    native_path = fssm / f"{STEM}.fssm"
    native_path.write_bytes(native)
    status = shader_disasm.one(str(native_path), str(disasm), "gfx1013", backend="python")
    if status not in ("clean", "invalid words"):
        raise ShaderCompileError(f"disassembly failed: {status}")
    result = subprocess.run(
        [sys.executable, "-I", str(TOOLS / "rdna2spirv.py"), str(disasm / f"{STEM}.s"), "--out", str(out),
         "--fssm-dir", str(fssm), "--assembler", "python", "--no-asm"],
        capture_output=True, text=True, errors="replace",
    )
    if result.returncode or not (out / f"{STEM}.spv").is_file():
        diagnostic = "\n".join(message for message in (result.stdout.strip(), result.stderr.strip()) if message)
        raise ShaderCompileError(f"translation failed: {diagnostic or f'exit code {result.returncode}'}")


def compile_cached(bytecode: bytes, cache: Path, *, translate=translate_compute) -> CompileResult:
    """Return a complete cached library, building it in a private sibling directory on a miss."""
    cache = cache.resolve()
    key = cache_key(bytecode)
    destination = cache / key
    if destination.exists():
        return _require_cached(destination, key)

    native = _compute_fssm(bytecode)
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".shader-", dir=cache) as work:
        output = Path(work) / "spirv"
        output.mkdir()
        translate(bytecode, native, output)
        try:
            index, digest = _entry(output)
            metadata = index[STEM]
            if metadata["fssm_sha256"] != hashlib.sha256(native).hexdigest():
                raise ValueError("FSSM hash does not match the input")
        except (OSError, ValueError) as error:
            raise ShaderCompileError(f"incomplete translation: {error}") from error
        metadata["on_demand_key"] = key
        metadata["on_demand_spirv_sha256"] = digest
        metadata["on_demand_index_sha256"] = _index_checksum(index)
        (output / "index.json").write_text(json.dumps(index) + "\n", encoding="utf-8")
        try:
            # Both artifacts become visible under their final name together, on the same filesystem.
            output.rename(destination)
        except OSError:
            if not destination.exists():
                raise
            # Another process may have published the same request while this one translated it.
            return _require_cached(destination, key)
    return CompileResult(destination, cache_hit=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("shader", type=Path)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = compile_cached(args.shader.read_bytes(), args.cache)
    except (OSError, ShaderCompileError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"directory": str(result.directory), "cache_hit": result.cache_hit}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
