"""数据层契约：schema、幂等写入、过滤、分页、全文搜索、统计。"""

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from pip_app import db, repo  # noqa: E402

SOURCES = [
    {"id": "cnn", "name": "CNN", "domain": "geopol", "lang": "en", "url": "https://cnn.com/rss", "tier": 1},
    {"id": "qbitai", "name": "量子位", "domain": "ai", "lang": "zh", "url": "https://qbitai.com/feed", "tier": 2},
]

ITEMS = [
    {"url": "https://a.com/1", "source_id": "cnn", "source_name": "CNN", "domain": "geopol",
     "lang": "en", "title": "US and China resume trade talks", "summary": "Tariffs dominate the agenda",
     "published_at": "2026-11-25T08:00:00Z", "fetched_at": "2026-11-25T09:00:00Z",
     "time_confidence": "high", "time_source": "item_pubDate", "content_hash": "h1"},
    {"url": "https://a.com/2", "source_id": "cnn", "source_name": "CNN", "domain": "geopol",
     "lang": "en", "title": "Election results delayed in swing state", "summary": "Officials cite recount",
     "published_at": "2026-11-24T08:00:00Z", "fetched_at": "2026-11-25T09:00:00Z",
     "time_confidence": "low", "time_source": "feed_updated", "content_hash": "h2"},
    {"url": "https://b.com/3", "source_id": "qbitai", "source_name": "量子位", "domain": "ai",
     "lang": "zh", "title": "新一代大模型发布", "summary": "推理能力显著提升",
     "published_at": "2026-11-25T07:00:00Z", "fetched_at": "2026-11-25T09:00:00Z",
     "time_confidence": "high", "time_source": "item_pubDate", "content_hash": "h3"},
]


class DbCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "t.db"
        self.conn = db.init(self.path)
        repo.upsert_sources(self.conn, SOURCES, geo={"cnn": ("US", "New York"), "qbitai": ("CN", "Beijing")})
        repo.insert_items(self.conn, ITEMS)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()


class SchemaTest(DbCase):
    def test_version_recorded(self):
        self.assertEqual(db.version(self.conn), db.SCHEMA_VERSION)

    def test_tables_exist(self):
        counts = db.table_counts(self.conn)
        self.assertEqual(counts["sources"], 2)
        self.assertEqual(counts["items"], 3)

    def test_init_is_idempotent(self):
        db.init(conn=self.conn)
        self.assertEqual(db.table_counts(self.conn)["items"], 3)

    def test_fts_table_populated_by_trigger(self):
        n = self.conn.execute("SELECT COUNT(*) FROM items_fts").fetchone()[0]
        self.assertEqual(n, 3)


class WriteTest(DbCase):
    def test_insert_is_idempotent_by_url(self):
        inserted, updated = repo.insert_items(self.conn, ITEMS)
        self.assertEqual((inserted, updated), (0, 3))
        self.assertEqual(db.table_counts(self.conn)["items"], 3)

    def test_update_keeps_original_published_at_when_missing(self):
        repo.insert_items(self.conn, [{"url": "https://a.com/1", "source_id": "cnn", "title": "US and China resume trade talks"}])
        row = self.conn.execute("SELECT published_at FROM items WHERE url = ?", ("https://a.com/1",)).fetchone()
        self.assertEqual(row["published_at"], "2026-11-25T08:00:00Z")

    def test_item_without_url_is_skipped(self):
        inserted, updated = repo.insert_items(self.conn, [{"title": "no url"}])
        self.assertEqual((inserted, updated), (0, 0))

    def test_source_update_keeps_country(self):
        repo.upsert_sources(self.conn, [{"id": "cnn", "name": "CNN International", "domain": "geopol"}])
        row = self.conn.execute("SELECT name, country FROM sources WHERE id='cnn'").fetchone()
        self.assertEqual(row["name"], "CNN International")
        self.assertEqual(row["country"], "US")

    def test_foreign_key_rejects_unknown_source(self):
        with self.assertRaises(sqlite3.IntegrityError):
            repo.insert_items(self.conn, [{"url": "https://x.com/9", "source_id": "ghost", "title": "x"}])


class QueryTest(DbCase):
    def test_filter_by_domain(self):
        out = repo.query_items(self.conn, domain="ai")
        self.assertEqual(out["total"], 1)
        self.assertEqual(out["items"][0]["source_id"], "qbitai")

    def test_filter_by_lang_and_conf(self):
        self.assertEqual(repo.query_items(self.conn, lang="zh")["total"], 1)
        self.assertEqual(repo.query_items(self.conn, conf="low")["total"], 1)

    def test_filter_by_source(self):
        self.assertEqual(repo.query_items(self.conn, source_id="cnn")["total"], 2)

    def test_sort_by_published_desc(self):
        out = repo.query_items(self.conn, sort="published")
        self.assertEqual(out["items"][0]["title"][:2], "US")

    def test_pagination(self):
        out = repo.query_items(self.conn, size=2, page=1)
        self.assertEqual(len(out["items"]), 2)
        self.assertEqual(out["pages"], 2)
        page2 = repo.query_items(self.conn, size=2, page=2)
        self.assertEqual(len(page2["items"]), 1)

    def test_size_is_clamped(self):
        self.assertLessEqual(repo.query_items(self.conn, size=9999)["size"], 200)

    def test_fts_english_search(self):
        out = repo.query_items(self.conn, q="trade")
        self.assertEqual(out["total"], 1)
        self.assertIn("trade", out["items"][0]["title"].lower())

    def test_fts_chinese_search(self):
        out = repo.query_items(self.conn, q="大模型")
        self.assertEqual(out["total"], 1)
        self.assertEqual(out["items"][0]["source_id"], "qbitai")

    def test_short_query_falls_back_to_like(self):
        out = repo.query_items(self.conn, q="US")
        self.assertEqual(out["total"], 1)

    def test_no_match_returns_empty(self):
        out = repo.query_items(self.conn, q="nonexistentkeyword")
        self.assertEqual(out["total"], 0)
        self.assertEqual(out["items"], [])


class StatsTest(DbCase):
    def test_stats_shape(self):
        s = repo.stats(self.conn)
        self.assertEqual(s["total"], 3)
        self.assertEqual(s["sources"], 2)
        self.assertEqual(s["domains"]["geopol"], 2)
        self.assertEqual(s["confidence"]["high"], 2)

    def test_sources_with_counts(self):
        rows = repo.sources_with_counts(self.conn)
        by_id = {r["id"]: r for r in rows}
        self.assertEqual(by_id["cnn"]["items"], 2)
        self.assertEqual(by_id["cnn"]["country"], "US")

    def test_runs_summary(self):
        repo.insert_run(self.conn, {"source_id": "cnn", "status": "ok", "elapsed_ms": 120, "item_count": 2})
        repo.insert_run(self.conn, {"source_id": "cnn", "status": "failed", "error": "boom"})
        self.conn.commit()
        rows = repo.runs_summary(self.conn)
        cnn = next(r for r in rows if r["source_id"] == "cnn")
        self.assertEqual(cnn["runs"], 2)
        self.assertEqual(cnn["ok"], 1)
        self.assertEqual(cnn["failed"], 1)

    def test_days(self):
        days = repo.days(self.conn)
        self.assertEqual(len(days), 1)
        self.assertEqual(days[0]["n"], 3)


if __name__ == "__main__":
    unittest.main()
