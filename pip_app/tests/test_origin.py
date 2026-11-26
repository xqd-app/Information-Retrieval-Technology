"""采集端实时同步的契约：读取当前值、变化判定、失败降级、开关。"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from pip_app import config, origin  # noqa: E402


class CurrentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = config.DATA_DIR
        config.DATA_DIR = Path(self.tmp.name)

    def tearDown(self):
        config.DATA_DIR = self.original
        self.tmp.cleanup()

    def write_globe(self, origin_payload):
        (config.DATA_DIR / "globe.json").write_text(
            json.dumps({"origin": origin_payload, "generated_at": "2026-11-26T03:00:00+00:00"}),
            encoding="utf-8",
        )

    def test_reads_origin_from_globe(self):
        self.write_globe({"city": "Kunming", "lat": 25.04, "lon": 102.72,
                          "source": "env-city", "detected_at": ""})
        snapshot = origin.current()
        self.assertEqual(snapshot["city"], "Kunming")
        self.assertAlmostEqual(snapshot["lat"], 25.04, places=2)

    def test_missing_globe_returns_empty(self):
        snapshot = origin.current()
        self.assertEqual(snapshot["city"], "")
        self.assertIsNone(snapshot["lat"])

    def test_age_seconds_computed(self):
        self.write_globe({"city": "Tokyo", "lat": 35.6, "lon": 139.7,
                          "source": "ip-detected:x", "detected_at": "2026-11-26T03:00:00Z"})
        snapshot = origin.current()
        self.assertIsNotNone(snapshot["age_seconds"])
        self.assertGreaterEqual(snapshot["age_seconds"], 0)

    def test_broken_json_is_safe(self):
        (config.DATA_DIR / "globe.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(origin.current()["city"], "")


class SameTest(unittest.TestCase):
    def test_same_city_and_close_coords(self):
        a = {"city": "Tokyo", "lat": 35.6289, "lon": 139.7915}
        b = {"city": "Tokyo", "lat": 35.6300, "lon": 139.7900}
        self.assertTrue(origin._same(a, b))

    def test_different_city(self):
        a = {"city": "Tokyo", "lat": 35.6289, "lon": 139.7915}
        b = {"city": "Osaka", "lat": 35.6289, "lon": 139.7915}
        self.assertFalse(origin._same(a, b))

    def test_far_coords(self):
        a = {"city": "Tokyo", "lat": 35.6, "lon": 139.7}
        b = {"city": "Tokyo", "lat": 36.3, "lon": 139.7}
        self.assertFalse(origin._same(a, b))

    def test_none_inputs(self):
        self.assertFalse(origin._same(None, {"city": "X"}))
        self.assertFalse(origin._same({"city": "X"}, None))


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = config.DATA_DIR
        config.DATA_DIR = Path(self.tmp.name)
        (config.DATA_DIR / "globe.json").write_text(
            json.dumps({"origin": {"city": "Kunming", "lat": 25.04, "lon": 102.72,
                                   "source": "env-city"}}),
            encoding="utf-8",
        )

    def tearDown(self):
        config.DATA_DIR = self.original
        self.tmp.cleanup()

    def test_detect_failure_is_reported(self):
        original_detect = origin.detect
        origin.detect = lambda **kw: None
        try:
            result = origin.sync(rebuild=False)
            self.assertFalse(result["changed"])
            self.assertEqual(result["reason"], "detect-failed")
        finally:
            origin.detect = original_detect

    def test_unchanged_is_reported(self):
        original_detect = origin.detect
        origin.detect = lambda **kw: {"city": "Kunming", "lat": 25.04, "lon": 102.72,
                                      "source": "ip-api.com", "ip": "1.1.1.1"}
        try:
            result = origin.sync(rebuild=False)
            self.assertFalse(result["changed"])
            self.assertEqual(result["reason"], "unchanged")
        finally:
            origin.detect = original_detect

    def test_changed_without_rebuild(self):
        original_detect = origin.detect
        origin.detect = lambda **kw: {"city": "Frankfurt", "lat": 50.11, "lon": 8.68,
                                      "source": "ip-api.com", "ip": "2.2.2.2"}
        try:
            result = origin.sync(rebuild=False)
            self.assertTrue(result["changed"])
            self.assertEqual(result["reason"], "changed-no-rebuild")
            self.assertEqual(result["after"]["city"], "Frankfurt")
        finally:
            origin.detect = original_detect


class SwitchTest(unittest.TestCase):
    def test_auto_enabled_default(self):
        os.environ.pop("PIP_AUTO_ORIGIN", None)
        self.assertTrue(origin.auto_enabled())

    def test_auto_disabled(self):
        os.environ["PIP_AUTO_ORIGIN"] = "0"
        try:
            self.assertFalse(origin.auto_enabled())
        finally:
            os.environ.pop("PIP_AUTO_ORIGIN", None)


if __name__ == "__main__":
    unittest.main()
