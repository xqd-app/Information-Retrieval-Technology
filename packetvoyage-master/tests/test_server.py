"""Tests for FastMCP server endpoints and tool functions."""

from unittest.mock import patch

from packetvoyage import server


def test_analyze_voyage_text_endpoint():
    sample_trace = """
traceroute to 8.8.8.8 (8.8.8.8), 30 hops max
 1  192.168.1.1  1.0 ms
 2  dns.google (8.8.8.8)  15.0 ms
"""
    result = server.analyze_voyage_text(sample_trace)
    assert result["destination"] == "8.8.8.8"
    assert result["completed"] is True
    assert result["total_hops"] == 2
    assert "voyage_narrative" in result
    assert "route_summary" in result
    assert "detailed_story" in result
    assert "casefile_summary" in result


def test_voyage_investigate_endpoint_with_data():
    sample_trace = """
 1  192.168.1.1  1.0 ms
 2  ae-1.tokyo-hnd.bb.net (203.0.113.1)  2.5 ms
 3  xe-0.sjc-core.bb.net (198.51.100.25)  88.5 ms
 4  8.8.8.8  89.0 ms
"""
    res = server.voyage_investigate(data=sample_trace)
    assert "PacketVoyage Case File" in res
    assert "Packet Voyage Journey Report" in res
    assert "Summary Route Flow" in res


def test_voyage_investigate_endpoint_no_args():
    res = server.voyage_investigate()
    assert "Error:" in res


def test_list_known_iata_airports_endpoint():
    res = server.list_known_iata_airports()
    assert "airports" in res
    assert "HND" in res["airports"]
    assert "NRT" in res["airports"]
    assert "SJC" in res["airports"]
    assert "Tokyo" in res["airports"]["HND"]["city"]


def test_research_host_endpoint():
    from packetvoyage.preflight import HostReport

    mock_report = HostReport(
        host="example.com",
        verdict="direct",
        addresses=["93.184.216.34"],
    )
    with patch("packetvoyage.preflight.research_host", return_value=mock_report):
        res = server.research_host("example.com")
        assert res["host"] == "example.com"
        assert res["verdict"] == "direct"
        assert "report" in res
