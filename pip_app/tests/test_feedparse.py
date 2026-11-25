"""解析层契约测试（A/B 组）：离线 fixture，不联网。"""

import unittest
from datetime import datetime, timezone
from pathlib import Path

from pip_app.feedparse import NotAFeed, parse_feed, summarize_html

FIX = Path(__file__).parent / "fixtures"


class RssParseTest(unittest.TestCase):
    def setUp(self):
        self.items, self.feed_updated = parse_feed((FIX / "rss2.xml").read_bytes())

    def test_extracts_all_items(self):
        self.assertEqual(len(self.items), 2)

    def test_title_is_trimmed(self):
        self.assertEqual(self.items[0]["title"], "Nvidia datacenter revenue up 94%")

    def test_link_and_guid_used_for_url(self):
        self.assertTrue(self.items[0]["url"].startswith("https://example.com/a"))
        self.assertEqual(self.items[1]["url"], "https://example.com/b")

    def test_cdata_description_is_stripped_to_text(self):
        self.assertEqual(self.items[0]["summary"], "Datacenter revenue up 94% year over year.")

    def test_pubdate_parsed_as_utc(self):
        self.assertEqual(self.items[0]["published_at"], datetime(2026, 11, 24, 1, 30, tzinfo=timezone.utc))

    def test_feed_updated_exposed_for_fallback(self):
        self.assertIsNotNone(self.feed_updated)
        self.assertEqual(self.feed_updated.year, 2026)

    def test_items_carry_source_timestamps_separately(self):
        self.assertIn("published_at", self.items[0])
        self.assertNotIn("fetched_at", self.items[0])  # fetched_at 由采集层注入


class AtomParseTest(unittest.TestCase):
    def setUp(self):
        self.items, self.feed_updated = parse_feed((FIX / "atom.xml").read_bytes())

    def test_extracts_entries(self):
        self.assertEqual(len(self.items), 2)

    def test_link_from_href_attribute(self):
        self.assertEqual(self.items[0]["url"], "https://example.org/atom-1")

    def test_iso_published_parsed(self):
        self.assertEqual(self.items[0]["published_at"], datetime(2026, 11, 24, 1, 45, tzinfo=timezone.utc))

    def test_missing_published_is_none(self):
        self.assertIsNone(self.items[1]["published_at"])

    def test_escaped_html_summary_is_unescaped_then_stripped(self):
        self.assertEqual(self.items[0]["summary"], "A short note on scaling.")


class EdgeCaseTest(unittest.TestCase):
    def test_empty_feed_returns_no_items(self):
        items, updated = parse_feed((FIX / "empty.xml").read_bytes())
        self.assertEqual(items, [])
        self.assertIsNotNone(updated)

    def test_html_page_raises_not_a_feed(self):
        with self.assertRaises(NotAFeed):
            parse_feed((FIX / "not-a-feed.html").read_bytes())

    def test_summary_truncated_to_limit(self):
        long_text = "word " * 500
        self.assertLessEqual(len(summarize_html(long_text, limit=220)), 221)

    def test_invalid_bytes_raise_not_a_feed(self):
        with self.assertRaises(NotAFeed):
            parse_feed(b"\x00\x01\x02 not xml at all")


if __name__ == "__main__":
    unittest.main()
