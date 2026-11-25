"""健康报告契约：退役源不得继续标红（换源后旧 id 会永远红）。"""

import json
import tempfile
import unittest
from pathlib import Path

from pip_app.health_report import RETIRED, load_rows, render, summarize


def row(source_id: str, status: str, name: str = "", day: str = "2026-11-24", error: str = "") -> dict:
    return {
        "run_at": "2026-11-24T12:00:00+00:00",
        "day": day,
        "source_id": source_id,
        "source_name": name or source_id,
        "domain": "ai",
        "status": status,
        "fetched": 10 if status == "ok" else 0,
        "error": error,
        "duration_ms": 100,
    }


class RetiredSourceTest(unittest.TestCase):
    def test_retired_source_flagged_and_excluded_from_red_count(self):
        rows = [row("alive", "ok"), row("alive", "ok"), row("dead", "failed", error="not_a_feed")]
        health = summarize(rows, active_ids={"alive"})
        dead = next(h for h in health if h.source_id == "dead")
        alive = next(h for h in health if h.source_id == "alive")
        self.assertEqual(dead.flag, RETIRED)
        self.assertEqual(alive.flag, "GREEN")

    def test_render_separates_retired_section(self):
        health = summarize([row("alive", "ok"), row("dead", "failed")], active_ids={"alive"})
        text = render(health)
        self.assertIn("已退役", text)
        self.assertIn("红色 0 个", text)

    def test_without_active_ids_behaviour_unchanged(self):
        health = summarize([row("dead", "failed", error="not_a_feed")])
        self.assertEqual(health[0].flag, "RED")


class LoadRowsTest(unittest.TestCase):
    def test_missing_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_rows(Path(tmp) / "nope.jsonl"), [])

    def test_old_rows_filtered_by_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "health.jsonl"
            old = row("x", "ok")
            old["run_at"] = "2020-01-01T00:00:00+00:00"
            path.write_text(
                json.dumps(old) + "\n" + json.dumps(row("y", "ok")) + "\n", encoding="utf-8"
            )
            loaded = load_rows(path, days=7)
            self.assertEqual([r["source_id"] for r in loaded], ["y"])


class UnreachableTest(unittest.TestCase):
    """网络层失败不算源质量：分母要扣掉 unreachable。"""

    def test_unreachable_excluded_from_success_rate(self):
        rows = [row("s", "ok"), row("s", "ok"), row("s", "unreachable"), row("s", "unreachable")]
        health = summarize(rows)[0]
        self.assertEqual(health.unreachable, 2)
        self.assertEqual(health.failed, 0)
        self.assertAlmostEqual(health.success_rate, 1.0)
        self.assertEqual(health.flag, "GREEN")

    def test_all_unreachable_is_idle_not_red(self):
        health = summarize([row("s", "unreachable") for _ in range(3)])[0]
        self.assertEqual(health.flag, "IDLE")
        self.assertAlmostEqual(health.success_rate, 0.0)


class SuccessRateTest(unittest.TestCase):
    def test_zero_result_counts_as_not_ok(self):
        health = summarize([row("s", "ok"), row("s", "zero_result")])
        self.assertAlmostEqual(health[0].success_rate, 0.5)
        self.assertEqual(health[0].zero, 1)
        self.assertEqual(health[0].flag, "YELLOW")

    def test_three_failures_force_red(self):
        rows = [row("s", "failed") for _ in range(3)] + [row("s", "ok") for _ in range(3)]
        self.assertEqual(summarize(rows)[0].flag, "RED")


if __name__ == "__main__":
    unittest.main()
