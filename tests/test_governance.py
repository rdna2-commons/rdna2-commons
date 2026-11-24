import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bot"))
import rules  # noqa: E402

HEAD = "f" * 40


def review(user, verdict="approve"):
    body = (f"Verdict: {verdict}\nChecked:\n- one concrete check\n- two concrete check\n- three concrete check\n"
            "Tried to break: removed the label and pushed again, still refused\nReproduced: " + "d" * 64 + "\n")
    return {"user": user, "body": body, "commit": HEAD}


class Protected(unittest.TestCase):
    def test_paths(self):
        self.assertEqual(rules.protected_paths(["bot/rules.py", "docs/a.md", ".github/workflows/x.yml",
                                                "MAINTAINERS", "tools/results.py", "tools/fails_on_base.py"]),
                         [".github/workflows/x.yml", "MAINTAINERS", "bot/rules.py", "tools/fails_on_base.py"])

    def test_never_automerged(self):
        pr = {"author": "a", "labels": [], "head": HEAD, "protected": True}
        ok, why = rules.merge_decision(pr, [review("b"), review("c")], True, {"b": 9, "c": 9}, 100, set(), {"b", "c"})
        self.assertFalse(ok)
        self.assertIn("by hand", why)
        pr = {"author": "a", "labels": ["governance"], "head": HEAD}
        self.assertFalse(rules.merge_decision(pr, [review("b"), review("c")], True, {"b": 9, "c": 9}, 100, set(),
                                              {"b", "c"})[0])


class GovernanceStatus(unittest.TestCase):
    PR = {"author": "a", "head": HEAD}

    def test_needs_two_other_maintainers(self):
        m = {"a", "m1", "m2", "m3"}
        self.assertFalse(rules.governance_status(self.PR, [review("m1")], True, 100, m)[0])
        self.assertTrue(rules.governance_status(self.PR, [review("m1"), review("m2")], True, 100, m)[0])
        self.assertFalse(rules.governance_status(self.PR, [review("m1"), review("a")], True, 100, m)[0])

    def test_one_other_maintainer_suffices_when_only_one(self):
        self.assertTrue(rules.governance_status(self.PR, [review("m1")], True, 100, {"a", "m1"})[0])
        self.assertFalse(rules.governance_status(self.PR, [], True, 100, {"a"})[0])

    def test_blockers(self):
        m = {"m1", "m2"}
        two = [review("m1"), review("m2")]
        self.assertFalse(rules.governance_status(self.PR, two, False, 100, m)[0])
        self.assertFalse(rules.governance_status(self.PR, two, True, 10, m)[0])
        self.assertFalse(rules.governance_status(self.PR, two + [review("x", "reject")], True, 100, m)[0])

    def test_claim_limits(self):
        free = {"labels": ["task", "ready"], "assignees": []}
        self.assertIn("2 claims", rules.can_claim(free, "a", 2))
        self.assertIsNone(rules.can_claim(free, "a", 2, rules.MAX_CLAIMS_MAINTAINER))


class Candidates(unittest.TestCase):
    def test_candidates(self):
        counts = {"a": 12, "b": 12, "c": 5, "d": 15, "e": 20, "x[bot]": 50}
        days = {"a": 40, "b": 10, "c": 90, "d": 60, "e": 60, "x[bot]": 90}
        self.assertEqual(rules.maintainer_candidates(counts, days, {"d"}, {"e"}), ["a"])


if __name__ == "__main__":
    unittest.main()
