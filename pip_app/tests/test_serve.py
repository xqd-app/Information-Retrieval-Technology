"""本地服务契约：筛选逻辑与元信息（不依赖 HTTP，可直接单测）。"""

import unittest

from pip_app.serve import build_meta, filter_items

ITEMS = [
    {"source_id": "a", "domain": "ai", "time_confidence": "high", "lang": "en",
     "title": "Nvidia beats estimates", "summary": "Datacenter revenue up 94%"},
    {"source_id": "b", "domain": "geopol", "time_confidence": "low", "lang": "en",
     "title": "Sanctions on North Korea", "summary": "A barge was found"},
    {"source_id": "c", "domain": "ai", "time_confidence": "high", "lang": "zh",
     "title": "我国牵头 AI 国际标准", "summary": "市场监管总局"},
]


class FilterItemsTest(unittest.TestCase):
    def test_no_filter_returns_all(self):
        self.assertEqual(len(filter_items(ITEMS)), 3)

    def test_domain_filter(self):
        self.assertEqual([i["source_id"] for i in filter_items(ITEMS, domain="ai")], ["a", "c"])

    def test_confidence_filter(self):
        self.assertEqual([i["source_id"] for i in filter_items(ITEMS, conf="low")], ["b"])

    def test_query_matches_title_case_insensitive(self):
        self.assertEqual([i["source_id"] for i in filter_items(ITEMS, q="nvidia")], ["a"])

    def test_query_matches_summary(self):
        self.assertEqual([i["source_id"] for i in filter_items(ITEMS, q="barge")], ["b"])

    def test_query_matches_chinese(self):
        self.assertEqual([i["source_id"] for i in filter_items(ITEMS, q="国际标准")], ["c"])

    def test_filters_combine(self):
        self.assertEqual(filter_items(ITEMS, domain="ai", conf="high", q="标准"), [ITEMS[2]])

    def test_unknown_domain_returns_empty(self):
        self.assertEqual(filter_items(ITEMS, domain="sports"), [])

    def test_missing_fields_do_not_crash(self):
        broken = [{"title": None, "summary": None}]
        self.assertEqual(len(filter_items(broken, q="x")), 0)

    def test_limit_applied(self):
        self.assertEqual(len(filter_items(ITEMS, limit=2)), 2)


class MetaTest(unittest.TestCase):
    def test_counts_and_distribution(self):
        meta = build_meta(ITEMS, health_rows=[{"status": "ok"}, {"status": "failed"}])
        self.assertEqual(meta["total"], 3)
        self.assertEqual(meta["domains"], {"ai": 2, "geopol": 1})
        self.assertEqual(meta["confidence"], {"high": 2, "low": 1})
        self.assertEqual(meta["languages"], {"en": 2, "zh": 1})
        self.assertEqual(meta["sources"], 3)
        self.assertEqual(meta["health"], {"ok": 1, "failed": 1})

    def test_empty_items(self):
        meta = build_meta([])
        self.assertEqual(meta["total"], 0)
        self.assertEqual(meta["domains"], {})
        self.assertEqual(meta["health"], {})

    def test_ai_ready_count_excludes_low_confidence(self):
        meta = build_meta(ITEMS)
        self.assertEqual(meta["daily_candidates"], 2)  # 只有 high 可信的能进日报


if __name__ == "__main__":
    unittest.main()
