"""仓储层：把采集结果写进库，把查询拼成 SQL。

设计原则：
    1. 幂等：同一 url 重复写入只更新字段，不新增行
    2. 参数化：所有用户输入走占位符，不拼字符串
    3. 分页：返回 (rows, total)，前端才能显示「1 / 30 页」
    4. 搜索：FTS5 trigram，<3 字符的查询自动退回 LIKE（trigram 的硬限制）
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SOURCE_FIELDS = ("id", "name", "domain", "lang", "url", "tier", "country", "city", "precision")
ITEM_FIELDS = (
    "url", "source_id", "source_name", "domain", "lang", "title", "summary",
    "published_at", "fetched_at", "time_confidence", "time_source", "content_hash", "day",
)
SORTS = {
    "published": "published_at DESC",
    "published_asc": "published_at ASC",
    "fetched": "fetched_at DESC",
    "source": "source_name ASC, published_at DESC",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------- 写入
def upsert_sources(conn: sqlite3.Connection, sources: Iterable[dict], *, geo: dict[str, tuple[str, str]] | None = None) -> int:
    """写入/更新源。geo 提供 {source_id: (country, city)}。"""
    geo = geo or {}
    rows = []
    for src in sources:
        country, city = geo.get(src["id"], ("", ""))
        rows.append((
            src["id"], src.get("name") or src["id"], src.get("domain"), src.get("lang"),
            src.get("url"), src.get("tier"), country or None, city or None, None, 1,
        ))
    conn.executemany(
        """INSERT INTO sources(id, name, domain, lang, url, tier, country, city, precision, active)
           VALUES(?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             name=excluded.name, domain=excluded.domain, lang=excluded.lang,
             url=excluded.url, tier=excluded.tier,
             country=COALESCE(excluded.country, sources.country),
             city=COALESCE(excluded.city, sources.city)""",
        rows,
    )
    return len(rows)


def insert_items(conn: sqlite3.Connection, items: Iterable[dict]) -> tuple[int, int]:
    """幂等写入条目，返回 (新增, 更新)。"""
    inserted = updated = 0
    for item in items:
        url = item.get("url")
        title = item.get("title")
        if not url or not title:
            continue
        day = item.get("day") or (item.get("fetched_at") or "")[:10] or _now()[:10]
        payload = (
            url, item.get("source_id") or "unknown", item.get("source_name"),
            item.get("domain"), item.get("lang"), title, item.get("summary"),
            item.get("published_at"), item.get("fetched_at"),
            item.get("time_confidence"), item.get("time_source"),
            item.get("content_hash"), day,
        )
        existed = conn.execute("SELECT 1 FROM items WHERE url = ?", (url,)).fetchone()
        conn.execute(
            """INSERT INTO items(url, source_id, source_name, domain, lang, title, summary,
                                 published_at, fetched_at, time_confidence, time_source, content_hash, day)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(url) DO UPDATE SET
                 title=excluded.title, summary=excluded.summary,
                 published_at=COALESCE(excluded.published_at, items.published_at),
                 fetched_at=excluded.fetched_at,
                 time_confidence=excluded.time_confidence,
                 time_source=excluded.time_source,
                 content_hash=excluded.content_hash""",
            payload,
        )
        if existed:
            updated += 1
        else:
            inserted += 1
    return inserted, updated


def insert_run(conn: sqlite3.Connection, run: dict) -> None:
    conn.execute(
        """INSERT INTO source_runs(source_id, run_at, status, http_status, elapsed_ms, item_count, error)
           VALUES(?,?,?,?,?,?,?)""",
        (
            run.get("source_id") or "unknown", run.get("run_at") or _now(),
            run.get("status"), run.get("http_status"), run.get("elapsed_ms"),
            run.get("item_count"), run.get("error"),
        ),
    )


def ingest_jsonl(conn: sqlite3.Connection, path: Path) -> tuple[int, int]:
    """把一天的采集文件导入库。"""
    if not path.exists():
        return 0, 0
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return insert_items(conn, rows)


# ---------------------------------------------------------------- 查询
def _fts_query(term: str) -> str:
    """把用户输入转成 FTS5 查询：按空格切词，每个词加引号转义。"""
    parts = [p for p in term.replace('"', " ").split() if p]
    return " AND ".join(f'"{p}"' for p in parts)


def query_items(
    conn: sqlite3.Connection,
    *,
    domain: str = "all",
    lang: str = "all",
    conf: str = "all",
    source_id: str = "all",
    q: str = "",
    day: str = "",
    sort: str = "published",
    page: int = 1,
    size: int = 30,
) -> dict[str, Any]:
    where: list[str] = []
    params: list[Any] = []

    if domain != "all":
        where.append("i.domain = ?"); params.append(domain)
    if lang != "all":
        where.append("i.lang = ?"); params.append(lang)
    if conf != "all":
        where.append("i.time_confidence = ?"); params.append(conf)
    if source_id != "all":
        where.append("i.source_id = ?"); params.append(source_id)
    if day:
        where.append("i.day = ?"); params.append(day)

    term = (q or "").strip()
    if term and len(term) >= 3:
        where.append("i.id IN (SELECT rowid FROM items_fts WHERE items_fts MATCH ?)")
        params.append(_fts_query(term))
    elif term:
        where.append("(i.title LIKE ? OR i.summary LIKE ?)")
        params += [f"%{term}%", f"%{term}%"]

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    order_sql = SORTS.get(sort, SORTS["published"])
    size = max(1, min(int(size), 200))
    page = max(1, int(page))
    offset = (page - 1) * size

    total = conn.execute(f"SELECT COUNT(*) FROM items i {where_sql}", params).fetchone()[0]
    rows = conn.execute(
        f"""SELECT i.* FROM items i {where_sql}
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?""",
        params + [size, offset],
    ).fetchall()
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "size": size,
        "pages": max(1, (total + size - 1) // size),
    }


def stats(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute(
        """SELECT COUNT(*) AS total,
                  COUNT(DISTINCT source_id) AS sources,
                  COUNT(DISTINCT domain) AS domains,
                  COUNT(DISTINCT lang) AS languages,
                  MIN(published_at) AS oldest, MAX(published_at) AS newest
           FROM items"""
    ).fetchone()
    by_domain = {r["domain"] or "unknown": r["n"] for r in conn.execute(
        "SELECT domain, COUNT(*) n FROM items GROUP BY domain ORDER BY n DESC")}
    by_lang = {r["lang"] or "unknown": r["n"] for r in conn.execute(
        "SELECT lang, COUNT(*) n FROM items GROUP BY lang ORDER BY n DESC")}
    by_conf = {r["time_confidence"] or "unknown": r["n"] for r in conn.execute(
        "SELECT time_confidence, COUNT(*) n FROM items GROUP BY time_confidence")}
    return {
        "total": row["total"], "sources": row["sources"], "domains": by_domain,
        "languages": by_lang, "confidence": by_conf,
        "oldest": row["oldest"], "newest": row["newest"],
    }


def sources_with_counts(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT s.id, s.name, s.domain, s.lang, s.country, s.city, s.tier,
                  COUNT(i.id) AS items
           FROM sources s LEFT JOIN items i ON i.source_id = s.id
           GROUP BY s.id ORDER BY items DESC, s.name ASC"""
    ).fetchall()
    return [dict(r) for r in rows]


def runs_summary(conn: sqlite3.Connection, *, limit: int = 200) -> list[dict]:
    rows = conn.execute(
        """SELECT source_id,
                  COUNT(*) AS runs,
                  SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) AS ok,
                  SUM(CASE WHEN status = 'zero_result' THEN 1 ELSE 0 END) AS zero,
                  SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                  SUM(CASE WHEN status = 'unreachable' THEN 1 ELSE 0 END) AS unreachable,
                  ROUND(AVG(elapsed_ms)) AS avg_ms,
                  MAX(run_at) AS last_run
           FROM (SELECT * FROM source_runs ORDER BY run_at DESC LIMIT ?)
           GROUP BY source_id ORDER BY runs DESC""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def days(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT day, COUNT(*) n FROM items GROUP BY day ORDER BY day DESC"
    ).fetchall()
    return [dict(r) for r in rows]
