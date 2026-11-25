"""Tests for Team Cymru IP-to-ASN bulk whois parsing and lookup module."""

from unittest.mock import patch

from packetvoyage import cymru


def test_cymru_parse_normal_output():
    raw_cymru_output = """
Bulk mode; whois.cymru.com [2026-08-14 10:00:00 +0000]
AS | IP | BGP Prefix | CC | Registry | Allocated | AS Name
15169 | 8.8.8.8 | 8.8.8.0/24 | US | arin | 1992-12-01 | GOOGLE, US
13335 | 1.1.1.1 | 1.1.1.0/24 | US | apnic | 2011-08-11 | CLOUDFLARENET, US
NA | 192.168.1.1 | NA | NA | iana | |
"""
    parsed = cymru._parse(raw_cymru_output)
    assert len(parsed) == 2
    assert "8.8.8.8" in parsed
    assert parsed["8.8.8.8"]["asn"] == "15169"
    assert parsed["8.8.8.8"]["as_name"] == "GOOGLE, US"
    assert parsed["8.8.8.8"]["country_code"] == "US"
    assert parsed["8.8.8.8"]["prefix"] == "8.8.8.0/24"

    assert "1.1.1.1" in parsed
    assert parsed["1.1.1.1"]["asn"] == "13335"
    assert parsed["1.1.1.1"]["as_name"] == "CLOUDFLARENET, US"

    # NA / private IP should be omitted
    assert "192.168.1.1" not in parsed


def test_cymru_annotate_ips_empty():
    assert cymru.annotate_ips([]) == {}


def test_cymru_annotate_ips_success():
    sample_response = """
AS | IP | BGP Prefix | CC | Registry | Allocated | AS Name
15169 | 8.8.8.8 | 8.8.8.0/24 | US | arin | 1992-12-01 | GOOGLE, US
"""
    with patch("packetvoyage.cymru._query", return_value=sample_response):
        res = cymru.annotate_ips(["8.8.8.8"])
        assert "8.8.8.8" in res
        assert res["8.8.8.8"] is not None
        assert res["8.8.8.8"]["asn"] == "15169"


def test_cymru_annotate_ips_network_failure_fallback():
    with patch("packetvoyage.cymru._query", side_effect=TimeoutError("Connection timed out")):
        res = cymru.annotate_ips(["8.8.8.8", "1.1.1.1"])
        assert "8.8.8.8" in res
        assert "1.1.1.1" in res
        assert res["8.8.8.8"] is None
        assert res["1.1.1.1"] is None


def test_cymru_annotate_ips_invalid_format():
    # Invalid IP strings should return None without raising exception or querying
    res = cymru.annotate_ips(["not-an-ip", "8.8.8.8\nbegin\n", ""])
    assert res.get("not-an-ip") is None
    assert res.get("8.8.8.8\nbegin\n") is None
    assert res.get("") is None
