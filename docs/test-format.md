# Shared test format

A **case** is one small, hand-written RDNA2 program with its inputs and the exact output words it must produce.
Cases are format-neutral: any translator (to SPIR-V, DXIL, HLSL, or an interpreter) can run them.

Cases live in `cases/<group>/<name>.json`; `tools/cases.py` validates them and CI runs it on every pull request.
Never put anything taken from a game into a case: every program is written by hand for the test.

## Fields

| Field | Type | Meaning |
|---|---|---|
| `id` | string | `<group>/<name>`, equal to the file path without `cases/` and `.json` |
| `summary` | string | One sentence: what behaviour this pins down |
| `isa` | `"rdna2"` | Target instruction set |
| `wave` | 32 or 64 | Wave size the program assumes |
| `group` | [x, y, z] | Workgroup size; dispatch is always one workgroup |
| `sgpr` | {"s4": "0x...", ...} | User SGPR values, from s4 up; s0..s3 are reserved (below) |
| `source` | [string] | Assembly, one instruction per line, LLVM `gfx1030` syntax |
| `expect` | [string] | Output words, 32-bit hex, read from the output buffer from word 0 |
| `known` | [object] | Optional: documented divergences, each `{"hw_class", "when", "words", "note"}` |
| `provenance` | string | `original`, or the source and its licence for an adapted case |

## Conventions every runner provides

- `s[0:3]` holds a buffer resource descriptor for the output buffer, zero-filled, 256 bytes.
- User SGPRs from `sgpr` are loaded starting at `s4`, in register order.
- Output words are read back from the start of the buffer and compared with `expect`, word by word.
- A run whose words match a `known` entry for its hardware class is reported as **known**, not as a pass:
  it documents a real divergence that a translator should avoid (for example with a stricter instruction).

## Example

```json
{
  "id": "valu-f32/add-basic",
  "summary": "v_add_f32 of 1.5 and 2.25 is 3.75",
  "isa": "rdna2",
  "wave": 32,
  "group": [1, 1, 1],
  "sgpr": {},
  "source": [
    "v_mov_b32 v0, 0x3fc00000",
    "v_add_f32 v1, 0x40100000, v0",
    "v_mov_b32 v2, 0",
    "buffer_store_dword v1, v2, s[0:3], 0 offen",
    "s_endpgm"
  ],
  "expect": ["0x40700000"],
  "known": [],
  "provenance": "original"
}
```
