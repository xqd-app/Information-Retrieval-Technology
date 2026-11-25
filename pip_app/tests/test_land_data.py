"""真实海岸线数据的不变量（Natural Earth 110m 抽稀后）。"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from pip_app.tools.build_land_data import LAND_OUT, simplify, to_latlon_polygons  # noqa: E402


class SimplifyTest(unittest.TestCase):
    def test_short_polyline_is_kept(self):
        pts = [[0, 0], [1, 1]]
        self.assertEqual(simplify(pts, eps=0.5), pts)

    def test_collinear_points_are_dropped(self):
        pts = [[0, 0], [0, 1], [0, 2], [0, 3]]
        kept = simplify(pts, eps=0.1)
        self.assertLessEqual(len(kept), 3)
        self.assertEqual(kept[0], [0, 0])
        self.assertEqual(kept[-1], [0, 3])

    def test_corner_point_survives(self):
        pts = [[0, 0], [0, 1], [1, 1]]
        self.assertIn([0, 1], simplify(pts, eps=0.1))


class LatLonTest(unittest.TestCase):
    def test_geojson_lonlat_is_swapped(self):
        # GeoJSON 是 [lon, lat]
        polys = to_latlon_polygons([
            {"geometry": {"type": "Polygon", "coordinates": [[[10, 50], [11, 50], [11, 51], [10, 50]]]}}
        ])
        self.assertEqual(polys[0][0], [50, 10])

    def test_multipolygon_is_flattened(self):
        polys = to_latlon_polygons([
            {"geometry": {"type": "MultiPolygon", "coordinates": [
                [[[0, 0], [1, 0], [1, 1]]],
                [[[5, 5], [6, 5], [6, 6]]],
            ]}}
        ])
        self.assertEqual(len(polys), 2)


class GeneratedLandTest(unittest.TestCase):
    """生成物本身的体检（若 data/land.json 尚未生成则跳过）。"""

    @classmethod
    def setUpClass(cls):
        cls.polys = json.loads(LAND_OUT.read_text(encoding="utf-8")) if LAND_OUT.exists() else None

    def test_file_exists(self):
        self.assertIsNotNone(self.polys, "先运行 python -m pip_app.tools.build_land_data")

    def test_enough_polygons(self):
        self.assertGreater(len(self.polys), 20, "陆地多边形太少，可能解析失败")

    def test_coordinates_in_range(self):
        for poly in self.polys:
            for lat, lon in poly:
                self.assertGreaterEqual(lat, -90)
                self.assertLessEqual(lat, 90)
                self.assertGreaterEqual(lon, -180)
                self.assertLessEqual(lon, 180)

    def test_size_budget(self):
        total = sum(len(p) for p in self.polys)
        self.assertGreater(total, 800, "点太少，形状会失真")
        self.assertLess(total, 8000, "点太多，页面体积会失控")

    def test_known_landmasses_present(self):
        """抽查：欧亚、北美、非洲、澳洲各应落在一个较大的多边形里。"""
        probes = {"eurasia": (50, 20), "namerica": (45, -100), "africa": (5, 20), "australia": (-25, 135)}

        def inside(pt, poly):
            lat, lon = pt
            c = False
            j = len(poly) - 1
            for i in range(len(poly)):
                yi, xi = poly[i]
                yj, xj = poly[j]
                if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                    c = not c
                j = i
            return c

        for name, pt in probes.items():
            self.assertTrue(any(inside(pt, poly) for poly in self.polys), f"{name} 没有覆盖点 {pt}")


if __name__ == "__main__":
    unittest.main()
