"""源健康报告：按源聚合最近 N 天的成功率，失败率高者标红。

替代「只看今天」的盲区：world-model 连续 35 天 fallback 无人发现，
就是因为它既没有趋势、也没有阈值。
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config

RED = "RED"        # 成功率 < 0.5 或连续失败
YELLOW = "YELLOW"  # 0.5 <= 成功率 < 0.9
GREEN = "GREEN"
IDLE = "IDLE"      # 窗口内无记录
RETIRED = "RETIRED"  # 源已从 sources.json 移除：历史失败不再计入红色统计


@dataclass
class SourceHealth:
    source_id: str
    source_name: str
    domain: str
    runs: int
    ok: int
    zero: int
    failed: int
    avg_ms: int
    last_error: str
    unreachable: int = 0
    retired: bool = False

    @property
    def reachable_runs(self) -> int:
        return max(self.runs - self.unreachable, 0)

    @property
    def success_rate(self) -> float:
        return self.ok / self.reachable_runs if self.reachable_runs else 0.0

    @property
    def flag(self) -> str:
        if self.retired:
            return RETIRED
        if self.runs == 0 or self.reachable_runs == 0:
            return IDLE
        if self.success_rate < 0.5 or self.failed >= 3:
            return RED
        if self.success_rate < 0.9:
            return YELLOW
        return GREEN


def load_rows(path: Path | str = config.HEALTH_FILE, *, days: int = config.HEALTH_WINDOW_DAYS) -> list[dict]:
    file = Path(path)
    if not file.exists():
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    rows = [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [row for row in rows if (row.get("run_at") or "") >= cutoff]


def summarize(rows: list[dict], *, active_ids: set[str] | None = None) -> list[SourceHealth]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["source_id"]].append(row)

    out: list[SourceHealth] = []
    for source_id, group in grouped.items():
        ok = sum(1 for r in group if r["status"] == "ok")
        zero = sum(1 for r in group if r["status"] == "zero_result")
        failed = sum(1 for r in group if r["status"] in {"failed", "timeout"})
        unreachable = sum(1 for r in group if r["status"] == "unreachable")
        errors = [r["error"] for r in group if r.get("error")]
        out.append(
            SourceHealth(
                source_id=source_id,
                source_name=group[-1].get("source_name", source_id),
                domain=group[-1].get("domain", ""),
                runs=len(group),
                ok=ok,
                zero=zero,
                failed=failed,
                unreachable=unreachable,
                avg_ms=int(sum(r.get("duration_ms", 0) for r in group) / len(group)),
                last_error=errors[-1] if errors else "",
                retired=active_ids is not None and source_id not in active_ids,
            )
        )
    out.sort(key=lambda h: (h.retired, h.success_rate, -h.failed, h.source_id))
    return out


def _line(row: SourceHealth) -> str:
    return (
        f"{row.flag:<8}{row.source_name[:24]:<26}{row.domain:<8}"
        f"{row.success_rate:>6.0%}{f'{row.ok}/{row.zero}/{row.failed}':>15}"
        f"{row.avg_ms:>7}ms{row.unreachable:>6}  {row.last_error[:40]}"
    )


def render(health: list[SourceHealth]) -> str:
    active = [h for h in health if not h.retired]
    retired = [h for h in health if h.retired]
    lines = [f"源健康报告（最近 {config.HEALTH_WINDOW_DAYS} 天）", ""]
    lines.append(
        f"{'状态':<8}{'源':<26}{'域':<8}{'成功率':>7}{'ok/zero/fail':>15}"
        f"{'均耗时':>8}{'离线':>6}  最近错误"
    )
    lines.extend(_line(row) for row in active)
    reds = [h for h in active if h.flag == RED]
    lines.append("")
    lines.append(
        f"合计 {len(active)} 源，红色 {len(reds)} 个"
        + ("：" + ", ".join(h.source_id for h in reds) if reds else "")
    )
    if retired:
        lines.append("")
        lines.append(f"— 已退役 {len(retired)} 源（不在当前 sources.json 中，历史失败不计入统计）")
        lines.extend(_line(row) for row in retired)
    return "\n".join(lines)
