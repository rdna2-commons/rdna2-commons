import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import progress  # noqa: E402


def issue(n, area, state="open", labels=(), assignees=()):
    return {"number": n, "state": state, "labels": [{"name": f"area:{area}"}] + [{"name": l} for l in labels],
            "assignees": [{"login": a} for a in assignees]}


class Progress(unittest.TestCase):
    def test_states_and_totals(self):
        issues = [issue(1, "shaders", "closed"), issue(2, "shaders", labels=["ready"]),
                  issue(3, "shaders", assignees=["a"]), issue(4, "docs"),
                  {"number": 5, "state": "open", "labels": [], "assignees": [], "pull_request": {}}]
        pulls = [{"merged_at": "x", "user": {"login": "a"}}, {"merged_at": None, "user": {"login": "b"}}]
        page = progress.render(issues, pulls, {}, "now")
        self.assertIn("**1 of 4 tasks done**", page)
        self.assertIn("1 in progress · 1 ready to take · 1 waiting on others · 1 pull requests merged by 1", page)
        self.assertIn("| shaders | `███·······` | 1 | 1 | 1 | 0 |", page)
        self.assertIn("| docs | `··········` | 0 | 0 | 0 | 1 |", page)
        self.assertLess(page.index("| shaders"), page.index("| docs"))

    def test_unlabelled_task_is_unsorted(self):
        page = progress.render([{"number": 1, "state": "open", "labels": [], "assignees": []}], [], {}, "now")
        self.assertIn("| unsorted |", page)

    def test_results_section(self):
        rows = {("t", "a" * 40, "nvidia-ada"): ("CONFIRMED", {"d" * 64: ["x", "y"]})}
        page = progress.render([], [], rows, "now")
        self.assertIn("| CONFIRMED | t | `aaaaaaaaa` | nvidia-ada | 2 |", page)
        self.assertIn("No reports yet", progress.render([], [], {}, "now"))


if __name__ == "__main__":
    unittest.main()
