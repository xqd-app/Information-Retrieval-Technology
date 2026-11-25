"""采集层回归测试：gzip 解压、时间判定注入、当日合并去重、失败不外溢。

说明：其中 gzip 与 normalize 的用例是在实现之后补的**回归锁定**（characterization），
不是 TDD 驱动——真实缺陷（deepmind 无视 Accept-Encoding 返回 gzip）先被发现，才补的测试。
"""

import gzip
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from pip_app import collect as collector
from pip_app.collect import Source, _decompress, _merge_existing, normalize, run_source

SRC = Source(id="fixture", name="Fixture", domain="ai", lang="en", url="https://example.com/rss")


def raw_item(title="Title", url="https://example.com/a", published=None):
    return {"title": title, "url": url, "published_at": published, "summary": "s"}


class DecompressTest(unittest.TestCase):
    def test_gzip_by_magic_bytes(self):
        payload = b"<?xml version='1.0'?><rss/>"
        self.assertEqual(_decompress(gzip.compress(payload), ""), payload)

    def test_gzip_by_header_even_without_magic(self):
        payload = gzip.compress(b"<rss/>")
        self.assertEqual(_decompress(payload, "gzip"), b"<rss/>")

    def test_plain_payload_untouched(self):
        payload = b"<rss><channel/></rss>"
        self.assertEqual(_decompress(payload, ""), payload)

    def test_corrupt_gzip_falls_back_to_raw(self):
        broken = b"\x1f\x8bnot-really-gzip"
        self.assertEqual(_decompress(broken, "gzip"), broken)


class NormalizeTest(unittest.TestCase):
    def test_fresh_pubdate_is_high(self):
        item = raw_item(published=datetime.now(timezone.utc) - timedelta(hours=1))
        rows = normalize(SRC, [item], None)
        self.assertEqual(rows[0]["time_confidence"], "high")
        self.assertIsNotNone(rows[0]["published_at"])

    def test_old_pubdate_demoted_to_low(self):
        item = raw_item(published=datetime.now(timezone.utc) - timedelta(days=45))
        rows = normalize(SRC, [item], None)
        self.assertEqual(rows[0]["time_confidence"], "low")
        self.assertIsNone(rows[0]["published_at"])

    def test_shared_timestamp_across_items_demoted(self):
        stamp = datetime.now(timezone.utc) - timedelta(hours=2)
        items = [raw_item(url=f"https://example.com/{i}", published=None) for i in range(3)]
        rows = normalize(SRC, items, stamp)
        self.assertTrue(all(r["time_confidence"] == "low" for r in rows))

    def test_stable_id_from_content(self):
        rows = normalize(SRC, [raw_item()], None)
        self.assertEqual(len(rows[0]["id"]), 16)
        self.assertEqual(rows[0]["source_id"], "fixture")

    def test_limit_per_source_applied(self):
        items = [raw_item(url=f"https://example.com/{i}") for i in range(100)]
        rows = normalize(SRC, items, None)
        self.assertLessEqual(len(rows), collector.config.LIMIT_PER_SOURCE)


class MergeExistingTest(unittest.TestCase):
    def test_merges_by_url_and_keeps_newest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "items.jsonl"
            old = {"url": "https://a.com/1", "published_at": "2026-11-23T01:00:00+00:00", "title": "old"}
            newer = {"url": "https://a.com/1", "published_at": "2026-11-24T01:00:00+00:00", "title": "new"}
            other = {"url": "https://a.com/2", "published_at": "2026-11-22T01:00:00+00:00", "title": "other"}
            path.write_text(json.dumps(old) + "\n", encoding="utf-8")
            merged = _merge_existing(path, [newer, other])
            by_url = {row["url"]: row for row in merged}
            self.assertEqual(by_url["https://a.com/1"]["title"], "new")
            self.assertIn("https://a.com/2", by_url)
            self.assertEqual(len(merged), 2)


class RetryTest(unittest.TestCase):
    """网络层故障（SSL EOF / 连接重置 / 超时）必须重试，源级故障（403/404）不重试。"""

    def test_transient_ssl_error_is_retried_then_succeeds(self):
        import urllib.error

        calls = {"n": 0}
        payload = b"<rss><channel><item><title>T</title><link>https://x/1</link></item></channel></rss>"

        def flaky(url, timeout=None):
            calls["n"] += 1
            if calls["n"] < 3:
                raise urllib.error.URLError("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred")
            return payload

        with mock.patch.object(collector, "_request_once", side_effect=flaky), \
             mock.patch.object(collector.time, "sleep", return_value=None):
            run = run_source(SRC)
        self.assertEqual(run.status, "ok")
        self.assertEqual(calls["n"], 3)

    def test_retries_exhausted_records_failure(self):
        import urllib.error

        with mock.patch.object(collector, "_request_once",
                               side_effect=urllib.error.URLError("timed out")), \
             mock.patch.object(collector.time, "sleep", return_value=None):
            run = run_source(SRC)
        self.assertEqual(run.status, "unreachable")

    def test_http_404_not_retried(self):
        import urllib.error

        calls = {"n": 0}

        def not_found(url, timeout=None):
            calls["n"] += 1
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

        with mock.patch.object(collector, "_request_once", side_effect=not_found), \
             mock.patch.object(collector.time, "sleep", return_value=None):
            run = run_source(SRC)
        self.assertEqual(run.status, "failed")
        self.assertEqual(calls["n"], 1, "4xx 不应重试")


class RetryTimeoutTest(unittest.TestCase):
    """重试要用更短的超时：3×15s 会让一个坏源吃掉 45s+，把整轮拖到预算边缘。"""

    def test_first_attempt_uses_full_timeout_then_shorter(self):
        import urllib.error

        seen = []

        def flaky(url, timeout=None):
            seen.append(timeout)
            if len(seen) < 3:
                raise urllib.error.URLError("timed out")
            return b"<rss><channel><item><title>T</title><link>https://x/1</link></item></channel></rss>"

        with mock.patch.object(collector, "_request_once", side_effect=flaky), \
             mock.patch.object(collector.time, "sleep", return_value=None):
            run = run_source(SRC)
        self.assertEqual(run.status, "ok")
        self.assertEqual(seen[0], collector.config.TIMEOUT_SECONDS)
        self.assertTrue(all(t == collector.config.RETRY_TIMEOUT_SECONDS for t in seen[1:]))


class RunSourceIsolationTest(unittest.TestCase):
    def test_not_a_feed_recorded_as_failed(self):
        with mock.patch.object(collector, "_request", return_value=b"<!DOCTYPE html><html></html>"):
            run = run_source(SRC)
        self.assertEqual(run.status, "failed")
        self.assertIn("not_a_feed", run.error)

    def test_empty_feed_is_zero_result_not_ok(self):
        payload = Path(__file__).parent.joinpath("fixtures/empty.xml").read_bytes()
        with mock.patch.object(collector, "_request", return_value=payload):
            run = run_source(SRC)
        self.assertEqual(run.status, "zero_result")
        self.assertNotEqual(run.status, "ok")

    def test_http_error_recorded(self):
        import urllib.error

        err = urllib.error.HTTPError(SRC.url, 403, "Forbidden", {}, None)  # type: ignore[arg-type]
        with mock.patch.object(collector, "_request", side_effect=err):
            run = run_source(SRC)
        self.assertEqual(run.status, "failed")
        self.assertIn("403", run.error)

    def test_unexpected_exception_does_not_escape(self):
        with mock.patch.object(collector, "_request", side_effect=RuntimeError("boom")):
            run = run_source(SRC)
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.error, "RuntimeError")


if __name__ == "__main__":
    unittest.main()
