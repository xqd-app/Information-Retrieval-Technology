"""自动检测「本机位置」用于采集端。

关键事实：检测到的是**公网出口位置**，走代理/VPN 时会指向代理节点，
所以结果必须带来源标记，且允许手动覆盖。

优先级（在 build_globe_data 里体现）：
    1. PIP_ORIGIN_LATLON="25.04,102.72"   直接给坐标
    2. PIP_ORIGIN_CITY="Kunming"          给城市名（查 CITY_COORDS）
    3. 自动 IP 检测（本模块）             带 source / org / ip
    4. 默认 Kunming
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent.parent
CACHE = ROOT / "pip_app" / "data" / "geo_self.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
DEFAULT_TTL = 24 * 3600


def _get(url: str, timeout: float = 6.0) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def parse_ipapi(payload: dict) -> dict | None:
    if payload.get("status") != "success":
        return None
    return {
        "city": payload.get("city") or payload.get("regionName") or "",
        "region": payload.get("regionName", ""),
        "country": payload.get("country", ""),
        "lat": float(payload["lat"]),
        "lon": float(payload["lon"]),
        "ip": payload.get("query", ""),
        "org": "",
    }


def parse_ipwho(payload: dict) -> dict | None:
    if not payload.get("success"):
        return None
    conn = payload.get("connection") or {}
    return {
        "city": payload.get("city") or payload.get("region") or "",
        "region": payload.get("region", ""),
        "country": payload.get("country", ""),
        "lat": float(payload["latitude"]),
        "lon": float(payload["longitude"]),
        "ip": payload.get("ip", ""),
        "org": conn.get("isp") or conn.get("org") or "",
    }


def parse_ipinfo(payload: dict) -> dict | None:
    loc = (payload.get("loc") or "").split(",")
    if len(loc) != 2:
        return None
    return {
        "city": payload.get("city", ""),
        "region": payload.get("region", ""),
        "country": payload.get("country", ""),
        "lat": float(loc[0]),
        "lon": float(loc[1]),
        "ip": payload.get("ip", ""),
        "org": payload.get("org", ""),
    }


PROVIDERS: list[tuple[str, str, Callable[[dict], dict | None]]] = [
    ("ip-api.com", "http://ip-api.com/json/?fields=status,country,regionName,city,lat,lon,query", parse_ipapi),
    ("ipwho.is", "https://ipwho.is/", parse_ipwho),
    ("ipinfo.io", "https://ipinfo.io/json", parse_ipinfo),
]


def load_cache(path: Path = CACHE, *, ttl: int = DEFAULT_TTL, now: float | None = None) -> dict | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    ts = float(payload.get("detected_ts", 0))
    if (now if now is not None else time.time()) - ts > ttl:
        return None
    return payload


def detect(
    *,
    cache_path: Path = CACHE,
    ttl: int = DEFAULT_TTL,
    force: bool = False,
    fetcher: Callable[[str], dict] | None = None,
    now: float | None = None,
) -> dict | None:
    """依次尝试多个接口；成功即写缓存。全部失败返回 None（调用方回落到手动/默认）。"""
    if not force:
        cached = load_cache(cache_path, ttl=ttl, now=now)
        if cached:
            return cached

    fetch = fetcher or _get
    stamp = now if now is not None else time.time()
    for name, url, parser in PROVIDERS:
        try:
            raw = fetch(url)
            info = parser(raw)
        except Exception:  # noqa: BLE001 - 探测失败继续下一个
            continue
        if not info or not info.get("lat"):
            continue
        info.update({"source": name, "detected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stamp)), "detected_ts": stamp})
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass
        return info
    return None


if __name__ == "__main__":
    result = detect(force=True)
    if result:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("检测失败：所有接口不可达")
