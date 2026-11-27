import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import local_analyze as la  # noqa: E402


class Scrub(unittest.TestCase):
    def test_gdk_keeps_names_and_counts_only(self):
        report = {"images": [{"thunks": 12, "helpers": ["x 0x1000"], "unreached_classes": ["XGameUi", "bad name!"],
                              "classes": [
                                  {"class": "XUser", "class_id": "{abc}", "served": True, "thunks": 3,
                                   "interfaces": {"i1": {"slots": {"5": {"name": "XUserAddAsync", "thunk_rvas": {"0x1": 1}},
                                                                   "6": {"name": None}}}}},
                                  {"class": "XStore", "served": False, "thunks": 1, "interfaces": {}}]}]}
        out = la.scrub_gdk(report)
        self.assertEqual(out[0]["thunks"], 12)
        self.assertEqual(out[0]["unreached_classes"], ["XGameUi"])
        user = next(c for c in out[0]["classes"] if c["class"] == "XUser")
        self.assertEqual((user["slots_called"], user["slot_names"]), (2, ["XUserAddAsync"]))
        self.assertNotIn("0x", str(out))
        self.assertNotIn("helpers", str(out))

    def test_cpu_drops_sites(self):
        r = {"instructions": 100, "features": {"SSE4A": {"class": "amd-only", "total": 3,
                                                         "sites": [{"rva": 4096}]}}}
        self.assertEqual(la.scrub_cpu(r), {"instructions": 100, "features": {"SSE4A": {"class": "amd-only", "total": 3}}})

    def test_census_drops_addresses(self):
        r = {"pdata_functions": 10, "insns": 500, "image_base": "0x140000000", "file": "game.exe",
             "unhandled": [["vpermq", 4], ["bad mnem!", 1]], "worst_functions": [{"rva": "0x10"}],
             "indirect_control_flow": {"call_reg": 3}}
        out = la.scrub_census(r)
        self.assertEqual(out["unhandled"], [["vpermq", 4]])
        self.assertNotIn("image_base", out)
        self.assertNotIn("worst_functions", out)
        self.assertNotIn("game.exe", str(out))

    def test_dry_run(self):
        text = ("game.exe   base=0000 size=1 entry=+0x10  shim=2 host=3 module=0 unimplemented=2\n"
                "    UNIMPLEMENTED xgameruntime.dll!XFooBar  [returns HRESULT]\n"
                "    UNIMPLEMENTED KERNELX.dll!SomeCall\n"
                "    SHIM          kernelx.dll!VirtualAlloc\n"
                "3 module(s) mapped, 2 unimplemented import(s)\n")
        out = la.scrub_dry_run(text)
        self.assertEqual(out["unimplemented"], {"kernelx.dll": ["SomeCall"], "xgameruntime.dll": ["XFooBar"]})
        self.assertEqual(out["shimmed_count"], 1)

    def test_markdown(self):
        needs = {"imports": {"unimplemented": {"kernelx.dll": ["A", "B"]}, "shimmed_count": 1},
                 "gdk": [{"thunks": 1, "classes": [{"class": "XStore", "served": False, "thunks": 1,
                                                    "slots_called": 4, "slot_names": []}], "unreached_classes": []}],
                 "cpu": {"instructions": 1, "features": {"SSE4A": {"class": "amd-only", "total": 3}}},
                 "census": {"pdata_functions": 10, "insns": 5, "insn_coverage_pct": 50.0, "unhandled": [["vpermq", 4]]}}
        md = la.markdown(needs)
        self.assertIn("## Unimplemented imports: 2", md)
        self.assertIn("- `XStore`: 4 slot(s)", md)
        self.assertIn("- `SSE4A` (amd-only): 3", md)
        self.assertIn("`vpermq` 4", md)


if __name__ == "__main__":
    unittest.main()
