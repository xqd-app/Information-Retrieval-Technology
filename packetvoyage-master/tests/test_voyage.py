from packetvoyage import analyze, parser, sleuth

SAMPLE_TRANS_PACIFIC_TRACE = """
traceroute to 1.1.1.1 (1.1.1.1), 30 hops max, 60 byte packets
 1  gateway (192.168.1.1)  0.812 ms  0.780 ms
 2  * * *
 3  ae-1.tokyo-hnd.bb.net (203.0.113.1)  2.100 ms  2.050 ms
 4  xe-0-0.sjc-core.bb.net (198.51.100.25)  88.500 ms  88.450 ms
 5  one.one.one.one (1.1.1.1)  88.700 ms  88.650 ms
"""

SAMPLE_RTT_INVERSION_TRACE = """
traceroute to 8.8.8.8 (8.8.8.8), 30 hops max
 1  192.168.1.1  1.2 ms
 2  slow-cpu-router.isp.net (198.51.100.1)  75.0 ms  76.2 ms
 3  fast-edge.isp.net (198.51.100.2)  12.0 ms  12.1 ms
 4  dns.google (8.8.8.8)  12.5 ms  12.4 ms
"""


def test_parser_trans_pacific():
    trace = parser.parse_traceroute(SAMPLE_TRANS_PACIFIC_TRACE)
    assert len(trace.hops) == 5
    assert trace.hops[0].hop == 1
    assert trace.hops[1].loss == 100.0  # Silent gap
    assert trace.hops[2].iata == "HND"
    assert trace.hops[3].iata == "SJC"
    assert trace.completed is True


def test_sleuth_detects_mysteries():
    trace = parser.parse_traceroute(SAMPLE_TRANS_PACIFIC_TRACE)
    mysteries = sleuth.detect_mysteries(trace)
    kinds = [m.kind for m in mysteries]
    assert "silent_gap" in kinds

    # Test RTT inversion
    trace_inv = parser.parse_traceroute(SAMPLE_RTT_INVERSION_TRACE)
    mysteries_inv = sleuth.detect_mysteries(trace_inv)
    kinds_inv = [m.kind for m in mysteries_inv]
    assert "rtt_inversion" in kinds_inv


def test_analyze_voyage_narrative():
    trace = parser.parse_traceroute(SAMPLE_TRANS_PACIFIC_TRACE)
    voyage = analyze.analyze_voyage(trace)
    assert len(voyage.legs) >= 1
    assert len(voyage.oceanic_crossings) == 1
    assert "Trans-Pacific" in voyage.oceanic_crossings[0]
    assert len(voyage.narrative) >= 3
    assert len(voyage.route_summary) > 0
    assert "Tokyo" in voyage.route_summary
    assert "San Jose" in voyage.route_summary
    assert "Packet Voyage Journey Report" in voyage.detailed_story
