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

    def test_phases_and_svg(self):
        issues = [issue(1, "shaders", "closed", ["phase:1"]), issue(2, "shaders", labels=["phase:1"])]
        page = progress.render(issues, [], {}, "now")
        self.assertIn("| 1. Shared knowledge |", page)
        self.assertIn("| 1/2 |", page)
        chart = progress.svg(progress.count(issues, progress.area_of))
        self.assertTrue(chart.startswith("<svg"))
        self.assertIn(">shaders<", chart)
        self.assertIn(">1/2<", chart)

    def test_task_lists_merges_and_badges(self):
        issues = [dict(issue(1, "shaders", "closed", ["phase:1"]), title="Done one"),
                  dict(issue(2, "docs", labels=["phase:0", "ready"]), title="Ready | two")]
        pulls = [{"merged_at": "2026-11-24T09:00:00Z", "user": {"login": "a"}, "number": 7, "title": "A PR"}]
        page = progress.render(issues, pulls, {}, "now", {"valu-f32": 2})
        self.assertIn("## Phase 0: Foundation", page)
        self.assertIn("| 🟦 | [#2](../../issues/2) Ready \| two | docs | — |", page)
        self.assertIn("| 2026-11-24 | [#7](../../pull/7) A PR | @a |", page)
        self.assertIn("| @a | 1 |", page)
        self.assertIn("**2 cases**", page)
        b = progress.badges(issues, pulls, {}, 2)
        self.assertIn("1/2 done", b["tasks"])
        self.assertIn("phase", b["phase"])
        self.assertIn(">0 of 4<", b["phase"])

    def test_title_runs_section(self):
        page = progress.render([], [], {}, "now", {}, {("build-a", "c" * 40): ("menu", "in-world")})
        self.assertIn("| build-a | `ccccccccc` | menu | in-world |", page)
        self.assertIn("No reports yet. See docs/title-runs.md.", progress.render([], [], {}, "now"))


if __name__ == "__main__":
    unittest.main()
