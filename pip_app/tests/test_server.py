"""生产化服务的契约：健康检查、指标、gzip、缓存头、错误处理、全球扫描接口。"""

import gzip
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

from pip_app.server import Metrics, make_server  # noqa: E402


class ServerCase(unittest.TestCase):
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

    def get(self, path, **headers):
        req = urllib.request.Request(self.base + path, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()


class HealthTest(ServerCase):
    def test_healthz_ok(self):
        status, _, body = self.get("/healthz")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["status"], "ok")
        self.assertGreater(payload["items"], 0)
        self.assertIn("date", payload)

    def test_root_serves_html(self):
        status, headers, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn("PIP".encode(), body)

    def test_unknown_path_is_404(self):
        status, _, _ = self.get("/nope")
        self.assertEqual(status, 404)


class ApiTest(ServerCase):
    def test_items_filter_by_domain(self):
        status, _, body = self.get("/api/items?domain=ai&limit=5")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertLessEqual(len(payload["items"]), 5)
        self.assertTrue(all(i["domain"] == "ai" for i in payload["items"]))

    def test_meta_shape(self):
        status, _, body = self.get("/api/meta")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        for key in ("total", "sources", "domains", "confidence", "languages"):
            self.assertIn(key, payload)

    def test_world_endpoint(self):
        status, _, body = self.get("/api/world")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertIn("regions", payload)
        self.assertIn("coverage", payload)
        self.assertIn("blind_spots", payload)
        self.assertGreaterEqual(payload["coverage"]["regions_total"], 5)

    def test_health_endpoint(self):
        status, _, body = self.get("/api/health")
        self.assertEqual(status, 200)
        self.assertIn("rows", json.loads(body))


class CompressionTest(ServerCase):
    def test_gzip_when_accepted(self):
        status, headers, body = self.get("/api/items?limit=50", **{"Accept-Encoding": "gzip"})
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Content-Encoding"), "gzip")
        self.assertTrue(json.loads(gzip.decompress(body))["items"])

    def test_no_gzip_without_header(self):
        status, headers, body = self.get("/api/items?limit=5")
        self.assertEqual(status, 200)
        self.assertIsNone(headers.get("Content-Encoding"))
        self.assertIn("items", json.loads(body))

    def test_vary_header_is_set(self):
        _, headers, _ = self.get("/api/items?limit=5", **{"Accept-Encoding": "gzip"})
        self.assertIn("Accept-Encoding", headers.get("Vary", ""))


class CacheHeaderTest(ServerCase):
    def test_api_is_not_cached(self):
        _, headers, _ = self.get("/api/meta")
        self.assertIn("no-store", headers.get("Cache-Control", ""))

    def test_html_is_not_cached(self):
        _, headers, _ = self.get("/")
        self.assertIn("no-cache", headers.get("Cache-Control", ""))

    def test_screens_are_cached(self):
        status, headers, _ = self.get("/screens/pip-v17-hacker.png")
        if status != 200:
            self.skipTest("截图不存在")
        self.assertIn("max-age", headers.get("Cache-Control", ""))


class MetricsTest(unittest.TestCase):
    def test_counter_and_render(self):
        m = Metrics()
        m.inc("requests_total")
        m.inc("requests_total", 2)
        m.observe(0.02)
        m.observe(0.04)
        text = m.render()
        self.assertIn("pip_requests_total 3", text)
        self.assertIn("pip_request_seconds_count 2", text)
        self.assertIn("# TYPE pip_requests_total counter", text)

    def test_gauge(self):
        m = Metrics()
        m.set("pip_items", 524)
        self.assertIn("pip_items 524", m.render())


class SecurityTest(ServerCase):
    def test_path_traversal_blocked(self):
        status, _, _ = self.get("/screens/../../config.py")
        self.assertIn(status, (400, 403, 404))

    def test_only_allowed_static_prefix(self):
        status, _, _ = self.get("/../pip_app/config.py")
        self.assertIn(status, (400, 403, 404))


if __name__ == "__main__":
    unittest.main()
