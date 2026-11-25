"""§5.2 三阶段去重：URL 归一 -> 标题精确 -> Jaccard 近似。

原则：宁可保留重复，不可错误合并。因此近似阶段有两条额外闸门：
- token 数不足 MIN_TOKENS_FOR_FUZZY 时不启用
- 标题语言不同（一个含 CJK、一个纯拉丁）时不合并
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DEDUP_THRESHOLD = 0.85
MIN_TOKENS_FOR_FUZZY = 6

_TRACKING_PREFIXES = ("utm_", "spm", "from", "ref", "fbclid", "gclid")
_PUNCT = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)
_CJK = re.compile(r"[\u4e00-\u9fff]")


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith(_TRACKING_PREFIXES)]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def normalize_title(title: str) -> str:
    return " ".join(_PUNCT.sub(" ", title).casefold().split())


def tokens(text: str) -> frozenset[str]:
    norm = normalize_title(text)
    if _CJK.search(norm):
        compact = norm.replace(" ", "")
        if len(compact) < 2:
            return frozenset([compact]) if compact else frozenset()
        return frozenset(compact[i:i + 2] for i in range(len(compact) - 1))
    return frozenset(norm.split())


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _lang_matches(a: str, b: str) -> bool:
    return bool(_CJK.search(a)) == bool(_CJK.search(b))


@dataclass
class Item:
    title: str
    url: str
    published_at: datetime | None = None
    domain: str = ""
    payload: dict = field(default_factory=dict)


def _newer(a: Item, b: Item) -> Item:
    if a.published_at is None:
        return b
    if b.published_at is None:
        return a
    return a if a.published_at >= b.published_at else b


def dedupe(items: Iterable[Item], threshold: float = DEDUP_THRESHOLD) -> list[Item]:
    stage1: dict[str, Item] = {}
    for item in items:
        key = normalize_url(item.url)
        stage1[key] = _newer(stage1[key], item) if key in stage1 else item

    stage2: dict[str, Item] = {}
    for item in stage1.values():
        key = normalize_title(item.title)
        stage2[key] = _newer(stage2[key], item) if key in stage2 else item

    kept: list[Item] = list(stage2.values())
    result: list[Item] = []
    for item in kept:
        merged = False
        item_tokens = tokens(item.title)
        if len(item_tokens) >= MIN_TOKENS_FOR_FUZZY:
            for i, existing in enumerate(result):
                existing_tokens = tokens(existing.title)
                if len(existing_tokens) < MIN_TOKENS_FOR_FUZZY:
                    continue
                if not _lang_matches(item.title, existing.title):
                    continue
                if jaccard(item_tokens, existing_tokens) >= threshold:
                    result[i] = _newer(existing, item)
                    merged = True
                    break
        if not merged:
            result.append(item)
    return result
