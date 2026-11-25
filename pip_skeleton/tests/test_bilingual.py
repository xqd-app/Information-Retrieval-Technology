"""§5.7 双语交付（重要内容强制双文）——先写测试，后写实现。"""

import unittest

from pip.bilingual import (
    BilingualDoc,
    Glossary,
    MissingBilingualError,
    Term,
    TranslationCache,
    check_numeric_consistency,
    check_terms,
    numbers,
    translate_with_cache,
)

GLOSSARY = Glossary([
    Term("world model", "世界模型", forbid=("全球模型", "世界建模")),
    Term("inference-time compute", "推理期算力", forbid=("推理时间计算",)),
    Term("context window", "上下文窗口", forbid=("语境窗口",)),
])


class TermCheckTest(unittest.TestCase):
    def test_violation_detected_when_forbidden_translation_used(self):
        violations = check_terms("This world model is new.", "这个全球模型很新。", GLOSSARY)
        self.assertEqual(len(violations), 1)
        self.assertIn("全球模型", violations[0])

    def test_correct_translation_passes(self):
        self.assertEqual(check_terms("This world model is new.", "这个新世界模型很新。", GLOSSARY), [])

    def test_only_terms_present_in_text_are_selected(self):
        matched = GLOSSARY.matches("The context window doubled.")
        self.assertEqual([t.en for t in matched], ["context window"])

    def test_forbid_list_does_not_trigger_when_term_absent(self):
        self.assertEqual(check_terms("Nothing relevant here.", "这里没有相关内容。", GLOSSARY), [])


class NumericConsistencyTest(unittest.TestCase):
    def test_numbers_extracted(self):
        self.assertEqual(numbers("营收增长 94%，达 35.08 亿美元"), {"94", "35.08"})

    def test_mismatch_detected(self):
        ok, detail = check_numeric_consistency("营收增长 94%", "Revenue grew 49%")
        self.assertFalse(ok)
        self.assertIn("94", detail)

    def test_consistent_pair_passes(self):
        ok, _ = check_numeric_consistency("营收增长 94%，达 350 亿美元", "Revenue grew 94% to 35 billion")
        self.assertTrue(ok)

    def test_missing_number_in_translation_is_flagged(self):
        ok, detail = check_numeric_consistency("共 37 条", "There are items")
        self.assertFalse(ok)
        self.assertIn("37", detail)


class BilingualDocTest(unittest.TestCase):
    def test_p0_content_requires_both_languages(self):
        with self.assertRaises(MissingBilingualError):
            BilingualDoc(title_zh="今日主线", title_en="", summary_zh="摘要", summary_en="Summary")

    def test_complete_doc_is_valid(self):
        doc = BilingualDoc(title_zh="今日主线", title_en="Today's thread",
                           summary_zh="摘要", summary_en="Summary")
        self.assertTrue(doc.is_complete)
        doc.validate()

    def test_terms_rendered_for_display(self):
        doc = BilingualDoc(title_zh="世界模型", title_en="World model",
                           summary_zh="摘要", summary_en="Summary",
                           terms=(("world model", "世界模型"),))
        self.assertEqual(doc.term_pairs(), [("world model", "世界模型")])


class TranslationCacheTest(unittest.TestCase):
    def setUp(self):
        self.cache = TranslationCache(":memory:")
        self.calls = 0

    def tearDown(self):
        self.cache.close()

    def _translate(self, text, src, dst):
        self.calls += 1
        return f"[{dst}]{text}"

    def test_first_call_translates_and_caches(self):
        out, hit = translate_with_cache("world model", "en", "zh", self._translate, self.cache)
        self.assertEqual(out, "[zh]world model")
        self.assertFalse(hit)
        self.assertEqual(self.calls, 1)

    def test_second_call_hits_cache_without_translating(self):
        translate_with_cache("world model", "en", "zh", self._translate, self.cache)
        out, hit = translate_with_cache("world model", "en", "zh", self._translate, self.cache)
        self.assertTrue(hit)
        self.assertEqual(out, "[zh]world model")
        self.assertEqual(self.calls, 1)

    def test_different_target_language_misses(self):
        translate_with_cache("hello", "en", "zh", self._translate, self.cache)
        _, hit = translate_with_cache("hello", "en", "ja", self._translate, self.cache)
        self.assertFalse(hit)
        self.assertEqual(self.calls, 2)


if __name__ == "__main__":
    unittest.main()
