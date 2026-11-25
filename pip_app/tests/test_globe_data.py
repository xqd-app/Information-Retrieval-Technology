"""地球数据的不变量：坐标可核实、采集端可解析、物理量合理。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packetvoyage-master" / "src"))

from pip_app.tools.build_globe_data import (  # noqa: E402
    CITY_COORDS,
    DEFAULT_ORIGIN_CITY,
    SOURCE_PLACE,
    build_city_arcs,
    build_globe_payload,
    distance_and_rtt,
    resolve_origin,
)

ALLOWED_PRECISION = {"hq", "city", "approx"}
TEST_ORIGIN = {"city": "Kunming", "lat": 25.0389, "lon": 102.7183, "source": "test"}


class SourceCoverageTest(unittest.TestCase):
    def test_every_source_maps_to_a_known_city(self):
        unknown = sorted({city for city, _ in SOURCE_PLACE.values() if city not in CITY_COORDS})
        self.assertEqual(unknown, [], f"这些城市没有坐标：{unknown}")

    def test_precision_values_are_documented(self):
        bad = {sid: p for sid, (_, p) in SOURCE_PLACE.items() if p not in ALLOWED_PRECISION}
        self.assertEqual(bad, {}, f"精度标记不合规：{bad}")

    def test_expected_cities_present(self):
        for city in ("San Francisco", "Mountain View", "New York", "Cambridge", "Englewood Cliffs",
                     "Arlington", "Washington", "London", "Paris", "Lyon", "Hannover",
                     "Doha", "Hong Kong", "Beijing", "Qingdao"):
            self.assertIn(city, CITY_COORDS)

    def test_the_decoder_is_in_hannover(self):
        self.assertEqual(SOURCE_PLACE["the-decoder"], ("Hannover", "hq"))

    def test_coordinates_look_like_cities_not_country_centres(self):
        lat, lon = CITY_COORDS["Hannover"]
        self.assertAlmostEqual(lat, 52.37, delta=0.5)
        self.assertAlmostEqual(lon, 9.73, delta=0.5)
        lat, lon = CITY_COORDS["Mountain View"]
        self.assertAlmostEqual(lat, 37.42, delta=0.5)
        self.assertAlmostEqual(lon, -122.08, delta=0.6)


class OriginResolutionTest(unittest.TestCase):
    """采集端解析优先级：手动坐标 > 城市名 > 自动检测 > 默认。"""

    def test_manual_latlon_wins(self):
        import os
        os.environ["PIP_ORIGIN_LATLON"] = "30.5,104.0"
        try:
            origin = resolve_origin(use_detect=False)
            self.assertEqual(origin["source"], "env-latlon")
            self.assertAlmostEqual(origin["lat"], 30.5)
        finally:
            os.environ.pop("PIP_ORIGIN_LATLON", None)

    def test_city_env_looks_up_coordinates(self):
        import os
        os.environ["PIP_ORIGIN_CITY"] = "Tokyo"
        try:
            origin = resolve_origin(use_detect=False)
            self.assertEqual(origin["city"], "Tokyo")
            self.assertEqual(origin["source"], "env-city")
        finally:
            os.environ.pop("PIP_ORIGIN_CITY", None)

    def test_detected_location_is_used_with_provenance(self):
        detected = {"city": "Tokyo", "lat": 35.6289, "lon": 139.7915,
                    "ip": "203.0.113.7", "org": "Example", "source": "ip-api.com",
                    "detected_at": "2026-11-25T00:00:00Z"}
        origin = resolve_origin(detected=detected)
        self.assertTrue(origin["source"].startswith("ip-detected"))
        self.assertEqual(origin["ip"], "203.0.113.7")
        self.assertAlmostEqual(origin["lat"], 35.6289)

    def test_falls_back_to_default_when_detection_fails(self):
        origin = resolve_origin(use_detect=False)
        self.assertEqual(origin["city"], DEFAULT_ORIGIN_CITY)
        self.assertEqual(origin["source"], "default")


class ArcTest(unittest.TestCase):
    def test_arc_has_multiple_points_and_ends(self):
        arc = build_city_arcs("Beijing", "London")
        self.assertGreater(len(arc), 20)
        self.assertAlmostEqual(arc[0][0], CITY_COORDS["Beijing"][0], places=2)
        self.assertAlmostEqual(arc[-1][0], CITY_COORDS["London"][0], places=2)

    def test_distance_beijing_london_is_plausible(self):
        dist, rtt = distance_and_rtt("Beijing", "London")
        self.assertGreater(dist, 7500)
        self.assertLess(dist, 9000)
        self.assertGreater(rtt, 70)
        self.assertLess(rtt, 110)

    def test_antimeridian_arc_stays_continuous(self):
        arc = build_city_arcs("San Francisco", "Beijing")
        lons = [p[1] for p in arc]
        jumps = [abs(b - a) for a, b in zip(lons, lons[1:])]
        self.assertLess(max(jumps), 180, "跨太平洋弧线经度应连续")


class PayloadTest(unittest.TestCase):
    def setUp(self):
        self.payload = build_globe_payload(
            {"San Francisco": 300, "New York": 90, "London": 40, "Beijing": 75, "Hannover": 10},
            sources=[
                {"source_id": "a", "city": "San Francisco", "precision": "hq", "count": 100},
                {"source_id": "b", "city": "San Francisco", "precision": "hq", "count": 200},
                {"source_id": "c", "city": "Hannover", "precision": "hq", "count": 10},
            ],
            origin=TEST_ORIGIN,
        )

    def test_payload_shape(self):
        self.assertEqual(
            set(self.payload),
            {"generated_at", "origin", "solar", "terminator", "cities", "sources"},
        )
        self.assertEqual(len(self.payload["cities"]), 5)
        self.assertEqual(len(self.payload["sources"]), 3)

    def test_origin_is_reported(self):
        self.assertEqual(self.payload["origin"]["city"], "Kunming")
        self.assertAlmostEqual(self.payload["origin"]["lat"], 25.0389, places=3)

    def test_cities_sorted_by_count(self):
        counts = [c["count"] for c in self.payload["cities"]]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_same_city_sources_are_offset(self):
        sf = [n for n in self.payload["sources"] if n["city"] == "San Francisco"]
        self.assertEqual(len(sf), 2)
        self.assertNotEqual((sf[0]["lat"], sf[0]["lon"]), (sf[1]["lat"], sf[1]["lon"]))
        self.assertLess(abs(sf[0]["lat"] - sf[1]["lat"]), 0.2)
        self.assertLess(abs(sf[0]["lon"] - sf[1]["lon"]), 0.3)

    def test_terminator_is_dense_polyline(self):
        self.assertGreater(len(self.payload["terminator"]), 100)

    def test_each_city_has_arc_and_physics(self):
        for city in self.payload["cities"]:
            if city["distance_km"] == 0:
                self.assertEqual(len(city["arc"]), 1)
                continue
            self.assertGreater(len(city["arc"]), 2)
            self.assertGreater(city["min_rtt_ms"], 0)


if __name__ == "__main__":
    unittest.main()
