import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import scan_history  # noqa: E402


def g(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class ScanHistory(unittest.TestCase):
    def test_deleted_file_is_still_found(self):
        with tempfile.TemporaryDirectory() as d:
            g(d, "init", "-q")
            g(d, "config", "user.email", "t@t")
            g(d, "config", "user.name", "t")
            with open(os.path.join(d, "a.txt"), "w") as f:
                f.write("fine\n")
            g(d, "add", "-A")
            g(d, "commit", "-qm", "base")
            base = g(d, "rev-parse", "HEAD")
            with open(os.path.join(d, "x.rpf"), "wb") as f:
                f.write(b"data")
            g(d, "add", "-A")
            g(d, "commit", "-qm", "add")
            os.remove(os.path.join(d, "x.rpf"))
            g(d, "add", "-A")
            g(d, "commit", "-qm", "remove")
            n, flagged = scan_history.scan(d, "HEAD")
            self.assertTrue(any("x.rpf" in f for f in flagged))
            n, flagged = scan_history.scan(d, "HEAD", "HEAD")
            self.assertEqual((n, flagged), (0, []))
            n, flagged = scan_history.scan(d, base)
            self.assertEqual(flagged, [])


if __name__ == "__main__":
    unittest.main()
