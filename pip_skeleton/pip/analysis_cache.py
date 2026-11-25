"""§5.6 文章级分析缓存（SQLite）。

命中条件 = content_hash 相同 且 prompt_version 相同 且 model 相同。
只更新 last_hit_at，不重算；提示词改版即不再命中（旧行保留以备审计）。
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis_cache (
  content_hash   TEXT PRIMARY KEY,
  domain         TEXT NOT NULL,
  lang           TEXT NOT NULL,
  summary_zh     TEXT NOT NULL,
  stability      TEXT NOT NULL,
  evidence_json  TEXT NOT NULL,
  model          TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  tokens_in      INTEGER,
  tokens_out     INTEGER,
  created_at     TEXT NOT NULL,
  last_hit_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_cache_domain_created ON analysis_cache(domain, created_at);
CREATE TABLE IF NOT EXISTS cache_stats (
  day TEXT PRIMARY KEY,
  lookups INTEGER NOT NULL DEFAULT 0,
  hits    INTEGER NOT NULL DEFAULT 0
);
"""


def content_hash(title: str, body: str) -> str:
    normalized = " ".join(body.split())
    return hashlib.sha256(f"{title.strip()}\n{normalized}".encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CacheEntry:
    content_hash: str
    summary_zh: str
    stability: str
    evidence: dict
    model: str
    prompt_version: str


class AnalysisCache:
    def __init__(self, path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def _bump(self, day: str, hit: bool) -> None:
        self.conn.execute(
            "INSERT INTO cache_stats(day, lookups, hits) VALUES(?, 1, ?) "
            "ON CONFLICT(day) DO UPDATE SET lookups = lookups + 1, hits = hits + excluded.hits",
            (day, 1 if hit else 0),
        )
        self.conn.commit()

    def get(self, chash: str, model: str, prompt_version: str, *, day: str) -> CacheEntry | None:
        row = self.conn.execute(
            "SELECT content_hash, summary_zh, stability, evidence_json, model, prompt_version "
            "FROM analysis_cache WHERE content_hash=? AND model=? AND prompt_version=?",
            (chash, model, prompt_version),
        ).fetchone()
        self._bump(day, row is not None)
        if row is None:
            return None
        self.conn.execute(
            "UPDATE analysis_cache SET last_hit_at=? WHERE content_hash=?",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"), chash),
        )
        self.conn.commit()
        return CacheEntry(row[0], row[1], row[2], json.loads(row[3]), row[4], row[5])

    def put(self, entry: CacheEntry, *, domain: str, lang: str, tokens_in: int, tokens_out: int) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO analysis_cache VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                entry.content_hash, domain, lang, entry.summary_zh, entry.stability,
                json.dumps(entry.evidence, ensure_ascii=False), entry.model, entry.prompt_version,
                tokens_in, tokens_out, datetime.now(timezone.utc).isoformat(timespec="seconds"), None,
            ),
        )
        self.conn.commit()

    def hit_rate(self, day: str) -> float:
        row = self.conn.execute("SELECT lookups, hits FROM cache_stats WHERE day=?", (day,)).fetchone()
        if not row or row[0] == 0:
            return 0.0
        return row[1] / row[0]
