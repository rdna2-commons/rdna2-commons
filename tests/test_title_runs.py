import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import title_runs as tr  # noqa: E402

C = "c" * 40
BUILDS = {"build-a": {}}


def run(**k):
    r = {"build": "build-a", "commit": C, "hw_class": "nvidia-ada", "os": "windows-11", "driver": "621.24",
         "stage": "menu", "fps": 30.0, "stop": "game.exe+0x2478440 access violation", "notes": "menus work"}
    r.update(k)
    return r


class Validate(unittest.TestCase):
    def test_good(self):
        self.assertEqual(tr.validate_run(run(), "build-a", C, BUILDS), [])
        self.assertEqual(tr.validate_run(run(stop="", fps=None), "build-a", C, BUILDS), [])
        self.assertEqual(tr.validate_run(run(stop="gpu hang after 5 s"), "build-a", C, BUILDS), [])

    def test_bad(self):
        self.assertTrue(tr.validate_run(run(stage="boots"), "build-a", C, BUILDS))
        self.assertTrue(tr.validate_run(run(build="build-b"), "build-a", C, BUILDS))
        self.assertTrue(tr.validate_run(run(), "build-a", "d" * 40, BUILDS))
        self.assertTrue(tr.validate_run(run(notes="x" * 600), "build-a", C, BUILDS))
        self.assertTrue(tr.validate_run(run(notes="dump " + "ab" * 40), "build-a", C, BUILDS))
        self.assertTrue(tr.validate_run(run(stop="Here Is A Quoted Line From The Title"), "build-a", C, BUILDS))
        self.assertTrue(tr.validate_run(dict(run(), extra=1), "build-a", C, BUILDS))

    def test_build(self):
        b = {"id": "build-a", "exe_sha256": "a" * 64, "exe_size": 10, "note": "console build"}
        self.assertEqual(tr.validate_build(b, "build-a"), [])
        self.assertTrue(tr.validate_build(dict(b, id="Build A"), "Build A"))
        self.assertTrue(tr.validate_build(dict(b, exe_sha256="x"), "build-a"))


class Confirm(unittest.TestCase):
    def test_second_best_is_confirmed(self):
        reports = [("a", run(stage="in-world")), ("b", run(stage="menu")), ("c", run(stage="first-frame")),
                   ("a", run(stage="loads"))]
        self.assertEqual(tr.confirmed(reports)[("build-a", C)], ("menu", "in-world"))

    def test_one_person_is_not_confirmation(self):
        reports = [("a", run(stage="in-world")), ("a", run(stage="playable"))]
        self.assertEqual(tr.confirmed(reports)[("build-a", C)], (None, "playable"))


if __name__ == "__main__":
    unittest.main()
