"""Tests for Network Sleuth mystery detection and case file builder."""

from packetvoyage import sleuth
from packetvoyage.parser import Hop, ParsedTrace


def test_detect_silent_gap():
    trace = ParsedTrace(
        destination="8.8.8.8",
        destination_ip="8.8.8.8",
        completed=True,
        hops=[
            Hop(hop=1, ip="192.168.1.1", rtt_ms=1.0),
            Hop(hop=2, ip=None, rtt_ms=None, loss=100.0),
            Hop(hop=3, ip=None, rtt_ms=None, loss=100.0),
            Hop(hop=4, ip="8.8.8.8", rtt_ms=15.0),
        ],
    )
    mysteries = sleuth.detect_mysteries(trace)
    kinds = [m.kind for m in mysteries]
    assert "silent_gap" in kinds
    gap_m = next(m for m in mysteries if m.kind == "silent_gap")
    assert gap_m.hops_involved == [2, 3]


def test_detect_rtt_inversion():
    trace = ParsedTrace(
        destination="8.8.8.8",
        destination_ip="8.8.8.8",
        completed=True,
        hops=[
            Hop(hop=1, ip="192.168.1.1", rtt_ms=1.0),
            Hop(hop=2, ip="10.0.0.1", rtt_ms=95.0),  # Slow ICMP generation
            Hop(hop=3, ip="8.8.8.8", rtt_ms=12.0),
        ],
    )
    mysteries = sleuth.detect_mysteries(trace)
    kinds = [m.kind for m in mysteries]
    assert "rtt_inversion" in kinds
    inv_m = next(m for m in mysteries if m.kind == "rtt_inversion")
    assert inv_m.hop_index == 2


def test_detect_geo_contradiction():
    # Tokyo to USA in 1ms latency delta -> impossible physically
    trace = ParsedTrace(
        destination="example.com",
        destination_ip="93.184.216.34",
        completed=True,
        hops=[
            Hop(
                hop=1,
                ip="192.0.2.1",
                hostname="hnd-core.net",
                iata="HND",
                city="Tokyo",
                country="Japan",
                lat=35.5494,
                lon=139.7798,
                rtt_ms=2.0,
            ),
            Hop(
                hop=2,
                ip="198.51.100.1",
                hostname="sjc-core.net",
                iata="SJC",
                city="San Jose",
                country="United States",
                lat=37.3619,
                lon=-121.9290,
                rtt_ms=2.8,  # Only 0.8ms delta for 8000+km distance!
            ),
        ],
    )
    mysteries = sleuth.detect_mysteries(trace)
    kinds = [m.kind for m in mysteries]
    assert "geo_contradiction" in kinds or "physics_violation" in kinds


def test_detect_path_loop():
    trace = ParsedTrace(
        destination="8.8.8.8",
        completed=False,
        stop_reason="max_hops_truncated",
        hops=[
            Hop(hop=1, ip="192.168.1.1", rtt_ms=1.0),
            Hop(hop=2, ip="10.0.0.1", rtt_ms=5.0),
            Hop(hop=3, ip="10.0.0.2", rtt_ms=6.0),
            Hop(hop=4, ip="10.0.0.1", rtt_ms=7.0),  # Loop back to 10.0.0.1
        ],
    )
    mysteries = sleuth.detect_mysteries(trace)
    kinds = [m.kind for m in mysteries]
    assert "path_loop" in kinds


def test_detect_jitter_anomaly():
    trace = ParsedTrace(
        destination="8.8.8.8",
        completed=True,
        hops=[
            Hop(hop=1, ip="192.168.1.1", rtt_ms=1.0, rtts=[1.0, 1.1]),
            Hop(hop=2, ip="10.0.0.1", rtt_ms=5.0, rtts=[5.0, 150.0, 10.0]),  # Max - Min = 145ms
            Hop(hop=3, ip="8.8.8.8", rtt_ms=10.0, rtts=[10.0, 10.2]),
        ],
    )
    mysteries = sleuth.detect_mysteries(trace)
    kinds = [m.kind for m in mysteries]
    assert "jitter_anomaly" in kinds


def test_build_and_format_casefile():
    trace = ParsedTrace(
        destination="example.com",
        destination_ip="93.184.216.34",
        completed=True,
        hops=[
            Hop(hop=1, ip="192.168.1.1", rtt_ms=1.0),
            Hop(hop=2, ip="93.184.216.34", rtt_ms=15.0),
        ],
    )
    casefile = sleuth.build_casefile(trace)
    assert casefile.completed is True
    assert casefile.total_hops == 2

    formatted = sleuth.format_casefile(casefile)
    assert "PacketVoyage Case File" in formatted
    assert "example.com" in formatted
