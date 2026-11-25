"""W1 采集编排：抓取 → 解析 → 时间判定 → 去重 → 落盘 → 健康记录。

对应 PIP v1.2 §5.1–§5.4。所有失败都变成结构化 status，绝不静默。
"""

from __future__ import annotations

import gzip
import json
import time
import urllib.error
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from pip.analysis_cache import content_hash
from pip.dedupe import Item, dedupe
from pip.time_confidence import LOW, resolve, same_timestamp

from . import config
from .feedparse import NotAFeed, parse_feed

OK = "ok"
FAILED = "failed"
ZERO_RESULT = "zero_result"
TIMEOUT = "timeout"
UNREACHABLE = "unreachable"   # 网络层失败：DNS/TLS/连接重置，不等于源坏了
PARTIAL = "partial"


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    domain: str
    lang: str
    url: str
    tier: int = 3


@dataclass
class SourceRun:
    source: Source
    status: str
    fetched: int = 0
    error: str = ""
    duration_ms: int = 0
    items: list[dict] = field(default_factory=list)


@dataclass
class CollectOutcome:
    run_at: str
    domain: str
    status: str
    sources: list[SourceRun]
    items: list[dict]
    duplicates_removed: int


def load_sources(path: Path | str = config.SOURCES_FILE) -> list[Source]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Source(**row) for row in payload["sources"]]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds") if value else None


def _request(url: str) -> bytes:
    """带重试的取数：网络层故障重试，4xx 立即失败（不掩盖真实错误）。

    首次尝试用完整超时；重试改用更短超时——一个坏源不该吃掉 45s。
    """
    import urllib.error

    attempts = config.RETRY_ATTEMPTS + 1
    last_error: Exception | None = None
    for attempt in range(attempts):
        timeout = config.TIMEOUT_SECONDS if attempt == 0 else config.RETRY_TIMEOUT_SECONDS
        try:
            return _request_once(url, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500:
                raise  # 403/404 是源的真实状态，重试没意义
            last_error = exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last_error = exc
        if attempt < attempts - 1:
            time.sleep(config.RETRY_BACKOFF_SECONDS * (2 ** attempt))
    assert last_error is not None
    raise last_error


def _request_once(url: str, timeout: float | None = None) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": config.UA, "Accept": config.ACCEPT})
    with urllib.request.urlopen(request, timeout=timeout or config.TIMEOUT_SECONDS) as response:
        raw = response.read(config.MAX_BYTES)
        encoding = (response.headers.get("Content-Encoding") or "").lower()
    return _decompress(raw, encoding)


def _decompress(raw: bytes, encoding: str) -> bytes:
    """部分站点（如 deepmind）无视 Accept-Encoding 一律 gzip；不解压会把 feed 误判成坏 XML。"""
    if encoding == "gzip" or raw[:2] == b"\x1f\x8b":
        try:
            return gzip.decompress(raw)
        except OSError:
            return raw
    if encoding == "deflate":
        try:
            return zlib.decompress(raw)
        except zlib.error:
            return raw
    return raw


def normalize(source: Source, raw_items: list[dict], feed_updated: datetime | None) -> list[dict]:
    """注入 fetched_at、判定时间可信度、算 content_hash。"""
    fetched_at = utc_now()
    stamps = [item["published_at"] for item in raw_items]
    # 两种情况都视为「共用 feed 时间」：多条同戳，或全部没有独立发布时间（只有 lastBuildDate）
    all_same = same_timestamp(stamps) or all(stamp is None for stamp in stamps)

    out: list[dict] = []
    for raw in raw_items[: config.LIMIT_PER_SOURCE]:
        resolved = resolve(raw["published_at"], feed_updated, fetched_at, all_same=all_same)
        out.append(
            {
                "id": content_hash(raw["title"], raw["url"])[:16],
                "domain": source.domain,
                "source_id": source.id,
                "source_name": source.name,
                "lang": source.lang,
                "title": raw["title"],
                "url": raw["url"],
                "summary": raw["summary"],
                "published_at": _iso(resolved.published_at),
                "fetched_at": _iso(resolved.fetched_at),
                "time_confidence": resolved.confidence,
                "time_source": resolved.source,
                "content_hash": content_hash(raw["title"], raw.get("summary", "")),
            }
        )
    return out


def run_source(source: Source) -> SourceRun:
    started = time.perf_counter()
    try:
        payload = _request(source.url)
    except urllib.error.HTTPError as exc:
        # 4xx/5xx 是源的真实状态
        return SourceRun(source, FAILED, error=f"HTTP {exc.code}", duration_ms=_ms(started))
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        # 网络层失败：DNS / TLS / 连接重置 / 超时。这类不该算「源坏了」。
        reason = str(getattr(exc, "reason", exc))
        return SourceRun(source, UNREACHABLE, error=reason[:120], duration_ms=_ms(started))
    except Exception as exc:  # noqa: BLE001 - 单源故障不外溢
        return SourceRun(source, FAILED, error=type(exc).__name__, duration_ms=_ms(started))

    try:
        raw_items, feed_updated = parse_feed(payload)
    except NotAFeed as exc:
        return SourceRun(source, FAILED, error=f"not_a_feed: {exc}"[:120], duration_ms=_ms(started))

    if not raw_items:
        return SourceRun(source, ZERO_RESULT, error="", duration_ms=_ms(started))

    items = normalize(source, raw_items, feed_updated)
    return SourceRun(source, OK, fetched=len(items), items=items, duration_ms=_ms(started))


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def collect(sources: Iterable[Source], *, workers: int = config.WORKERS) -> CollectOutcome:
    selected = list(sources)
    runs: list[SourceRun] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run_source, source): source for source in selected}
        for future in as_completed(futures, timeout=config.GLOBAL_BUDGET_SECONDS):
            runs.append(future.result())

    runs.sort(key=lambda run: run.source.id)
    candidates: list[Item] = []
    for run in runs:
        for item in run.items:
            candidates.append(
                Item(
                    title=item["title"],
                    url=item["url"],
                    published_at=_parse_iso(item["published_at"]),
                    domain=item["source_id"],
                    payload=item,
                )
            )
    kept = dedupe(candidates)
    items = [item.payload for item in kept]
    items.sort(key=lambda row: row["published_at"] or "", reverse=True)

    status = OK if all(run.status == OK for run in runs) else PARTIAL
    return CollectOutcome(
        run_at=_iso(utc_now()) or "",
        domain=",".join(sorted({run.source.domain for run in runs})),
        status=status,
        sources=runs,
        items=items,
        duplicates_removed=len(candidates) - len(kept),
    )


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def write_outputs(outcome: CollectOutcome, *, day: str | None = None) -> dict[str, str]:
    config.ITEMS_DIR.mkdir(parents=True, exist_ok=True)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    day = day or (outcome.run_at[:10] if outcome.run_at else utc_now().strftime("%Y-%m-%d"))

    items_path = config.ITEMS_DIR / f"{day}.jsonl"
    merged = _merge_existing(items_path, outcome.items)
    with items_path.open("w", encoding="utf-8", newline="\n") as fh:
        for item in merged:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")

    with config.HEALTH_FILE.open("a", encoding="utf-8", newline="\n") as fh:
        for run in outcome.sources:
            fh.write(
                json.dumps(
                    {
                        "run_at": outcome.run_at,
                        "day": day,
                        "source_id": run.source.id,
                        "source_name": run.source.name,
                        "domain": run.source.domain,
                        "status": run.status,
                        "fetched": run.fetched,
                        "error": run.error,
                        "duration_ms": run.duration_ms,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    return {"items": str(items_path), "health": str(config.HEALTH_FILE), "items_count": len(merged)}


def _merge_existing(path: Path, new_items: list[dict]) -> list[dict]:
    by_url: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            by_url[row["url"]] = row
    for item in new_items:
        existing = by_url.get(item["url"])
        if existing is None or (item["published_at"] or "") >= (existing.get("published_at") or ""):
            by_url[item["url"]] = item
    rows = list(by_url.values())
    rows.sort(key=lambda row: row["published_at"] or "", reverse=True)
    return rows
