"""点阵数据的不变量：密度要够、要落在陆地上、不能把海洋当陆地。"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from pip_app.tools.build_dots import OUT, point_in_polygon  # noqa: E402


class PointInPolygonTest(unittest.TestCase):
    SQUARE = [[0, 0], [0, 10], [10, 10], [10, 0]]

    def test_inside(self):
        self.assertTrue(point_in_polygon(5, 5, self.SQUARE))

    def test_outside(self):
        self.assertFalse(point_in_polygon(15, 5, self.SQUARE))
        self.assertFalse(point_in_polygon(5, -1, self.SQUARE))


class GeneratedDotsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dots = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else None

    def test_file_exists(self):
        self.assertIsNotNone(self.dots, "先运行 python -m pip_app.tools.build_dots")

    def test_density_is_reasonable(self):
        self.assertGreater(len(self.dots), 2200, "点太少，大陆会看不出形状")
        self.assertLess(len(self.dots), 9000, "点太多，每帧绘制会掉帧")

    def test_coordinates_in_range(self):
        for lat, lon in self.dots:
            self.assertGreaterEqual(lat, -90)
            self.assertLessEqual(lat, 90)
            self.assertGreaterEqual(lon, -180)
            self.assertLessEqual(lon, 180)

    def _near(self, target, radius=1.6):
        return any(abs(lat - target[0]) <= radius and abs(lon - target[1]) <= radius
                   for lat, lon in self.dots)

    def test_known_land_has_dots(self):
        for name, pt in {"北京": (39.9, 116.4), "伦敦": (51.5, -0.1), "旧金山": (37.8, -122.4),
                         "亚马孙": (-3.0, -60.0), "撒哈拉": (23.0, 10.0)}.items():
            self.assertTrue(self._near(pt), f"{name} 附近没有点，采样可能漏了陆地")

    def test_open_ocean_has_no_dots(self):
        for name, pt in {"太平洋中心": (0.0, -150.0), "大西洋中心": (25.0, -40.0),
                         "印度洋中心": (-20.0, 80.0)}.items():
            self.assertFalse(self._near(pt, 3.0), f"{name} 不该有点")


if __name__ == "__main__":
    unittest.main()
