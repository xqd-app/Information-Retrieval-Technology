"""Tests for PeeringDB network-lookup parsing and batching."""

from unittest.mock import patch

from packetvoyage import peeringdb


def test_peeringdb_parse_normal_payload():
    payload = {
        "data": [
            {
                "asn": 13335,
                "name": "Cloudflare, Inc.",
                "aka": "",
                "info_type": "Content",
                "policy_general": "Open",
                "website": "https://www.cloudflare.com",
                "netixlan_set": [
                    {"name": "DE-CIX Frankfurt", "speed": 100000},
                    {"name": "LINX LON1", "speed": 100000},
                    {"name": "DE-CIX Frankfurt", "speed": 10000},
                ],
            }
        ]
    }
    parsed = peeringdb._parse(payload)
    assert "13335" in parsed
    assert parsed["13335"]["name"] == "Cloudflare, Inc."
    assert parsed["13335"]["info_type"] == "Content"
    assert parsed["13335"]["policy_general"] == "Open"
    assert parsed["13335"]["ix_count"] == 3
    assert parsed["13335"]["ix_names"] == ["DE-CIX Frankfurt", "LINX LON1"]


def test_peeringdb_parse_skips_entries_without_asn():
    parsed = peeringdb._parse({"data": [{"name": "no asn here"}]})
    assert parsed == {}


def test_peeringdb_annotate_asns_empty():
    assert peeringdb.annotate_asns([]) == {}


def test_peeringdb_annotate_asns_invalid_values_only():
    assert peeringdb.annotate_asns(["not-an-asn", "", None]) == {}  # type: ignore[list-item]


def test_peeringdb_annotate_asns_success():
    sample = {
        "data": [
            {
                "asn": 15169,
                "name": "Google LLC",
                "info_type": "Content",
                "policy_general": "Selective",
                "netixlan_set": [],
            }
        ]
    }
    with patch("packetvoyage.peeringdb._query", return_value=sample):
        res = peeringdb.annotate_asns([15169])
        assert res["15169"] is not None
        assert res["15169"]["name"] == "Google LLC"
        assert res["15169"]["ix_count"] == 0


def test_peeringdb_annotate_asns_no_record_for_asn():
    """An ASN with no PeeringDB entry (most ASNs) should map to None, not error."""
    with patch("packetvoyage.peeringdb._query", return_value={"data": []}):
        res = peeringdb.annotate_asns([64512])
        assert res == {"64512": None}


def test_peeringdb_annotate_asns_network_failure_fallback():
    with patch("packetvoyage.peeringdb._query", side_effect=TimeoutError("timed out")):
        res = peeringdb.annotate_asns([13335, 15169])
        assert res == {"13335": None, "15169": None}


def test_peeringdb_annotate_asns_dedupes_and_sorts_query_args():
    captured: dict[str, list[int]] = {}

    def fake_query(asns: list[int]) -> dict:
        captured["asns"] = asns
        return {"data": []}

    with patch("packetvoyage.peeringdb._query", side_effect=fake_query):
        peeringdb.annotate_asns([15169, "15169", 13335])
        assert sorted(captured["asns"]) == [13335, 15169]
