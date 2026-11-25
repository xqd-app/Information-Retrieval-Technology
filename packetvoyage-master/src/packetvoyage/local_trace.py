"""Local multi-protocol traceroute runner and probe battery.

Executes local traceroutes via standard platform tools (`traceroute`, `tracert`)
and runs protocol battery tests (ICMP, UDP, TCP) to compare firewall filtering
and routing differences across protocols.
"""

from __future__ import annotations

import logging
import platform
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

from packetvoyage.parser import ParsedTrace, parse_traceroute

logger = logging.getLogger("packetvoyage.local_trace")


def is_traceroute_available() -> bool:
    """Check if a platform traceroute binary is present on PATH."""
    system = platform.system().lower()
    if system == "windows":
        return shutil.which("tracert") is not None
    return shutil.which("traceroute") is not None or shutil.which("tracepath") is not None


def run_local_traceroute(
    target: str,
    protocol: str = "icmp",
    port: int | None = None,
    max_hops: int = 30,
    timeout_sec: int = 15,
) -> ParsedTrace:
    """Run a local traceroute to a target using specified protocol."""
    target = target.strip()
    if not target or target.startswith("-") or not re.match(r"^[a-zA-Z0-9.\-:_]+$", target):
        return ParsedTrace(destination=target, stop_reason="invalid_target")

    system = platform.system().lower()
    cmd: list[str] = []

    if system == "windows":
        cmd = ["tracert", "-h", str(max_hops), "-w", "1000", target]
    else:
        # Linux / BSD / macOS
        tr_bin = shutil.which("traceroute") or "traceroute"
        cmd = [tr_bin, "-m", str(max_hops), "-w", "1", "-q", "2"]

        proto = protocol.lower()
        if proto == "icmp":
            cmd.append("-I")
        elif proto == "tcp":
            cmd.extend(["-T", "-p", str(port or 443)])
        elif proto == "udp":
            cmd.extend(["-U", "-p", str(port or 53)])

        cmd.extend(["--", target])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        raw_output = proc.stdout
        if not raw_output and proc.stderr:
            raw_output = proc.stderr
    except subprocess.TimeoutExpired:
        raw_output = f"traceroute to {target} timed out after {timeout_sec}s"
    except Exception as exc:
        raw_output = f"Failed to execute traceroute: {exc}"

    trace = parse_traceroute(raw_output)
    if not trace.destination:
        trace.destination = target
    return trace


def run_protocol_battery(target: str, timeout_sec: int = 15) -> dict[str, ParsedTrace]:
    """Execute a parallel battery of protocol probes (ICMP, TCP/443, UDP/53).

    Helps students understand how firewalls and transport layers affect packet reachability.
    """
    probes = [
        ("icmp", "icmp", None),
        ("tcp_443", "tcp", 443),
        ("udp_53", "udp", 53),
    ]

    results: dict[str, ParsedTrace] = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        future_map = {
            pool.submit(run_local_traceroute, target, proto, port, 30, timeout_sec): name
            for name, proto, port in probes
        }
        for future in as_completed(future_map):
            name = future_map[future]
            try:
                results[name] = future.result()
            except Exception as e:
                logger.warning("Protocol probe %s failed: %s", name, e)

    return results
