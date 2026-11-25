"""A 组：抓取健壮性（对应 §12 测试矩阵 A2–A5，全部离线，不联网）。"""

import os
import tempfile
import time
import unittest
from pathlib import Path

from pip.fetch import (
    BUSY,
    FAILED,
    OK,
    PARTIAL,
    THROTTLED,
    ZERO_RESULT,
    SingleFlight,
    classify,
    collect,
    throttle_remaining,
)


class ClassifyTest(unittest.TestCase):
    def test_a1_ok(self):
        self.assertEqual(classify(12, ""), OK)

    def test_a2_http_error_is_failed(self):
        self.assertEqual(classify(0, "HTTP 403"), FAILED)

    def test_a3_zero_items_is_not_success(self):
        self.assertEqual(classify(0, ""), ZERO_RESULT)

    def test_a4_selector_miss_is_failed(self):
        self.assertEqual(classify(0, "selector_miss"), FAILED)
        self.assertNotEqual(classify(0, "selector_miss"), OK)

    def test_a5_timeout_classified(self):
        self.assertEqual(classify(0, "read timeout"), "timeout")


class CollectTest(unittest.TestCase):
    def test_a2_bad_source_does_not_break_batch(self):
        def fetch_one(name):
            if name == "broken":
                return 0, "HTTP 500"
            return 3, ""

        result = collect(["good", "broken", "empty"], lambda n: (0, "") if n == "empty" else fetch_one(n))
        statuses = {s.name: s.status for s in result.sources}
        self.assertEqual(statuses["good"], OK)
        self.assertEqual(statuses["broken"], FAILED)
        self.assertEqual(statuses["empty"], ZERO_RESULT)
        self.assertEqual(result.status, PARTIAL)

    def test_a5_exception_never_escapes(self):
        def fetch_one(name):
            raise RuntimeError("boom")

        result = collect(["s1"], fetch_one)
        self.assertEqual(result.sources[0].status, FAILED)
        self.assertEqual(result.sources[0].error, "RuntimeError")

    def test_budget_exhaustion_marks_remaining_timeout(self):
        def slow(name):
            time.sleep(0.25)
            return 5, ""

        result = collect(["a", "b", "c", "d"], slow, workers=2, budget=0.05)
        self.assertTrue(any(s.status == "timeout" for s in result.sources))
        self.assertEqual(len(result.sources), 4)


class ThrottleTest(unittest.TestCase):
    def test_c1_cooldown_blocks_second_manual_refresh(self):
        now = 1_000_000.0
        self.assertEqual(throttle_remaining(None, now, cooldown=600), 0)
        self.assertEqual(throttle_remaining(now - 100, now, cooldown=600), 500)
        self.assertEqual(throttle_remaining(now - 700, now, cooldown=600), 0)


class SingleFlightTest(unittest.TestCase):
    def test_second_acquire_fails_while_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "fetch-ai.lock"
            with SingleFlight(lock) as first:
                self.assertTrue(first)
                with SingleFlight(lock) as second:
                    self.assertFalse(second)
            self.assertFalse(lock.exists())  # 退出即释放


if __name__ == "__main__":
    unittest.main()
