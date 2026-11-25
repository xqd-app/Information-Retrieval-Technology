"""PIP 本地服务：仪表盘 + JSON API + 源健康。

只用标准库（http.server）。默认可直接 `python -m pip_app.serve` 起来，
访问 http://127.0.0.1:8765/ 就是当日报纸，/api/* 给下游 Agent 或前端取数。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, urlsplit

from . import config
from .health_report import load_rows, summarize

DEFAULT_PORT = 8765
WEB_DIR = Path(__file__).resolve().parent / "web"
LATEST_ITEMS: Path = config.ITEMS_DIR / "2026-11-24.jsonl"


def filter_items(
    items: Iterable[dict],
    *,
    domain: str = "all",
    conf: str = "all",
    q: str = "",
    limit: int | None = None,
) -> list[dict]:
    """纯函数：域 / 可信度 / 关键词三重筛选，缺字段不炸。"""
    needle = (q or "").strip().lower()
    out: list[dict] = []
    for item in items:
        if domain != "all" and item.get("domain") != domain:
            continue
        if conf != "all" and item.get("time_confidence") != conf:
            continue
        if needle:
            haystack = f"{item.get('title') or ''} {item.get('summary') or ''}".lower()
            if needle not in haystack:
                continue
        out.append(item)
    if limit is not None:
        out = out[:limit]
    return out


def build_meta(items: Iterable[dict], health_rows: Iterable[dict] | None = None) -> dict[str, Any]:
    rows = list(items)
    domains = Counter(row.get("domain") or "unknown" for row in rows)
    confidence = Counter(row.get("time_confidence") or "unknown" for row in rows)
    languages = Counter(row.get("lang") or "unknown" for row in rows)
    health = Counter((row.get("status") or "unknown") for row in (health_rows or []))
    return {
        "total": len(rows),
        "sources": len({row.get("source_id") for row in rows if row.get("source_id")}),
        "domains": dict(domains),
        "confidence": dict(confidence),
        "languages": dict(languages),
        "health": dict(health),
        "daily_candidates": sum(1 for row in rows if row.get("time_confidence") == "high"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def latest_items_path() -> Path:
    files = sorted(config.ITEMS_DIR.glob("*.jsonl"))
    return files[-1] if files else LATEST_ITEMS


def load_items() -> list[dict]:
    path = latest_items_path()
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_health() -> list[dict]:
    active = {s.id for s in _active_sources()}
    rows = load_rows()
    latest_day = rows[-1]["run_at"][:10] if rows else ""
    return [
        row for row in rows
        if row.get("run_at", "")[:10] == latest_day and row.get("source_id") in active
    ]


def _active_sources():
    from .collect import load_sources

    try:
        return load_sources()
    except Exception:
        return []


class Handler(BaseHTTPRequestHandler):
    server_version = "PIP/0.2"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler 约定
        parsed = urlsplit(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path in {"/", "/index.html"}:
            return self._send_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
        if path == "/api/items":
            items = load_items()
            filtered = filter_items(
                items,
                domain=query.get("domain", ["all"])[0],
                conf=query.get("conf", ["all"])[0],
                q=query.get("q", [""])[0],
                limit=int(query["limit"][0]) if "limit" in query else None,
            )
            return self._send_json({"count": len(filtered), "items": filtered})
        if path == "/api/meta":
            return self._send_json(build_meta(load_items(), load_health()))
        if path == "/api/health":
            health = summarize(load_health())
            return self._send_json(
                {
                    "sources": len(health),
                    "red": [h.source_id for h in health if h.flag == "RED"],
                    "rows": [
                        {
                            "source_id": h.source_id,
                            "source_name": h.source_name,
                            "domain": h.domain,
                            "flag": h.flag,
                            "success_rate": round(h.success_rate, 2),
                            "avg_ms": h.avg_ms,
                        }
                        for h in health
                    ],
                }
            )
        if path.startswith("/screens/"):
            return self._send_file(WEB_DIR / path.lstrip("/"), "image/png")
        return self._send_json({"error": "not found", "path": path}, status=404)

    def _send_json(self, payload: dict, *, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            return self._send_json({"error": "file not found", "path": str(path)}, status=404)
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:  # 安静一点
        sys.stderr.write("[pip] " + (fmt % args) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pip_app.serve", description="PIP 本地服务")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--refresh", action="store_true", help="启动前先抓一次最新数据")
    args = parser.parse_args(argv)

    if args.refresh:
        from .collect import collect, load_sources, write_outputs

        outcome = collect(load_sources())
        paths = write_outputs(outcome)
        print(f"已刷新：{len(outcome.items)} 条 -> {paths['items']}")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    meta = build_meta(load_items(), load_health())
    print(f"PIP 服务已启动  http://{args.host}:{args.port}/")
    print(f"  条数 {meta['total']} 源 {meta['sources']} 高可信 {meta['confidence'].get('high', 0)}")
    print(f"  API: /api/meta  /api/items?domain=ai&conf=high&q=nvidia  /api/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
