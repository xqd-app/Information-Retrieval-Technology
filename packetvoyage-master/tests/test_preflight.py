"""Unit tests for packetvoyage.preflight (local host research / CDN detection)."""

from __future__ import annotations

from unittest.mock import patch

from packetvoyage.preflight import HostReport, _annotate_peering, classify, hostname_provider


class TestHostnameProvider:
    def test_known_cdn_suffix(self) -> None:
        assert hostname_provider("d123.cloudfront.net") == "Amazon CloudFront"
        assert hostname_provider("cdn.fastly.net") == "Fastly"
        assert hostname_provider("www.akamaized.net") == "Akamai"

    def test_bare_apex_matches(self) -> None:
        assert hostname_provider("cloudfront.net") == "Amazon CloudFront"

    def test_lookalike_does_not_match(self) -> None:
        assert hostname_provider("fakeakamai.net") is None
        assert hostname_provider("fastly.example.org") is None


class TestClassify:
    def test_cdn_via_cname_chain(self) -> None:
        report = classify(
            "www.example.com",
            cname_chain=["www.example.com", "d123.cloudfront.net"],
            resolver_sets={"system": ["203.0.113.9"]},
            asn={},
        )
        assert report.verdict == "cdn"
        assert report.providers == ["Amazon CloudFront"]
        assert report.anycast is True

    def test_cdn_via_known_asn(self) -> None:
        report = classify(
            "example.com",
            cname_chain=["example.com"],
            resolver_sets={"system": ["1.1.1.1"]},
            asn={"1.1.1.1": {"asn": "13335", "as_name": "CLOUDFLARENET"}},
        )
        assert report.verdict == "cdn"
        assert report.providers == ["Cloudflare"]

    def test_cdn_via_org_keyword(self) -> None:
        report = classify(
            "example.com",
            resolver_sets={"system": ["203.0.113.9"]},
            asn={"203.0.113.9": {"asn": "16509", "as_name": "AMAZON-CLOUDFRONT"}},
        )
        assert report.verdict == "cdn"
        assert report.providers == ["Amazon CloudFront"]

    def test_generic_google_asn_is_not_a_cdn(self) -> None:
        report = classify(
            "example.com",
            resolver_sets={"system": ["8.8.8.8"]},
            asn={"8.8.8.8": {"asn": "15169", "as_name": "GOOGLE"}},
        )
        assert report.verdict == "direct"
        assert report.providers == []

    def test_geodns_when_resolvers_disagree(self) -> None:
        report = classify(
            "geo.example.com",
            resolver_sets={
                "system": ["203.0.113.1"],
                "1.1.1.1": ["203.0.113.2"],
            },
            asn={},
        )
        assert report.verdict == "geodns"

    def test_direct_when_single_ip_no_cdn_signals(self) -> None:
        report = classify(
            "origin.example.com",
            resolver_sets={"system": ["203.0.113.9"], "1.1.1.1": ["203.0.113.9"]},
            asn={},
        )
        assert report.verdict == "direct"
        assert report.anycast is False

    def test_dns_error_when_nothing_resolved(self) -> None:
        report = classify("nowhere.invalid", resolver_sets={"system": []}, asn={})
        assert report.verdict == "dns_error"


class TestAnnotatePeering:
    def test_skipped_by_default(self) -> None:
        report = HostReport(host="example.com")
        _annotate_peering(report, enable_peeringdb_lookup=False)
        assert report.peeringdb_lookup_skipped is True
        assert report.peeringdb_lookup_skip_reason is None
        assert report.peering == {}

    def test_skipped_without_asn_numbers(self) -> None:
        report = HostReport(host="example.com", asn={"203.0.113.9": {}})
        _annotate_peering(report, enable_peeringdb_lookup=True)
        assert report.peeringdb_lookup_skipped is True
        assert report.peeringdb_lookup_skip_reason is not None
        assert "enable_asn_lookup" in report.peeringdb_lookup_skip_reason

    def test_queries_peeringdb_when_asn_known(self) -> None:
        report = HostReport(
            host="example.com",
            asn={"1.1.1.1": {"asn": "13335", "as_name": "CLOUDFLARENET"}},
        )
        with patch(
            "packetvoyage.preflight.peeringdb.annotate_asns",
            return_value={"13335": {"name": "Cloudflare, Inc.", "ix_count": 3}},
        ) as mock_annotate:
            _annotate_peering(report, enable_peeringdb_lookup=True)
        mock_annotate.assert_called_once_with(["13335"])
        assert report.peeringdb_lookup_skipped is False
        assert report.peering["13335"]["name"] == "Cloudflare, Inc."

    def test_drops_asns_with_no_peeringdb_record(self) -> None:
        report = HostReport(
            host="example.com",
            asn={"203.0.113.9": {"asn": "64512"}},
        )
        with patch("packetvoyage.preflight.peeringdb.annotate_asns", return_value={"64512": None}):
            _annotate_peering(report, enable_peeringdb_lookup=True)
        assert report.peeringdb_lookup_skipped is False
        assert report.peering == {}
