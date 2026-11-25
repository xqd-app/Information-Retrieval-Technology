"""用 packetvoyage.geo 生成地球数据：真实编辑部坐标 + 大圆航迹 + 昼夜 + 光纤物理。

采集端（origin）按优先级解析：
    1. PIP_ORIGIN_LATLON="25.04,102.72"   直接给坐标
    2. PIP_ORIGIN_CITY="Kunming"          给城市名（查 CITY_COORDS）
    3. 自动检测（detect_location）        带 source / ip —— 注意这是出口 IP 的位置
    4. 默认 Kunming

坐标精度（`precision`，仅用于展示）：
    hq     官网 contact / imprint 可核实
    city   只知道城市
    approx 只确定区域
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
for candidate in (ROOT, ROOT / "packetvoyage-master" / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from packetvoyage import geo  # noqa: E402

from pip_app.tools.detect_location import detect  # noqa: E402

OUT = ROOT / "pip_app" / "data" / "globe.json"
DEFAULT_ORIGIN_CITY = "Kunming"

CITY_COORDS = {
    "San Francisco": (37.7749, -122.4194),
    "Mountain View": (37.4220, -122.0841),
    "New York": (40.7128, -74.0060),
    "Cambridge": (42.3736, -71.1097),
    "Englewood Cliffs": (40.8854, -73.9521),
    "Arlington": (38.8816, -77.0910),
    "Washington": (38.9072, -77.0369),
    "London": (51.5072, -0.1276),
    "Paris": (48.8566, 2.3522),
    "Lyon": (45.7640, 4.8357),
    "Hannover": (52.3721, 9.7350),
    "Doha": (25.2854, 51.5310),
    "Hong Kong": (22.3193, 114.1694),
    "Beijing": (39.9042, 116.4074),
    "Shanghai": (31.2304, 121.4737),
    "Qingdao": (36.0671, 120.3826),
    "Kunming": (25.0389, 102.7183),
    "Tokyo": (35.6289, 139.7915),
    "Singapore": (1.3521, 103.8198),
    "Frankfurt": (50.1109, 8.6821),
    "Amsterdam": (52.3676, 4.9041),
    "Seoul": (37.5665, 126.9780),
    "Sydney": (-33.8688, 151.2093),
    "Mumbai": (19.0760, 72.8777),
    "Dubai": (25.2048, 55.2708),
    "Chennai": (13.0827, 80.2707),
    "Karachi": (24.8607, 67.0011),
    "São Paulo": (-23.5505, -46.6333),
    "Buenos Aires": (-34.6037, -58.3816),
    "Abuja": (9.0765, 7.3986),
    "Brazzaville": (-4.2634, 15.2429),
    "Nairobi": (-1.2921, 36.8219),
    "Wellington": (-41.2865, 174.7762),
    "Bangkok": (13.7563, 100.5018),
    "Hanoi": (21.0278, 105.8342),
    "Manila": (14.5995, 120.9842),
    "Warsaw": (52.2297, 21.0122),
    "Kyiv": (50.4501, 30.5234),
    "Belgrade": (44.7866, 20.4489),
    "Madrid": (40.4168, -3.7038),
    "Jerusalem": (31.7683, 35.2137),
}

SOURCE_PLACE = {
    "techcrunch-ai": ("San Francisco", "hq"),
    "ars-technica": ("New York", "hq"),
    "theverge": ("New York", "hq"),
    "mit-tech-review": ("Cambridge", "hq"),
    "google-ai-blog": ("Mountain View", "hq"),
    "deepmind": ("London", "hq"),
    "huggingface-blog": ("New York", "hq"),
    "hn-frontpage": ("San Francisco", "hq"),
    "simonwillison": ("San Francisco", "approx"),
    "github-blog": ("San Francisco", "hq"),
    "google-news-ai": ("Mountain View", "approx"),
    "openai-news": ("San Francisco", "hq"),
    "the-decoder": ("Hannover", "hq"),
    "product-hunt": ("San Francisco", "hq"),
    "latent-space": ("San Francisco", "approx"),
    "gh-trending": ("San Francisco", "hq"),
    "gh-changelog": ("San Francisco", "hq"),
    "cnbc-world": ("Englewood Cliffs", "hq"),
    "politico": ("Arlington", "hq"),
    "thehill": ("Washington", "hq"),
    "npr-world": ("Washington", "hq"),
    "wsj-markets": ("New York", "hq"),
    "guardian-world": ("London", "hq"),
    "financial-times": ("London", "hq"),
    "france24": ("Paris", "hq"),
    "euronews": ("Lyon", "hq"),
    "aljazeera": ("Doha", "hq"),
    "scmp": ("Hong Kong", "hq"),
    "ithome": ("Qingdao", "city"),
    "qbitai": ("Beijing", "city"),
    "infoq-cn": ("Beijing", "city"),
    "timesofisrael": ("Jerusalem", "hq"),
    "hindu-world": ("Chennai", "hq"),
    "toi-world": ("Mumbai", "hq"),
    "dawn-world": ("Karachi", "hq"),
    "g1-world": ("São Paulo", "hq"),
    "lanacion": ("Buenos Aires", "hq"),
    "clarin": ("Buenos Aires", "hq"),
    "premium-times": ("Abuja", "hq"),
    "africanews": ("Brazzaville", "city"),
    "standard-ke": ("Nairobi", "hq"),
    "guardian-au": ("Sydney", "hq"),
    "rnz-world": ("Wellington", "hq"),
    "sbs-news": ("Sydney", "hq"),
    "straitstimes-world": ("Singapore", "hq"),
    "cna-asia": ("Singapore", "hq"),
    "bangkokpost": ("Bangkok", "hq"),
    "vnexpress": ("Hanoi", "hq"),
    "rappler": ("Manila", "hq"),
    "notesfrompoland": ("Warsaw", "hq"),
    "kyivpost": ("Kyiv", "hq"),
    "balkaninsight": ("Belgrade", "hq"),
    "elpais-america": ("Madrid", "hq"),
}

COUNTRY_OF_CITY = {
    "San Francisco": "US", "Mountain View": "US", "New York": "US", "Cambridge": "US",
    "Englewood Cliffs": "US", "Arlington": "US", "Washington": "US",
    "London": "GB", "Paris": "FR", "Lyon": "FR", "Hannover": "DE",
    "Doha": "QA", "Hong Kong": "HK", "Beijing": "CN", "Shanghai": "CN", "Qingdao": "CN",
    "Kunming": "CN", "Tokyo": "JP", "Singapore": "SG", "Frankfurt": "DE",
    "Chennai": "IN", "Karachi": "PK", "São Paulo": "BR", "Buenos Aires": "AR", "Abuja": "NG", "Brazzaville": "CG", "Nairobi": "KE", "Wellington": "NZ", "Bangkok": "TH", "Hanoi": "VN", "Manila": "PH", "Warsaw": "PL", "Jerusalem": "IL", "Kyiv": "UA", "Belgrade": "RS", "Madrid": "ES", 
    "Amsterdam": "NL", "Seoul": "KR", "Sydney": "AU", "Mumbai": "IN", "Dubai": "AE",
}

SOURCE_CITY = {sid: city for sid, (city, _) in SOURCE_PLACE.items()}


def _parse_latlon(raw: str) -> tuple[float, float] | None:
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None


def resolve_origin(*, use_detect: bool = True, detected: dict | None = None) -> dict[str, Any]:
    """返回 {city, lat, lon, source, ip?}；永远有结果（最终回落到昆明）。"""
    latlon = os.environ.get("PIP_ORIGIN_LATLON", "").strip()
    if latlon:
        parsed = _parse_latlon(latlon)
        if parsed:
            return {
                "city": os.environ.get("PIP_ORIGIN_NAME", "Manual"),
                "lat": parsed[0],
                "lon": parsed[1],
                "source": "env-latlon",
            }

    city = os.environ.get("PIP_ORIGIN_CITY", "").strip()
    if city and city in CITY_COORDS:
        lat, lon = CITY_COORDS[city]
        return {"city": city, "lat": lat, "lon": lon, "source": "env-city"}

    if use_detect:
        info = detected if detected is not None else detect()
        if info:
            return {
                "city": info.get("city") or info.get("region") or "Detected",
                "lat": float(info["lat"]),
                "lon": float(info["lon"]),
                "source": f"ip-detected:{info.get('source', '?')}",
                "ip": info.get("ip", ""),
                "org": info.get("org", ""),
                "detected_at": info.get("detected_at", ""),
            }

    lat, lon = CITY_COORDS[DEFAULT_ORIGIN_CITY]
    return {"city": DEFAULT_ORIGIN_CITY, "lat": lat, "lon": lon, "source": "default"}


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return geo.haversine_km(lat1, lon1, lat2, lon2)


def distance_and_rtt(city_a: str, city_b: str) -> tuple[float, float]:
    lat1, lon1 = CITY_COORDS[city_a]
    lat2, lon2 = CITY_COORDS[city_b]
    km = haversine(lat1, lon1, lat2, lon2)
    return km, geo.min_rtt_ms(km)


def build_city_arcs(city_a: str, city_b: str) -> list[list[float]]:
    return geo.great_circle_arc(CITY_COORDS[city_a], CITY_COORDS[city_b])


def _offset(lat: float, lon: float, index: int, total: int) -> tuple[float, float]:
    if total <= 1:
        return lat, lon
    angle = (index / total) * 2 * math.pi
    radius = 0.055 + 0.02 * (index % 3)
    return (
        round(lat + radius * math.sin(angle), 4),
        round(lon + radius * math.cos(angle) / max(0.2, math.cos(math.radians(lat))), 4),
    )


def build_globe_payload(
    city_counts: dict[str, int],
    sources: list[dict] | None = None,
    *,
    origin: dict[str, Any] | None = None,
) -> dict:
    origin = origin or resolve_origin()
    now = datetime.now(timezone.utc)
    decl = 23.44 * math.sin(math.radians(360.0 / 365.0 * (now.timetuple().tm_yday - 81)))
    hour = now.hour + now.minute / 60.0
    solar_lon = 180.0 - 15.0 * hour
    if solar_lon < -180.0:
        solar_lon += 360.0

    cities = []
    for city, count in city_counts.items():
        if city not in CITY_COORDS:
            continue
        lat, lon = CITY_COORDS[city]
        km = haversine(lat, lon, origin["lat"], origin["lon"])
        cities.append(
            {
                "city": city,
                "country": COUNTRY_OF_CITY.get(city, "US"),
                "lat": lat,
                "lon": lon,
                "count": int(count),
                "distance_km": round(km),
                "min_rtt_ms": round(geo.min_rtt_ms(km), 1),
                "arc": geo.great_circle_arc((lat, lon), (origin["lat"], origin["lon"])),
            }
        )
    cities.sort(key=lambda c: c["count"], reverse=True)

    nodes = []
    if sources:
        by_city: dict[str, list[dict]] = {}
        for row in sources:
            by_city.setdefault(row["city"], []).append(row)
        for city, group in by_city.items():
            if city not in CITY_COORDS:
                continue
            base_lat, base_lon = CITY_COORDS[city]
            for i, row in enumerate(sorted(group, key=lambda r: r["source_id"])):
                lat, lon = _offset(base_lat, base_lon, i, len(group))
                nodes.append(
                    {
                        "source_id": row["source_id"],
                        "city": city,
                        "country": COUNTRY_OF_CITY.get(city, "US"),
                        "lat": lat,
                        "lon": lon,
                        "count": int(row.get("count", 0)),
                        "precision": row.get("precision", "city"),
                    }
                )

    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "origin": {
            "city": origin["city"],
            "lat": origin["lat"],
            "lon": origin["lon"],
            "source": origin.get("source", ""),
            "ip": origin.get("ip", ""),
            "org": origin.get("org", ""),
            "detected_at": origin.get("detected_at", ""),
        },
        "solar": {"lat": round(decl, 2), "lon": round(solar_lon, 2)},
        "terminator": geo.terminator_points(now),
        "cities": cities,
        "sources": nodes,
    }


def counts_from_items(path: Path) -> tuple[dict[str, int], list[dict]]:
    city_counts: dict[str, int] = {}
    per_source: dict[str, int] = {}
    if not path.exists():
        return city_counts, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        sid = row.get("source_id", "")
        if sid in SOURCE_PLACE:
            per_source[sid] = per_source.get(sid, 0) + 1

    sources = []
    for sid, count in per_source.items():
        city, precision = SOURCE_PLACE[sid]
        city_counts[city] = city_counts.get(city, 0) + count
        sources.append({"source_id": sid, "city": city, "precision": precision, "count": count})
    return city_counts, sources


def latest_items_path() -> Path:
    files = sorted((ROOT / "pip_app" / "data" / "items").glob("*.jsonl"))
    return files[-1] if files else ROOT / "pip_app" / "data" / "items" / "2026-11-25.jsonl"


def main() -> None:
    city_counts, sources = counts_from_items(latest_items_path())
    origin = resolve_origin()
    payload = build_globe_payload(city_counts, sources, origin=origin)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    total = sum(c["count"] for c in payload["cities"])
    hq = sum(1 for n in payload["sources"] if n["precision"] == "hq")
    o = payload["origin"]
    print(f"生成 {OUT}  ({OUT.stat().st_size/1024:.1f} KB)")
    print(f"  采集端 {o['city']} ({o['lat']:.2f}, {o['lon']:.2f})  来源={o['source']}"
          + (f"  IP={o['ip']}" if o.get("ip") else ""))
    print(f"  城市 {len(payload['cities'])} · 来源点位 {len(payload['sources'])}（hq 核实 {hq}）· 条目 {total}")
    for c in payload["cities"]:
        print(f"  {c['city']:<18}{c['count']:>5} 条  {c['distance_km']:>6} km  RTT≥{c['min_rtt_ms']:>7} ms")


if __name__ == "__main__":
    main()
