import io
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bot"))


class DryRun(unittest.TestCase):
    def load(self, dry):
        env = {"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": "o/r"}
        if dry:
            env["COMMONS_DRY_RUN"] = "1"
        with mock.patch.dict(os.environ, env, clear=False):
            if not dry:
                os.environ.pop("COMMONS_DRY_RUN", None)
            sys.modules.pop("main", None)
            import main
        return main

    def fake_urlopen(self, sent):
        class Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def urlopen(req, timeout=None):
            sent.append((req.get_method(), req.full_url, json.loads(req.data) if req.data else None))
            return Resp(b"{}")
        return urlopen

    def test_dry_run_changes_nothing_but_comments(self):
        main = self.load(True)
        sent = []
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "t"}), \
                mock.patch("urllib.request.urlopen", self.fake_urlopen(sent)), \
                mock.patch("sys.stdout", io.StringIO()):
            main.add_label(5, "rejected")
            main.call("PATCH", "/repos/o/r/pulls/5", {"state": "closed"})
            main.call("PUT", "/repos/o/r/pulls/5/merge", {})
            self.assertEqual(main.call("POST", "/repos/o/r/issues", {"title": "x"}), {"number": 0})
            main.comment(5, "Closing: reasons")
            main.call("GET", "/repos/o/r/pulls/5")
        self.assertEqual([m for m, _, _ in sent], ["POST", "GET"])
        self.assertTrue(sent[0][1].endswith("/issues/5/comments"))
        self.assertIn("Dry run", sent[0][2]["body"])
        self.assertEqual(len(main.DRY_LOG), 4)

    def test_normal_mode_acts(self):
        main = self.load(False)
        sent = []
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "t"}), \
                mock.patch("urllib.request.urlopen", self.fake_urlopen(sent)):
            main.call("PATCH", "/repos/o/r/pulls/5", {"state": "closed"})
            main.comment(5, "hi")
        self.assertEqual([m for m, _, _ in sent], ["PATCH", "POST"])
        self.assertNotIn("Dry run", sent[1][2]["body"])


if __name__ == "__main__":
    unittest.main()
