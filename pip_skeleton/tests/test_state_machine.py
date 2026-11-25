"""E 组：降级状态机与预算（对应 §12 测试矩阵 E1–E3）。"""

import unittest

from pip.state_machine import (
    DEGRADED,
    NORMAL,
    DayRecord,
    budget_action,
    evaluate,
)


def day(n: int, degraded: bool, rate: float = 1.0, domain: str = "ai") -> DayRecord:
    return DayRecord(day=f"2026-11-{n:02d}", degraded=degraded, success_rate=rate, domain=domain)


class DegradedStateTest(unittest.TestCase):
    def test_e1_three_consecutive_days_block_weekly(self):
        history = [day(20, False), day(21, True), day(22, True)]
        decision = evaluate(history, today=day(23, True))
        self.assertEqual(decision.level, DEGRADED)
        self.assertEqual(decision.consecutive_degraded, 3)
        self.assertTrue(decision.alert)
        self.assertTrue(decision.block_weekly)
        self.assertIn("阻断周报", decision.reasons[0])

    def test_e1_two_days_alert_but_no_block(self):
        decision = evaluate([day(21, True)], today=day(22, True))
        self.assertEqual(decision.consecutive_degraded, 2)
        self.assertFalse(decision.block_weekly)

    def test_e2_recovery_resets_state(self):
        history = [day(20, True), day(21, True), day(22, True)]
        decision = evaluate(history, today=day(23, False))
        self.assertEqual(decision.level, NORMAL)
        self.assertEqual(decision.consecutive_degraded, 0)
        self.assertFalse(decision.block_weekly)

    def test_e2_history_preserved_by_caller(self):
        history = [day(20, True), day(21, True), day(22, True)]
        normalize_before = list(history)
        evaluate(history, today=day(23, False))
        self.assertEqual(history, normalize_before)  # 纯函数，不改入参

    def test_e3_low_success_rate_alert_without_block(self):
        history = [day(n, False, rate=0.2) for n in range(15, 22)]
        decision = evaluate(history, today=day(22, False, rate=0.2))
        self.assertTrue(decision.alert)
        self.assertFalse(decision.block_weekly)
        self.assertTrue(any("成功率" in r for r in decision.reasons))


class BudgetTest(unittest.TestCase):
    def test_e3_budget_thresholds(self):
        self.assertEqual(budget_action(79, 100), "ok")
        self.assertEqual(budget_action(80, 100), "warn")
        self.assertEqual(budget_action(100, 100), "stop")
        self.assertEqual(budget_action(150, 100), "stop")

    def test_e3_zero_budget_rejected(self):
        with self.assertRaises(ValueError):
            budget_action(10, 0)


if __name__ == "__main__":
    unittest.main()
