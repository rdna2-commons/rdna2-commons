import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import try_prs  # noqa: E402


def g(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)


class TryPrs(unittest.TestCase):
    """An origin with three PR refs: #1 adds a.txt, #2 adds b.txt, #3 conflicts with #1, #4 breaks the test."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.origin = os.path.join(self.tmp, "origin")
        os.makedirs(self.origin)
        o = self.origin
        g(o, "init", "-q", "-b", "main")
        g(o, "config", "user.email", "t@t")
        g(o, "config", "user.name", "t")
        self.write("ok", "1")
        g(o, "add", "-A")
        g(o, "commit", "-qm", "base")
        for n, (path, text) in {1: ("a.txt", "a"), 2: ("b.txt", "b"), 3: ("a.txt", "other"), 4: ("ok", "0")}.items():
            g(o, "switch", "-q", "-c", f"pr{n}", "main")
            self.write(path, text)
            g(o, "add", "-A")
            g(o, "commit", "-qm", f"pr {n}")
            g(o, "update-ref", f"refs/pull/{n}/head", f"pr{n}")
            g(o, "switch", "-q", "main")
        self.clone = os.path.join(self.tmp, "clone")
        g(self.tmp, "clone", "-q", self.origin, self.clone)
        self.test = f'"{sys.executable}" -c "import sys; sys.exit(0 if open(\'ok\').read() == \'1\' else 1)"'

    def write(self, path, text):
        with open(os.path.join(self.origin, path), "w") as f:
            f.write(text)

    def test_alone_and_stacked(self):
        base_ok, rows, stacked, stack_ok, _ = try_prs.try_prs(self.clone, "origin", "main", [1, 2, 3, 99],
                                                             self.test, 60)
        self.assertTrue(base_ok)
        self.assertTrue(rows[1]["merges"] and rows[1]["alone"])
        self.assertTrue(rows[2]["alone"])
        self.assertTrue(rows[3]["alone"])          # #3 is fine alone...
        self.assertEqual(stacked, [1, 2])          # ...but conflicts with #1 in the stack
        self.assertFalse(rows[3]["in_stack"])
        self.assertTrue(stack_ok)
        self.assertFalse(rows[99]["fetch"])
        text = try_prs.table("main", base_ok, rows, stacked, stack_ok, "t")
        self.assertIn("| #3 | yes | yes | **no** |", text)
        self.assertIn("could not fetch", text)

    def test_breaking_pr(self):
        _, rows, stacked, stack_ok, _ = try_prs.try_prs(self.clone, "origin", "main", [1, 4], self.test, 60)
        self.assertFalse(rows[4]["alone"])
        self.assertEqual(stacked, [1, 4])
        self.assertFalse(stack_ok)


if __name__ == "__main__":
    unittest.main()
