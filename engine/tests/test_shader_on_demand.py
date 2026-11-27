"""One source-built compute shader through the on-demand worker and its cache."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
sys.path[:0] = [str(TOOLS), str(HERE)]  # also run by the stdlib job with python -I

import shader_on_demand
from test_fssm_unpack import make_dxbc, make_xbch, make_xdat


def shader(group_x=4, stage=5):
    native = bytearray(0x148)
    native[:6] = b"FSSM\x01\x01"
    struct.pack_into("<I", native, 0xC0, 0x120)  # instructions start 0x28 bytes into the code section
    struct.pack_into("<I", native, 0xD4, 0x20)  # wave32
    struct.pack_into("<4I", native, 0x138, 8, group_x, 1, 1)  # four user SGPRs for the output V#
    # v_cmpx_eq_u32 0, v0; v_mov_b32 v1, 42; buffer_store_dword v1, off, s[0:3], 0; s_endpgm
    native.extend(bytes.fromhex("8000a47d aa02027e 000070e000010080 000081bf"))
    native = bytes(native)
    dxil = make_xdat({0x0D: make_xbch(native)}, pre_padding=struct.pack("<HH", 0x66, stage))
    return make_dxbc([(b"DXIL", dxil)]), native


def translator_artifacts(_bytecode, native, out):
    # Stand-in only for cache tests. The separate CLI test uses the real worker and validates its output.
    module = struct.pack("<5I", 0x07230203, 0x00010500, 0, 1, 0)
    (out / "cs_shader.spv").write_bytes(module)
    (out / "index.json").write_text(json.dumps({"cs_shader": {
        "stage": "cs", "fssm_sha256": hashlib.sha256(native).hexdigest(),
    }}), encoding="utf-8")


class ShaderOnDemand(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.cache = self.root / "cache"
        self.bytecode, self.native = shader()

    def unexpected_translation(self, *_args):
        self.fail("a warm request invoked the translator")

    def test_content_key_uses_bytecode_and_a_warm_hit_skips_translation(self):
        first = shader_on_demand.compile_cached(self.bytecode, self.cache, translate=translator_artifacts)
        self.assertFalse(first.cache_hit)
        hit = shader_on_demand.compile_cached(self.bytecode, self.cache, translate=self.unexpected_translation)
        self.assertTrue(hit.cache_hit)
        self.assertEqual(hit.directory, first.directory)

        # Changing container metadata must invalidate even when the native FSSM bytes remain identical.
        changed = bytearray(self.bytecode)
        changed[4] ^= 1
        different = shader_on_demand.compile_cached(bytes(changed), self.cache, translate=translator_artifacts)
        self.assertFalse(different.cache_hit)
        self.assertNotEqual(different.directory, first.directory)

    def test_failed_output_is_not_visible_and_can_be_retried(self):
        def writes_partial_output(_bytecode, _native, out):
            (out / "cs_shader.spv").write_bytes(b"interrupted")
            self.assertEqual(list(self.cache.glob("*/index.json")), [])

        with self.assertRaises(shader_on_demand.ShaderCompileError):
            shader_on_demand.compile_cached(self.bytecode, self.cache, translate=writes_partial_output)
        self.assertEqual(list(self.cache.iterdir()), [])
        retry = shader_on_demand.compile_cached(self.bytecode, self.cache, translate=translator_artifacts)
        self.assertFalse(retry.cache_hit)
        self.assertTrue((retry.directory / "index.json").is_file())

    def test_mismatched_metadata_or_noncompute_input_is_refused(self):
        def writes_wrong_metadata(bytecode, _native, out):
            translator_artifacts(bytecode, b"another program", out)

        with self.assertRaises(shader_on_demand.ShaderCompileError):
            shader_on_demand.compile_cached(self.bytecode, self.cache, translate=writes_wrong_metadata)
        noncompute, _ = shader(stage=0)
        with self.assertRaisesRegex(shader_on_demand.ShaderCompileError, "compute DXBC"):
            shader_on_demand.compile_cached(noncompute, self.cache, translate=self.unexpected_translation)
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_corrupted_module_is_refused_even_when_its_framing_is_intact(self):
        first = shader_on_demand.compile_cached(self.bytecode, self.cache, translate=translator_artifacts)
        module = first.directory / "cs_shader.spv"
        changed = bytearray(module.read_bytes())
        changed[8] ^= 1
        module.write_bytes(changed)
        with self.assertRaisesRegex(shader_on_demand.ShaderCompileError, "cached shader"):
            shader_on_demand.compile_cached(self.bytecode, self.cache, translate=self.unexpected_translation)

    def test_corrupted_metadata_is_refused_even_when_its_json_is_valid(self):
        first = shader_on_demand.compile_cached(self.bytecode, self.cache, translate=translator_artifacts)
        metadata = first.directory / "index.json"
        changed = json.loads(metadata.read_bytes())
        changed["cs_shader"]["local_size"] = [1024, 1024, 1024]
        metadata.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaisesRegex(shader_on_demand.ShaderCompileError, "cached shader"):
            shader_on_demand.compile_cached(self.bytecode, self.cache, translate=self.unexpected_translation)

    def test_concurrent_publication_returns_one_complete_entry(self):
        both_compiling = threading.Barrier(2, timeout=10)

        def concurrent_translation(bytecode, native, out):
            translator_artifacts(bytecode, native, out)
            both_compiling.wait()

        def compile_one():
            return shader_on_demand.compile_cached(self.bytecode, self.cache, translate=concurrent_translation)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: compile_one(), range(2)))
        self.assertEqual(results[0].directory, results[1].directory)
        self.assertEqual(sorted(result.cache_hit for result in results), [False, True])
        published = list(self.cache.iterdir())
        self.assertEqual(len(published), 1)
        self.assertTrue(published[0].samefile(results[0].directory))
        self.assertEqual(sorted(p.name for p in results[0].directory.iterdir()), ["cs_shader.spv", "index.json"])

    @unittest.skipUnless(shutil.which("spirv-val"), "the real worker requires spirv-val")
    def test_cli_translates_real_source_built_dxbc_and_serves_a_warm_hit(self):
        source = self.root / "synthetic.dxbc"
        source.write_bytes(self.bytecode)
        cli = [sys.executable, "-I", str(TOOLS / "shader_on_demand.py"), str(source), "--cache", str(self.cache)]
        cold = subprocess.run(cli, capture_output=True, text=True, check=True)
        result = json.loads(cold.stdout)
        self.assertFalse(result["cache_hit"])
        directory = Path(result["directory"])
        entry = json.loads((directory / "index.json").read_bytes())["cs_shader"]
        self.assertEqual(entry["fssm_sha256"], hashlib.sha256(self.native).hexdigest())
        self.assertEqual(entry["stage"], "cs")
        self.assertEqual(entry["local_size"], [4, 1, 1])
        subprocess.run(["spirv-val", "--target-env", "vulkan1.3", str(directory / "cs_shader.spv")], check=True)
        # The worker can serve the warm module even when the validator for a cold translation is off PATH.
        no_validator = self.root / "empty-path"
        no_validator.mkdir()
        warm = subprocess.run(cli, capture_output=True, text=True, check=True,
                              env={**os.environ, "PATH": str(no_validator)})
        self.assertEqual(json.loads(warm.stdout), {**result, "cache_hit": True})

    def test_cli_refuses_an_unsupported_shader_without_publishing(self):
        source = self.root / "synthetic.dxbc"
        source.write_bytes(shader(group_x=0)[0])
        result = subprocess.run(
            [sys.executable, "-I", str(TOOLS / "shader_on_demand.py"), str(source), "--cache", str(self.cache)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("CS group size", result.stderr)
        self.assertEqual(list(self.cache.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
