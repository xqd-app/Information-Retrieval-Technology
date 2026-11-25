"""生成真实海岸线数据（Natural Earth → 抽稀 → data/land.json）。

支持 110m（低精度，默认）与 50m（高精度）。

- 110m：116 块 / ~2,100 点 / ~31 KB，容差 0.35°
- 50m ：海岸线细一倍，容差按比例收紧，点数控制在可流畅绘制的范围内

输出格式：[[[lat, lon], ...], ...]（注意转成 lat,lon，与前端投影一致）。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "pip_app" / "data"
LAND_OUT = DATA_DIR / "land.json"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
MIN_POINTS = 4
MIN_AREA_DEG2 = 0.035   # 小于此面积（度²）的碎片丢弃：约 430 km²，肉眼几乎不可见

# scale -> (源文件, 默认容差, 原始缓存名)
SCALES = {
    "110m": ("ne_110m_land.geojson", 0.35, "land_raw_110m.geojson"),
    "50m": ("ne_50m_land.geojson", 0.16, "land_raw_50m.geojson"),
}
BASE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
EPS_DEG = SCALES["110m"][1]


def source_url(scale: str = "110m") -> str:
    return BASE_URL + SCALES[scale][0]


def raw_path(scale: str = "110m") -> Path:
    return DATA_DIR / SCALES[scale][2]


def _point_line_dist(pt: list[float], a: list[float], b: list[float]) -> float:
    (py, px), (ay, ax), (by, bx) = pt, a, b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def simplify(points: list[list[float]], eps: float = EPS_DEG) -> list[list[float]]:
    """Douglas-Peucker：保留形状，丢掉共线点。"""
    if len(points) < 3:
        return points
    start, end = points[0], points[-1]
    idx, dist = 0, 0.0
    for i in range(1, len(points) - 1):
        d = _point_line_dist(points[i], start, end)
        if d > dist:
            idx, dist = i, d
    if dist > eps:
        left = simplify(points[: idx + 1], eps)
        right = simplify(points[idx:], eps)
        return left[:-1] + right
    return [start, end]


def polygon_area(pts: list[list[float]]) -> float:
    """鞋带公式：经纬度近似的多边形面积（度²）。"""
    s = 0.0
    n = len(pts)
    for i in range(n):
        y1, x1 = pts[i]
        y2, x2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def to_latlon_polygons(features: list[dict]) -> list[list[list[float]]]:
    """GeoJSON features → [[[lat, lon], ...], ...]（顺带做 lon/lat 交换）。"""
    out: list[list[list[float]]] = []
    for feature in features:
        geom = feature.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates") or []
        rings: list[list[list[float]]] = []
        if gtype == "Polygon":
            rings = [coords[0]] if coords else []
        elif gtype == "MultiPolygon":
            rings = [poly[0] for poly in coords if poly]
        for ring in rings:
            out.append([[lat, lon] for lon, lat in ring])
    return out


def build_land(
    out: Path = LAND_OUT,
    *,
    scale: str = "110m",
    eps: float | None = None,
    download: bool = True,
) -> Path:
    if scale not in SCALES:
        raise ValueError(f"scale 必须是 {sorted(SCALES)} 之一")
    eps = SCALES[scale][1] if eps is None else eps
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    raw = raw_path(scale)
    if not raw.exists() and download:
        request = urllib.request.Request(source_url(scale), headers={"User-Agent": UA})
        with urllib.request.urlopen(request, timeout=60) as resp:
            raw.write_bytes(resp.read())

    payload = json.loads(raw.read_text(encoding="utf-8"))
    polygons = to_latlon_polygons(payload.get("features", []))

    simplified: list[list[list[float]]] = []
    for poly in polygons:
        if len(poly) < MIN_POINTS:
            continue
        if polygon_area(poly) < MIN_AREA_DEG2:
            continue
        kept = simplify(poly, eps)
        if len(kept) >= MIN_POINTS:
            simplified.append([[round(lat, 2), round(lon, 2)] for lat, lon in kept])

    simplified.sort(key=len, reverse=True)
    out.write_text(json.dumps(simplified, separators=(",", ":")), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="生成海岸线数据")
    parser.add_argument("--scale", default="50m", choices=sorted(SCALES))
    parser.add_argument("--eps", type=float, default=None, help="抽稀容差（度），留空用该 scale 默认值")
    args = parser.parse_args(argv)

    path = build_land(scale=args.scale, eps=args.eps)
    polys = json.loads(path.read_text(encoding="utf-8"))
    total = sum(len(p) for p in polys)
    print(f"生成 {path}  ({path.stat().st_size/1024:.1f} KB)")
    print(f"  scale={args.scale} · 多边形 {len(polys)} 块 · 总点数 {total} · 最大块 {len(polys[0])} 点")


if __name__ == "__main__":
    main()
