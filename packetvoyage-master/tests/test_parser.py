"""Tests for universal traceroute parser (Linux, Windows, Looking Glass, JSON)."""

from packetvoyage import parser


def test_parse_windows_tracert():
    windows_output = """
Tracing route to 8.8.8.8 over a maximum of 30 hops

  1    <1 ms    <1 ms    <1 ms  192.168.1.1
  2     1 ms     1 ms     1 ms  10.0.0.1
  3     *        *        *     Request timed out.
  4    15 ms    14 ms    15 ms  dns.google (8.8.8.8)

Trace complete.
"""
    trace = parser.parse_traceroute(windows_output)
    assert trace.destination == "8.8.8.8"
    assert trace.destination_ip == "8.8.8.8"
    assert len(trace.hops) == 4
    assert trace.completed is True
    assert trace.stop_reason == "destination_reached"

    # Check hop 1 (<1 ms parsed as 0.5)
    assert trace.hops[0].hop == 1
    assert trace.hops[0].ip == "192.168.1.1"
    assert trace.hops[0].rtt_ms == 0.5

    # Check hop 3 (timeout)
    assert trace.hops[2].hop == 3
    assert trace.hops[2].ip is None
    assert trace.hops[2].loss == 100.0

    # Check hop 4 (destination reached)
    assert trace.hops[3].hop == 4
    assert trace.hops[3].ip == "8.8.8.8"
    assert trace.hops[3].hostname == "dns.google"


def test_parse_looking_glass_with_as_and_flags():
    lg_output = """
Type escape sequence to abort.
Tracing the route to 198.51.100.254

 1 192.0.2.1 [AS64496] 1.234 ms 1.100 ms
 2 border1.tyo.example.net (192.0.2.50) [AS64496] 3.500 ms 3.400 ms
 3 198.51.100.254 85.120 ms !H
"""
    trace = parser.parse_traceroute(lg_output)
    assert len(trace.hops) == 3
    assert trace.hops[0].asn == "AS64496"
    assert trace.hops[1].iata == "TYO"
    assert trace.hops[1].city == "Tokyo"
    assert "!H" in trace.hops[2].flags


def test_parse_json_dict_and_string():
    raw_dict = {
        "destination": "example.com",
        "destination_ip": "93.184.216.34",
        "hops": [
            {"hop": 1, "ip": "192.168.1.1", "rtt_ms": 1.2},
            {"hop": 2, "ip": "93.184.216.34", "hostname": "example.com", "rtt_ms": 15.4},
        ],
        "completed": True,
    }
    trace = parser.parse_traceroute(raw_dict)
    assert trace.destination == "example.com"
    assert len(trace.hops) == 2
    assert trace.completed is True

    # JSON string
    import json

    trace_json_str = parser.parse_traceroute(json.dumps(raw_dict))
    assert trace_json_str.destination == "example.com"
    assert len(trace_json_str.hops) == 2


def test_parse_globalping_format():
    globalping_dict = {
        "result": {
            "target": "1.1.1.1",
            "destination_ip": "1.1.1.1",
            "hops": [
                {"hop": 1, "ip": "10.0.0.1", "rtts": [1.0, 1.2]},
                {"hop": 2, "ip": "1.1.1.1", "ptr": "one.one.one.one", "rtts": [10.5]},
            ],
        }
    }
    trace = parser.parse_traceroute(globalping_dict)
    assert trace.destination == "1.1.1.1"
    assert len(trace.hops) == 2
    assert trace.hops[1].hostname == "one.one.one.one"
