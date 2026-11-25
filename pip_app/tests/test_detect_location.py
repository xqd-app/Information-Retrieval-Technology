"""自动定位的契约：解析、降级、缓存、以及「出口 IP ≠ 真实位置」这一事实。"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from pip_app.tools.detect_location import (  # noqa: E402
    detect,
    load_cache,
    parse_ipapi,
    parse_ipinfo,
    parse_ipwho,
)

IPAPI = {"status": "success", "country": "Japan", "regionName": "Tokyo", "city": "Tokyo",
         "lat": 35.6289, "lon": 139.7915, "query": "203.0.113.7"}
IPWHO = {"success": True, "country": "Japan", "city": "Tokyo", "latitude": 35.68, "longitude": 139.69,
         "ip": "203.0.113.7", "connection": {"isp": "Example ISP"}}
IPINFO = {"ip": "203.0.113.7", "city": "Tokyo", "region": "Tokyo", "country": "JP",
          "loc": "35.6895,139.6917", "org": "AS1 Example"}


class ParserTest(unittest.TestCase):
    def test_ipapi_success(self):
        info = parse_ipapi(IPAPI)
        self.assertEqual(info["city"], "Tokyo")
        self.assertAlmostEqual(info["lat"], 35.6289)

    def test_ipapi_failure_status_returns_none(self):
        self.assertIsNone(parse_ipapi({"status": "fail", "message": "reserved range"}))

    def test_ipwho_success(self):
        info = parse_ipwho(IPWHO)
        self.assertEqual(info["org"], "Example ISP")
        self.assertAlmostEqual(info["lon"], 139.69)

    def test_ipinfo_loc_parsed(self):
        info = parse_ipinfo(IPINFO)
        self.assertAlmostEqual(info["lat"], 35.6895)
        self.assertAlmostEqual(info["lon"], 139.6917)

    def test_ipinfo_missing_loc_returns_none(self):
        self.assertIsNone(parse_ipinfo({"city": "Tokyo"}))


class DetectChainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "geo_self.json"
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def _fetcher(self, responses):
        def fetch(url):
            self.calls.append(url)
            for key, value in responses.items():
                if key in url:
                    if isinstance(value, Exception):
                        raise value
                    return value
            raise RuntimeError("no provider matched")
        return fetch

    def test_first_provider_wins(self):
        info = detect(cache_path=self.cache, force=True, fetcher=self._fetcher({"ip-api": IPAPI}))
        self.assertEqual(info["source"], "ip-api.com")
        self.assertAlmostEqual(info["lat"], 35.6289)
        self.assertEqual(len(self.calls), 1)

    def test_falls_back_to_next_provider(self):
        info = detect(
            cache_path=self.cache,
            force=True,
            fetcher=self._fetcher({"ip-api": RuntimeError("blocked"), "ipwho": IPWHO}),
        )
        self.assertEqual(info["source"], "ipwho.is")
        self.assertEqual(len(self.calls), 2)

    def test_all_providers_failing_returns_none(self):
        info = detect(
            cache_path=self.cache,
            force=True,
            fetcher=self._fetcher({"ip-api": RuntimeError("x"), "ipwho": RuntimeError("y"), "ipinfo": RuntimeError("z")}),
        )
        self.assertIsNone(info)

    def test_result_is_cached_and_reused(self):
        fetch = self._fetcher({"ip-api": IPAPI})
        detect(cache_path=self.cache, force=True, fetcher=fetch, now=1000.0)
        self.assertEqual(len(self.calls), 1)

        fetch2 = self._fetcher({"ip-api": {**IPAPI, "city": "Osaka"}})
        info = detect(cache_path=self.cache, ttl=86400, fetcher=fetch2, now=2000.0)
        self.assertEqual(info["city"], "Tokyo")   # 命中缓存
        self.assertEqual(len(self.calls), 1)      # 没有新请求

    def test_cache_expires(self):
        detect(cache_path=self.cache, force=True, fetcher=self._fetcher({"ip-api": IPAPI}), now=1000.0)
        self.assertIsNone(load_cache(self.cache, ttl=60, now=1000.0 + 120))

    def test_no_cache_file_returns_none(self):
        self.assertIsNone(load_cache(self.cache))


class HonestyTest(unittest.TestCase):
    """检测到的是出口 IP 位置，必须能看出来（源 + IP 都要带回来）。"""

    def test_source_and_ip_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            info = detect(cache_path=Path(tmp) / "g.json", force=True,
                          fetcher=lambda url: IPAPI)
        self.assertEqual(info["ip"], "203.0.113.7")
        self.assertIn("source", info)
        self.assertIn("detected_at", info)


if __name__ == "__main__":
    unittest.main()
