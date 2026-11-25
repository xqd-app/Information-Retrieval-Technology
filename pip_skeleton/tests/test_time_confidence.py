"""B 组：时间与窗口（对应 §12 测试矩阵 B1–B4）。"""

import unittest
from datetime import datetime, timedelta, timezone

from pip.time_confidence import HIGH, LOW, MEDIUM, resolve, same_timestamp

FETCHED = datetime(2026, 11, 24, 3, 0, tzinfo=timezone.utc)


class TimeConfidenceTest(unittest.TestCase):
    def test_b1_normal_pubdate_is_high(self):
        resolved = resolve(FETCHED - timedelta(hours=1), None, FETCHED)
        self.assertEqual(resolved.confidence, HIGH)
        self.assertTrue(resolved.in_window)

    def test_b2_only_lastbuilddate_medium(self):
        resolved = resolve(None, FETCHED - timedelta(hours=2), FETCHED)
        self.assertEqual(resolved.confidence, MEDIUM)
        self.assertTrue(resolved.in_window)

    def test_b2_same_timestamp_downgrades_to_low(self):
        resolved = resolve(None, FETCHED - timedelta(hours=2), FETCHED, all_same=True)
        self.assertEqual(resolved.confidence, LOW)
        self.assertIsNone(resolved.published_at)
        self.assertFalse(resolved.in_window)

    def test_b3_utc_boundary_keeps_published_at(self):
        edge = datetime(2026, 11, 23, 23, 59, 59, tzinfo=timezone.utc)
        resolved = resolve(edge, None, FETCHED)
        self.assertEqual(resolved.published_at, edge)
        self.assertTrue(resolved.in_window)

    def test_b4_future_time_is_low(self):
        resolved = resolve(FETCHED + timedelta(hours=7), None, FETCHED)
        self.assertEqual(resolved.confidence, LOW)
        self.assertIsNone(resolved.published_at)

    def test_b4_too_old_is_low(self):
        resolved = resolve(FETCHED - timedelta(days=31), None, FETCHED)
        self.assertEqual(resolved.confidence, LOW)

    def test_naive_datetime_is_treated_as_utc(self):
        naive = datetime(2026, 11, 24, 2, 0)
        resolved = resolve(naive, None, FETCHED)
        self.assertEqual(resolved.confidence, HIGH)
        self.assertEqual(resolved.published_at, FETCHED - timedelta(hours=1))

    def test_same_timestamp_helper(self):
        stamp = datetime(2026, 11, 24, tzinfo=timezone.utc)
        self.assertTrue(same_timestamp([stamp, stamp, None]))
        self.assertFalse(same_timestamp([stamp]))
        self.assertFalse(same_timestamp([stamp, stamp - timedelta(seconds=1)]))


if __name__ == "__main__":
    unittest.main()
