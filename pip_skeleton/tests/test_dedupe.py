"""C 组：去重（对应 §12 测试矩阵 C1–C4）。"""

import unittest
from datetime import datetime, timezone

from pip.dedupe import Item, dedupe, jaccard, normalize_title, normalize_url, tokens

EARLY = datetime(2026, 11, 24, 1, 0, tzinfo=timezone.utc)
LATE = datetime(2026, 11, 24, 2, 0, tzinfo=timezone.utc)


def item(title, url, published=LATE):
    return Item(title=title, url=url, published_at=published)


class NormalizeTest(unittest.TestCase):
    def test_c1_url_tracking_params_removed(self):
        a = normalize_url("https://Example.com/post/?utm_source=x&id=3&spm=9#frag")
        b = normalize_url("https://example.com/post?id=3")
        self.assertEqual(a, b)

    def test_c1_trailing_slash_removed(self):
        self.assertEqual(normalize_url("http://a.com/x/"), normalize_url("http://a.com/x"))

    def test_title_normalized(self):
        self.assertEqual(normalize_title("OpenAI 发布 GPT-5！"), normalize_title("openai 发布 gpt 5"))


class DedupeTest(unittest.TestCase):
    def test_c1_same_url_after_normalization_merged(self):
        items = [
            item("Title A", "https://x.com/a?utm_source=rss", EARLY),
            item("Title A", "https://x.com/a", LATE),
        ]
        self.assertEqual(len(dedupe(items)), 1)

    def test_c2_same_title_keeps_newest(self):
        result = dedupe([item("Same Title", "https://x.com/1", EARLY),
                         item("Same Title", "https://y.com/2", LATE)])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].url, "https://y.com/2")

    def test_c3_threshold_boundary(self):
        base = "alpha beta gamma delta epsilon zeta eta theta"
        near = "alpha beta gamma delta epsilon zeta eta theta iota"  # jaccard 8/9 -> 合并
        far = "alpha beta gamma delta epsilon zeta eta omega"         # jaccard 7/9 -> 保留
        self.assertGreaterEqual(jaccard(tokens(base), tokens(near)), 0.85)
        self.assertLess(jaccard(tokens(base), tokens(far)), 0.85)

        merged = dedupe([item(base, "https://a.com/1"), item(near, "https://a.com/2")])
        self.assertEqual(len(merged), 1)

        kept = dedupe([item(base, "https://b.com/1"), item(far, "https://b.com/2")])
        self.assertEqual(len(kept), 2)

    def test_c4_different_headline_same_event_not_merged(self):
        a = item("Nvidia beats earnings expectations on datacenter demand",
                 "https://reuters.com/a")
        b = item("Chipmaker Nvidia posts record quarterly revenue",
                 "https://apnews.com/b")
        self.assertEqual(len(dedupe([a, b])), 2)

    def test_short_titles_never_fuzzy_merged(self):
        self.assertEqual(len(dedupe([item("AI news", "https://a.com/1"),
                                     item("AI news today", "https://a.com/2")])), 2)

    def test_cross_language_not_merged(self):
        en = item("Nvidia reports record revenue for the quarter",
                  "https://a.com/1")
        zh = item("英伟达公布季度营收创纪录 数据中心业务增长显著",
                  "https://b.com/2")
        self.assertEqual(len(dedupe([en, zh])), 2)

    def test_chinese_bigram_similarity(self):
        a = "英伟达公布季度财报 数据中心营收创下历史新高"
        b = "英伟达公布季度财报 数据中心营收创下历史新高 股价上涨"
        self.assertGreaterEqual(jaccard(tokens(a), tokens(b)), 0.6)


if __name__ == "__main__":
    unittest.main()
