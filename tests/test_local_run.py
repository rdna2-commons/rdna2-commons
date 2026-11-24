import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import local_run as lr  # noqa: E402
import title_runs  # noqa: E402


def ev(kind, **k):
    return json.dumps(dict({"seq": 1, "t": 0.0, "kind": kind}, **k))


class Trace(unittest.TestCase):
    def test_stages_in_order(self):
        self.assertEqual(lr.stage_from_trace([ev("map")])[0], "loads")
        self.assertEqual(lr.stage_from_trace([ev("map"), ev("dllmain")])[0], "imports-resolved")
        lines = [ev("map"), ev("device_created"), ev("first_frame"), ev("frames", count=150, fps=29.97)]
        stage, fps, crash = lr.stage_from_trace(lines)
        self.assertEqual((stage, fps, crash), ("first-frame", 29.97, None))

    def test_later_events_do_not_lower_the_stage(self):
        self.assertEqual(lr.stage_from_trace([ev("first_frame"), ev("map"), "not json"])[0], "first-frame")

    def test_crash(self):
        c = {"code": "0xc0000005", "at": "host:game.exe+0x2478440", "access": "read", "address": "0x0"}
        _, _, crash = lr.stage_from_trace([ev("map"), ev("crash", **c)])
        self.assertEqual(lr.stop_text(crash, False, 1), "game.exe+0x2478440 access violation (read)")
        self.assertEqual(lr.stop_text({"code": "0xc000001d", "at": "0x1234"}, False, 1),
                         "crash at an unmapped address")
        self.assertEqual(lr.stop_text(None, True, None), "")
        self.assertEqual(lr.stop_text(None, False, 3), "exited with code 3")


class Shaders(unittest.TestCase):
    def test_reasons_are_scrubbed(self):
        r = lr.reason_bucket("NotImplementedError: v_foo_b32 at 0x1a2b in 'shader_123' (42 times) ps_blur_main")
        self.assertEqual(r, "NotImplementedError: v_foo_b at in ( times)")
        self.assertNotIn("ps_blur", r)
        self.assertNotIn("shader_123", r)
        self.assertNotIn("0x", r)

    def test_stats_and_notes(self):
        index = {"a": {"stage": "ps"}, "b": {"error": "ValueError: bad 0x10"}, "c": {"error": "ValueError: bad 0x20"},
                 "d": {"error": "KeyError: 'x'"}}
        total, failed, reasons = lr.shader_stats(index)
        self.assertEqual((total, failed), (4, 3))
        self.assertEqual(reasons, {"ValueError: bad": 2, "KeyError": 1})
        self.assertEqual(lr.notes_text(total, failed, reasons),
                         "shaders: 1 of 4 translated; failed: 2 ValueError: bad; 1 KeyError")
        self.assertEqual(lr.notes_text(0, 0, {}), "no shader index")
        self.assertLessEqual(len(lr.notes_text(10 ** 6, 10 ** 6, {f"E{i}": 1 for i in range(500)})), 480)


class Report(unittest.TestCase):
    def test_report_passes_title_run_validation(self):
        c = "c" * 40
        r = lr.build_report("build-a", c, "nvidia-ada", "windows-11", "621.24", "first-frame", 30.0,
                            "game.exe+0x10 access violation (read)", "shaders: 1 of 1 translated")
        self.assertEqual(title_runs.validate_run(r, "build-a", c, {"build-a": {}}), [])


if __name__ == "__main__":
    unittest.main()
