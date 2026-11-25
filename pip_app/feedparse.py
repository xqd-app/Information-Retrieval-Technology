"""RSS / Atom 解析（标准库实现）。

设计要点：
- 支持 RSS 2.0 与 Atom（命名空间用 local-name 判定，忽略前缀差异）
- 时间解析三种格式：RFC822（email.utils）、ISO8601（含 Z）、显式 offset
- HTML 页面、空字节、坏 XML 一律抛 NotAFeed，由采集层记为 failed（不是 zero_result）
- 摘要去标签 + 限长，保留原文以便回查
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

SUMMARY_LIMIT = 400
_BLOCK_TAG = re.compile(r"<\s*/?\s*(br|p|div|li|ul|ol|h[1-6]|tr|td|blockquote)\b[^>]*>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_PUNCT_SPACE = re.compile(r"\s+([.,;:!?%)\]])")
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}")


class NotAFeed(ValueError):
    """响应体不是可解析的 feed（HTML 改版 / 空体 / 坏 XML）。"""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _find(node: ET.Element, *names: str) -> ET.Element | None:
    wanted = {n.lower() for n in names}
    for child in node:
        if _local(child.tag) in wanted:
            return child
    return None


def _text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return (node.text or "").strip()


def parse_datetime(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if _ISO.match(raw):
        candidate = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            return None
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if parsed is None:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def summarize_html(text: str, limit: int = SUMMARY_LIMIT) -> str:
    unescaped = html.unescape(text or "")
    spaced = _BLOCK_TAG.sub(" ", unescaped)      # 块级标签变空格，避免句子粘连
    stripped = _TAG.sub("", spaced)              # 行内标签直接去掉，避免 "scaling ."
    collapsed = _WS.sub(" ", stripped).strip()
    return _PUNCT_SPACE.sub(r"\1", collapsed)[:limit]


def _atom_link(entry: ET.Element) -> str:
    for child in entry:
        if _local(child.tag) != "link":
            continue
        rel = (child.get("rel") or "alternate").lower()
        href = child.get("href")
        if href and rel in {"alternate", ""}:
            return href.strip()
    return ""


def parse_feed(payload: bytes) -> tuple[list[dict], datetime | None]:
    """返回 (items, feed_updated)。items 不含 fetched_at（由采集层注入）。"""
    if not payload or not payload.strip():
        raise NotAFeed("empty payload")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise NotAFeed(f"xml parse error: {exc}") from exc

    kind = _local(root.tag)
    if kind == "rss":
        channel = _find(root, "channel")
        if channel is None:
            raise NotAFeed("rss without channel")
    elif kind == "feed":
        channel = root
    else:
        raise NotAFeed(f"unexpected root element: {kind}")

    feed_updated = parse_datetime(_text(_find(channel, "lastBuildDate", "updated", "date", "pubDate")))

    entries = [child for child in channel if _local(child.tag) in {"item", "entry"}]
    items: list[dict] = []
    for entry in entries:
        title = _text(_find(entry, "title"))
        if kind == "feed":
            url = _atom_link(entry)
        else:
            url = _text(_find(entry, "link")) or _text(_find(entry, "guid"))
        if not title or not url:
            continue
        published = parse_datetime(
            _text(_find(entry, "pubDate", "published", "updated", "date", "issued"))
        )
        summary_raw = _text(_find(entry, "description", "summary", "content"))
        items.append(
            {
                "title": _WS.sub(" ", title).strip(),
                "url": url,
                "published_at": published,
                "summary": summarize_html(summary_raw),
            }
        )
    return items, feed_updated
