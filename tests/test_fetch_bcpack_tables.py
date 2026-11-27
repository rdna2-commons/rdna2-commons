import io
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import fetch_bcpack_tables as f  # noqa: E402


class Fetch(unittest.TestCase):
    def test_the_url_is_pinned_to_a_commit(self):
        self.assertIn(f.COMMIT, f.url())
        self.assertTrue(f.url().endswith(f.PATH))
        self.assertEqual(len(f.COMMIT), 40)

    def test_anything_but_the_pinned_file_is_refused(self):
        self.assertIn("bytes", f.check(b"x"))
        self.assertIn("SHA-256", f.check(b"\0" * f.SIZE))

    def test_a_bad_download_writes_nothing(self):
        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        data = f.fetch(opener=lambda req, timeout: Response(b"\0" * f.SIZE))
        self.assertIsNotNone(f.check(data))

    def test_the_request_names_the_project(self):
        seen = []

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def opener(req, timeout):
            seen.append(req.get_header("User-agent"))
            return Response(b"")

        f.fetch(opener=opener)
        self.assertEqual(seen, ["rdna2-commons-fetch"])
        with tempfile.TemporaryDirectory() as d:
            original = f.fetch
            f.fetch = lambda: data
            try:
                self.assertEqual(f.main(["--out", d]), 1)
            finally:
                f.fetch = original
            self.assertFalse(os.path.exists(os.path.join(d, f.NAME)))


if __name__ == "__main__":
    unittest.main()
