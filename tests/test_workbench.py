import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import workbench  # noqa: E402


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


class Workbench(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = temp.name
        self.source = os.path.join(self.root, "run")
        self.repo = os.path.join(self.root, "bench")

    def tracked(self):
        out = subprocess.run(["git", "-C", self.repo, "ls-files"], capture_output=True, text=True, check=True)
        return sorted(out.stdout.split())

    def test_saves_allowed_scripts_and_skips_other_files(self):
        write(os.path.join(self.source, "bench.ps1"), b"Write-Output 1\n")
        write(os.path.join(self.source, "tools", "score.py"), b"print(1)\n")
        write(os.path.join(self.source, "run.log"), b"a log\n")
        write(os.path.join(self.source, "frame.png"), b"\x89PNG\r\n")
        write(os.path.join(self.source, "a", "b", "c", "deep.py"), b"print(2)\n")
        copied, refused = workbench.save(self.repo, [self.source])
        self.assertEqual((copied, refused), (2, []))
        self.assertEqual(self.tracked(), ["run/bench.ps1", "run/tools/score.py"])
        branch = subprocess.run(["git", "-C", self.repo, "branch", "--show-current"], capture_output=True, text=True)
        self.assertEqual(branch.stdout.strip(), "workbench")

    def test_refuses_secrets_binaries_and_large_files(self):
        write(os.path.join(self.source, "token.ps1"), b"$t = 'ghp_" + b"a" * 36 + b"'\n")
        write(os.path.join(self.source, "key.md"), b"-----BEGIN OPENSSH PRIVATE KEY-----\n")
        write(os.path.join(self.source, "blob.py"), b"\0\1\2")
        write(os.path.join(self.source, "big.md"), b"x" * (workbench.MAX_BYTES + 1))
        write(os.path.join(self.source, "ok.sh"), b"echo ok\n")
        copied, refused = workbench.save(self.repo, [self.source])
        self.assertEqual(copied, 1)
        self.assertEqual(sorted(os.path.basename(p) for p, _ in refused), ["big.md", "blob.py", "key.md", "token.ps1"])
        self.assertEqual(self.tracked(), ["run/ok.sh"])

    def test_a_file_that_turns_secret_is_removed_from_the_next_commit(self):
        path = os.path.join(self.source, "env.ps1")
        write(path, b"$x = 1\n")
        workbench.save(self.repo, [self.source])
        write(path, b"$password = 'hunter2hunter2'\n")
        copied, refused = workbench.save(self.repo, [self.source])
        self.assertEqual((copied, len(refused)), (0, 1))
        self.assertEqual(self.tracked(), [])

    def test_refuses_a_repository_with_a_remote(self):
        os.makedirs(self.repo)
        subprocess.run(["git", "-C", self.repo, "init", "-q"], check=True)
        subprocess.run(["git", "-C", self.repo, "remote", "add", "origin", "https://example.invalid/x.git"], check=True)
        write(os.path.join(self.source, "a.py"), b"print(1)\n")
        with self.assertRaises(SystemExit):
            workbench.save(self.repo, [self.source])


if __name__ == "__main__":
    unittest.main()
