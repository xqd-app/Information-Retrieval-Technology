"""把陆地多边形采样成点阵（参考图的球面是「点阵大陆」而不是实心块）。

为什么离线做：
球上每个点都要做一次点在多边形内判断，3 万格 × 116 块 ≈ 300 万次，浏览器每帧算不起；
预生成后前端只需按可见性画点（fillRect），4000 个点毫无压力。

输出：[[lat, lon], ...]（保留 1 位小数，体积可控）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "pip_app" / "data"
LAND = DATA_DIR / "land.json"
OUT = DATA_DIR / "land_dots.json"

STEP_DEG = 1.7      # 采样步长（度）：越小越密，1.45° ≈ 160 km
LAT_RANGE = (-84, 84)


def point_in_polygon(lat: float, lon: float, poly: list[list[float]]) -> bool:
    """射线法。poly 是 [[lat, lon], ...]。"""
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        yi, xi = poly[i]
        yj, xj = poly[j]
        if (yi > lat) != (yj > lat):
            x_cross = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_cross:
                inside = not inside
        j = i
    return inside


def build_dots(land_path: Path = LAND, out: Path = OUT, step: float = STEP_DEG) -> Path:
    polys = json.loads(land_path.read_text(encoding="utf-8"))
    boxes = []
    for poly in polys:
        lats = [p[0] for p in poly]
        lons = [p[1] for p in poly]
        boxes.append((min(lats), max(lats), min(lons), max(lons), poly))

    dots: list[list[float]] = []
    lat = LAT_RANGE[0]
    while lat <= LAT_RANGE[1]:
        lon = -180.0
        while lon < 180.0:
            for min_lat, max_lat, min_lon, max_lon, poly in boxes:
                if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
                    continue
                if point_in_polygon(lat, lon, poly):
                    dots.append([round(lat, 1), round(lon, 1)])
                    break
            lon += step
        lat += step

    out.write_text(json.dumps(dots, separators=(",", ":")), encoding="utf-8")
    return out


def main() -> None:
    path = build_dots()
    dots = json.loads(path.read_text(encoding="utf-8"))
    print(f"生成 {path}  ({path.stat().st_size/1024:.1f} KB)")
    print(f"  点 {len(dots)} 个 · 步长 {STEP_DEG}°")


if __name__ == "__main__":
    main()
