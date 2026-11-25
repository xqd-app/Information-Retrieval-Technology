"""§11.2 降级状态机与阻断规则。

world-model 的教训：只标记不阻断，人会习惯性忽略标记。
因此连续 3 天 degraded 必须同时「告警」+「阻断周报」。
"""

from __future__ import annotations

from dataclasses import dataclass

DEGRADED_BLOCK_DAYS = 3
LOW_SUCCESS_DAYS = 7
LOW_SUCCESS_RATE = 0.5
BUDGET_WARN_RATIO = 0.8
BUDGET_STOP_RATIO = 1.0

NORMAL = "normal"
DEGRADED = "degraded"


@dataclass(frozen=True)
class DayRecord:
    day: str
    degraded: bool
    success_rate: float = 1.0
    domain: str = "default"


@dataclass(frozen=True)
class Decision:
    level: str
    consecutive_degraded: int
    alert: bool
    block_weekly: bool
    reasons: tuple[str, ...]


def evaluate(history: list[DayRecord], *, today: DayRecord) -> Decision:
    """history 为按时间升序的既往记录（不含 today）。幂等、无副作用，可直接单测。"""
    reasons: list[str] = []
    consecutive = 0
    for record in reversed(history + [today]):
        if record.degraded:
            consecutive += 1
        else:
            break

    block = consecutive >= DEGRADED_BLOCK_DAYS
    alert = block
    if block:
        reasons.append(f"连续 {consecutive} 天 degraded >= {DEGRADED_BLOCK_DAYS}，阻断周报")

    tail = [r for r in (history + [today]) if r.domain == today.domain][-LOW_SUCCESS_DAYS:]
    if len(tail) >= LOW_SUCCESS_DAYS:
        rate = sum(r.success_rate for r in tail) / len(tail)
        if rate < LOW_SUCCESS_RATE:
            alert = True
            reasons.append(f"{today.domain} 连续 {LOW_SUCCESS_DAYS} 天成功率 {rate:.2f} < {LOW_SUCCESS_RATE}")

    return Decision(
        level=DEGRADED if consecutive else NORMAL,
        consecutive_degraded=consecutive,
        alert=alert,
        block_weekly=block,
        reasons=tuple(reasons),
    )


def budget_action(tokens_used: int, daily_budget: int) -> str:
    if daily_budget <= 0:
        raise ValueError("daily_budget must be positive")
    ratio = tokens_used / daily_budget
    if ratio >= BUDGET_STOP_RATIO:
        return "stop"
    if ratio >= BUDGET_WARN_RATIO:
        return "warn"
    return "ok"
