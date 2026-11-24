import copy
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import cases  # noqa: E402

GOOD = {"id": "g/n", "summary": "a summary long enough", "isa": "rdna2", "wave": 32, "group": [1, 1, 1],
        "sgpr": {"s4": "0x00000001"}, "source": ["v_mov_b32 v0, s4", "s_endpgm"], "expect": ["0x00000001"],
        "known": [], "provenance": "original"}


def bad(**changes):
    c = copy.deepcopy(GOOD)
    for k, v in changes.items():
        if v is None:
            del c[k]
        else:
            c[k] = v
    return cases.validate(c, "g/n")


class Validate(unittest.TestCase):
    def test_good(self):
        self.assertEqual(cases.validate(GOOD, "g/n"), [])

    def test_problems(self):
        self.assertTrue(bad(id="x/y"))
        self.assertTrue(bad(wave=16))
        self.assertTrue(bad(wave=True))
        self.assertTrue(bad(group=[2048, 1, 1]))
        self.assertTrue(bad(sgpr={"s0": "0x00000000"}))
        self.assertTrue(bad(sgpr={"s4": "0x1"}))
        self.assertTrue(bad(sgpr={"s5": "0x00000000"}))
        self.assertTrue(bad(source=["v_nop"]))
        self.assertTrue(bad(expect=["0xABCDEF01"]))
        self.assertTrue(bad(expect=[]))
        self.assertTrue(bad(provenance=None))
        self.assertTrue(bad(extra="x"))
        self.assertTrue(bad(known=[{"hw_class": "x", "when": "y", "words": [], "note": "z"}]))

    def test_repository_cases_are_valid(self):
        found, problems = cases.load_all(os.path.join(ROOT, "cases"))
        self.assertEqual(problems, [])
        self.assertGreaterEqual(len(found), 3)

    def test_non_json_and_guard(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "g"))
            with open(os.path.join(d, "g", "x.spv"), "wb") as f:
                f.write(b"\x03\x02\x23\x07")
            _, problems = cases.load_all(d)
            self.assertTrue(any("only .json" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
