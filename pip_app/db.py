"""SQLite 数据层：连接、schema、迁移。

为什么用 SQLite：
    1. 标准库自带，零依赖，`pip install` 都不用
    2. 单文件，备份就是拷一个文件，部署时挂载即可
    3. FTS5 + trigram 分词，中文也能子串检索
    4. 这个项目的数据量（万级/天）离 SQLite 的上限很远

表：
    sources      源元数据（含国家/城市，供全球扫描）
    items        条目（唯一键 = url）
    items_fts    FTS5 全文索引（trigram，中文可用）
    source_runs  每次采集的结果（用于健康报表）
    schema_meta  版本号，方便以后迁移
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 1

DEFAULT_DB = Path(os.environ.get("PIP_DB", Path(__file__).resolve().parent / "data" / "pip.db"))

DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    domain      TEXT,
    lang        TEXT,
    url         TEXT,
    tier        INTEGER,
    country     TEXT,
    city        TEXT,
    precision   TEXT,
    active      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT NOT NULL UNIQUE,
    source_id       TEXT NOT NULL,
    source_name     TEXT,
    domain          TEXT,
    lang            TEXT,
    title           TEXT NOT NULL,
    summary         TEXT,
    published_at    TEXT,
    fetched_at      TEXT,
    time_confidence TEXT,
    time_source     TEXT,
    content_hash    TEXT,
    day             TEXT,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_items_published ON items(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_source    ON items(source_id);
CREATE INDEX IF NOT EXISTS idx_items_day       ON items(day);
CREATE INDEX IF NOT EXISTS idx_items_domain    ON items(domain);
CREATE INDEX IF NOT EXISTS idx_items_conf      ON items(time_confidence);

CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
    title,
    summary,
    content='items',
    content_rowid='id',
    tokenize='trigram'
);

CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON items BEGIN
    INSERT INTO items_fts(rowid, title, summary) VALUES (new.id, new.title, new.summary);
END;

CREATE TRIGGER IF NOT EXISTS items_ad AFTER DELETE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, title, summary) VALUES ('delete', old.id, old.title, old.summary);
END;

CREATE TRIGGER IF NOT EXISTS items_au AFTER UPDATE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, title, summary) VALUES ('delete', old.id, old.title, old.summary);
    INSERT INTO items_fts(rowid, title, summary) VALUES (new.id, new.title, new.summary);
END;

CREATE TABLE IF NOT EXISTS source_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   TEXT NOT NULL,
    run_at      TEXT NOT NULL,
    status      TEXT,
    http_status INTEGER,
    elapsed_ms  INTEGER,
    item_count  INTEGER,
    error       TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_source ON source_runs(source_id, run_at DESC);
"""


def connect(path: Path | str | None = None, *, readonly: bool = False) -> sqlite3.Connection:
    """打开连接。readonly 用于只读场景（避免建表）。"""
    target = Path(path) if path else DEFAULT_DB
    if readonly:
        uri = f"file:{target}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(target, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init(path: Path | str | None = None, *, conn: sqlite3.Connection | None = None) -> sqlite3.Connection:
    """建表（幂等）。返回连接。"""
    owned = conn is None
    conn = conn or connect(path)
    conn.executescript(DDL)
    row = conn.execute("SELECT version FROM schema_meta").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_meta(version) VALUES (?)", (SCHEMA_VERSION,))
    elif row["version"] != SCHEMA_VERSION:
        conn.execute("UPDATE schema_meta SET version = ?", (SCHEMA_VERSION,))
    conn.commit()
    if owned:
        return conn
    return conn


def version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT version FROM schema_meta").fetchone()
    return int(row["version"]) if row else 0


@contextmanager
def session(path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """事务上下文：正常提交，异常回滚，最后关闭。"""
    conn = connect(path)
    try:
        init(conn=conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    out = {}
    for table in ("sources", "items", "source_runs"):
        try:
            out[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.OperationalError:
            out[table] = -1
    return out
