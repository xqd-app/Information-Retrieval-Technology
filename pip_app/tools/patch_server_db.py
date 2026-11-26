"""把数据库接到服务上：新增 /api/v1/* 分页与全文搜索接口。

策略：数据库可用则走 DB（分页、搜索、聚合），不可用自动回落到 JSONL，
所以「没建库」也不会让服务挂掉。
"""

from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "server.py"
text = PATH.read_text(encoding="utf-8")

# ---------- 1) 导入 ----------
old_import = "from .serve import build_meta, filter_items"
new_import = """from . import db as database
from . import repo
from .serve import build_meta, filter_items"""
assert old_import in text
text = text.replace(old_import, new_import, 1)

# ---------- 2) DB 访问辅助 ----------
anchor = "def world_report() -> dict:"
assert anchor in text
DB_HELPERS = '''def db_path() -> Path:
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


'''
text = text.replace(anchor, DB_HELPERS + anchor, 1)

# ---------- 3) 路由 ----------
old_route = '        if path == "/api/world":'
new_route = '''        if path == "/api/v1/items":
            return self._serve_items_v1(query)
        if path == "/api/v1/stats":
            return self._serve_stats_v1()
        if path == "/api/v1/sources":
            return self._serve_sources_v1()
        if path == "/api/v1/days":
            return self._serve_days_v1()
        if path == "/api/v1/health":
            return self._serve_health_v1()
        if path == "/api/world":'''
assert old_route in text
text = text.replace(old_route, new_route, 1)

# ---------- 4) 处理函数 ----------
anchor2 = "    def _serve_static(self, path: str) -> int:"
assert anchor2 in text
HANDLERS = '''    # ---- v1：数据库驱动
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

    def _serve_static(self, path: str) -> int:'''
text = text.replace(anchor2, HANDLERS, 1)

# ---------- 5) healthz 带上数据库状态 ----------
old_hz = '''        payload = {
            "status": "ok" if ok else "degraded",
            "items": len(items),
            "date": latest_items_path().stem,
            "sources": len({i.get("source_id") for i in items if i.get("source_id")}),
            "uptime_s": round(time.time() - START_TIME),
        }'''
new_hz = '''        counts = with_db(database.table_counts) or {}
        payload = {
            "status": "ok" if ok else "degraded",
            "items": len(items),
            "date": latest_items_path().stem,
            "sources": len({i.get("source_id") for i in items if i.get("source_id")}),
            "uptime_s": round(time.time() - START_TIME),
            "db": {"path": str(db_path()), "available": db_available(), **counts},
        }'''
assert old_hz in text
text = text.replace(old_hz, new_hz, 1)

PATH.write_text(text, encoding="utf-8")
print("patched server with db api")
