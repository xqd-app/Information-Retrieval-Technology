"""§5.7 双语交付：重要内容强制双文（中文主版本 + 英文对照）。

三条质量门：
1. 术语一致性：术语表命中的英文词，中文侧不得出现禁用译法
2. 数字一致性：中英两侧的数值（含亿/billion 量级）必须能对上
3. 完整性：P0 内容（标题、摘要）缺任一语言即拒绝入库
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass, field

_NUMBER = re.compile(r"(\d+(?:[.,]\d+)?)\s*(%|亿|万|千|billion|million|thousand|bn|mn)?", re.IGNORECASE)

_SCALES = {
    "亿": 1e8, "万": 1e4, "千": 1e3,
    "billion": 1e9, "bn": 1e9,
    "million": 1e6, "mn": 1e6,
    "thousand": 1e3,
}

CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS translation_cache (
  key_hash TEXT PRIMARY KEY,
  src_lang TEXT NOT NULL,
  dst_lang TEXT NOT NULL,
  source   TEXT NOT NULL,
  translated TEXT NOT NULL,
  engine   TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class MissingBilingualError(ValueError):
    """P0 内容缺少某一种语言。"""


@dataclass(frozen=True)
class Term:
    en: str
    zh: str
    forbid: tuple[str, ...] = ()

    def violates(self, zh_text: str) -> bool:
        return any(word in zh_text for word in self.forbid)


class Glossary:
    def __init__(self, terms: list[Term]) -> None:
        self.terms = list(terms)

    def matches(self, text: str) -> list[Term]:
        lowered = text.casefold()
        return [t for t in self.terms if t.en.casefold() in lowered]


def check_terms(en_text: str, zh_text: str, glossary: Glossary) -> list[str]:
    violations = []
    for term in glossary.matches(en_text):
        for word in term.forbid:
            if word in zh_text:
                violations.append(f"{term.en} 不应译为「{word}」，应为「{term.zh}」")
    return violations


def numbers(text: str) -> set[str]:
    """原始数值 token（用于提示与人工核对）。"""
    return {m.group(1) for m in _NUMBER.finditer(text)}


def normalized_numbers(text: str) -> set[str]:
    """带量级归一（亿/billion 等），用于中英两侧数值对齐。"""
    out: set[str] = set()
    for match in _NUMBER.finditer(text):
        raw, unit = match.group(1), (match.group(2) or "").lower()
        value = float(raw.replace(",", ""))
        if unit in _SCALES:
            value *= _SCALES[unit]
        out.add(f"{value:.6g}")
    return out


def check_numeric_consistency(zh_text: str, en_text: str) -> tuple[bool, str]:
    zh_norm = normalized_numbers(zh_text)
    en_norm = normalized_numbers(en_text)
    if zh_norm == en_norm:
        return True, ""
    only_zh = sorted(zh_norm - en_norm)
    only_en = sorted(en_norm - zh_norm)
    raw = sorted(numbers(zh_text))
    detail = f"中文侧数值 {raw}；缺失或不符：{only_zh or '无'}/{only_en or '无'}"
    return False, detail


@dataclass(frozen=True)
class BilingualDoc:
    title_zh: str
    title_en: str
    summary_zh: str
    summary_en: str
    terms: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        missing = [
            name for name, value in (
                ("title_zh", self.title_zh),
                ("title_en", self.title_en),
                ("summary_zh", self.summary_zh),
                ("summary_en", self.summary_en),
            ) if not value or not value.strip()
        ]
        if missing:
            raise MissingBilingualError(f"P0 内容缺少语言字段：{', '.join(missing)}")

    @property
    def is_complete(self) -> bool:
        try:
            self.validate()
        except MissingBilingualError:
            return False
        return True

    def term_pairs(self) -> list[tuple[str, str]]:
        return list(self.terms)


class TranslationCache:
    def __init__(self, path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(path)
        self.conn.executescript(CACHE_SCHEMA)

    def close(self) -> None:
        self.conn.close()

    @staticmethod
    def key(text: str, src: str, dst: str) -> str:
        return hashlib.sha256(f"{src}|{dst}|{text}".encode("utf-8")).hexdigest()

    def get(self, text: str, src: str, dst: str) -> str | None:
        row = self.conn.execute(
            "SELECT translated FROM translation_cache WHERE key_hash=?",
            (self.key(text, src, dst),),
        ).fetchone()
        return row[0] if row else None

    def put(self, text: str, src: str, dst: str, translated: str, *, engine: str = "") -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO translation_cache(key_hash, src_lang, dst_lang, source, translated, engine)"
            " VALUES(?,?,?,?,?,?)",
            (self.key(text, src, dst), src, dst, text, translated, engine),
        )
        self.conn.commit()


def translate_with_cache(
    text: str,
    src: str,
    dst: str,
    translate_fn,
    cache: TranslationCache,
) -> tuple[str, bool]:
    cached = cache.get(text, src, dst)
    if cached is not None:
        return cached, True
    translated = translate_fn(text, src, dst)
    cache.put(text, src, dst, translated)
    return translated, False
