"""§5.4 时间可信度校验。

三条规则（按序短路）：
1. item_pubDate 解析成功且落在 [fetched_at-30d, fetched_at+6h] -> high
2. 仅 feed_updated 可得：
   - 同源当轮所有条目共享同一时间戳（all_same=True）-> low（ai-news 的坑）
   - 否则 -> medium
3. 缺失 / 解析失败 / 超窗 -> low，published_at 置 None
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

HIGH = "high"
MEDIUM = "medium"
LOW = "low"

MAX_PAST = timedelta(days=30)
MAX_FUTURE = timedelta(hours=6)


@dataclass(frozen=True)
class ResolvedTime:
    published_at: datetime | None
    fetched_at: datetime
    confidence: str
    source: str  # item_pubDate | feed_updated | unknown

    @property
    def in_window(self) -> bool:
        """是否允许进入日报主列表。"""
        return self.confidence != LOW and self.published_at is not None


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def resolve(
    item_pub: datetime | None,
    feed_updated: datetime | None,
    fetched_at: datetime,
    *,
    all_same: bool = False,
) -> ResolvedTime:
    fetched = _aware(fetched_at)

    if item_pub is not None:
        pub = _aware(item_pub)
        if fetched - MAX_PAST <= pub <= fetched + MAX_FUTURE:
            return ResolvedTime(pub, fetched, HIGH, "item_pubDate")
        return ResolvedTime(None, fetched, LOW, "item_pubDate")

    if feed_updated is not None:
        updated = _aware(feed_updated)
        if all_same:
            return ResolvedTime(None, fetched, LOW, "feed_updated")
        return ResolvedTime(updated, fetched, MEDIUM, "feed_updated")

    return ResolvedTime(None, fetched, LOW, "unknown")


def same_timestamp(items: list[datetime | None]) -> bool:
    """同源当轮条目时间戳是否全部相同（用于识别 lastBuildDate 冒充）。"""
    stamps = [t for t in items if t is not None]
    return len(stamps) >= 2 and len({_aware(t) for t in stamps}) == 1
