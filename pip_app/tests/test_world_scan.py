"""全球覆盖扫描的契约：区域聚合、盲区识别、覆盖率、未知来源处理。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packetvoyage-master" / "src"))

from pip_app.world_scan import (  # noqa: E402
    REGIONS,
    STATUS_BLIND,
    STATUS_FULL,
    STATUS_PARTIAL,
    country_of_source,
    region_of_country,
    scan,
)


class MappingTest(unittest.TestCase):
    def test_known_source_country(self):
        self.assertEqual(country_of_source("the-decoder"), "DE")
        self.assertEqual(country_of_source("openai-news"), "US")
        self.assertEqual(country_of_source("qbitai"), "CN")
        self.assertEqual(country_of_source("aljazeera"), "QA")

    def test_unknown_source_country_is_empty(self):
        self.assertEqual(country_of_source("no-such-source"), "")

    def test_region_lookup(self):
        self.assertEqual(region_of_country("US"), "北美")
        self.assertEqual(region_of_country("CN"), "东亚")
        self.assertEqual(region_of_country("ZA"), "非洲")
        self.assertEqual(region_of_country("ZZ"), "其他")


class ScanTest(unittest.TestCase):
    def _sources(self, *pairs):
        return [{"id": sid, "name": sid, "domain": "ai", "lang": "en", "url": ""} for sid in pairs]

    def test_region_aggregation(self):
        lookup = {"a": "US", "b": "US", "c": "CN", "d": "DE"}
        out = scan(self._sources("a", "b", "c", "d"), [{"source_id": "a"}, {"source_id": "a"}, {"source_id": "c"}],
                   country_lookup=lookup.get)
        na = next(r for r in out["regions"] if r["region"] == "北美")
        self.assertEqual(na["source_count"], 2)
        self.assertEqual(na["item_count"], 2)
        self.assertEqual(na["status"], STATUS_PARTIAL)

    def test_full_status_needs_three_sources(self):
        lookup = {"a": "US", "b": "US", "c": "US"}
        out = scan(self._sources("a", "b", "c"), country_lookup=lookup.get)
        na = next(r for r in out["regions"] if r["region"] == "北美")
        self.assertEqual(na["status"], STATUS_FULL)

    def test_blind_regions_are_reported(self):
        out = scan(self._sources("a"), country_lookup={"a": "US"}.get)
        blind = {b["region"] for b in out["blind_spots"]}
        self.assertIn("非洲", blind)
        self.assertIn("拉美", blind)
        self.assertNotIn("北美", blind)

    def test_coverage_percentage(self):
        lookup = {"a": "US", "b": "CN"}
        out = scan(self._sources("a", "b"), country_lookup=lookup.get)
        self.assertEqual(out["coverage"]["regions_total"], len(REGIONS))
        self.assertEqual(out["coverage"]["regions_covered"], 2)
        self.assertEqual(out["coverage"]["pct"], round(2 / len(REGIONS) * 100))
        self.assertEqual(out["coverage"]["countries_covered"], 2)

    def test_unmapped_sources_are_listed_not_counted(self):
        out = scan(self._sources("a", "ghost"), country_lookup={"a": "US"}.get)
        self.assertEqual(out["unmapped_sources"], ["ghost"])
        self.assertEqual(out["coverage"]["sources_total"], 2)
        self.assertEqual(out["coverage"]["countries_covered"], 1)

    def test_empty_input_is_safe(self):
        out = scan([], [], country_lookup=lambda sid: "")
        self.assertEqual(out["coverage"]["items_total"], 0)
        self.assertEqual(out["coverage"]["pct"], 0)
        self.assertEqual(len(out["blind_spots"]), len(REGIONS))

    def test_languages_collected_per_region(self):
        out = scan(
            self._sources("a"),
            [{"source_id": "a", "lang": "zh"}],
            country_lookup={"a": "CN"}.get,
        )
        ea = next(r for r in out["regions"] if r["region"] == "东亚")
        self.assertIn("zh", ea["languages"])


class RealDataTest(unittest.TestCase):
    """跑真实源清单，确认结果合理（不是空表）。"""

    def test_real_sources_cover_multiple_regions(self):
        from pip_app.world_scan import load_items, load_sources, latest_items

        sources = load_sources(ROOT / "pip_app" / "sources.json")
        items = load_items(latest_items())
        out = scan(sources, items)
        self.assertGreaterEqual(out["coverage"]["regions_covered"], 4)
        self.assertGreater(out["coverage"]["countries_covered"], 3)
        self.assertEqual(out["unmapped_sources"], [], "所有源都应能解析出国家")
        self.assertGreater(out["coverage"]["items_total"], 100)


if __name__ == "__main__":
    unittest.main()
