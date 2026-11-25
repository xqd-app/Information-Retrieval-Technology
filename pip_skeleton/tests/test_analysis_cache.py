"""D 组：分析缓存与规则优先级（对应 §12 测试矩阵 D3–D4，加规则覆盖 LLM 的一例）。"""

import unittest

from pip.analysis_cache import AnalysisCache, CacheEntry, content_hash
from pip.stability import StabilitySignals, judge

MODEL = "deepseek-chat"
PROMPT = "stability-v3"


class CacheTest(unittest.TestCase):
    def setUp(self):
        self.cache = AnalysisCache(":memory:")
        self.chash = content_hash("Nvidia earnings", "Datacenter revenue up 94%.")

    def tearDown(self):
        self.cache.close()

    def _entry(self):
        return CacheEntry(self.chash, "英伟达数据中心营收增长 94%", "developing",
                          {"source_count": 4}, MODEL, PROMPT)

    def test_d3_hit_returns_entry_without_recompute(self):
        self.cache.put(self._entry(), domain="tech", lang="en", tokens_in=800, tokens_out=120)
        hit = self.cache.get(self.chash, MODEL, PROMPT, day="2026-11-24")
        self.assertIsNotNone(hit)
        self.assertEqual(hit.stability, "developing")
        self.assertEqual(hit.evidence["source_count"], 4)

    def test_d3_miss_then_hit_rate(self):
        self.assertIsNone(self.cache.get(self.chash, MODEL, PROMPT, day="2026-11-24"))
        self.cache.put(self._entry(), domain="tech", lang="en", tokens_in=800, tokens_out=120)
        self.cache.get(self.chash, MODEL, PROMPT, day="2026-11-24")
        self.assertAlmostEqual(self.cache.hit_rate("2026-11-24"), 0.5)

    def test_d4_prompt_version_bump_invalidates(self):
        self.cache.put(self._entry(), domain="tech", lang="en", tokens_in=800, tokens_out=120)
        self.assertIsNone(self.cache.get(self.chash, MODEL, "stability-v4", day="2026-11-24"))

    def test_d4_model_change_invalidates(self):
        self.cache.put(self._entry(), domain="tech", lang="en", tokens_in=800, tokens_out=120)
        self.assertIsNone(self.cache.get(self.chash, "gemini-2.5-flash", PROMPT, day="2026-11-24"))

    def test_content_change_is_new_article(self):
        other = content_hash("Nvidia earnings", "Datacenter revenue up 95%.")
        self.assertNotEqual(self.chash, other)


class StabilityRuleTest(unittest.TestCase):
    def test_llm_stable_overridden_by_conflicting_sources(self):
        signals = StabilitySignals(source_count=4, source_agreement=0.6,
                                   has_primary_source=False, contradiction_terms=2,
                                   time_span_hours=19)
        verdict = judge(signals, llm_stability="stable", llm_rationale="多家媒体一致报道")
        self.assertNotEqual(verdict.stability, "stable")
        self.assertIn("source_agreement", verdict.rule_trace)

    def test_llm_used_when_rules_neutral(self):
        signals = StabilitySignals(source_count=5, source_agreement=0.9,
                                   has_primary_source=True, contradiction_terms=0,
                                   time_span_hours=8)
        verdict = judge(signals, llm_stability="stable", llm_rationale="官方通报与两家通讯社一致")
        self.assertEqual(verdict.stability, "stable")

    def test_degraded_when_llm_absent(self):
        signals = StabilitySignals(source_count=2, source_agreement=0.7,
                                   has_primary_source=False, contradiction_terms=0,
                                   time_span_hours=3)
        verdict = judge(signals, llm_stability=None, llm_rationale="")
        self.assertTrue(verdict.degraded)
        self.assertIn(verdict.stability, {"developing", "contested"})


if __name__ == "__main__":
    unittest.main()
