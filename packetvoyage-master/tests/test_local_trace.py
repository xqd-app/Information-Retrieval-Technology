"""Tests for local_trace runner and protocol battery."""

import subprocess
from unittest.mock import MagicMock, patch

from packetvoyage import local_trace


def test_is_traceroute_available():
    with patch("shutil.which", return_value="/usr/bin/traceroute"):
        assert local_trace.is_traceroute_available() is True

    with patch("shutil.which", return_value=None):
        assert local_trace.is_traceroute_available() is False


def test_run_local_traceroute_success():
    sample_stdout = """
traceroute to 8.8.8.8 (8.8.8.8), 30 hops max
 1  192.168.1.1  1.123 ms
 2  dns.google (8.8.8.8)  14.567 ms
"""
    mock_proc = MagicMock()
    mock_proc.stdout = sample_stdout
    mock_proc.stderr = ""

    with patch("subprocess.run", return_value=mock_proc):
        trace = local_trace.run_local_traceroute("8.8.8.8", protocol="icmp")
        assert trace.destination == "8.8.8.8"
        assert trace.destination_ip == "8.8.8.8"
        assert len(trace.hops) == 2
        assert trace.completed is True


def test_run_local_traceroute_timeout():
    with patch(
        "subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="traceroute", timeout=15)
    ):
        trace = local_trace.run_local_traceroute("8.8.8.8")
        assert trace.destination == "8.8.8.8"
        assert trace.completed is False


def test_run_protocol_battery():
    sample_trace = local_trace.ParsedTrace(
        destination="8.8.8.8",
        completed=True,
    )
    with patch("packetvoyage.local_trace.run_local_traceroute", return_value=sample_trace):
        battery_results = local_trace.run_protocol_battery("8.8.8.8")
        assert "icmp" in battery_results
        assert "tcp_443" in battery_results
        assert "udp_53" in battery_results
        assert battery_results["icmp"].completed is True


def test_run_local_traceroute_invalid_target():
    trace = local_trace.run_local_traceroute("-F")
    assert trace.stop_reason == "invalid_target"

    trace2 = local_trace.run_local_traceroute("example.com; rm -rf /")
    assert trace2.stop_reason == "invalid_target"
