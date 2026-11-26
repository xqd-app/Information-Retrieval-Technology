"""PIP 生产服务：仪表盘 + JSON API + 健康检查 + Prometheus 指标。

与 `pip_app.serve` 的区别（serve 是本地调试用的最小实现）：
    1. /healthz 给编排系统探活，/metrics 给监控抓取
    2. 全站 gzip（>1 KB 且客户端支持时）
    3. 缓存策略分层：HTML/API 不缓存，截图长缓存
    4. 结构化请求日志（JSON 行），含耗时与状态码
    5. 优雅关闭（SIGTERM/SIGINT）
    6. 可选后台定时采集（PIP_AUTO_COLLECT=1）
    7. /api/world：全球覆盖扫描

零第三方依赖，只用标准库，直接 `python -m pip_app.server`。

环境变量：
    PIP_HOST=0.0.0.0        PIP_PORT=8080
    PIP_DATA_DIR / PIP_WEB_DIR
    PIP_LOG_LEVEL=INFO      PIP_AUTO_COLLECT=0
    PIP_COLLECT_INTERVAL=21600（秒，默认 6 小时）
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import signal
import sys
import threading
import time
from collections import Counter
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from . import config
from .health_report import load_rows, summarize
from . import auth
from . import db as database
from . import repo
from .serve import build_meta, filter_items
from .world_scan import load_items as load_items_file
from .world_scan import load_sources, scan

LOG = logging.getLogger("pip.server")

STATIC_PREFIX = "/screens/"
GZIP_MIN_BYTES = 1024


# ---------------------------------------------------------------- 指标
class Metrics:
    """极简 Prometheus 文本导出（counters + gauges + 耗时摘要）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Counter[str] = Counter()
        self._gauges: dict[str, float] = {}
        self._obs: list[float] = []

    def inc(self, name: str, value: float = 1) -> None:
        with self._lock:
            self._counters[name] += value

    def set(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def observe(self, seconds: float) -> None:
        with self._lock:
            self._obs.append(seconds)
            if len(self._obs) > 5000:
                del self._obs[:2500]

    def render(self) -> str:
        with self._lock:
            counters = dict(self._counters)
            gauges = dict(self._gauges)
            obs = list(self._obs)
        lines = []
        for name, value in sorted(counters.items()):
            metric = name if name.startswith("pip_") else f"pip_{name}"
            lines.append(f"# TYPE {metric} counter")
            lines.append(f"{metric} {value:g}")
        for name, value in sorted(gauges.items()):
            metric = name if name.startswith("pip_") else f"pip_{name}"
            if not any(line.startswith(f"# TYPE {metric} ") for line in lines):
                lines.append(f"# TYPE {metric} gauge")
            lines.append(f"{metric} {value:g}")
        total = sum(obs)
        lines.append("# TYPE pip_request_seconds summary")
        lines.append(f"pip_request_seconds_count {len(obs)}")
        lines.append(f"pip_request_seconds_sum {total:.6f}")
        if obs:
            lines.append(f"pip_request_seconds_avg {(total / len(obs)):.6f}")
        return "\n".join(lines) + "\n"


METRICS = Metrics()


# ---------------------------------------------------------------- 数据读取
def data_dir() -> Path:
    return Path(os.environ.get("PIP_DATA_DIR", config.DATA_DIR))


def web_dir() -> Path:
    return Path(os.environ.get("PIP_WEB_DIR", Path(__file__).resolve().parent / "web"))


def sources_file() -> Path:
    return Path(os.environ.get("PIP_SOURCES", config.SOURCES_FILE))


def latest_items_path() -> Path:
    files = sorted((data_dir() / "items").glob("*.jsonl"))
    return files[-1] if files else data_dir() / "items" / "1970-01-01.jsonl"


def read_items() -> list[dict]:
    path = latest_items_path()
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_health(active_ids: set[str] | None = None) -> list[dict]:
    path = data_dir() / "source_health.jsonl"
    rows = summarize(load_rows(path), active_ids=active_ids or set())
    return [
        {
            "source_id": h.source_id, "source_name": h.source_name, "domain": h.domain,
            "flag": h.flag, "success_rate": round(h.success_rate, 2),
            "ok": h.ok, "zero": h.zero, "failed": h.failed,
            "unreachable": h.unreachable, "avg_ms": h.avg_ms, "error": h.last_error,
        }
        for h in rows if not h.retired
    ]


def active_source_ids() -> set[str]:
    path = sources_file()
    if not path.exists():
        return set()
    return {row["id"] for row in json.loads(path.read_text(encoding="utf-8"))["sources"]}


PUBLIC_PATHS = {"/login", "/api/login", "/healthz", "/metrics", "/favicon.ico"}


def session_token(handler) -> str | None:
    raw = handler.headers.get("Cookie") or ""
    for part in raw.split(";"):
        name, _, value = part.strip().partition("=")
        if name == "pip_session":
            return value or None
    return None


def is_authenticated(handler) -> bool:
    return auth.SESSIONS.valid(session_token(handler))


def client_key(handler) -> str:
    fwd = handler.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return handler.client_address[0] if handler.client_address else "unknown"


def db_path() -> Path:
    return Path(os.environ.get("PIP_DB", config.DATA_DIR / "pip.db"))


def db_available() -> bool:
    return db_path().exists()


def with_db(fn):
    """打开连接执行 fn(conn)；库不存在或出错返回 None（调用方回落 JSONL）。"""
    if not db_available():
        return None
    try:
        conn = database.connect(db_path(), readonly=True)
        try:
            return fn(conn)
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        LOG.warning("db query failed, falling back: %s", exc)
        METRICS.inc("db_failures_total")
        return None


def world_report() -> dict:
    path = sources_file()
    sources = load_sources(path) if path.exists() else []
    return scan(sources, read_items())


# ---------------------------------------------------------------- Handler
class Handler(BaseHTTPRequestHandler):
    server_version = "PIP/1.1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        LOG.info(json.dumps({"client": self.address_string(), "msg": fmt % args}, ensure_ascii=False))

    # ---- 响应工具
    def _send(self, status: int, body: bytes, content_type: str, *, cache: str = "no-store",
              extra: dict[str, str] | None = None) -> None:
        accept_gzip = "gzip" in (self.headers.get("Accept-Encoding") or "")
        use_gzip = accept_gzip and len(body) >= GZIP_MIN_BYTES
        payload = gzip.compress(body, 6) if use_gzip else body

        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", cache)
        self.send_header("Vary", "Accept-Encoding")
        self.send_header("X-Content-Type-Options", "nosniff")
        if use_gzip:
            self.send_header("Content-Encoding", "gzip")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def _error(self, status: int, message: str) -> None:
        self._json(status, {"error": message, "status": status})

    # ---- 路由
    def do_HEAD(self) -> None:  # noqa: N802
        self._dispatch()

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch()

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch()

    def _dispatch(self) -> None:
        started = time.perf_counter()
        status = 500
        try:
            status = self._route()
        except Exception as exc:  # noqa: BLE001
            LOG.exception("request failed: %s", exc)
            METRICS.inc("errors_total")
            try:
                self._error(500, "internal error")
            except OSError:
                pass
            status = 500
        finally:
            elapsed = time.perf_counter() - started
            METRICS.inc("requests_total")
            METRICS.observe(elapsed)
            LOG.info(json.dumps({
                "method": self.command, "path": self.path.split("?")[0],
                "status": status, "ms": round(elapsed * 1000, 1),
            }, ensure_ascii=False))

    def _route(self) -> int:
        parts = urlsplit(self.path)
        path = parts.path
        query = parse_qs(parts.query)

        if path == "/login":
            return self._serve_login()
        if path == "/api/login":
            return self._handle_login()
        if path == "/logout":
            return self._handle_logout()

        if path not in PUBLIC_PATHS and not is_authenticated(self):
            if path.startswith("/api/"):
                self._json(401, {"ok": False, "message": "未登录或会话已过期"})
                return 401
            self.send_response(302)
            self.send_header("Location", "/login")
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return 302

        if path in ("/", "/index.html"):
            return self._serve_html()
        if path == "/healthz":
            return self._serve_healthz()
        if path == "/metrics":
            body = METRICS.render().encode()
            self._send(200, body, "text/plain; version=0.0.4; charset=utf-8")
            return 200
        if path == "/api/items":
            return self._serve_items(query)
        if path == "/api/meta":
            return self._serve_meta()
        if path == "/api/health":
            return self._serve_source_health()
        if path == "/api/v1/items":
            return self._serve_items_v1(query)
        if path == "/api/v1/stats":
            return self._serve_stats_v1()
        if path == "/api/v1/sources":
            return self._serve_sources_v1()
        if path == "/api/v1/days":
            return self._serve_days_v1()
        if path == "/api/v1/health":
            return self._serve_health_v1()
        if path == "/api/world":
            return self._serve_world()
        if path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
            return 204
        if path.startswith(STATIC_PREFIX):
            return self._serve_static(path)
        self._error(404, "not found")
        return 404

    def _serve_login(self) -> int:
        page = web_dir() / "login.html"
        if not page.exists():
            self._error(503, "login page missing")
            return 503
        self._send(200, page.read_bytes(), "text/html; charset=utf-8", cache="no-cache")
        return 200

    def _handle_login(self) -> int:
        if (self.command or "GET").upper() != "POST":
            self._error(405, "method not allowed")
            return 405

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 8192:
            self._json(400, {"ok": False, "message": "请求格式错误"})
            return 400
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8", "replace"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._json(400, {"ok": False, "message": "请求格式错误"})
            return 400

        key = client_key(self)
        locked = auth.ATTEMPTS.locked(key)
        if locked:
            self._json(429, {"ok": False, "message": f"尝试次数过多，请 {int(locked)} 秒后再试"})
            METRICS.inc("login_locked_total")
            return 429

        user = str(payload.get("username") or "")
        password = str(payload.get("password") or "")
        if auth.verify(user, password):
            auth.ATTEMPTS.success(key)
            token = auth.SESSIONS.create(user)
            body = json.dumps({"ok": True, "user": auth.username()}).encode()
            self._send(200, body, "application/json; charset=utf-8",
                       cache="no-store", extra={"Set-Cookie": auth.cookie_header(token)})
            METRICS.inc("login_success_total")
            LOG.info(json.dumps({"event": "login_ok", "user": auth.username(), "ip": key}, ensure_ascii=False))
            return 200

        count = auth.ATTEMPTS.fail(key)
        METRICS.inc("login_failed_total")
        LOG.warning(json.dumps({"event": "login_fail", "ip": key, "attempt": count}, ensure_ascii=False))
        message = "账号或密码错误"
        if count >= auth.MAX_FAILURES:
            message = f"尝试次数过多，请 {auth.LOCK_SECONDS // 60} 分钟后重试"
        self._json(401, {"ok": False, "message": message, "attempts": count})
        return 401

    def _handle_logout(self) -> int:
        token = session_token(self)
        auth.SESSIONS.revoke(token)
        if self.path.split("?")[0].startswith("/api/"):
            self._json(200, {"ok": True})
            return 200
        self.send_response(302)
        self.send_header("Location", "/login")
        self.send_header("Set-Cookie", auth.clear_cookie_header())
        self.send_header("Content-Length", "0")
        self.end_headers()
        return 302

    def _serve_html(self) -> int:
        index = web_dir() / "index.html"
        if not index.exists():
            self._error(503, "dashboard not built; run python -m pip_app.tools.build_web")
            return 503
        self._send(200, index.read_bytes(), "text/html; charset=utf-8", cache="no-cache")
        return 200

    def _serve_healthz(self) -> int:
        items = read_items()
        ok = bool(items)
        counts = with_db(database.table_counts) or {}
        payload = {
            "status": "ok" if ok else "degraded",
            "items": len(items),
            "date": latest_items_path().stem,
            "sources": len({i.get("source_id") for i in items if i.get("source_id")}),
            "uptime_s": round(time.time() - START_TIME),
            "db": {"path": str(db_path()), "available": db_available(), **counts},
        }
        self._json(200 if ok else 503, payload)
        METRICS.set("pip_items", len(items))
        return 200 if ok else 503

    def _serve_items(self, query: dict[str, list[str]]) -> int:
        domain = (query.get("domain") or ["all"])[0]
        conf = (query.get("conf") or ["all"])[0]
        q = (query.get("q") or [""])[0]
        try:
            limit = int((query.get("limit") or ["0"])[0])
        except ValueError:
            limit = 0
        items = filter_items(read_items(), domain=domain, conf=conf, q=q, limit=limit or None)
        self._json(200, {"items": items, "count": len(items)})
        return 200

    def _serve_meta(self) -> int:
        items = read_items()
        self._json(200, build_meta(items, read_health(active_source_ids())))
        return 200

    def _serve_source_health(self) -> int:
        self._json(200, {"rows": read_health(active_source_ids())})
        return 200

    def _serve_world(self) -> int:
        payload = world_report()
        self._json(200, payload)
        METRICS.set("pip_regions_covered", payload["coverage"]["regions_covered"])
        return 200

    # ---- v1：数据库驱动
    def _int(self, query, key, default):
        try:
            return int((query.get(key) or [str(default)])[0])
        except ValueError:
            return default

    def _serve_items_v1(self, query) -> int:
        def run(conn):
            return repo.query_items(
                conn,
                domain=(query.get("domain") or ["all"])[0],
                lang=(query.get("lang") or ["all"])[0],
                conf=(query.get("conf") or ["all"])[0],
                source_id=(query.get("source") or ["all"])[0],
                q=(query.get("q") or [""])[0],
                day=(query.get("day") or [""])[0],
                sort=(query.get("sort") or ["published"])[0],
                page=self._int(query, "page", 1),
                size=self._int(query, "size", 30),
            )

        payload = with_db(run)
        if payload is None:
            items = filter_items(
                read_items(),
                domain=(query.get("domain") or ["all"])[0],
                conf=(query.get("conf") or ["all"])[0],
                q=(query.get("q") or [""])[0],
                limit=self._int(query, "size", 30),
            )
            payload = {"items": items, "total": len(items), "page": 1, "size": len(items),
                       "pages": 1, "source": "jsonl"}
        else:
            payload["source"] = "db"
        self._json(200, payload)
        return 200

    def _serve_stats_v1(self) -> int:
        payload = with_db(repo.stats)
        if payload is None:
            items = read_items()
            payload = build_meta(items, read_health(active_source_ids()))
            payload["source"] = "jsonl"
        else:
            payload["source"] = "db"
        self._json(200, payload)
        return 200

    def _serve_sources_v1(self) -> int:
        payload = with_db(repo.sources_with_counts)
        self._json(200, {"sources": payload or [], "count": len(payload or [])})
        return 200

    def _serve_days_v1(self) -> int:
        payload = with_db(repo.days) or []
        self._json(200, {"days": payload})
        return 200

    def _serve_health_v1(self) -> int:
        payload = with_db(repo.runs_summary)
        self._json(200, {"rows": payload or [], "source": "db" if payload is not None else "jsonl"})
        return 200

    def _serve_static(self, path: str) -> int:
        rel = path[len(STATIC_PREFIX):]
        if not rel or ".." in rel or rel.startswith(("/", "\\")):
            self._error(400, "bad path")
            return 400
        base = (web_dir() / "screens").resolve()
        target = (base / rel).resolve()
        if base not in target.parents and target != base:
            self._error(403, "forbidden")
            return 403
        if not target.exists() or target.is_dir():
            self._error(404, "not found")
            return 404
        suffix = target.suffix.lower()
        ctype = {".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp",
                 ".svg": "image/svg+xml"}.get(suffix, "application/octet-stream")
        self._send(200, target.read_bytes(), ctype, cache="public, max-age=86400")
        return 200


START_TIME = time.time()


# ---------------------------------------------------------------- 组装
def make_server(host: str = "127.0.0.1", port: int = 8765) -> tuple[ThreadingHTTPServer, int]:
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    return httpd, httpd.server_address[1]


def start_scheduler(interval: int) -> threading.Thread:
    """后台定时采集 + 重建（失败不退出，只记日志）。"""
    def loop() -> None:
        from .cli import main as cli_main  # 延迟导入，避免循环

        while True:
            time.sleep(interval)
            try:
                LOG.info("scheduled collect start")
                cli_main(["collect"])
                cli_main(["health"])
                from .tools import build_globe_data, build_web  # type: ignore

                build_globe_data.main()
                build_web.main()
                LOG.info("scheduled collect done")
                METRICS.inc("scheduled_runs_total")
            except Exception as exc:  # noqa: BLE001
                LOG.error("scheduled collect failed: %s", exc)
                METRICS.inc("scheduled_failures_total")

    thread = threading.Thread(target=loop, name="pip-scheduler", daemon=True)
    thread.start()
    return thread


def _install_signal_handlers(httpd: ThreadingHTTPServer) -> None:
    def handler(signum, _frame):
        LOG.info("signal %s received, shutting down", signum)
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, handler)
        except (ValueError, OSError):
            pass


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="PIP 生产服务")
    parser.add_argument("--host", default=os.environ.get("PIP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PIP_PORT", "8765")))
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=os.environ.get("PIP_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )

    httpd, port = make_server(args.host, args.port)
    _install_signal_handlers(httpd)

    if os.environ.get("PIP_AUTO_COLLECT", "0") == "1":
        interval = int(os.environ.get("PIP_COLLECT_INTERVAL", "21600"))
        start_scheduler(interval)
        LOG.info("scheduler on, interval=%ss", interval)

    notice = auth.generated_password_notice()
    if notice:
        LOG.warning(notice)

    LOG.info("PIP listening on http://%s:%s/ (metrics at /metrics)", args.host, port)
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        LOG.info("stopped")


if __name__ == "__main__":
    main()
