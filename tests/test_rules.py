import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bot"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_build  # noqa: E402
import results  # noqa: E402
import rules  # noqa: E402

BODY = "Closes #7\n\nProvenance:\n- original\n"
SIGNED = "Fix it\n\nSigned-off-by: A <a@example.com>"


def pr(body=BODY, author="alice", labels=(), size=10, number=20):
    return {"number": number, "author": author, "body": body, "labels": list(labels), "additions": size,
            "deletions": 0}


TASK = {"number": 7, "assignees": ["alice"], "labels": ["task", "ready"], "state": "open"}


class FileChecks(unittest.TestCase):
    def test_source_ok(self):
        self.assertIsNone(rules.check_file("src/a.rs", b"fn main() {}\n"))

    def test_blocked_extension(self):
        self.assertIn(".rpf", rules.check_file("x/data.rpf", b"text"))
        self.assertIn(".spv", rules.check_file("tests/a.spv", b"text"))

    def test_magic_in_innocent_name(self):
        self.assertIn("PE executable", rules.check_file("src/notes.txt", b"MZ\x90\x00" + b"\0" * 64))
        self.assertIn("SPIR-V", rules.check_file("docs/a.md", b"\x03\x02\x23\x07rest"))
        self.assertIn("zlib", rules.check_file("tests/x.txt", b"\x78\x9cabc"))

    def test_binary_outside_images(self):
        self.assertIn("binary", rules.check_file("tests/blob", b"\x01\x02\x00\xff" * 10))

    def test_image_allowed_and_capped(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\0" * 100
        self.assertIsNone(rules.check_file("docs/images/a.png", png))
        self.assertIn("KiB", rules.check_file("docs/images/a.png", png + b"\0" * rules.MAX_IMAGE_BYTES))
        webp = b"RIFF\0\0\0\0WEBPVP8 " + b"\0" * 20
        self.assertIsNone(rules.check_file("docs/images/a.webp", webp))
        self.assertIn("RIFF", rules.check_file("docs/images/a.webp", b"RIFF\0\0\0\0WAVEfmt "))

    def test_smuggled_base64_and_arrays(self):
        import base64
        blob = base64.b64encode(os.urandom(6000))
        self.assertIn("encoded blob", rules.check_file("src/a.rs", b"const X: &str = \"" + blob + b"\";"))
        arr = b", ".join(b"0x%02x" % (i % 256) for i in range(5000))
        self.assertIn("byte array", rules.check_file("src/a.c", b"char x[] = {" + arr + b"};"))

    def test_long_text_without_blob_ok(self):
        self.assertIsNone(rules.check_file("docs/a.md", b"word " * 20000))


class Gate(unittest.TestCase):
    def run_gate(self, p=None, files=(("src/a.rs", b"x"), ("tests/t.rs", b"y")), task=TASK, others=(),
                 commits=(SIGNED,)):
        return rules.gate(p or pr(), list(files), task, list(others), list(commits))

    def test_clean(self):
        self.assertEqual(self.run_gate(), ([], []))

    def test_no_task(self):
        hard, _ = self.run_gate(pr(body="Provenance:\n- original\n"))
        self.assertTrue(any("Closes" in h for h in hard))

    def test_task_not_assigned(self):
        hard, _ = self.run_gate(pr(author="bob"))
        self.assertTrue(any("not assigned" in h for h in hard))

    def test_duplicate_later_pr_closed(self):
        hard, _ = self.run_gate(others=[{"number": 5, "body": "Closes #7"}])
        self.assertTrue(any("#5 already" in h for h in hard))
        hard, _ = self.run_gate(others=[{"number": 30, "body": "Closes #7"}])
        self.assertEqual(hard, [])

    def test_provenance(self):
        hard, _ = self.run_gate(pr(body="Closes #7\n"))
        self.assertTrue(any("Provenance" in h for h in hard))
        body = "Closes #7\nProvenance:\n- https://github.com/x/y (GPL-2.0-only): a.rs\n"
        hard, _ = self.run_gate(pr(body=body))
        self.assertTrue(any("GPL-2.0-only" in h for h in hard))
        body = "Closes #7\nProvenance:\n- https://github.com/x/y (MIT): a.rs\n- original\n"
        self.assertEqual(self.run_gate(pr(body=body))[0], [])

    def test_provenance_footer_is_not_an_item(self):
        body = "Closes #7\n\nProvenance:\n- original\n\nGenerated with some tool\n"
        self.assertEqual(self.run_gate(pr(body=body))[0], [])
        body = "Closes #7\nProvenance:\n- original\n- https://x/y (GPL-2.0-only): a\nfooter"
        self.assertTrue(any("GPL-2.0-only" in h for h in self.run_gate(pr(body=body))[0]))

    def test_engine_code_needs_an_engine_test(self):
        _, soft = self.run_gate(files=[("engine/runtime/shims/x.cpp", b"int x;\n")])
        self.assertTrue(any("engine code" in m for m in soft))
        for test in ("engine/runtime/test/x_test.cpp", "engine/tests/test_x.py"):
            _, soft = self.run_gate(files=[("engine/runtime/shims/x.cpp", b"int x;\n"), (test, b"t\n")])
            self.assertFalse(any("engine code" in m for m in soft))
        _, soft = self.run_gate(files=[("engine/runtime/README.md", b"doc\n")])
        self.assertFalse(any("engine code" in m for m in soft))

    def test_soft_rules(self):
        _, soft = self.run_gate(files=[("src/a.rs", b"x")], commits=["no sign-off"], p=pr(size=2000))
        self.assertEqual(len(soft), 3)
        _, soft = self.run_gate(p=pr(size=2000, labels=["large"]))
        self.assertEqual(soft, [])

    def test_result_report_named_after_author(self):
        hard, _ = self.run_gate(files=[("results/t/c/bob.json", b"{}")])
        self.assertTrue(any("named after" in h for h in hard))
        self.assertEqual(self.run_gate(files=[("results/t/c/alice.json", b"{}")])[0], [])
        hard, _ = self.run_gate(files=[("title-runs/b/c/bob.json", b"{}")])
        self.assertTrue(any("named after" in h for h in hard))
        self.assertEqual(self.run_gate(files=[("title-runs/b/c/alice.json", b"{}")])[0], [])


class Tasks(unittest.TestCase):
    def test_ready(self):
        self.assertEqual(rules.task_ready("Depends on #3\ndepends on #4", {3}), (False, [3, 4]))
        self.assertTrue(rules.task_ready("Depends on #3", {3, 9})[0])
        self.assertTrue(rules.task_ready("", set())[0])

    def test_claim(self):
        free = {"labels": ["task", "ready"], "assignees": []}
        self.assertIsNone(rules.can_claim(free, "a", 0))
        self.assertIn("not ready", rules.can_claim({"labels": ["task"], "assignees": []}, "a", 0))
        self.assertIn("already", rules.can_claim({"labels": ["task", "ready"], "assignees": ["b"]}, "a", 0))
        self.assertIn("2 claims", rules.can_claim(free, "a", 2))


HEAD = "f" * 40
DIG = "d" * 64


def review(user, verdict="approve", commit=HEAD, digest=DIG, checked=3, broke=True):
    body = f"Verdict: {verdict}\nChecked:\n" + "".join(f"- concrete check number {i}\n" for i in range(checked))
    if broke:
        body += "Tried to break: fed it an empty input and a maximal one, both handled\n"
    if digest:
        body += f"Reproduced: {digest}\n"
    return {"user": user, "body": body, "commit": commit}


class Merge(unittest.TestCase):
    COUNTS = {"b": 3, "c": 5, "d": 1, "e": 0, "f": 0, "g": 0}

    def decide(self, reviews, labels=(), ci=True, hours=30, maint=(), assigned=("b", "c", "d", "e", "f", "g")):
        return rules.merge_decision({"author": "alice", "labels": list(labels), "head": HEAD}, reviews, ci,
                                    self.COUNTS, hours, set(maint), set(assigned))

    def test_two_trusted_merge(self):
        self.assertTrue(self.decide([review("b"), review("c")])[0])

    def test_new_reviewers_count_half(self):
        self.assertFalse(self.decide([review("b"), review("d")])[0])             # 1.5
        self.assertTrue(self.decide([review("b"), review("d"), review("e")])[0])  # 2.0
        self.assertTrue(self.decide([review(u) for u in "defg"])[0])              # 4 new = 2.0
        self.assertTrue(self.decide([review("b"), review("d")], maint=["d"])[0])

    def test_only_assigned_reviewers_of_this_commit(self):
        self.assertFalse(self.decide([review("b"), review("c")], assigned=("b",))[0])
        self.assertFalse(self.decide([review("b"), review("c", commit="0" * 40)])[0])
        self.assertFalse(self.decide([review("b"), review("alice")], assigned=("b", "alice"))[0])

    def test_form_is_required(self):
        for bad in (review("c", checked=2), review("c", broke=False), review("c", digest=None)):
            self.assertFalse(self.decide([review("b"), bad])[0])

    def test_blockers(self):
        two = [review("b"), review("c")]
        self.assertFalse(self.decide(two, labels=["hold"])[0])
        self.assertFalse(self.decide(two, ci=False)[0])
        self.assertFalse(self.decide(two, hours=3)[0])
        self.assertFalse(self.decide(two + [review("e", verdict="reject")])[0])
        self.assertIn("differ", self.decide([review("b"), review("c", digest="e" * 64)])[1])

    def test_latest_valid_review_wins(self):
        self.assertTrue(self.decide([review("b", verdict="reject"), review("b"), review("c")])[0])


class Network(unittest.TestCase):
    def test_deadline_shrinks(self):
        self.assertEqual([rules.fix_deadline_hours(n) for n in (0, 5, 20, 50)], [48, 24, 8, 4])

    def test_adoption(self):
        self.assertFalse(rules.adoption_due(10, 30, 0))
        self.assertTrue(rules.adoption_due(24, 24, 0))
        self.assertFalse(rules.adoption_due(24, 2, 0))   # author spoke recently
        self.assertTrue(rules.adoption_due(4, 4, 25))

    def test_pick_reviewers(self):
        pool = ["a", "b", "c", "d", "e"]
        one = rules.pick_reviewers(pool, {"a"}, "7:abc")
        self.assertEqual(len(one), 3)
        self.assertNotIn("a", one)
        self.assertEqual(one, rules.pick_reviewers(list(reversed(pool)), {"a"}, "7:abc"))
        draws = {tuple(rules.pick_reviewers(pool, {"a"}, f"7:{i}")) for i in range(20)}
        self.assertGreater(len(draws), 1)

    def test_split(self):
        parts = rules.parse_split("/split\n- Parse the header\n- Decode the payload | depends: 1\n")
        self.assertEqual(parts, [("Parse the header", []), ("Decode the payload", [1])])
        for bad in ("/split\n- only one part here", "/split\n- First part ok\n- Second | depends: 2",
                    "/split\n- short\n- Another part here"):
            with self.assertRaises(ValueError):
                rules.parse_split(bad)

    def test_collusion(self):
        merges = [("a", ["b"])] * 3 + [("b", ["a"])] * 3 + [("c", ["d"])] * 3 + [("d", ["c"])] * 3 \
            + [("x", ["d"])] * 5
        self.assertEqual(rules.collusion_pairs(merges), [("a", "b")])


class FailsOnBase(unittest.TestCase):
    def run_case(self, fixed):
        import subprocess
        import fails_on_base
        with tempfile.TemporaryDirectory() as d:
            def g(*a):
                subprocess.run(["git", *a], cwd=d, check=True, capture_output=True)
            g("init", "-q")
            g("config", "user.email", "t@t")
            g("config", "user.name", "t")
            os.makedirs(os.path.join(d, "src"))
            os.makedirs(os.path.join(d, "tests"))
            open(os.path.join(d, "src", "__init__.py"), "w").close()
            open(os.path.join(d, "tests", "__init__.py"), "w").close()
            with open(os.path.join(d, "src", "m.py"), "w") as f:
                f.write("def add(a, b):\n    return a - b\n")
            g("add", "-A")
            g("commit", "-qm", "base")
            g("branch", "base")
            with open(os.path.join(d, "src", "m.py"), "w") as f:
                f.write("def add(a, b):\n    return a + b\n" if fixed else "def add(a, b):\n    return a - b  # x\n")
            with open(os.path.join(d, "tests", "test_m.py"), "w") as f:
                f.write("import unittest\nfrom src.m import add\n\nclass T(unittest.TestCase):\n"
                        + ("    def test(self):\n        self.assertEqual(add(2, 2), 4)\n" if fixed else
                           "    def test(self):\n        self.assertEqual(add(2, 2), 0)\n"))
            g("add", "-A")
            g("commit", "-qm", "head")
            cwd = os.getcwd()
            os.chdir(d)
            try:
                old = sys.argv
                sys.argv = ["x", "base", "HEAD"]
                import contextlib
                import io
                with contextlib.redirect_stdout(io.StringIO()):
                    return fails_on_base.main()
            finally:
                sys.argv = old
                os.chdir(cwd)

    def test_real_fix_passes(self):
        self.assertEqual(self.run_case(True), 0)

    def test_test_that_passes_on_base_is_rejected(self):
        self.assertEqual(self.run_case(False), 1)


class Results(unittest.TestCase):
    C = "a" * 40

    def rep(self, digest, hw="nvidia-ada"):
        return {"test": "t", "commit": self.C, "hw_class": hw, "driver": "1", "digest": digest, "pass": True}

    def test_consensus(self):
        d1, d2 = "1" * 64, "2" * 64
        out = results.consensus([("a", self.rep(d1)), ("b", self.rep(d1)), ("a", self.rep(d1, "amd-rdna3")),
                                 ("c", self.rep(d1, "intel")), ("d", self.rep(d2, "intel"))])
        self.assertEqual(out[("t", self.C, "nvidia-ada")][0], "CONFIRMED")
        self.assertEqual(out[("t", self.C, "amd-rdna3")][0], "UNCONFIRMED")
        self.assertEqual(out[("t", self.C, "intel")][0], "DISPUTED")

    def test_same_person_twice_is_one(self):
        out = results.consensus([("a", self.rep("1" * 64)), ("a", self.rep("1" * 64))])
        self.assertEqual(out[("t", self.C, "nvidia-ada")][0], "UNCONFIRMED")

    def test_validate_path(self):
        self.assertIsNone(results.validate(f"results/t/{self.C}/a.json", self.rep("1" * 64)))
        self.assertIn("must be", results.validate(f"results/x/{self.C}/a.json", self.rep("1" * 64)))


class CheckBuild(unittest.TestCase):
    def test_parse_rejects_escapes(self):
        self.assertEqual(check_build.parse(["# c", "a" * 64 + "  dir/f.bin"]), [("a" * 64, "dir/f.bin")])
        for bad in ["a" * 64 + "  ../x", "a" * 64 + "  /etc/x", "abc  x"]:
            with self.assertRaises(ValueError):
                check_build.parse([bad])

    def test_sha256(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "f")
            with open(p, "wb") as f:
                f.write(b"abc")
            self.assertEqual(check_build.sha256(p),
                             "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")


if __name__ == "__main__":
    unittest.main()
