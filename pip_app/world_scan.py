"""全球覆盖扫描：把来源按大洲/国家聚合，算出「哪些地区有情报、哪些是盲区」。

为什么需要：
现在的 31 个源集中在北美 + 西欧 + 东亚，本质是一张「英语世界视角」的雷达图。
要判断情报覆盖是否真的全球化，必须能回答三个问题：
    1. 每个区域有多少源、多少条目？
    2. 哪些区域一个源都没有（盲区）？
    3. 全球覆盖率是多少？

数据来源：
    sources.json         源清单（id / name / domain / lang）
    build_globe_data     SOURCE_PLACE（源 → 城市） + COUNTRY_OF_CITY（城市 → 国家）
    data/items/*.jsonl   当日条目（按 source_id 计数）
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from pip_app.tools.build_globe_data import COUNTRY_OF_CITY, SOURCE_PLACE

# 区域 → 国家代码。刻意包含「一个源都没有」的区域，盲区才有意义。
REGIONS: dict[str, list[str]] = {
    "北美": ["US", "CA", "MX"],
    "西欧": ["GB", "FR", "DE", "NL", "BE", "CH", "IE", "ES", "IT", "PT", "AT", "SE", "NO", "DK", "FI"],
    "中东": ["QA", "AE", "SA", "IL", "TR", "IR"],
    "东亚": ["CN", "JP", "KR", "HK", "TW", "MO"],
    "南亚": ["IN", "PK", "BD", "LK"],
    "东南亚": ["SG", "ID", "MY", "TH", "VN", "PH"],
    "大洋洲": ["AU", "NZ"],
    "拉美": ["BR", "AR", "CL", "CO", "PE", "VE"],
    "非洲": ["ZA", "NG", "KE", "EG", "MA"],
    "东欧与俄": ["RU", "PL", "CZ", "UA", "HU", "RO"],
}

COUNTRY_NAMES = {
    "US": "美国", "CA": "加拿大", "MX": "墨西哥",
    "GB": "英国", "FR": "法国", "DE": "德国", "NL": "荷兰", "BE": "比利时", "CH": "瑞士",
    "IE": "爱尔兰", "ES": "西班牙", "IT": "意大利", "PT": "葡萄牙", "AT": "奥地利",
    "SE": "瑞典", "NO": "挪威", "DK": "丹麦", "FI": "芬兰",
    "QA": "卡塔尔", "AE": "阿联酋", "SA": "沙特", "IL": "以色列", "TR": "土耳其", "IR": "伊朗",
    "CN": "中国", "JP": "日本", "KR": "韩国", "HK": "中国香港", "TW": "中国台湾", "MO": "中国澳门",
    "IN": "印度", "PK": "巴基斯坦", "BD": "孟加拉", "LK": "斯里兰卡",
    "SG": "新加坡", "ID": "印尼", "MY": "马来西亚", "TH": "泰国", "VN": "越南", "PH": "菲律宾",
    "AU": "澳大利亚", "NZ": "新西兰",
    "BR": "巴西", "AR": "阿根廷", "CL": "智利", "CO": "哥伦比亚", "PE": "秘鲁", "VE": "委内瑞拉",
    "ZA": "南非", "NG": "尼日利亚", "KE": "肯尼亚", "EG": "埃及", "MA": "摩洛哥",
    "RU": "俄罗斯", "PL": "波兰", "CZ": "捷克", "UA": "乌克兰", "HU": "匈牙利", "RO": "罗马尼亚",
}

STATUS_FULL = "covered"      # >= 3 个源
STATUS_PARTIAL = "thin"      # 1-2 个源
STATUS_BLIND = "blind"       # 0 个源


def country_of_source(source_id: str) -> str:
    """源 → 国家代码（来自编辑部所在城市）。"""
    place = SOURCE_PLACE.get(source_id)
    if not place:
        return ""
    city = place[0]
    return COUNTRY_OF_CITY.get(city, "")


def region_of_country(code: str) -> str:
    for region, codes in REGIONS.items():
        if code in codes:
            return region
    return "其他"


def _status(source_count: int) -> str:
    if source_count <= 0:
        return STATUS_BLIND
    if source_count < 3:
        return STATUS_PARTIAL
    return STATUS_FULL


def scan(
    sources: Iterable[dict],
    items: Iterable[dict] = (),
    *,
    country_lookup=country_of_source,
) -> dict:
    """产出一张全球覆盖表。纯函数，便于测试。"""
    source_list = list(sources)
    item_counts: dict[str, int] = {}
    lang_counts: dict[str, dict[str, int]] = {}
    for row in items:
        sid = row.get("source_id") or ""
        if not sid:
            continue
        item_counts[sid] = item_counts.get(sid, 0) + 1
        lang = row.get("lang") or "unknown"
        lang_counts.setdefault(sid, {})
        lang_counts[sid][lang] = lang_counts[sid].get(lang, 0) + 1

    by_country: dict[str, dict] = {}
    unknown: list[str] = []
    for src in source_list:
        sid = src.get("id") or ""
        code = country_lookup(sid) or ""
        if not code:
            unknown.append(sid)
            continue
        bucket = by_country.setdefault(
            code, {"code": code, "name": COUNTRY_NAMES.get(code, code), "sources": 0, "items": 0, "langs": {}}
        )
        bucket["sources"] += 1
        bucket["items"] += item_counts.get(sid, 0)
        for lang, n in lang_counts.get(sid, {}).items():
            bucket["langs"][lang] = bucket["langs"].get(lang, 0) + n

    regions_out = []
    for region, codes in REGIONS.items():
        rows = [by_country[c] for c in codes if c in by_country]
        source_count = sum(r["sources"] for r in rows)
        item_count = sum(r["items"] for r in rows)
        regions_out.append(
            {
                "region": region,
                "source_count": source_count,
                "item_count": item_count,
                "country_count": len(rows),
                "status": _status(source_count),
                "countries": sorted(rows, key=lambda r: (-r["sources"], r["code"])),
                "languages": sorted({lang for r in rows for lang in r["langs"]}),
            }
        )

    covered = [r for r in regions_out if r["source_count"] > 0]
    blind = [
        {"region": r["region"], "countries": len(REGIONS[r["region"]])}
        for r in regions_out
        if r["source_count"] == 0
    ]
    total_items = sum(item_counts.values())
    return {
        "regions": regions_out,
        "blind_spots": blind,
        "coverage": {
            "regions_total": len(regions_out),
            "regions_covered": len(covered),
            "pct": round(len(covered) / len(regions_out) * 100),
            "countries_covered": len(by_country),
            "sources_total": len(source_list),
            "items_total": total_items,
        },
        "unmapped_sources": unknown,
    }


def load_sources(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("sources", [])


def load_items(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def report(sources_path: Path, items_path: Path) -> dict:
    return scan(load_sources(sources_path), load_items(items_path))


def latest_items(items_dir: Path | None = None) -> Path:
    """最新的当日条目文件（没有则返回一个不存在的路径）。"""
    directory = items_dir or (Path(__file__).resolve().parent / "data" / "items")
    files = sorted(directory.glob("*.jsonl"))
    return files[-1] if files else directory / "1970-01-01.jsonl"