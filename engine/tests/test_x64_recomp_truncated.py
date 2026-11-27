"""tools/x64_recomp.py: a VEX/EVEX prefix that runs into the end of the buffer is a DecodeError, not an IndexError.

Found by tools/local_analyze.py: recomp_census.py stopped on the last bytes of a section that ended in a VEX
prefix. Hand-written bytes only.

    python -I tests/test_x64_recomp_truncated.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import x64_recomp  # noqa: E402


class Truncated(unittest.TestCase):
    def check(self, data):
        with self.assertRaises(x64_recomp.DecodeError):
            x64_recomp.decode_one(bytes(data), 0, len(data), 0x1000)

    def test_two_byte_vex_at_the_end(self):
        self.check([0xC5, 0xF8])            # vex2 prefix, no opcode

    def test_three_byte_vex_cut(self):
        self.check([0xC4, 0xE2])            # vex3 missing its third byte
        self.check([0xC4, 0xE2, 0x79])      # vex3 prefix, no opcode

    def test_evex_at_the_end(self):
        self.check([0x62, 0xF1, 0x7C, 0x48])  # evex prefix, no opcode


if __name__ == "__main__":
    unittest.main()
