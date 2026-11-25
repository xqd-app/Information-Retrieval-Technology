"""§6 稳定性判级的规则层（规则优先，LLM 可被覆盖）。

这里只实现可判定的部分：把「源一致性 / 矛盾词 / 一手源」折算成等级，
并保留 rule_trace 供日报引用。真正的 LLM 调用在分析服务里，不在此模块。
"""

from __future__ import annotations

from dataclasses import dataclass

STABLE = "stable"
DEVELOPING = "developing"
CONTESTED = "contested"

AGREEMENT_FLOOR = 0.8
MIN_SOURCES_FOR_STABLE = 3


@dataclass(frozen=True)
class StabilitySignals:
    source_count: int
    source_agreement: float  # 0..1
    has_primary_source: bool
    contradiction_terms: int
    time_span_hours: float


@dataclass(frozen=True)
class Verdict:
    stability: str
    confidence: float
    rule_trace: str
    degraded: bool


def judge(signals: StabilitySignals, *, llm_stability: str | None, llm_rationale: str = "") -> Verdict:
    trace: list[str] = []

    if signals.contradiction_terms > 0 and signals.source_agreement < AGREEMENT_FLOOR:
        trace.append(f"source_agreement={signals.source_agreement:.2f}<{AGREEMENT_FLOOR} "
                     f"AND contradiction_terms={signals.contradiction_terms}>0 -> contested/developing")
        stability = CONTESTED if signals.contradiction_terms >= 2 else DEVELOPING
        confidence = 0.55
    elif signals.source_count >= MIN_SOURCES_FOR_STABLE and signals.source_agreement >= AGREEMENT_FLOOR:
        trace.append(f"source_count={signals.source_count}>={MIN_SOURCES_FOR_STABLE} "
                     f"AND source_agreement={signals.source_agreement:.2f}>={AGREEMENT_FLOOR} -> allow stable")
        stability = llm_stability or STABLE
        confidence = 0.85 if llm_stability else 0.7
    else:
        trace.append(f"source_count={signals.source_count} "
                     f"AND source_agreement={signals.source_agreement:.2f} -> developing (insufficient support)")
        stability = DEVELOPING
        confidence = 0.6

    if llm_stability is None:
        trace.append("llm_unavailable -> degraded")
        return Verdict(stability, min(confidence, 0.6), " | ".join(trace), True)

    if llm_rationale:
        trace.append(f"llm: {llm_rationale}")

    return Verdict(stability, confidence, " | ".join(trace), False)
