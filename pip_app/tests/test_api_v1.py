"""v1 API 的契约：分页、搜索、聚合、DB 回落。"""

import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packetvoyage-master" / "src"))

from pip_app import db, repo  # noqa: E402
from pip_app.server import make_server  # noqa: E402


class ApiV1Case(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.port = make_server(host="127.0.0.1", port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path, timeout=10) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")


class ItemsV1Test(ApiV1Case):
    def test_pagination_shape(self):
        status, body = self.get("/api/v1/items?size=5&page=1")
        self.assertEqual(status, 200)
        self.assertLessEqual(len(body["items"]), 5)
        for key in ("total", "page", "size", "pages", "source"):
            self.assertIn(key, body)
        self.assertIn(body["source"], ("db", "jsonl"))

    def test_domain_filter(self):
        status, body = self.get("/api/v1/items?domain=ai&size=3")
        self.assertEqual(status, 200)
        self.assertTrue(all(i["domain"] == "ai" for i in body["items"]))

    def test_search_returns_results(self):
        status, body = self.get("/api/v1/items?q=AI&size=5")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(body["total"], 0)

    def test_bad_page_number_does_not_crash(self):
        status, body = self.get("/api/v1/items?page=abc&size=xyz")
        self.assertEqual(status, 200)
        self.assertEqual(body["page"], 1)

    def test_page_beyond_range_is_empty_not_error(self):
        status, body = self.get("/api/v1/items?page=9999&size=10")
        self.assertEqual(status, 200)
        self.assertEqual(body["items"], [])


class StatsV1Test(ApiV1Case):
    def test_stats_has_counts(self):
        status, body = self.get("/api/v1/stats")
        self.assertEqual(status, 200)
        self.assertIn("source", body)
        self.assertIn("total", body)


class SourcesV1Test(ApiV1Case):
    def test_sources_list(self):
        status, body = self.get("/api/v1/sources")
        self.assertEqual(status, 200)
        self.assertIn("sources", body)
        self.assertIn("count", body)


class DaysV1Test(ApiV1Case):
    def test_days(self):
        status, body = self.get("/api/v1/days")
        self.assertEqual(status, 200)
        self.assertIsInstance(body["days"], list)


class HealthV1Test(ApiV1Case):
    def test_health_aggregate(self):
        status, body = self.get("/api/v1/health")
        self.assertEqual(status, 200)
        self.assertIsInstance(body["rows"], list)


class HealthzDbTest(ApiV1Case):
    def test_healthz_reports_db(self):
        status, body = self.get("/healthz")
        self.assertEqual(status, 200)
        self.assertIn("db", body)
        self.assertIn("available", body["db"])


class FallbackTest(unittest.TestCase):
    """库不存在时必须回落 JSONL，而不是 500。"""

    def test_with_db_returns_none_when_missing(self):
        from pip_app.server import with_db

        import os

        old = os.environ.get("PIP_DB")
        os.environ["PIP_DB"] = "/nonexistent/path/x.db"
        try:
            self.assertIsNone(with_db(lambda conn: 1))
        finally:
            if old is None:
                os.environ.pop("PIP_DB", None)
            else:
                os.environ["PIP_DB"] = old


if __name__ == "__main__":
    unittest.main()
