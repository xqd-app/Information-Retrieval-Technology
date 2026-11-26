"""把采集文件同步进数据库。

设计：幂等全量 upsert（url 唯一），所以重复执行安全，采集后直接调用即可。
默认只同步最近 N 天，避免每次都在几十个历史文件上做全表扫描。
"""

from __future__ import annotations

import json
from pathlib import Path

from . import db, repo
from .config import DATA_DIR, ITEMS_DIR, SOURCES_FILE

GEO_LOOKUP: dict[str, tuple[str, str]] = {}


def _geo_map() -> dict[str, tuple[str, str]]:
    """源 → (国家, 城市)，来自 build_globe_data 的坐标表。"""
    if GEO_LOOKUP:
        return GEO_LOOKUP
    try:
        from .tools.build_globe_data import COUNTRY_OF_CITY, SOURCE_PLACE

        for sid, (city, _prec) in SOURCE_PLACE.items():
            GEO_LOOKUP[sid] = (COUNTRY_OF_CITY.get(city, ""), city)
    except Exception:  # noqa: BLE001 - 地理表不可用时不阻塞入库
        pass
    return GEO_LOOKUP


def load_sources(path: Path = SOURCES_FILE) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("sources", [])


def sync(
    *,
    days: int = 7,
    db_path: Path | None = None,
    items_dir: Path = ITEMS_DIR,
    sources_file: Path = SOURCES_FILE,
) -> dict:
    """同步源清单 + 最近 N 天条目。返回统计。"""
    files = sorted(items_dir.glob("*.jsonl"))[-days:] if items_dir.exists() else []
    result = {"files": len(files), "inserted": 0, "updated": 0, "sources": 0}
    with db.session(db_path) as conn:
        sources = load_sources(sources_file)
        if sources:
            result["sources"] = repo.upsert_sources(conn, sources, geo=_geo_map())
        for path in files:
            ins, upd = repo.ingest_jsonl(conn, path)
            result["inserted"] += ins
            result["updated"] += upd
        result["total"] = db.table_counts(conn)["items"]
    return result


def sync_health(*, db_path: Path | None = None, data_dir: Path = DATA_DIR, limit: int = 500) -> int:
    """把 source_health.jsonl 的最近记录写入 source_runs。"""
    path = data_dir / "source_health.jsonl"
    if not path.exists():
        return 0
    lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    count = 0
    with db.session(db_path) as conn:
        for line in lines:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            repo.insert_run(conn, {
                "source_id": row.get("source_id"),
                "run_at": row.get("fetched_at") or row.get("run_at"),
                "status": row.get("status"),
                "http_status": row.get("http_status"),
                "elapsed_ms": row.get("elapsed_ms"),
                "item_count": row.get("item_count"),
                "error": row.get("error"),
            })
            count += 1
    return count


def main() -> None:
    result = sync()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
